"""
config.py
---------
Zentrale Konfigurationswerte für die Quiz-WebApp.
Alles, was an mehreren Stellen im Code gebraucht wird, steht hier - nicht verstreut.
"""

import os

# Basisverzeichnis des Projekts (Ordner, in dem app.py liegt)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Ordner, in dem die Kategorie-JSON-Dateien liegen
QUIZ_FOLDER = os.path.join(BASE_DIR, "Quiz")

# Gültige Schwierigkeitsgrade (Reihenfolge wird auch in der UI so verwendet)
DIFFICULTIES = ["leicht", "mittel", "schwer"]

# Zeitlimit pro Schwierigkeitsgrad in Sekunden.
# None = kein Zeitlimit (Gamemaster entscheidet manuell, wann die Frage endet).
TIME_LIMITS = {
    "leicht": None,
    "mittel": 120,
    "schwer": 30,
}

# Gültige Fragetypen
QUESTION_TYPES = ["boolean", "multiple_choice"]

# Punkte für eine richtige Antwort (flach, keine Zeitbonus-Logik -> einfacher & robuster)
POINTS_PER_CORRECT_ANSWER = 100

# Länge des Beitritts-Codes (Buchstaben+Ziffern, ohne verwechselbare Zeichen)
GAME_CODE_LENGTH = 5
GAME_CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"  # ohne O/0/I/1 zur besseren Lesbarkeit

# Dateien, die NICHT als Kategorie geladen werden sollen (z.B. das Template selbst)
IGNORED_QUIZ_FILE_PREFIXES = ("_",)

# Flask-Konfiguration
SECRET_KEY = "dev-secret-key-bitte-in-produktion-aendern"
HOST = "0.0.0.0"
PORT = 5000
DEBUG = True
