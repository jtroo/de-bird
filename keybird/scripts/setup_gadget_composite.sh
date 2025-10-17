#!/usr/bin/env bash
set -euo pipefail

# Composite HID Gadget: Keyboard + Consumer Control (for media keys)
# Creates /dev/hidg0 (keyboard) and /dev/hidg1 (consumer/media)

# --- CONFIG ---
# Load from config file if it exists
CONFIG_FILE="$(dirname "$0")/gadget.conf"
if [ -f "$CONFIG_FILE" ]; then
    echo "📄 Loading config from $CONFIG_FILE"
    source "$CONFIG_FILE"
fi

# Fallback defaults (if not in config file or env)
: "${PI_PRODUCT:=Dell WK636 Keyboard}"
: "${PI_MANUFACTURER:=Logitech}"
: "${PI_SERIAL:=Pi5KB$(hexdump -n4 -e '4/1 "%02X"' /dev/urandom)}"
: "${VID:=0x046d}"
: "${PID:=0x4049}"

modprobe libcomposite
G=/sys/kernel/config/usb_gadget/g1

# Check if gadget already exists and is bound
if [ -f "$G/UDC" ] && [ -n "$(cat $G/UDC 2>/dev/null)" ]; then
  echo "✅ USB HID gadget already running"
  exit 0
fi

# Clean up any partial gadget config
if [ -d "$G" ]; then
  echo "Cleaning up existing gadget config..."
  [ -f "$G/UDC" ] && echo "" > "$G/UDC" 2>/dev/null || true
  rm -f "$G/configs/c.1/hid.usb0" 2>/dev/null || true
  rm -f "$G/configs/c.1/hid.usb1" 2>/dev/null || true
  rm -rf "$G/functions/hid.usb0" 2>/dev/null || true
  rm -rf "$G/functions/hid.usb1" 2>/dev/null || true
  rmdir "$G/configs/c.1/strings/0x409" 2>/dev/null || true
  rmdir "$G/configs/c.1" 2>/dev/null || true
  rm -rf "$G/strings/0x409" 2>/dev/null || true
  rmdir "$G" 2>/dev/null || true
fi

mkdir -p "$G"
cd "$G"

echo $VID > idVendor
echo $PID > idProduct
echo 0x0100 > bcdDevice
echo 0x0200 > bcdUSB

mkdir -p strings/0x409
echo "$PI_SERIAL" > strings/0x409/serialnumber
echo "$PI_MANUFACTURER" > strings/0x409/manufacturer
echo "$PI_PRODUCT" > strings/0x409/product

mkdir -p configs/c.1
echo 250 > configs/c.1/MaxPower

# ----- Function 1: Keyboard HID (boot keyboard) -----
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol     # keyboard
echo 1 > functions/hid.usb0/subclass     # boot
echo 8 > functions/hid.usb0/report_length

# Boot keyboard descriptor (8-byte reports)
printf '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc

# ----- Function 2: Consumer Control HID (media keys) -----
mkdir -p functions/hid.usb1
echo 0 > functions/hid.usb1/protocol     # none
echo 0 > functions/hid.usb1/subclass     # none
echo 3 > functions/hid.usb1/report_length  # 3 bytes for consumer control

# Consumer control descriptor (volume, mute, play/pause, etc.)
# Report ID (1 byte) + Usage (2 bytes, little-endian)
printf '\x05\x0C\x09\x01\xA1\x01\x85\x01\x19\x00\x2A\x3C\x02\x15\x00\x26\xFF\x03\x75\x10\x95\x01\x81\x00\xC0' > functions/hid.usb1/report_desc

# ----- Function 3: Mouse HID (3-button + wheel) -----
mkdir -p functions/hid.usb2
echo 2 > functions/hid.usb2/protocol     # mouse
echo 1 > functions/hid.usb2/subclass     # boot
echo 4 > functions/hid.usb2/report_length  # 4 bytes: buttons, X, Y, wheel

# Boot mouse descriptor (3 buttons, X/Y relative, wheel)
# Report: [buttons, X, Y, wheel]
printf '\x05\x01\x09\x02\xA1\x01\x09\x01\xA1\x00\x05\x09\x19\x01\x29\x03\x15\x00\x25\x01\x95\x03\x75\x01\x81\x02\x95\x01\x75\x05\x81\x01\x05\x01\x09\x30\x09\x31\x09\x38\x15\x81\x25\x7F\x75\x08\x95\x03\x81\x06\xC0\xC0' > functions/hid.usb2/report_desc

# Link all three functions to config
ln -s functions/hid.usb0 configs/c.1/
ln -s functions/hid.usb1 configs/c.1/
ln -s functions/hid.usb2 configs/c.1/

# Bind UDC
UDC=$(ls /sys/class/udc | head -n1 || true)
if [ -z "$UDC" ]; then
  echo "No UDC found. Make sure USB is in peripheral mode (see config.txt overlay)." >&2
  exit 1
fi
echo "$UDC" > UDC

# Permissions
chgrp -f plugdev /dev/hidg* 2>/dev/null || true
chmod 660 /dev/hidg* 2>/dev/null || true

echo "✅ Composite USB HID gadget ready (VID=$VID PID=$PID)"
echo "   /dev/hidg0 = Keyboard"
echo "   /dev/hidg1 = Consumer Control (media keys)"
echo "   /dev/hidg2 = Mouse"

