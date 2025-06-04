import json
import os
import subprocess
import threading
from flask import Flask, render_template_string, request, jsonify
import wifi
from pathlib import Path
import time
import sys

# Constants
WIFI_CONFIG_FILE = Path("wifi_config.json")
HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>WiFi Setup</title>
    <style>
        body { font-family: Arial; max-width: 600px; margin: 0 auto; padding: 20px; }
        .network { padding: 10px; margin: 5px; border: 1px solid #ddd; cursor: pointer; }
        .network:hover { background-color: #f0f0f0; }
        #passwordForm { display: none; }
    </style>
</head>
<body>
    <h1>WiFi Setup</h1>
    <div id="networks"></div>
    <div id="passwordForm">
        <h3 id="selectedNetwork"></h3>
        <input type="password" id="password" placeholder="Enter password">
        <button onclick="connectWifi()">Connect</button>
    </div>
    <script>
        fetch('/scan')
            .then(response => response.json())
            .then(networks => {
                const networksDiv = document.getElementById('networks');
                networks.forEach(network => {
                    const div = document.createElement('div');
                    div.className = 'network';
                    div.textContent = network;
                    div.onclick = () => showPasswordForm(network);
                    networksDiv.appendChild(div);
                });
            });

        function showPasswordForm(network) {
            document.getElementById('passwordForm').style.display = 'block';
            document.getElementById('selectedNetwork').textContent = network;
        }

        function connectWifi() {
            const network = document.getElementById('selectedNetwork').textContent;
            const password = document.getElementById('password').value;
            fetch('/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ssid: network, password: password})
            }).then(response => response.json())
              .then(data => alert(data.message));
        }
    </script>
</body>
</html>
"""

app = Flask(__name__)

def get_wifi_networks():
    """Scan and return available WiFi networks"""
    try:
        wifi_scanner = wifi.Cell.all('wlan0')
        return [cell.ssid for cell in wifi_scanner]
    except:
        # Fallback for testing or if wifi module fails
        return ["Network1", "Network2", "Network3"]

def create_wpa_config(ssid, password):
    """Create WPA supplicant config file content"""
    return f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    psk="{password}"
    key_mgmt=WPA-PSK
}}"""

def check_wifi_connection(ssid):
    """Check if connected to specified network"""
    try:
        # Get current WiFi info using iwconfig
        result = subprocess.run(['iwgetid'], capture_output=True, text=True)
        return ssid in result.stdout
    except:
        return False

def connect_to_wifi(ssid, password):
    """Connect to a WiFi network"""
    try:
        # Save credentials
        save_wifi_config(ssid, password)
        
        # Create wpa_supplicant configuration in a temporary file
        config_content = create_wpa_config(ssid, password)
        temp_config = '/tmp/wpa_supplicant.conf.tmp'
        
        with open(temp_config, 'w') as f:
            f.write(config_content)
        
        # Copy the config file to correct location with sudo
        subprocess.run(['sudo', 'cp', temp_config, '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
        subprocess.run(['sudo', 'chmod', '600', '/etc/wpa_supplicant/wpa_supplicant.conf'], check=True)
        
        # Restart networking with sudo
        print("Restarting wireless interface...")
        subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'down'], check=True)
        subprocess.run(['sudo', 'ip', 'link', 'set', 'wlan0', 'up'], check=True)
        
        # Restart wpa_supplicant and dhclient with sudo
        print("Restarting network services...")
        subprocess.run(['sudo', 'systemctl', 'restart', 'wpa_supplicant'], check=True)
        subprocess.run(['sudo', 'dhclient', 'wlan0'], check=True)
        
        # Clean up temp file
        os.remove(temp_config)
        
        # Wait for connection
        print("Waiting for connection...")
        max_retries = 15
        for i in range(max_retries):
            if check_wifi_connection(ssid):
                print(f"Successfully connected to {ssid}")
                return True
            time.sleep(1)
            print(f"Attempting to connect... ({i+1}/{max_retries})")
        
        print("Failed to connect after maximum retries")
        return False
        
    except subprocess.CalledProcessError as e:
        print(f"Failed to execute command: {e}")
        print("Error output:", e.stderr if hasattr(e, 'stderr') else 'No error output')
        return False
    except Exception as e:
        print(f"Failed to connect to WiFi: {e}")
        return False

def save_wifi_config(ssid, password):
    """Save WiFi credentials to local file"""
    config = {'ssid': ssid, 'password': password}
    with open(WIFI_CONFIG_FILE, 'w') as f:
        json.dump(config, f)

def load_wifi_config():
    """Load saved WiFi credentials"""
    if WIFI_CONFIG_FILE.exists():
        with open(WIFI_CONFIG_FILE, 'r') as f:
            return json.load(f)
    return None

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scan')
def scan():
    return jsonify(get_wifi_networks())

@app.route('/connect', methods=['POST'])
def connect():
    data = request.json
    success = connect_to_wifi(data['ssid'], data['password'])
    if success:
        return jsonify({
            'message': f"Connected successfully to {data['ssid']}",
            'status': 'success'
        })
    else:
        return jsonify({
            'message': 'Failed to connect to WiFi network',
            'status': 'error'
        })

def start_web_server():
    """Start the Flask web server"""
    app.run(host='0.0.0.0', port=8080)

def main():
    """Main function to handle WiFi management"""
    # Check if running with sudo
    if os.geteuid() != 0:
        print("This script must be run with sudo privileges!")
        print("Please run: sudo python3 wifi_manager.py")
        sys.exit(1)
        
    # Try to connect with saved credentials first
    config = load_wifi_config()
    if config:
        print(f"Attempting to connect to saved network: {config['ssid']}")
        if connect_to_wifi(config['ssid'], config['password']):
            print("Connected to saved network successfully")
        else:
            print("Failed to connect to saved network")
    
    # Start web server in a separate thread
    server_thread = threading.Thread(target=start_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    print("Web server started at http://localhost:8080")
    try:
        while True:
            pass  # Keep the main thread running
    except KeyboardInterrupt:
        print("Shutting down...")

if __name__ == "__main__":
    main()
