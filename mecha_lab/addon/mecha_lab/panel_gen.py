"""Panel generator shared by Face Extract (Basic) and Armor Sculpt.

Not an Extrude + Bevel modifier chain: the solid is BUILT from a cross-section
profile, so chamfer width, angle and depth, the chamfer direction and the
outer (base) edge are controlled independently and exactly.

Input: a copy of the selected face region (any curvature, holes allowed) and
the surrounding surface (for projecting rings that go outward).

    top cap  - the region, shrunk to make room for the edge band, lifted along
               the surface normals by the height field
    top band - rings following the TOP EDGE profile (chamfer / bevel fillets)
    wall     - the side wall down to the base
    bottom   - rings following the OUTER (BASE) EDGE profile + bottom cap
               (omitted when Thickness > 0: the part becomes a shell, closed
               by a Solidify modifier)

Every ring has exactly one vertex per boundary vertex, so the result is built
from index tables and is always a closed, consistently oriented solid.

Cross-section coordinates per boundary vertex ("column"): ``s`` = distance
INTO the region along the surface (negative = outward), ``z`` = height above
the surface (plus Surface Offset).

Armor Sculpt adds a local N/E/S/W frame (average normal + principal axis,
user rotation / scale / offset / mirror): every edge setting and the top
height are blended between the four directions with a smooth partition of
unity, and a centre-line ridge field (6 presets) changes the real top
heights.  Pure functions here; Blender data handling is in face_extract.py.
"""
from __future__ import annotations

import heapq
import math

import bmesh
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

DIRS = ('N', 'E', 'S', 'W')
DIR_ANGLE = {'E': 0.0, 'N': math.pi / 2, 'W': math.pi, 'S': 1.5 * math.pi}


class PanelError(Exception):
    pass


# =============================================================================
# Small math helpers
# =============================================================================


def dir_weights(theta):
    """Smooth partition of unity over the 4 local directions (sum = 1)."""
    c, s = math.cos(theta), math.sin(theta)
    return {'E': max(c, 0.0) ** 2, 'W': max(-c, 0.0) ** 2, 'N': max(s, 0.0) ** 2, 'S': max(-s, 0.0) ** 2}


def smoothstep(t):
    t = min(1.0, max(0.0, t))
    return t * t * (3.0 - 2.0 * t)


def smooth_max(a, b, k):
    """Polynomial smooth maximum (k = blend width, 0 = hard max)."""
    if k <= 1e-9:
        return max(a, b)
    h = max(k - abs(a - b), 0.0) / k
    return max(a, b) + h * h * k * 0.25


def _resample(points, n):
    """Resample a polyline to ``n`` points by arc length (keeps both ends)."""
    if n <= 1 or len(points) == 1:
        return [points[0]] * max(n, 1) if n > 1 and len(points) == 1 else list(points[:1])
    acc = [0.0]
    for i in range(1, len(points)):
        acc.append(acc[-1] + math.dist(points[i - 1], points[i]))
    total = acc[-1]
    if total < 1e-12:
        return [points[0]] * n
    out, j = [], 0
    for k in range(n):
        t = total * k / (n - 1)
        while j < len(acc) - 2 and acc[j + 1] < t:
            j += 1
        span = acc[j + 1] - acc[j] or 1.0
        f = (t - acc[j]) / span
        a, b = points[j], points[j + 1]
        out.append((a[0] + (b[0] - a[0]) * f, a[1] + (b[1] - a[1]) * f))
    return out


def _fillet(prev_pt, corner, next_pt, size, segments, profile):
    """Rounded corner points between segments prev->corner->next.
    profile 0.5 = round, 1 = boxy, 0 = straight chamfer."""
    a = Vector((corner[0] - prev_pt[0], corner[1] - prev_pt[1]))
    b = Vector((next_pt[0] - corner[0], next_pt[1] - corner[1]))
    la, lb = a.length, b.length
    if size <= 1e-9 or la < 1e-9 or lb < 1e-9 or segments < 1:
        return [corner]
    t = min(size, la * 0.5, lb * 0.5)
    a.normalize()
    b.normalize()
    p1 = Vector(corner) - a * t
    p2 = Vector(corner) + b * t
    mid = (p1 + p2) * 0.5
    ctrl = mid + (Vector(corner) - mid) * (2.0 * max(0.0, min(1.0, profile)))
    pts = []
    for k in range(segments + 1):
        u = k / segments
        q = p1 * (1 - u) ** 2 + ctrl * (2 * u * (1 - u)) + p2 * u * u
        pts.append((q.x, q.y))
    return pts


def edge_profile(width, depth, direction='IN', bevel=0.0, segments=0, profile=0.5, wall_room=1e9):
    """Cross-section of an edge as (s, z) points from the wall end to the cap
    end.  The flat face is z = 0 for s >= end, the wall is at the first point's
    ``s`` going to z -> -inf.  Chamfer: horizontal ``width`` x vertical
    ``depth``; IN cuts into the face, OUT flares outward (wall moves out)."""
    width = max(0.0, width)
    depth = max(0.0, min(depth, wall_room * 0.95))
    if direction == 'OUT' and width > 0 and depth > 0:
        corners = [(-width, -depth), (0.0, 0.0)]
        wall_s = -width
    elif width > 0 and depth > 0:
        corners = [(0.0, -depth), (width, 0.0)]
        wall_s = 0.0
    else:
        corners = [(0.0, 0.0)]
        wall_s = 0.0
    far = 1e3
    chain = [(wall_s, -far)] + corners + [(corners[-1][0] + far, 0.0)]
    bevel = max(0.0, bevel)
    if bevel > 0 and segments >= 1:
        # a fillet on the wall side may not run below the available wall height
        out = [chain[0]]
        for k in range(1, len(chain) - 1):
            size = bevel
            if k == 1:
                size = min(bevel, max(wall_room * 0.9 - depth, 0.0))
            out.extend(_fillet(chain[k - 1], chain[k], chain[k + 1], size, segments, profile))
        out.append(chain[-1])
        chain = out
    pts = chain[1:-1]
    return pts


# =============================================================================
# Region analysis
# =============================================================================


def boundary_loops(bm, faces):
    """Ordered boundary loops of a face set (region on the LEFT of each loop
    w.r.t. the face normals).  Returns lists of BMVerts."""
    fset = set(faces)
    nxt = {}
    for f in faces:
        for lp in f.loops:
            e = lp.edge
            if sum(1 for lf in e.link_faces if lf in fset) == 1:
                a, b = lp.vert, lp.link_loop_next.vert
                if a in nxt:
                    raise PanelError('The selection touches itself at a single vertex; select a cleaner region.')
                nxt[a] = b
    loops, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        loop, v = [], start
        while v not in seen:
            seen.add(v)
            loop.append(v)
            v = nxt.get(v)
            if v is None:
                raise PanelError('Open boundary could not be followed.')
        loops.append(loop)
    if not loops:
        raise PanelError('The selection has no boundary (a closed surface cannot be extracted as a panel).')
    return loops


def region_frame(verts, faces):
    """Centre, unit normal, tangent T, bitangent B, radius."""
    area_n = Vector()
    cen = Vector()
    tot = 0.0
    for f in faces:
        a = f.calc_area()
        area_n += f.normal * a
        cen += f.calc_center_median() * a
        tot += a
    if tot <= 1e-12 or area_n.length < 1e-12:
        raise PanelError('Selected faces have no area.')
    cen /= tot
    n = area_n.normalized()
    # principal axis of the projected vertices
    pts = [(v.co - cen) - n * (v.co - cen).dot(n) for v in verts]
    sxx = sum(p.x * p.x for p in pts)
    syy = sum(p.y * p.y for p in pts)
    szz = sum(p.z * p.z for p in pts)
    sxy = sum(p.x * p.y for p in pts)
    sxz = sum(p.x * p.z for p in pts)
    syz = sum(p.y * p.z for p in pts)
    cov = Matrix(((sxx, sxy, sxz), (sxy, syy, syz), (sxz, syz, szz)))
    t = Vector((1.0, 0.3, 0.1))
    for _ in range(40):                  # power iteration
        t = cov @ t
        t -= n * t.dot(n)
        if t.length < 1e-12:
            break
        t.normalize()
    if t.length < 1e-6:
        t = n.orthogonal()
    t = (t - n * t.dot(n)).normalized()
    b = n.cross(t).normalized()
    radius = max((p.length for p in pts), default=1.0) or 1.0
    return cen, n, t, b, radius


def distance_from_boundary(bm_verts, boundary_set):
    """Dijkstra edge-length distance of every vertex to the boundary."""
    dist = {v: (0.0 if v in boundary_set else math.inf) for v in bm_verts}
    heap = [(0.0, id(v), v) for v in boundary_set]
    heapq.heapify(heap)
    vset = set(bm_verts)
    while heap:
        d, _i, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for e in v.link_edges:
            w = e.other_vert(v)
            if w not in vset:
                continue
            nd = d + e.calc_length()
            if nd < dist[w]:
                dist[w] = nd
                heapq.heappush(heap, (nd, id(w), w))
    return dist


# =============================================================================
# Centre line (ridge) guide
# =============================================================================

PRESETS = ('STRAIGHT', 'CROSS', 'Y', 'X', 'S', 'Z')


def _card(theta, p, name):
    """Blend a per-direction value (N/E/S/W) at angle theta."""
    w = dir_weights(theta)
    return sum(w[d] * getattr(p, f'cl_{d.lower()}_{name}') for d in DIRS)


def guide_branches(p):
    """Centre-line polylines in normalized local units (radius = 1) with a
    width factor per polyline: [(points, width_factor)]."""
    preset = p.cl_preset
    out = []

    def ray(angle):
        L = _card(angle, p, 'length')
        W = _card(angle, p, 'width')
        return ([(0.0, 0.0), (math.cos(angle) * L, math.sin(angle) * L)], W)
    if preset == 'STRAIGHT':
        out = [ray(math.pi / 2), ray(1.5 * math.pi)]
    elif preset == 'CROSS':
        out = [ray(a) for a in (0.0, math.pi / 2, math.pi, 1.5 * math.pi)]
    elif preset == 'Y':
        spread = p.cl_branch_angle
        out = [ray(1.5 * math.pi), ray(math.pi / 2 - spread), ray(math.pi / 2 + spread)]
    elif preset == 'X':
        spread = p.cl_branch_angle
        out = [ray(a) for a in (spread, math.pi - spread, math.pi + spread, 2 * math.pi - spread)]
    elif preset == 'S':
        ln, ls = p.cl_n_length, p.cl_s_length
        be, bw = p.cl_e_length * p.cl_curvature, p.cl_w_length * p.cl_curvature
        p0, p1, p2, p3 = Vector((0, -ls)), Vector((be, -ls / 3)), Vector((-bw, ln / 3)), Vector((0, ln))
        pts = []
        for k in range(33):
            u = k / 32
            q = p0 * (1 - u) ** 3 + p1 * 3 * u * (1 - u) ** 2 + p2 * 3 * u * u * (1 - u) + p3 * u ** 3
            pts.append((q.x, q.y))
        out = [(pts, 0.5 * (p.cl_n_width + p.cl_s_width))]
    elif preset == 'Z':
        ln, ls, le, lw = p.cl_n_length, p.cl_s_length, p.cl_e_length, p.cl_w_length
        out = [([(-lw, ln), (le, ln)], p.cl_n_width), ([(le, ln), (-lw, -ls)], 0.5 * (p.cl_e_width + p.cl_w_width)),
               ([(-lw, -ls), (le, -ls)], p.cl_s_width)]
    if p.cl_symmetry:
        out = out + [([(-x, y) for x, y in pts], w) for pts, w in out]
    # global transform (independent of the directional lengths)
    rot = p.cl_rotation
    c, s = math.cos(rot), math.sin(rot)
    res = []
    for pts, w in out:
        tp = []
        for x, y in pts:
            x, y = x * p.cl_scale_x, y * p.cl_scale_y
            tp.append((x * c - y * s + p.cl_offset_x, x * s + y * c + p.cl_offset_y))
        res.append((tp, w))
    return res


def _seg_dist(px, py, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L2 = dx * dx + dy * dy
    t = 0.0 if L2 < 1e-18 else max(0.0, min(1.0, ((px - ax) * dx + (py - ay) * dy) / L2))
    return math.hypot(px - (ax + dx * t), py - (ay + dy * t))


def ridge_profile(kind, t, p):
    """Normalized ridge height (signed) at t = distance / half width."""
    if t >= 1.0:
        return 0.0
    sharp = max(0.0, p.cl_sharpness)
    rnd = max(0.0, min(1.0, p.cl_roundness))
    slope = max(0.02, min(0.9, 0.35 / max(math.tan(max(p.cl_angle, 0.05)), 0.05)))
    if kind == 'SHARP':
        base = (1.0 - t) ** (1.0 + sharp * 3.0)
        return base * (1 - rnd) + (1.0 - t * t) * rnd
    if kind == 'ROUND':
        return math.sqrt(max(0.0, 1.0 - t * t))
    if kind == 'FLAT':
        plateau = max(0.05, 1.0 - slope)
        return 1.0 if t <= plateau else smoothstep((1.0 - t) / max(1.0 - plateau, 1e-6)) * (1 - rnd) + \
            (1.0 - (t - plateau) / max(1.0 - plateau, 1e-6)) * rnd
    if kind == 'BOX':
        edge = 1.0 - slope * 0.5
        if t <= edge:
            return 1.0
        f = (1.0 - t) / max(1.0 - edge, 1e-6)
        return f * (1 - rnd) + smoothstep(f) * rnd
    if kind == 'GROOVE':
        return -math.sqrt(max(0.0, 1.0 - t * t)) * (1 - rnd) - (1.0 - t) * rnd
    if kind == 'SPLIT':
        return -((1.0 - t) ** (1.0 + sharp * 2.0)) * 2.0      # narrow deep V: panels look separated
    return 0.0


def ridge_value(u, v, branches, p, radius):
    """Signed ridge height at normalized (u, v)."""
    if p.cl_preset == 'NONE' or not branches:
        return 0.0
    kind = p.ridge_profile
    k = p.transition_smoothness * 0.5
    best = None
    for pts, wfac in branches:
        hw = max(1e-4, p.cl_width * wfac)
        d = min(_seg_dist(u, v, pts[i], pts[i + 1]) for i in range(len(pts) - 1))
        val = ridge_profile(kind, d / hw, p)
        if best is None:
            best = val
        elif val >= 0 or best >= 0:
            best = smooth_max(best, val, k) if val >= 0 and best >= 0 else (val if abs(val) > abs(best) else best)
        else:
            best = min(best, val)
    h = (best or 0.0) * p.cl_height * p.cl_strength
    return -h if p.cl_invert else h


# =============================================================================
# Parameters per column / vertex
# =============================================================================


def _blend(p, theta, name):
    w = dir_weights(theta)
    return sum(w[d] * getattr(p, f'{d.lower()}_{name}') for d in DIRS)


def chamfer_wd(width, angle, depth, mode):
    """(width, depth) of a chamfer from any two of width / angle / depth."""
    if mode == 'WIDTH_DEPTH':
        return width, depth
    if mode == 'DEPTH_ANGLE':
        return (depth / math.tan(angle) if math.tan(angle) > 1e-6 else 0.0), depth
    return width, width * math.tan(max(0.0, min(angle, math.radians(89.0))))


def column_params(p, theta, armor):
    """Edge parameters of one boundary column (top + base edge)."""
    if armor:
        thick = _blend(p, theta, 'thickness')
        cw = _blend(p, theta, 'chamfer_width')
        ca = _blend(p, theta, 'chamfer_angle')
        bw = _blend(p, theta, 'bevel_width')
        w = dir_weights(theta)
        seg = max(int(round(getattr(p, f'{d.lower()}_bevel_segments'))) for d in DIRS if w[d] > 0.02)
        cw, cd = chamfer_wd(cw, ca, 0.0, 'WIDTH_ANGLE')
        return {'height': thick, 'cw': cw, 'cd': cd, 'dir': 'IN', 'bw': bw, 'seg': seg,
                'prof': p.bevel_profile, 'ow': p.outer_chamfer_width,
                'od': p.outer_chamfer_width * math.tan(p.outer_chamfer_angle), 'obw': p.outer_bevel_width,
                'oseg': p.bevel_segments}
    cw, cd = chamfer_wd(p.chamfer_width, p.chamfer_angle, p.chamfer_depth, p.chamfer_mode)
    return {'height': p.extract_height, 'cw': cw, 'cd': cd, 'dir': p.chamfer_direction,
            'bw': p.bevel_width, 'seg': p.bevel_segments, 'prof': p.bevel_profile,
            'ow': p.outer_chamfer_width, 'od': p.outer_chamfer_width * math.tan(p.outer_chamfer_angle),
            'obw': p.outer_bevel_width, 'oseg': p.bevel_segments}


def directional_height(p, theta, r):
    """Armor top height: centre height blended to the per-direction edge
    thickness with per-direction slope (reach) and roundness."""
    hc = p.extract_height
    w = dir_weights(theta)
    tension = max(0.05, 1.0 + p.surface_tension)
    h = hc
    for d in DIRS:
        if w[d] <= 0:
            continue
        reach = max(0.02, min(1.0, getattr(p, f'{d.lower()}_slope')))
        rnd = max(0.0, min(1.0, getattr(p, f'{d.lower()}_roundness')))
        t = (r - (1.0 - reach)) / reach
        t = min(1.0, max(0.0, t)) ** tension
        g = t * (1 - rnd) + smoothstep(t) * rnd
        h += w[d] * (getattr(p, f'{d.lower()}_thickness') - hc) * g
    return h


# =============================================================================
# Builder
# =============================================================================


def build(region_mesh, context_mesh, p, armor=False, notes=None):
    """Return a BMesh of the panel (in the region's coordinate space)."""
    notes = notes if notes is not None else []
    bm = bmesh.new()
    bm.from_mesh(region_mesh)
    try:
        return _build(bm, context_mesh, p, armor, notes)
    except Exception:
        bm.free()
        raise


def _project_factory(context_mesh, bm_region):
    src = context_mesh if context_mesh is not None and len(context_mesh.polygons) else None
    if src is not None:
        cbm = bmesh.new()
        cbm.from_mesh(src)
        tree = BVHTree.FromBMesh(cbm)
        cbm.free()
    else:
        tree = BVHTree.FromBMesh(bm_region)

    def project(co, nrm=None):
        """Onto the surface along the normal; off the surface (outward rings
        past the mesh edge) the point stays on the tangent-plane extension."""
        if nrm is None or nrm.length < 1e-12:
            hit = tree.find_nearest(co)
            return hit[0] if hit and hit[0] is not None else co
        best = None
        for d in (nrm, -nrm):
            loc, _n, _i, dist = tree.ray_cast(co - d * 1e-6, d)
            if loc is not None and (best is None or dist < best[0]):
                best = (dist, loc)
        return best[1] if best is not None else co
    return project


def _build(bm, context_mesh, p, armor, notes):
    bm.verts.ensure_lookup_table()
    if not bm.faces:
        raise PanelError('No faces selected.')
    levels = max(0, int(p.resolution))
    if levels:
        for _ in range(levels):
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
    bm.normal_update()
    project = _project_factory(context_mesh, bm)
    faces = list(bm.faces)
    loops = boundary_loops(bm, faces)
    verts = list(bm.verts)
    cen, n_avg, t_ax, b_ax, radius = region_frame(verts, faces)
    # user rotation / mirror of the local frame (around the average normal)
    rot = getattr(p, 'dir_rotation', 0.0)
    q = Matrix.Rotation(rot, 3, n_avg)
    t_ax, b_ax = q @ t_ax, q @ b_ax
    sx = max(1e-3, getattr(p, 'dir_scale_x', 1.0))
    sy = max(1e-3, getattr(p, 'dir_scale_y', 1.0))
    ox, oy = getattr(p, 'dir_offset_x', 0.0), getattr(p, 'dir_offset_y', 0.0)
    mirror = -1.0 if getattr(p, 'dir_mirror', False) else 1.0

    def local_uv(co):
        d = co - cen
        u = (d.dot(t_ax) / radius - ox) / sx * mirror
        v = (d.dot(b_ax) / radius - oy) / sy
        return u, v

    bset = {v for lp in loops for v in lp}
    dist = distance_from_boundary(verts, bset)
    dmax = max((d for d in dist.values() if d < math.inf), default=0.0) or 1.0
    vnorm = {v: (v.normal.copy() if v.normal.length > 1e-9 else n_avg.copy()) for v in verts}
    offset = p.surface_offset
    shell = p.thickness > 1e-9
    branches = guide_branches(p) if armor else []
    trans_w = max(1e-3, getattr(p, 'transition_width', 0.25))

    # ---- columns ---------------------------------------------------------------
    columns = []                 # per loop: list of dicts
    min_inr = min((math.dist(v.co, cen) for v in bset), default=radius)
    width_cap = max(1e-5, 0.45 * min(min_inr, dmax * 2.0))
    clamp_hit = False
    for lp in loops:
        cols = []
        n = len(lp)
        for i, v in enumerate(lp):
            p0, p1, p2 = lp[i - 1].co, v.co, lp[(i + 1) % n].co
            nv = vnorm[v]
            e1, e2 = (p1 - p0), (p2 - p1)
            l1 = nv.cross(e1)
            l2 = nv.cross(e2)
            l1 = l1.normalized() if l1.length > 1e-12 else Vector()
            l2 = l2.normalized() if l2.length > 1e-12 else Vector()
            inward = l1 + l2
            if inward.length < 1e-9:
                inward = l1 if l1.length else nv.orthogonal()
            inward.normalize()
            miter = 1.0 / max(0.35, inward.dot(l1) if l1.length else 1.0)
            # turning angle (for side edge bevel)
            turn = 0.0
            if e1.length > 1e-12 and e2.length > 1e-12:
                turn = e1.normalized().angle(e2.normalized(), 0.0)
            u, w_ = local_uv(p1)
            theta = math.atan2(w_, u)
            cp = column_params(p, theta, armor)
            cols.append({'v': v, 'inward': inward, 'miter': miter, 'normal': nv, 'theta': theta, 'turn': turn,
                         'cp': cp})
        columns.append(cols)

    # ---- profiles ----------------------------------------------------------------
    def top_profile(cp):
        h = max(1e-5, cp['height'])
        room = h * (0.9 if shell else 0.9)
        cw, cd, bw = cp['cw'], cp['cd'], cp['bw']
        # bottom (outer) edge takes part of the wall height
        od, obw = cp['od'], cp['obw']
        need = cd + bw + od + obw
        if need > room and need > 0:
            f = room / need
            cd, bw, od, obw = cd * f, bw * f, od * f, obw * f
            nonlocal clamp_hit
            clamp_hit = True
        cw = min(cw, width_cap)
        top = edge_profile(cw, cd, cp['dir'], bw, cp['seg'] if bw > 0 else 0, cp['prof'],
                           wall_room=max(h - od - obw, 1e-5))
        return top, (od, obw)

    def bottom_profile(cp, wall_s, od, obw):
        ow = min(cp['ow'], width_cap)
        if shell:
            return [(wall_s, 0.0)]
        pts = edge_profile(ow, od, 'IN', obw, cp['oseg'] if obw > 0 else 0, cp['prof'], wall_room=1e9)
        return [(s + wall_s, -z) for s, z in pts]       # mirrored: z goes up the wall

    prof_top, prof_bot = [], []
    n_top = n_bot = 1
    for cols in columns:
        pt, pb = [], []
        for c in cols:
            top, (od, obw) = top_profile(c['cp'])
            wall_s = top[0][0]
            bot = bottom_profile(c['cp'], wall_s, od, obw)
            pt.append(top)
            pb.append(bot)
            n_top = max(n_top, len(top))
            n_bot = max(n_bot, len(bot))
        prof_top.append(pt)
        prof_bot.append(pb)
    if clamp_hit:
        notes.append('edge sizes reduced to fit the part height')
    # equal row counts everywhere: give sharp columns a tiny chamfer, then resample
    eps = max(radius * 2e-3, 1e-5)
    for li, cols in enumerate(columns):
        for ci in range(len(cols)):
            for prof, nrow, sign in ((prof_top, n_top, 1), (prof_bot, n_bot, -1)):
                pr = prof[li][ci]
                if len(pr) == 1 and nrow > 1:
                    s0, z0 = pr[0]
                    pr = [(s0, z0 - eps * sign), (s0 + eps, z0)]
                prof[li][ci] = _resample(pr, nrow) if nrow > 1 else pr

    # ---- cap shrink (harmonic displacement of the region) --------------------------
    cap_s = {}
    for li, cols in enumerate(columns):
        for ci, c in enumerate(cols):
            cap_s[c['v']] = (prof_top[li][ci][-1][0], prof_bot[li][ci][-1][0])

    def shrink(which):
        disp = {}
        for li, cols in enumerate(columns):
            for c in cols:
                s = cap_s[c['v']][which]
                disp[c['v']] = c['inward'] * c['miter'] * s
        if all(d.length < 1e-12 for d in disp.values()):
            return {v: v.co.copy() for v in verts}
        field = {v: disp.get(v, Vector()) for v in verts}
        interior = [v for v in verts if v not in bset]
        nbrs = {v: [e.other_vert(v) for e in v.link_edges] for v in interior}
        for _ in range(min(200, 20 + len(interior) // 4)):
            new = {}
            delta = 0.0
            for v in interior:
                acc = Vector()
                for w in nbrs[v]:
                    acc += field[w]
                acc /= max(len(nbrs[v]), 1)
                delta = max(delta, (acc - field[v]).length)
                new[v] = acc
            field.update(new)
            if delta < radius * 1e-5:
                break
        return {v: project(v.co + field[v], vnorm[v]) for v in verts}

    top_pos = shrink(0)
    bot_pos = top_pos if all(abs(a - b) < 1e-12 for a, b in cap_s.values()) else shrink(1)

    # ---- heights ------------------------------------------------------------------------
    def top_height(v, co_for_uv):
        r = 1.0 - min(dist[v], dmax) / dmax
        u, w_ = local_uv(co_for_uv)
        theta = math.atan2(w_, u)
        if armor:
            h = directional_height(p, theta, r)
            if branches:
                fade = 1.0 - smoothstep((r - (1.0 - trans_w)) / trans_w)
                h += ridge_value(u, w_, branches, p, radius) * fade
        else:
            h = p.extract_height
        return h

    # ---- assemble -----------------------------------------------------------------------------
    out = bmesh.new()
    smooth_faces = getattr(p, 'smooth_shading', True)
    vt, vb = {}, {}
    for v in verts:
        h = top_height(v, v.co)
        vt[v] = out.verts.new(top_pos[v] + vnorm[v] * (offset + h))
        if not shell:
            vb[v] = out.verts.new(bot_pos[v] + vnorm[v] * offset)
    for f in faces:
        nf = out.faces.new([vt[v] for v in f.verts])
        nf.smooth = smooth_faces
        if not shell:
            nf2 = out.faces.new([vb[v] for v in reversed(f.verts)])
            nf2.smooth = smooth_faces
    weight_edges = []
    for li, cols in enumerate(columns):
        n = len(cols)
        col_verts = []
        for ci, c in enumerate(cols):
            v = c['v']
            base = v.co
            ht = top_height(v, base)      # edge height (r = 1)
            nv = c['normal']
            chain = [vt[v]]
            # top band from inner to outer (the cap point itself is vt[v])
            top = prof_top[li][ci]
            def at(s):
                return project(base + c['inward'] * c['miter'] * s, nv)
            vt[v].co = at(top[-1][0]) + nv * (offset + ht + top[-1][1])
            for s, z in reversed(top[:-1]):
                chain.append(out.verts.new(at(s) + nv * (offset + ht + z)))
            bot = prof_bot[li][ci]
            for s, z in bot[:-1] if not shell else bot:
                chain.append(out.verts.new(at(s) + nv * (offset + z)))
            if not shell:
                s, z = bot[-1]
                vb[v].co = at(s) + nv * (offset + z)
                chain.append(vb[v])
            col_verts.append(chain)
        rows = len(col_verts[0])
        for ci in range(n):
            a, b = col_verts[ci], col_verts[(ci + 1) % n]
            for k in range(rows - 1):
                quad = (b[k], a[k], a[k + 1], b[k + 1])
                if len({id(x) for x in quad}) < 4:
                    continue
                try:
                    f = out.faces.new(quad)
                    f.smooth = smooth_faces
                except ValueError:
                    pass
        # side edges: vertical wall edges at sharp boundary corners (bevel by angle)
        thr = getattr(p, 'bevel_angle', math.radians(30.0))
        nt = len(prof_top[li][0])
        for ci, c in enumerate(cols):
            if c['turn'] >= thr:
                chain = col_verts[ci]
                k0 = nt - 1          # wall top (outermost top point)
                k1 = k0 + 1          # wall bottom (first bottom point)
                if k1 < len(chain):
                    weight_edges.append((chain[k0], chain[k1]))
    out.verts.index_update()
    bmesh.ops.remove_doubles(out, verts=out.verts[:], dist=radius * 1e-7)
    layer = out.edges.layers.float.get('bevel_weight_edge') or out.edges.layers.float.new('bevel_weight_edge')
    for a, b in weight_edges:
        if a.is_valid and b.is_valid:
            e = out.edges.get((a, b))
            if e is not None:
                e[layer] = 1.0
    out.normal_update()
    bad = [e for e in out.edges if not e.is_manifold]
    if not shell and bad:
        notes.append(f'{len(bad)} non-manifold edges (selection boundary too complex)')
    if not shell and out.calc_volume(signed=True) < 0:
        bmesh.ops.reverse_faces(out, faces=out.faces[:])
    bm.free()
    return out
