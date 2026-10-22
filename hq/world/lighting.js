/**
 * Market-session lighting.
 *
 * The tint is derived from the real US market clock (America/New_York), so
 * the look of the city tells you the actual session at a glance. When the
 * bot reports the entry window closed, that overrides the clock -- the bot's
 * own view of the session beats our arithmetic about it.
 */

export const SESSIONS = {
  night:      { key: 'night',      label: 'Overnight',    tint: '#0b1236', alpha: 0.52 },
  premarket:  { key: 'premarket',  label: 'Pre-market',   tint: '#2a2f6b', alpha: 0.26 },
  open:       { key: 'open',       label: 'Market open',  tint: '#ffffff', alpha: 0.00 },
  power:      { key: 'power',      label: 'Power hour',   tint: '#ffb85c', alpha: 0.10 },
  afterhours: { key: 'afterhours', label: 'After hours',  tint: '#d97b3c', alpha: 0.20 },
  closed:     { key: 'closed',     label: 'Closed',       tint: '#101a3a', alpha: 0.42 }
};

/** Minutes since midnight in New York. */
export function etMinutes(now = new Date()) {
  const p = new Intl.DateTimeFormat('en-US', {
    timeZone: 'America/New_York', hour12: false,
    hour: 'numeric', minute: 'numeric', weekday: 'short'
  }).formatToParts(now).reduce((m, x) => (m[x.type] = x.value, m), {});
  return { mins: (+p.hour % 24) * 60 + (+p.minute), weekday: p.weekday };
}

export function currentSession(state) {
  const { mins, weekday } = etMinutes();
  const weekend = weekday === 'Sat' || weekday === 'Sun';

  if (weekend) return mins < 6 * 60 || mins >= 20 * 60 ? SESSIONS.night : SESSIONS.closed;

  if (mins < 4 * 60) return SESSIONS.night;
  if (mins < 9 * 60 + 30) return SESSIONS.premarket;
  if (mins < 15 * 60) return SESSIONS.open;
  if (mins < 16 * 60) return SESSIONS.power;          // final hour
  if (mins < 20 * 60) return SESSIONS.afterhours;
  return SESSIONS.night;
}

/** Is it dark enough that indoor lights would be on? */
export function isDark(session) {
  return session.key === 'night' || session.key === 'closed' || session.key === 'premarket';
}
