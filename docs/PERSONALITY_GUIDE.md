# Misty Personality & Animation Guide

This guide explains how to use Misty's new dynamic personality features!

## 🎭 What's New

Your Misty robot is now much more engaging and fun to interact with! Here's what she can do:

### 1. **Dynamic Animations During Conversations**
- **Listening**: Subtle head tilt when you start speaking
- **Thinking**: Head movements while processing your question
- **Speaking**: Head bobs and arm gestures while responding
- **Greeting**: Waves with happy eyes when recognizing faces

### 2. **Eye Expressions** (18 Different Emotions)
- Joy, Love, Amazement, Surprise
- Sadness, Anger, Fear, Disgust
- Sleepy, Contempt, Terror, Rage
- And more!

### 3. **Screensaver Mode** (Dancing When Idle)
After 2 minutes of no interaction, Misty will:
- Start dancing with 4 different dance routines
- Show various expressions
- Move her head and arms in fun patterns
- Keep entertaining herself!

### 4. **Battery Saving Mode**
When in screensaver:
- Camera turns off (no face recognition)
- Microphone turns off (no wake word detection)
- Saves battery during idle time
- **Say "Hey Misty" to wake her up** - everything restarts automatically!

---

## ⚙️ Configuration

All personality features are configured in your `.env` file:

```bash
# Personality & Animations Configuration
PERSONALITY_ENABLED=true              # Enable dynamic animations
IDLE_TIMEOUT_SECONDS=120.0            # Seconds before screensaver (default: 2 minutes)
SCREENSAVER_ENABLED=true              # Enable dancing mode
BATTERY_SAVING_ENABLED=true           # Stop camera/audio when idle
ANIMATIONS_DURING_SPEECH=true         # Animate during conversations
```

### Configuration Options

| Setting | Default | Description |
|---------|---------|-------------|
| `PERSONALITY_ENABLED` | `true` | Master switch for all personality features |
| `IDLE_TIMEOUT_SECONDS` | `120.0` | How long before screensaver activates (in seconds) |
| `SCREENSAVER_ENABLED` | `true` | Enable/disable dancing mode |
| `BATTERY_SAVING_ENABLED` | `true` | Turn off camera/mic during screensaver |
| `ANIMATIONS_DURING_SPEECH` | `true` | Enable animations during conversations |

### Customization Examples

**Shorter Screensaver Timeout (30 seconds)**
```bash
IDLE_TIMEOUT_SECONDS=30.0
```

**Disable Battery Saving (keep services on)**
```bash
BATTERY_SAVING_ENABLED=false
```

**Disable Animations (keep Misty still)**
```bash
ANIMATIONS_DURING_SPEECH=false
```

**Disable All Personality Features**
```bash
PERSONALITY_ENABLED=false
```

---

## 🚀 How to Use

### Running the Full Assistant

Just run the main assistant as usual:

```bash
python3 misty_aicco_assistant.py
```

Everything will work automatically:
1. Misty will animate during conversations
2. After 2 minutes of inactivity, she'll start dancing
3. Battery saving mode activates during screensaver
4. Say "Hey Misty" to wake her up anytime

### Testing Personality Features

To test animations and screensaver separately:

```bash
python3 test_personality.py
```

This will test:
- Eye expressions (5 different emotions)
- Conversation animations (listening, thinking, speaking, greeting)
- Individual dance moves (4 routines)
- Screensaver activation (optional, 10-second timeout for testing)

---

## 🎬 Dance Moves

Misty has 4 different dance routines that play randomly in screensaver mode:

### Dance Move 1: Head Shake with Arm Waves
- Shakes head left and right
- Waves arms up and down
- Shows joy expression

### Dance Move 2: Spin 360
- Spins in place
- Shows amazement expression
- Full circle rotation

### Dance Move 3: Arm Wave Sequence
- Both arms wave up and down
- Shows love expression
- Repeats 3 times

### Dance Move 4: Look Around Curiously
- Looks in different directions
- Shows surprise expression
- Explores the environment

---

## 👁️ Eye Expressions

Misty can show 18 different expressions! Here are the main ones:

| Expression | Use Case |
|------------|----------|
| `joy` | Happy, during conversations |
| `love` | Greeting friends |
| `amazement` | Surprised or excited |
| `surprise` | Unexpected events |
| `default` | Neutral, idle state |
| `sleepy` | Tired, low battery |
| `anger` | Error states (if configured) |
| `sadness` | Failures (if configured) |

---

## 🔋 Battery Saving

### How It Works

1. **Normal Operation**: Camera and microphone are always on
2. **After 2 Minutes Idle**: Screensaver activates, battery saving begins
3. **Services Stop**: Face recognition and wake word detection turn off
4. **Dancing Continues**: Misty keeps dancing to entertain
5. **Say "Hey Misty"**: Everything wakes up and restarts automatically

### Why Battery Saving?

- Face recognition uses significant camera processing
- Wake word detection requires constant microphone monitoring
- Turning these off during idle saves battery
- Misty can entertain for longer without charging

### Disabling Battery Saving

If you want camera/mic to stay on even during screensaver:

```bash
BATTERY_SAVING_ENABLED=false
```

---

## 🎯 User Experience Examples

### Example 1: Face Greeting
```
1. You walk into the room
2. Misty recognizes your face
3. Shows "love" expression
4. Waves her arm
5. Says "Hello, John! Welcome back!"
```

### Example 2: Voice Conversation
```
1. You say "Hey Misty"
2. Misty tilts head (listening animation)
3. Purple LED turns on
4. You ask "What's the weather?"
5. Misty looks around (thinking animation)
6. Cyan LED while processing
7. Misty bobs head and moves arm (speaking animation)
8. Yellow-green LED while speaking
9. Says "The weather is sunny today!"
10. Returns to neutral pose
```

### Example 3: Screensaver Mode
```
1. No interaction for 2 minutes
2. Camera and microphone turn off (battery saving)
3. Misty starts dancing
4. Shows different expressions
5. Random dance moves keep playing
6. You say "Hey Misty"
7. Camera and microphone turn back on
8. Misty stops dancing and responds
```

---

## 🐛 Troubleshooting

### Animations Not Working

**Check configuration:**
```bash
PERSONALITY_ENABLED=true
ANIMATIONS_DURING_SPEECH=true
```

**Check logs:**
```bash
tail -f misty_assistant.log | grep Personality
```

**Look for:**
```
✅ Personality manager initialized successfully
```

### Screensaver Not Activating

**Check timeout setting:**
```bash
IDLE_TIMEOUT_SECONDS=120.0  # 2 minutes
SCREENSAVER_ENABLED=true
```

**Test with shorter timeout:**
```bash
IDLE_TIMEOUT_SECONDS=30.0  # 30 seconds for testing
```

**Check logs:**
```
⏰ Idle for 120s - entering screensaver mode
🎬 Entering screensaver mode (dancing)
```

### Battery Saving Issues

**Verify setting:**
```bash
BATTERY_SAVING_ENABLED=true
```

**Check logs for:**
```
🔋 Entering battery saving mode - stopping services...
   Stopping face recognition (camera off)...
   Stopping audio monitor (microphone off)...
✅ Battery saving mode active - say 'Hey Misty' to wake up
```

**Wake up logs:**
```
🔌 Exiting battery saving mode - restarting services...
   Restarting face recognition (camera on)...
   Restarting audio monitor (microphone on)...
✅ All services restarted - ready for interactions
```

### Misty Gets Stuck in Screensaver

**Say "Hey Misty"** - This should wake her up

**If that doesn't work:**
1. Stop the assistant (Ctrl+C)
2. Restart: `python3 misty_aicco_assistant.py`

**Emergency reset:**
```bash
# Connect to Misty directly
python3 -c "from mistyPy.Robot import Robot; m = Robot('YOUR_IP'); m.halt(); m.move_head(0,0,0); m.change_led(0,255,0)"
```

---

## 📝 Notes

- All animations are designed to be subtle and natural
- Dance moves are randomized for variety
- Eye expressions change based on context
- Battery saving is automatic and seamless
- All features can be disabled individually
- Thread-safe implementation prevents conflicts

---

## 🎉 Tips for Best Experience

1. **Let Misty dance!** Wait the full 2 minutes to see screensaver mode
2. **Adjust idle timeout** to your preference (30s to 600s)
3. **Enable battery saving** if you want Misty to run longer
4. **Keep animations on** for the most engaging experience
5. **Test with** `test_personality.py` before full deployment

---

## 📚 Technical Details

### Files Modified
- `personality_manager.py` - Main personality and animation logic
- `misty_aicco_assistant.py` - Integration with main assistant
- `config.py` - Configuration management
- `env.example` - Environment variable template

### Architecture
- **Idle Monitor Thread**: Tracks inactivity time
- **Screensaver Thread**: Runs dance routines
- **Callbacks**: Battery saving hooks for main system
- **Thread-Safe**: Proper locking and state management

### Performance
- Minimal CPU usage (event-driven)
- No impact on conversation latency
- Clean shutdown and restart
- Graceful error handling

---

Enjoy your dynamic, engaging Misty robot! 🤖✨

