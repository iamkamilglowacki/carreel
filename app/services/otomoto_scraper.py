"""Scrape car listing data from Otomoto URL using __NEXT_DATA__."""

import json
import logging
import re
from dataclasses import dataclass, field
from pathlib import Path

import httpx

logger = logging.getLogger(__name__)

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept": "text/html,application/xhtml+xml",
    "Accept-Language": "pl-PL,pl;q=0.9",
}

_NEXT_DATA_RE = re.compile(
    r'<script id="__NEXT_DATA__"[^>]*>(.*?)</script>', re.DOTALL
)


@dataclass
class OtomotoListing:
    title: str = ""
    price: str = ""
    currency: str = "PLN"
    year: str = ""
    mileage: str = ""
    fuel_type: str = ""
    engine_power: str = ""
    engine_capacity: str = ""
    gearbox: str = ""
    body_type: str = ""
    color: str = ""
    make: str = ""
    model: str = ""
    description: str = ""
    location: str = ""
    seller_name: str = ""
    phone_number: str = ""
    photo_urls: list[str] = field(default_factory=list)
    equipment: list[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return {
            "title": self.title,
            "price": self.price,
            "currency": self.currency,
            "year": self.year,
            "mileage": self.mileage,
            "fuel_type": self.fuel_type,
            "engine_power": self.engine_power,
            "engine_capacity": self.engine_capacity,
            "gearbox": self.gearbox,
            "body_type": self.body_type,
            "color": self.color,
            "make": self.make,
            "model": self.model,
            "description": self.description,
            "location": self.location,
            "seller_name": self.seller_name,
            "phone_number": self.phone_number,
            "photo_urls": self.photo_urls,
            "equipment": self.equipment,
        }

    def to_transcript(self) -> str:
        """Build a natural-language car description for the pipeline."""
        parts = []
        if self.title:
            parts.append(self.title)
        specs = []
        if self.year:
            specs.append(f"Rok: {self.year}")
        if self.mileage:
            specs.append(f"Przebieg: {self.mileage}")
        if self.fuel_type:
            specs.append(f"Paliwo: {self.fuel_type}")
        if self.engine_power:
            specs.append(f"Moc: {self.engine_power}")
        if self.engine_capacity:
            specs.append(f"Pojemność: {self.engine_capacity}")
        if self.gearbox:
            specs.append(f"Skrzynia: {self.gearbox}")
        if self.body_type:
            specs.append(f"Nadwozie: {self.body_type}")
        if self.color:
            specs.append(f"Kolor: {self.color}")
        if self.price:
            specs.append(f"Cena: {self.price} {self.currency}")
        if self.location:
            specs.append(f"Lokalizacja: {self.location}")
        if specs:
            parts.append(", ".join(specs))
        if self.equipment:
            parts.append("Wyposażenie: " + ", ".join(self.equipment[:20]))
        if self.description:
            # Strip HTML tags from description
            clean = re.sub(r"<[^>]+>", " ", self.description)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                parts.append(clean)
        return ". ".join(parts)


def _get_param(params: dict, key: str) -> str:
    entry = params.get(key, {})
    values = entry.get("values", [])
    if values:
        return values[0].get("label", "")
    return ""


async def _scrape_phone_number(url: str) -> str:
    """Use Playwright to click 'Wyświetl numer' and extract the phone number."""
    try:
        from playwright.async_api import async_playwright
    except ImportError:
        logger.warning("Playwright not installed – skipping phone number extraction")
        return ""

    try:
        async with async_playwright() as pw:
            browser = await pw.chromium.launch(headless=True)
            ctx = await browser.new_context(
                user_agent=_HEADERS["User-Agent"],
                viewport={"width": 1280, "height": 900},
                locale="pl-PL",
            )
            page = await ctx.new_page()
            await page.goto(url, wait_until="networkidle", timeout=30_000)

            # Dismiss cookie banner if present
            try:
                await page.click("button#onetrust-accept-btn-handler", timeout=3000)
            except Exception:
                pass

            # Click 'Wyświetl numer'
            btn = page.locator('button:has-text("Wyświetl numer")').first
            await btn.click(timeout=5000)
            await page.wait_for_timeout(2000)

            # Read the revealed tel: link
            tel_link = page.locator('a[href^="tel:"]').first
            href = await tel_link.get_attribute("href", timeout=5000)
            await browser.close()

            if href and href.startswith("tel:"):
                phone = href.removeprefix("tel:")
                logger.info("Extracted phone number: %s", phone)
                return phone
    except Exception as exc:
        logger.warning("Failed to extract phone number: %s", exc)

    return ""


async def scrape_otomoto(url: str) -> OtomotoListing:
    """Fetch and parse an Otomoto listing page."""
    if "otomoto.pl" not in url:
        raise ValueError("URL must be from otomoto.pl")

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=15) as client:
        resp = await client.get(url)
        resp.raise_for_status()

    html = resp.text
    match = _NEXT_DATA_RE.search(html)
    if not match:
        raise ValueError("Could not find listing data on page (no __NEXT_DATA__)")

    data = json.loads(match.group(1))
    ad = data["props"]["pageProps"]["advert"]

    listing = OtomotoListing()
    listing.title = ad.get("title", "")

    price_data = ad.get("price", {})
    listing.price = price_data.get("value", "")
    listing.currency = price_data.get("currency", "PLN")

    # Main features (quick access)
    main = ad.get("mainFeatures", [])
    if len(main) >= 1:
        listing.year = main[0]
    if len(main) >= 2:
        listing.mileage = main[1]
    if len(main) >= 3:
        listing.engine_capacity = main[2]
    if len(main) >= 4:
        listing.fuel_type = main[3]

    # Detailed params
    params = ad.get("parametersDict", {})
    listing.engine_power = _get_param(params, "engine_power")
    listing.gearbox = _get_param(params, "gearbox")
    listing.body_type = _get_param(params, "body_type")
    listing.color = _get_param(params, "color")
    listing.make = _get_param(params, "make")
    listing.model = _get_param(params, "model")

    # Description
    listing.description = ad.get("description", "")

    # Seller
    seller = ad.get("seller", {})
    listing.seller_name = seller.get("name", "")
    location = seller.get("location", {})
    listing.location = location.get("address", "") or location.get("city", "")

    # Photos
    images = ad.get("images", {})
    photos = images.get("photos", [])
    for photo in photos:
        photo_url = photo.get("url", "")
        if photo_url:
            listing.photo_urls.append(photo_url)

    # Equipment (flat list of labels)
    for group in ad.get("equipment", []):
        for item in group.get("values", []):
            label = item.get("label", "")
            if label:
                listing.equipment.append(label)

    # Phone number (requires Playwright to decrypt) — only when WhatsApp feature is enabled
    from app.config import settings
    if settings.enable_whatsapp:
        listing.phone_number = await _scrape_phone_number(url)

    logger.info("Scraped Otomoto listing: %s (%d photos, phone=%s)", listing.title, len(listing.photo_urls), bool(listing.phone_number))
    return listing


async def download_photos(listing: OtomotoListing, dest_dir: Path) -> list[Path]:
    """Download listing photos to dest_dir. Returns list of saved file paths."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        for i, url in enumerate(listing.photo_urls[:20]):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                ext = ".jpg"
                content_type = resp.headers.get("content-type", "")
                if "png" in content_type:
                    ext = ".png"
                elif "webp" in content_type:
                    ext = ".webp"
                file_path = dest_dir / f"otomoto_{i:02d}{ext}"
                file_path.write_bytes(resp.content)
                paths.append(file_path)
            except Exception as exc:
                logger.warning("Failed to download photo %d: %s", i, exc)

    logger.info("Downloaded %d/%d photos to %s", len(paths), len(listing.photo_urls), dest_dir)
    return paths
