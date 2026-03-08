"""Async subprocess runner for FFmpeg commands."""

import asyncio
import logging

logger = logging.getLogger(__name__)


class FFmpegError(Exception):
    def __init__(self, returncode: int, stderr: str):
        self.returncode = returncode
        self.stderr = stderr
        super().__init__(f"FFmpeg exited with code {returncode}: {stderr[-500:]}")


async def run_ffmpeg(cmd: list[str], timeout: float = 300) -> str:
    """Run an FFmpeg/ffprobe command asynchronously.

    Returns stdout as string. Raises FFmpegError on non-zero exit.
    """
    logger.info("Running: %s", " ".join(cmd))

    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )

    try:
        stdout_bytes, stderr_bytes = await asyncio.wait_for(
            proc.communicate(), timeout=timeout
        )
    except asyncio.TimeoutError:
        proc.kill()
        await proc.communicate()
        raise FFmpegError(-1, "Command timed out")

    stdout = stdout_bytes.decode(errors="replace")
    stderr = stderr_bytes.decode(errors="replace")

    if proc.returncode != 0:
        logger.error("FFmpeg stderr: %s", stderr[-1000:])
        raise FFmpegError(proc.returncode, stderr)

    return stdout
