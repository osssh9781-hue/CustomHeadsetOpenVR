"""0.24.95 The user's Sci-Fi decals (``SciFi_Decals_30``: 30 RGBA PNGs, 1024 px, transparent backgrounds - "추가
데칼이야! 이거도 추가해 줘") into Mecha Lab's decal library as FULL-COLOUR decals (their own colours, not the two-tone
mask): RGB = the colour (sRGB), alpha = where the decal is.

For each ``NN_Name_Words.png``:
    * cut to what is drawn (the alpha's box) + 2 % margin, so the decal plane is the picture's own shape (Hazard
      Stripe 8.6 : 1, Direction Arrows 3.6 : 1 ...); at most 1024 px on its long side
    * the colour run on under the see-through pixels (push-pull fill): no dark / white fringe where the GPU blends a
      visible pixel with a hidden one (linear filtering, mip-maps)
    * ``addon/mecha_lab/decals/SF_<NAME>.webp`` (WebP quality 92, its alpha lossless - a quarter of the PNG: the
      pictures' worn grain makes PNGs big, and the add-on zip has to stay under GitHub's 100 MB a file), its tile
      ``mech_icons/decal_SF_<NAME>.png`` (128 px, on dark grey as the two-tone ones) and ``decals/scifi.json`` (id ->
      label, width : height, in the pack's order)

    python3 -I tools_dev/import_scifi_decals.py <the unpacked SciFi_Decals_30 folder>
"""
import json
import os
import re
import sys

import numpy as np
from PIL import Image

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
OUT = os.path.join(ROOT, 'addon', 'mecha_lab', 'decals')
ICONS = os.path.join(ROOT, 'addon', 'mecha_lab', 'mech_icons')
LONG = 1024


def push_pull(rgb, w):
    """``rgb`` filled where ``w`` is 0 from the pixels round it (an image pyramid: each level the weighted mean of the
    one above, then back up, the holes taking the coarser colour)."""
    h, wd = w.shape
    if min(h, wd) <= 2:
        tot = w.sum()
        mean = (rgb * w[..., None]).sum((0, 1)) / tot if tot > 0 else np.full(3, 0.5)
        return np.broadcast_to(mean, rgb.shape).copy()
    h2, w2 = (h + 1) // 2, (wd + 1) // 2
    pr = np.zeros((h2 * 2, w2 * 2, 3))
    pw = np.zeros((h2 * 2, w2 * 2))
    pr[:h, :wd] = rgb * w[..., None]
    pw[:h, :wd] = w
    sr = pr.reshape(h2, 2, w2, 2, 3).sum((1, 3))
    sw = pw.reshape(h2, 2, w2, 2).sum((1, 3))
    low = np.where(sw[..., None] > 0, sr / np.maximum(sw, 1e-9)[..., None], 0.0)
    low = push_pull(low, np.minimum(sw, 1.0))
    up = low.repeat(2, 0).repeat(2, 1)[:h, :wd]
    return rgb * w[..., None] + up * (1.0 - w[..., None])


def name_of(fname):
    stem = os.path.splitext(fname)[0]
    words = re.sub(r'^\d+_', '', stem).split('_')
    label = ' '.join(wd if wd.lower() not in {'of'} else wd.lower() for wd in words)
    return 'SF_' + '_'.join(wd.upper() for wd in words), label


def one(path):
    im = Image.open(path).convert('RGBA')
    a = np.asarray(im).astype(np.float64) / 255.0
    al = a[..., 3]
    ys, xs = np.nonzero(al > 8 / 255)
    x0, x1, y0, y1 = xs.min(), xs.max() + 1, ys.min(), ys.max() + 1
    m = int(round(0.02 * max(x1 - x0, y1 - y0)))
    pad = np.zeros((a.shape[0] + 2 * m, a.shape[1] + 2 * m, 4))
    pad[m:m + a.shape[0], m:m + a.shape[1]] = a
    a = pad[y0:y1 + 2 * m, x0:x1 + 2 * m]
    rgb, al = a[..., :3], a[..., 3]
    fill = push_pull(rgb, (al > 0.5).astype(np.float64))
    rgb = np.where(al[..., None] > 0.02, rgb, fill)
    out = Image.fromarray(np.clip(np.dstack([rgb, al]) * 255 + 0.5, 0, 255).astype(np.uint8), 'RGBA')
    s = LONG / max(out.size)
    if s < 1.0:
        out = out.resize((max(1, round(out.width * s)), max(1, round(out.height * s))), Image.LANCZOS)
    return out


def icon(ident, img):
    a = np.asarray(img).astype(np.float64) / 255.0
    bg = np.array([0.26, 0.26, 0.28]) ** (1 / 2.2)            # (the two-tone tiles' grey, as shown)
    col = a[..., :3] * a[..., 3:] + bg * (1 - a[..., 3:])
    im = Image.fromarray(np.clip(col * 255 + 0.5, 0, 255).astype(np.uint8))
    im.thumbnail((112, 112), Image.LANCZOS)
    tile = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
    plate = Image.new('RGBA', im.size, (0, 0, 0, 255))
    plate.paste(im, (0, 0))
    tile.paste(plate, ((128 - im.width) // 2, (128 - im.height) // 2))
    tile.save(os.path.join(ICONS, f'decal_{ident}.png'), optimize=True)


def main(src):
    table = {}
    for f in sorted(os.listdir(src)):
        if not re.match(r'^\d+_.*\.png$', f):
            continue
        ident, label = name_of(f)
        img = one(os.path.join(src, f))
        path = os.path.join(OUT, ident + '.webp')
        img.save(path, quality=92, method=6)
        icon(ident, img)
        table[ident] = [label, round(img.width / img.height, 4)]
        print(ident, label, img.size, os.path.getsize(path) // 1024, 'KB')
    with open(os.path.join(OUT, 'scifi.json'), 'w', encoding='utf-8') as fh:
        json.dump(table, fh, indent=1)
    print(len(table), 'sci-fi decals into', OUT)


if __name__ == '__main__':
    main(sys.argv[1])
