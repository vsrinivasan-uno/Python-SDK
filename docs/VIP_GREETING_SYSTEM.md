# VIP Greeting System with OpenAI Realtime API

## Overview

The Misty Aicco Assistant includes a sophisticated VIP greeting system that uses **OpenAI's Realtime API** to deliver personalized greetings with consistent voice quality. The system uses **local file storage** for pre-generated greetings, enabling instant streaming to Misty without upload delays.

## Architecture

### System Flow

```
Face Recognition → Greeting Manager → Local Cache Check → Stream to Misty
                         ↓
                   (Cache Miss)
                         ↓
                 OpenAI Realtime API → Generate Audio → Stream to Misty
```

### Key Components

1. **Greeting Manager** ([`greeting_manager.py`](../src/core/greeting_manager.py))
   - Manages cooldown tracking
   - Loads and streams pre-cached greetings from local storage
   - Falls back to Realtime API or Misty TTS if cache unavailable
   - Handles LED animations during greetings

2. **VIP Greeting Generator** ([`generate_vip_greetings.py`](../generate_vip_greetings.py))
   - Pre-generates high-quality greetings using OpenAI Realtime API
   - Saves WAV files locally in `greeting_cache/` directory
   - No Misty connection required for generation

3. **Face Recognition Integration** ([`misty_aicco_assistant.py`](../src/misty_aicco_assistant.py))
   - Continuous face recognition
   - Automatic greeting triggering
   - Audio monitor pause/resume coordination

4. **Configuration** ([`config.py`](../src/config.py))
   - VIP person definitions
   - Custom greeting messages
   - Cooldown settings
   - Realtime API enablement

## Configuration

### Environment Variables

Add to your `.env` file:

```bash
# Face Recognition Settings
FACE_RECOGNITION_ENABLED=true
GREETING_COOLDOWN_SECONDS=300  # 5 minutes between greetings

# Voice Mode (can be "realtime" or "traditional")
VOICE_MODE=realtime
```

**Note:** The `USE_REALTIME_FOR_GREETINGS` setting is no longer needed. Greetings always use pre-generated cache (with OpenAI voice) when available, falling back to Misty TTS otherwise.

### VIP Persons Configuration

VIP persons are configured in [`config.py`](../src/config.py):

```python
vip_persons = {
    "Mayor_John_W_Ewing_Junior": "Hi Mayor John W Ewing Junior. Delighted to have you...",
    "Chancellor_Joanne_Li": "Hi Chancellor Joanne Li. Delighted to have you...",
    "President_Heath_Mello": "Hi President Heath Mello. Delighted to have you...",
    # Add more VIP persons as needed
}
```

**Note:** Person names must match the face recognition training data exactly.

## Greeting Delivery Strategy

The system uses a **two-tier strategy** for optimal reliability:

### Priority 1: Local Cached Audio (Fastest - Instant)
- **Latency:** ~0.5-1 second
- **Source:** Pre-generated WAV files in `greeting_cache/` (created using OpenAI Realtime API)
- **Advantage:** 
  - Instant playback with consistent OpenAI voice
  - Highest quality audio
  - No API calls during demo
  - Works offline
- **When Used:** If greeting audio exists locally for the person (recommended for all VIPs)

### Priority 2: Misty TTS (Fallback - Always Available)
- **Latency:** ~1-2 seconds
- **Source:** Misty's built-in text-to-speech
- **Advantage:** 
  - No external dependencies
  - Always works (offline capable)
  - Reliable for non-VIP persons
- **When Used:** No cached greeting available

**Note:** OpenAI Realtime API is used **only for pre-generation** (via `generate_vip_greetings.py`), not for real-time greeting delivery. This ensures the demo has consistent, high-quality voice without risking API latency or failures during live interactions.

## Setup Guide

### Step 1: Train Face Recognition

Train Misty to recognize VIP persons:

```python
from mistyPy.Robot import Robot

misty = Robot("192.168.1.100")

# Start face training
misty.start_face_training("Mayor_John_W_Ewing_Junior")
# Look at the person for 10-15 seconds
misty.stop_face_training()
```

**Important:** Use exact names matching `vip_persons` configuration.

### Step 2: Generate Cached Greetings

Pre-generate greeting audio for all VIP persons:

```bash
cd Python-SDK
python generate_vip_greetings.py
```

**Output:**
```
=== VIP Greeting Generator (Local Storage) ===
Cache Directory: /path/to/Python-SDK/greeting_cache
VIP Persons: 8

[1/8] Processing: Mayor_John_W_Ewing_Junior
----------------------------------------------------------
📤 Generating audio for greeting...
✅ Audio generation complete: 245760 bytes
💾 Saving to local storage: greeting_Mayor_John_W_Ewing_Junior.wav
✅ Successfully saved: greeting_Mayor_John_W_Ewing_Junior.wav

📊 Generation Summary:
   ✅ Successful: 8
   ❌ Failed: 0
   📦 Total: 8
   📂 Saved to: /path/to/Python-SDK/greeting_cache
```

**Generated Files:**
```
greeting_cache/
├── greeting_Mayor_John_W_Ewing_Junior.wav
├── greeting_Chancellor_Joanne_Li.wav
├── greeting_President_Heath_Mello.wav
└── ...
```

### Step 3: Run the Assistant

```bash
cd Python-SDK
python run_assistant.py
```

The greeting manager will automatically load cached greetings on startup:

```
Greeting Manager initialized with 300s cooldown
Available greeting templates: 4
VIP persons configured: 8
Cached greetings loaded: 8
Cache directory: greeting_cache
Voice mode: OpenAI Realtime API
```

## Usage Examples

### Recognizing a VIP Person

When a VIP is recognized:

```
👤 Face recognized: Chancellor Joanne Li (confidence: 0.92)
🌟 VIP recognized: Chancellor Joanne Li
👋 Greeting 'Chancellor Joanne Li': Hi Chancellor Joanne Li. Delighted...
🎵 Using LOCAL cached greeting audio for Chancellor Joanne Li
📂 Reading local file: greeting_cache/greeting_Chancellor_Joanne_Li.wav
📦 Loaded 123.45 KB from local storage
📤 Uploading to Misty as: temp_greeting_a1b2c3d4.wav
✅ Uploaded to Misty successfully
🔊 Playing greeting on Misty
✅ Playback started successfully
✅ Local cached greeting delivered to 'Chancellor Joanne Li'
```

### Recognizing a Regular Person

When a regular person is recognized (no cached greeting):

```
👤 Face recognized: John Smith (confidence: 0.88)
👋 Greeting 'John Smith': Hello, John Smith! Welcome back!
🔊 Using Misty's built-in TTS for greeting
✅ Greeting spoken successfully (Misty TTS)
✅ Greeting delivered to 'John Smith'
```

### Cooldown Management

Greetings respect cooldown periods to avoid repetition:

```
👤 Face recognized: Chancellor Joanne Li (confidence: 0.91)
⏳ Skipping greeting for 'Chancellor Joanne Li' (cooldown: 245s remaining)
```

## API Reference

### GreetingManager Class

#### Constructor

```python
GreetingManager(
    misty: Robot,
    greeting_templates: list,
    cooldown_seconds: int = 300,
    greeting_led_color: tuple = (0, 255, 100),
    idle_led_color: tuple = (0, 255, 0),
    vip_persons: dict = None,
    realtime_handler = None,
    audio_queue_manager = None,
    use_realtime_api: bool = False,
    cache_directory: str = "greeting_cache"
)
```

#### Key Methods

**`greet_person(person_name, force=False, recognized_at=None)`**
- Delivers personalized greeting with cooldown management
- Returns `True` if greeting delivered, `False` if skipped
- `force=True` bypasses cooldown check

**`should_greet(person_name)`**
- Checks if person should be greeted based on cooldown
- Returns `True` if greeting allowed, `False` otherwise

**`get_greeting_status(person_name)`**
- Returns dictionary with greeting status:
  - `last_greeted`: Timestamp of last greeting
  - `can_greet`: Boolean indicating if greeting allowed
  - `cooldown_remaining`: Seconds until next greeting allowed
  - `has_cached_audio`: Boolean indicating if cached audio exists

**`reload_cache()`**
- Reloads cached greetings from local storage
- Useful after generating new greetings

**`reset_cooldown(person_name=None)`**
- Resets cooldown for specific person or all people
- `None` resets all cooldowns

### VIPGreetingGenerator Class

#### Constructor

```python
VIPGreetingGenerator(cache_directory: str = "greeting_cache")
```

#### Key Methods

**`connect_realtime_api()`**
- Establishes connection to OpenAI Realtime API

**`generate_greeting_audio(greeting_text, timeout=30.0)`**
- Generates audio from text using Realtime API
- Returns PCM16 audio bytes at 24kHz
- Timeout in seconds for generation

**`save_locally(person_name, wav_bytes)`**
- Saves greeting WAV file to local cache
- Returns `True` if successful

**`generate_all_vip_greetings()`**
- Batch generates all VIP greetings from config
- Saves to local cache automatically

## Performance Metrics

### Latency Comparison

| Method | Time to Audio | Quality | Voice | Dependencies |
|--------|---------------|---------|-------|--------------|
| Local Cache | 0.5-1s | Excellent | OpenAI (Ash) | None (offline) |
| Misty TTS | 1-2s | Good | Misty Default | None (offline) |

### Storage Requirements

- **Cached Greeting:** ~100-200 KB per person (WAV, 24kHz)
- **10 VIP persons:** ~1-2 MB total
- **Format:** Uncompressed PCM WAV (high quality)

## Troubleshooting

### Issue: Cached greetings not loading

**Symptoms:**
```
ℹ️ No cached greetings found in local storage
   Run 'python generate_vip_greetings.py' to generate them
```

**Solution:**
1. Run the greeting generator:
   ```bash
   python generate_vip_greetings.py
   ```
2. Verify files exist in `greeting_cache/` directory
3. Restart the assistant to reload cache

### Issue: Face recognition not triggering greetings

**Symptoms:** Face recognized but no greeting delivered

**Checklist:**
1. **Check cooldown status:**
   ```python
   status = greeting_manager.get_greeting_status("Person Name")
   print(status['cooldown_remaining'])  # Must be 0 to greet
   ```

2. **Verify face name matches config:**
   ```python
   # Face training name must match exactly
   "Mayor_John_W_Ewing_Junior"  # ✅ Correct
   "Mayor John W Ewing Junior"  # ❌ Wrong (spaces vs underscores)
   ```

3. **Check audio monitor state:**
   - Audio monitor may be paused during voice interaction
   - Greeting resumes after conversation ends

### Issue: Want consistent OpenAI voice for greetings

**Solution:** Pre-generate greetings using the generator script

The system is designed to use **pre-generated cache** for consistent OpenAI voice, not real-time API calls. This ensures:
- Instant playback (0.5-1s)
- No API failures during demo
- Consistent quality
- Works offline

**Steps:**
1. Run the greeting generator:
   ```bash
   python generate_vip_greetings.py
   ```

2. Verify files were created:
   ```bash
   ls -la greeting_cache/
   ```

3. Restart the assistant to load cache

### Issue: Audio playback fails

**Symptoms:** Upload succeeds but playback fails

**Solutions:**
1. **Check audio format:**
   - Must be WAV format
   - Sample rate: 16kHz or 24kHz
   - Channels: Mono (1 channel)
   - Bits per sample: 16

2. **Verify Misty storage:**
   - Check available storage on Misty
   - Delete old audio files if needed

3. **Increase timeout:**
   - Large files may need longer upload time
   - Check network connection to Misty

## Best Practices

### 1. Pre-Generate for VIPs
Always pre-generate greetings for VIP persons:
- Instant playback (0.5-1s latency)
- No API calls during demo
- Consistent quality
- Offline capability

### 2. Use Descriptive Names
Match face training names to configuration exactly:
```python
# Good: Clear, descriptive, matches config
"Chancellor_Joanne_Li"

# Bad: Ambiguous or mismatched
"Joanne"
"chancellor_li"
```

### 3. Optimize Cooldown
Balance between friendliness and annoyance:
- **Short events (1-2 hours):** 300s (5 min)
- **Long events (all day):** 900s (15 min)
- **Testing:** 60s (1 min)

### 4. Cache Management
Regenerate cache when:
- Greeting text changes
- Voice model updates
- Audio quality issues detected

### 5. Monitor Performance
Check logs for latency metrics:
```
⏱️ Face→speak latency: 0.847s
🎵 Using LOCAL cached greeting audio
✅ Playback started successfully
```

## Integration with Voice Assistant

### Seamless Coordination

The greeting system coordinates with the voice assistant:

1. **Audio Monitor Pause:**
   - Face recognition pauses audio monitor during greeting
   - Prevents wake word false positives
   - Resumes after 5 seconds

2. **LED States:**
   - Greeting: Green-cyan (0, 255, 100)
   - Idle: Green (0, 255, 0)
   - Speaking: Yellow-green (100, 255, 0)

3. **Conversation Mode:**
   - Face recognition disabled during "Hey Misty" conversations
   - Resumes when conversation ends
   - Prevents conflicting interactions

### Example Flow

```
[Idle] → Face Recognized → Greeting Delivered → Return to Idle
                                                      ↓
                                              "Hey Misty" detected
                                                      ↓
                                              Voice Conversation
                                                      ↓
                                              Conversation Ends
                                                      ↓
                                              Resume Face Recognition
```

## Advanced Configuration

### Custom Greeting Templates

For non-VIP persons, customize templates in [`config.py`](../src/config.py):

```python
greeting_templates = [
    "Hello, {name}! Welcome back!",
    "Hi {name}! Great to see you again!",
    "Hey {name}! How are you doing?",
    "Welcome back, {name}!",
    "Good to see you, {name}!",
]
```

### LED Customization

Customize LED colors in `.env`:

```bash
# Custom LED colors (RGB values 0-255)
LED_GREETING_R=0
LED_GREETING_G=255
LED_GREETING_B=100
```

### Cache Directory

Change cache location:

```python
greeting_manager = GreetingManager(
    misty=misty,
    cache_directory="/custom/path/to/cache",
    # ... other parameters
)
```

## Testing

### Test VIP Configuration

```bash
python test_vip_greetings.py
```

**Output:**
```
🧪 Starting VIP Greeting Tests

[Test 1] Checking VIP persons configuration...
✅ PASS: 8 VIP persons configured

[Test 2] Verifying required VIP persons...
  ✅ Mayor John W Ewing Junior: Found
  ✅ Chancellor Joanne Li: Found
  ✅ President Heath Mello: Found
✅ PASS: All required VIP persons are configured

✅ ALL TESTS PASSED
```

### Manual Greeting Test

Test greeting delivery manually:

```python
from src.core.greeting_manager import GreetingManager
from mistyPy.Robot import Robot

misty = Robot("192.168.1.100")
greeting_manager = GreetingManager(misty, greeting_templates=[...])

# Test VIP greeting
greeting_manager.greet_person("Chancellor_Joanne_Li", force=True)

# Test regular greeting
greeting_manager.greet_person("John_Smith", force=True)

# Check status
status = greeting_manager.get_greeting_status("Chancellor_Joanne_Li")
print(f"Has cached audio: {status['has_cached_audio']}")
print(f"Can greet: {status['can_greet']}")
```

## Future Enhancements

### Planned Features

1. **Multilingual Greetings**
   - Support for multiple languages
   - Auto-detect user language preference
   - Per-person language configuration

2. **Dynamic Greeting Context**
   - Time-based greetings (morning, afternoon, evening)
   - Event-based greetings (conferences, demos)
   - Weather-aware greetings

3. **Gesture Recognition**
   - Hand wave detection
   - Combined with face recognition
   - More natural interaction flow

4. **Emotion Detection**
   - Adapt greeting tone to detected emotion
   - Enthusiastic for happy faces
   - Gentle for tired faces

5. **Greeting Analytics**
   - Track greeting frequency per person
   - Most common visitors
   - Peak interaction times

## Conclusion

The VIP greeting system provides a professional, personalized experience for important visitors while maintaining flexibility for regular users. The **pre-generation + local cache** strategy ensures:

- **Low latency:** Instant greetings (0.5-1s) via local cache
- **High quality:** Consistent OpenAI voice (same as voice assistant)
- **Reliability:** Pre-generated audio eliminates API failures during demos
- **Offline capability:** Works without internet after pre-generation
- **Scalability:** Easy to add new VIP persons

**Key Insight:** By separating greeting generation (offline, using Realtime API) from greeting delivery (instant, from local files), we achieve both consistent voice quality and rock-solid reliability for live demos.

For questions or issues, refer to the troubleshooting section or check the logs for diagnostic information.