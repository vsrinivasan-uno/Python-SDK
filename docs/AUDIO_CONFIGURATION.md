# Audio Configuration Guide

This document explains the audio streaming/chunking configuration options available for the Misty Aicco Assistant in **realtime mode**.

## Overview

When using `VOICE_MODE=realtime`, audio responses from OpenAI can be handled in two ways:

1. **Chunked Streaming** (default) - Break audio into chunks and play them sequentially
2. **Single-File Playback** - Wait for complete audio, then play as one file

## Configuration Options

### 1. AUDIO_CHUNKING_ENABLED

**Type**: Boolean (`true` or `false`)  
**Default**: `true`  
**Description**: Master switch for audio streaming/chunking

- **`true`**: Enable chunked streaming (lower latency, better UX)
- **`false`**: Single-file playback (simpler, higher latency)

**When to disable:**
- Debugging playback issues
- Very unstable network (chunking requires multiple API calls)
- Prefer simplicity over performance

### 2. CHUNK_DURATION_SECONDS

**Type**: Float (seconds)  
**Default**: `6.0`  
**Description**: Size of each audio chunk in seconds

**Technical Details:**
- Chunk size calculated as: `chunk_bytes = duration * 48000`
- At 24kHz PCM16: 48,000 bytes = 1 second of audio
- Default (6s): ~288,000 bytes (~0.18 MB)

**Tuning Guide:**
| Duration | Chunk Size | Use Case |
|----------|------------|----------|
| 3.0s | ~0.09 MB | Fast network, short responses |
| 6.0s | ~0.18 MB | **Optimal balance** (recommended) |
| 10.0s | ~0.30 MB | Slow network, longer responses |

**Trade-offs:**
- **Smaller chunks** = Lower latency, more API calls, more potential gaps
- **Larger chunks** = Higher latency, fewer API calls, fewer gaps

⚠️ **Warning**: Very large chunks (>10s) may cause HTTP 500 errors on Misty!

### 3. PARALLEL_UPLOAD_ENABLED

**Type**: Boolean (`true` or `false`)  
**Default**: `true`  
**Description**: Pre-upload next chunk while playing current chunk

- **`true`**: Seamless transitions, minimal gaps between chunks
- **`false`**: Sequential upload, noticeable gaps between chunks

**When to disable:**
- Debugging upload/playback issues
- Very slow network (parallel operations might overwhelm it)
- Prefer simpler execution flow

## Usage Examples

### Example 1: Disable Chunking Entirely

For debugging or simplicity:

```bash
export AUDIO_CHUNKING_ENABLED=false
python run_assistant.py
```

**Result**: Waits for complete audio response, then plays as single file. Higher latency but simpler.

### Example 2: Smaller Chunks for Fast Network

If you have a fast, reliable network:

```bash
export AUDIO_CHUNKING_ENABLED=true
export CHUNK_DURATION_SECONDS=3.0
export PARALLEL_UPLOAD_ENABLED=true
python run_assistant.py
```

**Result**: Faster initial response (3s chunks), seamless playback.

### Example 3: Larger Chunks for Slow Network

If uploads are taking too long:

```bash
export AUDIO_CHUNKING_ENABLED=true
export CHUNK_DURATION_SECONDS=8.0
export PARALLEL_UPLOAD_ENABLED=true
python run_assistant.py
```

**Result**: Fewer chunks, fewer API calls, but slightly higher initial latency.

### Example 4: Sequential Upload (Debugging)

To isolate parallel upload issues:

```bash
export AUDIO_CHUNKING_ENABLED=true
export CHUNK_DURATION_SECONDS=6.0
export PARALLEL_UPLOAD_ENABLED=false
python run_assistant.py
```

**Result**: Chunks uploaded one at a time. Noticeable gaps, but simpler execution.

## Performance Comparison

### Latency Breakdown (6s chunks, good network)

**With Chunking Enabled** (default):
```
User speaks → (2s silence) → OpenAI processes → (3s) 
  → First chunk ready → Upload (0.5s) → Play → AUDIO STARTS (5.5s total)
  → Continue playing subsequent chunks seamlessly
```

**With Chunking Disabled**:
```
User speaks → (2s silence) → OpenAI processes → (7s for full response) 
  → Complete audio ready → Upload (2s) → Play → AUDIO STARTS (11s total)
```

**Improvement**: ~5.5 seconds faster with chunking! 🚀

## Troubleshooting

### HTTP 500 Errors During Playback

**Symptoms**: `❌ Playback failed: 500`

**Possible Causes**:
1. Chunk size too large (>10s)
2. Misty's storage full (files not being deleted)
3. Too many rapid API calls

**Solutions**:
1. Reduce chunk size: `export CHUNK_DURATION_SECONDS=5.0`
2. Check file cleanup logs: Look for deletion failures
3. Disable parallel upload temporarily: `export PARALLEL_UPLOAD_ENABLED=false`

### Audible Gaps Between Chunks

**Symptoms**: Noticeable pauses between sentence fragments

**Possible Causes**:
1. Parallel upload disabled
2. Slow network causing upload delays
3. Chunk size too small

**Solutions**:
1. Enable parallel upload: `export PARALLEL_UPLOAD_ENABLED=true`
2. Increase chunk size: `export CHUNK_DURATION_SECONDS=7.0`
3. Check network latency: `ping <MISTY_IP_ADDRESS>`

### Very Slow Upload Times

**Symptoms**: Logs show upload taking >10 seconds for 0.18 MB

**Cause**: Poor network connection to Misty

**Solutions**:
1. Move Misty closer to WiFi router
2. Check network: `ping <MISTY_IP_ADDRESS>` (should be <50ms)
3. Consider disabling chunking if network can't be improved

## Monitoring Configuration

Check your current configuration at startup:

```
[Voice Assistant]
  Voice Mode: realtime
    ↳ Pipeline: Voice → Voice (faster ~1-3s, realtime)
  Audio Chunking: True
    ↳ Chunk Duration: 6.0s (~0.18MB)
    ↳ Parallel Upload: True
```

Or if chunking is disabled:

```
[Voice Assistant]
  Voice Mode: realtime
    ↳ Pipeline: Voice → Voice (faster ~1-3s, realtime)
  Audio Chunking: False
    ↳ Single-file playback (simpler but higher latency)
```

## Best Practices

1. **Start with defaults**: The default configuration (6s chunks, parallel upload) is optimal for most scenarios.

2. **Adjust based on network**: Run `ping <MISTY_IP>` to check latency:
   - <50ms: Can use smaller chunks (3-4s)
   - 50-200ms: Stick with default (6s)
   - >200ms or packet loss: Use larger chunks (8-10s) or disable

3. **Monitor logs**: Watch for upload times and playback failures to tune settings.

4. **Test incremental changes**: Change one setting at a time to isolate impact.

## Related Environment Variables

See `.env.example` for all available configuration options, including:
- `VOICE_MODE` - Choose between "traditional" and "realtime"
- `MAX_RECORDING_SECONDS` - Maximum user recording length
- `CONVERSATION_MODE` - Enable continuous conversation

---

For more information, see:
- Main README: `../README.md`
- Scratchpad (development notes): `../.cursor/scratchpad.md`

