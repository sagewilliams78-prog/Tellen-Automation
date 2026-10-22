#!/usr/bin/env python3
"""
Owns sage_bot_v13's watchlist, so the nightly screener can change it
without ever rewriting Python source.

WHY THIS EXISTS
---------------
The watchlist used to be a literal list on line 178 of sage_bot_v13.py.
Having a nightly automated job regex-edit a live trading bot's source code
every night is a genuinely bad idea: one bad substitution and the bot
either won't start or, worse, starts and trades something unintended.

So the list moved here, into a JSON file. sage_bot_v13.py now reads it at
startup (and falls back to its own hardcoded list if anything at all is
wrong with this module or the file). The nightly job only ever writes
JSON. Python source is never touched again.

SAFETY RAILS
------------
Sage chose fully-automatic updates with no approval step -- that's her
call, and this module does not second-guess it. What it DOES enforce are
the rails that aren't about permission, they're about not corrupting the
account:

  * A symbol with an OPEN POSITION is never dropped. Dropping one would
    orphan the position -- the bot only manages symbols in WATCHLIST, so a
    dropped holding would sit there with nothing driving it to its stop or
    target. This is the single most dangerous thing this system could do,
    and it is unconditional.
  * At most MAX_SWAPS symbols change per run.
  * The list never grows or shrinks -- swaps are 1-for-1, so sizing and
    per-symbol capital assumptions stay valid.
  * Never drops below MIN_SYMBOLS.
  * Every change writes the previous list into history, so any night can
    be rolled back by hand.
  * Anything malformed => fall back to the last good list, never a
    partial or empty one.

This module does no network calls and imports nothing outside the stdlib,
so it cannot itself be a reason the bot fails to start.
"""
import json
import os
import re
from datetime import datetime

DATA_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_watchlist")
WATCHLIST_FILE = os.path.join(DATA_DIR, "current.json")

# Identical to what was hardcoded in sage_bot_v13.py on 2026-08-27, so a
# missing/corrupt file reproduces today's behaviour exactly rather than
# doing something surprising.
DEFAULT_WATCHLIST = ["IBRX", "IOVA", "NVDA", "TSLA", "AMD", "GDX", "SMCI"]

MAX_SWAPS = 2          # per run -- Sage's choice, 2026-08-27
MIN_SYMBOLS = 5
# Raised 10 -> 24 on 2026-08-27 to support a wider floor (7 desks x 3
# symbols). The reason for a wider list is empirical, not cosmetic: on a
# sampled live scan, 3 of 7 symbols were disqualified outright by the 3%
# zone-width filter and only one of the rest was in the buy zone, so the
# effective pool that day was a single symbol. More symbols raises the
# odds that at least one is both wide enough AND in the zone at once.
#
# Note what it does NOT do: concurrent positions are capped by buying
# power (bp // MIN_POSSIBLE_NOTIONAL), not by watchlist length. A wider
# list means fewer dead days and better selection among candidates, not
# more simultaneous trades.
MAX_SYMBOLS = 24
_TICKER = re.compile(r"^[A-Z][A-Z0-9.\-]{0,9}$")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def _valid_list(symbols):
    """A list is usable only if every entry looks like a ticker, there are
    no duplicates, and the size is sane. Anything else and we do not touch
    the bot's behaviour."""
    if not isinstance(symbols, list):
        return False
    if not (MIN_SYMBOLS <= len(symbols) <= MAX_SYMBOLS):
        return False
    if len(set(symbols)) != len(symbols):
        return False
    return all(isinstance(s, str) and _TICKER.match(s) for s in symbols)


def _read_state():
    if not os.path.exists(WATCHLIST_FILE):
        return {"symbols": list(DEFAULT_WATCHLIST), "updated": None, "history": []}
    try:
        with open(WATCHLIST_FILE) as f:
            data = json.load(f)
        if not _valid_list(data.get("symbols")):
            raise ValueError("stored watchlist failed validation")
        data.setdefault("history", [])
        data.setdefault("updated", None)
        return data
    except Exception:
        # Corrupt file -- behave exactly as the bot did before this module
        # existed rather than trading on a half-parsed list.
        return {"symbols": list(DEFAULT_WATCHLIST), "updated": None,
                "history": [], "note": "fell back to DEFAULT_WATCHLIST"}


def load_watchlist():
    """What sage_bot_v13.py calls at startup. Always returns a usable list."""
    return list(_read_state()["symbols"])


def read_state():
    """Full state including history -- for the dashboard and the nightly job."""
    return _read_state()


def apply_swaps(add, drop, open_positions=(), reason="", max_swaps=MAX_SWAPS):
    """Swap `drop` out for `add` in, 1-for-1, subject to the rails above.

    add / drop      : lists of tickers the screener proposed
    open_positions  : tickers the account currently HOLDS -- never dropped
    reason          : free text recorded in history

    Returns a result dict describing what actually happened, including
    anything that was refused and why. Callers should log it verbatim --
    a refused swap is information, not an error.
    """
    state = _read_state()
    current = list(state["symbols"])
    held = {s.upper() for s in open_positions}

    add = [s.upper() for s in (add or [])]
    drop = [s.upper() for s in (drop or [])]
    refused = []

    # --- filter the proposed drops -------------------------------------
    safe_drop = []
    for s in drop:
        if s not in current:
            refused.append(f"drop {s}: not in the watchlist")
        elif s in held:
            refused.append(f"drop {s}: REFUSED -- open position, dropping it "
                           f"would leave the position unmanaged")
        else:
            safe_drop.append(s)

    # --- filter the proposed adds --------------------------------------
    safe_add = []
    for s in add:
        if s in current:
            refused.append(f"add {s}: already in the watchlist")
        elif not _TICKER.match(s):
            refused.append(f"add {s}: not a valid ticker")
        elif s in safe_add:
            refused.append(f"add {s}: duplicate in proposal")
        else:
            safe_add.append(s)

    # --- 1-for-1, capped ------------------------------------------------
    # Two different reasons a survivor can go unused, and they must not be
    # conflated: it either exceeded the cap, or it had nothing left to pair
    # with because the other side got filtered out. Reporting an unpaired
    # add as "over the cap" would send someone diagnosing a bad night
    # looking at the wrong rail entirely.
    n = min(len(safe_add), len(safe_drop), max_swaps)
    for side, items in (("add", safe_add), ("drop", safe_drop)):
        for s in items[n:]:
            over_cap = min(len(safe_add), len(safe_drop)) > max_swaps
            refused.append(
                f"{side} {s}: over the {max_swaps}-swap cap for one run" if over_cap
                else f"{side} {s}: no valid counterpart to swap with this run")
    safe_add, safe_drop = safe_add[:n], safe_drop[:n]

    if n == 0:
        return {"changed": False, "symbols": current, "added": [], "dropped": [],
                "refused": refused, "reason": reason}

    new_list = [s for s in current if s not in safe_drop] + safe_add

    if not _valid_list(new_list):
        return {"changed": False, "symbols": current, "added": [], "dropped": [],
                "refused": refused + ["result failed validation -- no change made"],
                "reason": reason}

    entry = {
        "when": datetime.now().astimezone().isoformat(),
        "from": current,
        "to": new_list,
        "added": safe_add,
        "dropped": safe_drop,
        "reason": reason,
    }
    state["symbols"] = new_list
    state["updated"] = entry["when"]
    state.setdefault("history", []).insert(0, entry)
    del state["history"][30:]

    _ensure_dirs()
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(state, f, indent=2)

    return {"changed": True, "symbols": new_list, "added": safe_add,
            "dropped": safe_drop, "refused": refused, "reason": reason}


def expand(add, reason=""):
    """Add symbols WITHOUT dropping any -- growing the list rather than
    swapping within it.

    Deliberately separate from apply_swaps(), and deliberately NOT used by
    the nightly job: that one is capped at 2 one-for-one swaps precisely so
    the list cannot drift on its own. Growing the floor is a considered
    decision a human makes, so it gets its own entry point and its own
    history record.

    Every symbol passed here should already have cleared the backtest gate
    -- this function does not and cannot check that. Adding an unvetted
    ticker is exactly the mistake BTAI was.
    """
    state = _read_state()
    current = list(state["symbols"])
    refused, accepted = [], []

    for s in [x.upper() for x in (add or [])]:
        if s in current or s in accepted:
            refused.append(f"add {s}: already in the watchlist")
        elif not _TICKER.match(s):
            refused.append(f"add {s}: not a valid ticker")
        elif len(current) + len(accepted) >= MAX_SYMBOLS:
            refused.append(f"add {s}: would exceed the {MAX_SYMBOLS}-symbol ceiling")
        else:
            accepted.append(s)

    if not accepted:
        return {"changed": False, "symbols": current, "added": [], "dropped": [],
                "refused": refused, "reason": reason}

    new_list = current + accepted
    if not _valid_list(new_list):
        return {"changed": False, "symbols": current, "added": [], "dropped": [],
                "refused": refused + ["result failed validation -- no change made"],
                "reason": reason}

    entry = {"when": datetime.now().astimezone().isoformat(), "from": current,
             "to": new_list, "added": accepted, "dropped": [], "reason": reason}
    state["symbols"] = new_list
    state["updated"] = entry["when"]
    state.setdefault("history", []).insert(0, entry)
    del state["history"][30:]

    _ensure_dirs()
    with open(WATCHLIST_FILE, "w") as f:
        json.dump(state, f, indent=2)

    return {"changed": True, "symbols": new_list, "added": accepted,
            "dropped": [], "refused": refused, "reason": reason}


def rollback(steps=1):
    """Undo the last `steps` changes by restoring an earlier list. Manual
    use only -- the nightly job never calls this."""
    state = _read_state()
    hist = state.get("history", [])
    if len(hist) < steps:
        raise ValueError(f"only {len(hist)} changes in history")
    target = hist[steps - 1]["from"]
    if not _valid_list(target):
        raise ValueError("that historical list fails validation")
    return apply_swaps(
        add=[s for s in target if s not in state["symbols"]],
        drop=[s for s in state["symbols"] if s not in target],
        open_positions=(),
        reason=f"manual rollback of {steps} change(s)",
        max_swaps=MAX_SYMBOLS,
    )


def seed_if_missing():
    """Write the current hardcoded list on first run, so day one is a
    no-op rather than a surprise change."""
    if os.path.exists(WATCHLIST_FILE):
        return False
    _ensure_dirs()
    with open(WATCHLIST_FILE, "w") as f:
        json.dump({"symbols": list(DEFAULT_WATCHLIST),
                   "updated": datetime.now().astimezone().isoformat(),
                   "history": [],
                   "note": "seeded from sage_bot_v13.py's original hardcoded list"},
                  f, indent=2)
    return True


if __name__ == "__main__":
    seed_if_missing()
    print(json.dumps(read_state(), indent=2))
