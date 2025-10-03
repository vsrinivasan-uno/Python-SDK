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
from collections import deque


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
        on_audio_received: Optional[Callable[[bytes], None]] = None,
        chunk_ms: int = 100,
        use_audioop: bool = True,
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
        # Streaming configuration: how many milliseconds per chunk (smaller -> faster time-to-first-byte)
        # Default 100ms -> at 24kHz samples_per_ms = 24 -> 2400 samples -> 4800 bytes
        self.chunk_ms = int(chunk_ms)
        self.use_audioop = bool(use_audioop)
        # Outgoing send queue for reliable delivery
        self.send_queue = deque()  # items: (payload_dict, attempt_count, next_try_ts)
        self.send_lock = threading.Lock()
        self.sender_thread: Optional[threading.Thread] = None
        self.paused_until = 0.0  # timestamp until which sending is paused (rate limits)
        self.max_send_retries = 5
        # Start sender background thread
        self._start_sender_thread()
        
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

    def _start_sender_thread(self):
        """Start background thread that drains the send queue."""
        if self.sender_thread and self.sender_thread.is_alive():
            return

        def _loop():
            self.logger.debug("Sender thread started")
            while True:
                try:
                    self._sender_loop()
                except Exception as e:
                    # Keep sender thread alive on unexpected errors
                    self.logger.error(f"Sender thread error: {e}", exc_info=True)
                    time.sleep(1)

        self.sender_thread = threading.Thread(target=_loop, daemon=True)
        self.sender_thread.start()
    
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
                "voice": "sage",
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
        # If socket-level broken pipe / connection issues, attempt reconnect
        try:
            err_str = str(error or "")
            if "Broken pipe" in err_str or "[Errno 32]" in err_str or isinstance(error, OSError):
                self.logger.info("Detected broken pipe or OSError - scheduling reconnect")
                # Mark as disconnected and schedule reconnect
                self.connected = False
                # Try reconnect asynchronously (non-blocking)
                threading.Thread(target=self._attempt_reconnect_with_backoff, daemon=True).start()
        except Exception:
            pass
    
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

        # Handle rate limit events specifically
        if event_type == "rate_limits.updated":
            # Pause outgoing sends until rate limit resets (if provided)
            pause_secs = 0
            # Common possible fields: retry_after (seconds), reset_after_ms
            if isinstance(data.get("retry_after"), (int, float)):
                pause_secs = int(data.get("retry_after"))
            elif isinstance(data.get("reset_after_ms"), (int, float)):
                pause_secs = int(data.get("reset_after_ms") / 1000.0)
            else:
                # try nested limits
                limits = data.get("limits") or {}
                if isinstance(limits, dict):
                    # pick smallest reset hint available
                    for k in ("reset_after_ms", "retry_after"):
                        v = limits.get(k)
                        if isinstance(v, (int, float)):
                            if k.endswith("ms"):
                                pause_secs = int(v / 1000.0)
                            else:
                                pause_secs = int(v)
                            break

            if pause_secs <= 0:
                pause_secs = 60  # default 60s if unspecified

            self.paused_until = time.time() + pause_secs
            self.logger.warning(f"Rate limit updated - pausing sends for {pause_secs}s")
        
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
        """Convert WAV audio to PCM16 mono at 24kHz.
        
        - If 16-bit mono 24kHz: return as-is
        - If stereo: average channels
        - If sample rate != 24kHz: naive linear resample (good enough for speech)
        """
        import wave
        import array
        # Try to use audioop for faster conversions when available and allowed
        try:
            import audioop
        except Exception:
            audioop = None
        
        f = wave.open(io.BytesIO(wav_bytes), 'rb')
        channels = f.getnchannels()
        sampwidth = f.getsampwidth()
        sr = f.getframerate()
        n = f.getnframes()
        raw = f.readframes(n)
        f.close()
        
        self.logger.debug(f"WAV info: {channels}ch, {sampwidth*8}bit, {sr}Hz, {n} frames")
        
        # Fast path using audioop when available and requested
        if self.use_audioop and audioop is not None:
            try:
                # If input is already 16-bit, just ensure correct channels and rate
                if sampwidth == 2:
                    samples = raw
                else:
                    # Convert sample width to 2 (sampwidth param is bytes)
                    samples = audioop.lin2lin(raw, sampwidth, 2)

                # Downmix stereo to mono if needed
                if channels == 2:
                    samples = audioop.tomono(samples, 2, 0.5, 0.5)

                # Resample to 24000 Hz if needed
                target_sr = 24000
                if sr != target_sr:
                    samples = audioop.ratecv(samples, 2, 1, sr, target_sr, None)[0]

                return samples
            except Exception as e:
                # Fall back to pure-Python implementation below
                self.logger.debug(f"audioop fast path failed: {e}")

        # Fallback pure-Python path (original behavior)
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
        
        # Stream audio in chunks so server can start earlier. Chunk size derived from `chunk_ms`.
        # samples_per_ms = 24 (24000 samples/sec -> 24 samples/ms)
        samples_per_ms = 24
        chunk_size = samples_per_ms * self.chunk_ms * 2  # samples * bytes_per_sample
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
        # Prefer enqueueing into the send queue and let background sender handle retries
        try:
            self._enqueue_json(payload)
        except Exception as e:
            self.logger.error(f"Failed to enqueue payload for sending: {e}", exc_info=True)

    def _enqueue_json(self, payload: dict, attempt: int = 0, delay: float = 0.0):
        """Add a payload to the send queue with optional initial delay."""
        next_try = time.time() + float(delay)
        with self.send_lock:
            self.send_queue.append((payload, int(attempt), next_try))
        # Ensure the sender thread is running
        self._start_sender_thread()

    def _sender_loop(self):
        """Drain the send queue, sending messages with retries and honoring rate limits."""
        # If not connected, wait briefly and retry
        now = time.time()
        if time.time() < self.paused_until:
            # Respect rate limit pause
            sleep_for = max(0.1, self.paused_until - time.time())
            time.sleep(sleep_for)
            return

        with self.send_lock:
            if not self.send_queue:
                # Nothing to do
                time.sleep(0.05)
                return
            payload, attempt, next_try = self.send_queue.popleft()

        if time.time() < next_try:
            # Not yet time to try this item - requeue and back off
            with self.send_lock:
                self.send_queue.appendleft((payload, attempt, next_try))
            time.sleep(0.05)
            return

        if not self.ws or not self.connected:
            # If disconnected, requeue with backoff and attempt reconnect
            backoff = min(60, (2 ** attempt))
            self.logger.debug(f"Socket not connected, requeueing payload (attempt={attempt}) backoff={backoff}s")
            with self.send_lock:
                self.send_queue.append((payload, attempt + 1, time.time() + backoff))
            # Trigger reconnect attempt asynchronously
            threading.Thread(target=self._attempt_reconnect_with_backoff, daemon=True).start()
            time.sleep(0.1)
            return

        # Try to send now
        try:
            msg = json.dumps(payload)
            self.logger.debug(f"📤 Sending from queue: {payload.get('type', 'unknown')} - {len(msg)} chars")
            self.ws.send(msg)
            self.logger.debug("✅ Sent successfully from queue")
        except Exception as e:
            self.logger.error(f"❌ Failed to send queued JSON: {e}")
            # On failure, decide whether to retry
            if attempt < self.max_send_retries:
                backoff = min(60, (2 ** attempt))
                with self.send_lock:
                    self.send_queue.append((payload, attempt + 1, time.time() + backoff))
                # If failure looks like connection issue, schedule reconnect
                err_str = str(e)
                if "Broken pipe" in err_str or "[Errno 32]" in err_str or isinstance(e, OSError):
                    self.connected = False
                    threading.Thread(target=self._attempt_reconnect_with_backoff, daemon=True).start()
            else:
                self.logger.error(f"Dropping payload after {attempt} attempts: {payload.get('type', 'unknown')}")

    def _attempt_reconnect_with_backoff(self, max_attempts: int = 6):
        """Attempt to reconnect with exponential backoff. Non-blocking caller."""
        attempt = 0
        while attempt < max_attempts and not self.connected:
            wait = min(60, 2 ** attempt)
            self.logger.info(f"Attempting Realtime API reconnect (attempt {attempt+1}) in {wait}s")
            time.sleep(wait)
            try:
                # If ws exists, close it first
                try:
                    if self.ws:
                        self.ws.close()
                except Exception:
                    pass
                # Try to establish a fresh connection
                self.connect()
                if self.connected:
                    self.logger.info("Reconnect successful")
                    return True
            except Exception as e:
                self.logger.debug(f"Reconnect attempt {attempt+1} failed: {e}")
            attempt += 1
        self.logger.error("Failed to reconnect to Realtime API after multiple attempts")
        return False
    
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
                    """System Prompt for UNO AI Program Assistant
You are an official virtual assistant for the University of Nebraska Omaha (UNO), specifically focused on providing information about UNO and its Bachelor of Science in Artificial Intelligence (BSAI) program.
Your Role and Scope
Your ONLY purpose is to discuss:

University of Nebraska Omaha (UNO) - its campus, facilities, rankings, and general information
The Bachelor of Science in Artificial Intelligence (BSAI) program offered by UNO
The College of Information Science and Technology at UNO

You must STRICTLY operate within the provided knowledge base below. You do NOT have information about:

Other universities or their programs
Other degree programs at UNO beyond what's mentioned in your knowledge base
General AI topics, tutorials, or technical explanations unrelated to the BSAI program
Current events, news, or information outside your knowledge base
Personal advice unrelated to the UNO BSAI program

Knowledge Base
UNIVERSITY OF NEBRASKA OMAHA (UNO)
Basic Information:

Location: Omaha, Nebraska (41.259°N 96.006°W)
Website: https://www.unomaha.edu/
Type: Public Research University (R2: High research activity)
Established: 1908
Part of: University of Nebraska system
Campus: 3 campuses (Dodge, Scott, Center), urban setting, 88 acres
Student Enrollment: Approximately 9,910 full-time students

Academic Structure:

6 colleges offering 200+ degree programs
Strong focus on Information Science, Technology, and Computer Science

Rankings & Recognition:

#1 public university in the US for veterans
Affordable tuition among Nebraska's four-year institutions
High employability focus for students

Resources & Opportunities:

Modern facilities for engineering, IT, business, and biomechanics
Extensive partnerships with 1,000+ organizations for community engagement
Service learning opportunities
Internships and research centers
AI-powered career development tools


BACHELOR OF SCIENCE IN ARTIFICIAL INTELLIGENCE (BSAI)
Program Details:

College: College of Information Science and Technology
Department: Computer Science
Program Start: Spring 2025
Distinction: First AI bachelor's program in Nebraska, one of few in the Midwest
Catalog: https://catalog.unomaha.edu/undergraduate/college-information-science-technology/computer-science/ai-bs/#fouryearplantext

Program Mission:

Prepare graduates as AI specialists, leaders, and innovators
Bridge theory and real-world industry applications
Target students interested in machine learning, data science, generative AI, and ethical AI application
Hands-on curriculum with emphasis on practical experience

Curriculum Areas:

Machine Learning
Data Analysis and Mining
Neural Networks & Deep Learning
Natural Language Processing (NLP)
Computer Vision
Robotics & Autonomous Systems
Algorithm Development
AI Ethics and Society
Interdisciplinary electives (business, psychology, philosophy)

Special Features:

Real-world project collaborations with Omaha tech sector
Research opportunities at UNO AI Research Center
Access to industry internships and community initiatives
Student organizations for AI, tech, and professional development

Career Outcomes:
Graduates can pursue roles such as:

AI Engineer
Machine Learning Engineer
Data Scientist
Robotics Engineer
NLP Specialist
Computer Vision Engineer
AI Research Scientist

Job Market:

AI jobs projected to grow over 30% in the next decade
AI specialist jobs carry up to 25% wage premium in some markets

Admission & Progression:

Direct, standard application through UNO portal
Open for new enrollment
Pathways into accelerated Master's programs (5-year BS/MS)
All backgrounds welcome
Foundational primer courses available for students without prior computing experience

Industry Connections:

Partnerships with Omaha Chamber of Commerce
Collaborations with local and national tech firms
AI-powered career advising
Immersive job training experiences


CONTACT INFORMATION
College of Information Science and Technology

Phone: (402) 554-3819
Email: istt@unomaha.edu
Address: PKI 280, 1110 South 67th Street, Omaha, NE 68182

Communication Style
CRITICAL: Keep responses short, crisp, and conversational

Write like you're having a natural conversation, not giving a presentation
Use 2-4 sentences for most responses
Break up longer information into digestible chunks
Avoid walls of text and long paragraphs
Don't list everything at once - share what's relevant to their question
Use a friendly, casual tone while staying professional
It's okay to follow up with "Want to know more about [specific topic]?" to keep it interactive

Example of good response style:
"The BSAI program starts Spring 2025 and it's actually the first AI bachelor's degree in Nebraska! You'll get hands-on experience with machine learning, NLP, computer vision, and more. What aspect interests you most?"
Example of what to avoid:
Long paragraphs listing every single detail about the curriculum, requirements, and career outcomes all at once.
Response Guidelines
When responding to questions within your scope:

Be helpful and conversational
Answer directly and concisely
Share 1-3 key points, not everything at once
Ask follow-up questions to keep the conversation flowing
Use natural language, not formal/robotic phrasing
Direct to contact info only when they need specific help (applications, detailed questions)

When users ask questions OUTSIDE your scope:
Keep it brief and friendly:

"I'm focused on UNO's AI program specifically. What would you like to know about it?"
"That's outside my wheelhouse! I'm here for questions about UNO and our BSAI degree. Anything I can help with there?"
"I only cover UNO's AI bachelor's program. For other programs, check out unomaha.edu or call (402) 554-3819."

Topics to redirect:

Other universities → "I only know about UNO. You'd want to reach out to them directly!"
Other degree programs → "I specialize in our AI program. For other UNO programs, visit unomaha.edu."
General AI tutorials → "I'm here to discuss our academic program, not tech support. Want to know what AI topics we cover in class?"
Specific admission cases → "Best to contact istt@unomaha.edu or call (402) 554-3819 for that!"

Important Rules

NEVER make up information not in your knowledge base
NEVER discuss other universities or compare programs
NEVER provide technical AI assistance or coding help
NEVER give definitive admission decisions
ALWAYS stay within the scope of UNO and the BSAI program
ALWAYS keep responses short and conversational
ALWAYS be honest when you don't have information

Keep it natural, keep it brief, keep it helpful!RetryClaude can make mistakes. Please double-check responses."""
                )
            )
        except Exception as e:
            self.logger.error(f"Failed to request response: {e}")
            return

        self.logger.info("🎤 Audio sent, committed, and response requested - awaiting output...")

