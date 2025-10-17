#!/usr/bin/env bash
# Quick start script - run gadget setup and Flask app
# Usage: ./quick-start.sh <pi-name>

set -e

if [ $# -eq 0 ]; then
    echo "Usage: $0 <pi-name>"
    echo "Example: $0 keybird"
    echo ""
    echo "Available Pis:"
    pi status
    exit 1
fi

PI_NAME=$1

echo "🚀 Starting Pi HID Bridge on $PI_NAME..."
echo ""

# Setup composite gadget (keyboard + media + mouse)
echo "🔧 Setting up USB HID composite gadget..."
$PI_NAME run-stream "sudo bash /home/pi/pi-hid-bridge/scripts/cleanup_gadget.sh 2>/dev/null || true"
sleep 1
$PI_NAME run-stream "sudo bash /home/pi/pi-hid-bridge/scripts/setup_gadget_composite.sh"

echo ""

# Restart Flask service
echo "🌐 Restarting Flask web app..."
$PI_NAME run-stream "sudo systemctl restart pi-hid-bridge.service"

sleep 3

# Get Pi IP
PI_IP=$($PI_NAME run-stream "hostname -I | awk '{print \$1}'")

echo ""
echo "✅ Pi HID Bridge is running!"
echo ""
echo "📱 Web UI: http://$PI_IP:8080"
echo ""
echo "🔌 Check USB Status:"
echo "   $PI_NAME run-stream 'cat /sys/class/udc/*/state'"
echo ""
echo "📋 View Logs:"
echo "   $PI_NAME run-stream 'sudo journalctl -u pi-hid-bridge.service -f'"
echo ""
echo "🎹 Available features:"
echo "   - Keyboard pass-through (auto-enabled)"
echo "   - Mouse pass-through"
echo "   - Web trackpad with calibration"
echo "   - Keyboard mappings management"
echo "   - Emulation profile switching"
echo ""
