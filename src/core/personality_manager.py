#!/usr/bin/env python3
"""Personality Manager for Misty Robot

Handles animations, expressions, and dynamic behaviors to make Misty more engaging.

Features:
- Conversation animations (head movements, arm gestures during speech)
- Eye expressions for different emotions
- Screensaver mode (dancing/animations when idle)
- Battery saving mode (stops services when idle)

Author: Misty Robotics
Date: October 2, 2025
"""

import logging
import threading
import time
import random
from typing import Optional
from mistyPy.Robot import Robot


class PersonalityManager:
    """Manages Misty's personality animations and behaviors."""
    
    def __init__(
        self,
        misty: Robot,
        idle_timeout_seconds: float = 120.0,  # 2 minutes default
        screensaver_enabled: bool = True
    ):
        """Initialize the Personality Manager.
        
        Args:
            misty: Robot instance
            idle_timeout_seconds: Seconds of inactivity before screensaver
            screensaver_enabled: Whether to enable screensaver mode
        """
        self.misty = misty
        self.idle_timeout_seconds = idle_timeout_seconds
        self.screensaver_enabled = screensaver_enabled
        
        self.logger = logging.getLogger("PersonalityManager")
        
        # State tracking
        self.last_interaction_time = time.time()
        self.in_screensaver = False
        self.screensaver_thread: Optional[threading.Thread] = None
        self.idle_monitor_thread: Optional[threading.Thread] = None
        self.running = False
        
        # Callbacks for screensaver events
        self.on_enter_screensaver: Optional[callable] = None
        self.on_exit_screensaver: Optional[callable] = None
        
        # Available eye expressions (Misty's default images)
        self.eye_expressions = {
            "happy": "e_Joy.jpg",
            "love": "e_Love.jpg",
            "amazement": "e_Amazement.jpg",
            "default": "e_DefaultContent.jpg",
            "joy": "e_Joy.jpg",
            "sadness": "e_Sadness.jpg",
            "disgust": "e_Disgust.jpg",
            "sleepy": "e_Sleepy.jpg",
            "angry": "e_Anger.jpg",
            "fear": "e_Fear.jpg",
            "contempt": "e_Contempt.jpg",
            "surprise": "e_Surprise.jpg",
            "app_default": "e_AppDefault.jpg",
            "eco": "e_Eco.jpg",
            "rage": "e_Rage.jpg",
            "sleeping": "e_Sleeping.jpg",
            "system_camera": "e_SystemCamera.jpg",
            "terror": "e_Terror.jpg"
        }
        
        self.logger.info(f"Personality Manager initialized (idle timeout: {idle_timeout_seconds}s)")
    
    def start(self):
        """Start the personality manager and idle monitoring."""
        if self.running:
            self.logger.warning("Personality Manager already running")
            return
        
        self.running = True
        self.last_interaction_time = time.time()
        
        # Start idle monitoring thread
        if self.screensaver_enabled:
            self.idle_monitor_thread = threading.Thread(target=self._idle_monitor_loop, daemon=True)
            self.idle_monitor_thread.start()
            self.logger.info("✅ Personality Manager started with idle monitoring")
        else:
            self.logger.info("✅ Personality Manager started (screensaver disabled)")
    
    def stop(self):
        """Stop the personality manager."""
        self.running = False
        
        if self.in_screensaver:
            self._exit_screensaver()
        
        if self.idle_monitor_thread and self.idle_monitor_thread.is_alive():
            self.idle_monitor_thread.join(timeout=1)
        
        self.logger.info("Personality Manager stopped")
    
    def record_interaction(self):
        """Record that an interaction occurred (resets idle timer)."""
        self.last_interaction_time = time.time()
        
        # If in screensaver, exit it
        if self.in_screensaver:
            self._exit_screensaver()
    
    def show_expression(self, expression: str = "default"):
        """Show an eye expression.
        
        Args:
            expression: Expression name (happy, love, amazement, etc.)
        """
        image_name = self.eye_expressions.get(expression, self.eye_expressions["default"])
        
        try:
            self.misty.display_image(fileName=image_name)
            self.logger.debug(f"👁️  Showing expression: {expression} ({image_name})")
        except Exception as e:
            self.logger.warning(f"Failed to show expression: {e}")
    
    def listening_animation(self):
        """Animate Misty while listening (subtle head tilt)."""
        try:
            # Slight head tilt to show active listening
            self.misty.move_head(pitch=-5, roll=0, yaw=0, velocity=50, duration=0.5)
            self.show_expression("default")
        except Exception as e:
            self.logger.warning(f"Failed to play listening animation: {e}")
    
    def thinking_animation(self):
        """Animate Misty while processing (head movement, eyes)."""
        try:
            # Look up slightly (thinking pose)
            self.misty.move_head(pitch=-10, roll=0, yaw=10, velocity=50, duration=0.8)
            self.show_expression("default")
            time.sleep(0.5)
            # Look the other way
            self.misty.move_head(pitch=-10, roll=0, yaw=-10, velocity=50, duration=0.8)
        except Exception as e:
            self.logger.warning(f"Failed to play thinking animation: {e}")
    
    def speaking_animation(self):
        """Animate Misty while speaking (head bobs, arm gestures)."""
        try:
            # Random head position for natural movement
            pitch = random.randint(-5, 5)
            yaw = random.randint(-15, 15)
            
            self.misty.move_head(pitch=pitch, roll=0, yaw=yaw, velocity=40, duration=0.6)
            
            # Random arm gesture (one arm up slightly)
            if random.choice([True, False]):
                self.misty.move_arm(arm="left", position=random.randint(-20, 20), velocity=50)
            else:
                self.misty.move_arm(arm="right", position=random.randint(-20, 20), velocity=50)
            
            # Happy/engaged expression
            self.show_expression("joy")
            
        except Exception as e:
            self.logger.warning(f"Failed to play speaking animation: {e}")
    
    def greeting_animation(self):
        """Animate Misty when greeting someone (wave, happy eyes)."""
        try:
            # Happy eyes
            self.show_expression("love")
            
            # Wave with right arm
            self.misty.move_head(pitch=0, roll=0, yaw=0, velocity=50)
            self.misty.move_arm(arm="right", position=70, velocity=80, duration=0.5)
            time.sleep(0.6)
            self.misty.move_arm(arm="right", position=-70, velocity=80, duration=0.5)
            time.sleep(0.6)
            self.misty.move_arm(arm="right", position=0, velocity=80, duration=0.5)
            
        except Exception as e:
            self.logger.warning(f"Failed to play greeting animation: {e}")
    
    def reset_to_neutral(self):
        """Reset Misty to neutral pose."""
        try:
            self.misty.move_head(pitch=0, roll=0, yaw=0, velocity=50)
            self.misty.move_arms(
                leftArmPosition=0, 
                rightArmPosition=0, 
                leftArmVelocity=50, 
                rightArmVelocity=50
            )
            self.show_expression("default")
            self.logger.debug("Reset to neutral pose")
        except Exception as e:
            self.logger.warning(f"Failed to reset to neutral: {e}")
    
    def _idle_monitor_loop(self):
        """Background thread to monitor for idle state."""
        while self.running:
            try:
                time_since_interaction = time.time() - self.last_interaction_time
                
                # Check if we should enter screensaver
                if not self.in_screensaver and time_since_interaction >= self.idle_timeout_seconds:
                    self.logger.info(f"⏰ Idle for {time_since_interaction:.0f}s - entering screensaver mode")
                    self._enter_screensaver()
                
                # Check every 5 seconds
                time.sleep(5)
                
            except Exception as e:
                self.logger.error(f"Error in idle monitor: {e}")
                time.sleep(5)
    
    def _enter_screensaver(self):
        """Enter screensaver mode (dancing/animations)."""
        if self.in_screensaver:
            return
        
        self.in_screensaver = True
        self.logger.info("🎬 Entering screensaver mode (dancing)")
        
        # Call battery saving callback if set
        if self.on_enter_screensaver:
            try:
                self.on_enter_screensaver()
            except Exception as e:
                self.logger.error(f"Error in on_enter_screensaver callback: {e}")
        
        # Start screensaver thread
        self.screensaver_thread = threading.Thread(target=self._screensaver_loop, daemon=True)
        self.screensaver_thread.start()
    
    def _exit_screensaver(self):
        """Exit screensaver mode."""
        if not self.in_screensaver:
            return
        
        self.in_screensaver = False
        self.logger.info("🎬 Exiting screensaver mode")
        
        # Wait for screensaver thread to finish
        if self.screensaver_thread and self.screensaver_thread.is_alive():
            self.screensaver_thread.join(timeout=2)
        
        # Call battery saving callback if set
        if self.on_exit_screensaver:
            try:
                self.on_exit_screensaver()
            except Exception as e:
                self.logger.error(f"Error in on_exit_screensaver callback: {e}")
        
        # Reset to neutral
        self.reset_to_neutral()
    
    def _screensaver_loop(self):
        """Screensaver animation loop (dancing)."""
        dance_moves = [
            self._dance_move_1,
            self._dance_move_2,
            self._dance_move_3,
            self._dance_move_4
        ]
        
        while self.in_screensaver and self.running:
            try:
                # Pick random dance move
                move = random.choice(dance_moves)
                move()
                
                # Wait between moves
                time.sleep(2)
                
            except Exception as e:
                self.logger.error(f"Error in screensaver: {e}")
                time.sleep(2)
    
    def _dance_move_1(self):
        """Dance move 1: Head shake with arm waves."""
        try:
            # Happy expression
            self.show_expression("joy")
            
            # Head shake left-right
            self.misty.move_head(pitch=0, roll=0, yaw=-30, velocity=60, duration=0.5)
            self.misty.move_arms(leftArmPosition=60, rightArmPosition=-60, duration=0.5)
            time.sleep(0.6)
            
            self.misty.move_head(pitch=0, roll=0, yaw=30, velocity=60, duration=0.5)
            self.misty.move_arms(leftArmPosition=-60, rightArmPosition=60, duration=0.5)
            time.sleep(0.6)
            
            # Back to center
            self.misty.move_head(pitch=0, roll=0, yaw=0, velocity=60)
            self.misty.move_arms(leftArmPosition=0, rightArmPosition=0, duration=0.5)
            
        except Exception as e:
            self.logger.debug(f"Dance move 1 error: {e}")
    
    def _dance_move_2(self):
        """Dance move 2: Spin in place."""
        try:
            # Excited expression
            self.show_expression("amazement")
            
            # Spin 360 degrees
            self.misty.drive_time(linearVelocity=0, angularVelocity=30, timeMs=2000)
            time.sleep(2.5)
            
            # Stop
            self.misty.halt()
            
        except Exception as e:
            self.logger.debug(f"Dance move 2 error: {e}")
    
    def _dance_move_3(self):
        """Dance move 3: Arm wave sequence."""
        try:
            # Joy expression
            self.show_expression("love")
            
            # Wave both arms up and down
            for _ in range(3):
                self.misty.move_arms(leftArmPosition=70, rightArmPosition=70, duration=0.4)
                time.sleep(0.5)
                self.misty.move_arms(leftArmPosition=-70, rightArmPosition=-70, duration=0.4)
                time.sleep(0.5)
            
            # Return to neutral
            self.misty.move_arms(leftArmPosition=0, rightArmPosition=0, duration=0.4)
            
        except Exception as e:
            self.logger.debug(f"Dance move 3 error: {e}")
    
    def _dance_move_4(self):
        """Dance move 4: Look around curiously."""
        try:
            # Curious expression
            self.show_expression("surprise")
            
            # Look around
            directions = [
                (-15, -30),  # Look down-left
                (15, 30),    # Look up-right
                (-15, 30),   # Look down-right
                (15, -30)    # Look up-left
            ]
            
            for pitch, yaw in directions:
                self.misty.move_head(pitch=pitch, roll=0, yaw=yaw, velocity=50, duration=0.6)
                time.sleep(0.7)
            
            # Back to center
            self.misty.move_head(pitch=0, roll=0, yaw=0, velocity=50)
            
        except Exception as e:
            self.logger.debug(f"Dance move 4 error: {e}")

