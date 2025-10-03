#!/usr/bin/env python3
"""Misty Aicco Assistant - Main Application

A voice-activated AI assistant for Misty II robots with continuous face recognition
and personalized greetings.

Features:
- Continuous face recognition with personalized greetings
- Voice-activated AI assistant with "Hey Aicco" wake word
- OpenAI GPT integration for intelligent responses
- LED feedback for different states
- Robust error handling and logging

Author: Misty Robotics
Date: October 2, 2025
"""

import os
import sys
import signal
import logging
import threading
import time
from typing import Optional

# Add project root to path for mistyPy access
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))

from mistyPy.Robot import Robot
from mistyPy.Events import Events
from src.config import get_config, Config
from src.core.face_recognition_manager import FaceRecognitionManager
from src.core.greeting_manager import GreetingManager
from src.core.audio_monitor import AudioMonitor
from src.handlers.speech_to_text import SpeechToTextHandler
from src.core.ai_chat_handler import AIChatHandler
from src.handlers.realtime_handler import RealtimeHandler
from src.core.personality_manager import PersonalityManager


class MistyAiccoAssistant:
    """Main application class for Misty Aicco Assistant.
    
    Coordinates face recognition, voice assistant, and all supporting modules.
    """
    
    def __init__(self, config: Config):
        """Initialize the Misty Aicco Assistant.
        
        Args:
            config: Configuration object with all settings
        """
        self.config = config
        self.logger = self._setup_logging()
        self.misty: Optional[Robot] = None
        self.running = False
        
        self.logger.info("Initializing Misty Aicco Assistant...")
        
        # Modules will be initialized in later tasks
        self.face_recognition_manager = None
        self.audio_monitor = None
        self.speech_to_text = None
        self.ai_chat = None
        self.realtime_handler = None
        self.state_manager = None
        self.greeting_manager = None
        self.personality_manager = None
        
        # Conversation mode state
        self.conversation_active = False
        self.conversation_timer: Optional[threading.Timer] = None
        self.speaking_lock = False
        
        # Battery saving state
        self.services_stopped = False
        
    def _setup_logging(self) -> logging.Logger:
        """Set up logging configuration.
        
        Returns:
            Configured logger instance
        """
        logger = logging.getLogger("MistyAiccoAssistant")
        logger.setLevel(getattr(logging, self.config.logging.level))
        
        # Console handler
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(getattr(logging, self.config.logging.level))
        console_formatter = logging.Formatter(
            '%(asctime)s - %(name)s - %(levelname)s - %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )
        console_handler.setFormatter(console_formatter)
        logger.addHandler(console_handler)
        
        # File handler (if enabled)
        if self.config.logging.log_to_file:
            from logging.handlers import RotatingFileHandler
            file_handler = RotatingFileHandler(
                self.config.logging.log_file_path,
                maxBytes=self.config.logging.max_log_size_mb * 1024 * 1024,
                backupCount=self.config.logging.backup_count
            )
            file_handler.setLevel(getattr(logging, self.config.logging.level))
            file_formatter = logging.Formatter(
                '%(asctime)s - %(name)s - %(levelname)s - %(funcName)s:%(lineno)d - %(message)s',
                datefmt='%Y-%m-%d %H:%M:%S'
            )
            file_handler.setFormatter(file_formatter)
            logger.addHandler(file_handler)
        
        return logger
    
    def start(self):
        """Start the Misty Aicco Assistant.
        
        This method initializes all modules and starts the main event loop.
        """
        try:
            self.logger.info("=" * 60)
            self.logger.info("Starting Misty Aicco Assistant")
            self.logger.info("=" * 60)
            
            # Print configuration
            self.config.print_config()
            
            # Connect to Misty
            self.logger.info(f"Connecting to Misty at {self.config.misty.ip_address}...")
            self.misty = Robot(self.config.misty.ip_address)
            self.logger.info("Connected to Misty successfully!")
            
            # Set initial LED state (idle)
            self.logger.info("Setting initial LED state...")
            self.misty.change_led(*self.config.led.idle)
            
            # Initialize personality manager (animations, screensaver)
            if self.config.personality.enabled:
                self._initialize_personality()
            
            # Initialize modules
            if self.config.face_recognition.enabled:
                self._initialize_face_recognition()
            
            if self.config.voice_assistant.enabled:
                self._initialize_voice_assistant()
            
            # TODO: Initialize remaining modules (will be implemented in later tasks)
            # self._initialize_state_manager()
            
            self.running = True
            self.logger.info("Misty Aicco Assistant is now running!")
            self.logger.info("Press Ctrl+C to stop.")
            
            # Keep the main thread alive for event processing
            self.misty.keep_alive()
            
        except KeyboardInterrupt:
            self.logger.info("\nReceived interrupt signal. Shutting down...")
            self.stop()
        except Exception as e:
            self.logger.error(f"Error during startup: {e}", exc_info=True)
            self.stop()
            raise
    
    def stop(self):
        """Stop the Misty Aicco Assistant gracefully.
        
        Cleans up all resources, unregisters events, and shuts down modules.
        """
        if not self.running:
            return
        
        self.logger.info("Shutting down Misty Aicco Assistant...")
        self.running = False
        
        try:
            # Clean up conversation mode
            if self.conversation_active:
                self.logger.info("Ending conversation mode...")
                self._end_conversation()
            
            # Stop modules
            if self.personality_manager:
                self.logger.info("Stopping personality manager...")
                self.personality_manager.stop()
            
            if self.face_recognition_manager:
                self.logger.info("Stopping face recognition...")
                self.face_recognition_manager.stop()
            
            if self.audio_monitor:
                self.logger.info("Stopping audio monitor...")
                self.audio_monitor.stop()
            
            if self.realtime_handler:
                self.logger.info("Disconnecting realtime handler...")
                self.realtime_handler.disconnect()
            
            # Unregister all Misty events
            if self.misty:
                self.logger.info("Unregistering all Misty events...")
                self.misty.unregister_all_events()
                
                # Set LED to indicate shutdown
                self.misty.change_led(255, 255, 0)  # Yellow
                
            self.logger.info("Shutdown complete. Goodbye!")
            
        except Exception as e:
            self.logger.error(f"Error during shutdown: {e}", exc_info=True)
    
    def _initialize_personality(self):
        """Initialize personality manager for animations and screensaver."""
        self.logger.info("Initializing personality manager...")
        
        try:
            self.personality_manager = PersonalityManager(
                misty=self.misty,
                idle_timeout_seconds=self.config.personality.idle_timeout_seconds,
                screensaver_enabled=self.config.personality.screensaver_enabled
            )
            
            # Set callback for battery saving mode
            if self.config.personality.battery_saving_enabled:
                self.personality_manager.on_enter_screensaver = self._on_enter_battery_saving
                self.personality_manager.on_exit_screensaver = self._on_exit_battery_saving
            
            self.personality_manager.start()
            
            self.logger.info("✅ Personality manager initialized successfully")
            self.logger.info(f"   Idle timeout: {self.config.personality.idle_timeout_seconds}s")
            self.logger.info(f"   Screensaver: {self.config.personality.screensaver_enabled}")
            self.logger.info(f"   Battery saving: {self.config.personality.battery_saving_enabled}")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize personality manager: {e}", exc_info=True)
            self.personality_manager = None
    
    def _initialize_face_recognition(self):
        """Initialize face recognition module.
        
        Creates and starts the FaceRecognitionManager for continuous face monitoring.
        """
        self.logger.info("Initializing face recognition...")
        
        try:
            # Initialize greeting manager first
            self.logger.info("Setting up greeting manager...")
            self.greeting_manager = GreetingManager(
                misty=self.misty,
                greeting_templates=self.config.face_recognition.greeting_templates,
                cooldown_seconds=self.config.face_recognition.greeting_cooldown_seconds,
                greeting_led_color=self.config.led.greeting,
                idle_led_color=self.config.led.idle
            )
            self.logger.info(f"✅ Greeting manager initialized ({self.config.face_recognition.greeting_cooldown_seconds}s cooldown)")
            
            # Create face recognition manager with callback
            self.face_recognition_manager = FaceRecognitionManager(
                misty=self.misty,
                on_face_recognized=self._on_face_recognized
            )
            
            # Start continuous face recognition
            self.face_recognition_manager.start()
            
            # List known faces
            known_faces = self.face_recognition_manager.get_known_faces()
            if known_faces:
                self.logger.info(f"Known faces in database: {', '.join(known_faces)}")
            else:
                self.logger.info("No faces trained yet. Train faces to enable greetings.")
            
            self.logger.info("✅ Face recognition initialized successfully")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize face recognition: {e}", exc_info=True)
            self.face_recognition_manager = None
            self.greeting_manager = None
    
    def _on_face_recognized(self, face_data: dict):
        """Callback when a face is recognized.
        
        Triggers personalized greeting with cooldown management.
        
        Args:
            face_data: Dictionary containing face information
        """
        # Ignore face recognition while speaking
        if getattr(self, "speaking_lock", False):
            self.logger.debug("Ignoring face recognition during speaking")
            return
        name = face_data.get("name", "Unknown")
        confidence = face_data.get("confidence", 0.0)
        
        self.logger.info(f"👤 Face recognized: {name} (confidence: {confidence:.2f})")
        
        # Record interaction (resets idle timer)
        if self.personality_manager:
            self.personality_manager.record_interaction()
        
        # Task 2.2: Greet person with cooldown management
        if self.greeting_manager:
            # Request greeting immediately to minimize latency
            import time
            recognized_at = time.time()
            self.greeting_manager.greet_person(name, recognized_at=recognized_at)
            
            # Run greeting animation asynchronously so it doesn't delay TTS
            if self.personality_manager and self.config.personality.animations_during_speech:
                try:
                    threading.Thread(target=self.personality_manager.greeting_animation, daemon=True).start()
                except Exception:
                    # Non-fatal if animation thread fails
                    pass
    
    def _initialize_voice_assistant(self):
        """Initialize voice assistant module.
        
        Creates and starts the AudioMonitor for wake word detection.
        Initializes either traditional (STT→GPT→TTS) or realtime (voice→voice) mode.
        """
        self.logger.info("Initializing voice assistant...")
        
        try:
            voice_mode = self.config.voice_assistant.voice_mode
            
            if voice_mode == "traditional":
                self._initialize_traditional_mode()
            elif voice_mode == "realtime":
                self._initialize_realtime_mode()
            else:
                raise ValueError(f"Invalid voice mode: {voice_mode}")
            
            # Create audio monitor with callbacks
            self.audio_monitor = AudioMonitor(
                misty=self.misty,
                on_wake_word_detected=self._on_wake_word_detected,
                on_speech_captured=self._on_speech_captured,
                wake_word_mode=self.config.voice_assistant.wake_word_mode,
                silence_timeout=int(self.config.voice_assistant.silence_threshold_seconds * 1000),
                max_speech_length=int(self.config.voice_assistant.max_recording_seconds * 1000)
            )
            
            # Start continuous audio monitoring
            self.audio_monitor.start()
            
            self.logger.info("✅ Voice assistant initialized successfully")
            self.logger.info(f"   Voice mode: {voice_mode}")
            self.logger.info(f"   Wake word mode: {self.config.voice_assistant.wake_word_mode}")
            if self.config.voice_assistant.wake_word_mode == "misty_builtin":
                self.logger.info("   Wake word: 'Hey Misty'")
            else:
                self.logger.info(f"   Wake word: '{self.config.voice_assistant.wake_word_custom}'")
            
        except Exception as e:
            self.logger.error(f"Failed to initialize voice assistant: {e}", exc_info=True)
            self.audio_monitor = None
            self.speech_to_text = None
            self.ai_chat = None
            self.realtime_handler = None
    
    def _initialize_traditional_mode(self):
        """Initialize traditional mode (STT → GPT → TTS)."""
        self.logger.info("Setting up TRADITIONAL mode (STT → GPT → TTS)...")
        
        # Initialize Speech-to-Text handler
        self.logger.info("  - Setting up OpenAI Whisper for speech-to-text...")
        self.speech_to_text = SpeechToTextHandler(
            misty=self.misty,
            openai_api_key=self.config.openai.api_key,
            whisper_model=self.config.openai.whisper_model
        )
        self.logger.info(f"    ✅ STT initialized (model: {self.config.openai.whisper_model})")
        
        # Initialize AI Chat handler
        self.logger.info("  - Setting up OpenAI Chat for AI responses...")
        self.ai_chat = AIChatHandler(
            openai_api_key=self.config.openai.api_key,
            model=self.config.openai.model,
            max_tokens=self.config.openai.max_tokens,
            temperature=self.config.openai.temperature,
            conversation_history_length=5  # Keep last 5 exchanges
        )
        self.logger.info(f"    ✅ Chat initialized (model: {self.config.openai.model})")
        self.logger.info("  ⚠️  Expected latency: ~5-8 seconds per response")
    
    def _initialize_realtime_mode(self):
        """Initialize realtime mode (voice → voice)."""
        self.logger.info("Setting up REALTIME mode (voice → voice)...")
        
        # Initialize Realtime API handler
        self.logger.info("  - Connecting to OpenAI Realtime API...")
        self.realtime_handler = RealtimeHandler(
            api_key=self.config.openai.api_key,
            model="gpt-4o-realtime-preview-2024-10-01",
            on_transcript_received=self._on_realtime_transcript,
            on_audio_received=self._on_realtime_audio
        )
        
        # Set realtime handler to DEBUG level for troubleshooting
        import logging
        realtime_logger = logging.getLogger("RealtimeHandler")
        realtime_logger.setLevel(logging.DEBUG)
        
        # Add same handlers as main logger so events show in console and file
        for handler in self.logger.handlers:
            realtime_logger.addHandler(handler)
        
        # Connect to the API
        self.realtime_handler.connect()
        self.logger.info("    ✅ Realtime API connected")
        self.logger.info("  ⚡ Expected latency: ~1-3 seconds per response")
        self.logger.info("  🐛 Debug mode enabled for Realtime API")
    
    def _on_wake_word_detected(self, event_data: dict):
        """Callback when wake word is detected.
        
        Args:
            event_data: Event data from wake word detection
        """
        self.logger.info("🎤 Wake word detected!")
        
        # Record interaction (resets idle timer, wakes from screensaver if needed)
        if self.personality_manager:
            self.personality_manager.record_interaction()
        
        # Start conversation mode if enabled
        if self.config.voice_assistant.conversation_mode:
            self._start_conversation()
        
        # Set LED to listening state (purple)
        try:
            self.misty.change_led(*self.config.led.listening)
            self.logger.debug(f"💡 LED set to listening: RGB{self.config.led.listening}")
        except Exception as e:
            self.logger.warning(f"Failed to change LED: {e}")
        
        # Play listening animation
        if self.personality_manager and self.config.personality.animations_during_speech:
            self.personality_manager.listening_animation()
        
        self.logger.info("📝 Listening for your query...")
    
    def _on_speech_captured(self, audio_data: dict):
        """Callback when speech is captured after wake word.
        
        Routes to appropriate handler based on voice mode:
        - Traditional: STT → GPT → TTS pipeline
        - Realtime: Send audio directly to Realtime API
        
        Args:
            audio_data: Dictionary containing audio filename and metadata
        """
        filename = audio_data.get("filename", "unknown")
        self.logger.info(f"🎙️  Speech captured: {filename}")
        
        # Record interaction (user is speaking)
        if self.personality_manager:
            self.personality_manager.record_interaction()
        
        # Reset conversation timer if in conversation mode
        if self.conversation_active:
            self._cancel_conversation_timer()  # We're actively speaking, reset timeout
        
        # Set LED to processing state (cyan)
        try:
            self.misty.change_led(*self.config.led.processing)
            self.logger.debug(f"💡 LED set to processing: RGB{self.config.led.processing}")
        except Exception as e:
            self.logger.warning(f"Failed to change LED: {e}")
        
        # Play thinking animation
        if self.personality_manager and self.config.personality.animations_during_speech:
            self.personality_manager.thinking_animation()
        
        # Route to appropriate mode
        if self.config.voice_assistant.voice_mode == "traditional":
            self._handle_traditional_pipeline(filename)
        elif self.config.voice_assistant.voice_mode == "realtime":
            self._handle_realtime_pipeline(filename)
        else:
            self.logger.error(f"Unknown voice mode: {self.config.voice_assistant.voice_mode}")
            self._speak_and_reset("Sorry, there's a configuration error.")
    
    def _handle_traditional_pipeline(self, filename: str):
        """Handle traditional STT → GPT → TTS pipeline.
        
        Args:
            filename: Audio filename on Misty
        """
        # Task 4.2: Transcribe speech using OpenAI Whisper
        if not self.speech_to_text:
            self.logger.error("Speech-to-Text handler not initialized")
            self._speak_and_reset("Sorry, my speech recognition is not available.")
            return
        
        self.logger.info("🔄 Transcribing speech with OpenAI Whisper...")
        transcription = self.speech_to_text.transcribe_with_retry(filename, max_retries=2)
        
        if not transcription:
            self.logger.error("❌ Transcription failed")
            self._speak_and_reset("Sorry, I couldn't understand that. Please try again.")
            return
        
        self.logger.info(f"✅ Transcription: '{transcription}'")
        
        # Task 5.1: Get AI response from OpenAI Chat
        if not self.ai_chat:
            self.logger.error("AI Chat handler not initialized")
            self._speak_and_reset("Sorry, my AI brain is not available.")
            return
        
        self.logger.info("🤖 Generating AI response...")
        ai_response = self.ai_chat.get_response_with_retry(transcription, max_retries=2)
        
        if not ai_response:
            self.logger.error("❌ AI response generation failed")
            self._speak_and_reset("Sorry, I couldn't think of a response. Please try again.")
            return
        
        self.logger.info(f"✅ AI Response: '{ai_response}'")
        
        # Task 5.2: Speak the response using Text-to-Speech
        self._speak_response(ai_response)
    
    def _handle_realtime_pipeline(self, filename: str):
        """Handle realtime voice → voice pipeline.
        
        Args:
            filename: Audio filename on Misty
        """
        if not self.realtime_handler:
            self.logger.error("Realtime handler not initialized")
            self._speak_and_reset("Sorry, realtime mode is not available.")
            return
        
        if not self.realtime_handler.connected:
            # Try a single reconnect attempt before failing to give the realtime
            # handler a chance to recover from transient network issues.
            self.logger.warning("Realtime API not connected - attempting reconnect...")
            try:
                self.realtime_handler.connect()
            except Exception as e:
                self.logger.error(f"Realtime reconnect failed: {e}")
            if not self.realtime_handler.connected:
                self.logger.error("Realtime API not connected")
                self._speak_and_reset("Sorry, I'm not connected to the voice service.")
                return
        
        # Get audio from Misty (with retry for 503 errors)
        self.logger.info("🔄 Retrieving audio from Misty...")
        import time
        import base64
        
        max_retries = 3
        retry_delay = 0.5  # seconds
        
        for attempt in range(max_retries):
            try:
                if attempt > 0:
                    self.logger.info(f"   Retry {attempt}/{max_retries-1}...")
                    time.sleep(retry_delay)
                
                response = self.misty.get_audio_file(fileName=filename, base64=True)
                
                # Parse response to get base64 audio
                if response.status_code != 200:
                    if response.status_code == 503 and attempt < max_retries - 1:
                        # Service unavailable - file might not be ready yet, retry
                        self.logger.debug(f"   Got 503, waiting {retry_delay}s before retry...")
                        continue
                    raise Exception(f"Failed to get audio file: {response.status_code}")
                
                result = response.json()
                if not result or "result" not in result:
                    raise Exception("No result in audio file response")
                
                base64_audio = result["result"].get("base64")
                if not base64_audio:
                    raise Exception("No base64 data in response")
                
                # Decode base64 to bytes
                audio_bytes = base64.b64decode(base64_audio)
                
                self.logger.info(f"✅ Audio retrieved: {len(audio_bytes)} bytes")
                break  # Success, exit retry loop
                
            except Exception as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    self.logger.error(f"❌ Failed to retrieve audio after {max_retries} attempts: {e}")
                    self._speak_and_reset("Sorry, I couldn't retrieve the audio.")
                    return
                # Otherwise continue to next retry
        else:
            # Should not reach here, but handle just in case
            self.logger.error("❌ Failed to retrieve audio: max retries exceeded")
            self._speak_and_reset("Sorry, I couldn't retrieve the audio.")
            return
        
        # Send to Realtime API
        self.logger.info("⚡ Sending to Realtime API...")
        try:
            self.realtime_handler.process_audio_file(audio_bytes)
            self.logger.info("✅ Audio sent to Realtime API, waiting for response...")
            # Response will come via callbacks (_on_realtime_transcript and _on_realtime_audio)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to process with Realtime API: {e}")
            self._speak_and_reset("Sorry, I had trouble processing that.")
    
    def _on_realtime_transcript(self, transcript: str):
        """Callback when transcript is received from Realtime API.
        
        Args:
            transcript: Transcribed text from Realtime API
        """
        self.logger.info(f"📝 Realtime transcript: '{transcript}'")
    
    def _on_realtime_audio(self, audio_bytes: bytes):
        """Callback when audio response is received from Realtime API.
        
        Args:
            audio_bytes: Audio response from Realtime API (PCM16 format, 24kHz)
        """
        self.logger.info(f"🔊 Realtime audio received: {len(audio_bytes)} bytes (PCM16)")
        
        # Convert PCM to WAV format for Misty
        try:
            import uuid
            import base64
            import struct
            
            # Generate unique filename
            temp_filename = f"realtime_response_{uuid.uuid4().hex[:8]}.wav"
            
            # Convert PCM16 to WAV by adding WAV header
            # Optimize: Downsample from 24kHz to 16kHz for faster upload (speech quality is sufficient)
            original_sample_rate = 24000
            target_sample_rate = 16000
            num_channels = 1
            bits_per_sample = 16
            
            # Downsample audio data from 24kHz to 16kHz using linear interpolation
            import array
            samples_24k = array.array('h')
            samples_24k.frombytes(audio_bytes)
            
            # Simple downsampling by linear interpolation
            ratio = target_sample_rate / original_sample_rate  # 16000/24000 = 0.6667
            out_len = int(len(samples_24k) * ratio)
            samples_16k = array.array('h', [0] * out_len)
            
            for i in range(out_len):
                src_pos = i / ratio
                j = int(src_pos)
                frac = src_pos - j
                if j + 1 < len(samples_24k):
                    a = samples_24k[j]
                    b = samples_24k[j + 1]
                    val = int(a + (b - a) * frac)
                else:
                    val = samples_24k[j] if j < len(samples_24k) else 0
                samples_16k[i] = max(-32768, min(32767, val))
            
            downsampled_bytes = samples_16k.tobytes()
            data_size = len(downsampled_bytes)
            
            byte_rate = target_sample_rate * num_channels * bits_per_sample // 8
            block_align = num_channels * bits_per_sample // 8
            
            # Build WAV header for 16kHz audio
            wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
                b'RIFF',
                36 + data_size,  # File size - 8
                b'WAVE',
                b'fmt ',
                16,  # fmt chunk size
                1,   # PCM format
                num_channels,
                target_sample_rate,
                byte_rate,
                block_align,
                bits_per_sample,
                b'data',
                data_size
            )
            
            # Combine header and downsampled data
            wav_bytes = wav_header + downsampled_bytes
            
            self.logger.info(f"🔽 Downsampled audio: {original_sample_rate}Hz -> {target_sample_rate}Hz ({len(audio_bytes)} -> {len(downsampled_bytes)} bytes, {100 - int(100*len(downsampled_bytes)/len(audio_bytes))}% smaller)")
            
            self.logger.info(f"✅ Converted PCM to WAV: {len(wav_bytes)} bytes total")
            
            # Convert WAV bytes to base64 string (required by Misty API)
            audio_base64 = base64.b64encode(wav_bytes).decode('utf-8')
            base64_size_mb = len(audio_base64) / (1024 * 1024)
            
            # Upload to Misty with timing
            self.logger.info(f"📤 Uploading audio to Misty... ({base64_size_mb:.2f} MB base64)")
            upload_start = time.time()
            upload_response = self.misty.save_audio(
                fileName=temp_filename,
                data=audio_base64,
                immediatelyApply=False,
                overwriteExisting=True
            )
            upload_duration = time.time() - upload_start
            
            if upload_response.status_code == 200:
                self.logger.info(f"✅ Audio uploaded: {temp_filename} (took {upload_duration:.2f}s)")
                
                # Play the audio
                self._play_realtime_audio(temp_filename)
            else:
                self.logger.error(f"❌ Failed to upload audio: {upload_response.status_code}")
                self._speak_and_reset("Sorry, I couldn't play the response.")
            
        except Exception as e:
            self.logger.error(f"❌ Failed to handle realtime audio: {e}", exc_info=True)
            self._speak_and_reset("Sorry, I had trouble playing the response.")
    
    def _play_realtime_audio(self, filename: str):
        """Play realtime audio response through Misty.
        
        Args:
            filename: Filename of audio on Misty
        """
        # Enter speaking state: lock and pause audio monitor
        self._enter_speaking_state()
        try:
            # Set LED to speaking state
            self.misty.change_led(*self.config.led.speaking)
            self.logger.info(f"🔊 Playing realtime audio: {filename}")
            
            play_response = self.misty.play_audio(fileName=filename, volume=100)
            if play_response.status_code == 200:
                self.logger.info("✅ Audio playback started")
                self._wait_for_audio_play_complete()
            else:
                self.logger.warning(f"Play audio returned status {play_response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Failed to play audio: {e}")
        finally:
            self._exit_speaking_state_after_playback()
            self.logger.info("✅ Realtime response complete!")
    
    def _speak_response(self, text: str):
        """Speak AI response using Misty's TTS and handle conversation/idle after completion."""
        # Enter speaking state: lock and pause audio monitor
        self._enter_speaking_state()
        
        try:
            try:
                self.misty.change_led(*self.config.led.speaking)
                self.logger.debug(f"💡 LED set to speaking: RGB{self.config.led.speaking}")
            except Exception as e:
                self.logger.warning(f"Failed to change LED: {e}")
            
            if self.personality_manager and self.config.personality.animations_during_speech:
                self.personality_manager.speaking_animation()
            
            self.logger.info(f"🔊 Speaking: '{text}'")
            self._speak_and_wait_for_tts_complete(text)
        except Exception as e:
            self.logger.error(f"❌ Failed during TTS: {e}")
        finally:
            self._exit_speaking_state_after_playback()

    def _enter_speaking_state(self):
        """Enter speaking state: set lock and pause audio monitor."""
        self.speaking_lock = True
        if self.audio_monitor:
            try:
                self.audio_monitor.pause()
            except Exception:
                pass

    def _exit_speaking_state_after_playback(self):
        """Exit speaking state and transition to conversation follow-up or idle."""
        # Conversation mode follow-ups
        if self.config.voice_assistant.conversation_mode and self.conversation_active:
            self.logger.info("💬 Conversation mode active - listening for follow-up...")
            self._start_conversation_timer()
            try:
                self.misty.change_led(*self.config.led.listening)
                self.logger.debug("💡 LED set to listening (waiting for follow-up)")
            except Exception as e:
                self.logger.warning(f"Failed to change LED: {e}")
            if self.audio_monitor:
                try:
                    self.audio_monitor.resume()
                    self.audio_monitor.capture_speech_without_wake_word()
                except Exception:
                    pass
        else:
            # Return to idle and wake word mode
            try:
                self.misty.change_led(*self.config.led.idle)
                self.logger.debug(f"💡 LED returned to idle: RGB{self.config.led.idle}")
            except Exception as e:
                self.logger.warning(f"Failed to reset LED: {e}")
            if self.audio_monitor:
                try:
                    self.audio_monitor.resume()
                    self.audio_monitor.restart_wake_word_detection()
                except Exception:
                    pass
        self.speaking_lock = False

    def _wait_for_audio_play_complete(self, timeout_seconds: float = 30.0):
        """Block until AudioPlayComplete event arrives or timeout."""
        import time
        from mistyPy.Events import Events
        event_name = "AudioPlayCompleteEvent"
        done_flag = {"done": False}
        
        def _handler(_):
            done_flag["done"] = True
        
        try:
            self.misty.register_event(
                event_type=Events.AudioPlayComplete,
                event_name=event_name,
                keep_alive=False,
                callback_function=lambda data: _handler(data)
            )
        except Exception as e:
            self.logger.warning(f"Failed to register AudioPlayComplete: {e}")
            time.sleep(2)
            return
        
        start = time.time()
        while not done_flag["done"] and (time.time() - start) < timeout_seconds:
            time.sleep(0.05)
        try:
            self.misty.unregister_event(event_name)
        except Exception:
            pass

    def _speak_and_wait_for_tts_complete(self, text: str, timeout_seconds: float = 30.0):
        """Speak text and wait for TextToSpeechComplete event or timeout."""
        import time
        from mistyPy.Events import Events
        event_name = "TextToSpeechCompleteEvent"
        done_flag = {"done": False}
        
        def _handler(_):
            done_flag["done"] = True
        
        # Register completion event first
        try:
            self.misty.register_event(
                event_type=Events.TextToSpeechComplete,
                event_name=event_name,
                keep_alive=False,
                callback_function=lambda data: _handler(data)
            )
        except Exception as e:
            self.logger.warning(f"Failed to register TextToSpeechComplete: {e}")
        
        # Speak
        try:
            response = self.misty.speak(text=text, flush=True)
            if response.status_code == 200:
                self.logger.info("✅ Speech playback started")
            else:
                self.logger.warning(f"Speak command returned status {response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Failed to speak response: {e}")
            try:
                self.misty.unregister_event(event_name)
            except Exception:
                pass
            return
        
        start = time.time()
        while not done_flag["done"] and (time.time() - start) < timeout_seconds:
            time.sleep(0.05)
        try:
            self.misty.unregister_event(event_name)
        except Exception:
            pass
    
    def _start_conversation(self):
        """Start a new conversation session."""
        if not self.config.voice_assistant.conversation_mode:
            return
        
        self.conversation_active = True
        self.logger.info("🎬 Starting conversation mode")
        self._start_conversation_timer()
    
    def _end_conversation(self):
        """End the current conversation session."""
        if not self.conversation_active:
            return
        
        self.conversation_active = False
        self._cancel_conversation_timer()
        self.logger.info("🎬 Ending conversation mode - returning to idle")
        
        # Return LED to idle
        try:
            self.misty.change_led(*self.config.led.idle)
        except Exception as e:
            self.logger.warning(f"Failed to reset LED: {e}")
        
        # Restart wake word detection for next "Hey Misty"
        if self.audio_monitor:
            self.audio_monitor.restart_wake_word_detection()
    
    def _start_conversation_timer(self):
        """Start or restart the conversation timeout timer."""
        # Cancel existing timer if any
        self._cancel_conversation_timer()
        
        # Start new timer
        timeout = self.config.voice_assistant.conversation_timeout_seconds
        self.conversation_timer = threading.Timer(timeout, self._on_conversation_timeout)
        self.conversation_timer.daemon = True
        self.conversation_timer.start()
        self.logger.debug(f"⏰ Conversation timer set for {timeout}s")
    
    def _cancel_conversation_timer(self):
        """Cancel the conversation timeout timer."""
        if self.conversation_timer and self.conversation_timer.is_alive():
            self.conversation_timer.cancel()
            self.logger.debug("⏰ Conversation timer cancelled")
    
    def _on_conversation_timeout(self):
        """Called when conversation times out due to inactivity."""
        self.logger.info("⏰ Conversation timeout - no speech detected")
        self._end_conversation()
    
    def _speak_and_reset(self, error_message: str):
        """Speak error message and return to idle state.
        
        Args:
            error_message: Error message to speak
        """
        try:
            self.misty.speak(text=error_message, flush=True)
        except Exception as e:
            self.logger.error(f"Failed to speak error message: {e}")
        
        # Return LED to idle
        try:
            self.misty.change_led(*self.config.led.idle)
        except Exception as e:
            self.logger.warning(f"Failed to reset LED: {e}")
    
    def _initialize_state_manager(self):
        """Initialize state manager.
        
        TODO: Implement in Phase 6
        """
        pass
    
    def _on_enter_battery_saving(self):
        """Called when entering screensaver - stop camera to save battery, keep microphone for wake word."""
        if self.services_stopped:
            return
        
        self.logger.info("🔋 Entering screensaver mode...")
        
        try:
            # Stop face recognition (camera) to save power
            if self.face_recognition_manager and self.face_recognition_manager.running:
                self.logger.info("   Stopping face recognition (camera off)...")
                self.face_recognition_manager.stop()
            
            # KEEP audio monitor running so we can hear "Hey Misty" to wake up!
            # Note: Not stopping audio monitor - wake word detection stays active
            self.logger.info("   Audio monitor stays active - listening for 'Hey Misty' to wake up")
            
            self.services_stopped = True
            self.logger.info("✅ Screensaver active - say 'Hey Misty' to wake up anytime!")
            
        except Exception as e:
            self.logger.error(f"Error entering screensaver mode: {e}", exc_info=True)
    
    def _on_exit_battery_saving(self):
        """Called when exiting screensaver - restart camera service."""
        if not self.services_stopped:
            return
        
        self.logger.info("🔌 Waking up from screensaver - restarting services...")
        
        try:
            # Restart face recognition (camera)
            if self.face_recognition_manager and self.config.face_recognition.enabled:
                self.logger.info("   Restarting face recognition (camera on)...")
                self.face_recognition_manager.start()
            
            # Audio monitor was never stopped - it stayed active for wake word detection
            # No need to restart it
            self.logger.info("   Audio monitor already active")
            
            self.services_stopped = False
            self.logger.info("✅ Services restarted - ready for interactions!")
            
        except Exception as e:
            self.logger.error(f"Error exiting battery saving mode: {e}", exc_info=True)


def signal_handler(sig, frame):
    """Handle interrupt signals for graceful shutdown."""
    print("\nInterrupt received. Shutting down gracefully...")
    sys.exit(0)


def main():
    """Main entry point for the application."""
    # Register signal handlers for graceful shutdown
    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)
    
    try:
        # Load configuration
        config = get_config()
        
        # Create and start the assistant
        assistant = MistyAiccoAssistant(config)
        assistant.start()
        
    except ValueError as e:
        print(f"\n❌ Configuration Error: {e}")
        print("\nPlease check your environment variables or env.example file.")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Fatal Error: {e}")
        import traceback
        traceback.print_exc()
        sys.exit(1)


if __name__ == "__main__":
    main()

