#!/usr/bin/env python3
"""Generate a small original 16-bit-style TOP-DOWN pixel-art tileset for the
Smallville town view. All hand-drawn pixel-by-pixel with Pillow -- no
external assets, no copyrighted tilesets. Outputs base64 PNG strings into
town_assets.py."""
import base64
import io
from PIL import Image

INK = (24, 20, 16, 255)

def px(img, x, y, color):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), color)

def rect(img, x0, y0, x1, y1, color):
    for y in range(y0, y1):
        for x in range(x0, x1):
            px(img, x, y, color)

def outline_rect(img, x0, y0, x1, y1, color, w=1):
    rect(img, x0, y0, x1, y0 + w, color)
    rect(img, x0, y1 - w, x1, y1, color)
    rect(img, x0, y0, x0 + w, y1, color)
    rect(img, x1 - w, y0, x1, y1, color)

def circle(img, cx, cy, r, color):
    for y in range(cy - r, cy + r):
        for x in range(cx - r, cx + r):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                px(img, x, y, color)

def to_b64(img):
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode()

assets = {}

# ---------- GRASS TILE (8x8, seamless) ----------
g = Image.new("RGBA", (8, 8), (74, 147, 74, 255))
dark = (61, 128, 61, 255)
light = (97, 173, 97, 255)
for (x, y) in [(1,1),(5,2),(2,5),(6,6),(0,4)]:
    px(g, x, y, dark)
for (x, y) in [(3,0),(7,3),(4,6)]:
    px(g, x, y, light)
assets["grass"] = to_b64(g)

# ---------- PATH TILE (8x8, seamless) ----------
p = Image.new("RGBA", (8, 8), (216, 196, 138, 255))
pd = (184, 159, 102, 255)
pl = (232, 216, 168, 255)
for (x, y) in [(2,1),(6,3),(1,5),(5,6)]:
    px(p, x, y, pd)
for (x, y) in [(4,0),(0,3),(7,6)]:
    px(p, x, y, pl)
assets["path"] = to_b64(p)

# ---------- ASPHALT TILE (8x8, seamless) -- for real city roads ----------
a = Image.new("RGBA", (8, 8), (42, 42, 46, 255))
ad = (32, 32, 36, 255)
al = (58, 58, 63, 255)
for (x, y) in [(1,2),(5,1),(3,5),(6,6),(0,6)]:
    px(a, x, y, ad)
for (x, y) in [(4,3),(7,0),(2,7)]:
    px(a, x, y, al)
assets["asphalt"] = to_b64(a)

# ---------- WATER TILE (8x8) ----------
w = Image.new("RGBA", (8, 8), (79, 163, 209, 255))
wl = (140, 200, 232, 255)
rect(w, 0, 2, 8, 3, wl)
rect(w, 0, 6, 8, 7, wl)
assets["water"] = to_b64(w)

# ---------- TREE, seen from above (18x18, transparent) ----------
t = Image.new("RGBA", (18, 18), (0,0,0,0))
canopy = (47, 125, 58, 255); canopy_d = (30, 84, 36, 255); canopy_l = (74, 163, 84, 255)
circle(t, 9, 9, 8, canopy)
for y in range(18):
    for x in range(9):
        if t.getpixel((x, y))[3]:
            px(t, x, y, canopy_d)
circle(t, 11, 6, 3, canopy_l)
assets["tree"] = to_b64(t)

# ---------- BENCH, seen from above (16x8) ----------
b = Image.new("RGBA", (16, 8), (0,0,0,0))
wood = (140, 100, 62, 255); wood_d = (107, 74, 47, 255)
rect(b, 0, 2, 16, 6, wood)
rect(b, 0, 2, 16, 3, wood_d)
for x in range(1, 16, 4):
    rect(b, x, 2, x+1, 6, wood_d)
assets["bench"] = to_b64(b)

# ---------- BUILDING GENERATOR (top-down roof view) ----------
def make_roof(w, h, roof_color, roof_shade, roof_light, accent=None, boarded=False,
              badge=None, entrance="s", extra=None):
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    x0, y0, x1, y1 = 2, 2, w - 2, h - 2

    def lerp(a, b, t):
        return tuple(int(a[i] + (b[i] - a[i]) * t) for i in range(3)) + (255,)

    # soft multi-band diagonal gradient (light corner -> base -> shade corner)
    # instead of one hard split, for a rendered rather than flat-fill look
    span = (x1 - x0) + (y1 - y0)
    for y in range(y0, y1):
        for x in range(x0, x1):
            t = ((x - x0) + (y - y0)) / max(span, 1)
            if t < 0.35:
                c = lerp(roof_light, roof_color, t / 0.35)
            elif t < 0.72:
                c = roof_color
            else:
                c = lerp(roof_color, roof_shade, (t - 0.72) / 0.28)
            px(img, x, y, c)
    # roof ridge line (structural highlight along the long axis)
    if w >= h:
        rect(img, x0 + 3, y0 + 2, x1 - 3, y0 + 3, roof_light)
    else:
        rect(img, x0 + 2, y0 + 3, x0 + 3, y1 - 3, roof_light)
    # visible foundation/eave edge -- a thin darker course along the bottom,
    # reads as a low wall peeking past the roofline for more real structure
    eave = (max(roof_shade[0]-18,0), max(roof_shade[1]-18,0), max(roof_shade[2]-18,0), 255)
    rect(img, x0, y1 - 3, x1, y1, eave)
    # soften the 4 corners so the silhouette isn't a hard rectangle
    for (cx, cy) in [(x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)]:
        px(img, cx, cy, (0, 0, 0, 0))
    outline_rect(img, x0, y0, x1, y1, INK, 1)
    for (cx, cy) in [(x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)]:
        px(img, cx, cy, (0, 0, 0, 0))
    # entrance notch (doorstep peeking out of the roof edge, reads as the door from above)
    door_w = max(10, w // 4)
    mat = (232, 216, 168, 255)
    if entrance == "s":
        dx0 = w // 2 - door_w // 2
        rect(img, dx0, y1 - 3, dx0 + door_w, y1 + 3, mat)
        outline_rect(img, dx0, y1 - 3, dx0 + door_w, y1 + 3, INK, 1)
    # status accent -- small skylights near the top edge, tinted by real state
    if accent:
        sw = max(8, w // 8)
        sy = y0 + 6
        for sx in (x0 + w // 4 - sw // 2, x1 - w // 4 - sw // 2):
            rect(img, sx, sy, sx + sw, sy + sw, accent)
            outline_rect(img, sx, sy, sx + sw, sy + sw, INK, 1)
    if badge:
        bw = 10
        bx, by = w // 2 - bw // 2, y0 + h // 2 - bw // 2 - 4
        badge(img, bx, by, bw)
    if extra:
        extra(img, x0, y0, x1, y1)
    if boarded:
        for i in range(-h, w, 6):
            for t_ in range(max(w, h)):
                xx, yy = x0 + i + t_, y0 + t_
                if x0 <= xx < x1 and y0 <= yy < y1:
                    px(img, xx, yy, (130, 112, 86, 200))
    return img

ROOF_RED = (179, 69, 58, 255); ROOF_RED_D = (140, 48, 40, 255); ROOF_RED_L = (206, 104, 92, 255)
ROOF_PURPLE = (122, 79, 160, 255); ROOF_PURPLE_D = (91, 56, 125, 255); ROOF_PURPLE_L = (152, 114, 188, 255)
ROOF_GREEN = (63, 143, 92, 255); ROOF_GREEN_D = (44, 110, 68, 255); ROOF_GREEN_L = (94, 173, 120, 255)
ROOF_BLUE = (58, 111, 168, 255); ROOF_BLUE_D = (40, 82, 130, 255); ROOF_BLUE_L = (94, 148, 201, 255)
ROOF_NAVY = (52, 74, 122, 255); ROOF_NAVY_D = (36, 54, 94, 255); ROOF_NAVY_L = (84, 108, 156, 255)
ROOF_FIRE = (196, 62, 48, 255); ROOF_FIRE_D = (156, 42, 32, 255); ROOF_FIRE_L = (222, 98, 78, 255)
ROOF_GREY = (150, 150, 150, 255); ROOF_GREY_D = (114, 114, 114, 255); ROOF_GREY_L = (178, 178, 178, 255)

WIN_BUY = (124, 252, 154, 255)
WIN_SELL = (255, 179, 71, 255)
WIN_DIM = (110, 118, 132, 255)
WIN_LIT = (255, 227, 122, 255)

def badge_star(img, x, y, s):
    gold = (255, 214, 92, 255)
    for (dx, dy) in [(4,0),(3,1),(4,1),(5,1),(2,2),(3,2),(4,2),(5,2),(6,2),
                      (1,3),(2,3),(3,3),(4,3),(5,3),(6,3),(7,3),(3,4),(4,4),(5,4)]:
        px(img, x+dx, y+dy, gold)

def badge_cross(img, x, y, s):
    red = (230, 60, 50, 255)
    rect(img, x+3, y, x+6, y+9, red)
    rect(img, x, y+3, x+9, y+6, red)

# ---- distinguishing roof details, so buildings read as different, not just recolored ----
def detail_chimney(img, x0, y0, x1, y1):
    c = (110, 110, 110, 255); cd = (80, 80, 80, 255)
    rect(img, x1 - 12, y0 + 3, x1 - 5, y0 + 13, c)
    rect(img, x1 - 12, y0 + 3, x1 - 9, y0 + 13, cd)
    outline_rect(img, x1 - 12, y0 + 3, x1 - 5, y0 + 13, INK, 1)

def detail_dormer(img, x0, y0, x1, y1):
    cx = (x0 + x1) // 2
    d = (232, 226, 210, 255)
    rect(img, cx - 6, y0 - 4, cx + 6, y0 + 6, d)
    outline_rect(img, cx - 6, y0 - 4, cx + 6, y0 + 6, INK, 1)
    win = (200, 224, 255, 255)
    rect(img, cx - 3, y0, cx + 3, y0 + 4, win)

def detail_vane(img, x0, y0, x1, y1):
    cx = (x0 + x1) // 2
    m = (90, 90, 90, 255)
    rect(img, cx, y0 - 8, cx + 1, y0 + 2, m)
    rect(img, cx - 4, y0 - 6, cx + 5, y0 - 5, m)

def detail_cupola(img, x0, y0, x1, y1):
    cx, cy = (x0 + x1) // 2, (y0 + y1) // 2
    circle(img, cx, cy, 9, (200, 224, 255, 255))
    outline_rect(img, cx - 9, cy - 9, cx + 9, cy + 9, INK, 1)
    rect(img, cx, y0 - 10, cx + 1, y0, (90, 90, 90, 255))
    rect(img, cx - 3, y0 - 10, cx + 5, y0 - 7, (214, 60, 60, 255))

def detail_awning(img, x0, y0, x1, y1):
    stripe1, stripe2 = (192, 57, 43, 255), (244, 236, 216, 255)
    y = y1
    for sx in range(x0, x1, 6):
        rect(img, sx, y, sx + 3, y + 5, stripe1)
        rect(img, sx + 3, y, sx + 6, y + 5, stripe2)
    outline_rect(img, x0, y, x1, y + 5, INK, 1)

def detail_loading(img, x0, y0, x1, y1):
    yellow, black = (240, 200, 40, 255), (40, 36, 30, 255)
    y = y1 - 5
    for i, sx in enumerate(range(x0, x1, 5)):
        rect(img, sx, y, sx + 5, y + 4, yellow if i % 2 == 0 else black)

def detail_flag(img, x0, y0, x1, y1):
    pole = (90, 90, 90, 255)
    rect(img, x1 - 4, y0 - 12, x1 - 3, y0 + 2, pole)
    rect(img, x1 - 3, y0 - 12, x1 + 6, y0 - 6, (255, 214, 92, 255))
    outline_rect(img, x1 - 3, y0 - 12, x1 + 6, y0 - 6, INK, 1)

def detail_bay_doors(img, x0, y0, x1, y1):
    grey, grey_d = (200, 200, 200, 255), (160, 160, 160, 255)
    w3 = (x1 - x0) // 2 - 3
    for bx in (x0 + 2, x0 + w3 + 8):
        rect(img, bx, y1 - 10, bx + w3, y1 - 3, grey)
        for i in range(bx, bx + w3, 4):
            rect(img, i, y1 - 10, i + 1, y1 - 3, grey_d)
        outline_rect(img, bx, y1 - 10, bx + w3, y1 - 3, INK, 1)

hall_lit = make_roof(96, 68, ROOF_PURPLE, ROOF_PURPLE_D, ROOF_PURPLE_L, accent=WIN_LIT, extra=detail_cupola)
hall_dim = make_roof(96, 68, ROOF_PURPLE, ROOF_PURPLE_D, ROOF_PURPLE_L, accent=WIN_DIM, extra=detail_cupola)
assets["hall_lit"] = to_b64(hall_lit)
assets["hall_dim"] = to_b64(hall_dim)

# Each house keeps ONE structural detail (chimney/dormer/vane) tied to its
# position in the row, independent of its live zone-status color -- so the
# row reads as 7 different houses even when several share the same status.
# 4 statuses x 3 details = 12 baked variants; JS picks by (status, i % 3).
HOUSE_DETAILS = [detail_chimney, detail_dormer, detail_vane]
HOUSE_STATUSES = {
    "buy":    (ROOF_RED, ROOF_RED_D, ROOF_RED_L, WIN_BUY, False),
    "sell":   (ROOF_RED, ROOF_RED_D, ROOF_RED_L, WIN_SELL, False),
    "dim":    (ROOF_RED, ROOF_RED_D, ROOF_RED_L, WIN_DIM, False),
    "narrow": (ROOF_GREY, ROOF_GREY_D, ROOF_GREY_L, WIN_DIM, True),
}
for status, (rc, rd, rl, win, is_boarded) in HOUSE_STATUSES.items():
    for di, detail_fn in enumerate(HOUSE_DETAILS):
        key = f"house_{status}_{di}"
        assets[key] = to_b64(make_roof(56, 48, rc, rd, rl, accent=win, boarded=is_boarded, extra=detail_fn))
house_buy = Image.open(io.BytesIO(base64.b64decode(assets["house_buy_0"])))
house_narrow = Image.open(io.BytesIO(base64.b64decode(assets["house_narrow_0"])))

cafe = make_roof(60, 46, ROOF_GREEN, ROOF_GREEN_D, ROOF_GREEN_L, accent=WIN_LIT, extra=detail_awning)
assets["cafe"] = to_b64(cafe)

grocery = make_roof(60, 46, ROOF_BLUE, ROOF_BLUE_D, ROOF_BLUE_L, accent=WIN_LIT, extra=detail_loading)
assets["grocery"] = to_b64(grocery)

sheriff_calm = make_roof(52, 46, ROOF_NAVY, ROOF_NAVY_D, ROOF_NAVY_L, badge=badge_star, extra=detail_flag)
sheriff_alert = make_roof(52, 46, ROOF_NAVY, ROOF_NAVY_D, ROOF_NAVY_L, badge=badge_star, accent=(255,179,71,255), extra=detail_flag)
assets["sheriff_calm"] = to_b64(sheriff_calm)
assets["sheriff_alert"] = to_b64(sheriff_alert)

fire_calm = make_roof(52, 46, ROOF_FIRE, ROOF_FIRE_D, ROOF_FIRE_L, badge=badge_cross, extra=detail_bay_doors)
fire_alert = make_roof(52, 46, ROOF_FIRE, ROOF_FIRE_D, ROOF_FIRE_L, badge=badge_cross, accent=(255,90,80,255), extra=detail_bay_doors)
assets["fire_calm"] = to_b64(fire_calm)
assets["fire_alert"] = to_b64(fire_alert)

# ---------- PEOPLE, seen from above (16x18, transparent) ----------
def make_person(hair, outfit, outfit_shade, hat=None, hat_band=None, badge_color=None):
    img = Image.new("RGBA", (16, 18), (0, 0, 0, 0))
    # feet peeking out beneath the body
    shoe = (58, 46, 38, 255)
    rect(img, 4, 15, 7, 18, shoe)
    rect(img, 9, 15, 12, 18, shoe)
    # body (shirt), seen from above -- rounded rectangle
    rect(img, 2, 6, 14, 16, outfit)
    for (x, y) in [(2,6),(13,6),(2,15),(13,15)]:
        px(img, x, y, (0,0,0,0))
    rect(img, 2, 6, 8, 16, outfit_shade)
    outline_rect(img, 2, 6, 14, 16, INK, 1)
    if badge_color:
        px(img, 5, 9, badge_color); px(img, 6, 9, badge_color)
    # head / hair, seen from above
    if hat:
        circle(img, 8, 6, 7, hat)
        if hat_band:
            rect(img, 1, 6, 15, 8, hat_band)
        outline_rect(img, 1, 0, 15, 12, (0,0,0,0), 0)
    else:
        circle(img, 8, 6, 6, hair)
    for y in range(18):
        for x in range(16):
            c = img.getpixel((x, y))
            if c[3] and (x-8)**2+(y-6)**2 <= 49 and (hat or (x-8)**2+(y-6)**2 <= 36):
                pass
    return img

# deterministic per-symbol trader palette (index-based, not random)
TRADER_PALETTE = [
    ((255, 158, 71, 255), (214, 122, 45, 255)),   # orange
    ((84, 191, 191, 255), (54, 140, 140, 255)),   # teal
    ((222, 120, 189, 255), (176, 84, 148, 255)),  # pink
    ((176, 214, 82, 255), (132, 168, 52, 255)),   # lime
    ((158, 122, 230, 255), (114, 84, 176, 255)),  # violet
    ((240, 214, 90, 255), (196, 168, 56, 255)),   # gold
    ((122, 168, 240, 255), (84, 122, 196, 255)),  # sky blue
]
HAIR_A = (61, 42, 26, 255); HAIR_B = (40, 32, 30, 255)

for i, (outfit, shade) in enumerate(TRADER_PALETTE):
    hair = HAIR_A if i % 2 == 0 else HAIR_B
    assets[f"trader_{i}"] = to_b64(make_person(hair, outfit, shade))

# ---- HOMES, one per trader, roof tinted a muted version of their own
# outfit color so a trader visually "belongs" to their house. Small cozy
# cottage, always has a chimney, no status accent (a home isn't market data).
def mute(c, amt=0.45):
    grey = 150
    return tuple(int(c[i] * (1 - amt) + grey * amt) for i in range(3)) + (255,)

for i, (outfit, shade) in enumerate(TRADER_PALETTE):
    home_roof = mute(outfit[:3], 0.35)
    home_shade = mute(shade[:3], 0.30)
    home_light = tuple(min(c + 40, 255) for c in home_roof[:3]) + (255,)
    home = make_roof(46, 42, home_roof, home_shade, home_light, extra=detail_chimney)
    assets[f"home_{i}"] = to_b64(home)

eva = make_person(HAIR_A, (91, 140, 255, 255), (58, 96, 200, 255))
assets["eva"] = to_b64(eva)

sheriff_hat = (40, 60, 100, 255); sheriff_band = (255, 214, 92, 255)
sheriff_person = make_person(None, (52, 74, 122, 255), (36, 54, 94, 255),
                              hat=sheriff_hat, hat_band=sheriff_band, badge_color=(255,214,92,255))
assets["sheriff_person"] = to_b64(sheriff_person)

fire_hat = (214, 178, 40, 255)
fire_person = make_person(None, (196, 62, 48, 255), (156, 42, 32, 255),
                           hat=fire_hat, hat_band=(230,60,50,255))
assets["fire_person"] = to_b64(fire_person)

# ---------- write module ----------
lines = ['"""Auto-generated pixel-art assets for the Smallville town view (top-down).\n'
         'Hand-drawn with Pillow -- original art, not copied from any tileset.\n'
         'Regenerate with gen_town_assets.py if you want to tweak the look."""\n']
for name, b64 in assets.items():
    lines.append(f'{name.upper()}_PNG = "{b64}"')
out_path = "/Users/sagewilliams/Desktop/Sages trading bot/town_assets.py"
with open(out_path, "w") as f:
    f.write("\n".join(lines) + "\n")
print("wrote", out_path, "with", len(assets), "assets")

# contact sheet for visual review
home_0 = Image.open(io.BytesIO(base64.b64decode(assets["home_0"])))
home_3 = Image.open(io.BytesIO(base64.b64decode(assets["home_3"])))
imgs_to_show = [
    ("grass", Image.open(io.BytesIO(base64.b64decode(assets["grass"]))).resize((48,48), Image.NEAREST)),
    ("path", Image.open(io.BytesIO(base64.b64decode(assets["path"]))).resize((48,48), Image.NEAREST)),
    ("tree", t.resize((72,72), Image.NEAREST)),
    ("hall_lit", hall_lit.resize((288,204), Image.NEAREST)),
    ("house_buy", house_buy.resize((168,144), Image.NEAREST)),
    ("house_narrow", house_narrow.resize((168,144), Image.NEAREST)),
    ("home_0", home_0.resize((115,105), Image.NEAREST)),
    ("home_3", home_3.resize((115,105), Image.NEAREST)),
    ("cafe", cafe.resize((120,92), Image.NEAREST)),
    ("sheriff_calm", sheriff_calm.resize((104,92), Image.NEAREST)),
    ("fire_alert", fire_alert.resize((104,92), Image.NEAREST)),
    ("eva", eva.resize((64,72), Image.NEAREST)),
    ("trader_0", Image.open(io.BytesIO(base64.b64decode(assets["trader_0"]))).resize((64,72), Image.NEAREST)),
    ("trader_2", Image.open(io.BytesIO(base64.b64decode(assets["trader_2"]))).resize((64,72), Image.NEAREST)),
    ("sheriff_person", sheriff_person.resize((64,72), Image.NEAREST)),
    ("fire_person", fire_person.resize((64,72), Image.NEAREST)),
]
sheet = Image.new("RGBA", (1500, 220), (20, 60, 30, 255))
x = 4
for name, im in imgs_to_show:
    sheet.paste(im, (x, 4), im if im.mode == "RGBA" else None)
    x += im.width + 12
sheet.save("/private/tmp/claude-501/-Users-sagewilliams-Desktop-World-Domination/078e0397-347a-4124-b98c-328086eb407d/scratchpad/contact_sheet.png")
print("wrote contact sheet")
