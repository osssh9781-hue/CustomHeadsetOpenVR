"""0.24.179 Face Pop (user, a faceted rock in Edit Mode: "내가 선택한 면이 튀어나오게 하는 것도 만들어 주라"): faces of a
part picked stand out - Height high, sides slanting in by Taper; side by side together, Each Face apart; Alt: off.
0.24.180 two ways (user: "페이스 팝은 별개의 메쉬로 분리되어야지" - "그냥 페이스 팝도 나쁘지 않으니까 유지하고 스플릿
버전도"): In the Part (as 0.24.179) - and Split: the picked faces make a part of their own - a new object, a closed piece, the part's child with its materials - the part itself not touched; more
faces into the same piece, Alt takes them off (none left: the piece goes); Edit Mode selection: a new piece; Apply: a
plain mesh, still its own object."""
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
red = bpy.data.materials.new('Red')
box.data.materials.append(red)
n0, v0 = len(box.data.polygons), len(box.data.vertices)
co0 = np.array([tuple(v.co) for v in box.data.vertices])
top = [p.index for p in box.data.polygons if p.normal.z > 0.9]
S.mch_pop.height, S.mch_pop.taper, S.mch_pop.each = 0.3, 0.3, False


def ev(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    e = ob.evaluated_get(dg)
    P = np.array([tuple(ob.matrix_world @ v.co) for v in e.data.vertices])
    bm = bmesh.new()
    bm.from_mesh(e.data)
    bad = sum(1 for ed in bm.edges if len(ed.link_faces) != 2)
    bm.free()
    return P, len(e.data.polygons), bad


def untouched():
    co = np.array([tuple(v.co) for v in box.data.vertices])
    return (len(box.data.polygons) == n0 and len(box.data.vertices) == v0 and np.allclose(co, co0)
            and not len(box.modifiers) and box.data.attributes.get(fp.ATTR) is None)


# --- In the Part (0.24.179, the default)
check(f'two ways: In the Part (the default: {S.mch_pop.mode}) and Split', S.mch_pop.mode == 'PART'
      and [i.identifier for i in S.mch_pop.bl_rna.properties['mode'].enum_items] == ['PART', 'SPLIT'])
fp.set_faces(box, top[:2], True, S.mch_pop)
dg = C.evaluated_depsgraph_get()
dg.update()
e = box.evaluated_get(dg)
zt = max((box.matrix_world @ v.co).z for v in e.data.vertices)
check(f'In the Part: the two faces out of the part itself (top {zt:.3f}; its modifier, its own mesh as it was: '
      f'{len(box.data.polygons)} faces)', abs(zt - 1.3) < 1e-4 and box.modifiers.get(fp.MOD) is not None
      and len(box.data.polygons) == n0)
fp.set_faces(box, top[:2], False)
check('... Alt: taken off - no modifier, no attribute left', untouched())
# --- Split
S.mch_pop.mode = 'SPLIT'
pc = fp.add_faces(C, box, top[:2])
P, nf, bad = ev(pc)
check(f'two top faces picked: a piece of its own ("{pc.name}", the part\'s child: {pc.parent == box}), out 0.3 (top '
      f'{P[:, 2].max():.3f}), its bottom a little in the part ({P[:, 2].min():.3f}), closed ({bad} open edges), the '
      f'part\'s material ({[m.name for m in pc.data.materials]})',
      fp.is_piece(pc) and pc is not box and pc.parent == box and abs(P[:, 2].max() - 1.3) < 1e-4
      and 0.9 < P[:, 2].min() < 1.0 and bad == 0 and pc.data.materials[0] == red)
check(f'... the part not touched ({len(box.data.polygons)} faces, no modifier, no attribute)', untouched())
tops = P[np.abs(P[:, 2] - 1.3) < 1e-4]
check(f'Taper 0.3: its top smaller than its foot (top {np.ptp(tops[:, 0]):.2f} x {np.ptp(tops[:, 1]):.2f}, the two '
      f'faces 2.00 x 1.00 or 1.00 x 2.00)', 0.6 < max(np.ptp(tops[:, 0]), np.ptp(tops[:, 1])) < 1.6)
pc.mch_pop.each = True
_P2, nf2, bad2 = ev(pc)
check(f'Each Face: apart (faces {nf} -> {nf2})', nf2 > nf)
pc.mch_pop.each = False
pc.mch_pop.height = 0.5
P3, _n, _b = ev(pc)
check(f'live: Height 0.5 (top {P3[:, 2].max():.3f})', abs(P3[:, 2].max() - 1.5) < 1e-4)
fp.add_faces(C, box, top[2:3], pc)
check(f'one more face into the same piece ({len(fp.faces_of(pc))} faces, pieces of the part: '
      f'{len(fp.pieces_of(box))})', len(fp.faces_of(pc)) == 3 and len(fp.pieces_of(box)) == 1)
gone = fp.remove_faces(box, top[:1])
check(f'Alt: a face taken off ({gone}; {len(fp.faces_of(pc))} left)', gone == 1 and len(fp.faces_of(pc)) == 2)
name = pc.name
fp.remove_faces(box, top[:3])
check('all taken off: the piece gone', bpy.data.objects.get(name) is None and not fp.pieces_of(box))
# Edit Mode selection: a new piece
bpy.ops.object.mode_set(mode='EDIT')
bm = bmesh.from_edit_mesh(box.data)
for f in bm.faces:
    f.select_set(f.normal.x > 0.9)
bmesh.update_edit_mesh(box.data)
bpy.ops.object.mode_set(mode='OBJECT')
C.view_layer.objects.active = box
r = bpy.ops.mch.face_pop_from_edit()
pcs = fp.pieces_of(box)
P4, _n, bad4 = ev(pcs[0]) if pcs else (np.zeros((1, 3)), 0, 1)
check(f'From Edit Mode Selection ({r}): a new piece - the right side\'s faces out (x up to {P4[:, 0].max():.3f}), '
      f'closed ({bad4}); the part not touched ({untouched()})',
      r == {'FINISHED'} and len(pcs) == 1 and P4[:, 0].max() > 1.2 and bad4 == 0 and untouched())
C.view_layer.objects.active = pcs[0]
r = bpy.ops.mch.face_pop_apply()
ap = pcs[0]
check(f'Apply ({r}): a plain mesh ({len(ap.data.polygons)} faces), no modifier, still its own object; the part as it was',
      r == {'FINISHED'} and not len(ap.modifiers) and not fp.is_piece(ap) and len(ap.data.polygons) > 4
      and ap is not box and untouched())
summary()
