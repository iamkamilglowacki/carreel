"""Job CRUD endpoints."""

import asyncio
import logging
from pathlib import Path

from typing import Optional

from fastapi import APIRouter, Form, HTTPException, Request, UploadFile, File

from app.dependencies import build_agents
from app.models import JobContext, JobStatus, PipelineStep
from app.services.event_bus import EventBus, JobEvent
from app.services.file_manager import create_job_dir, delete_job_dir, get_input_dir
from app.services.job_store import delete_job, list_jobs, load_job, save_job
from app.pipeline.orchestrator import run_pipeline

logger = logging.getLogger(__name__)

router = APIRouter()


async def _run_pipeline_background(ctx: JobContext, event_bus: EventBus) -> None:
    """Run the pipeline in a background task, publishing events along the way."""
    agents = build_agents()

    async def on_event(step: PipelineStep, status: str, message: str) -> None:
        await event_bus.publish(
            JobEvent(
                job_id=ctx.job_id,
                event=status,
                step=step.value,
                message=message,
            )
        )

    try:
        await run_pipeline(agents=agents, ctx=ctx, on_event=on_event)
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", ctx.job_id)
        ctx.status = JobStatus.FAILED
        ctx.error = str(exc)
        await event_bus.publish(
            JobEvent(
                job_id=ctx.job_id,
                event="failed",
                step=None,
                message=str(exc),
            )
        )

    # Persist final state
    save_job(ctx)

    # Notify subscribers the job is done
    terminal_event = "job_complete" if ctx.status == JobStatus.COMPLETED else "job_failed"
    await event_bus.publish(
        JobEvent(
            job_id=ctx.job_id,
            event=terminal_event,
            step=None,
            message=ctx.error if ctx.status == JobStatus.FAILED else "Pipeline finished",
        )
    )


@router.post("/jobs", status_code=201)
async def create_job(
    request: Request,
    media: list[UploadFile] = File(...),
    voice_memo: Optional[UploadFile] = File(None),
    transcript: Optional[str] = Form(None),
):
    """Upload media files + voice memo or typed transcript, create a job, and start the pipeline."""
    if not voice_memo and not transcript:
        raise HTTPException(
            status_code=422,
            detail="Provide either a voice memo or a typed transcript.",
        )

    event_bus: EventBus = request.app.state.event_bus

    ctx = JobContext()
    job_dir = create_job_dir(ctx.job_id)
    ctx.job_dir = job_dir

    input_dir = get_input_dir(ctx.job_id)

    # Save voice memo (if provided)
    if voice_memo:
        vm_path = input_dir / voice_memo.filename
        vm_path.write_bytes(await voice_memo.read())
        ctx.voice_memo_path = vm_path

    # Or use typed transcript directly
    if transcript:
        ctx.transcript = transcript

    # Save media files
    for f in media:
        media_path = input_dir / f.filename
        media_path.write_bytes(await f.read())
        ctx.raw_media_paths.append(media_path)

    # Persist initial state
    save_job(ctx)

    # Start pipeline in background
    asyncio.create_task(_run_pipeline_background(ctx, event_bus))

    return {"job_id": ctx.job_id, "status": ctx.status.value}


@router.get("/jobs")
async def get_jobs():
    """List all jobs."""
    return list_jobs()


@router.get("/jobs/{job_id}")
async def get_job(job_id: str):
    """Get job detail."""
    ctx = load_job(job_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return ctx.to_dict()


@router.delete("/jobs/{job_id}")
async def remove_job(job_id: str):
    """Delete a job and its files."""
    ctx = load_job(job_id)
    if ctx is None:
        raise HTTPException(status_code=404, detail="Job not found")
    delete_job_dir(job_id)
    return {"deleted": True, "job_id": job_id}
