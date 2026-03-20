"""Otomoto scraping endpoint."""

import asyncio
import logging

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from app.models import JobContext
from app.services.event_bus import EventBus
from app.services.file_manager import create_job_dir, get_input_dir
from app.services.job_store import save_job
from app.services.otomoto_scraper import scrape_otomoto, download_photos
from app.services.copywriter import generate_sales_copy
from app.services.pipeline_runner import run_pipeline_background

logger = logging.getLogger(__name__)

router = APIRouter()


class OtomotoRequest(BaseModel):
    url: str
    lang: str = "pl"
    photo_urls: list[str] | None = None


@router.post("/scrape-otomoto")
async def scrape_listing(body: OtomotoRequest):
    """Scrape an Otomoto listing and return structured data (preview only)."""
    try:
        listing = await scrape_otomoto(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to scrape Otomoto URL: %s", body.url)
        raise HTTPException(status_code=502, detail=f"Nie udało się pobrać ogłoszenia: {exc}")
    return listing.to_dict()


@router.post("/otomoto-job", status_code=201)
async def create_otomoto_job(request: Request, body: OtomotoRequest):
    """Scrape Otomoto listing, download photos, and start the reel pipeline."""
    try:
        listing = await scrape_otomoto(body.url)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    except Exception as exc:
        logger.exception("Failed to scrape Otomoto URL: %s", body.url)
        raise HTTPException(status_code=502, detail=f"Nie udało się pobrać ogłoszenia: {exc}")

    # Use user-curated photo list if provided (photos removed in preview)
    if body.photo_urls is not None:
        listing.photo_urls = body.photo_urls

    if not listing.photo_urls:
        raise HTTPException(status_code=400, detail="Ogłoszenie nie zawiera zdjęć.")

    event_bus: EventBus = request.app.state.event_bus

    ctx = JobContext()
    ctx.session_id = request.state.session_id
    ctx.language = body.lang if body.lang in ("pl", "en", "de") else "pl"
    ctx.source = "listing"
    job_dir = create_job_dir(ctx.job_id)
    ctx.job_dir = job_dir

    input_dir = get_input_dir(ctx.job_id)

    # Download photos
    photo_paths = await download_photos(listing, input_dir)
    if not photo_paths:
        raise HTTPException(status_code=502, detail="Nie udało się pobrać zdjęć z ogłoszenia.")

    ctx.raw_media_paths = photo_paths

    # Generate sales-oriented voiceover text via AI
    sales_copy = await generate_sales_copy(listing.to_dict(), lang=body.lang)
    ctx.transcript = sales_copy

    save_job(ctx)

    asyncio.create_task(run_pipeline_background(ctx, event_bus))

    return {
        "job_id": ctx.job_id,
        "status": ctx.status.value,
        "listing": listing.to_dict(),
        "sales_copy": sales_copy,
        "phone_number": listing.phone_number or "",
    }
