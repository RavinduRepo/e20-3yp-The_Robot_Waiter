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
import signal
from getpass import getpass

# Configuration file paths
CONFIG_FILE = "robot_config.json"
WEBSOCKET_DATA_FILE = "websocket_data.json"
MQTT_LOG_FILE = "mqtt_data_log.json"
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"
SERVER_CONFIG_FILE = "server_config.json"
PROCESS_STATE_FILE = "robot_process_state.json"

# Global variables for process management
robot_processes = {}
connection_state = {"connected": False, "last_credentials": None}

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

def save_process_state(state):
    """Save current process state to file"""
    try:
        with open(PROCESS_STATE_FILE, "w") as file:
            json.dump(state, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving process state: {e}")
        return False

def load_process_state():
    """Load process state from file"""
    try:
        if os.path.exists(PROCESS_STATE_FILE):
            with open(PROCESS_STATE_FILE, "r") as file:
                return json.load(file)
        return {"connected": False, "last_credentials": None}
    except Exception as e:
        print(f"Error loading process state: {e}")
        return {"connected": False, "last_credentials": None}

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
        return credentials
    except Exception as e:
        print(f"✗ Error extracting MQTT credentials: {e}")
        return None

def stop_robot_processes():
    """Stop all robot-related processes"""
    global robot_processes
    
    print("🛑 Stopping all robot processes...")
    
    stopped_processes = []
    
    for process_name, process in robot_processes.items():
        try:
            if process and process.poll() is None:  # Process is still running
                print(f"🔄 Stopping {process_name}...")
                process.terminate()
                
                # Wait up to 5 seconds for graceful termination
                try:
                    process.wait(timeout=5)
                    stopped_processes.append(process_name)
                    print(f"✅ {process_name} stopped gracefully")
                except subprocess.TimeoutExpired:
                    # Force kill if necessary
                    process.kill()
                    process.wait()
                    stopped_processes.append(process_name)
                    print(f"⚡ {process_name} force-killed")
            else:
                print(f"ℹ️ {process_name} was not running")
                
        except Exception as e:
            print(f"❌ Error stopping {process_name}: {e}")
    
    # Clear the process dictionary
    robot_processes.clear()
    
    # Update connection state
    connection_state["connected"] = False
    save_process_state(connection_state)
    
    print(f"🏁 Stopped processes: {', '.join(stopped_processes) if stopped_processes else 'None'}")
    return len(stopped_processes) > 0

def start_robot_control():
    """Start the robot control script"""
    global robot_processes
    
    try:
        print("🤖 Starting robot control script...")
        
        # Start the motor control script
        motor_process = subprocess.Popen([sys.executable, "motor_thread.py"])
        robot_processes["motor_thread"] = motor_process
        
        print("✅ Robot control script started successfully")
        
        # Update connection state
        connection_state["connected"] = True
        save_process_state(connection_state)
        
        return True
        
    except Exception as e:
        print(f"❌ Failed to start robot control script: {e}")
        return False

def handle_connect_message(data, robot_id):
    """Handle connect-type MQTT message"""
    print("🔌 Processing CONNECT message...")
    
    # Stop any existing processes first
    stop_robot_processes()
    
    # Store data and extract credentials
    if store_data_locally(data):
        credentials = extract_mqtt_credentials(data, robot_id)
        if credentials:
            connection_state["last_credentials"] = credentials
            save_process_state(connection_state)
            
            # Start robot control
            if start_robot_control():
                print("🎉 Robot connected and control active!")
                return True
            else:
                print("⚠️ Failed to start robot control")
                return False
        else:
            print("❌ Failed to extract MQTT credentials")
            return False
    else:
        print("❌ Failed to store WebSocket data")
        return False

def handle_disconnect_message(data, robot_id):
    """Handle disconnect-type MQTT message"""
    print("🔌 Processing DISCONNECT message...")
    
    # Stop all robot processes
    if stop_robot_processes():
        print("✅ Robot disconnected successfully - all processes stopped")
    else:
        print("ℹ️ Robot disconnect complete - no active processes found")
    
    return True

def handle_reconnect_message(data, robot_id):
    """Handle reconnect-type MQTT message"""
    print("🔄 Processing RECONNECT message...")
    
    # Load last known credentials
    last_credentials = connection_state.get("last_credentials")
    
    if not last_credentials:
        print("❌ No previous credentials found - cannot reconnect")
        return False
    
    print(f"📋 Using last known credentials from {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(last_credentials['extracted_at']))}")
    
    # Stop any existing processes first
    stop_robot_processes()
    
    # Use existing credentials without re-extracting
    if start_robot_control():
        print("🎉 Robot reconnected successfully using existing credentials!")
        return True
    else:
        print("❌ Failed to reconnect robot control")
        return False

def get_data_locally():
    """Retrieve locally stored WebSocket data"""
    try:
        if os.path.exists(WEBSOCKET_DATA_FILE):
            with open(WEBSOCKET_DATA_FILE, "r") as file:
                return json.load(file)
        else:
            print("No local WebSocket data found")
            return None
    except Exception as e:
        print(f"Error retrieving WebSocket data locally: {e}")
        return None

def wait_for_mqtt_message(driver, robot_id, timeout=18000):
    """Event-driven wait for MQTT authentication message with disconnect/reconnect support."""
    print(f"🔄 Waiting for MQTT messages for robot {robot_id}...")
    print(f"⏰ Timeout set to {timeout//3600} hours")

    from threading import Event, Thread
    import time

    result = {"data": None, "continue_monitoring": True}
    done = Event()

    def watch_local_storage():
        check_count = 0
        last_processed_data = None
        
        while not done.is_set() and result["continue_monitoring"]:
            try:
                websocket_data = driver.execute_script("return localStorage.getItem('webSocketData');")

                if websocket_data:
                    data = json.loads(websocket_data)
                    
                    # Skip if we've already processed this exact message
                    if data == last_processed_data:
                        time.sleep(2)
                        continue
                    
                    message_type = data.get("type", "").lower()
                    
                    if message_type == "connect" and data.get("user") and data["user"].get("token"):
                        print(f"\n📨 CONNECT message received: {data}")
                        last_processed_data = data
                        
                        if handle_connect_message(data, robot_id):
                            result["data"] = data
                        
                    elif message_type == "disconnect":
                        print(f"\n📨 DISCONNECT message received: {data}")
                        last_processed_data = data
                        
                        handle_disconnect_message(data, robot_id)
                        # Continue monitoring for reconnect
                        
                    elif message_type == "reconnect":
                        print(f"\n📨 RECONNECT message received: {data}")
                        last_processed_data = data
                        
                        if handle_reconnect_message(data, robot_id):
                            result["data"] = data

                check_count += 1
                if check_count % 15 == 0:
                    elapsed = int(time.time() - start_time)
                    remaining = timeout - elapsed
                    print(f"⏳ Monitoring... {elapsed//60}m elapsed, {remaining//60}m remaining")
                time.sleep(2)

            except Exception as e:
                print(f"\n⚠️ Error checking for MQTT message: {e}")
                time.sleep(5)

    start_time = time.time()
    thread = Thread(target=watch_local_storage)
    thread.start()

    # Don't timeout - keep monitoring indefinitely
    try:
        while result["continue_monitoring"]:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n🛑 Monitoring interrupted by user")
        result["continue_monitoring"] = False
        done.set()

    thread.join()
    return result["data"]

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

def main_robot_process():
    """Main robot process that handles login and MQTT monitoring"""
    global connection_state
    driver = None
    
    try:
        # Load process state
        connection_state = load_process_state()
        
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
        driver = setup_webdriver()
        
        # Perform login
        if not perform_login(driver, robot_id, password):
            print("❌ Login failed. Check credentials and try again.")
            return False
        
        # Wait for WebSocket connection
        time.sleep(3)
        
        # Check WebSocket connection
        max_websocket_retries = 5
        websocket_ready = False
        
        for attempt in range(max_websocket_retries):
            if check_websocket_connection(driver):
                websocket_ready = True
                break
            else:
                print(f"🔄 WebSocket not ready, attempt {attempt + 1}/{max_websocket_retries}")
                time.sleep(2)
        
        if not websocket_ready:
            print("❌ WebSocket connection failed after multiple attempts")
            return False
        
        # Start continuous MQTT message monitoring
        print("\n📡 Starting continuous MQTT message monitoring...")
        print("🔄 Monitoring for CONNECT, DISCONNECT, and RECONNECT messages...")
        print("Press Ctrl+C to exit...")
        
        mqtt_data = wait_for_mqtt_message(driver, robot_id)
        
        if mqtt_data:
            print("\n🎉 MQTT monitoring session completed!")
        else:
            print("🛑 MQTT monitoring ended without receiving initial message")
            
        return True
            
    except Exception as e:
        print(f"❌ Critical error in main process: {e}")
        traceback.print_exc()
        return False
        
    finally:
        # Cleanup: stop all processes and close browser
        print("\n🧹 Performing cleanup...")
        stop_robot_processes()
        
        if driver:
            print("🔒 Closing browser...")
            try:
                driver.quit()
            except:
                pass

def signal_handler(sig, frame):
    """Handle shutdown signals gracefully"""
    print(f"\n🛑 Received signal {sig}, shutting down gracefully...")
    stop_robot_processes()
    sys.exit(0)

def main():
    """Main function with auto-restart capability"""
    global connection_state
    
    # Setup signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    max_retries = 3
    retry_count = 0
    
    print("🤖 Robot MQTT Monitor Starting...")
    print(f"📁 Config file: {CONFIG_FILE}")
    print(f"📁 Data files: {WEBSOCKET_DATA_FILE}, {MQTT_LOG_FILE}")
    print(f"📁 Robot credentials file: {ROBOT_CREDENTIALS_FILE}")
    print(f"📁 Process state file: {PROCESS_STATE_FILE}")
    
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
            stop_robot_processes()
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
    
    print("🏁 Robot MQTT Monitor finished")

if __name__ == "__main__":
    main()