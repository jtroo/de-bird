# Manual Deployment Scripts

**For users who want to see under the hood or customize the deployment process.**

If you prefer the automated approach, see the [main README](../README.md) for pip installation.

---

## What's Here

These are the original deployment scripts that show exactly what happens during Keybird installation:

- **deploy.sh** - Full deployment to a fresh Raspberry Pi
- **quick-start.sh** - Quick restart of services on already-deployed Pi
- **MANUAL_DEPLOY.md** - Detailed technical documentation

---

## Why Manual Deploy?

Use these scripts if you:
- Want to understand exactly what Keybird does to your Pi
- Need to customize the installation process
- Are debugging installation issues
- Want to deploy to a non-standard location
- Are learning about USB gadget mode

---

## Quick Start

### Prerequisites
- [Pi Shell CLI](https://github.com/mcyork/pi-shell) installed (`pip install pi-shell`)
- Raspberry Pi accessible via SSH

### Deploy

```bash
cd manual-deploy
./deploy.sh mypi
```

See **MANUAL_DEPLOY.md** for complete instructions.

---

## What The Scripts Do

The deployment scripts automate:

1. **Directory Creation**
   - Creates `/home/pi/pi-hid-bridge/` structure
   - Sets up subdirectories for app, scripts, services

2. **File Upload**
   - Copies Python application
   - Uploads web UI templates and static files
   - Installs setup scripts

3. **Dependency Installation**
   - Runs `pip install flask evdev`

4. **System Configuration**
   - Modifies `/boot/firmware/config.txt` for USB gadget mode
   - Updates `/boot/firmware/cmdline.txt` for module loading
   - Installs systemd services
   - Enables auto-start on boot

5. **USB Gadget Creation**
   - Runs `setup_gadget_composite.sh`
   - Creates keyboard, mouse, and media HID devices

---

## Difference from pip install

| Aspect | pip install keybird | Manual Deploy Scripts |
|--------|-------------------|---------------------|
| **Installation** | `pip install keybird` | `./deploy.sh mypi` |
| **Location** | `/opt/keybird/` (system) | `/home/pi/pi-hid-bridge/` (user) |
| **Visibility** | Automated | Every step visible |
| **Customization** | Limited | Full control |

---

## Support

For issues with manual deployment, see the troubleshooting section in **MANUAL_DEPLOY.md**.

For pip installation issues, see the main project [README.md](../README.md).

