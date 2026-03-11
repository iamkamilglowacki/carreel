"""JSON file-based job persistence."""

import json
import logging
from pathlib import Path

from app.config import settings
from app.models import JobContext, JobStatus
from app.services.file_manager import get_job_dir

logger = logging.getLogger(__name__)

METADATA_FILE = "job.json"


def _metadata_path(job_id: str) -> Path:
    return get_job_dir(job_id) / METADATA_FILE


def save_job(ctx: JobContext) -> None:
    """Persist job context to disk as JSON."""
    path = _metadata_path(ctx.job_id)
    data = {
        "job_id": ctx.job_id,
        "session_id": ctx.session_id,
        "status": ctx.status.value,
        "current_step": ctx.current_step.value if ctx.current_step else None,
        "error": ctx.error,
        "created_at": ctx.created_at,
        "transcript": ctx.transcript,
        "script": ctx.script,
        "voice_memo_path": str(ctx.voice_memo_path) if ctx.voice_memo_path else None,
        "voiceover_path": str(ctx.voiceover_path) if ctx.voiceover_path else None,
        "raw_media_paths": [str(p) for p in ctx.raw_media_paths],
        "processed_clips": [str(p) for p in ctx.processed_clips],
        "captions_path": str(ctx.captions_path) if ctx.captions_path else None,
        "final_video_path": str(ctx.final_video_path) if ctx.final_video_path else None,
        "timestamps": ctx.timestamps,
    }
    path.write_text(json.dumps(data, indent=2))


def load_job(job_id: str) -> JobContext | None:
    """Load job context from disk."""
    path = _metadata_path(job_id)
    if not path.exists():
        return None

    data = json.loads(path.read_text())
    ctx = JobContext(
        job_id=data["job_id"],
        session_id=data.get("session_id", ""),
        job_dir=get_job_dir(job_id),
        status=JobStatus(data["status"]),
        current_step=data.get("current_step"),
        error=data.get("error", ""),
        created_at=data.get("created_at", ""),
        transcript=data.get("transcript", ""),
        script=data.get("script", {}),
        voice_memo_path=Path(data["voice_memo_path"]) if data.get("voice_memo_path") else None,
        voiceover_path=Path(data["voiceover_path"]) if data.get("voiceover_path") else None,
        raw_media_paths=[Path(p) for p in data.get("raw_media_paths", [])],
        processed_clips=[Path(p) for p in data.get("processed_clips", [])],
        captions_path=Path(data["captions_path"]) if data.get("captions_path") else None,
        final_video_path=Path(data["final_video_path"]) if data.get("final_video_path") else None,
        timestamps=data.get("timestamps", []),
    )
    return ctx


def list_jobs(session_id: str = "") -> list[dict]:
    """List jobs filtered by session_id."""
    jobs_dir = settings.jobs_dir
    if not jobs_dir.exists():
        return []

    results = []
    for job_dir in sorted(jobs_dir.iterdir()):
        if not job_dir.is_dir():
            continue
        meta = job_dir / METADATA_FILE
        if meta.exists():
            try:
                data = json.loads(meta.read_text())
                if session_id and data.get("session_id", "") != session_id:
                    continue
                results.append({
                    "job_id": data["job_id"],
                    "status": data["status"],
                    "current_step": data.get("current_step"),
                    "error": data.get("error", ""),
                    "created_at": data.get("created_at", ""),
                    "has_final_video": data.get("final_video_path") is not None,
                    "media_count": len(data.get("raw_media_paths", [])),
                })
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning("Skipping corrupt job metadata %s: %s", job_dir.name, e)

    return results


def delete_job(job_id: str) -> bool:
    """Remove job metadata. Physical files handled by file_manager."""
    path = _metadata_path(job_id)
    return path.exists()
