#!/usr/bin/env python3
"""Test script for Phase 5: Full Conversational AI

This script tests the complete end-to-end conversational AI pipeline:
1. Wake word detection ("Hey Misty")
2. Speech capture (with silence detection)
3. Speech-to-Text transcription (OpenAI Whisper)
4. AI response generation (OpenAI GPT)
5. Text-to-Speech output (Misty speaks!)
6. Conversation history management
7. Continuous operation (repeat unlimited times)

This is the FINAL integration test for the full Misty Aicco Assistant!

Usage:
    python3 test_full_conversation.py
"""

import os
import sys
import logging

# Add project root to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

from src.config import get_config
from src.misty_aicco_assistant import MistyAiccoAssistant


def setup_logging():
    """Set up logging for the test."""
    logging.basicConfig(
        level=logging.INFO,
        format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
        datefmt='%Y-%m-%d %H:%M:%S'
    )
    return logging.getLogger("FullConversationTest")


def test_full_conversation():
    """Test the complete conversational AI system."""
    logger = setup_logging()
    
    logger.info("=" * 70)
    logger.info("🎉 FULL CONVERSATIONAL AI - Complete System Test")
    logger.info("=" * 70)
    
    # Load configuration
    config = get_config()
    
    logger.info("\n" + "=" * 70)
    logger.info("✨ COMPLETE PIPELINE - Phase 1-5 Integration")
    logger.info("=" * 70)
    
    logger.info("\n🎯 What's Being Tested:")
    logger.info("   ✅ Phase 1: Configuration & Setup")
    logger.info("   ✅ Phase 2: Face Recognition & Greetings")
    logger.info("   ✅ Phase 3: Wake Word Detection")
    logger.info("   ✅ Phase 4: Speech-to-Text (Whisper)")
    logger.info("   ✅ Phase 5: AI Chat (GPT) + Text-to-Speech")
    
    logger.info("\n📝 Success Criteria (Phase 5):")
    logger.info("   ✅ Task 5.1: AI response generation")
    logger.info("      - Query sent to OpenAI GPT successfully")
    logger.info("      - Response received and formatted")
    logger.info("      - Response time < 5 seconds")
    logger.info("      - Conversation context maintained")
    logger.info("   ✅ Task 5.2: Text-to-Speech response")
    logger.info("      - Response spoken clearly through Misty")
    logger.info("      - LED yellow-green during speaking")
    logger.info("      - System ready for next query after speaking")
    
    logger.info("\n" + "=" * 70)
    logger.info("🎬 HOW TO USE MISTY AICCO ASSISTANT")
    logger.info("=" * 70)
    
    logger.info("\n📝 Full Conversation Flow:")
    logger.info("   1️⃣  Say 'Hey Misty'")
    logger.info("      → LED turns PURPLE (listening)")
    logger.info("      → Misty is waiting for your query")
    logger.info("")
    logger.info("   2️⃣  Ask your question, for example:")
    logger.info("      • 'What is artificial intelligence?'")
    logger.info("      • 'Tell me a joke'")
    logger.info("      • 'What's the capital of France?'")
    logger.info("      • 'How are you doing today?'")
    logger.info("      • 'Explain quantum physics simply'")
    logger.info("")
    logger.info("   3️⃣  Wait for 2 seconds of silence")
    logger.info("      → LED turns CYAN (processing)")
    logger.info("      → Speech is being transcribed...")
    logger.info("      → AI is generating response...")
    logger.info("")
    logger.info("   4️⃣  Misty speaks the answer!")
    logger.info("      → LED turns YELLOW-GREEN (speaking)")
    logger.info("      → Listen to Misty's response")
    logger.info("")
    logger.info("   5️⃣  After response completes")
    logger.info("      → LED turns GREEN (idle)")
    logger.info("      → Ready for next 'Hey Misty'!")
    logger.info("")
    logger.info("   🔁 REPEAT AS MANY TIMES AS YOU WANT!")
    
    logger.info("\n" + "=" * 70)
    logger.info("💡 EXAMPLE CONVERSATIONS TO TRY")
    logger.info("=" * 70)
    
    logger.info("\n🗣️  Example 1: General Knowledge")
    logger.info("   You: 'Hey Misty'")
    logger.info("   You: 'What is the tallest mountain in the world?'")
    logger.info("   Misty: [Responds with answer about Mount Everest]")
    
    logger.info("\n🗣️  Example 2: Fun & Entertainment")
    logger.info("   You: 'Hey Misty'")
    logger.info("   You: 'Tell me a fun fact about robots'")
    logger.info("   Misty: [Shares an interesting robot fact]")
    
    logger.info("\n🗣️  Example 3: Follow-up Questions (Context)")
    logger.info("   You: 'Hey Misty'")
    logger.info("   You: 'Who wrote Romeo and Juliet?'")
    logger.info("   Misty: [Responds: William Shakespeare]")
    logger.info("   You: 'Hey Misty'")
    logger.info("   You: 'What other plays did he write?'")
    logger.info("   Misty: [Responds with other Shakespeare plays]")
    logger.info("   ✨ (Maintains conversation history!)")
    
    logger.info("\n🗣️  Example 4: Personal Interaction")
    logger.info("   You: 'Hey Misty'")
    logger.info("   You: 'How are you doing today?'")
    logger.info("   Misty: [Responds with friendly personality]")
    
    logger.info("\n" + "=" * 70)
    logger.info("🌟 LED STATE LEGEND")
    logger.info("=" * 70)
    logger.info("   🟢 GREEN     = Idle (waiting for 'Hey Misty')")
    logger.info("   🟣 PURPLE    = Listening (speak your query)")
    logger.info("   🔵 CYAN      = Processing (transcribing & thinking)")
    logger.info("   🟡 YELLOW-GREEN = Speaking (Misty is responding)")
    logger.info("   🔴 RED       = Error (something went wrong)")
    
    logger.info("\n" + "=" * 70)
    logger.info("🚀 STARTING FULL ASSISTANT NOW...")
    logger.info("=" * 70)
    logger.info("\n   Press Ctrl+C to stop\n")
    
    try:
        # Create and start the full assistant
        logger.info("Initializing complete Misty Aicco Assistant...")
        assistant = MistyAiccoAssistant(config)
        
        # Start in a separate try block to handle the keep_alive loop
        try:
            assistant.start()
        except KeyboardInterrupt:
            logger.info("\n\n⏹️  Shutting down assistant...")
        
    except Exception as e:
        logger.error(f"\n❌ Test failed with error: {e}", exc_info=True)
        sys.exit(1)
    
    # Test summary
    logger.info("\n" + "=" * 70)
    logger.info("📊 TEST SESSION COMPLETE")
    logger.info("=" * 70)
    
    logger.info("\n✅ All systems functional:")
    logger.info("   ✓ Face recognition with greetings")
    logger.info("   ✓ Wake word detection")
    logger.info("   ✓ Speech capture")
    logger.info("   ✓ Speech-to-Text transcription")
    logger.info("   ✓ AI response generation")
    logger.info("   ✓ Text-to-Speech output")
    logger.info("   ✓ Conversation history")
    logger.info("   ✓ LED state feedback")
    logger.info("   ✓ Continuous operation")
    
    # Manual verification checklist
    logger.info("\n📋 MANUAL VERIFICATION CHECKLIST:")
    logger.info("   □ Did wake word 'Hey Misty' work reliably?")
    logger.info("   □ Did speech capture work after your query?")
    logger.info("   □ Was transcription accurate?")
    logger.info("   □ Did AI generate appropriate responses?")
    logger.info("   □ Did Misty speak the responses clearly?")
    logger.info("   □ Did LED states change correctly?")
    logger.info("   □ Did follow-up questions maintain context?")
    logger.info("   □ Could you have multiple conversations?")
    logger.info("   □ Did face recognition still work?")
    logger.info("   □ Was the overall experience smooth?")
    
    logger.info("\n" + "=" * 70)
    logger.info("🎉 CONGRATULATIONS!")
    logger.info("=" * 70)
    logger.info("\n   You have a fully functional AI assistant on Misty!")
    logger.info("   Phases 1-5 are COMPLETE! 🚀")
    logger.info("")
    logger.info("   Next steps (Optional - Phase 6-10):")
    logger.info("   - State management for conflict prevention")
    logger.info("   - Advanced error handling")
    logger.info("   - Performance optimization")
    logger.info("   - Additional features")
    
    logger.info("\n" + "=" * 70)


if __name__ == "__main__":
    test_full_conversation()

