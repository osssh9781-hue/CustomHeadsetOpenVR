"""0.24.32 Concept Move / Path Move panel like Cut: Through All / From Surface, Auto Target / Selected Only / Active,
Auto Apply off = editable moves (Undo Last / Clear / Apply); world-space moves on rotated / scaled objects."""
import json
import math

from _harness import bpy, check, fresh, summary
import numpy as np
from mathutils import Vector

import mecha_lab
from mecha_lab import concept_move as cm

mecha_lab.register()
fresh()
C = bpy.context
st = C.scene.mch_concept
check('panel defaults: From Surface, Auto Target, Auto Apply on', (st.depth_mode, st.targets, st.auto_apply)
      == ('SURFACE', 'AUTO', True))


def cube(name, loc, size=1.0, cuts=4):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    o = C.active_object
    o.name = name
    if cuts:
        bpy.ops.object.mode_set(mode='EDIT')
        bpy.ops.mesh.subdivide(number_cuts=cuts)
        bpy.ops.object.mode_set(mode='OBJECT')
    return o


front = cube('Front', (0, -3, 0))
back = cube('Back', (0, 0, 0))
plate = cube('Plate', (0, 0.6, 0), size=0.4, cuts=2)          # sits on the back cube's +Y side
for o in C.view_layer.objects:
    o.select_set(False)
back.select_set(True)
C.view_layer.objects.active = back
ray_o, ray_d = Vector((0, -10, 0)), Vector((0, 1, 0))
g = cm.pick_grab(C, ray_o, ray_d, 'AUTO')
check('Auto Target: the first mesh under the mouse', g is not None and g[2] == front, g and g[2].name)
g = cm.pick_grab(C, ray_o, ray_d, 'ACTIVE')
check('Active: looks through other meshes to the active one', g is not None and g[2] == back
      and abs(g[0].y + 0.5) < 1e-4, g and (g[2].name, tuple(g[0])))
g = cm.pick_grab(C, ray_o, ray_d, 'SELECTED')
check('Selected Only: only selected meshes count', g is not None and g[2] == back)
check('From Surface: only the grabbed mesh', cm.grab_objects(C, back, Vector((0, 0.5, 0)), 0.5, 'AUTO', 'SURFACE') == [back])
objs = cm.grab_objects(C, back, Vector((0, 0.5, 0)), 0.5, 'AUTO', 'THROUGH')
check('Through All: also the plate inside the brush, not the far cube', back in objs and plate in objs and front not in objs,
      [o.name for o in objs])
objs = cm.grab_objects(C, back, Vector((0, 0.5, 0)), 0.5, 'SELECTED', 'THROUGH')
check('Through All + Selected Only: only selected ones', objs == [back], [o.name for o in objs])

# a move in the scene on several objects (World): both the cube and the plate on it move the same way
before = {o.name: [o.matrix_world @ v.co for v in o.data.vertices] for o in (back, plate)}
res = bpy.ops.mch.concept_move('EXEC_DEFAULT', space='WORLD', objects=json.dumps(['Back', 'Plate']),
                               centre=(0, 0.5, 0), delta=(0, 0.8, 0), radius=0.5, hardness=0.9, mirror=False,
                               generate_mesh=False, axes=(1, 0, 0, 0, 1, 0, 0, 0, 1))
moved = {}
for o in (back, plate):
    after = [o.matrix_world @ v.co for v in o.data.vertices]
    moved[o.name] = max((a - b).y for a, b in zip(after, before[o.name]))
check('Through All move: the cube and the plate on it both pull out', res == {'FINISHED'}
      and moved['Back'] > 0.7 and moved['Plate'] > 0.7, moved)

# rotated + scaled object: the move happens in the scene, not in the object's own axes
rot = cube('Rot', (10, 0, 0), size=1.0, cuts=4)
rot.rotation_euler = (0, 0, math.radians(90))
rot.scale = (2, 2, 2)
C.view_layer.update()
w0 = np.array([rot.matrix_world @ v.co for v in rot.data.vertices])
tip = Vector((10, 1.0, 0))                                    # the +Y face centre in the scene
res = bpy.ops.mch.concept_move('EXEC_DEFAULT', space='WORLD', objects=json.dumps(['Rot']), centre=tip, delta=(0, 1.0, 0),
                               radius=0.6, hardness=0.9, mirror=False, generate_mesh=False)
C.view_layer.update()
w1 = np.array([rot.matrix_world @ v.co for v in rot.data.vertices])
d = w1 - w0
check('rotated / scaled object: pulled along the scene Y by the scene distance', res == {'FINISHED'}
      and abs(d[:, 1].max() - 1.0) < 1e-3 and abs(d[:, 0]).max() < 1e-3, (float(d[:, 1].max()), float(abs(d[:, 0]).max())))

# Auto Apply off: the moves stay editable
ed = cube('Edit', (20, 0, 0), cuts=4)
orig = cm.read_coords(ed.data).copy()
kw = dict(space='WORLD', objects=json.dumps(['Edit']), radius=0.4, hardness=0.9, mirror=False, generate_mesh=True,
          auto_apply=False)
bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(20.5, 0, 0), delta=(0.6, 0, 0), **kw)
after1 = cm.read_coords(ed.data).copy()
bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(20, 0, 0.5), delta=(0, 0, 0.6), **kw)
check('Auto Apply off: the mesh before is kept, both moves remembered', cm.has_base(ed) and len(cm.recorded_moves(ed)) == 2)
C.view_layer.objects.active = ed
res = bpy.ops.mch.concept_undo_last()
now = cm.read_coords(ed.data)
check('Undo Last: only the second move is taken back', res == {'FINISHED'} and len(cm.recorded_moves(ed)) == 1
      and now.shape == after1.shape and np.allclose(now, after1, atol=1e-5), (now.shape, after1.shape))
res = bpy.ops.mch.concept_clear()
now = cm.read_coords(ed.data)
check('Clear: back to the mesh before the moves, nothing kept', res == {'FINISHED'} and now.shape == orig.shape
      and np.allclose(now, orig, atol=1e-6) and not cm.has_base(ed) and cm.MOVES_KEY not in ed)
nb = len(bpy.data.meshes)
bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(20.5, 0, 0), delta=(0.6, 0, 0), **kw)
res = bpy.ops.mch.concept_bake()
check('Apply: the move stays, the kept mesh is gone', res == {'FINISHED'} and not cm.has_base(ed)
      and cm.MOVES_KEY not in ed and len(bpy.data.meshes) == nb and cm.read_coords(ed.data)[:, 0].max() > 0.9)
ap = cube('AutoOn', (30, 0, 0))
bpy.ops.mch.concept_move('EXEC_DEFAULT', space='WORLD', objects=json.dumps(['AutoOn']), centre=(30.5, 0, 0),
                         delta=(0.5, 0, 0), radius=0.4, hardness=0.9, mirror=False, generate_mesh=False, auto_apply=True)
check('Auto Apply on: nothing extra kept (as before)', not cm.has_base(ap) and cm.MOVES_KEY not in ap)

# Path Move on several objects in the scene (Through All)
pa = cube('PathA', (40, 0, 0), cuts=6)
pb = cube('PathB', (40, 0.6, 0), size=0.4, cuts=2)
path = [(40, 0.5, 0), (40, 0.9, 0), (40, 1.3, 0), (40, 1.7, 0)]
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', space='WORLD', objects=json.dumps(['PathA', 'PathB']),
                               path=json.dumps([list(p) for p in path]), radius=0.35, hardness=0.9, mirror=False,
                               generate_mesh=True, axes=(1, 0, 0, 0, 1, 0, 0, 0, 1))
ya = max((pa.matrix_world @ v.co).y for v in pa.data.vertices)
yb = max((pb.matrix_world @ v.co).y for v in pb.data.vertices)
check('Path Move, Through All: both meshes follow the path', res == {'FINISHED'} and ya > 1.5 and yb > 1.6, (ya, yb))
pe = cube('PathEdit', (50, 0, 0), cuts=6)
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', space='WORLD', objects=json.dumps(['PathEdit']),
                               path=json.dumps([[50.5, 0, 0], [51, 0, 0], [51.5, 0, 0]]), radius=0.35, hardness=0.9,
                               mirror=False, generate_mesh=True, auto_apply=False)
check('Path Move, Auto Apply off: each step remembered (Undo Last / Clear work on it)', res == {'FINISHED'}
      and cm.has_base(pe) and len(cm.recorded_moves(pe)) >= 2)
from mecha_lab import ui_tool_settings as uts
check('the panel draws the Cut-style options for both tools', 'draw_targets' in dir(cm) and 'CMOVE' in uts.DRAWERS
      and 'CPATH' in uts.DRAWERS)
summary()
