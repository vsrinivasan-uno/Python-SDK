"""Audio Monitor for Misty Aicco Assistant.

Manages continuous audio monitoring for wake word detection and voice queries.
"""

import logging
import threading
import time
from typing import Optional, Callable
from mistyPy.Robot import Robot
from mistyPy.Events import Events


class AudioMonitor:
    """Manages audio monitoring for wake word detection.
    
    This class handles:
    - Starting and stopping wake word detection
    - Monitoring for wake word events
    - Capturing speech after wake word detected
    - Thread-safe operation to avoid blocking face recognition
    """
    
    def __init__(self, misty: Robot, 
                 on_wake_word_detected: Optional[Callable] = None,
                 on_speech_captured: Optional[Callable] = None,
                 wake_word_mode: str = "misty_builtin",
                 silence_timeout: int = 2000,
                 max_speech_length: int = 15000):
        """Initialize the Audio Monitor.
        
        Args:
            misty: Misty robot instance
            on_wake_word_detected: Optional callback when wake word is detected.
                                  Function signature: on_wake_word_detected(event_data: dict)
            on_speech_captured: Optional callback when speech is captured.
                               Function signature: on_speech_captured(audio_data: dict)
            wake_word_mode: Wake word mode ("misty_builtin" or "openai_whisper")
            silence_timeout: Milliseconds of silence before ending speech capture (default: 2000ms = 2s)
            max_speech_length: Maximum speech length in milliseconds (default: 15000ms = 15s)
        """
        self.misty = misty
        self.on_wake_word_detected = on_wake_word_detected
        self.on_speech_captured = on_speech_captured
        self.wake_word_mode = wake_word_mode
        self.silence_timeout = silence_timeout
        self.max_speech_length = max_speech_length
        self.logger = logging.getLogger("AudioMonitor")
        
        self.running = False
        self.wake_word_event_name = "WakeWordEvent"
        self.voice_record_event_name = "VoiceRecordEvent"
        
        # Thread for non-blocking audio monitoring
        self.monitor_thread: Optional[threading.Thread] = None
        self.lock = threading.Lock()
        
        self.logger.info(f"Audio Monitor initialized (mode: {wake_word_mode})")
        self.logger.info(f"Silence timeout: {silence_timeout}ms, Max speech: {max_speech_length}ms")
    
    def start(self):
        """Start audio monitoring for wake word detection.
        
        This method:
        1. Starts Misty's key phrase recognition service
        2. Registers event listeners for wake word and voice recording
        3. Sets up non-blocking monitoring
        """
        if self.running:
            self.logger.warning("Audio monitor is already running")
            return
        
        try:
            self.logger.info("Starting audio monitoring...")
            
            # Start key phrase recognition based on mode
            if self.wake_word_mode == "misty_builtin":
                self._start_builtin_wake_word()
            elif self.wake_word_mode == "openai_whisper":
                self._start_whisper_wake_word()
            else:
                self.logger.error(f"Invalid wake word mode: {self.wake_word_mode}")
                return
            
            # Register event handlers
            self._register_events()
            
            self.running = True
            self.logger.info("✅ Audio monitoring started successfully")
            
        except Exception as e:
            self.logger.error(f"❌ Error starting audio monitor: {e}", exc_info=True)
            self.running = False
    
    def stop(self):
        """Stop audio monitoring.
        
        This method:
        1. Stops key phrase recognition
        2. Unregisters event listeners
        3. Cleans up resources
        """
        if not self.running:
            self.logger.warning("Audio monitor is not running")
            return
        
        try:
            self.logger.info("Stopping audio monitoring...")
            
            # Unregister events
            self.misty.unregister_event(self.wake_word_event_name)
            self.misty.unregister_event(self.voice_record_event_name)
            self.logger.info("Event listeners unregistered")
            
            # Stop key phrase recognition
            response = self.misty.stop_key_phrase_recognition()
            if response.status_code == 200:
                self.logger.info("✅ Key phrase recognition stopped")
            else:
                self.logger.warning(f"Failed to stop key phrase recognition: {response.status_code}")
            
            self.running = False
            self.logger.info("Audio monitoring stopped")
            
        except Exception as e:
            self.logger.error(f"Error stopping audio monitor: {e}", exc_info=True)
    
    def _start_builtin_wake_word(self):
        """Start Misty's built-in key phrase recognition (default wake word)."""
        self.logger.info("🎤 Starting built-in key phrase recognition (wake word: 'Hey Misty')...")
        
        try:
            response = self.misty.start_key_phrase_recognition(
                overwriteExisting=True,
                silenceTimeout=self.silence_timeout,
                maxSpeechLength=self.max_speech_length,
                captureSpeech=True  # Automatically capture speech after wake word
            )
            
            if response.status_code == 200:
                self.logger.info("✅ Built-in key phrase recognition started")
                self.logger.info("   Wake word: 'Hey Misty'")
                self.logger.info(f"   Silence timeout: {self.silence_timeout}ms")
                self.logger.info(f"   Max speech length: {self.max_speech_length}ms")
            else:
                self.logger.error(f"❌ Failed to start key phrase recognition: {response.status_code}")
                self.logger.error(f"   Response: {response.text}")
                raise RuntimeError(f"Key phrase recognition failed: {response.text}")
                
        except Exception as e:
            self.logger.error(f"❌ Error starting built-in wake word: {e}", exc_info=True)
            raise
    
    def _start_whisper_wake_word(self):
        """Start OpenAI Whisper-based wake word detection (custom wake word).
        
        Note: This will be implemented in future if custom wake words are needed.
        """
        self.logger.warning("⚠️  OpenAI Whisper wake word mode not yet implemented")
        self.logger.info("   For now, use 'misty_builtin' mode with 'Hey Misty' wake word")
        self.logger.info("   Custom wake words can be added in a future task")
        raise NotImplementedError("OpenAI Whisper wake word detection not yet implemented")
    
    def _register_events(self):
        """Register event handlers for wake word and voice recording."""
        self.logger.info("📡 Registering audio event handlers...")
        
        try:
            # Register KeyPhraseRecognized event
            self.misty.register_event(
                event_type=Events.KeyPhraseRecognized,
                event_name=self.wake_word_event_name,
                keep_alive=True,  # Keep listening continuously
                callback_function=lambda data: self._on_wake_word_event(data)
            )
            self.logger.info("✅ Wake word event handler registered")
            
            # Register VoiceRecord event (fires when speech capture completes)
            self.misty.register_event(
                event_type=Events.VoiceRecord,
                event_name=self.voice_record_event_name,
                keep_alive=True,
                callback_function=lambda data: self._on_voice_record_event(data)
            )
            self.logger.info("✅ Voice record event handler registered")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to register event handlers: {e}", exc_info=True)
            raise
    
    def _on_wake_word_event(self, event_data: dict):
        """Internal callback for wake word detection events.
        
        Args:
            event_data: Event data from Misty's key phrase recognition
        """
        try:
            self.logger.debug(f"Wake word event received: {event_data}")
            
            # Extract wake word information
            if "message" not in event_data:
                self.logger.warning("Wake word event missing 'message' field")
                return
            
            message = event_data["message"]
            
            # Log wake word detection
            self.logger.info("🎤 Wake word detected!")
            self.logger.info(f"   Event data: {message}")
            
            # Call external callback if provided
            if self.on_wake_word_detected:
                try:
                    self.on_wake_word_detected(message)
                except Exception as e:
                    self.logger.error(f"Error in wake word callback: {e}", exc_info=True)
            
        except Exception as e:
            self.logger.error(f"Error processing wake word event: {e}", exc_info=True)
    
    def _on_voice_record_event(self, event_data: dict):
        """Internal callback for voice recording events.
        
        This fires when speech capture completes after wake word detection.
        
        Args:
            event_data: Event data from Misty's voice recording
        """
        try:
            self.logger.debug(f"Voice record event received: {event_data}")
            
            # Extract voice recording information
            if "message" not in event_data:
                self.logger.warning("Voice record event missing 'message' field")
                return
            
            message = event_data["message"]
            
            # Get audio file name
            audio_filename = message.get("filename", None)
            success = message.get("success", False)
            error_message = message.get("errorMessage", None)
            
            if success and audio_filename:
                self.logger.info(f"🎙️  Speech captured successfully: {audio_filename}")
                
                # Prepare audio data for callback
                audio_data = {
                    "filename": audio_filename,
                    "success": success,
                    "timestamp": time.time(),
                    "raw_event": message
                }
                
                # Call external callback if provided
                if self.on_speech_captured:
                    try:
                        self.on_speech_captured(audio_data)
                    except Exception as e:
                        self.logger.error(f"Error in speech captured callback: {e}", exc_info=True)
            else:
                self.logger.error(f"❌ Speech capture failed: {error_message}")
            
            # IMPORTANT: Restart wake word detection for continuous listening
            # Misty's key phrase recognition stops after capturing speech
            # NOTE: We don't auto-restart here anymore - let the main assistant decide
            # whether to restart wake word detection (normal mode) or capture speech
            # directly (conversation mode)
            
        except Exception as e:
            self.logger.error(f"Error processing voice record event: {e}", exc_info=True)
    
    def is_running(self) -> bool:
        """Check if audio monitoring is running.
        
        Returns:
            True if monitoring is active, False otherwise
        """
        return self.running
    
    def restart_wake_word_detection(self):
        """Manually restart wake word detection.
        
        Used when conversation mode ends or after processing a query
        to return to normal "Hey Misty" wake word mode.
        """
        if not self.running:
            self.logger.warning("Cannot restart wake word - audio monitor not running")
            return
        
        try:
            self.logger.info("🔄 Restarting wake word detection...")
            if self.wake_word_mode == "misty_builtin":
                self._start_builtin_wake_word()
                self.logger.info("✅ Wake word detection restarted - ready for next 'Hey Misty'")
        except Exception as e:
            self.logger.error(f"❌ Failed to restart wake word detection: {e}", exc_info=True)
    
    def capture_speech_without_wake_word(self):
        """Capture speech directly without waiting for wake word.
        
        This is used for conversation mode follow-ups where we want to 
        capture ANY speech, not just speech after "Hey Misty".
        """
        if not self.running:
            self.logger.warning("Cannot capture speech - audio monitor not running")
            return
        
        try:
            self.logger.info("🎤 Starting direct speech capture (no wake word required)...")
            
            # Use capture_speech instead of key phrase recognition
            # This captures ANY speech without requiring "Hey Misty"
            response = self.misty.capture_speech(
                overwriteExisting=True,
                silenceTimeout=self.silence_timeout,
                maxSpeechLength=self.max_speech_length,
                requireKeyPhrase=False  # KEY: Don't require "Hey Misty"
            )
            
            if response.status_code == 200:
                self.logger.info("✅ Direct speech capture started - speak now!")
            else:
                self.logger.error(f"❌ Failed to start speech capture: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"❌ Error starting speech capture: {e}", exc_info=True)
    
    def get_status(self) -> dict:
        """Get current audio monitor status.
        
        Returns:
            Dictionary with status information
        """
        return {
            "running": self.running,
            "mode": self.wake_word_mode,
            "silence_timeout_ms": self.silence_timeout,
            "max_speech_length_ms": self.max_speech_length
        }

