"""0.23.8: Pinch 1 (big folds) / Pinch 2 (small folds) on separate sliders; Cloth Sim - a light
Geometry Nodes cloth simulation (simulation zone) that drapes a cloth layer on its body and bakes."""
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
check('new layers start with Pinch 2 = Pinch 1 (same look as before)', abs(gi(ob, 'Pinch 2') - gi(ob, 'Pinch')) < 1e-9
      and gi(ob, 'Pinch') > 0)


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

# ---- Cloth Sim (pure geometry nodes)
ng = sim.build_group()
bad = [l for l in ng.links if not l.is_valid]
check('cloth sim node group: a simulation zone, valid links', any(n.bl_idname == 'GeometryNodeSimulationOutput'
                                                                  for n in ng.nodes) and not bad, len(bad))
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(0, 30, 0))
body = C.active_object
bpy.ops.mesh.primitive_grid_add(x_subdivisions=16, y_subdivisions=16, size=1.6, location=(0, 30, 1.4))
cl = C.active_object
sim.attach(cl, body, Iterations=10, Slack=0.0, Thickness=0.02, **{'Pin Mode': 0})
check('attach: the sim modifier is first in the stack', cl.modifiers[0].name == sim.MOD and sim.has_sim(cl))
sim.simulate(C, cl, frames=24, bake=True)
z = np.array([v.co.z for v in cl.data.vertices]) + cl.location.z
check('bake: the modifier is gone, the mesh keeps the result', not sim.has_sim(cl) and len(cl.data.vertices) == 289)
check('the cloth fell and rests on the box top (not through it)', z.max() < 1.39 and z.min() > 1.0 - 0.02,
      (round(float(z.min()), 3), round(float(z.max()), 3)))
xs = np.array([v.co.x for v in cl.data.vertices])
check('edges kept their length (no blow up / no big stretch)', xs.max() - xs.min() < 1.7 and xs.max() - xs.min() > 1.3,
      round(float(xs.max() - xs.min()), 3))
check('sim helper attributes removed after the bake',
      not any(cl.data.attributes.get(n) for n in ('mch_rest', 'mch_vel', 'mch_p0', 'mch_pin', 'mch_prev')))
# pinned: the top band stays
bpy.ops.mesh.primitive_grid_add(x_subdivisions=10, y_subdivisions=10, size=1.0, location=(0, 34, 2.0),
                                rotation=(math.pi / 2, 0, 0))
hang = C.active_object
top0 = max((hang.matrix_world @ v.co).z for v in hang.data.vertices)
sim.attach(hang, None, Iterations=8, **{'Pin Mode': 2, 'Pin Width': 0.05})
sim.simulate(C, hang, frames=12, bake=True)
ws = [hang.matrix_world @ v.co for v in hang.data.vertices]
check('Pin Top: the top row stays, the rest hangs', abs(max(w.z for w in ws) - top0) < 1e-3)

# ---- the operator on a cloth plate (collider = the body it was drawn on, border pinned)
C.view_layer.objects.active = ob
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
check('collider of a cloth layer = its body', sim.collider_for(ob) == box)
nv = len(ob.data.vertices)
res = bpy.ops.mch.cloth_sim(frames=6, slack=0.15)
check('Cloth Sim operator: simulated + baked, wrinkle layer stays live', res == {'FINISHED'} and not sim.has_sim(ob)
      and cw.is_wrinkle(ob) and len(ob.data.vertices) == nv)
check('Cloth Sim turns the drawn folds off by default (the sim makes the folds)', gi(ob, 'Pinch') == 0 and
      gi(ob, 'Pinch 2') == 0)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
