#!/usr/bin/env python3
"""
Streamlined WebRTC Receiver for Raspberry Pi
Receives audio from caller and sends video/audio to caller
"""

import asyncio
import logging
import signal
import sys
from typing import Optional
import numpy as np
import cv2
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, VideoStreamTrack, AudioStreamTrack, VideoFrame, AudioFrame

# Optional audio import
try:
    import pyaudio
    AUDIO_AVAILABLE = True
except ImportError:
    AUDIO_AVAILABLE = False

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class CameraVideoTrack(VideoStreamTrack):
    def __init__(self, camera):
        super().__init__()
        self.camera = camera
        self.frame_count = 0
    
    async def recv(self):
        ret, frame = self.camera.read()
        if ret and frame is not None:
            self.frame_count += 1
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            av_frame = VideoFrame.from_ndarray(frame, format="rgb24")
            av_frame.pts = self.frame_count
            av_frame.time_base = 1/30
            return av_frame
        return None

class MicrophoneAudioTrack(AudioStreamTrack):
    def __init__(self):
        super().__init__()
        if not AUDIO_AVAILABLE:
            raise Exception("PyAudio not available")
        
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
        try:
            data = self.stream.read(1024, exception_on_overflow=False)
            self.frame_count += 1
            audio_array = np.frombuffer(data, dtype=np.int16)
            frame = AudioFrame(format="s16", layout="mono", samples=len(audio_array))
            frame.planes[0].update(audio_array.tobytes())
            frame.pts = self.frame_count
            frame.sample_rate = 44100
            return frame
        except Exception as e:
            logger.warning(f"Audio capture error: {e}")
            return None

class WebRTCReceiver:
    def __init__(self, call_id: str):
        self.call_id = call_id
        self.pc = None
        self.running = False
        self.camera = None
        self.audio_stream = None
        self.audio = None
        
        # WebRTC configuration
        self.rtc_config = {
            "iceServers": [
                {"urls": "stun:stun.l.google.com:19302"},
                {"urls": "turn:relay.metered.ca:80", "username": "openai", "credential": "openai"}
            ]
        }
        
        # Initialize Firebase
        self.init_firebase()
        
        # Setup audio for playback
        if AUDIO_AVAILABLE:
            self.setup_audio_playback()
    
    def init_firebase(self):
        try:
            cred = credentials.Certificate("serviceAccountKey.json")
            firebase_admin.initialize_app(cred)
            self.db = firestore.client()
            logger.info("Firebase initialized")
        except Exception as e:
            logger.error(f"Firebase init failed: {e}")
            self.db = None
    
    def setup_camera(self):
        for i in [0, 1, 2]:
            try:
                cap = cv2.VideoCapture(i)
                if cap.isOpened():
                    ret, frame = cap.read()
                    if ret and frame is not None:
                        cap.set(cv2.CAP_PROP_FRAME_WIDTH, 640)
                        cap.set(cv2.CAP_PROP_FRAME_HEIGHT, 480)
                        cap.set(cv2.CAP_PROP_FPS, 30)
                        self.camera = cap
                        logger.info(f"Camera ready on index {i}")
                        return True
                cap.release()
            except Exception as e:
                logger.warning(f"Camera {i} failed: {e}")
        return False
    
    def setup_audio_playback(self):
        try:
            self.audio = pyaudio.PyAudio()
            self.audio_stream = self.audio.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=44100,
                output=True,
                frames_per_buffer=1024
            )
            return True
        except Exception as e:
            logger.warning(f"Audio playback setup failed: {e}")
            return False
    
    async def create_peer_connection(self):
        self.pc = RTCPeerConnection(self.rtc_config)
        
        # Add video track
        if self.setup_camera():
            self.pc.addTrack(CameraVideoTrack(self.camera))
            logger.info("Video track added")
        
        # Add audio track
        if AUDIO_AVAILABLE:
            try:
                self.pc.addTrack(MicrophoneAudioTrack())
                logger.info("Audio track added")
            except Exception as e:
                logger.warning(f"Audio track failed: {e}")
        
        # Handle incoming tracks
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Received {track.kind} track")
            if track.kind == "audio" and self.audio_stream:
                asyncio.create_task(self.play_audio_track(track))
        
        # Handle ICE candidates
        @self.pc.on("icecandidate")
        def on_icecandidate(candidate):
            if candidate:
                asyncio.create_task(self.send_ice_candidate(candidate))
        
        # Handle connection state
        @self.pc.on("connectionstatechange")
        def on_connectionstatechange():
            logger.info(f"Connection state: {self.pc.connectionState}")
    
    async def play_audio_track(self, track):
        try:
            while self.running and self.audio_stream:
                frame = await track.recv()
                if hasattr(frame, 'to_ndarray'):
                    audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                    self.audio_stream.write(audio_data)
        except Exception as e:
            logger.warning(f"Audio playback error: {e}")
    
    async def send_ice_candidate(self, candidate):
        try:
            if self.db:
                candidate_data = {
                    "candidate": candidate.candidate,
                    "sdpMLineIndex": candidate.sdpMLineIndex,
                    "sdpMid": candidate.sdpMid
                }
                self.db.collection('calls').document(self.call_id).collection('answerCandidates').add(candidate_data)
        except Exception as e:
            logger.warning(f"ICE candidate send failed: {e}")
    
    async def handle_call(self):
        if not self.db:
            logger.error("No Firebase connection")
            return False
        
        call_ref = self.db.collection('calls').document(self.call_id)
        
        # Wait for offer
        while self.running:
            try:
                doc = call_ref.get()
                if doc.exists and doc.to_dict().get('offer'):
                    break
                await asyncio.sleep(1)
            except Exception as e:
                logger.warning(f"Offer check error: {e}")
                await asyncio.sleep(1)
        
        if not self.running:
            return False
        
        # Process offer
        try:
            offer = doc.to_dict()['offer']
            await self.pc.setRemoteDescription(RTCSessionDescription(offer['sdp'], offer['type']))
            
            # Create and send answer
            answer = await self.pc.createAnswer()
            await self.pc.setLocalDescription(answer)
            
            call_ref.update({"answer": {"sdp": answer.sdp, "type": answer.type}})
            logger.info("Call answered")
            
            # Listen for ICE candidates
            asyncio.create_task(self.listen_ice_candidates())
            return True
            
        except Exception as e:
            logger.error(f"Call handling error: {e}")
            return False
    
    async def listen_ice_candidates(self):
        try:
            candidates_ref = self.db.collection('calls').document(self.call_id).collection('offerCandidates')
            processed = set()
            
            while self.running and self.pc.connectionState not in ["closed"]:
                try:
                    for doc in candidates_ref.get():
                        if doc.id not in processed:
                            data = doc.to_dict()
                            candidate = RTCIceCandidate(data['candidate'], data.get('sdpMLineIndex'), data.get('sdpMid'))
                            await self.pc.addIceCandidate(candidate)
                            processed.add(doc.id)
                except Exception as e:
                    logger.warning(f"ICE candidate error: {e}")
                await asyncio.sleep(1)
        except Exception as e:
            logger.warning(f"ICE listening error: {e}")
    
    async def start(self):
        try:
            self.running = True
            logger.info(f"Starting receiver for call: {self.call_id}")
            
            await self.create_peer_connection()
            
            if await self.handle_call():
                logger.info("Call connected")
                while self.running and self.pc.connectionState != "closed":
                    await asyncio.sleep(1)
            else:
                logger.error("Call connection failed")
                
        except Exception as e:
            logger.error(f"Start error: {e}")
        finally:
            self.cleanup()
    
    def cleanup(self):
        logger.info("Cleaning up...")
        self.running = False
        
        if self.pc:
            try:
                asyncio.create_task(self.pc.close())
            except:
                pass
        
        if self.camera:
            self.camera.release()
        
        if self.audio_stream:
            try:
                self.audio_stream.stop_stream()
                self.audio_stream.close()
            except:
                pass
        
        if self.audio:
            try:
                self.audio.terminate()
            except:
                pass
    
    def signal_handler(self, signum, frame):
        logger.info("Shutdown signal received")
        self.cleanup()
        sys.exit(0)

async def main():
    if len(sys.argv) != 2:
        print("Usage: python3 webrtc_receiver.py <call_id>")
        sys.exit(1)
    
    call_id = sys.argv[1]
    receiver = WebRTCReceiver(call_id)
    
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