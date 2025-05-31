import RPi.GPIO as GPIO
import time
import os
import threading
import multiprocessing
import paho.mqtt.client as mqtt
import json
import sys
from ultrasonic_thread import measure_distance

# Motor GPIO pins
IN1, IN2 = 13, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# Configuration files
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"

# Fallback AWS IoT setup (in case credentials file is not available)
AWS_ENDPOINT = "a2cdp9hijgdiig-ats.iot.ap-southeast-2.amazonaws.com"
THING_NAME = "3yp-device2"
FALLBACK_MQTT_TOPIC = "#"
CERT_FILE = "../../cert/567ac5f9b0348408455bfc91506042fe17270e042a0499705711a24c5c7a6883-certificate.pem.crt"
KEY_FILE = "../../cert/567ac5f9b0348408455bfc91506042fe17270e042a0499705711a24c5c7a6883-private.pem.key"
CA_CERT = "../../cert/AmazonRootCA1.pem"

distence = 50

def load_mqtt_credentials():
    """Load MQTT credentials from the file created by selenium script"""
    try:
        if os.path.exists(ROBOT_CREDENTIALS_FILE):
            with open(ROBOT_CREDENTIALS_FILE, "r") as file:
                credentials = json.load(file)
                print(f"✅ Loaded MQTT credentials for Robot ID: {credentials.get('robotId', 'Unknown')}")
                return credentials
        else:
            print("⚠️ No MQTT credentials file found, using fallback configuration")
            return None
    except Exception as e:
        print(f"❌ Error loading MQTT credentials: {e}")
        return None

def get_mqtt_config():
    """Get MQTT configuration from credentials or fallback"""
    credentials = load_mqtt_credentials()
    
    if credentials and credentials.get('token'):
        # Use dynamic configuration from selenium script
        config = {
            'endpoint': AWS_ENDPOINT,  # Keep same endpoint
            'topic': credentials.get('topic', f"robot/{credentials.get('robotId', 'unknown')}/commands"),
            'token': credentials.get('token'),
            'robotId': credentials.get('robotId'),
            'use_token_auth': True
        }
        print(f"🔑 Using token-based authentication for robot: {config['robotId']}")
        print(f"📡 Subscribing to topic: {config['topic']}")
    else:
        # Use fallback certificate-based authentication
        config = {
            'endpoint': AWS_ENDPOINT,
            'topic': FALLBACK_MQTT_TOPIC,
            'cert_file': CERT_FILE,
            'key_file': KEY_FILE,
            'ca_cert': CA_CERT,
            'use_token_auth': False
        }
        print("🔒 Using certificate-based authentication (fallback)")
        print(f"📡 Subscribing to topic: {config['topic']}")
        
        # Validate certificates for fallback mode
        for f in [config['ca_cert'], config['cert_file'], config['key_file']]:
            if not os.path.exists(f):
                raise FileNotFoundError(f"Missing certificate file: {f}")
    
    return config

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
        mqtt_config = userdata
        client.subscribe(mqtt_config['topic'])
        print(f"📡 Subscribed to topic: {mqtt_config['topic']}")
    else:
        print(f"❌ MQTT connection failed with code {rc}")

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

def setup_mqtt_client(mqtt_config):
    """Setup MQTT client with appropriate authentication method"""
    client = mqtt.Client()
    client.user_data_set(mqtt_config)
    
    if mqtt_config['use_token_auth']:
        # Token-based authentication (from selenium script)
        print("🔑 Setting up token-based authentication...")
        # For AWS IoT with tokens, you might need to set custom headers or use different auth method
        # This depends on how your AWS IoT is configured to accept tokens
        client.tls_set(ca_certs=CA_CERT)  # Still need CA cert for TLS
        # Add token to headers or as username/password depending on your setup
        client.username_pw_set(mqtt_config['robotId'], mqtt_config['token'])
    else:
        # Certificate-based authentication (fallback)
        print("🔒 Setting up certificate-based authentication...")
        client.tls_set(ca_certs=mqtt_config['ca_cert'], 
                      certfile=mqtt_config['cert_file'], 
                      keyfile=mqtt_config['key_file'])
    
    client.on_connect = on_connect
    client.on_message = on_message
    
    return client

def main():
    """Main function"""
    try:
        print("🤖 Robot Control Script Starting...")
        
        # Get MQTT configuration
        mqtt_config = get_mqtt_config()
        
        # Setup MQTT client
        client = setup_mqtt_client(mqtt_config)
        
        # Launch background processes
        ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
        ultrasonic_process.start()

        obstacle_process = multiprocessing.Process(target=monitor_obstacles)
        obstacle_process.start()

        # Main Loop
        print(f"🔗 Connecting to AWS IoT Core at {mqtt_config['endpoint']}...")
        client.connect(mqtt_config['endpoint'], 8883, 60)
        client.loop_start()
        print("✅ MQTT client running... Waiting for commands.")

        while True:
            time.sleep(1)

    except KeyboardInterrupt:
        print("\n🛑 Shutting down...")

    except Exception as e:
        print(f"❌ Error in main process: {e}")
        sys.exit(1)

    finally:
        motor_stop()
        GPIO.cleanup()
        if 'client' in locals():
            client.loop_stop()
        if 'ultrasonic_process' in locals():
            ultrasonic_process.terminate()
        if 'obstacle_process' in locals():
            obstacle_process.terminate()
        print("✅ Cleanup complete. Goodbye!")

if __name__ == "__main__":
    main()