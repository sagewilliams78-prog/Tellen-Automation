#!/usr/bin/env python3
"""
Sage's Prediction Desk -- a real, point-in-time snapshot of Sage's actual
Robinhood prediction-market (event contract) activity. Same honesty rule as
atm_business.py and studio.py: nothing here is invented.

Unlike the ATM Co. or the trading bot, there is no live bot behind this and
no continuous polling -- dashboard_server.py deliberately has no separate
connection to Robinhood (see its own footer note). This snapshot is pulled
by Claude, by hand, via the Robinhood MCP tools, whenever Sage asks for a
refresh -- then written here as plain JSON for the dashboard and the pixel
city to read. The "as_of" timestamp is the whole truth about freshness:
there is no promise this is current beyond that moment, and no "live" claim
is ever made about it.

There is also no tool to list open prediction-market positions or browse
available markets -- only an account-level dollar total
(event_contracts_value) and the realized-trade history. This snapshot
sticks to exactly those two real things.

Its own folder, its own filing cabinet -- same pattern as the trading bot,
the Archive Studio, and the ATM Co.: separate businesses, never sharing
files.
"""
import json
import os
from datetime import datetime

BUSINESS_DIR = os.path.expanduser("~/Desktop/Sage's Prediction Desk")
DATA_DIR = os.path.join(BUSINESS_DIR, "_predict")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")
BOARD_FILE = os.path.join(DATA_DIR, "daily_board.json")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def write_snapshot(account_label, cash, buying_power, event_contracts_value,
                    total_value, trades_window_label, trade_count,
                    net_realized, wins, losses, biggest_win, biggest_loss,
                    note=""):
    """Write one real, point-in-time pull from Robinhood. Called by hand
    (via Claude + the Robinhood MCP tools) -- never by a scheduled job,
    since dashboard_server.py has no Robinhood connection of its own and
    this file makes no network calls."""
    _ensure_dirs()
    data = {
        "account_label": account_label,
        "cash": cash,
        "buying_power": buying_power,
        "event_contracts_value": event_contracts_value,
        "total_value": total_value,
        "trades": {
            "window_label": trades_window_label,
            "count": trade_count,
            "net_realized": net_realized,
            "wins": wins,
            "losses": losses,
            "win_rate_pct": round(100 * wins / trade_count, 1) if trade_count else None,
            "biggest_win": biggest_win,
            "biggest_loss": biggest_loss,
        },
        "note": note,
        "as_of": datetime.now().astimezone().isoformat(),
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def write_daily_board(games, note="", summary=""):
    """Write today's real research board: what's actually playing today,
    real public odds, and Fay's own read -- not a guarantee, not betting
    advice, same disclaimer discipline as everything else in this project
    (see Percy's "not tax advice" and Wes's "not legal advice").

    `games` is a list of dicts, each:
      {
        "league": "NFL", "matchup": "Buccaneers @ Cowboys",
        "time_label": "8:15 PM ET",
        "odds": {"spread": "...", "moneyline": "...", "total": "..."},
        "context": "short real facts -- injuries, records, form",
        "read": "Fay's own probabilistic lean, hedged honestly",
        "sources": ["https://..."]
      }
    Pulled by hand (via Claude + WebSearch), same as write_snapshot() is
    pulled via the Robinhood MCP tools -- this file makes no network calls
    of its own."""
    _ensure_dirs()
    data = {
        "games": games,
        "note": note,
        "summary": summary,
        "as_of": datetime.now().astimezone().isoformat(),
    }
    with open(BOARD_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def _load_board():
    if not os.path.exists(BOARD_FILE):
        return None
    try:
        with open(BOARD_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def build_predict_status():
    """Read-only. Returns the last real account snapshot pulled, plus the
    last real daily research board, if either has ever been taken --
    loaded=False / board=None is the honest starting state, not an error."""
    board = _load_board()
    if not os.path.exists(STATUS_FILE):
        return {"loaded": False, "data_dir": DATA_DIR, "board": board}
    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)
        data["loaded"] = True
        data["board"] = board
        return data
    except Exception:
        return {"loaded": False, "data_dir": DATA_DIR, "board": board}


if __name__ == "__main__":
    print(json.dumps(build_predict_status(), indent=2))
