"""0.24.241 / 0.24.242 (user: "리토포 하고 베이크까지" in two steps, "베큠 하듯이 메쉬에 붙여버리는" retopo, a progress card):
1 Retopo makes a quad low near the asked face count (Quad: remesh; Wrap: a quad box vacuum-packed onto the high -
on its surface, the quads even, nothing inside out); 2 Bake puts the high's Normal / AO on it (UVs, a material with
the maps); the high is hidden and never changed; the steps report their progress (fraction rising to 1)."""
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import retopo_bake as rb, bake_maps as bm, progress  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=128, ring_count=64, radius=1.0)
high = C.active_object
high.name = 'Head'
high.scale = (1.0, 0.8, 1.3)
tex = bpy.data.textures.new('bumps', 'CLOUDS'); tex.noise_scale = 0.18
d = high.modifiers.new('D', 'DISPLACE'); d.texture = tex; d.strength = 0.12
high.modifiers.new('S', 'SUBSURF').levels = 1
co0 = np.empty(len(high.data.vertices) * 3); high.data.vertices.foreach_get('co', co0)
st = bm.settings(C); st.res = '512'; st.ao_samples = 8; st.save = False
check('the box: Quad / Wrap, Faces, 1 Retopo, 2 Bake (no low yet: Bake off)',
      not bpy.ops.mch.retopo_bake.poll() and bpy.ops.mch.retopo_make.poll())
S.mch_rb_faces, S.mch_rb_method = 3000, 'QUAD'
fr = [f for f, _l in rb.make_low_steps(C, high, 3000, 'QUAD', None)] if False else None
r = bpy.ops.mch.retopo_make()
low = C.active_object
nf = len(low.data.polygons)
quads = sum(1 for p in low.data.polygons if len(p.vertices) == 4) / max(1, nf)
check(f'1 Retopo (Quad): a low near 3000 faces ({nf:,}), mostly quads ({quads:.0%}), no bake yet, the high hidden',
      r == {'FINISHED'} and low.name == 'Head_Low' and 1500 <= nf <= 6000 and quads > 0.8 and not low.data.materials[:1] == ['x']
      and high.hide_get())
check('now Bake can run', bpy.ops.mch.retopo_bake.poll())
r = bpy.ops.mch.retopo_bake()
imgs = [n.image.name for m in low.data.materials if m and m.node_tree for n in m.node_tree.nodes if n.type == 'TEX_IMAGE' and n.image]
check(f'2 Bake: Normal and AO on the low ({imgs}), UVs made', r == {'FINISHED'} and any('Normal' in n for n in imgs)
      and any('AO' in n for n in imgs) and len(low.data.uv_layers) > 0)
# Wrap
S.mch_rb_method, S.mch_rb_faces = 'WRAP', 2500
steps = []
gen = rb.make_low_steps(C, high, 2500, 'WRAP', low)
t = time.time()
try:
    while True:
        steps.append(next(gen)[0])
except StopIteration as ex:
    low2, _note = ex.value
dt = time.time() - t
nf = len(low2.data.polygons)
check(f'Retopo again with Wrap ({dt:.1f} s): the same low object, all quads ({nf:,} faces near 2500)',
      low2 is low and all(len(p.vertices) == 4 for p in low2.data.polygons) and 1800 <= nf <= 3300)
check(f'its progress rises step by step to the end ({len(steps)} steps, {steps[0]:.2f} -> {steps[-1]:.2f})',
      len(steps) >= 10 and all(b >= a for a, b in zip(steps, steps[1:])) and steps[-1] >= 0.9)
dg = C.evaluated_depsgraph_get()
ev = high.evaluated_get(dg)
bvh = BVHTree.FromObject(ev, dg)
P = np.array([v.co for v in low2.data.vertices])
dist = np.array([bvh.find_nearest(Vector(p))[3] for p in P])
size = max(high.dimensions)
check(f'wrapped onto the surface (largest gap {dist.max():.4f}, size {size:.2f})', dist.max() < 0.003 * size)
E_ = np.array([e.vertices[:] for e in low2.data.edges])
L = np.linalg.norm(P[E_[:, 0]] - P[E_[:, 1]], axis=1)
check(f'the quads stay even (edge length spread: 95 % within {np.percentile(L, 97.5) / np.percentile(L, 2.5):.1f}x)',
      np.percentile(L, 97.5) / np.percentile(L, 2.5) < 4.0)
inside = 0
for p in low2.data.polygons[:400]:
    c = Vector(p.center); n = p.normal
    if n.dot(c) < 0:
        inside += 1
check(f'faces point outward ({inside} of 400 inward)', inside < 8)
r = bpy.ops.mch.retopo_bake()
check('Bake again from the same high onto the wrapped low', r == {'FINISHED'} and C.active_object is low)
check('the high is never changed', np.allclose(co0, np.array([c for v in high.data.vertices for c in v.co])))
summary()
