#!/usr/bin/env python3
# robot_process_manager.py - Helper script to manage robot processes

import json
import os
import subprocess
import time
import signal
import psutil
import sys

PROCESS_STATE_FILE = "robot_process_state.json"
MQTT_LOG_FILE = "mqtt_data_log.json"
ROBOT_CREDENTIALS_FILE = "robot_mqtt_credentials.json"

def load_process_state():
    """Load current process state"""
    try:
        if os.path.exists(PROCESS_STATE_FILE):
            with open(PROCESS_STATE_FILE, "r") as file:
                return json.load(file)
        return {"connected": False, "last_credentials": None}
    except Exception as e:
        print(f"Error loading process state: {e}")
        return {"connected": False, "last_credentials": None}

def find_robot_processes():
    """Find all running robot-related processes"""
    robot_processes = []
    
    for proc in psutil.process_iter(['pid', 'name', 'cmdline']):
        try:
            cmdline = ' '.join(proc.info['cmdline']) if proc.info['cmdline'] else ''
            
            if any(script in cmdline for script in [
                'robot_login_and_listen2.py',
                'motor_thread.py', 
                'ultrasonic_thread2.py',
                'robot_process_manager.py'
            ]):
                robot_processes.append({
                    'pid': proc.info['pid'],
                    'name': proc.info['name'],
                    'cmdline': cmdline
                })
        except (psutil.NoSuchProcess, psutil.AccessDenied):
            continue
    
    return robot_processes

def stop_all_robot_processes():
    """Stop all robot-related processes"""
    processes = find_robot_processes()
    stopped_count = 0
    
    print(f"Found {len(processes)} robot processes")
    
    for proc in processes:
        # Don't kill the process manager itself
        if 'robot_process_manager.py' in proc['cmdline']:
            continue
            
        try:
            pid = proc['pid']
            print(f"Stopping process {pid}: {proc['name']}")
            
            # Try graceful termination first
            os.kill(pid, signal.SIGTERM)
            time.sleep(2)
            
            # Check if process is still running
            if psutil.pid_exists(pid):
                print(f"Force killing process {pid}")
                os.kill(pid, signal.SIGKILL)
            
            stopped_count += 1
            print(f"✅ Stopped process {pid}")
            
        except (OSError, psutil.NoSuchProcess) as e:
            print(f"⚠️ Error stopping process {proc['pid']}: {e}")
    
    print(f"🏁 Stopped {stopped_count} processes")
    return stopped_count

def show_status():
    """Show current robot system status"""
    print("\n" + "="*60)
    print("🤖 ROBOT SYSTEM STATUS")
    print("="*60)
    
    # Process state
    state = load_process_state()
    print(f"Connection Status: {'🟢 Connected' if state['connected'] else '🔴 Disconnected'}")
    
    if state['last_credentials']:
        creds = state['last_credentials']
        extracted_time = time.strftime('%Y-%m-%d %H:%M:%S', 
                                     time.localtime(creds.get('extracted_at', 0)))
        print(f"Last Credentials: {extracted_time}")
        print(f"Robot ID: {creds.get('robotId', 'Unknown')}")
        print(f"Topic: {creds.get('topic', 'Unknown')}")
    
    # File status
    print(f"\n📁 FILE STATUS:")
    files_to_check = [
        ("Config", "robot_config.json"),
        ("MQTT Log", MQTT_LOG_FILE), 
        ("Credentials", ROBOT_CREDENTIALS_FILE),
        ("Process State", PROCESS_STATE_FILE),
        ("Server Config", "server_config.json")
    ]
    
    for name, filename in files_to_check:
        exists = "✅" if os.path.exists(filename) else "❌"
        size = f"({os.path.getsize(filename)} bytes)" if os.path.exists(filename) else ""
        print(f"  {name}: {exists} {filename} {size}")
    
    # Running processes
    processes = find_robot_processes()
    print(f"\n🔄 RUNNING PROCESSES ({len(processes)}):")
    
    if processes:
        for proc in processes:
            script_name = "Unknown"
            for script in ['robot_login_and_listen2.py', 'motor_thread.py', 'ultrasonic_thread2.py', 'robot_process_manager.py']:
                if script in proc['cmdline']:
                    script_name = script
                    break
            print(f"  PID {proc['pid']}: {script_name}")
    else:
        print("  No robot processes running")
    
    print("="*60)

def cleanup_files():
    """Clean up temporary files"""
    files_to_clean = [
        WEBSOCKET_DATA_FILE,
        MQTT_LOG_FILE,
        PROCESS_STATE_FILE,
        ROBOT_CREDENTIALS_FILE
    ]
    
    cleaned_count = 0
    for filename in files_to_clean:
        try:
            if os.path.exists(filename):
                os.remove(filename)
                print(f"🗑️ Removed {filename}")
                cleaned_count += 1
        except Exception as e:
            print(f"⚠️ Error removing {filename}: {e}")
    
    print(f"🧹 Cleaned up {cleaned_count} files")

def test_sensors():
    """Test ultrasonic sensors"""
    print("🧪 Testing ultrasonic sensors...")
    try:
        result = subprocess.run([sys.executable, "ultrasonic_thread2.py", "test"], 
                              capture_output=True, text=True, timeout=30)
        print(result.stdout)
        if result.stderr:
            print("Errors:", result.stderr)
        return result.returncode == 0
    except subprocess.TimeoutExpired:
        print("❌ Sensor test timed out")
        return False
    except Exception as e:
        print(f"❌ Error testing sensors: {e}")
        return False

def main():
    """Main menu function"""
    while True:
        print("\n🤖 ROBOT PROCESS MANAGER")
        print("="*40)
        print("1. Show Status")
        print("2. Stop All Processes")
        print("3. Test Sensors")
        print("4. Cleanup Files")
        print("5. Start Main Robot System")
        print("6. View Recent MQTT Data")
        print("0. Exit")
        
        try:
            choice = input("\nSelect option (0-6): ").strip()
            
            if choice == "0":
                print("👋 Goodbye!")
                break
                
            elif choice == "1":
                show_status()
                
            elif choice == "2":
                confirm = input("⚠️ Stop all robot processes? (y/N): ").lower()
                if confirm in ['y', 'yes']:
                    stop_all_robot_processes()
                else:
                    print("Operation cancelled")
                    
            elif choice == "3":
                test_sensors()
                
            elif choice == "4":
                confirm = input("⚠️ Delete temporary files? (y/N): ").lower()
                if confirm in ['y', 'yes']:
                    cleanup_files()
                else:
                    print("Operation cancelled")
                    
            elif choice == "5":
                print("🚀 Starting robot system...")
                subprocess.Popen([sys.executable, "robot_login_and_listen2.py"])
                print("✅ Robot system started in background")
                
            elif choice == "6":
                if os.path.exists(MQTT_LOG_FILE):
                    try:
                        with open(MQTT_LOG_FILE, "r") as f:
                            data = json.load(f)
                        print("\n📊 RECENT MQTT DATA:")
                        print(json.dumps(data, indent=2))
                    except Exception as e:
                        print(f"❌ Error reading MQTT data: {e}")
                else:
                    print("❌ No MQTT data file found")
                    
            else:
                print("❌ Invalid option")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")

if __name__ == "__main__":
    main()