"""0.24.176 Insect Wing (user: "곤충 날개도 크리쳐 클로스처럼 메쉬에 붙게 할 수 있어?", "벌레 날개도 처음 선 긋는 부분이 벌레
날개 [뿌리] 되게 해 줘"): the part drawn over a mesh sits on it, the rest eases back into the wing; the wing follows that
mesh (its child - even while live, laid again where the mesh is now); on Enter a Hook to each other mesh it is on (as
Creature Cloth); Stick to Mesh off: flat as before.  Its root where the drawing was started (a sketch: where its first
shape was started).  Measured on the wing's own points (world)."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_membrane as cm, insect_wing as iw  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
R = 0.4
bpy.ops.mesh.primitive_uv_sphere_add(radius=R, segments=96, ring_count=48, location=(0, 0, 0))
body = C.active_object
body.name = 'Thorax'
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # (looking +Y)


def outline(x0, z0, L, Wd, n=60, from_tip=False):
    pts = [(x0 + L * i / (n - 1), z0 + 0.02 * L * math.sin(math.pi * i / (n - 1))) for i in range(n)]
    pts += [(x0 + L * (1 - i / (n - 1)), z0 - Wd * math.sin(math.pi * (1 - i / (n - 1))) ** 0.7) for i in range(n)]
    if from_tip:
        pts = pts[n - 1:] + pts[:n - 1]
    return [[FRONT.to_screen(Vector((x, -3.0, z))) for x, z in pts]]


def world(ob):
    C.view_layer.update()
    dg = C.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    P = np.array([tuple(ev.matrix_world @ v.co) for v in me.vertices])
    ev.to_mesh_clear()
    return P


def unselect():
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = None


unselect()
S.mch_wing.preset = 'FLY'
msg = iw.perform(C, outline(0.05, 0.1, 1.5, 0.32), FRONT)        # (started over the thorax, toward +x)
w = C.active_object
d = iw.data(w)
P = world(w)
r_ = np.linalg.norm(P, axis=1)
over = np.hypot(P[:, 0], P[:, 2]) < R * 0.9                        # (over the thorax, seen from the front)
tip = P[:, 0] > 1.2
on_err = float(np.median(np.abs(r_[over] - R))) if over.any() else 9.9
check(f'drawn over the thorax: the part over it sits on it (distance to its surface, median {on_err:.4f}; '
      f'{int(over.sum())} points), the far part stays in the wing\'s plane (y {P[tip, 1].min():.3f}..'
      f'{P[tip, 1].max():.3f}) - {msg[:90]}...', over.sum() > 50 and on_err < 0.02 and np.ptp(P[tip, 1]) < 0.03)
grp = [g.name for g in w.vertex_groups if g.name.startswith(cm.HOST_PREFIX)]
check(f'it follows the thorax: its child ({w.parent and w.parent.name}), held points marked ({grp}), told so',
      w.parent == body and grp == [cm.HOST_PREFIX + 'Thorax'] and 'follows' in msg)
me = w.data
E = np.array([[e.vertices[0], e.vertices[1]] for e in me.edges])
co = np.array([tuple(v.co) for v in me.vertices])
el = np.linalg.norm(co[E[:, 0]] - co[E[:, 1]], axis=1)
check(f'no tear where it leaves the thorax (longest edge / median {el.max() / np.median(el):.1f})',
      el.max() / np.median(el) < 12.0)
root_xy = np.array(d['outline'][d['root']])
first = np.array([0.05, 0.1])
o3 = Vector(d['origin'])
X, Y = Vector(d['x']), Vector(d['y'])
r3 = o3 + X * float(root_xy[0]) + Y * float(root_xy[1])
check(f'its root where the drawing was started (x {r3.x:.3f}, z {r3.z:.3f}; started at 0.050, 0.100)',
      abs(r3.x - first[0]) < 0.06 and abs(r3.z - first[1]) < 0.06)
# the thorax moved: the wing with it - and laid again (a slider) it stays on it there
P0 = world(w)
body.location = (0.3, 0.0, 1.0)
P1 = world(w)
mv = P1 - P0
check(f'the thorax moved (0.3, 0, 1): the wing with it (moved {np.round(mv.mean(0), 4).tolist()})',
      np.abs(mv - np.array([0.3, 0.0, 1.0])).max() < 1e-4)
w.mch_wing.vein_height = 0.9                                         # (laid again, live)
P2 = world(w)
c2 = np.array([0.3, 0.0, 1.0])
over2 = np.hypot(P2[:, 0] - c2[0], P2[:, 2] - c2[2]) < R * 0.9
err2 = float(np.median(np.abs(np.linalg.norm(P2[over2] - c2, axis=1) - R))) if over2.any() else 9.9
check(f'laid again after it moved (a slider): still on the thorax where it is now (median {err2:.4f})', err2 < 0.02)
body.location = (0.0, 0.0, 0.0)
w.mch_wing.stick = False
P3 = world(w)
check(f'Stick to Mesh off: flat as before (the part over the thorax back in the plane: y {P3[over, 1].min():.3f}..'
      f'{P3[over, 1].max():.3f}), no held points', np.ptp(P3[over, 1]) < 0.03
      and not any(g.name.startswith(cm.HOST_PREFIX) for g in w.vertex_groups))
w.mch_wing.stick = True
P4 = world(w)
check('on again: on the thorax again', float(np.median(np.abs(np.linalg.norm(P4[over], axis=1) - R))) < 0.02)
bpy.data.objects.remove(w)
# drawn from the tip: the root there
unselect()
msg2 = iw.perform(C, outline(0.05, 0.1, 1.5, 0.32, from_tip=True), FRONT)
w2 = C.active_object
d2 = iw.data(w2)
rx = (Vector(d2['origin']) + Vector(d2['x']) * d2['outline'][d2['root']][0]).x
check(f'drawn starting at the far end: its root there (x {rx:.3f}), its tip at the thorax', rx > 1.4)
bpy.data.objects.remove(w2)
# two meshes under it: kept (Enter) - a Hook to the other one, its own points only
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.14, segments=48, ring_count=24, location=(0.62, 0.0, 0.05))
arm = C.active_object
arm.name = 'Arm'
unselect()
iw.perform(C, outline(0.05, 0.1, 1.5, 0.32), FRONT)
w3 = C.active_object
groups = sorted(g.name for g in w3.vertex_groups if g.name.startswith(cm.HOST_PREFIX))
r = bpy.ops.mch.wing_apply()
hooks = [(m.object.name, m.vertex_group) for m in w3.modifiers if m.type == 'HOOK']
Pa = world(w3)
arm.location.z += 0.3
Pb = world(w3)
dz = Pb[:, 2] - Pa[:, 2]
held_arm = np.zeros(len(Pa), bool)
vg = w3.vertex_groups.get(cm.HOST_PREFIX + 'Arm')
for v in w3.data.vertices:
    if any(g.group == vg.index for g in v.groups):
        held_arm[v.index] = True
check(f'over two meshes: held by both ({groups}); Enter: kept ({r}), a child of the thorax + a Hook to the arm ({hooks}); '
      f'the arm moved up 0.3: its points with it ({dz[held_arm].min():.3f}..{dz[held_arm].max():.3f}), the rest not '
      f'({np.abs(dz[~held_arm]).max():.4f})', r == {'FINISHED'} and w3.parent == body and hooks
      and hooks[0][0] == 'Arm' and held_arm.any() and abs(dz[held_arm].min() - 0.3) < 1e-3
      and np.abs(dz[~held_arm]).max() < 1e-4 and iw.data(w3) is None)
bpy.data.objects.remove(w3)
bpy.data.objects.remove(arm)
# a sketch: its root where its first shape was started
from mecha_lab import lasso_sketch  # noqa: E402
S.mch_brush.sketch_first = True
unselect()
lasso_sketch.add(C, 'WING', outline(0.9, 0.1, 0.9, 0.3, from_tip=True), FRONT)      # (started at x 1.8)
lasso_sketch.add(C, 'WING', outline(0.05, 0.1, 1.0, 0.3), FRONT)
lasso_sketch.commit(C)
S.mch_brush.sketch_first = False
w4 = C.active_object
d4 = iw.data(w4)
rx4 = (Vector(d4['origin']) + Vector(d4['x']) * d4['outline'][d4['root']][0]).x
check(f'a sketch (two shapes, the first started at x 1.80): the root where the first one was started (x {rx4:.3f})',
      iw.is_wing(w4) and rx4 > 1.7)
# a wing from before 0.24.176 (its plane in the world, nothing under it stored) still lays again
dd = iw.data(w4)
for k in ('lo', 'lx', 'ly', 'ln', 'attach'):
    dd.pop(k, None)
w4[iw.KEY] = json.dumps(dd)
nf = iw.build(w4, C)
check(f'a wing made before (its plane in the world): still laid again ({nf:,} faces)', nf > 1000)
summary()
