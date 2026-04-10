"""
stt.py — Speech-to-Text module using faster-whisper.

The model is loaded once at module level so GPU weights stay warm between
requests.  Transcription is done via the `transcribe()` function.
"""

import logging
import re
import time

logger = logging.getLogger(__name__)
from faster_whisper import WhisperModel
from errors import PipelineError

# ---------------------------------------------------------------------------
# Model loading (once, at import time)
# ---------------------------------------------------------------------------

logger.info("🔧 Loading faster-whisper model (large-v3-turbo, cuda, float16)…")
_load_start = time.perf_counter()
_model = WhisperModel(
    "large-v3-turbo",
    device="cuda",
    compute_type="float16",
)
logger.info("✅ Whisper model loaded in %.1fs", time.perf_counter() - _load_start)


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
    logger.info("   Transcribing: %s", audio_path)
    t0 = time.perf_counter()
    segments, info = _model.transcribe(audio_path, beam_size=5)
    segments = list(segments)

    if not segments:
        raise PipelineError("stt", "No speech detected. Please try again.")

    # Calculate mean logprob over segments
    mean_logprob = sum(segment.avg_logprob for segment in segments) / len(segments)

    # Collect all segment texts
    full_text = " ".join(segment.text for segment in segments)
    logger.info("   Segments collected in %.2fs", time.perf_counter() - t0)

    # Clean up: strip whitespace, collapse repeated spaces
    full_text = full_text.strip()
    full_text = re.sub(r"\s+", " ", full_text)

    if not full_text:
        raise PipelineError("stt", "No speech detected. Please try again.")

    return {
        "text": full_text,
        "language": info.language,
        "language_probability": round(info.language_probability, 3),
        "low_confidence": mean_logprob < -0.8,
    }
