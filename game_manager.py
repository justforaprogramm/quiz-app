"""
game_manager.py
----------------
Verwaltet ALLE aktiven GameSession-Objekte (eine pro laufendem Quiz) und ist
für die Generierung eindeutiger Beitritts-Codes verantwortlich.

app.py spricht nur mit dem GameManager (und der QuizLoader-Instanz) - die
eigentliche Spiellogik lebt in models.GameSession.
"""

from __future__ import annotations

import random
import threading
from typing import Dict, Optional

from config import GAME_CODE_ALPHABET, GAME_CODE_LENGTH
from models import GameSession


class GameManager:
    def __init__(self):
        self._sessions: Dict[str, GameSession] = {}
        self._lock = threading.Lock()

    # --------------------------------------------------------------- Codes

    def _neuen_code_generieren(self) -> str:
        while True:
            code = "".join(random.choice(GAME_CODE_ALPHABET) for _ in range(GAME_CODE_LENGTH))
            if code not in self._sessions:
                return code

    # --------------------------------------------------------------- Sessions

    def session_erstellen(self, gamemaster_sid: str) -> GameSession:
        with self._lock:
            code = self._neuen_code_generieren()
            session = GameSession(code=code, gamemaster_sid=gamemaster_sid)
            self._sessions[code] = session
            return session

    def session_holen(self, code: str) -> Optional[GameSession]:
        return self._sessions.get(code.upper().strip()) if code else None

    def session_loeschen(self, code: str) -> None:
        with self._lock:
            self._sessions.pop(code, None)

    def session_per_gamemaster_sid(self, sid: str) -> Optional[GameSession]:
        for session in self._sessions.values():
            if session.gamemaster_sid == sid:
                return session
        return None

    def session_per_spieler_sid(self, sid: str) -> Optional[GameSession]:
        for session in self._sessions.values():
            if sid in session.players:
                return session
        return None
