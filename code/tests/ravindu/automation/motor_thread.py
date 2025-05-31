import RPi.GPIO as GPIO
import time
import os
import threading
import multiprocessing
import json
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from ultrasonic_thread2 import measure_distance

# Motor GPIO pins
IN1, IN2 = 13, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# Load AWS IoT credentials from JSON file
def load_mqtt_credentials():
    try:
        with open('mqtt_data_log.json', 'r') as f:
            # Read the last line of the file (most recent credentials)
            lines = f.readlines()
            if lines:
                last_line = lines[-1].strip()
                data = json.loads(last_line)
                user_data = data['data']['user']
                return {
                    'endpoint': user_data['awsHost'],
                    'access_key': user_data['awsAccessKey'],
                    'secret_key': user_data['awsSecretKey'],
                    'session_token': user_data['awsSessionToken'],
                    'region': user_data['awsRegion'],
                    'topic': user_data['topic']
                }
    except Exception as e:
        print(f"Error loading credentials: {e}")
        return None

# Load credentials
credentials = load_mqtt_credentials()
if not credentials:
    print("Failed to load MQTT credentials from mqtt_data_log.json")
    exit(1)

AWS_ENDPOINT = credentials['endpoint']
MQTT_TOPIC = credentials['topic']

distence = 50

# Shared memory for sensor distances and blocked directions
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])        # [front_blocked, back_blocked]
motor_timer = None

# Motor control functions
def stop_motor_after_timeout(timeout=0.3):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
    print("➡️ Turning right")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_stop():
    print("🛑 Stopping motors")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

# Monitor obstacles from sensors
def monitor_obstacles():
    while True:
        front, back = shared_distances[0], shared_distances[1]

        blocked_directions[0] = 1 if front < distence else 0  # Block forward if front too close
        blocked_directions[1] = 1 if back < distence else 0   # Block backward if back too close

        print(f"📏 Front: {front:.2f} cm | Back: {back:.2f} cm | Blocked: F={blocked_directions[0]} B={blocked_directions[1]}")
        time.sleep(0.5)

# MQTT Callbacks
def on_connect_success():
    print("✅ Connected to AWS IoT Core")
    print(f"📡 Subscribing to topic: {MQTT_TOPIC}")
    client.subscribe(MQTT_TOPIC, 1, on_message)

def on_connect_failure():
    print("❌ Failed to connect to AWS IoT Core")

def on_disconnect():
    print("❌ Disconnected from AWS IoT Core")

def on_subscribe_success(mid):
    print(f"✅ Successfully subscribed to topic with message ID: {mid}")

def on_subscribe_failure(mid):
    print(f"❌ Failed to subscribe to topic with message ID: {mid}")

def on_message(client, userdata, message):
    global motor_timer
    payload = message.payload.decode()
    print(f"📩 Received message: {payload}")

    if payload == '{"key":"ArrowUp"}':
        if blocked_directions[0]:  # Front sensor
            print("🚫 Obstacle ahead! Cannot move forward.")
            motor_stop()
            return
        motor_forward()

    elif payload == '{"key":"ArrowDown"}':
        if blocked_directions[1]:  # Back sensor
            print("🚫 Obstacle behind! Cannot move backward.")
            motor_stop()
            return
        motor_backward()

    elif payload == '{"key":"ArrowLeft"}':
        motor_left()

    elif payload == '{"key":"ArrowRight"}':
        motor_right()

    else:
        print("❓ Unknown command. Stopping motors.")
        motor_stop()
        if motor_timer:
            motor_timer.cancel()

# MQTT Client Setup using AWS IoT SDK with temporary credentials
client_id = f"robot_client_{int(time.time())}"
client = AWSIoTMQTTClient(client_id, useWebsocket=True)

# Configure AWS IoT endpoint
client.configureEndpoint(AWS_ENDPOINT, 443)

# Configure credentials
client.configureCredentials(None)  # No root CA needed for WebSocket
client.configureIAMCredentials(
    credentials['access_key'],
    credentials['secret_key'], 
    credentials['session_token']
)

# Configure connection settings
client.configureAutoReconnectBackoffBaseDelay(1)
client.configureAutoReconnectBackoffMaxDelay(32)
client.configureAutoReconnectBackoffMultiplier(2)
client.configureOfflinePublishQueueing(-1)
client.configureDrainingFrequency(2)
client.configureConnectDisconnectTimeout(10)
client.configureMQTTOperationTimeout(5)

print(f"🔑 Using credentials from: {credentials['endpoint']}")
print(f"📡 Will subscribe to topic: {credentials['topic']}")
print(f"🤖 Client ID: {client_id}")

# Launch background processes
ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
ultrasonic_process.start()

obstacle_process = multiprocessing.Process(target=monitor_obstacles)
obstacle_process.start()

# Main Loop
try:
    print(f"🔗 Connecting to AWS IoT Core at {AWS_ENDPOINT}...")
    
    # Attempt connection
    if client.connect(5):  # 5 second timeout
        print("✅ Connected to AWS IoT Core successfully!")
        
        # Subscribe to topic
        print(f"📡 Subscribing to topic: {MQTT_TOPIC}")
        client.subscribe(MQTT_TOPIC, 1, on_message)
        print("✅ Subscription request sent")
        
        print("✅ MQTT client running... Waiting for commands.")
        
        # Keep the main thread alive
        while True:
            time.sleep(1)
    else:
        print("❌ Failed to connect to AWS IoT Core")
        print("💡 Possible issues:")
        print("   - Invalid/expired credentials")
        print("   - Network connectivity problems")
        print("   - AWS IoT policy restrictions")
        print("   - Incorrect endpoint URL")

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")

except Exception as e:
    print(f"❌ Error in main loop: {e}")

finally:
    motor_stop()
    GPIO.cleanup()
    try:
        client.disconnect()
        print("✅ MQTT client disconnected")
    except:
        pass
    ultrasonic_process.terminate()
    obstacle_process.terminate()
    print("✅ Cleanup complete. Goodbye!")