# wifi_portal.py
from flask import Flask, render_template, request
import json
import subprocess
import os
import threading
import time
import tempfile

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.chrome.options import Options as ChromeOptions

app = Flask(__name__)
CONFIG_PATH = "/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/utils/wifi_config.json"

# HTML rendering
@app.route('/')
def index():
    return render_template('index.html')

# Handle form submission
@app.route('/submit', methods=['POST'])
def submit():
    ssid = request.form['ssid']
    password = request.form['password']

    with open(CONFIG_PATH, "w") as f:
        json.dump({"ssid": ssid, "password": password}, f)

    # Connect using nmcli
    subprocess.run(["nmcli", "dev", "wifi", "connect", ssid, "password", password])

    return "✅ WiFi credentials saved and connection attempt started.<br>Reboot or rerun the robot system."

# Background thread to open browser after server starts
def open_browser():
    time.sleep(5)  # Wait for Flask server to be ready

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
        chrome_options.add_argument("--start-fullscreen")
        
        # Temporary profile
        user_data_dir = tempfile.mkdtemp()
        chrome_options.add_argument(f"--user-data-dir={user_data_dir}")
        
        # Setup WebDriver
        service = ChromeService("/usr/bin/chromedriver")
        driver = webdriver.Chrome(service=service, options=chrome_options)
        driver.set_page_load_timeout(30)
        driver.fullscreen_window()
        driver.get("http://localhost:8080/")

    except Exception as e:
        print(f"❌ Failed to open browser: {e}")

if __name__ == '__main__':
    # Launch browser in a thread
    threading.Thread(target=open_browser, daemon=True).start()

    # Start Flask server
    app.run(host='0.0.0.0', port=8080)
