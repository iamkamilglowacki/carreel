"""Per-job directory and file management."""

import shutil
from pathlib import Path

from app.config import settings


def ensure_jobs_dir() -> Path:
    """Create and return the top-level jobs directory."""
    jobs_dir = settings.jobs_dir
    jobs_dir.mkdir(parents=True, exist_ok=True)
    return jobs_dir


def create_job_dir(job_id: str) -> Path:
    """Create a directory for a specific job, including subdirs."""
    job_dir = ensure_jobs_dir() / job_id
    job_dir.mkdir(parents=True, exist_ok=True)
    (job_dir / "input").mkdir(exist_ok=True)
    (job_dir / "processing").mkdir(exist_ok=True)
    (job_dir / "output").mkdir(exist_ok=True)
    return job_dir


def get_job_dir(job_id: str) -> Path:
    return settings.jobs_dir / job_id


def delete_job_dir(job_id: str) -> bool:
    """Delete a job's directory tree. Returns True if it existed."""
    job_dir = get_job_dir(job_id)
    if job_dir.exists():
        shutil.rmtree(job_dir)
        return True
    return False


def get_input_dir(job_id: str) -> Path:
    return get_job_dir(job_id) / "input"


def get_processing_dir(job_id: str) -> Path:
    return get_job_dir(job_id) / "processing"


def get_output_dir(job_id: str) -> Path:
    return get_job_dir(job_id) / "output"
