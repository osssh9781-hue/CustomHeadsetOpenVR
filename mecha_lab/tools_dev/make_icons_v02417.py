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
        img, d = canvas()
        d.rectangle((110, 150, 300, 380), outline=FG, width=W)               # the mesh
        for x in range(300, 420, 40):                                          # hidden half: dashed
            d.line((x, 150, x + 20, 150), fill=DIM, width=W)
            d.line((x, 380, x + 20, 380), fill=DIM, width=W)
        for y in range(150, 380, 40):
            d.line((410, y, 410, y + 20), fill=DIM, width=W)
        for x in range(240, 440, 44):                                          # the drawn box
            d.line((x, 110, x + 24, 110), fill=ACC, width=18)
            d.line((x, 420, x + 24, 420), fill=ACC, width=18)
        for y in range(110, 420, 44):
            d.line((240, y, 240, y + 24), fill=ACC, width=18)
            d.line((440, y, 440, y + 24), fill=ACC, width=18)
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
        img, d = canvas()
        d.ellipse((126, 126, 386, 386), outline=FG, width=W)
        d.ellipse((176, 176, 336, 336), outline=DIM, width=14)
        d.line((206, 256, 306, 256), fill=ACC, width=W + 6)
        d.line((256, 206, 256, 306), fill=ACC, width=W + 6)
        return img
    out['screw'] = screw

    def cloth():
        img, d = canvas()
        shirt = [(196, 110), (226, 140), (286, 140), (316, 110), (420, 160), (390, 240), (350, 220), (350, 410),
                 (162, 410), (162, 220), (122, 240), (92, 160)]
        poly(d, shirt, PU, fill=(205, 120, 255, 60))
        d.arc((222, 96, 290, 164), start=20, end=160, fill=PU, width=18)       # collar
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
