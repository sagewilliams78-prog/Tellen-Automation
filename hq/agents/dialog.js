/**
 * Conversation topics and reactions.
 *
 * The old model picked a line and a reply from two independent random pools,
 * so exchanges came out as non-sequiturs:
 *
 *     Rosa:  "Pen's still lucky. Don't touch it."
 *     Miles: "I've got a spreadsheet for that."
 *
 * Two changes fix that:
 *
 *  1. TOPICS -- a conversation now has a subject. The opener and the reply are
 *     drawn from the SAME topic, so they answer each other.
 *  2. REACTIONS -- reply *forms* (agree / tease / ask / deflect) rather than
 *     free-standing statements. These read as responses after almost any line,
 *     which is what lets a character's signature line still get a sane answer.
 *
 * Topic choice is driven by where people are standing, so the room they are in
 * shapes what they talk about.
 *
 * The honesty rule from banter.js still holds everywhere in this file: no
 * market claims, no prices, no P&L, no predictions. Real information is the
 * status bubble's job. This is small talk.
 */

/** Subjects, each a self-contained exchange. */
export const TOPICS = {
  coffee: {
    opens: [
      'Who made this pot? It tastes like a dare.',
      'Third coffee. Judge me later.',
      "I'm switching to decaf. Starting tomorrow.",
      'We need a better kettle.'
    ],
    replies: [
      'You say that every week.',
      'Pour me one while you are up.',
      'It is not the kettle, it is the beans.',
      'Decaf. Sure.'
    ]
  },
  quiet: {
    opens: [
      'Quiet in here today.',
      'Too quiet. It makes me itch.',
      'You can hear the lights buzzing.',
      'Nobody has said a word in an hour.'
    ],
    replies: [
      'Quiet is fine by me.',
      'Do not jinx it.',
      'I was enjoying that, actually.',
      'Give it ten minutes.'
    ]
  },
  work: {
    opens: [
      'I checked it twice. Then a third time.',
      'Nearly finished the thing from this morning.',
      'Remind me why we do it this way?',
      'I am going to redo that properly tomorrow.'
    ],
    replies: [
      'Twice is usually enough.',
      'Show me when it is done.',
      'Because it worked once and nobody argued.',
      'Write it down before you forget.'
    ]
  },
  tired: {
    opens: [
      'I am running on about four hours.',
      'Long one today.',
      'My eyes have gone square.',
      'Is it only Tuesday?'
    ],
    replies: [
      'Go home. Properly, I mean.',
      'Take the long way back, it helps.',
      'Every week feels like Tuesday.',
      'Sit down for five minutes.'
    ]
  },
  food: {
    opens: [
      'Somebody has left a sandwich in the fridge since Monday.',
      'I forgot lunch again.',
      'There are biscuits if anyone wants them.',
      'What is that smell? Is that fish?'
    ],
    replies: [
      'That was not me.',
      'You always forget lunch.',
      'Say no more, I am coming.',
      'I am throwing it out, I have decided.'
    ]
  },
  weather: {
    opens: [
      'Nice out, for once.',
      'It is going dark early now.',
      'Bit cold to be standing about.',
      'I could stay out here all evening.'
    ],
    replies: [
      'Make the most of it.',
      'It always does this time of year.',
      'Then go inside.',
      'Five more minutes.'
    ]
  },
  home: {
    opens: [
      'I keep meaning to sort this place out.',
      'The neighbours were up half the night.',
      'Nothing on. Absolutely nothing.',
      'I might just have an early one.'
    ],
    replies: [
      'You said that last month.',
      'Knock on their door then.',
      'Put something on in the background.',
      'Good. You have earned it.'
    ]
  },
  studio: {
    opens: [
      'The archive footage is a mess to search.',
      'That interview needs one more pass.',
      'I keep second-guessing the opening line.',
      'We should log the sources properly this time.'
    ],
    replies: [
      'Tag it as you go, it saves hours later.',
      'Read it out loud, you will hear it.',
      'The opening is always the last thing to land.',
      'Agreed. Do it while it is fresh.'
    ]
  },

  // ---- expanded set: 42 more subjects, so the town has somewhere to go
  // besides the same eight loops. Still small talk -- no market claims, no
  // prices, no predictions, same rule as the original eight.

  atm: {
    opens: [
      'That storefront by the pond still has nobody in it.',
      'Wes was out there again, just looking at the wall.',
      'Funny thing to build before there is even a machine in it.',
      'I still cannot picture where the machine actually goes.'
    ],
    replies: [
      'Give it time, it is still just a plan.',
      'He seems to like the quiet, honestly.',
      'Better to have the room than scramble for one later.',
      'North corner, probably. That is where I would put it.'
    ]
  },
  small_business: {
    opens: [
      'Ever think about starting something on the side?',
      'Everyone I know has some idea they are sitting on.',
      'It is the paperwork that puts me off, not the idea.',
      'I keep meaning to write mine down properly.'
    ],
    replies: [
      'Write it down before you talk yourself out of it.',
      'The paperwork is the boring part everyone skips.',
      'Half the town is sitting on an idea like that.',
      'Do it small first. See if it even holds up.'
    ]
  },
  weekend: {
    opens: [
      'Any plans for the weekend, or just recovering?',
      'I have absolutely nothing on, for once.',
      'Two days is never enough.',
      'I am doing precisely nothing and I am thrilled about it.'
    ],
    replies: [
      'Nothing sounds like the correct plan.',
      'Ask me again Sunday night, I will have wasted it.',
      'Enjoy it. Monday finds you either way.',
      'Same. Absolutely nothing, and proud of it.'
    ]
  },
  commute: {
    opens: [
      'The walk in was nice this morning, actually.',
      'I keep taking the long way round without meaning to.',
      'Forgot my umbrella and paid for it.',
      'Same walk every day and I still notice something new.'
    ],
    replies: [
      'The long way is usually the better one.',
      'That is what the awning outside the cafe is for.',
      'That is the trick, apparently. Keep noticing things.',
      'Small mercies. At least it is not raining now.'
    ]
  },
  traffic: {
    opens: [
      'Somebody was really moving on the main road earlier.',
      'The crossing by the studio gets busy around now.',
      'I swear the same car goes past three times a day.',
      'Nearly stepped out without looking. Bad habit.'
    ],
    replies: [
      'People always speed up right before the corner.',
      'It is the shortcut, everyone uses it.',
      'Maybe it is circling for parking.',
      'Look twice. Always. Habit or not.'
    ]
  },
  lake: {
    opens: [
      'The lake was dead still this morning.',
      'Someone was skimming stones out there again.',
      'I could sit by the water all afternoon, given the chance.',
      'The ducks have got very bold lately.'
    ],
    replies: [
      'Best spot in the whole park, honestly.',
      'Bet they never once make it skip properly.',
      'Nobody is stopping you. Go sit.',
      'They know exactly who feeds them.'
    ]
  },
  park: {
    opens: [
      'The flowers by the path are doing well this year.',
      'Somebody left a bench absolutely covered in crumbs.',
      'I sat outside for ten minutes and forgot to go back in.',
      'The grass finally dried out after all that rain.'
    ],
    replies: [
      'Ten minutes turns into thirty, every time.',
      'That will be the birds. Or the squirrels.',
      'Small mercies. It was a swamp out there.',
      'They have looked good all week, actually.'
    ]
  },
  dogs: {
    opens: [
      "Sage's two came tearing past here earlier.",
      'One of the dogs stopped and just stared at me for a full minute.',
      'They never seem to run out of energy, those two.',
      'I swear the smaller one is faster than the other.'
    ],
    replies: [
      'They do that. Ignore it and they lose interest.',
      'Somebody is feeding them well, clearly.',
      'I would not keep up with either of them for long.',
      'The little one always has something to prove.'
    ]
  },
  sage: {
    opens: [
      'Saw the owner heading down by the lake earlier.',
      'She actually stopped and said something to me this morning.',
      'Her house looks like it gets the best light in town.',
      'Still cannot get over her building that place herself.'
    ],
    replies: [
      'She is around more than you would think.',
      'Nice when someone actually notices you are there.',
      'North light, probably. Lucky spot.',
      'Somebody has to make the calls, I suppose.'
    ]
  },
  gossip: {
    opens: [
      'Did you hear about the mix-up over at the cafe?',
      'Someone said the corridor upstairs was locked all morning.',
      'I heard third-hand and it was already wrong twice.',
      'Nobody actually knows, they just enjoy saying it.'
    ],
    replies: [
      'By the time it reaches me it is unrecognisable.',
      'Ask Sal. She hears everything eventually.',
      'That sounds exactly like something that never happened.',
      'I stopped repeating things after the last one.'
    ]
  },
  plants: {
    opens: [
      'My plant finally forgave me for last month.',
      'Somebody keeps watering the office plant and it is not me.',
      'I bought another one I definitely do not have room for.',
      'The one on the windowsill is somehow thriving on neglect.'
    ],
    replies: [
      'Some of them just want to be left alone.',
      'Whoever it is, thank them for me too.',
      'There is always room for one more.',
      'That is the secret, apparently. Ignore them.'
    ]
  },
  tech: {
    opens: [
      'My charger cable finally gave up this week.',
      'Does anyone actually read the update notes?',
      'I still cannot find half the settings on this thing.',
      'Lost an afternoon to a cable that was not even plugged in.'
    ],
    replies: [
      'Nobody reads those. Ever.',
      'They are usually hiding under something obvious.',
      'Classic. Happens to everyone eventually.',
      'Buy two next time. Always buy two.'
    ]
  },
  news: {
    opens: [
      'Did you catch anything in the paper this morning?',
      'Somebody mentioned something happening downtown, no idea what.',
      'I have stopped reading the news before coffee. Bad idea.',
      'Everyone seems to know more than me about everything lately.'
    ],
    replies: [
      'Wise. Coffee first, always.',
      'It will still be there after lunch.',
      'Half of it is nothing by the time it reaches here.',
      'Or they are all making it up. Hard to tell.'
    ]
  },
  shopping: {
    opens: [
      'I went out for one thing and came back with six.',
      'The shelves were bare this week, of all things.',
      'I keep forgetting the one item I actually needed.',
      'Somebody needs to invent a list that reminds itself.'
    ],
    replies: [
      'That is how it always goes.',
      'Try again Tuesday, restock day I think.',
      'Write it on your hand. Works for me.',
      'I would buy that, honestly.'
    ]
  },
  sleep: {
    opens: [
      'I was wide awake at four for no reason at all.',
      'Slept like a log, first time in weeks.',
      'The neighbours again. Half two, like clockwork.',
      'I keep meaning to go to bed earlier. Keep failing.'
    ],
    replies: [
      'No reason is the worst reason.',
      'Enjoy it while it lasts.',
      'Say something. Politely, but say something.',
      'We all keep meaning to.'
    ]
  },
  exercise: {
    opens: [
      'Went for a walk at lunch, actually made it round the whole park.',
      'I keep saying I will start running. Keep not starting.',
      'My legs are letting me know about yesterday.',
      'Ten minutes of stretching and I already feel smug.'
    ],
    replies: [
      'That counts. Do not let anyone tell you otherwise.',
      'Tomorrow. It is always tomorrow.',
      'That will teach you.',
      'Smug is a good look on you.'
    ]
  },
  hobbies: {
    opens: [
      'Picked the guitar back up after months of nothing.',
      'I have three unfinished projects and started a fourth.',
      'Found an old sketchbook, most of it is terrible.',
      'Spent the whole evening on something completely useless and loved it.'
    ],
    replies: [
      'Better late than never.',
      'That is basically everyone I know.',
      'Terrible is how it starts for all of us.',
      'Useless is underrated, honestly.'
    ]
  },
  neighbors: {
    opens: [
      'The people next door had music going half the night.',
      'Somebody borrowed my ladder and I have genuinely no idea who.',
      'The corridor smells like something new every week.',
      'I waved at the wrong window again this morning.'
    ],
    replies: [
      'Knock and ask. Cannot hurt.',
      'It always turns up eventually. Usually broken.',
      'I do not want to know, honestly.',
      'Happens to all of us at least once.'
    ]
  },
  parking: {
    opens: [
      'Somebody parked right across the whole space again.',
      'Took me three laps to find anywhere at all today.',
      'I left mine miles away just to be safe.',
      'The spot by the door was actually free for once.'
    ],
    replies: [
      'Every single week, like clockwork.',
      'It is never that bad, and then suddenly it is.',
      'Better safe than boxed in.',
      'Do not get used to it.'
    ]
  },
  mail: {
    opens: [
      'A parcel has been sat by the door for two days now.',
      'I am still waiting on something that was meant to arrive Monday.',
      "Got someone else's post again. Third time this month.",
      'Nothing but bills, as usual.'
    ],
    replies: [
      'That will be mine, probably. Thank you.',
      'It will turn up whenever it wants to.',
      'Send it back round, they will notice eventually.',
      'They always are, somehow.'
    ]
  },
  streaming: {
    opens: [
      'Started something last night and now I am three episodes deep.',
      'I cannot find a single thing worth finishing lately.',
      'Somebody spoiled the ending for me before I even started.',
      'Fell asleep halfway through again. Missed the whole point.'
    ],
    replies: [
      'That is how it always happens.',
      'Same. Everything looks the same after a while.',
      'Unforgivable. Truly.',
      'Watch it again. Different this time, I promise.'
    ]
  },
  cooking: {
    opens: [
      'Tried a new recipe last night, went about how you would expect.',
      'I have made the same five meals for years now.',
      'Burned the toast and set off the whole thing. Again.',
      'Somebody left something delicious-smelling in the break room.'
    ],
    replies: [
      'Points for trying, at least.',
      'Nothing wrong with a reliable five.',
      'That thing goes off if you look at it wrong.',
      'Lead me to it.'
    ]
  },
  holidays: {
    opens: [
      'Feels too early to be thinking about it, but here we are.',
      'I still have not decided what to do with the time off.',
      'Everyone keeps asking about plans I do not have yet.',
      'Last one I took, I spent it doing nothing and it was perfect.'
    ],
    replies: [
      'It always creeps up faster than you think.',
      'Decide nothing. Works every time.',
      'Tell them the same thing I tell them. Nothing, thanks.',
      'Nothing is underrated as a plan.'
    ]
  },
  childhood: {
    opens: [
      'Drove past somewhere that reminded me of growing up.',
      'Found an old photo and could not place half the people in it.',
      'My mum used to make that exact same thing, funnily enough.',
      'Some smells just take you straight back, no warning at all.'
    ],
    replies: [
      'That happens more as you get older, I think.',
      'Someone in the family will know, ask around.',
      'Small world, that.',
      'Every single time. No warning at all.'
    ]
  },
  birdwatching: {
    opens: [
      'There is a whole flock of them over the lake this week.',
      'One landed right on the bench next to me, bold as anything.',
      'I could not tell you a single species if you asked.',
      'They have been loud since sunrise, every one of them.'
    ],
    replies: [
      'Means the weather is turning, probably.',
      'They know exactly where the crumbs are.',
      'Nobody can. Do not let it worry you.',
      'That is how you know it is actually spring.'
    ]
  },
  photography: {
    opens: [
      'Tried to get a decent photo of the lake and it came out flat.',
      'Half my old photos are blurry and I still cannot throw them out.',
      'The light around here in the evening is something else.',
      'I keep meaning to actually print some of these out.'
    ],
    replies: [
      'Golden hour, they call it. Worth waiting for.',
      'Blurry ones are still proof it happened.',
      'It really is, especially by the water.',
      'Do it. They just sit on a phone otherwise.'
    ]
  },
  history: {
    opens: [
      'Read something about this town that I never knew before.',
      'Funny how much gets forgotten in one generation.',
      'Somebody should really be writing this stuff down properly.',
      'Old photos of this street look nothing like it does now.'
    ],
    replies: [
      'Somebody usually is, eventually.',
      'Faster than you would think, honestly.',
      'That is the whole job, really.',
      'Everything changes and nobody notices at the time.'
    ]
  },
  writing: {
    opens: [
      'Started keeping a journal again. Third attempt this year.',
      'I write better first thing, before I second-guess it.',
      'Deleted an entire page and started over from nothing.',
      'Somebody should tell me when an idea is actually good.'
    ],
    replies: [
      'Third time is usually the one that sticks.',
      'That is when the good stuff comes out, I find.',
      'Sometimes starting over is the fix.',
      'You will know. Eventually.'
    ]
  },
  games: {
    opens: [
      'Lost at chess again. I am starting to suspect I am just bad at it.',
      'Found an old deck of cards, half of them missing.',
      'Somebody left a puzzle half-finished on the table for a week.',
      'I have never once won at this game and I keep playing anyway.'
    ],
    replies: [
      'Or they are just better than you. Consider it.',
      'Half a deck is still a deck, technically.',
      'Somebody should finish that before it drives me mad.',
      'That is either very stubborn or very admirable.'
    ]
  },
  cars: {
    opens: [
      'Mine made a noise this morning I did not love.',
      'Finally got round to washing it, first time in months.',
      'Somebody left their lights on again, whole street could hear it.',
      'I still cannot parallel park to save my life.'
    ],
    replies: [
      'Get it looked at before it gets worse.',
      'Feels good, does not it. Enjoy it while it lasts.',
      'That will be a flat battery by morning.',
      'Nobody can, do not let them tell you otherwise.'
    ]
  },
  bikes: {
    opens: [
      'Dug the bike out of storage, tyres were flat as anything.',
      'Rode in today instead of walking, made good time.',
      'Somebody nearly took my ear off cycling past.',
      'The chain needs oiling and I keep putting it off.'
    ],
    replies: [
      'Pump is by the door if you need it.',
      'Beats the walk, most days.',
      'They are always in more of a hurry than they need to be.',
      'It will seize up eventually. Do it today.'
    ]
  },
  library: {
    opens: [
      'Finally returned a book I had for way too long.',
      'Picked something up on a whim and could not put it down.',
      'The one I wanted was already out, of course.',
      'I have got a stack by the bed I am never getting through.'
    ],
    replies: [
      'They never even noticed, honestly.',
      'That is the best kind of find.',
      'Put your name down, worth the wait.',
      'Nobody does. It is fine.'
    ]
  },
  puzzles: {
    opens: [
      'Got stuck on the same clue for twenty minutes this morning.',
      'Finished one properly for the first time in ages.',
      'Somebody filled half of it in wrong and left it for the rest of us.',
      'I am hopeless at these and I keep doing them anyway.'
    ],
    replies: [
      'Sleep on it. It always comes to you eventually.',
      'Small victories. Take them.',
      'That is going to bother me all day now.',
      'That is the whole appeal, honestly.'
    ]
  },
  seasons: {
    opens: [
      'You can feel it turning already, if you pay attention.',
      'My allergies have started up right on schedule.',
      'The evenings are drawing in earlier every day now.',
      'First proper warm day of the year, finally.'
    ],
    replies: [
      'Every year, same time, without fail.',
      'Mine too. Like clockwork.',
      'Means the mornings will be worth it soon.',
      'About time. Make the most of it.'
    ]
  },
  wes: {
    opens: [
      'Wes was out measuring the corner of that storefront again.',
      'He does not say much, but he is always out there thinking.',
      'Asked him how it was going. Got a very careful answer.',
      'He has got a notebook full of numbers he will not show anyone.'
    ],
    replies: [
      'Slow and careful. Nothing wrong with that.',
      'Better than saying too much too soon.',
      'That usually means it is not decided yet.',
      'Good. Means he is taking it seriously.'
    ]
  },
  studio_crew: {
    opens: [
      "The studio's three were up late again, lights on until who knows when.",
      'Della was buried in old photographs the last time I walked past.',
      'Nell reads her own scripts out loud to nobody. Works, apparently.',
      'Rafa never talks about a cut until it is basically finished.'
    ],
    replies: [
      'That is dedication or stubbornness, hard to say which.',
      'She would find something in a blank wall, that one.',
      'Whatever gets the words right in the end.',
      'Keeps the surprises for the screening, I suppose.'
    ]
  },
  trading_floor: {
    opens: [
      'The floor gets quiet right before the bell, every single time.',
      'Margo runs a tight ship over there, always has.',
      'Eva never seems to actually rest, does she.',
      'The desks fill up fast once the market opens.'
    ],
    replies: [
      'Calm before the storm, I suppose.',
      'Somebody has to keep the rest of us honest.',
      'She is not built to, from what I hear.',
      'Same time, every day, like a tide coming in.'
    ]
  },
  cafe_regulars: {
    opens: [
      "Sal remembers everyone's order, it is genuinely uncanny.",
      'Same four people at the same four tables, every morning.',
      "The corner couch has basically got somebody's name on it now.",
      'Somebody left a very generous tip and nobody knows who.'
    ],
    replies: [
      'She never misses. Not once.',
      'You could set a clock by that lot.',
      'Fair enough, honestly. Best seat in the place.',
      'Whoever it was, good on them.'
    ]
  },
  chess: {
    opens: [
      'Rosa still will not let anyone touch that pen of hers mid-game.',
      'Lost in four moves. Four. I counted.',
      'Somebody left a game half-finished on the corner table for days.',
      'I keep meaning to actually learn the openings properly.'
    ],
    replies: [
      'That pen has apparently never lost a game either.',
      'Four is almost impressive, honestly.',
      'Whoever it was clearly forgot about it entirely.',
      'Start with one and stick to it. That is the whole trick.'
    ]
  },
  mornings: {
    opens: [
      'I am not a real person until the second coffee.',
      'Somehow made it in on time and I do not know how.',
      'Mornings get harder every single year, I am convinced.',
      'The walk in wakes me up faster than the coffee does.'
    ],
    replies: [
      'Nobody is. Do not fight it.',
      'Do not question it, just take the win.',
      'They really do. Nobody warns you.',
      'That is the real secret, honestly.'
    ]
  },
  deadlines: {
    opens: [
      'Everything is apparently due at once this week.',
      'I keep moving the same thing to tomorrow.',
      'Finished something early for once and it felt wrong.',
      'The last hour before anything is due is somehow always the most productive.'
    ],
    replies: [
      'It always feels like that, every single week.',
      'Tomorrow becomes today eventually, you know.',
      'Enjoy it, that never happens twice in a row.',
      'Say that a little quieter, it might hear you.'
    ]
  },
  keys: {
    opens: [
      'Locked myself out again. Second time this month.',
      'Found my keys in the fridge. Do not ask.',
      'I have started keeping a spare with a neighbour, best decision all year.',
      'Spent ten minutes patting every pocket before I found them in my hand.'
    ],
    replies: [
      'At some point you have to just accept it about yourself.',
      'I am not going to ask.',
      'Smart. Everyone should do that.',
      'We have all been there, more than once.'
    ]
  }
};

/**
 * Reply forms that work after ANY opener, including a character's own
 * signature line. This is what stops "Pen's still lucky" getting answered with
 * an unrelated statement.
 */
export const REACTIONS = {
  agree:   ['Fair enough.', 'True.', 'Cannot argue with that.', 'Same here.'],
  tease:   ['Course it is.', 'Sure. Sure it is.', 'You said that last week too.',
            'Whatever gets you through.'],
  ask:     ['Since when?', 'Is that right?', 'How come?', 'Says who?'],
  deflect: ['If you say so.', 'Hm.', 'Anyway.', 'Right.']
};

/** Which reaction style a trait reaches for first. */
const TRAIT_STYLE = {
  superstitious: 'agree',
  methodical:    'ask',
  dry:           'tease',
  warm:          'agree',
  blunt:         'tease',
  anxious:       'ask',
  cheerful:      'agree'
};

const pick = arr => arr[Math.floor(Math.random() * arr.length)];

/**
 * Pick a subject that suits where the pair are standing. A conversation in the
 * cafe is about coffee; one in the studio is about the cut; one outside at
 * night is about the weather. This is the "smarter about surroundings" part --
 * the venue chooses the subject.
 */
export function topicForVenue(venue, isNight) {
  if (venue === 'cafe') return pick(['coffee', 'food', 'quiet', 'gossip', 'weekend',
                                      'streaming', 'cooking', 'cafe_regulars', 'news', 'mornings']);
  if (venue === 'room:studio') return pick(['studio', 'work', 'coffee', 'photography',
                                             'history', 'writing', 'studio_crew', 'deadlines']);
  if (venue === 'room:atmco' || venue === 'atmco') return pick(['atm', 'small_business', 'work', 'coffee', 'wes']);
  if (venue === 'room:break') return pick(['coffee', 'food', 'tired', 'mornings']);
  if (venue && venue.startsWith('home:')) return pick(['home', 'tired', 'food', 'sleep',
                                                        'cooking', 'streaming', 'plants', 'childhood']);
  if (venue === 'condo-hall') return pick(['neighbors', 'gossip', 'mail', 'quiet', 'parking']);
  if (venue === 'outdoors') return pick(isNight
    ? ['weather', 'tired', 'home', 'sleep', 'seasons']
    : ['weather', 'quiet', 'dogs', 'sage', 'lake', 'park', 'birdwatching', 'exercise',
       'plants', 'neighbors', 'parking', 'bikes', 'traffic', 'commute', 'seasons']);
  if (venue && venue.startsWith('room:trading')) return pick(['trading_floor', 'work', 'quiet', 'coffee', 'deadlines']);
  if (venue && venue.startsWith('room:')) return pick(['work', 'quiet', 'coffee', 'tech',
                                                        'news', 'puzzles', 'games', 'chess',
                                                        'shopping', 'holidays', 'hobbies',
                                                        'library', 'keys', 'deadlines']);
  return pick(['quiet', 'work']);
}

/** An opener on a subject. */
export function openerFor(topic) {
  const t = TOPICS[topic];
  return t ? pick(t.opens) : null;
}

/** A reply that actually answers `topic`. */
export function replyFor(topic) {
  const t = TOPICS[topic];
  return t ? pick(t.replies) : null;
}

/** A reaction in this person's style -- works after any line. */
export function reactionFor(person) {
  const style = TRAIT_STYLE[person && person.trait] || 'deflect';
  // mostly in-character, occasionally not, so it does not become a tic
  const bank = Math.random() < 0.7 ? REACTIONS[style]
                                   : REACTIONS[pick(Object.keys(REACTIONS))];
  return pick(bank);
}
