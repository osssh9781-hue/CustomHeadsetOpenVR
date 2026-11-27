"""0.24.343 (user: "데칼은 왜 베이크가 안돼?" / "빠르게 해줘"): Decals baked into No High Poly maps - each part's decals
(their colour, roughness, metallic, by their alpha, their damage too) laid over its own material; As One with many
parts in one pass of the engine."""
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, decals as dc, fast_shade as fsh, mech_shader as ms, progress

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
RES = 256
L = fsh.lib()
check('the engine casts rays for decals (mbake v5)', L is not None and L.mbake_version() >= 5)

bpy.ops.mesh.primitive_cube_add(size=2)
cube = C.active_object
cube.name = 'Body'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode='OBJECT')
ms.assign(C, [cube], ms.new_material('PAINTED'))
bm.ensure_uv(C, cube, new=False, res=RES)
st = S.mch_bake
st.res = str(RES)
st.own, st.fast, st.own_one = True, True, False
st.normal = st.ao = st.metal = False
st.color = st.rough = True
st.curv = st.height = st.emit = False
st.save, st.use_on_low = False, False


def bake_color(ob):
    for o in S.objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    info = bm.bake_pair(C, ob, [], st)
    px = np.array(bpy.data.images[f'{ob.name}_Color'].pixels[:]).reshape(RES, RES, 4)[..., :3].copy()
    return px, info


plain, _i = bake_color(cube)
dec = dc.place(C, cube, (0.0, 0.0, 1.0), (0.0, 0.0, 1.0), 'HAZARD')
with_d, info = bake_color(cube)
diff = np.abs(with_d - plain).max(2)
ch = diff > 0.08
yellow = (with_d[..., 0] > 0.6) & (with_d[..., 1] > 0.45) & (with_d[..., 2] < 0.3)
check(f'a Hazard decal shows in the baked Color map ({ch.mean() * 100:.2f}% of the map changed, '
      f'{yellow.sum()} yellow texels), fast ({info.get("fast")})',
      0.002 < ch.mean() < 0.2 and yellow.sum() > 50 and 'COLOR' in (info.get('fast') or []))
check('only under the decal: the rest of the map as before', np.percentile(diff[~ch], 99) < 0.02)
dec.hide_render = True
again, _i = bake_color(cube)
check('a decal hidden from renders is left out', np.abs(again - plain).max() < 0.02)
dec.hide_render = False

# As One: 12 parts (decal on one) in one pass
parts = [cube]
for i in range(11):
    bpy.ops.mesh.primitive_cube_add(size=1.2, location=(3 + (i % 4) * 2.0, (i // 4) * 2.0, 0))
    o = C.active_object
    o.name = f'P{i}'
    ms.assign(C, [o], ms.new_material(('STEEL', 'BATTLE', 'PAINTED')[i % 3]))
    parts.append(o)
st.own_one = True
st.ao = st.normal = st.metal = True
t0 = time.time()
info = progress.run_now(bm.bake_self_one_steps(C, parts, st))
dt = time.time() - t0
J = bpy.data.objects.get(info['low'])
col = np.array(bpy.data.images[f'{J.name}_Color'].pixels[:]).reshape(RES, RES, 4)[..., :3]
yl = (col[..., 0] > 0.6) & (col[..., 1] > 0.45) & (col[..., 2] < 0.3)
check(f'As One, 12 parts: one joined copy, every map fast ({info["fast"]}, {dt:.1f} s), the decal in it '
      f'({yl.sum()} yellow texels)',
      J is not None and set(info['fast']) == {'NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL'} and yl.sum() > 5)
check('the decal is still there, on its part (not joined in)', dec.name in bpy.data.objects and dec.parent is cube)
summary()
