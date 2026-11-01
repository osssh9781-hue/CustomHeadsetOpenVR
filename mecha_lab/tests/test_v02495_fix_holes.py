"""0.24.95 (user: "이미 빵꾸가 난 건 어떻게 고쳐? 고치는 기능도 만들어 줘") Holes already made by a cut on a part with the
live Mirror (a cut wall on / within the Bisect distance of the mirror plane - see test_v02495_mirror_cut_holes): the
base mesh is whole, so Fix Mesh used to find nothing.  Fix Mesh (Mecha Lab tab, Quad Remesh box, ZBrush shelf) now
measures what is SEEN (the mirror applied) and moves the faces lying on the plane just past it, to the side the
Bisect cuts off - the cut then crosses the centre and the mirrored part closes.  A mirror already applied: the holes
are in the mesh and the usual repair fills them.  A half part's open side on its mirror plane is never filled."""
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, mesh_fix as mf, symmetry, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion())


def open_edges(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def seen(ob):
    ev = ob.evaluated_get(C.evaluated_depsgraph_get())
    me = bpy.data.meshes.new_from_object(ev)
    bm = bmesh.new()
    bm.from_mesh(me)
    vol = bm.calc_volume()
    bm.free()
    n = open_edges(me)
    bpy.data.meshes.remove(me)
    return n, round(vol, 3)


def part(mirror=True, half=False):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    m = ob.modifiers.new('s', 'SUBSURF')
    m.subdivision_type, m.levels = 'SIMPLE', 2
    bpy.ops.object.convert(target='MESH')
    if half:                                     # (the faces left of x = 0 taken away: open along the plane)
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.calc_center_median().x < 0], context='FACES')
        bm.to_mesh(ob.data)
        bm.free()
    if mirror:
        symmetry.set_mode(C, ob, 'MIRROR')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob
    return ob


def holed(x0, x1, flip=False):
    """A part holed the old way: the cut made with the 0.24.95 cut fix switched off."""
    ob = part()
    m = symmetry.mirror_mod(ob)
    m.use_bisect_flip_axis[0] = flip
    keep, cg.MIRROR_CLEAR = cg.MIRROR_CLEAR, 0.0
    try:
        px = lambda v: 500 + v * 100
        ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop((px(x0), px(-0.4)), (px(x1), px(0.4)))], TOP)
    finally:
        cg.MIRROR_CLEAR = keep
    return ob


rows = []
for name, x0, x1, flip in (('wall 0.5 mm from the centre', 0.0005, 0.3, False),
                           ('wall on the centre line', 0.0, 0.3, False),
                           ('Flip (the minus side kept), wall 0.5 mm', -0.3, -0.0005, True)):
    ob = holed(x0, x1, flip)
    before = seen(ob)[0], open_edges(ob.data)
    r = bpy.ops.mch.fix_mesh()
    after, vol = seen(ob)
    rows.append((name, before, after, open_edges(ob.data), vol))
check('A part holed by a cut at its mirror plane (whole base mesh, 6 - 8 open edges seen): Fix Mesh closes what is '
      'seen, the cut crosses the centre (8 - 2 x 0.6 x 0.8 = 7.04)',
      all(b[0] >= 6 and b[1] == 0 and a == 0 and o == 0 and abs(v - 7.04) < 0.02 for _n, b, a, o, v in rows), rows)
ob = holed(0.0005, 0.3)
mf_msg = mf.report(mf.fix_part(C, ob))
check('... its report says so (open edges seen, points moved off the mirror plane, closed)',
      'open edges seen' in mf_msg and 'moved off the mirror plane' in mf_msg and '(closed)' in mf_msg, mf_msg)
ob = part()
co0 = [v.co.copy() for v in ob.data.vertices]
st = mf.fix_part(C, ob)
check('... a mirrored part with no hole: nothing moved', st.get('mirror_moved') == 0 and st['seen_after'] == 0
      and all((v.co - c).length < 1e-9 for v, c in zip(ob.data.vertices, co0)))

# the mirror already applied: the holes are in the mesh
ob = holed(0.0005, 0.3)
symmetry.apply(C, ob)
b = open_edges(ob.data)
r = bpy.ops.mch.fix_mesh()
check('The mirror applied with the hole in it: Fix Mesh fills it (open edges in the mesh -> 0)',
      b > 0 and open_edges(ob.data) == 0 and not symmetry.mirror_mod(ob), (b, open_edges(ob.data)))

# a half part (open at the plane), its mirror without Bisect: that side is the mirror's to close, not a hole
ob = part(half=True)
m = symmetry.mirror_mod(ob)
for i in range(3):
    m.use_bisect_axis[i] = False
side = open_edges(ob.data)
n_faces = len(ob.data.polygons)
st = mf.fix_part(C, ob)
check('A half part on a mirror without Bisect: its open side on the plane is left open (the mirror closes it)',
      side > 0 and open_edges(ob.data) == side and len(ob.data.polygons) == n_faces and st['seen_after'] == 0,
      (side, open_edges(ob.data), st.get('seen_after')))
n0 = len(ob.data.polygons)
fixed = mf.auto_fix(C, [ob], 'Cut')
check('... and the automatic Fix Mesh before a cut leaves it too', len(ob.data.polygons) == n0
      and open_edges(ob.data) == side, fixed)

# no mirror: an ordinary hole
ob = part(mirror=False)
bm = bmesh.new()
bm.from_mesh(ob.data)
bm.faces.ensure_lookup_table()
bmesh.ops.delete(bm, geom=[bm.faces[0]], context='FACES_ONLY')
bm.to_mesh(ob.data)
bm.free()
b = open_edges(ob.data)
bpy.ops.mch.fix_mesh()
check('A part without a mirror, a face missing: filled as before', b == 4 and open_edges(ob.data) == 0, b)

# the ZBrush shelf: Check Mesh shows the holes (as seen), Fix Mesh closes them
ob = holed(0.0005, 0.3)
bpy.ops.object.mode_set(mode='SCULPT')
chk = zs.run(C, 'CHECK_MESH')
fix = zs.run(C, 'FIX_MESH')
chk2 = zs.run(C, 'CHECK_MESH')
check('ZBrush shelf: Check Mesh counts the holes as seen (before: open edges were not counted - "clean"), Fix Mesh '
      'closes them, still in Sculpt Mode', 'open edges (holes)' in chk and fix.startswith('Fix Mesh:')
      and chk2 == 'Check Mesh: clean' and C.mode == 'SCULPT', (chk, fix, chk2))
from mecha_lab import mecha_menu
check('Mecha Lab: Fix Holes in the Mecha Menu\'s Actions (Fix Mesh, the mirror\'s holes too)',
      any(lab == 'Fix Holes' and op == 'mch.fix_mesh' for _s, btns in mecha_menu.ACTIONS for lab, _i, op, *_r in btns))
summary()
