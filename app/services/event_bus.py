"""In-memory pub/sub event bus for SSE broadcasting."""

import asyncio
from dataclasses import dataclass


@dataclass
class JobEvent:
    job_id: str
    event: str  # "started", "completed", "failed", "job_complete", "job_failed"
    step: str | None
    message: str


class EventBus:
    """In-memory SSE event broadcaster.

    Each job can have multiple SSE subscribers (browser tabs).
    Events are pushed to all subscribers of a given job_id.
    """

    def __init__(self) -> None:
        self._subscribers: dict[str, list[asyncio.Queue[JobEvent]]] = {}

    def subscribe(self, job_id: str) -> asyncio.Queue[JobEvent]:
        """Subscribe to events for a job. Returns an asyncio.Queue."""
        queue: asyncio.Queue[JobEvent] = asyncio.Queue()
        self._subscribers.setdefault(job_id, []).append(queue)
        return queue

    def unsubscribe(self, job_id: str, queue: asyncio.Queue[JobEvent]) -> None:
        """Remove a subscriber."""
        queues = self._subscribers.get(job_id, [])
        try:
            queues.remove(queue)
        except ValueError:
            pass
        if not queues and job_id in self._subscribers:
            del self._subscribers[job_id]

    async def publish(self, event: JobEvent) -> None:
        """Publish an event to all subscribers of a job."""
        for queue in self._subscribers.get(event.job_id, []):
            await queue.put(event)
