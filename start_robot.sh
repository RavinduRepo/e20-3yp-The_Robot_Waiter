#!/bin/bash

echo "[Startup] Checking WiFi configuration..."

# Run WiFi setup
python3 /home/pi/Documents/e20-3yp-The_Robot_Waiter/code/utils/wifi_setup.py

# Kill any existing Chrome/Chromium processes
pkill -f chrome || true
pkill -f chromium || true

# Wait a moment for processes to fully terminate
sleep 2

# Clean up Chrome temp directories
find /tmp -name "chrome_*" -type d -user pi -exec rm -rf {} + 2>/dev/null || true

# Activate virtual environment
source /home/pi/Documents/e20-3yp-The_Robot_Waiter/venv/bin/activate

# Set environment variables for display
export DISPLAY=:0
export PYTHONUNBUFFERED=1

# Ensure X11 display is available
if ! xset q &>/dev/null; then
    echo "No X11 display available"
fi

# Change to the main directory
cd /home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/

# Debug info
echo "Current working directory: $(pwd)"
echo "Files in current directory:"
ls -la

# Run the main robot code
python robot_main.py
