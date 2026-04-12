/* =========================================================================
   Voca — Frontend JavaScript (Chat Mode)
   ========================================================================= */

(() => {
	"use strict";

	// --- DOM Elements -------------------------------------------------------
	const micBtn = document.getElementById("mic-btn");
	const recTimer = document.getElementById("recording-timer");
	const timerText = document.getElementById("timer-text");

	const fileInput = document.getElementById("file-input");
	const uploadLabel = document.getElementById("upload-label");

	const textInput = document.getElementById("text-input");
	const runBtn = document.getElementById("run-btn");
	const chatHistory = document.getElementById("chat-history");
	const modelSelect = document.getElementById("model-select");
	const themeToggle = document.getElementById("theme-toggle");

	// --- Theme Management --------------------------------------------------
	function initializeTheme() {
		const savedTheme = localStorage.getItem("voca-theme") || "light";
		applyTheme(savedTheme);
	}

	function applyTheme(theme) {
		if (theme === "dark") {
			document.documentElement.classList.add("dark-mode");
		} else {
			document.documentElement.classList.remove("dark-mode");
		}
		localStorage.setItem("voca-theme", theme);
	}

	function toggleTheme() {
		const isDarkMode = document.documentElement.classList.contains("dark-mode");
		applyTheme(isDarkMode ? "light" : "dark");
	}

	if (themeToggle) {
		themeToggle.addEventListener("click", toggleTheme);
	}

	// --- State --------------------------------------------------------------
	let pendingIntents = [];
	let isAwaitingConfirmation = false;
	let actionLogState = [];
	let chatContextState = [];
	let mediaRecorder = null;
	let audioChunks = [];
	let isRecording = false;
	let recordingInterval = null;
	let recordingSeconds = 0;
	let currentAudioBlob = null;
	let currentFileName = "recording.wav";

	// --- LocalStorage Management -----------------------------------------------
	const STORAGE_KEY = "voca_chat_messages";

	function saveMessageToLocalStorage(message) {
		try {
			const messages = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");
			messages.push({
				...message,
				id: Date.now(),
			});
			localStorage.setItem(STORAGE_KEY, JSON.stringify(messages));
		} catch (err) {
			console.error("Error saving message to localStorage:", err);
		}
	}

	function loadMessagesFromLocalStorage() {
		try {
			const messages = JSON.parse(localStorage.getItem(STORAGE_KEY) || "[]");

			return messages;
		} catch (err) {
			console.error("Error loading messages from localStorage:", err);
			return [];
		}
	}

	function clearLocalStorage() {
		try {
			localStorage.removeItem(STORAGE_KEY);
		} catch (err) {
			console.error("Error clearing localStorage:", err);
		}
	}

	// Load chat on page load
	async function initializeChat() {
		initializeTheme();

		if (modelSelect) {
			try {
				const response = await fetch("/api/models");
				const data = await response.json();

				if (data && data.models && data.models.length > 0) {
					modelSelect.innerHTML = "";
					data.models.forEach((model) => {
						const option = document.createElement("option");
						option.value = model.name;
						option.textContent = model.name;
						if (model.name === "gemma3:4b") option.selected = true;
						modelSelect.appendChild(option);
					});
				} else {
					modelSelect.innerHTML = `<option value="gemma3:4b">gemma3:4b</option>`;
				}
			} catch (e) {
				console.error("Failed to load models:", e);
				modelSelect.innerHTML = `<option value="gemma3:4b">gemma3:4b</option>`;
			}
		}

		// Load saved messages from localStorage
		const savedMessages = loadMessagesFromLocalStorage();

		// Restore messages to chat history
		savedMessages.forEach((msg) => {
			if (msg.type === "user") {
				appendUserMessageDirect(msg.content, msg.isLowConfidence);
			} else if (msg.type === "agent" && msg.content) {
				appendAgentMessageDirect(msg.content);
			}
		});

		// Messages restored silently
	}

	// Call initializeChat immediately if document is already ready
	if (document.readyState === "loading") {
		window.addEventListener("DOMContentLoaded", initializeChat);
	} else {
		initializeChat();
	}
	micBtn.addEventListener("click", async () => {
		if (isAwaitingConfirmation || micBtn.disabled) return;
		if (isRecording) {
			stopRecording();
		} else {
			await startRecording();
		}
	});

	async function startRecording() {
		try {
			const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
			mediaRecorder = new MediaRecorder(stream, {
				mimeType: getSupportedMimeType(),
			});
			audioChunks = [];

			mediaRecorder.ondataavailable = (e) => {
				if (e.data.size > 0) audioChunks.push(e.data);
			};

			mediaRecorder.onstop = () => {
				const mimeType = mediaRecorder.mimeType || "audio/webm";
				currentAudioBlob = new Blob(audioChunks, { type: mimeType });
				const ext = mimeType.includes("webm") ? "webm" : "wav";
				currentFileName = `recording.${ext}`;
				stream.getTracks().forEach((t) => t.stop());
				enableRunButton();
			};

			mediaRecorder.start();
			isRecording = true;
			micBtn.classList.add("recording");
			micLabel.textContent = "Recording...";
			recTimer.classList.add("visible");
			recordingSeconds = 0;
			timerText.textContent = "00:00";

			recordingInterval = setInterval(() => {
				recordingSeconds++;
				const m = String(Math.floor(recordingSeconds / 60)).padStart(2, "0");
				const s = String(recordingSeconds % 60).padStart(2, "0");
				timerText.textContent = `${m}:${s}`;
			}, 1000);
		} catch (err) {
			console.error("Microphone access denied:", err);
			micLabel.textContent = "Mic access denied";
			micLabel.style.color = "#ef4444";
		}
	}

	function stopRecording() {
		if (mediaRecorder && mediaRecorder.state !== "inactive") {
			mediaRecorder.stop();
		}
		isRecording = false;
		micBtn.classList.remove("recording");
		recTimer.classList.remove("visible");
		clearInterval(recordingInterval);
	}

	function getSupportedMimeType() {
		const types = [
			"audio/webm;codecs=opus",
			"audio/webm",
			"audio/ogg",
			"audio/wav",
		];
		for (const type of types) {
			if (MediaRecorder.isTypeSupported(type)) return type;
		}
		return "";
	}

	// --- File Upload --------------------------------------------------------
	fileInput.addEventListener("change", (e) => {
		const file = e.target.files[0];
		if (!file) return;

		currentAudioBlob = file;
		currentFileName = file.name;
		uploadLabel.classList.add("has-file");
		uploadLabel.title = file.name;
		textInput.value = ""; // clear text if uploading audio

		enableRunButton();
	});

	// --- Text Input ---------------------------------------------------------
	textInput.addEventListener("input", () => {
		if (textInput.value.trim().length > 0) {
			enableRunButton();
			// Optionally clear audio if they start typing
			if (currentAudioBlob && !isRecording) {
				currentAudioBlob = null;
				fileInput.value = "";
				uploadLabel.classList.remove("has-file");
			}
		} else if (!currentAudioBlob) {
			runBtn.disabled = true;
		}
	});

	textInput.addEventListener("keypress", (e) => {
		if (e.key === "Enter" && !runBtn.disabled) {
			runBtn.click();
		}
	});

	// --- Run / Processing ---------------------------------------------------
	function enableRunButton() {
		runBtn.disabled = false;
	}

	runBtn.addEventListener("click", async () => {
		if (isAwaitingConfirmation || runBtn.disabled) return;
		const textVal = textInput.value.trim();
		if (textVal) {
			await processText(textVal);
		} else if (currentAudioBlob) {
			await processAudio();
		}
	});

	async function processText(text) {
		runBtn.disabled = true;
		textInput.disabled = true;
		appendUserMessage(text);
		textInput.value = "";

		const typingEl = showTypingIndicator("Classifying intent…");

		const stages = ["Executing action…", "Preparing results…"];
		let stageIdx = 0;
		const stageInterval = setInterval(() => {
			if (stageIdx < stages.length) {
				updateTypingIndicator(typingEl, stages[stageIdx]);
				stageIdx++;
			}
		}, 2000);

		try {
			const response = await fetch("/api/process_text", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					text: text,
					action_log: actionLogState,
					chat_context: chatContextState,
					llm_model: modelSelect ? modelSelect.value : "gemma3:4b",
				}),
			});

			if (!response.ok) throw new Error(`Server error: ${response.status}`);
			const data = await response.json();
			syncState(data);
			appendAgentMessage(data);
		} catch (err) {
			console.error("Text Pipeline error:", err);
			appendAgentMessage({
				error: true,
				stage: "framework",
				message: err.message,
			});
		} finally {
			clearInterval(stageInterval);
			removeTypingIndicator(typingEl);
			textInput.disabled = false;
			textInput.focus();
			runBtn.disabled = true;
		}
	}

	async function processAudio() {
		runBtn.disabled = true;

		// For audio, we haven't transcribed yet, so just show the typing bubble
		// User bubble will be inserted after STT finishes
		const typingEl = showTypingIndicator("Transcribing audio…");

		const stages = [
			"Classifying intent…",
			"Executing action…",
			"Preparing results…",
		];
		let stageIdx = 0;
		const stageInterval = setInterval(() => {
			if (stageIdx < stages.length) {
				updateTypingIndicator(typingEl, stages[stageIdx]);
				stageIdx++;
			}
		}, 3000);

		try {
			const formData = new FormData();
			formData.append("audio", currentAudioBlob, currentFileName);
			formData.append(
				"state",
				JSON.stringify({
					action_log: actionLogState,
					chat_context: chatContextState,
					llm_model: modelSelect ? modelSelect.value : "gemma3:4b",
				}),
			);

			const response = await fetch("/api/process", {
				method: "POST",
				body: formData,
			});

			if (!response.ok) throw new Error(`Server error: ${response.status}`);
			const data = await response.json();
			syncState(data);

			// Remove typing bubble briefly so User Bubble appears correctly before Agent Response
			removeTypingIndicator(typingEl);
			if (!data.error || data.stage !== "stt") {
				appendUserMessage(
					data.transcript || "(Empty transcript)",
					data.low_confidence,
				);
			}
			appendAgentMessage(data);
		} catch (err) {
			console.error("Pipeline error:", err);
			appendAgentMessage({
				error: true,
				stage: "framework",
				message: err.message,
			});
		} finally {
			clearInterval(stageInterval);
			// In case of error it might still be there
			if (document.body.contains(typingEl)) {
				removeTypingIndicator(typingEl);
			}

			// Reset inputs
			currentAudioBlob = null;
			uploadLabel.classList.remove("has-file");
			uploadLabel.title = "Upload an audio file";
			runBtn.disabled = true;
		}
	}

	// --- Chat UI Creation ---------------------------------------------------

	function showTypingIndicator(initialText) {
		const msgDiv = document.createElement("div");
		msgDiv.className = "message agent typing-msg";
		msgDiv.innerHTML = `
      <div class="avatar">🎙️</div>
      <div class="bubble">
        <p class="role-title">Voca</p>
        <div class="bubble-content" style="padding: 0.8rem 1.2rem;">
          <div class="typing-indicator">
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <div class="typing-dot"></div>
            <span class="typing-text">${escapeHTML(initialText)}</span>
          </div>
        </div>
      </div>
    `;
		chatHistory.appendChild(msgDiv);
		scrollToBottom();
		return msgDiv;
	}

	function updateTypingIndicator(element, text) {
		if (!element) return;
		const textEl = element.querySelector(".typing-text");
		if (textEl) textEl.textContent = text;
	}

	function removeTypingIndicator(element) {
		if (element && element.parentNode) {
			element.parentNode.removeChild(element);
		}
	}

	function scrollToBottom() {
		setTimeout(() => {
			chatHistory.scrollTo({
				top: chatHistory.scrollHeight,
				behavior: "smooth",
			});
		}, 50);
	}

	function appendUserMessage(text, isLowConfidence = false) {
		appendUserMessageDirect(text, isLowConfidence);

		// Save to localStorage
		saveMessageToLocalStorage({
			type: "user",
			content: text,
			isLowConfidence: isLowConfidence,
			timestamp: new Date().toISOString(),
		});
	}

	function appendUserMessageDirect(text, isLowConfidence = false) {
		const msgDiv = document.createElement("div");
		msgDiv.className = "message user";
		let warning = "";
		if (isLowConfidence) {
			warning = `
          <div class="warning-banner" style="margin-bottom: 0.5rem; padding: 0.5rem; background: rgba(255, 170, 0, 0.1); border-left: 3px solid #ffaa00; border-radius: 4px; font-size: 0.85rem; color: #ffaa00;">
            ⚠️ Low confidence — please verify transcript before running.
          </div>
        `;
		}
		msgDiv.innerHTML = `
      <div class="avatar">👤</div>
      <div class="bubble">
        <p class="role-title">You</p>
        <div class="bubble-content">
          ${warning}
          ${escapeHTML(text)}
        </div>
      </div>
    `;
		chatHistory.appendChild(msgDiv);
		scrollToBottom();
	}

	function appendAgentMessage(data) {
		appendAgentMessageDirect(data);

		// Save to localStorage
		saveMessageToLocalStorage({
			type: "agent",
			content: data,
			timestamp: new Date().toISOString(),
		});
	}

	function appendAgentMessageDirect(data) {
		const msgDiv = document.createElement("div");
		msgDiv.className = "message agent";

		if (data.error) {
			msgDiv.innerHTML = `
        <div class="avatar" style="background: rgba(255, 60, 60, 0.1);">❌</div>
        <div class="bubble error-bubble" style="border: 1px solid rgba(255, 60, 60, 0.3);">
          <p class="role-title" style="color: #ff6b6b; font-weight: 600;">Pipeline Failed — Stage: ${escapeHTML(data.stage || "unknown")}</p>
          <div class="bubble-content" style="color: var(--text-primary); margin-top: 5px;">
            ${escapeHTML(data.message || "An unknown error occurred.")}
          </div>
        </div>
      `;
			chatHistory.appendChild(msgDiv);
			scrollToBottom();
			return;
		}

		const results = data.results || [];

		// Determine title block for Action
		const actionIcons = {
			create_file: "📁 Create File",
			write_file: "📝 Write File",
			write_code: "💻 Code Generation",
			summarize: "📄 Summary",
			general_chat: "💬 General Chat",
			error: "❌ Pipeline Error",
			unknown: "⚠️ Unknown Intent",
		};

		let allBlocksHtml = "";

		results.forEach((res, idx) => {
			const intent = res.intent;
			const action = res.action;
			const resultText = res.result;

			const actionTitle = actionIcons[action] || action || "Process Result";

			let intentHtml = "";
			if (intent && Object.keys(intent).length > 0) {
				intentHtml = `
          <div class="detail-block">
            <div class="detail-header">
              <span>🧠 Intent JSON ${results.length > 1 ? `(#${idx + 1})` : ""}</span>
            </div>
            <div class="detail-body">
              <pre class="code-block json-block">${escapeHTML(JSON.stringify(intent, null, 2))}</pre>
            </div>
          </div>
        `;
			}

			let resultHtml = `
        <div class="detail-block" style="${intentHtml ? "margin-top: 0.5rem;" : ""}">
          <div class="detail-header">
            <span>📋 ${actionTitle}</span>
          </div>
          <div class="detail-body">
            <pre class="code-block">${escapeHTML(resultText || "No result generated.")}</pre>
          </div>
        </div>
      `;

			allBlocksHtml += `
        <div class="action-combo" style="${idx > 0 ? "margin-top: 2rem; padding-top: 1rem; border-top: 1px dashed rgba(255,255,255,0.1);" : ""}">
          ${intentHtml}
          ${resultHtml}
        </div>
      `;
		});

		if (results.length === 0 && !data.requires_confirmation) {
			allBlocksHtml = `<p>No parsed actions returned.</p>`;
		} else if (results.length === 0 && data.requires_confirmation) {
			// It's possible ONLY pending intents exist and no results
			allBlocksHtml = ``;
		}

		if (data.requires_confirmation) {
			allBlocksHtml += `
        <div class="confirm-panel" ${allBlocksHtml ? 'style="margin-top: 1rem;"' : ""}>
          <div class="confirm-text">${escapeHTML(data.confirmation_message)}</div>
          <div class="confirm-actions" style="margin-top: 0.8rem;">
            <button class="btn-confirm" id="btn-confirm-intents">✅ Confirm</button>
            <button class="btn-cancel" id="btn-cancel-intents">❌ Cancel</button>
          </div>
        </div>
      `;
		}

		msgDiv.innerHTML = `
      <div class="avatar">🎙️</div>
      <div class="bubble">
        <p class="role-title">Voca</p>
        <div class="bubble-content">
          ${allBlocksHtml}
        </div>
      </div>
    `;

		chatHistory.appendChild(msgDiv);
		scrollToBottom();

		if (data.requires_confirmation) {
			isAwaitingConfirmation = true;
			pendingIntents = data.pending_intents || [];
			textInput.disabled = true;
			micBtn.disabled = true;
			runBtn.disabled = true;

			const confirmBtn = msgDiv.querySelector("#btn-confirm-intents");
			const cancelBtn = msgDiv.querySelector("#btn-cancel-intents");

			confirmBtn.addEventListener("click", () => handleConfirm(msgDiv));
			cancelBtn.addEventListener("click", () => handleCancel(msgDiv));
		}
	}

	async function handleConfirm(panelMsgDiv) {
		const currPending = pendingIntents;
		const panel = panelMsgDiv.querySelector(".confirm-panel");
		if (panel) {
			panel.innerHTML = `<div class="confirm-text" style="color: var(--text-muted)">✅ Confirmed. Executing...</div>`;
		}

		const typingEl = showTypingIndicator("Executing actions…");
		try {
			const response = await fetch("/api/confirm_intents", {
				method: "POST",
				headers: { "Content-Type": "application/json" },
				body: JSON.stringify({
					intents: currPending,
					action_log: actionLogState,
					chat_context: chatContextState,
					llm_model: modelSelect ? modelSelect.value : "gemma3:4b",
				}),
			});

			if (!response.ok) throw new Error(`Server error: ${response.status}`);
			const data = await response.json();
			syncState(data);
			removeTypingIndicator(typingEl);
			appendAgentMessage(data);
		} catch (err) {
			console.error("Confirmation error:", err);
			removeTypingIndicator(typingEl);
			appendAgentMessage({
				error: true,
				stage: "framework",
				message: err.message,
			});
		} finally {
			resetConfirmationState();
		}
	}

	function handleCancel(panelMsgDiv) {
		const panel = panelMsgDiv.querySelector(".confirm-panel");
		if (panel) {
			panel.innerHTML = `<div class="confirm-text" style="color: var(--text-muted)">❌ File operation cancelled.</div>`;
		}
		resetConfirmationState();
	}

	function resetConfirmationState() {
		isAwaitingConfirmation = false;
		pendingIntents = [];
		textInput.disabled = false;
		micBtn.disabled = false;
		if (textInput.value.trim().length > 0 || currentAudioBlob) {
			runBtn.disabled = false;
		}
		textInput.focus();
	}

	// Utility to escape HTML and prevent injection
	function escapeHTML(str) {
		if (typeof str !== "string") return str;
		return str.replace(
			/[&<>'"]/g,
			(tag) =>
				({
					"&": "&amp;",
					"<": "&lt;",
					">": "&gt;",
					"'": "&#39;",
					'"': "&quot;",
				})[tag] || tag,
		);
	}

	// --- Session Memory State & UI ------------------------------------------

	const clearSessionBtn = document.getElementById("clear-session-btn");
	const historyCount = document.getElementById("history-count");
	const historyTbody = document.getElementById("history-tbody");

	if (clearSessionBtn) {
		clearSessionBtn.addEventListener("click", async (e) => {
			e.preventDefault();
			e.stopPropagation();
			actionLogState = [];
			chatContextState = [];

			// Clear localStorage
			clearLocalStorage();

			// Clear chat history from DOM (keep the start message)
			const messages = chatHistory.querySelectorAll(
				".message:not(.start-message)",
			);
			messages.forEach((msg) => msg.remove());

			renderHistoryPanel();
		});
	}

	function syncState(data) {
		if (data.action_log) actionLogState = data.action_log;
		if (data.chat_context) chatContextState = data.chat_context;
		renderHistoryPanel();
	}

	function renderHistoryPanel() {
		if (!historyCount || !historyTbody) return;

		historyCount.textContent = actionLogState.length;

		if (actionLogState.length === 0) {
			historyTbody.innerHTML = `<tr><td colspan="5" class="text-center text-muted" style="padding: 1rem;">No actions recorded this session.</td></tr>`;
			return;
		}

		let html = "";
		// Render in reverse chronological or just chronological?
		// Let's keep it chronological (append at bottom)
		actionLogState.forEach((item) => {
			const statusClass = item.status === "success" ? "success" : "error";
			const statusText = item.status === "success" ? "Success" : "Failed";
			html += `
        <tr>
          <td style="white-space: nowrap;">${escapeHTML(item.timestamp)}</td>
          <td>${escapeHTML(item.transcript)}</td>
          <td><span style="font-weight: 500; font-family: monospace;">${escapeHTML(item.intent)}</span></td>
          <td>${escapeHTML(item.filename || "-")}</td>
          <td><span class="status-badge ${statusClass}">${statusText}</span></td>
        </tr>
      `;
		});

		historyTbody.innerHTML = html;
	}
})();
