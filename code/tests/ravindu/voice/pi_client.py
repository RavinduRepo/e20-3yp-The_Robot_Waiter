#!/usr/bin/env python3
"""
Raspberry Pi WebRTC Audio Client
Handles USB headset audio input/output and WebRTC connection
"""

import asyncio
import json
import websockets
import pyaudio
import threading
import queue
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
from aiortc.contrib.media import MediaRecorder, MediaPlayer
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioTrack(MediaStreamTrack):
    """Custom audio track for microphone input"""
    kind = "audio"
    
    def __init__(self, device_index=None):
        super().__init__()
        self.device_index = device_index
        self.audio_queue = queue.Queue()
        self.p = pyaudio.PyAudio()
        self.stream = None
        self.running = False
        
        # Audio parameters
        self.sample_rate = 48000
        self.channels = 1
        self.chunk_size = 1024
        
    def start_recording(self):
        """Start recording from USB microphone"""
        try:
            self.stream = self.p.open(
                format=pyaudio.paInt16,
                channels=self.channels,
                rate=self.sample_rate,
                input=True,
                input_device_index=self.device_index,
                frames_per_buffer=self.chunk_size,
                stream_callback=self._audio_callback
            )
            self.running = True
            self.stream.start_stream()
            logger.info(f"Started recording from device index: {self.device_index}")
        except Exception as e:
            logger.error(f"Error starting recording: {e}")
    
    def _audio_callback(self, in_data, frame_count, time_info, status):
        """PyAudio callback for capturing audio"""
        if self.running:
            self.audio_queue.put(in_data)
        return (None, pyaudio.paContinue)
    
    async def recv(self):
        """Receive audio frame for WebRTC"""
        if not self.running:
            self.start_recording()
        
        try:
            # Get audio data from queue (non-blocking)
            audio_data = self.audio_queue.get_nowait()
            # Convert to numpy array and create frame
            audio_array = np.frombuffer(audio_data, dtype=np.int16)
            return audio_array
        except queue.Empty:
            # Return silence if no audio available
            return np.zeros(self.chunk_size, dtype=np.int16)
    
    def stop(self):
        """Stop recording"""
        self.running = False
        if self.stream:
            self.stream.stop_stream()
            self.stream.close()
        self.p.terminate()

class WebRTCAudioClient:
    def __init__(self, websocket_url="ws://localhost:8765"):
        self.websocket_url = websocket_url
        self.pc = RTCPeerConnection()
        self.websocket = None
        self.audio_track = None
        self.audio_output = None
        self.usb_mic_index = None
        self.usb_speaker_index = None
        
        # Setup PyAudio for output
        self.p_output = pyaudio.PyAudio()
        self.output_stream = None
        
    def find_usb_audio_devices(self):
        """Find USB audio devices (microphone and speaker)"""
        p = pyaudio.PyAudio()
        
        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"Device {i}: {info['name']} - Max inputs: {info['maxInputChannels']}, Max outputs: {info['maxOutputChannels']}")
            
            # Look for USB devices (usually contain "USB" in the name)
            if "USB" in info['name'].upper() or "HEADSET" in info['name'].upper():
                if info['maxInputChannels'] > 0 and self.usb_mic_index is None:
                    self.usb_mic_index = i
                    logger.info(f"Found USB microphone: {info['name']} (index: {i})")
                if info['maxOutputChannels'] > 0 and self.usb_speaker_index is None:
                    self.usb_speaker_index = i
                    logger.info(f"Found USB speaker: {info['name']} (index: {i})")
        
        p.terminate()
        
        if self.usb_mic_index is None:
            logger.warning("No USB microphone found, using default input device")
            self.usb_mic_index = None
        if self.usb_speaker_index is None:
            logger.warning("No USB speaker found, using default output device")
            self.usb_speaker_index = None
    
    def setup_audio_output(self):
        """Setup audio output stream for receiving audio"""
        try:
            self.output_stream = self.p_output.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=48000,
                output=True,
                output_device_index=self.usb_speaker_index,
                frames_per_buffer=1024
            )
            logger.info(f"Audio output setup completed for device: {self.usb_speaker_index}")
        except Exception as e:
            logger.error(f"Error setting up audio output: {e}")
    
    async def handle_incoming_audio(self, track):
        """Handle incoming audio from remote peer"""
        self.setup_audio_output()
        
        try:
            async for frame in track:
                if self.output_stream and not self.output_stream.is_stopped():
                    # Convert frame to bytes and play
                    audio_data = frame.to_ndarray().astype(np.int16).tobytes()
                    self.output_stream.write(audio_data)
        except Exception as e:
            logger.error(f"Error handling incoming audio: {e}")
    
    async def create_offer(self):
        """Create WebRTC offer"""
        # Find and setup USB audio devices
        self.find_usb_audio_devices()
        
        # Create audio track from USB microphone
        self.audio_track = AudioTrack(device_index=self.usb_mic_index)
        self.pc.addTrack(self.audio_track)
        
        # Handle incoming tracks
        @self.pc.on("track")
        def on_track(track):
            logger.info(f"Received track: {track.kind}")
            if track.kind == "audio":
                asyncio.create_task(self.handle_incoming_audio(track))
        
        # Create offer
        offer = await self.pc.createOffer()
        await self.pc.setLocalDescription(offer)
        
        return {
            "type": offer.type,
            "sdp": offer.sdp
        }
    
    async def handle_answer(self, answer_data):
        """Handle WebRTC answer"""
        answer = RTCSessionDescription(
            sdp=answer_data["sdp"],
            type=answer_data["type"]
        )
        await self.pc.setRemoteDescription(answer)
    
    async def connect_websocket(self):
        """Connect to WebSocket signaling server"""
        try:
            self.websocket = await websockets.connect(self.websocket_url)
            logger.info(f"Connected to WebSocket server: {self.websocket_url}")
            
            # Create and send offer
            offer = await self.create_offer()
            await self.websocket.send(json.dumps({
                "type": "offer",
                "data": offer
            }))
            
            # Listen for messages
            async for message in self.websocket:
                data = json.loads(message)
                
                if data["type"] == "answer":
                    await self.handle_answer(data["data"])
                    logger.info("WebRTC connection established!")
                elif data["type"] == "ice-candidate":
                    # Handle ICE candidates if needed
                    pass
                    
        except Exception as e:
            logger.error(f"WebSocket connection error: {e}")
    
    async def start(self):
        """Start the WebRTC client"""
        logger.info("Starting Raspberry Pi WebRTC Audio Client...")
        await self.connect_websocket()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.audio_track:
            self.audio_track.stop()
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        if self.p_output:
            self.p_output.terminate()

async def main():
    client = WebRTCAudioClient()
    
    try:
        await client.start()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        client.cleanup()

if __name__ == "__main__":
    # Install required packages:
    # pip install aiortc pyaudio websockets numpy
    
    asyncio.run(main())