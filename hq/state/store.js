/**
 * The single source of truth for the city: the bot's own /api/status.
 *
 * This layer ONLY reads. It performs no broker calls, places no orders, and
 * invents nothing -- every field below comes straight out of the live bot's
 * log and CSVs. When the bot is offline or a field is missing, that is
 * reported as unknown rather than filled in with a plausible-looking value.
 */

const ENDPOINT = '/api/status';
const STUDIO_ENDPOINT = '/api/studio';
const ATM_ENDPOINT = '/api/atm';
const SIM_ENDPOINT = '/api/sim';
const SECURITY_ENDPOINT = '/api/security';
const CRYPTO_ENDPOINT = '/api/crypto';
const PREDICT_ENDPOINT = '/api/predictions';
const AIRPORT_ENDPOINT = '/api/airport';

export const store = {
  raw: null,
  /** Archive Studio state -- its own endpoint, its own files, its own shift. */
  studio: null,
  /** Sage's ATM Co. -- its own endpoint, a real (currently all-false) checklist. */
  atm: null,
  /** The town's make-believe economy. FICTION -- see sim_economy.py's header.
   *  Kept in its own field precisely so it can never be mistaken for the
   *  real P&L that lives in `raw`. */
  sim: null,
  /** REAL, live: real secret-file permission checks -- see
   *  dashboard_server.py's build_security_status(). Drives Voss & Ito's
   *  actual job (agents/activity.js's securityState) -- the one place in
   *  the Field Office that isn't just decoration. */
  security: null,
  /** REAL, but NOT live: the last snapshot Claude pulled from Sage's actual
   *  Robinhood prediction-market account, via predict_business.py. No bot
   *  feeds this -- it only changes when Sage asks for a fresh pull. */
  predict: null,
  lastOk: null,
  error: null,
  studioError: null,
  atmError: null,
  listeners: new Set(),

  subscribe(fn) { this.listeners.add(fn); return () => this.listeners.delete(fn); },

  emit() { for (const fn of this.listeners) fn(this.raw, this); },

  async refresh() {
    // Three separate businesses plus the town's fictional economy, fetched
    // independently -- none of them can break any of the others.
    const [botRes, studioRes, atmRes, simRes, securityRes, cryptoRes, predictRes, airportRes] = await Promise.allSettled([
      fetch(ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`status ${r.status}`);
        return r.json();
      }),
      fetch(STUDIO_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`studio ${r.status}`);
        return r.json();
      }),
      fetch(ATM_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`atm ${r.status}`);
        return r.json();
      }),
      fetch(SIM_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`sim ${r.status}`);
        return r.json();
      }),
      fetch(SECURITY_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`security ${r.status}`);
        return r.json();
      }),
      // The 24/7 crypto desk -- its own process, its own cadence, so it is
      // fetched independently like every other business here. A dead crypto
      // desk must never blank out the equity floor.
      fetch(CRYPTO_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`crypto ${r.status}`);
        return r.json();
      }),
      // The Prediction Desk -- a snapshot, not a live feed, fetched
      // independently like every other business here so a missing one
      // never blanks out the rest of the city.
      fetch(PREDICT_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`predictions ${r.status}`);
        return r.json();
      }),
      // Smallville Regional -- a real Gmail-checked flight status, not a
      // live feed (no airline publishes a public live API for one
      // traveller's inbox). Fetched independently like every other
      // business here.
      fetch(AIRPORT_ENDPOINT, { cache: 'no-store' }).then(r => {
        if (!r.ok) throw new Error(`airport ${r.status}`);
        return r.json();
      })
    ]);

    if (cryptoRes.status === 'fulfilled') {
      this.crypto = cryptoRes.value;
      this.cryptoError = null;
    } else {
      this.cryptoError = cryptoRes.reason.message;
    }

    if (botRes.status === 'fulfilled') {
      this.raw = botRes.value;
      this.lastOk = Date.now();
      this.error = null;
    } else {
      this.error = botRes.reason.message;
    }

    if (studioRes.status === 'fulfilled') {
      this.studio = studioRes.value;
      this.studioError = null;
    } else {
      this.studioError = studioRes.reason.message;
    }

    if (atmRes.status === 'fulfilled') {
      this.atm = atmRes.value;
      this.atmError = null;
    } else {
      this.atmError = atmRes.reason.message;
    }

    if (simRes.status === 'fulfilled') this.sim = simRes.value;
    if (securityRes.status === 'fulfilled') this.security = securityRes.value;
    if (predictRes.status === 'fulfilled') this.predict = predictRes.value;
    if (airportRes.status === 'fulfilled') this.airport = airportRes.value;

    this.emit();
  },

  start(ms = 10000) {
    this.refresh();
    setInterval(() => this.refresh(), ms);
  }
};

/* ---------- derived helpers, all from real fields ---------- */

export function symbols(s) {
  return (s && s.scan && s.scan.symbols) ? s.scan.symbols : [];
}

export function isMarketClosed(s) {
  if (!s || !s.scan) return null;                 // unknown, not "closed"
  return s.scan.market_closed === true || s.scan.window_closed === true;
}

/** The mechanic run we should display: the most recent real check on record,
 *  across ALL of them -- not just hourly/morning. Fixed 2026-08-29: this
 *  only ever compared those two, so it silently never surfaced eva-live-scan's
 *  own real 'live_scan' check even after that key existed in /api/status.
 *  Reads whatever keys are actually present under s.mechanics rather than
 *  naming them, so a future mechanic needs no change here to show up. */
export function activeMechanic(s) {
  const m = (s && s.mechanics) || {};
  const checks = Object.values(m).filter(Boolean);
  if (!checks.length) return null;
  return checks.reduce((latest, c) =>
    new Date(c.last_run) >= new Date(latest.last_run) ? c : latest);
}

/** Every real mechanic check on record, most recent first -- for the
 *  activity log, which should show each one honestly rather than collapse
 *  them into a single "most recent" line. */
export function allMechanics(s) {
  const m = (s && s.mechanics) || {};
  const KIND_LABEL = { hourly: 'Hourly check', morning: 'Morning check', live_scan: 'Live scan check' };
  return Object.entries(m)
    .filter(([, v]) => v)
    .map(([k, v]) => ({ ...v, kind: KIND_LABEL[k] || k }))
    .sort((a, b) => new Date(b.last_run) - new Date(a.last_run));
}

export function riskFlags(s) {
  const blackout = (s && s.earnings_blackout) || [];
  const weekly = (s && s.weekly_status) || '';
  const paused = /pausing/i.test(weekly);
  return { blackout, weekly, paused, alerting: paused || blackout.length > 0 };
}

export function todaysPnl(s) {
  return ((s && s.todays_trades) || [])
    .reduce((t, x) => t + (parseFloat(x['P&L']) || 0), 0);
}

export function totalPnl(s) {
  const curve = (s && s.equity_curve) || [];
  if (curve.length) return curve[curve.length - 1].cumulative;
  // fallback when equity_curve hasn't loaded: recent_trades is capped at 10,
  // so this undercounts on an account with a longer history.
  return ((s && s.recent_trades) || [])
    .reduce((t, x) => t + (parseFloat(x['P&L']) || 0), 0);
}

/* ---------- the studio, on the trading floor's clock ---------- */

/**
 * The studio's shift, straight from the server (which computes it in market
 * time). The studio keeps the SAME hours as the bot: in at 09:00 ET, out at
 * 16:00 ET, weekdays. Returns null when the studio hasn't been reached yet --
 * unknown, not "closed".
 */
export function studioShift() {
  return (store.studio && store.studio.shift) || null;
}

/** True only when the studio is genuinely on shift right now. */
export function studioOnShift() {
  const sh = studioShift();
  return sh ? sh.open === true : false;
}

/** The studio's task board -- real pipeline gaps, not invented work. */
export function studioTasks() {
  return (store.studio && store.studio.tasks) || [];
}

/**
 * The task a given studio character is working, matched by the stage their
 * roster entry binds to. Returns null when they have nothing outstanding.
 */
export function taskForStage(stage) {
  return studioTasks().find(t => t.stage === stage && t.state === 'todo') || null;
}

/* ---------- the watchlist, and how it has really changed ---------- */

export function watchlist(s) {
  return (s && s.watchlist) || null;
}

/** How many days ago a watchlist change happened, or null. */
function daysAgo(iso) {
  if (!iso) return null;
  const d = (Date.now() - new Date(iso).getTime()) / 86400000;
  return d >= 0 ? d : null;
}

/**
 * Symbols added or dropped within the last `days`, from the REAL history
 * watchlist_manager records. Used to mark a desk as a new arrival rather
 * than letting a ticker silently change overnight.
 */
export function recentWatchlistChange(s, days = 3) {
  const w = watchlist(s);
  if (!w || !w.history || !w.history.length) return { added: [], dropped: [], entries: [] };
  const entries = w.history.filter(h => {
    const d = daysAgo(h.when);
    return d != null && d <= days;
  });
  return {
    added: [...new Set(entries.flatMap(h => h.added || []))],
    dropped: [...new Set(entries.flatMap(h => h.dropped || []))],
    entries
  };
}

/* ---------- what actually went wrong lately ---------- */

/**
 * Real trouble signals from the bot's own daily journal and risk state.
 * Every item is something the bot genuinely recorded -- nothing here is
 * inferred sentiment or a made-up "health score".
 */
export function troubleSignals(s) {
  if (!s) return [];
  const out = [];
  const journal = s.recent_journal || [];

  const losing = journal.filter(d => parseFloat(d.PnL) < 0);
  if (losing.length) {
    const worst = losing.reduce((a, b) => (parseFloat(a.PnL) <= parseFloat(b.PnL) ? a : b));
    out.push({
      level: losing.length >= 3 ? 'alert' : 'warn',
      what: `${losing.length} losing day${losing.length > 1 ? 's' : ''} in the last ${journal.length}`,
      detail: `Worst: ${worst.Date} at ${money(parseFloat(worst.PnL))}`
    });
  }

  const paused = journal.filter(d => String(d.WeeklyPauseActive).toLowerCase() === 'true');
  if (paused.length) {
    out.push({ level: 'alert', what: `Weekly win-rate breaker fired on ${paused.length} day(s)`,
               detail: paused.map(d => d.Date).join(', ') });
  }

  const stillOpen = journal.filter(d => parseInt(d.StillOpenAtClose, 10) > 0);
  if (stillOpen.length) {
    out.push({ level: 'warn', what: `Position still open at the close on ${stillOpen.length} day(s)`,
               detail: stillOpen.map(d => `${d.Date} (${d.StillOpenAtClose})`).join(', ') });
  }

  const lowWr = journal.filter(d => parseInt(d.Trades, 10) >= 3 && parseFloat(d.WinRatePct) < 40);
  if (lowWr.length) {
    out.push({ level: 'warn', what: `Win rate under 40% on ${lowWr.length} day(s) with real volume`,
               detail: lowWr.map(d => `${d.Date} (${d.WinRatePct}%)`).join(', ') });
  }

  const f = riskFlags(s);
  if (f.blackout.length) {
    out.push({ level: 'watch', what: `Earnings blackout active`, detail: f.blackout.join(', ') });
  }
  return out;
}

const money = v => (v < 0 ? '-' : '+') + '$' + Math.abs(v).toFixed(2);

/* ---------- Sage's ATM Co. permission toggle ---------- */

/**
 * The ONLY way Wes's permission flag moves -- a real click in the pixel
 * city, posted straight to the server, which is the only thing allowed to
 * write permission.json. Refreshes the store afterward so every panel sees
 * the new state immediately.
 */
/* ---------- mission control: real aggregates, no new data sources ---------- */

/**
 * How many watchlist symbols are genuinely tradeable right now -- not
 * narrow-zone-excluded. This is "eligible," not "in a buy zone": it answers
 * "how many of today's symbols could possibly fire," which is what you want
 * at a glance, not a live entry count (that's the alert-level desks already).
 */
export function eligibleCount(s) {
  return symbols(s).filter(x => !x.narrow).length;
}

/** Real freshness: how long since this payload was generated, server-side. */
export function dataAgeSeconds(s) {
  if (!s || !s.generated_at) return null;
  return Math.max(0, (Date.now() - new Date(s.generated_at).getTime()) / 1000);
}

/**
 * Is the bot ACTUALLY supposed to be alive right now? Uses the real US
 * market clock (lighting.js), not a guess -- during 'open' or 'power' the
 * bot should be running; anything else (premarket/afterhours/night/closed)
 * and bot_alive=false is completely normal, not an incident.
 */
function duringMarketHours(session) {
  return session.key === 'open' || session.key === 'power';
}

/**
 * Real incident detection. Every reason here traces to a field already in
 * /api/status -- nothing invented, nothing guessed. An incident is active
 * only when something is ACTUALLY wrong, not merely off-hours.
 */
export function incidentState(s, session) {
  const reasons = [];
  if (!s) return { active: false, severity: 'none', reasons };

  if (!s.bot_alive && session && duringMarketHours(session)) {
    reasons.push({ id: 'bot_down', severity: 'alert',
      text: "Eva's log has gone stale during market hours — the bot may be down." });
  }
  const m = s.mechanics || {};
  const activeMech = (m.hourly && m.hourly.last_run) ? m.hourly : m.morning;
  if (activeMech && activeMech.status === 'needs_attention') {
    reasons.push({ id: 'mechanic_alert', severity: 'alert',
      text: `Mechanic flagged a real problem: ${activeMech.summary || 'no summary given'}` });
  }
  const weekly = (s.weekly_status || '').toUpperCase();
  if (weekly.includes('PAUSING')) {
    reasons.push({ id: 'weekly_breaker', severity: 'warn',
      text: `Weekly win-rate circuit breaker is active: ${s.weekly_status}` });
  }
  const age = dataAgeSeconds(s);
  if (age != null && age > 120 && session && duringMarketHours(session)) {
    reasons.push({ id: 'stale_payload', severity: 'warn',
      text: `Dashboard data is ${Math.round(age)}s old during market hours.` });
  }

  const severity = reasons.some(r => r.severity === 'alert') ? 'alert'
                 : reasons.length ? 'warn' : 'none';
  return { active: reasons.length > 0, severity, reasons };
}

export async function setAtmPermission(granted) {
  const res = await fetch('/api/atm/permission', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ granted: !!granted })
  });
  const d = await res.json();
  if (!d.ok) throw new Error(d.error || 'permission update failed');
  await store.refresh();
  return d.result;
}
