"""0.24.33 Path Move methods: Extend (cut where you grab, sweep the section, carry the end - one clean mesh) and
Separate Tube (a new object, Merge = Join / Union); both light; Stretch kept."""
import json
import math
import time

from _harness import bpy, check, fresh, summary
import bmesh
import numpy as np
from mathutils import Matrix, Vector

import mecha_lab
from mecha_lab import concept_move as cm, path_sweep as ps

mecha_lab.register()
fresh()
C = bpy.context
check('Extend is the default Path Move method', C.scene.mch_concept.path_method == 'EXTEND')
r = ps.min_rotation(Vector((1, 0, 0)), Vector((0, 0, 1)))
check('smallest turn between two directions', (r @ Vector((1, 0, 0)) - Vector((0, 0, 1))).length < 1e-6)
path = [Vector((i * 0.5, 0, 0)) for i in range(4)] + [Vector((1.5, 0, 0.5 * k)) for k in range(1, 4)]
fr = ps.sweep_frames(path, Vector((1, 0, 0)), True)
check('frames turn with the path (ends pointing up)', (fr[-1] @ Vector((1, 0, 0)) - Vector((0, 0, 1))).length < 1e-6)
check('Follow Turns off: no turning', all((f @ Vector((1, 0, 0)) - Vector((1, 0, 0))).length < 1e-9
                                          for f in ps.sweep_frames(path, Vector((1, 0, 0)), False)))
check('loop order from edges', ps.order_loop([(0, 1), (2, 3), (1, 2), (3, 0)]) in ([0, 1, 2, 3], [0, 3, 2, 1])
      and ps.order_loop([(0, 1), (1, 2)]) is None)
sq = [Vector((0, 1, 1)), Vector((0, -1, 1)), Vector((0, -1, -1)), Vector((0, 1, -1))]
check('loop direction seen from the drag direction', ps.ccw(sq, Vector((1, 0, 0))) != ps.ccw(sq[::-1], Vector((1, 0, 0))))


def grid_cube(name, loc, size=2.0, cuts=3):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    o = C.active_object
    o.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def solid_ok(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    nm = sum(not e.is_manifold for e in bm.edges)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return nm, vol


offs = [[0.3 * i, 0, 0] for i in range(6)] + [[1.5 + 0.3 * i, 0, 0.3 * i] for i in range(1, 5)]
o = grid_cube('Ext', (0, 0, 0))
n0 = len(o.data.vertices)
info = ps.analyse(o.data, (0.6, 0, 0), (1, 0, 0))
check('the section where you grab is read (a closed loop) with the cut-off end', info is not None
      and len(info['loop']) >= 8 and info['tip'] is not None and abs(info['centre'].x - 0.6) < 1e-6)
t = time.time()
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', objects=json.dumps(['Ext']), grab_point=(0.6, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps(offs))
dt = time.time() - t
nm, vol = solid_ok(o.data)
co = cm.read_coords(o.data)
check('Extend: one closed mesh, outward faces', res == {'FINISHED'} and nm == 0 and vol > 0, (nm, vol))
check('Extend: it goes along the path and up the bend', co[:, 0].max() > 3.5 and co[:, 2].max() > 2.0,
      (co[:, 0].max(), co[:, 2].max()))
check('Extend: light - few new points (rings only), quick', len(co) < n0 * 4 and dt < 1.0, (n0, len(co), dt))
ys = co[(co[:, 0] > 1.3) & (co[:, 0] < 1.9)][:, 1]
check('Extend: the section keeps its size along the way (no thinning, no stretching)', abs(np.ptp(ys) - 2.0) < 1e-4,
      float(np.ptp(ys)))
tan = np.array([1.0, 0.0, 1.0]) / math.sqrt(2.0)                # the last step of the path goes up at 45 degrees
d = co @ tan
check('Extend: the original end is carried to the end of the path, its flat side facing the new way',
      int((d > d.max() - 1e-4).sum()) >= 9, int((d > d.max() - 1e-4).sum()))

# taper
o2 = grid_cube('ExtT', (10, 0, 0))
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', objects=json.dumps(['ExtT']), grab_point=(0.6, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps([[0.4 * i, 0, 0] for i in range(6)]), taper=0.5)
c2 = cm.read_coords(o2.data)
tip = c2[c2[:, 0] > c2[:, 0].max() - 0.05]
check('Taper: the end is smaller', res == {'FINISHED'} and np.ptp(tip[:, 1]) < 1.2, float(np.ptp(tip[:, 1])))

# Separate Tube + Merge
o3 = grid_cube('Src', (20, 0, 0))
nsrc = len(o3.data.vertices)
before = set(bpy.data.objects)
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='SWEEP', objects=json.dumps(['Src']), grab_point=(0.6, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps(offs))
new = [x for x in bpy.data.objects if x not in before]
tube = new[0] if new else None
check('Separate Tube: a new object, the mesh untouched', res == {'FINISHED'} and tube is not None
      and len(o3.data.vertices) == nsrc and tube.get(ps.SOURCE_KEY) == 'Src')
nm, vol = solid_ok(tube.data) if tube else (1, 0)
check('Separate Tube: a closed tube (capped)', nm == 0 and vol > 0, (nm, vol))
C.view_layer.objects.active = tube
res = bpy.ops.mch.path_merge(mode='JOIN')
check('Merge Join: one object', res == {'FINISHED'} and 'Src_Path' not in bpy.data.objects
      and len(o3.data.vertices) > nsrc)
o4 = grid_cube('SrcU', (30, 0, 0))
bpy.ops.mch.concept_path('EXEC_DEFAULT', method='SWEEP', objects=json.dumps(['SrcU']), grab_point=(0.6, 0, 0),
                         grab_normal=(1, 0, 0), offsets=json.dumps(offs))
C.view_layer.objects.active = bpy.data.objects['SrcU_Path']
res = bpy.ops.mch.path_merge(mode='UNION')
nm, vol = solid_ok(o4.data)
check('Merge Union: one closed surface', res == {'FINISHED'} and 'SrcU_Path' not in bpy.data.objects and nm == 0
      and cm.read_coords(o4.data)[:, 0].max() > 3.5, nm)

# Extend on an open sheet falls back to a Separate Tube
bpy.ops.mesh.primitive_grid_add(size=2, x_subdivisions=6, y_subdivisions=6, location=(40, 0, 0))
g = C.active_object
g.name = 'Sheet'
before = set(bpy.data.objects)
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', objects=json.dumps(['Sheet']), grab_point=(0.5, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps(offs))
check('no closed section: tells and changes nothing', res == {'CANCELLED'} and set(bpy.data.objects) == before)

# editable (Auto Apply off) Extend: Undo Last / Clear
o5 = grid_cube('ExtE', (50, 0, 0))
orig = cm.read_coords(o5.data).copy()
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', objects=json.dumps(['ExtE']), grab_point=(0.6, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps(offs), auto_apply=False)
check('Extend, Auto Apply off: remembered', res == {'FINISHED'} and cm.has_base(o5) and len(cm.recorded_moves(o5)) == 1)
C.view_layer.objects.active = o5
bpy.ops.mch.concept_clear()
now = cm.read_coords(o5.data)
check('Clear: back to the mesh before', now.shape == orig.shape and np.allclose(now, orig))

# a big mesh: Extend stays quick (only the grabbed part is cut)
bpy.ops.mesh.primitive_uv_sphere_add(segments=256, ring_count=128, radius=1.0, location=(60, 0, 0))
big = C.active_object
big.name = 'Big'
t = time.time()
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='SWEEP', objects=json.dumps(['Big']), grab_point=(0.0, 0, 0),
                               grab_normal=(1, 0, 0), offsets=json.dumps(offs))
check(f'big mesh ({len(big.data.vertices)} points): Separate Tube in about a second', res == {'FINISHED'}
      and time.time() - t < 3.0, round(time.time() - t, 2))
summary()
