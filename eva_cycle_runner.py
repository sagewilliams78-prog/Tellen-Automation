#!/usr/bin/env python3

import subprocess
import sys
import time
from datetime import datetime, timedelta, time as dt_time
from pathlib import Path
from zoneinfo import ZoneInfo

TZ = ZoneInfo("America/Los_Angeles")

BOT_DIR = Path(__file__).resolve().parent
# Switched to v14 on 2026-09-01. v14 = v13 plus MCP call timeouts (v13 froze
# for 7+ min holding an unmanaged position), a full decision journal, and
# config-driven filters. All risk/sizing math is byte-identical to v13.
# Rollback: change this one line back to sage_bot_v13.py.
BOT_FILE = BOT_DIR / "sage_bot_v13.py"

LAUNCH_HOUR = 6
LAUNCH_MINUTE = 30

now = datetime.now(TZ)

days_until_friday = (4 - now.weekday()) % 7
CYCLE_END = now.date() + timedelta(days=days_until_friday)

launched_dates = set()


def log(message=""):
    stamp = datetime.now(TZ).strftime("%Y-%m-%d %I:%M:%S %p %Z")
    print(f"[{stamp}] {message}", flush=True)


def bot_running():
    result = subprocess.run(
        ["pgrep", "-f", str(BOT_FILE)],
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    return result.returncode == 0


log("=" * 70)
log("EVA TRADING CYCLE RUNNER STARTED")
log(f"Cycle ends after Friday: {CYCLE_END}")
log("Scheduled launch: 6:30 AM Pacific")
log(f"Bot: {BOT_FILE}")
log("=" * 70)

while True:

    now = datetime.now(TZ)
    today = now.date()

    if today > CYCLE_END:
        log("Trading cycle complete.")
        log("Eva cycle runner shutting down.")
        break

    if today.weekday() >= 5:
        time.sleep(60)
        continue

    target = datetime.combine(
        today,
        dt_time(
            hour=LAUNCH_HOUR,
            minute=LAUNCH_MINUTE
        ),
        tzinfo=TZ,
    )

    if today in launched_dates:
        time.sleep(60)
        continue

    if now < target:

        remaining = (target - now).total_seconds()

        if remaining > 3600:
            sleep_for = 300
        elif remaining > 600:
            sleep_for = 60
        else:
            sleep_for = 10

        time.sleep(sleep_for)
        continue

    grace_end = target + timedelta(minutes=30)

    if now > grace_end:
        log(
            f"Missed today's 6:30 AM launch window. "
            f"Skipping {today}."
        )
        launched_dates.add(today)
        continue

    if bot_running():
        log("Eva v13 is already running. Duplicate launch prevented.")
        launched_dates.add(today)
        continue

    log("=" * 70)
    log("6:30 AM LAUNCH WINDOW REACHED")
    log("Starting EVA v13...")
    log("=" * 70)

    launched_dates.add(today)

    try:

        result = subprocess.run(
            [
                sys.executable,
                # -u = unbuffered. Without it Python block-buffers stdout when
                # redirected to a file, so the bot can run for minutes with an
                # empty log -- and dashboard_server.py judges liveness by log
                # mtime, so Eva shows OFFLINE while trading normally. Hit this
                # for real on 2026-09-01.
                "-u",
                str(BOT_FILE),
            ],
            cwd=str(BOT_DIR),
        )

        log(
            f"Eva exited with code "
            f"{result.returncode}"
        )

        log(
            "No automatic intraday restart will occur. "
            "Waiting for next scheduled trading day."
        )

    except Exception as e:

        log(
            f"Eva launch failed: "
            f"{type(e).__name__}: {e}"
        )

    time.sleep(60)
