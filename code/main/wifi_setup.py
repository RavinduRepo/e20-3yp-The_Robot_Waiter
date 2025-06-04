import subprocess
import json
import os
from pathlib import Path

CONFIG_FILE = Path("/home/pi/Documents/e20-3yp-The_Robot_Waiter/wifi_config.json")

def scan_networks():
    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
    networks = list(filter(None, set(result.stdout.strip().split('\n'))))  # Remove empty/duplicates
    return networks

def connect_to_wifi(ssid, password):
    result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                            capture_output=True, text=True)
    return result.returncode == 0

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
        return False
    print("\nAvailable WiFi Networks:")
    for idx, net in enumerate(networks):
        print(f"{idx + 1}: {net}")
    try:
        choice = int(input("\nSelect network (1 - {}): ".format(len(networks))))
        ssid = networks[choice - 1]
        password = input(f"Enter password for {ssid}: ")
        if connect_to_wifi(ssid, password):
            save_credentials(ssid, password)
            return True
    except Exception as e:
        print(f"Error: {e}")
    return False

def try_auto_connect():
    creds = load_credentials()
    if creds:
        return connect_to_wifi(creds['ssid'], creds['password'])
    return False

if __name__ == "__main__":
    if not try_auto_connect():
        print("WiFi auto-connect failed or not configured.")
        setup_interactively()
