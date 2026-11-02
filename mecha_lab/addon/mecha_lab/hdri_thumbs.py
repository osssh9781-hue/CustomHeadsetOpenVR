"""0.24.95 HDRI previews made in a second Blender (user: "hdri 뭉탱이로 불러왔더니 캐무거워" - a folder of folders of
big HDRIs: every preview read a whole HDRI in the window's Blender, one after another, and the window stopped for each).

* ``make_thumb(src, out)``: a small picture of the panorama (256 x 128 PNG; its brightness set by its mean, tone mapped,
  sRGB) - written under a temporary name and moved into place, so a half-written file is never read
* run as a script (``blender -b --factory-startup --python hdri_thumbs.py -- <list.json>``, or a python with the bpy
  module): makes the previews of the list's [source, out] pairs one by one, lowest priority; a source it cannot read
  gets ``<out>.fail`` (not tried again)
Only bpy and numpy: the worker does not load the add-on."""
import json
import os
import sys

THUMB = (256, 128)


def make_thumb(src_path, out_path, size=THUMB):
    import bpy
    import numpy as np
    W, H = size
    img = bpy.data.images.load(src_path, check_existing=False)
    try:
        if not img.size[0] or not img.size[1]:
            raise RuntimeError(f'cannot read {src_path}')
        is_float = img.is_float
        img.scale(W, H)
        px = np.empty(W * H * 4, np.float32)
        img.pixels.foreach_get(px)
    finally:
        bpy.data.images.remove(img)
    a = px.reshape(H, W, 4)[..., :3].astype(np.float64)
    if is_float:                                  # (an HDR: its brightness set by its mean, tone mapped, sRGB)
        lum = a @ np.array([0.2126, 0.7152, 0.0722])
        a = a * min(max(0.35 / max(float(lum.mean()), 1e-5), 0.05), 50.0)
        a = np.clip(a / (1.0 + a) * 1.3, 0.0, 1.0)
        a = np.where(a <= 0.0031308, a * 12.92, 1.055 * a ** (1 / 2.4) - 0.055)
    else:                                         # (0.24.95 a photo / a backdrop: as it is - its own colours)
        a = np.clip(a, 0.0, 1.0)
    tmp = out_path[:-4] + '.part.png' if out_path.lower().endswith('.png') else out_path + '.part.png'
    out = bpy.data.images.new('mch_hdri_thumb', W, H, alpha=False)
    try:
        rgba = np.concatenate([a, np.ones((H, W, 1))], -1).astype(np.float32)
        out.pixels.foreach_set(rgba.ravel())
        out.filepath_raw = tmp
        out.file_format = 'PNG'
        out.save()
    finally:
        bpy.data.images.remove(out)
    os.replace(tmp, out_path)
    return out_path


def _low_priority():
    try:
        os.nice(10)
    except (AttributeError, OSError):
        pass


def main():
    argv = sys.argv
    argv = argv[argv.index('--') + 1:] if '--' in argv else argv[1:]
    with open(argv[0], encoding='utf-8') as f:
        jobs = json.load(f)
    _low_priority()
    done = 0
    for src, out in jobs:
        if os.path.isfile(out) or os.path.isfile(out + '.fail'):
            continue
        try:
            make_thumb(src, out)
            done += 1
            print('MCH_THUMB', out, flush=True)
        except Exception as ex:                       # (any file the worker cannot read: marked, the rest go on)
            print('MCH_THUMB_FAIL', src, ex, flush=True)
            try:
                with open(out + '.fail', 'w', encoding='utf-8') as f:
                    f.write(f'{src}\n{ex}\n')
            except OSError:
                pass
    print('MCH_THUMBS_DONE', done, flush=True)


if __name__ == '__main__':
    main()
