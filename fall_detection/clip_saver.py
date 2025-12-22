"""
Video Clip Saver Module
=======================
Saves video clips when falls are detected, including frames before and after detection.
"""

import cv2
import os
import time
import threading
from collections import deque
from config import SAVE_CLIPS_DIR, CLIP_BUFFER_SECONDS, CLIP_POST_SECONDS, CAMERA_FPS
import logging


logger = logging.getLogger(__name__)


class ClipSaver:
    """
    Saves video clips with a rolling buffer to capture events 
    including footage before the trigger.
    """
    
    def __init__(self, output_dir=None, buffer_seconds=None, post_seconds=None, fps=None):
        """
        Initialize clip saver.
        
        Args:
            output_dir: Directory to save clips
            buffer_seconds: Seconds of video to keep before trigger
            post_seconds: Seconds of video to record after trigger
            fps: Frames per second
        """
        self.output_dir = output_dir or SAVE_CLIPS_DIR
        self.buffer_seconds = buffer_seconds or CLIP_BUFFER_SECONDS
        self.post_seconds = post_seconds or CLIP_POST_SECONDS
        self.fps = fps or CAMERA_FPS
        
        # Calculate buffer size
        buffer_frames = int(self.fps * self.buffer_seconds)
        self.frame_buffer = deque(maxlen=buffer_frames)
        
        # Ensure output directory exists
        os.makedirs(self.output_dir, exist_ok=True)
        
        # State tracking
        self.is_recording = False
        self.recording_frames = []
        self.post_frames_count = 0
        self.post_frames_needed = int(self.fps * self.post_seconds)
        self.current_clip_path = None
        
        # Lock for thread safety
        self.lock = threading.Lock()
        
    def add_frame(self, frame):
        """
        Add a frame to the rolling buffer.
        
        Args:
            frame: CV2 frame to add
        """
        with self.lock:
            # If recording, add to recording frames
            if self.is_recording:
                self.recording_frames.append(frame.copy())
                self.post_frames_count += 1
                
                # Check if we have enough post-event frames
                if self.post_frames_count >= self.post_frames_needed:
                    self._finalize_clip()
            else:
                # Add to rolling buffer
                self.frame_buffer.append(frame.copy())
                
    def trigger_save(self):
        """
        Trigger clip saving. Call this when a fall is detected.
        
        Returns:
            str: Path where clip will be saved, or None if already recording
        """
        with self.lock:
            if self.is_recording:
                logger.debug("Already recording, ignoring trigger")
                return None
                
            # Start recording
            self.is_recording = True
            self.post_frames_count = 0
            
            # Copy buffer frames to recording
            self.recording_frames = list(self.frame_buffer)
            
            # Generate clip filename
            timestamp = int(time.time())
            datetime_str = time.strftime("%Y%m%d_%H%M%S", time.localtime())
            self.current_clip_path = os.path.join(
                self.output_dir, 
                f"fall_{datetime_str}_{timestamp}.mp4"
            )
            
            logger.info(f"Started recording clip: {self.current_clip_path}")
            return self.current_clip_path
            
    def _finalize_clip(self):
        """Save the recorded clip to disk."""
        if not self.recording_frames:
            self.is_recording = False
            return
            
        # Get frame dimensions
        height, width = self.recording_frames[0].shape[:2]
        
        # Create video writer
        fourcc = cv2.VideoWriter_fourcc(*'mp4v')
        writer = cv2.VideoWriter(
            self.current_clip_path, 
            fourcc, 
            self.fps, 
            (width, height)
        )
        
        # Write all frames
        for frame in self.recording_frames:
            writer.write(frame)
            
        writer.release()
        
        logger.info(f"Saved clip: {self.current_clip_path} ({len(self.recording_frames)} frames)")
        
        # Reset state
        self.is_recording = False
        self.recording_frames = []
        self.post_frames_count = 0
        
    def force_save(self):
        """Force save current recording if any."""
        with self.lock:
            if self.is_recording and self.recording_frames:
                self._finalize_clip()
                
    def get_buffer_status(self):
        """
        Get current buffer status.
        
        Returns:
            dict: Buffer statistics
        """
        return {
            'buffer_frames': len(self.frame_buffer),
            'is_recording': self.is_recording,
            'recording_frames': len(self.recording_frames) if self.is_recording else 0,
            'output_dir': self.output_dir
        }
