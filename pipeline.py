"""
pipeline.py — Orchestrator that wires STT → Intent → Tools.

Provides `run_pipeline()` which is the single entry-point the UI calls.
"""

import logging
import time

from stt import transcribe
from intent import classify_intent
from tools import dispatch
from errors import PipelineError
import datetime

logger = logging.getLogger(__name__)

def _log_action(action_log, intent_obj, transcript=""):
    action = intent_obj.get("intent", "unknown")
    if action in {"error", "unknown"}:
        return
    log_entry = {
        "timestamp": datetime.datetime.now().strftime("%H:%M:%S"),
        "transcript": transcript or "Confirmed action",
        "intent": action,
        "filename": intent_obj.get("filename", ""),
        "status": "success"
    }
    action_log.append(log_entry)


def run_pipeline(audio_input, action_log=None, chat_context=None, llm_model: str = "gemma3:4b") -> dict:
    """
    Execute the full voice-agent pipeline.
    """
    result = {
        "transcript": "",
        "results": [],
        "requires_confirmation": False,
        "confirmation_message": "",
        "pending_intents": [],
        "action_log": action_log or [],
        "chat_context": chat_context or [],
    }

    pipeline_start = time.perf_counter()
    logger.info("═" * 50)
    logger.info("🚀 Pipeline started")
    logger.info("   Audio input: %s", audio_input)

    try:
        # --- Stage 1: Speech-to-Text ---
        logger.info("─" * 40)
        logger.info("📢 Stage 1: Speech-to-Text")
        t0 = time.perf_counter()
        stt_result = transcribe(audio_input)
        elapsed = time.perf_counter() - t0
        result["transcript"] = stt_result["text"]
        if stt_result.get("low_confidence"):
            result["low_confidence"] = True
            
        logger.info("   ✅ Transcript: %s", stt_result["text"][:120])
        logger.info("   Language: %s (%.1f%% confidence)",
                    stt_result["language"],
                    stt_result["language_probability"] * 100)
        logger.info("   ⏱  STT took %.2fs", elapsed)

        # --- Stage 2: Intent Classification ---
        logger.info("─" * 40)
        logger.info("🧠 Stage 2: Intent Classification")
        t0 = time.perf_counter()
        intent_array = classify_intent(result["transcript"], result["action_log"], llm_model)
        elapsed = time.perf_counter() - t0
        logger.info("   ⏱  Classification took %.2fs", elapsed)

        # --- Stage 3: Tool Execution ---
        logger.info("─" * 40)
        logger.info("⚡ Stage 3: Tool Execution (%d actions)", len(intent_array))
        for intent_obj in intent_array:
            action = intent_obj.get("intent", "unknown")
            
            if action in {"create_file", "write_file", "write_code"}:
                logger.info("   ⏸ Holding action for confirmation: %s", action)
                result["pending_intents"].append(intent_obj)
                continue
                
            logger.info("   ▶ Executing action: %s", action)
            t0 = time.perf_counter()
            tool_res = dispatch(intent_obj, result["chat_context"], llm_model)
            elapsed = time.perf_counter() - t0
            
            result["results"].append({
                "intent": intent_obj,
                "action": action,
                "result": tool_res
            })
            _log_action(result["action_log"], intent_obj, result["transcript"])
            logger.info("   ✅ Executed %s in %.2fs. Result preview: %s", action, elapsed, str(tool_res)[:100])
            
        if result["pending_intents"]:
            result["requires_confirmation"] = True
            parts = []
            for item in result["pending_intents"]:
                fname = item.get("filename", "unknown_file")
                if item.get("intent") == "create_file":
                    parts.append(f"{fname} (empty)")
                elif item.get("intent") == "write_file":
                    parts.append(f"{fname} (text {item.get('mode', 'overwrite')})")
                else:
                    parts.append(f"{fname} ({item.get('language', 'code')} code)")
            joined_files = ", ".join(parts)
            result["confirmation_message"] = f"About to write {len(result['pending_intents'])} file(s): {joined_files}. Proceed?"
            
    except PipelineError as e:
        logger.error("   ❌ Pipeline Error [%s]: %s", e.stage, e.message)
        return {"error": True, "stage": e.stage, "message": e.message}
    except Exception as e:
        logger.error("   ❌ Unhandled exception: %s", e, exc_info=True)
        return {"error": True, "stage": "framework", "message": f"Unhandled error: {e}"}

    total = time.perf_counter() - pipeline_start
    logger.info("─" * 40)
    logger.info("🏁 Pipeline complete in %.2fs", total)
    logger.info("═" * 50)

    return result

def process_text_command(text_input: str, action_log=None, chat_context=None, llm_model: str = "gemma3:4b") -> dict:
    """
    Execute the pipeline starting directly from text (bypassing STT).
    """
    result = {
        "transcript": text_input.strip(),
        "results": [],
        "requires_confirmation": False,
        "confirmation_message": "",
        "pending_intents": [],
        "action_log": action_log or [],
        "chat_context": chat_context or [],
    }

    pipeline_start = time.perf_counter()
    logger.info("═" * 50)
    logger.info("🚀 Text Pipeline started")
    logger.info("   Text input: %s", text_input[:120])

    try:
        # --- Stage 2: Intent Classification ---
        logger.info("─" * 40)
        logger.info("🧠 Stage 2: Intent Classification")
        t0 = time.perf_counter()
        intent_array = classify_intent(result["transcript"], result["action_log"], llm_model)
        elapsed = time.perf_counter() - t0
        logger.info("   ⏱  Classification took %.2fs", elapsed)

        # --- Stage 3: Tool Execution ---
        logger.info("─" * 40)
        logger.info("⚡ Stage 3: Tool Execution (%d actions)", len(intent_array))
        for intent_obj in intent_array:
            action = intent_obj.get("intent", "unknown")
            
            if action in {"create_file", "write_file", "write_code"}:
                logger.info("   ⏸ Holding action for confirmation: %s", action)
                result["pending_intents"].append(intent_obj)
                continue
                
            logger.info("   ▶ Executing action: %s", action)
            t0 = time.perf_counter()
            tool_res = dispatch(intent_obj, result["chat_context"], llm_model)
            elapsed = time.perf_counter() - t0
            
            result["results"].append({
                "intent": intent_obj,
                "action": action,
                "result": tool_res
            })
            _log_action(result["action_log"], intent_obj, result["transcript"])
            logger.info("   ✅ Executed %s in %.2fs. Result preview: %s", action, elapsed, str(tool_res)[:100])
            
        if result["pending_intents"]:
            result["requires_confirmation"] = True
            parts = []
            for item in result["pending_intents"]:
                fname = item.get("filename", "unknown_file")
                if item.get("intent") == "create_file":
                    parts.append(f"{fname} (empty)")
                elif item.get("intent") == "write_file":
                    parts.append(f"{fname} (text {item.get('mode', 'overwrite')})")
                else:
                    parts.append(f"{fname} ({item.get('language', 'code')} code)")
            joined_files = ", ".join(parts)
            result["confirmation_message"] = f"About to write {len(result['pending_intents'])} file(s): {joined_files}. Proceed?"
            
    except PipelineError as e:
        logger.error("   ❌ Pipeline Error [%s]: %s", e.stage, e.message)
        return {"error": True, "stage": e.stage, "message": e.message}
    except Exception as e:
        logger.error("   ❌ Unhandled exception: %s", e, exc_info=True)
        return {"error": True, "stage": "framework", "message": f"Unhandled error: {e}"}

    total = time.perf_counter() - pipeline_start
    logger.info("─" * 40)
    logger.info("🏁 Text Pipeline complete in %.2fs", total)
    logger.info("═" * 50)

    return result

def execute_intents(intent_array: list, action_log=None, chat_context=None, llm_model: str = "gemma3:4b") -> dict:
    """
    Directly execute an array of intents. Used for Stage 2 confirmation.
    """
    result = {
        "results": [],
        "action_log": action_log or [],
        "chat_context": chat_context or [],
    }
    logger.info("═" * 50)
    logger.info("🚀 Executing Confirmed Intents (%d actions)", len(intent_array))
    
    try:
        for intent_obj in intent_array:
            action = intent_obj.get("intent", "unknown")
            logger.info("   ▶ Executing action: %s", action)
            t0 = time.perf_counter()
            tool_res = dispatch(intent_obj, result["chat_context"], llm_model)
            elapsed = time.perf_counter() - t0
            
            result["results"].append({
                "intent": intent_obj,
                "action": action,
                "result": tool_res
            })
            _log_action(result["action_log"], intent_obj)
            logger.info("   ✅ Executed %s in %.2fs", action, elapsed)
    except PipelineError as e:
        logger.error("   ❌ Pipeline Error [%s]: %s", e.stage, e.message)
        return {"error": True, "stage": e.stage, "message": e.message}
    except Exception as e:
        logger.error("   ❌ Unhandled exception: %s", e, exc_info=True)
        return {"error": True, "stage": "framework", "message": f"Unhandled error: {e}"}
        
    logger.info("═" * 50)
    return result
