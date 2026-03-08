"""Mock scriptwriter that builds a script from the user transcript.

Falls back to a hardcoded demo script when no transcript is provided.
"""

import asyncio
import re

from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

MOCK_SCRIPT: dict = {
    "voiceover_text": (
        "BMW M4 Competition z 2021 roku. Alpine White. 503 konie mechaniczne, "
        "doładowany rzędowy sześciocylindrowiec. Przebieg tylko 35 tysięcy "
        "kilometrów. Wnętrze w idealnym stanie, czerwona skóra i włókno węglowe. "
        "Idealne połączenie codziennego komfortu i weekendowej mocy. "
        "Ten egzemplarz długo nie postoi."
    ),
    "segments": [
        {"text": "BMW M4 Competition z 2021 roku.", "duration": 3.0, "media_index": 0},
        {"text": "Alpine White. 503 konie mechaniczne, doładowany rzędowy sześciocylindrowiec.", "duration": 4.5, "media_index": 1},
        {"text": "Przebieg tylko 35 tysięcy kilometrów.", "duration": 2.5, "media_index": 2},
        {"text": "Wnętrze w idealnym stanie, czerwona skóra i włókno węglowe.", "duration": 4.0, "media_index": 3},
        {"text": "Idealne połączenie codziennego komfortu i weekendowej mocy.", "duration": 3.5, "media_index": 4},
        {"text": "Ten egzemplarz długo nie postoi.", "duration": 2.5, "media_index": 5},
    ],
}

# Average speaking rate in Polish: ~3 seconds per short sentence, scaled by length
_BASE_DURATION_PER_CHAR = 0.07  # seconds per character (approx)


def _build_script_from_transcript(transcript: str, media_count: int) -> dict:
    """Split transcript into sentences and build a script dict."""
    # Split on sentence-ending punctuation, keeping the delimiter
    raw_parts = re.split(r"(?<=[.!?])\s+", transcript.strip())
    sentences = [s.strip() for s in raw_parts if s.strip()]

    if not sentences:
        return MOCK_SCRIPT

    total_chars = sum(len(s) for s in sentences)
    # Total duration estimate based on character count
    total_duration = max(total_chars * _BASE_DURATION_PER_CHAR, len(sentences) * 2.0)

    segments = []
    for i, sentence in enumerate(sentences):
        duration = (len(sentence) / total_chars) * total_duration if total_chars else 3.0
        duration = round(max(duration, 1.5), 1)  # minimum 1.5s per segment
        segments.append({
            "text": sentence,
            "duration": duration,
            "media_index": i % media_count if media_count > 0 else i,
        })

    voiceover_text = " ".join(s["text"] for s in segments)
    return {"voiceover_text": voiceover_text, "segments": segments}


class MockScriptwriter(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.SCRIPTWRITE

    async def process(self, ctx: JobContext) -> AgentResult:
        await asyncio.sleep(0.1)  # simulate latency

        if ctx.transcript.strip():
            media_count = len(ctx.raw_media_paths)
            ctx.script = _build_script_from_transcript(ctx.transcript, media_count)
            n = len(ctx.script["segments"])
            return AgentResult(
                success=True,
                step=self.step,
                message=f"Built script from transcript ({n} segments)",
            )

        ctx.script = MOCK_SCRIPT
        return AgentResult(
            success=True,
            step=self.step,
            message="No transcript provided — returned mock script with 6 segments",
        )
