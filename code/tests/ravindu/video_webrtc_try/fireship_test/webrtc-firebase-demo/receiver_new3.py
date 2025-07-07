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

# ICE server configuration
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
        try:
            self.stream = sd.InputStream(
                device=self.device,
                channels=self.channels,
                samplerate=self.samplerate,
                dtype='int16',
                blocksize=960,  # 20ms audio
            )
            self.stream.start()
        except Exception as e:
            print(f"[Audio ERROR] Could not start microphone stream: {e}")
            raise

    async def recv(self):
        frame, _ = self.stream.read(960)
        frame = np.squeeze(frame)
        if frame.ndim == 0:
            frame = np.expand_dims(frame, axis=0)

        # Debug output
        print(f"[AUDIO] min={frame.min()} max={frame.max()} shape={frame.shape}")

        pts, time_base = await self.next_timestamp()

        audio_frame = av.AudioFrame.from_ndarray(frame, format="s16", layout="mono")
        audio_frame.sample_rate = self.samplerate
        audio_frame.pts = pts
        audio_frame.time_base = time_base
        return audio_frame

async def main(call_id):
    # Firebase init
    if not firebase_admin._apps:
        cred = credentials.Certificate('serviceAccountKey.json')
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    loop = asyncio.get_running_loop()
    pc = RTCPeerConnection(configuration=config)

    # Add video and audio tracks
    pc.addTrack(PiCameraVideoTrack())
    pc.addTrack(MicrophoneAudioTrack(device=2))

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
            print("[ICE] Sent candidate")
        else:
            print("[ICE] Gathering complete")

    # Load offer from Firestore
    call_doc = call_ref.get()
    if not call_doc.exists:
        print(f"[ERROR] No call with ID {call_id}")
        return
    call_data = call_doc.to_dict()
    offer = call_data.get("offer")
    if not offer:
        print(f"[ERROR] No offer found in call {call_id}")
        return

    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send answer to Firestore
    await call_ref.update({
        "answer": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })

    def on_snapshot(col_snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                candidate = RTCIceCandidate(
                    candidate=data["candidate"],
                    sdpMid=data["sdpMid"],
                    sdpMLineIndex=data["sdpMLineIndex"]
                )
                asyncio.run_coroutine_threadsafe(pc.addIceCandidate(candidate), loop)
                print("[ICE] Received remote candidate")

    offer_candidates_ref.on_snapshot(on_snapshot)

    print("[INFO] Connection initialized and waiting for ICE to complete...")
    await asyncio.Future()

if __name__ == "__main__":
    call_id = input("Enter Call ID to answer: ")
    asyncio.run(main(call_id))
