# Voca — Local Voice AI Agent

Voca is a fully local, privacy-preserving voice-controlled AI assistant. It allows you to use voice commands or text to interface entirely with your local machine, creating files, generating code, summarizing text, and chatting conversationally, with complete local execution bounding your private footprint.

---

## ⚡ Architecture

Voca uses a decentralized state architecture with a clean separation of concerns split between an asynchronous pipeline and frontend-driven session state tracking.

### The Pipeline (`pipeline.py`)
At its core, Voca processes inputs sequentially through three major stages:
1. **Speech-To-Text (STT):** Uses `faster-whisper` (`large-v3-turbo`) to transcribe spoken `.wav` buffers into clean textual commands. Low confidence scores (`avg_logprob < -0.8`) natively trigger gracefully degraded warnings on the frontend.
2. **Intent Classification (`intent.py`):** Uses an Ollama-powered local LLM (dynamically chosen via the UI dropdown!). A structured schema prompts the model to generate a strictly formatted JSON array of actionable "intents" in order.
3. **Tool Dispatcher (`tools.py`):** Takes validated intents and maps them to pure Python deterministic functions inside a completely sandboxed `output/` directory, preventing catastrophic system overwrites. Code generation invokes the LLM again for pure codebase derivation.

### Frontend Driven Memory (`script.js`) 
Instead of relying on unstable backend caching, Voca pushes the concept of an **Action Log** and a **Chat Context** directly into the frontend. 
- The client ships its entire session contextual footprint (`actionLogState`, `chatContextState`) to the backend via POST form data with every invocation. 
- The backend evaluates, edits, and fires it back asynchronously. Multi-turn reference resolutions (e.g. *"summarize that python script you just made"*) resolves cleanly because the LLM is primed via the Action Log context appended to the base system prompt payload!

---

## 🔄 User Workflow

When using Voca, interactions follow a clear, predictable flow that ensures control and safety over automated computer interactions. 

1. **Input Generation:** You interact through the browser via the microphone, raw text commands, or by uploading existing `.wav` files directly.
2. **Analysis and Extraction:** The STT engine transcribes your audio, and the intent classifier determines exactly what code should be generated or what files should be modified.
3. **Execution Block & Human-In-The-Loop:** If the requested command triggers any write operations to your local hard drive (e.g. `write_code` or `create_file`), Voca actively halts execution. The UI renders a red/green confirmation prompt alerting you identically to what files the AI is about to modify.
4. **Execution & Auditing:** Upon clicking "Confirm", the pipeline instantly resumes, tools are dispatched, and the exact timestamped sequence is locked into the **Session History** panel indefinitely for auditing cross-checks.

---

## ⚙ Hardware Workarounds & Design Constraints

Operating Local LLMs alongside localized Speech-To-Text processing engines presents rigid hardware execution limits. The following modifications were integrated to keep overhead incredibly fast:

- **GPU Delegation (`stt.py`):** Voca initializes `faster_whisper` statically out of the gate natively with `compute_type="float16"` locking precision on the `cuda` device buffer. Because it initializes once at module startup, the model's footprint remains in warm VRAM, resolving massive instantiation timeouts between separate queries.
- **Dynamic Model Selection:** Voca dynamically hooks into your Ollama Daemon (`/api/models`) and intercepts all available downloaded model binaries. You can selectively drop down from an intensive 8-billion parameter deployment like `llama3.1` down to smaller `qwen` instances based on concurrent load. 
- **Graceful Retries:** `intent.py` employs a multi-step inference logic sequence. Because small LLMs occasionally hallucinate formatting or fail JSON conversions, Voca implements a safe `except JSONDecodeError` safety net. If a model breaks schema, Voca hits the backend with a strict `STRICT_RETRY_PROMPT` bypassing STT processing immediately before elegantly retreating to the `general_chat` bucket.

---

## 🚀 Setup Instructions

1. **Install uv Package Manager**
   Voca utilizes `uv` to maintain its isolated environment incredibly quickly.
   If you don't have it installed:
   ```bash
   pip install uv
   ```

2. **Pull Dependencies**
   ```bash
   uv sync
   ```

3. **Install and Run Ollama for Inference**
   Install [Ollama](https://ollama.com/) physically on your machine.
   Boot up the background service (`ollama serve`) or run the executable directly depending on OS parameters. 
   Pull a model to get started:
   ```bash
   ollama pull gemma2:2b    # or any model of your choosing!
   ```

4. **Boot Voca**
   Launch the FastAPI Backend:
   ```bash
   uv run python app.py
   ```
   Head to **`http://localhost:7860`** in your browser. Wait a few seconds for the `large-v3-turbo` whisper module weights to load onto your GPU locally.  

5. **Interact!**
   - Click the microphone trigger, speak your query (e.g. *"Create a folder and generate a python script that tracks crypto prices"*).
   - Before executing code to your hard drive, Voca will prompt you linearly for two-stage approval. Check the Session Log to review memory constraints!
