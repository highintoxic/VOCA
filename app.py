"""
app.py — Gradio web UI for the Voca voice agent.

Provides microphone and file-upload input, and displays all four pipeline
stages: Transcription, Intent, Action, and Result.
"""

import json
import tempfile
import os

import gradio as gr
import numpy as np
import soundfile as sf

from pipeline import run_pipeline


def _save_audio_to_temp(audio_input) -> str:
    """
    Convert Gradio audio input to a temporary WAV file path.

    Gradio returns either:
      - A file path (str) for uploaded files
      - A tuple (sample_rate, numpy_array) for microphone recordings
    """
    if isinstance(audio_input, str):
        return audio_input

    if isinstance(audio_input, tuple):
        sr, data = audio_input
        # Ensure the data is float32 for soundfile
        if data.dtype != np.float32:
            data = data.astype(np.float32)
            # Normalise int ranges to [-1, 1]
            if np.max(np.abs(data)) > 1.0:
                data = data / 32768.0
        tmp = tempfile.NamedTemporaryFile(suffix=".wav", delete=False)
        sf.write(tmp.name, data, sr)
        return tmp.name

    raise ValueError(f"Unsupported audio input type: {type(audio_input)}")


def process_audio(audio_input):
    """Run the full pipeline and return the four display outputs."""
    if audio_input is None:
        return (
            "⚠️ No audio provided. Please record or upload audio.",
            "{}",
            "",
            "",
        )

    try:
        audio_path = _save_audio_to_temp(audio_input)
        result = run_pipeline(audio_path)
    except Exception as e:
        return (f"❌ Error: {e}", "{}", "", "")
    finally:
        # Clean up temp file if we created one
        if isinstance(audio_input, tuple):
            try:
                os.unlink(audio_path)
            except Exception:
                pass

    return (
        result.get("transcript", ""),
        json.dumps(result.get("intent", {}), indent=2),
        result.get("action", ""),
        result.get("result", ""),
    )


# ---------------------------------------------------------------------------
# UI Layout
# ---------------------------------------------------------------------------

CUSTOM_CSS = """
.main-header {
    text-align: center;
    margin-bottom: 0.5rem;
}
.main-header h1 {
    background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
    -webkit-background-clip: text;
    -webkit-text-fill-color: transparent;
    font-size: 2.2rem;
    font-weight: 800;
    margin-bottom: 0.25rem;
}
.main-header p {
    color: #888;
    font-size: 1rem;
}
.output-panel {
    border-left: 3px solid #667eea;
    padding-left: 1rem;
}
"""

with gr.Blocks(
    title="Voca — Voice AI Agent",
    theme=gr.themes.Soft(
        primary_hue="indigo",
        secondary_hue="purple",
        neutral_hue="slate",
        font=gr.themes.GoogleFont("Inter"),
    ),
    css=CUSTOM_CSS,
) as app:

    # Header
    gr.HTML(
        """
        <div class="main-header">
            <h1>🎙️ Voca</h1>
            <p>Voice-Controlled Local AI Agent — fully private, fully local</p>
        </div>
        """
    )

    with gr.Row():
        # --- Left column: Input ---
        with gr.Column(scale=1):
            audio_input = gr.Audio(
                sources=["microphone", "upload"],
                type="numpy",
                label="Audio Input",
                elem_id="audio-input",
            )
            run_btn = gr.Button(
                "🚀 Run Agent",
                variant="primary",
                size="lg",
                elem_id="run-btn",
            )

        # --- Right column: Outputs ---
        with gr.Column(scale=2, elem_classes="output-panel"):
            transcript_box = gr.Textbox(
                label="📝 Transcription",
                interactive=False,
                lines=3,
                elem_id="transcript-output",
            )
            intent_box = gr.Code(
                label="🧠 Detected Intent",
                language="json",
                interactive=False,
                elem_id="intent-output",
            )
            action_box = gr.Textbox(
                label="⚡ Action Taken",
                interactive=False,
                elem_id="action-output",
            )
            result_box = gr.Code(
                label="📋 Result / Output",
                language="python",
                interactive=False,
                lines=12,
                elem_id="result-output",
            )

    # Wire the button
    run_btn.click(
        fn=process_audio,
        inputs=[audio_input],
        outputs=[transcript_box, intent_box, action_box, result_box],
    )


if __name__ == "__main__":
    app.launch()
