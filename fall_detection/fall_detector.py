"""
Fall Detection Module using MediaPipe Pose Estimation
=====================================================
Uses pretrained MediaPipe Pose model to detect falls based on body keypoint analysis.
"""

import cv2
import mediapipe as mp
import numpy as np
from collections import deque
import time


class FallDetector:
    """
    Fall detector using MediaPipe Pose for body keypoint estimation.
    Analyzes body position and movement to detect falls.
    """
    
    def __init__(self, confidence_threshold=0.7):
        """
        Initialize the fall detector.
        
        Args:
            confidence_threshold: Minimum confidence score to report a fall
        """
        self.confidence_threshold = confidence_threshold
        
        # Initialize MediaPipe Pose
        self.mp_pose = mp.solutions.pose
        self.mp_drawing = mp.solutions.drawing_utils
        self.pose = self.mp_pose.Pose(
            static_image_mode=False,
            model_complexity=1,
            enable_segmentation=False,
            min_detection_confidence=0.5,
            min_tracking_confidence=0.5
        )
        
        # History for temporal analysis
        self.position_history = deque(maxlen=30)  # ~1 second at 30fps
        self.velocity_history = deque(maxlen=10)
        self.last_fall_time = 0
        self.fall_cooldown = 5  # seconds
        
        # Body proportion tracking
        self.standing_height_ratio = None
        self.calibration_frames = 0
        self.calibration_needed = 30  # frames to calibrate
        
    def _calculate_body_metrics(self, landmarks, frame_height, frame_width):
        """Calculate key body metrics from pose landmarks."""
        
        # Get key points (MediaPipe Pose landmarks)
        # 0: nose, 11: left shoulder, 12: right shoulder
        # 23: left hip, 24: right hip, 27: left ankle, 28: right ankle
        
        try:
            # Shoulder midpoint
            left_shoulder = landmarks[11]
            right_shoulder = landmarks[12]
            shoulder_y = (left_shoulder.y + right_shoulder.y) / 2
            shoulder_x = (left_shoulder.x + right_shoulder.x) / 2
            
            # Hip midpoint
            left_hip = landmarks[23]
            right_hip = landmarks[24]
            hip_y = (left_hip.y + right_hip.y) / 2
            hip_x = (left_hip.x + right_hip.x) / 2
            
            # Head (nose or use shoulder as reference)
            nose = landmarks[0]
            head_y = nose.y
            
            # Calculate body dimensions
            torso_height = abs(hip_y - shoulder_y)
            head_to_hip = abs(hip_y - head_y)
            
            # Body orientation (horizontal vs vertical)
            body_width = abs(left_shoulder.x - right_shoulder.x)
            body_angle = np.arctan2(
                (left_shoulder.y - left_hip.y) * frame_height,
                (left_shoulder.x - left_hip.x) * frame_width
            )
            body_angle_degrees = abs(np.degrees(body_angle))
            
            # Bounding box aspect ratio
            all_y = [landmarks[i].y for i in [0, 11, 12, 23, 24, 27, 28] 
                     if landmarks[i].visibility > 0.5]
            all_x = [landmarks[i].x for i in [0, 11, 12, 23, 24, 27, 28] 
                     if landmarks[i].visibility > 0.5]
            
            if len(all_y) > 2 and len(all_x) > 2:
                height_extent = max(all_y) - min(all_y)
                width_extent = max(all_x) - min(all_x)
                aspect_ratio = height_extent / (width_extent + 1e-6)
            else:
                aspect_ratio = 1.0
            
            return {
                'head_y': head_y,
                'hip_y': hip_y,
                'shoulder_y': shoulder_y,
                'torso_height': torso_height,
                'head_to_hip': head_to_hip,
                'body_angle': body_angle_degrees,
                'aspect_ratio': aspect_ratio,
                'center_x': (shoulder_x + hip_x) / 2,
                'center_y': (shoulder_y + hip_y) / 2,
                'visibility': np.mean([landmarks[i].visibility for i in [0, 11, 12, 23, 24]])
            }
            
        except Exception as e:
            return None
    
    def predict(self, frame):
        """
        Detect falls in the given frame.
        
        Args:
            frame: BGR image from camera
            
        Returns:
            tuple: (is_fall, confidence, annotated_frame)
        """
        # Convert to RGB for MediaPipe
        rgb_frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        results = self.pose.process(rgb_frame)
        
        annotated_frame = frame.copy()
        is_fall = False
        confidence = 0.0
        
        if results.pose_landmarks:
            # Draw pose landmarks
            self.mp_drawing.draw_landmarks(
                annotated_frame,
                results.pose_landmarks,
                self.mp_pose.POSE_CONNECTIONS,
                self.mp_drawing.DrawingSpec(color=(0, 255, 0), thickness=2, circle_radius=2),
                self.mp_drawing.DrawingSpec(color=(0, 0, 255), thickness=2)
            )
            
            # Calculate body metrics
            h, w = frame.shape[:2]
            metrics = self._calculate_body_metrics(
                results.pose_landmarks.landmark, h, w
            )
            
            if metrics and metrics['visibility'] > 0.5:
                # Add to position history
                self.position_history.append({
                    'time': time.time(),
                    'metrics': metrics
                })
                
                # Calibration phase
                if self.calibration_frames < self.calibration_needed:
                    if metrics['aspect_ratio'] > 1.2:  # More vertical than horizontal
                        if self.standing_height_ratio is None:
                            self.standing_height_ratio = metrics['aspect_ratio']
                        else:
                            self.standing_height_ratio = 0.9 * self.standing_height_ratio + 0.1 * metrics['aspect_ratio']
                    self.calibration_frames += 1
                    
                    # Show calibration status
                    cv2.putText(annotated_frame, f"Calibrating: {self.calibration_frames}/{self.calibration_needed}",
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (255, 255, 0), 2)
                else:
                    # Fall detection logic
                    is_fall, confidence = self._detect_fall(metrics)
                    
                    # Apply cooldown
                    current_time = time.time()
                    if is_fall and (current_time - self.last_fall_time) < self.fall_cooldown:
                        is_fall = False
                        confidence = 0.0
                    elif is_fall:
                        self.last_fall_time = current_time
                    
                    # Draw status
                    status_color = (0, 0, 255) if is_fall else (0, 255, 0)
                    status_text = f"FALL DETECTED! ({confidence:.0%})" if is_fall else "Normal"
                    cv2.putText(annotated_frame, status_text,
                                (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, status_color, 2)
        else:
            cv2.putText(annotated_frame, "No person detected",
                        (10, 30), cv2.FONT_HERSHEY_SIMPLEX, 0.7, (128, 128, 128), 2)
        
        return is_fall, confidence, annotated_frame
    
    def _detect_fall(self, current_metrics):
        """
        Core fall detection algorithm.
        Analyzes body position and movement patterns.
        """
        fall_indicators = []
        
        # 1. Aspect ratio check (body more horizontal than vertical)
        if self.standing_height_ratio:
            ratio_change = current_metrics['aspect_ratio'] / self.standing_height_ratio
            if ratio_change < 0.5:  # Body became significantly more horizontal
                fall_indicators.append(0.4)
        
        if current_metrics['aspect_ratio'] < 0.8:  # Body is horizontal
            fall_indicators.append(0.3)
        
        # 2. Body angle check
        if current_metrics['body_angle'] < 45:  # Body nearly horizontal
            fall_indicators.append(0.3)
        
        # 3. Rapid vertical velocity (sudden drop)
        if len(self.position_history) >= 5:
            recent = list(self.position_history)[-5:]
            y_positions = [p['metrics']['center_y'] for p in recent]
            time_span = recent[-1]['time'] - recent[0]['time']
            
            if time_span > 0:
                velocity = (y_positions[-1] - y_positions[0]) / time_span
                if velocity > 0.5:  # Rapid downward movement
                    fall_indicators.append(0.4)
        
        # 4. Position below normal standing (head closer to bottom of frame)
        if current_metrics['head_y'] > 0.6:  # Head in lower 40% of frame
            fall_indicators.append(0.2)
        
        # Calculate overall confidence
        if fall_indicators:
            confidence = min(sum(fall_indicators), 1.0)
            is_fall = confidence >= self.confidence_threshold
            return is_fall, confidence
        
        return False, 0.0
    
    def reset(self):
        """Reset the detector state."""
        self.position_history.clear()
        self.velocity_history.clear()
        self.calibration_frames = 0
        self.standing_height_ratio = None
    
    def __del__(self):
        """Cleanup resources."""
        if hasattr(self, 'pose'):
            self.pose.close()
