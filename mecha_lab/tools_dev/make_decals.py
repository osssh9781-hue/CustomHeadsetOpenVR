"""0.24.95 The decal library for Mecha Lab's Decals (user: picked "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능").

Every decal is a two-tone mask, so its colours are chosen in Blender: RGB white = Color 1, black = Color 2, alpha =
where the decal is.  ``addon/mecha_lab/decals/<ID>.png`` (512 px on the long side) and its tile picture
``addon/mecha_lab/mech_icons/decal_<ID>.png`` (128 px, the default colours on dark grey).  The letters for Text
decals: ``decals/glyphs.png`` (an 8 x 6 atlas, 128 px cells, DejaVu Sans Bold - Bitstream Vera licence, rendered
shapes only) + ``decals/glyphs.json`` (each character's cell and width).

    python3 tools_dev/make_decals.py          (numpy + Pillow)
    python3 tools_dev/make_decals.py tech     (0.24.95 only the Tech Marks - the others left as they are)

0.24.95 (user: "너도 좀 더 바코드 같은 데칼 종류 더 만들어 줘") 24 Tech Marks (``TECH``): barcodes, QR / Data Matrix
codes, serial / lot labels, ruler, tick ring, gauge, registration target, tech text, warning label, keep clear, number,
hex grid, dashes, pinstripes, checker band, circuit, power cell, arrow row, axis mark, panel ID, perforation - the
same two-tone way (the codes are random patterns, not real codes).
"""
import json
import math
import os

import numpy as np
from PIL import Image, ImageDraw, ImageFont

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addon', 'mecha_lab', 'decals')
ICONS = os.path.join(ROOT, 'addon', 'mecha_lab', 'mech_icons')
FONT = '/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'
MONO = '/usr/share/fonts/truetype/dejavu/DejaVuSansMono-Bold.ttf'
SS = 2                       # (drawn at 2 x, then reduced: smooth edges)

# id: (label, width : height, colour 1, colour 2) - the same table is in mecha_lab/decals.py
DECALS = {
    'HAZARD': ('Hazard Stripes', 2.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'HAZARD_RW': ('Red / White Stripes', 2.0, (0.85, 0.1, 0.08), (0.92, 0.92, 0.9)),
    'BARS': ('Two Bars', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CHEVRON': ('Chevrons', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'ARROW': ('Arrow', 2.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'WARNING': ('Warning', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'VOLTAGE': ('High Voltage', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'RADIATION': ('Radiation', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'NO_STEP': ('No Step', 2.5, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'DANGER': ('Danger', 2.5, (0.85, 0.1, 0.08), (0.95, 0.95, 0.93)),
    'CAUTION': ('Caution', 2.5, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'EJECT': ('Eject', 2.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'LIFT': ('Lift Point', 1.6, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'FUEL': ('Fuel', 1.0, (0.92, 0.92, 0.9), (0.85, 0.1, 0.08)),
    'ROUNDEL': ('Roundel', 1.0, (0.92, 0.92, 0.9), (0.1, 0.25, 0.6)),
    'CROSSHAIR': ('Crosshair', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'VENT': ('Vent Slots', 1.6, (0.05, 0.05, 0.05), (0.3, 0.3, 0.3)),
    'BARCODE': ('Barcode', 2.0, (0.05, 0.05, 0.05), (0.92, 0.92, 0.9)),
    'SERIAL': ('Serial Plate', 2.2, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'STAR': ('Star', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'RANK': ('Rank Stripes', 1.0, (0.95, 0.75, 0.05), (0.05, 0.05, 0.05)),
    'DOTS': ('Dot Grid', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CORNERS': ('Corner Brackets', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
    'CIRCLE_NUM': ('Unit Circle', 1.0, (0.92, 0.92, 0.9), (0.05, 0.05, 0.05)),
}
W1, K1, Y1, R1 = (0.92, 0.92, 0.9), (0.05, 0.05, 0.05), (0.95, 0.75, 0.05), (0.85, 0.1, 0.08)
TECH = {
    'BARCODE_TALL': ('Barcode Label', 1.25, K1, W1),
    'BARCODE_STRIP': ('Barcode Strip', 4.0, W1, K1),
    'QR': ('QR Code', 1.0, K1, W1),
    'DATAMATRIX': ('Data Matrix', 1.0, K1, W1),
    'SERIAL_TAG': ('Serial Tag', 2.4, W1, (0.12, 0.12, 0.13)),
    'LOT_LABEL': ('Lot Label', 1.6, K1, W1),
    'RULER': ('Ruler', 6.0, W1, K1),
    'TICK_RING': ('Tick Ring', 1.0, W1, K1),
    'GAUGE': ('Gauge', 1.4, W1, K1),
    'TARGET': ('Reg. Target', 1.0, W1, K1),
    'TECH_TEXT': ('Tech Text', 3.2, W1, K1),
    'WARN_LABEL': ('Warning Label', 3.2, Y1, K1),
    'KEEP_CLEAR': ('Keep Clear', 2.5, W1, K1),
    'NUMBER': ('Stencil 07', 1.1, W1, K1),
    'HEXGRID': ('Hex Grid', 1.6, W1, K1),
    'DASHES': ('Dash Line', 8.0, W1, K1),
    'PINSTRIPE': ('Pinstripes', 8.0, R1, W1),
    'CHECKER': ('Checker Band', 6.0, W1, K1),
    'CIRCUIT': ('Circuit', 1.6, W1, K1),
    'POWER_CELL': ('Power Cell', 2.0, W1, K1),
    'ARROW_ROW': ('Arrow Row', 4.0, Y1, K1),
    'AXIS': ('Axis Mark', 1.0, W1, R1),
    'PANEL_ID': ('Panel ID', 1.5, K1, W1),
    'PERFORATION': ('Perforation', 2.0, W1, K1),
}
DECALS.update(TECH)
GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./#:+!?'
CELL = 128


def font(px, mono=False):
    return ImageFont.truetype(MONO if mono else FONT, int(px))


def canvas(ratio, long=512):
    w, h = (long, int(long / ratio)) if ratio >= 1 else (int(long * ratio), long)
    w, h = w * SS, h * SS
    # two layers: coverage (alpha) and primary (white = colour 1)
    a = Image.new('L', (w, h), 0)
    p = Image.new('L', (w, h), 0)
    return a, p, ImageDraw.Draw(a), ImageDraw.Draw(p), w, h


def text_center(draw, w, h, s, px, cx=None, cy=None, fill=255, mono=False):
    f = font(px, mono)
    box = draw.textbbox((0, 0), s, font=f)
    tw, th = box[2] - box[0], box[3] - box[1]
    x = (w if cx is None else 2 * cx) / 2 - tw / 2 - box[0]
    y = (h if cy is None else 2 * cy) / 2 - th / 2 - box[1]
    draw.text((x, y), s, font=f, fill=fill)


def stripes(da, dp, w, h, n=6, slope=1.0):
    da.rectangle((0, 0, w, h), fill=255)
    period = w / n
    for i in range(-n, 2 * n):
        x0 = i * period
        poly = [(x0, h), (x0 + period / 2, h), (x0 + period / 2 + h * slope, 0), (x0 + h * slope, 0)]
        dp.polygon(poly, fill=255)


def triangle(da, dp, w, h, inner):
    m = 0.06 * w
    tri = [(w / 2, m), (w - m, h - m * 1.2), (m, h - m * 1.2)]
    da.polygon(tri, fill=255)
    dp.polygon(tri, fill=255)
    m2 = 0.17 * w
    tri2 = [(w / 2, m2 * 1.15), (w - m2, h - m2 * 0.85), (m2, h - m2 * 0.85)]
    dp.polygon(tri2, fill=0)                     # (a colour-2 field inside a colour-1 rim)
    inner(dp, w, h)


def bars(dp, x0, x1, y0, y1, unit, rng):
    x = x0
    while x < x1:
        bw = rng.choice([1, 1, 2, 3]) * unit
        dp.rectangle((x, y0, min(x + bw, x1), y1), fill=255)
        x += bw + rng.choice([1, 2]) * unit


def code_grid(dp, x0, y0, size, n, cells):
    c = size / n
    for (i, j) in cells:
        dp.rectangle((x0 + i * c, y0 + j * c, x0 + (i + 1) * c - 1, y0 + (j + 1) * c - 1), fill=255)


def text_left(draw, x, y, s, px, mono=True, fill=255):
    f = font(px, mono)
    box = draw.textbbox((0, 0), s, font=f)
    draw.text((x - box[0], y - box[1]), s, font=f, fill=fill)


def make_tech(ident, a, p, da, dp, w, h):
    """0.24.95 the Tech Marks (white in the colour layer = Color 1, the rest of the coverage = Color 2)."""
    rng = np.random.default_rng(sum(ord(ch) for ch in ident))      # (the same picture on every run)
    if ident == 'BARCODE_TALL':
        da.rounded_rectangle((0, 0, w, h), radius=0.04 * h, fill=255)
        bars(dp, 0.08 * w, 0.92 * w, 0.08 * h, 0.72 * h, 0.009 * w, rng)
        text_center(dp, w, h, '4 017338 270914', h * 0.12, cy=h * 0.84, mono=True)
    elif ident == 'BARCODE_STRIP':
        bars(da, 0.0, w, 0.0, h, 0.0055 * w, rng)
        dp.bitmap((0, 0), a, fill=255)
    elif ident in ('QR', 'DATAMATRIX'):
        da.rectangle((0, 0, w, h), fill=255)
        n = 25 if ident == 'QR' else 18
        q = 0.08 * w
        size = w - 2 * q
        cells = {(i, j) for i in range(n) for j in range(n) if rng.random() < 0.5}
        if ident == 'QR':
            for fx, fy in ((0, 0), (n - 7, 0), (0, n - 7)):          # (the three finder squares)
                for i in range(-1, 8):
                    for j in range(-1, 8):
                        cells.discard((fx + i, fy + j))
                for i in range(7):
                    for j in range(7):
                        if i in (0, 6) or j in (0, 6) or (2 <= i <= 4 and 2 <= j <= 4):
                            cells.add((fx + i, fy + j))
        else:
            cells = {(i, j) for (i, j) in cells if 0 < i < n - 1 and 0 < j < n - 1}
            cells |= {(0, j) for j in range(n)} | {(i, n - 1) for i in range(n)}          # (the solid L)
            cells |= {(i, 0) for i in range(0, n, 2)} | {(n - 1, j) for j in range(1, n, 2)}   # (its clock track)
        code_grid(dp, q, q, size, n, cells)
    elif ident == 'SERIAL_TAG':
        da.rounded_rectangle((0, 0, w, h), radius=0.14 * h, fill=255)
        dp.rounded_rectangle((0.02 * w, 0.06 * h, 0.98 * w, 0.94 * h), radius=0.11 * h, outline=255,
                             width=int(0.035 * h))
        text_left(dp, 0.07 * w, 0.2 * h, 'S/N', h * 0.16)
        text_left(dp, 0.07 * w, 0.42 * h, '2187-0447-A', h * 0.26)
        bars(dp, 0.07 * w, 0.62 * w, 0.76 * h, 0.86 * h, 0.006 * w, rng)
        for k in range(4):
            cx = (0.72 + 0.065 * k) * w
            dp.ellipse((cx - 0.022 * w, 0.78 * h - 0.022 * w, cx + 0.022 * w, 0.78 * h + 0.022 * w), fill=255)
    elif ident == 'LOT_LABEL':
        da.rectangle((0, 0, w, h), fill=255)
        dp.rectangle((0.03 * w, 0.04 * h, 0.97 * w, 0.96 * h), outline=255, width=int(0.02 * h))
        dp.rectangle((0.03 * w, 0.04 * h, 0.97 * w, 0.22 * h), fill=255)
        text_center(da, w, h, 'MECHA LAB', h * 0.12, cy=0.13 * h, fill=255, mono=True)
        lab = Image.new('L', (w, h), 0)
        text_center(ImageDraw.Draw(lab), w, h, 'MECHA LAB', h * 0.12, cy=0.13 * h, mono=True)
        p.paste(0, (0, 0), lab)
        for k, line in enumerate(('LOT   2391-B', 'MFG   07.2187', 'QC    PASS')):
            text_left(dp, 0.08 * w, (0.3 + 0.13 * k) * h, line, h * 0.09)
        bars(dp, 0.08 * w, 0.92 * w, 0.72 * h, 0.9 * h, 0.006 * w, rng)
    elif ident == 'RULER':
        da.rectangle((0, 0, w, 0.08 * h), fill=255)
        for i in range(101):
            x = 0.02 * w + i * 0.96 * w / 100
            L = 0.75 if i % 10 == 0 else (0.5 if i % 5 == 0 else 0.3)
            da.rectangle((x - 0.0016 * w, 0, x + 0.0016 * w, L * h), fill=255)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'TICK_RING':
        c = w / 2
        for i in range(60):
            t = math.radians(i * 6)
            r0 = 0.36 if i % 5 == 0 else 0.41
            pts = []
            for r, dt in ((r0, -0.012 if i % 5 else -0.02), (0.48, -0.012 if i % 5 else -0.02),
                          (0.48, 0.012 if i % 5 else 0.02), (r0, 0.012 if i % 5 else 0.02)):
                pts.append((c + math.cos(t + dt) * r * w, c + math.sin(t + dt) * r * w))
            da.polygon(pts, fill=255)
        da.ellipse((c - 0.03 * w, c - 0.03 * w, c + 0.03 * w, c + 0.03 * w), fill=255)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'GAUGE':
        cx, cy, r = w / 2, 0.86 * h, 0.44 * w
        da.pieslice((cx - r, cy - r, cx + r, cy + r), 180, 360, fill=255)
        for i in range(21):
            t = math.radians(180 + i * 9)
            r0 = 0.78 if i % 5 == 0 else 0.86
            dp.line([(cx + math.cos(t) * r0 * r, cy + math.sin(t) * r0 * r),
                     (cx + math.cos(t) * 0.96 * r, cy + math.sin(t) * 0.96 * r)], fill=255,
                    width=int(0.012 * w if i % 5 == 0 else 0.006 * w))
        t = math.radians(305)
        dp.polygon([(cx + math.cos(t) * 0.8 * r, cy + math.sin(t) * 0.8 * r),
                    (cx + math.cos(t + 1.57) * 0.03 * r, cy + math.sin(t + 1.57) * 0.03 * r),
                    (cx + math.cos(t - 1.57) * 0.03 * r, cy + math.sin(t - 1.57) * 0.03 * r)], fill=255)
        dp.ellipse((cx - 0.06 * r, cy - 0.06 * r, cx + 0.06 * r, cy + 0.06 * r), fill=255)
        text_center(dp, w, h, 'x100', h * 0.1, cy=cy - 0.35 * r, mono=True)
    elif ident == 'TARGET':
        c = w / 2
        da.ellipse((c - 0.4 * w, c - 0.4 * w, c + 0.4 * w, c + 0.4 * w), fill=255)
        dp.pieslice((c - 0.4 * w, c - 0.4 * w, c + 0.4 * w, c + 0.4 * w), 0, 90, fill=255)
        dp.pieslice((c - 0.4 * w, c - 0.4 * w, c + 0.4 * w, c + 0.4 * w), 180, 270, fill=255)
        for d in (da, dp):
            d.rectangle((c - 0.008 * w, 0, c + 0.008 * w, h), fill=255)
            d.rectangle((0, c - 0.008 * w, w, c + 0.008 * w), fill=255)
        dp.ellipse((c - 0.4 * w, c - 0.4 * w, c + 0.4 * w, c + 0.4 * w), outline=255, width=int(0.012 * w))
    elif ident == 'TECH_TEXT':
        da.rectangle((0, 0.05 * h, 0.018 * w, 0.95 * h), fill=255)
        for k, (line, px) in enumerate((('MK-IV ASSAULT FRAME', 0.2), ('LOAD 2.4T   CLASS B', 0.15),
                                        ('REF 07-114  REV C  ////', 0.15))):
            text_left(da, 0.045 * w, (0.07 + 0.32 * k) * h, line, h * px)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'WARN_LABEL':
        da.rectangle((0, 0, w, h), fill=255)
        sw = int(0.22 * w)
        st = Image.new('L', (sw, h), 0)
        stripes(ImageDraw.Draw(Image.new('L', (1, 1))), ImageDraw.Draw(st), sw, h, n=3)
        p.paste(st, (0, 0))
        dp.rectangle((0, 0, w - 1, h - 1), outline=255, width=int(0.05 * h))
        text_center(dp, w, h, 'WARNING', h * 0.36, cx=0.61 * w, cy=0.38 * h)
        text_center(dp, w, h, 'HIGH PRESSURE SYSTEM', h * 0.13, cx=0.61 * w, cy=0.76 * h, mono=True)
    elif ident == 'KEEP_CLEAR':
        for d in (da, dp):
            d.rectangle((0, 0, w - 1, h - 1), outline=255, width=int(0.06 * h))
            for sx in (0, 1):
                for sy in (0, 1):
                    x, y = (0 if sx == 0 else w), (0 if sy == 0 else h)
                    dx, dy = (1 if sx == 0 else -1), (1 if sy == 0 else -1)
                    d.polygon([(x, y), (x + dx * 0.22 * h, y), (x, y + dy * 0.22 * h)], fill=255)
        text_center(da, w, h, 'KEEP CLEAR', h * 0.36)
        text_center(dp, w, h, 'KEEP CLEAR', h * 0.36)
    elif ident == 'NUMBER':
        f = font(h * 0.78)
        box = da.textbbox((0, 0), '07', font=f)
        x0 = (w - (box[2] - box[0])) / 2 - box[0]
        y0 = (h - (box[3] - box[1])) / 2 - box[1]
        da.text((x0, y0), '07', font=f, fill=255)
        z = da.textbbox((x0, y0), '0', font=f)                    # (the 0's own box: its two stencil bridges)
        cx = (z[0] + z[2]) / 2
        for ya, yb in ((z[1] - 2, z[1] + 0.3 * (z[3] - z[1])), (z[3] - 0.3 * (z[3] - z[1]), z[3] + 2)):
            da.rectangle((cx - 0.022 * w, ya, cx + 0.022 * w, yb), fill=0)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'HEXGRID':
        r = 0.09 * h
        for j in range(-1, 8):
            for i in range(-1, 12):
                cx = i * 1.5 * r * 1.02 + 0.1 * w
                cy = j * math.sqrt(3) * r * 1.02 + (i % 2) * math.sqrt(3) / 2 * r * 1.02 + 0.08 * h
                pts = [(cx + math.cos(math.radians(60 * k)) * r, cy + math.sin(math.radians(60 * k)) * r)
                       for k in range(6)]
                da.polygon(pts, outline=255, width=int(0.012 * h))
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'DASHES':
        for i in range(14):
            x0 = (i / 14) * w + 0.012 * w
            da.rectangle((x0, 0.3 * h, x0 + 0.045 * w, 0.7 * h), fill=255)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'PINSTRIPE':
        da.rectangle((0, 0.08 * h, w, 0.92 * h), fill=255)
        dp.rectangle((0, 0.08 * h, w, 0.48 * h), fill=255)
        dp.rectangle((0, 0.68 * h, w, 0.92 * h), fill=255)
        da.rectangle((0, 0.48 * h, w, 0.68 * h), fill=0)
    elif ident == 'CHECKER':
        n = 24
        for i in range(n):
            for j in range(2):
                da.rectangle((i * w / n, j * h / 2, (i + 1) * w / n, (j + 1) * h / 2), fill=255)
                if (i + j) % 2 == 0:
                    dp.rectangle((i * w / n, j * h / 2, (i + 1) * w / n, (j + 1) * h / 2), fill=255)
    elif ident == 'CIRCUIT':
        lw = int(0.018 * h)
        for k in range(9):
            y = (0.12 + k * 0.095) * h
            x0 = rng.uniform(0.02, 0.2) * w
            x1 = rng.uniform(0.45, 0.7) * w
            y1 = y + rng.choice([-1, 1]) * 0.09 * h
            x2 = rng.uniform(0.78, 0.96) * w
            da.line([(x0, y), (x1, y), (x1 + abs(y1 - y), y1), (x2, y1)], fill=255, width=lw, joint='curve')
            for (px, py) in ((x0, y), (x2, y1)):
                r = 0.03 * h
                da.ellipse((px - r, py - r, px + r, py + r), fill=255)
                da.ellipse((px - r * 0.45, py - r * 0.45, px + r * 0.45, py + r * 0.45), fill=0)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'POWER_CELL':
        da.rounded_rectangle((0.02 * w, 0.12 * h, 0.9 * w, 0.88 * h), radius=0.08 * h, fill=255)
        da.rectangle((0.9 * w, 0.36 * h, 0.97 * w, 0.64 * h), fill=255)
        dp.rectangle((0.9 * w, 0.36 * h, 0.97 * w, 0.64 * h), fill=255)
        dp.rounded_rectangle((0.02 * w, 0.12 * h, 0.9 * w, 0.88 * h), radius=0.08 * h, outline=255,
                             width=int(0.06 * h))
        for k in range(3):
            x0 = (0.08 + k * 0.205) * w
            dp.rectangle((x0, 0.26 * h, x0 + 0.17 * w, 0.74 * h), fill=255)
    elif ident == 'ARROW_ROW':
        da.rectangle((0, 0, w, h), fill=255)
        for i in range(7):
            x0 = (0.04 + i * 0.135) * w
            dp.polygon([(x0, 0.15 * h), (x0 + 0.05 * w, 0.15 * h), (x0 + 0.1 * w, 0.5 * h), (x0 + 0.05 * w, 0.85 * h),
                        (x0, 0.85 * h), (x0 + 0.05 * w, 0.5 * h)], fill=255)
    elif ident == 'AXIS':
        lw = 0.045 * w
        for d in (da, dp):
            d.rectangle((0.12 * w, 0.84 * h - lw / 2, 0.8 * w, 0.84 * h + lw / 2), fill=255)
            d.polygon([(0.78 * w, 0.74 * h), (0.96 * w, 0.84 * h), (0.78 * w, 0.94 * h)], fill=255)
        for d in (da,):
            d.rectangle((0.16 * w - lw / 2, 0.2 * h, 0.16 * w + lw / 2, 0.88 * h), fill=255)
            d.polygon([(0.06 * w, 0.22 * h), (0.16 * w, 0.04 * h), (0.26 * w, 0.22 * h)], fill=255)
        text_center(da, w, h, 'X', h * 0.2, cx=0.62 * w, cy=0.66 * h)
        text_center(dp, w, h, 'X', h * 0.2, cx=0.62 * w, cy=0.66 * h)
        text_center(da, w, h, 'Y', h * 0.2, cx=0.36 * w, cy=0.2 * h)
    elif ident == 'PANEL_ID':
        da.polygon([(0, 0), (0.82 * w, 0), (w, 0.28 * h), (w, h), (0, h)], fill=255)
        dp.polygon([(0.04 * w, 0.06 * h), (0.8 * w, 0.06 * h), (0.95 * w, 0.3 * h), (0.95 * w, 0.94 * h),
                    (0.04 * w, 0.94 * h)], outline=255, width=int(0.035 * h))
        text_center(dp, w, h, 'A-07', h * 0.42, cy=0.47 * h)
        text_center(dp, w, h, 'PANEL', h * 0.12, cy=0.8 * h, mono=True)
    elif ident == 'PERFORATION':
        r = 0.05 * h
        for j in range(5):
            for i in range(12):
                cx = (0.06 + i * 0.08 + (j % 2) * 0.04) * w
                cy = (0.14 + j * 0.18) * h
                if cx + r > w:
                    continue
                da.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
        dp.bitmap((0, 0), a, fill=255)


def make(ident):
    label, ratio, _c1, _c2 = DECALS[ident]
    a, p, da, dp, w, h = canvas(ratio)
    if ident in TECH:
        make_tech(ident, a, p, da, dp, w, h)
    elif ident in ('HAZARD', 'HAZARD_RW'):
        stripes(da, dp, w, h)
    elif ident == 'BARS':
        for y0 in (0.12, 0.58):
            da.rectangle((0, y0 * h, w, (y0 + 0.3) * h), fill=255)
            dp.rectangle((0, y0 * h, w, (y0 + 0.3) * h), fill=255)
    elif ident == 'CHEVRON':
        for i in range(3):
            x0 = w * (0.08 + i * 0.28)
            poly = [(x0, 0.1 * h), (x0 + 0.13 * w, 0.1 * h), (x0 + 0.3 * w, 0.5 * h), (x0 + 0.13 * w, 0.9 * h),
                    (x0, 0.9 * h), (x0 + 0.17 * w, 0.5 * h)]
            da.polygon(poly, fill=255)
            dp.polygon(poly, fill=255)
    elif ident == 'ARROW':
        poly = [(0.04 * w, 0.36 * h), (0.62 * w, 0.36 * h), (0.62 * w, 0.1 * h), (0.96 * w, 0.5 * h),
                (0.62 * w, 0.9 * h), (0.62 * w, 0.64 * h), (0.04 * w, 0.64 * h)]
        da.polygon(poly, fill=255)
        dp.polygon(poly, fill=255)
    elif ident == 'WARNING':
        triangle(da, dp, w, h, lambda d, w, h: text_center(d, w, h, '!', h * 0.4, cy=h * 0.62))
    elif ident == 'VOLTAGE':
        def bolt(d, w, h):
            d.polygon([(0.55 * w, 0.3 * h), (0.4 * w, 0.58 * h), (0.5 * w, 0.58 * h), (0.43 * w, 0.8 * h),
                       (0.62 * w, 0.5 * h), (0.52 * w, 0.5 * h), (0.6 * w, 0.3 * h)], fill=255)
        triangle(da, dp, w, h, bolt)
    elif ident == 'RADIATION':
        da.ellipse((0, 0, w, h), fill=255)
        dp.ellipse((0, 0, w, h), fill=0)
        c = w / 2
        dp.ellipse((c - 0.07 * w, c - 0.07 * w, c + 0.07 * w, c + 0.07 * w), fill=255)
        for k in range(3):
            a0 = -90 + k * 120
            dp.pieslice((c - 0.42 * w, c - 0.42 * w, c + 0.42 * w, c + 0.42 * w), a0 - 30, a0 + 30, fill=255)
        dp.ellipse((c - 0.12 * w, c - 0.12 * w, c + 0.12 * w, c + 0.12 * w), fill=0)
        dp.ellipse((c - 0.07 * w, c - 0.07 * w, c + 0.07 * w, c + 0.07 * w), fill=255)
    elif ident == 'NO_STEP':
        da.rectangle((0, 0, w, h), fill=0)
        for y0 in (0.08, 0.82):
            da.rectangle((0.03 * w, y0 * h, 0.97 * w, (y0 + 0.08) * h), fill=255)
            dp.rectangle((0.03 * w, y0 * h, 0.97 * w, (y0 + 0.08) * h), fill=255)
        text_center(da, w, h, 'NO STEP', h * 0.42)
        text_center(dp, w, h, 'NO STEP', h * 0.42)
    elif ident in ('DANGER', 'CAUTION'):
        da.rectangle((0, 0, w, h), fill=255)
        dp.rectangle((0, 0, w, h), fill=255)
        dp.rectangle((0.05 * w, 0.12 * h, 0.95 * w, 0.88 * h), fill=0)
        text_center(dp, w, h, label.upper(), h * 0.4)
    elif ident == 'EJECT':
        da.rectangle((0, 0, w, h), fill=255)
        stripes(da, dp, w, h * 0.22, n=10)
        dp.rectangle((0, 0.22 * h, w, 0.78 * h), fill=0)
        a2 = Image.new('L', (w, int(h * 0.22) + 1), 0)
        d2 = ImageDraw.Draw(a2)
        stripes(ImageDraw.Draw(Image.new('L', (1, 1))), d2, w, h * 0.22, n=10)
        p.paste(a2, (0, int(h * 0.78)))
        text_center(dp, w, h, 'EJECT', h * 0.4)
    elif ident == 'LIFT':
        text_center(da, w, h, 'LIFT', h * 0.36, cy=h * 0.3)
        text_center(dp, w, h, 'LIFT', h * 0.36, cy=h * 0.3)
        poly = [(0.5 * w, 0.95 * h), (0.3 * w, 0.62 * h), (0.43 * w, 0.62 * h), (0.43 * w, 0.52 * h),
                (0.57 * w, 0.52 * h), (0.57 * w, 0.62 * h), (0.7 * w, 0.62 * h)]
        da.polygon(poly, fill=255)
        dp.polygon(poly, fill=255)
    elif ident == 'FUEL':
        da.ellipse((0, 0, w, h), fill=255)
        dp.ellipse((0, 0, w, h), fill=255)
        dp.ellipse((0.1 * w, 0.1 * h, 0.9 * w, 0.9 * h), fill=0)
        text_center(dp, w, h, 'FUEL', h * 0.26)
    elif ident == 'ROUNDEL':
        da.ellipse((0, 0, w, h), fill=255)
        for r, col in ((0.5, 0), (0.36, 255), (0.2, 0)):
            dp.ellipse(((0.5 - r) * w, (0.5 - r) * h, (0.5 + r) * w, (0.5 + r) * h), fill=col)
    elif ident == 'CROSSHAIR':
        c = w / 2
        for r0, r1 in ((0.46, 0.4),):
            da.ellipse((c - r0 * w, c - r0 * w, c + r0 * w, c + r0 * w), fill=255)
            da.ellipse((c - r1 * w, c - r1 * w, c + r1 * w, c + r1 * w), fill=0)
        for x0, y0, x1, y1 in ((0.47, 0.0, 0.53, 0.38), (0.47, 0.62, 0.53, 1.0), (0.0, 0.47, 0.38, 0.53),
                               (0.62, 0.47, 1.0, 0.53)):
            da.rectangle((x0 * w, y0 * h, x1 * w, y1 * h), fill=255)
        dp.bitmap((0, 0), a, fill=255)
    elif ident == 'VENT':
        da.rounded_rectangle((0, 0, w, h), radius=0.08 * h, fill=255)
        for i in range(6):
            y0 = (0.1 + i * 0.14) * h
            dp.rounded_rectangle((0.08 * w, y0, 0.92 * w, y0 + 0.08 * h), radius=0.04 * h, fill=255)
    elif ident == 'BARCODE':
        da.rectangle((0, 0, w, h), fill=255)
        rng = np.random.default_rng(7)
        x = 0.06 * w
        while x < 0.94 * w:
            bw = rng.choice([1, 2, 3]) * 0.008 * w
            dp.rectangle((x, 0.1 * h, x + bw, 0.8 * h), fill=255)
            x += bw + rng.choice([1, 2]) * 0.008 * w
        text_center(dp, w, h, '0427 3381 92', h * 0.12, cy=h * 0.9)
    elif ident == 'SERIAL':
        da.rectangle((0, 0, w, h), fill=0)
        da.rectangle((0.02 * w, 0.04 * h, 0.98 * w, 0.96 * h), outline=255, width=int(0.03 * h))
        dp.rectangle((0.02 * w, 0.04 * h, 0.98 * w, 0.96 * h), outline=255, width=int(0.03 * h))
        for txt, cy, px in (('MK-II  UNIT 07', 0.32, 0.22), ('S/N 0427-A  MECHA LAB', 0.68, 0.14)):
            text_center(da, w, h, txt, h * px, cy=h * cy)
            text_center(dp, w, h, txt, h * px, cy=h * cy)
    elif ident == 'STAR':
        c = w / 2
        pts = [(c + math.cos(math.radians(-90 + i * 36)) * (0.47 if i % 2 == 0 else 0.19) * w,
                c + math.sin(math.radians(-90 + i * 36)) * (0.47 if i % 2 == 0 else 0.19) * w) for i in range(10)]
        da.polygon(pts, fill=255)
        dp.polygon(pts, fill=255)
    elif ident == 'RANK':
        for i in range(3):
            y0 = (0.1 + i * 0.28) * h
            poly = [(0.05 * w, y0 + 0.12 * h), (0.5 * w, y0 - 0.02 * h), (0.95 * w, y0 + 0.12 * h),
                    (0.95 * w, y0 + 0.24 * h), (0.5 * w, y0 + 0.1 * h), (0.05 * w, y0 + 0.24 * h)]
            da.polygon(poly, fill=255)
            dp.polygon(poly, fill=255)
    elif ident == 'DOTS':
        for i in range(5):
            for j in range(5):
                cx, cy = (0.1 + i * 0.2) * w, (0.1 + j * 0.2) * h
                r = 0.055 * w
                da.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
                dp.ellipse((cx - r, cy - r, cx + r, cy + r), fill=255)
    elif ident == 'CORNERS':
        t, L = 0.08 * w, 0.32 * w
        for sx, sy in ((0, 0), (1, 0), (0, 1), (1, 1)):
            x0 = 0 if sx == 0 else w - L
            y0 = 0 if sy == 0 else h - t
            for d in (da, dp):
                d.rectangle((x0, y0, x0 + L, y0 + t), fill=255)
                xv = 0 if sx == 0 else w - t
                yv = 0 if sy == 0 else h - L
                d.rectangle((xv, yv, xv + t, yv + L), fill=255)
    elif ident == 'CIRCLE_NUM':
        da.ellipse((0, 0, w, h), fill=255)
        dp.ellipse((0, 0, w, h), fill=255)
        dp.ellipse((0.07 * w, 0.07 * h, 0.93 * w, 0.93 * h), fill=0)
        text_center(dp, w, h, '07', h * 0.5)
    a = a.resize((w // SS, h // SS), Image.LANCZOS)
    p = p.resize((w // SS, h // SS), Image.LANCZOS)
    img = Image.merge('RGBA', (p, p, p, a))
    img.save(os.path.join(OUT, ident + '.png'), optimize=True)
    return img


def icon(ident, img):
    _l, _r, c1, c2 = DECALS[ident]
    a = np.asarray(img).astype(np.float64) / 255.0
    col = a[..., :1] * np.array(c1) + (1 - a[..., :1]) * np.array(c2)
    bg = np.array([0.26, 0.26, 0.28])
    out = col * a[..., 3:] + bg * (1 - a[..., 3:])
    im = Image.fromarray(np.clip(out ** (1 / 2.2) * 255, 0, 255).astype(np.uint8))
    im.thumbnail((112, 112), Image.LANCZOS)
    tile = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    plate = Image.new('RGBA', im.size, (0, 0, 0, 255))
    plate.paste(im, (0, 0))
    tile.paste(plate, ((128 - im.width) // 2, (128 - im.height) // 2))
    tile.save(os.path.join(ICONS, f'decal_{ident}.png'), optimize=True)


def glyphs():
    cols = 8
    rows = math.ceil(len(GLYPHS) / cols)
    a = Image.new('L', (cols * CELL * SS, rows * CELL * SS), 0)
    d = ImageDraw.Draw(a)
    f = font(CELL * SS * 0.82)
    info = {}
    for i, ch in enumerate(GLYPHS):
        cx, cy = i % cols, i // cols
        box = d.textbbox((0, 0), ch, font=f)
        adv = f.getlength(ch)
        x = cx * CELL * SS + (CELL * SS - adv) / 2
        y = cy * CELL * SS + CELL * SS * 0.06
        d.text((x, y), ch, font=f, fill=255)
        info[ch] = {'cell': [cx, cy], 'width': round(adv / (CELL * SS), 4), 'box': [round(v / (CELL * SS), 4) for v in box]}
    a = a.resize((cols * CELL, rows * CELL), Image.LANCZOS)
    img = Image.merge('RGBA', (a, a, a, a))
    img.save(os.path.join(OUT, 'glyphs.png'), optimize=True)
    with open(os.path.join(OUT, 'glyphs.json'), 'w') as fh:
        json.dump({'cols': cols, 'rows': rows, 'glyphs': info, 'space': 0.32}, fh, indent=0)


def main(which=''):
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ICONS, exist_ok=True)
    todo = list(TECH) if which == 'tech' else list(DECALS)
    for ident in todo:
        icon(ident, make(ident))
        print('decal', ident)
    if which != 'tech':
        glyphs()
    print(len(todo), 'decals into', OUT)


if __name__ == '__main__':
    import sys
    main(sys.argv[1] if len(sys.argv) > 1 else '')
