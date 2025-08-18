# Camera Backup System

A Python package for backing up RTSP camera streams to S3-compatible storage. Records video streams in 1-hour segments using FFmpeg and automatically uploads completed segments to cloud storage.

## Features

- Records RTSP/RTSPS streams from IP cameras in 1-hour segments
- Automatic upload to S3-compatible storage with organized folder structure
- Systemd service integration for reliable operation
- Configurable camera management (enable/disable individual cameras)
- Safe upload logic (only uploads files older than 5 minutes)
- Automatic cleanup after successful upload

## Installation

### Development Setup

```bash
# Clone the repository
git clone <repository-url>
cd camera-backup

# Create virtual environment
python3 -m venv venv
source venv/bin/activate

# Install in development mode
pip install -e .

# Or install with test dependencies
pip install -e ".[test]"
```

### Production Deployment

```bash
# Build the package
hatch build

# Copy wheel to server and install
scp dist/camera_backup-0.1.0-py3-none-any.whl user@server:/tmp/

# On server
pip install /tmp/camera_backup-0.1.0-py3-none-any.whl
sudo camera-backup-install
```

## Development with Hatch

This project uses [Hatch](https://hatch.pypa.io/) for development workflow management.

### Basic Commands

```bash
# Run tests
hatch test

# Run tests with coverage report
hatch run test:cov

# Start a development shell with dependencies
hatch shell

# Build the package (wheel + source distribution)
hatch build

# Clean build artifacts
hatch clean
```

### Testing

```bash
# Run all tests
hatch test

# Run tests with verbose output
hatch run test:run -v

# Run tests with coverage
hatch run test:cov

# Run specific test file
hatch run test:run tests/test_uploader.py

# Run tests matching a pattern
hatch run test:run -k "test_upload"
```

### Environment Management

```bash
# Show available environments
hatch env show

# Enter development shell
hatch shell

# Run commands in specific environment
hatch run test:python --version
hatch run test:pip list
```

## Configuration

Create `/etc/camera-backup/config.yaml`:

```yaml
# Camera Backup Configuration
storage:
  local_path: "/var/lib/camera-backup/segments"

# S3-compatible storage configuration
s3:
  access_key_id: "YOUR_ACCESS_KEY_ID" 
  secret_access_key: "YOUR_SECRET_ACCESS_KEY"
  bucket: "camera-backups"
  endpoint: "https://YOUR_ENDPOINT_URL"  # e.g., https://account.r2.cloudflarestorage.com

cameras:
  - name: "front-door"
    rtsp_url: "rtsp://username:password@camera-ip:554/stream"
    enabled: true
  - name: "back-yard" 
    rtsp_url: "rtsp://username:password@camera-ip:554/stream"
    enabled: true

recording:
  segment_duration: 3600  # 1 hour in seconds

upload:
  check_interval: 300  # Check for completed segments every 5 minutes
  delete_after_upload: true
```

## Deployment

### 1. Install System Components

```bash
# Creates user, directories, and installs config template
sudo camera-backup-install
```

### 2. Configure Cameras (Required)

```bash
# Edit the configuration template with your camera details and storage credentials
sudo nano /etc/camera-backup/config.yaml
```

**Important:** The template contains placeholder values that must be replaced:
- Replace `YOUR_ACCOUNT_ID`, `YOUR_ACCESS_KEY_ID`, etc. with actual S3-compatible storage credentials
- Replace example RTSP URLs with your actual camera endpoints  
- Enable/disable cameras as needed

**Supported Storage Providers:**
- Cloudflare R2
- Amazon S3
- MinIO
- Backblaze B2 (via S3 API)
- Any S3-compatible storage

### 3. Generate Services

```bash
# Generate systemd service files for each enabled camera
sudo camera-backup-generate --config /etc/camera-backup/config.yaml
```

### 4. Start Services

```bash
# Enable services to start on boot
sudo systemctl enable camera-recorder-* camera-uploader

# Start services (only after config is properly filled out)
sudo systemctl start camera-recorder-* camera-uploader

# Check service status
sudo systemctl status camera-recorder-front-door
sudo systemctl status camera-uploader
```

**Note:** Services will fail to start if the configuration template hasn't been properly edited with real values.

### 5. Monitor Operations

```bash
# View logs
sudo journalctl -u camera-recorder-front-door -f
sudo journalctl -u camera-uploader -f

# Check for completed segments
ls -la /var/lib/camera-backup/segments/
```

## Architecture

The system consists of:

1. **Recording Services**: One systemd service per camera that runs FFmpeg with segment output
2. **Upload Service**: Single service that monitors for completed segments and uploads to R2
3. **Configuration Management**: YAML-based configuration with service generation scripts

### File Structure

```
/etc/camera-backup/
├── config.yaml                    # Main configuration

/var/lib/camera-backup/segments/
├── front-door/                     # Camera-specific directories
│   ├── 20240118_120000.mp4       # 1-hour segments
│   └── 20240118_130000.mp4
└── back-yard/
    └── 20240118_120000.mp4

/etc/systemd/system/
├── camera-recorder-front-door.service
├── camera-recorder-back-yard.service
└── camera-uploader.service
```

### R2 Storage Structure

Files are uploaded to R2 with the following structure:
```
bucket/
├── front-door/
│   └── 2024/01/18/
│       ├── 20240118_120000.mp4
│       └── 20240118_130000.mp4
└── back-yard/
    └── 2024/01/18/
        └── 20240118_120000.mp4
```

## Requirements

- Python 3.8+
- FFmpeg with RTSP support
- Systemd (Linux)
- Network access to IP cameras and S3-compatible storage

## Dependencies

- `pyyaml` - Configuration file parsing
- `boto3` - S3-compatible storage uploads

## License

MIT
