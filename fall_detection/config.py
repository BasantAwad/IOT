# Fall Detection Configuration
# ============================

# Local MQTT Configuration (for optional local broker - NOT needed if using AWS IoT Core)
# Set to False if you only want to use AWS IoT Core for all communication
LOCAL_MQTT_ENABLED = False  # Disable local MQTT, use AWS IoT Core instead
MQTT_BROKER = "localhost"  # Only used if LOCAL_MQTT_ENABLED = True
MQTT_PORT = 1883
MQTT_TOPIC = "novacare/fall"
MQTT_CLIENT_ID = "fall_detector_ec2"

# Camera Configuration
CAMERA_ID = 0  # Use 0 for Pi camera or USB webcam
CAMERA_WIDTH = 640
CAMERA_HEIGHT = 480
CAMERA_FPS = 30

# Fall Detection Settings
FALL_CONFIDENCE_THRESHOLD = 0.7  # Minimum confidence to trigger fall alert
FALL_COOLDOWN_SECONDS = 5  # Minimum time between fall alerts

# Clip Saving Configuration
SAVE_CLIPS_DIR = "clips"
CLIP_BUFFER_SECONDS = 3  # Seconds of video to save before fall
CLIP_POST_SECONDS = 2    # Seconds of video to save after fall

# Flask Dashboard
FLASK_HOST = "0.0.0.0"
FLASK_PORT = 5000
FLASK_DEBUG = True

# Video Source Configuration
# Set to 'local' for USB webcam/Pi camera, 'remote' for MQTT stream from Raspberry Pi
VIDEO_SOURCE = "remote"  # Options: "local" or "remote"

# Remote Video Settings (when VIDEO_SOURCE = "remote")
REMOTE_CAMERA_TOPIC = "novacare/camera/frames"  # Topic to subscribe for video frames
REMOTE_FRAME_TIMEOUT = 5  # Seconds without frames before showing "no signal"
