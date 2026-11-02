"""0.24.95 The decal library for Mecha Lab's Decals (user: picked "데칼 - 번호, 경고 줄무늬, 로고를 표면에 붙이는 기능").

Every decal is a two-tone mask, so its colours are chosen in Blender: RGB white = Color 1, black = Color 2, alpha =
where the decal is.  ``addon/mecha_lab/decals/<ID>.png`` (512 px on the long side) and its tile picture
``addon/mecha_lab/mech_icons/decal_<ID>.png`` (128 px, the default colours on dark grey).  The letters for Text
decals: ``decals/glyphs.png`` (an 8 x 6 atlas, 128 px cells, DejaVu Sans Bold - Bitstream Vera licence, rendered
shapes only) + ``decals/glyphs.json`` (each character's cell and width).

    python3 tools_dev/make_decals.py          (numpy + Pillow)
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
GLYPHS = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789-./#:+!?'
CELL = 128


def font(px):
    return ImageFont.truetype(FONT, int(px))


def canvas(ratio, long=512):
    w, h = (long, int(long / ratio)) if ratio >= 1 else (int(long * ratio), long)
    w, h = w * SS, h * SS
    # two layers: coverage (alpha) and primary (white = colour 1)
    a = Image.new('L', (w, h), 0)
    p = Image.new('L', (w, h), 0)
    return a, p, ImageDraw.Draw(a), ImageDraw.Draw(p), w, h


def text_center(draw, w, h, s, px, cx=None, cy=None, fill=255):
    f = font(px)
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


def make(ident):
    label, ratio, _c1, _c2 = DECALS[ident]
    a, p, da, dp, w, h = canvas(ratio)
    if ident in ('HAZARD', 'HAZARD_RW'):
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


def main():
    os.makedirs(OUT, exist_ok=True)
    os.makedirs(ICONS, exist_ok=True)
    for ident in DECALS:
        icon(ident, make(ident))
        print('decal', ident)
    glyphs()
    print(len(DECALS), 'decals + glyphs into', OUT)


if __name__ == '__main__':
    main()
