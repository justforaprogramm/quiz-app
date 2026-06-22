/*
 * player.js
 * ---------
 * Steuert die UI der Spieler-Seite. Wie bei gamemaster.js liegt alle
 * Spiellogik auf dem Server (Python) - dieses Skript zeigt nur an, was
 * der Server meldet, und sendet Antworten an den Server.
 */

const socket = io();

let aktuellerCode = null;
let eigenerName = null;
let timerInterval = null;
let bereitsGeantwortet = false;

function zeigeSchritt(id) {
  document.querySelectorAll('[id^="schritt-"]').forEach((el) => el.classList.add('hidden'));
  document.getElementById(id).classList.remove('hidden');
}

function zeigeFehler(nachricht) {
  const box = document.getElementById('fehler-anzeige');
  box.innerHTML = `<div class="error-box">${nachricht}</div>`;
  setTimeout(() => { box.innerHTML = ''; }, 6000);
}

function escapeHtml(text) {
  const div = document.createElement('div');
  div.textContent = text;
  return div.innerHTML;
}

socket.on('fehler', (data) => zeigeFehler(data.nachricht));
socket.on('connect_error', () => zeigeFehler('Verbindung zum Server fehlgeschlagen.'));

// ================================================================ Beitritt

document.getElementById('btn-beitreten').addEventListener('click', () => {
  const code = document.getElementById('input-code').value.trim().toUpperCase();
  const name = document.getElementById('input-name').value.trim();
  if (!code || !name) { zeigeFehler('Bitte Code und Namen eingeben.'); return; }
  socket.emit('player_beitreten', { code, name });
});

// Enter-Taste im Namensfeld soll auch beitreten
document.getElementById('input-name').addEventListener('keydown', (e) => {
  if (e.key === 'Enter') document.getElementById('btn-beitreten').click();
});

socket.on('beitritt_erfolgreich', (data) => {
  aktuellerCode = data.code;
  eigenerName = data.name;
  document.getElementById('lobby-eigener-name').textContent = eigenerName;
  zeigeSchritt('schritt-lobby');
});

socket.on('lobby_update', (data) => {
  const liste = document.getElementById('lobby-spieler-liste');
  liste.innerHTML = '';
  data.spieler.forEach((p) => {
    const li = document.createElement('li');
    li.innerHTML = `<span><span class="status-dot"></span>${escapeHtml(p.name)}</span><span>${p.score} Pkt.</span>`;
    liste.appendChild(li);
  });
  document.getElementById('lobby-spieler-anzahl').textContent = data.spieler.length;
});

// ================================================================ Aktive Frage

function rendereFrageSpieler(frage) {
  bereitsGeantwortet = false;
  document.getElementById('antwort-gesendet-info').textContent = '';
  document.getElementById('frage-text').textContent = frage.frage;
  const container = document.getElementById('frage-optionen');
  container.innerHTML = '';

  if (frage.typ === 'boolean') {
    [['Wahr', true], ['Falsch', false]].forEach(([label, wert]) => {
      const btn = document.createElement('button');
      btn.className = 'option-btn';
      btn.textContent = label;
      btn.addEventListener('click', () => antwortSenden(wert, btn));
      container.appendChild(btn);
    });
  } else {
    frage.optionen.forEach((text, i) => {
      const btn = document.createElement('button');
      btn.className = 'option-btn';
      btn.textContent = text;
      btn.addEventListener('click', () => antwortSenden(i, btn));
      container.appendChild(btn);
    });
  }
}

function antwortSenden(wert, btnElement) {
  if (bereitsGeantwortet) return;
  bereitsGeantwortet = true;
  document.querySelectorAll('#frage-optionen .option-btn').forEach((b) => { b.disabled = true; });
  btnElement.classList.add('chosen');
  socket.emit('player_antwort_einreichen', { code: aktuellerCode, antwort: wert });
}

socket.on('frage_gestartet', (data) => {
  document.getElementById('frage-fortschritt').textContent =
    `Frage ${data.frage_nummer} / ${data.fragen_gesamt}`;
  rendereFrageSpieler(data.frage);
  starteTimerAnzeige(data.frage.zeitlimit);
  zeigeSchritt('schritt-frage');
});

socket.on('antwort_bestaetigt', (data) => {
  document.getElementById('antwort-gesendet-info').textContent =
    data.richtig ? '✅ Antwort gesendet – richtig!' : '❌ Antwort gesendet – leider falsch.';
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

// ================================================================ Ergebnis

function rendereRangliste(containerId, rangliste) {
  const el = document.getElementById(containerId);
  el.innerHTML = '';
  rangliste.forEach((p, i) => {
    const row = document.createElement('div');
    row.className = 'rank-row';
    if (p.name === eigenerName) row.style.outline = '2px solid var(--accent)';
    row.innerHTML = `<span><span class="place">#${i + 1}</span>${escapeHtml(p.name)}</span><span>${p.score} Pkt.</span>`;
    el.appendChild(row);
  });
}

socket.on('frage_beendet', (data) => {
  clearInterval(timerInterval);
  const loesungText = data.frage_typ === 'boolean'
    ? (data.richtige_antwort ? 'Wahr' : 'Falsch')
    : `Option ${data.richtige_antwort + 1}`;
  document.getElementById('ergebnis-titel').textContent = 'Ergebnis dieser Frage';
  document.getElementById('ergebnis-loesung').textContent = `Richtige Antwort: ${loesungText}`;
  document.getElementById('ergebnis-erklaerung').textContent = data.erklaerung || '';
  rendereRangliste('ergebnis-rangliste', data.rangliste);
  zeigeSchritt('schritt-ergebnis');
});

// ================================================================ Quiz beendet

socket.on('quiz_beendet', (data) => {
  rendereRangliste('ende-rangliste', data.rangliste);
  zeigeSchritt('schritt-ende');
});

socket.on('gamemaster_getrennt', () => {
  zeigeFehler('Der Gamemaster hat die Verbindung getrennt. Das Spiel wurde beendet.');
});
