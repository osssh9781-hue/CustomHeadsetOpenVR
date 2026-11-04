"""0.24.95 picture for Press Cut (same style as make_icons.py): a stamp shape pressed down into a block - the pocket
goes deeper (stepped outlines) under a down arrow.

python make_icons_v02495_press.py <out dir>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, CY, FG, W, canvas, poly, save  # noqa: E402


def icons():
    out = {}

    def press_cut():
        img, d = canvas()
        poly(d, [(70, 250), (256, 170), (442, 250), (256, 330)], FG, width=W)            # the block's top
        d.line((70, 250, 70, 400), fill=FG, width=W)
        d.line((442, 250, 442, 400), fill=FG, width=W)
        d.line((256, 330, 256, 470), fill=FG, width=W)
        poly(d, [(70, 400), (256, 470), (442, 400)], FG, width=W, closed=False)
        notch = [(176, 252), (256, 218), (336, 252), (296, 270), (256, 252), (216, 270)]
        poly(d, notch, ACC, width=18, fill=(255, 158, 40, 110))                          # the stamp on the top
        sunk = [(x, y + 52) for x, y in notch]
        poly(d, sunk, ACC, width=12)                                                       # ... pressed in
        for (x0, y0), (x1, y1) in zip(notch[:3], sunk[:3]):
            d.line((x0, y0, x1, y1), fill=ACC, width=10)
        d.line((256, 40, 256, 150), fill=CY, width=W)                                      # hold = deeper
        poly(d, [(206, 120), (256, 182), (306, 120)], CY, fill=CY)
        return img
    out['press_cut'] = press_cut
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
