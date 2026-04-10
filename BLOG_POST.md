# Building Voca: A Fully Local, Privacy-First Voice AI Agent

Voice assistants are incredibly ubiquitous today. However, the vast majority rely on sending your raw audio data and personal context into cloud-based black boxes. For developers working on sensitive repositories or individuals who simply value absolute local privacy, this trade-off is often deeply uncomfortable.

Enter **Voca** — a 100% open-source, entirely localized voice-controlled Artificial Intelligence agent capable of creating files, generating codebase scripts, summarizing text, and holding contextual memory without a single byte ever phoning home.

Writing a completely offline system capable of doing everything an enterprise-level voice assistant does locally brought several massive architectural and hardware challenges. Here’s a dive into exactly how Voca was built.

---

## 🏗️ The Architecture: Keeping It Stateless & Fast

The goal for Voca was to keep the environment lean, exceptionally modular, and lightning-fast. 

The **Backend** is orchestrated by FastAPI operating a singular async execution pipeline route (`/api/process`). Using Python alongside Uvicorn allowed for natively intercepting audio blob transfers instantly over standard HTTP forms, dropping the need for complex websocket management.

The **Frontend** opts out of heavy abstractions entirely, utilizing Vanilla Javascript, HTML, and CSS. But the greatest architectural decision was **decentralizing memory away from the backend**.

Initially, caching long-running chat memories against the backend proved chaotic when managing multiple sessions or scaling local inferences. We solved this by pushing the entirety of our state architecture directly to the client. 
Instead of the server remembering what was said, the *frontend* stores two strictly sized arrays: an `actionLogState` (every physical file creation or code drop authorized) and a `chatContextState` (conversational dialogue). 

Every single time a user clicks the microphone or enters a text packet, the frontend securely stringifies that footprint and ships it *with* the audio binary into the FastAPI inference pipeline. This makes our backend explicitly **stateless**.

### The Native Pipeline
For every audio blob ingested, it traverses three fully localized stages:
1. **STT (Speech To Text)**: Transforms the audio into raw textual data.
2. **Intent Classification**: Evaluates the text alongside the historical action-logger to determine what functions the user explicitly wants to trigger.
3. **Tool Dispatcher**: Safely delegates the intent execution into sandboxed Python tools capable of touching the local filesystem.

---

## 🛠️ The Features & Tool Map

When the pipeline reaches the **Tool Dispatcher**, we strictly map the LLM's structured output into one of four deterministic Python functions designed specifically for automated execution:

- 📁 **`create_file`**: Instantiates a blank file or directory strictly inside an air-gapped `output/` sandbox directory. This is useful for initializing folder structures before writing code to them.
- 💻 **`write_code`**: Given a description and a targeted filename, this triggers the localized LLM seamlessly as a "code generator", strips out all markdown boundaries securely, and prints raw script logic down onto the hard drive footprint.
- 📄 **`summarize`**: Bypasses the local hard drive, pulling text input dynamically into the LLM system prompt tuned explicitly for short, bulleted summarization before piping it rapidly back to the active chat stream.
- 💬 **`general_chat`**: The fallback reasoning bucket for when intents fail parsing or when you simply want to bounce questions off the agent. Chat contexts are passed dynamically across forms to ensure conversations maintain rolling 20-frame bounds!

---

## 🧠 The Models We Chose (And Why)

Running an entire multi-layered reasoning engine completely locally heavily bounds your constraints by raw GPU VRAM limits. We couldn't throw monolithic deployments at the process. We needed incredibly calculated model selections.

### Audio Transcription: `faster-whisper`
We deployed **faster-whisper** locking the `large-v3-turbo` model. 
> [!TIP]
> Standard Whisper deployments often invoke significant PyTorch latency per inference. 

We circumvented this hardware penalty by initializing the model explicitly **once** statically at module load time natively overriding precision bounds to `compute_type="float16"` locking immediately into the `cuda` buffers. By ensuring the whisper weights remain resting warmly on the GPU, transcriptions resolve in mere milliseconds.
Additionally, the system inherently calculates the `avg_logprob` across returned whisper segments. If confidence drops below `-0.8`, the system purposefully triggers a "Graceful Degradation", cleanly rejecting automated code executions and warning the user that their sentence wasn't heard accurately.

### Intent Detection & Intelligence: Ollama
Instead of bundling proprietary logic frameworks, we rely strictly on **Ollama** natively binding itself to local LLMs (the default baseline uses Google's `gemma3:4b`).
Because users possess different hardware stacks, we later wrote a dynamic bridging mechanic. Voca automatically hooks into `/api/models` fetching every instance available in an individual's Ollama Daemon—surfacing a slick dropdown bridging users natively to switch from `deepseek-r` to `llama3.2` instantaneously between tasks depending on the inference density they need.

---

## 🧗 Challenges Faced

Building autonomous LLMs to write raw file data poses distinct hurdles.

### Challenge 1: The "Compound Intent" Hallucination
*Issue:* If a user says *"Create a folder called scripts and write a python loop inside it"*, smaller 4-billion parameter LLMs regularly collapse logically. They would combine the two actions into a single hallucinated tool call or break standard JSON formatting completely (`{intent: "create_folder_and_file"}`).
*Solution:* We strictly enforced **Structured Output Frameworking** by attaching a strict JSON schema array layout straight into Ollama’s `format=` argument. The LLM was forcibly stripped of the physical ability to return malformed structures, forcing it to correctly chunk outputs into linear arrays: `[{intent: "create_file"}, {intent: "write_code"}]`.

### Challenge 2: Contextual Ambiguity
*Issue:* A user asks `"make that function async"` 30 seconds after creating a file. The LLM has no actual idea what "that function" or "that file" refers to.
*Solution:* This is identically why the `action_log` is passed from the frontend UI! Inside `intent.py`, if the action history contains modifications, Voca seamlessly builds a secondary system prompt string dynamically mapping out exactly what local files have been birthed during the session, handing the LLM perfectly synced reference mapping.

### Challenge 3: Safety & Human-In-The-Loop
*Issue:* Voice-driven actions are notorious for dangerous side-effects. An offhand cough mapping into an `rm -rf` transcription could theoretically be lethal.
*Solution:* 
1. **Sandboxing:** `tools.py` forces all file deployments blindly through an isolation layer (`safe_path()`) locking everything solely inside an `output/` directory constraint tracking path bounds preventing escape sequences.
2. **Two-Stage Execution:** Any request designated as an OS write request (`write_code` or `create_file`) purposely halts pipelining. It bounces the intention fully back to the client triggering a massive Human-In-The-Loop confirmation boundary on the UI, natively forcing explicit human visualization over purely generative side-effects before disk allocation is approved.

---

## 🎯 Conclusion

By bridging `faster-whisper`, pure FastAPI async streaming, and dynamically localized Ollama LLMs bounded behind explicit safety wrappers — **Voca** represents a leap forward into truly sovereign computing. 

It executes blistering fast automated infrastructure without a single cloud subscription fee, allowing developers to speak their codebase into existence entirely underneath their own roof.
