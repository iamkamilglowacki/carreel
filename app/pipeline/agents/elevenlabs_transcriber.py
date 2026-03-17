"""Transcribe voice memos using ElevenLabs Scribe v2 Speech-to-Text API."""

import logging

import httpx

from app.config import settings
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

_API_URL = "https://api.elevenlabs.io/v1/speech-to-text"


class ElevenLabsTranscriber(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.TRANSCRIBE

    async def process(self, ctx: JobContext, progress=None) -> AgentResult:
        if not ctx.voice_memo_path or not ctx.voice_memo_path.exists():
            return AgentResult(
                success=False,
                step=self.step,
                message="No voice memo file found",
            )

        api_key = settings.elevenlabs_api_key
        if not api_key:
            return AgentResult(
                success=False,
                step=self.step,
                message="ELEVENLABS_API_KEY is not set in config",
            )

        headers = {"xi-api-key": api_key}

        audio_bytes = ctx.voice_memo_path.read_bytes()
        filename = ctx.voice_memo_path.name

        lang_map = {"pl": "pol", "en": "eng", "de": "deu"}
        language_code = lang_map.get(ctx.language, "pol")

        files = {"file": (filename, audio_bytes)}
        data = {
            "model_id": "scribe_v2",
            "language_code": language_code,
            "timestamps_granularity": "word",
            "tag_audio_events": "false",
            "diarize": "false",
        }

        logger.info(
            "Calling ElevenLabs STT for %s (%.1f KB)",
            filename,
            len(audio_bytes) / 1024,
        )

        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                _API_URL, headers=headers, files=files, data=data
            )

        if resp.status_code != 200:
            return AgentResult(
                success=False,
                step=self.step,
                message=f"ElevenLabs STT error {resp.status_code}: {resp.text[:300]}",
            )

        result = resp.json()

        transcript = result.get("text", "").strip()
        if not transcript:
            return AgentResult(
                success=False,
                step=self.step,
                message="ElevenLabs returned empty transcript",
            )

        ctx.transcript = transcript

        logger.info(
            "Transcription complete: %d characters, language: %s (%.0f%% confidence)",
            len(transcript),
            result.get("language_code", "?"),
            (result.get("language_probability", 0) or 0) * 100,
        )

        return AgentResult(
            success=True,
            step=self.step,
            message=f"Transcribed {len(transcript)} chars ({len(transcript.split())} words)",
        )
