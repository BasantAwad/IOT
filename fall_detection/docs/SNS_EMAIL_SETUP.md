# SNS Email Subscription Setup
# =============================

Follow these steps to receive email alerts when falls are detected.

## Step 1: Go to SNS Console
1. Open [AWS SNS Console](https://console.aws.amazon.com/sns/)
2. Select your region: **us-east-1**
3. Click on **Topics** in the left sidebar
4. Click on **novacare-fall-alerts**

## Step 2: Create Subscription
1. Click **Create subscription**
2. Select:
   - **Protocol**: Email
   - **Endpoint**: your-email@example.com
3. Click **Create subscription**

## Step 3: Confirm Email
1. Check your inbox for an email from AWS
2. Click the **Confirm subscription** link
3. You should see "Subscription confirmed!" message

## Step 4: Test Notification
Run this on your EC2 or local machine:
```bash
cd ~/novacare
source .venv/bin/activate
python -c "
from aws_services import get_sns_notifier
n = get_sns_notifier()
if n.enabled:
    n.send_fall_alert(0.95, clip_url='test', device_id='test-device')
    print('Test alert sent! Check your email.')
else:
    print('SNS not enabled')
"
```

## Email Format
You will receive emails like:

```
Subject: 🚨 Fall Detected - NovaCare Alert

A fall has been detected by your NovaCare monitoring system.

Device: fall_detector_pi
Confidence: 95.0%
Time: 2025-12-23T12:00:00Z

Video clip: https://novacare-fall-detection.s3.amazonaws.com/clips/...

This is an automated alert from NovaCare Fall Detection System.
```
