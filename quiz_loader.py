"""
quiz_loader.py
--------------
Lädt und validiert die Kategorie-JSON-Dateien aus dem Quiz/-Ordner.

Jede .json-Datei im Quiz-Ordner (außer solche, die mit '_' beginnen, siehe
config.IGNORED_QUIZ_FILE_PREFIXES) entspricht GENAU EINER Kategorie.
"""

from __future__ import annotations

import json
import os
from typing import Dict, List

from config import IGNORED_QUIZ_FILE_PREFIXES, QUESTION_TYPES, QUIZ_FOLDER, DIFFICULTIES
from models import Question


class QuizValidationError(Exception):
    """Wird ausgelöst, wenn eine Kategorie-JSON-Datei fehlerhaft aufgebaut ist."""


class QuizCategory:
    """Eine geladene Kategorie: Name + Beschreibung + Liste von Question-Objekten."""

    def __init__(self, dateiname: str, kategorie: str, beschreibung: str, fragen: List[Question]):
        self.dateiname = dateiname
        self.kategorie = kategorie
        self.beschreibung = beschreibung
        self.fragen = fragen

    def fragen_zahl_pro_schwierigkeit(self) -> Dict[str, int]:
        ergebnis = {d: 0 for d in DIFFICULTIES}
        for f in self.fragen:
            if f.schwierigkeit in ergebnis:
                ergebnis[f.schwierigkeit] += 1
        return ergebnis

    def to_dict_fuer_auswahl(self) -> dict:
        """Kompakte Darstellung für die Kategorie-Auswahl im Gamemaster-UI."""
        return {
            "dateiname": self.dateiname,
            "kategorie": self.kategorie,
            "beschreibung": self.beschreibung,
            "fragen_pro_schwierigkeit": self.fragen_zahl_pro_schwierigkeit(),
        }


class QuizLoader:
    """Scannt den Quiz-Ordner und stellt validierte QuizCategory-Objekte bereit."""

    def __init__(self, quiz_folder: str = QUIZ_FOLDER):
        self.quiz_folder = quiz_folder
        self._cache: Dict[str, QuizCategory] = {}

    # ------------------------------------------------------------------ laden

    def _ist_relevante_datei(self, dateiname: str) -> bool:
        if not dateiname.lower().endswith(".json"):
            return False
        return not dateiname.startswith(IGNORED_QUIZ_FILE_PREFIXES)

    def alle_neu_laden(self) -> None:
        """Liest den Quiz-Ordner komplett neu ein (z.B. wenn neue Dateien hinzugefügt wurden)."""
        self._cache.clear()
        if not os.path.isdir(self.quiz_folder):
            os.makedirs(self.quiz_folder, exist_ok=True)
            return

        for dateiname in sorted(os.listdir(self.quiz_folder)):
            if not self._ist_relevante_datei(dateiname):
                continue
            pfad = os.path.join(self.quiz_folder, dateiname)
            try:
                kategorie = self._datei_laden(pfad, dateiname)
                self._cache[dateiname] = kategorie
            except QuizValidationError as exc:
                # Eine fehlerhafte Datei darf nicht den ganzen Server crashen -
                # sie wird einfach übersprungen und das Problem wird ausgegeben.
                print(f"[QuizLoader] WARNUNG: '{dateiname}' wird ignoriert: {exc}")

    def _datei_laden(self, pfad: str, dateiname: str) -> QuizCategory:
        with open(pfad, "r", encoding="utf-8") as f:
            try:
                rohdaten = json.load(f)
            except json.JSONDecodeError as exc:
                raise QuizValidationError(f"Ungültiges JSON ({exc})") from exc

        kategorie_name = rohdaten.get("kategorie")
        if not kategorie_name or not isinstance(kategorie_name, str):
            raise QuizValidationError("Feld 'kategorie' fehlt oder ist kein String.")

        beschreibung = rohdaten.get("beschreibung", "")
        rohe_fragen = rohdaten.get("fragen")
        if not isinstance(rohe_fragen, list) or len(rohe_fragen) == 0:
            raise QuizValidationError("Feld 'fragen' fehlt oder ist leer.")

        fragen: List[Question] = []
        gesehene_ids = set()
        for i, roh in enumerate(rohe_fragen):
            frage = self._frage_validieren(roh, i, dateiname)
            if frage.id in gesehene_ids:
                raise QuizValidationError(f"Doppelte Frage-ID '{frage.id}'.")
            gesehene_ids.add(frage.id)
            fragen.append(frage)

        return QuizCategory(dateiname, kategorie_name, beschreibung, fragen)

    def _frage_validieren(self, roh: dict, index: int, dateiname: str) -> Question:
        ort = f"Frage #{index + 1} in '{dateiname}'"
        if not isinstance(roh, dict):
            raise QuizValidationError(f"{ort}: ist kein Objekt.")

        frage_id = roh.get("id") or f"auto_{index}"
        typ = roh.get("typ")
        schwierigkeit = roh.get("schwierigkeit")
        text = roh.get("frage")
        erklaerung = roh.get("erklaerung")

        if typ not in QUESTION_TYPES:
            raise QuizValidationError(f"{ort}: 'typ' muss eines von {QUESTION_TYPES} sein, war '{typ}'.")
        if schwierigkeit not in DIFFICULTIES:
            raise QuizValidationError(f"{ort}: 'schwierigkeit' muss eines von {DIFFICULTIES} sein, war '{schwierigkeit}'.")
        if not text or not isinstance(text, str):
            raise QuizValidationError(f"{ort}: Feld 'frage' fehlt oder ist kein String.")

        if typ == "boolean":
            antwort_richtig = roh.get("antwort_richtig")
            if not isinstance(antwort_richtig, bool):
                raise QuizValidationError(f"{ort}: 'antwort_richtig' muss true/false sein.")
            return Question(
                id=frage_id, typ=typ, schwierigkeit=schwierigkeit, frage=text,
                erklaerung=erklaerung, antwort_richtig=antwort_richtig,
            )

        # multiple_choice
        optionen = roh.get("optionen")
        index_richtig = roh.get("antwort_richtig_index")
        if not isinstance(optionen, list) or len(optionen) != 4:
            raise QuizValidationError(f"{ort}: 'optionen' muss eine Liste mit genau 4 Einträgen sein.")
        if not all(isinstance(o, str) and o for o in optionen):
            raise QuizValidationError(f"{ort}: alle 'optionen' müssen nicht-leere Strings sein.")
        if not isinstance(index_richtig, int) or not (0 <= index_richtig <= 3):
            raise QuizValidationError(f"{ort}: 'antwort_richtig_index' muss eine Zahl zwischen 0 und 3 sein.")

        return Question(
            id=frage_id, typ=typ, schwierigkeit=schwierigkeit, frage=text,
            erklaerung=erklaerung, optionen=optionen, antwort_richtig_index=index_richtig,
        )

    # ------------------------------------------------------------------ Zugriff

    def kategorien_liste(self) -> List[dict]:
        """Liefert alle Kategorien (kompakt) für die Auswahl im Gamemaster-UI."""
        return [k.to_dict_fuer_auswahl() for k in self._cache.values()]

    def kategorie_holen(self, dateiname: str) -> QuizCategory:
        if dateiname not in self._cache:
            raise QuizValidationError(f"Kategorie '{dateiname}' nicht gefunden.")
        return self._cache[dateiname]
