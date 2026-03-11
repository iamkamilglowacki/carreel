"""File download endpoint."""

from fastapi import APIRouter, HTTPException, Request
from fastapi.responses import FileResponse

from app.services.job_store import load_job

router = APIRouter()


@router.get("/jobs/{job_id}/output")
async def download_output(request: Request, job_id: str):
    """Download the final rendered video for a job."""
    ctx = load_job(job_id)
    if ctx is None or ctx.session_id != request.state.session_id:
        raise HTTPException(status_code=404, detail="Job not found")

    if ctx.final_video_path is None or not ctx.final_video_path.exists():
        raise HTTPException(status_code=404, detail="Output video not yet available")

    return FileResponse(
        path=str(ctx.final_video_path),
        media_type="video/mp4",
        filename=f"reel_{job_id}.mp4",
    )
