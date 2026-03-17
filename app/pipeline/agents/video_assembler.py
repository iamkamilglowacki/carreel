"""Assemble processed clips, voiceover, and captions into the final video."""

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

        # 1. Write the concat file
        concat_file = ctx.job_dir / "concat.txt"
        concat_lines = [f"file '{clip.name}'" for clip in ctx.processed_clips]
        concat_file.write_text("\n".join(concat_lines) + "\n", encoding="utf-8")
        logger.info("Concat file: %d clips", len(ctx.processed_clips))
        if progress:
            await progress(1, total_steps)

        # 2. Concatenate clips into one silent video
        silent_video = ctx.job_dir / "silent.mp4"
        cmd_concat = concat_videos(ctx.processed_clips, silent_video, concat_file)
        await run_ffmpeg(cmd_concat, timeout=180)
        if progress:
            await progress(2, total_steps)

        # 3. Get voiceover duration so the final video matches it exactly
        if progress:
            await progress(3, total_steps)
        audio_duration_str = await run_ffmpeg(get_duration(ctx.voiceover_path))
        audio_duration = float(audio_duration_str.strip())
        logger.info("Voiceover duration: %.2fs — video will match this length", audio_duration)

        # 4. Overlay audio and captions, looping video to match audio length
        final_path = ctx.job_dir / "final.mp4"
        cmd_overlay = overlay_audio_and_captions(
            video_path=silent_video,
            audio_path=ctx.voiceover_path,
            captions_path=ctx.captions_path,
            output_path=final_path,
            audio_duration=audio_duration,
        )
        await run_ffmpeg(cmd_overlay, timeout=180)
        if progress:
            await progress(4, total_steps)

        ctx.final_video_path = final_path
        return AgentResult(
            success=True,
            step=self.step,
            message=f"Final video assembled: {final_path.name}",
        )
