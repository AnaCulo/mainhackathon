"""Local speech-to-text for push-to-talk: audio never leaves this machine.

Uses faster-whisper (open-source Whisper on CTranslate2, CPU int8). The model is downloaded once
from Hugging Face on first use and cached locally; after that transcription runs offline. The
audio is written to a private temporary file only for decoding and deleted immediately.

Settings were chosen on 20 Nov from a benchmark of generated workplace sentences (various voices,
0.4 s lead-in): small.en + beam 5 + workplace hotwords gave 1.3 % word error on sentences
(base.en beam 1: 2.9 %) at about 1.1 s per utterance. Override with STT_MODEL=base.en for speed.
A lone acronym ("CEO.") stays unreliable for every model; in a sentence it is recognised, and the
reporter always checks the text before sending.
"""
import os
import tempfile
import threading
import time

from .security import owner_only

MODEL_NAME = os.environ.get("STT_MODEL", "small.en")
HOTWORDS = ("CEO CFO COO CTO HR team lead supervisor manager controller invoice ledger "
            "purchase order sign-off procurement supplier forklift inspection pallets "
            "loading dock warehouse harassment fraud bribery whistleblower")
_model = None
_lock = threading.Lock()


def _load():
    global _model
    with _lock:
        if _model is None:
            from faster_whisper import WhisperModel

            _model = WhisperModel(MODEL_NAME, device="cpu", compute_type="int8")
    return _model


def unavailable_reason(exc: BaseException) -> str:
    """Map a load failure to a reason the page can explain. Never includes audio or text."""
    if isinstance(exc, ModuleNotFoundError):
        return "stt_not_installed"        # faster-whisper or a dependency was never installed
    if isinstance(exc, ImportError):
        return "stt_runtime_missing"      # installed, but a native library failed to load (Windows: DLL)
    return "stt_model_unavailable"        # the model could not be downloaded or opened


def warm_up():
    """Load the model in the background so the first spoken message is not slow."""
    if "PYTEST_CURRENT_TEST" in os.environ or os.environ.get("STT_WARMUP") == "0":
        return
    try:
        import faster_whisper  # noqa: F401
    except ImportError:
        return
    threading.Thread(target=_load, daemon=True).start()


def transcribe(audio: bytes) -> dict:
    started = time.perf_counter()
    model = _load()
    fd, path = tempfile.mkstemp(suffix=".audio")
    try:
        owner_only(fd, path)
        with os.fdopen(fd, "wb") as f:
            f.write(audio)
        segments, info = model.transcribe(
            path, language="en", beam_size=5, hotwords=HOTWORDS,
            vad_filter=True, condition_on_previous_text=False)
        text = " ".join(s.text.strip() for s in segments)
        # Whisper can end on a partial multi-byte token, which decodes to U+FFFD ("�").
        text = " ".join(text.replace("\ufffd", " ").split())
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
