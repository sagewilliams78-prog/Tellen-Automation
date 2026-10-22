/**
 * Night-time animation layer.
 *
 * Only runs when the session is actually dark (see lighting.js). The extra
 * "the building is shut" cues -- the security wash and the armed LED -- are
 * gated on the REAL bot state, so they appear when the bot is genuinely
 * offline rather than on a timer. Nothing here invents activity: an empty,
 * dark HQ should look empty and dark.
 *
 * Draw order matters. The session tint is a `multiply` pass, so anything
 * drawn before it gets darkened along with the world (good for soft pools
 * that should feel like part of the scene) and anything drawn after it stays
 * bright (good for point lights that should actually glow).
 */

import { TILE, WORLD, BUILDING, HOMES, ROOMS, CAFE, HOSPITAL, STUDIO, lampPositions } from './hq-map.js';

/** Deterministic PRNG -- the same city every reload, no flicker on refresh. */
function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

const inRect = (x, y, r, pad = 0) =>
  x >= r.x - pad && x < r.x + r.w + pad && y >= r.y - pad && y < r.y + r.h + pad;

export class NightFX {
  constructor(seed = 20260825) {
    const rnd = mulberry32(seed);
    this.t = 0;

    // ---- fireflies: only over open grass, never inside the HQ or a home ----
    this.flies = [];
    let guard = 0;
    while (this.flies.length < 46 && guard++ < 4000) {
      const x = rnd() * WORLD.w;
      const y = rnd() * WORLD.h;
      if (inRect(x, y, BUILDING, 1)) continue;
      if (HOMES.some(h => inRect(x, y, h.rect, 1))) continue;
      this.flies.push({
        x, y,
        // each drifts on its own slow lissajous rather than a shared sine,
        // which is what stops them reading as one pulsing group
        ax: 0.5 + rnd() * 1.4, ay: 0.4 + rnd() * 1.2,
        px: rnd() * Math.PI * 2, py: rnd() * Math.PI * 2,
        sp: 0.22 + rnd() * 0.38,
        blink: 0.5 + rnd() * 1.5,
        off: rnd() * Math.PI * 2,
        r: 1.1 + rnd() * 0.9
      });
    }

    // Positions come from hq-map.js's lampPositions() -- the same list
    // renderer.js draws the physical daytime post at, so the two never
    // drift apart. Only the flicker phase is added here.
    this.lamps = lampPositions().map(p => ({ ...p, ph: rnd() * Math.PI * 2 }));
  }

  update(dt) { this.t += dt; }

  /**
   * Soft, scene-integrated light. Drawn BEFORE the tint so it reads as part
   * of the world rather than sitting on top of it.
   */
  drawUnder(ctx, state) {
    const t = this.t;

    // lamp pools -- a faint mains hum, not a disco
    for (const l of this.lamps) {
      const flick = 0.9 + 0.1 * Math.sin(t * 2.3 + l.ph);
      const cx = l.x * TILE, cy = l.y * TILE;
      const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, 34);
      g.addColorStop(0, `rgba(255,226,160,${0.30 * flick})`);
      g.addColorStop(1, 'rgba(255,226,160,0)');
      ctx.fillStyle = g;
      ctx.fillRect(cx - 36, cy - 36, 72, 72);
      // the fitting itself
      ctx.fillStyle = '#2c2620';
      ctx.fillRect(cx - 1, cy - 1, 2, 5);
      ctx.fillStyle = `rgba(255,232,170,${0.85 * flick})`;
      ctx.fillRect(cx - 2, cy - 3, 4, 3);
    }

    // security wash -- ONLY while the bot is genuinely down. A slow band
    // sweeping the empty trading floor: the building is shut, not asleep.
    if (state && !state.bot_alive) {
      const cycle = (t * 0.16) % 1;
      const sx = (BUILDING.x + cycle * BUILDING.w) * TILE;
      const g = ctx.createLinearGradient(sx - 60, 0, sx + 60, 0);
      g.addColorStop(0, 'rgba(120,180,255,0)');
      g.addColorStop(0.5, 'rgba(120,180,255,.13)');
      g.addColorStop(1, 'rgba(120,180,255,0)');
      ctx.fillStyle = g;
      ctx.fillRect(BUILDING.x * TILE, BUILDING.y * TILE,
                   BUILDING.w * TILE, BUILDING.h * TILE);
    }
  }

  /**
   * Interior lighting.
   *
   * Drawn AFTER the tint with `lighter` compositing, which is the only way a
   * lit room actually reads brighter than the dark outside -- painting warm
   * pixels before a multiply pass just yields dim beige.
   *
   * Brightness follows real state, not the clock: an HQ room is properly lit
   * when the bot is alive or somebody is standing in it, and drops to a dim
   * security level otherwise. A dark, empty building should look dark and
   * empty.
   */
  drawInteriors(ctx, state, agents = []) {
    const occupied = r => agents.some(a =>
      a.x >= r.x && a.x < r.x + r.w && a.y >= r.y && a.y < r.y + r.h);

    const alive = !!(state && state.bot_alive);
    const spaces = [];

    for (const rm of ROOMS) {
      spaces.push({ rect: rm.rect, level: (alive || occupied(rm.rect)) ? 1 : 0.16 });
    }
    // the cafe idles low when nobody is in it; the hospital runs all night
    spaces.push({ rect: CAFE.interior, level: occupied(CAFE.interior) ? 0.85 : 0.2 });
    spaces.push({ rect: HOSPITAL.interior, level: 0.66 });
    // the studio burns the midnight oil while a project is still in progress
    spaces.push({ rect: STUDIO.interior, level: occupied(STUDIO.interior) ? 0.9 : 0.3 });
    for (const h of HOMES) {
      spaces.push({ rect: h.rect, level: occupied(h.rect) ? 0.9 : 0.1 });
    }

    ctx.save();
    ctx.globalCompositeOperation = 'lighter';
    for (const s of spaces) {
      if (s.level <= 0) continue;
      const { x, y, w, h } = s.rect;
      const px = x * TILE, py = y * TILE, pw = w * TILE, ph = h * TILE;

      // even warm wash across the floor
      ctx.fillStyle = `rgba(92,62,24,${0.34 * s.level})`;
      ctx.fillRect(px, py, pw, ph);

      // ceiling fixtures on a coarse grid, so big rooms get several
      for (let fx = x + 4; fx < x + w; fx += 8) {
        for (let fy = y + 4; fy < y + h; fy += 8) {
          const cx = fx * TILE, cy = fy * TILE;
          const g = ctx.createRadialGradient(cx, cy, 2, cx, cy, 46);
          g.addColorStop(0, `rgba(150,108,44,${0.30 * s.level})`);
          g.addColorStop(1, 'rgba(150,108,44,0)');
          ctx.fillStyle = g;
          ctx.fillRect(cx - 48, cy - 48, 96, 96);
          // the fitting itself
          ctx.fillStyle = `rgba(255,228,168,${0.5 * s.level})`;
          ctx.fillRect(cx - 2, cy - 1, 4, 2);
        }
      }
    }
    ctx.restore();
  }

  /**
   * Point lights. Drawn AFTER the tint so they survive the multiply pass and
   * actually glow against the dark.
   */
  drawOver(ctx, state) {
    const t = this.t;

    // fireflies
    for (const f of this.flies) {
      const x = (f.x + Math.sin(t * f.sp + f.px) * f.ax) * TILE;
      const y = (f.y + Math.cos(t * f.sp * 0.82 + f.py) * f.ay) * TILE;
      // long dark gaps, short bright flashes -- the shape of a real firefly
      const b = Math.pow(Math.max(0, Math.sin(t * f.blink + f.off)), 7);
      if (b < 0.02) continue;
      const g = ctx.createRadialGradient(x, y, 0, x, y, 7);
      g.addColorStop(0, `rgba(198,255,150,${0.85 * b})`);
      g.addColorStop(1, 'rgba(198,255,150,0)');
      ctx.fillStyle = g;
      ctx.fillRect(x - 8, y - 8, 16, 16);
      ctx.fillStyle = `rgba(226,255,190,${b})`;
      ctx.beginPath(); ctx.arc(x, y, f.r, 0, Math.PI * 2); ctx.fill();
    }

    // armed / offline LED on the HQ door -- steady red heartbeat, and only
    // when the bot really is offline
    if (state && !state.bot_alive) {
      const cx = (BUILDING.x + BUILDING.w / 2) * TILE;
      const cy = (BUILDING.y + BUILDING.h + 0.4) * TILE;
      const beat = Math.pow(Math.max(0, Math.sin(t * 1.9)), 3);
      const g = ctx.createRadialGradient(cx, cy, 0, cx, cy, 9);
      g.addColorStop(0, `rgba(255,70,58,${0.75 * beat})`);
      g.addColorStop(1, 'rgba(255,70,58,0)');
      ctx.fillStyle = g;
      ctx.fillRect(cx - 10, cy - 10, 20, 20);
      ctx.fillStyle = `rgba(255,96,80,${0.45 + 0.55 * beat})`;
      ctx.beginPath(); ctx.arc(cx, cy, 1.7, 0, Math.PI * 2); ctx.fill();
    }
  }
}
