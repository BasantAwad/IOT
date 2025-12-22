#!/bin/bash
# NovaCare Fall Detection System - Setup Script for Raspberry Pi / Linux

echo "=========================================="
echo " NovaCare Fall Detection System - Setup"
echo "=========================================="
echo

cd "$(dirname "$0")"

echo "[1/3] Creating virtual environment..."
python3 -m venv .venv

echo "[2/3] Activating virtual environment..."
source .venv/bin/activate

echo "[3/3] Installing dependencies..."
pip install --upgrade pip
pip install -r requirements.txt

echo
echo "=========================================="
echo " Setup Complete!"
echo "=========================================="
echo
echo "To run the application:"
echo "  1. source .venv/bin/activate"
echo "  2. python run_camera.py"
echo "  3. Open browser to http://localhost:5000"
echo
echo "Edit config.py to set your MQTT broker IP"
echo "=========================================="
