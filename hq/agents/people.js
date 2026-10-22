/**
 * The people who work the desks.
 *
 * A character is a PERSON, not a ticker. The watchlist changes (COIN was
 * swapped for SMCI on 2026-08-21), so desk 3 has always been Gus's desk --
 * only his assignment moves. Names and backstories are fixed and persist
 * across any watchlist change.
 *
 * NOTE: desk 3 was originally named "Bear" -- renamed to Gus when the news
 * bulletin's Bull & Bear anchors were added as real, separately-drawn HQ
 * characters, to avoid the exact "two Junes" name collision this world hit
 * once before. See ui/newsbulletin.js and world/hq-map.js's NEWS_ROOM.
 *
 * IMPORTANT: these biographies and the banter lines are FICTION. They are
 * flavour for the world. Nothing in here is a market claim, a number, or a
 * piece of trading advice -- banter deliberately never mentions prices,
 * P&L, or what a symbol is about to do. Real state always lives in the
 * status bubble, which comes from agents/activity.js.
 */

export const PEOPLE = {
  0: {
    name: 'Rosa',
    full: 'Rosa Delgado',
    title: 'Desk 1 — floor veteran',
    bio: 'Started as a runner on a physical trading floor at nineteen and never quite got the noise out of her head. Keeps a chewed-up pen she refuses to replace. Talks in short bursts and trusts her gut about three seconds before she can explain why.',
    trait: 'superstitious',
    lines: [
      "Pen's still lucky. Don't touch it.",
      'Quiet mornings make me nervous.',
      "I miss the shouting, honestly.",
      'Third coffee. Judge me later.',
      "You ever get a feeling and no reason for it?"
    ],
    replies: [
      "You said that last week too.",
      'That pen is disgusting, Rosa.',
      'Sure. Sure it is.'
    ]
  },
  1: {
    name: 'Miles',
    full: 'Miles Okafor',
    title: 'Desk 2 — ex-actuary',
    bio: 'Spent eleven years pricing insurance risk before deciding it was too exciting. Double-checks everything, then checks it once more. Has a spreadsheet for his groceries. Genuinely happy when nothing happens.',
    trait: 'cautious',
    lines: [
      'I ran the numbers twice. Then a third time.',
      'Boring is a perfectly good outcome.',
      "I've got a spreadsheet for that.",
      'Slow is smooth. Smooth is fast.',
      "Let's not do anything clever today."
    ],
    replies: [
      'Of course you did.',
      "That's the most Miles thing you've ever said.",
      'Fine. Fine! Check it again.'
    ]
  },
  2: {
    name: 'Priya',
    full: 'Priya Raman',
    title: 'Desk 3 — the quick one',
    bio: 'Youngest on the floor and impossible to slow down. Reads faster than she talks and talks fast. Treats every quiet stretch as a personal insult. Beat Gus at chess once and has not stopped mentioning it.',
    trait: 'impatient',
    lines: [
      'Still 1–0 me, Gus. Just saying.',
      "Anything? Anything at all?",
      "I'm not bored, you're bored.",
      'Come on, come on, come on.',
      'I could have read four things by now.'
    ],
    replies: [
      'It was one game, Priya.',
      'Breathe. Just try breathing.',
      'You are extremely bored.'
    ]
  },
  3: {
    name: 'Gus',
    full: 'Gus Halvorsen',
    title: 'Desk 4 — seen it before',
    bio: 'Lived through three crashes and describes all of them as "a bit choppy". Deadpan to the point where people check if he is joking. He usually is. Drinks coffee that could strip paint and claims it helps him stay calm.',
    trait: 'deadpan',
    lines: [
      "Seen worse. Much worse.",
      'This coffee is technically a solvent.',
      "In '08 this would've been a Tuesday.",
      'Patience is free. Everything else costs.',
      'Wake me if the building catches fire.'
    ],
    replies: [
      'Here we go. The eighties again.',
      'That is not a comforting story, Gus.',
      'You say that every single day.'
    ]
  },
  4: {
    name: 'June',
    full: 'June Park',
    title: 'Desk 5 — the quiet one',
    bio: 'Night owl who does her best thinking after everyone else has gone home. Speaks rarely and precisely. Keeps a small notebook nobody has ever been allowed to read. Waters everyone else\'s plants without being asked.',
    trait: 'methodical',
    lines: [
      '…',
      'Your plant was dying. I fixed it.',
      "I'll note it down.",
      'Mm.',
      'Everything in order.'
    ],
    replies: [
      'Thanks, June.',
      'She wrote it down. It\'s official now.',
      'What IS in that notebook?'
    ]
  },
  5: {
    name: 'Cy',
    full: 'Cy Ferraro',
    title: 'Desk 6 — the optimist',
    bio: 'Came from sales and never entirely left. Could talk a wall into moving. Genuinely, relentlessly cheerful, which the rest of the floor finds either delightful or unbearable depending on the hour.',
    trait: 'relentlessly upbeat',
    lines: [
      "Good day for it! Whatever 'it' is.",
      'Team meeting? No? Just me then.',
      "I'm feeling good about this. I'm always feeling good.",
      'Anyone want to hear an idea? Anyone?',
      "That's the spirit! Nobody said anything, but still."
    ],
    replies: [
      'It is 6am, Cy.',
      'Nobody wants to hear the idea.',
      'How are you like this already?'
    ]
  },
  6: {
    name: 'Wren',
    full: 'Wren Abbott',
    title: 'Desk 7 — ex-engineer',
    bio: 'Built bridges before she built models and still thinks in load and tolerance. Fixes the printer, the chairs, and the coffee machine without being asked. Dry enough that people miss the joke entirely.',
    trait: 'dry',
    lines: [
      'Fixed the chair. Nobody noticed. Typical.',
      "That noise? That's tolerable. Barely.",
      'Everything holds until it does not.',
      "I could rebuild that, you know.",
      'Structurally, this floor is fine. Emotionally, unclear.'
    ],
    replies: [
      'Thanks, Wren.',
      'Was that a joke? I can never tell.',
      'Please do not rebuild the coffee machine again.'
    ]
  }
};

/** Named staff outside the watchlist desks. */
export const STAFF = {
  eva: {
    name: 'Eva',
    full: 'Eva',
    title: 'The trading bot',
    bio: 'The system itself. Runs the scan loop, sizes the trades, and manages every position to its stop or target. Everyone else in this building is a way of looking at what Eva is doing.',
    lines: ['Scanning.', 'Nothing qualifies yet.', 'Watching the zones.'],
    replies: ['Understood.']
  },
  risk: {
    name: 'Margo',
    full: 'Marguerite Vance',
    title: 'Risk',
    bio: 'Compliance lifer who has told more people "no" than anyone in the building and lost precisely zero sleep over it. Holds the earnings blackout and the weekly win-rate breaker. Immovable on both.',
    trait: 'immovable',
    lines: [
      'The answer is no. Ask me again tomorrow.',
      'Rules exist because of days like this.',
      "I don't make the gates. I just hold them."
    ],
    replies: ['Worth a try.', "She's not going to budge."]
  },
  barista: {
    name: 'Sal',
    full: 'Sal Moreno',
    title: 'The Corner Cup',
    bio: 'Pulls every shot in town and hears every conversation twice — once when it happens and once when someone comes back to complain about it. Keeps a corkboard behind the bar. Says nothing, writes everything down.',
    trait: 'hears everything',
    lines: [
      'Board\'s filling up again.',
      'Same order? Thought so.',
      'I hear things. I write them down.',
      'You look like you need a large one.',
      'Somebody pinned another one this morning.'
    ],
    replies: ['Sal knows.', 'Put it on the board, Sal.', 'Thanks Sal.']
  },
  mechanic: {
    name: 'Otis',
    full: 'Otis Grady',
    title: 'Maintenance',
    bio: 'Keeps the lights on and the process running. Talks to the server racks more than to people, and the racks have never once argued back. Runs the morning and hourly checks.',
    trait: 'practical',
    lines: [
      'Racks are humming. All good.',
      'Checked it. Twice.',
      'She runs, or I find out why.'
    ],
    replies: ['Nice one, Otis.', 'Thanks for keeping it up.']
  },
  archivist: {
    name: 'Della',
    full: 'Della Okonkwo',
    title: 'Archive Studio — research',
    bio: 'Finds the primary source before anyone writes a word about it. Keeps the idea wall stocked with photos and background. Hands everything to Priya before a script counts as verified.',
    trait: 'exacting',
    lines: [
      'Found the photo. Checking the rights.',
      'Pinned another one to the wall.',
      'This is Priya’s to check now.',
      'Sourcing the next one.'
    ],
    replies: ['Della found it.', 'Good catch.']
  },
  crypto: {
    name: 'Nix',
    full: 'Nix Adeyemi',
    title: 'The Crypto Desk — BTC, 24/7',
    bio: 'Works the only desk in the building with no closing bell. Trades one position at a time on a deliberately tiny book, and is more proud of the trades she talks herself out of than the ones she takes. Keeps the kill switch taped where she can reach it.',
    trait: 'unsleeping',
    lines: [
      'Crypto does not care what time it is.',
      'Small size is why I can sleep. Sometimes.',
      'Not chasing that. It is already extended.',
      'One position. That is the whole rule.',
      'Flat is a position too.'
    ],
    replies: ['Nix is still up.', 'Good discipline.']
  },
  factchecker: {
    name: 'Iris',
    full: 'Iris Faraday',
    title: 'Archive Studio — fact-check',
    bio: 'Verifies every claim in a script against a real, citable source before it counts as done. Her desk has sat next to the writers’ room since the room was built; nobody worked it until now.',
    trait: 'exacting',
    lines: [
      'Two sources or it does not go in.',
      'That date is wrong. I checked.',
      'Verified. Moving to the next claim.',
      'Not confident enough yet — hold it.'
    ],
    replies: ['Priya caught it.', 'Good catch.']
  },
  writer: {
    name: 'Nell',
    full: 'Nell Halloway',
    title: 'Archive Studio — scripts',
    bio: 'Writes the outlines and the scripts. Believes a documentary lives or dies on its cold open and that named people carry a story further than any thesis does.',
    trait: 'structural',
    lines: [
      'Start with one place and one year.',
      'Names carry it. Not arguments.',
      'The turn needs a date on it.',
      'Draft saved.'
    ],
    replies: ['Read the draft.', 'That opening works.']
  },
  editor: {
    name: 'Rafa',
    full: 'Rafael Duarte',
    title: 'Archive Studio — cut and packaging',
    bio: 'Owns the shot list through to the thumbnail. Cuts to the narration, not the other way round, and will re-crop or re-time an image rather than let it drift from what’s actually being said. Has opinions about titles that he is usually right about.',
    trait: 'decisive',
    lines: [
      'Cut is locked.',
      'That image lands a beat late — fixing it.',
      'Needs a stronger thumbnail.',
      'Rendering.'
    ],
    replies: ['Ship it.', 'Rafa is right.']
  },
  atmops: {
    name: 'Wes',
    full: 'Wes',
    title: "Sage's ATM Co. — launch checklist",
    bio: 'Careful with money that is not his to be careless with. Measures a storefront twice before he says a word about it out loud. Keeps every real number in one notebook and will not guess at the rest.',
    trait: 'methodical',
    lines: [
      'Still just the six steps. No shortcuts.',
      'Measured the corner again. Numbers still hold.',
      'One real step at a time.',
      'Not signing anything I have not read twice.',
      'The plan is the plan until something real changes it.'
    ],
    replies: ['Slow is fine, Wes.', 'That is very on brand for you.', 'Careful is good, here.']
  },
  doctor1: {
    name: 'Dr. Ahn',
    full: 'Dr. Soo-jin Ahn',
    title: 'Smallville General — attending',
    bio: 'Drives in from clear across town every morning and has never once complained about it out loud. Reads the whole chart before she says a word to anyone.',
    trait: 'exacting',
    lines: [
      'Long drive. Worth it for the quiet.',
      'Chart first, opinions after.',
      'Everything is stable. For now.',
      'I will believe it when I have checked it myself.'
    ],
    replies: ['Trust the chart, I suppose.', 'That drive would wear on anyone.', 'Fair enough, doctor.']
  },
  doctor2: {
    name: 'Dr. Reyes',
    full: 'Dr. Marco Reyes',
    title: 'Smallville General — attending',
    bio: 'Leaves it all at the door on the way out, or says he does. The car radio is apparently the whole secret. Easy to talk to, harder to read.',
    trait: 'warm',
    lines: [
      'Made it in. Radio helped.',
      'Quiet shift so far. Do not jinx it.',
      'Ask me again after the drive home.',
      'Everyone here is in good hands, for what it is worth.'
    ],
    replies: ['Same here, honestly.', 'That commute would break me.', 'Good to hear, doctor.']
  },
  bull: {
    name: 'Bull',
    full: 'Bull',
    title: 'The News Desk — anchor',
    bio: 'Reads every number like it is the best number anyone has ever reported. Owns a treadmill desk he has never once used standing up. Genuinely believes tomorrow is going to be great, and says so, on air, constantly.',
    trait: 'relentlessly upbeat',
    lines: [
      "It's a BEAUTIFUL day on the desk.",
      'Every win counts.',
      "I'll take it.",
      'Back in thirty, folks.',
      'Bear, say something nice. Just once.'
    ],
    replies: ['Bear is never going to say something nice.', 'That is the spirit, Bull.', 'Somebody has to believe it.']
  },
  bear: {
    name: 'Bear',
    full: 'Bear',
    title: 'The News Desk — anchor',
    bio: 'Reads the same numbers as Bull and finds a way to sound unimpressed by all of them. Keeps a running tally of every time Bull has said "beautiful day." It is a large number.',
    trait: 'dry, sarcastic',
    lines: [
      'Shockingly.',
      '...for once.',
      'Try to contain your excitement.',
      'Bar is low tonight.',
      "That's generous phrasing, Bull."
    ],
    replies: ['Bear is not wrong, usually.', 'Somebody has to say it.', 'Every single broadcast.']
  },
  voss: {
    name: 'Voss',
    full: 'Voss',
    title: 'The Field Office — security',
    bio: 'Says "routine check" about everything, including the coffee machine. Nobody has ever seen an actual incident report leave this building. Believes that is the point.',
    trait: 'unreadable',
    lines: [
      'Routine check.',
      'Nothing to report. As usual.',
      'Noted.',
      "I'm not saying it's suspicious. I'm saying I wrote it down.",
      'Ito, log it.'
    ],
    replies: ['Log what, Voss?', 'There is never anything to report.', 'Understood, I think.']
  },
  ito: {
    name: 'Ito',
    full: 'Ito',
    title: 'The Field Office — security',
    bio: 'Keeps the actual notes, since Voss just says "noted" and moves on. Has a corkboard nobody is allowed to look at directly. Genuinely enjoys the paperwork.',
    trait: 'thorough',
    lines: [
      'Cross-referencing.',
      'Filed. Properly, this time.',
      'The board says otherwise, Voss.',
      'Everything checks out. Again.',
      'I like the paperwork. Sue me.'
    ],
    replies: ['Nobody doubts the paperwork, Ito.', 'The board is a menace.', 'Thorough as always.']
  },
  marnie: {
    name: 'Marnie',
    full: 'Marnie',
    title: 'The Bank — teller',
    bio: 'Balances her own checkbook to the penny and calls it a professional habit. Reads the equity curve the way other people read a weather report -- once in the morning, no comment either way.',
    trait: 'exact',
    lines: [
      'The numbers are the numbers.',
      'Balanced. As always.',
      "I don't round up. Ever.",
      'Checked it twice. It still says what it said.',
      'A penny is still a real number.'
    ],
    replies: ['Marnie would know.', 'Exactly to the penny, apparently.', 'Nobody argues with the ledger.']
  },
  percy: {
    name: 'Percy',
    full: 'Percy',
    title: 'The Tax Office — records',
    bio: 'Keeps a real shoebox of real receipts and insists a shoebox is a filing system. Says "not tax advice" so often it has become a kind of greeting.',
    trait: 'careful, disclaims everything',
    lines: [
      'Not tax advice. Just the numbers.',
      'Filed. Ask a real professional about the rest.',
      "That's a record, not a recommendation.",
      'Every receipt, every time.',
      'The shoebox system has never failed me.'
    ],
    replies: ['Percy says that about everything.', 'Fair enough, Percy.', 'The shoebox again?']
  },
  predict: {
    name: 'Fay',
    full: 'Fay',
    title: 'The Prediction Desk',
    bio: "Every contract on her board settles at exactly $0 or $1 -- nothing in between, no partial credit. She has carried that over into how she talks: a thing is either true or it isn't yet, and she will not round up a maybe into a yes. Pulls a fresh snapshot only when asked and says exactly how old the last one is.",
    trait: 'unsentimental',
    lines: [
      'Settles at zero or one. Never in between.',
      'That number is only as fresh as the last pull.',
      "I don't guess at odds I haven't priced.",
      "Ask and I'll pull a real one. Until then, that's yesterday's.",
      'A maybe is not a yes.'
    ],
    replies: ['Fay would never round that up.', 'Fair. Get a fresh pull first.', 'That is very Fay.']
  },
  milo: {
    name: 'Milo',
    full: 'Milo',
    title: 'Park regular',
    bio: 'Walks the same loop around the pond every day, rain or shine, and has strong unsolicited opinions about which bench gets the best afternoon light. Knows every dog in town by name and most people by their dog.',
    trait: 'restless',
    lines: [
      'Same loop, same ducks, same opinions.',
      "That bench is overrated. Everyone's wrong about that bench.",
      'Good walking weather, this.',
      'Saw a dog I didn\'t recognize. Unsettling.'
    ],
    replies: ['Milo has thoughts on this.', 'Here we go again.', 'The bench discourse continues.']
  },
  nadia: {
    name: 'Nadia',
    full: 'Nadia',
    title: 'Park regular',
    bio: 'Claims the same bench by the pond most afternoons and watches the town go by without much comment. People-watching, she says, beats most TV. Keeps a paperback she never seems to get further than halfway through.',
    trait: 'observant',
    lines: [
      'Same page as yesterday. No rush.',
      'People-watching. Better than most TV.',
      'That one\'s new around here.',
      'Quiet bench, loud town.'
    ],
    replies: ['Nadia sees everything.', 'Still on that page, huh.', 'Fair assessment, honestly.']
  },
  reed: {
    name: 'Reed',
    full: 'Reed',
    title: 'Hangs around the General Store',
    bio: 'Never seems to actually buy anything, just leans by the entrance and talks to whoever walks in or out. Knows the store\'s whole inventory better than the people who work there, somehow.',
    trait: 'chatty',
    lines: [
      'They restocked. Finally.',
      'You want the good ones, they\'re in the back.',
      'Just here. Just talking.',
      'Told the owner that shelf was crooked. Still crooked.'
    ],
    replies: ['Reed knows the inventory cold.', 'Does he even work here?', 'Classic Reed.']
  },
  theo: {
    name: 'Theo',
    full: 'Theo',
    title: 'The Outskirts',
    bio: 'Moved out this way for the quiet and has no complaints about the commute, mostly because there isn\'t one. Spends a lot of time fixing things that were not really broken.',
    trait: 'unhurried',
    lines: [
      'Quiet out here. I like that.',
      'Fixed the fence. It was fine already.',
      "Don't miss downtown much, honestly.",
      'Plenty of room to spread out.'
    ],
    replies: ['Theo\'s got the space for it.', 'That fence was fine, Theo.', 'Can\'t argue with the quiet.']
  },
  greta: {
    name: 'Greta',
    full: 'Greta',
    title: 'The Outskirts',
    bio: 'Keeps the biggest garden on this side of town and will tell you about it at length, whether you asked or not. Knows every neighbor who hasn\'t moved in yet.',
    trait: 'proud, chatty',
    lines: [
      'Tomatoes are coming in early this year.',
      'Still a couple empty lots down the road. Good houses, though.',
      'You should see the garden right now.',
      'Plenty of room out here still.'
    ],
    replies: ['Greta\'s tomatoes again.', 'She would know, she\'s out there every day.', 'Fair point about the lots.']
  },
  oscar: {
    name: 'Oscar', full: 'Oscar', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'quiet',
    lines: ["Morning.", "Another day out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  lena: {
    name: 'Lena', full: 'Lena', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'friendly',
    lines: ["Nice enough day for it.", "Can't complain."],
    replies: ['Fair enough.', 'Same to you.']
  },
  hugo: {
    name: 'Hugo', full: 'Hugo', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'busy',
    lines: ["Keeping busy.", "Same as always."],
    replies: ['Fair enough.', 'Same to you.']
  },
  mira: {
    name: 'Mira', full: 'Mira', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'tired',
    lines: ["Long week.", "Nearly the weekend."],
    replies: ['Fair enough.', 'Same to you.']
  },
  dex: {
    name: 'Dex', full: 'Dex', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'cheerful',
    lines: ["Good to see a new face.", "Don't get many out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  paloma: {
    name: 'Paloma', full: 'Paloma', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'gruff',
    lines: ["Heading out, heading back.", "That's about it."],
    replies: ['Fair enough.', 'Same to you.']
  },
  arlo: {
    name: 'Arlo', full: 'Arlo', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'curious',
    lines: ["Quiet block, this one.", "Suits me fine."],
    replies: ['Fair enough.', 'Same to you.']
  },
  sable: {
    name: 'Sable', full: 'Sable', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'reserved',
    lines: ["Seen worse days.", "Seen better too."],
    replies: ['Fair enough.', 'Same to you.']
  },
  finn: {
    name: 'Finn', full: 'Finn', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'warm',
    lines: ["Settling in alright.", "Still unpacking, honestly."],
    replies: ['Fair enough.', 'Same to you.']
  },
  juno: {
    name: 'Juno', full: 'Juno', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'brisk',
    lines: ["Nothing much to report.", "Same as yesterday."],
    replies: ['Fair enough.', 'Same to you.']
  },
  rhea: {
    name: 'Rhea', full: 'Rhea', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'quiet',
    lines: ["Morning.", "Another day out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  soren: {
    name: 'Soren', full: 'Soren', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'friendly',
    lines: ["Nice enough day for it.", "Can't complain."],
    replies: ['Fair enough.', 'Same to you.']
  },
  ivy: {
    name: 'Ivy', full: 'Ivy', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'busy',
    lines: ["Keeping busy.", "Same as always."],
    replies: ['Fair enough.', 'Same to you.']
  },
  mateo: {
    name: 'Mateo', full: 'Mateo', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'tired',
    lines: ["Long week.", "Nearly the weekend."],
    replies: ['Fair enough.', 'Same to you.']
  },
  celia: {
    name: 'Celia', full: 'Celia', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'cheerful',
    lines: ["Good to see a new face.", "Don't get many out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  dash: {
    name: 'Dash', full: 'Dash', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'gruff',
    lines: ["Heading out, heading back.", "That's about it."],
    replies: ['Fair enough.', 'Same to you.']
  },
  wylie: {
    name: 'Wylie', full: 'Wylie', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'curious',
    lines: ["Quiet block, this one.", "Suits me fine."],
    replies: ['Fair enough.', 'Same to you.']
  },
  noor: {
    name: 'Noor', full: 'Noor', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'reserved',
    lines: ["Seen worse days.", "Seen better too."],
    replies: ['Fair enough.', 'Same to you.']
  },
  bram: {
    name: 'Bram', full: 'Bram', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'warm',
    lines: ["Settling in alright.", "Still unpacking, honestly."],
    replies: ['Fair enough.', 'Same to you.']
  },
  tamsin: {
    name: 'Tamsin', full: 'Tamsin', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'brisk',
    lines: ["Nothing much to report.", "Same as yesterday."],
    replies: ['Fair enough.', 'Same to you.']
  },
  zane: {
    name: 'Zane', full: 'Zane', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'quiet',
    lines: ["Morning.", "Another day out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  odette: {
    name: 'Odette', full: 'Odette', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'friendly',
    lines: ["Nice enough day for it.", "Can't complain."],
    replies: ['Fair enough.', 'Same to you.']
  },
  cole: {
    name: 'Cole', full: 'Cole', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'busy',
    lines: ["Keeping busy.", "Same as always."],
    replies: ['Fair enough.', 'Same to you.']
  },
  freya: {
    name: 'Freya', full: 'Freya', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'tired',
    lines: ["Long week.", "Nearly the weekend."],
    replies: ['Fair enough.', 'Same to you.']
  },
  enzo: {
    name: 'Enzo', full: 'Enzo', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'cheerful',
    lines: ["Good to see a new face.", "Don't get many out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  marisol: {
    name: 'Marisol', full: 'Marisol', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'gruff',
    lines: ["Heading out, heading back.", "That's about it."],
    replies: ['Fair enough.', 'Same to you.']
  },
  kai: {
    name: 'Kai', full: 'Kai', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'curious',
    lines: ["Quiet block, this one.", "Suits me fine."],
    replies: ['Fair enough.', 'Same to you.']
  },
  thalia: {
    name: 'Thalia', full: 'Thalia', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'reserved',
    lines: ["Seen worse days.", "Seen better too."],
    replies: ['Fair enough.', 'Same to you.']
  },
  dmitri: {
    name: 'Dmitri', full: 'Dmitri', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'warm',
    lines: ["Settling in alright.", "Still unpacking, honestly."],
    replies: ['Fair enough.', 'Same to you.']
  },
  elsie: {
    name: 'Elsie', full: 'Elsie', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'brisk',
    lines: ["Nothing much to report.", "Same as yesterday."],
    replies: ['Fair enough.', 'Same to you.']
  },
  rowan: {
    name: 'Rowan', full: 'Rowan', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'quiet',
    lines: ["Morning.", "Another day out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  vesna: {
    name: 'Vesna', full: 'Vesna', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'friendly',
    lines: ["Nice enough day for it.", "Can't complain."],
    replies: ['Fair enough.', 'Same to you.']
  },
  lior: {
    name: 'Lior', full: 'Lior', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'busy',
    lines: ["Keeping busy.", "Same as always."],
    replies: ['Fair enough.', 'Same to you.']
  },
  bianca: {
    name: 'Bianca', full: 'Bianca', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'tired',
    lines: ["Long week.", "Nearly the weekend."],
    replies: ['Fair enough.', 'Same to you.']
  },
  caspian: {
    name: 'Caspian', full: 'Caspian', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'cheerful',
    lines: ["Good to see a new face.", "Don't get many out here."],
    replies: ['Fair enough.', 'Same to you.']
  },
  ingrid: {
    name: 'Ingrid', full: 'Ingrid', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'gruff',
    lines: ["Heading out, heading back.", "That's about it."],
    replies: ['Fair enough.', 'Same to you.']
  },
  mo: {
    name: 'Mo', full: 'Mo', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'curious',
    lines: ["Quiet block, this one.", "Suits me fine."],
    replies: ['Fair enough.', 'Same to you.']
  },
  sunny: {
    name: 'Sunny', full: 'Sunny', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'reserved',
    lines: ["Seen worse days.", "Seen better too."],
    replies: ['Fair enough.', 'Same to you.']
  },
  petra: {
    name: 'Petra', full: 'Petra', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'warm',
    lines: ["Settling in alright.", "Still unpacking, honestly."],
    replies: ['Fair enough.', 'Same to you.']
  },
  dario: {
    name: 'Dario', full: 'Dario', title: 'The Eastside',
    bio: 'Lives out on the Eastside. One of the newer houses past the old edge of town.',
    trait: 'brisk',
    lines: ["Nothing much to report.", "Same as yesterday."],
    replies: ['Fair enough.', 'Same to you.']
  },
  dana: {
    name: 'Dana',
    full: 'Dana',
    title: 'Smallville Regional — gate agent',
    bio: "Checks the real board before saying anything about it, every time -- burned once by a connecting passenger who trusted a screen that hadn't refreshed. Won't call a search result a booking just because somebody wants it to be one.",
    trait: 'exacting',
    lines: [
      'Board says what the board says.',
      "That's a search, not a ticket.",
      'Checked it twice. Still empty.',
      'I\'ll believe it when there\'s a confirmation number.'
    ],
    replies: ['Dana would check twice.', 'Fair point, Dana.', 'That is exactly her job.']
  }
};

export function personFor(def) {
  if (def.slot != null) return PEOPLE[def.slot] || null;
  return STAFF[def.id] || null;
}
