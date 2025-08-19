#!/usr/bin/env python3

import yaml
import sys
import os
from pathlib import Path

def generate_services(config_path="config.yaml", service_dir="/etc/systemd/system"):
    """Generate systemd service files from config.yaml"""
    
    if not os.path.exists(config_path):
        print(f"Config file not found: {config_path}")
        sys.exit(1)
    
    with open(config_path, 'r') as f:
        config = yaml.safe_load(f)
    
    service_dir = Path(service_dir)
    generated_services = []
    
    for camera in config['cameras']:
        if not camera.get('enabled', False):
            continue
            
        name = camera['name']
        rtsp_url = camera['rtsp_url']
        local_path = config['storage']['local_path']
        duration = config['recording']['segment_duration']
        
        service_content = f"""[Unit]
Description=Camera Recorder for {name}
After=network.target
Wants=network.target

[Service]
Type=simple
ExecStart=/usr/bin/ffmpeg -i {rtsp_url} -c copy -map 0 -avoid_negative_ts make_zero -f segment -segment_time {duration} -segment_format mp4 -segment_atclocktime 1 -strftime 1 {local_path}/{name}/%%Y%%m%%d_%%H%%M%%S.mp4
Restart=always
RestartSec=60
User=camera-backup
Group=camera-backup
UMask=0027
ExecStartPre=/bin/mkdir -p {local_path}/{name}
StandardOutput=journal
StandardError=journal
SyslogIdentifier=camera-recorder-{name}

[Install]
WantedBy=multi-user.target
"""
        
        service_file = service_dir / f"camera-recorder-{name}.service"
        
        with open(service_file, 'w') as f:
            f.write(service_content)
        
        generated_services.append(f"camera-recorder-{name}.service")
        print(f"Generated: {service_file}")
    
    if generated_services:
        print("\nTo enable and start all services:")
        services = " ".join(generated_services)
        print(f"systemctl daemon-reload")
        print(f"systemctl enable {services}")
        print(f"systemctl start {services}")
    else:
        print("No enabled cameras found in config")

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Generate systemd services from camera config")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    parser.add_argument("--service-dir", default="/etc/systemd/system", help="Systemd service directory")
    
    args = parser.parse_args()
    
    generate_services(args.config, args.service_dir)

if __name__ == "__main__":
    main()