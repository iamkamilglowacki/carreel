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

    // Top-level section (reels or comparator)
    mainSection: "reels",

    // Create reel tab (url or manual)
    createTab: "url",

    // Comparator state
    comparatorUrl: "",
    comparatorLoading: false,
    comparatorError: "",
    comparatorListing: null,

    // Reel preview playback
    reelPaused: true,
    reelCurrentTime: 0,
    reelDuration: 0,
    _reelRAF: null,
    _reelSeeking: false,

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

    removeListingPhoto(idx) {
      if (!this.otomotoListing) return;
      this.otomotoListing.photo_urls = this.otomotoListing.photo_urls.filter((_, i) => i !== idx);
    },

    async generateFromOtomoto() {
      const url = this.otomotoUrl.trim();
      if (!url) return;
      const source = this._detectSource(url);
      this.otomotoGenerating = true;
      this.otomotoError = "";
      this.otomotoSalesCopy = "";

      const photoUrls = this.otomotoListing ? this.otomotoListing.photo_urls : null;
      const endpoint = source === "mobile" ? "/api/mobile-job" : "/api/otomoto-job";
      try {
        const res = await fetch(endpoint, {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, lang: getLang(), photo_urls: photoUrls }),
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
      this._stopTimeTracking();
      this.selectedJob = null;
      this.steps = [];
      this.reelPaused = true;
      this.reelCurrentTime = 0;
      this.reelDuration = 0;
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

    // ---------- Otomoto search link from mobile.de data ----------

    buildOtomotoSearchUrl() {
      const l = this.otomotoListing;
      if (!l || !l.make) return null;

      // Make slug mapping: mobile.de name → otomoto URL slug
      const makeMap = {
        "Abarth": "abarth", "Alfa Romeo": "alfa-romeo", "Audi": "audi",
        "BMW": "bmw", "Chevrolet": "chevrolet", "Chrysler": "chrysler",
        "Citroën": "citroen", "Cupra": "cupra", "Dacia": "dacia",
        "DS": "ds-automobiles", "Dodge": "dodge", "Fiat": "fiat",
        "Ford": "ford", "Honda": "honda", "Hyundai": "hyundai",
        "Infiniti": "infiniti", "Jaguar": "jaguar", "Jeep": "jeep",
        "Kia": "kia", "Lancia": "lancia", "Land Rover": "land-rover",
        "Lexus": "lexus", "Maserati": "maserati", "Mazda": "mazda",
        "Mercedes-Benz": "mercedes-benz", "MINI": "mini", "Mitsubishi": "mitsubishi",
        "Nissan": "nissan", "Opel": "opel", "Peugeot": "peugeot",
        "Porsche": "porsche", "Renault": "renault", "Seat": "seat",
        "Škoda": "skoda", "Skoda": "skoda", "Smart": "smart",
        "Subaru": "subaru", "Suzuki": "suzuki", "Tesla": "tesla",
        "Toyota": "toyota", "Volkswagen": "volkswagen", "Volvo": "volvo",
      };

      // Model slug mapping: mobile.de model → otomoto slug
      const modelMap = {
        // BMW
        "1er": "seria-1", "2er": "seria-2", "3er": "seria-3", "4er": "seria-4",
        "5er": "seria-5", "6er": "seria-6", "7er": "seria-7", "8er": "seria-8",
        "X1": "x1", "X2": "x2", "X3": "x3", "X4": "x4", "X5": "x5", "X6": "x6", "X7": "x7",
        "Z4": "z4", "i3": "i3", "i4": "i4", "i5": "i5", "i7": "i7", "iX": "ix", "iX3": "ix3",
        // Mercedes
        "A-Klasse": "klasa-a", "B-Klasse": "klasa-b", "C-Klasse": "klasa-c",
        "E-Klasse": "klasa-e", "S-Klasse": "klasa-s", "G-Klasse": "klasa-g",
        "V-Klasse": "klasa-v", "CLA": "cla", "CLS": "cls", "GLA": "gla",
        "GLB": "glb", "GLC": "glc", "GLE": "gle", "GLS": "gls", "AMG GT": "amg-gt",
        "EQA": "eqa", "EQB": "eqb", "EQC": "eqc", "EQE": "eqe", "EQS": "eqs",
        // Audi
        "A1": "a1", "A3": "a3", "A4": "a4", "A5": "a5", "A6": "a6", "A7": "a7", "A8": "a8",
        "Q2": "q2", "Q3": "q3", "Q4 e-tron": "q4-e-tron", "Q5": "q5", "Q7": "q7", "Q8": "q8",
        "e-tron": "e-tron", "e-tron GT": "e-tron-gt", "TT": "tt", "R8": "r8",
        // VW
        "Golf": "golf", "Passat": "passat", "Polo": "polo", "Tiguan": "tiguan",
        "T-Roc": "t-roc", "T-Cross": "t-cross", "Touareg": "touareg",
        "Touran": "touran", "Arteon": "arteon", "ID.3": "id.3", "ID.4": "id.4", "ID.5": "id.5",
        "Caddy": "caddy", "Multivan": "multivan", "Transporter": "transporter",
      };

      // Fuel type mapping: German → Otomoto enum value
      const fuelMap = {
        "Benzin": "petrol", "Diesel": "diesel", "Elektro": "electric",
        "Hybrid (Benzin/Elektro)": "hybrid", "Hybrid (Diesel/Elektro)": "hybrid",
        "Plug-in-Hybrid": "hybrid", "Erdgas (CNG)": "cng", "Autogas (LPG)": "petrol-lpg",
        "Wasserstoff": "hydrogen",
      };

      const makeSlug = makeMap[l.make] || l.make.toLowerCase().replace(/\s+/g, "-");
      const modelSlug = modelMap[l.model] || l.model.toLowerCase().replace(/\s+/g, "-");

      // Extract year from "Erstzulassung" (e.g. "03/2020" or "2020")
      let year = "";
      if (l.year) {
        const ym = l.year.match(/(\d{4})/);
        if (ym) year = ym[1];
      }

      // Extract mileage number (e.g. "85.000 km" → 85000)
      let mileageNum = 0;
      if (l.mileage) {
        const cleaned = l.mileage.replace(/[.\s]/g, "").replace(/,/g, "");
        const mm = cleaned.match(/(\d+)/);
        if (mm) mileageNum = parseInt(mm[1], 10);
      }

      // Build URL
      let path = `https://www.otomoto.pl/osobowe/${makeSlug}`;
      if (modelSlug) path += `/${modelSlug}`;
      if (year) path += `/od-${year}`;

      const params = new URLSearchParams();
      if (year) {
        params.set("search[filter_float_year:to]", year);
      }

      // Fuel type
      const fuelVal = fuelMap[l.fuel_type];
      if (fuelVal) {
        params.set("search[filter_enum_fuel_type]", fuelVal);
      }

      // Mileage range: ±20%
      if (mileageNum > 0) {
        const from = Math.max(0, Math.round(mileageNum * 0.8 / 5000) * 5000);
        const to = Math.round(mileageNum * 1.2 / 5000) * 5000;
        params.set("search[filter_float_mileage:from]", String(from));
        params.set("search[filter_float_mileage:to]", String(to));
      }

      const qs = params.toString();
      return qs ? `${path}?${qs}` : path;
    },

    openOtomotoSearch() {
      const url = this.buildOtomotoSearchUrl();
      if (url) window.open(url, "_blank");
    },

    // ---------- Comparator (Mobile.de → Otomoto) ----------

    async comparatorFetch() {
      const url = this.comparatorUrl.trim();
      if (!url || !url.includes("mobile.de")) {
        this.comparatorError = t("comparator.errorUrl");
        return;
      }
      this.comparatorLoading = true;
      this.comparatorError = "";
      this.comparatorListing = null;

      try {
        const res = await fetch("/api/scrape-mobile", {
          method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ url, lang: "de" }),
        });
        if (!res.ok) {
          const err = await res.json().catch(() => ({}));
          throw new Error(err.detail || t("comparator.errorScrape"));
        }
        this.comparatorListing = await res.json();
      } catch (e) {
        this.comparatorError = e.message;
      } finally {
        this.comparatorLoading = false;
      }
    },

    buildComparatorOtomotoUrl() {
      const l = this.comparatorListing;
      if (!l || !l.make) return null;

      // Reuse the same mapping logic
      const makeMap = {
        "Abarth": "abarth", "Alfa Romeo": "alfa-romeo", "Audi": "audi",
        "BMW": "bmw", "Chevrolet": "chevrolet", "Chrysler": "chrysler",
        "Citroën": "citroen", "Cupra": "cupra", "Dacia": "dacia",
        "DS": "ds-automobiles", "Dodge": "dodge", "Fiat": "fiat",
        "Ford": "ford", "Honda": "honda", "Hyundai": "hyundai",
        "Infiniti": "infiniti", "Jaguar": "jaguar", "Jeep": "jeep",
        "Kia": "kia", "Lancia": "lancia", "Land Rover": "land-rover",
        "Lexus": "lexus", "Maserati": "maserati", "Mazda": "mazda",
        "Mercedes-Benz": "mercedes-benz", "MINI": "mini", "Mitsubishi": "mitsubishi",
        "Nissan": "nissan", "Opel": "opel", "Peugeot": "peugeot",
        "Porsche": "porsche", "Renault": "renault", "Seat": "seat",
        "Škoda": "skoda", "Skoda": "skoda", "Smart": "smart",
        "Subaru": "subaru", "Suzuki": "suzuki", "Tesla": "tesla",
        "Toyota": "toyota", "Volkswagen": "volkswagen", "Volvo": "volvo",
      };

      const modelMap = {
        "1er": "seria-1", "2er": "seria-2", "3er": "seria-3", "4er": "seria-4",
        "5er": "seria-5", "6er": "seria-6", "7er": "seria-7", "8er": "seria-8",
        "X1": "x1", "X2": "x2", "X3": "x3", "X4": "x4", "X5": "x5", "X6": "x6", "X7": "x7",
        "Z4": "z4", "i3": "i3", "i4": "i4", "i5": "i5", "i7": "i7", "iX": "ix", "iX3": "ix3",
        "A-Klasse": "klasa-a", "B-Klasse": "klasa-b", "C-Klasse": "klasa-c",
        "E-Klasse": "klasa-e", "S-Klasse": "klasa-s", "G-Klasse": "klasa-g",
        "V-Klasse": "klasa-v", "CLA": "cla", "CLS": "cls", "GLA": "gla",
        "GLB": "glb", "GLC": "glc", "GLE": "gle", "GLS": "gls", "AMG GT": "amg-gt",
        "EQA": "eqa", "EQB": "eqb", "EQC": "eqc", "EQE": "eqe", "EQS": "eqs",
        "A1": "a1", "A3": "a3", "A4": "a4", "A5": "a5", "A6": "a6", "A7": "a7", "A8": "a8",
        "Q2": "q2", "Q3": "q3", "Q4 e-tron": "q4-e-tron", "Q5": "q5", "Q7": "q7", "Q8": "q8",
        "e-tron": "e-tron", "e-tron GT": "e-tron-gt", "TT": "tt", "R8": "r8",
        "Golf": "golf", "Passat": "passat", "Polo": "polo", "Tiguan": "tiguan",
        "T-Roc": "t-roc", "T-Cross": "t-cross", "Touareg": "touareg",
        "Touran": "touran", "Arteon": "arteon", "ID.3": "id.3", "ID.4": "id.4", "ID.5": "id.5",
        "Caddy": "caddy", "Multivan": "multivan", "Transporter": "transporter",
      };

      const fuelMap = {
        "Benzin": "petrol", "Diesel": "diesel", "Elektro": "electric",
        "Hybrid (Benzin/Elektro)": "hybrid", "Hybrid (Diesel/Elektro)": "hybrid",
        "Plug-in-Hybrid": "hybrid", "Erdgas (CNG)": "cng", "Autogas (LPG)": "petrol-lpg",
        "Wasserstoff": "hydrogen",
      };

      const makeSlug = makeMap[l.make] || l.make.toLowerCase().replace(/\s+/g, "-");
      const modelSlug = modelMap[l.model] || l.model.toLowerCase().replace(/\s+/g, "-");

      let year = "";
      if (l.year) {
        const ym = l.year.match(/(\d{4})/);
        if (ym) year = ym[1];
      }

      let mileageNum = 0;
      if (l.mileage) {
        const cleaned = l.mileage.replace(/[.\s]/g, "").replace(/,/g, "");
        const mm = cleaned.match(/(\d+)/);
        if (mm) mileageNum = parseInt(mm[1], 10);
      }

      let path = `https://www.otomoto.pl/osobowe/${makeSlug}`;
      if (modelSlug) path += `/${modelSlug}`;
      if (year) path += `/od-${year}`;

      const params = new URLSearchParams();
      if (year) params.set("search[filter_float_year:to]", year);
      const fuelVal = fuelMap[l.fuel_type];
      if (fuelVal) params.set("search[filter_enum_fuel_type]", fuelVal);
      if (mileageNum > 0) {
        const from = Math.max(0, Math.round(mileageNum * 0.8 / 5000) * 5000);
        const to = Math.round(mileageNum * 1.2 / 5000) * 5000;
        params.set("search[filter_float_mileage:from]", String(from));
        params.set("search[filter_float_mileage:to]", String(to));
      }

      const qs = params.toString();
      return qs ? `${path}?${qs}` : path;
    },

    openComparatorOtomotoSearch() {
      const url = this.buildComparatorOtomotoUrl();
      if (url) window.open(url, "_blank");
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
          this._startTimeTracking(video);
        }).catch(() => {
          video.muted = true;
          video.play().then(() => {
            this.reelPaused = false;
            this._startTimeTracking(video);
          });
        });
      } else {
        video.pause();
        this.reelPaused = true;
        this._stopTimeTracking();
      }
    },

    _startTimeTracking(video) {
      this._stopTimeTracking();
      const tick = () => {
        this.reelCurrentTime = video.currentTime || 0;
        this.reelDuration = video.duration || 0;
        this._reelRAF = requestAnimationFrame(tick);
      };
      tick();
    },

    _stopTimeTracking() {
      if (this._reelRAF) {
        cancelAnimationFrame(this._reelRAF);
        this._reelRAF = null;
      }
    },

    seekReel(event) {
      const video = this.$refs.reelVideo;
      if (!video || !video.duration) return;
      const bar = event.currentTarget;
      const rect = bar.getBoundingClientRect();
      const clientX = event.touches ? event.touches[0].clientX : event.clientX;
      const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
      video.currentTime = ratio * video.duration;
      this.reelCurrentTime = video.currentTime;
    },

    startSeekDrag(event) {
      event.preventDefault();
      this._reelSeeking = true;
      this._seekBar = event.currentTarget;
      const video = this.$refs.reelVideo;
      this._wasPlaying = video && !video.paused;
      if (video && !video.paused) video.pause();
      this.seekReel(event);

      const onMove = (e) => {
        if (!this._reelSeeking) return;
        // Reuse seekReel logic with the stored bar
        const video = this.$refs.reelVideo;
        if (!video || !video.duration) return;
        const rect = this._seekBar.getBoundingClientRect();
        const clientX = e.touches ? e.touches[0].clientX : e.clientX;
        const ratio = Math.max(0, Math.min(1, (clientX - rect.left) / rect.width));
        video.currentTime = ratio * video.duration;
        this.reelCurrentTime = video.currentTime;
      };

      const onUp = () => {
        this._reelSeeking = false;
        document.removeEventListener("mousemove", onMove);
        document.removeEventListener("mouseup", onUp);
        document.removeEventListener("touchmove", onMove);
        document.removeEventListener("touchend", onUp);
        const video = this.$refs.reelVideo;
        if (this._wasPlaying && video) {
          video.play();
          this.reelPaused = false;
        }
      };

      document.addEventListener("mousemove", onMove);
      document.addEventListener("mouseup", onUp);
      document.addEventListener("touchmove", onMove, { passive: false });
      document.addEventListener("touchend", onUp);
    },

    formatTime(sec) {
      if (!sec || !isFinite(sec)) return "0:00";
      const m = Math.floor(sec / 60);
      const s = Math.floor(sec % 60);
      return m + ":" + (s < 10 ? "0" : "") + s;
    },
  }));
});
