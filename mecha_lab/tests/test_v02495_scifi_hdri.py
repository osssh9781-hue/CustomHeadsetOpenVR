"""0.24.95 The add-on's own sci-fi HDRIs (user: "HDRI 도 만들어 줘 빨리! 배경보다도 라이팅"): 8 lighting set-ups
(tools_dev/make_scifi_hdris.py) in the HDRI list as 'M:<file>' - after the user's folder, before Blender's - with
their previews, a heading 'Sci-Fi Lighting' on the HDRI page; picked like any other; their lights where they were meant
to be (the model faces -Y: a front light is at -Y)."""
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
bpy.ops.mesh.primitive_cube_add()
bpy.ops.mch.mech_shader_apply(preset='PAINTED')

files = ms.mecha_hdri_files()
check('8 sci-fi HDRIs come with the add-on (its hdris folder), each with its preview',
      [n for _f, n in files] == [n for _k, n in ms.MECHA_HDRIS] and len(files) == 8
      and all(ms.hdri_icon(ms.MECHA + f).startswith('file:') for f, _n in files), [n for _f, n in files])
items = [i[0] for i in ms._hdri_items(None, C)]
mine = [i for i in items if i.startswith(ms.MECHA)]
check('... in the HDRI list as \'M:\' entries, before Blender\'s own (Blender\'s first still number 0)',
      len(mine) == 8 and items.index(mine[-1]) < items.index(ms.hdri_files()[0])
      and next(i[4] for i in ms._hdri_items(None, C) if i[0] == ms.hdri_files()[0]) == 0, items[:10])

stats = {}
for f, n in files:
    img = bpy.data.images.load(os.path.join(ms.MECHA_DIR, f), check_existing=False)
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    a = a.reshape(h, w, 4)[..., :3].astype(np.float64)
    lum = a @ np.array([0.2126, 0.7152, 0.0722])
    el = ((np.arange(h) + 0.5) / h - 0.5) * np.pi
    wt = np.cos(el)[:, None]
    mean = float((lum * wt).sum() / (wt.sum() * w))
    r, c = np.unravel_index(int(np.argmax(lum)), lum.shape)
    ph = (0.5 - (c + 0.5) / w) * 2 * np.pi                 # (Blender: u = 0.5 - atan2(y, x) / 2pi)
    e = el[r]
    top = (np.cos(e) * np.cos(ph), np.cos(e) * np.sin(ph), np.sin(e))
    stats[f] = dict(size=(w, h), mean=mean, max=float(lum.max()), top=top)
check('... each 2048 x 1024, HDR (lights far over 1), as bright overall as Blender\'s own (mean 0.4 .. 1.0)',
      all(s['size'] == (2048, 1024) and s['max'] > 10 and 0.4 < s['mean'] < 1.0 for s in stats.values()),
      {k: (round(s['mean'], 2), round(s['max'])) for k, s in stats.items()})
sun = stats['orbital_window.exr']['top']
check('... the lights where they were meant to be: Orbital Window\'s sun front-left-above the model (-X, -Y, +Z)',
      sun[0] < -0.2 and sun[1] < -0.4 and sun[2] > 0.3, tuple(round(v, 2) for v in sun))

sc.mch_mech_hdri = ms.MECHA + 'hangar_bay.exr'
bpy.ops.mch.mech_hdri(action='SET')
env = sc.world.node_tree.nodes['mch:env']
check('Picked like any other: the world lit by it (the add-on\'s file)', env.image is not None
      and os.path.normpath(bpy.path.abspath(env.image.filepath)) == os.path.join(ms.MECHA_DIR, 'hangar_bay.exr'),
      env.image.filepath if env.image else None)
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
heads = [i.label for i in its if i.kind in ('pnote', 'shead')]
tiles = [i.label for i in its if i.kind == 'htile']
check('... the HDRI page: a \'Sci-Fi Lighting (8)\' heading over their previews, Hangar Bay\'s lit',
      any(h.startswith('Sci-Fi Lighting  (8)') for h in heads) and 'Hangar Bay' in tiles
      and any(i.kind == 'htile' and i.on and i.label == 'Hangar Bay' for i in its), (heads, tiles))
try:
    ms.remove_hdri(C, ms.MECHA + 'hangar_bay.exr')
    removed = True
except RuntimeError:
    removed = False
check('... not removable from the list (only the user\'s own are), its file untouched',
      not removed and os.path.isfile(os.path.join(ms.MECHA_DIR, 'hangar_bay.exr')))
summary()
