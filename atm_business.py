#!/usr/bin/env python3
"""
Sage's ATM Company -- real status for a real business that's still just a
plan. Same honesty rule as studio.py: nothing here is invented. Right now
that means every step reads "not started", because none of them are --
this file exists to be updated by hand (or by a future automation) as real
steps actually happen, never to make progress look further along than it is.

Its own folder, its own filing cabinet -- same pattern as the trading bot
and the Archive Studio: three real businesses, never sharing files.
"""
import json
import os
from datetime import datetime

BUSINESS_DIR = os.path.expanduser("~/Desktop/ATM CO. OUTPUTS")
DATA_DIR = os.path.join(BUSINESS_DIR, "_atm")
STATUS_FILE = os.path.join(DATA_DIR, "status.json")
PERMISSION_FILE = os.path.join(DATA_DIR, "permission.json")
DRAFTS_DIR = os.path.join(DATA_DIR, "drafts")
SHIFT_STATUS_FILE = os.path.join(DATA_DIR, "wes_shift_status.json")
READABLE_EXT = {".md", ".txt", ".json"}
MAX_DOC_BYTES = 400_000

# The six real steps from the research primer (published 2026-08-26), in
# order. This list is the plan; STATUS_FILE tracks which of them are
# actually done. Budget revised with Sage on 2026-10-08: the original ~$6k
# figure priced one machine, own-and-operate. Sage has since set aside
# $20,000 as holding-company capital for a multi-location rollout (see
# BUDGET_NOTE and the budget_allocation draft in DRAFTS_DIR) -- see step
# notes below.
STEPS = [
    {"id": "structure", "title": "Pick the business structure",
     "what": "Form an LLC before any money moves -- separates the machine's liability from everything else."},
    {"id": "path", "title": "Confirm own-vs-ISO",
     "what": "Own-and-operate confirmed (not ISO/placement). Budget widened 2026-10-08 from ~$6k/machine to $20k total, to cover a 3-location rollout -- see BUDGET_NOTE."},
    {"id": "location", "title": "Line up the location",
     "what": "A signed placement agreement with a real revenue-share and a realistic foot-traffic estimate, before a machine is ordered."},
    {"id": "processor", "title": "Contact 2-3 processors",
     "what": "Compare real settlement terms and surcharge splits -- not assumed numbers."},
    {"id": "legal", "title": "Confirm the state-law question",
     "what": "One real conversation with a business attorney in the placement state, specifically about ATM operation."},
    {"id": "launch", "title": "Install, load, activate",
     "what": "EMV and ADA compliance confirmed before the machine goes live."},
]

BUDGET_NOTE = (
    "$20,000 holding-company capital, confirmed with Sage 2026-10-08 -- own-and-operate "
    "path, not ISO/placement. Supersedes the original ~$6k/single-machine estimate from "
    "2026-08-26; see budget_allocation draft in DRAFTS_DIR for the line-item breakdown."
)


def _ensure_dirs():
    os.makedirs(DATA_DIR, exist_ok=True)


def load_status():
    """Which steps are actually done. Empty dict (nothing done) if the file
    doesn't exist yet -- that is the honest starting state, not an error."""
    if not os.path.exists(STATUS_FILE):
        return {}
    try:
        with open(STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def mark_step_done(step_id, note=""):
    """Record that a real step actually happened. Never call this because a
    step *should* be done by now -- only because it genuinely is, the same
    rule as every stage-detection check in studio.py."""
    valid_ids = {s["id"] for s in STEPS}
    if step_id not in valid_ids:
        raise ValueError(f"not a real step id: {step_id}")
    status = load_status()
    status[step_id] = {
        "done": True,
        "note": note,
        "when": datetime.now().astimezone().isoformat(),
    }
    _ensure_dirs()
    with open(STATUS_FILE, "w") as f:
        json.dump(status, f, indent=2)
    return status[step_id]


def load_permission():
    """Whether Wes is allowed to do anything on his own during work hours.
    Off by default -- this is the real gate, not a cosmetic label. It only
    ever changes because Sage clicked the toggle in the pixel city, which
    calls set_permission() through the dashboard server; nothing else may
    flip it."""
    if not os.path.exists(PERMISSION_FILE):
        return {"granted": False, "changed_at": None}
    try:
        with open(PERMISSION_FILE) as f:
            data = json.load(f)
        return {"granted": bool(data.get("granted")), "changed_at": data.get("changed_at")}
    except Exception:
        return {"granted": False, "changed_at": None}


def set_permission(granted):
    """The only way the toggle moves. Called from the dashboard server's
    /api/atm/permission route, which only fires on a real click in the UI --
    never called by the scheduled shift itself."""
    _ensure_dirs()
    data = {"granted": bool(granted), "changed_at": datetime.now().astimezone().isoformat()}
    with open(PERMISSION_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


DRAFT_BANNER = (
    "> **DRAFT — not legal advice, not binding, not sent.**\n"
    "> Written by the ATM Co. desk in Sage's pixel city as a starting point.\n"
    "> Nothing here has been reviewed by an attorney. Nothing here has been\n"
    "> sent to anyone or signed by anyone. Before any of this is used for\n"
    "> real: read it yourself, change what is wrong, and — for anything with\n"
    "> money or a signature attached — have a real attorney in the placement\n"
    "> state look at it first.\n"
)


def write_draft(filename, body_markdown):
    """Write one draft into the ATM Co.'s own drafts folder.

    Always prepends DRAFT_BANNER: every file this produces is a starting
    point for Sage to review, never a finished or binding document. This
    function only ever writes a file -- it cannot send an email, cannot
    sign anything, and has no network access of any kind.
    """
    if os.path.basename(filename) != filename:
        raise ValueError("drafts live flat in the drafts folder")
    os.makedirs(DRAFTS_DIR, exist_ok=True)
    path = os.path.join(DRAFTS_DIR, filename)
    with open(path, "w") as f:
        f.write(DRAFT_BANNER + "\n" + body_markdown.rstrip() + "\n")
    return path


def write_shift_status(status, summary):
    """Mirror of the studio's shift_status.json -- what Wes actually did on
    his last run, shown on the dashboard. status: worked | blocked | idle."""
    _ensure_dirs()
    data = {
        "last_run": datetime.now().astimezone().isoformat(),
        "status": status,
        "summary": summary,
    }
    with open(SHIFT_STATUS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    return data


def read_shift_status():
    """The last time Wes's scheduled shift ran, if it ever has."""
    if not os.path.exists(SHIFT_STATUS_FILE):
        return None
    try:
        with open(SHIFT_STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return None


def _kind_of(name):
    """Order matters: the most specific marker wins. "email"/"outreach" is
    checked before "location", because an outreach email about a location
    is an email draft, not location research -- the other way round
    mislabelled the outreach drafts."""
    n = name.lower()
    if "business_plan" in n: return "Business plan"
    if "agreement" in n or "contract" in n: return "Contract template"
    if "email" in n or "outreach" in n: return "Email draft"
    if "processor" in n: return "Processor research"
    if "location" in n or "criteria" in n or "scouting" in n: return "Location research"
    return "Draft"


def list_drafts():
    """Real files Wes has actually written to disk -- nothing here is
    invented or implied from a stage; either the file exists or it isn't
    listed."""
    if not os.path.isdir(DRAFTS_DIR):
        return []
    out = []
    for name in sorted(os.listdir(DRAFTS_DIR)):
        path = os.path.join(DRAFTS_DIR, name)
        if not os.path.isfile(path):
            continue
        out.append({
            "name": name,
            "path": path,
            "kind": _kind_of(name),
            "size": os.path.getsize(path),
            "when": datetime.fromtimestamp(os.path.getmtime(path)).astimezone().isoformat(),
            "readable": os.path.splitext(name)[1].lower() in READABLE_EXT,
        })
    out.sort(key=lambda d: d["when"], reverse=True)
    return out


def read_document(path):
    """Read one draft, sandboxed to this business's own data dir -- same
    resolve-then-check pattern as studio.read_document(), so a path that
    tries to escape DATA_DIR is rejected even after symlink resolution."""
    real = os.path.realpath(os.path.expanduser(path))
    root = os.path.realpath(DATA_DIR)
    if not (real == root or real.startswith(root + os.sep)):
        raise ValueError("outside the ATM Co. folder")
    if os.path.splitext(real)[1].lower() not in READABLE_EXT:
        raise ValueError("not a readable document type")
    if not os.path.isfile(real):
        raise ValueError("not found")
    size = os.path.getsize(real)
    with open(real, "r", errors="replace") as f:
        text = f.read(MAX_DOC_BYTES)
    return {
        "name": os.path.basename(real),
        "path": real,
        "kind": _kind_of(os.path.basename(real)),
        "size": size,
        "truncated": size > MAX_DOC_BYTES,
        "when": datetime.fromtimestamp(os.path.getmtime(real)).isoformat(),
        "text": text,
    }


def build_atm_status():
    status = load_status()
    steps = []
    for s in STEPS:
        real = status.get(s["id"], {})
        steps.append({**s, "done": bool(real.get("done")),
                     "note": real.get("note", ""), "when": real.get("when")})
    done_count = sum(1 for s in steps if s["done"])
    return {
        "name": "Sage's ATM Company",
        "budget_note": BUDGET_NOTE,
        "steps": steps,
        "done_count": done_count,
        "total_steps": len(steps),
        "launched": done_count == len(steps),
        "permission": load_permission(),
        "drafts": list_drafts(),
        "shift": read_shift_status(),
        "data_dir": DATA_DIR,
        "generated_at": datetime.now().astimezone().isoformat(),
    }


if __name__ == "__main__":
    print(json.dumps(build_atm_status(), indent=2))
