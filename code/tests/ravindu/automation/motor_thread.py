import json
import os
import time
import threading
import multiprocessing
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from ultrasonic_thread2 import measure_distance
import RPi.GPIO as GPIO

# GPIO Setup
IN1, IN2, IN3, IN4 = 13, 27, 22, 23
GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
for pin in [IN1, IN2, IN3, IN4]:
    GPIO.setup(pin, GPIO.OUT)

# Constants
TOPIC = "your/topic/here"  # same as in localStorage.getItem("topic") in React
DISTANCE_THRESHOLD = 50

# Shared memory for sensor distances
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])
motor_timer = None

# Load credentials
with open("mqtt_data_log.json", "r") as f:
    data = json.load(f)
    credentials = data["data"]["user"]
    token = credentials["token"]

# AWS MQTT settings
ACCESS_KEY = credentials["accessKeyId"]
SECRET_KEY = credentials["secretAccessKey"]
SESSION_TOKEN = credentials["sessionToken"]
REGION = data["data"].get("region", "ap-southeast-2")  # optional default
ENDPOINT = data["data"].get("host", "a2cdp9hijgdiig-ats.iot.ap-southeast-2.amazonaws.com")

# Create MQTT client with WebSocket
client = AWSIoTMQTTClient("raspberryPiClient", useWebsocket=True)
client.configureEndpoint(ENDPOINT, 443)
client.configureCredentials(os.path.join(os.getcwd(), "AmazonRootCA1.pem"))

# Set credentials
client.configureIAMCredentials(ACCESS_KEY, SECRET_KEY, SESSION_TOKEN)

# Configure MQTT behavior
client.configureAutoReconnectBackoffTime(1, 32, 20)
client.configureOfflinePublishQueueing(-1)
client.configureDrainingFrequency(2)
client.configureConnectDisconnectTimeout(10)
client.configureMQTTOperationTimeout(5)

# Motor control functions
def stop_motor_after_timeout(timeout=0.3):
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_stop():
    for pin in [IN1, IN2, IN3, IN4]:
        GPIO.output(pin, GPIO.LOW)

# Obstacle monitoring
def monitor_obstacles():
    while True:
        front, back = shared_distances[0], shared_distances[1]
        blocked_directions[0] = 1 if front < DISTANCE_THRESHOLD else 0
        blocked_directions[1] = 1 if back < DISTANCE_THRESHOLD else 0
        print(f"📏 Front: {front:.2f}, Back: {back:.2f} | Blocked: {blocked_directions[:]}")
        time.sleep(0.5)

# MQTT Callbacks
def customCallback(client, userdata, message):
    global motor_timer
    payload = message.payload.decode()
    print(f"📩 Received: {payload}")

    if payload == '{"key":"ArrowUp"}':
        if blocked_directions[0]:
            print("🚫 Obstacle ahead.")
            motor_stop()
            return
        motor_forward()
    elif payload == '{"key":"ArrowDown"}':
        if blocked_directions[1]:
            print("🚫 Obstacle behind.")
            motor_stop()
            return
        motor_backward()
    elif payload == '{"key":"ArrowLeft"}':
        motor_left()
    elif payload == '{"key":"ArrowRight"}':
        motor_right()
    else:
        print("❓ Unknown command. Stopping.")
        motor_stop()
        if motor_timer:
            motor_timer.cancel()

# Start distance measuring and obstacle threads
ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
ultrasonic_process.start()

obstacle_process = multiprocessing.Process(target=monitor_obstacles)
obstacle_process.start()

# Connect and subscribe
try:
    print("🔗 Connecting to AWS IoT Core...")
    client.connect()
    print("✅ Connected.")
    client.subscribe(TOPIC, 1, customCallback)

    while True:
        time.sleep(1)

except KeyboardInterrupt:
    print("\n🛑 Keyboard Interrupt received.")

finally:
    motor_stop()
    GPIO.cleanup()
    ultrasonic_process.terminate()
    obstacle_process.terminate()
    print("✅ Cleanup complete.")
