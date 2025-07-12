#!/bin/bash

# Wait a bit for the system to settle
sleep 20

# Check if we're connected to the internet
ping -c 1 -W 5 8.8.8.8 >/dev/null 2>&1
if [ $? -ne 0 ]; then
    echo "[Fallback] No internet, enabling hotspot..."

    sudo systemctl enable hostapd
    sudo systemctl enable dnsmasq
    sudo systemctl start hostapd
    sudo systemctl start dnsmasq
else
    echo "[Fallback] Internet is working fine."
fi
