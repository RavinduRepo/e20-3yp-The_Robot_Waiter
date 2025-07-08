# --- Updated video_call_manager.py ---
import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription, RTCIceCandidate
from aiortc import VideoStreamTrack, AudioStreamTrack
import av
import numpy as np
from picamera2 import Picamera2
import sounddevice as sd
import signal
import sys

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

class MicrophoneAudioTrack(AudioStreamTrack):
    def __init__(self, device=None, samplerate=48000, channels=1):
        super().__init__()
        self.device = device
        self.samplerate = samplerate
        self.channels = channels
        self.stream = sd.InputStream(
            device=self.device,
            channels=self.channels,
            samplerate=self.samplerate,
            dtype='int16',
            blocksize=960,
        )
        self.stream.start()

    async def recv(self):
        frame, _ = self.stream.read(960)
        frame = np.squeeze(frame)
        if len(frame.shape) == 1:
            frame = np.stack([frame, frame], axis=0).T
        pts, time_base = await self.next_timestamp()
        audio_frame = av.AudioFrame.from_ndarray(frame, format="s16", layout="stereo")
        audio_frame.sample_rate = self.samplerate
        audio_frame.pts = pts
        audio_frame.time_base = time_base
        return audio_frame

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

    audio_track = MicrophoneAudioTrack(device=2)
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