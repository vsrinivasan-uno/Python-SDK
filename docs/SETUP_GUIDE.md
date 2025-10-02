# Misty Aicco Assistant - Setup Guide

This guide will help you set up and run the Misty Aicco Assistant.

## Prerequisites

- Misty II Robot connected to your network
- Python 3.8 or higher
- OpenAI API key ([Get one here](https://platform.openai.com/api-keys))

## Installation

1. **Clone or navigate to the project directory**
   ```bash
   cd /path/to/Python-SDK
   ```

2. **Install dependencies**
   ```bash
   pip install -r requirements.txt
   ```

3. **Configure environment variables**
   
   Copy the example environment file:
   ```bash
   cp env.example .env
   ```
   
   Edit `.env` and set your values:
   ```bash
   # Required
   MISTY_IP_ADDRESS=your.robot.ip.address
   OPENAI_API_KEY=sk-your-actual-api-key-here
   
   # Optional (defaults are provided)
   OPENAI_MODEL=gpt-4o-mini
   GREETING_COOLDOWN_SECONDS=300
   LOG_LEVEL=INFO
   ```

4. **Test configuration**
   ```bash
   python3 test_config.py
   ```
   
   You should see:
   ```
   ✅ Configuration loaded successfully!
   ✅ All configuration values accessible!
   ✅ ALL TESTS PASSED!
   ```

## Running the Assistant

Once configuration is complete and Task 1.2+ are implemented:

```bash
python3 misty_aicco_assistant.py
```

The assistant will:
1. Connect to your Misty robot
2. Start face recognition
3. Listen for the wake word "Hey Aicco"
4. Respond to voice queries using OpenAI

Press `Ctrl+C` to stop gracefully.

## Project Structure

```
Python-SDK/
├── misty_aicco_assistant.py  # Main application
├── config.py                  # Configuration management
├── env.example                # Environment variable template
├── requirements.txt           # Python dependencies
├── test_config.py            # Configuration test script
├── mistyPy/                  # Misty SDK (existing)
│   ├── Robot.py
│   ├── Events.py
│   └── RobotCommands.py
└── .cursor/
    └── scratchpad.md         # Project planning and progress
```

## Configuration Options

### Misty Robot
- `MISTY_IP_ADDRESS`: IP address of your Misty II robot

### OpenAI
- `OPENAI_API_KEY`: Your OpenAI API key (required)
- `OPENAI_MODEL`: Chat model (default: gpt-4o-mini)
- `OPENAI_WHISPER_MODEL`: STT model (default: whisper-1)
- `OPENAI_MAX_TOKENS`: Response length limit (default: 512)
- `OPENAI_TEMPERATURE`: Response creativity (default: 0.7)

### Face Recognition
- `FACE_RECOGNITION_ENABLED`: Enable face recognition (default: true)
- `GREETING_COOLDOWN_SECONDS`: Time between greetings (default: 300)

### Voice Assistant
- `VOICE_ASSISTANT_ENABLED`: Enable voice assistant (default: true)
- `WAKE_WORD`: Activation phrase (default: "Hey Aicco")
- `WAKE_WORD_SENSITIVITY`: Detection sensitivity 0.0-1.0 (default: 0.5)
- `SILENCE_THRESHOLD_SECONDS`: End of speech detection (default: 2.0)
- `MAX_RECORDING_SECONDS`: Maximum query length (default: 30)

### Logging
- `LOG_LEVEL`: DEBUG, INFO, WARNING, ERROR (default: INFO)
- `LOG_TO_FILE`: Enable file logging (default: true)
- `LOG_FILE_PATH`: Log file location (default: misty_assistant.log)

## Troubleshooting

### Configuration errors
- Make sure `.env` file exists and has valid values
- Check that OPENAI_API_KEY is set correctly
- Verify MISTY_IP_ADDRESS is reachable

### Import errors
- Run `pip install -r requirements.txt` to install dependencies
- Make sure you're using Python 3.8 or higher

### Connection issues
- Verify Misty robot is powered on and connected to network
- Check that the IP address is correct
- Ensure your computer can ping the Misty robot

## Development Status

**Current Status**: Phase 1 - Foundation & Setup

**Completed Tasks**:
- ✅ Task 1.1: Project Structure & Configuration

**Next Tasks**:
- Task 1.2: Wake Word Detection Solution Selection
- Task 2.1: Face Recognition Implementation
- Task 3.1: Audio Monitoring Implementation

See `.cursor/scratchpad.md` for detailed project plan and progress.

## Support

For issues with:
- **Misty SDK**: See [Misty Robotics Documentation](https://docs.mistyrobotics.com/)
- **OpenAI API**: See [OpenAI Documentation](https://platform.openai.com/docs)
- **This Project**: Check `.cursor/scratchpad.md` for implementation details

## License

Apache License 2.0 (inherited from Misty Python SDK)

