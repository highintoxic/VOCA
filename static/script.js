/* =========================================================================
   Voca — Frontend JavaScript
   Handles mic recording, file upload, API calls, and result rendering
   ========================================================================= */

(() => {
  "use strict";

  // --- DOM Elements -------------------------------------------------------
  const micBtn = document.getElementById("mic-btn");
  const micLabel = document.getElementById("mic-label");
  const recTimer = document.getElementById("recording-timer");
  const timerText = document.getElementById("timer-text");

  const fileInput = document.getElementById("file-input");
  const uploadArea = document.getElementById("upload-area");
  const uploadLabel = uploadArea.querySelector(".upload-label");
  const fileNameEl = document.getElementById("file-name");

  const runBtn = document.getElementById("run-btn");

  const transcriptText = document.getElementById("transcript-text");
  const intentJson = document.getElementById("intent-json");
  const actionText = document.getElementById("action-text");
  const resultOutput = document.getElementById("result-output");

  const loadingOverlay = document.getElementById("loading-overlay");
  const loaderText = document.getElementById("loader-text");

  const resultCards = document.querySelectorAll(".result-card");

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
      micLabel.textContent = "Click to stop";
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

    // Clear any file upload
    fileInput.value = "";
    fileNameEl.textContent = "";
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
    fileNameEl.textContent = `📎 ${file.name}`;
    uploadLabel.classList.add("has-file");

    // Clear mic recording state
    micLabel.textContent = "Click to record";
    micLabel.style.color = "";

    enableRunButton();
  });

  // Drag & Drop
  uploadLabel.addEventListener("dragover", (e) => {
    e.preventDefault();
    uploadLabel.style.borderColor = "var(--accent)";
  });

  uploadLabel.addEventListener("dragleave", () => {
    uploadLabel.style.borderColor = "";
  });

  uploadLabel.addEventListener("drop", (e) => {
    e.preventDefault();
    uploadLabel.style.borderColor = "";
    const file = e.dataTransfer.files[0];
    if (file && file.type.startsWith("audio/")) {
      currentAudioBlob = file;
      currentFileName = file.name;
      fileNameEl.textContent = `📎 ${file.name}`;
      uploadLabel.classList.add("has-file");
      enableRunButton();
    }
  });

  // --- Run Button ---------------------------------------------------------

  function enableRunButton() {
    runBtn.disabled = false;
  }

  runBtn.addEventListener("click", async () => {
    if (!currentAudioBlob) return;
    await processAudio();
  });

  async function processAudio() {
    // Show loading
    loadingOverlay.classList.add("visible");
    runBtn.disabled = true;
    clearResults();

    const stages = [
      "Transcribing audio…",
      "Classifying intent…",
      "Executing action…",
      "Preparing results…",
    ];
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

      if (!response.ok) {
        throw new Error(`Server error: ${response.status}`);
      }

      const data = await response.json();
      displayResults(data);
    } catch (err) {
      console.error("Pipeline error:", err);
      resultOutput.textContent = `❌ Error: ${err.message}`;
      resultOutput.classList.remove("placeholder");
    } finally {
      clearInterval(stageInterval);
      loadingOverlay.classList.remove("visible");
      runBtn.disabled = false;
    }
  }

  // --- Results ------------------------------------------------------------

  function clearResults() {
    transcriptText.textContent = "Waiting for audio…";
    transcriptText.classList.add("placeholder");
    intentJson.textContent = "{ }";
    intentJson.classList.add("placeholder");
    actionText.textContent = "—";
    actionText.classList.add("placeholder");
    resultOutput.textContent = "—";
    resultOutput.classList.add("placeholder");

    resultCards.forEach((card) => card.classList.remove("active"));
  }

  function displayResults(data) {
    // Transcript
    if (data.transcript) {
      transcriptText.textContent = data.transcript;
      transcriptText.classList.remove("placeholder");
      animateCard(0);
    }

    // Intent
    setTimeout(() => {
      if (data.intent && Object.keys(data.intent).length > 0) {
        intentJson.textContent = JSON.stringify(data.intent, null, 2);
        intentJson.classList.remove("placeholder");
      }
      animateCard(1);
    }, 200);

    // Action
    setTimeout(() => {
      if (data.action) {
        actionText.textContent = formatAction(data.action);
        actionText.classList.remove("placeholder");
      }
      animateCard(2);
    }, 400);

    // Result
    setTimeout(() => {
      if (data.result) {
        resultOutput.textContent = data.result;
        resultOutput.classList.remove("placeholder");
      }
      animateCard(3);
    }, 600);
  }

  function animateCard(index) {
    const card = resultCards[index];
    if (!card) return;
    card.classList.add("active");
    card.style.transform = "scale(1.01)";
    setTimeout(() => {
      card.style.transform = "";
    }, 300);
  }

  function formatAction(action) {
    const icons = {
      create_file: "📁 Create File",
      write_code: "💻 Write Code",
      summarize: "📄 Summarize",
      general_chat: "💬 General Chat",
    };
    return icons[action] || action;
  }
})();
