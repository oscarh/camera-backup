import pytest
import yaml
import tempfile
from pathlib import Path
from unittest.mock import patch, mock_open

from camera_backup.generate_services import generate_services


@pytest.fixture
def sample_config():
    return {
        'storage': {
            'local_path': '/var/lib/camera-backup/segments'
        },
        'recording': {
            'segment_duration': 3600
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
                'name': 'disabled-camera',
                'rtsp_url': 'rtsps://user:pass@192.168.1.102:7441/stream1',
                'enabled': False
            }
        ]
    }


@pytest.fixture
def config_file(sample_config):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        return f.name


def test_generate_services_creates_files_for_enabled_cameras(config_file):
    with tempfile.TemporaryDirectory() as temp_dir:
        service_dir = Path(temp_dir)
        
        generate_services(config_file, str(service_dir))
        
        # Should create services for enabled cameras only
        assert (service_dir / "camera-recorder-front-door.service").exists()
        assert (service_dir / "camera-recorder-back-yard.service").exists()
        assert not (service_dir / "camera-recorder-disabled-camera.service").exists()


def test_generate_services_creates_correct_service_content(config_file):
    with tempfile.TemporaryDirectory() as temp_dir:
        service_dir = Path(temp_dir)
        
        generate_services(config_file, str(service_dir))
        
        service_file = service_dir / "camera-recorder-front-door.service"
        content = service_file.read_text()
        
        # Check key elements in service file
        assert "Description=Camera Recorder for front-door" in content
        assert "rtsps://user:pass@192.168.1.100:7441/stream1" in content
        assert "-c copy -map 0" in content
        assert "-segment_time 3600" in content
        assert "/var/lib/camera-backup/segments/front-door" in content
        assert "User=camera-backup" in content


def test_generate_services_handles_missing_config_file():
    with pytest.raises(SystemExit) as exc_info:
        generate_services("nonexistent.yaml", "/tmp")
    
    assert exc_info.value.code == 1


def test_generate_services_handles_no_enabled_cameras():
    config = {
        'storage': {'local_path': '/tmp'},
        'recording': {'segment_duration': 3600},
        'cameras': [
            {'name': 'camera1', 'rtsp_url': 'rtsp://test', 'enabled': False}
        ]
    }
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        config_file = f.name
    
    with tempfile.TemporaryDirectory() as temp_dir:
        # Should not raise an error, just print a message
        generate_services(config_file, temp_dir)
        
        # No service files should be created
        assert len(list(Path(temp_dir).glob("*.service"))) == 0


def test_generate_services_escapes_special_characters():
    config = {
        'storage': {'local_path': '/tmp'},
        'recording': {'segment_duration': 3600},
        'cameras': [
            {
                'name': 'test-camera',
                'rtsp_url': 'rtsps://user:p@ss$word@192.168.1.100:7441/stream',
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
        
        # URL should be preserved as-is in the service file
        assert "rtsps://user:p@ss$word@192.168.1.100:7441/stream" in content