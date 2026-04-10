"""
tools.py — Tool execution functions for the Voca voice agent.

Every tool that writes to disk is sandboxed to the `output/` directory.
The safe_path() utility enforces this boundary.
"""

import logging
import os
import httpx

logger = logging.getLogger(__name__)
from pathlib import Path

import ollama
from errors import PipelineError

# Resolve the output directory once at module level
OUTPUT_DIR = Path(__file__).parent / "output"
OUTPUT_DIR.mkdir(exist_ok=True)


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

def _chat(*args, **kwargs):
    """Wrapper to catch Ollama connection errors."""
    try:
        return ollama.chat(*args, **kwargs)
    except (httpx.ConnectError, ConnectionError) as e:
        raise PipelineError("tool", "Ollama is not running. Start it with `ollama serve`.")

def create_file(filename: str) -> str:
    """Create an empty file (or directory if name ends with '/') in output/."""
    logger.info("   📁 create_file: %s", filename)
    path = safe_path(filename)

    try:
        if filename.endswith("/"):
            path.mkdir(parents=True, exist_ok=True)
            return f"📁 Created directory: {path.relative_to(Path(__file__).parent)}"
        else:
            path.parent.mkdir(parents=True, exist_ok=True)
            path.touch()
            return f"📄 Created file: {path.relative_to(Path(__file__).parent)}"
    except OSError as e:
        raise PipelineError("tool", f"OS file permission error: {e}")


def write_code(filename: str, language: str, description: str, chat_context: list, model: str) -> str:
    """Generate code via Ollama and write it to output/<filename>."""
    logger.info("   💻 write_code: %s (%s) — %s", filename, language, description[:80])
    path = safe_path(filename)
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
    except OSError as e:
        raise PipelineError("tool", f"OS file permission error: {e}")

    prompt = (
        f"Write {language} code that {description}. "
        "Respond with raw code only — no markdown fences, no explanations."
    )
    
    messages = [{"role": "system", "content": "You are a code generator. Output raw code only."}]
    if chat_context:
        messages.extend(chat_context)
    messages.append({"role": "user", "content": prompt})
    response = _chat(
        model=model,
        messages=messages,
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

    try:
        path.write_text(code, encoding="utf-8")
    except OSError as e:
        raise PipelineError("tool", f"OS file permission error: {e}")
        
    chat_context.append({"role": "user", "content": f"Write {language} code that {description} to {filename}"})
    chat_context.append({"role": "assistant", "content": f"I have written the code to {filename} successfully."})
    while len(chat_context) > 20:
        chat_context.pop(0)

    logger.info("   ✅ Code written to %s (%d chars)", path, len(code))
    return code


def summarize(content: str, model: str) -> str:
    """Summarise the given content using Ollama."""
    logger.info("   📄 summarize: %d chars of content", len(content))
    response = _chat(
        model=model,
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


def general_chat(message: str, chat_context: list, model: str) -> str:
    """Handle general conversation that has no actionable intent."""
    logger.info("   💬 general_chat: %s", message[:80])
    
    messages = [{"role": "system", "content": "You are a helpful voice assistant. Be concise and friendly."}]
    if chat_context:
        messages.extend(chat_context)
    messages.append({"role": "user", "content": message})
    response = _chat(
        model=model,
        messages=messages,
    )
    
    reply = response["message"]["content"]
    
    chat_context.append({"role": "user", "content": message})
    chat_context.append({"role": "assistant", "content": reply})
    while len(chat_context) > 20:
        chat_context.pop(0)
        
    return reply


# ---------------------------------------------------------------------------
# Dispatcher
# ---------------------------------------------------------------------------

_TOOL_MAP = {
    "create_file": lambda obj, ctx, model: create_file(obj["filename"]),
    "write_code": lambda obj, ctx, model: write_code(
        obj["filename"], obj["language"], obj["description"], ctx, model
    ),
    "summarize": lambda obj, ctx, model: summarize(obj["content"], model),
    "general_chat": lambda obj, ctx, model: general_chat(obj["message"], ctx, model),
}


def dispatch(intent_obj: dict, chat_context: list = None, model: str = "gemma3:4b") -> str:
    """Route an intent object to the correct tool function."""
    if chat_context is None:
        chat_context = []
        
    intent_key = intent_obj.get("intent")
    handler = _TOOL_MAP.get(intent_key)

    if handler is None:
        logger.warning("   Unknown intent: %s", intent_key)
        raise PipelineError("tool", f"Intent '{intent_key}' is not supported. Try rephrasing.")

    logger.info("   Dispatching to tool: %s", intent_key)
    return handler(intent_obj, chat_context, model)
