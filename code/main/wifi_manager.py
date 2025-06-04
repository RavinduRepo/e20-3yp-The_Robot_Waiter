#!/usr/bin/env python3
import json
import os
import subprocess
import threading
import time
import re
from flask import Flask, render_template_string, request, jsonify
from pathlib import Path

# Constants
WIFI_CONFIG_FILE = Path("wifi_config.json")
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi WiFi Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 600px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
        }
        .network { 
            padding: 15px; 
            margin: 8px 0; 
            border: 1px solid #ddd; 
            cursor: pointer; 
            border-radius: 4px;
            background: #fafafa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .network:hover { 
            background-color: #e8f4f8; 
            border-color: #007acc;
        }
        .network-info {
            display: flex;
            flex-direction: column;
        }
        .network-name {
            font-weight: bold;
            font-size: 16px;
        }
        .network-details {
            font-size: 12px;
            color: #666;
            margin-top: 2px;
        }
        .signal-strength {
            font-size: 12px;
            color: #007acc;
            font-weight: bold;
        }
        #passwordForm { 
            display: none; 
            background: #f0f8ff;
            padding: 20px;
            border-radius: 6px;
            margin-top: 20px;
        }
        input[type="password"] {
            width: 100%;
            padding: 10px;
            margin: 10px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background: #007acc;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background: #005a99;
        }
        .cancel-btn {
            background: #666;
        }
        .cancel-btn:hover {
            background: #444;
        }
        .status {
            margin-top: 15px;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .refresh-btn {
            background: #28a745;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #218838;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>Raspberry Pi WiFi Setup</h1>
        <button class="refresh-btn" onclick="refreshNetworks()">🔄 Refresh Networks</button>
        <div class="loading" id="loading">Scanning for networks...</div>
        <div id="networks"></div>
        <div id="passwordForm">
            <h3>Connect to: <span id="selectedNetwork"></span></h3>
            <input type="password" id="password" placeholder="Enter WiFi password">
            <br>
            <button onclick="connectWifi()">Connect</button>
            <button class="cancel-btn" onclick="hidePasswordForm()">Cancel</button>
        </div>
        <div id="status" class="status"></div>
    </div>

    <script>
        let selectedSSID = '';
        
        function loadNetworks() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('networks').innerHTML = '';
            
            fetch('/scan')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('loading').style.display = 'none';
                    if (data.success) {
                        displayNetworks(data.networks);
                    } else {
                        showStatus('Failed to scan networks: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    document.getElementById('loading').style.display = 'none';
                    showStatus('Error scanning networks: ' + error.message, 'error');
                });
        }

        function displayNetworks(networks) {
            const networksDiv = document.getElementById('networks');
            networksDiv.innerHTML = '';
            
            if (networks.length === 0) {
                networksDiv.innerHTML = '<p>No networks found. Try refreshing.</p>';
                return;
            }
            
            networks.forEach(network => {
                const div = document.createElement('div');
                div.className = 'network';
                div.innerHTML = `
                    <div class="network-info">
                        <div class="network-name">${network.ssid}</div>
                        <div class="network-details">${network.encryption} • Channel ${network.channel}</div>
                    </div>
                    <div class="signal-strength">${network.signal_strength}%</div>
                `;
                div.onclick = () => showPasswordForm(network.ssid, network.encryption);
                networksDiv.appendChild(div);
            });
        }

        function showPasswordForm(ssid, encryption) {
            selectedSSID = ssid;
            document.getElementById('passwordForm').style.display = 'block';
            document.getElementById('selectedNetwork').textContent = ssid;
            document.getElementById('password').focus();
            
            // Clear previous status
            hideStatus();
        }

        function hidePasswordForm() {
            document.getElementById('passwordForm').style.display = 'none';
            document.getElementById('password').value = '';
            selectedSSID = '';
        }

        function connectWifi() {
            const password = document.getElementById('password').value;
            
            if (!selectedSSID) {
                showStatus('No network selected', 'error');
                return;
            }
            
            showStatus('Connecting to ' + selectedSSID + '...', 'info');
            
            fetch('/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ssid: selectedSSID, password: password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showStatus(data.message, 'success');
                    hidePasswordForm();
                } else {
                    showStatus(data.message, 'error');
                }
            })
            .catch(error => {
                showStatus('Connection error: ' + error.message, 'error');
            });
        }

        function refreshNetworks() {
            loadNetworks();
        }

        function showStatus(message, type) {
            const statusDiv = document.getElementById('status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
            
            if (type === 'success') {
                setTimeout(hideStatus, 5000);
            }
        }

        function hideStatus() {
            document.getElementById('status').style.display = 'none';
        }

        // Load networks on page load
        loadNetworks();
        
        // Enter key support for password field
        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                connectWifi();
            }
        });
    </script>
</body>
</html>
"""

app = Flask(__name__)

def run_command(command, timeout=30):
    """Run a system command with timeout"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def get_wifi_interface():
    """Get the WiFi interface name"""
    success, output, _ = run_command("ls /sys/class/net/ | grep -E '^wl'")
    if success and output.strip():
        return output.strip().split('\n')[0]
    return "wlan0"  # Default fallback

def scan_wifi_networks():
    """Scan for available WiFi networks using nmcli or iwlist"""
    interface = get_wifi_interface()
    networks = []
    
    # Try nmcli first (NetworkManager)
    success, output, _ = run_command("which nmcli")
    if success:
        success, output, error = run_command("nmcli -t -f SSID,SIGNAL,SECURITY,CHAN dev wifi list")
        if success:
            for line in output.strip().split('\n'):
                if line and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[0].strip():
                        ssid = parts[0].strip()
                        signal = parts[1].strip() if parts[1] else "0"
                        security = parts[2].strip() if parts[2] else "Open"
                        channel = parts[3].strip() if parts[3] else "Unknown"
                        
                        # Skip hidden networks
                        if ssid and ssid != "--":
                            networks.append({
                                'ssid': ssid,
                                'signal_strength': signal,
                                'encryption': security if security else "Open",
                                'channel': channel
                            })
    
    # Fallback to iwlist if nmcli failed
    if not networks:
        success, output, _ = run_command(f"sudo iwlist {interface} scan")
        if success:
            networks = parse_iwlist_output(output)
    
    # Remove duplicates and sort by signal strength
    seen_ssids = set()
    unique_networks = []
    for network in networks:
        if network['ssid'] not in seen_ssids:
            seen_ssids.add(network['ssid'])
            unique_networks.append(network)
    
    # Sort by signal strength (descending)
    try:
        unique_networks.sort(key=lambda x: int(str(x['signal_strength']).replace('%', '').replace('dBm', '')), reverse=True)
    except:
        pass
    
    return unique_networks

def parse_iwlist_output(output):
    """Parse iwlist scan output"""
    networks = []
    current_network = {}
    
    for line in output.split('\n'):
        line = line.strip()
        
        if 'Cell' in line and 'Address:' in line:
            if current_network.get('ssid'):
                networks.append(current_network)
            current_network = {}
        
        elif 'ESSID:' in line:
            ssid_match = re.search(r'ESSID:"([^"]*)"', line)
            if ssid_match:
                current_network['ssid'] = ssid_match.group(1)
        
        elif 'Signal level=' in line:
            signal_match = re.search(r'Signal level=(-?\d+)', line)
            if signal_match:
                # Convert dBm to percentage (rough approximation)
                dbm = int(signal_match.group(1))
                percentage = max(0, min(100, 2 * (dbm + 100)))
                current_network['signal_strength'] = str(percentage)
        
        elif 'Encryption key:' in line:
            if 'off' in line:
                current_network['encryption'] = 'Open'
            else:
                current_network['encryption'] = 'WPA/WPA2'
        
        elif 'Channel:' in line:
            channel_match = re.search(r'Channel:(\d+)', line)
            if channel_match:
                current_network['channel'] = channel_match.group(1)
    
    # Add the last network
    if current_network.get('ssid'):
        networks.append(current_network)
    
    return networks

def connect_to_wifi_nmcli(ssid, password):
    """Connect using NetworkManager (nmcli)"""
    # Check if NetworkManager is available
    success, _, _ = run_command("which nmcli")
    if not success:
        return False, "NetworkManager not available"
    
    # Remove existing connection if it exists
    run_command(f'nmcli connection delete "{ssid}"')
    
    # Create new connection
    if password:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}" password "{password}"'
        )
    else:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}"'
        )
    
    if success:
        return True, f"Successfully connected to {ssid}"
    else:
        return False, f"Failed to connect: {error}"

def connect_to_wifi_wpa(ssid, password):
    """Connect using wpa_supplicant (fallback method)"""
    interface = get_wifi_interface()
    
    try:
        # Create wpa_supplicant config
        config_content = f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    """
        
        if password:
            config_content += f'    psk="{password}"\n'
        else:
            config_content += '    key_mgmt=NONE\n'
        
        config_content += "}\n"
        
        # Write config file
        with open('/tmp/wpa_temp.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to system location
        success, _, error = run_command('sudo cp /tmp/wpa_temp.conf /etc/wpa_supplicant/wpa_supplicant.conf')
        if not success:
            return False, f"Failed to write config: {error}"
        
        # Restart network interface
        run_command(f'sudo ifconfig {interface} down')
        time.sleep(2)
        run_command(f'sudo ifconfig {interface} up')
        
        # Restart wpa_supplicant
        run_command('sudo systemctl restart wpa_supplicant')
        time.sleep(3)
        
        # Request DHCP
        run_command(f'sudo dhclient {interface}')
        
        # Check connection
        for i in range(15):
            success, output, _ = run_command('iwgetid -r')
            if success and ssid in output:
                return True, f"Successfully connected to {ssid}"
            time.sleep(2)
        
        return False, "Connection timeout"
        
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def save_wifi_config(ssid, password):
    """Save WiFi credentials to local file"""
    config = {'ssid': ssid, 'password': password, 'timestamp': time.time()}
    try:
        with open(WIFI_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False

def load_wifi_config():
    """Load saved WiFi credentials"""
    try:
        if WIFI_CONFIG_FILE.exists():
            with open(WIFI_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
    return None

def check_internet_connectivity():
    """Check if we have internet connectivity"""
    success, _, _ = run_command("ping -c 1 -W 5 8.8.8.8")
    return success

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scan')
def scan():
    try:
        networks = scan_wifi_networks()
        return jsonify({
            'success': True,
            'networks': networks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'networks': []
        })

@app.route('/connect', methods=['POST'])
def connect():
    try:
        data = request.json
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        
        if not ssid:
            return jsonify({
                'success': False,
                'message': 'SSID is required'
            })
        
        # Try NetworkManager first
        success, message = connect_to_wifi_nmcli(ssid, password)
        
        # Fallback to wpa_supplicant if NetworkManager fails
        if not success:
            success, message = connect_to_wifi_wpa(ssid, password)
        
        if success:
            # Save successful connection
            save_wifi_config(ssid, password)
            
            # Check internet connectivity
            time.sleep(5)  # Wait a bit for connection to stabilize
            if check_internet_connectivity():
                message += " - Internet connectivity confirmed"
            else:
                message += " - Connected but no internet access"
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection error: {str(e)}'
        })

@app.route('/status')
def status():
    """Get current WiFi status"""
    try:
        success, output, _ = run_command('iwgetid -r')
        current_ssid = output.strip() if success else None
        
        internet = check_internet_connectivity()
        
        return jsonify({
            'connected': bool(current_ssid),
            'ssid': current_ssid,
            'internet': internet
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'ssid': None,
            'internet': False,
            'error': str(e)
        })

def start_web_server():
    """Start the Flask web server"""
    app.run(host='0.0.0.0', port=8080, debug=False)

def main():
    """Main function"""
    print("=== Raspberry Pi WiFi Setup Tool ===")
    
    # Check if running as root/sudo for system operations
    if os.geteuid() != 0:
        print("Warning: Not running as root. Some operations may fail.")
        print("Consider running with: sudo python3 wifi_setup.py")
    
    # Try to connect with saved credentials first
    config = load_wifi_config()
    if config and config.get('ssid'):
        print(f"Attempting to connect to saved network: {config['ssid']}")
        success, message = connect_to_wifi_nmcli(config['ssid'], config.get('password', ''))
        if success:
            print("✓ Connected to saved network successfully")
        else:
            print(f"✗ Failed to connect to saved network: {message}")
    
    # Start web server
    server_thread = threading.Thread(target=start_web_server)
    server_thread.daemon = True
    server_thread.start()
    
    print(f"\n🌐 Web interface started!")
    print(f"   Local access: http://localhost:8080")
    
    # Try to get IP address for remote access
    success, output, _ = run_command("hostname -I")
    if success and output.strip():
        ip = output.strip().split()[0]
        print(f"   Network access: http://{ip}:8080")
    
    print(f"\n📱 Open the web interface to configure WiFi")
    print(f"   Press Ctrl+C to stop the server")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down WiFi setup tool...")

if __name__ == "__main__":
    main()