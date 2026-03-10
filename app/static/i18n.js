/* CarReel - Internationalization (i18n) */

const translations = {
  pl: {
    "header.subtitle": "Generator Rolek Samochodowych",

    "upload.title": "Nowa Rolka",
    "upload.carDescription": "Opis Samochodu",
    "upload.tabRecord": "Nagrywanie",
    "upload.tabType": "Wpisywanie",
    "upload.holdToRecord": "Przytrzymaj, aby nagrać",
    "upload.recording": "Nagrywanie...",
    "upload.recorded": "KB nagrane",
    "upload.recordHint": "Naciśnij i przytrzymaj, aby nagrać przez mikrofon",
    "upload.voiceHint": "lub przytrzymaj, aby nagrać opis przez mikrofon",
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

    "job.title": "Zadanie",
    "job.close": "Zamknij",
    "job.preview": "Podgląd",
    "job.downloadMp4": "Pobierz MP4",

    "jobs.title": "Zadania",
    "jobs.empty": "Brak zadań. Prześlij pliki powyżej, aby rozpocząć.",
    "jobs.files": "plik(ów)",

    "steps.transcribe": "Transkrypcja",
    "steps.scriptwrite": "Skrypt",
    "steps.voiceover": "Lektor",
    "steps.media_process": "Media",
    "steps.caption_generate": "Napisy",
    "steps.video_assemble": "Montaż",

    "footer.text": "CarReel — Generator Rolek Samochodowych",
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
