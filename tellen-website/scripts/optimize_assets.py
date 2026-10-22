"""
Builds a properly-sized, properly-compressed asset set from the raw images
extracted out of the prototype, so index.html can reference small external
files instead of three ~90KB-465KB blobs inlined as base64 (one of them,
the full-res logo, was literally being reused unresized as the favicon).
"""
from PIL import Image
import os

RAW = "/home/claude/tellen-automation/assets/raw"
OUT = "/home/claude/tellen-automation/assets"
os.makedirs(OUT, exist_ok=True)

LOGO = os.path.join(RAW, "ee0b6a177b1c.png")       # 825x645, 455KB — nav/footer mark + (mis)used as favicon
HERO = os.path.join(RAW, "36a5bf927179.jpg")        # 1100x850, 88KB — hero skyline background
ABOUT = os.path.join(RAW, "faae064a786a.jpg")       # 1536x1024, 111KB — about section visual


def save_png(im, path, max_w):
    w, h = im.size
    if w > max_w:
        ratio = max_w / w
        im = im.resize((max_w, round(h * ratio)), Image.LANCZOS)
    im.save(path, "PNG", optimize=True)
    print(path, os.path.getsize(path), "bytes", im.size)


def save_jpg(im, path, max_w, quality=78):
    w, h = im.size
    if w > max_w:
        ratio = max_w / w
        im = im.resize((max_w, round(h * ratio)), Image.LANCZOS)
    im.convert("RGB").save(path, "JPEG", quality=quality, optimize=True, progressive=True)
    print(path, os.path.getsize(path), "bytes", im.size)


# --- Logo: small inline mark for the nav/footer brand lockup ---
logo = Image.open(LOGO)
save_png(logo, os.path.join(OUT, "logo-mark.png"), max_w=160)

# --- Favicons, generated from the same approved logo, each a sane icon size ---
for size, name in [(32, "favicon-32.png"), (180, "apple-touch-icon.png"), (512, "icon-512.png")]:
    im = Image.open(LOGO).copy()
    im.thumbnail((size, size), Image.LANCZOS)
    # pad to square so it behaves as a normal favicon/app icon
    canvas = Image.new("RGB", (size, size), (5, 10, 18))  # matches --bg
    x = (size - im.width) // 2
    y = (size - im.height) // 2
    canvas.paste(im, (x, y))
    canvas.save(os.path.join(OUT, name), "PNG", optimize=True)
    print(name, os.path.getsize(os.path.join(OUT, name)), "bytes", canvas.size)

# --- Hero skyline background: one real file instead of 3 inline copies ---
hero = Image.open(HERO)
save_jpg(hero, os.path.join(OUT, "hero-skyline.jpg"), max_w=1600, quality=76)

# --- About section visual ---
about = Image.open(ABOUT)
save_jpg(about, os.path.join(OUT, "about-visual.jpg"), max_w=900, quality=78)

print("\nDone.")
