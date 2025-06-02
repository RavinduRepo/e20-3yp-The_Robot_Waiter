#!/usr/bin/env python3
"""
Laptop WebRTC Audio Server
Handles built-in microphone/speakers and WebRTC connection with signaling server
"""

import asyncio
import json
import websockets
import pyaudio
import threading
import queue
import numpy as np
from aiortc import RTCPeerConnection, RTCSessionDescription, MediaStreamTrack
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AudioTrack(MediaStreamTrack):
    """Custom audio track for laptop microphone input"""
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
        """Start recording from laptop microphone"""
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

class SignalingServer:
    """WebSocket signaling server for WebRTC negotiation"""
    def __init__(self, host="localhost", port=8765):
        self.host = host
        self.port = port
        self.clients = set()
        
    async def register(self, websocket, path):
        """Register new client"""
        self.clients.add(websocket)
        logger.info(f"Client connected: {websocket.remote_address}")
        
        try:
            await websocket.wait_closed()
        finally:
            self.clients.remove(websocket)
            logger.info(f"Client disconnected: {websocket.remote_address}")
    
    async def broadcast(self, message, sender=None):
        """Broadcast message to all clients except sender"""
        if self.clients:
            await asyncio.gather(
                *[client.send(message) for client in self.clients if client != sender],
                return_exceptions=True
            )
    
    async def start_server(self):
        """Start the signaling server"""
        logger.info(f"Starting signaling server on {self.host}:{self.port}")
        return await websockets.serve(self.register, self.host, self.port)

class WebRTCAudioServer:
    def __init__(self):
        self.pc = RTCPeerConnection()
        self.audio_track = None
        self.signaling_server = SignalingServer()
        self.connected_clients = {}
        
        # Setup PyAudio for output
        self.p_output = pyaudio.PyAudio()
        self.output_stream = None
        self.default_mic_index = None
        self.default_speaker_index = None
        
    def find_default_audio_devices(self):
        """Find default audio devices"""
        p = pyaudio.PyAudio()
        
        print("Available audio devices:")
        for i in range(p.get_device_count()):
            info = p.get_device_info_by_index(i)
            print(f"Device {i}: {info['name']} - Max inputs: {info['maxInputChannels']}, Max outputs: {info['maxOutputChannels']}")
        
        # Get default devices
        try:
            default_input_info = p.get_default_input_device_info()
            self.default_mic_index = default_input_info['index']
            logger.info(f"Default microphone: {default_input_info['name']} (index: {self.default_mic_index})")
        except:
            logger.warning("No default input device found")
            
        try:
            default_output_info = p.get_default_output_device_info()
            self.default_speaker_index = default_output_info['index']
            logger.info(f"Default speaker: {default_output_info['name']} (index: {self.default_speaker_index})")
        except:
            logger.warning("No default output device found")
        
        p.terminate()
    
    def setup_audio_output(self):
        """Setup audio output stream for receiving audio"""
        try:
            self.output_stream = self.p_output.open(
                format=pyaudio.paInt16,
                channels=1,
                rate=48000,
                output=True,
                output_device_index=self.default_speaker_index,
                frames_per_buffer=1024
            )
            logger.info("Audio output setup completed")
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
    
    async def handle_websocket_client(self, websocket, path):
        """Handle WebSocket client connections"""
        client_id = f"{websocket.remote_address[0]}:{websocket.remote_address[1]}"
        self.connected_clients[client_id] = {
            'websocket': websocket,
            'pc': RTCPeerConnection()
        }
        
        logger.info(f"Client connected: {client_id}")
        
        try:
            async for message in websocket:
                data = json.loads(message)
                await self.handle_signaling_message(client_id, data)
                
        except websockets.exceptions.ConnectionClosed:
            logger.info(f"Client disconnected: {client_id}")
        finally:
            if client_id in self.connected_clients:
                del self.connected_clients[client_id]
    
    async def handle_signaling_message(self, client_id, data):
        """Handle signaling messages from clients"""
        client_info = self.connected_clients[client_id]
        websocket = client_info['websocket']
        pc = client_info['pc']
        
        if data["type"] == "offer":
            # Handle offer from Raspberry Pi
            offer_data = data["data"]
            offer = RTCSessionDescription(
                sdp=offer_data["sdp"],
                type=offer_data["type"]
            )
            
            # Set remote description
            await pc.setRemoteDescription(offer)
            
            # Find and setup default audio devices
            self.find_default_audio_devices()
            
            # Create audio track from laptop microphone
            audio_track = AudioTrack(device_index=self.default_mic_index)
            pc.addTrack(audio_track)
            
            # Handle incoming tracks
            @pc.on("track")
            def on_track(track):
                logger.info(f"Received track from {client_id}: {track.kind}")
                if track.kind == "audio":
                    asyncio.create_task(self.handle_incoming_audio(track))
            
            # Create answer
            answer = await pc.createAnswer()
            await pc.setLocalDescription(answer)
            
            # Send answer back to client
            answer_message = {
                "type": "answer",
                "data": {
                    "type": answer.type,
                    "sdp": answer.sdp
                }
            }
            
            await websocket.send(json.dumps(answer_message))
            logger.info(f"Sent answer to {client_id}")
    
    async def start_server(self):
        """Start the WebRTC server with signaling"""
        logger.info("Starting Laptop WebRTC Audio Server...")
        
        # Start WebSocket signaling server
        server = await websockets.serve(
            self.handle_websocket_client,
            "localhost",
            8765
        )
        
        logger.info("WebSocket signaling server started on ws://localhost:8765")
        logger.info("Waiting for Raspberry Pi to connect...")
        
        # Keep server running
        await server.wait_closed()
    
    def cleanup(self):
        """Cleanup resources"""
        if self.output_stream:
            self.output_stream.stop_stream()
            self.output_stream.close()
        if self.p_output:
            self.p_output.terminate()

async def main():
    server = WebRTCAudioServer()
    
    try:
        await server.start_server()
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        server.cleanup()

if __name__ == "__main__":
    # Install required packages:
    # pip install aiortc pyaudio websockets numpy
    
    print("=== Laptop WebRTC Audio Server ===")
    print("This server will:")
    print("1. Use your laptop's built-in microphone and speakers")
    print("2. Start a WebSocket signaling server on ws://localhost:8765")
    print("3. Wait for the Raspberry Pi client to connect")
    print("4. Establish WebRTC audio communication")
    print("\nPress Ctrl+C to stop the server")
    print("=" * 50)
    
    asyncio.run(main())