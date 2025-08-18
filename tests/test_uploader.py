import pytest
import yaml
import time
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock
from datetime import datetime

from camera_backup.uploader import R2Uploader


@pytest.fixture
def sample_config():
    return {
        'storage': {
            'local_path': '/tmp/camera-backup/segments'
        },
        'cloudflare': {
            'account_id': 'test-account',
            'access_key_id': 'test-key',
            'secret_access_key': 'test-secret',
            'bucket': 'test-bucket',
            'endpoint': 'https://test.r2.cloudflarestorage.com'
        },
        'upload': {
            'check_interval': 300,
            'delete_after_upload': True
        }
    }


@pytest.fixture
def config_file(sample_config):
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(sample_config, f)
        return f.name


@pytest.fixture
def temp_segments_dir():
    with tempfile.TemporaryDirectory() as temp_dir:
        segments_dir = Path(temp_dir)
        
        # Create camera directories
        (segments_dir / "front-door").mkdir()
        (segments_dir / "back-yard").mkdir()
        
        yield segments_dir


@patch('camera_backup.uploader.boto3.client')
def test_r2_uploader_initialization(mock_boto3, config_file):
    mock_s3_client = Mock()
    mock_boto3.return_value = mock_s3_client
    
    uploader = R2Uploader(config_file)
    
    # Check boto3 client was initialized correctly
    mock_boto3.assert_called_once_with(
        's3',
        endpoint_url='https://test.r2.cloudflarestorage.com',
        aws_access_key_id='test-key',
        aws_secret_access_key='test-secret'
    )
    
    assert uploader.bucket == 'test-bucket'
    assert uploader.check_interval == 300
    assert uploader.delete_after_upload is True


@patch('camera_backup.uploader.boto3.client')
def test_find_completed_segments_filters_by_age(mock_boto3, config_file, temp_segments_dir):
    uploader = R2Uploader(config_file)
    uploader.local_path = temp_segments_dir
    
    # Create test files with different modification times
    old_file = temp_segments_dir / "front-door" / "20240101_120000.mp4"
    recent_file = temp_segments_dir / "front-door" / "20240101_130000.mp4"
    non_video_file = temp_segments_dir / "front-door" / "log.txt"
    
    old_file.touch()
    recent_file.touch()
    non_video_file.touch()
    
    # Set modification times
    old_time = time.time() - 400  # 6+ minutes ago
    recent_time = time.time() - 100  # 1-2 minutes ago
    
    # Use os.stat for actual file times, but mock time.time() for comparison
    import os
    os.utime(str(old_file), (old_time, old_time))
    os.utime(str(recent_file), (recent_time, recent_time))
    
    segments = uploader.find_completed_segments()
    
    # Should only find the old video file
    assert len(segments) == 1
    assert old_file in segments
    assert recent_file not in segments


@patch('camera_backup.uploader.boto3.client')
def test_upload_file_success(mock_boto3, config_file, temp_segments_dir):
    mock_s3_client = Mock()
    mock_boto3.return_value = mock_s3_client
    
    uploader = R2Uploader(config_file)
    
    # Create test file
    test_file = temp_segments_dir / "front-door" / "20240115_120000.mp4"
    test_file.touch()
    
    # Mock file stats for date extraction
    mock_time = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    with patch.object(Path, 'stat') as mock_stat:
        mock_stat.return_value = Mock(st_mtime=mock_time)
        
        result = uploader.upload_file(test_file)
    
    assert result is True
    
    # Verify S3 upload was called with correct parameters
    expected_key = "front-door/2024/01/15/20240115_120000.mp4"
    mock_s3_client.upload_file.assert_called_once_with(
        str(test_file),
        'test-bucket',
        expected_key
    )
    
    # File should be deleted after upload
    assert not test_file.exists()


@patch('camera_backup.uploader.boto3.client')
def test_upload_file_failure(mock_boto3, config_file, temp_segments_dir):
    mock_s3_client = Mock()
    mock_s3_client.upload_file.side_effect = Exception("Upload failed")
    mock_boto3.return_value = mock_s3_client
    
    uploader = R2Uploader(config_file)
    
    test_file = temp_segments_dir / "front-door" / "20240115_120000.mp4"
    test_file.touch()
    
    mock_time = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    with patch.object(Path, 'stat') as mock_stat:
        mock_stat.return_value = Mock(st_mtime=mock_time)
        
        result = uploader.upload_file(test_file)
    
    assert result is False
    
    # File should still exist after failed upload
    assert test_file.exists()


@patch('camera_backup.uploader.boto3.client')
def test_upload_file_no_delete_after_upload(mock_boto3, config_file, temp_segments_dir):
    # Modify config to disable deletion
    with open(config_file, 'r') as f:
        config = yaml.safe_load(f)
    config['upload']['delete_after_upload'] = False
    
    with tempfile.NamedTemporaryFile(mode='w', suffix='.yaml', delete=False) as f:
        yaml.dump(config, f)
        no_delete_config = f.name
    
    mock_s3_client = Mock()
    mock_boto3.return_value = mock_s3_client
    
    uploader = R2Uploader(no_delete_config)
    
    test_file = temp_segments_dir / "front-door" / "20240115_120000.mp4"
    test_file.touch()
    
    mock_time = datetime(2024, 1, 15, 12, 0, 0).timestamp()
    with patch.object(Path, 'stat') as mock_stat:
        mock_stat.return_value = Mock(st_mtime=mock_time)
        
        result = uploader.upload_file(test_file)
    
    assert result is True
    
    # File should still exist when delete_after_upload is False
    assert test_file.exists()


@patch('camera_backup.uploader.boto3.client')
def test_s3_key_generation(mock_boto3, config_file, temp_segments_dir):
    mock_s3_client = Mock()
    mock_boto3.return_value = mock_s3_client
    
    uploader = R2Uploader(config_file)
    
    # Test different camera names and dates
    test_cases = [
        ("front-door", "test_file.mp4", datetime(2024, 1, 15, 12, 0, 0), "front-door/2024/01/15/test_file.mp4"),
        ("back-yard", "segment.mp4", datetime(2023, 12, 31, 23, 59, 59), "back-yard/2023/12/31/segment.mp4"),
    ]
    
    for camera_name, filename, file_date, expected_key in test_cases:
        test_file = temp_segments_dir / camera_name / filename
        test_file.touch()
        
        with patch.object(Path, 'stat') as mock_stat:
            mock_stat.return_value = Mock(st_mtime=file_date.timestamp())
            
            uploader.upload_file(test_file)
        
        # Check the S3 key used in the upload call
        call_args = mock_s3_client.upload_file.call_args
        assert call_args[0][2] == expected_key
        
        mock_s3_client.reset_mock()