"""Assemble processed clips, voiceover, and captions into the final video."""

import math
import logging
from pathlib import Path

from app.ffmpeg.commands import concat_videos, get_duration, overlay_audio_and_captions
from app.ffmpeg.runner import run_ffmpeg
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)


class VideoAssembler(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.VIDEO_ASSEMBLE

    async def process(self, ctx: JobContext, progress=None) -> AgentResult:
        if not ctx.processed_clips:
            return AgentResult(
                success=False, step=self.step, message="No processed clips to assemble"
            )
        if not ctx.voiceover_path:
            return AgentResult(
                success=False, step=self.step, message="No voiceover audio available"
            )

        total_steps = 4

        # 1. Get voiceover duration to calculate how many clip loops we need
        audio_duration_str = await run_ffmpeg(get_duration(ctx.voiceover_path))
        audio_duration = float(audio_duration_str.strip())
        logger.info("Voiceover duration: %.2fs — video will match this length", audio_duration)
        if progress:
            await progress(1, total_steps)

        # 2. Calculate total clip duration and repeat clips to cover audio
        clip_durations: list[float] = []
        for clip in ctx.processed_clips:
            dur_str = await run_ffmpeg(get_duration(clip))
            clip_durations.append(float(dur_str.strip()))
        one_pass_duration = sum(clip_durations)

        if one_pass_duration > 0:
            loops_needed = math.ceil(audio_duration / one_pass_duration)
        else:
            loops_needed = 1

        clip_sequence = ctx.processed_clips * loops_needed

        # 3. Write the concat file with looped clips
        concat_file = ctx.job_dir / "concat.txt"
        concat_lines = [f"file '{clip.name}'" for clip in clip_sequence]
        concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        logger.info(
            "Concat file: %d clips × %d loops = %d entries (%.1fs per pass, %.1fs audio)",
            len(ctx.processed_clips), loops_needed, len(clip_sequence),
            one_pass_duration, audio_duration,
        )

        silent_video = ctx.job_dir / "silent.mp4"
        cmd_concat = concat_videos(clip_sequence, silent_video, concat_file)
        await run_ffmpeg(cmd_concat, timeout=180)
        if progress:
            await progress(3, total_steps)

        # 4. Overlay audio and captions, trim to audio duration
        from app.pipeline.agents.caption_generator import get_fonts_dir

        final_path = ctx.job_dir / "final.mp4"
        cmd_overlay = overlay_audio_and_captions(
            video_path=silent_video,
            audio_path=ctx.voiceover_path,
            captions_path=ctx.captions_path,
            output_path=final_path,
            audio_duration=audio_duration,
            fonts_dir=get_fonts_dir(),
        )
        await run_ffmpeg(cmd_overlay, timeout=180)
        if progress:
            await progress(4, total_steps)

        ctx.final_video_path = final_path
        return AgentResult(
            success=True,
            step=self.step,
            message=f"Final video assembled: {final_path.name} ({audio_duration:.1f}s)",
        )
