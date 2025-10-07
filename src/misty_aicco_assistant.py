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
from src.prompts import UNO_BSAI_SYSTEM_PROMPT


class AudioQueueManager:
    """Manages queue of audio chunks for sequential playback on Misty.
    
    This class handles:
    - Queueing audio chunks as they arrive from OpenAI
    - Converting PCM to WAV format
    - Downsampling for faster uploads
    - Uploading chunks to Misty
    - Playing chunks sequentially without gaps
    - Handling AudioPlayComplete events to trigger next chunk
    """
    
    def __init__(self, misty, logger, config, on_response_complete=None, personality_manager=None):
        """Initialize the AudioQueueManager.
        
        Args:
            misty: Misty robot instance
            logger: Logger instance
            config: Configuration object
            on_response_complete: Optional callback when response is complete
            personality_manager: Optional PersonalityManager for animations
        """
        self.misty = misty
        self.logger = logger
        self.config = config
        self.personality_manager = personality_manager
        
        # Queue of chunks ready to play: [(filename, wav_data, is_final), ...]
        self.play_queue = []
        self.lock = threading.Lock()
        
        # Current playback state
        self.currently_playing = None  # (filename, is_final)
        self.currently_uploading = False  # Track if upload is in progress
        self.is_processing = False
        self.fallback_timer = None  # Timer for fallback playback completion
        self.animations_started = False  # Track if we started continuous animations
        
        # Statistics
        self.chunks_received = 0
        self.chunks_played = 0
        self.chunks_uploaded = 0
        
        # File cleanup tracking
        self.uploaded_files = []  # Track files for cleanup
        # Optional callback invoked when a full response playback is complete
        self.on_response_complete = on_response_complete
        
    def add_chunk(self, audio_bytes: bytes, is_final: bool, chunk_index: int):
        """Add audio chunk to queue and start processing if idle.
        
        Args:
            audio_bytes: Raw PCM16 audio data (24kHz)
            is_final: Whether this is the last chunk
            chunk_index: Index of this chunk
        """
        import uuid
        
        self.logger.info(f"📥 Received chunk {chunk_index}: {len(audio_bytes)} bytes (final={is_final})")
        self.chunks_received += 1
        
        try:
            # Generate unique filename
            filename = f"chunk_{uuid.uuid4().hex[:8]}_{chunk_index}.wav"
            
            # Process audio (convert to WAV, downsample)
            wav_data = self._prepare_audio(audio_bytes)
            
            # Add to queue
            with self.lock:
                self.play_queue.append((filename, wav_data, is_final))
                queue_size = len(self.play_queue)
            
            self.logger.info(f"📋 Chunk {chunk_index} queued as {filename} (queue size: {queue_size})")
            
            # Start processing if idle
            if not self.is_processing:
                self._process_next()
                
        except Exception as e:
            self.logger.error(f"❌ Error adding chunk {chunk_index}: {e}", exc_info=True)
            # Continue processing even if one chunk fails
            if not self.is_processing and len(self.play_queue) > 0:
                self._process_next()
    
    def _prepare_audio(self, audio_bytes: bytes) -> bytes:
        """Convert PCM16 to WAV format and downsample.
        
        Args:
            audio_bytes: Raw PCM16 audio at 24kHz
            
        Returns:
            WAV format audio at 16kHz
        """
        import array
        import struct
        
        # Downsample from 24kHz to 16kHz for faster upload
        original_sample_rate = 24000
        target_sample_rate = 16000
        num_channels = 1
        bits_per_sample = 16
        
        # Convert bytes to samples
        samples_24k = array.array('h')
        samples_24k.frombytes(audio_bytes)
        
        # Downsample using linear interpolation
        ratio = target_sample_rate / original_sample_rate  # 0.6667
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
        
        # Create WAV header
        byte_rate = target_sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + data_size,
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
        
        return wav_header + downsampled_bytes
    
    def _process_next(self):
        """Process next chunk from queue.
        
        This method now implements parallel processing:
        - If not currently playing: upload and play first chunk
        - If currently playing: pre-upload next chunk in background
        """
        with self.lock:
            if not self.play_queue:
                self.logger.debug("Queue empty, waiting for more chunks...")
                return
            
            if self.currently_playing:
                # Already playing - check if we should pre-upload next chunk (if parallel upload enabled)
                if self.config.voice_assistant.parallel_upload_enabled:
                    if not self.currently_uploading and len(self.play_queue) > 0:
                        # Pre-upload next chunk while current one plays
                        filename, wav_data, is_final = self.play_queue[0]  # Peek, don't pop yet
                        self.currently_uploading = True
                        self.logger.info(f"🚀 Pre-uploading next chunk: {filename} (while playing)")
                        
                        # Upload in background thread
                        threading.Thread(
                            target=self._pre_upload_chunk,
                            args=(filename, wav_data, is_final),
                            daemon=True
                        ).start()
                return
            
            # Not currently playing - start first chunk
            filename, wav_data, is_final = self.play_queue.pop(0)
            self.currently_playing = (filename, is_final)
            self.is_processing = True
        
        self.logger.info(f"⚙️  Processing first chunk: {filename} (final={is_final})")
        
        # Upload and play in background thread
        threading.Thread(
            target=self._upload_and_play,
            args=(filename, wav_data, is_final),
            daemon=True
        ).start()
    
    def _pre_upload_chunk(self, filename: str, wav_data: bytes, is_final: bool):
        """Pre-upload next chunk while current chunk is playing.
        
        Args:
            filename: Name for the audio file on Misty
            wav_data: WAV format audio data
            is_final: Whether this is the last chunk
        """
        import base64
        
        try:
            upload_start = time.time()
            file_size_mb = len(wav_data) / (1024 * 1024)
            
            self.logger.info(f"📤 Pre-uploading {filename}: {file_size_mb:.2f} MB")
            
            # Encode to base64
            b64_data = base64.b64encode(wav_data).decode('utf-8')
            
            # Upload with extended timeout
            upload_response = self.misty.save_audio(
                fileName=filename,
                data=b64_data,
                immediatelyApply=False,
                overwriteExisting=True
            )
            
            upload_duration = time.time() - upload_start
            
            if upload_response.status_code == 200:
                self.logger.info(f"✅ Pre-uploaded {filename} in {upload_duration:.2f}s (ready to play!)")
                self.chunks_uploaded += 1
                self.uploaded_files.append(filename)  # Track for cleanup
            else:
                self.logger.error(f"❌ Pre-upload failed: {upload_response.status_code}")
                
        except Exception as e:
            self.logger.error(f"❌ Error pre-uploading chunk: {e}", exc_info=True)
        finally:
            with self.lock:
                self.currently_uploading = False
    
    def _upload_and_play(self, filename: str, wav_data: bytes, is_final: bool):
        """Upload audio chunk to Misty and play it (for first chunk only).
        
        Args:
            filename: Name for the audio file on Misty
            wav_data: WAV format audio data
            is_final: Whether this is the last chunk
        """
        import base64
        
        try:
            # Upload to Misty
            upload_start = time.time()
            file_size_mb = len(wav_data) / (1024 * 1024)
            
            self.logger.info(f"📤 Uploading first chunk {filename}: {file_size_mb:.2f} MB")
            
            # Encode to base64
            b64_data = base64.b64encode(wav_data).decode('utf-8')
            
            # Upload with extended timeout
            upload_response = self.misty.save_audio(
                fileName=filename,
                data=b64_data,
                immediatelyApply=False,
                overwriteExisting=True
            )
            
            upload_duration = time.time() - upload_start
            
            if upload_response.status_code == 200:
                self.logger.info(f"✅ Uploaded first chunk {filename} in {upload_duration:.2f}s")
                self.chunks_uploaded += 1
                self.uploaded_files.append(filename)  # Track for cleanup
                
                # Play the chunk (pass wav_data for duration calculation)
                self._play_chunk(filename, is_final, wav_data)
                
                # Start pre-uploading next chunk if available
                self._process_next()
            else:
                self.logger.error(f"❌ Upload failed: {upload_response.status_code}")
                # Skip this chunk and continue with next
                self._on_chunk_error(is_final)
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading chunk: {e}", exc_info=True)
            self._on_chunk_error(is_final)
    
    def _play_chunk(self, filename: str, is_final: bool, wav_data: bytes = None):
        """Play audio chunk on Misty.
        
        Args:
            filename: Name of audio file on Misty
            is_final: Whether this is the last chunk
            wav_data: Optional WAV data for duration calculation
        """
        try:
            self.logger.info(f"🔊 Playing {filename}")
            
            play_response = self.misty.play_audio(fileName=filename, volume=100)
            
            if play_response.status_code == 200:
                self.logger.info(f"✅ Playback started for {filename}")
                self.chunks_played += 1
                
                # Start continuous speaking animations on first chunk (non-blocking, parallel)
                if not self.animations_started and self.personality_manager:
                    try:
                        self.personality_manager.start_continuous_speaking_movements()
                        self.animations_started = True
                        self.logger.debug("🎭 Started continuous speaking animations")
                    except Exception as e:
                        self.logger.warning(f"Failed to start speaking animations: {e}")
                
                # CRITICAL FIX: AudioPlayComplete event may not fire reliably for short chunks
                # Calculate actual audio duration dynamically
                if wav_data and len(wav_data) > 44:  # WAV header is 44 bytes
                    # WAV format: 16kHz, 1 channel, 16-bit = 32000 bytes per second
                    audio_data_size = len(wav_data) - 44  # Subtract WAV header
                    duration_seconds = audio_data_size / (16000 * 2)  # 16kHz * 2 bytes per sample
                    fallback_duration = duration_seconds + 0.1  # Add minimal 200ms buffer
                    self.logger.debug(f"⏱️  Calculated duration: {duration_seconds:.2f}s, fallback: {fallback_duration:.2f}s")
                else:
                    # Fallback to default if wav_data not available
                    fallback_duration = 6.1  # 6s audio + 0.1s buffer
                
                def fallback_trigger():
                    self.logger.warning(f"⏰ AudioPlayComplete didn't fire for {filename}, using fallback")
                    self.on_playback_complete()
                
                # Store timer reference so we can cancel it if AudioPlayComplete fires
                self.fallback_timer = threading.Timer(fallback_duration, fallback_trigger)
                self.fallback_timer.daemon = True
                self.fallback_timer.start()
                
                self.logger.debug(f"⏱️  Set fallback timer: {fallback_duration:.2f}s")
            else:
                self.logger.error(f"❌ Playback failed: {play_response.status_code}")
                self._on_chunk_error(is_final)
                
        except Exception as e:
            self.logger.error(f"❌ Error playing chunk: {e}", exc_info=True)
            self._on_chunk_error(is_final)
    
    def _on_chunk_error(self, was_final: bool):
        """Handle chunk upload/playback error.
        
        Args:
            was_final: Whether the failed chunk was the last one
        """
        with self.lock:
            self.currently_playing = None
        
        if was_final:
            # Last chunk failed, complete anyway
            self.logger.warning("⚠️  Final chunk failed, completing response")
            self.is_processing = False
            self._complete_response()
        else:
            # Try next chunk
            self.logger.info("⏭️  Skipping failed chunk, processing next...")
            self._process_next()
    
    def on_playback_complete(self):
        """Called when AudioPlayComplete event fires OR fallback timer triggers.
        
        This is the key method that enables seamless chunk transitions.
        Now optimized to play pre-uploaded chunks immediately!
        """
        with self.lock:
            if not self.currently_playing:
                self.logger.debug("Playback complete called but no chunk was playing")
                return
            
            filename, was_final = self.currently_playing
            self.currently_playing = None
            
            # Cancel fallback timer if it's still running (event fired before timer)
            if self.fallback_timer:
                self.fallback_timer.cancel()
                self.fallback_timer = None
        
        self.logger.info(f"✅ Playback complete: {filename}")
        
        # Delete the played file from Misty to free up space (in background to avoid blocking)
        # Use threading to prevent blocking the next playback
        import threading
        threading.Thread(target=self._delete_file, args=(filename,), daemon=True).start()
        
        if was_final:
            # Final chunk played successfully
            self.logger.info("🎉 All chunks played successfully!")
            self.is_processing = False
            self._complete_response()
        else:
            # Play next chunk (should already be uploaded!)
            self.logger.info("⏭️  Playing next chunk...")
            self._play_next_chunk()
    
    def _play_next_chunk(self):
        """Play the next pre-uploaded chunk immediately (no upload delay!).
        
        This is called after a chunk finishes playing. The next chunk
        should already be uploaded and ready to play immediately.
        """
        with self.lock:
            if not self.play_queue:
                self.logger.warning("⚠️  No chunks in queue after playback complete")
                self.is_processing = False
                return
            
            # Pop the next chunk (should already be uploaded!)
            filename, wav_data, is_final = self.play_queue.pop(0)
            self.currently_playing = (filename, is_final)
        
        # Play immediately (already uploaded!) - pass wav_data for duration calculation
        self.logger.info(f"🎬 Playing pre-uploaded chunk: {filename}")
        self._play_chunk(filename, is_final, wav_data)
        
        # Start pre-uploading the NEXT chunk while this one plays
        self._process_next()
    
    def _complete_response(self):
        """Complete the response and return to idle state."""
        self.logger.info(f"📊 Response complete: {self.chunks_played}/{self.chunks_received} chunks played, {self.chunks_uploaded} chunks uploaded")
        
        # Stop continuous speaking animations if they were started
        if self.animations_started and self.personality_manager:
            try:
                self.personality_manager.stop_continuous_speaking_movements()
                self.animations_started = False
                self.logger.debug("🎭 Stopped continuous speaking animations")
            except Exception as e:
                self.logger.warning(f"Failed to stop speaking animations: {e}")
        
        # Clean up any remaining files
        self._cleanup_all_files()
        
        # Return LED to idle state (green)
        try:
            self.misty.change_led(*self.config.led.idle)
            self.logger.info("💚 Returned to idle state")
        except Exception as e:
            self.logger.error(f"Failed to change LED: {e}")
        
        # Reset statistics for next response
        self.chunks_received = 0
        self.chunks_played = 0
        self.chunks_uploaded = 0
        # Notify assistant that response finished so it can restart listening
        try:
            if getattr(self, "on_response_complete", None):
                self.logger.info("📞 Calling on_response_complete callback to resume assistant state...")
                self.on_response_complete()
                self.logger.info("✅ on_response_complete callback completed")
        except Exception as e:
            self.logger.error(f"❌ Error in on_response_complete callback: {e}", exc_info=True)
    
    def clear(self):
        """Clear the queue and reset state."""
        with self.lock:
            self.play_queue.clear()
            self.currently_playing = None
            self.is_processing = False
        
        # Stop animations if they were running
        if self.animations_started and self.personality_manager:
            try:
                self.personality_manager.stop_continuous_speaking_movements()
                self.animations_started = False
            except Exception as e:
                self.logger.warning(f"Failed to stop animations during clear: {e}")
        
        # Clean up all uploaded files
        self._cleanup_all_files()
        
        self.logger.info("🗑️  Queue cleared")
    
    def _delete_file(self, filename: str):
        """Delete an audio file from Misty to free up space.
        
        Args:
            filename: Name of the file to delete
        """
        try:
            # Use Misty's delete audio endpoint
            response = self.misty.delete_audio(filename)
            if response.status_code == 200:
                self.logger.debug(f"🗑️  Deleted {filename}")
                if filename in self.uploaded_files:
                    self.uploaded_files.remove(filename)
            else:
                self.logger.warning(f"Failed to delete {filename}: {response.status_code}")
        except Exception as e:
            self.logger.warning(f"Error deleting {filename}: {e}")
    
    def _cleanup_all_files(self):
        """Clean up all uploaded chunk files from Misty."""
        if not self.uploaded_files:
            return
        
        self.logger.info(f"🧹 Cleaning up {len(self.uploaded_files)} chunk files...")
        
        for filename in self.uploaded_files[:]:  # Copy list to avoid modification during iteration
            self._delete_file(filename)
        
        self.uploaded_files.clear()
        self.logger.info("✅ Cleanup complete")
    
    def get_status(self) -> dict:
        """Get current queue status.
        
        Returns:
            Dictionary with status information
        """
        with self.lock:
            return {
                'queue_size': len(self.play_queue),
                'is_playing': self.currently_playing is not None,
                'is_processing': self.is_processing,
                'chunks_received': self.chunks_received,
                'chunks_played': self.chunks_played
            }


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
        self.audio_queue = None  # AudioQueueManager for chunked playback
        self.state_manager = None
        self.greeting_manager = None
        self.personality_manager = None
        
        # Simple photo mapping: person name -> image file path
        self.person_photos = {
            "Ashish": "photos/ashish.jpg",
            "Vishva": "photos/vishva.png", 
            "Jane Smith": "photos/jane_smith.png",
            # Add more people here as needed
        }
        
        # Track uploaded photos to avoid re-uploading
        self.uploaded_photos = {}  # person_name -> misty_filename
        
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
            
            # Preload all configured photos for faster display
            self._preload_all_photos()
            
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
        
        # Ignore face recognition during active conversation mode
        if self.conversation_active:
            self.logger.debug("Ignoring face recognition during active conversation")
            return
        
        name = face_data.get("name", "Unknown")
        confidence = face_data.get("confidence", 0.0)
        
        self.logger.info(f"👤 Face recognized: {name} (confidence: {confidence:.2f})")
        
        # DIAGNOSTIC: Check if greeting will actually be delivered (cooldown check)
        will_greet = False
        if self.greeting_manager:
            will_greet = self.greeting_manager.should_greet(name)
            self.logger.info(f"🔍 DIAGNOSTIC - Will greet {name}? {will_greet}")
            if not will_greet:
                cooldown_status = self.greeting_manager.get_greeting_status(name)
                self.logger.info(f"   Cooldown remaining: {cooldown_status['cooldown_remaining']:.1f}s")
        
        # PAUSE AUDIO MONITOR during face greeting to prevent conflicts
        # BUT ONLY if we're actually going to deliver a greeting
        if self.audio_monitor and will_greet:
            self.logger.debug("⏸️  Pausing audio monitor for face greeting")
            self.audio_monitor.pause()
        elif self.audio_monitor and not will_greet:
            self.logger.debug("ℹ️  Skipping audio monitor pause - greeting won't be delivered (cooldown active)")
        
        # Record interaction (resets idle timer)
        if self.personality_manager:
            self.personality_manager.record_interaction()
        
        # Display person's photo if available in dictionary
        self._display_person_photo(name)
        
        # Task 2.2: Greet person with cooldown management
        greeting_delivered = False
        if self.greeting_manager:
            # Request greeting immediately to minimize latency
            import time
            recognized_at = time.time()
            greeting_delivered = self.greeting_manager.greet_person(name, recognized_at=recognized_at)
            
            # Run greeting animation asynchronously so it doesn't delay TTS (only if greeting was delivered)
            if greeting_delivered and self.personality_manager and self.config.personality.animations_during_speech:
                try:
                    threading.Thread(target=self.personality_manager.greeting_animation, daemon=True).start()
                except Exception:
                    # Non-fatal if animation thread fails
                    pass
            
            # RESUME AUDIO MONITOR after greeting completes (with delay for TTS)
            # BUT ONLY if we actually paused it (i.e., greeting was delivered)
            if greeting_delivered:
                # Schedule resume in background thread to avoid blocking
                def resume_after_greeting():
                    time.sleep(3.0)  # Wait for greeting to complete (adjust based on typical greeting length)
                    if self.audio_monitor:
                        self.logger.debug("▶️  Resuming audio monitor after face greeting")
                        self.audio_monitor.resume()
                        # Restart wake word detection if not in conversation mode
                        if not self.conversation_active:
                            self.audio_monitor.restart_wake_word_detection()
                
                threading.Thread(target=resume_after_greeting, daemon=True).start()
            else:
                self.logger.debug("ℹ️  Skipping audio monitor resume - it was never paused (cooldown active)")
    
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
        """Initialize realtime mode (voice → voice) with audio chunking."""
        self.logger.info("Setting up REALTIME mode (voice → voice)...")
        
        # Initialize AudioQueueManager for chunked playback (if chunking is enabled)
        if self.config.voice_assistant.audio_chunking_enabled:
            self.logger.info("  - Initializing Audio Queue Manager...")
            # Pass a callback so the assistant can handle conversation/idle transitions
            self.audio_queue = AudioQueueManager(
                self.misty,
                self.logger,
                self.config,
                on_response_complete=self._exit_speaking_state_after_playback,
                personality_manager=self.personality_manager
            )
            self.logger.info("    ✅ Audio queue initialized")
            
            # Register AudioPlayComplete event for seamless chunk transitions
            self.logger.info("  - Registering AudioPlayComplete event...")
            try:
                self.misty.register_event(
                    Events.AudioPlayComplete,
                    "ChunkPlaybackComplete",
                    keep_alive=True,
                    callback_function=lambda ws, msg: self.audio_queue.on_playback_complete()
                )
                self.logger.info("    ✅ AudioPlayComplete event registered")
            except Exception as e:
                self.logger.error(f"Failed to register AudioPlayComplete: {e}")
        else:
            self.audio_queue = None
            self.logger.info("  - Audio chunking disabled (single-file playback)")
        
        # Calculate chunk threshold from configuration (24kHz PCM16 = 48000 bytes/second)
        chunk_threshold_bytes = int(self.config.voice_assistant.chunk_duration_seconds * 48000)
        
        # Initialize Realtime API handler with system instructions
        self.logger.info("  - Connecting to OpenAI Realtime API...")
        self.realtime_handler = RealtimeHandler(
            api_key=self.config.openai.api_key,
            model="gpt-4o-realtime-preview-2024-10-01",
            on_transcript_received=self._on_realtime_transcript,
            on_user_transcript_received=self._on_user_transcript,
            on_audio_chunk_received=self._on_realtime_audio_chunk if self.config.voice_assistant.audio_chunking_enabled else None,
            chunk_threshold_bytes=chunk_threshold_bytes if self.config.voice_assistant.audio_chunking_enabled else None,
            system_instructions=UNO_BSAI_SYSTEM_PROMPT  # Set once at session level for fast responses!
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
        
        # Log configuration
        if self.config.voice_assistant.audio_chunking_enabled:
            chunk_mb = chunk_threshold_bytes / 1024 / 1024
            self.logger.info(f"  ⚡ Expected latency: ~4-6 seconds to first audio (60% improvement!)")
            self.logger.info(f"  🎵 Audio chunking enabled: {self.config.voice_assistant.chunk_duration_seconds}s chunks (~{chunk_mb:.2f}MB)")
            if self.config.voice_assistant.parallel_upload_enabled:
                self.logger.info(f"  🚀 Parallel upload enabled (pre-upload while playing)")
        else:
            self.logger.info(f"  ⏳ Single-file playback mode (higher latency, simpler)")
        self.logger.info("  🐛 Debug mode enabled for Realtime API")
    
    def _on_wake_word_detected(self, event_data: dict):
        """Callback when wake word is detected.
        
        Args:
            event_data: Event data from wake word detection
        """
        self.logger.info("🎤 Wake word detected!")
        
        # DIAGNOSTIC: Log current system state when wake word is detected
        self.logger.info(f"🔍 DIAGNOSTIC - System State at Wake Word:")
        self.logger.info(f"   - In screensaver: {self.personality_manager.in_screensaver if self.personality_manager else 'N/A'}")
        self.logger.info(f"   - Services stopped: {self.services_stopped}")
        self.logger.info(f"   - Conversation active: {self.conversation_active}")
        self.logger.info(f"   - Speaking lock: {self.speaking_lock}")
        
        # PAUSE FACE RECOGNITION during voice interaction to prevent conflicts
        if self.face_recognition_manager and self.face_recognition_manager.running:
            self.logger.debug("⏸️  Pausing face recognition for voice interaction")
            self.face_recognition_manager.stop()
        
        # Record interaction (resets idle timer, wakes from screensaver if needed)
        if self.personality_manager:
            self.logger.info("🔄 Recording interaction - will exit screensaver if active")
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
        
        # NOTE: Thinking animation disabled during speech capture to avoid blocking delays
        # The animation can cause 10-15 second delays when Misty's network is slow
        # We prioritize fast audio processing over visual feedback
        # if self.personality_manager and self.config.personality.animations_during_speech:
        #     self.personality_manager.thinking_animation()
        
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
        
        # Check for ending phrases in conversation mode
        if self.conversation_active and self._is_ending_phrase(transcription):
            self.logger.info(f"🚪 Ending phrase detected: '{transcription}' - exiting conversation mode")
            # End conversation after the response completes
            threading.Timer(0.5, self._end_conversation).start()
        
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
        pipeline_start = time.time()
        self.logger.info(f"⏱️  [PERF] Realtime pipeline started at {pipeline_start:.3f}")
        
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
        retrieval_start = time.time()
        self.logger.info(f"⏱️  [PERF] Audio retrieval started at {retrieval_start:.3f} (+{retrieval_start - pipeline_start:.3f}s)")
        
        import base64
        
        max_retries = 3
        retry_delay = 0.3  # Reduced from 0.5s to 0.3s for faster retries
        
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
                
                retrieval_end = time.time()
                self.logger.info(f"⏱️  [PERF] Audio retrieved: {len(audio_bytes)} bytes in {retrieval_end - retrieval_start:.3f}s")
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
        api_send_start = time.time()
        self.logger.info(f"⏱️  [PERF] Sending to Realtime API at {api_send_start:.3f} (+{api_send_start - retrieval_end:.3f}s)")
        try:
            self.realtime_handler.process_audio_file(audio_bytes)
            api_send_end = time.time()
            self.logger.info(f"⏱️  [PERF] Audio sent to Realtime API in {api_send_end - api_send_start:.3f}s, waiting for response...")
            # Response will come via callbacks (_on_realtime_transcript and _on_realtime_audio)
            
        except Exception as e:
            self.logger.error(f"❌ Failed to process with Realtime API: {e}")
            self._speak_and_reset("Sorry, I had trouble processing that.")
    
    def _on_realtime_transcript(self, transcript: str):
        """Callback when AI response transcript is received from Realtime API.
        
        Args:
            transcript: AI's response text from Realtime API
        """
        self.logger.info(f"📝 AI response transcript: '{transcript}'")
    
    def _on_user_transcript(self, transcript: str):
        """Callback when user input transcript is received from Realtime API.
        
        Args:
            transcript: User's input text from Realtime API
        """
        self.logger.info(f"👤 User input transcript: '{transcript}'")
        
        # Check for ending phrases in conversation mode
        if self.conversation_active and self._is_ending_phrase(transcript):
            self.logger.info(f"🚪 Ending phrase detected: '{transcript}' - exiting conversation mode")
            # End conversation after the response completes
            # Use a small delay to let the current response finish gracefully
            threading.Timer(0.5, self._end_conversation).start()
    
    def _on_realtime_audio_chunk(self, audio_bytes: bytes, is_final: bool, chunk_index: int):
        """Callback when audio chunk is received from Realtime API.
        
        This is the NEW chunked callback that enables low-latency playback.
        Chunks are sent to AudioQueueManager which handles upload/playback pipeline.
        
        Args:
            audio_bytes: Audio chunk from Realtime API (PCM16 format, 24kHz)
            is_final: Whether this is the last chunk of the response
            chunk_index: Index of this chunk in the response
        """
        chunk_received_time = time.time()
        self.logger.info(f"🎵 Audio chunk {chunk_index} received: {len(audio_bytes)} bytes (final={is_final})")
        
        # Log time to first audio chunk (critical latency metric)
        if chunk_index == 0:
            self.logger.info(f"⏱️  [PERF] First audio chunk received at {chunk_received_time:.3f} (TIME TO FIRST AUDIO)")
        
        if not self.audio_queue:
            self.logger.error("Audio queue not initialized!")
            return
        
        try:
            # Forward chunk to AudioQueueManager
            # It will handle: PCM→WAV conversion, downsampling, uploading, queueing, playing
            self.audio_queue.add_chunk(audio_bytes, is_final, chunk_index)
            
            # Set LED to speaking state on first chunk
            if chunk_index == 0:
                self.misty.change_led(*self.config.led.speaking)
                self.logger.info("🔊 First chunk received, playback starting soon!")
            
            # Return to idle LED after final chunk completes
            # (AudioQueueManager will handle this via _complete_response)
            if is_final:
                # Schedule LED return to idle after estimated playback time
                # This is handled by AudioQueueManager.on_playback_complete()
                pass
                
        except Exception as e:
            self.logger.error(f"❌ Error processing audio chunk {chunk_index}: {e}", exc_info=True)
            if is_final:
                # If final chunk fails, at least return to idle state
                self._speak_and_reset("Sorry, I had trouble playing the response.")
    
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
            
            # Start continuous speaking animations (non-blocking, parallel)
            if self.personality_manager:
                try:
                    self.personality_manager.start_continuous_speaking_movements()
                except Exception as e:
                    self.logger.warning(f"Failed to start speaking animations: {e}")
            
            play_response = self.misty.play_audio(fileName=filename, volume=100)
            if play_response.status_code == 200:
                self.logger.info("✅ Audio playback started")
                self._wait_for_audio_play_complete()
            else:
                self.logger.warning(f"Play audio returned status {play_response.status_code}")
        except Exception as e:
            self.logger.error(f"❌ Failed to play audio: {e}")
        finally:
            # Stop continuous speaking animations
            if self.personality_manager:
                try:
                    self.personality_manager.stop_continuous_speaking_movements()
                except Exception as e:
                    self.logger.warning(f"Failed to stop speaking animations: {e}")
            
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
        self.logger.info("🔄 Exiting speaking state...")
        
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
                    # OPTIMIZATION: Add small delay to allow Misty's audio system to stabilize
                    # before starting direct capture (avoids 503 errors and improves readiness)
                    time.sleep(0.15)  # 150ms delay for audio system readiness
                    self.audio_monitor.capture_speech_without_wake_word()
                except Exception:
                    pass
            # Keep face recognition paused during conversation mode
            self.logger.info("⏸️  Face recognition stays OFF during conversation mode")
        else:
            # Return to idle and wake word mode
            self.logger.info("🏠 Returning to wake word listening mode...")
            try:
                self.misty.change_led(*self.config.led.idle)
                self.logger.debug(f"💡 LED returned to idle: RGB{self.config.led.idle}")
            except Exception as e:
                self.logger.warning(f"Failed to reset LED: {e}")
            if self.audio_monitor:
                try:
                    self.audio_monitor.resume()
                    self.audio_monitor.restart_wake_word_detection()
                except Exception as e:
                    self.logger.error(f"Failed to restart audio monitor: {e}")
            
            # DO NOT RESUME FACE RECOGNITION - it should stay off after voice interaction starts
            # Face recognition only runs at startup before any "Hey Misty" is detected
            self.logger.info("👀 Face recognition remains OFF (only active at startup before voice interaction)")
        
        self.speaking_lock = False
        self.logger.info("🔓 Speaking lock released")

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
            self.logger.debug("_end_conversation called but conversation not active")
            return
        
        self.conversation_active = False
        self._cancel_conversation_timer()
        self.logger.info("🎬 Ending conversation mode - returning to greeting mode")
        
        # Return LED to idle
        try:
            self.misty.change_led(*self.config.led.idle)
        except Exception as e:
            self.logger.warning(f"Failed to reset LED: {e}")
        
        # Restart wake word detection for next "Hey Misty"
        if self.audio_monitor:
            self.logger.info("🔄 Restarting wake word detection...")
            self.audio_monitor.restart_wake_word_detection()
        
        # RESUME FACE RECOGNITION after conversation ends (return to greeting mode)
        self.logger.info("👀 Resuming face recognition after conversation ends...")
        if self.face_recognition_manager:
            self.logger.info(f"   Face recognition manager exists: running={self.face_recognition_manager.running}")
            self.logger.info(f"   Face recognition enabled in config: {self.config.face_recognition.enabled}")
            
            if not self.face_recognition_manager.running and self.config.face_recognition.enabled:
                self.logger.info("▶️  Starting face recognition (returning to greeting mode)...")
                try:
                    self.face_recognition_manager.start()
                    self.logger.info("✅ Face recognition resumed successfully - back to greeting mode!")
                except Exception as e:
                    self.logger.error(f"❌ Failed to resume face recognition: {e}", exc_info=True)
            elif self.face_recognition_manager.running:
                self.logger.info("ℹ️  Face recognition already running")
            else:
                self.logger.warning("⚠️  Face recognition not enabled in config")
        else:
            self.logger.warning("⚠️  Face recognition manager not initialized")
    
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
    
    def _is_ending_phrase(self, text: str) -> bool:
        """Check if the text contains an ending phrase that should exit conversation mode.
        
        Args:
            text: Text to check for ending phrases
            
        Returns:
            True if text contains an ending phrase, False otherwise
        """
        # Normalize text: lowercase and strip whitespace
        normalized = text.lower().strip()
        
        # Common ending phrases that indicate the user wants to end the conversation
        ending_phrases = [
            "thank you",
            "thanks",
            "thank you very much",
            "thanks a lot",
            "that's all",
            "that's it",
            "that'll be all",
            "goodbye",
            "good bye",
            "bye",
            "see you",
            "see ya",
            "have a good day",
            "have a nice day",
            "okay bye",
            "ok bye",
            "that's all i need",
            "that's all i needed",
            "nothing else",
            "no more questions",
            "i'm done",
            "i'm good",
            "that helps",
            "that's helpful",
            "got it thanks",
            "okay thanks",
            "ok thanks",
            "alright thanks",
            "perfect thanks",
            "great thanks",
        ]
        
        # Check if any ending phrase appears in the text
        for phrase in ending_phrases:
            if phrase in normalized:
                self.logger.debug(f"   Matched ending phrase: '{phrase}'")
                return True
        
        return False
    
    def _display_person_photo(self, person_name: str):
        """Display a person's photo on Misty's screen using simple dictionary lookup.
        
        Args:
            person_name: Name of the person as recognized by face recognition
        """
        try:
            # Check if we have a photo for this person in our dictionary
            if person_name not in self.person_photos:
                self.logger.debug(f"No photo configured for {person_name}")
                return
            
            photo_path = self.person_photos[person_name]
            self.logger.info(f"📸 Found photo for {person_name}: {photo_path}")
            
            # Check if photo is already uploaded to Misty
            if person_name not in self.uploaded_photos:
                # Upload photo to Misty
                if self._upload_person_photo(person_name, photo_path):
                    self.logger.info(f"✅ Photo uploaded for {person_name}")
                else:
                    self.logger.warning(f"❌ Failed to upload photo for {person_name}")
                    return
            
            # Display the photo
            misty_filename = self.uploaded_photos[person_name]
            self.logger.info(f"🖼️  Displaying photo: {misty_filename}")
            
            response = self.misty.display_image(
                fileName=misty_filename,
                alpha=1.0,  # Fully opaque
                layer="default"
            )
            
            if response.status_code == 200:
                self.logger.info(f"✅ Photo displayed for {person_name}")
                
                # Set timer to return to default expression after 3 seconds
                def return_to_default():
                    try:
                        self.misty.display_image(
                            fileName="e_DefaultContent.jpg",  # Default Misty eyes
                            alpha=1.0,
                            layer="default"
                        )
                        self.logger.debug("🔄 Returned to default eye expression")
                    except Exception as e:
                        self.logger.warning(f"Failed to return to default expression: {e}")
                
                # Schedule return to default after 3 seconds
                timer = threading.Timer(3.0, return_to_default)
                timer.daemon = True
                timer.start()
                
            else:
                self.logger.error(f"❌ Failed to display photo: {response.status_code}")
                
        except Exception as e:
            self.logger.error(f"❌ Error displaying photo for {person_name}: {e}", exc_info=True)
    
    def _upload_person_photo(self, person_name: str, photo_path: str) -> bool:
        """Upload a person's photo to Misty.
        
        Args:
            person_name: Name of the person
            photo_path: Path to the photo file
            
        Returns:
            True if upload successful, False otherwise
        """
        try:
            import os
            import base64
            
            # Check if file exists
            if not os.path.exists(photo_path):
                self.logger.error(f"Photo file not found: {photo_path}")
                return False
            
            # Read photo file
            with open(photo_path, 'rb') as f:
                photo_data = f.read()
            
            # Convert to base64
            base64_data = base64.b64encode(photo_data).decode('utf-8')
            
            # Generate filename for Misty (sanitize name)
            safe_name = person_name.lower().replace(" ", "_").replace(".", "")
            misty_filename = f"person_{safe_name}.jpg"
            
            self.logger.info(f"📤 Uploading {photo_path} as {misty_filename} ({len(photo_data)} bytes)")
            
            # Upload to Misty
            response = self.misty.save_image(
                fileName=misty_filename,
                data=base64_data,
                immediatelyApply=False,
                overwriteExisting=True
            )
            
            if response.status_code == 200:
                # Store the Misty filename for future use
                self.uploaded_photos[person_name] = misty_filename
                self.logger.info(f"✅ Photo uploaded successfully: {misty_filename}")
                return True
            else:
                self.logger.error(f"❌ Upload failed with status: {response.status_code}")
                return False
                
        except Exception as e:
            self.logger.error(f"❌ Error uploading photo: {e}", exc_info=True)
            return False
    
    def _preload_all_photos(self):
        """Preload all configured photos to Misty for faster display."""
        self.logger.info("🔄 Preloading person photos...")
        
        uploaded_count = 0
        for person_name, photo_path in self.person_photos.items():
            if self._upload_person_photo(person_name, photo_path):
                uploaded_count += 1
                self.logger.debug(f"  ✅ Preloaded: {person_name}")
            else:
                self.logger.warning(f"  ❌ Failed to preload: {person_name}")
        
        self.logger.info(f"✅ Preloaded {uploaded_count}/{len(self.person_photos)} photos")

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
            
            # DIAGNOSTIC: Check audio monitor state before screensaver
            if self.audio_monitor:
                status = self.audio_monitor.get_status()
                self.logger.info(f"🔍 DIAGNOSTIC - Audio Monitor State:")
                self.logger.info(f"   - Running: {status['running']}")
                self.logger.info(f"   - Paused: {status['paused']}")
                self.logger.info(f"   - Mode: {status['mode']}")
                
                # CRITICAL FIX: Ensure audio monitor is active and listening for wake word
                if status['paused']:
                    self.logger.warning("⚠️  Audio monitor was PAUSED - resuming for wake word detection")
                    self.audio_monitor.resume()
                
                # CRITICAL FIX: Restart wake word detection to ensure it's active in screensaver
                self.logger.info("🔄 Restarting wake word detection for screensaver mode...")
                self.audio_monitor.restart_wake_word_detection()
                self.logger.info("✅ Wake word detection restarted - 'Hey Misty' will wake from screensaver")
            else:
                self.logger.warning("⚠️  Audio monitor not initialized - wake word won't work!")
            
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
            
            # DIAGNOSTIC: Verify audio monitor is still working after wake
            if self.audio_monitor:
                status = self.audio_monitor.get_status()
                self.logger.info(f"🔍 DIAGNOSTIC - Audio Monitor State After Wake:")
                self.logger.info(f"   - Running: {status['running']}")
                self.logger.info(f"   - Paused: {status['paused']}")
                self.logger.info(f"   - Mode: {status['mode']}")
                
                # Ensure audio monitor is ready for next wake word
                if status['paused']:
                    self.logger.warning("⚠️  Audio monitor was paused after wake - resuming")
                    self.audio_monitor.resume()
                    self.audio_monitor.restart_wake_word_detection()
                
                self.logger.info("✅ Audio monitor verified - ready for 'Hey Misty'")
            else:
                self.logger.warning("⚠️  Audio monitor not initialized")
            
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

