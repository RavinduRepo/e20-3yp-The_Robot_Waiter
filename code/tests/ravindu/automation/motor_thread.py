# motor_thread.py
import json
import time
import os
import threading
import multiprocessing
import signal
import sys
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
from ultrasonic_thread2 import measure_distance
import RPi.GPIO as GPIO

# Motor GPIO pins
IN1, IN2 = 13, 27
IN3, IN4 = 22, 23

GPIO.setmode(GPIO.BCM)
GPIO.setwarnings(False)
GPIO.setup(IN1, GPIO.OUT)
GPIO.setup(IN2, GPIO.OUT)
GPIO.setup(IN3, GPIO.OUT)
GPIO.setup(IN4, GPIO.OUT)

# Global variables for process management
shutdown_event = threading.Event()
ultrasonic_process = None
obstacle_monitor_process = None
mqtt_client = None
motor_timer = None

# Shared memory for ultrasonic sensors
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])        # [front_blocked, back_blocked]

# Configuration
distance_threshold = 50

def load_mqtt_credentials():
    """Load MQTT credentials from file with retry logic"""
    max_retries = 5
    retry_delay = 2
    
    for attempt in range(max_retries):
        try:
            if os.path.exists("mqtt_data_log.json"):
                with open("mqtt_data_log.json", "r") as f:
                    data = json.load(f)
                
                # Extract credentials
                user_data = data["data"]["user"]
                credentials = {
                    "aws_access_key": user_data["awsAccessKey"],
                    "aws_secret_key": user_data["awsSecretKey"],
                    "aws_session_token": user_data["awsSessionToken"],
                    "region": user_data["awsRegion"],
                    "endpoint": user_data["awsHost"],
                    "topic": user_data["topic"]
                }
                
                print(f"✅ MQTT credentials loaded successfully")
                return credentials
                
        except FileNotFoundError:
            print(f"⚠️ Credentials file not found, attempt {attempt + 1}/{max_retries}")
        except (json.JSONDecodeError, KeyError) as e:
            print(f"⚠️ Error parsing credentials, attempt {attempt + 1}/{max_retries}: {e}")
        except Exception as e:
            print(f"⚠️ Unexpected error loading credentials, attempt {attempt + 1}/{max_retries}: {e}")
        
        if attempt < max_retries - 1:
            print(f"🔄 Retrying in {retry_delay} seconds...")
            time.sleep(retry_delay)
            retry_delay *= 2  # Exponential backoff
    
    print("❌ Failed to load MQTT credentials after all retries")
    return None

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Received signal {sig}, shutting down motor thread...")
    shutdown_gracefully()
    sys.exit(0)

def shutdown_gracefully():
    """Perform graceful shutdown of all components"""
    global ultrasonic_process, obstacle_monitor_process, mqtt_client, motor_timer
    
    print("🛑 Initiating graceful shutdown...")
    
    # Set shutdown event
    shutdown_event.set()
    
    # Stop motor immediately
    motor_stop()
    
    # Cancel any pending motor timer
    if motor_timer:
        motor_timer.cancel()
        motor_timer = None
    
    # Disconnect MQTT client
    if mqtt_client:
        try:
            print("🔌 Disconnecting MQTT client...")
            mqtt_client.disconnect()
            mqtt_client = None
            print("✅ MQTT client disconnected")
        except Exception as e:
            print(f"⚠️ Error disconnecting MQTT client: {e}")
    
    # Stop ultrasonic process
    if ultrasonic_process and ultrasonic_process.is_alive():
        print("📏 Stopping ultrasonic sensor process...")
        ultrasonic_process.terminate()
        ultrasonic_process.join(timeout=5)
        if ultrasonic_process.is_alive():
            ultrasonic_process.kill()
        ultrasonic_process = None
        print("✅ Ultrasonic sensor process stopped")
    
    # Stop obstacle monitor process
    if obstacle_monitor_process and obstacle_monitor_process.is_alive():
        print("🚧 Stopping obstacle monitor process...")
        obstacle_monitor_process.terminate()
        obstacle_monitor_process.join(timeout=5)
        if obstacle_monitor_process.is_alive():
            obstacle_monitor_process.kill()
        obstacle_monitor_process = None
        print("✅ Obstacle monitor process stopped")
    
    # Cleanup GPIO
    try:
        GPIO.cleanup()
        print("✅ GPIO cleanup completed")
    except Exception as e:
        print(f"⚠️ Error during GPIO cleanup: {e}")
    
    print("🏁 Graceful shutdown completed")

# === Motor control functions ===
def stop_motor_after_timeout(timeout=0.3):
    global motor_timer
    if shutdown_event.is_set():
        return
        
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    if shutdown_event.is_set():
        return
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    if shutdown_event.is_set():
        return
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    if shutdown_event.is_set():
        return
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
    if shutdown_event.is_set():
        return
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

# === Obstacle monitoring thread ===
def monitor_obstacles():
    print("🚧 Starting obstacle monitoring...")
    
    while not shutdown_event.is_set():
        try:
            front, back = shared_distances[0], shared_distances[1]
            blocked_directions[0] = 1 if front < distance_threshold else 0
            blocked_directions[1] = 1 if back < distance_threshold else 0
            
            # Only print every 10 cycles to reduce spam
            if int(time.time()) % 5 == 0:
                print(f"📏 Front: {front:.2f} cm | Back: {back:.2f} cm | Blocked: F={blocked_directions[0]} B={blocked_directions[1]}")
            
            time.sleep(0.5)
        except Exception as e:
            if not shutdown_event.is_set():
                print(f"⚠️ Error in obstacle monitoring: {e}")
            time.sleep(1)
    
    print("✅ Obstacle monitoring stopped")

# === MQTT message handler ===
def customCallback(client, userdata, message):
    global motor_timer
    
    if shutdown_event.is_set():
        return
    
    try:
        payload = message.payload.decode()
        print(f"📩 Received message: {payload}")

        if payload == '{"key":"ArrowUp"}':
            if blocked_directions[0]:
                print("🚫 Obstacle ahead!")
                motor_stop()
                return
            motor_forward()

        elif payload == '{"key":"ArrowDown"}':
            if blocked_directions[1]:
                print("🚫 Obstacle behind!")
                motor_stop()
                return
            motor_backward()

        elif payload == '{"key":"ArrowLeft"}':
            motor_left()

        elif payload == '{"key":"ArrowRight"}':
            motor_right()

        else:
            print("❓ Unknown command")
            motor_stop()
            if motor_timer:
                motor_timer.cancel()
                
    except Exception as e:
        print(f"⚠️ Error processing MQTT message: {e}")

def setup_mqtt_client(credentials):
    """Setup and connect MQTT client"""
    global mqtt_client
    
    try:
        print("🔗 Setting up MQTT client...")
        
        # Setup AWSIoTPythonSDK MQTT Client with WebSocket
        mqtt_client = AWSIoTMQTTClient("pythonClient", useWebsocket=True)
        mqtt_client.configureEndpoint(credentials["endpoint"], 443)
        mqtt_client.configureCredentials("../../../cert/AmazonRootCA1.pem")  # Only the CA is needed for WebSocket

        # Configure credentials
        mqtt_client.configureIAMCredentials(
            credentials["aws_access_key"], 
            credentials["aws_secret_key"], 
            credentials["aws_session_token"]
        )

        # Configurations (timeouts and more)
        mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
        mqtt_client.configureOfflinePublishQueueing(-1)  # Infinite queueing
        mqtt_client.configureDrainingFrequency(2)
        mqtt_client.configureConnectDisconnectTimeout(10)
        mqtt_client.configureMQTTOperationTimeout(5)

        # Connect and subscribe
        print(f"🔗 Connecting to {credentials['endpoint']} using WebSocket...")
        mqtt_client.connect()
        mqtt_client.subscribe(credentials["topic"], 1, customCallback)
        print(f"✅ Connected and subscribed to {credentials['topic']}")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup MQTT client: {e}")
        return False

def start_background_processes():
    """Start ultrasonic and obstacle monitoring processes"""
    global ultrasonic_process, obstacle_monitor_process
    
    try:
        print("🚀 Starting background processes...")
        
        # Start ultrasonic sensor process
        ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
        ultrasonic_process.start()
        print("✅ Ultrasonic sensor process started")
        
        # Start obstacle monitoring process
        obstacle_monitor_process = multiprocessing.Process(target=monitor_obstacles)
        obstacle_monitor_process.start()
        print("✅ Obstacle monitoring process started")
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start background processes: {e}")
        return False

def main():
    """Main function with improved error handling and graceful shutdown"""
    global shutdown_event
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🤖 Robot Motor Control Starting...")
    
    try:
        # Load MQTT credentials
        credentials = load_mqtt_credentials()
        if not credentials:
            print("❌ Failed to load MQTT credentials. Exiting...")
            return
        
        # Start background processes
        if not start_background_processes():
            print("❌ Failed to start background processes. Exiting...")
            return
        
        # Setup MQTT client
        if not setup_mqtt_client(credentials):
            print("❌ Failed to setup MQTT client. Exiting...")
            return
        
        print("🎉 Robot control system fully initialized!")
        print("🎮 Ready to receive control commands...")
        print("Press Ctrl+C to stop...")
        
        # Main loop - keep the program alive
        while not shutdown_event.is_set():
            try:
                # Health check every 30 seconds
                time.sleep(30)
                
                # Check if processes are still alive
                if ultrasonic_process and not ultrasonic_process.is_alive():
                    print("⚠️ Ultrasonic process died, restarting...")
                    ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
                    ultrasonic_process.start()
                
                if obstacle_monitor_process and not obstacle_monitor_process.is_alive():
                    print("⚠️ Obstacle monitor process died, restarting...")
                    obstacle_monitor_process = multiprocessing.Process(target=monitor_obstacles)
                    obstacle_monitor_process.start()
                
                print("💓 System health check: All processes running")
                
            except Exception as e:
                if not shutdown_event.is_set():
                    print(f"⚠️ Error in main loop: {e}")
                time.sleep(5)
        
    except Exception as e:
        print(f"💥 Critical error in main function: {e}")
    
    finally:
        shutdown_gracefully()

if __name__ == "__main__":
    main()