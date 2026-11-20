"""Local speech-to-text for push-to-talk: audio never leaves this machine.

Uses faster-whisper (open-source Whisper on CTranslate2, CPU int8). The model is downloaded once
from Hugging Face on first use and cached locally; after that transcription runs offline. The
audio is written to a private temporary file only for decoding and deleted immediately.
"""
import os
import tempfile
import threading
import time

MODEL_NAME = os.environ.get("STT_MODEL", "base.en")
_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def transcribe(audio: bytes) -> dict:
    started = time.perf_counter()
    model = _load()
    fd, path = tempfile.mkstemp(suffix=".webm")
    try:
        os.fchmod(fd, 0o600)
        with os.fdopen(fd, "wb") as f:
            f.write(audio)
        segments, info = model.transcribe(path, language="en", beam_size=1, vad_filter=True)
        text = " ".join(s.text.strip() for s in segments).strip()
    finally:
        os.remove(path)
    return {
        "text": text,
        "engine": f"faster-whisper {MODEL_NAME} (local CPU)",
        "audio_bytes": len(audio),
        "audio_seconds": round(getattr(info, "duration", 0.0), 1),
        "ms": round((time.perf_counter() - started) * 1000),
        "audio_deleted": not os.path.exists(path),
        "left_device": False,
    }
