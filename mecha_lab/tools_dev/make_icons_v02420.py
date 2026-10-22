"""0.24.20 Base Mesh profile picture for Puff (an inflated lump, round on both sides) - same style as the other
profile_*.png from make_icons.py.

python make_icons_v02420.py <out dir>
"""
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, FG, canvas, poly, save  # noqa: E402


def icons():
    def profile_puff():
        # side view: a lens / pill bulging above and below the drawing plane (dashed line through the middle)
        img, d = canvas()
        cx, cy, rx, ry = 256, 280, 168, 110
        pts = [(cx + rx * math.cos(a), cy + ry * math.sin(a) * (1 - 0.18 * math.cos(a) ** 8))
               for a in [i * 2 * math.pi / 72 for i in range(72)]]
        poly(d, pts, ACC, fill=(255, 158, 40, 90))
        for x in range(70, 442, 44):
            d.line((x, cy, x + 22, cy), fill=FG, width=10)
        return img
    return {'profile_puff': profile_puff}


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
