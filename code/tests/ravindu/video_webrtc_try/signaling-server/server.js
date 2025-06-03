const express = require('express');
const WebSocket = require('ws');
const app = express();
const server = require('http').createServer(app);
const wss = new WebSocket.Server({ server });

let clientSocket = null;
let piSocket = null;

wss.on('connection', socket => {
  socket.on('message', msg => {
    const message = JSON.parse(msg);
    if (message.role === 'client') {
      clientSocket = socket;
    } else if (message.role === 'pi') {
      piSocket = socket;
    }

    if (message.type === 'offer' && clientSocket) {
      clientSocket.send(JSON.stringify({ type: 'offer', sdp: message.sdp }));
    }

    if (message.type === 'answer' && piSocket) {
      piSocket.send(JSON.stringify({ type: 'answer', sdp: message.sdp }));
    }

    if (message.type === 'ice' && message.to === 'client' && clientSocket) {
      clientSocket.send(JSON.stringify({ type: 'ice', candidate: message.candidate }));
    }

    if (message.type === 'ice' && message.to === 'pi' && piSocket) {
      piSocket.send(JSON.stringify({ type: 'ice', candidate: message.candidate }));
    }
  });
});

app.use(express.static('public'));

server.listen(3000, () => console.log('Server running on http://localhost:3000'));
