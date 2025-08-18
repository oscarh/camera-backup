#!/usr/bin/env python3

import os
import sys
import shutil
import subprocess
from pathlib import Path

def install_system_files():
    """Install systemd service files and create necessary directories"""
    
    if os.geteuid() != 0:
        print("This script must be run as root for system installation")
        sys.exit(1)
    
    # Create user and group
    try:
        subprocess.run(['useradd', '-r', '-s', '/bin/false', 'camera-backup'], check=True)
        print("Created camera-backup user")
    except subprocess.CalledProcessError:
        print("camera-backup user already exists")
    
    # Create directories
    os.makedirs('/etc/camera-backup', exist_ok=True)
    os.makedirs('/var/lib/camera-backup/segments', exist_ok=True)
    
    # Set ownership
    shutil.chown('/var/lib/camera-backup/segments', 'camera-backup', 'camera-backup')
    
    # Copy service file
    service_file = Path(__file__).parent / 'camera-uploader.service'
    if service_file.exists():
        shutil.copy2(service_file, '/etc/systemd/system/')
        print("Installed camera-uploader.service")
    else:
        print("Warning: camera-uploader.service not found in package")
    
    # Copy config template if it doesn't exist
    if not os.path.exists('/etc/camera-backup/config.yaml'):
        config_file = Path(__file__).parent / 'config.yaml'
        if config_file.exists():
            shutil.copy2(config_file, '/etc/camera-backup/')
            shutil.chown('/etc/camera-backup/config.yaml', 'root', 'camera-backup')
            os.chmod('/etc/camera-backup/config.yaml', 0o640)
            print("Copied config template to /etc/camera-backup/config.yaml")
            print("Please edit it with your camera details and Cloudflare credentials")
        else:
            print("Warning: config.yaml template not found in package")
    
    # Reload systemd
    subprocess.run(['systemctl', 'daemon-reload'], check=True)
    
    print("\nInstallation complete!")
    print("\nNext steps:")
    print("1. Edit /etc/camera-backup/config.yaml with your settings")
    print("2. Run: camera-backup-generate --config /etc/camera-backup/config.yaml")
    print("3. Enable services: systemctl enable camera-recorder-* camera-uploader")
    print("4. Start services: systemctl start camera-recorder-* camera-uploader")

if __name__ == "__main__":
    install_system_files()