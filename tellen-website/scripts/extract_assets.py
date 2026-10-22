"""
Extracts embedded data: URI images out of the uploaded prototype's index.html
(treated purely as a DATA source — we never execute anything from that file)
and writes them to disk as real image files for inspection and re-optimization.
"""
import re
import base64
import hashlib
import os

SRC = "/home/claude/inspect-zip/tellen-premium-v4/index.html"
OUT_DIR = "/home/claude/tellen-automation/assets/raw"

with open(SRC, "r", encoding="utf-8", errors="replace") as f:
    content = f.read()

pattern = re.compile(r"data:(image/[a-zA-Z0-9.+-]+);base64,([A-Za-z0-9+/=]{200,})")

seen = {}
results = []
for m in pattern.finditer(content):
    mime, b64 = m.group(1), m.group(2)
    raw = base64.b64decode(b64)
    h = hashlib.sha256(raw).hexdigest()[:12]
    ext = mime.split("/")[-1].replace("jpeg", "jpg")
    fname = f"{h}.{ext}"
    path = os.path.join(OUT_DIR, fname)
    if h not in seen:
        with open(path, "wb") as out:
            out.write(raw)
        seen[h] = fname
    results.append({
        "start": m.start(),
        "mime": mime,
        "hash": h,
        "file": seen[h],
        "bytes": len(raw),
    })

for r in results:
    print(f"offset={r['start']:>8}  mime={r['mime']:<10}  bytes={r['bytes']:>9}  -> {r['file']}")

print(f"\n{len(results)} data URIs found, {len(seen)} unique blobs")
