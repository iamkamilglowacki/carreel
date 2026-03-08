"""Mock transcriber that returns a hardcoded car transcript."""

import asyncio

from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

MOCK_TRANSCRIPT = (
    "Hej, zobaczcie to BMW M4 Competition z 2021 roku. Właśnie przyjechało na plac. "
    "Wygląda absolutnie fenomenalnie w kolorze Alpine White. Pod maską pracuje "
    "doładowany rzędowy sześciocylindrowy silnik o mocy 503 koni mechanicznych. "
    "Przebieg tylko 35 tysięcy kilometrów. Wnętrze w idealnym stanie, czerwona "
    "skóra, wykończenia z włókna węglowego wszędzie. Poprzedni właściciel dbał "
    "o ten samochód perfekcyjnie. Jeśli szukasz auta na co dzień, które daje też "
    "kopa w weekend, to jest to. Przyjedź, zanim ktoś Cię ubiegnie."
)


class MockTranscriber(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.TRANSCRIBE

    async def process(self, ctx: JobContext) -> AgentResult:
        await asyncio.sleep(0.1)  # simulate latency
        ctx.transcript = MOCK_TRANSCRIPT
        return AgentResult(
            success=True,
            step=self.step,
            message="Returned mock transcript",
        )
