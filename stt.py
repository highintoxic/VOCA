"""
stt.py — Speech-to-Text module using faster-whisper.

The model is loaded once at module level so GPU weights stay warm between
requests.  Transcription is done via the `transcribe()` function.
"""

import re
from faster_whisper import WhisperModel

# ---------------------------------------------------------------------------
# Model loading (once, at import time)
# ---------------------------------------------------------------------------

_model = WhisperModel(
    "large-v3-turbo",
    device="cuda",
    compute_type="float16",
)


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def transcribe(audio_path: str) -> dict:
    """
    Transcribe an audio file and return structured results.

    Parameters
    ----------
    audio_path : str
        Path to a .wav or .mp3 file.

    Returns
    -------
    dict
        {
            "text": str,               # Full transcription
            "language": str,           # Detected language code
            "language_probability": float  # Confidence 0-1
        }
    """
    segments, info = _model.transcribe(audio_path, beam_size=5)

    # Collect all segment texts
    full_text = " ".join(segment.text for segment in segments)

    # Clean up: strip whitespace, collapse repeated spaces
    full_text = full_text.strip()
    full_text = re.sub(r"\s+", " ", full_text)

    return {
        "text": full_text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
    }
