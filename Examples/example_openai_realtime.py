"""Misty -> OpenAI Realtime streaming client (prototype).
Streams short audio chunks from Misty to OpenAI Realtime WebSocket and prints transcripts/responses.
Requires: websocket-client, requests
"""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import time
import base64
import threading
import json
import io
import requests
import websocket
from mistyPy.Robot import Robot

OPENAI_ENV_VAR = "OPENAI_API_KEY"

def get_openai_key():
    key = os.environ.get(OPENAI_ENV_VAR)
    if not key:
        key = input("Enter OpenAI API key: ").strip()
    return key

class RealtimeWS:
    def __init__(self, api_key, model="gpt-4o-realtime-preview"):
        self.api_key = api_key
        self.model = model
        self.ws = None
        self.running = False
        self.open = False

    def connect(self):
        url = f"wss://api.openai.com/v1/realtime?model={self.model}"
        headers = [
            f"Authorization: Bearer {self.api_key}",
            "OpenAI-Beta: realtime=v1"
        ]
        self.ws = websocket.WebSocketApp(url,
                                         header=headers,
                                         on_message=self.on_message,
                                         on_error=self.on_error,
                                         on_close=self.on_close,
                                         on_open=self.on_open)
        self.thread = threading.Thread(target=self.ws.run_forever, kwargs={"ping_timeout":10})
        self.thread.daemon = True
        self.thread.start()
        # wait briefly for connection to open
        timeout = 5.0
        waited = 0.0
        while not self.open and waited < timeout:
            time.sleep(0.1)
            waited += 0.1
        if not self.open:
            print("Warning: websocket did not open within timeout.")

    def on_open(self, ws=None):
        self.open = True
        self.running = True
        print("Realtime websocket opened.")

    def on_message(self, ws, message):
        # Messages are JSON events; parse and buffer deltas for final assembly.
        try:
            data = json.loads(message)
        except Exception:
            print("Received non-json message:", message)
            return

        typ = data.get("type")
        # ensure buffers exist
        if not hasattr(self, "audio_buffers"):
            self.audio_buffers = {}        # response_id -> bytearray
            self.transcript_buffers = {}   # response_id -> str

        # helper to find a response id (fallback to 'default' when missing)
        resp_id = None
        if isinstance(data.get("response"), dict):
            resp_id = data["response"].get("id")
        if not resp_id:
            resp_id = data.get("response_id") or data.get("id") or "default"

        # Handle audio chunks (base64-encoded) and transcript/text deltas.
        if typ == "response.audio.delta":
            # Try to find base64-encoded audio inside common fields
            b64 = None
            # top-level fields
            for k in ("audio", "delta", "data", "b64", "chunk"):
                v = data.get(k)
                if isinstance(v, str) and len(v) > 32:
                    b64 = v
                    break
            # nested delta object
            if not b64 and isinstance(data.get("delta"), dict):
                for k in ("audio", "b64", "data", "chunk"):
                    v = data["delta"].get(k)
                    if isinstance(v, str) and len(v) > 32:
                        b64 = v
                        break
            if b64:
                try:
                    chunk = base64.b64decode(b64)
                    self.audio_buffers.setdefault(resp_id, bytearray()).extend(chunk)
                except Exception:
                    # If it fails, keep moving; don't spam full payload
                    pass
            print(f"Realtime audio delta (response={resp_id}, bytes={len(self.audio_buffers.get(resp_id, b''))})")

        elif typ == "response.audio_transcript.delta" or typ in ("response.output_text.delta", "response.delta", "transcript", "message"):
            # Extract text from likely fields (delta.text, text, transcript, content)
            text = None
            for k in ("text", "transcript", "content"):
                v = data.get(k)
                if isinstance(v, str) and v.strip():
                    text = v
                    break
            if text is None and isinstance(data.get("delta"), dict):
                for k in ("text", "transcript", "content"):
                    v = data["delta"].get(k)
                    if isinstance(v, str) and v.strip():
                        text = v
                        break
            if text:
                self.transcript_buffers.setdefault(resp_id, "")
                self.transcript_buffers[resp_id] += text
                # Print only the newly appended text to reduce noise
                print(f"Realtime transcript delta (response={resp_id}): {text}")
            else:
                # If no text found, print the raw event for debugging
                print("Realtime event:", json.dumps(data, indent=2))

        else:
            # Check for lifecycle/finalization events indicating the response is complete.
            completed = False
            # common explicit completed event types
            if typ in ("response.completed", "response.done", "response.ended"):
                completed = True
            # or status field inside response object
            if isinstance(data.get("response"), dict) and data["response"].get("status") in ("completed", "succeeded", "done"):
                completed = True

            if completed:
                # Print assembled transcript and write audio if available
                transcript = self.transcript_buffers.pop(resp_id, "")
                audio_bytes = bytes(self.audio_buffers.pop(resp_id, b""))
                if transcript:
                    print(f"Realtime final transcript (response={resp_id}):\n{transcript}")
                else:
                    print(f"Realtime final event for response={resp_id} (no transcript buffered)")

                if audio_bytes:
                    # save audio to a file for inspection/playback
                    try:
                        fname = f"realtime_response_{resp_id}.wav"
                        with open(fname, "wb") as f:
                            f.write(audio_bytes)
                        print(f"Saved assembled audio to {fname} ({len(audio_bytes)} bytes)")
                    except Exception as e:
                        print("Failed saving assembled audio:", e)
                return

            # show important lifecycle or error events briefly
            if "error" in data:
                print("Realtime error:", json.dumps(data, indent=2))
            else:
                if typ is not None:
                    print(f"Realtime event type: {typ}")

    def on_error(self, ws, error):
        print("Realtime websocket error:", error)

    def on_close(self, ws=None, close_status_code=None, close_msg=None):
        self.running = False
        self.open = False
        print("Realtime websocket closed.")

    def send_json(self, payload):
        if not self.ws:
            return
        try:
            # Debug: print payload before sending so we can detect unsupported params
            try:
                print("Sending payload:", json.dumps(payload))
            except Exception:
                print("Sending payload (non-serializable):", payload)
            self.ws.send(json.dumps(payload))
        except Exception as e:
            print("Failed to send json:", e)

    def send_audio_chunk(self, audio_bytes):
        """Send audio bytes (WAV/MP3) as base64 using input_audio_buffer.append"""
        b64 = base64.b64encode(audio_bytes).decode("ascii")
        msg = {"type":"input_audio_buffer.append", "audio": b64}
        self.send_json(msg)

    def commit_audio(self):
        self.send_json({"type":"input_audio_buffer.commit"})

    def request_transcription(self):
        """Request transcription/assistant response from buffered audio; request text-only output to avoid unsupported 'response.audio' parameter."""
        payload = {
            "type": "response.create",
            "response": {
                "instructions": "Transcribe the audio and reply concisely as the assistant.",
                "modalities": ["text"]
            }
        }
        self.send_json(payload)

def stream_from_misty(misty, ws_client, chunk_seconds=1, filename_prefix="rt_chunk"):
    idx = 0
    try:
        while True:
            fname = f"{filename_prefix}_{idx}.wav"
            # Start a short recording on Misty
            misty.start_recording_audio(fname)
            time.sleep(chunk_seconds)
            misty.stop_recording_audio()
            # slight delay for the robot to finalize the file
            time.sleep(0.1)
            # fetch file from the robot
            resp = misty.get_audio_file(fileName=fname, base64=True)
            b64 = None
            # Attempt to extract base64 from common Misty JSON shapes
            try:
                j = resp.json()
                if isinstance(j, dict) and "result" in j and isinstance(j["result"], dict):
                    b64 = j["result"].get("base64")
                if not b64:
                    for k in ("base64","data","file","fileBase64","fileData","audio"):
                        if k in j:
                            b64 = j[k]; break
                if not b64:
                    # fallback: take longest string value
                    candidate = None
                    for v in j.values():
                        if isinstance(v, str) and (candidate is None or len(v) > len(candidate)):
                            candidate = v
                    if candidate and len(candidate) > 100:
                        b64 = candidate
            except Exception:
                b64 = None

            # If we couldn't parse JSON, inspect raw bytes
            if not b64:
                try:
                    content = getattr(resp, "content", None)
                    if isinstance(content, (bytes, bytearray)) and len(content) > 4:
                        # If it's a WAV/MP3 header, stream raw bytes
                        if content[:4] == b'RIFF' or content[:3] == b'ID3' or content[:2] == b'\xff\xd8':
                            ws_client.send_audio_chunk(content)
                            ws_client.commit_audio()
                            ws_client.request_transcription()
                            idx += 1
                            continue
                    # Try text fallback
                    txt = resp.text
                    if txt and txt.strip():
                        if txt.strip().startswith("data:"):
                            b64 = txt.split("base64,")[-1]
                        elif len(txt.strip()) > 100:
                            b64 = txt.strip()
                except Exception:
                    pass

            if b64:
                if isinstance(b64, str) and b64.startswith("data:"):
                    b64 = b64.split("base64,")[-1]
                try:
                    audio_bytes = base64.b64decode(b64)
                except Exception:
                    audio_bytes = None
                if audio_bytes:
                    ws_client.send_audio_chunk(audio_bytes)
                    ws_client.commit_audio()
                    ws_client.request_transcription()
                else:
                    print("Could not decode chunk base64 for", fname)
            else:
                print("No base64/audio returned for chunk", fname)
            idx += 1
    except KeyboardInterrupt:
        print("Stopping Misty stream.")

def main():
    ip = input("Misty IP (default 10.66.239.83): ").strip() or "10.66.239.83"
    misty = Robot(ip)
    api_key = get_openai_key()
    if not api_key:
        print("OpenAI API key required.")
        return

    model = input("Realtime model (default gpt-4o-realtime-preview): ").strip() or "gpt-4o-realtime-preview"
    ws = RealtimeWS(api_key, model=model)
    ws.connect()

    print("Starting streaming from Misty to Realtime API. Ctrl+C to stop.")
    stream_from_misty(misty, ws, chunk_seconds=1)

if __name__ == "__main__":
    main()