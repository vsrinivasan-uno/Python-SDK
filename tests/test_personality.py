#!/usr/bin/env python3
"""Test script for Personality Manager

Tests dynamic animations, eye expressions, and screensaver mode.

Run this script to verify:
1. Eye expressions work
2. Animations work (head, arms)
3. Screensaver mode activates
4. Battery saving works (stops/starts services)

Author: Misty Robotics
Date: October 2, 2025
"""

import sys
import os
import time

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mistyPy.Robot import Robot
from src.config import get_config
from src.core.personality_manager import PersonalityManager


def test_expressions(personality: PersonalityManager):
    """Test different eye expressions."""
    print("\n" + "=" * 60)
    print("TEST 1: Eye Expressions")
    print("=" * 60)
    
    expressions = ["joy", "love", "amazement", "surprise", "default"]
    
    for expr in expressions:
        print(f"  Showing expression: {expr}")
        personality.show_expression(expr)
        time.sleep(2)
    
    print("✅ Expression test complete!")


def test_animations(personality: PersonalityManager):
    """Test conversation animations."""
    print("\n" + "=" * 60)
    print("TEST 2: Conversation Animations")
    print("=" * 60)
    
    print("  Testing listening animation...")
    personality.listening_animation()
    time.sleep(2)
    
    print("  Testing thinking animation...")
    personality.thinking_animation()
    time.sleep(2)
    
    print("  Testing speaking animation...")
    personality.speaking_animation()
    time.sleep(2)
    
    print("  Testing greeting animation...")
    personality.greeting_animation()
    time.sleep(3)
    
    print("  Resetting to neutral...")
    personality.reset_to_neutral()
    
    print("✅ Animation test complete!")


def test_screensaver(personality: PersonalityManager):
    """Test screensaver mode (shortened for testing)."""
    print("\n" + "=" * 60)
    print("TEST 3: Screensaver Mode")
    print("=" * 60)
    
    # Temporarily reduce idle timeout for testing
    original_timeout = personality.idle_timeout_seconds
    personality.idle_timeout_seconds = 10  # 10 seconds for testing
    
    print(f"  Idle timeout set to {personality.idle_timeout_seconds}s for testing")
    print("  Waiting for screensaver to activate...")
    print("  (This would normally take 2 minutes)")
    
    # Wait for screensaver to activate
    time.sleep(12)
    
    if personality.in_screensaver:
        print("✅ Screensaver activated!")
        print("  Watching dance moves for 10 seconds...")
        time.sleep(10)
        
        print("\n  Simulating interaction (should exit screensaver)...")
        personality.record_interaction()
        time.sleep(2)
        
        if not personality.in_screensaver:
            print("✅ Screensaver exited successfully!")
        else:
            print("❌ Screensaver didn't exit")
    else:
        print("❌ Screensaver didn't activate")
    
    # Restore original timeout
    personality.idle_timeout_seconds = original_timeout


def test_dance_moves(personality: PersonalityManager):
    """Test individual dance moves."""
    print("\n" + "=" * 60)
    print("TEST 4: Dance Moves")
    print("=" * 60)
    
    print("  Dance Move 1: Head shake with arm waves")
    personality._dance_move_1()
    time.sleep(2)
    
    print("  Dance Move 2: Spin 360")
    personality._dance_move_2()
    time.sleep(3)
    
    print("  Dance Move 3: Arm wave sequence")
    personality._dance_move_3()
    time.sleep(3)
    
    print("  Dance Move 4: Look around curiously")
    personality._dance_move_4()
    time.sleep(2)
    
    print("  Resetting to neutral...")
    personality.reset_to_neutral()
    
    print("✅ Dance moves test complete!")


def main():
    """Main test function."""
    print("=" * 60)
    print("Personality Manager - Test Script")
    print("=" * 60)
    
    # Load configuration
    config = get_config()
    
    print(f"\n📡 Connecting to Misty at {config.misty.ip_address}...")
    misty = Robot(config.misty.ip_address)
    print("✅ Connected to Misty")
    
    # Create personality manager
    print("\n🎭 Creating Personality Manager...")
    personality = PersonalityManager(
        misty=misty,
        idle_timeout_seconds=config.personality.idle_timeout_seconds,
        screensaver_enabled=config.personality.screensaver_enabled
    )
    print("✅ Personality Manager created")
    
    # Start personality manager
    print("\n🚀 Starting Personality Manager...")
    personality.start()
    print("✅ Personality Manager started")
    
    try:
        # Run tests
        test_expressions(personality)
        test_animations(personality)
        test_dance_moves(personality)
        
        # Ask user if they want to test screensaver
        print("\n" + "=" * 60)
        print("SCREENSAVER TEST (Optional)")
        print("=" * 60)
        print("This test will wait 10 seconds for screensaver to activate.")
        response = input("Run screensaver test? (y/n): ")
        
        if response.lower() == 'y':
            test_screensaver(personality)
        else:
            print("Skipping screensaver test")
        
        print("\n" + "=" * 60)
        print("✅ ALL TESTS COMPLETE!")
        print("=" * 60)
        
        print("\nManual Verification Checklist:")
        print("  [ ] Eye expressions changed correctly")
        print("  [ ] Head moved during animations")
        print("  [ ] Arms moved during animations")
        print("  [ ] Dance moves looked smooth")
        print("  [ ] Screensaver activated when idle (if tested)")
        print("  [ ] Misty returned to neutral pose")
        
        print("\n💡 TIP: Test with full assistant (misty_aicco_assistant.py) to verify:")
        print("  - Animations during actual conversations")
        print("  - Screensaver after 2 minutes of no interaction")
        print("  - Battery saving (camera/audio turn off)")
        print("  - Wake from screensaver with 'Hey Misty'")
        
    except KeyboardInterrupt:
        print("\n\n⚠️  Test interrupted by user")
    
    except Exception as e:
        print(f"\n❌ Error during tests: {e}")
        import traceback
        traceback.print_exc()
    
    finally:
        # Cleanup
        print("\n🛑 Stopping Personality Manager...")
        personality.stop()
        print("✅ Cleanup complete")
        
        # Reset Misty to neutral
        print("\n🔄 Resetting Misty to neutral pose...")
        misty.move_head(pitch=0, roll=0, yaw=0, velocity=50)
        misty.move_arms(leftArmPosition=0, rightArmPosition=0, duration=0.5)
        misty.display_image("e_DefaultContent.jpg")
        misty.change_led(0, 255, 0)  # Green
        print("✅ Misty reset to neutral")


if __name__ == "__main__":
    main()

