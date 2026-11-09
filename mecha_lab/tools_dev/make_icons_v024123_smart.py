"""0.24.123 picture for Smart Move (same style as make_icons.py): a small part lifted off a slab, its origin dot, a
drop line to the point on the surface it goes to, and a turn arrow round the origin (the 3D mouse).

python make_icons_v024123_smart.py <out dir>
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, CY, FG, W, canvas, circle_pts, poly, save  # noqa: E402


def icons():
    out = {}

    def smart_move():
        img, d = canvas()
        poly(d, [(60, 330), (256, 250), (452, 330), (256, 410)], FG, width=W)              # the slab's top
        d.line((60, 330, 60, 410), fill=FG, width=W)
        d.line((452, 330, 452, 410), fill=FG, width=W)
        poly(d, [(60, 410), (256, 490), (452, 410)], FG, width=W, closed=False)
        # the part, held above the slab (a tilted little box)
        top = [(206, 118), (276, 90), (336, 122), (266, 150)]
        poly(d, top, ACC, width=18, fill=(255, 158, 40, 120))
        poly(d, [(206, 118), (206, 178), (266, 212), (266, 150)], ACC, width=18, fill=(255, 158, 40, 70))
        poly(d, [(266, 150), (336, 122), (336, 182), (266, 212)], ACC, width=18, fill=(255, 158, 40, 90))
        ox, oy = 268, 150                                                                  # its origin
        d.ellipse((ox - 20, oy - 20, ox + 20, oy + 20), fill=CY)
        # the drop to the surface point (dashed) and the point
        px, py = 300, 318
        for k in range(5):
            t0, t1 = k / 5 + 0.05, k / 5 + 0.15
            d.line((ox + (px - ox) * t0, oy + 40 + (py - oy - 40) * t0, ox + (px - ox) * t1, oy + 40 + (py - oy - 40) * t1),
                   fill=CY, width=12)
        d.ellipse((px - 22, py - 22, px + 22, py + 22), outline=CY, width=12)
        # the turn arrow round the origin (the 3D mouse)
        arc = circle_pts(ox, oy, 96, n=40, start=math.radians(200), arc=math.radians(250))
        poly(d, arc, FG, width=16, closed=False)
        ex, ey = arc[-1]                                                                   # (the bottom, going left)
        poly(d, [(ex - 40, ey + 2), (ex + 8, ey - 30), (ex + 8, ey + 30)], FG, width=8, fill=FG)
        return img
    out['smart_move'] = smart_move
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
