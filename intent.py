"""
intent.py — Intent classification module using a local LLM via Ollama.

Parses transcribed text into a structured JSON intent object with retry logic.
"""

import json
import logging
import time

logger = logging.getLogger(__name__)

import ollama

OLLAMA_MODEL = "gemma3:4b"

SYSTEM_PROMPT = """\
You are an intent classifier for a voice-controlled file assistant.
Given a user's spoken command, respond with a JSON array containing one or more JSON objects representing the ordered intents.

Each JSON object in the array must have an "intent" key set to one of:
  - "create_file"  → also include "filename" (string)
  - "write_code"   → also include "filename" (string), "language" (string), "description" (string)
  - "summarize"    → also include "content" (string — the text to summarise)
  - "general_chat" → also include "message" (string — the user's message)

Rules:
• If the user asks to create a file, folder, or directory → "create_file".
• If the user asks to write, generate, or create code/script → "write_code".
• If the user asks to summarise, recap, or condense something → "summarize".
• For everything else (greetings, questions, chitchat) → "general_chat".
• If there are multiple actions, split them into multiple intent objects in the correct order.

Respond ONLY with the JSON array. No markdown, no explanation.
"""

STRICT_RETRY_PROMPT = """\
Your previous response was not a valid JSON array. Try again.
Classify the following user command into a JSON array of intent objects. Respond with ONLY the JSON — nothing else.

Example format:
[
  { "intent": "summarize", "content": "..." },
  { "intent": "create_file", "filename": "summary.txt" }
]

User command: {transcript}
"""


def classify_intent(transcript: str) -> list:
    """
    Classify a transcript into a structured list of intent dicts (compound commands).

    Uses Ollama's JSON mode and retries once with a stricter prompt if the
    first attempt fails to parse. Gracefully degrades to unknown on complete failure.
    """
    # --- First attempt ---
    try:
        logger.info("   Sending transcript to %s (attempt 1)…", OLLAMA_MODEL)
        t0 = time.perf_counter()
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            format="json",
        )
        elapsed = time.perf_counter() - t0
        raw = response["message"]["content"]
        logger.info("   LLM responded in %.2fs: %s", elapsed, raw[:200])
        result = json.loads(raw)
        if not isinstance(result, list):
            result = [result]

        for item in result:
            _validate(item)
            
        logger.info("   ✅ Intents parsed on first attempt: %d actions", len(result))
        return result
    except (json.JSONDecodeError, KeyError, ValueError) as e:
        logger.warning("   ⚠️  First attempt failed (%s), retrying…", e)

    # --- Retry with stricter prompt ---
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {
                    "role": "user",
                    "content": STRICT_RETRY_PROMPT.format(transcript=transcript),
                },
            ],
            format="json",
        )

        result = json.loads(response["message"]["content"])
        if not isinstance(result, list):
            result = [result]

        for item in result:
            _validate(item)
        
        logger.info("   ✅ Intents parsed on retry: %d actions", len(result))
        return result
    except Exception as e:
        logger.error("   ❌ Retry failed (%s). Returning unknown intent.", e)
        return [{"intent": "unknown", "raw": transcript}]


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {
    "create_file": ["filename"],
    "write_code": ["filename", "language", "description"],
    "summarize": ["content"],
    "general_chat": ["message"],
}


def _validate(obj: dict) -> None:
    """Raise ValueError if the intent object is missing required fields."""
    intent = obj.get("intent")
    if intent not in _REQUIRED_FIELDS:
        raise ValueError(f"Unknown intent: {intent!r}")
    for field in _REQUIRED_FIELDS[intent]:
        if field not in obj:
            raise ValueError(f"Missing field {field!r} for intent {intent!r}")
