"""0.24.342 Project to Original (user: "쿼드 플로우나 리토포 하고 원본 메쉬에 프로젝트 하는 기능" -> "표면에 딱
붙이기만", "자동"): the low (Retopo's Quad / Wrap, Manual Retopo, or one made elsewhere) snapped onto its original's
surface - its face count and flow unchanged, its points on the high.

Auto direction: each point looks along its own normal, out and in, within a reach (a share of the low's size) and
takes the nearer surface it meets; where neither way meets it (or the hit is much farther than the nearest surface),
the nearest point on the surface.  Then a little evening-out: each point slides toward its neighbours' middle
ALONG the surface (no shrinking) and is put back on the surface - so points do not bunch in a crease.  Open borders
stay where they were projected; a Mirror modifier's middle line stays on the middle."""
from __future__ import annotations

import bpy
import numpy as np
from mathutils import Vector
from mathutils.bvhtree import BVHTree


def _high_tree(context, highs):
    """One BVH of all the highs as they are drawn (modifiers on), world space."""
    from .light_copies import full as lc_full
    dg = context.evaluated_depsgraph_get()
    V, F, base = [], [], 0
    for h in highs:
        ev = lc_full(h, dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            nt = len(me.loop_triangles)
            if not nt:
                continue
            co = np.empty(len(me.vertices) * 3, np.float64)
            me.vertices.foreach_get('co', co)
            M = np.array(h.matrix_world, np.float64)
            V.append(co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3])
            t = np.empty(nt * 3, np.int64)
            me.loop_triangles.foreach_get('vertices', t)
            F.append(t.reshape(-1, 3) + base)
            base += len(me.vertices)
        finally:
            ev.to_mesh_clear()
    if not V:
        raise RuntimeError('the original has no faces')
    V = np.concatenate(V)
    F = np.concatenate(F)
    return BVHTree.FromPolygons(V.tolist(), F.tolist(), all_triangles=True)


def _snap(tree, P, N, reach):
    """Each point onto the surface: along its normal (out / in, the nearer), else the nearest point."""
    out = P.copy()
    how = np.zeros(len(P), np.int8)                 # 1 ray, 2 nearest
    for i in range(len(P)):
        p = Vector(P[i])
        n = Vector(N[i])
        near = tree.find_nearest(p)
        dn = near[3] if near[0] is not None else None
        best, bd = None, None
        if n.length > 1e-9:
            for d in (n, -n):
                hit = tree.ray_cast(p, d, reach)
                if hit[0] is not None and (bd is None or hit[3] < bd):
                    best, bd = hit[0], hit[3]
        # (a ray hit far beyond the nearest surface: a thin wall's other side - the nearest point instead)
        if best is not None and (dn is None or bd <= max(dn * 3.0, reach * 0.05)):
            out[i] = best
            how[i] = 1
        elif near[0] is not None:
            out[i] = near[0]
            how[i] = 2
    return out, how


def _nearest(tree, P):
    out = P.copy()
    for i in range(len(P)):
        h = tree.find_nearest(Vector(P[i]))
        if h[0] is not None:
            out[i] = h[0]
    return out


def project(context, low, highs, relax=2, strength=0.5):
    """``low``'s points onto ``highs``' surface (in place; its face count / flow unchanged).  Returns
    {'moved': mean move, 'ray': share by ray, 'max_off': largest distance left to the surface}."""
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    me = low.data
    nv = len(me.vertices)
    if not nv:
        raise RuntimeError(f'{low.name} has no points')
    tree = _high_tree(context, highs)
    M = np.array(low.matrix_world, np.float64)
    R, T = M[:3, :3], M[:3, 3]
    Ri = np.linalg.inv(R)
    co = np.empty(nv * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    nr = np.empty(nv * 3, np.float64)
    me.vertex_normals.foreach_get('vector', nr)
    nr = nr.reshape(-1, 3)
    P = co @ R.T + T
    N = nr @ Ri                                     # (normals: the inverse transpose)
    N /= np.maximum(np.linalg.norm(N, axis=1, keepdims=True), 1e-12)
    size = float(np.linalg.norm(P.max(0) - P.min(0)))
    reach = max(size * 0.15, 1e-6)
    P0 = P.copy()
    P, how = _snap(tree, P, N, reach)
    # the mirror middle: points on the mirror plane stay on it
    mid = np.zeros(nv, bool)
    for m in low.modifiers:
        if m.type == 'MIRROR' and m.show_viewport:
            eps = max(size * 1e-4, 1e-6)
            for a in range(3):
                if m.use_axis[a]:
                    mid |= np.abs(co[:, a]) < eps
    # neighbours (edges), open borders pinned
    ne = len(me.edges)
    E = np.empty(ne * 2, np.int64)
    me.edges.foreach_get('vertices', E)
    E = E.reshape(-1, 2)
    pin = np.zeros(nv, bool)
    if len(me.polygons):
        ek = np.empty(sum(len(p.vertices) for p in me.polygons), np.int64)
        me.polygons.foreach_get('vertices', ek)
        tot = np.empty(len(me.polygons), np.int64)
        me.polygons.foreach_get('loop_total', tot)
        st = np.concatenate([[0], np.cumsum(tot)[:-1]])
        nxt = np.arange(len(ek)) + 1
        nxt[st + tot - 1] = st
        a, b = np.minimum(ek, ek[nxt]), np.maximum(ek, ek[nxt])
        key = a * nv + b
        uk, cnt = np.unique(key, return_counts=True)
        border = uk[cnt == 1]
        pin[border // nv] = True
        pin[border % nv] = True
    deg = np.bincount(E.ravel(), minlength=nv).astype(np.float64)
    for _it in range(max(0, int(relax))):
        acc = np.zeros_like(P)
        np.add.at(acc, E[:, 0], P[E[:, 1]])
        np.add.at(acc, E[:, 1], P[E[:, 0]])
        avg = acc / np.maximum(deg, 1)[:, None]
        # the normal of the surface there: from the low's own faces (rebuilt each round)
        d = avg - P
        Nn = _point_normals(me, P)
        d -= (d * Nn).sum(1, keepdims=True) * Nn          # (along the surface only - no shrinking)
        move = ~pin & (deg > 0)
        P2 = P.copy()
        P2[move] += strength * d[move]
        P2[move] = _nearest(tree, P2[move])
        P = P2
    # back to the object, the mirror middle kept on its plane
    loc = (P - T) @ Ri.T
    if mid.any():
        for m in low.modifiers:
            if m.type == 'MIRROR' and m.show_viewport:
                for a in range(3):
                    if m.use_axis[a]:
                        loc[mid & (np.abs(co[:, a]) < max(size * 1e-4, 1e-6)), a] = 0.0
    me.vertices.foreach_set('co', loc.astype(np.float64).ravel())
    me.update()
    off = np.array([tree.find_nearest(Vector(p))[3] or 0.0 for p in (loc @ R.T + T)[:: max(1, nv // 2000)]])
    return {'moved': float(np.linalg.norm(P - P0, axis=1).mean()), 'ray': float((how == 1).mean()),
            'max_off': float(off.max()) if len(off) else 0.0, 'size': size}


def _point_normals(me, P):
    """Point normals of the low's faces with the points at ``P`` (area weighted)."""
    nv = len(P)
    tot = np.empty(len(me.polygons), np.int64)
    me.polygons.foreach_get('loop_total', tot)
    vs = np.empty(int(tot.sum()), np.int64)
    me.polygons.foreach_get('vertices', vs)
    st = np.concatenate([[0], np.cumsum(tot)[:-1]])
    nxt = np.arange(len(vs)) + 1
    nxt[st + tot - 1] = st
    fid = np.repeat(np.arange(len(tot)), tot)
    cr = np.cross(P[vs], P[vs[nxt]])                     # (Newell: the face normal x 2 area)
    fn = np.zeros((len(tot), 3))
    np.add.at(fn, fid, cr)
    pn = np.zeros((nv, 3))
    np.add.at(pn, vs, fn[fid])
    return pn / np.maximum(np.linalg.norm(pn, axis=1, keepdims=True), 1e-12)


def targets(context):
    """[(low, [highs])] for the selection: Retopo pairs (a high or its low selected), else the user's own low + its
    original(s) selected together."""
    from . import retopo_bake as rb
    out = []
    for h, lo in rb.selected_pairs(context):
        if lo is not None and lo is not h:
            out.append((lo, [h]))
    if out:
        return out
    op = rb.own_pair(context)
    if op is not None:
        _h, low, highs = op
        return [(low, list(highs))]
    obs = [o for o in context.selected_objects if o.type == 'MESH']
    if len(obs) == 2:                                    # (two meshes: the one with fewer faces is the low)
        obs.sort(key=lambda o: len(o.data.polygons))
        return [(obs[0], [obs[1]])]
    return []


class MCH_OT_retopo_project(bpy.types.Operator):
    """Snap the retopo (low) onto its original's surface: each point along its normal to the nearer surface it meets
    (else the nearest point), then evened out along the surface.  Select a Retopo low or its high, or your own low +
    the original"""
    bl_idname = 'mch.retopo_project'
    bl_label = 'Project to Original'
    bl_options = {'REGISTER', 'UNDO'}

    relax: bpy.props.IntProperty(name='Even Out', default=2, min=0, max=20,
                                 description='Rounds of evening the points out along the surface after the snap '
                                 '(0: just the snap)')

    @classmethod
    def poll(cls, context):
        return bool(targets(context))

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        tg = targets(context)
        if not tg:
            self.report({'WARNING'}, 'Select a Retopo low (or its high), or your low + the original')
            return {'CANCELLED'}
        msgs = []
        for low, highs in tg:
            try:
                r = project(context, low, highs, relax=self.relax)
            except RuntimeError as ex:
                msgs.append(f'{low.name}: {ex}')
                continue
            msgs.append(f'{low.name} -> {", ".join(h.name for h in highs)} (moved {r["moved"]:.4g}, '
                        f'{r["ray"] * 100:.0f}% along its normal)')
        self.report({'INFO'}, 'Project: ' + '; '.join(msgs))
        return {'FINISHED'}


CLASSES = (MCH_OT_retopo_project,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
