/**
 * AgentSprite -- one reusable class for every character.
 *
 * There is deliberately no per-character subclass or per-character branch:
 * a character is a spritesheet plus a position plus a state. Phases 4-6 add
 * status, bubbles and alerts by setting fields on this object, not by
 * writing new drawing code for each agent.
 */

import { DIR } from './roster.js';

export const FRAME_W = 16;
export const FRAME_H = 24;
const TILE = 16;

/** Walk cycle order: stand, stepA, stand, stepB. */
const WALK_FRAMES = [0, 1, 0, 2];

export class AgentSprite {
  constructor(def, sheet) {
    this.def = def;
    this.id = def.id;
    this.sheet = sheet;

    // position is kept in TILE units as floats so Phase 5 can move between
    // tiles smoothly without changing anything here
    this.x = def.home.x;
    this.y = def.home.y;
    this.facing = def.facing || 'down';

    this.walking = false;
    this.animT = 0;
    this.phase = Math.random() * Math.PI * 2;   // desync idle bobs

    // driven by real /api/status data (see agents/activity.js)
    this.level = 'idle';
    this.bubble = '';
    this.detail = '';
    this.label = def.name;

    this.path = [];            // remaining tiles to walk
    this.speed = 3.2;          // tiles per second
  }

  /** Send the character somewhere. `path` comes from world/nav.js. */
  setPath(path) {
    this.path = path || [];
    this.walking = this.path.length > 0;
  }

  atHome() {
    return Math.abs(this.x - this.def.home.x) < 0.01 &&
           Math.abs(this.y - this.def.home.y) < 0.01;
  }

  update(dt) {
    this.animT += dt;
    if (!this.path.length) { this.walking = false; return; }

    this.walking = true;
    const next = this.path[0];
    const dx = next.x - this.x;
    const dy = next.y - this.y;
    const dist = Math.hypot(dx, dy);
    const step = this.speed * dt;

    if (dist <= step) {
      this.x = next.x;
      this.y = next.y;
      this.path.shift();
      if (!this.path.length) {
        this.walking = false;
        this.facing = this.def.facing || 'down';
      }
      return;
    }
    this.x += (dx / dist) * step;
    this.y += (dy / dist) * step;
    this.facing = Math.abs(dx) > Math.abs(dy)
      ? (dx > 0 ? 'right' : 'left')
      : (dy > 0 ? 'down' : 'up');
  }

  /** Which spritesheet column to draw right now. */
  frameIndex() {
    if (!this.walking) return 0;
    return WALK_FRAMES[Math.floor(this.animT * 8) % WALK_FRAMES.length];
  }

  /** A 1px idle bob so a standing character doesn't look frozen. */
  bob() {
    if (this.walking) return 0;
    return Math.sin(this.animT * 2.2 + this.phase) > 0.62 ? -1 : 0;
  }

  /** Feet sit on the bottom of the tile, so the head overhangs upward. */
  screenPos() {
    return {
      px: Math.round(this.x * TILE),
      py: Math.round(this.y * TILE + TILE - FRAME_H + this.bob())
    };
  }

  draw(ctx) {
    const col = this.frameIndex();
    const row = DIR[this.facing] ?? DIR.down;
    const { px, py } = this.screenPos();
    ctx.drawImage(
      this.sheet,
      col * FRAME_W, row * FRAME_H, FRAME_W, FRAME_H,
      px, py, FRAME_W, FRAME_H
    );
  }

  /** Tile-space bounds, used for click hit-testing in Phase 7. */
  bounds() {
    const { px, py } = this.screenPos();
    return { x: px, y: py, w: FRAME_W, h: FRAME_H };
  }
}

/** Build every sprite in a roster. */
export function createAgents(roster, sprites) {
  return roster.map(def => new AgentSprite(def, sprites[def.sheet]));
}
