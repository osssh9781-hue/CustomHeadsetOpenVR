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
MAX_UNDO = 30                  # Ctrl+Z steps kept while drawing
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


def _inside(poly, pts):
    """Which of the points ``pts`` (n, 2) lie inside the closed polygon ``poly`` (m, 2)."""
    x, y = pts[:, 0][:, None], pts[:, 1][:, None]
    a, b = poly, np.roll(poly, -1, axis=0)
    cross = ((a[:, 1] <= y) != (b[:, 1] <= y))
    t = (y - a[:, 1]) / np.where(np.abs(b[:, 1] - a[:, 1]) > 1e-12, b[:, 1] - a[:, 1], 1e-12)
    xs = a[:, 0] + t * (b[:, 0] - a[:, 0])
    return ((cross & (x < xs)).sum(1) % 2) == 1


def border_loops(low):
    """Every closed border loop of the low: [[vertex index ...]]."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(low.data)
    loops = _loops(bm)
    bm.free()
    return loops


def _loops(bm):
    edges = [e for e in bm.edges if e.is_boundary]
    nxt = {}
    for e in edges:
        a, b = e.verts
        nxt.setdefault(a.index, []).append(b.index)
        nxt.setdefault(b.index, []).append(a.index)
    seen, loops = set(), []
    for start in list(nxt):
        if start in seen or len(nxt[start]) != 2:
            continue
        loop, prev, cur = [start], None, start
        seen.add(start)
        while True:
            options = [v for v in nxt[cur] if v != prev]
            if not options:
                break
            prev, cur = cur, options[0]
            if cur == start:
                break
            if cur in seen or len(nxt.get(cur, ())) != 2:
                loop = None
                break
            seen.add(cur)
            loop.append(cur)
        if loop and len(loop) >= 3:
            loops.append(loop)
    return loops


def holes(low):
    """The low's holes: [[vertex index ...] (a closed border loop)] - every border loop but the longest of its piece
    (that one is the piece's outside)."""
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(low.data)
    bm.verts.ensure_lookup_table()
    loops = _loops(bm)
    # the piece each loop is on (faces linked), its outside = its longest loop
    piece, k = {}, 0
    for f in bm.faces:
        if f.index in piece:
            continue
        stack = [f]
        piece[f.index] = k
        while stack:
            g = stack.pop()
            for e in g.edges:
                for h in e.link_faces:
                    if h.index not in piece:
                        piece[h.index] = k
                        stack.append(h)
        k += 1
    co = [v.co.copy() for v in bm.verts]
    of_loop = []
    for loop in loops:
        f = next(iter(bm.verts[loop[0]].link_faces), None)
        length = sum((co[loop[i]] - co[loop[i - 1]]).length for i in range(len(loop)))
        of_loop.append((piece.get(f.index, -1) if f is not None else -1, length))
    bm.free()
    longest = {}
    for i, (pc, ln) in enumerate(of_loop):
        if pc not in longest or ln > of_loop[longest[pc]][1]:
            longest[pc] = i
    return [loop for i, loop in enumerate(loops) if longest.get(of_loop[i][0]) != i]


def fill_holes(context, scene, poly, view):
    """0.24.334 (user: "중앙에 난 빵꾸는 내가 라쏘로 동그라미 치면 메꿔지게") the low's holes inside the lasso ``poly``
    (pixels on the screen ``view``) filled: 4 points a quad, an even ring a grid, else filled and made quads where it
    can; the new points put on the model.  Returns the holes filled."""
    low = low_of(scene)
    if low is None or not len(low.data.polygons):
        return 0
    poly = np.asarray(poly, float)
    M = low.matrix_world
    co = np.array([M @ v.co for v in low.data.vertices])
    xy, w = _screen(co, view)
    chosen = [loop for loop in holes(low) if (w[loop] > 0).all() and _inside(poly, xy[loop]).all()]
    if not chosen:
        return 0
    lay = context.view_layer
    if lay.objects.active != low:
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        low.select_set(True)
        lay.objects.active = low
    was_edit = low.mode == 'EDIT'
    if not was_edit:
        bpy.ops.object.mode_set(mode='EDIT')
    import bmesh
    n0 = len(low.data.vertices)
    done = 0
    for loop in chosen:
        bm = bmesh.from_edit_mesh(low.data)
        bm.verts.ensure_lookup_table()
        for v in bm.verts:
            v.select_set(False)
        bm.select_flush(False)
        vs = [bm.verts[i] for i in loop]
        for v in vs:
            v.select_set(True)
        bm.select_flush(True)
        bmesh.update_edit_mesh(low.data)
        try:
            if len(loop) <= 4:
                bpy.ops.mesh.edge_face_add()
            else:
                try:
                    bpy.ops.mesh.fill_grid(span=max(1, len(loop) // 4), offset=0, use_interp_simple=False)
                except RuntimeError:
                    bpy.ops.mesh.fill(use_beauty=True)
                    bpy.ops.mesh.tris_convert_to_quads()
            bpy.ops.mesh.normals_make_consistent(inside=False)
            done += 1
        except RuntimeError:
            continue
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    if len(low.data.vertices) > n0:              # (the new inside points onto the model)
        for v in low.data.vertices:
            v.select = v.index >= n0
        snap_low(context, scene, only_selected=True)
        for v in low.data.vertices:
            v.select = False
    if was_edit:
        bpy.ops.object.mode_set(mode='EDIT')
    return done


def ray_lift(scene, view, pts2d):
    """The model's surface under each screen point (pixels on ``view``): (n, 3), NaN where nothing is there."""
    ref = ref_of(scene)
    tree = _ref_tree(ref)
    Mr, Mri = ref.matrix_world, ref.matrix_world.inverted()
    Minv = np.linalg.inv(np.array(view['m'], float).reshape(4, 4))
    out = np.full((len(pts2d), 3), np.nan)
    for i, (x, y) in enumerate(pts2d):
        ndc = (x / view['w'] * 2 - 1, y / view['h'] * 2 - 1)
        a = Minv @ np.r_[ndc[0], ndc[1], -1.0, 1.0]
        b = Minv @ np.r_[ndc[0], ndc[1], 1.0, 1.0]
        a, b = a[:3] / a[3], b[:3] / b[3]
        hit = tree.ray_cast(Mri @ Vector(a), (Mri.to_3x3() @ Vector(b - a)).normalized())
        if hit[0] is not None:
            out[i] = np.array(Mr @ hit[0])
    return out


_TREES = {}


def _ref_tree(ref):
    from mathutils.bvhtree import BVHTree
    key = (ref.name, len(ref.data.vertices), len(ref.data.polygons))
    if _TREES.get('key') != key:
        me = ref.data
        _TREES['key'] = key
        _TREES['tree'] = BVHTree.FromPolygons([v.co for v in me.vertices], [p.vertices for p in me.polygons])
    return _TREES['tree']


def _grid_ring(P2, step):
    """The closed outline ``P2`` (pixels) as a ring for a grid fill: its four corners found (the points nearest the
    corners of its own box, turned to its long side), each side cut every ``step`` pixels - opposite sides the same
    count, so the quads follow the shape (a long strip: long rows, not a twist).  Returns (ring (n, 2), span)."""
    P = np.asarray(P2, float)
    if len(P) > 2 and np.linalg.norm(P[0] - P[-1]) < 1e-6:
        P = P[:-1]
    area = 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
    if area < 0:
        P = P[::-1]
    # dense, even spacing first (the corners picked from it)
    Q = np.vstack([P, P[:1]])
    s = _arc(np.c_[Q, np.zeros(len(Q))])
    m = max(64, int(s[-1] / 2))
    u = np.linspace(0, s[-1], m + 1)[:-1]
    D = np.c_[np.interp(u, s, Q[:, 0]), np.interp(u, s, Q[:, 1])]
    c = D.mean(0)
    w_, V = np.linalg.eigh(np.cov((D - c).T))
    ax = V[:, ::-1]                              # (long side first)
    loc = (D - c) @ ax
    lo, hi = loc.min(0), loc.max(0)
    corners = [np.array([lo[0], lo[1]]), np.array([hi[0], lo[1]]), np.array([hi[0], hi[1]]), np.array([lo[0], hi[1]])]
    idx = sorted({int(np.argmin(np.linalg.norm(loc - k, axis=1))) for k in corners})
    if len(idx) < 4:
        idx = [int(round(i * m / 4)) for i in range(4)]
    sides, L = [], []
    for k in range(4):
        a, b = idx[k], idx[(k + 1) % 4]
        seg = np.vstack([D[a:], D[:b + 1]]) if b <= a else D[a:b + 1]
        sides.append(seg)
        L.append(float(np.sum(np.linalg.norm(np.diff(seg, axis=0), axis=1))))
    na = max(1, int(round((L[0] + L[2]) / 2 / max(step, 2.0))))
    nb = max(1, int(round((L[1] + L[3]) / 2 / max(step, 2.0))))
    ring = []
    for k, n in zip(range(4), (na, nb, na, nb)):
        seg = sides[k]
        ss = _arc(np.c_[seg, np.zeros(len(seg))])
        uu = np.linspace(0, ss[-1], n + 1)[:-1]
        ring.extend(np.c_[np.interp(uu, ss, seg[:, 0]), np.interp(uu, ss, seg[:, 1])])
    return np.array(ring), na


def _dense(P2):
    """The closed outline ``P2`` (pixels) every ~2 pixels, CCW."""
    P = np.asarray(P2, float)
    if len(P) > 2 and np.linalg.norm(P[0] - P[-1]) < 1e-6:
        P = P[:-1]
    area = 0.5 * float(np.sum(P[:, 0] * np.roll(P[:, 1], -1) - np.roll(P[:, 0], -1) * P[:, 1]))
    if area < 0:
        P = P[::-1]
    Q = np.vstack([P, P[:1]])
    s = _arc(np.c_[Q, np.zeros(len(Q))])
    m = max(64, int(s[-1] / 2))
    u = np.linspace(0, s[-1], m + 1)[:-1]
    return np.c_[np.interp(u, s, Q[:, 0]), np.interp(u, s, Q[:, 1])]


def _cut(P, n):
    """The open polyline ``P`` (2D) cut into ``n`` even pieces: n + 1 points."""
    s = _arc(np.c_[P, np.zeros(len(P))])
    u = np.linspace(0, s[-1], n + 1)
    return np.c_[np.interp(u, s, P[:, 0]), np.interp(u, s, P[:, 1])]


def attach_plan(low, poly, view, step):
    """0.24.335 (user: "전에 만든 거랑 안 붙어? 에리어 필") the part of the outline over the low already made is the
    low's own border: (border vertex path A..B, left, top, right (pixels)) for a grid between that border and the new
    part of the outline, or None (the outline does not reach the low)."""
    tree = low_tree_of(low)
    if tree is None:
        return None
    D = _dense(poly)
    Minv = np.linalg.inv(np.array(view['m'], float).reshape(4, 4))

    def on_low(q):
        ndc = (q[0] / view['w'] * 2 - 1, q[1] / view['h'] * 2 - 1)
        a = Minv @ np.r_[ndc[0], ndc[1], -1.0, 1.0]
        b = Minv @ np.r_[ndc[0], ndc[1], 1.0, 1.0]
        a, b = a[:3] / a[3], b[:3] / b[3]
        return tree.ray_cast(Vector(a), Vector(b - a).normalized())[0] is not None
    inside = np.array([on_low(q) for q in D])
    if not inside.any() or inside.all():
        return None
    k0 = int(np.argmax(inside))                  # (start on the low: the runs off it in one piece)
    D, inside = np.roll(D, -k0, axis=0), np.roll(inside, -k0)
    runs, i = [], 0
    while i < len(D):
        if not inside[i]:
            j = i
            while j + 1 < len(D) and not inside[j + 1]:
                j += 1
            runs.append((i, j))
            i = j + 1
        else:
            i += 1
    s0, e0 = max(runs, key=lambda r: r[1] - r[0])
    if e0 - s0 < 4:
        return None
    M = low.matrix_world
    co = np.array([M @ v.co for v in low.data.vertices])
    xy, w = _screen(co, view)
    loops = border_loops(low)
    if not loops:
        return None
    bverts = np.array(sorted({v for lp in loops for v in lp}))

    def nearest_border(q):
        d = np.linalg.norm(xy[bverts] - q, axis=1)
        d[w[bverts] <= 0] = np.inf
        return int(bverts[int(np.argmin(d))])
    A = nearest_border((D[s0 - 1] + D[s0]) * 0.5)
    B = nearest_border((D[e0] + D[(e0 + 1) % len(D)]) * 0.5)
    loop = next((lp for lp in loops if A in lp and B in lp), None)
    if loop is None or A == B:
        return None
    ia, ib = loop.index(A), loop.index(B)
    fwd = loop[ia:] + loop[:ia]
    p1 = fwd[:fwd.index(B) + 1]                  # A .. B one way round
    rev = (loop[ib:] + loop[:ib])
    p2 = rev[:rev.index(A) + 1][::-1]            # A .. B the other way
    # the way round that lies along the drawn outline's inside part (inside the outline)

    def score(path):
        if len(path) <= 2:
            return 0.5
        return float(_inside(D, xy[path[1:-1]]).mean())
    path = p1 if score(p1) >= score(p2) else p2
    run = np.vstack([xy[A][None], D[s0:e0 + 1], xy[B][None]])
    m = len(path) - 1
    # how far the new part stands off the border: the rows across (k), and the run's two ends that far each
    bp = xy[path]
    dist = np.array([np.min(np.linalg.norm(bp - q, axis=1)) for q in run])
    reach = float(np.median(dist[len(dist) // 4: max(len(dist) * 3 // 4, len(dist) // 4 + 1)]))
    sr = _arc(np.c_[run, np.zeros(len(run))])
    Lrun = sr[-1]
    lk = min(max(reach, step * 0.5), Lrun / 3)
    k = max(1, int(round(lk / max(step, 2.0))))

    def piece(a, b):
        u = np.linspace(a, b, max(8, int((b - a) / 2) + 2))
        return np.c_[np.interp(u, sr, run[:, 0]), np.interp(u, sr, run[:, 1])]
    left = _cut(piece(0, lk), k)
    top = _cut(piece(lk, Lrun - lk), m)
    right = _cut(piece(Lrun - lk, Lrun), k)[::-1]
    return dict(path=path, left=left, top=top, right=right, k=k, m=m, run=run)


def _attached_fill(context, scene, low, plan_, view):
    """The grid between the low's border path and the new part of the outline (a Coons patch on the screen, put on the
    model along the line of sight).  Returns the faces made."""
    import bmesh
    path, left, top, right, k, m = (plan_[x] for x in ('path', 'left', 'top', 'right', 'k', 'm'))
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    co = np.array([M @ v.co for v in low.data.vertices])
    bxy = _screen(co[path], view)[0]
    G = _coons(bxy, np.asarray(top), np.asarray(left), np.asarray(right))
    if _folded(G) and _folded(G[:, ::-1]):      # (the grid would fold: the ring filled and made quads instead)
        return _fill_attached_ngon(context, scene, low, plan_, view)
    new_xy = G[:, 1:].reshape(-1, 2)
    P = ray_lift(scene, view, new_xy).reshape(m + 1, k, 3)
    for i in range(m + 1):                       # (off the model: as deep as the border point below it)
        for j in range(k):
            if np.isnan(P[i, j]).any():
                P[i, j] = co[path[i]]
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    me = low.data
    f0 = len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    ids = [[bm.verts[path[i]]] + [None] * k for i in range(m + 1)]
    for i in range(m + 1):
        for j in range(1, k + 1):
            ids[i][j] = bm.verts.new(Mi @ Vector(P[i, j - 1]))
    made = []
    for i in range(m):
        for j in range(k):
            try:
                made.append(bm.faces.new((ids[i][j], ids[i + 1][j], ids[i + 1][j + 1], ids[i][j + 1])))
            except ValueError:
                pass
    # the same way round as the faces next to them: two faces the same way round walk their shared edge in
    # opposite directions
    flip = None
    made_set = set(made)
    for f in made:
        for e in f.edges:
            other = [g for g in e.link_faces if g not in made_set]
            if not other:
                continue
            g = other[0]

            def walks(face, e=e):
                vs = [lp.vert for lp in face.loops]
                i = vs.index(e.verts[0])
                return vs[(i + 1) % len(vs)] == e.verts[1]
            flip = walks(f) == walks(g)
            break
        if flip is not None:
            break
    if flip:
        for f in made:
            f.normal_flip()
    elif flip is None:
        _faces_toward(bm, made, M, view)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(me.polygons) - f0


def _coons(bottom, top, left, right):
    """A grid (m+1, k+1, 2) inside four sides (2D): bottom / top m+1 points left to right, left / right k+1 points
    bottom to top (their corners shared)."""
    m, k = len(bottom) - 1, len(left) - 1
    G = np.zeros((m + 1, k + 1, 2))
    G[:, 0], G[:, k] = bottom, top
    G[0, :], G[m, :] = left, right
    c00, c10, c01, c11 = bottom[0], bottom[m], top[0], top[m]
    for i in range(1, m):
        for j in range(1, k):
            u, v = i / m, j / k
            G[i, j] = ((1 - v) * bottom[i] + v * top[i] + (1 - u) * left[j] + u * right[j]
                       - ((1 - u) * (1 - v) * c00 + u * (1 - v) * c10 + (1 - u) * v * c01 + u * v * c11))
    return G


def _folded(G):
    """Does the grid fold over itself (a quad turned the other way round on the screen)?"""
    a, b, c, d = G[:-1, :-1], G[1:, :-1], G[1:, 1:], G[:-1, 1:]
    area = 0.5 * ((a[..., 0] * b[..., 1] - b[..., 0] * a[..., 1]) + (b[..., 0] * c[..., 1] - c[..., 0] * b[..., 1])
                  + (c[..., 0] * d[..., 1] - d[..., 0] * c[..., 1]) + (d[..., 0] * a[..., 1] - a[..., 0] * d[..., 1]))
    return bool((area <= 0).any())


def _faces_toward(bm, faces, M, view):
    """``faces`` turned to face the eye of ``view`` (most of them)."""
    Minv = np.linalg.inv(np.array(view['m'], float).reshape(4, 4))
    eye = Minv @ np.array([0.0, 0.0, -1.0, 1.0])
    eye = Vector(eye[:3] / eye[3])
    bm.normal_update()
    away = sum(1 for f in faces if (M.to_3x3() @ f.normal).dot((M @ f.calc_center_median()) - eye) > 0)
    if away > len(faces) / 2:
        for f in faces:
            f.normal_flip()


def _fill_attached_ngon(context, scene, low, plan_, view):
    """An attached shape a grid would fold over: the ring (the low's border path + the new part of the outline)
    filled, the triangles made quads, the new inside relaxed."""
    import bmesh
    path, run = plan_['path'], plan_['run']
    step = max(np.linalg.norm(plan_['top'][1] - plan_['top'][0]) if len(plan_['top']) > 1 else 20.0, 4.0)
    sr = _arc(np.c_[run, np.zeros(len(run))])
    n = max(2, int(round(sr[-1] / step)))
    R = _cut(run, n)[1:-1]                       # (its ends are the border's A and B)
    P = ray_lift(scene, view, R)
    me = low.data
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    co = np.array([M @ v.co for v in me.vertices])
    for i in range(len(P)):
        if np.isnan(P[i]).any():
            P[i] = co[path[0]] if i < len(P) / 2 else co[path[-1]]
    n0, f0 = len(me.vertices), len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    new_vs = [bm.verts.new(Mi @ Vector(p)) for p in P]
    ring = [bm.verts[path[0]]] + new_vs + [bm.verts[i] for i in path[::-1][:-1]]
    es = []
    for a, b in zip(ring, ring[1:] + ring[:1]):
        e = bm.edges.get((a, b))
        es.append(e if e is not None else bm.edges.new((a, b)))
    before = set(bm.faces)
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=es)
    tris = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)]
    if not tris:
        bm.free()
        return 0
    bmesh.ops.join_triangles(bm, faces=tris, angle_face_threshold=math.radians(180),
                             angle_shape_threshold=math.radians(180))
    made = [f for f in bm.faces if f not in before]
    _faces_toward(bm, made, M, view)
    bm.to_mesh(me)
    bm.free()
    me.update()
    relax_low(scene, set(range(n0, len(me.vertices))), iterations=20, view=view)
    return len(me.polygons) - f0


def area_fill(context, scene, poly, view, size_px=40, tol=None):
    """0.24.334 (user: "그냥 내가 영역을 그리면 거기 내부를 쿼드로 채워 주는 모드도") the outline ``poly`` (pixels on
    ``view``) filled with quads about ``size_px`` across.  0.24.335 (user, a fill twisted into a fan: "꼬일 때가 있는데")
    our own grid: the outline's four sides (its corners found by its shape, opposite sides the same count), the inside
    a Coons patch on the screen - no twist - then put on the model along the line of sight and relaxed; an outline that
    would fold the grid (a deep L) is filled and made quads instead.  Over the low made already: joined to its border
    (``attach_plan``); else points of the outline by the low's points become them.  Returns the faces made."""
    import bmesh
    low = low_of(scene)
    if low is None:
        return 0
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    if len(low.data.polygons):                  # 0.24.335 drawn over the low made already: joined to its border
        pl = attach_plan(low, poly, view, size_px)
        if pl is not None:
            return _attached_fill(context, scene, low, pl, view)
    ring2, na = _grid_ring(poly, size_px)
    nb = len(ring2) // 2 - na
    if nb < 1:
        return 0
    ring_c = np.vstack([ring2, ring2[:1]])
    bottom = ring_c[0:na + 1]
    right = ring_c[na:na + nb + 1]
    top = ring_c[na + nb:2 * na + nb + 1][::-1]
    left = ring_c[2 * na + nb:2 * na + 2 * nb + 1][::-1]
    G = _coons(bottom, top, left, right)
    me = low.data
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    n0, f0 = len(me.vertices), len(me.polygons)
    if _folded(G):
        return _fill_ngon(context, scene, low, ring2, view, tol)
    P = ray_lift(scene, view, G.reshape(-1, 2)).reshape(G.shape[0], G.shape[1], 3)
    ok = ~np.isnan(P).any(2)
    if ok.mean() < 0.6:
        return 0
    if not ok.all():                             # (a point off the model: as deep as the nearest one on it)
        good = np.argwhere(ok)
        for i, j in np.argwhere(~ok):
            g = good[np.argmin(np.abs(good - (i, j)).sum(1))]
            P[i, j] = P[g[0], g[1]]
    bm = bmesh.new()
    bm.from_mesh(me)
    V = [[bm.verts.new(Mi @ Vector(P[i, j])) for j in range(G.shape[1])] for i in range(G.shape[0])]
    made = []
    for i in range(G.shape[0] - 1):
        for j in range(G.shape[1] - 1):
            made.append(bm.faces.new((V[i][j], V[i + 1][j], V[i + 1][j + 1], V[i][j + 1])))
    _faces_toward(bm, made, M, view)
    ring_vs = set(V[i][0] for i in range(G.shape[0])) | set(V[i][-1] for i in range(G.shape[0])) \
        | set(V[0]) | set(V[-1])
    if n0:
        _weld_to_old(bm, n0, ring_vs, tol if tol is not None else size_px_world(P) * 0.35)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(me.polygons) - f0


def size_px_world(P):
    """The mean spacing of the grid points ``P`` (m, k, 3)."""
    d = np.linalg.norm(np.diff(P, axis=0), axis=2)
    return float(np.mean(d)) if d.size else 0.0


def _weld_to_old(bm, n0, ring_vs, wtol):
    from mathutils.kdtree import KDTree
    import bmesh
    bm.verts.ensure_lookup_table()
    kd = KDTree(n0)
    for v in bm.verts[:n0]:
        kd.insert(v.co, v.index)
    kd.balance()
    weld = {}
    for v in ring_vs:
        if v.is_valid:
            _c, j, d = kd.find(v.co)
            if j is not None and d < wtol:
                weld[v] = bm.verts[j]
    if weld:
        bmesh.ops.weld_verts(bm, targetmap=weld)


def _fill_ngon(context, scene, low, ring2, view, tol):
    """A shape a grid would fold over (a deep L): the ring filled, the triangles made quads, the inside relaxed."""
    import bmesh
    ring = ray_lift(scene, view, ring2)
    ok = ~np.isnan(ring).any(1)
    if ok.sum() < len(ring) * 0.6:
        return 0
    idx = np.nonzero(ok)[0]
    for i in np.nonzero(~ok)[0]:
        ring[i] = ring[idx[np.argmin(np.abs(idx - i))]]
    me = low.data
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    n0, f0 = len(me.vertices), len(me.polygons)
    bm = bmesh.new()
    bm.from_mesh(me)
    vs = [bm.verts.new(Mi @ Vector(p)) for p in ring]
    vs_set = set(vs)
    es = [bm.edges.new((a, b)) for a, b in zip(vs, vs[1:] + vs[:1])]
    res = bmesh.ops.triangle_fill(bm, use_beauty=True, use_dissolve=False, edges=es)
    tris = [f for f in res['geom'] if isinstance(f, bmesh.types.BMFace)]
    bmesh.ops.join_triangles(bm, faces=tris, angle_face_threshold=math.radians(180),
                             angle_shape_threshold=math.radians(180))
    made = [f for f in bm.faces if f.is_valid and all(v in vs_set for v in f.verts)]
    _faces_toward(bm, made, M, view)
    if n0:
        _weld_to_old(bm, n0, set(vs), tol if tol is not None else float(np.median(
            np.linalg.norm(np.diff(ring, axis=0), axis=1))) * 0.35)
    bm.to_mesh(me)
    bm.free()
    me.update()
    relax_low(scene, set(range(n0, len(me.vertices))), iterations=20, view=view)
    return len(me.polygons) - f0


def is_lasso(P2):
    """Is the stroke ``P2`` (pixels) a closed loop - its end back by its start, and round something?"""
    if len(P2) < 8:
        return False
    span = P2.max(0) - P2.min(0)
    return bool(np.linalg.norm(P2[-1] - P2[0]) < PICK_PX * 2.5 and span.min() > PICK_PX * 3)


def relax_low(scene, only=None, iterations=40, strength=0.5, view=None):
    """0.24.335 (user, a fill twisted into a fan: "스무스 같은 거 만들어서 풀어지게") Relax: the low's inside points
    (``only``: these vertex indices) moved to the middle of their neighbours again and again - the border points stay
    - each time put back on the model: a bunched, twisted grid spreads out even.  Returns the points moved."""
    low, ref = low_of(scene), ref_of(scene)
    if low is None or ref is None or not len(low.data.vertices):
        return 0
    if low.mode == 'EDIT':                       # (Edit Mode: its own copy of the mesh would cover the change)
        low.update_from_editmode()
        bpy.ops.object.mode_set(mode='OBJECT')
        try:
            return relax_low(scene, only, iterations, strength, view)
        finally:
            bpy.ops.object.mode_set(mode='EDIT')
    import bmesh
    me = low.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    pinned = {v.index for v in bm.verts if v.is_boundary or not v.link_faces}
    nbr = [[e.other_vert(v).index for e in v.link_edges] for v in bm.verts]
    bm.free()
    move = [i for i in range(len(nbr)) if i not in pinned and nbr[i] and (only is None or i in only)]
    if not move:
        return 0
    M, Mi = low.matrix_world, low.matrix_world.inverted()
    co = np.array([M @ v.co for v in me.vertices])
    tree = _ref_tree(ref)
    Mr, Mri = ref.matrix_world, ref.matrix_world.inverted()
    me.update()
    nrm = np.array([(M.to_3x3() @ v.normal).normalized() for v in me.vertices])
    reach = float(np.median([np.linalg.norm(co[i] - co[nbr[i]], axis=1).mean() for i in move])) * 2

    def onto(p, n):
        """``p`` onto the model along its own normal (the nearer hit, either way) - not the nearest surface, which
        can be inside a groove next to it."""
        best = None
        for d in (n, -n):
            hit = tree.ray_cast(Mri @ Vector(p), (Mri.to_3x3() @ Vector(d)).normalized(), reach)
            if hit[0] is not None:
                q = np.array(Mr @ hit[0])
                if best is None or np.linalg.norm(q - p) < np.linalg.norm(best - p):
                    best = q
        if best is None:
            hit = tree.find_nearest(Mri @ Vector(p))
            best = np.array(Mr @ hit[0]) if hit[0] is not None else p
        return best
    if view is not None:                        # 0.24.335 as seen: evened out on the screen, back on the model along
        xy, w = _screen(co, view)               # the line of sight (a groove beside a point does not pull it in);
        seen = ray_lift(scene, view, xy)        # only the points seen there (not hidden, not round the back)
        vis = set(i for i in move if w[i] > 0 and not np.isnan(seen[i]).any()
                  and np.linalg.norm(seen[i] - co[i]) < reach * 0.5)
        if vis:
            q = xy.copy()
            mv = [i for i in move if i in vis]
            for _it in range(iterations):
                new = q.copy()
                for i in mv:
                    new[i] = q[i] * (1 - strength) + q[nbr[i]].mean(0) * strength
                q = new
            lifted = ray_lift(scene, view, q[mv])
            for i, p_ in zip(mv, lifted):
                if not np.isnan(p_).any():
                    co[i] = p_
            for i in mv:
                me.vertices[i].co = Mi @ Vector(co[i])
            me.update()
            return len(mv)
        return 0
    for _it in range(iterations):
        new = co.copy()
        for i in move:
            new[i] = co[i] * (1 - strength) + co[nbr[i]].mean(0) * strength
        for i in move:
            new[i] = onto(new[i], nrm[i])
        co = new
    for i in move:
        me.vertices[i].co = Mi @ Vector(co[i])
    me.update()
    return len(move)


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
    mode: bpy.props.EnumProperty(name='Draw', default='GRID',
                                 items=[('GRID', 'Grid Lines', 'Lines one way and across: every closed cell a face'),
                                        ('AREA', 'Area Fill', 'Draw round an area: its inside filled with quads')])
    area_size: bpy.props.IntProperty(name='Quad Size', default=40, min=10, max=300, subtype='PIXEL',
                                     description='Area Fill: the quads about this many pixels across on the screen')


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
    face.  A loop drawn round a hole in the low fills it.  Enter: make the faces, Ctrl+Z: last line off, Shift+click: that line off, Esc: leave (lines kept)"""
    bl_idname = 'mch.mretopo_draw'
    bl_label = 'Grid Draw'
    bl_options = {'REGISTER', 'UNDO'}

    mode: bpy.props.EnumProperty(items=[('KEEP', 'As Set', ''), ('GRID', 'Grid Lines', ''), ('AREA', 'Area Fill', '')],
                                 default='KEEP', options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return in_scene(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        from mathutils.bvhtree import BVHTree
        self.cur_xy = []
        self.history = []
        if self.mode != 'KEEP':
            context.scene.mch_mretopo.mode = self.mode
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
        self._status(context)

        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _status(self, context):
        if context.scene.mch_mretopo.mode == 'AREA':
            t = ('Area Fill: draw round an area - its inside filled with quads (Quad Size)   a loop round a hole: '
                 'filled   Tab: Grid Lines   Esc: leave   right click: Retopo menu')
        else:
            t = ('Grid Lines: drag lines over the model (one way, then across)   a loop round a hole: filled   '
                 'Enter: make faces   Ctrl+Z: last line off   Shift+click: a line off   Tab: Area Fill   Esc: leave   '
                 'right click: Retopo menu')
        context.workspace.status_text_set(t)

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

    def _snap(self, context):
        """0.24.335 (user: "왜 컨트롤 Z 도 안 먹히고") the low as it is, kept for Ctrl+Z (a fill changes it while
        drawing - Blender's own undo only sees the drawing as one step)."""
        low = low_of(context.scene)
        if low is not None:
            keep = low.data.copy()
            keep.use_fake_user = False
            self.history.append(('MESH', keep.name))
            del self.history[:-MAX_UNDO]

    def _undo(self, context):
        """Ctrl+Z while drawing: the last line, or the last fill, taken back."""
        while self.history:
            kind, name = self.history.pop()
            if kind == 'LINE':
                if self.L:
                    self.L.pop()
                    self._save(context)
                    return 'line'
                continue
            keep = bpy.data.meshes.get(name)
            low = low_of(context.scene)
            if keep is None or low is None:
                continue
            old = low.data
            low.data = keep
            if old.users == 0:
                bpy.data.meshes.remove(old)
            self._preview(context)
            if context.area is not None:
                context.area.tag_redraw()
            return 'fill'
        if self.L:                              # (lines from before this drawing)
            self.L.pop()
            self._save(context)
            return 'line'
        return None

    def _drop_last(self):
        if self.history and self.history[-1][0] == 'MESH':
            me = bpy.data.meshes.get(self.history.pop()[1])
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)

    def _drop_history(self):
        for kind, name in getattr(self, 'history', []):
            if kind == 'MESH':
                me = bpy.data.meshes.get(name)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        self.history = []

    def _end(self, context):
        self._drop_history()
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
                    self.cur_xy.append(xy)
                    self.last_xy = xy
                    w, tol = self.hit(context, xy)
                    if w is not None:
                        self.cur.append(tuple(w))
                        self.tols.append(tol or 0.0)
                    context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                P2 = np.array(self.cur_xy + [xy], float)
                if is_lasso(P2):                     # 0.24.334 a closed loop round a hole: the hole filled (no hole
                    self._snap(context)              # inside: an ordinary line - a ring of the grid)
                    n = fill_holes(context, context.scene, P2, view_of(context.region, context.region_data))
                    if not n:
                        self._drop_last()
                    if n:
                        self.cur = None
                        self._preview(context)
                        context.area.tag_redraw()
                        self.report({'INFO'}, f'{n} hole(s) filled')
                        return {'RUNNING_MODAL'}
                if context.scene.mch_mretopo.mode == 'AREA' and len(P2) >= 8:
                    self.cur = None                  # 0.24.334 Area Fill: the outline's inside, quads
                    self._snap(context)
                    n = area_fill(context, context.scene, P2, view_of(context.region, context.region_data),
                                  context.scene.mch_mretopo.area_size)
                    self._preview(context)
                    context.area.tag_redraw()
                    if not n:
                        self._drop_last()
                    self.report({'INFO'} if n else {'WARNING'},
                                f'Area Fill: {n} face(s)  (Ctrl+Z: back)' if n else
                                'Area Fill: draw round an area of the model')
                    return {'RUNNING_MODAL'}
                if len(self.cur) >= 2:
                    tol = float(np.median([t for t in self.tols if t] or [0.0]))
                    self.L.append((tol, np.array(self.cur), view_of(context.region, context.region_data)))
                    self.history.append(('LINE', ''))
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
            w, tol = self.hit(context, xy)                # (off the model too: a loop round a hole may start there)
            self.cur, self.tols, self.last_xy = ([tuple(w)], [tol or 0.0], xy) if w is not None else ([], [], xy)
            self.cur_xy = [xy]
            return {'RUNNING_MODAL'}
        if event.type == 'TAB' and event.value == 'PRESS':     # 0.24.334 Grid Lines <-> Area Fill
            st = context.scene.mch_mretopo
            st.mode = 'AREA' if st.mode == 'GRID' else 'GRID'
            self._status(context)
            return {'RUNNING_MODAL'}
        if event.type == 'Z' and event.value == 'PRESS' and (event.ctrl or event.oskey):
            what = self._undo(context)
            self.report({'INFO'}, {'line': 'Undo: the last line', 'fill': 'Undo: the last fill'}.get(what, 'Nothing to undo'))
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
                                      ('RELAX', 'Relax', 'Untwist: the inside points spread out evenly, on the model - '
                                                         'the border stays (Edit Mode: the selected points; else all)'),
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
        was_edit = low.mode == 'EDIT'
        if low.mode != 'EDIT':
            bpy.ops.object.mode_set(mode='EDIT')
        try:
            if self.action == 'POLYBUILD':
                bpy.ops.wm.tool_set_by_id(name='builtin.poly_build')
            elif self.action == 'RELAX':            # 0.24.335 untwist: the inside points spread out, on the model
                bpy.ops.object.mode_set(mode='OBJECT')
                sel = {v.index for v in low.data.vertices if v.select}
                rv = context.region_data if context.area is not None and context.area.type == 'VIEW_3D' else None
                n = relax_low(context.scene, sel if was_edit and sel else None,
                              view=view_of(context.region, rv) if rv is not None else None)
                bpy.ops.object.mode_set(mode='EDIT' if was_edit else 'OBJECT')
                self.report({'INFO'}, f'Relax: {n} point(s) spread out (the border stays)')
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
    r.operator('mch.mretopo_draw', text='Grid Draw', icon='GREASEPENCIL').mode = 'GRID'
    r.operator('mch.mretopo_draw', text='Area Fill', icon='MESH_GRID').mode = 'AREA'
    r = col.row(align=True)
    r.prop(st, 'cuts')
    r.prop(st, 'area_size')
    r = col.row(align=True)
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
