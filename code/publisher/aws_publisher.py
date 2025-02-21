import json
import ssl
import time
import paho.mqtt.client as mqtt

# AWS IoT Core Settings (Updated with your details)
AWS_ENDPOINT = "a2xhp106oe6s98-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device1"
CERT_PATH = "cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-certificate.pem.crt"
KEY_PATH = "cert/799d1ffb1d3048e86a907eee932912dc855437b47e8d52b88c6316cf2dc2d8a0-private.pem.key"
ROOT_CA_PATH = "cert/AmazonRootCA1.pem"

# MQTT Topic to Publish To
TOPIC = "/robot/control"

# Callback for connection success
def on_connect(client, userdata, flags, rc):
    if rc == 0:
        print("✅ Connected to AWS IoT Core")
    else:
        print(f"❌ Connection failed. RC: {rc}")

# Logging for debugging
def on_log(client, userdata, level, buf):
    print(f"LOG: {buf}")

# Set up the MQTT client
client = mqtt.Client(client_id=THING_NAME)

# Configure TLS settings (Ensure TLS version is correct for AWS IoT)
client.tls_set(ROOT_CA_PATH, certfile=CERT_PATH, keyfile=KEY_PATH, tls_version=ssl.PROTOCOL_TLSv1_2)

# Attach callbacks
client.on_connect = on_connect
client.on_log = on_log

# Connect to AWS IoT Core
print("🚀 Connecting to AWS IoT Core...")
client.connect(AWS_ENDPOINT, 8883)

# Start the MQTT loop in a non-blocking way
client.loop_start()

# Publish messages to AWS IoT Core
try:
    while True:
        payload = {
            "device": THING_NAME,
            "action": "forward",
            "timestamp": int(time.time())
        }
        
        print(f"📤 Publishing message: {payload}")
        client.publish(TOPIC, json.dumps(payload), qos=1)

        # Wait before sending the next message
        time.sleep(5)

except KeyboardInterrupt:
    print("🛑 Stopping publisher...")
    client.loop_stop()
    client.disconnect()
