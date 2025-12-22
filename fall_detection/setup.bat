@echo off
echo ==========================================
echo  NovaCare Fall Detection System - Setup
echo ==========================================
echo.

cd /d %~dp0

echo [1/3] Creating virtual environment...
python -m venv .venv

echo [2/3] Activating virtual environment...
call .venv\Scripts\activate.bat

echo [3/3] Installing dependencies...
pip install --upgrade pip
pip install -r requirements.txt

echo.
echo ==========================================
echo  Setup Complete!
echo ==========================================
echo.
echo To run the application:
echo   1. Open Command Prompt in this folder
echo   2. Run: .venv\Scripts\activate
echo   3. Run: python run_camera.py
echo   4. Open browser to http://localhost:5000
echo.
echo Edit config.py to set your MQTT broker IP
echo ==========================================
pause
