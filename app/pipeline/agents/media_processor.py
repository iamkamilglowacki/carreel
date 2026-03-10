"""Process raw media files into portrait-format clips for each script segment.

Videos longer than SPLIT_THRESHOLD seconds are automatically split into
short dynamic fragments (SPLIT_MIN–SPLIT_MAX seconds each) so the final
reel feels fast-paced and engaging.
"""

import json
import logging
import random
from pathlib import Path

from app.ffmpeg.commands import (
    crop_video_to_portrait,
    get_duration,
    ken_burns_from_image,
    probe_media,
    split_video_segment,
)
from app.ffmpeg.runner import run_ffmpeg
from app.models import AgentResult, JobContext, PipelineStep
from app.pipeline.base import BaseAgent

logger = logging.getLogger(__name__)

IMAGE_EXTS = {".jpg", ".jpeg", ".png", ".webp"}
VIDEO_EXTS = {".mp4", ".mov", ".avi", ".webm"}

# Auto-split settings
SPLIT_THRESHOLD = 5.0  # split videos longer than 5s
SPLIT_MIN = 2.0        # minimum fragment duration
SPLIT_MAX = 3.0        # maximum fragment duration


def _classify_media(path: Path, probe_data: dict | None = None) -> str:
    """Return 'image' or 'video' based on extension, falling back to probe data."""
    ext = path.suffix.lower()
    if ext in IMAGE_EXTS:
        return "image"
    if ext in VIDEO_EXTS:
        return "video"
    if probe_data:
        for stream in probe_data.get("streams", []):
            if stream.get("codec_type") == "video":
                nb_frames = stream.get("nb_frames", "1")
                if nb_frames != "N/A" and int(nb_frames) > 1:
                    return "video"
        return "image"
    return "image"


async def _get_video_duration(path: Path) -> float:
    """Get video duration in seconds via ffprobe."""
    output = await run_ffmpeg(get_duration(path))
    return float(output.strip())


async def _split_video_into_clips(
    video_path: Path,
    job_dir: Path,
    clip_index_start: int,
) -> list[Path]:
    """Split a long video into short dynamic fragments."""
    total_duration = await _get_video_duration(video_path)

    if total_duration <= SPLIT_THRESHOLD:
        # Short video — just crop to portrait as-is
        output_path = job_dir / f"clip_{clip_index_start:03d}.mp4"
        cmd = crop_video_to_portrait(video_path, output_path)
        await run_ffmpeg(cmd, timeout=120)
        return [output_path]

    # Split into 2-3 second fragments
    clips: list[Path] = []
    pos = 0.0
    idx = clip_index_start

    while pos < total_duration - 0.5:  # skip tiny remainder
        frag_duration = round(random.uniform(SPLIT_MIN, SPLIT_MAX), 1)
        remaining = total_duration - pos
        if remaining < SPLIT_MIN:
            break
        if remaining < frag_duration + SPLIT_MIN:
            frag_duration = remaining  # use the rest

        output_path = job_dir / f"clip_{idx:03d}.mp4"
        cmd = split_video_segment(video_path, output_path, pos, frag_duration)
        logger.info(
            "Splitting %s: %.1fs–%.1fs (%.1fs)",
            video_path.name, pos, pos + frag_duration, frag_duration,
        )
        await run_ffmpeg(cmd, timeout=120)
        clips.append(output_path)

        pos += frag_duration
        idx += 1

    return clips


def _interleave(video_clips: list[Path], image_clips: list[Path]) -> list[Path]:
    """Interleave video fragments and image clips for a dynamic reel.

    Pattern: video → image → video → image → ...
    If one list runs out, the remaining items from the other list are appended.
    """
    result: list[Path] = []
    vi, ii = 0, 0

    while vi < len(video_clips) and ii < len(image_clips):
        result.append(video_clips[vi])
        vi += 1
        # After every 2 video clips, insert an image for variety
        if vi % 2 == 0 or vi >= len(video_clips):
            result.append(image_clips[ii])
            ii += 1

    # Append remaining clips
    result.extend(video_clips[vi:])
    result.extend(image_clips[ii:])

    return result


class MediaProcessor(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.MEDIA_PROCESS

    async def process(self, ctx: JobContext) -> AgentResult:
        raw_paths = ctx.raw_media_paths
        if not raw_paths:
            return AgentResult(
                success=False, step=self.step, message="No raw media files provided"
            )

        # Phase 1: Classify all media
        images: list[Path] = []
        videos: list[Path] = []

        for media_path in raw_paths:
            ext = media_path.suffix.lower()
            if ext not in IMAGE_EXTS and ext not in VIDEO_EXTS:
                probe_json = await run_ffmpeg(probe_media(media_path))
                probe_data = json.loads(probe_json)
            else:
                probe_data = None

            if _classify_media(media_path, probe_data) == "image":
                images.append(media_path)
            else:
                videos.append(media_path)

        # Phase 2: Split all videos into short fragments
        video_clips: list[Path] = []
        clip_idx = 0

        for video_path in videos:
            logger.info("Splitting video: %s", video_path.name)
            clips = await _split_video_into_clips(video_path, ctx.job_dir, clip_idx)
            video_clips.extend(clips)
            clip_idx += len(clips)

        # Phase 3: Create Ken Burns clips from all images
        image_clips: list[Path] = []
        zoom_directions = ["in", "out"]
        image_duration = 2.5  # each image shows for 2.5s

        for i, img_path in enumerate(images):
            output_path = ctx.job_dir / f"clip_{clip_idx:03d}.mp4"
            zoom = zoom_directions[i % len(zoom_directions)]
            cmd = ken_burns_from_image(img_path, output_path, image_duration, zoom)
            logger.info("Processing image: %s (Ken Burns %s)", img_path.name, zoom)
            await run_ffmpeg(cmd, timeout=120)
            image_clips.append(output_path)
            clip_idx += 1

        # Phase 4: Interleave video fragments and images
        if video_clips and image_clips:
            processed = _interleave(video_clips, image_clips)
        else:
            processed = video_clips or image_clips

        if not processed:
            return AgentResult(
                success=False, step=self.step, message="No clips produced"
            )

        ctx.processed_clips = processed
        return AgentResult(
            success=True,
            step=self.step,
            message=f"Processed {len(processed)} clips "
                    f"({len(video_clips)} video fragments + {len(image_clips)} images, interleaved)",
        )
