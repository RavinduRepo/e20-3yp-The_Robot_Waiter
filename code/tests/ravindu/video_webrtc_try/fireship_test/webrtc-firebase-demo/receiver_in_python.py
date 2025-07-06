import asyncio
import json
import firebase_admin
from firebase_admin import credentials, firestore
from aiortc import RTCPeerConnection, RTCSessionDescription, RTCIceCandidate, MediaStreamTrack
from aiortc.contrib.media import MediaPlayer
import pyaudio

# 🔑 Firebase setup
firebase_config_path = 'serviceAccountKey.json'  # Download from Firebase console
cred = credentials.Certificate(firebase_config_path)
firebase_admin.initialize_app(cred)
db = firestore.client()

# ICE servers
ICE_SERVERS = [
    {"urls": "stun:stun.l.google.com:19302"},
    {"urls": "stun:stun1.l.google.com:19302"},
    {
        "urls": "turn:relay.metered.ca:80",
        "username": "openai",
        "credential": "openai"
    },
    {
        "urls": "turn:relay.metered.ca:443",
        "username": "openai",
        "credential": "openai"
    }
]

# Play received audio using PyAudio
class AudioReceiver(MediaStreamTrack):
    kind = "audio"

    def __init__(self, track):
        super().__init__()
        self.track = track
        self.p = pyaudio.PyAudio()
        self.stream = self.p.open(
            format=pyaudio.paInt16,
            channels=1,
            rate=48000,
            output=True
        )

    async def recv(self):
        frame = await self.track.recv()
        self.stream.write(frame.planes[0].to_bytes())
        return frame

async def run_receiver(call_id):
    from aiortc import RTCConfiguration

    pc = RTCPeerConnection(configuration=RTCConfiguration(iceServers=ICE_SERVERS))


    call_ref = db.collection("calls").document(call_id)
    answer_candidates = call_ref.collection("answerCandidates")
    offer_candidates = call_ref.collection("offerCandidates")

    @pc.on("icecandidate")
    async def on_icecandidate(event):
        if event.candidate:
            await answer_candidates.add(json.loads(event.candidate.to_json()))

    @pc.on("track")
    def on_track(track):
        print(f"Track received: {track.kind}")
        if track.kind == "audio":
            receiver = AudioReceiver(track)
            asyncio.ensure_future(play_audio(receiver))
        # If you wanted to handle video, you'd add code here

    # Get offer
    offer_data = call_ref.get().to_dict()
    if not offer_data or "offer" not in offer_data:
        print("No valid offer found.")
        return

    offer = RTCSessionDescription(sdp=offer_data["offer"]["sdp"], type=offer_data["offer"]["type"])
    await pc.setRemoteDescription(offer)

    # Create answer
    answer = await pc.createAnswer()
    await pc.setLocalDescription(answer)

    # Send answer to Firestore
    await call_ref.update({
        "answer": {
            "type": pc.localDescription.type,
            "sdp": pc.localDescription.sdp
        }
    })

    # Listen for ICE candidates from caller
    def on_offer_candidate(snapshot, changes, read_time):
        for change in changes:
            if change.type.name == 'ADDED':
                candidate = change.document.to_dict()
                asyncio.ensure_future(pc.addIceCandidate(RTCIceCandidate(
                    sdpMid=candidate['sdpMid'],
                    sdpMLineIndex=candidate['sdpMLineIndex'],
                    candidate=candidate['candidate']
                )))

    offer_candidates.on_snapshot(on_offer_candidate)

    # Keep alive
    while True:
        await asyncio.sleep(1)

async def play_audio(receiver):
    while True:
        await receiver.recv()

if __name__ == "__main__":
    import sys
    if len(sys.argv) < 2:
        print("Usage: python receiver.py CALL_ID")
        sys.exit(1)

    call_id = sys.argv[1]
    asyncio.run(run_receiver(call_id))
