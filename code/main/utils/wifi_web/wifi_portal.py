from flask import Flask, request, render_template
import json
import os
import subprocess
import threading
import time
import webbrowser

app = Flask(__name__)
CONFIG_PATH = "/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/utils/wifi_config.json"

# Scan for available WiFi networks using nmcli
def scan_networks():
    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"], capture_output=True, text=True)
    ssids = [ssid for ssid in result.stdout.strip().split('\n') if ssid]
    return sorted(list(set(ssids)))  # Remove duplicates

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

def open_browser():
    time.sleep(2)  # Wait for server to start
    webbrowser.open("http://localhost:8080")

if __name__ == "__main__":
    threading.Thread(target=open_browser).start()
    app.run(host="0.0.0.0", port=8080)
