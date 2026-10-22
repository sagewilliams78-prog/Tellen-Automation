/**
 * Side panel + activity log.
 *
 * Panels are plain DOM overlaid on the canvas -- text selection, scrolling
 * and accessibility come free, and the world keeps the whole screen.
 * Everything rendered here is real data from /api/status.
 */

import { LEVEL_COLOR, deskSymbols, mostActionable, SYMBOLS_PER_DESK } from '../agents/activity.js';
import { DESK_COUNT } from '../agents/roster.js';
import { roomAt } from '../world/hq-map.js';
import { personFor } from '../agents/people.js';
import { complaints } from '../agents/complaints.js';
import { symbols, riskFlags, activeMechanic, allMechanics, todaysPnl, totalPnl,
         store, studioShift, setAtmPermission,
         watchlist, recentWatchlistChange, troubleSignals,
         eligibleCount, dataAgeSeconds } from '../state/store.js';

const el = id => document.getElementById(id);
const esc = s => String(s ?? '').replace(/[&<>"]/g, c =>
  ({ '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;' }[c]));

const money = v => (v < 0 ? '-' : '+') + '$' + Math.abs(v).toFixed(2);

function row(k, v) {
  return `<div class="row"><span>${esc(k)}</span><b>${esc(v)}</b></div>`;
}

/**
 * Cumulative P&L line chart, straight from /api/status's equity_curve
 * (one point per completed trade, in order -- server-computed, not
 * re-derived here). Green above zero, red below, matching LEVEL_COLOR.
 */
function equityCurveSvg(curve) {
  const W = 300, H = 84, pad = 6;
  if (!curve || curve.length < 2) {
    return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}">` +
           `<text x="${W / 2}" y="${H / 2}" fill="#6f6558" font-size="10" ` +
           `text-anchor="middle" dominant-baseline="middle">Not enough trades yet for a curve</text>` +
           `</svg></div>`;
  }
  const values = curve.map(p => p.cumulative);
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values);
  const range = (hi - lo) || 1;
  const x = i => pad + (i / (curve.length - 1)) * (W - pad * 2);
  const y = v => H - pad - ((v - lo) / range) * (H - pad * 2);
  const zeroY = y(0);
  const points = curve.map((p, i) => `${x(i).toFixed(1)},${y(p.cumulative).toFixed(1)}`).join(' ');
  const last = values[values.length - 1];
  const color = last >= 0 ? LEVEL_COLOR.ok : LEVEL_COLOR.alert;
  const areaPoints = `${x(0).toFixed(1)},${zeroY.toFixed(1)} ${points} ` +
                      `${x(curve.length - 1).toFixed(1)},${zeroY.toFixed(1)}`;
  return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}">` +
    `<line x1="${pad}" y1="${zeroY.toFixed(1)}" x2="${W - pad}" y2="${zeroY.toFixed(1)}" ` +
    `stroke="#3a3128" stroke-width="1" stroke-dasharray="3,3" />` +
    `<polygon points="${areaPoints}" fill="${color}" opacity="0.14" />` +
    `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="1.6" ` +
    `stroke-linejoin="round" stroke-linecap="round" />` +
    `</svg></div>`;
}

/**
 * Real per-day P&L, straight from /api/status's recent_journal (the bot's
 * own daily journal, already aggregated -- nothing re-derived here beyond
 * parsing the number and putting it on a bar). Oldest to newest, left to
 * right, matching how the equity curve reads.
 */
function dailyPnlBarSvg(journal) {
  const W = 300, H = 84, pad = 6;
  if (!journal || !journal.length) {
    return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}">` +
           `<text x="${W / 2}" y="${H / 2}" fill="#6f6558" font-size="10" ` +
           `text-anchor="middle" dominant-baseline="middle">No daily journal yet</text>` +
           `</svg></div>`;
  }
  const days = [...journal].reverse();   // recent_journal is newest-first; charts read oldest->newest
  const values = days.map(d => parseFloat(d.PnL) || 0);
  const maxAbs = Math.max(1, ...values.map(v => Math.abs(v)));
  const n = days.length;
  const gap = (W - pad * 2) / n;
  const bw = Math.max(2, gap * 0.62);
  const zeroY = H / 2;
  const scale = (H / 2 - pad) / maxAbs;
  let bars = '';
  values.forEach((v, i) => {
    const bx = pad + i * gap + (gap - bw) / 2;
    const bh = Math.max(1, Math.abs(v) * scale);
    const by = v >= 0 ? zeroY - bh : zeroY;
    const color = v >= 0 ? LEVEL_COLOR.ok : LEVEL_COLOR.alert;
    bars += `<rect x="${bx.toFixed(1)}" y="${by.toFixed(1)}" width="${bw.toFixed(1)}" ` +
            `height="${bh.toFixed(1)}" fill="${color}" opacity="0.85" />`;
  });
  return `<div class="chart-wrap"><svg viewBox="0 0 ${W} ${H}">` +
    `<line x1="${pad}" y1="${zeroY}" x2="${W - pad}" y2="${zeroY}" ` +
    `stroke="#3a3128" stroke-width="1" stroke-dasharray="3,3" />${bars}</svg></div>`;
}

/**
 * The Bank's real substance -- every number here is read straight off
 * /api/status, gathered into one dedicated financial view rather than
 * split across the Records Room and the wall display. Nothing computed
 * twice: todaysPnl()/totalPnl() are the exact same server-derived
 * functions the mission-control wall display and Marnie's own bubble use.
 */
function bankSection(s) {
  const curve = s.equity_curve || [];
  const journal = s.recent_journal || [];
  const trades = s.recent_trades || [];
  const scan = s.scan || {};

  let h = `<div class="rows">`;
  h += row("Today's P&L", money(todaysPnl(s)));
  h += row('All-time P&L', money(totalPnl(s)));
  h += row('Buying power', scan.buying_power != null ? `$${scan.buying_power.toFixed(2)}` : '—');
  h += row('Open positions', scan.managed != null ? scan.managed : '—');
  h += row('Trades logged (all-time)', curve.length || trades.length);
  h += `</div>`;

  h += `<h4>Equity curve — cumulative, all trades</h4>`;
  h += equityCurveSvg(curve);

  h += `<h4>Daily P&amp;L — last ${journal.length} trading day${journal.length === 1 ? '' : 's'}</h4>`;
  h += dailyPnlBarSvg(journal);

  const wins = trades.filter(t => t['Win/Loss'] === 'WIN').length;
  const losses = trades.filter(t => t['Win/Loss'] === 'LOSS').length;
  if (wins + losses > 0) {
    h += `<h4>Recent trades — win/loss</h4><div class="rows">`;
    h += row('Wins', wins);
    h += row('Losses', losses);
    h += row(`Win rate (last ${wins + losses})`, `${Math.round((wins / (wins + losses)) * 100)}%`);
    h += `</div>`;
  }

  return h;
}

/**
 * The Tax Office's real substance: a real realized-gains ledger off the
 * bot's own trade log. Deliberately stops at the raw numbers -- no tax
 * rate, bracket, holding-period classification, or liability is computed
 * or implied anywhere in here. That would be real tax advice, and this
 * app doesn't give any; the disclaimer below says so explicitly rather
 * than leaving it implied.
 */
function taxSection(s) {
  const curve = s.equity_curve || [];
  const trades = s.recent_trades || [];

  let h = `<div class="hint" style="margin:0 0 10px">` +
    `Not tax advice. This is your own real trade log, for your own records -- ` +
    `for filing, use your broker's official 1099 and a real tax professional.</div>`;

  h += `<div class="rows">`;
  h += row('Total realized (all-time)', money(totalPnl(s)));
  h += row('Completed trades (all-time)', curve.length || trades.length);
  h += `</div>`;

  if (trades.length) {
    h += `<h4>Recent realized trades</h4><div class="rows">`;
    for (const t of trades) {
      const pnl = parseFloat(t['P&L']) || 0;
      const col = pnl > 0 ? '#4fbf6a' : pnl < 0 ? '#e0503c' : '#8d8577';
      h += `<div class="row"><span>${esc(t.Date)} ${esc(t.Symbol)}</span>` +
           `<b style="font-weight:500;color:${col}">${money(pnl)}</b></div>`;
    }
    h += `</div>`;
    h += `<div class="hint">Each entry above is one completed real position, ` +
         `open to close -- the strategy targets same-day closes (see "Reason" ` +
         `in the full trade log), but check each trade's own date if you need ` +
         `to confirm holding period.</div>`;
  } else {
    h += `<p class="lead">No completed trades logged yet.</p>`;
  }

  return h;
}

/**
 * The Prediction Desk's real substance: the last real snapshot Claude
 * pulled from Sage's actual Robinhood prediction-market account (see
 * predict_business.py). Reads store.predict directly -- same self-contained
 * style as atmSection() -- since there is no live /api/status field for
 * this, unlike the Bank/Tax Office. Deliberately states how old the
 * snapshot is rather than implying anything here is current, and states
 * plainly that there is no API to browse available markets or list open
 * positions -- only this account-level total and the realized-trade log.
 */
function predictSection() {
  const p = store.predict;
  if (!p || !p.loaded) {
    return `<h4>The Prediction Desk</h4><p class="lead">No snapshot yet -- ` +
           `ask Claude to pull a real one from Robinhood.</p>`;
  }

  let h = `<div class="hint" style="margin:0 0 10px">` +
    `Snapshot only, not live -- Robinhood exposes no endpoint to browse available ` +
    `prediction markets or list open positions, just this account total and the ` +
    `realized-trade history. Pulled ${new Date(p.as_of).toLocaleString()}. Not financial advice.</div>`;

  h += `<div class="rows">`;
  h += row('Account', p.account_label || '—');
  h += row('Open event-contract value', money(p.event_contracts_value));
  h += row('Cash', money(p.cash));
  h += row('Buying power', money(p.buying_power));
  h += row('Total account value', money(p.total_value));
  h += `</div>`;

  const t = p.trades || {};
  h += `<h4>Realized trades — ${esc(t.window_label || 'window not recorded')}</h4><div class="rows">`;
  h += row('Settled contracts', t.count ?? '—');
  h += row('Net realized', money(t.net_realized));
  h += row('Wins / losses', `${t.wins ?? '—'} / ${t.losses ?? '—'}`);
  if (t.win_rate_pct != null) h += row('Win rate', `${t.win_rate_pct}%`);
  if (t.biggest_win != null) h += row('Biggest win', money(t.biggest_win));
  if (t.biggest_loss != null) h += row('Biggest loss', money(t.biggest_loss));
  h += `</div>`;

  if (p.note) h += `<div class="hint" style="margin-top:8px">${esc(p.note)}</div>`;

  h += predictBoardSection(p.board);

  return h;
}

/**
 * Smallville Regional's real substance: the last real check Claude ran
 * against Gmail for an actual flight confirmation. Deliberately distinct
 * from a marketing/abandoned-cart email -- the first real check found 15+
 * CheapOair "still thinking about Nashville?" nags for a search that was
 * never booked, and this says so explicitly rather than presenting that
 * search as a trip. No live polling, same as the Prediction Desk.
 */
function airportSection() {
  const a = store.airport;
  if (!a || !a.loaded) {
    return `<h4>Smallville Regional</h4><p class="lead">No check run yet -- ` +
           `ask Claude to search Gmail for a real flight confirmation.</p>`;
  }

  let h = `<div class="hint" style="margin:0 0 10px">` +
    `Checked ${new Date(a.as_of).toLocaleString()}. Not live -- no airline publishes a ` +
    `live feed of one traveller's inbox, so this only updates when Claude re-checks. ` +
    `A marketing or abandoned-cart email never counts as a flight here.</div>`;

  if (!a.flights || !a.flights.length) {
    h += `<div class="rows"><div class="row"><span>Upcoming flights</span>` +
         `<b style="color:#e0503c">None found</b></div></div>`;
    if (a.note) h += `<div class="hint" style="margin-top:8px">${esc(a.note)}</div>`;
    return h;
  }

  h += `<h4>Upcoming flights</h4><div class="rows">`;
  for (const f of a.flights) {
    h += `<div class="row"><span>${esc(f.date || '')} — ${esc(f.route || f.destination || '')}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:58%">${esc(f.confirmation ? 'Conf: ' + f.confirmation : '')}</b></div>`;
  }
  h += `</div>`;
  if (a.note) h += `<div class="hint" style="margin-top:8px">${esc(a.note)}</div>`;

  return h;
}

/**
 * Today's board -- what's actually playing today, real public odds, and
 * Fay's own read. Pulled by hand (Claude + web search), refreshed each
 * morning by the scheduled daily-sports-board task. Deliberately the same
 * disclaimer discipline as everything else real-money-adjacent in this
 * project: a read, not a guarantee, not betting advice.
 */
function predictBoardSection(board) {
  if (!board || !board.games || !board.games.length) {
    return `<h4>Today's board</h4><p class="lead">No board pulled yet today -- ` +
           `ask Claude to research today's games, or wait for the morning refresh.</p>`;
  }

  let h = `<h4>Today's board — ${new Date(board.as_of).toLocaleDateString()}</h4>`;
  if (board.note) h += `<div class="hint" style="margin:0 0 10px">${esc(board.note)}</div>`;
  if (board.summary) {
    h += `<div class="rows" style="margin-bottom:12px"><div class="row" style="flex-direction:column;align-items:flex-start">` +
         `<span style="color:#8d8577;margin-bottom:4px">Ranked, most to least confident</span>` +
         `<b style="font-weight:500;white-space:pre-line">${esc(board.summary)}</b></div></div>`;
  }

  for (const g of board.games) {
    const odds = g.odds || {};
    const oddsLine = Object.entries(odds).map(([k, v]) => `${k}: ${v}`).join(' · ');
    h += `<div style="margin-bottom:12px;padding-bottom:10px;border-bottom:1px solid #3a3128">`;
    h += `<div style="display:flex;justify-content:space-between;gap:10px">` +
         `<b>${esc(g.league || '')} — ${esc(g.matchup || '')}</b>` +
         `<span style="color:#8d8577;white-space:nowrap">${esc(g.time_label || '')}</span></div>`;
    if (oddsLine) h += `<div class="hint" style="margin:4px 0 0">${esc(oddsLine)}</div>`;
    if (g.context) h += `<p class="lead" style="margin:6px 0 0">${esc(g.context)}</p>`;
    if (g.read) h += `<p class="lead" style="margin:6px 0 0;color:#c9a5e0">${esc(g.read)}</p>`;
    if (g.sources && g.sources.length) {
      h += `<div class="hint" style="margin-top:4px">` +
           g.sources.map(u => `<a href="${esc(u)}" target="_blank" style="color:#93867a">source</a>`).join(' · ') +
           `</div>`;
    }
    h += `</div>`;
  }

  return h;
}

export function closePanel() {
  el('panel').classList.remove('open');
  currentReopen = null;
}

/** Re-render whichever panel is currently open, against the latest store
 * state -- used after an action that changes what the panel should show
 * (e.g. the ATM permission toggle), so the click's effect is visible
 * immediately instead of waiting for the next click elsewhere. */
let currentReopen = null;
export function refreshOpenPanel() {
  if (currentReopen) currentReopen();
}

function openPanel(title, sub, level, bodyHtml) {
  el('panelTitle').textContent = title;
  el('panelSub').textContent = sub || '';
  el('panelDot').style.background = LEVEL_COLOR[level] || LEVEL_COLOR.idle;
  el('panelBody').innerHTML = bodyHtml;
  el('panel').classList.add('open');
}

/* ---------------- agent ---------------- */

export function showAgent(agent, s) {
  const d = agent.def;
  const who = personFor(d);
  let html = '';

  html += `<p class="lead">${esc(agent.detail || '—')}</p>`;
  html += `<div class="rows">`;
  if (who) html += row('Name', who.full);
  html += row('Role', d.role);
  html += row('Status', agent.bubble || '—');
  html += row('Room', d.room);
  html += row('Driven by', d.binds);
  html += `</div>`;

  if (who && who.bio) {
    html += `<h4>Background</h4><p class="lead">${esc(who.bio)}</p>`;
    html += `<div class="hint">Backstory is fiction — colour for the world. Everything above the
             line comes from the bot's real state.</div>`;
  }

  // symbol desks get their real zone numbers
  if (d.slot != null) {
    // A desk covers up to SYMBOLS_PER_DESK real symbols (deskSymbols), not
    // one -- symbols(s)[d.slot] used to index the desk number straight into
    // the scan array, which only happened to be right while there were 7
    // symbols and 7 desks. With the watchlist wider than the desk count,
    // that showed the wrong symbol's data, or none, for most desks. This
    // shows the desk's REAL full group, with the one driving the bubble
    // marked, so "what is this desk actually watching" has one honest answer.
    const group = deskSymbols(s, d.slot);
    const featured = mostActionable(group);
    if (group.length) {
      html += `<h4>${group.length > 1 ? `Desk group (${group.length} of ${SYMBOLS_PER_DESK})` : 'Live zone data'}</h4>`;
      for (const x of group) {
        const isFeatured = featured && x.symbol === featured.symbol;
        if (group.length > 1) {
          html += `<div class="rows" style="margin-top:${x === group[0] ? 0 : 8}px">`;
          html += `<div class="row"><span>${isFeatured ? '● ' : ''}${esc(x.symbol)}` +
                   `${isFeatured ? ' — driving the bubble' : ''}</span>` +
                   `<b style="font-weight:500">$${Number(x.price).toFixed(2)} · ${esc(x.zone)}</b></div>`;
        } else {
          // Single symbol at this desk -- the group-header line above only
          // fires for group.length > 1, so Price and Zone need their own
          // explicit rows here or they never render at all. (They did not,
          // for a stretch -- caught by comparing rendered panel text against
          // the real API payload field by field, not just eyeballing it.)
          html += `<div class="rows">`;
          html += row('Price', `$${Number(x.price).toFixed(2)}`);
          html += row('Zone', x.zone);
        }
        if (x.buy_low != null) html += row('Buy zone', `$${x.buy_low} – $${x.buy_high}`);
        if (x.target != null) html += row('Target', `$${x.target}`);
        if (x.distance_pct != null) html += row('Distance', `${x.distance_pct.toFixed(2)}%`);
        html += row('Candle', x.candle + (x.lowvol ? ' (low vol)' : ''));
        html += row('Zone width OK', x.narrow ? 'No — too narrow' : 'Yes');
        html += `</div>`;
      }
    }
  }

  if (d.id === 'eva' && s && s.scan) {
    html += `<h4>Session</h4><div class="rows">`;
    html += row('Scan', `#${s.scan.scan_num} at ${s.scan.time}`);
    if (s.scan.buying_power != null) html += row('Buying power', `$${s.scan.buying_power.toFixed(2)}`);
    if (s.scan.managed != null) html += row('Open positions', s.scan.managed);
    if (s.scan.room_for != null) html += row('Room for', `${s.scan.room_for} more`);
    if (s.scan.breadth != null) html += row('SPY breadth', `${s.scan.breadth > 0 ? '+' : ''}${s.scan.breadth}%`);
    html += `</div>`;
    html += `<h4>Eva's read</h4><p class="lead">${esc(s.market_update || '—')}</p>`;
  }

  if (d.id === 'risk' && s) {
    const f = riskFlags(s);
    html += `<h4>Risk gates</h4><div class="rows">`;
    html += row('Weekly breaker', f.weekly || '—');
    html += row('Earnings blackout', f.blackout.length ? f.blackout.join(', ') : 'none');
    html += `</div>`;
  }

  if (d.id === 'barista') {
    const list = complaints(s);
    html += `<h4>The complaint board</h4>`;
    if (!list.length) {
      html += `<p class="lead">Nothing pinned. Quiet day.</p>`;
    } else {
      html += `<div class="rows">`;
      for (const c of list) {
        html += `<div class="row"><span><i class="dot" style="background:${LEVEL_COLOR[c.level] || LEVEL_COLOR.idle}"></i>${esc(c.who)}</span><b style="font-weight:500;text-align:right">${esc(c.what)}</b></div>`;
      }
      html += `</div>`;
      html += `<div class="hint">Every line is derived from live bot state — blackouts,
               the win-rate breaker, narrow zones, failed health checks and today's
               losing trades. Sal is fiction; the gripes are not.</div>`;
    }
  }

  if (d.id === 'mechanic' && s) {
    const m = activeMechanic(s);
    html += `<h4>Last health check</h4><div class="rows">`;
    html += row('Status', m ? m.status : '—');
    html += row('Ran', m && m.last_run ? new Date(m.last_run).toLocaleString() : '—');
    html += `</div>`;
    if (m && m.summary) html += `<p class="lead">${esc(m.summary)}</p>`;
  }

  if (d.studio) html += studioSection();
  if (d.id === 'atmops') html += atmSection();
  if (d.id === 'predict') html += predictSection();
  if (d.id === 'dana') html += airportSection();

  // A desk whose ticker changed recently explains itself: which symbol it
  // replaced and the real reason the screener gave for the swap.
  if (d.slot != null && agent.name) {
    const change = recentWatchlistChange(s, 3);
    const entry = (change.entries || []).find(e => (e.added || []).includes(agent.name));
    if (entry) {
      html += `<h4>New at this desk</h4><div class="rows">`;
      html += row('Arrived', entry.when ? new Date(entry.when).toLocaleDateString() : '—');
      if ((entry.dropped || []).length) html += row('Replaced', entry.dropped.join(', '));
      html += `</div>`;
      if (entry.reason) html += `<p class="lead" style="margin-top:6px">${esc(entry.reason)}</p>`;
      html += `<div class="hint">Swapped in by the nightly screener after passing the same ` +
              `backtest gate every symbol here has to clear.</div>`;
    }
  }

  html += walletSection(d.id);

  openPanel(agent.label, d.role, agent.level, html);
  currentReopen = () => showAgent(agent, store.raw);
}

/* ---------------- Sage's ATM Co. ---------------- */

/**
 * The real 6-step launch checklist, straight from /api/atm. No stage
 * inference, no file-scanning -- a step is done only when
 * atm_business.mark_step_done() was actually called for it, so this is
 * either completely honest or completely absent, never guessed at.
 */
function atmSection() {
  const atm = store.atm;
  if (!atm) return `<h4>Sage's ATM Co.</h4><p class="lead">Not loaded yet.</p>`;

  let h = `<h4>Sage's ATM Co.</h4>`;
  h += `<p class="lead">${esc(atm.budget_note)}</p>`;
  h += `<div class="lead" style="color:#93867a">` +
       `${atm.launched ? '✓ Launched' : `${atm.done_count} of ${atm.total_steps} real steps done`}</div>`;

  h += `<div class="rows" style="margin-top:8px">`;
  for (const s of atm.steps) {
    const mark = s.done ? '✓' : '○';
    h += `<div class="row"><span>${mark} ${esc(s.title)}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:58%">${s.done ? (esc(s.note) || 'Done') : '—'}</b></div>`;
  }
  h += `</div>`;

  const next = atm.steps.find(s => !s.done);
  if (next) {
    h += `<p class="lead" style="margin-top:8px">Next: <b>${esc(next.title)}</b> — ${esc(next.what)}</p>`;
  }
  h += `<div class="hint">This is a real plan for a real business, not a simulation — nothing here ` +
       `marks itself done. See the <a href="https://claude.ai/code/artifact/68415107-5ca7-4543-a7bd-c32c35c6cf92" ` +
       `target="_blank" style="color:#93867a">research primer</a> for the numbers behind it.</div>`;

  h += wesPermissionBlock(atm);
  h += wesDraftsBlock(atm);

  return h;
}

/**
 * Wes can draft (never send, never sign) emails, business-plan sections,
 * contract templates, and location research -- but only during the studio's
 * work hours, and only when this is on. Off by default. The button posts
 * straight to /api/atm/permission -- the only thing that may flip it.
 */
function wesPermissionBlock(atm) {
  const perm = atm.permission || { granted: false, changed_at: null };
  const on = !!perm.granted;
  const when = perm.changed_at ? new Date(perm.changed_at).toLocaleString() : null;

  let h = `<h4>Wes's permission</h4>`;
  h += `<div class="rows"><div class="row"><span>Allowed to work</span>` +
       `<b style="color:${on ? '#4fbf6a' : '#e0503c'}">${on ? '✓ Yes' : '✗ No'}</b></div></div>`;
  h += `<button class="perm-toggle" data-next="${on ? 'false' : 'true'}" ` +
       `style="margin-top:8px;width:100%">${on ? 'Revoke permission' : 'Grant permission'}</button>`;
  h += `<div class="hint">` +
       (on
         ? `Granted ${esc(when || '')}. During work hours (same as the Studio — 09:00–16:00 ET, weekdays), ` +
           `Wes may draft emails, a business plan, and contract templates, and research placement locations. ` +
           `He never sends an email, never signs anything, and nothing he drafts is legally binding — that ` +
           `needs your own review and a real attorney before anything is used for real.`
         : `Wes does nothing on his own until this is granted — no drafts, no research, no Gmail activity. ` +
           `Revoke any time; it takes effect on his next shift.`) +
       `</div>`;

  const shift = atm.shift;
  if (shift) {
    const dotColor = shift.status === 'productive' ? '#4fbf6a'
                    : shift.status === 'blocked' ? '#e08b3c' : '#8d8577';
    h += `<div class="rows" style="margin-top:8px"><div class="row"><span>Last shift</span>` +
         `<b style="color:${dotColor}">${esc(shift.status || '')}</b></div></div>`;
    if (shift.summary) h += `<p class="lead" style="margin-top:6px">${esc(shift.summary)}</p>`;
    if (shift.last_run) h += `<div class="hint">${new Date(shift.last_run).toLocaleString()}</div>`;
  }
  return h;
}

// Roughly the order the six real steps need them in: plan first, then the
// location work, then the outreach, then the paperwork.
const ATM_DOC_KIND_ORDER = ['Business plan', 'Location research', 'Email draft',
                            'Processor research', 'Contract template', 'Draft'];

/** Real files Wes has actually written to ~/Desktop/Sage's ATM Co/_atm/drafts —
 * nothing here is implied from a stage; either the file is there or it's not
 * shown. Clicking one reads it straight off disk via /api/atm/doc. */
function wesDraftsBlock(atm) {
  const drafts = atm.drafts || [];
  let h = `<h4>Wes's drafts</h4>`;
  if (!drafts.length) {
    h += `<p class="lead" style="color:#93867a">Nothing drafted yet.</p>`;
    return h;
  }
  const sorted = [...drafts].sort((a, b) =>
    ATM_DOC_KIND_ORDER.indexOf(a.kind) - ATM_DOC_KIND_ORDER.indexOf(b.kind));
  h += `<div class="rows">`;
  for (const d of sorted) {
    const clickable = d.readable;
    const name = clickable
      ? `<span class="filelink doc-open" data-src="atm" data-path="${esc(d.path)}" title="Open ${esc(d.name)}">${esc(d.name)}</span>`
      : esc(d.name);
    h += `<div class="row"><span>${name}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:58%">${esc(d.kind)} · ${fmtSize(d.size)}</b></div>`;
  }
  h += `</div>`;
  h += `<div class="hint">Every draft is exactly that — a starting point Wes wrote for you to review, ` +
       `edit, and send/sign yourself. None of it goes out or gets signed on its own.</div>`;
  return h;
}

/* ---------------- morning briefing ---------------- */

/**
 * Everything worth knowing before the open, in one place: today's real
 * watchlist, what the nightly screener actually changed overnight (if
 * anything), earnings exclusions, system health, and yesterday's real
 * results. Every field here already exists elsewhere in the panels --
 * this is the same real data, gathered into one read instead of six clicks.
 */
export function showMorningBriefing(s) {
  if (!s) return openPanel('Morning Briefing', 'Trading Floor', 'idle',
                            `<p class="lead">No data yet.</p>`);

  let html = `<p class="lead">Everything worth knowing before the open.</p>`;

  // --- today's real watchlist -------------------------------------------
  const list = symbols(s);
  html += `<h4>Today's watchlist — ${list.length} symbols</h4>`;
  html += `<p class="lead">${list.map(x => esc(x.symbol)).join(' · ') || '—'}</p>`;

  // --- what the screener actually changed overnight ----------------------
  const w = watchlist(s);
  if (w) {
    const last = (w.history || [])[0];
    const hoursAgo = last ? (Date.now() - new Date(last.when).getTime()) / 3600000 : null;
    html += `<h4>Overnight screener</h4>`;
    if (last && hoursAgo != null && hoursAgo < 20) {
      const swap = `${(last.dropped || []).join(', ') || '—'} → ${(last.added || []).join(', ') || '—'}`;
      html += `<p class="lead">Changed the list ${Math.round(hoursAgo)}h ago: <b>${esc(swap)}</b></p>`;
      if (last.reason) html += `<p class="lead" style="color:#93867a">${esc(last.reason)}</p>`;
    } else {
      html += `<p class="lead">No change overnight — the list is the same one it was yesterday.</p>`;
    }
  }

  // --- earnings exclusions ------------------------------------------------
  const blackout = s.earnings_blackout || [];
  html += `<h4>Earnings exclusions</h4>`;
  html += `<p class="lead">${blackout.length
    ? `${blackout.join(', ')} — blocked from new entries today.`
    : 'None today — every symbol is eligible on that front.'}</p>`;

  // --- system health -------------------------------------------------------
  const m = activeMechanic(s);
  html += `<h4>System health</h4><div class="rows">`;
  html += row('Bot', s.bot_alive ? 'Alive' : 'Offline');
  html += row('Last mechanic check', m ? m.status : 'none yet');
  html += row('Risk', riskFlags(s).alerting ? 'Blocked' : 'Clear');
  html += `</div>`;

  // --- prior-day results ----------------------------------------------------
  // recent_trades spans MULTIPLE prior days, not just one -- summing all of
  // it and labeling it "that day" silently mixed several days into a single
  // number (caught live: -$0.61 + $1.27 + -$0.03 read as one day's +$0.63).
  // "That day" now means only trades on the single most recent prior date.
  const todayStr = new Date().toLocaleDateString('en-CA'); // YYYY-MM-DD, matches trade-log format
  const prior = (s.recent_trades || []).filter(t => t.Date && t.Date !== todayStr);
  const lastDay = prior[0] && prior[0].Date;
  const lastDayTrades = prior.filter(t => t.Date === lastDay);
  html += `<h4>Prior-day results</h4>`;
  if (prior.length) {
    const priorPnl = lastDayTrades.reduce((sum, t) => sum + (parseFloat(t['P&L']) || 0), 0);
    html += `<div class="rows">`;
    html += row('Last logged day', lastDay);
    html += row('Trades that day', lastDayTrades.length);
    html += row('P&L that day', money(priorPnl));
    html += `</div>`;
  } else {
    html += `<p class="lead">No prior trades logged yet.</p>`;
  }

  openPanel('Morning Briefing', 'Trading Floor', 'ok', html);
}

/* ---------------- the watchlist ---------------- */

/**
 * How the watchlist has really changed. Every number here comes out of
 * watchlist_manager's own history -- the same record the nightly screener
 * writes when it swaps a symbol, so this is the audit trail, not a
 * summary of one.
 */
function watchlistSection(s) {
  const w = watchlist(s);
  if (!w) return '';

  // The file and the RUNNING bot can legitimately disagree: Eva reads the
  // watchlist once at startup, so an overnight change is pending until the
  // 6:00am restart. Showing the file alone would imply she is trading a
  // symbol she has not loaded yet -- so say which is which.
  const scanning = symbols(s).map(x => x.symbol);
  const pendingAdd = w.symbols.filter(sym => scanning.length && !scanning.includes(sym));
  const pendingDrop = scanning.filter(sym => !w.symbols.includes(sym));

  let h = `<h4>Watchlist</h4>`;
  h += `<p class="lead">${w.symbols.map(esc).join(' · ')}</p>`;

  if (pendingAdd.length || pendingDrop.length) {
    h += `<div class="rows" style="margin-top:8px"><div class="row">` +
         `<span><i class="dot" style="background:#e8c15a"></i>Pending</span>` +
         `<b style="font-weight:500;color:#e8c15a">takes effect at the next open</b></div></div>`;
    h += `<div class="hint" style="margin-top:6px">Eva is still scanning ` +
         `<code>${scanning.map(esc).join(', ')}</code> — she loads the watchlist once when she ` +
         `starts, so tonight's change goes live after the 6:00am restart, not now.</div>`;
  }

  const change = recentWatchlistChange(s, 3);
  if (change.added.length || change.dropped.length) {
    h += `<div class="rows" style="margin-top:8px">`;
    for (const sym of change.added) {
      h += `<div class="row"><span><i class="dot" style="background:#4fbf6a"></i>${esc(sym)}</span>` +
           `<b style="font-weight:500;color:#4fbf6a">just added</b></div>`;
    }
    for (const sym of change.dropped) {
      h += `<div class="row"><span><i class="dot" style="background:#e0503c"></i>${esc(sym)}</span>` +
           `<b style="font-weight:500;color:#e0503c">dropped</b></div>`;
    }
    h += `</div>`;
  }

  if (w.history && w.history.length) {
    h += `<h4>Recent changes</h4><div class="rows">`;
    for (const e of w.history.slice(0, 5)) {
      const when = e.when ? new Date(e.when).toLocaleDateString() : '—';
      const swap = `${(e.dropped || []).join(', ') || '—'} → ${(e.added || []).join(', ') || '—'}`;
      h += `<div class="row"><span>${esc(when)}</span>` +
           `<b style="font-weight:500;text-align:right;max-width:66%">${esc(swap)}</b></div>`;
      if (e.reason) {
        h += `<div class="row"><span style="color:#6f6558;font-size:10.5px">${esc(e.reason)}</span></div>`;
      }
    }
    h += `</div>`;
  } else {
    h += `<div class="hint">No changes recorded yet — the list is still the one it started with.</div>`;
  }

  const n = w.nightly;
  if (n) {
    const c = n.status === 'changed' ? '#4fbf6a' : n.status === 'blocked' ? '#e0503c' : '#8d8577';
    h += `<div class="rows" style="margin-top:8px"><div class="row"><span>Last nightly scan</span>` +
         `<b style="color:${c}">${esc(n.status || '')}</b></div></div>`;
    if (n.summary) h += `<p class="lead" style="margin-top:6px">${esc(n.summary)}</p>`;
    if (n.last_run) h += `<div class="hint">${new Date(n.last_run).toLocaleString()}</div>`;
  }
  h += candidateBoard(w.candidates);

  h += `<div class="hint">Refreshed automatically each night: every candidate is backtested first, ` +
       `at most ${w.max_swaps ?? 2} swap(s) per run, and a symbol with an open position is never dropped.</div>`;
  return h;
}

/**
 * The full screener universe -- every symbol actually backtested last night,
 * ranked by real P&L, not just the 7 that made the cut. Live symbols are
 * marked so it reads as "here's the whole board" rather than a second,
 * confusing watchlist.
 *
 * This exists because the screener was evaluating ~29 symbols a night and
 * none of that work was visible anywhere -- only the 7 winners ever
 * surfaced. A symbol can sit here with a strong backtest for weeks without
 * being promoted (MAX_SWAPS caps it at a couple of changes a night), so this
 * is genuinely "who to watch," not a preview of tomorrow's list.
 */
function candidateBoard(candidates) {
  if (!candidates || !candidates.results || !candidates.results.length) return '';
  const { results, universe_size, generated_at } = candidates;

  let h = `<h4>Candidate board — ${universe_size} symbols screened</h4>`;
  h += `<div class="rows">`;
  for (const r of results) {
    const pnl = typeof r.pnl === 'number' ? r.pnl : 0;
    const pnlColor = pnl > 0 ? '#4fbf6a' : pnl < 0 ? '#e0503c' : '#8d8577';
    const tag = r.live
      ? `<span style="color:#4fbf6a;font-weight:700">● live</span>`
      : `<span style="color:#8d8577">watching</span>`;
    h += `<div class="row"><span>${esc(r.symbol)} ${tag}</span>` +
         `<b style="font-weight:500;color:${pnlColor}">` +
         `${pnl >= 0 ? '+' : ''}${pnl.toFixed(2)} · ${(r.winrate || 0).toFixed(0)}% · ` +
         `${r.trades || 0} trade${r.trades === 1 ? '' : 's'}</b></div>`;
  }
  h += `</div>`;
  if (generated_at) {
    h += `<div class="hint">Backtested ${new Date(generated_at).toLocaleString()}. ` +
         `Ranked by real backtested P&L over the sampled window, highest first — ` +
         `a strong number here does not guarantee promotion, only that it is worth watching.</div>`;
  }
  return h;
}

/* ---------------- what actually went wrong ---------------- */

/**
 * Real trouble from the bot's own daily journal. Shows "nothing" honestly
 * when there is nothing -- an empty state here is a real result, not a
 * failure to load.
 */
function troubleSection(s) {
  const items = troubleSignals(s);
  let h = `<h4>Worth a look</h4>`;
  if (!items.length) {
    h += `<p class="lead" style="color:#93867a">Nothing flagged in the last ` +
         `${((s && s.recent_journal) || []).length} trading day(s).</p>`;
    return h;
  }
  h += `<div class="rows">`;
  for (const it of items) {
    h += `<div class="row"><span><i class="dot" style="background:${LEVEL_COLOR[it.level] || LEVEL_COLOR.idle}"></i>` +
         `${esc(it.what)}</span></div>`;
    h += `<div class="row"><span style="color:#6f6558;font-size:10.5px">${esc(it.detail)}</span></div>`;
  }
  h += `</div>`;
  return h;
}

/** The day-by-day journal the bot writes itself -- real per-day outcomes. */
function journalSection(s) {
  const j = (s && s.recent_journal) || [];
  if (!j.length) return '';
  let h = `<h4>Day by day</h4><div class="rows">`;
  for (const d of j) {
    const pnl = parseFloat(d.PnL) || 0;
    const col = pnl > 0 ? '#4fbf6a' : pnl < 0 ? '#e0503c' : '#8d8577';
    const wr = d.Trades && parseInt(d.Trades, 10) > 0 ? ` · ${d.WinRatePct}%` : '';
    h += `<div class="row"><span>${esc(d.Date)}</span>` +
         `<b style="font-weight:500;color:${col}">${money(pnl)}` +
         `<span style="color:#6f6558">  ${esc(d.Trades)} trade(s)${esc(wr)}</span></b></div>`;
  }
  h += `</div>`;
  return h;
}

/* ---------------- the general store ---------------- */

const SIM_KIND_LABEL = { home: '🏠', pet: '🐾', vehicle: '🚲' };

/**
 * The town's make-believe economy. Deliberately reads as a game panel and
 * says so out loud -- everything else in this city is real data, and this
 * one is not, so the distinction has to be visible rather than assumed.
 */
function storeSection() {
  const sim = store.sim;
  if (!sim) return `<h4>The Store</h4><p class="lead">Not loaded yet.</p>`;

  const money = n => `${sim.currency}${n.toLocaleString()}`;

  let h = `<div class="hint" style="margin:0 0 10px">🎲 ${esc(sim.fiction_note)}</div>`;
  h += `<p class="lead">${esc(sim.payday_note)}</p>`;
  if (sim.last_payday) {
    h += `<div class="lead" style="color:#93867a">Last payday ${esc(sim.last_payday)} · ` +
         `${sim.paydays_run} so far</div>`;
  }

  // --- what everyone is saving for -----------------------------------
  h += `<h4>Saving up for</h4><div class="rows">`;
  for (const r of sim.residents) {
    if (!r.goal) continue;
    const bar = `<span style="display:inline-block;width:46px;height:5px;background:#2a231b;` +
                `vertical-align:middle;margin-right:5px">` +
                `<span style="display:block;width:${r.goal.pct}%;height:100%;background:#4fbf6a"></span></span>`;
    h += `<div class="row"><span>${esc(r.name)}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:70%">${bar}${esc(r.goal.name)} · ` +
         `${money(r.goal.saved)}/${money(r.goal.price)}</b></div>`;
  }
  h += `</div>`;

  // --- the catalogue --------------------------------------------------
  h += `<h4>On the shelves</h4><div class="rows">`;
  for (const item of sim.catalog) {
    const owners = sim.residents.filter(r => r.owned.some(o => o.id === item.id)).length;
    h += `<div class="row"><span>${SIM_KIND_LABEL[item.kind] || ''} ${esc(item.name)}</span>` +
         `<b style="font-weight:500;text-align:right">${money(item.price)}` +
         (owners ? `<span style="color:#6f6558"> · ${owners} sold</span>` : '') + `</b></div>`;
  }
  h += `</div>`;
  h += `<div class="hint">${esc(sim.catalog.find(c => c.id === 'extension')?.blurb || '')}</div>`;

  // --- the ledger -----------------------------------------------------
  if (sim.log && sim.log.length) {
    h += `<h4>Recently</h4><div class="rows">`;
    for (const entry of sim.log.slice(0, 10)) {
      h += `<div class="row"><span>${esc(entry.text)}</span></div>`;
    }
    h += `</div>`;
  }
  return h;
}

/** One resident's own wallet -- shown on their character panel. */
function walletSection(agentId) {
  const sim = store.sim;
  if (!sim) return '';
  const r = sim.residents.find(x => x.id === agentId);
  if (!r) return '';
  const money = n => `${sim.currency}${n.toLocaleString()}`;

  let h = `<h4>Wallet <span style="color:#6f6558">· make-believe</span></h4>`;
  h += `<div class="rows">`;
  h += row('Balance', money(r.balance));
  if (r.goal) {
    h += row('Saving for', `${r.goal.name} (${money(r.goal.price)})`);
    h += row('Still needs', r.goal.short > 0 ? money(r.goal.short) : 'can afford it');
  }
  h += `</div>`;
  if (r.owned.length) {
    h += `<div class="lead" style="margin-top:8px;color:#93867a">Owns: ` +
         r.owned.map(o => `${SIM_KIND_LABEL[o.kind] || ''} ${esc(o.name)}`).join(' · ') + `</div>`;
  }
  return h;
}

/* ---------------- the archive studio ---------------- */

// Mirrors studio.py's STAGES tuple exactly, in order -- there is no other
// source of truth for stage order on this side, so this list and that one
// have to be kept in sync by hand if a stage is ever added or renamed.
const STUDIO_STAGES = [
  ['research',  'Research'],
  ['script',    'Script'],
  ['shotlist',  'Shot list'],
  ['audio',     'Audio'],
  ['video',     'Video'],
  ['packaging', 'Packaging'],
  ['publish',   'Publish']
];

/**
 * One project, one card: every pipeline stage with the real file(s) that
 * back it, or an honest "not started" / "implied only" when there isn't
 * one. `docPath` maps a filename to its real path (from st.documents) so a
 * stage's evidence file can be opened the same way the old flat file list
 * let you -- this isn't losing that feature, just grouping it by project.
 */
function projectCard(p, docPath) {
  const shipped = p.current_stage === 'shipped';
  const pct = Math.round((p.progress || 0) * 100);
  const stageLabel = (STUDIO_STAGES.find(s => s[0] === p.current_stage) || [])[1];

  let h = `<h4 style="margin-top:20px">${esc(p.title)}${p.subtitle ? ' — ' + esc(p.subtitle) : ''}</h4>`;
  h += `<div class="lead" style="color:#93867a">` +
       `${shipped ? '✓ Shipped — ready to publish' : `Blocked on: ${esc(stageLabel || p.current_stage)}`}` +
       ` · ${pct}% through the pipeline</div>`;

  h += `<div class="rows" style="margin-top:6px">`;
  for (const [key, label] of STUDIO_STAGES) {
    const st = p.stages && p.stages[key];
    if (!st) continue;
    const mark = st.done ? (st.implied ? '◐' : '✓') : '○';
    let evidence;
    if (st.files && st.files.length) {
      evidence = st.files.map(name => {
        const path = docPath.get(name);
        return path
          ? `<span class="filelink doc-open" data-path="${esc(path)}" title="Open ${esc(name)}">${esc(name)}</span>`
          : esc(name);
      }).join(', ');
    } else {
      evidence = st.implied ? 'implied by a later stage' : '—';
    }
    h += `<div class="row"><span>${mark} ${esc(label)}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:62%">${evidence}</b></div>`;
  }
  h += `</div>`;
  if (p.stages && Object.values(p.stages).some(s => s.implied)) {
    h += `<div class="hint">◐ = implied only -- a later stage has a file, so this must ` +
         `have happened, but nothing names it directly.</div>`;
  }
  return h;
}

const WAREHOUSE_READABLE = new Set(['md', 'txt', 'srt', 'vtt', 'csv', 'json', 'yml', 'yaml']);

function fmtSize(bytes) {
  return bytes > 1024 * 1024 ? `${(bytes / 1024 / 1024).toFixed(1)} MB` : `${Math.round(bytes / 1024)} KB`;
}

/** One project's warehouse shelf -- every real file it shipped with, each
 * one described in plain English (not just a filename), clickable where
 * it's actually readable as text. Matches studio.py's warehouse_status(). */
function warehouseShelf(w) {
  let h = `<h4 style="margin-top:16px">📦 ${esc(w.title)}${w.subtitle ? ' — ' + esc(w.subtitle) : ''}</h4>`;
  if (!w.files || !w.files.length) {
    h += `<p class="lead">Shelf is empty.</p>`;
    return h;
  }
  h += `<div class="rows">`;
  for (const f of w.files) {
    const clickable = WAREHOUSE_READABLE.has(f.ext);
    const nameHtml = clickable
      ? `<span class="filelink doc-open" data-path="${esc(f.path)}" title="Open ${esc(f.name)}">${esc(f.name)}</span>`
      : esc(f.name);
    h += `<div class="row"><span>${nameHtml}</span>` +
         `<b style="font-weight:500;text-align:right;max-width:58%">${esc(f.description)} · ${fmtSize(f.size)}</b></div>`;
  }
  h += `</div>`;
  if (w.manifest_path) {
    h += `<div class="hint"><span class="filelink doc-open" data-path="${esc(w.manifest_path)}">Open the full manifest</span></div>`;
  }
  return h;
}

/**
 * Shift clock, per-project pipelines (with real file evidence per stage),
 * the warehouse (finished projects, stored until used), recent activity,
 * and where the studio keeps its own operational files.
 *
 * All of it comes from /api/studio, which reads the real channel folders.
 * Nothing here is a to-do list someone typed -- every mark is a real file on
 * disk, or the honest absence of one.
 */
export function studioSection() {
  const st = store.studio;
  if (!st) {
    return `<h4>Archive Studio</h4><p class="lead">Studio state hasn't loaded yet.</p>`;
  }

  const sh = studioShift() || {};
  const onShift = sh.open === true;
  const phaseLabel = { open: 'On shift', before: 'Not in yet',
                       after: 'Clocked out', weekend: 'Weekend' }[sh.phase] || '—';

  let h = `<h4>Shift</h4><div class="rows">`;
  h += row('Status', `${onShift ? '🟢' : '🌙'} ${phaseLabel}`);
  h += row('Hours', `${sh.opens_et || '09:00'} – ${sh.closes_et || '16:00'} ET, weekdays`);
  h += row('Now', `${sh.now_et || '—'} ET`);
  h += `</div>`;
  h += `<div class="hint">The studio keeps the trading floor's hours: in when the bot
        starts at 09:00 ET, out when it exits at 16:00 ET.</div>`;

  // --- one card per project, pipeline stages with the real file(s) behind
  //     each one -- this replaces a flat task list + a flat, unsorted
  //     document list, which mixed every project's files together and made
  //     "what has ACT UP actually got done" impossible to answer at a glance.
  const projects = st.projects || [];
  const docPath = new Map((st.documents || []).map(d => [d.name, d.path]));
  h += `<h4>Projects — ${projects.length}</h4>`;
  if (!projects.length) {
    h += `<p class="lead">No projects found in the channel folders.</p>`;
  } else {
    for (const p of projects) h += projectCard(p, docPath);
  }

  // --- the warehouse: finished projects, stored until used -----------------
  const warehouse = st.warehouse || [];
  h += `<h4>Warehouse</h4>`;
  if (!warehouse.length) {
    h += `<p class="lead">Nothing shipped yet — finished projects land here, one shelf each.</p>`;
  } else {
    h += `<p class="lead">Copies, not the originals — every shipped project keeps a clean, ` +
         `complete shelf here so nothing gets lost in the channel folders. ${warehouse.length} ` +
         `project${warehouse.length === 1 ? '' : 's'} stored.</p>`;
    for (const w of warehouse) h += warehouseShelf(w);
  }

  // --- what the studio actually did ----------------------------------------
  const acts = st.activity || [];
  h += `<h4>Recent activity</h4>`;
  if (!acts.length) {
    h += `<p class="lead">Nothing logged yet.</p>`;
  } else {
    h += `<div class="rows">`;
    for (const a of acts.slice(0, 6)) {
      h += `<div class="row"><span>${esc(a.time)} ${esc(a.event)}</span>` +
           `<b style="font-weight:500;text-align:right">${esc(a.detail || '')}</b></div>`;
    }
    h += `</div>`;
  }

  // --- its own filing cabinet ----------------------------------------------
  if (st.files) {
    h += `<h4>Its own files</h4><div class="rows">`;
    h += row('Ideas', 'ideas.json');
    h += row('Activity', 'activity.csv');
    h += row('Reports', `${(st.reports || []).length} in reports/`);
    h += row('Outlines', `${(st.outlines || []).length} in outlines/`);
    h += `</div>`;
    h += `<div class="hint">Kept in <code>${esc(st.data_dir || '')}</code> — the channel's own
          folder. Nothing here touches the bot's trade logs.</div>`;
  }
  return h;
}

/* ---------------- room ---------------- */

/**
 * Who is ACTUALLY standing in this room right now, by real tile position --
 * not who is nominally assigned here. Filtering by a.def.room alone kept
 * someone listed under "Here now" even after they had walked home for the
 * night, which is exactly what "here now" promises isn't happening. Falls
 * back to def.room only if x/y aren't available for some reason (defensive,
 * should not normally trigger).
 */
function actuallyInRoom(agents, roomId) {
  return agents.filter(a => {
    if (typeof a.x === 'number' && typeof a.y === 'number') {
      const here = roomAt(Math.round(a.x), Math.round(a.y));
      return here && here.id === roomId;
    }
    return a.def.room === roomId;
  });
}

export function showRoom(room, s, agents) {
  const inRoom = actuallyInRoom(agents, room.id);
  let html = `<p class="lead">${esc(room.blurb)}</p>`;

  if (inRoom.length) {
    html += `<h4>Here now</h4><div class="rows">`;
    for (const a of inRoom) {
      html += `<div class="row"><span><i class="dot" style="background:${LEVEL_COLOR[a.level] || LEVEL_COLOR.idle}"></i>${esc(a.label)}</span><b>${esc(a.bubble || '—')}</b></div>`;
    }
    html += `</div>`;
  }

  if (room.id === 'watchlist' && s) {
    // The 7 "Here now" desk characters only ever show ONE featured symbol
    // each (deskSymbols/mostActionable), so a watchlist wider than 7 had
    // real symbols with no visible representation anywhere in this room.
    // This lists every real symbol currently scanned, full stop -- the
    // actual answer to "what is the trading floor watching."
    const all = symbols(s);
    html += `<h4>Full watchlist — ${all.length} symbol${all.length === 1 ? '' : 's'} scanned</h4>`;
    if (all.length) {
      html += `<div class="rows">`;
      all.forEach((x, i) => {
        const desk = (i % DESK_COUNT) + 1;   // round-robin -- must match activity.js's symbolSlotOf
        const zoneColor = x.zone === 'BUY' ? '#4fbf6a' : x.narrow ? '#8d8577' : '#e8c15a';
        html += `<div class="row"><span>${esc(x.symbol)} <span style="color:#6f6558;font-size:10px">desk ${desk}</span></span>` +
                 `<b style="font-weight:500;color:${zoneColor}">$${Number(x.price).toFixed(2)} · ` +
                 `${x.narrow ? 'too narrow' : esc(x.zone)}</b></div>`;
      });
      html += `</div>`;
      html += `<div class="hint">Each desk covers up to ${SYMBOLS_PER_DESK} symbols and shows whichever is ` +
               `most actionable — click a desk for its full group.</div>`;
    } else {
      html += `<p class="lead">No scan data yet.</p>`;
    }
  }

  if (room.id === 'records' && s) {
    const t = (s.recent_trades || []);
    const curve = s.equity_curve || [];
    html += `<h4>Equity curve</h4>`;
    html += equityCurveSvg(curve);
    html += `<div class="rows" style="margin-top:8px">`;
    html += row("Today's P&L", money(todaysPnl(s)));
    html += row('All-time P&L', money(totalPnl(s)));
    html += row('Trades logged (all-time)', curve.length || t.length);
    html += `</div>`;
    if (t.length) {
      html += `<h4>Recent trades</h4><div class="rows">`;
      for (const x of t.slice(0, 6)) {
        const pnl = parseFloat(x['P&L']) || 0;
        const col = pnl > 0 ? '#4fbf6a' : pnl < 0 ? '#e0503c' : '#8d8577';
        html += `<div class="row"><span>${esc(x.Date)} ${esc(x.Symbol)}</span>` +
                `<b style="font-weight:500;color:${col}">${money(pnl)}` +
                `<span style="color:#6f6558">  ${esc(x.Reason || '')}</span></b></div>`;
      }
      html += `</div>`;
    }
    // The per-day journal and the trouble list -- the Records Room holds
    // both and used to surface neither.
    html += journalSection(s);
    html += troubleSection(s);
  }

  if (room.id === 'trading' && s && s.scan) {
    html += `<h4>Scan</h4><div class="rows">`;
    html += row('Bot alive', s.bot_alive ? 'yes' : 'no');
    html += row('Latest scan', `#${s.scan.scan_num} at ${s.scan.time}`);
    html += `</div>`;
    html += watchlistSection(s);
  }

  if (room.id === 'studio') html += studioSection();
  if (room.id === 'atmco') html += atmSection();
  if (room.id === 'store') html += storeSection();
  if (room.id === 'bank' && s) html += bankSection(s);
  if (room.id === 'tax' && s) html += taxSection(s);
  if (room.id === 'predict') html += predictSection();
  if (room.id === 'airport') html += airportSection();

  html += room.data.length
    ? `<div class="hint">Data source: <code>${esc(room.data.join(', '))}</code></div>`
    : `<div class="hint">No real subsystem behind this room -- ambient only.</div>`;
  openPanel(room.name, 'Department', inRoom.some(a => a.level === 'alert') ? 'alert' : 'ok', html);
  currentReopen = () => showRoom(room, store.raw, agents);
}

/* ---------------- objects (desks, terminals, screens) ---------------- */

const OBJECT_INFO = {
  'money-board':   { title: 'The Money Board', what: 'Combined real status: trading P&L and unpublished, ready-to-earn Studio work.' },
  'eva-desk':      { title: "Eva's terminal", what: 'The scan loop runs here.' },
  'war-table':     { title: 'Morning Briefing', what: 'Today\'s watchlist, overnight changes, and system health -- everything worth knowing before the open, in one place.' },
  'trading-aux':   { title: 'Spare desk', what: 'Unassigned workstation.' },
  'risk-desk':     { title: 'Risk terminal', what: 'Entry gates and blackout rules.' },
  'risk-aux':      { title: 'Risk aux desk', what: 'Unassigned workstation.' },
  'records-desk':  { title: 'Archive terminal', what: 'Trade log and reviews.' },
  'mechanic-desk': { title: 'Diagnostics terminal', what: 'Scheduled health checks.' },
  'bench':         { title: 'Workbench', what: 'Where the mechanic works.' },
  'rack-a':        { title: 'Server rack A', what: 'The bot process host.' },
  'rack-b':        { title: 'Server rack B', what: 'Log and journal storage.' },
  'break-table':   { title: 'Break table', what: 'Off-hours.' },
  // wall screens
  'scan':    { title: 'Scan display', what: 'Current scan number and cadence.' },
  'breadth': { title: 'Breadth display', what: "SPY's move from today's open." },
  'pnl':     { title: 'P&L display', what: "Today's realised profit and loss." },
  'equity':  { title: 'Equity curve', what: 'Cumulative P&L across every logged trade.' },
  'zones':   { title: 'Zone board', what: 'How many symbols are in a tradeable buy zone.' },
  'risk':    { title: 'Risk board', what: 'Active entry blocks.' }
};

export function showObject(obj, s, agents) {
  const key = obj.station || obj.screen;

  // An Archive Studio station -- show the real pipeline stage behind it.
  if (obj.studioStation) return showStudioStation(obj.studioStation);

  const meta = OBJECT_INFO[key] || { title: key, what: '' };
  let html = `<p class="lead">${esc(meta.what)}</p>`;

  // A desk's furniture, clicked directly (as opposed to the character
  // standing at it -- showAgent handles that path). Same real group, same
  // deskSymbols()/mostActionable() as showAgent's slot branch -- this used
  // to independently do the wrong symbols(s)[slot] indexing here, so it
  // silently showed the wrong desk's data (or none) even after that exact
  // bug was fixed on the character-click path. Two entry points, one bug,
  // fixed in only one place the first time.
  const symMatch = /^sym-(\d+)$/.exec(obj.station || '');
  if (symMatch) {
    const slot = +symMatch[1];
    const group = deskSymbols(s, slot);
    const featured = mostActionable(group);
    const who = agents.find(a => a.def.slot === slot);
    const title = group.length === 1 ? `${group[0].symbol} desk` : `Desk ${slot + 1}`;
    let body = `<p class="lead">${esc(who ? who.detail : '')}</p>`;
    if (group.length) {
      for (const x of group) {
        const isFeatured = featured && x.symbol === featured.symbol;
        body += `<div class="rows" style="margin-top:${x === group[0] ? 0 : 8}px">`;
        if (group.length > 1) {
          body += `<div class="row"><span>${isFeatured ? '● ' : ''}${esc(x.symbol)}</span>` +
                   `<b style="font-weight:500">$${Number(x.price).toFixed(2)} · ${esc(x.zone)}</b></div>`;
        } else {
          body += row('Price', `$${Number(x.price).toFixed(2)}`);
          body += row('Zone', x.zone);
        }
        if (x.buy_low != null) body += row('Buy zone', `$${x.buy_low} – $${x.buy_high}`);
        if (x.target != null) body += row('Target', `$${x.target}`);
        if (x.distance_pct != null) body += row('Distance', `${x.distance_pct.toFixed(2)}%`);
        body += row('Zone width OK', x.narrow ? 'No — too narrow' : 'Yes');
        body += `</div>`;
      }
    } else {
      body += `<div class="rows">${row('Status', 'no live data')}</div>`;
    }
    return openPanel(title, 'Workstation', who ? who.level : 'idle', body);
  }

  if (key === 'eva-desk' && s) {
    html += `<div class="rows">`;
    html += row('Bot alive', s.bot_alive ? 'yes' : 'no');
    if (s.scan) {
      html += row('Scan', `#${s.scan.scan_num} at ${s.scan.time}`);
      if (s.scan.buying_power != null) html += row('Buying power', `$${s.scan.buying_power.toFixed(2)}`);
      if (s.scan.managed != null) html += row('Open positions', s.scan.managed);
    }
    html += `</div>`;
    if (s.market_update) html += `<h4>Read</h4><p class="lead">${esc(s.market_update)}</p>`;
  }

  if (key === 'scan' || obj.screen === 'scan') {
    html += `<div class="rows">`;
    html += row('Bot alive', s && s.bot_alive ? 'yes' : 'no');
    if (s && s.scan) {
      html += row('Scan', `#${s.scan.scan_num} at ${s.scan.time}`);
      if (s.scan.buying_power != null) html += row('Buying power', `$${s.scan.buying_power.toFixed(2)}`);
      if (s.scan.managed != null) html += row('Open positions', s.scan.managed);
      if (s.scan.room_for != null) html += row('Room for', `${s.scan.room_for} more`);
    } else {
      html += row('Scan', 'no data yet');
    }
    html += `</div>`;
  }

  if (key === 'breadth' || obj.screen === 'breadth') {
    html += `<div class="rows">`;
    if (s && s.scan && s.scan.breadth != null) {
      html += row('SPY breadth', `${s.scan.breadth > 0 ? '+' : ''}${s.scan.breadth}% from open`);
    } else {
      html += row('SPY breadth', 'no data yet');
    }
    html += `</div>`;
    if (s && s.market_update) html += `<h4>Eva's read</h4><p class="lead">${esc(s.market_update)}</p>`;
  }

  if (key === 'pnl' || obj.screen === 'pnl') {
    const trades = (s && s.todays_trades) || [];
    const wins = trades.filter(t => t['Win/Loss'] === 'WIN').length;
    const losses = trades.filter(t => t['Win/Loss'] === 'LOSS').length;
    html += `<div class="rows">`;
    html += row("Today's P&L", money(todaysPnl(s)));
    html += row('Trades today', trades.length);
    html += row('Win / Loss', `${wins} / ${losses}`);
    html += `</div>`;
  }

  if (key === 'zones' || obj.screen === 'zones') {
    const list = symbols(s);
    const inZone = list.filter(x => x.distance_pct === 0 && !x.narrow).length;
    const narrow = list.filter(x => x.narrow).length;
    html += `<div class="rows">`;
    html += row('Symbols tracked', list.length);
    html += row('In buy zone', inZone);
    html += row('Too narrow', narrow);
    html += `</div>`;
    if (list.length) {
      html += `<h4>All desks</h4><div class="rows">`;
      for (const x of list) {
        const flag = x.distance_pct === 0 && !x.narrow ? ' ⚡' : '';
        html += row(x.symbol, `${x.zone}${flag} · $${Number(x.price).toFixed(2)}`);
      }
      html += `</div>`;
    }
  }

  if (key === 'risk-desk' || obj.screen === 'risk') {
    const f = riskFlags(s);
    html += `<div class="rows">`;
    html += row('Weekly breaker', f.weekly || '—');
    html += row('Earnings blackout', f.blackout.length ? f.blackout.join(', ') : 'none');
    html += `</div>`;
  }

  if (key === 'records-desk') {
    const t = (s && s.recent_trades) || [];
    html += `<div class="rows">`;
    html += row("Today's P&L", money(todaysPnl(s)));
    html += row('All-time', money(totalPnl(s)));
    html += row('Trades logged', t.length);
    html += `</div>`;
    const rv = (s && s.todays_reviews) || [];
    if (rv.length) {
      html += `<h4>Today's trade reviews</h4><div class="rows">`;
      for (const r of rv) {
        html += row(`${r.Symbol} ${r.Reason || ''}`,
                    `designed ${r.DesignedRR || '—'} · realised ${r.RealizedR || '—'}`);
      }
      html += `</div>`;
    }
  }

  if (key === 'equity' || obj.screen === 'equity') {
    const curve = (s && s.equity_curve) || [];
    html += equityCurveSvg(curve);
    html += `<div class="rows" style="margin-top:8px">`;
    html += row('All-time P&L', money(totalPnl(s)));
    html += row('Trades logged', curve.length);
    html += `</div>`;
  }

  if (key === 'money-board') {
    const curve = (s && s.equity_curve) || [];
    const projects = (store.studio && store.studio.projects) || [];
    const shipped = projects.filter(p => p.current_stage === 'shipped');

    html += `<p class="lead">Everything this town exists to do, in one place.</p>`;
    html += `<h4>Trading</h4><div class="rows">`;
    html += row("Today's P&L", money(todaysPnl(s)));
    html += row('All-time P&L', money(totalPnl(s)));
    html += row('Trades logged', curve.length);
    html += `</div>`;

    html += `<h4>Archive Studio — ready to publish</h4>`;
    if (!shipped.length) {
      html += `<p class="lead">Nothing finished yet — no revenue waiting on a decision.</p>`;
    } else {
      html += `<div class="rows">`;
      for (const p of shipped) html += row(p.title, 'Finished — not published yet');
      html += `</div>`;
      html += `<div class="hint">${shipped.length} finished project${shipped.length === 1 ? '' : 's'} ` +
              `sitting in the warehouse, ready to upload. That work is already done and earning ` +
              `nothing until it's published — the only thing standing between it and real revenue ` +
              `is you hitting publish.</div>`;
    }
  }

  if (key === 'bench' || key === 'rack-a' || key === 'rack-b' || obj.screen === 'mechanic') {
    const m = activeMechanic(s);
    html += `<div class="rows">`;
    html += row('Last check', m ? m.status : 'none yet');
    html += row('Ran', m && m.last_run ? new Date(m.last_run).toLocaleString() : '—');
    html += `</div>`;
    if (m && m.summary) html += `<p class="lead">${esc(m.summary)}</p>`;
  }

  if (key === 'war-table' && s) return showMorningBriefing(s);

  openPanel(meta.title, 'Object', 'ok', html);
}

/**
 * One station in the Archive Studio -- Research Wall, Writers' Desk, Edit Bay,
 * Booth or Packaging Desk. Each maps to a real production stage, so this shows
 * which projects have a file backing that stage and which do not.
 */
export function showStudioStation(st) {
  const data = store.studio;
  let html = `<p class="lead">${esc(st.blurb || '')}</p>`;

  if (!data) {
    html += `<p class="lead">Studio state hasn't loaded yet.</p>`;
    return openPanel(st.name, 'Archive Studio', 'idle', html);
  }

  // The station id is the stage id in studio.py. The Edit Bay covers the
  // whole back half of the pipeline, so match generously.
  const projects = data.projects || [];
  const stageId = st.id === 'video' ? 'video' : st.id;

  // Three states, kept distinct on purpose:
  //   ✓  a real file on disk matches this stage
  //   ◐  implied -- a LATER stage has a file, so this must have happened,
  //      but nothing here names it. Inference, not evidence.
  //   ○  nothing yet
  html += `<h4>Across the slate</h4><div class="rows">`;
  let anyMissing = false, anyImplied = false;
  for (const p of projects) {
    const stage = (p.stages || {})[stageId];
    const hasFiles = !!(stage && stage.files && stage.files.length);
    const implied = !!(stage && stage.done && !hasFiles);
    if (!stage || !stage.done) anyMissing = true;
    if (implied) anyImplied = true;
    const mark = hasFiles ? '✓' : implied ? '◐' : '○';
    const ev = hasFiles ? stage.files.slice(0, 1).join(', ')
             : implied  ? 'implied by a later stage'
             : 'no file yet';
    html += `<div class="row"><span>${mark} ${esc(p.title)}</span>` +
            `<b style="font-weight:500;text-align:right">${esc(ev)}</b></div>`;
  }
  html += `</div>`;

  const task = (data.tasks || []).find(t => t.stage === stageId && t.state === 'todo');
  if (task) {
    html += `<h4>Open here</h4><p class="lead">${esc(task.project)} — ${esc(task.what)}. ` +
            `${esc(task.evidence)}.</p>`;
  } else if (!anyMissing && !anyImplied) {
    html += `<p class="lead">Every project has a real file backing this stage.</p>`;
  }

  if (anyImplied) {
    html += `<div class="hint">◐ means the stage is complete by inference only — a later
             stage has a file, so this must have happened, but no file names it.</div>`;
  }
  html += `<div class="hint">A stage counts as done only when a file on disk matches it.
           Read from <code>${esc(data.data_dir || '')}</code> and the channel folders.</div>`;

  openPanel(st.name, 'Archive Studio · station', anyMissing ? 'work' : 'ok', html);
}

/**
 * Open one real studio document in the panel.
 *
 * The text is inserted with textContent, never innerHTML -- these are files
 * off disk and must never be interpreted as markup.
 */
export async function showDocument(path, src = 'studio') {
  const endpoint = src === 'atm' ? '/api/atm/doc' : '/api/studio/doc';
  const label = src === 'atm' ? "Sage's ATM Co." : 'Archive Studio';
  openPanel('Opening…', label, 'idle', `<p class="lead">Reading the file…</p>`);
  let d;
  try {
    const res = await fetch(endpoint + '?p=' + encodeURIComponent(path),
                            { cache: 'no-store' });
    d = await res.json();
    if (d.error) throw new Error(d.error);
  } catch (e) {
    return openPanel('Could not open', label, 'alert',
                     `<p class="lead">${esc(e.message)}</p>`);
  }

  const kb = (d.size / 1024).toFixed(1);
  let html = `<div class="rows">`;
  html += row('Kind', d.kind);
  html += row('Size', `${kb} KB`);
  html += row('Modified', new Date(d.when).toLocaleString());
  html += `</div>`;
  if (d.truncated) {
    html += `<div class="hint">Showing the first part only — the file is larger than the read cap.</div>`;
  }
  html += `<h4>Contents</h4><pre class="doc-text" id="docText"></pre>`;
  html += `<div class="hint">Read straight from <code>${esc(d.path)}</code>.</div>`;

  openPanel(d.name, `${label} · ${d.kind}`, 'ok', html);
  const pre = el('docText');
  if (pre) pre.textContent = d.text;      // text, never markup
}

/* ---------------- activity log ---------------- */

// Real mechanic status string -> the same level vocabulary activity.js's
// character bubbles already use, so the log dot and a character's dot mean
// the same thing everywhere in this app.
const MECHANIC_LEVEL = { needs_attention: 'alert', fixed: 'warn', healthy: 'ok' };

export function renderLog(s) {
  const box = el('logList');
  if (!box) return;
  const lines = [];

  if (s && s.scan) lines.push([s.scan.time, `Scan #${s.scan.scan_num} — ${symbols(s).length} symbols checked`, 'ok']);
  for (const t of (s && s.todays_trades) || []) {
    const pnl = parseFloat(t['P&L']) || 0;
    lines.push([t.Time, `${t.Symbol} closed ${money(pnl)} (${t.Reason})`, pnl >= 0 ? 'ok' : 'warn']);
  }
  const f = s ? riskFlags(s) : null;
  if (f && f.blackout.length) lines.push(['—', `Earnings blackout: ${f.blackout.join(', ')}`, 'warn']);
  if (f && f.paused) lines.push(['—', 'Weekly win-rate breaker active — entries paused', 'alert']);

  // Every real mechanic check on record (morning/hourly/live-scan, or
  // whatever else exists), not just the single most-recent one -- so the
  // city's activity feed actually reflects that several different real
  // automated checks are running, each on its own schedule.
  for (const m of allMechanics(s)) {
    lines.push([
      m.last_run ? new Date(m.last_run).toLocaleTimeString() : '—',
      `${m.kind}: ${m.status}`,
      MECHANIC_LEVEL[m.status] || 'idle'
    ]);
  }

  // The Archive Studio keeps its own real event log (shift start/end, task
  // complete, status report written -- /api/studio's `activity`, already
  // fetched into store.studio). It logs the SAME event multiple times when
  // more than one project hits that event at once, which is real but
  // repetitive on screen -- collapsed here to one line per distinct
  // (time, event, detail), nothing invented or reworded. Scoped to today
  // (studio's own real `shift.day`, not the browser's clock) so this stays
  // "what happened today", same as the rest of the log.
  const studio = store.studio;
  const today = studio && studio.shift && studio.shift.day;
  if (studio && Array.isArray(studio.activity) && today) {
    const seen = new Set();
    for (const a of studio.activity) {
      if (a.date !== today) continue;
      const key = `${a.time}|${a.event}|${a.detail}`;
      if (seen.has(key)) continue;
      seen.add(key);
      const level = a.event === 'shift end' ? 'idle'
                  : a.event === 'task complete' ? 'ok'
                  : 'watch';
      lines.push([a.time, `Studio — ${a.detail}`, level]);
    }
  }

  box.innerHTML = lines.length
    ? lines.map(([t, msg, level]) =>
        `<div class="log-row"><span class="log-dot" style="background:${LEVEL_COLOR[level] || LEVEL_COLOR.idle}"></span><time>${esc(t)}</time><span>${esc(msg)}</span></div>`
      ).join('')
    : `<div class="log-row"><span class="muted">No activity yet today.</span></div>`;
}

/* ---------------- incident panel ---------------- */

/**
 * What happened, when, what the system attempted, and whether it recovered
 * -- built entirely from real fields already in incidentState()'s reasons
 * and the mechanic's own real last-run summary (which IS the "what was
 * attempted" record: the morning/hourly mechanic task writes exactly what
 * it checked and did, verbatim, every real run).
 */
export function showIncident(inc, s) {
  let html = '';
  if (!inc || !inc.active) {
    html = `<p class="lead">No active incident. This panel only opens when something real is wrong.</p>`;
    return openPanel('All clear', 'Incident', 'ok', html);
  }

  html += `<h4>What's wrong</h4><div class="rows">`;
  for (const r of inc.reasons) {
    html += `<div class="row"><span><i class="dot" style="background:${LEVEL_COLOR[r.severity] || LEVEL_COLOR.idle}"></i>${esc(r.id)}</span>` +
             `<b style="font-weight:500;text-align:right;max-width:66%">${esc(r.text)}</b></div>`;
  }
  html += `</div>`;

  const m = activeMechanic(s);
  if (m) {
    html += `<h4>What the mechanic attempted</h4>`;
    html += `<div class="rows">`;
    html += row('Last run', m.last_run ? new Date(m.last_run).toLocaleString() : 'never');
    html += row('Status', m.status || '—');
    html += `</div>`;
    html += `<p class="lead" style="margin-top:8px">${esc(m.summary || 'No summary recorded.')}</p>`;
    const recovered = m.status === 'healthy' || m.status === 'fixed';
    html += `<div class="hint">${recovered
      ? 'The mechanic\'s own last check reports this as resolved or healthy — if the banner is still up, a newer problem has appeared since.'
      : 'The mechanic has not reported a healthy result yet — this is still open.'}</div>`;
  } else {
    html += `<h4>What the mechanic attempted</h4><p class="lead">No health check has run today.</p>`;
  }

  const age = dataAgeSeconds(s);
  if (age != null) {
    html += `<div class="hint" style="margin-top:10px">Dashboard data is ${Math.round(age)}s old as of this panel opening.</div>`;
  }

  openPanel('Incident', 'Mission Control', inc.severity === 'alert' ? 'alert' : 'warn', html);
}

export function wirePanelChrome() {
  el('panelClose').onclick = closePanel;
  el('logToggle').onclick = () => el('logPanel').classList.toggle('collapsed');
  document.addEventListener('keydown', e => { if (e.key === 'Escape') closePanel(); });

  // Document rows are rebuilt on every panel render, so listen on the panel
  // body rather than binding each row.
  el('panelBody').addEventListener('click', e => {
    const row = e.target.closest('.doc-open');
    if (row && row.dataset.path) return showDocument(row.dataset.path, row.dataset.src || 'studio');

    const toggle = e.target.closest('.perm-toggle');
    if (toggle) {
      const next = toggle.dataset.next === 'true';
      toggle.disabled = true;
      toggle.textContent = next ? 'Granting…' : 'Revoking…';
      setAtmPermission(next)
        .then(() => refreshOpenPanel())
        .catch(err => { toggle.disabled = false; toggle.textContent = 'Failed — try again'; console.error(err); });
    }
  });
}
