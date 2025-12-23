"""
AWS IoT Core MQTT Client for Fall Detection
============================================
Publishes fall detection events to AWS IoT Core.
"""

import json
import time
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

# Try to import AWS IoT SDK
AWS_IOT_AVAILABLE = False
try:
    from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
    AWS_IOT_AVAILABLE = True
except ImportError:
    logger.warning("AWSIoTPythonSDK not installed. Run: pip install AWSIoTPythonSDK")

try:
    import boto3
    BOTO3_AVAILABLE = True
except ImportError:
    BOTO3_AVAILABLE = False
    logger.warning("boto3 not installed. S3 uploads disabled.")

from aws_config import (
    IOT_CORE_ENABLED, IOT_CORE_ENDPOINT, IOT_CORE_TOPIC,
    IOT_CORE_CERT_PATH, IOT_CORE_KEY_PATH, IOT_CORE_ROOT_CA_PATH,
    S3_ENABLED, S3_BUCKET_NAME, S3_CLIPS_PREFIX,
    AWS_REGION
)


class AWSIoTPublisher:
    """AWS IoT Core MQTT client for publishing fall events."""
    
    def __init__(self, client_id="raspi-fall-detector"):
        self.client_id = client_id
        self.client = None
        self.connected = False
        self.s3_client = None
        
    def connect(self):
        """Connect to AWS IoT Core."""
        if not AWS_IOT_AVAILABLE:
            logger.error("AWS IoT SDK not available")
            return False
            
        if not IOT_CORE_ENABLED:
            logger.info("AWS IoT Core disabled in config")
            return False
        
        # Check certificate files exist
        cert_files = [IOT_CORE_CERT_PATH, IOT_CORE_KEY_PATH, IOT_CORE_ROOT_CA_PATH]
        for cert_file in cert_files:
            if not Path(cert_file).exists():
                logger.error(f"Certificate file not found: {cert_file}")
                return False
        
        try:
            # Create MQTT client
            self.client = AWSIoTMQTTClient(self.client_id)
            self.client.configureEndpoint(IOT_CORE_ENDPOINT, 8883)
            self.client.configureCredentials(
                IOT_CORE_ROOT_CA_PATH,
                IOT_CORE_KEY_PATH,
                IOT_CORE_CERT_PATH
            )
            
            # Configure connection settings
            self.client.configureAutoReconnectBackoffTime(1, 32, 20)
            self.client.configureOfflinePublishQueueing(-1)  # Infinite queue
            self.client.configureDrainingFrequency(2)  # 2 Hz
            self.client.configureConnectDisconnectTimeout(10)
            self.client.configureMQTTOperationTimeout(5)
            
            # Connect
            self.connected = self.client.connect()
            
            if self.connected:
                logger.info(f"Connected to AWS IoT Core: {IOT_CORE_ENDPOINT}")
                
                # Initialize S3 client
                if S3_ENABLED and BOTO3_AVAILABLE:
                    self.s3_client = boto3.client('s3', region_name=AWS_REGION)
                    logger.info("S3 client initialized")
                    
            return self.connected
            
        except Exception as e:
            logger.error(f"Failed to connect to AWS IoT Core: {e}")
            return False
    
    def disconnect(self):
        """Disconnect from AWS IoT Core."""
        if self.client and self.connected:
            try:
                self.client.disconnect()
                self.connected = False
                logger.info("Disconnected from AWS IoT Core")
            except Exception as e:
                logger.error(f"Error disconnecting: {e}")
    
    def publish_fall_event(self, confidence, clip_path=None, timestamp=None):
        """
        Publish a fall detection event to AWS IoT Core.
        
        Args:
            confidence: Detection confidence (0-1)
            clip_path: Local path to video clip
            timestamp: Event timestamp
            
        Returns:
            bool: True if published successfully
        """
        if not self.connected:
            logger.warning("Not connected to AWS IoT Core")
            return False
        
        ts = timestamp or int(time.time())
        
        # Upload clip to S3 if enabled
        s3_clip_url = None
        if clip_path and self.s3_client and Path(clip_path).exists():
            try:
                s3_key = f"{S3_CLIPS_PREFIX}{Path(clip_path).name}"
                self.s3_client.upload_file(clip_path, S3_BUCKET_NAME, s3_key)
                s3_clip_url = f"s3://{S3_BUCKET_NAME}/{s3_key}"
                logger.info(f"Uploaded clip to S3: {s3_clip_url}")
            except Exception as e:
                logger.error(f"Failed to upload clip to S3: {e}")
        
        # Build message
        event = {
            "event": "fall_detected",
            "device_id": self.client_id,
            "confidence": round(confidence, 3),
            "timestamp": ts,
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(ts)),
            "clip_path": clip_path,
            "s3_url": s3_clip_url
        }
        
        try:
            message = json.dumps(event)
            self.client.publish(IOT_CORE_TOPIC, message, 1)
            logger.info(f"Published fall event to AWS IoT Core: confidence={confidence:.1%}")
            return True
        except Exception as e:
            logger.error(f"Failed to publish to AWS IoT Core: {e}")
            return False
    
    def publish_status(self, status="online"):
        """Publish device status."""
        if not self.connected:
            return False
            
        status_topic = f"{IOT_CORE_TOPIC}/status"
        message = json.dumps({
            "status": status,
            "device_id": self.client_id,
            "timestamp": int(time.time())
        })
        
        try:
            self.client.publish(status_topic, message, 1)
            return True
        except Exception as e:
            logger.error(f"Failed to publish status: {e}")
            return False


# Factory function to get appropriate publisher
def get_mqtt_publisher():
    """
    Get the appropriate MQTT publisher based on configuration.
    Returns AWS IoT publisher if enabled, otherwise falls back to local MQTT.
    """
    if IOT_CORE_ENABLED and AWS_IOT_AVAILABLE:
        publisher = AWSIoTPublisher()
        if publisher.connect():
            return publisher
        logger.warning("AWS IoT connection failed, falling back to local MQTT")
    
    # Fallback to local MQTT
    from mqtt_client import MQTTPublisher
    return MQTTPublisher()
