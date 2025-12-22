"""
Fall Detection System - Main Application
=========================================
Captures camera frames, runs fall detection, publishes events via MQTT,
and streams video to Flask dashboard.
"""

import cv2
import os
import sys
import time
import logging
import threading
from flask import Flask, Response, render_template, jsonify
from fall_detector import FallDetector
from mqtt_client import MQTTPublisher
from clip_saver import ClipSaver
import config

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
    'mqtt': 'disconnected',
    'detection': 'initializing',
    'last_fall': None
}


def detect_and_publish():
    """
    Main detection loop.
    Captures frames, runs fall detection, publishes events, saves clips.
    """
    global output_frame, system_status
    
    # Initialize components
    logger.info("Initializing fall detection system...")
    
    # Initialize camera
    logger.info(f"Opening camera {config.CAMERA_ID}...")
    cap = cv2.VideoCapture(config.CAMERA_ID)
    
    if not cap.isOpened():
        logger.error("Failed to open camera!")
        system_status['camera'] = 'error'
        return
        
    cap.set(cv2.CAP_PROP_FRAME_WIDTH, config.CAMERA_WIDTH)
    cap.set(cv2.CAP_PROP_FRAME_HEIGHT, config.CAMERA_HEIGHT)
    cap.set(cv2.CAP_PROP_FPS, config.CAMERA_FPS)
    system_status['camera'] = 'connected'
    logger.info("Camera initialized successfully")
    
    # Initialize fall detector
    detector = FallDetector(confidence_threshold=config.FALL_CONFIDENCE_THRESHOLD)
    system_status['detection'] = 'running'
    logger.info("Fall detector initialized")
    
    # Initialize clip saver
    clip_saver = ClipSaver()
    logger.info(f"Clip saver initialized, saving to: {config.SAVE_CLIPS_DIR}")
    
    # Initialize MQTT
    mqtt_publisher = MQTTPublisher()
    if mqtt_publisher.connect():
        system_status['mqtt'] = 'connected'
        mqtt_publisher.publish_status('online')
        logger.info("MQTT connected")
    else:
        system_status['mqtt'] = 'disconnected'
        logger.warning("MQTT connection failed - events will not be published")
    
    last_fall_time = 0
    
    try:
        while True:
            ret, frame = cap.read()
            if not ret:
                logger.warning("Failed to read frame")
                time.sleep(0.1)
                continue
            
            # Run fall detection
            is_fall, confidence, annotated_frame = detector.predict(frame)
            
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
                        # Keep only last 50 events
                        if len(fall_events) > 50:
                            fall_events.pop()
                    
                    system_status['last_fall'] = event['timestamp_str']
            
            # Update output frame for streaming
            with frame_lock:
                output_frame = annotated_frame.copy()
            
            # Small delay to control frame rate
            time.sleep(1.0 / config.CAMERA_FPS)
            
    except KeyboardInterrupt:
        logger.info("Shutting down...")
    finally:
        cap.release()
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
    # Create clips directory
    os.makedirs(config.SAVE_CLIPS_DIR, exist_ok=True)
    
    # Start detection thread
    detection_thread = threading.Thread(target=detect_and_publish)
    detection_thread.daemon = True
    detection_thread.start()
    
    # Give detector time to initialize
    time.sleep(2)
    
    # Start Flask server
    logger.info(f"Starting dashboard on http://{config.FLASK_HOST}:{config.FLASK_PORT}")
    app.run(
        host=config.FLASK_HOST,
        port=config.FLASK_PORT,
        debug=config.FLASK_DEBUG,
        threaded=True,
        use_reloader=False
    )


if __name__ == '__main__':
    main()
