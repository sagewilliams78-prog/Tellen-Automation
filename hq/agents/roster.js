/**
 * The cast.
 *
 * IMPORTANT / honesty note: the live system is ONE bot process
 * (sage_bot_v13.py). These characters are personifications of real
 * subsystems and real tracked symbols -- they are not separate AI agents,
 * and nothing here should imply the bot runs a staff. Each entry declares
 * the real /api/status field that will drive it from Phase 4.
 *
 * `station` refers to a tagged item in world/furniture.js.
 * `home` is the tile the character stands on (its desk chair).
 */

export const DIR = { down: 0, left: 1, right: 2, up: 3 };

export const ROSTER = [
  {
    id: 'eva',
    name: 'Eva',
    role: 'Trading bot',
    sheet: 'char_eva',
    room: 'trading',
    station: 'eva-desk',
    home: { x: 24, y: 9 },
    homeSlot: 7,
    facing: 'up',
    binds: 'bot_alive + scan'
  },
  {
    id: 'risk',
    name: 'Risk',
    role: 'Win-rate breaker / earnings blackout',
    sheet: 'char_risk',
    room: 'risk',
    station: 'risk-desk',
    home: { x: 7, y: 9 },
    homeSlot: 18,   // her own house out in Sunrise Meadows now, not the condo
    facing: 'up',
    binds: 'weekly_status + earnings_blackout',
    commute: 'hq', car: 'car_purple'   // drives in from Sunrise Meadows -- see world/commute.js
  },
  {
    id: 'mechanic',
    name: 'Mechanic',
    role: 'Scheduled health checks',
    sheet: 'char_mechanic',
    room: 'mechanic',
    station: 'mechanic-desk',
    home: { x: 36, y: 36 },
    homeSlot: 17,   // his own house out in Sunrise Meadows now, not the condo
    facing: 'up',
    binds: 'mechanics',
    commute: 'hq', car: 'car_green'    // drives in from Sunrise Meadows -- see world/commute.js
  }
  ,
  {
    id: 'barista',
    homeSlot: 13,
    name: 'Sal',
    role: 'Barista — keeps the complaint board',
    sheet: 'char_barista',
    room: 'cafe',
    station: 'cafe-bar',
    home: { x: 69, y: 34 },      // the lane behind the counter; never commutes
    facing: 'down',
    binds: 'everything that is currently blocked or broken'
  }
  ,
  // ---- Archive Studio ----------------------------------------------------
  // These three are bound to /api/studio, which reads the real files in
  // ~/Desktop/YouTube the. Each stands at the station for the stage its
  // project is actually at, so where they are IS the production status.
  {
    id: 'archivist',
    homeSlot: 10,
    name: 'Della',
    role: 'Research — sources photos and background',
    sheet: 'char_archivist',
    studio: true,
    room: 'studio',
    station: 'research',
    home: { x: 115, y: 11 },
    facing: 'up',
    binds: 'studio.projects[].stages.research'
  },
  // Priya's desk was always here -- the writers' room was built with two
  // seats "because scripts get a fact-check pass" (see hq-map.js's STUDIO
  // layout), but the seat sat empty until fact-checking became its own
  // real, independently-gated stage on 2026-08-29 (studio.py's STAGES).
  // Her job is a real, separate verification pass, not folded into Della's
  // research anymore -- every claim in the script checked against a real
  // source before it counts as done.
  {
    id: 'factchecker',
    homeSlot: 23,
    name: 'Iris',
    role: 'Fact-checking — verifies every claim against a real source',
    sheet: 'char_factchecker',
    studio: true,
    room: 'studio',
    station: 'factcheck',
    home: { x: 119, y: 13 },
    facing: 'up',
    binds: 'studio.projects[].stages.factcheck'
  },
  {
    id: 'writer',
    homeSlot: 11,
    name: 'Nell',
    role: 'Scripts and outlines',
    sheet: 'char_writer',
    studio: true,
    room: 'studio',
    station: 'script',
    home: { x: 122, y: 13 },
    facing: 'up',
    binds: 'studio.projects[].stages.script'
  },
  {
    id: 'editor',
    homeSlot: 12,
    name: 'Rafa',
    // Strengthened 2026-08-29: the real quality-review step he owns doesn't
    // just check a cut exists -- it pulls real sample frames and confirms
    // each one is legible, on-topic, AND actually matches what the
    // narration is saying at that exact timestamp, not just "looks right
    // in isolation." See archive-studio-shift's step 3.
    role: 'Shot list, cut, packaging — image quality & narration-timing match',
    sheet: 'char_editor',
    studio: true,
    room: 'studio',
    station: 'video',
    home: { x: 129, y: 13 },
    facing: 'up',
    binds: 'studio.projects[].stages.video'
  },
  // ---- The Crypto Desk ----------------------------------------------------
  // Nix. The ONLY desk in this world that trades around the clock -- BTC has
  // no market close, so while every other character is home asleep, this one
  // is still working. Bound to the real crypto-status.json that
  // crypto_btc_monitor.py writes every 60s: real BTC price, real RSI/trend,
  // real open position, and the real leash state (halted / kill switch).
  // Nothing here is ambient -- if it says holding, there is a real position.
  {
    id: 'crypto',
    homeSlot: 24,
    name: 'Nix',
    role: 'The Crypto Desk — BTC, 24/7, live orders on a short leash',
    sheet: 'char_crypto',
    crypto: true,
    room: 'trading',
    station: 'eva-desk',
    home: { x: 38, y: 9 },
    facing: 'up',
    binds: 'crypto-status.json -- real BTC state + real position + real leash'
  },
  // ---- Sage's ATM Co. -----------------------------------------------------
  // A real business, still just a plan -- see atm_business.py. One role for
  // now: working the real 6-step launch checklist. Bound to /api/atm, not
  // to any fictional stage-inference -- there's no file-scanning here, just
  // an honest done/not-done record.
  {
    id: 'atmops',
    homeSlot: 14,
    name: 'Wes',
    role: "Sage's ATM Co. — location scouting, launch checklist",
    sheet: 'char_atmops',
    room: 'atmco',
    station: 'atm-desk',
    home: { x: 87, y: 8 },
    facing: 'down',
    binds: 'atm.steps'
  },
  // ---- Smallville General -------------------------------------------------
  // Purely ambient -- the hospital has no real subsystem behind it (see its
  // own comment in hq-map.js: it only exists for the after-hours traffic/EMS
  // system). These two exist so the building has real staff instead of
  // standing empty, and so "give the doctors a car" has someone to drive it.
  // Homes are deliberately far across town (world/commute.js drives them in
  // and out along the road rather than the normal walking homing logic).
  {
    id: 'doctor1',
    homeSlot: 15,
    name: 'Dr. Ahn',
    role: 'Smallville General — attending',
    sheet: 'char_doctor1',
    hospital: true,
    commute: 'hospital', car: 'car_blue',
    room: 'hospital',
    station: 'hospital-desk',
    home: { x: 125, y: 36 },
    facing: 'up',
    binds: 'ambient only -- no real hospital data'
  },
  {
    id: 'doctor2',
    homeSlot: 16,
    name: 'Dr. Reyes',
    role: 'Smallville General — attending',
    sheet: 'char_doctor2',
    hospital: true,
    commute: 'hospital', car: 'car_yellow',
    room: 'hospital',
    station: 'hospital-desk2',
    home: { x: 123, y: 43 },
    facing: 'down',
    binds: 'ambient only -- no real hospital data'
  },
  // ---- The News Desk -------------------------------------------------
  // Bull and Bear, in the flesh -- the SAME two anchors as the popup
  // bulletin (ui/newsbulletin.js), now with a real desk and a real home,
  // same as everyone else in this world. Purely ambient (see
  // activity.js's newsState): the real, data-driven broadcast still lives
  // entirely in the popup, on its own 30-minute cadence. Standing here is
  // flavor, not a second copy of that logic.
  {
    id: 'bull',
    homeSlot: 19,
    name: 'Bull',
    role: 'The News Desk — anchor',
    sheet: 'char_bull',
    news: true,
    room: 'news',
    station: 'news-desk-bull',
    home: { x: 163, y: 12 },
    facing: 'up',
    binds: "ambient only -- personifies ui/newsbulletin.js's Bull"
  },
  {
    id: 'bear',
    homeSlot: 20,
    name: 'Bear',
    role: 'The News Desk — anchor',
    sheet: 'char_bear',
    news: true,
    room: 'news',
    station: 'news-desk-bear',
    home: { x: 174, y: 12 },
    facing: 'up',
    binds: "ambient only -- personifies ui/newsbulletin.js's Bear"
  },
  // ---- The Field Office -----------------------------------------------
  // Voss & Ito. Their status is a REAL check now, not decoration: real
  // permission checks on the real secret files this app and the live bot
  // depend on (see activity.js's securityState + dashboard_server.py's
  // build_security_status()). Everything else about the room is still
  // ambient -- see hq-map.js's FIELD_OFFICE comment.
  {
    id: 'voss',
    homeSlot: 8,
    name: 'Voss',
    role: 'The Field Office — security',
    sheet: 'char_voss',
    security: true,
    room: 'field',
    station: 'field-desk-voss',
    home: { x: 23, y: 68 },
    facing: 'up',
    binds: 'real secret-file permission checks -- build_security_status()'
  },
  {
    id: 'ito',
    homeSlot: 9,
    name: 'Ito',
    role: 'The Field Office — security',
    sheet: 'char_ito',
    security: true,
    room: 'field',
    station: 'field-desk-ito',
    home: { x: 30, y: 68 },
    facing: 'up',
    binds: 'real secret-file permission checks -- build_security_status()'
  },
  // ---- The Bank ---------------------------------------------------------
  // Marnie. Her status bubble is a real number, same discipline as Voss &
  // Ito's: today's real P&L (see activity.js's bankState). The room's real
  // substance is the click-through panel (ui/panels.js's bankSection),
  // same as every other real data room in this app.
  {
    id: 'marnie',
    homeSlot: 21,
    name: 'Marnie',
    role: 'The Bank — teller',
    sheet: 'char_marnie',
    bank: true,
    room: 'bank',
    station: 'bank-desk',
    home: { x: 43, y: 69 },
    facing: 'up',
    binds: "today's real P&L -- todaysPnl()"
  },
  // ---- The Tax Office -----------------------------------------------------
  // Percy. The room's real substance is the click-through panel
  // (ui/panels.js's taxSection): a real realized-gains ledger off the trade
  // log, all-time total via totalPnl() -- no rate, bracket, or liability
  // ever computed or claimed. Not tax advice.
  {
    id: 'percy',
    homeSlot: 22,
    name: 'Percy',
    role: 'The Tax Office — records',
    sheet: 'char_percy',
    tax: true,
    room: 'tax',
    station: 'tax-desk',
    home: { x: 73, y: 69 },
    facing: 'up',
    binds: 'real realized-gains ledger -- totalPnl() + recent_trades'
  },
  // ---- The Prediction Desk -----------------------------------------------
  // Fay. A real dollar snapshot of Sage's actual Robinhood prediction-market
  // account -- pulled by hand via the Robinhood MCP tools, not a live bot.
  // See hq-map.js's PREDICT_DESK comment and predict_business.py.
  {
    id: 'predict',
    homeSlot: 25,
    name: 'Fay',
    role: 'The Prediction Desk — real event-contract snapshot',
    sheet: 'char_predict',
    predict: true,
    room: 'predict',
    station: 'predict-desk',
    home: { x: 193, y: 60 },
    facing: 'up',
    binds: 'predict_business.py -- event_contracts_value + realized trade history'
  },
  // ---- Ambient townsfolk -------------------------------------------------
  // Milo, Nadia, Reed. No real subsystem behind any of these three, same as
  // the doctors and Bull & Bear -- added purely so the park and the street
  // outside the General Store have people in them who aren't staff of a
  // real room. Each has its own small home (see hq-map.js) and a fixed
  // daytime spot, same as everyone else here.
  {
    id: 'milo',
    homeSlot: 26,
    name: 'Milo',
    role: 'Ambient — park regular',
    ambient: true,
    sheet: 'char_milo',
    room: 'park',
    home: { x: 70, y: 27 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'nadia',
    homeSlot: 27,
    name: 'Nadia',
    role: 'Ambient — park regular',
    ambient: true,
    sheet: 'char_nadia',
    room: 'park',
    home: { x: 87, y: 26 },
    facing: 'left',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'reed',
    homeSlot: 28,
    name: 'Reed',
    role: 'Ambient — hangs around the General Store',
    ambient: true,
    sheet: 'char_reed',
    room: 'store',
    home: { x: 85, y: 28 },
    facing: 'left',
    binds: 'ambient only -- no real subsystem behind this'
  },
  // ---- The Outskirts -----------------------------------------------------
  // Theo, Greta. Ambient, same as Milo/Nadia/Reed -- filler for the new
  // row of houses south of the hospital. The other two houses on that same
  // row are deliberately vacant (see hq-map.js's FORSALE1_HOME/FORSALE2_HOME)
  // and have no roster entry at all.
  {
    id: 'theo',
    homeSlot: 29,
    name: 'Theo',
    role: 'Ambient — the Outskirts',
    ambient: true,
    sheet: 'char_theo',
    room: 'outskirts',
    home: { x: 146, y: 64 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'greta',
    homeSlot: 30,
    name: 'Greta',
    role: 'Ambient — the Outskirts',
    ambient: true,
    sheet: 'char_greta',
    room: 'outskirts',
    home: { x: 158, y: 64 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  // ---- The Eastside -------------------------------------------------------
  // 40 crowd-fill residents, 10 shared sprites reused 4x each. No real
  // subsystem behind any of them -- see hq-map.js's EASTSIDE_HOMES comment.
  {
    id: 'oscar',
    homeSlot: 33,
    name: 'Oscar',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler1',
    room: 'eastside',
    home: { x: 274, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'lena',
    homeSlot: 34,
    name: 'Lena',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler2',
    room: 'eastside',
    home: { x: 284, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'hugo',
    homeSlot: 35,
    name: 'Hugo',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler3',
    room: 'eastside',
    home: { x: 270, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'mira',
    homeSlot: 36,
    name: 'Mira',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler4',
    room: 'eastside',
    home: { x: 270, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'dex',
    homeSlot: 37,
    name: 'Dex',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler5',
    room: 'eastside',
    home: { x: 289, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'paloma',
    homeSlot: 38,
    name: 'Paloma',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler6',
    room: 'eastside',
    home: { x: 289, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'arlo',
    homeSlot: 39,
    name: 'Arlo',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler7',
    room: 'eastside',
    home: { x: 314, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'sable',
    homeSlot: 40,
    name: 'Sable',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler8',
    room: 'eastside',
    home: { x: 324, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'finn',
    homeSlot: 41,
    name: 'Finn',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler9',
    room: 'eastside',
    home: { x: 310, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'juno',
    homeSlot: 42,
    name: 'Juno',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler10',
    room: 'eastside',
    home: { x: 310, y: 135 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'rhea',
    homeSlot: 43,
    name: 'Rhea',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler1',
    room: 'eastside',
    home: { x: 329, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'soren',
    homeSlot: 44,
    name: 'Soren',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler2',
    room: 'eastside',
    home: { x: 329, y: 135 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'ivy',
    homeSlot: 45,
    name: 'Ivy',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler3',
    room: 'eastside',
    home: { x: 354, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'mateo',
    homeSlot: 46,
    name: 'Mateo',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler4',
    room: 'eastside',
    home: { x: 364, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'celia',
    homeSlot: 47,
    name: 'Celia',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler5',
    room: 'eastside',
    home: { x: 350, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'dash',
    homeSlot: 48,
    name: 'Dash',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler6',
    room: 'eastside',
    home: { x: 350, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'wylie',
    homeSlot: 49,
    name: 'Wylie',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler7',
    room: 'eastside',
    home: { x: 369, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'noor',
    homeSlot: 50,
    name: 'Noor',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler8',
    room: 'eastside',
    home: { x: 369, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'bram',
    homeSlot: 51,
    name: 'Bram',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler9',
    room: 'eastside',
    home: { x: 394, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'tamsin',
    homeSlot: 52,
    name: 'Tamsin',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler10',
    room: 'eastside',
    home: { x: 404, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'zane',
    homeSlot: 53,
    name: 'Zane',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler1',
    room: 'eastside',
    home: { x: 390, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'odette',
    homeSlot: 54,
    name: 'Odette',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler2',
    room: 'eastside',
    home: { x: 390, y: 135 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'cole',
    homeSlot: 55,
    name: 'Cole',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler3',
    room: 'eastside',
    home: { x: 409, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'freya',
    homeSlot: 56,
    name: 'Freya',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler4',
    room: 'eastside',
    home: { x: 409, y: 135 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'enzo',
    homeSlot: 57,
    name: 'Enzo',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler5',
    room: 'eastside',
    home: { x: 434, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'marisol',
    homeSlot: 58,
    name: 'Marisol',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler6',
    room: 'eastside',
    home: { x: 444, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'kai',
    homeSlot: 59,
    name: 'Kai',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler7',
    room: 'eastside',
    home: { x: 430, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'thalia',
    homeSlot: 60,
    name: 'Thalia',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler8',
    room: 'eastside',
    home: { x: 430, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'dmitri',
    homeSlot: 61,
    name: 'Dmitri',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler9',
    room: 'eastside',
    home: { x: 449, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'elsie',
    homeSlot: 62,
    name: 'Elsie',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler10',
    room: 'eastside',
    home: { x: 449, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'rowan',
    homeSlot: 63,
    name: 'Rowan',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler1',
    room: 'eastside',
    home: { x: 294, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'vesna',
    homeSlot: 64,
    name: 'Vesna',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler2',
    room: 'eastside',
    home: { x: 304, y: 139 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'lior',
    homeSlot: 65,
    name: 'Lior',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler3',
    room: 'eastside',
    home: { x: 290, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'bianca',
    homeSlot: 66,
    name: 'Bianca',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler4',
    room: 'eastside',
    home: { x: 290, y: 135 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'caspian',
    homeSlot: 67,
    name: 'Caspian',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler5',
    room: 'eastside',
    home: { x: 309, y: 127 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'ingrid',
    homeSlot: 68,
    name: 'Ingrid',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler6',
    room: 'eastside',
    home: { x: 374, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'mo',
    homeSlot: 69,
    name: 'Mo',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler7',
    room: 'eastside',
    home: { x: 384, y: 86 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'sunny',
    homeSlot: 70,
    name: 'Sunny',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler8',
    room: 'eastside',
    home: { x: 370, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'petra',
    homeSlot: 71,
    name: 'Petra',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler9',
    room: 'eastside',
    home: { x: 370, y: 97 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  },
  {
    id: 'dario',
    homeSlot: 72,
    name: 'Dario',
    role: 'Ambient — the Eastside',
    ambient: true,
    sheet: 'char_filler10',
    room: 'eastside',
    home: { x: 389, y: 89 },
    facing: 'down',
    binds: 'ambient only -- no real subsystem behind this'
  }
];

/**
 * One desk per DESK, not per symbol -- each desk already covers up to
 * SYMBOLS_PER_DESK (3) real symbols via activity.js's deskSymbols()/
 * mostActionable(), showing whichever of its group is most actionable
 * right now. 7 desks x 3 = 21 symbols of headroom, comfortably above the
 * 14-symbol watchlist promote_candidates.py produced and the 20-symbol
 * ceiling it was asked to grow toward. That's why this stayed at 7 rather
 * than growing into a bigger grid.
 */
const DESK_TILES = [
  { x: 6,  y: 29 }, { x: 11, y: 29 }, { x: 16, y: 29 }, { x: 21, y: 29 },
  { x: 6,  y: 35 }, { x: 11, y: 35 }, { x: 16, y: 35 }
];

/** How many physical desks actually exist. activity.js's desk-assignment
 *  math reads this so it can never drift from what's really built. */
export const DESK_COUNT = DESK_TILES.length;

for (let i = 0; i < DESK_TILES.length; i++) {
  ROSTER.push({
    id: `sym${i}`,
    name: `Desk ${i + 1}`,        // replaced with the real ticker in Phase 4
    role: 'Watchlist symbol',
    sheet: `char_trader${i}`,
    room: 'watchlist',
    station: `sym-${i}`,
    home: { ...DESK_TILES[i] },
    facing: 'up',
    slot: i,
    binds: 'scan.symbols[]'
  });
}

// ---- Smallville Regional (the airport) -------------------------------
// Dana, the gate agent. Bound to a real check: Claude searches Gmail for
// an actual flight confirmation (never a marketing/retargeting email --
// see airport_business.py's own header for why that distinction is real
// and not pedantic). Starts empty, says so, same honesty rule as Wes/Fay.
ROSTER.push({
  id: 'dana',
  homeSlot: 73,
  name: 'Dana',
  role: 'Smallville Regional — gate agent',
  sheet: 'char_dana',
  airport: true,
  room: 'airport',
  station: 'checkin-desk',
  home: { x: 544, y: 97 },
  facing: 'down',
  binds: 'airport_business.py -- real Gmail flight-confirmation search, never marketing email'
});

export const ROSTER_SPRITES = ROSTER.map(a => a.sheet);
