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
from bpy.props import EnumProperty, IntProperty

HIGH_KEY = 'mch_rb_high'        # on the low: the name of its high


def high_of(low):
    if low is None or low.type != 'MESH':
        return None
    h = bpy.data.objects.get(low.get(HIGH_KEY, ''))
    return h if h is not None and h.type == 'MESH' and h is not low else None


def low_of(high):
    if high is None:
        return None
    return next((o for o in bpy.data.objects if o.type == 'MESH' and o.get(HIGH_KEY) == high.name), None)


def pair(ob):
    """(high, low or None) for the selected object."""
    h = high_of(ob)
    if h is not None:
        return h, ob
    return ob, low_of(ob)


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
            note = qf.remesh_object(low, max(4, int(faces)), all_quads=False, crease_deg=30.0) or ''
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
    closed (all of them when the high is closed; on an open high only the small ones - its own border stays), and
    every face is turned to point out.  Returns a note or ''."""
    import bmesh
    dg = context.evaluated_depsgraph_get()
    hm = high.evaluated_get(dg).to_mesh()
    try:
        hb = bmesh.new()
        hb.from_mesh(hm)
        high_open = any(e.is_boundary for e in hb.edges)
        hb.free()
    finally:
        high.evaluated_get(dg).to_mesh_clear()
    bm_ = bmesh.new()
    bm_.from_mesh(low.data)
    bm_.edges.ensure_lookup_table()
    size = max(low.dimensions) or 1.0
    filled = 0
    for loop in _boundary_loops(bm_):
        per = sum(e.calc_length() for e in loop)
        if high_open and per > 0.35 * size:
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
    return f'{filled} hole(s) closed' if filled else ''


def deviation(context, high, low):
    """How far the low is off the high (world units, 99th percentile of its points)."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    bvh = BVHTree.FromObject(high.evaluated_get(dg), dg)
    Hi = high.matrix_world.inverted()
    pts = [low.matrix_world @ v.co for v in low.data.vertices]
    if len(pts) > 6000:
        pts = pts[:: len(pts) // 6000 + 1]
    d = []
    for p in pts:
        q = bvh.find_nearest(Hi @ p)
        if q[0] is not None:
            d.append(((high.matrix_world @ q[0]) - p).length)
    return float(np.percentile(d, 99)) if d else 0.0


def bake_steps(context, high, low):
    from . import bake_maps as bm
    st = bm.settings(context)
    if st is None:
        raise RuntimeError('Bake settings are missing')
    keep = bm._Keep(context, [low, high])
    new_uv = st.new_uv
    ray = st.ray
    st.new_uv = not low.data.uv_layers
    # 0.24.243 (a rough rock baked black: the low lay farther off the high than the rays reached) the rays reach
    # past the farthest the low is off the high
    need = 100.0 * 1.5 * deviation(context, high, low) / max(bm.size_of(low), 1e-9)
    if need > st.ray:
        st.ray = min(20.0, need)
    try:
        info = yield from bm.bake_pair_steps(context, low, [high], st, keep_state=keep)
    finally:
        st.new_uv = new_uv
        st.ray = ray
        keep.restore(context)
    if st.show:
        high.hide_set(True)
        high.select_set(False)
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
        return any(lo is not None for _h, lo in selected_pairs(context))

    def invoke(self, context, event):
        return self._go(context)

    def execute(self, context):
        return self._go(context)

    def _go(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
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
    n_low = sum(1 for _h, lo in items if lo is not None)
    box = layout.box()
    box.label(text='RETOPO + BAKE', icon='MOD_REMESH')
    box.row(align=True).prop(S, 'mch_rb_method', expand=True)
    col = box.column(align=True)
    col.prop(S, 'mch_rb_faces')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    many = len(items) > 1
    r.operator('mch.retopo_make', text=(f'1  Retopo {len(items)} Meshes' if many else
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
    if many:
        box.label(text=f'{len(items)} meshes selected, {n_low} with a low', icon='CHECKMARK')
    elif low is not None:
        box.label(text=f'{high.name} -> {low.name}', icon='CHECKMARK')
    else:
        box.label(text='Select the detailed mesh(es) (high)', icon='INFO')


CLASSES = (MCH_OT_retopo_make, MCH_OT_retopo_bake)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rb_faces = IntProperty(
        name='Faces', default=5000, min=50, max=200000,
        description='About how many faces the low poly gets')
    bpy.types.Scene.mch_rb_method = EnumProperty(
        name='Method', default='QUAD',
        items=[('QUAD', 'Quad', 'Quad remesh: the edge flow follows the shape'),
               ('WRAP', 'Vacuum Wrap', 'A box of even quads vacuum-packed onto the high (heads, torsos, armour, rocks: '
                                'one closed blob; gaps are bridged)')])


def unregister():
    for a in ('mch_rb_faces', 'mch_rb_method'):
        if hasattr(bpy.types.Scene, a):
            delattr(bpy.types.Scene, a)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
