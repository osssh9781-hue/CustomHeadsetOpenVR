"""0.24.297 Array Cut (user: "어레이컷 - 내가 정한 어레이 개수만큼 라쏘로 자르면 오른쪽으로 잘리는 거, 거리나 개수 이런 건 사후에
실시간 조정, 크기가 점점 작아지는 것 같은 것도" / "스케치 모드가 기본 작동이고 그 이후에 쉬프트 누르고 라인 그으면 어레이 가이드
라인 - 직선 모드 / 프리드로우 모드로 나누면 될 듯, 원으로도 박스로도, 그 라인을 따라서 생기는 거").

* Draw (any shape): the cut shape goes into a sketch (Alt + draw: subtract; Backspace: last; Esc: clear) - nothing
  is cut yet.
* Shift + draw: the array's guide (Guide: Line - start to end / Free - as drawn / Circle - round the point you start
  at, out to where you let go / Box - the rectangle from the start to the end).  The sketch is cut along it at once:
  Count copies (the shape itself the first), spread over the guide or one every Spacing; End Size makes them smaller
  (or bigger) toward the end; Align turns them with the guide.
* The cut stays live: Count / Spacing / End Size / Align / Guide change it (the parts as they were kept); Shift + draw
  again: a new guide; Enter (or Apply) keeps it.
The Cut tool's settings make the cut (Through All / From Surface, depth, edge finish ...).
"""
from __future__ import annotations

import json
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector

from . import core_geometry as cg

KEY = 'mch_array_cut'            # Scene: the live array cut (json)
MODE = 'ACUT'
_BUSY = [False]
_PENDING = [False]


# ---- the guide and the copies (pure, screen space) -----------------------------------------------------------------

def _centroid(loops):
    pts = [q for lp in loops for q in lp]
    return (sum(q[0] for q in pts) / len(pts), sum(q[1] for q in pts) / len(pts))


def guide_path(kind, raw, centre_of_shape):
    """(points, closed) of the guide from the raw Shift + drawn points."""
    raw = [tuple(q) for q in raw]
    if len(raw) < 2:
        return raw, False
    p0, p1 = raw[0], raw[-1]
    if kind == 'LINE':
        return [p0, p1], False
    if kind == 'CIRCLE':
        r = math.dist(p0, p1)
        if r < 1e-6:
            return [p0], False
        a0 = math.atan2(centre_of_shape[1] - p0[1], centre_of_shape[0] - p0[0])   # (starts at the shape)
        n = 96
        return [(p0[0] + r * math.cos(a0 + 2 * math.pi * k / n), p0[1] + r * math.sin(a0 + 2 * math.pi * k / n))
                for k in range(n)], True
    if kind == 'BOX':
        x0, x1 = sorted((p0[0], p1[0]))
        y0, y1 = sorted((p0[1], p1[1]))
        rect = [(x0, y0), (x1, y0), (x1, y1), (x0, y1)]
        # (starts at the point of the outline nearest the shape)
        best, bi, bt = None, 0, 0.0
        for i in range(4):
            a, b = rect[i], rect[(i + 1) % 4]
            dx, dy = b[0] - a[0], b[1] - a[1]
            ll = dx * dx + dy * dy
            t = 0.0 if ll < 1e-12 else max(0.0, min(1.0, ((centre_of_shape[0] - a[0]) * dx +
                                                          (centre_of_shape[1] - a[1]) * dy) / ll))
            d = math.dist(centre_of_shape, (a[0] + dx * t, a[1] + dy * t))
            if best is None or d < best:
                best, bi, bt = d, i, t
        a, b = rect[bi], rect[(bi + 1) % 4]
        start = (a[0] + (b[0] - a[0]) * bt, a[1] + (b[1] - a[1]) * bt)
        pts = [start] + [rect[(bi + 1 + k) % 4] for k in range(4)]
        if math.dist(pts[-1], start) < 1e-6:
            pts.pop()
        return pts, True
    out = [raw[0]]                                    # FREE: as drawn (points closer than 2 px dropped)
    for q in raw[1:]:
        if math.dist(q, out[-1]) >= 2.0:
            out.append(q)
    return out, False


def _sample(path, closed, d):
    """(point, tangent angle) at arc length ``d`` along the path."""
    pts = list(path) + ([path[0]] if closed else [])
    acc = 0.0
    for a, b in zip(pts, pts[1:]):
        ln = math.dist(a, b)
        if ln > 1e-12 and acc + ln >= d - 1e-9:
            t = (d - acc) / ln
            return (a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t), math.atan2(b[1] - a[1], b[0] - a[0])
        acc += ln
    a, b = pts[-2], pts[-1]
    return b, math.atan2(b[1] - a[1], b[0] - a[0])


def _length(path, closed):
    pts = list(path) + ([path[0]] if closed else [])
    return sum(math.dist(a, b) for a, b in zip(pts, pts[1:]))


def stations(path, closed, count, spacing_px):
    """[(point, angle)] where the copies go: the first at the guide's start."""
    n = max(1, int(count))
    total = _length(path, closed)
    if total <= 1e-9 or len(path) < 2:
        return [(path[0] if path else (0.0, 0.0), 0.0)]
    if spacing_px > 0.0:
        ds = []
        k = 0
        while k < n and k * spacing_px <= total + 1e-6 and not (closed and k and k * spacing_px >= total - 1e-6):
            ds.append(k * spacing_px)
            k += 1
    elif closed:
        ds = [total * i / n for i in range(n)]
    else:
        ds = [total * i / max(1, n - 1) for i in range(n)] if n > 1 else [0.0]
    return [_sample(path, closed, d) for d in ds]


def copies(loops, path, closed, count, spacing_px=0.0, end_scale=1.0, align=False):
    """[[loop, ...] per copy]: the shape moved along the guide (the first copy = the shape itself)."""
    st = stations(path, closed, count, spacing_px)
    c = _centroid(loops)
    (g0x, g0y), a0 = st[0]
    out = []
    m = len(st)
    for i, ((gx, gy), a) in enumerate(st):
        s = 1.0 + (end_scale - 1.0) * (i / (m - 1) if m > 1 else 0.0)
        turn = (a - a0) if align else 0.0
        ca, sa = math.cos(turn), math.sin(turn)
        dx, dy = gx - g0x, gy - g0y
        cp = []
        for lp in loops:
            q2 = []
            for x, y in lp:
                x, y = (x - c[0]) * s, (y - c[1]) * s
                x, y = x * ca - y * sa, x * sa + y * ca
                q2.append((c[0] + x + dx, c[1] + y + dy))
            cp.append(q2)
        out.append(cp)
    return out


# ---- the live cut ---------------------------------------------------------------------------------------------------

def record(scene):
    try:
        raw = scene.get(KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError):
        return None


def _px_per_world(proj, targets):
    from . import armor_plate as ap
    for t in targets:
        v = ap.px_per_world(proj, t)
        if v > 0.0:
            return v
    return float(getattr(proj, 'ppu', 0.0) or 0.0)


def _targets_for(context, proj, loops):
    from . import cut_engine as ce
    how = getattr(getattr(context.scene, 'mch_cut', None), 'targets', 'AUTO')
    if how == 'AUTO':
        return ce.auto_targets(context.view_layer, proj, loops)
    if how == 'ACTIVE':
        ob = context.active_object
        return [ob] if ob is not None and ob.type == 'MESH' else []
    return [o for o in context.selected_objects if o.type == 'MESH']


def _cut(context, rec):
    """Cut the record's copies into its parts (from the kept meshes).  Returns (copies cut, message)."""
    from . import armor_plate as ap
    from . import cut_engine as ce
    st = context.scene.mch_acut
    proj = ap.thaw_projector(rec['proj'])
    loops = [[tuple(q) for q in lp] for lp in rec['loops']]
    path, closed = guide_path(st.guide, rec['guide'], _centroid(loops))
    targets = [bpy.data.objects[n] for n in rec['targets'] if n in bpy.data.objects]
    if not targets:
        raise cg.CutError('Array Cut: its parts are gone.')
    for t in targets:                                  # back to the parts as they were
        me = bpy.data.meshes.get(rec['backups'].get(t.name, ''))
        if me is not None:
            bm_copy(me, t.data)
    pxw = _px_per_world(proj, targets)
    sp = st.spacing * pxw if st.spacing > 0.0 and pxw > 0.0 else 0.0
    cps = copies(loops, path, closed, st.count, sp, st.end_scale, st.align)
    all_loops = [lp for cp in cps for lp in cp]
    try:
        msg = ce.perform_closed(context, 'CUT', targets, all_loops, proj)
    except cg.CutError:
        msg = ''                                       # (copies overlapping each other: one by one)
        for cp in cps:
            alive = [t for t in targets if t.name in bpy.data.objects]
            msg = ce.perform_closed(context, 'CUT', alive, cp, proj)
    return len(cps), msg


def bm_copy(src, dst):
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(src)
        bm.to_mesh(dst)
    finally:
        bm.free()
    dst.update()


def set_guide(context, raw_pts, projector):
    """Shift + draw finished: the guide.  The sketch (or the live cut's shape) is cut along it.  Returns a report."""
    from . import armor_plate as ap
    from . import lasso_sketch as ls
    scene = context.scene
    d = ls.data(scene)
    rec = record(scene)
    if d is not None and d.get('mode') == MODE:
        loops, proj = ls.screen_loops(d)
        if rec is not None:
            finish(context)                            # (a new sketch: the last array is kept as it is)
            rec = None
    elif rec is not None:
        loops, proj = [[tuple(q) for q in lp] for lp in rec['loops']], ap.thaw_projector(rec['proj'])
    else:
        raise cg.CutError('Array Cut: draw the shape to cut first, then Shift + draw the guide.')
    if not loops:
        raise cg.CutError('Array Cut: the sketch is empty.')
    guide = _to_proj(raw_pts, projector, proj, d)
    if len(guide) < 2:
        raise cg.CutError('Array Cut: the guide is too short.')
    if rec is None:
        frozen = d['proj']
        st = scene.mch_acut
        path, closed = guide_path(st.guide, guide, _centroid(loops))
        reach = [lp for cp in copies(loops, path, closed, st.count, 0.0, max(1.0, st.end_scale), False) for lp in cp]
        targets = _targets_for(context, proj, reach)
        if not targets:
            raise cg.CutError('Array Cut: the shape and its guide cover no mesh (or select one).')
        backups = {}
        for t in targets:
            cg.check_target(t)
            b = t.data.copy()
            b.name = 'MCH_ArrayCutBackup_' + t.name
            b.use_fake_user = True
            backups[t.name] = b.name
        rec = {'loops': [[list(q) for q in lp] for lp in loops], 'proj': frozen, 'targets': [t.name for t in targets],
               'backups': backups}
    rec['guide'] = [list(q) for q in guide]
    scene[KEY] = json.dumps(rec)
    if d is not None and d.get('mode') == MODE:
        ls.clear(scene)
    n, _msg = _cut(context, rec)
    return (f'Array Cut: {n} cuts along the guide ({scene.mch_acut.guide.title()}) - Count / Spacing / End Size / '
            'Align change it now; Shift + draw: a new guide; Enter: keep')


def _to_proj(raw_pts, cur, proj, sketch):
    """The guide's points (drawn in the view now) in the sketch's first view (through the sketch's plane)."""
    from . import lasso_sketch as ls
    if sketch is None:
        return [tuple(q) for q in raw_pts]
    frame = ls._frame(sketch)
    origin, n = frame.translation, frame.col[2].to_3d().normalized()
    out = []
    for q in raw_pts:
        o, dv = cur.ray(q)
        if abs(dv.dot(n)) < 1e-6:
            continue
        w = cg._plane_hit(o, dv, origin, n)[0]
        s = proj.to_screen(w)
        if s is not None:
            out.append((float(s[0]), float(s[1])))
    return out


def refresh(context):
    """A setting changed: cut again from the kept parts."""
    rec = record(context.scene)
    if rec is None or _BUSY[0] or not rec.get('guide'):
        return
    _BUSY[0] = True
    try:
        _cut(context, rec)
    except cg.CutError as ex:
        print('Mecha Array Cut:', ex)
    finally:
        _BUSY[0] = False


def flush():
    if not _PENDING[0]:
        return None
    _PENDING[0] = False
    try:
        refresh(bpy.context)
    except (RuntimeError, ReferenceError, AttributeError):
        pass
    return None


def _upd(self, context):
    """From a timer, not inside the update (a cut inside a property update can take Blender down)."""
    if record(context.scene) is None:
        return
    _PENDING[0] = True
    if bpy.app.background:
        return
    try:
        if not bpy.app.timers.is_registered(flush):
            bpy.app.timers.register(flush, first_interval=0.0)
    except (ValueError, RuntimeError):
        pass


def finish(context):
    """Keep the live array cut as it is (the kept meshes go)."""
    scene = context.scene
    rec = record(scene)
    if rec is None:
        return False
    for name in rec.get('backups', {}).values():
        me = bpy.data.meshes.get(name)
        if me is not None:
            me.use_fake_user = False
            if me.users == 0:
                bpy.data.meshes.remove(me)
    del scene[KEY]
    return True


class MCH_PG_ArrayCut(bpy.types.PropertyGroup):
    guide: EnumProperty(name='Guide', default='LINE', update=_upd, items=[
        ('LINE', 'Line', 'Shift + draw: a straight guide from where you start to where you let go'),
        ('FREE', 'Free', 'Shift + draw: the guide exactly as drawn'),
        ('CIRCLE', 'Circle', 'Shift + draw: a circle round the point you start at, out to where you let go'),
        ('BOX', 'Box', 'Shift + draw: the rectangle from where you start to where you let go')])
    count: IntProperty(name='Count', default=5, min=1, soft_max=40, max=500, update=_upd,
                       description='How many cuts along the guide (the drawn shape is the first)')
    spacing: FloatProperty(name='Spacing', default=0.0, min=0.0, soft_max=2.0, precision=4, unit='LENGTH', update=_upd,
                           description='The distance between cuts along the guide (0 = Count spread over the whole '
                                       'guide)')
    end_scale: FloatProperty(name='End Size', default=1.0, min=0.05, soft_max=2.0, max=5.0, update=_upd,
                             description='The size of the last cut (x the drawn shape): less = smaller and smaller '
                                         'toward the end of the guide')
    align: BoolProperty(name='Align', default=False, update=_upd,
                        description='Each cut turned with the guide (round a circle: facing the middle)')


class MCH_OT_array_cut_apply(bpy.types.Operator):
    """Apply: keep the live Array Cut as it is"""
    bl_idname = 'mch.array_cut_apply'
    bl_label = 'Apply Array Cut'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return record(context.scene) is not None

    def execute(self, context):
        finish(context)
        self.report({'INFO'}, 'Array Cut: kept')
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_acut
    live = record(context.scene) is not None
    box = layout.box()
    col = box.column(align=True)
    col.label(text='Array Cut' + (' (live)' if live else ''), icon='MOD_ARRAY')
    col.label(text='Draw: the shape (a sketch) - Shift + draw: the guide')
    col.prop(st, 'guide', expand=True)
    col = box.column(align=True)
    col.prop(st, 'count')
    col.prop(st, 'spacing', text='Spacing (0: spread)')
    col.prop(st, 'end_scale', slider=True)
    col.prop(st, 'align')
    if live:
        box.operator('mch.array_cut_apply', text='Apply (Enter)', icon='CHECKMARK')


CLASSES = (MCH_PG_ArrayCut, MCH_OT_array_cut_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_acut = bpy.props.PointerProperty(type=MCH_PG_ArrayCut)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_acut'):
        del bpy.types.Scene.mch_acut
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
