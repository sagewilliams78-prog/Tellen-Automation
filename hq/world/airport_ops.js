/**
 * Smallville Regional's one ambient plane.
 *
 * Pure scenery, exactly like Traffic's cars on the main street -- this does
 * NOT represent a real flight. Dana's actual board (airport_business.py,
 * read from a real Gmail check) is the only real travel data in this city,
 * and as of the last check it says plainly: no upcoming flights. This
 * plane lands, sits at the gate a while (standing in for deplaning and
 * boarding), departs, and comes back about a minute later -- forever, with
 * nobody real on it, same honesty split as Bull & Bear's fictional
 * broadcast sitting next to the real news ticker.
 */
import { AIRPORT_RUNWAY } from './hq-map.js';

const RUNWAY_MIDY = AIRPORT_RUNWAY.y + AIRPORT_RUNWAY.h / 2;
const EDGE_X = AIRPORT_RUNWAY.x + AIRPORT_RUNWAY.w + 16;   // off the east edge, out of view
const TOUCHDOWN_X = AIRPORT_RUNWAY.x + AIRPORT_RUNWAY.w - 20;
const GATE_X = AIRPORT_RUNWAY.x + 22;                      // taxis here, under the apron/terminal

const FLIGHT_SPEED = 46;   // tiles/sec while approaching or departing
const TAXI_SPEED = 9;      // tiles/sec while taxiing to/from the gate
const GATE_MS = 14000;     // "deplaning and boarding"
const CYCLE_WAIT_MS = 60000;   // comes back about a minute after it leaves

export class AirportOps {
  constructor() {
    this.state = 'waiting';     // waiting | approaching | taxiing_in | boarding | taxiing_out | departing
    this.x = EDGE_X;
    this.y = RUNWAY_MIDY;
    this.nextAt = Date.now() + 4000;   // first arrival shortly after the page loads
    this.gateUntil = 0;
  }

  get visible() { return this.state !== 'waiting'; }
  /** Facing right (nose east) while departing/outbound, left while inbound. */
  get facingRight() { return this.state === 'taxiing_out' || this.state === 'departing'; }

  update(dt, now = Date.now()) {
    switch (this.state) {
      case 'waiting':
        if (now >= this.nextAt) { this.state = 'approaching'; this.x = EDGE_X; }
        break;
      case 'approaching':
        this.x -= FLIGHT_SPEED * dt;
        if (this.x <= TOUCHDOWN_X) this.state = 'taxiing_in';
        break;
      case 'taxiing_in':
        this.x -= TAXI_SPEED * dt;
        if (this.x <= GATE_X) { this.x = GATE_X; this.state = 'boarding'; this.gateUntil = now + GATE_MS; }
        break;
      case 'boarding':
        if (now >= this.gateUntil) this.state = 'taxiing_out';
        break;
      case 'taxiing_out':
        this.x += TAXI_SPEED * dt;
        if (this.x >= TOUCHDOWN_X) this.state = 'departing';
        break;
      case 'departing':
        this.x += FLIGHT_SPEED * dt;
        if (this.x >= EDGE_X) { this.state = 'waiting'; this.nextAt = now + CYCLE_WAIT_MS; }
        break;
    }
  }
}
