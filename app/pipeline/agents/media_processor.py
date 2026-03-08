"""Process raw media files into portrait-format clips for each script segment."""

import json
import logging
from pathlib import Path

from app.ffmpeg.commands import crop_video_to_portrait, ken_burns_from_image, probe_media
from app.ffmpeg.runner import run_ffmpeg
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm"}


def _classify_media(path: Path, probe_data: dict | None = None) -> str:
    """Return 'image' or 'video' based on extension, falling back to probe data."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    # Ambiguous extension -- inspect streams from ffprobe
    if probe_data:
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                # Check if it has more than 1 frame (heuristic for true video)
                nb_frames = stream.get("nb_frames", "1")
                if nb_frames != "N/A" and int(nb_frames) > 1:
                    return "video"
        return "image"
    return "image"  # safe default


class MediaProcessor(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.MEDIA_PROCESS

    async def process(self, ctx: JobContext) -> AgentResult:
        segments = ctx.script.get("segments", [])
        if not segments:
            return AgentResult(
                success=False, step=self.step, message="No segments in script"
            )

        raw_paths = ctx.raw_media_paths
        if not raw_paths:
            return AgentResult(
                success=False, step=self.step, message="No raw media files provided"
            )

        processed: list[Path] = []
        zoom_directions = ["in", "out"]

        for i, segment in enumerate(segments):
            media_path = raw_paths[i % len(raw_paths)]  # cycle if fewer files
            duration = float(segment.get("duration", 3.0))
            output_path = ctx.job_dir / f"clip_{i:03d}.mp4"

            # Classify the media file
            ext = media_path.suffix.lower()
            if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
                probe_json = await run_ffmpeg(probe_media(media_path))
                probe_data = json.loads(probe_json)
            else:
                probe_data = None

            media_type = _classify_media(media_path, probe_data)

            if media_type == "image":
                zoom = zoom_directions[i % len(zoom_directions)]
                cmd = ken_burns_from_image(media_path, output_path, duration, zoom)
            else:
                cmd = crop_video_to_portrait(media_path, output_path)

            logger.info("Processing segment %d: %s (%s)", i, media_path.name, media_type)
            await run_ffmpeg(cmd, timeout=120)
            processed.append(output_path)

        ctx.processed_clips = processed
        return AgentResult(
            success=True,
            step=self.step,
            message=f"Processed {len(processed)} clips",
        )
