# --- Updated video_call_manager.py with optimized audio handling ---
import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription, RTCIceCandidate
from aiortc import VideoStreamTrack, MediaStreamTrack
import av
import numpy as np
from picamera2 import Picamera2
import sounddevice as sd
import signal
import sys
import fractions
import threading
from concurrent.futures import ThreadPoolExecutor
import time

# Build the ICE servers list
ice_servers = [
    RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
    RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
    RTCIceServer(
        urls=["turn:relay.metered.ca:80"],
        username="openai",
        credential="openai"
    ),
    RTCIceServer(
        urls=["turn:relay.metered.ca:443"],
        username="openai",
        credential="openai"
    ),
]

config = RTCConfiguration(iceServers=ice_servers)

class PiCameraVideoTrack(VideoStreamTrack):
    kind = "video"
    def __init__(self):
        super().__init__()
        self.picam2 = Picamera2()
        self.picam2.start()

    async def recv(self):
        pts, time_base = await self.next_timestamp()
        frame = self.picam2.capture_array()
        if frame.shape[2] == 4:
            frame = frame[:, :, :3]
        video_frame = av.VideoFrame.from_ndarray(frame, format='rgb24')
        video_frame.pts = pts
        video_frame.time_base = time_base
        return video_frame

class MicrophoneAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, device=None, samplerate=48000, channels=1):
        super().__init__()
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = 1000  # Reduced blocksize for lower latency (10ms at 48kHz)
        self.sequence = 0
        
        # Reduced buffer size to minimize latency
        self.audio_queue = asyncio.Queue(maxsize=2000)  # ~0.5 seconds of buffer

        # Noise threshold for simple noise gating
        self.NOISE_THRESHOLD_RMS = 600 

        def audio_callback(indata, frames, time, status):
            """Audio callback - runs in separate thread"""
            try:
                # Non-blocking put with immediate drop if queue is full
                self.audio_queue.put_nowait(np.copy(indata).astype(np.int16))
            except asyncio.QueueFull:
                # Drop old frames to maintain real-time performance
                try:
                    self.audio_queue.get_nowait()  # Remove oldest frame
                    self.audio_queue.put_nowait(np.copy(indata).astype(np.int16))
                except asyncio.QueueEmpty:
                    pass

        # Initialize the sounddevice input stream
        self.stream = sd.InputStream(
            device=self.device,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype='int16',
            blocksize=self.blocksize,
            latency='low',
            callback=audio_callback
        )
        self.stream.start()

    async def recv(self):
        try:
            # Use wait_for to prevent indefinite blocking
            frame_data = await asyncio.wait_for(self.audio_queue.get(), timeout=0.1)
            frame_data = np.squeeze(frame_data)

            # Simple noise gating
            rms = np.sqrt(np.mean(np.square(frame_data.astype(np.float64))))
            if rms < self.NOISE_THRESHOLD_RMS:
                frame_data = np.zeros_like(frame_data)

            # Reshape for AV frame
            if len(frame_data.shape) == 1:
                frame_data = np.expand_dims(frame_data, axis=0)
                layout = "mono"
            elif frame_data.shape[1] == 1:
                frame_data = frame_data.T
                layout = "mono"
            elif frame_data.shape[1] == 2:
                frame_data = frame_data.T
                layout = "stereo"
            else:
                raise ValueError(f"Unsupported audio shape: {frame_data.shape}")

            # Timestamping
            pts = self.sequence * self.blocksize
            time_base = fractions.Fraction(1, self.samplerate)
            self.sequence += 1

            audio_frame = av.AudioFrame.from_ndarray(frame_data, format="s16", layout=layout)
            audio_frame.sample_rate = self.samplerate
            audio_frame.pts = pts
            audio_frame.time_base = time_base

            return audio_frame

        except asyncio.TimeoutError:
            # Return silence if no audio available
            silence = np.zeros((1, self.blocksize), dtype=np.int16)
            pts = self.sequence * self.blocksize
            time_base = fractions.Fraction(1, self.samplerate)
            self.sequence += 1
            
            audio_frame = av.AudioFrame.from_ndarray(silence, format="s16", layout="mono")
            audio_frame.sample_rate = self.samplerate
            audio_frame.pts = pts
            audio_frame.time_base = time_base
            return audio_frame
        except Exception as e:
            print(f"[x] Error in MicrophoneAudioTrack.recv(): {e}")
            return None

def get_usb_microphone(name_contains="USB"):
    """Finds the first input device with a name containing the given substring."""
    devices = sd.query_devices()
    for idx, dev in enumerate(devices):
        if dev['max_input_channels'] > 0 and name_contains.lower() in dev['name'].lower():
            print(f"[✓] Selected input device: {dev['name']} (index {idx})")
            return idx
    raise RuntimeError(f"No USB microphone found matching '{name_contains}'")

class AudioPlaybackHandler:
    """Handles audio playback in a separate thread to avoid blocking the main event loop"""
    
    def __init__(self):
        self.executor = ThreadPoolExecutor(max_workers=1, thread_name_prefix="AudioPlayback")
        self.audio_queue = asyncio.Queue(maxsize=10)  # Small buffer for real-time playback
        self.stream = None
        self.running = False
        
    def start_playback_thread(self, sample_rate, channels):
        """Start the audio playback thread"""
        def playback_worker():
            """Worker function that runs in a separate thread"""
            try:
                # Create output stream in the worker thread
                stream = sd.OutputStream(
                    samplerate=sample_rate,
                    channels=channels,
                    dtype='int16',
                    blocksize=480,  # Small blocksize for low latency
                    latency='low',  # Use low latency mode
                )
                stream.start()
                self.stream = stream
                self.running = True
                
                print(f"[✓] Audio playback thread started: {sample_rate}Hz, {channels} channels")
                
                # Process audio frames
                while self.running:
                    try:
                        # Get audio data from the thread-safe queue
                        # This will block until data is available or timeout
                        future = asyncio.run_coroutine_threadsafe(
                            asyncio.wait_for(self.audio_queue.get(), timeout=0.1),
                            asyncio.get_event_loop()
                        )
                        pcm_data = future.result(timeout=0.2)
                        
                        if pcm_data is not None:
                            stream.write(pcm_data)
                            
                    except Exception as e:
                        if self.running:  # Only log if we're still supposed to be running
                            print(f"[x] Playback worker error: {e}")
                        continue
                        
            except Exception as e:
                print(f"[x] Audio playback thread error: {e}")
            finally:
                if self.stream:
                    self.stream.stop()
                    self.stream.close()
                    self.stream = None
                self.running = False
                print("[✓] Audio playback thread stopped")
        
        # Start the worker thread
        self.executor.submit(playback_worker)
    
    async def add_audio_frame(self, pcm_data):
        """Add audio frame to playback queue (non-blocking)"""
        try:
            self.audio_queue.put_nowait(pcm_data)
        except asyncio.QueueFull:
            # Drop frames if queue is full to maintain real-time performance
            try:
                self.audio_queue.get_nowait()  # Remove oldest
                self.audio_queue.put_nowait(pcm_data)  # Add new
            except asyncio.QueueEmpty:
                pass
    
    def stop(self):
        """Stop the audio playback"""
        self.running = False
        self.executor.shutdown(wait=True)

# Global variables
pc = None
audio_handler = None

async def play_audio_track(track):
    """Optimized audio playback using separate thread"""
    global audio_handler
    
    print("[✓] Starting audio playback from browser")
    
    try:
        # Get first frame to determine audio parameters
        first_frame = await asyncio.wait_for(track.recv(), timeout=5.0)
        
        sample_rate = first_frame.sample_rate or 48000
        layout_channels = len(first_frame.layout.channels)
        
        print(f"[✓] Audio format: {layout_channels} channels, {sample_rate} Hz")
        
        # Initialize audio handler
        audio_handler = AudioPlaybackHandler()
        
        # Process first frame
        pcm = first_frame.to_ndarray()
        if pcm.dtype != np.int16:
            pcm = pcm.astype(np.int16)
            
        # Determine actual channels from PCM shape
        if pcm.ndim == 1:
            detected_channels = 1
        else:
            detected_channels = pcm.shape[0]
            
        print(f"[✓] Detected channels: {detected_channels}")
        
        # Start playback thread
        audio_handler.start_playback_thread(sample_rate, detected_channels)
        
        # Add first frame
        if pcm.ndim == 1:
            pcm = pcm[:, np.newaxis]
        elif pcm.shape[0] < pcm.shape[1]:
            pcm = pcm.T
            
        await audio_handler.add_audio_frame(pcm)
        
        # Process remaining frames
        while True:
            try:
                # Use timeout to prevent blocking
                frame = await asyncio.wait_for(track.recv(), timeout=0.1)
                
                pcm = frame.to_ndarray()
                if pcm.dtype != np.int16:
                    pcm = pcm.astype(np.int16)
                
                # Adjust PCM shape
                if pcm.ndim == 1:
                    pcm = pcm[:, np.newaxis]
                elif pcm.shape[0] < pcm.shape[1]:
                    pcm = pcm.T
                
                # Add to playback queue (non-blocking)
                await audio_handler.add_audio_frame(pcm)
                
            except asyncio.TimeoutError:
                # No audio frame available, continue loop
                continue
            except Exception as e:
                print(f"[x] Error processing audio frame: {e}")
                break
                
    except Exception as e:
        print(f"[x] Error in audio playback: {e}")
    finally:
        if audio_handler:
            audio_handler.stop()

async def main(call_id):
    global pc

    if not firebase_admin._apps:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    loop = asyncio.get_running_loop()
    pc = RTCPeerConnection(configuration=config)

    @pc.on("track")
    def on_track(track):
        print(f"[✓] Received track: {track.kind}")
        
        if track.kind == "audio":
            # Create task but don't await it to avoid blocking
            asyncio.create_task(play_audio_track(track))

    video_track = PiCameraVideoTrack()
    pc.addTrack(video_track)

    device_index = get_usb_microphone("USB")
    audio_track = MicrophoneAudioTrack(device=device_index)
    pc.addTrack(audio_track)

    call_ref = db.collection('calls').document(call_id)
    offer_candidates_ref = call_ref.collection('offerCandidates')
    answer_candidates_ref = call_ref.collection('answerCandidates')

    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            await answer_candidates_ref.add({
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex
            })

    call_doc = call_ref.get()
    if not call_doc.exists:
        print(f"No call found with ID {call_id}")
        return
    offer = call_doc.to_dict().get("offer")
    if not offer:
        print(f"No offer in call document {call_id}")
        return

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    call_ref.update({"answer": {
        "type": pc.localDescription.type,
        "sdp": pc.localDescription.sdp
    }})

    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                candidate_dict = {
                    "candidate": data["candidate"],
                    "sdpMid": data["sdpMid"],
                    "sdpMLineIndex": data["sdpMLineIndex"]
                }
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(candidate_dict), loop)

    offer_candidates_ref.on_snapshot(on_snapshot)

    print("[✓] WebRTC connection established")
    
    # Keep the connection alive
    try:
        await asyncio.Future()
    except asyncio.CancelledError:
        pass

def terminate_webrtc():
    global pc, audio_handler
    if pc:
        print("[x] Closing peer connection")
        pc.close()
        pc = None
    if audio_handler:
        audio_handler.stop()
        audio_handler = None

if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python receiver.py CALL_ID")
        sys.exit(1)

    call_id = sys.argv[1]
    print(f"Starting WebRTC receiver for call ID: {call_id}")
    
    try:
        asyncio.run(main(call_id))
    except KeyboardInterrupt:
        print("Receiver stopped by user")
        terminate_webrtc()
    except Exception as e:
        print(f"Receiver failed: {e}")
        terminate_webrtc()