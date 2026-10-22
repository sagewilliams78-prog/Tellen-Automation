/**
 * Traffic.
 *
 * Purely ambient — a car every so often tears down the main street, leans on
 * the horn, and anyone standing too close to the kerb jumps and says
 * something about it. None of this touches bot state; it is the city being a
 * city. Characters only react when they are actually near the road.
 */

import { WORLD, STREETS } from './hq-map.js';

const MAIN = STREETS[0];                 // the long east-west road
const SPRITES = ['car_red', 'car_blue', 'car_yellow'];

const MIN_GAP = 9000;                    // ms between cars
const MAX_GAP = 22000;
const SPEED   = 22;                      // tiles per second — properly speeding
const HONK_MS = 1400;
const SCARE_MS = 3200;
const KERB = 2.2;                        // how close to the road counts as "too close"
const SCARE_X = 7;                       // how far ahead the car startles someone

const SCARED = [
  'Whoa —!', 'HEY!', 'Watch it!', 'Every time!',
  'Maniac!', 'That was close.', 'Slow down!', 'Off the road!'
];

const pick = a => a[Math.floor(Math.random() * a.length)];

export class Traffic {
  /**
   * Configurable so the Eastside Freeway can run its own, denser, faster
   * instance (all 5 car colours, no pedestrian-hazard checks since nobody
   * walks a freeway shoulder) while the main street keeps its original
   * slower, pedestrian-aware behaviour unchanged. Every option defaults to
   * the main street's original values, so `new Traffic()` with no args is
   * exactly the old behaviour.
   */
  constructor(opts = {}) {
    this.road = opts.road || MAIN;
    this.sprites = opts.sprites || SPRITES;
    this.minGap = opts.minGap ?? MIN_GAP;
    this.maxGap = opts.maxGap ?? MAX_GAP;
    this.speed = opts.speed ?? SPEED;
    this.pedestrianHazard = opts.pedestrianHazard ?? true;
    this.lanes = opts.lanes || [this.road.y + 0.35, this.road.y + this.road.h - 1.95];
    this.cars = [];
    this.next = Date.now() + (opts.firstSpawnDelay ?? 4000);
    this.afterHours = false;   // set from the real session each frame
    this.onHit = null;         // callback(agent) -- wired to the ambulance
  }

  spawn(now) {
    const eastbound = Math.random() < 0.5;
    this.cars.push({
      sprite: pick(this.sprites),
      dir: eastbound ? 1 : -1,
      // two lanes: eastbound rides the upper lane, westbound the lower
      y: eastbound ? this.lanes[0] : this.lanes[1],
      x: eastbound ? -5 : WORLD.w + 5,
      honkUntil: 0,
      born: now
    });
    this.next = now + this.minGap + Math.random() * (this.maxGap - this.minGap);
  }

  update(dt, agents, now = Date.now()) {
    if (now >= this.next) this.spawn(now);

    for (const car of this.cars) {
      car.x += car.dir * this.speed * dt;
      if (this.pedestrianHazard) this.checkHazard(car, agents, now);
    }

    this.cars = this.cars.filter(c => c.x > -10 && c.x < WORLD.w + 10);
  }

  /**
   * Same near-the-road hazard check any car on the main street poses to a
   * pedestrian -- scares them if they're close, and after hours can
   * actually connect (dispatching EMS via this.onHit). Factored out so any
   * car object {x, y, dir, honkUntil} can use it, not just Traffic's own
   * spawned ones -- world/commute.js calls this too, for the two doctors
   * and Otis/Margo while their own cars are actually out on the main road
   * (not the avenue or Sunrise Meadows' own street, where nobody walks).
   */
  checkHazard(car, agents, now = Date.now()) {
    const road = this.road;
    for (const a of agents) {
      if (a.injured || a._inCare || a._riding || a._commuting) continue;

      // only people actually near the kerb are in any danger
      const dyToRoad = Math.min(
        Math.abs(a.y - road.y),
        Math.abs(a.y - (road.y + road.h))
      );
      const onRoad = a.y >= road.y - KERB && a.y <= road.y + road.h + KERB;
      if (!onRoad && dyToRoad > KERB) continue;

      // A real hit only happens AFTER HOURS, and only if they are actually
      // standing in the carriageway rather than safely on the kerb.
      const inLane = a.y >= road.y - 0.4 && a.y <= road.y + road.h + 0.4;
      if (this.afterHours && inLane && Math.abs(a.x - car.x - 2) < 1.2 && this.onHit) {
        car.honkUntil = now + HONK_MS;
        this.onHit(a);
        continue;
      }

      const ahead = (a.x - car.x) * car.dir;           // positive = in front
      if (ahead < 0 || ahead > SCARE_X) continue;
      if (a._scaredUntil && now < a._scaredUntil) continue;

      a._scaredUntil = now + SCARE_MS;
      a.chat = pick(SCARED);
      a.chatWith = null;
      a.facing = car.dir > 0 ? 'left' : 'right';       // spin round at it
      car.honkUntil = now + HONK_MS;
      setTimeout(() => { if (a.chat && SCARED.includes(a.chat)) a.chat = null; }, SCARE_MS);
    }
  }
}
