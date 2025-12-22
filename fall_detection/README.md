# NovaCare Fall Detection System

A complete fall detection system for Raspberry Pi using MediaPipe pose estimation, MQTT event publishing, Flask dashboard, and local clip saving.

## 🚀 Quick Start

### 1. Set Up Virtual Environment

> ⚠️ **Important**: This project requires **Python 3.10** due to MediaPipe compatibility. Python 3.11+ is not supported.

```bash
cd fall_detection

# Create venv with Python 3.10 specifically
py -3.10 -m venv .venv

# Windows
.venv\Scripts\activate

# Linux/macOS/Raspberry Pi
# python3.10 -m venv .venv
# source .venv/bin/activate
```

### 2. Install Dependencies

```bash
pip install --upgrade pip
pip install -r requirements.txt
```

### 3. Configure Settings

Edit `config.py` to set your MQTT broker:

```python
MQTT_BROKER = "YOUR_MQTT_BROKER_IP"  # e.g., "192.168.1.100" or "localhost"
MQTT_PORT = 1883
MQTT_TOPIC = "novacare/fall"
```

### 4. Run the Application

```bash
python run_camera.py
```

### 5. Access the Dashboard

Open your browser to: `http://localhost:5000` (or `http://RASPBERRY_PI_IP:5000`)

## 📁 Project Structure

```
fall_detection/
├── config.py           # Configuration settings
├── requirements.txt    # Python dependencies
├── run_camera.py       # Main application
├── fall_detector.py    # MediaPipe-based fall detection
├── mqtt_client.py      # MQTT publisher
├── clip_saver.py       # Video clip saver
├── templates/
│   └── dashboard.html  # Web dashboard
├── clips/              # Saved fall clips (auto-created)
└── README.md           # This file
```

## 🔧 Configuration Options

| Setting                     | Default         | Description                           |
| --------------------------- | --------------- | ------------------------------------- |
| `MQTT_BROKER`               | `localhost`     | MQTT broker IP address                |
| `MQTT_PORT`                 | `1883`          | MQTT broker port                      |
| `MQTT_TOPIC`                | `novacare/fall` | Topic for fall events                 |
| `CAMERA_ID`                 | `0`             | Camera index (0 for Pi camera/webcam) |
| `FALL_CONFIDENCE_THRESHOLD` | `0.7`           | Minimum confidence to trigger alert   |
| `CLIP_BUFFER_SECONDS`       | `3`             | Seconds of video before fall          |
| `CLIP_POST_SECONDS`         | `2`             | Seconds of video after fall           |

## 📡 MQTT Message Format

Fall events are published as JSON:

```json
{
  "event": "fall_detected",
  "confidence": 0.85,
  "timestamp": 1703254966,
  "timestamp_iso": "2023-12-22T15:22:46",
  "device_id": "fall_detector_pi",
  "clip_path": "clips/fall_20231222_152246_1703254966.mp4"
}
```

## 🎥 API Endpoints

| Endpoint      | Description             |
| ------------- | ----------------------- |
| `/`           | Dashboard UI            |
| `/video_feed` | MJPEG video stream      |
| `/api/status` | System status JSON      |
| `/api/events` | Recent fall events JSON |
| `/api/health` | Health check            |

## 📋 Requirements

- **Python 3.10** (required - MediaPipe 0.10.9 is not compatible with Python 3.11+)
- Camera (Pi camera, USB webcam, or any OpenCV-compatible camera)
- MQTT broker (optional, for event publishing)

## 🔒 Notes

- The system calibrates for 30 frames on startup to learn normal standing posture
- Fall detection uses body orientation, aspect ratio, and velocity analysis
- Clips include 3 seconds before and 2 seconds after detection
- Dashboard auto-refreshes status and events every few seconds

## 🐛 Troubleshooting

**Camera not found:**

- Check `CAMERA_ID` in config.py (try 0, 1, or 2)
- On Raspberry Pi, ensure camera is enabled: `sudo raspi-config`

**MQTT not connecting:**

- Verify broker is running: `mosquitto -v`
- Check firewall allows port 1883

**Low FPS:**

- Reduce `CAMERA_WIDTH` and `CAMERA_HEIGHT` in config.py
- Set `model_complexity=0` in fall_detector.py for faster inference
