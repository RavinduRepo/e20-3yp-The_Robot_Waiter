# robot_login_and_listen2.py
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
import time
import json
import os
import threading
import sys
import traceback
import subprocess
from getpass import getpass
import signal

# Configuration file paths
CONFIG_FILE = "robot_config.json"
WEBSOCKET_DATA_FILE = "websocket_data.json" 
MQTT_LOG_FILE = "mqtt_data_log.json"
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"
SERVER_CONFIG_FILE = "server_config.json"
CONNECTION_STATE_FILE = "connection_state.json"

# Global variables for state management
current_driver = None
robot_control_process = None
monitoring_active = False
connection_state = {
    "status": "disconnected",  # disconnected, connected, waiting
    "last_connect_time": None,
    "last_disconnect_time": None,
    "reconnect_count": 0
}

def load_robot_config():
    """Load robot credentials from config file"""
    try:
        if os.path.exists(CONFIG_FILE):
            with open(CONFIG_FILE, "r") as file:
                config = json.load(file)
                print(f"Loaded configuration for Robot ID: {config.get('robotId', 'Unknown')}")
                return config
        else:
            print("No configuration file found.")
            return None
    except Exception as e:
        print(f"Error loading configuration: {e}")
        return None

def save_robot_config(robot_id, password):
    """Save robot credentials to config file"""
    try:
        config = {
            "robotId": robot_id,
            "password": password,
            "lastUpdated": time.time()
        }
        with open(CONFIG_FILE, "w") as file:
            json.dump(config, file, indent=2)
        print(f"Configuration saved for Robot ID: {robot_id}")
        return True
    except Exception as e:
        print(f"Error saving configuration: {e}")
        return False

def save_connection_state():
    """Save current connection state to file"""
    try:
        with open(CONNECTION_STATE_FILE, "w") as file:
            json.dump(connection_state, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving connection state: {e}")
        return False

def load_connection_state():
    """Load connection state from file"""
    global connection_state
    try:
        if os.path.exists(CONNECTION_STATE_FILE):
            with open(CONNECTION_STATE_FILE, "r") as file:
                connection_state = json.load(file)
                print(f"Loaded connection state: {connection_state['status']}")
        return True
    except Exception as e:
        print(f"Error loading connection state: {e}")
        return False

def get_user_credentials():
    """Get robot credentials from user input"""
    print("\n" + "="*50)
    print("ROBOT CREDENTIALS SETUP")
    print("="*50)
    
    robot_id = input("Enter Robot ID: ").strip()
    if not robot_id:
        print("Robot ID cannot be empty!")
        return None, None
    
    password = getpass("Enter Robot Password: ").strip()
    if not password:
        print("Password cannot be empty!")
        return None, None
    
    # Ask if user wants to save credentials
    save_choice = input("Save credentials for future use? (y/n): ").lower().strip()
    if save_choice in ['y', 'yes']:
        if save_robot_config(robot_id, password):
            print("Credentials saved successfully!")
        else:
            print("Failed to save credentials, but continuing...")
    
    return robot_id, password

def store_data_locally(data):
    """Store WebSocket/MQTT data locally"""
    try:
        # Store both in JSON file and a more persistent log
        with open(WEBSOCKET_DATA_FILE, "w") as file:
            json.dump(data, file, indent=2)
        
        # Write to log file with timestamp
        with open(MQTT_LOG_FILE, "w") as log_file:
            log_entry = {
                "timestamp": time.time(),
                "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
                "data": data
            }
            log_file.write(json.dumps(log_entry) + "\n")
        
        print(f"✓ WebSocket data stored: {data}")
        return True
    except Exception as e:
        print(f"✗ Error storing WebSocket data locally: {e}")
        return False

def extract_mqtt_credentials(data, robot_id):
    """Extract MQTT credentials from WebSocket data and save for robot control"""
    try:
        credentials = {
            "robotId": robot_id,
            "token": data.get("user", {}).get("token"),
            "timestamp": data.get("timestamp"),
            "topic": data.get("user", {}).get("topic"),
            "extracted_at": time.time()
        }
        
        with open(ROBOT_CREDENTIALS_FILE, "w") as file:
            json.dump(credentials, file, indent=2)
        
        print(f"✓ MQTT credentials extracted and saved to {ROBOT_CREDENTIALS_FILE}")
        return True
    except Exception as e:
        print(f"✗ Error extracting MQTT credentials: {e}")
        return False

def start_robot_control():
    """Start the robot control script"""
    global robot_control_process
    try:
        print("🤖 Starting robot control script...")
        # Terminate existing process if running
        if robot_control_process and robot_control_process.poll() is None:
            print("🔄 Terminating existing robot control process...")
            robot_control_process.terminate()
            time.sleep(2)
        
        # Start new robot control script as a subprocess
        robot_control_process = subprocess.Popen([sys.executable, "motor_thread.py"])
        print("✅ Robot control script started successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to start robot control script: {e}")
        return False

def stop_robot_control():
    """Stop the robot control script"""
    global robot_control_process
    try:
        if robot_control_process and robot_control_process.poll() is None:
            print("🛑 Stopping robot control script...")
            robot_control_process.terminate()
            time.sleep(2)
            if robot_control_process.poll() is None:
                robot_control_process.kill()
            print("✅ Robot control script stopped")
            return True
        else:
            print("ℹ️ Robot control script was not running")
            return True
    except Exception as e:
        print(f"❌ Failed to stop robot control script: {e}")
        return False

def handle_connect_message(data, robot_id):
    """Handle MQTT connect message"""
    global connection_state
    print("🔗 Handling CONNECT message...")
    
    connection_state["status"] = "connected"
    connection_state["last_connect_time"] = time.time()
    save_connection_state()
    
    if store_data_locally(data):
        if extract_mqtt_credentials(data, robot_id):
            print("🔑 MQTT credentials prepared for robot control")
            if start_robot_control():
                print("🤖 Robot control is now active!")
                return True
            else:
                print("⚠️ Failed to start robot control, but credentials are saved")
                return False
    return False

def handle_disconnect_message(data):
    """Handle MQTT disconnect message"""
    global connection_state
    print("🔌 Handling DISCONNECT message...")
    
    connection_state["status"] = "waiting"
    connection_state["last_disconnect_time"] = time.time()
    save_connection_state()
    
    # Stop robot control
    stop_robot_control()
    print("🔄 Robot disconnected. Waiting for new connection...")
    return True

def handle_reconnect_message(data, robot_id):
    """Handle MQTT reconnect message"""
    global connection_state
    print("🔄 Handling RECONNECT message...")
    
    connection_state["reconnect_count"] += 1
    save_connection_state()
    
    # Stop current robot control
    stop_robot_control()
    time.sleep(1)
    
    # Restart with existing credentials
    if extract_mqtt_credentials(data, robot_id):
        if start_robot_control():
            print("🤖 Robot reconnected successfully!")
            connection_state["status"] = "connected"
            connection_state["last_connect_time"] = time.time()
            save_connection_state()
            return True
    
    print("❌ Failed to reconnect robot")
    return False

def process_websocket_message(data, robot_id):
    """Process different types of WebSocket messages"""
    message_type = data.get("type", "").lower()
    
    if message_type == "connect":
        return handle_connect_message(data, robot_id)
    elif message_type == "disconnect":
        return handle_disconnect_message(data)
    elif message_type == "reconnect":
        return handle_reconnect_message(data, robot_id)
    else:
        print(f"❓ Unknown message type: {message_type}")
        return False

def wait_for_mqtt_message(driver, robot_id, timeout=18000):
    """Event-driven wait for MQTT messages with enhanced handling"""
    global monitoring_active
    print(f"🔄 Starting MQTT message monitoring for robot {robot_id}...")
    print(f"⏰ Timeout set to {timeout//3600} hours")

    monitoring_active = True
    check_count = 0
    start_time = time.time()
    last_message = None

    while monitoring_active and (time.time() - start_time) < timeout:
        try:
            websocket_data = driver.execute_script("return localStorage.getItem('webSocketData');")

            if websocket_data:
                data = json.loads(websocket_data)
                
                # Check if this is a new message
                if data != last_message:
                    last_message = data
                    print(f"\n📨 WebSocket message received: {data}")
                    
                    # Process the message based on type
                    if process_websocket_message(data, robot_id):
                        print("✅ Message processed successfully")
                    else:
                        print("⚠️ Message processing had issues")

            check_count += 1
            if check_count % 15 == 0:
                elapsed = int(time.time() - start_time)
                remaining = timeout - elapsed
                status = connection_state.get("status", "unknown")
                print(f"⏳ Status: {status} | {elapsed//60}m elapsed, {remaining//60}m remaining")
            
            time.sleep(2)

        except Exception as e:
            print(f"\n⚠️ Error checking for MQTT message: {e}")
            time.sleep(5)

    if not monitoring_active:
        print("\n🛑 Monitoring stopped by user request")
    else:
        print(f"\n⏰ Timeout: No new messages within {timeout//3600} hours")

def setup_webdriver():
    """Setup and return Chrome WebDriver for Raspberry Pi"""
    try:
        chrome_options = ChromeOptions()
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-web-security")
        chrome_options.add_argument("--allow-running-insecure-content")
        chrome_options.add_argument("--disable-extensions")
        chrome_options.add_argument("--disable-background-timer-throttling")
        chrome_options.add_argument("--disable-backgrounding-occluded-windows")
        chrome_options.add_argument("--disable-renderer-backgrounding")
        
        # Uncomment for headless mode (recommended for Raspberry Pi)
        # chrome_options.add_argument("--headless")
        
        # Use system-installed chromedriver
        service = ChromeService("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        return driver
    except Exception as e:
        print(f"❌ Failed to setup WebDriver: {e}")
        raise

def load_server_config():
    """Load server configuration from file"""
    try:
        if os.path.exists(SERVER_CONFIG_FILE):
            with open(SERVER_CONFIG_FILE, "r") as file:
                config = json.load(file)
                server_ip = config.get("serverIp")
                if server_ip:
                    print(f"Loaded server IP: {server_ip}")
                    return server_ip
                else:
                    print("Server IP not found in configuration file.")
                    return None
        else:
            print("No server configuration file found.")
            return None
    except Exception as e:
        print(f"Error loading server configuration: {e}")
        return None

def perform_login(driver, robot_id, password):
    """Perform robot login"""
    try:
        server_ip = load_server_config()
        if not server_ip:
            print("❌ Server IP not configured. Exiting...")
            return False

        print("🌐 Navigating to login page...")
        driver.get(f"http://{server_ip}:5001/robot-login")
        time.sleep(3)

        print("🔍 Finding login elements...")
        robot_id_input = driver.find_element(By.XPATH, "//input[@placeholder='Robot ID']")
        robot_id_input.clear()
        robot_id_input.send_keys(robot_id)

        password_input = driver.find_element(By.XPATH, "//input[@placeholder='Password']")
        password_input.clear()
        password_input.send_keys(password)

        print("📝 Submitting login form...")
        password_input.send_keys(Keys.RETURN)
        time.sleep(5)

        current_url = driver.current_url
        print(f"📍 Current URL after login: {current_url}")
        
        return True
        
    except Exception as e:
        print(f"❌ Login failed: {e}")
        return False

def check_websocket_connection(driver):
    """Check WebSocket connection status"""
    try:
        websocket_status = driver.execute_script("""
            return window.webSocketManager ? 
                   (window.webSocketManager.ws ? window.webSocketManager.ws.readyState : 'No WebSocket') : 
                   'No WebSocketManager';
        """)
        
        print(f"🔌 WebSocket status: {websocket_status}")
        
        if websocket_status == 1:  # WebSocket.OPEN
            print("✅ WebSocket connection established successfully!")
            return True
        else:
            print("⚠️ WebSocket connection not ready")
            return False
            
    except Exception as e:
        print(f"❌ Error checking WebSocket status: {e}")
        return False

def signal_handler(signum, frame):
    """Handle Ctrl+C gracefully"""
    global monitoring_active
    print(f"\n🛑 Received signal {signum}. Shutting down gracefully...")
    monitoring_active = False
    stop_robot_control()
    sys.exit(0)

def main_robot_process():
    """Main robot process that handles login and MQTT monitoring"""
    global current_driver, monitoring_active
    
    # Setup signal handlers
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load connection state
        load_connection_state()
        
        # Load or get robot credentials
        config = load_robot_config()
        
        if config and config.get('robotId') and config.get('password'):
            robot_id = config['robotId']
            password = config['password']
            print(f"✅ Using saved credentials for Robot ID: {robot_id}")
        else:
            print("🔧 No valid configuration found. Setting up new credentials...")
            robot_id, password = get_user_credentials()
            
            if not robot_id or not password:
                print("❌ Invalid credentials provided. Exiting...")
                return False

        print(f"\n🚀 Starting robot monitoring process for: {robot_id}")
        print("=" * 60)
        
        # Setup WebDriver
        current_driver = setup_webdriver()
        
        # Perform login
        if not perform_login(current_driver, robot_id, password):
            print("❌ Login failed. Check credentials and try again.")
            return False
        
        # Wait for WebSocket connection
        time.sleep(3)
        
        # Check WebSocket connection
        max_websocket_retries = 5
        websocket_ready = False
        
        for attempt in range(max_websocket_retries):
            if check_websocket_connection(current_driver):
                websocket_ready = True
                break
            else:
                print(f"🔄 WebSocket not ready, attempt {attempt + 1}/{max_websocket_retries}")
                time.sleep(2)
        
        if not websocket_ready:
            print("❌ WebSocket connection failed after multiple attempts")
            return False
        
        # Set initial state
        connection_state["status"] = "waiting"
        save_connection_state()
        
        # Start continuous MQTT message monitoring
        print("\n📡 Starting continuous MQTT message monitoring...")
        print("System will handle connect/disconnect/reconnect messages automatically")
        print("Press Ctrl+C to exit...")
        
        # Continuous monitoring loop
        wait_for_mqtt_message(current_driver, robot_id)
        
        return True
            
    except Exception as e:
        print(f"❌ Critical error in main process: {e}")
        traceback.print_exc()
        return False
        
    finally:
        monitoring_active = False
        stop_robot_control()
        if current_driver:
            print("🔒 Closing browser...")
            try:
                current_driver.quit()
            except:
                pass

def main():
    """Main function with auto-restart capability"""
    max_retries = 3
    retry_count = 0
    
    print("🤖 Enhanced Robot MQTT Monitor Starting...")
    print(f"📁 Config file: {CONFIG_FILE}")
    print(f"📁 Data files: {WEBSOCKET_DATA_FILE}, {MQTT_LOG_FILE}")
    print(f"📁 Robot credentials file: {ROBOT_CREDENTIALS_FILE}")
    print(f"📁 Connection state file: {CONNECTION_STATE_FILE}")
    
    while retry_count < max_retries:
        try:
            print(f"\n🔄 Attempt {retry_count + 1}/{max_retries}")
            
            success = main_robot_process()
            
            if success:
                print("✅ Process completed successfully!")
                break
            else:
                retry_count += 1
                if retry_count < max_retries:
                    wait_time = 10 * retry_count
                    print(f"⏳ Waiting {wait_time} seconds before retry...")
                    time.sleep(wait_time)
                
        except KeyboardInterrupt:
            print("\n🛑 Process interrupted by user")
            break
        except Exception as e:
            print(f"💥 Unexpected error: {e}")
            traceback.print_exc()
            retry_count += 1
            
            if retry_count < max_retries:
                wait_time = 15 * retry_count
                print(f"⏳ Waiting {wait_time} seconds before retry...")
                time.sleep(wait_time)
    
    if retry_count >= max_retries:
        print(f"❌ Process failed after {max_retries} attempts")
        sys.exit(1)
    
    print("🏁 Enhanced Robot MQTT Monitor finished")

if __name__ == "__main__":
    main()