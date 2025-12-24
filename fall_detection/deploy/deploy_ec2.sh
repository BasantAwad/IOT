#!/bin/bash
# ============================================
# NovaCare Fall Detection - EC2 Deployment Script
# For Ubuntu 24.04 LTS
# ============================================

set -e  # Exit on any error

echo ""
echo "╔═══════════════════════════════════════════════════════════╗"
echo "║         NovaCare EC2 Deployment Script                    ║"
echo "║         Ubuntu 24.04 LTS                                  ║"
echo "╚═══════════════════════════════════════════════════════════╝"
echo ""

# Color codes
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Installation directory
INSTALL_DIR="${HOME}/novacare"
VENV_DIR="${INSTALL_DIR}/.venv"

# Step 1: Update system packages
echo -e "${YELLOW}[1/8] Updating system packages...${NC}"
sudo apt update
sudo apt upgrade -y

# Step 2: Install Python 3.10+ and pip
echo -e "${YELLOW}[2/8] Installing Python and dependencies...${NC}"
sudo apt install -y \
    python3 \
    python3-pip \
    python3-venv \
    python3-dev \
    build-essential \
    cmake \
    git

# Step 3: Install OpenCV system dependencies (Ubuntu 24.04 compatible)
echo -e "${YELLOW}[3/8] Installing OpenCV dependencies...${NC}"
sudo apt install -y \
    libgl1 \
    libglib2.0-0t64 \
    libsm6 \
    libxext6 \
    libxrender1 \
    libgtk-3-0t64 \
    libavcodec-dev \
    libavformat-dev \
    libswscale-dev \
    libv4l-dev || echo "Some packages may have different names, continuing..."

# Step 4: Create installation directory
echo -e "${YELLOW}[4/8] Setting up installation directory...${NC}"
mkdir -p "${INSTALL_DIR}"
cd "${INSTALL_DIR}"

# If files don't exist, show instructions
if [ ! -f "run_camera_ec2.py" ]; then
    echo -e "${YELLOW}Project files not found. Please copy project files to ${INSTALL_DIR}${NC}"
    echo ""
    echo "You can use SCP to copy files from your local machine:"
    echo "  scp -r /path/to/fall_detection/* ubuntu@<EC2_IP>:~/novacare/"
    echo ""
    echo "Or clone from git if you have a repository."
    echo ""
    # Continue anyway to set up environment
fi

# Step 5: Create Python virtual environment
echo -e "${YELLOW}[5/8] Creating Python virtual environment...${NC}"
python3 -m venv "${VENV_DIR}"
source "${VENV_DIR}/bin/activate"

# Step 6: Install Python packages
echo -e "${YELLOW}[6/8] Installing Python packages...${NC}"
pip install --upgrade pip

# Install from requirements if exists
if [ -f "deploy/ec2_requirements.txt" ]; then
    pip install -r deploy/ec2_requirements.txt
elif [ -f "requirements.txt" ]; then
    pip install -r requirements.txt
    pip install awsiotsdk awscrt
else
    # Install packages directly
    pip install \
        opencv-python-headless>=4.8.0 \
        mediapipe>=0.10.9 \
        flask>=2.0.0 \
        paho-mqtt>=1.6.0 \
        boto3>=1.26.0 \
        awsiotsdk>=1.21.0 \
        awscrt>=0.19.0 \
        numpy>=1.21.0
fi

# Step 7: Set up systemd service
echo -e "${YELLOW}[7/8] Setting up systemd service...${NC}"
sudo bash -c "cat > /etc/systemd/system/novacare.service << EOF
[Unit]
Description=NovaCare Fall Detection System
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=${USER}
WorkingDirectory=${INSTALL_DIR}
Environment=\"PATH=${VENV_DIR}/bin\"
ExecStart=${VENV_DIR}/bin/python run_camera_ec2.py --source remote --port 5000
Restart=always
RestartSec=10
StandardOutput=journal
StandardError=journal

[Install]
WantedBy=multi-user.target
EOF"

# Step 8: Configure firewall
echo -e "${YELLOW}[8/8] Configuring firewall...${NC}"
# Allow Flask dashboard
sudo ufw allow 5000/tcp 2>/dev/null || true
echo "Note: Also ensure AWS Security Group allows inbound on port 5000"

# Enable and start service (but don't start yet - need certificates)
sudo systemctl daemon-reload
sudo systemctl enable novacare

echo ""
echo -e "${GREEN}✅ Installation complete!${NC}"
echo ""
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo "NEXT STEPS:"
echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
echo ""
echo "1. Copy your AWS IoT Core certificates to ${INSTALL_DIR}/certs/"
echo "   - device.pem.crt"
echo "   - private.pem.key"
echo "   - AmazonRootCA1.pem"
echo ""
echo "2. Update aws_config.py with your settings if needed"
echo ""
echo "3. Test the application:"
echo "   cd ${INSTALL_DIR}"
echo "   source .venv/bin/activate"
echo "   python run_camera_ec2.py --source remote"
echo ""
echo "4. Once tested, start the service:"
echo "   sudo systemctl start novacare"
echo ""
echo "5. View logs:"
echo "   sudo journalctl -u novacare -f"
echo ""
echo "6. Access dashboard at: http://<EC2_PUBLIC_IP>:5000"
echo ""
