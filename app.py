"""
app.py
------
Einstiegspunkt der Quiz-WebApp.

Enthält:
  1) Die Flask-Routen für die drei Seiten (Start, Gamemaster, Spieler)
  2) Alle Socket.IO-Events, die die Echtzeit-Kommunikation zwischen
     Gamemaster und Spielern steuern (siehe README.md, Abschnitt "Ablauf"
     und das Mermaid-Sequenzdiagramm dort)

Die eigentlichen Spielregeln/Zustände/Daten liegen NICHT hier, sondern in
models.py (GameSession, Player, Question), game_manager.py (Verwaltung
aller Sessions) und quiz_loader.py (Laden der Kategorie-JSON-Dateien).
app.py ist bewusst nur die "Verkabelung" zwischen Web-Clients und der
eigentlichen Logik - das hält die Spielregeln an einer Stelle testbar.
"""

import threading

from flask import Flask, render_template, request
from flask_socketio import SocketIO, emit, join_room

from config import DEBUG, HOST, PORT, SECRET_KEY, TIME_LIMITS
from game_manager import GameManager
from models import GameState
from quiz_loader import QuizLoader, QuizValidationError

app = Flask(__name__)
app.config["SECRET_KEY"] = SECRET_KEY

# async_mode="threading" braucht keine zusätzliche Abhängigkeit (kein eventlet/gevent
# nötig) und funktioniert zuverlässig zusammen mit threading.Timer für die Zeitlimits.
socketio = SocketIO(app, async_mode="threading", cors_allowed_origins="*")

game_manager = GameManager()
quiz_loader = QuizLoader()
quiz_loader.alle_neu_laden()


# ================================================================== Webseiten

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/gamemaster")
def gamemaster_page():
    return render_template("gamemaster.html")


@app.route("/player")
def player_page():
    return render_template("player.html")


# ================================================================== Hilfsfunktionen
#
# Diese Funktionen kapseln Abläufe, die von mehreren Events gebraucht werden
# (z.B. eine Frage an alle senden, oder eine Frage abschließen), damit die
# eigentlichen @socketio.on-Handler unten kurz und klar bleiben.

def _fehler(nachricht: str):
    """Schickt eine Fehlermeldung NUR an den Client, der das aktuelle Event ausgelöst hat."""
    emit("fehler", {"nachricht": nachricht})


def _ist_gamemaster(session, sid: str) -> bool:
    return session is not None and session.gamemaster_sid == sid


def _frage_an_raum_senden(session):
    """
    Sendet die aktuelle Frage an alle Beteiligten:
      - Spieler bekommen die Version OHNE Lösung (frage.fuer_spieler())
      - Der Gamemaster bekommt zusätzlich die Lösung, direkt an seine eigene sid
    Richtet außerdem - falls die Schwierigkeit ein Zeitlimit hat (mittel/schwer) -
    einen Timer ein, der die Frage automatisch beendet.
    """
    frage = session.aktuelle_frage

    payload_spieler = {
        "frage": frage.fuer_spieler(),
        "frage_nummer": session.aktuelle_frage_index,
        "fragen_gesamt": len(session.frage_pool),
        "spieler_anzahl": len(session.players),
    }
    socketio.emit("frage_gestartet", payload_spieler, room=session.code)

    payload_gm = dict(payload_spieler)
    payload_gm["frage"] = frage.fuer_gamemaster()
    socketio.emit("frage_gestartet_gm", payload_gm, room=session.gamemaster_sid)

    session.timer_abbrechen()
    limit = TIME_LIMITS.get(session.schwierigkeit)
    if limit is not None:
        handle = threading.Timer(limit, _frage_automatisch_beenden, args=(session.code,))
        handle.daemon = True
        session.timer_handle = handle
        handle.start()


def _frage_automatisch_beenden(code: str):
    """Wird vom Hintergrund-Timer aufgerufen, wenn die Zeit für 'mittel'/'schwer' abgelaufen ist."""
    session = game_manager.session_holen(code)
    if session is None or session.state != GameState.QUESTION:
        return  # Frage wurde inzwischen schon manuell beendet o.ä. -> nichts tun
    _frage_abschliessen(session)


def _frage_abschliessen(session):
    """Beendet die aktuelle Frage und sendet Lösung + aktuelle Rangliste an alle im Raum."""
    session.frage_beenden()
    frage = session.aktuelle_frage
    payload = {
        "frage_id": frage.id,
        "frage_typ": frage.typ,
        "richtige_antwort": frage.richtige_antwort_anzeigen(),
        "erklaerung": frage.erklaerung,
        "rangliste": session.rangliste(),
        "weitere_fragen_verfuegbar": session.naechste_frage_verfuegbar(),
    }
    socketio.emit("frage_beendet", payload, room=session.code)


# ================================================================== Verbindung

@socketio.on("connect")
def on_connect():
    pass  # Der Client muss sich nach dem Verbinden noch per Event anmelden (GM oder Spieler)


@socketio.on("disconnect")
def on_disconnect():
    sid = request.sid

    # War der Trennende der Gamemaster? -> Session beenden, Spieler informieren.
    session = game_manager.session_per_gamemaster_sid(sid)
    if session is not None:
        socketio.emit("gamemaster_getrennt", {}, room=session.code)
        game_manager.session_loeschen(session.code)
        return

    # War der Trennende ein Spieler? -> nur ihn entfernen, Rest läuft weiter.
    session = game_manager.session_per_spieler_sid(sid)
    if session is not None:
        session.spieler_entfernen(sid)
        socketio.emit("lobby_update", session.lobby_status(), room=session.code)
        if session.state == GameState.QUESTION and session.alle_haben_geantwortet():
            _frage_abschliessen(session)


# ================================================================== Gamemaster-Events

@socketio.on("gm_session_erstellen")
def gm_session_erstellen(data=None):
    """Erstellt eine neue GameSession und schickt dem Gamemaster den Beitritts-Code
    sowie die Liste aller verfügbaren Kategorien (= JSON-Dateien im Quiz-Ordner)."""
    quiz_loader.alle_neu_laden()  # neue/geänderte JSON-Dateien ohne Serverneustart erkennen
    session = game_manager.session_erstellen(gamemaster_sid=request.sid)
    join_room(session.code)
    emit("session_erstellt", {
        "code": session.code,
        "kategorien": quiz_loader.kategorien_liste(),
    })


@socketio.on("gm_quiz_konfigurieren")
def gm_quiz_konfigurieren(data):
    """Der Gamemaster wählt Kategorie (= welche JSON-Datei) und Schwierigkeit."""
    data = data or {}
    session = game_manager.session_holen(data.get("code", ""))
    if not _ist_gamemaster(session, request.sid):
        return _fehler("Keine Berechtigung oder Session nicht gefunden.")
    if session.state != GameState.LOBBY:
        return _fehler("Das Quiz läuft bereits - Kategorie kann nicht mehr geändert werden.")

    try:
        kategorie = quiz_loader.kategorie_holen(data.get("dateiname"))
    except QuizValidationError as exc:
        return _fehler(str(exc))

    schwierigkeit = data.get("schwierigkeit")
    session.quiz_konfigurieren(kategorie.kategorie, schwierigkeit, kategorie.fragen)

    socketio.emit("quiz_konfiguriert", {
        "kategorie": kategorie.kategorie,
        "schwierigkeit": schwierigkeit,
        "fragen_verfuegbar": len(session.frage_pool),
    }, room=session.code)


@socketio.on("gm_quiz_starten")
def gm_quiz_starten(data):
    session = game_manager.session_holen((data or {}).get("code", ""))
    if not _ist_gamemaster(session, request.sid):
        return _fehler("Keine Berechtigung oder Session nicht gefunden.")
    if not session.frage_pool:
        return _fehler("Bitte zuerst Kategorie und Schwierigkeit wählen.")
    if not session.players:
        return _fehler("Es ist noch kein Spieler beigetreten.")

    frage = session.naechste_frage_ziehen()
    if frage is None:
        return _fehler("Für diese Schwierigkeit sind keine Fragen vorhanden.")
    _frage_an_raum_senden(session)


@socketio.on("gm_naechste_frage")
def gm_naechste_frage(data):
    session = game_manager.session_holen((data or {}).get("code", ""))
    if not _ist_gamemaster(session, request.sid):
        return _fehler("Keine Berechtigung oder Session nicht gefunden.")
    if session.state == GameState.QUESTION:
        return _fehler("Die aktuelle Frage läuft noch.")

    frage = session.naechste_frage_ziehen()
    if frage is None:
        emit("keine_weiteren_fragen", {})
        return
    _frage_an_raum_senden(session)


@socketio.on("gm_frage_beenden")
def gm_frage_beenden(data):
    """Manuelles Beenden der aktuellen Frage (nötig bei 'leicht', da kein Zeitlimit läuft;
    bei 'mittel'/'schwer' kann der Gamemaster die Frage damit auch vorzeitig abbrechen)."""
    session = game_manager.session_holen((data or {}).get("code", ""))
    if not _ist_gamemaster(session, request.sid):
        return _fehler("Keine Berechtigung oder Session nicht gefunden.")
    if session.state != GameState.QUESTION:
        return _fehler("Es läuft aktuell keine Frage.")
    _frage_abschliessen(session)


@socketio.on("gm_quiz_beenden")
def gm_quiz_beenden(data):
    session = game_manager.session_holen((data or {}).get("code", ""))
    if not _ist_gamemaster(session, request.sid):
        return _fehler("Keine Berechtigung oder Session nicht gefunden.")

    session.timer_abbrechen()
    session.state = GameState.FINISHED
    socketio.emit("quiz_beendet", {"rangliste": session.rangliste()}, room=session.code)


# ================================================================== Spieler-Events

@socketio.on("player_beitreten")
def player_beitreten(data):
    data = data or {}
    code = data.get("code", "")
    name = (data.get("name") or "").strip()

    session = game_manager.session_holen(code)
    if session is None:
        return _fehler("Code nicht gefunden. Bitte beim Gamemaster nachfragen.")
    if session.state != GameState.LOBBY:
        return _fehler("Dieses Quiz läuft bereits oder ist beendet - kein Beitritt mehr möglich.")
    if not name:
        return _fehler("Bitte einen Namen eingeben.")
    if any(p.name.lower() == name.lower() for p in session.players.values()):
        return _fehler("Dieser Name ist in diesem Quiz schon vergeben.")

    session.spieler_hinzufuegen(request.sid, name)
    join_room(session.code)

    emit("beitritt_erfolgreich", {"code": session.code, "name": name})
    socketio.emit("lobby_update", session.lobby_status(), room=session.code)


@socketio.on("player_antwort_einreichen")
def player_antwort_einreichen(data):
    data = data or {}
    session = game_manager.session_holen(data.get("code", ""))
    if session is None:
        return _fehler("Session nicht gefunden.")

    ergebnis = session.antwort_einreichen(request.sid, data.get("antwort"))
    if ergebnis is None:
        return _fehler("Antwort konnte nicht angenommen werden (zu spät oder schon beantwortet).")

    emit("antwort_bestaetigt", {"richtig": ergebnis["richtig"]})
    socketio.emit("antwort_eingegangen", {
        "beantwortet": sum(1 for p in session.players.values() if p.hat_aktuelle_frage_beantwortet),
        "gesamt": len(session.players),
    }, room=session.gamemaster_sid)

    if session.alle_haben_geantwortet():
        _frage_abschliessen(session)


# ================================================================== Start

if __name__ == "__main__":
    print(f"Quiz-App läuft auf http://localhost:{PORT}")
    print("  Gamemaster: /gamemaster      Spieler: /player")
    socketio.run(app, host=HOST, port=PORT, debug=DEBUG, allow_unsafe_werkzeug=True)
