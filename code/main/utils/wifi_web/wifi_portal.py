from flask import Flask, request, render_template
import json
import os
import subprocess
import threading
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from pathlib import Path

app = Flask(__name__)
CONFIG_PATH = "/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/utils/wifi_config.json"

# Scan for WiFi networks using nmcli
def scan_networks():
    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"],
                            capture_output=True, text=True)
    ssids = [ssid for ssid in result.stdout.strip().split('\n') if ssid]
    return sorted(list(set(ssids)))

@app.route("/", methods=["GET", "POST"])
def index():
    message = None
    if request.method == "POST":
        ssid = request.form.get("ssid")
        password = request.form.get("password")
        if ssid and password:
            with open(CONFIG_PATH, "w") as f:
                json.dump({"ssid": ssid, "password": password}, f)
            message = f"WiFi credentials for {ssid} saved. Please reboot."
    networks = scan_networks()
    return render_template("index.html", networks=networks, message=message)

def launch_chromium_with_selenium():
    time.sleep(2)  # Give Flask server time to start
    try:
        chrome_options = Options()
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--kiosk")  # Fullscreen for touch displays
        chrome_options.add_argument("--window-size=1024,768")
        chrome_options.add_argument("--start-fullscreen")

        driver = webdriver.Chrome(options=chrome_options)
        driver.get("http://localhost:8080")
    except Exception as e:
        print(f"[Error launching browser] {e}")

if __name__ == "__main__":
    # Only launch Selenium if config file is missing
    if not Path(CONFIG_PATH).exists():
        threading.Thread(target=launch_chromium_with_selenium).start()
    app.run(host="0.0.0.0", port=8080)
