# Voice-Controlled Local AI Agent — Problem Statement & Task Breakdown

## Problem Statement

Modern AI tooling has made it increasingly feasible to run powerful speech and language models entirely on consumer hardware. However, most voice assistant pipelines either rely on cloud APIs (creating latency, privacy concerns, and internet dependency) or are poorly integrated — treating transcription, reasoning, and execution as disconnected steps rather than a unified local system.

The challenge is to design and implement a **fully local, privacy-preserving voice agent** that accepts spoken commands from a user, understands the intent behind those commands using a language model, and autonomously executes real actions on the local filesystem — all surfaced through a clean, interactive UI. The system must be robust enough to handle ambiguous speech, efficient enough to run on a mid-range consumer GPU, and safe enough to prevent unintended filesystem modifications.

---

## Objectives

- Build a complete voice-to-action pipeline that runs **entirely on local hardware** (no mandatory cloud dependency).
- Integrate a **Speech-to-Text (STT)** model to accurately transcribe microphone or uploaded audio.
- Use a **local Large Language Model (LLM)** to classify user intent and extract structured parameters from the transcription.
- Implement **tool execution** functions that act on the local filesystem safely and deterministically.
- Present the full pipeline — input, transcription, intent, action, and result — in a **unified web-based UI**.

---

## System Architecture Overview

The pipeline follows a strict linear flow:

```
Audio Input → STT (faster-whisper) → Transcribed Text
    → Intent Classification (Ollama LLM, JSON output)
    → Tool Dispatcher (Python switch logic)
    → Result (file created / code written / summary shown)
    → UI Display (Gradio)
```

Each stage is a discrete, independently testable module. No stage should have a hard dependency on the UI layer — the core pipeline must be usable as a standalone Python API.

---

## Task Breakdown

### Task 1 — Project Scaffold & Safety Constraints

**Goal:** Set up the repository structure and enforce the `output/` directory safety boundary before writing any feature code.

**Deliverables:**
- Repository with the following structure:
  ```
  project/
  ├── app.py          ← Gradio UI entry point
  ├── stt.py          ← STT wrapper module
  ├── intent.py       ← Intent classification module
  ├── tools.py        ← Tool execution functions
  ├── output/         ← ALL generated files restricted to this folder
  └── README.md
  ```
- A path sanitization utility in `tools.py` that:
  - Strips any `..` traversal sequences from filenames
  - Prefixes every output path with `output/`
  - Raises a clear exception if a caller attempts to write outside `output/`

**Acceptance Criteria:** No tool function can create or overwrite a file outside `output/` under any input.

---

### Task 2 — Speech-to-Text Module (`stt.py`)

**Goal:** Implement accurate, GPU-accelerated transcription using `faster-whisper`.

**Model:** `Whisper Large V3 Turbo` via `faster-whisper`, loaded with `device="cuda"` and `compute_type="int8"` quantization to minimise VRAM usage.

**Inputs supported:**
- **Microphone recording** — captured via `sounddevice` or `pyaudio`, saved as a temporary `.wav` file, then passed to the transcriber.
- **Uploaded audio file** — `.wav` or `.mp3` file path passed directly.

**Key implementation notes:**
- Load the model once at module import time (not on every call) so the GPU weights stay warm between requests.
- Return both the full transcribed string and a confidence/language field for display in the UI.
- Strip leading/trailing whitespace and collapse repeated spaces from the transcript.

**Acceptance Criteria:** Given a clear English audio clip of ≤30 seconds, the module returns an accurate transcript in under 5 seconds on the target hardware (RTX 4050).

---

### Task 3 — Intent Classification Module (`intent.py`)

**Goal:** Use a locally running LLM via Ollama to parse the transcribed text into a structured JSON intent object.

**Recommended model:** `qwen3:1.7b` or `llama3.2:3b` — small enough to coexist in VRAM with the Whisper model, fast enough for near-real-time response.

**Supported intents and required fields:**

| Intent Key | Required JSON Fields | Triggered When |
|---|---|---|
| `create_file` | `filename` | User asks to create an empty file or folder |
| `write_code` | `filename`, `language`, `description` | User asks to generate and save code |
| `summarize` | `content` | User asks to summarise provided text |
| `general_chat` | `message` | No actionable file/code intent detected |

**Structured output strategy:**
- Use a tightly scoped system prompt instructing the model to respond **only** with a valid JSON object — no prose, no markdown fences.
- Use Ollama's `format: "json"` API parameter to constrain output format at the inference level.
- Implement a fallback: if JSON parsing fails, re-send the transcript with a stricter one-shot prompt before raising an error.

**Acceptance Criteria:** Given 20 varied transcriptions covering all four intents, the module correctly classifies ≥18 of them with valid, parseable JSON output.

---

### Task 4 — Tool Execution Module (`tools.py`)

**Goal:** Implement one handler function per intent that takes the parsed JSON parameters and performs the appropriate local action.

**Tool functions:**

- **`create_file(filename: str) → str`**
  - Creates an empty file (or directory if the name ends with `/`) at `output/<filename>`.
  - Returns a success message: `"Created output/<filename>"`.

- **`write_code(filename: str, language: str, description: str) → str`**
  - Sends a code-only prompt to Ollama: *"Write {language} code that {description}. Respond with raw code only, no markdown."*
  - Strips any accidental code fences from the response.
  - Writes the code to `output/<filename>`.
  - Returns the written code as a string for display.

- **`summarize(content: str) → str`**
  - Sends the content to Ollama with a summarisation system prompt.
  - Returns the summary string (does not write to disk unless the user also requests a file).

- **`general_chat(message: str) → str`**
  - Passes the message to Ollama as a standard chat turn.
  - Returns the model's response string.

**Acceptance Criteria:** Each tool function is independently callable with mocked inputs in a unit test without requiring audio input or a running UI.

---

### Task 5 — Pipeline Orchestrator

**Goal:** Wire all modules together into a single callable function that the UI invokes.

```python
def run_pipeline(audio_input) -> dict:
    transcript = transcribe(audio_input)          # stt.py
    intent_obj = classify_intent(transcript)      # intent.py
    result = dispatch(intent_obj)                  # tools.py
    return {
        "transcript": transcript,
        "intent": intent_obj,
        "action": intent_obj["intent"],
        "result": result
    }
```

The orchestrator must:
- Handle and surface errors from any stage gracefully (never crash the UI).
- Return a structured dict so the UI layer has no knowledge of pipeline internals.

---

### Task 6 — Gradio UI (`app.py`)

**Goal:** Build a clean, functional web interface using `gr.Blocks` that exposes all pipeline stages visibly.

**UI Layout:**

```
┌──────────────────────────────────────────┐
│  🎙 Voice AI Agent                       │
├──────────────────────────────────────────┤
│  [ Audio Input — mic or file upload ]    │
│  [ Run Agent ] button                    │
├──────────────────────────────────────────┤
│  Transcription:  [ text box ]            │
│  Detected Intent:[ JSON display ]        │
│  Action Taken:   [ text label ]          │
│  Result/Output:  [ code / text box ]     │
└──────────────────────────────────────────┘
```

**Requirements:**
- Use `gr.Audio(sources=["microphone", "upload"])` to handle both input methods.
- Display the four pipeline outputs (`transcript`, `intent`, `action`, `result`) in separate, clearly labelled components.
- Show a loading spinner (Gradio handles this automatically with `gr.Button(loading=True)`) while the pipeline runs.
- All output components should be read-only and cleared on each new submission.

**Acceptance Criteria:** A non-technical user can record or upload audio, click Run, and see the full pipeline result displayed without any console interaction.

---

### Task 7 — README Documentation

**Goal:** Write a `README.md` that enables a fresh setup from zero.

**Required sections:**
- **System Requirements** — Python version, CUDA version, Ollama version, required VRAM
- **Installation** — step-by-step `pip install` and `ollama pull` commands
- **Running the App** — single command to launch
- **STT Decision Note** — if using an API-based fallback instead of local Whisper, explain the hardware limitation that motivated this choice
- **Pipeline Diagram** — an ASCII or Mermaid diagram of the data flow
- **Safety Note** — explain the `output/` directory restriction and why it exists
- **Example Interactions** — 3–4 example voice commands and their expected pipeline outputs

---

## Evaluation Criteria

| Criterion | Weight | What is Assessed |
|---|---|---|
| STT Accuracy | 20% | Transcription quality on test audio clips |
| Intent Classification | 25% | Correct JSON output across all four intent types |
| Tool Execution | 25% | Files created correctly, code is runnable, summaries are coherent |
| UI Completeness | 15% | All four pipeline stages visible, both input methods work |
| Code Quality & Safety | 15% | Path safety, modular structure, error handling, README clarity |

---

## Constraints & Rules

- All file and code generation **must** be restricted to the `output/` subdirectory — no exceptions.
- The STT model must be a HuggingFace-compatible or local model (`faster-whisper` counts). If an API is used instead, this must be documented with justification in the README.
- The LLM for intent classification must run locally via Ollama, LM Studio, or equivalent. Cloud LLM APIs are not permitted for the intent/tool layer.
- The UI must display all four pipeline stages — partial display does not satisfy the requirement.
- Python 3.10+ required. All dependencies must be installable via `pip` and listed in `requirements.txt`.

---

## Suggested Tech Stack

| Component | Recommended Choice | Why |
|---|---|---|
| STT | `faster-whisper` + `large-v3-turbo` | 4–6× faster than HuggingFace pipeline; INT8 CUDA; open-source |
| LLM | `qwen3:1.7b` via Ollama | Tiny VRAM footprint; strong JSON instruction-following |
| UI | Gradio (`gr.Blocks`) | Native `gr.Audio` mic+upload; designed for ML pipelines |
| Audio Capture | `sounddevice` | Lightweight; no system dependencies vs pyaudio |
| JSON Parsing | `json` stdlib + retry logic | Robust against occasional LLM formatting drift |

