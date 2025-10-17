# Uninstalling Keybird

## Complete Removal

Keybird makes system-level changes that `pip uninstall` alone won't remove. Follow these steps for complete cleanup:

### 1. Run the Uninstall Script

```bash
sudo keybird-uninstall
```

This removes:
- ✅ USB gadget configuration from boot files
- ✅ Systemd services
- ✅ Installed scripts in `/opt/keybird/`
- ✅ Active HID devices

**Preserves** (in case you reinstall):
- 💾 `/home/pi/keyboard_profiles.json`
- 💾 `/home/pi/keyboard_mappings.json`
- 💾 `/home/pi/trackpad_calibrations.json`

### 2. Remove Python Package

```bash
sudo pip uninstall keybird
```

### 3. Reboot (Apply Boot Changes)

```bash
sudo reboot
```

---

## Optional: Remove Saved Data

If you want to completely remove all Keybird data:

```bash
# After uninstalling
rm /home/pi/keyboard_profiles.json
rm /home/pi/keyboard_mappings.json
rm /home/pi/trackpad_calibrations.json
```

---

## Manual Uninstall (Without keybird-uninstall)

If the uninstall command isn't available:

### 1. Stop Services

```bash
sudo systemctl stop pi-hid-bridge.service
sudo systemctl stop hid-gadget.service
sudo systemctl disable pi-hid-bridge.service
sudo systemctl disable hid-gadget.service
```

### 2. Remove Service Files

```bash
sudo rm /etc/systemd/system/hid-gadget.service
sudo rm /etc/systemd/system/pi-hid-bridge.service
sudo systemctl daemon-reload
```

### 3. Remove Boot Configuration

Edit `/boot/firmware/config.txt` (or `/boot/config.txt`):
```bash
sudo nano /boot/firmware/config.txt
# Remove line: dtoverlay=dwc2,dr_mode=peripheral
```

Edit `/boot/firmware/cmdline.txt` (or `/boot/cmdline.txt`):
```bash
sudo nano /boot/firmware/cmdline.txt
# Remove: modules-load=dwc2,g_hid
```

### 4. Remove Installed Files

```bash
sudo rm -rf /opt/keybird/
```

### 5. Uninstall Python Package

```bash
sudo pip uninstall keybird
```

### 6. Reboot

```bash
sudo reboot
```

---

## Verify Clean Removal

After uninstall and reboot:

```bash
# USB gadget should be gone
ls /sys/class/udc/*/state
# Should show: No such file or directory

# HID devices should be gone
ls /dev/hidg*
# Should show: No such file or directory

# Services should be gone
systemctl status pi-hid-bridge.service
# Should show: Unit not found

# Package should be gone
which keybird-server
# Should show: nothing
```

---

## Reinstalling After Uninstall

If you want to reinstall Keybird after uninstalling:

```bash
sudo pip install keybird
sudo keybird-setup
sudo reboot
```

Your saved profiles/mappings will be preserved if you didn't delete them! 🔄

