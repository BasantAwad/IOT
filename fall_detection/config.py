# Fall Detection Configuration
# ============================

# MQTT Configuration
MQTT_BROKER = "localhost"  # Change to your MQTT broker IP (e.g., "192.168.1.100")
MQTT_PORT = 1883
MQTT_TOPIC = "novacare/fall"
MQTT_CLIENT_ID = "fall_detector_pi"

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
