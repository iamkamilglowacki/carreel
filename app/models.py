from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Any


class JobStatus(str, Enum):
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStep(str, Enum):
    TRANSCRIBE = "transcribe"
    SCRIPTWRITE = "scriptwrite"
    VOICEOVER = "voiceover"
    MEDIA_PROCESS = "media_process"
    CAPTION_GENERATE = "caption_generate"
    VIDEO_ASSEMBLE = "video_assemble"


@dataclass
class AgentResult:
    success: bool
    step: PipelineStep
    message: str = ""
    data: dict[str, Any] = field(default_factory=dict)


@dataclass
class JobContext:
    """Mutable context passed through the pipeline. Each agent reads/writes fields."""

    job_id: str = field(default_factory=lambda: uuid.uuid4().hex[:12])
    job_dir: Path = field(default_factory=lambda: Path("."))

    # Input files
    voice_memo_path: Path | None = None
    raw_media_paths: list[Path] = field(default_factory=list)

    # Pipeline artifacts (populated by agents)
    transcript: str = ""
    script: dict[str, Any] = field(default_factory=dict)
    voiceover_path: Path | None = None
    timestamps: list[dict[str, Any]] = field(default_factory=list)
    processed_clips: list[Path] = field(default_factory=list)
    captions_path: Path | None = None
    final_video_path: Path | None = None

    # Status tracking
    status: JobStatus = JobStatus.PENDING
    current_step: PipelineStep | None = None
    error: str = ""
    created_at: str = field(
        default_factory=lambda: datetime.now(timezone.utc).isoformat()
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "job_id": self.job_id,
            "status": self.status.value if isinstance(self.status, Enum) else self.status,
            "current_step": self.current_step.value if isinstance(self.current_step, Enum) else self.current_step,
            "error": self.error,
            "created_at": self.created_at,
            "has_transcript": bool(self.transcript),
            "has_script": bool(self.script),
            "has_voiceover": self.voiceover_path is not None,
            "has_captions": self.captions_path is not None,
            "has_final_video": self.final_video_path is not None,
            "media_count": len(self.raw_media_paths),
        }
