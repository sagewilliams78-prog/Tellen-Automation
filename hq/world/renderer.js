/**
 * Renderer -- draws the HQ.
 *
 * Architecture note (performance): the ground, floors, walls and doors never
 * change, so they are rasterised ONCE into an offscreen canvas the size of
 * the world. Each frame then blits that single bitmap through the camera
 * transform instead of re-tiling several thousand tiles. Only the dynamic
 * layer (agents, bubbles -- Phase 3+) is redrawn per frame.
 */

import { TILE, WORLD, BUILDING, ROOMS, CORRIDOR, WALLS, DOORS,
         STREETS, SIDEWALKS, ROAD_LINE, FREEWAY, HOMES, HOME_LAYOUT, UNIT_LAYOUT,
         PARK, CAFE, CONDO, HOSPITAL, STUDIO, TERRACE, HOME_STYLES, layoutFor,
         SAGE_HOME, BILLBOARD, lampPositions, ATM_CO, HOSPITAL_PARKING, HQ_PARKING, SUBURB,
         AVENUE, TOP_ST, TOWN_PARKING, STORE, NEWS_STUDIO, FIELD_OFFICE, BANK, TAX_OFFICE, PREDICT_DESK, SHOPS,
         TERMINAL, AIRPORT_RUNWAY, ownedPlacements } from './hq-map.js';
import { ROSTER } from '../agents/roster.js';
import { carSpriteFor } from './commute.js';
import { FURNITURE, SCREENS } from './furniture.js';
import { LEVEL_COLOR } from '../agents/activity.js';
import { isDark } from './lighting.js';
import { NightFX } from './night.js';
import { SeasonFX, realSeason } from './season.js';

const INK = '#1a1612';

export function loadSprites(names, base = 'sprites/') {
  return Promise.all(names.map(n => new Promise((resolve, reject) => {
    const img = new Image();
    img.onload = () => resolve([n, img]);
    img.onerror = () => reject(new Error('sprite failed to load: ' + n));
    img.src = `${base}${n}.png`;
  }))).then(pairs => Object.fromEntries(pairs));
}

export class Renderer {
  constructor(canvas, camera, sprites) {
    this.canvas = canvas;
    this.ctx = canvas.getContext('2d');
    this.cam = camera;
    this.sprites = sprites;
    this.static = null;
    this.hoverRoom = null;
    this.agents = [];          // dynamic layer, redrawn every frame
    this.buildStatic();
  }

  /** Fill a tile-rect with a repeating sprite. */
  static tileRect(ctx, sprite, rect) {
    for (let ty = 0; ty < rect.h; ty++) {
      for (let tx = 0; tx < rect.w; tx++) {
        ctx.drawImage(sprite, (rect.x + tx) * TILE, (rect.y + ty) * TILE);
      }
    }
  }

  buildStatic() {
    const w = WORLD.w * TILE, h = WORLD.h * TILE;
    const off = document.createElement('canvas');
    off.width = w; off.height = h;
    const c = off.getContext('2d');
    c.imageSmoothingEnabled = false;

    const S = this.sprites;

    // 1. ground everywhere
    Renderer.tileRect(c, S.grass, { x: 0, y: 0, w: WORLD.w, h: WORLD.h });

    // 1a. the Eastside Freeway, RAISED -- a drop-shadow on the grass below it
    // plus concrete support pillars at intervals, drawn before anything else
    // outdoors so the road itself (drawn next, with everything else) reads
    // as sitting above them. This is the one road in the city meant to look
    // elevated; every other street stays flat/at-grade.
    {
      const f = FREEWAY;
      const shadowDrop = 10;   // px -- how far "below grade" the shadow falls
      c.fillStyle = 'rgba(10,10,8,.35)';
      c.fillRect(f.x * TILE - 4, f.y * TILE + shadowDrop, (f.w) * TILE + 8, f.h * TILE);
      c.fillStyle = '#6b6258';                               // concrete pillars
      const pillarW = 6;
      for (let x = f.x + 4; x < f.x + f.w - 4; x += 14) {
        c.fillRect(x * TILE - pillarW / 2, f.y * TILE + f.h * TILE, pillarW, shadowDrop + 6);
      }
    }

    // 1b. the city outdoors: pavements, roads, park, homes
    for (const s of SIDEWALKS) Renderer.tileRect(c, S.sidewalk, s);
    for (const st of STREETS) Renderer.tileRect(c, S.asphalt, st);

    // dashed centre line -- the main road, plus the avenue and TOP_ST
    // (Sunrise Meadows' own street), so they read as real two-lane roads
    // rather than a plain grey connector. The avenue runs north-south, so
    // its dashes run the other way: vertical, down its own centre column.
    c.fillStyle = '#e6c84e';
    for (let x = ROAD_LINE.x0; x < ROAD_LINE.x1; x += 3) {
      c.fillRect(x * TILE, ROAD_LINE.y * TILE, TILE * 1.6, 3);
    }
    // The freeway's own edge stripes (safety white, not the dashed yellow
    // centre line every at-grade street gets) -- another cue that this
    // road is a different, elevated kind of thing.
    c.fillStyle = 'rgba(235,235,225,.85)';
    c.fillRect(FREEWAY.x * TILE, FREEWAY.y * TILE + 1, FREEWAY.w * TILE, 2);
    c.fillRect(FREEWAY.x * TILE, (FREEWAY.y + FREEWAY.h) * TILE - 3, FREEWAY.w * TILE, 2);
    {
      const topY = TOP_ST.y + TOP_ST.h / 2 - 0.1;
      for (let x = TOP_ST.x; x < TOP_ST.x + TOP_ST.w; x += 3) {
        c.fillRect(x * TILE, topY * TILE, TILE * 1.6, 3);
      }
      const aveX = AVENUE.x + AVENUE.w / 2 - 0.1;
      for (let y = AVENUE.y; y < AVENUE.y + AVENUE.h; y += 3) {
        c.fillRect(aveX * TILE, y * TILE, 3, TILE * 1.6);
      }
    }
    // Kerbs -- but only where a street edge actually meets grass. Drawing
    // one at every rect's own top/bottom, unconditionally, put a dark bar
    // straight across the avenue/TOP_ST junction where the two streets
    // actually flow into each other -- looked like a broken road. A tile is
    // only a real kerb if the row (or column, for a vertical street like
    // the avenue) just outside the street isn't itself part of another one.
    const isStreetTile = (x, y) => STREETS.some(s => x >= s.x && x < s.x + s.w && y >= s.y && y < s.y + s.h);
    c.fillStyle = 'rgba(20,18,14,.5)';
    for (const st of STREETS) {
      if (st.h > st.w) {
        for (let y = st.y; y < st.y + st.h; y++) {
          if (!isStreetTile(st.x - 1, y)) c.fillRect(st.x * TILE, y * TILE, 2, TILE);
          if (!isStreetTile(st.x + st.w, y)) c.fillRect((st.x + st.w) * TILE - 2, y * TILE, 2, TILE);
        }
      } else {
        for (let x = st.x; x < st.x + st.w; x++) {
          if (!isStreetTile(x, st.y - 1)) c.fillRect(x * TILE, st.y * TILE, TILE, 2);
          if (!isStreetTile(x, st.y + st.h)) c.fillRect(x * TILE, (st.y + st.h) * TILE - 2, TILE, 2);
        }
      }
    }

    // ---- the lake -------------------------------------------------------
    // Sand shore first, then water inset inside it, then ripples. Corners of
    // both are knocked off so it reads as a lake rather than a blue rectangle.
    {
      const P = PARK.pond;
      Renderer.tileRect(c, S.sidewalk, PARK.lakePath);          // path to it
      c.fillStyle = '#ded0a4';                                   // sand
      c.fillRect((P.x - 1) * TILE, (P.y - 1) * TILE, (P.w + 2) * TILE, (P.h + 2) * TILE);
      c.fillStyle = '#a8c47e';                                   // grass corners back
      const cw = TILE * 2;
      c.fillRect((P.x - 1) * TILE, (P.y - 1) * TILE, cw, cw);
      c.fillRect((P.x + P.w + 1) * TILE - cw, (P.y - 1) * TILE, cw, cw);
      c.fillRect((P.x - 1) * TILE, (P.y + P.h + 1) * TILE - cw, cw, cw);
      c.fillRect((P.x + P.w + 1) * TILE - cw, (P.y + P.h + 1) * TILE - cw, cw, cw);

      Renderer.tileRect(c, S.water, P);
      c.fillStyle = '#ded0a4';                                   // water corners
      c.fillRect(P.x * TILE, P.y * TILE, TILE, TILE);
      c.fillRect((P.x + P.w - 1) * TILE, P.y * TILE, TILE, TILE);
      c.fillRect(P.x * TILE, (P.y + P.h - 1) * TILE, TILE, TILE);
      c.fillRect((P.x + P.w - 1) * TILE, (P.y + P.h - 1) * TILE, TILE, TILE);

      c.strokeStyle = 'rgba(30,70,96,.55)';                      // waterline
      c.lineWidth = 2;
      c.strokeRect(P.x * TILE + 1, P.y * TILE + 1, P.w * TILE - 2, P.h * TILE - 2);

      c.strokeStyle = 'rgba(220,242,255,.4)';                    // ripples
      c.lineWidth = 1;
      for (let i = 0; i < 5; i++) {
        const ry = (P.y + 1.6 + i * 1.3) * TILE;
        c.beginPath();
        c.moveTo((P.x + 1.4) * TILE, ry);
        c.lineTo((P.x + P.w - 1.4) * TILE, ry);
        c.stroke();
      }
      c.fillStyle = '#4f9a5e';                                   // lily pads
      for (const [lx, ly] of [[2.4, 2.2], [5.1, 4.4], [9.3, 2.8], [7.2, 6.1], [11.2, 5.2]]) {
        c.beginPath();
        c.arc((P.x + lx) * TILE, (P.y + ly) * TILE, 5, 0, Math.PI * 2);
        c.fill();
      }
    }

    // --- interiors helper: fill, ring the walls, punch the doorway -------
    const shell = (rect, interior, doorway, floorSprite, accent) => {
      Renderer.tileRect(c, floorSprite, interior);
      for (let ty = rect.y; ty < rect.y + rect.h; ty++) {
        for (let tx = rect.x; tx < rect.x + rect.w; tx++) {
          const inIn = tx >= interior.x && tx < interior.x + interior.w &&
                       ty >= interior.y && ty < interior.y + interior.h;
          if (inIn) continue;
          const inDoor = doorway && tx >= doorway.x && tx < doorway.x + doorway.w &&
                         ty >= doorway.y && ty < doorway.y + doorway.h;
          c.drawImage(inDoor ? S.door : S.wall, tx * TILE, ty * TILE);
        }
      }
      c.strokeStyle = INK; c.lineWidth = 2;
      c.strokeRect(rect.x * TILE + 1, rect.y * TILE + 1, rect.w * TILE - 2, rect.h * TILE - 2);
      if (accent) {
        c.fillStyle = accent;
        c.fillRect(rect.x * TILE + 3, rect.y * TILE + 3, rect.w * TILE - 6, 3);
      }
    };

    // standalone houses on the street, plus Sal's flat by the cafe. Each gets
    // its own floor and its own furniture -- see HOME_STYLES in hq-map.js.
    for (const h of HOMES.filter(x => !x.unit)) {
      const style = HOME_STYLES[h.slot];
      Renderer.tileRect(c, S.sidewalk, h.driveway);
      shell(h.rect, h.interior, h.doorway,
            S[(style && style.floor) || 'floor_wood'] || S.floor_wood, h.accent);
      for (const f of layoutFor(h)) {
        const img = S[f.sprite];
        if (img) c.drawImage(img, (h.rect.x + f.dx) * TILE, (h.rect.y + f.dy) * TILE);
      }
    }

    // The Field Office -- same construction as the ATM Co./News Desk, south
    // of the street houses on ground that was empty all session. Doorway
    // faces SOUTH deliberately, away from the houses: two street homes
    // (x18-27, x32-41) sit directly north of this footprint, so a
    // north-facing door would open onto a house's back wall instead of open
    // ground. South opens onto genuinely empty grass down to the world edge
    // -- no sidewalk needed, walkable grass reaches it directly either way.
    shell(FIELD_OFFICE.rect, FIELD_OFFICE.interior, FIELD_OFFICE.doorway, S.floor_tile, FIELD_OFFICE.accent);
    for (const f of FIELD_OFFICE.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (FIELD_OFFICE.interior.x + f.dx) * TILE, (FIELD_OFFICE.interior.y + f.dy) * TILE);
    }

    // The Bank -- same construction and same south-facing-door reasoning as
    // the Field Office, a few tiles east of it in the same empty strip.
    shell(BANK.rect, BANK.interior, BANK.doorway, S.floor_tile, BANK.accent);
    for (const f of BANK.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (BANK.interior.x + f.dx) * TILE, (BANK.interior.y + f.dy) * TILE);
    }

    // The Tax Office -- same construction, same south strip.
    shell(TAX_OFFICE.rect, TAX_OFFICE.interior, TAX_OFFICE.doorway, S.floor_tile, TAX_OFFICE.accent);
    for (const f of TAX_OFFICE.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (TAX_OFFICE.interior.x + f.dx) * TILE, (TAX_OFFICE.interior.y + f.dy) * TILE);
    }

    // The Prediction Desk -- same standalone construction, its own quiet
    // corner east of everything else (see hq-map.js's own comment on why).
    shell(PREDICT_DESK.rect, PREDICT_DESK.interior, PREDICT_DESK.doorway, S.floor_tile, PREDICT_DESK.accent);
    for (const f of PREDICT_DESK.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (PREDICT_DESK.interior.x + f.dx) * TILE, (PREDICT_DESK.interior.y + f.dy) * TILE);
    }

    // Six empty storefronts along the Eastside -- generic loop, not six
    // hand-copied blocks (see hq-map.js's SHOPS comment).
    for (const shop of SHOPS) {
      shell(shop.rect, shop.interior, shop.doorway, S.floor_tile, shop.accent);
      for (const f of shop.layout) {
        const img = S[f.sprite];
        if (img) c.drawImage(img, (shop.interior.x + f.dx) * TILE, (shop.interior.y + f.dy) * TILE);
      }
    }

    // Smallville Regional -- the terminal, by far the biggest building here.
    // A cooler, polished concourse floor (not the warm office/home tile
    // every other building shares) plus real floor-to-ceiling windows along
    // the apron-facing wall -- the two cheapest, highest-impact cues that
    // read as "airport" rather than "generic office."
    shell(TERMINAL.rect, TERMINAL.interior, TERMINAL.doorway, S.floor_terminal, TERMINAL.accent);
    for (const f of TERMINAL.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (TERMINAL.interior.x + f.dx) * TILE, (TERMINAL.interior.y + f.dy) * TILE);
    }
    if (S.glass_wall) {
      const wallY = TERMINAL.rect.y + TERMINAL.rect.h - 1;     // the south wall row
      for (let tx = TERMINAL.rect.x; tx < TERMINAL.rect.x + TERMINAL.rect.w; tx++) {
        const atDoor = tx >= TERMINAL.doorway.x && tx < TERMINAL.doorway.x + TERMINAL.doorway.w;
        if (atDoor) continue;    // leave the real doorway alone
        c.drawImage(S.glass_wall, tx * TILE, wallY * TILE);
      }
    }

    // The runway -- real markings, not just plain asphalt (already tiled by
    // the generic STREETS loop above): a dashed centreline down its length
    // and threshold stripes at both ends, same visual language as a real
    // runway, drawn at genuinely huge scale next to every other building.
    {
      const r = AIRPORT_RUNWAY;
      const midY = (r.y + r.h / 2) * TILE;
      c.strokeStyle = 'rgba(255,255,255,.85)';
      c.lineWidth = 3;
      c.setLineDash([18, 14]);
      c.beginPath();
      c.moveTo((r.x + 6) * TILE, midY);
      c.lineTo((r.x + r.w - 6) * TILE, midY);
      c.stroke();
      c.setLineDash([]);
      c.fillStyle = 'rgba(255,255,255,.85)';
      for (const edgeX of [r.x + 4, r.x + r.w - 4]) {
        for (let i = -3; i <= 3; i++) {
          c.fillRect(edgeX * TILE, (r.y + r.h / 2 + i * 2) * TILE, TILE * 0.6, TILE * 0.9);
        }
      }
    }

    // Walkway from Wes's door down to the main street. Straight south is
    // blocked by the HQ building's own east wall and, further down, the
    // cafe -- the one gap between them (verified against nav.js's walkable
    // grid before drawing) is the x61-63 corridor, so the path drops out of
    // the doorway, jogs two tiles west into that corridor, then runs
    // straight down to the sidewalk at y47.
    {
      const wesHome = HOMES.find(h => h.slot === 14);
      if (wesHome) {
        const wy0 = wesHome.approach.y;                    // 17, just outside the door
        Renderer.tileRect(c, S.sidewalk, { x: 61, y: wy0, w: 6, h: 1 });   // jog west, x61-66
        Renderer.tileRect(c, S.sidewalk, { x: 61, y: wy0, w: 3, h: 47 - wy0 + 1 }); // down to y47
      }
    }

    // the condo block: outer shell, shared corridor, then each unit
    shell(CONDO.rect, { x: CONDO.rect.x + 1, y: CONDO.rect.y + 1,
                        w: CONDO.rect.w - 2, h: CONDO.rect.h - 2 },
          CONDO.entrance, S.floor_tile, CONDO.accent);
    Renderer.tileRect(c, S.floor_tile, CONDO.corridor);
    for (const h of HOMES.filter(x => x.unit && !x.terrace)) {
      const style = HOME_STYLES[h.slot];
      shell(h.rect, h.interior, h.doorway,
            S[(style && style.floor) || 'floor_wood'] || S.floor_wood, h.accent);
      for (const f of layoutFor(h)) {
        const img = S[f.sprite];
        if (img) c.drawImage(img, (h.interior.x + f.dx) * TILE, (h.interior.y + f.dy) * TILE);
      }
    }

    // The Darkroom -- the studio crew's terrace. One outer shell, then the
    // three units inside it, same construction as the condo block.
    shell(TERRACE.rect, TERRACE.interior, null, S.floor_wood, TERRACE.accent);
    for (const h of HOMES.filter(x => x.terrace)) {
      const style = HOME_STYLES[h.slot];
      Renderer.tileRect(c, S.sidewalk, h.driveway);
      shell(h.rect, h.interior, h.doorway,
            S[(style && style.floor) || 'floor_wood'] || S.floor_wood, h.accent);
      for (const f of layoutFor(h)) {
        const img = S[f.sprite];
        if (img) c.drawImage(img, (h.interior.x + f.dx) * TILE, (h.interior.y + f.dy) * TILE);
      }
    }
    // Paved route from the condo's west door down to the pavement. It stops
    // at y47 -- the earlier version ran 39 tiles and carried on through the
    // street and off the bottom of the map.
    {
      const px0 = CONDO.rect.x - 2, py0 = CONDO.rect.y + 8;   // beside the door
      const PAVEMENT_Y = 47;
      Renderer.tileRect(c, S.sidewalk, { x: px0, y: py0, w: 2, h: 3 });
      Renderer.tileRect(c, S.sidewalk,
        { x: px0, y: py0 + 2, w: 2, h: Math.max(0, PAVEMENT_Y - (py0 + 2) + 1) });
    }

    // the Archive Studio -- same construction as the hospital, wood floor
    shell(STUDIO.rect, STUDIO.interior, STUDIO.doorway, S.floor_wood, STUDIO.accent);
    for (const f of STUDIO.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (STUDIO.interior.x + f.dx) * TILE,
                                (STUDIO.interior.y + f.dy) * TILE);
    }
    // Walkway from the studio door down to the street. It cannot run straight
    // south -- the hospital occupies x118..139 from y32 -- so it drops out of
    // the doorway, jogs west, and then runs down the alley at x115..117, the
    // gap between the condos (which end at x114) and the hospital.
    //
    // The previous route turned west at y29 and ran to the lake path at x87.
    // That crossed x90..114, which is the CONDO footprint (x90..114, y28..46),
    // and because this draws after the homes it painted a pavement strip over
    // the building. The alley reaches the north sidewalk at y47 directly, so
    // the detour past the lake is not needed.
    const sy = STUDIO.rect.y + STUDIO.rect.h;              // y24, just outside the door
    Renderer.tileRect(c, S.sidewalk,
      { x: STUDIO.doorway.x, y: sy, w: 3, h: 7 });          // x123..125, y24..30
    Renderer.tileRect(c, S.sidewalk, { x: 115, y: 29, w: 11, h: 2 });  // jog west, y29..30
    Renderer.tileRect(c, S.sidewalk, { x: 115, y: 29, w: 3,  h: 19 }); // alley down to y47

    // The General Store -- the middle of town, on the strip between the
    // lake shore and the cafe's north wall. Same construction as every
    // other standalone building. Its door faces south and a short paved
    // apron runs from the threshold down to the cafe's roofline, so the
    // two places people actually go off-duty are a few steps apart.
    shell(STORE.rect, STORE.interior, STORE.doorway, S.floor_wood, STORE.accent);
    for (const f of STORE.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (STORE.interior.x + f.dx) * TILE, (STORE.interior.y + f.dy) * TILE);
    }
    Renderer.tileRect(c, S.sidewalk,
      { x: STORE.doorway.x - 1, y: STORE.rect.y + STORE.rect.h, w: 4, h: CAFE.rect.y - (STORE.rect.y + STORE.rect.h) });

    // Sage's ATM Company -- small storefront, same construction as her
    // house. Still just a plan (see _atm/status.json) -- the building
    // exists in the world before the real business does, same as the
    // Archive Studio's outline stage seeds a folder before real footage.
    shell(ATM_CO.rect, ATM_CO.interior, ATM_CO.doorway, S.floor_tile, ATM_CO.accent);
    for (const f of ATM_CO.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (ATM_CO.interior.x + f.dx) * TILE, (ATM_CO.interior.y + f.dy) * TILE);
    }

    // The News Desk -- same construction as the ATM Co. Bull & Bear's homes
    // sit south of it (slots 19-20, in the gap between them so a walkway
    // can run straight down without crossing either house).
    shell(NEWS_STUDIO.rect, NEWS_STUDIO.interior, NEWS_STUDIO.doorway, S.floor_wood, NEWS_STUDIO.accent);
    for (const f of NEWS_STUDIO.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (NEWS_STUDIO.interior.x + f.dx) * TILE, (NEWS_STUDIO.interior.y + f.dy) * TILE);
    }
    {
      // Door (x169-170) down to the gap between Bull's and Bear's houses
      // (x168-173), then straight down that gap to the main street at y47 --
      // never crosses either home's footprint (Bull: x158-167, Bear: x174-183).
      const ny0 = NEWS_STUDIO.approach.y;              // y20, just outside the door
      Renderer.tileRect(c, S.sidewalk, { x: 169, y: ny0, w: 3, h: 1 });      // jog to the gap
      Renderer.tileRect(c, S.sidewalk, { x: 171, y: ny0, w: 2, h: 47 - ny0 + 1 }); // down to y47
    }

    // Sage's house -- the owner's own place, same construction as the
    // hospital/studio. A short paved path connects its door to the open
    // grass between the street houses and here (no road runs this far
    // south, so grass is the walk -- see outdoorBlocked() in hq-map.js).
    Renderer.tileRect(c, S.sidewalk,
      { x: SAGE_HOME.doorway.x - 1, y: SAGE_HOME.approach.y, w: 4, h: 1 });
    shell(SAGE_HOME.rect, SAGE_HOME.interior, SAGE_HOME.doorway, S.floor_wood, SAGE_HOME.accent);
    for (const f of SAGE_HOME.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (SAGE_HOME.interior.x + f.dx) * TILE,
                                (SAGE_HOME.interior.y + f.dy) * TILE);
    }
    // A real paved walkway down from her door to the main street sidewalk
    // (y47) -- not just walkable grass. Straight south only as far as y27:
    // the condo block starts at y28 and runs x90-114, so going straight
    // down from here would run the path through the middle of a building.
    // Jogs east instead, at y27 (just above the condo), into the SAME
    // alley the Archive Studio already uses to reach the street (x115-117),
    // which was built with exactly this gap -- x115-117 sits in the space
    // between the condo (ends x114) and the hospital -- for this reason.
    {
      const SAGE_PATH_Y0 = SAGE_HOME.approach.y, JOG_Y = 27, ALLEY_X = 115, SAGE_STREET_Y = 47;
      Renderer.tileRect(c, S.sidewalk, { x: 100, y: SAGE_PATH_Y0, w: 3, h: JOG_Y - SAGE_PATH_Y0 + 1 });
      Renderer.tileRect(c, S.sidewalk, { x: 101, y: JOG_Y, w: ALLEY_X + 2 - 101, h: 1 });
      Renderer.tileRect(c, S.sidewalk, { x: ALLEY_X, y: JOG_Y, w: 3, h: SAGE_STREET_Y - JOG_Y + 1 });
    }

    // the hospital, same construction as the cafe
    shell(HOSPITAL.rect, HOSPITAL.interior, HOSPITAL.doorway, S.floor_tile, HOSPITAL.accent);
    for (const f of HOSPITAL.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (HOSPITAL.interior.x + f.dx) * TILE,
                                (HOSPITAL.interior.y + f.dy) * TILE);
    }
    Renderer.tileRect(c, S.sidewalk, { x: HOSPITAL.bay.x - 1, y: HOSPITAL.rect.y + HOSPITAL.rect.h, w: 4, h: 1 });

    // Smallville General's own staff lot -- directly east of the hospital,
    // on the ground the world gained when it was widened for exactly this
    // (see hq-map.js's HOSPITAL_PARKING comment). Plain asphalt, two spaces
    // side by side, with one short straight run of pavement down to the
    // main road. The cars themselves are NOT drawn here -- they're only
    // ever there because a doctor actually drove in this shift, so they're
    // drawn per-frame by drawCommuteCars(), same as the moving ones.
    if (S.asphalt) Renderer.tileRect(c, S.asphalt, HOSPITAL_PARKING.rect);
    {
      const lot = HOSPITAL_PARKING.rect;
      const linkX = lot.x + Math.floor(lot.w / 2) - 1;
      Renderer.tileRect(c, S.sidewalk, { x: linkX, y: lot.y + lot.h, w: 3, h: 47 - (lot.y + lot.h) + 1 });
    }

    // the coffee shop, built the same way as the homes
    Renderer.tileRect(c, S.floor_tile, CAFE.interior);
    for (let ty = CAFE.rect.y; ty < CAFE.rect.y + CAFE.rect.h; ty++) {
      for (let tx = CAFE.rect.x; tx < CAFE.rect.x + CAFE.rect.w; tx++) {
        const inIn = tx >= CAFE.interior.x && tx < CAFE.interior.x + CAFE.interior.w &&
                     ty >= CAFE.interior.y && ty < CAFE.interior.y + CAFE.interior.h;
        const inDoor = tx >= CAFE.doorway.x && tx < CAFE.doorway.x + CAFE.doorway.w &&
                       ty >= CAFE.doorway.y && ty < CAFE.doorway.y + CAFE.doorway.h;
        if (inIn) continue;
        c.drawImage(inDoor ? S.door : S.wall, tx * TILE, ty * TILE);
      }
    }
    c.strokeStyle = INK; c.lineWidth = 2;
    c.strokeRect(CAFE.rect.x * TILE + 1, CAFE.rect.y * TILE + 1,
                 CAFE.rect.w * TILE - 2, CAFE.rect.h * TILE - 2);
    // awning stripe over the entrance
    for (let i = 0; i < CAFE.rect.w - 2; i++) {
      c.fillStyle = i % 2 ? '#f4ecd8' : CAFE.accent;
      c.fillRect((CAFE.rect.x + 1 + i) * TILE, (CAFE.rect.y + CAFE.rect.h - 1) * TILE + 10, TILE, 4);
    }
    for (const f of CAFE.layout) {
      const img = S[f.sprite];
      if (img) c.drawImage(img, (CAFE.interior.x + f.dx) * TILE, (CAFE.interior.y + f.dy) * TILE);
    }

    for (const f of PARK.flowers) c.drawImage(S[f.s], f.x * TILE, f.y * TILE);
    for (const b of PARK.benches) c.drawImage(S.bench_out, b.x * TILE, b.y * TILE);
    for (const t of PARK.trees) c.drawImage(S.tree_big, t.x * TILE, t.y * TILE);

    // 2. sidewalk ring one tile outside the building, plus an approach path
    const ring = { x: BUILDING.x - 1, y: BUILDING.y - 1, w: BUILDING.w + 2, h: BUILDING.h + 2 };
    for (let ty = ring.y; ty < ring.y + ring.h; ty++) {
      for (let tx = ring.x; tx < ring.x + ring.w; tx++) {
        const inside = tx >= BUILDING.x && tx < BUILDING.x + BUILDING.w &&
                       ty >= BUILDING.y && ty < BUILDING.y + BUILDING.h;
        if (!inside) c.drawImage(S.sidewalk, tx * TILE, ty * TILE);
      }
    }
    Renderer.tileRect(c, S.sidewalk, { x: 0, y: 21, w: BUILDING.x - 1, h: 3 }); // approach

    // The money billboard -- combined real P&L + unpublished-inventory
    // status, right by the staff-door commute route so it's actually seen.
    c.drawImage(S.billboard, BILLBOARD.x * TILE, BILLBOARD.y * TILE);

    // Curbside spots for Otis and Margo, flanking the billboard. No shared
    // lot shell, just a short straight run of pavement down to the road at
    // each spot's own column -- the cars themselves are drawn per-frame by
    // drawCommuteCars(), same as the hospital's, only ever there because
    // someone actually drove in.
    for (const spot of HQ_PARKING.spots) {
      Renderer.tileRect(c, S.sidewalk, { x: spot.x, y: spot.y, w: spot.w, h: 47 - spot.y + 1 });
    }

    // Downtown visitor lot, in the corridor between the cafe and the condo
    // block -- where a Sunrise Meadows resident actually parks on a trip
    // into town. Asphalt down the whole run so it reads as a lot, with
    // painted bay lines; the cars themselves are drawn per-frame by
    // drawCommuteCars(), only there when someone genuinely drove in.
    {
      const first = TOWN_PARKING.spots[0];
      const last = TOWN_PARKING.spots[TOWN_PARKING.spots.length - 1];
      const lot = { x: first.x, y: first.y - 1, w: first.w, h: (last.y + last.h) - first.y + 2 };
      if (S.asphalt) Renderer.tileRect(c, S.asphalt, lot);
      c.fillStyle = 'rgba(232,226,200,.5)';
      for (const spot of TOWN_PARKING.spots) {
        c.fillRect(spot.x * TILE, spot.y * TILE - 1, spot.w * TILE, 2);
      }
    }

    // Streetlamp posts -- night.js already lights these exact spots after
    // dark; this is just the physical post so the street isn't bare by day.
    // `l.y` is where the post plants its base (the sidewalk position), and
    // the sprite is 3 tiles tall, so its BOTTOM edge has to land on l.y --
    // anchoring from the top (as this originally did) put the base ~2.5
    // tiles further south than intended, which for the north-kerb lamps
    // landed it in the middle of the road instead of on the sidewalk.
    if (S.streetlamp) {
      const LAMP_TILES_TALL = 3;
      for (const l of lampPositions()) {
        c.drawImage(S.streetlamp, (l.x - 0.5) * TILE, (l.y - LAMP_TILES_TALL) * TILE);
      }
    }

    // 3. room floors + corridor
    for (const r of ROOMS) Renderer.tileRect(c, S[r.floor], r.rect);
    Renderer.tileRect(c, S.floor_tile, CORRIDOR);

    // 4. walls -- sprite fill, then a hard outline so rooms read clearly
    for (const w of WALLS) {
      Renderer.tileRect(c, S.wall, w);
      c.strokeStyle = INK;
      c.lineWidth = 2;
      c.strokeRect(w.x * TILE + 1, w.y * TILE + 1, w.w * TILE - 2, w.h * TILE - 2);
    }

    // 5. doors punch through the walls drawn above
    for (const d of DOORS) Renderer.tileRect(c, S.door, d);

    // 6. furniture, drawn in listed order so rugs land under objects.
    //    Each sprite is placed once at its natural size -- no tiling.
    for (const f of FURNITURE) {
      const img = S[f.sprite];
      if (!img) continue;
      c.drawImage(img, f.x * TILE, f.y * TILE);
    }

    this.static = off;
  }

  draw() {
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.imageSmoothingEnabled = false;
    ctx.fillStyle = '#4f7a3f';                       // out-of-world backdrop
    ctx.fillRect(0, 0, this.canvas.width / dpr, this.canvas.height / dpr);

    const t = this.cam.transform();   // [a, b, c, d, e, f] -- d is at index 3
    ctx.setTransform(t[0] * dpr, 0, 0, t[3] * dpr, t[4] * dpr, t[5] * dpr);
    ctx.imageSmoothingEnabled = false;

    ctx.drawImage(this.static, 0, 0);

    if (this.hoverRoom) {
      const { x, y, w, h } = this.hoverRoom.rect;
      ctx.fillStyle = 'rgba(255,255,255,.13)';
      ctx.fillRect(x * TILE, y * TILE, w * TILE, h * TILE);
      ctx.strokeStyle = this.hoverRoom.accent;
      ctx.lineWidth = 2;
      ctx.strokeRect(x * TILE + 1, y * TILE + 1, w * TILE - 2, h * TILE - 2);
    }

    this.drawScreens(ctx);
    this.drawAgents(ctx);
    this.drawCars(ctx);
    this.drawPlane(ctx);
    this.drawAmbulances(ctx);
    this.drawCommuteCars(ctx);
    this.drawOwnedGoods(ctx);
    if (this.wildlife) this.wildlife.draw(ctx, TILE, !!this.session && !isDark(this.session));
    this.drawEffects(ctx);
    this.drawSeason(ctx);        // real-calendar weather, over the world, under the tint
    this.drawLighting(ctx);      // over the world, under the UI
    this.drawBeacon(ctx);
    this.drawLabels();
    this.drawAgentTags();
  }

  /**
   * Session tint. Also lights the windows of any home with someone in it
   * once it is dark, which is why the neighbourhood glows overnight.
   */
  drawLighting(ctx) {
    const s = this.session;
    if (!s) return;

    const dark = isDark(s);
    if (dark && !this.night) this.night = new NightFX();

    if (dark) {                            // warm pools before the tint lands
      ctx.globalCompositeOperation = 'source-over';
      for (const h of HOMES) {
        const occupied = this.agents.some(a =>
          a.x >= h.rect.x && a.x < h.rect.x + h.rect.w &&
          a.y >= h.rect.y && a.y < h.rect.y + h.rect.h);
        if (!occupied) continue;
        const g = ctx.createRadialGradient(
          (h.rect.x + h.rect.w / 2) * TILE, (h.rect.y + h.rect.h / 2) * TILE, 8,
          (h.rect.x + h.rect.w / 2) * TILE, (h.rect.y + h.rect.h / 2) * TILE, h.rect.w * TILE * 0.7);
        g.addColorStop(0, 'rgba(255,208,120,.42)');
        g.addColorStop(1, 'rgba(255,208,120,0)');
        ctx.fillStyle = g;
        ctx.fillRect(h.rect.x * TILE - 20, h.rect.y * TILE - 20,
                     h.rect.w * TILE + 40, h.rect.h * TILE + 40);
      }
      // Sage's own house glows the same way when she's home
      if (this.player &&
          this.player.x >= SAGE_HOME.rect.x && this.player.x < SAGE_HOME.rect.x + SAGE_HOME.rect.w &&
          this.player.y >= SAGE_HOME.rect.y && this.player.y < SAGE_HOME.rect.y + SAGE_HOME.rect.h) {
        const g = ctx.createRadialGradient(
          (SAGE_HOME.rect.x + SAGE_HOME.rect.w / 2) * TILE, (SAGE_HOME.rect.y + SAGE_HOME.rect.h / 2) * TILE, 8,
          (SAGE_HOME.rect.x + SAGE_HOME.rect.w / 2) * TILE, (SAGE_HOME.rect.y + SAGE_HOME.rect.h / 2) * TILE, SAGE_HOME.rect.w * TILE * 0.7);
        g.addColorStop(0, 'rgba(255,208,120,.42)');
        g.addColorStop(1, 'rgba(255,208,120,0)');
        ctx.fillStyle = g;
        ctx.fillRect(SAGE_HOME.rect.x * TILE - 20, SAGE_HOME.rect.y * TILE - 20,
                     SAGE_HOME.rect.w * TILE + 40, SAGE_HOME.rect.h * TILE + 40);
      }
      // the HQ keeps its lights on whenever the bot is running
      if (this.state && this.state.bot_alive) {
        const g = ctx.createRadialGradient(
          (BUILDING.x + BUILDING.w / 2) * TILE, (BUILDING.y + BUILDING.h / 2) * TILE, 40,
          (BUILDING.x + BUILDING.w / 2) * TILE, (BUILDING.y + BUILDING.h / 2) * TILE, BUILDING.w * TILE * 0.6);
        g.addColorStop(0, 'rgba(255,214,140,.30)');
        g.addColorStop(1, 'rgba(255,214,140,0)');
        ctx.fillStyle = g;
        ctx.fillRect(BUILDING.x * TILE, BUILDING.y * TILE, BUILDING.w * TILE, BUILDING.h * TILE);
      }
      this.night.drawUnder(ctx, this.state);   // lamps + security sweep
    }

    if (s.alpha <= 0) return;
    ctx.globalCompositeOperation = 'multiply';
    ctx.globalAlpha = s.alpha;
    ctx.fillStyle = s.tint;
    ctx.fillRect(0, 0, WORLD.w * TILE, WORLD.h * TILE);
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = 'source-over';

    // interiors + point lights go over the tint so they read as light, not paint
    if (dark) {
      this.night.drawInteriors(ctx, this.state, this.agents);
      this.night.drawOver(ctx, this.state);
    }
  }

  /**
   * Rooftop beacon. Red when something is actually broken, amber when an
   * entry gate is holding, otherwise a slow green. Readable at 0.5x, which
   * is the point -- problems should find you.
   */
  drawBeacon(ctx) {
    const s = this.state;
    const cx = (BUILDING.x + BUILDING.w / 2) * TILE;
    const cy = (BUILDING.y - 1) * TILE + 4;

    let colour = '#4fbf6a', speed = 1.2, urgent = false;
    if (!s) { colour = '#6a6a72'; }
    else if (!s.bot_alive && this.session && this.session.key === 'open') { colour = '#e0503c'; speed = 5; urgent = true; }
    else if (this.beaconLevel === 'alert') { colour = '#e0503c'; speed = 5; urgent = true; }
    else if (this.beaconLevel === 'warn') { colour = '#e08b3c'; speed = 2.6; }
    else if (!s.bot_alive) { colour = '#6a6a72'; speed = 0; }

    const t = this.beaconT || 0;
    const pulse = speed ? 0.45 + 0.55 * Math.abs(Math.sin(t * speed)) : 0.5;

    // mast
    ctx.fillStyle = '#3a3128';
    ctx.fillRect(cx - 1, cy, 2, 12);
    // glow
    const g = ctx.createRadialGradient(cx, cy, 1, cx, cy, urgent ? 26 : 16);
    g.addColorStop(0, colour);
    g.addColorStop(1, 'rgba(0,0,0,0)');
    ctx.globalAlpha = pulse * 0.75;
    ctx.fillStyle = g;
    ctx.beginPath(); ctx.arc(cx, cy, urgent ? 26 : 16, 0, Math.PI * 2); ctx.fill();
    ctx.globalAlpha = 1;
    // lamp
    ctx.fillStyle = colour;
    ctx.beginPath(); ctx.arc(cx, cy, 3.2, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = '#15120e'; ctx.lineWidth = 1; ctx.stroke();
  }

  /** Traffic, plus a HONK when it has just startled somebody. */
  drawCars(ctx) {
    const allCars = [
      ...(this.traffic ? this.traffic.cars : []),
      ...(this.freewayTraffic ? this.freewayTraffic.cars : [])
    ];
    for (const car of allCars) {
      const img = this.sprites[car.sprite];
      if (!img) continue;
      const px = car.x * TILE, py = car.y * TILE;
      ctx.save();
      if (car.dir < 0) {                      // flip for westbound
        ctx.translate(px + img.width, py);
        ctx.scale(-1, 1);
        ctx.drawImage(img, 0, 0);
      } else {
        ctx.drawImage(img, px, py);
      }
      ctx.restore();

      if (Date.now() < car.honkUntil) {
        ctx.font = '700 11px ui-monospace, monospace';
        ctx.textAlign = 'center';
        ctx.lineWidth = 3;
        ctx.strokeStyle = 'rgba(10,8,6,.9)';
        ctx.strokeText('HONK!', px + 32, py - 6);
        ctx.fillStyle = '#ffd45c';
        ctx.fillText('HONK!', px + 32, py - 6);
        ctx.textAlign = 'left';
      }
    }
  }

  /**
   * Smallville Regional's one ambient plane (see world/airport_ops.js's own
   * header -- pure scenery, not a real flight). Drawn the same
   * flip-for-direction way as the cars above, just a bigger sprite on its
   * own runway rather than the street.
   */
  drawPlane(ctx) {
    const ops = this.airportOps;
    if (!ops || !ops.visible) return;
    const img = this.sprites.plane;
    if (!img) return;
    const px = ops.x * TILE, py = ops.y * TILE;
    ctx.save();
    if (ops.facingRight) {
      ctx.drawImage(img, px, py);
    } else {
      ctx.translate(px + img.width, py);
      ctx.scale(-1, 1);
      ctx.drawImage(img, 0, 0);
    }
    ctx.restore();
  }

  /** Ambulances, with a flashing light bar while the siren is on. */
  drawAmbulances(ctx) {
    if (!this.ems) return;
    const img = this.sprites.ambulance;
    if (!img) return;
    for (const u of this.ems.units) {
      const px = u.x * TILE, py = u.y * TILE;
      ctx.save();
      if (u.dir < 0) { ctx.translate(px + img.width, py); ctx.scale(-1, 1); ctx.drawImage(img, 0, 0); }
      else ctx.drawImage(img, px, py);
      ctx.restore();

      if (u.siren) {
        const on = Math.floor(Date.now() / 220) % 2 === 0;
        ctx.fillStyle = on ? '#ff5a4a' : '#6f9cff';
        ctx.beginPath(); ctx.arc(px + 32, py - 5, 5, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = .35;
        ctx.beginPath(); ctx.arc(px + 32, py - 5, 12, 0, Math.PI * 2); ctx.fill();
        ctx.globalAlpha = 1;
      }
    }
  }

  /**
   * The two doctors' own commute cars -- unhurried, no siren, no honking.
   * Unlike Traffic/EMS (a single fixed lane, so only ever left/right), this
   * one really turns corners -- out the driveway, down the avenue, along
   * the main road, into the lot -- so it needs a vertical orientation too.
   * u.x/u.y are treated as the car's CENTRE (not top-left) precisely so
   * horizontal and vertical drawing can share the same rotation math.
   */
  drawCommuteCars(ctx) {
    if (!this.commute) return;
    const drawAt = (img, cx, cy, orient, dirSign) => {
      ctx.save();
      ctx.translate(cx, cy);
      if (orient === 'v') ctx.rotate(dirSign < 0 ? -Math.PI / 2 : Math.PI / 2);
      else if (dirSign < 0) ctx.scale(-1, 1);
      ctx.drawImage(img, -img.width / 2, -img.height / 2);
      ctx.restore();
    };
    for (const u of this.commute.units.values()) {
      const img = this.sprites[carSpriteFor(u.doctor)];
      if (img) drawAt(img, u.x * TILE, u.y * TILE, u.orient, u.dirSign);
    }
    // Parked all shift, not moving -- drawn plainly, facing into the spot.
    for (const spot of this.commute.parked.values()) {
      const img = this.sprites[spot.sprite];
      if (img) ctx.drawImage(img, spot.x * TILE, spot.y * TILE);
    }
  }

  /**
   * Everything the town has actually bought from the General Store.
   *
   * Drawn in the DYNAMIC layer rather than baked into the static bitmap on
   * purpose: ownership changes on payday, and redrawing the whole world
   * bitmap for a new bookshelf would be silly. It is only a handful of
   * sprites, and this way a purchase shows up the moment it happens.
   *
   * `this.sim` is set from the real /api/sim payload in main.js -- when it
   * hasn't loaded, nothing is drawn rather than anything being guessed.
   */
  drawOwnedGoods(ctx) {
    if (!this.sim || !this.sim.residents) return;
    for (const r of this.sim.residents) {
      const def = ROSTER.find(d => d.id === r.id);
      if (!def) continue;
      // Named staff carry `homeSlot`; the seven watchlist-desk characters
      // instead key their home off `slot` (see activity.js's symbolState,
      // which returns `goto: { home: slot }`). Checking only homeSlot meant
      // seven of the seventeen residents' purchases never drew at all.
      const slot = def.homeSlot ?? def.slot;
      if (slot == null) continue;
      const home = HOMES.find(h => h.slot === slot);
      if (!home) continue;
      for (const p of ownedPlacements(home, r.owned.map(o => o.id))) {
        const img = this.sprites[p.sprite];
        if (!img) continue;
        if (p.frame) {
          // an animal sheet: take the first (front-facing) 16x24 frame
          ctx.drawImage(img, 0, 0, 16, 24, p.x * TILE, p.y * TILE - 8, 16, 24);
        } else {
          ctx.drawImage(img, p.x * TILE, p.y * TILE);
        }
      }
    }
  }

  /** Trade moments: a burst and a floating figure at the desk that filled. */
  drawEffects(ctx) {
    if (!this.effects || !this.effects.length) return;
    const now = Date.now();
    for (const e of this.effects) {
      const age = (now - e.born) / e.life;
      if (age >= 1) continue;
      const x = e.x * TILE + 8, y = e.y * TILE + 8 - age * 26;
      ctx.globalAlpha = 1 - age;
      // ring
      ctx.strokeStyle = e.colour;
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.arc(e.x * TILE + 8, e.y * TILE + 10, 6 + age * 22, 0, Math.PI * 2); ctx.stroke();
      // figure
      ctx.font = '700 11px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.lineWidth = 3;
      ctx.strokeStyle = 'rgba(10,8,6,.85)';
      ctx.strokeText(e.text, x, y);
      ctx.fillStyle = e.colour;
      ctx.fillText(e.text, x, y);
      ctx.textAlign = 'left';
      ctx.globalAlpha = 1;
    }
    this.effects = this.effects.filter(e => now - e.born < e.life);
  }

  /** Real-calendar weather (falling leaves in autumn, snow in winter --
   *  see season.js). Lazily created once the real season is known, same
   *  pattern as NightFX below. No effect at all in spring/summer -- not
   *  every season needs one, and inventing rain/pollen would be decoration
   *  for its own sake rather than something real driving it. */
  drawSeason(ctx) {
    if (this.season === undefined) {
      const sea = realSeason();
      this.season = sea ? new SeasonFX(sea) : null;
    }
    if (this.season) this.season.draw(ctx);
  }

  /**
   * Live data painted onto the wall screens. These are real numbers from
   * /api/status, redrawn each frame -- the screens are instruments, not
   * decoration. `this.state` is set by main.js on every poll.
   */
  drawScreens(ctx) {
    const s = this.state;
    if (!s) return;
    const scan = s.scan || {};
    const money = v => (v < 0 ? '-' : '+') + '$' + Math.abs(v).toFixed(2);
    const pnl = (s.todays_trades || []).reduce((t, x) => t + (parseFloat(x['P&L']) || 0), 0);

    for (const sc of SCREENS) {
      const x = sc.x * TILE + 3, y = sc.y * TILE + 3;
      const w = sc.w * TILE - 6, h = sc.h * TILE - 6;

      ctx.fillStyle = s.bot_alive ? '#0d1a14' : '#1a1414';   // dark when offline
      ctx.fillRect(x, y, w, h);

      let text = '—', tint = '#7ee0a0';
      if (!s.bot_alive) { text = 'OFFLINE'; tint = '#c56d63'; }
      else if (sc.screen === 'pnl')     { text = money(pnl); tint = pnl < 0 ? '#e0705f' : '#7ee0a0'; }
      else if (sc.screen === 'breadth' && scan.breadth != null)
        { text = `SPY ${scan.breadth > 0 ? '+' : ''}${scan.breadth}%`; tint = scan.breadth < 0 ? '#e0a05f' : '#7ee0a0'; }
      else if (sc.screen === 'scan')    { text = `SCAN ${scan.scan_num ?? '—'}`; }
      else if (sc.screen === 'risk') {
        const n = (s.earnings_blackout || []).length;
        text = n ? `${n} BLACKOUT` : 'CLEAR'; tint = n ? '#e0a05f' : '#7ee0a0';
      }
      else if (sc.screen === 'zones') {
        const inZone = (scan.symbols || []).filter(z => z.zone === 'BUY' && !z.narrow).length;
        text = `${inZone} IN ZONE`; tint = inZone ? '#7ee0a0' : '#8fa596';
      }
      else if (sc.screen === 'equity') {
        this.drawSparkline(ctx, s.equity_curve || [], x, y, w, h);
        continue;
      }

      ctx.fillStyle = tint;
      ctx.font = '700 7px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText(text, x + w / 2, y + h / 2 + 2.5);
      ctx.textAlign = 'left';
    }
  }

  /** Cumulative P&L, drawn straight onto the Records Room wall screen. */
  drawSparkline(ctx, curve, x, y, w, h) {
    if (curve.length < 2) {
      ctx.fillStyle = '#6f8a7c';
      ctx.font = '700 6px ui-monospace, monospace';
      ctx.textAlign = 'center';
      ctx.fillText('NO DATA', x + w / 2, y + h / 2 + 2);
      ctx.textAlign = 'left';
      return;
    }
    const vals = curve.map(p => p.cumulative);
    const lo = Math.min(...vals, 0), hi = Math.max(...vals, 0);
    const span = (hi - lo) || 1;
    const px = i => x + 2 + (i / (vals.length - 1)) * (w - 4);
    const py = v => y + h - 2 - ((v - lo) / span) * (h - 4);

    ctx.strokeStyle = 'rgba(140,170,155,.35)';               // zero line
    ctx.lineWidth = 0.5;
    ctx.beginPath(); ctx.moveTo(x + 2, py(0)); ctx.lineTo(x + w - 2, py(0)); ctx.stroke();

    ctx.strokeStyle = vals[vals.length - 1] >= 0 ? '#7ee0a0' : '#e0705f';
    ctx.lineWidth = 1;
    ctx.beginPath();
    vals.forEach((v, i) => i ? ctx.lineTo(px(i), py(v)) : ctx.moveTo(px(i), py(v)));
    ctx.stroke();
  }

  /**
   * Dynamic layer. Sorted by Y so a character lower on the screen draws in
   * front of one above it -- the usual top-down depth trick.
   */
  /** The fictional cast plus Sage and her dogs, when she's out and about. */
  allAgents() {
    const extra = [];
    if (this.player) extra.push(this.player);
    if (this.dogs) extra.push(...this.dogs);
    return extra.length ? [...this.agents, ...extra] : this.agents;
  }

  drawAgents(ctx) {
    const all = this.allAgents();
    if (!all.length) return;
    const ordered = all.filter(a => !a._riding && !a._commuting).sort((a, b) => a.y - b.y);
    for (const a of ordered) {
      const p = a.screenPos();
      // soft contact shadow so characters sit on the floor
      ctx.fillStyle = 'rgba(0,0,0,.22)';
      ctx.beginPath();
      ctx.ellipse(p.px + 8, p.py + 23, 5, 2.2, 0, 0, Math.PI * 2);
      ctx.fill();
      a.draw(ctx);
    }
  }

  /**
   * Name tag + status bubble + alert light, in screen space so text stays
   * crisp at any zoom. All content comes from real bot state.
   */
  drawAgentTags() {
    const all = this.allAgents();
    if (!all.length) return;
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    const vw = this.canvas.width / dpr, vh = this.canvas.height / dpr;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textAlign = 'center';

    // Bubbles are laid out in screen space at a FIXED readable size, and are
    // pushed upward when they would collide with one already placed. Without
    // this, a group standing together in the cafe produced an unreadable pile.
    const NAME_F = '700 11px ui-monospace, "SF Mono", Menlo, monospace';
    // Name tags get busy when zoomed out, but speech is the whole point --
    // chat bubbles render at EVERY zoom, including the 0.5x 'Fit' view.
    const showNames = this.cam.scale >= 1;
    const placed = [];
    const overlaps = (r) => placed.some(q =>
      r.x < q.x + q.w + 3 && r.x + r.w + 3 > q.x &&
      r.y < q.y + q.h + 3 && r.y + r.h + 3 > q.y);

    // nearest the camera first, so front-most characters keep their spot
    const ordered = [...all].sort((a, b) => b.y - a.y);

    for (const a of ordered) {
      const p = a.screenPos();
      const s = this.cam.worldToScreen(p.px + 8, p.py);
      if (s.x < -160 || s.y < -80 || s.x > vw + 160 || s.y > vh + 80) continue;

      const isPlayer = a === this.player || (this.dogs && this.dogs.includes(a));
      // Used below both for the status dot and the chat-bubble status chip,
      // so it stays in this outer scope even though the dot itself is
      // skipped for Sage/the dogs (not a bot subsystem, no fake "state").
      const colour = LEVEL_COLOR[a.level] || LEVEL_COLOR.idle;

      if (!isPlayer) {
        const lit = a.level === 'alert' || a.level === 'warn';
        const pulse = lit ? 0.55 + 0.45 * Math.sin(a.animT * 5) : 1;
        ctx.globalAlpha = pulse;
        ctx.fillStyle = colour;
        ctx.beginPath();
        ctx.arc(s.x, s.y - 4, a.level === 'alert' ? 5 : 4, 0, Math.PI * 2);
        ctx.fill();
        ctx.globalAlpha = 1;
        ctx.strokeStyle = 'rgba(12,10,8,.9)';
        ctx.lineWidth = 1.5;
        ctx.stroke();
      }

      if (!showNames && !a.chat) continue;   // zoomed out: speech only

      const chatting = !!a.chat;
      const text = a.chat || a.bubble;
      const CHAT_F = `${chatting ? '500 italic' : '700'} 12px ui-monospace, "SF Mono", Menlo, monospace`;

      // measure both rows, then find a vertical slot that is free
      ctx.font = NAME_F;
      const nameW = Math.ceil(ctx.measureText(a.label).width) + 12;
      ctx.font = CHAT_F;
      const chatW = text ? Math.ceil(ctx.measureText(text).width) + 18 : 0;

      const blockW = Math.max(nameW, chatW);
      const nameH = showNames ? 16 : 0, chatH = text ? 20 : 0;
      const gap = (showNames && text) ? 3 : 0;
      const blockH = nameH + chatH + gap;

      let top = s.y - 12 - blockH;
      for (let tries = 0; tries < 14; tries++) {
        const r = { x: s.x - blockW / 2, y: top, w: blockW, h: blockH };
        if (!overlaps(r)) break;
        top -= blockH + 4;                    // stack upward
      }
      placed.push({ x: s.x - blockW / 2, y: top, w: blockW, h: blockH });
      a._bubbleAt = { x: s.x, y: top + nameH + gap + 10 };

      // leader line back down to the character when pushed far up
      const bottom = top + blockH;
      if (s.y - 12 - bottom > 6) {
        ctx.strokeStyle = 'rgba(240,236,226,.35)';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(s.x, bottom); ctx.lineTo(s.x, s.y - 10); ctx.stroke();
      }

      // ---- name tag (hidden when zoomed right out)
      if (showNames) {
        ctx.font = NAME_F;
        ctx.fillStyle = 'rgba(16,13,10,.92)';
        ctx.beginPath(); ctx.roundRect(s.x - nameW / 2, top, nameW, nameH, 4); ctx.fill();
        ctx.strokeStyle = 'rgba(0,0,0,.55)'; ctx.lineWidth = 1; ctx.stroke();
        ctx.fillStyle = '#f6f1e6';
        ctx.fillText(a.label, s.x, top + 12);
      }

      // ---- speech bubble: banter is blue-grey italic, real status is cream
      if (!text) continue;
      const by = top + nameH + gap;
      ctx.font = CHAT_F;
      ctx.fillStyle = chatting ? '#eef2f9' : '#fffaf0';
      ctx.strokeStyle = chatting ? '#3d465e' : '#12100d';
      ctx.lineWidth = 2;
      ctx.beginPath(); ctx.roundRect(s.x - chatW / 2, by, chatW, chatH, 6); ctx.fill(); ctx.stroke();
      ctx.beginPath();                                   // tail
      ctx.moveTo(s.x - 5, by + chatH - 1);
      ctx.lineTo(s.x, by + chatH + 6);
      ctx.lineTo(s.x + 5, by + chatH - 1);
      ctx.closePath();
      ctx.fillStyle = chatting ? '#eef2f9' : '#fffaf0'; ctx.fill(); ctx.stroke();
      if (!chatting) {                                   // status chip: real data only
        ctx.fillStyle = colour;
        ctx.beginPath(); ctx.roundRect(s.x - chatW / 2 + 4, by + 4, 3.5, chatH - 8, 2); ctx.fill();
      }
      ctx.fillStyle = chatting ? '#2b3346' : '#12100d';
      ctx.fillText(text, s.x + (chatting ? 0 : 3), by + 14);
    }

    // Link the two halves of a conversation so it reads as people talking to
    // each other rather than two unrelated bubbles that happen to be near by.
    ctx.setLineDash([3, 3]);
    ctx.strokeStyle = 'rgba(150,175,220,.55)';
    ctx.lineWidth = 1.5;
    for (const a of this.agents) {
      const o = a.chatWith;
      if (!a.chat || !o || !o.chat || !a._bubbleAt || !o._bubbleAt) continue;
      if (a.id > o.id) continue;                     // draw each pair once
      ctx.beginPath();
      ctx.moveTo(a._bubbleAt.x, a._bubbleAt.y);
      ctx.lineTo(o._bubbleAt.x, o._bubbleAt.y);
      ctx.stroke();
    }
    ctx.setLineDash([]);
  }

  /** Labels are drawn in screen space so they stay legible at any zoom. */
  drawLabels() {
    const ctx = this.ctx;
    const dpr = window.devicePixelRatio || 1;
    ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
    ctx.textAlign = 'center';

    // Labels are wayfinding for the overview. Once you zoom in to inspect a
    // room they'd sit on top of its centrepiece furniture, so they fade out
    // and the hover readout in the footer takes over.
    const fade = this.cam.scale >= 3 ? 0.28 : 1;
    ctx.globalAlpha = fade;

    for (const r of ROOMS) {
      const cx = (r.rect.x + r.rect.w / 2) * TILE;
      const cy = (r.rect.y + r.rect.h / 2) * TILE;
      const p = this.cam.worldToScreen(cx, cy);
      if (p.x < -160 || p.y < -60 ||
          p.x > this.canvas.width / dpr + 160 || p.y > this.canvas.height / dpr + 60) continue;

      const big = r.primary ? 14 : 12;
      ctx.font = `700 ${big}px ui-monospace, "SF Mono", Menlo, monospace`;
      const label = r.name.toUpperCase();
      const wpx = ctx.measureText(label).width;

      ctx.fillStyle = 'rgba(20,16,12,.72)';
      ctx.fillRect(p.x - wpx / 2 - 9, p.y - big, wpx + 18, big + 8);
      ctx.fillStyle = r.accent;
      ctx.fillRect(p.x - wpx / 2 - 9, p.y - big, 3, big + 8);

      ctx.fillStyle = '#fdfaf3';
      ctx.fillText(label, p.x, p.y - 1);

      if (this.cam.scale === 2) {
        ctx.font = '500 10px ui-monospace, "SF Mono", Menlo, monospace';
        ctx.fillStyle = 'rgba(255,255,255,.62)';
        ctx.fillText(r.blurb, p.x, p.y + 15);
      }
    }

    // The standalone buildings were the only unlabelled things in the city --
    // you had to already know which block was which. Their signs hang over
    // the doorway rather than the centre, so they don't cover the interior.
    const SIGNS = [
      { name: STUDIO.name,   accent: STUDIO.accent,   rect: STUDIO.rect },
      { name: CAFE.name,     accent: CAFE.accent,     rect: CAFE.rect },
      { name: HOSPITAL.name, accent: HOSPITAL.accent, rect: HOSPITAL.rect },
      { name: CONDO.name,    accent: CONDO.accent,    rect: CONDO.rect },
      { name: SAGE_HOME.name, accent: SAGE_HOME.accent, rect: SAGE_HOME.rect },
      { name: ATM_CO.name, accent: ATM_CO.accent, rect: ATM_CO.rect },
      { name: SUBURB.name, accent: SUBURB.accent, rect: SUBURB.rect },
      { name: STORE.name, accent: STORE.accent, rect: STORE.rect },
      { name: NEWS_STUDIO.name, accent: NEWS_STUDIO.accent, rect: NEWS_STUDIO.rect },
      { name: FIELD_OFFICE.name, accent: FIELD_OFFICE.accent, rect: FIELD_OFFICE.rect },
      { name: BANK.name, accent: BANK.accent, rect: BANK.rect },
      { name: TAX_OFFICE.name, accent: TAX_OFFICE.accent, rect: TAX_OFFICE.rect },
      { name: PREDICT_DESK.name, accent: PREDICT_DESK.accent, rect: PREDICT_DESK.rect },
      ...SHOPS.map(shop => ({ name: shop.name, accent: shop.accent, rect: shop.rect })),
      { name: TERMINAL.name, accent: TERMINAL.accent, rect: TERMINAL.rect }
    ];
    for (const s of SIGNS) {
      const cx = (s.rect.x + s.rect.w / 2) * TILE;
      const cy = (s.rect.y - 0.4) * TILE;                  // just above the roof
      const p = this.cam.worldToScreen(cx, cy);
      if (p.x < -180 || p.y < -60 ||
          p.x > this.canvas.width / dpr + 180 || p.y > this.canvas.height / dpr + 60) continue;

      ctx.font = '700 11px ui-monospace, "SF Mono", Menlo, monospace';
      const label = s.name.toUpperCase();
      const wpx = ctx.measureText(label).width;
      ctx.fillStyle = 'rgba(20,16,12,.78)';
      ctx.fillRect(p.x - wpx / 2 - 8, p.y - 12, wpx + 16, 17);
      ctx.fillStyle = s.accent;
      ctx.fillRect(p.x - wpx / 2 - 8, p.y - 12, 3, 17);
      ctx.fillStyle = '#fdfaf3';
      ctx.fillText(label, p.x, p.y);
    }
    ctx.globalAlpha = 1;
  }
}
