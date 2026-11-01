"""0.24.95 The user's sci-fi pack (user: "우리 기존 메테리얼 탭에 넣을 베이스 컬러랑 러프니스도 추가로 좀 뽑아 왔어" - 20 Base
Color + 20 Roughness, 1254 px, made with an image generator, "seamless not guaranteed"): into the Mech Shader's Base
and Roughness slots (``tools_dev/import_photo_maps.py --scifi``) and 20 new material presets on them.

* Base maps: the colour taken out (each channel to the same mean - the shader does colour x map x 2), the detail and
  the colour variation kept; the colour goes in the preset.  Each has its height map.
* Roughness maps: shifted to a 0.5 mean, contrast kept; the preset's Roughness = the map's mean, Roughness Map 1.
* Every map tiles (the seams healed with patches of the map itself).
* The old presets and maps keep their places (they are stored by position in .blend files): the new ones come after."""
import os

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms

mecha_lab.register()
fresh()
C = bpy.context

OLD_PRESETS = ['PLASTIC', 'PLASTIC_MATTE', 'RUBBER', 'STEEL', 'BRUSHED', 'GUNMETAL', 'CAST', 'FORGED', 'HEAT', 'BRASS',
               'COPPER', 'CARBON', 'PAINTED', 'CAMO', 'CHIPPED', 'SCRATCHED', 'RUSTY', 'RUSTED', 'DIRTY', 'MUDDY',
               'SNOWY', 'BATTLE', 'EMISSIVE', 'CIRCUIT', 'GLOW_SCRATCH', 'GLASS', 'GLASS_FROSTED', 'VISOR', 'HOLO',
               'CLOTH', 'CLOTH_DENIM', 'CLOTH_NYLON', 'CLOTH_PADDED', 'CLOTH_BURLAP', 'LEATHER']
OLD_BASE = ['FLAT', 'MOTTLED', 'BRUSHED', 'CAST', 'FORGED', 'HEAT', 'PATINA', 'PEEL', 'CARBON', 'CAMO']
OLD_ROUGH = ['CLEAN', 'FINE', 'SMUDGE', 'FINGER', 'BRUSHED', 'PATCHY', 'GRUNGE', 'WATER', 'STREAKS', 'WORN']
NEW = [k for k, _n in ms.SCIFI_MAPS]


def pixels(slot, ident, channels=3):
    img = bpy.data.images.load(ms.map_path(slot, ident))
    w, h = img.size
    a = np.empty(w * h * 4, np.float32)
    img.pixels.foreach_get(a)
    bpy.data.images.remove(img)
    return a.reshape(h, w, 4)[..., :channels].astype(np.float64)


def seam(g):
    sx = np.abs(g[:, 0] - g[:, -1]).mean() / max(np.abs(g[:, 1:] - g[:, :-1]).mean(), 1e-4)
    sy = np.abs(g[0] - g[-1]).mean() / max(np.abs(g[1:] - g[:-1]).mean(), 1e-4)
    return max(sx, sy)


ids = [p[0] for p in ms.PRESETS]
check('20 new materials, after the old 35 (old presets keep their places - a saved file keeps its preset)',
      len(NEW) == 20 and ids[:35] == OLD_PRESETS and ids[35:] == NEW, ids[35:])
check('... their maps after the old ten in Base and Roughness (the old maps keep their places)',
      [k for k, _l in ms.MAPS['base'][3]] == OLD_BASE + NEW and [k for k, _l in ms.MAPS['rough'][3]] == OLD_ROUGH + NEW)
missing = [(s, k) for s in ('base', 'rough') for k in NEW if ms.map_path(s, k) is None]
missing += [('base', k + '_height') for k in NEW if ms.map_path('base', k + '_height') is None]
check('... every Base map, its height map and every Roughness map on disk', not missing, missing)

# ---- the maps themselves (Blender reads the files as data here: the values as stored)
bad_mean, bad_seam, sizes = [], [], set()
for k in NEW:
    for slot in ('base', 'rough'):
        a = pixels(slot, k, 3 if slot == 'base' else 1)
        sizes.add(a.shape[:2])
        m = a.reshape(-1, a.shape[2]).mean(0)
        if slot == 'base':
            # (one mean for all three channels: the colour is out of the map; 0.5, or a little less for a map whose
            #  specks would clip)
            if np.ptp(m) > 0.03 or not 0.25 < m.mean() < 0.53:
                bad_mean.append((slot, k, m.round(3)))
        elif abs(m[0] - 0.5) > 0.03:
            bad_mean.append((slot, k, m.round(3)))
        s = seam(a.mean(2))
        if s > 1.7:
            bad_seam.append((slot, k, round(s, 2)))
check('Base maps grey on average (the colour is the preset\'s), Roughness maps a 0.5 mean', not bad_mean, bad_mean)
check('All 40 tile: the jump across their edges like an ordinary step inside (< 1.7; the pack: 1.1 - 3.3)',
      not bad_seam, bad_seam)
check('... 1024 px', sizes == {(1024, 1024)}, sizes)

# ---- a preset puts its own maps and colour on the nodes
bpy.ops.mesh.primitive_cube_add()
ob = C.active_object
for k in ('NAVAL', 'TWILL', 'NICKEL'):
    r = bpy.ops.mch.mech_shader_apply(preset=k)
    mat = ob.active_material
    st = getattr(mat, ms.KEY)
    nodes = mat.node_tree.nodes
    spec = dict((p[0], p[2]) for p in ms.PRESETS)[k]
    ok = (r == {'FINISHED'} and st.preset == k and st.base_map == k and st.rough_map == k
          and nodes['mch:img:base'].image.name.startswith(k) and nodes['mch:img:rough'].image.name.startswith(k)
          and abs(st.rough_amount - 1.0) < 1e-6)
    if k == 'NAVAL':        # (a coating: paint over metal, the map in the paint)
        ok = ok and st.paint == 1.0 and st.paint_pattern == 1.0 and abs(st.paint_rough - spec['paint_rough']) < 1e-6
        ok = ok and max(abs(a - b) for a, b in zip(st.paint_color, spec['paint_color'])) < 1e-4
        ok = ok and st.paint_color[2] > st.paint_color[0]                   # (blue)
    elif k == 'TWILL':      # (a composite: not metal, clear-coated)
        ok = ok and st.metallic == 0.0 and st.coat > 0.5 and st.paint == 0.0
    else:                   # (bare metal)
        ok = ok and st.metallic == 1.0 and st.paint == 0.0 and abs(st.roughness - spec['roughness']) < 1e-6
    check(f'{k}: Apply puts its own Base / Roughness maps and its colour / roughness on the material', ok,
          (r, st.preset, st.base_map, st.rough_map, nodes['mch:img:base'].image.name))
names = []
st.preset = 'LEATHER'
for _i in range(20):
    bpy.ops.mch.mech_shader_step(prop='preset', step=1)
    names.append(st.preset)
check('Stepping ▶ from the last old preset goes through the 20 new ones', names == NEW, names)
check('... each has its sphere icon (mech_icons/mat_<ID>.png)',
      all(os.path.isfile(os.path.join(os.path.dirname(ms.__file__), 'mech_icons', f'mat_{k}.png')) for k in NEW))
summary()
