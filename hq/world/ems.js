/**
 * Emergency services.
 *
 * AFTER HOURS ONLY. If the speeding car actually connects with somebody once
 * the market has closed, an ambulance runs out of the hospital, collects
 * them, takes them back for treatment, and then drops them home. During
 * market hours the car still startles people but nobody is ever hit — the
 * desks stay staffed and the real bot state keeps driving everything.
 *
 * This is ambient, like the traffic. It changes nothing about bot data.
 */

import { HOSPITAL, HOMES, STREETS } from './hq-map.js';

const MAIN = STREETS[0];
const LANE = MAIN.y + 1.2;             // ambulances run down the middle
const SPEED = 14;                      // tiles/sec
const LOAD_MS = 2600;                  // scooping the patient up
const TREAT_MS = 9000;                 // time in the ward
const DROP_MS = 2200;                  // helping them to the door

export const INJURY_LINES = [
  'Ow.', 'I am fine. Probably.', "That'll bruise.", 'Told you they speed.'
];

export class EMS {
  constructor() {
    this.units = [];
  }

  get busy() { return this.units.length > 0; }

  /** Send a unit to a casualty. */
  dispatch(patient, now = Date.now()) {
    if (patient._inCare) return;
    patient._inCare = true;
    patient.injured = true;
    patient.path = [];
    patient.walking = false;

    this.units.push({
      x: HOSPITAL.bay.x,
      y: LANE,
      state: 'to_scene',
      patient,
      timer: 0,
      siren: true,
      born: now
    });
  }

  update(dt, now = Date.now()) {
    for (const u of this.units) {
      const p = u.patient;

      switch (u.state) {
        case 'to_scene': {
          if (this.driveTo(u, p.x, dt)) {
            u.state = 'loading';
            u.timer = now + LOAD_MS;
          }
          break;
        }
        case 'loading': {
          if (now >= u.timer) {
            p._riding = true;               // hidden while aboard
            u.state = 'to_hospital';
          }
          break;
        }
        case 'to_hospital': {
          if (this.driveTo(u, HOSPITAL.bay.x, dt)) {
            u.state = 'treating';
            u.timer = now + TREAT_MS;
            u.siren = false;
            p._riding = false;
            p.x = HOSPITAL.ward.x;          // laid up in the ward
            p.y = HOSPITAL.ward.y;
            p.facing = 'down';
          }
          break;
        }
        case 'treating': {
          if (now >= u.timer) {
            p._riding = true;
            u.state = 'to_home';
          }
          break;
        }
        case 'to_home': {
          const home = HOMES.find(h => h.slot === (p.def.slot ?? p.def.homeSlot));
          const dropX = home ? home.approach.x : HOSPITAL.bay.x;
          if (this.driveTo(u, dropX, dt)) {
            u.state = 'dropping';
            u.timer = now + DROP_MS;
          }
          break;
        }
        case 'dropping': {
          if (now >= u.timer) {
            const home = HOMES.find(h => h.slot === (p.def.slot ?? p.def.homeSlot));
            p._riding = false;
            if (home) { p.x = home.approach.x; p.y = home.approach.y; }
            p.injured = false;
            p._inCare = false;
            p.destination = null;           // let normal behaviour take over
            u.state = 'returning';
            u.siren = false;
          }
          break;
        }
        case 'returning': {
          if (this.driveTo(u, HOSPITAL.bay.x, dt)) u.state = 'done';
          break;
        }
      }

      // a passenger rides along with the van
      if (p._riding) { p.x = u.x + 1.5; p.y = u.y; }
    }

    this.units = this.units.filter(u => u.state !== 'done');
  }

  /** Move toward a target x along the road. True once arrived. */
  driveTo(u, targetX, dt) {
    const dx = targetX - u.x;
    const step = SPEED * dt;
    if (Math.abs(dx) <= step) { u.x = targetX; return true; }
    u.x += Math.sign(dx) * step;
    u.dir = Math.sign(dx);
    return false;
  }
}
