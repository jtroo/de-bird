#!/usr/bin/env bash
# Pi HID Bridge Deployment Script v2.0
# Usage: ./deploy.sh <pi-name>
# Example: ./deploy.sh keybird

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
REMOTE_PATH="/home/pi/pi-hid-bridge"

echo "🚀 Deploying Pi HID Bridge v2.0 to $PI_NAME..."
echo ""

# Check if Pi is online
echo "📡 Checking if $PI_NAME is online..."
if ! pi run-stream --pi $PI_NAME "echo 'Connected'" > /dev/null 2>&1; then
    echo "❌ Error: Cannot connect to $PI_NAME"
    echo "   Check that the Pi is online with: pi status"
    exit 1
fi

# Get Pi model and IP
echo "🔍 Detecting Pi model..."
PI_MODEL=$(pi run-stream --pi $PI_NAME "cat /proc/device-tree/model 2>/dev/null || echo 'Unknown'")
PI_IP=$(pi run-stream --pi $PI_NAME "hostname -I | awk '{print \$1}'")
echo "   Model: $PI_MODEL"
echo "   IP: $PI_IP"
echo ""

# Check if Pi 5
if [[ "$PI_MODEL" == *"Pi 5"* ]] || [[ "$PI_MODEL" == *"Raspberry Pi 5"* ]]; then
    echo "⚠️  WARNING: Raspberry Pi 5 detected!"
    echo "   USB gadget mode is currently non-functional on Pi 5."
    echo "   This deployment will complete, but USB output won't work."
    echo "   Recommend using Pi 4, Pi Zero 2 W, or earlier models."
    echo ""
    read -p "   Continue anyway? (y/N) " -n 1 -r
    echo
    if [[ ! $REPLY =~ ^[Yy]$ ]]; then
        exit 1
    fi
fi

# Create directory structure
echo "📁 Creating directory structure..."
pi run-stream --pi $PI_NAME "mkdir -p $REMOTE_PATH/{app,scripts,systemd,templates,static/css,static/js}"

# Upload application files
echo "📤 Uploading application files..."
pi send --pi $PI_NAME requirements.txt $REMOTE_PATH/requirements.txt
pi send --pi $PI_NAME app/pi_kb.py $REMOTE_PATH/app/pi_kb.py

# Upload web UI files
echo "📤 Uploading web UI templates and static files..."
pi send --pi $PI_NAME templates/index.html $REMOTE_PATH/templates/index.html
pi send --pi $PI_NAME static/css/style.css $REMOTE_PATH/static/css/style.css
pi send --pi $PI_NAME static/js/app.js $REMOTE_PATH/static/js/app.js

# Upload scripts
echo "📤 Uploading scripts..."
pi send --pi $PI_NAME scripts/setup_gadget_composite.sh $REMOTE_PATH/scripts/setup_gadget_composite.sh
pi send --pi $PI_NAME scripts/cleanup_gadget.sh $REMOTE_PATH/scripts/cleanup_gadget.sh
pi send --pi $PI_NAME scripts/gadget.conf $REMOTE_PATH/scripts/gadget.conf

# Upload systemd services
echo "📤 Uploading systemd services..."
pi send --pi $PI_NAME systemd/hid-gadget.service $REMOTE_PATH/systemd/hid-gadget.service
pi send --pi $PI_NAME systemd/pi-hid-bridge.service $REMOTE_PATH/systemd/pi-hid-bridge.service

# Make scripts executable
echo "🔧 Setting permissions..."
pi run-stream --pi $PI_NAME "chmod +x $REMOTE_PATH/scripts/*.sh"

# Install dependencies
echo "📦 Installing Python dependencies..."
pi run-stream --pi $PI_NAME "sudo pip3 install -r $REMOTE_PATH/requirements.txt --break-system-packages 2>&1 | grep -v 'Requirement already satisfied' || true"

# Configure boot config for USB gadget mode
echo "⚙️  Configuring USB gadget mode in boot config..."
pi run-stream --pi $PI_NAME "sudo cp /boot/firmware/config.txt /boot/firmware/config.txt.backup 2>/dev/null || sudo cp /boot/config.txt /boot/config.txt.backup || true"

# Check if dwc2 overlay already exists
if pi run-stream --pi $PI_NAME "grep -q 'dtoverlay=dwc2' /boot/firmware/config.txt 2>/dev/null || grep -q 'dtoverlay=dwc2' /boot/config.txt 2>/dev/null"; then
    echo "   ✓ dwc2 overlay already configured"
else
    echo "   Adding dwc2 overlay to config.txt..."
    pi run-stream --pi $PI_NAME "echo 'dtoverlay=dwc2,dr_mode=peripheral' | sudo tee -a /boot/firmware/config.txt >/dev/null 2>&1 || echo 'dtoverlay=dwc2,dr_mode=peripheral' | sudo tee -a /boot/config.txt >/dev/null"
fi

# Check if modules-load already in cmdline
if pi run-stream --pi $PI_NAME "grep -q 'modules-load=dwc2' /boot/firmware/cmdline.txt 2>/dev/null || grep -q 'modules-load=dwc2' /boot/cmdline.txt 2>/dev/null"; then
    echo "   ✓ modules-load already configured"
else
    echo "   Adding modules-load to cmdline.txt..."
    pi run-stream --pi $PI_NAME "sudo sed -i 's/rootwait/rootwait modules-load=dwc2,g_hid/' /boot/firmware/cmdline.txt 2>/dev/null || sudo sed -i 's/rootwait/rootwait modules-load=dwc2,g_hid/' /boot/cmdline.txt"
fi

# Install systemd services
echo "🔧 Installing systemd services..."
pi run-stream --pi $PI_NAME "sudo cp $REMOTE_PATH/systemd/hid-gadget.service /etc/systemd/system/"
pi run-stream --pi $PI_NAME "sudo cp $REMOTE_PATH/systemd/pi-hid-bridge.service /etc/systemd/system/"
pi run-stream --pi $PI_NAME "sudo systemctl daemon-reload"
pi run-stream --pi $PI_NAME "sudo systemctl enable hid-gadget.service"
pi run-stream --pi $PI_NAME "sudo systemctl enable pi-hid-bridge.service"

echo ""
echo "✅ Deployment complete!"
echo ""
echo "📋 What was deployed:"
echo "   ✅ Composite HID gadget (Keyboard + Media Keys + Mouse)"
echo "   ✅ Flask web app with all v2.0 features:"
echo "      - Multi-keyboard pass-through"
echo "      - Multi-mouse pass-through"
echo "      - Emulation profile switching"
echo "      - Per-keyboard custom mappings"
echo "      - Key suppression (YubiKey support)"
echo "      - Web trackpad with calibration"
echo "      - Learning mode & mapping management"
echo "   ✅ Systemd auto-start services"
echo "   ✅ Boot configuration for USB gadget mode"
echo ""
echo "📋 Next steps:"
echo "   1. Reboot the Pi:"
echo "      pi run-stream --pi $PI_NAME 'sudo reboot'"
echo ""
echo "   2. Wait ~30-45 seconds for reboot"
echo ""
echo "   3. Services will auto-start! Check status:"
echo "      pi run-stream --pi $PI_NAME 'sudo systemctl status hid-gadget.service'"
echo "      pi run-stream --pi $PI_NAME 'sudo systemctl status pi-hid-bridge.service'"
echo ""
echo "   4. Connect USB-C cable:"
echo "      Pi USB-C port → Target computer USB port"
echo ""
echo "   5. Open web UI:"
echo "      http://$PI_IP:8080"
echo ""
echo "💡 Features available:"
echo "   - Section 1: Keyboard pass-through (auto-enabled)"
echo "   - Section 2: Mouse pass-through"
echo "   - Section 3: Learning mode (map unknown keys)"
echo "   - Section 4: Web trackpad + calibration"
echo "   - Section 5: Keyboard mappings management"
echo "   - Section 6: Send bulk text"
echo ""
echo "🔧 Troubleshooting:"
echo "   - Check USB: pi run-stream --pi $PI_NAME 'cat /sys/class/udc/*/state'"
echo "   - View logs: pi run-stream --pi $PI_NAME 'sudo journalctl -u pi-hid-bridge.service -f'"
echo "   - List HID devices: pi run-stream --pi $PI_NAME 'ls -la /dev/hidg*'"
echo ""
