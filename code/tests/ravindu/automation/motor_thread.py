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

# Global variables for system state
mqtt_client = None
motor_timer = None
system_running = True
connection_active = False
shared_distances = multiprocessing.Array('d', [100.0, 100.0])  # [front, back]
blocked_directions = multiprocessing.Array('b', [0, 0])        # [front_blocked, back_blocked]
distence = 50

def load_mqtt_credentials():
    """Load MQTT credentials from file"""
    try:
        with open("mqtt_data_log.json", "r") as f:
            data = json.load(f)
        
        credentials = {
            "aws_access_key": data["data"]["user"]["awsAccessKey"],
            "aws_secret_key": data["data"]["user"]["awsSecretKey"],
            "aws_session_token": data["data"]["user"]["awsSessionToken"],
            "region": data["data"]["user"]["awsRegion"],
            "endpoint": data["data"]["user"]["awsHost"],
            "topic": data["data"]["user"]["topic"]
        }
        
        print(f"✅ MQTT credentials loaded successfully")
        print(f"🔗 Endpoint: {credentials['endpoint']}")
        print(f"📡 Topic: {credentials['topic']}")
        
        return credentials
        
    except Exception as e:
        print(f"❌ Error loading MQTT credentials: {e}")
        return None

def stop_motor_after_timeout(timeout=0.3):
    """Stop motor after specified timeout"""
    global motor_timer
    if motor_timer:
        motor_timer.cancel()
    motor_timer = threading.Timer(timeout, motor_stop)
    motor_timer.start()

def motor_forward():
    """Move robot forward"""
    print("🚀 Moving forward")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_backward():
    """Move robot backward"""
    print("🔄 Moving backward")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_left():
    """Turn robot left"""
    print("⬅️ Turning left")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.HIGH)
    GPIO.output(IN3, GPIO.HIGH)
    GPIO.output(IN4, GPIO.LOW)
    stop_motor_after_timeout()

def motor_right():
    """Turn robot right"""
    print("➡️ Turning right")
    GPIO.output(IN1, GPIO.HIGH)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.HIGH)
    stop_motor_after_timeout()

def motor_stop():
    """Stop all motors"""
    print("🛑 Stopping motors")
    GPIO.output(IN1, GPIO.LOW)
    GPIO.output(IN2, GPIO.LOW)
    GPIO.output(IN3, GPIO.LOW)
    GPIO.output(IN4, GPIO.LOW)

def monitor_obstacles():
    """Monitor obstacles continuously"""
    global system_running
    print("👁️ Starting obstacle monitoring...")
    
    while system_running:
        try:
            front, back = shared_distances[0], shared_distances[1]
            blocked_directions[0] = 1 if front < distence else 0
            blocked_directions[1] = 1 if back < distence else 0
            
            # Only print every 10 iterations to reduce spam
            if time.time() % 5 < 0.5:  # Print approximately every 5 seconds
                print(f"📏 Front: {front:.2f}cm | Back: {back:.2f}cm | Blocked: F={blocked_directions[0]} B={blocked_directions[1]}")
            
            time.sleep(0.5)
            
        except Exception as e:
            print(f"⚠️ Error in obstacle monitoring: {e}")
            time.sleep(1)

def customCallback(client, userdata, message):
    """Handle incoming MQTT messages"""
    global motor_timer, connection_active
    
    if not connection_active:
        print("⚠️ Received command but connection is not active")
        return
    
    try:
        payload = message.payload.decode()
        print(f"📩 Received: {payload}")

        # Parse JSON payload
        try:
            command_data = json.loads(payload)
        except:
            print("❓ Invalid JSON format")
            return

        # Handle different message types
        if isinstance(command_data, dict):
            if "key" in command_data:
                handle_movement_command(command_data["key"])
            elif "type" in command_data:
                handle_system_command(command_data)
            else:
                print("❓ Unknown command format")
        else:
            print("❓ Unexpected payload format")
            
    except Exception as e:
        print(f"❌ Error processing message: {e}")

def handle_movement_command(key):
    """Handle movement commands"""
    if key == "ArrowUp":
        if blocked_directions[0]:
            print("🚫 Obstacle ahead!")
            motor_stop()
            return
        motor_forward()

    elif key == "ArrowDown":
        if blocked_directions[1]:
            print("🚫 Obstacle behind!")
            motor_stop()
            return
        motor_backward()

    elif key == "ArrowLeft":
        motor_left()

    elif key == "ArrowRight":
        motor_right()

    else:
        print(f"❓ Unknown movement command: {key}")
        motor_stop()

def handle_system_command(command_data):
    """Handle system-level commands"""
    global connection_active, motor_timer
    
    command_type = command_data.get("type", "").lower()
    
    if command_type == "disconnect":
        print("🔌 Received disconnect command")
        connection_active = False
        motor_stop()
        if motor_timer:
            motor_timer.cancel()
        print("✅ Robot control deactivated")
        
    elif command_type == "reconnect":
        print("🔄 Received reconnect command")
        connection_active = True
        print("✅ Robot control reactivated")
        
    elif command_type == "connect":
        print("🔗 Received connect command")
        connection_active = True
        print("✅ Robot control activated")
        
    else:
        print(f"❓ Unknown system command: {command_type}")

def setup_mqtt_client(credentials):
    """Setup and configure MQTT client"""
    global mqtt_client
    
    try:
        # Create MQTT client with WebSocket
        mqtt_client = AWSIoTMQTTClient("pythonClient", useWebsocket=True)
        mqtt_client.configureEndpoint(credentials["endpoint"], 443)
        mqtt_client.configureCredentials("../../../cert/AmazonRootCA1.pem")
        
        # Configure IAM credentials
        mqtt_client.configureIAMCredentials(
            credentials["aws_access_key"],
            credentials["aws_secret_key"], 
            credentials["aws_session_token"]
        )
        
        # Configure connection settings
        mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
        mqtt_client.configureOfflinePublishQueueing(-1)
        mqtt_client.configureDrainingFrequency(2)
        mqtt_client.configureConnectDisconnectTimeout(10)
        mqtt_client.configureMQTTOperationTimeout(5)
        
        print("✅ MQTT client configured successfully")
        return True
        
    except Exception as e:
        print(f"❌ Failed to setup MQTT client: {e}")
        return False

def connect_mqtt(credentials):
    """Connect to MQTT and subscribe to topic"""
    global mqtt_client, connection_active
    
    try:
        print(f"🔗 Connecting to {credentials['endpoint']}...")
        mqtt_client.connect()
        
        print(f"📡 Subscribing to topic: {credentials['topic']}")
        mqtt_client.subscribe(credentials['topic'], 1, customCallback)
        
        connection_active = True
        print("✅ MQTT connection established and subscribed")
        return True
        
    except Exception as e:
        print(f"❌ MQTT connection failed: {e}")
        return False

def disconnect_mqtt():
    """Disconnect from MQTT"""
    global mqtt_client, connection_active
    
    try:
        if mqtt_client:
            connection_active = False
            mqtt_client.disconnect()
            print("✅ MQTT disconnected")
        return True
    except Exception as e:
        print(f"❌ Error disconnecting MQTT: {e}")
        return False

def signal_handler(signum, frame):
    """Handle shutdown signals gracefully"""
    global system_running
    print(f"\n🛑 Received signal {signum}. Shutting down...")
    system_running = False
    cleanup_and_exit()

def cleanup_and_exit():
    """Clean up resources and exit"""
    global ultrasonic_process, obstacle_process, motor_timer
    
    print("🧹 Cleaning up resources...")
    
    # Stop motors
    motor_stop()
    if motor_timer:
        motor_timer.cancel()
    
    # Disconnect MQTT
    disconnect_mqtt()
    
    # Terminate processes
    try:
        if 'ultrasonic_process' in globals() and ultrasonic_process.is_alive():
            ultrasonic_process.terminate()
            ultrasonic_process.join(timeout=2)
            print("✅ Ultrasonic process terminated")
    except:
        pass
    
    try:
        if 'obstacle_process' in globals() and obstacle_process.is_alive():
            obstacle_process.terminate()
            obstacle_process.join(timeout=2)
            print("✅ Obstacle monitoring process terminated")
    except:
        pass
    
    # Clean up GPIO
    GPIO.cleanup()
    print("✅ GPIO cleanup complete")
    
    print("👋 Motor control system shutdown complete")
    sys.exit(0)

def monitor_credentials_file():
    """Monitor for credential file changes to handle reconnection"""
    global system_running
    last_modified = 0
    
    while system_running:
        try:
            if os.path.exists("mqtt_data_log.json"):
                current_modified = os.path.getmtime("mqtt_data_log.json")
                if current_modified > last_modified:
                    last_modified = current_modified
                    print("🔄 Detected credentials update, checking for reconnection...")
                    # Small delay to ensure file write is complete
                    time.sleep(1)
            time.sleep(5)  # Check every 5 seconds
        except Exception as e:
            print(f"⚠️ Error monitoring credentials file: {e}")
            time.sleep(10)

def main():
    """Main function to start motor control system"""
    global system_running, ultrasonic_process, obstacle_process
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    print("🤖 Starting Enhanced Motor Control System...")
    print("=" * 50)
    
    try:
        # Load MQTT credentials
        credentials = load_mqtt_credentials()
        if not credentials:
            print("❌ Failed to load MQTT credentials. Exiting...")
            return False
        
        # Setup MQTT client
        if not setup_mqtt_client(credentials):
            print("❌ Failed to setup MQTT client. Exiting...")
            return False
        
        # Connect to MQTT
        if not connect_mqtt(credentials):
            print("❌ Failed to connect to MQTT. Exiting...")
            return False
        
        # Start ultrasonic sensor process
        print("📡 Starting ultrasonic sensor monitoring...")
        ultrasonic_process = multiprocessing.Process(target=measure_distance, args=(shared_distances,))
        ultrasonic_process.start()
        
        # Start obstacle monitoring process
        print("👁️ Starting obstacle monitoring...")
        obstacle_process = multiprocessing.Process(target=monitor_obstacles)
        obstacle_process.start()
        
        # Start credentials monitoring thread
        credentials_thread = threading.Thread(target=monitor_credentials_file, daemon=True)
        credentials_thread.start()
        
        print("✅ All systems operational!")
        print("🎮 Robot is ready for control commands")
        print("🔗 Connection status will be managed by main system")
        print("Press Ctrl+C to shutdown...")
        
        # Main loop - keep the system running
        while system_running:
            try:
                # Periodic status check
                status = "🟢 Active" if connection_active else "🟡 Standby"
                if time.time() % 30 < 1:  # Print status every 30 seconds
                    print(f"📊 System Status: {status}")
                
                time.sleep(1)
                
            except KeyboardInterrupt:
                print("\n🛑 Shutdown requested by user")
                break
            except Exception as e:
                print(f"⚠️ Error in main loop: {e}")
                time.sleep(5)
        
        return True
        
    except Exception as e:
        print(f"💥 Critical error in motor control system: {e}")
        return False
    
    finally:
        cleanup_and_exit()

if __name__ == "__main__":
    try:
        success = main()
        if not success:
            print("❌ Motor control system failed to start properly")
            sys.exit(1)
    except Exception as e:
        print(f"💥 Unexpected error: {e}")
        cleanup_and_exit()