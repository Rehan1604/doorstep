"""Optional local speech-to-text (faster-whisper, CPU, int8). Audio never leaves the machine."""
import importlib.util
import os
import tempfile

MODEL_SIZE = os.getenv("DOORSTEP_WHISPER", "base.en")
MAX_BYTES = 5_000_000
_model = None


class VoiceUnavailable(Exception):
    pass


def available() -> bool:
    return importlib.util.find_spec("faster_whisper") is not None


def transcribe(data: bytes) -> str:
    global _model
    if not available():
        raise VoiceUnavailable("faster-whisper not installed")
    from faster_whisper import WhisperModel

    if _model is None:
        _model = WhisperModel(MODEL_SIZE, device="cpu", compute_type="int8")
    with tempfile.NamedTemporaryFile(suffix=".webm", delete=False) as f:
        f.write(data)
        path = f.name
    try:
        segments, _ = _model.transcribe(path, beam_size=1, vad_filter=True)
        return " ".join(s.text.strip() for s in segments).strip()
    finally:
        os.unlink(path)
