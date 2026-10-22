#!/usr/bin/env python3
"""
The town economy -- PURE FICTION, and deliberately so.

Everything else this dashboard serves is real: /api/status is the live
trading bot, /api/studio reads real files on disk, /api/atm tracks a real
business with real money. This file is the opposite and must never be
confused with them. There is no real money here, no real payroll, and no
connection of any kind to Sage's actual finances. It is a game economy for
fictional characters, so the town has something to do and somewhere to
spend it.

The one rule it borrows from the real modules: it does not lie about
ITSELF either. A character's balance is whatever the arithmetic actually
produced, purchases are recorded when they actually happen, and payday
runs once per month rather than whenever a page happens to load.
"""
import json
import os
from datetime import date, datetime

SIM_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_sim")
STATE_FILE = os.path.join(SIM_DIR, "economy.json")

CURRENCY = "SV$"          # Smallville dollars -- not dollars
STIPEND = 1000            # each resident, each payday
PAYDAY_DOM = 1            # the 1st of the month, same day for everyone

# ---------------------------------------------------------------------
#  The store's catalogue.
#
#  Prices are set against the SV$1,000/month stipend so that the cheap
#  things are a couple of weeks of saving and the big ones are most of a
#  year -- that gap is the point, since a goal you can buy immediately
#  isn't a goal.
# ---------------------------------------------------------------------
CATALOG = [
    # --- home upgrades ---
    {"id": "houseplant",  "name": "Houseplant",        "price": 80,    "kind": "home",
     "blurb": "Hard to kill. Mostly."},
    {"id": "rug",         "name": "Good rug",          "price": 150,   "kind": "home",
     "blurb": "Ties the room together, allegedly."},
    {"id": "bookshelf",   "name": "Bookshelf",         "price": 220,   "kind": "home",
     "blurb": "Fills up faster than you expect."},
    {"id": "coffee",      "name": "Espresso machine",  "price": 260,   "kind": "home",
     "blurb": "Sal says it will never be as good as hers."},
    {"id": "bigtv",       "name": "Big television",    "price": 600,   "kind": "home",
     "blurb": "Objectively too big for the room."},
    {"id": "garden",      "name": "Garden plot",       "price": 700,   "kind": "home",
     "blurb": "Tomatoes by August, optimistically."},
    {"id": "extension",   "name": "Home extension",    "price": 14000, "kind": "home",
     "blurb": "A whole extra room. Years of saving."},
    # --- pets ---
    {"id": "cat",         "name": "Cat",               "price": 450,   "kind": "pet",
     "blurb": "Will decide whether it lives with you."},
    {"id": "dog",         "name": "Dog",               "price": 850,   "kind": "pet",
     "blurb": "Sage's two seem to have started something."},
    # --- getting about ---
    {"id": "bicycle",     "name": "Bicycle",           "price": 400,   "kind": "vehicle",
     "blurb": "Faster than walking to the cafe."},
    {"id": "usedcar",     "name": "Used car",          "price": 4500,  "kind": "vehicle",
     "blurb": "Runs. Mostly. A real commute, finally."},
    {"id": "newcar",      "name": "New car",           "price": 9000,  "kind": "vehicle",
     "blurb": "The one everybody actually wants."},
]

CATALOG_BY_ID = {item["id"]: item for item in CATALOG}

# Who lives here, and what each of them is actually saving toward, in
# order. The wishlists are drawn from the same personalities as people.js
# -- Cy wants a garden because Cy fills every corner with plants; Miles
# wants a bookshelf before anything with an engine in it.
#
# Every list ends in something genuinely expensive, so nobody ever runs
# out of things to work toward -- an early version let two of them buy
# their whole list on the first payday and then just sit on a growing pile
# of money with no goal, which defeats the point.
RESIDENTS = {
    "sym0":      {"name": "Rosa",      "wishlist": ["rug", "cat", "bigtv", "usedcar", "extension"]},
    "sym1":      {"name": "Miles",     "wishlist": ["bookshelf", "coffee", "usedcar", "garden", "extension"]},
    "sym2":      {"name": "Priya",     "wishlist": ["bicycle", "bigtv", "newcar", "extension"]},
    "sym3":      {"name": "Bear",      "wishlist": ["bigtv", "dog", "garden", "usedcar", "extension"]},
    "sym4":      {"name": "June",      "wishlist": ["bookshelf", "houseplant", "cat", "garden", "extension"]},
    "sym5":      {"name": "Cy",        "wishlist": ["garden", "houseplant", "dog", "bicycle", "extension"]},
    "sym6":      {"name": "Wren",      "wishlist": ["coffee", "bicycle", "usedcar", "newcar", "extension"]},
    "eva":       {"name": "Eva",       "wishlist": ["houseplant", "bookshelf", "rug", "garden", "extension"]},
    "risk":      {"name": "Margo",     "wishlist": ["bookshelf", "garden", "usedcar", "extension"]},
    "mechanic":  {"name": "Otis",      "wishlist": ["coffee", "dog", "usedcar", "extension"]},
    "barista":   {"name": "Sal",       "wishlist": ["cat", "rug", "garden", "bicycle", "extension"]},
    "archivist": {"name": "Della",     "wishlist": ["bookshelf", "rug", "cat", "garden", "extension"]},
    "writer":    {"name": "Nell",      "wishlist": ["coffee", "bookshelf", "garden", "cat", "extension"]},
    "editor":    {"name": "Rafa",      "wishlist": ["bigtv", "newcar", "extension"]},
    "atmops":    {"name": "Wes",       "wishlist": ["bookshelf", "usedcar", "dog", "extension"]},
    "doctor1":   {"name": "Dr. Ahn",   "wishlist": ["garden", "bigtv", "newcar", "extension"]},
    "doctor2":   {"name": "Dr. Reyes", "wishlist": ["dog", "garden", "newcar", "extension"]},
}


def _ensure_dirs():
    os.makedirs(SIM_DIR, exist_ok=True)


def _blank_state():
    return {
        "last_payday": None,          # ISO date string of the last payday run
        "paydays_run": 0,
        "wallets": {rid: 0 for rid in RESIDENTS},
        "owned": {rid: [] for rid in RESIDENTS},
        "log": [],                    # newest first, capped
    }


def load_state():
    if not os.path.exists(STATE_FILE):
        return _blank_state()
    try:
        with open(STATE_FILE) as f:
            data = json.load(f)
    except Exception:
        return _blank_state()
    # A resident added to RESIDENTS after the file was written starts at
    # zero rather than crashing a lookup.
    base = _blank_state()
    base.update({k: v for k, v in data.items() if k in base})
    for rid in RESIDENTS:
        base["wallets"].setdefault(rid, 0)
        base["owned"].setdefault(rid, [])
    return base


def save_state(state):
    _ensure_dirs()
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _log(state, text):
    state["log"].insert(0, {"when": datetime.now().astimezone().isoformat(), "text": text})
    del state["log"][60:]


def current_goal(rid, owned):
    """The next thing on this resident's list they don't already own.
    None once they've bought everything they ever wanted."""
    for item_id in RESIDENTS[rid]["wishlist"]:
        if item_id not in owned:
            return CATALOG_BY_ID[item_id]
    return None


def _shop(state):
    """Everyone buys their current goal if they can now afford it.

    Deliberately NOT "buy the most expensive affordable thing" -- a
    resident saving for a car walks past a houseplant they could afford,
    because the whole point is having something to work toward.
    """
    for rid in RESIDENTS:
        while True:
            goal = current_goal(rid, state["owned"][rid])
            if not goal or state["wallets"][rid] < goal["price"]:
                break
            state["wallets"][rid] -= goal["price"]
            state["owned"][rid].append(goal["id"])
            _log(state, f"{RESIDENTS[rid]['name']} bought {goal['name']} "
                        f"for {CURRENCY}{goal['price']:,}")


def _paydays_between(last_iso, today):
    """How many PAYDAY_DOMs have passed since the last run. Returns a list
    of the dates, so a dashboard left closed for three months pays three
    times rather than silently swallowing two."""
    if last_iso is None:
        return [today]                     # first ever run: pay once, now
    last = date.fromisoformat(last_iso)
    out, y, m = [], last.year, last.month
    while True:
        m += 1
        if m > 12:
            m, y = 1, y + 1
        d = date(y, m, PAYDAY_DOM)
        if d > today:
            break
        out.append(d)
    return out


def run_payday_if_due(today=None):
    """Idempotent. Pays every resident their stipend for each payday that
    has actually passed since the last run, then lets them shop."""
    today = today or date.today()
    state = load_state()
    due = _paydays_between(state["last_payday"], today)
    if not due:
        return state

    for d in due:
        for rid in RESIDENTS:
            state["wallets"][rid] += STIPEND
        state["paydays_run"] += 1
        _log(state, f"Payday — everyone received {CURRENCY}{STIPEND:,}")
        state["last_payday"] = d.isoformat()
    _shop(state)
    save_state(state)
    return state


def grant_bonus(amount, reason="Bonus"):
    """A one-off payment to every resident, on top of the monthly stipend.

    Separate from run_payday_if_due() on purpose: payday is on a schedule
    and must stay idempotent, whereas a bonus happens because someone
    decided it should. Calling this twice pays twice -- that is correct,
    and why nothing calls it automatically.
    """
    state = load_state()
    for rid in RESIDENTS:
        state["wallets"][rid] += amount
    _log(state, f"{reason} — everyone received {CURRENCY}{amount:,}")
    _shop(state)
    save_state(state)
    return state


def build_economy_status():
    state = load_state()
    residents = []
    for rid, meta in RESIDENTS.items():
        owned = state["owned"][rid]
        bal = state["wallets"][rid]
        goal = current_goal(rid, owned)
        residents.append({
            "id": rid,
            "name": meta["name"],
            "balance": bal,
            "owned": [{"id": i, "name": CATALOG_BY_ID[i]["name"],
                       "kind": CATALOG_BY_ID[i]["kind"]} for i in owned],
            "goal": ({"id": goal["id"], "name": goal["name"], "price": goal["price"],
                      "saved": bal, "short": max(0, goal["price"] - bal),
                      "pct": min(100, round(bal / goal["price"] * 100))}
                     if goal else None),
        })
    residents.sort(key=lambda r: r["name"])
    return {
        "currency": CURRENCY,
        "stipend": STIPEND,
        "payday_note": f"Every resident receives {CURRENCY}{STIPEND:,} on the "
                       f"{PAYDAY_DOM}st of each month.",
        "last_payday": state["last_payday"],
        "paydays_run": state["paydays_run"],
        "catalog": CATALOG,
        "residents": residents,
        "log": state["log"][:20],
        "fiction_note": "Smallville dollars are make-believe. This economy has no "
                        "connection to any real account, and none of it is real money.",
        "generated_at": datetime.now().astimezone().isoformat(),
    }


if __name__ == "__main__":
    run_payday_if_due()
    print(json.dumps(build_economy_status(), indent=2))
