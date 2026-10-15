"""0.23.8: Pinch 1 (big folds) / Pinch 2 (small folds) on separate sliders; Panel Cloth - a short
cloth simulation (pressure / shrink / pinned border / body collider) baked into a new _PCloth object."""
import math
import sys

_src = open(__file__.replace('test_v0238.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_sim as sim, cloth_wrinkle as cw, last_used
last_used.forget('wrinkle')

# ---- Pinch 1 / Pinch 2
check('Pinch 2 input + two HUD sliders (big / small folds)', any(x[0] == 'Pinch 2' for x in cw.INPUTS) and
      {'pinch', 'pinch2'} <= {k[0] for k in cw.SLIDERS} and 'Pinch 2' in cw.SIZE_INPUTS and
      {'pinch', 'pinch2'} <= set(cw.slider_keys(None)))
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.wtype = 'DENIM'
box = cube('Box', 4.0)
r, m = lasso([(340, 330), (660, 330), (665, 670), (335, 670)])
ob = C.active_object
gi = cw.get_input
check('new layers start with Pinch 2 = half of Pinch 1 (0.23.11: calmer small fans)',
      abs(gi(ob, 'Pinch 2') - gi(ob, 'Pinch') * 0.5) < 1e-9 and gi(ob, 'Pinch') > 0)


def evz(o):
    dg = C.evaluated_depsgraph_get()
    return np.array([v.co.z for v in o.evaluated_get(dg).data.vertices])


cw.set_input(ob, 'Fan Mix', 1.0)
base = evz(ob)
p1 = gi(ob, 'Pinch')
cw.set_input(ob, 'Pinch 2', 0.0)
no_small = evz(ob)
cw.set_input(ob, 'Pinch 2', p1)
cw.set_input(ob, 'Pinch', 0.0)
no_big = evz(ob)
check('Pinch 2 alone changes the small folds', np.abs(base - no_small).max() > 1e-5)
check('Pinch 1 alone changes the big folds', np.abs(base - no_big).max() > 1e-5)
check('the two act on different folds', np.abs(no_small - no_big).max() > 1e-5)
cw.set_input(ob, 'Pinch', p1)

# ---- Panel Cloth (Blender's own cloth solver, short sim, baked)
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 30, 0))
body = C.active_object
bpy.ops.mesh.primitive_grid_add(x_subdivisions=12, y_subdivisions=12, size=1.6, location=(0, 30, 1.001))
pan = C.active_object
nb_mods = len(body.modifiers)
out = sim.panel_cloth(C, [pan], frames=20, pressure=4.0, shrink=-0.05, cuts=2)
pc = out[0]
check('Panel Cloth: a new _PCloth object, the source only hidden', len(out) == 1 and pc.name.endswith(sim.SUFFIX)
      and pan.name in bpy.data.objects and pan.hide_get() and pan.hide_render)
check('baked: no cloth modifier left, a Subdivision modifier on top', not any(m.type == 'CLOTH' for m in pc.modifiers)
      and any(m.type == 'SUBSURF' for m in pc.modifiers))
check('subdivided before the sim (Cuts)', len(pc.data.vertices) > 169 * 4, len(pc.data.vertices))
z = np.array([(pc.matrix_world @ v.co).z for v in pc.data.vertices])
bd = set(sim.build_cloth_mesh([([pan.matrix_world @ v.co for v in pan.data.vertices],
                                [tuple(p_.vertices) for p_ in pan.data.polygons])], 2)[1])
check('Pressure puffs the panel up, the pinned border stays', z.max() > 1.05 and
      abs(min(z[i] for i in bd) - 1.001) < 0.02, (round(float(z.max()), 3)))
check('not through the body (collider)', z.min() > 0.95, round(float(z.min()), 3))
check('the body got its temporary collider removed again', len(body.modifiers) == nb_mods)
check('cloth helpers: collider of a cloth layer = its body', sim.collider_for(ob) == box)
# Through halves on one body join into one cloth ring
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=1.0, depth=6.0, location=(0, 40, 0),
                                    rotation=(0, math.pi / 2, 0))
cyl = C.active_object
VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((0, 40, 0)))
S.mch_brush.through_mode = True
r, m = lasso([(400, 300), (600, 300), (600, 700), (400, 700)])
S.mch_brush.through_mode = False
halves = [o for o in C.selected_objects if cw.is_wrinkle(o)]
out = sim.panel_cloth(C, halves, frames=10, pressure=2.0, shrink=-0.1, cuts=1)
check('Through front + back -> one joined cloth around the cylinder', len(halves) == 2 and len(out) == 1, len(out))
ring = out[0]
import bmesh as _bm
bmr = _bm.new()
bmr.from_mesh(ring.data)
loops = len({frozenset(v.index for v in e.verts) for e in bmr.edges if e.is_boundary})
ys = [(ring.matrix_world @ v.co).x for v in bmr.verts if v.is_boundary]
bmr.free()
check('the seams are welded: only the two sleeve ends are open', max(ys) - min(ys) > 1.5 and
      all(abs(abs(x) - 1.0) < 0.1 for x in ys), (round(min(ys), 3), round(max(ys), 3)))
# operator
for o in C.selected_objects:
    o.select_set(False)
ob.hide_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
res = bpy.ops.mch.panel_cloth(frames=5, cuts=1)
check('Panel Cloth operator', res == {'FINISHED'} and C.active_object.name.endswith(sim.SUFFIX))
# edit mode: selected faces
bpy.ops.mesh.primitive_grid_add(x_subdivisions=6, y_subdivisions=6, size=1.0, location=(0, 50, 0))
g = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
res = bpy.ops.mch.panel_cloth(frames=5, cuts=1, collider='NONE')
check('Panel Cloth from selected faces (Edit Mode)', res == {'FINISHED'} and C.mode == 'OBJECT' and
      C.active_object.name == g.name + sim.SUFFIX)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
