/**
 * The Bull & Bear Desk Report -- a bulletin-style popup, top-right corner,
 * that "airs" a fresh script every 30 minutes and pops itself open.
 *
 * Bull and Bear are decoration -- two fictional anchors, clearly labeled as
 * such, invented purely to read out REAL numbers. Every line in the script
 * traces to a field already exposed by /api/status (see state/store.js):
 * today's P&L, eligible/open counts, real incidents, real risk flags. The
 * "weather" (rain on a red day, sun on a green day) is a visual read of the
 * same real todaysPnl() sign -- nothing here is a separate invented mood.
 *
 * Voice: there's a hook for ElevenLabs TTS, deliberately inert. No API key
 * is configured in this environment, so the button explains that instead of
 * silently failing or pretending to speak. Wire a real key in and swap
 * speakScript() below for an actual fetch to ElevenLabs' TTS endpoint.
 */

import { todaysPnl, eligibleCount, symbols, riskFlags, incidentState, dataAgeSeconds } from '../state/store.js';
import { currentSession } from '../world/lighting.js';

const BROADCAST_INTERVAL_MS = 30 * 60 * 1000;   // a new broadcast airs every 30 min
const AUTO_COLLAPSE_MS = 45 * 1000;              // then tucks itself back into the corner tab

let lastBroadcastAt = 0;
let lastScript = null;
let collapseTimer = null;

const money = v => (v < 0 ? '-$' : '+$') + Math.abs(v).toFixed(2);

// Real drawn faces for the two anchors -- inline SVG, no new image assets,
// same "no external dependencies" rule as the rest of hq/. Original cartoon
// designs (bold ink outline, oversized eyes, suit-and-tie) in the general
// flat-cartoon-news-anchor style, NOT a reproduction of any specific
// copyrighted character. Decoration only: fictional presenters, not a
// rendering of anything real. Kept as path-only fragments (FACE_INNER) so
// the SAME artwork can be composited twice, side by side, into one shared
// booth scene (see boothSvg()) instead of drawn once per speech line.
const FACE_INNER = {
  bull: `
    <path d="M2 40 Q3 28 10 25 L26 25 Q33 28 34 40 Z" fill="#2b3550" stroke="#1c1712" stroke-width="1.4"/>
    <path d="M18 25 L14.5 32 L18 36 L21.5 32 Z" fill="#c0392b" stroke="#1c1712" stroke-width="1"/>
    <path d="M5 9 Q1.5 2.5 7 3.6 Q8.4 8 9.6 10.4" fill="#e8e2d8" stroke="#1c1712" stroke-width="1.6" stroke-linejoin="round"/>
    <path d="M31 9 Q34.5 2.5 29 3.6 Q27.6 8 26.4 10.4" fill="#e8e2d8" stroke="#1c1712" stroke-width="1.6" stroke-linejoin="round"/>
    <circle cx="18" cy="15" r="13" fill="#d9ac72" stroke="#1c1712" stroke-width="1.8"/>
    <path d="M9 11.5 Q12 8.7 15.2 11" fill="none" stroke="#1c1712" stroke-width="1.7" stroke-linecap="round"/>
    <path d="M27 11.5 Q24 8.7 20.8 11" fill="none" stroke="#1c1712" stroke-width="1.7" stroke-linecap="round"/>
    <ellipse cx="12.4" cy="15.5" rx="4.4" ry="5" fill="#fff" stroke="#1c1712" stroke-width="1.3"/>
    <ellipse cx="23.6" cy="15.5" rx="4.4" ry="5" fill="#fff" stroke="#1c1712" stroke-width="1.3"/>
    <circle cx="13.4" cy="16.6" r="1.9" fill="#1c1712"/>
    <circle cx="22.6" cy="16.6" r="1.9" fill="#1c1712"/>
    <ellipse cx="18" cy="23.5" rx="7.2" ry="4.4" fill="#eccf9a" stroke="#1c1712" stroke-width="1.3"/>
    <circle cx="15.4" cy="23.5" r="0.85" fill="#1c1712"/>
    <circle cx="20.6" cy="23.5" r="0.85" fill="#1c1712"/>
    <path d="M13 25.5 Q18 28 23 25.5" fill="none" stroke="#1c1712" stroke-width="1.2" stroke-linecap="round"/>`,
  bear: `
    <path d="M2 40 Q3 28 10 25 L26 25 Q33 28 34 40 Z" fill="#402a1c" stroke="#1c1712" stroke-width="1.4"/>
    <path d="M18 25 L14.5 32 L18 36 L21.5 32 Z" fill="#1f5c33" stroke="#1c1712" stroke-width="1"/>
    <circle cx="7" cy="6" r="4.6" fill="#6b5237" stroke="#1c1712" stroke-width="1.6"/>
    <circle cx="29" cy="6" r="4.6" fill="#6b5237" stroke="#1c1712" stroke-width="1.6"/>
    <circle cx="18" cy="16" r="13" fill="#7a5f40" stroke="#1c1712" stroke-width="1.8"/>
    <ellipse cx="12.4" cy="16.3" rx="4.4" ry="5" fill="#fff" stroke="#1c1712" stroke-width="1.3"/>
    <ellipse cx="23.6" cy="16.3" rx="4.4" ry="5" fill="#fff" stroke="#1c1712" stroke-width="1.3"/>
    <circle cx="13.4" cy="17.4" r="1.9" fill="#1c1712"/>
    <circle cx="22.6" cy="17.4" r="1.9" fill="#1c1712"/>
    <ellipse cx="18" cy="24.3" rx="6.6" ry="4.3" fill="#c9a877" stroke="#1c1712" stroke-width="1.3"/>
    <circle cx="18" cy="24" r="1.3" fill="#1c1712"/>
    <path d="M13.4 26.4 Q18 28.6 22.6 26.4" fill="none" stroke="#1c1712" stroke-width="1.2" stroke-linecap="round"/>`
};

/**
 * The shared booth: both anchors, sitting together behind one desk, with a
 * skyline of little rooftops in the window behind them -- a nod to the same
 * town this bulletin reports on, not a literal second copy of the real map.
 * Built once per broadcast (see renderCard), not once per line -- this is
 * what makes it read as "the same booth" rather than two separate cutaways.
 */
function boothSvg() {
  return `<svg viewBox="0 0 280 92" xmlns="http://www.w3.org/2000/svg" aria-hidden="true" class="nb-booth-svg">
    <defs>
      <linearGradient id="nbSky" x1="0" y1="0" x2="0" y2="1">
        <stop offset="0%" stop-color="#2a2350"/>
        <stop offset="100%" stop-color="#171226"/>
      </linearGradient>
    </defs>
    <rect x="0" y="0" width="280" height="92" fill="url(#nbSky)"/>
    <g opacity=".5" fill="#0e0b1a">
      <path d="M6 60 L6 48 L18 38 L30 48 L30 60 Z"/>
      <path d="M36 60 L36 44 L50 44 L50 60 Z"/>
      <path d="M56 60 L56 50 L68 40 L80 50 L80 60 Z"/>
      <path d="M198 60 L198 46 L210 46 L210 60 Z"/>
      <path d="M216 60 L216 50 L228 40 L240 50 L240 60 Z"/>
      <path d="M246 60 L246 44 L260 44 L260 60 Z"/>
      <path d="M266 60 L266 52 L274 46 L280 52 L280 60 Z"/>
    </g>
    <rect x="0" y="58" width="280" height="3" fill="#3a3350" opacity=".7"/>
    <g transform="translate(63,4) scale(1.5)">${FACE_INNER.bull}</g>
    <g transform="translate(163,4) scale(1.5)">${FACE_INNER.bear}</g>
    <rect x="0" y="72" width="280" height="20" fill="#4a3623" stroke="#1c1712" stroke-width="1.5"/>
    <rect x="0" y="72" width="280" height="4" fill="#5f4630"/>
    <text x="140" y="86" text-anchor="middle" font-family="ui-monospace, monospace" font-size="8" font-weight="700" letter-spacing="2" fill="#e8c15a">THE DESK</text>
  </svg>`;
}

function escapeHtml(str) {
  return String(str).replace(/[&<>"']/g, c => (
    { '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#39;' }[c]
  ));
}

/**
 * Build tonight's/today's script from real state. Nothing invented -- every
 * substituted value below is a real field (see the imports up top). The
 * VOICE is invented: Bull is chronically upbeat, Bear is dry and sarcastic,
 * and each line reacts to the one before it rather than reading its own
 * isolated stat -- that's what makes it a conversation instead of two
 * separate tickers taking turns.
 */
function buildScript(s) {
  const session = currentSession(s);
  const pnl = todaysPnl(s);
  const trades = (s && s.todays_trades) || [];
  const hasTrades = trades.length > 0;
  const elig = eligibleCount(s), total = symbols(s).length;
  const openCount = (s && s.scan && s.scan.managed) || 0;
  const risk = riskFlags(s);
  const inc = incidentState(s, session);

  const weather = !hasTrades ? 'cloud' : pnl > 0 ? 'sun' : pnl < 0 ? 'rain' : 'cloud';
  const sessLabel = session.label.toLowerCase();

  const lines = [
    { a: 'bull', emoji: '📺', text: `Good ${sessLabel}, I'm Bull — and folks, it is a BEAUTIFUL day on the desk.` },
    hasTrades
      ? { a: 'bear', emoji: pnl >= 0 ? '💰' : '🔻',
          text: `It's ${sessLabel}, we're ${pnl >= 0 ? 'up' : 'down'} ${money(pnl)} across ${trades.length} trade${trades.length === 1 ? '' : 's'}, and Bull already called it "beautiful." Bar's low tonight.` }
      : { a: 'bear', emoji: '💤', text: `No trades logged today. "Beautiful" is a stretch, Bull.` },
    { a: 'bull', emoji: '🙂', text: hasTrades ? `Every ${pnl >= 0 ? 'win' : 'lesson'} counts, Bear.` : `Quiet days build character, Bear.` },
    { a: 'bear', emoji: '🖥️', text: `${elig} of ${total} watchlist symbols are "eligible" right now — generous word for "technically allowed."` },
    { a: 'bull', emoji: '📋', text: `And ${openCount} position${openCount === 1 ? '' : 's'} open, nothing's on fire. I'll take it.` },
    inc.active
      ? { a: 'bear', emoji: inc.severity === 'alert' ? '🚨' : '⚠️', text: `Correction: ${inc.reasons[0].text} So something IS on fire, actually.` }
      : { a: 'bear', emoji: '😐', text: `...for once.` },
    { a: 'bull', emoji: '🤔', text: `Risk desk?` },
    {
      a: 'bear', emoji: risk.alerting ? '🛑' : '🟢',
      text: risk.alerting
        ? `${[
            risk.paused ? "weekly breaker's active" : null,
            risk.blackout.length ? `earnings blackout on ${risk.blackout.join(', ')}` : null
          ].filter(Boolean).join(', ') || risk.weekly}. Not exactly "clear," Bull.`
        : `Clear. Shockingly.`
    },
    { a: 'bull', emoji: '👋', text: `That's the desk, folks. Back in thirty.` },
    { a: 'bear', emoji: weather === 'sun' ? '☀️' : weather === 'rain' ? '🌧️' : '⛅',
      text: `Try to contain your excitement. ${weather === 'rain' ? 'Bring an umbrella.' : weather === 'sun' ? 'Wear sunscreen.' : 'Grab a coat, maybe.'}` }
  ];

  return { session, weather, lines, generatedAt: Date.now() };
}

/**
 * The "breaking news" cut-in -- plays ONLY when a genuinely new broadcast
 * airs (renderCard is only ever called on a due 30-min refresh, never on a
 * manual reopen of the same content). Purely a visual sting: a flashing
 * red banner + a quick zoom/flicker on the card itself, like a channel
 * actually cutting to a report. No sound (browsers block autoplay audio
 * anyway, and it would be jarring unprompted) -- real voice stays behind
 * the explicit 🔊 click, same as before.
 */
function renderCard(container, script) {
  const weatherEmoji = script.weather === 'sun' ? '☀️' : script.weather === 'rain' ? '🌧️' : '⛅';
  // per-line, a compact speaker tag rather than a repeated portrait -- the
  // one shared booth above already establishes who's who; this transcript
  // just needs to say who's talking, like a real chyron.
  const linesHtml = script.lines.map(l => `
    <div class="nb-line nb-${l.a}">
      <span class="nb-tag nb-tag-${l.a}">${l.a === 'bull' ? 'BULL' : 'BEAR'}</span>
      <span class="nb-bubble"><span class="nb-emoji">${l.emoji}</span>${escapeHtml(l.text)}</span>
    </div>`).join('');

  container.innerHTML = `
    <div class="nb-tab" id="nbTab">📺 NEWS <span class="nb-ago" id="nbAgo">now</span></div>
    <div class="nb-card nb-${script.weather} nb-entering" id="nbCard">
      <div class="nb-breaking" id="nbBreaking"><span class="dot"></span>BREAKING · DESK UPDATE<span class="dot"></span></div>
      <div class="nb-head">
        <span class="nb-title">Bull &amp; Bear Desk Report ${weatherEmoji}</span>
        <span class="nb-onair"><span class="dot"></span>LIVE</span>
        <button class="nb-close" id="nbClose" title="Minimize">–</button>
      </div>
      <div class="nb-booth">${boothSvg()}</div>
      <div class="nb-body">${linesHtml}</div>
      <div class="nb-foot">
        <span>Fictional anchors, real desk data · every 30 min</span>
        <button class="nb-voice" id="nbVoice" title="Play as a short -- real ElevenLabs voices read each line aloud">🔊</button>
      </div>
    </div>`;

  document.getElementById('nbTab').onclick = () => toggleBulletin(container);
  document.getElementById('nbClose').onclick = e => { e.stopPropagation(); collapseBulletin(container); };
  document.getElementById('nbVoice').onclick = e => {
    e.stopPropagation();
    playAsShort(script, container);
  };

  // clean the one-shot animation classes/elements off once they've played,
  // so they don't linger or replay on the next unrelated DOM touch
  const card = document.getElementById('nbCard');
  setTimeout(() => card && card.classList.remove('nb-entering'), 700);
  setTimeout(() => document.getElementById('nbBreaking')?.remove(), 1700);
}

function openBulletin(container) {
  container.classList.remove('collapsed');
  scheduleAutoCollapse(container);
}
function collapseBulletin(container) {
  if (playing) return;   // don't tuck the short away mid-narration
  container.classList.add('collapsed');
  clearTimeout(collapseTimer);
}
function toggleBulletin(container) {
  container.classList.contains('collapsed') ? openBulletin(container) : collapseBulletin(container);
}
function scheduleAutoCollapse(container) {
  clearTimeout(collapseTimer);
  collapseTimer = setTimeout(() => collapseBulletin(container), AUTO_COLLAPSE_MS);
}
function updateAgoLabel() {
  const el = document.getElementById('nbAgo');
  if (!el) return;
  const mins = Math.round((Date.now() - lastBroadcastAt) / 60000);
  el.textContent = mins < 1 ? 'now' : `${mins}m ago`;
}

/**
 * Real voice playback, shorts-style: plays each anchor line's REAL audio
 * (fetched from this app's own POST /api/tts -- the ElevenLabs key never
 * reaches the browser, see dashboard_server.py's handle_tts) in sequence,
 * highlighting the caption currently being spoken like a short's burned-in
 * captions. Click again mid-playback to stop. A real fetch/playback error
 * is shown inline in the footer -- never swallowed, never faked.
 */
let playing = false;
let currentAudio = null;

async function fetchLineAudio(line) {
  const res = await fetch('/api/tts', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text: line.text, voice: line.a })
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    throw new Error(err.error || `Voice request failed (${res.status})`);
  }
  return res.blob();
}

function playBlob(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const audio = new Audio(url);
    currentAudio = audio;
    audio.onended = () => { URL.revokeObjectURL(url); resolve(); };
    audio.onerror = () => { URL.revokeObjectURL(url); reject(new Error('Playback failed')); };
    audio.play().catch(reject);
  });
}

function setFooterStatus(container, text) {
  const el = container.querySelector('.nb-foot span');
  if (el) el.textContent = text;
}

async function playAsShort(script, container) {
  const voiceBtn = document.getElementById('nbVoice');
  if (playing) {
    playing = false;
    if (currentAudio) currentAudio.pause();
    if (voiceBtn) voiceBtn.textContent = '🔊';
    setFooterStatus(container, 'Fictional anchors, real desk data · every 30 min');
    container.querySelectorAll('.nb-line').forEach(el => el.classList.remove('nb-active'));
    return;
  }
  playing = true;
  if (voiceBtn) voiceBtn.textContent = '⏹';
  const lineEls = [...container.querySelectorAll('.nb-line')];
  for (let i = 0; i < script.lines.length && playing; i++) {
    lineEls.forEach((el, idx) => el.classList.toggle('nb-active', idx === i));
    lineEls[i] && lineEls[i].scrollIntoView({ block: 'nearest' });
    try {
      setFooterStatus(container, 'Speaking…');
      const blob = await fetchLineAudio(script.lines[i]);
      if (!playing) break;
      await playBlob(blob);
    } catch (err) {
      setFooterStatus(container, `Voice error: ${err.message}`);
      break;
    }
  }
  playing = false;
  if (voiceBtn) voiceBtn.textContent = '🔊';
  lineEls.forEach(el => el.classList.remove('nb-active'));
  if (!container.querySelector('.nb-foot span').textContent.startsWith('Voice error')) {
    setFooterStatus(container, 'Fictional anchors, real desk data · every 30 min');
  }
}

/**
 * Called on every poll (~10s), same as the wall display. Internally gates
 * on the real 30-minute broadcast cadence -- most calls just refresh the
 * "Xm ago" label; only once every 30 min does it regenerate the script and
 * pop the bulletin open.
 */
export function updateNewsBulletin(s) {
  const container = document.getElementById('newsBulletin');
  if (!container) return;

  const due = lastScript === null || (Date.now() - lastBroadcastAt) >= BROADCAST_INTERVAL_MS;
  if (due) {
    lastScript = buildScript(s);
    lastBroadcastAt = Date.now();
    renderCard(container, lastScript);
    openBulletin(container);
  } else {
    updateAgoLabel();
  }
}
