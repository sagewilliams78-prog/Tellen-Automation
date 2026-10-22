/**
 * Seasonal weather layer.
 *
 * Purely ambient, same honesty rule as everywhere else in this world: it
 * represents something real (the actual current calendar month, Northern
 * Hemisphere) and nothing about bot state -- it never implies a scan, a
 * trade, or a health check happened. Added 2026-08-29 as part of the
 * "visual polish" pass.
 *
 * Draw order: over the world, under the session tint (drawLighting handles
 * that pass) so falling leaves/snow still dim correctly at night, same as
 * the fireflies in night.js.
 */

import { TILE, WORLD } from './hq-map.js';

function mulberry32(a) {
  return function () {
    a |= 0; a = (a + 0x6D2B79F5) | 0;
    let t = Math.imul(a ^ (a >>> 15), 1 | a);
    t = (t + Math.imul(t ^ (t >>> 7), 61 | t)) ^ t;
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

/** Real current season from the real current month -- Northern Hemisphere
 *  (this city runs on the US market clock everywhere else, so that's the
 *  consistent default). Returns null for spring/summer: not every season
 *  needs a weather effect, and adding rain/pollen would be inventing detail
 *  no real signal calls for. */
export function realSeason(now = new Date()) {
  const m = now.getMonth(); // 0 = Jan
  if (m === 11 || m === 0 || m === 1) return 'winter';   // Dec, Jan, Feb
  if (m >= 8 && m <= 10) return 'autumn';                 // Sep, Oct, Nov
  return null;
}

const AUTUMN_COLORS = ['#c9622b', '#d99a3d', '#b5471f', '#e0b23a'];
const WORLD_W_PX = WORLD.w * TILE;
const WORLD_H_PX = WORLD.h * TILE;

export class SeasonFX {
  constructor(season, seed = 20260901) {
    this.season = season;
    const rnd = mulberry32(seed);
    const count = season === 'winter' ? 90 : 55;
    this.particles = [];
    for (let i = 0; i < count; i++) {
      this.particles.push({
        x: rnd() * WORLD_W_PX,
        y: rnd() * WORLD_H_PX,
        r: season === 'winter' ? 1.4 + rnd() * 2.0 : 2.2 + rnd() * 2.4,
        speed: season === 'winter' ? 14 + rnd() * 18 : 20 + rnd() * 26,
        sway: 0.4 + rnd() * 1.1,
        phase: rnd() * Math.PI * 2,
        spin: rnd() * Math.PI * 2,
        spinSpeed: (rnd() - 0.5) * 2.2,
        colour: season === 'winter' ? '#f4f8ff' : AUTUMN_COLORS[i % AUTUMN_COLORS.length]
      });
    }
    this.t = 0;
  }

  update(dt) {
    this.t += dt;
    const h = WORLD_H_PX, w = WORLD_W_PX;
    for (const p of this.particles) {
      p.y += p.speed * dt;
      p.spin += p.spinSpeed * dt;
      if (p.y > h + 10) { p.y = -10; p.x = ((p.x + 137) % w + w) % w; } // re-seed x on wrap, deterministic
    }
  }

  draw(ctx) {
    for (const p of this.particles) {
      const sx = p.x + Math.sin(this.t * p.sway + p.phase) * (this.season === 'winter' ? 14 : 20);
      if (this.season === 'winter') {
        ctx.beginPath();
        ctx.fillStyle = p.colour;
        ctx.globalAlpha = 0.85;
        ctx.arc(sx, p.y, p.r, 0, Math.PI * 2);
        ctx.fill();
      } else {
        ctx.save();
        ctx.translate(sx, p.y);
        ctx.rotate(p.spin);
        ctx.fillStyle = p.colour;
        ctx.globalAlpha = 0.9;
        ctx.beginPath();
        ctx.ellipse(0, 0, p.r * 1.6, p.r, 0, 0, Math.PI * 2);
        ctx.fill();
        ctx.restore();
      }
      ctx.globalAlpha = 1;
    }
  }
}
