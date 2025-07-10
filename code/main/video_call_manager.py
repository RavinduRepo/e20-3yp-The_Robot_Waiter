# --- Updated video_call_manager.py ---
import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription, RTCIceCandidate
# from aiortc import VideoStreamTrack, AudioStreamTrack
from aiortc import VideoStreamTrack, MediaStreamTrack
import av
import numpy as np
from picamera2 import Picamera2
import sounddevice as sd
import signal
import sys
import fractions

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

    def __init__(self, device=None, samplerate=48000, channels=1): # Reverted samplerate to 48000
        super().__init__()  # Initialize base MediaStreamTrack
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = 960  # Reverted blocksize to 960 (20ms at 48kHz)
        self.sequence = 0
        
        # Increased maxsize further to absorb more significant delays.
        # 2000 blocks * (960/48000)s/block = ~40 seconds of buffer.
        self.audio_queue = asyncio.Queue(maxsize=2000) 

        # Define a noise threshold for simple noise gating (RMS value)
        # This value might need to be tuned based on your microphone and environment.
        self.NOISE_THRESHOLD_RMS = 500 

        # Define the callback function for the sounddevice stream
        def audio_callback(indata, frames, time, status):
            """
            This function is called by sounddevice in a separate thread
            whenever new audio data is available.
            """

            # Put the audio data into the asyncio queue.
            try:
                # Make a copy of indata as sounddevice reuses the buffer
                # Ensure the data type is consistent with what av expects (int16 for s16)
                self.audio_queue.put_nowait(np.copy(indata).astype(np.int16))
                # print(f"Audio queue size: {self.audio_queue.qsize()}") # For debugging
            except asyncio.QueueFull:
                # This indicates that the consumer (recv method) is not
                # processing data fast enough. This is the cause of 'input overflow'.
                print("Audio queue is full, dropping audio block (consumer too slow).")
            except Exception as e:
                print(f"Error in audio_callback: {e}")

        # Initialize the sounddevice input stream with the callback
        self.stream = sd.InputStream(
            device=self.device,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype='int16', # Explicitly ensure dtype is int16
            blocksize=self.blocksize,
            latency='low', # Keep latency low, but the larger blocksize might help
            callback=audio_callback # Pass the callback function here
        )
        self.stream.start() # Start the audio stream

    async def recv(self):
        try:
            # Wait asynchronously for the next audio block from the queue
            # This will block until data is available, but won't block the event loop.
            frame_data = await self.audio_queue.get()
            frame_data = np.squeeze(frame_data)

            # --- Simple Noise Gating ---
            # Calculate RMS (Root Mean Square) of the audio block
            # RMS = sqrt(mean(x^2))
            # np.float64 is used for calculation to prevent overflow with int16, then cast back
            rms = np.sqrt(np.mean(np.square(frame_data.astype(np.float64))))

            # If RMS is below the threshold, silence the block
            if rms < self.NOISE_THRESHOLD_RMS:
                frame_data = np.zeros_like(frame_data)
            # --- End Noise Gating ---

            # Reshape for AV frame based on channel configuration
            # This logic remains correct for av.AudioFrame.from_ndarray
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

            # Timestamping for the audio frame
            pts = self.sequence * self.blocksize
            time_base = fractions.Fraction(1, self.samplerate)
            self.sequence += 1

            audio_frame = av.AudioFrame.from_ndarray(frame_data, format="s16", layout=layout)
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

from scipy.io.wavfile import write as wav_write
from collections import deque

async def play_audio_track(track):
    print("[✓] Starting audio playback from browser")

    try:
        print("waiting for first frame")
        first_frame = await track.recv()
        sample_rate = first_frame.sample_rate
        if sample_rate is None or sample_rate < 1000:
            print("[!] Invalid or missing sample rate, defaulting to 48000")
            sample_rate = 32000
        else:
            print(f"[✓] Detected sample rate: {sample_rate}")

        layout_channels = len(first_frame.layout.channels)
        print(f"[✓] Incoming audio layout: {layout_channels} channel(s), {sample_rate} Hz")

        # Actually check the shape of the first frame
        first_pcm = first_frame.to_ndarray()
        print(f"→ First frame PCM shape: {first_pcm.shape}, dtype: {first_pcm.dtype}")

        # Real detected channels
        detected_channels = first_pcm.shape[0] if first_pcm.ndim == 2 else 1
        print(f"[→] Detected channels from PCM shape: {detected_channels}")

        stream = sd.OutputStream(
            samplerate=sample_rate,
            channels=detected_channels,
            dtype='int16',
            device=0
        )
        stream.start()
        print("stream started")

        recorded_frames = deque()
        total_samples = 0
        max_record_seconds = 5

        while True:
            frame = first_frame if total_samples == 0 else await track.recv()
            pcm = frame.to_ndarray()
            print(f"→ Raw pcm shape: {pcm.shape}, dtype: {pcm.dtype}")

            # Ensure shape is (samples, channels)
            if pcm.ndim == 1:
                pcm = np.expand_dims(pcm, axis=1)  # (samples, 1)
            elif pcm.shape[0] == detected_channels:
                pcm = pcm.T  # (samples, channels)

            print(f"[Debug] Prepared PCM shape for stream: {pcm.shape}")

            if pcm.shape[1] != stream.channels:
                print(f"[!] Mismatch: pcm has {pcm.shape[1]} channels, stream expects {stream.channels}")
                break

            stream.write(pcm)

            recorded_frames.append(pcm.copy())
            total_samples += pcm.shape[0]

            if total_samples >= max_record_seconds * sample_rate:
                all_data = np.concatenate(recorded_frames, axis=0)
                print("[✓] Saving audio with scipy to 'web_audio_recorded.wav'")
                wav_write("web_audio_recorded.wav", sample_rate, all_data)
                recorded_frames.clear()

    except Exception as e:
        print(f"[x] Error during audio playback: {e}")
    finally:
        try:
            stream.stop()
            stream.close()
        except:
            pass

# Global PC
pc = None

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
            asyncio.ensure_future(play_audio_track(track))


    video_track = PiCameraVideoTrack()
    pc.addTrack(video_track)

    device_index = get_usb_microphone("USB")  # or "PnP" or full name
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

    ## audio test
    # print("Remote SDP:", offer["sdp"])
    # print(pc.remoteDescription.sdp)
    # print(pc.localDescription.sdp)
    #erteeeeeeee

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # ########################
    # print("[Debug] Local SDP:")
    # print(pc.localDescription.sdp)
    # ########################

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
    await asyncio.Future()


def terminate_webrtc():
    global pc
    if pc:
        print("[x] Closing peer connection")
        pc.close()
        pc = None


if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python receiver.py CALL_ID")
        sys.exit(1)

    call_id = sys.argv[1]
    print(f"Starting WebRTC receiver for call ID: {call_id}")
    
    try:
        asyncio.run(main(call_id))
    except KeyboardInterrupt:
        print("Receiver stopped by user")
    except Exception as e:
        print(f"Receiver failed: {e}")