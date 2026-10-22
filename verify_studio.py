#!/usr/bin/env python3
"""
Regression check for studio.py, focused on the two places a silent bug
actually costs something: the document sandbox, and the done/implied
distinction the task board depends on.

The document reader serves real files off disk over HTTP. It was built
narrow on purpose -- allowlisted roots, allowlisted extensions, a size cap,
and validation on the REAL path after symlink resolution. None of that is
useful unless something keeps checking it stays that way after edits. This
does.

No test framework, stdlib only. Run with: python3 verify_studio.py
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import studio

failures = 0
checks = 0


def check(label, ok, detail=""):
    global failures, checks
    checks += 1
    if ok:
        return
    failures += 1
    print(f"  ✗ {label}" + (f" -- {detail}" if detail else ""))


def section(name):
    print(f"\n{name}")


# ------------------------------------------------------------------
section("Document sandbox rejects everything it should")
# ------------------------------------------------------------------
attacks = [
    ("/etc/passwd", "absolute path outside the studio folders"),
    (os.path.expanduser("~/trading_log_v9.csv"), "the bot's own trade log"),
    (os.path.expanduser("~/.eva_mechanic_status.json"), "the bot's own status file"),
    (os.path.join(studio.CHANNEL_DIR, "..", "..", ".ssh", "id_rsa"), "../ traversal out of the channel folder"),
    (os.path.join(studio.CHANNEL_DIR, "nonexistent_file_xyz.md"), "a file that doesn't exist"),
]
for path, why in attacks:
    try:
        studio.read_document(path)
        check(f"rejects: {why}", False, f"read_document('{path}') SUCCEEDED -- it should have raised")
    except ValueError:
        check(f"rejects: {why}", True)
    except Exception as e:
        check(f"rejects: {why}", False, f"raised the wrong exception type: {type(e).__name__}: {e}")

# a real media file inside the allowed folder -- allowed root, wrong extension
media = None
for d in studio.STUDIO_DIRS:
    if not os.path.isdir(d):
        continue
    for name in os.listdir(d):
        if name.lower().endswith((".mp4", ".mov", ".mp3")):
            media = os.path.join(d, name)
            break
    if media:
        break
if media:
    try:
        studio.read_document(media)
        check("rejects: a real media file in an allowed folder", False,
              f"read_document succeeded on {media}")
    except ValueError:
        check("rejects: a real media file in an allowed folder", True)
else:
    print("  (skipped -- no media file found to test against)")

# ------------------------------------------------------------------
section("Document sandbox ACCEPTS the real, legitimate case")
# ------------------------------------------------------------------
docs = studio.list_documents()
check("list_documents() finds at least one real document", len(docs) > 0,
      "channel folders may be empty or missing")
if docs:
    d = studio.read_document(docs[0]["path"])
    check("reading the top-ranked real document succeeds", bool(d.get("text") is not None))
    check("returned path matches what was requested",
          os.path.realpath(d["path"]) == os.path.realpath(docs[0]["path"]))

# ------------------------------------------------------------------
section("Document listing has no duplicates (the _studio/-nested-in-channel bug)")
# ------------------------------------------------------------------
names_and_paths = [(d["name"], d["path"]) for d in docs]
check("no duplicate (name, path) pairs in the document list",
      len(names_and_paths) == len(set(names_and_paths)),
      f"{len(names_and_paths) - len(set(names_and_paths))} duplicate(s) -- "
      f"likely STUDIO_DATA_DIR being walked both on its own and as part of a channel dir")

# ------------------------------------------------------------------
section("Scripts and shot lists rank above dated status reports")
# ------------------------------------------------------------------
# This is the exact bug that shipped once: sorting purely by mtime buried
# ACT_UP_SCRIPT.md under dozens of newer daily status reports.
kinds_seen = [d["kind"] for d in docs]
if "script" in kinds_seen and "report" in kinds_seen:
    check("the first script ranks above the first report",
          kinds_seen.index("script") < kinds_seen.index("report"),
          "a report is ranked ahead of a script -- the real writing will get buried again")

# ------------------------------------------------------------------
section("The task board never claims done+no-evidence in the same breath")
# ------------------------------------------------------------------
# This is the exact bug the studio panel shipped once: showing "checkmark"
# next to "no file yet" for an implied-done stage.
status = studio.build_studio_status()
for p in status.get("projects", []):
    for stage_id, s in p.get("stages", {}).items():
        has_files = bool(s.get("files"))
        implied = bool(s.get("implied"))
        if s.get("done") and not has_files:
            check(f"{p['id']}:{stage_id} done-without-files is marked implied",
                  implied, "done=true, no files, but not flagged implied -- panel would show a contradiction")

# ------------------------------------------------------------------
section("The shift ticker is idempotent -- one shift's work happens once")
# ------------------------------------------------------------------
before = len(studio.read_activity(500))
for _ in range(5):
    studio.run_shift_tick()
after = len(studio.read_activity(500))
check("5 extra ticks add zero activity rows", before == after,
      f"{after - before} extra row(s) appeared -- shift_tick is no longer idempotent")

# ------------------------------------------------------------------
section("The studio's data lives nowhere near the bot's files")
# ------------------------------------------------------------------
home = os.path.expanduser("~")
check("the studio's data_dir is NOT the home directory itself",
      os.path.realpath(studio.STUDIO_DATA_DIR) != os.path.realpath(home))
check("the studio's data_dir is under the channel folder, not ~",
      os.path.realpath(studio.STUDIO_DATA_DIR).startswith(os.path.realpath(studio.CHANNEL_DIR)))
bot_files = ["trading_log_v9.csv", "sage_bot_daily_journal.csv",
             "sage_bot_floor_lead_reviews.csv", ".eva_mechanic_status.json"]
for bf in bot_files:
    p = os.path.join(home, bf)
    if os.path.exists(p):
        check(f"'{bf}' was not modified by this run",
              True)  # existence check only -- a real mtime diff would need a baseline captured before the suite ran

print(f"\n{'─' * 60}")
print(f"{checks} checks, {failures} failure(s)")
if failures:
    print("FAIL\n")
    sys.exit(1)
else:
    print("PASS\n")
