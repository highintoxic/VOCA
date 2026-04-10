"""
pipeline.py — Orchestrator that wires STT → Intent → Tools.

Provides `run_pipeline()` which is the single entry-point the UI calls.
"""

import logging
import time

from stt import transcribe
from intent import classify_intent
from tools import dispatch

logger = logging.getLogger(__name__)


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
        "results": [],
    }

    pipeline_start = time.perf_counter()
    logger.info("═" * 50)
    logger.info("🚀 Pipeline started")
    logger.info("   Audio input: %s", audio_input)

    # --- Stage 1: Speech-to-Text ---
    try:
        logger.info("─" * 40)
        logger.info("📢 Stage 1: Speech-to-Text")
        t0 = time.perf_counter()
        stt_result = transcribe(audio_input)
        elapsed = time.perf_counter() - t0
        result["transcript"] = stt_result["text"]
        logger.info("   ✅ Transcript: %s", stt_result["text"][:120])
        logger.info("   Language: %s (%.1f%% confidence)",
                    stt_result["language"],
                    stt_result["language_probability"] * 100)
        logger.info("   ⏱  STT took %.2fs", elapsed)
    except Exception as e:
        logger.error("   ❌ STT failed: %s", e, exc_info=True)
        result["result"] = f"❌ STT Error: {e}"
        return result

    # --- Stage 2: Intent Classification ---
    try:
        logger.info("─" * 40)
        logger.info("🧠 Stage 2: Intent Classification")
        t0 = time.perf_counter()
        intent_array = classify_intent(result["transcript"])
        elapsed = time.perf_counter() - t0
        logger.info("   ⏱  Classification took %.2fs", elapsed)
    except Exception as e:
        logger.error("   ❌ Intent classification failed: %s", e, exc_info=True)
        result["results"].append({
            "intent": {},
            "action": "error",
            "result": f"❌ Intent Classification Error: {e}"
        })
        return result

    # --- Stage 3: Tool Execution ---
    try:
        logger.info("─" * 40)
        logger.info("⚡ Stage 3: Tool Execution (%d actions)", len(intent_array))
        for intent_obj in intent_array:
            action = intent_obj.get("intent", "unknown")
            logger.info("   ▶ Executing action: %s", action)
            t0 = time.perf_counter()
            tool_res = dispatch(intent_obj)
            elapsed = time.perf_counter() - t0
            
            result["results"].append({
                "intent": intent_obj,
                "action": action,
                "result": tool_res
            })
            logger.info("   ✅ Executed %s in %.2fs. Result preview: %s", action, elapsed, str(tool_res)[:100])
    except Exception as e:
        logger.error("   ❌ Tool execution failed: %s", e, exc_info=True)
        result["results"].append({
            "intent": {"error": "framework_crash"},
            "action": "error",
            "result": f"❌ Tool Execution Error: {e}"
        })

    total = time.perf_counter() - pipeline_start
    logger.info("─" * 40)
    logger.info("🏁 Pipeline complete in %.2fs", total)
    logger.info("═" * 50)

    return result

def process_text_command(text_input: str) -> dict:
    """
    Execute the pipeline starting directly from text (bypassing STT).
    """
    result = {
        "transcript": text_input.strip(),
        "results": [],
    }

    pipeline_start = time.perf_counter()
    logger.info("═" * 50)
    logger.info("🚀 Text Pipeline started")
    logger.info("   Text input: %s", text_input[:120])

    # --- Stage 2: Intent Classification ---
    try:
        logger.info("─" * 40)
        logger.info("🧠 Stage 2: Intent Classification")
        t0 = time.perf_counter()
        intent_array = classify_intent(result["transcript"])
        elapsed = time.perf_counter() - t0
        logger.info("   ⏱  Classification took %.2fs", elapsed)
    except Exception as e:
        logger.error("   ❌ Intent classification failed: %s", e, exc_info=True)
        result["results"].append({
            "intent": {},
            "action": "error",
            "result": f"❌ Intent Classification Error: {e}"
        })
        return result

    # --- Stage 3: Tool Execution ---
    try:
        logger.info("─" * 40)
        logger.info("⚡ Stage 3: Tool Execution (%d actions)", len(intent_array))
        for intent_obj in intent_array:
            action = intent_obj.get("intent", "unknown")
            logger.info("   ▶ Executing action: %s", action)
            t0 = time.perf_counter()
            tool_res = dispatch(intent_obj)
            elapsed = time.perf_counter() - t0
            
            result["results"].append({
                "intent": intent_obj,
                "action": action,
                "result": tool_res
            })
            logger.info("   ✅ Executed %s in %.2fs. Result preview: %s", action, elapsed, str(tool_res)[:100])
    except Exception as e:
        logger.error("   ❌ Tool execution failed: %s", e, exc_info=True)
        result["results"].append({
            "intent": {"error": "framework_crash"},
            "action": "error",
            "result": f"❌ Tool Execution Error: {e}"
        })

    total = time.perf_counter() - pipeline_start
    logger.info("─" * 40)
    logger.info("🏁 Text Pipeline complete in %.2fs", total)
    logger.info("═" * 50)

    return result
