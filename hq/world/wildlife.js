/**
 * Ambient wildlife -- birds drifting across the sky, butterflies working
 * the park's flower beds. Purely decorative, daylight only (birds don't fly
 * at night, and the whole point is a livelier daytime city -- night already
 * has its own atmosphere via night.js). Drawn procedurally with canvas
 * paths rather than sprite frames, the same way the pond's ripples and
 * lily pads are, so a wingbeat can animate smoothly instead of stepping
 * between a handful of fixed poses.
 */
import { WORLD, PARK } from './hq-map.js';

const BIRD_COUNT = 5;

const rnd = (a, b) => a + Math.random() * (b - a);

export class Wildlife {
  constructor() {
    this.birds = Array.from({ length: BIRD_COUNT }, () => this._newBird());
    this.butterflies = PARK.flowers.map(f => ({
      home: { x: f.x, y: f.y, s: f.s },
      x: f.x, y: f.y,
      t: Math.random() * 100,
      speed: rnd(0.6, 1.1)
    }));
  }

  _newBird() {
    const eastbound = Math.random() < 0.5;
    const baseY = rnd(3, 20);
    return {
      x: eastbound ? -5 : WORLD.w + 5,
      baseY, y: baseY,
      dir: eastbound ? 1 : -1,
      speed: rnd(3.5, 6),
      wingPhase: Math.random() * Math.PI * 2,
      bobPhase: Math.random() * Math.PI * 2
    };
  }

  /** `daylight` -- pass !isDark(session) from the caller. */
  update(dt, daylight) {
    if (!daylight) return;
    for (const b of this.birds) {
      b.x += b.dir * b.speed * dt;
      b.wingPhase += dt * 9;
      b.bobPhase += dt * 1.4;
      b.y = b.baseY + Math.sin(b.bobPhase) * 1.2;
      if ((b.dir > 0 && b.x > WORLD.w + 6) || (b.dir < 0 && b.x < -6)) {
        Object.assign(b, this._newBird());
      }
    }
    for (const fl of this.butterflies) {
      fl.t += dt * fl.speed;
      fl.x = fl.home.x + Math.sin(fl.t) * 1.7 + Math.sin(fl.t * 2.3) * 0.4;
      fl.y = fl.home.y + Math.cos(fl.t * 0.8) * 1.1 - 0.6;
    }
  }

  draw(ctx, TILE, daylight) {
    if (!daylight) return;
    ctx.save();

    ctx.strokeStyle = 'rgba(28,24,18,.7)';
    ctx.lineWidth = 1.3;
    for (const b of this.birds) {
      const px = b.x * TILE, py = b.y * TILE;
      const flap = Math.sin(b.wingPhase) * 4;
      ctx.beginPath();
      ctx.moveTo(px - 5, py - flap);
      ctx.quadraticCurveTo(px - 2, py - flap - 3, px, py);
      ctx.quadraticCurveTo(px + 2, py - flap - 3, px + 5, py - flap);
      ctx.stroke();
    }

    for (const fl of this.butterflies) {
      const px = fl.x * TILE, py = fl.y * TILE;
      const wing = 2 + Math.abs(Math.sin(fl.t * 6)) * 2.2;
      ctx.fillStyle = fl.home.s === 'flower_a' ? 'rgba(222,96,118,.85)' : 'rgba(232,190,84,.85)';
      ctx.beginPath();
      ctx.ellipse(px - wing * 0.55, py, wing, wing * 0.7, 0.5, 0, Math.PI * 2);
      ctx.ellipse(px + wing * 0.55, py, wing, wing * 0.7, -0.5, 0, Math.PI * 2);
      ctx.fill();
    }

    ctx.restore();
  }
}
