"""
AWS Services Module for Fall Detection
======================================
Provides classes for uploading clips to S3, logging events to DynamoDB,
and sending notifications via SNS.
"""

import os
import time
import threading
import logging
from typing import Optional, Dict, Any

logger = logging.getLogger(__name__)

# Import AWS config
try:
    from aws_config import (
        S3_ENABLED, S3_BUCKET_NAME, S3_CLIPS_PREFIX,
        SNS_ENABLED, SNS_TOPIC_ARN,
        DYNAMODB_ENABLED, DYNAMODB_TABLE_NAME,
        get_s3_client, get_sns_client, get_dynamodb_resource
    )
    AWS_CONFIG_AVAILABLE = True
except ImportError:
    AWS_CONFIG_AVAILABLE = False
    logger.warning("aws_config.py not found - AWS features disabled")


class S3Uploader:
    """Handles uploading video clips to S3."""
    
    def __init__(self):
        self.enabled = AWS_CONFIG_AVAILABLE and S3_ENABLED
        self.client = None
        self.bucket = S3_BUCKET_NAME if AWS_CONFIG_AVAILABLE else None
        self.prefix = S3_CLIPS_PREFIX if AWS_CONFIG_AVAILABLE else ""
        
        if self.enabled:
            try:
                self.client = get_s3_client()
                if self.client:
                    logger.info(f"S3 uploader initialized for bucket: {self.bucket}")
                else:
                    self.enabled = False
                    logger.warning("Failed to create S3 client")
            except Exception as e:
                self.enabled = False
                logger.error(f"S3 initialization error: {e}")
    
    def upload_async(self, local_path: str, callback=None) -> Optional[str]:
        """
        Upload a file to S3 asynchronously.
        
        Args:
            local_path: Path to local file
            callback: Optional callback function(success, s3_url)
            
        Returns:
            S3 key if upload started, None if disabled
        """
        if not self.enabled or not os.path.exists(local_path):
            if callback:
                callback(False, None)
            return None
        
        # Generate S3 key
        filename = os.path.basename(local_path)
        s3_key = f"{self.prefix}{filename}"
        
        def upload_worker():
            try:
                self.client.upload_file(local_path, self.bucket, s3_key)
                s3_url = f"s3://{self.bucket}/{s3_key}"
                logger.info(f"Uploaded to S3: {s3_url}")
                if callback:
                    callback(True, s3_url)
            except Exception as e:
                logger.error(f"S3 upload failed: {e}")
                if callback:
                    callback(False, None)
        
        thread = threading.Thread(target=upload_worker, daemon=True)
        thread.start()
        return s3_key
    
    def upload_sync(self, local_path: str) -> Optional[str]:
        """
        Upload a file to S3 synchronously.
        
        Args:
            local_path: Path to local file
            
        Returns:
            S3 URL if successful, None otherwise
        """
        if not self.enabled or not os.path.exists(local_path):
            return None
        
        filename = os.path.basename(local_path)
        s3_key = f"{self.prefix}{filename}"
        
        try:
            self.client.upload_file(local_path, self.bucket, s3_key)
            s3_url = f"s3://{self.bucket}/{s3_key}"
            logger.info(f"Uploaded to S3: {s3_url}")
            return s3_url
        except Exception as e:
            logger.error(f"S3 upload failed: {e}")
            return None


class DynamoDBLogger:
    """Handles logging fall events to DynamoDB."""
    
    def __init__(self):
        self.enabled = AWS_CONFIG_AVAILABLE and DYNAMODB_ENABLED
        self.table = None
        
        if self.enabled:
            try:
                dynamodb = get_dynamodb_resource()
                if dynamodb:
                    self.table = dynamodb.Table(DYNAMODB_TABLE_NAME)
                    logger.info(f"DynamoDB logger initialized for table: {DYNAMODB_TABLE_NAME}")
                else:
                    self.enabled = False
                    logger.warning("Failed to create DynamoDB resource")
            except Exception as e:
                self.enabled = False
                logger.error(f"DynamoDB initialization error: {e}")
    
    def log_event(self, event_data: Dict[str, Any]) -> bool:
        """
        Log a fall event to DynamoDB.
        
        Args:
            event_data: Dictionary containing event details
            
        Returns:
            True if logged successfully
        """
        if not self.enabled:
            return False
        
        # Ensure required fields
        item = {
            'event_id': f"fall_{int(time.time() * 1000)}",
            'timestamp': int(time.time()),
            'timestamp_iso': time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            **event_data
        }
        
        try:
            self.table.put_item(Item=item)
            logger.info(f"Logged event to DynamoDB: {item['event_id']}")
            return True
        except Exception as e:
            logger.error(f"DynamoDB log failed: {e}")
            return False
    
    def log_event_async(self, event_data: Dict[str, Any]) -> None:
        """Log event asynchronously."""
        thread = threading.Thread(
            target=self.log_event, 
            args=(event_data,), 
            daemon=True
        )
        thread.start()


class SNSNotifier:
    """Handles sending notifications via SNS."""
    
    def __init__(self):
        self.enabled = AWS_CONFIG_AVAILABLE and SNS_ENABLED
        self.client = None
        self.topic_arn = SNS_TOPIC_ARN if AWS_CONFIG_AVAILABLE else None
        
        if self.enabled:
            try:
                self.client = get_sns_client()
                if self.client:
                    logger.info(f"SNS notifier initialized for topic: {self.topic_arn}")
                else:
                    self.enabled = False
                    logger.warning("Failed to create SNS client")
            except Exception as e:
                self.enabled = False
                logger.error(f"SNS initialization error: {e}")
    
    def send_fall_alert(self, confidence: float, clip_url: Optional[str] = None, 
                        device_id: str = "unknown") -> bool:
        """
        Send a fall detection alert via SNS.
        
        Args:
            confidence: Detection confidence (0-1)
            clip_url: Optional URL to video clip
            device_id: Device identifier
            
        Returns:
            True if sent successfully
        """
        if not self.enabled:
            return False
        
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
        
        subject = f"⚠️ Fall Detected - {device_id}"
        message = f"""
FALL DETECTION ALERT
====================
Time: {timestamp}
Device: {device_id}
Confidence: {confidence:.1%}
"""
        if clip_url:
            message += f"Video Clip: {clip_url}\n"
        
        message += """
Please check on the person immediately.

- NovaCare Fall Detection System
"""
        
        try:
            self.client.publish(
                TopicArn=self.topic_arn,
                Subject=subject,
                Message=message.strip()
            )
            logger.info(f"Sent SNS notification for fall event")
            return True
        except Exception as e:
            logger.error(f"SNS notification failed: {e}")
            return False
    
    def send_alert_async(self, confidence: float, clip_url: Optional[str] = None,
                         device_id: str = "unknown") -> None:
        """Send alert asynchronously."""
        thread = threading.Thread(
            target=self.send_fall_alert,
            args=(confidence, clip_url, device_id),
            daemon=True
        )
        thread.start()


# Singleton instances for easy access
_s3_uploader = None
_dynamodb_logger = None
_sns_notifier = None


def get_s3_uploader() -> S3Uploader:
    """Get singleton S3 uploader instance."""
    global _s3_uploader
    if _s3_uploader is None:
        _s3_uploader = S3Uploader()
    return _s3_uploader


def get_dynamodb_logger() -> DynamoDBLogger:
    """Get singleton DynamoDB logger instance."""
    global _dynamodb_logger
    if _dynamodb_logger is None:
        _dynamodb_logger = DynamoDBLogger()
    return _dynamodb_logger


def get_sns_notifier() -> SNSNotifier:
    """Get singleton SNS notifier instance."""
    global _sns_notifier
    if _sns_notifier is None:
        _sns_notifier = SNSNotifier()
    return _sns_notifier
