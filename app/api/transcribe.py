"""Standalone transcription endpoint with AI post-processing."""

import logging

import httpx
from fastapi import APIRouter, HTTPException, UploadFile, File

from app.config import settings

logger = logging.getLogger(__name__)

router = APIRouter()

_STT_URL = "https://api.elevenlabs.io/v1/speech-to-text"
_GEMINI_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent"

_CLEANUP_PROMPT = """\
Jesteś asystentem dealera samochodowego. Dostajesz surowy tekst — transkrypcję głosową \
lub skopiowany opis z ogłoszenia (np. z OtoMoto).

Twoim zadaniem jest przerobić ten tekst na płynny, naturalny opis samochodu gotowy \
do użycia jako voiceover w krótkim filmiku (Instagram Reel).

Zasady:
- Zamień słowa na cyfry tam gdzie to naturalne (np. "dwadzieścia trzy tysiące" → "23 000", \
  "dwa tysiące dwadzieścia trzy" → "2023", "sto pięćdziesiąt koni" → "150 koni")
- Usuń myślniki, punktory, gwiazdki i inną strukturę list — zamień na płynne zdania
- Usuń powtórzenia i słowa-wypełniacze ("no", "wie pan", "tak jakby", "eee")
- Zachowaj kluczowe informacje: marka, model, rok, przebieg, moc, wyposażenie, cena
- Pisz krótko i dynamicznie — tekst będzie czytany na głos w 30-60 sekundowym filmiku
- Nie dodawaj informacji których nie ma w oryginale
- Odpowiedz TYLKO poprawionym tekstem, bez komentarzy

Tekst do obróbki:
"""


async def _transcribe_audio(audio_bytes: bytes, filename: str) -> str:
    """Send audio to ElevenLabs Scribe v2 and return raw transcript."""
    api_key = settings.elevenlabs_api_key
    if not api_key:
        raise HTTPException(status_code=500, detail="ELEVENLABS_API_KEY not configured")

    files = {"file": (filename, audio_bytes)}
    data = {
        "model_id": "scribe_v2",
        "language_code": "pol",
        "timestamps_granularity": "word",
        "tag_audio_events": "false",
        "diarize": "false",
    }
    headers = {"xi-api-key": api_key}

    logger.info("Transcribing audio: %s (%.1f KB)", filename, len(audio_bytes) / 1024)

    async with httpx.AsyncClient(timeout=120.0) as client:
        resp = await client.post(_STT_URL, headers=headers, files=files, data=data)

    if resp.status_code != 200:
        logger.error("ElevenLabs STT error: %s", resp.text[:300])
        raise HTTPException(status_code=502, detail="Transcription failed")

    return resp.json().get("text", "").strip()


async def _cleanup_text(raw_text: str) -> str:
    """Post-process transcript through Gemini for cleanup."""
    api_key = settings.gemini_api_key
    if not api_key:
        logger.info("No GEMINI_API_KEY, skipping text cleanup")
        return raw_text

    url = f"{_GEMINI_URL}?key={api_key}"
    payload = {
        "contents": [
            {
                "parts": [
                    {"text": _CLEANUP_PROMPT + raw_text}
                ]
            }
        ],
    }

    logger.info("Cleaning up transcript with Gemini (%d chars)", len(raw_text))

    async with httpx.AsyncClient(timeout=30.0) as client:
        resp = await client.post(url, json=payload)

    if resp.status_code != 200:
        logger.warning("Gemini cleanup failed (%d): %s", resp.status_code, resp.text[:200])
        return raw_text

    result = resp.json()
    try:
        cleaned = result["candidates"][0]["content"]["parts"][0]["text"].strip()
    except (KeyError, IndexError):
        logger.warning("Unexpected Gemini response format, returning raw text")
        return raw_text

    return cleaned if cleaned else raw_text


@router.post("/transcribe")
async def transcribe_audio(file: UploadFile = File(...)):
    """Transcribe audio file and clean up the text with AI."""
    audio_bytes = await file.read()

    # Step 1: Transcribe
    raw_text = await _transcribe_audio(audio_bytes, file.filename or "recording.webm")

    if not raw_text:
        return {"text": "", "raw": ""}

    # Step 2: Clean up with Gemini (if API key available)
    cleaned_text = await _cleanup_text(raw_text)

    logger.info("Transcription done: %d chars raw → %d chars cleaned", len(raw_text), len(cleaned_text))

    return {"text": cleaned_text, "raw": raw_text}


@router.post("/cleanup")
async def cleanup_text(body: dict):
    """Clean up pasted or typed text with AI."""
    text = body.get("text", "").strip()
    if not text:
        return {"text": ""}

    cleaned = await _cleanup_text(text)
    return {"text": cleaned}
