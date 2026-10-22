/**
 * WorldCamera -- pan / zoom over the HQ, in world pixels.
 *
 * Keeps pixel art crisp: zoom levels are whole numbers, and the renderer
 * disables image smoothing. The camera never scales by fractions, so a
 * source pixel always lands on an exact multiple of screen pixels.
 */

/**
 * Discrete zoom ladder. Whole numbers keep pixels exact; the fractions
 * still land source pixels on predictable screen pixels (quarter-pixel
 * steps at worst) and are needed because the city is larger than most
 * screens. The low end was widened when the world grew from 274x74 to
 * 480x190 (the Eastside expansion) -- 0.5 could no longer fit the whole
 * map on screen at once, so fitScale() silently fell back to a scale that
 * didn't actually fit. 0.15 fits the full width on anything down to a
 * ~1150px-wide view at TILE=16.
 */
export const ZOOM_STEPS = [0.15, 0.2, 0.25, 0.35, 0.5, 0.75, 1, 1.5, 2, 3, 4, 6];

export class WorldCamera {
  constructor(worldW, worldH, opts = {}) {
    this.worldW = worldW;               // world size in pixels
    this.worldH = worldH;
    this.minScale = opts.minScale ?? ZOOM_STEPS[0];
    this.maxScale = opts.maxScale ?? ZOOM_STEPS[ZOOM_STEPS.length - 1];
    this.scale = opts.scale ?? 1;
    this.x = 0;                         // top-left of the view, world px
    this.y = 0;
    this.viewW = 0;
    this.viewH = 0;
  }

  setViewport(w, h) {
    this.viewW = w;
    this.viewH = h;
    this.clamp();
  }

  /** Largest ladder step that still fits the whole world on screen. */
  fitScale() {
    if (!this.viewW || !this.viewH) return this.minScale;
    const s = Math.min(this.viewW / this.worldW, this.viewH / this.worldH);
    const usable = ZOOM_STEPS.filter(z => z <= s && z >= this.minScale);
    return usable.length ? usable[usable.length - 1] : this.minScale;
  }

  fit() {
    this.scale = this.fitScale();
    this.centerOn(this.worldW / 2, this.worldH / 2);
  }

  centerOn(wx, wy) {
    this.x = wx - this.viewW / (2 * this.scale);
    this.y = wy - this.viewH / (2 * this.scale);
    this.clamp();
  }

  /** Keep the view inside the world; centre an axis the world underfills. */
  clamp() {
    const visW = this.viewW / this.scale;
    const visH = this.viewH / this.scale;
    this.x = visW >= this.worldW
      ? (this.worldW - visW) / 2
      : Math.max(0, Math.min(this.x, this.worldW - visW));
    this.y = visH >= this.worldH
      ? (this.worldH - visH) / 2
      : Math.max(0, Math.min(this.y, this.worldH - visH));
  }

  panByScreen(dxScreen, dyScreen) {
    this.x -= dxScreen / this.scale;
    this.y -= dyScreen / this.scale;
    this.clamp();
  }

  /** Zoom one ladder step, keeping the point under the cursor stationary. */
  zoomAt(screenX, screenY, dir) {
    const i = ZOOM_STEPS.indexOf(this.scale);
    const base = i >= 0 ? i
      : ZOOM_STEPS.reduce((best, z, k) =>
          Math.abs(z - this.scale) < Math.abs(ZOOM_STEPS[best] - this.scale) ? k : best, 0);
    const ni = Math.max(0, Math.min(ZOOM_STEPS.length - 1, base + dir));
    const next = Math.max(this.minScale, Math.min(this.maxScale, ZOOM_STEPS[ni]));
    if (next === this.scale) return;
    const before = this.screenToWorld(screenX, screenY);
    this.scale = next;
    const after = this.screenToWorld(screenX, screenY);
    this.x += before.x - after.x;
    this.y += before.y - after.y;
    this.clamp();
  }

  screenToWorld(sx, sy) {
    return { x: this.x + sx / this.scale, y: this.y + sy / this.scale };
  }

  worldToScreen(wx, wy) {
    return { x: (wx - this.x) * this.scale, y: (wy - this.y) * this.scale };
  }

  /** Apply as a canvas transform: ctx.setTransform(...cam.transform()). */
  transform() {
    return [this.scale, 0, 0, this.scale,
            Math.round(-this.x * this.scale), Math.round(-this.y * this.scale)];
  }
}
