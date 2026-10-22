/**
 * The complaint board behind the bar.
 *
 * Sal is fiction. The board is not: every item below is derived from a real
 * field the bot publishes. This is the one place that answers "what is
 * currently blocked, broken or annoying?" in a single list, which is exactly
 * the question that is otherwise spread across six rooms.
 *
 * Each complaint carries `who` (the person it affects), `what`, and a
 * severity that matches the same level vocabulary the characters use.
 */

import { symbols, riskFlags, activeMechanic, isMarketClosed } from '../state/store.js';
import { PEOPLE, STAFF } from './people.js';

const nameForSlot = slot => (PEOPLE[slot] && PEOPLE[slot].name) || `Desk ${slot + 1}`;

export function complaints(s) {
  const out = [];
  if (!s) {
    return [{ who: 'Sal', what: 'No data from the dashboard at all.', level: 'alert' }];
  }

  // --- the bot itself ---------------------------------------------------
  if (!s.bot_alive) {
    out.push({
      who: STAFF.eva.name,
      what: 'Bot is not running — nothing is being scanned.',
      level: isMarketClosed(s) ? 'idle' : 'alert'
    });
  }

  // --- risk gates -------------------------------------------------------
  const f = riskFlags(s);
  if (f.paused) {
    out.push({ who: STAFF.risk.name,
               what: `Weekly win-rate breaker is holding entries: ${f.weekly}`,
               level: 'alert' });
  }
  for (const b of f.blackout) {
    out.push({ who: STAFF.risk.name, what: `${b} — blacked out for earnings.`, level: 'warn' });
  }

  // --- per-symbol gripes ------------------------------------------------
  const syms = symbols(s);
  syms.forEach((x, i) => {
    if (x.narrow) {
      out.push({ who: nameForSlot(i),
                 what: `${x.symbol}'s zone is too narrow to trade.`, level: 'idle' });
    } else if (x.distance_pct != null && x.distance_pct > 5) {
      out.push({ who: nameForSlot(i),
                 what: `${x.symbol} is ${x.distance_pct.toFixed(1)}% above its buy zone.`,
                 level: 'idle' });
    }
  });

  // --- maintenance ------------------------------------------------------
  const m = activeMechanic(s);
  if (m && m.status === 'needs_attention') {
    out.push({ who: STAFF.mechanic.name, what: m.summary || 'Health check needs attention.', level: 'alert' });
  } else if (m && m.status === 'fixed') {
    out.push({ who: STAFF.mechanic.name, what: m.summary || 'Had to fix something this morning.', level: 'warn' });
  }

  // --- the day's results ------------------------------------------------
  const trades = s.todays_trades || [];
  const losers = trades.filter(t => (parseFloat(t['P&L']) || 0) < 0);
  for (const t of losers) {
    out.push({ who: 'Records', what: `${t.Symbol} closed down (${t['P&L']}).`, level: 'warn' });
  }
  if (!trades.length && isMarketClosed(s) && s.bot_alive !== undefined) {
    out.push({ who: 'Records', what: 'No trades taken today.', level: 'idle' });
  }

  const rank = { alert: 0, warn: 1, idle: 2 };
  return out.sort((a, b) => rank[a.level] - rank[b.level]);
}

/** What Sal says above the bar. */
export function baristaState(s) {
  const list = complaints(s);
  const urgent = list.filter(c => c.level === 'alert').length;
  const warn = list.filter(c => c.level === 'warn').length;
  if (!list.length) return { level: 'ok', bubble: '☕ Board is clear', count: 0 };
  if (urgent) return { level: 'alert', bubble: `📌 ${list.length} on the board`, count: list.length };
  if (warn) return { level: 'warn', bubble: `📌 ${list.length} on the board`, count: list.length };
  return { level: 'watch', bubble: `📌 ${list.length} gripes`, count: list.length };
}
