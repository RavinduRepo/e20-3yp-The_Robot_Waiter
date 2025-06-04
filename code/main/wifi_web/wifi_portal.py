from flask import Flask, render_template, request, redirect
import subprocess
import json
from pathlib import Path

app = Flask(__name__)
CONFIG_PATH = Path("/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/utils/wifi_config.json")

def scan_networks():
    result = subprocess.run(["nmcli", "-t", "-f", "SSID", "dev", "wifi"],
                            capture_output=True, text=True)
    networks = list(filter(None, set(result.stdout.strip().split('\n'))))
    return sorted(networks)

def connect_wifi(ssid, password):
    result = subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password],
                            capture_output=True, text=True)
    return result.returncode == 0

@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        ssid = request.form.get("ssid")
        password = request.form.get("password")
        if connect_wifi(ssid, password):
            with open(CONFIG_PATH, "w") as f:
                json.dump({"ssid": ssid, "password": password}, f)
            return "<h2>WiFi Connected Successfully. You can close this window.</h2>"
        else:
            return "<h2>Failed to connect. Please try again.</h2>"

    networks = scan_networks()
    return render_template("index.html", networks=networks)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8080)
