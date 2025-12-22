# AWS Configuration for Fall Detection System
# ============================================
# Configure AWS services for cloud integration

import os

# AWS Credentials (set via environment variables for security)
AWS_ACCESS_KEY_ID = os.environ.get('AWS_ACCESS_KEY_ID', 'YOUR_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', 'YOUR_SECRET_ACCESS_KEY')
AWS_REGION = os.environ.get('AWS_REGION', 'us-east-1')

# S3 Configuration (for storing fall clips in cloud)
S3_ENABLED = False  # Set to True to enable S3 uploads
S3_BUCKET_NAME = 'novacare-fall-detection'
S3_CLIPS_PREFIX = 'clips/'  # Prefix for clip files in bucket

# SNS Configuration (for push notifications)
SNS_ENABLED = False  # Set to True to enable SNS notifications
SNS_TOPIC_ARN = 'arn:aws:sns:us-east-1:YOUR_ACCOUNT_ID:novacare-fall-alerts'

# IoT Core Configuration (alternative to MQTT)
IOT_CORE_ENABLED = False  # Set to True to use AWS IoT Core instead of local MQTT
IOT_CORE_ENDPOINT = 'YOUR_IOT_ENDPOINT.iot.us-east-1.amazonaws.com'
IOT_CORE_TOPIC = 'novacare/fall'
IOT_CORE_CERT_PATH = 'certs/device.pem.crt'
IOT_CORE_KEY_PATH = 'certs/private.pem.key'
IOT_CORE_ROOT_CA_PATH = 'certs/AmazonRootCA1.pem'

# DynamoDB Configuration (for storing event history)
DYNAMODB_ENABLED = False  # Set to True to enable DynamoDB logging
DYNAMODB_TABLE_NAME = 'novacare-fall-events'


def get_boto3_session():
    """
    Get a boto3 session with configured credentials.
    
    Returns:
        boto3.Session: Configured AWS session
    """
    try:
        import boto3
        return boto3.Session(
            aws_access_key_id=AWS_ACCESS_KEY_ID,
            aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
            region_name=AWS_REGION
        )
    except ImportError:
        print("boto3 not installed. Run: pip install boto3")
        return None


def get_s3_client():
    """Get an S3 client."""
    session = get_boto3_session()
    return session.client('s3') if session else None


def get_sns_client():
    """Get an SNS client."""
    session = get_boto3_session()
    return session.client('sns') if session else None


def get_dynamodb_resource():
    """Get a DynamoDB resource."""
    session = get_boto3_session()
    return session.resource('dynamodb') if session else None
