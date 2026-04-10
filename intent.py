"""
intent.py — Intent classification module using a local LLM via Ollama.

Parses transcribed text into a structured JSON intent object with retry logic.
"""

import json

import ollama

OLLAMA_MODEL = "gemma3:4b"

SYSTEM_PROMPT = """\
You are an intent classifier for a voice-controlled file assistant.
Given a user's spoken command, respond with a single JSON object (no extra text).

The JSON must have an "intent" key set to one of:
  - "create_file"  → also include "filename" (string)
  - "write_code"   → also include "filename" (string), "language" (string), "description" (string)
  - "summarize"    → also include "content" (string — the text to summarise)
  - "general_chat" → also include "message" (string — the user's message)

Rules:
• If the user asks to create a file, folder, or directory → "create_file".
• If the user asks to write, generate, or create code/script → "write_code".
• If the user asks to summarise, recap, or condense something → "summarize".
• For everything else (greetings, questions, chitchat) → "general_chat".

Respond ONLY with the JSON object. No markdown, no explanation.
"""

STRICT_RETRY_PROMPT = """\
Your previous response was not valid JSON. Try again.
Classify the following user command into exactly ONE JSON object with an "intent"
key and the required fields. Respond with ONLY the JSON — nothing else.

User command: {transcript}
"""


def classify_intent(transcript: str) -> dict:
    """
    Classify a transcript into a structured intent dict.

    Uses Ollama's JSON mode and retries once with a stricter prompt if the
    first attempt fails to parse.
    """
    # --- First attempt ---
    try:
        response = ollama.chat(
            model=OLLAMA_MODEL,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": transcript},
            ],
            format="json",
        )
        result = json.loads(response["message"]["content"])
        _validate(result)
        return result
    except (json.JSONDecodeError, KeyError, ValueError):
        pass  # Fall through to retry

    # --- Retry with stricter prompt ---
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
    _validate(result)
    return result


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
