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
        # plate set look: side view on the base line - a dome screw head with its slot
        img, d = canvas()
        base_line(d)
        head = [(120, 380)] + [(256 + 136 * math.cos(math.pi * (1 - i / 32.0)),
                                 380 - 160 * math.sin(math.pi * (1 - i / 32.0))) for i in range(33)] + [(392, 380)]
        poly(d, head, ACC, closed=False)
        d.line((256, 222, 256, 290), fill=ACC, width=W)                    # the slot
        return img
    out['screw'] = screw

    def cloth():
        # plate set look: side view on the base line - a padded panel puffing up between pinched seams
        img, d = canvas()
        base_line(d)
        pts = [(80, 380)]
        for i in range(61):                                                 # soft pillow: rounded shoulders,
            t = i / 60.0                                                    # a gentle wave on top
            x = 100 + 312 * t
            edge = math.sin(math.pi * t) ** 0.45
            h = edge * (150 + 14 * math.cos(math.pi * 4 * t))
            pts.append((x, 380 - h))
        pts += [(432, 380)]
        poly(d, pts, PU, closed=False)
        for x in range(146, 380, 46):                                       # stitches
            d.line((x, 345, x + 22, 345), fill=DIM, width=10)
        return img
    out['cloth'] = cloth

    def cloth_shirt():
        # the same line look as the plate set: a shirt drawn with one stroke on the base line
        img, d = canvas()
        base_line(d)
        shirt = [(200, 120), (232, 146), (280, 146), (312, 120), (402, 166), (378, 232), (344, 216), (344, 380),
                 (168, 380), (168, 216), (134, 232), (110, 166)]
        poly(d, shirt, PU)
        return img
    out['cloth_shirt'] = cloth_shirt

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
