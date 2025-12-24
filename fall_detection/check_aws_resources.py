"""
AWS Resources Verification Script
==================================
Checks if all required AWS resources are properly deployed and accessible.
"""

import sys
import os

# Add parent directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

try:
    import boto3
    from botocore.exceptions import ClientError, NoCredentialsError
except ImportError:
    print("❌ boto3 is not installed. Run: pip install boto3")
    sys.exit(1)

try:
    from aws_config import (
        AWS_ACCESS_KEY_ID, AWS_SECRET_ACCESS_KEY, AWS_REGION,
        S3_BUCKET_NAME, S3_ENABLED,
        SNS_TOPIC_ARN, SNS_ENABLED,
        DYNAMODB_TABLE_NAME, DYNAMODB_ENABLED,
        IOT_CORE_ENDPOINT, IOT_CORE_ENABLED
    )
except ImportError:
    print("❌ aws_config.py not found")
    sys.exit(1)


def get_session():
    """Create boto3 session with configured credentials."""
    return boto3.Session(
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        region_name=AWS_REGION
    )


def check_credentials():
    """Check if AWS credentials are valid."""
    print("\n" + "="*50)
    print("🔐 CHECKING AWS CREDENTIALS")
    print("="*50)
    
    if AWS_ACCESS_KEY_ID == 'YOUR_ACCESS_KEY_ID':
        print("❌ AWS_ACCESS_KEY_ID not configured (still placeholder)")
        return False
    
    if AWS_SECRET_ACCESS_KEY == 'YOUR_SECRET_ACCESS_KEY':
        print("❌ AWS_SECRET_ACCESS_KEY not configured (still placeholder)")
        return False
    
    try:
        session = get_session()
        sts = session.client('sts')
        identity = sts.get_caller_identity()
        print(f"✅ Credentials valid!")
        print(f"   Account: {identity['Account']}")
        print(f"   User ARN: {identity['Arn']}")
        print(f"   Region: {AWS_REGION}")
        return True
    except NoCredentialsError:
        print("❌ No credentials found")
        return False
    except ClientError as e:
        print(f"❌ Credential error: {e}")
        return False


def check_s3_bucket():
    """Check if S3 bucket exists and is accessible."""
    print("\n" + "="*50)
    print("📦 CHECKING S3 BUCKET")
    print("="*50)
    
    if not S3_ENABLED:
        print("⚠️  S3 is disabled in config")
        return True
    
    print(f"   Bucket: {S3_BUCKET_NAME}")
    
    try:
        session = get_session()
        s3 = session.client('s3')
        
        # Check if bucket exists
        s3.head_bucket(Bucket=S3_BUCKET_NAME)
        print(f"✅ Bucket exists and is accessible")
        
        # Check bucket location
        location = s3.get_bucket_location(Bucket=S3_BUCKET_NAME)
        region = location.get('LocationConstraint') or 'us-east-1'
        print(f"   Location: {region}")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == '404':
            print(f"❌ Bucket does not exist")
        elif error_code == '403':
            print(f"❌ Access denied to bucket")
        else:
            print(f"❌ Error: {e}")
        return False


def check_dynamodb_table():
    """Check if DynamoDB table exists."""
    print("\n" + "="*50)
    print("📊 CHECKING DYNAMODB TABLE")
    print("="*50)
    
    if not DYNAMODB_ENABLED:
        print("⚠️  DynamoDB is disabled in config")
        return True
    
    print(f"   Table: {DYNAMODB_TABLE_NAME}")
    
    try:
        session = get_session()
        dynamodb = session.client('dynamodb')
        
        # Describe table
        response = dynamodb.describe_table(TableName=DYNAMODB_TABLE_NAME)
        table = response['Table']
        
        print(f"✅ Table exists")
        print(f"   Status: {table['TableStatus']}")
        print(f"   Item Count: {table.get('ItemCount', 'N/A')}")
        print(f"   Key Schema: {table['KeySchema']}")
        
        return table['TableStatus'] == 'ACTIVE'
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'ResourceNotFoundException':
            print(f"❌ Table does not exist")
        else:
            print(f"❌ Error: {e}")
        return False


def check_sns_topic():
    """Check if SNS topic exists."""
    print("\n" + "="*50)
    print("📢 CHECKING SNS TOPIC")
    print("="*50)
    
    if not SNS_ENABLED:
        print("⚠️  SNS is disabled in config")
        return True
    
    print(f"   Topic ARN: {SNS_TOPIC_ARN}")
    
    try:
        session = get_session()
        sns = session.client('sns')
        
        # Get topic attributes
        response = sns.get_topic_attributes(TopicArn=SNS_TOPIC_ARN)
        attrs = response['Attributes']
        
        print(f"✅ Topic exists")
        print(f"   Display Name: {attrs.get('DisplayName', 'N/A')}")
        print(f"   Subscriptions: {attrs.get('SubscriptionsConfirmed', 0)} confirmed")
        
        return True
        
    except ClientError as e:
        error_code = e.response['Error']['Code']
        if error_code == 'NotFound':
            print(f"❌ Topic does not exist")
        elif error_code == 'AuthorizationError':
            print(f"❌ Not authorized to access topic")
        else:
            print(f"❌ Error: {e}")
        return False


def check_iot_core():
    """Check if IoT Core endpoint is reachable."""
    print("\n" + "="*50)
    print("🌐 CHECKING AWS IOT CORE")
    print("="*50)
    
    if not IOT_CORE_ENABLED:
        print("⚠️  IoT Core is disabled in config")
        return True
    
    print(f"   Endpoint: {IOT_CORE_ENDPOINT}")
    
    try:
        session = get_session()
        iot = session.client('iot')
        
        # Get endpoint
        response = iot.describe_endpoint(endpointType='iot:Data-ATS')
        endpoint = response['endpointAddress']
        
        print(f"✅ IoT Core accessible")
        print(f"   Data Endpoint: {endpoint}")
        
        # Check if configured endpoint matches
        if IOT_CORE_ENDPOINT != endpoint:
            print(f"⚠️  Warning: Configured endpoint differs from account endpoint")
        
        return True
        
    except ClientError as e:
        print(f"❌ Error: {e}")
        return False


def main():
    """Run all checks."""
    print("\n" + "="*50)
    print("   AWS RESOURCES VERIFICATION")
    print("   NovaCare Fall Detection System")
    print("="*50)
    
    results = {}
    
    # Check credentials first
    results['credentials'] = check_credentials()
    
    if not results['credentials']:
        print("\n❌ Cannot proceed without valid credentials")
        print("\nPlease configure your AWS credentials:")
        print("  1. Set environment variables:")
        print("     $env:AWS_ACCESS_KEY_ID='your_key'")
        print("     $env:AWS_SECRET_ACCESS_KEY='your_secret'")
        print("  2. Or update aws_config.py directly")
        return False
    
    # Check each resource
    results['s3'] = check_s3_bucket()
    results['dynamodb'] = check_dynamodb_table()
    results['sns'] = check_sns_topic()
    results['iot'] = check_iot_core()
    
    # Summary
    print("\n" + "="*50)
    print("📋 SUMMARY")
    print("="*50)
    
    all_passed = True
    for resource, passed in results.items():
        status = "✅" if passed else "❌"
        print(f"   {status} {resource.upper()}")
        if not passed:
            all_passed = False
    
    if all_passed:
        print("\n🎉 All AWS resources are properly deployed!")
    else:
        print("\n⚠️  Some resources need attention. See details above.")
    
    return all_passed


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
