import json
import ssl
import paho.mqtt.client as mqtt

# AWS IoT Core settings
AWS_ENDPOINT = "a2xhp106oe6s98-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device1"
CERT_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-certificate.pem.crt"
KEY_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-private.pem.key"
ROOT_CA_PATH = "../cert/AmazonRootCA1.pem"

# Topic for subscription
TOPIC = "/3YP/batch2025/device1"

# Command handler function
def command_handler(command):
    key = command.get("key", "")
    
    if key == "ArrowRight":
        print("Moving Right")
    elif key == "ArrowLeft":
        print("Moving Left")
    elif key == "ArrowUp":
        print("Moving Forward")
    elif key == "ArrowDown":
        print("Moving Backward")
    else:
        print(f"Unknown command: {key}")

# MQTT Callback for received messages
def on_message(client, userdata, message):
    try:
        payload = message.payload.decode()
        command = json.loads(payload)
        print(f"Received command: {command}")
        
        command_handler(command)
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {e}")
    except Exception as e:
        print(f"Error processing message: {e}")

# Callback for connection success
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print(f"Connected successfully to {AWS_ENDPOINT}")
        client.subscribe(TOPIC)
        print(f"Subscribed to topic: {TOPIC}")
    else:
        print(f"Failed to connect, return code {rc}")

# Setup MQTT Client
client = mqtt.Client(client_id=THING_NAME)
client.tls_set(ROOT_CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLS)
client.on_message = on_message
client.on_connect = on_connect  # Attach connection callback

# Logging for debugging
client.on_log = lambda client, userdata, level, buf: print(f"LOG: {buf}")

# Connect to AWS IoT Core
client.connect(AWS_ENDPOINT, 8883)

# Start the MQTT client loop
client.loop_forever()

