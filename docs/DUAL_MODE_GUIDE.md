# Dual-Mode Voice Assistant Guide

## Overview

Your Misty voice assistant now supports **two different processing modes** that you can switch between based on your needs:

### 🐢 Traditional Mode (STT → GPT → TTS)
**Current default mode** - Slower but more stable

**How it works:**
1. Speech captured → Whisper transcribes to text (~1-2s)
2. Text sent to GPT for response (~2-3s)
3. Response converted to speech via Misty TTS (~2-3s)
4. **Total: ~5-8 seconds**

**Pros:**
- ✅ More stable and mature technology
- ✅ Works with all GPT models (gpt-4, gpt-4o, gpt-4o-mini)
- ✅ Easier to debug (you see the text at each step in logs)
- ✅ Better for complex conversations with context
- ✅ Conversation history maintained

**Cons:**
- ❌ Higher latency (~5-8 seconds feels slow)
- ❌ More API calls (costs slightly more)

---

### ⚡ Realtime Mode (Voice → Voice)
**New faster mode** - Much quicker responses

**How it works:**
1. Speech captured → Sent directly to OpenAI Realtime API
2. AI processes voice and responds with voice (~1-3s total)
3. **Total: ~1-3 seconds**

**Pros:**
- ✅ Much faster (~1-3 seconds feels natural)
- ✅ More natural conversation flow
- ✅ Lower cost (single API call instead of 3)
- ✅ Streaming audio responses

**Cons:**
- ⚠️ Only works with `gpt-4o-realtime-preview` model
- ⚠️ Newer technology (less mature, may have edge cases)
- ⚠️ Harder to debug (audio → audio, no text visibility)

---

## How to Switch Modes

### Option 1: Edit your `.env` file

Open your `.env` file and change the `VOICE_MODE` setting:

```bash
# For traditional mode (current default)
VOICE_MODE=traditional

# For realtime mode (faster)
VOICE_MODE=realtime
```

Then restart your application:
```bash
source venv/bin/activate
python misty_aicco_assistant.py
```

### Option 2: Set environment variable

```bash
# Traditional mode
export VOICE_MODE=traditional

# Realtime mode
export VOICE_MODE=realtime
```

---

## When to Use Which Mode?

### Use **Traditional Mode** when:
- 🔧 You're debugging or developing
- 📚 You need complex conversations with context
- 🎯 You want maximum stability
- 📝 You need to see what was said (text logs)
- 💰 You're using a cheaper model (gpt-4o-mini)

### Use **Realtime Mode** when:
- ⚡ You want the fastest responses possible
- 💬 You're doing simple Q&A conversations
- 🎭 You want the most natural conversation feel
- 🎤 Audio quality is more important than debugging
- 💵 You're okay with using gpt-4o-realtime-preview

---

## Testing the Configuration

Run the test script to verify both modes work:

```bash
source venv/bin/activate
python test_dual_mode.py
```

You should see:
```
✅ ALL TESTS PASSED!
```

---

## Configuration Example

Here's what your `.env` should look like:

```bash
# Misty Configuration
MISTY_IP_ADDRESS=10.66.239.83
OPENAI_API_KEY=sk-your-key-here

# Voice Mode Selection
VOICE_MODE=realtime           # Switch to "traditional" for slower but stable mode

# Wake Word Settings
WAKE_WORD_MODE=misty_builtin  # Uses "Hey Misty"

# Other settings...
FACE_RECOGNITION_ENABLED=true
VOICE_ASSISTANT_ENABLED=true
```

---

## What You'll See

### Traditional Mode Startup:
```
Setting up TRADITIONAL mode (STT → GPT → TTS)...
  - Setting up OpenAI Whisper for speech-to-text...
    ✅ STT initialized (model: whisper-1)
  - Setting up OpenAI Chat for AI responses...
    ✅ Chat initialized (model: gpt-4o-mini)
  ⚠️  Expected latency: ~5-8 seconds per response
```

### Realtime Mode Startup:
```
Setting up REALTIME mode (voice → voice)...
  - Connecting to OpenAI Realtime API...
    ✅ Realtime API connected
  ⚡ Expected latency: ~1-3 seconds per response
```

---

## Troubleshooting

### "Realtime mode is not available"
- Make sure you have a valid OpenAI API key
- Check your internet connection
- The Realtime API may be experiencing issues

### "Configuration Error"
- Run `python test_dual_mode.py` to verify your config
- Make sure `VOICE_MODE` is set to either `traditional` or `realtime`
- Check that your `.env` file exists and is properly formatted

### Slow responses in Realtime mode
- Realtime mode should be 1-3 seconds
- If it's slower, check your internet speed
- Try switching back to traditional mode temporarily

---

## Summary

**Current Setup:** You have both modes available and can switch anytime!

**Quick Switch:**
```bash
# Edit .env file
nano .env

# Change this line:
VOICE_MODE=realtime    # or "traditional"

# Restart
python misty_aicco_assistant.py
```

**My Recommendation:** Try realtime mode! It's much faster and feels more natural for conversations. If you encounter any issues, you can always switch back to traditional mode.

---

## Files Created

- `config.py` - Updated with `voice_mode` configuration
- `realtime_handler.py` - New handler for OpenAI Realtime API
- `misty_aicco_assistant.py` - Updated to support both modes
- `env.example` - Updated with new configuration options
- `test_dual_mode.py` - Test script to verify both modes
- `DUAL_MODE_GUIDE.md` - This guide!

