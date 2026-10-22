"""Generate the built-in stamp shapes (addon/mecha_lab/shapes/builtin_shapes.json)
and their palette icons (addon/mecha_lab/icons/shape_*.png).

Step 1 (any Python):                              python3 make_shapes.py json
Step 2 (Python with Pillow):                    python3 make_shapes.py icons
"""
import json
import math
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
ADDON = ROOT / 'addon' / 'mecha_lab'
OUT_JSON = ADDON / 'shapes' / 'builtin_shapes.json'

# (stem, label) in palette order
SHAPES = [
    ('PENTAGON', 'Pentagon'),
    ('TRAPEZOID', 'Trapezoid'),
    ('PILLS3', 'Three Pills'),
    ('TRIANGLE', 'Triangle'),
    ('NOTCH_ROUND', 'Round Notch Box'),
    ('NOTCH_POLY', 'Polygon Notch Box'),
    ('SCALE_A', 'Scale A (wide)'),
    ('SCALE_B', 'Scale B (round)'),
    ('SCALE_C', 'Scale C (pear)'),
    ('SCALE_D', 'Scale D (box)'),
    ('SCALE_E', 'Scale E (cloud)'),
    ('SCALE_F', 'Scale F (heart)'),
    ('SCALE_G', 'Scale G (leaf)'),
]

# 0.24.20 scale outlines traced from the user's sketch (px, y down).  The FIRST point is the root (the green mark):
# Creature Plate Scale is thick there and lifts on the far side.
SCALE_SKETCH = {
    'SCALE_A': [(415, 440), (530, 425), (640, 395), (690, 415), (740, 480), (790, 590), (790, 635), (690, 635),
                (665, 625), (660, 645), (630, 655), (610, 685), (550, 688), (480, 715), (440, 728), (380, 728),
                (300, 735), (175, 710), (160, 680), (175, 675), (172, 560), (172, 475), (360, 463)],
    'SCALE_B': [(180, 960), (230, 930), (290, 925), (330, 960), (370, 1030), (380, 1080), (365, 1150), (365, 1210),
                (300, 1260), (260, 1280), (215, 1280), (160, 1250), (110, 1215), (130, 1210), (125, 1150), (95, 1080),
                (90, 1040), (130, 1000)],
    'SCALE_C': [(565, 1155), (640, 1110), (700, 1080), (750, 1080), (775, 1130), (775, 1185), (760, 1210), (750, 1300),
                (745, 1340), (700, 1390), (650, 1430), (560, 1430), (490, 1415), (440, 1360), (420, 1300), (425, 1270),
                (450, 1230), (470, 1185), (510, 1175)],
    # second sketch: the orange mark is the root
    'SCALE_D': [(468, 655), (520, 657), (555, 650), (568, 638), (565, 560), (560, 455), (520, 455), (480, 478),
                (455, 470), (440, 452), (420, 450), (390, 470), (360, 500), (340, 540), (330, 565), (305, 575),
                (310, 620), (320, 660), (380, 655), (430, 650)],
    'SCALE_E': [(368, 915), (420, 940), (470, 948), (520, 935), (555, 910), (565, 875), (545, 845), (510, 835),
                (495, 800), (485, 770), (460, 750), (435, 760), (425, 775), (410, 765), (395, 760), (370, 745),
                (355, 748), (340, 758), (310, 760), (270, 745), (240, 742), (180, 775), (140, 800), (135, 860),
                (175, 858), (250, 880), (320, 900)],
    'SCALE_F': [(757, 798), (770, 835), (790, 855), (848, 855), (848, 770), (840, 710), (820, 670), (800, 630),
                (770, 630), (740, 660), (700, 700), (660, 720), (650, 760), (660, 785), (705, 800), (740, 795)],
    'SCALE_G': [(418, 1355), (470, 1360), (520, 1340), (570, 1315), (598, 1300), (600, 1250), (605, 1180),
                (610, 1130), (580, 1130), (545, 1125), (530, 1100), (522, 1040), (515, 980), (500, 975), (470, 1010),
                (430, 1060), (405, 1075), (375, 1070), (355, 1050), (330, 1045), (315, 1070), (295, 1120),
                (280, 1170), (275, 1210), (280, 1265), (330, 1270), (365, 1285), (395, 1320)],
}


def regular(n, r, start=math.pi / 2):
    return [(r * math.cos(start + 2 * math.pi * i / n), r * math.sin(start + 2 * math.pi * i / n)) for i in range(n)]


def normalize(loops):
    """Centre on the bounding box, longest side = 1 (span -0.5 .. 0.5)."""
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    cx, cy = (min(xs) + max(xs)) / 2, (min(ys) + max(ys)) / 2
    ext = max(max(xs) - min(xs), max(ys) - min(ys))
    return [[[round((x - cx) / ext, 5), round((y - cy) / ext, 5)] for x, y in lp] for lp in loops]


def notch_round():
    w, h, r = 0.5, 0.35, 0.22
    pts = [(-w, -h), (w, -h), (w, h), (r, h)]
    n = 24
    for i in range(1, n):
        a = -math.pi * i / n          # 0 .. -180 deg: the bite goes down into the box
        pts.append((r * math.cos(a), h + r * math.sin(a)))
    pts += [(-r, h), (-w, h)]
    return [pts]


def notch_poly():
    w, h = 0.5, 0.35
    return [[(-w, -h), (w, -h), (w, h), (0.26, h), (0.13, 0.06), (-0.13, 0.06), (-0.26, h), (-w, h)]]


def capsule(cx, cy, tilt, half, rad, n=12):
    """Closed pill outline: axis tilted ``tilt`` from vertical (leans right)."""
    ax = (math.sin(tilt), math.cos(tilt))
    nx = (ax[1], -ax[0])                       # right-hand normal
    top = (cx + ax[0] * half, cy + ax[1] * half)
    bot = (cx - ax[0] * half, cy - ax[1] * half)
    a0 = math.atan2(nx[1], nx[0])
    pts = []
    for i in range(n + 1):                    # top cap: from right side over to left side
        a = a0 + math.pi * i / n
        pts.append((top[0] + rad * math.cos(a), top[1] + rad * math.sin(a)))
    for i in range(n + 1):                    # bottom cap: left side round to right side
        a = a0 + math.pi + math.pi * i / n
        pts.append((bot[0] + rad * math.cos(a), bot[1] + rad * math.sin(a)))
    return pts


def pills3():
    """Three slanted pills side by side (vent slots): three separate outlines."""
    tilt, half, rad = math.radians(30.0), 0.30, 0.10
    gap = (2 * rad + 0.07) / math.cos(tilt)     # 0.07 clear space between neighbours
    return [capsule((i - 1) * gap, 0.0, tilt, half, rad) for i in range(3)]


def build_json():
    data = {
        'PENTAGON': [regular(5, 0.5)],
        'TRAPEZOID': [[(-0.5, -0.32), (0.5, -0.32), (0.27, 0.32), (-0.27, 0.32)]],
        'PILLS3': pills3(),
        'TRIANGLE': [regular(3, 0.5)],
        'NOTCH_ROUND': notch_round(),
        'NOTCH_POLY': notch_poly(),
    }
    data.update({k: [[(x, -y) for x, y in v]] for k, v in SCALE_SKETCH.items()})
    out = {'schema': 1, 'shapes': [{'stem': s, 'name': n, 'loops': normalize(data[s])} for s, n in SHAPES]}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    print('wrote', OUT_JSON, [(s['stem'], sum(len(lp) for lp in s['loops'])) for s in out['shapes']])


def build_icons():
    from PIL import Image, ImageDraw
    S, OUT = 512, 128
    d = json.loads(OUT_JSON.read_text(encoding='utf-8'))
    for sh in d['shapes']:
        img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        dr.rounded_rectangle((8, 8, S - 8, S - 8), radius=72, fill=(38, 41, 48, 255))
        for lp in sh['loops']:
            pts = [(S / 2 + x * S * 0.78, S / 2 - y * S * 0.78) for x, y in lp]
            dr.polygon(pts, fill=(255, 158, 40, 110))
            dr.line(pts + [pts[0]], fill=(255, 158, 40, 255), width=18, joint='curve')
        path = ADDON / 'icons' / f'shape_{sh["stem"].lower()}.png'
        img.resize((OUT, OUT), Image.LANCZOS).save(path)
        print('icon', path.name)


if __name__ == '__main__':
    {'json': build_json, 'icons': build_icons}[sys.argv[1] if len(sys.argv) > 1 else 'json']()
