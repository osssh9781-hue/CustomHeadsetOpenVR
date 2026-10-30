"""0.24.93 Paint Lab brush icons: the Essentials brush previews (Paint Soft / Paint Square / Paint Blend / Smear /
Blur) written as 128 px PNGs into icons/ (zb_<name>.png), the way the cloth brush icons were made.
Run with a bpy-enabled Python:  python tools_dev/make_icons_v02493_paint.py"""
import os
import sys

import bpy
import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ICONS = os.path.join(os.path.dirname(HERE), 'addon', 'mecha_lab', 'icons')
NAMES = ('Paint Soft', 'Paint Square', 'Paint Blend', 'Smear', 'Blur')


def stem(bl):
    return 'zb_' + bl.lower().replace('/', '_').replace(' ', '_')


def main():
    lib = os.path.join(bpy.utils.system_resource('DATAFILES'), 'assets', 'brushes', 'essentials_brushes-mesh_sculpt.blend')
    with bpy.data.libraries.load(lib, assets_only=True) as (src, dst):
        dst.brushes = [n for n in src.brushes if n in NAMES]
    made = []
    for b in dst.brushes:
        if b is None or b.preview is None:
            continue
        pv = b.preview
        w, h = pv.image_size
        if w == 0:
            continue
        px = np.array(pv.image_pixels_float[:], np.float32).reshape(h, w, 4)
        img = bpy.data.images.new('icon_' + b.name, w, h, alpha=True)
        img.pixels.foreach_set(px.ravel())
        if (w, h) != (128, 128):
            img.scale(128, 128)
        out = os.path.join(ICONS, stem(b.name) + '.png')
        img.filepath_raw = out
        img.file_format = 'PNG'
        img.save()
        made.append(out)
        bpy.data.images.remove(img)
    print('icons:', [os.path.basename(m) for m in made])
    return made


if __name__ == '__main__':
    main()
