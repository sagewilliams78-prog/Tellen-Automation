/**
 * Ambient wandering for the city's purely-decorative cast (Milo, Nadia,
 * Reed, Theo, Greta, and the 40 Eastside residents -- every roster entry
 * with `ambient: true`). Pure flavour: the point is a city and an airport
 * that look lived in, not a real simulation of anybody's schedule.
 *
 * During open hours (agents/activity.js's ambientState returns no `goto`
 * then), an idle one occasionally walks to a real waypoint -- a shop, the
 * airport terminal, a neighbour's own doorstep -- and stays a while before
 * picking the next one. Off hours, ambientState already sends them home
 * via the normal goto.home path in main.js, so this never fights that: it
 * only ever acts on an agent that currently has no destination of its own.
 */
import { findPath } from './nav.js';
import { HOMES, SHOPS, TERMINAL, PARK } from './hq-map.js';

const MIN_WAIT_MS = 15000;
const MAX_WAIT_MS = 45000;
const ARRIVE_MIN_MS = 10000;   // how long they linger once they arrive
const ARRIVE_MAX_MS = 25000;

function buildWaypoints() {
  const points = [];
  // Every Eastside resident's own doorstep -- so they visit each other.
  for (const h of HOMES) {
    if (h.slot >= 33 && h.slot <= 72 && h.approach) points.push(h.approach);
  }
  // The shopping strip.
  for (const s of SHOPS) points.push(s.approach);
  // The airport terminal.
  points.push(TERMINAL.approach);
  // A couple of park benches, for the ones who start out there already.
  for (const b of PARK.benches) points.push({ x: b.x, y: b.y + 1 });
  return points;
}

let WAYPOINTS = null;

const pick = arr => arr[Math.floor(Math.random() * arr.length)];

export class Wanderer {
  constructor() {
    this.nextAt = new Map();   // agent id -> next time it's allowed to move
  }

  /**
   * `agents` is renderer.agents (live AgentSprite instances); `shiftOpen`
   * gates this off entirely outside open hours (ambientState's goto.home
   * already owns that transition). `occupied` is an optional Set of
   * "x,y" strings -- other agents' current tiles -- same collision-avoid
   * contract as nav.js's findPath.
   */
  update(agents, shiftOpen, occupied) {
    if (!shiftOpen) return;
    if (!WAYPOINTS) WAYPOINTS = buildWaypoints();
    const now = Date.now();

    for (const a of agents) {
      if (!a.def || !a.def.ambient) continue;
      if (a.path && a.path.length) continue;       // already walking somewhere

      let next = this.nextAt.get(a.def.id);
      if (next == null) {
        this.nextAt.set(a.def.id, now + MIN_WAIT_MS + Math.random() * (MAX_WAIT_MS - MIN_WAIT_MS));
        continue;
      }
      if (now < next) continue;

      const from = { x: Math.round(a.x), y: Math.round(a.y) };
      const dest = pick(WAYPOINTS);
      if (from.x !== dest.x || from.y !== dest.y) {
        const path = findPath(from, dest, occupied);
        if (path.length) a.setPath(path);
      }
      this.nextAt.set(a.def.id, now + ARRIVE_MIN_MS + Math.random() * (ARRIVE_MAX_MS - ARRIVE_MIN_MS));
    }
  }
}
