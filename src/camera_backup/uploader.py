#!/usr/bin/env python3

import os
import yaml
import time
import logging
import boto3
from pathlib import Path
from datetime import datetime

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class S3Uploader:
    def __init__(self, config_path="config.yaml"):
        with open(config_path, 'r') as f:
            self.config = yaml.safe_load(f)
        
        self.local_path = Path(self.config['storage']['local_path'])
        self.check_interval = self.config['upload']['check_interval']
        self.delete_after_upload = self.config['upload']['delete_after_upload']
        
        # Initialize S3-compatible storage client
        s3_config = self.config['s3']
        self.s3_client = boto3.client(
            's3',
            endpoint_url=s3_config['endpoint'],
            aws_access_key_id=s3_config['access_key_id'],
            aws_secret_access_key=s3_config['secret_access_key']
        )
        self.bucket = s3_config['bucket']
    
    def find_completed_segments(self):
        """Find video files that are ready for upload"""
        segments = []
        
        for camera_dir in self.local_path.iterdir():
            if not camera_dir.is_dir():
                continue
                
            for video_file in camera_dir.glob("*.mp4"):
                # Check if file is still being written to
                # If modified more than 5 minutes ago, consider it complete
                mod_time = video_file.stat().st_mtime
                if time.time() - mod_time > 300:  # 5 minutes
                    segments.append(video_file)
        
        return sorted(segments)
    
    def upload_file(self, local_file):
        """Upload a file to S3-compatible storage"""
        camera_name = local_file.parent.name
        filename = local_file.name
        
        # Create S3 key: camera/YYYY/MM/DD/filename
        date_str = datetime.fromtimestamp(local_file.stat().st_mtime)
        s3_key = f"{camera_name}/{date_str.strftime('%Y/%m/%d')}/{filename}"
        
        try:
            logger.info(f"Uploading {local_file} to {s3_key}")
            
            self.s3_client.upload_file(
                str(local_file),
                self.bucket,
                s3_key
            )
            
            logger.info(f"Upload successful: {s3_key}")
            
            if self.delete_after_upload:
                local_file.unlink()
                logger.info(f"Deleted local file: {local_file}")
            
            return True
            
        except Exception as e:
            logger.error(f"Upload failed for {local_file}: {e}")
            return False
    
    def run_continuous(self):
        """Continuously check for and upload completed segments"""
        logger.info("Starting S3 uploader")
        
        while True:
            try:
                segments = self.find_completed_segments()
                
                for segment in segments:
                    self.upload_file(segment)
                
                if segments:
                    logger.info(f"Processed {len(segments)} segments")
                
                time.sleep(self.check_interval)
                
            except KeyboardInterrupt:
                logger.info("Uploader stopped by user")
                break
            except Exception as e:
                logger.error(f"Error in upload loop: {e}")
                time.sleep(60)  # Wait before retrying

def main():
    import argparse
    
    parser = argparse.ArgumentParser(description="Upload camera segments to S3-compatible storage")
    parser.add_argument("--config", default="config.yaml", help="Path to config file")
    
    args = parser.parse_args()
    
    uploader = S3Uploader(args.config)
    uploader.run_continuous()

if __name__ == "__main__":
    main()