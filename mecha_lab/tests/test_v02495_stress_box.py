"""Stress test (user: "박스에 구멍 엄청 마구잡이로 뚫고 디바이드 올리는 테스트해봐" + "복스하이드로도 구멍 뚫고 작은 원기둥
다시 나타나게"): a box, many random cuts (circles, rectangles, line grooves; from the top, front and side; finishes
Off / Chamfer / Bevel / GN Chamfer), Box Hide holes with a small cylinder restored inside; then the marks are checked
and the box divided (Bake High Poly Divide, ZBrush-style polygroups + Divide x3)."""
import math, os, random, sys, time
import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Euler, Quaternion, Vector
import mecha_lab
from mecha_lab import bake_highpoly as bk, box_hide as bh, core_geometry as cg, cut_engine as ce, edge_memory as em
from mecha_lab import lasso_line as ll, zbrush_bridge as zb

SEED = int(os.environ.get('MCH_SEED', '7'))
OUT = os.environ.get('MCH_OUT', '')
random.seed(SEED)
mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'ACTIVE'
PPU = 100.0
VIEWS = {'TOP': cg.OrthoProjector(Quaternion(), pixels_per_unit=PPU),
         'FRONT': cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=PPU),
         'SIDE': cg.OrthoProjector(Euler((math.pi / 2, 0, math.pi / 2)).to_quaternion(), pixels_per_unit=PPU)}
HALF = {'TOP': (1.5, 1.5), 'FRONT': (1.5, 0.5), 'SIDE': (1.5, 0.5)}     # (the box seen from each view)


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


me = bpy.data.meshes.new('box')
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=1.0)
for v in bm.verts:
    v.co = Vector((v.co.x * 3, v.co.y * 3, v.co.z * 1))
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new('Box', me)
S.collection.objects.link(ob)
C.view_layer.objects.active = ob
ob.select_set(True)
em.mark_generated(me)


def angles(m):
    e_s, f_s, st, en = em._edge_faces(m)
    s2 = st[(en - st) == 2]
    nrm = np.empty(len(m.polygons) * 3, np.float32)
    m.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    fa, fb = f_s[s2], f_s[s2 + 1]
    return e_s[s2], fa, fb, np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', nrm[fa], nrm[fb]), -1, 1)))


def unmarked(m, lo=50.0, slivers=False):
    """edges sharper than ``lo`` left unmarked; without ``slivers``, the edges of faces smaller than 1e-5 of the box's
    size squared are left out (the Boolean's crumpled slivers: their normals mean nothing)"""
    e, fa, fb, ang = angles(m)
    bad = (ang > lo) & ~em.marked(m)[e]
    if not slivers:
        area = np.empty(len(m.polygons)); m.polygons.foreach_get('area', area)
        tiny = 1e-5 * 3.0 ** 2           # (a 1 cm square on this 3 m box)
        bad &= (area[fa] > tiny) & (area[fb] > tiny)
    return int(bad.sum())


def finish(kind):
    cut = S.mch_cut
    cut.edge_finish, cut.gn_finish = 'NONE', 'NONE'
    if kind in ('CHAMFER', 'BEVEL'):
        cut.edge_finish, cut.finish_width, cut.finish_segments = kind, random.choice((0.015, 0.025, 0.04)), 3
    elif kind == 'GN':
        cut.gn_finish, cut.gn_width, cut.gn_segments = random.choice(('CHAMFER', 'BEVEL')), 0.02, 3


def circle(view, cx, cy, r):
    lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
    lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', P(cx, cy)
    return lg._drag_loops(P(cx + r, cy), False, False)[0]


log = []
t_all = time.time()
for step in range(int(os.environ.get('MCH_STEPS', '28'))):
    view = random.choice(('TOP', 'TOP', 'TOP', 'FRONT', 'SIDE'))
    hx, hy = HALF[view]
    kind = random.choice(('circle', 'circle', 'rect', 'line', 'hide'))
    fin = random.choice(('NONE', 'CHAMFER', 'BEVEL', 'GN'))
    finish(fin)
    proj = VIEWS[view]
    t0 = time.time()
    try:
        if kind == 'circle':
            r = random.uniform(0.08, 0.45) * (0.5 if view != 'TOP' else 1.0)
            cx, cy = random.uniform(-hx, hx), random.uniform(-hy, hy)
            msg = ce.perform_closed(C, 'CUT', [ob], [circle(view, cx, cy, r)], proj)
        elif kind == 'rect':
            cx, cy = random.uniform(-hx, hx), random.uniform(-hy, hy)
            w, h = random.uniform(0.1, 0.8), random.uniform(0.1, 0.6) * (0.5 if view != 'TOP' else 1.0)
            msg = ce.perform_closed(C, 'CUT', [ob], [ce.rect_loop(P(cx - w / 2, cy - h / 2), P(cx + w / 2, cy + h / 2))], proj)
        elif kind == 'line':
            S.mch_brush.line_width = random.uniform(0.04, 0.12)
            a = Vector((random.uniform(-hx, hx), random.uniform(-hy, hy)))
            b = Vector((random.uniform(-hx, hx), random.uniform(-hy, hy)))
            mid = (a + b) / 2 + Vector((random.uniform(-0.5, 0.5), random.uniform(-0.5, 0.5)))
            pts = [P(*((1 - t) ** 2 * a + 2 * (1 - t) * t * mid + t * t * b)) for t in np.linspace(0, 1, 30)]
            msg = ce.perform_closed(C, 'CUT', [ob], [ll.line_loop(C, proj, pts, S.mch_brush)], proj)
        else:                                       # Box Hide: a box hidden, a small cylinder brought back inside
            proj = VIEWS['TOP']
            cx, cy = random.uniform(-1.2, 1.2), random.uniform(-1.2, 1.2)
            w = random.uniform(0.4, 0.8)
            bh.perform(C, [ob], [ce.rect_loop(P(cx - w / 2, cy - w / 2), P(cx + w / 2, cy + w / 2))], proj)
            bh.perform(C, [ob], [circle('TOP', cx, cy, w * 0.2)], proj, restore=True)
            bh.apply(C, ob)
            msg = 'Box Hide + cylinder restored, applied'
            fin = '-'
    except Exception as ex:
        msg = f'ERR {type(ex).__name__}: {str(ex)[:90]}'
    u = unmarked(ob.data)
    log.append((step, view, kind, fin, len(ob.data.polygons), u, round(time.time() - t0, 2), str(msg)[:70]))
    print(f'step {step:2d} {view:5s} {kind:6s} {fin:7s} faces {len(ob.data.polygons):6,} unmarked>50 {u:3d} '
          f'{time.time() - t0:5.2f}s | {str(msg)[:80]}')

me = ob.data
print(f'all cuts: {time.time() - t_all:.1f} s, {len(me.polygons):,} faces, {em.count(me):,} marked edges')
errs = [l for l in log if l[7].startswith('ERR')]
check(f'{len(log)} random cuts / Box Hides ran ({len(errs)} refused with a message)', len(errs) <= 4, errs[:4])
u, us = unmarked(me), unmarked(me, slivers=True)
check(f'After all of them: edges sharper than 50 degrees left unmarked (faces bigger than slivers; with slivers {us})',
      u <= 20, u)
tmp = zb.export_copy(C, ob, False)
ids, ng, _nb = zb.crease_regions(tmp.data)
e2, fa2, fb2, ang2 = angles(tmp.data)
leaks = int(((ids[fa2] == ids[fb2]) & (ang2 > 50)).sum())
print(f'ZBrush export: {ng} polygroups, edges sharper than 50 deg inside one polygroup (slivers too): {leaks}')
# ZBrush: Import Mats as Polygroups -> CreasePG -> Divide x2, how far it strays from the box
tm = tmp.data
e_s, f_s, st, en = em._edge_faces(tm); cnt = en - st
cr = np.zeros(len(tm.edges), np.float32); cr[e_s[st[cnt != 2]]] = 1.0
s2 = st[cnt == 2]; cr[e_s[s2][ids[f_s[s2]] != ids[f_s[s2 + 1]]]] = 1.0
(tm.attributes.get('crease_edge') or tm.attributes.new('crease_edge', 'FLOAT', 'EDGE')).data.foreach_set('value', cr)
md = tmp.modifiers.new('div', 'SUBSURF'); md.levels = md.render_levels = 2; md.use_creases = True
from mathutils.bvhtree import BVHTree
bvh = BVHTree.FromObject(ob, C.evaluated_depsgraph_get())
zm = bpy.data.meshes.new_from_object(tmp.evaluated_get(C.evaluated_depsgraph_get()), depsgraph=C.evaluated_depsgraph_get())
zc = np.empty(len(zm.vertices) * 3); zm.vertices.foreach_get('co', zc)
zd = np.array([bvh.find_nearest(Vector(p))[3] for p in zc.reshape(-1, 3)])
check(f'ZBrush-style CreasePG + Divide x2 ({len(zm.polygons):,} faces): points more than 1 % of the box off it '
      f'{int((zd > 0.03).sum())}, the farthest {zd.max() / 3 * 100:.2f} % of the box', zd.max() < 0.09, zd.max())
bpy.data.meshes.remove(zm)
bpy.data.objects.remove(tmp)
if OUT:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f'stress_box_{SEED}.blend'))
t = time.time()
hp, info = bk.build(C, ob, target_faces=600_000, bevels='DIVIDE')
dt = time.time() - t
print(bk.describe(info))
co = np.empty(len(hp.data.vertices) * 3)
hp.data.vertices.foreach_get('co', co)
d = np.array([bvh.find_nearest(Vector(p))[3] for p in co.reshape(-1, 3)])
check(f'Bake High Poly Divide: {len(hp.data.polygons):,} faces in {dt:.1f} s; points more than 1 % of the box off '
      f'it: {int((d > 0.03).sum())}, the farthest {d.max() / 3 * 100:.2f} % of the box', d.max() < 0.09, d.max())
if OUT:
    bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f'stress_box_{SEED}_divided.blend'))
summary()
