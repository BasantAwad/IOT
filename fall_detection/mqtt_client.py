"""
MQTT Client Module for Fall Detection Events
============================================
Publishes fall detection events to MQTT broker.
"""

import paho.mqtt.client as mqtt
import json
import time
import logging
from config import MQTT_BROKER, MQTT_PORT, MQTT_TOPIC, MQTT_CLIENT_ID


logger = logging.getLogger(__name__)


class MQTTPublisher:
    """MQTT client for publishing fall detection events."""
    
    def __init__(self, broker=None, port=None, topic=None, client_id=None):
        """
        Initialize MQTT publisher.
        
        Args:
            broker: MQTT broker address
            port: MQTT broker port
            topic: Topic to publish fall events to
            client_id: Client identifier
        """
        self.broker = broker or MQTT_BROKER
        self.port = port or MQTT_PORT
        self.topic = topic or MQTT_TOPIC
        self.client_id = client_id or MQTT_CLIENT_ID
        
        self.client = mqtt.Client(client_id=self.client_id)
        self.connected = False
        
        # Set up callbacks
        self.client.on_connect = self._on_connect
        self.client.on_disconnect = self._on_disconnect
        self.client.on_publish = self._on_publish
        
    def _on_connect(self, client, userdata, flags, rc):
        """Callback when connected to broker."""
        if rc == 0:
            self.connected = True
            logger.info(f"Connected to MQTT broker at {self.broker}:{self.port}")
        else:
            logger.error(f"Failed to connect to MQTT broker, return code: {rc}")
            
    def _on_disconnect(self, client, userdata, rc):
        """Callback when disconnected from broker."""
        self.connected = False
        if rc != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker")
            
    def _on_publish(self, client, userdata, mid):
        """Callback when message is published."""
        logger.debug(f"Message {mid} published successfully")
        
    def connect(self):
        """
        Connect to MQTT broker.
        
        Returns:
            bool: True if connection successful
        """
        try:
            self.client.connect(self.broker, self.port, keepalive=60)
            self.client.loop_start()
            
            # Wait for connection
            timeout = 5
            start = time.time()
            while not self.connected and (time.time() - start) < timeout:
                time.sleep(0.1)
                
            return self.connected
            
        except Exception as e:
            logger.error(f"Failed to connect to MQTT broker: {e}")
            return False
            
    def disconnect(self):
        """Disconnect from MQTT broker."""
        self.client.loop_stop()
        self.client.disconnect()
        self.connected = False
        logger.info("Disconnected from MQTT broker")
        
    def publish_fall_event(self, confidence, clip_path=None, timestamp=None):
        """
        Publish a fall detection event.
        
        Args:
            confidence: Detection confidence score (0-1)
            clip_path: Path to saved video clip
            timestamp: Event timestamp (defaults to current time)
            
        Returns:
            bool: True if publish successful
        """
        if not self.connected:
            logger.warning("Not connected to MQTT broker, attempting to reconnect...")
            if not self.connect():
                return False
        
        event = {
            "event": "fall_detected",
            "confidence": round(confidence, 3),
            "timestamp": timestamp or int(time.time()),
            "timestamp_iso": time.strftime("%Y-%m-%dT%H:%M:%S", time.localtime()),
            "device_id": self.client_id
        }
        
        if clip_path:
            event["clip_path"] = clip_path
            
        message = json.dumps(event)
        
        try:
            result = self.client.publish(self.topic, message, qos=1)
            if result.rc == mqtt.MQTT_ERR_SUCCESS:
                logger.info(f"Published fall event: confidence={confidence:.1%}")
                return True
            else:
                logger.error(f"Failed to publish message, rc: {result.rc}")
                return False
                
        except Exception as e:
            logger.error(f"Error publishing fall event: {e}")
            return False
            
    def publish_status(self, status="online"):
        """
        Publish device status message.
        
        Args:
            status: Status string (online/offline/error)
        """
        if not self.connected:
            return False
            
        status_topic = f"{self.topic}/status"
        message = json.dumps({
            "status": status,
            "device_id": self.client_id,
            "timestamp": int(time.time())
        })
        
        try:
            self.client.publish(status_topic, message, qos=1, retain=True)
            return True
        except Exception as e:
            logger.error(f"Error publishing status: {e}")
            return False


# Singleton instance for easy access
_publisher = None


def get_publisher():
    """Get the singleton MQTT publisher instance."""
    global _publisher
    if _publisher is None:
        _publisher = MQTTPublisher()
    return _publisher
