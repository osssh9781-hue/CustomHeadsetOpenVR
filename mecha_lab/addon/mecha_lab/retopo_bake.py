"""0.24.241 Retopo + Bake (user: "리토포 하고 베이킹 하는 툴도 만들어 줄 수 있어?").
0.24.242 two steps in the same box (user: "한번에 처리하지 말구 그 탭에서 리토포 하고 베이크까지 하기만 하면 될듯"),
the progress card while they run (user: "팝업으로 진행상황 ... 게이지 차면서 퍼센트로"), and Wrap - a simple mesh
vacuum-packed onto the high (user: "적당한 사이즈의 메쉬로 마치 베큠하듯이 메쉬에 붙여버릴 수는 없나 - 그렇게 리토포").

1. Retopo   select the detailed mesh (the high): a low-poly copy ``<name>_Low`` of about ``Faces`` faces, made by
            Quad     our quad remesh engine (QuadriFlow when it is not there) - edge flow follows the shape;
            Wrap     a box of even quads a little bigger than the high (its sides divided by the high's size) is
                     shrunk onto it like a vacuum bag: every round each point is pulled to the nearest surface and
                     the grid is relaxed so the quads stay even; the last rounds put it on the surface exactly.
                     Gaps (between legs, under arms) are bridged like a bag would - it is for heads, torsos,
                     armour pieces, rocks: one closed blob.
            With the low selected: made again from its high (new Faces / method).
2. Bake     the high's Normal / AO (/ Color) onto the low (new UVs on a fresh low), the maps put on it.
The high is hidden, never changed.
"""
import math
import time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, IntProperty

HIGH_KEY = 'mch_rb_high'        # on the low: the name of its high
PARTS_KEY = 'mch_rb_parts'      # 0.24.252 on a joined high and its low: the names of the meshes it was joined from


def high_of(low):
    if low is None or low.type != 'MESH':
        return None
    h = bpy.data.objects.get(low.get(HIGH_KEY, ''))
    return h if h is not None and h.type == 'MESH' and h is not low else None


def low_of(high):
    if high is None:
        return None
    return next((o for o in bpy.data.objects if o.type == 'MESH' and o.get(HIGH_KEY) == high.name), None)


def parts_of(ob):
    """0.24.252 the meshes a joined high / its low was made from (those still there), or []."""
    import json
    try:
        names = json.loads(ob.get(PARTS_KEY, '[]')) if ob is not None else []
    except (TypeError, ValueError):
        names = []
    return [o for o in (bpy.data.objects.get(n) for n in names) if o is not None and o.type == 'MESH']


def joined_of(part):
    """The joined high ``part`` was made into (As One), or None."""
    if part is None:
        return None
    return next((o for o in bpy.data.objects if o.type == 'MESH' and o is not part and part.name in
                 [p.name for p in parts_of(o)] and low_of(o) is not None and o.get(PARTS_KEY)), None)


def pair(ob):
    """(high, low or None) for the selected object (a part of an As One retopo: its joined high and their low)."""
    h = high_of(ob)
    if h is not None:
        return h, ob
    lo = low_of(ob)
    if lo is None:
        j = joined_of(ob)
        if j is not None:
            return j, low_of(j)
    return ob, lo


# --- Wrap (vacuum) -----------------------------------------------------------------------------------------------------

def _box_grid(lo, hi, faces):
    """A closed box of quads over lo..hi, its sides divided by size so the quads are about square.  (V, F)."""
    d = np.maximum(hi - lo, 1e-6)
    area = 2 * (d[0] * d[1] + d[1] * d[2] + d[0] * d[2])
    q = math.sqrt(area / max(6, faces))
    n = [max(1, int(round(x / q))) for x in d]
    verts, index, F = [], {}, []

    def vid(i, j, k):
        key = (i, j, k)
        if key not in index:
            index[key] = len(verts)
            verts.append(lo + d * np.array([i / n[0], j / n[1], k / n[2]]))
        return index[key]
    for axis in range(3):
        u, v = [a for a in range(3) if a != axis]
        for side in (0, n[axis]):
            for a in range(n[u]):
                for b in range(n[v]):
                    c = []
                    for da, db in ((0, 0), (1, 0), (1, 1), (0, 1)):
                        p = [0, 0, 0]
                        p[axis], p[u], p[v] = side, a + da, b + db
                        c.append(vid(*p))
                    flip = (side == 0) ^ (axis == 1)
                    F.append(c[::-1] if flip else c)
    return np.array(verts), F


def wrap_steps(context, high, faces, rounds=48):
    """Generator: the vacuum-packed low's mesh (object space of ``high``); yields (fraction, what)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    ev = high.evaluated_get(dg)
    hm = ev.to_mesh()
    try:
        co = np.empty(len(hm.vertices) * 3)
        hm.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        hm.calc_loop_triangles()
        tri = np.empty(len(hm.loop_triangles) * 3, np.int64)
        hm.loop_triangles.foreach_get('vertices', tri)
        bvh = BVHTree.FromPolygons([tuple(p) for p in co], tri.reshape(-1, 3).tolist())
    finally:
        ev.to_mesh_clear()
    lo, hi = co.min(0), co.max(0)
    pad = (hi - lo) * 0.08 + 1e-4
    V, F = _box_grid(lo - pad, hi + pad, faces)
    E = set()
    for f in F:
        for i in range(4):
            a, b = f[i], f[(i + 1) % 4]
            E.add((min(a, b), max(a, b)))
    E = np.array(sorted(E))
    deg = np.bincount(E.ravel(), minlength=len(V)).astype(np.float64)
    yield (0.03, f'Wrap: a box of {len(F):,} quads')

    def nearest(P):
        out = np.empty_like(P)
        for i, p in enumerate(P):
            hit = bvh.find_nearest(Vector(p))
            out[i] = hit[0] if hit[0] is not None else p
        return out

    def relax(P, lam):
        acc = np.zeros_like(P)
        np.add.at(acc, E[:, 0], P[E[:, 1]])
        np.add.at(acc, E[:, 1], P[E[:, 0]])
        avg = acc / np.maximum(deg, 1)[:, None]
        return P + lam * (avg - P)
    P = V.copy()
    for r in range(rounds):
        t = r / max(1, rounds - 1)
        pull = 0.25 + 0.75 * t                       # (gently first: the grid settles round the shape)
        P = P + pull * (nearest(P) - P)
        P = relax(P, 0.5 if t < 0.85 else 0.3)
        if r % 3 == 2:
            yield (0.05 + 0.9 * t, f'Wrap: vacuum round {r + 1} / {rounds}')
    for _k in range(3):                              # (on the surface, still even)
        P = nearest(relax(P, 0.25))
    me = bpy.data.meshes.new(high.name + '_Low')
    me.from_pydata([tuple(p) for p in P], [], F)
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])        # (outward)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return me


# --- making the low --------------------------------------------------------------------------------------------------

def joined_high(context, parts, faces, method='QUAD'):
    """0.24.252 (user: "두세 개 선택해서 한 덩어리로 리토포 → 하나의 메쉬로 베이크") the selected meshes as one hidden
    mesh (world space): for Quad their union (a voxel remesh a third of a quad fine - the walls inside where they
    overlap gone, so the quads run over the whole as one skin); for Wrap simply joined (the wrap takes the outside).
    Made again over the old one when the same meshes are retopo'd again.  Returns the object."""
    import json
    import bmesh
    dg = context.evaluated_depsgraph_get()
    bm_ = bmesh.new()
    for o in parts:
        me_ = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
        me_.transform(o.matrix_world)
        bm_.from_mesh(me_)
        bpy.data.meshes.remove(me_)
    names = sorted(p.name for p in parts)
    name = parts[0].name + '_Joined'
    ob = next((o for o in bpy.data.objects if o.type == 'MESH' and o.get(PARTS_KEY) and
               sorted(p.name for p in parts_of(o)) == names and high_of(o) is None), None)
    me = bpy.data.meshes.new(name)
    bm_.to_mesh(me)
    bm_.free()
    if method != 'WRAP' and len(parts) > 1:
        area = sum(p.area for p in me.polygons)
        quad = math.sqrt(max(area, 1e-12) / max(4, int(faces)))
        tmp = bpy.data.objects.new('_mch_join_tmp', me)
        context.scene.collection.objects.link(tmp)
        try:
            m = tmp.modifiers.new('V', 'REMESH')
            m.mode = 'VOXEL'
            m.voxel_size = max(quad / 3.0, 1e-6)
            m.use_smooth_shade = True
            dg = context.evaluated_depsgraph_get()
            me2 = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
        finally:
            bpy.data.objects.remove(tmp)
        if len(me2.polygons):
            bpy.data.meshes.remove(me)
            me = me2
            me.name = name
        else:
            bpy.data.meshes.remove(me2)
    for mat in parts[0].data.materials:
        me.materials.append(mat)
    if ob is None:
        ob = bpy.data.objects.new(name, me)
        for coll in parts[0].users_collection:
            coll.objects.link(ob)
        if not ob.users_collection:
            context.scene.collection.objects.link(ob)
    else:
        old = ob.data
        ob.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
    ob.matrix_world.identity()
    ob[PARTS_KEY] = json.dumps(names)
    ob.hide_render = True
    ob.display_type = 'WIRE'
    return ob


def make_one_steps(context, parts, faces, method='QUAD'):
    """Generator: one low for all of ``parts`` (As One).  Returns (low, note)."""
    yield (0.01, f'Joining {len(parts)} meshes into one')
    j = joined_high(context, parts, faces, method)
    lo = low_of(j)
    low, note = yield from make_low_steps(context, j, faces, method, lo)
    low[PARTS_KEY] = j[PARTS_KEY]
    j.hide_set(True)
    for p in parts:
        p.hide_set(True)
    return low, note


def make_low_steps(context, high, faces, method='QUAD', low=None):
    """Generator: the low for ``high`` (new, or ``low``'s mesh replaced).  Returns (low, note)."""
    yield (0.02, 'Reading the high')
    note = ''
    if method == 'WRAP':
        me = yield from wrap_steps(context, high, faces)
    else:
        dg = context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(high.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
        if len(me.polygons) == 0:
            bpy.data.meshes.remove(me)
            raise RuntimeError(f'{high.name} has no faces')
        for lay in list(me.uv_layers):               # (the remesh makes new faces: old UVs do not fit)
            me.uv_layers.remove(lay)
        yield (0.1, f'Quad remesh to about {int(faces):,} faces (one step - please wait)')
    me.name = high.name + '_Low'
    if low is None:
        low = bpy.data.objects.new(high.name + '_Low', me)
        for coll in high.users_collection:
            coll.objects.link(low)
        if not low.users_collection:
            context.scene.collection.objects.link(low)
    else:
        old = low.data
        low.data = me
        if old.users == 0:
            bpy.data.meshes.remove(old)
        for lay in list(low.data.uv_layers):
            low.data.uv_layers.remove(lay)
    low.matrix_world = high.matrix_world.copy()
    low[HIGH_KEY] = high.name
    if method != 'WRAP':
        before = len(me.polygons)
        try:
            from . import quad_field as qf
            engine = qf.available()
        except ImportError:
            engine = False
        if engine:
            # 0.24.248 (user: "고르지 않은 면을 손봐 줘") on a rough sculpt every 30-degree crease was kept as an edge the
            # quads had to follow - 60 % quads, edges 4x apart; without (Hard Edges off) 95 % quads, even (1.5x)
            hard = bool(getattr(context.scene, 'mch_rb_hard', False))
            note = qf.remesh_object(low, max(4, int(faces)), all_quads=False, crease_deg=30.0 if hard else 180.0) or ''
        if not engine or len(low.data.polygons) == before:
            from . import quad_remesh as qr         # (old QuadriFlow way, in place)
            st = context.scene.mch_quadremesh
            keep = st.faces
            st.faces = max(4, int(faces))
            try:
                me2, _kept, _miss, note2 = qr.build_mesh(context, low, st)
            except RuntimeError as ex:
                raise RuntimeError(f'Retopo failed: {ex}') from None
            finally:
                st.faces = keep
            old = low.data
            low.data = me2
            me2.name = high.name + '_Low'
            if old.users == 0:
                bpy.data.meshes.remove(old)
            note = note2 or note
    yield (0.97, 'Finishing')
    note2 = tidy_low(context, high, low)
    if note2:
        note = (note + ' | ' if note else '') + note2
    if not low.data.materials:
        for mat in high.data.materials:
            low.data.materials.append(mat)
    for p in low.data.polygons:
        p.use_smooth = True
    low.show_wire = low.show_all_edges = True
    high.hide_set(True)
    for o in list(context.selected_objects):
        o.select_set(False)
    low.hide_set(False)
    low.select_set(True)
    context.view_layer.objects.active = low
    return low, note


def _boundary_loops(bm_):
    edges = [e for e in bm_.edges if e.is_boundary]
    seen, loops = set(), []
    for e in edges:
        if e.index in seen:
            continue
        loop, stack = [], [e]
        while stack:
            x = stack.pop()
            if x.index in seen:
                continue
            seen.add(x.index)
            loop.append(x)
            for v in x.verts:
                stack.extend(y for y in v.link_edges if y.is_boundary and y.index not in seen)
        loops.append(loop)
    return loops


def tidy_low(context, high, low):
    """0.24.243 (user: "리토포 툴이 이렇게 빵꾸가 나" - a rough scanned rock) holes the remesh left in the low are
    closed, and every face is turned to point out.  Returns a note or ''.
    0.24.251 (user's sculpt "002.fbx": 47 pin-holes in the high, a long zig-zag crack in the low): a hole of the low
    is kept open only when it runs along the high's own open border (measured, not "the high has any hole"); a
    crack - its two sides a quad apart - is zipped (its points welded) before the rest is filled.  Sizes in the
    low's own units (an FBX at scale 0.01 skipped every hole before)."""
    import bmesh
    from mathutils.kdtree import KDTree
    dg = context.evaluated_depsgraph_get()
    hm = high.evaluated_get(dg).to_mesh()
    border = None
    try:
        hb = bmesh.new()
        hb.from_mesh(hm)
        M = high.matrix_world
        pts = [M @ ((e.verts[0].co + e.verts[1].co) * 0.5) for e in hb.edges if e.is_boundary]
        high_open = bool(pts)
        if pts:
            border = KDTree(len(pts))
            for i, p_ in enumerate(pts):
                border.insert(p_, i)
            border.balance()
        hb.free()
    finally:
        high.evaluated_get(dg).to_mesh_clear()
    fins = 0
    bm_ = bmesh.new()
    bm_.from_mesh(low.data)
    multi = sum(1 for e in bm_.edges if len(e.link_faces) > 2)
    bm_.free()
    if multi:                     # 0.24.250 (user's thin extracted plate: edges with 3+ faces where a wall pinched)
        from . import mesh_fix
        mesh_fix.fix_mesh(low.data, fill='CRACKS' if high_open else 'SMALL')
        fins = multi
    bm_ = bmesh.new()
    bm_.from_mesh(low.data)
    bm_.edges.ensure_lookup_table()
    Lw = low.matrix_world
    lens = sorted(e.calc_length() for e in bm_.edges)
    quad = lens[len(lens) // 2] if lens else 0.0                      # (a quad's side, the low's own units)
    wq = quad * max(low.matrix_world.to_scale())                        # (the same in world units)

    def own_border(loop):
        if border is None:
            return False
        vs = {v for e in loop for v in e.verts}
        near = sum(1 for v in vs if border.find(Lw @ v.co)[2] <= 2.0 * wq)
        return near >= 0.6 * len(vs)
    # cracks zipped: the points of the holes that are not the high's border, welded across a narrow gap
    zipped = 0
    crack_vs = [v for loop in _boundary_loops(bm_) if not own_border(loop) for e in loop for v in e.verts]
    if crack_vs and quad > 0:
        tm = bmesh.ops.find_doubles(bm_, verts=list(set(crack_vs)), dist=0.6 * quad)['targetmap']
        tm = {a: b for a, b in tm.items() if not any(b in f.verts for f in a.link_faces)}   # (not across one face)
        if tm:
            bmesh.ops.weld_verts(bm_, targetmap=tm)
            zipped = len(tm)
    filled = 0
    for loop in _boundary_loops(bm_):
        if own_border(loop):
            continue
        res = bmesh.ops.holes_fill(bm_, edges=loop, sides=0)
        new = res.get('faces', [])
        if new:
            bmesh.ops.triangulate(bm_, faces=new, quad_method='BEAUTY', ngon_method='BEAUTY')
            filled += 1
    bmesh.ops.recalc_face_normals(bm_, faces=bm_.faces[:])
    bm_.to_mesh(low.data)
    bm_.free()
    low.data.update()
    if zipped:                    # (a weld can leave a 3+-face edge or a pinch: mended as above)
        from . import mesh_fix
        mesh_fix.fix_mesh(low.data, fill='CRACKS' if high_open else 'SMALL')
    notes = (([f'{filled} hole(s) closed'] if filled else []) + ([f'crack zipped ({zipped} points)'] if zipped else [])
             + ([f'{fins} pinched edge(s) mended'] if fins else []))
    return ', '.join(notes)


def deviation(context, high, low):
    """How far the low is off the high (world units, 99th percentile of its points).  ``high`` may be a list
    (0.24.253: each point measured to the nearest of them)."""
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    highs = list(high) if isinstance(high, (list, tuple)) else [high]
    trees = [(h.matrix_world.copy(), h.matrix_world.inverted(), BVHTree.FromObject(h.evaluated_get(dg), dg))
             for h in highs]
    pts = [low.matrix_world @ v.co for v in low.data.vertices]
    if len(pts) > 6000:
        pts = pts[:: len(pts) // 6000 + 1]
    d = []
    for p in pts:
        best = None
        for M, Mi, bvh in trees:
            q = bvh.find_nearest(Mi @ p)
            if q[0] is not None:
                dist = ((M @ q[0]) - p).length
                best = dist if best is None else min(best, dist)
        if best is not None:
            d.append(best)
    return float(np.percentile(d, 99)) if d else 0.0


def bake_steps(context, high, low):
    from . import bake_maps as bm
    st = bm.settings(context)
    if st is None:
        raise RuntimeError('Bake settings are missing')
    highs = parts_of(high) or parts_of(low) or [high]  # 0.24.252 As One / 0.24.253 own low: from all the meshes
    keep = bm._Keep(context, [low] + highs)
    new_uv = st.new_uv
    ray = st.ray
    st.new_uv = not low.data.uv_layers
    # 0.24.243 (a rough rock baked black: the low lay farther off the high than the rays reached) the rays reach
    # past the farthest the low is off the high
    need = 100.0 * 1.5 * deviation(context, highs if len(highs) > 1 else high, low) / max(bm.size_of(low), 1e-9)
    if need > st.ray:
        st.ray = min(20.0, need)
    try:
        info = yield from bm.bake_pair_steps(context, low, highs, st, keep_state=keep)
    finally:
        st.new_uv = new_uv
        st.ray = ray
        keep.restore(context)
    if st.show:
        for h_ in set([high] + highs):
            h_.hide_set(True)
            h_.select_set(False)
    low.hide_set(False)
    for o in list(context.selected_objects):
        o.select_set(False)
    low.select_set(True)
    context.view_layer.objects.active = low
    yield (1.0, 'Done')
    return info


# --- operators -------------------------------------------------------------------------------------------------------

def selected_pairs(context):
    """0.24.243 (user: "오브젝트 여러 개는 한 번에 선택해서 리토포") every selected mesh as (high, low or None), once."""
    obs = [o for o in context.selected_objects if o.type == 'MESH']
    act = context.active_object
    if act is not None and act.type == 'MESH' and act not in obs:
        obs.append(act)
    out, seen = [], set()
    for o in obs:
        h, lo = pair(o)
        if h.name not in seen:
            seen.add(h.name)
            out.append((h, lo))
    return out


def own_pair(context):
    """0.24.251 (user: "리토포 해 온 메쉬를 선택해서 베이크하는 것도") the user's own low (made elsewhere: ZBrush,
    another remesher, ...) and its high(s) selected together: (main high, low, [highs]) or None.
    Two meshes: the one with fewer faces is the low.  0.24.253 (user: "다른 곳에서 리메쉬한 한 덩어리로 하이폴 여러
    덩어리를 베이크") three or more: the low is the one that wraps all the others (they lie inside its box) - all
    the others are its highs, baked onto it in one go.  None when any of them is already a
    Retopo low / high, or (As One, two meshes) when both are meant as highs."""
    obs = [o for o in context.selected_objects if o.type == 'MESH']
    act = context.active_object
    if act is not None and act.type == 'MESH' and act not in obs:
        obs.append(act)
    if len(obs) < 2 or any(high_of(o) is not None or low_of(o) is not None or o.get(PARTS_KEY) for o in obs):
        return None
    obs.sort(key=lambda o: len(o.data.polygons))
    if len(obs) == 2:
        low, highs = obs[0], obs[1:]
        if getattr(context.scene, 'mch_rb_join', 'EACH') == 'ONE' or len(low.data.polygons) == len(highs[0].data.polygons):
            return None
    else:
        # three or more: the low is the one mesh that wraps all the others (their boxes inside its box) - by
        # place, not by face count (a hard-surface high can have fewer faces than the remeshed low)
        from mathutils import Vector

        def box(o):
            P = [o.matrix_world @ Vector(c) for c in o.bound_box]
            return (Vector([min(p[i] for p in P) for i in range(3)]), Vector([max(p[i] for p in P) for i in range(3)]))
        boxes = {o.name: box(o) for o in obs}

        def wraps(c):
            lo_, hi_ = boxes[c.name]
            tol = 0.05 * max(hi_ - lo_)
            return all(all(boxes[o.name][0][i] >= lo_[i] - tol and boxes[o.name][1][i] <= hi_[i] + tol for i in range(3))
                       for o in obs if o is not c)
        cands = [o for o in obs if wraps(o)]
        if not cands:
            return None
        low = cands[0]                               # (several wrap all - e.g. one big part: the fewest faces)
        highs = [o for o in obs if o is not low]
    highs.sort(key=lambda o: -len(o.data.polygons))
    return highs[0], low, highs


def link_own(context):
    """The selected own low tied to its high(s) (so Bake, Bake again and Retopo Again know them).  Or None."""
    import json
    pr = own_pair(context)
    if pr is not None:
        main, low, highs = pr
        low[HIGH_KEY] = main.name
        if len(highs) > 1:
            low[PARTS_KEY] = json.dumps(sorted(h.name for h in highs))
    return pr


def selected_parts(context):
    """0.24.252 As One: the selected meshes as the parts to join (a joined low / high selected: its parts)."""
    obs = [o for o in context.selected_objects if o.type == 'MESH']
    act = context.active_object
    if act is not None and act.type == 'MESH' and act not in obs:
        obs.append(act)
    out = []
    for o in obs:
        h = high_of(o)
        for p_ in (parts_of(h) if h is not None else []) or parts_of(o) or [o]:
            if p_ not in out:
                out.append(p_)
    return out


def _many(items, step_fn):
    """Generator: ``step_fn(item)`` (a job) for every item in turn, the fractions spread over all.  Returns
    [(item, result or the error)]."""
    out = []
    n = len(items)
    for i, it in enumerate(items):
        name = it[0].name
        try:
            gen = step_fn(it)
            while True:
                f, label = next(gen)
                yield ((i + f) / n, f'{name} ({i + 1} / {n}): {label}')
        except StopIteration as ex:
            out.append((it, ex.value))
        except RuntimeError as ex:
            out.append((it, ex))
    return out


class MCH_OT_retopo_make(bpy.types.Operator):
    """Step 1: a low-poly copy of each selected detailed mesh (Quad: remeshed; Wrap: a quad box vacuum-packed onto
    it).  A low selected: made again"""
    bl_idname = 'mch.retopo_make'
    bl_label = 'Retopo'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(selected_pairs(context))

    def invoke(self, context, event):
        return self._go(context)

    def execute(self, context):
        return self._go(context)

    def _go(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        items = selected_pairs(context)
        S = context.scene
        method, faces = S.mch_rb_method, S.mch_rb_faces
        t0 = time.time()

        def done(res):
            lows = [r[0] for _it, r in res if not isinstance(r, Exception)]
            bad = [(it[0].name, str(r)) for it, r in res if isinstance(r, Exception)]
            for o in list(context.selected_objects):
                o.select_set(False)
            for lo in lows:
                lo.hide_set(False)
                lo.select_set(True)
            if lows:
                context.view_layer.objects.active = lows[-1]
            msg = (f'Retopo ({"Wrap" if method == "WRAP" else "Quad"}): {len(lows)} low(s), '
                   f'{sum(len(lo.data.polygons) for lo in lows):,} faces, {time.time() - t0:.1f} s')
            notes = [r[1] for _it, r in res if not isinstance(r, Exception) and r[1] and not r[1].startswith('Quad Remesh:')]
            if notes:
                msg += ' | ' + '; '.join(notes[:3])
            if bad:
                msg += ' | failed: ' + '; '.join(f'{n}: {e}' for n, e in bad[:3])
            return msg
        from . import progress
        parts = selected_parts(context) if getattr(S, 'mch_rb_join', 'EACH') == 'ONE' else []
        if len(parts) > 1:                           # 0.24.252 As One: one low for all of them
            items = [(parts[0], None)]
            gen = _many(items, lambda it: make_one_steps(context, parts, faces, method))
            title = f'Retopo: {len(parts)} meshes as one'
        else:
            gen = _many(items, lambda it: make_low_steps(context, it[0], faces, method, it[1]))
            title = f'Retopo: {items[0][0].name}' if len(items) == 1 else f'Retopo: {len(items)} meshes'
        res = progress.start(context, title, gen, done)
        if res != 'RUNNING':
            self.report({'INFO'}, done(res))
        return {'FINISHED'}


class MCH_OT_retopo_bake(bpy.types.Operator):
    """Step 2: bake each selected high's maps onto its low (made by Retopo), the maps put on the low"""
    bl_idname = 'mch.retopo_bake'
    bl_label = 'Bake'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(lo is not None for _h, lo in selected_pairs(context)) or own_pair(context) is not None

    def invoke(self, context, event):
        return self._go(context)

    def execute(self, context):
        return self._go(context)

    def _go(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        link_own(context)                            # 0.24.251 the user's own low + its high
        items = [(h, lo) for h, lo in selected_pairs(context) if lo is not None]
        from . import bake_maps as bm, progress
        try:
            from . import safety_save
            safety_save.before_risky('Bake')
        except (ImportError, AttributeError, RuntimeError):
            pass

        def done(res):
            ok = [(it, r) for it, r in res if not isinstance(r, Exception)]
            bad = [(it[0].name, str(r)) for it, r in res if isinstance(r, Exception)]
            for o in list(context.selected_objects):
                o.select_set(False)
            for (h, lo), _r in ok:
                lo.hide_set(False)
                lo.select_set(True)
            if ok:
                context.view_layer.objects.active = ok[-1][0][1]
            msg = 'Bake: ' + (f'{ok[0][0][0].name} -> {ok[0][0][1].name}' if len(ok) == 1 else f'{len(ok)} lows')
            if ok:
                info = ok[-1][1]
                msg += f', {", ".join(bm.SUFFIX[k] for k in info["maps"])} {info["res"]} px'
            if bad:
                msg += ' | failed: ' + '; '.join(f'{n}: {e}' for n, e in bad[:3])
            return msg
        gen = _many(items, lambda it: bake_steps(context, it[0], it[1]))
        title = f'Bake: {items[0][0].name} -> {items[0][1].name}' if len(items) == 1 else f'Bake: {len(items)} meshes'
        res = progress.start(context, title, gen, done)
        if res != 'RUNNING':
            self.report({'INFO'}, done(res))
        return {'FINISHED'}


def draw(layout, context):
    """The two-step box (Remesh tool window, Bake Maps)."""
    from . import bake_maps as bm, panel_capture as pc
    st = bm.settings(context)
    S = context.scene
    if st is None or not hasattr(S, 'mch_rb_faces'):
        return
    ob = context.active_object
    high, low = pair(ob) if ob is not None and ob.type == 'MESH' else (None, None)
    items = selected_pairs(context)
    own = own_pair(context)
    n_low = sum(1 for _h, lo in items if lo is not None) or (1 if own is not None else 0)
    box = layout.box()
    box.label(text='RETOPO + BAKE', icon='MOD_REMESH')
    box.row(align=True).prop(S, 'mch_rb_method', expand=True)
    col = box.column(align=True)
    col.prop(S, 'mch_rb_faces')
    if S.mch_rb_method == 'QUAD' and hasattr(S, 'mch_rb_hard'):
        col.prop(S, 'mch_rb_hard', toggle=True)
    parts = selected_parts(context) if hasattr(S, 'mch_rb_join') else []
    one = len(parts) > 1 and S.mch_rb_join == 'ONE'
    if hasattr(S, 'mch_rb_join') and (len(parts) > 1 or S.mch_rb_join == 'ONE'):    # 0.24.252 each / as one
        box.row(align=True).prop(S, 'mch_rb_join', expand=True)
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    many = len(items) > 1
    r.operator('mch.retopo_make', text=(f'1  Retopo {len(parts)} as One' if one else
                                        f'1  Retopo {len(items)} Meshes' if many else
                                        '1  Retopo Again' if low is not None else '1  Retopo'), icon='MOD_REMESH')
    col = box.column(align=True)
    r = col.row(align=True)
    r.prop(st, 'res', text='')
    r.prop(st, 'normal', toggle=True)
    r.prop(st, 'ao', toggle=True)
    r.prop(st, 'color', toggle=True)
    r = col.row(align=True)                          # 0.24.243 more maps
    r.prop(st, 'rough', toggle=True)
    r.prop(st, 'metal', toggle=True)
    r.prop(st, 'curv', toggle=True)
    r.prop(st, 'height', toggle=True)
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.enabled = n_low > 0
    r.operator('mch.retopo_bake', text=f'2  Bake {n_low} Meshes' if n_low > 1 else '2  Bake', icon='RENDER_STILL')
    if one:
        box.label(text=f'{len(parts)} meshes -> one low, baked from all of them', icon='CHECKMARK')
    elif own is not None:
        box.label(text=(f'Your own low: {own[0].name} -> {own[1].name}  (2 Bake)' if len(own[2]) == 1 else
                        f'Your own low: {len(own[2])} highs -> {own[1].name}  (2 Bake)'), icon='CHECKMARK')
    elif many:
        box.label(text=f'{len(items)} meshes selected, {n_low} with a low', icon='CHECKMARK')
    elif low is not None:
        box.label(text=f'{high.name} -> {low.name}', icon='CHECKMARK')
    else:
        box.label(text='Select the detailed mesh(es) (high)', icon='INFO')
        box.label(text='Your own low: select it and its high(s), then 2 Bake', icon='INFO')


CLASSES = (MCH_OT_retopo_make, MCH_OT_retopo_bake)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rb_faces = IntProperty(
        name='Faces', default=5000, min=50, max=200000,
        description='About how many faces the low poly gets')
    bpy.types.Scene.mch_rb_hard = BoolProperty(
        name='Keep Hard Edges', default=False,
        description='Quad: the quads follow the sharp edges (hard-surface parts).  Off: even quads over the whole '
                    'shape (sculpts, creatures, rocks)')
    bpy.types.Scene.mch_rb_join = EnumProperty(
        name='Several Meshes', default='EACH',
        items=[('EACH', 'Each Its Own', 'Each selected mesh gets its own low and its own maps'),
               ('ONE', 'As One', 'The selected meshes joined into one low (their union), baked from all of them: '
                                 'one mesh, one set of maps')])
    bpy.types.Scene.mch_rb_method = EnumProperty(
        name='Method', default='QUAD',
        items=[('QUAD', 'Quad', 'Quad remesh: the edge flow follows the shape'),
               ('WRAP', 'Vacuum Wrap', 'A box of even quads vacuum-packed onto the high (heads, torsos, armour, rocks: '
                                'one closed blob; gaps are bridged)')])


def unregister():
    for a in ('mch_rb_faces', 'mch_rb_method', 'mch_rb_hard', 'mch_rb_join'):
        if hasattr(bpy.types.Scene, a):
            delattr(bpy.types.Scene, a)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
