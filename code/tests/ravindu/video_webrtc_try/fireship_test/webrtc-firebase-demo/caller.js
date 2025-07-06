import firebase from 'firebase/app';
import 'firebase/firestore';

const firebaseConfig = {
  apiKey: "AIzaSyBubdSfljjucCKUUwEwh15EtZFLywbsGEQ",
  authDomain: "test-webrtc-f155e.firebaseapp.com",
  projectId: "test-webrtc-f155e",
  storageBucket: "test-webrtc-f155e.appspot.com",
  messagingSenderId: "674163171327",
  appId: "1:674163171327:web:c8f988f1605a01bd9291ca"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
const firestore = firebase.firestore();

const servers = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' }
  ],
  iceCandidatePoolSize: 10,
};

let pc = null;
let localStream = null;

const webcamButton = document.getElementById('webcamButton');
const webcamVideo = document.getElementById('webcamVideo');
const callButton = document.getElementById('callButton');
const callInput = document.getElementById('callInput');
const remoteVideo = document.getElementById('remoteVideo');
const hangupButton = document.getElementById('hangupButton');

const resetCall = () => {
  if (localStream) {
    localStream.getTracks().forEach(track => track.stop());
    localStream = null;
  }
  if (pc) {
    pc.close();
    pc = null;
  }
  webcamVideo.srcObject = null;
  remoteVideo.srcObject = null;
  callInput.value = '';
  webcamButton.disabled = false;
  callButton.disabled = true;
  hangupButton.disabled = true;
};

webcamButton.onclick = async () => {
  alert('Please allow microphone access.');
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true, video: false });
    webcamVideo.srcObject = localStream;  // Shows mic activity if any
    pc = new RTCPeerConnection(servers);

    localStream.getTracks().forEach(track => {
      pc.addTrack(track, localStream);
    });

    pc.ontrack = (event) => {
      if (!remoteVideo.srcObject) {
        remoteVideo.srcObject = event.streams[0];
      }
    };

    callButton.disabled = false;
    webcamButton.disabled = true;
  } catch (err) {
    alert('Failed to get microphone: ' + err.message);
  }
};

callButton.onclick = async () => {
  const callDoc = firestore.collection('calls').doc();
  const offerCandidates = callDoc.collection('offerCandidates');
  const answerCandidates = callDoc.collection('answerCandidates');

  callInput.value = callDoc.id;

  pc.onicecandidate = (event) => {
    event.candidate && offerCandidates.add(event.candidate.toJSON());
  };

  const offerDescription = await pc.createOffer();
  await pc.setLocalDescription(offerDescription);

  await callDoc.set({ offer: { type: offerDescription.type, sdp: offerDescription.sdp } });

  callDoc.onSnapshot((snapshot) => {
    const data = snapshot.data();
    if (data?.answer && !pc.currentRemoteDescription) {
      pc.setRemoteDescription(new RTCSessionDescription(data.answer));
    }
  });

  answerCandidates.onSnapshot(snapshot => {
    snapshot.docChanges().forEach(change => {
      if (change.type === 'added') {
        const candidate = new RTCIceCandidate(change.doc.data());
        pc.addIceCandidate(candidate);
      }
    });
  });

  hangupButton.disabled = false;
  callButton.disabled = true;
};

hangupButton.onclick = resetCall;
