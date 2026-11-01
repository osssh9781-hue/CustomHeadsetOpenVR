"""0.24.95 Quad Remesh follows the remembered lines (user: "지금 개선한 엣지 추적 방식으로 리메시 엔진도 수정할 수
있겠다" / "리메시 먼저 해 봐"): the part's Edge Memory lines are fixed lines for the remesh (not only edges sharper than
30 degrees: an Edge Finish band's 15-degree borders were crossed), and afterwards only the quads' edges lying ON those
lines are remembered again (the old "near the line" transfer marked 47 - 72 % stray edges round a band)."""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, edge_memory as em, lasso_line as ll, mesh_io as mio
from mecha_lab import quad_field as qf

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
PPU = 100.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def block(name, dims):
    me = bpy.data.meshes.new(name)
    b = bmesh.new()
    bmesh.ops.create_cube(b, size=1.0)
    for v in b.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    b.to_mesh(me)
    b.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    for o in C.selected_objects:
        o.select_set(False)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    em.mark_generated(me)
    return ob


def finish(mode='NONE', w=0.02, seg=3):
    c = S.mch_cut
    c.edge_finish, c.finish_width, c.finish_segments, c.gn_finish = mode, w, seg, 'NONE'


def hole(ob, cx, cy, r):
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', P(cx, cy)
    return ce.perform_closed(C, 'CUT', [ob], [lg._drag_loops(P(cx + r, cy), False, False)[0]], TOP)


def thin_tree(segs):
    verts, polys = [], []
    for i, (a, b) in enumerate(segs):
        d = b - a
        side = np.cross(d, [0, 0, 1.0]) if abs(d[2]) < 0.9 * np.linalg.norm(d) else np.cross(d, [1.0, 0, 0])
        side = side / (np.linalg.norm(side) or 1) * 1e-7
        verts += [Vector(a), Vector(b), Vector(b + side)]
        polys.append((3 * i, 3 * i + 1, 3 * i + 2))
    return BVHTree.FromPolygons(verts, polys, all_triangles=True)


def survive(seg_old, me_new, tol):
    """(share of the old lines' length with a remembered edge of the new mesh within tol, share of the new mesh's
    remembered edges off the old lines)"""
    co = mio.read_co(me_new)
    ev = mio.read_edge_verts(me_new)[em.marked(me_new)]
    if not len(ev):
        return 0.0, 1.0
    tn, to = thin_tree(co[ev]), thin_tree(seg_old)
    tot = hit = 0.0
    for a, b in seg_old:
        L = np.linalg.norm(b - a)
        n = max(1, int(L / (tol * 0.5)))
        for t in (np.arange(n) + 0.5) / n:
            tot += L / n
            if tn.find_nearest(Vector(a + (b - a) * t), tol)[0] is not None:
                hit += L / n
    mids = (co[ev[:, 0]] + co[ev[:, 1]]) / 2
    off = sum(1 for m in mids if to.find_nearest(Vector(m), tol)[0] is None)
    return hit / tot, off / len(mids)


# ---- mark_on_lines on its own
me = bpy.data.meshes.new('grid')
bm = bmesh.new()
bmesh.ops.create_grid(bm, x_segments=4, y_segments=4, size=1.0)
bm.to_mesh(me)
bm.free()
line = np.array([[[-1.0, 0.0, 0.0], [1.0, 0.0, 0.0]]])               # the grid's middle row
n = em.mark_on_lines(me, line, 0.02)
co = mio.read_co(me)
ev = mio.read_edge_verts(me)
on = np.abs(co[ev][:, :, 1]).max(1) < 1e-6
check('mark_on_lines: the 4 edges of the grid\'s middle row are marked, none across it or beside it',
      n == 4 and em.marked(me)[on].all() and not em.marked(me)[~on].any(), (n, int(on.sum())))

# ---- a plate with a Line Cut + Bevel band, a Chamfer hole and a plain hole, Quad Remeshed to 8,000 faces
a = block('Plate', (3, 1.6, 0.2))
finish('BEVEL', 0.03, 3)
S.mch_brush.line_width = 0.08
ce.perform_closed(C, 'CUT', [a], [ll.line_loop(C, TOP, [P(-1.2 + 0.1 * i, -0.5 + 0.04 * i) for i in range(24)],
                                               S.mch_brush)], TOP)
finish('CHAMFER', 0.02, 1)
hole(a, 0.8, 0.3, 0.25)
finish()
hole(a, -0.6, 0.35, 0.2)
seg = em.lines(a.data)
memo = qf.remembered_lines(a.data)
check(f'remembered_lines: the plate\'s {len(seg)} marked lines go to the remesh as fixed lines',
      memo is not None and len(memo) == len(seg))
msg = qf.remesh_object(a, 8000, all_quads=False, crease_deg=30.0)
me2 = a.data
h = math.sqrt(sum(p.area for p in me2.polygons) / max(1, len(me2.polygons)))
cov, off = survive(seg, me2, 0.25 * h)
check(f'Quad Remesh of the plate ({len(me2.polygons):,} faces): {cov * 100:.0f} % of its remembered lines remembered '
      f'again (before: 67 %), {off * 100:.1f} % of the remembered edges off those lines (before: 72 %)',
      cov > 0.8 and off < 0.02 and 'Quad Remesh' in msg, (cov, off, msg[:80]))

# ---- a box: bevel hole, chamfer pocket, plain hole
b = block('Box', (2, 2, 1))
finish('BEVEL', 0.04, 2)
hole(b, -0.4, 0.2, 0.3)
finish('CHAMFER', 0.03, 1)
ce.perform_closed(C, 'CUT', [b], [ce.rect_loop(P(0.2, -0.6), P(0.7, 0.1))], TOP)
finish()
hole(b, 0.5, 0.6, 0.15)
seg = em.lines(b.data)
qf.remesh_object(b, 8000, all_quads=False, crease_deg=30.0)
h = math.sqrt(sum(p.area for p in b.data.polygons) / max(1, len(b.data.polygons)))
cov, off = survive(seg, b.data, 0.25 * h)
check(f'Quad Remesh of the box: {cov * 100:.1f} % of its lines kept (before: 99.6 %), {off * 100:.1f} % stray '
      f'(before: 9 %)', cov > 0.98 and off < 0.02, (cov, off))

# ---- smeared marks (most edges of a dense mesh) are not used as fixed lines
me = bpy.data.meshes.new('dense')
bm = bmesh.new()
bmesh.ops.create_uvsphere(bm, u_segments=64, v_segments=48, radius=1.0)
bm.to_mesh(me)
bm.free()
a_ = me.attributes.new(em.ATTR, 'BOOLEAN', 'EDGE')
a_.data.foreach_set('value', np.ones(len(me.edges), bool))
check('remembered_lines: marks on more than half of a dense mesh\'s edges (smeared) are not used',
      qf.remembered_lines(me) is None)
# ---- Fast Decimate: the remembered sides are kept by the engine; now they are remembered again exactly
from mecha_lab import fast_decimate as fd
c = block('Box2', (2, 2, 1))
finish('BEVEL', 0.04, 2)
hole(c, -0.4, 0.2, 0.3)
finish('CHAMFER', 0.03, 1)
ce.perform_closed(C, 'CUT', [c], [ce.rect_loop(P(0.2, -0.6), P(0.7, 0.1))], TOP)
finish()
seg = em.lines(c.data)
fd.decimate_object(c, 30)
cov, off = survive(seg, c.data, 0.004 * em.mesh_size(c.data))
check(f'Fast Decimate of the box: {cov * 100:.1f} % of its lines remembered again (before: 61 %), {off * 100:.1f} % '
      f'stray (before: 24 % - the diagonals beside the lines)', cov > 0.98 and off < 0.02, (cov, off))
summary()
