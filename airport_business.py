#!/usr/bin/env python3
"""
Smallville Regional -- a real, point-in-time check of Sage's actual
upcoming flights. Same honesty rule as predict_business.py and
atm_business.py: nothing here is invented.

The real distinction this file exists to protect: a marketing or
abandoned-cart email (a travel site nagging about a search you never
booked) is NOT a flight. The first real check here (2026-10-08, via Gmail)
found 15+ CheapOair "still thinking about Nashville?" emails for an
Ontario -> Nashville search Sage never finished booking -- none of those
count, and this file's job is to only ever write a flight here when a
genuine confirmation (an e-ticket, a real airline/booking-site
confirmation number, a boarding pass) was actually found.

No live polling: there is no API that pushes "here's what's in one
traveller's inbox." This is pulled by hand (via Claude + Gmail search),
same refresh-on-request discipline as predict_business.py.

Its own folder, its own filing cabinet -- same pattern as every other real
business in this project.
"""
import json
import os
from datetime import datetime

BUSINESS_DIR = os.path.expanduser("~/Desktop/Smallville Regional")
DATA_DIR = os.path.join(BUSINESS_DIR, "_airport")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def write_flights(flights, note=""):
    """Write the result of one real Gmail check. `flights` is a list of
    dicts, each a genuine confirmed booking:
      {"date": "2026-11-24", "route": "Ontario (ONT) -> Nashville (BNA)",
       "confirmation": "I09R11", "airline": "United"}
    Pass an empty list when no real confirmation was found -- that is the
    honest result, not an error, and this function will say so rather than
    leave the previous (possibly stale) flight sitting there unexplained."""
    _ensure_dirs()
    data = {
        "flights": flights,
        "note": note,
        "as_of": datetime.now().astimezone().isoformat(),
    }
    with open(STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def build_airport_status():
    """Read-only. Returns the last real check, or loaded=False if none has
    ever been run -- the honest starting state, not an error."""
    if not os.path.exists(STATUS_FILE):
        return {"loaded": False, "data_dir": DATA_DIR}
    try:
        with open(STATUS_FILE) as f:
            data = json.load(f)
        data["loaded"] = True
        return data
    except Exception:
        return {"loaded": False, "data_dir": DATA_DIR}


if __name__ == "__main__":
    print(json.dumps(build_airport_status(), indent=2))
