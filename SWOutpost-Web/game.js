// --- Outpost Command: browser 4X-lite prototype ---------------------------

const CELL = 48;
const GRID_W = 40;
const GRID_H = 40;
const PLANET_RADIUS_CELLS = 13;
const PLANET_CENTER_WORLD = { x: (GRID_W * CELL) / 2, y: (GRID_H * CELL) / 2 };

const BUILDING_DEFS = {
  commandCenter: {
    name: "Command Center", size: 2, buildTime: 0, color: "#ffb545",
    cost: {}, production: {}, placeable: false, maxHealth: 1000, housing: 10,
  },
  refinery: {
    name: "Refinery", size: 1, buildTime: 4, color: "#9bb0d6",
    cost: { credits: 150 }, production: { durasteel: 2 }, placeable: true, maxHealth: 150, key: "1",
  },
  fuelDepot: {
    name: "Fuel Depot", size: 1, buildTime: 4, color: "#49d9a0",
    cost: { credits: 100, durasteel: 50 }, production: { fuel: 1.5 }, placeable: true, maxHealth: 150, key: "2",
  },
  habitat: {
    name: "Habitat", size: 1, buildTime: 4, color: "#e0c171",
    cost: { credits: 120, durasteel: 40 }, production: {}, placeable: true, maxHealth: 140, housing: 8, key: "3",
  },
  barracks: {
    name: "Barracks", size: 2, buildTime: 6, color: "#c97b4a",
    cost: { credits: 200, durasteel: 75 }, production: {}, placeable: true, maxHealth: 250, key: "4",
  },
  turret: {
    name: "Turret", size: 1, buildTime: 3, color: "#ff5b54",
    cost: { credits: 100, durasteel: 100 }, production: {}, placeable: true, maxHealth: 180, key: "5",
  },
  shieldGenerator: {
    name: "Shield Gen.", size: 2, buildTime: 7, color: "#4ab0ff",
    cost: { credits: 300, durasteel: 150, fuel: 20 }, production: {}, placeable: true, maxHealth: 300, key: "6",
  },
  workshop: {
    name: "Workshop", size: 1, buildTime: 5, color: "#b084f0",
    cost: { credits: 250, durasteel: 100 }, production: {}, placeable: true, maxHealth: 200, key: "7",
  },
  landingPad: {
    name: "Landing Pad", size: 2, buildTime: 5, color: "#e6ecf9",
    cost: { credits: 200, fuel: 50 }, production: {}, placeable: true, maxHealth: 200, key: "8",
  },
};

const TECH_DEFS = {
  efficientRefineries: { name: "Efficient Refineries", desc: "+50% Durasteel production.", cost: { credits: 300, durasteel: 150 }, time: 10 },
  fuelInjectors: { name: "Fuel Injectors", desc: "+50% Fuel production.", cost: { credits: 250, durasteel: 80 }, time: 9 },
  reinforcedHulls: { name: "Reinforced Hulls", desc: "+50% structure max health.", cost: { credits: 350, durasteel: 200 }, time: 12 },
  advancedWeapons: { name: "Advanced Weapons", desc: "+50% turret & shield defense.", cost: { credits: 400, durasteel: 250 }, time: 14 },
  logisticsNetwork: { name: "Logistics Network", desc: "Troopers train 50% faster.", cost: { credits: 300, fuel: 100 }, time: 10 },
};

const TRAIN_COST = { credits: 40 };
const TRAIN_POP_COST = 1;
const TRAIN_BASE_TIME = 6;

const GALAXY_PLANETS = [
  { id: "home", name: "Virellis", owner: "player", faction: null, color: "#ffb545", x: 0.5, y: 0.5, strength: 0 },
  { id: "p1", name: "Dren Hollow", owner: "enemy", faction: "Korven Syndicate", color: "#ff5b54", x: 0.20, y: 0.28, strength: 90 },
  { id: "p2", name: "Ashvane", owner: "enemy", faction: "Ashreach Dominion", color: "#b084f0", x: 0.78, y: 0.20, strength: 150 },
  { id: "p3", name: "Coru Minor", owner: "neutral", faction: null, color: "#8293ba", x: 0.68, y: 0.76, strength: 45 },
  { id: "p4", name: "Hollow's Edge", owner: "enemy", faction: "The Drift Concord", color: "#4ab0ff", x: 0.16, y: 0.70, strength: 110 },
  { id: "p5", name: "Nym Reach", owner: "neutral", faction: null, color: "#8293ba", x: 0.86, y: 0.52, strength: 60 },
];

const state = {
  resources: { credits: 500, durasteel: 100, fuel: 50 },
  population: { current: 6, cap: 10 },
  troopers: 0,
  training: null,
  research: { activeId: null, progress: 0 },
  unlockedTechs: new Set(),
  buildings: [],
  camera: { x: PLANET_CENTER_WORLD.x, y: PLANET_CENTER_WORLD.y, zoom: 0.75 },
  placing: null,
  hoverCell: { x: 0, y: 0 },
  dragging: false,
  lastDrag: { x: 0, y: 0 },
  lastTime: performance.now(),
  gameTime: 0,
  view: "planet",
  stars: [],
  raid: { nextAt: 50, warned: false, strength: 0 },
  galaxy: { planets: GALAXY_PLANETS.map((p) => ({ ...p })), selectedId: null, nodes: [] },
  gameOver: false,
  victoryAchieved: false,
  fuelShortage: false,
  lastSaveAt: 0,
};

const SAVE_KEY = "outpostCommand.save.v1";
const TROOPER_FUEL_UPKEEP = 0.04;

function freshState() {
  return {
    resources: { credits: 500, durasteel: 100, fuel: 50 },
    population: { current: 6 },
    troopers: 0,
    training: null,
    research: { activeId: null, progress: 0 },
    unlockedTechs: [],
    buildings: [{
      type: "commandCenter",
      gx: Math.floor(GRID_W / 2) - 1,
      gy: Math.floor(GRID_H / 2) - 1,
      progress: 1,
      built: true,
      health: BUILDING_DEFS.commandCenter.maxHealth,
    }],
    gameTime: 0,
    raid: { nextAt: 50, warned: false, strength: 0 },
    galaxyPlanets: GALAXY_PLANETS.map((p) => ({ ...p })),
    victoryAchieved: false,
  };
}

function applySnapshot(snap) {
  state.resources = snap.resources;
  state.population.current = snap.population.current;
  state.troopers = snap.troopers;
  state.training = snap.training;
  state.research = snap.research;
  state.unlockedTechs = new Set(snap.unlockedTechs);
  state.buildings = snap.buildings;
  state.gameTime = snap.gameTime;
  state.raid = snap.raid;
  state.galaxy.planets = snap.galaxyPlanets;
  state.victoryAchieved = snap.victoryAchieved;
  state.gameOver = false;
}

function saveState() {
  const snap = {
    resources: state.resources,
    population: { current: state.population.current },
    troopers: state.troopers,
    training: state.training,
    research: state.research,
    unlockedTechs: [...state.unlockedTechs],
    buildings: state.buildings,
    gameTime: state.gameTime,
    raid: state.raid,
    galaxyPlanets: state.galaxy.planets,
    victoryAchieved: state.victoryAchieved,
  };
  try { localStorage.setItem(SAVE_KEY, JSON.stringify(snap)); } catch (err) { /* storage unavailable */ }
}

function loadState() {
  try {
    const raw = localStorage.getItem(SAVE_KEY);
    if (!raw) return false;
    const snap = JSON.parse(raw);
    if (!snap || !snap.buildings || !snap.resources) return false;
    applySnapshot(snap);
    return true;
  } catch (err) {
    return false;
  }
}

function newGame() {
  try { localStorage.removeItem(SAVE_KEY); } catch (err) { /* storage unavailable */ }
  applySnapshot(freshState());
  state.placing = null;
  state.galaxy.selectedId = null;
  document.getElementById("gameOverOverlay").classList.add("hidden");
  document.getElementById("victoryTag").classList.add("hidden");
  setView("planet");
}

const canvas = document.getElementById("game");
const ctx = canvas.getContext("2d");

// --- pre-rendered planet terrain texture (generated once, drawn scaled) ---
const PLANET_TEX_SIZE = 1024;
const planetTexCanvas = document.createElement("canvas");
planetTexCanvas.width = PLANET_TEX_SIZE;
planetTexCanvas.height = PLANET_TEX_SIZE;
(function generatePlanetTexture() {
  const tctx = planetTexCanvas.getContext("2d");
  tctx.fillStyle = "#121a2c";
  tctx.fillRect(0, 0, PLANET_TEX_SIZE, PLANET_TEX_SIZE);

  const biomes = ["#16233c", "#182640", "#10192c", "#1b2846", "#142338"];
  for (let i = 0; i < 16; i++) {
    const bx = Math.random() * PLANET_TEX_SIZE;
    const by = Math.random() * PLANET_TEX_SIZE;
    const br = 90 + Math.random() * 170;
    const g = tctx.createRadialGradient(bx, by, 0, bx, by, br);
    g.addColorStop(0, `${biomes[i % biomes.length]}dd`);
    g.addColorStop(1, `${biomes[i % biomes.length]}00`);
    tctx.fillStyle = g;
    tctx.beginPath(); tctx.arc(bx, by, br, 0, Math.PI * 2); tctx.fill();
  }
  for (let i = 0; i < 50; i++) {
    const cx = Math.random() * PLANET_TEX_SIZE;
    const cy = Math.random() * PLANET_TEX_SIZE;
    const cr = 6 + Math.random() * 28;
    const g = tctx.createRadialGradient(cx, cy, 0, cx, cy, cr);
    g.addColorStop(0, "rgba(0,0,0,0.38)");
    g.addColorStop(0.7, "rgba(0,0,0,0.12)");
    g.addColorStop(1, "rgba(0,0,0,0)");
    tctx.fillStyle = g;
    tctx.beginPath(); tctx.arc(cx, cy, cr, 0, Math.PI * 2); tctx.fill();
    tctx.strokeStyle = "rgba(130,160,210,0.10)";
    tctx.lineWidth = 1;
    tctx.beginPath(); tctx.arc(cx, cy, cr * 0.9, 0, Math.PI * 2); tctx.stroke();
  }
})();

function drawSpaceBackdrop() {
  const w = canvas.width, h = canvas.height;
  const g = ctx.createRadialGradient(w * 0.32, h * 0.22, 0, w * 0.32, h * 0.22, Math.max(w, h) * 0.95);
  g.addColorStop(0, "#0e1733");
  g.addColorStop(0.55, "#080c18");
  g.addColorStop(1, "#030409");
  ctx.fillStyle = g;
  ctx.fillRect(0, 0, w, h);
}

// --- building glyphs -------------------------------------------------------
function drawPolygon(x, y, r, sides) {
  ctx.beginPath();
  for (let i = 0; i < sides; i++) {
    const a = (Math.PI * 2 * i) / sides - Math.PI / 2;
    const px = x + Math.cos(a) * r, py = y + Math.sin(a) * r;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.stroke();
}
function drawStarShape(x, y, r, points, innerRatio) {
  ctx.beginPath();
  for (let i = 0; i < points * 2; i++) {
    const a = (Math.PI * i) / points - Math.PI / 2;
    const rad = i % 2 === 0 ? r : r * innerRatio;
    const px = x + Math.cos(a) * rad, py = y + Math.sin(a) * rad;
    if (i === 0) ctx.moveTo(px, py); else ctx.lineTo(px, py);
  }
  ctx.closePath();
  ctx.fill();
}
function drawDroplet(x, y, r) {
  ctx.beginPath();
  ctx.moveTo(x, y - r);
  ctx.quadraticCurveTo(x + r, y + r * 0.2, x, y + r);
  ctx.quadraticCurveTo(x - r, y + r * 0.2, x, y - r);
  ctx.closePath();
  ctx.stroke();
}
function drawDome(x, y, r) {
  ctx.beginPath();
  ctx.arc(x, y + r * 0.15, r, Math.PI, 0);
  ctx.lineTo(x + r, y + r * 0.5);
  ctx.lineTo(x - r, y + r * 0.5);
  ctx.closePath();
  ctx.stroke();
  ctx.beginPath();
  ctx.arc(x, y - r * 0.05, r * 0.16, 0, Math.PI * 2);
  ctx.fill();
}
function drawChevronShield(x, y, r) {
  ctx.beginPath();
  ctx.moveTo(x, y - r);
  ctx.lineTo(x + r * 0.8, y - r * 0.3);
  ctx.lineTo(x + r * 0.55, y + r * 0.9);
  ctx.lineTo(x - r * 0.55, y + r * 0.9);
  ctx.lineTo(x - r * 0.8, y - r * 0.3);
  ctx.closePath();
  ctx.stroke();
}
function drawRings(x, y, r) {
  ctx.beginPath(); ctx.arc(x, y, r * 0.95, 0, Math.PI * 2); ctx.stroke();
  ctx.beginPath(); ctx.arc(x, y, r * 0.38, 0, Math.PI * 2); ctx.fill();
}
function drawRingDot(x, y, r, lineWidth) {
  const prevWidth = ctx.lineWidth;
  ctx.lineWidth = lineWidth;
  ctx.beginPath(); ctx.arc(x, y, r * 0.92, 0, Math.PI * 2); ctx.stroke();
  ctx.lineWidth = prevWidth;
  ctx.beginPath(); ctx.arc(x, y, r * 0.2, 0, Math.PI * 2); ctx.fill();
}
function drawGear(x, y, r) {
  const teeth = 6;
  for (let i = 0; i < teeth; i++) {
    ctx.save();
    ctx.translate(x, y);
    ctx.rotate((Math.PI * 2 * i) / teeth);
    ctx.fillRect(-r * 0.12, -r * 1.05, r * 0.24, r * 0.3);
    ctx.restore();
  }
  ctx.beginPath(); ctx.arc(x, y, r * 0.6, 0, Math.PI * 2); ctx.stroke();
}
function drawPadCross(x, y, r) {
  ctx.beginPath(); ctx.arc(x, y, r * 0.95, 0, Math.PI * 2); ctx.stroke();
  const w = r * 0.22;
  ctx.fillRect(x - w / 2, y - r * 0.6, w, r * 1.2);
  ctx.fillRect(x - r * 0.6, y - w / 2, r * 1.2, w);
}

function drawBuildingGlyph(type, cx, cy, r, ink) {
  ctx.save();
  ctx.fillStyle = ink;
  ctx.strokeStyle = ink;
  ctx.lineWidth = Math.max(1.2, r * 0.16);
  switch (type) {
    case "commandCenter": drawStarShape(cx, cy, r, 5, 0.48); break;
    case "refinery": drawPolygon(cx, cy, r, 6); break;
    case "fuelDepot": drawDroplet(cx, cy, r); break;
    case "habitat": drawDome(cx, cy, r); break;
    case "barracks": drawChevronShield(cx, cy, r); break;
    case "turret": drawRings(cx, cy, r); break;
    case "shieldGenerator": drawRingDot(cx, cy, r, Math.max(1.5, r * 0.26)); break;
    case "workshop": drawGear(cx, cy, r); break;
    case "landingPad": drawPadCross(cx, cy, r); break;
  }
  ctx.restore();
}

function hasTech(id) { return state.unlockedTechs.has(id); }

function shadeColor(hex, amount) {
  const n = parseInt(hex.slice(1), 16);
  let r = (n >> 16) & 255, g = (n >> 8) & 255, b = n & 255;
  const mix = amount > 0 ? 255 : 0;
  const a = Math.abs(amount);
  r = Math.round(r + (mix - r) * a);
  g = Math.round(g + (mix - g) * a);
  b = Math.round(b + (mix - b) * a);
  return `rgb(${r},${g},${b})`;
}
function lighten(hex, amount) { return shadeColor(hex, amount); }
function darken(hex, amount) { return shadeColor(hex, -amount); }

function generateStars() {
  state.stars = Array.from({ length: 160 }, () => ({
    x: Math.random() * canvas.width,
    y: Math.random() * canvas.height,
    r: Math.random() * 1.4 + 0.3,
    a: Math.random() * 0.55 + 0.2,
  }));
}

function resizeCanvas() {
  canvas.width = window.innerWidth;
  canvas.height = window.innerHeight;
  generateStars();
}
window.addEventListener("resize", resizeCanvas);
resizeCanvas();

if (!loadState()) applySnapshot(freshState());

// --- coordinate helpers ---------------------------------------------------
function worldToScreen(wx, wy) {
  const z = state.camera.zoom;
  return { x: (wx - state.camera.x) * z + canvas.width / 2, y: (wy - state.camera.y) * z + canvas.height / 2 };
}
function screenToWorld(sx, sy) {
  const z = state.camera.zoom;
  return { x: (sx - canvas.width / 2) / z + state.camera.x, y: (sy - canvas.height / 2) / z + state.camera.y };
}
function worldToGrid(wx, wy) { return { gx: Math.floor(wx / CELL), gy: Math.floor(wy / CELL) }; }

function isWithinPlanet(gx, gy) {
  const cx = (gx + 0.5) * CELL;
  const cy = (gy + 0.5) * CELL;
  return Math.hypot(cx - PLANET_CENTER_WORLD.x, cy - PLANET_CENTER_WORLD.y) <= PLANET_RADIUS_CELLS * CELL;
}

function footprintCells(b) {
  const def = BUILDING_DEFS[b.type];
  const cells = [];
  for (let dx = 0; dx < def.size; dx++)
    for (let dy = 0; dy < def.size; dy++) cells.push({ gx: b.gx + dx, gy: b.gy + dy });
  return cells;
}
function isOccupied(gx, gy, ignore) {
  for (const b of state.buildings) {
    if (b === ignore) continue;
    for (const c of footprintCells(b)) if (c.gx === gx && c.gy === gy) return true;
  }
  return false;
}
function canAfford(cost) { return Object.entries(cost).every(([k, v]) => state.resources[k] >= v); }
function spend(cost) { Object.entries(cost).forEach(([k, v]) => (state.resources[k] -= v)); }

// --- build menu ------------------------------------------------------------
const menuEl = document.getElementById("buildMenu");
Object.entries(BUILDING_DEFS).filter(([, def]) => def.placeable).forEach(([key, def]) => {
  const btn = document.createElement("div");
  btn.className = "build-btn";
  btn.dataset.key = key;
  const costStr = Object.entries(def.cost).map(([k, v]) => `${v} ${k[0].toUpperCase()}`).join(" · ");
  btn.innerHTML = `<span class="key">${def.key}</span>
    <div class="swatch" style="background:${def.color}"></div>
    <div class="name">${def.name}</div>
    <div class="cost">${costStr}</div>`;
  btn.addEventListener("click", () => {
    state.placing = state.placing === key ? null : key;
    updateMenuActive();
  });
  menuEl.appendChild(btn);
});
function updateMenuActive() {
  [...menuEl.children].forEach((el) => el.classList.toggle("active", el.dataset.key === state.placing));
}

// --- view toggle -------------------------------------------------------
const viewToggleBtn = document.getElementById("viewToggle");
const buildDock = document.getElementById("buildDock");
const commandPanel = document.getElementById("commandPanel");
const researchPanel = document.getElementById("researchPanel");
const galaxyPanel = document.getElementById("galaxyPanel");

function setView(view) {
  state.view = view;
  state.placing = null;
  updateMenuActive();
  const inPlanet = view === "planet";
  buildDock.classList.toggle("hidden", !inPlanet);
  commandPanel.classList.toggle("hidden", !inPlanet);
  researchPanel.classList.toggle("hidden", !inPlanet);
  galaxyPanel.classList.toggle("hidden", inPlanet);
  viewToggleBtn.textContent = inPlanet ? "Galaxy Map" : "Return to Planet";
  viewToggleBtn.classList.toggle("active", !inPlanet);
  canvas.style.cursor = inPlanet ? "crosshair" : "pointer";
}
viewToggleBtn.addEventListener("click", () => setView(state.view === "planet" ? "galaxy" : "planet"));

const newGameBtn = document.getElementById("newGameBtn");
let newGameArmed = false;
let newGameArmTimeout = null;
newGameBtn.addEventListener("click", () => {
  if (newGameArmed) {
    newGameArmed = false;
    newGameBtn.textContent = "New Game";
    newGameBtn.classList.remove("armed");
    clearTimeout(newGameArmTimeout);
    newGame();
    return;
  }
  newGameArmed = true;
  newGameBtn.textContent = "Confirm?";
  newGameBtn.classList.add("armed");
  newGameArmTimeout = setTimeout(() => {
    newGameArmed = false;
    newGameBtn.textContent = "New Game";
    newGameBtn.classList.remove("armed");
  }, 4000);
});

// --- input ---------------------------------------------------------------
const tooltipEl = document.getElementById("tooltip");

function buildingAt(gx, gy) {
  for (const b of state.buildings) {
    for (const c of footprintCells(b)) if (c.gx === gx && c.gy === gy) return b;
  }
  return null;
}

function updateTooltip(clientX, clientY) {
  if (state.placing) { tooltipEl.classList.add("hidden"); return; }
  const b = buildingAt(state.hoverCell.gx, state.hoverCell.gy);
  if (!b) { tooltipEl.classList.add("hidden"); return; }
  const def = BUILDING_DEFS[b.type];
  let text = def.name;
  if (!b.built) {
    text += ` — constructing ${Math.round(b.progress * 100)}%`;
  } else {
    const maxHealth = def.maxHealth * (hasTech("reinforcedHulls") ? 1.5 : 1);
    text += ` — ${Math.max(0, Math.round(b.health))}/${Math.round(maxHealth)} HP`;
    if (def.production.durasteel) text += ` — +${(def.production.durasteel * (hasTech("efficientRefineries") ? 1.5 : 1)).toFixed(1)} Durasteel/s`;
    if (def.production.fuel) text += ` — +${(def.production.fuel * (hasTech("fuelInjectors") ? 1.5 : 1)).toFixed(1)} Fuel/s`;
    if (def.housing) text += ` — Houses ${def.housing}`;
  }
  tooltipEl.textContent = text;
  tooltipEl.style.left = `${clientX + 14}px`;
  tooltipEl.style.top = `${clientY + 16}px`;
  tooltipEl.classList.remove("hidden");
}

canvas.addEventListener("mousemove", (e) => {
  if (state.view === "galaxy") {
    tooltipEl.classList.add("hidden");
    return;
  }
  const world = screenToWorld(e.clientX, e.clientY);
  state.hoverCell = worldToGrid(world.x, world.y);
  if (state.dragging) {
    const dx = e.clientX - state.lastDrag.x;
    const dy = e.clientY - state.lastDrag.y;
    state.camera.x -= dx / state.camera.zoom;
    state.camera.y -= dy / state.camera.zoom;
    state.lastDrag = { x: e.clientX, y: e.clientY };
    tooltipEl.classList.add("hidden");
  } else {
    updateTooltip(e.clientX, e.clientY);
  }
});

canvas.addEventListener("mousedown", (e) => {
  if (state.view === "galaxy") {
    if (e.button === 0) selectGalaxyNodeAt(e.clientX, e.clientY);
    return;
  }
  if (e.button === 2 || e.button === 1) {
    state.dragging = true;
    state.lastDrag = { x: e.clientX, y: e.clientY };
    return;
  }
  if (e.button === 0 && state.placing) tryPlace(state.placing, state.hoverCell.gx, state.hoverCell.gy);
});
canvas.addEventListener("mouseup", () => (state.dragging = false));
canvas.addEventListener("contextmenu", (e) => {
  e.preventDefault();
  state.placing = null;
  updateMenuActive();
});
canvas.addEventListener("wheel", (e) => {
  if (state.view !== "planet") return;
  e.preventDefault();
  const factor = e.deltaY > 0 ? 0.9 : 1.1;
  state.camera.zoom = Math.min(2.2, Math.max(0.32, state.camera.zoom * factor));
}, { passive: false });

const KEY_TO_BUILDING = Object.fromEntries(
  Object.entries(BUILDING_DEFS).filter(([, def]) => def.key).map(([key, def]) => [def.key, key])
);
window.addEventListener("keydown", (e) => {
  if (e.key === "Escape") { state.placing = null; updateMenuActive(); return; }
  if (state.view !== "planet") return;
  const buildingKey = KEY_TO_BUILDING[e.key];
  if (buildingKey) { state.placing = state.placing === buildingKey ? null : buildingKey; updateMenuActive(); }
});

function tryPlace(key, gx, gy) {
  const def = BUILDING_DEFS[key];
  const cells = [];
  for (let dx = 0; dx < def.size; dx++) for (let dy = 0; dy < def.size; dy++) cells.push({ gx: gx + dx, gy: gy + dy });
  const onPlanet = cells.every((c) => isWithinPlanet(c.gx, c.gy));
  const free = cells.every((c) => !isOccupied(c.gx, c.gy));
  if (!onPlanet || !free || !canAfford(def.cost)) return;
  spend(def.cost);
  state.buildings.push({ type: key, gx, gy, progress: 0, built: false, health: 0 });
  state.placing = null;
  updateMenuActive();
}

// --- garrison panel (population + troopers) -------------------------------
const cpPop = document.getElementById("cp-pop");
const cpTroopers = document.getElementById("cp-troopers");
const trainBtn = document.getElementById("trainBtn");
const trainQueue = document.getElementById("trainQueue");
const trainQueueFill = document.getElementById("trainQueueFill");
const commandHint = document.getElementById("commandHint");

trainBtn.addEventListener("click", () => {
  if (state.training) return;
  const hasBarracks = state.buildings.some((b) => b.type === "barracks" && b.built);
  if (!hasBarracks) return;
  if (state.population.current < TRAIN_POP_COST || !canAfford(TRAIN_COST)) return;
  spend(TRAIN_COST);
  state.population.current -= TRAIN_POP_COST;
  const time = TRAIN_BASE_TIME * (hasTech("logisticsNetwork") ? 0.5 : 1);
  state.training = { progress: 0, timeNeeded: time };
});

function updateCommandPanel() {
  const hasBarracks = state.buildings.some((b) => b.type === "barracks" && b.built);
  cpPop.textContent = `${Math.floor(state.population.current)} / ${state.population.cap}`;
  cpTroopers.textContent = state.troopers;
  trainBtn.disabled = !hasBarracks || !!state.training || state.population.current < TRAIN_POP_COST || !canAfford(TRAIN_COST);
  commandHint.textContent = hasBarracks ? "" : "Build a Barracks to train troopers.";
  commandHint.style.display = hasBarracks ? "none" : "block";
  trainQueue.classList.toggle("hidden", !state.training);
  if (state.training) trainQueueFill.style.width = `${Math.min(100, (state.training.progress / state.training.timeNeeded) * 100)}%`;
}

// --- research panel ---------------------------------------------------------
const techListEl = document.getElementById("techList");
const researchHint = document.getElementById("researchHint");
const techEls = {};

Object.entries(TECH_DEFS).forEach(([id, def]) => {
  const el = document.createElement("div");
  el.className = "tech";
  const costStr = Object.entries(def.cost).map(([k, v]) => `${v} ${k[0].toUpperCase()}`).join(" · ");
  el.innerHTML = `<div class="tech-name">${def.name}</div>
    <div class="tech-desc">${def.desc}</div>
    <div class="tech-cost">${costStr} · ${def.time}s</div>
    <button class="tech-btn" type="button">Research</button>
    <div class="tech-bar"><div class="tech-bar-fill"></div></div>`;
  const btn = el.querySelector(".tech-btn");
  const bar = el.querySelector(".tech-bar-fill");
  btn.addEventListener("click", () => {
    const hasWorkshop = state.buildings.some((b) => b.type === "workshop" && b.built);
    if (!hasWorkshop || state.research.activeId || hasTech(id) || !canAfford(def.cost)) return;
    spend(def.cost);
    state.research = { activeId: id, progress: 0 };
  });
  techListEl.appendChild(el);
  techEls[id] = { btn, bar };
});

function updateResearchPanel() {
  const hasWorkshop = state.buildings.some((b) => b.type === "workshop" && b.built);
  researchHint.style.display = hasWorkshop ? "none" : "block";
  Object.entries(TECH_DEFS).forEach(([id, def]) => {
    const { btn, bar } = techEls[id];
    if (hasTech(id)) {
      btn.textContent = "Researched";
      btn.disabled = true;
      btn.classList.add("done");
      bar.style.width = "100%";
    } else if (state.research.activeId === id) {
      btn.textContent = "Researching…";
      btn.disabled = true;
      bar.style.width = `${Math.min(100, (state.research.progress / def.time) * 100)}%`;
    } else {
      btn.textContent = "Research";
      btn.disabled = !hasWorkshop || !!state.research.activeId || !canAfford(def.cost);
      bar.style.width = "0%";
    }
  });
}

// --- raid banner + toast ---------------------------------------------------
const raidBanner = document.getElementById("raidBanner");
const raidTimerEl = document.getElementById("raidTimer");
const raidStrengthEl = document.getElementById("raidStrength");
const toastEl = document.getElementById("toast");
let toastTimeout = null;

function showToast(msg, kind) {
  toastEl.textContent = msg;
  toastEl.className = kind || "";
  clearTimeout(toastTimeout);
  toastTimeout = setTimeout(() => toastEl.classList.add("hidden"), 3600);
}

function defensePower() {
  const advMult = hasTech("advancedWeapons") ? 1.5 : 1;
  const trooperMult = state.fuelShortage ? 0.5 : 1;
  let power = state.troopers * 12 * trooperMult;
  for (const b of state.buildings) {
    if (!b.built) continue;
    if (b.type === "turret") power += 30 * advMult;
    if (b.type === "shieldGenerator") power += 60 * advMult;
  }
  return power;
}

const gameOverOverlay = document.getElementById("gameOverOverlay");

function gameOver() {
  state.gameOver = true;
  try { localStorage.removeItem(SAVE_KEY); } catch (err) { /* storage unavailable */ }
  gameOverOverlay.classList.remove("hidden");
  raidBanner.classList.add("hidden");
}
document.getElementById("rebuildBtn").addEventListener("click", newGame);

function resolveRaid() {
  const strength = state.raid.strength;
  const defense = defensePower();
  raidBanner.classList.add("hidden");
  if (defense >= strength) {
    const salvage = Math.round(strength * 0.5);
    state.resources.credits += salvage;
    showToast(`Raid repelled. Salvaged ${salvage} credits.`, "win");
  } else {
    const shortfall = strength - defense;
    const trooperLoss = Math.min(state.troopers, Math.ceil(shortfall / 12));
    state.troopers -= trooperLoss;
    const popLoss = Math.min(state.population.current, Math.floor(Math.random() * 3) + 1);
    state.population.current -= popLoss;
    const targets = state.buildings.filter((b) => b.built);
    let damageNote = "";
    if (targets.length) {
      const target = targets[Math.floor(Math.random() * targets.length)];
      const maxHealth = BUILDING_DEFS[target.type].maxHealth * (hasTech("reinforcedHulls") ? 1.5 : 1);
      target.health -= maxHealth * 0.4;
      if (target.health <= 0) {
        if (target.type === "commandCenter") {
          showToast(`Raid breached defenses! Lost ${trooperLoss} troopers, ${popLoss} civilians. Command Center destroyed.`, "lose");
          gameOver();
          return;
        }
        state.buildings.splice(state.buildings.indexOf(target), 1);
        damageNote = ` ${BUILDING_DEFS[target.type].name} destroyed.`;
      } else {
        damageNote = ` ${BUILDING_DEFS[target.type].name} damaged.`;
      }
    }
    showToast(`Raid breached defenses! Lost ${trooperLoss} troopers, ${popLoss} civilians.${damageNote}`, "lose");
  }
  state.raid.nextAt = state.gameTime + 55 + Math.random() * 35;
  state.raid.warned = false;
}

// --- galaxy map --------------------------------------------------------
const galaxyInfo = document.getElementById("galaxyInfo");

function selectGalaxyNodeAt(clientX, clientY) {
  for (const node of state.galaxy.nodes) {
    const dx = clientX - node.sx;
    const dy = clientY - node.sy;
    if (Math.hypot(dx, dy) <= node.r + 4) {
      state.galaxy.selectedId = node.id;
      renderGalaxyInfo();
      return;
    }
  }
}

function renderGalaxyInfo() {
  const planet = state.galaxy.planets.find((p) => p.id === state.galaxy.selectedId);
  if (!planet) {
    galaxyInfo.innerHTML = `<div class="panel-hint">Select a planet to view its defenses.</div>`;
    return;
  }
  if (planet.owner === "player") {
    galaxyInfo.innerHTML = `<div class="planet-info-name">${planet.name}</div>
      <div class="planet-info-owner" style="color:${planet.color}">Your outpost</div>
      <div class="panel-hint">This is home. Return to the planet view to keep building it up.</div>`;
    return;
  }
  const ownerLabel = planet.owner === "neutral" ? "Unaligned" : planet.faction;
  galaxyInfo.innerHTML = `<div class="planet-info-name">${planet.name}</div>
    <div class="planet-info-owner" style="color:${planet.color}">${ownerLabel}</div>
    <div class="planet-info-stat"><span>Garrison strength</span><span class="mono">${planet.strength}</span></div>
    <div class="planet-info-stat"><span>Your troopers</span><span class="mono">${state.troopers}</span></div>
    <button class="attack-btn" type="button" ${state.troopers < 1 ? "disabled" : ""}>Launch Assault (commits all ${state.troopers})</button>`;
  const btn = galaxyInfo.querySelector(".attack-btn");
  if (btn) btn.addEventListener("click", () => attackPlanet(planet));
}

function checkVictory() {
  if (state.victoryAchieved) return;
  const allCaptured = state.galaxy.planets.every((p) => p.id === "home" || p.owner === "player");
  if (allCaptured) {
    state.victoryAchieved = true;
    document.getElementById("victoryTag").classList.remove("hidden");
    showToast("Sector Secured! Every world answers to Virellis now.", "win");
  }
}

function attackPlanet(planet) {
  const trooperMult = state.fuelShortage ? 0.5 : 1;
  const attackPower = state.troopers * 18 * trooperMult * (0.85 + Math.random() * 0.3);
  if (attackPower >= planet.strength) {
    const losses = Math.min(state.troopers, Math.round(state.troopers * (planet.strength / attackPower) * 0.5));
    state.troopers -= losses;
    planet.owner = "player";
    planet.strength = Math.round(planet.strength * 0.4);
    planet.color = "#ffb545";
    showToast(`${planet.name} captured! Lost ${losses} troopers taking it.`, "win");
    checkVictory();
  } else {
    showToast(`Assault on ${planet.name} failed. The attacking force was lost.`, "lose");
    state.troopers = 0;
  }
  renderGalaxyInfo();
}

// --- simulation ----------------------------------------------------------
function update(dt) {
  if (state.gameOver) return;
  state.gameTime += dt;

  // population cap from command center + habitats
  let cap = 0;
  for (const b of state.buildings) {
    const def = BUILDING_DEFS[b.type];
    if (def.housing && (b.built || b.type === "commandCenter")) cap += def.housing;
  }
  state.population.cap = cap;
  if (state.population.current < cap) {
    state.population.current = Math.min(cap, state.population.current + 0.25 * dt);
  }

  // construction + production
  const refineryMult = hasTech("efficientRefineries") ? 1.5 : 1;
  const fuelMult = hasTech("fuelInjectors") ? 1.5 : 1;
  for (const b of state.buildings) {
    const def = BUILDING_DEFS[b.type];
    if (!b.built) {
      b.progress += dt / Math.max(def.buildTime, 0.01);
      if (b.progress >= 1) {
        b.progress = 1;
        b.built = true;
        b.health = def.maxHealth * (hasTech("reinforcedHulls") ? 1.5 : 1);
      }
    } else {
      if (def.production.durasteel) state.resources.durasteel += def.production.durasteel * refineryMult * dt;
      if (def.production.fuel) state.resources.fuel += def.production.fuel * fuelMult * dt;
    }
  }

  // captured planets trickle income
  for (const p of state.galaxy.planets) {
    if (p.owner === "player" && p.id !== "home") state.resources.credits += 0.4 * dt;
  }

  // army logistics: troopers draw down fuel; running dry weakens them
  state.resources.fuel -= state.troopers * TROOPER_FUEL_UPKEEP * dt;
  state.fuelShortage = state.resources.fuel <= 0 && state.troopers > 0;

  for (const k of Object.keys(state.resources)) state.resources[k] = Math.max(0, state.resources[k]);

  // training
  if (state.training) {
    state.training.progress += dt;
    if (state.training.progress >= state.training.timeNeeded) {
      state.troopers += 1;
      state.training = null;
    }
  }

  // research
  if (state.research.activeId) {
    state.research.progress += dt;
    const def = TECH_DEFS[state.research.activeId];
    if (state.research.progress >= def.time) {
      state.unlockedTechs.add(state.research.activeId);
      state.research = { activeId: null, progress: 0 };
    }
  }

  // raids
  const timeToRaid = state.raid.nextAt - state.gameTime;
  if (timeToRaid <= 8 && !state.raid.warned) {
    state.raid.warned = true;
    state.raid.strength = Math.round(50 + Math.floor(state.gameTime / 60) * 25 + Math.random() * 25);
  }
  if (state.raid.warned && timeToRaid > 0) {
    raidBanner.classList.remove("hidden");
    raidTimerEl.textContent = Math.max(0, Math.ceil(timeToRaid));
    raidStrengthEl.textContent = state.raid.strength;
  }
  if (state.gameTime >= state.raid.nextAt) resolveRaid();

  document.getElementById("res-credits").textContent = Math.floor(state.resources.credits);
  document.getElementById("res-durasteel").textContent = Math.floor(state.resources.durasteel);
  document.getElementById("res-fuel").textContent = Math.floor(state.resources.fuel);
  document.getElementById("res-population").textContent = Math.floor(state.population.current);
  document.getElementById("res-pop-cap").textContent = state.population.cap;
  document.getElementById("res-troopers").textContent = state.troopers;
  document.querySelector('.gauge[data-res="fuel"]').classList.toggle("warning", state.fuelShortage);

  updateCommandPanel();
  updateResearchPanel();
  if (state.view === "galaxy" && state.galaxy.selectedId) renderGalaxyInfo();

  if (state.gameTime - state.lastSaveAt > 4) {
    state.lastSaveAt = state.gameTime;
    saveState();
  }
}

// --- render: planet view ----------------------------------------------
function drawStars() {
  for (const s of state.stars) {
    ctx.globalAlpha = s.a;
    ctx.fillStyle = "#cfe0ff";
    ctx.beginPath();
    ctx.arc(s.x, s.y, s.r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;
}

function drawPlanetSurface() {
  drawSpaceBackdrop();
  drawStars();

  const center = worldToScreen(PLANET_CENTER_WORLD.x, PLANET_CENTER_WORLD.y);
  const radius = PLANET_RADIUS_CELLS * CELL * state.camera.zoom;

  const glow = ctx.createRadialGradient(center.x, center.y, radius * 0.92, center.x, center.y, radius * 1.2);
  glow.addColorStop(0, "rgba(74,176,255,0.0)");
  glow.addColorStop(0.65, "rgba(74,176,255,0.12)");
  glow.addColorStop(1, "rgba(74,176,255,0)");
  ctx.fillStyle = glow;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius * 1.2, 0, Math.PI * 2);
  ctx.fill();

  ctx.save();
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
  ctx.clip();

  ctx.drawImage(planetTexCanvas, center.x - radius, center.y - radius, radius * 2, radius * 2);

  // subtle day/night shading so the sphere reads as lit from the upper-left
  const shade = ctx.createLinearGradient(center.x - radius, center.y - radius, center.x + radius * 0.6, center.y + radius);
  shade.addColorStop(0, "rgba(255,255,255,0.05)");
  shade.addColorStop(0.5, "rgba(0,0,0,0)");
  shade.addColorStop(1, "rgba(0,0,0,0.28)");
  ctx.fillStyle = shade;
  ctx.fillRect(center.x - radius, center.y - radius, radius * 2, radius * 2);

  ctx.strokeStyle = "#1c2a4a";
  ctx.lineWidth = 1;
  const topLeft = screenToWorld(center.x - radius, center.y - radius);
  const bottomRight = screenToWorld(center.x + radius, center.y + radius);
  const startGX = Math.max(0, Math.floor(topLeft.x / CELL));
  const endGX = Math.min(GRID_W, Math.ceil(bottomRight.x / CELL));
  const startGY = Math.max(0, Math.floor(topLeft.y / CELL));
  const endGY = Math.min(GRID_H, Math.ceil(bottomRight.y / CELL));
  for (let gx = startGX; gx <= endGX; gx++) {
    const p1 = worldToScreen(gx * CELL, startGY * CELL);
    const p2 = worldToScreen(gx * CELL, endGY * CELL);
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
  }
  for (let gy = startGY; gy <= endGY; gy++) {
    const p1 = worldToScreen(startGX * CELL, gy * CELL);
    const p2 = worldToScreen(endGX * CELL, gy * CELL);
    ctx.beginPath(); ctx.moveTo(p1.x, p1.y); ctx.lineTo(p2.x, p2.y); ctx.stroke();
  }
  ctx.restore();

  ctx.strokeStyle = "#3a5a86";
  ctx.lineWidth = 2;
  ctx.beginPath();
  ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
  ctx.stroke();
}

function drawBuilding(b) {
  const def = BUILDING_DEFS[b.type];
  const topLeft = worldToScreen(b.gx * CELL, b.gy * CELL);
  const size = CELL * def.size * state.camera.zoom;
  const x = topLeft.x + 2, y = topLeft.y + 2, w = size - 4, h = size - 4;
  const cx = x + w / 2, cy = y + h / 2;
  const rad = Math.min(6, w * 0.14);

  ctx.save();
  ctx.shadowColor = "rgba(0,0,0,0.45)";
  ctx.shadowBlur = 7;
  ctx.shadowOffsetY = 3;
  ctx.fillStyle = def.color;
  ctx.globalAlpha = b.built ? 1 : 0.16;
  ctx.beginPath(); ctx.roundRect(x, y, w, h, rad); ctx.fill();
  ctx.restore();

  if (!b.built) {
    const revealH = h * b.progress;
    ctx.save();
    ctx.beginPath(); ctx.rect(x, y + h - revealH, w, revealH); ctx.clip();
    ctx.fillStyle = def.color;
    ctx.beginPath(); ctx.roundRect(x, y, w, h, rad); ctx.fill();
    ctx.restore();

    ctx.strokeStyle = "#ffb545";
    ctx.lineWidth = Math.max(1.5, 2 * state.camera.zoom);
    ctx.beginPath();
    ctx.moveTo(x, y + h - revealH);
    ctx.lineTo(x + w, y + h - revealH);
    ctx.stroke();
  }

  ctx.strokeStyle = b.built ? "rgba(0,0,0,0.4)" : "rgba(255,255,255,0.2)";
  ctx.lineWidth = 1;
  ctx.beginPath(); ctx.roundRect(x, y, w, h, rad); ctx.stroke();

  if (b.built && state.camera.zoom > 0.42) {
    drawBuildingGlyph(b.type, cx, cy - h * 0.1, Math.min(w, h) * 0.26, "#0a0e18");
  }

  if (state.camera.zoom > 0.55) {
    ctx.fillStyle = b.built ? "#0a0e18" : "#d7deef";
    ctx.font = `${Math.max(9, 10.5 * state.camera.zoom)}px 'IBM Plex Sans', sans-serif`;
    ctx.textAlign = "center";
    ctx.fillText(def.name, cx, y + h - 6);
  }
}

function drawGhost() {
  if (!state.placing) return;
  const def = BUILDING_DEFS[state.placing];
  const { gx, gy } = state.hoverCell;
  const cells = [];
  for (let dx = 0; dx < def.size; dx++) for (let dy = 0; dy < def.size; dy++) cells.push({ gx: gx + dx, gy: gy + dy });
  const onPlanet = cells.every((c) => isWithinPlanet(c.gx, c.gy));
  const free = cells.every((c) => !isOccupied(c.gx, c.gy));
  const affordable = canAfford(def.cost);
  const valid = onPlanet && free && affordable;

  const topLeft = worldToScreen(gx * CELL, gy * CELL);
  const size = CELL * def.size * state.camera.zoom;
  const rad = Math.min(6, size * 0.14);
  ctx.fillStyle = valid ? "#49d9a055" : "#ff5b5455";
  ctx.beginPath(); ctx.roundRect(topLeft.x, topLeft.y, size, size, rad); ctx.fill();
  ctx.strokeStyle = valid ? "#49d9a0" : "#ff5b54";
  ctx.lineWidth = 2;
  ctx.setLineDash([5, 4]);
  ctx.beginPath(); ctx.roundRect(topLeft.x, topLeft.y, size, size, rad); ctx.stroke();
  ctx.setLineDash([]);
  if (valid) drawBuildingGlyph(state.placing, topLeft.x + size / 2, topLeft.y + size / 2 - size * 0.1, Math.min(size, size) * 0.26, "#0a0e18aa");
}

// --- render: galaxy view -----------------------------------------------
function drawGalaxy() {
  drawSpaceBackdrop();
  drawStars();

  state.galaxy.nodes = [];
  const home = state.galaxy.planets.find((p) => p.id === "home");
  const homeX = canvas.width * home.x;
  const homeY = canvas.height * home.y;

  for (const p of state.galaxy.planets) {
    if (p.id === "home") continue;
    const px = canvas.width * p.x;
    const py = canvas.height * p.y;
    const owned = p.owner === "player";
    ctx.strokeStyle = owned ? "rgba(255,181,69,0.35)" : "rgba(130,147,186,0.22)";
    ctx.lineWidth = owned ? 1.5 : 1;
    ctx.setLineDash(owned ? [] : [2, 5]);
    ctx.beginPath(); ctx.moveTo(homeX, homeY); ctx.lineTo(px, py); ctx.stroke();
    ctx.setLineDash([]);
  }

  for (const p of state.galaxy.planets) {
    const px = canvas.width * p.x;
    const py = canvas.height * p.y;
    const isHome = p.id === "home";
    const r = isHome ? 27 : 16 + Math.min(14, p.strength / 14);
    const selected = state.galaxy.selectedId === p.id;

    if (isHome || selected) {
      const glow = ctx.createRadialGradient(px, py, r * 0.6, px, py, r * 2.4);
      glow.addColorStop(0, `${p.color}50`);
      glow.addColorStop(1, `${p.color}00`);
      ctx.fillStyle = glow;
      ctx.beginPath(); ctx.arc(px, py, r * 2.4, 0, Math.PI * 2); ctx.fill();
    }

    // orbit ring
    ctx.strokeStyle = "rgba(226,235,255,0.14)";
    ctx.lineWidth = 1;
    ctx.beginPath(); ctx.arc(px, py, r * 1.55, 0, Math.PI * 2); ctx.stroke();

    // lit sphere: gradient offset toward the upper-left "light"
    const sphere = ctx.createRadialGradient(px - r * 0.4, py - r * 0.4, r * 0.1, px, py, r * 1.1);
    sphere.addColorStop(0, lighten(p.color, 0.35));
    sphere.addColorStop(0.55, p.color);
    sphere.addColorStop(1, darken(p.color, 0.35));
    ctx.fillStyle = sphere;
    ctx.beginPath(); ctx.arc(px, py, r, 0, Math.PI * 2); ctx.fill();
    ctx.strokeStyle = selected ? "#ffffff" : "rgba(0,0,0,0.4)";
    ctx.lineWidth = selected ? 2 : 1.3;
    ctx.stroke();

    if (isHome) {
      ctx.strokeStyle = "rgba(255,181,69,0.55)";
      ctx.lineWidth = 1.5;
      ctx.setLineDash([3, 4]);
      ctx.beginPath(); ctx.arc(px, py, r + 7, 0, Math.PI * 2); ctx.stroke();
      ctx.setLineDash([]);
    }

    ctx.fillStyle = "#e6ecf9";
    ctx.font = "600 13px 'IBM Plex Sans', sans-serif";
    ctx.textAlign = "center";
    ctx.fillText(p.name, px, py + r + 18);

    state.galaxy.nodes.push({ id: p.id, sx: px, sy: py, r });
  }
}

function render() {
  if (state.view === "planet") {
    drawPlanetSurface();
    for (const b of state.buildings) drawBuilding(b);
    drawGhost();
  } else {
    drawGalaxy();
  }
}

function loop() {
  const now = performance.now();
  const dt = Math.min(0.1, (now - state.lastTime) / 1000);
  state.lastTime = now;
  update(dt);
  render();
  requestAnimationFrame(loop);
}
requestAnimationFrame(loop);
