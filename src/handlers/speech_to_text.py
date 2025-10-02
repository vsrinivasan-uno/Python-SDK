"""Speech-to-Text Handler for Misty Aicco Assistant.

Handles audio transcription using OpenAI Whisper API.
"""

import logging
import base64
import io
from typing import Optional
from openai import OpenAI
from mistyPy.Robot import Robot


class SpeechToTextHandler:
    """Handles speech-to-text transcription using OpenAI Whisper.
    
    This class handles:
    - Retrieving audio files from Misty
    - Converting audio format for Whisper API
    - Sending to OpenAI Whisper for transcription
    - Error handling and retries
    """
    
    def __init__(self, misty: Robot, openai_api_key: str, whisper_model: str = "whisper-1"):
        """Initialize the Speech-to-Text Handler.
        
        Args:
            misty: Misty robot instance
            openai_api_key: OpenAI API key for Whisper
            whisper_model: Whisper model to use (default: "whisper-1")
        """
        self.misty = misty
        self.whisper_model = whisper_model
        self.logger = logging.getLogger("SpeechToText")
        
        # Initialize OpenAI client
        try:
            self.client = OpenAI(api_key=openai_api_key)
            self.logger.info("OpenAI client initialized successfully")
        except Exception as e:
            self.logger.error(f"Failed to initialize OpenAI client: {e}")
            raise
    
    def transcribe_audio(self, audio_filename: str, language: str = "en") -> Optional[str]:
        """Transcribe audio file using OpenAI Whisper.
        
        Args:
            audio_filename: Name of the audio file stored on Misty
            language: Language code for transcription (default: "en")
        
        Returns:
            Transcribed text, or None if transcription failed
        """
        try:
            self.logger.info(f"📝 Starting transcription for: {audio_filename}")
            
            # Step 1: Retrieve audio file from Misty
            self.logger.debug("Retrieving audio file from Misty...")
            audio_data = self._get_audio_from_misty(audio_filename)
            
            if audio_data is None:
                self.logger.error("Failed to retrieve audio from Misty")
                return None
            
            # Step 2: Send to OpenAI Whisper for transcription
            self.logger.debug(f"Sending audio to OpenAI Whisper ({self.whisper_model})...")
            transcription = self._transcribe_with_whisper(audio_data, language)
            
            if transcription:
                self.logger.info(f"✅ Transcription successful: '{transcription}'")
            else:
                self.logger.error("Transcription failed")
            
            return transcription
            
        except Exception as e:
            self.logger.error(f"Error during transcription: {e}", exc_info=True)
            return None
    
    def _get_audio_from_misty(self, filename: str) -> Optional[bytes]:
        """Retrieve audio file from Misty robot.
        
        Args:
            filename: Name of the audio file on Misty
        
        Returns:
            Audio data as bytes, or None if retrieval failed
        """
        try:
            # Get audio file from Misty (base64 encoded)
            response = self.misty.get_audio_file(fileName=filename, base64=True)
            
            if response.status_code != 200:
                self.logger.error(f"Failed to get audio file: {response.status_code}")
                self.logger.error(f"Response: {response.text}")
                return None
            
            # Parse response
            data = response.json()
            
            if not data.get("result"):
                self.logger.error("No result in audio file response")
                return None
            
            result = data["result"]
            
            # Get base64 encoded audio
            base64_audio = result.get("base64", None)
            
            if not base64_audio:
                self.logger.error("No base64 audio data in response")
                return None
            
            # Decode base64 to bytes
            audio_bytes = base64.b64decode(base64_audio)
            self.logger.info(f"✅ Retrieved audio file: {len(audio_bytes)} bytes")
            
            return audio_bytes
            
        except Exception as e:
            self.logger.error(f"Error retrieving audio from Misty: {e}", exc_info=True)
            return None
    
    def _transcribe_with_whisper(self, audio_data: bytes, language: str = "en") -> Optional[str]:
        """Transcribe audio using OpenAI Whisper API.
        
        Args:
            audio_data: Audio data as bytes
            language: Language code for transcription
        
        Returns:
            Transcribed text, or None if transcription failed
        """
        try:
            # Create a file-like object from bytes
            # Misty records audio as .wav files
            audio_file = io.BytesIO(audio_data)
            audio_file.name = "audio.wav"  # Whisper needs a filename with extension
            
            # Call OpenAI Whisper API
            self.logger.debug("Calling OpenAI Whisper API...")
            
            response = self.client.audio.transcriptions.create(
                model=self.whisper_model,
                file=audio_file,
                language=language,
                response_format="text"
            )
            
            # Extract transcription text
            transcription = response.strip() if response else None
            
            if transcription:
                self.logger.debug(f"Raw transcription: '{transcription}'")
                return transcription
            else:
                self.logger.warning("Empty transcription received")
                return None
            
        except Exception as e:
            self.logger.error(f"Error calling Whisper API: {e}", exc_info=True)
            return None
    
    def transcribe_with_retry(self, audio_filename: str, max_retries: int = 2) -> Optional[str]:
        """Transcribe audio with retry logic.
        
        Args:
            audio_filename: Name of the audio file stored on Misty
            max_retries: Maximum number of retry attempts (default: 2)
        
        Returns:
            Transcribed text, or None if all attempts failed
        """
        for attempt in range(max_retries + 1):
            if attempt > 0:
                self.logger.info(f"Retry attempt {attempt}/{max_retries}...")
            
            result = self.transcribe_audio(audio_filename)
            
            if result:
                return result
            
            if attempt < max_retries:
                self.logger.warning(f"Transcription failed, retrying...")
        
        self.logger.error(f"Transcription failed after {max_retries + 1} attempts")
        return None

