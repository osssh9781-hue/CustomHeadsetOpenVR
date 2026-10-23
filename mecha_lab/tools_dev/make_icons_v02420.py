"""0.24.20 pictures for the new tools and Base Mesh profiles - same style as make_icons.py / make_icons_v02417.py:
Creature Base Mesh, Creature Plate, Belt Maker, Creature Spike, Creature Scales, Scale Brush, Bridge Patch,
Flower Plate, Surface Curve; profiles Puff, Ridge, Pillow, Cushion.

python make_icons_v02420.py <out dir>
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, CY, FG, GR, PU, W, canvas, circle_pts, poly, save  # noqa: E402

DIM = (120, 126, 140, 255)


def base_line(d, y=380):
    d.line((70, y, 442, y), fill=DIM, width=W)


def lens(cx, cy, rx, ry, n=72, pinch=0.18):
    return [(cx + rx * math.cos(a), cy + ry * math.sin(a) * (1 - pinch * math.cos(a) ** 8))
            for a in [i * 2 * math.pi / n for i in range(n)]]


def side_profile(d, top, color, fill):
    """A profile seen from the side, mirrored below the dashed drawing plane (y = 280)."""
    cy = 280
    up = [(x, cy - h) for x, h in top]
    down = [(x, cy + h) for x, h in reversed(top)]
    poly(d, up + down, color, fill=fill)
    for x in range(70, 442, 44):
        d.line((x, cy, x + 22, cy), fill=FG, width=10)


def icons():
    out = {}

    def profile_puff():
        img, d = canvas()
        poly(d, lens(256, 280, 168, 110), ACC, fill=(255, 158, 40, 90))
        for x in range(70, 442, 44):
            d.line((x, 280, x + 22, 280), fill=FG, width=10)
        return img
    out['profile_puff'] = profile_puff

    def profile_ridge():
        img, d = canvas()
        top = [(90, 0), (120, 40), (256, 120), (392, 40), (422, 0)]
        side_profile(d, top, ACC, (255, 158, 40, 90))
        return img
    out['profile_ridge'] = profile_ridge

    def profile_pillow():
        img, d = canvas()
        top = [(90 + 30 * (1 - math.cos(a)), 70 * math.sin(a)) for a in [i * math.pi / 2 / 10 for i in range(11)]]
        top += [(422 - 30 * (1 - math.cos(a)), 70 * math.sin(a)) for a in [i * math.pi / 2 / 10 for i in range(10, -1, -1)]]
        side_profile(d, top, ACC, (255, 158, 40, 90))
        return img
    out['profile_pillow'] = profile_pillow

    def profile_cushion():
        img, d = canvas()
        top = []
        for i in range(41):
            t = i / 40.0
            x = 90 + 332 * t
            e = min(t, 1 - t) / 0.3
            h = 80 * math.sqrt(max(0.0, 1 - (1 - min(e, 1.0)) ** 2)) * (0.85 + 0.15 * math.sqrt(min(t, 1 - t) * 2))
            top.append((x, h))
        side_profile(d, top, PU, (205, 120, 255, 80))
        return img
    out['profile_cushion'] = profile_cushion

    def cbase():
        # a puffy creature blob outline (Creature Base Mesh)
        img, d = canvas()
        pts = []
        for i in range(72):
            a = i * 2 * math.pi / 72
            r = 150 + 28 * math.sin(3 * a) + 14 * math.cos(5 * a)
            pts.append((256 + r * math.cos(a), 266 + 0.8 * r * math.sin(a)))
        poly(d, pts, ACC, fill=(255, 158, 40, 90))
        d.arc((170, 190, 290, 290), 200, 300, fill=FG, width=16)       # highlight: it is round
        return img
    out['cbase'] = cbase

    def cplate():
        img, d = canvas()
        base_line(d)
        top = [(110 + 292 * t, 380 - 150 * math.sin(math.pi * t) ** 0.7) for t in (i / 30.0 for i in range(31))]
        poly(d, top, GR, closed=False)
        return img
    out['cplate'] = cplate

    def belt():
        # a strap around a body with a buckle
        img, d = canvas()
        d.ellipse((110, 90, 402, 440), outline=DIM, width=W)
        d.arc((90, 220, 422, 340), 0, 180, fill=CY, width=46)
        d.rectangle((226, 306, 286, 352), outline=FG, width=14)
        return img
    out['belt'] = belt

    def spike():
        img, d = canvas()
        base_line(d)
        for x0, h, lean in ((110, 150, 30), (210, 230, 40), (320, 180, 25)):
            poly(d, [(x0, 380), (x0 + 30 + lean, 380 - h), (x0 + 80, 380)], ACC, fill=(255, 158, 40, 90))
        return img
    out['spike'] = spike

    def scales():
        # overlapping scales in rows
        img, d = canvas()
        for row, y in enumerate((170, 260, 350)):
            for k in range(4):
                x = 110 + k * 96 + (48 if row % 2 else 0)
                pts = [(x - 52, y - 40), (x + 52, y - 40), (x + 40, y + 10), (x, y + 40), (x - 40, y + 10)]
                if x + 52 > 450:
                    continue
                poly(d, pts, GR, width=16, fill=(38, 41, 48, 255))
        return img
    out['scales'] = scales

    def scale_brush():
        # pebbles packed close in a lasso
        img, d = canvas()
        d.ellipse((76, 86, 436, 436), outline=DIM, width=14)
        rng = [(170, 190, 52), (270, 170, 46), (360, 230, 44), (150, 300, 50), (250, 270, 44), (340, 330, 46),
               (230, 370, 40)]
        for cx, cy, r in rng:
            pts = [(cx + r * (1 + 0.15 * math.sin(3 * a + cx)) * math.cos(a),
                    cy + r * 0.85 * (1 + 0.15 * math.cos(2 * a + cy)) * math.sin(a)) for a in
                   [i * 2 * math.pi / 36 for i in range(36)]]
            poly(d, pts, GR, width=14, fill=(110, 230, 120, 80))
        return img
    out['scale_brush'] = scale_brush

    def bridge_patch():
        # two lumps joined by a smooth neck
        img, d = canvas()
        d.ellipse((150, 70, 362, 230), outline=FG, width=W)
        d.ellipse((120, 290, 392, 460), outline=FG, width=W)
        left = [(196, 200), (186, 260), (176, 320)]
        right = [(316, 200), (326, 260), (336, 320)]
        poly(d, left + list(reversed(right)), ACC, fill=(255, 158, 40, 110))
        return img
    out['bridge_patch'] = bridge_patch

    def flower():
        # a part attached at the root that lifts and curls (side view)
        img, d = canvas()
        base_line(d)
        pts = []
        for i in range(41):
            t = i / 40.0
            a = math.radians(70) * min(1.0, t / 0.35) - math.radians(140) * t ** 1.3
            pts.append(a)
        x, y = 110.0, 380.0
        line = [(x, y)]
        for a in pts[1:]:
            x += 9 * math.cos(a)
            y -= 9 * math.sin(a)
            line.append((x, y))
        d.line(line, fill=PU, width=40, joint='curve')
        return img
    out['flower'] = flower

    def surface_curve():
        # a curve lying on a surface
        img, d = canvas()
        d.arc((60, 180, 452, 560), 200, 340, fill=DIM, width=W)
        pts = [(120 + 272 * t, 300 - 60 * math.sin(math.pi * t) + 30 * math.sin(3 * math.pi * t)) for t in
               (i / 40.0 for i in range(41))]
        d.line(pts, fill=CY, width=44, joint='curve')
        for x, y in (pts[0], pts[20], pts[40]):
            d.ellipse((x - 18, y - 18, x + 18, y + 18), fill=FG)
        return img
    out['surface_curve'] = surface_curve
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
