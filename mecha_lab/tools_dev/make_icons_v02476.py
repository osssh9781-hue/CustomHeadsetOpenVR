"""0.24.76 picture for Silhouette Move (same style as make_icons.py / make_icons_v02420.py): the whole part, cut
where it is grabbed, stretched out along a bent path.

python make_icons_v02476.py <out dir>
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
from make_icons import ACC, CY, W, canvas, poly, save  # noqa: E402

DIM = (120, 126, 140, 255)


def icons():
    out = {}

    def silhouette_move():                    # 0.24.76 the whole section swept: the part grows longer and bends
        img, d = canvas()
        poly(d, [(70, 300), (70, 420), (190, 420), (190, 300)], DIM, width=8)          # the part as it was
        band = [(130, 360), (250, 360), (330, 320), (380, 240), (395, 140)]
        poly(d, band, ACC, width=120, closed=False)                                     # the whole part, stretched
        poly(d, band, (255, 210, 140, 255), width=10, closed=False)
        d.line((250, 250, 330, 200), fill=CY, width=W)
        d.line((330, 200, 360, 120), fill=CY, width=W)
        poly(d, [(372, 92), (330, 120), (378, 142)], CY, fill=CY)
        return img
    out['silhouette_move'] = silhouette_move
    return out


if __name__ == '__main__':
    dst = Path(sys.argv[1] if len(sys.argv) > 1 else '.')
    dst.mkdir(parents=True, exist_ok=True)
    for name, fn in icons().items():
        save(fn(), dst / f'{name}.png')
        print('wrote', dst / f'{name}.png')
