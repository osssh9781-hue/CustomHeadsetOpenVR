"""0.23.26 Fold Patch: + Add on a mesh, live X / Y fold decal (handle, size, depth, wrap, taper, fade, mirror,
patterns), several per mesh, own N panel, not touched by the Cloth Plate Overall Scale."""
import math
import sys

from _harness import bpy, check, fresh, summary
import bmesh
import numpy as np
import mecha_lab

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import fold_patch as fp

bpy.ops.mesh.primitive_cylinder_add(vertices=256, radius=0.5, depth=4.0, rotation=(0, math.pi / 2, 0), end_fill_type='NOTHING')
arm = C.active_object
bm = bmesh.new()
bm.from_mesh(arm.data)
bmesh.ops.subdivide_edges(bm, edges=[e for e in bm.edges if abs(e.verts[0].co.z - e.verts[1].co.z) > 1e-6], cuts=150,
                          use_grid_fill=False)
bm.to_mesh(arm.data)
bm.free()
bpy.ops.object.transform_apply(rotation=True)
base = np.array([v.co[:] for v in arm.data.vertices])


def ev():
    dg = C.evaluated_depsgraph_get()
    dg.update()
    me = arm.evaluated_get(dg).to_mesh()
    co = np.array([v.co[:] for v in me.vertices])
    arm.evaluated_get(dg).to_mesh_clear()
    return co


S.cursor.location = (0.0, -0.6, 0.0)                 # in front of the elbow
res = bpy.ops.mch.fold_patch_add()
h = C.active_object
check('+ Add: a handle on the surface, a modifier on the mesh', res == {'FINISHED'} and fp.HANDLE_KEY in h and
      len(fp.patches_of(arm)) == 1 and abs(h.location.y + 0.5) < 0.02, tuple(h.location))
check('limb radius found -> Wrap (around the arm)', abs(h.mch_fold.wrap - 0.5) < 0.05, h.mch_fold.wrap)
co = ev()
d = np.linalg.norm(co - base, axis=1)
check('folds: the surface moves near the handle, not far away', d.max() > 0.01 and d[np.abs(base[:, 0]) > 1.8].max() < 1e-6,
      round(float(d.max()), 4))
check('the folds wrap round the arm (also on top, not only in front)', d[(base[:, 2] > 0.35)].max() > 0.002)
h.location.x = 1.0
co2 = ev()
d2 = np.linalg.norm(co2 - base, axis=1)
check('moving the handle moves the folds (live)', d2[np.abs(base[:, 0] - 1.0) < 0.3].max() > 0.01 and
      d2[np.abs(base[:, 0]) < 0.2].max() < d[np.abs(base[:, 0]) < 0.2].max() * 0.5)
h.location.x = 0.6
h.mch_fold.mirror = True
d3 = np.linalg.norm(ev() - base, axis=1)
check('Mirror X: the same folds on the other side', d3[np.abs(base[:, 0] + 0.6) < 0.3].max() > 0.01)
h.mch_fold.mirror = False
before = ev()
h.mch_fold.taper = 0.7
check('Taper "<" changes the folds', np.abs(ev() - before).max() > 1e-4)
nrm = np.array([v.normal[:] for v in arm.data.vertices])
out_before = float(((ev() - base) * nrm).sum(1).max())
h.mch_fold.depth = -h.mch_fold.depth
out_after = float(((ev() - base) * nrm).sum(1).min())
check('negative Depth: the folds go in instead of out', out_after < -0.5 * out_before, (round(out_before, 4), round(out_after, 4)))
h.mch_fold.depth = -h.mch_fold.depth
key0 = h['mch_fold_baked']
C.view_layer.objects.active = h
bpy.ops.mch.fold_patch_pattern(step=1)
check('pattern arrows: next pattern (flipped first), image baked again', h['mch_fold_baked'] != key0, h['mch_fold_baked'])
# a second patch, and Overall Scale of a Cloth Plate has nothing to do with these
C.view_layer.objects.active = arm
S.cursor.location = (-1.2, -0.6, 0.0)
bpy.ops.mch.fold_patch_add()
check('several patches on one mesh', len(fp.patches_of(arm)) == 2)
check('own sidebar panel (not the main Cloth Plate one)', fp.MCH_PT_fold_patch.bl_label == 'Fold Patch' and
      fp.MCH_PT_fold_patch.bl_category == 'Mecha Lab' and not hasattr(fp.MCH_PT_fold_patch, 'bl_parent_id'))
from mecha_lab import cloth_wrinkle as cw
check('not part of the Cloth Plate inputs (Overall Scale leaves it alone)', not any(n.startswith('Fold Patch') for n in cw.INPUT_NAMES))
h2 = C.active_object
n2 = h2.name
bpy.ops.mch.fold_patch_remove(name=n2)
check('remove one patch: its handle and modifier go', len(fp.patches_of(arm)) == 1 and n2 not in bpy.data.objects)
C.view_layer.objects.active = arm
bpy.ops.mch.fold_patch_apply()
check('Apply: folds baked into the mesh, no patch left', not fp.patches_of(arm) and
      np.linalg.norm(np.array([v.co[:] for v in arm.data.vertices]) - base, axis=1).max() > 0.005)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
