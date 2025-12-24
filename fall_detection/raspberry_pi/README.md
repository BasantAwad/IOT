# Raspberry Pi Camera Streamer for NovaCare
# ==========================================

This directory contains the camera streaming component for Raspberry Pi.

## Setup

1. **Copy this folder to your Raspberry Pi**

2. **Install dependencies:**
   ```bash
   pip install -r pi_requirements.txt
   
   # For Pi Camera support (optional):
   sudo apt install -y python3-picamera2
   ```

3. **Copy your IoT certificates to `certs/` folder:**
   - `device.pem.crt` - Device certificate
   - `private.pem.key` - Private key
   - `AmazonRootCA1.pem` - Amazon Root CA

4. **Update the endpoint** in `pi_camera_streamer.py` if different from:
   ```
   a3vbyo79k8vjec-ats.iot.us-east-1.amazonaws.com
   ```

## Usage

```bash
# Basic usage (streams forever)
python pi_camera_streamer.py

# With custom settings
python pi_camera_streamer.py --fps 15 --quality 60 --camera 0

# Stream for 60 seconds
python pi_camera_streamer.py --duration 60
```

## Command Line Arguments

| Argument | Default | Description |
|----------|---------|-------------|
| `--endpoint` | AWS IoT endpoint | AWS IoT Core endpoint |
| `--cert` | `certs/device.pem.crt` | Device certificate path |
| `--key` | `certs/private.pem.key` | Private key path |
| `--ca` | `certs/AmazonRootCA1.pem` | Root CA path |
| `--device-id` | `raspi-camera-01` | Device identifier |
| `--camera` | `0` | Camera ID (0 for Pi Camera or USB) |
| `--fps` | `10` | Target frames per second |
| `--quality` | `50` | JPEG quality (0-100) |
| `--duration` | `None` | Stream duration in seconds |

## Run as a Service

To run the streamer automatically on boot:

```bash
# Copy the service file
sudo cp novacare-camera.service /etc/systemd/system/

# Enable and start
sudo systemctl enable novacare-camera
sudo systemctl start novacare-camera

# Check status
sudo systemctl status novacare-camera
```
