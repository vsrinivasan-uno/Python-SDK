"""Configuration management for Misty Aicco Assistant.

This module handles all configuration settings including API keys, timeouts,
cooldowns, and other customizable parameters.
"""

import os
from typing import Optional
from dataclasses import dataclass
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


@dataclass
class MistyConfig:
    """Misty robot configuration."""
    ip_address: str
    
    
@dataclass
class OpenAIConfig:
    """OpenAI API configuration."""
    api_key: str
    model: str = "gpt-4o-mini"  # Default to cost-effective model
    whisper_model: str = "whisper-1"
    max_tokens: int = 512
    temperature: float = 0.7


@dataclass
class FaceRecognitionConfig:
    """Face recognition and greeting configuration."""
    enabled: bool = True
    greeting_cooldown_seconds: int = 300  # 5 minutes default
    greeting_templates: list = None
    
    def __post_init__(self):
        if self.greeting_templates is None:
            self.greeting_templates = [
                "Hello, {name}! Welcome back!",
                "Hi {name}! Great to see you again!",
                "Hey {name}! How are you doing?",
                "Welcome back, {name}!",
            ]


@dataclass
class VoiceAssistantConfig:
    """Voice assistant configuration."""
    enabled: bool = True
    wake_word_mode: str = "misty_builtin"  # "misty_builtin" or "openai_whisper"
    wake_word_custom: str = "Hey Aicco"  # Used only if mode is "openai_whisper"
    voice_mode: str = "traditional"  # "traditional" (STT→GPT→TTS) or "realtime" (voice→voice)
    silence_threshold_seconds: float = 2.0
    max_recording_seconds: int = 15  # Misty's max is 20 seconds (20000ms), default to 15s
    audio_chunk_seconds: float = 1.5
    conversation_mode: bool = True  # Enable continuous conversation (no wake word after first activation)
    conversation_timeout_seconds: float = 10.0  # Timeout for conversation mode (silence before ending)
    

@dataclass
class LEDConfig:
    """LED color configuration for different states."""
    idle: tuple = (0, 255, 0)  # Green
    greeting: tuple = (0, 255, 100)  # Green-cyan
    listening: tuple = (255, 0, 255)  # Purple
    processing: tuple = (0, 255, 255)  # Cyan
    speaking: tuple = (100, 255, 0)  # Yellow-green
    error: tuple = (255, 0, 0)  # Red


@dataclass
class LoggingConfig:
    """Logging configuration."""
    level: str = "INFO"  # DEBUG, INFO, WARNING, ERROR
    log_to_file: bool = True
    log_file_path: str = "logs/misty_assistant.log"
    max_log_size_mb: int = 10
    backup_count: int = 3


@dataclass
class PersonalityConfig:
    """Personality and animation configuration."""
    enabled: bool = True
    idle_timeout_seconds: float = 120.0  # 2 minutes before screensaver
    screensaver_enabled: bool = True
    battery_saving_enabled: bool = True  # Stop camera/audio when in screensaver
    animations_during_speech: bool = True  # Animate during conversations
    

class Config:
    """Main configuration class that aggregates all settings."""
    
    def __init__(self):
        """Initialize configuration from environment variables."""
        self.misty = self._load_misty_config()
        self.openai = self._load_openai_config()
        self.face_recognition = self._load_face_recognition_config()
        self.voice_assistant = self._load_voice_assistant_config()
        self.led = self._load_led_config()
        self.logging = self._load_logging_config()
        self.personality = self._load_personality_config()
        
        # Validate configuration
        self._validate()
    
    def _load_misty_config(self) -> MistyConfig:
        """Load Misty robot configuration."""
        ip = os.getenv("MISTY_IP_ADDRESS", "192.168.1.100")
        return MistyConfig(ip_address=ip)
    
    def _load_openai_config(self) -> OpenAIConfig:
        """Load OpenAI API configuration."""
        api_key = os.getenv("OPENAI_API_KEY", "")
        model = os.getenv("OPENAI_MODEL", "gpt-4o-mini")
        whisper_model = os.getenv("OPENAI_WHISPER_MODEL", "whisper-1")
        max_tokens = int(os.getenv("OPENAI_MAX_TOKENS", "512"))
        temperature = float(os.getenv("OPENAI_TEMPERATURE", "0.7"))
        
        return OpenAIConfig(
            api_key=api_key,
            model=model,
            whisper_model=whisper_model,
            max_tokens=max_tokens,
            temperature=temperature
        )
    
    def _load_face_recognition_config(self) -> FaceRecognitionConfig:
        """Load face recognition configuration."""
        enabled = os.getenv("FACE_RECOGNITION_ENABLED", "true").lower() == "true"
        cooldown = int(os.getenv("GREETING_COOLDOWN_SECONDS", "300"))
        
        return FaceRecognitionConfig(
            enabled=enabled,
            greeting_cooldown_seconds=cooldown
        )
    
    def _load_voice_assistant_config(self) -> VoiceAssistantConfig:
        """Load voice assistant configuration."""
        enabled = os.getenv("VOICE_ASSISTANT_ENABLED", "true").lower() == "true"
        wake_word_mode = os.getenv("WAKE_WORD_MODE", "misty_builtin")
        wake_word_custom = os.getenv("WAKE_WORD_CUSTOM", "Hey Aicco")
        voice_mode = os.getenv("VOICE_MODE", "traditional")
        silence_threshold = float(os.getenv("SILENCE_THRESHOLD_SECONDS", "2.0"))
        max_recording = int(os.getenv("MAX_RECORDING_SECONDS", "30"))
        chunk_seconds = float(os.getenv("AUDIO_CHUNK_SECONDS", "1.5"))
        conversation_mode = os.getenv("CONVERSATION_MODE", "true").lower() == "true"
        conversation_timeout = float(os.getenv("CONVERSATION_TIMEOUT_SECONDS", "10.0"))
        
        return VoiceAssistantConfig(
            enabled=enabled,
            wake_word_mode=wake_word_mode,
            wake_word_custom=wake_word_custom,
            voice_mode=voice_mode,
            silence_threshold_seconds=silence_threshold,
            max_recording_seconds=max_recording,
            audio_chunk_seconds=chunk_seconds,
            conversation_mode=conversation_mode,
            conversation_timeout_seconds=conversation_timeout
        )
    
    def _load_led_config(self) -> LEDConfig:
        """Load LED configuration."""
        # Allow customization via environment, but use defaults if not provided
        return LEDConfig()
    
    def _load_logging_config(self) -> LoggingConfig:
        """Load logging configuration."""
        level = os.getenv("LOG_LEVEL", "INFO").upper()
        log_to_file = os.getenv("LOG_TO_FILE", "true").lower() == "true"
        log_file = os.getenv("LOG_FILE_PATH", "logs/misty_assistant.log")
        max_size = int(os.getenv("MAX_LOG_SIZE_MB", "10"))
        backup_count = int(os.getenv("LOG_BACKUP_COUNT", "3"))
        
        # Create logs directory if it doesn't exist
        log_dir = os.path.dirname(log_file)
        if log_dir and not os.path.exists(log_dir):
            os.makedirs(log_dir, exist_ok=True)
        
        return LoggingConfig(
            level=level,
            log_to_file=log_to_file,
            log_file_path=log_file,
            max_log_size_mb=max_size,
            backup_count=backup_count
        )
    
    def _load_personality_config(self) -> PersonalityConfig:
        """Load personality and animation configuration."""
        enabled = os.getenv("PERSONALITY_ENABLED", "true").lower() == "true"
        idle_timeout = float(os.getenv("IDLE_TIMEOUT_SECONDS", "120.0"))
        screensaver = os.getenv("SCREENSAVER_ENABLED", "true").lower() == "true"
        battery_saving = os.getenv("BATTERY_SAVING_ENABLED", "true").lower() == "true"
        animations = os.getenv("ANIMATIONS_DURING_SPEECH", "true").lower() == "true"
        
        return PersonalityConfig(
            enabled=enabled,
            idle_timeout_seconds=idle_timeout,
            screensaver_enabled=screensaver,
            battery_saving_enabled=battery_saving,
            animations_during_speech=animations
        )
    
    def _validate(self):
        """Validate configuration values."""
        errors = []
        
        # Validate Misty IP
        if not self.misty.ip_address:
            errors.append("MISTY_IP_ADDRESS is required")
        
        # Validate OpenAI API key
        if not self.openai.api_key:
            errors.append("OPENAI_API_KEY is required")
        
        # Validate wake word mode
        valid_wake_word_modes = ["misty_builtin", "openai_whisper"]
        if self.voice_assistant.wake_word_mode not in valid_wake_word_modes:
            errors.append(f"WAKE_WORD_MODE must be one of {valid_wake_word_modes}")
        
        # Validate voice mode
        valid_voice_modes = ["traditional", "realtime"]
        if self.voice_assistant.voice_mode not in valid_voice_modes:
            errors.append(f"VOICE_MODE must be one of {valid_voice_modes}")
        
        # Validate numeric ranges
        
        if self.face_recognition.greeting_cooldown_seconds < 0:
            errors.append("GREETING_COOLDOWN_SECONDS must be non-negative")
        
        if self.voice_assistant.silence_threshold_seconds <= 0:
            errors.append("SILENCE_THRESHOLD_SECONDS must be positive")
        
        # Misty's API requires maxSpeechLength between 0.5 and 20 seconds
        if self.voice_assistant.max_recording_seconds < 0.5 or self.voice_assistant.max_recording_seconds > 20:
            errors.append("MAX_RECORDING_SECONDS must be between 0.5 and 20 (Misty API limit)")
        
        # Validate logging level
        valid_levels = ["DEBUG", "INFO", "WARNING", "ERROR", "CRITICAL"]
        if self.logging.level not in valid_levels:
            errors.append(f"LOG_LEVEL must be one of {valid_levels}")
        
        if errors:
            raise ValueError(f"Configuration validation failed:\n" + "\n".join(f"  - {e}" for e in errors))
    
    def print_config(self):
        """Print current configuration (masking sensitive data)."""
        print("=" * 60)
        print("Misty Aicco Assistant Configuration")
        print("=" * 60)
        print(f"\n[Misty Robot]")
        print(f"  IP Address: {self.misty.ip_address}")
        
        print(f"\n[OpenAI]")
        print(f"  API Key: {'*' * 8}{self.openai.api_key[-4:] if len(self.openai.api_key) > 4 else '****'}")
        print(f"  Model: {self.openai.model}")
        print(f"  Whisper Model: {self.openai.whisper_model}")
        print(f"  Max Tokens: {self.openai.max_tokens}")
        print(f"  Temperature: {self.openai.temperature}")
        
        print(f"\n[Face Recognition]")
        print(f"  Enabled: {self.face_recognition.enabled}")
        print(f"  Greeting Cooldown: {self.face_recognition.greeting_cooldown_seconds}s")
        print(f"  Greeting Templates: {len(self.face_recognition.greeting_templates)} templates")
        
        print(f"\n[Voice Assistant]")
        print(f"  Enabled: {self.voice_assistant.enabled}")
        print(f"  Voice Mode: {self.voice_assistant.voice_mode}")
        if self.voice_assistant.voice_mode == "traditional":
            print(f"    ↳ Pipeline: STT → GPT → TTS (slower ~5-8s, more stable)")
        else:
            print(f"    ↳ Pipeline: Voice → Voice (faster ~1-3s, realtime)")
        print(f"  Wake Word Mode: {self.voice_assistant.wake_word_mode}")
        if self.voice_assistant.wake_word_mode == "openai_whisper":
            print(f"  Custom Wake Word: '{self.voice_assistant.wake_word_custom}'")
        else:
            print(f"  Wake Word: 'Hey Misty' (Misty default)")
        print(f"  Silence Threshold: {self.voice_assistant.silence_threshold_seconds}s")
        print(f"  Max Recording: {self.voice_assistant.max_recording_seconds}s")
        print(f"  Conversation Mode: {self.voice_assistant.conversation_mode}")
        if self.voice_assistant.conversation_mode:
            print(f"    ↳ Continuous conversation enabled (no wake word after first question)")
            print(f"    ↳ Timeout: {self.voice_assistant.conversation_timeout_seconds}s of silence")
        
        print(f"\n[LED Colors]")
        print(f"  Idle: RGB{self.led.idle}")
        print(f"  Greeting: RGB{self.led.greeting}")
        print(f"  Listening: RGB{self.led.listening}")
        print(f"  Processing: RGB{self.led.processing}")
        print(f"  Speaking: RGB{self.led.speaking}")
        print(f"  Error: RGB{self.led.error}")
        
        print(f"\n[Logging]")
        print(f"  Level: {self.logging.level}")
        print(f"  Log to File: {self.logging.log_to_file}")
        if self.logging.log_to_file:
            print(f"  Log File: {self.logging.log_file_path}")
            print(f"  Max Size: {self.logging.max_log_size_mb}MB")
        
        print(f"\n[Personality & Animations]")
        print(f"  Enabled: {self.personality.enabled}")
        print(f"  Idle Timeout: {self.personality.idle_timeout_seconds}s")
        print(f"  Screensaver Mode: {self.personality.screensaver_enabled}")
        if self.personality.screensaver_enabled:
            print(f"    ↳ Activates after {self.personality.idle_timeout_seconds}s of inactivity")
            print(f"    ↳ Battery Saving: {self.personality.battery_saving_enabled}")
        print(f"  Speech Animations: {self.personality.animations_during_speech}")
        
        print("=" * 60)


# Global configuration instance (initialized when needed)
_config_instance: Optional[Config] = None


def get_config() -> Config:
    """Get or create the global configuration instance."""
    global _config_instance
    if _config_instance is None:
        _config_instance = Config()
    return _config_instance


def reload_config() -> Config:
    """Reload configuration from environment variables."""
    global _config_instance
    _config_instance = Config()
    return _config_instance

