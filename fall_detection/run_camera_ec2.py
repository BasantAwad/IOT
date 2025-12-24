"""
Fall Detection System - Main Application (EC2 Version)
=======================================================
Runs on EC2 to receive camera frames from Raspberry Pi via MQTT,
performs fall detection, and triggers AWS notifications.

Supports two video sources:
- local: USB webcam or connected camera (for testing)
- remote: MQTT stream from Raspberry Pi via AWS IoT Core
"""

import cv2
import os
import sys
import time
import logging
import threading
import argparse
import numpy as np
from flask import Flask, Response, render_template, jsonify
from fall_detector import FallDetector
from mqtt_client import MQTTPublisher
from clip_saver import ClipSaver
import config

# Import AWS services (optional - gracefully degrades if not configured)
try:
    from aws_services import get_dynamodb_logger, get_sns_notifier, get_s3_uploader
    AWS_SERVICES_AVAILABLE = True
except ImportError:
    AWS_SERVICES_AVAILABLE = False

# Import remote video receiver
try:
    from mqtt_video_receiver import MQTTVideoReceiver
    REMOTE_VIDEO_AVAILABLE = True
except ImportError:
    REMOTE_VIDEO_AVAILABLE = False

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Flask app
app = Flask(__name__)

# Global state
output_frame = None
frame_lock = threading.Lock()
fall_events = []
fall_events_lock = threading.Lock()
system_status = {
    'camera': 'initializing',
    'video_source': 'unknown',
    'mqtt': 'disconnected',
    'detection': 'initializing',
    'aws_s3': 'disabled',
    'aws_dynamodb': 'disabled',
    'aws_sns': 'disabled',
    'last_fall': None,
    'frames_processed': 0
}

# Video source (set from command line or config)
video_source_mode = config.VIDEO_SOURCE


class LocalCamera:
    """Wrapper for local camera (USB webcam, Pi camera)."""
    
    def __init__(self, camera_id=0):
        self.camera_id = camera_id
        self.cap = None
        
    def connect(self):
        """Open the camera."""
        logger.info(f"Opening local camera {self.camera_id}...")
        self.cap = cv2.VideoCapture(self.camera_id)
        
        if not self.cap.isOpened():
            logger.error("Failed to open camera!")
            return False
            
        self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
        self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
        self.cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
        
        logger.info("✅ Local camera initialized")
        return True
    
    def get_frame(self):
        """Get a frame from the camera."""
        if self.cap is None:
            return None
        ret, frame = self.cap.read()
        return frame if ret else None
    
    def is_receiving(self):
        """Check if camera is providing frames."""
        return self.cap is not None and self.cap.isOpened()
    
    def disconnect(self):
        """Release the camera."""
        if self.cap:
            self.cap.release()
            logger.info("Local camera released")


class RemoteCamera:
    """Wrapper for remote camera via MQTT."""
    
    def __init__(self):
        self.receiver = None
        
    def connect(self):
        """Connect to MQTT and start receiving frames."""
        if not REMOTE_VIDEO_AVAILABLE:
            logger.error("Remote video receiver not available!")
            return False
            
        self.receiver = MQTTVideoReceiver()
        if self.receiver.connect():
            logger.info("✅ Remote camera connected via MQTT")
            return True
        return False
    
    def get_frame(self):
        """Get the latest frame from MQTT."""
        if self.receiver is None:
            return None
        return self.receiver.get_frame()
    
    def is_receiving(self):
        """Check if frames are being received."""
        if self.receiver is None:
            return False
        return self.receiver.is_receiving()
    
    def get_stats(self):
        """Get receiver statistics."""
        if self.receiver is None:
            return {}
        return self.receiver.get_stats()
    
    def disconnect(self):
        """Disconnect from MQTT."""
        if self.receiver:
            self.receiver.disconnect()
            logger.info("Remote camera disconnected")


def create_no_signal_frame(width=640, height=480, message="No Signal"):
    """Create a 'no signal' placeholder frame."""
    frame = np.zeros((height, width, 3), dtype=np.uint8)
    frame[:] = (30, 30, 30)  # Dark gray
    
    # Add text
    font = cv2.FONT_HERSHEY_SIMPLEX
    text_size = cv2.getTextSize(message, font, 1.5, 2)[0]
    text_x = (width - text_size[0]) // 2
    text_y = (height + text_size[1]) // 2
    cv2.putText(frame, message, (text_x, text_y), font, 1.5, (100, 100, 100), 2)
    
    return frame


def detect_and_publish():
    """
    Main detection loop.
    Captures frames, runs fall detection, publishes events, saves clips.
    """
    global output_frame, system_status
    
    # Initialize components
    logger.info("Initializing fall detection system...")
    logger.info(f"Video source mode: {video_source_mode}")
    
    # Initialize video source
    if video_source_mode == "remote":
        camera = RemoteCamera()
        system_status['video_source'] = 'remote (MQTT)'
    else:
        camera = LocalCamera(config.CAMERA_ID)
        system_status['video_source'] = 'local'
    
    if not camera.connect():
        logger.error("Failed to initialize video source!")
        system_status['camera'] = 'error'
        # Keep running to show error on dashboard
        no_signal = create_no_signal_frame(message="Camera Error")
        with frame_lock:
            output_frame = no_signal
        return
        
    system_status['camera'] = 'connected'
    
    # Initialize fall detector
    detector = FallDetector(confidence_threshold=config.FALL_CONFIDENCE_THRESHOLD)
    system_status['detection'] = 'running'
    logger.info("Fall detector initialized")
    
    # Initialize clip saver
    clip_saver = ClipSaver()
    logger.info(f"Clip saver initialized, saving to: {config.SAVE_CLIPS_DIR}")
    
    # Initialize Local MQTT (for publishing fall events - optional, separate from video MQTT)
    mqtt_publisher = None
    if getattr(config, 'LOCAL_MQTT_ENABLED', True):  # Default to True for backwards compatibility
        mqtt_publisher = MQTTPublisher()
        if mqtt_publisher.connect():
            system_status['mqtt'] = 'connected'
            mqtt_publisher.publish_status('online')
            logger.info("Local MQTT connected")
        else:
            system_status['mqtt'] = 'disconnected'
            logger.warning("Local MQTT connection failed - local events will not be published")
    else:
        system_status['mqtt'] = 'disabled (using AWS IoT Core)'
        logger.info("Local MQTT disabled - using AWS IoT Core for all communication")
    
    # Check AWS services status
    if AWS_SERVICES_AVAILABLE:
        try:
            s3_uploader = get_s3_uploader()
            system_status['aws_s3'] = 'enabled' if s3_uploader.enabled else 'disabled'
        except:
            pass
        try:
            db_logger = get_dynamodb_logger()
            system_status['aws_dynamodb'] = 'enabled' if db_logger.enabled else 'disabled'
        except:
            pass
        try:
            sns = get_sns_notifier()
            system_status['aws_sns'] = 'enabled' if sns.enabled else 'disabled'
        except:
            pass
    
    last_fall_time = 0
    no_frame_count = 0
    frames_processed = 0
    
    try:
        while True:
            frame = camera.get_frame()
            
            if frame is None:
                no_frame_count += 1
                if no_frame_count > 30:  # About 1 second without frames
                    no_signal = create_no_signal_frame(
                        message="Waiting for camera stream..."
                    )
                    with frame_lock:
                        output_frame = no_signal
                    system_status['camera'] = 'waiting'
                time.sleep(0.033)  # ~30 FPS check rate
                continue
            
            no_frame_count = 0
            system_status['camera'] = 'receiving'
            frames_processed += 1
            system_status['frames_processed'] = frames_processed
            
            # Run fall detection
            is_fall, confidence, annotated_frame = detector.predict(frame)
            
            # Add frame to clip buffer
            clip_saver.add_frame(frame)
            
            # Handle fall detection
            if is_fall:
                current_time = time.time()
                if (current_time - last_fall_time) > config.FALL_COOLDOWN_SECONDS:
                    last_fall_time = current_time
                    
                    logger.warning(f"🚨 FALL DETECTED! Confidence: {confidence:.1%}")
                    
                    # Trigger clip save
                    clip_path = clip_saver.trigger_save()
                    
                    # Upload clip to S3
                    s3_url = None
                    if AWS_SERVICES_AVAILABLE:
                        try:
                            s3_uploader = get_s3_uploader()
                            if s3_uploader.enabled and clip_path:
                                s3_url = s3_uploader.upload_sync(clip_path)
                                if s3_url:
                                    logger.info(f"Clip uploaded to S3: {s3_url}")
                        except Exception as e:
                            logger.error(f"S3 upload error: {e}")
                    
                    # Publish local MQTT event (if enabled)
                    if mqtt_publisher and system_status['mqtt'] == 'connected':
                        mqtt_publisher.publish_fall_event(confidence, clip_path)
                    
                    # Add to event list
                    event = {
                        'timestamp': int(current_time),
                        'timestamp_str': time.strftime("%Y-%m-%d %H:%M:%S"),
                        'confidence': round(confidence, 3),
                        'clip_path': clip_path,
                        's3_url': s3_url,
                        'device_id': config.MQTT_CLIENT_ID
                    }
                    with fall_events_lock:
                        fall_events.insert(0, event)
                        # Keep only last 50 events
                        if len(fall_events) > 50:
                            fall_events.pop()
                    
                    system_status['last_fall'] = event['timestamp_str']
                    
                    # AWS: Log event to DynamoDB
                    if AWS_SERVICES_AVAILABLE:
                        try:
                            dynamodb_logger = get_dynamodb_logger()
                            if dynamodb_logger.enabled:
                                dynamodb_logger.log_event_async(event)
                                logger.info("Queued event for DynamoDB logging")
                        except Exception as e:
                            logger.error(f"DynamoDB logging error: {e}")
                    
                    # AWS: Send SNS notification (EMAIL!)
                    if AWS_SERVICES_AVAILABLE:
                        try:
                            sns_notifier = get_sns_notifier()
                            if sns_notifier.enabled:
                                sns_notifier.send_alert_async(
                                    confidence=confidence,
                                    clip_url=s3_url or clip_path,
                                    device_id=config.MQTT_CLIENT_ID
                                )
                                logger.info("📧 SNS fall alert notification sent!")
                        except Exception as e:
                            logger.error(f"SNS notification error: {e}")
            
            # Update output frame for streaming
            with frame_lock:
                output_frame = annotated_frame.copy()
            
            # Small delay to control CPU usage
            time.sleep(0.01)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        camera.disconnect()
        clip_saver.force_save()
        if mqtt_publisher and system_status['mqtt'] == 'connected':
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
                # Show a loading frame
                loading = create_no_signal_frame(message="Loading...")
                ret, jpeg = cv2.imencode('.jpg', loading, 
                                          [cv2.IMWRITE_JPEG_QUALITY, 80])
                if ret:
                    frame_bytes = jpeg.tobytes()
                    yield (b'--frame\r\n'
                           b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
                time.sleep(0.1)
                continue
            ret, jpeg = cv2.imencode('.jpg', output_frame, 
                                      [cv2.IMWRITE_JPEG_QUALITY, 80])
            if not ret:
                continue
            frame_bytes = jpeg.tobytes()
            
        yield (b'--frame\r\n'
               b'Content-Type: image/jpeg\r\n\r\n' + frame_bytes + b'\r\n')
        time.sleep(1.0 / 30)  # Limit stream rate


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
    global video_source_mode
    
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="NovaCare Fall Detection System")
    parser.add_argument(
        "--source", 
        choices=["local", "remote"], 
        default=config.VIDEO_SOURCE,
        help="Video source: 'local' for camera, 'remote' for MQTT stream"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=config.FLASK_PORT,
        help="Flask server port"
    )
    args = parser.parse_args()
    
    video_source_mode = args.source
    
    print("""
    ╔═══════════════════════════════════════════════════════════╗
    ║         NovaCare Fall Detection System                    ║
    ║         EC2 Server Edition                                ║
    ╚═══════════════════════════════════════════════════════════╝
    """)
    print(f"    Video Source: {video_source_mode}")
    print(f"    Dashboard Port: {args.port}")
    print(f"    AWS Services: {'Available' if AWS_SERVICES_AVAILABLE else 'Not available'}")
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
    logger.info(f"Starting dashboard on http://{config.FLASK_HOST}:{args.port}")
    app.run(
        host=config.FLASK_HOST,
        port=args.port,
        debug=False,  # Disable debug mode on EC2
        threaded=True,
        use_reloader=False
    )


if __name__ == '__main__':
    main()
