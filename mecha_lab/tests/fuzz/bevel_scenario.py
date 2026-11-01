"""Bevel fuzz (user: "베벨로만 한 50개 만들어 봐 - 베벨로 만든 거 컷으로 자르고 베벨로 컷한 거 이런 걸로"): one Base Mesh
part per seed with a Bevel profile (a sharp polygon, a curve or both; 1 - 6 segments; top or both sides), then 2 - 5
cuts into it - Cut with an Edge Finish Bevel (circle / rectangle / polygon / line groove, through or a pocket, from the
top, front or side) or a Base Mesh subtract with a Bevel profile.  After every step the part is checked like the
combination fuzz; at the end it is Divided twice - Bake High Poly Divide and the ZBrush way (polygroups by crease,
crease on their borders, Catmull-Clark) - and each counted: faces turned against the part (> 107 degrees) and the
farthest point off it.

    <python with bpy> bevel_scenario.py <seed> <steps>          (run_fuzz.py 50 5 1 1 bevel_scenario.py runs 50)
"""
import math
import os
import random
import sys
import time
import traceback

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.dirname(HERE))
from _harness import bmesh, bpy, fresh  # noqa: E402
import numpy as np  # noqa: E402
from mathutils import Euler, Quaternion, Vector  # noqa: E402
from mathutils.bvhtree import BVHTree  # noqa: E402

import mecha_lab  # noqa: E402
from mecha_lab import base_mesh as bm_, bake_highpoly as bk, box_hide as bh, core_geometry as cg  # noqa: E402
from mecha_lab import cut_engine as ce, edge_memory as em, lasso_line as ll  # noqa: E402

seed, nsteps = int(sys.argv[-2]), int(sys.argv[-1])
rng = random.Random(seed)
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'SELECTED'
PPU = 100.0
VIEWS = {'TOP': Quaternion(), 'FRONT': Euler((math.pi / 2, 0, 0)).to_quaternion(),
         'SIDE': Euler((math.pi / 2, 0, math.pi / 2)).to_quaternion(), 'BOTTOM': Euler((math.pi, 0, 0)).to_quaternion()}


def proj(view):
    return cg.OrthoProjector(VIEWS[view], pixels_per_unit=PPU)


def log(kind, text):
    print(f'{kind} {text}', flush=True)


# ---- the part
def make_part():
    p = bm_.scene_defaults(C)
    p.sketch = False
    p.profile = 'BEVEL'
    p.height = rng.uniform(0.3, 1.3)
    p.bevel_width = rng.uniform(0.03, 0.25)
    p.bevel_segments = rng.choice((1, 2, 2, 3, 3, 4, 6))
    p.bevel_sides = rng.choice(('TOP', 'TOP', 'BOTH'))
    kind = rng.choice(('poly', 'poly', 'curve', 'mixed'))
    n = rng.randint(4, 9) if kind == 'poly' else 36
    r0 = rng.uniform(0.8, 1.5)
    pts = []
    for i in range(n):
        a = 2 * math.pi * i / n
        if kind == 'poly':
            a += rng.uniform(-0.2, 0.2)
            r = r0 * rng.uniform(0.6, 1.0)
        elif kind == 'curve':
            r = r0 * (1.0 + 0.2 * math.sin(3 * a))
        else:                                    # (a rounded half and a flat-cut half)
            r = r0 if math.cos(a) > 0 else r0 * 0.7 / max(0.35, abs(math.cos(a - math.pi)))
        pts.append((500 + math.cos(a) * r * PPU, 500 + math.sin(a) * r * PPU))
    before = set(bpy.data.objects)
    bm_.perform_base(C, [pts], proj('TOP'))
    ob = [o for o in bpy.data.objects if o not in before][0]
    return ob, (f'Base Mesh BEVEL {kind} ({n} corners) w {p.bevel_width:.2f} seg {p.bevel_segments} '
                f'{p.bevel_sides} h {p.height:.2f}')


# ---- checks
def parts():
    return [o for o in S.objects if o.type == 'MESH' and not o.name.startswith(('MCH_Hide', 'MCH_Cutter', 'MCH_Base'
                                                                                 'Cutter', '.')) and
            o.get(bh.VOL_KEY) is None and not o.get(bk.SRC_KEY) and o.visible_get()]


def stats(o):
    me = o.data
    e_s, f_s, st, en = em._edge_faces(me) if len(me.polygons) else (None, None, np.zeros(0, int), np.zeros(0, int))
    cnt = en - st
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    warp = 0
    if len(me.polygons):
        from mecha_lab import mesh_io as mio
        cv = mio.read_corner_verts(me)
        start, tot = mio.read_face_starts(me)
        nrm = np.empty(len(me.polygons) * 3)
        me.polygons.foreach_get('normal', nrm)
        nrm = nrm.reshape(-1, 3)
        big = np.flatnonzero(tot > 3)
        if len(big):
            fid = np.repeat(np.arange(len(tot)), tot)
            cen = np.add.reduceat(co[cv], start) / tot[:, None]
            dev = np.abs(np.einsum('ij,ij->i', co[cv] - cen[fid], nrm[fid]))
            fdev = np.maximum.reduceat(dev, start)
            size = (float(np.ptp(co, axis=0).max()) or 1.0) if len(co) else 1.0
            warp = int((fdev[big] > 0.01 * size).sum())
    return dict(faces=len(me.polygons), open=int((cnt == 1).sum()), multi=int((cnt > 2).sum()), warp=warp,
                tangled=len(tangled(me)),
                nan=bool(np.isnan(co).any()), lo=co.min(0) if len(co) else None, hi=co.max(0) if len(co) else None)


def _orient(p1, p2, p3):
    return (p2[..., 0] - p1[..., 0]) * (p3[..., 1] - p1[..., 1]) - (p2[..., 1] - p1[..., 1]) * (p3[..., 0] - p1[..., 0])


def tangled(me):
    """the faces whose outline crosses itself in the face's own plane (a lip folded back over the face: Divide
    folds it, the part shades a dark seam)"""
    from mecha_lab import mesh_io as mio
    nf = len(me.polygons)
    if not nf:
        return []
    start, tot = mio.read_face_starts(me)
    co = mio.read_co(me)
    cv = mio.read_corner_verts(me)
    nrm = np.empty(nf * 3)
    me.polygons.foreach_get('normal', nrm)
    nrm = nrm.reshape(-1, 3)
    out = []
    for f in np.flatnonzero(tot >= 4):
        p = co[cv[start[f]:start[f] + tot[f]]]
        n = nrm[f]
        u = np.cross(n, (1.0, 0, 0) if abs(n[0]) < 0.9 else (0, 1.0, 0))
        u /= np.linalg.norm(u) or 1.0
        q = np.stack([p @ u, p @ np.cross(n, u)], 1)
        a, b = q, np.roll(q, -1, 0)
        m = len(q)
        i, j = np.triu_indices(m, 2)
        keep = ~((i == 0) & (j == m - 1))
        i, j = i[keep], j[keep]
        eps = 1e-12 * float(np.ptp(q, 0).max() or 1.0) ** 2
        x = ((_orient(a[i], b[i], a[j]) * _orient(a[i], b[i], b[j]) < -eps * eps)
             & (_orient(a[j], b[j], a[i]) * _orient(a[j], b[j], b[i]) < -eps * eps))
        if x.any():
            out.append(int(f))
    return out


def unmarked(o, size):
    me = o.data
    if len(me.polygons) < 4:
        return 0
    e_s, f_s, st, en = em._edge_faces(me)
    s2 = st[(en - st) == 2]
    fa, fb = f_s[s2], f_s[s2 + 1]
    n = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', n)
    n = n.reshape(-1, 3)
    ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', n[fa], n[fb]), -1, 1)))
    area = np.empty(len(me.polygons))
    me.polygons.foreach_get('area', area)
    tiny = 1e-5 * size * size
    return int(((ang > 50) & ~em.marked(me)[e_s[s2]] & (area[fa] > tiny) & (area[fb] > tiny)).sum())


SIZE = {}


def snapshot():
    return {o.name: (stats(o), unmarked(o, SIZE.get(o.name, 1.0))) for o in parts()}


def judge(step, before, after, op):
    for name, (st, um) in after.items():
        b = before.get(name)
        size = SIZE.setdefault(name, SIZE.get(name.split('_Split')[0], 1.0))
        if st['nan']:
            log('BAD', f'{step} nan: {name} has NaN points after {op}')
        if st['faces'] == 0:
            log('BAD', f'{step} empty: {name} has no faces after {op}')
            continue
        closed_before = b is not None and b[0]['open'] == 0 and b[0]['multi'] == 0
        if (b is None or closed_before) and (st['open'] or st['multi']):
            log('BAD', f'{step} open: {name} {st["open"]} open / {st["multi"]} 3-face edges after {op}')
        if b is not None and b[0]['lo'] is not None and st['lo'] is not None:
            grow = max(float((b[0]['lo'] - st['lo']).max()), float((st['hi'] - b[0]['hi']).max()))
            if grow > 0.01 * size:
                log('BAD', f'{step} grew: {name} got {grow / size * 100:.1f} % bigger after {op}')
        if st['warp'] > (b[0]['warp'] if b is not None else 0):
            log('BAD', f'{step} warped: {name} {st["warp"] - (b[0]["warp"] if b else 0)} new faces bent more than 1 % of '
                       f'its size after {op}')
        if st['tangled'] > (b[0]['tangled'] if b is not None else 0):
            log('BAD', f'{step} tangled: {name} {st["tangled"] - (b[0]["tangled"] if b else 0)} new faces cross '
                       f'themselves after {op}')
        if um - (b[1] if b is not None else 0) > 12:
            log('BAD', f'{step} crease: {name} {um - (b[1] if b else 0)} new hard edges without a crease after {op} '
                       f'({um} in all)')


# ---- shapes
def centre_of(o, view):
    """a random screen point over part ``o`` from ``view`` (its world box projected)."""
    pr = proj(view)
    corners = [o.matrix_world @ Vector(c) for c in o.bound_box]
    xy = np.array([pr.to_screen(c)[:2] for c in corners])
    lo, hi = xy.min(0), xy.max(0)
    return (rng.uniform(lo[0], hi[0]), rng.uniform(lo[1], hi[1])), float((hi - lo).min()) / PPU


def shape(view, o):
    (cx, cy), span = centre_of(o, view)
    r = max(0.05, rng.uniform(0.06, 0.35) * max(span, 0.3))
    kind = rng.choice(('circle', 'circle', 'rect', 'poly', 'line'))
    if kind == 'circle':
        lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
        lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', (cx, cy)
        return kind, [lg._drag_loops((cx + r * PPU, cy), False, False)[0]]
    if kind == 'rect':
        w, h = r * rng.uniform(0.6, 2.0), r * rng.uniform(0.6, 2.0)
        return kind, [ce.rect_loop((cx - w * PPU, cy - h * PPU), (cx + w * PPU, cy + h * PPU))]
    if kind == 'poly':
        n = rng.randint(3, 7)
        pts = [(cx + math.cos(2 * math.pi * i / n + rng.uniform(-0.3, 0.3)) * r * rng.uniform(0.5, 1.3) * PPU,
                cy + math.sin(2 * math.pi * i / n + rng.uniform(-0.3, 0.3)) * r * rng.uniform(0.5, 1.3) * PPU)
               for i in range(n)]
        return kind, [pts]
    S.mch_brush.line_width = rng.uniform(0.03, 0.12)
    a = Vector((cx, cy)) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1))) * span * PPU * 0.6
    b_ = Vector((cx, cy)) + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1))) * span * PPU * 0.6
    mid = (a + b_) / 2 + Vector((rng.uniform(-1, 1), rng.uniform(-1, 1))) * span * PPU * 0.3
    path = [tuple((1 - t) ** 2 * a + 2 * (1 - t) * t * mid + t * t * b_) for t in np.linspace(0, 1, 24)]
    return kind, [ll.line_loop(C, proj(view), path, S.mch_brush)]


def finish():
    cut = S.mch_cut
    cut.edge_finish, cut.gn_finish = 'NONE', 'NONE'
    f = rng.choice(('BEVEL', 'BEVEL', 'BEVEL', 'GN', 'NONE'))
    if f == 'BEVEL':
        cut.edge_finish, cut.finish_width, cut.finish_segments = 'BEVEL', rng.choice((0.01, 0.02, 0.04, 0.06)), \
            rng.choice((2, 3, 4))
    elif f == 'GN':
        cut.gn_finish, cut.gn_width, cut.gn_segments = 'BEVEL', rng.choice((0.02, 0.04)), 3
    cut.depth_mode = rng.choice(('THROUGH', 'THROUGH', 'SURFACE'))
    cut.depth = rng.uniform(0.05, 0.4)
    return f + ('' if cut.depth_mode == 'THROUGH' else f' pocket {cut.depth:.2f}')


def select_only(o):
    for x in C.selected_objects:
        x.select_set(False)
    o.select_set(True)
    C.view_layer.objects.active = o


# ---- the run
t_run = time.time()
ob, what = make_part()
SIZE[ob.name] = max(ob.dimensions)
log('STEP', f'0 part: {what} -> {ob.name} ({len(ob.data.polygons)} faces)')
for step in range(1, nsteps + 1):
    ps = parts()
    if not ps:
        log('BAD', f'{step} nothing left')
        break
    o = rng.choice(ps)
    SIZE.setdefault(o.name, max(o.dimensions))
    view = rng.choice(('TOP', 'TOP', 'FRONT', 'SIDE'))
    op = rng.choice(('cut', 'cut', 'cut', 'cut', 'sub', 'sub', 'split'))
    select_only(o)
    if os.environ.get('MCH_SAVE_AT') == str(step):          # (debug: the scene just before this step)
        bpy.ops.wm.save_as_mainfile(filepath=os.environ['MCH_SAVE'])
    if os.environ.get('MCH_HOOK_AT') == str(step):          # (debug: a tracing script run just before this step)
        exec(open(os.environ['MCH_HOOK']).read())
    before = snapshot()
    t0 = time.time()
    desc = ''
    try:
        if op == 'cut':
            fin = finish()
            k, loops = shape(view, o)
            desc = f'Cut {k} {fin} from {view} on {o.name}'
            msg = ce.perform_closed(C, 'CUT', [o], loops, proj(view))
        elif op == 'split':
            finish()
            S.mch_cut.depth_mode = 'THROUGH'
            k, loops = shape(view, o)
            desc = f'Split {k} from {view} on {o.name}'
            msg = ce.perform_closed(C, 'SPLIT', [o], loops, proj(view))
        elif op == 'hide':
            k, loops = shape(view, o)
            how = rng.choice(('apply', 'restore', 'split_off'))
            desc = f'Box Hide {k} from {view} on {o.name}, then {how}'
            msg = bh.perform(C, [o], loops, proj(view))
            if how == 'restore':
                (cx, cy), span = centre_of(o, view)
                lg = ce.StrokeLogic.__new__(ce.StrokeLogic)
                g = loops[0]
                mx, my = sum(p[0] for p in g) / len(g), sum(p[1] for p in g) / len(g)
                lg.brush, lg.shape, lg.anchor = S.mch_brush, 'CIRCLE', (mx, my)
                rr = 0.25 * min(max(p[0] for p in g) - min(p[0] for p in g), max(p[1] for p in g) - min(p[1] for p in g))
                bh.perform(C, [o], [lg._drag_loops((mx + max(rr, 3.0), my), False, False)[0]], proj(view), restore=True)
                bh.apply(C, o)
            elif how == 'apply':
                bh.apply(C, o)
            else:
                piece = bh.split_off(C, o)
                msg = f'{msg} | split off -> {piece.name if piece else None}'
        else:
            p = bm_.scene_defaults(C)
            p.sketch = False
            p.profile = 'BEVEL'
            p.height = rng.uniform(0.05, 0.6) * SIZE[o.name]
            p.alt_mode = rng.choice(('HEIGHT', 'HEIGHT', 'THROUGH', 'CUT'))
            S.mch_cut.depth_mode = 'THROUGH'
            p.bevel_width, p.bevel_segments = rng.uniform(0.01, 0.08), rng.choice((1, 2, 3, 4))
            p.bevel_sides = rng.choice(('TOP', 'BOTH'))
            k, loops = shape(view, o)
            desc = f'Base Mesh subtract {k} {p.profile} {p.alt_mode} h {p.height:.2f} from {view} on {o.name}'
            msg = bm_.perform_base(C, loops, proj(view), cutter=True, targets=[o])
        dt = time.time() - t0
        log('STEP', f'{step} {desc} | {str(msg)[:110]} ({dt:.2f} s)')
        if dt > 20:
            log('SLOW', f'{step} {dt:.1f} s: {desc}')
    except cg.CutError as ex:
        log('STEP', f'{step} {desc}')
        log('FAIL', f'{step} refused: {str(ex).splitlines()[0][:140]}')
    except Exception as ex:
        log('STEP', f'{step} {desc}')
        log('ERROR', f'{step} {type(ex).__name__}: {str(ex).splitlines()[0][:160] if str(ex) else ""}')
        traceback.print_exc()
    for x in parts():                              # (a piece made this step: measured on its own size)
        SIZE.setdefault(x.name, max(x.dimensions) or 1.0)
    judge(step, before, snapshot(), desc)
    if os.environ.get('MCH_SAVE_AFTER') == str(step):       # (debug: the scene just after this step)
        bpy.ops.wm.save_as_mainfile(filepath=os.environ['MCH_SAVE_AFTER_FILE'])

# ---- Divide every part: Bake High Poly Divide and the ZBrush way
if os.environ.get('MCH_SAVE') and not os.environ.get('MCH_SAVE_AT'):
    bpy.ops.wm.save_as_mainfile(filepath=os.environ['MCH_SAVE'])


def zbrush_divide(o, levels=2):
    """ZBrush's Mats as Polygroups -> CreasePG -> Divide: our export copy, crease on every polygroup border."""
    from mecha_lab import zbrush_bridge as zb
    tmp = zb.export_copy(C, o, False)
    me = tmp.data
    ids, _n, _nb = zb.crease_regions(me)
    e_s, f_s, st, en = em._edge_faces(me)
    cnt = en - st
    cr = np.zeros(len(me.edges), np.float32)
    cr[e_s[st[cnt != 2]]] = 1.0
    s2 = st[cnt == 2]
    cr[e_s[s2][ids[f_s[s2]] != ids[f_s[s2 + 1]]]] = 1.0
    a = me.attributes.get('crease_edge') or me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
    a.data.foreach_set('value', cr)
    m = tmp.modifiers.new('div', 'SUBSURF')
    m.levels = m.render_levels = levels
    m.use_creases = True
    m.use_limit_surface = True
    dg = C.evaluated_depsgraph_get()
    out = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    tmp.modifiers.clear()
    old = tmp.data
    tmp.data = out
    bpy.data.meshes.remove(old)
    return tmp


def divide_quality(o, hi):
    """(faces turned more than 107 degrees from the part's surface under them, farthest point off it / size)"""
    size = max(o.dimensions) or 1.0
    bvh = BVHTree.FromObject(o, C.evaluated_depsgraph_get())
    mw, ow = hi.matrix_world, o.matrix_world.inverted()
    flipped = 0
    rot = mw.to_3x3()
    for pf in hi.data.polygons:
        c = ow @ (mw @ Vector(pf.center))
        _loc, nrm, _i, dist = bvh.find_nearest(c)
        if nrm is None:
            continue
        n = (rot @ Vector(pf.normal)).normalized()
        if n.dot(nrm) >= -0.3:
            continue
        # (a thin wall: the face nearest may be the wall's other side - turned only when every face of the part
        # about as near is against it)
        near = bvh.find_nearest_range(c, dist + 0.005 * size)
        if all(n.dot(h[1]) < -0.3 for h in near):
            flipped += 1
    co = np.empty(len(hi.data.vertices) * 3)
    hi.data.vertices.foreach_get('co', co)
    d = max((bvh.find_nearest(ow @ (mw @ Vector(p)))[3] for p in co.reshape(-1, 3)[::5]), default=0.0) / size
    return flipped, d


def folds(me, limit=120.0):
    """edges of the Divide that are not Sharp / creased but whose two faces turn more than ``limit`` degrees (a fold:
    the surface doubles back on itself there)"""
    e_s, f_s, st, en = em._edge_faces(me)
    s2 = st[(en - st) == 2]
    if not len(s2):
        return 0
    n = np.empty(len(me.polygons) * 3)
    me.polygons.foreach_get('normal', n)
    n = n.reshape(-1, 3)
    ang = np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', n[f_s[s2]], n[f_s[s2 + 1]]), -1, 1)))
    hard = np.zeros(len(me.edges), bool)
    a = me.attributes.get('sharp_edge')
    if a is not None and a.domain == 'EDGE':
        a.data.foreach_get('value', hard)
    a = me.attributes.get('crease_edge')
    if a is not None and a.domain == 'EDGE':
        cr = np.zeros(len(me.edges), np.float32)
        a.data.foreach_get('value', cr)
        hard |= cr > 0.5
    return int(((ang > limit) & ~hard[e_s[s2]]).sum())


dev_worst = 0.0
for o in parts():
    if len(o.data.polygons) < 8:
        continue
    t0 = time.time()
    try:
        hp, info = bk.build(C, o, target_faces=100_000, bevels='DIVIDE')
        f1, d1 = divide_quality(o, hp)
        k1 = folds(hp.data)
        o.hide_set(False)
        zt = zbrush_divide(o)
        f2, d2 = divide_quality(o, zt)
        k2 = folds(zt.data)
        dev_worst = max(dev_worst, d1)
        log('STEP', f'divide {o.name}: {len(o.data.polygons):,} faces | Bake HP folds {k1} flipped {f1} off '
                    f'{d1 * 100:.2f} % | ZBrush-style folds {k2} flipped {f2} off {d2 * 100:.2f} % '
                    f'({time.time() - t0:.1f} s)')
        if k1:
            log('BAD', f'divide fold: {o.name} Bake HP Divide folds over at {k1} soft edges')
        if k2:
            log('BAD', f'zbrush fold: {o.name} ZBrush-style Divide folds over at {k2} soft edges')
        if f1:
            log('BAD', f'divide flip: {o.name} Bake HP Divide turned {f1} faces against the part')
        if f2:
            log('BAD', f'zbrush flip: {o.name} ZBrush-style Divide turned {f2} faces against the part')
        if d1 > 0.03:
            log('BAD', f'divide: {o.name} strays {d1 * 100:.1f} % of its size from the part')
        if d2 > 0.03:
            log('BAD', f'zbrush: {o.name} ZBrush-style Divide strays {d2 * 100:.1f} % of its size from the part')
    except RuntimeError as ex:
        if 'nothing to bake' not in str(ex):
            log('ERROR', f'divide {o.name}: {type(ex).__name__}: {str(ex)[:140]}')
            traceback.print_exc()
        else:
            log('FAIL', f'divide {o.name} refused: {str(ex)[:140]}')
    except Exception as ex:
        log('ERROR', f'divide {o.name}: {type(ex).__name__}: {str(ex)[:140]}')
        traceback.print_exc()
log('RESULT', f'seed {seed}: {len(parts())} parts, worst Divide {dev_worst * 100:.2f} %, {time.time() - t_run:.0f} s')
print('DONE', flush=True)
