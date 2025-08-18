import pytest
import yaml
import tempfile
import subprocess
import time
from pathlib import Path
from unittest.mock import patch, Mock

from camera_backup.generate_services import generate_services


@pytest.fixture
def full_config():
    return {
        'storage': {
            'local_path': '/var/lib/camera-backup/segments'
        },
        'cloudflare': {
            'account_id': 'test-account',
            'access_key_id': 'test-key',
            'secret_access_key': 'test-secret',
            'bucket': 'test-bucket',
            'endpoint': 'https://test.r2.cloudflarestorage.com'
        },
        'recording': {
            'segment_duration': 3600
        },
        'upload': {
            'check_interval': 300,
            'delete_after_upload': True
        },
        'cameras': [
            {
                'name': 'front-door',
                'rtsp_url': 'rtsps://user:pass@192.168.1.100:7441/stream1',
                'enabled': True
            },
            {
                'name': 'back-yard',
                'rtsp_url': 'rtsps://user:pass@192.168.1.101:7441/stream1',
                'enabled': True
            },
            {
                'name': 'garage',
                'rtsp_url': 'rtsps://user:pass@192.168.1.102:7441/stream1',
                'enabled': False
            }
        ]
    }


def test_end_to_end_service_generation_and_validation(full_config):
    """Test the complete workflow from config to generated services"""
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(full_config, f)
        config_file = f.name
    
    with tempfile.TemporaryDirectory() as temp_dir:
        service_dir = Path(temp_dir)
        
        # Generate services
        generate_services(config_file, str(service_dir))
        
        # Verify correct number of services created
        service_files = list(service_dir.glob("*.service"))
        assert len(service_files) == 2  # Only enabled cameras
        
        service_names = [f.name for f in service_files]
        assert "camera-recorder-front-door.service" in service_names
        assert "camera-recorder-back-yard.service" in service_names
        assert "camera-recorder-garage.service" not in service_names
        
        # Validate service file structure for each camera
        for service_file in service_files:
            content = service_file.read_text()
            
            # Common elements all services should have
            assert "[Unit]" in content
            assert "[Service]" in content 
            assert "[Install]" in content
            assert "Type=simple" in content
            assert "Restart=always" in content
            assert "User=camera-backup" in content
            assert "ExecStart=/usr/bin/ffmpeg" in content
            assert "-c copy -map 0" in content
            assert "-f segment" in content
            assert "-segment_time 3600" in content
            
            # Camera-specific elements
            camera_name = service_file.name.replace("camera-recorder-", "").replace(".service", "")
            assert f"Description=Camera Recorder for {camera_name}" in content
            assert f"segments/{camera_name}" in content


def test_config_validation_comprehensive():
    """Test various config validation scenarios"""
    
    base_config = {
        'storage': {'local_path': '/tmp'},
        'recording': {'segment_duration': 3600},
        'cameras': []
    }
    
    # Test missing required sections
    incomplete_configs = [
        # Missing storage
        {
            'recording': {'segment_duration': 3600},
            'cameras': [{'name': 'test', 'rtsp_url': 'rtsp://test', 'enabled': True}]
        },
        # Missing cameras
        {
            'storage': {'local_path': '/tmp'},
            'recording': {'segment_duration': 3600}
        },
    ]
    
    for config in incomplete_configs:
        with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
            yaml.dump(config, f)
            config_file = f.name
        
        with tempfile.TemporaryDirectory() as temp_dir:
            # Should handle missing sections gracefully
            try:
                generate_services(config_file, temp_dir)
            except KeyError:
                # Expected for incomplete configs
                pass


def test_service_file_systemd_compatibility():
    """Test that generated service files would be valid for systemd"""
    
    config = {
        'storage': {'local_path': '/var/lib/camera-backup/segments'},
        'recording': {'segment_duration': 1800},  # 30 minutes
        'cameras': [
            {
                'name': 'test-camera',
                'rtsp_url': 'rtsps://user:complex$pass@192.168.1.100:7441/stream?param=value',
                'enabled': True
            }
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_file = f.name
    
    with tempfile.TemporaryDirectory() as temp_dir:
        generate_services(config_file, temp_dir)
        
        service_file = Path(temp_dir) / "camera-recorder-test-camera.service"
        content = service_file.read_text()
        
        # Verify systemd-specific requirements
        lines = content.strip().split('\n')
        
        # Should have proper section headers
        sections = [line for line in lines if line.startswith('[') and line.endswith(']')]
        assert '[Unit]' in sections
        assert '[Service]' in sections
        assert '[Install]' in sections
        
        # Should have required fields
        assert any(line.startswith('Description=') for line in lines)
        assert any(line.startswith('ExecStart=') for line in lines)
        assert any(line.startswith('Type=') for line in lines)
        
        # ExecStart should be a single line (no line breaks in command)
        exec_start_lines = [line for line in lines if line.startswith('ExecStart=')]
        assert len(exec_start_lines) == 1
        
        # URL with special characters should be preserved
        assert 'complex$pass' in content
        assert 'param=value' in content


@patch('camera_backup.uploader.boto3.client')
def test_uploader_handles_file_system_changes(mock_boto3):
    """Test uploader behavior when files are added/removed during operation"""
    
    config = {
        'storage': {'local_path': '/tmp/test-segments'},
        'cloudflare': {
            'account_id': 'test',
            'access_key_id': 'key',
            'secret_access_key': 'secret',
            'bucket': 'bucket',
            'endpoint': 'https://test.com'
        },
        'upload': {
            'check_interval': 1,
            'delete_after_upload': True
        }
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_file = f.name
    
    with tempfile.TemporaryDirectory() as temp_dir:
        segments_dir = Path(temp_dir)
        
        # Update config to use temp directory
        config['storage']['local_path'] = str(segments_dir)
        with open(config_file, 'w') as f:
            yaml.dump(config, f)
        
        from camera_backup.uploader import R2Uploader
        uploader = R2Uploader(config_file)
        
        # Create camera directory
        camera_dir = segments_dir / "test-camera"
        camera_dir.mkdir()
        
        # Test with no files
        segments = uploader.find_completed_segments()
        assert len(segments) == 0
        
        # Create old file (should be found)
        old_file = camera_dir / "old_segment.mp4"
        old_file.touch()
        old_time = time.time() - 400
        
        # Use os.utime to set actual file modification time
        import os
        os.utime(str(old_file), (old_time, old_time))
        
        segments = uploader.find_completed_segments()
        
        assert len(segments) == 1
        assert old_file in segments