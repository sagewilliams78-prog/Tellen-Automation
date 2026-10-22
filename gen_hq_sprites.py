#!/usr/bin/env python3
"""
Phase 1 sprite generator for Eva's Trading HQ (the Smallville /hq view).

Writes real PNG files into hq/sprites/ so artwork can be swapped later
without touching any application code -- the renderer only ever refers to
sprites by filename. All art is drawn pixel-by-pixel with Pillow; nothing
here is copied from a commercial tileset.

Phase 1 covers ground + structure only:
  grass, sidewalk, wood floor, tile floor, carpet, wall fill, door.
Furniture and characters arrive in Phase 2/3.

Run:  python3 gen_hq_sprites.py
"""
import os
from PIL import Image

TILE = 16                      # every world tile is 16x16 source pixels
OUT = os.path.join(os.path.dirname(os.path.abspath(__file__)), "hq", "sprites")

INK = (26, 22, 18, 255)        # the single dark outline colour used everywhere


def px(img, x, y, c):
    if 0 <= x < img.width and 0 <= y < img.height:
        img.putpixel((x, y), c)


def rect(img, x0, y0, x1, y1, c):
    for y in range(y0, y1):
        for x in range(x0, x1):
            px(img, x, y, c)


def circle(img, cx, cy, r, color):
    for y in range(cy - r, cy + r + 1):
        for x in range(cx - r, cx + r + 1):
            if (x - cx) ** 2 + (y - cy) ** 2 <= r * r:
                px(img, x, y, color)


def tile(base):
    return Image.new("RGBA", (TILE, TILE), base)


def save(img, name):
    img.save(os.path.join(OUT, name + ".png"))
    return name


def build():
    os.makedirs(OUT, exist_ok=True)
    made = []

    # ---------- GRASS ----------------------------------------------------
    # Seamless: only interior pixels are decorated, edges stay base colour.
    g = tile((104, 168, 86, 255))
    dark = (88, 148, 72, 255)
    lite = (124, 188, 104, 255)
    for (x, y) in [(3, 2), (11, 5), (6, 9), (13, 12), (1, 13), (8, 1)]:
        px(g, x, y, dark)
        px(g, x + 1, y, dark)
    for (x, y) in [(5, 6), (12, 3), (2, 10), (9, 13)]:
        px(g, x, y, lite)
    made.append(save(g, "grass"))

    # ---------- SIDEWALK / OUTDOOR PATH ----------------------------------
    # Paving slabs: light stone with a darker mortar line on two edges so
    # tiles read as a grid when repeated.
    s = tile((208, 202, 188, 255))
    mortar = (176, 169, 154, 255)
    rect(s, 0, 0, TILE, 1, mortar)
    rect(s, 0, 0, 1, TILE, mortar)
    for (x, y) in [(5, 6), (11, 10), (7, 13)]:
        px(s, x, y, (192, 186, 172, 255))
    made.append(save(s, "sidewalk"))

    # ---------- WOOD FLOOR ------------------------------------------------
    # Light wood planks, horizontal, with staggered end-joints.
    w = tile((214, 166, 110, 255))
    grain = (198, 148, 94, 255)
    joint = (168, 122, 74, 255)
    rect(w, 0, 7, TILE, 8, joint)         # plank divider
    rect(w, 0, 15, TILE, 16, joint)
    rect(w, 4, 0, 5, 7, joint)            # staggered end joints
    rect(w, 11, 8, 12, 15, joint)
    for (x, y) in [(2, 3), (9, 3), (13, 2), (6, 11), (14, 12)]:
        rect(w, x, y, x + 3, y + 1, grain)
    made.append(save(w, "floor_wood"))

    # ---------- TILE FLOOR ------------------------------------------------
    # Small chequered pattern, the "utility room" floor.
    t = tile((232, 228, 217, 255))
    alt = (214, 209, 196, 255)
    rect(t, 0, 0, 8, 8, alt)
    rect(t, 8, 8, 16, 16, alt)
    line = (198, 192, 178, 255)
    rect(t, 0, 0, TILE, 1, line)
    rect(t, 0, 0, 1, TILE, line)
    made.append(save(t, "floor_tile"))

    # ---------- CARPET ----------------------------------------------------
    # For the executive room -- flat weave with a subtle fleck.
    c = tile((122, 106, 148, 255))
    fleck = (108, 93, 132, 255)
    for (x, y) in [(2, 3), (7, 6), (12, 2), (5, 11), (14, 9), (9, 14)]:
        px(c, x, y, fleck)
    rect(c, 0, 0, TILE, 1, fleck)
    made.append(save(c, "floor_carpet"))

    # ---------- WALL FILL -------------------------------------------------
    # Walls are drawn by the renderer as thick bands filled with this tile
    # and stroked with INK, which avoids needing 16 corner variants.
    v = tile((242, 239, 231, 255))
    shade = (223, 218, 206, 255)
    rect(v, 0, 12, TILE, 16, shade)       # base shadow along the wall foot
    for (x, y) in [(3, 4), (10, 7)]:
        px(v, x, y, (232, 228, 218, 255))
    made.append(save(v, "wall"))

    # ---------- DOOR ------------------------------------------------------
    # A doorway mat/threshold drawn in the wall gap.
    d = tile((198, 150, 96, 255))
    rect(d, 0, 0, TILE, 2, INK)
    rect(d, 0, 14, TILE, 16, INK)
    rect(d, 2, 4, 14, 12, (176, 130, 80, 255))
    made.append(save(d, "door"))

    return made


# ============================================================
#  PHASE 2 -- FURNITURE
#  Top-down objects. Consistent language: flat colour body, a lighter
#  strip along the top edge (light comes from the top-left), a darker
#  strip along the bottom, and a hard INK outline with cut corners so
#  silhouettes don't read as plain rectangles.
# ============================================================

def shade_of(c, amt=0.78):
    return (int(c[0] * amt), int(c[1] * amt), int(c[2] * amt), 255)


def light_of(c, amt=1.18):
    return (min(int(c[0] * amt), 255), min(int(c[1] * amt), 255),
            min(int(c[2] * amt), 255), 255)


def outline_box(img, x0, y0, x1, y1, cut=1):
    """Hard outline with cut corners."""
    rect(img, x0, y0, x1, y0 + 1, INK)
    rect(img, x0, y1 - 1, x1, y1, INK)
    rect(img, x0, y0, x0 + 1, y1, INK)
    rect(img, x1 - 1, y0, x1, y1, INK)
    if cut:
        for (cx, cy) in [(x0, y0), (x1 - 1, y0), (x0, y1 - 1), (x1 - 1, y1 - 1)]:
            px(img, cx, cy, (0, 0, 0, 0))


def body(w, h, color, foot=None):
    """Base furniture block."""
    img = Image.new("RGBA", (w, h), (0, 0, 0, 0))
    rect(img, 0, 0, w, h, color)
    rect(img, 1, 1, w - 1, 3, light_of(color))            # top highlight
    rect(img, 0, h - max(3, h // 6), w, h, shade_of(color, foot or 0.74))
    outline_box(img, 0, 0, w, h)
    return img


def build_furniture():
    made = []
    T = TILE

    WOOD      = (176, 124, 74, 255)
    WOOD_DARK = (138, 96, 56, 255)
    METAL     = (150, 156, 166, 255)
    WHITE     = (228, 226, 218, 255)
    SCREEN    = (44, 52, 64, 255)
    GLOW      = (126, 200, 226, 255)

    def screen_on(img, x0, y0, x1, y1, glow=GLOW):
        rect(img, x0, y0, x1, y1, SCREEN)
        rect(img, x0 + 1, y0 + 1, x1 - 1, y0 + 2, glow)
        rect(img, x0 + 1, y0 + 3, x1 - 3, y0 + 4, shade_of(glow, .7))
        outline_box(img, x0, y0, x1, y1, cut=0)

    # ---- desk 3x2, monitor + keyboard built in --------------------------
    d = body(3 * T, 2 * T, WOOD)
    screen_on(d, 8, 5, 3 * T - 8, 15)                     # monitor
    rect(d, 3 * T // 2 - 7, 20, 3 * T // 2 + 7, 24, (60, 62, 70, 255))  # keyboard
    outline_box(d, 3 * T // 2 - 7, 20, 3 * T // 2 + 7, 24, cut=0)
    made.append(save(d, "desk"))

    # ---- small desk 2x2 --------------------------------------------------
    d2 = body(2 * T, 2 * T, WOOD)
    screen_on(d2, 6, 5, 2 * T - 6, 15)
    rect(d2, T - 6, 20, T + 6, 23, (60, 62, 70, 255))
    made.append(save(d2, "desk_small"))

    # ---- chair -----------------------------------------------------------
    c = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    seat = (92, 104, 130, 255)
    rect(c, 3, 5, T - 3, T - 2, seat)
    rect(c, 3, 5, T - 3, 7, light_of(seat))
    outline_box(c, 3, 5, T - 3, T - 2)
    rect(c, 2, 1, T - 2, 5, shade_of(seat, .82))          # backrest
    outline_box(c, 2, 1, T - 2, 5)
    made.append(save(c, "chair"))

    # ---- filing cabinet 1x2 ---------------------------------------------
    fc = body(T, 2 * T, METAL)
    for y in (7, 15, 23):
        rect(fc, 4, y, T - 4, y + 1, shade_of(METAL, .62))
        rect(fc, 6, y - 1, T - 6, y, (206, 210, 216, 255))
    made.append(save(fc, "filing_cabinet"))

    # ---- bookshelf 2x1 ---------------------------------------------------
    bs = body(2 * T, T, WOOD_DARK)
    cols = [(196, 84, 74, 255), (86, 140, 190, 255), (214, 176, 78, 255),
            (108, 170, 116, 255), (150, 116, 190, 255), (206, 122, 78, 255)]
    for i, col in enumerate(cols):
        x = 3 + i * 4
        rect(bs, x, 4, x + 3, T - 4, col)
    outline_box(bs, 0, 0, 2 * T, T)
    made.append(save(bs, "bookshelf"))

    # ---- storage rack 3x1 (boxes on shelves) ----------------------------
    rk = body(3 * T, T, METAL)
    for i in range(4):
        x = 3 + i * 11
        rect(rk, x, 4, x + 9, T - 4, (188, 146, 96, 255))
        outline_box(rk, x, 4, x + 9, T - 4, cut=0)
    made.append(save(rk, "rack"))

    # ---- meeting table 6x4 ----------------------------------------------
    tb = body(6 * T, 4 * T, WOOD)
    inner = shade_of(WOOD, .88)
    rect(tb, 6, 8, 6 * T - 6, 4 * T - 8, inner)
    outline_box(tb, 6, 8, 6 * T - 6, 4 * T - 8, cut=0)
    made.append(save(tb, "table_big"))

    # ---- couch 4x2 -------------------------------------------------------
    cv = (168, 96, 104, 255)
    cs = Image.new("RGBA", (4 * T, 2 * T), (0, 0, 0, 0))
    rect(cs, 0, 6, 4 * T, 2 * T, cv)
    rect(cs, 0, 6, 4 * T, 8, light_of(cv))
    outline_box(cs, 0, 6, 4 * T, 2 * T)
    rect(cs, 0, 0, 4 * T, 8, shade_of(cv, .84))           # backrest
    outline_box(cs, 0, 0, 4 * T, 8)
    for x in (0, 4 * T - 7):                              # arms
        rect(cs, x, 4, x + 7, 2 * T, shade_of(cv, .9))
        outline_box(cs, x, 4, x + 7, 2 * T)
    rect(cs, 4 * T // 2 - 1, 10, 4 * T // 2 + 1, 2 * T - 3, shade_of(cv, .8))
    made.append(save(cs, "couch"))

    # ---- fridge 2x2 ------------------------------------------------------
    fr = body(2 * T, 2 * T, WHITE)
    rect(fr, 3, 2 * T // 2 - 1, 2 * T - 3, 2 * T // 2 + 1, shade_of(WHITE, .7))
    rect(fr, 2 * T - 8, 8, 2 * T - 6, 14, (120, 126, 136, 255))     # handle
    rect(fr, 2 * T - 8, 2 * T - 12, 2 * T - 6, 2 * T - 6, (120, 126, 136, 255))
    made.append(save(fr, "fridge"))

    # ---- coffee machine 1x1 ---------------------------------------------
    cm = body(T, T, (58, 62, 70, 255))
    rect(cm, 3, 4, T - 3, 8, (196, 90, 70, 255))
    rect(cm, 5, 10, T - 5, T - 3, (166, 172, 182, 255))
    made.append(save(cm, "coffee"))

    # ---- counter 4x1 -----------------------------------------------------
    ct = body(4 * T, T, (204, 198, 184, 255))
    rect(ct, 2 * T - 6, 4, 2 * T + 6, T - 4, (150, 156, 166, 255))   # sink
    outline_box(ct, 2 * T - 6, 4, 2 * T + 6, T - 4, cut=0)
    made.append(save(ct, "counter"))

    # ---- plant 1x1 -------------------------------------------------------
    pl = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    pot = (172, 106, 74, 255)
    rect(pl, 4, T - 6, T - 4, T - 1, pot)
    outline_box(pl, 4, T - 6, T - 4, T - 1)
    leaf = (86, 152, 84, 255)
    for (x, y, w_, h_) in [(5, 3, 6, 8), (8, 1, 5, 7), (3, 6, 5, 5), (9, 6, 5, 5)]:
        rect(pl, x, y, x + w_, y + h_, leaf)
    rect(pl, 6, 4, 9, 7, light_of(leaf))
    made.append(save(pl, "plant"))

    # ---- crate 1x1 -------------------------------------------------------
    cr = body(T, T, (188, 146, 96, 255))
    rect(cr, 2, T // 2 - 1, T - 2, T // 2 + 1, shade_of((188, 146, 96, 255), .7))
    rect(cr, T // 2 - 1, 3, T // 2 + 1, T - 3, shade_of((188, 146, 96, 255), .7))
    made.append(save(cr, "crate"))

    # ---- wall screen 3x1 (analytics display) ----------------------------
    ws = Image.new("RGBA", (3 * T, T), (0, 0, 0, 0))
    rect(ws, 0, 0, 3 * T, T, (34, 38, 48, 255))
    screen_on(ws, 2, 2, 3 * T - 2, T - 3)
    for i, hgt in enumerate([5, 8, 4, 9, 6, 7]):          # tiny bar chart
        x = 6 + i * 7
        rect(ws, x, T - 4 - hgt, x + 4, T - 4, (110, 196, 140, 255))
    made.append(save(ws, "wallscreen"))

    # ---- whiteboard 3x1 --------------------------------------------------
    wb = body(3 * T, T, (238, 238, 234, 255))
    for (x, y, w_) in [(5, 5, 20), (5, 9, 30), (30, 5, 12), (5, 12, 16)]:
        rect(wb, x, y, x + w_, y + 1, (120, 132, 150, 255))
    made.append(save(wb, "whiteboard"))

    # ---- server rack 2x2 (mechanic bay) ---------------------------------
    sv = body(2 * T, 2 * T, (54, 58, 68, 255))
    for i in range(5):
        y = 4 + i * 5
        rect(sv, 4, y, 2 * T - 4, y + 3, (74, 80, 92, 255))
        px(sv, 2 * T - 7, y + 1, (110, 226, 140, 255))    # status LEDs
        px(sv, 2 * T - 9, y + 1, (226, 190, 110, 255))
    made.append(save(sv, "server_rack"))

    # ---- workbench 4x2 ---------------------------------------------------
    bn = body(4 * T, 2 * T, WOOD_DARK)
    rect(bn, 4, 5, 4 * T - 4, 8, (150, 156, 166, 255))    # tool strip
    for i in range(6):
        x = 7 + i * 9
        rect(bn, x, 12, x + 5, 2 * T - 6, shade_of(WOOD_DARK, .8))
    made.append(save(bn, "workbench"))

    # ---- rug 4x3 ---------------------------------------------------------
    rgc = (128, 96, 150, 255)
    rg = Image.new("RGBA", (4 * T, 3 * T), (0, 0, 0, 0))
    rect(rg, 0, 0, 4 * T, 3 * T, rgc)
    rect(rg, 4, 4, 4 * T - 4, 3 * T - 4, light_of(rgc, 1.1))
    rect(rg, 9, 9, 4 * T - 9, 3 * T - 9, rgc)
    outline_box(rg, 0, 0, 4 * T, 3 * T)
    made.append(save(rg, "rug"))

    return made


# ============================================================
#  PHASE 3 -- CHARACTERS
#  One spritesheet per character: 4 rows (down, left, right, up) x
#  3 columns (stand, step-A, step-B), each frame CW x CH.
#  Slight 3/4 view -- faces read from above, which is what the
#  reference art does; a strict overhead view turns people into blobs.
# ============================================================

CW, CH = 16, 24
DIRS = ["down", "left", "right", "up"]


def silhouette_outline(img, color=INK):
    """Draw ONE dark outline around the whole character.

    Outlining each body part separately (head, torso, every arm and leg)
    leaves a 3px-wide limb with 2px of border and 1px of fill -- the sprite
    turns into a black smear. Tracing the silhouette once is how pixel art
    actually does it, and keeps the interior readable.
    """
    src = img.load()
    out = img.copy()
    w, h = img.size
    for y in range(h):
        for x in range(w):
            if src[x, y][3]:
                continue
            for dx, dy in ((1, 0), (-1, 0), (0, 1), (0, -1)):
                nx, ny = x + dx, y + dy
                if 0 <= nx < w and 0 <= ny < h and src[nx, ny][3]:
                    out.putpixel((x, y), color)
                    break
    return out


def char_frame(direction, step, pal):
    """One character frame. `step` is 0 (stand), 1 or 2 (walk poses)."""
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    skin, hair = pal["skin"], pal["hair"]
    shirt, shirt_d = pal["shirt"], shade_of(pal["shirt"], .76)
    pants, shoes = pal["pants"], pal["shoes"]

    side = direction in ("left", "right")
    back = direction == "up"

    # ---- legs & shoes (drawn first so the torso overlaps them) -------
    # Steps only lift a foot, never extend below the baseline, so frames
    # stay inside the cell.
    la, lb = (0, 0) if step == 0 else ((-1, 0) if step == 1 else (0, -1))
    if side:
        rect(img, 6, 18, 10, 21 + la, pants)
        rect(img, 5, 21 + la, 10, 23 + la, shoes)
    else:
        rect(img, 4, 18, 7, 21 + la, pants)
        rect(img, 9, 18, 12, 21 + lb, pants)
        rect(img, 4, 21 + la, 7, 23 + la, shoes)
        rect(img, 9, 21 + lb, 12, 23 + lb, shoes)

    # ---- torso -------------------------------------------------------
    bx0, bx1 = (5, 12) if side else (3, 13)
    rect(img, bx0, 12, bx1, 19, shirt)
    rect(img, bx0, 12, bx1, 14, light_of(shirt))          # shoulder light
    rect(img, bx0, 18, bx1, 19, shirt_d)                  # hem
    if not side and not back:
        rect(img, 7, 14, 9, 18, shirt_d)                  # placket

    # ---- arms (after the torso: in profile the near arm reads in FRONT
    #      of the body, otherwise it is hidden behind it) ---------------
    swing = 0 if step == 0 else (1 if step == 1 else -1)
    if side:
        ax = 5 if direction == "left" else 9
        rect(img, ax, 13 + swing, ax + 3, 18 + swing, shirt_d)
    else:
        rect(img, 1, 13 + swing, 3, 18 + swing, shirt_d)
        rect(img, 13, 13 - swing, 15, 18 - swing, shirt_d)

    # ---- head --------------------------------------------------------
    hx0, hx1 = (5, 12) if side else (4, 12)
    rect(img, hx0, 5, hx1, 12, skin)
    if back:
        rect(img, hx0, 2, hx1, 11, hair)                  # back of the head
    elif side:
        rect(img, hx0, 2, hx1, 8, hair)
        rect(img, hx0, 2, hx0 + 2, 11, hair)              # sideburn
        px(img, 10 if direction == "right" else 6, 8, INK)
    else:
        rect(img, hx0, 2, hx1, 7, hair)                   # fringe
        rect(img, 6, 8, 8, 9, INK)                        # eyes
        rect(img, 9, 8, 11, 9, INK)
        rect(img, 7, 10, 9, 11, shade_of(skin, .8))       # mouth

    return silhouette_outline(img)


def char_sheet(pal):
    sheet = Image.new("RGBA", (CW * 3, CH * 4), (0, 0, 0, 0))
    for r, d in enumerate(DIRS):
        for c in range(3):
            sheet.paste(char_frame(d, c, pal), (c * CW, r * CH))
    return sheet


SKIN_A = (238, 195, 154, 255)
SKIN_B = (214, 162, 118, 255)
SKIN_C = (176, 124, 86, 255)
DARK_PANTS = (58, 62, 78, 255)
SHOE = (48, 42, 38, 255)

# id -> palette. Colour is the only thing that differs, so characters stay
# visually consistent with one another.
CHARACTERS = {
    "eva":      dict(skin=SKIN_A, hair=(84, 58, 40, 255),  shirt=(84, 132, 226, 255), pants=DARK_PANTS, shoes=SHOE),
    "risk":     dict(skin=SKIN_B, hair=(70, 70, 76, 255),  shirt=(48, 70, 116, 255),  pants=DARK_PANTS, shoes=SHOE),
    "mechanic": dict(skin=SKIN_C, hair=(42, 34, 30, 255),  shirt=(196, 96, 56, 255),  pants=(74, 66, 58, 255), shoes=SHOE),
    "trader0":  dict(skin=SKIN_A, hair=(60, 44, 34, 255),  shirt=(226, 138, 62, 255), pants=DARK_PANTS, shoes=SHOE),
    "trader1":  dict(skin=SKIN_B, hair=(34, 30, 28, 255),  shirt=(72, 172, 168, 255), pants=DARK_PANTS, shoes=SHOE),
    "trader2":  dict(skin=SKIN_C, hair=(52, 40, 32, 255),  shirt=(206, 106, 166, 255),pants=DARK_PANTS, shoes=SHOE),
    "trader3":  dict(skin=SKIN_A, hair=(146, 96, 46, 255), shirt=(150, 190, 74, 255), pants=DARK_PANTS, shoes=SHOE),
    "trader4":  dict(skin=SKIN_B, hair=(40, 36, 34, 255),  shirt=(142, 110, 210, 255),pants=DARK_PANTS, shoes=SHOE),
    "trader5":  dict(skin=SKIN_C, hair=(64, 48, 36, 255),  shirt=(222, 194, 84, 255), pants=DARK_PANTS, shoes=SHOE),
    "trader6":  dict(skin=SKIN_A, hair=(30, 30, 34, 255),  shirt=(104, 150, 222, 255),pants=DARK_PANTS, shoes=SHOE),
    # the barista -- apron green, never leaves the cafe
    "barista":  dict(skin=SKIN_B, hair=(58, 40, 28, 255),  shirt=(74, 122, 96, 255),  pants=(62, 58, 54, 255), shoes=SHOE),
    # Archive Studio staff -- plum/rose range, matching the studio accent so
    # they read as belonging to that building rather than the trading floor
    "archivist": dict(skin=SKIN_C, hair=(48, 36, 44, 255), shirt=(168, 87, 127, 255), pants=(62, 54, 66, 255), shoes=SHOE),
    "writer":    dict(skin=SKIN_A, hair=(96, 62, 48, 255), shirt=(198, 140, 172, 255), pants=DARK_PANTS, shoes=SHOE),
    "editor":    dict(skin=SKIN_B, hair=(36, 32, 38, 255), shirt=(122, 84, 146, 255),  pants=DARK_PANTS, shoes=SHOE),
    # Fact-checker -- deeper wine/burgundy, distinct from writer's rose and
    # editor's violet but still clearly "Archive Studio plum family." Added
    # 2026-08-29: the writers' room was always built with two seats "because
    # scripts get a fact-check pass" (see hq-map.js's STUDIO layout comment)
    # but the second seat never had anyone sitting in it until now.
    "factchecker": dict(skin=SKIN_C, hair=(58, 30, 32, 255), shirt=(150, 58, 74, 255), pants=DARK_PANTS, shoes=SHOE),
    # Sage -- the owner, player-controlled. Gold reads as "not one of the
    # staff" against every other palette above (blues, oranges, plums).
    "sage":      dict(skin=SKIN_A, hair=(56, 40, 30, 255),  shirt=(212, 168, 46, 255), pants=DARK_PANTS, shoes=SHOE),
    # Sage's ATM Co. -- one role for now: scouting real locations and
    # working the real launch checklist. Green/gold reads as "money", matches
    # ATM_CO.accent, distinct from every other palette above.
    "atmops":    dict(skin=SKIN_C, hair=(50, 40, 30, 255),  shirt=(47, 122, 82, 255),  pants=DARK_PANTS, shoes=SHOE),
    # Smallville General -- pale scrub blue and a white coat read as
    # "hospital" against every other palette above, and distinguish the two
    # from each other the same way the trading floor's desks do.
    "doctor1":   dict(skin=SKIN_A, hair=(30, 26, 24, 255),  shirt=(120, 168, 196, 255), pants=DARK_PANTS, shoes=SHOE),
    "doctor2":   dict(skin=SKIN_B, hair=(84, 60, 40, 255),  shirt=(226, 228, 224, 255), pants=(74, 78, 92, 255), shoes=SHOE),
    # The News Desk -- Bull & Bear, in the flesh. Same generic body as every
    # other character (see silhouette_outline/char_frame -- nobody gets bespoke
    # geometry, personality is colour + behaviour + dialogue, not a unique
    # sprite shape). Shirt colours echo their popup-bulletin palette
    # (ui/newsbulletin.js's FACE_INNER): navy blazer for Bull, forest green
    # for Bear, so the two versions of each character read as the same person.
    "bull":      dict(skin=SKIN_A, hair=(58, 42, 32, 255),  shirt=(43, 53, 80, 255),   pants=DARK_PANTS, shoes=SHOE),
    "bear":      dict(skin=SKIN_C, hair=(38, 34, 30, 255),  shirt=(31, 92, 51, 255),   pants=DARK_PANTS, shoes=SHOE),
    # The Field Office -- Voss & Ito. Ambient security duo, same generic body,
    # dark slate/charcoal and maroon suits reading as "plainclothes" against
    # every brighter palette above. See hq-map.js's FIELD_OFFICE comment --
    # purely decoration, no real intrusion-detection system behind them.
    "voss":      dict(skin=SKIN_B, hair=(40, 38, 40, 255),  shirt=(54, 60, 70, 255),   pants=DARK_PANTS, shoes=SHOE),
    "ito":       dict(skin=SKIN_C, hair=(28, 26, 26, 255),  shirt=(72, 52, 48, 255),   pants=DARK_PANTS, shoes=SHOE),
    # The Bank -- Marnie. Brass/gold reads as "the money building" against
    # every other palette above (nothing else here is this warm a tone).
    "marnie":    dict(skin=SKIN_A, hair=(78, 54, 36, 255),  shirt=(168, 132, 58, 255), pants=DARK_PANTS, shoes=SHOE),
    # The Tax Office -- Percy. Olive/khaki reads as "records office" against
    # the Bank's brass and everything else here.
    "percy":     dict(skin=SKIN_B, hair=(60, 56, 52, 255),  shirt=(96, 104, 64, 255),  pants=DARK_PANTS, shoes=SHOE),
    # The Crypto Desk -- Nix. Bitcoin orange, deliberately the loudest shirt in
    # the building: this is the only desk that trades 24/7 while everyone else
    # is asleep, and it should be obvious at a glance which one it is. Distinct
    # from the mechanic's rust-orange (196,96,56) -- brighter and more saturated.
    "crypto":    dict(skin=SKIN_C, hair=(34, 30, 32, 255),  shirt=(242, 148, 38, 255), pants=DARK_PANTS, shoes=SHOE),
    # The Prediction Desk -- Fay. Violet reads as "odds/forecasting" and is
    # the one hue nothing else in this palette uses (closest neighbours are
    # the Archive Studio's plum family and the Field Office's slate -- this
    # sits clearly apart from both).
    "predict":   dict(skin=SKIN_B, hair=(44, 38, 48, 255),  shirt=(108, 74, 168, 255), pants=DARK_PANTS, shoes=SHOE),
    # Ambient townsfolk -- no real subsystem behind any of these three, same
    # as the doctors and Bull & Bear. Added purely so the park and streets
    # have people in them. Warm, everyday colours -- deliberately NOT in the
    # "money green / bank gold / crypto orange" family, so nobody mistakes
    # them for staff of a real room.
    "milo":      dict(skin=SKIN_A, hair=(32, 28, 26, 255),  shirt=(196, 90, 74, 255),  pants=(70, 90, 78, 255), shoes=SHOE),
    "nadia":     dict(skin=SKIN_C, hair=(54, 44, 60, 255),  shirt=(72, 150, 150, 255), pants=DARK_PANTS, shoes=SHOE),
    "reed":      dict(skin=SKIN_B, hair=(130, 100, 60, 255), shirt=(196, 164, 56, 255), pants=(74, 66, 58, 255), shoes=SHOE),
    # The Outskirts -- Theo, Greta. Ambient, same as Milo/Nadia/Reed, just
    # out past the hospital rather than downtown.
    "theo":      dict(skin=SKIN_A, hair=(60, 52, 48, 255),  shirt=(92, 118, 148, 255), pants=DARK_PANTS, shoes=SHOE),
    "greta":     dict(skin=SKIN_C, hair=(150, 140, 60, 255), shirt=(100, 138, 132, 255), pants=(70, 90, 78, 255), shoes=SHOE),
    # Generic filler palettes -- the 40-house Eastside expansion reuses these
    # 10 across its residents (4 each). Pure crowd variety, same as a real
    # neighbourhood having repeat shirt colours; nothing here is meant to be
    # a distinct, bespoke character the way the named cast is.
    "filler1": dict(skin=SKIN_A, hair=(70, 54, 40, 255), shirt=(176, 120, 96, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler2": dict(skin=SKIN_B, hair=(40, 36, 34, 255), shirt=(96, 140, 176, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler3": dict(skin=SKIN_C, hair=(130, 96, 60, 255), shirt=(168, 168, 96, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler4": dict(skin=SKIN_A, hair=(30, 28, 26, 255), shirt=(140, 96, 160, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler5": dict(skin=SKIN_B, hair=(150, 110, 60, 255), shirt=(96, 160, 128, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler6": dict(skin=SKIN_C, hair=(54, 44, 40, 255), shirt=(200, 140, 100, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler7": dict(skin=SKIN_A, hair=(90, 70, 50, 255), shirt=(120, 120, 180, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler8": dict(skin=SKIN_B, hair=(36, 32, 30, 255), shirt=(180, 100, 110, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler9": dict(skin=SKIN_C, hair=(110, 90, 56, 255), shirt=(110, 150, 100, 255), pants=DARK_PANTS, shoes=SHOE),
    "filler10": dict(skin=SKIN_A, hair=(60, 48, 40, 255), shirt=(150, 150, 150, 255), pants=DARK_PANTS, shoes=SHOE),
    # Smallville Regional -- Dana, the gate agent. Navy with gold trim reads
    # as "airline uniform" against every other palette here.
    "dana": dict(skin=SKIN_B, hair=(46, 40, 36, 255), shirt=(42, 58, 92, 255), pants=(32, 40, 64, 255), shoes=SHOE),
}


def build_characters():
    made = []
    for cid, pal in CHARACTERS.items():
        made.append(save(char_sheet(pal), f"char_{cid}"))
    return made


# ============================================================
#  Sage's two dogs -- same sheet shape (3 cols x 4 rows, CW x CH)
#  so they drop straight into AgentSprite/DIR unchanged, but a much
#  lower, horizontal silhouette so they read as animals, not short
#  people. A simple bob (whole body shifts up 1px) stands in for a
#  real per-leg gait -- legible at this pixel budget, and consistent
#  with how the human walk-cycle is a broad simplification too.
# ============================================================

def dog_frame(direction, step, pal):
    img = Image.new("RGBA", (CW, CH), (0, 0, 0, 0))
    coat, coat_d = pal["coat"], shade_of(pal["coat"], .7)
    ear = pal["ear"]
    side = direction in ("left", "right")
    back = direction == "up"
    bob = -1 if step != 0 else 0
    by0, by1 = 16 + bob, 20 + bob   # body band

    if side:
        facing_right = direction == "right"
        rect(img, 2, by0, 13, by1, coat)
        rect(img, 2, by0, 13, by0 + 1, light_of(coat))       # spine highlight
        if facing_right:
            rect(img, 10, by0 - 4, 14, by0 + 1, coat)        # head
            rect(img, 12, by0 - 6, 14, by0 - 3, ear)         # ear
            rect(img, 1, by0 - 2, 2, by0 + 1, coat_d)        # tail
        else:
            rect(img, 1, by0 - 4, 5, by0 + 1, coat)
            rect(img, 1, by0 - 6, 3, by0 - 3, ear)
            rect(img, 13, by0 - 2, 14, by0 + 1, coat_d)
        loff = 0 if step == 0 else (2 if step == 1 else 0)
        rect(img, 4, by1, 5, 23, coat_d)
        rect(img, 10, by1, 11, 23 - loff, coat_d)
    else:
        rect(img, 4, by0, 11, by1, coat)
        rect(img, 4, by0, 11, by0 + 1, light_of(coat))
        rect(img, 5, by0 - 4, 10, by0 + 1, coat)             # head, facing camera
        rect(img, 4, by0 - 6, 6, by0 - 3, ear)
        rect(img, 9, by0 - 6, 11, by0 - 3, ear)
        if not back:
            px(img, 6, by0 - 2, INK)
            px(img, 9, by0 - 2, INK)
        rect(img, 5, by1, 6, 23, coat_d)
        rect(img, 9, by1, 10, 23, coat_d)

    return silhouette_outline(img)


def dog_sheet(pal):
    sheet = Image.new("RGBA", (CW * 3, CH * 4), (0, 0, 0, 0))
    for r, d in enumerate(DIRS):
        for c in range(3):
            sheet.paste(dog_frame(d, c, pal), (c * CW, r * CH))
    return sheet


DOGS = {
    "dog1": dict(coat=(196, 148, 96, 255), ear=(120, 82, 52, 255)),   # tan
    "dog2": dict(coat=(70, 62, 58, 255),   ear=(40, 34, 32, 255)),    # dark brindle
    # Pets bought from the General Store (see sim_economy.py's catalogue).
    # Same low-quadruped sheet as Sage's two -- a cat at this pixel budget
    # reads as "small four-legged animal, not a dog" mostly through colour
    # and the paler ear, which is as far as 16x24 will honestly carry it.
    "pet_dog": dict(coat=(148, 112, 74, 255), ear=(96, 68, 44, 255)),
    "pet_cat": dict(coat=(122, 122, 130, 255), ear=(214, 176, 182, 255)),
}


def build_dogs():
    made = []
    for did, pal in DOGS.items():
        made.append(save(dog_sheet(pal), f"char_{did}"))
    return made


# ============================================================
#  OUTDOOR -- the city around the HQ
#  Same visual language as the interior: flat colour, top-left light,
#  hard silhouette outline, 16px tile grid.
# ============================================================

def build_outdoor():
    made = []
    T = TILE

    # ---- asphalt (seamless) ---------------------------------------------
    a = tile((58, 58, 64, 255))
    for (x, y) in [(2, 3), (9, 6), (5, 11), (13, 8), (1, 14)]:
        px(a, x, y, (48, 48, 54, 255))
    for (x, y) in [(6, 2), (12, 12), (3, 8)]:
        px(a, x, y, (70, 70, 77, 255))
    made.append(save(a, "asphalt"))

    # ---- water (seamless) ------------------------------------------------
    w = tile((78, 150, 196, 255))
    rect(w, 0, 3, T, 5, (104, 176, 216, 255))
    rect(w, 0, 10, T, 12, (104, 176, 216, 255))
    made.append(save(w, "water"))

    # ---- tree, 3x3 -------------------------------------------------------
    tr = Image.new("RGBA", (3 * T, 3 * T), (0, 0, 0, 0))
    cx = cy = 3 * T // 2
    canopy = (62, 128, 66, 255)
    circle(tr, cx, cy, 21, canopy)
    for yy in range(3 * T):                                  # shade lower-right
        for xx in range(3 * T):
            if tr.getpixel((xx, yy))[3] and (xx - cx) + (yy - cy) > 14:
                px(tr, xx, yy, shade_of(canopy, .78))
    circle(tr, cx - 6, cy - 7, 8, light_of(canopy, 1.14))    # highlight
    for (bx, by) in [(cx - 14, cy + 2), (cx + 10, cy - 6), (cx + 4, cy + 13)]:
        circle(tr, bx, by, 6, canopy)
    tr = silhouette_outline(tr)
    made.append(save(tr, "tree_big"))

    # ---- outdoor bench 2x1 ----------------------------------------------
    bn = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    wood = (150, 106, 64, 255)
    rect(bn, 1, 3, 2 * T - 1, 10, wood)
    rect(bn, 1, 3, 2 * T - 1, 5, light_of(wood))
    for x in range(3, 2 * T - 2, 5):
        rect(bn, x, 3, x + 1, 10, shade_of(wood, .8))
    rect(bn, 3, 10, 6, 13, (86, 66, 46, 255))
    rect(bn, 2 * T - 6, 10, 2 * T - 3, 13, (86, 66, 46, 255))
    made.append(save(silhouette_outline(bn), "bench_out"))

    # ---- flowers 1x1 -----------------------------------------------------
    for name, col in [("flower_a", (222, 96, 118, 255)), ("flower_b", (232, 190, 84, 255))]:
        f = Image.new("RGBA", (T, T), (0, 0, 0, 0))
        for (x, y) in [(4, 6), (10, 4), (7, 10), (12, 11)]:
            px(f, x, y, col); px(f, x + 1, y, col)
            px(f, x, y + 1, col); px(f, x + 1, y + 1, col)
            px(f, x, y, light_of(col))
        made.append(save(f, name))

    # ---- houses: one per watchlist symbol -------------------------------
    # 8x7 tiles. Roof colour is the only difference so the row still reads
    # as one neighbourhood.
    HOUSE_ROOFS = [
        (196, 104, 84, 255), (96, 154, 176, 255), (176, 116, 168, 255),
        (150, 172, 92, 255), (140, 122, 190, 255), (206, 170, 92, 255),
        (110, 150, 200, 255),
    ]
    HW, HH = 8 * T, 7 * T
    for i, roof in enumerate(HOUSE_ROOFS):
        h = Image.new("RGBA", (HW, HH), (0, 0, 0, 0))
        rshade, rlight = shade_of(roof, .76), light_of(roof, 1.14)
        # roof body with a ridge running left-right
        rect(h, 2, 6, HW - 2, HH - 6, roof)
        rect(h, 2, 6, HW - 2, 12, rlight)                 # sunlit upper slope
        rect(h, 2, HH - 20, HW - 2, HH - 6, rshade)       # shaded lower slope
        rect(h, 2, HH // 2 - 2, HW - 2, HH // 2 + 1, shade_of(roof, .62))  # ridge
        # shingle courses
        for y in range(14, HH - 8, 6):
            rect(h, 4, y, HW - 4, y + 1, shade_of(roof, .86))
        # chimney
        rect(h, HW - 30, 0, HW - 18, 14, (128, 108, 100, 255))
        rect(h, HW - 30, 0, HW - 18, 4, (150, 130, 120, 255))
        # doorstep on the NORTH face -- the homes front onto the street that
        # runs between them and the HQ, so the door has to face up
        rect(h, HW // 2 - 10, 0, HW // 2 + 10, 7, (222, 206, 170, 255))
        made.append(save(silhouette_outline(h), f"house_{i}"))

    # ---- money billboard, 3x3 --------------------------------------------
    # A roadside sign, not a building -- two posts holding up a board with a
    # gold coin on it. Purely a "look here" marker; the real numbers are
    # rendered live in the click panel, same as every other screen.
    bw, bh = 3 * T, 3 * T
    bb = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    post = (90, 78, 66, 255)
    board = (250, 244, 224, 255)
    frame_c = (60, 44, 30, 255)
    rect(bb, 6, 26, 10, bh, post)
    rect(bb, bw - 10, 26, bw - 6, bh, post)
    rect(bb, 2, 4, bw - 2, 30, frame_c)
    rect(bb, 4, 6, bw - 4, 28, board)
    rect(bb, 4, 6, bw - 4, 10, light_of(board))
    gold, gold_d = (224, 178, 64, 255), shade_of((224, 178, 64, 255), .8)
    cx, cy = bw // 2, 17
    circle(bb, cx, cy, 9, gold_d)
    circle(bb, cx, cy, 8, gold)
    circle(bb, cx - 2, cy - 2, 3, light_of(gold, 1.2))
    rect(bb, cx - 1, cy - 3, cx + 1, cy + 4, gold_d)
    made.append(save(silhouette_outline(bb), "billboard"))

    # ---- streetlamp, 1x3 ---------------------------------------------------
    # Night.js already lights these positions after dark (a warm glow +
    # a tiny 2x5 fitting) but draws nothing for them in daylight, so the
    # streets look bare until the sun goes down. This is the daytime post
    # that stands where those lights already are -- same coordinates,
    # drawn once as a static sprite instead of only appearing after dark.
    lw, lh = TILE, 3 * TILE
    lamp = Image.new("RGBA", (lw, lh), (0, 0, 0, 0))
    pole = (58, 54, 50, 255)
    pole_l = light_of(pole, 1.3)
    base = (40, 38, 36, 255)
    glass = (250, 232, 180, 255)
    cx = lw // 2
    rect(lamp, cx - 2, lh - 10, cx + 2, lh - 2, base)          # base
    rect(lamp, cx - 1, 6, cx + 1, lh - 8, pole)                # pole shaft
    rect(lamp, cx - 1, 6, cx, lh - 8, pole_l)                  # highlight edge
    rect(lamp, cx - 4, 0, cx + 4, 8, base)                     # lamp housing
    rect(lamp, cx - 3, 1, cx + 3, 6, glass)                    # glass
    rect(lamp, cx - 2, 2, cx, 4, light_of(glass, 1.15))
    made.append(save(silhouette_outline(lamp), "streetlamp"))

    return made


def build_home_interiors():
    """Furniture that only appears inside the houses."""
    made = []
    T = TILE

    # ---- bed 2x3 ---------------------------------------------------------
    bed = Image.new("RGBA", (2 * T, 3 * T), (0, 0, 0, 0))
    frame = (150, 106, 64, 255)
    sheet = (238, 234, 224, 255)
    quilt = (108, 142, 190, 255)
    rect(bed, 0, 0, 2 * T, 3 * T, frame)
    rect(bed, 2, 2, 2 * T - 2, 3 * T - 2, sheet)           # mattress
    rect(bed, 2, 2, 2 * T - 2, 10, (250, 248, 242, 255))   # pillow
    rect(bed, 3, 3, 2 * T - 3, 9, (226, 224, 216, 255))
    rect(bed, 2, 14, 2 * T - 2, 3 * T - 2, quilt)          # quilt
    rect(bed, 2, 14, 2 * T - 2, 16, light_of(quilt))
    for y in range(19, 3 * T - 4, 5):                       # quilt stitching
        rect(bed, 4, y, 2 * T - 4, y + 1, shade_of(quilt, .86))
    made.append(save(silhouette_outline(bed), "bed"))

    # ---- television 2x1 --------------------------------------------------
    tv = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    rect(tv, 2, 2, 2 * T - 2, T - 3, (42, 44, 52, 255))
    rect(tv, 4, 4, 2 * T - 4, T - 6, (96, 150, 170, 255))   # screen glow
    rect(tv, 5, 5, 2 * T - 8, 8, (140, 196, 210, 255))
    rect(tv, T - 4, T - 3, T + 4, T - 1, (60, 62, 70, 255)) # stand
    made.append(save(silhouette_outline(tv), "tv"))

    # ---- kitchen unit 2x1 ------------------------------------------------
    kt = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    top = (206, 200, 186, 255)
    rect(kt, 0, 0, 2 * T, T, top)
    rect(kt, 0, 0, 2 * T, 3, light_of(top))
    rect(kt, 4, 5, 14, T - 3, (140, 146, 156, 255))         # sink
    rect(kt, 2 * T - 12, 5, 2 * T - 4, T - 3, (92, 96, 104, 255))  # hob
    made.append(save(silhouette_outline(kt), "kitchen"))

    # ---- small dining table 2x2 -----------------------------------------
    dt = Image.new("RGBA", (2 * T, 2 * T), (0, 0, 0, 0))
    wood = (176, 124, 74, 255)
    rect(dt, 1, 1, 2 * T - 1, 2 * T - 1, wood)
    rect(dt, 1, 1, 2 * T - 1, 4, light_of(wood))
    rect(dt, 4, 5, 2 * T - 4, 2 * T - 4, shade_of(wood, .9))
    made.append(save(silhouette_outline(dt), "table_small"))

    return made


def build_cafe():
    """Fittings that make the coffee shop read as a coffee shop."""
    made = []
    T = TILE
    WOOD_BAR = (128, 84, 50, 255)

    # ---- barista bar 6x1 -------------------------------------------------
    bar = Image.new("RGBA", (6 * T, T), (0, 0, 0, 0))
    rect(bar, 0, 0, 6 * T, T, WOOD_BAR)
    rect(bar, 0, 0, 6 * T, 4, light_of(WOOD_BAR, 1.22))      # polished top
    rect(bar, 0, T - 4, 6 * T, T, shade_of(WOOD_BAR, .7))
    for x in range(6, 6 * T, 14):                             # plank joints
        rect(bar, x, 4, x + 1, T - 4, shade_of(WOOD_BAR, .84))
    made.append(save(silhouette_outline(bar), "cafe_bar"))

    # ---- espresso machine 2x1 -------------------------------------------
    esp = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    chrome = (196, 200, 208, 255)
    rect(esp, 1, 2, 2 * T - 1, T - 1, chrome)
    rect(esp, 1, 2, 2 * T - 1, 5, light_of(chrome, 1.1))
    rect(esp, 3, 6, 11, T - 3, (60, 64, 72, 255))             # group head
    rect(esp, 2 * T - 12, 6, 2 * T - 4, T - 3, (60, 64, 72, 255))
    px(esp, 6, 4, (224, 88, 70, 255)); px(esp, 8, 4, (110, 200, 140, 255))
    made.append(save(silhouette_outline(esp), "espresso"))

    # ---- pastry case 2x1 -------------------------------------------------
    pas = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    glass = (206, 226, 232, 255)
    rect(pas, 1, 2, 2 * T - 1, T - 1, glass)
    rect(pas, 1, 2, 2 * T - 1, 4, (232, 244, 248, 255))
    for i, col in enumerate([(214, 158, 88, 255), (196, 122, 74, 255), (226, 186, 118, 255)]):
        x = 4 + i * 8
        rect(pas, x, 7, x + 6, T - 3, col)
    made.append(save(silhouette_outline(pas), "pastry"))

    # ---- menu board 3x1 --------------------------------------------------
    mb = Image.new("RGBA", (3 * T, T), (0, 0, 0, 0))
    rect(mb, 0, 0, 3 * T, T, (54, 48, 42, 255))
    rect(mb, 2, 2, 3 * T - 2, T - 2, (38, 40, 38, 255))
    for i, (x, w_) in enumerate([(5, 22), (5, 16), (30, 18), (5, 12), (30, 10)]):
        y = 4 + (i % 3) * 3
        rect(mb, x, y, x + w_, y + 1, (226, 220, 196, 255))
    made.append(save(silhouette_outline(mb), "menu"))

    # ---- bar stool 1x1 ---------------------------------------------------
    st = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    seat = (150, 96, 62, 255)
    circle(st, T // 2, T // 2, 5, seat)
    circle(st, T // 2 - 1, T // 2 - 2, 3, light_of(seat, 1.15))
    made.append(save(silhouette_outline(st), "stool"))

    # ---- round cafe table 2x2 -------------------------------------------
    rt = Image.new("RGBA", (2 * T, 2 * T), (0, 0, 0, 0))
    top = (168, 118, 74, 255)
    circle(rt, T, T, 13, top)
    circle(rt, T - 3, T - 4, 7, light_of(top, 1.12))
    made.append(save(silhouette_outline(rt), "cafe_table"))

    # ---- complaint bulletin board 3x2 -----------------------------------
    bb = Image.new("RGBA", (3 * T, 2 * T), (0, 0, 0, 0))
    cork = (176, 132, 84, 255)
    rect(bb, 0, 0, 3 * T, 2 * T, (96, 66, 40, 255))          # frame
    rect(bb, 3, 3, 3 * T - 3, 2 * T - 3, cork)
    rect(bb, 3, 3, 3 * T - 3, 6, light_of(cork, 1.1))
    # pinned notes
    notes = [(6, 7, 12, 9), (21, 8, 11, 8), (34, 6, 10, 10),
             (8, 19, 13, 8), (25, 20, 14, 7)]
    for i, (x, y, w_, h_) in enumerate(notes):
        col = [(238, 234, 218, 255), (232, 214, 156, 255), (226, 190, 178, 255)][i % 3]
        rect(bb, x, y, x + w_, y + h_, col)
        rect(bb, x + 2, y + 2, x + w_ - 2, y + 3, (150, 146, 134, 255))
        rect(bb, x + 2, y + 4, x + w_ - 4, y + 5, (170, 166, 154, 255))
        px(bb, x + w_ // 2, y, (196, 62, 48, 255))           # pin
    made.append(save(silhouette_outline(bb), "bulletin"))

    # ---- bicycle, seen from above 2x1 -----------------------------------
    # Bought from the General Store (sim_economy.py). Read from above a
    # bike is mostly two wheels and a bar between them, so that is what
    # this draws rather than pretending to a side-on silhouette.
    bike = Image.new("RGBA", (2 * T, T), (0, 0, 0, 0))
    W, H = 2 * T, T
    tyre = (38, 36, 40, 255)
    frame_c = (196, 74, 62, 255)
    circle(bike, 7, H // 2, 5, tyre)                     # rear wheel
    circle(bike, 7, H // 2, 2, (150, 150, 156, 255))     # hub
    circle(bike, W - 8, H // 2, 5, tyre)                 # front wheel
    circle(bike, W - 8, H // 2, 2, (150, 150, 156, 255))
    rect(bike, 8, H // 2 - 1, W - 9, H // 2 + 1, frame_c)  # crossbar
    rect(bike, 12, H // 2 - 3, 14, H // 2 + 3, (60, 58, 62, 255))  # saddle
    rect(bike, W - 11, H // 2 - 4, W - 9, H // 2 + 4, (60, 58, 62, 255))  # bars
    made.append(save(silhouette_outline(bike), "bicycle"))

    # ---- cars, seen from above 4x2 --------------------------------------
    for name, paint in [("car_red", (198, 62, 54, 255)),
                        ("car_blue", (58, 104, 178, 255)),
                        ("car_yellow", (226, 182, 56, 255)),
                        ("car_green", (86, 140, 74, 255)),      # Otis's own car
                        ("car_purple", (124, 106, 148, 255))]:  # Margo's own car

        car = Image.new("RGBA", (4 * T, 2 * T), (0, 0, 0, 0))
        W, H = 4 * T, 2 * T
        tyre = (36, 34, 38, 255)
        rect(car, 8, 1, 20, 4, tyre)                     # wheels poking out
        rect(car, 40, 1, 52, 4, tyre)
        rect(car, 8, H - 4, 20, H - 1, tyre)
        rect(car, 40, H - 4, 52, H - 1, tyre)
        rect(car, 3, 4, W - 3, H - 4, paint)             # body
        rect(car, 3, 4, W - 3, 7, light_of(paint, 1.15)) # sunlit top edge
        rect(car, 3, H - 7, W - 3, H - 4, shade_of(paint, .78))
        glass = (150, 196, 216, 255)
        rect(car, 12, 7, 26, H - 7, glass)               # windscreen
        rect(car, 34, 7, 48, H - 7, shade_of(glass, .88))# rear window
        rect(car, 27, 7, 33, H - 7, shade_of(paint, .86))# roof spine
        rect(car, W - 5, 8, W - 3, 12, (255, 236, 170, 255))   # headlights
        rect(car, W - 5, H - 12, W - 3, H - 8, (255, 236, 170, 255))
        rect(car, 3, 9, 5, 12, (210, 70, 60, 255))       # tail lights
        rect(car, 3, H - 12, 5, H - 9, (210, 70, 60, 255))
        made.append(save(silhouette_outline(car), name))

    # ---- ambulance 4x2 ---------------------------------------------------
    amb = Image.new("RGBA", (4 * T, 2 * T), (0, 0, 0, 0))
    W, H = 4 * T, 2 * T
    body_c = (238, 238, 234, 255)
    tyre = (36, 34, 38, 255)
    rect(amb, 8, 1, 20, 4, tyre); rect(amb, 40, 1, 52, 4, tyre)
    rect(amb, 8, H - 4, 20, H - 1, tyre); rect(amb, 40, H - 4, 52, H - 1, tyre)
    rect(amb, 2, 3, W - 3, H - 3, body_c)                  # boxy van body
    rect(amb, 2, 3, W - 3, 6, (252, 252, 250, 255))
    rect(amb, 2, H - 6, W - 3, H - 3, (208, 208, 202, 255))
    rect(amb, 2, 12, W - 3, 16, (214, 62, 52, 255))        # red stripe
    glass = (150, 196, 216, 255)
    rect(amb, W - 16, 6, W - 4, H - 6, glass)              # cab window
    # red cross on the flank
    rect(amb, 18, 9, 30, 13, (214, 62, 52, 255))
    rect(amb, 22, 5, 26, 17, (214, 62, 52, 255))
    rect(amb, 6, 0, 12, 3, (232, 70, 60, 255))             # roof lights
    rect(amb, 14, 0, 20, 3, (110, 150, 232, 255))
    made.append(save(silhouette_outline(amb), "ambulance"))

    # ---- the one plane, seen from above, 8x3 ------------------------------
    # Pure ambient scenery for Smallville Regional, same drawing style as
    # every car above -- rects and a circle, nothing traced or copied.
    plane = Image.new("RGBA", (8 * T, 3 * T), (0, 0, 0, 0))
    W, H = 8 * T, 3 * T
    cy = H // 2
    body_c = (232, 234, 230, 255)
    stripe_c = (58, 104, 178, 255)
    engine_c = (54, 52, 56, 255)
    glass = (140, 190, 214, 255)
    # main wings, roughly a third back from the nose (nose is at the right,
    # matching the cars' own headlights-on-the-right convention)
    rect(plane, 40, 2, 62, H - 2, shade_of(body_c, .9))
    rect(plane, 40, 2, 62, 6, light_of(body_c, 1.1))
    # tailplane, near the back
    rect(plane, W - 28, cy - 9, W - 16, cy + 9, shade_of(body_c, .88))
    # fuselage, drawn over the wings so it reads as sitting on top of them
    rect(plane, 8, cy - 5, W - 6, cy + 5, body_c)
    rect(plane, 8, cy - 5, W - 6, cy - 2, light_of(body_c, 1.12))
    rect(plane, 8, cy + 2, W - 6, cy + 5, shade_of(body_c, .82))
    circle(plane, W - 8, cy, 6, body_c)                      # rounded nose
    rect(plane, W - 18, cy - 3, W - 12, cy + 3, glass)        # cockpit
    for wx in range(16, W - 24, 9):                          # cabin windows
        circle(plane, wx, cy - 1, 1, glass)
    rect(plane, 6, cy - 2, 13, cy + 2, stripe_c)              # tail stripe
    rect(plane, 46, cy - 9, 54, cy - 5, engine_c)             # engines
    rect(plane, 46, cy + 5, 54, cy + 9, engine_c)
    made.append(save(silhouette_outline(plane), "plane"))

    # ---- luggage, a small stacked-suitcase prop, 1x1 ----------------------
    # The one airport-specific prop nothing else in the city has.
    lug = Image.new("RGBA", (T, T), (0, 0, 0, 0))
    case1 = (150, 108, 64, 255)
    case2 = (70, 92, 140, 255)
    rect(lug, 1, 7, T - 1, T - 1, case1)
    rect(lug, 1, 7, T - 1, 9, light_of(case1))
    outline_box(lug, 1, 7, T - 1, T - 1, cut=0)
    rect(lug, 3, 2, T - 4, 8, case2)
    rect(lug, 3, 2, T - 4, 4, light_of(case2))
    outline_box(lug, 3, 2, T - 4, 8, cut=0)
    rect(lug, T // 2 - 3, 0, T // 2 + 3, 2, (40, 38, 42, 255))
    made.append(save(lug, "luggage"))

    return made


if __name__ == "__main__":
    names = build()
    names += build_home_interiors()
    names += build_cafe()
    names += build_furniture()
    names += build_characters()
    names += build_dogs()      # Sage's two, plus the store's pets
    names += build_outdoor()
    print(f"wrote {len(names)} sprites to {OUT}")
    for n in names:
        print("  ", n + ".png")
