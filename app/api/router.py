"""Top-level API router that includes all sub-routers."""

from fastapi import APIRouter

from app.api.jobs import router as jobs_router
from app.api.files import router as files_router
from app.api.sse import router as sse_router
from app.api.transcribe import router as transcribe_router
from app.api.otomoto import router as otomoto_router
from app.api.mobile import router as mobile_router

api_router = APIRouter(prefix="/api")

api_router.include_router(jobs_router, tags=["jobs"])
api_router.include_router(files_router, tags=["files"])
api_router.include_router(sse_router, tags=["sse"])
api_router.include_router(transcribe_router, tags=["transcribe"])
api_router.include_router(otomoto_router, tags=["otomoto"])
api_router.include_router(mobile_router, tags=["mobile"])
