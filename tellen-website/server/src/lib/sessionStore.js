/**
 * Minimal in-memory per-session store for the chat proxy.
 *
 * Keyed strictly by sessionId so one visitor's conversation can never leak
 * into another's (session isolation). Entries expire automatically so this
 * never grows without bound. This is intentionally simple — if the real
 * n8n workflow owns conversation memory once connected, this store becomes
 * just a rate-limit/turn-count guard rather than the source of truth.
 */

const TTL_MS = 30 * 60 * 1000; // 30 minutes of inactivity
const MAX_TURNS_STORED = 10;
const MAX_SESSIONS = 5000; // hard cap so a flood of fake sessionIds can't exhaust memory

const sessions = new Map();

function touch(sessionId) {
  let s = sessions.get(sessionId);
  if (!s) {
    if (sessions.size >= MAX_SESSIONS) {
      // Evict the oldest entry rather than growing unbounded.
      const oldestKey = sessions.keys().next().value;
      if (oldestKey) sessions.delete(oldestKey);
    }
    s = { turns: [], lastSeen: Date.now(), messageCount: 0 };
    sessions.set(sessionId, s);
  }
  s.lastSeen = Date.now();
  return s;
}

function recordTurn(sessionId, role, text) {
  const s = touch(sessionId);
  s.turns.push({ role, text });
  if (s.turns.length > MAX_TURNS_STORED) s.turns.shift();
  if (role === "user") s.messageCount += 1;
  return s;
}

function getSession(sessionId) {
  return sessions.get(sessionId) || null;
}

function sweep() {
  const now = Date.now();
  for (const [id, s] of sessions) {
    if (now - s.lastSeen > TTL_MS) sessions.delete(id);
  }
}

const sweepInterval = setInterval(sweep, 5 * 60 * 1000);
sweepInterval.unref?.();

module.exports = { touch, recordTurn, getSession, _sessions: sessions, _sweep: sweep };
