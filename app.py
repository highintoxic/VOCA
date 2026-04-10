"""
app.py — FastAPI backend for the Voca voice agent.

Serves a custom HTML/CSS/JS frontend and exposes a /api/process endpoint
that accepts audio files and returns the full pipeline result.
"""

import json
import os
import tempfile

import aiofiles
import uvicorn
from fastapi import FastAPI, UploadFile, File
from fastapi.responses import HTMLResponse, FileResponse
from fastapi.staticfiles import StaticFiles

from pipeline import run_pipeline

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
async def process_audio(audio: UploadFile = File(...)):
    """
    Accept an uploaded audio file, run the full pipeline, and return
    structured JSON with transcript, intent, action, and result.
    """
    # Save the uploaded file to a temp location
    suffix = os.path.splitext(audio.filename or ".wav")[1]
    tmp = tempfile.NamedTemporaryFile(suffix=suffix, delete=False)
    try:
        content = await audio.read()
        tmp.write(content)
        tmp.flush()
        tmp.close()

        result = run_pipeline(tmp.name)
    except Exception as e:
        result = {
            "transcript": "",
            "intent": {},
            "action": "",
            "result": f"❌ Error: {e}",
        }
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass

    return result


if __name__ == "__main__":
    uvicorn.run("app:app", host="0.0.0.0", port=7860, reload=False)
