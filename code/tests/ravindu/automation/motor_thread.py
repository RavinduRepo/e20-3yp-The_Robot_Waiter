import json
import time
import os
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from urllib.parse import urlparse

# --- Step 1: Load stored credentials from file ---
with open("mqtt_data_log.json", "r") as f:
    logs = f.readlines()

# Get the latest credentials log (the last line in the file)
latest = json.loads(logs[-1])
creds = latest["data"]["credentials"]
region = latest["data"]["region"]
endpoint = latest["data"]["endpoint"]
topic = latest["data"]["topic"]

access_key = creds["AccessKeyId"]
secret_key = creds["SecretKey"]
session_token = creds["SessionToken"]

# --- Step 2: Setup MQTT client with WebSocket + SigV4 ---
client_id = "raspi-client-" + str(int(time.time()))

mqtt_client = AWSIoTMQTTClient(client_id, useWebsocket=True)
mqtt_client.configureEndpoint(endpoint, 443)
mqtt_client.configureCredentials("./AmazonRootCA1.pem")

# Configure credentials (SigV4 Auth)
mqtt_client.configureIAMCredentials(access_key, secret_key, session_token)

# Configure MQTT connection behavior
mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite queue
mqtt_client.configureDrainingFrequency(2)        # Draining: 2 Hz
mqtt_client.configureConnectDisconnectTimeout(10)
mqtt_client.configureMQTTOperationTimeout(5)

# --- Step 3: Define callbacks ---
def on_message(client, userdata, message):
    print(f"📩 Received message from {message.topic}: {message.payload.decode()}")
    # Insert motor control logic here like in your previous on_message()

mqtt_client.onMessage = on_message

# --- Step 4: Connect & Subscribe ---
print("🔗 Connecting to AWS IoT Core via WebSocket with SigV4...")
mqtt_client.connect()
print("✅ Connected.")

mqtt_client.subscribe(topic, 1, on_message)

# --- Step 5: Main loop ---
try:
    while True:
        time.sleep(1)
except KeyboardInterrupt:
    print("🛑 Interrupted. Disconnecting...")
finally:
    mqtt_client.disconnect()
    print("✅ Disconnected.")
