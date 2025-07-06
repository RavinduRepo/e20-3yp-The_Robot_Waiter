#!/usr/bin/env python3
"""
WebRTC Receiver for Raspberry Pi
Receives audio from caller and sends video/audio to caller
No web interface required - runs as a standalone Python script
Prioritizes video functionality - continues working even if audio fails
"""

import asyncio
import json
import logging
import signal
import sys
from typing import Optional
import numpy as np

# Third-party imports
import cv2
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, VideoStreamTrack, AudioStreamTrack
from aiortc.contrib.media import MediaPlayer, MediaRecorder
from aiortc.contrib.signaling import object_to_string, object_from_string
import threading
import time

# Optional audio import - gracefully handle if not available
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False
    logging.warning("PyAudio not available - audio functionality will be disabled")

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
        self.video_enabled = False
        self.audio_enabled = False
        
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
        
        # Audio setup for playback (only if available)
        if AUDIO_AVAILABLE:
            self.audio_format = pyaudio.paInt16
            self.channels = 1
            self.rate = 44100
            self.chunk = 1024
            self.audio = None
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
            camera_found = False
            for camera_index in [0, 1, 2]:
                try:
                    cap = cv2.VideoCapture(camera_index)
                    if cap.isOpened():
                        # Test if we can actually read from the camera
                        ret, frame = cap.read()
                        if ret and frame is not None:
                            # Set camera properties for better performance
                            cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                            cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                            cap.set(cv2.CAP_PROP_FPS, 30)
                            self.camera = cap
                            self.video_enabled = True
                            logger.info(f"Camera initialized successfully on index {camera_index}")
                            return True
                        else:
                            cap.release()
                    else:
                        cap.release()
                except Exception as e:
                    logger.warning(f"Camera index {camera_index} failed: {e}")
                    if 'cap' in locals():
                        cap.release()
            
            logger.error("No working camera found")
            self.video_enabled = False
            return False
            
        except Exception as e:
            logger.error(f"Failed to setup camera: {e}")
            self.video_enabled = False
            return False
    
    def setup_audio(self):
        """Initialize audio for recording and playback"""
        if not AUDIO_AVAILABLE:
            logger.warning("Audio not available - skipping audio setup")
            self.audio_enabled = False
            return False
            
        try:
            # Initialize PyAudio
            self.audio = pyaudio.PyAudio()
            
            # Setup audio stream for playback (hearing caller)
            self.audio_stream = self.audio.open(
                format=self.audio_format,
                channels=self.channels,
                rate=self.rate,
                output=True,
                frames_per_buffer=self.chunk
            )
            self.audio_enabled = True
            logger.info("Audio initialized successfully")
            return True
            
        except Exception as e:
            logger.warning(f"Failed to setup audio (continuing without audio): {e}")
            self.audio_enabled = False
            if hasattr(self, 'audio_stream') and self.audio_stream:
                try:
                    self.audio_stream.close()
                except:
                    pass
            if hasattr(self, 'audio') and self.audio:
                try:
                    self.audio.terminate()
                except:
                    pass
            return False
    
    async def create_peer_connection(self):
        """Create and configure RTCPeerConnection"""
        self.pc = RTCPeerConnection(self.rtc_configuration)
        
        # Add local media tracks (camera + microphone)
        if self.setup_camera():
            # Create video track from camera
            self.local_video = CameraVideoTrack(self.camera)
            self.pc.addTrack(self.local_video)
            logger.info("Video track added to peer connection")
        else:
            logger.warning("No video track - continuing without camera")
            
        if self.setup_audio():
            # Create audio track from microphone
            try:
                self.local_audio = MicrophoneAudioTrack()
                self.pc.addTrack(self.local_audio)
                logger.info("Audio track added to peer connection")
            except Exception as e:
                logger.warning(f"Failed to add audio track (continuing without audio): {e}")
                self.audio_enabled = False
        else:
            logger.warning("No audio track - continuing without microphone")
        
        # Handle incoming media
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Received track: {track.kind}")
            if track.kind == "audio" and self.audio_enabled:
                # Play received audio
                try:
                    asyncio.create_task(self.play_audio_track(track))
                except Exception as e:
                    logger.warning(f"Failed to play audio track: {e}")
            elif track.kind == "video":
                # We don't need to display video from caller
                logger.info("Received video track (not displaying)")
        
        # Handle ICE candidates
        @self.pc.on("icecandidate")
        def on_icecandidate(candidate):
            if candidate:
                try:
                    asyncio.create_task(self.send_ice_candidate(candidate))
                except Exception as e:
                    logger.warning(f"Failed to send ICE candidate: {e}")
        
        # Handle connection state changes
        @self.pc.on("connectionstatechange")
        def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                logger.error("Connection failed")
                # Don't cleanup immediately - try to reconnect
                logger.info("Attempting to continue despite connection failure")
            elif self.pc.connectionState == "connected":
                logger.info("WebRTC connection established successfully")
    
    async def play_audio_track(self, track):
        """Play received audio track"""
        if not self.audio_enabled:
            logger.warning("Audio not enabled - skipping audio playback")
            return
            
        try:
            while self.running and self.audio_stream:
                try:
                    frame = await track.recv()
                    # Convert frame to bytes and play
                    if self.audio_stream and hasattr(frame, 'to_ndarray'):
                        try:
                            # Convert the audio frame to the format expected by PyAudio
                            audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                            self.audio_stream.write(audio_data)
                        except Exception as e:
                            logger.warning(f"Audio frame conversion error: {e}")
                except Exception as e:
                    logger.warning(f"Error receiving audio frame: {e}")
                    break
        except Exception as e:
            logger.warning(f"Error in audio playback: {e}")
    
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
            logger.warning(f"Failed to send ICE candidate: {e}")
    
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
                    try:
                        doc = call_ref.get()
                        if doc.exists and doc.to_dict().get('offer'):
                            break
                    except Exception as e:
                        logger.warning(f"Error checking for offer: {e}")
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
            asyncio.create_task(self.listen_for_ice_candidates())
            
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
            
            while self.running and self.pc.connectionState not in ["closed"]:
                try:
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
                except Exception as e:
                    logger.warning(f"Error processing ICE candidates: {e}")
                
                await asyncio.sleep(1)
                
        except Exception as e:
            logger.warning(f"Error listening for ICE candidates: {e}")
    
    async def start(self):
        """Start the WebRTC receiver"""
        try:
            self.running = True
            logger.info(f"Starting WebRTC receiver for call ID: {self.call_id}")
            
            # Create peer connection
            await self.create_peer_connection()
            
            # Check what functionality is available
            if not self.video_enabled and not self.audio_enabled:
                logger.error("Neither video nor audio is available - cannot continue")
                return
            elif not self.video_enabled:
                logger.warning("Video not available - continuing with audio only")
            elif not self.audio_enabled:
                logger.warning("Audio not available - continuing with video only")
            else:
                logger.info("Both video and audio are available")
            
            # Listen for and handle the call
            success = await self.listen_for_offer()
            
            if success:
                logger.info("Call connected successfully")
                # Keep the connection alive
                while self.running:
                    # Check connection state and try to maintain connection
                    if self.pc.connectionState == "closed":
                        logger.warning("Connection closed")
                        break
                    elif self.pc.connectionState == "failed":
                        logger.warning("Connection failed - but continuing to try")
                    
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
        
        try:
            if self.pc:
                # Create a new event loop for cleanup if needed
                try:
                    loop = asyncio.get_event_loop()
                    if loop.is_running():
                        asyncio.create_task(self.pc.close())
                    else:
                        loop.run_until_complete(self.pc.close())
                except:
                    pass
        except Exception as e:
            logger.warning(f"Error closing peer connection: {e}")
            
        try:
            if hasattr(self, 'camera') and self.camera:
                self.camera.release()
        except Exception as e:
            logger.warning(f"Error releasing camera: {e}")
            
        try:
            if self.audio_stream:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
        except Exception as e:
            logger.warning(f"Error closing audio stream: {e}")
            
        try:
            if hasattr(self, 'audio') and self.audio:
                self.audio.terminate()
        except Exception as e:
            logger.warning(f"Error terminating audio: {e}")
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info("Received shutdown signal")
        self.cleanup()
        sys.exit(0)


# Custom video track for camera
class CameraVideoTrack(VideoStreamTrack):
    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.frame_count = 0
    
    async def recv(self):
        """Capture and return video frame"""
        try:
            ret, frame = self.camera.read()
            if ret and frame is not None:
                self.frame_count += 1
                # Convert OpenCV BGR to RGB
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                
                # Create aiortc VideoFrame
                from aiortc import VideoFrame
                av_frame = VideoFrame.from_ndarray(frame, format="rgb24")
                av_frame.pts = self.frame_count
                av_frame.time_base = 1/30  # 30 FPS
                
                return av_frame
            else:
                logger.warning("Failed to capture video frame")
                return None
        except Exception as e:
            logger.warning(f"Error in video capture: {e}")
            return None


# Custom audio track for microphone
class MicrophoneAudioTrack(AudioStreamTrack):
    def __init__(self):
        super().__init__()
        if not AUDIO_AVAILABLE:
            raise Exception("PyAudio not available")
            
        # Initialize microphone recording
        self.audio = pyaudio.PyAudio()
        self.stream = self.audio.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=44100,
            input=True,
            frames_per_buffer=1024
        )
        self.frame_count = 0
    
    async def recv(self):
        """Capture and return audio frame"""
        try:
            data = self.stream.read(1024, exception_on_overflow=False)
            self.frame_count += 1
            
            # Convert to aiortc AudioFrame
            from aiortc import AudioFrame
            
            # Convert bytes to numpy array
            audio_array = np.frombuffer(data, dtype=np.int16)
            
            # Create AudioFrame
            frame = AudioFrame(format="s16", layout="mono", samples=len(audio_array))
            frame.planes[0].update(audio_array.tobytes())
            frame.pts = self.frame_count
            frame.sample_rate = 44100
            
            return frame
        except Exception as e:
            logger.warning(f"Error capturing audio: {e}")
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
    except Exception as e:
        logger.error(f"Unexpected error: {e}")
        receiver.cleanup()


if __name__ == "__main__":
    asyncio.run(main())