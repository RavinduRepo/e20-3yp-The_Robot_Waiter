import json
import ssl
import paho.mqtt.client as mqtt

# AWS IoT Core settings
AWS_ENDPOINT = "a2xhp106oe6s98-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device1"
CERT_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-certificate.pem.crt"
KEY_PATH = "../cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-private.pem.key"
ROOT_CA_PATH = "../cert/AmazonRootCA1.pem"

# MQTT Callback for received messages
def on_message(client, userdata, message):
#    print(f"RAW Message: {message.payload.decode()}")
    try:
        command = json.loads(message.payload.decode())
#        print(f"Received command: {command}")
        if command["action"] == "forward":
            print("Moving forward")
        elif command["action"] == "stop":
            print("Stopping")
    except json.JSONDecodeError as e:
        print(f"JSON Error: {e}")

# Callback for connection success
def on_connect(client, userdata, flags, rc):
    print(f"Connected with result code {rc}")
    if rc == 0:
#        print("Connection successful, subscribing to /robot/control...")
        client.subscribe("/robot/control")
    else:
        print(f"Failed to connect, result code {rc}")

# Setup MQTT Client
client = mqtt.Client(client_id=THING_NAME)
client.tls_set(ROOT_CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLS)
client.on_message = on_message
client.on_connect = on_connect  # Add the on_connect callback

# Logging for debugging
client.on_log = lambda client, userdata, level, buf: print(f"LOG: {buf}")

# Connect to AWS IoT Core
client.connect(AWS_ENDPOINT, 8883)

# Start the MQTT client loop
client.loop_forever()

