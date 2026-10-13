"""Draw icons/primitive_pill.png in the style of the other primitive icons
(dark rounded tile, white outline, orange ring)."""
import math
import os
import sys

from PIL import Image, ImageDraw

S = 4                      # supersampling
N = 128 * S
BG, EDGE = (37, 43, 53, 255), (68, 81, 96, 255)
WHITE, ORANGE = (238, 242, 247, 255), (246, 165, 54, 255)


def stadium(cx, cy, half, r, squash, n=40):
    """Top view of a pill, squashed vertically (perspective)."""
    pts = []
    for i in range(n + 1):
        t = -math.pi / 2 + math.pi * i / n
        pts.append((cx + half + r * math.cos(t), cy + r * math.sin(t) * squash))
    for i in range(n + 1):
        t = math.pi / 2 + math.pi * i / n
        pts.append((cx - half + r * math.cos(t), cy + r * math.sin(t) * squash))
    return pts


def main(out):
    img = Image.new('RGBA', (N, N), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    d.rounded_rectangle((4 * S, 4 * S, N - 4 * S, N - 4 * S), radius=22 * S, fill=BG, outline=EDGE, width=3 * S)
    w = 5 * S
    cx, top, bot = 60 * S, 40 * S, 84 * S
    half, r, sq = 18 * S, 16 * S, 0.45
    pts = stadium(cx, top, half, r, sq)
    d.line(pts + [pts[0]], fill=WHITE, width=w, joint='curve')
    left, right = cx - half - r, cx + half + r
    d.line([(left, top), (left, bot)], fill=WHITE, width=w)
    d.line([(right, top), (right, bot)], fill=WHITE, width=w)
    low = [p for p in stadium(cx, bot, half, r, sq) if p[1] >= bot - 1]
    low.sort(key=lambda p: p[0])
    d.line(low, fill=WHITE, width=w, joint='curve')
    d.ellipse((88 * S, 82 * S, 112 * S, 106 * S), outline=ORANGE, width=5 * S, fill=BG)
    img.resize((128, 128), Image.LANCZOS).save(out)


if __name__ == '__main__':
    main(sys.argv[1] if len(sys.argv) > 1 else
         os.path.join(os.path.dirname(__file__), '..', 'addon', 'mecha_lab', 'icons', 'primitive_pill.png'))
