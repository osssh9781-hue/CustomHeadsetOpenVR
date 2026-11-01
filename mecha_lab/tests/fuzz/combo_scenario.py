"""Combination fuzz (user: "복스 하이드, 베이스 메쉬 빼기, 컷, 스플릿 이거 다 조합해 가지고 한 100개 만들어 보고 문제 계속
추적해 줄래?"): one random part per seed - a box, a plate or a Base Mesh part - then random Box Hide (hide + apply,
hide + a cylinder restored, hide + Split Off), Base Mesh Alt subtract (Carve Height / Through / Like Cut), Cut
(circle / rectangle / polygon / line groove; Off / Chamfer / Bevel / GN; through or a pocket) and Split, from the top,
front, side or below, on any part made so far.  After every step the parts are checked; at the end each is made a
Bake High Poly Divide.

    <python with bpy> combo_scenario.py <seed> <steps>          (run_fuzz.py ... combo_scenario.py runs many)

Lines: STEP (what was done), ERROR (a Python error - a bug), FAIL (refused with a message), SLOW (a step over 20 s),
BAD (a check failed: open / 3-face edges on a part that was closed, the part grew, NaN, an empty part, hard edges left
without a crease, a Divide far off the part), DONE.
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
    kind = rng.choice(('box', 'box', 'plate', 'base', 'base'))
    if kind == 'base':
        p = bm_.scene_defaults(C)
        p.sketch = False
        p.profile = rng.choice(('FLAT', 'CHAMFER', 'BEVEL'))
        p.height = rng.uniform(0.3, 1.2)
        if p.profile != 'FLAT':
            p.bevel_width, p.bevel_segments = rng.uniform(0.02, 0.12), rng.choice((1, 2, 3, 4))
        n = rng.randint(4, 9)
        r0 = rng.uniform(0.8, 1.6)
        pts = []
        for i in range(n):
            a = 2 * math.pi * i / n + rng.uniform(-0.2, 0.2)
            r = r0 * rng.uniform(0.6, 1.0)
            pts.append((500 + math.cos(a) * r * PPU, 500 + math.sin(a) * r * PPU))
        before = set(bpy.data.objects)
        bm_.perform_base(C, [pts], proj('TOP'))
        ob = [o for o in bpy.data.objects if o not in before][0]
        return ob, f'Base Mesh {p.profile} ({n} corners, height {p.height:.2f})'
    dims = ((rng.uniform(1.2, 3.0), rng.uniform(1.2, 3.0), rng.uniform(0.6, 1.6)) if kind == 'box'
            else (rng.uniform(2.0, 3.5), rng.uniform(1.2, 2.4), rng.uniform(0.12, 0.35)))
    me = bpy.data.meshes.new('Part')
    b = bmesh.new()
    bmesh.ops.create_cube(b, size=1.0)
    for v in b.verts:
        v.co = Vector((v.co.x * dims[0], v.co.y * dims[1], v.co.z * dims[2]))
    b.to_mesh(me)
    b.free()
    ob = bpy.data.objects.new('Part', me)
    S.collection.objects.link(ob)
    em.mark_generated(me)
    return ob, f'{kind} {dims[0]:.2f} x {dims[1]:.2f} x {dims[2]:.2f}'


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
                nan=bool(np.isnan(co).any()), lo=co.min(0) if len(co) else None, hi=co.max(0) if len(co) else None)


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
    f = rng.choice(('NONE', 'NONE', 'CHAMFER', 'BEVEL', 'GN'))
    if f in ('CHAMFER', 'BEVEL'):
        cut.edge_finish, cut.finish_width, cut.finish_segments = f, rng.choice((0.01, 0.02, 0.04)), rng.choice((1, 2, 3))
    elif f == 'GN':
        cut.gn_finish, cut.gn_width, cut.gn_segments = rng.choice(('CHAMFER', 'BEVEL')), 0.02, 3
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
    view = rng.choice(('TOP', 'TOP', 'FRONT', 'SIDE', 'BOTTOM'))
    op = rng.choice(('cut', 'cut', 'cut', 'split', 'hide', 'hide', 'sub', 'sub'))
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
            p.profile = rng.choice(('FLAT', 'CHAMFER', 'BEVEL'))
            p.height = rng.uniform(0.05, 0.6) * SIZE[o.name]
            p.alt_mode = rng.choice(('HEIGHT', 'HEIGHT', 'THROUGH', 'CUT'))
            S.mch_cut.depth_mode = 'THROUGH'
            if p.profile != 'FLAT':
                p.bevel_width, p.bevel_segments = rng.uniform(0.01, 0.06), rng.choice((1, 2, 3))
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

# ---- Divide every part
if os.environ.get('MCH_SAVE') and not os.environ.get('MCH_SAVE_AT'):
    bpy.ops.wm.save_as_mainfile(filepath=os.environ['MCH_SAVE'])
dev_worst = 0.0
for o in parts():
    if len(o.data.polygons) < 20:
        continue
    t0 = time.time()
    try:
        size = max(o.dimensions) or 1.0
        bvh = BVHTree.FromObject(o, C.evaluated_depsgraph_get())
        hp, info = bk.build(C, o, target_faces=150_000, bevels='DIVIDE')
        co = np.empty(len(hp.data.vertices) * 3)
        hp.data.vertices.foreach_get('co', co)
        mw = hp.matrix_world
        ow = o.matrix_world.inverted()
        d = max((bvh.find_nearest(ow @ (mw @ Vector(p)))[3] for p in co.reshape(-1, 3)[::7]), default=0.0) / size
        dev_worst = max(dev_worst, d)
        log('STEP', f'divide {o.name}: {len(o.data.polygons):,} -> {len(hp.data.polygons):,} faces, farthest '
                    f'{d * 100:.2f} % of its size ({time.time() - t0:.1f} s)')
        if d > 0.03:
            log('BAD', f'divide: {o.name} strays {d * 100:.1f} % of its size from the part')
        o.hide_set(False)
    except RuntimeError as ex:
        if 'nothing to bake' not in str(ex):
            raise
        log('FAIL', f'divide {o.name} refused: {str(ex)[:140]}')   # (an all-hidden live part: a refusal, not a bug)
    except Exception as ex:
        log('ERROR', f'divide {o.name}: {type(ex).__name__}: {str(ex)[:140]}')
        traceback.print_exc()
log('RESULT', f'seed {seed}: {len(parts())} parts, worst Divide {dev_worst * 100:.2f} %, {time.time() - t_run:.0f} s')
print('DONE', flush=True)
