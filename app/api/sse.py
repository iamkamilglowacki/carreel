"""Server-Sent Events endpoint for live job progress."""

import asyncio
import json

from fastapi import APIRouter, Request
from starlette.responses import StreamingResponse

from app.services.event_bus import EventBus, JobEvent

router = APIRouter()

PING_INTERVAL = 15  # seconds


@router.get("/jobs/{job_id}/events")
async def job_events(job_id: str, request: Request):
    """Stream SSE events for a specific job."""
    event_bus: EventBus = request.app.state.event_bus

    async def event_generator():
        queue = event_bus.subscribe(job_id)
        try:
            while True:
                # Check for client disconnect
                if await request.is_disconnected():
                    break

                try:
                    event: JobEvent = await asyncio.wait_for(
                        queue.get(), timeout=PING_INTERVAL
                    )
                    payload = {
                        "event": event.event,
                        "step": event.step,
                        "message": event.message,
                    }
                    if event.progress is not None:
                        payload["progress"] = event.progress
                    data = json.dumps(payload)
                    yield f"event: {event.event}\ndata: {data}\n\n"

                    # Stop streaming after terminal events
                    if event.event in ("job_complete", "job_failed"):
                        break
                except asyncio.TimeoutError:
                    # Send keep-alive ping
                    yield ": ping\n\n"
        finally:
            event_bus.unsubscribe(job_id, queue)

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
