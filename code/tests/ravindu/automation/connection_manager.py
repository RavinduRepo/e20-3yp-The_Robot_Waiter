# connection_manager.py
import json
import time
import os
import sys

CONNECTION_STATE_FILE = "connection_state.json"
MQTT_LOG_FILE = "mqtt_data_log.json"

def load_connection_state():
    """Load current connection state"""
    try:
        if os.path.exists(CONNECTION_STATE_FILE):
            with open(CONNECTION_STATE_FILE, "r") as file:
                return json.load(file)
        else:
            return {"status": "unknown", "message": "State file not found"}
    except Exception as e:
        return {"status": "error", "message": f"Error loading state: {e}"}

def save_connection_state(state):
    """Save connection state"""
    try:
        with open(CONNECTION_STATE_FILE, "w") as file:
            json.dump(state, file, indent=2)
        return True
    except Exception as e:
        print(f"Error saving state: {e}")
        return False

def get_system_status():
    """Get comprehensive system status"""
    state = load_connection_state()
    
    print("🤖 ROBOT SYSTEM STATUS")
    print("=" * 40)
    
    # Connection status
    status = state.get("status", "unknown")
    status_icons = {
        "connected": "🟢",
        "disconnected": "🔴", 
        "waiting": "🟡",
        "unknown": "⚪"
    }
    
    print(f"Connection Status: {status_icons.get(status, '❓')} {status.upper()}")
    
    # Timestamps
    if state.get("last_connect_time"):
        connect_time = time.strftime("%Y-%m-%d %H:%M:%S", 
                                   time.localtime(state["last_connect_time"]))
        print(f"Last Connect: {connect_time}")
    
    if state.get("last_disconnect_time"):
        disconnect_time = time.strftime("%Y-%m-%d %H:%M:%S", 
                                      time.localtime(state["last_disconnect_time"]))
        print(f"Last Disconnect: {disconnect_time}")
    
    if state.get("reconnect_count"):
        print(f"Reconnect Count: {state['reconnect_count']}")
    
    # File status
    print("\n📁 FILE STATUS")
    print("-" * 20)
    
    files_to_check = [
        ("Config", "robot_config.json"),
        ("MQTT Data", MQTT_LOG_FILE),
        ("WebSocket Data", "websocket_data.json"),
        ("Robot Credentials", "robot_mqtt_credentials.json"),
        ("Server Config", "server_config.json"),
        ("Connection State", CONNECTION_STATE_FILE)
    ]
    
    for name, filename in files_to_check:
        if os.path.exists(filename):
            size = os.path.getsize(filename)
            modified = time.strftime("%H:%M:%S", 
                                   time.localtime(os.path.getmtime(filename)))
            print(f"{name}: ✅ ({size} bytes, modified {modified})")
        else:
            print(f"{name}: ❌ Missing")

def reset_connection_state():
    """Reset connection state to initial values"""
    initial_state = {
        "status": "disconnected",
        "last_connect_time": None,
        "last_disconnect_time": time.time(),
        "reconnect_count": 0
    }
    
    if save_connection_state(initial_state):
        print("✅ Connection state reset successfully")
        return True
    else:
        print("❌ Failed to reset connection state")
        return False

def simulate_disconnect():
    """Simulate a disconnect message for testing"""
    disconnect_message = {
        "type": "disconnect",
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "user": {"test": True}
    }
    
    try:
        log_entry = {
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "data": disconnect_message
        }
        
        with open(MQTT_LOG_FILE, "w") as file:
            json.dump(log_entry, file, indent=2)
        
        print("✅ Disconnect message simulated")
        print(f"📝 Written to {MQTT_LOG_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to simulate disconnect: {e}")
        return False

def simulate_reconnect():
    """Simulate a reconnect message for testing"""
    reconnect_message = {
        "type": "reconnect", 
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S.%fZ", time.gmtime()),
        "user": {"test": True}
    }
    
    try:
        log_entry = {
            "timestamp": time.time(),
            "formatted_time": time.strftime("%Y-%m-%d %H:%M:%S", time.localtime()),
            "data": reconnect_message
        }
        
        with open(MQTT_LOG_FILE, "w") as file:
            json.dump(log_entry, file, indent=2)
        
        print("✅ Reconnect message simulated")
        print(f"📝 Written to {MQTT_LOG_FILE}")
        return True
        
    except Exception as e:
        print(f"❌ Failed to simulate reconnect: {e}")
        return False

def show_menu():
    """Display main menu"""
    print("\n🛠️ CONNECTION MANAGER MENU")
    print("=" * 30)
    print("1. Show System Status")
    print("2. Reset Connection State")
    print("3. Simulate Disconnect")
    print("4. Simulate Reconnect") 
    print("5. Monitor Status (Real-time)")
    print("0. Exit")
    print("-" * 30)

def monitor_status():
    """Monitor system status in real-time"""
    print("🔄 Real-time status monitoring (Press Ctrl+C to stop)")
    print("=" * 50)
    
    try:
        while True:
            # Clear screen (works on most terminals)
            os.system('clear' if os.name == 'posix' else 'cls')
            
            print("🔄 REAL-TIME SYSTEM MONITOR")
            print("=" * 40)
            print(f"Updated: {time.strftime('%Y-%m-%d %H:%M:%S')}")
            print()
            
            get_system_status()
            
            print("\nPress Ctrl+C to exit monitoring...")
            time.sleep(5)
            
    except KeyboardInterrupt:
        print("\n🛑 Monitoring stopped")

def main():
    """Main function"""
    print("🤖 Robot Connection Manager")
    print("Manage and monitor robot connection state")
    
    while True:
        try:
            show_menu()
            choice = input("\nEnter your choice (0-5): ").strip()
            
            if choice == "1":
                get_system_status()
            elif choice == "2":
                reset_connection_state()
            elif choice == "3":
                simulate_disconnect()
            elif choice == "4":
                simulate_reconnect()
            elif choice == "5":
                monitor_status()
            elif choice == "0":
                print("👋 Goodbye!")
                break
            else:
                print("❌ Invalid choice. Please try again.")
                
            if choice != "5":  # Don't pause after monitoring
                input("\nPress Enter to continue...")
                
        except KeyboardInterrupt:
            print("\n👋 Goodbye!")
            break
        except Exception as e:
            print(f"❌ Error: {e}")
            input("Press Enter to continue...")

if __name__ == "__main__":
    main()