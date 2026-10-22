/**
 * Commutes for the staff who live out in Sunrise Meadows.
 *
 * Everyone else off-duty just walks home -- their homes are all a short
 * stroll from work, on purpose. Four people are the exception: the two
 * doctors, plus Otis and Margo once they were pulled out of the condo into
 * real houses of their own, all genuinely far across town (see hq-map.js's
 * SUBURB comment), so they all drive.
 *
 * Unlike the ambulance (EMS) or the ambient Traffic, which only ever move
 * along a single fixed x-axis lane, this drives the real road network: out
 * the driveway, along TOP_ST, down the avenue, along the main road, then
 * into whichever lot is theirs -- the hospital's for the doctors, curbside
 * outside HQ for Otis and Margo -- and parks in their own dedicated spot.
 * The car stays visibly parked there for the whole shift and only leaves
 * again when the shift actually ends.
 *
 * Purely ambient, like the traffic and the EMS system. Triggered only by a
 * real edge in the studio/trading floor's shift clock (everyone here keeps
 * the same hours), never invented.
 */

import { STREETS, TOP_ST, AVENUE, HOMES, HOSPITAL_PARKING, HQ_PARKING, TOWN_PARKING } from './hq-map.js';

const MAIN = STREETS[0];
const LANE = MAIN.y + 3.4;          // its own lane, below the ambulance's and traffic's
const SPEED = 12;                   // tiles/sec -- unhurried, not "speeding" like Traffic
const TOP_ST_LANE = TOP_ST.y + TOP_ST.h / 2;
const AVE_COL = AVENUE.x + AVENUE.w / 2;

const HOSP_LOT = HOSPITAL_PARKING.rect;
const HOSP_LINK_X = HOSP_LOT.x + Math.floor(HOSP_LOT.w / 2) - 1;   // matches renderer.js's connector strip
const HOSP_ENTRY_Y = HOSP_LOT.y + HOSP_LOT.h;                       // where the connector meets the lot

// The corridor between the cafe and the condo block (see hq-map.js's
// TOWN_PARKING) -- where a leisure trip into town actually parks now,
// rather than just vanishing at a curb.
const TOWN_COL = TOWN_PARKING.spots[0].x + TOWN_PARKING.spots[0].w / 2;

function spotCenter(spot) {
  return { x: spot.x + spot.w / 2, y: spot.y + spot.h / 2 };
}

/**
 * This character's home.
 *
 * Named staff carry `homeSlot`; the seven watchlist-desk characters key
 * theirs off `slot` instead (activity.js's symbolState returns
 * `goto: { home: slot }`). Looking at homeSlot alone returned undefined for
 * all seven -- fine while only the four Sunrise Meadows commuters drove,
 * but a crash the moment a desk trader bought a car of their own.
 */
function homeFor(doc) {
  const slot = doc.def.homeSlot ?? doc.def.slot;
  return slot == null ? null : HOMES.find(h => h.slot === slot) || null;
}

/**
 * Which car sprite to draw for this person. The four Sunrise Meadows
 * commuters have one assigned on their roster entry; anyone else is
 * driving something they bought at the General Store, and main.js sets
 * `_carSprite` from what they actually own before starting the trip.
 */
export function carSpriteFor(doc) {
  return doc._carSprite || doc.def.car || 'car_red';
}

function spotFor(doc) {
  const pool = doc.def.commute === 'hospital' ? HOSPITAL_PARKING.spots : HQ_PARKING.spots;
  return pool.find(s => s.staff === doc.def.id);
}

/** The leg from "on the main road" to actually parked -- the only part
 * that differs between the hospital's staff lot and HQ's own curb spots. */
function destSequence(doc) {
  const spot = spotFor(doc);
  const parked = spotCenter(spot);
  if (doc.def.commute === 'hospital') {
    return [
      { x: HOSP_LINK_X, y: LANE },
      { x: HOSP_LINK_X, y: HOSP_ENTRY_Y },
      parked
    ];
  }
  // HQ curbside: each spot sits directly above the road at its own column,
  // clear ground the whole way down -- no shared link needed.
  return [
    { x: parked.x, y: LANE },
    parked
  ];
}

/** The real route from a commuter's own home parking spot to their own
 * work parking spot, home end first. Reversed for the trip home. */
function routeFor(doc) {
  const home = homeFor(doc);
  const parkedHome = spotCenter(home.parkSpot);
  const driveway = { x: home.driveway.x, y: TOP_ST_LANE };
  const onAvenue = { x: AVE_COL, y: TOP_ST_LANE };
  const enterMain = { x: AVE_COL, y: LANE };
  return [parkedHome, driveway, onAvenue, enterMain, ...destSequence(doc)];
}

/** Same first three legs (home -> avenue -> main road), but pulling into a
 * real downtown space instead of their own work spot -- for a leisure trip
 * into town, not the shift commute. `spot` is whichever space was free. */
function townRoute(doc, spot) {
  const home = homeFor(doc);
  const parkedHome = spotCenter(home.parkSpot);
  const driveway = { x: home.driveway.x, y: TOP_ST_LANE };
  const onAvenue = { x: AVE_COL, y: TOP_ST_LANE };
  const enterMain = { x: AVE_COL, y: LANE };
  const turnIn = { x: TOWN_COL, y: LANE };
  return [parkedHome, driveway, onAvenue, enterMain, turnIn, spotCenter(spot)];
}

/**
 * The same trip for someone who BOUGHT a car at the General Store rather
 * than being one of the four Sunrise Meadows commuters.
 *
 * They live downtown already, so there is no avenue leg -- their driveway
 * meets the main road directly. Everything downstream (the drive, the
 * hazard checks, parking, walking off to the cafe) is shared with the
 * commuters, so a bought car behaves exactly like an owned one.
 */
function boughtCarRoute(home, spot) {
  const parkedHome = { x: home.driveway.x, y: home.driveway.y };
  const onRoad = { x: home.driveway.x, y: LANE };
  const turnIn = { x: TOWN_COL, y: LANE };
  return [parkedHome, onRoad, turnIn, spotCenter(spot)];
}

export class Commute {
  constructor() {
    this.wasOpen = null;         // null until the first real shift reading arrives
    this.units = new Map();      // agent id -> {route, i, x, y, orient, dirSign, kind, doctor}
    this.parked = new Map();     // agent id -> the spot they're actually sitting in
    this.townSpots = new Map();  // agent id -> which downtown space they took
  }

  /** A downtown space nobody has claimed. Null when the lot is full. */
  freeTownSpot() {
    const taken = new Set([...this.townSpots.values()]);
    return TOWN_PARKING.spots.find(s => !taken.has(s)) || null;
  }

  /** commuters: the roster's commute-flagged agents. shiftOpen: real, from studioShift(). */
  update(dt, commuters, shiftOpen, now = Date.now()) {
    if (shiftOpen == null) return;
    if (this.wasOpen === null) {
      // No live edge to animate on the very first reading -- but the real
      // shift state already tells us where each car actually is right now
      // (at work if shiftOpen, home otherwise), the same way every other
      // character's position already reflects current state on page load
      // without needing to have been watching the transition happen. Not
      // inventing an event, just not leaving something real invisible
      // until the next 09:00/16:00 ET rolls around.
      this.wasOpen = shiftOpen;
      this.initSteadyState(commuters, shiftOpen);
      return;
    }

    if (shiftOpen && !this.wasOpen) this.startAll(commuters, 'to_work');
    if (!shiftOpen && this.wasOpen) this.startAll(commuters, 'to_home');
    this.wasOpen = shiftOpen;

    for (const u of this.units.values()) this.advance(u, dt);
    for (const [id, u] of this.units) if (u.done) this.units.delete(id);
  }

  /** Places each car directly, no driving animation -- there's no real
   * transition to animate yet, just a real current state to reflect. */
  initSteadyState(commuters, shiftOpen) {
    for (const doc of commuters) {
      if (shiftOpen) {
        this.parked.set(doc.def.id, spotFor(doc));
      } else {
        const home = homeFor(doc);
        if (home) this.parked.set(doc.def.id, { ...home.parkSpot, sprite: doc.def.car });
      }
    }
  }

  startAll(commuters, kind) {
    const toWork = kind === 'to_work';
    for (const doc of commuters) {
      if (this.units.has(doc.def.id)) continue;   // already mid-commute somehow
      const route = routeFor(doc);
      const ordered = toWork ? route : [...route].reverse();

      doc._commuting = true;
      doc.walking = false;
      doc.path = [];
      doc.chat = null;
      doc.chatWith = null;
      doc.bubble = toWork ? '🚗 Driving in' : '🚗 Heading home';
      doc.level = 'idle';
      doc.x = ordered[0].x; doc.y = ordered[0].y;
      this.parked.delete(doc.def.id);              // pulling out, if they were parked

      this.units.set(doc.def.id, {
        route: ordered, i: 1,
        x: ordered[0].x, y: ordered[0].y,
        orient: 'h', dirSign: toWork ? 1 : -1,
        kind, doctor: doc, done: false
      });
    }
  }

  /**
   * A commuter's own choice, not the shift clock -- when their ambient
   * off-duty wander (main.js's applyState()) decides they'd rather be at
   * the cafe or the lake than sit at home, driving that far is faster than
   * walking it, so they drive in, same as they would to save time getting
   * to work. direction: 'to_town' | 'to_home' (from town, not from work).
   */
  startTownTrip(doc, direction) {
    if (this.units.has(doc.def.id)) return;   // already mid-trip somehow
    const toTown = direction === 'to_town';

    // Whichever space is actually free -- these aren't assigned the way the
    // work spots are. On the way back it's the one they're already in.
    const spot = toTown ? this.freeTownSpot() : this.townSpots.get(doc.def.id);
    if (!spot) return;                        // lot full: they just stay put

    // Sunrise Meadows residents take the long route out through the
    // avenue; anyone who simply BOUGHT a car lives downtown already and
    // pulls straight off their own driveway onto the main road. A home
    // with no driveway at all (the condo units share one entrance) can't
    // be driven from -- those residents just walk, which is fine, since
    // they live a few tiles from the cafe anyway.
    const home = homeFor(doc);
    if (!home || (!home.parkSpot && !home.driveway)) return;

    if (toTown) this.townSpots.set(doc.def.id, spot);
    const route = home.parkSpot
      ? townRoute(doc, spot)
      : boughtCarRoute(home, spot);
    const ordered = toTown ? route : [...route].reverse();

    doc._commuting = true;
    doc.walking = false;
    doc.path = [];
    doc.chat = null;
    doc.chatWith = null;
    doc.bubble = toTown ? '🚗 Driving into town' : '🚗 Heading home';
    doc.level = 'idle';
    doc.x = ordered[0].x; doc.y = ordered[0].y;
    this.parked.delete(doc.def.id);              // pulling out, if parked at home

    this.units.set(doc.def.id, {
      route: ordered, i: 1,
      x: ordered[0].x, y: ordered[0].y,
      orient: 'h', dirSign: 1,
      kind: toTown ? 'town_arrive' : 'town_home', doctor: doc, done: false
    });
  }

  advance(u, dt) {
    const target = u.route[u.i];
    const dx = target.x - u.x, dy = target.y - u.y;
    const dist = Math.hypot(dx, dy);
    const step = SPEED * dt;

    if (Math.abs(dx) >= Math.abs(dy)) { u.orient = 'h'; u.dirSign = Math.sign(dx) || u.dirSign; }
    else                              { u.orient = 'v'; u.dirSign = Math.sign(dy) || u.dirSign; }

    if (dist <= step) {
      u.x = target.x; u.y = target.y;
      u.i++;
      if (u.i >= u.route.length) { this.arrive(u); return; }
    } else {
      u.x += (dx / dist) * step;
      u.y += (dy / dist) * step;
    }
    u.doctor.x = u.x;
    u.doctor.y = u.y;
  }

  /** Units currently out on the shared main road -- not the avenue or
   * Sunrise Meadows' own street, where nobody walks. main.js feeds these
   * into Traffic.checkHazard() so a commuter's own car follows the exact
   * same near-the-road rules as everyone else's. */
  unitsOnMainRoad() {
    return [...this.units.values()].filter(u => Math.abs(u.y - LANE) < 1 && u.orient === 'h');
  }

  arrive(u) {
    const doc = u.doctor;
    doc._commuting = false;

    if (u.kind === 'to_work') {
      doc.x = doc.def.home.x;
      doc.y = doc.def.home.y;
      doc.facing = doc.def.facing || 'down';
      this.parked.set(doc.def.id, spotFor(doc));    // the car stays visible all shift

    } else if (u.kind === 'to_home') {
      const home = homeFor(doc);
      if (home) {
        doc.x = home.approach.x; doc.y = home.approach.y;
        // Parked on the side for the night -- same visible-all-shift
        // treatment as the work end, just at their own home spot.
        // Only the four Sunrise Meadows commuters have a dedicated home
        // spot. A resident who simply BOUGHT a car has theirs drawn on
        // their own driveway by ownedPlacements(), so adding a second
        // parked entry here would draw the same car twice.
        if (home.parkSpot) {
          this.parked.set(doc.def.id, { ...home.parkSpot, sprite: carSpriteFor(doc) });
        }
      }
      doc.facing = 'down';

    } else if (u.kind === 'town_arrive') {
      const spot = this.townSpots.get(doc.def.id);
      // Step out into the clear row just past their own space -- the lot's
      // corridor is exactly one car wide, so beside it is the cafe's wall,
      // not pavement. Then they walk the rest the normal way: main.js's own
      // cafe/lake targeting takes over now that they're actually downtown.
      doc.x = spot.x + 1; doc.y = spot.y + spot.h;
      doc.facing = 'down';
      doc._inTown = true;
      this.parked.set(doc.def.id, { ...spot, sprite: carSpriteFor(doc) });
      // Fresh dwell window so they don't immediately re-roll and turn
      // straight back around the moment they arrive.
      doc.nextHomeMove = Date.now() + 18000 + Math.random() * 22000;

    } else if (u.kind === 'town_home') {
      const home = homeFor(doc);
      if (home) {
        doc.x = home.approach.x; doc.y = home.approach.y;
        // Only the four Sunrise Meadows commuters have a dedicated home
        // spot. A resident who simply BOUGHT a car has theirs drawn on
        // their own driveway by ownedPlacements(), so adding a second
        // parked entry here would draw the same car twice.
        if (home.parkSpot) {
          this.parked.set(doc.def.id, { ...home.parkSpot, sprite: carSpriteFor(doc) });
        }
      }
      doc.facing = 'down';
      doc._inTown = false;
      this.townSpots.delete(doc.def.id);       // space is free again
      doc.nextHomeMove = Date.now() + 18000 + Math.random() * 22000;
    }
    u.done = true;
  }
}
