"""0.24.321 (user: "노말 베벨 두께만큼 리얼 메쉬로 변환했을 때 그 두께로 안 나와, 되게 얇게 나와"): Make Bevel Real gives the
Radius in world size on a scaled part too (the Bevel modifier's Width is in the object's own space: a part scaled 0.01
got a bevel 100 x thinner), and the Radius slider keeps it so."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bevel_normal as bn

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def width(ob):
    """The bevel as built, in world size: how far in from the side the flat top starts."""
    C.view_layer.update()
    ev = ob.evaluated_get(C.evaluated_depsgraph_get())
    me = ev.to_mesh()
    co = np.array([(ob.matrix_world @ v.co)[:] for v in me.vertices])
    ev.to_mesh_clear()
    top = co[np.abs(co[:, 2] - co[:, 2].max()) < 1e-5]
    return co[:, 0].max() - top[:, 0].max()


S.mch_bevel_normal_radius = 0.05
for sc in (1.0, 0.01, 2.0, 100.0):
    bpy.ops.mesh.primitive_cube_add(size=2 / sc)
    ob = C.active_object
    ob.scale = (sc,) * 3
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    bpy.ops.mch.bevel_normal_real()
    w = width(ob)
    check(f'scale {sc}: the real bevel {w:.4f} wide in the world (Radius 0.05)', abs(w - 0.05) < 1e-3)
    if sc == 0.01:
        S.mch_bevel_normal_radius = 0.02
        check(f'... Radius 0.02 afterwards: follows in world size ({width(ob):.4f})', abs(width(ob) - 0.02) < 1e-3)
        S.mch_bevel_normal_radius = 0.05
    bpy.data.objects.remove(ob)

# 0.24.330 (user's cop_for_rig.blend: parts scaled unevenly - (0.55, 0.39, 0.017)) the scale into the mesh first, then
# the bevel is the same width every way
bpy.ops.mesh.primitive_cube_add(size=2.0)
ob = C.active_object
ob.scale = (2.0, 1.0, 0.05)
C.view_layer.update()
before = [(ob.matrix_world @ v.co)[:] for v in ob.data.vertices]
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
S.mch_bevel_normal_radius = 0.02
bpy.ops.mch.bevel_normal_real()
C.view_layer.update()
after = [(ob.matrix_world @ v.co)[:] for v in ob.data.vertices]
check('an uneven scale (2, 1, 0.05): put into the mesh (scale 1), the part where it was',
      tuple(ob.scale) == (1.0, 1.0, 1.0) and np.abs(np.array(sorted(before)) - np.array(sorted(after))).max() < 1e-6)
ev = ob.evaluated_get(C.evaluated_depsgraph_get()).to_mesh()
co = np.array([(ob.matrix_world @ v.co)[:] for v in ev.vertices])
ob.evaluated_get(C.evaluated_depsgraph_get()).to_mesh_clear()
top = co[np.abs(co[:, 2] - co[:, 2].max()) < 1e-6]
side = co[np.abs(co[:, 0] - co[:, 0].max()) < 1e-6]
wx = co[:, 0].max() - top[:, 0].max()           # (in from the side on the top)
wz = co[:, 2].max() - side[:, 2].max()          # (down from the top on the side)
check(f'... the bevel the same width both ways ({wx:.4f} across, {wz:.4f} down; Radius 0.02)',
      abs(wx - 0.02) < 2e-3 and abs(wz - 0.02) < 2e-3)
summary()
