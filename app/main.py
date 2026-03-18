"""FastAPI application entry point."""

import logging
import logging.handlers
import threading
import uuid
from contextlib import asynccontextmanager
from pathlib import Path

import httpx

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")


class DiscordHandler(logging.Handler):
    """Send ERROR+ log records to a Discord webhook (non-blocking)."""

    def __init__(self, webhook_url: str):
        super().__init__(level=logging.ERROR)
        self.webhook_url = webhook_url

    def emit(self, record: logging.LogRecord) -> None:
        try:
            msg = self.format(record)
            # Truncate to Discord's 2000 char limit
            if len(msg) > 1950:
                msg = msg[:1950] + "..."
            # Fire-and-forget in a thread to never block the event loop
            threading.Thread(
                target=self._send, args=(msg,), daemon=True
            ).start()
        except Exception:
            self.handleError(record)

    def _send(self, message: str) -> None:
        try:
            httpx.post(
                self.webhook_url,
                json={"content": f"```\n{message}\n```"},
                timeout=5,
            )
        except Exception:
            pass  # don't crash the app over a notification failure


_discord_url = (
    "https://discord.com/api/webhooks/"
    "1483808630930276432/Q9tWUJu4abO1kNfFubHdx9yDKnPEbVWhtVqf8zn_K_p6pUpk-yu1pDNYtohtEU6zcP4w"
)
_discord_handler = DiscordHandler(_discord_url)
_discord_handler.setFormatter(logging.Formatter("%(levelname)s %(name)s: %(message)s"))
logging.getLogger().addHandler(_discord_handler)

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import Response

from app.services.event_bus import EventBus
from app.services.file_manager import ensure_jobs_dir

SESSION_COOKIE = "carreel_session"


@asynccontextmanager
async def lifespan(app: FastAPI):
    ensure_jobs_dir()
    app.state.event_bus = EventBus()
    yield


app = FastAPI(title="CarReel", lifespan=lifespan)


class SessionMiddleware(BaseHTTPMiddleware):
    """Assign a persistent session cookie to each browser."""

    async def dispatch(self, request: Request, call_next):
        session_id = request.cookies.get(SESSION_COOKIE)
        if not session_id:
            session_id = uuid.uuid4().hex
        request.state.session_id = session_id
        response: Response = await call_next(request)
        if SESSION_COOKIE not in request.cookies:
            response.set_cookie(
                SESSION_COOKIE,
                session_id,
                max_age=60 * 60 * 24 * 365,
                httponly=True,
                samesite="lax",
            )
        return response


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
app.add_middleware(SessionMiddleware)

# Mount API router
from app.api.router import api_router  # noqa: E402
from fastapi.responses import HTMLResponse, RedirectResponse  # noqa: E402

app.include_router(api_router)

# Language routes — serve index.html with lang preset
static_dir = Path(__file__).parent / "static"
_index_html = (static_dir / "index.html").read_text(encoding="utf-8")

SUPPORTED_LANGS = {"pl", "en", "de"}


@app.get("/")
async def root_redirect():
    return RedirectResponse(url="/pl", status_code=302)


@app.get("/pl")
@app.get("/en")
@app.get("/de")
async def lang_page(request: Request):
    lang = request.url.path.strip("/")
    lang_script = f'<script>localStorage.setItem("lang","{lang}")</script>'
    html = _index_html.replace("</head>", f"{lang_script}\n</head>")
    return HTMLResponse(html)


# Mount static files for JS/CSS/images (no html=True so it won't catch /)
app.mount("/", StaticFiles(directory=str(static_dir)), name="static")
