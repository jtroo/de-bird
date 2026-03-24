#!/usr/bin/env python3
"""
De-bird Setup - One-time system configuration for Raspberry Pi

This script configures your Raspberry Pi for USB gadget mode and installs
the necessary systemd services.
"""

import os
import sys
import subprocess
import shutil
from pathlib import Path

def check_privileges():
    """Ensure script is run with sudo/root"""
    if os.geteuid() != 0:
        print("❌ Error: This script must be run with sudo")
        print("   Usage: sudo python3 setup.py")
        sys.exit(1)

def check_raspberry_pi():
    """Verify we're running on a Raspberry Pi with USB gadget support"""
    if not os.path.exists('/sys/class/udc'):
        print("❌ Error: USB gadget mode not available")
        print("   De-bird requires a Raspberry Pi with USB gadget support:")
        print("   - Pi 4 Model B ✅")
        print("   - Pi Zero 2 W ✅")
        print("   - Pi 3 Model B ✅")
        print("   - Pi 5 ❌ (USB gadget broken)")
        sys.exit(1)

    # Check for Pi 5
    try:
        with open('/proc/device-tree/model', 'r') as f:
            model = f.read()
            if 'Pi 5' in model or 'Raspberry Pi 5' in model:
                print("⚠️  WARNING: Raspberry Pi 5 detected!")
                print("   USB gadget mode is currently broken on Pi 5.")
                print("   Setup will continue, but USB output won't work.")
                response = input("   Continue anyway? (y/N): ")
                if response.lower() != 'y':
                    sys.exit(1)
    except:
        pass

def install_files():
    """Copy scripts and systemd services to system locations"""
    package_dir = Path(__file__).parent

    # Create installation directory
    install_dir = Path('/opt/de-bird')
    install_dir.mkdir(parents=True, exist_ok=True)

    # Copy scripts
    print("📁 Installing scripts to /opt/de-bird/scripts...")
    scripts_src = package_dir / 'scripts'
    scripts_dst = install_dir / 'scripts'
    if scripts_src.exists():
        shutil.copytree(scripts_src, scripts_dst, dirs_exist_ok=True)
        # Make executable
        for script in scripts_dst.glob('*.sh'):
            script.chmod(0o755)

    # Install systemd services
    print("🔧 Installing systemd services...")
    systemd_src = package_dir / 'systemd'
    systemd_dst = Path('/etc/systemd/system')

    if systemd_src.exists():
        for service_file in systemd_src.glob('*.service'):
            shutil.copy2(service_file, systemd_dst / service_file.name)

    # Update service file paths to use installed Python
    update_systemd_paths(install_dir)

def update_systemd_paths(install_dir):
    """Update systemd service files to use system paths"""
    services = [
        '/etc/systemd/system/hid-gadget.service',
        '/etc/systemd/system/pi-hid-bridge.service'
    ]

    for service in services:
        if os.path.exists(service):
            with open(service, 'r') as f:
                content = f.read()

            with open(service, 'w') as f:
                f.write(content)

def configure_boot():
    """Configure boot files for USB gadget mode"""
    print("⚙️  Configuring USB gadget mode in boot config...")

    # Find config.txt location (varies by Pi OS version)
    config_paths = ['/boot/firmware/config.txt', '/boot/config.txt']
    config_txt = None
    for path in config_paths:
        if os.path.exists(path):
            config_txt = path
            break

    if not config_txt:
        print("⚠️  Warning: Could not find config.txt")
        return

    # Backup config.txt
    subprocess.run(['cp', config_txt, f'{config_txt}.backup'], check=False)

    # Check if dwc2 overlay already exists
    with open(config_txt, 'r') as f:
        content = f.read()

    if 'dtoverlay=dwc2' not in content:
        print("   Adding dwc2 overlay to config.txt...")
        with open(config_txt, 'a') as f:
            f.write('\ndtoverlay=dwc2,dr_mode=peripheral\n')
    else:
        print("   ✓ dwc2 overlay already configured")

    # Configure cmdline.txt
    cmdline_paths = ['/boot/firmware/cmdline.txt', '/boot/cmdline.txt']
    cmdline_txt = None
    for path in cmdline_paths:
        if os.path.exists(path):
            cmdline_txt = path
            break

    if cmdline_txt:
        with open(cmdline_txt, 'r') as f:
            cmdline = f.read()

        if 'modules-load=dwc2' not in cmdline:
            print("   Adding modules-load to cmdline.txt...")
            cmdline = cmdline.replace('rootwait', 'rootwait modules-load=dwc2')
            with open(cmdline_txt, 'w') as f:
                f.write(cmdline)
        else:
            print("   ✓ modules-load already configured")

def setup_usb_gadget():
    """Run the USB gadget setup script"""
    script = Path('/opt/de-bird/scripts/setup_gadget_composite.sh')
    if script.exists():
        print("🔌 Setting up USB HID composite gadget...")
        subprocess.run(['bash', str(script)], check=True)
    else:
        print("⚠️  Warning: setup_gadget_composite.sh not found")

def enable_services():
    """Enable and start systemd services"""
    print("🚀 Enabling systemd services...")
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    subprocess.run(['systemctl', 'enable', 'hid-gadget.service'], check=True)
    subprocess.run(['systemctl', 'enable', 'pi-hid-bridge.service'], check=True)

def main():
    """Main setup function"""
    print("🎹 De-bird Setup - Raspberry Pi USB HID Bridge")
    print("=" * 60)
    print()

    check_privileges()
    check_raspberry_pi()

    install_files()
    configure_boot()

    try:
        setup_usb_gadget()
    except Exception as e:
        print(f"⚠️  Warning: Could not setup USB gadget: {e}")
        print("   You may need to reboot first")

    enable_services()

    print()
    print("=" * 60)
    print("✅ De-bird setup complete!")
    print()
    print("📋 Next steps:")
    print("   1. Reboot the Pi:")
    print("      sudo reboot")
    print()
    print("   2. After reboot, services will auto-start")
    print("      Check status: systemctl status pi-hid-bridge")
    print()
    print("   3. Connect USB-C cable to target computer")
    print()

if __name__ == '__main__':
    main()

