# EC2 Deployment for NovaCare Fall Detection
# ============================================

This directory contains deployment scripts for running NovaCare on AWS EC2.

## Quick Start

### 1. Launch EC2 Instance
- **AMI**: Ubuntu 24.04 LTS
- **Instance Type**: c7i-flex.large or larger
- **Security Group**: Open ports 22 (SSH) and 5000 (Dashboard)

### 2. Copy Files to EC2
```bash
# From your local machine
scp -r /path/to/fall_detection ubuntu@<EC2_IP>:~/novacare
```

### 3. Run Deployment Script
```bash
# SSH into EC2
ssh ubuntu@<EC2_IP>

# Run deployment
cd ~/novacare/deploy
chmod +x deploy_ec2.sh
./deploy_ec2.sh
```

### 4. Copy IoT Certificates
```bash
# Copy your certificates to ~/novacare/certs/
mkdir -p ~/novacare/certs
# Copy device.pem.crt, private.pem.key, AmazonRootCA1.pem
```

### 5. Test & Start
```bash
# Test manually
cd ~/novacare
source .venv/bin/activate
python run_camera_ec2.py --source remote

# Start as service
sudo systemctl start novacare
sudo systemctl status novacare
```

## Files
- `deploy_ec2.sh` - Main deployment script
- `ec2_requirements.txt` - Python dependencies
- `novacare.service` - Systemd service file

## Useful Commands
```bash
# View logs
sudo journalctl -u novacare -f

# Restart service
sudo systemctl restart novacare

# Stop service
sudo systemctl stop novacare
```
