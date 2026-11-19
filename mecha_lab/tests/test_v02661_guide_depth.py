"""0.24.261 (user: "첫 장 뷰(위)에서 일직선으로 그렸는데 측면에선 지그재그"): a guide line drawn from above over a joined mesh -
a body with spikes on its back and an arm crossing over it - stays in the body: each point takes the stretch of the
body nearest the line so far (not the first thing the ray meets), the depths evened along the line."""
import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import rig_guides as rgd  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
parts = []
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.3, depth=4.0, rotation=(0, 1.5708, 0)); parts.append(C.active_object)
for x in np.linspace(-1.6, 1.6, 9):                             # (spikes on its back, poking up)
    bpy.ops.mesh.primitive_cone_add(vertices=16, radius1=0.12, depth=0.9, location=(x, 0.0, 0.55)); parts.append(C.active_object)
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=0.15, depth=3.0, location=(0.4, 0, 0.75), rotation=(1.5708, 0, 0))
parts.append(C.active_object)                                   # (an arm crossing over it, separate)
for p in parts:
    p.select_set(True)
C.view_layer.objects.active = parts[0]
bpy.ops.object.join()
ob = C.active_object
xs = np.linspace(-1.8, 1.8, 61)
bvh = rgd.body_bvh(ob)
d = np.array([0.0, 0.0, -1.0])
old, rays = [], []
for x in xs:
    o = np.array([x, 0.0, 5.0])
    sp = rgd.body_spans(ob, o, d)
    old.append(o + d * 0.5 * (sp[0][0] + sp[0][1]))             # (before: the first stretch the ray met)
    prev = None if not rays else rays[-1][0] + rays[-1][1] * rays[-1][3]
    pick = rgd.pick_span(sp, o, d, prev)
    rays.append((o, d, pick, rgd.deepest(bvh, o, d, pick)))
new = rgd.even_depths(rays)
old = np.array(old)
check(f'drawn from above along the body: before, the line jumped onto the spikes / the arm (height {old[:, 2].min():.2f} .. {old[:, 2].max():.2f}); '
      f'now it stays in the middle of the body ({new[:, 2].min():.3f} .. {new[:, 2].max():.3f})',
      old[:, 2].max() > 0.4 and np.abs(new[:, 2]).max() < 0.06)   # (the body 30 cm thick round)
check('straight from above stays straight from the side (no zigzag: largest step in height '
      f'{np.abs(np.diff(new[:, 2])).max() * 100:.1f} cm)', np.abs(np.diff(new[:, 2])).max() < 0.02)
summary()
