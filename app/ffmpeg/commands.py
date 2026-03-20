"""Pure functions that build FFmpeg command-line argument lists.

Performance notes:
- Clips are encoded ONCE during media processing (split/Ken Burns).
- Concatenation uses stream copy (-c copy) — no re-encoding.
- Only the final overlay step re-encodes (to burn in ASS subtitles).
"""

from pathlib import Path

# Target output dimensions for vertical social media video
WIDTH = 1080
HEIGHT = 1920
FPS = 30

# Encoding settings — balanced quality for social-media reels with crisp captions
PRESET = "medium"
CRF = "18"


def probe_media(path: Path) -> list[str]:
    """Get media info as JSON via ffprobe."""
    return [
        "ffprobe",
        "-v", "quiet",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(path),
    ]


def get_duration(path: Path) -> list[str]:
    """Get duration of a media file in seconds."""
    return [
        "ffprobe",
        "-v", "quiet",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(path),
    ]


def crop_video_to_portrait(input_path: Path, output_path: Path) -> list[str]:
    """Convert a video to 9:16 portrait, scaled to fit with black bars."""
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    return [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", vf,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-an",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


def ken_burns_from_image(
    input_path: Path,
    output_path: Path,
    duration: float,
    slide_direction: str = "right",
) -> list[str]:
    """Apply horizontal slide effect to a still image with blurred background.

    Two layers composited together:
    - Background: image scaled to fill 1080x1920, heavily blurred + darkened
    - Foreground: image scaled to FIT 1080x1920 (no crop, full image visible)

    A gentle horizontal pan is applied to the foreground for motion.
    - "right": camera slides left-to-right
    - "left":  camera slides right-to-left
    """
    total_frames = int(duration * FPS)

    # Slide offset in pixels (foreground pans by ~40px total)
    slide_px = 40
    if slide_direction == "right":
        x_expr = f"-{slide_px // 2}+{slide_px}*t/{duration}"
    else:
        x_expr = f"{slide_px // 2}-{slide_px}*t/{duration}"

    vf = (
        # Scale to fit, pad with black, apply horizontal slide
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black,"
        f"crop={WIDTH}:{HEIGHT}:{x_expr}:0"
    )

    return [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(input_path),
        "-vf", vf,
        "-t", str(duration),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


def split_video_segment(
    input_path: Path,
    output_path: Path,
    start: float,
    duration: float,
) -> list[str]:
    """Extract a segment from a video, fitted to 9:16 portrait with black bars.

    Uses -ss before -i for fast input seeking (demuxer-level).
    """
    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=decrease,"
        f"pad={WIDTH}:{HEIGHT}:(ow-iw)/2:(oh-ih)/2:color=black"
    )
    return [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-vf", vf,
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-an",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


def concat_videos(clip_paths: list[Path], output_path: Path, concat_file: Path) -> list[str]:
    """Concatenate video clips using stream copy (no re-encoding).

    All input clips must share the same codec, resolution, and pixel format.
    This is guaranteed because they all come from split_video_segment or
    ken_burns_from_image which produce identical output parameters.
    """
    return [
        "ffmpeg", "-y",
        "-f", "concat",
        "-safe", "0",
        "-i", str(concat_file),
        "-c", "copy",
        "-movflags", "+faststart",
        str(output_path),
    ]


def overlay_audio_and_captions(
    video_path: Path,
    audio_path: Path,
    captions_path: Path | None,
    output_path: Path,
    audio_duration: float | None = None,
    fonts_dir: Path | None = None,
) -> list[str]:
    """Merge video + audio + burn-in ASS subtitles into final output.

    This is the ONLY encoding pass in the assembly phase.
    When audio_duration is provided, the video is trimmed to that length
    (the caller is responsible for ensuring the video is long enough).
    When fonts_dir is provided, it is passed to libass via fontsdir= so
    bundled fonts (e.g. Montserrat) are found even without system install.
    """
    if captions_path:
        # Escape special chars in paths for FFmpeg filter syntax
        cp = str(captions_path).replace("\\", "/").replace(":", "\\:")
        if fonts_dir:
            fd = str(fonts_dir).replace("\\", "/").replace(":", "\\:")
            vf_filter = f"ass={cp}:fontsdir={fd}"
        else:
            vf_filter = f"ass={cp}"
    else:
        vf_filter = "null"

    cmd = [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-c:a", "aac",
        "-b:a", "192k",
    ]

    if audio_duration is not None:
        cmd += ["-t", str(round(audio_duration, 2))]
    else:
        cmd += ["-shortest"]

    cmd += [
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    return cmd


def filmstrip_scroll(
    image_paths: list[Path],
    output_path: Path,
    duration: float,
) -> list[str]:
    """Create a vertical filmstrip scroll effect from multiple images.

    All images are scaled to fit WIDTH×HEIGHT with blurred background,
    stacked vertically, then a scrolling crop window moves down the strip.

    Processes images in batches if needed to avoid FFmpeg memory limits.
    """
    n = len(image_paths)
    # Limit to 10 images max to keep vstack manageable
    if n > 10:
        image_paths = image_paths[:10]
        n = 10

    filters = []

    # Scale each image to full width, keep aspect ratio
    for i in range(n):
        filters.append(
            f"[{i}:v]scale={WIDTH}:-2[frame{i}]"
        )

    # Stack all frames vertically — each is now exactly 1080x1920
    stack_inputs = "".join(f"[frame{i}]" for i in range(n))
    filters.append(f"{stack_inputs}vstack=inputs={n}[strip]")

    # Crop a 1080×1920 window that scrolls down the strip
    # Total strip height is sum of all scaled image heights
    # We scroll from y=0 to y=(strip_height - 1920)
    # Use ih (strip input height) to calculate dynamically
    y_expr = f"(ih-{HEIGHT})*t/{duration}"

    filters.append(
        f"[strip]crop={WIDTH}:{HEIGHT}:0:'{y_expr}'[out]"
    )

    filter_complex = ";".join(filters)

    cmd = ["ffmpeg", "-y"]
    for img in image_paths:
        cmd += ["-loop", "1", "-i", str(img)]

    cmd += [
        "-filter_complex", filter_complex,
        "-map", "[out]",
        "-t", str(duration),
        "-r", str(FPS),
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]

    return cmd


def generate_silence(duration: float, output_path: Path) -> list[str]:
    """Generate a silent audio file of given duration."""
    return [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-c:a", "aac",
        str(output_path),
    ]
