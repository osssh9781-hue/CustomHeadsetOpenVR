"""Generate the Mecha Lab tool / shape icons (128 px PNG) with Pillow.

Run with any Python that has Pillow:  python make_icons.py <addon icons dir>
The icons are original simple glyphs (no third-party artwork).
"""
import math
import sys
from pathlib import Path

from PIL import Image, ImageDraw

S = 512                    # drawn at 4x, downsampled for anti-aliasing
OUT = 128
BG = (38, 41, 48, 255)
FG = (230, 232, 238, 255)
ACC = (255, 158, 40, 255)  # orange = cut/active part
CY = (70, 200, 255, 255)
GR = (110, 230, 120, 255)
PU = (205, 120, 255, 255)
W = 26


def canvas():
    img = Image.new('RGBA', (S, S), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((8, 8, S - 8, S - 8), radius=72, fill=BG)
    return img, d


def poly(d, pts, color, width=W, closed=True, fill=None):
    pts = [(float(x), float(y)) for x, y in pts]
    if fill:
        d.polygon(pts, fill=fill)
    seq = pts + ([pts[0]] if closed else [])
    d.line(seq, fill=color, width=width, joint='curve')


def dots(d, pts, color, r=22):
    for x, y in pts:
        d.ellipse((x - r, y - r, x + r, y + r), fill=color)


def circle_pts(cx, cy, r, n=64, start=0.0, arc=2 * math.pi):
    return [(cx + r * math.cos(start + arc * i / n), cy + r * math.sin(start + arc * i / n)) for i in range(n)]


def save(img, path):
    img.resize((OUT, OUT), Image.LANCZOS).save(path)


def icons():
    out = {}

    def cut():
        img, d = canvas()
        d.rectangle((96, 120, 416, 400), outline=FG, width=W)
        poly(d, [(170, 190), (330, 170), (350, 300), (230, 340), (160, 280)], ACC, fill=(255, 158, 40, 90))
        return img
    out['cut'] = cut

    def split():
        img, d = canvas()
        poly(d, [(90, 130), (230, 130), (200, 390), (90, 390)], FG, fill=(230, 232, 238, 60))
        poly(d, [(282, 130), (422, 130), (422, 390), (252, 390)], GR, fill=(110, 230, 120, 70))
        d.line([(256, 80), (226, 440)], fill=ACC, width=14)
        return img
    out['split'] = split

    def boolean():
        img, d = canvas()
        d.rectangle((90, 150, 320, 380), outline=FG, width=W)
        d.ellipse((210, 110, 430, 330), outline=ACC, width=W)
        return img
    out['boolean'] = boolean

    def fuse():
        img, d = canvas()
        d.ellipse((80, 160, 280, 360), outline=FG, width=W)
        d.ellipse((230, 160, 430, 360), outline=FG, width=W)
        d.arc((200, 150, 310, 370), 250, 290, fill=ACC, width=W + 8)
        d.arc((200, 150, 310, 370), 70, 110, fill=ACC, width=W + 8)
        return img
    out['fuse'] = fuse

    def mirror():
        img, d = canvas()
        poly(d, [(230, 120), (230, 390), (90, 390)], FG, fill=(230, 232, 238, 70))
        poly(d, [(282, 120), (282, 390), (422, 390)], CY, fill=(70, 200, 255, 70))
        for y in range(90, 430, 50):
            d.line([(256, y), (256, y + 26)], fill=ACC, width=12)
        return img
    out['mirror'] = mirror

    def mask():
        img, d = canvas()
        d.rectangle((96, 140, 416, 400), outline=FG, width=W)
        poly(d, [(140, 330), (200, 190), (300, 170), (370, 260), (300, 350)], PU, fill=(205, 120, 255, 110))
        return img
    out['mask'] = mask

    def array():
        img, d = canvas()
        pts = [(100 + i * 78, 340 - 160 * math.sin(i / 4 * math.pi)) for i in range(5)]
        d.line(pts, fill=CY, width=12, joint='curve')
        for x, y in pts:
            d.rectangle((x - 30, y - 30, x + 30, y + 30), outline=FG, width=18)
        return img
    out['array'] = array

    def radial():
        img, d = canvas()
        d.ellipse((150, 150, 362, 362), outline=CY, width=12)
        for x, y in circle_pts(256, 256, 150, 8):
            d.rectangle((x - 26, y - 26, x + 26, y + 26), outline=FG, width=16)
        return img
    out['radial'] = radial

    def panel():
        img, d = canvas()
        d.rectangle((90, 110, 422, 400), outline=FG, width=W)
        pts = [(130, 330), (200, 220), (300, 300), (380, 170)]
        d.line(pts, fill=ACC, width=W, joint='curve')
        dots(d, pts, CY, 16)
        return img
    out['panel'] = panel

    def pose():
        img, d = canvas()
        d.line([(130, 400), (220, 250), (360, 170)], fill=FG, width=W + 10, joint='curve')
        dots(d, [(130, 400), (220, 250), (360, 170)], ACC, 30)
        d.arc((150, 170, 300, 330), 200, 320, fill=CY, width=12)
        return img
    out['pose'] = pose

    def surface():
        img, d = canvas()
        d.arc((60, 250, 452, 560), 200, 340, fill=FG, width=W)
        d.rectangle((200, 150, 312, 260), outline=ACC, width=W)
        d.line([(256, 270), (256, 300)], fill=CY, width=14)
        return img
    out['surface'] = surface

    def assets():
        img, d = canvas()
        poly(d, [(256, 100), (410, 180), (410, 350), (256, 430), (102, 350), (102, 180)], FG)
        d.line([(102, 180), (256, 260), (410, 180)], fill=FG, width=W)
        d.line([(256, 260), (256, 430)], fill=ACC, width=W)
        return img
    out['assets'] = assets

    def remesh():
        img, d = canvas()
        for i in range(5):
            x = 110 + i * 73
            d.line([(x, 110), (x, 402)], fill=FG, width=12)
            d.line([(110, x), (402, x)], fill=FG, width=12)
        d.ellipse((180, 180, 332, 332), outline=ACC, width=W)
        return img
    out['remesh'] = remesh

    def live():
        img, d = canvas()
        d.line([(120, 270), (220, 370), (400, 150)], fill=GR, width=W + 14, joint='curve')
        return img
    out['live'] = live

    # ---- shapes --------------------------------------------------------

    def lasso():
        img, d = canvas()
        pts = [(120, 330), (170, 140), (300, 120), (400, 230), (330, 390), (220, 340)]
        poly(d, pts, ACC)
        dots(d, pts, FG, 18)
        return img
    out['lasso'] = lasso

    def curve_lasso():
        img, d = canvas()
        pts = circle_pts(256, 256, 150, 64)
        pts = [(x + 30 * math.sin(3 * i / 64 * 2 * math.pi), y) for i, (x, y) in enumerate(pts)]
        poly(d, pts, ACC)
        d.line([(150, 120), (256, 106), (362, 120)], fill=CY, width=10)
        dots(d, [(150, 120), (362, 120)], CY, 14)
        dots(d, [(256, 106)], FG, 18)
        return img
    out['curve_lasso'] = curve_lasso

    def rect():
        img, d = canvas()
        d.rectangle((110, 150, 402, 362), outline=ACC, width=W)
        return img
    out['rect'] = rect

    def circle():
        img, d = canvas()
        d.ellipse((110, 110, 402, 402), outline=ACC, width=W)
        return img
    out['circle'] = circle

    def ellipse():
        img, d = canvas()
        d.ellipse((80, 160, 432, 352), outline=ACC, width=W)
        return img
    out['ellipse'] = ellipse

    def stroke():
        img, d = canvas()
        pts = [(110 + i * 4.8, 256 + 90 * math.sin(i / 10) - 40 * math.cos(i / 4)) for i in range(62)]
        d.line(pts, fill=ACC, width=W + 6, joint='curve')
        return img
    out['stroke'] = stroke

    def custom():
        img, d = canvas()
        star = []
        for i in range(10):
            r = 165 if i % 2 == 0 else 72
            a = -math.pi / 2 + i * math.pi / 5
            star.append((256 + r * math.cos(a), 270 + r * math.sin(a)))
        poly(d, star, ACC, fill=(255, 158, 40, 80))
        d.ellipse((236, 250, 276, 290), fill=BG)
        return img
    out['custom'] = custom

    def base():
        img, d = canvas()
        poly(d, [(130, 330), (180, 160), (330, 140), (390, 260), (300, 360)], FG, width=14)
        poly(d, [(130, 400), (180, 230), (330, 210), (390, 330), (300, 430)], ACC, fill=(255, 158, 40, 90))
        for (x0, y0), (x1, y1) in (((130, 330), (130, 400)), ((390, 260), (390, 330)), ((300, 360), (300, 430))):
            d.line([(x0, y0), (x1, y1)], fill=FG, width=12)
        return img
    out['base'] = base

    def loft():
        img, d = canvas()
        for k, col in enumerate((FG, CY, FG)):
            y0 = 140 + k * 115
            pts = [(100 + i * 31, y0 + 40 * math.sin(i / 3 + k)) for i in range(11)]
            d.line(pts, fill=col, width=14, joint='curve')
        for i in range(0, 11, 2):
            d.line([(100 + i * 31, 140 + 40 * math.sin(i / 3)), (100 + i * 31, 370 + 40 * math.sin(i / 3 + 2))],
                   fill=ACC, width=6)
        return img
    out['loft'] = loft

    def zbrush():
        img, d = canvas()
        d.ellipse((90, 150, 250, 310), outline=FG, width=W)
        d.rectangle((280, 200, 420, 340), outline=CY, width=W)
        d.line([(180, 360), (360, 360)], fill=ACC, width=16)
        poly(d, [(360, 335), (405, 360), (360, 385)], ACC, fill=ACC)
        d.line([(330, 120), (150, 120)], fill=ACC, width=16)
        poly(d, [(150, 95), (105, 120), (150, 145)], ACC, fill=ACC)
        return img
    out['zbrush'] = zbrush

    def profile(kind):
        def fn():
            img, d = canvas()
            base_y, x0, x1, h = 380, 90, 422, 190
            if kind == 'flat':
                pts = [(x0, base_y), (x0, base_y - h), (x1, base_y - h), (x1, base_y)]
            elif kind == 'chamfer':
                c = 60
                pts = [(x0, base_y), (x0, base_y - h + c), (x0 + c, base_y - h), (x1 - c, base_y - h),
                       (x1, base_y - h + c), (x1, base_y)]
            elif kind == 'bevel':
                r = 60
                pts = [(x0, base_y)]
                pts += [(x0 + r - r * math.cos(a), base_y - h + r - r * math.sin(a))
                        for a in [i * math.pi / 2 / 8 for i in range(9)]]
                pts += [(x1 - r + r * math.cos(a), base_y - h + r - r * math.sin(a))
                        for a in [math.pi / 2 - i * math.pi / 2 / 8 for i in range(9)]]
                pts += [(x1, base_y)]
            else:
                pts = [(x0, base_y), (x0, base_y - 30)]
                pts += [(256 + 166 * math.cos(a), base_y - 30 - 210 * math.sin(a))
                        for a in [math.pi - i * math.pi / 24 for i in range(25)]]
                pts += [(x1, base_y)]
            poly(d, pts, ACC, fill=(255, 158, 40, 90))
            return img
        return fn
    for k in ('flat', 'chamfer', 'bevel', 'dome'):
        out['profile_' + k] = profile(k)

    def subd():
        img, d = canvas()
        poly(d, [(110, 300), (200, 160), (400, 180), (420, 330), (230, 390)], FG, width=10)
        smooth = []
        for i in range(48):
            a = 2 * math.pi * i / 48
            smooth.append((265 + 125 * math.cos(a) + 20 * math.cos(2 * a), 275 + 85 * math.sin(a)))
        poly(d, smooth, ACC, fill=(255, 158, 40, 90))
        d.line([(150, 420), (390, 420)], fill=CY, width=18)
        return img
    out['subd'] = subd

    def deform():
        img, d = canvas()
        # warped lattice cage: grid lines bent by a falloff around one point
        def warp(x, y):
            dx, dy = x - 330, y - 190
            w = max(0.0, 1.0 - math.hypot(dx, dy) / 260.0)
            return x + 60 * w * w, y - 70 * w * w
        for i in range(4):
            t = 110 + i * 97
            poly(d, [warp(t, 110 + j * 10) for j in range(30)], FG, width=9, closed=False)
            poly(d, [warp(110 + j * 10, t) for j in range(30)], FG, width=9, closed=False)
        cx, cy = warp(304, 207)
        d.ellipse((cx - 62, cy - 62, cx + 62, cy + 62), outline=CY, width=12)
        dots(d, [(cx, cy)], ACC, r=30)
        return img
    out['deform'] = deform
    return out


def main():
    target = Path(sys.argv[1] if len(sys.argv) > 1 else 'icons')
    target.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), target / f'{name}.png')
    print('wrote', len(icons()), 'icons to', target)


if __name__ == '__main__':
    main()
