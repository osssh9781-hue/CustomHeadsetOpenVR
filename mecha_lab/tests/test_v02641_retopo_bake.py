"""0.24.241 (user: "리토포 하고 베이킹 하는 툴" - "리토포+베이크 한 번에"): one button on a detailed mesh makes a quad
low poly near the asked face count with UVs, bakes the high's Normal / AO onto it (a material with the maps), hides
the high and leaves it unchanged; pressed again on that low it bakes again from the same high."""
import time

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import retopo_bake as rb, bake_maps as bm  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
high = C.active_object
high.name = 'Head'
tex = bpy.data.textures.new('bumps', 'CLOUDS'); tex.noise_scale = 0.18
d = high.modifiers.new('D', 'DISPLACE'); d.texture = tex; d.strength = 0.12
sub = high.modifiers.new('S', 'SUBSURF'); sub.levels = 1
co0 = np.empty(len(high.data.vertices) * 3); high.data.vertices.foreach_get('co', co0)
n_high = len(high.evaluated_get(C.evaluated_depsgraph_get()).data.polygons)
st = bm.settings(C); st.res = '512'; st.ao_samples = 8; st.save = False
S.mch_rb_faces = 3000
t = time.time()
r = bpy.ops.mch.retopo_bake()
dt = time.time() - t
low = C.active_object
check(f'the button runs ({dt:.1f} s), the low is active', r == {'FINISHED'} and low is not high and low.name == 'Head_Low')
nf = len(low.data.polygons)
quads = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, nf)
check(f'a low poly near 3000 faces ({nf:,} from {n_high:,}), mostly quads ({quads:.0%})',
      1500 <= nf <= 6000 and quads > 0.8)
check('it has UVs', len(low.data.uv_layers) > 0)
imgs = [n.image for m in low.data.materials if m and m.use_nodes for n in m.node_tree.nodes
        if n.type == 'TEX_IMAGE' and n.image]
names = sorted(i.name for i in imgs)
check(f'a material with the baked maps on the low ({names})', any('Normal' in n for n in names) and any('AO' in n for n in names))
nimg = next(i for i in imgs if 'Normal' in i.name)
px = np.array(nimg.pixels[:]).reshape(-1, 4)
used = px[px[:, 3] > 0.5] if (px[:, 3] > 0.5).any() else px
spread = float(used[:, 0].std() + used[:, 1].std())
check(f'the normal map carries the bumps (spread {spread:.3f})', spread > 0.02)
check('the high is hidden and its mesh unchanged',
      high.hide_get() and np.allclose(co0, np.array([v.co[i] for v in high.data.vertices for i in range(3)])))
check('the low knows its high', rb.high_of(low) is high)
nf0 = len(low.data.polygons)
r = bpy.ops.mch.retopo_bake()
check('pressed again on the low: baked again from the same high, the low kept (no new object)',
      r == {'FINISHED'} and C.active_object is low and len(low.data.polygons) == nf0
      and not any(o.name.startswith('Head_Low.') for o in bpy.data.objects))
summary()
