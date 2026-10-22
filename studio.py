#!/usr/bin/env python3
"""
Archive Studio -- real production state for the Bedtime Archive channel.

This reads the ACTUAL files on disk (scripts, shot lists, audio renders,
video cuts, packaging docs) and infers which stage each project is at. It
invents nothing: if a stage has no file backing it, it reports "not started"
rather than guessing. The HQ world uses this to light up the studio.

Idea backlog and generated outlines are persisted to ~/.eva_studio.json and
~/Desktop/YouTube the/outlines/ so they survive restarts and are editable by
hand.
"""
import json
import os
import re
import shutil
import time
from datetime import datetime

# The two real asset folders for the channel. Renamed 2026-10-08 to
# "YOUTUB OUTPUTS" (Sage's new folder) -- the old names kept as fallback
# search paths so nothing already filed under them goes missing silently.
STUDIO_DIRS = [
    os.path.expanduser("~/Desktop/YOUTUB OUTPUTS"),
    os.path.expanduser("~/Desktop/YouTube the"),
    os.path.expanduser("~/Desktop/youtub"),
]

# ---------------------------------------------------------------------------
# The studio keeps ALL of its own output under the channel's own folder. None
# of it lives in the home directory next to the trading bot's files
# (~/trading_log_v9.csv, ~/sage_bot_*.csv, ~/.eva_mechanic_status.json) and
# nothing here is ever read or written by the bot. Two separate businesses,
# two separate filing cabinets.
#
#   ~/Desktop/YouTube the/
#   ├── outlines/            scripts and outlines -- creative work only
#   └── _studio/             the studio's own operational data
#       ├── ideas.json           idea backlog        (was ~/.eva_studio.json)
#       ├── activity.csv         what the studio did, one row per event
#       └── reports/             dated production status reports
# ---------------------------------------------------------------------------
CHANNEL_DIR = os.path.expanduser("~/Desktop/YOUTUB OUTPUTS")
STUDIO_DATA_DIR = os.path.join(CHANNEL_DIR, "_studio")
IDEAS_FILE = os.path.join(STUDIO_DATA_DIR, "ideas.json")
ACTIVITY_LOG = os.path.join(STUDIO_DATA_DIR, "activity.csv")
REPORT_DIR = os.path.join(STUDIO_DATA_DIR, "reports")
OUTLINE_DIR = os.path.join(CHANNEL_DIR, "outlines")
# Finished projects' files, copied here (never moved) once shipped -- one
# shelf per project, each with its own MANIFEST.md. Living under _studio/
# means it's automatically covered by list_documents()/read_document()'s
# existing allowed-roots check, with no new wiring needed.
WAREHOUSE_DIR = os.path.join(STUDIO_DATA_DIR, "warehouse")

# Where the idea backlog used to live, before the studio got its own folder.
# Read once on migration, then left alone.
_LEGACY_IDEAS_FILE = os.path.expanduser("~/.eva_studio.json")


SHIFT_FILE = os.path.join(STUDIO_DATA_DIR, "shift.json")

# ---------------------------------------------------------------------------
# THE SHIFT
#
# The studio keeps the SAME hours as the trading floor. sage_bot_v13.py is
# started by launchd at 6:00am local (= 09:00 ET), trades the 10:00-15:55 ET
# window, and exits at 16:00 ET ("Market closed. Exiting."). So the studio
# clocks in at 09:00 ET and clocks out at 16:00 ET, Monday to Friday -- same
# bell, same door.
#
# Everything below is measured in New York time for exactly that reason: the
# bot's day is defined by the market, not by this machine's timezone.
# ---------------------------------------------------------------------------
SHIFT_OPEN_ET = 9 * 60           # 09:00 ET -- when the bot process starts
SHIFT_CLOSE_ET = 16 * 60         # 16:00 ET -- when the bot exits

try:
    from zoneinfo import ZoneInfo
    MARKET_TZ = ZoneInfo("America/New_York")
except Exception:
    MARKET_TZ = None


def market_now():
    """Now, in market time. The studio's day is the market's day."""
    return datetime.now(MARKET_TZ) if MARKET_TZ else datetime.now()


def shift_state(now=None):
    """Where the studio is in its working day, on the trading floor's clock."""
    now = now or market_now()
    mins = now.hour * 60 + now.minute
    weekday = now.weekday() < 5
    if not weekday:
        phase = "weekend"
    elif mins < SHIFT_OPEN_ET:
        phase = "before"
    elif mins < SHIFT_CLOSE_ET:
        phase = "open"
    else:
        phase = "after"
    return {
        "phase": phase,
        "open": phase == "open",
        "day": now.strftime("%Y-%m-%d"),
        "now_et": now.strftime("%H:%M"),
        "opens_et": "09:00",
        "closes_et": "16:00",
        "note": "Same hours as the trading floor — in at 09:00 ET, out at 16:00 ET.",
    }


def _ensure_dirs():
    os.makedirs(STUDIO_DATA_DIR, exist_ok=True)
    os.makedirs(REPORT_DIR, exist_ok=True)


def _load_shift():
    if not os.path.exists(SHIFT_FILE):
        return {}
    try:
        with open(SHIFT_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def _save_shift(d):
    _ensure_dirs()
    with open(SHIFT_FILE, "w") as f:
        json.dump(d, f, indent=2)


def log_activity(event, detail=""):
    """Append one row to the studio's OWN activity log.

    Deliberately a separate file from the bot's trade log -- the studio
    records production work, not trades, and the two must never share a file.
    """
    _ensure_dirs()
    new = not os.path.exists(ACTIVITY_LOG)
    stamp = datetime.now().astimezone()
    row = [stamp.strftime("%Y-%m-%d"), stamp.strftime("%H:%M:%S"),
           str(event).replace(",", " ")[:60],
           str(detail).replace(",", " ").replace("\n", " ")[:300]]
    with open(ACTIVITY_LOG, "a") as f:
        if new:
            f.write("Date,Time,Event,Detail\n")
        f.write(",".join(row) + "\n")


def read_activity(limit=40):
    """Most recent studio events, newest first. Empty list if never used."""
    if not os.path.exists(ACTIVITY_LOG):
        return []
    try:
        with open(ACTIVITY_LOG) as f:
            rows = [r.strip().split(",", 3) for r in f.readlines()[1:] if r.strip()]
    except Exception:
        return []
    out = [{"date": r[0], "time": r[1], "event": r[2],
            "detail": r[3] if len(r) > 3 else ""} for r in rows if len(r) >= 3]
    return out[::-1][:limit]

# Production stages, in order. Each maps to filename patterns that PROVE the
# stage is done -- a stage is only "done" if a real file matches.
#
# "factcheck" split out from "research" on 2026-08-29: a fact-check file used
# to just count toward research being done, so a project could reach
# "research: done" on a plain research file with no independent verification
# pass at all -- the ACT_UP_SCRIPT_FACT_CHECK.md format already proved this
# works for real, it just was never a REQUIRED, separately-gated stage. Now
# it is its own stage, so a missing fact-check shows up honestly as
# "implied" rather than silently vanishing into research's evidence.
STAGES = [
    ("research",  r"(photo_sourcing|research)"),
    ("factcheck", r"fact_check"),
    ("script",    r"(_script|script_)"),
    ("shotlist",  r"(shot_list|shotlist)"),
    ("audio",     r"\.(mp3|wav|m4a)$"),
    ("video",     r"\.(mp4|mov)$"),
    ("packaging", r"(packaging|thumbnail|description|marketing)"),
    ("publish",   r"(publishing|publish_checklist)"),
]

# Known projects, matched by keyword against filenames. Persisted to
# _studio/projects.json (seeded once from this list) rather than kept as a
# fixed constant, so a new project can be registered at runtime -- see
# start_next_idea(). Do not read this list directly; call load_projects().
_DEFAULT_PROJECTS = [
    {"id": "ww2",   "title": "Hidden in Plain Sight",
     "subtitle": "Gay lives during WWII", "match": r"(ww2|bedtime_archive|alexander)"},
    {"id": "actup", "title": "ACT UP",
     "subtitle": "AIDS activism", "match": r"act_up"},
]

PROJECTS_FILE = os.path.join(STUDIO_DATA_DIR, "projects.json")


def _seed_projects_file():
    if os.path.exists(PROJECTS_FILE):
        return
    _ensure_dirs()
    with open(PROJECTS_FILE, "w") as f:
        json.dump({"projects": _DEFAULT_PROJECTS}, f, indent=2)
    log_activity("projects registry created",
                 f"{len(_DEFAULT_PROJECTS)} project(s) seeded from the original list")


def load_projects():
    """The tracked-project registry. Persisted so a project started later by
    start_next_idea() survives restarts, instead of living only in memory."""
    _seed_projects_file()
    try:
        with open(PROJECTS_FILE) as f:
            return json.load(f).get("projects", [])
    except Exception:
        return list(_DEFAULT_PROJECTS)


def save_projects(projects):
    _ensure_dirs()
    with open(PROJECTS_FILE, "w") as f:
        json.dump({"projects": projects}, f, indent=2)


def add_project(project_id, title, subtitle, match):
    """Register a new tracked project. Idempotent -- calling it again with
    the same id returns the existing entry rather than duplicating it."""
    projects = load_projects()
    existing = next((p for p in projects if p["id"] == project_id), None)
    if existing:
        return existing
    entry = {"id": project_id, "title": title, "subtitle": subtitle, "match": match}
    projects.append(entry)
    save_projects(projects)
    log_activity("project added", f"{title} ({project_id}) — match pattern: {match}")
    return entry


def _walk():
    """Every real file across the studio folders, with mtime and size."""
    out = []
    for d in STUDIO_DIRS:
        if not os.path.isdir(d):
            continue
        for name in os.listdir(d):
            p = os.path.join(d, name)
            if not os.path.isfile(p) or name.startswith("."):
                continue
            try:
                st = os.stat(p)
            except OSError:
                continue
            out.append({
                "name": name, "path": p, "dir": os.path.basename(d),
                "mtime": st.st_mtime, "size": st.st_size,
                "ext": os.path.splitext(name)[1].lower().lstrip("."),
            })
    return out


def _stage_of(fname):
    low = fname.lower()
    hits = []
    for stage, pat in STAGES:
        if re.search(pat, low):
            hits.append(stage)
    return hits


def build_projects(files):
    projects = []
    for spec in load_projects():
        pat = re.compile(spec["match"], re.I)
        mine = [f for f in files if pat.search(f["name"])]
        stages = {}
        for stage, _ in STAGES:
            evidence = [f for f in mine if stage in _stage_of(f["name"])]
            stages[stage] = {
                "done": bool(evidence),
                "files": [f["name"] for f in evidence[:6]],
                "count": len(evidence),
            }
        # A finished cut proves the work before it happened, even when no file
        # is named for it. Mark those "implied" -- complete, but by inference
        # rather than direct evidence, so the two are never confused.
        order = [s for s, _ in STAGES]
        last_done = max((i for i, s in enumerate(order) if stages[s]["done"]),
                        default=-1)
        for i, s in enumerate(order):
            if i < last_done and not stages[s]["done"]:
                stages[s]["done"] = True
                stages[s]["implied"] = True

        done_count = sum(1 for s in stages.values() if s["done"])
        # current stage = the first one NOT done; if all done, it's shipped
        current = next((s for s in order if not stages[s]["done"]), "shipped")
        last = max((f["mtime"] for f in mine), default=0)
        projects.append({
            **{k: spec[k] for k in ("id", "title", "subtitle")},
            "stages": stages,
            "current_stage": current,
            "progress": round(done_count / len(STAGES), 2),
            "asset_count": len(mine),
            "last_touched": (
                datetime.fromtimestamp(last).isoformat() if last else None
            ),
        })
    return projects


def _migrate_legacy_ideas():
    """Move the backlog out of ~/.eva_studio.json into the studio's own folder.

    Runs once. The old file is left on disk untouched rather than deleted --
    if anything about this is wrong, the original is still there.
    """
    if os.path.exists(IDEAS_FILE) or not os.path.exists(_LEGACY_IDEAS_FILE):
        return
    try:
        with open(_LEGACY_IDEAS_FILE) as f:
            data = json.load(f)
    except Exception:
        return
    _ensure_dirs()
    with open(IDEAS_FILE, "w") as f:
        json.dump(data, f, indent=2)
    log_activity("backlog migrated",
                 f"{len(data.get('ideas', []))} idea(s) moved out of the home "
                 f"directory into _studio/ideas.json")


def load_ideas():
    """Idea backlog. Plain JSON so it can be edited by hand."""
    _migrate_legacy_ideas()
    if not os.path.exists(IDEAS_FILE):
        return []
    try:
        with open(IDEAS_FILE) as f:
            return json.load(f).get("ideas", [])
    except Exception:
        return []


def save_idea(title, note="", source=""):
    ideas = load_ideas()
    # Real bug, found 2026-08-29: int(time.time()) is only second-granular,
    # so pitching more than one idea in the same second (e.g. a script
    # adding several at once) silently gave them the SAME id -- confirmed
    # against the real ideas.json, which already had a 3-way collision from
    # before this fix. Millisecond timestamp + the idea's own index makes
    # every id unique regardless of how fast ideas are added.
    new_id = f"I{int(time.time() * 1000)}_{len(ideas)}"
    ideas.append({
        "id": new_id,
        "title": title.strip()[:200],
        "note": note.strip()[:1000],
        "source": source.strip()[:400],
        "added": datetime.now().astimezone().isoformat(),
        "status": "new",
    })
    _ensure_dirs()
    with open(IDEAS_FILE, "w") as f:
        json.dump({"ideas": ideas}, f, indent=2)
    log_activity("idea added", ideas[-1]["title"])
    return ideas[-1]


# The outline skeleton is lifted from the channel's OWN finished script
# structure (cold open -> context -> named individuals -> turn -> legacy),
# which is why it is a template rather than an invention.
OUTLINE_TEMPLATE = """# {title}

> Working outline generated {stamp}. Structure mirrors "Hidden in Plain Sight".

## Cold open (0:00-1:00)
A concrete scene, one place and one year. No thesis yet.
- Place / year:
- The detail that makes it real:

## Context (1:00-3:00)
What the world looked like before the turn.
- Legal situation:
- Visible culture:

## The turn (3:00-5:00)
The specific moment it changed. Date it precisely.
- Date:
- What changed on paper:
- What changed in practice:

## The people (5:00-14:00)
Two or three named individuals. Named people carry the story.
1. Name — who they were, what happened, what they did about it.
2. Name —
3. Name —

## Legacy (14:00-17:00)
What was lost, what survived, and who remembered.

## Close (17:00-18:00)
Return to the cold-open image, changed.

---
### Research to verify
- [ ] Primary source for every date above
- [ ] Photo rights / public domain check
- [ ] Fact-check pass (see ACT_UP_SCRIPT_FACT_CHECK.md for the format)
"""


def _slugify(title):
    return re.sub(r"[^a-z0-9]+", "_", title.lower()).strip("_")[:60] or "untitled"


def generate_outline(title):
    """Write a real outline file to disk and return its path."""
    os.makedirs(OUTLINE_DIR, exist_ok=True)
    slug = _slugify(title)
    path = os.path.join(OUTLINE_DIR, f"{slug}.md")
    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    with open(path, "w") as f:
        f.write(OUTLINE_TEMPLATE.format(title=title.strip(), stamp=stamp))
    log_activity("outline generated", os.path.basename(path))
    return path


def start_next_idea():
    """Pop the oldest still-'new' idea off the backlog, register it as a
    tracked project, and seed its outline.

    This is the literal "move to a different script when they're done" step.
    It does not run on its own timer -- a caller (the studio shift) decides
    a prior project is genuinely done (see write_publish_checklist) and
    calls this explicitly. Returns None if the backlog is empty.
    """
    ideas = load_ideas()
    idx = next((i for i, x in enumerate(ideas) if x.get("status") == "new"), None)
    if idx is None:
        return None
    idea = ideas[idx]
    slug = _slugify(idea["title"])
    add_project(slug, idea["title"], (idea.get("note") or "")[:80], re.escape(slug))
    ideas[idx] = {**idea, "status": "in_progress",
                 "started": datetime.now().astimezone().isoformat()}
    _ensure_dirs()
    with open(IDEAS_FILE, "w") as f:
        json.dump({"ideas": ideas}, f, indent=2)
    path = generate_outline(idea["title"])
    log_activity("next idea started", f"{idea['title']} — outline seeded at {os.path.basename(path)}")
    return {"project_id": slug, "title": idea["title"], "outline": path}


def checklist_status(project_id):
    """What packaging material already exists on disk for a project, and
    what's still missing. Read-only, invents nothing -- used to decide
    whether a real publish checklist can be assembled yet, or whether the
    missing piece needs to be written first."""
    projects = {p["id"]: p for p in load_projects()}
    spec = projects.get(project_id)
    if not spec:
        return {"error": f"no such project: {project_id}"}
    files = _walk()
    pat = re.compile(spec["match"], re.I)
    mine = [f for f in files if pat.search(f["name"])]
    videos = [f for f in mine if f["ext"] in ("mp4", "mov")]
    canonical = [f["name"] for f in videos if f["name"].lower().endswith("_final.mp4")]
    thumbs = [f["name"] for f in mine if f["ext"] in ("png", "jpg", "jpeg")
              and re.search(r"thumb", f["name"], re.I)]
    packaging_docs = [f["name"] for f in mine if f["ext"] in ("md", "txt")
                       and re.search(r"(packaging|description)", f["name"], re.I)]
    return {
        "project_id": project_id,
        "videos": [f["name"] for f in videos],
        "canonical_video": canonical[0] if canonical else None,
        "multiple_videos_no_canonical": len(videos) > 1 and not canonical,
        "thumbnails": thumbs,
        "packaging_docs": packaging_docs,
        "ready": bool(canonical or (len(videos) == 1)) and bool(packaging_docs),
    }


PUBLISH_FOOTER = (
    "## What's still manual\n\n"
    "This checklist is the ready-to-upload package, not an upload. Actually "
    "publishing to YouTube -- title, description, tags, thumbnail, visibility, "
    "hitting \"Publish\" -- stays a manual step you take yourself.\n"
)


def _self_matching_name(project_id, spec, suffix):
    """A `<...>_<suffix>` filename guaranteed to match the project's OWN
    `match` regex -- title-based names don't always. ww2's real title,
    "Hidden in Plain Sight", contains no "ww2"/"bedtime_archive"/etc., so a
    file named purely from the title (e.g. `Hidden_in_Plain_Sight_
    QUALITY_REVIEW.md`) would be invisible to build_projects()'s own stage
    detection for that project -- a real, latent bug, not hypothetical: it's
    exactly what happened the first time this ran. Prepending the id when
    the natural name doesn't already self-match closes that gap for good,
    for any project, not just the ones caught by hand so far.
    """
    title = (spec["title"] if spec else project_id).replace(" ", "_")
    fname = f"{title}_{suffix}"
    if spec and not re.search(spec["match"], fname, re.I):
        fname = f"{project_id}_{fname}"
    return fname


def write_publish_checklist(project_id, body_markdown):
    """Write the real `<Title>_PUBLISH_CHECKLIST.md` for a project.

    `body_markdown` is the actual assembled content -- video path, title,
    description, tags, thumbnail plan, known gaps -- composed by the caller.
    This function only does the mechanical part: a consistent filename, the
    standard "what's still manual" footer, and the activity log entry. It
    does not write creative content itself, same division as generate_outline()
    (this writes the file; the caller decides what goes in it).
    """
    projects = {p["id"]: p for p in load_projects()}
    spec = projects.get(project_id)
    fname = _self_matching_name(project_id, spec, "PUBLISH_CHECKLIST.md")
    path = os.path.join(CHANNEL_DIR, fname)
    with open(path, "w") as f:
        f.write(body_markdown.rstrip() + "\n\n" + PUBLISH_FOOTER)
    log_activity("publish checklist written", fname)
    try:
        warehouse_project(project_id)
    except Exception as e:
        log_activity("warehouse failed", f"{project_id}: {str(e)[:200]}")
    return path


# Plain-English description per kind, so a file the reader can't open as
# text (a video, an mp3, a thumbnail) still says what it IS in the manifest.
KIND_DESCRIPTION = {
    "script":     "The narration script -- the words read aloud in the final video.",
    "shot list":  "Maps script lines to the specific images used to illustrate them.",
    "fact-check": "Verifies the historical claims in the script against real sources.",
    "research":   "Background research and source material gathered for this project.",
    "packaging":  "Title, description, tags, and thumbnail plan for publishing.",
    "publish":    "The ready-to-upload checklist -- everything needed to publish.",
    "report":     "An operational status report, not part of the release itself.",
    "document":   "A supporting document for this project.",
}


def _describe_file(name, ext):
    if ext in ("mp4", "mov"):
        return "The finished video render."
    if ext in ("mp3", "wav", "m4a"):
        return "The recorded narration audio."
    if ext in ("png", "jpg", "jpeg"):
        return "Thumbnail image." if re.search(r"thumb", name, re.I) else "An image asset."
    return KIND_DESCRIPTION.get(_kind_of(name), "A project file.")


def warehouse_project(project_id):
    """Copy every real file for a project into its own warehouse shelf, with
    a manifest describing what each one is in plain English.

    Copies, never moves: the originals stay exactly where build_projects()'s
    stage-detection expects them, so warehousing a project can never make
    its own tracked pipeline status disappear. Safe to call again later --
    re-copies over the same shelf, so the warehouse always reflects the
    current real files, not a stale snapshot from the first time it shipped.
    """
    projects = {p["id"]: p for p in load_projects()}
    spec = projects.get(project_id)
    if not spec:
        raise ValueError(f"no such project: {project_id}")

    files = _walk()
    pat = re.compile(spec["match"], re.I)
    # "report" kind = dated status/roadmap noise (this channel has a LOT of
    # it from an earlier stuck automation loop) -- explicitly not part of
    # the release, so it never makes it onto the shelf even if the
    # project's match pattern happens to catch the filename too.
    mine = [f for f in files if pat.search(f["name"]) and _kind_of(f["name"]) != "report"]
    if not mine:
        return None

    dest_dir = os.path.join(WAREHOUSE_DIR, project_id)
    os.makedirs(dest_dir, exist_ok=True)

    entries = []
    for f in sorted(mine, key=lambda x: x["name"]):
        shutil.copy2(f["path"], os.path.join(dest_dir, f["name"]))
        entries.append({
            "name": f["name"], "kind": _kind_of(f["name"]), "ext": f["ext"],
            "size": f["size"], "description": _describe_file(f["name"], f["ext"]),
        })

    stamp = datetime.now().astimezone().strftime("%Y-%m-%d %H:%M")
    lines = [f"# {spec['title']} — warehouse shelf", "",
             f"_{spec.get('subtitle', '')}_", "",
             f"Stored {stamp}. {len(entries)} file(s), copied from the channel "
             f"folders -- not moved, the originals stay where the production "
             f"tracker expects them.", ""]
    for e in entries:
        size_txt = (f"{e['size']/1024/1024:.1f} MB" if e["size"] > 1024 * 1024
                    else f"{e['size']/1024:.0f} KB")
        lines.append(f"- **{e['name']}** ({size_txt}) — {e['description']}")
    with open(os.path.join(dest_dir, "MANIFEST.md"), "w") as f:
        f.write("\n".join(lines) + "\n")

    log_activity("warehoused", f"{spec['title']}: {len(entries)} file(s) in warehouse/{project_id}/")
    return {"project_id": project_id, "dir": dest_dir, "files": entries}


def write_quality_review(project_id, body_markdown, verdict):
    """Write the real `<Title>_QUALITY_REVIEW.md` for a project -- the
    studio's equivalent of the trading floor lead's per-trade review
    (`~/sage_bot_floor_lead_reviews.csv`, DesignedRR vs RealizedR): does the
    finished work actually hold up against what it was meant to be, checked
    AFTER the fact by someone other than whoever built it.

    `body_markdown` is the actual review -- what was checked, what was
    found, real specifics -- composed by the caller from real inspection
    (actually watching sampled frames, reading the script, checking
    audio/video sync and duration match). This function is the mechanical
    half only: filename, footer, activity log, same division as
    write_publish_checklist(). `verdict` is "pass" or "needs work" and gets
    logged plainly so a failed review is never buried in prose.
    """
    if verdict not in ("pass", "needs work"):
        raise ValueError('verdict must be "pass" or "needs work"')
    projects = {p["id"]: p for p in load_projects()}
    spec = projects.get(project_id)
    fname = _self_matching_name(project_id, spec, "QUALITY_REVIEW.md")
    path = os.path.join(CHANNEL_DIR, fname)
    footer = (f"\n\n## Verdict: {verdict.upper()}\n\n" +
              ("Ready for a viewer as-is." if verdict == "pass"
               else "Real issues found above -- fix before treating this as finished."))
    with open(path, "w") as f:
        f.write(body_markdown.rstrip() + footer + "\n")
    log_activity("quality review written", f"{fname} -- {verdict}")
    try:
        warehouse_project(project_id)
    except Exception as e:
        log_activity("warehouse failed", f"{project_id}: {str(e)[:200]}")
    return path


def warehouse_status():
    """What's actually sitting in the warehouse right now, per project --
    read-only, reflects real copied files on disk."""
    out = []
    if not os.path.isdir(WAREHOUSE_DIR):
        return out
    projects = {p["id"]: p for p in load_projects()}
    for pid in sorted(os.listdir(WAREHOUSE_DIR)):
        shelf = os.path.join(WAREHOUSE_DIR, pid)
        if not os.path.isdir(shelf):
            continue
        files = []
        for name in sorted(os.listdir(shelf)):
            if name.startswith(".") or name == "MANIFEST.md":
                continue
            p = os.path.join(shelf, name)
            if not os.path.isfile(p):
                continue
            st = os.stat(p)
            ext = os.path.splitext(name)[1].lower().lstrip(".")
            files.append({"name": name, "path": p, "size": st.st_size, "ext": ext,
                         "kind": _kind_of(name), "description": _describe_file(name, ext)})
        spec = projects.get(pid)
        manifest = os.path.join(shelf, "MANIFEST.md")
        out.append({
            "project_id": pid,
            "title": spec["title"] if spec else pid,
            "subtitle": (spec.get("subtitle") or "") if spec else "",
            "files": files,
            "manifest_path": manifest if os.path.isfile(manifest) else None,
        })
    return out


def archive_video_variant(path, project_id):
    """Move a superseded video file into that channel folder's own
    _archive/<project_id>/ subfolder. Never deletes media -- moves it aside
    so exactly one canonical `<slug>_FINAL.mp4` remains at the top level."""
    real = os.path.realpath(path)
    roots = [os.path.realpath(d) for d in STUDIO_DIRS]
    root = next((r for r in roots if real.startswith(r + os.sep)), None)
    if not root or not os.path.isfile(real):
        raise ValueError("not a file inside the studio's channel folders")
    name = os.path.basename(real)
    dest_dir = os.path.join(root, "_archive", project_id)
    os.makedirs(dest_dir, exist_ok=True)
    dest = os.path.join(dest_dir, name)
    os.rename(real, dest)
    log_activity("video archived", f"{project_id}: {name} -> _archive/{project_id}/")
    return dest


def write_status_report():
    """Real work, real output file.

    Reads the actual pipeline state and writes a dated production report to
    the channel's own folder. Everything in it is derived from files that
    exist -- the "blocked on" line is the first stage with no evidence, not a
    guess about what the user should do next.
    """
    st = build_studio_status()
    _ensure_dirs()
    day = datetime.now().strftime("%Y-%m-%d")
    # Reports go in the studio's own reports/ folder, NOT in outlines/ --
    # outlines/ is creative work, this is operational output.
    path = os.path.join(REPORT_DIR, f"PRODUCTION_STATUS_{day}.md")

    L = [f"# Production status — {st['channel']}", "",
         f"_Generated {datetime.now().astimezone().strftime('%Y-%m-%d %H:%M %Z')} "
         f"from {st['total_assets']} files on disk._", ""]

    for p in st["projects"]:
        L.append(f"## {p['title']} — {p['subtitle']}")
        L.append("")
        L.append(f"- **Stage:** {p['current_stage']}  ·  **Progress:** {int(p['progress'] * 100)}%")
        L.append(f"- **Assets:** {p['asset_count']}")
        if p["last_touched"]:
            L.append(f"- **Last touched:** {p['last_touched'][:16].replace('T', ' ')}")
        L.append("")
        L.append("| Stage | State | Evidence |")
        L.append("|---|---|---|")
        for stage, _ in STAGES:
            s = p["stages"][stage]
            state = ("implied" if s.get("implied")
                     else "done" if s["done"] else "**not started**")
            ev = ", ".join(s["files"][:2]) if s["files"] else "—"
            L.append(f"| {stage} | {state} | {ev} |")
        L.append("")
        blocked = p["current_stage"]
        if blocked != "shipped":
            L.append(f"> **Blocked on:** {blocked} — no file on disk yet proves this stage.")
            L.append("")

    ideas = st["ideas"]
    L.append("## Idea backlog")
    L.append("")
    if ideas:
        for i in ideas:
            L.append(f"- **{i['title']}** — {i.get('note', '')}".rstrip(" —"))
    else:
        L.append("_Empty._")
    L.append("")

    if st["outlines"]:
        L.append("## Outlines on disk")
        L.append("")
        for o in st["outlines"]:
            L.append(f"- {o}")
        L.append("")

    with open(path, "w") as f:
        f.write("\n".join(L) + "\n")
    log_activity("status report written", os.path.basename(path))
    return path


# What each stage actually asks a person to do. Wording is deliberately
# concrete -- these become the studio's task board, so "script" is not a task,
# "Draft the script" is.
STAGE_WORK = {
    "research":  ("Source photos",                "Research Wall"),
    "factcheck": ("Verify every claim in the script", "Fact-Check Desk"),
    "script":    ("Draft the script",             "Writers' Desk"),
    "shotlist":  ("Build the shot list",          "Edit Bay"),
    "audio":     ("Record narration",             "Booth"),
    "video":     ("Cut the video",                "Edit Bay"),
    "packaging": ("Title, thumbnail, description", "Packaging Desk"),
    "publish":   ("Run the publish checklist",    "Packaging Desk"),
}


def build_tasks(projects=None):
    """The studio's task board, derived from REAL pipeline state.

    A task is not invented: it is the first stage of a real project that has
    no file on disk backing it. It is 'done' only when a real file appears
    that matches that stage. Nothing here is a guess about what should exist
    -- it is a report of what does not exist yet.
    """
    if projects is None:
        projects = build_projects(_walk())
    tasks = []
    for p in projects:
        stage = p.get("current_stage")
        if not stage or stage == "shipped":
            tasks.append({
                "id": f"{p['id']}:shipped", "project": p["title"], "stage": "shipped",
                "what": "Shipped — nothing blocking", "station": "Packaging Desk",
                "state": "done", "evidence": "all stages have files on disk",
            })
            continue
        what, station = STAGE_WORK.get(stage, (f"Advance: {stage}", "Writers' Desk"))
        done_stages = [s for s in STAGES
                       if p["stages"].get(s[0], {}).get("done")]
        tasks.append({
            "id": f"{p['id']}:{stage}",
            "project": p["title"],
            "stage": stage,
            "what": what,
            "station": station,
            "state": "todo",
            "evidence": f"no file on disk matches '{stage}' yet",
            "progress": f"{len(done_stages)}/{len(STAGES)} stages have files",
        })
    return tasks


def run_shift_tick():
    """Do the studio's real work for wherever we are in the day.

    Called on every /api/studio read. Idempotent: each piece of work is
    stamped with the day it was done, so it happens once per shift no matter
    how often this runs.

    The work is genuinely real -- it reads the actual channel files, writes
    actual report files, and records what actually changed. It never claims a
    stage advanced unless a matching file really appeared on disk.
    """
    st = shift_state()
    day, phase = st["day"], st["phase"]
    sh = _load_shift()
    changed = False

    files = _walk()
    projects = build_projects(files)
    tasks = build_tasks(projects)
    # Fingerprint of which stages currently have real file evidence.
    snapshot = {p["id"]: sorted(s for s in p["stages"] if p["stages"][s]["done"])
                for p in projects}

    # --- clock in: write the day's production report, once -------------------
    if phase in ("open", "after") and sh.get("opened_on") != day:
        sh["opened_on"] = day
        changed = True
        log_activity("shift start", f"Clocked in 09:00 ET with the trading floor — "
                                    f"{len(tasks)} task(s) on the board")
        try:
            write_status_report()
        except Exception as e:
            log_activity("report failed", str(e)[:200])

    # --- during the shift: notice real progress ------------------------------
    prev = sh.get("snapshot") or {}
    if prev and phase == "open":
        for pid, stages in snapshot.items():
            gained = [s for s in stages if s not in prev.get(pid, [])]
            for g in gained:
                what = STAGE_WORK.get(g, (g, ""))[0]
                log_activity("task complete", f"{pid}: {what} — a real file now backs '{g}'")
                changed = True
    sh["snapshot"] = snapshot

    # --- clock out: end-of-day summary, once ---------------------------------
    if phase == "after" and sh.get("closed_on") != day:
        sh["closed_on"] = day
        changed = True
        open_tasks = [t for t in tasks if t["state"] == "todo"]
        log_activity("shift end",
                     f"Clocked out 16:00 ET with the trading floor — "
                     f"{len(open_tasks)} task(s) still open")

    if changed or "snapshot" not in _load_shift():
        _save_shift(sh)
    return {"shift": st, "tasks": tasks}


# ---------------------------------------------------------------------------
# READING THE ACTUAL WORK
#
# The studio panel can open the real scripts, shot lists and fact-checks. That
# means serving file contents over HTTP, so the reader is deliberately narrow:
#
#   * only inside the channel folders (STUDIO_DIRS) or the studio's own data dir
#   * only text-ish extensions -- never media, never binaries
#   * a hard size cap, so a huge file cannot wedge the server
#   * the path is re-resolved with realpath and re-checked against the roots
#     AFTER resolution, which is what actually stops ../ traversal and symlinks
# ---------------------------------------------------------------------------
READABLE_EXT = {".md", ".txt", ".srt", ".vtt", ".csv", ".json", ".yml", ".yaml"}
MAX_DOC_BYTES = 400_000


def _allowed_roots():
    return [os.path.realpath(d) for d in STUDIO_DIRS + [STUDIO_DATA_DIR]
            if os.path.isdir(d)]


def _walk_roots():
    """Allowed roots with nested ones removed.

    STUDIO_DATA_DIR lives inside the channel folder, so walking both listed
    everything in _studio/ twice.
    """
    roots = sorted(set(_allowed_roots()), key=len)
    keep = []
    for r in roots:
        if not any(r.startswith(k + os.sep) for k in keep):
            keep.append(r)
    return keep


def list_documents():
    """Every readable document across the channel folders, newest first."""
    out = []
    for root in _walk_roots():
        for dirpath, dirnames, filenames in os.walk(root):
            dirnames[:] = [d for d in dirnames if not d.startswith(".")]
            for name in filenames:
                if name.startswith("."):
                    continue
                if os.path.splitext(name)[1].lower() not in READABLE_EXT:
                    continue
                full = os.path.join(dirpath, name)
                try:
                    st = os.stat(full)
                except OSError:
                    continue
                out.append({
                    "name": name,
                    "path": full,
                    "size": st.st_size,
                    "mtime": st.st_mtime,
                    "when": datetime.fromtimestamp(st.st_mtime).isoformat(),
                    "kind": _kind_of(name),
                })
    # Rank by what the work actually is, THEN by recency. Sorting on mtime
    # alone buried the scripts: this channel has dozens of dated status
    # reports that are all newer than ACT_UP_SCRIPT.md, so a plain
    # newest-first list pushed the real writing off the end entirely.
    out.sort(key=lambda d: (KIND_RANK.get(d["kind"], 90), -d["mtime"]))
    return out


KIND_RANK = {
    "script": 0, "shot list": 1, "fact-check": 2, "research": 3,
    "packaging": 4, "publish": 5, "report": 6, "document": 7,
}


def _kind_of(name):
    """Rough bucket, by the same patterns the stage matcher uses."""
    low = name.lower()
    if re.search(r"(shot_list|shotlist)", low):        return "shot list"
    if re.search(r"fact_check", low):                  return "fact-check"
    if re.search(r"(_script|script_)", low):           return "script"
    if re.search(r"(packaging|thumbnail|description|marketing)", low): return "packaging"
    if re.search(r"(publishing|publish_checklist)", low): return "publish"
    if re.search(r"(research|photo_sourcing)", low):   return "research"
    if re.search(r"(status|report|roadmap|plan)", low): return "report"
    return "document"


def read_document(path):
    """Read one document, or raise ValueError if it is not allowed.

    Validation happens on the REAL path, after symlinks are resolved, so a
    path that escapes the channel folders is rejected even if it looked fine
    before resolution.
    """
    real = os.path.realpath(os.path.expanduser(path))
    roots = _allowed_roots()
    if not any(real == r or real.startswith(r + os.sep) for r in roots):
        raise ValueError("outside the studio folders")
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


SHIFT_STATUS_FILE = os.path.join(STUDIO_DATA_DIR, "shift_status.json")


def read_shift_status():
    """Last result from the archive-studio-shift scheduled task, same pattern
    as the trading bot's ~/.eva_mechanic_status.json. Empty dict if the shift
    has never run yet."""
    if not os.path.exists(SHIFT_STATUS_FILE):
        return {}
    try:
        with open(SHIFT_STATUS_FILE) as f:
            return json.load(f)
    except Exception:
        return {}


def build_studio_status():
    files = _walk()
    projects = build_projects(files)
    recent = sorted(files, key=lambda f: f["mtime"], reverse=True)[:12]
    outlines = []
    if os.path.isdir(OUTLINE_DIR):
        outlines = sorted(os.listdir(OUTLINE_DIR))
    reports = []
    if os.path.isdir(REPORT_DIR):
        reports = sorted(os.listdir(REPORT_DIR), reverse=True)
    return {
        "channel": "Bedtime Archive",
        "topic": "LGBTQ history documentary",
        "dirs_found": [d for d in STUDIO_DIRS if os.path.isdir(d)],
        "total_assets": len(files),
        "by_type": _counts(files),
        "projects": projects,
        "shift": shift_state(),
        "shift_status": read_shift_status(),
        "tasks": build_tasks(projects),
        "warehouse": warehouse_status(),
        "ideas": load_ideas(),
        "outlines": outlines,
        "reports": reports,
        # Where the studio keeps its own data -- surfaced so the HQ panel can
        # show it, and so it is obvious this is nowhere near the bot's files.
        "data_dir": STUDIO_DATA_DIR,
        "files": {
            "ideas": IDEAS_FILE,
            "activity": ACTIVITY_LOG,
            "reports": REPORT_DIR,
            "outlines": OUTLINE_DIR,
        },
        "activity": read_activity(20),
        # Real readable documents -- scripts, shot lists, fact-checks, reports.
        # The panel lists these and can open any of them.
        "documents": list_documents()[:60],
        "recent": [
            {"name": f["name"], "dir": f["dir"], "ext": f["ext"],
             "when": datetime.fromtimestamp(f["mtime"]).isoformat()}
            for f in recent
        ],
        "generated_at": datetime.now().astimezone().isoformat(),
    }


def _counts(files):
    c = {}
    for f in files:
        c[f["ext"] or "none"] = c.get(f["ext"] or "none", 0) + 1
    return dict(sorted(c.items(), key=lambda kv: -kv[1]))


if __name__ == "__main__":
    print(json.dumps(build_studio_status(), indent=2)[:3000])
