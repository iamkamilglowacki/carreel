/* CarReel - Alpine.js application logic */

document.addEventListener("alpine:init", () => {
  Alpine.data("reelApp", () => ({
    // State
    jobs: [],
    selectedJob: null,
    steps: [],
    uploading: false,
    uploadError: "",
    eventSource: null,

    // i18n
    lang: getLang(),

    // Input
    isRecording: false,
    mediaRecorder: null,
    audioChunks: [],
    recordedBlob: null,
    typedTranscript: "",

    // File inputs
    mediaFiles: [],

    // Reel preview playback
    reelPaused: true,

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
      // Poll for job list updates every 5 seconds
      setInterval(() => this.fetchJobs(), 5000);
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
      for (const f of this.mediaFiles) {
        form.append("media", f);
      }

      try {
        const res = await fetch("/api/jobs", { method: "POST", body: form });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          this.uploadError = err.detail || t("upload.errorUpload");
          return;
        }

        const data = await res.json();
        this.recordedBlob = null;
        this.typedTranscript = "";
        this.mediaFiles = [];

        // Reset file input
        const mediaInput = document.getElementById("media-input");
        if (mediaInput) mediaInput.value = "";

        await this.fetchJobs();
        this.selectJob(data.job_id);
      } catch (e) {
        this.uploadError = t("upload.errorNetwork") + e.message;
      } finally {
        this.uploading = false;
      }
    },

    async deleteJob(jobId) {
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
        return { key: s, label: t("steps." + s), status, progress: status === "completed" ? 100 : 0 };
      });
    },

    connectSSE(jobId) {
      const es = new EventSource(`/api/jobs/${jobId}/events`);
      this.eventSource = es;

      const handleEvent = (e) => {
        const data = JSON.parse(e.data);
        this.handleSSEEvent(data);
      };

      es.addEventListener("started", handleEvent);
      es.addEventListener("completed", handleEvent);
      es.addEventListener("failed", handleEvent);
      es.addEventListener("progress", handleEvent);
      es.addEventListener("job_complete", handleEvent);
      es.addEventListener("job_failed", handleEvent);

      es.onerror = () => {
        // Reconnect will be automatic with EventSource, or job is done
        es.close();
        this.eventSource = null;
        // Refresh job state
        if (this.selectedJob) {
          this.fetchJob(this.selectedJob.job_id).then((j) => {
            if (j) {
              this.selectedJob = j;
              this.initSteps(j);
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

    switchLang(lang) {
      setLang(lang);
      this.lang = lang;
      // Re-init step labels if job is selected
      if (this.selectedJob) {
        this.initSteps(this.selectedJob);
      }
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
        this.mediaFiles = [...this.mediaFiles, ...Array.from(e.dataTransfer.files)];
      }
    },

    addMediaFiles(fileList) {
      this.mediaFiles = [...this.mediaFiles, ...Array.from(fileList)];
    },

    removeMediaFile(idx) {
      this.mediaFiles = this.mediaFiles.filter((_, i) => i !== idx);
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
