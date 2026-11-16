"""0.24.179 Face Pop (user, a faceted rock in Edit Mode: "내가 선택한 면이 튀어나오게 하는 것도 만들어 주라"): faces of a part
picked stand out - Height high, sides slanting in by Taper; side by side together, Each Face apart; Alt: off; faces
picked in Edit Mode too; live until Apply; the part's own mesh untouched."""
import numpy as np
from _harness import bpy, check, fresh, summary

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import face_pop as fp, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check(f'the tool: a tile in Surface detail ({ts.TOOL_BY_ID["FPOP"][5]})',
      ts.TOOL_BY_ID['FPOP'][5] == 'mecha.face_pop' and 'FPOP' in dict(ts.TOOL_GROUPS)['Surface detail'])
bpy.ops.mesh.primitive_cube_add(size=2.0)
box = C.active_object
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=1)                   # (each side 4 faces)
bpy.ops.object.mode_set(mode='OBJECT')
me0 = len(box.data.polygons)
top = [p.index for p in box.data.polygons if p.normal.z > 0.9]
S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.3, 0.3, False


def ev():
    dg = C.evaluated_depsgraph_get()
    dg.update()
    e = box.evaluated_get(dg)
    P = np.array([tuple(v.co) for v in e.data.vertices])
    return P, len(e.data.polygons)


fp.set_faces(box, top[:2], True, S.mch_pop)
P, nf = ev()
check(f'two top faces side by side picked: out together, 0.3 high (top {P[:, 2].max():.3f}), the part\'s own mesh as '
      f'it was ({len(box.data.polygons)} faces; shown {nf})', abs(P[:, 2].max() - 1.3) < 1e-4
      and len(box.data.polygons) == me0 and nf > me0)
tops = P[np.abs(P[:, 2] - 1.3) < 1e-4]
check(f'Taper 0.3: its top smaller than its foot (top {np.ptp(tops[:, 0]):.2f} x {np.ptp(tops[:, 1]):.2f}, the two '
      f'faces 2.00 x 1.00 or 1.00 x 2.00)', 0.6 < max(np.ptp(tops[:, 0]), np.ptp(tops[:, 1])) < 1.6)
box.mch_pop.each = True
P2, nf2 = ev()
check(f'Each Face: apart (shown faces {nf} -> {nf2})', nf2 > nf)
box.mch_pop.height = 0.5
P3, _n = ev()
check(f'live: Height 0.5 (top {P3[:, 2].max():.3f})', abs(P3[:, 2].max() - 1.5) < 1e-4)
fp.set_faces(box, top[:2], False)
check('Alt (off): both taken off - no modifier left', box.modifiers.get(fp.MOD) is None and not fp.picked(box.data).any())
# Edit Mode selection
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(box.data)
for f in bm.faces:
    f.select_set(f.normal.x > 0.9)
bmesh.update_edit_mesh(box.data)
bpy.ops.object.mode_set(mode='OBJECT')
r = bpy.ops.mch.face_pop_from_edit()
P4, _n = ev()
check(f'From Edit Mode Selection: the right side\'s faces out ({r}, x up to {P4[:, 0].max():.3f})',
      r == {'FINISHED'} and P4[:, 0].max() > 1.2)
C.view_layer.objects.active = box
r = bpy.ops.mch.face_pop_apply()
check(f'Apply: into the mesh ({r}, {len(box.data.polygons)} faces), no modifier, no attribute',
      r == {'FINISHED'} and box.modifiers.get(fp.MOD) is None and len(box.data.polygons) > me0
      and box.data.attributes.get(fp.ATTR) is None)
summary()
