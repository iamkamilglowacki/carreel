from abc import ABC, abstractmethod

from app.models import AgentResult, JobContext, PipelineStep


class BaseAgent(ABC):
    """Abstract base class for pipeline agents."""

    @property
    @abstractmethod
    def step(self) -> PipelineStep:
        """Which pipeline step this agent handles."""
        ...

    @abstractmethod
    async def process(self, ctx: JobContext) -> AgentResult:
        """Process a job context. Mutate ctx in-place and return result."""
        ...
