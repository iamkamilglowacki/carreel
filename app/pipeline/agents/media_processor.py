"""Process raw media files into portrait-format clips for each script segment.

Videos longer than SPLIT_THRESHOLD seconds are automatically split into
short dynamic fragments (SPLIT_MIN–SPLIT_MAX seconds each) so the final
reel feels fast-paced and engaging.

Performance: video segments and image clips are processed in parallel.
"""

import asyncio
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
SPLIT_THRESHOLD = 5.0   # split videos longer than 5s
CLIP_DURATION = 2.0     # each clip is 2 seconds
MAX_CLIPS_PER_VIDEO = 15

# Max concurrent ffmpeg processes to avoid saturating CPU
MAX_CONCURRENT_FFMPEG = 6


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


async def _plan_video_splits(
    video_path: Path,
    job_dir: Path,
    clip_index_start: int,
) -> list[tuple[Path, list[str]]]:
    """Plan split commands for a video without executing them.

    Returns a list of (output_path, ffmpeg_cmd) tuples.
    """
    total_duration = await _get_video_duration(video_path)

    if total_duration <= SPLIT_THRESHOLD:
        output_path = job_dir / f"clip_{clip_index_start:03d}.mp4"
        cmd = crop_video_to_portrait(video_path, output_path)
        return [(output_path, cmd)]

    # Pick up to MAX_CLIPS_PER_VIDEO evenly spaced clips of CLIP_DURATION seconds
    num_clips = min(MAX_CLIPS_PER_VIDEO, int(total_duration / CLIP_DURATION))
    spacing = total_duration / num_clips

    planned: list[tuple[Path, list[str]]] = []
    idx = clip_index_start

    for i in range(num_clips):
        pos = round(i * spacing, 2)
        output_path = job_dir / f"clip_{idx:03d}.mp4"
        cmd = split_video_segment(video_path, output_path, pos, CLIP_DURATION)
        logger.info(
            "Planned split %s: %.1fs–%.1fs (%.1fs)",
            video_path.name, pos, pos + CLIP_DURATION, CLIP_DURATION,
        )
        planned.append((output_path, cmd))
        idx += 1

    return planned


def _interleave(video_clips: list[Path], image_clips: list[Path]) -> list[Path]:
    """Interleave video fragments and image clips for a dynamic reel."""
    result: list[Path] = []
    vi, ii = 0, 0

    while vi < len(video_clips) and ii < len(image_clips):
        result.append(video_clips[vi])
        vi += 1
        if vi % 2 == 0 or vi >= len(video_clips):
            result.append(image_clips[ii])
            ii += 1

    result.extend(video_clips[vi:])
    result.extend(image_clips[ii:])

    return result


class MediaProcessor(BaseAgent):
    @property
    def step(self) -> PipelineStep:
        return PipelineStep.MEDIA_PROCESS

    async def process(self, ctx: JobContext, progress=None) -> AgentResult:
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

        # Phase 2: Plan all work (lightweight — only ffprobe calls)
        semaphore = asyncio.Semaphore(MAX_CONCURRENT_FFMPEG)
        done_counter = 0

        # Plan video splits (needs ffprobe for duration)
        all_video_plans: list[tuple[Path, list[str]]] = []
        clip_idx = 0
        for video_path in videos:
            plans = await _plan_video_splits(video_path, ctx.job_dir, clip_idx)
            all_video_plans.extend(plans)
            clip_idx += len(plans)

        # Plan image Ken Burns commands
        zoom_directions = ["in", "out"]
        image_duration = 2.5
        all_image_plans: list[tuple[Path, list[str]]] = []
        for i, img_path in enumerate(images):
            output_path = ctx.job_dir / f"clip_{clip_idx:03d}.mp4"
            zoom = zoom_directions[i % len(zoom_directions)]
            cmd = ken_burns_from_image(img_path, output_path, image_duration, zoom)
            all_image_plans.append((output_path, cmd))
            clip_idx += 1

        # Phase 3: Execute ALL ffmpeg commands in parallel (bounded by semaphore)
        total_tasks = len(all_video_plans) + len(all_image_plans)

        async def _run_one(cmd: list[str]) -> None:
            nonlocal done_counter
            async with semaphore:
                await run_ffmpeg(cmd, timeout=120)
            done_counter += 1
            if progress:
                await progress(done_counter, total_tasks)

        all_tasks = [
            _run_one(cmd)
            for _, cmd in all_video_plans + all_image_plans
        ]
        await asyncio.gather(*all_tasks)

        # Collect results in planned order
        video_clips = [path for path, _ in all_video_plans]
        image_clips = [path for path, _ in all_image_plans]

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
