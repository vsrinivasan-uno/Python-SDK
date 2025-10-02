#!/usr/bin/env python3
"""OpenAI Realtime API Handler for Misty

Handles voice-to-voice communication using OpenAI's Realtime API.
This is faster than the traditional STT→GPT→TTS pipeline.

Author: Misty Robotics
Date: October 2, 2025
"""

import os
import sys
import time
import base64
import threading
import json
import logging
import io
from typing import Optional, Callable
import websocket


class RealtimeHandler:
    """OpenAI Realtime API handler for voice-to-voice communication.
    
    This handler manages a WebSocket connection to OpenAI's Realtime API,
    allowing for low-latency voice-to-voice conversations.
    """
    
    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-realtime-preview-2024-10-01",
        on_transcript_received: Optional[Callable[[str], None]] = None,
        on_audio_received: Optional[Callable[[bytes], None]] = None
    ):
        """Initialize the Realtime API handler.
        
        Args:
            api_key: OpenAI API key
            model: Realtime model to use
            on_transcript_received: Callback when transcript text is received
            on_audio_received: Callback when audio response is received
        """
        self.api_key = api_key
        self.model = model
        self.on_transcript_received = on_transcript_received
        self.on_audio_received = on_audio_received
        
        self.logger = logging.getLogger("RealtimeHandler")
        self.ws: Optional[websocket.WebSocketApp] = None
        self.running = False
        self.connected = False
        self.thread: Optional[threading.Thread] = None
        
        # Buffers for assembling streaming responses
        self.audio_buffers = {}  # response_id -> bytearray
        self.transcript_buffers = {}  # response_id -> str
        
    def connect(self):
        """Connect to the OpenAI Realtime API."""
        if self.connected:
            self.logger.warning("Already connected to Realtime API")
            return
        
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = [
            f"Authorization: Bearer {self.api_key}",
            "OpenAI-Beta: realtime=v1"
        ]
        
        self.logger.info(f"Connecting to Realtime API: {self.model}")
        
        self.ws = websocket.WebSocketApp(
            url,
            header=headers,
            on_message=self._on_message,
            on_error=self._on_error,
            on_close=self._on_close,
            on_open=self._on_open
        )
        
        # Start WebSocket in background thread
        self.thread = threading.Thread(
            target=self.ws.run_forever,
            kwargs={
                "ping_timeout": 10,
                "ping_interval": 15,
                "ping_payload": "keepalive"
            }
        )
        self.thread.daemon = True
        self.thread.start()
        
        # Wait for connection to open (max 5 seconds)
        timeout = 5.0
        waited = 0.0
        while not self.connected and waited < timeout:
            time.sleep(0.1)
            waited += 0.1
        
        if not self.connected:
            raise ConnectionError("Failed to connect to Realtime API within timeout")
        
        self.logger.info("✅ Connected to Realtime API")
        
        # Configure the session for audio input/output
        self._configure_session()
    
    def _configure_session(self):
        """Configure the session for audio input/output."""
        self.logger.info("📋 Configuring Realtime API session...")
        
        # Update session configuration (optimize for faster audio response)
        config_msg = {
            "type": "session.update",
            "session": {
                # Keep both modalities but minimize server work by disabling server VAD
                "modalities": ["text", "audio"],
                "instructions": "You are a helpful assistant. Keep responses concise and friendly.",
                "voice": "fable",
                "input_audio_format": "pcm16",  # Expect PCM16 at 24kHz
                "output_audio_format": "pcm16",  # Output PCM16 at 24kHz
                # Disable server-side transcription and VAD; we explicitly commit and request
                "input_audio_transcription": None,
                "turn_detection": None
            }
        }
        
        self._send_json(config_msg)
        self.logger.info("✅ Session configured")
    
    def disconnect(self):
        """Disconnect from the Realtime API."""
        if self.ws:
            self.ws.close()
        self.connected = False
        self.running = False
        self.logger.info("Disconnected from Realtime API")
    
    def _on_open(self, ws):
        """Called when WebSocket connection opens."""
        self.connected = True
        self.running = True
        self.logger.debug("Realtime WebSocket opened")
    
    def _on_close(self, ws, close_status_code, close_msg):
        """Called when WebSocket connection closes."""
        self.connected = False
        self.running = False
        self.logger.debug(f"Realtime WebSocket closed: {close_status_code} - {close_msg}")
    
    def _on_error(self, ws=None, error=None, *args, **kwargs):
        """Called when WebSocket error occurs.
        
        Note: Supports both old and new websocket-client API versions.
        """
        self.logger.error(f"Realtime WebSocket error: {error}")
    
    def _on_message(self, ws, message):
        """Called when a message is received from the Realtime API.
        
        Handles streaming audio and transcript deltas, assembling them
        into complete responses.
        """
        self.logger.debug(f"🔔 _on_message called (len={len(str(message)) if message else 0})")
        
        if message is None:
            self.logger.warning("⚠️ Received None message in _on_message")
            return
        
        try:
            data = json.loads(message)
            self.logger.debug(f"✅ Parsed JSON successfully")
        except Exception as e:
            self.logger.warning(f"❌ Received non-JSON message: {str(message)[:100]}")
            return
        
        event_type = data.get("type")
        
        # Debug: Log ALL event types to see what we're receiving
        self.logger.info(f"📨 Received event type: {event_type}")
        self.logger.debug(f"   Full event: {json.dumps(data, indent=2)[:500]}")
        
        # Extract response ID from various possible locations
        resp_id = self._extract_response_id(data)
        
        # Handle different event types
        if event_type == "response.audio.delta":
            self._handle_audio_delta(data, resp_id)
        
        elif event_type in ("response.audio_transcript.delta", "response.output_text.delta"):
            self._handle_transcript_delta(data, resp_id)
        
        elif event_type in ("response.done", "response.completed"):
            self._handle_response_complete(resp_id)
        
        elif "error" in data:
            self.logger.error(f"Realtime API error: {json.dumps(data, indent=2)}")
        
        else:
            # Log other event types at debug level
            self.logger.debug(f"Realtime event: {event_type}")
    
    def _extract_response_id(self, data: dict) -> str:
        """Extract response ID from event data."""
        # Try various possible locations
        if isinstance(data.get("response"), dict):
            resp_id = data["response"].get("id")
            if resp_id:
                return resp_id
        
        for key in ("response_id", "id"):
            if data.get(key):
                return data[key]
        
        return "default"
    
    def _handle_audio_delta(self, data: dict, resp_id: str):
        """Handle audio delta events."""
        # Extract base64-encoded audio from various possible fields
        b64_audio = None
        
        # Try top-level fields
        for key in ("audio", "delta", "data", "b64", "chunk"):
            value = data.get(key)
            if isinstance(value, str) and len(value) > 32:
                b64_audio = value
                break
        
        # Try nested delta object
        if not b64_audio and isinstance(data.get("delta"), dict):
            for key in ("audio", "b64", "data", "chunk"):
                value = data["delta"].get(key)
                if isinstance(value, str) and len(value) > 32:
                    b64_audio = value
                    break
        
        if b64_audio:
            try:
                chunk = base64.b64decode(b64_audio)
                if resp_id not in self.audio_buffers:
                    self.audio_buffers[resp_id] = bytearray()
                self.audio_buffers[resp_id].extend(chunk)
                
                self.logger.debug(f"Audio delta: {len(chunk)} bytes (total: {len(self.audio_buffers[resp_id])})")
            except Exception as e:
                self.logger.warning(f"Failed to decode audio delta: {e}")
    
    def _handle_transcript_delta(self, data: dict, resp_id: str):
        """Handle transcript delta events."""
        # Extract text from various possible fields
        text = None
        
        for key in ("text", "transcript", "content", "delta"):
            value = data.get(key)
            if isinstance(value, str) and value.strip():
                text = value
                break
        
        # Try nested delta object
        if not text and isinstance(data.get("delta"), dict):
            for key in ("text", "transcript", "content"):
                value = data["delta"].get(key)
                if isinstance(value, str) and value.strip():
                    text = value
                    break
        
        if text:
            if resp_id not in self.transcript_buffers:
                self.transcript_buffers[resp_id] = ""
            self.transcript_buffers[resp_id] += text
            
            self.logger.debug(f"Transcript delta: '{text}'")
    
    def _handle_response_complete(self, resp_id: str):
        """Handle response completion event."""
        # Get assembled transcript and audio
        transcript = self.transcript_buffers.pop(resp_id, "")
        audio_bytes = bytes(self.audio_buffers.pop(resp_id, b""))
        
        # Trigger callbacks
        if transcript and self.on_transcript_received:
            self.logger.info(f"✅ Transcript received: '{transcript}'")
            try:
                self.on_transcript_received(transcript)
            except Exception as e:
                self.logger.error(f"Error in transcript callback: {e}")
        
        if audio_bytes and self.on_audio_received:
            self.logger.info(f"✅ Audio received: {len(audio_bytes)} bytes")
            try:
                self.on_audio_received(audio_bytes)
            except Exception as e:
                self.logger.error(f"Error in audio callback: {e}")
    
    def _wav_to_pcm16(self, wav_bytes: bytes) -> bytes:
        """Convert WAV audio to PCM16 mono at 24kHz without audioop.
        
        - If 16-bit mono 24kHz: return as-is
        - If stereo: average channels
        - If sample rate != 24kHz: naive linear resample (good enough for speech)
        """
        import wave
        import array
        
        f = wave.open(io.BytesIO(wav_bytes), 'rb')
        channels = f.getnchannels()
        sampwidth = f.getsampwidth()
        sr = f.getframerate()
        n = f.getnframes()
        raw = f.readframes(n)
        f.close()
        
        self.logger.debug(f"WAV info: {channels}ch, {sampwidth*8}bit, {sr}Hz, {n} frames")
        
        # Ensure 16-bit little-endian samples array
        if sampwidth != 2:
            # Convert to 16-bit by simple scaling/truncation
            # Build array of original width, then map to 16-bit
            src = array.array('b' if sampwidth == 1 else 'h')
            src.frombytes(raw)
            # Normalize to float and re-quantize to int16
            if sampwidth == 1:
                # 8-bit unsigned to int16
                floats = [(x - 128) / 128.0 for x in src]
            else:
                maxv = float(2 ** (8 * sampwidth - 1) - 1)
                floats = [max(-1.0, min(1.0, x / maxv)) for x in src]
            int16 = array.array('h', [int(max(-32768, min(32767, v * 32767))) for v in floats])
            sampwidth = 2
        else:
            int16 = array.array('h')
            int16.frombytes(raw)
        
        # Deinterleave if stereo and downmix to mono by averaging
        if channels == 2:
            left = int16[0::2]
            right = int16[1::2]
            mono = array.array('h', [(l + r) // 2 for l, r in zip(left, right)])
        else:
            mono = int16
        
        # Resample to 24kHz using linear interpolation if needed
        target_sr = 24000
        if sr != target_sr and len(mono) > 1:
            import math
            ratio = target_sr / float(sr)
            out_len = int(math.floor(len(mono) * ratio))
            resampled = array.array('h')
            resampled.extend([0] * out_len)
            for i in range(out_len):
                # Map destination index to source position
                src_pos = i / ratio
                j = int(src_pos)
                frac = src_pos - j
                if j + 1 < len(mono):
                    a = mono[j]
                    b = mono[j + 1]
                    val = int(a + (b - a) * frac)
                else:
                    val = mono[j]
                # Clamp to int16
                if val > 32767:
                    val = 32767
                elif val < -32768:
                    val = -32768
                resampled[i] = val
            mono = resampled
        
        return mono.tobytes()
    
    def send_audio(self, audio_bytes: bytes):
        """Send audio to the Realtime API for processing.
        
        Args:
            audio_bytes: Audio data (WAV format)
        """
        if not self.connected:
            self.logger.error("Cannot send audio - not connected")
            return
        
        # Convert WAV to PCM16
        try:
            pcm_data = self._wav_to_pcm16(audio_bytes)
            self.logger.info(f"🎵 Converted WAV ({len(audio_bytes)} bytes) to PCM16 ({len(pcm_data)} bytes)")
        except Exception as e:
            self.logger.error(f"Failed to convert audio: {e}")
            return
        
        # Stream audio in chunks so server can start earlier
        chunk_size = 4800 * 2  # 4800 samples (~200ms at 24kHz) * 2 bytes
        total = len(pcm_data)
        sent = 0
        while sent < total:
            chunk = pcm_data[sent:sent+chunk_size]
            b64_audio = base64.b64encode(chunk).decode("ascii")
            msg = {
                "type": "input_audio_buffer.append",
                "audio": b64_audio
            }
            self._send_json(msg)
            sent += len(chunk)
        
        self.logger.info(f"📤 Sent PCM audio in chunks: {total} bytes total")
    
    def commit_audio(self):
        """Commit buffered audio for processing."""
        if not self.connected:
            self.logger.error("Cannot commit audio - not connected")
            return
        
        msg = {"type": "input_audio_buffer.commit"}
        self._send_json(msg)
        
        self.logger.info("📋 Committed audio buffer")
    
    def request_response(self, instructions: str = "Reply concisely as a helpful assistant."):
        """Request a response from the Realtime API.
        
        Args:
            instructions: Instructions for the AI response
        """
        if not self.connected:
            self.logger.error("Cannot request response - not connected")
            return
        
        msg = {
            "type": "response.create",
            "response": {
                "instructions": instructions,
                "modalities": ["text", "audio"]
            }
        }
        self._send_json(msg)
        
        self.logger.info(f"🤖 Requested response with modalities: ['text', 'audio']")
    
    def _send_json(self, payload: dict):
        """Send JSON message to the WebSocket."""
        if not self.ws:
            self.logger.error("Cannot send JSON - WebSocket not initialized")
            return
        
        if not self.connected:
            self.logger.error("Cannot send JSON - not connected")
            return
        
        try:
            msg = json.dumps(payload)
            self.logger.debug(f"📤 Sending: {payload.get('type', 'unknown')} - {len(msg)} chars")
            self.ws.send(msg)
            self.logger.debug(f"✅ Sent successfully")
        except Exception as e:
            self.logger.error(f"❌ Failed to send JSON: {e}")
            self.logger.error(f"   Payload type: {payload.get('type', 'unknown')}")
    
    def process_audio_file(self, audio_bytes: bytes):
        """Process a complete audio file through the Realtime API.
        
        With session VAD enabled, the API will automatically:
        1. Detect speech in the audio
        2. Transcribe it
        3. Generate a response
        4. Send back audio
        
        Args:
            audio_bytes: Audio data to process (WAV format)
        """
        # 1) Append audio buffer
        self.send_audio(audio_bytes)

        # 2) Commit buffer so the server knows input has ended
        #    This ensures a response is generated reliably across server configs
        try:
            self.commit_audio()
        except Exception as e:
            self.logger.error(f"Failed to commit audio buffer: {e}")
            return

        # 3) Explicitly request a response (text + audio)
        #    Even with server VAD enabled, requesting a response is the most
        #    reliable trigger for output across model versions.
        try:
            self.request_response(
                instructions=(
                    "Reply as a friendly assistant. Be concise and natural."
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to request response: {e}")
            return

        self.logger.info("🎤 Audio sent, committed, and response requested - awaiting output...")

