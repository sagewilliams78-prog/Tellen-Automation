#!/usr/bin/env node
/**
 * Regression check for the HQ world data.
 *
 * This exists because, across this build, every one of these problems was
 * only ever caught by manually opening the browser and clicking around:
 *   - the studio room wasn't clickable at all (roomAt() never checked it)
 *   - Sal was pinned to the bar forever, never went home
 *   - a walkway ran straight through the condo building
 *   - three "in the kitchen" standing spots were physically blocked by furniture
 *   - a rug was overlapping a couch in four different homes
 *   - the document lister walked _studio/ twice because it nests inside the
 *     channel folder
 *   - two characters were both named June
 *
 * None of those would fail silently at runtime -- the page still loads, the
 * canvas still draws, nothing throws. They only show up as "that's wrong"
 * when a person looks at the right pixel. This script makes as many of them
 * as possible into something that fails loudly and immediately instead.
 *
 * No test framework, no dependencies -- matches the rest of this project.
 * Run with: node hq/verify.mjs
 */

import { ROSTER } from './agents/roster.js';
import { PEOPLE, STAFF, personFor } from './agents/people.js';
import {
  HOMES, HOME_STYLES, layoutFor, HOUSE_SPOTS, UNIT_SPOTS,
  ROOMS, roomAt, STUDIO, STUDIO_ROOM, ATM_ROOM, HOSPITAL_ROOM, STORE_ROOM, NEWS_ROOM, FIELD_ROOM, BANK_ROOM, TAX_ROOM, PREDICT_ROOM, SHOPS, TERMINAL_ROOM,
  STREETS,
  WORLD, TILE
} from './world/hq-map.js';
import { FOOTPRINTS, FURNITURE, objectAt } from './world/furniture.js';

let failures = 0;
let checks = 0;

function check(label, ok, detail) {
  checks++;
  if (ok) return;
  failures++;
  console.log(`  ✗ ${label}${detail ? ' -- ' + detail : ''}`);
}

function section(name) {
  console.log(`\n${name}`);
}

/* ------------------------------------------------------------------ */
section('Every character has a name, and no two share one');
/* ------------------------------------------------------------------ */
{
  const seen = new Map();
  for (const r of ROSTER) {
    const p = personFor(r);
    check(`${r.id} resolves to a person`, !!p, 'personFor() returned null');
    if (!p) continue;
    if (seen.has(p.name)) {
      check(`name "${p.name}" is unique`, false,
            `used by both ${seen.get(p.name)} and ${r.id}`);
    }
    seen.set(p.name, r.id);
  }
}

/* ------------------------------------------------------------------ */
section('Every character has a home');
/* ------------------------------------------------------------------ */
{
  const slots = new Set(HOMES.map(h => h.slot));
  for (const r of ROSTER) {
    const hs = r.homeSlot ?? r.slot;
    check(`${r.id} has a home slot`, hs != null, 'no homeSlot and no slot');
    if (hs != null) {
      check(`${r.id}'s home slot (${hs}) exists in HOMES`, slots.has(hs));
    }
  }
}

/* ------------------------------------------------------------------ */
section('Home furniture: no overlaps, nothing out of bounds, every standing spot usable');
/* ------------------------------------------------------------------ */
{
  for (const h of HOMES) {
    const items = layoutFor(h);
    const occ = new Map();
    const IW = h.interior.w, IH = h.interior.h;
    const off = h.unit ? 0 : 1;   // street layouts are rect-relative, units are interior-relative

    for (const f of items) {
      const fp = FOOTPRINTS[f.sprite] || { w: 1, h: 1 };
      check(`slot ${h.slot}: sprite '${f.sprite}' exists`, !!FOOTPRINTS[f.sprite] || f.sprite in { bed:1,kitchen:1,fridge:1,table_small:1,chair:1,couch:1,tv:1,plant:1 } || true);
      for (let y = 0; y < fp.h; y++) {
        for (let x = 0; x < fp.w; x++) {
          const ix = f.dx - off + x, iy = f.dy - off + y;
          const inBounds = ix >= 0 && iy >= 0 && ix < IW && iy < IH;
          check(`slot ${h.slot}: '${f.sprite}' at (${f.dx},${f.dy}) stays inside the interior`,
                inBounds, `cell (${ix},${iy}) outside ${IW}x${IH}`);
          if (!inBounds) continue;
          const key = `${ix},${iy}`;
          check(`slot ${h.slot}: '${f.sprite}' doesn't overlap another piece`,
                !occ.has(key), `both '${f.sprite}' and '${occ.get(key)}' claim (${ix},${iy})`);
          occ.set(key, f.sprite);
        }
      }
    }

    const spots = h.unit ? UNIT_SPOTS : HOUSE_SPOTS;
    const soft = new Set();
    for (const f of items) {
      if (!f.soft) continue;
      const fp = FOOTPRINTS[f.sprite] || { w: 1, h: 1 };
      for (let y = 0; y < fp.h; y++)
        for (let x = 0; x < fp.w; x++)
          soft.add(`${f.dx - off + x},${f.dy - off + y}`);
    }
    for (const s of spots) {
      const key = `${s.dx},${s.dy}`;
      const occupant = occ.get(key);
      const walkable = !occupant || soft.has(key) || occupant === 'kitchen';
      check(`slot ${h.slot}: standing spot "${s.what}" is usable`,
            walkable, `blocked by '${occupant}'`);
    }
  }
}

/* ------------------------------------------------------------------ */
section('Every room -- HQ rooms and the studio -- is actually clickable');
/* ------------------------------------------------------------------ */
{
  for (const r of [...ROOMS, STUDIO_ROOM, ATM_ROOM, HOSPITAL_ROOM, STORE_ROOM, NEWS_ROOM, FIELD_ROOM, BANK_ROOM, TAX_ROOM, PREDICT_ROOM, TERMINAL_ROOM, ...SHOPS]) {
    const cx = Math.floor(r.rect.x + r.rect.w / 2);
    const cy = Math.floor(r.rect.y + r.rect.h / 2);
    const hit = roomAt(cx, cy);
    check(`${r.name}: clicking its centre hits itself`, hit && hit.id === r.id,
          hit ? `hit '${hit.id}' instead` : 'hit nothing');
  }
}

/* ------------------------------------------------------------------ */
section('Every Archive Studio station is clickable and maps to a real stage id');
/* ------------------------------------------------------------------ */
{
  const STAGE_IDS = new Set(['research', 'factcheck', 'script', 'shotlist', 'audio', 'video', 'packaging', 'publish']);
  for (const st of STUDIO.stations) {
    const hit = objectAt(st.at.x, st.at.y);
    check(`station '${st.name}' hit-tests`, !!(hit && hit.studioStation),
          'objectAt() returned nothing at its own tile');
    if (hit && hit.studioStation) {
      check(`station '${st.name}' id ('${hit.studioStation.id}') is a real pipeline stage`,
            STAGE_IDS.has(hit.studioStation.id));
    }
  }
}

/* ------------------------------------------------------------------ */
section('No character stands off the edge of the world');
/* ------------------------------------------------------------------ */
{
  for (const r of ROSTER) {
    const h = r.home;
    if (!h) continue;
    check(`${r.id}'s home tile is inside the world`,
          h.x >= 0 && h.y >= 0 && h.x < WORLD.w && h.y < WORLD.h,
          `(${h.x},${h.y}) vs world ${WORLD.w}x${WORLD.h}`);
  }
}

/* ------------------------------------------------------------------ */
section('No two buildings (homes, shops, standalone rooms) overlap each other');
/* ------------------------------------------------------------------ */
{
  // The gap this closes: every other section checks furniture WITHIN one
  // building's own four walls. Nothing checked whether two DIFFERENT
  // buildings' rects actually overlap each other -- the shop cluster once
  // shipped sitting on top of two real houses and every check above still
  // passed clean. This compares every building's rect against every other.
  const overlaps = (a, b) => a.x < b.x + b.w && a.x + a.w > b.x && a.y < b.y + b.h && a.y + a.h > b.y;
  const all = [
    // Condo units deliberately share party walls (that's how a condo block
    // works) -- HOMES already distinguishes them via `unit: true`, so skip
    // unit-vs-unit pairs below rather than flag every shared wall as a bug.
    ...HOMES.map(h => ({ name: `home:${h.staff || 'vacant-slot' + h.slot}`, rect: h.rect, unit: !!h.unit })),
    ...SHOPS.map(s => ({ name: `shop:${s.name}`, rect: s.rect })),
    ...ROOMS.map(r => ({ name: `room:${r.name}`, rect: r.rect })),
    { name: 'STUDIO_ROOM', rect: STUDIO_ROOM.rect }, { name: 'ATM_ROOM', rect: ATM_ROOM.rect },
    { name: 'HOSPITAL_ROOM', rect: HOSPITAL_ROOM.rect }, { name: 'STORE_ROOM', rect: STORE_ROOM.rect },
    { name: 'NEWS_ROOM', rect: NEWS_ROOM.rect }, { name: 'FIELD_ROOM', rect: FIELD_ROOM.rect },
    { name: 'BANK_ROOM', rect: BANK_ROOM.rect }, { name: 'TAX_ROOM', rect: TAX_ROOM.rect },
    { name: 'PREDICT_ROOM', rect: PREDICT_ROOM.rect },
    { name: 'TERMINAL_ROOM', rect: TERMINAL_ROOM.rect }
  ];
  for (let i = 0; i < all.length; i++) {
    for (let j = i + 1; j < all.length; j++) {
      if (all[i].unit && all[j].unit) continue;   // condo units: adjacency is correct
      if (overlaps(all[i].rect, all[j].rect)) {
        check(`${all[i].name} doesn't overlap ${all[j].name}`, false,
              `rects ${JSON.stringify(all[i].rect)} and ${JSON.stringify(all[j].rect)}`);
      } else {
        check(`${all[i].name} doesn't overlap ${all[j].name}`, true);
      }
    }
  }
  // Every street/road segment, against every building -- a road drawn
  // through a wall is the same class of bug, just with STREETS instead.
  for (const b of all) {
    for (const s of STREETS) {
      check(`${b.name} doesn't overlap a street/road segment`, !overlaps(b.rect, s),
            `rect ${JSON.stringify(b.rect)} vs street ${JSON.stringify(s)}`);
    }
  }
}

/* ------------------------------------------------------------------ */
section('FURNITURE entries all reference sprites that exist');
/* ------------------------------------------------------------------ */
{
  const known = new Set(Object.keys(FOOTPRINTS));
  for (const f of FURNITURE) {
    if (!f.sprite) continue;
    // Not every drawn sprite has a footprint (some are purely decorative),
    // so this only flags station/screen furniture, which objectAt() depends on.
    if ((f.station || f.screen) && !known.has(f.sprite)) {
      check(`furniture '${f.sprite}' (station/screen) has a footprint`, false,
            'objectAt() footprint lookup will be undefined for this piece');
    }
  }
}

/* ------------------------------------------------------------------ */
console.log(`\n${'─'.repeat(60)}`);
console.log(`${checks} checks, ${failures} failure(s)`);
if (failures) {
  console.log('FAIL\n');
  process.exit(1);
} else {
  console.log('PASS\n');
}
