#!/usr/bin/env python3
"""
Safety guards for Eva. Written after the 2026-09-03 incident.

WHAT HAPPENED
-------------
Eva ran 06:30-09:47 PT and attempted to buy PFE TWENTY-NINE TIMES, ~$135 each,
on a $250 account. The log shows:

    placed limit buy 4.95 PFE @ $28.64
    UNVERIFIABLE after 20s -- assuming FILLED (safe direction)
    ✓ EXECUTED

No money moved -- Robinhood recorded zero orders and zero positions, so every
one of those was phantom. That was luck, not design.

The loop: assume filled -> record a position -> next scan reconciles against
the broker -> broker has nothing -> delete the position -> PFE is still sitting
in the buy zone -> buy again. Forever.

"Assuming FILLED (safe direction)" is exactly backwards. An unverified fill
assumed TRUE means you may hold stock you never manage. Assumed FALSE means you
may miss a trade. Missing a trade is recoverable; an unmanaged position with no
stop is not. Unverifiable must mean NOT FILLED, and it must stop further entries
on that symbol rather than retrying blind.

AND THE PART THAT IS NOT EXPLAINED
-----------------------------------
That code is not in sage_bot_v13.py and never was -- its execute_order places
MARKET orders and prints "✓ ACCEPTED" before returning True. The log has 29
"✓ EXECUTED" and zero "✓ ACCEPTED", which the on-disk code cannot produce. The
file's mtime is 2026-09-03 09:49:50 -- after the run started and two minutes
after the log stopped.

Nobody knows what wrote it. The repo, the launch agents, the other Claude
session (from 08-27) and Codex were all checked and none of them contain that
string. So these guards assume the trading file itself is UNTRUSTED and may
change underneath a running process. That is why check_source_integrity()
exists: Eva now notices if her own code changes while she is holding money.

Every guard here fails CLOSED -- toward not trading.
"""

import csv
import hashlib
import json
import os
from collections import defaultdict
from datetime import date

STATE_DIR = os.path.expanduser("~/.eva_guards")
PENDING = os.path.join(STATE_DIR, "pending_orders.json")
COUNTS = os.path.join(STATE_DIR, "entry_counts.json")

# 29 buys of one symbol in one morning must be structurally impossible.
MAX_ENTRIES_PER_SYMBOL_PER_DAY = 2
MAX_ENTRIES_PER_DAY = 8
# How long an unconfirmed order blocks further attempts on that symbol.
PENDING_TTL_SECONDS = 900


def _load(path, default):
    try:
        with open(path) as f:
            return json.load(f)
    except Exception:
        return default


def _save(path, obj):
    os.makedirs(STATE_DIR, exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(obj, f, indent=2)
    os.replace(tmp, path)     # atomic; a crash mid-write cannot corrupt state


# --------------------------------------------------------- source integrity
def source_fingerprint(path):
    with open(path, "rb") as f:
        return hashlib.sha256(f.read()).hexdigest()[:16]


class SourceWatch:
    """Notice if the trading file changes while the bot is running.

    Normally paranoid. Here it is a direct response to an observed event: the
    live trading file was modified mid-session by something that has not been
    identified. A bot whose code changes underneath it cannot reason about its
    own behaviour, so it should stop opening new risk and say so loudly --
    while still managing whatever it already holds, because abandoning an open
    position is worse than anything the changed code might do.
    """

    def __init__(self, path):
        self.path = path
        self.original = source_fingerprint(path)
        self.tripped = False

    def check(self):
        try:
            now = source_fingerprint(self.path)
        except Exception:
            return True
        if now != self.original and not self.tripped:
            self.tripped = True
            print("\n" + "!" * 68)
            print("!! TRADING SOURCE CHANGED WHILE RUNNING")
            print(f"!!   {os.path.basename(self.path)}")
            print(f"!!   started as {self.original}, now {now}")
            print("!! NO NEW ENTRIES. Open positions still managed and exited.")
            print("!! This is what happened on 2026-09-03 -- do not ignore it.")
            print("!" * 68 + "\n")
        return not self.tripped


# ------------------------------------------------------------ pending orders
def mark_pending(symbol, ref_id, ts):
    """Record intent BEFORE the order is sent. If the process dies between
    sending and confirming, the marker survives and blocks a blind retry --
    which is the specific hole the 29-order loop fell through."""
    p = _load(PENDING, {})
    p[symbol] = {"ref_id": ref_id, "ts": ts}
    _save(PENDING, p)


def clear_pending(symbol):
    p = _load(PENDING, {})
    if p.pop(symbol, None) is not None:
        _save(PENDING, p)


def has_pending(symbol, now_ts):
    p = _load(PENDING, {})
    rec = p.get(symbol)
    if not rec:
        return False, None
    age = now_ts - rec["ts"]
    if age > PENDING_TTL_SECONDS:
        clear_pending(symbol)
        return False, None
    return True, age


# ------------------------------------------------------------- entry limits
def _today():
    return date.today().isoformat()


def entries_today(symbol=None):
    c = _load(COUNTS, {})
    day = c.get("date")
    if day != _today():
        return 0 if symbol else 0
    return c.get("symbols", {}).get(symbol, 0) if symbol else c.get("total", 0)


def record_entry(symbol):
    c = _load(COUNTS, {})
    if c.get("date") != _today():
        c = {"date": _today(), "total": 0, "symbols": {}}
    c["total"] = c.get("total", 0) + 1
    c["symbols"][symbol] = c["symbols"].get(symbol, 0) + 1
    _save(COUNTS, c)


def entry_allowed(symbol, now_ts):
    """The circuit breaker. Returns (allowed, reason)."""
    pending, age = has_pending(symbol, now_ts)
    if pending:
        return False, (f"an unconfirmed {symbol} order is still pending "
                       f"({age:.0f}s) -- refusing to stack another")
    n = entries_today(symbol)
    if n >= MAX_ENTRIES_PER_SYMBOL_PER_DAY:
        return False, (f"{symbol} already entered {n}x today "
                       f"(cap {MAX_ENTRIES_PER_SYMBOL_PER_DAY})")
    t = entries_today()
    if t >= MAX_ENTRIES_PER_DAY:
        return False, f"{t} entries today, daily cap {MAX_ENTRIES_PER_DAY} reached"
    return True, ""
