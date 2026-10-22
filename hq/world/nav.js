/**
 * Navigation grid + pathfinding.
 *
 * The HQ is only 66x48 tiles, so a plain BFS over walkable tiles is instant
 * and always finds the shortest route. No need for A* heuristics here.
 */

import { WORLD, ROOMS, CORRIDOR, DOORS, isOutdoors, outdoorBlocked,
         HOMES, homeSpot, cafeSpot } from './hq-map.js';
import { isBlocked } from './furniture.js';

function inRect(tx, ty, r) {
  return tx >= r.x && tx < r.x + r.w && ty >= r.y && ty < r.y + r.h;
}

let GRID = null;

/** true where a character may stand. Built once, cached. */
export function grid() {
  if (GRID) return GRID;
  GRID = [];
  for (let y = 0; y < WORLD.h; y++) {
    const row = [];
    for (let x = 0; x < WORLD.w; x++) {
      // Only the real indoor rooms (the main HQ building) route through
      // furniture.js's isBlocked() below. STUDIO_ROOM / ATM_ROOM are
      // standalone outdoor buildings with their own wall geometry in
      // outdoorBlocked() -- roomAt() also matches them (for click/panel
      // purposes), but routing them through the indoor path here made their
      // wall-collision code dead: isBlocked() knows nothing about a
      // building it was never told about, so every wall tile silently read
      // as walkable. Real bug, found while placing Wes's home next door.
      const inside = ROOMS.some(r => inRect(x, y, r.rect)) ||
                     inRect(x, y, CORRIDOR) || DOORS.some(d => inRect(x, y, d));
      if (inside) {
        row.push(!isBlocked(x, y));
      } else {
        // Outdoors: streets, pavements, grass and the park are all walkable;
        // buildings, trees, benches and the pond are not.
        row.push(isOutdoors(x, y) && !outdoorBlocked(x, y));
      }
    }
    GRID.push(row);
  }
  return GRID;
}

export function walkable(tx, ty) {
  const g = grid();
  return ty >= 0 && ty < g.length && tx >= 0 && tx < g[0].length && g[ty][tx];
}

/**
 * Shortest walkable path from a to b, inclusive of b.
 * Returns [] if unreachable. If b itself is blocked (e.g. a desk chair that
 * furniture sits on), the nearest walkable neighbour of b is used instead.
 *
 * `avoid` (optional): a Set of "x,y" strings -- tiles other characters
 * currently occupy, so nobody paths straight through somebody else. This is
 * solid-body collision between characters, not a physics simulation: no
 * velocity or momentum, just "that tile is taken, route around it." The
 * goal tile itself is never treated as occupied even if it's in the set, so
 * arriving next to a contested spot still works instead of failing outright
 * -- same spirit as the existing blocked-goal fallback above.
 */
export function findPath(from, to, avoid = null) {
  const g = grid();
  const H = g.length, W = g[0].length;

  let goal = to;
  if (!walkable(to.x, to.y)) {
    const alt = [[0, 1], [0, -1], [1, 0], [-1, 0]]
      .map(([dx, dy]) => ({ x: to.x + dx, y: to.y + dy }))
      .find(p => walkable(p.x, p.y));
    if (!alt) return [];
    goal = alt;
  }
  if (from.x === goal.x && from.y === goal.y) return [];

  const key = (x, y) => y * W + x;
  const occupied = (x, y) => avoid && (x !== goal.x || y !== goal.y) && avoid.has(`${x},${y}`);
  const prev = new Map();
  const seen = new Uint8Array(W * H);
  const q = [{ x: from.x, y: from.y }];
  seen[key(from.x, from.y)] = 1;

  while (q.length) {
    const cur = q.shift();
    if (cur.x === goal.x && cur.y === goal.y) {
      const path = [];
      let k = key(cur.x, cur.y);
      let node = cur;
      while (node) {
        path.push(node);
        node = prev.get(k);
        if (node) k = key(node.x, node.y);
      }
      path.reverse();
      path.shift();                       // drop the starting tile
      return path;
    }
    for (const [dx, dy] of [[0, 1], [0, -1], [1, 0], [-1, 0]]) {
      const nx = cur.x + dx, ny = cur.y + dy;
      if (nx < 0 || ny < 0 || nx >= W || ny >= H) continue;
      const nk = key(nx, ny);
      if (seen[nk] || !g[ny][nx] || occupied(nx, ny)) continue;
      seen[nk] = 1;
      prev.set(nk, cur);
      q.push({ x: nx, y: ny });
    }
  }
  return [];
}

/** A spot INSIDE the home belonging to a watchlist slot. */
export function homeDoor(slot, spotIdx = 0) {
  const s = homeSpot(slot, spotIdx);
  if (s && walkable(s.x, s.y)) return { x: s.x, y: s.y, what: s.what };
  const h = HOMES.find(x => x.slot === slot);
  return h ? { x: h.approach.x, y: h.approach.y } : null;
}

/** A spot inside the coffee shop. */
export function cafeTarget(idx = 0) {
  const s = cafeSpot(idx);
  return (s && walkable(s.x, s.y)) ? s : null;
}

/** A sensible standing tile inside a room (used for "go to the break room"). */
export function roomAnchor(roomId) {
  const r = ROOMS.find(x => x.id === roomId);
  if (!r) return null;
  const cx = Math.floor(r.rect.x + r.rect.w / 2);
  for (let dy = 0; dy < r.rect.h; dy++) {
    for (const cand of [{ x: cx, y: r.rect.y + r.rect.h - 2 - dy },
                        { x: cx + 1, y: r.rect.y + r.rect.h - 2 - dy },
                        { x: cx - 1, y: r.rect.y + r.rect.h - 2 - dy }]) {
      if (walkable(cand.x, cand.y)) return cand;
    }
  }
  return null;
}
