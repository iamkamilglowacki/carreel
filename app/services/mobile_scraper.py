"""Scrape car listing data from mobile.de via ScrapingBee."""

import json
import logging
import re
from dataclasses import dataclass, field
from html import unescape
from pathlib import Path

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_SCRAPINGBEE_URL = "https://app.scrapingbee.com/api/v1/"

_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    ),
    "Accept-Language": "de-DE,de;q=0.9",
}


@dataclass
class MobileListing:
    title: str = ""
    price: str = ""
    currency: str = "EUR"
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
            clean = re.sub(r"<[^>]+>", " ", self.description)
            clean = re.sub(r"\s+", " ", clean).strip()
            if clean:
                parts.append(clean)
        return ". ".join(parts)


def _clean_html(text: str) -> str:
    """Strip HTML tags and normalize whitespace."""
    text = unescape(text)
    text = re.sub(r"<[^>]+>", " ", text)
    text = text.replace("\xa0", " ")
    return re.sub(r"\s+", " ", text).strip()


def _parse_tech_items(html: str) -> dict[str, str]:
    """Parse technical data from data-testid item elements."""
    results = {}
    # Find the technical data section
    tech_section = re.search(
        r'data-testid="vip-technical-data-box"(.*?)(?=data-testid="vip-(?:features|vehicle-description|dealer)-box")',
        html,
        re.DOTALL,
    )
    if not tech_section:
        return results

    content = tech_section.group(1)
    # Extract label/value pairs from the flat dt/dd-like structure
    raw = _clean_html(content)
    # Split on known labels and extract values
    label_map = {
        "Fahrzeugzustand": "condition",
        "Kategorie": "body_type",
        "Kilometerstand": "mileage",
        "Hubraum": "engine_capacity",
        "Leistung": "engine_power",
        "Kraftstoffart": "fuel_type",
        "Getriebe": "gearbox",
        "Erstzulassung": "first_registration",
        "Farbe": "color",
        "Farbe (Hersteller)": "manufacturer_color",
        "Innenausstattung": "interior",
        "Baureihe": "series",
        "Ausstattungslinie": "trim",
    }
    for label, key in label_map.items():
        pattern = rf"{re.escape(label)}\s*\|\s*(.*?)(?:\s*\||$)"
        m = re.search(pattern, raw)
        if m:
            val = m.group(1).strip().strip("|").strip()
            if val and val != "|":
                results[key] = val

    return results


def _set_field(listing: MobileListing, key: str, val: str) -> None:
    """Set a listing field by key name, only if not already set."""
    if key == "trim":
        # Special: update title with trim info
        if listing.make and listing.model:
            listing.title = f"{listing.make} {listing.model} {val}"
        return
    if key == "series":
        return  # informational only
    current = getattr(listing, key, None)
    if not current:
        setattr(listing, key, val)


def _parse_listing(html: str) -> MobileListing:
    """Parse a mobile.de listing page HTML into a MobileListing."""
    listing = MobileListing()

    # --- Phone numbers (from JSON in HTML) ---
    phones_match = re.search(r'"phones":\s*\[(.*?)\]', html, re.DOTALL)
    if phones_match:
        try:
            phones = json.loads(f"[{phones_match.group(1)}]")
            if phones:
                listing.phone_number = phones[0].get("uri", "").removeprefix("tel:")
        except (json.JSONDecodeError, IndexError):
            pass

    # --- Price ---
    price_match = re.search(r'(\d{1,3}(?:\.\d{3})*)\s*(?:&nbsp;)?€', html)
    if price_match:
        listing.price = price_match.group(1).replace(".", "")

    # --- Make / Model from JSON-LD breadcrumbs ---
    ld_blocks = re.findall(
        r'<script type="application/ld\+json">(.*?)</script>', html, re.DOTALL
    )
    for block in ld_blocks:
        try:
            ld = json.loads(block)
            graph = ld.get("@graph", [])
            for item in graph:
                if item.get("@type") == "BreadcrumbList":
                    elements = item.get("itemListElement", [])
                    # Typical: [Home, Used Cars, Audi, A5]
                    if len(elements) >= 4:
                        listing.make = elements[2].get("item", {}).get("name", "")
                        listing.model = elements[3].get("item", {}).get("name", "")
        except (json.JSONDecodeError, KeyError):
            pass

    # --- Title ---
    title_match = re.search(r'"adTitle":"(.*?)"', html)
    if title_match:
        listing.title = unescape(title_match.group(1))
    elif listing.make and listing.model:
        listing.title = f"{listing.make} {listing.model}"

    # --- Key features & technical data (combined approach) ---
    # Parse label/value pairs from the full tech area using a flexible regex
    _tech_labels = {
        "Kilometerstand": "mileage",
        "Leistung": "engine_power",
        "Hubraum": "engine_capacity",
        "Kraftstoffart": "fuel_type",
        "Getriebe": "gearbox",
        "Erstzulassung": "year",
        "Kategorie": "body_type",
        "Farbe (Hersteller)": "color",
        "Farbe": "color",
        "Ausstattungslinie": "trim",
        "Baureihe": "series",
    }
    # Strategy: find each label in HTML, then grab the next text node after it
    for label, field_key in _tech_labels.items():
        # Match: label text in a span, then some tags, then value text
        pattern = rf">{re.escape(label)}</span>.*?<(?:div|span)[^>]*class=\"[^\"]*(?:geJSa|value)[^\"]*\"[^>]*>(.*?)</(?:div|span)>"
        m = re.search(pattern, html, re.DOTALL)
        if not m:
            # Fallback: label | value pattern in cleaned text
            pattern2 = rf"{re.escape(label)}\s*\|[\s|]*(.*?)(?:\s*\|\s*\||$)"
            # Search in tech section
            tech_area = re.search(
                r'data-testid="vip-key-features-box"(.*?)data-testid="vip-(?:dealer|more)-',
                html, re.DOTALL,
            )
            if tech_area:
                cleaned = _clean_html(tech_area.group(1))
                m2 = re.search(pattern2, cleaned)
                if m2:
                    val = m2.group(1).strip().strip("|").strip()
                    if val:
                        _set_field(listing, field_key, val)
            continue
        val = _clean_html(m.group(1))
        if val:
            _set_field(listing, field_key, val)

    # Fallback: also try _parse_tech_items for any remaining empty fields
    tech = _parse_tech_items(html)
    for key, val in tech.items():
        _set_field(listing, key, val)

    # --- Description ---
    desc_match = re.search(
        r'data-testid="vip-vehicle-description-text"[^>]*>(.*?)</div>', html, re.DOTALL
    )
    if desc_match:
        listing.description = _clean_html(desc_match.group(1))

    # --- Seller / Location ---
    dealer_name = re.search(
        r'data-testid="vip-dealer-box-headline"[^>]*>(.*?)<', html, re.DOTALL
    )
    if dealer_name:
        listing.seller_name = _clean_html(dealer_name.group(1))

    addr1 = re.search(
        r'data-testid="vip-dealer-box-seller-address1"[^>]*>(.*?)<', html, re.DOTALL
    )
    addr2 = re.search(
        r'data-testid="vip-dealer-box-seller-address2"[^>]*>(.*?)<', html, re.DOTALL
    )
    parts = []
    if addr1:
        parts.append(_clean_html(addr1.group(1)))
    if addr2:
        parts.append(_clean_html(addr2.group(1)))
    listing.location = ", ".join(parts)

    # --- Photos ---
    photo_ids = re.findall(
        r"(https://img\.classistatic\.de/api/v1/mo-prod/images/[a-f0-9]{2}/[a-f0-9-]+)",
        html,
    )
    seen = set()
    for pid in photo_ids:
        if pid not in seen:
            seen.add(pid)
            listing.photo_urls.append(f"{pid}?rule=mo-1024")

    # --- Equipment / Features ---
    features_section = re.search(
        r'data-testid="vip-features-content"(.*?)(?=data-testid="vip-(?!features))',
        html,
        re.DOTALL,
    )
    if features_section:
        items = re.findall(r"<li[^>]*>(.*?)</li>", features_section.group(1), re.DOTALL)
        for item in items:
            label = _clean_html(item)
            if label and len(label) < 80:
                listing.equipment.append(label)

    logger.info(
        "Parsed mobile.de listing: %s (%d photos, phone=%s)",
        listing.title,
        len(listing.photo_urls),
        bool(listing.phone_number),
    )
    return listing


def _normalize_mobile_url(url: str) -> str:
    """Convert any mobile.de link variant to the canonical German desktop URL."""
    match = re.search(r"[?&]id=(\d+)", url)
    if match:
        return f"https://suchen.mobile.de/fahrzeuge/details.html?id={match.group(1)}"
    return url


async def scrape_mobile(url: str) -> MobileListing:
    """Fetch and parse a mobile.de listing page via ScrapingBee."""
    if "mobile.de" not in url:
        raise ValueError("URL must be from mobile.de")

    url = _normalize_mobile_url(url)

    if not settings.scrapingbee_api_key:
        raise ValueError("ScrapingBee API key is required for mobile.de scraping")

    async with httpx.AsyncClient(timeout=90) as client:
        resp = await client.get(
            _SCRAPINGBEE_URL,
            params={
                "api_key": settings.scrapingbee_api_key,
                "url": url,
                "render_js": "true",
                "premium_proxy": "true",
                "country_code": "de",
                "wait": "5000",
            },
        )
        resp.raise_for_status()

    html = resp.text
    if len(html) < 5000 or "Zugriff verweigert" in html:
        raise ValueError("mobile.de blocked the request — please try again")

    return _parse_listing(html)


async def download_photos(listing: MobileListing, dest_dir: Path) -> list[Path]:
    """Download listing photos to dest_dir. Converts AVIF to JPEG for FFmpeg compatibility."""
    from io import BytesIO
    from PIL import Image

    dest_dir.mkdir(parents=True, exist_ok=True)
    paths: list[Path] = []

    async with httpx.AsyncClient(headers=_HEADERS, follow_redirects=True, timeout=30) as client:
        for i, url in enumerate(listing.photo_urls[:20]):
            try:
                resp = await client.get(url)
                resp.raise_for_status()
                content_type = resp.headers.get("content-type", "")
                file_path = dest_dir / f"mobile_{i:02d}.jpg"

                if "avif" in content_type:
                    # Convert AVIF to JPEG — FFmpeg can't use -loop with AVIF
                    img = Image.open(BytesIO(resp.content))
                    img.convert("RGB").save(file_path, "JPEG", quality=90)
                else:
                    file_path.write_bytes(resp.content)

                paths.append(file_path)
            except Exception as exc:
                logger.warning("Failed to download photo %d: %s", i, exc)

    logger.info("Downloaded %d/%d photos to %s", len(paths), len(listing.photo_urls), dest_dir)
    return paths
