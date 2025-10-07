"""Greeting Manager for Misty Aicco Assistant.

Manages personalized greetings with cooldown tracking and local audio cache.
"""

import logging
import time
import random
import os
import base64
from typing import Optional, Dict
from mistyPy.Robot import Robot


class GreetingManager:
    """Manages personalized greetings with cooldown tracking.
    
    This class handles:
    - Tracking last greeting time for each person
    - Enforcing cooldown periods between greetings
    - Generating personalized greeting messages
    - Playing pre-generated audio greetings from local storage
    - Speaking greetings via Misty's TTS or OpenAI Realtime API (fallback)
    - LED animations during greetings
    """
    
    def __init__(self, misty: Robot, greeting_templates: list, 
                 cooldown_seconds: int = 300,
                 greeting_led_color: tuple = (0, 255, 100),
                 idle_led_color: tuple = (0, 255, 0),
                 vip_persons: dict = None,
                 realtime_handler = None,
                 audio_queue_manager = None,
                 use_realtime_api: bool = False,
                 cache_directory: str = "greeting_cache"):
        """Initialize the Greeting Manager.
        
        Args:
            misty: Misty robot instance
            greeting_templates: List of greeting message templates with {name} placeholder
            cooldown_seconds: Time in seconds before greeting same person again (default: 300 = 5 minutes)
            greeting_led_color: RGB tuple for LED during greeting (default: green-cyan)
            idle_led_color: RGB tuple for LED when returning to idle (default: green)
            vip_persons: Dictionary mapping VIP person names to custom greeting messages
            realtime_handler: Optional RealtimeHandler instance for OpenAI Realtime API
            audio_queue_manager: Optional AudioQueueManager for chunked audio playback
            use_realtime_api: Whether to use OpenAI Realtime API (True) or Misty TTS (False)
            cache_directory: Local directory for cached greeting audio files (default: "greeting_cache")
        """
        self.misty = misty
        self.greeting_templates = greeting_templates
        self.cooldown_seconds = cooldown_seconds
        self.greeting_led_color = greeting_led_color
        self.idle_led_color = idle_led_color
        self.vip_persons = vip_persons or {}
        self.realtime_handler = realtime_handler
        self.audio_queue_manager = audio_queue_manager
        self.use_realtime_api = use_realtime_api
        self.logger = logging.getLogger("GreetingManager")
        
        # Dictionary to track last greeting time for each person
        # Format: {"PersonName": timestamp}
        self.last_greeting_times: Dict[str, float] = {}
        
        # Local cache for pre-generated greeting audio files
        # Format: {"PersonName": "/path/to/greeting_PersonName.wav"}
        self.greeting_audio_cache: Dict[str, str] = {}
        self.cache_directory = cache_directory
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_directory, exist_ok=True)
        
        # Load local cached greetings
        self._load_local_greeting_cache()
        
        self.logger.info(f"Greeting Manager initialized with {cooldown_seconds}s cooldown")
        self.logger.info(f"Available greeting templates: {len(greeting_templates)}")
        self.logger.info(f"VIP persons configured: {len(self.vip_persons)}")
        self.logger.info(f"Cached greetings loaded: {len(self.greeting_audio_cache)}")
        self.logger.info(f"Cache directory: {self.cache_directory}")
        self.logger.info(f"Voice mode: {'OpenAI Realtime API' if use_realtime_api else 'Misty TTS'}")
    
    def _load_local_greeting_cache(self):
        """Load pre-generated greeting audio files from local storage.
        
        Checks for files matching pattern: greeting_{person_name}.wav
        """
        try:
            if not os.path.exists(self.cache_directory):
                self.logger.info(f"Cache directory doesn't exist yet: {self.cache_directory}")
                return
            
            # List all WAV files in cache directory
            cache_files = [f for f in os.listdir(self.cache_directory) if f.endswith('.wav')]
            
            for filename in cache_files:
                # Check if filename matches our pattern: greeting_{PersonName}.wav
                if filename.startswith("greeting_") and filename.endswith(".wav"):
                    # Extract person name from filename
                    person_name = filename[9:-4]  # Remove "greeting_" and ".wav"
                    # Replace underscores with spaces for person names
                    person_name = person_name.replace("_", " ")
                    
                    full_path = os.path.join(self.cache_directory, filename)
                    self.greeting_audio_cache[person_name] = full_path
                    self.logger.info(f"  📦 Loaded cached greeting for: {person_name}")
            
            if self.greeting_audio_cache:
                self.logger.info(f"✅ Loaded {len(self.greeting_audio_cache)} cached greetings from local storage")
            else:
                self.logger.info("ℹ️ No cached greetings found in local storage")
                self.logger.info(f"   Run 'python generate_vip_greetings.py' to generate them")
                
        except Exception as e:
            self.logger.error(f"Error loading local greeting cache: {e}", exc_info=True)
    
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
        # Check if person is a VIP with custom greeting
        if person_name in self.vip_persons:
            self.logger.info(f"🌟 VIP recognized: {person_name}")
            return self.vip_persons[person_name]
        
        # Select a random greeting template for regular persons
        template = random.choice(self.greeting_templates)
        
        # Format with person's name
        greeting = template.format(name=person_name)
        
        return greeting
    
    def greet_person(self, person_name: str, force: bool = False, recognized_at: Optional[float] = None) -> bool:
        """Greet a person with personalized message and LED animation.
        
        Args:
            person_name: Name of the person to greet
            force: If True, bypass cooldown check (default: False)
            recognized_at: Timestamp when face was recognized (for latency tracking)
        
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
            self.logger.info(f"👋 Greeting '{person_name}': {greeting_message[:100]}...")
            
            # Set LED to greeting color (green-cyan pulse effect)
            try:
                r, g, b = self.greeting_led_color
                self.misty.change_led(red=r, green=g, blue=b)
                self.logger.debug(f"💡 LED set to greeting color: RGB({r}, {g}, {b})")
            except Exception as e:
                self.logger.warning(f"⚠️ Failed to change LED for greeting: {e}")
            
            # Speak the greeting - prioritize local cached audio for instant playback
            try:
                # Log latency from face recognized to speak command, if provided
                if recognized_at is not None:
                    now = time.time()
                    latency = now - recognized_at
                    self.logger.info(f"⏱️ Face→speak latency: {latency:.3f}s")
                
                # Priority 1: Check for locally cached audio file
                if person_name in self.greeting_audio_cache:
                    self.logger.info(f"🎵 Using LOCAL cached greeting audio for {person_name}")
                    local_file_path = self.greeting_audio_cache[person_name]
                    success = self._play_local_cached_greeting(local_file_path)
                    if not success:
                        self.logger.warning("⚠️ Local cached audio playback failed, falling back...")
                        # Fall through to other methods
                    else:
                        # Success! Update tracking and return
                        self.last_greeting_times[person_name] = time.time()
                        time.sleep(2)  # Brief delay
                        try:
                            r, g, b = self.idle_led_color
                            self.misty.change_led(red=r, green=g, blue=b)
                        except Exception as e:
                            self.logger.warning(f"⚠️ Failed to reset LED: {e}")
                        self.logger.info(f"✅ Local cached greeting delivered to '{person_name}'")
                        return True
                
                # Priority 2: Fallback to Misty's built-in TTS (Realtime API not suitable for greetings)
                self.logger.info("🔊 Using Misty's built-in TTS for greeting")
                response = self.misty.speak(text=greeting_message, voice="en-us-x-tpd-local", flush=True)
                if response.status_code == 200:
                    self.logger.info("✅ Greeting spoken successfully (Misty TTS)")
                else:
                    self.logger.error(f"❌ Misty TTS failed: {response.status_code}")
                    return False
                    
            except Exception as e:
                self.logger.error(f"❌ Failed to speak greeting: {e}", exc_info=True)
                return False
            
            # Update last greeting time
            self.last_greeting_times[person_name] = time.time()
            
            # Wait a moment for speech to complete, then return LED to idle
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
    
    def _play_local_cached_greeting(self, local_file_path: str) -> bool:
        """Play a pre-generated cached greeting from local storage.
        
        Reads the local WAV file and streams it to Misty for playback.
        
        Args:
            local_file_path: Path to the local WAV file
            
        Returns:
            True if successful, False otherwise
        """
        try:
            self.logger.info(f"📂 Reading local file: {local_file_path}")
            
            # Check if file exists
            if not os.path.exists(local_file_path):
                self.logger.error(f"❌ Local file not found: {local_file_path}")
                return False
            
            # Read the WAV file
            with open(local_file_path, 'rb') as f:
                wav_bytes = f.read()
            
            file_size_kb = len(wav_bytes) / 1024
            self.logger.info(f"📦 Loaded {file_size_kb:.2f} KB from local storage")
            
            # Generate unique filename for Misty
            import uuid
            misty_filename = f"temp_greeting_{uuid.uuid4().hex[:8]}.wav"
            
            # Convert to base64 for Misty API
            self.logger.info(f"📤 Uploading to Misty as: {misty_filename}")
            b64_data = base64.b64encode(wav_bytes).decode('utf-8')
            
            # Upload to Misty
            upload_response = self.misty.save_audio(
                fileName=misty_filename,
                data=b64_data,
                immediatelyApply=False,
                overwriteExisting=True
            )
            
            if upload_response.status_code != 200:
                self.logger.error(f"❌ Failed to upload to Misty: {upload_response.status_code}")
                return False
            
            self.logger.info(f"✅ Uploaded to Misty successfully")
            
            # Play the audio
            self.logger.info(f"🔊 Playing greeting on Misty")
            play_response = self.misty.play_audio(fileName=misty_filename, volume=100)
            
            if play_response.status_code == 200:
                self.logger.info(f"✅ Playback started successfully")
                
                # Schedule cleanup in background (delete temp file after 5 seconds)
                import threading
                def cleanup():
                    time.sleep(5)
                    try:
                        self.misty.delete_audio(misty_filename)
                        self.logger.debug(f"🗑️  Cleaned up temp file: {misty_filename}")
                    except Exception as e:
                        self.logger.debug(f"Cleanup error (non-fatal): {e}")
                
                threading.Thread(target=cleanup, daemon=True).start()
                return True
            else:
                self.logger.error(f"❌ Failed to play audio: {play_response.status_code}")
                # Try to clean up
                try:
                    self.misty.delete_audio(misty_filename)
                except:
                    pass
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error playing local cached greeting: {e}", exc_info=True)
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
                "cooldown_remaining": 0,
                "has_cached_audio": person_name in self.greeting_audio_cache
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
            "cooldown_remaining": cooldown_remaining,
            "has_cached_audio": person_name in self.greeting_audio_cache
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
    
    def reload_cache(self):
        """Reload the greeting audio cache from local storage.
        
        Useful after generating new cached greetings.
        """
        self.logger.info("🔄 Reloading local greeting cache...")
        self.greeting_audio_cache.clear()
        self._load_local_greeting_cache()
        self.logger.info(f"✅ Cache reloaded: {len(self.greeting_audio_cache)} cached greetings")
