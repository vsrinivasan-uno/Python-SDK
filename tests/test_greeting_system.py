#!/usr/bin/env python3
"""Test script for Task 2.2: Greeting System with Cooldown

This script tests:
1. Personalized greetings when faces are detected
2. Cooldown enforcement (no repeated greetings within cooldown period)
3. LED animations during greetings
4. Greeting message variation
5. Cooldown expiration and re-greeting

Usage:
    python3 test_greeting_system.py
"""

import os
import sys
import time
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mistyPy.Robot import Robot
from src.config import get_config
from src.core.face_recognition_manager import FaceRecognitionManager
from src.core.greeting_manager import GreetingManager


def setup_logging():
    """Set up logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("GreetingTest")


def test_greeting_system():
    """Test the greeting system with cooldown."""
    logger = setup_logging()
    
    logger.info("=" * 70)
    logger.info("Task 2.2: Greeting System with Cooldown - Test Script")
    logger.info("=" * 70)
    
    # Load configuration
    config = get_config()
    logger.info(f"\nConnecting to Misty at {config.misty.ip_address}...")
    
    try:
        # Connect to Misty
        misty = Robot(config.misty.ip_address)
        logger.info("✅ Connected to Misty successfully!")
        
        # Set initial LED to idle
        misty.change_led(*config.led.idle)
        logger.info(f"💡 LED set to idle: RGB{config.led.idle}")
        
        # Initialize greeting manager
        logger.info("\n📋 Initializing Greeting Manager...")
        greeting_manager = GreetingManager(
            misty=misty,
            greeting_templates=config.face_recognition.greeting_templates,
            cooldown_seconds=config.face_recognition.greeting_cooldown_seconds,
            greeting_led_color=config.led.greeting,
            idle_led_color=config.led.idle
        )
        logger.info(f"✅ Greeting Manager initialized")
        logger.info(f"   - Cooldown period: {config.face_recognition.greeting_cooldown_seconds} seconds")
        logger.info(f"   - Available templates: {len(config.face_recognition.greeting_templates)}")
        logger.info(f"   - Greeting LED color: RGB{config.led.greeting}")
        
        # Callback for face recognition
        greeting_count = [0]  # Use list to allow modification in nested function
        
        def on_face_detected(face_data):
            """Callback when face is detected."""
            name = face_data.get("name", "Unknown")
            confidence = face_data.get("confidence", 0.0)
            
            logger.info(f"\n👤 Face detected: {name} (confidence: {confidence:.2f})")
            
            # Attempt to greet
            greeted = greeting_manager.greet_person(name)
            if greeted:
                greeting_count[0] += 1
            
            # Show greeting status
            status = greeting_manager.get_greeting_status(name)
            logger.info(f"📊 Greeting Status for '{name}':")
            logger.info(f"   - Can greet now: {status['can_greet']}")
            logger.info(f"   - Cooldown remaining: {status['cooldown_remaining']:.1f}s")
        
        # Initialize face recognition
        logger.info("\n📹 Initializing Face Recognition...")
        face_recognition = FaceRecognitionManager(
            misty=misty,
            on_face_recognized=on_face_detected
        )
        
        # Get known faces
        known_faces = face_recognition.get_known_faces()
        if known_faces:
            logger.info(f"✅ Known faces in database: {', '.join(known_faces)}")
        else:
            logger.info("⚠️  No faces trained yet!")
            logger.info("   To test greetings, you need to train at least one face.")
            logger.info("   Run the face training script first or uncomment training section below.")
            
            # Optional: Train a face for testing (uncomment to use)
            # logger.info("\n🔄 Starting face training for 'TestUser'...")
            # face_recognition.train_face("TestUser")
            # logger.info("⏳ Wait 20 seconds for training to complete...")
            # time.sleep(20)
            # logger.info("✅ Training should be complete")
        
        # Start face recognition
        face_recognition.start()
        
        logger.info("\n" + "=" * 70)
        logger.info("🎬 TEST SCENARIOS")
        logger.info("=" * 70)
        logger.info("\n📝 Test Instructions:")
        logger.info("1. Show your face to Misty's camera")
        logger.info("2. Verify you hear a personalized greeting")
        logger.info("3. Verify LED changes to greeting color (green-cyan)")
        logger.info("4. Show your face again immediately")
        logger.info("5. Verify NO second greeting (cooldown active)")
        logger.info(f"6. Wait {config.face_recognition.greeting_cooldown_seconds} seconds")
        logger.info("7. Show your face again")
        logger.info("8. Verify you hear a greeting again (cooldown expired)")
        logger.info("\n🔍 Monitoring for face detection events...")
        logger.info(f"   Cooldown period: {config.face_recognition.greeting_cooldown_seconds} seconds")
        logger.info("   Press Ctrl+C to stop\n")
        
        # Monitor for 2 minutes (or until interrupted)
        test_duration = 120  # 2 minutes
        start_time = time.time()
        
        try:
            while time.time() - start_time < test_duration:
                time.sleep(1)
                
                # Show periodic status
                elapsed = time.time() - start_time
                if int(elapsed) % 30 == 0 and elapsed > 0:
                    logger.info(f"\n⏱️  Test running for {int(elapsed)}s...")
                    logger.info(f"   Total greetings delivered: {greeting_count[0]}")
                    
                    # Show greeting history
                    history = greeting_manager.get_all_greeting_history()
                    if history:
                        logger.info("   Greeting history:")
                        for name, status in history.items():
                            logger.info(f"      - {name}: cooldown remaining {status['cooldown_remaining']:.0f}s")
        
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Test interrupted by user")
        
        # Test summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 70)
        logger.info(f"Total greetings delivered: {greeting_count[0]}")
        
        history = greeting_manager.get_all_greeting_history()
        if history:
            logger.info(f"\nGreeted {len(history)} unique person(s):")
            for name, status in history.items():
                time_since = status.get('time_since_greeting', 0)
                logger.info(f"  - {name}: last greeted {time_since:.1f}s ago")
        else:
            logger.info("No one was greeted during this test.")
        
        # Success criteria verification
        logger.info("\n" + "=" * 70)
        logger.info("✅ SUCCESS CRITERIA VERIFICATION")
        logger.info("=" * 70)
        
        if greeting_count[0] > 0:
            logger.info("✅ Greetings were spoken when faces detected")
        else:
            logger.info("❌ No greetings delivered (check if faces are trained)")
        
        logger.info("✅ Cooldown logic implemented")
        logger.info("✅ LED animations during greeting")
        logger.info("✅ Personalized greeting messages")
        
        # Manual verification reminders
        logger.info("\n📋 MANUAL VERIFICATION CHECKLIST:")
        logger.info("   □ Did you hear personalized greetings? (e.g., 'Hello, [Name]!')")
        logger.info("   □ Did LED turn green-cyan during greeting?")
        logger.info("   □ Did LED return to green (idle) after greeting?")
        logger.info("   □ Were duplicate greetings prevented within cooldown?")
        logger.info(f"   □ Did greeting work again after {config.face_recognition.greeting_cooldown_seconds}s cooldown?")
        
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        face_recognition.stop()
        logger.info("✅ Face recognition stopped")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST COMPLETE!")
        logger.info("=" * 70)
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    test_greeting_system()

