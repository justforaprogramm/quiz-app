/*
 * gamemaster.js
 * -------------
 * Steuert die UI der Gamemaster-Seite. Die eigentliche Logik (Punkte,
 * Zustände, Zufallsauswahl der Fragen) läuft komplett auf dem Server
 * (Python) - dieses Skript zeigt nur an, was der Server per Socket.IO
 * meldet, und schickt Befehle (Buttons) an den Server.
 */

const socket = io();

let aktuellerCode = null;
let aktuelleKategorien = [];
let timerInterval = null;

function zeigeSchritt(id) {
  document.querySelectorAll('[id^="schritt-"]').forEach((el) => el.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function zeigeFehler(nachricht) {
  const box = document.getElementById('fehler-anzeige');
  box.innerHTML = `<div class="error-box">${nachricht}</div>`;
  setTimeout(() => { box.innerHTML = ''; }, 6000);
}

socket.on('fehler', (data) => zeigeFehler(data.nachricht));
socket.on('connect_error', () => zeigeFehler('Verbindung zum Server fehlgeschlagen.'));

// ================================================================ Schritt 1: Session erstellen

document.getElementById('btn-session-erstellen').addEventListener('click', () => {
  socket.emit('gm_session_erstellen', {});
});

socket.on('session_erstellt', (data) => {
  aktuellerCode = data.code;
  aktuelleKategorien = data.kategorien;
  document.getElementById('code-anzeige-konfig').textContent = data.code;

  const select = document.getElementById('select-kategorie');
  select.innerHTML = '';
  if (data.kategorien.length === 0) {
    select.innerHTML = '<option value="">Keine Kategorien gefunden – JSON-Datei in den Quiz-Ordner legen</option>';
  } else {
    data.kategorien.forEach((k) => {
      const opt = document.createElement('option');
      opt.value = k.dateiname;
      opt.textContent = `${k.kategorie} (${k.dateiname})`;
      select.appendChild(opt);
    });
  }
  aktualisiereFragenInfo();
  zeigeSchritt('schritt-konfiguration');
});

function aktualisiereFragenInfo() {
  const dateiname = document.getElementById('select-kategorie').value;
  const schwierigkeit = document.getElementById('select-schwierigkeit').value;
  const kategorie = aktuelleKategorien.find((k) => k.dateiname === dateiname);
  const info = document.getElementById('fragen-verfuegbar-info');
  if (!kategorie) { info.textContent = ''; return; }
  const anzahl = kategorie.fragen_pro_schwierigkeit[schwierigkeit] || 0;
  info.textContent = `${anzahl} Frage(n) verfügbar für "${schwierigkeit}"`;
  info.className = `badge ${schwierigkeit}`;
}
document.getElementById('select-kategorie').addEventListener('change', aktualisiereFragenInfo);
document.getElementById('select-schwierigkeit').addEventListener('change', aktualisiereFragenInfo);

// ================================================================ Schritt 2: Konfiguration speichern

document.getElementById('btn-konfiguration-speichern').addEventListener('click', () => {
  const dateiname = document.getElementById('select-kategorie').value;
  const schwierigkeit = document.getElementById('select-schwierigkeit').value;
  if (!dateiname) { zeigeFehler('Bitte eine Kategorie wählen.'); return; }
  socket.emit('gm_quiz_konfigurieren', { code: aktuellerCode, dateiname, schwierigkeit });
});

socket.on('quiz_konfiguriert', (data) => {
  document.getElementById('code-anzeige-lobby').textContent = aktuellerCode;
  document.getElementById('lobby-kategorie-info').textContent =
    `Kategorie: ${data.kategorie} · Schwierigkeit: ${data.schwierigkeit} · ${data.fragen_verfuegbar} Fragen verfügbar`;
  zeigeSchritt('schritt-lobby');
});

// ================================================================ Schritt 3: Lobby

socket.on('lobby_update', (data) => {
  const liste = document.getElementById('lobby-spieler-liste');
  liste.innerHTML = '';
  data.spieler.forEach((p) => {
    const li = document.createElement('li');
    li.innerHTML = `<span><span class="status-dot"></span>${escapeHtml(p.name)}</span><span>${p.score} Pkt.</span>`;
    liste.appendChild(li);
  });
  document.getElementById('lobby-spieler-anzahl').textContent = data.spieler.length;
  document.getElementById('btn-quiz-starten').disabled = data.spieler.length === 0;
});

document.getElementById('btn-quiz-starten').addEventListener('click', () => {
  socket.emit('gm_quiz_starten', { code: aktuellerCode });
});

// ================================================================ Schritt 4: Aktive Frage

function rendereFrageGM(frage) {
  document.getElementById('frage-text').textContent = frage.frage;
  const container = document.getElementById('frage-optionen');
  container.innerHTML = '';

  if (frage.typ === 'boolean') {
    [['Wahr', true], ['Falsch', false]].forEach(([label, wert]) => {
      const istRichtig = wert === frage.richtige_antwort;
      const div = document.createElement('div');
      div.className = 'option-btn' + (istRichtig ? ' correct' : '');
      div.textContent = label + (istRichtig ? '  ✓ richtig' : '');
      container.appendChild(div);
    });
  } else {
    frage.optionen.forEach((text, i) => {
      const istRichtig = i === frage.richtige_antwort;
      const div = document.createElement('div');
      div.className = 'option-btn' + (istRichtig ? ' correct' : '');
      div.textContent = text + (istRichtig ? '  ✓ richtig' : '');
      container.appendChild(div);
    });
  }
}

socket.on('frage_gestartet_gm', (data) => {
  document.getElementById('frage-fortschritt').textContent =
    `Frage ${data.frage_nummer} / ${data.fragen_gesamt}`;
  rendereFrageGM(data.frage);
  document.getElementById('antworten-status').textContent = `0 / ${data.spieler_anzahl} haben geantwortet`;
  starteTimerAnzeige(data.frage.zeitlimit);
  zeigeSchritt('schritt-frage');
});

socket.on('antwort_eingegangen', (data) => {
  document.getElementById('antworten-status').textContent = `${data.beantwortet} / ${data.gesamt} haben geantwortet`;
});

function starteTimerAnzeige(zeitlimit) {
  const anzeige = document.getElementById('frage-timer');
  clearInterval(timerInterval);
  if (!zeitlimit) {
    anzeige.classList.add('hidden');
    return;
  }
  anzeige.classList.remove('hidden');
  const ende = Date.now() + zeitlimit * 1000;
  const tick = () => {
    const rest = Math.max(0, Math.round((ende - Date.now()) / 1000));
    anzeige.textContent = `⏱ ${rest}s`;
    if (rest <= 0) clearInterval(timerInterval);
  };
  tick();
  timerInterval = setInterval(tick, 250);
}

document.getElementById('btn-frage-beenden').addEventListener('click', () => {
  socket.emit('gm_frage_beenden', { code: aktuellerCode });
});

// ================================================================ Schritt 5: Ergebnis

function rendereRangliste(containerId, rangliste) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  rangliste.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'rank-row';
    row.innerHTML = `<span><span class="place">#${i + 1}</span>${escapeHtml(p.name)}</span><span>${p.score} Pkt.</span>`;
    el.appendChild(row);
  });
}

socket.on('frage_beendet', (data) => {
  clearInterval(timerInterval);
  const loesungText = data.frage_typ === 'boolean'
    ? (data.richtige_antwort ? 'Wahr' : 'Falsch')
    : `Option ${data.richtige_antwort + 1}`;
  document.getElementById('ergebnis-loesung').textContent = `Richtige Antwort: ${loesungText}`;
  document.getElementById('ergebnis-erklaerung').textContent = data.erklaerung || '';
  rendereRangliste('ergebnis-rangliste', data.rangliste);
  const weiterBtn = document.getElementById('btn-naechste-frage');
  weiterBtn.disabled = !data.weitere_fragen_verfuegbar;
  weiterBtn.textContent = data.weitere_fragen_verfuegbar ? 'Nächste Frage' : 'Keine weiteren Fragen';
  zeigeSchritt('schritt-ergebnis');
});

document.getElementById('btn-naechste-frage').addEventListener('click', () => {
  socket.emit('gm_naechste_frage', { code: aktuellerCode });
});

socket.on('keine_weiteren_fragen', () => {
  zeigeFehler('Keine weiteren Fragen für diese Schwierigkeit verfügbar. Du kannst das Quiz jetzt beenden.');
});

document.getElementById('btn-quiz-beenden').addEventListener('click', () => {
  socket.emit('gm_quiz_beenden', { code: aktuellerCode });
});

// ================================================================ Schritt 6: Quiz beendet

socket.on('quiz_beendet', (data) => {
  rendereRangliste('ende-rangliste', data.rangliste);
  zeigeSchritt('schritt-ende');
});

// ================================================================ Hilfsfunktion

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}
