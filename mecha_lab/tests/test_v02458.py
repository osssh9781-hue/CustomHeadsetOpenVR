"""0.24.40 Path Move Hardness (like Concept Move) in Extend: 1 = hard (the section runs straight out of the cut,
as before); lower = the mesh round the grab is pulled out with the start of the path and fades out (a soft
collar).  The Path Move panel has its own Hardness (Concept Move's is unchanged)."""
import inspect
import json

from _harness import bpy, check, fresh, summary
import bmesh
import numpy as np
from mathutils import Vector

import mecha_lab
from mecha_lab import concept_move as cm, path_sweep as ps

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_concept
check('Path Move has its own Hardness (1 = hard, as before); Move keeps its own', hasattr(st, 'path_hardness')
      and st.path_hardness == 1.0 and abs(st.hardness - 0.5) < 1e-6)
check('the Path Move panel shows it', "'path_hardness'" in inspect.getsource(cm.draw_path))
P = [Vector((0.1 * i, 0, 0.1 * i)) for i in range(12)]          # a path going up at 45 degrees from the start
soft = ps.soften_path(P, Vector((1, 0, 0)), 0.6)
d0 = (soft[1] - soft[0]).normalized()
check('soft start: leaves the cut along the part (not at 45 degrees), same points, the far part unchanged',
      len(soft) == len(P) and d0.x > 0.9 and all((a - b).length < 1e-9 for a, b in zip(soft[8:], P[8:]))
      and (soft[0] - P[0]).length < 1e-9, d0)
check('Hardness 1 = no soft start', ps.soft_length([Vector((0, 1, 0))], Vector(), 1.0) == 0.0
      and abs(ps.soft_length([Vector((0, 1, 0))], Vector(), 0.5) - 1.5) < 1e-9)

def bar(name):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(0, 0, 0), scale=(3.0, 0.5, 0.5))
    o = C.active_object
    o.name = name
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=11)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def solid(me):
    b = bmesh.new()
    b.from_mesh(me)
    nm = sum(not e.is_manifold for e in b.edges)
    vol = b.calc_volume(signed=True)
    b.free()
    return nm, vol


OFFS = [[0.08 * i, 0, 0.08 * i] for i in range(16)]       # up at 45 degrees right from the cut
res = {}
for name, h in (('Hard', 1.0), ('Soft', 0.3)):
    o = bar(name)
    before = cm.read_coords(o.data).copy()
    r = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', objects=json.dumps([name]), grab_point=(0.9, 0, 0),
                                 grab_normal=(1, 0, 0), offsets=json.dumps(OFFS), edge_hardness=h)
    co = cm.read_coords(o.data)
    keep = before[before[:, 0] < 0.85]                     # the old points behind the cut
    moved = co[:len(before)][before[:, 0] < 0.85] - keep
    res[name] = (r, solid(o.data), np.abs(moved).max(axis=1), keep, co)
r, (nm, vol), mv, keep, co = res['Hard']
check('Hardness 1: one closed mesh, the mesh behind the cut stays (as before)', r == {'FINISHED'} and nm == 0
      and vol > 0 and mv.max() < 1e-6, (nm, vol, mv.max()))
hard_co = co
r, (nm, vol), mv, keep, co = res['Soft']
check('Hardness 0.3: one closed mesh, the mesh behind the cut still stays', r == {'FINISHED'} and nm == 0
      and vol > 0 and mv.max() < 1e-6, (nm, vol, mv.max()))


win = lambda c: c[(c[:, 0] > 0.95) & (c[:, 0] < 1.3)][:, 2].mean()      # the tube right after the cut (x 0.9)
low_h, low_s = win(hard_co), win(co)
check('... and right after the cut it bends up gently (lower there than the hard kink), a soft curve',
      low_s < low_h - 0.05, (low_h, low_s))
check('... the end still goes to the end of the path', (co.max(axis=0) - hard_co.max(axis=0)).__abs__().max() < 0.05,
      (co.max(axis=0), hard_co.max(axis=0)))
summary()
