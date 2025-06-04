import json
import subprocess
from pathlib import Path

CONFIG_PATH = "/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/utils/wifi_config.json"

def connect(ssid, password):
    result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                            capture_output=True, text=True)
    print(result.stdout)
    print(result.stderr)
    return result.returncode == 0

if Path(CONFIG_PATH).exists():
    with open(CONFIG_PATH, "r") as f:
        config = json.load(f)
        ssid = config.get("ssid")
        password = config.get("password")
        if ssid and password:
            print(f"[WiFi] Connecting to {ssid}...")
            if not connect(ssid, password):
                print("[WiFi] Failed to connect using saved config.")
        else:
            print("[WiFi] Invalid config format.")
else:
    print("[WiFi] Config file not found.")
