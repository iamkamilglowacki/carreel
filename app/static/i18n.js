/* CarReel - Internationalization (i18n) */

const translations = {
  pl: {
    "header.subtitle": "Generator Rolek Samochodowych",

    "tabs.fromUrl": "Z ogłoszenia",
    "tabs.fromMedia": "Własne media",

    "upload.title": "Nowa Rolka",
    "upload.carDescription": "Opis Samochodu",
    "upload.tabRecord": "Nagrywanie",
    "upload.tabType": "Wpisywanie",
    "upload.holdToRecord": "Przytrzymaj, aby nagrać",
    "upload.startRecord": "Nagrywaj",
    "upload.stopRecord": "Zakoncz nagrywanie",
    "upload.transcribing": "Transkrybuję...",
    "upload.transcribed": "Transkrypcja gotowa",
    "upload.transcribeError": "Błąd transkrypcji: ",
    "upload.cleanUp": "Popraw tekst AI",
    "upload.cleaningUp": "Poprawiam...",
    "upload.voiceHint": "lub nagraj opis przez mikrofon",
    "upload.typePlaceholder": "Opisz samochód... np. 2023 BMW M4 Competition, Alpine White, dach z włókna węglowego, wydech M Performance...",
    "upload.mediaLabel": "Pliki multimedialne (zdjęcia/wideo)",
    "upload.mediaSelected": "plik(ów) wybranych",
    "upload.mediaDrop": "Upuść pliki lub kliknij, aby przeglądać",
    "upload.generateReel": "Generuj Rolkę",
    "upload.uploading": "Przesyłanie...",
    "upload.errorRecord": "Najpierw nagraj notatkę głosową.",
    "upload.errorType": "Wpisz opis samochodu.",
    "upload.errorMedia": "Wybierz przynajmniej jeden plik multimedialny.",
    "upload.errorMic": "Brak dostępu do mikrofonu: ",
    "upload.errorNetwork": "Błąd sieci: ",
    "upload.errorUpload": "Przesyłanie nie powiodło się",
    "upload.errorInvalidFiles": "Pominięto pliki nieobsługiwanego typu. Dozwolone: zdjęcia i wideo.",
    "upload.errorTooManyFiles": "Maksymalnie 20 plików. Usuń część przed dodaniem nowych.",
    "upload.errorTotalSize": "Łączny rozmiar plików przekracza 500 MB.",

    "job.title": "Zadanie",
    "job.close": "Zamknij",
    "job.preview": "Podgląd",
    "job.downloadMp4": "Pobierz wideo",

    "job.sendWhatsApp": "Wyślij na WhatsApp",
    "job.confirmDelete": "Na pewno usunąć to zadanie?",

    "jobs.title": "Zadania",
    "jobs.empty": "Brak zadań. Prześlij pliki powyżej, aby rozpocząć.",
    "jobs.files": "plik(ów)",

    "steps.transcribe": "Transkrypcja",
    "steps.scriptwrite": "Skrypt",
    "steps.voiceover": "Lektor",
    "steps.media_process": "Media",
    "steps.caption_generate": "Napisy",
    "steps.video_assemble": "Montaż",

    "otomoto.title": "Importuj ogłoszenie",
    "otomoto.subtitle": "Wklej link z Otomoto — pobierzemy zdjęcia i dane automatycznie.",
    "otomoto.placeholder": "https://www.otomoto.pl/...",
    "otomoto.import": "Pobierz dane",
    "otomoto.loading": "Pobieram...",
    "otomoto.generate": "Generuj Rolkę z tego ogłoszenia",
    "otomoto.generating": "Tworzę...",
    "otomoto.photos": "zdjęć",
    "otomoto.errorUrl": "Wklej prawidłowy link z otomoto.pl",
    "otomoto.errorScrape": "Nie udało się pobrać danych z ogłoszenia.",
    "otomoto.errorGenerate": "Nie udało się utworzyć zadania.",
    "otomoto.salesCopyTitle": "Wygenerowany tekst sprzedażowy",
    "otomoto.allowedSources": "otomoto",
    "otomoto.searchOtomoto": "Szukaj na Otomoto",

    "nav.reels": "Rolki",
    "nav.comparator": "Porównywarka",

    "comparator.title": "Porównywarka Mobile.de → Otomoto",
    "comparator.subtitle": "Wklej link z Mobile.de — znajdziemy podobne ogłoszenia na Otomoto.",
    "comparator.placeholder": "https://www.mobile.de/...",
    "comparator.fetch": "Pobierz dane",
    "comparator.loading": "Pobieram...",
    "comparator.searchOtomoto": "Szukaj na Otomoto",
    "comparator.errorUrl": "Wklej prawidłowy link z mobile.de",
    "comparator.errorScrape": "Nie udało się pobrać danych z ogłoszenia.",

    "footer.text": "CarReel — Generator Rolek Samochodowych",
  },

  en: {
    "header.subtitle": "Car Reel Generator",

    "tabs.fromUrl": "From listing",
    "tabs.fromMedia": "Own media",

    "upload.title": "New Reel",
    "upload.carDescription": "Car Description",
    "upload.tabRecord": "Record",
    "upload.tabType": "Type",
    "upload.holdToRecord": "Hold to record",
    "upload.startRecord": "Record",
    "upload.stopRecord": "Stop recording",
    "upload.transcribing": "Transcribing...",
    "upload.transcribed": "Transcription ready",
    "upload.transcribeError": "Transcription error: ",
    "upload.cleanUp": "Clean up with AI",
    "upload.cleaningUp": "Cleaning up...",
    "upload.voiceHint": "or record a voice description",
    "upload.typePlaceholder": "Describe the car... e.g. 2023 BMW M4 Competition, Alpine White, carbon fiber roof, M Performance exhaust...",
    "upload.mediaLabel": "Media files (photos/videos)",
    "upload.mediaSelected": "file(s) selected",
    "upload.mediaDrop": "Drop files or click to browse",
    "upload.generateReel": "Generate Reel",
    "upload.uploading": "Uploading...",
    "upload.errorRecord": "Record a voice memo first.",
    "upload.errorType": "Enter a car description.",
    "upload.errorMedia": "Select at least one media file.",
    "upload.errorMic": "Microphone access denied: ",
    "upload.errorNetwork": "Network error: ",
    "upload.errorUpload": "Upload failed",
    "upload.errorInvalidFiles": "Unsupported file types were skipped. Allowed: images and videos.",
    "upload.errorTooManyFiles": "Maximum 20 files. Remove some before adding new ones.",
    "upload.errorTotalSize": "Total file size exceeds 500 MB.",

    "job.title": "Job",
    "job.close": "Close",
    "job.preview": "Preview",
    "job.downloadMp4": "Download MP4",

    "job.sendWhatsApp": "Send via WhatsApp",
    "job.confirmDelete": "Are you sure you want to delete this job?",

    "jobs.title": "Jobs",
    "jobs.empty": "No jobs yet. Upload files above to get started.",
    "jobs.files": "file(s)",

    "steps.transcribe": "Transcribe",
    "steps.scriptwrite": "Script",
    "steps.voiceover": "Voiceover",
    "steps.media_process": "Media",
    "steps.caption_generate": "Captions",
    "steps.video_assemble": "Assemble",

    "otomoto.title": "Import listing",
    "otomoto.subtitle": "Paste an Otomoto listing URL — we'll fetch photos and data automatically.",
    "otomoto.placeholder": "https://www.otomoto.pl/...",
    "otomoto.import": "Fetch data",
    "otomoto.loading": "Fetching...",
    "otomoto.generate": "Generate Reel from this listing",
    "otomoto.generating": "Creating...",
    "otomoto.photos": "photos",
    "otomoto.errorUrl": "Paste a valid otomoto.pl listing URL",
    "otomoto.errorScrape": "Failed to fetch listing data.",
    "otomoto.errorGenerate": "Failed to create job.",
    "otomoto.salesCopyTitle": "Generated sales copy",
    "otomoto.allowedSources": "otomoto",
    "otomoto.searchOtomoto": "Search on Otomoto",

    "nav.reels": "Reels",
    "nav.comparator": "Comparator",

    "comparator.title": "Comparator Mobile.de → Otomoto",
    "comparator.subtitle": "Paste a Mobile.de link — we'll find similar listings on Otomoto.",
    "comparator.placeholder": "https://www.mobile.de/...",
    "comparator.fetch": "Fetch data",
    "comparator.loading": "Fetching...",
    "comparator.searchOtomoto": "Search on Otomoto",
    "comparator.errorUrl": "Paste a valid mobile.de link",
    "comparator.errorScrape": "Failed to fetch listing data.",

    "footer.text": "CarReel — Car Reel Generator",
  },

  de: {
    "header.subtitle": "Auto-Reel-Generator",

    "tabs.fromUrl": "Aus Inserat",
    "tabs.fromMedia": "Eigene Medien",

    "upload.title": "Neues Reel",
    "upload.carDescription": "Fahrzeugbeschreibung",
    "upload.tabRecord": "Aufnahme",
    "upload.tabType": "Eingabe",
    "upload.holdToRecord": "Gedrückt halten zum Aufnehmen",
    "upload.startRecord": "Aufnehmen",
    "upload.stopRecord": "Aufnahme beenden",
    "upload.transcribing": "Transkribiere...",
    "upload.transcribed": "Transkription fertig",
    "upload.transcribeError": "Transkriptionsfehler: ",
    "upload.cleanUp": "Mit KI bereinigen",
    "upload.cleaningUp": "Bereinige...",
    "upload.voiceHint": "oder Beschreibung per Mikrofon aufnehmen",
    "upload.typePlaceholder": "Fahrzeug beschreiben... z.B. 2023 BMW M4 Competition, Alpinweiß, Carbon-Dach, M Performance Abgasanlage...",
    "upload.mediaLabel": "Mediendateien (Fotos/Videos)",
    "upload.mediaSelected": "Datei(en) ausgewählt",
    "upload.mediaDrop": "Dateien ablegen oder klicken zum Durchsuchen",
    "upload.generateReel": "Reel generieren",
    "upload.uploading": "Hochladen...",
    "upload.errorRecord": "Zuerst eine Sprachnotiz aufnehmen.",
    "upload.errorType": "Fahrzeugbeschreibung eingeben.",
    "upload.errorMedia": "Mindestens eine Mediendatei auswählen.",
    "upload.errorMic": "Kein Mikrofonzugriff: ",
    "upload.errorNetwork": "Netzwerkfehler: ",
    "upload.errorUpload": "Hochladen fehlgeschlagen",
    "upload.errorInvalidFiles": "Nicht unterstützte Dateitypen wurden übersprungen. Erlaubt: Bilder und Videos.",
    "upload.errorTooManyFiles": "Maximal 20 Dateien. Entfernen Sie einige, bevor Sie neue hinzufügen.",
    "upload.errorTotalSize": "Gesamtdateigröße überschreitet 500 MB.",

    "job.title": "Auftrag",
    "job.close": "Schließen",
    "job.preview": "Vorschau",
    "job.downloadMp4": "MP4 herunterladen",

    "job.sendWhatsApp": "Per WhatsApp senden",
    "job.confirmDelete": "Möchten Sie diesen Auftrag wirklich löschen?",

    "jobs.title": "Aufträge",
    "jobs.empty": "Noch keine Aufträge. Laden Sie oben Dateien hoch, um zu beginnen.",
    "jobs.files": "Datei(en)",

    "steps.transcribe": "Transkription",
    "steps.scriptwrite": "Skript",
    "steps.voiceover": "Sprecher",
    "steps.media_process": "Medien",
    "steps.caption_generate": "Untertitel",
    "steps.video_assemble": "Montage",

    "otomoto.title": "Inserat importieren",
    "otomoto.subtitle": "Mobile.de-Inseratslink einfügen — wir laden Fotos und Daten automatisch.",
    "otomoto.placeholder": "https://www.mobile.de/...",
    "otomoto.import": "Daten abrufen",
    "otomoto.loading": "Lade...",
    "otomoto.generate": "Reel aus diesem Inserat erstellen",
    "otomoto.generating": "Erstelle...",
    "otomoto.photos": "Fotos",
    "otomoto.errorUrl": "Gültigen mobile.de-Inseratslink einfügen",
    "otomoto.errorScrape": "Inseratsdaten konnten nicht abgerufen werden.",
    "otomoto.errorGenerate": "Auftrag konnte nicht erstellt werden.",
    "otomoto.salesCopyTitle": "Generierter Verkaufstext",
    "otomoto.allowedSources": "mobile",
    "otomoto.searchOtomoto": "Auf Otomoto suchen",

    "nav.reels": "Reels",
    "nav.comparator": "Vergleicher",

    "comparator.title": "Vergleicher Mobile.de → Otomoto",
    "comparator.subtitle": "Mobile.de-Link einfügen — wir finden ähnliche Inserate auf Otomoto.",
    "comparator.placeholder": "https://www.mobile.de/...",
    "comparator.fetch": "Daten abrufen",
    "comparator.loading": "Lade...",
    "comparator.searchOtomoto": "Auf Otomoto suchen",
    "comparator.errorUrl": "Gültigen mobile.de-Link einfügen",
    "comparator.errorScrape": "Inseratsdaten konnten nicht abgerufen werden.",

    "footer.text": "CarReel — Auto-Reel-Generator",
  },
};

// Current language (persisted in localStorage)
let currentLang = localStorage.getItem("lang") || "pl";

function setLang(lang) {
  if (translations[lang]) {
    currentLang = lang;
    localStorage.setItem("lang", lang);
  }
}

function getLang() {
  return currentLang;
}

function t(key) {
  const dict = translations[currentLang] || translations.pl;
  return dict[key] || key;
}
