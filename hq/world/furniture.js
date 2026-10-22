/**
 * Furniture placement, in tile coordinates.
 *
 * Items are listed per room in DRAW ORDER (rugs first, then objects on top).
 * FOOTPRINTS gives each sprite's tile size -- Phase 5 pathing will use it to
 * keep walking agents from strolling through desks, and Phase 7 hit-testing
 * will use it to make individual computers clickable.
 */

import { STUDIO, BILLBOARD } from './hq-map.js';

export const FOOTPRINTS = {
  desk:            { w: 3, h: 2 },
  desk_small:      { w: 2, h: 2 },
  chair:           { w: 1, h: 1 },
  filing_cabinet:  { w: 1, h: 2 },
  bookshelf:       { w: 2, h: 1 },
  rack:            { w: 3, h: 1 },
  table_big:       { w: 6, h: 4 },
  couch:           { w: 4, h: 2 },
  fridge:          { w: 2, h: 2 },
  coffee:          { w: 1, h: 1 },
  counter:         { w: 4, h: 1 },
  plant:           { w: 1, h: 1 },
  crate:           { w: 1, h: 1 },
  wallscreen:      { w: 3, h: 1 },
  whiteboard:      { w: 3, h: 1 },
  server_rack:     { w: 2, h: 2 },
  workbench:       { w: 4, h: 2 },
  rug:             { w: 4, h: 3 }
};

/** Sprites that agents can sit at / interact with, flagged for later phases. */
export const WORKSTATIONS = new Set(['desk', 'desk_small', 'server_rack', 'workbench']);

const F = (sprite, x, y, extra = {}) => ({ sprite, x, y, ...extra });

export const FURNITURE = [
  /* ---- Risk Office -- win-rate breaker & earnings blackout ------------ */
  F('rug', 6, 8, { room: 'risk' }),
  F('filing_cabinet', 4, 4, { room: 'risk' }),
  F('filing_cabinet', 4, 7, { room: 'risk' }),
  F('bookshelf', 6, 4, { room: 'risk' }),
  F('bookshelf', 9, 4, { room: 'risk' }),
  F('whiteboard', 12, 4, { room: 'risk' }),
  F('wallscreen', 16, 4, { room: 'risk', screen: 'risk' }),
  F('desk', 6, 6, { room: 'risk', station: 'risk-desk' }),
  F('chair', 7, 9, { room: 'risk' }),
  F('desk_small', 16, 7, { room: 'risk', station: 'risk-aux' }),
  F('chair', 16, 9, { room: 'risk' }),
  F('plant', 19, 4, { room: 'risk' }),
  F('plant', 4, 18, { room: 'risk' }),
  F('plant', 19, 18, { room: 'risk' }),

  /* ---- Trading Floor -- Eva, live scan loop, war-room table ----------- */
  F('whiteboard', 22, 4, { room: 'trading' }),
  F('wallscreen', 27, 4, { room: 'trading', screen: 'scan' }),
  F('wallscreen', 31, 4, { room: 'trading', screen: 'breadth' }),
  F('wallscreen', 35, 4, { room: 'trading', screen: 'pnl' }),
  F('plant', 39, 4, { room: 'trading' }),
  F('desk', 23, 7, { room: 'trading', station: 'eva-desk' }),
  F('chair', 24, 9, { room: 'trading' }),
  F('desk', 37, 7, { room: 'trading', station: 'trading-aux' }),
  F('chair', 38, 9, { room: 'trading' }),
  F('table_big', 28, 11, { room: 'trading', station: 'war-table' }),
  F('chair', 27, 12, { room: 'trading' }),
  F('chair', 27, 13, { room: 'trading' }),
  F('chair', 34, 12, { room: 'trading' }),
  F('chair', 34, 13, { room: 'trading' }),
  F('chair', 29, 10, { room: 'trading' }),
  F('chair', 31, 10, { room: 'trading' }),
  F('chair', 29, 15, { room: 'trading' }),
  F('chair', 31, 15, { room: 'trading' }),
  F('plant', 22, 18, { room: 'trading' }),
  F('plant', 40, 18, { room: 'trading' }),

  /* ---- Records Room -- trade log, equity curve, reviews --------------- */
  F('filing_cabinet', 44, 4, { room: 'records' }),
  F('filing_cabinet', 46, 4, { room: 'records' }),
  F('filing_cabinet', 48, 4, { room: 'records' }),
  F('filing_cabinet', 50, 4, { room: 'records' }),
  F('filing_cabinet', 52, 4, { room: 'records' }),
  F('filing_cabinet', 44, 7, { room: 'records' }),
  F('filing_cabinet', 46, 7, { room: 'records' }),
  F('filing_cabinet', 48, 7, { room: 'records' }),
  F('filing_cabinet', 50, 7, { room: 'records' }),
  F('filing_cabinet', 52, 7, { room: 'records' }),
  F('rack', 55, 4, { room: 'records' }),
  F('rack', 55, 6, { room: 'records' }),
  F('rack', 55, 8, { room: 'records' }),
  F('desk_small', 45, 11, { room: 'records', station: 'records-desk' }),
  F('chair', 45, 13, { room: 'records' }),
  F('bookshelf', 49, 11, { room: 'records' }),
  F('bookshelf', 52, 11, { room: 'records' }),
  F('wallscreen', 49, 14, { room: 'records', screen: 'equity' }),
  F('crate', 56, 12, { room: 'records' }),
  F('crate', 57, 12, { room: 'records' }),
  F('plant', 43, 18, { room: 'records' }),
  F('plant', 58, 18, { room: 'records' }),

  /* ---- Watchlist Wing -- 7 desks, each covering up to SYMBOLS_PER_DESK
     (3) real symbols via activity.js's deskSymbols()/mostActionable(), so
     the room already has headroom for a watchlist wider than 7 without
     adding desks. See SYMBOLS_PER_DESK in activity.js. ------------------ */
  F('desk', 5, 27,  { room: 'watchlist', station: 'sym-0' }),
  F('chair', 6, 29, { room: 'watchlist' }),
  F('desk', 10, 27, { room: 'watchlist', station: 'sym-1' }),
  F('chair', 11, 29, { room: 'watchlist' }),
  F('desk', 15, 27, { room: 'watchlist', station: 'sym-2' }),
  F('chair', 16, 29, { room: 'watchlist' }),
  F('desk', 20, 27, { room: 'watchlist', station: 'sym-3' }),
  F('chair', 21, 29, { room: 'watchlist' }),
  F('desk', 5, 33,  { room: 'watchlist', station: 'sym-4' }),
  F('chair', 6, 35, { room: 'watchlist' }),
  F('desk', 10, 33, { room: 'watchlist', station: 'sym-5' }),
  F('chair', 11, 35, { room: 'watchlist' }),
  F('desk', 15, 33, { room: 'watchlist', station: 'sym-6' }),
  F('chair', 16, 35, { room: 'watchlist' }),
  F('wallscreen', 20, 25, { room: 'watchlist', screen: 'zones' }),
  F('rack', 23, 33, { room: 'watchlist' }),
  F('plant', 25, 26, { room: 'watchlist' }),
  F('plant', 4, 40,  { room: 'watchlist' }),
  F('plant', 25, 40, { room: 'watchlist' }),

  /* ---- Mechanic Bay -- morning + hourly health checks ----------------- */
  F('workbench', 30, 27, { room: 'mechanic', station: 'bench' }),
  F('server_rack', 30, 31, { room: 'mechanic', station: 'rack-a' }),
  F('server_rack', 33, 31, { room: 'mechanic', station: 'rack-b' }),
  F('rack', 36, 25, { room: 'mechanic' }),
  F('rack', 36, 27, { room: 'mechanic' }),
  F('crate', 40, 30, { room: 'mechanic' }),
  F('crate', 41, 30, { room: 'mechanic' }),
  F('crate', 40, 31, { room: 'mechanic' }),
  F('desk_small', 36, 34, { room: 'mechanic', station: 'mechanic-desk' }),
  F('chair', 36, 36, { room: 'mechanic' }),
  F('plant', 42, 40, { room: 'mechanic' }),

  /* ---- Break Room -- off-hours ---------------------------------------- */
  F('counter', 46, 25, { room: 'break' }),
  F('coffee', 50, 25, { room: 'break' }),
  F('fridge', 51, 25, { room: 'break' }),
  F('couch', 46, 29, { room: 'break' }),
  F('rug', 51, 30, { room: 'break' }),
  F('table_big', 48, 34, { room: 'break', station: 'break-table' }),
  F('chair', 47, 35, { room: 'break' }),
  F('chair', 47, 36, { room: 'break' }),
  F('chair', 54, 35, { room: 'break' }),
  F('chair', 54, 36, { room: 'break' }),
  F('chair', 49, 33, { room: 'break' }),
  F('chair', 51, 33, { room: 'break' }),
  F('plant', 57, 26, { room: 'break' }),
  F('plant', 45, 40, { room: 'break' }),
  F('plant', 57, 40, { room: 'break' })
];

/** Distinct sprite files the furniture layer needs loaded. */
export const FURNITURE_SPRITES = [...new Set(FURNITURE.map(f => f.sprite))];

/**
 * The interactive object at a tile, or null. Only objects carrying a
 * `station` or `screen` tag are clickable -- a plant is scenery, a terminal
 * is a thing you can open.
 */
export function objectAt(tx, ty) {
  for (const f of FURNITURE) {
    if (!f.station && !f.screen) continue;
    const fp = FOOTPRINTS[f.sprite];
    if (tx >= f.x && tx < f.x + fp.w && ty >= f.y && ty < f.y + fp.h) return f;
  }
  // The Archive Studio's five stations are declared in hq-map.js rather than
  // in FURNITURE, so they were never clickable. Each one maps to a real
  // pipeline stage in studio.py, so clicking it should open that stage.
  for (const st of STUDIO.stations) {
    if (tx >= st.at.x - 1 && tx <= st.at.x + 2 && ty >= st.at.y - 1 && ty <= st.at.y + 2) {
      return { station: st.id, studioStation: st };
    }
  }
  if (tx >= BILLBOARD.x && tx < BILLBOARD.x + BILLBOARD.w &&
      ty >= BILLBOARD.y && ty < BILLBOARD.y + BILLBOARD.h) {
    return { station: BILLBOARD.station };
  }
  return null;
}

/** Every screen surface, for the live-data overlay the renderer draws. */
export const SCREENS = FURNITURE
  .filter(f => f.screen)
  .map(f => ({ ...f, ...FOOTPRINTS[f.sprite] }));

/** True if a tile is occupied by furniture -- used by Phase 5 pathing. */
export function isBlocked(tx, ty) {
  for (const f of FURNITURE) {
    if (f.sprite === 'rug') continue;            // you can walk on a rug
    const fp = FOOTPRINTS[f.sprite];
    if (tx >= f.x && tx < f.x + fp.w && ty >= f.y && ty < f.y + fp.h) return true;
  }
  return false;
}
