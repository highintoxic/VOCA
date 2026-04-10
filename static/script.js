/* =========================================================================
   Voca — Frontend JavaScript (Chat Mode)
   ========================================================================= */

(() => {
  "use strict";

  // --- DOM Elements -------------------------------------------------------
  const micBtn = document.getElementById("mic-btn");
  const micLabel = document.getElementById("mic-label");
  const recTimer = document.getElementById("recording-timer");
  const timerText = document.getElementById("timer-text");

  const fileInput = document.getElementById("file-input");
  const uploadLabel = document.getElementById("upload-label");

  const textInput = document.getElementById("text-input");
  const runBtn = document.getElementById("run-btn");
  const chatHistory = document.getElementById("chat-history");

  // --- State --------------------------------------------------------------
  let mediaRecorder = null;
  let audioChunks = [];
  let isRecording = false;
  let recordingInterval = null;
  let recordingSeconds = 0;
  let currentAudioBlob = null;
  let currentFileName = "recording.wav";

  // --- Microphone Recording -----------------------------------------------
  micBtn.addEventListener("click", async () => {
    if (isRecording) {
      stopRecording();
    } else {
      await startRecording();
    }
  });

  async function startRecording() {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      mediaRecorder = new MediaRecorder(stream, { mimeType: getSupportedMimeType() });
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
    micLabel.textContent = "Recording saved ✓";
    micLabel.style.color = "#22c55e";
    recTimer.classList.remove("visible");
    clearInterval(recordingInterval);

    fileInput.value = "";
    fileNameEl.textContent = "Upload file";
    uploadLabel.classList.remove("has-file");
  }

  function getSupportedMimeType() {
    const types = ["audio/webm;codecs=opus", "audio/webm", "audio/ogg", "audio/wav"];
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
        body: JSON.stringify({ text: text }),
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data = await response.json();
      appendAgentMessage(data);

    } catch (err) {
      console.error("Text Pipeline error:", err);
      appendAgentMessage({
        action: "error",
        result: `❌ Error: ${err.message}`
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

    const stages = ["Classifying intent…", "Executing action…", "Preparing results…"];
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

      const response = await fetch("/api/process", {
        method: "POST",
        body: formData,
      });

      if (!response.ok) throw new Error(`Server error: ${response.status}`);
      const data = await response.json();
      
      // Remove typing bubble briefly so User Bubble appears correctly before Agent Response
      removeTypingIndicator(typingEl);
      appendUserMessage(data.transcript || "(Empty transcript)");
      appendAgentMessage(data);

    } catch (err) {
      console.error("Pipeline error:", err);
      appendAgentMessage({
        action: "error",
        result: `❌ Error: ${err.message}`
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
        behavior: 'smooth'
      });
    }, 50);
  }

  function appendUserMessage(text) {
    const msgDiv = document.createElement("div");
    msgDiv.className = "message user";
    msgDiv.innerHTML = `
      <div class="avatar">👤</div>
      <div class="bubble">
        <p class="role-title">You</p>
        <div class="bubble-content">
          ${escapeHTML(text)}
        </div>
      </div>
    `;
    chatHistory.appendChild(msgDiv);
    scrollToBottom();
  }

  function appendAgentMessage(data) {
    const results = data.results || [];
    
    // Create elements dynamically to inject content safely
    const msgDiv = document.createElement("div");
    msgDiv.className = "message agent";
    
    // Determine title block for Action
    const actionIcons = {
      create_file: "📁 Create File",
      write_code: "💻 Code Generation",
      summarize: "📄 Summary",
      general_chat: "💬 General Chat",
      error: "❌ Pipeline Error",
      unknown: "⚠️ Unknown Intent"
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
              <span>🧠 Intent JSON ${results.length > 1 ? `(#${idx + 1})` : ''}</span>
            </div>
            <div class="detail-body">
              <pre class="code-block json-block">${escapeHTML(JSON.stringify(intent, null, 2))}</pre>
            </div>
          </div>
        `;
      }

      let resultHtml = `
        <div class="detail-block" style="${intentHtml ? 'margin-top: 0.5rem;' : ''}">
          <div class="detail-header">
            <span>📋 ${actionTitle}</span>
          </div>
          <div class="detail-body">
            <pre class="code-block">${escapeHTML(resultText || "No result generated.")}</pre>
          </div>
        </div>
      `;

      allBlocksHtml += `
        <div class="action-combo" style="${idx > 0 ? 'margin-top: 2rem; padding-top: 1rem; border-top: 1px dashed rgba(255,255,255,0.1);' : ''}">
          ${intentHtml}
          ${resultHtml}
        </div>
      `;
    });

    if (results.length === 0) {
      allBlocksHtml = `<p>No parsed actions returned.</p>`;
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
  }

  // Utility to escape HTML and prevent injection
  function escapeHTML(str) {
    if (typeof str !== 'string') return str;
    return str.replace(/[&<>'"]/g, 
      tag => ({
        '&': '&amp;',
        '<': '&lt;',
        '>': '&gt;',
        "'": '&#39;',
        '"': '&quot;'
      }[tag] || tag)
    );
  }

})();
