"""Face Recognition Manager for Misty Aicco Assistant.

Handles continuous face recognition monitoring and detection events.
"""

import logging
import time
from typing import Optional, Callable
from mistyPy.Robot import Robot
from mistyPy.Events import Events


class FaceRecognitionManager:
    """Manages continuous face recognition for Misty robot.
    
    This class handles:
    - Starting and stopping face recognition
    - Receiving face recognition events
    - Processing detected faces
    - Notifying other components when faces are recognized
    """
    
    def __init__(self, misty: Robot, on_face_recognized: Optional[Callable] = None, 
                 camera_active_color: tuple = (0, 100, 255)):
        """Initialize the Face Recognition Manager.
        
        Args:
            misty: Misty robot instance
            on_face_recognized: Optional callback function called when a face is recognized.
                               Function signature: on_face_recognized(face_data: dict)
            camera_active_color: RGB tuple for LED color when camera is active (default: blue)
        """
        self.misty = misty
        self.on_face_recognized = on_face_recognized
        self.logger = logging.getLogger("FaceRecognitionManager")
        self.running = False
        self.event_name = "FaceRecognitionEvent"
        self.camera_active_color = camera_active_color  # RGB color when camera is on
        
        self.logger.info("Face Recognition Manager initialized")
    
    def start(self):
        """Start continuous face recognition monitoring.
        
        This method:
        1. Verifies camera service is enabled
        2. Tests camera functionality
        3. Starts Misty's face recognition service
        4. Registers an event listener for face recognition events
        5. Sets up continuous monitoring (keep_alive=True)
        """
        if self.running:
            self.logger.warning("Face recognition is already running")
            return
        
        try:
            self.logger.info("Starting face recognition...")
            
            # Step 1: Check if camera service is enabled
            self.logger.info("📹 Checking camera service status...")
            try:
                camera_status = self.misty.camera_service_enabled()
                if camera_status.status_code == 200:
                    status_data = camera_status.json()
                    is_enabled = status_data.get("result", False)
                    if is_enabled:
                        self.logger.info("✅ Camera service is enabled")
                    else:
                        self.logger.error("❌ Camera service is DISABLED")
                        self.logger.info("🔧 Attempting to enable camera service...")
                        enable_response = self.misty.enable_camera_service()
                        if enable_response.status_code == 200:
                            self.logger.info("✅ Camera service enabled successfully")
                            # Wait a moment for service to initialize
                            time.sleep(2)
                        else:
                            self.logger.error(f"❌ Failed to enable camera service: {enable_response.status_code}")
                            return
                else:
                    self.logger.warning(f"⚠️ Could not verify camera status: {camera_status.status_code}")
            except Exception as e:
                self.logger.warning(f"⚠️ Error checking camera status: {e}")
            
            # Step 2: Test camera by taking a picture
            self.logger.info("📸 Testing camera functionality...")
            try:
                test_pic = self.misty.take_picture(
                    fileName="camera_test",
                    width=320,
                    height=240,
                    displayOnScreen=False,
                    overwriteExisting=True
                )
                if test_pic.status_code == 200:
                    self.logger.info("✅ Camera is capturing images successfully")
                else:
                    self.logger.warning(f"⚠️ Camera test photo failed: {test_pic.status_code}")
                    self.logger.warning("   Continuing anyway, but camera may not be working...")
            except Exception as e:
                self.logger.warning(f"⚠️ Camera test failed: {e}")
                self.logger.warning("   Continuing anyway, but camera may not be working...")
            
            # Step 3: Start Misty's face recognition
            self.logger.info("🚀 Starting face recognition service...")
            response = self.misty.start_face_recognition()
            if response.status_code == 200:
                self.logger.info("✅ Face recognition service started")
            else:
                self.logger.error(f"❌ Failed to start face recognition: {response.status_code}")
                self.logger.error(f"   Response: {response.text}")
                return
            
            # Step 4: Register event listener for face recognition with keep_alive=True for continuous monitoring
            self.logger.info("📡 Registering face recognition event listener...")
            try:
                # Use lambda wrapper to avoid "self" argument issue with SDK's callback checker
                # The SDK checks for exactly 1 argument, but methods have 2 (self + event_data)
                self.misty.register_event(
                    event_type=Events.FaceRecognition,
                    event_name=self.event_name,
                    keep_alive=True,  # Keep listening continuously
                    callback_function=lambda data: self._on_face_detected(data)
                )
                # Verify registration actually succeeded
                registered_events = self.misty.get_registered_events()
                if self.event_name in registered_events:
                    self.logger.info("✅ Event listener registered successfully")
                else:
                    self.logger.error("❌ Event registration failed - event not in active registrations")
                    self.misty.stop_face_recognition()
                    return
            except Exception as e:
                self.logger.error(f"❌ Failed to register event listener: {e}")
                # Try to stop face recognition since event listener failed
                self.misty.stop_face_recognition()
                return
            
            self.running = True
            
            # Set LED to indicate camera is active
            try:
                r, g, b = self.camera_active_color
                self.misty.change_led(red=r, green=g, blue=b)
                self.logger.info(f"💡 LED set to RGB({r}, {g}, {b}) - Camera Active Indicator")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to change LED color: {e}")
            
            self.logger.info("✅ Face recognition monitoring started (continuous mode)")
            self.logger.info("👀 Camera is ON and monitoring for faces...")
            
        except Exception as e:
            self.logger.error(f"❌ Error starting face recognition: {e}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop face recognition monitoring.
        
        This method:
        1. Unregisters the face recognition event
        2. Stops Misty's face recognition service
        """
        if not self.running:
            self.logger.warning("Face recognition is not running")
            return
        
        try:
            self.logger.info("Stopping face recognition...")
            
            # Unregister the event
            self.misty.unregister_event(self.event_name)
            self.logger.info("Event listener unregistered")
            
            # Stop face recognition service
            response = self.misty.stop_face_recognition()
            if response.status_code == 200:
                self.logger.info("✅ Face recognition service stopped")
            else:
                self.logger.warning(f"Failed to stop face recognition: {response.status_code}")
            
            # Reset LED to white (default/off state)
            try:
                self.misty.change_led(red=255, green=255, blue=255)
                self.logger.info("💡 LED reset to white - Camera Inactive")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to reset LED color: {e}")
            
            self.running = False
            self.logger.info("Face recognition monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping face recognition: {e}", exc_info=True)
    
    def _on_face_detected(self, event_data: dict):
        """Internal callback for face recognition events.
        
        This method processes the raw event data and extracts face information.
        
        Args:
            event_data: Event data from Misty's face recognition system
        """
        try:
            # Log raw event for debugging
            self.logger.debug(f"Face recognition event received: {event_data}")
            
            # Extract face information from event data
            # Event structure: {"message": {"label": "PersonName", "confidence": 0.95, ...}}
            if "message" not in event_data:
                self.logger.warning("Face recognition event missing 'message' field")
                return
            
            message = event_data["message"]
            
            # Extract face label (name)
            face_label = message.get("label", "unknown")
            confidence = message.get("distance", 0.0)  # Lower distance = higher confidence
            
            # Filter out unknown faces and low confidence detections
            if face_label == "unknown person" or not face_label:
                self.logger.debug(f"Unknown face detected (confidence: {confidence})")
                return
            
            # Log recognized face
            self.logger.info(f"👤 Face recognized: '{face_label}' (confidence: {confidence:.2f})")
            
            # Prepare face data for callback
            face_data = {
                "name": face_label,
                "confidence": confidence,
                "timestamp": time.time(),
                "raw_event": message
            }
            
            # Call external callback if provided
            if self.on_face_recognized:
                try:
                    self.on_face_recognized(face_data)
                except Exception as e:
                    self.logger.error(f"Error in face recognition callback: {e}", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error processing face recognition event: {e}", exc_info=True)
    
    def get_known_faces(self) -> list:
        """Get list of known faces from Misty's database.
        
        Returns:
            List of known face names, or empty list if error
        """
        try:
            response = self.misty.get_known_faces()
            if response.status_code == 200:
                data = response.json()
                if "result" in data:
                    faces = data["result"]
                    self.logger.info(f"Known faces: {faces}")
                    return faces
                else:
                    self.logger.warning("No 'result' in get_known_faces response")
                    return []
            else:
                self.logger.error(f"Failed to get known faces: {response.status_code}")
                return []
        except Exception as e:
            self.logger.error(f"Error getting known faces: {e}", exc_info=True)
            return []
    
    def train_face(self, face_id: str) -> bool:
        """Train Misty to recognize a new face.
        
        Args:
            face_id: Unique identifier for the face (person's name)
        
        Returns:
            True if training started successfully, False otherwise
        """
        try:
            self.logger.info(f"Starting face training for '{face_id}'...")
            self.logger.info("⏱️  Training will take approximately 15-20 seconds")
            self.logger.info("💡 Please look at Misty's camera and move your head slightly")
            
            response = self.misty.start_face_training(faceId=face_id)
            if response.status_code == 200:
                self.logger.info(f"✅ Face training started for '{face_id}'")
                self.logger.info("⏳ Wait for training to complete before using face recognition")
                return True
            else:
                self.logger.error(f"Failed to start face training: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Error starting face training: {e}", exc_info=True)
            return False
    
    def forget_face(self, face_id: str) -> bool:
        """Remove a face from Misty's recognition database.
        
        Args:
            face_id: Face identifier to forget
        
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"Forgetting face '{face_id}'...")
            response = self.misty.forget_faces(faceId=face_id)
            if response.status_code == 200:
                self.logger.info(f"✅ Face '{face_id}' forgotten")
                return True
            else:
                self.logger.error(f"Failed to forget face: {response.status_code}")
                return False
        except Exception as e:
            self.logger.error(f"Error forgetting face: {e}", exc_info=True)
            return False

