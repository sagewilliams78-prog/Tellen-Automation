"""
Assembles a single-file Artifact preview of the Tellen Automation site:
same design, but with images inlined as data: URIs (Artifact CSP blocks
external image hosts), no backend calls (chat runs the same mock reply
rules client-side; the lead form simulates locally and says so), and no
doctype/html/head/body wrapper (the Artifact tool supplies that skeleton).
"""
import re

ROOT = "/home/claude/tellen-automation"
OUT = "/tmp/claude-0/-home-claude/0331ce75-b3fa-5fe0-b1d7-a5476f6481e0/scratchpad/tellen-preview/index.html"

import os
os.makedirs(os.path.dirname(OUT), exist_ok=True)

def read(path):
    with open(os.path.join(ROOT, path), "r", encoding="utf-8") as f:
        return f.read()

def read_datauri(name):
    with open(f"/tmp/datauri_{name}.txt", "r", encoding="utf-8") as f:
        return f.read()

css = read("public/css/styles.css")
html_full = read("public/index.html")
main_js = read("public/js/main.js")

HERO_URI = read_datauri("hero")
ABOUT_URI = read_datauri("about")
LOGO_URI = read_datauri("logo")

# --- CSS adjustments -------------------------------------------------
css = css.replace('url("../assets/hero-skyline.jpg")', f'url("{HERO_URI}")')
# wrap: add the required safe-area gutter padding instead of the old
# fixed-subtraction width trick, so it also clears a phone's side system bar.
css = css.replace(
    ".wrap { width: min(1200px, calc(100% - 44px)); margin: auto; }",
    ".wrap {\n"
    "  max-width: 1200px;\n"
    "  margin: 0 auto;\n"
    "  padding-left: max(16px, env(safe-area-inset-left, 0px));\n"
    "  padding-right: max(16px, env(safe-area-inset-right, 0px));\n"
    "}"
)
css = css.replace(
    "@media (max-width: 680px) {\n  html { scroll-padding-top: 68px; }\n  body { overflow-x: hidden; }\n  .wrap { width: calc(100% - 36px); }",
    "@media (max-width: 680px) {\n  html { scroll-padding-top: 68px; }\n  body { overflow-x: hidden; }"
)
css = css.replace(
    "@media (max-width: 360px) {\n  .wrap { width: calc(100% - 28px); }\n  .hero h1 { font-size: 35px; }",
    "@media (max-width: 360px) {\n  .hero h1 { font-size: 35px; }"
)
# sticky nav should respect the top safe-area inset, not a bare 0
css = css.replace(
    ".nav {\n  height: 78px;\n  background: rgba(2, 9, 19, .92);\n  backdrop-filter: blur(15px);\n  position: sticky;\n  top: 0;",
    ".nav {\n  height: 78px;\n  background: rgba(2, 9, 19, .92);\n  backdrop-filter: blur(15px);\n  position: sticky;\n  top: env(safe-area-inset-top, 0px);"
)

# --- Extract the body content between <main> ... </footer> plus the
# legal dialog and chat widget markup from the real site -------------
body_match = re.search(r"<header class=\"nav\">.*?</section>\n\n<script", html_full, re.S)
body_html = body_match.group(0)
body_html = body_html[: body_html.rfind("\n\n<script")]

body_html = body_html.replace("/assets/logo-mark.png", LOGO_URI)
body_html = body_html.replace("/assets/about-visual.jpg", ABOUT_URI)

# Be explicit this is a visual/interaction preview, not the live backend.
body_html = body_html.replace(
    'This is a preview deployment. Submissions are validated and queued by the server, but the business email/CRM destination has not been configured yet — see the footer AI disclosure for details.',
    'This published page is a visual and interaction preview. The real validation, honeypot, and rate-limited backend live in the delivered project files, not here — submitting below simulates that flow locally.'
)
body_html = body_html.replace(
    "We'll only mark this submitted once our server confirms it — not before.",
    "This preview simulates the confirmed state locally — the real server confirmation happens in the delivered project."
)

print("Body content length:", len(body_html))
print(body_html[:200])
print("...")
print(body_html[-300:])

with open("/tmp/preview_body.html", "w", encoding="utf-8") as f:
    f.write(body_html)

with open("/tmp/preview_css.css", "w", encoding="utf-8") as f:
    f.write(css)
