#!/usr/bin/env bash
set -euo pipefail

# --- CONFIG (optionally export these before calling) ---
: "${PI_PRODUCT:=Dell WK636 Keyboard}"
: "${PI_MANUFACTURER:=Logitech}"
: "${PI_SERIAL:=Pi5KB$(hexdump -n4 -e '4/1 "%02X"' /dev/urandom)}"
: "${VID:=0x046d}"      # Logitech (Dell keyboard)
: "${PID:=0x4049}"      # Dell WK636

# To use default Linux Foundation IDs instead:
# export VID=0x1d6b
# export PID=0x0104

modprobe libcomposite
G=/sys/kernel/config/usb_gadget/g1

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

# ----- Keyboard HID function (boot keyboard)
mkdir -p functions/hid.usb0
echo 1 > functions/hid.usb0/protocol     # keyboard
echo 1 > functions/hid.usb0/subclass     # boot
echo 8 > functions/hid.usb0/report_length

# Report descriptor (boot keyboard, 8-byte reports)
# IMPORTANT: Use printf to write actual binary data, not echo!
printf '\x05\x01\x09\x06\xa1\x01\x05\x07\x19\xe0\x29\xe7\x15\x00\x25\x01\x75\x01\x95\x08\x81\x02\x95\x01\x75\x08\x81\x03\x95\x06\x75\x08\x15\x00\x25\x65\x05\x07\x19\x00\x29\x65\x81\x00\xc0' > functions/hid.usb0/report_desc

ln -s functions/hid.usb0 configs/c.1/

# Bind UDC
UDC=$(ls /sys/class/udc | head -n1 || true)
if [ -z "$UDC" ]; then
  echo "No UDC found. Make sure USB is in peripheral mode (see config.txt overlay)." >&2
  exit 1
fi
echo "$UDC" > UDC

# Permissions for /dev/hidg0 (udev rule can also do this)
chgrp -f plugdev /dev/hidg0 2>/dev/null || true
chmod 660 /dev/hidg0 2>/dev/null || true

echo "USB HID gadget ready (VID=$VID PID=$PID, product='$PI_PRODUCT')"

