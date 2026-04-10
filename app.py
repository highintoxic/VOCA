"""
app.py — FastAPI backend for the Voca voice agent.

Serves a custom HTML/CSS/JS frontend and exposes a /api/process endpoint
that accepts audio files and returns the full pipeline result.
"""

import json
import logging
import os
import sys
import tempfile
import time

import aiofiles
import uvicorn
from fastapi import FastAPI, UploadFile, File, Request, Form
from fastapi.responses import HTMLResponse, FileResponse
from pydantic import BaseModel

# ---------------------------------------------------------------------------
# Logging configuration — must be set up before any module imports that log
# ---------------------------------------------------------------------------

LOG_FORMAT = (
    "%(asctime)s │ %(levelname)-7s │ %(name)-12s │ %(message)s"
)
DATE_FORMAT = "%H:%M:%S"

def setup_logging():
    """Configure root logger with a clean, readable format."""
    root = logging.getLogger()
    root.setLevel(logging.INFO)

    # Clear existing handlers (e.g. from uvicorn pre-config)
    root.handlers.clear()

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(logging.INFO)
    handler.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=DATE_FORMAT))
    root.addHandler(handler)

    # Quieten noisy third-party loggers
    logging.getLogger("uvicorn.access").setLevel(logging.WARNING)
    logging.getLogger("uvicorn.error").setLevel(logging.INFO)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("faster_whisper").setLevel(logging.INFO)

setup_logging()
logger = logging.getLogger(__name__)
from fastapi.staticfiles import StaticFiles

logger.info("🎙️  Voca — Voice AI Agent starting up…")
logger.info("   Loading pipeline modules (this triggers model downloads)…")

from pipeline import run_pipeline

logger.info("✅ All modules loaded. Server ready to accept requests.")

app = FastAPI(title="Voca — Voice AI Agent")

# Serve static files (CSS, JS)
STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
os.makedirs(STATIC_DIR, exist_ok=True)
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.get("/", response_class=HTMLResponse)
async def index():
    """Serve the main UI page."""
    html_path = os.path.join(STATIC_DIR, "index.html")
    async with aiofiles.open(html_path, "r", encoding="utf-8") as f:
        return await f.read()


@app.post("/api/process")
async def process_audio(
    audio: UploadFile = File(...),
    state: str = Form('{"action_log": [], "chat_context": []}')
):
    """
    Accept an uploaded audio file, run the full pipeline, and return
    structured JSON with transcript, intent, action, and result.
    """
    try:
        state_obj = json.loads(state)
        action_log = state_obj.get("action_log", [])
        chat_context = state_obj.get("chat_context", [])
    except json.JSONDecodeError:
        action_log = []
        chat_context = []
    # Save the uploaded file to a temp location
    suffix = os.path.splitext(audio.filename or ".wav")[1]
    logger.info("📥 Received audio upload: %s (%s)", audio.filename, suffix)
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await audio.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()
        size_kb = len(content) / 1024
        logger.info("   Saved to temp file: %s (%.1f KB)", tmp.name, size_kb)

        t0 = time.perf_counter()
        result = run_pipeline(tmp.name, action_log, chat_context)
        elapsed = time.perf_counter() - t0
        logger.info("📤 Returning result (total API time: %.2fs)", elapsed)
    except Exception as e:
        logger.error("❌ Unhandled error in /api/process: %s", e, exc_info=True)
        return {
            "error": True,
            "stage": "api",
            "message": str(e)
        }
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return result

class TextRequest(BaseModel):
    text: str
    action_log: list = []
    chat_context: list = []

@app.post("/api/process_text")
async def process_text_api(request: TextRequest):
    """
    Accept raw text input, bypass STT, and run the pipeline.
    """
    from pipeline import process_text_command
    try:
        t0 = time.perf_counter()
        result = process_text_command(request.text, request.action_log, request.chat_context)
        elapsed = time.perf_counter() - t0
        logger.info("📤 Returning result (total API time: %.2fs)", elapsed)
        return result
    except Exception as e:
        logger.error("❌ Unhandled error in /api/process_text: %s", e, exc_info=True)
        return {
            "error": True,
            "stage": "api",
            "message": str(e)
        }

class ConfirmRequest(BaseModel):
    intents: list[dict]
    action_log: list = []
    chat_context: list = []

@app.post("/api/confirm_intents")
async def confirm_intents_api(request: ConfirmRequest):
    """
    Accept an array of confirmed intents directly from the UI and execute them.
    """
    from pipeline import execute_intents
    try:
        t0 = time.perf_counter()
        result = execute_intents(request.intents, request.action_log, request.chat_context)
        elapsed = time.perf_counter() - t0
        logger.info("📤 Returning confirmed execution result (total API time: %.2fs)", elapsed)
        return result
    except Exception as e:
        logger.error("❌ Unhandled error in /api/confirm_intents: %s", e, exc_info=True)
        return {
            "error": True,
            "stage": "api",
            "message": str(e)
        }

if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
