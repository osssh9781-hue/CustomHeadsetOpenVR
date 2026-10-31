"""0.24.95 Flip in the right-click menus (user: "우클릭 팝업에 뒤집기도 넣어 줘 ... 좌우 오브젝트 뒤집는 거"): the selected
objects mirrored left-right - one in place, several round their middle as a group - the mesh itself flipped (no negative
scale), the outside staying outside; Sculpt Mode: back to Sculpt after."""
import inspect

import numpy as np
from _harness import bpy, check, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import mecha_menu, zb_ui

mecha_lab.register()
fresh()
C = bpy.context


def world(ob):
    return np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])


def outward(ob):
    """share of faces whose normal points away from the object's middle (a closed convex-ish mesh: all)."""
    mw = ob.matrix_world
    c = Vector(world(ob).mean(0))
    n3 = mw.to_3x3().inverted().transposed()
    return np.mean([(n3 @ p.normal).dot(mw @ p.center - c) > 0 for p in ob.data.polygons])


# an asymmetric part: a cone leaning to +X, rotated, at x = 2
bpy.ops.mesh.primitive_cone_add(radius1=0.5, depth=1.0, location=(2, 0, 0), rotation=(0, 0.6, 0.3))
a = C.active_object
for v in a.data.vertices:                      # (lean it: not symmetric about its own origin)
    v.co.x += 0.4 * (v.co.z + 0.5)
w0 = world(a)
select_only(a)
r = bpy.ops.mch.flip_object(axis='X')
w1 = world(a)
flipped = w0.copy()
flipped[:, 0] = 2 * 2.0 - w0[:, 0]
check('Flip (one object): mirrored left-right in place (through its origin x = 2): every point x -> 4 - x, y and z kept',
      r == {'FINISHED'} and np.allclose(w1, flipped, atol=1e-5), np.abs(w1 - flipped).max())
check('... no negative scale on the object, the faces still face out', all(s_ > 0 for s_ in a.scale) and outward(a) > 0.99,
      (tuple(a.scale), outward(a)))
bpy.ops.mesh.primitive_cube_add(size=1, location=(-3, 1, 0))
b = C.active_object
wa, wb = world(a), world(b)
a.select_set(True)
b.select_set(True)
bpy.ops.mch.flip_object(axis='X')
mid = (2.0 + -3.0) / 2.0
ea, eb = wa.copy(), wb.copy()
ea[:, 0] = 2 * mid - wa[:, 0]
eb[:, 0] = 2 * mid - wb[:, 0]
check('Flip (two objects): mirrored as a group round the middle of their origins (they swap sides, still together)',
      np.allclose(world(a), ea, atol=1e-5) and np.allclose(world(b), eb, atol=1e-5) and outward(b) > 0.99)
select_only(b)
bpy.ops.object.mode_set(mode='SCULPT')
wb2 = world(b)
bpy.ops.mch.flip_object(axis='X')
e2 = wb2.copy()
e2[:, 0] = 2 * b.matrix_world.translation.x - wb2[:, 0]
check('Sculpt Mode: flipped, and still in Sculpt Mode', C.mode == 'SCULPT' and np.allclose(world(b), e2, atol=1e-5))
bpy.ops.object.mode_set(mode='OBJECT')
check('In the Mecha right-click menu (Actions) and the ZBrush cursor menu',
      any(lab == 'Flip' and op == 'mch.flip_object' for _s, btns in mecha_menu.ACTIONS for lab, _i, op, *_r in btns)
      and "'mch.flip_object'" in inspect.getsource(zb_ui.popup))
summary()
