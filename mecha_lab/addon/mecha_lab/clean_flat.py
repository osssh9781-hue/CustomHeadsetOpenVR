"""0.24.284 Clean (Planar) (user: "지브러시에서 덩어리 잡아 오면 스컬핑한 상태 - 옆의 평평한 면이 있으면 그걸로 밀어서
정리", "클린이라고 새로 만들자", then on the automatic try: "리메시랑 큰 차이 없잖아 - 그 부근의 평평한 면으로 그냥 밀어
버렸으면, 지브러시의 플래너처럼") A lasso tool like ZBrush's Planar brush: draw an outline over a part - the surface
inside it (the side you see) is pushed onto one flat plane.

* The plane: fitted through the points inside the outline (Fit), or facing you through them (Facing View).
* Both: every point onto the plane; Cut: only what stands above it comes down (like Planar Cut); Fill: only the
  hollows come up.
* Soft Edge: near the outline the push fades out, so the flat runs into the rest without a step.
* Only the surface you see under the outline (facing you, the front layer): the back of the part is never touched.
The mesh keeps its points and faces (no remesh); one undo step.
"""
from __future__ import annotations

import numpy as np

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Vector


class MCH_PG_Clean(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Push', default='BOTH', items=(
        ('BOTH', 'Both', 'Every point inside the outline onto the plane'),
        ('CUT', 'Cut', 'Only what stands above the plane comes down (Planar Cut)'),
        ('FILL', 'Fill', 'Only the hollows come up to the plane')))
    plane: EnumProperty(name='Plane', default='FIT', items=(
        ('FIT', 'Fit', 'The plane that fits the surface inside the outline best'),
        ('VIEW', 'Facing View', 'A plane facing you, through the surface inside the outline')))
    height: FloatProperty(name='Height', default=0.0, min=-50.0, max=50.0, subtype='PERCENTAGE', precision=1,
                          description='Clean: the plane moved out (+) or in (-), in % of the outline size '
                                      '(Cut with a lower plane takes more off)')
    soft: FloatProperty(name='Soft Edge', default=10.0, min=0.0, max=50.0, subtype='PERCENTAGE', precision=0,
                        description='Clean: near the outline the push fades out over this share of its size '
                                    '(0: a hard step at the outline)')
    strength: FloatProperty(name='Strength', default=1.0, min=0.0, max=1.0, subtype='FACTOR',
                            description='Clean: how far the points go onto the plane (1: all the way)')
    # 0.24.285 (user: "좀 더 더 밀어도 돼, 아직도 너무 촘촘해")
    merge: BoolProperty(name='Merge Flat', default=True,
                        description='Clean: the flattened area becomes a few big faces instead of the sculpt\'s many '
                                    'small ones (the shape does not change)')


def screen_xy(projector, P):
    """Screen positions (n, 2) of world points ``P`` (n, 3), and which are in front of the eye."""
    if hasattr(projector, 'rv3d'):
        M = np.array(projector.rv3d.perspective_matrix, float)
        h = np.c_[P, np.ones(len(P))] @ M.T
        w = h[:, 3]
        ok = w > 1e-9
        w = np.where(ok, w, 1.0)
        rg = projector.region
        x = (h[:, 0] / w + 1.0) * 0.5 * rg.width
        y = (h[:, 1] / w + 1.0) * 0.5 * rg.height
        return np.stack([x, y], 1), ok
    rot = np.array(projector.rot, float)
    right, up = rot[:, 0], rot[:, 1]
    d = P - np.array(projector.center, float)
    x = projector.size[0] / 2 + (d @ right) * projector.ppu
    y = projector.size[1] / 2 + (d @ up) * projector.ppu
    return np.stack([x, y], 1), np.ones(len(P), bool)


def inside_loop(Q, loop):
    """Which of the points ``Q`` (n, 2) are inside the closed outline ``loop`` [(x, y)] (even-odd)."""
    L = np.asarray(loop, float)
    inside = np.zeros(len(Q), bool)
    x, y = Q[:, 0], Q[:, 1]
    for (x1, y1), (x2, y2) in zip(L, np.roll(L, -1, 0)):
        if y1 == y2:
            continue
        c = (y1 > y) != (y2 > y)
        xi = x1 + (y - y1) * (x2 - x1) / (y2 - y1)
        inside ^= c & (x < xi)
    return inside


def edge_distance(Q, loop):
    """Each point's screen distance to the outline."""
    L = np.asarray(loop, float)
    best = np.full(len(Q), np.inf)
    for a, b in zip(L, np.roll(L, -1, 0)):
        ab = b - a
        t = np.clip(((Q - a) @ ab) / max(float(ab @ ab), 1e-12), 0.0, 1.0)
        best = np.minimum(best, np.linalg.norm(Q - (a + t[:, None] * ab), axis=1))
    return best


def _front(ob, W, sel, projector, Q):
    """Of the points ``sel``, the ones on the surface you see (not behind another layer of the same part): the depth
    the view ray meets the part at, sampled on a grid over them, against each point's own depth."""
    from mathutils.bvhtree import BVHTree
    dg = bpy.context.evaluated_depsgraph_get()
    try:
        bvh = BVHTree.FromObject(ob, dg)
    except (RuntimeError, ValueError):
        return sel
    idx = np.nonzero(sel)[0]
    vd = np.array(projector.view_dir, float)
    eye = np.array(getattr(projector, 'eye', W[idx].mean(0) - vd * 1000.0), float)
    depth = (W[idx] - eye) @ vd
    span = float(np.linalg.norm(W[idx].max(0) - W[idx].min(0))) or 1.0
    band = 0.03 * span
    q = Q[idx]
    lo, hi = q.min(0), q.max(0)
    G = 48
    cell = np.maximum((hi - lo) / G, 1e-9)
    gi = np.clip(((q - lo) / cell).astype(int), 0, G - 1)
    keys = gi[:, 0] * G + gi[:, 1]
    mw = ob.matrix_world
    inv = mw.inverted()
    hit = {}
    for key in np.unique(keys).tolist():
        xy = (lo[0] + (key // G + 0.5) * cell[0], lo[1] + (key % G + 0.5) * cell[1])
        o, d = projector.ray(xy)
        loc, _n, _i, _dist = bvh.ray_cast(inv @ Vector(o), (inv.to_3x3() @ Vector(d)).normalized())
        hit[key] = np.nan if loc is None else float((np.array(mw @ loc) - eye) @ vd)
    hd = np.array([hit[k] for k in keys.tolist()])
    keep = np.isnan(hd) | (depth <= hd + band)
    out = np.zeros_like(sel)
    out[idx[keep]] = True
    return out


def planar(ob, loop, projector, st):
    """Push the surface of ``ob`` inside the screen outline ``loop`` onto one plane.  Returns how many points moved."""
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    no = np.empty(n * 3)
    me.vertices.foreach_get('normal', no)
    no = no.reshape(-1, 3)
    M = np.array(ob.matrix_world, float)
    W = co @ M[:3, :3].T + M[:3, 3]
    Nw = no @ np.linalg.inv(M[:3, :3])
    Nw /= np.maximum(np.linalg.norm(Nw, axis=1), 1e-30)[:, None]
    Q, front_of_eye = screen_xy(projector, W)
    vd = np.array(projector.view_dir, float)
    sel = front_of_eye & inside_loop(Q, loop) & ((Nw @ vd) < -0.25)       # (facing you: walls seen edge-on stay)
    if sel.sum() < 3:
        return 0
    sel = _front(ob, W, sel, projector, Q)
    idx = np.nonzero(sel)[0]
    if len(idx) < 3:
        return 0
    P = W[idx]
    c = P.mean(0)
    if st.plane == 'VIEW':
        nrm = -vd
    else:
        u = np.linalg.svd(P - c, full_matrices=False)[2][-1]
        nrm = u if u @ vd < 0 else -u
    L = np.asarray(loop, float)
    rad_px = 0.5 * float(np.linalg.norm(L.max(0) - L.min(0))) or 1.0
    size = float(np.linalg.norm(P.max(0) - P.min(0))) or 1.0
    c = c + nrm * (st.height * 0.01 * size)
    off = (P - c) @ nrm                      # + above the plane (toward you)
    if st.mode == 'CUT':
        off = np.maximum(off, 0.0)
    elif st.mode == 'FILL':
        off = np.minimum(off, 0.0)
    w = np.full(len(idx), float(st.strength))
    if st.soft > 0.0:
        t = np.clip(edge_distance(Q[idx], loop) / (st.soft * 0.01 * rad_px), 0.0, 1.0)
        w *= t * t * (3.0 - 2.0 * t)
    Wn = W.copy()
    Wn[idx] = P - nrm[None, :] * (off * w)[:, None]
    moved = int((np.abs(off * w) > 1e-9).sum())
    Mi = np.linalg.inv(M)
    co2 = Wn @ Mi[:3, :3].T + Mi[:3, 3]
    me.vertices.foreach_set('co', co2.astype(np.float32).ravel())
    me.update()
    if getattr(st, 'merge', False) and st.strength >= 0.999:
        flat = np.zeros(n, bool)
        flat[idx[(w >= 0.999) | (np.abs(off) < 1e-9 * size)]] = True
        _merge_flat(ob, flat)
    return moved


def _merge_flat(ob, flat):
    """0.24.285 the flattened area made of a few big triangles: everything else (and the flat's own rim) locked, the
    points inside the flat collapsed away (they lie on one plane: the shape does not change)."""
    from . import fast_decimate as fd
    me = ob.data
    me.calc_loop_triangles()
    nt = len(me.loop_triangles)
    T = np.empty(nt * 3, np.int64)
    me.loop_triangles.foreach_get('vertices', T)
    T = T.reshape(-1, 3)
    on = flat[T].all(1)                       # triangles lying on the flat
    if on.sum() < 8 or not fd.available():
        return
    rim = np.zeros(len(flat), bool)
    rim[T[~on].ravel()] = True                # flat points touching the rest: kept (the shape round it stays)
    locked = ~flat | rim
    target = int((~on).sum()) + max(8, int(on.sum() * 0.01))
    fd.decimate_object(ob, 100.0 * target / nt, quads=True, keep_borders=True, keep_edges=False, locked=locked)


def perform(context, loops, projector):
    """The outline(s) drawn: the part(s) under them flattened."""
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger outline')
    st = context.scene.mch_clean
    obs = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
    if not obs:
        from . import base_mesh
        outer = max(groups, key=lambda g: abs(cg.signed_area(g[0])))[0]
        _q, found = base_mesh.anchor_hit(context, projector, outer)
        if found is None:
            raise cg.CutError('Draw the outline over a part')
        obs = [bpy.data.objects.get(found[2].name) or found[2]]
    total = 0
    nf0 = sum(len(o.data.polygons) for o in obs)
    for ob in obs:
        if ob.data.shape_keys is not None or any(m.type == 'MULTIRES' for m in ob.modifiers):
            continue
        for outer, _holes in groups:
            total += planar(ob, outer, projector, st)
    if not total:
        raise cg.CutError('Clean: nothing to flatten under the outline (draw it over the part, on the side you see)')
    nf = sum(len(o.data.polygons) for o in obs)
    return f'Clean: {total:,} points pushed onto the plane ({nf0:,} > {nf:,} faces)' if nf != nf0 else \
        f'Clean: {total:,} points pushed onto the plane'


def draw(layout, context):
    st = context.scene.mch_clean
    col = layout.column(align=True)
    col.label(text='Clean (Planar): draw over the area to flatten')
    col.row(align=True).prop(st, 'mode', expand=True)
    col.row(align=True).prop(st, 'plane', expand=True)
    col.prop(st, 'height')
    col.prop(st, 'soft')
    col.prop(st, 'strength')
    col.prop(st, 'merge')


CLASSES = (MCH_PG_Clean,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_clean = bpy.props.PointerProperty(type=MCH_PG_Clean)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_clean'):
        del bpy.types.Scene.mch_clean
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
