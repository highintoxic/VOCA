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
  const uploadLabel = document.querySelector(".upload-label");
  const fileNameEl = document.getElementById("file-name");

  const runBtn = document.getElementById("run-btn");
  const chatHistory = document.getElementById("chat-history");
  
  const loadingOverlay = document.getElementById("loading-overlay");
  const loaderText = document.getElementById("loader-text");

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
    fileNameEl.textContent = file.name;
    uploadLabel.classList.add("has-file");

    micLabel.textContent = "Record Audio";
    micLabel.style.color = "";
    enableRunButton();
  });

  // --- Run / Processing ---------------------------------------------------
  function enableRunButton() {
    runBtn.disabled = false;
  }

  runBtn.addEventListener("click", async () => {
    if (!currentAudioBlob) return;
    await processAudio();
  });

  async function processAudio() {
    loadingOverlay.classList.add("visible");
    runBtn.disabled = true;

    const stages = ["Transcribing audio…", "Classifying intent…", "Executing action…", "Preparing results…"];
    let stageIdx = 0;
    const stageInterval = setInterval(() => {
      stageIdx = Math.min(stageIdx + 1, stages.length - 1);
      loaderText.textContent = stages[stageIdx];
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
      loadingOverlay.classList.remove("visible");
      
      // Reset inputs
      currentAudioBlob = null;
      micLabel.textContent = "Record Audio";
      micLabel.style.color = "";
      fileNameEl.textContent = "Upload file";
      uploadLabel.classList.remove("has-file");
      runBtn.disabled = true;
      loaderText.textContent = "Processing…";
    }
  }

  // --- Chat UI Creation ---------------------------------------------------

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
    const { intent, action, result } = data;
    
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
    
    const actionTitle = actionIcons[action] || action || "Process Result";

    // Build the intent JSON block safely
    let intentHtml = "";
    if (intent && Object.keys(intent).length > 0) {
      intentHtml = `
        <div class="detail-block">
          <div class="detail-header">
            <span>🧠 Intent JSON</span>
          </div>
          <div class="detail-body">
            <pre class="code-block json-block">${escapeHTML(JSON.stringify(intent, null, 2))}</pre>
          </div>
        </div>
      `;
    }

    // Build Result Block
    let resultHtml = `
      <div class="detail-block">
        <div class="detail-header">
          <span>📋 ${actionTitle}</span>
        </div>
        <div class="detail-body">
          <pre class="code-block">${escapeHTML(result || "No result generated.")}</pre>
        </div>
      </div>
    `;

    msgDiv.innerHTML = `
      <div class="avatar">🎙️</div>
      <div class="bubble">
        <p class="role-title">Voca</p>
        <div class="bubble-content">
          ${intentHtml}
          ${resultHtml}
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
