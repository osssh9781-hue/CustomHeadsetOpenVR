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
summary()
