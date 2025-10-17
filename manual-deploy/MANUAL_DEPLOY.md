# Pi HID Bridge - Application

Turn a Raspberry Pi into a USB HID keyboard/mouse bridge with web-based control, passthrough, and custom key mapping.

**GitHub Repository:** [github.com/mcyork/keybird](https://github.com/mcyork/keybird)

---

## 📦 Installation

### 1. Install Pi Shell CLI (Optional but Recommended)

The deployment scripts use the **Pi Shell** tool (pip installable):

```bash
# Install Pi Shell
pip install pi-shell

# Verify installation
pi-shell --help
```

**Add your Pi with SSH key authentication (recommended):**

```bash
# Add your Pi (--push-key sets up password-less SSH)
pi-shell add mypi --host 192.168.1.50 --user pi --password raspberry --push-key

# Verify it's added and online
pi-shell status mypi

# Now you can use either:
pi-shell run "hostname" --pi mypi
# Or the symlink:
mypi run "hostname"
```

GitHub: [github.com/mcyork/pi-shell](https://github.com/mcyork/pi-shell)

### 2. Get Keybird

```bash
# Clone from GitHub
git clone https://github.com/mcyork/keybird.git
cd keybird/pi-hid-bridge

# Or download and extract
curl -L https://github.com/mcyork/keybird/archive/refs/heads/main.tar.gz | tar xz
cd keybird-main/pi-hid-bridge
```

---

## Quick Deploy

```bash
# From the pi-hid-bridge directory
./deploy.sh <pi-name>

# Example:
./deploy.sh keybird
```

See the main [README.md](../README.md) for complete documentation.

---

## Files

### Application
- **app/pi_kb.py** - Flask web app (~1,540 lines - refactored!)
  - Multi-keyboard/mouse pass-through
  - Web trackpad with calibration
  - Emulation profile management
  - Custom keyboard mappings
  - Learning mode
  - REST API

- **templates/index.html** - Jinja2 web UI template
  - Bootstrap 5 dark theme
  - Tabbed interface (Control, Learning, Mappings, Settings)
  - Responsive design

- **static/css/style.css** - Custom stylesheet
  - Bootstrap customizations
  - Trackpad styling
  - Dark theme enhancements

- **static/js/app.js** - Client-side JavaScript
  - Tab switching
  - API interactions
  - Real-time updates
  - Mouse/keyboard controls

- **requirements.txt** - Python dependencies
  - flask
  - evdev

### Scripts
- **scripts/setup_gadget_composite.sh** - Creates USB composite HID gadget
  - Keyboard (hidg0)
  - Consumer Control for media keys (hidg1)
  - Mouse (hidg2)

- **scripts/cleanup_gadget.sh** - Properly removes USB gadget
  - Unbinds UDC first
  - Removes all gadget components

- **scripts/gadget.conf** - USB gadget configuration
  - VID/PID values
  - Manufacturer/Product strings
  - Loaded by setup script

### Systemd Services
- **systemd/hid-gadget.service** - Auto-starts USB gadget on boot
- **systemd/pi-hid-bridge.service** - Auto-starts Flask app

### Deployment Scripts
- **deploy.sh** - Full deployment to fresh Pi
- **quick-start.sh** - Quick restart on already-deployed Pi

---

## Manual Deployment (Without Pi Shell)

If you don't have Pi Shell, you can deploy manually:

### 1. Prepare Pi

```bash
# SSH into Pi
ssh pi@<pi-ip>

# Create directory structure
mkdir -p /home/pi/pi-hid-bridge/{app,scripts,systemd,templates,static/css,static/js}
```

### 2. Upload Files

```bash
# From your local machine
scp -r app pi@<pi-ip>:/home/pi/pi-hid-bridge/
scp -r scripts pi@<pi-ip>:/home/pi/pi-hid-bridge/
scp -r systemd pi@<pi-ip>:/home/pi/pi-hid-bridge/
scp -r templates pi@<pi-ip>:/home/pi/pi-hid-bridge/
scp -r static pi@<pi-ip>:/home/pi/pi-hid-bridge/
scp requirements.txt pi@<pi-ip>:/home/pi/pi-hid-bridge/
```

### 3. Install on Pi

```bash
# SSH into Pi
ssh pi@<pi-ip>

# Install dependencies
sudo pip3 install -r /home/pi/pi-hid-bridge/requirements.txt --break-system-packages

# Make scripts executable
chmod +x /home/pi/pi-hid-bridge/scripts/*.sh

# Install systemd services
sudo cp /home/pi/pi-hid-bridge/systemd/*.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable hid-gadget.service
sudo systemctl enable pi-hid-bridge.service

# Configure boot for USB gadget mode
echo 'dtoverlay=dwc2,dr_mode=peripheral' | sudo tee -a /boot/firmware/config.txt
sudo sed -i 's/rootwait/rootwait modules-load=dwc2/' /boot/firmware/cmdline.txt

# Reboot
sudo reboot
```

### 4. After Reboot

Services start automatically. Connect USB-C cable and access web UI at:
```
http://<pi-ip>:8080
```

---

## Development

### Testing Changes Locally

Edit files locally, then upload:

```bash
# Python backend changes
keybird send app/pi_kb.py /home/pi/pi-hid-bridge/app/pi_kb.py
keybird run-stream 'sudo systemctl restart pi-hid-bridge.service'

# Web UI changes (HTML/CSS/JS) - No restart needed, just refresh browser
keybird send templates/index.html /home/pi/pi-hid-bridge/templates/index.html
keybird send static/css/style.css /home/pi/pi-hid-bridge/static/css/style.css
keybird send static/js/app.js /home/pi/pi-hid-bridge/static/js/app.js

# Without Pi Shell (manual)
scp app/pi_kb.py pi@<pi-ip>:/home/pi/pi-hid-bridge/app/
scp templates/index.html pi@<pi-ip>:/home/pi/pi-hid-bridge/templates/
scp static/css/style.css pi@<pi-ip>:/home/pi/pi-hid-bridge/static/css/
scp static/js/app.js pi@<pi-ip>:/home/pi/pi-hid-bridge/static/js/
ssh pi@<pi-ip> 'sudo systemctl restart pi-hid-bridge.service'
```

### Viewing Logs

```bash
# With Pi Shell
keybird run-stream 'sudo journalctl -u pi-hid-bridge.service -f'

# Without Pi Shell
ssh pi@<pi-ip> 'sudo journalctl -u pi-hid-bridge.service -f'
```

### Testing USB Gadget

```bash
# Check devices created
ls -la /dev/hidg*

# Check USB state
cat /sys/class/udc/*/state
# Should show: "configured"

# Manually recreate gadget
sudo bash /home/pi/pi-hid-bridge/scripts/cleanup_gadget.sh
sudo bash /home/pi/pi-hid-bridge/scripts/setup_gadget_composite.sh
```

---

## API Documentation

See main [README.md](../README.md) for complete API reference.

Quick examples:

```bash
# Send text
curl -X POST http://<pi-ip>:8080/send_text \
  -H 'Content-Type: application/json' \
  -d '{"text": "Hello, world!"}'

# Mouse click
curl -X POST http://<pi-ip>:8080/mouse_click \
  -H 'Content-Type: application/json' \
  -d '{"button": "left"}'

# Check status
curl http://<pi-ip>:8080/usb_status
```

---

## File Sizes

| File | Lines | Purpose |
|------|-------|---------|
| app/pi_kb.py | ~1,540 | Flask backend (46% reduction from refactoring!) |
| templates/index.html | ~320 | Bootstrap 5 web UI template |
| static/js/app.js | ~720 | Client-side JavaScript |
| static/css/style.css | ~90 | Custom styles |
| setup_gadget_composite.sh | 112 | USB gadget creation |
| cleanup_gadget.sh | 39 | USB gadget removal |
| gadget.conf | 9 | VID/PID configuration |
| requirements.txt | 2 | Python dependencies |

---

## Documentation

All feature documentation is in the main [README.md](../README.md):
- Web UI tabs (Control, Learning, Mappings, Settings)
- YubiKey suppression
- Trackpad calibration
- Profile switching
- Complete API reference

---

## Support

For issues, see:
- Main [README.md](../README.md) - Complete documentation including deployment, troubleshooting, and backup
- [UNINSTALL.md](../docs/UNINSTALL.md) - Clean removal
