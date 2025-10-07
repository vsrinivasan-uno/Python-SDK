#!/usr/bin/env python3
"""Generate Pre-Cached Greetings for VIP Persons (Local Storage)

This utility generates high-quality greeting audio files using OpenAI's Realtime API
and saves them locally for instant streaming to Misty during face recognition.

Usage:
    python generate_vip_greetings.py

The script will:
1. Connect to OpenAI's Realtime API
2. Generate audio for each VIP greeting
3. Save the audio files locally in greeting_cache/ directory
4. Display progress and results

Environment Variables Required:
- OPENAI_API_KEY: Your OpenAI API key

Note: Misty connection is NOT required for generation, only for playback.
"""

import os
import sys
import time
import logging
from dotenv import load_dotenv

# Add project root to path
sys.path.append(os.path.dirname(__file__))

from src.handlers.realtime_handler import RealtimeHandler
from src.config import get_config

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VIPGreetingGenerator")


class VIPGreetingGenerator:
    """Generates and saves pre-cached greetings locally for VIP persons."""
    
    def __init__(self, cache_directory: str = "greeting_cache"):
        """Initialize the generator.
        
        Args:
            cache_directory: Local directory to save greeting audio files
        """
        load_dotenv()
        
        self.config = get_config()
        self.cache_directory = cache_directory
        self.realtime_handler = None
        self.current_audio_buffer = bytearray()
        self.audio_complete = False
        
        # Create cache directory if it doesn't exist
        os.makedirs(self.cache_directory, exist_ok=True)
        
        logger.info("=== VIP Greeting Generator (Local Storage) ===")
        logger.info(f"Cache Directory: {os.path.abspath(self.cache_directory)}")
        logger.info(f"VIP Persons: {len(self.config.face_recognition.vip_persons)}")
    
    def connect_realtime_api(self):
        """Connect to OpenAI Realtime API."""
        logger.info("Connecting to OpenAI Realtime API...")
        
        self.realtime_handler = RealtimeHandler(
            api_key=self.config.openai.api_key,
            model="gpt-4o-realtime-preview-2024-10-01",
            on_audio_chunk_received=self._on_audio_chunk,
            chunk_threshold_bytes=480000,  # 10 seconds @ 24kHz
            system_instructions="You are a greeting assistant. Speak the provided text exactly as written, with enthusiasm and warmth."
        )
        
        self.realtime_handler.connect()
        logger.info("✅ Connected to Realtime API")
    
    def _on_audio_chunk(self, audio_bytes: bytes, is_final: bool, chunk_index: int):
        """Callback for receiving audio chunks from Realtime API."""
        logger.info(f"📥 Received audio chunk {chunk_index}: {len(audio_bytes)} bytes (final={is_final})")
        self.current_audio_buffer.extend(audio_bytes)
        
        if is_final:
            self.audio_complete = True
            logger.info(f"✅ Complete audio received: {len(self.current_audio_buffer)} bytes total")
    
    def generate_greeting_audio(self, greeting_text: str, timeout: float = 30.0) -> bytes:
        """Generate audio for a greeting using Realtime API.
        
        Args:
            greeting_text: The greeting text to convert to speech
            timeout: Maximum time to wait for audio generation (seconds)
            
        Returns:
            PCM16 audio bytes at 24kHz
        """
        logger.info(f"📤 Generating audio for greeting...")
        logger.info(f"   Text length: {len(greeting_text)} characters")
        
        # Reset buffer
        self.current_audio_buffer = bytearray()
        self.audio_complete = False
        
        # Send greeting text to Realtime API
        message = {
            "type": "conversation.item.create",
            "item": {
                "type": "message",
                "role": "user",
                "content": [
                    {
                        "type": "input_text",
                        "text": greeting_text
                    }
                ]
            }
        }
        self.realtime_handler._send_json(message)
        
        # Request response
        self.realtime_handler.request_response()
        
        # Wait for audio to complete
        start_time = time.time()
        while not self.audio_complete and (time.time() - start_time) < timeout:
            time.sleep(0.1)
        
        if not self.audio_complete:
            logger.error(f"❌ Timeout waiting for audio generation ({timeout}s)")
            return None
        
        logger.info(f"✅ Audio generation complete: {len(self.current_audio_buffer)} bytes")
        return bytes(self.current_audio_buffer)
    
    def convert_pcm_to_wav(self, pcm_bytes: bytes, sample_rate: int = 24000) -> bytes:
        """Convert PCM16 audio to WAV format.
        
        Args:
            pcm_bytes: Raw PCM16 audio data
            sample_rate: Sample rate in Hz (default: 24000)
            
        Returns:
            WAV format audio bytes
        """
        import struct
        
        num_channels = 1
        bits_per_sample = 16
        byte_rate = sample_rate * num_channels * bits_per_sample // 8
        block_align = num_channels * bits_per_sample // 8
        data_size = len(pcm_bytes)
        
        # Build WAV header
        wav_header = struct.pack('<4sI4s4sIHHIIHH4sI',
            b'RIFF',
            36 + data_size,
            b'WAVE',
            b'fmt ',
            16,  # fmt chunk size
            1,   # PCM format
            num_channels,
            sample_rate,
            byte_rate,
            block_align,
            bits_per_sample,
            b'data',
            data_size
        )
        
        return wav_header + pcm_bytes
    
    def save_locally(self, person_name: str, wav_bytes: bytes) -> bool:
        """Save greeting audio to local storage.
        
        Args:
            person_name: Name of the person (used in filename)
            wav_bytes: WAV format audio data
            
        Returns:
            True if successful, False otherwise
        """
        # Create filename: greeting_{PersonName}.wav
        # Replace spaces with underscores for filename
        safe_name = person_name.replace(" ", "_")
        filename = f"greeting_{safe_name}.wav"
        filepath = os.path.join(self.cache_directory, filename)
        
        logger.info(f"💾 Saving to local storage: {filename}")
        logger.info(f"   File size: {len(wav_bytes) / 1024:.2f} KB")
        logger.info(f"   Full path: {os.path.abspath(filepath)}")
        
        try:
            # Save to file
            with open(filepath, 'wb') as f:
                f.write(wav_bytes)
            
            logger.info(f"✅ Successfully saved: {filename}")
            return True
                
        except Exception as e:
            logger.error(f"❌ Save error: {e}")
            return False
    
    def generate_all_vip_greetings(self):
        """Generate and save greetings locally for all VIP persons."""
        vip_persons = self.config.face_recognition.vip_persons
        
        if not vip_persons:
            logger.warning("⚠️ No VIP persons configured in config")
            return
        
        logger.info(f"\n🎯 Generating {len(vip_persons)} VIP greetings...")
        logger.info("=" * 60)
        
        success_count = 0
        failed_count = 0
        
        for i, (person_name, greeting_text) in enumerate(vip_persons.items(), 1):
            logger.info(f"\n[{i}/{len(vip_persons)}] Processing: {person_name}")
            logger.info("-" * 60)
            
            try:
                # Generate audio
                pcm_audio = self.generate_greeting_audio(greeting_text)
                if not pcm_audio:
                    logger.error(f"❌ Failed to generate audio for {person_name}")
                    failed_count += 1
                    continue
                
                # Convert to WAV
                wav_audio = self.convert_pcm_to_wav(pcm_audio)
                logger.info(f"📦 Converted to WAV: {len(wav_audio) / 1024:.2f} KB")
                
                # Save locally
                if self.save_locally(person_name, wav_audio):
                    success_count += 1
                else:
                    failed_count += 1
                
                # Brief delay between generations
                if i < len(vip_persons):
                    time.sleep(2)
                    
            except Exception as e:
                logger.error(f"❌ Error processing {person_name}: {e}")
                failed_count += 1
        
        logger.info("\n" + "=" * 60)
        logger.info("📊 Generation Summary:")
        logger.info(f"   ✅ Successful: {success_count}")
        logger.info(f"   ❌ Failed: {failed_count}")
        logger.info(f"   📦 Total: {len(vip_persons)}")
        logger.info(f"   📂 Saved to: {os.path.abspath(self.cache_directory)}")
        logger.info("=" * 60)
    
    def disconnect(self):
        """Disconnect from Realtime API."""
        if self.realtime_handler:
            self.realtime_handler.disconnect()
            logger.info("✅ Disconnected from Realtime API")


def main():
    """Main entry point."""
    generator = VIPGreetingGenerator()
    
    try:
        # Connect to Realtime API
        generator.connect_realtime_api()
        
        # Generate all VIP greetings
        generator.generate_all_vip_greetings()
        
        logger.info("\n✅ Generation complete!")
        logger.info("💡 Greetings saved locally in: greeting_cache/")
        logger.info("💡 The greeting manager will automatically load and stream them to Misty")
        logger.info("💡 No upload needed - instant playback on face recognition!")
        
    except KeyboardInterrupt:
        logger.info("\n⚠️ Generation interrupted by user")
    except Exception as e:
        logger.error(f"\n❌ Fatal error: {e}", exc_info=True)
    finally:
        # Cleanup
        generator.disconnect()


if __name__ == "__main__":
    main()