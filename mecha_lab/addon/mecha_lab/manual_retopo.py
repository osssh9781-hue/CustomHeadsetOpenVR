"""0.24.332 Manual Retopo (user: "자동이 아니라 그냥 리토폴로지 툴도 하나 만들자 ... 내가 메쉬 위에 크게 격자무늬로 리토포를
다 그릴게 그럼 그걸 너가 생성해 주면 돼", "하이폴을 다 선택하고 수동 리토포 툴을 누르면 새로운 창으로 가서 한 덩어리로
합쳐지고 ... 드래그해서 만들면 될 거 같고 ... 리토포 모드로 가면 우클릭 창이 리토포 메뉴가 나오면 될 듯, 익스트루드 버텍스
합치기 나이프").

* **Manual Retopo** (the selected high-poly parts): a scene of its own ("Retopo - <name>") in a new window - the parts
  joined into ONE reference mesh (a copy: the parts themselves are not touched, it cannot be selected) and an empty
  low mesh "<name>_Retopo" drawn on top of it (in front, wire, blue).
* **Grid Draw**: drag lines over the reference - they stick to its surface.  Lines one way and lines across them: where
  two lines cross is a point, every cell closed by the lines is a face (4 lines: a quad; 3 or 5+: a triangle / n-gon,
  counted in the message).  The cells show while drawing.  Ctrl+Z the last line, Shift+click a line: it goes;
  Enter makes the faces (Cuts 2-4: each cell divided 2x2 .. 4x4, along the lines' own curves), Esc leaves (the lines
  are kept for later).  The new faces join the low (shared edges merged); 0.24.333 the low's open border counts as a
  line - lines drawn next to it close their cells on it, the new faces on its own points.
* **Right click** in the Retopo scene: the Retopo menu (not the Actions wheel) - Grid Draw, Extrude, Merge (Center /
  Collapse / By Distance), Knife, Loop Cut, Poly Build, Fill, Grid Fill, Dissolve, Delete, Relax, Snap to Surface,
  Flip, X Mirror, Edit / Object, Finish.  In Edit Mode moved points snap onto the reference (this scene's own snap
  settings; the main scene's stay as they were).
* **Finish**: the low goes to the main scene (where the parts are), the reference and the Retopo scene go; the low and
  the parts are left selected - Retopo + Bake's 2 Bake bakes them at once ("your own low")."""
from __future__ import annotations

import json
import math

import bpy
import numpy as np
from mathutils import Vector

KEY = 'mch_mretopo'            # on the Retopo scene: {main, ref, out, src}
LINES = 'mch_mretopo_lines'    # on the Retopo scene: [[tol, [x, y, z] ...] ...]
LOW_COLOR = (0.25, 0.65, 1.0, 1.0)
REF_COLOR = (0.62, 0.62, 0.64, 1.0)
PICK_PX = 14                   # a crossing / a Shift+click: this many pixels
SNAP_END = 0.35                # a line meeting the low's border this near (of the edge) to its point: on the point
STEP_PX = 6                    # a line point every this many pixels


# --- the scene ----------------------------------------------------------------------------------------------------

def info(scene):
    try:
        return json.loads(scene.get(KEY, '')) if scene is not None and scene.get(KEY) else None
    except (TypeError, ValueError):
        return None


def in_scene(context):
    return info(getattr(context, 'scene', None)) is not None


def ref_of(scene):
    d = info(scene)
    return bpy.data.objects.get(d['ref']) if d else None


def low_of(scene):
    d = info(scene)
    return bpy.data.objects.get(d['out']) if d else None


def joined_mesh(context, obs, name):
    """The parts (modifiers applied, world space) joined into one mesh (no object)."""
    import bmesh
    dg = context.evaluated_depsgraph_get()
    bm = bmesh.new()
    for o in obs:
        ev = o.evaluated_get(dg)
        try:
            me = ev.to_mesh()
        except RuntimeError:
            continue
        me.transform(o.matrix_world)
        bm.from_mesh(me)
        ev.to_mesh_clear()
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    return me


def _look(scene):
    """The Retopo scene's own settings: points snap onto the reference while editing; the low drawn in front."""
    ts = scene.tool_settings
    try:
        ts.use_snap = True
        ts.snap_elements = {'FACE_PROJECT'}
        ts.snap_target = 'CLOSEST'
        ts.use_snap_self = False
    except (AttributeError, TypeError, ValueError):
        pass
    try:
        ts.use_mesh_automerge = True
    except AttributeError:
        pass


def view_look(window, scene):
    """The window's 3D views: object colours (grey reference, blue low), the retopology overlay."""
    if window is None:
        return
    for area in window.screen.areas:
        if area.type != 'VIEW_3D':
            continue
        sp = area.spaces.active
        try:
            sp.shading.type = 'SOLID'
            sp.shading.color_type = 'OBJECT'
        except (AttributeError, TypeError):
            pass
        try:
            sp.overlay.show_retopology = True
        except AttributeError:
            pass


def start(context, obs, new_window=True):
    """The Retopo scene for the parts ``obs``.  Returns the scene."""
    from . import work_scene as wsm
    main = context.scene
    name = (context.active_object if context.active_object in obs else obs[0]).name
    me = joined_mesh(context, obs, f'{name}_RetopoRef')
    ws = wsm._new_scene(main, f'Retopo - {name}')
    ref = bpy.data.objects.new(f'{name}_RetopoRef', me)
    ws.collection.objects.link(ref)
    ref.hide_select = True
    ref.color = REF_COLOR
    low_me = bpy.data.meshes.new(f'{name}_Retopo')
    low = bpy.data.objects.new(f'{name}_Retopo', low_me)
    ws.collection.objects.link(low)
    low.show_in_front = True
    low.show_wire = True
    low.color = LOW_COLOR
    ws[KEY] = json.dumps(dict(main=main.name, ref=ref.name, out=low.name, src=[o.name for o in obs]))
    _look(ws)
    lay = ws.view_layers[0]
    try:
        low.select_set(True, view_layer=lay)
        lay.objects.active = low
    except (RuntimeError, TypeError):
        pass
    before = set(context.window_manager.windows[:])
    wsm._show(context, ws, new_window)
    made = [w for w in context.window_manager.windows if w not in before] or [context.window]
    view_look(made[-1], ws)
    return ws


def finish(context, scene):
    """The low into the main scene, the reference and the Retopo scene gone.  Returns the low."""
    from . import work_scene as wsm
    d = info(scene)
    main = bpy.data.scenes.get(d.get('main', '')) if d else None
    if main is None:
        return None
    low = bpy.data.objects.get(d['out'])
    ref = bpy.data.objects.get(d['ref'])
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass
    if low is not None:
        if low.name not in main.collection.objects:
            main.collection.objects.link(low)
        if low.name in scene.collection.objects:
            scene.collection.objects.unlink(low)
        low.show_in_front = False
        low.show_wire = False
        low.color = (1.0, 1.0, 1.0, 1.0)
    if ref is not None:
        rme = ref.data
        bpy.data.objects.remove(ref)
        if rme.users == 0:
            bpy.data.meshes.remove(rme)
    wm = context.window_manager
    cur = getattr(context, 'window', None)
    for w in wm.windows:
        if w.scene == scene:
            w.scene = main
            if len(wm.windows) > 1 and (w != cur or any(o != w and o.scene == main for o in wm.windows)):
                wsm._CLOSE.append(w)
    if not any(w.scene == scene for w in wm.windows):
        bpy.data.scenes.remove(scene)
    if wsm._CLOSE:
        bpy.app.timers.register(wsm._close_later, first_interval=0.05)
    lay = main.view_layers[0]
    for o in main.objects:
        try:
            o.select_set(o == low or o.name in d.get('src', ()), view_layer=lay)
        except RuntimeError:
            pass
    if low is not None:
        try:
            lay.objects.active = low
        except (RuntimeError, TypeError):
            pass
    return low


# --- the lines ----------------------------------------------------------------------------------------------------

def lines(scene):
    """[(tol, P (n, 3), view or None)] of the Retopo scene (view: the screen it was drawn on - its 4x4 perspective
    matrix and size)."""
    try:
        raw = json.loads(scene.get(LINES, '[]'))
    except (TypeError, ValueError):
        raw = []
    out = []
    for item in raw:
        t, P = item[0], item[1]
        if len(P) >= 2:
            out.append((float(t), np.array(P, float).reshape(-1, 3), item[2] if len(item) > 2 else None))
    return out


def set_lines(scene, L):
    scene[LINES] = json.dumps([[float(x[0]), np.round(np.asarray(x[1]), 6).tolist()] + ([x[2]] if len(x) > 2 and x[2]
                                                                                         else []) for x in L])


def view_of(region, rv3d):
    return {'m': [v for row in rv3d.perspective_matrix for v in row], 'w': region.width, 'h': region.height}


def _screen(P, view):
    """``P`` on the screen ``view`` (pixels), and its depth (w; <= 0 behind the eye)."""
    M = np.array(view['m'], float).reshape(4, 4)
    H = np.c_[P, np.ones(len(P))] @ M.T
    w = H[:, 3]
    ws = np.where(np.abs(w) > 1e-9, w, 1e-9)
    xy = np.c_[(H[:, 0] / ws + 1) * 0.5 * view['w'], (H[:, 1] / ws + 1) * 0.5 * view['h']]
    return xy, w


def _seg_closest(A0, A1, B0, B1):
    """Closest points of every segment of A against every segment of B: (s (n,m), t (n,m), distance (n,m))."""
    d1 = (A1 - A0)[:, None, :]
    d2 = (B1 - B0)[None, :, :]
    r = A0[:, None, :] - B0[None, :, :]
    a = (d1 * d1).sum(-1)
    e = (d2 * d2).sum(-1)
    f = (d2 * r).sum(-1)
    c = (d1 * r).sum(-1)
    b = (d1 * d2).sum(-1)
    den = a * e - b * b
    s = np.where(den > 1e-18, np.clip((b * f - c * e) / np.where(den > 1e-18, den, 1.0), 0, 1), 0.0)
    t = (b * s + f) / np.maximum(e, 1e-18)
    t = np.clip(t, 0, 1)
    s = np.clip((b * t - c) / np.maximum(a, 1e-18), 0, 1)
    p = A0[:, None, :] + d1 * s[..., None]
    q = B0[None, :, :] + d2 * t[..., None]
    return s, t, np.linalg.norm(p - q, axis=-1)


def _arc(P):
    return np.concatenate(([0.0], np.cumsum(np.linalg.norm(np.diff(P, axis=0), axis=1))))


def _extend(P, by):
    """The line a little longer at both ends (a line that stops just short of another still meets it)."""
    out = [P]
    for end, nxt, at in ((P[0], P[1], 0), (P[-1], P[-2], -1)):
        d = end - nxt
        n = np.linalg.norm(d)
        if n > 1e-12:
            q = end + d / n * by
            out.insert(0 if at == 0 else len(out), q[None])
    return np.concatenate(out)


def graph(L, border_from=None):
    """The crossings of the lines ``L`` [(tol, P, view)]: (nodes (k, 3), edges [(a, b, path (n, 3), line)])."""
    ext = [(x[0], _extend(x[1], x[0] * 1.2), x[2] if len(x) > 2 else None) for x in L]
    hits = []                                    # (line i, arc s on i, line j, arc s on j, point)
    for i in range(len(ext)):
        ti, Pi, _vi = ext[i]
        si = _arc(Pi)
        for j in range(i + 1, len(ext)):
            tj, Pj, vj = ext[j]
            tol = max(ti, tj)
            if vj is not None:                   # 0.24.332 where they cross ON THE SCREEN the later one was drawn on
                Ai, wi = _screen(Pi, vj)         #  (a line over a groove: in 3D it dips, on the screen it crosses)
                Aj, wj = _screen(Pj, vj)
                A3 = np.c_[Ai, np.zeros(len(Ai))]
                B3 = np.c_[Aj, np.zeros(len(Aj))]
                s, t, dist = _seg_closest(A3[:-1], A3[1:], B3[:-1], B3[1:])
                front = (wi[:-1, None] > 0) & (wj[None, :-1] > 0)
                ok = (dist < PICK_PX * 0.6) & front
            else:
                s, t, dist = _seg_closest(Pi[:-1], Pi[1:], Pj[:-1], Pj[1:])
                ok = dist < tol
            if border_from is not None and i < border_from <= j:   # 0.24.333 a line along the low's border (over it):
                da = Pi[1:] - Pi[:-1]                            #  not crossing it there
                db = Pj[1:] - Pj[:-1]
                na = np.linalg.norm(da, axis=1)[:, None]
                nb = np.linalg.norm(db, axis=1)[None, :]
                cos = np.abs(da @ db.T) / np.maximum(na * nb, 1e-20)
                ok = ok & (cos < 0.9)
            ia, ja = np.nonzero(ok)
            if not len(ia):
                continue
            sj = _arc(Pj)
            cand = []
            for a, b in zip(ia, ja):
                ai = si[a] + s[a, b] * (si[a + 1] - si[a])
                bj = sj[b] + t[a, b] * (sj[b + 1] - sj[b])
                pa = Pi[a] + (Pi[a + 1] - Pi[a]) * s[a, b]
                pb = Pj[b] + (Pj[b + 1] - Pj[b]) * t[a, b]
                if vj is not None:               # (the one in front: what the eye saw there)
                    da = wi[a] + (wi[a + 1] - wi[a]) * s[a, b]
                    db = wj[b] + (wj[b + 1] - wj[b]) * t[a, b]
                    p = pa if da <= db else pb
                else:
                    p = (pa + pb) * 0.5
                cand.append((dist[a, b], ai, bj, p, None if vj is None else (
                    Ai[a] + (Ai[a + 1] - Ai[a]) * s[a, b])))
            cand.sort(key=lambda c: c[0])
            taken = []
            for dd, ai, bj, p, xy in cand:        # (one crossing per place along the two lines)
                if xy is not None:
                    new = all(np.linalg.norm(xy - q) > PICK_PX * 2 for _x, _y, q in taken)
                else:
                    new = all(abs(ai - x) > 3 * tol or abs(bj - y) > 3 * tol for x, y, _q in taken)
                if new:
                    taken.append((ai, bj, xy))
                    hits.append((i, ai, j, bj, p, tol, None if xy is None else (xy, vj)))
    # nodes: crossings close together are one point
    pts = [h[4] for h in hits]
    parent = list(range(len(pts)))

    def root(x):
        while parent[x] != x:
            parent[x] = parent[parent[x]]
            x = parent[x]
        return x
    def close(a, b):
        sa = hits[a][6]
        if sa is not None:                       # (on the screen it was drawn on)
            q = _screen(np.array([pts[b]]), sa[1])[0][0]
            return np.linalg.norm(q - sa[0]) < PICK_PX * 1.5
        return np.linalg.norm(pts[a] - pts[b]) < max(hits[a][5], hits[b][5]) * 1.5
    for a in range(len(pts)):
        for b in range(a + 1, len(pts)):
            if close(a, b):
                parent[root(a)] = root(b)
    groups = {}
    for a in range(len(pts)):
        groups.setdefault(root(a), []).append(a)
    nodes, of_hit = [], {}
    for k, members in enumerate(groups.values()):
        nodes.append(np.mean([pts[m] for m in members], axis=0))
        for m in members:
            of_hit[m] = k
    on_line = {}                                 # line -> [(arc, node)]
    for h, (i, ai, j, bj, _p, _t, _s) in enumerate(hits):
        on_line.setdefault(i, []).append((ai, of_hit[h]))
        on_line.setdefault(j, []).append((bj, of_hit[h]))
    edges, seen = [], set()
    for i, lst in on_line.items():
        P = ext[i][1]
        s = _arc(P)
        lst = sorted(lst)
        clean = []
        for a, n in lst:
            if clean and clean[-1][1] == n:
                continue
            clean.append((a, n))
        for (a0, n0), (a1, n1) in zip(clean, clean[1:]):
            if n0 == n1 or (min(n0, n1), max(n0, n1), i) in seen:
                continue
            seen.add((min(n0, n1), max(n0, n1), i))
            inner = P[(s > a0) & (s < a1)]
            path = np.concatenate((nodes[n0][None], inner, nodes[n1][None]))
            edges.append((n0, n1, path, i))
    return np.array(nodes).reshape(-1, 3), edges


def faces(nodes, edges, normal_at, views=None):
    """The cells the edges close: [[half-edge (edge index, forward)] ...] - each cell once, the outside left out.
    ``normal_at(p)`` the surface's normal there; ``views`` (per line) the screens the lines were drawn on - then the
    turn round a point and the cell's way round are read on that screen (what the user saw)."""
    views = views or []

    def view_of_line(i):
        return views[i] if 0 <= i < len(views) else None
    inc = {}
    for k, e in enumerate(edges):
        a, b = e[0], e[1]
        inc.setdefault(a, []).append((k, True))
        inc.setdefault(b, []).append((k, False))
    order = {}
    for v, lst in inc.items():
        view = view_of_line(max(edges[k][3] if len(edges[k]) > 3 else -1 for k, _f in lst))

        def out_point(h):
            k, fwd = h
            path = edges[k][2]
            if len(path) > 3:                    # (the line's direction a little way out, not its first wobble)
                return path[min(3, len(path) - 1)] if fwd else path[max(-4, -len(path))]
            return path[1] if fwd else path[-2]
        if view is not None:
            c = _screen(np.array([nodes[v]]), view)[0][0]

            def ang(h, c=c, view=view):
                q = _screen(np.array([out_point(h)]), view)[0][0]
                return math.atan2(q[1] - c[1], q[0] - c[0])
        else:
            n = Vector(normal_at(nodes[v])).normalized()
            x = n.orthogonal().normalized()
            y = n.cross(x)

            def ang(h, x=x, y=y):
                d = Vector(out_point(h)) - Vector(nodes[v])
                return math.atan2(d.dot(y), d.dot(x))
        order[v] = sorted(lst, key=ang)
    used, cells = set(), []
    for k in range(len(edges)):
        for fwd in (True, False):
            if (k, fwd) in used:
                continue
            cyc, h = [], (k, fwd)
            for _guard in range(64):
                if h in used:
                    break
                used.add(h)
                cyc.append(h)
                kk, ff = h
                b = edges[kk][1] if ff else edges[kk][0]
                lst = order[b]
                back = (kk, not ff)              # the same edge leaving b
                idx = lst.index(back)
                h = lst[(idx - 1) % len(lst)]    # the next one clockwise round b: the cell on the left
            if h == (k, fwd) and len(cyc) >= 3:
                cells.append(cyc)
    keep = []
    for cyc in cells:
        P = np.concatenate([edges[k][2] if f else edges[k][2][::-1] for k, f in cyc])
        view = view_of_line(max(edges[k][3] if len(edges[k]) > 3 else -1 for k, _f in cyc))
        if view is not None:
            Q = _screen(P, view)[0]
            area = 0.5 * float(np.sum(Q[:, 0] * np.roll(Q[:, 1], -1) - np.roll(Q[:, 0], -1) * Q[:, 1]))
        else:
            c = P.mean(0)
            n = np.array(normal_at(c))
            area = 0.5 * np.cross(P - c, np.roll(P, -1, axis=0) - c).sum(0).dot(n)
        if area > 0:                             # (the outside goes round the other way)
            keep.append(cyc)
    return keep


def _resample(path, n):
    s = _arc(path)
    if s[-1] <= 0:
        return np.repeat(path[:1], n + 1, axis=0)
    u = np.linspace(0, s[-1], n + 1)
    return np.stack([np.interp(u, s, path[:, i]) for i in range(3)], axis=1)


def build(nodes, edges, cells, cuts=1, snap=None):
    """(V, F) of the cells: a quad cell ``cuts`` x ``cuts`` along its own edges (a Coons patch), others one face of
    their edge points.  ``snap(p)`` puts a new inside point on the surface."""
    V = [np.asarray(p, float) for p in nodes]
    edge_pts = {}

    def edge_ids(k):
        if k not in edge_pts:
            a, b, path = edges[k][:3]
            P = _resample(path, cuts)
            ids = [a]
            for p in P[1:-1]:
                V.append(snap(p) if snap else p)
                ids.append(len(V) - 1)
            ids.append(b)
            edge_pts[k] = ids
        return edge_pts[k]

    def side(h):
        k, f = h
        ids = edge_ids(k)
        return ids if f else ids[::-1]
    F = []
    for cyc in cells:
        sides = [side(h) for h in cyc]
        if len(cyc) == 4 and cuts > 1:
            n = cuts
            B0, R, T, Lf = sides[0], sides[1], sides[2][::-1], sides[3][::-1]   # bottom, right, top, left
            P = lambda i: V[i]                                                  # noqa: E731
            grid = [[None] * (n + 1) for _ in range(n + 1)]
            for i in range(n + 1):
                grid[i][0] = B0[i]
                grid[i][n] = T[i]
            for j in range(n + 1):
                grid[0][j] = Lf[j]
                grid[n][j] = R[j]
            c00, c10, c01, c11 = P(B0[0]), P(B0[n]), P(T[0]), P(T[n])
            for i in range(1, n):
                for j in range(1, n):
                    u, v = i / n, j / n
                    p = ((1 - v) * P(B0[i]) + v * P(T[i]) + (1 - u) * P(Lf[j]) + u * P(R[j])
                         - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11))
                    V.append(snap(p) if snap else p)
                    grid[i][j] = len(V) - 1
            for i in range(n):
                for j in range(n):
                    F.append([grid[i][j], grid[i + 1][j], grid[i + 1][j + 1], grid[i][j + 1]])
        else:
            ring = []
            for s in sides:
                ring.extend(s[:-1])
            F.append(ring)
    return np.array(V).reshape(-1, 3), F


def border_lines(low, L, view):
    """0.24.333 (user: "그 옆에 그리면 추가로 같이 붙는 건 어때") the low's open border near the new lines, as lines
    of its own (one per border edge, the new lines' tolerance and screen): a new line that crosses it or ends on it
    meets it, the border closes the cells next to the low."""
    if low is None or view is None or not len(low.data.polygons) or not L:
        return []
    import bmesh
    me = low.data
    bm = bmesh.new()
    bm.from_mesh(me)
    M = low.matrix_world
    segs = [(np.array(M @ e.verts[0].co), np.array(M @ e.verts[1].co)) for e in bm.edges if e.is_boundary]
    bm.free()
    if not segs:
        return []
    allp = np.concatenate([_screen(x[1], view)[0] for x in L])
    lo, hi = allp.min(0) - PICK_PX * 4, allp.max(0) + PICK_PX * 4
    tol = float(np.median([x[0] for x in L]))
    out = []
    for a, b in segs:
        q, w = _screen(np.array([a, b]), view)
        if (w <= 0).any():
            continue
        if (np.maximum(q[0], q[1]) < lo).any() or (np.minimum(q[0], q[1]) > hi).any():
            continue
        out.append((tol, np.array([a, b]), view))
    return out


def plan(L, ref, tree, low=None, low_tree=None):
    """(nodes, edges, cells, all lines) of the drawn lines ``L`` - with the low's open border near them as lines
    too (``low``); a cell of the border only, or over faces the low already has, is left out."""
    view = next((x[2] for x in reversed(L) if len(x) > 2 and x[2]), None)
    B = border_lines(low, L, view)
    A = list(L) + B
    nodes, edges = graph(A, len(L) if B else None)
    if not len(nodes):
        return nodes, edges, [], A
    Mr, Mri = ref.matrix_world, ref.matrix_world.inverted()

    def normal_at(p):
        hit = tree.find_nearest(Mri @ Vector(p))
        return tuple((Mr.to_3x3() @ hit[1]).normalized()) if hit[1] is not None else (0.0, 0.0, 1.0)
    cells = faces(nodes, edges, normal_at, [x[2] if len(x) > 2 else None for x in A])
    if B:
        n_new = len(L)
        keep = []
        for cyc in cells:
            if all(edges[k][3] >= n_new for k, _f in cyc):
                continue                         # (the low's own border round: not a new cell)
            if low_tree is not None:
                P = np.concatenate([edges[k][2] for k, _f in cyc])
                c = P.mean(0)
                hit = low_tree.find_nearest(Vector(c))
                if hit[0] is not None and hit[3] < max(x[0] for x in L) * 0.5:
                    inside = _inside_low(cyc, edges, nodes, low_tree, view)
                    if inside:
                        continue
            keep.append(cyc)
        cells = keep
    return nodes, edges, cells, A


def _inside_low(cyc, edges, nodes, low_tree, view):
    """Is the cell over faces the low already has (its middle, seen on the screen, on the low)?"""
    if view is None:
        return False
    P = np.concatenate([edges[k][2] if f else edges[k][2][::-1] for k, f in cyc])
    Q = _screen(P, view)[0]
    cx, cy = Q.mean(0)
    Minv = np.linalg.inv(np.array(view['m'], float).reshape(4, 4))
    ndc = (cx / view['w'] * 2 - 1, cy / view['h'] * 2 - 1)
    a = Minv @ np.r_[ndc[0], ndc[1], -1.0, 1.0]
    b = Minv @ np.r_[ndc[0], ndc[1], 1.0, 1.0]
    a, b = a[:3] / a[3], b[:3] / b[3]
    hit = low_tree.ray_cast(Vector(a), Vector(b - a).normalized())
    return hit[0] is not None


def low_tree_of(low):
    """A BVH of the low (world space), or None."""
    from mathutils.bvhtree import BVHTree
    if low is None or not len(low.data.polygons):
        return None
    M = low.matrix_world
    return BVHTree.FromPolygons([M @ v.co for v in low.data.vertices], [p.vertices for p in low.data.polygons])


def make(context, scene, cuts=1):
    """The scene's lines into faces on the low.  Returns (quads, others) made, or None (no cell)."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    L = lines(scene)
    ref, low = ref_of(scene), low_of(scene)
    if not L or ref is None or low is None:
        return None
    tree = BVHTree.FromPolygons([v.co for v in ref.data.vertices], [p.vertices for p in ref.data.polygons])
    Mr = ref.matrix_world
    Mri = Mr.inverted()

    def near(p):
        hit = tree.find_nearest(Mri @ Vector(p))
        return hit

    def normal_at(p):
        hit = near(p)
        return tuple((Mr.to_3x3() @ hit[1]).normalized()) if hit[1] is not None else (0.0, 0.0, 1.0)

    view = next((x[2] for x in reversed(L) if len(x) > 2 and x[2]), None)
    Minv = np.linalg.inv(np.array(view['m'], float).reshape(4, 4)) if view else None

    def snap(p):
        """Onto the surface: along the line of sight of the screen the lines were drawn on (what was seen there),
        else the nearest point."""
        if Minv is not None:
            H = np.array(view['m'], float).reshape(4, 4) @ np.r_[p, 1.0]
            if H[3] > 1e-9:
                ndc = H[:3] / H[3]
                a = Minv @ np.r_[ndc[0], ndc[1], -1.0, 1.0]
                b = Minv @ np.r_[ndc[0], ndc[1], 1.0, 1.0]
                a, b = a[:3] / a[3], b[:3] / b[3]
                d = b - a
                o = Mri @ Vector(a)
                dl = (Mri.to_3x3() @ Vector(d)).normalized()
                hit = tree.ray_cast(o, dl)
                if hit[0] is not None:
                    q = np.array(Mr @ hit[0])
                    if np.linalg.norm(q - p) < tol_snap:
                        return q
        hit = near(p)
        return np.array(Mr @ hit[0]) if hit[0] is not None else np.asarray(p)
    tol_snap = max(x[0] for x in L) * 6
    nodes, edges, cells, A = plan(L, ref, tree, low, low_tree_of(low))
    if not len(nodes) or not cells:
        return None
    nodes = np.array([snap(p) for p in nodes])
    B = A[len(L):]
    if B:                                       # (a line meeting the low's border near one of its points: on it -
        btol = max(x[0] for x in L)             #  only near the middle of a border edge is that edge split)
        for k in range(len(nodes)):
            for _t, seg, *_v in B:
                a, b = seg[0], seg[1]
                d = b - a
                L2 = float(d @ d)
                if L2 <= 1e-20:
                    continue
                t = float((nodes[k] - a) @ d) / L2
                if -0.05 <= t <= 1.05 and np.linalg.norm(a + d * min(max(t, 0), 1) - nodes[k]) < btol:
                    if t < SNAP_END:
                        nodes[k] = a
                    elif t > 1 - SNAP_END:
                        nodes[k] = b
                    break
    if Minv is not None:                        # 0.24.332 on the screen it was drawn on: the cells divided there
        # (evenly, as seen), every point then put on the surface along its line of sight - a groove the lines
        # cross does not pull the points into it

        def flat(P):
            xy, _w = _screen(np.asarray(P, float).reshape(-1, 3), view)
            return np.c_[xy, np.zeros(len(xy))]

        def lift(q, fallback):
            ndc = (q[0] / view['w'] * 2 - 1, q[1] / view['h'] * 2 - 1)
            a = Minv @ np.r_[ndc[0], ndc[1], -1.0, 1.0]
            b = Minv @ np.r_[ndc[0], ndc[1], 1.0, 1.0]
            a, b = a[:3] / a[3], b[:3] / b[3]
            d = (b - a) / max(np.linalg.norm(b - a), 1e-12)
            hit = tree.ray_cast(Mri @ Vector(a), (Mri.to_3x3() @ Vector(d)).normalized())
            if hit[0] is not None:
                return np.array(Mr @ hit[0])
            return a + d * float(np.dot(fallback - a, d))        # (missed: on the ray, as deep as the corner)
        n2 = flat(nodes)
        e2 = [(e[0], e[1], flat(e[2])) + tuple(e[3:]) for e in edges]
        V2, F = build(n2, e2, cells, cuts, None)
        V = [nodes[i] if i < len(nodes) else None for i in range(len(V2))]
        near_node = n2[:, :2]
        for i in range(len(nodes), len(V2)):
            j = int(np.argmin(np.linalg.norm(near_node - V2[i][:2], axis=1)))
            V[i] = lift(V2[i], nodes[j])
        V = np.array(V)
    else:
        V, F = build(nodes, edges, cells, cuts, snap)
    Mi = low.matrix_world.inverted()
    me = low.data
    bm = bmesh.new()
    bm.from_mesh(me)
    old = len(bm.verts)
    vs = [bm.verts.new(Mi @ Vector(p)) for p in V]
    quads = others = 0
    for f in F:
        if len(set(f)) < 3:
            continue
        try:
            face = bm.faces.new([vs[i] for i in f])
        except ValueError:                      # (already there)
            continue
        if len(f) == 4:
            quads += 1
        else:
            others += 1
        c = sum((Vector(V[i]) for i in f), Vector()) / len(f)
        face.normal_update()
        if face.normal.dot(Mi.to_3x3() @ Vector(normal_at(c))) < 0:
            face.normal_flip()
    tol = min(x[0] for x in L)
    bmesh.ops.remove_doubles(bm, verts=vs, dist=tol * 0.1)
    if old:                                     # (the new faces meet the old ones: a new point within a line's
        from mathutils.kdtree import KDTree     #  tolerance of an old one becomes it)
        bm.verts.ensure_lookup_table()
        olds = [v for v in bm.verts[:old] if v.is_valid]
        kd = KDTree(len(olds))
        for i, v in enumerate(olds):
            kd.insert(v.co, i)
        kd.balance()
        weld = {}
        for v in vs:
            if v.is_valid:
                _co, i, dist = kd.find(v.co)
                if i is not None and dist < tol:
                    weld[v] = olds[i]
        rest = [v for v in vs if v.is_valid and v not in weld]
        if weld:
            bmesh.ops.weld_verts(bm, targetmap=weld)
        # (a new point ON an old border edge, not at its ends: that edge split there, the point merged into it)
        split = {}
        for v in rest:
            if not v.is_valid:
                continue
            for e in [e for e in bm.edges if e.is_boundary and v not in e.verts]:
                a, b = e.verts[0].co, e.verts[1].co
                d = b - a
                L2 = d.length_squared
                if L2 <= 1e-20:
                    continue
                t = (v.co - a).dot(d) / L2
                if 0.02 < t < 0.98 and (a + d * t - v.co).length < tol:
                    _e, nv = bmesh.utils.edge_split(e, e.verts[0], t)
                    split[v] = nv
                    break
        if split:
            bmesh.ops.weld_verts(bm, targetmap=split)
    loose = [v for v in bm.verts if not v.link_faces]
    bmesh.ops.delete(bm, geom=loose, context='VERTS')
    if bpy.context.mode == 'EDIT_MESH' and low.mode == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT')
    bm.to_mesh(me)
    bm.free()
    me.update()
    return quads, others


def snap_low(context, scene, only_selected=False):
    """The low's points onto the reference (nearest)."""
    from mathutils.bvhtree import BVHTree
    ref, low = ref_of(scene), low_of(scene)
    if ref is None or low is None:
        return 0
    tree = BVHTree.FromPolygons([v.co for v in ref.data.vertices], [p.vertices for p in ref.data.polygons])
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    Mr, Mri = ref.matrix_world, ref.matrix_world.inverted()
    edit = low.mode == 'EDIT'
    if edit:
        bpy.ops.object.mode_set(mode='OBJECT')
    n = 0
    for v in low.data.vertices:
        if only_selected and not v.select:
            continue
        hit = tree.find_nearest(Mri @ (M @ v.co))
        if hit[0] is not None:
            v.co = Mi @ (Mr @ hit[0])
            n += 1
    low.data.update()
    if edit:
        bpy.ops.object.mode_set(mode='EDIT')
    return n


def set_mirror(low, on):
    m = low.modifiers.get('MCH Retopo Mirror')
    if on and m is None:
        m = low.modifiers.new('MCH Retopo Mirror', 'MIRROR')
        m.use_clip = True
        m.use_mirror_merge = True
        m.merge_threshold = 0.001
        m.show_on_cage = True
    elif not on and m is not None:
        low.modifiers.remove(m)


# --- settings -----------------------------------------------------------------------------------------------------

def _mirror_update(self, context):
    low = low_of(context.scene)
    if low is not None:
        set_mirror(low, self.mirror)


class MCH_PG_mretopo(bpy.types.PropertyGroup):
    cuts: bpy.props.IntProperty(name='Cuts', default=1, min=1, max=4,
                                description='Each drawn cell divided into Cuts x Cuts quads (1: as drawn)')
    mirror: bpy.props.BoolProperty(name='X Mirror', default=False, update=_mirror_update,
                                   description='Draw one side: the other side made by a live Mirror (X)')


# --- the Grid Draw mode -------------------------------------------------------------------------------------------

_DRAW = {'handle': None, 'op': None}


def _draw_view():
    op = _DRAW.get('op')
    if op is None:
        return
    try:
        op.draw_view()
    except ReferenceError:
        _DRAW['op'] = None


class MCH_OT_mretopo_draw(bpy.types.Operator):
    """Grid Draw: drag lines over the reference - lines one way and lines across them; every closed cell becomes a
    face.  Enter: make the faces, Ctrl+Z: last line off, Shift+click: that line off, Esc: leave (lines kept)"""
    bl_idname = 'mch.mretopo_draw'
    bl_label = 'Grid Draw'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return in_scene(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        from mathutils.bvhtree import BVHTree
        self.ref = ref_of(context.scene)
        if self.ref is None:
            return {'CANCELLED'}
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        me = self.ref.data
        self.tree = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
        self.L = lines(context.scene)
        self.cur = None
        self.preview = []
        self._preview(context)
        _DRAW['op'] = self
        if _DRAW['handle'] is None:
            _DRAW['handle'] = bpy.types.SpaceView3D.draw_handler_add(_draw_view, (), 'WINDOW', 'POST_VIEW')
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set('Grid Draw: drag lines over the model (one way, then across)   '
                                          'Enter: make faces   Ctrl+Z: last line off   Shift+click: a line off   '
                                          'Esc: leave   right click: Retopo menu')
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    # (surface hits)
    def hit(self, context, xy):
        from bpy_extras import view3d_utils
        r, rv = context.region, context.region_data
        o = view3d_utils.region_2d_to_origin_3d(r, rv, xy)
        d = view3d_utils.region_2d_to_vector_3d(r, rv, xy)
        M, Mi = self.ref.matrix_world, self.ref.matrix_world.inverted()
        lo, ld = Mi @ o, (Mi.to_3x3() @ d).normalized()
        p, _n, _i, _dist = self.tree.ray_cast(lo, ld)
        if p is None:
            return None, None
        w = M @ p
        # the tolerance: PICK_PX on the screen at that depth
        a = view3d_utils.location_3d_to_region_2d(r, rv, w)
        if a is None:
            return w, None
        b = view3d_utils.region_2d_to_location_3d(r, rv, (a.x + PICK_PX, a.y), w)
        return w, (b - w).length

    def _preview(self, context):
        """The cells the lines close now (shown)."""
        self.preview = []
        if len(self.L) < 2:
            return
        try:
            low = low_of(context.scene)
            nodes, edges, cells, _A = plan(self.L, self.ref, self.tree, low, low_tree_of(low))
            if not len(nodes):
                return
            for cyc in cells:
                P = np.concatenate([edges[k][2] if f else edges[k][2][::-1] for k, f in cyc])
                self.preview.append((P, len(cyc)))
            self.nodes = nodes
        except (ValueError, IndexError, KeyError):
            self.preview = []

    def draw_view(self):
        import gpu
        from gpu_extras.batch import batch_for_shader
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        vp = gpu.state.viewport_get()
        sh.uniform_float('viewportSize', (vp[2], vp[3]))
        sh.uniform_float('lineWidth', 2.5)
        segs = []
        for P in [x[1] for x in self.L] + ([np.array(self.cur)] if self.cur is not None and len(self.cur) > 1 else []):
            for a, b in zip(P[:-1], P[1:]):
                segs.extend((tuple(a), tuple(b)))
        if segs:
            sh.uniform_float('color', (1.0, 0.55, 0.1, 0.95))
            batch_for_shader(sh, 'LINES', {'pos': segs}).draw(sh)
        fill = gpu.shader.from_builtin('UNIFORM_COLOR')
        for P, k in self.preview:
            c = P.mean(0)
            tris = []
            for a, b in zip(P, np.roll(P, -1, axis=0)):
                tris.extend((tuple(c), tuple(a), tuple(b)))
            fill.uniform_float('color', (0.25, 0.65, 1.0, 0.28) if k == 4 else (1.0, 0.3, 0.3, 0.28))
            batch_for_shader(fill, 'TRIS', {'pos': tris}).draw(fill)
        if self.preview and getattr(self, 'nodes', None) is not None and len(self.nodes):
            pt = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
            gpu.state.point_size_set(8)
            pt.uniform_float('color', (1.0, 1.0, 1.0, 1.0))
            batch_for_shader(pt, 'POINTS', {'pos': [tuple(p) for p in self.nodes]}).draw(pt)
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')

    def _save(self, context):
        set_lines(context.scene, self.L)
        self._preview(context)
        context.area.tag_redraw()

    def _line_at(self, context, xy):
        from bpy_extras import view3d_utils
        best, at = PICK_PX * 1.5, None
        for k, (_t, P, *_v) in enumerate(self.L):
            for p in P:
                q = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, Vector(p))
                if q is not None:
                    d = math.hypot(q.x - xy[0], q.y - xy[1])
                    if d < best:
                        best, at = d, k
        return at

    def _end(self, context):
        _DRAW['op'] = None
        if _DRAW['handle'] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW['handle'], 'WINDOW')
            _DRAW['handle'] = None
        context.workspace.status_text_set(None)
        if context.area is not None:
            context.area.tag_redraw()

    def modal(self, context, event):
        xy = (event.mouse_region_x, event.mouse_region_y)
        if self.cur is not None:
            if event.type == 'MOUSEMOVE':
                if math.hypot(xy[0] - self.last_xy[0], xy[1] - self.last_xy[1]) >= STEP_PX:
                    w, tol = self.hit(context, xy)
                    if w is not None:
                        self.cur.append(tuple(w))
                        self.tols.append(tol or 0.0)
                        self.last_xy = xy
                        context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                if len(self.cur) >= 2:
                    tol = float(np.median([t for t in self.tols if t] or [0.0]))
                    self.L.append((tol, np.array(self.cur), view_of(context.region, context.region_data)))
                    self._save(context)
                self.cur = None
                context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            if not (0 <= xy[0] < context.region.width and 0 <= xy[1] < context.region.height):
                return {'PASS_THROUGH'}
            if event.shift:
                k = self._line_at(context, xy)
                if k is not None:
                    self.L.pop(k)
                    self._save(context)
                return {'RUNNING_MODAL'}
            w, tol = self.hit(context, xy)
            if w is None:
                return {'RUNNING_MODAL'}
            self.cur, self.tols, self.last_xy = [tuple(w)], [tol or 0.0], xy
            return {'RUNNING_MODAL'}
        if event.type == 'Z' and event.value == 'PRESS' and (event.ctrl or event.oskey):
            if self.L:
                self.L.pop()
                self._save(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'SPACE'} and event.value == 'PRESS':
            self._end(context)
            set_lines(context.scene, self.L)
            st = context.scene.mch_mretopo
            got = make(context, context.scene, st.cuts)
            if got is None:
                self.report({'WARNING'}, 'Grid Draw: no closed cell yet - draw lines one way, then lines across them')
                return {'CANCELLED'}
            set_lines(context.scene, [])
            q, o = got
            self.report({'INFO'}, f'Retopo: {q} quad(s)' + (f', {o} triangle / n-gon cell(s) (not 4 sides)' if o else '')
                        + ' added - right click: the Retopo menu')
            return {'FINISHED'}
        if event.type == 'ESC' and event.value == 'PRESS':
            self._end(context)
            set_lines(context.scene, self.L)
            return {'FINISHED'}
        if event.type == 'RIGHTMOUSE' and event.value == 'PRESS':
            self._end(context)
            set_lines(context.scene, self.L)
            bpy.ops.wm.call_panel('INVOKE_DEFAULT', name=MCH_PT_mretopo_menu.bl_idname, keep_open=False)
            return {'FINISHED'}
        return {'PASS_THROUGH'}                  # (navigation, the UI)


# --- operators ------------------------------------------------------------------------------------------------------

class MCH_OT_mretopo_start(bpy.types.Operator):
    """Manual Retopo: the selected high-poly parts joined (a copy) in a Retopo scene of their own, in a new window -
    draw the low over it by hand (Grid Draw, right click: the Retopo menu), Finish brings the low back"""
    bl_idname = 'mch.mretopo_start'
    bl_label = 'Manual Retopo'
    bl_options = {'REGISTER', 'UNDO'}

    new_window: bpy.props.BoolProperty(name='New Window', default=True)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        if in_scene(context):
            self.report({'INFO'}, 'Already in a Retopo scene')
            return {'CANCELLED'}
        obs = [o for o in context.selected_objects if o.type == 'MESH' and o.visible_get()]
        if not obs:
            self.report({'WARNING'}, 'Manual Retopo: select the high-poly parts first')
            return {'CANCELLED'}
        ws = start(context, obs, self.new_window)
        ref = ref_of(ws)
        self.report({'INFO'}, f'Manual Retopo: {len(obs)} part(s) joined ({len(ref.data.polygons):,} faces) - '
                              f'right click: Grid Draw and the Retopo tools')
        return {'FINISHED'}


class MCH_OT_mretopo_finish(bpy.types.Operator):
    """Finish: the low to the main scene (next to the parts), the reference and the Retopo scene gone"""
    bl_idname = 'mch.mretopo_finish'
    bl_label = 'Finish Retopo'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return in_scene(context)

    def execute(self, context):
        low = finish(context, context.scene)
        if low is None:
            return {'CANCELLED'}
        self.report({'INFO'}, f'{low.name}: {len(low.data.polygons)} faces - in the main scene with the parts '
                              f'selected (Retopo + Bake: 2 Bake)')
        return {'FINISHED'}


EDIT_ACTIONS = (
    ('EXTRUDE', 'Extrude', 'Extrude the selection (then move it)', 'view3d.edit_mesh_extrude_move_normal', {}),
    ('MERGE_CENTER', 'Merge Center', 'The selected points merged at their centre', 'mesh.merge', {'type': 'CENTER'}),
    ('COLLAPSE', 'Collapse', 'Each selected piece merged into one point', 'mesh.merge', {'type': 'COLLAPSE'}),
    ('MERGE_DIST', 'By Distance', 'Points closer than a little merged', 'mesh.remove_doubles', {}),
    ('KNIFE', 'Knife', 'Cut new edges (Enter to finish)', 'mesh.knife_tool', {}),
    ('LOOPCUT', 'Loop Cut', 'A new edge loop (click, slide)', 'mesh.loopcut_slide', {}),
    ('FILL', 'Fill', 'A face (or edge) from the selected points', 'mesh.edge_face_add', {}),
    ('GRID_FILL', 'Grid Fill', 'A closed edge ring filled with a grid', 'mesh.fill_grid', {}),
    ('DISSOLVE', 'Dissolve', 'The selected points / edges dissolved (the faces stay)', 'mesh.dissolve_mode', {}),
    ('DELETE', 'Delete', 'The selected points deleted', 'mesh.delete', {'type': 'VERT'}),
    ('BRIDGE', 'Bridge', 'Two edge loops bridged', 'mesh.bridge_edge_loops', {}),
    ('FLIP', 'Flip', 'The selected faces turned round', 'mesh.flip_normals', {}),
)
_EDIT = {a[0]: a for a in EDIT_ACTIONS}


class MCH_OT_mretopo_edit(bpy.types.Operator):
    """A Retopo edit tool on the low (Edit Mode first if needed)"""
    bl_idname = 'mch.mretopo_edit'
    bl_label = 'Retopo Edit'
    bl_options = {'REGISTER', 'UNDO'}

    action: bpy.props.EnumProperty(items=[(a, n, d) for a, n, d, _o, _p in EDIT_ACTIONS]
                                   + [('POLYBUILD', 'Poly Build', 'Blender\'s Poly Build tool: click to add faces'),
                                      ('RELAX', 'Relax', 'The selected points smoothed, then back on the surface'),
                                      ('SNAP', 'Snap to Surface', 'The points (selected in Edit Mode) onto the model'),
                                      ('MODE', 'Edit / Object', 'Edit Mode on the low, or back')])

    @classmethod
    def poll(cls, context):
        return in_scene(context)

    @classmethod
    def description(cls, context, props):
        for a, _n, d, _o, _p in EDIT_ACTIONS:
            if a == props.action:
                return d
        return cls.__doc__

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        low = low_of(context.scene)
        if low is None:
            return {'CANCELLED'}
        lay = context.view_layer
        if lay.objects.active != low:
            if context.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            for o in context.selected_objects:
                o.select_set(False)
            low.select_set(True)
            lay.objects.active = low
        if self.action == 'MODE':
            bpy.ops.object.mode_set(mode='OBJECT' if low.mode == 'EDIT' else 'EDIT')
            return {'FINISHED'}
        if self.action == 'SNAP':
            n = snap_low(context, context.scene, only_selected=low.mode == 'EDIT')
            self.report({'INFO'}, f'{n} point(s) on the surface')
            return {'FINISHED'}
        if low.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        try:
            if self.action == 'POLYBUILD':
                bpy.ops.wm.tool_set_by_id(name='builtin.poly_build')
            elif self.action == 'RELAX':
                bpy.ops.mesh.vertices_smooth(factor=0.5, repeat=3)
                snap_low(context, context.scene, only_selected=True)
            else:
                _a, _n, _d, op, props = _EDIT[self.action]
                mod, name = op.split('.')
                fn = getattr(getattr(bpy.ops, mod), name)
                if self.action in {'KNIFE', 'LOOPCUT', 'EXTRUDE'}:
                    fn('INVOKE_DEFAULT', **props)
                else:
                    fn(**props)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex).split('\n')[-1][:160] or 'Not possible on this selection')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_mretopo_lines(bpy.types.Operator):
    """The Grid Draw lines not made yet: all taken off"""
    bl_idname = 'mch.mretopo_lines'
    bl_label = 'Clear Lines'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return in_scene(context) and bool(lines(context.scene))

    def execute(self, context):
        set_lines(context.scene, [])
        return {'FINISHED'}


class MCH_PT_mretopo_menu(bpy.types.Panel):
    bl_idname = 'MCH_PT_mretopo_menu'
    bl_label = 'Retopo'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 16

    @classmethod
    def poll(cls, context):
        return in_scene(context)

    def draw(self, context):
        draw_menu(self.layout, context)


def draw_menu(layout, context):
    S = context.scene
    st = S.mch_mretopo
    low = low_of(S)
    layout.operator_context = 'INVOKE_DEFAULT'
    col = layout.column(align=True)
    col.label(text='RETOPO', icon='MOD_REMESH')
    r = col.row(align=True)
    r.scale_y = 1.4
    r.operator('mch.mretopo_draw', text='Grid Draw', icon='GREASEPENCIL')
    r = col.row(align=True)
    r.prop(st, 'cuts')
    r.prop(st, 'mirror', toggle=True)
    nl = len(lines(S))
    if nl:
        r = col.row(align=True)
        r.label(text=f'{nl} line(s) not made yet')
        r.operator('mch.mretopo_lines', text='', icon='X')

    def grid(acts, cols=3):
        g = layout.grid_flow(row_major=True, columns=cols, even_columns=True, align=True)
        for a in acts:
            g.operator('mch.mretopo_edit', text=dict((x, n) for x, n, *_r in EDIT_ACTIONS).get(a, a.title())).action = a
    layout.separator()
    layout.label(text='Edit')
    grid(('EXTRUDE', 'KNIFE', 'LOOPCUT', 'FILL', 'GRID_FILL', 'BRIDGE'))
    layout.label(text='Merge')
    grid(('MERGE_CENTER', 'COLLAPSE', 'MERGE_DIST'))
    layout.label(text='Clean Up')
    grid(('DISSOLVE', 'DELETE', 'FLIP'))
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    g.operator('mch.mretopo_edit', text='Poly Build').action = 'POLYBUILD'
    g.operator('mch.mretopo_edit', text='Relax').action = 'RELAX'
    g.operator('mch.mretopo_edit', text='Snap').action = 'SNAP'
    layout.separator()
    r = layout.row(align=True)
    r.operator('mch.mretopo_edit', text='Object Mode' if low is not None and low.mode == 'EDIT' else 'Edit Mode',
               icon='EDITMODE_HLT').action = 'MODE'
    r = layout.row(align=True)
    r.scale_y = 1.3
    r.operator('mch.mretopo_finish', text='Finish', icon='CHECKMARK')
    if low is not None:
        layout.label(text=f'{low.name}: {len(low.data.polygons)} faces')


class MCH_OT_mretopo_menu(bpy.types.Operator):
    """Right click in the Retopo scene: the Retopo menu"""
    bl_idname = 'mch.mretopo_menu'
    bl_label = 'Retopo Menu'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return in_scene(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        bpy.ops.wm.call_panel(name=MCH_PT_mretopo_menu.bl_idname, keep_open=False)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.wm.call_panel(name=MCH_PT_mretopo_menu.bl_idname, keep_open=False)
        return {'FINISHED'}


def draw_button(layout, context):
    """The Manual Retopo button (the Retopo + Bake box)."""
    r = layout.row(align=True)
    r.scale_y = 1.2
    if in_scene(context):
        r.operator('mch.mretopo_finish', text='Finish Manual Retopo', icon='CHECKMARK')
    else:
        r.operator('mch.mretopo_start', text='Manual Retopo (draw it)', icon='GREASEPENCIL')


CLASSES = (MCH_PG_mretopo, MCH_OT_mretopo_draw, MCH_OT_mretopo_start, MCH_OT_mretopo_finish, MCH_OT_mretopo_edit,
           MCH_OT_mretopo_lines, MCH_PT_mretopo_menu, MCH_OT_mretopo_menu)
_keymaps = []


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_mretopo = bpy.props.PointerProperty(type=MCH_PG_mretopo)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        for name in ('Object Mode', 'Mesh'):
            km = kc.keymaps.new(name=name, space_type='EMPTY')
            _keymaps.append((km, km.keymap_items.new('mch.mretopo_menu', 'RIGHTMOUSE', 'PRESS')))


def unregister():
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except Exception:            # a stale item (key configuration rebuilt)
            pass
    _keymaps.clear()
    if _DRAW['handle'] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW['handle'], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW['handle'] = None
    try:
        del bpy.types.Scene.mch_mretopo
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
