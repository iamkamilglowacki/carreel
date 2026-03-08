"""Sequential pipeline runner that executes agents in order."""

import logging
from collections.abc import Callable, Sequence
from typing import Awaitable

from app.models import AgentResult, JobContext, JobStatus, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

EventCallback = Callable[[PipelineStep, str, str], Awaitable[None]] | None


async def run_pipeline(
    agents: Sequence[BaseAgent],
    ctx: JobContext,
    on_event: EventCallback = None,
) -> JobContext:
    """Run each agent in sequence, updating *ctx* as we go.

    Parameters
    ----------
    agents:
        Ordered list of agents to execute.
    ctx:
        Mutable job context shared across all agents.
    on_event:
        Optional async callback ``(step, status, message)`` fired at the
        start, completion, or failure of each step.
    """
    ctx.status = JobStatus.PROCESSING

    for agent in agents:
        step = agent.step
        ctx.current_step = step
        logger.info("[%s] Starting step: %s", ctx.job_id, step.value)

        # Skip transcription when transcript is already provided
        if step == PipelineStep.TRANSCRIBE and ctx.transcript:
            logger.info("[%s] Transcript pre-populated, skipping transcription", ctx.job_id)
            if on_event:
                await on_event(step, "started", f"Starting {step.value}")
                await on_event(step, "completed", "Transcript provided by user")
            continue

        if on_event:
            await on_event(step, "started", f"Starting {step.value}")

        try:
            result: AgentResult = await agent.process(ctx)
        except Exception as exc:
            ctx.status = JobStatus.FAILED
            ctx.error = f"{step.value}: {exc}"
            logger.exception("[%s] Step %s failed", ctx.job_id, step.value)
            if on_event:
                await on_event(step, "failed", str(exc))
            return ctx

        if not result.success:
            ctx.status = JobStatus.FAILED
            ctx.error = f"{step.value}: {result.message}"
            logger.error("[%s] Step %s returned failure: %s", ctx.job_id, step.value, result.message)
            if on_event:
                await on_event(step, "failed", result.message)
            return ctx

        logger.info("[%s] Completed step: %s", ctx.job_id, step.value)
        if on_event:
            await on_event(step, "completed", result.message or f"Completed {step.value}")

    ctx.status = JobStatus.COMPLETED
    ctx.current_step = None
    logger.info("[%s] Pipeline completed successfully", ctx.job_id)
    return ctx
