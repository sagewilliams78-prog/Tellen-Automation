/**
 * Real bot state -> what a character shows and where it stands.
 *
 * Every branch below is driven by a field the bot actually publishes. There
 * is no random behaviour and no invented activity: if the bot is offline,
 * characters say so rather than miming work.
 *
 * Levels: ok | watch | warn | alert | idle | offline
 */

import { symbols, isMarketClosed, activeMechanic, riskFlags,
         studioShift, taskForStage, store, recentWatchlistChange, todaysPnl, totalPnl } from '../state/store.js';
import { isDark, currentSession } from '../world/lighting.js';
import { baristaState } from './complaints.js';
import { DESK_COUNT } from './roster.js';

export const LEVEL_COLOR = {
  ok:      '#4fbf6a',
  watch:   '#e8c15a',
  warn:    '#e08b3c',
  alert:   '#e0503c',
  idle:    '#8d8577',
  offline: '#6a6a72'
};

const short = (s, n = 30) => (s && s.length > n ? s.slice(0, n - 1) + '…' : (s || ''));

/* ---------------- Eva ---------------- */

function evaState(s) {
  if (!s) return { level: 'offline', bubble: 'No data', detail: 'Dashboard has no state yet.' };
  if (!s.bot_alive) {
    return { level: 'offline', bubble: 'Offline', goto: { home: 7 },
             detail: "The bot's log has not been written to in over 3 minutes." };
  }
  const scan = s.scan || {};
  const firing = symbols(s).find(x => x.entry_flag);
  if (firing) {
    return { level: 'alert', bubble: `⚡ Entry: ${firing.symbol}`,
             goto: { symbolSlot: symbolSlotOf(s, firing.symbol) },
             detail: `Entry conditions met on ${firing.symbol} at $${firing.price}.` };
  }
  if (isMarketClosed(s)) {
    return { level: 'idle', bubble: 'Market closed', goto: { home: 7 },
             detail: 'Outside the entry window. No new positions.' };
  }
  const managed = scan.managed || 0;
  if (managed > 0) {
    return { level: 'watch', bubble: `Managing ${managed}`,
             detail: `${managed} open position(s) being managed to stop or target.` };
  }
  return { level: 'ok', bubble: scan.scan_num ? `Scanning #${scan.scan_num}` : 'Scanning',
           detail: s.market_update || 'Scanning the watchlist.' };
}

/** How many symbols one desk covers, at most. Each trader watches a small
 *  basket rather than a single ticker, so a desk is only truly idle when
 *  ALL of its symbols are out -- which is much rarer than any one being out. */
export const SYMBOLS_PER_DESK = 3;

/**
 * Desk assignment is ROUND-ROBIN over the real desk count (symbol index %
 * DESK_COUNT), not sequential chunking (index / SYMBOLS_PER_DESK).
 *
 * Sequential chunking front-loads: with 7 real symbols and 3-per-desk, desks
 * 0-2 got everything and desks 3-6 sat empty -- not "once the list grows
 * past 9," but immediately, with the ORIGINAL 7-symbol watchlist, before any
 * widening happened at all. Round-robin uses every desk that exists as soon
 * as there are that many symbols: at 7 symbols, all 7 desks get exactly one;
 * only past 7 does any desk start covering more than one, and only past 21
 * (DESK_COUNT * SYMBOLS_PER_DESK) does the room genuinely run out of room.
 */
function symbolSlotOf(s, sym) {
  const i = symbols(s).findIndex(x => x.symbol === sym);
  return i < 0 ? -1 : i % DESK_COUNT;
}

/** The symbols one desk is responsible for. */
export function deskSymbols(s, slot) {
  return symbols(s).filter((_, i) => i % DESK_COUNT === slot);
}

/**
 * Which of a desk's symbols to put on the sign: whatever is most
 * actionable right now. An entry beats a buy zone, a buy zone beats
 * "close to the zone", and a symbol disqualified by the zone-width filter
 * loses to anything still live.
 */
export function mostActionable(list) {
  if (!list.length) return null;
  const live = list.filter(x => !x.narrow);
  const pool = live.length ? live : list;
  const entry = pool.find(x => x.entry_flag);
  if (entry) return entry;
  const buy = pool.find(x => x.zone === 'BUY');
  if (buy) return buy;
  return pool.reduce((a, b) => {
    const da = a.distance_pct == null ? Infinity : Math.abs(a.distance_pct);
    const db = b.distance_pct == null ? Infinity : Math.abs(b.distance_pct);
    return db < da ? b : a;
  });
}

/* ---------------- watchlist symbols ---------------- */

function symbolState(s, slot) {
  const group = deskSymbols(s, slot);
  const x = mostActionable(group);

  // Off the clock: the bot is down or the entry window has closed, so the
  // desks are empty and everyone is at home. This is a real state, not
  // decoration -- it mirrors bot_alive / market_closed exactly.
  if (!s || !s.bot_alive) {
    return { name: x ? x.symbol : null, level: 'offline', bubble: '🏠 Off the clock',
             goto: { home: slot },
             detail: 'Bot is not running — no live quote for this symbol.' };
  }
  if (isMarketClosed(s)) {
    return { name: x ? x.symbol : null, level: 'idle', bubble: '🏠 Home',
             goto: { home: slot },
             detail: 'Entry window closed for the day.' };
  }
  if (!x) {
    return { name: null, level: 'idle', bubble: 'No symbol',
             detail: 'No symbol is assigned to this desk right now.' };
  }
  const price = `$${Number(x.price).toFixed(2)}`;
  const dist = x.distance_pct != null ? `${x.distance_pct.toFixed(1)}% away` : '';

  // A desk quietly becoming a different ticker overnight is exactly what
  // the nightly screener does, and it used to be invisible. If this symbol
  // was genuinely added in the last few days -- per watchlist_manager's own
  // history, not a guess -- the desk says so.
  const change = recentWatchlistChange(s, 3);
  const isNew = change.added.includes(x.symbol);
  const newNote = isNew ? ' · new to the watchlist' : '';

  // Intelligence layer: each branch reads as one clear, complete sentence
  // explaining what is ACTUALLY true right now, built from the same real
  // zone/price/flag fields as before -- no new data, just written to be
  // understood at a glance rather than assembled from price/dist fragments.
  if (x.entry_flag) {
    return { name: x.symbol, level: 'alert', bubble: '⚡ Entry!', isNew,
             detail: `Entry triggered on ${x.symbol} at ${price}.${isNew ? ' This symbol is new to the watchlist.' : ''}` };
  }
  if (x.narrow) {
    return { name: x.symbol, level: 'idle', bubble: '😴 Sitting out', isNew,
             detail: `Watching ${x.symbol} at ${price}, but today's range is too narrow to trust — sitting this one out.${isNew ? ' New to the watchlist.' : ''}` };
  }
  if (x.zone === 'BUY') {
    return { name: x.symbol, level: 'ok', bubble: '📈 In Buy Zone', isNew,
             detail: `Watching ${x.symbol} at ${price}. Price is inside the configured buy zone, but a bullish confirmation candle hasn't printed yet.${isNew ? ' New to the watchlist.' : ''}` };
  }
  if (x.zone === 'SELL') {
    return { name: x.symbol, level: 'watch', bubble: `📉 ${dist || 'Above zone'}`, isNew,
             detail: `Watching ${x.symbol} at ${price}, ${dist ? `currently ${dist} above the buy zone` : 'above the buy zone'} — no entry until it comes back in range.${isNew ? ' New to the watchlist.' : ''}` };
  }
  return { name: x.symbol, level: 'watch', bubble: isNew ? '✨ New here' : (dist || 'Waiting'), isNew,
           detail: `Watching ${x.symbol} at ${price}, sitting between the buy and sell zones${dist ? ` (${dist})` : ''}.${isNew ? ' New to the watchlist.' : ''}` };
}

/* ---------------- risk ---------------- */

function riskState(def, s) {
  if (!s) return { level: 'offline', bubble: 'No data', detail: '' };
  const f = riskFlags(s);
  if (f.paused) {
    return { level: 'alert', bubble: '⚠ Entries paused',
             detail: `No new positions permitted. Weekly win-rate breaker is active: ${f.weekly}` };
  }
  if (f.blackout.length) {
    return { level: 'warn', bubble: `⚠ ${f.blackout.length} blackout`,
             detail: `${f.blackout.length} symbol${f.blackout.length === 1 ? ' is' : 's are'} blocked on an earnings blackout: ${f.blackout.join(', ')}. No new entries there until it clears.` };
  }
  if (!s.bot_alive) return { level: 'offline', bubble: 'Off duty', goto: { home: def.homeSlot },
                             detail: 'The bot is not running, so there is nothing to gate right now.' };
  return { level: 'ok', bubble: '✓ All clear',
           detail: f.weekly ? `No entries currently blocked. ${f.weekly}` : 'No risk blocks are active — full watchlist is eligible.' };
}

/* ---------------- mechanic ---------------- */

function mechanicState(def, s) {
  const m = activeMechanic(s);
  if (!m) return { level: 'idle', bubble: 'No checks yet', detail: 'No health check has run today.' };
  const when = m.last_run ? new Date(m.last_run).toLocaleTimeString([], {hour:'2-digit', minute:'2-digit'}) : null;
  if (m.status === 'needs_attention') {
    return { level: 'alert', bubble: '⚠ Needs attention',
             detail: `Real problem found${when ? ` at the ${when} check` : ''}: ${m.summary || 'no summary given'}` };
  }
  if (m.status === 'fixed') {
    return { level: 'warn', bubble: '🔧 Fixed an issue',
             detail: `Found and resolved a problem${when ? ` at ${when}` : ''}: ${m.summary || 'no summary given'}` };
  }
  if (s && !s.bot_alive) {
    return { level: 'idle', bubble: 'Off duty', goto: { home: def.homeSlot },
             detail: short(m.summary, 120) };
  }
  return { level: 'ok', bubble: '✓ Healthy',
           detail: `Last check${when ? ` at ${when}` : ''} came back healthy. ${short(m.summary, 100)}` };
}

/* ---------------- archive studio ---------------- */

// Which stages each studio character actually covers. Rafa runs the back half
// of the pipeline, so he owns more than one -- this mirrors the roster's
// `binds` field and the STAGE_WORK table in studio.py.
const STUDIO_STAGES = {
  archivist:   ['research'],
  factchecker: ['factcheck'],
  writer:      ['script'],
  editor:      ['shotlist', 'video', 'audio', 'packaging', 'publish'],
};

/**
 * A studio character's state.
 *
 * The studio works the SAME shift as the trading floor -- in at 09:00 ET,
 * out at 16:00 ET, weekdays -- so off-shift they head home exactly like the
 * traders do. On shift, their bubble is the real outstanding task for a stage
 * they own, taken from /api/studio, which derives it from files that actually
 * exist on disk. When every stage they own has real file evidence, they are
 * genuinely done, and that is what they say.
 */
function studioState(def) {
  const shift = studioShift();
  const stages = STUDIO_STAGES[def.id] || [];

  // Studio unreachable -- unknown, never invented.
  if (!shift) {
    return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  }

  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Clocked out';
    return {
      level: 'idle',
      bubble: `🌙 ${when}`,
      goto: { home: def.homeSlot ?? 0 },
      detail: `Off shift. The studio keeps the trading floor's hours — ` +
              `${shift.opens_et}–${shift.closes_et} ET, weekdays. Now ${shift.now_et} ET.`
    };
  }

  const task = stages.map(taskForStage).find(Boolean);
  if (!task) {
    return { level: 'ok', bubble: '✓ Nothing blocking',
             detail: 'Every stage this desk owns has a real file backing it.' };
  }
  return {
    level: 'work',
    bubble: `📝 ${task.what}`,
    name: task.project,
    detail: `${task.project} — ${task.what}. ${task.evidence}. ` +
            `${task.progress || ''}`.trim()
  };
}

/* ---------------- Sage's ATM Co. ---------------- */

function atmState(def) {
  const atm = store.atm;
  if (!atm) return { level: 'idle', bubble: '', detail: 'ATM Co. state not loaded yet.' };

  // Wes keeps the studio's hours now that he has an actual home to go to --
  // off shift he heads there like everyone else, rather than standing at
  // his desk around the clock.
  const shift = studioShift();
  if (shift && !shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Clocked out';
    return {
      level: 'idle', bubble: `🌙 ${when}`, goto: { home: def ? def.homeSlot : 14 },
      detail: `Off shift. Now ${shift.now_et} ET.`
    };
  }

  if (atm.launched) {
    return { level: 'ok', bubble: '✓ Launched', detail: 'All six real steps are done.' };
  }
  const next = atm.steps.find(s => !s.done);
  const perm = atm.permission && atm.permission.granted;
  const permNote = perm ? '' : ' · no permission to work on his own yet';
  return {
    level: 'work',
    bubble: next ? `${atm.done_count}/${atm.total_steps} · ${next.title}` : `${atm.done_count}/${atm.total_steps}`,
    detail: (next ? `${next.title} — ${next.what}` : 'Checklist state unclear.') + permNote
  };
}

/* ---------------- Smallville General ---------------- */

/**
 * The two doctors. Purely ambient -- the hospital has no real subsystem
 * behind it (see hq-map.js's own comment on HOSPITAL). They keep the same
 * shift as everyone else; off shift they head home, same as any other
 * character, EXCEPT the actual journey is a car commute handled entirely by
 * world/commute.js -- while that's in progress this never runs at all (see
 * the `_commuting` early-exit in main.js's applyState()).
 */
function doctorState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Hospital state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Clocked out';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET. Commutes by car -- see the parking lot.` };
  }
  return { level: 'ok', bubble: 'On shift',
           detail: 'Smallville General -- ambient only, no real hospital data behind this.' };
}

/* ---------------- The News Desk ---------------- */

/**
 * Bull & Bear, standing at their desks. Purely ambient, exactly like the
 * doctors -- see hq-map.js's NEWS_STUDIO comment. Same shift as the trading
 * floor and the Archive Studio (studioShift()); off shift they walk home
 * like anyone else. The REAL bulletin -- the sarcastic script read from
 * real /api/status fields -- lives entirely in ui/newsbulletin.js and pops
 * up on its own 30-minute cadence, independent of whether these two are
 * physically at their desk. Standing here is flavor, not a second data feed.
 */
function newsState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Off air';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }
  return { level: 'ok', bubble: '🔴 On air',
           detail: 'The News Desk -- ambient only. The real bulletin (top-right of the screen) reads real bot data every 30 min.' };
}

/* ---------------- The Field Office ---------------- */

/**
 * Voss & Ito's real job: real permission checks on the real secret files
 * this app and the live bot depend on (dashboard_server.py's
 * build_security_status() -- three plain os.stat() calls, nothing
 * fabricated). This is the one place in the Field Office that isn't
 * decoration -- everything else about the room is (see hq-map.js's
 * FIELD_OFFICE comment). Same trading-floor shift as everyone else in this
 * building cluster; off shift they go home like anyone else.
 */
function securityState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Off duty';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }

  const sec = store.security;
  if (!sec) {
    return { level: 'idle', bubble: '⏳ Checking…', detail: 'Security check not loaded yet.' };
  }
  if (sec.all_clear) {
    return {
      level: 'ok', bubble: '🟢 All secrets secured',
      detail: `${sec.checks.length} real secret file${sec.checks.length === 1 ? '' : 's'} checked -- ` +
              `every one owner-only (600). Real check, see dashboard_server.py's build_security_status().`
    };
  }
  const bad = sec.checks.filter(c => !c.ok);
  const worst = bad[0];
  return {
    level: 'alert', bubble: `🚨 ${worst.label} exposed`,
    detail: `${bad.length} real finding${bad.length === 1 ? '' : 's'}: ` +
            bad.map(c => `${c.label} -- ${c.detail}`).join('; ')
  };
}

/* ---------------- The Bank ---------------- */

/**
 * Marnie's real number: today's real P&L (todaysPnl(), server-computed from
 * the real trade log -- same function the mission-control wall display
 * uses). The room's real substance is the click-through panel
 * (ui/panels.js's bankSection, with the equity curve, daily P&L and
 * win/loss record) -- this is just her status bubble, kept honest the same
 * way rather than left as pure flavor.
 */
function bankState(def, s) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Closed for the day';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }
  const trades = (s && s.todays_trades) || [];
  if (!trades.length) {
    return { level: 'idle', bubble: '📋 Balancing the books', detail: 'No trades logged yet today.' };
  }
  const pnl = todaysPnl(s);
  const m = (pnl < 0 ? '-$' : '+$') + Math.abs(pnl).toFixed(2);
  return {
    level: pnl >= 0 ? 'ok' : 'warn', bubble: `${pnl >= 0 ? '💰' : '🔻'} ${m} today`,
    detail: `${trades.length} trade(s) logged today. Real number -- todaysPnl(), same as the wall display.`
  };
}

/* ---------------- The Tax Office ---------------- */

/**
 * Percy's real number: the real all-time realized total (totalPnl(), the
 * same server-derived function the Bank and the wall display use) --
 * deliberately never a rate, bracket, or liability. The room's real
 * substance is the click-through panel (ui/panels.js's taxSection: the
 * real trade-by-trade ledger, clearly labeled "not tax advice").
 */
function taxState(def, s) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Closed for the day';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }
  const curve = (s && s.equity_curve) || [];
  if (!curve.length) {
    return { level: 'idle', bubble: '🗂️ Filing', detail: 'No completed trades logged yet.' };
  }
  const total = totalPnl(s);
  const m = (total < 0 ? '-$' : '+$') + Math.abs(total).toFixed(2);
  return {
    level: 'idle', bubble: `🗂️ Ledger: ${m} all-time`,
    detail: `${curve.length} completed trade(s) on record. Real number -- totalPnl(). Not tax advice.`
  };
}

/* ---------------- The Prediction Desk ---------------- */

/**
 * Fay's real number: the last real snapshot pulled from Sage's actual
 * Robinhood prediction-market account (predict_business.py). Unlike every
 * other financial desk here, there is no live bot feeding this -- it only
 * ever changes when Sage asks Claude to pull a fresh one via the Robinhood
 * MCP tools. The bubble and panel both say how old the snapshot is rather
 * than implying it's current.
 */
function predictState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Closed for the day';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }
  const p = store.predict;
  if (!p || !p.loaded) {
    return { level: 'idle', bubble: '🔮 No snapshot yet',
             detail: 'Nobody has asked Claude to pull a real Robinhood prediction-market snapshot yet.' };
  }
  const net = p.trades.net_realized;
  const m = (net < 0 ? '-$' : '+$') + Math.abs(net).toFixed(2);
  return {
    level: net >= 0 ? 'ok' : 'warn',
    bubble: `🔮 ${m} · ${p.trades.count} settled`,
    detail: `Snapshot as of ${new Date(p.as_of).toLocaleString()}. Not live -- refreshed only when asked.`
  };
}

/* ---------------- ambient filler (Eastside + park/store regulars) ------- */

/**
 * The 45 purely-ambient characters (Milo/Nadia/Reed/Theo/Greta plus the 40
 * Eastside residents) had no day/night cycle at all until now -- they just
 * stood at their own front door forever, since nothing ever populated
 * `goto`. This gives them the same real studio-hours rhythm as everyone
 * else (home at night, same as Bull/Bear/Wes/Fay); during open hours it
 * hands off to world/wander.js, which actually walks idle ones to a real
 * waypoint (a shop, a neighbour's door, the airport) and back.
 */
function ambientState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: '' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Turning in for the night';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot }, detail: 'Off for the night.' };
  }
  return { level: 'idle', bubble: '', detail: 'Out and about -- see world/wander.js.' };
}

/* ---------------- Smallville Regional (the airport) ---------------- */

/**
 * Dana's real number: whether a real, confirmed flight exists -- never a
 * marketing or abandoned-cart search email. The first real check (Gmail,
 * via Claude) found 15+ CheapOair "still thinking about Nashville?" nags
 * for a search Sage never finished booking -- that is explicitly NOT a
 * flight, and this never presents it as one. No live polling: same
 * refresh-on-request discipline as the Prediction Desk.
 */
function airportState(def) {
  const shift = studioShift();
  if (!shift) return { level: 'idle', bubble: '', detail: 'Studio state not loaded yet.' };
  if (!shift.open) {
    const when = shift.phase === 'weekend' ? 'Back Monday'
               : shift.phase === 'before'  ? 'In at 09:00 ET'
               : 'Closed for the day';
    return { level: 'idle', bubble: `🌙 ${when}`, goto: { home: def.homeSlot },
             detail: `Off shift. Now ${shift.now_et} ET.` };
  }
  const a = store.airport;
  if (!a || !a.loaded || !a.flights || !a.flights.length) {
    return { level: 'idle', bubble: '🛫 No upcoming flights',
             detail: (a && a.note) || 'No real confirmed flight found in Gmail -- marketing/abandoned-cart emails do not count.' };
  }
  const next = a.flights[0];
  return {
    level: 'ok',
    bubble: `🛫 ${next.route || next.destination || 'flight'} · ${next.date || ''}`,
    detail: `Checked ${new Date(a.as_of).toLocaleString()}. Not live -- refreshed only when asked.`
  };
}

/* ---------------- The Crypto Desk ---------------- */

/**
 * Nix's real state, straight from crypto-status.json (written every 60s by
 * crypto_btc_monitor.py). Unlike the ambient characters, every branch here is
 * a real fact about a real position and a real leash:
 *   - halted / kill switch    -> the desk is genuinely stopped
 *   - a position              -> real BTC is really held, with real unrealized P&L
 *   - flat                    -> genuinely flat, and why no entry fired
 * She never goes home: BTC has no close, so the desk runs around the clock.
 * That is not decoration -- the process really does run 24/7.
 */
function cryptoState(def) {
  const c = store.crypto;
  if (!c) {
    return { level: 'idle', bubble: '', detail: 'Crypto desk state not loaded yet.' };
  }
  const s = c.state || c;
  const desk = s.desk || {};
  const price = s.price != null ? `$${Number(s.price).toLocaleString()}` : '—';

  if (!s.mcp_connected) {
    return { level: 'offline', bubble: '🔌 Disconnected',
             detail: 'The crypto desk cannot reach Robinhood right now.' };
  }

  const pos = desk.position;
  if (pos) {
    const up = Number(pos.change_pct);
    return {
      level: up >= 0 ? 'ok' : 'warn',
      bubble: `₿ ${up >= 0 ? '+' : ''}${up.toFixed(2)}%`,
      detail: `Holding ${Number(pos.quantity).toFixed(6)} BTC from ` +
              `$${Number(pos.entry).toLocaleString()} — now ${price}, ` +
              `unrealized ${pos.unrealized < 0 ? '-$' : '+$'}` +
              `${Math.abs(pos.unrealized).toFixed(2)}, held ${pos.held_hours}h. ` +
              `Stop ${s.leash ? s.leash.stop_pct : '?'}%, target ` +
              `${s.leash ? s.leash.target_pct : '?'}%.`
    };
  }

  if (desk.halted) {
    const killed = /kill switch/i.test(desk.halt_reason || '');
    return {
      level: killed ? 'alert' : 'warn',
      bubble: killed ? '🛑 Halted' : '⏸ Paused',
      detail: `${desk.halt_reason || 'Halted.'} BTC ${price}.`
    };
  }

  return {
    level: 'idle',
    bubble: `₿ ${price} · flat`,
    detail: `${desk.halt_reason || 'Watching for a setup.'} ` +
            `BTC ${price}, RSI ${s.rsi14}, ${s.trend}. ` +
            `Today: ${desk.day_trades || 0} trade(s), ` +
            `realized ${(desk.day_realized_pnl || 0) < 0 ? '-$' : '+$'}` +
            `${Math.abs(desk.day_realized_pnl || 0).toFixed(2)}.`
  };
}

/* ---------------- dispatcher ---------------- */

export function resolve(agentDef, s) {
  if (agentDef.id === 'eva') return evaState(s);
  if (agentDef.id === 'risk') return riskState(agentDef, s);
  if (agentDef.id === 'mechanic') return mechanicState(agentDef, s);
  if (agentDef.id === 'atmops') return atmState();
  if (agentDef.hospital) return doctorState(agentDef);
  if (agentDef.studio) return studioState(agentDef);
  if (agentDef.news) return newsState(agentDef);
  if (agentDef.security) return securityState(agentDef);
  if (agentDef.crypto) return cryptoState(agentDef);
  if (agentDef.bank) return bankState(agentDef, s);
  if (agentDef.tax) return taxState(agentDef, s);
  if (agentDef.predict) return predictState(agentDef);
  if (agentDef.airport) return airportState(agentDef);
  if (agentDef.ambient) return ambientState(agentDef);
  if (agentDef.id === 'barista') {
    const b = baristaState(s);
    // Sal lives above the shop. Once it is dark she closes up and goes up.
    const home = isDark(currentSession())
      ? { home: agentDef.homeSlot ?? 13 } : null;
    return { level: b.level, bubble: home ? '🌙 Closed up' : b.bubble,
             goto: home || undefined,
             detail: `${b.count} item(s) pinned to the board right now.` };
  }
  if (agentDef.slot != null) return symbolState(s, agentDef.slot);
  return { level: 'idle', bubble: '', detail: '' };
}
