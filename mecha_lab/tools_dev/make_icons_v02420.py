"""0.24.20 pictures for the new tools and Base Mesh profiles - same style as make_icons.py / make_icons_v02417.py:
Creature Base Mesh, Creature Plate, Belt Maker, Creature Spike, Creature Scales, Scale Brush, Bridge Patch,
Flower Plate, Surface Curve; profiles Puff, Ridge, Pillow, Cushion; 0.24.21 sculpt brush tiles (Draw, Clay Strips,
Inflate, Grab, Smooth, Crease).

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

    # 0.24.21 sculpt brush tiles: a surface line (side view) and what the brush does to it
    def sculpt_base(d):
        d.line((70, 330, 442, 330), fill=DIM, width=W)

    def sculpt_draw():
        img, d = canvas()
        pts = [(80 + 352 * t, 330 - 120 * math.exp(-((t - 0.5) / 0.16) ** 2)) for t in (i / 40.0 for i in range(41))]
        d.line(pts, fill=ACC, width=W, joint='curve')
        return img
    out['sculpt_draw'] = sculpt_draw

    def sculpt_clay():
        img, d = canvas()
        sculpt_base(d)
        for k, y in enumerate((300, 268, 236)):
            d.rounded_rectangle((120 + k * 30, y - 22, 392 - k * 30, y + 6), radius=14, fill=(255, 158, 40, 160 + 30 * k))
        return img
    out['sculpt_clay'] = sculpt_clay

    def sculpt_inflate():
        img, d = canvas()
        poly(d, circle_pts(256, 270, 120), ACC, fill=(255, 158, 40, 70))
        for a in range(0, 360, 45):
            r = math.radians(a)
            d.line((256 + 150 * math.cos(r), 270 + 150 * math.sin(r), 256 + 200 * math.cos(r),
                    270 + 200 * math.sin(r)), fill=FG, width=16)
        return img
    out['sculpt_inflate'] = sculpt_inflate

    def sculpt_grab():
        img, d = canvas()
        pts = [(80 + 352 * t, 360 - 170 * math.exp(-((t - 0.6) / 0.2) ** 2)) for t in (i / 40.0 for i in range(41))]
        d.line(pts, fill=CY, width=W, joint='curve')
        poly(d, [(330, 130), (330, 60), (300, 90)], FG, width=16, closed=False)
        poly(d, [(330, 60), (360, 90)], FG, width=16, closed=False)
        return img
    out['sculpt_grab'] = sculpt_grab

    def sculpt_smooth():
        img, d = canvas()
        rough = [(80 + 352 * t, 230 + 26 * math.sin(t * 40)) for t in (i / 60.0 for i in range(61))]
        d.line(rough, fill=DIM, width=12)
        d.line([(80, 330), (432, 330)], fill=GR, width=W)
        poly(d, [(256, 262), (256, 312)], FG, width=14, closed=False)
        poly(d, [(236, 292), (256, 312), (276, 292)], FG, width=14, closed=False)
        return img
    out['sculpt_smooth'] = sculpt_smooth

    def sculpt_crease():
        img, d = canvas()
        pts = [(80, 250), (200, 260), (256, 360), (312, 260), (432, 250)]
        d.line(pts, fill=PU, width=W, joint='curve')
        return img
    out['sculpt_crease'] = sculpt_crease
    # 0.24.28 Cape: a cloak hanging from the shoulders, folds and a pointed hem
    def cape():
        img, d = canvas()
        d.ellipse((216, 60, 296, 140), outline=DIM, width=14)                 # head
        pts = [(170, 160), (342, 160), (430, 430), (380, 410), (330, 450), (256, 415), (182, 450), (132, 410), (82, 430)]
        poly(d, pts, ACC, fill=(255, 158, 40, 90))
        for x0, x1 in ((222, 196), (290, 316)):
            d.line((x0, 180, x1, 420), fill=FG, width=12)                     # folds
        return img
    out['cape'] = cape

    # 0.24.29 Creature Hair: dreadlocks falling from a head, metal bands
    def hair():
        img, d = canvas()
        d.ellipse((176, 70, 336, 230), outline=DIM, width=14)                 # head
        for k, x0 in enumerate((190, 225, 262, 300, 330)):
            pts = [(x0 + 14 * math.sin(t * 2.2 + k), 120 + 330 * t) for t in (i / 20.0 for i in range(21))]
            d.line(pts, fill=ACC if k % 2 == 0 else GR, width=24, joint='curve')
            by = 250 + (k % 3) * 45
            t = (by + 10 - 120) / 330.0
            bx = x0 + 14 * math.sin(t * 2.2 + k)
            d.rounded_rectangle((bx - 17, by, bx + 17, by + 20), radius=6, fill=FG)   # band round the strand
        return img
    out['hair'] = hair

    # 0.24.31 Clothing: a T-shirt over pants
    def garment():
        img, d = canvas()
        shirt = [(196, 70), (316, 70), (420, 130), (390, 200), (340, 175), (340, 290), (172, 290), (172, 175),
                 (122, 200), (92, 130)]
        poly(d, shirt, ACC, fill=(255, 158, 40, 90))
        d.arc((222, 50, 290, 100), 0, 180, fill=FG, width=12)                  # neckline
        pants = [(180, 305), (332, 305), (340, 460), (276, 460), (256, 360), (236, 460), (172, 460)]
        poly(d, pants, CY, fill=(80, 200, 255, 70))
        return img
    out['garment'] = garment

    # 0.24.31 Hood: a pointed hood round a head, cowl over the shoulders
    def hood():
        img, d = canvas()
        pts = [(256, 50), (360, 150), (380, 290), (440, 340), (450, 420), (62, 420), (72, 340), (132, 290),
               (152, 150)]
        poly(d, pts, ACC, fill=(255, 158, 40, 90))
        d.ellipse((190, 150, 322, 300), fill=(20, 22, 28, 255), outline=FG, width=12)   # face opening
        return img
    out['hood'] = hood

    # 0.24.31 Scarf: wraps round a neck and two tails
    def scarf():
        img, d = canvas()
        d.ellipse((196, 40, 316, 160), outline=DIM, width=14)                 # head
        for y in (180, 230):
            d.rounded_rectangle((136, y, 376, y + 58), radius=28, outline=ACC, width=14, fill=(255, 158, 40, 90))
        poly(d, [(200, 280), (262, 280), (250, 460), (190, 450)], CY, fill=(80, 200, 255, 70))
        poly(d, [(280, 280), (330, 280), (350, 410), (300, 420)], CY, fill=(80, 200, 255, 70))
        return img
    out['scarf'] = scarf

    def concept_move():                       # 0.24.31 a lump pulled out of a surface + the drag arrow
        img, d = canvas()
        d.arc((60, 250, 452, 560), 200, 340, fill=DIM, width=W)
        poly(d, [(170, 300), (210, 170), (300, 130), (360, 190), (340, 300)], ACC, fill=(255, 158, 40, 90))
        d.line((300, 250, 420, 80), fill=CY, width=W)
        poly(d, [(420, 80), (370, 100), (410, 135)], CY, fill=CY)
        return img
    out['concept_move'] = concept_move

    def path_move():                          # 0.24.31 a square lump swept along a bent path
        img, d = canvas()
        d.arc((60, 300, 452, 600), 200, 340, fill=DIM, width=W)
        poly(d, [(150, 330), (150, 250), (330, 250), (330, 330)], DIM, width=8, closed=False)
        poly(d, [(150, 250), (150, 170), (250, 90), (330, 90), (330, 170), (330, 250)], ACC,
             fill=(255, 158, 40, 90))
        d.line((240, 300, 240, 210), fill=CY, width=W)
        d.line((240, 210, 300, 140), fill=CY, width=W)
        poly(d, [(330, 105), (280, 125), (318, 158)], CY, fill=CY)
        return img
    out['path_move'] = path_move

    def perforate():                          # 0.24.33 a plate with honeycomb holes
        img, d = canvas()
        d.rounded_rectangle((70, 90, 442, 422), radius=36, outline=DIM, width=W, fill=(120, 126, 140, 60))
        r = 34
        for j in range(4):
            for i in range(4 if j % 2 == 0 else 3):
                cx = 140 + i * 78 + (39 if j % 2 else 0)
                cy = 150 + j * 68
                pts = [(cx + r * math.cos(math.pi / 6 + k * math.pi / 3), cy + r * math.sin(math.pi / 6 + k * math.pi / 3))
                       for k in range(6)]
                poly(d, pts, ACC if (i + j) % 3 else CY, width=8, fill=(20, 22, 28, 255))
        return img
    out['perforate'] = perforate

    def surface_draw():                       # 0.24.33 a raised band drawn on a surface
        img, d = canvas()
        d.arc((50, 230, 462, 620), 200, 340, fill=DIM, width=W)
        poly(d, [(110, 300), (180, 250), (260, 270), (330, 220), (400, 250)], ACC, width=W + 22, closed=False)
        poly(d, [(110, 300), (180, 250), (260, 270), (330, 220), (400, 250)], (255, 210, 140, 255), width=8,
             closed=False)
        d.line((400, 250, 450, 120), fill=CY, width=W)
        return img
    out['surface_draw'] = surface_draw

    def cloth_brush():                        # 0.24.33 a wavy cloth strip
        img, d = canvas()
        d.arc((50, 230, 462, 620), 200, 340, fill=DIM, width=W)
        top = [(100 + 30 * i, 250 - 18 * math.sin(i * 1.3)) for i in range(11)]
        bot = [(x + 10, y + 70) for x, y in top]
        poly(d, top + bot[::-1], CY, width=10, fill=(80, 200, 255, 90))
        for i in range(1, 10, 2):
            d.line((top[i][0], top[i][1], bot[i][0], bot[i][1]), fill=CY, width=6)
        return img
    out['cloth_brush'] = cloth_brush
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
