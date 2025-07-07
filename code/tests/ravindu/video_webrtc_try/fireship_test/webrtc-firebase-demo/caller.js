// caller.js
import './style.css';
import firebase from 'firebase/app';
import 'firebase/firestore';

const firebaseConfig = {
  apiKey: "AIzaSyBubdSfljjucCKUUwEwh15EtZFLywbsGEQ",
  authDomain: "test-webrtc-f155e.firebaseapp.com",
  projectId: "test-webrtc-f155e",
  storageBucket: "test-webrtc-f155e.firebasestorage.app",
  messagingSenderId: "674163171327",
  appId: "1:674163171327:web:c8f988f1605a01bd9291ca",
  measurementId: "G-VV8L1PP7GZ"
};

if (!firebase.apps.length) {
  firebase.initializeApp(firebaseConfig);
}
const firestore = firebase.firestore();

const servers = {
  iceServers: [
    { urls: 'stun:stun.l.google.com:19302' },
    { urls: 'stun:stun1.l.google.com:19302' },
    {
      urls: 'turn:relay.metered.ca:80',
      username: 'openai',
      credential: 'openai'
    },
    {
      urls: 'turn:relay.metered.ca:443',
      username: 'openai',
      credential: 'openai'
    }
  ],
  iceCandidatePoolSize: 10,
};

let pc = null;
let localStream = null;
let remoteStream = new MediaStream();

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
  if (remoteStream) {
    remoteStream.getTracks().forEach(track => track.stop());
    remoteStream = new MediaStream();
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
  alert('This site needs access to your camera and microphone. Please click "Allow" in your browser prompt.');
  try {
    localStream = await navigator.mediaDevices.getUserMedia({ audio: true });
    webcamVideo.srcObject = localStream;
    pc = new RTCPeerConnection(servers);

    localStream.getTracks().forEach((track) => {
      pc.addTrack(track, localStream);
    });

    pc.addTransceiver('video', { direction: 'recvonly' });
    pc.addTransceiver('audio', { direction: 'recvonly' }); // Ensure audio is expected

    pc.ontrack = (event) => {
      console.log(`[ontrack] Received track: kind=${event.track.kind}`);
      remoteStream.addTrack(event.track);
      remoteVideo.srcObject = remoteStream;

      if (event.track.kind === 'audio') {
        console.log('[ontrack] Remote audio track received:', event.track);
      }

      if (event.track.kind === 'video') {
        console.log('[ontrack] Remote video track received:', event.track);
      }
    };

    pc.onconnectionstatechange = () => {
      console.log('Connection state changed to:', pc.connectionState);
    };

    callButton.disabled = false;
    webcamButton.disabled = true;
  } catch (error) {
    console.error('Error accessing media devices:', error);
    alert('Failed to start webcam. Please ensure camera/microphone permissions are granted and devices are available.');
  }
};

callButton.onclick = async () => {
  if (!pc) {
    alert("Please start your webcam first!");
    return;
  }
  const callDoc = firestore.collection('calls').doc();
  const offerCandidates = callDoc.collection('offerCandidates');
  const answerCandidates = callDoc.collection('answerCandidates');

  callInput.value = callDoc.id;

  pc.onicecandidate = (event) => {
    if (event.candidate) {
      console.log('[onicecandidate] Local ICE candidate:', event.candidate);
      offerCandidates.add(event.candidate.toJSON());
    }
  };

  const offerDescription = await pc.createOffer();
  await pc.setLocalDescription(offerDescription);
  console.log('[createOffer] Offer created and set:', offerDescription);

  await callDoc.set({ offer: { sdp: offerDescription.sdp, type: offerDescription.type } });

  callDoc.onSnapshot((snapshot) => {
    const data = snapshot.data();
    if (data?.answer && !pc.currentRemoteDescription) {
      const answerDescription = new RTCSessionDescription(data.answer);
      pc.setRemoteDescription(answerDescription);
      console.log('[onSnapshot] Answer received and set:', answerDescription);
    }
  });

  answerCandidates.onSnapshot((snapshot) => {
    snapshot.docChanges().forEach((change) => {
      if (change.type === 'added') {
        const candidate = new RTCIceCandidate(change.doc.data());
        pc.addIceCandidate(candidate);
        console.log('[onSnapshot] Remote ICE candidate added:', candidate);
      }
    });
  });

  hangupButton.disabled = false;
  callButton.disabled = true;
};

hangupButton.onclick = () => {
  resetCall();
};
