"""
intent.py — Intent classification module using a local LLM via Ollama.

Parses transcribed text into a structured JSON intent object with retry logic.
"""

import json
import logging
import time
import httpx

from errors import PipelineError

logger = logging.getLogger(__name__)

import ollama


FORMAT_SCHEMA = {
  "type": "array",
  "items": {
    "type": "object",
    "properties": {
      "intent": {
        "type": "string",
                "enum": ["create_file", "write_file", "write_code", "summarize", "general_chat", "unknown"]
      },
      "filename": { "type": "string" },
    "mode": { "type": "string", "enum": ["overwrite", "append", "edit"] },
      "language": { "type": "string" },
      "description": { "type": "string" },
      "content": { "type": "string" },
      "message": { "type": "string" }
    },
    "required": ["intent"]
  }
}

SYSTEM_PROMPT = """\
You are an intent classifier for a voice-controlled file assistant.
Given a user's spoken command, respond with a JSON array containing one or more JSON objects representing the ordered intents.

Each JSON object in the array must have an "intent" key set to one of:
    - "create_file"  → also include "filename" (string)
    - "write_file"   → include "filename" (string), "content" (string), and optional "mode" ("overwrite" | "append" | "edit")
  - "write_code"   → also include "filename" (string), "language" (string), "description" (string)
  - "summarize"    → also include "content" (string — the text to summarise)
  - "general_chat" → also include "message" (string — the user's message)

Rules:
• If the user asks to create a file, folder, or directory → "create_file".
• If the user asks to write plain text/content to a file (notes, docs, markdown, text) → "write_file" with mode "overwrite" (default).
• If the user asks to add/append text to an existing file → "write_file" with mode "append".
• If the user asks to edit/update/modify/rewrite an existing text file → "write_file" with mode "edit" and put the edit request in "content".
• If the user asks to write, generate, or create code/script/program → "write_code".
• If the user asks to summarise, recap, or condense something → "summarize".
• For everything else (greetings, questions, chitchat) → "general_chat".
• If there are multiple actions, split them into multiple intent objects in the correct order.
• Prefer "write_file" over "write_code" when the request is not explicitly about code.

Example command: "Create a file called notes.txt and then write a python script called hello.py that prints hello"
Example output:
[
  { "intent": "create_file", "filename": "notes.txt" },
  { "intent": "write_code", "filename": "hello.py", "language": "python", "description": "print hello" }
]

Example command: "Write meeting notes to notes.txt saying project kickoff is at 10am"
Example output:
[
    { "intent": "write_file", "filename": "notes.txt", "mode": "overwrite", "content": "project kickoff is at 10am" }
]

Example command: "Edit notes.txt to change kickoff time to 11am and keep everything else"
Example output:
[
    { "intent": "write_file", "filename": "notes.txt", "mode": "edit", "content": "change kickoff time to 11am and keep everything else" }
]

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


def classify_intent(transcript: str, action_log=None, model: str = "gemma3:4b") -> list:
    """
    Classify a transcript into a structured list of intent dicts (compound commands).

    Uses Ollama's JSON mode and retries once with a stricter prompt if the
    first attempt fails to parse. Gracefully degrades to unknown on complete failure.
    """
    action_log = action_log or []
    
    # Inject recent context to help LLM resolve vague references ("that file")
    sys_prompt = SYSTEM_PROMPT
    if action_log:
        recent = action_log[-5:]
        ctx_lines = []
        for act in recent:
            if act["intent"] == "create_file":
                ctx_lines.append(f" - created file {act['filename']}")
            elif act["intent"] == "write_file":
                mode = act.get("mode", "overwrite")
                ctx_lines.append(f" - wrote text to {act['filename']} ({mode})")
            elif act["intent"] == "write_code":
                ctx_lines.append(f" - wrote code to {act['filename']} ({act.get('language', 'unknown')})")
        
        if ctx_lines:
            sys_prompt += "\n\nRecent actions this session (for resolving vague references like 'that file'):\n" + "\n".join(ctx_lines)

    # --- First attempt ---
    try:
        logger.info("   Sending transcript to %s (attempt 1)…", model)
        t0 = time.perf_counter()
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": sys_prompt},
                    {"role": "user", "content": transcript},
                ],
                format=FORMAT_SCHEMA,
            )
        except (httpx.ConnectError, ConnectionError) as e:
            raise PipelineError("intent", "Ollama is not running. Start it with `ollama serve`.")

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
        try:
            response = ollama.chat(
                model=model,
                messages=[
                    {"role": "system", "content": SYSTEM_PROMPT},
                    {
                        "role": "user",
                        "content": STRICT_RETRY_PROMPT.format(transcript=transcript),
                    },
                ],
                format=FORMAT_SCHEMA,
            )
        except (httpx.ConnectError, ConnectionError) as e:
            raise PipelineError("intent", "Ollama is not running. Start it with `ollama serve`.")

        result = json.loads(response["message"]["content"])
        if not isinstance(result, list):
            result = [result]

        for item in result:
            _validate(item)
        
        logger.info("   ✅ Intents parsed on retry: %d actions", len(result))
        return result
    except Exception as e:
        logger.error("   ❌ Retry failed (%s). Routing to fallback.", e)
        return [{"intent": "general_chat", "message": transcript}]


# ---------------------------------------------------------------------------
# Validation helper
# ---------------------------------------------------------------------------

_REQUIRED_FIELDS = {
    "create_file": ["filename"],
    "write_file": ["filename", "content"],
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
