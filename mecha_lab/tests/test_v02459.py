"""0.24.40 Primitive Remember Turn (the turn you gave the ghost on one surface is kept for the next click) and
Stamp Face: pick a point on the ghost = the face that goes onto the mesh; a click on a mesh
puts that face on the surface (facing into it, pressed Stamp Depth in) and Add / Subtract (or Stamp on Click)
merges / carves it there."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import primitive_place as pp

mecha_lab.register()
fresh()
C = bpy.context

# pure parts
loc, q = pp.stamp_transform(Quaternion(), Vector((0.5, 0, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)), Vector((0, 0, 1)))
check('the picked face (+X) faces into the surface (normal +Z) and sits on the hit point',
      (q @ Vector((1, 0, 0)) - Vector((0, 0, -1))).length < 1e-6
      and (loc + q @ Vector((0.5, 0, 0)) - Vector((0, 0, 1))).length < 1e-6, (loc, q))
loc2, _q = pp.stamp_transform(Quaternion(), Vector((0.5, 0, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)),
                              Vector((0, 0, 1)), depth=0.2)
check('Stamp Depth presses it in along the surface normal', (loc2 - loc - Vector((0, 0, -0.2))).length < 1e-6)
loc3, q3 = pp.stamp_transform(Quaternion(), Vector((0.5, 0, 0)), Vector((1, 0, 0)), Vector((0, 0, 1)),
                              Vector((0, 0, 1)), align=False)
check('Align to Surface off: only moved, not turned', abs(q3.angle) < 1e-9
      and (loc3 + Vector((0.5, 0, 0)) - Vector((0, 0, 1))).length < 1e-6)
verts, faces, _s = pp.ghost_shape('BOX', (1, 1, 2))
p, n = pp.pick_contact(verts, faces, pp.ghost_matrix((5, 0, 0), Quaternion()), (5, -10, 0.3), (0, 1, 0))
check('a click on the ghost picks the face it hits (local point and outward normal)', p is not None
      and abs(p.y + 0.5) < 1e-6 and (n - Vector((0, -1, 0))).length < 1e-6, (p, n))
check('a click past the ghost picks nothing', pp.pick_contact(verts, faces, pp.ghost_matrix((5, 0, 0), Quaternion()),
                                                            (9, -10, 0.3), (0, 1, 0))[0] is None)
check('how far the box reaches behind its -Y face: 1', abs(pp.behind_extent(verts, p, n) - 1.0) < 1e-6)

# on a mesh
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 0, 0))
cube = C.active_object
st = C.window_manager.mch_place
st.show = True
st.placed = True
st.kind, st.size, st.rotation, st.location = 'BOX', (0.4, 0.4, 1.2), (1, 0, 0, 0), (5, 0, 0)
st.contact_point = (0.5, 0.0, 0.0)                 # the +X side face (as a part of Size)
st.contact_on = True
cp, cn = pp.contact_local(st)
check('the picked face on the ghost, also after resizing it (kept as a part of Size)',
      abs(cp.x - 0.2) < 1e-6 and (cn - Vector((1, 0, 0))).length < 1e-6, (cp, cn))
st.stamp_depth = 0.25
pp.stamp_at(st, Vector((0, 0, 1)), Vector((0, 0, 1)))
q = Quaternion(st.rotation)
check('click on the top of the cube: the long box lies flat on it, its +X face down, 25 % of 0.4 in',
      (q @ Vector((1, 0, 0)) - Vector((0, 0, -1))).length < 1e-6 and abs(st.location[2] - (1.0 + 0.2 - 0.1)) < 1e-6,
      (tuple(st.location), q))
msg = pp.commit(C, st, subtract=True)
zs = sorted({round(v.co.z, 4) for v in cube.data.vertices})
check('Subtract: a stamp 0.1 deep in the shape of that face (a 1.2 long slot), closed mesh',
      0.9 in zs and non_manifold(cube) == 0 and 'subtracted' in msg, (zs, msg))
xs = [v.co for v in cube.data.vertices if abs(v.co.z - 0.9) < 1e-4]
check('... the slot is as long as the box (1.2) and as wide as it (0.4)',
      abs(max(abs(c.x) for c in xs) * 2 - 0.4) < 1e-3 and abs(max(abs(c.y) for c in xs) * 2 - 1.2) < 1e-3
      or abs(max(abs(c.y) for c in xs) * 2 - 0.4) < 1e-3 and abs(max(abs(c.x) for c in xs) * 2 - 1.2) < 1e-3,
      [tuple(c) for c in xs])
st.stamp_depth = 0.0
pp.stamp_at(st, Vector((1, 0, 0)), Vector((1, 0, 0)))
n0 = len(cube.data.vertices)
pp.commit(C, st, subtract=False)
check('Add on the side: merged into the cube (a hair in, no face lying on the surface), closed',
      len(C.scene.objects) == 1 and non_manifold(cube) == 0 and max(v.co.x for v in cube.data.vertices) > 1.3,
      (len(C.scene.objects), max(v.co.x for v in cube.data.vertices)))
# Remember Turn
st.contact_on = False
st.rotation, st.surface_set, st.remember_turn = (1, 0, 0, 0), False, True
st.rotation = pp.surface_turn(st, Vector((0, 0, 1)))                    # first click on the top: Z up
check('first click: Z straight out of the surface', (Quaternion(st.rotation) @ Vector((0, 0, 1)) - Vector((0, 0, 1))).length < 1e-6)
tilt = Quaternion(Vector((1, 0, 0)), math.radians(30)) @ Quaternion(Vector((0, 0, 1)), math.radians(45))
st.rotation = tilt                                                      # the user turns it on the top
st.rotation = pp.surface_turn(st, Vector((0, 0, 1)))                    # next click on the same top
check('next click on a surface facing the same way: the same turn as before',
      Quaternion(st.rotation).rotation_difference(tilt).angle < 1e-5)
st.rotation = pp.surface_turn(st, Vector((1, 0, 0)))                    # then on the side (+X)
side = pp.align_rotation(Vector((1, 0, 0)))
check('on the side: the same turn against that surface (tilted 30 degrees off its normal the same way)',
      abs((Quaternion(st.rotation) @ Vector((0, 0, 1))).angle(Vector((1, 0, 0))) - math.radians(30)) < 1e-5
      and Quaternion(st.rotation).rotation_difference(side @ tilt).angle < 1e-5)
st.remember_turn = False
st.rotation = pp.surface_turn(st, Vector((0, 0, 1)))
check('Remember Turn off: Z straight out again', (Quaternion(st.rotation) @ Vector((0, 0, 1)) - Vector((0, 0, 1))).length < 1e-6)
st.remember_turn = True
st.rotation = tilt
bpy.ops.mch.place_rotate(axis='RESET')
st.rotation = pp.surface_turn(st, Vector((0, 1, 0)))
check('Turn Reset: the next click starts straight again', (Quaternion(st.rotation) @ Vector((0, 0, 1)) - Vector((0, 1, 0))).length < 1e-6)
check('the panel and the Alt+click stamp key are there', hasattr(bpy.ops.mch, 'place_pick_face') and any(
      k[0] == 'mch.place_click' and k[1].get('alt') for k in pp.TOOL_KEYMAP))
summary()
