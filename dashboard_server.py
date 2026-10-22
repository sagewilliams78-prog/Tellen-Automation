#!/usr/bin/env python3
"""
Eva Trading Dashboard -- local, read-only status server.

Reads directly from the live bot's own stdout log and the CSV files it
already writes (trade log, daily journal, floor-lead reviews). Makes NO
calls to Robinhood/MCP itself -- zero risk of interfering with the live
bot's own session, zero new credentials needed. Just tails files that
already exist and serves them as JSON + a simple auto-refreshing page.

Usage:
    "robin hood trading bot/.venv/bin/python" dashboard_server.py
    then open http://localhost:8420 in a browser (or use the Browser pane).
"""
import csv, json, os, re, stat, threading, time
import urllib.request, urllib.error
from datetime import datetime, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
import studio
import atm_business
import predict_business
import airport_business
import sim_economy
import crypto_desk
from town_assets import (
    GRASS_PNG, PATH_PNG, ASPHALT_PNG, WATER_PNG, TREE_PNG, BENCH_PNG,
    HALL_LIT_PNG, HALL_DIM_PNG, CAFE_PNG, GROCERY_PNG, EVA_PNG,
    SHERIFF_CALM_PNG, SHERIFF_ALERT_PNG, FIRE_CALM_PNG, FIRE_ALERT_PNG,
    SHERIFF_PERSON_PNG, FIRE_PERSON_PNG,
    TRADER_0_PNG, TRADER_1_PNG, TRADER_2_PNG, TRADER_3_PNG,
    TRADER_4_PNG, TRADER_5_PNG, TRADER_6_PNG,
    HOUSE_BUY_0_PNG, HOUSE_BUY_1_PNG, HOUSE_BUY_2_PNG,
    HOUSE_SELL_0_PNG, HOUSE_SELL_1_PNG, HOUSE_SELL_2_PNG,
    HOUSE_DIM_0_PNG, HOUSE_DIM_1_PNG, HOUSE_DIM_2_PNG,
    HOUSE_NARROW_0_PNG, HOUSE_NARROW_1_PNG, HOUSE_NARROW_2_PNG,
    HOME_0_PNG, HOME_1_PNG, HOME_2_PNG, HOME_3_PNG, HOME_4_PNG, HOME_5_PNG, HOME_6_PNG,
)
TRADER_PNGS = [TRADER_0_PNG, TRADER_1_PNG, TRADER_2_PNG, TRADER_3_PNG,
               TRADER_4_PNG, TRADER_5_PNG, TRADER_6_PNG]
HOME_PNGS = [HOME_0_PNG, HOME_1_PNG, HOME_2_PNG, HOME_3_PNG, HOME_4_PNG, HOME_5_PNG, HOME_6_PNG]
HOUSE_PNGS = {
    "buy":    [HOUSE_BUY_0_PNG, HOUSE_BUY_1_PNG, HOUSE_BUY_2_PNG],
    "sell":   [HOUSE_SELL_0_PNG, HOUSE_SELL_1_PNG, HOUSE_SELL_2_PNG],
    "dim":    [HOUSE_DIM_0_PNG, HOUSE_DIM_1_PNG, HOUSE_DIM_2_PNG],
    "narrow": [HOUSE_NARROW_0_PNG, HOUSE_NARROW_1_PNG, HOUSE_NARROW_2_PNG],
}

def _durl(b64):
    return "data:image/png;base64," + b64

PORT = 8420

# ---- Bull & Bear news-bulletin voice (ElevenLabs) --------------------------
# The key lives ONLY here, server-side, in a file outside every directory
# this server serves statically (see serve_hq's HQ_DIR guard and the fact
# nothing under _secrets/ is ever served). The browser calls POST /api/tts
# on this server; this server is the only thing that ever holds the real
# key or talks to ElevenLabs. Never move this into hq/ or return it in any
# response -- that would ship it to anyone who opens dev tools.
SECRETS_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_secrets")
ELEVENLABS_KEY_FILE = os.path.join(SECRETS_DIR, "elevenlabs.json")
# Two of ElevenLabs' own stock premade voices (Adam, Rachel) -- stable public
# voice IDs, not anything tied to this account. Swap these for cloned/chosen
# voices later by editing this dict alone.
ELEVENLABS_VOICES = {"bull": "pNInz6obpgDQGcFmaJgB", "bear": "21m00Tcm4TlvDq8ikWAM"}

def read_elevenlabs_key():
    try:
        with open(ELEVENLABS_KEY_FILE) as f:
            return (json.load(f) or {}).get("api_key") or None
    except Exception:
        return None

def elevenlabs_tts(text, voice):
    """One line of the news-bulletin script -> real MP3 bytes from ElevenLabs.
    Raises RuntimeError (missing key / bad input) or urllib.error.HTTPError
    (ElevenLabs itself rejected the request) -- handle_tts() turns either
    into a real error the UI can show, never a fabricated audio clip."""
    key = read_elevenlabs_key()
    if not key:
        raise RuntimeError("ElevenLabs API key not configured -- add one to _secrets/elevenlabs.json")
    voice_id = ELEVENLABS_VOICES.get(voice, ELEVENLABS_VOICES["bull"])
    req = urllib.request.Request(
        f"https://api.elevenlabs.io/v1/text-to-speech/{voice_id}",
        data=json.dumps({
            "text": text,
            "model_id": "eleven_turbo_v2_5",
            "voice_settings": {"stability": 0.4, "similarity_boost": 0.75}
        }).encode(),
        headers={"xi-api-key": key, "Content-Type": "application/json", "Accept": "audio/mpeg"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=30) as resp:
        return resp.read()

# ---- The Field Office's real job -------------------------------------------
# Voss & Ito's "🚨 on air / 🟢 all secure" status (see hq/agents/activity.js's
# securityState) is driven by THIS, not fiction: a real, cheap check of the
# real secret files this app and the live bot actually depend on. Every
# check below is a plain os.stat() call -- no filesystem crawling, safe to
# run on every poll. A file is flagged unsafe if it grants the group or
# "other" permission bits ANYTHING (0o077 mask) -- owner-only (600) is what
# every one of these was set up as; anything looser is a real finding, not
# a style nit.
SECURITY_TARGETS = [
    {"id": "elevenlabs",      "label": "ElevenLabs API key",              "path": ELEVENLABS_KEY_FILE},
    {"id": "bot_secrets",     "label": "Finnhub key + account number",    "path": os.path.expanduser("~/.eva_bot_secrets.json")},
    {"id": "robinhood_auth",  "label": "Robinhood OAuth credentials",            "path": os.path.expanduser("~/.sage_robinhood_oauth.json")},
]

def build_security_status():
    # Real local file paths (which reveal the machine's username/layout)
    # are used to run the check but deliberately never put in the response
    # -- the UI only needs id/label/exists/ok/detail, and there's no reason
    # to hand a real filesystem path to anything that renders in a browser,
    # even a localhost-only one.
    checks = []
    for t in SECURITY_TARGETS:
        p = t["path"]
        pub = {"id": t["id"], "label": t["label"]}
        if not os.path.exists(p):
            checks.append({**pub, "exists": False, "ok": False, "mode": None,
                           "detail": "file not found"})
            continue
        mode = stat.S_IMODE(os.stat(p).st_mode)
        ok = (mode & 0o077) == 0
        checks.append({
            **pub, "exists": True, "ok": ok, "mode": oct(mode),
            "detail": "owner-only (600)" if ok else f"group/other-accessible ({oct(mode)}) -- real exposure"
        })
    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "all_clear": all(c["ok"] for c in checks),
        "checks": checks,
    }

# Where Eva's live output actually is. This moved on 2026-09-01: the bot is
# now launched by eva_cycle_runner.py, which redirects its stdout to
# ~/eva_cycle.log -- the old launchd path stopped being written and the city
# sat frozen on a day-old scan while the real bot was on scan #200.
#
# Rather than hardcode one path and break again the next time the launcher
# changes, pick whichever candidate log was written most recently. A stale
# path simply loses; the live one always wins.
BOT_LOG_CANDIDATES = [
    os.path.expanduser("~/eva_cycle.log"),
    "/Users/sagewilliams/Desktop/robin hood trading bot/logs/sage_bot_v13.log",
]


def _freshest_bot_log():
    best, best_mtime = BOT_LOG_CANDIDATES[0], -1
    for p in BOT_LOG_CANDIDATES:
        try:
            m = os.path.getmtime(p)
        except OSError:
            continue
        if m > best_mtime:
            best, best_mtime = p, m
    return best


def bot_log_path():
    """Call this at read time, never cache it -- the dashboard is long-lived
    and the bot's launcher can change under it."""
    return _freshest_bot_log()
TRADE_LOG = os.path.expanduser("~/trading_log_v9.csv")
JOURNAL_LOG = os.path.expanduser("~/sage_bot_daily_journal.csv")
FLOOR_LEAD_LOG = os.path.expanduser("~/sage_bot_floor_lead_reviews.csv")

SCAN_HEADER_RE = re.compile(r"^\[(\d{2}:\d{2}:\d{2} [AP]M ET)\] Scan #(\d+)")
ZONE_LINE_RE = re.compile(
    r"^\s+(\w+): \$([\d.]+)\s+(BUY|KILL|SELL)\s+candle:(\w+)\s*(lowvol)?\s*(⚡ ENTRY)?"
)
BP_LINE_RE = re.compile(r"BP \$([\d.]+) \| (\d+) managed.*room for (\d+) more")
BREADTH_RE = re.compile(r"market breadth \(SPY\): ([+-][\d.]+)% from open")
LEVELS_LINE_RE = re.compile(
    r"^\s+(\w+): Sell \[([\d.]+)-([\d.]+)\] \| Kill \[([\d.]+)-([\d.]+)\] \| "
    r"Buy \[([\d.]+)-([\d.]+)\] \| target \$([\d.]+)(\s+⛔ zone too narrow)?"
)
LEVELS_HEADER_RE = re.compile(r"RANGE & SWING LEVELS")
EARNINGS_LINE_RE = re.compile(r"EARNINGS BLACKOUT - no new entries today: (.+)")
WEEKLY_LINE_RE = re.compile(r"Trailing 7-day win rate: (.+)")

def read_csv_rows(path):
    if not os.path.exists(path):
        return []
    with open(path, newline="") as f:
        return list(csv.DictReader(f))

def tail_lines(path, n=400):
    if not os.path.exists(path):
        return []
    with open(path, "r", errors="replace") as f:
        lines = f.readlines()
    return lines[-n:]

def parse_latest_scan():
    """Find the most recent scan block in the bot log and parse it."""
    lines = tail_lines(bot_log_path(), 400)
    last_scan_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if SCAN_HEADER_RE.match(lines[i]):
            last_scan_idx = i
            break
    if last_scan_idx is None:
        return None
    header = SCAN_HEADER_RE.match(lines[last_scan_idx])
    scan = {"time": header.group(1), "scan_num": int(header.group(2)), "symbols": []}
    # Read to the END of this scan block, not a fixed number of lines.
    #
    # Fixed 2026-09-01: this was `last_scan_idx + 20`, which silently dropped
    # the tail of every scan once the watchlist grew past ~16 symbols. A block
    # is header + breadth + buying-power + "ZONES" + one line per symbol, so a
    # 20-symbol watchlist needs 24 lines and the city was showing 16 -- the
    # last four tickers (WMT, GOOGL, BA, PFE) simply never appeared, with no
    # error anywhere. Bounding by the NEXT scan header instead means this
    # cannot rot again the next time the watchlist changes size.
    block_end = len(lines)
    for j in range(last_scan_idx + 1, len(lines)):
        if SCAN_HEADER_RE.match(lines[j]):
            block_end = j
            break

    for line in lines[last_scan_idx:block_end]:
        bp_m = BP_LINE_RE.search(line)
        if bp_m:
            scan["buying_power"] = float(bp_m.group(1))
            scan["managed"] = int(bp_m.group(2))
            scan["room_for"] = int(bp_m.group(3))
        breadth_m = BREADTH_RE.search(line)
        if breadth_m:
            scan["breadth"] = float(breadth_m.group(1))
        zone_m = ZONE_LINE_RE.match(line)
        if zone_m:
            scan["symbols"].append({
                "symbol": zone_m.group(1), "price": float(zone_m.group(2)),
                "zone": zone_m.group(3), "candle": zone_m.group(4),
                "lowvol": bool(zone_m.group(5)), "entry_flag": bool(zone_m.group(6)),
            })
        if "Market closed. Exiting." in line:
            scan["market_closed"] = True
        if "Entry window CLOSED" in line:
            scan["window_closed"] = True
    return scan

# Last successfully parsed daily banner. The banner prints ONCE per process
# start, so on a long trading day it eventually scrolls out of the tail window
# (observed 2026-08-25: banner 4018 lines back vs. a 4000-line window, which
# silently blanked every buy zone, the earnings blackout and the weekly status
# mid-afternoon). Widening the window alone only moves the cliff, so the last
# good parse is also cached and reused when the banner is no longer visible.
_daily_cache = {"levels": {}, "earnings_blackout": [], "weekly_status": None, "found": False}

def parse_daily_status():
    """Find the MOST RECENT startup banner's Range & Swing levels, earnings
    blackout list, and weekly win-rate status. This block only prints once
    per process start (not per scan), so search a large tail for the last
    occurrence -- if the bot restarted mid-day, this correctly picks up the
    freshest one, not a stale one from hours ago."""
    lines = tail_lines(bot_log_path(), 30000)
    last_header_idx = None
    for i in range(len(lines) - 1, -1, -1):
        if LEVELS_HEADER_RE.search(lines[i]):
            last_header_idx = i
            break
    levels = {}
    earnings_blackout = []
    weekly_status = None
    if last_header_idx is not None:
        for line in lines[last_header_idx:last_header_idx + 15]:
            m = LEVELS_LINE_RE.match(line)
            if m:
                sym, sell_lo, sell_hi, kill_lo, kill_hi, buy_lo, buy_hi, target, narrow = m.groups()
                levels[sym] = {
                    "buy_low": float(buy_lo), "buy_high": float(buy_hi),
                    "target": float(target), "narrow": bool(narrow),
                }
            e = EARNINGS_LINE_RE.search(line)
            if e:
                # split only on commas that separate ENTRIES (comma followed by a new symbol,
                # i.e. an uppercase letter) -- NOT the comma inside "(+1d, 2026-08-26 pm)"
                earnings_blackout = [s.strip() for s in re.split(r",\s*(?=[A-Z])", e.group(1)) if s.strip()]
            w = WEEKLY_LINE_RE.search(line)
            if w:
                weekly_status = w.group(1).strip()

    if levels:
        _daily_cache.update({"levels": levels, "earnings_blackout": earnings_blackout,
                             "weekly_status": weekly_status, "found": True})
    elif _daily_cache["found"]:
        # banner has scrolled out of the window -- reuse the last good parse
        # rather than reporting "no zones", which reads as a real all-clear
        return {k: _daily_cache[k] for k in ("levels", "earnings_blackout", "weekly_status")}

    return {"levels": levels, "earnings_blackout": earnings_blackout, "weekly_status": weekly_status}

def bot_process_alive():
    """Best-effort liveness check: was the log touched in the last 3 minutes?"""
    log_path = bot_log_path()
    if not os.path.exists(log_path):
        return False
    age = time.time() - os.path.getmtime(log_path)
    return age < 180

def today_str():
    return datetime.now().astimezone().strftime("%Y-%m-%d")

MECHANIC_STATUS_FILE = os.path.expanduser("~/.eva_mechanic_status.json")

def read_mechanic_status():
    """Read the status file the eva-morning-mechanic and eva-hourly-mechanic
    scheduled tasks write to on every run. Missing/malformed file just means
    neither has run yet -- not an error."""
    if not os.path.exists(MECHANIC_STATUS_FILE):
        return {}
    try:
        with open(MECHANIC_STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}

def build_equity_curve(trades):
    """Cumulative P&L across every completed trade in the log, in order.
    Not date-bucketed -- one point per trade, so multi-trade days show
    real intra-day movement instead of collapsing to a single point."""
    running = 0.0
    curve = []
    for t in trades:
        try:
            running += float(t.get("P&L", 0) or 0)
        except ValueError:
            continue
        curve.append({"date": t.get("Date", ""), "symbol": t.get("Symbol", ""),
                      "cumulative": round(running, 2)})
    return curve

def generate_market_update(scan, weekly_status, earnings_blackout):
    """A short, plain-language summary in Eva's voice, built entirely from
    real fields already parsed above -- no AI call, no fabrication risk.
    Deliberately scoped to what the bot itself actually knows (SPY breadth
    from its own Finnhub check, its own zone math) rather than pretending
    to have broader market/news awareness it doesn't have."""
    if not scan or not scan.get("symbols"):
        return "No scan data yet -- check back once the bot has run at least once today."

    lines = []
    breadth = scan.get("breadth")
    if breadth is not None:
        if breadth > 0.15:
            tone = "a genuinely green day"
        elif breadth < -0.15:
            tone = "a real down day"
        elif abs(breadth) <= 0.05:
            tone = "dead flat"
        else:
            tone = "quiet, mildly " + ("positive" if breadth > 0 else "negative")
        lines.append(f"SPY is {breadth:+.2f}% from today's open -- {tone}.")

    syms = scan["symbols"]
    in_zone = [s for s in syms if s.get("distance_pct") == 0 and not s.get("narrow")]
    narrow = [s for s in syms if s.get("narrow")]
    tradeable = [s for s in syms if not s.get("narrow")]

    if in_zone:
        names = ", ".join(s["symbol"] for s in in_zone)
        lines.append(f"{names} {'is' if len(in_zone) == 1 else 'are'} sitting in Buy Zone right now -- that's a live candidate, watch for a fill.")
    else:
        candidates = [s for s in tradeable if s.get("distance_pct") is not None]
        if candidates:
            closest = min(candidates, key=lambda s: s["distance_pct"])
            lines.append(f"Nothing's in Buy Zone right now. {closest['symbol']} is closest, "
                         f"{closest['distance_pct']:.1f}% above its zone.")
        else:
            lines.append("Nothing's in Buy Zone right now, and nothing else is close enough to call out.")

    if narrow:
        names = ", ".join(s["symbol"] for s in narrow)
        lines.append(f"{names} {'is' if len(narrow) == 1 else 'are'} sitting out today -- "
                      f"{'its' if len(narrow) == 1 else 'their'} range is too narrow to trust, not worth chasing.")

    if weekly_status and "PAUSING" in weekly_status.upper():
        lines.append("Heads up: the weekly win-rate breaker is active, so no new entries today regardless of signals.")
    if earnings_blackout:
        lines.append(f"{', '.join(earnings_blackout)} blacked out for earnings -- skipping those even if they'd otherwise qualify.")

    managed = scan.get("managed")
    if managed:
        lines.append(f"Currently holding {managed} position{'s' if managed != 1 else ''} -- managing it, not adding to it.")

    return " ".join(lines)

def read_watchlist_state():
    """Eva's real watchlist plus how it has actually changed -- and the FULL
    screener universe, not just the 7 currently live.

    watchlist_manager's rails only ever promote 1-for-1: a symbol can sit in
    screener-latest.json with a great backtested P&L for weeks without ever
    making the cut, because MAX_SWAPS=2/run and a symbol only gets swapped in
    when the screener actually proposes it over a live incumbent. Without
    this, that whole evaluated universe -- and Eva's own read of why each one
    is or isn't live -- was invisible; the dashboard only ever showed the 7.

    Read-only, and defensive: watchlist_manager and the screener own these
    files. If anything here fails, the dashboard shows no watchlist section
    rather than taking the trading bot down with it.
    """
    try:
        import watchlist_manager
        state = watchlist_manager.read_state()
        hist = state.get("history", [])[:8]
        live = set(state.get("symbols", []))

        base_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_watchlist")

        nightly = None
        try:
            p = os.path.join(base_dir, "nightly_status.json")
            if os.path.exists(p):
                with open(p) as f:
                    nightly = json.load(f)
        except Exception:
            nightly = None

        # The full candidate board -- every symbol the screener actually
        # backtested, ranked by real P&L, flagged as live or not.
        candidates = None
        try:
            p = os.path.join(base_dir, "screener-latest.json")
            if os.path.exists(p):
                with open(p) as f:
                    raw = json.load(f)
                results = sorted(raw.get("results", []),
                                  key=lambda r: r.get("pnl", 0), reverse=True)
                for r in results:
                    r["live"] = r.get("symbol") in live
                candidates = {
                    "generated_at": raw.get("generated_at"),
                    "universe_size": raw.get("universe_size", len(results)),
                    "results": results,
                }
        except Exception:
            candidates = None

        return {
            "symbols": state.get("symbols", []),
            "updated": state.get("updated"),
            "history": hist,
            "nightly": nightly,
            "candidates": candidates,
            "max_swaps": getattr(watchlist_manager, "MAX_SWAPS", None),
        }
    except Exception:
        return None


LIVE_SCAN_STATUS_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "_scheduled_state", "live-scan-status.json")

def read_live_scan_status():
    """The scheduled eva-live-scan task's own real status, written fresh
    every real pass (see eva_live_scan_task.md). Preferred over the old
    log-parsed scan once it exists: sage_bot_v13.py was retired 2026-08-28
    in favor of this task, so that log will never advance again -- without
    this, the dashboard would show 2026-08-28's last scan forever, frozen,
    even while the new system is really trading."""
    try:
        with open(LIVE_SCAN_STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return None

def live_scan_fresh(status, max_age_seconds=420):
    """420s = 7 min, generous margin over the task's real 5-min cadence."""
    if not status or not status.get("generated_at"):
        return False
    try:
        age = (datetime.now().astimezone() - datetime.fromisoformat(status["generated_at"])).total_seconds()
        return 0 <= age < max_age_seconds
    except Exception:
        return False

def build_status():
    live_status = read_live_scan_status()
    trades = read_csv_rows(TRADE_LOG)
    journal = read_csv_rows(JOURNAL_LOG)
    reviews = read_csv_rows(FLOOR_LEAD_LOG)
    today = today_str()
    todays_trades = [t for t in trades if t.get("Date") == today]
    todays_reviews = [r for r in reviews if r.get("Date") == today]

    # Only trust live-scan-status.json while it is genuinely FRESH.
    #
    # Fixed 2026-09-01: this branch used to win on `is not None`, so once the
    # eva-live-scan scheduled task was deleted, the city pinned itself to that
    # task's last write (scan #4, a day old) and reported bot_alive=False --
    # while the real standalone bot was running scan #200 in the same minute.
    # A dead file must never outrank a live one.
    if live_status is not None and live_scan_fresh(live_status):
        # eva-live-scan already resolves buy_low/buy_high/target/narrow/
        # distance_pct itself (it has the real day's levels in hand when it
        # writes this), so no log-banner merge is needed here.
        scan = {k: live_status[k] for k in
                ("scan_num", "time", "buying_power", "managed", "room_for", "breadth", "symbols",
                 "market_closed", "window_closed")
                if k in live_status}
        earnings_blackout = live_status.get("earnings_blackout", [])
        weekly_status = live_status.get("weekly_status")
        bot_alive = live_scan_fresh(live_status)
    else:
        # Legacy path -- the old standalone sage_bot_v13.py log format.
        # Kept working in case that script is ever run by hand again.
        scan = parse_latest_scan()
        daily = parse_daily_status()
        if scan:
            for s in scan.get("symbols", []):
                lv = daily["levels"].get(s["symbol"])
                if lv:
                    s["buy_low"] = lv["buy_low"]
                    s["buy_high"] = lv["buy_high"]
                    s["target"] = lv["target"]
                    s["narrow"] = lv["narrow"]
                    if lv["buy_low"] <= s["price"] <= lv["buy_high"]:
                        s["distance_pct"] = 0.0
                    elif s["price"] > lv["buy_high"] and lv["buy_high"] > 0:
                        s["distance_pct"] = round((s["price"] - lv["buy_high"]) / lv["buy_high"] * 100, 2)
                    else:
                        s["distance_pct"] = None
        earnings_blackout = daily["earnings_blackout"]
        weekly_status = daily["weekly_status"]
        bot_alive = bot_process_alive()

    return {
        "generated_at": datetime.now().astimezone().isoformat(),
        "bot_alive": bot_alive,
        "scan": scan,
        "earnings_blackout": earnings_blackout,
        "weekly_status": weekly_status,
        "todays_trades": todays_trades,
        "todays_reviews": todays_reviews,
        "recent_trades": trades[-10:][::-1],
        "recent_journal": journal[-7:][::-1],
        "mechanics": read_mechanic_status(),
        "watchlist": read_watchlist_state(),
        "equity_curve": build_equity_curve(trades),
        "market_update": generate_market_update(scan, weekly_status, earnings_blackout),
    }

DASHBOARD_HTML = """<!doctype html>
<html><head><meta charset="utf-8"><title>Eva Trading Dashboard</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    color-scheme: dark;
    --bg: #01130a; --bg-elev: #041f10; --border: #1f5c33; --border-soft: #123a20;
    --text: #b9ffce; --text-dim: #5fa87d; --text-faint: #2f6844;
    --green: #39ff6a; --green-dim: #0e3d1e; --red: #ff4136; --red-dim: #3d0f0c;
    --amber: #ffb300; --amber-dim: #402c00; --accent: #39ff6a;
  }
  * { box-sizing: border-box; }
  @keyframes flicker { 0%,100% { opacity: 1; } 50% { opacity: .985; } }
  @keyframes pulse { 0%,100% { opacity: 1; } 50% { opacity: .35; } }
  @keyframes blink { 0%,49% { opacity: 1; } 50%,100% { opacity: 0; } }
  html { background: #000; }
  body {
    margin: 0; font-family: "SF Mono", "Menlo", "Monaco", "Consolas", "Courier New", monospace;
    background: radial-gradient(ellipse 140% 100% at 50% 0%, #062a14 0%, var(--bg) 60%, #000 100%);
    color: var(--text); padding: 22px; animation: flicker 6s infinite;
    position: relative; min-height: 100vh;
  }
  body::before {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 50;
    background: repeating-linear-gradient(0deg, rgba(0,0,0,.28) 0px, rgba(0,0,0,.28) 1px, transparent 1px, transparent 3px);
    mix-blend-mode: multiply;
  }
  body::after {
    content: ""; position: fixed; inset: 0; pointer-events: none; z-index: 51;
    box-shadow: inset 0 0 180px 40px rgba(0,0,0,.75);
  }
  .num { font-variant-numeric: tabular-nums; }
  header { display: flex; align-items: center; justify-content: space-between; margin-bottom: 26px;
           flex-wrap: wrap; gap: 12px; border-bottom: 1px solid var(--border); padding-bottom: 16px; }
  .brand { display: flex; align-items: center; gap: 14px; }
  .mark { width: 38px; height: 38px; border: 2px solid var(--green); display: flex; align-items: center; justify-content: center;
          background: var(--green-dim); font-weight: 700; font-size: 16px; color: var(--green);
          text-shadow: 0 0 8px var(--green); box-shadow: 0 0 12px rgba(57,255,106,.35); }
  h1 { font-size: 17px; margin: 0; font-weight: 700; letter-spacing: .08em; text-transform: uppercase;
       color: var(--green); text-shadow: 0 0 8px rgba(57,255,106,.55); }
  h1::before { content: "$ "; color: var(--text-faint); text-shadow: none; }
  h1::after { content: "\\2588"; margin-left: 6px; color: var(--green); animation: blink 1s step-start infinite; }
  .terminal-frame {
    max-width: 1400px; margin: 0 auto; border: 2px solid var(--border); background: var(--bg);
    box-shadow: 0 0 0 1px rgba(57,255,106,.08), 0 24px 70px rgba(0,0,0,.65), 0 0 46px rgba(57,255,106,.07);
    position: relative;
  }
  .term-titlebar {
    display: flex; align-items: center; gap: 8px; padding: 10px 14px;
    background: var(--bg-elev); border-bottom: 1px solid var(--border);
  }
  .term-dot { width: 11px; height: 11px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .term-dot-r { background: #a84a44; box-shadow: 0 0 5px rgba(255,95,86,.35); }
  .term-dot-y { background: #a88a3a; box-shadow: 0 0 5px rgba(255,189,46,.35); }
  .term-dot-g { background: var(--green); box-shadow: 0 0 6px var(--green); }
  .term-title {
    flex: 1; text-align: center; margin-right: 45px; color: var(--text-faint);
    font-size: 11px; letter-spacing: .05em;
  }
  .term-body { padding: 26px 30px 44px; }
  .sub { color: var(--text-dim); font-size: 12px; margin-top: 3px; letter-spacing: .02em; }
  .status-pill { display: inline-flex; align-items: center; gap: 8px; padding: 7px 14px 7px 11px;
                 background: var(--bg-elev); border: 1px solid var(--border); font-size: 12px;
                 text-transform: uppercase; letter-spacing: .06em; }
  .dot { width: 9px; height: 9px; border-radius: 50%; display: inline-block; flex-shrink: 0; }
  .dot.live { background: var(--green); box-shadow: 0 0 10px var(--green); animation: pulse 2s ease-in-out infinite; }
  .dot.dead { background: var(--red); box-shadow: 0 0 10px var(--red); }
  .grid { display: grid; grid-template-columns: repeat(auto-fit, minmax(230px, 1fr)); gap: 14px; margin-bottom: 16px; }
  .grid.g2 { grid-template-columns: repeat(auto-fit, minmax(340px, 1fr)); }
  .card { background: linear-gradient(180deg, rgba(57,255,106,.03), transparent 40%), var(--bg-elev);
          border: 1px solid var(--border); padding: 18px; position: relative;
          box-shadow: inset 0 0 0 1px rgba(57,255,106,.06), 0 0 18px rgba(0,0,0,.5); }
  .card::before {
    content: ""; position: absolute; top: -1px; left: -1px; right: -1px; height: 3px;
    background: linear-gradient(90deg, var(--green), transparent 70%); opacity: .55;
  }
  .card h2 { font-size: 11px; text-transform: uppercase; letter-spacing: .12em; color: var(--text-dim);
             margin: 0 0 14px; font-weight: 700; }
  .card h2::before { content: "// "; color: var(--border); }
  .stat { font-size: 30px; font-weight: 700; letter-spacing: -.01em; text-shadow: 0 0 10px currentColor; }
  .stat.pos { color: var(--green); } .stat.neg { color: var(--red); } .stat.flat { color: var(--text); text-shadow: 0 0 6px rgba(185,255,206,.3); }
  .stat-sub { color: var(--text-dim); margin-top: 7px; font-size: 12px; }
  table { width: 100%; border-collapse: collapse; font-size: 12.5px; }
  th, td { text-align: left; padding: 9px 10px; border-bottom: 1px solid var(--border-soft); }
  tbody tr:last-child td { border-bottom: none; }
  tbody tr { transition: background .1s ease; }
  tbody tr:hover { background: rgba(57,255,106,.05); }
  th { color: var(--text-dim); font-weight: 700; font-size: 10.5px; text-transform: uppercase; letter-spacing: .08em; }
  .zone-pill { display: inline-block; padding: 2px 9px; border: 1px solid currentColor; font-size: 10.5px; font-weight: 700;
               text-transform: uppercase; letter-spacing: .04em; }
  .zone-BUY { background: var(--green-dim); color: var(--green); text-shadow: 0 0 6px var(--green); }
  .zone-KILL { background: #0a1c11; color: var(--text-faint); border-color: var(--border); }
  .zone-SELL { background: var(--amber-dim); color: var(--amber); }
  .narrow-badge { color: var(--text-faint); font-size: 10px; margin-left: 6px; text-transform: uppercase; letter-spacing: .04em; }
  .dist-in { color: var(--green); font-weight: 700; text-shadow: 0 0 6px var(--green); }
  .dist-far { color: var(--text-dim); }
  .badge { display: inline-block; padding: 3px 9px; border: 1px solid currentColor; font-size: 10.5px; font-weight: 700;
           text-transform: uppercase; letter-spacing: .04em; }
  .badge.win { background: var(--green-dim); color: var(--green); }
  .badge.loss { background: var(--red-dim); color: var(--red); }
  .flag { color: var(--amber); font-weight: 700; text-shadow: 0 0 6px var(--amber); }
  .muted { color: var(--text-dim); }
  .footer { color: var(--text-faint); font-size: 11px; margin-top: 26px; text-align: center; text-transform: uppercase; letter-spacing: .05em; }
  .mech-row { display: flex; justify-content: space-between; align-items: flex-start; gap: 12px; padding: 12px 0;
              border-bottom: 1px solid var(--border-soft); }
  .mech-row:last-child { border-bottom: none; padding-bottom: 0; }
  .mech-row:first-child { padding-top: 0; }
  .mech-name { font-weight: 700; font-size: 13px; text-transform: uppercase; letter-spacing: .03em; }
  .mech-time { color: var(--text-dim); font-size: 11px; margin-top: 3px; }
  .mech-summary { color: var(--text); opacity: .8; font-size: 12px; margin-top: 5px; max-width: 460px; line-height: 1.4; }
  .mech-badge { padding: 4px 11px; border: 1px solid currentColor; font-size: 10.5px; font-weight: 700; white-space: nowrap;
                text-transform: uppercase; letter-spacing: .04em; }
  .mech-badge.healthy { background: var(--green-dim); color: var(--green); }
  .mech-badge.fixed { background: var(--amber-dim); color: var(--amber); }
  .mech-badge.needs_attention { background: var(--red-dim); color: var(--red); }
  .mech-badge.unknown { background: #0a1c11; color: var(--text-dim); }
  .risk-row { display: flex; justify-content: space-between; align-items: center; padding: 10px 0;
              border-bottom: 1px solid var(--border-soft); font-size: 13px; }
  .risk-row:last-child { border-bottom: none; }
  .risk-label { color: var(--text-dim); font-size: 12px; text-transform: uppercase; letter-spacing: .03em; }
  .ok-pill { color: var(--green); font-size: 12px; font-weight: 700; text-shadow: 0 0 6px var(--green); }
  .warn-pill { color: var(--amber); font-size: 12px; font-weight: 700; text-shadow: 0 0 6px var(--amber); }
  #equity-svg { width: 100%; height: 120px; display: block; }
  .empty-state { color: var(--text-dim); font-size: 12.5px; padding: 20px 0; text-align: center; }
  .eva-update { background: linear-gradient(180deg, rgba(57,255,106,.05), transparent 40%), var(--bg-elev); border-color: var(--green); }
  .eva-update-head { display: flex; align-items: center; gap: 10px; margin-bottom: 10px; }
  .eva-update h2 { text-transform: uppercase; letter-spacing: .1em; font-size: 12px; color: var(--green); text-shadow: 0 0 6px var(--green); }
  .eva-update h2::before { content: ""; }
  #market-update { margin: 0; font-size: 13.5px; line-height: 1.7; color: var(--text); }
  #market-update::after { content: "\\2588"; color: var(--green); animation: blink 1s step-start infinite; margin-left: 2px; }
</style>
</head>
<body>
<div class="terminal-frame">
  <div class="term-titlebar">
    <span class="term-dot term-dot-r"></span><span class="term-dot term-dot-y"></span><span class="term-dot term-dot-g"></span>
    <span class="term-title">eva@robinhood -- dashboard -- 130x48</span>
  </div>
  <div class="term-body">
  <header>
    <div class="brand">
      <div class="mark">E</div>
      <div>
        <h1>Eva Trading Dashboard</h1>
        <div class="sub" id="subhead">Loading...</div>
      </div>
    </div>
    <div style="display:flex; align-items:center; gap:10px;">
      <a href="/hq/" style="color:var(--green); text-decoration:none; font-size:11px; text-transform:uppercase; letter-spacing:.06em; border:1px solid var(--border); padding:7px 12px; background:var(--bg-elev);">&#127970; Trading HQ</a>
      <a href="/town" style="color:var(--green); text-decoration:none; font-size:11px; text-transform:uppercase; letter-spacing:.06em; border:1px solid var(--border); padding:7px 12px; background:var(--bg-elev);">&#127961; Smallville</a>
      <div class="status-pill"><span id="dot" class="dot dead"></span><span id="status-text">--</span></div>
    </div>
  </header>

  <div class="card eva-update" style="margin-bottom:16px;">
    <div class="eva-update-head">
      <div class="mark" style="width:26px;height:26px;font-size:12px;flex-shrink:0;">E</div>
      <h2 style="margin:0;">Eva's Market Update</h2>
    </div>
    <p id="market-update">Loading...</p>
  </div>

  <div class="grid">
    <div class="card">
      <h2>Buying Power</h2>
      <div class="stat flat num" id="bp">--</div>
      <div class="stat-sub" id="slots"></div>
    </div>
    <div class="card">
      <h2>Today's P&amp;L</h2>
      <div class="stat flat num" id="pnl">--</div>
      <div class="stat-sub" id="trade-count"></div>
    </div>
    <div class="card">
      <h2>Market Breadth (SPY)</h2>
      <div class="stat flat num" id="breadth">--</div>
    </div>
    <div class="card">
      <h2>Total Track Record</h2>
      <div class="stat flat num" id="total-pnl">--</div>
      <div class="stat-sub" id="total-trades"></div>
    </div>
  </div>

  <div class="card" style="margin-bottom:14px;">
    <h2>Equity Curve -- cumulative P&amp;L, all trades</h2>
    <svg id="equity-svg" viewBox="0 0 800 120" preserveAspectRatio="none"></svg>
  </div>

  <div class="card" style="margin-bottom:14px;">
    <h2>Live Zones -- Scan #<span id="scan-num">--</span> (<span id="scan-time">--</span>)</h2>
    <table>
      <thead><tr><th>Symbol</th><th>Price</th><th>Zone</th><th>Buy Zone</th><th>Distance</th><th>Candle</th><th></th></tr></thead>
      <tbody id="zones-body"></tbody>
    </table>
  </div>

  <div class="grid g2" style="margin-bottom:14px;">
    <div class="card">
      <h2>Risk Status</h2>
      <div id="risk-body"></div>
    </div>
    <div class="card">
      <h2>Mechanics -- automated health checks</h2>
      <div id="mechanics-body">
        <div class="muted">Loading...</div>
      </div>
    </div>
  </div>

  <div class="grid g2">
    <div class="card">
      <h2>Today's Trade Reviews</h2>
      <table>
        <thead><tr><th>Symbol</th><th>Designed R:R</th><th>Realized R</th><th>Reason</th></tr></thead>
        <tbody id="reviews-body"></tbody>
      </table>
    </div>
    <div class="card">
      <h2>Recent Trades</h2>
      <table>
        <thead><tr><th>Date</th><th>Symbol</th><th>P&amp;L</th><th>Result</th></tr></thead>
        <tbody id="trades-body"></tbody>
      </table>
    </div>
  </div>

  <div class="footer">Auto-refreshes every 15s &middot; Read-only, reflects the live bot's own log &middot; No separate connection to Robinhood</div>
  </div>
</div>

<script>
function fmtMoney(v) {
  const n = parseFloat(v);
  const sign = n < 0 ? "-" : "+";
  return sign + "$" + Math.abs(n).toFixed(2);
}
function drawEquityCurve(curve) {
  const svg = document.getElementById("equity-svg");
  const W = 800, H = 120, pad = 8;
  if (!curve || curve.length < 2) {
    svg.innerHTML = `<text x="${W/2}" y="${H/2}" fill="#565d69" font-size="12" text-anchor="middle" dominant-baseline="middle">Not enough trades yet for a curve</text>`;
    return;
  }
  const values = curve.map(p => p.cumulative);
  const lo = Math.min(0, ...values), hi = Math.max(0, ...values);
  const range = (hi - lo) || 1;
  const x = i => pad + (i / (curve.length - 1)) * (W - pad * 2);
  const y = v => H - pad - ((v - lo) / range) * (H - pad * 2);
  const zeroY = y(0);
  const points = curve.map((p, i) => `${x(i).toFixed(1)},${y(p.cumulative).toFixed(1)}`).join(" ");
  const last = values[values.length - 1];
  const color = last >= 0 ? "#33d17a" : "#ff5c66";
  const areaPoints = `${x(0).toFixed(1)},${zeroY.toFixed(1)} ` + points + ` ${x(curve.length-1).toFixed(1)},${zeroY.toFixed(1)}`;
  svg.innerHTML = `
    <line x1="${pad}" y1="${zeroY.toFixed(1)}" x2="${W-pad}" y2="${zeroY.toFixed(1)}" stroke="#23272f" stroke-width="1" stroke-dasharray="3,3" />
    <polygon points="${areaPoints}" fill="${color}" opacity="0.12" />
    <polyline points="${points}" fill="none" stroke="${color}" stroke-width="2" stroke-linejoin="round" stroke-linecap="round" />
  `;
}
async function refresh() {
  try {
    const res = await fetch("/api/status");
    const d = await res.json();
    document.getElementById("dot").className = "dot " + (d.bot_alive ? "live" : "dead");
    document.getElementById("status-text").textContent = d.bot_alive ? "Running" : "Idle / not detected";
    document.getElementById("subhead").textContent = "Last update " + new Date(d.generated_at).toLocaleTimeString();
    document.getElementById("market-update").textContent = d.market_update || "No update available yet.";

    if (d.scan) {
      document.getElementById("scan-num").textContent = d.scan.scan_num ?? "--";
      document.getElementById("scan-time").textContent = d.scan.time ?? "--";
      document.getElementById("bp").textContent = d.scan.buying_power != null ? "$" + d.scan.buying_power.toFixed(2) : "--";
      document.getElementById("slots").textContent = d.scan.managed != null
        ? d.scan.managed + " position(s) held, room for " + d.scan.room_for + " more" : "";
      document.getElementById("breadth").textContent = d.scan.breadth != null ? (d.scan.breadth >= 0 ? "+" : "") + d.scan.breadth.toFixed(2) + "%" : "--";
      const bEl = document.getElementById("breadth");
      bEl.className = "stat num " + (d.scan.breadth > 0 ? "pos" : d.scan.breadth < 0 ? "neg" : "flat");

      const zbody = document.getElementById("zones-body");
      zbody.innerHTML = "";
      (d.scan.symbols || []).forEach(s => {
        const tr = document.createElement("tr");
        const buyZoneTxt = (s.buy_low != null) ? `$${s.buy_low.toFixed(2)}-$${s.buy_high.toFixed(2)}` : "--";
        const narrowTxt = s.narrow ? '<span class="narrow-badge">too narrow</span>' : "";
        let distTxt = "--";
        if (s.distance_pct === 0) distTxt = '<span class="dist-in">in zone</span>';
        else if (s.distance_pct != null) distTxt = `<span class="dist-far">${s.distance_pct.toFixed(1)}% away</span>`;
        tr.innerHTML = `<td>${s.symbol}</td><td class="num">$${s.price.toFixed(2)}</td>` +
          `<td><span class="zone-pill zone-${s.zone}">${s.zone}</span>${narrowTxt}</td>` +
          `<td class="num muted">${buyZoneTxt}</td><td class="num">${distTxt}</td>` +
          `<td>${s.candle}${s.lowvol ? " (lowvol)" : ""}</td>` +
          `<td>${s.entry_flag ? '<span class="flag">⚡ ENTRY</span>' : ""}</td>`;
        zbody.appendChild(tr);
      });
    }

    const riskBody = document.getElementById("risk-body");
    const blackout = d.earnings_blackout || [];
    riskBody.innerHTML = `
      <div class="risk-row">
        <span class="risk-label">Weekly win-rate breaker</span>
        <span class="${(d.weekly_status || "").includes("PAUSING") ? "warn-pill" : "ok-pill"}">${d.weekly_status || "not yet checked today"}</span>
      </div>
      <div class="risk-row">
        <span class="risk-label">Earnings blackout</span>
        <span class="${blackout.length ? "warn-pill" : "ok-pill"}">${blackout.length ? blackout.join(", ") : "none active"}</span>
      </div>`;

    drawEquityCurve(d.equity_curve);
    const allTrades = d.recent_trades || [];
    const totalPnl = (d.equity_curve && d.equity_curve.length) ? d.equity_curve[d.equity_curve.length - 1].cumulative : 0;
    const totalEl = document.getElementById("total-pnl");
    totalEl.textContent = fmtMoney(totalPnl);
    totalEl.className = "stat num " + (totalPnl > 0 ? "pos" : totalPnl < 0 ? "neg" : "flat");
    document.getElementById("total-trades").textContent = (d.equity_curve ? d.equity_curve.length : 0) + " trade(s) all-time";

    const todaysTrades = d.todays_trades || [];
    const pnl = todaysTrades.reduce((sum, t) => sum + parseFloat(t["P&L"] || 0), 0);
    const pnlEl = document.getElementById("pnl");
    pnlEl.textContent = todaysTrades.length ? fmtMoney(pnl) : "$0.00";
    pnlEl.className = "stat num " + (pnl > 0 ? "pos" : pnl < 0 ? "neg" : "flat");
    document.getElementById("trade-count").textContent = todaysTrades.length + " trade(s) today";

    const mech = d.mechanics || {};
    const mechBody = document.getElementById("mechanics-body");
    const mechDefs = [
      { key: "morning", label: "Morning check", schedule: "weekdays ~6:29 AM -- did Eva start today?" },
      { key: "hourly", label: "Hourly check", schedule: "weekdays ~7:33 AM-1:33 PM, every hour -- is Eva still running?" },
    ];
    mechBody.innerHTML = "";
    mechDefs.forEach(def => {
      const m = mech[def.key];
      const status = m ? m.status : "unknown";
      const label = { healthy: "Healthy", fixed: "Fixed", needs_attention: "Needs attention", unknown: "No runs yet" }[status] || status;
      const when = m && m.last_run ? new Date(m.last_run).toLocaleString() : "--";
      const summary = m && m.summary ? m.summary : def.schedule;
      const row = document.createElement("div");
      row.className = "mech-row";
      row.innerHTML = `<div>
          <div class="mech-name">${def.label}</div>
          <div class="mech-time">Last run: ${when}</div>
          <div class="mech-summary">${summary}</div>
        </div>
        <span class="mech-badge ${status}">${label}</span>`;
      mechBody.appendChild(row);
    });

    const rbody = document.getElementById("reviews-body");
    rbody.innerHTML = "";
    (d.todays_reviews || []).forEach(r => {
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${r.Symbol}</td><td>${r.DesignedRR || "-"}</td><td>${r.RealizedR || "-"}</td><td>${r.Reason}</td>`;
      rbody.appendChild(tr);
    });
    if (!d.todays_reviews || !d.todays_reviews.length) {
      rbody.innerHTML = '<tr><td colspan="4" class="muted">No completed trades yet today</td></tr>';
    }

    const tbody = document.getElementById("trades-body");
    tbody.innerHTML = "";
    (d.recent_trades || []).forEach(t => {
      const win = t["Win/Loss"] === "WIN";
      const tr = document.createElement("tr");
      tr.innerHTML = `<td>${t.Date}</td><td>${t.Symbol}</td><td>${fmtMoney(t["P&L"])}</td>` +
        `<td><span class="badge ${win ? "win" : "loss"}">${t["Win/Loss"]}</span></td>`;
      tbody.appendChild(tr);
    });
  } catch (e) {
    document.getElementById("subhead").textContent = "Dashboard server unreachable: " + e;
    document.getElementById("dot").className = "dot dead";
  }
}
refresh();
setInterval(refresh, 15000);
</script>
</body></html>
"""

TOWN_HTML = """<!doctype html>
<html>
<head>
<meta charset="utf-8">
<title>Smallville -- Eva's Town</title>
<meta name="viewport" content="width=device-width, initial-scale=1">
<style>
  :root {
    --grass1: #4a934a; --grass2: #57a157; --path: #d8c48a; --path-edge: #b89f66;
    --wood: #6b4a2f; --roof-red: #b3453a; --roof-blue: #3a6fa8; --roof-purple: #7a4fa0;
    --roof-green: #3f8f5c; --wall: #ece2c8; --night: #0c1030; --ink: #1c1712;
    --curb: #8f8f96; --curb-dark: #6b6b71; --lane: #f2d24b;
  }
  * { box-sizing: border-box; }
  body {
    margin: 0; background: #0c1030; font-family: "Courier New", "SF Mono", monospace;
    color: #f4ecd8; padding: 18px; min-height: 100vh;
  }
  .town-frame { max-width: 1480px; margin: 0 auto; }
  .town-topbar {
    display: flex; align-items: center; justify-content: space-between; margin-bottom: 14px;
  }
  .town-topbar a {
    color: #f4ecd8; text-decoration: none; font-size: 14px; padding: 8px 16px;
    border: 2px solid #f4ecd8; background: #1c1712;
  }
  .town-topbar a:hover { background: #f4ecd8; color: #1c1712; }
  .town-title {
    font-size: 27px; font-weight: 700; letter-spacing: .12em; text-align: center;
    text-shadow: 2px 0 #b3453a, -2px 0 #3a6fa8, 0 2px #3f8f5c, 0 -2px #7a4fa0;
    color: #fff;
  }
  .town-sub { text-align: center; font-size: 13px; color: #a99fc9; margin-top: -6px; margin-bottom: 12px; letter-spacing: .04em; }

  .scene {
    position: relative; width: 1400px; height: 980px; overflow: hidden;
    border: 5px solid #1c1712; box-shadow: 0 0 0 2px #6b4a2f, 0 24px 70px rgba(0,0,0,.6);
    background-image: url(__GRASS__);
    background-size: 30px 30px; image-rendering: pixelated;
  }
  .scene-scroll { overflow-x: auto; }

  .plaza {
    position: absolute; left: 50px; top: 260px; width: 1300px; height: 460px;
    background-image: url(__ASPHALT__); background-size: 30px 30px; image-rendering: pixelated;
    border: 7px solid var(--curb); border-radius: 26px;
    box-shadow: inset 0 0 0 4px var(--curb-dark), inset 0 0 0 8px rgba(0,0,0,.15);
  }
  .main-street {
    position: absolute; left: 640px; top: 200px; width: 80px; height: 60px;
    background-image: url(__ASPHALT__); background-size: 30px 30px; image-rendering: pixelated;
    border-left: 7px solid var(--curb); border-right: 7px solid var(--curb);
  }
  .residential-road {
    position: absolute; left: 50px; top: 720px; width: 1300px; height: 40px;
    background-image: url(__ASPHALT__); background-size: 30px 30px; image-rendering: pixelated;
    border-top: 7px solid var(--curb); border-bottom: 7px solid var(--curb);
  }
  .driveway {
    position: absolute; width: 22px; height: 16px; top: -14px; left: 50%; transform: translateX(-50%);
    background-image: url(__ASPHALT__); background-size: 30px 30px; image-rendering: pixelated;
    border-left: 3px solid var(--curb); border-right: 3px solid var(--curb);
  }
  .road-line {
    position: absolute; background: repeating-linear-gradient(90deg, var(--lane) 0 20px, transparent 20px 38px);
    height: 5px; z-index: 2;
  }
  .road-line.vertical {
    background: repeating-linear-gradient(180deg, var(--lane) 0 20px, transparent 20px 38px);
    width: 5px; height: auto;
  }

  .bld { position: absolute; text-align: center; transition: filter .3s ease; }
  .bld .label {
    font-size: 13px; margin-top: 5px; color: #fff; text-shadow: 1px 1px 0 #000;
    letter-spacing: .03em; white-space: nowrap; font-weight: 700;
    background: rgba(20, 15, 10, .55); padding: 2px 7px; border-radius: 4px; display: inline-block;
  }
  .bld .sign {
    font-size: 11px; color: #ffe9a8; text-shadow: 1px 1px 0 #000; margin-top: 3px; white-space: nowrap;
    background: rgba(20, 15, 10, .5); padding: 1px 6px; border-radius: 3px; display: inline-block;
  }
  .bld-img {
    image-rendering: pixelated; display: block; margin: 0 auto;
    filter: drop-shadow(3px 5px 3px rgba(0,0,0,.4));
  }

  /* Hall (Eva's Trading Hall) */
  .hall { left: 580px; top: 30px; width: 240px; }
  .hall .bld-img { width: 240px; height: 170px; }

  /* generic small house */
  .house { width: 140px; }
  .house .bld-img { width: 140px; height: 120px; }
  .house.narrow-h { filter: grayscale(0.6) brightness(0.85); }
  .house .banner {
    position: absolute; top: -18px; left: 50%; transform: translateX(-50%) rotate(-3deg);
    background: #c0392b; color: #fff; font-size: 10px; font-weight: 700; padding: 2px 7px; border: 1px solid #7a1f16;
    white-space: nowrap; display: none; z-index: 5; border-radius: 3px;
  }
  .house.narrow-h .banner { display: block; }
  .house.firing { animation: pulseGlow 1s ease-in-out infinite; }
  @keyframes pulseGlow { 0%,100% { filter: drop-shadow(0 0 0 rgba(57,255,106,0)); } 50% { filter: drop-shadow(0 0 16px rgba(57,255,106,.85)); } }
  .spark { position: absolute; top: -26px; left: 50%; transform: translateX(-50%); font-size: 16px; display: none; animation: bob 0.6s ease-in-out infinite; z-index: 5; }
  .house.firing .spark { display: block; }
  @keyframes bob { 0%,100% { transform: translate(-50%, 0); } 50% { transform: translate(-50%, -5px); } }

  /* cafe */
  .cafe { width: 150px; }
  .cafe .bld-img { width: 150px; height: 115px; }

  /* grocery */
  .grocery { width: 150px; }
  .grocery .bld-img { width: 150px; height: 115px; }

  /* sheriff / fire (civic buildings) */
  .sheriff, .firehouse { width: 130px; }
  .sheriff .bld-img, .firehouse .bld-img { width: 130px; height: 115px; }

  /* park */
  .park { width: 280px; height: 148px; }
  .park .patch {
    width: 280px; height: 132px; background-image: url(__GRASS__); background-size: 30px 30px;
    image-rendering: pixelated; border-radius: 50%; border: 3px solid #3a7a3a;
  }
  .tree { position: absolute; }
  .tree img { width: 45px; height: 55px; image-rendering: pixelated; }
  .pond {
    position: absolute; width: 74px; height: 40px; border-radius: 50%; border: 3px solid #2f7ba8;
    background-image: url(__WATER__); background-size: 20px 20px; image-rendering: pixelated;
  }
  .bench img { width: 40px; height: 20px; image-rendering: pixelated; }

  /* homes -- one per trader, residential row south of the town square */
  .home { width: 115px; }
  .home .bld-img { width: 115px; height: 105px; }
  .residential-label {
    position: absolute; left: 50px; color: #cfead0; font-size: 11px; letter-spacing: .1em;
    text-transform: uppercase; opacity: .55;
  }

  /* notice board */
  .noticeboard {
    position: absolute; left: 50px; top: 34px; width: 230px; background: #6b4a2f; border: 3px solid #3d2a1a;
    padding: 9px 12px; font-size: 12px; color: #fff8e0; box-shadow: 0 5px 0 rgba(0,0,0,.3); border-radius: 3px;
  }
  .noticeboard .nb-head { font-size: 10.5px; color: #ffe9a8; letter-spacing: .08em; margin-bottom: 5px; }
  .noticeboard .nb-line { min-height: 16px; }

  /* character tokens -- Eva, traders, sheriff, firefighter all share this */
  .person { position: absolute; width: 44px; text-align: center;
    transition: left 1.6s cubic-bezier(.45,.05,.55,.95), top 1.6s cubic-bezier(.45,.05,.55,.95); }
  .person img { width: 44px; height: 50px; image-rendering: pixelated; position: relative; z-index: 2; }
  .person::before {
    content: ""; position: absolute; left: 50%; bottom: 3px; width: 26px; height: 8px;
    background: rgba(0,0,0,.35); border-radius: 50%; transform: translateX(-50%); z-index: 1;
  }
  .person-bubble {
    position: absolute; top: -26px; left: 50%; transform: translateX(-50%); font-size: 11.5px;
    font-weight: 700; color: #1c1712; white-space: nowrap; z-index: 4;
    background: #fff8ec; padding: 3px 8px; border-radius: 8px; border: 2px solid #1c1712;
    box-shadow: 0 2px 0 rgba(0,0,0,.25);
  }
  .person-bubble::after {
    content: ""; position: absolute; bottom: -7px; left: 50%; transform: translateX(-50%);
    border-left: 5px solid transparent; border-right: 5px solid transparent; border-top: 6px solid #1c1712;
  }
  .person-bubble::before {
    content: ""; position: absolute; bottom: -4.5px; left: 50%; transform: translateX(-50%); z-index: 1;
    border-left: 4px solid transparent; border-right: 4px solid transparent; border-top: 5px solid #fff8ec;
  }
  .person-bubble .tag { letter-spacing: .02em; }
  .person-bubble .icon { margin-left: 3px; }
  @keyframes idlebob { 0%,100% { transform: translateY(0) rotate(0deg); } 50% { transform: translateY(-2px) rotate(0deg); } }
  @keyframes walkbob { 0%,100% { transform: translateY(0) rotate(-3deg); } 50% { transform: translateY(-5px) rotate(3deg); } }
  .person .sprite-body { animation: idlebob 1.2s ease-in-out infinite; transform-origin: 50% 90%; }
  .person.walking .sprite-body { animation: walkbob 0.28s ease-in-out infinite; }
  .person.eva { z-index: 25; }
  .person.civic { z-index: 22; }
  .person.trader { z-index: 18; }

  /* dialogue box */
  .dialogue {
    margin-top: 14px; background: #1c1712; border: 3px solid #f4ecd8; padding: 14px 18px;
    font-size: 15px; line-height: 1.65; position: relative; min-height: 66px;
  }
  .dialogue .speaker { color: #ffe9a8; font-weight: 700; letter-spacing: .05em; font-size: 13px; margin-bottom: 5px; }
  .dialogue .cursor { display: inline-block; margin-left: 4px; animation: blink 0.9s step-start infinite; }
  @keyframes blink { 0%,49% { opacity: 1; } 50%,100% { opacity: 0; } }

  .town-footer { color: #7a7396; font-size: 12px; margin-top: 12px; text-align: center; }
</style>
</head>
<body>
<div class="town-frame">
  <div class="town-topbar">
    <a href="/">&larr; Dashboard</a>
    <div><div class="town-title">SMALLVILLE</div><div class="town-sub">Eva's town -- built entirely from real bot data</div></div>
    <a href="/hq/">Trading HQ &rarr;</a>
  </div>

  <div class="scene-scroll">
  <div class="scene" id="scene">
    <div class="plaza"></div>
    <div class="main-street"></div>
    <div class="residential-road"></div>
    <div class="road-line vertical" style="left:678px; top:200px; height:60px;"></div>
    <div class="road-line" style="left:100px; top:450px; width:1200px;"></div>
    <div class="road-line" style="left:100px; top:738px; width:1200px;"></div>

    <div class="noticeboard">
      <div class="nb-head">// TOWN NOTICE BOARD</div>
      <div class="nb-line" id="nb-line">Loading...</div>
    </div>

    <div class="bld hall" id="hall-bld">
      <img class="bld-img" id="hall-img" src="__HALL_DIM__">
      <div class="label">EVA'S TRADING HALL</div>
      <div class="sign" id="hall-sign">--</div>
    </div>

    <div class="bld cafe" style="left:180px; top:484px;">
      <img class="bld-img" src="__CAFE__">
      <div class="label">THE CAFE</div>
    </div>

    <div class="bld grocery" style="left:380px; top:484px;">
      <img class="bld-img" src="__GROCERY__">
      <div class="label">GENERAL STORE</div>
      <div class="sign" id="grocery-sign">--</div>
    </div>

    <div class="bld sheriff" style="left:580px; top:484px;">
      <img class="bld-img" id="sheriff-img" src="__SHERIFF_CALM__">
      <div class="label">SHERIFF'S OFFICE</div>
      <div class="sign" id="sheriff-sign">--</div>
    </div>

    <div class="bld firehouse" style="left:760px; top:484px;">
      <img class="bld-img" id="fire-img" src="__FIRE_CALM__">
      <div class="label">FIRE STATION</div>
      <div class="sign" id="fire-sign">--</div>
    </div>

    <div class="bld park" style="left:940px; top:484px;">
      <div class="patch"></div>
      <div class="tree" style="left:2px; top:2px;"><img src="__TREE__"></div>
      <div class="tree" style="left:50px; top:-10px;"><img src="__TREE__"></div>
      <div class="tree" style="right:8px; top:8px;"><img src="__TREE__"></div>
      <div class="pond" style="left:90px; top:54px;"></div>
      <div class="bench" style="left:164px; top:44px;"><img src="__BENCH__"></div>
      <div class="label" style="margin-top:105px;">THE PARK</div>
    </div>

    <div class="residential-label" style="top:730px;">Residential District</div>
    <div id="homes"></div>

    <div id="houses"></div>
    <div id="traders"></div>
    <div id="eva-sprite"></div>
    <div id="civic-sprites"></div>
  </div>
  </div>

  <div class="dialogue">
    <div class="speaker">EVA</div>
    <div id="dialogue-text">Loading town data...<span class="cursor">&#9608;</span></div>
  </div>

  <div class="town-footer">Auto-refreshes every 15s &middot; read-only, same data as the main dashboard &middot; Eva's location, lit windows, and dialogue are all computed directly from real bot state -- nothing here is generated or invented</div>
</div>

<script>
const HOUSE_W = 140, HOUSE_H = 120, HOUSE_TOP = 300;
const HOUSE_SLOTS = [114, 286, 458, 630, 802, 974, 1146].map(left => ({left, top: HOUSE_TOP}));
const HOME_W = 115, HOME_H = 105, HOME_TOP = 760;
const HOME_SLOTS = [114, 286, 458, 630, 802, 974, 1146].map(left => ({left: left + 13, top: HOME_TOP}));
const HOME_IMGS = ["__HOME_0__", "__HOME_1__", "__HOME_2__", "__HOME_3__", "__HOME_4__", "__HOME_5__", "__HOME_6__"];

// Every building defines its own box; Eva always stands centered just below
// it on the path, so her position is derived, not hand-tuned per spot.
const BUILDINGS = {
  hall:     {left: 580, top: 30,  w: 240, h: 170},
  cafe:     {left: 180, top: 484, w: 150, h: 115},
  grocery:  {left: 380, top: 484, w: 150, h: 115},
  sheriff:  {left: 580, top: 484, w: 130, h: 115},
  fire:     {left: 760, top: 484, w: 130, h: 115},
  park:     {left: 940, top: 484, w: 280, h: 148},
};
function standSpot(b) {
  return {left: `${b.left + (b.w - 44) / 2}px`, top: `${b.top + b.h + 8}px`};
}
function offsetSpot(loc, dx) {
  return {left: `${parseFloat(loc.left) + dx}px`, top: loc.top};
}
const WALK_MS = 1650;
function placePerson(id, containerId, src, bubbleHtml, loc, cls) {
  let el = document.getElementById(id);
  if (!el) {
    const wrap = document.getElementById(containerId);
    el = document.createElement("div");
    el.id = id;
    el.className = "person " + (cls || "");
    el.innerHTML = `<div class="person-bubble"></div><div class="sprite-body"><img src="${src}"></div>`;
    wrap.appendChild(el);
    el.dataset.left = loc.left; el.dataset.top = loc.top;
    el.style.left = loc.left;
    el.style.top = loc.top;
    el.querySelector(".person-bubble").innerHTML = bubbleHtml;
    return;
  }
  el.querySelector(".person-bubble").innerHTML = bubbleHtml;
  const moved = el.dataset.left !== loc.left || el.dataset.top !== loc.top;
  if (moved) {
    el.dataset.left = loc.left; el.dataset.top = loc.top;
    el.classList.add("walking");
    clearTimeout(el._walkTimer);
    el._walkTimer = setTimeout(() => el.classList.remove("walking"), WALK_MS);
  }
  el.style.left = loc.left;
  el.style.top = loc.top;
}

function fmtMoney(v) {
  const n = parseFloat(v) || 0;
  const sign = n < 0 ? "-" : "+";
  return sign + "$" + Math.abs(n).toFixed(2);
}

function nyParts() {
  const fmt = new Intl.DateTimeFormat("en-US", {timeZone:"America/New_York", hour12:false, weekday:"short", hour:"numeric", minute:"numeric"});
  const map = {};
  fmt.formatToParts(new Date()).forEach(p => map[p.type] = p.value);
  return {weekday: map.weekday, hour: parseInt(map.hour,10), minute: parseInt(map.minute,10)};
}
function marketOpen() {
  const {weekday, hour, minute} = nyParts();
  if (weekday === "Sat" || weekday === "Sun") return false;
  const mins = hour*60+minute;
  return mins >= (9*60+30) && mins < 16*60;
}

// Each house keeps one of 3 roof-detail variants (chimney/dormer/vane) tied
// to its position, independent of its live zone-color -- 4 statuses x 3
// details, so 7 houses stay visually distinct even if several share a status.
const HOUSE_IMG = {
  buy:    ["__HOUSE_BUY_0__", "__HOUSE_BUY_1__", "__HOUSE_BUY_2__"],
  sell:   ["__HOUSE_SELL_0__", "__HOUSE_SELL_1__", "__HOUSE_SELL_2__"],
  dim:    ["__HOUSE_DIM_0__", "__HOUSE_DIM_1__", "__HOUSE_DIM_2__"],
  narrow: ["__HOUSE_NARROW_0__", "__HOUSE_NARROW_1__", "__HOUSE_NARROW_2__"],
};
const TRADER_IMGS = [
  "__TRADER_0__", "__TRADER_1__", "__TRADER_2__", "__TRADER_3__",
  "__TRADER_4__", "__TRADER_5__", "__TRADER_6__"
];

function renderHouses(symbols) {
  const container = document.getElementById("houses");
  container.innerHTML = "";
  symbols.forEach((s, i) => {
    const slot = HOUSE_SLOTS[i % HOUSE_SLOTS.length];
    const narrow = !!s.narrow;
    const firing = !!s.entry_flag;
    const statusKey = narrow ? "narrow" : (s.zone === "BUY" ? "buy" : s.zone === "SELL" ? "sell" : "dim");
    const src = HOUSE_IMG[statusKey][i % 3];
    const div = document.createElement("div");
    div.className = "bld house" + (narrow ? " narrow-h" : "") + (firing ? " firing" : "");
    div.style.left = slot.left + "px"; div.style.top = slot.top + "px";
    div.innerHTML = `
      <div class="banner">FOR LEASE -- ZONE TOO NARROW</div>
      <div class="spark">&#9889;</div>
      <img class="bld-img" src="${src}">
      <div class="label">${s.symbol}</div>
      <div class="sign">$${s.price != null ? s.price.toFixed(2) : "--"} -- ${s.zone || "--"}</div>
    `;
    container.appendChild(div);
  });
}

function renderHomes(symbols) {
  const wrap = document.getElementById("homes");
  if (wrap.childElementCount) return; // homes are static -- one-time render
  symbols.forEach((s, i) => {
    const slot = HOME_SLOTS[i % HOME_SLOTS.length];
    const div = document.createElement("div");
    div.className = "bld home";
    div.style.left = slot.left + "px"; div.style.top = slot.top + "px";
    div.innerHTML = `
      <div class="driveway"></div>
      <img class="bld-img" src="${HOME_IMGS[i % HOME_IMGS.length]}">
      <div class="label">${s.symbol}'S HOME</div>
    `;
    wrap.appendChild(div);
  });
}

// Each trader has a real daily schedule: at their stock's storefront during
// real market hours (if Eva's bot is actually alive), otherwise home or
// wandering nearby -- never fabricated, just real market-hours + bot-alive
// state translated into where they'd plausibly be.
function traderWorkLoc(i) {
  const slot = HOUSE_SLOTS[i % HOUSE_SLOTS.length];
  return offsetSpot(standSpot({left: slot.left, top: slot.top, w: HOUSE_W, h: HOUSE_H}), -26);
}
function traderHomeLoc(i) {
  const slot = HOME_SLOTS[i % HOME_SLOTS.length];
  return standSpot({left: slot.left, top: slot.top, w: HOME_W, h: HOME_H});
}
function traderBubble(s, working) {
  const tag = s.symbol || "??";
  let icon = "💬";
  if (!working) icon = "💤";
  else if (s.entry_flag) icon = "⚡";
  else if (s.narrow) icon = "😴";
  else if (s.zone === "BUY") icon = "📈";
  else if (s.zone === "SELL") icon = "💰";
  else icon = "➖";
  return `<span class="tag">${tag}</span><span class="icon">${icon}</span>`;
}

function renderTraders(data) {
  const scan = data.scan;
  const symbols = (scan && scan.symbols) ? scan.symbols : [];
  const working = marketOpen() && data.bot_alive;
  symbols.forEach((s, i) => {
    let loc;
    if (working) {
      loc = traderWorkLoc(i);
    } else {
      const base = traderHomeLoc(i);
      const jx = (Math.random() - 0.5) * 100;
      const jy = (Math.random() - 0.5) * 54;
      loc = {left: `${parseFloat(base.left) + jx}px`, top: `${parseFloat(base.top) + jy}px`};
    }
    placePerson(`trader-${i}`, "traders", TRADER_IMGS[i % TRADER_IMGS.length], traderBubble(s, working), loc, "trader");
  });
}

function evaSpot(data) {
  const open = marketOpen();
  const alive = data.bot_alive;
  const scan = data.scan;
  if (open && alive) {
    const firing = scan && scan.symbols ? scan.symbols.find(s => s.entry_flag) : null;
    if (firing) {
      const idx = scan.symbols.indexOf(firing) % HOUSE_SLOTS.length;
      const slot = HOUSE_SLOTS[idx];
      const loc = offsetSpot(standSpot({left: slot.left, top: slot.top, w: HOUSE_W, h: HOUSE_H}), 26);
      return {...loc, where: `visiting ${firing.symbol}`};
    }
    return {...standSpot(BUILDINGS.hall), where: "at the Trading Hall"};
  }
  const day = new Date().getDate();
  const b = (day % 2 === 0) ? BUILDINGS.park : BUILDINGS.cafe;
  const where = (day % 2 === 0) ? "relaxing at the Park" : "unwinding at the Cafe";
  return {...standSpot(b), where};
}

function evaBubble(where) {
  let icon = "🏛️";
  if (where.startsWith("visiting")) icon = "🎯";
  else if (where.includes("Cafe")) icon = "☕";
  else if (where.includes("Park")) icon = "🌳";
  return `<span class="tag">EVA</span><span class="icon">${icon}</span>`;
}
function renderEva(loc) {
  placePerson("eva-actual", "eva-sprite", "__EVA__", evaBubble(loc.where), loc, "eva");
}

function mechanicAlertLevel(m) {
  if (!m || !m.status || m.status === "healthy" || m.status === "unknown") return "calm";
  return "alert"; // needs_attention or fixed -- something real happened
}
function sheriffAlert(data) {
  const weekly = (data.weekly_status || "").toUpperCase();
  return weekly.includes("PAUSING") || (data.earnings_blackout || []).length > 0;
}

function renderCivic(data) {
  const mech = data.mechanics || {};
  const activeMech = (mech.hourly && mech.hourly.last_run) ? mech.hourly : (mech.morning || {});
  const fireAlert = mechanicAlertLevel(activeMech) === "alert";
  const sAlert = sheriffAlert(data);

  document.getElementById("sheriff-img").src = sAlert ? "__SHERIFF_ALERT__" : "__SHERIFF_CALM__";
  document.getElementById("fire-img").src = fireAlert ? "__FIRE_ALERT__" : "__FIRE_CALM__";

  const blackout = data.earnings_blackout || [];
  document.getElementById("sheriff-sign").textContent = sAlert
    ? (blackout.length ? `WATCHING: ${blackout.join(", ")}` : "ON PATROL -- WIN-RATE BREAKER ACTIVE")
    : "ALL QUIET";
  const fireSummary = activeMech.summary || "";
  document.getElementById("fire-sign").textContent = fireSummary
    ? (fireSummary.length > 46 ? fireSummary.slice(0, 46) + "..." : fireSummary)
    : "STANDING BY -- NO CHECKS YET TODAY";

  const sheriffLoc = sAlert ? offsetSpot(standSpot(BUILDINGS.hall), -32) : standSpot(BUILDINGS.sheriff);
  const fireLoc = fireAlert ? offsetSpot(standSpot(BUILDINGS.hall), 32) : standSpot(BUILDINGS.fire);
  const sheriffBubble = `<span class="tag">SHF</span><span class="icon">${sAlert ? "🚨" : "✅"}</span>`;
  const fireBubble = `<span class="tag">FD</span><span class="icon">${fireAlert ? "🚒" : "✅"}</span>`;
  placePerson("sheriff-person", "civic-sprites", "__SHERIFF_PERSON__", sheriffBubble, sheriffLoc, "civic");
  placePerson("fire-person", "civic-sprites", "__FIRE_PERSON__", fireBubble, fireLoc, "civic");
}

let nbMessages = ["Loading..."];
let nbIdx = 0;
function cycleNotice() {
  document.getElementById("nb-line").textContent = nbMessages[nbIdx % nbMessages.length];
  nbIdx++;
}
let nbTimer = null;

let lastData = null;

async function refresh() {
  try {
    const res = await fetch("/api/status");
    const data = await res.json();
    lastData = data;

    const scan = data.scan;
    const symbols = (scan && scan.symbols) ? scan.symbols : [];
    renderHouses(symbols);
    renderHomes(symbols);
    renderTraders(data);
    renderCivic(data);

    document.getElementById("hall-img").src = data.bot_alive ? "__HALL_LIT__" : "__HALL_DIM__";
    document.getElementById("hall-sign").textContent = scan ? `SCAN #${scan.scan_num} -- ${scan.time}` : "OFFLINE";

    const bp = scan && scan.buying_power != null ? scan.buying_power : null;
    document.getElementById("grocery-sign").textContent = bp != null ? `BUYING POWER: $${bp.toFixed(2)}` : "--";

    const todaysPnl = (data.todays_trades || []).reduce((sum, t) => sum + (parseFloat(t["P&L"]) || 0), 0);
    const totalPnl = (data.recent_trades || []).reduce((sum, t) => sum + (parseFloat(t["P&L"]) || 0), 0);
    const wins = (data.recent_trades || []).filter(t => t["Win/Loss"] === "WIN").length;
    const losses = (data.recent_trades || []).filter(t => t["Win/Loss"] === "LOSS").length;
    const breadth = scan && scan.breadth != null ? scan.breadth : null;

    nbMessages = [
      `TODAY'S P&L: ${fmtMoney(todaysPnl)}`,
      `TRACK RECORD: ${fmtMoney(totalPnl)} (${wins}W / ${losses}L)`,
      bp != null ? `BUYING POWER: $${bp.toFixed(2)}` : "BUYING POWER: --",
      breadth != null ? `SPY BREADTH: ${breadth >= 0 ? "+" : ""}${breadth.toFixed(2)}%` : "SPY BREADTH: --",
    ];
    if (!nbTimer) {
      cycleNotice();
      nbTimer = setInterval(cycleNotice, 3500);
    }

    const loc = evaSpot(data);
    renderEva(loc);
    document.getElementById("dialogue-text").innerHTML =
      (data.market_update || "Nothing to report yet.") +
      ` (Right now I'm ${loc.where}.)` +
      `<span class="cursor">&#9608;</span>`;

  } catch (e) {
    document.getElementById("dialogue-text").textContent = "Town server unreachable: " + e;
  }
}
refresh();
setInterval(refresh, 15000);

// Independent of the 15s data poll: off-duty traders get nudged around near
// home every few seconds so they visibly wander instead of standing frozen.
// Working traders are untouched here -- their position stays exactly what
// renderTraders already set from real data.
setInterval(() => {
  if (!lastData) return;
  if (marketOpen() && lastData.bot_alive) return;
  renderTraders(lastData);
}, 4000);
</script>
</body></html>
"""

for _token, _png in [
    ("__GRASS__", GRASS_PNG), ("__PATH__", PATH_PNG), ("__ASPHALT__", ASPHALT_PNG), ("__WATER__", WATER_PNG),
    ("__TREE__", TREE_PNG), ("__BENCH__", BENCH_PNG),
    ("__HALL_LIT__", HALL_LIT_PNG), ("__HALL_DIM__", HALL_DIM_PNG),
    ("__CAFE__", CAFE_PNG), ("__GROCERY__", GROCERY_PNG), ("__EVA__", EVA_PNG),
    ("__SHERIFF_CALM__", SHERIFF_CALM_PNG), ("__SHERIFF_ALERT__", SHERIFF_ALERT_PNG),
    ("__FIRE_CALM__", FIRE_CALM_PNG), ("__FIRE_ALERT__", FIRE_ALERT_PNG),
    ("__SHERIFF_PERSON__", SHERIFF_PERSON_PNG), ("__FIRE_PERSON__", FIRE_PERSON_PNG),
]:
    TOWN_HTML = TOWN_HTML.replace(_token, _durl(_png))
for _i, _png in enumerate(TRADER_PNGS):
    TOWN_HTML = TOWN_HTML.replace(f"__TRADER_{_i}__", _durl(_png))
for _i, _png in enumerate(HOME_PNGS):
    TOWN_HTML = TOWN_HTML.replace(f"__HOME_{_i}__", _durl(_png))
for _status, _pngs in HOUSE_PNGS.items():
    for _i, _png in enumerate(_pngs):
        TOWN_HTML = TOWN_HTML.replace(f"__HOUSE_{_status.upper()}_{_i}__", _durl(_png))

HQ_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hq")
HQ_TYPES = {
    ".html": "text/html; charset=utf-8",
    ".js":   "text/javascript; charset=utf-8",
    ".css":  "text/css; charset=utf-8",
    ".png":  "image/png",
    ".json": "application/json",
}

class Handler(BaseHTTPRequestHandler):
    def log_message(self, fmt, *args):
        pass  # keep the terminal quiet

    def serve_hq(self):
        """Static files for the /hq pixel-art view. Read-only, same as the
        rest of this server -- it serves files off disk and nothing else."""
        # /hq must redirect to /hq/ or the page's relative asset paths
        # (main.js, sprites/*.png) would resolve against the site root.
        if self.path.split("?", 1)[0] == "/hq":
            self.send_response(301)
            self.send_header("Location", "/hq/")
            self.end_headers()
            return
        rel = self.path[len("/hq"):].split("?", 1)[0].lstrip("/")
        if rel in ("", "/"):
            rel = "index.html"
        full = os.path.normpath(os.path.join(HQ_DIR, rel))
        # refuse anything that escapes hq/ (path traversal guard)
        if not full.startswith(HQ_DIR + os.sep):
            self.send_response(403)
            self.end_headers()
            return
        if not os.path.isfile(full):
            self.send_response(404)
            self.end_headers()
            self.wfile.write(b"Not found")
            return
        ctype = HQ_TYPES.get(os.path.splitext(full)[1].lower(), "application/octet-stream")
        with open(full, "rb") as f:
            body = f.read()
        self.send_response(200)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        if self.path == "/" or self.path == "":
            body = DASHBOARD_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/town":
            body = TOWN_HTML.encode()
            self.send_response(200)
            self.send_header("Content-Type", "text/html; charset=utf-8")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/status":
            try:
                body = json.dumps(build_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path.startswith("/api/studio/doc"):
            # Read one real studio document. studio.read_document() does the
            # sandboxing -- it resolves the real path and refuses anything
            # outside the channel folders or of a non-text type.
            from urllib.parse import urlparse, parse_qs, unquote
            q = parse_qs(urlparse(self.path).query)
            want = unquote((q.get("p") or [""])[0])
            try:
                body = json.dumps(studio.read_document(want)).encode()
                self.send_response(200)
            except ValueError as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(403)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/studio":
            # Archive Studio -- real production state for the Bedtime Archive
            # channel, read straight off the files on disk.
            try:
                # Advance the studio's shift first: clocks in at 09:00 ET with
                # the trading floor, records real stage progress, clocks out at
                # 16:00 ET. Idempotent -- each piece of work happens once a day
                # however often this endpoint is polled.
                studio.run_shift_tick()
                body = json.dumps(studio.build_studio_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/atm":
            # Sage's ATM Company -- real plan status, read straight from
            # atm_business.py. No shift tick, no side effects: this business
            # doesn't run on the trading floor's clock, and nothing here
            # auto-advances -- a step is done only when it's genuinely done.
            try:
                body = json.dumps(atm_business.build_atm_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/predictions":
            # The Prediction Desk -- a real, point-in-time snapshot of
            # Sage's actual Robinhood prediction-market account, read
            # straight from predict_business.py. No live connection: this
            # file is only ever updated by hand (via Claude + the Robinhood
            # MCP tools), never polled, same "no separate connection to
            # Robinhood" rule as the rest of this server.
            try:
                body = json.dumps(predict_business.build_predict_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/api/airport":
            # Smallville Regional -- a real, point-in-time check of Sage's
            # actual upcoming flights, read straight from
            # airport_business.py. No live connection: only updated by hand
            # (via Claude + a real Gmail search for an actual confirmation,
            # never a marketing/abandoned-cart email).
            try:
                body = json.dumps(airport_business.build_airport_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/api/sim":
            # The town's make-believe economy -- see sim_economy.py's own
            # header. Advances payday first (idempotent: once per calendar
            # month however often this is polled), same pattern as
            # /api/studio's shift tick. Nothing here touches real money.
            try:
                sim_economy.run_payday_if_due()
                body = json.dumps(sim_economy.build_economy_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path == "/crypto":

            body = crypto_desk.crypto_html().encode()

            self.send_response(200)

            self.send_header(

                "Content-Type",

                "text/html; charset=utf-8"

            )

            self.send_header(

                "Content-Length",

                str(len(body))

            )

            self.end_headers()

            self.wfile.write(body)

            return


        elif self.path == "/api/crypto":

            try:

                body = json.dumps(

                    crypto_desk.build_crypto_status()

                ).encode()

                self.send_response(200)

            except Exception as e:

                body = json.dumps(

                    {"error": str(e)}

                ).encode()

                self.send_response(500)


            self.send_header(

                "Content-Type",

                "application/json"

            )

            self.send_header(

                "Content-Length",

                str(len(body))

            )

            self.end_headers()

            self.wfile.write(body)

            return


        elif self.path == "/api/security":
            # The Field Office's real job -- see build_security_status()
            # above. Read-only, three os.stat() calls, nothing sensitive
            # ever appears in the response (not even a filename beyond what
            # SECURITY_TARGETS already declares statically in this file).
            try:
                body = json.dumps(build_security_status()).encode()
                self.send_response(200)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)

        elif self.path.startswith("/api/atm/doc"):
            # One real draft Wes has written -- sandboxed to the ATM Co.'s
            # own data dir by atm_business.read_document().
            from urllib.parse import urlparse, parse_qs, unquote
            q = parse_qs(urlparse(self.path).query)
            want = unquote((q.get("p") or [""])[0])
            try:
                body = json.dumps(atm_business.read_document(want)).encode()
                self.send_response(200)
            except ValueError as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(403)
            except Exception as e:
                body = json.dumps({"error": str(e)}).encode()
                self.send_response(500)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.end_headers()
            self.wfile.write(body)
        elif self.path == "/hq" or self.path.startswith("/hq/"):
            self.serve_hq()
        else:
            self.send_response(404)
            self.end_headers()

    def handle_tts(self):
        """POST /api/tts -- turn one news-bulletin line into real speech.
        The only route that returns audio bytes instead of JSON on success;
        every failure path (no key, bad input, ElevenLabs itself erroring)
        still returns JSON so the UI can show a real error, not silence."""
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
            text = (payload.get("text") or "").strip()
            voice = payload.get("voice") or "bull"
            if not text:
                raise ValueError("no text provided")
            audio = elevenlabs_tts(text[:500], voice)
            self.send_response(200)
            self.send_header("Content-Type", "audio/mpeg")
            self.send_header("Content-Length", str(len(audio)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(audio)
            return
        except urllib.error.HTTPError as e:
            detail = e.read().decode(errors="replace") if hasattr(e, "read") else str(e)
            body = json.dumps({"ok": False, "error": f"ElevenLabs error {e.code}: {detail[:300]}"}).encode()
            self.send_response(502)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode()
            self.send_response(400)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_POST(self):
        """The studio and the ATM Co. are the only places this server writes
        anything. The studio route writes to the channel's own idea backlog /
        outline folder; the ATM permission route only flips one boolean, and
        only because of a real click in the UI. /api/tts writes nothing --
        it only relays real bulletin text to ElevenLabs and streams back real
        audio. Nothing here can touch the trading bot."""
        if self.path == "/api/tts":
            return self.handle_tts()
        routes = {"/api/studio/idea", "/api/studio/outline", "/api/studio/report",
                  "/api/atm/permission"}
        if self.path not in routes:
            self.send_response(404); self.end_headers(); return
        try:
            n = int(self.headers.get("Content-Length") or 0)
            payload = json.loads(self.rfile.read(n) or b"{}")
            if self.path == "/api/studio/idea":
                result = studio.save_idea(
                    payload.get("title", ""), payload.get("note", ""),
                    payload.get("source", ""))
            elif self.path == "/api/studio/report":
                path = studio.write_status_report()
                result = {"path": path, "name": os.path.basename(path)}
            elif self.path == "/api/atm/permission":
                result = atm_business.set_permission(bool(payload.get("granted")))
            else:
                path = studio.generate_outline(payload.get("title", "Untitled"))
                result = {"path": path, "name": os.path.basename(path)}
            body = json.dumps({"ok": True, "result": result}).encode()
            self.send_response(200)
        except Exception as e:
            body = json.dumps({"ok": False, "error": str(e)}).encode()
            self.send_response(500)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

if __name__ == "__main__":
    server = ThreadingHTTPServer(("127.0.0.1", PORT), Handler)
    print(f"Eva dashboard running at http://localhost:{PORT}  (read-only, local only)")
    print("Ctrl+C to stop. Does not touch the live bot or Robinhood in any way.")
    server.serve_forever()
