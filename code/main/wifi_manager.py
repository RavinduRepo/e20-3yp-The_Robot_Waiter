@app.route('/robot-config', methods=['GET', 'POST'])
def robot_config():
    """Handle robot configuration"""
    if request.method == 'GET':
        try:
            config = load_robot_config()
            return jsonify({
                'success': True,
                'config': config
            })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e),
                'config': {}
            })
    
    elif request.method == 'POST':
        try:
            data = request.json
            robot_id = data.get('robotId', '').strip()
            password = data.get('password', '').strip()
            
            if not robot_id:
                return jsonify({
                    'success': False,
                    'message': 'Robot ID is required'
                })
            
            if not password:
                return jsonify({
                    'success': False,
                    'message': 'Password is required'
                })
            
            # Validate robot ID format (optional - adjust as needed)
            if len(robot_id) < 3:
                return jsonify({
                    'success': False,
                    'message': 'Robot ID must be at least 3 characters long'
                })
            
            if len(password) < 4:
                return jsonify({
                    'success': False,
                    'message': 'Password must be at least 4 characters long'
                })
            
            success = save_robot_config(robot_id, password)
            
            if success:
                return jsonify({
                    'success': True,
                    'message': f'Robot configuration saved successfully! Robot ID: {robot_id}'
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to save robot configuration'
                })
                
        except Exception as e:
            return jsonify({
                'success': False#!/usr/bin/env python3
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
ROBOT_CONFIG_FILE = Path("robot_config.json")
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi WiFi & Robot Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
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
        .tabs {
            display: flex;
            margin-bottom: 20px;
            border-bottom: 2px solid #ddd;
        }
        .tab {
            padding: 10px 20px;
            cursor: pointer;
            border: none;
            background: none;
            font-size: 16px;
            color: #666;
            border-bottom: 2px solid transparent;
            transition: all 0.3s;
        }
        .tab.active {
            color: #007acc;
            border-bottom-color: #007acc;
            font-weight: bold;
        }
        .tab:hover {
            color: #007acc;
            background-color: #f0f8ff;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
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
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #333;
        }
        input[type="password"], input[type="text"] {
            width: 100%;
            padding: 10px;
            margin: 5px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
            font-size: 14px;
        }
        button {
            background: #007acc;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
            font-size: 14px;
        }
        button:hover {
            background: #005a99;
        }
        .cancel-btn, .secondary-btn {
            background: #666;
        }
        .cancel-btn:hover, .secondary-btn:hover {
            background: #444;
        }
        .success-btn {
            background: #28a745;
        }
        .success-btn:hover {
            background: #218838;
        }
        .danger-btn {
            background: #dc3545;
        }
        .danger-btn:hover {
            background: #c82333;
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
        .status.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
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
        .robot-config {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border: 1px solid #dee2e6;
        }
        .config-display {
            background: #e9ecef;
            padding: 15px;
            border-radius: 4px;
            margin: 15px 0;
            font-family: monospace;
            border: 1px solid #ced4da;
        }
        .config-row {
            display: flex;
            justify-content: space-between;
            align-items: center;
            padding: 8px 0;
            border-bottom: 1px solid #dee2e6;
        }
        .config-row:last-child {
            border-bottom: none;
        }
        .config-label {
            font-weight: bold;
            color: #495057;
            min-width: 120px;
        }
        .config-value {
            font-family: monospace;
            color: #007acc;
            background: white;
            padding: 4px 8px;
            border-radius: 3px;
            border: 1px solid #ced4da;
            flex: 1;
            margin: 0 10px;
        }
        .edit-form {
            display: none;
            margin-top: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <h1>🤖 Raspberry Pi Setup</h1>
        
        <div class="tabs">
            <button class="tab active" onclick="showTab('wifi')">📶 WiFi Setup</button>
            <button class="tab" onclick="showTab('robot')">🤖 Robot Config</button>
        </div>
        
        <!-- WiFi Setup Tab -->
        <div id="wifi-tab" class="tab-content active">
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
            <div id="wifi-status" class="status"></div>
        </div>
        
        <!-- Robot Config Tab -->
        <div id="robot-tab" class="tab-content">
            <div class="robot-config">
                <h3>🤖 Robot Configuration</h3>
                <p>Current robot settings:</p>
                
                <div id="robotConfigDisplay" class="config-display">
                    <div class="config-row">
                        <span class="config-label">Robot ID:</span>
                        <span class="config-value" id="displayRobotId">Loading...</span>
                    </div>
                    <div class="config-row">
                        <span class="config-label">Password:</span>
                        <span class="config-value" id="displayPassword">Loading...</span>
                    </div>
                    <div class="config-row">
                        <span class="config-label">Last Updated:</span>
                        <span class="config-value" id="displayLastUpdated">Loading...</span>
                    </div>
                </div>
                
                <button class="success-btn" onclick="showEditForm()">✏️ Edit Configuration</button>
                <button class="secondary-btn" onclick="loadRobotConfig()">🔄 Refresh</button>
                
                <div id="editForm" class="edit-form">
                    <h4>Edit Robot Configuration</h4>
                    <div class="form-group">
                        <label for="robotId">Robot ID:</label>
                        <input type="text" id="robotId" placeholder="Enter Robot ID" maxlength="20">
                    </div>
                    <div class="form-group">
                        <label for="robotPassword">Password:</label>
                        <input type="text" id="robotPassword" placeholder="Enter Robot Password" maxlength="50">
                    </div>
                    <button class="success-btn" onclick="saveRobotConfig()">💾 Save Configuration</button>
                    <button class="cancel-btn" onclick="hideEditForm()">Cancel</button>
                </div>
            </div>
            <div id="robot-status" class="status"></div>
        </div>
    </div>

    <script>
        let selectedSSID = '';
        
        // Tab Management
        function showTab(tabName) {
            // Hide all tab contents
            document.querySelectorAll('.tab-content').forEach(content => {
                content.classList.remove('active');
            });
            
            // Remove active class from all tabs
            document.querySelectorAll('.tab').forEach(tab => {
                tab.classList.remove('active');
            });
            
            // Show selected tab content
            document.getElementById(tabName + '-tab').classList.add('active');
            
            // Add active class to clicked tab
            event.target.classList.add('active');
            
            // Load data for robot tab
            if (tabName === 'robot') {
                loadRobotConfig();
            }
        }
        
        // WiFi Functions
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
                        showWifiStatus('Failed to scan networks: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    document.getElementById('loading').style.display = 'none';
                    showWifiStatus('Error scanning networks: ' + error.message, 'error');
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
            hideWifiStatus();
        }

        function hidePasswordForm() {
            document.getElementById('passwordForm').style.display = 'none';
            document.getElementById('password').value = '';
            selectedSSID = '';
        }

        function connectWifi() {
            const password = document.getElementById('password').value;
            
            if (!selectedSSID) {
                showWifiStatus('No network selected', 'error');
                return;
            }
            
            showWifiStatus('Connecting to ' + selectedSSID + '...', 'info');
            
            fetch('/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ssid: selectedSSID, password: password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showWifiStatus(data.message, 'success');
                    hidePasswordForm();
                } else {
                    showWifiStatus(data.message, 'error');
                }
            })
            .catch(error => {
                showWifiStatus('Connection error: ' + error.message, 'error');
            });
        }

        function refreshNetworks() {
            loadNetworks();
        }

        function showWifiStatus(message, type) {
            const statusDiv = document.getElementById('wifi-status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
            
            if (type === 'success') {
                setTimeout(() => hideWifiStatus(), 5000);
            }
        }

        function hideWifiStatus() {
            document.getElementById('wifi-status').style.display = 'none';
        }
        
        // Robot Config Functions
        function loadRobotConfig() {
            fetch('/robot-config')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        updateRobotDisplay(data.config);
                    } else {
                        showRobotStatus('Failed to load robot config: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showRobotStatus('Error loading robot config: ' + error.message, 'error');
                });
        }
        
        function updateRobotDisplay(config) {
            document.getElementById('displayRobotId').textContent = config.robotId || 'Not set';
            document.getElementById('displayPassword').textContent = config.password || 'Not set';
            
            if (config.lastUpdated) {
                const date = new Date(config.lastUpdated * 1000);
                document.getElementById('displayLastUpdated').textContent = date.toLocaleString();
            } else {
                document.getElementById('displayLastUpdated').textContent = 'Never';
            }
        }
        
        function showEditForm() {
            // Load current values into form
            const robotId = document.getElementById('displayRobotId').textContent;
            const password = document.getElementById('displayPassword').textContent;
            
            document.getElementById('robotId').value = robotId !== 'Not set' ? robotId : '';
            document.getElementById('robotPassword').value = password !== 'Not set' ? password : '';
            
            document.getElementById('editForm').style.display = 'block';
            document.getElementById('robotId').focus();
            hideRobotStatus();
        }
        
        function hideEditForm() {
            document.getElementById('editForm').style.display = 'none';
            document.getElementById('robotId').value = '';
            document.getElementById('robotPassword').value = '';
        }
        
        function saveRobotConfig() {
            const robotId = document.getElementById('robotId').value.trim();
            const password = document.getElementById('robotPassword').value.trim();
            
            if (!robotId) {
                showRobotStatus('Robot ID is required', 'error');
                return;
            }
            
            if (!password) {
                showRobotStatus('Password is required', 'error');
                return;
            }
            
            showRobotStatus('Saving robot configuration...', 'info');
            
            fetch('/robot-config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    robotId: robotId,
                    password: password
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showRobotStatus('Robot configuration saved successfully!', 'success');
                    hideEditForm();
                    loadRobotConfig(); // Refresh display
                } else {
                    showRobotStatus('Failed to save: ' + data.message, 'error');
                }
            })
            .catch(error => {
                showRobotStatus('Save error: ' + error.message, 'error');
            });
        }
        
        function showRobotStatus(message, type) {
            const statusDiv = document.getElementById('robot-status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
            
            if (type === 'success') {
                setTimeout(() => hideRobotStatus(), 5000);
            }
        }
        
        function hideRobotStatus() {
            document.getElementById('robot-status').style.display = 'none';
        }
        
        // Initialize
        loadNetworks();
        
        // Enter key support
        document.getElementById('password').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                connectWifi();
            }
        });
        
        document.getElementById('robotId').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                document.getElementById('robotPassword').focus();
            }
        });
        
        document.getElementById('robotPassword').addEventListener('keypress', function(e) {
            if (e.key === 'Enter') {
                saveRobotConfig();
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
    
    print(f"Attempting to connect to {ssid} using NetworkManager...")
    
    # First, disconnect from current network
    print("Disconnecting from current network...")
    run_command("nmcli device disconnect wifi")
    time.sleep(2)
    
    # Remove existing connection if it exists
    print(f"Removing existing connection for {ssid}...")
    run_command(f'nmcli connection delete "{ssid}"', timeout=10)
    
    # Rescan for networks
    print("Rescanning for networks...")
    run_command("nmcli device wifi rescan", timeout=15)
    time.sleep(3)
    
    # Create new connection
    print(f"Creating new connection to {ssid}...")
    if password:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}" password "{password}"',
            timeout=30
        )
    else:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}"',
            timeout=30
        )
    
    print(f"nmcli output: {output}")
    if error:
        print(f"nmcli error: {error}")
    
    if success:
        # Wait and verify connection
        time.sleep(5)
        success, current_ssid, _ = run_command("nmcli -t -f active,ssid dev wifi | grep '^yes' | cut -d: -f2")
        if success and ssid in current_ssid:
            return True, f"Successfully connected to {ssid}"
        else:
            return False, f"Connection command succeeded but not connected to {ssid}"
    else:
        return False, f"Failed to connect: {error}"

def connect_to_wifi_wpa(ssid, password):
    """Connect using wpa_supplicant (fallback method)"""
    interface = get_wifi_interface()
    print(f"Attempting to connect to {ssid} using wpa_supplicant on interface {interface}...")
    
    try:
        # Kill existing wpa_supplicant processes
        print("Stopping existing wpa_supplicant processes...")
        run_command("sudo pkill wpa_supplicant")
        time.sleep(2)
        
        # Bring interface down and up
        print(f"Resetting interface {interface}...")
        run_command(f'sudo ifconfig {interface} down')
        time.sleep(2)
        run_command(f'sudo ifconfig {interface} up')
        time.sleep(2)
        
        # Create wpa_supplicant config
        config_content = f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    """
        
        if password:
            # Generate PSK for better compatibility
            success, psk_output, _ = run_command(f'wpa_passphrase "{ssid}" "{password}"')
            if success and "psk=" in psk_output:
                # Extract the PSK line
                for line in psk_output.split('\n'):
                    if line.strip().startswith('psk=') and not line.strip().startswith('psk="'):
                        psk = line.strip().split('=')[1]
                        config_content += f'    psk={psk}\n'
                        break
                else:
                    config_content += f'    psk="{password}"\n'
            else:
                config_content += f'    psk="{password}"\n'
            
            config_content += '    key_mgmt=WPA-PSK\n'
        else:
            config_content += '    key_mgmt=NONE\n'
        
        config_content += "    scan_ssid=1\n}\n"
        
        print("Generated wpa_supplicant config:")
        print(config_content.replace(password, "***" if password else ""))
        
        # Write config file
        with open('/tmp/wpa_temp.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to system location
        success, _, error = run_command('sudo cp /tmp/wpa_temp.conf /etc/wpa_supplicant/wpa_supplicant.conf')
        if not success:
            return False, f"Failed to write config: {error}"
        
        # Start wpa_supplicant manually
        print("Starting wpa_supplicant...")
        success, output, error = run_command(
            f'sudo wpa_supplicant -B -i {interface} -c /etc/wpa_supplicant/wpa_supplicant.conf',
            timeout=15
        )
        
        if not success:
            print(f"wpa_supplicant error: {error}")
            return False, f"Failed to start wpa_supplicant: {error}"
        
        time.sleep(5)
        
        # Request DHCP
        print("Requesting DHCP...")
        run_command(f'sudo dhclient -r {interface}')  # Release old lease
        time.sleep(2)
        success, dhcp_output, dhcp_error = run_command(f'sudo dhclient {interface}', timeout=20)
        
        if dhcp_output:
            print(f"DHCP output: {dhcp_output}")
        if dhcp_error:
            print(f"DHCP error: {dhcp_error}")
        
        # Check connection multiple times
        print("Verifying connection...")
        for i in range(20):
            # Check if connected to the right SSID
            success, output, _ = run_command('iwgetid -r')
            current_ssid = output.strip() if success else ""
            
            # Check if we have an IP address
            success_ip, ip_output, _ = run_command(f'ip addr show {interface} | grep "inet " | awk "{{print $2}}"')
            has_ip = success_ip and ip_output.strip() and "127.0.0.1" not in ip_output
            
            print(f"Attempt {i+1}/20: SSID='{current_ssid}', Target='{ssid}', Has IP={has_ip}")
            
            if current_ssid == ssid and has_ip:
                return True, f"Successfully connected to {ssid}"
            
            time.sleep(2)
        
        return False, f"Connection timeout - connected to '{current_ssid}' but expected '{ssid}'"
        
    except Exception as e:
        print(f"Exception in wpa connection: {e}")
        return False, f"Connection failed: {str(e)}"

def save_robot_config(robot_id, password):
    """Save robot configuration to local file"""
    config = {
        'robotId': robot_id,
        'password': password,
        'lastUpdated': time.time()
    }
    try:
        with open(ROBOT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True
    except Exception as e:
        print(f"Failed to save robot config: {e}")
        return False

def load_robot_config():
    """Load robot configuration"""
    try:
        if ROBOT_CONFIG_FILE.exists():
            with open(ROBOT_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Create default config if file doesn't exist
            default_config = {
                'robotId': '',
                'password': '',
                'lastUpdated': None
            }
            save_robot_config('', '')
            return default_config
    except Exception as e:
        print(f"Failed to load robot config: {e}")
        return {
            'robotId': '',
            'password': '',
            'lastUpdated': None
        }
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
        
        print(f"\n=== Attempting to connect to '{ssid}' ===")
        
        # Check current connection
        success, current_output, _ = run_command('iwgetid -r')
        current_ssid = current_output.strip() if success else ""
        print(f"Currently connected to: '{current_ssid}'")
        
        # Save credentials first (so they're available even if connection fails)
        save_wifi_config(ssid, password)
        print("Credentials saved to config file")
        
        connection_success = False
        final_message = ""
        
        # Try NetworkManager first
        print("\n--- Trying NetworkManager ---")
        success, message = connect_to_wifi_nmcli(ssid, password)
        if success:
            connection_success = True
            final_message = message
            print(f"✓ NetworkManager success: {message}")
        else:
            print(f"✗ NetworkManager failed: {message}")
            
            # Fallback to wpa_supplicant
            print("\n--- Trying wpa_supplicant fallback ---")
            success, message = connect_to_wifi_wpa(ssid, password)
            if success:
                connection_success = True
                final_message = message
                print(f"✓ wpa_supplicant success: {message}")
            else:
                print(f"✗ wpa_supplicant failed: {message}")
                final_message = f"Both connection methods failed. NetworkManager: {message}"
        
        if connection_success:
            # Verify final connection state
            time.sleep(3)
            success, verify_output, _ = run_command('iwgetid -r')
            verified_ssid = verify_output.strip() if success else ""
            
            if verified_ssid == ssid:
                # Check internet connectivity
                if check_internet_connectivity():
                    final_message += " - Internet connectivity confirmed"
                    print("✓ Internet connectivity confirmed")
                else:
                    final_message += " - Connected but no internet access"
                    print("! Connected but no internet access")
            else:
                connection_success = False
                final_message = f"Connection verification failed. Expected '{ssid}', got '{verified_ssid}'"
                print(f"✗ Verification failed: {final_message}")
        
        print(f"=== Final result: {'SUCCESS' if connection_success else 'FAILED'} ===\n")
        
        return jsonify({
            'success': connection_success,
            'message': final_message
        })
        
    except Exception as e:
        error_msg = f'Connection error: {str(e)}'
        print(f"✗ Exception in connect route: {error_msg}")
        return jsonify({
            'success': False,
            'message': error_msg
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
    
    # Show current WiFi status
    success, current_output, _ = run_command('iwgetid -r')
    current_ssid = current_output.strip() if success else "None"
    print(f"Currently connected to: {current_ssid}")
    
    # Try to connect with saved credentials first
    config = load_wifi_config()
    if config and config.get('ssid'):
        saved_ssid = config['ssid']
        print(f"Found saved network: {saved_ssid}")
        
        # Only try to reconnect if not already connected to the saved network
        if current_ssid != saved_ssid:
            print(f"Attempting to connect to saved network: {saved_ssid}")
            success, message = connect_to_wifi_nmcli(saved_ssid, config.get('password', ''))
            if success:
                print("✓ Connected to saved network successfully")
            else:
                print(f"✗ Failed to connect to saved network: {message}")
                # Try wpa_supplicant fallback
                success, message = connect_to_wifi_wpa(saved_ssid, config.get('password', ''))
                if success:
                    print("✓ Connected to saved network using fallback method")
                else:
                    print(f"✗ Fallback connection also failed: {message}")
        else:
            print("✓ Already connected to saved network")
    
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
    print(f"\n📊 Debug info will be shown in the console when connecting")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down WiFi setup tool...")

if __name__ == "__main__":
    main()