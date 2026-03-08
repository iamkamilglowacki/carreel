"""Mock voiceover that uses macOS `say` + FFmpeg to produce real audio."""

import asyncio
import logging
from pathlib import Path

from app.ffmpeg.commands import get_duration
from app.ffmpeg.runner import run_ffmpeg
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)


class MockVoiceover(BaseAgent):
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

        aiff_path = ctx.job_dir / "voiceover.aiff"
        wav_path = ctx.job_dir / "voiceover.wav"

        # Generate audio using macOS say (explicit voice required — default Siri voice
        # may produce empty files with -o on some systems)
        say_proc = await asyncio.create_subprocess_exec(
            "say", "-v", "Zosia", "-o", str(aiff_path), voiceover_text,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
        _, stderr = await say_proc.communicate()
        if say_proc.returncode != 0:
            return AgentResult(
                success=False,
                step=self.step,
                message=f"say command failed: {stderr.decode(errors='replace')}",
            )

        # Convert AIFF to WAV
        await run_ffmpeg([
            "ffmpeg", "-y",
            "-i", str(aiff_path),
            str(wav_path),
        ])

        # Get the real audio duration
        duration_str = await run_ffmpeg(get_duration(wav_path))
        total_duration = float(duration_str.strip())
        logger.info("Voiceover duration: %.2fs", total_duration)

        # Estimate word-level timestamps from duration and word lengths
        words = voiceover_text.split()
        char_counts = [len(w) for w in words]
        total_chars = sum(char_counts)

        timestamps = []
        cursor = 0.0
        for word, ccount in zip(words, char_counts):
            word_dur = (ccount / total_chars) * total_duration
            timestamps.append({
                "word": word,
                "start": round(cursor, 3),
                "end": round(cursor + word_dur, 3),
            })
            cursor += word_dur

        ctx.voiceover_path = wav_path
        ctx.timestamps = timestamps

        return AgentResult(
            success=True,
            step=self.step,
            message=f"Generated voiceover ({total_duration:.1f}s, {len(words)} words)",
        )
