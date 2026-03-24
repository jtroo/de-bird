#!/usr/bin/env bash
# Cleanup USB gadget properly

G=/sys/kernel/config/usb_gadget/g1

if [ ! -d "$G" ]; then
  echo "No gadget to clean up."
  exit 0
fi

cd "$G"

# Step 1: Unbind UDC
if [ -f "UDC" ]; then
  echo "" > UDC 2>/dev/null || true
fi

# Step 2: Remove symlinks from configs
rm -f configs/c.1/hid.usb* 2>/dev/null || true

# Step 3: Remove config directories
rmdir configs/c.1/strings/0x409 2>/dev/null || true
rmdir configs/c.1 2>/dev/null || true

# Step 4: Remove function directories  
rmdir functions/hid.usb* 2>/dev/null || true

# Step 5: Remove string directories
rmdir strings/0x409 2>/dev/null || true

# Step 6: Remove other directories
rmdir webusb os_desc 2>/dev/null || true

# Step 7: Remove gadget
cd ..
rmdir g1 2>/dev/null || true

echo "✅ Gadget cleaned up"
