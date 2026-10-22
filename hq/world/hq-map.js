/**
 * Eva's Trading HQ -- floor plan.
 *
 * Everything is expressed in TILES (16 source px each). The renderer is the
 * only thing that converts tiles to pixels, so the whole building can be
 * rescaled by changing TILE alone.
 *
 * Every room here corresponds to a real subsystem of the live trading bot.
 * No room exists for a department the bot does not actually have.
 */

export const TILE = 16;
// The world is one continuous city: the HQ building sits top-left, a street
// runs beneath it, the residential row faces that street, and the park fills
// the space to the east. Interior coordinates are unchanged from Phase 1.
// Widened east so Sunrise Meadows' last house (Margo's, x249-258) isn't
// flush against the world boundary -- at w:260 it had a single tile of
// margin and read as cut off rather than as a house at the edge of town.
export const WORLD = { w: 700, h: 190 };
export const BUILDING = { x: 3, y: 3, w: 58, h: 40 };

/* ---- rooms -----------------------------------------------------------
   `data` names the real /api/status field(s) that will drive this room
   from Phase 4 onward. It is documentation now and wiring later. */
export const ROOMS = [
  {
    id: 'risk',
    name: 'Risk Office',
    floor: 'floor_carpet',
    accent: '#b0653a',
    rect: { x: 4, y: 4, w: 17, h: 16 },
    blurb: 'Win-rate breaker · earnings blackout',
    data: ['weekly_status', 'earnings_blackout']
  },
  {
    id: 'trading',
    name: 'Trading Floor',
    floor: 'floor_wood',
    accent: '#3f8f5c',
    rect: { x: 22, y: 4, w: 20, h: 16 },
    blurb: "Eva · live scan loop",
    data: ['scan', 'bot_alive', 'market_update'],
    primary: true
  },
  {
    id: 'records',
    name: 'Records Room',
    floor: 'floor_wood',
    accent: '#6d5ba8',
    rect: { x: 43, y: 4, w: 17, h: 16 },
    blurb: 'Trade log · equity curve · reviews',
    data: ['recent_trades', 'equity_curve', 'todays_reviews']
  },
  {
    id: 'watchlist',
    name: 'Watchlist Wing',
    floor: 'floor_wood',
    accent: '#2f7ba8',
    rect: { x: 4, y: 25, w: 24, h: 17 },
    blurb: 'One desk per tracked symbol',
    data: ['scan.symbols']
  },
  {
    id: 'mechanic',
    name: 'Mechanic Bay',
    floor: 'floor_tile',
    accent: '#c0392b',
    rect: { x: 29, y: 25, w: 15, h: 17 },
    blurb: 'Morning + hourly health checks',
    data: ['mechanics']
  },
  {
    id: 'break',
    name: 'Break Room',
    floor: 'floor_tile',
    accent: '#c9962f',
    rect: { x: 45, y: 25, w: 15, h: 17 },
    blurb: 'Off-hours · market closed',
    data: ['bot_alive']
  }
];

/** The central corridor every room opens onto. */
export const CORRIDOR = { x: 4, y: 21, w: 56, h: 3 };

/** Walls, 1 tile thick. Doors are punched through these afterwards. */
export const WALLS = [
  // building shell
  { x: 3,  y: 3,  w: 58, h: 1  },
  { x: 3,  y: 42, w: 58, h: 1  },
  { x: 3,  y: 3,  w: 1,  h: 40 },
  { x: 60, y: 3,  w: 1,  h: 40 },
  // corridor walls
  { x: 4,  y: 20, w: 56, h: 1  },
  { x: 4,  y: 24, w: 56, h: 1  },
  // dividers, top band
  { x: 21, y: 4,  w: 1,  h: 16 },
  { x: 42, y: 4,  w: 1,  h: 16 },
  // dividers, bottom band
  { x: 28, y: 25, w: 1,  h: 17 },
  { x: 44, y: 25, w: 1,  h: 17 }
];

/** Doorways -- drawn over the wall they interrupt. */
export const DOORS = [
  { x: 11, y: 20, w: 2, h: 1, room: 'risk' },
  { x: 31, y: 20, w: 2, h: 1, room: 'trading' },
  { x: 50, y: 20, w: 2, h: 1, room: 'records' },
  { x: 15, y: 24, w: 2, h: 1, room: 'watchlist' },
  { x: 35, y: 24, w: 2, h: 1, room: 'mechanic' },
  { x: 51, y: 24, w: 2, h: 1, room: 'break' },
  { x: 3,  y: 22, w: 1, h: 2, room: null, entrance: true },
  // staff door: Break Room out to the street, the route home
  { x: 51, y: 42, w: 2, h: 1, room: 'break', entrance: true }
];

/* ======================================================================
   OUTDOOR CITY
   ====================================================================== */

/**
 * The local street across the very top of the map, far northeast -- this
 * is what the future-district avenue actually connects to. Sunrise Meadows
 * (see SUBURB_HOMES below) fronts the west end of it; the rest stays open,
 * genuinely reserved ground for whatever gets built here next.
 */
export const TOP_ST = { x: 195, y: 15, w: 72, h: 4 };

/**
 * The avenue itself -- north off the main road, far northeast, clear of
 * the hospital and its lot, running up to TOP_ST. Exported (not just an
 * entry in STREETS) because world/commute.js drives the doctors' cars
 * along this exact route rather than teleporting them across it.
 */
export const AVENUE = { x: 200, y: 19, w: 5, h: 29 };

/**
 * The Eastside Freeway -- a real bypass along the SOUTH edge of the whole
 * map, clear of both downtown and the Eastside cul-de-sacs, not a road
 * cutting through the middle of either. Originally placed at y=20 (right
 * between downtown and the new district, reading as "through town") --
 * moved down here on Sage's correction. Full width, same as the main
 * street. No sidewalks alongside it on purpose: a freeway, not a street --
 * nobody walks the shoulder, so Traffic's pedestrian-hazard checks simply
 * never fire here (no agents are ever placed within KERB of it).
 */
export const FREEWAY = { x: 0, y: 180, w: WORLD.w, h: 4 };

/** Roads and pavements. Drawn under everything else outdoors. */

/**
 * The Eastside collector + its 7 cul-de-sac stubs, plus the connector that
 * ties it back to the original main street. Real modern-suburb shape: a
 * through-road, short dead-end stubs branching off it, each ending at a
 * court (see EASTSIDE_HOMES above) -- not a single straight ribbon.
 */
export const EASTSIDE_COLLECTOR = { x: 265, y: 110, w: 200, h: 6 };
export const EASTSIDE_CONNECTOR = { x: 300, y: 52, w: 6, h: 58 };
export const EASTSIDE_STUBS = [
  { x: 277, y: 102, w: 6, h: 8 },  // cul-de-sac stub 1
  { x: 317, y: 116, w: 6, h: 8 },  // cul-de-sac stub 2
  { x: 357, y: 102, w: 6, h: 8 },  // cul-de-sac stub 3
  { x: 397, y: 116, w: 6, h: 8 },  // cul-de-sac stub 4
  { x: 437, y: 102, w: 6, h: 8 },  // cul-de-sac stub 5
  { x: 297, y: 116, w: 6, h: 8 },  // cul-de-sac stub 6
  { x: 377, y: 102, w: 6, h: 8 },  // cul-de-sac stub 7
];

/**
 * Smallville Regional -- the airport. Built genuinely to scale relative to
 * everything else in this city: the runway alone is longer than the entire
 * original downtown. World widened from 480 to 700 specifically to hold
 * it, in its own territory east of the Eastside with nothing else out
 * there. The apron is the paved walk from the terminal down to the
 * runway/freeway; the runway itself is paved (walkable, like any street)
 * but carries no pedestrian-hazard checks and no Traffic instance -- it's
 * dressed with real runway markings in the renderer, not driven by cars.
 */
export const AIRPORT_RUNWAY = { x: 500, y: 150, w: 170, h: 18 };
export const AIRPORT_APRON  = { x: 550, y: 116, w: 30, h: 34 };

export const STREETS = [
  { x: 0, y: 48, w: WORLD.w, h: 4 },        // main street
  { x: 50, y: 43, w: 4, h: 5 },             // connector from the HQ staff door
  // Real road, real houses on it (Sunrise Meadows fronts TOP_ST), real room
  // left over for whatever the next district turns out to be.
  AVENUE,
  TOP_ST,
  FREEWAY,
  EASTSIDE_COLLECTOR,
  EASTSIDE_CONNECTOR,
  ...EASTSIDE_STUBS,
  AIRPORT_RUNWAY,
  AIRPORT_APRON
];

export const SIDEWALKS = [
  { x: 0, y: 47, w: WORLD.w, h: 1 },
  { x: 0, y: 52, w: WORLD.w, h: 1 }
];

/** Dashed centre line segments, drawn procedurally by the renderer. */
export const ROAD_LINE = { y: 49.6, x0: 0, x1: WORLD.w };

/* ----------------------------------------------------------------------
   WHERE PEOPLE LIVE

   Four standalone houses still line the street. Everyone else lives in the
   condo block beside the coffee shop. Either way a unit belongs to a SLOT,
   so unit 3 is Gus's whichever ticker he is covering this week.
   ---------------------------------------------------------------------- */

const HOME_W = 10, HOME_H = 8, HOME_Y = 54;
const HOUSE_XS = [4, 18, 32, 46];          // the four that stayed on the street

const UNIT_W = 7, UNIT_H = 6;
const CONDO_X = 90, CONDO_Y = 28;

export const CONDO = {
  name: 'Smallville Condos',
  rect:     { x: CONDO_X, y: CONDO_Y, w: 25, h: 19 },
  corridor: { x: CONDO_X + 1, y: CONDO_Y + 8, w: 23, h: 3 },
  entrance: { x: CONDO_X, y: CONDO_Y + 8, w: 1, h: 3 },      // west door
  accent:   '#7c6aa8'
};

/** Furniture in a standalone house (interior 8x6). */
export const HOME_LAYOUT = [
  { sprite: 'bed',         dx: 1, dy: 1, w: 2, h: 3, soft: true },
  { sprite: 'plant',       dx: 3, dy: 1, w: 1, h: 1 },
  { sprite: 'fridge',      dx: 7, dy: 1, w: 2, h: 2 },
  { sprite: 'kitchen',     dx: 7, dy: 3, w: 2, h: 1 },
  { sprite: 'table_small', dx: 4, dy: 3, w: 2, h: 2 },
  { sprite: 'chair',       dx: 6, dy: 4, w: 1, h: 1 },
  { sprite: 'couch',       dx: 1, dy: 5, w: 4, h: 2, soft: true },
  { sprite: 'tv',          dx: 6, dy: 6, w: 2, h: 1 },
  { sprite: 'plant',       dx: 8, dy: 6, w: 1, h: 1 }
];

/** Furniture in a condo unit (interior 7x6) -- smaller, four pieces. */
export const UNIT_LAYOUT = [
  { sprite: 'bed',         dx: 0, dy: 0, w: 2, h: 3, soft: true },
  { sprite: 'kitchen',     dx: 5, dy: 0, w: 2, h: 1 },
  { sprite: 'table_small', dx: 3, dy: 2, w: 2, h: 2 },
  { sprite: 'couch',       dx: 0, dy: 4, w: 4, h: 2, soft: true },
  { sprite: 'tv',          dx: 5, dy: 5, w: 2, h: 1 },
  { sprite: 'plant',       dx: 6, dy: 2, w: 1, h: 1 }
];

/** Standing spots, per home type. Ambient only -- never claimed as data. */
export const HOUSE_SPOTS = [
  { dx: 1, dy: 2, what: 'resting' },
  { dx: 2, dy: 5, what: 'on the couch' },
  // (6,2) used to land squarely on the kitchen counter itself --
  // unwalkable in every standalone house, not just the new ones, so
  // homeDoor() silently fell back to the front step every time this index
  // came up, which is why nobody was ever seen inside. (7,3) is directly
  // below the counter and is genuinely clear in every standalone house,
  // checked against BOTH the collision grid and each home's real drawn
  // furniture (the two disagree -- see the note in outdoorBlocked()).
  { dx: 7, dy: 3, what: 'in the kitchen' },
  { dx: 3, dy: 4, what: 'at the table' }
];
export const UNIT_SPOTS = [
  { dx: 0, dy: 1, what: 'resting' },
  { dx: 1, dy: 4, what: 'on the couch' },
  { dx: 4, dy: 0, what: 'in the kitchen' },
  { dx: 2, dy: 3, what: 'at the table' }
];

/**
 * Personalised interiors.
 *
 * Every home keeps the same four functional anchors -- bed, couch, kitchen,
 * table -- because HOUSE_SPOTS / UNIT_SPOTS place people on them ("resting",
 * "on the couch", "in the kitchen", "at the table"). Move those and someone
 * ends up asleep on bare floorboards.
 *
 * What changes per person is everything else: what they collect, what they
 * work on at home, how cluttered it is. Each entry says who it belongs to and
 * what the room is meant to say about them.
 *
 * Street-house layouts are RECT-relative (interior starts at +1,+1).
 * Unit layouts are INTERIOR-relative. That matches how the renderer draws each.
 */

// --- street houses, slots 0-3 (interior 8x6, so dx 1..8 / dy 1..6) ----------
const HOUSE_BASE = [
  { sprite: 'bed',         dx: 1, dy: 1, soft: true },
  { sprite: 'kitchen',     dx: 7, dy: 3 },
  { sprite: 'fridge',      dx: 7, dy: 1 },
  { sprite: 'table_small', dx: 4, dy: 3 },
  { sprite: 'couch',       dx: 1, dy: 5, soft: true }
];

// --- condo units + terrace, slots 4-12 (interior 7x6) -----------------------
const UNIT_BASE = [
  { sprite: 'bed',         dx: 0, dy: 0, soft: true },
  { sprite: 'kitchen',     dx: 5, dy: 0 },
  { sprite: 'table_small', dx: 3, dy: 2 },
  { sprite: 'couch',       dx: 0, dy: 4, soft: true }
];

export const HOME_STYLES = {
  // ---- street houses (rect-relative; free cells are dx3-6/dy1-2, dx6-8/dy4-6)
  0: { who: 'Rosa',  style: 'Lived-in',        floor: 'floor_wood',
       note: 'Thirty years of clutter and a telly she talks back to.',
       extra: [{ sprite: 'bookshelf', dx: 3, dy: 1 }, { sprite: 'plant', dx: 6, dy: 1 },
               { sprite: 'tv', dx: 7, dy: 5 }, { sprite: 'plant', dx: 6, dy: 6 }] },
  1: { who: 'Miles', style: 'Orderly',         floor: 'floor_wood',
       note: 'An ex-actuary keeps his files at home too.',
       extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'desk_small', dx: 5, dy: 1 },
               { sprite: 'chair', dx: 4, dy: 2 }, { sprite: 'bookshelf', dx: 7, dy: 5 }] },
  2: { who: 'Priya', style: 'Barely unpacked', floor: 'floor_tile',
       note: 'Moved in months ago. The boxes have not moved since.',
       extra: [{ sprite: 'crate', dx: 3, dy: 1 }, { sprite: 'crate', dx: 4, dy: 1 },
               { sprite: 'crate', dx: 3, dy: 2 }, { sprite: 'tv', dx: 7, dy: 5 }] },
  3: { who: 'Gus',   style: 'Comfortable',     floor: 'floor_carpet',
       note: 'One good chair, one good telly, nothing to prove.',
       extra: [{ sprite: 'tv', dx: 7, dy: 5 }, { sprite: 'chair', dx: 6, dy: 3 },
               { sprite: 'plant', dx: 3, dy: 1 }, { sprite: 'bookshelf', dx: 5, dy: 1 }] },

  // ---- condo units (interior-relative; free blocks dx2-4/dy0-1, dx5-6/dy1-3, dx4-6/dy4-5)
  4: { who: 'June', style: 'Studious', floor: 'floor_wood',
       note: 'The quiet one reads at home as well.',
       extra: [{ sprite: 'bookshelf', dx: 2, dy: 0 }, { sprite: 'desk_small', dx: 5, dy: 2 },
               { sprite: 'chair', dx: 4, dy: 4 }, { sprite: 'plant', dx: 2, dy: 1 }] },
  5: { who: 'Cy',    style: 'Sunny',            floor: 'floor_wood',
       note: 'Plants in every corner. Relentlessly cheerful about it.',
       extra: [{ sprite: 'plant', dx: 2, dy: 0 }, { sprite: 'plant', dx: 2, dy: 1 },
               { sprite: 'plant', dx: 6, dy: 1 }, { sprite: 'plant', dx: 4, dy: 4 },
               { sprite: 'bookshelf', dx: 5, dy: 4 }] },
  6: { who: 'Wren',  style: 'Workshop',         floor: 'floor_tile',
       note: 'An engineer never really stops taking things apart.',
       extra: [{ sprite: 'desk_small', dx: 2, dy: 0 }, { sprite: 'server_rack', dx: 5, dy: 2 },
               { sprite: 'crate', dx: 4, dy: 4 }, { sprite: 'crate', dx: 4, dy: 1 }] },
  7: { who: 'Eva',   style: 'Barely lived in',  floor: 'floor_tile',
       note: 'A bot does not really need a flat. It has one anyway.',
       extra: [{ sprite: 'server_rack', dx: 2, dy: 0 }, { sprite: 'wallscreen', dx: 4, dy: 4 },
               { sprite: 'crate', dx: 6, dy: 2 }] },
  // Units 8 and 9 stood empty once Margo and Otis moved to real houses of
  // their own out in Sunrise Meadows (slots 18 and 17) -- now occupied
  // again, by the Field Office's two officers (see FIELD_OFFICE below).
  8: { who: 'Voss', style: 'Sparse, deliberately', floor: 'floor_wood',
       note: 'Nothing on the walls. Says it is easier to leave a place than to have left a home.',
       extra: [{ sprite: 'filing_cabinet', dx: 2, dy: 0 }, { sprite: 'desk_small', dx: 5, dy: 1 },
               { sprite: 'chair', dx: 5, dy: 4 }] },
  9: { who: 'Ito', style: 'One wall of case notes', floor: 'floor_tile',
       note: 'Off duty, allegedly. The corkboard says otherwise.',
       extra: [{ sprite: 'bookshelf', dx: 2, dy: 0 }, { sprite: 'whiteboard', dx: 4, dy: 4 },
               { sprite: 'plant', dx: 2, dy: 1 }] },

  // ---- The Darkroom terrace ------------------------------------------------
  10: { who: 'Della', style: 'The archive',     floor: 'floor_wood',
        note: 'Her flat is an extension of the research wall.',
        extra: [{ sprite: 'bookshelf', dx: 2, dy: 0 }, { sprite: 'bookshelf', dx: 5, dy: 2 },
                { sprite: 'filing_cabinet', dx: 2, dy: 1 }, { sprite: 'plant', dx: 6, dy: 4 }] },
  11: { who: 'Nell', style: "Writer's room", floor: 'floor_carpet',
        note: 'A desk facing a wall, on purpose.',
        extra: [{ sprite: 'desk_small', dx: 2, dy: 0 }, { sprite: 'chair', dx: 4, dy: 1 },
                { sprite: 'whiteboard', dx: 4, dy: 4 }, { sprite: 'bookshelf', dx: 5, dy: 2 }] },
  12: { who: 'Rafa',  style: 'Edit suite',      floor: 'floor_carpet',
        note: 'He cuts at home when the studio is shut.',
        extra: [{ sprite: 'wallscreen', dx: 4, dy: 4 }, { sprite: 'desk_small', dx: 5, dy: 2 },
                { sprite: 'chair', dx: 4, dy: 5 }, { sprite: 'plant', dx: 2, dy: 1 }] },

  // ---- above the shop ------------------------------------------------------
  13: { who: 'Sal',   style: 'Above the shop',  floor: 'floor_wood',
        note: 'Lives a staircase from the counter. Hears everything twice.',
        extra: [{ sprite: 'espresso', dx: 3, dy: 1 }, { sprite: 'bookshelf', dx: 5, dy: 1 },
                { sprite: 'tv', dx: 7, dy: 5 }, { sprite: 'plant', dx: 6, dy: 6 }] },

  // ---- Wes's cottage, west of the pond (street-house style, slot 14) ------
  14: { who: 'Wes',   style: 'Still just planning', floor: 'floor_wood',
        note: 'The checklist lives on the kitchen table some nights too.',
        extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'desk_small', dx: 5, dy: 1 },
                { sprite: 'chair', dx: 4, dy: 2 }, { sprite: 'coffee', dx: 7, dy: 5 }] },

  // ---- Sunrise Meadows: the two doctors, then Margo and Otis, pulled out
  // of the condo into real houses (slots 15-18) -- see SUBURB in this file.
  15: { who: 'Dr. Ahn',  style: 'Decompressing', floor: 'floor_wood',
        note: 'A long drive home is apparently part of how she unwinds.',
        extra: [{ sprite: 'bookshelf', dx: 3, dy: 1 }, { sprite: 'plant', dx: 6, dy: 1 },
                { sprite: 'tv', dx: 7, dy: 5 }, { sprite: 'coffee', dx: 6, dy: 6 }] },
  16: { who: 'Dr. Reyes', style: 'Somewhere else entirely', floor: 'floor_carpet',
        note: 'Whatever happened at the hospital stays at the hospital.',
        extra: [{ sprite: 'crate', dx: 3, dy: 1 }, { sprite: 'chair', dx: 5, dy: 1 },
                { sprite: 'bookshelf', dx: 7, dy: 5 }, { sprite: 'plant', dx: 6, dy: 6 }] },
  17: { who: 'Otis',  style: 'Practical, just bigger now', floor: 'floor_tile',
        note: 'Tools by the door. Kettle on. More room to spread the tools out.',
        extra: [{ sprite: 'desk_small', dx: 3, dy: 1 }, { sprite: 'crate', dx: 6, dy: 1 },
                { sprite: 'crate', dx: 7, dy: 4 }, { sprite: 'coffee', dx: 6, dy: 6 }] },
  18: { who: 'Margo', style: 'Fortified, with a yard now', floor: 'floor_wood',
        note: 'Everything filed, everything shut. Immovable at home too.',
        extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'filing_cabinet', dx: 4, dy: 1 },
                { sprite: 'bookshelf', dx: 7, dy: 5 }, { sprite: 'crate', dx: 6, dy: 6 }] },

  // ---- The News Desk: Bull & Bear's own places, slots 19-20 -- see
  // NEWS_STUDIO below for where they work. Street-house style (same 10x8
  // footprint as slots 0-3), just placed near the studio instead of on the
  // original street.
  19: { who: 'Bull', style: 'Relentlessly upbeat', floor: 'floor_carpet',
        note: 'Motivational posters. A treadmill desk he has never once stood at.',
        extra: [{ sprite: 'bookshelf', dx: 3, dy: 1 }, { sprite: 'plant', dx: 6, dy: 1 },
                { sprite: 'tv', dx: 7, dy: 5 }, { sprite: 'plant', dx: 6, dy: 6 }] },
  20: { who: 'Bear', style: 'Dry and minimal', floor: 'floor_tile',
        note: 'One good chair. Everything else in this room is negotiable.',
        extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'chair', dx: 5, dy: 1 },
                { sprite: 'bookshelf', dx: 7, dy: 5 }, { sprite: 'plant', dx: 6, dy: 6 }] },
  21: { who: 'Marnie', style: 'Tidy, ledger-brained', floor: 'floor_wood',
        note: 'Balances her own checkbook to the penny. Says it is a professional habit.',
        extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'desk_small', dx: 5, dy: 1 },
                { sprite: 'chair', dx: 4, dy: 2 }, { sprite: 'bookshelf', dx: 7, dy: 5 }] },
  22: { who: 'Percy', style: 'Every receipt, filed', floor: 'floor_tile',
        note: 'Keeps a shoebox of real receipts. Insists a shoebox is a filing system.',
        extra: [{ sprite: 'filing_cabinet', dx: 3, dy: 1 }, { sprite: 'desk_small', dx: 5, dy: 1 },
                { sprite: 'chair', dx: 4, dy: 2 }, { sprite: 'bookshelf', dx: 7, dy: 5 }] },

  // ---- The Outskirts (street-house style, slots 29-30) --------------------
  29: { who: 'Theo', style: 'Fixing things that were not broken', floor: 'floor_wood',
        note: 'A workbench takes up most of the free wall.',
        extra: [{ sprite: 'crate', dx: 3, dy: 1 }, { sprite: 'desk_small', dx: 5, dy: 1 },
                { sprite: 'chair', dx: 4, dy: 2 }, { sprite: 'crate', dx: 7, dy: 5 }] },
  30: { who: 'Greta', style: 'More plant than furniture', floor: 'floor_wood',
        note: 'Every windowsill is a planter now.',
        extra: [{ sprite: 'plant', dx: 3, dy: 1 }, { sprite: 'plant', dx: 6, dy: 1 },
                { sprite: 'plant', dx: 6, dy: 6 }, { sprite: 'bookshelf', dx: 7, dy: 5 }] }
};

/** The full furniture list for a home: shared anchors + their own things. */
export function layoutFor(home) {
  const style = HOME_STYLES[home.slot];
  const base = home.unit ? UNIT_BASE : HOUSE_BASE;
  if (!style) return home.unit ? UNIT_LAYOUT : HOME_LAYOUT;
  return [...base, ...(style.extra || [])];
}

/* ----------------------------------------------------------------------
   WHAT A PURCHASE ACTUALLY LOOKS LIKE

   Buying something at the General Store (sim_economy.py) has to show up in
   the world, or the whole economy is just a number going up in a panel.
   Each catalogue id maps to a real sprite and where it goes:

     'indoor'  -- furniture, placed in a genuinely free interior cell
     'yard'    -- drawn on the grass outside the front door
     'pet'     -- an animal, indoors where it lives (same free-cell search
                  as furniture, but drawn from an animal sheet's first frame)
     'car'     -- a parked car on the driveway

   Nothing is hardcoded to a cell: placement runs against the home's REAL
   occupied cells, so a bought bookshelf can never land on top of the bed,
   whichever home it is and whatever that resident already owns.
   ---------------------------------------------------------------------- */
export const OWNED_GOODS = {
  houseplant: { where: 'indoor', sprite: 'plant',     w: 1, h: 1 },
  rug:        { where: 'indoor', sprite: 'rug',       w: 4, h: 3 },
  bookshelf:  { where: 'indoor', sprite: 'bookshelf', w: 2, h: 1 },
  coffee:     { where: 'indoor', sprite: 'coffee',    w: 1, h: 1 },
  bigtv:      { where: 'indoor', sprite: 'tv',        w: 2, h: 1 },
  garden:     { where: 'yard',   sprite: 'flower_a',  w: 1, h: 1 },
  cat:        { where: 'pet',    sprite: 'char_pet_cat', w: 1, h: 1 },
  dog:        { where: 'pet',    sprite: 'char_pet_dog', w: 1, h: 1 },
  bicycle:    { where: 'yard',   sprite: 'bicycle',  w: 2, h: 1 },
  usedcar:    { where: 'car',    sprite: 'car_red',   w: 4, h: 2 },
  newcar:     { where: 'car',    sprite: 'car_blue',  w: 4, h: 2 },
  // bicycle and extension have no sprite of their own yet -- deliberately
  // absent rather than drawn as something they are not. They still show as
  // owned in the panel.
};

/** Cells a home's own furniture already occupies, in interior coords. */
function occupiedCells(home) {
  const off = home.unit ? 0 : 1;      // street layouts are rect-relative
  const taken = new Set();
  for (const f of layoutFor(home)) {
    const fp = { w: f.w || 1, h: f.h || 1 };
    for (let y = 0; y < fp.h; y++) {
      for (let x = 0; x < fp.w; x++) {
        taken.add(`${f.dx - off + x},${f.dy - off + y}`);
      }
    }
  }
  return taken;
}

/**
 * Where each of this resident's purchases actually gets drawn.
 * Returns absolute world-tile placements, so the renderer just draws them.
 */
export function ownedPlacements(home, ownedIds) {
  if (!home || !ownedIds || !ownedIds.length) return [];
  const taken = occupiedCells(home);
  const I = home.interior;
  const out = [];
  let yardN = 0, petN = 0;

  const fits = (dx, dy, w, h) => {
    if (dx < 0 || dy < 0 || dx + w > I.w || dy + h > I.h) return false;
    for (let y = 0; y < h; y++)
      for (let x = 0; x < w; x++)
        if (taken.has(`${dx + x},${dy + y}`)) return false;
    return true;
  };

  for (const id of ownedIds) {
    const g = OWNED_GOODS[id];
    if (!g) continue;

    if (g.where === 'indoor' || g.where === 'pet') {
      // Pets live inside, same as the furniture -- they get the same
      // free-cell search so a cat never ends up standing in the fridge.
      let placed = false;
      for (let dy = I.h - 1; dy >= 0 && !placed; dy--) {
        for (let dx = 0; dx < I.w && !placed; dx++) {
          if (!fits(dx, dy, g.w, g.h)) continue;
          for (let y = 0; y < g.h; y++)
            for (let x = 0; x < g.w; x++) taken.add(`${dx + x},${dy + y}`);
          out.push({ sprite: g.sprite, x: I.x + dx, y: I.y + dy,
                     frame: g.where === 'pet' });
          placed = true;
        }
      }
      // If nothing fits, it simply isn't drawn -- a full house is a real
      // outcome, and squeezing it in on top of the bed would be worse.

    } else if (g.where === 'yard') {
      // On the grass beside the front step: flowers for a garden, the
      // bicycle leaned up where its owner actually left it.
      const a = home.approach;
      const dir = a.y > home.rect.y ? 1 : -1;        // which side the door faces
      out.push({ sprite: g.sprite, x: a.x + 2 + yardN, y: a.y + dir });
      yardN += (g.w || 1);

    } else if (g.where === 'car' && home.driveway) {
      // Only for residents who don't already own a commute car -- the four
      // in Sunrise Meadows have real ones parked by world/commute.js, and
      // a second car on the same tile would just overlap it.
      if (!home.parkSpot) {
        out.push({ sprite: g.sprite, x: home.driveway.x - 1, y: home.driveway.y });
      }
    }
  }
  return out;
}

export const HOME_ACCENTS = [
  '#c46854', '#609ab0', '#b074a8', '#96ac5c', '#8c7abe', '#ceaa5c', '#6e96c8',
  '#5b8cff', '#39557a', '#c46a3c'
];

const STREET_HOMES = HOUSE_XS.map((x, i) => ({
  slot: i,
  unit: false,
  staff: null,
  accent: HOME_ACCENTS[i],
  rect:     { x, y: HOME_Y, w: HOME_W, h: HOME_H },
  interior: { x: x + 1, y: HOME_Y + 1, w: HOME_W - 2, h: HOME_H - 2 },
  doorway:  { x: x + 4, y: HOME_Y, w: 2, h: 1 },
  approach: { x: x + 4, y: HOME_Y - 1 },
  driveway: { x: x + 4, y: 53, w: 2, h: 1 }
}));

/** Six condo units: three north of the corridor, three south. Slots 4-9. */
const CONDO_HOMES = Array.from({ length: 6 }, (_, k) => {
  const slot = k + 4;
  const col = k % 3, north = k < 3;
  const ix = CONDO_X + 1 + col * (UNIT_W + 1);
  const iy = north ? CONDO_Y + 1 : CONDO_Y + 12;
  const doorY = north ? CONDO_Y + 7 : CONDO_Y + 11;
  return {
    slot,
    unit: true,
    staff: slot >= 7 ? ['eva', 'risk', 'mechanic'][slot - 7] : null,
    accent: HOME_ACCENTS[slot],
    interior: { x: ix, y: iy, w: UNIT_W, h: UNIT_H },
    rect:     { x: ix - 1, y: iy - 1, w: UNIT_W + 2, h: UNIT_H + 2 },
    doorway:  { x: ix + 3, y: doorY, w: 2, h: 1 },
    approach: { x: ix + 3, y: north ? doorY + 1 : doorY - 1 }
  };
});

/**
 * The Darkroom -- a three-unit terrace for the Archive Studio crew.
 *
 * Shared walls, three front doors, three driveways onto the same street the
 * other homes use. They live together and a short walk from the studio,
 * which is the point: the studio keeps the trading floor's hours, so the
 * three of them commute in and out on the same bell as everyone else.
 *
 * Built from the condo's unit geometry (7x6 interior) so it reuses
 * UNIT_LAYOUT and UNIT_SPOTS rather than inventing a third furniture set.
 */
const TERRACE_X = 62, TERRACE_Y = 54;
// Widened 2026-08-29 (28 -> 37) for the fact-checker's unit, and again
// 2026-08-31 (37 -> 46) for the crypto desk's -- shell() draws from these
// rect/interior values generically, so this is safe: nothing else hardcodes
// the terrace's width.
export const TERRACE = {
  name: 'The Darkroom',
  rect:     { x: TERRACE_X, y: TERRACE_Y, w: 46, h: 8 },
  interior: { x: TERRACE_X + 1, y: TERRACE_Y + 1, w: 44, h: 6 },
  accent:   '#8a6f9e'
};

// factchecker's slot is 23, not 10+3=13 -- 13 is already Sal's flat (see
// SAL_FLAT below). Every slot 10-22 is spoken for by an existing home; 23
// is the first genuinely free one (checked directly against every `slot:`
// in this file before picking it).
const STUDIO_SLOTS = [10, 11, 12, 23, 24];
const STUDIO_HOMES = ['archivist', 'writer', 'editor', 'factchecker', 'crypto'].map((who, k) => {
  const ix = TERRACE_X + 1 + k * 9;          // 63, 72, 81, 90, 99
  return {
    slot: STUDIO_SLOTS[k],
    unit: true,
    terrace: true,                            // drawn with the terrace, not the condo
    staff: who,
    accent: ['#b8705a', '#5f8fa6', '#9a7bb0', '#963f52', '#f29426'][k],
    interior: { x: ix, y: TERRACE_Y + 1, w: UNIT_W, h: UNIT_H },
    rect:     { x: ix - 1, y: TERRACE_Y, w: UNIT_W + 2, h: UNIT_H + 2 },
    doorway:  { x: ix + 3, y: TERRACE_Y, w: 2, h: 1 },   // north wall, onto the street
    approach: { x: ix + 3, y: TERRACE_Y - 1 },
    driveway: { x: ix + 3, y: 53, w: 2, h: 1 }
  };
});

/**
 * Sal's flat -- the one character who had nowhere to live.
 *
 * Sits directly north of The Corner Cup, door facing the shop, which is the
 * whole joke: she lives a few steps from the counter and hears everything
 * twice. Same 8x6 interior as the street houses so it reuses HOUSE_SPOTS.
 */
const SAL_X = 64, SAL_Y = 24;
const SAL_FLAT = {
  slot: 13,
  unit: false,
  staff: 'barista',
  accent: '#c98a4b',
  rect:     { x: SAL_X, y: SAL_Y, w: 10, h: 8 },
  interior: { x: SAL_X + 1, y: SAL_Y + 1, w: 8, h: 6 },
  doorway:  { x: SAL_X + 4, y: SAL_Y + 7, w: 2, h: 1 },   // south wall, toward the cafe
  approach: { x: SAL_X + 4, y: SAL_Y + 8 },
  driveway: { x: SAL_X + 4, y: SAL_Y + 8, w: 2, h: 1 }
};

/**
 * Wes's cottage -- the one place he lives, not just his desk at the ATM Co.
 * West side of the pond, in the same north stretch of the park as his own
 * workplace (roughly 20 tiles by the path, not next door -- comparable to
 * how the trading floor's own staff commute in from the condo block clear
 * across town). Genuinely clear ground, verified against nav.js's walkable
 * grid before placing, not eyeballed -- the same lesson as the ATM Co.
 * building and the streetlamp-in-the-road bugs. Same 10x8 footprint as the
 * street houses so it reuses HOME_LAYOUT/HOUSE_SPOTS without new code.
 */
const WES_X = 62, WES_Y = 9;
const WES_HOME = {
  slot: 14,
  unit: false,
  staff: 'atmops',
  accent: '#3f8a63',
  rect:     { x: WES_X, y: WES_Y, w: 10, h: 8 },
  interior: { x: WES_X + 1, y: WES_Y + 1, w: 8, h: 6 },
  doorway:  { x: WES_X + 4, y: WES_Y + 7, w: 2, h: 1 },   // south wall, onto the park
  approach: { x: WES_X + 4, y: WES_Y + 8 },
  driveway: { x: WES_X + 4, y: WES_Y + 8, w: 2, h: 1 }    // every other non-unit home has one
};

/**
 * Fay's flat -- where she goes off shift from the Prediction Desk (see that
 * room's own comment, far below). North side of town, genuinely clear
 * ground -- verified against nav.js's walkable grid and every other
 * building's rect before placing, same discipline as Wes's cottage above.
 * Same 10x8 footprint and south-facing door as Sal's flat and Wes's
 * cottage -- no new layout code needed.
 */
const FAY_X = 192, FAY_Y = 6;
const FAY_HOME = {
  slot: 25,
  unit: false,
  staff: 'predict',
  accent: '#6c4aa8',
  rect:     { x: FAY_X, y: FAY_Y, w: 10, h: 8 },
  interior: { x: FAY_X + 1, y: FAY_Y + 1, w: 8, h: 6 },
  doorway:  { x: FAY_X + 4, y: FAY_Y + 7, w: 2, h: 1 },
  approach: { x: FAY_X + 4, y: FAY_Y + 8 },
  driveway: { x: FAY_X + 4, y: FAY_Y + 8, w: 2, h: 1 }   // every other non-unit home has one
};

/**
 * Three ambient townsfolk's homes -- Milo, Nadia, Reed. No real subsystem
 * behind any of them, same as the doctors and Bull & Bear: added purely so
 * the city has people in it who aren't staff of a real room. Two sit in the
 * open block north of the hospital (verified clear the same way as every
 * other placement here); the third slots into the remaining strip next to
 * Fay's flat, north side of town. Same 10x8 footprint, south-facing door,
 * as every other standalone house -- no new layout code needed.
 */
const MILO_X = 186, MILO_Y = 34;
const MILO_HOME = {
  slot: 26, unit: false, staff: 'milo', accent: '#c45a4a',
  rect:     { x: MILO_X, y: MILO_Y, w: 10, h: 8 },
  interior: { x: MILO_X + 1, y: MILO_Y + 1, w: 8, h: 6 },
  doorway:  { x: MILO_X + 4, y: MILO_Y + 7, w: 2, h: 1 },
  approach: { x: MILO_X + 4, y: MILO_Y + 8 },
  driveway: { x: MILO_X + 4, y: MILO_Y + 8, w: 2, h: 1 }
};

const NADIA_X = 205, NADIA_Y = 34;
const NADIA_HOME = {
  slot: 27, unit: false, staff: 'nadia', accent: '#489696',
  rect:     { x: NADIA_X, y: NADIA_Y, w: 10, h: 8 },
  interior: { x: NADIA_X + 1, y: NADIA_Y + 1, w: 8, h: 6 },
  doorway:  { x: NADIA_X + 4, y: NADIA_Y + 7, w: 2, h: 1 },
  approach: { x: NADIA_X + 4, y: NADIA_Y + 8 },
  driveway: { x: NADIA_X + 4, y: NADIA_Y + 8, w: 2, h: 1 }
};

const REED_X = 202, REED_Y = 6;
const REED_HOME = {
  slot: 28, unit: false, staff: 'reed', accent: '#c4a438',
  rect:     { x: REED_X, y: REED_Y, w: 10, h: 8 },
  interior: { x: REED_X + 1, y: REED_Y + 1, w: 8, h: 6 },
  doorway:  { x: REED_X + 4, y: REED_Y + 7, w: 2, h: 1 },
  approach: { x: REED_X + 4, y: REED_Y + 8 },
  driveway: { x: REED_X + 4, y: REED_Y + 8, w: 2, h: 1 }
};

/**
 * The Outskirts -- a new row of four houses on a large (50x24), genuinely
 * empty block south of the hospital, verified clear the same way as every
 * other placement here. Two are occupied (Theo, Greta -- more ambient
 * filler, no real subsystem). The other two are deliberately left with no
 * `staff` -- vacant houses, reserved for whatever real project gets built
 * here next. Nothing about them needs to be decided now; they just need to
 * exist so there's somewhere to put it later. Same 10x8 footprint and
 * south-facing door as every other standalone house.
 */
const THEO_X = 142, THEO_Y = 56;
const THEO_HOME = {
  slot: 29, unit: false, staff: 'theo', accent: '#5c76a0',
  rect:     { x: THEO_X, y: THEO_Y, w: 10, h: 8 },
  interior: { x: THEO_X + 1, y: THEO_Y + 1, w: 8, h: 6 },
  doorway:  { x: THEO_X + 4, y: THEO_Y + 7, w: 2, h: 1 },
  approach: { x: THEO_X + 4, y: THEO_Y + 8 },
  driveway: { x: THEO_X + 4, y: THEO_Y + 8, w: 2, h: 1 }
};

const GRETA_X = 154, GRETA_Y = 56;
const GRETA_HOME = {
  slot: 30, unit: false, staff: 'greta', accent: '#648a84',
  rect:     { x: GRETA_X, y: GRETA_Y, w: 10, h: 8 },
  interior: { x: GRETA_X + 1, y: GRETA_Y + 1, w: 8, h: 6 },
  doorway:  { x: GRETA_X + 4, y: GRETA_Y + 7, w: 2, h: 1 },
  approach: { x: GRETA_X + 4, y: GRETA_Y + 8 },
  driveway: { x: GRETA_X + 4, y: GRETA_Y + 8, w: 2, h: 1 }
};

// Vacant -- reserved for a future real project. staff: null is an already-
// proven case (several condo units are vacant the same way); no roster
// entry points at these, so nobody lives here yet.
const FORSALE1_X = 166, FORSALE1_Y = 56;
const FORSALE1_HOME = {
  slot: 31, unit: false, staff: null, accent: '#9a9488', forSale: true,
  rect:     { x: FORSALE1_X, y: FORSALE1_Y, w: 10, h: 8 },
  interior: { x: FORSALE1_X + 1, y: FORSALE1_Y + 1, w: 8, h: 6 },
  doorway:  { x: FORSALE1_X + 4, y: FORSALE1_Y + 7, w: 2, h: 1 },
  approach: { x: FORSALE1_X + 4, y: FORSALE1_Y + 8 },
  driveway: { x: FORSALE1_X + 4, y: FORSALE1_Y + 8, w: 2, h: 1 }
};

const FORSALE2_X = 178, FORSALE2_Y = 56;
const FORSALE2_HOME = {
  slot: 32, unit: false, staff: null, accent: '#9a9488', forSale: true,
  rect:     { x: FORSALE2_X, y: FORSALE2_Y, w: 10, h: 8 },
  interior: { x: FORSALE2_X + 1, y: FORSALE2_Y + 1, w: 8, h: 6 },
  doorway:  { x: FORSALE2_X + 4, y: FORSALE2_Y + 7, w: 2, h: 1 },
  approach: { x: FORSALE2_X + 4, y: FORSALE2_Y + 8 },
  driveway: { x: FORSALE2_X + 4, y: FORSALE2_Y + 8, w: 2, h: 1 }
};

/**
 * Sunrise Meadows -- a small suburban development fronting the top-right
 * street (TOP_ST), far northeast, well clear of downtown and the hospital.
 * This is where staff who don't need to be downtown live: the two doctors
 * (who drive the distance, see world/commute.js) plus Otis and Margo,
 * pulled out of their old Smallville Condos units into real houses of
 * their own -- same 10x8 footprint as every other standalone house, just
 * further out. Same street-facing, north-door, straight-driveway
 * construction as the original four, so no new layout code either way --
 * just fronting TOP_ST instead of the main road, with a one-tile driveway
 * gap between the street and the houses, same as everywhere else.
 * Sits east of the north-south avenue, leaving the rest of TOP_ST (and the
 * avenue itself) genuinely open for whatever the next district needs.
 */
const SUBURB_X = [210, 223, 236, 249];
const SUBURB_Y = TOP_ST.y + TOP_ST.h + 1;   // one tile south of the street, for the driveway
const SUBURB_STAFF = ['doctor1', 'doctor2', 'mechanic', 'risk'];
const SUBURB_ACCENTS = ['#5a8fae', '#a8756a', '#9a8a5c', '#7c6a94'];
const SUBURB_HOMES = SUBURB_X.map((x, i) => ({
  slot: 15 + i,
  unit: false,
  staff: SUBURB_STAFF[i],
  accent: SUBURB_ACCENTS[i],
  rect:     { x, y: SUBURB_Y, w: 10, h: 8 },
  interior: { x: x + 1, y: SUBURB_Y + 1, w: 8, h: 6 },
  doorway:  { x: x + 4, y: SUBURB_Y, w: 2, h: 1 },          // north wall, toward TOP_ST
  approach: { x: x + 4, y: SUBURB_Y - 1 },
  driveway: { x: x + 4, y: SUBURB_Y - 1, w: 2, h: 1 },      // straight up to TOP_ST
  // Where the car actually sits once they're home for the night -- on the
  // street's own north shoulder, clear of the driving lane (TOP_ST_LANE,
  // see world/commute.js), a couple of tiles off from the driveway itself
  // so it reads as parked on the side, not blocking their own door.
  parkSpot: { x: x + 2, y: TOP_ST.y, w: 4, h: 2 }
}));

/**
 * Bull & Bear's own houses -- slots 19-20. Same freestanding 10x8 footprint
 * as the street houses, placed just south of NEWS_STUDIO (see below) rather
 * than out on the original street, so the two of them live a short walk
 * from their own desk the same way the Archive Studio crew lives a short
 * walk from theirs (The Darkroom). Doors face north, toward the studio.
 * Genuinely clear ground -- checked against every rect above before
 * placing, same discipline as the ATM Co. and Wes's cottage.
 */
const BULL_HOME = {
  slot: 19,
  unit: false,
  staff: 'bull',
  accent: '#e8c15a',
  rect:     { x: 158, y: 30, w: 10, h: 8 },
  interior: { x: 159, y: 31, w: 8, h: 6 },
  doorway:  { x: 162, y: 30, w: 2, h: 1 },      // north wall, toward the studio
  approach: { x: 162, y: 29 },
  driveway: { x: 162, y: 29, w: 2, h: 1 }        // every other non-unit home has one
};
const BEAR_HOME = {
  slot: 20,
  unit: false,
  staff: 'bear',
  accent: '#5a8fe0',
  rect:     { x: 174, y: 30, w: 10, h: 8 },
  interior: { x: 175, y: 31, w: 8, h: 6 },
  doorway:  { x: 178, y: 30, w: 2, h: 1 },      // north wall, toward the studio
  approach: { x: 178, y: 29 },
  driveway: { x: 178, y: 29, w: 2, h: 1 }
};

/**
 * Marnie's house -- slot 21. Same freestanding footprint, placed a few
 * tiles east of the Bank in the same south strip as the Field Office.
 * Door faces north -- genuinely clear ground up to the street homes' row
 * (which ends at x55; this sits at x56 onward).
 */
const MARNIE_HOME = {
  slot: 21,
  unit: false,
  staff: 'marnie',
  accent: '#c9a227',
  rect:     { x: 56, y: 63, w: 10, h: 8 },
  interior: { x: 57, y: 64, w: 8, h: 6 },
  doorway:  { x: 60, y: 63, w: 2, h: 1 },
  approach: { x: 60, y: 62 },
  driveway: { x: 60, y: 62, w: 2, h: 1 }
};

/**
 * Percy's house -- slot 22. Same freestanding footprint, next open ground
 * east of Marnie's house (which ends x65), same south strip.
 */
const PERCY_HOME = {
  slot: 22,
  unit: false,
  staff: 'percy',
  accent: '#5c6b47',
  rect:     { x: 86, y: 63, w: 10, h: 8 },
  interior: { x: 87, y: 64, w: 8, h: 6 },
  doorway:  { x: 90, y: 63, w: 2, h: 1 },
  approach: { x: 90, y: 62 },
  driveway: { x: 90, y: 62, w: 2, h: 1 }
};

/**
 * The General Store -- the town's one shop, and where its make-believe
 * economy actually happens: residents draw a monthly stipend and save
 * toward home upgrades, pets and cars (see sim_economy.py, and note its
 * header -- Smallville dollars are fiction with no connection to any real
 * money).
 *
 * Right in the middle of town on purpose: the strip between the lake shore
 * and The Corner Cup's north wall, which is the one patch of ground almost
 * every character already walks past off-duty (the cafe and the lake are
 * the two venues the ambient wander actually sends them to). Its door opens
 * south, four tiles from the cafe's own roofline, so "walk to the shop" is
 * a genuinely short walk from anywhere downtown rather than a trek.
 *
 * Verified clear of every building, road, pavement, tree and the pond
 * before placing; the one thing that was in the way -- a park bench at
 * (79,25) -- moved west along the shore rather than being deleted.
 */
const STORE_X = 74, STORE_Y = 25;
export const STORE = {
  // Not "Smallville General <anything>" -- the hospital is already
  // "Smallville General", and the two signs sit close enough together on
  // screen to be read as the same place.
  name: 'The General Store',
  rect:     { x: STORE_X, y: STORE_Y, w: 11, h: 6 },
  interior: { x: STORE_X + 1, y: STORE_Y + 1, w: 9, h: 4 },
  doorway:  { x: STORE_X + 4, y: STORE_Y + 5, w: 2, h: 1 },   // south wall, toward the cafe
  approach: { x: STORE_X + 4, y: STORE_Y + 6 },
  accent:   '#b8863c',
  // Interior is 9x4 (dx0-8, dy0-3). The doorway sits at dx3-4, so that
  // column stays clear front to back -- same walk-in rule every other
  // building here follows.
  layout: [
    // back wall: the price board and the stock shelves
    { sprite: 'menu',       dx: 0, dy: 0, w: 3, h: 1 },
    { sprite: 'bookshelf',  dx: 5, dy: 0, w: 2, h: 1 },
    { sprite: 'bookshelf',  dx: 7, dy: 0, w: 2, h: 1 },
    // dy1 kept clear -- the lane the shopkeeper works in
    { sprite: 'counter',    dx: 5, dy: 2, w: 4, h: 1 },
    { sprite: 'counter',    dx: 5, dy: 2, w: 4, h: 1 },
    // the floor: crated stock down the left, browsable
    { sprite: 'crate',      dx: 0, dy: 2, w: 1, h: 1 },
    { sprite: 'crate',      dx: 1, dy: 2, w: 1, h: 1 },
    { sprite: 'crate',      dx: 0, dy: 3, w: 1, h: 1 },
    { sprite: 'plant',      dx: 8, dy: 3, w: 1, h: 1 }
  ]
};

export const STORE_ROOM = {
  id: 'store',
  name: STORE.name,
  rect: STORE.rect,
  blurb: "The town's one shop. Where everyone spends their make-believe pay.",
  data: ['/api/sim']
};

export const SUBURB = {
  name: 'Sunrise Meadows',
  accent: '#8ba888',
  // A sign spanning the development's own stretch of TOP_ST. Reuses the
  // same rect-cornered sign convention as every standalone building.
  rect: {
    x: SUBURB_X[0] - 2, y: SUBURB_Y - 5,
    w: (SUBURB_X[SUBURB_X.length - 1] + 10) - (SUBURB_X[0] - 2), h: 4
  }
};


/**
 * The Eastside -- redesigned as cul-de-sacs, not a grid. Seven courts
 * branch off a bent collector road (itself connected back to the main
 * street via a north-south link), each court ringed by houses facing
 * INWARD -- doors on whichever wall actually faces the court, not always
 * south. Same 40 residents as before (see roster.js/people.js), just
 * relocated; their names/sprites/ids are unchanged, only slot-to-
 * position mapping moved. Verified clear against every existing rect,
 * street and the Eastside Freeway before placing.
 */
const EASTSIDE_HOMES = [
  { slot: 33, unit: false, staff: 'oscar', accent: '#a07858', rect: { x: 270, y: 78, w: 10, h: 8 }, interior: { x: 271, y: 79, w: 8, h: 6 }, doorway: { x: 274, y: 85, w: 2, h: 1 }, approach: { x: 274, y: 86 }, driveway: { x: 274, y: 86, w: 1, h: 1 } },
  { slot: 34, unit: false, staff: 'lena', accent: '#5888a8', rect: { x: 280, y: 78, w: 10, h: 8 }, interior: { x: 281, y: 79, w: 8, h: 6 }, doorway: { x: 284, y: 85, w: 2, h: 1 }, approach: { x: 284, y: 86 }, driveway: { x: 284, y: 86, w: 1, h: 1 } },
  { slot: 35, unit: false, staff: 'hugo', accent: '#a8a858', rect: { x: 260, y: 86, w: 10, h: 8 }, interior: { x: 261, y: 87, w: 8, h: 6 }, doorway: { x: 269, y: 89, w: 1, h: 2 }, approach: { x: 270, y: 89 }, driveway: { x: 270, y: 89, w: 1, h: 1 } },
  { slot: 36, unit: false, staff: 'mira', accent: '#8858a0', rect: { x: 260, y: 94, w: 10, h: 8 }, interior: { x: 261, y: 95, w: 8, h: 6 }, doorway: { x: 269, y: 97, w: 1, h: 2 }, approach: { x: 270, y: 97 }, driveway: { x: 270, y: 97, w: 1, h: 1 } },
  { slot: 37, unit: false, staff: 'dex', accent: '#58a088', rect: { x: 290, y: 86, w: 10, h: 8 }, interior: { x: 291, y: 87, w: 8, h: 6 }, doorway: { x: 290, y: 89, w: 1, h: 2 }, approach: { x: 289, y: 89 }, driveway: { x: 289, y: 89, w: 1, h: 1 } },
  { slot: 38, unit: false, staff: 'paloma', accent: '#a87858', rect: { x: 290, y: 94, w: 10, h: 8 }, interior: { x: 291, y: 95, w: 8, h: 6 }, doorway: { x: 290, y: 97, w: 1, h: 2 }, approach: { x: 289, y: 97 }, driveway: { x: 289, y: 97, w: 1, h: 1 } },
  { slot: 39, unit: false, staff: 'arlo', accent: '#7878b8', rect: { x: 310, y: 140, w: 10, h: 8 }, interior: { x: 311, y: 141, w: 8, h: 6 }, doorway: { x: 314, y: 140, w: 2, h: 1 }, approach: { x: 314, y: 139 }, driveway: { x: 314, y: 139, w: 1, h: 1 } },
  { slot: 40, unit: false, staff: 'sable', accent: '#b85868', rect: { x: 320, y: 140, w: 10, h: 8 }, interior: { x: 321, y: 141, w: 8, h: 6 }, doorway: { x: 324, y: 140, w: 2, h: 1 }, approach: { x: 324, y: 139 }, driveway: { x: 324, y: 139, w: 1, h: 1 } },
  { slot: 41, unit: false, staff: 'finn', accent: '#6ea868', rect: { x: 300, y: 124, w: 10, h: 8 }, interior: { x: 301, y: 125, w: 8, h: 6 }, doorway: { x: 309, y: 127, w: 1, h: 2 }, approach: { x: 310, y: 127 }, driveway: { x: 310, y: 127, w: 1, h: 1 } },
  { slot: 42, unit: false, staff: 'juno', accent: '#989898', rect: { x: 300, y: 132, w: 10, h: 8 }, interior: { x: 301, y: 133, w: 8, h: 6 }, doorway: { x: 309, y: 135, w: 1, h: 2 }, approach: { x: 310, y: 135 }, driveway: { x: 310, y: 135, w: 1, h: 1 } },
  { slot: 43, unit: false, staff: 'rhea', accent: '#a07858', rect: { x: 330, y: 124, w: 10, h: 8 }, interior: { x: 331, y: 125, w: 8, h: 6 }, doorway: { x: 330, y: 127, w: 1, h: 2 }, approach: { x: 329, y: 127 }, driveway: { x: 329, y: 127, w: 1, h: 1 } },
  { slot: 44, unit: false, staff: 'soren', accent: '#5888a8', rect: { x: 330, y: 132, w: 10, h: 8 }, interior: { x: 331, y: 133, w: 8, h: 6 }, doorway: { x: 330, y: 135, w: 1, h: 2 }, approach: { x: 329, y: 135 }, driveway: { x: 329, y: 135, w: 1, h: 1 } },
  { slot: 45, unit: false, staff: 'ivy', accent: '#a8a858', rect: { x: 350, y: 78, w: 10, h: 8 }, interior: { x: 351, y: 79, w: 8, h: 6 }, doorway: { x: 354, y: 85, w: 2, h: 1 }, approach: { x: 354, y: 86 }, driveway: { x: 354, y: 86, w: 1, h: 1 } },
  { slot: 46, unit: false, staff: 'mateo', accent: '#8858a0', rect: { x: 360, y: 78, w: 10, h: 8 }, interior: { x: 361, y: 79, w: 8, h: 6 }, doorway: { x: 364, y: 85, w: 2, h: 1 }, approach: { x: 364, y: 86 }, driveway: { x: 364, y: 86, w: 1, h: 1 } },
  { slot: 47, unit: false, staff: 'celia', accent: '#58a088', rect: { x: 340, y: 86, w: 10, h: 8 }, interior: { x: 341, y: 87, w: 8, h: 6 }, doorway: { x: 349, y: 89, w: 1, h: 2 }, approach: { x: 350, y: 89 }, driveway: { x: 350, y: 89, w: 1, h: 1 } },
  { slot: 48, unit: false, staff: 'dash', accent: '#a87858', rect: { x: 340, y: 94, w: 10, h: 8 }, interior: { x: 341, y: 95, w: 8, h: 6 }, doorway: { x: 349, y: 97, w: 1, h: 2 }, approach: { x: 350, y: 97 }, driveway: { x: 350, y: 97, w: 1, h: 1 } },
  { slot: 49, unit: false, staff: 'wylie', accent: '#7878b8', rect: { x: 370, y: 86, w: 10, h: 8 }, interior: { x: 371, y: 87, w: 8, h: 6 }, doorway: { x: 370, y: 89, w: 1, h: 2 }, approach: { x: 369, y: 89 }, driveway: { x: 369, y: 89, w: 1, h: 1 } },
  { slot: 50, unit: false, staff: 'noor', accent: '#b85868', rect: { x: 370, y: 94, w: 10, h: 8 }, interior: { x: 371, y: 95, w: 8, h: 6 }, doorway: { x: 370, y: 97, w: 1, h: 2 }, approach: { x: 369, y: 97 }, driveway: { x: 369, y: 97, w: 1, h: 1 } },
  { slot: 51, unit: false, staff: 'bram', accent: '#6ea868', rect: { x: 390, y: 140, w: 10, h: 8 }, interior: { x: 391, y: 141, w: 8, h: 6 }, doorway: { x: 394, y: 140, w: 2, h: 1 }, approach: { x: 394, y: 139 }, driveway: { x: 394, y: 139, w: 1, h: 1 } },
  { slot: 52, unit: false, staff: 'tamsin', accent: '#989898', rect: { x: 400, y: 140, w: 10, h: 8 }, interior: { x: 401, y: 141, w: 8, h: 6 }, doorway: { x: 404, y: 140, w: 2, h: 1 }, approach: { x: 404, y: 139 }, driveway: { x: 404, y: 139, w: 1, h: 1 } },
  { slot: 53, unit: false, staff: 'zane', accent: '#a07858', rect: { x: 380, y: 124, w: 10, h: 8 }, interior: { x: 381, y: 125, w: 8, h: 6 }, doorway: { x: 389, y: 127, w: 1, h: 2 }, approach: { x: 390, y: 127 }, driveway: { x: 390, y: 127, w: 1, h: 1 } },
  { slot: 54, unit: false, staff: 'odette', accent: '#5888a8', rect: { x: 380, y: 132, w: 10, h: 8 }, interior: { x: 381, y: 133, w: 8, h: 6 }, doorway: { x: 389, y: 135, w: 1, h: 2 }, approach: { x: 390, y: 135 }, driveway: { x: 390, y: 135, w: 1, h: 1 } },
  { slot: 55, unit: false, staff: 'cole', accent: '#a8a858', rect: { x: 410, y: 124, w: 10, h: 8 }, interior: { x: 411, y: 125, w: 8, h: 6 }, doorway: { x: 410, y: 127, w: 1, h: 2 }, approach: { x: 409, y: 127 }, driveway: { x: 409, y: 127, w: 1, h: 1 } },
  { slot: 56, unit: false, staff: 'freya', accent: '#8858a0', rect: { x: 410, y: 132, w: 10, h: 8 }, interior: { x: 411, y: 133, w: 8, h: 6 }, doorway: { x: 410, y: 135, w: 1, h: 2 }, approach: { x: 409, y: 135 }, driveway: { x: 409, y: 135, w: 1, h: 1 } },
  { slot: 57, unit: false, staff: 'enzo', accent: '#58a088', rect: { x: 430, y: 78, w: 10, h: 8 }, interior: { x: 431, y: 79, w: 8, h: 6 }, doorway: { x: 434, y: 85, w: 2, h: 1 }, approach: { x: 434, y: 86 }, driveway: { x: 434, y: 86, w: 1, h: 1 } },
  { slot: 58, unit: false, staff: 'marisol', accent: '#a87858', rect: { x: 440, y: 78, w: 10, h: 8 }, interior: { x: 441, y: 79, w: 8, h: 6 }, doorway: { x: 444, y: 85, w: 2, h: 1 }, approach: { x: 444, y: 86 }, driveway: { x: 444, y: 86, w: 1, h: 1 } },
  { slot: 59, unit: false, staff: 'kai', accent: '#7878b8', rect: { x: 420, y: 86, w: 10, h: 8 }, interior: { x: 421, y: 87, w: 8, h: 6 }, doorway: { x: 429, y: 89, w: 1, h: 2 }, approach: { x: 430, y: 89 }, driveway: { x: 430, y: 89, w: 1, h: 1 } },
  { slot: 60, unit: false, staff: 'thalia', accent: '#b85868', rect: { x: 420, y: 94, w: 10, h: 8 }, interior: { x: 421, y: 95, w: 8, h: 6 }, doorway: { x: 429, y: 97, w: 1, h: 2 }, approach: { x: 430, y: 97 }, driveway: { x: 430, y: 97, w: 1, h: 1 } },
  { slot: 61, unit: false, staff: 'dmitri', accent: '#6ea868', rect: { x: 450, y: 86, w: 10, h: 8 }, interior: { x: 451, y: 87, w: 8, h: 6 }, doorway: { x: 450, y: 89, w: 1, h: 2 }, approach: { x: 449, y: 89 }, driveway: { x: 449, y: 89, w: 1, h: 1 } },
  { slot: 62, unit: false, staff: 'elsie', accent: '#989898', rect: { x: 450, y: 94, w: 10, h: 8 }, interior: { x: 451, y: 95, w: 8, h: 6 }, doorway: { x: 450, y: 97, w: 1, h: 2 }, approach: { x: 449, y: 97 }, driveway: { x: 449, y: 97, w: 1, h: 1 } },
  { slot: 63, unit: false, staff: 'rowan', accent: '#a07858', rect: { x: 290, y: 140, w: 10, h: 8 }, interior: { x: 291, y: 141, w: 8, h: 6 }, doorway: { x: 294, y: 140, w: 2, h: 1 }, approach: { x: 294, y: 139 }, driveway: { x: 294, y: 139, w: 1, h: 1 } },
  { slot: 64, unit: false, staff: 'vesna', accent: '#5888a8', rect: { x: 300, y: 140, w: 10, h: 8 }, interior: { x: 301, y: 141, w: 8, h: 6 }, doorway: { x: 304, y: 140, w: 2, h: 1 }, approach: { x: 304, y: 139 }, driveway: { x: 304, y: 139, w: 1, h: 1 } },
  { slot: 65, unit: false, staff: 'lior', accent: '#a8a858', rect: { x: 280, y: 124, w: 10, h: 8 }, interior: { x: 281, y: 125, w: 8, h: 6 }, doorway: { x: 289, y: 127, w: 1, h: 2 }, approach: { x: 290, y: 127 }, driveway: { x: 290, y: 127, w: 1, h: 1 } },
  { slot: 66, unit: false, staff: 'bianca', accent: '#8858a0', rect: { x: 280, y: 132, w: 10, h: 8 }, interior: { x: 281, y: 133, w: 8, h: 6 }, doorway: { x: 289, y: 135, w: 1, h: 2 }, approach: { x: 290, y: 135 }, driveway: { x: 290, y: 135, w: 1, h: 1 } },
  { slot: 67, unit: false, staff: 'caspian', accent: '#58a088', rect: { x: 310, y: 124, w: 10, h: 8 }, interior: { x: 311, y: 125, w: 8, h: 6 }, doorway: { x: 310, y: 127, w: 1, h: 2 }, approach: { x: 309, y: 127 }, driveway: { x: 309, y: 127, w: 1, h: 1 } },
  { slot: 68, unit: false, staff: 'ingrid', accent: '#a87858', rect: { x: 370, y: 78, w: 10, h: 8 }, interior: { x: 371, y: 79, w: 8, h: 6 }, doorway: { x: 374, y: 85, w: 2, h: 1 }, approach: { x: 374, y: 86 }, driveway: { x: 374, y: 86, w: 1, h: 1 } },
  { slot: 69, unit: false, staff: 'mo', accent: '#7878b8', rect: { x: 380, y: 78, w: 10, h: 8 }, interior: { x: 381, y: 79, w: 8, h: 6 }, doorway: { x: 384, y: 85, w: 2, h: 1 }, approach: { x: 384, y: 86 }, driveway: { x: 384, y: 86, w: 1, h: 1 } },
  { slot: 70, unit: false, staff: 'sunny', accent: '#b85868', rect: { x: 360, y: 86, w: 10, h: 8 }, interior: { x: 361, y: 87, w: 8, h: 6 }, doorway: { x: 369, y: 89, w: 1, h: 2 }, approach: { x: 370, y: 89 }, driveway: { x: 370, y: 89, w: 1, h: 1 } },
  { slot: 71, unit: false, staff: 'petra', accent: '#6ea868', rect: { x: 360, y: 94, w: 10, h: 8 }, interior: { x: 361, y: 95, w: 8, h: 6 }, doorway: { x: 369, y: 97, w: 1, h: 2 }, approach: { x: 370, y: 97 }, driveway: { x: 370, y: 97, w: 1, h: 1 } },
  { slot: 72, unit: false, staff: 'dario', accent: '#989898', rect: { x: 390, y: 86, w: 10, h: 8 }, interior: { x: 391, y: 87, w: 8, h: 6 }, doorway: { x: 390, y: 89, w: 1, h: 2 }, approach: { x: 389, y: 89 }, driveway: { x: 389, y: 89, w: 1, h: 1 } },
];

const DANA_X = 600, DANA_Y = 90;
const DANA_HOME = {
  slot: 73, unit: false, staff: 'dana', accent: '#2a3a5c',
  rect:     { x: DANA_X, y: DANA_Y, w: 10, h: 8 },
  interior: { x: DANA_X + 1, y: DANA_Y + 1, w: 8, h: 6 },
  doorway:  { x: DANA_X + 4, y: DANA_Y + 7, w: 2, h: 1 },
  approach: { x: DANA_X + 4, y: DANA_Y + 8 },
  driveway: { x: DANA_X + 4, y: DANA_Y + 8, w: 2, h: 1 }
};

export const HOMES = [...STREET_HOMES, ...CONDO_HOMES, ...STUDIO_HOMES, SAL_FLAT, WES_HOME, ...SUBURB_HOMES, BULL_HOME, BEAR_HOME, MARNIE_HOME, PERCY_HOME, FAY_HOME, MILO_HOME, NADIA_HOME, REED_HOME, THEO_HOME, GRETA_HOME, FORSALE1_HOME, FORSALE2_HOME, ...EASTSIDE_HOMES, DANA_HOME];

/** Absolute tile of a home spot. */
export function homeSpot(slot, idx) {
  const h = HOMES.find(v => v.slot === slot);
  if (!h) return null;
  const table = h.unit ? UNIT_SPOTS : HOUSE_SPOTS;
  const s = table[idx % table.length];
  return { x: h.interior.x + s.dx, y: h.interior.y + s.dy, what: s.what };
}

/**
 * The coffee shop, between the HQ and the park. Off the clock, people
 * sometimes come here instead of going straight home -- and because they end
 * up standing near each other, this is where most of the banter happens.
 */
export const CAFE = {
  name: 'The Corner Cup',
  // The HQ occupies x3..60 inclusive, so the cafe starts at 64 -- three
  // clear tiles of pavement between the two buildings. It previously began
  // at x60 and overlapped the HQ's east wall.
  rect:     { x: 64, y: 32, w: 22, h: 15 },
  interior: { x: 65, y: 33, w: 20, h: 13 },
  doorway:  { x: 73, y: 46, w: 3, h: 1 },
  accent:   '#c07a4a',
  /** Sal stands in the lane between the back wall and the counter. */
  baristaSpot: { x: 69, y: 34 },
  layout: [
    // back wall: menus, machine, and the complaint board
    { sprite: 'menu',       dx: 1,  dy: 0,  w: 3, h: 1 },
    { sprite: 'menu',       dx: 5,  dy: 0,  w: 3, h: 1 },
    { sprite: 'espresso',   dx: 9,  dy: 0,  w: 2, h: 1 },
    { sprite: 'bulletin',   dx: 17, dy: 0,  w: 3, h: 2 },
    // dy1 is deliberately clear -- that is the lane Sal works in
    // the counter, with the food along the far end
    { sprite: 'cafe_bar',   dx: 1,  dy: 2,  w: 6, h: 1 },
    { sprite: 'cafe_bar',   dx: 7,  dy: 2,  w: 6, h: 1 },
    { sprite: 'pastry',     dx: 13, dy: 2,  w: 2, h: 1 },
    { sprite: 'pastry',     dx: 15, dy: 2,  w: 2, h: 1 },
    { sprite: 'coffee',     dx: 17, dy: 2,  w: 1, h: 1 },
    // stools on the customer side of the counter
    { sprite: 'stool',      dx: 2,  dy: 4,  w: 1, h: 1 },
    { sprite: 'stool',      dx: 5,  dy: 4,  w: 1, h: 1 },
    { sprite: 'stool',      dx: 8,  dy: 4,  w: 1, h: 1 },
    { sprite: 'stool',      dx: 11, dy: 4,  w: 1, h: 1 },
    // seating floor
    { sprite: 'cafe_table', dx: 1,  dy: 6,  w: 2, h: 2 },
    { sprite: 'stool',      dx: 3,  dy: 7,  w: 1, h: 1 },
    { sprite: 'cafe_table', dx: 5,  dy: 6,  w: 2, h: 2 },
    { sprite: 'stool',      dx: 7,  dy: 7,  w: 1, h: 1 },
    { sprite: 'cafe_table', dx: 10, dy: 6,  w: 2, h: 2 },
    { sprite: 'stool',      dx: 12, dy: 7,  w: 1, h: 1 },
    { sprite: 'cafe_table', dx: 1,  dy: 10, w: 2, h: 2 },
    { sprite: 'stool',      dx: 3,  dy: 11, w: 1, h: 1 },
    { sprite: 'cafe_table', dx: 5,  dy: 10, w: 2, h: 2 },
    { sprite: 'stool',      dx: 7,  dy: 11, w: 1, h: 1 },
    // soft corner by the board
    { sprite: 'couch',      dx: 15, dy: 6,  w: 4, h: 2, soft: true },
    { sprite: 'couch',      dx: 15, dy: 10, w: 4, h: 2, soft: true },
    { sprite: 'cafe_table', dx: 16, dy: 8,  w: 2, h: 2 },
    { sprite: 'plant',      dx: 0,  dy: 12, w: 1, h: 1 },
    { sprite: 'plant',      dx: 19, dy: 12, w: 1, h: 1 }
  ],
  /** Every spot must be a clear interior tile (dx 0..19, dy 0..12). */
  spots: [
    { dx: 16, dy: 6,  what: 'on the caf\u00e9 couch' },
    { dx: 17, dy: 10, what: 'putting the world right' },
    { dx: 2,  dy: 8,  what: 'at a table' },
    { dx: 11, dy: 8,  what: 'by the window' },
    { dx: 4,  dy: 4,  what: 'ordering a coffee' },
    { dx: 6,  dy: 12, what: 'catching up' },
    { dx: 17, dy: 4,  what: 'reading the board' },
    { dx: 2,  dy: 12, what: 'putting off going home' }
  ]
};

/**
 * The hospital. Only ever used after hours: if the speeding car actually
 * connects with somebody, an ambulance runs out of here, collects them,
 * brings them back, and then drops them home once they are patched up.
 */
export const HOSPITAL = {
  name: 'Smallville General',
  rect:     { x: 118, y: 32, w: 22, h: 15 },
  interior: { x: 119, y: 33, w: 20, h: 13 },
  doorway:  { x: 127, y: 46, w: 3, h: 1 },
  accent:   '#c8443c',
  /** Where the ambulance sits when it is off duty. */
  bay: { x: 128, y: 47 },
  /** Bed the patient occupies while being treated. */
  ward: { x: 122, y: 37 },
  layout: [
    { sprite: 'counter',     dx: 1,  dy: 1,  w: 4, h: 1 },
    { sprite: 'desk_small',  dx: 6,  dy: 1,  w: 2, h: 2 },
    { sprite: 'chair',       dx: 6,  dy: 3,  w: 1, h: 1 },
    { sprite: 'bulletin',    dx: 16, dy: 0,  w: 3, h: 2 },
    { sprite: 'bed',         dx: 2,  dy: 4,  w: 2, h: 3, soft: true },
    { sprite: 'bed',         dx: 6,  dy: 4,  w: 2, h: 3, soft: true },
    { sprite: 'bed',         dx: 10, dy: 4,  w: 2, h: 3, soft: true },
    { sprite: 'bed',         dx: 14, dy: 4,  w: 2, h: 3, soft: true },
    { sprite: 'plant',       dx: 18, dy: 4,  w: 1, h: 1 },
    { sprite: 'cafe_table',  dx: 2,  dy: 9,  w: 2, h: 2 },
    { sprite: 'chair',       dx: 4,  dy: 10, w: 1, h: 1 },
    { sprite: 'couch',       dx: 14, dy: 9,  w: 4, h: 2, soft: true },
    { sprite: 'plant',       dx: 0,  dy: 12, w: 1, h: 1 },
    { sprite: 'plant',       dx: 19, dy: 12, w: 1, h: 1 }
  ]
};

/** A spot on the lake shore. */
export function lakeSpot(idx) {
  const s = PARK.lakeSpots[idx % PARK.lakeSpots.length];
  return { x: s.x, y: s.y, what: s.what };
}

export function cafeSpot(idx) {
  const s = CAFE.spots[idx % CAFE.spots.length];
  return { x: CAFE.interior.x + s.dx, y: CAFE.interior.y + s.dy, what: s.what };
}

/** Park furniture, east of the HQ. */
/**
 * The Archive Studio -- production house for the Bedtime Archive channel
 * (LGBTQ history documentary). Its stations map one-to-one onto the REAL
 * pipeline stages reported by /api/studio, which reads the actual files in
 * ~/Desktop/YouTube the and ~/Desktop/youtub. Nothing here is decorative
 * filler: each station has a stage behind it.
 */
export const STUDIO = {
  name: 'The Archive Studio',
  channel: 'Bedtime Archive',
  rect:     { x: 112, y: 6, w: 26, h: 18 },
  interior: { x: 113, y: 7, w: 24, h: 16 },
  doorway:  { x: 123, y: 23, w: 3, h: 1 },
  accent:   '#a8577f',
  /** Click targets, keyed to the stage ids in studio.py. */
  stations: [
    { id: 'research',  name: 'Research Wall', at: { x: 115, y: 9 },
      blurb: 'Idea backlog · photo sourcing' },
    // The writers' room's second seat -- see the layout comment below,
    // this desk existed empty since the room was first built. 2026-08-29:
    // fact-checking became its own real, independently-gated stage
    // (studio.py's STAGES) instead of silently counting as part of
    // "research," so this desk finally has a real job to point at.
    { id: 'factcheck', name: 'Fact-Check Desk', at: { x: 119, y: 12 },
      blurb: 'Verifies every claim in the script against real sources' },
    { id: 'script',    name: "Writers' Desk",  at: { x: 122, y: 12 },
      blurb: 'Outlines and scripts' },
    { id: 'video',     name: 'Edit Bay',       at: { x: 129, y: 12 },
      blurb: 'Shot list · composition · final cut · images matched to narration timing' },
    { id: 'audio',     name: 'Booth',          at: { x: 134, y: 12 },
      blurb: 'Narration renders' },
    { id: 'publish',   name: 'Packaging Desk', at: { x: 118, y: 19 },
      blurb: 'Titles · thumbnails · publish checklist' }
  ],
  layout: [
    // back wall: the idea wall, the board, and the reference screens
    { sprite: 'bulletin',       dx: 1,  dy: 0 },
    { sprite: 'whiteboard',     dx: 6,  dy: 0 },
    { sprite: 'wallscreen',     dx: 12, dy: 0 },
    { sprite: 'wallscreen',     dx: 17, dy: 0 },
    { sprite: 'bookshelf',      dx: 21, dy: 0 },
    // research desk
    { sprite: 'desk',           dx: 1,  dy: 4 },
    { sprite: 'chair',          dx: 2,  dy: 6 },
    { sprite: 'filing_cabinet', dx: 5,  dy: 4 },
    // writers' room -- two seats, because scripts get a fact-check pass.
    // The first (dx8) was empty from when this room was built until
    // 2026-08-29, when factcheck became its own real staffed stage.
    { sprite: 'desk_small',     dx: 8,  dy: 4 },
    { sprite: 'chair',          dx: 8,  dy: 6 },
    { sprite: 'desk_small',     dx: 11, dy: 4 },
    { sprite: 'chair',          dx: 11, dy: 6 },
    // edit bay
    { sprite: 'desk',           dx: 15, dy: 4 },
    { sprite: 'chair',          dx: 16, dy: 6 },
    { sprite: 'tv',             dx: 19, dy: 4 },
    // audio booth
    { sprite: 'workbench',      dx: 21, dy: 4 },
    { sprite: 'server_rack',    dx: 21, dy: 7 },
    // archive shelving and the packaging corner
    { sprite: 'rack',           dx: 1,  dy: 10 },
    { sprite: 'rack',           dx: 4,  dy: 10 },
    { sprite: 'crate',          dx: 8,  dy: 11 },
    { sprite: 'crate',          dx: 10, dy: 11 },
    { sprite: 'couch',          dx: 14, dy: 11 },
    { sprite: 'table_small',    dx: 17, dy: 11 },
    { sprite: 'plant',          dx: 22, dy: 12 },
    { sprite: 'rug',            dx: 13, dy: 13 }
  ]
};

export const PARK = {
  bounds: { x: 64, y: 4, w: 78, h: 38 },
  // The lake. Bigger than the old 9x5 puddle, with a sand shore drawn round
  // it by the renderer and a paved path running down to the street so people
  // can actually walk here.
  pond: { x: 78, y: 16, w: 14, h: 8 },
  lakePath: { x: 87, y: 24, w: 2, h: 24 },
  /** Shore tiles people stand on when they visit. */
  lakeSpots: [
    { x: 80, y: 24, what: 'watching the ducks' },
    { x: 85, y: 24, what: 'sitting by the lake' },
    { x: 92, y: 20, what: 'skimming stones' },
    { x: 77, y: 18, what: 'getting some air' }
  ],
  // note: the tree that used to sit at (64,38) was removed -- the café
  // stands there now
  trees: [
    { x: 67, y: 6 }, { x: 74, y: 9 }, { x: 92, y: 7 },
    { x: 68, y: 18 }, { x: 95, y: 24 },
    { x: 78, y: 5 },
    // the trees that stood at (122,14) and (134,9) came out when the Archive
    // Studio was built; (110,8) shifted west to clear its wall.
    // (99,12) and (106,8) shifted south, out of Sage's House footprint
    // (x94-109, y4-14) when it moved here from the street, and kept clear
    // of x100-102 -- the walkway running from her door down to the street.
    { x: 96, y: 30 }, { x: 96, y: 36 },
    { x: 138, y: 24 }, { x: 120, y: 50 }, { x: 66, y: 22 }
  ],
  benches: [
    // (79,25) moved west along the shore when the General Store was sited
    // between the lake and the cafe -- the store's footprint sat on it.
    { x: 75, y: 18 }, { x: 86, y: 25 }, { x: 94, y: 21 }
  ],
  flowers: [
    { x: 66, y: 14, s: 'flower_a' }, { x: 90, y: 30, s: 'flower_b' },
    { x: 76, y: 36, s: 'flower_a' }, { x: 97, y: 19, s: 'flower_b' },
    { x: 70, y: 24, s: 'flower_b' }, { x: 103, y: 8, s: 'flower_a' }
  ]
};

export const OUTDOOR_SPRITES = [
  'asphalt', 'water', 'tree_big', 'bench_out', 'flower_a', 'flower_b',
  'bed', 'tv', 'kitchen', 'table_small',
  'cafe_bar', 'espresso', 'pastry', 'menu', 'stool', 'cafe_table',
  'bulletin', 'counter', 'desk_small', 'chair', 'billboard', 'streetlamp',
  'plane', 'luggage', 'floor_terminal', 'glass_wall'
];

/**
 * The money billboard -- combined real financial status for BOTH businesses
 * (Eva's trading P&L, the Archive Studio's unpublished-but-shipped
 * inventory), read live in the click panel from /api/status + /api/studio.
 * Placed on the open ground between the HQ and the street houses, right by
 * the staff-door commute route everyone already walks -- not tucked away.
 */
export const BILLBOARD = { x: 46, y: 44, w: 3, h: 3, station: 'money-board' };

/**
 * Curbside parking for the two HQ staff who now live out in Sunrise
 * Meadows -- Otis and Margo, same reasoning as the doctors (see
 * world/commute.js): the drive is real, so the car is real. Two spots
 * flanking the billboard, clear of it and of the staff-door connector,
 * each with its own straight run down to the road. No shared building
 * shell like the hospital's lot -- just curb, since the HQ already exists
 * and this is genuinely all the room there is right in front of it.
 */
export const HQ_PARKING = {
  spots: [ { x: 40, y: 44, sprite: 'car_green',  w: 4, h: 2, staff: 'mechanic' },
           { x: 56, y: 44, sprite: 'car_purple', w: 4, h: 2, staff: 'risk' } ]
};

/**
 * Downtown visitor parking -- the corridor between the cafe (ends x85) and
 * the condo block (starts x90), genuinely empty the whole 15 tiles down,
 * verified clear before placing. This is where a Sunrise Meadows resident
 * actually parks on a leisure trip into town (see world/commute.js's
 * startTownTrip) -- not assigned to any one person the way the work lots
 * are, since whoever's visiting takes whichever space is free.
 */
export const TOWN_PARKING = {
  spots: [
    { x: 86, y: 33, w: 4, h: 2 },
    { x: 86, y: 37, w: 4, h: 2 },
    { x: 86, y: 41, w: 4, h: 2 },
    { x: 86, y: 45, w: 4, h: 2 }
  ]
};

/**
 * Streetlamp positions -- the single source of truth for where a lamp
 * stands, shared by night.js (which lights these spots after dark) and
 * renderer.js (which draws the physical post at these same coordinates in
 * daylight, so the two never drift apart). Perimeter of the HQ lot, both
 * kerbs of the main road, and along the Archive Studio's walkway.
 */
// Real crossing columns -- every place a walkway actually reaches the main
// street -- kept out of the curbside lamp run below, so a post never lands
// where someone is meant to be walking through, not around it: the HQ
// staff-door connector (x50-53), the condo's walkway (x88-89), and the
// alley the Studio and Sage's House both funnel into (x115-117).
const STREET_CROSSINGS = [[49, 54], [87, 90], [114, 118]];
const onCrossing = x => STREET_CROSSINGS.some(([a, b]) => x >= a && x <= b);

export function lampPositions() {
  const out = [];
  const b = BUILDING;
  for (let i = 0; i <= 4; i++) {
    const fx = b.x + (b.w * i) / 4;
    out.push({ x: fx, y: b.y - 2.2 });
    out.push({ x: fx, y: b.y + b.h + 2.2 });
  }
  for (let x = 6; x < WORLD.w; x += 12) {
    // y47.4 sits inside sidewalk row 47 (47.0-48.0), correctly clear of the
    // road (rows 48-51). The south side must land in row 52 (52.0-53.0),
    // NOT 51.8 -- that's still inside row 51, the road's own last row, which
    // is exactly the "pole standing in the street" bug once these were
    // given an actual base-anchored sprite instead of just a soft glow.
    if (!onCrossing(x)) out.push({ x, y: 47.4 });
    if (!onCrossing(x + 6)) out.push({ x: x + 6, y: 52.4 });
  }
  // Flanking the Studio's own door approach and the alley it shares with
  // Sage's walkway, rather than standing dead-centre in either.
  for (const [x, y] of [[121, 27], [127, 27], [113, 35], [119, 35]]) {
    out.push({ x, y });
  }
  return out;
}

const within = (tx, ty, r) => tx >= r.x && tx < r.x + r.w && ty >= r.y && ty < r.y + r.h;

/** Outdoor things a character cannot walk through. */
export function outdoorBlocked(tx, ty) {
  if (within(tx, ty, PARK.lakePath)) return false;   // the path to the lake
  if (within(tx, ty, PARK.pond)) return true;        // you cannot walk on water
  if (within(tx, ty, BILLBOARD)) return true;
  for (const s of HOSPITAL_PARKING.spots) if (within(tx, ty, { x: s.x, y: s.y, w: s.w, h: s.h })) return true;
  for (const s of HQ_PARKING.spots) if (within(tx, ty, { x: s.x, y: s.y, w: s.w, h: s.h })) return true;
  for (const s of TOWN_PARKING.spots) if (within(tx, ty, { x: s.x, y: s.y, w: s.w, h: s.h })) return true;
  for (const h of HOMES) if (h.parkSpot && within(tx, ty, h.parkSpot)) return true;
  for (const t of PARK.trees) if (within(tx, ty, { x: t.x, y: t.y, w: 3, h: 3 })) return true;
  for (const b of PARK.benches) if (within(tx, ty, { x: b.x, y: b.y, w: 2, h: 1 })) return true;

  // ---- standalone street houses ----------------------------------------
  // NOTE, known and deliberate: this collides against the GENERIC
  // HOME_LAYOUT, while the renderer draws layoutFor(h) -- the generic
  // anchors plus each resident's own personalized extras (HOME_STYLES).
  // So a personal bookshelf or telly is visible but walk-through-able.
  // Left as-is rather than "fixed": the two lists genuinely disagree in
  // several homes, and switching this to layoutFor() would seal off
  // standing spots that people currently use. Anything that picks a spot
  // inside a house must therefore satisfy BOTH lists to be safe -- see
  // HOUSE_SPOTS' kitchen entry, which had to.
  for (const h of HOMES) {
    if (h.unit || !within(tx, ty, h.rect)) continue;
    if (within(tx, ty, h.doorway)) return false;
    if (!within(tx, ty, h.interior)) return true;
    for (const f of HOME_LAYOUT) {
      if (f.soft) continue;
      const r = { x: h.interior.x + f.dx - 1, y: h.interior.y + f.dy - 1, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  // ---- the condo block ---------------------------------------------------
  if (within(tx, ty, CONDO.rect)) {
    if (within(tx, ty, CONDO.entrance)) return false;
    if (within(tx, ty, CONDO.corridor)) return false;     // shared hallway
    for (const h of HOMES) {
      if (!h.unit) continue;
      if (within(tx, ty, h.doorway)) return false;
      if (!within(tx, ty, h.interior)) continue;
      for (const f of UNIT_LAYOUT) {
        if (f.soft) continue;
        const r = { x: h.interior.x + f.dx, y: h.interior.y + f.dy, w: f.w, h: f.h };
        if (within(tx, ty, r)) return true;
      }
      return false;
    }
    return true;                                          // structural walls
  }

  if (within(tx, ty, SAGE_HOME.rect)) {
    if (within(tx, ty, SAGE_HOME.doorway)) return false;
    if (!within(tx, ty, SAGE_HOME.interior)) return true;
    for (const f of SAGE_HOME.layout) {
      if (f.soft) continue;
      const r = { x: SAGE_HOME.interior.x + f.dx, y: SAGE_HOME.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, STORE.rect)) {
    if (within(tx, ty, STORE.doorway)) return false;
    if (!within(tx, ty, STORE.interior)) return true;
    for (const f of STORE.layout) {
      if (f.soft) continue;
      const r = { x: STORE.interior.x + f.dx, y: STORE.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, ATM_CO.rect)) {
    if (within(tx, ty, ATM_CO.doorway)) return false;
    if (!within(tx, ty, ATM_CO.interior)) return true;
    for (const f of ATM_CO.layout) {
      if (f.soft) continue;
      const r = { x: ATM_CO.interior.x + f.dx, y: ATM_CO.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, NEWS_STUDIO.rect)) {
    if (within(tx, ty, NEWS_STUDIO.doorway)) return false;
    if (!within(tx, ty, NEWS_STUDIO.interior)) return true;
    for (const f of NEWS_STUDIO.layout) {
      if (f.soft) continue;
      const r = { x: NEWS_STUDIO.interior.x + f.dx, y: NEWS_STUDIO.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, FIELD_OFFICE.rect)) {
    if (within(tx, ty, FIELD_OFFICE.doorway)) return false;
    if (!within(tx, ty, FIELD_OFFICE.interior)) return true;
    for (const f of FIELD_OFFICE.layout) {
      if (f.soft) continue;
      const r = { x: FIELD_OFFICE.interior.x + f.dx, y: FIELD_OFFICE.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, BANK.rect)) {
    if (within(tx, ty, BANK.doorway)) return false;
    if (!within(tx, ty, BANK.interior)) return true;
    for (const f of BANK.layout) {
      if (f.soft) continue;
      const r = { x: BANK.interior.x + f.dx, y: BANK.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, TAX_OFFICE.rect)) {
    if (within(tx, ty, TAX_OFFICE.doorway)) return false;
    if (!within(tx, ty, TAX_OFFICE.interior)) return true;
    for (const f of TAX_OFFICE.layout) {
      if (f.soft) continue;
      const r = { x: TAX_OFFICE.interior.x + f.dx, y: TAX_OFFICE.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, PREDICT_DESK.rect)) {
    if (within(tx, ty, PREDICT_DESK.doorway)) return false;
    if (!within(tx, ty, PREDICT_DESK.interior)) return true;
    for (const f of PREDICT_DESK.layout) {
      if (f.soft) continue;
      const r = { x: PREDICT_DESK.interior.x + f.dx, y: PREDICT_DESK.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, TERMINAL.rect)) {
    if (within(tx, ty, TERMINAL.doorway)) return false;
    if (!within(tx, ty, TERMINAL.interior)) return true;
    for (const f of TERMINAL.layout) {
      if (f.soft) continue;
      const r = { x: TERMINAL.interior.x + f.dx, y: TERMINAL.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  for (const shop of SHOPS) {
    if (within(tx, ty, shop.rect)) {
      if (within(tx, ty, shop.doorway)) return false;
      if (!within(tx, ty, shop.interior)) return true;
      for (const f of shop.layout) {
        if (f.soft) continue;
        const r = { x: shop.interior.x + f.dx, y: shop.interior.y + f.dy, w: f.w, h: f.h };
        if (within(tx, ty, r)) return true;
      }
      return false;
    }
  }

  if (within(tx, ty, HOSPITAL.rect)) {
    if (within(tx, ty, HOSPITAL.doorway)) return false;
    if (!within(tx, ty, HOSPITAL.interior)) return true;
    for (const f of HOSPITAL.layout) {
      if (f.soft) continue;
      const r = { x: HOSPITAL.interior.x + f.dx, y: HOSPITAL.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }

  if (within(tx, ty, CAFE.rect)) {
    if (within(tx, ty, CAFE.doorway)) return false;
    if (!within(tx, ty, CAFE.interior)) return true;
    for (const f of CAFE.layout) {
      if (f.soft) continue;
      // cafe layout offsets are INTERIOR-relative (dx 0..19, dy 0..12)
      const r = { x: CAFE.interior.x + f.dx, y: CAFE.interior.y + f.dy, w: f.w, h: f.h };
      if (within(tx, ty, r)) return true;
    }
    return false;
  }
  return false;
}

/** True anywhere outside the HQ footprint that is on the map. */
export function isOutdoors(tx, ty) {
  if (tx < 0 || ty < 0 || tx >= WORLD.w || ty >= WORLD.h) return false;
  return !within(tx, ty, BUILDING);
}

/** Sprite files Phase 1 needs loaded before the first draw. */
export const SPRITES = [
  'grass', 'sidewalk', 'floor_wood', 'floor_tile', 'floor_carpet', 'wall', 'door'
];


/**
 * The Field Office -- Voss & Ito, plainclothes "security." Deliberately NOT
 * named after any real agency (this is a private single-user pixel-art
 * world; a persistent building signed with a real federal agency's name
 * still isn't something to put up, even as a joke). Same standalone
 * construction as the ATM Co./News Desk.
 *
 * The building and the banter are decoration, same as everywhere else --
 * but their STATUS is real: real permission checks on the real secret
 * files this app and the live bot depend on (ElevenLabs key, Finnhub
 * key + account number, Robinhood auth), run live by
 * dashboard_server.py's build_security_status() and read into their
 * status bubble by activity.js's securityState(). All three currently
 * live outside anything this server serves statically, at chmod 600 --
 * see build_security_status()'s own header for exactly what "unsafe"
 * would mean and how it would show up here in real time.
 * Placed south of the street houses, on ground that was empty all session
 * (y63 onward was never used by anything above).
 */
const FIELD_X = 20, FIELD_Y = 63;
export const FIELD_OFFICE = {
  name: 'The Field Office',
  rect:     { x: FIELD_X, y: FIELD_Y, w: 14, h: 10 },
  interior: { x: FIELD_X + 1, y: FIELD_Y + 1, w: 12, h: 8 },
  doorway:  { x: FIELD_X + 6, y: FIELD_Y + 9, w: 2, h: 1 },   // south wall
  approach: { x: FIELD_X + 6, y: FIELD_Y + 10 },
  accent:   '#2c3e50',
  // Door sits at dx5-6 (interior-relative) -- kept clear front to back, same
  // walk-in-corridor rule every building here follows. Two symmetric desks
  // (case board + monitoring rack on Voss's side, filing + a shared couch on
  // Ito's), nothing invented beyond what a two-person office would need.
  layout: [
    { sprite: 'whiteboard',     dx: 1,  dy: 0, w: 3, h: 1 },   // case board
    { sprite: 'desk',           dx: 1,  dy: 1, w: 3, h: 2 },
    { sprite: 'chair',          dx: 2,  dy: 4, w: 1, h: 1 },
    { sprite: 'server_rack',    dx: 0,  dy: 5, w: 2, h: 2 },   // monitoring
    { sprite: 'filing_cabinet', dx: 10, dy: 0, w: 1, h: 2 },
    { sprite: 'desk_small',     dx: 8,  dy: 1, w: 2, h: 2 },
    { sprite: 'chair',          dx: 9,  dy: 4, w: 1, h: 1 },
    { sprite: 'couch',          dx: 8,  dy: 5, w: 3, h: 2, soft: true },
    { sprite: 'plant',          dx: 0,  dy: 0, w: 1, h: 1 },
    { sprite: 'plant',          dx: 11, dy: 7, w: 1, h: 1 }
  ]
};

export const FIELD_ROOM = {
  id: 'field',
  name: FIELD_OFFICE.name,
  rect: FIELD_OFFICE.rect,
  blurb: "The building is decoration, but Voss & Ito's status isn't -- it's a " +
         'real, live permission check on the 3 real secret files this app and ' +
         'the live bot depend on. See dashboard_server.py\'s build_security_status().',
  data: []
};

/**
 * The Bank -- the app's dedicated real-money view. Unlike the News Desk and
 * the Field Office, this room is NOT ambient decoration wearing real data
 * as a costume: clicking it (showRoom's room.id==='bank' branch, see
 * ui/panels.js's bankSection()) renders real charts straight off
 * /api/status -- the same equity_curve, recent_journal and recent_trades
 * every other real panel in this app already reads, just gathered into one
 * dedicated financial view instead of split across the Records Room. Same
 * standalone construction as the ATM Co./News Desk/Field Office. Placed in
 * the same south strip as the Field Office, on ground confirmed empty all
 * session (y63 onward).
 */
const BANK_X = 40, BANK_Y = 63;
export const BANK = {
  name: 'The Bank',
  rect:     { x: BANK_X, y: BANK_Y, w: 14, h: 10 },
  interior: { x: BANK_X + 1, y: BANK_Y + 1, w: 12, h: 8 },
  doorway:  { x: BANK_X + 6, y: BANK_Y + 9, w: 2, h: 1 },   // south wall, same reasoning as the Field Office
  approach: { x: BANK_X + 6, y: BANK_Y + 10 },
  accent:   '#c9a227',
  // Door at dx5-6 (interior-relative), kept clear front to back. A teller
  // desk and "the vault" (a server rack standing in for the ledger) on one
  // side, records + a waiting couch on the other -- nothing invented beyond
  // what a small two-room bank would actually have.
  layout: [
    { sprite: 'wallscreen',     dx: 1,  dy: 0, w: 3, h: 1 },
    { sprite: 'wallscreen',     dx: 8,  dy: 0, w: 3, h: 1 },
    { sprite: 'desk',           dx: 1,  dy: 2, w: 3, h: 2 },
    { sprite: 'chair',          dx: 2,  dy: 5, w: 1, h: 1 },
    { sprite: 'server_rack',    dx: 0,  dy: 5, w: 2, h: 2 },
    { sprite: 'filing_cabinet', dx: 9,  dy: 2, w: 1, h: 2 },
    { sprite: 'filing_cabinet', dx: 10, dy: 2, w: 1, h: 2 },
    { sprite: 'couch',          dx: 8,  dy: 5, w: 3, h: 2, soft: true },
    { sprite: 'plant',          dx: 0,  dy: 0, w: 1, h: 1 },
    { sprite: 'plant',          dx: 11, dy: 7, w: 1, h: 1 }
  ]
};

export const BANK_ROOM = {
  id: 'bank',
  name: BANK.name,
  rect: BANK.rect,
  blurb: 'Real charts, straight off /api/status -- the equity curve, daily ' +
         "P&L and win/loss record, gathered in one place. Click through for " +
         'the real numbers.',
  data: ['/api/status']
};

/**
 * The Tax Office -- a real realized-gains ledger, straight off the bot's
 * own trade log. Same real-data discipline as the Bank: clicking it (see
 * ui/panels.js's taxSection()) shows the real recent_trades list and the
 * real all-time total (totalPnl(), the same server-derived function
 * everywhere else uses). Deliberately does NOT compute or claim a tax
 * rate, bracket, or liability -- that's real financial/tax advice, and
 * this app doesn't give any. It states the raw real numbers and says so:
 * for your own records, not a filing document, consult a real
 * professional and your broker's official 1099. Same south strip as the
 * Field Office and the Bank, next open ground east of Marnie's house.
 */
const TAX_X = 70, TAX_Y = 63;
export const TAX_OFFICE = {
  name: 'The Tax Office',
  rect:     { x: TAX_X, y: TAX_Y, w: 14, h: 10 },
  interior: { x: TAX_X + 1, y: TAX_Y + 1, w: 12, h: 8 },
  doorway:  { x: TAX_X + 6, y: TAX_Y + 9, w: 2, h: 1 },   // south wall, same reasoning as the Field Office/Bank
  approach: { x: TAX_X + 6, y: TAX_Y + 10 },
  accent:   '#5c6b47',
  layout: [
    { sprite: 'filing_cabinet', dx: 0,  dy: 0, w: 1, h: 2 },
    { sprite: 'filing_cabinet', dx: 1,  dy: 0, w: 1, h: 2 },
    { sprite: 'rack',           dx: 9,  dy: 0, w: 3, h: 1 },
    { sprite: 'desk',           dx: 1,  dy: 2, w: 3, h: 2 },
    { sprite: 'chair',          dx: 2,  dy: 5, w: 1, h: 1 },
    { sprite: 'whiteboard',     dx: 8,  dy: 2, w: 3, h: 1 },
    { sprite: 'couch',          dx: 8,  dy: 5, w: 3, h: 2, soft: true },
    { sprite: 'plant',          dx: 0,  dy: 7, w: 1, h: 1 },
    { sprite: 'plant',          dx: 11, dy: 7, w: 1, h: 1 }
  ]
};

export const TAX_ROOM = {
  id: 'tax',
  name: TAX_OFFICE.name,
  rect: TAX_OFFICE.rect,
  blurb: 'A real realized-gains ledger, straight off the trade log -- for ' +
         'your own records. Not tax advice, and not a filing document: see ' +
         "the disclaimer inside.",
  data: ['/api/status']
};

/**
 * The Prediction Desk -- Fay's real, point-in-time snapshot of Sage's actual
 * Robinhood prediction-market (event contract) account: current dollar
 * value, plus the realized-trade history. UNLIKE the Bank/Tax Office, this
 * has no live bot behind it and no continuous polling -- dashboard_server.py
 * deliberately has no separate connection to Robinhood, so this is pulled by
 * hand (Claude + the Robinhood MCP tools) whenever Sage asks for a refresh,
 * then written to disk by predict_business.py. The "as of" timestamp on the
 * panel is the whole honesty story: nothing here claims to be live.
 * Placed on genuinely clear ground, verified against nav.js's walkable grid
 * and every other building's rect before placing (same discipline as the
 * ATM Co. and Wes's cottage) -- far east of downtown, its own quiet corner.
 */
const PREDICT_X = 190, PREDICT_Y = 54;
export const PREDICT_DESK = {
  name: 'The Prediction Desk',
  rect:     { x: PREDICT_X, y: PREDICT_Y, w: 14, h: 10 },
  interior: { x: PREDICT_X + 1, y: PREDICT_Y + 1, w: 12, h: 8 },
  doorway:  { x: PREDICT_X + 6, y: PREDICT_Y + 9, w: 2, h: 1 },   // south wall, same reasoning as the Bank/Tax Office
  approach: { x: PREDICT_X + 6, y: PREDICT_Y + 10 },
  accent:   '#6c4aa8',
  layout: [
    { sprite: 'wallscreen',     dx: 1,  dy: 0, w: 3, h: 1 },
    { sprite: 'desk',           dx: 1,  dy: 2, w: 3, h: 2 },
    { sprite: 'chair',          dx: 2,  dy: 5, w: 1, h: 1 },
    { sprite: 'filing_cabinet', dx: 0,  dy: 5, w: 1, h: 2 },
    { sprite: 'whiteboard',     dx: 8,  dy: 2, w: 3, h: 1 },
    { sprite: 'couch',          dx: 8,  dy: 5, w: 3, h: 2, soft: true },
    { sprite: 'plant',          dx: 0,  dy: 0, w: 1, h: 1 },
    { sprite: 'plant',          dx: 11, dy: 7, w: 1, h: 1 }
  ]
};

export const PREDICT_ROOM = {
  id: 'predict',
  name: PREDICT_DESK.name,
  rect: PREDICT_DESK.rect,
  blurb: "A real dollar snapshot of Sage's Robinhood prediction-market " +
         'activity -- pulled on request, not continuously polled. See ' +
         'predict_business.py.',
  data: ['/api/predictions']
};

/**
 * The Terminal -- Smallville Regional's one building, by far the biggest
 * footprint in the city (50x26, next largest is the Archive Studio at
 * 26x18). Bound to a real check: Claude searches Gmail for an actual
 * flight confirmation (not a marketing/abandoned-cart email -- the first
 * real check here found 15+ CheapOair "still thinking about Nashville?"
 * nags for a search Sage never finished booking, which is NOT a real
 * flight and does not count). Starts empty and says so -- same honesty
 * rule as the ATM Co.'s checklist and the Prediction Desk's snapshot.
 */
export const TERMINAL = {
  name: 'Smallville Regional',
  rect:     { x: 540, y: 90, w: 50, h: 26 },
  interior: { x: 541, y: 91, w: 48, h: 24 },
  doorway:  { x: 564, y: 115, w: 2, h: 1 },
  approach: { x: 564, y: 116 },
  accent:   '#3f6fa8',
  // Four real zones, not a generic office: a ticket counter (4 desks in an
  // actual row), a departures board wall, a baggage-claim corner (the only
  // place in the city 'luggage' props show up), and real gate seating
  // facing its own gate sign.
  layout: [
    // -- departures board + gate sign, the wall you see on walking in --
    { sprite: 'wallscreen',     dx: 18, dy: 1,  w: 4, h: 1 },
    { sprite: 'wallscreen',     dx: 24, dy: 1,  w: 4, h: 1 },
    { sprite: 'whiteboard',     dx: 30, dy: 1,  w: 3, h: 1 },   // "GATE A1"

    // -- ticket counter: four desks in a real row, not two islands --
    { sprite: 'filing_cabinet', dx: 0,  dy: 0,  w: 1, h: 2 },
    { sprite: 'desk',           dx: 2,  dy: 3,  w: 3, h: 2 },
    { sprite: 'chair',          dx: 3,  dy: 5,  w: 1, h: 1 },
    { sprite: 'desk',           dx: 7,  dy: 3,  w: 3, h: 2 },
    { sprite: 'chair',          dx: 8,  dy: 5,  w: 1, h: 1 },
    { sprite: 'desk',           dx: 12, dy: 3,  w: 3, h: 2 },
    { sprite: 'chair',          dx: 13, dy: 5,  w: 1, h: 1 },
    { sprite: 'desk',           dx: 17, dy: 3,  w: 3, h: 2 },
    { sprite: 'chair',          dx: 18, dy: 5,  w: 1, h: 1 },

    // -- baggage claim: its own desk + scattered luggage --
    { sprite: 'desk',           dx: 2,  dy: 9,  w: 3, h: 2 },
    { sprite: 'chair',          dx: 3,  dy: 11, w: 1, h: 1 },
    { sprite: 'luggage',        dx: 7,  dy: 10, w: 1, h: 1 },
    { sprite: 'luggage',        dx: 9,  dy: 10, w: 1, h: 1 },
    { sprite: 'luggage',        dx: 7,  dy: 12, w: 1, h: 1 },

    // -- gate seating: three rows of real bench chairs facing the windows,
    // not couches (a couch reads as a living room; rows of attached-style
    // seating read as a departure gate) --
    { sprite: 'chair', dx: 29, dy: 4,  w: 1, h: 1 }, { sprite: 'chair', dx: 31, dy: 4,  w: 1, h: 1 },
    { sprite: 'chair', dx: 33, dy: 4,  w: 1, h: 1 }, { sprite: 'chair', dx: 35, dy: 4,  w: 1, h: 1 },
    { sprite: 'chair', dx: 37, dy: 4,  w: 1, h: 1 }, { sprite: 'chair', dx: 39, dy: 4,  w: 1, h: 1 },
    { sprite: 'chair', dx: 29, dy: 7,  w: 1, h: 1 }, { sprite: 'chair', dx: 31, dy: 7,  w: 1, h: 1 },
    { sprite: 'chair', dx: 33, dy: 7,  w: 1, h: 1 }, { sprite: 'chair', dx: 35, dy: 7,  w: 1, h: 1 },
    { sprite: 'chair', dx: 37, dy: 7,  w: 1, h: 1 }, { sprite: 'chair', dx: 39, dy: 7,  w: 1, h: 1 },
    { sprite: 'chair', dx: 29, dy: 10, w: 1, h: 1 }, { sprite: 'chair', dx: 31, dy: 10, w: 1, h: 1 },
    { sprite: 'chair', dx: 33, dy: 10, w: 1, h: 1 }, { sprite: 'chair', dx: 35, dy: 10, w: 1, h: 1 },
    { sprite: 'chair', dx: 37, dy: 10, w: 1, h: 1 }, { sprite: 'chair', dx: 39, dy: 10, w: 1, h: 1 },
    { sprite: 'plant',          dx: 42, dy: 7,  w: 1, h: 1 },
    { sprite: 'plant',          dx: 42, dy: 1,  w: 1, h: 1 },

    // -- a couple of bags sitting by the door, like someone's about to leave --
    { sprite: 'luggage',        dx: 22, dy: 20, w: 1, h: 1 },
    { sprite: 'luggage',        dx: 24, dy: 20, w: 1, h: 1 },
    { sprite: 'plant',          dx: 22, dy: 22, w: 1, h: 1 },
    { sprite: 'plant',          dx: 46, dy: 22, w: 1, h: 1 }
  ]
};

export const TERMINAL_ROOM = {
  id: 'airport',
  name: TERMINAL.name,
  rect: TERMINAL.rect,
  blurb: "Real flight data, pulled from Gmail by Claude on request -- " +
         'marketing/abandoned-cart emails do not count, only an actual ' +
         'confirmation. See airport_business.py.',
  data: ['/api/airport']
};

/**
 * Six empty storefronts, 2x3, fronting the collector's south edge near
 * its east end -- real roadside placement instead of floating alone in
 * open grass (where they sat after the first relocation: clear of every
 * collision, but visually disconnected from the road network). Reserved
 * ground, not real businesses (see each one's blurb). Generic, reusable
 * shape: outdoorBlocked()/roomAt()/the renderer all just loop over this
 * array.
 */
export const SHOPS = [
  {
    id: 'shop_laundromat', name: "Sunset Laundromat", accent: '#7aa0c4',
    rect:     { x: 420, y: 117, w: 14, h: 10 },
    interior: { x: 421, y: 118, w: 12, h: 8 },
    doorway:  { x: 426, y: 126, w: 2, h: 1 },
    approach: { x: 426, y: 127 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
  {
    id: 'shop_hardware', name: "Eastside Hardware", accent: '#b08050',
    rect:     { x: 436, y: 117, w: 14, h: 10 },
    interior: { x: 437, y: 118, w: 12, h: 8 },
    doorway:  { x: 442, y: 126, w: 2, h: 1 },
    approach: { x: 442, y: 127 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
  {
    id: 'shop_tacos', name: "Corner Tacos", accent: '#d08838',
    rect:     { x: 452, y: 117, w: 14, h: 10 },
    interior: { x: 453, y: 118, w: 12, h: 8 },
    doorway:  { x: 458, y: 126, w: 2, h: 1 },
    approach: { x: 458, y: 127 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
  {
    id: 'shop_thrift', name: "Thrifty's", accent: '#9868a8',
    rect:     { x: 420, y: 131, w: 14, h: 10 },
    interior: { x: 421, y: 132, w: 12, h: 8 },
    doorway:  { x: 426, y: 140, w: 2, h: 1 },
    approach: { x: 426, y: 141 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
  {
    id: 'shop_gym', name: "Vista Gym", accent: '#588858',
    rect:     { x: 436, y: 131, w: 14, h: 10 },
    interior: { x: 437, y: 132, w: 12, h: 8 },
    doorway:  { x: 442, y: 140, w: 2, h: 1 },
    approach: { x: 442, y: 141 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
  {
    id: 'shop_pharmacy', name: "Eastside Pharmacy", accent: '#c05858',
    rect:     { x: 452, y: 131, w: 14, h: 10 },
    interior: { x: 453, y: 132, w: 12, h: 8 },
    doorway:  { x: 458, y: 140, w: 2, h: 1 },
    approach: { x: 458, y: 141 },
    layout: [ { sprite: 'whiteboard', dx: 1, dy: 0, w: 3, h: 1 }, { sprite: 'plant', dx: 9, dy: 6, w: 1, h: 1 } ],
    blurb: 'Empty storefront, reserved for a future project -- nothing real here yet.'
  },
];

/**
 * The News Desk -- where Bull & Bear physically stand. A standalone
 * building, same construction as the ATM Co. (rect/interior/doorway/
 * approach/accent/layout, drawn and wall-collided the same explicit way --
 * see outdoorBlocked() below). Ambient only: the REAL, data-driven bulletin
 * (real P&L, real incidents, real risk flags, all read live from
 * /api/status) lives entirely in ui/newsbulletin.js's popup, top-right of
 * the screen, on its own 30-minute cadence. Standing here is flavor, the
 * same honest split as the Archive Studio building vs. its real /api/studio
 * data -- nothing about this room is a second copy of that logic, and
 * nothing here is presented as a live newsroom actually producing anything.
 */
const NEWS_X = 160, NEWS_Y = 6;
export const NEWS_STUDIO = {
  name: 'The News Desk',
  rect:     { x: NEWS_X, y: NEWS_Y, w: 20, h: 14 },
  interior: { x: NEWS_X + 1, y: NEWS_Y + 1, w: 18, h: 12 },
  doorway:  { x: NEWS_X + 9, y: NEWS_Y + 13, w: 2, h: 1 },   // south wall
  approach: { x: NEWS_X + 9, y: NEWS_Y + 14 },
  accent:   '#c0392b',
  // Door sits at dx8-9 (interior-relative) -- that column stays completely
  // free of furniture from dy0 to dy11, the same walk-in-corridor rule
  // Sage's House and the ATM Co. both follow. Two symmetric anchor desks,
  // one either side of the corridor, each with its own backdrop screen and
  // a couch for the "green room" -- nothing invented beyond what a small
  // two-person set would actually need.
  layout: [
    { sprite: 'wallscreen',  dx: 1,  dy: 0, w: 3, h: 1 },   // Bull's backdrop
    { sprite: 'desk_small',  dx: 2,  dy: 2, w: 2, h: 2 },
    { sprite: 'chair',       dx: 2,  dy: 5, w: 1, h: 1 },
    { sprite: 'couch',       dx: 1,  dy: 8, w: 4, h: 2, soft: true },
    { sprite: 'wallscreen',  dx: 13, dy: 0, w: 3, h: 1 },   // Bear's backdrop
    { sprite: 'desk_small',  dx: 13, dy: 2, w: 2, h: 2 },
    { sprite: 'chair',       dx: 13, dy: 5, w: 1, h: 1 },
    { sprite: 'couch',       dx: 13, dy: 8, w: 4, h: 2, soft: true },
    { sprite: 'plant',       dx: 0,  dy: 10, w: 1, h: 1 },
    { sprite: 'plant',       dx: 17, dy: 10, w: 1, h: 1 }
  ]
};

export const NEWS_ROOM = {
  id: 'news',
  name: NEWS_STUDIO.name,
  rect: NEWS_STUDIO.rect,
  blurb: 'Where Bull & Bear stand -- ambient only. The real, data-driven ' +
         'bulletin lives in the popup, top-right of the screen, not here.',
  data: []
};

/** Which room contains a tile coordinate, or null. Used by hit-testing. */
/**
 * The studio is a separate building, not one of the six HQ rooms, so it was
 * never reachable through ROOMS. Presented here in room shape so clicking it
 * opens a department panel like anywhere else.
 */
export const STUDIO_ROOM = {
  id: 'studio',
  name: STUDIO.name,
  rect: STUDIO.rect,
  blurb: `Production house for ${STUDIO.channel}. Keeps the trading floor's ` +
         `hours — in at 09:00 ET, out at 16:00 ET.`,
  data: ['/api/studio']
};

/**
 * Sage's house -- the owner's own place. Player-controlled, so it isn't part
 * of the HOMES array (that array belongs to the fictional cast whose comings
 * and goings are driven by real bot state). Sits in the open grass south of
 * the street houses/Darkroom terrace (y54-61), which was empty until now.
 * Built the same way as the hospital/studio: its own rect/interior/doorway
 * and a dedicated shell() call in the renderer, a dedicated block in
 * outdoorBlocked() below.
 */
export const SAGE_HOME = {
  name: "Sage's House",
  // North of the pond -- park ground, not the street. Doorway faces south,
  // toward the lake, so the walk down to the water is right out the front
  // door. Two trees that used to sit in this footprint (99,12) and (106,8)
  // moved further south in PARK.trees below; nothing else was in the way.
  rect:     { x: 94, y: 4, w: 16, h: 11 },
  interior: { x: 95, y: 5, w: 14, h: 9 },
  doorway:  { x: 101, y: 14, w: 2, h: 1 },
  approach: { x: 101, y: 15 },
  accent:   '#d4af37',
  // The door is on the SOUTH wall (world y14), so dx6-7 (the doorway's own
  // width, in interior-local coordinates) is kept completely free of
  // furniture from dy0 all the way to dy8 -- a clear walk-in corridor from
  // the threshold to the back wall. Nothing else is placed in that column.
  layout: [
    { sprite: 'bed',         dx: 1,  dy: 1, w: 3, h: 3, soft: true },
    { sprite: 'plant',       dx: 4,  dy: 1, w: 1, h: 1 },
    { sprite: 'bookshelf',   dx: 10, dy: 1, w: 1, h: 1 },
    { sprite: 'plant',       dx: 12, dy: 1, w: 1, h: 1 },
    { sprite: 'kitchen',     dx: 0,  dy: 5, w: 2, h: 1 },
    { sprite: 'fridge',      dx: 0,  dy: 6, w: 2, h: 2 },
    { sprite: 'table_small', dx: 2,  dy: 6, w: 2, h: 2 },
    { sprite: 'chair',       dx: 4,  dy: 7, w: 1, h: 1 },
    { sprite: 'tv',          dx: 9,  dy: 3, w: 2, h: 1 },
    { sprite: 'couch',       dx: 9,  dy: 5, w: 4, h: 2, soft: true },
    { sprite: 'desk',        dx: 11, dy: 7, w: 2, h: 1 },
    { sprite: 'chair',       dx: 11, dy: 8, w: 1, h: 1 }
  ]
};

/**
 * Sage's ATM Company -- a small storefront, not a full building, since this
 * is a real business that's still just a plan (see _atm/status.json via
 * atm_business.py). North of the pond, near Sage's House and the park's
 * daily foot traffic -- fitting for a business whose whole point is being
 * somewhere people already are. Genuinely clear ground, verified against
 * nav.js's walkable grid before placing (the lesson from the warehouse
 * building search and the streetlamp-in-the-road bugs earlier).
 */
export const ATM_CO = {
  name: "Sage's ATM Co.",
  rect:     { x: 83, y: 4, w: 8, h: 7 },
  interior: { x: 84, y: 5, w: 6, h: 5 },
  doorway:  { x: 86, y: 10, w: 2, h: 1 },
  approach: { x: 86, y: 11 },
  accent:   '#2f7a52',
  layout: [
    { sprite: 'desk',           dx: 1, dy: 1, w: 3, h: 2 },
    { sprite: 'chair',          dx: 2, dy: 3, w: 1, h: 1 },
    { sprite: 'filing_cabinet', dx: 0, dy: 0, w: 1, h: 2 },
    { sprite: 'whiteboard',     dx: 2, dy: 0, w: 3, h: 1 },
    { sprite: 'plant',          dx: 5, dy: 4, w: 1, h: 1 }
  ]
};

export const ATM_ROOM = {
  id: 'atmco',
  name: ATM_CO.name,
  rect: ATM_CO.rect,
  blurb: 'A real business, still just a plan. Six real steps to a first machine — none of them done yet.',
  data: ['/api/atm']
};

/**
 * Smallville General's own staff lot -- directly east of the hospital
 * building itself, on genuinely fresh ground once the world was widened to
 * make room (see WORLD.w). A short straight run of pavement ties it right
 * into the main road, rather than the old cross-town alley route this used
 * before there was anywhere closer to put it. Two spaces, side by side,
 * each one doctor's own -- occupied only while they're actually at work
 * (see world/commute.js, which really drives the car here and parks it),
 * never decorative. Their tiles are always reserved (blocked in
 * outdoorBlocked() below) whether or not a car happens to be sitting there
 * right now; the rest of the lot stays open pavement.
 */
export const HOSPITAL_PARKING = {
  name: 'Smallville General — Staff Parking',
  rect: { x: 141, y: 34, w: 13, h: 8 },
  accent: '#5a6672',
  // cars are 4x2 tiles (see gen_hq_sprites.py) -- spaced so the two spots
  // read as genuinely side by side rather than overlapping.
  spots: [ { x: 143, y: 36, sprite: 'car_blue', w: 4, h: 2, staff: 'doctor1' },
           { x: 149, y: 36, sprite: 'car_yellow', w: 4, h: 2, staff: 'doctor2' } ]
};

/** A few standing spots inside Sage's own house -- used by her ambient
 * wander, the same way HOUSE_SPOTS/UNIT_SPOTS place the fictional cast. */
export function sageHomeSpots() {
  const ix = SAGE_HOME.interior.x, iy = SAGE_HOME.interior.y;
  return [
    { x: ix + 3,  y: iy + 2, what: 'resting' },
    { x: ix + 6,  y: iy + 6, what: 'in the middle of the room' },
    { x: ix + 11, y: iy + 8, what: 'at the desk' }
  ];
}

export const HOSPITAL_ROOM = {
  id: 'hospital',
  name: HOSPITAL.name,
  rect: HOSPITAL.rect,
  blurb: 'Ambient only -- no real subsystem behind it. Staffed after the sprites pass but never a data source.',
  data: []
};

export function roomAt(tx, ty) {
  for (const r of ROOMS) {
    const { x, y, w, h } = r.rect;
    if (tx >= x && tx < x + w && ty >= y && ty < y + h) return r;
  }
  const s = STUDIO_ROOM.rect;
  if (tx >= s.x && tx < s.x + s.w && ty >= s.y && ty < s.y + s.h) return STUDIO_ROOM;
  const a = ATM_ROOM.rect;
  if (tx >= a.x && tx < a.x + a.w && ty >= a.y && ty < a.y + a.h) return ATM_ROOM;
  const hos = HOSPITAL_ROOM.rect;
  if (tx >= hos.x && tx < hos.x + hos.w && ty >= hos.y && ty < hos.y + hos.h) return HOSPITAL_ROOM;
  const st = STORE_ROOM.rect;
  if (tx >= st.x && tx < st.x + st.w && ty >= st.y && ty < st.y + st.h) return STORE_ROOM;
  const n = NEWS_ROOM.rect;
  if (tx >= n.x && tx < n.x + n.w && ty >= n.y && ty < n.y + n.h) return NEWS_ROOM;
  const fl = FIELD_ROOM.rect;
  if (tx >= fl.x && tx < fl.x + fl.w && ty >= fl.y && ty < fl.y + fl.h) return FIELD_ROOM;
  const bk = BANK_ROOM.rect;
  if (tx >= bk.x && tx < bk.x + bk.w && ty >= bk.y && ty < bk.y + bk.h) return BANK_ROOM;
  const txo = TAX_ROOM.rect;
  if (tx >= txo.x && tx < txo.x + txo.w && ty >= txo.y && ty < txo.y + txo.h) return TAX_ROOM;
  const pd = PREDICT_ROOM.rect;
  if (tx >= pd.x && tx < pd.x + pd.w && ty >= pd.y && ty < pd.y + pd.h) return PREDICT_ROOM;
  const term = TERMINAL_ROOM.rect;
  if (tx >= term.x && tx < term.x + term.w && ty >= term.y && ty < term.y + term.h) return TERMINAL_ROOM;
  for (const shop of SHOPS) {
    if (tx >= shop.rect.x && tx < shop.rect.x + shop.rect.w &&
        ty >= shop.rect.y && ty < shop.rect.y + shop.rect.h) {
      return { id: shop.id, name: shop.name, rect: shop.rect, blurb: shop.blurb, data: [] };
    }
  }
  return null;
}
