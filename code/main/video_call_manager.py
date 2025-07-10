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

    def __init__(self, device=None, samplerate=48000, channels=1):
        super().__init__()  # Initialize base MediaStreamTrack
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = 960  # 960 samples = 20ms @ 48kHz
        self.sequence = 0

        # Initialize the sounddevice input stream
        self.stream = sd.InputStream(
            device=self.device,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype='int16',
            blocksize=self.blocksize,
            latency='low',
        )
        self.stream.start() # Start the audio stream

    async def recv(self):
        try:
            # Get the current running event loop. This is safe to do inside recv
            # as recv is called within the asyncio event loop.
            loop = asyncio.get_running_loop()

            # Read a block of audio samples (20ms) using run_in_executor.
            # This offloads the blocking sounddevice.read() call to a separate
            # thread, preventing it from blocking the main asyncio event loop.
            # This allows the event loop to remain responsive and process
            # WebRTC signaling and packet sending efficiently, preventing
            # audio buffering and bursting.
            frame, _ = await loop.run_in_executor(
                None,  # Use the default ThreadPoolExecutor
                self.stream.read,
                self.blocksize
            )
            frame = np.squeeze(frame) # Remove single-dimensional entries from the shape of an array

            # Reshape for AV frame based on channel configuration
            if len(frame.shape) == 1:
                # Mono shape (960,) → (1, 960) for av.AudioFrame
                frame = np.expand_dims(frame, axis=0)
                layout = "mono"
            elif frame.shape[1] == 1:
                # If shape is (N, 1), transpose to (1, N) for mono
                frame = frame.T
                layout = "mono"
            elif frame.shape[1] == 2:
                # Stereo shape (N, 2), transpose to (2, N) for stereo
                frame = frame.T
                layout = "stereo"
            else:
                raise ValueError(f"Unsupported audio shape: {frame.shape}")

            # Timestamping for the audio frame
            # pts (presentation timestamp) is the cumulative number of samples
            pts = self.sequence * self.blocksize
            # time_base defines the unit of pts (1/samplerate seconds per sample)
            time_base = fractions.Fraction(1, self.samplerate)
            self.sequence += 1 # Increment sequence for the next frame

            # Create an av.AudioFrame from the numpy array
            audio_frame = av.AudioFrame.from_ndarray(frame, format="s16", layout=layout)
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