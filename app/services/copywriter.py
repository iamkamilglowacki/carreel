"""AI copywriter — turns raw Otomoto listing data into a punchy reel script."""

import logging
import re

import httpx

from app.config import settings

logger = logging.getLogger(__name__)

_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

_SYSTEM_PROMPTS = {
    "pl": """\
Jesteś profesjonalnym copywriterem specjalizującym się w reklamach samochodowych \
na Instagram Reels / TikTok. Dostajesz surowe dane z ogłoszenia samochodu \
i przerabiasz je na krótki, chwytliwy, sprzedażowy tekst lektorski pod 30-sekundowego reela.

Zasady:
- Pisz po polsku, dynamicznie, z emocją — jak dobry sprzedawca.
- Używaj krótkich, punchowych zdań (max 10-15 słów na zdanie).
- Podkreśl najważniejsze atuty: mocne strony, stan, wyposażenie, cenę.
- Każde zdanie to osobna "scena" w reelu — pasująca do kolejnego zdjęcia.
- Napisz 5-8 zdań (łącznie ~25-35 sekund lektora).
- Zakończ wezwaniem do działania (CTA).
- NIE używaj hashtagów, emoji ani formatowania markdown.
- NIE wymieniaj suchej listy parametrów — wpleć je naturalnie w narrację.
- Każde zdanie zakończ kropką.
""",
    "en": """\
You are a professional copywriter specialising in car advertisements \
for Instagram Reels / TikTok. You receive raw car listing data \
and turn it into a short, catchy, sales-oriented voiceover script for a 30-second reel.

Rules:
- Write in English, dynamically, with emotion — like a great salesperson.
- Use short, punchy sentences (max 10-15 words per sentence).
- Highlight the key strengths: condition, equipment, price.
- Each sentence is a separate "scene" in the reel — matching the next photo.
- Write 5-8 sentences (totalling ~25-35 seconds of voiceover).
- End with a call to action (CTA).
- Do NOT use hashtags, emojis, or markdown formatting.
- Do NOT list dry parameters — weave them naturally into the narrative.
- End every sentence with a full stop.
""",
    "de": """\
Du bist ein professioneller Werbetexter, spezialisiert auf Automobilwerbung \
für Instagram Reels / TikTok. Du bekommst rohe Fahrzeug-Inseratsdaten \
und verwandelst sie in einen kurzen, eingängigen, verkaufsorientierten Sprechertext für ein 30-Sekunden-Reel.

Regeln:
- Schreibe auf Deutsch, dynamisch, mit Emotion — wie ein großartiger Verkäufer.
- Verwende kurze, knackige Sätze (max. 10-15 Wörter pro Satz).
- Hebe die wichtigsten Stärken hervor: Zustand, Ausstattung, Preis.
- Jeder Satz ist eine eigene "Szene" im Reel — passend zum nächsten Foto.
- Schreibe 5-8 Sätze (insgesamt ca. 25-35 Sekunden Sprecher).
- Ende mit einem Handlungsaufruf (CTA).
- Verwende KEINE Hashtags, Emojis oder Markdown-Formatierung.
- Liste KEINE trockenen Parameter auf — verwebe sie natürlich in die Erzählung.
- Beende jeden Satz mit einem Punkt.
""",
}


async def generate_sales_copy(listing_data: dict, lang: str = "pl") -> str:
    """Generate a sales-oriented voiceover script from listing data."""
    if not settings.gemini_api_key:
        logger.warning("No Gemini API key — falling back to raw listing data")
        return _fallback_copy(listing_data, lang)

    system_prompt = _SYSTEM_PROMPTS.get(lang, _SYSTEM_PROMPTS["pl"])
    user_prompt = _build_user_prompt(listing_data)

    payload = {
        "system_instruction": {"parts": [{"text": system_prompt}]},
        "contents": [{"parts": [{"text": user_prompt}]}],
        "generationConfig": {
            "temperature": 0.8,
            "maxOutputTokens": 1024,
            "thinkingConfig": {"thinkingBudget": 0},
        },
    }

    try:
        async with httpx.AsyncClient(timeout=30) as client:
            resp = await client.post(
                _GEMINI_URL,
                params={"key": settings.gemini_api_key},
                json=payload,
            )
            resp.raise_for_status()
            data = resp.json()

        text = data["candidates"][0]["content"]["parts"][0]["text"].strip()
        logger.info("Generated sales copy (%d chars)", len(text))
        return text
    except Exception as exc:
        logger.exception("Gemini API error, falling back to raw copy")
        return _fallback_copy(listing_data, lang)


def _build_user_prompt(d: dict) -> str:
    lines = [f"Tytuł ogłoszenia: {d.get('title', '')}"]
    if d.get("price"):
        lines.append(f"Cena: {d['price']} {d.get('currency', 'PLN')}")
    for key, label in [
        ("year", "Rok"),
        ("mileage", "Przebieg"),
        ("fuel_type", "Paliwo"),
        ("engine_power", "Moc"),
        ("engine_capacity", "Pojemność silnika"),
        ("gearbox", "Skrzynia biegów"),
        ("body_type", "Nadwozie"),
        ("color", "Kolor"),
        ("make", "Marka"),
        ("model", "Model"),
        ("location", "Lokalizacja"),
    ]:
        val = d.get(key, "")
        if val:
            lines.append(f"{label}: {val}")
    equip = d.get("equipment", [])
    if equip:
        lines.append(f"Wyposażenie: {', '.join(equip[:25])}")
    desc = d.get("description", "")
    if desc:
        clean = re.sub(r"<[^>]+>", " ", desc)
        clean = re.sub(r"\s+", " ", clean).strip()
        if clean:
            lines.append(f"Opis sprzedawcy: {clean[:500]}")
    lines.append(f"Liczba zdjęć: {len(d.get('photo_urls', []))}")
    return "\n".join(lines)


def _fallback_copy(d: dict, lang: str = "pl") -> str:
    """Simple fallback when AI is unavailable."""
    parts = []
    title = d.get("title", "")
    if title:
        parts.append(f"{title}.")

    year = d.get("year", "")
    mileage = d.get("mileage", "")
    power = d.get("engine_power", "")
    fuel = d.get("fuel_type", "")
    gearbox = d.get("gearbox", "")
    price = d.get("price", "")

    if lang == "de":
        if year and mileage:
            parts.append(f"Baujahr {year}, Kilometerstand {mileage}.")
        if power and fuel:
            parts.append(f"{power}, {fuel}-Motor.")
        if gearbox:
            parts.append(f"{gearbox}-Getriebe.")
        if price:
            parts.append(f"Preis {int(price):,} EUR.".replace(",", "."))
        parts.append("Schreiben oder anrufen für Details.")
    elif lang == "en":
        if year and mileage:
            parts.append(f"Year {year}, mileage {mileage}.")
        if power and fuel:
            parts.append(f"{power}, {fuel.lower()} engine.")
        if gearbox:
            parts.append(f"{gearbox} transmission.")
        if price:
            parts.append(f"Price {int(price):,} PLN.".replace(",", " "))
        parts.append("Message or call for details.")
    else:
        if year and mileage:
            parts.append(f"Rocznik {year}, przebieg {mileage}.")
        if power and fuel:
            parts.append(f"{power}, silnik {fuel.lower()}.")
        if gearbox:
            parts.append(f"Skrzynia {gearbox.lower()}.")
        if price:
            parts.append(f"Cena {int(price):,} PLN.".replace(",", " "))
        parts.append("Napisz lub zadzwoń po szczegóły.")

    return " ".join(parts)
