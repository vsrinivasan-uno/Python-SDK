"""Greeting Manager for Misty Aicco Assistant.

Manages personalized greetings with cooldown tracking to avoid repetitive greetings.
"""

import logging
import time
import random
from typing import Optional, Dict
from mistyPy.Robot import Robot


class GreetingManager:
    """Manages personalized greetings with cooldown tracking.
    
    This class handles:
    - Tracking last greeting time for each person
    - Enforcing cooldown periods between greetings
    - Generating personalized greeting messages
    - Speaking greetings via Misty's TTS
    - LED animations during greetings
    """
    
    def __init__(self, misty: Robot, greeting_templates: list, 
                 cooldown_seconds: int = 300,
                 greeting_led_color: tuple = (0, 255, 100),
                 idle_led_color: tuple = (0, 255, 0)):
        """Initialize the Greeting Manager.
        
        Args:
            misty: Misty robot instance
            greeting_templates: List of greeting message templates with {name} placeholder
            cooldown_seconds: Time in seconds before greeting same person again (default: 300 = 5 minutes)
            greeting_led_color: RGB tuple for LED during greeting (default: green-cyan)
            idle_led_color: RGB tuple for LED when returning to idle (default: green)
        """
        self.misty = misty
        self.greeting_templates = greeting_templates
        self.cooldown_seconds = cooldown_seconds
        self.greeting_led_color = greeting_led_color
        self.idle_led_color = idle_led_color
        self.logger = logging.getLogger("GreetingManager")
        
        # Dictionary to track last greeting time for each person
        # Format: {"PersonName": timestamp}
        self.last_greeting_times: Dict[str, float] = {}
        
        self.logger.info(f"Greeting Manager initialized with {cooldown_seconds}s cooldown")
        self.logger.info(f"Available greeting templates: {len(greeting_templates)}")
    
    def should_greet(self, person_name: str) -> bool:
        """Check if we should greet this person based on cooldown.
        
        Args:
            person_name: Name of the person to check
        
        Returns:
            True if person should be greeted, False if within cooldown period
        """
        current_time = time.time()
        
        # If we've never greeted this person, greet them
        if person_name not in self.last_greeting_times:
            return True
        
        # Check if enough time has passed since last greeting
        last_greeting_time = self.last_greeting_times[person_name]
        time_elapsed = current_time - last_greeting_time
        
        if time_elapsed >= self.cooldown_seconds:
            return True
        
        # Still within cooldown period
        time_remaining = self.cooldown_seconds - time_elapsed
        self.logger.debug(f"Cooldown active for '{person_name}': {time_remaining:.1f}s remaining")
        return False
    
    def get_greeting_message(self, person_name: str) -> str:
        """Generate a personalized greeting message.
        
        Args:
            person_name: Name of the person to greet
        
        Returns:
            Personalized greeting message
        """
        # Select a random greeting template
        template = random.choice(self.greeting_templates)
        
        # Format with person's name
        greeting = template.format(name=person_name)
        
        return greeting
    
    def greet_person(self, person_name: str, force: bool = False) -> bool:
        """Greet a person with personalized message and LED animation.
        
        Args:
            person_name: Name of the person to greet
            force: If True, bypass cooldown check (default: False)
        
        Returns:
            True if greeting was delivered, False if skipped due to cooldown
        """
        try:
            # Check cooldown (unless forced)
            if not force and not self.should_greet(person_name):
                time_remaining = self.cooldown_seconds - (time.time() - self.last_greeting_times[person_name])
                self.logger.info(f"⏳ Skipping greeting for '{person_name}' (cooldown: {time_remaining:.0f}s remaining)")
                return False
            
            # Generate greeting message
            greeting_message = self.get_greeting_message(person_name)
            self.logger.info(f"👋 Greeting '{person_name}': {greeting_message}")
            
            # Set LED to greeting color (green-cyan pulse effect)
            try:
                r, g, b = self.greeting_led_color
                self.misty.change_led(red=r, green=g, blue=b)
                self.logger.debug(f"💡 LED set to greeting color: RGB({r}, {g}, {b})")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to change LED for greeting: {e}")
            
            # Speak the greeting
            try:
                response = self.misty.speak(text=greeting_message, flush=True)
                if response.status_code == 200:
                    self.logger.info("🔊 Greeting spoken successfully")
                else:
                    self.logger.warning(f"⚠️ Speak command returned status {response.status_code}")
            except Exception as e:
                self.logger.error(f"❌ Failed to speak greeting: {e}")
                return False
            
            # Update last greeting time
            self.last_greeting_times[person_name] = time.time()
            
            # Wait a moment for speech to complete, then return LED to idle
            # Note: We could use TextToSpeechComplete event for more precise timing
            time.sleep(2)  # Brief delay before returning to idle
            
            try:
                r, g, b = self.idle_led_color
                self.misty.change_led(red=r, green=g, blue=b)
                self.logger.debug(f"💡 LED returned to idle color: RGB({r}, {g}, {b})")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to reset LED after greeting: {e}")
            
            self.logger.info(f"✅ Greeting delivered to '{person_name}'")
            return True
            
        except Exception as e:
            self.logger.error(f"❌ Error greeting person '{person_name}': {e}", exc_info=True)
            return False
    
    def reset_cooldown(self, person_name: Optional[str] = None):
        """Reset cooldown for a specific person or all people.
        
        Args:
            person_name: Name of person to reset cooldown for, or None to reset all
        """
        if person_name:
            if person_name in self.last_greeting_times:
                del self.last_greeting_times[person_name]
                self.logger.info(f"Cooldown reset for '{person_name}'")
        else:
            self.last_greeting_times.clear()
            self.logger.info("All cooldowns reset")
    
    def get_greeting_status(self, person_name: str) -> dict:
        """Get greeting status information for a person.
        
        Args:
            person_name: Name of person to check
        
        Returns:
            Dictionary with greeting status info
        """
        current_time = time.time()
        
        if person_name not in self.last_greeting_times:
            return {
                "person": person_name,
                "last_greeted": None,
                "can_greet": True,
                "cooldown_remaining": 0
            }
        
        last_greeting_time = self.last_greeting_times[person_name]
        time_elapsed = current_time - last_greeting_time
        can_greet = time_elapsed >= self.cooldown_seconds
        cooldown_remaining = max(0, self.cooldown_seconds - time_elapsed)
        
        return {
            "person": person_name,
            "last_greeted": last_greeting_time,
            "time_since_greeting": time_elapsed,
            "can_greet": can_greet,
            "cooldown_remaining": cooldown_remaining
        }
    
    def get_all_greeting_history(self) -> dict:
        """Get greeting history for all people.
        
        Returns:
            Dictionary mapping person names to their greeting status
        """
        return {
            name: self.get_greeting_status(name) 
            for name in self.last_greeting_times.keys()
        }

