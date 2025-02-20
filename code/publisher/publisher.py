import paho.mqtt.client as mqtt
import json
import ssl
import keyboard
import threading
import time

# AWS IoT Core settings
AWS_ENDPOINT = "a2xhp106oe6s98-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device1"
CERT_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-certificate.pem.crt"
KEY_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-private.pem.key"
ROOT_CA_PATH = "../cert/AmazonRootCA1.pem"

# MQTT Setup
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")

client = mqtt.Client(client_id=THING_NAME)
client.tls_set(ROOT_CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLS)
client.on_connect = on_connect
client.connect(AWS_ENDPOINT, 8883)

# Dictionary to track key press states
key_states = {"forward": False, "backward": False, "left": False, "right": False}

# Function to send MQTT messages while key is held down
def send_mqtt(action):
    while key_states[action]:  # Keep sending while the key is pressed
        message = json.dumps({"action": action})
        client.publish("/robot/control", message)
        time.sleep(0.1)  # Adjust frequency of sending (10 times per second)

# Function to handle key presses
def on_key_event(event):
    if event.event_type == "down":  # Key Pressed
        if event.name == "up" and not key_states["forward"]:
            key_states["forward"] = True
            threading.Thread(target=send_mqtt, args=("forward",), daemon=True).start()
        elif event.name == "down" and not key_states["backward"]:
            key_states["backward"] = True
            threading.Thread(target=send_mqtt, args=("backward",), daemon=True).start()
        elif event.name == "left" and not key_states["left"]:
            key_states["left"] = True
            threading.Thread(target=send_mqtt, args=("left",), daemon=True).start()
        elif event.name == "right" and not key_states["right"]:
            key_states["right"] = True
            threading.Thread(target=send_mqtt, args=("right",), daemon=True).start()

    elif event.event_type == "up":  # Key Released
        if event.name == "up":
            key_states["forward"] = False
        elif event.name == "down":
            key_states["backward"] = False
        elif event.name == "left":
            key_states["left"] = False
        elif event.name == "right":
            key_states["right"] = False

# Start listening for keyboard input
keyboard.hook(on_key_event)
print("Press arrow keys to send commands. Release to stop sending.")
keyboard.wait()  # Keep script running
