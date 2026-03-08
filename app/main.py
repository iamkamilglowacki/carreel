"""FastAPI application entry point."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.event_bus import EventBus
from app.services.file_manager import ensure_jobs_dir


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_jobs_dir()
    app.state.event_bus = EventBus()
    yield


app = FastAPI(title="ReelDealer AI", lifespan=lifespan)


class NoCacheStaticMiddleware(BaseHTTPMiddleware):
    """Prevent browser caching of static assets during development."""

    async def dispatch(self, request: Request, call_next):
        response: Response = await call_next(request)
        path = request.url.path
        if path.endswith((".js", ".css", ".html")):
            response.headers["Cache-Control"] = "no-cache, no-store, must-revalidate"
            response.headers["Pragma"] = "no-cache"
            response.headers["Expires"] = "0"
        return response


app.add_middleware(NoCacheStaticMiddleware)

# Mount API router
from app.api.router import api_router  # noqa: E402

app.include_router(api_router)

# Mount static files last (catch-all for the SPA)
static_dir = Path(__file__).parent / "static"
app.mount("/", StaticFiles(directory=str(static_dir), html=True), name="static")
