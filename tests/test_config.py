#!/usr/bin/env python3
"""Test configuration loading for Misty Aicco Assistant.

This script tests that the configuration module works correctly.
"""

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

# Set up test environment variables
os.environ["MISTY_IP_ADDRESS"] = "192.168.1.100"
os.environ["OPENAI_API_KEY"] = "sk-test-key-for-validation"

try:
    from src.config import get_config
    
    print("Testing configuration loading...")
    print("-" * 60)
    
    # Load configuration
    config = get_config()
    print("✅ Configuration loaded successfully!")
    
    # Test configuration values
    print("\nTesting configuration access...")
    print(f"  Misty IP: {config.misty.ip_address}")
    print(f"  OpenAI Model: {config.openai.model}")
    print(f"  Face Recognition Enabled: {config.face_recognition.enabled}")
    print(f"  Voice Assistant Enabled: {config.voice_assistant.enabled}")
    print(f"  Wake Word Mode: {config.voice_assistant.wake_word_mode}")
    print(f"  Logging Level: {config.logging.level}")
    print("✅ All configuration values accessible!")
    
    # Print full configuration
    print("\n" + "=" * 60)
    config.print_config()
    
    print("\n✅ ALL TESTS PASSED!")
    print("\nConfiguration module is working correctly.")
    
except ImportError as e:
    print(f"❌ Import Error: {e}")
    print("\nMake sure all dependencies are installed:")
    print("  pip install -r requirements.txt")
    sys.exit(1)
    
except ValueError as e:
    print(f"❌ Configuration Validation Error: {e}")
    sys.exit(1)
    
except Exception as e:
    print(f"❌ Unexpected Error: {e}")
    import traceback
    traceback.print_exc()
    sys.exit(1)

