"""0.24.127 pictures for the 3D mouse settings table, in the style of 3DxWare's Speed panel (a grey line drawing of the
cap with arrows): left / right, forward / back, up / down (pull / push), tilt, spin, roll.

python make_icons_v024127_ndof.py <out dir>
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

S, OUT = 512, 64
LINE = (235, 236, 240, 255)
DIM = (150, 154, 162, 255)
W = 22


def canvas():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    return img, ImageDraw.Draw(img)


def cap(d, cx=256, cy=300, rx=120, ry=44, h=70):
    """The 3D mouse's cap seen from the front, a little from above: a short cylinder."""
    d.ellipse((cx - rx, cy + h - ry, cx + rx, cy + h + ry), outline=LINE, width=W)         # the base rim
    d.rectangle((cx - rx - W // 2 + 2, cy, cx + rx + W // 2 - 2, cy + h), fill=(0, 0, 0, 0))
    d.line((cx - rx, cy, cx - rx, cy + h), fill=LINE, width=W)
    d.line((cx + rx, cy, cx + rx, cy + h), fill=LINE, width=W)
    d.ellipse((cx - rx, cy - ry, cx + rx, cy + ry), fill=(0, 0, 0, 0), outline=LINE, width=W)   # the top


def arrow(d, a, b, width=W, head=34, color=LINE):
    d.line((a, b), fill=color, width=width)
    ang = math.atan2(b[1] - a[1], b[0] - a[0])
    for s_ in (-1, 1):
        d.line((b, (b[0] - head * math.cos(ang + s_ * 0.5), b[1] - head * math.sin(ang + s_ * 0.5))), fill=color, width=width)


def arc_arrow(d, box, start, end, width=W, color=LINE, head_at_end=True):
    d.arc(box, start, end, fill=color, width=width)
    x0, y0, x1, y1 = box
    cx, cy, rx, ry = (x0 + x1) / 2, (y0 + y1) / 2, (x1 - x0) / 2, (y1 - y0) / 2
    t = math.radians(end if head_at_end else start)
    tip = (cx + rx * math.cos(t), cy + ry * math.sin(t))
    sgn = 1.0 if head_at_end else -1.0
    tangent = (-rx * math.sin(t) * sgn, ry * math.cos(t) * sgn)
    n = math.hypot(*tangent) or 1.0
    tangent = (tangent[0] / n, tangent[1] / n)
    base = (tip[0] - tangent[0] * 36, tip[1] - tangent[1] * 36)
    normal = (-tangent[1], tangent[0])
    d.polygon([tip, (base[0] + normal[0] * 20, base[1] + normal[1] * 20), (base[0] - normal[0] * 20, base[1] - normal[1] * 20)], fill=color)


def icons():
    out = {}

    def lr():
        img, d = canvas()
        cap(d)
        arrow(d, (256, 190), (70, 190))
        arrow(d, (256, 190), (442, 190))
        return img

    def fb():
        img, d = canvas()
        cap(d)
        arrow(d, (256, 200), (352, 56))          # away from you (forward) ...
        arrow(d, (256, 200), (160, 344 - 100))   # ... and back
        return img

    def ud():
        img, d = canvas()
        cap(d, cy=330)
        arrow(d, (256, 200), (256, 50))          # pull up ...
        arrow(d, (256, 200), (256, 290))         # ... push down
        return img

    def tilt():
        img, d = canvas()
        cap(d)
        box = (150, 60, 362, 230)                # rocking front / back: an arc over the top, both ways
        arc_arrow(d, box, 195, 345)
        arc_arrow(d, box, 195, 345, head_at_end=False)
        return img

    def spin():
        img, d = canvas()
        cap(d)
        arc_arrow(d, (96, 140, 416, 236), 40, 320)          # round the top
        return img

    def roll():
        img, d = canvas()
        cap(d)
        box = (40, 90, 472, 320)                 # rocking left / right: a wide arc, both ways
        arc_arrow(d, box, 205, 335)
        arc_arrow(d, box, 205, 335, head_at_end=False)
        return img
    out['ndof_lr'], out['ndof_fb'], out['ndof_ud'] = lr, fb, ud
    out['ndof_tilt'], out['ndof_spin'], out['ndof_roll'] = tilt, spin, roll
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        fn().resize((OUT, OUT), Image.LANCZOS).save(dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
