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
    width: FloatProperty(name='Width', default=0.05, min=0.00005, soft_min=0.0002, soft_max=0.2, precision=4,
                         step=0.1, unit='LENGTH', update=_redraw,
                         description='How far in from the edge the cut goes, on each face (0.24.179: down to 0.05 mm, '
                                     'the slider finer)')
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
    """Per run segment: (normal A, way into A, normal B, way into B) - the two faces kept on the same sides along it."""
    out = []
    prev = None
    for e in runs.edge_ids[rid]:
        (n0, i0, _f0), (n1, i1, _f1) = runs.faces[e][:2]
        if prev is not None and float(np.dot(n1, prev)) > float(np.dot(n0, prev)):
            n0, i0, n1, i1 = n1, i1, n0, i0
        out.append((n0, i0, n1, i1))
        prev = n0
    return out


def _frame(P, T, nA, inA, nB, inB):
    """The section's directions at an edge point: (dA, dB) in each face going away from the edge; None for an inside
    (concave) edge."""
    dA = _unit(np.cross(nA, T))
    if float(np.dot(inA, dA)) < 0:
        dA = -dA
    dB = _unit(np.cross(nB, T))
    if float(np.dot(inB, dB)) < 0:
        dB = -dB
    if float(np.dot(dB, nA)) > 1e-6:
        return None                                   # (face B rises above face A's plane: an inside corner)
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


def _end(runs, rid, k, sec, sign, ext, inside=None):
    """A section at an end of the edge: (point, tangent, points, the section past the end or None).  The next hard edge
    there sharing a face with it decides: that face's corner convex (a box's corner - nothing past the end): the
    cutter runs on past it (the cut goes through); reflex (the corner of a hole, a step - the face goes on past the
    end): it would cut a notch into the face, so the end is mitred against that next edge (two cuts meet on the line
    between them).  No next edge: square."""
    p, T, pts = sec
    dirn = T * sign                                   # (out of the edge, past its end)
    path = runs.paths[rid]
    v = path[0] if k == 0 else path[-1]
    mine = set(runs.edge_ids[rid])
    end_edge = runs.edge_ids[rid][0 if k == 0 else -1]
    # each of the edge's two faces: its next hard edge at that point, and whether the face's corner there is convex
    corners = {}
    for fn, inward, f in runs.faces[end_edge]:
        best = None
        for e, (a, b) in runs.edges.items():
            if e in mine or v not in (a, b):
                continue
            o = b if a == v else a
            d = _unit(runs.co[o] - runs.co[v])
            # (in that face's plane - a boolean's face round a hole is split into several faces)
            if not any(ff == f for _nn, _ii, ff in runs.faces[e]) and abs(float(np.dot(d, fn))) > 0.05:
                continue
            key = abs(float(np.dot(d, dirn)))
            if best is None or key < best[0]:
                best = (key, d)
        corners[f] = None if best is None else (best[1], float(np.dot(best[1], inward)) > 1e-6)
    reflex = [c for c in corners.values() if c is not None and not c[1]]
    if not reflex:                                    # (a box's corner - or a face going on past it: on through)
        return (p, T, pts, (p + dirn * ext, T, [q + dirn * ext for q in pts]))
    nxt = reflex[0][0]
    m = _unit(dirn + nxt)                             # (reflex: the mitre between the way on and the next edge)
    if np.linalg.norm(m) < 1e-9 or abs(float(np.dot(m, dirn))) < 1e-6:
        return (p, T, pts, None)
    out = []
    for q in pts:
        t = -float(np.dot(m, q - p)) / float(np.dot(m, dirn))
        out.append(q + dirn * t)
    return (p, T, out, None)


def _inside_test(ob_mesh):
    """A function: is a local point inside the part (its own mesh)?  (The nearest face's side.)"""
    from mathutils.bvhtree import BVHTree
    try:
        bvh = BVHTree.FromPolygons([tuple(v.co) for v in ob_mesh.vertices], [tuple(f.vertices) for f in ob_mesh.polygons])
    except (ValueError, RuntimeError):
        return None

    def inside(q):
        loc, nrm, _i, d = bvh.find_nearest(Vector(q))
        if loc is None:
            return False
        return float(np.dot(np.asarray(q) - np.asarray(loc), np.asarray(nrm))) < 0 and d > 1e-9
    return inside


def cutter_mesh(runs, rid, s0, s1, w, profile='CHAMFER', segments=8, name='MCH_BoolBevel_Cutter', inside=None):
    """The cutter (the part's local space) for run ``rid`` between arc lengths ``s0`` .. ``s1`` (a loop: ``s1`` may run
    past its length).  ``inside``: a test for points in the part (an end of the edge runs on past it only where there
    is nothing).  Raises BevelError for an inside edge."""
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
    if not whole_loop and not closed:                # the drawn part reaching an end of the edge:
        ext = w * 1.2
        if s0 <= 1e-6 * max(total, 1.0) + 1e-9:
            p, T, pts, past = _end(runs, rid, 0, secs[0], -1, ext, inside)
            secs[0] = (p, T, pts)
            if past is not None:
                secs.insert(0, past)
        if s1 >= total - 1e-6 * max(total, 1.0) - 1e-9:
            p, T, pts, past = _end(runs, rid, -1, secs[-1], 1, ext, inside)
            secs[-1] = (p, T, pts)
            if past is not None:
                secs.append(past)
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
    return before, len(new.polygons)


def _changed(a, b):
    if len(a.polygons) != len(b.polygons) or len(a.vertices) != len(b.vertices):
        return True
    ca = np.empty(len(a.vertices) * 3, np.float32)
    cb = np.empty(len(b.vertices) * 3, np.float32)
    a.vertices.foreach_get('co', ca)
    b.vertices.foreach_get('co', cb)
    return float(np.abs(np.sort(ca) - np.sort(cb)).max()) > 1e-6


def portions(runs, pts, reach, whole=False):
    """0.24.178 (user: "불린 베벨은 어느 정도 기존 메쉬 엣지들에 살짝 붙으면서 내가 그리면 좋을 듯"): the drawing snaps to
    the edges it passes - round a corner onto the next edge too: [(run, s0, s1)] in the order drawn (each run its
    drawn stretch); a click: the whole edge nearest."""
    if whole:
        got = portion(runs, pts[:1], reach, whole=True)
        return [got] if got is not None else []
    order, groups = [], {}
    for p in pts:
        hit = runs.nearest(p, reach)
        if hit is None:
            continue
        if hit[0] not in groups:
            groups[hit[0]] = []
            order.append(hit[0])
        groups[hit[0]].append(p)
    out = []
    for rid in order:
        if len(groups[rid]) < 2:              # (a passing touch is not drawn along)
            continue
        got = portion(runs, groups[rid], reach * 1e6)
        if got is not None and got[2] - got[1] > 1e-9:
            out.append(got)
    return out


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


# 0.24.179 (user, two screenshots: "옆에 라인 클릭해서 베벨 하면 이렇게 돼, 저 베벨이 만나야 되는 거 아니여?"): cut one
# after another, the second edge met the first one's cut faces at its end - not the part's corner - and stopped square
# there (a notch, a block left in the corner).  Now the part's mesh as it was before its first Boolean Bevel is kept
# (its "base"), with the list of the cuts on it; each click cuts the base again with all of them - every edge's ends
# read from the base's own corners, so two edges meeting at a corner meet, whichever was cut first.  Alt + click: that
# edge's cut taken off.  Changed by anything else since (a cut, a sculpt ...): the part as it is now is the new base.
STATE = 'mch_bool_bevel'               # on the part: {"base": mesh name, "sig": ..., "cuts": [...]}


def _signature(me):
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    return [n, len(me.polygons), round(float(co.sum()), 5), round(float(np.abs(co).sum()), 5)]


def state(ob):
    """The part's Boolean Bevel set ({'base', 'sig', 'cuts'}) when its mesh is still what the last cut made, else
    None."""
    import json
    raw = ob.get(STATE)
    if not raw:
        return None
    try:
        d = json.loads(raw)
    except ValueError:
        return None
    base = bpy.data.meshes.get(d.get('base', ''))
    if base is None or ob.data is None or d.get('sig') != _signature(ob.data):
        return None
    return d


def base_mesh(ob):
    d = state(ob)
    return bpy.data.meshes.get(d['base']) if d else ob.data


def runs_for(ob):
    """The runs to pick from: the base's (the edges as they were, bevelled ones too) while the set is live."""
    me = base_mesh(ob)
    return edge_runs.get_mesh(me)


def _rebuild(context, ob, base, cuts):
    """``ob``'s mesh = ``base`` with every cut of ``cuts`` taken out (each read on the base)."""
    runs = edge_runs.get_mesh(base)
    inside = _inside_test(base)
    cutters = []
    for c in cuts:
        rid = c['rid'] if c['rid'] < len(runs.paths) else None
        if rid is None or float(np.linalg.norm(runs.co[runs.paths[rid][0]] - np.array(c['p0']))) > 1e-6:
            continue                                  # (the base's runs read the same way every time; a stale one: off)
        cutters.append((c, cutter_mesh(runs, rid, c['s0'], c['s1'], c['w'], c['profile'], c['segments'],
                                       inside=inside)))
    work = base.copy()
    work.name = (ob.data.name if ob.data is not None else base.name) + ' bevelled'
    old = ob.data
    ob.data = work
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    done = 0
    try:
        for c, me in cutters:
            try:
                cut(context, ob, me)
                done += 1
            except BevelError:
                pass
    finally:
        for _c, me in cutters:
            try:
                if me.users == 0:
                    bpy.data.meshes.remove(me)
            except ReferenceError:
                pass
    return done


def perform(context, ob, pts_local, whole=False, reach=None, remove=False):
    """Boolean Bevel ``ob`` along the edge ``pts_local`` (its local space) were drawn over (``remove``: that edge's
    cut taken off).  Returns a message."""
    import json
    st = context.scene.mch_bool_bevel
    w = st.width / _mean_scale(ob)
    d = state(ob)
    if d is None:                                     # (the first cut, or the part changed since: a new base)
        base = ob.data.copy()
        base.name = 'MCH Bool Bevel Base - ' + ob.name
        base.use_fake_user = True
        old = bpy.data.meshes.get(json.loads(ob[STATE])['base']) if ob.get(STATE) else None
        if old is not None and old.users <= 1 and old is not base:
            old.use_fake_user = False
            if old.users == 0:
                bpy.data.meshes.remove(old)
        d = {'base': base.name, 'cuts': []}
    base = bpy.data.meshes[d['base']]
    runs = edge_runs.get_mesh(base)
    parts = portions(runs, pts_local, reach if reach is not None else max(w * 1.5, 1e-6), whole)
    if not parts:
        raise BevelError('No edge there - drag along one of the shown edges of the part')
    before = len(ob.data.polygons)
    cuts = list(d['cuts'])
    if remove:
        gone = {rid for rid, _a, _b in parts}
        kept = [c for c in cuts if c['rid'] not in gone]
        if len(kept) == len(cuts):
            raise BevelError('That edge has no Boolean Bevel to take off')
        cuts = kept
    else:
        for rid, s0, s1 in parts:
            cuts.append({'rid': int(rid), 'p0': [float(x) for x in runs.co[runs.paths[rid][0]]], 's0': float(s0),
                         's1': float(s1), 'w': float(w), 'profile': st.profile, 'segments': int(st.segments)})
    done = _rebuild(context, ob, base, cuts)
    if cuts and not done:
        raise BevelError('The cut took nothing off (is the edge inside the part, or the part not closed?)')
    d['cuts'] = cuts
    d['sig'] = _signature(ob.data)
    ob[STATE] = json.dumps(d)
    if remove:
        return f'Boolean Bevel taken off {len(parts)} edge{"s" if len(parts) != 1 else ""} of "{ob.name}"'
    length = sum(s1 - s0 for _r, s0, s1 in parts) * _mean_scale(ob)
    return (f'Boolean Bevel ({st.profile.title()}, {st.width:.3g} wide) on "{ob.name}": {length:.3g} along '
            f'{len(parts)} edge{"s" if len(parts) != 1 else ""}; {len(cuts)} cut{"s" if len(cuts) != 1 else ""} on '
            f'it, read from the part as it was - corners meet ({before:,} -> {len(ob.data.polygons):,} faces)')


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
        runs = runs_for(ob)
        edge_runs.draw_all(ob, runs, (0.35, 0.85, 1.0, 0.55), 1.5)
        if op is not None and op.portion:
            for rid, s0, s1 in op.portion:            # (what will be cut, snapped onto the edges)
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
                got = runs_for(ob).nearest(ob.matrix_world.inverted_safe() @ loc, _reach_px(context, ob, loc))
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
        self.reach = max(st.width * 1.5 / _mean_scale(self.ob), _reach_px(context, self.ob, loc, 24.0))
        self.runs = runs_for(self.ob)
        self.portion = []
        self.remove = bool(event.alt)
        self._update()
        _LIVE['op'] = self
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _update(self):
        self.portion = portions(self.runs, self.pts, self.reach, whole=self.moved < 6.0)

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
                msg = perform(context, self.ob, self.pts, whole=self.moved < 6.0, reach=self.reach,
                              remove=self.remove)
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
    for line in ('Drag along the edges: it snaps onto them (round corners',
                 'too) - that much is cut off (orange while you draw)',
                 'Click an edge: all of it.  Alt + click: its cut off',
                 'Edges cut one after another meet at their corners',
                 'Target (top bar, T): Auto / Selected / Active'):
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
                 ('mch.bool_bevel_draw', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),   # (off)
                 ('mch.toggle_targets', {'type': 'T', 'value': 'PRESS'}, None),      # (Auto <-> Selected)
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_PG_BoolBevel, MCH_OT_bool_bevel_hover, MCH_OT_bool_bevel_draw)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bool_bevel = PointerProperty(type=MCH_PG_BoolBevel)
    edge_runs.register()
    try:
        bpy.utils.register_tool(MCH_TOOL_bool_bevel, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_edges, (), 'WINDOW', 'POST_VIEW')


def unregister():
    edge_runs.unregister()
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
