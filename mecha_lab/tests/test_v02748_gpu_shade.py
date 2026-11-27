"""0.24.348 GPU material evaluation (user: "2.3.4 먼저 해 줘" - 3: the node maths on the graphics card).

Headless (no GPU): every Mech preset's node tree is written as GLSL without a node it does not know, and a bake with
GPU on falls back to numpy with the same maps.  With a GPU (run in a window): the maps from the GPU the same as numpy,
also cut into batches."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_maps as bm, fast_shade as F, gpu_bake as gb, gpu_shade as gs, mech_shader as ms

fresh()
mecha_lab.register()
C = bpy.context
KINDS = ['NORMAL', 'COLOR', 'ROUGH', 'METAL', 'EMIT']


def grooved(name):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    ob.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=3)
    bpy.ops.mesh.inset(thickness=0.08, depth=-0.08, use_individual=True)
    bpy.ops.object.mode_set(mode='OBJECT')
    return ob


ob = grooved('GPU Shade')
built, failed = 0, []
for pid in ms.PRESET_IDS:
    m = ms.new_material(pid)
    ms.assign(C, [ob], m)
    bm.ensure_uv(C, ob, new=False, res=64)
    g = F.Geo(C, ob, 64)
    sc = F._scene_new(*F._part_mesh(g))
    try:
        ev = F.Eval(ob, g, F.Images(), sc, sc, np.arange(g.n, dtype=np.uint32), 0.25)
        ev.root_tree = m.node_tree
        src, geo, atlas, kinds = gs.build(ev, m, KINDS, F.Images())
        ok = 'void main()' in src and geo.shape[0] == g.n and len(kinds) == len(KINDS)
        built += bool(ok)
        if not ok:
            failed.append(pid)
    except F.Unsupported as ex:
        failed.append(f'{pid}: {ex}')
    finally:
        F._scene_free(sc)
check('every Mech preset is written as GLSL (no node left to numpy)', not failed and built == len(ms.PRESET_IDS),
      failed[:4])

st = bm.settings(C)
st.res = '256'
m = ms.new_material('BATTLE')
ms.assign(C, [ob], m)
bm.ensure_uv(C, ob, new=False, res=256)
out = {}
_bevel = gb.bevel
gb.bevel = lambda *a, **k: None                    # (the Bevel rays on the C engine both times: the node maths compared)
for use in (False, True):
    st.gpu = use
    pix, why, _t = F.bake(C, ob, None, KINDS, 256, st)
    out[use] = (pix, why, F.GPU_MATS[0])
check('the bake works with the GPU switch on (all maps, none to Cycles)',
      all(k in out[True][0] for k in KINDS) and not out[True][1], out[True][1])
gpu_used = out[True][2] > 0
diff = max(float(np.abs(np.asarray(out[False][0][k]) - np.asarray(out[True][0][k])).max()) for k in KINDS)
check('GPU on = numpy (the same maps)' + ('' if gpu_used else ' [no GPU here: numpy both times]'), diff < 2e-3, diff)
if gpu_used:
    gs.MAXROWS[0] = 4                              # (tiny batches: the texels in many pieces)
    try:
        pix, why, _t = F.bake(C, ob, None, KINDS, 256, st)
    finally:
        gs.MAXROWS[0] = 8192
    d2 = max(float(np.abs(np.asarray(out[False][0][k]) - np.asarray(pix[k])).max()) for k in KINDS)
    check('GPU in batches = numpy', d2 < 2e-3 and F.GPU_MATS[0] > 0, d2)
gb.bevel = _bevel
print('GPU used:', gpu_used, gs.STATS)
failed = summary()
if not bpy.app.background:
    bpy.ops.wm.quit_blender()
