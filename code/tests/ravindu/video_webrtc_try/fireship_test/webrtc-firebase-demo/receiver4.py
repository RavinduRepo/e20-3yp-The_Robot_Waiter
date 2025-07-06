#!/usr/bin/env python3
"""
WebRTC Receiver for Raspberry Pi
Receives audio from caller and sends video/audio to caller
No web interface required - runs as a standalone Python script
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Optional

# Third-party imports
import cv2
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import object_to_string, object_from_string
import pyaudio
import threading
import time

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class WebRTCReceiver:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.pc: Optional[RTCPeerConnection] = None
        self.local_video = None
        self.local_audio = None
        self.running = False
        
        # Firebase configuration
        self.firebase_config = {
            "apiKey": "AIzaSyBubdSfljjucCKUUwEwh15EtZFLywbsGEQ",
            "authDomain": "test-webrtc-f155e.firebaseapp.com",
            "projectId": "test-webrtc-f155e",
            "storageBucket": "test-webrtc-f155e.firebasestorage.app",
            "messagingSenderId": "674163171327",
            "appId": "1:674163171327:web:c8f988f1605a01bd9291ca",
            "measurementId": "G-VV8L1PP7GZ"
        }
        
        # WebRTC configuration
        self.rtc_configuration = {
            "iceServers": [
                {"urls": "stun:stun.l.google.com:19302"},
                {"urls": "stun:stun1.l.google.com:19302"},
                {
                    "urls": "turn:relay.metered.ca:80",
                    "username": "openai",
                    "credential": "openai"
                },
                {
                    "urls": "turn:relay.metered.ca:443",
                    "username": "openai",
                    "credential": "openai"
                }
            ]
        }
        
        # Initialize Firebase
        self.init_firebase()
        
        # Audio setup for playback
        self.audio_format = pyaudio.paInt16
        self.channels = 1
        self.rate = 44100
        self.chunk = 1024
        self.audio = pyaudio.PyAudio()
        self.audio_stream = None
        
    def init_firebase(self):
        """Initialize Firebase connection"""
        try:
            # Initialize Firebase Admin SDK
            # Note: You'll need to download your service account key file
            # and place it in the same directory as this script
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("Firebase initialized successfully")
        except Exception as e:
            logger.error(f"Failed to initialize Firebase: {e}")
            # For development, you can use the REST API instead
            # This is a simplified approach - in production, use proper authentication
            self.db = None
            logger.warning("Using fallback Firebase connection")
    
    def setup_camera(self):
        """Initialize camera for video capture"""
        try:
            # Try different camera indices (0, 1, 2) for Raspberry Pi
            for camera_index in [0, 1, 2]:
                cap = cv2.VideoCapture(camera_index)
                if cap.isOpened():
                    # Set camera properties for better performance
                    cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                    cap.set(cv2.CAP_PROP_FPS, 30)
                    self.camera = cap
                    logger.info(f"Camera initialized on index {camera_index}")
                    return True
                cap.release()
            
            logger.error("No camera found")
            return False
        except Exception as e:
            logger.error(f"Failed to setup camera: {e}")
            return False
    
    def setup_audio(self):
        """Initialize audio for recording and playback"""
        try:
            # Setup audio stream for playback (hearing caller)
            self.audio_stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk
            )
            logger.info("Audio initialized successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to setup audio: {e}")
            return False
    
    async def create_peer_connection(self):
        """Create and configure RTCPeerConnection"""
        self.pc = RTCPeerConnection(self.rtc_configuration)
        
        # Add local media tracks (camera + microphone)
        if self.setup_camera():
            # Create video track from camera
            self.local_video = CameraVideoTrack(self.camera)
            self.pc.addTrack(self.local_video)
            
        if self.setup_audio():
            # Create audio track from microphone
            self.local_audio = MicrophoneAudioTrack()
            self.pc.addTrack(self.local_audio)
        
        # Handle incoming media
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Received track: {track.kind}")
            if track.kind == "audio":
                # Play received audio
                asyncio.create_task(self.play_audio_track(track))
            elif track.kind == "video":
                # We don't need to display video from caller
                logger.info("Received video track (not displaying)")
        
        # Handle ICE candidates
        @self.pc.on("icecandidate")
        def on_icecandidate(candidate):
            if candidate:
                asyncio.create_task(self.send_ice_candidate(candidate))
        
        # Handle connection state changes
        @self.pc.on("connectionstatechange")
        def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                logger.error("Connection failed")
                self.cleanup()
    
    async def play_audio_track(self, track):
        """Play received audio track"""
        try:
            while self.running:
                frame = await track.recv()
                # Convert frame to bytes and play
                if self.audio_stream:
                    # This is a simplified approach - you might need to convert
                    # the audio frame format to match your audio stream
                    audio_data = frame.to_ndarray().tobytes()
                    self.audio_stream.write(audio_data)
        except Exception as e:
            logger.error(f"Error playing audio: {e}")
    
    async def send_ice_candidate(self, candidate):
        """Send ICE candidate to Firebase"""
        try:
            if self.db:
                candidate_data = {
                    "candidate": candidate.candidate,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "sdpMid": candidate.sdpMid
                }
                
                self.db.collection('calls').document(self.call_id)\
                    .collection('answerCandidates').add(candidate_data)
                
                logger.info("ICE candidate sent")
        except Exception as e:
            logger.error(f"Failed to send ICE candidate: {e}")
    
    async def listen_for_offer(self):
        """Listen for incoming call offer"""
        try:
            if not self.db:
                logger.error("Firebase not initialized")
                return False
                
            call_ref = self.db.collection('calls').document(self.call_id)
            
            # Wait for offer
            doc = call_ref.get()
            if not doc.exists:
                logger.info(f"Waiting for call {self.call_id}...")
                # In a real implementation, you'd use Firebase listeners
                # For now, we'll poll (not ideal but works for demo)
                while self.running:
                    doc = call_ref.get()
                    if doc.exists and doc.to_dict().get('offer'):
                        break
                    await asyncio.sleep(1)
            
            if not self.running:
                return False
                
            call_data = doc.to_dict()
            offer = call_data.get('offer')
            
            if not offer:
                logger.error("No offer found")
                return False
                
            # Set remote description
            await self.pc.setRemoteDescription(
                RTCSessionDescription(offer['sdp'], offer['type'])
            )
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            # Send answer to Firebase
            answer_data = {
                "answer": {
                    "sdp": answer.sdp,
                    "type": answer.type
                }
            }
            call_ref.update(answer_data)
            
            logger.info("Call answered successfully")
            
            # Listen for ICE candidates from caller
            await self.listen_for_ice_candidates()
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to handle offer: {e}")
            return False
    
    async def listen_for_ice_candidates(self):
        """Listen for ICE candidates from caller"""
        try:
            if not self.db:
                return
                
            # This is a simplified polling approach
            # In production, use Firebase real-time listeners
            offer_candidates_ref = self.db.collection('calls').document(self.call_id)\
                .collection('offerCandidates')
            
            processed_candidates = set()
            
            while self.running and self.pc.connectionState != "closed":
                docs = offer_candidates_ref.get()
                
                for doc in docs:
                    if doc.id not in processed_candidates:
                        candidate_data = doc.to_dict()
                        candidate = RTCIceCandidate(
                            candidate_data['candidate'],
                            candidate_data.get('sdpMLineIndex'),
                            candidate_data.get('sdpMid')
                        )
                        await self.pc.addIceCandidate(candidate)
                        processed_candidates.add(doc.id)
                        logger.info("Added ICE candidate")
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.error(f"Error listening for ICE candidates: {e}")
    
    async def start(self):
        """Start the WebRTC receiver"""
        try:
            self.running = True
            logger.info(f"Starting WebRTC receiver for call ID: {self.call_id}")
            
            # Create peer connection
            await self.create_peer_connection()
            
            # Listen for and handle the call
            success = await self.listen_for_offer()
            
            if success:
                logger.info("Call connected successfully")
                # Keep the connection alive
                while self.running and self.pc.connectionState not in ["closed", "failed"]:
                    await asyncio.sleep(1)
            else:
                logger.error("Failed to connect call")
                
        except Exception as e:
            logger.error(f"Error in start: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        self.running = False
        
        if self.pc:
            asyncio.create_task(self.pc.close())
            
        if hasattr(self, 'camera') and self.camera:
            self.camera.release()
            
        if self.audio_stream:
            self.audio_stream.stop_stream()
            self.audio_stream.close()
            
        if self.audio:
            self.audio.terminate()
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal")
        self.cleanup()
        sys.exit(0)


# Custom video track for camera
class CameraVideoTrack:
    def __init__(self, camera):
        self.camera = camera
        self.kind = "video"
    
    async def recv(self):
        """Capture and return video frame"""
        ret, frame = self.camera.read()
        if ret:
            # Convert OpenCV frame to aiortc VideoFrame
            # This is a simplified conversion - you might need to adjust
            return frame
        return None


# Custom audio track for microphone
class MicrophoneAudioTrack:
    def __init__(self):
        self.kind = "audio"
        # Initialize microphone recording
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            frames_per_buffer=1024
        )
    
    async def recv(self):
        """Capture and return audio frame"""
        try:
            data = self.stream.read(1024)
            # Convert to aiortc AudioFrame
            # This is a simplified conversion
            return data
        except Exception as e:
            logger.error(f"Error capturing audio: {e}")
            return None


async def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python3 webrtc_receiver.py <call_id>")
        sys.exit(1)
    
    call_id = sys.argv[1]
    receiver = WebRTCReceiver(call_id)
    
    # Set up signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, receiver.signal_handler)
    signal.signal(signal.SIGTERM, receiver.signal_handler)
    
    try:
        await receiver.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
        receiver.cleanup()


if __name__ == "__main__":
    asyncio.run(main())