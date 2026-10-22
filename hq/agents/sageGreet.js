/**
 * Sage-acknowledgment.
 *
 * When the player walks near a character, that character notices -- a short
 * chat bubble, same mechanism (and same `a.chat` field) as the ambient
 * banter in banter.js. Edge-triggered (fires once on approach, not every
 * frame while standing close) and gated the same way banter is: never during
 * an alert/warn state, and never stomping a conversation already in
 * progress. Purely social flavour -- never touches level/bubble, which stay
 * the real status.
 */

const NEAR = 3;              // tiles -- close enough to notice
const GREET_MS = 4000;       // how long the line stays up
const COOLDOWN_MS = 25000;   // don't re-greet the same person right away

const LINES = [
  'Hey, Sage!',
  'Oh -- hey!',
  "Didn't see you there.",
  'Boss is here.',
  'Afternoon.',
  'Hey there.',
  'Good to see you.',
  'Oh, hello!'
];

const pick = arr => arr[Math.floor(Math.random() * arr.length)];

export class SageGreeter {
  constructor() {
    this._wasNear = new Map();
    this._cooldownUntil = new Map();
    this.active = [];
  }

  tick(agents, player, now = Date.now()) {
    if (!player) return;

    for (const a of agents) {
      const near = Math.hypot(a.x - player.x, a.y - player.y) <= NEAR;
      const was = this._wasNear.get(a.id) || false;
      this._wasNear.set(a.id, near);
      if (!near || was) continue;                       // only far -> near edge
      if (a.level === 'alert' || a.level === 'warn') continue;  // never cover a real problem
      if (a.chat) continue;                              // don't interrupt banter
      if ((this._cooldownUntil.get(a.id) || 0) > now) continue;

      a.chat = pick(LINES);
      a.chatWith = player;
      const dx = player.x - a.x, dy = player.y - a.y;
      a.facing = Math.abs(dx) > Math.abs(dy) ? (dx > 0 ? 'right' : 'left') : (dy > 0 ? 'down' : 'up');
      this._cooldownUntil.set(a.id, now + COOLDOWN_MS);
      this.active.push({ agent: a, until: now + GREET_MS });
    }

    this.active = this.active.filter(c => {
      if (now < c.until) return true;
      if (c.agent.chat && c.agent.chatWith === player) {
        c.agent.chat = null;
        c.agent.chatWith = null;
      }
      return false;
    });
  }
}
