import subprocess
import json
import os
from pathlib import Path

CONFIG_FILE = Path("/etc/robot_wifi_config.json")

def scan_networks():
    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
    networks = list(filter(None, set(result.stdout.strip().split('\n'))))  # Remove duplicates and empty
    return networks

def connect_to_wifi(ssid, password):
    print(f"Connecting to {ssid}...")
    result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                            capture_output=True, text=True)
    if result.returncode == 0:
        print(f"Successfully connected to {ssid}")
        return True
    else:
        print(f"Failed to connect: {result.stderr}")
        return False

def save_credentials(ssid, password):
    with open(CONFIG_FILE, "w") as f:
        json.dump({"ssid": ssid, "password": password}, f)

def load_credentials():
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            return json.load(f)
    return None

def setup_interactively():
    networks = scan_networks()
    if not networks:
        print("No networks found.")
        return
    print("\nAvailable WiFi Networks:")
    for idx, net in enumerate(networks):
        print(f"{idx + 1}: {net}")
    choice = int(input("\nSelect network (1 - {}): ".format(len(networks))))
    ssid = networks[choice - 1]
    password = input(f"Enter password for {ssid}: ")
    if connect_to_wifi(ssid, password):
        save_credentials(ssid, password)

def try_auto_connect():
    creds = load_credentials()
    if creds:
        print(f"Attempting to connect to saved WiFi: {creds['ssid']}")
        return connect_to_wifi(creds['ssid'], creds['password'])
    return False

if __name__ == "__main__":
    if not try_auto_connect():
        setup_interactively()
