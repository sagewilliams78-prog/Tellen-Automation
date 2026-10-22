/**
 * Phase 1 boot: load sprites, build the world, wire the camera controls.
 *
 * Phase 1 scope is deliberately the map and the camera only. Agents,
 * furniture, bubbles and click-through panels arrive in later phases; the
 * hooks they need (room hit-testing, a per-frame dynamic layer) are already
 * in place here so they can be added without restructuring anything.
 */

import { TILE, WORLD, ROOMS, roomAt, SAGE_HOME, sageHomeSpots, FREEWAY } from './world/hq-map.js';
import { SPRITES } from './world/hq-map.js';
import { FURNITURE, FURNITURE_SPRITES, objectAt } from './world/furniture.js';
import { OUTDOOR_SPRITES } from './world/hq-map.js';
const CAR_SPRITES = ['car_red', 'car_blue', 'car_yellow', 'car_green', 'car_purple'];
import { ROSTER, ROSTER_SPRITES } from './agents/roster.js';
import { createAgents } from './agents/AgentSprite.js';
import { resolve } from './agents/activity.js';
import { personFor } from './agents/people.js';
import { Banter } from './agents/banter.js';
import { currentSession, isDark } from './world/lighting.js';
import { Wildlife } from './world/wildlife.js';
import { Traffic } from './world/traffic.js';
import { AirportOps } from './world/airport_ops.js';
import { Wanderer } from './world/wander.js';
import { EMS, INJURY_LINES } from './world/ems.js';
import { Commute } from './world/commute.js';
import { findPath, roomAnchor, homeDoor, cafeTarget } from './world/nav.js';
import { lakeSpot } from './world/hq-map.js';
import { store, symbols, studioShift, eligibleCount, dataAgeSeconds,
         incidentState, todaysPnl, riskFlags } from './state/store.js';
import { showAgent, showRoom, showObject, renderLog, wirePanelChrome, closePanel, showIncident } from './ui/panels.js';
import { updateNewsBulletin } from './ui/newsbulletin.js';
import { WorldCamera } from './world/camera.js';
import { Renderer, loadSprites } from './world/renderer.js';
import { AgentSprite } from './agents/AgentSprite.js';
import { SageGreeter } from './agents/sageGreet.js';

const canvas = document.getElementById('hq');
const statusEl = document.getElementById('status');
const zoomEl = document.getElementById('zoomLevel');
const roomEl = document.getElementById('roomReadout');

const cam = new WorldCamera(WORLD.w * TILE, WORLD.h * TILE, { minScale: 0.15, maxScale: 6 });
let renderer = null;
let needsDraw = true;
const banter = new Banter();
const wildlife = new Wildlife();
const sageGreeter = new SageGreeter();
const traffic = new Traffic();
// The Eastside Freeway -- denser, faster, all 5 car colours, no pedestrian
// hazard checks (nobody ever stands near it; see hq-map.js's FREEWAY).
const freewayTraffic = new Traffic({
  road: FREEWAY,
  sprites: ['car_red', 'car_blue', 'car_yellow', 'car_green', 'car_purple'],
  speed: 46,
  minGap: 1800,
  maxGap: 4500,
  pedestrianHazard: false
});
const ems = new EMS();
const airportOps = new AirportOps();
const wanderer = new Wanderer();
const commute = new Commute();
// only after hours does the car actually connect with anybody
traffic.onHit = (agent) => {
  agent.chat = INJURY_LINES[Math.floor(Math.random() * INJURY_LINES.length)];
  ems.dispatch(agent);
};
let seenTrades = null;   // null until the first poll, so we don't replay history
let lastIncident = null; // the current real incidentState(), for the banner's click handler
let lastTradeEvent = null; // most recent REAL trade this session has seen, for the live ticker
let flashUntil = 0;        // brief highlight window right after a NEW trade lands

function resize() {
  const dpr = window.devicePixelRatio || 1;
  const r = canvas.getBoundingClientRect();
  canvas.width = Math.round(r.width * dpr);
  canvas.height = Math.round(r.height * dpr);
  cam.setViewport(r.width, r.height);
  needsDraw = true;
}

// Characters animate continuously, so from Phase 3 on the loop draws every
// frame rather than only on input. Still cheap: the world is one cached
// bitmap blit plus ten 16x24 sprites.
let lastT = performance.now();

function frame(now) {
  const dt = Math.min((now - lastT) / 1000, 0.1);
  lastT = now;

  if (renderer) {
    for (const a of renderer.agents) a.update(dt);
    const sess = renderer.session;
    traffic.afterHours = !!(sess && sess.key !== 'open' && sess.key !== 'power');
    traffic.update(dt, renderer.agents);
    freewayTraffic.update(dt, renderer.agents);
    airportOps.update(dt);
    ems.update(dt);
    const shift = studioShift();
    {
      const occupied = new Set(renderer.agents.map(o => `${Math.round(o.x)},${Math.round(o.y)}`));
      wanderer.update(renderer.agents, shift ? shift.open : false, occupied);
    }
    commute.update(dt, renderer.agents.filter(a => a.def.commute), shift ? shift.open : null, Date.now());
    // A commuter's own car, while it's actually out on the shared main
    // road, poses the same hazard to a pedestrian as any other car --
    // scares them if they're close, and after hours can really connect.
    for (const u of commute.unitsOnMainRoad()) {
      traffic.checkHazard({ x: u.x, y: u.y, dir: u.dirSign, honkUntil: 0 }, renderer.agents, Date.now());
    }
    banter.tick(renderer.agents);
    if (renderer.player) {
      renderer.player.update(dt);
      wanderSage(Date.now());
      recordSageTrail();
      sageGreeter.tick(renderer.agents, renderer.player, Date.now());
    }
    if (renderer.dogs) {
      for (const dog of renderer.dogs) dog.update(dt);
      followTrail(renderer.dogs[0], 3);
      followTrail(renderer.dogs[1], 7);
    }
    wildlife.update(dt, !!sess && !isDark(sess));
    renderer.beaconT = (renderer.beaconT || 0) + dt;
    if (renderer.night) renderer.night.update(dt);
    if (renderer.season) renderer.season.update(dt);
    renderer.session = currentSession(store.raw);
    renderer.draw();
    if (needsDraw) { zoomEl.textContent = `${cam.scale}×`; needsDraw = false; }
  }
  requestAnimationFrame(frame);
}

/* ---- input ---------------------------------------------------------- */

let dragging = false, moved = false, lastX = 0, lastY = 0;

canvas.addEventListener('mousedown', e => {
  dragging = true; moved = false;
  lastX = e.clientX; lastY = e.clientY;
  canvas.style.cursor = 'grabbing';
});

window.addEventListener('mouseup', () => {
  dragging = false;
  canvas.style.cursor = 'grab';
});

/** Click: an agent takes priority over the room behind it. */
canvas.addEventListener('click', e => {
  if (moved || !renderer) return;
  const r = canvas.getBoundingClientRect();
  const w = cam.screenToWorld(e.clientX - r.left, e.clientY - r.top);

  const hitAgent = [...renderer.agents]
    .sort((a, b) => b.y - a.y)
    .find(a => {
      const b = a.bounds();
      return w.x >= b.x && w.x <= b.x + b.w && w.y >= b.y && w.y <= b.y + b.h;
    });
  if (hitAgent) return showAgent(hitAgent, store.raw);

  // then an interactive object (desk, terminal, screen), then the room
  const tx = Math.floor(w.x / TILE), ty = Math.floor(w.y / TILE);
  const obj = objectAt(tx, ty);
  if (obj) return showObject(obj, store.raw, renderer.agents);

  const room = roomAt(tx, ty);
  if (room) return showRoom(room, store.raw, renderer.agents);
  closePanel();
});

window.addEventListener('mousemove', e => {
  if (dragging) {
    const dx = e.clientX - lastX, dy = e.clientY - lastY;
    if (Math.abs(dx) + Math.abs(dy) > 2) moved = true;
    cam.panByScreen(dx, dy);
    lastX = e.clientX; lastY = e.clientY;
    needsDraw = true;
    return;
  }
  if (!renderer) return;
  const r = canvas.getBoundingClientRect();
  const w = cam.screenToWorld(e.clientX - r.left, e.clientY - r.top);
  const hit = roomAt(Math.floor(w.x / TILE), Math.floor(w.y / TILE));
  if (hit !== renderer.hoverRoom) {
    renderer.hoverRoom = hit;
    roomEl.textContent = hit ? `${hit.name} — ${hit.blurb}` : 'Drag to pan · scroll to zoom · "📍 Me" finds Sage and the dogs';
    needsDraw = true;
  }
});

canvas.addEventListener('wheel', e => {
  e.preventDefault();
  const r = canvas.getBoundingClientRect();
  cam.zoomAt(e.clientX - r.left, e.clientY - r.top, e.deltaY < 0 ? 1 : -1);
  needsDraw = true;
}, { passive: false });

document.getElementById('zoomIn').onclick = () => {
  cam.zoomAt(cam.viewW / 2, cam.viewH / 2, 1); needsDraw = true;
};
document.getElementById('zoomOut').onclick = () => {
  cam.zoomAt(cam.viewW / 2, cam.viewH / 2, -1); needsDraw = true;
};
document.getElementById('fit').onclick = () => { cam.fit(); needsDraw = true; };

const incidentBanner = document.getElementById('incidentBanner');
if (incidentBanner) incidentBanner.onclick = () => {
  if (lastIncident) showIncident(lastIncident, store.raw);
};

const findMeBtn = document.getElementById('findMe');
if (findMeBtn) findMeBtn.onclick = () => {
  if (!renderer || !renderer.player) return;
  cam.scale = 2;
  cam.centerOn(renderer.player.x * TILE, renderer.player.y * TILE);
  needsDraw = true;
};

// Triggers the exact same trip the doctors/Otis/Margo make on a real
// 09:00/16:00 ET edge -- just fired on a click instead of waiting for the
// clock, so it's actually watchable. Sends each commuter the OPPOSITE way
// from wherever their car actually is right now (checked per-doctor, not
// via a single shared toggle) -- deliberately never touches
// commute.wasOpen, which stays tied to the real market clock. Touching it
// here would desync from the real automatic system the very next frame,
// since that loop keeps resetting it to match the actual shift state.
const previewBtn = document.getElementById('previewCommute');
if (previewBtn) previewBtn.onclick = () => {
  if (!renderer) return;
  for (const doc of renderer.agents.filter(a => a.def.commute)) {
    if (commute.units.has(doc.def.id)) continue;      // already mid-trip, leave it
    const spot = commute.parked.get(doc.def.id);
    const atWork = !!(spot && 'staff' in spot);        // work spots carry a staff tag, home spots don't
    commute.startAll([doc], atWork ? 'to_home' : 'to_work');
  }
  needsDraw = true;
};

window.addEventListener('resize', resize);

/* ---- Sage: lives her own life, same as everyone else ----------------
 *
 * Keyboard control turned out unreliable in practice, so instead of
 * debugging input delivery she gets exactly the same treatment as every
 * NPC: a periodic re-target between a short list of real places (her own
 * house, the cafe, the lake), pathed to with the same findPath() everyone
 * else uses, walked with the same AgentSprite interpolation. No input
 * required -- she just wanders, continuously, like the rest of the city.
 */

let sageNextMove = 0;

function wanderSage(now) {
  const p = renderer.player;
  if (!p) return;
  if (p.path.length || now < sageNextMove) return;   // still walking, or not due yet

  const roll = Math.random();
  let spot = null;
  if (roll < 0.35) spot = cafeTarget(pickSociableCafeSpot(p));
  else if (roll < 0.6) spot = lakeSpot(Math.floor(Math.random() * 4));
  else {
    const homeSpots = sageHomeSpots();
    spot = homeSpots[Math.floor(Math.random() * homeSpots.length)];
  }

  const from = { x: Math.round(p.x), y: Math.round(p.y) };
  if (spot && (from.x !== spot.x || from.y !== spot.y)) {
    const occupied = new Set(renderer.agents.map(o => `${Math.round(o.x)},${Math.round(o.y)}`));
    p.setPath(findPath(from, spot, occupied));
  }
  sageNextMove = now + 15000 + Math.random() * 20000;   // 15-35s, matches the NPC cadence
}

/* ---- the dogs: follow wherever Sage has actually walked --------------
 *
 * Not "walk toward Sage's current position" (that would cut every corner
 * she takes) -- they retrace a recent point on her own path, the same way
 * a dog on a lead actually trails a few steps behind, not beside.
 */
const SAGE_TRAIL_MAX = 30;
const sageTrail = [];
let lastTrailPos = null;

function recordSageTrail() {
  const p = renderer.player;
  if (!p) return;
  const here = { x: Math.round(p.x), y: Math.round(p.y) };
  if (lastTrailPos && lastTrailPos.x === here.x && lastTrailPos.y === here.y) return;
  lastTrailPos = here;
  sageTrail.push(here);
  if (sageTrail.length > SAGE_TRAIL_MAX) sageTrail.shift();
}

function followTrail(dog, stepsBehind) {
  if (dog.path.length) return;
  const target = sageTrail[sageTrail.length - 1 - stepsBehind] || sageTrail[0];
  if (!target) return;
  if (dog._trailTarget && dog._trailTarget.x === target.x && dog._trailTarget.y === target.y) return;
  dog._trailTarget = target;
  const from = { x: Math.round(dog.x), y: Math.round(dog.y) };
  if (from.x !== target.x || from.y !== target.y) dog.setPath(findPath(from, target));
}

/* ---- go -------------------------------------------------------------- */

/**
 * Choose a cafe seat next to somebody already there, if anyone is. Falls back
 * to a free seat at random when the place is empty.
 */
function pickSociableCafeSpot(self) {
  const taken = new Map();
  for (const o of renderer.agents) {
    if (o !== self && o.atCafe && o.cafeIdx != null) taken.set(o.cafeIdx, o);
  }
  const free = [0, 1, 2, 3, 4, 5, 6, 7].filter(i => !taken.has(i));
  if (!free.length) return Math.floor(Math.random() * 8);
  if (!taken.size) return free[Math.floor(Math.random() * free.length)];

  // rank free seats by how close they sit to an occupied one
  let best = free[0], bestD = Infinity;
  for (const i of free) {
    const p = cafeTarget(i);
    if (!p) continue;
    for (const o of taken.values()) {
      const d = Math.hypot(o.x - p.x, o.y - p.y);
      if (d < bestD) { bestD = d; best = i; }
    }
  }
  return best;
}

/** What a given character actually owns at the General Store, from the
 * real /api/sim payload. Empty until it loads -- never guessed at. */
function ownedIds(agentId) {
  const r = store.sim && store.sim.residents.find(x => x.id === agentId);
  return r ? r.owned.map(o => o.id) : [];
}

/**
 * Bind live bot state onto the characters. Called on every poll.
 * Nothing here fabricates activity -- see agents/activity.js.
 */
function applyState(s) {
  if (!renderer) return;

  for (const a of renderer.agents) {
    const r = resolve(a.def, s);
    a.level = r.level;
    a.bubble = r.bubble;
    a.detail = r.detail;
    // the PERSON is fixed; the ticker is their current assignment
    const who = personFor(a.def);
    a.label = who ? (r.name ? `${who.name} · ${r.name}` : who.name)
                  : (r.name || a.def.name);

    // Anyone in the back of an ambulance is out of action until EMS is done.
    if (a.injured || a._inCare || a._riding) {
      a.bubble = a._riding ? '🚑 In the ambulance' : '🤕 Waiting for the ambulance';
      a.level = 'warn';
      continue;
    }

    // A doctor mid-commute is entirely owned by world/commute.js -- it sets
    // x/y/bubble itself every frame. Skip the normal resolve()/homing logic
    // so the two systems never fight over where they should be standing.
    if (a._commuting) continue;

    // decide where this character should be standing
    // Sal works the bar all day. She does go home -- she just lives upstairs,
    // so she only leaves once it is properly dark.
    let target = a.def.home;
    if (a.def.id === 'barista' && !isDark(currentSession())) {
      a.destination = { ...target };
      continue;
    }
    if (r.goto && r.goto.home != null) {
      // Off the clock. People drift between spots, and sometimes head to the
      // coffee shop instead of home. Purely ambient -- the status bubble is
      // still the real one, and nothing here is derived from market data.
      if (a.homeSlotIdx == null || Date.now() > (a.nextHomeMove || 0)) {
        const first = a.homeSlotIdx == null;
        a.homeSlotIdx = first
          ? (a.def.slot ?? 0) % 4
          : (a.homeSlotIdx + 1 + Math.floor(Math.random() * 3)) % 4;
        // they are a sociable bunch -- most off-duty stretches are spent
        // at the cafe rather than alone at home
        const roll = Math.random();
        a.venue = roll < 0.55 ? 'cafe' : roll < 0.75 ? 'lake' : 'home';
        a.lakeIdx = Math.floor(Math.random() * 4);
        // Sit near whoever is already in. People cluster; they don't
        // spread themselves evenly around an empty room.
        a.cafeIdx = pickSociableCafeSpot(a);
        a.nextHomeMove = Date.now() + 18000 + Math.random() * 22000;
      }

      // Sunrise Meadows residents live too far out to walk into town on a
      // whim -- if the roll above sent them toward the cafe or the lake,
      // they drive in first (world/commute.js), same reasoning as the
      // shift commute: the distance is real, so walking it for a coffee
      // would eat the whole visit. Only once they're actually in town does
      // the normal cafe/lake targeting below apply.
      // ...and anyone who has actually BOUGHT a car at the General Store
      // drives too, for the same reason they bought it: it beats walking.
      // `_carSprite` tells the renderer which one they're in -- a bought
      // car is drawn as the thing they own, not a generic stand-in.
      const bought = ownedIds(a.def.id);
      const ownsCar = bought.includes('newcar') || bought.includes('usedcar');
      if (ownsCar) a._carSprite = bought.includes('newcar') ? 'car_blue' : 'car_red';

      if (a.def.commute || ownsCar) {
        const wantsTown = a.venue !== 'home';
        if (wantsTown && !a._inTown) {
          if (!commute.units.has(a.def.id)) commute.startTownTrip(a, 'to_town');
          continue;
        }
        if (!wantsTown && a._inTown) {
          if (!commute.units.has(a.def.id)) commute.startTownTrip(a, 'to_home');
          continue;
        }
      }

      let spot = null;
      if (a.venue === 'cafe') spot = cafeTarget(a.cafeIdx);
      else if (a.venue === 'lake') spot = lakeSpot(a.lakeIdx);
      if (!spot) spot = homeDoor(r.goto.home, a.homeSlotIdx);
      if (spot) {
        target = spot;
        a.homeWhat = spot.what;
        a.atCafe = a.venue === 'cafe';
        a.atLake = a.venue === 'lake';
      }
    } else {
      a.homeSlotIdx = null;
      a.homeWhat = null;
      a.atCafe = false;
      a.atLake = false;
      if (r.goto && r.goto.room) {
        target = roomAnchor(r.goto.room) || a.def.home;
      } else if (r.goto && r.goto.symbolSlot != null && r.goto.symbolSlot >= 0) {
        const desk = ROSTER.find(d => d.slot === r.goto.symbolSlot);
        if (desk) target = { x: desk.home.x + 1, y: desk.home.y };
      }
    }

    // while at home the bubble says what they're actually doing in there
    if (a.homeWhat) a.bubble = `${a.atCafe ? '☕' : a.atLake ? '🦆' : '🏠'} ${a.homeWhat}`;

    const dest = a.destination;
    if (!dest || dest.x !== target.x || dest.y !== target.y) {
      a.destination = { ...target };
      const from = { x: Math.round(a.x), y: Math.round(a.y) };
      if (from.x !== target.x || from.y !== target.y) {
        // Solid collision: don't route straight through where somebody else
        // is currently standing -- see nav.js's findPath() avoid param.
        const occupied = new Set(
          renderer.agents.filter(o => o !== a)
            .map(o => `${Math.round(o.x)},${Math.round(o.y)}`)
        );
        a.setPath(findPath(from, target, occupied));
      }
    }
  }

  renderer.state = s;
  // What the town has actually bought, so purchases show up in the world
  // (see Renderer.drawOwnedGoods). Null until /api/sim first responds.
  renderer.sim = store.sim;
  renderLog(s);

  // Beacon severity, from real gates and real health checks
  const mech = (s && s.mechanics) || {};
  const active = (mech.hourly && mech.hourly.last_run) ? mech.hourly : mech.morning;
  const paused = /pausing/i.test((s && s.weekly_status) || '');
  renderer.beaconLevel =
    (active && active.status === 'needs_attention') ? 'alert'
    : (paused || (s && (s.earnings_blackout || []).length) || (active && active.status === 'fixed')) ? 'warn'
    : 'ok';

  // Trade moments: fire only for trades that appear AFTER we started watching
  const trades = (s && s.todays_trades) || [];
  const ids = trades.map(t => `${t.Date}|${t.Time}|${t.Symbol}`);
  if (seenTrades === null) {
    seenTrades = new Set(ids);                 // first poll: adopt, don't celebrate
    // still seed the live ticker with today's most recent real trade, if any
    // -- so it isn't empty on load, just not flashing as "new".
    if (trades.length) lastTradeEvent = { ...trades[trades.length - 1], seenAt: Date.now() };
  } else {
    for (let i = 0; i < trades.length; i++) {
      if (seenTrades.has(ids[i])) continue;
      seenTrades.add(ids[i]);
      const t = trades[i];
      const pnl = parseFloat(t['P&L']) || 0;
      const slot = symbols(s).findIndex(x => x.symbol === t.Symbol);
      const desk = ROSTER.find(d => d.slot === slot);
      const at = desk ? desk.home : { x: 32, y: 12 };
      renderer.effects = renderer.effects || [];
      renderer.effects.push({
        x: at.x, y: at.y, born: Date.now(), life: 2600,
        colour: pnl >= 0 ? '#4fbf6a' : '#e0503c',
        text: (pnl < 0 ? '-$' : '+$') + Math.abs(pnl).toFixed(2)
      });
      lastTradeEvent = { ...t, seenAt: Date.now() };
      flashUntil = Date.now() + 2400;
    }
  }

  const alerts = renderer.agents.filter(a => a.level === 'alert' || a.level === 'warn').length;
  const live = s ? (s.bot_alive ? 'bot live' : 'bot offline') : 'no data';
  statusEl.textContent =
    `${ROOMS.length} rooms · ${renderer.agents.length} characters · ${live}` +
    (alerts ? ` · ${alerts} alert${alerts > 1 ? 's' : ''}` : '');

  updateWallDisplay(s);
  updateNewsBulletin(s);
  updateLiveTicker(s);
}

/**
 * The live trades ticker -- one persistent, always-visible line, no click
 * required. Priority order, every real poll (~10s):
 *   1. A symbol's entry_flag is up right now -- a real live BUY signal
 *      (see dashboard_server.py's ZONE_LINE_RE parsing "⚡ ENTRY").
 *   2. The most recent real trade this session has actually seen open or
 *      close (todays_trades), briefly highlighted right when it's new.
 *   3. A quiet, honest idle line -- how many symbols are actually in a
 *      real BUY zone right now, out of how many are being scanned.
 * "Live" here means "as fresh as the last poll" (~10s), not tick-by-tick
 * streaming -- the label says so rather than implying something faster.
 */
function updateLiveTicker(s) {
  const el = document.getElementById('liveTicker');
  const text = document.getElementById('ltText');
  if (!el || !text) return;

  el.classList.remove('entering', 'gain', 'loss', 'flash');

  const entering = symbols(s).filter(x => x.entry_flag);
  if (entering.length) {
    const names = entering.map(x => x.symbol).join(', ');
    text.textContent = `⚡ ${names} entering the buy zone right now`;
    el.classList.add('entering');
    return;
  }

  if (lastTradeEvent) {
    const t = lastTradeEvent;
    const pnl = parseFloat(t['P&L']) || 0;
    const ago = Math.max(0, Math.round((Date.now() - t.seenAt) / 60000));
    const when = ago < 1 ? 'just now' : `${ago}m ago`;
    text.textContent = `${t.Symbol} ${pnl < 0 ? '-$' : '+$'}${Math.abs(pnl).toFixed(2)} · ` +
      `${t.Time || t.Date} ET · ${t.Reason || 'closed'} · ${when}`;
    el.classList.add(pnl >= 0 ? 'gain' : 'loss');
    if (Date.now() < flashUntil) el.classList.add('flash');
    return;
  }

  const inZone = symbols(s).filter(x => !x.narrow && (x.zone === 'BUY' || x.entry_flag)).length;
  const total = symbols(s).length;
  text.textContent = total
    ? `Watching ${total} symbol${total === 1 ? '' : 's'} · ${inZone} in a real buy zone right now`
    : 'Watching…';
}

/**
 * Mission-control wall display + incident banner. Runs every poll (10s),
 * completely independent of which panel (if any) is open -- situational
 * awareness without clicking anything. Every value here is read straight
 * off /api/status; nothing is computed from character animation state.
 */
function updateWallDisplay(s) {
  const session = currentSession(s);
  const set = (id, text, cls) => {
    const el = document.getElementById(id);
    if (!el) return;
    el.textContent = text;
    el.className = 'wv' + (cls ? ' ' + cls : '');
  };

  if (!s) {
    set('wBot', '—'); set('wEligible', '—'); set('wOpen', '—');
    set('wPnl', '—'); set('wRisk', '—'); set('wFresh', '—');
  } else {
    set('wBot', s.bot_alive ? 'Alive' : 'Offline', s.bot_alive ? 'ok' : 'alert');
    set('wEligible', `${eligibleCount(s)} / ${symbols(s).length}`,
        eligibleCount(s) > 0 ? 'ok' : 'idle');
    const openCount = (s.scan && s.scan.managed) || 0;
    set('wOpen', String(openCount), openCount > 0 ? 'warn' : 'idle');
    const pnl = todaysPnl(s);
    set('wPnl', (pnl < 0 ? '-$' : '+$') + Math.abs(pnl).toFixed(2),
        pnl > 0 ? 'ok' : pnl < 0 ? 'alert' : 'idle');
    const f = riskFlags(s);
    set('wRisk', f.alerting ? 'Blocked' : 'Clear', f.alerting ? 'warn' : 'ok');
    const age = dataAgeSeconds(s);
    set('wFresh', age == null ? '—' : age < 30 ? 'Live' : `${Math.round(age)}s old`,
        age == null ? 'idle' : age < 60 ? 'ok' : 'warn');
  }

  const inc = incidentState(s, session);
  const banner = document.getElementById('incidentBanner');
  const text = document.getElementById('incidentText');
  if (banner) {
    banner.classList.toggle('active', inc.active);
    if (inc.active) text.textContent = inc.reasons.map(r => r.text).join('  ·  ');
  }
  lastIncident = inc;
}

loadSprites([...SPRITES, ...FURNITURE_SPRITES, ...ROSTER_SPRITES, ...OUTDOOR_SPRITES, ...CAR_SPRITES,
             'ambulance', 'char_sage', 'char_dog1', 'char_dog2',
             'char_pet_cat', 'char_pet_dog', 'bicycle'])
  .then(sprites => {
    renderer = new Renderer(canvas, cam, sprites);
    renderer.traffic = traffic;
    renderer.freewayTraffic = freewayTraffic;
    renderer.airportOps = airportOps;
    renderer.ems = ems;
    renderer.commute = commute;
    renderer.agents = createAgents(ROSTER, sprites);
    // Sage, the owner -- kept OUT of `renderer.agents` on purpose. That
    // array is re-pathed every poll by applyState() from real bot/studio
    // state (see agents/activity.js); mixing her into it would mean the app
    // silently walks her back "home" every ~10s the way it does the
    // fictional cast. She gets her own field and her own ambient wander
    // instead (see wanderSage()), and is added into the draw/label passes
    // explicitly via Renderer.allAgents().
    const sageHome = { x: SAGE_HOME.interior.x + 6, y: SAGE_HOME.interior.y + 4 };
    renderer.player = new AgentSprite({ id: 'sage', name: 'Sage', home: sageHome, facing: 'down' },
                                       sprites.char_sage);
    renderer.dogs = [
      new AgentSprite({ id: 'dog1', name: 'Biscuit', home: { x: sageHome.x - 1, y: sageHome.y }, facing: 'down' },
                       sprites.char_dog1),
      new AgentSprite({ id: 'dog2', name: 'Pepper', home: { x: sageHome.x + 1, y: sageHome.y }, facing: 'down' },
                       sprites.char_dog2)
    ];
    renderer.wildlife = wildlife;
    wirePanelChrome();
    resize();
    cam.fit();
    statusEl.textContent =
      `${ROOMS.length} rooms · ${renderer.agents.length} characters · connecting…`;
    store.subscribe(applyState);
    store.start(10000);
    // handy for debugging in the console; nothing in the app reads this
    window.__hq = { cam, renderer, store };
    needsDraw = true;
    requestAnimationFrame(frame);
  })
  .catch(err => {
    statusEl.textContent = 'Failed to load sprites';
    roomEl.textContent = err.message;
    console.error(err);
  });
