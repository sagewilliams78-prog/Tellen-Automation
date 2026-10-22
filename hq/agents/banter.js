/**
 * Ambient banter.
 *
 * Two rules keep this honest:
 *  1. Banter NEVER contains a market claim, a price, a P&L figure, or a
 *     prediction. Look in people.js -- the lines are about pens, coffee and
 *     chess. Real information always comes from the status bubble.
 *  2. Banter never runs when a character is in a warn/alert state, and never
 *     overwrites a real status. If something is wrong, you see the problem.
 */

import { personFor } from './people.js';
import { roomAt, CAFE, CONDO, HOMES } from '../world/hq-map.js';
import { topicForVenue, openerFor, replyFor, reactionFor } from './dialog.js';
import { isDark, currentSession } from '../world/lighting.js';

const inRect = (x, y, r) =>
  x >= r.x && x < r.x + r.w && y >= r.y && y < r.y + r.h;

/**
 * Which enclosed space someone is standing in. Conversation requires a shared
 * venue, so nobody shouts through a wall at the person in the next room.
 */
function venueOf(a) {
  const x = Math.round(a.x), y = Math.round(a.y);
  const room = roomAt(x, y);
  if (room) return 'room:' + room.id;
  if (inRect(x, y, CAFE.rect)) return 'cafe';
  for (const h of HOMES) {
    if (inRect(x, y, h.interior)) return 'home:' + h.slot;
  }
  if (inRect(x, y, CONDO.rect)) return 'condo-hall';
  return 'outdoors';
}

const CHAT_MS = 7000;        // how long one line stays up
const REPLY_MS = 2000;       // reply lands while the first line is STILL up,
                             // so the two bubbles overlap and read as a chat
const MIN_WAIT = 3000;       // shortest pause before a new conversation
const MAX_WAIT = 9000;
const NEAR = 9;              // tiles apart to be "in earshot"

const pick = arr => arr[Math.floor(Math.random() * arr.length)];

/** Turn `a` to look at `b`. This is the bit that makes them feel present. */
function faceToward(a, b) {
  const dx = b.x - a.x, dy = b.y - a.y;
  a.facing = Math.abs(dx) > Math.abs(dy)
    ? (dx > 0 ? 'right' : 'left')
    : (dy > 0 ? 'down' : 'up');
}

/** Everyone within earshot, nearest first. */
function neighbours(a, pool, range) {
  const here = venueOf(a);
  return pool
    .filter(o => o !== a &&
                 Math.hypot(o.x - a.x, o.y - a.y) <= range &&
                 venueOf(o) === here)          // same room only
    .sort((p, q) => Math.hypot(p.x - a.x, p.y - a.y) - Math.hypot(q.x - a.x, q.y - a.y));
}

export class Banter {
  constructor() {
    this.next = Date.now() + 1500;
    this.active = [];        // {agent, text, until}
    this._walking = new Map();   // agent id -> was walking last frame
  }

  /** May this character chat right now? */
  static canChat(a) {
    if (a.walking) return false;
    if (a.level === 'alert' || a.level === 'warn') return false;
    if (a.level === 'offline' && !a.homeWhat) return false;   // offline at a desk = say nothing
    return !!personFor(a.def);
  }

  /**
   * Someone who has just finished walking up to a group says hello, and the
   * nearest person turns and answers. This is what makes arrivals feel like
   * arrivals instead of characters silently teleporting into a room.
   */
  greetArrivals(agents, now) {
    for (const a of agents) {
      const was = this._walking.get(a.id);
      this._walking.set(a.id, a.walking);
      if (was !== true || a.walking) continue;          // only on the walk->stop edge
      if (!Banter.canChat(a) || a.chat) continue;
      const near = neighbours(a, agents.filter(Banter.canChat), NEAR)[0];
      if (!near || near.chat) continue;

      const p = personFor(a.def), np = personFor(near.def);
      if (!p || !np) continue;
      faceToward(a, near); faceToward(near, a);

      // Someone walking in opens with their own voice; the person already
      // there answers with a reaction, which reads as a reply to whatever was
      // actually said rather than a fresh unrelated remark.
      a.chat = pick(p.lines);
      a.chatWith = near;
      this.active.push({ agent: a, text: a.chat, until: now + CHAT_MS });
      setTimeout(() => {
        if (!Banter.canChat(near)) return;
        near.chat = reactionFor(np);
        near.chatWith = a;
        faceToward(near, a);
        this.active.push({ agent: near, text: near.chat, until: Date.now() + CHAT_MS });
      }, REPLY_MS);
      return;                                            // one greeting per tick
    }
  }

  /** Clear expired lines. Call every frame. */
  tick(agents) {
    const now = Date.now();
    for (const c of this.active) {
      if (now >= c.until) { c.agent.chat = null; c.agent.chatWith = null; }
    }
    this.active = this.active.filter(c => now < c.until);

    this.greetArrivals(agents, now);

    if (now < this.next) return;
    if (this.active.length >= 4) return;   // a few can talk at once
    this.start(agents, now);
  }

  start(agents, now) {
    const eligible = agents.filter(Banter.canChat);
    if (eligible.length < 1) { this.next = now + MIN_WAIT; return; }

    // Prefer somebody who actually has a neighbour, so conversations pair up
    // instead of people muttering to themselves across an empty room.
    const withCompany = eligible.filter(a => neighbours(a, eligible, NEAR).length);
    if (!withCompany.length) { this.next = now + MIN_WAIT; return; }  // nobody to talk to
    const speaker = pick(withCompany);
    const person = personFor(speaker.def);

    // the nearest person answers -- you talk to whoever you're standing with
    const listener = neighbours(speaker, eligible, NEAR)[0];
    if (!listener) { this.next = now + MIN_WAIT; return; }

    // The room picks the subject. Most exchanges run on a shared topic so the
    // reply answers the opener; the rest let the speaker use one of their own
    // signature lines, which the listener meets with a reaction.
    const topic = topicForVenue(venueOf(speaker), isDark(currentSession()));
    const useSignature = Math.random() < 0.35;
    const line = useSignature ? pick(person.lines) : (openerFor(topic) || pick(person.lines));

    speaker.chat = line;
    speaker.chatTopic = topic;
    this.active.push({ agent: speaker, text: line, until: now + CHAT_MS });

    speaker.chatWith = listener;              // renderer links the pair
    faceToward(speaker, listener);            // both turn to look at each other
    faceToward(listener, speaker);

    const lp = personFor(listener.def);
    const reply = useSignature ? reactionFor(lp)
                               : (replyFor(topic) || reactionFor(lp));
    setTimeout(() => {
      if (!Banter.canChat(listener)) return;
      listener.chat = reply;
      listener.chatWith = speaker;
      listener.chatTopic = topic;
      this.active.push({ agent: listener, text: reply, until: Date.now() + CHAT_MS });
    }, REPLY_MS);

    this.next = now + CHAT_MS + MIN_WAIT + Math.random() * (MAX_WAIT - MIN_WAIT);
  }
}
