/* CarReel - Alpine.js application logic */

const MAX_FILES = 20;
const MAX_TOTAL_SIZE_MB = 500;

document.addEventListener("alpine:init", () => {
  Alpine.data("reelApp", () => ({
    // State
    jobs: [],
    selectedJob: null,
    steps: [],
    uploading: false,
    uploadProgress: 0,
    uploadError: "",
    eventSource: null,

    // i18n
    lang: getLang(),

    // Input
    isRecording: false,
    transcribing: false,
    cleaningUp: false,
    mediaRecorder: null,
    audioChunks: [],
    recordedBlob: null,
    typedTranscript: "",

    // File inputs
    mediaFiles: [],

    // Otomoto import
    otomotoUrl: "",
    otomotoLoading: false,
    otomotoError: "",
    otomotoListing: null,
    otomotoGenerating: false,
    otomotoSalesCopy: "",
    otomotoPhoneNumber: "",
    otomotoListingTitle: "",

    // WhatsApp is localhost-only
    isLocal: ["localhost", "127.0.0.1"].includes(window.location.hostname),

    // Create reel tab (url or manual)
    createTab: "url",

    // Reel preview playback
    reelPaused: true,

    // SSE reconnect
    _sseRetries: 0,
    _sseMaxRetries: 3,

    pipelineSteps: [
      "transcribe",
      "scriptwrite",
      "voiceover",
      "media_process",
      "caption_generate",
      "video_assemble",
    ],

    init() {
      this.fetchJobs();
      // Poll for job list updates every 15 seconds
      setInterval(() => this.fetchJobs(), 15000);
    },

    // ---------- API calls ----------

    async fetchJobs() {
      try {
        const res = await fetch("/api/jobs");
        if (res.ok) {
          this.jobs = await res.json();
        }
      } catch {
        // silently retry on next interval
      }
    },

    async fetchJob(jobId) {
      try {
        const res = await fetch(`/api/jobs/${jobId}`);
        if (res.ok) {
          return await res.json();
        }
      } catch {
        // ignore
      }
      return null;
    },

    async startRecording() {
      if (this.isRecording) return;
      try {
        const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
        this.audioChunks = [];
        const mimeType = MediaRecorder.isTypeSupported("audio/webm;codecs=opus")
          ? "audio/webm;codecs=opus"
          : "audio/webm";
        this.mediaRecorder = new MediaRecorder(stream, { mimeType });
        this.mediaRecorder.ondataavailable = (e) => {
          if (e.data.size > 0) this.audioChunks.push(e.data);
        };
        this.mediaRecorder.onstop = () => {
          this.recordedBlob = new Blob(this.audioChunks, { type: mimeType });
          // Release mic
          stream.getTracks().forEach((t) => t.stop());
        };
        this.mediaRecorder.start();
        this.isRecording = true;
      } catch (e) {
        this.uploadError = t("upload.errorMic") + e.message;
      }
    },

    stopRecording() {
      if (!this.isRecording) return;
      this.isRecording = false;
      if (this.mediaRecorder && this.mediaRecorder.state !== "inactive") {
        this.mediaRecorder.stop();
      }
    },

    async stopAndTranscribe() {
      if (!this.isRecording) return;
      this.isRecording = false;

      // Stop recorder and wait for blob
      await new Promise((resolve) => {
        this.mediaRecorder.onstop = () => {
          const mimeType = this.mediaRecorder.mimeType;
          this.recordedBlob = new Blob(this.audioChunks, { type: mimeType });
          // Release mic
          this.mediaRecorder.stream.getTracks().forEach((t) => t.stop());
          resolve();
        };
        this.mediaRecorder.stop();
      });

      // Send to transcription API
      this.transcribing = true;
      this.uploadError = "";
      try {
        const form = new FormData();
        form.append("file", this.recordedBlob, "recording.webm");
        form.append("lang", getLang());
        const res = await fetch("/api/transcribe", { method: "POST", body: form });
        if (!res.ok) {
          this.uploadError = t("upload.transcribeError") + (await res.text());
          return;
        }
        const data = await res.json();
        if (data.text) {
          // Append to existing text or set it
          if (this.typedTranscript.trim()) {
            this.typedTranscript += " " + data.text;
          } else {
            this.typedTranscript = data.text;
          }
        }
      } catch (e) {
        this.uploadError = t("upload.transcribeError") + e.message;
      } finally {
        this.transcribing = false;
      }
    },

    async cleanUpText() {
      if (!this.typedTranscript.trim() || this.cleaningUp) return;
      this.cleaningUp = true;
      this.uploadError = "";
      try {
        const res = await fetch("/api/cleanup", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ text: this.typedTranscript, lang: getLang() }),
        });
        if (res.ok) {
          const data = await res.json();
          if (data.text) this.typedTranscript = data.text;
        }
      } catch (e) {
        this.uploadError = e.message;
      } finally {
        this.cleaningUp = false;
      }
    },

    async upload() {
      const hasTyped = this.typedTranscript.trim().length > 0;
      const hasRecording = !!this.recordedBlob;

      if (!hasTyped && !hasRecording) {
        this.uploadError = t("upload.errorType");
        return;
      }
      if (this.mediaFiles.length === 0) {
        this.uploadError = t("upload.errorMedia");
        return;
      }

      this.uploading = true;
      this.uploadProgress = 0;
      this.uploadError = "";

      const form = new FormData();
      // Always send typed transcript if present
      if (hasTyped) {
        form.append("transcript", this.typedTranscript.trim());
      }
      // Also send voice memo if recorded (used when no transcript)
      if (hasRecording && !hasTyped) {
        form.append("voice_memo", this.recordedBlob, "recording.webm");
      }
      form.append("lang", getLang());
      for (const f of this.mediaFiles) {
        form.append("media", f);
      }

      try {
        const data = await new Promise((resolve, reject) => {
          const xhr = new XMLHttpRequest();
          xhr.open("POST", "/api/jobs");

          xhr.upload.onprogress = (e) => {
            if (e.lengthComputable) {
              this.uploadProgress = Math.round((e.loaded / e.total) * 100);
            }
          };

          xhr.onload = () => {
            if (xhr.status >= 200 && xhr.status < 300) {
              resolve(JSON.parse(xhr.responseText));
            } else {
              try {
                const err = JSON.parse(xhr.responseText);
                reject(new Error(err.detail || t("upload.errorUpload")));
              } catch {
                reject(new Error(t("upload.errorUpload")));
              }
            }
          };

          xhr.onerror = () => reject(new Error(t("upload.errorNetwork")));
          xhr.send(form);
        });

        this.recordedBlob = null;
        this.typedTranscript = "";
        this.mediaFiles = [];

        // Reset file input
        const mediaInput = document.getElementById("media-input");
        if (mediaInput) mediaInput.value = "";

        await this.fetchJobs();
        this.selectJob(data.job_id);
      } catch (e) {
        this.uploadError = e.message;
      } finally {
        this.uploading = false;
        this.uploadProgress = 0;
      }
    },

    // ---------- Otomoto import ----------

    _detectSource(url) {
      if (url.includes("otomoto.pl")) return "otomoto";
      if (url.includes("mobile.de")) return "mobile";
      return null;
    },

    _isSourceAllowed(source) {
      const allowed = t("otomoto.allowedSources");
      return allowed === source;
    },

    async importOtomoto() {
      const url = this.otomotoUrl.trim();
      const source = this._detectSource(url);
      if (!url || !source || !this._isSourceAllowed(source)) {
        this.otomotoError = t("otomoto.errorUrl");
        return;
      }
      this.otomotoLoading = true;
      this.otomotoError = "";
      this.otomotoListing = null;

      const endpoint = source === "mobile" ? "/api/scrape-mobile" : "/api/scrape-otomoto";
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, lang: getLang() }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || t("otomoto.errorScrape"));
        }
        this.otomotoListing = await res.json();
      } catch (e) {
        this.otomotoError = e.message;
      } finally {
        this.otomotoLoading = false;
      }
    },

    async generateFromOtomoto() {
      const url = this.otomotoUrl.trim();
      if (!url) return;
      const source = this._detectSource(url);
      this.otomotoGenerating = true;
      this.otomotoError = "";
      this.otomotoSalesCopy = "";

      const endpoint = source === "mobile" ? "/api/mobile-job" : "/api/otomoto-job";
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, lang: getLang() }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || t("otomoto.errorGenerate"));
        }
        const data = await res.json();
        if (data.sales_copy) {
          this.otomotoSalesCopy = data.sales_copy;
        }
        this.otomotoPhoneNumber = data.phone_number || "";
        this.otomotoListingTitle = data.listing?.title || "";
        this.otomotoUrl = "";
        this.otomotoListing = null;
        await this.fetchJobs();
        this.selectJob(data.job_id);
      } catch (e) {
        this.otomotoError = e.message;
      } finally {
        this.otomotoGenerating = false;
      }
    },

    async deleteJob(jobId) {
      if (!confirm(t("job.confirmDelete"))) return;
      try {
        await fetch(`/api/jobs/${jobId}`, { method: "DELETE" });
        if (this.selectedJob && this.selectedJob.job_id === jobId) {
          this.closeJob();
        }
        await this.fetchJobs();
      } catch {
        // ignore
      }
    },

    // ---------- Job selection & SSE ----------

    async selectJob(jobId) {
      this.closeEventSource();

      const job = await this.fetchJob(jobId);
      if (!job) return;
      this.selectedJob = job;

      // Initialize step states from current job state
      this.initSteps(job);

      // If job is still processing, connect to SSE
      if (job.status === "pending" || job.status === "processing") {
        this._sseRetries = 0;
        this.connectSSE(jobId);
      }
    },

    initSteps(job) {
      const stepOrder = this.pipelineSteps;
      const currentIdx = job.current_step
        ? stepOrder.indexOf(job.current_step)
        : -1;

      this.steps = stepOrder.map((s, i) => {
        let status = "pending";
        if (job.status === "completed") {
          status = "completed";
        } else if (job.status === "failed") {
          if (job.current_step === s) {
            status = "failed";
          } else if (i < currentIdx) {
            status = "completed";
          }
        } else if (i < currentIdx) {
          status = "completed";
        } else if (i === currentIdx) {
          status = "active";
        }
        return { key: s, label: this.t("steps." + s), status, progress: status === "completed" ? 100 : 0 };
      });
    },

    connectSSE(jobId) {
      const es = new EventSource(`/api/jobs/${jobId}/events`);
      this.eventSource = es;

      const handleEvent = (e) => {
        const data = JSON.parse(e.data);
        this._sseRetries = 0;
        this.handleSSEEvent(data);
      };

      es.addEventListener("started", handleEvent);
      es.addEventListener("completed", handleEvent);
      es.addEventListener("failed", handleEvent);
      es.addEventListener("progress", handleEvent);
      es.addEventListener("job_complete", handleEvent);
      es.addEventListener("job_failed", handleEvent);

      es.onerror = () => {
        es.close();
        this.eventSource = null;

        // Refresh job state
        if (this.selectedJob) {
          this.fetchJob(this.selectedJob.job_id).then((j) => {
            if (j) {
              this.selectedJob = j;
              this.initSteps(j);

              // Retry SSE if job still processing
              if ((j.status === "pending" || j.status === "processing") && this._sseRetries < this._sseMaxRetries) {
                this._sseRetries++;
                const delay = Math.pow(2, this._sseRetries) * 1000;
                setTimeout(() => this.connectSSE(j.job_id), delay);
              }
            }
          });
        }
      };
    },

    handleSSEEvent(data) {
      const { event, step, message, progress } = data;

      if (event === "started" && step) {
        this.setStepStatus(step, "active");
        this.setStepProgress(step, 0);
      } else if (event === "progress" && step) {
        this.setStepProgress(step, Math.round((progress || 0) * 100));
      } else if (event === "completed" && step) {
        this.setStepStatus(step, "completed");
        this.setStepProgress(step, 100);
      } else if (event === "failed" && step) {
        this.setStepStatus(step, "failed");
      } else if (event === "job_complete") {
        // Mark all pending as completed
        this.steps.forEach((s) => {
          if (s.status === "pending" || s.status === "active") {
            s.status = "completed";
          }
        });
        if (this.selectedJob) {
          this.selectedJob.status = "completed";
          this.selectedJob.has_final_video = true;
        }
        this.closeEventSource();
        this.fetchJobs();
      } else if (event === "job_failed") {
        if (this.selectedJob) {
          this.selectedJob.status = "failed";
          this.selectedJob.error = message;
        }
        this.closeEventSource();
        this.fetchJobs();
      }
    },

    setStepStatus(stepKey, status) {
      const found = this.steps.find((s) => s.key === stepKey);
      if (found) found.status = status;
    },

    setStepProgress(stepKey, pct) {
      const found = this.steps.find((s) => s.key === stepKey);
      if (found) found.progress = pct;
    },

    closeJob() {
      this.closeEventSource();
      this.selectedJob = null;
      this.steps = [];
    },

    closeEventSource() {
      if (this.eventSource) {
        this.eventSource.close();
        this.eventSource = null;
      }
    },

    // ---------- i18n ----------

    t(key) {
      // Access this.lang to create Alpine reactivity dependency
      void this.lang;
      return t(key);
    },

    switchLang(lang) {
      setLang(lang);
      // Navigate to the language subpage
      window.location.href = "/" + lang;
    },

    // ---------- Helpers ----------

    statusColor(status) {
      const map = {
        pending: "bg-slate-600",
        processing: "bg-blue-600",
        completed: "bg-emerald-600",
        failed: "bg-red-600",
      };
      return map[status] || "bg-slate-600";
    },

    stepIcon(status) {
      const map = {
        pending: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z",
        active: "M4 4v5h.582m15.356 2A8.001 8.001 0 004.582 9m0 0H9m11 11v-5h-.581m0 0a8.003 8.003 0 01-15.357-2m15.357 2H15",
        completed: "M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z",
        failed: "M10 14l2-2m0 0l2-2m-2 2l-2-2m2 2l2 2m7-2a9 9 0 11-18 0 9 9 0 0118 0z",
      };
      return map[status] || map.pending;
    },

    stepColorClass(status) {
      const map = {
        pending: "text-slate-500",
        active: "text-blue-400 step-active",
        completed: "text-emerald-400",
        failed: "text-red-400",
      };
      return map[status] || "text-slate-500";
    },

    formatDate(iso) {
      if (!iso) return "";
      const d = new Date(iso);
      return d.toLocaleString();
    },

    // Drag & drop helpers
    onDragOver(e, zone) {
      e.preventDefault();
      zone.classList.add("drag-over");
    },

    onDragLeave(e, zone) {
      zone.classList.remove("drag-over");
    },

    onDropMedia(e) {
      e.preventDefault();
      e.currentTarget.classList.remove("drag-over");
      if (e.dataTransfer.files.length > 0) {
        this.addMediaFiles(e.dataTransfer.files);
      }
    },

    addMediaFiles(fileList) {
      const incoming = Array.from(fileList);
      // Filter to only image/video types
      const valid = incoming.filter(
        (f) => f.type.startsWith("image/") || f.type.startsWith("video/")
      );
      if (valid.length < incoming.length) {
        this.uploadError = t("upload.errorInvalidFiles");
      }
      // Check max file count
      const combined = [...this.mediaFiles, ...valid];
      if (combined.length > MAX_FILES) {
        this.uploadError = t("upload.errorTooManyFiles");
        return;
      }
      // Check total size
      const totalBytes = combined.reduce((sum, f) => sum + f.size, 0);
      if (totalBytes > MAX_TOTAL_SIZE_MB * 1024 * 1024) {
        this.uploadError = t("upload.errorTotalSize");
        return;
      }
      this.mediaFiles = combined;
    },

    removeMediaFile(idx) {
      this.mediaFiles = this.mediaFiles.filter((_, i) => i !== idx);
    },

    // WhatsApp — localhost only
    openWhatsApp() {
      if (!this.otomotoPhoneNumber || !this.selectedJob) return;
      const link = document.createElement("a");
      link.href = `/api/jobs/${this.selectedJob.job_id}/output`;
      link.download = "";
      link.click();
      let phone = this.otomotoPhoneNumber.replace(/\D/g, "");
      if (phone.length === 9) phone = "48" + phone;
      const carName = this.otomotoListingTitle || (getLang() === "de" ? "Fahrzeug" : "samochód");
      const msgs = {
        pl: `Dzień dobry! Przygotowałem krótką prezentację wideo Pana/Pani ogłoszenia: ${carName}. Chętnie porozmawiam o szczegółach współpracy. Pozdrawiam!`,
        en: `Hello! I've prepared a short video presentation of your listing: ${carName}. I'd love to discuss cooperation details. Best regards!`,
        de: `Guten Tag! Ich habe eine kurze Videopräsentation Ihres Inserats erstellt: ${carName}. Ich freue mich auf ein Gespräch über die Zusammenarbeit. Mit freundlichen Grüßen!`,
      };
      const msg = msgs[getLang()] || msgs.pl;
      setTimeout(() => {
        window.open(`https://web.whatsapp.com/send?phone=${phone}&text=${encodeURIComponent(msg)}`, "_blank");
      }, 1000);
    },

    // Reel preview play/pause
    toggleReelPlay(video) {
      if (!video) return;
      if (video.paused) {
        video.play().then(() => {
          video.muted = false;
          this.reelPaused = false;
        }).catch(() => {
          // Autoplay blocked — try muted
          video.muted = true;
          video.play().then(() => { this.reelPaused = false; });
        });
      } else {
        video.pause();
        this.reelPaused = true;
      }
    },
  }));
});
