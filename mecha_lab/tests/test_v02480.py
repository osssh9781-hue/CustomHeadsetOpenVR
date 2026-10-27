"""0.24.58 Path Move Back Mask: the far side of a thin part (faces turned away from you) stays put.
Stretch: the move is held back by how much each point faces you.  Extend Brush: no fall back to the whole section
(a smaller brush is tried, else nothing is changed)."""
import inspect
import json

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
import numpy as np
from mathutils import Vector

import mecha_lab
from mecha_lab import concept_move as cm, key_legend, path_sweep as ps

mecha_lab.register()
fresh()
C = bpy.context
st = C.scene.mch_concept
check('Back Mask: off by default, on the operator too (F9)', st.path_back_mask is False
      and 'back_mask' in bpy.ops.mch.concept_path.get_rna_type().properties)
w = cm.facing_weights([(0, 0, 1), (0, 0, -1), (1, 0, 0), (0, 0.6, 0.8)], (0, 0, 2))
check('Facing weights: facing you 1, the far side 0, side-on a short ramp', w[0] == 1.0 and w[1] == 0.0
      and 0.2 < w[2] < 0.5 and w[3] == 1.0, list(w))


def plate(name='Plate', cuts=12):
    """A thin plate 2 x 2 x 0.1 (top at z 0.05, bottom at z -0.05)."""
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    for v in bm.verts:
        v.co = Vector((v.co.x * 2, v.co.y * 2, v.co.z * 0.1))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.scene.collection.objects.link(ob)
    for o in C.scene.objects:
        if o is not None:
            o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return ob


def bottom_moved(ob, before):
    co = cm.read_coords(ob.data)[:len(before)]
    low = before[:, 2] < 0
    return float(np.abs(co[low] - before[low]).max())


def top_moved(ob, before):
    co = cm.read_coords(ob.data)[:len(before)]
    high = before[:, 2] > 0
    return float(np.abs(co[high] - before[high]).max())


# Stretch: a path from the top middle upward - the radius (0.4) reaches through the 0.1 thick plate
path = json.dumps([[0, 0, 0.05], [0, 0, 0.25], [0, 0, 0.45]])
for mask in (False, True):
    ob = plate(f'S{int(mask)}')
    before = cm.read_coords(ob.data)
    res = bpy.ops.mch.concept_path('EXEC_DEFAULT', path=path, radius=0.4, method='STRETCH', mirror=False,
                                   generate_mesh=True, back_mask=mask, toward=(0, 0, 1))
    if mask:
        check('Stretch + Back Mask: the top is pulled, the bottom (far side) stays put, still closed',
              res == {'FINISHED'} and top_moved(ob, before) > 0.2 and bottom_moved(ob, before) < 1e-6
              and non_manifold(ob) == 0, (top_moved(ob, before), bottom_moved(ob, before)))
    else:
        check('Stretch without it: the bottom is dragged along too (what the mask is for)',
              res == {'FINISHED'} and bottom_moved(ob, before) > 0.1, bottom_moved(ob, before))
    bpy.data.objects.remove(ob)

# the record keeps the mask for a rebuild (Auto Apply off = editable moves)
ob = plate('Rec')
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', path=path, radius=0.4, method='STRETCH', mirror=False,
                               generate_mesh=True, back_mask=True, toward=(0, 0, 1), auto_apply=False)
rec = cm.recorded_moves(ob)
after = cm.read_coords(ob.data)
cm.rebuild_from_base(ob, rec)
check('Auto Apply off: the move remembers the mask; rebuilt the same', res == {'FINISHED'} and rec
      and rec[-1].get('back') and np.allclose(cm.read_coords(ob.data), after, atol=1e-5), rec and rec[-1].keys())
bpy.data.objects.remove(ob)

# Extend Brush: no whole section when the patch fails
calls = []
real_patch = ps._patch


def failing(limit):
    def f(bm, hit, drag, radius, sides=8):
        calls.append(round(radius, 4))
        return None if radius > limit else real_patch(bm, hit, drag, radius, sides)
    return f


ob = plate('E')
me = ob.data
ps._patch = failing(0.0)
try:
    a0 = ps.analyse(me, (0.5, 0, 0.05), Vector((1, 0, 0)), 0.3, 8)        # dragged along the plate
    calls.clear()
    a1 = ps.analyse(me, (0.5, 0, 0.05), Vector((1, 0, 0)), 0.3, 8, front_only=True)
    check('A brush patch that fails: without the mask the whole section, with it nothing (3 brush sizes tried)',
          a0 is not None and a0['area'] == 'SECTION' and a1 is None and calls == [0.3, 0.21, 0.15], (a0 and a0['area'],
                                                                                                   calls))
    ps._patch = failing(0.25)
    calls.clear()
    a2 = ps.analyse(me, (0, 0, 0.05), Vector((0, 0, 1)), 0.3, 8, front_only=True)
    check('... a smaller brush that works is used (the mesh read again first, not left half cut)',
          a2 is not None and a2['area'] == 'BRUSH' and calls == [0.3, 0.21] and len(a2['loop']) >= 8, calls)
    n_obj = len(bpy.data.objects)
    ps._patch = failing(0.0)
    v0 = len(me.vertices)
    res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='BRUSH', back_mask=True, objects='["E"]',
                                   grab_point=(0, 0, 0.05), grab_normal=(0, 0, 1), radius=0.3, size=1.0,
                                   offsets=json.dumps([[0, 0, 0], [0, 0, 0.2], [0, 0, 0.4]]))
    check('Extend: nothing is changed and no Separate Tube (that would take the whole section)',
          res == {'CANCELLED'} and len(bpy.data.objects) == n_obj and len(me.vertices) == v0)
finally:
    ps._patch = real_patch
before = cm.read_coords(me)
res = bpy.ops.mch.concept_path('EXEC_DEFAULT', method='EXTEND', area='BRUSH', back_mask=True, objects='["E"]',
                               grab_point=(0, 0, 0.05), grab_normal=(0, 0, 1), radius=0.3, size=1.0,
                               offsets=json.dumps([[0, 0, 0], [0, 0, 0.2], [0, 0, 0.4]]))
co = cm.read_coords(me)
check('Extend Brush + Back Mask on a thin plate: pulled out of the top, the bottom untouched, closed',
      res == {'FINISHED'} and co[:, 2].max() > 0.4 and co[:, 2].min() > -0.0501 and non_manifold(ob) == 0,
      (co[:, 2].max(), co[:, 2].min()))
src = inspect.getsource(cm.MCH_OT_concept_path.modal)
check('While dragging: B turns it on / off; the header and key legend say so',
      "event.type == 'B'" in src and 'Back Mask' in inspect.getsource(cm.MCH_OT_concept_path._header)
      and any('Back Mask' in t for t in key_legend.EXTRA['CPATH']))
check('Panel and F9: the Back Mask button', 'path_back_mask' in inspect.getsource(cm.draw_path)
      and "'back_mask'" in inspect.getsource(cm.MCH_OT_concept_path.draw))
summary()
