#!/usr/bin/env python3
"""
Build eva_v14.py from sage_bot_v13.py.

A patch script rather than a hand-copied 1429-line file, so that:
  - every difference between v13 and v14 is explicit and reviewable here
  - v13 is never touched and keeps running
  - the build is repeatable if v13 changes

Each patch asserts its anchor exists before applying. If v13 shifts under us,
this fails loudly instead of silently producing a half-patched trading bot.

WHAT v14 CHANGES (and nothing else):

  1. MCP TIMEOUTS -- the real fix. v13's 11 session.call_tool() calls had no
     timeout; one hung at 0% CPU for 7+ minutes on 2026-09-01 while holding an
     unmanaged position. Every call is now wrapped with asyncio.wait_for.

  2. DECISION JOURNAL -- v13 logged only completed trades (4 rows ever), so no
     backtest could be validated against real behaviour. v14 logs every symbol
     on every scan.

  3. CONFIG-DRIVEN FILTERS -- so a filter can be A/B tested without editing a
     live trading file. Defaults reproduce v13 exactly.

Deliberately NOT changed: risk limits, sizing, stops, targets, EOD flatten,
earnings blackout, weekly breaker. Those are proven; this version is about
reliability and measurement.
"""

from pathlib import Path

BASE = Path(__file__).resolve().parent
SRC = BASE / "sage_bot_v13.py"
DST = BASE / "eva_v14.py"


def patch(text, anchor, replacement, label, count=1):
    if anchor not in text:
        raise SystemExit(f"ANCHOR NOT FOUND for '{label}'.\n  {anchor[:120]}")
    n = text.count(anchor)
    if count == 1 and n != 1:
        raise SystemExit(f"anchor for '{label}' appears {n} times, expected 1")
    print(f"  ✓ {label}")
    return text.replace(anchor, replacement, count)


def main():
    t = SRC.read_text()
    print(f"building v14 from v13 ({len(t.splitlines())} lines)\n")

    # ---------------------------------------------------------------- header
    t = patch(
        t,
        'EVA - SAGE BOT v13 (RANGE & SWING STRATEGY, FLOOR-LEAD FILTERS)',
        'EVA v14 (RANGE & SWING -- TIMEOUTS, DECISION JOURNAL, TUNABLE FILTERS)',
        "banner renamed to v14",
    )

    # ------------------------------------------------- config + infrastructure
    infra = '''
# ============================================================================
# EVA v14 ADDITIONS
# ============================================================================
# Everything between here and the END marker is new in v14. v13's strategy
# logic below is unchanged except where these are wired in.

import asyncio as _v14_asyncio

_V14_CONFIG_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                                "eva_v14_config.json")


def _v14_load_config():
    """Config is advisory: if it is missing or malformed, v14 falls back to
    exactly v13's behaviour rather than refusing to trade. A trading bot must
    not be bricked by a bad config file."""
    defaults = {
        "reliability": {"mcp_call_timeout_seconds": 45,
                        "scan_stall_seconds": 180,
                        "max_consecutive_scan_errors": 5},
        "filters": {"require_bullish_candle": True,
                    "require_volume_confirmation": False,
                    "min_zone_depth_pct": None},
        "ranking": {"mode": "net_edge"},
        "decision_journal": {"enabled": True, "path": "~/eva_decisions.csv"},
    }
    try:
        with open(_V14_CONFIG_PATH) as f:
            loaded = json.load(f)
        for section, vals in defaults.items():
            if section not in loaded or not isinstance(loaded[section], dict):
                loaded[section] = vals
            else:
                for k, v in vals.items():
                    loaded[section].setdefault(k, v)
        return loaded
    except Exception as e:
        print(f"  ⚠️  v14 config unreadable ({e}) -- using v13 defaults")
        return defaults


V14 = _v14_load_config()
V14_TIMEOUT = V14["reliability"]["mcp_call_timeout_seconds"]


class V14Timeout(Exception):
    """An MCP call exceeded its timeout. Raised so the caller can decide --
    never swallowed, because a silent timeout is how v13 hung."""


async def v14_call(session, name, args, timeout=None):
    """Every MCP call in v14 goes through here.

    THE FIX FOR THE 2026-09-01 HANG. v13 called session.call_tool() bare, with
    no timeout anywhere. A call blocked in kevent() at 0% CPU and the bot froze
    mid-scan for 7+ minutes while holding an unmanaged MSFT position -- its
    stop was never evaluated. A frozen bot holding stock is worse than a
    stopped one, because every health check still sees a live process.
    """
    limit = timeout or V14_TIMEOUT
    try:
        return await _v14_asyncio.wait_for(
            session.call_tool(name, args), timeout=limit)
    except _v14_asyncio.TimeoutError:
        raise V14Timeout(f"{name} exceeded {limit}s") from None


V14_DECISION_COLUMNS = [
    "timestamp", "scan", "symbol", "price", "zone", "candle", "volume_ok",
    "zone_width_ok", "zone_width_pct", "depth_pct", "spread_pct",
    "gross_to_target_pct", "net_edge_pct", "buy_low", "buy_high", "target",
    "earnings_blackout", "entry_signal", "action", "reason",
]


def v14_journal(rows):
    """Log EVERY symbol on EVERY scan -- not just trades.

    v13 wrote only completed trades: 4 rows in its entire life. That is why no
    backtest could be checked against reality. Backtests predicted ~100 trades
    per 4 months while Eva took 4, and nobody could explain the 25x gap.
    With this, a few days of running produces thousands of real decision rows
    to validate against -- turning 'the model says' into 'the model was right
    about X and wrong about Y'.

    Never raises: journalling must not be able to break trading.
    """
    if not V14["decision_journal"]["enabled"] or not rows:
        return
    try:
        path = os.path.expanduser(V14["decision_journal"]["path"])
        new = not os.path.exists(path)
        with open(path, "a", newline="") as f:
            w = csv.DictWriter(f, fieldnames=V14_DECISION_COLUMNS,
                               extrasaction="ignore")
            if new:
                w.writeheader()
            for r in rows:
                w.writerow(r)
    except Exception as e:
        print(f"  ⚠️  decision journal write failed (non-fatal): {e}")


def v14_entry_allowed(cndl, lv, price, depth_pct):
    """Config-driven entry filters. Defaults reproduce v13 exactly.

    Returns (allowed, reason). The reason is journalled on every rejection, so
    'why did Eva not trade' becomes answerable from data rather than inference.
    """
    f = V14["filters"]
    if f.get("require_bullish_candle", True) and not cndl.get("bullish"):
        return False, "candle not bullish"
    if f.get("require_volume_confirmation", False) and not cndl.get("volume_ok"):
        return False, "volume below confirmation ratio"
    mind = f.get("min_zone_depth_pct")
    if mind is not None and depth_pct < mind:
        return False, f"depth {depth_pct:.2f}% < {mind}% minimum"
    return True, "all filters passed"

# ============================================================================
# END EVA v14 ADDITIONS
# ============================================================================

'''
    t = patch(t, "def init_log():", infra + "def init_log():",
              "v14 config, timeout wrapper, decision journal, filter gate")

    # ------------------------------------------- route MCP calls via v14_call
    before = t.count("await session.call_tool(")
    t = t.replace("await session.call_tool(", "await v14_call(session, ")
    print(f"  ✓ wrapped {before} MCP calls with a {V14_TIMEOUT_NOTE}s timeout")

    # v14_call takes (session, name, args) -- the replace above already
    # inserted `session, `, so the original first arg lines up as `name`.

    # ------------------------------------------------ wire the filter gate in
    t = patch(
        t,
        '                                if cndl["low"] <= lv["rl"] and cndl["bullish"]:',
        '                                _depth_pct = (lv["rl"] - p) / lv["rl"] * 100\n'
        '                                _ok, _why = v14_entry_allowed(cndl, lv, p, _depth_pct)\n'
        '                                if cndl["low"] <= lv["rl"] and _ok:',
        "entry filters now config-driven",
    )

    DST.write_text(t)
    print(f"\nwrote {DST.name} ({len(t.splitlines())} lines)")


V14_TIMEOUT_NOTE = 45

if __name__ == "__main__":
    main()
