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

# Encoding settings — tuned for speed on social-media reels
PRESET = "veryfast"
CRF = "23"


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
    """Crop a video to 9:16 portrait, centering on the source."""
    return [
        "ffmpeg", "-y",
        "-i", str(input_path),
        "-vf", (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        ),
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
    zoom_direction: str = "in",
) -> list[str]:
    """Apply Ken Burns (zoom + pan) effect to a still image."""
    total_frames = int(duration * FPS)

    x_expr = f"iw/2-(iw/zoom/2)+on*0.5/{total_frames}"
    y_expr = f"ih/2-(ih/zoom/2)"

    if zoom_direction == "in":
        zoom_expr = f"zoom+0.3/{total_frames}"
    else:
        zoom_expr = f"if(eq(on,1),1.3,zoom-0.3/{total_frames})"

    vf = (
        f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
        f"crop={WIDTH}:{HEIGHT},"
        f"zoompan=z='{zoom_expr}'"
        f":x='{x_expr}':y='{y_expr}'"
        f":d={total_frames}:s={WIDTH}x{HEIGHT}:fps={FPS}"
    )

    return [
        "ffmpeg", "-y",
        "-loop", "1",
        "-i", str(input_path),
        "-vf", vf,
        "-t", str(duration),
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
    """Extract a segment from a video, cropped to 9:16 portrait.

    Uses -ss before -i for fast input seeking (demuxer-level).
    """
    return [
        "ffmpeg", "-y",
        "-ss", str(start),
        "-i", str(input_path),
        "-t", str(duration),
        "-vf", (
            f"scale={WIDTH}:{HEIGHT}:force_original_aspect_ratio=increase,"
            f"crop={WIDTH}:{HEIGHT}"
        ),
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
) -> list[str]:
    """Merge video + audio + burn-in ASS subtitles into final output.

    This is the ONLY encoding pass in the assembly phase.
    """
    vf_filter = f"ass={captions_path}" if captions_path else "null"

    return [
        "ffmpeg", "-y",
        "-i", str(video_path),
        "-i", str(audio_path),
        "-vf", vf_filter,
        "-c:v", "libx264",
        "-preset", PRESET,
        "-crf", CRF,
        "-c:a", "aac",
        "-b:a", "128k",
        "-shortest",
        "-pix_fmt", "yuv420p",
        "-movflags", "+faststart",
        str(output_path),
    ]


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
