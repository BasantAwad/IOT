"""
Webcam Test Script
==================
Tests webcam connectivity and displays a live preview.
Use this to verify your camera is working before running the main application.
"""

import cv2
import sys


def test_webcam(camera_id=0):
    """
    Test webcam connectivity and display live preview.
    
    Args:
        camera_id: Camera index to test (default 0)
    """
    print(f"=" * 50)
    print("  NovaCare Webcam Test")
    print(f"=" * 50)
    print(f"\nTesting camera index: {camera_id}")
    print("Press 'q' to quit, 's' to save a snapshot\n")
    
    # Try to open the camera
    cap = cv2.VideoCapture(camera_id)
    
    if not cap.isOpened():
        print(f"❌ ERROR: Could not open camera {camera_id}")
        print("\nTroubleshooting:")
        print("  1. Check if camera is connected")
        print("  2. Try a different camera_id (0, 1, or 2)")
        print("  3. On Raspberry Pi: sudo raspi-config -> Interface -> Camera")
        print("  4. Check if another application is using the camera")
        return False
    
    # Get camera properties
    width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
    height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
    fps = cap.get(cv2.CAP_PROP_FPS)
    
    print(f"✅ Camera opened successfully!")
    print(f"   Resolution: {width}x{height}")
    print(f"   FPS: {fps}")
    print(f"\nDisplaying live preview...\n")
    
    frame_count = 0
    snapshot_count = 0
    
    try:
        while True:
            ret, frame = cap.read()
            
            if not ret:
                print("❌ Failed to grab frame")
                break
            
            frame_count += 1
            
            # Add info overlay
            info_text = f"Camera {camera_id} | {width}x{height} | Frame: {frame_count}"
            cv2.putText(frame, info_text, (10, 30), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            cv2.putText(frame, "Press 'q' to quit, 's' to save snapshot", (10, 60), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255, 255, 255), 1)
            
            # Display the frame
            cv2.imshow('Webcam Test - NovaCare', frame)
            
            # Handle key presses
            key = cv2.waitKey(1) & 0xFF
            
            if key == ord('q'):
                print("\nQuitting...")
                break
            elif key == ord('s'):
                snapshot_count += 1
                filename = f"snapshot_{snapshot_count}.jpg"
                cv2.imwrite(filename, frame)
                print(f"📸 Saved snapshot: {filename}")
                
    except KeyboardInterrupt:
        print("\nInterrupted by user")
    finally:
        cap.release()
        cv2.destroyAllWindows()
    
    print(f"\n✅ Test complete. Captured {frame_count} frames.")
    return True


def list_available_cameras(max_check=5):
    """
    Check which camera indices are available.
    
    Args:
        max_check: Maximum number of camera indices to check
    """
    print("\nScanning for available cameras...")
    available = []
    
    for i in range(max_check):
        cap = cv2.VideoCapture(i)
        if cap.isOpened():
            width = int(cap.get(cv2.CAP_PROP_FRAME_WIDTH))
            height = int(cap.get(cv2.CAP_PROP_FRAME_HEIGHT))
            available.append((i, width, height))
            cap.release()
    
    if available:
        print(f"\n✅ Found {len(available)} camera(s):")
        for cam_id, w, h in available:
            print(f"   Camera {cam_id}: {w}x{h}")
    else:
        print("\n❌ No cameras found!")
    
    return available


if __name__ == '__main__':
    # Parse command line arguments
    camera_id = 0
    if len(sys.argv) > 1:
        if sys.argv[1] == '--list':
            list_available_cameras()
            sys.exit(0)
        else:
            try:
                camera_id = int(sys.argv[1])
            except ValueError:
                print(f"Invalid camera ID: {sys.argv[1]}")
                print("Usage: python test_webcam.py [camera_id]")
                print("       python test_webcam.py --list")
                sys.exit(1)
    
    # List cameras first
    cameras = list_available_cameras()
    
    if cameras:
        # Test the specified camera
        test_webcam(camera_id)
    else:
        print("\nNo cameras available to test.")
        sys.exit(1)
