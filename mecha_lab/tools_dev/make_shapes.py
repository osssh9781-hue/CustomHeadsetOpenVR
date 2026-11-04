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

# 0.24.95 (user: "메카닉에 쓸 수 있는 스탬프도 50종 - 썸네일도 보이게 그치만 가볍게", "알파나 디테일용이 아니라 형태 잡기용이야")
# shapes that block out a part's form with Cut / Split / Press Cut: corner and edge cutters, panel / armour outlines,
# bold silhouettes - no holes, no fine detail.  Appended after the first 13 (their list places are kept).
MECH = [
    ('M_CORNER_CHAMFER', 'Corner Chamfer'), ('M_CORNER_CHAMFER30', 'Corner Chamfer 30'),
    ('M_CORNER_STEPS', 'Corner Steps'), ('M_CORNER_DOUBLE', 'Corner Double Chamfer'),
    ('M_CORNER_FILLET', 'Corner Fillet'),
    ('M_V_NOTCH', 'V Notch'), ('M_U_SLOT', 'U Slot'), ('M_SQUARE_NOTCH', 'Square Notch'),
    ('M_DOVETAIL', 'Dovetail'), ('M_WIDE_NOTCH', 'Wide Notch'), ('M_STEP_NOTCH', 'Step Notch'),
    ('M_SAW_EDGE', 'Saw Edge'), ('M_SCALLOP_EDGE', 'Scallop Edge'), ('M_CRENEL_EDGE', 'Crenel Edge'),
    ('M_WAVE_EDGE', 'Wave Edge'),
    ('M_CHAMFER_PANEL', 'Chamfer Panel'), ('M_TWO_CORNER_PANEL', 'Two-Corner Panel'),
    ('M_ROUND_PANEL', 'Round Panel'), ('M_LONG_HEX', 'Long Hex'), ('M_OCTAGON', 'Octagon'),
    ('M_DIAMOND', 'Diamond'), ('M_KITE', 'Kite'), ('M_TALL_TRAPEZOID', 'Tall Trapezoid'),
    ('M_PARALLELOGRAM', 'Parallelogram'), ('M_ARROWHEAD', 'Arrowhead'), ('M_CHEVRON', 'Chevron'),
    ('M_WEDGE', 'Wedge'), ('M_SHIELD', 'Shield'), ('M_SHOULDER', 'Shoulder Pad'), ('M_KNEE', 'Knee Plate'),
    ('M_VISOR', 'Visor Slit'), ('M_CHEST', 'Chest Plate'), ('M_BLADE', 'Blade'), ('M_FIN', 'Fin'),
    ('M_TAPER_BAR', 'Taper Bar'), ('M_CRESCENT', 'Crescent'), ('M_HALF_DISC', 'Half Disc'),
    ('M_QUARTER_DISC', 'Quarter Disc'), ('M_ARC_BAND', 'Arc Band'), ('M_L_BLOCK', 'L Block'),
    ('M_T_BLOCK', 'T Block'), ('M_CROSS', 'Cross'), ('M_Z_STEP', 'Z Step'), ('M_STEP_PYRAMID', 'Step Pyramid'),
    ('M_Y_FORK', 'Y Fork'), ('M_SLASH_BAND', 'Slash Band'), ('M_THREE_PRONGS', 'Three Prongs'),
    ('M_HOOK', 'Hook'), ('M_ANGLE_CUTOFF', 'Angle Cutoff'), ('M_ARCH', 'Arch'),
]
SHAPES = SHAPES + MECH

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


def arc(cx, cy, r, a0, a1, n=12, ry=None):
    """Points on a circle (ellipse with ``ry``) from angle a0 to a1 (degrees), both ends included."""
    ry = r if ry is None else ry
    return [(cx + r * math.cos(math.radians(a0 + (a1 - a0) * i / n)),
             cy + ry * math.sin(math.radians(a0 + (a1 - a0) * i / n))) for i in range(n + 1)]


def round_rect(w, h, r, n=5):
    pts = []
    for cx, cy, a0 in ((w - r, -h + r, -90), (w - r, h - r, 0), (-w + r, h - r, 90), (-w + r, -h + r, 180)):
        pts += arc(cx, cy, r, a0, a0 + 90, n)
    return pts


def chamfer_rect(w, h, c):
    return [(-w + c, -h), (w - c, -h), (w, -h + c), (w, h - c), (w - c, h), (-w + c, h), (-w, h - c), (-w, -h + c)]


def crescent():
    a = 50.0
    p1 = (0.5 * math.cos(math.radians(a)), 0.5 * math.sin(math.radians(a)))
    apex = -0.2
    cx = (p1[0] ** 2 + p1[1] ** 2 - apex ** 2) / (2 * (p1[0] - apex))
    r = cx - apex
    t = math.degrees(math.atan2(p1[1], p1[0] - cx))
    outer = arc(0, 0, 0.5, a, 360 - a, 24)
    inner = arc(cx, cy := 0.0, r, -t, -360 + t, 24)[1:-1]
    return outer + inner


def mech_shapes():
    """The 50 form-blocking shapes (any size: normalized afterwards)."""
    wave = [(-0.6, 0.3), (0.6, 0.3)] + [(0.6 - 1.2 * i / 24, -0.15 * math.sin(math.pi * 3 * i / 24)) for i in range(25)]
    scallop = [(-0.6, 0.3), (0.6, 0.3), (0.6, 0.0)]
    for c in (0.4, 0.0, -0.4):
        scallop += arc(c, 0.0, 0.2, 0, -180, 10)[1:]
    return {
        'M_CORNER_CHAMFER': [(0, 0), (1, 0), (0, 1)],
        'M_CORNER_CHAMFER30': [(0, 0), (1, 0), (0, 0.577)],
        'M_CORNER_STEPS': [(0, 0), (1, 0), (1, 0.33), (0.67, 0.33), (0.67, 0.67), (0.33, 0.67), (0.33, 1), (0, 1)],
        'M_CORNER_DOUBLE': [(0, 0), (1, 0), (0.85, 0.5), (0.5, 0.85), (0, 1)],
        'M_CORNER_FILLET': [(0, 0)] + arc(1, 1, 1, 270, 180, 16),
        'M_V_NOTCH': [(-0.5, 0.5), (0, -0.4), (0.5, 0.5)][::-1],
        'M_U_SLOT': [(-0.25, 0.5), (-0.25, 0.0)] + arc(0, 0, 0.25, 180, 360, 12)[1:-1] + [(0.25, 0.0), (0.25, 0.5)],
        'M_SQUARE_NOTCH': [(-0.3, -0.3), (0.3, -0.3), (0.3, 0.5), (-0.3, 0.5)],
        'M_DOVETAIL': [(-0.35, -0.3), (0.35, -0.3), (0.2, 0.5), (-0.2, 0.5)],
        'M_WIDE_NOTCH': [(-0.2, -0.3), (0.2, -0.3), (0.45, 0.5), (-0.45, 0.5)],
        'M_STEP_NOTCH': [(-0.25, -0.1), (0.25, -0.1), (0.25, 0.2), (0.5, 0.2), (0.5, 0.5), (-0.5, 0.5), (-0.5, 0.2),
                         (-0.25, 0.2)],
        'M_SAW_EDGE': [(-0.6, 0.0), (-0.4, -0.3), (-0.2, 0.0), (0.0, -0.3), (0.2, 0.0), (0.4, -0.3), (0.6, 0.0),
                       (0.6, 0.3), (-0.6, 0.3)],
        'M_SCALLOP_EDGE': scallop[::-1],
        'M_CRENEL_EDGE': [(-0.6, -0.3), (-0.4, -0.3), (-0.4, 0.0), (-0.1, 0.0), (-0.1, -0.3), (0.1, -0.3), (0.1, 0.0),
                          (0.4, 0.0), (0.4, -0.3), (0.6, -0.3), (0.6, 0.3), (-0.6, 0.3)],
        'M_WAVE_EDGE': wave[::-1],
        'M_CHAMFER_PANEL': chamfer_rect(0.5, 0.3, 0.12),
        'M_TWO_CORNER_PANEL': [(-0.3, -0.3), (0.5, -0.3), (0.5, 0.1), (0.3, 0.3), (-0.5, 0.3), (-0.5, -0.1)],
        'M_ROUND_PANEL': round_rect(0.5, 0.3, 0.14),
        'M_LONG_HEX': [(-0.5, 0), (-0.3, -0.25), (0.3, -0.25), (0.5, 0), (0.3, 0.25), (-0.3, 0.25)],
        'M_OCTAGON': regular(8, 0.5, start=math.pi / 8),
        'M_DIAMOND': [(0, -0.5), (0.35, 0), (0, 0.5), (-0.35, 0)],
        'M_KITE': [(0, -0.5), (0.3, 0.15), (0, 0.5), (-0.3, 0.15)],
        'M_TALL_TRAPEZOID': [(-0.3, -0.5), (0.3, -0.5), (0.18, 0.5), (-0.18, 0.5)],
        'M_PARALLELOGRAM': [(-0.5, -0.2), (0.25, -0.2), (0.5, 0.2), (-0.25, 0.2)],
        'M_ARROWHEAD': [(0, 0.5), (-0.45, -0.35), (0, -0.1), (0.45, -0.35)],
        'M_CHEVRON': [(0, -0.3), (0.5, 0.3), (0.3, 0.3), (0, 0.0), (-0.3, 0.3), (-0.5, 0.3)],
        'M_WEDGE': [(-0.5, -0.08), (0.5, 0.0), (-0.5, 0.08)],
        'M_SHIELD': [(0, -0.5), (0.4, 0.0), (0.4, 0.5), (-0.4, 0.5), (-0.4, 0.0)],
        'M_SHOULDER': arc(0, 0, 0.5, 0, 180, 16, ry=0.35) + [(-0.4, -0.2), (0.4, -0.2)],
        'M_KNEE': [(0, -0.5), (0.35, 0.0), (0.3, 0.5), (-0.3, 0.5), (-0.35, 0.0)],
        'M_VISOR': [(-0.42, -0.08), (0.42, -0.08), (0.5, 0.05), (0.38, 0.12), (-0.38, 0.12), (-0.5, 0.05)],
        'M_CHEST': [(-0.4, -0.3), (0.4, -0.3), (0.5, 0.2), (0.25, 0.35), (0.1, 0.35), (0, 0.25), (-0.1, 0.35),
                    (-0.25, 0.35), (-0.5, 0.2)],
        'M_BLADE': [(-0.5, -0.1), (0.2, -0.05), (0.5, 0.15), (0.1, 0.05), (-0.5, 0.05)],
        'M_FIN': [(-0.5, -0.25), (0.2, -0.25), (0.5, 0.25), (0.0, 0.25)],
        'M_TAPER_BAR': [(-0.5, -0.12), (0.5, -0.06), (0.5, 0.06), (-0.5, 0.12)],
        'M_CRESCENT': crescent(),
        'M_HALF_DISC': arc(0, 0, 0.5, 0, 180, 16),
        'M_QUARTER_DISC': [(0, 0)] + arc(0, 0, 1, 0, 90, 12),
        'M_ARC_BAND': arc(0, 0, 0.5, 30, 150, 14) + arc(0, 0, 0.3, 150, 30, 14),
        'M_L_BLOCK': [(0, 0), (1, 0), (1, 0.35), (0.35, 0.35), (0.35, 1), (0, 1)],
        'M_T_BLOCK': [(-0.15, -0.5), (0.15, -0.5), (0.15, 0.2), (0.5, 0.2), (0.5, 0.5), (-0.5, 0.5), (-0.5, 0.2),
                      (-0.15, 0.2)],
        'M_CROSS': [(-0.15, -0.5), (0.15, -0.5), (0.15, -0.15), (0.5, -0.15), (0.5, 0.15), (0.15, 0.15), (0.15, 0.5),
                    (-0.15, 0.5), (-0.15, 0.15), (-0.5, 0.15), (-0.5, -0.15), (-0.15, -0.15)],
        'M_Z_STEP': [(-0.5, -0.3), (0.1, -0.3), (0.1, 0.0), (0.5, 0.0), (0.5, 0.3), (-0.1, 0.3), (-0.1, 0.0),
                     (-0.5, 0.0)],
        'M_STEP_PYRAMID': [(-0.5, -0.3), (0.5, -0.3), (0.5, -0.1), (0.3, -0.1), (0.3, 0.1), (0.1, 0.1), (0.1, 0.3),
                           (-0.1, 0.3), (-0.1, 0.1), (-0.3, 0.1), (-0.3, -0.1), (-0.5, -0.1)],
        'M_Y_FORK': [(-0.12, -0.5), (0.12, -0.5), (0.12, 0.0), (0.45, 0.4), (0.3, 0.5), (0, 0.15), (-0.3, 0.5),
                     (-0.45, 0.4), (-0.12, 0.0)],
        'M_SLASH_BAND': [(-0.5, -0.5), (-0.25, -0.5), (0.5, 0.5), (0.25, 0.5)],
        'M_THREE_PRONGS': [(-0.45, -0.5), (0.45, -0.5), (0.45, 0.5), (0.3, 0.5), (0.3, 0.0), (0.075, 0.0),
                           (0.075, 0.5), (-0.075, 0.5), (-0.075, 0.0), (-0.3, 0.0), (-0.3, 0.5), (-0.45, 0.5)],
        'M_HOOK': [(0.1, -0.25), (0.05, -0.32), (-0.12, -0.32), (-0.2, -0.25), (-0.2, -0.05), (-0.4, -0.05),
                   (-0.4, -0.3), (-0.25, -0.5), (0.15, -0.5), (0.3, -0.3), (0.3, 0.5), (0.1, 0.5)],
        'M_ANGLE_CUTOFF': [(-0.5, -0.5), (0.5, -0.5), (0.5, 0.5), (-0.5, -0.1)],
        'M_ARCH': [(-0.3, -0.5), (0.3, -0.5), (0.3, 0.1)] + arc(0, 0.1, 0.3, 0, 180, 12)[1:-1] + [(-0.3, 0.1)],
    }


def ccw(lp):
    a = sum(lp[i][0] * lp[(i + 1) % len(lp)][1] - lp[(i + 1) % len(lp)][0] * lp[i][1] for i in range(len(lp)))
    return lp if a > 0 else lp[::-1]


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
    data.update({k: [ccw(v)] for k, v in mech_shapes().items()})
    out = {'schema': 1, 'shapes': [{'stem': s, 'name': n, 'loops': normalize(data[s])} for s, n in SHAPES]}
    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    OUT_JSON.write_text(json.dumps(out, separators=(',', ':')), encoding='utf-8')
    print('wrote', OUT_JSON, [(s['stem'], sum(len(lp) for lp in s['loops'])) for s in out['shapes']])


def build_icons():
    """0.24.95 light thumbnails (user: "썸네일도 보이게 그치만 가볍게"): a soft pale silhouette on clear, 64 px."""
    from PIL import Image, ImageDraw
    S, OUT = 256, 64
    d = json.loads(OUT_JSON.read_text(encoding='utf-8'))
    for sh in d['shapes']:
        img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
        dr = ImageDraw.Draw(img)
        for lp in sh['loops']:
            pts = [(S / 2 + x * S * 0.8, S / 2 - y * S * 0.8) for x, y in lp]
            dr.polygon(pts, fill=(206, 212, 222, 150))
            dr.line(pts + [pts[0]], fill=(236, 240, 246, 235), width=7, joint='curve')
        path = ADDON / 'icons' / f'shape_{sh["stem"].lower()}.png'
        img.resize((OUT, OUT), Image.LANCZOS).save(path, optimize=True)
        print('icon', path.name)


if __name__ == '__main__':
    {'json': build_json, 'icons': build_icons}[sys.argv[1] if len(sys.argv) > 1 else 'json']()
