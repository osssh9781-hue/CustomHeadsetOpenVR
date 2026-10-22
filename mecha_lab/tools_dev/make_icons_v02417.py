"""0.24.17 own pictures for the left tool list entries that shared one (extract / cable / cut):
Box Hide, Armor Plate, Plate Detail 1 / 2 / 3, Screw Stamp, Cloth Plate (a shirt), Mesh Curve, Line Curve.

python make_icons_v02417.py <out dir>     (same style as make_icons.py)
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, CY, FG, GR, PU, W, canvas, circle_pts, dots, poly, save  # noqa: E402

DIM = (120, 126, 140, 255)


def base_line(d, y=380):
    d.line((70, y, 442, y), fill=DIM, width=W)


def icons():
    out = {}

    def hide():
        # a box with one corner block hidden: the hidden part is only a dashed orange outline
        img, d = canvas()
        bg = (38, 41, 48, 255)
        # box: front square + top + right side (oblique)
        F = [(110, 200), (330, 200), (330, 420), (110, 420)]
        T = [(110, 200), (190, 120), (410, 120), (330, 200)]
        Rs = [(330, 200), (410, 120), (410, 340), (330, 420)]
        for face, shade in ((F, (70, 74, 84, 255)), (T, (92, 96, 108, 255)), (Rs, (58, 62, 72, 255))):
            d.polygon(face, fill=shade)
            poly(d, face, FG, width=16)
        # hidden corner block (top-right-front): erase it, outline dashed
        blk = [(250, 200), (330, 200), (330, 280), (250, 280)]
        d.polygon([(250, 200), (330, 200), (410, 120), (330, 120)], fill=bg)
        d.polygon([(330, 200), (410, 120), (410, 200), (330, 280)], fill=bg)
        d.polygon(blk, fill=bg)
        inner = [(250, 200), (250, 280), (330, 280)]
        poly(d, inner, FG, width=16, closed=False)
        poly(d, [(250, 200), (330, 120)], FG, width=16, closed=False)
        poly(d, [(330, 280), (410, 200)], FG, width=16, closed=False)

        def dash(p0, p1, n=4):
            for k in range(n):
                t0, t1 = k / n, (k + 0.55) / n
                d.line((p0[0] + (p1[0] - p0[0]) * t0, p0[1] + (p1[1] - p0[1]) * t0,
                        p0[0] + (p1[0] - p0[0]) * t1, p0[1] + (p1[1] - p0[1]) * t1), fill=ACC, width=14)
        for p0, p1 in (((250, 200), (330, 200)), ((330, 200), (330, 280)), ((330, 200), (410, 120)),
                       ((330, 120), (410, 120)), ((410, 120), (410, 200)), ((250, 200), (330, 120))):
            dash(p0, p1)
        return img
    out['hide'] = hide

    def armor():
        img, d = canvas()
        body = [(70, 400), (140, 330), (256, 300), (372, 330), (442, 400)]
        poly(d, body, DIM, closed=False)
        plate = [(140, 300), (256, 262), (372, 300), (360, 240), (256, 196), (152, 240)]
        poly(d, plate, CY, fill=(70, 200, 255, 70))
        return img
    out['armor'] = armor

    def detail1():
        img, d = canvas()
        base_line(d)
        prof = [(80, 380), (110, 380), (110, 230), (170, 230), (170, 280), (230, 280), (230, 320), (282, 320),
                (282, 280), (342, 280), (342, 230), (402, 230), (402, 380), (432, 380)]
        poly(d, prof, ACC, closed=False)
        return img
    out['detail1'] = detail1

    def detail2():
        img, d = canvas()
        base_line(d)
        pts = []
        for i in range(41):
            t = i / 40.0
            x = 80 + 352 * t
            h = 0.5 - 0.5 * math.cos(2 * math.pi * min(1.0, max(0.0, (t - 0.08) / 0.84)))
            h = min(1.0, h * 1.6)
            pts.append((x, 380 - 170 * h))
        poly(d, pts, GR, closed=False)
        return img
    out['detail2'] = detail2

    def detail3():
        img, d = canvas()
        base_line(d)
        poly(d, [(80, 380), (130, 380), (130, 220), (382, 220), (382, 380), (432, 380)], CY, closed=False)
        return img
    out['detail3'] = detail3

    def screw():
        # a round screw head sitting on a plate (seen from above at an angle) with a cross slot
        img, d = canvas()
        d.polygon([(60, 330), (190, 230), (452, 230), (322, 330)], fill=(70, 74, 84, 255))
        poly(d, [(60, 330), (190, 230), (452, 230), (322, 330)], DIM, width=14)
        d.polygon([(60, 330), (322, 330), (322, 360), (60, 360)], fill=(52, 56, 64, 255))
        cx, cy = 256, 250
        d.ellipse((cx - 120, cy - 30, cx + 120, cy + 70), fill=(52, 56, 64, 255))       # head side
        d.rectangle((cx - 120, cy - 70, cx + 120, cy + 20), fill=(52, 56, 64, 255))
        d.ellipse((cx - 120, cy - 120, cx + 120, cy - 20), fill=(205, 210, 220, 255))   # head top
        d.arc((cx - 120, cy - 30, cx + 120, cy + 70), start=0, end=180, fill=FG, width=14)
        d.line((cx - 120, cy - 70, cx - 120, cy + 20), fill=FG, width=14)
        d.line((cx + 120, cy - 70, cx + 120, cy + 20), fill=FG, width=14)
        d.ellipse((cx - 120, cy - 120, cx + 120, cy - 20), outline=FG, width=14)
        d.line((cx - 76, cy - 70, cx + 76, cy - 70), fill=ACC, width=24)                 # cross slot (top
        d.line((cx, cy - 104, cx, cy - 36), fill=ACC, width=24)                          # seen at an angle)
        return img
    out['screw'] = screw

    def cloth():
        # a padded jacket: sleeves, zip down the middle, quilted (puffed) bands
        img, d = canvas()
        body = [(178, 112), (218, 100), (256, 136), (294, 100), (334, 112), (418, 170), (440, 330), (392, 340),
                (370, 238), (366, 420), (146, 420), (142, 238), (120, 340), (72, 330), (94, 170)]
        d.polygon(body, fill=(120, 70, 170, 255))
        for y in (190, 250, 310, 370):                                    # quilting: puffed bands
            d.line((150, y, 362, y), fill=(205, 120, 255, 255), width=10)
        for y, x0, x1 in ((230, 96, 140), (280, 104, 140), (230, 372, 416), (280, 372, 410)):
            d.line((x0, y, x1, y), fill=(205, 120, 255, 255), width=10)
        poly(d, body, PU, width=18)
        d.line((256, 136, 256, 420), fill=FG, width=12)                   # zip
        poly(d, [(218, 100), (256, 160), (294, 100)], FG, width=14, closed=False)   # collar
        return img
    out['cloth'] = cloth

    def tube():
        img, d = canvas()
        pts = [(110 + 292 * t, 256 + 110 * math.sin(math.pi * 2 * t) * (1 - 0.2 * t)) for t in
               (i / 40.0 for i in range(41))]
        d.line(pts, fill=FG, width=70, joint='curve')
        d.line(pts, fill=(38, 41, 48, 255), width=26, joint='curve')
        dots(d, [pts[0], pts[20], pts[40]], ACC, r=26)
        return img
    out['tube'] = tube

    def line_curve():
        img, d = canvas()
        pts = [(100 + 312 * t, 256 + 110 * math.sin(math.pi * 2 * t)) for t in (i / 60.0 for i in range(61))]
        d.line(pts, fill=DIM, width=10, joint='curve')
        for k in range(0, 61, 10):
            x, y = pts[k]
            d.ellipse((x - 30, y - 30, x + 30, y + 30), outline=CY, width=16)
        return img
    out['line_curve'] = line_curve
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
