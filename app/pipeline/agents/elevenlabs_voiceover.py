"""Voiceover agent using ElevenLabs TTS with word-level timestamps."""

import base64
import logging

import httpx

from app.config import settings
from app.ffmpeg.commands import get_duration
from app.ffmpeg.runner import run_ffmpeg
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

_API_BASE = "https://api.elevenlabs.io/v1"


def _chars_to_word_timestamps(
    characters: list[str],
    start_times: list[float],
    end_times: list[float],
) -> list[dict]:
    """Convert character-level timestamps into word-level timestamps.

    Groups characters by spaces to reconstruct words and their time spans.
    """
    words: list[dict] = []
    current_word_chars: list[str] = []
    word_start: float | None = None

    for char, t_start, t_end in zip(characters, start_times, end_times):
        if char == " ":
            # Flush current word
            if current_word_chars and word_start is not None:
                words.append({
                    "word": "".join(current_word_chars),
                    "start": round(word_start, 3),
                    "end": round(t_start, 3),  # word ends where the space starts
                })
            current_word_chars = []
            word_start = None
        else:
            if word_start is None:
                word_start = t_start
            current_word_chars.append(char)

    # Flush the last word
    if current_word_chars and word_start is not None:
        words.append({
            "word": "".join(current_word_chars),
            "start": round(word_start, 3),
            "end": round(end_times[-1], 3) if end_times else round(word_start, 3),
        })

    return words


class ElevenLabsVoiceover(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.VOICEOVER

    async def process(self, ctx: JobContext) -> AgentResult:
        voiceover_text = ctx.script.get("voiceover_text", "")
        if not voiceover_text:
            return AgentResult(
                success=False,
                step=self.step,
                message="No voiceover_text found in script",
            )

        default_voice = settings.elevenlabs_voice_id
        voice_ids = {
            "pl": settings.elevenlabs_voice_id_pl or default_voice,
            "en": settings.elevenlabs_voice_id_en or default_voice,
            "de": settings.elevenlabs_voice_id_de or default_voice,
        }
        voice_id = voice_ids.get(ctx.language, default_voice)
        if not voice_id:
            return AgentResult(
                success=False,
                step=self.step,
                message="ELEVENLABS_VOICE_ID is not set in config",
            )

        api_key = settings.elevenlabs_api_key
        if not api_key:
            return AgentResult(
                success=False,
                step=self.step,
                message="ELEVENLABS_API_KEY is not set in config",
            )

        url = f"{_API_BASE}/text-to-speech/{voice_id}/with-timestamps"
        headers = {
            "xi-api-key": api_key,
            "Content-Type": "application/json",
        }
        payload = {
            "text": voiceover_text,
            "model_id": "eleven_v3",
            "voice_settings": {
                "stability": 0.3,
                "similarity_boost": 0.75,
                "style": 0.4,
            },
        }

        logger.info("Calling ElevenLabs TTS for %d characters", len(voiceover_text))

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(url, json=payload, headers=headers)

        if resp.status_code != 200:
            return AgentResult(
                success=False,
                step=self.step,
                message=f"ElevenLabs API error {resp.status_code}: {resp.text[:300]}",
            )

        data = resp.json()

        # Decode and save audio
        audio_bytes = base64.b64decode(data["audio_base64"])
        audio_path = ctx.job_dir / "voiceover.mp3"
        audio_path.write_bytes(audio_bytes)
        logger.info("Saved voiceover audio to %s (%d bytes)", audio_path, len(audio_bytes))

        # Build word-level timestamps from character alignment
        alignment = data.get("alignment", {})
        characters = alignment.get("characters", [])
        char_starts = alignment.get("character_start_times_seconds", [])
        char_ends = alignment.get("character_end_times_seconds", [])

        if characters and char_starts and char_ends:
            timestamps = _chars_to_word_timestamps(characters, char_starts, char_ends)
        else:
            # Fallback: estimate timestamps from word lengths
            logger.warning("No alignment data from ElevenLabs, estimating timestamps")
            words = voiceover_text.split()
            total_chars = sum(len(w) for w in words)
            # Rough estimate: 150 words per minute
            total_duration = len(words) / 2.5
            cursor = 0.0
            timestamps = []
            for word in words:
                word_dur = (len(word) / total_chars) * total_duration if total_chars else 0.3
                timestamps.append({
                    "word": word,
                    "start": round(cursor, 3),
                    "end": round(cursor + word_dur, 3),
                })
                cursor += word_dur

        ctx.voiceover_path = audio_path
        ctx.timestamps = timestamps

        # Rescale script segment durations so total video length matches audio
        audio_duration_str = await run_ffmpeg(get_duration(audio_path))
        audio_duration = float(audio_duration_str.strip())
        logger.info("ElevenLabs audio duration: %.2fs", audio_duration)

        segments = ctx.script.get("segments", [])
        if segments:
            estimated_total = sum(s["duration"] for s in segments)
            if estimated_total > 0:
                scale = audio_duration / estimated_total
                for seg in segments:
                    seg["duration"] = round(seg["duration"] * scale, 2)
                logger.info(
                    "Rescaled %d segment durations: %.1fs -> %.1fs",
                    len(segments), estimated_total, audio_duration,
                )

        return AgentResult(
            success=True,
            step=self.step,
            message=f"ElevenLabs voiceover generated ({audio_duration:.1f}s, {len(timestamps)} words)",
        )
