"""0.24.178 Boolean Bevel (user: "불린 베벨 만들자, 그건 걍 메뉴로 빼 주고, 내가 원하는 만큼 그리면 걍 그 부분이 베벨 불린이
되는 거, 챔퍼랑"): its own tool.  The part's edges you can use are shown (edge_runs); drag along one - that much of it
is cut off by a boolean, a chamfer (flat) or a round (an arc), Width wide; a click takes the whole edge.  The cut is
real (the part's own mesh - its modifiers stay as they are); Ctrl+Z takes it back.

The cutter: along the edge (the part of it drawn over), a prism whose section is what a bevel of that width takes off
the corner - the two faces' planes at the edge, the points ``Width`` in from the edge on each, and between them a
straight line (Chamfer) or an arc touching both faces (Round) - running out past the surface.  Where the drawn part
reaches the end of the edge it runs on past it (the cut goes through the corner), elsewhere it stops square.  Only
outside (convex) edges.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from bpy.props import EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Vector

from . import edge_runs

PROFILES = (('CHAMFER', 'Chamfer', 'A flat cut across the edge'),
            ('ROUND', 'Round', 'A round cut (an arc touching both faces)'))


def _redraw(self, context):
    for a in getattr(getattr(context, 'screen', None), 'areas', []):
        if a.type == 'VIEW_3D':
            a.tag_redraw()


class MCH_PG_BoolBevel(bpy.types.PropertyGroup):
    profile: EnumProperty(name='Profile', items=PROFILES, default='CHAMFER', update=_redraw)
    width: FloatProperty(name='Width', default=0.05, min=0.0005, soft_max=1.0, precision=3, unit='LENGTH',
                         update=_redraw, description='How far in from the edge the cut goes, on each face')
    segments: IntProperty(name='Round Segments', default=8, min=2, max=48,
                          description='Steps of the round cut\'s arc')


class BevelError(Exception):
    pass


# -----------------------------------------------------------------------------
# the cutter
# -----------------------------------------------------------------------------

def _unit(v):
    n = float(np.linalg.norm(v))
    return v / n if n > 1e-12 else v


def _sides(runs, rid):
    """Per run segment: (normal A, centre A, normal B, centre B) - the two faces kept on the same sides along it."""
    out = []
    prev = None
    for e in runs.edge_ids[rid]:
        (n0, c0), (n1, c1) = runs.faces[e]
        if prev is not None and float(np.dot(n1, prev)) > float(np.dot(n0, prev)):
            (n0, c0), (n1, c1) = (n1, c1), (n0, c0)
        out.append((n0, c0, n1, c1))
        prev = n0
    return out


def _frame(P, T, nA, cA, nB, cB):
    """The section's directions at an edge point: (dA, dB) in each face going away from the edge; None for an inside
    (concave) edge."""
    dA = _unit(np.cross(nA, T))
    if float(np.dot(cA - P, dA)) < 0:
        dA = -dA
    dB = _unit(np.cross(nB, T))
    if float(np.dot(cB - P, dB)) < 0:
        dB = -dB
    if float(np.dot(cB - P, nA)) > 1e-9 * (1.0 + float(np.linalg.norm(cB - P))):
        return None                                   # (face B above face A's plane: an inside corner)
    return dA, dB


def section(P, T, nA, nB, dA, dB, w, profile, segments):
    """The cutter's section points at an edge point (a closed polygon)."""
    A, B = P + dA * w, P + dB * w
    h = w * 0.9 + 1e-6
    out_n = _unit(nA + nB)
    if profile == 'ROUND':
        alpha = math.acos(max(-1.0, min(1.0, float(np.dot(dA, dB)))))
        bis = _unit(dA + dB)
        C = P + bis * (w / max(math.cos(alpha / 2), 1e-3))
        r = w * math.tan(alpha / 2)
        u = _unit(A - C)
        v = B - C
        v = _unit(v - u * float(np.dot(v, u)))
        phi = math.acos(max(-1.0, min(1.0, float(np.dot(_unit(A - C), _unit(B - C))))))
        arc = [C + r * (math.cos(phi * k / segments) * u + math.sin(phi * k / segments) * v) for k in range(segments + 1)]
        pts = arc
    else:
        pts = [A, B]
    return pts + [B + nB * h, P + out_n * h * 1.6, A + nA * h]


def cutter_mesh(runs, rid, s0, s1, w, profile='CHAMFER', segments=8, name='MCH_BoolBevel_Cutter'):
    """The cutter (the part's local space) for run ``rid`` between arc lengths ``s0`` .. ``s1`` (a loop: ``s1`` may run
    past its length).  Raises BevelError for an inside edge."""
    P = runs.polyline(rid)
    closed = runs.closed[rid]
    L = np.linalg.norm(P[1:] - P[:-1], axis=1)
    acc = np.concatenate([[0.0], np.cumsum(L)])
    total = float(acc[-1])
    sides = _sides(runs, rid)
    nseg = len(L)
    whole_loop = closed and s1 - s0 >= total - 1e-9

    def at(s):
        """(point, tangent, nA, cA, nB, cB) at arc length ``s``; at a run point the two segments' mean."""
        if closed:
            s = s % total if total > 0 else 0.0
        s = min(max(s, 0.0), total)
        k = int(np.searchsorted(acc, s, side='right') - 1)
        k = min(max(k, 0), nseg - 1)
        t = (s - acc[k]) / max(L[k], 1e-12)
        p = P[k] + (P[k + 1] - P[k]) * t
        ks = [k]
        if t < 1e-6 and (k > 0 or closed):
            ks.append((k - 1) % nseg)
        elif t > 1 - 1e-6 and (k < nseg - 1 or closed):
            ks.append((k + 1) % nseg)
        T = _unit(np.sum([_unit(P[j + 1] - P[j]) for j in ks], axis=0))
        nA = _unit(np.sum([sides[j][0] for j in ks], axis=0))
        nB = _unit(np.sum([sides[j][2] for j in ks], axis=0))
        return p, T, nA, sides[k][1], nB, sides[k][3]

    # where the sections go: the two ends and every run point between
    if whole_loop:
        params = list(acc[:-1])
    else:
        inner = [float(a) for a in acc if s0 + 1e-9 < a < s1 - 1e-9]
        if closed:
            inner = sorted({float(a + total * m) for a in acc[:-1] for m in (0, 1) if s0 + 1e-9 < a + total * m < s1 - 1e-9})
        params = [s0] + inner + [s1]
    secs = []
    for s in params:
        p, T, nA, cA, nB, cB = at(s)
        fr = _frame(p, T, nA, cA, nB, cB)
        if fr is None:
            raise BevelError('That edge is an inside corner - Boolean Bevel cuts outside edges')
        secs.append((p, T, section(p, T, nA, nB, fr[0], fr[1], w, profile, segments)))
    if not whole_loop:                               # (past the end of the edge where the drawn part reaches it)
        ext = w * 1.2
        if not closed and s0 <= 1e-6 * max(total, 1.0) + 1e-9:
            p, T, pts = secs[0]
            secs.insert(0, (p - T * ext, T, [q - T * ext for q in pts]))
        if not closed and s1 >= total - 1e-6 * max(total, 1.0) - 1e-9:
            p, T, pts = secs[-1]
            secs.append((p + T * ext, T, [q + T * ext for q in pts]))
    bm = bmesh.new()
    rings = [[bm.verts.new(Vector(q)) for q in pts] for _p, _T, pts in secs]
    m = len(rings[0])
    count = len(rings) if whole_loop else len(rings) - 1
    for i in range(count):
        a, b = rings[i], rings[(i + 1) % len(rings)]
        for j in range(m):
            try:
                bm.faces.new((a[j], a[(j + 1) % m], b[(j + 1) % m], b[j]))
            except ValueError:
                pass
    if not whole_loop:
        for ring in (rings[0], rings[-1]):
            try:
                bm.faces.new(ring)
            except ValueError:
                pass
    bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=w * 1e-5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    return me


# -----------------------------------------------------------------------------
# the cut
# -----------------------------------------------------------------------------

def _solvers():
    return [i.identifier for i in bpy.types.BooleanModifier.bl_rna.properties['solver'].enum_items]


def cut(context, ob, cutter_me):
    """``cutter_me`` (the part's local space) taken out of ``ob``'s own mesh (its other modifiers left alone, not
    baked): Manifold first, Exact when it refuses (an open part).  Returns the faces before / after."""
    from . import core_geometry as cg, light_copies as lc
    cutter = cg.link_temp_object(context, cutter_me, 'MCH_BoolBevel_TEMP')
    cutter.matrix_world = ob.matrix_world.copy()
    saved = [(m, m.show_viewport) for m in ob.modifiers]
    mod = ob.modifiers.new('MCH_BoolBevel', 'BOOLEAN')
    mod.operation = 'DIFFERENCE'
    mod.object = cutter
    before = len(ob.data.polygons)
    new = None
    try:
        for m_, _s in saved:
            m_.show_viewport = False
        for solver in [x for x in ('MANIFOLD', 'EXACT') if x in _solvers()]:
            mod.solver = solver
            dg = context.evaluated_depsgraph_get()
            dg.update()
            try:
                me = bpy.data.meshes.new_from_object(lc.full(ob, dg), preserve_all_data_layers=True, depsgraph=dg)
            except RuntimeError:
                continue
            if len(me.polygons) and _changed(me, ob.data):
                new = me
                break
            bpy.data.meshes.remove(me)
    finally:
        try:
            ob.modifiers.remove(mod)
        except (ReferenceError, RuntimeError):
            pass
        for m_, show in saved:
            try:
                m_.show_viewport = show
            except ReferenceError:
                pass
        cg.remove_object_and_mesh(cutter)
    if new is None:
        raise BevelError('The cut took nothing off (is the edge inside the part, or the part not closed?)')
    old = ob.data
    new.name = old.name
    if not len(new.materials):
        for mt in old.materials:
            new.materials.append(mt)
    ob.data = new
    if old.users == 0:
        bpy.data.meshes.remove(old)
    edge_runs.clear()
    return before, len(new.polygons)


def _changed(a, b):
    if len(a.polygons) != len(b.polygons) or len(a.vertices) != len(b.vertices):
        return True
    ca = np.empty(len(a.vertices) * 3, np.float32)
    cb = np.empty(len(b.vertices) * 3, np.float32)
    a.vertices.foreach_get('co', ca)
    b.vertices.foreach_get('co', cb)
    return float(np.abs(np.sort(ca) - np.sort(cb)).max()) > 1e-6


def portion(runs, pts, reach, whole=False):
    """(run, s0, s1) the drawn points ``pts`` (local) run along: the run most of them are near, from the first to
    the last of them along it (a loop: the short way round); ``whole`` (a click): all of it.  None: no edge there."""
    votes = {}
    near = []
    for p in pts:
        hit = runs.nearest(p, reach)
        if hit is not None:
            votes[hit[0]] = votes.get(hit[0], 0) + 1
            near.append((hit[0], p))
    if not votes:
        return None
    rid = max(votes, key=votes.get)
    s, total = runs.arc(rid, [p for r, p in near if r == rid])
    if whole or len(s) < 2 or float(np.ptp(s)) < 1e-9:
        return rid, 0.0, total
    if not runs.closed[rid]:
        return rid, float(s.min()), float(s.max())
    v = np.sort(s)
    gaps = np.diff(np.concatenate([v, [v[0] + total]]))
    k = int(np.argmax(gaps))                          # (the biggest gap is what was not drawn over)
    start = float(v[(k + 1) % len(v)])
    end = float(v[k]) + (total if k + 1 < len(v) else 0.0)
    if end <= start:
        end += total
    return rid, start, end


def _mean_scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def perform(context, ob, pts_local, whole=False, reach=None):
    """Boolean Bevel ``ob`` along the edge ``pts_local`` (its local space) were drawn over.  Returns a message."""
    st = context.scene.mch_bool_bevel
    w = st.width / _mean_scale(ob)
    runs = edge_runs.get(ob)
    got = portion(runs, pts_local, reach if reach is not None else max(w * 1.5, 1e-6), whole)
    if got is None:
        raise BevelError('No edge there - drag along one of the shown edges of the part')
    rid, s0, s1 = got
    me = cutter_mesh(runs, rid, s0, s1, w, st.profile, st.segments)
    try:
        before, after = cut(context, ob, me)
    finally:
        try:                                          # (cut() removes it with its temporary object)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        except ReferenceError:
            pass
    length = (s1 - s0) * _mean_scale(ob)
    return (f'Boolean Bevel ({st.profile.title()}, {st.width:.3g} wide) on "{ob.name}": {length:.3g} of the edge '
            f'({before:,} -> {after:,} faces)')


# -----------------------------------------------------------------------------
# the tool
# -----------------------------------------------------------------------------

HOVER = {'part': None, 'run': None, 'region': None}
_LIVE = {'op': None}


def _pick(context, xy):
    from . import geo_sculpt as gs
    return gs.pick_part(context, xy)


def _reach_px(context, ob, loc, px=14.0):
    from . import geo_sculpt as gs
    return (px / gs.px_per_world(context.region, context.region_data, loc)) / _mean_scale(ob)


def tool_on(context):
    from . import tool_state as ts
    try:
        return ts.effective_tool(context) == 'BBEVEL'
    except (AttributeError, KeyError, TypeError):
        return False


def draw_edges():
    context = bpy.context
    try:
        if not tool_on(context):
            return
        op = _LIVE['op']
        name = op.ob.name if op is not None else HOVER['part']
        ob = bpy.data.objects.get(name) if name else None
        if ob is None or ob.type != 'MESH':
            return
        runs = edge_runs.get(ob)
        edge_runs.draw_lines(edge_runs.world_segs(ob, runs), (0.35, 0.85, 1.0, 0.55), 1.5)
        if op is not None and op.portion is not None:
            rid, s0, s1 = op.portion
            edge_runs.draw_lines(edge_runs.portion_segs(ob, runs, rid, s0, s1), (1.0, 0.5, 0.1, 1.0), 5.0)
        elif HOVER['run'] is not None and HOVER['run'] < len(runs.edge_ids):
            edge_runs.draw_lines(edge_runs.world_segs(ob, runs, runs.edge_ids[HOVER['run']]), (1.0, 0.92, 0.2, 1.0),
                                 4.0)
    except (ReferenceError, AttributeError, RuntimeError, KeyError):
        pass


class MCH_OT_bool_bevel_hover(bpy.types.Operator):
    """(Boolean Bevel) the part and edge under the mouse, shown (passes the move on)"""
    bl_idname = 'mch.bool_bevel_hover'
    bl_label = 'Boolean Bevel Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW' or _LIVE['op'] is not None:
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit = _pick(context, xy)
        part, run = None, None
        if hit is not None:
            ob, loc, _n = hit
            part = ob.name
            try:
                got = edge_runs.get(ob).nearest(ob.matrix_world.inverted_safe() @ loc, _reach_px(context, ob, loc))
                run = got[0] if got is not None else None
            except (ReferenceError, RuntimeError, ValueError):
                run = None
        if (part, run) != (HOVER['part'], HOVER['run']):
            HOVER['part'], HOVER['run'] = part, run
            context.region.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_bool_bevel_draw(bpy.types.Operator):
    """Boolean Bevel: drag along one of the shown edges of a part - that much of it is cut off (Chamfer / Round, Width
    wide); a click takes the whole edge"""
    bl_idname = 'mch.bool_bevel_draw'
    bl_label = 'Boolean Bevel'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        from . import geo_sculpt as gs
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit = _pick(context, xy)
        if hit is None:
            return {'PASS_THROUGH'}
        self.ob, loc, _n = hit
        try:
            self.caster = gs.SurfaceCaster(context, self.ob)
        except (RuntimeError, AttributeError, ReferenceError):
            return {'PASS_THROUGH'}
        first = self.caster.cast(context, xy)
        if first is None:
            return {'PASS_THROUGH'}
        self.p0 = xy
        self.moved = 0.0
        self.pts = [tuple(first[0])]
        st = context.scene.mch_bool_bevel
        self.reach = max(st.width * 1.5 / _mean_scale(self.ob), _reach_px(context, self.ob, loc))
        self.runs = edge_runs.get(self.ob)
        self.portion = None
        self._update()
        _LIVE['op'] = self
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _update(self):
        self.portion = portion(self.runs, self.pts, self.reach, whole=self.moved < 6.0)

    def _end(self, context):
        _LIVE['op'] = None
        HOVER['run'] = None
        if context.area:
            context.area.tag_redraw()

    def modal(self, context, event):
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            self.moved = max(self.moved, math.dist(self.p0, xy))
            hit = self.caster.cast(context, xy)
            if hit is not None:
                self.pts.append(tuple(hit[0]))
                self._update()
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._end(context)
            try:
                msg = perform(context, self.ob, self.pts, whole=self.moved < 6.0, reach=self.reach)
            except BevelError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'CANCELLED'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'TRACKPADPAN', 'TRACKPADZOOM', 'NDOF_MOTION'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


def draw(layout, context):
    st = context.scene.mch_bool_bevel
    row = layout.row(align=True)
    row.prop_enum(st, 'profile', 'CHAMFER')
    row.prop_enum(st, 'profile', 'ROUND')
    col = layout.column(align=True)
    col.prop(st, 'width')
    if st.profile == 'ROUND':
        col.prop(st, 'segments')
    col = layout.column(align=True)
    for line in ('Drag along a shown edge: that much of it is cut off',
                 'Click an edge: all of it.  Ctrl+Z: back',
                 'Blue: edges you can use; yellow: under the mouse'):
        col.label(text=line)


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return
    draw(layout, context)


class MCH_TOOL_bool_bevel(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.bool_bevel'
    bl_label = 'Mecha Boolean Bevel'
    bl_description = ('Drag along an edge of a part: that much of it is cut off by a boolean - a chamfer or a round, '
                      'Width wide.\nClick an edge: all of it')
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = (('mch.bool_bevel_hover', {'type': 'MOUSEMOVE', 'value': 'ANY', 'any': True}, None),
                 ('mch.bool_bevel_draw', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_PG_BoolBevel, MCH_OT_bool_bevel_hover, MCH_OT_bool_bevel_draw)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bool_bevel = PointerProperty(type=MCH_PG_BoolBevel)
    try:
        bpy.utils.register_tool(MCH_TOOL_bool_bevel, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_edges, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_bool_bevel)
    except (ValueError, RuntimeError, KeyError):
        pass
    if hasattr(bpy.types.Scene, 'mch_bool_bevel'):
        del bpy.types.Scene.mch_bool_bevel
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
