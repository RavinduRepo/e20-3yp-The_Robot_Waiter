import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import (
    RTCPeerConnection,
    RTCConfiguration,
    RTCIceServer,
    RTCSessionDescription,
    VideoStreamTrack,
    MediaStreamTrack
)
import av
import numpy as np
import time
from picamera2 import Picamera2
import sounddevice as sd

# === ICE servers (STUN + TURN) ===
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

# === Video Track (Pi Camera) ===
class PiCameraVideoTrack(VideoStreamTrack):
    def __init__(self):
        super().__init__()
        self.picam2 = Picamera2()
        self.picam2.configure(
            self.picam2.create_video_configuration(main={"format": 'RGB888', "size": (640, 480)})
        )
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

# === Audio Track (USB Mic) ===
class MicrophoneAudioTrack(MediaStreamTrack):
    kind = "audio"

    def __init__(self, samplerate=48000, channels=1, device_index=2):
        super().__init__()
        self.samplerate = samplerate
        self.channels = channels
        self.blocksize = 960  # 20ms @ 48kHz
        self.stream = sd.InputStream(
            samplerate=samplerate,
            blocksize=self.blocksize,
            channels=channels,
            dtype='int16',
            latency='low',
            device=device_index
        )
        self.stream.start()

    async def recv(self):
        data, _ = self.stream.read(self.blocksize)
        frame = av.AudioFrame.from_ndarray(data, format='s16', layout='mono')
        frame.sample_rate = self.samplerate
        frame.pts = int(time.time() * self.samplerate)
        frame.time_base = av.Rational(1, self.samplerate)
        return frame

# === Main WebRTC logic ===
async def main(call_id):
    # Init Firebase
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()
    loop = asyncio.get_running_loop()

    # WebRTC connection
    pc = RTCPeerConnection(configuration=config)

    # Add media tracks
    video_track = PiCameraVideoTrack()
    audio_track = MicrophoneAudioTrack(device_index=2)
    pc.addTrack(video_track)
    pc.addTrack(audio_track)

    # Firestore refs
    call_ref = db.collection("calls").document(call_id)
    offer_candidates_ref = call_ref.collection("offerCandidates")
    answer_candidates_ref = call_ref.collection("answerCandidates")

    # Send ICE candidates
    @pc.on("icecandidate")
    async def on_icecandidate(candidate):
        if candidate:
            await answer_candidates_ref.add({
                "candidate": candidate.candidate,
                "sdpMid": candidate.sdpMid,
                "sdpMLineIndex": candidate.sdpMLineIndex
            })

    # Get offer from Firestore
    call_doc = call_ref.get()
    if not call_doc.exists:
        print(f"No call found with ID {call_id}")
        return
    offer = call_doc.to_dict().get("offer")
    if not offer:
        print(f"No offer present in call document")
        return

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))

    # Create and send answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await call_ref.update({
        "answer": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })

    # Listen for remote ICE candidates
    def on_snapshot(snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(data), loop)

    offer_candidates_ref.on_snapshot(on_snapshot)

    print("✅ Connection established — streaming audio & video to caller...")
    await asyncio.Future()  # Keep running forever

if __name__ == "__main__":
    call_id = input("Enter Call ID to answer: ")
    asyncio.run(main(call_id))
