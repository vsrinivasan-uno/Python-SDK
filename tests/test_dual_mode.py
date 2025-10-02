#!/usr/bin/env python3
"""Test script for dual-mode voice assistant configuration.

This script verifies that both traditional and realtime modes
can be configured and initialized properly.

Author: Misty Robotics
Date: October 2, 2025
"""

import os
import sys

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import get_config, reload_config


def test_traditional_mode():
    """Test traditional mode configuration."""
    print("\n" + "=" * 60)
    print("Testing TRADITIONAL Mode (STT → GPT → TTS)")
    print("=" * 60)
    
    # Set environment for traditional mode
    os.environ["VOICE_MODE"] = "traditional"
    os.environ["WAKE_WORD_MODE"] = "misty_builtin"
    
    try:
        config = reload_config()
        
        assert config.voice_assistant.voice_mode == "traditional", \
            "Voice mode should be traditional"
        
        print("\n✅ Traditional mode configuration loaded successfully!")
        print(f"   Voice Mode: {config.voice_assistant.voice_mode}")
        print(f"   Pipeline: STT → GPT → TTS")
        print(f"   Expected Latency: ~5-8 seconds")
        print(f"   Wake Word: {'Hey Misty' if config.voice_assistant.wake_word_mode == 'misty_builtin' else config.voice_assistant.wake_word_custom}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Traditional mode test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_realtime_mode():
    """Test realtime mode configuration."""
    print("\n" + "=" * 60)
    print("Testing REALTIME Mode (Voice → Voice)")
    print("=" * 60)
    
    # Set environment for realtime mode
    os.environ["VOICE_MODE"] = "realtime"
    os.environ["WAKE_WORD_MODE"] = "misty_builtin"
    
    try:
        config = reload_config()
        
        assert config.voice_assistant.voice_mode == "realtime", \
            "Voice mode should be realtime"
        
        print("\n✅ Realtime mode configuration loaded successfully!")
        print(f"   Voice Mode: {config.voice_assistant.voice_mode}")
        print(f"   Pipeline: Voice → Voice (direct)")
        print(f"   Expected Latency: ~1-3 seconds")
        print(f"   Model: gpt-4o-realtime-preview")
        print(f"   Wake Word: {'Hey Misty' if config.voice_assistant.wake_word_mode == 'misty_builtin' else config.voice_assistant.wake_word_custom}")
        
        return True
        
    except Exception as e:
        print(f"\n❌ Realtime mode test failed: {e}")
        import traceback
        traceback.print_exc()
        return False


def test_invalid_mode():
    """Test that invalid mode is rejected."""
    print("\n" + "=" * 60)
    print("Testing INVALID Mode Rejection")
    print("=" * 60)
    
    # Set environment for invalid mode
    os.environ["VOICE_MODE"] = "invalid_mode"
    
    try:
        config = reload_config()
        print("\n❌ Invalid mode test failed - should have raised error!")
        return False
        
    except ValueError as e:
        print(f"\n✅ Invalid mode correctly rejected!")
        print(f"   Error: {e}")
        return True
        
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        return False


def print_comparison():
    """Print a comparison of the two modes."""
    print("\n" + "=" * 60)
    print("VOICE MODE COMPARISON")
    print("=" * 60)
    
    print("\nTRADITIONAL MODE (STT → GPT → TTS):")
    print("  ✅ More stable and mature")
    print("  ✅ Works with all GPT models (gpt-4, gpt-4o, gpt-4o-mini)")
    print("  ✅ Easier to debug (can see text at each step)")
    print("  ✅ Better for complex conversations")
    print("  ❌ Higher latency (~5-8 seconds)")
    print("  ❌ More API calls (Whisper + Chat)")
    
    print("\nREALTIME MODE (Voice → Voice):")
    print("  ✅ Much faster (~1-3 seconds)")
    print("  ✅ More natural conversation flow")
    print("  ✅ Lower cost (single API call)")
    print("  ✅ Streaming audio responses")
    print("  ⚠️  Only works with gpt-4o-realtime-preview")
    print("  ⚠️  Newer technology (less mature)")
    print("  ⚠️  Harder to debug (audio-only)")
    
    print("\nRECOMMENDATION:")
    print("  • Use TRADITIONAL for: Stability, debugging, complex conversations")
    print("  • Use REALTIME for: Speed, natural feel, simple Q&A")
    
    print("\nTO SWITCH MODES:")
    print("  Edit your .env file and change:")
    print("    VOICE_MODE=traditional   (for traditional mode)")
    print("    VOICE_MODE=realtime      (for realtime mode)")


def main():
    """Run all tests."""
    print("\n" + "=" * 70)
    print("DUAL-MODE VOICE ASSISTANT CONFIGURATION TEST")
    print("=" * 70)
    
    results = []
    
    # Test traditional mode
    results.append(("Traditional Mode", test_traditional_mode()))
    
    # Test realtime mode
    results.append(("Realtime Mode", test_realtime_mode()))
    
    # Test invalid mode
    results.append(("Invalid Mode Rejection", test_invalid_mode()))
    
    # Print comparison
    print_comparison()
    
    # Print summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)
    
    for name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"  {status}: {name}")
    
    all_passed = all(result for _, result in results)
    
    if all_passed:
        print("\n✅ ALL TESTS PASSED!")
        print("\nYou can now switch between modes by editing VOICE_MODE in your .env file.")
        print("  - Set VOICE_MODE=traditional for slower but more stable responses")
        print("  - Set VOICE_MODE=realtime for faster, more natural conversations")
        return 0
    else:
        print("\n❌ SOME TESTS FAILED")
        return 1


if __name__ == "__main__":
    sys.exit(main())

