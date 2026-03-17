"""Shared pipeline background runner for all listing sources."""

import logging

from app.dependencies import build_agents
from app.models import JobContext, JobStatus, PipelineStep
from app.services.event_bus import EventBus, JobEvent
from app.services.job_store import save_job

logger = logging.getLogger(__name__)


async def run_pipeline_background(ctx: JobContext, event_bus: EventBus) -> None:
    """Run the pipeline in a background task."""
    from app.pipeline.orchestrator import run_pipeline

    agents = build_agents()

    async def on_event(step: PipelineStep, status: str, message: str) -> None:
        await event_bus.publish(
            JobEvent(job_id=ctx.job_id, event=status, step=step.value, message=message)
        )

    async def on_progress(step: PipelineStep, current: int, total: int) -> None:
        await event_bus.publish(
            JobEvent(
                job_id=ctx.job_id,
                event="progress",
                step=step.value,
                message=f"{current}/{total}",
                progress=current / total if total > 0 else 0,
            )
        )

    try:
        await run_pipeline(agents=agents, ctx=ctx, on_event=on_event, on_progress=on_progress)
    except Exception as exc:
        logger.exception("Pipeline failed for job %s", ctx.job_id)
        ctx.status = JobStatus.FAILED
        ctx.error = str(exc)
        await event_bus.publish(
            JobEvent(job_id=ctx.job_id, event="failed", step=None, message=str(exc))
        )

    save_job(ctx)

    terminal_event = "job_complete" if ctx.status == JobStatus.COMPLETED else "job_failed"
    await event_bus.publish(
        JobEvent(
            job_id=ctx.job_id,
            event=terminal_event,
            step=None,
            message=ctx.error if ctx.status == JobStatus.FAILED else "Pipeline finished",
        )
    )
