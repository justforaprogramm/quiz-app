"""
models.py
---------
Die zentralen Datenklassen der App:

- Question      : eine einzelne Frage aus einer Kategorie-JSON-Datei
- Player        : ein angemeldeter Mitspieler (nicht der Gamemaster)
- GameSession   : eine laufende Quiz-Runde mit eigenem Beitritts-Code

Diese Klassen enthalten bewusst auch etwas Logik (z.B. Antwortprüfung,
Punkteberechnung, Status-Übergänge), damit die Spielregeln an EINER Stelle
stehen und nicht über app.py verstreut sind.
"""

from __future__ import annotations

import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Dict, List, Optional

from config import POINTS_PER_CORRECT_ANSWER, TIME_LIMITS


class GameState(str, Enum):
    """Mögliche Zustände einer GameSession (siehe Ablaufdiagramm in der README)."""

    LOBBY = "lobby"               # Spieler können beitreten, GM wählt Kategorie/Schwierigkeit
    QUESTION = "question"         # Eine Frage ist aktiv, Spieler können antworten
    RESULT = "result"             # Ergebnis der letzten Frage wird angezeigt
    FINISHED = "finished"         # Quiz beendet, Endstand wird angezeigt


@dataclass
class Question:
    """Repräsentiert eine einzelne Frage, geladen aus einer Kategorie-JSON-Datei."""

    id: str
    typ: str                      # "boolean" oder "multiple_choice"
    schwierigkeit: str             # "leicht" | "mittel" | "schwer"
    frage: str
    erklaerung: Optional[str] = None

    # nur für typ == "boolean"
    antwort_richtig: Optional[bool] = None

    # nur für typ == "multiple_choice"
    optionen: Optional[List[str]] = None
    antwort_richtig_index: Optional[int] = None

    def ist_richtig(self, antwort) -> bool:
        """Prüft eine eingereichte Antwort gegen die richtige Lösung."""
        if self.typ == "boolean":
            return bool(antwort) == bool(self.antwort_richtig)
        if self.typ == "multiple_choice":
            try:
                return int(antwort) == int(self.antwort_richtig_index)
            except (TypeError, ValueError):
                return False
        return False

    def richtige_antwort_anzeigen(self):
        """Liefert die richtige Antwort in einer Form, die das Frontend anzeigen kann."""
        if self.typ == "boolean":
            return self.antwort_richtig
        return self.antwort_richtig_index

    def fuer_spieler(self) -> dict:
        """Version der Frage OHNE Lösung - das ist es, was Spieler-Clients zu sehen bekommen."""
        data = {
            "id": self.id,
            "typ": self.typ,
            "schwierigkeit": self.schwierigkeit,
            "frage": self.frage,
            "zeitlimit": TIME_LIMITS.get(self.schwierigkeit),
        }
        if self.typ == "multiple_choice":
            data["optionen"] = self.optionen
        return data

    def fuer_gamemaster(self) -> dict:
        """Version der Frage MIT Lösung - nur für den Gamemaster-Client."""
        data = self.fuer_spieler()
        data["richtige_antwort"] = self.richtige_antwort_anzeigen()
        data["erklaerung"] = self.erklaerung
        return data


@dataclass
class Player:
    """Ein Mitspieler innerhalb einer GameSession (nicht der Gamemaster)."""

    sid: str                       # Socket.IO Session-ID der aktuellen Verbindung
    name: str
    score: int = 0
    hat_aktuelle_frage_beantwortet: bool = False
    letzte_antwort_richtig: Optional[bool] = None

    def neue_frage_zuruecksetzen(self):
        self.hat_aktuelle_frage_beantwortet = False
        self.letzte_antwort_richtig = None

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "score": self.score,
            "hat_geantwortet": self.hat_aktuelle_frage_beantwortet,
        }


@dataclass
class GameSession:
    """
    Eine laufende Quiz-Runde.

    Genau EIN Gamemaster erstellt die Session und steuert sie (Kategorie wählen,
    Schwierigkeit wählen, Frage starten/beenden, nächste Frage, Quiz beenden).
    Beliebig viele Spieler treten über den 'code' bei.
    """

    code: str
    gamemaster_sid: str

    state: GameState = GameState.LOBBY
    players: Dict[str, Player] = field(default_factory=dict)  # sid -> Player

    kategorie_name: Optional[str] = None
    schwierigkeit: Optional[str] = None

    frage_pool: List[Question] = field(default_factory=list)   # gefiltert nach Schwierigkeit, gemischt
    gestellte_fragen_ids: set = field(default_factory=set)

    aktuelle_frage: Optional[Question] = None
    aktuelle_frage_index: int = 0          # wie viele Fragen wurden in dieser Runde schon gestellt
    frage_start_zeit: Optional[float] = None
    antworten_aktuelle_frage: Dict[str, dict] = field(default_factory=dict)  # sid -> {"antwort":..., "richtig":...}

    # threading.Timer-Objekt für automatisches Beenden bei mittel/schwer (None = kein aktiver Timer)
    timer_handle: Optional[object] = field(default=None, repr=False, compare=False)

    # --------------------------------------------------------------- Setup

    def quiz_konfigurieren(self, kategorie_name: str, schwierigkeit: str, alle_fragen: List[Question]):
        """Wird vom Gamemaster vor Spielstart aufgerufen: Kategorie + Schwierigkeit festlegen."""
        self.kategorie_name = kategorie_name
        self.schwierigkeit = schwierigkeit
        gefiltert = [f for f in alle_fragen if f.schwierigkeit == schwierigkeit]
        random.shuffle(gefiltert)
        self.frage_pool = gefiltert
        self.gestellte_fragen_ids.clear()
        self.aktuelle_frage_index = 0

    # --------------------------------------------------------------- Spieler

    def spieler_hinzufuegen(self, sid: str, name: str) -> Player:
        spieler = Player(sid=sid, name=name)
        self.players[sid] = spieler
        return spieler

    def spieler_entfernen(self, sid: str):
        self.players.pop(sid, None)
        self.antworten_aktuelle_frage.pop(sid, None)

    def alle_haben_geantwortet(self) -> bool:
        if not self.players:
            return False
        return all(p.hat_aktuelle_frage_beantwortet for p in self.players.values())

    # --------------------------------------------------------------- Fragenfluss

    def naechste_frage_verfuegbar(self) -> bool:
        return len(self.gestellte_fragen_ids) < len(self.frage_pool)

    def naechste_frage_ziehen(self) -> Optional[Question]:
        """Zieht zufällig eine noch nicht gestellte Frage aus dem Pool."""
        verbleibend = [f for f in self.frage_pool if f.id not in self.gestellte_fragen_ids]
        if not verbleibend:
            return None
        frage = random.choice(verbleibend)
        self.gestellte_fragen_ids.add(frage.id)
        self.aktuelle_frage = frage
        self.aktuelle_frage_index += 1
        self.frage_start_zeit = time.time()
        self.antworten_aktuelle_frage = {}
        for p in self.players.values():
            p.neue_frage_zuruecksetzen()
        self.state = GameState.QUESTION
        return frage

    def antwort_einreichen(self, sid: str, antwort) -> Optional[dict]:
        """Prüft + speichert eine Spielerantwort. Gibt None zurück, falls ungültig/zu spät."""
        if self.state != GameState.QUESTION:
            return None
        if sid not in self.players:
            return None
        spieler = self.players[sid]
        if spieler.hat_aktuelle_frage_beantwortet:
            return None  # schon beantwortet -> ignorieren

        richtig = self.aktuelle_frage.ist_richtig(antwort)
        spieler.hat_aktuelle_frage_beantwortet = True
        spieler.letzte_antwort_richtig = richtig
        if richtig:
            spieler.score += POINTS_PER_CORRECT_ANSWER

        ergebnis = {"sid": sid, "antwort": antwort, "richtig": richtig}
        self.antworten_aktuelle_frage[sid] = ergebnis
        return ergebnis

    def frage_beenden(self):
        """Beendet die aktuelle Frage (manuell durch GM oder automatisch durch Timer)."""
        self.state = GameState.RESULT
        self.timer_abbrechen()

    def timer_abbrechen(self):
        if self.timer_handle is not None:
            try:
                self.timer_handle.cancel()
            except Exception:
                pass
            self.timer_handle = None

    # --------------------------------------------------------------- Punktestand

    def rangliste(self) -> List[dict]:
        sortiert = sorted(self.players.values(), key=lambda p: p.score, reverse=True)
        return [p.to_dict() for p in sortiert]

    def lobby_status(self) -> dict:
        return {
            "code": self.code,
            "spieler": [p.to_dict() for p in self.players.values()],
            "kategorie": self.kategorie_name,
            "schwierigkeit": self.schwierigkeit,
        }
