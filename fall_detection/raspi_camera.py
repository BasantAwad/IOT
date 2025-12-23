"""
Raspberry Pi Camera Fall Detection System
==========================================
Captures frames from Raspberry Pi Camera, runs fall detection,
publishes events via MQTT, and streams video to Flask dashboard.

Run this script on your Raspberry Pi:
    python raspi_camera.py

Access the dashboard:
    http://<pi-ip-address>:5000
"""

import cv2
import os
import sys
import time
import logging
import threading
from flask import Flask, Response, render_template, jsonify

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Try to import Pi Camera library
PI_CAMERA_AVAILABLE = False
try:
    from picamera2 import Picamera2
    PI_CAMERA_AVAILABLE = True
    logger.info("PiCamera2 library loaded successfully")
except ImportError:
    logger.warning("PiCamera2 not available - will use OpenCV camera fallback")

# Import local modules
from fall_detector import FallDetector
from clip_saver import ClipSaver
import config

# Import MQTT publisher - will use AWS IoT if configured, else local MQTT
try:
    from aws_iot_client import get_mqtt_publisher
    USE_AWS_IOT = True
except ImportError:
    from mqtt_client import MQTTPublisher
    USE_AWS_IOT = False
    def get_mqtt_publisher():
        return MQTTPublisher()

# Flask app
app = Flask(__name__)

# Global state
output_frame = None
frame_lock = threading.Lock()
fall_events = []
fall_events_lock = threading.Lock()
system_status = {
    'camera': 'initializing',
    'camera_type': 'unknown',
    'mqtt': 'disconnected',
    'detection': 'initializing',
    'last_fall': None
}


class PiCameraCapture:
    """Raspberry Pi Camera capture using PiCamera2."""
    
    def __init__(self, width=640, height=480, fps=30):
        self.width = width
        self.height = height
        self.fps = fps
        self.camera = None
        self.started = False
        
    def start(self):
        """Initialize and start the Pi Camera."""
        try:
            self.camera = Picamera2()
            
            # Configure camera
            config = self.camera.create_preview_configuration(
                main={
                    "format": "RGB888",
                    "size": (self.width, self.height)
                }
            )
            self.camera.configure(config)
            self.camera.start()
            self.started = True
            logger.info(f"Pi Camera started: {self.width}x{self.height} @ {self.fps}fps")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start Pi Camera: {e}")
            return False
    
    def read(self):
        """Read a frame from the camera."""
        if not self.started:
            return False, None
            
        try:
            # Capture frame (RGB format)
            frame = self.camera.capture_array()
            
            # Convert RGB to BGR for OpenCV compatibility
            frame_bgr = cv2.cvtColor(frame, cv2.COLOR_RGB2BGR)
            
            return True, frame_bgr
            
        except Exception as e:
            logger.error(f"Failed to capture frame: {e}")
            return False, None
    
    def release(self):
        """Stop and release the camera."""
        if self.camera:
            try:
                self.camera.stop()
                self.camera.close()
            except:
                pass
        self.started = False
        logger.info("Pi Camera released")
    
    def isOpened(self):
        """Check if camera is running."""
        return self.started


class FallbackCameraCapture:
    """Fallback to OpenCV VideoCapture for non-Pi environments."""
    
    def __init__(self, camera_id=0, width=640, height=480, fps=30):
        self.camera_id = camera_id
        self.width = width
        self.height = height
        self.fps = fps
        self.cap = None
        
    def start(self):
        """Initialize and start the camera."""
        try:
            self.cap = cv2.VideoCapture(self.camera_id)
            
            if not self.cap.isOpened():
                logger.error(f"Could not open camera {self.camera_id}")
                return False
            
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)
            self.cap.set(cv2.CAP_PROP_FPS, self.fps)
            
            logger.info(f"OpenCV camera {self.camera_id} started: {self.width}x{self.height}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to start OpenCV camera: {e}")
            return False
    
    def read(self):
        """Read a frame from the camera."""
        if self.cap is None:
            return False, None
        return self.cap.read()
    
    def release(self):
        """Release the camera."""
        if self.cap:
            self.cap.release()
        logger.info("OpenCV camera released")
    
    def isOpened(self):
        """Check if camera is open."""
        return self.cap is not None and self.cap.isOpened()


def get_camera():
    """Get the appropriate camera based on availability."""
    if PI_CAMERA_AVAILABLE:
        logger.info("Using Raspberry Pi Camera (PiCamera2)")
        return PiCameraCapture(
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS
        ), "picamera"
    else:
        logger.info("Using OpenCV fallback camera")
        return FallbackCameraCapture(
            camera_id=config.CAMERA_ID,
            width=config.CAMERA_WIDTH,
            height=config.CAMERA_HEIGHT,
            fps=config.CAMERA_FPS
        ), "opencv"


def detect_and_publish():
    """
    Main detection loop.
    Captures frames, runs fall detection, publishes events, saves clips.
    """
    global output_frame, system_status
    
    logger.info("Initializing fall detection system...")
    
    # Get camera
    camera, camera_type = get_camera()
    system_status['camera_type'] = camera_type
    
    if not camera.start():
        logger.error("Failed to start camera!")
        system_status['camera'] = 'error'
        return
    
    system_status['camera'] = 'connected'
    logger.info(f"Camera initialized successfully ({camera_type})")
    
    # Initialize fall detector
    detector = FallDetector(confidence_threshold=config.FALL_CONFIDENCE_THRESHOLD)
    system_status['detection'] = 'running'
    logger.info("Fall detector initialized")
    
    # Initialize clip saver
    clip_saver = ClipSaver()
    logger.info(f"Clip saver initialized, saving to: {config.SAVE_CLIPS_DIR}")
    
    # Initialize MQTT (uses AWS IoT if configured, else local MQTT)
    mqtt_publisher = get_mqtt_publisher()
    if mqtt_publisher.connected if hasattr(mqtt_publisher, 'connected') else mqtt_publisher.connect():
        system_status['mqtt'] = 'connected'
        mqtt_publisher.publish_status('online')
        mqtt_type = "AWS IoT Core" if USE_AWS_IOT else "Local MQTT"
        logger.info(f"{mqtt_type} connected")
    else:
        system_status['mqtt'] = 'disconnected'
        logger.warning("MQTT connection failed - events will not be published")
    
    last_fall_time = 0
    frame_count = 0
    
    try:
        while True:
            ret, frame = camera.read()
            
            if not ret or frame is None:
                logger.warning("Failed to read frame")
                time.sleep(0.1)
                continue
            
            frame_count += 1
            
            # Run fall detection
            is_fall, confidence, annotated_frame = detector.predict(frame)
            
            # Add camera type overlay
            cv2.putText(
                annotated_frame,
                f"Camera: {camera_type.upper()}",
                (annotated_frame.shape[1] - 180, 30),
                cv2.FONT_HERSHEY_SIMPLEX,
                0.5,
                (255, 255, 255),
                1
            )
            
            # Add frame to clip buffer
            clip_saver.add_frame(frame)
            
            # Handle fall detection
            if is_fall:
                current_time = time.time()
                if (current_time - last_fall_time) > config.FALL_COOLDOWN_SECONDS:
                    last_fall_time = current_time
                    
                    logger.warning(f"FALL DETECTED! Confidence: {confidence:.1%}")
                    
                    # Trigger clip save
                    clip_path = clip_saver.trigger_save()
                    
                    # Publish MQTT event
                    if system_status['mqtt'] == 'connected':
                        mqtt_publisher.publish_fall_event(confidence, clip_path)
                    
                    # Add to event list
                    event = {
                        'timestamp': int(current_time),
                        'timestamp_str': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'confidence': round(confidence, 3),
                        'clip_path': clip_path
                    }
                    with fall_events_lock:
                        fall_events.insert(0, event)
                        if len(fall_events) > 50:
                            fall_events.pop()
                    
                    system_status['last_fall'] = event['timestamp_str']
            
            # Update output frame for streaming
            with frame_lock:
                output_frame = annotated_frame.copy()
            
            # Control frame rate
            time.sleep(1.0 / config.CAMERA_FPS)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        camera.release()
        clip_saver.force_save()
        if system_status['mqtt'] == 'connected':
            mqtt_publisher.publish_status('offline')
            mqtt_publisher.disconnect()
        system_status['camera'] = 'disconnected'
        system_status['detection'] = 'stopped'


def generate_frames():
    """Generator for video streaming."""
    global output_frame
    
    while True:
        with frame_lock:
            if output_frame is None:
                time.sleep(0.1)
                continue
            ret, jpeg = cv2.imencode('.jpg', output_frame,
                                      [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
            frame_bytes = jpeg.tobytes()
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(1.0 / 30)


@app.route('/')
def index():
    """Main dashboard page."""
    return render_template('dashboard.html')


@app.route('/video_feed')
def video_feed():
    """Video streaming route."""
    return Response(
        generate_frames(),
        mimetype='multipart/x-mixed-replace; boundary=frame'
    )


@app.route('/api/status')
def get_status():
    """Get system status."""
    return jsonify(system_status)


@app.route('/api/events')
def get_events():
    """Get recent fall events."""
    with fall_events_lock:
        return jsonify(fall_events[:20])


@app.route('/api/health')
def health():
    """Health check endpoint."""
    return jsonify({'status': 'ok', 'timestamp': int(time.time())})


def main():
    """Main entry point."""
    print("=" * 60)
    print("   Raspberry Pi Fall Detection System")
    print("=" * 60)
    print()
    
    if PI_CAMERA_AVAILABLE:
        print("✓ PiCamera2 detected - using Raspberry Pi Camera")
    else:
        print("⚠ PiCamera2 not found - using OpenCV camera fallback")
    print()
    
    # Create clips directory
    os.makedirs(config.SAVE_CLIPS_DIR, exist_ok=True)
    
    # Start detection thread
    detection_thread = threading.Thread(target=detect_and_publish)
    detection_thread.daemon = True
    detection_thread.start()
    
    # Give detector time to initialize
    time.sleep(2)
    
    # Start Flask server
    print(f"Starting dashboard on http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    print("Press Ctrl+C to stop")
    print()
    
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=False,  # Disable debug mode for production on Pi
        threaded=True,
        use_reloader=False
    )


if __name__ == '__main__':
    main()
