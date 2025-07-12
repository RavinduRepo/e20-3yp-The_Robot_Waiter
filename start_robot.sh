#!/bin/bash

# Kill any existing Chrome/Chromium processes
pkill -f chrome || true
pkill -f chromium || true

# Wait a moment for processes to fully terminate
sleep 2

# Clean up any leftover Chrome temp directories
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

# Optional: Set screen resolution (uncomment if needed)
# xrandr --output HDMI-1 --mode 1920x1080 --rate 60

# Change to the main directory where the script and config files are located
cd /home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/

# Debug: Show current directory and list files
echo "Current working directory: $(pwd)"
echo "Files in current directory:"
ls -la

# run wifi setup script
python wifi_manager.py &
# Run the Python script
python robot_main.py
