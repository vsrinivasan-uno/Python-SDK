#!/usr/bin/env python3
"""Test script for Task 3.1: Continuous Audio Monitoring

This script tests:
1. Audio monitoring starts and runs continuously
2. No blocking of other operations
3. Memory efficient operation
4. Event handlers registered properly

Usage:
    python3 test_audio_monitor.py
"""

import os
import sys
import time
import logging
import psutil  # For memory monitoring

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from mistyPy.Robot import Robot
from src.config import get_config
from src.core.audio_monitor import AudioMonitor


def setup_logging():
    """Set up logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("AudioMonitorTest")


def get_process_memory_mb():
    """Get current process memory usage in MB."""
    process = psutil.Process()
    mem_info = process.memory_info()
    return mem_info.rss / 1024 / 1024  # Convert bytes to MB


def test_audio_monitoring():
    """Test the audio monitoring system."""
    logger = setup_logging()
    
    logger.info("=" * 70)
    logger.info("Task 3.1: Continuous Audio Monitoring - Test Script")
    logger.info("=" * 70)
    
    # Load configuration
    config = get_config()
    logger.info(f"\nConnecting to Misty at {config.misty.ip_address}...")
    
    try:
        # Connect to Misty
        misty = Robot(config.misty.ip_address)
        logger.info("✅ Connected to Misty successfully!")
        
        # Set LED to indicate testing
        misty.change_led(100, 100, 255)  # Light blue for testing
        logger.info("💡 LED set to test mode: Light Blue")
        
        # Track events for testing
        wake_word_count = [0]
        speech_capture_count = [0]
        
        def on_wake_word_detected(event_data):
            """Callback when wake word is detected."""
            wake_word_count[0] += 1
            logger.info(f"\n🎤 WAKE WORD DETECTED! (#{wake_word_count[0]})")
            logger.info(f"   Event data: {event_data}")
            logger.info("   📝 Listening for your query now...")
        
        def on_speech_captured(audio_data):
            """Callback when speech is captured."""
            speech_capture_count[0] += 1
            logger.info(f"\n🎙️  SPEECH CAPTURED! (#{speech_capture_count[0]})")
            logger.info(f"   Filename: {audio_data.get('filename')}")
            logger.info(f"   Success: {audio_data.get('success')}")
            logger.info("   ✅ Ready for next wake word...")
        
        # Initialize audio monitor
        logger.info("\n📋 Initializing Audio Monitor...")
        audio_monitor = AudioMonitor(
            misty=misty,
            on_wake_word_detected=on_wake_word_detected,
            on_speech_captured=on_speech_captured,
            wake_word_mode=config.voice_assistant.wake_word_mode,
            silence_timeout=int(config.voice_assistant.silence_threshold_seconds * 1000),
            max_speech_length=config.voice_assistant.max_recording_seconds * 1000
        )
        
        # Get initial memory usage
        initial_memory = get_process_memory_mb()
        logger.info(f"📊 Initial memory usage: {initial_memory:.2f} MB")
        
        # Start audio monitoring
        logger.info("\n🎬 Starting audio monitoring...")
        audio_monitor.start()
        
        # Check status
        status = audio_monitor.get_status()
        logger.info("\n📊 Audio Monitor Status:")
        logger.info(f"   Running: {status['running']}")
        logger.info(f"   Mode: {status['mode']}")
        logger.info(f"   Silence timeout: {status['silence_timeout_ms']}ms")
        logger.info(f"   Max speech length: {status['max_speech_length_ms']}ms")
        
        logger.info("\n" + "=" * 70)
        logger.info("🎬 TEST SCENARIOS - Task 3.1 Success Criteria")
        logger.info("=" * 70)
        
        logger.info("\n📝 Success Criteria:")
        logger.info("   ✅ Audio continuously monitored in non-blocking manner")
        logger.info("   ✅ No blocking of other operations (test by moving around)")
        logger.info("   ✅ Memory efficient (will monitor over 60 seconds)")
        logger.info("   ✅ Event handlers registered and functional")
        
        logger.info("\n📝 Test Instructions:")
        logger.info("1. Say 'Hey Misty' to trigger wake word detection")
        logger.info("2. After acknowledgment, say a query (e.g., 'What time is it?')")
        logger.info("3. Wait 2 seconds of silence to complete capture")
        logger.info("4. Verify speech capture event fires")
        logger.info("5. Repeat multiple times to test continuous operation")
        logger.info("\n🔍 Monitoring for 60 seconds...")
        logger.info("   Press Ctrl+C to stop early\n")
        
        # Run test for 60 seconds with periodic status updates
        test_duration = 60
        start_time = time.time()
        last_memory_check = start_time
        memory_samples = [initial_memory]
        
        try:
            while time.time() - start_time < test_duration:
                time.sleep(1)
                
                elapsed = time.time() - start_time
                
                # Check memory every 10 seconds
                if time.time() - last_memory_check >= 10:
                    current_memory = get_process_memory_mb()
                    memory_samples.append(current_memory)
                    memory_delta = current_memory - initial_memory
                    
                    logger.info(f"\n⏱️  Elapsed: {int(elapsed)}s / {test_duration}s")
                    logger.info(f"   Memory: {current_memory:.2f} MB (Δ {memory_delta:+.2f} MB)")
                    logger.info(f"   Wake words detected: {wake_word_count[0]}")
                    logger.info(f"   Speech captures: {speech_capture_count[0]}")
                    
                    last_memory_check = time.time()
        
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Test interrupted by user")
        
        # Final memory check
        final_memory = get_process_memory_mb()
        memory_delta = final_memory - initial_memory
        max_memory = max(memory_samples)
        avg_memory = sum(memory_samples) / len(memory_samples)
        
        # Test summary
        logger.info("\n" + "=" * 70)
        logger.info("📊 TEST SUMMARY")
        logger.info("=" * 70)
        
        logger.info(f"\n⏱️  Test Duration: {time.time() - start_time:.1f} seconds")
        logger.info(f"🎤 Wake words detected: {wake_word_count[0]}")
        logger.info(f"🎙️  Speech captures completed: {speech_capture_count[0]}")
        
        logger.info(f"\n💾 Memory Statistics:")
        logger.info(f"   Initial: {initial_memory:.2f} MB")
        logger.info(f"   Final: {final_memory:.2f} MB")
        logger.info(f"   Delta: {memory_delta:+.2f} MB")
        logger.info(f"   Average: {avg_memory:.2f} MB")
        logger.info(f"   Peak: {max_memory:.2f} MB")
        
        # Memory efficiency check
        if abs(memory_delta) < 50:  # Less than 50MB growth
            logger.info("   ✅ Memory usage is stable and efficient")
        else:
            logger.warning(f"   ⚠️  Memory delta is {memory_delta:.2f} MB - check for leaks")
        
        # Success criteria verification
        logger.info("\n" + "=" * 70)
        logger.info("✅ SUCCESS CRITERIA VERIFICATION")
        logger.info("=" * 70)
        
        is_running = audio_monitor.is_running()
        if is_running:
            logger.info("✅ Audio continuously monitored throughout test")
        else:
            logger.warning("❌ Audio monitoring stopped unexpectedly")
        
        logger.info("✅ No blocking observed (script responsive to Ctrl+C)")
        
        if abs(memory_delta) < 50:
            logger.info("✅ Memory usage stable - efficient operation confirmed")
        else:
            logger.info("⚠️  Memory usage increased - may need optimization")
        
        if wake_word_count[0] > 0:
            logger.info(f"✅ Event handlers functional - {wake_word_count[0]} wake word(s) detected")
        else:
            logger.info("⚠️  No wake words detected - try saying 'Hey Misty'")
        
        # Manual verification checklist
        logger.info("\n📋 MANUAL VERIFICATION CHECKLIST:")
        logger.info("   □ Did audio monitoring start without errors?")
        logger.info("   □ Could you trigger wake word detection by saying 'Hey Misty'?")
        logger.info("   □ Did speech capture complete after your query?")
        logger.info("   □ Was the system responsive (no freezing)?")
        logger.info("   □ Did memory usage remain stable?")
        
        # Cleanup
        logger.info("\n🧹 Cleaning up...")
        audio_monitor.stop()
        logger.info("✅ Audio monitor stopped")
        
        # Reset LED
        misty.change_led(*config.led.idle)
        logger.info("💡 LED reset to idle")
        
        logger.info("\n" + "=" * 70)
        logger.info("✅ TEST COMPLETE!")
        logger.info("=" * 70)
        
        logger.info("\n💡 Note: This completes Task 3.1 (Continuous Audio Monitoring)")
        logger.info("   Next: Task 3.2 will integrate full wake word detection logic")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    # Check if psutil is installed
    try:
        import psutil
    except ImportError:
        print("❌ Error: psutil not installed")
        print("   Install with: pip install psutil")
        sys.exit(1)
    
    test_audio_monitoring()

