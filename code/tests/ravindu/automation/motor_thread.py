import RPi.GPIO as GPIO
import time
import os
import threading
import multiprocessing
import paho.mqtt.client as mqtt
import json
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
def on_connect(client, userdata, flags, rc, properties=None):
    if rc == 0:
        print("✅ Connected to AWS IoT Core")
        result, mid = client.subscribe(MQTT_TOPIC)
        if result == mqtt.MQTT_ERR_SUCCESS:
            print(f"📡 Successfully subscribed to topic: {MQTT_TOPIC}")
        else:
            print(f"❌ Failed to subscribe to topic: {MQTT_TOPIC}, error code: {result}")
    else:
        print(f"❌ MQTT connection failed with code {rc}")

def on_subscribe(client, userdata, mid, granted_qos):
    print(f"✅ Subscription confirmed for message ID: {mid}, QoS: {granted_qos}")

def on_disconnect(client, userdata, rc):
    if rc != 0:
        print(f"❌ Unexpected disconnection from MQTT broker, code: {rc}")
    else:
        print("✅ Disconnected from MQTT broker")

def on_message(client, userdata, msg):
    global motor_timer
    payload = msg.payload.decode()
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

# MQTT Client Setup
client = mqtt.Client()
client.on_connect = on_connect
client.on_subscribe = on_subscribe
client.on_disconnect = on_disconnect
client.on_message = on_message

# Launch background processes
ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
ultrasonic_process.start()

obstacle_process = multiprocessing.Process(target=monitor_obstacles)
obstacle_process.start()

# Main Loop
try:
    print(f"🔗 Connecting to AWS IoT Core at {AWS_ENDPOINT}...")
    client.connect(AWS_ENDPOINT, 8883, 60)
    client.loop_start()
    print("✅ MQTT client running... Waiting for commands.")

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Shutting down...")

finally:
    motor_stop()
    GPIO.cleanup()
    client.loop_stop()
    ultrasonic_process.terminate()
    obstacle_process.terminate()
    print("✅ Cleanup complete. Goodbye!")