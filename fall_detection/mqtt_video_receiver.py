"""
MQTT Video Receiver for EC2
===========================
Receives camera frames from Raspberry Pi via AWS IoT Core MQTT.
"""

import cv2
import base64
import json
import time
import logging
import threading
import numpy as np
from collections import deque
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Import AWS config
try:
    from aws_config import (
        IOT_CORE_ENDPOINT, IOT_CORE_CERT_PATH, IOT_CORE_KEY_PATH, IOT_CORE_ROOT_CA_PATH
    )
except ImportError:
    IOT_CORE_ENDPOINT = "a3vbyo79k8vjec-ats.iot.us-east-1.amazonaws.com"
    IOT_CORE_CERT_PATH = "certs/device.pem.crt"
    IOT_CORE_KEY_PATH = "certs/private.pem.key"
    IOT_CORE_ROOT_CA_PATH = "certs/AmazonRootCA1.pem"

# MQTT Topics
IOT_CAMERA_TOPIC = "novacare/camera/frames"
IOT_STATUS_TOPIC = "novacare/camera/status"

# Frame buffer configuration
MAX_FRAME_BUFFER = 30  # Keep last 30 frames


class MQTTVideoReceiver:
    """Receives video frames from AWS IoT Core MQTT."""
    
    def __init__(
        self,
        endpoint=None,
        cert_path=None,
        key_path=None,
        ca_path=None,
        camera_topic=IOT_CAMERA_TOPIC
    ):
        """
        Initialize the video receiver.
        
        Args:
            endpoint: AWS IoT Core endpoint
            cert_path: Path to device certificate
            key_path: Path to private key
            ca_path: Path to Amazon Root CA
            camera_topic: MQTT topic to subscribe to
        """
        self.endpoint = endpoint or IOT_CORE_ENDPOINT
        self.cert_path = cert_path or IOT_CORE_CERT_PATH
        self.key_path = key_path or IOT_CORE_KEY_PATH
        self.ca_path = ca_path or IOT_CORE_ROOT_CA_PATH
        self.camera_topic = camera_topic
        
        self.mqtt_connection = None
        self.connected = False
        
        # Frame buffer (thread-safe)
        self._frame_buffer = deque(maxlen=MAX_FRAME_BUFFER)
        self._current_frame = None
        self._frame_lock = threading.Lock()
        
        # Stats
        self.frames_received = 0
        self.last_frame_time = None
        self.device_status = {}
        
    def connect(self):
        """Connect to AWS IoT Core and subscribe to camera topic."""
        try:
            from awscrt import io, mqtt
            from awsiot import mqtt_connection_builder
            
            # Create event loop group and host resolver
            event_loop_group = io.EventLoopGroup(1)
            host_resolver = io.DefaultHostResolver(event_loop_group)
            client_bootstrap = io.ClientBootstrap(event_loop_group, host_resolver)
            
            # Create MQTT connection
            self.mqtt_connection = mqtt_connection_builder.mtls_from_path(
                endpoint=self.endpoint,
                cert_filepath=self.cert_path,
                pri_key_filepath=self.key_path,
                ca_filepath=self.ca_path,
                client_bootstrap=client_bootstrap,
                client_id=f"ec2-receiver-{int(time.time())}",
                clean_session=False,
                keep_alive_secs=30
            )
            
            # Connect
            logger.info(f"Connecting to AWS IoT Core at {self.endpoint}...")
            connect_future = self.mqtt_connection.connect()
            connect_future.result(timeout=10)
            
            self.connected = True
            logger.info("✅ Connected to AWS IoT Core")
            
            # Subscribe to camera frames
            self._subscribe_to_camera()
            
            # Subscribe to camera status
            self._subscribe_to_status()
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to AWS IoT Core: {e}")
            import traceback
            traceback.print_exc()
            return False
    
    def _subscribe_to_camera(self):
        """Subscribe to camera frames topic."""
        from awscrt.mqtt import QoS
        
        def on_message(topic, payload, **kwargs):
            """Callback for received camera frames."""
            try:
                data = json.loads(payload)
                frame_b64 = data.get("frame")
                
                if frame_b64:
                    # Decode base64 to image
                    frame_bytes = base64.b64decode(frame_b64)
                    nparr = np.frombuffer(frame_bytes, np.uint8)
                    frame = cv2.imdecode(nparr, cv2.IMREAD_COLOR)
                    
                    if frame is not None:
                        with self._frame_lock:
                            self._current_frame = frame
                            self._frame_buffer.append({
                                "frame": frame,
                                "frame_id": data.get("frame_id", 0),
                                "device_id": data.get("device_id", "unknown"),
                                "timestamp": data.get("timestamp"),
                                "received_at": datetime.utcnow()
                            })
                        
                        self.frames_received += 1
                        self.last_frame_time = time.time()
                        
                        if self.frames_received % 100 == 0:
                            logger.info(f"Received {self.frames_received} frames")
                            
            except Exception as e:
                logger.error(f"Error processing frame: {e}")
        
        logger.info(f"Subscribing to {self.camera_topic}...")
        subscribe_future, _ = self.mqtt_connection.subscribe(
            topic=self.camera_topic,
            qos=QoS.AT_MOST_ONCE,
            callback=on_message
        )
        subscribe_future.result(timeout=10)
        logger.info(f"✅ Subscribed to {self.camera_topic}")
    
    def _subscribe_to_status(self):
        """Subscribe to camera status topic."""
        from awscrt.mqtt import QoS
        
        def on_status(topic, payload, **kwargs):
            """Callback for camera status updates."""
            try:
                data = json.loads(payload)
                device_id = data.get("device_id", "unknown")
                self.device_status[device_id] = {
                    "status": data.get("status"),
                    "timestamp": data.get("timestamp"),
                    "received_at": datetime.utcnow()
                }
                logger.info(f"Camera {device_id}: {data.get('status')}")
            except Exception as e:
                logger.warning(f"Error processing status: {e}")
        
        subscribe_future, _ = self.mqtt_connection.subscribe(
            topic=IOT_STATUS_TOPIC,
            qos=QoS.AT_LEAST_ONCE,
            callback=on_status
        )
        subscribe_future.result(timeout=10)
        logger.info(f"✅ Subscribed to {IOT_STATUS_TOPIC}")
    
    def disconnect(self):
        """Disconnect from AWS IoT Core."""
        if self.mqtt_connection:
            try:
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                logger.info("Disconnected from AWS IoT Core")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        self.connected = False
    
    def get_frame(self):
        """
        Get the latest frame.
        
        Returns:
            numpy array: Latest frame, or None if no frame available
        """
        with self._frame_lock:
            return self._current_frame.copy() if self._current_frame is not None else None
    
    def get_frame_with_metadata(self):
        """
        Get the latest frame with metadata.
        
        Returns:
            dict: Frame data with metadata, or None if no frame available
        """
        with self._frame_lock:
            if self._frame_buffer:
                data = self._frame_buffer[-1].copy()
                data["frame"] = data["frame"].copy()
                return data
            return None
    
    def get_buffered_frames(self, count=None):
        """
        Get buffered frames.
        
        Args:
            count: Number of frames to get (None for all)
            
        Returns:
            list: List of frame data dicts
        """
        with self._frame_lock:
            if count:
                return list(self._frame_buffer)[-count:]
            return list(self._frame_buffer)
    
    def is_receiving(self):
        """Check if frames are being received."""
        if self.last_frame_time is None:
            return False
        return (time.time() - self.last_frame_time) < 5  # No frame in 5 seconds = not receiving
    
    def get_stats(self):
        """Get receiver statistics."""
        return {
            "connected": self.connected,
            "receiving": self.is_receiving(),
            "frames_received": self.frames_received,
            "last_frame_time": self.last_frame_time,
            "buffer_size": len(self._frame_buffer),
            "device_status": self.device_status
        }


# Singleton instance
_receiver = None


def get_video_receiver():
    """Get singleton video receiver instance."""
    global _receiver
    if _receiver is None:
        _receiver = MQTTVideoReceiver()
    return _receiver


if __name__ == "__main__":
    # Test the receiver
    receiver = MQTTVideoReceiver()
    
    if receiver.connect():
        print("Receiver started. Waiting for frames...")
        try:
            while True:
                time.sleep(1)
                stats = receiver.get_stats()
                print(f"Frames: {stats['frames_received']}, Receiving: {stats['receiving']}")
                
                frame = receiver.get_frame()
                if frame is not None:
                    cv2.imshow("Remote Camera", frame)
                    if cv2.waitKey(1) & 0xFF == ord('q'):
                        break
                        
        except KeyboardInterrupt:
            print("Stopping...")
        finally:
            receiver.disconnect()
            cv2.destroyAllWindows()
    else:
        print("Failed to connect")
