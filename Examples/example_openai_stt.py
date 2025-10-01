"""Conversation bridge: Misty -> OpenAI (Whisper + GPT). Records speech on Misty, transcribes with Whisper,
sends transcript to GPT (gpt-5-mini) and has Misty speak the response."""
import os
import sys
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
import time
import base64
import io
import requests
from mistyPy.Robot import Robot

OPENAI_ENV_VAR = "OPENAI_API_KEY"

def get_openai_key():
    key = os.environ.get(OPENAI_ENV_VAR)
    if not key:
        key = input("Enter OpenAI API key: ").strip()
    return key

def fetch_audio_base64(misty, filename):
    """Obtain audio from Misty. Handles nested JSON like {"result":{"base64":"..."}} and returns
    either raw bytes (if response contains audio bytes) or a base64 string for decoding later."""
    print(f"Requesting audio file '{filename}' from robot...")
    resp = misty.get_audio_file(fileName=filename, base64=True)

    # Try JSON response first and handle common nesting patterns
    try:
        j = resp.json()
        # Common Misty response: {"result": {"base64": "..."}}
        if isinstance(j, dict) and "result" in j and isinstance(j["result"], dict):
            for k in ("base64", "file", "data", "audio", "fileBase64", "fileData"):
                if k in j["result"]:
                    return j["result"][k]
        # Top-level keys
        if isinstance(j, dict):
            for k in ("data", "file", "base64", "audio", "fileData", "fileBase64"):
                if k in j:
                    return j[k]
        # Fallback: find longest string value in the JSON (likely the base64)
        if isinstance(j, dict):
            candidate = None
            for v in j.values():
                if isinstance(v, str) and (candidate is None or len(v) > len(candidate)):
                    candidate = v
            if candidate and len(candidate) > 100:
                return candidate
    except Exception:
        # Not JSON or parse failed; continue to inspect raw content
        pass

    # Inspect raw content bytes (sometimes the robot returns raw WAV/MP3 bytes)
    content = getattr(resp, "content", None)
    if isinstance(content, (bytes, bytearray)) and len(content) > 4:
        if content[:4] == b'RIFF' or content[:3] == b'ID3' or content[:2] == b'\xff\xd8':
            return content

    # Try to parse textual content for data: URI or long base64 string
    text = None
    try:
        text = resp.text
    except Exception:
        try:
            text = content.decode('utf-8', errors='ignore') if isinstance(content, (bytes, bytearray)) else None
        except Exception:
            text = None
    if text:
        if text.strip().startswith("data:"):
            return text.split("base64,")[-1]
        if len(text.strip()) > 100:
            return text.strip()

    # Diagnostics for debugging robot response when nothing useful found
    try:
        print("Audio request status:", getattr(resp, "status_code", None))
        headers_preview = {k: resp.headers[k] for k in list(resp.headers.keys())[:6]} if hasattr(resp, "headers") else {}
        print("Response headers (preview):", headers_preview)
        text_preview = None
        try:
            text_preview = resp.text
        except Exception:
            try:
                text_preview = resp.content[:512]
            except Exception:
                text_preview = "<unreadable content>"
        if isinstance(text_preview, str):
            print("Response text (first 512 chars):", text_preview[:512])
        else:
            print("Response content (bytes) length:", len(resp.content) if hasattr(resp, "content") else "unknown")
    except Exception as e:
        print("Failed to inspect response object:", e)

    print("Failed to obtain base64 audio from robot response.")
    return None

def transcribe_with_openai(api_key, audio_bytes, filename="speech.wav"):
    print("Sending audio to OpenAI Whisper for transcription...")
    headers = {"Authorization": f"Bearer {api_key}"}
    files = {"file": (filename, io.BytesIO(audio_bytes), "audio/wav")}
    data = {"model": "whisper-1"}
    try:
        resp = requests.post("https://api.openai.com/v1/audio/transcriptions", headers=headers, files=files, data=data, timeout=60)
    except Exception as e:
        print("Error sending request to OpenAI:", e)
        return None

    if resp.status_code == 200:
        try:
            return resp.json().get("text", "")
        except Exception:
            return resp.text
    else:
        print("OpenAI transcription request failed:", resp.status_code, resp.text)
        return None

def chat_with_openai(api_key, user_message, model="gpt-5-mini"):
    print("Sending message to OpenAI chat model...")
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    payload = {"model": model, "messages": [{"role": "user", "content": user_message}], "max_completion_tokens": 512}
    try:
        resp = requests.post("https://api.openai.com/v1/chat/completions", headers=headers, json=payload, timeout=60)
    except Exception as e:
        print("OpenAI chat request failed:", e)
        return None

    if resp.status_code == 200:
        try:
            j = resp.json()
            return j["choices"][0]["message"]["content"].strip()
        except Exception as e:
            print("Failed parsing chat response:", e)
            return None
    else:
        print("Chat API error:", resp.status_code, resp.text)
        return None

def record_and_get_transcript(misty, api_key, filename="user_speech.wav", record_seconds=5):
    print(f"Recording {record_seconds}s to '{filename}' on robot...")
    misty.start_recording_audio(filename)
    time.sleep(record_seconds)
    misty.stop_recording_audio()
    time.sleep(0.5)

    b64_or_bytes = fetch_audio_base64(misty, filename)
    if not b64_or_bytes:
        return None

    if isinstance(b64_or_bytes, (bytes, bytearray)):
        audio_bytes = b64_or_bytes
    else:
        try:
            audio_bytes = base64.b64decode(b64_or_bytes)
        except Exception:
            audio_bytes = None

    if not audio_bytes:
        print("Failed to decode audio bytes.")
        return None

    return transcribe_with_openai(api_key, audio_bytes, filename)

def main():
    ip = input("Misty IP (default 10.66.239.83): ").strip() or "10.66.239.83"
    misty = Robot(ip)
    api_key = get_openai_key()
    if not api_key:
        print("OpenAI API key required.")
        return

    print("Press Enter to start recording, Ctrl+C to exit.")
    try:
        while True:
            input("Ready to record. Press Enter to record...")
            seconds = input("Record duration in seconds (default 5): ").strip()
            try:
                record_seconds = int(seconds) if seconds else 5
            except:
                record_seconds = 5

            transcript = record_and_get_transcript(misty, api_key, "user_speech.wav", record_seconds)
            if transcript:
                print("You said:", transcript)
                reply = chat_with_openai(api_key, transcript)
                if reply:
                    print("OpenAI reply:", reply)
                    try:
                        # Ask Misty to speak the reply using its TTS
                        misty.speak(reply, None, None, None, True, "openai-response")
                    except Exception as e:
                        print("Failed to have Misty speak:", e)
                else:
                    print("No reply from OpenAI.")
            else:
                print("No transcript available.")
    except KeyboardInterrupt:
        print("\nExiting.")

if __name__ == "__main__":
    main()