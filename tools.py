"""
tools.py — Tool execution functions for the Voca voice agent.

Every tool that writes to disk is sandboxed to the `output/` directory.
The safe_path() utility enforces this boundary.
"""

import logging
import os

logger = logging.getLogger(__name__)
from pathlib import Path

import ollama

# Resolve the output directory once at module level
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)

OLLAMA_MODEL = "gemma3:4b"


# ---------------------------------------------------------------------------
# Path safety
# ---------------------------------------------------------------------------

def safe_path(filename: str) -> Path:
    """
    Return an absolute Path inside OUTPUT_DIR for the given filename.

    Raises ValueError if the resolved path escapes the output directory.
    """
    # Strip path traversal sequences
    cleaned = filename.replace("..", "").replace("\\", "/")
    # Remove leading slashes so the join stays relative
    cleaned = cleaned.lstrip("/")

    if not cleaned:
        raise ValueError("Filename is empty after sanitization.")

    target = (OUTPUT_DIR / cleaned).resolve()

    # Ensure the resolved path is still inside OUTPUT_DIR
    if not str(target).startswith(str(OUTPUT_DIR.resolve())):
        logger.error("🚫 Path escape attempt blocked: %s → %s", filename, target)
        raise ValueError(
            f"Path escapes the output directory: {filename!r} → {target}"
        )

    logger.debug("   safe_path: %s → %s", filename, target)
    return target


# ---------------------------------------------------------------------------
# Tool functions
# ---------------------------------------------------------------------------

def create_file(filename: str) -> str:
    """Create an empty file (or directory if name ends with '/') in output/."""
    logger.info("   📁 create_file: %s", filename)
    path = safe_path(filename)

    if filename.endswith("/"):
        path.mkdir(parents=True, exist_ok=True)
        return f"📁 Created directory: {path.relative_to(Path(__file__).parent)}"
    else:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.touch()
        return f"📄 Created file: {path.relative_to(Path(__file__).parent)}"


def write_code(filename: str, language: str, description: str) -> str:
    """Generate code via Ollama and write it to output/<filename>."""
    logger.info("   💻 write_code: %s (%s) — %s", filename, language, description[:80])
    path = safe_path(filename)
    path.parent.mkdir(parents=True, exist_ok=True)

    prompt = (
        f"Write {language} code that {description}. "
        "Respond with raw code only — no markdown fences, no explanations."
    )

    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {"role": "system", "content": "You are a code generator. Output raw code only."},
            {"role": "user", "content": prompt},
        ],
    )

    code = response["message"]["content"]

    # Strip accidental markdown code fences
    if code.startswith("```"):
        lines = code.split("\n")
        # Remove first line (```lang) and last line (```)
        if lines[-1].strip() == "```":
            lines = lines[1:-1]
        else:
            lines = lines[1:]
        code = "\n".join(lines)

    path.write_text(code, encoding="utf-8")
    logger.info("   ✅ Code written to %s (%d chars)", path, len(code))
    return code


def summarize(content: str) -> str:
    """Summarise the given content using Ollama."""
    logger.info("   📄 summarize: %d chars of content", len(content))
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": (
                    "You are a concise summariser. Provide a clear, "
                    "well-structured summary of the user's text."
                ),
            },
            {"role": "user", "content": content},
        ],
    )
    return response["message"]["content"]


def general_chat(message: str) -> str:
    """Handle general conversation that has no actionable intent."""
    logger.info("   💬 general_chat: %s", message[:80])
    response = ollama.chat(
        model=OLLAMA_MODEL,
        messages=[
            {
                "role": "system",
                "content": "You are a helpful voice assistant. Be concise and friendly.",
            },
            {"role": "user", "content": message},
        ],
    )
    return response["message"]["content"]


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "create_file": lambda obj: create_file(obj["filename"]),
    "write_code": lambda obj: write_code(
        obj["filename"], obj["language"], obj["description"]
    ),
    "summarize": lambda obj: summarize(obj["content"]),
    "general_chat": lambda obj: general_chat(obj["message"]),
}


def dispatch(intent_obj: dict) -> str:
    """Route an intent object to the correct tool function."""
    intent_key = intent_obj.get("intent")
    handler = _TOOL_MAP.get(intent_key)

    if handler is None:
        logger.warning("   Unknown intent: %s", intent_key)
        return f"⚠️ Unknown intent: {intent_key!r}"

    logger.info("   Dispatching to tool: %s", intent_key)
    return handler(intent_obj)
