"""
Raspberry Pi Camera Streamer for NovaCare Fall Detection
=========================================================
Captures frames from Pi Camera and streams to AWS IoT Core via MQTT.
"""

import cv2
import base64
import json
import time
import logging
import argparse
import sys
from datetime import datetime

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# AWS IoT configuration
IOT_ENDPOINT = "a3vbyo79k8vjec-ats.iot.us-east-1.amazonaws.com"
IOT_CAMERA_TOPIC = "novacare/camera/frames"
IOT_STATUS_TOPIC = "novacare/camera/status"
DEVICE_ID = "raspi-camera-01"

# Camera configuration
CAMERA_ID = 0
FRAME_WIDTH = 640
FRAME_HEIGHT = 480
TARGET_FPS = 10  # FPS to stream (balance quality vs bandwidth)
JPEG_QUALITY = 50  # JPEG compression quality (0-100)


class PiCameraStreamer:
    """Streams camera frames to AWS IoT Core via MQTT."""
    
    def __init__(
        self,
        endpoint=IOT_ENDPOINT,
        cert_path="certs/device.pem.crt",
        key_path="certs/private.pem.key",
        ca_path="certs/AmazonRootCA1.pem",
        device_id=DEVICE_ID
    ):
        """
        Initialize the camera streamer.
        
        Args:
            endpoint: AWS IoT Core endpoint
            cert_path: Path to device certificate
            key_path: Path to private key
            ca_path: Path to Amazon Root CA
            device_id: Unique identifier for this device
        """
        self.endpoint = endpoint
        self.cert_path = cert_path
        self.key_path = key_path
        self.ca_path = ca_path
        self.device_id = device_id
        
        self.mqtt_connection = None
        self.connected = False
        self.camera = None
        self.running = False
        
    def connect_mqtt(self):
        """Connect to AWS IoT Core."""
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
                client_id=f"{self.device_id}-{int(time.time())}",
                clean_session=False,
                keep_alive_secs=30
            )
            
            # Connect
            logger.info(f"Connecting to AWS IoT Core at {self.endpoint}...")
            connect_future = self.mqtt_connection.connect()
            connect_future.result(timeout=10)
            
            self.connected = True
            logger.info("✅ Connected to AWS IoT Core")
            
            # Publish online status
            self._publish_status("online")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to connect to AWS IoT Core: {e}")
            return False
    
    def disconnect_mqtt(self):
        """Disconnect from AWS IoT Core."""
        if self.mqtt_connection:
            try:
                self._publish_status("offline")
                disconnect_future = self.mqtt_connection.disconnect()
                disconnect_future.result(timeout=5)
                logger.info("Disconnected from AWS IoT Core")
            except Exception as e:
                logger.warning(f"Error during disconnect: {e}")
        self.connected = False
    
    def _publish_status(self, status):
        """Publish device status."""
        if not self.connected:
            return
            
        message = json.dumps({
            "device_id": self.device_id,
            "status": status,
            "timestamp": datetime.utcnow().isoformat() + "Z"
        })
        
        try:
            from awscrt.mqtt import QoS
            self.mqtt_connection.publish(
                topic=IOT_STATUS_TOPIC,
                payload=message,
                qos=QoS.AT_LEAST_ONCE
            )
        except Exception as e:
            logger.warning(f"Failed to publish status: {e}")
    
    def init_camera(self, camera_id=CAMERA_ID):
        """Initialize the camera."""
        logger.info(f"Initializing camera {camera_id}...")
        
        # Try Pi Camera first via libcamera
        try:
            from picamera2 import Picamera2
            self.camera = Picamera2()
            config = self.camera.create_preview_configuration(
                main={"size": (FRAME_WIDTH, FRAME_HEIGHT), "format": "RGB888"}
            )
            self.camera.configure(config)
            self.camera.start()
            self._camera_type = "picamera2"
            logger.info("✅ Pi Camera initialized via picamera2")
            return True
        except ImportError:
            logger.info("picamera2 not available, trying OpenCV...")
        except Exception as e:
            logger.warning(f"picamera2 failed: {e}, trying OpenCV...")
        
        # Fall back to OpenCV (USB webcam or Pi Camera via v4l2)
        try:
            self.camera = cv2.VideoCapture(camera_id)
            if not self.camera.isOpened():
                raise RuntimeError("Failed to open camera")
                
            self.camera.set(cv2.CAP_PROP_FRAME_WIDTH, FRAME_WIDTH)
            self.camera.set(cv2.CAP_PROP_FRAME_HEIGHT, FRAME_HEIGHT)
            self.camera.set(cv2.CAP_PROP_FPS, TARGET_FPS)
            
            self._camera_type = "opencv"
            logger.info(f"✅ Camera initialized via OpenCV")
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize camera: {e}")
            return False
    
    def capture_frame(self):
        """Capture a single frame from the camera."""
        if self._camera_type == "picamera2":
            frame = self.camera.capture_array()
            # Convert RGB to BGR for consistency with OpenCV
            frame = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            return True, frame
        else:
            return self.camera.read()
    
    def release_camera(self):
        """Release camera resources."""
        if self.camera:
            if self._camera_type == "picamera2":
                self.camera.stop()
            else:
                self.camera.release()
            logger.info("Camera released")
    
    def stream(self, duration=None):
        """
        Stream camera frames to AWS IoT Core.
        
        Args:
            duration: Duration in seconds (None for infinite)
        """
        if not self.connected:
            logger.error("Not connected to AWS IoT Core")
            return
            
        from awscrt.mqtt import QoS
        
        self.running = True
        frame_interval = 1.0 / TARGET_FPS
        frame_count = 0
        start_time = time.time()
        
        logger.info(f"Starting stream at {TARGET_FPS} FPS (JPEG quality: {JPEG_QUALITY})...")
        
        try:
            while self.running:
                loop_start = time.time()
                
                # Check duration
                if duration and (time.time() - start_time) > duration:
                    break
                
                # Capture frame
                ret, frame = self.capture_frame()
                if not ret:
                    logger.warning("Failed to capture frame")
                    time.sleep(0.1)
                    continue
                
                # Compress to JPEG
                encode_params = [cv2.IMWRITE_JPEG_QUALITY, JPEG_QUALITY]
                _, jpeg_buffer = cv2.imencode('.jpg', frame, encode_params)
                
                # Convert to base64
                frame_b64 = base64.b64encode(jpeg_buffer).decode('utf-8')
                
                # Create message
                message = json.dumps({
                    "device_id": self.device_id,
                    "frame": frame_b64,
                    "frame_id": frame_count,
                    "timestamp": datetime.utcnow().isoformat() + "Z",
                    "width": FRAME_WIDTH,
                    "height": FRAME_HEIGHT
                })
                
                # Publish to IoT Core
                try:
                    self.mqtt_connection.publish(
                        topic=IOT_CAMERA_TOPIC,
                        payload=message,
                        qos=QoS.AT_MOST_ONCE  # Use QoS 0 for video frames (faster)
                    )
                    frame_count += 1
                    
                    if frame_count % (TARGET_FPS * 10) == 0:  # Log every 10 seconds
                        elapsed = time.time() - start_time
                        actual_fps = frame_count / elapsed
                        logger.info(f"Streamed {frame_count} frames ({actual_fps:.1f} FPS actual)")
                        
                except Exception as e:
                    logger.error(f"Failed to publish frame: {e}")
                
                # Rate limiting
                elapsed = time.time() - loop_start
                sleep_time = frame_interval - elapsed
                if sleep_time > 0:
                    time.sleep(sleep_time)
                    
        except KeyboardInterrupt:
            logger.info("Stopping stream...")
        finally:
            self.running = False
            
        elapsed = time.time() - start_time
        logger.info(f"Streamed {frame_count} frames in {elapsed:.1f}s ({frame_count/elapsed:.1f} FPS)")
    
    def stop(self):
        """Stop streaming."""
        self.running = False


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(description="Pi Camera Streamer for NovaCare")
    parser.add_argument("--endpoint", default=IOT_ENDPOINT, help="AWS IoT Core endpoint")
    parser.add_argument("--cert", default="certs/device.pem.crt", help="Device certificate path")
    parser.add_argument("--key", default="certs/private.pem.key", help="Private key path")
    parser.add_argument("--ca", default="certs/AmazonRootCA1.pem", help="Root CA path")
    parser.add_argument("--device-id", default=DEVICE_ID, help="Device identifier")
    parser.add_argument("--camera", type=int, default=0, help="Camera ID")
    parser.add_argument("--fps", type=int, default=TARGET_FPS, help="Target FPS")
    parser.add_argument("--quality", type=int, default=JPEG_QUALITY, help="JPEG quality (0-100)")
    parser.add_argument("--duration", type=int, default=None, help="Stream duration in seconds")
    
    args = parser.parse_args()
    
    # Update globals based on args
    global TARGET_FPS, JPEG_QUALITY, CAMERA_ID
    TARGET_FPS = args.fps
    JPEG_QUALITY = args.quality
    CAMERA_ID = args.camera
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         NovaCare Pi Camera Streamer                       ║
    ║         Streaming to AWS IoT Core                         ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    
    streamer = PiCameraStreamer(
        endpoint=args.endpoint,
        cert_path=args.cert,
        key_path=args.key,
        ca_path=args.ca,
        device_id=args.device_id
    )
    
    # Initialize camera
    if not streamer.init_camera(args.camera):
        logger.error("Failed to initialize camera")
        sys.exit(1)
    
    # Connect to AWS IoT Core
    if not streamer.connect_mqtt():
        streamer.release_camera()
        logger.error("Failed to connect to AWS IoT Core")
        sys.exit(1)
    
    try:
        # Start streaming
        streamer.stream(duration=args.duration)
    finally:
        # Cleanup
        streamer.disconnect_mqtt()
        streamer.release_camera()
    
    logger.info("Streamer stopped")


if __name__ == "__main__":
    main()
