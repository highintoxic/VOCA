"""
pipeline.py — Orchestrator that wires STT → Intent → Tools.

Provides `run_pipeline()` which is the single entry-point the UI calls.
"""

from stt import transcribe
from intent import classify_intent
from tools import dispatch


def run_pipeline(audio_input) -> dict:
    """
    Execute the full voice-agent pipeline.

    Parameters
    ----------
    audio_input : str or tuple
        Path to an audio file, or a (sample_rate, numpy_array) tuple
        from Gradio's microphone input.

    Returns
    -------
    dict
        {
            "transcript": str,
            "intent": dict,
            "action": str,
            "result": str
        }
    """
    result = {
        "transcript": "",
        "intent": {},
        "action": "",
        "result": "",
    }

    # --- Stage 1: Speech-to-Text ---
    try:
        stt_result = transcribe(audio_input)
        result["transcript"] = stt_result["text"]
    except Exception as e:
        result["result"] = f"❌ STT Error: {e}"
        return result

    # --- Stage 2: Intent Classification ---
    try:
        intent_obj = classify_intent(result["transcript"])
        result["intent"] = intent_obj
        result["action"] = intent_obj.get("intent", "unknown")
    except Exception as e:
        result["result"] = f"❌ Intent Classification Error: {e}"
        return result

    # --- Stage 3: Tool Execution ---
    try:
        result["result"] = dispatch(intent_obj)
    except Exception as e:
        result["result"] = f"❌ Tool Execution Error: {e}"

    return result
