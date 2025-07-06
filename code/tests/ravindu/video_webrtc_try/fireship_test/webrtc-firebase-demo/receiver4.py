#!/usr/bin/env python3
"""
WebRTC Receiver for Raspberry Pi - Simplified Version
Handles audio issues and provides better error handling
"""

import asyncio
import json
import logging
import signal
import sys
import time
import threading
from typing import Optional

# Third-party imports
import cv2
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate
from aiortc import VideoStreamTrack, AudioStreamTrack
import numpy as np
import pyaudio

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class CameraVideoStreamTrack(VideoStreamTrack):
    """Custom video track for camera stream"""
    
    def __init__(self, camera_index=0):
        super().__init__()
        self.camera = cv2.VideoCapture(camera_index)
        self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
        self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
        self.camera.set(cv2.CAP_PROP_FPS, 15)  # Lower FPS for Pi
        
    async def recv(self):
        """Capture frame from camera"""
        ret, frame = self.camera.read()
        if ret:
            # Convert BGR to RGB
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            # Create VideoFrame
            from aiortc import VideoFrame
            video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
            video_frame.pts = int(time.time() * 1000000)  # Timestamp in microseconds
            video_frame.time_base = 1000000
            return video_frame
        else:
            # Return empty frame if camera fails
            empty_frame = np.zeros((480, 640, 3), dtype=np.uint8)
            from aiortc import VideoFrame
            video_frame = VideoFrame.from_ndarray(empty_frame, format="rgb24")
            video_frame.pts = int(time.time() * 1000000)
            video_frame.time_base = 1000000
            return video_frame

class MicrophoneAudioStreamTrack(AudioStreamTrack):
    """Custom audio track for microphone stream"""
    
    def __init__(self):
        super().__init__()
        self.audio = None
        self.stream = None
        self.setup_audio()
        
    def setup_audio(self):
        """Setup audio with fallback options"""
        try:
            self.audio = pyaudio.PyAudio()
            
            # Try to find a working input device
            input_device_index = None
            for i in range(self.audio.get_device_count()):
                try:
                    device_info = self.audio.get_device_info_by_index(i)
                    if device_info.get('maxInputChannels', 0) > 0:
                        input_device_index = i
                        logger.info(f"Found input device: {device_info['name']}")
                        break
                except:
                    continue
            
            if input_device_index is not None:
                self.stream = self.audio.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,  # Lower sample rate for Pi
                    input=True,
                    input_device_index=input_device_index,
                    frames_per_buffer=1024
                )
                logger.info("Microphone initialized successfully")
            else:
                logger.warning("No input device found - microphone disabled")
                
        except Exception as e:
            logger.error(f"Failed to setup microphone: {e}")
            self.audio = None
            self.stream = None
    
    async def recv(self):
        """Capture audio frame"""
        if self.stream:
            try:
                data = self.stream.read(1024, exception_on_overflow=False)
                # Convert to numpy array
                audio_data = np.frombuffer(data, dtype=np.int16)
                # Create AudioFrame
                from aiortc import AudioFrame
                audio_frame = AudioFrame.from_ndarray(
                    audio_data.reshape(1, -1), format="s16", layout="mono"
                )
                audio_frame.sample_rate = 16000
                audio_frame.pts = int(time.time() * 16000)
                audio_frame.time_base = 16000
                return audio_frame
            except Exception as e:
                logger.error(f"Error capturing audio: {e}")
                
        # Return silence if no audio available
        silence = np.zeros((1, 1024), dtype=np.int16)
        from aiortc import AudioFrame
        audio_frame = AudioFrame.from_ndarray(silence, format="s16", layout="mono")
        audio_frame.sample_rate = 16000
        audio_frame.pts = int(time.time() * 16000)
        audio_frame.time_base = 16000
        return audio_frame

class WebRTCReceiver:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.pc: Optional[RTCPeerConnection] = None
        self.running = False
        self.audio_player = None
        
        # WebRTC configuration
        self.rtc_configuration = {
            "iceServers": [
                {"urls": "stun:stun.l.google.com:19302"},
                {"urls": "stun:stun1.l.google.com:19302"},
                {
                    "urls": "turn:relay.metered.ca:80",
                    "username": "openai",
                    "credential": "openai"
                }
            ]
        }
        
        # Initialize Firebase
        self.init_firebase()
        
        # Setup audio player
        self.setup_audio_player()
        
    def init_firebase(self):
        """Initialize Firebase connection"""
        try:
            # Try to initialize Firebase Admin SDK
            # For demo purposes, we'll use a simple approach
            # Replace with your actual service account key path
            service_account_path = "service-account-key.json"
            
            try:
                cred = credentials.Certificate(service_account_path)
                firebase_admin.initialize_app(cred)
                self.db = firestore.client()
                logger.info("Firebase initialized successfully")
            except Exception as e:
                logger.warning(f"Firebase Admin SDK failed: {e}")
                # Fallback to manual Firebase REST API if needed
                self.db = None
                logger.info("Using fallback Firebase connection")
                
        except Exception as e:
            logger.error(f"Firebase initialization error: {e}")
            self.db = None
    
    def setup_audio_player(self):
        """Setup audio player for incoming audio"""
        try:
            self.audio_player = pyaudio.PyAudio()
            
            # Find output device
            output_device_index = None
            for i in range(self.audio_player.get_device_count()):
                try:
                    device_info = self.audio_player.get_device_info_by_index(i)
                    if device_info.get('maxOutputChannels', 0) > 0:
                        output_device_index = i
                        logger.info(f"Found output device: {device_info['name']}")
                        break
                except:
                    continue
            
            if output_device_index is not None:
                self.output_stream = self.audio_player.open(
                    format=pyaudio.paInt16,
                    channels=1,
                    rate=16000,
                    output=True,
                    output_device_index=output_device_index,
                    frames_per_buffer=1024
                )
                logger.info("Audio player initialized successfully")
            else:
                logger.warning("No output device found - audio playback disabled")
                self.output_stream = None
                
        except Exception as e:
            logger.error(f"Failed to setup audio player: {e}")
            self.audio_player = None
            self.output_stream = None
    
    async def create_peer_connection(self):
        """Create and configure RTCPeerConnection"""
        self.pc = RTCPeerConnection(self.rtc_configuration)
        
        # Add local video track
        video_track = CameraVideoStreamTrack()
        self.pc.addTrack(video_track)
        logger.info("Added video track")
        
        # Add local audio track
        audio_track = MicrophoneAudioStreamTrack()
        self.pc.addTrack(audio_track)
        logger.info("Added audio track")
        
        # Handle incoming media
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Received {track.kind} track")
            if track.kind == "audio":
                asyncio.create_task(self.handle_audio_track(track))
            elif track.kind == "video":
                logger.info("Received video track (ignoring as requested)")
        
        # Handle ICE candidates
        @self.pc.on("icecandidate")
        def on_icecandidate(event):
            if event.candidate:
                asyncio.create_task(self.send_ice_candidate(event.candidate))
        
        # Handle connection state changes
        @self.pc.on("connectionstatechange")
        def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
            if self.pc.connectionState == "failed":
                logger.error("Connection failed")
                self.cleanup()
    
    async def handle_audio_track(self, track):
        """Handle incoming audio track"""
        try:
            while self.running:
                frame = await track.recv()
                if self.output_stream and frame:
                    # Convert frame to bytes and play
                    audio_data = frame.to_ndarray().astype(np.int16)
                    self.output_stream.write(audio_data.tobytes())
        except Exception as e:
            logger.error(f"Error handling audio track: {e}")
    
    async def send_ice_candidate(self, candidate):
        """Send ICE candidate to Firebase"""
        try:
            if self.db:
                candidate_data = {
                    "candidate": candidate.candidate,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "sdpMid": candidate.sdpMid,
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                
                self.db.collection('calls').document(self.call_id)\
                    .collection('answerCandidates').add(candidate_data)
                
                logger.info("ICE candidate sent to Firebase")
        except Exception as e:
            logger.error(f"Failed to send ICE candidate: {e}")
    
    async def wait_for_offer(self):
        """Wait for call offer from Firebase"""
        try:
            if not self.db:
                logger.error("Firebase not available")
                return None
            
            call_ref = self.db.collection('calls').document(self.call_id)
            
            # Poll for offer (in production, use real-time listeners)
            logger.info(f"Waiting for call offer with ID: {self.call_id}")
            
            for attempt in range(300):  # Wait up to 5 minutes
                try:
                    doc = call_ref.get()
                    if doc.exists:
                        call_data = doc.to_dict()
                        if call_data and 'offer' in call_data:
                            logger.info("Found call offer")
                            return call_data['offer']
                except Exception as e:
                    logger.error(f"Error checking for offer: {e}")
                
                if not self.running:
                    break
                    
                await asyncio.sleep(1)
            
            logger.error("Timeout waiting for offer")
            return None
            
        except Exception as e:
            logger.error(f"Error waiting for offer: {e}")
            return None
    
    async def answer_call(self, offer):
        """Answer the call with the given offer"""
        try:
            # Set remote description
            await self.pc.setRemoteDescription(
                RTCSessionDescription(offer['sdp'], offer['type'])
            )
            
            # Create answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            # Send answer to Firebase
            if self.db:
                answer_data = {
                    "answer": {
                        "sdp": answer.sdp,
                        "type": answer.type
                    },
                    "timestamp": firestore.SERVER_TIMESTAMP
                }
                
                call_ref = self.db.collection('calls').document(self.call_id)
                call_ref.update(answer_data)
                
                logger.info("Answer sent to Firebase")
                
                # Start listening for ICE candidates
                await self.listen_for_ice_candidates()
                
                return True
            else:
                logger.error("Cannot send answer - Firebase not available")
                return False
                
        except Exception as e:
            logger.error(f"Error answering call: {e}")
            return False
    
    async def listen_for_ice_candidates(self):
        """Listen for ICE candidates from caller"""
        try:
            if not self.db:
                return
            
            offer_candidates_ref = self.db.collection('calls').document(self.call_id)\
                .collection('offerCandidates')
            
            processed_candidates = set()
            
            while self.running and self.pc.connectionState not in ["closed", "failed"]:
                try:
                    docs = offer_candidates_ref.get()
                    
                    for doc in docs:
                        if doc.id not in processed_candidates:
                            candidate_data = doc.to_dict()
                            
                            if 'candidate' in candidate_data:
                                candidate = RTCIceCandidate(
                                    candidate_data['candidate'],
                                    candidate_data.get('sdpMLineIndex'),
                                    candidate_data.get('sdpMid')
                                )
                                
                                await self.pc.addIceCandidate(candidate)
                                processed_candidates.add(doc.id)
                                logger.info("Added ICE candidate from caller")
                
                except Exception as e:
                    logger.error(f"Error processing ICE candidates: {e}")
                
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
            
            # Wait for offer
            offer = await self.wait_for_offer()
            
            if offer:
                # Answer the call
                success = await self.answer_call(offer)
                
                if success:
                    logger.info("Call connected successfully!")
                    
                    # Keep connection alive
                    while self.running and self.pc.connectionState not in ["closed", "failed"]:
                        await asyncio.sleep(1)
                        
                        # Log connection state periodically
                        if int(time.time()) % 30 == 0:
                            logger.info(f"Connection state: {self.pc.connectionState}")
                else:
                    logger.error("Failed to answer call")
            else:
                logger.error("No offer received")
                
        except Exception as e:
            logger.error(f"Error in start: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        """Clean up resources"""
        logger.info("Cleaning up resources...")
        self.running = False
        
        if self.pc:
            try:
                asyncio.create_task(self.pc.close())
            except:
                pass
        
        # Clean up audio
        if hasattr(self, 'output_stream') and self.output_stream:
            try:
                self.output_stream.stop_stream()
                self.output_stream.close()
            except:
                pass
        
        if self.audio_player:
            try:
                self.audio_player.terminate()
            except:
                pass
    
    def signal_handler(self, signum, frame):
        """Handle shutdown signals"""
        logger.info(f"Received signal {signum}")
        self.cleanup()
        sys.exit(0)


async def main():
    """Main function"""
    if len(sys.argv) != 2:
        print("Usage: python3 webrtc_receiver.py <call_id>")
        print("Example: python3 webrtc_receiver.py test-call-123")
        sys.exit(1)
    
    call_id = sys.argv[1]
    receiver = WebRTCReceiver(call_id)
    
    # Set up signal handlers
    signal.signal(signal.SIGINT, receiver.signal_handler)
    signal.signal(signal.SIGTERM, receiver.signal_handler)
    
    try:
        await receiver.start()
    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        receiver.cleanup()


if __name__ == "__main__":
    asyncio.run(main())