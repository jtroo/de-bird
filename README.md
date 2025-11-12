# Keybird v1.0.5

**Transform your Raspberry Pi into a professional USB keyboard, mouse, and media controller with web-based management.**

Control a computer from another computer, customize per-keyboard mappings, suppress keys or functions that auto-enter, and manage everything through a modern Bootstrap 5 dark theme web interface. But why does this exist [BHB.bzz](https://bhb.buzz/keybird.html)

**🔗 GitHub:** [github.com/mcyork/keybird](https://github.com/mcyork/keybird)

---

## 🎯 What Is This?

The Pi HID Bridge turns a Raspberry Pi into a **composite USB HID device** that emulates:
- ⌨️ **Keyboard** with 100+ mapped keys
- 🖱️ **Mouse** with 3 buttons + scroll wheel
- 🎵 **Media keys** (volume, play/pause, etc.)

**Plus unique features:**
- 🎹 **Multi-keyboard pass-through** - Monitor YubiKey, Dell, Apple, Microsoft keyboards simultaneously
- 🔧 **Per-keyboard custom mappings** - YubiKey Enter suppression, key remapping, text macros
- 📋 **Emulation profile switching** - Pretend to be different keyboard models
- 🖱️ **Web trackpad** with automatic calibration for different displays
- 🌐 **Web UI** - Control from laptop, phone, or tablet

---

## ⚡ Quick Start (2 Minutes)

### Prerequisites

- **Raspberry Pi 4 Model B** (tested and validated)
  - Full functionality including keyboard pass-through
- **Raspberry Pi Zero 2 W** (tested and validated)
  - ⚠️ Keyboard functionality only - no pass-through capability due to single USB port hardware limitation
- ⚠️ **NOT compatible with Pi 5** (USB gadget mode unresolved issues)
- **USB-C data cable** - Must support data, not just charging (Pi 4B)
- **Micro-USB data cable** - Must support data, not just charging (Pi Zero 2 W)
  - Pi connected to network (WiFi or Ethernet)
  - Pi has SSH enabled (default on Raspberry Pi OS)

### Deploy from Your Computer (No SSH login needed!)

```bash
# 1. Install pi-shell and keybird on YOUR COMPUTER
pip install pi-shell keybird

# 2. Add your Pi (one-time setup with password-less SSH)
pi-shell add mypi --host 192.168.1.50 --user pi --password raspberry --push-key

# 3. Deploy to Pi (single command!)
keybird-deploy mypi
```

**Done!** 🎉 Access web UI at `http://192.168.1.50:8080`

> **📦 Note:** Keybird not yet on PyPI. For now, install from source:
> ```bash
> pip install pi-shell
> git clone https://github.com/mcyork/keybird.git
> cd keybird
> pip install .
> pi-shell add mypi --host 192.168.1.50 --user pi --password raspberry --push-key
> keybird-deploy mypi
> ```

### What Gets Installed

✅ **Flask web app** with Bootstrap 5 dark theme UI  
✅ **USB HID gadget** (keyboard + mouse + media keys)  
✅ **Systemd services** (auto-start on boot)  
✅ **Boot configuration** (enables USB gadget mode)  
✅ **Dependencies** (flask, evdev)

### Manual Deployment (See Under the Hood)

Want transparency? See **[manual-deploy/README.md](manual-deploy/README.md)** for step-by-step SSH deployment.

---

## Post-Installation

### Connect Hardware

Connect your Pi's **USB-C port** to your target computer's USB port.

### Access Web UI

```bash
open http://<pi-ip>:8080
```

**Done!** 🎉

---

## 🎹 Core Features

### Multi-Keyboard Pass-Through

> **Note:** This feature requires **Raspberry Pi 4 Model B** (Pi Zero 2 W lacks physical USB host ports for keyboards)

**Monitor all keyboards at once:**
- YubiKey NEO
- Dell WK636 Wireless Keyboard  
- Apple Magic Keyboard
- Microsoft keyboards
- Any USB keyboard

Each keyboard can have its own custom key mappings!

**Example:** Suppress YubiKey's auto-Enter key while keeping Enter normal on other keyboards.

### Emulation Profile Switching

**Pretend to be different keyboards:**
- Dell WK636 (VID: 046d, PID: c52b)
- Apple Magic Keyboard (VID: 05ac, PID: 029f)
- Logitech Unifying Receiver (VID: 046d, PID: 4049)
- Any keyboard you clone!

**Why?** Some software only works with specific keyboard models. Clone the required keyboard and switch profiles as needed.

### Mouse Control

**Two ways to control the mouse:**

1. **Web Trackpad** - Beautiful 500x350px trackpad in browser
   - Click on trackpad → sends click to target PC
   - Move in trackpad → cursor moves
   - Right-click → context menu
   - Scroll wheel → page scrolling
   - Auto-calibration for your display size

2. **Physical Mouse Pass-Through** - Plug real mice into Pi
   - Forwards all movements and clicks
   - Multi-mouse support
   - Zero latency

### Per-Keyboard Custom Mappings

**Three mapping types:**

1. **HID Remap** - Map key X to key Y
   - Example: Map F13 to Print Screen

2. **Text Replacement** - Map key to type text
   - Example: Map F14 to type "show ip interface brief"

3. **Suppress** - Ignore specific keys
   - Example: Suppress Enter key on YubiKey only

**Management UI:**
- Select keyboard from dropdown
- View all mappings in table
- Add/Edit/Delete mappings
- Export/Import for backup

---

## 📱 Web Interface

Access at `http://<pi-ip>:8080`

**Modern Bootstrap 5 dark theme with tabbed interface:**

### Header Controls (Always Visible)
- **Status Bar:** USB connection and emulation profile status
- **Mode Toggles:** Keyboard and mouse pass-through switches
- **Quick Actions:** Reboot button

### Tab 1: Control (Default)
- **Send Text:** Batch send text as keystrokes to connected computer
- **Trackpad:** Interactive mouse control with sensitivity and calibration

### Tab 2: Learning
- **Unmapped Keys:** Auto-detected unknown keys with one-click mapping
- **HID Reference:** Quick lookup for common HID codes

### Tab 3: Mappings
- **Keyboard Management:** Select any connected keyboard
- **Custom Mappings:** Suppress keys, remap, or send text macros
- **Per-Keyboard Rules:** Different mappings for each physical device

### Tab 4: Settings
- **Emulation Profiles:** Switch which keyboard device the Pi pretends to be
- **Detected Keyboards:** See all physically connected keyboards
- **Export/Import:** Backup your profiles and mappings

---

## 🚀 Advanced Usage

### YubiKey Integration

**Problem:** YubiKey OTP mode sends Enter after password  
**Solution:** Suppress Enter key on YubiKey only

```
1. Go to Mappings tab
2. Select "Yubico Yubikey NEO OTP+U2F+CCID"
3. Add Mapping:
   - Key Code: 28 (Enter)
   - Action Type: 🚫 Suppress
4. Done! YubiKey outputs password without auto-submit
```

### Trackpad Calibration

**Problem:** Different screens need different sensitivities  
**Solution:** Calibrate for each display

```
1. Enable Mouse Pass-through toggle in header
2. Go to Control tab → Click 🎯 Calibrate button
3. Use physical mouse to click 4 corners of screen
4. Save as "Windows Desktop" or "MacBook Pro"
5. Disable mouse pass-through toggle
6. Use web trackpad with perfect sensitivity!
```

### Profile Switching

**Problem:** Some software requires specific keyboard models  
**Solution:** Clone and switch profiles

```
1. Plug target keyboard into Pi
2. Go to Settings tab → Detected Physical Keyboards
3. Click "Clone" button next to the keyboard
4. Pi reboots as that keyboard
5. Use Emulation Profile dropdown to switch between saved profiles anytime
```

### Multi-Computer Setup

**Best Practice with KVM:**

```
[Powered USB Hub] ← Constant power
      ↓
   [KVM] ← Switches USB data
      ↓
[Computer A] [Computer B] [Computer C]

Connected to hub:
- Raspberry Pi (via USB-C data cable)
  - Your keyboards
  - Your mice
- Microphone
- Other USB devices

Benefits:
- Pi stays powered (no reboot when switching)
- All devices switch together
- Web UI always accessible
- Different calibrations per computer
```

---

## 📦 What Gets Installed

### On the Pi

**Application Files:**
```
/home/pi/pi-hid-bridge/
├── app/pi_kb.py              # Flask app (2,850+ lines)
├── scripts/
│   ├── setup_gadget_composite.sh  # Creates USB gadget
│   ├── cleanup_gadget.sh          # Removes USB gadget
│   └── gadget.conf                # VID/PID configuration
├── systemd/
│   ├── hid-gadget.service         # Auto-start gadget
│   └── pi-hid-bridge.service      # Auto-start Flask
└── requirements.txt               # Python deps
```

**Runtime Data Files:**
```
/home/pi/
├── keyboard_profiles.json         # Emulation profiles
├── keyboard_mappings.json         # Per-keyboard custom mappings
└── trackpad_calibrations.json     # Trackpad calibrations
```

**System Configuration:**
```
/boot/firmware/config.txt          # dtoverlay=dwc2 added
/boot/firmware/cmdline.txt         # modules-load=dwc2 added
/etc/systemd/system/               # Services installed
```

**USB Devices Created:**
```
/dev/hidg0                         # Keyboard
/dev/hidg1                         # Consumer Control (media keys)
/dev/hidg2                         # Mouse
```

---

## 🛠️ Pi Shell CLI

This project uses **Pi Shell** - a pip-installable CLI tool for managing Raspberry Pis via SSH.

**Install:** `pip install pi-shell`  
**GitHub:** [github.com/mcyork/pi-shell](https://github.com/mcyork/pi-shell)

### Essential Commands

After adding your Pi with `pi-shell add mypi ...`, you can use the symlink:

```bash
# Check status
pi-shell status mypi

# Execute commands (streaming output)
mypi run-stream "command"

# Send files
mypi send /local/file /remote/path

# Read files
mypi read /remote/file > local-file

# List all Pis
pi-shell list
```

### Deployment Commands

```bash
# Deploy from scratch
keybird-deploy mypi

# Quick restart (already deployed)
cd keybird/manual-deploy
./quick-start.sh mypi
```

---

## 🔌 Hardware Setup

### Raspberry Pi 4 Model B

**USB Ports:**
- **USB-C port** 
  - USB gadget output (connects to target computer)
- **4× USB-A ports** - Connect keyboards, mice, YubiKey, etc.
- **Ethernet** - Management network
- **Wi-Fi** - Wireless management (optional)

**Wiring:**
```
Target Computer USB Port
         ↓
    [USB-C Cable] ← Data + Power
         ↓
    Pi USB-C Port
    
Pi USB-A Ports:
    ├─ Keyboard 1 (Dell)
    ├─ Keyboard 2 (YubiKey)
    ├─ Mouse 1 (Logitech)
    └─ Mouse 2 (Microsoft)
```

**Power Options:**
1. **Via USB-C from target** - If target provides enough power
2. **Via GPIO pins** - 5V to pins 2/4, GND to pin 6
3. **PoE HAT** - Power over Ethernet

---

## 📚 Documentation

### Getting Started
- **[Manual Deployment README](manual-deploy/README.md)** - Deploy without pip install
- **[Manual Deployment Guide](manual-deploy/MANUAL_DEPLOY.md)** - Step-by-step SSH deployment

### Maintenance
- **[Uninstall Guide](docs/UNINSTALL.md)** - Complete removal instructions

---

## 🐛 Troubleshooting

### USB Not Connecting

**Check USB status:**
```bash
mypi run-stream 'cat /sys/class/udc/*/state'
```

**Should show:** `configured`  
**If shows:** `not attached` → Check USB cable is data-capable

**Manually recreate gadget:**
```bash
mypi run-stream 'sudo systemctl restart hid-gadget.service'
```

### Services Won't Start

**Check logs:**
```bash
mypi run-stream 'sudo journalctl -u pi-hid-bridge.service -n 50'
mypi run-stream 'sudo journalctl -u hid-gadget.service -n 50'
```

**Manual restart:**
```bash
mypi run-stream 'sudo systemctl restart hid-gadget.service'
mypi run-stream 'sudo systemctl restart pi-hid-bridge.service'
```

### Keyboard Pass-Through Not Working

**Check keyboards detected:**
```bash
curl http://<pi-ip>:8080/detected_keyboards
```

**Enable pass-through:**
- Open web UI
- Toggle "Keyboard Pass-through" in header

**Check logs:**
```bash
mypi run-stream 'sudo journalctl -u pi-hid-bridge.service -f'
```

### Mouse Not Working

**Check mouse devices exist:**
```bash
mypi run-stream 'ls -la /dev/hidg*'
```

**Should see:** `/dev/hidg0`, `/dev/hidg1`, `/dev/hidg2`

**If missing hidg2:**
```bash
mypi run-stream 'sudo systemctl restart hid-gadget.service'
```

### Web UI Not Loading

**Check Flask is running:**
```bash
mypi run-stream 'sudo systemctl status pi-hid-bridge.service'
```

**Check it's listening:**
```bash
mypi run-stream 'sudo ss -tlnp | grep 8080'
```

**View live logs:**
```bash
mypi run-stream 'sudo journalctl -u pi-hid-bridge.service -f'
```

---

## 🔄 Updating & Backup

### Update Python Backend

```bash
mypi send app/pi_kb.py /home/pi/pi-hid-bridge/app/pi_kb.py
mypi run-stream 'sudo systemctl restart pi-hid-bridge.service'
```

### Update Web UI (No Restart Needed)

```bash
mypi send templates/index.html /home/pi/pi-hid-bridge/templates/index.html
mypi send static/css/style.css /home/pi/pi-hid-bridge/static/css/style.css
mypi send static/js/app.js /home/pi/pi-hid-bridge/static/js/app.js
# Just refresh browser
```

### Backup Profiles and Mappings

```bash
# Download from Pi
mypi read /home/pi/keyboard_profiles.json > backup_profiles.json
mypi read /home/pi/keyboard_mappings.json > backup_mappings.json
mypi read /home/pi/trackpad_calibrations.json > backup_calibrations.json
```

Or use Web UI → Export buttons.

### Restore Backups

```bash
# Upload to Pi
mypi send backup_profiles.json /home/pi/keyboard_profiles.json
mypi send backup_mappings.json /home/pi/keyboard_mappings.json
mypi send backup_calibrations.json /home/pi/trackpad_calibrations.json

# Restart service
mypi run-stream 'sudo systemctl restart pi-hid-bridge.service'
```

### Full Re-Deploy

```bash
keybird-deploy mypi
```

---

## 🌐 API Reference

### Health Check
```bash
GET /health
```

### USB Status
```bash
GET /usb_status
# Returns: {"state": "configured", "attached": true}
```

### Keyboard Pass-Through
```bash
GET /passthrough
# Check status

POST /passthrough
# Body: {"enabled": true}
# Toggle on/off
```

### Mouse Pass-Through
```bash
GET /mouse_passthrough
POST /mouse_passthrough
# Body: {"enabled": true}
```

### Mouse Control
```bash
POST /mouse_move
# Body: {"dx": 10, "dy": -5, "buttons": 0, "wheel": 0}

POST /mouse_click
# Body: {"button": "left"}  # or "right", "middle"
```

### Send Text
```bash
POST /send_text
# Body: {"text": "Hello, world!"}
```

### Detected Keyboards
```bash
GET /detected_keyboards
# Returns list of physical keyboards with VID/PID
```

### Detected Mice
```bash
GET /detected_mice
# Returns list of physical mice
```

### Emulation Profiles
```bash
GET /emulation_profiles
# List all saved profiles

POST /emulation_profiles/switch
# Body: {"profile_id": "logitech_4049"}
```

### Keyboard Mappings
```bash
GET /keyboard_mappings/all
# List all keyboards with mappings

GET /keyboard_mappings/<kbd_id>
# Get specific keyboard's mappings

POST /keyboard_mappings/<kbd_id>/mapping
# Body: {"code": 28, "type": "suppress"}

DELETE /keyboard_mappings/<kbd_id>/mapping/<code>
```

### Trackpad Calibration
```bash
POST /calibration/start
# Start calibration process

GET /calibration/status
# Check calibration progress

POST /calibration/save
# Body: {"name": "Windows Desktop", "sensitivity": 3.2, "points": [...]}

GET /calibrations
# List all saved calibrations

POST /calibrations/<cal_id>/activate
# Activate a calibration profile
```

### System Control
```bash
POST /reboot
# Reboot the Pi
```

---

## 📖 Detailed Documentation

### Getting Started
- Read **DEPLOYMENT_QUICK_REFERENCE.md** for deployment cheat sheet
- Read **DEPLOYMENT_GUIDE.md** for detailed manual deployment

### Feature Guides
- **LEARNING_MODE_GUIDE.md** - Map unknown keys interactively
- **YUBIKEY_SUPPRESS_EXAMPLE.md** - Suppress YubiKey Enter key
- **MOUSE_CONTROL_GUIDE.md** - Use the web trackpad
- **TRACKPAD_CALIBRATION_GUIDE.md** - Calibrate for your display
- **PROFILES_AND_MAPPINGS.md** - Understand emulation vs mappings

### Advanced Topics
- **KEYBOARD_VENDOR_NOTES.md** - Why Dell keyboards show as Logitech
- **MOUSE_PASSTHROUGH_GUIDE.md** - Physical mouse forwarding
- **FINDINGS.md** - Pi 5 USB gadget investigation

---

## 🏗️ Architecture

### Components

```
┌─────────────────────────────────────────────────┐
│           Target Computer (Windows/Mac/Linux)    │
│                        ▲                         │
│                        │ USB HID                 │
└────────────────────────┼─────────────────────────┘
                         │
                    USB-C Cable
                         │
┌────────────────────────▼─────────────────────────┐
│              Raspberry Pi 4 Model B              │
│  ┌───────────────────────────────────────────┐  │
│  │  Composite USB HID Gadget                 │  │
│  │  - /dev/hidg0 (Keyboard)                  │  │
│  │  - /dev/hidg1 (Consumer Control)          │  │
│  │  - /dev/hidg2 (Mouse)                     │  │
│  └───────────────────────────────────────────┘  │
│                      ▲                           │
│                      │                           │
│  ┌───────────────────┴───────────────────────┐  │
│  │         Flask Web App (pi_kb.py)          │  │
│  │  - Keyboard pass-through                  │  │
│  │  - Mouse pass-through                     │  │
│  │  - Custom mappings engine                 │  │
│  │  - Profile management                     │  │
│  │  - Calibration system                     │  │
│  │  - Web UI server                          │  │
│  └───────────────────┬───────────────────────┘  │
│                      │                           │
│                      │ evdev                     │
│                      ▼                           │
│  ┌──────────────────────────────────────────┐   │
│  │     Physical Input Devices               │   │
│  │  - Keyboards (YubiKey, Dell, Apple...)   │   │
│  │  - Mice (Logitech, Microsoft...)         │   │
│  └──────────────────────────────────────────┘   │
│                                                  │
│  Network: Ethernet + Wi-Fi ◄─── Web Browser     │
└──────────────────────────────────────────────────┘
```

### Data Flow

**Keyboard Pass-Through:**
```
Physical Keyboard → evdev → Pi → Custom Mappings → HID Report → Target PC
```

**Web Trackpad:**
```
Browser → HTTP → Pi → Calibration → HID Report → Target PC
```

**Profile Switching:**
```
User Selection → Update gadget.conf → Reboot → New VID/PID → Target PC sees different keyboard
```

---

## 🤝 Contributing

This is a personal project, but suggestions welcome!

**Areas for improvement:**
- Additional mapping types (delays, sequences)
- Drag-and-drop mouse support
- Encrypted macro implementation
- AI command generation
- GamePad emulation

---

## 📜 License

Personal project - use at your own risk!

---

## 🙏 Acknowledgments

Built with:
- **Flask** - Web framework
- **evdev** - Linux input device interface
- **Python** - Glue holding it all together
- **Pi Shell** - Pi management CLI ([github.com/mcyork/pi-shell](https://github.com/mcyork/pi-shell))

Inspired by Black Hat Booze (https://bhb.buzz) and the deep obsession with the distilation process - be it for spirits or code.
---

## 🗑️ Uninstalling

Keybird makes system-level changes that need proper cleanup:

```bash
# Complete removal (cleans everything)
sudo keybird-uninstall

# Then remove Python package
sudo pip uninstall keybird

# Reboot to apply boot config changes
sudo reboot
```

The uninstall script removes:
- ✅ USB gadget configuration (boot files)
- ✅ Systemd services  
- ✅ Installed files in `/opt/keybird/`

**Preserves** (in case you reinstall):
- 💾 Saved profiles, mappings, calibrations in `/home/pi/`

See **[UNINSTALL.md](docs/UNINSTALL.md)** for manual uninstall steps.

---

## 🆘 Support

**Check logs:**
```bash
sudo journalctl -u pi-hid-bridge.service -f
```

**Reset everything (pip install users):**
```bash
sudo systemctl restart hid-gadget.service
sudo systemctl restart pi-hid-bridge.service
```

**Reset everything (manual deploy users):**
```bash
cd keybird/manual-deploy
./quick-start.sh mypi
```

---

## 🚀 Version History

- **v1.0.5** (Nov 2025) - **Listen Mode & Branding**: Added key listening mode for easy keyboard mapping, auto-start pass-through on boot, keyboard deduplication, favicon integration, and rebranded to "Keybird"
- **v1.0.4** (Oct 2025) - **PyPI Fix**: Corrected package build to include touch support for iPhone/iPad trackpad
- **v1.0.3** (Oct 2025) - **Mobile Support**: Added touch support for iPhone/iPad trackpad - touch to move cursor, tap to click, two-finger right-click
- **v1.0.2** (Oct 2025) - **Modernization**: Updated to Python 3.10+, replaced deprecated pkg_resources with importlib.resources
- **v1.0.1** (Oct 2025) - **Bug fix**: Fixed silent crash in keyboard pass-through mode
- **v1.0** (Oct 2025) - Initial release with keyboard pass-through, web UI, mouse control, trackpad calibration, multi-keyboard support, profiles, per-keyboard mappings, and YubiKey support
- **v0.1** (Oct 2025) - Initial prototype

---

**Ready to control your computers like a pro? Deploy and enjoy!** 🎮
