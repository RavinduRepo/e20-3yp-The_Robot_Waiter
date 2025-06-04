#!/bin/bash

# Step 1: Update and upgrade the system
echo "í´„ Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Step 2: Install Chromium and Chromedriver
echo "í·© Installing Chromium and Chromedriver..."
sudo apt-get install -y chromium-browser chromium-chromedriver

# Step 3: Set upstream branch and create virtual environment
echo "í´§ Setting Git upstream and Python environment..."
cd /home/pi/Documents/e20-3yp-The_Robot_Waiter || exit

git branch --set-upstream-to=origin/main main

python3 -m venv venv --system-site-packages
source venv/bin/activate

pip install -r requirements.txt

# Step 4: Create systemd service file
echo "í³„ Creating systemd service: robotwaiter.service..."
SERVICE_PATH="/etc/systemd/system/robotwaiter.service"

sudo tee $SERVICE_PATH > /dev/null <<EOF
[Unit]
Description=Start Robot Waiter Python Script on Boot
After=network.target

[Service]
ExecStart=/home/pi/Documents/e20-3yp-The_Robot_Waiter/start_robot.sh
WorkingDirectory=/home/pi/Documents/e20-3yp-The_Robot_Waiter
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Step 5: Enable and start the service
echo "íº€ Enabling and starting the robotwaiter service..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload
sudo systemctl enable robotwaiter.service
sudo systemctl start robotwaiter.service

echo "âœ… Setup complete. Use 'sudo journalctl -u robotwaiter.service -e' to view logs."

