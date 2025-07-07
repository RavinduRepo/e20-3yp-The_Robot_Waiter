import asyncio
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCConfiguration, RTCIceServer, RTCSessionDescription, MediaStreamTrack
from aiortc.mediastreams import VideoFrame
from picamera2 import Picamera2
import numpy as np

# ICE servers
ice_servers = [
    RTCIceServer(urls=["stun:stun.l.google.com:19302"]),
    RTCIceServer(urls=["stun:stun1.l.google.com:19302"]),
    RTCIceServer(urls=["turn:relay.metered.ca:80"], username="openai", credential="openai"),
    RTCIceServer(urls=["turn:relay.metered.ca:443"], username="openai", credential="openai")
]
config = RTCConfiguration(iceServers=ice_servers)

# Video track
class CameraVideoTrack(MediaStreamTrack):
    kind = "video"
    def __init__(self):
        super().__init__()
        self.picam2 = Picamera2()
        self.picam2.configure(self.picam2.create_video_configuration(main={"format": 'RGB888', "size": (640, 480)}))
        self.picam2.start()

    async def recv(self):
        frame = await asyncio.get_event_loop().run_in_executor(None, self.picam2.capture_array)
        video_frame = VideoFrame.from_ndarray(frame, format="rgb24")
        video_frame.pts, video_frame.time_base = self.next_timestamp()
        return video_frame

async def main(call_id):
    # Firebase init
    if not firebase_admin._apps:
        cred = credentials.Certificate("serviceAccountKey.json")
        firebase_admin.initialize_app(cred)
    db = firestore.client()

    pc = RTCPeerConnection(configuration=config)
    video_track = CameraVideoTrack()
    pc.addTrack(video_track)

    # Firestore signaling
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
    call_data = call_doc.to_dict()
    offer = call_data.get("offer")
    await pc.setRemoteDescription(RTCSessionDescription(sdp=offer["sdp"], type=offer["type"]))

    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)
    await call_ref.update({"answer": {"type": pc.localDescription.type, "sdp": pc.localDescription.sdp}})

    def on_snapshot(snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                data = change.document.to_dict()
                asyncio.ensure_future(pc.addIceCandidate(data))

    offer_candidates_ref.on_snapshot(on_snapshot)

    print("Streaming video to caller. Press Ctrl+C to stop.")
    await asyncio.Future()

if __name__ == "__main__":
    call_id = input("Enter Call ID to answer: ")
    asyncio.run(main(call_id))
