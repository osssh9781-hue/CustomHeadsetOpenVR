"""0.24 Plate Detail: low surface trim for armour plates (own tool, not Armor Plate).

Draw an outline on a mesh -> a separate, thin detail piece laid on the surface:

* the inside is a flat panel (Base height above the surface);
* along the outline 1 / 2 / 3 trim layers step down from the edge inward, each
  with its own width and height (presets per layer count);
* 0 / 1 / 2 screws: shallow round recesses in the outer trim near the corners.

How it is built (pure geometry, the drawn-on mesh is never changed): the
region under the outline is an even triangle patch on the surface (the Armor
Plate patch).  Every point gets its distance to the outline; the patch is cut
exactly along the iso-lines of that distance (layer borders) and around the
screw centres, every face takes the height of its band, and the bands are
joined by vertical walls, so the steps are crisp and follow the outline
(inward offset: sharp at convex corners, round at concave ones).  The region
is kept on the object, so every value changes live until Apply.
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from mathutils import Vector

# Layer presets: (width, height) per layer, outer layer first, FRACTIONS of the plate size (bounding
# diagonal).  Outer layer is the highest; the inside panel sits at Base.
LAYER_PRESETS = {
    1: ((0.070, 0.010),),
    2: ((0.050, 0.014), (0.040, 0.007)),
    3: ((0.040, 0.018), (0.032, 0.012), (0.028, 0.006)),
}
BASE_FRAC = 0.006            # inside panel thickness above the surface
SCREW_R_FRAC = 0.40          # screw radius = this x outer layer width (stays inside the trim)
SCREW_DEPTH_FRAC = 0.55      # recess depth = this x outer layer height


# -----------------------------------------------------------------------------
# Distance field
# -----------------------------------------------------------------------------


def _boundary_loop(bm):
    """Ordered outer boundary verts of the patch (longest loop)."""
    edges = [e for e in bm.edges if len(e.link_faces) == 1]
    nxt = {}
    for e in edges:
        f = e.link_faces[0]
        for lp in f.loops:
            if lp.edge == e:
                nxt[lp.vert] = lp.link_loop_next.vert     # face winding order
                break
    loops, seen = [], set()
    for start in list(nxt):
        if start in seen:
            continue
        lp, v = [], start
        while v is not None and v not in seen:
            seen.add(v)
            lp.append(v)
            v = nxt.get(v)
        loops.append(lp)
    return loops


def _seg_arrays(loops):
    a, b = [], []
    for lp in loops:
        n = len(lp)
        for i in range(n):
            a.append(tuple(lp[i].co))
            b.append(tuple(lp[(i + 1) % n].co))
    return np.array(a, float), np.array(b, float)


def dist_to_segments(pts, A, B, chunk=2048):
    """Distance of every point (n x 3) to the closest segment A[i] - B[i]."""
    pts = np.asarray(pts, float)
    out = np.empty(len(pts))
    AB = B - A
    L2 = np.maximum((AB * AB).sum(1), 1e-18)
    for s in range(0, len(pts), chunk):
        P = pts[s:s + chunk, None, :]
        t = np.clip(((P - A) * AB).sum(2) / L2, 0.0, 1.0)
        Q = A + AB * t[..., None]
        out[s:s + chunk] = np.sqrt(((P - Q) ** 2).sum(2)).min(1)
    return out


# -----------------------------------------------------------------------------
# Iso-line cut
# -----------------------------------------------------------------------------


def cut_iso(bm, key, level, eps, carry=()):
    """Cut the triangle patch exactly along key == level (marching triangles).

    ``key`` is a float vertex layer holding the field (computed once, 0.24.2);
    new verts on the cut get it by linear interpolation along the edge, like
    every layer in ``carry``."""
    layers = [key] + [c for c in carry if c is not key]
    on = set()
    for v in bm.verts:
        if abs(v[key] - level) < eps:
            on.add(v)
    for e in list(bm.edges):
        a, b = e.verts
        if a in on or b in on:
            continue
        fa, fb = a[key] - level, b[key] - level
        if fa * fb < 0:
            t = fa / (fa - fb)
            vals = [a[l] + (b[l] - a[l]) * t for l in layers]
            _ne, nv = bmesh.utils.edge_split(e, a, t)
            for l, x in zip(layers, vals):
                nv[l] = x
            nv[key] = level
            on.add(nv)
    for f in list(bm.faces):
        vs = [v for v in f.verts if v in on]
        if len(vs) != 2:
            continue
        a, b = vs
        if any(b in e.verts for e in a.link_edges if f in e.link_faces):
            continue                                # already an edge of the face
        try:
            bmesh.utils.face_split(f, a, b)
        except ValueError:
            pass
    bmesh.ops.triangulate(bm, faces=bm.faces[:])


def _field_layer(bm, name, values):
    lay = bm.verts.layers.float.new(name)
    for v, x in zip(bm.verts, values):
        v[lay] = float(x)
    return lay


# -----------------------------------------------------------------------------
# Screws
# -----------------------------------------------------------------------------


def screw_centres(loop, w1, count, min_turn=25.0):
    """Up to ``count`` screw centres on the middle of the outer trim, at the
    sharpest CONVEX corners of the outline (far apart): the point on the
    corner bisector at distance w1 / 2 from both sides."""
    if count <= 0 or len(loop) < 3:
        return []
    co = np.array([tuple(p_[0]) for p_ in loop])
    nr = np.array([tuple(p_[1]) for p_ in loop])
    seg = np.linalg.norm(np.roll(co, -1, 0) - co, axis=1)
    arc = np.concatenate([[0.0], np.cumsum(seg)])[:-1]
    total = float(seg.sum())
    look = min(max(w1 * 1.5, total * 0.015), total * 0.08)

    def at(i, off):
        s_ = (arc[i] + off) % total
        j = int(np.searchsorted(arc, s_, side='right') - 1)
        return co[j]

    cand = []
    for i in range(len(co)):
        d1, d2 = co[i] - at(i, -look), at(i, look) - co[i]
        l1, l2 = np.linalg.norm(d1), np.linalg.norm(d2)
        if l1 < 1e-12 or l2 < 1e-12:
            continue
        d1, d2 = d1 / l1, d2 / l2
        turn = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(d1, d2))))))
        if turn < min_turn or float(np.dot(np.cross(d1, d2), nr[i])) <= 0:    # straight or concave
            continue
        b = np.cross(nr[i], d1) + np.cross(nr[i], d2)                           # inward bisector
        bl = np.linalg.norm(b)
        if bl < 1e-9:
            continue
        reach = (w1 * 0.5) / max(0.2, math.cos(math.radians(turn) * 0.5))
        cand.append((turn, i, co[i] + b / bl * reach))
    if not cand:                                    # round outline: ends of the longest axis
        c0 = co.mean(0)
        far = int(np.argmax(np.linalg.norm(co - c0, axis=1)))
        far2 = int(np.argmax(np.linalg.norm(co - co[far], axis=1)))
        out = []
        for i in (far, far2)[:count]:
            v = c0 - co[i]
            out.append(Vector(co[i] + v / max(np.linalg.norm(v), 1e-9) * w1 * 0.5))
        return out
    cand.sort(key=lambda t: -t[0])
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    picked = [cand[0]]
    for c in cand[1:]:
        if len(picked) >= count:
            break
        if all(np.linalg.norm(co[c[1]] - co[p_[1]]) > size * 0.45 for p_ in picked):
            picked.append(c)
    return [Vector(c[2]) for c in picked]


# -----------------------------------------------------------------------------
# Build
# -----------------------------------------------------------------------------


def build_detail(region_me, layers, base, screws=0, screw_r=None, screw_depth=None, embed=0.0,
                 name='MCH_PlateDetail', direction='OUT', center=0.0, lift=0.0):
    """New mesh: flat panel + stepped trim layers + screw recesses on the
    region (triangle patch, faces pointing out of the surface).

    direction 'OUT': the edge is highest, layers step DOWN inward to the panel
    at Base.  'IN': layers step UP inward (each layer adds its height) and the
    inside panel is the highest, ``center`` above the last layer."""
    layers = [(float(w), float(h)) for w, h in layers if w > 0]
    bm = bmesh.new()
    try:
        bm.from_mesh(region_me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        kappa = surface_curvature(bm)
        loops = _boundary_loop(bm)
        if not loops or not bm.faces:
            raise ValueError('empty region')
        A, B = _seg_arrays(loops)
        size = float(np.linalg.norm(A.max(0) - A.min(0)))
        eps = size * 1e-5
        bm.normal_update()
        # a new layer reallocates the verts: keep the outline as plain coordinates / normals
        outer = [(v.co.copy(), v.normal.copy()) for v in max(loops, key=len)]
        dl = _field_layer(bm, 'd', dist_to_segments(np.array([tuple(v.co) for v in bm.verts]), A, B))
        levels = list(np.cumsum([w for w, _h in layers]))
        for L in levels:
            cut_iso(bm, dl, L, eps)
        # screws on the middle of the outer layer
        centres = []
        if layers and screws > 0:
            w1, h1 = layers[0]
            r = min(screw_r if screw_r else w1 * SCREW_R_FRAC, w1 * 0.45)
            centres = screw_centres(outer, w1, screws)
            for i, c in enumerate(centres):
                sl = _field_layer(bm, f's{i}', [(v.co - c).length for v in bm.verts])
                cut_iso(bm, sl, r, eps, carry=(dl,))
        else:
            r = 0.0
        depth = screw_depth if screw_depth is not None else (layers[0][1] * SCREW_DEPTH_FRAC if layers else 0.0)
        bm.normal_update()

        if direction == 'IN':
            heights = list(base + np.cumsum([h for _w, h in layers]))
            inside = (heights[-1] if heights else base) + center
        else:
            heights = [base + h for _w, h in layers]
            inside = base
        if layers and screw_depth is None:
            depth = (heights[0] - base) * SCREW_DEPTH_FRAC

        def face_height(f):
            cen = f.calc_center_median()
            d = sum(v[dl] for v in f.verts) / len(f.verts)     # every face lies inside one band
            h = inside
            for L, hh in zip(levels, heights):
                if d < L:
                    h = hh
                    break
            for c in centres:
                if (cen - c).length < r:
                    h -= depth
            return round(h, 9)

        fh = {f: face_height(f) for f in bm.faces}
        nrm = {v: v.normal.copy() for v in bm.verts}
        bm.verts.index_update()
        bm.faces.index_update()
        # Sectors: the faces of one height around a vertex that touch through edges.  Where a band border
        # pinches through a vertex (A B A B around it) the lower bands get their own copy of the vertex,
        # the highest band is shared - every wall edge then has exactly two faces.
        sector = {}
        for v in bm.verts:
            lf = list(v.link_faces)
            if not lf:
                continue
            top = max(fh[f] for f in lf)
            parent = {f: f for f in lf}

            def find(f):
                while parent[f] is not f:
                    parent[f] = parent[parent[f]]
                    f = parent[f]
                return f
            for e in v.link_edges:
                ef = e.link_faces
                if len(ef) == 2 and fh[ef[0]] == fh[ef[1]]:
                    parent[find(ef[0])] = find(ef[1])
            for f in lf:
                sector[(v.index, f.index)] = 0 if fh[f] == top else find(f).index + 1
        out_co, key_idx = [], {}

        def vid(v, h, f=None):
            k = (v.index, h, 0 if f is None else sector[(v.index, f.index)])
            i = key_idx.get(k)
            if i is None:
                i = key_idx[k] = len(out_co)
                out_co.append(v.co + nrm[v] * (h + lift))
            return i

        faces = []
        for f in bm.faces:
            h = fh[f]
            faces.append([vid(v, h, f) for v in f.verts])                  # top
            faces.append([vid(v, -embed) for v in reversed(f.verts)])     # bottom
        # boundary faces per vertex: where two bands meet at the outline, the higher band's side wall
        # carries the lower band's corner too (no open edge)
        bface = {}
        for e in bm.edges:
            if len(e.link_faces) == 1:
                for v in e.verts:
                    bface.setdefault(v, []).append(e.link_faces[0])

        def mids(v, h, top_down):
            lower = sorted({(fh[g], vid(v, fh[g], g)) for g in bface.get(v, ()) if fh[g] < h - 1e-12},
                           reverse=top_down)
            return [i for _h, i in lower]
        for e in bm.edges:
            lf = e.link_faces
            a, b = e.verts
            if len(lf) == 1:
                f = lf[0]
                h = fh[f]
                faces.append([vid(a, h, f), vid(b, h, f)] + mids(b, h, True) + [vid(b, -embed), vid(a, -embed)] +
                             mids(a, h, False))
            elif len(lf) == 2 and fh[lf[0]] != fh[lf[1]]:
                f1, f2 = lf
                faces.append([vid(a, fh[f1], f1), vid(b, fh[f1], f1), vid(b, fh[f2], f2), vid(a, fh[f2], f2)])
    finally:
        bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in out_co], [], faces)
    me.validate()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        simplify(bm, kappa=kappa)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(35))
    except (AttributeError, TypeError):
        pass
    me.update()
    me['mch_detail_screws'] = len(centres)
    return me


RISE_PROFILES = (
    ('ROUND', 'Round', 'Grows out of the surface: soft fillet at the foot, rounded top edge'),
    ('CHAMFER', 'Chamfer', 'Straight slope with crisp edges'),
    ('DOME', 'Round Top', 'Steep at the foot, rounding into the top'),
    ('FOOT', 'Soft Foot', 'Gentle at the foot, steeper near the top'),
)


def rise_curve(t, profile='ROUND'):
    t = np.clip(t, 0.0, 1.0)
    if profile == 'CHAMFER':
        return t
    if profile == 'DOME':
        return np.sin(t * math.pi * 0.5)
    if profile == 'FOOT':
        return t * t
    return t * t * t * (t * (6.0 * t - 15.0) + 10.0)     # smootherstep: flat at the foot and the top


def build_rise(region_me, height, ramp, embed=0.0, name='MCH_PlateRise', profile='ROUND', lift=0.0):
    """0.24 Detail 2: the surface itself rises smoothly inside the outline -
    0 at the outline, a smooth slope ``ramp`` wide, then a flat top
    ``height`` above the surface (no walls, no trims)."""
    bm = bmesh.new()
    try:
        bm.from_mesh(region_me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        kappa = surface_curvature(bm)
        loops = _boundary_loop(bm)
        if not loops or not bm.faces:
            raise ValueError('empty region')
        A, B = _seg_arrays(loops)
        size = float(np.linalg.norm(A.max(0) - A.min(0)))
        bm.normal_update()
        # 0.24.1 the slope as clean rings (like bevel segments): cut along the iso-lines of the distance,
        # heights are linear inside each ring, so every ring and the top merge into few faces
        segs = 1 if profile == 'CHAMFER' else RISE_SEGMENTS
        dl = _field_layer(bm, 'd', dist_to_segments(np.array([tuple(v.co) for v in bm.verts]), A, B))
        for k in range(1, segs + 1):
            cut_iso(bm, dl, ramp * k / segs, size * 1e-5)
        bm.normal_update()
        bm.verts.index_update()
        t = np.clip(np.array([v[dl] for v in bm.verts]) / max(ramp, 1e-9), 0.0, 1.0)
        k = np.minimum(np.floor(t * segs + 1e-6), segs - 1)
        lo, hi = rise_curve(k / segs, profile), rise_curve((k + 1) / segs, profile)
        frac = np.clip(t * segs - k, 0.0, 1.0)
        hs = lift + height * (lo + (hi - lo) * frac)
        out_co = [v.co + v.normal * float(h) for v, h in zip(bm.verts, hs)]
        n = len(out_co)
        out_co += [v.co + v.normal * (lift - embed) for v in bm.verts]
        faces = []
        for f in bm.faces:
            idx = [v.index for v in f.verts]
            faces.append(idx)
            faces.append([n + i for i in reversed(idx)])
        for e in bm.edges:
            if len(e.link_faces) == 1:
                a, b = (v.index for v in e.verts)
                faces.append([a, b, n + b, n + a])
    finally:
        bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in out_co], [], faces)
    me.validate()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        simplify(bm, kappa=kappa)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.shade_smooth()
    try:
        # 0.24.1 the skirt under the foot must not darken the smooth foot (it read as a cut-off edge)
        me.set_sharp_from_angle(angle=math.radians(60 if profile != 'CHAMFER' else 20))
    except (AttributeError, TypeError):
        pass
    me.update()
    return me


RISE_SEGMENTS = 8             # rings on a Round slope
SIMPLIFY_ANGLE = 0.6          # degrees: faces flatter than this merge into one


def surface_curvature(bm):
    """Bending of the surface patch (1 / radius, 90th percentile over its edges)."""
    bm.normal_update()
    kap = []
    for e in bm.edges:
        a_, b_ = e.verts
        L = e.calc_length()
        if L > 1e-12:
            kap.append(a_.normal.angle(b_.normal, 0.0) / L)
    return float(np.percentile(kap, 90)) if kap else 0.0


def simplify(bm, angle=SIMPLIFY_ANGLE, tol_frac=0.0012, kappa=0.0):
    """0.24.1 the dense patch is only needed to follow the outline and the
    surface: flat areas (bands, bottom, straight wall runs) merge into big faces.
    On a curved surface the merging is fenced by a grid (seams) whose cell size
    keeps every merged face within ``tol_frac`` x size of the real surface, so
    a big panel cannot flatten into the surface."""
    if not bm.faces:
        return
    co = np.array([tuple(v.co) for v in bm.verts])
    size = float(np.linalg.norm(co.max(0) - co.min(0))) or 1.0
    seams = []
    if kappa > 1e-9:
        g = max(math.sqrt(8.0 * tol_frac * size / kappa), size * 0.02)
        cell = {v: tuple(np.floor(np.array(tuple(v.co)) / g).astype(int)) for v in bm.verts}
        for e in bm.edges:
            if cell[e.verts[0]] != cell[e.verts[1]] and not e.seam:
                e.seam = True
                seams.append(e)
    bmesh.ops.dissolve_limit(bm, angle_limit=math.radians(angle), use_dissolve_boundaries=False,
                             verts=bm.verts[:], edges=bm.edges[:], delimit={'SEAM'} if seams else set())
    for e in bm.edges:
        e.seam = False
    # straight runs leave 2-edge verts behind
    lone = [v for v in bm.verts if len(v.link_edges) == 2 and len(v.link_faces) == 2 and
            (v.link_edges[0].other_vert(v).co - v.co).normalized().dot(
                (v.co - v.link_edges[1].other_vert(v).co).normalized()) > math.cos(math.radians(angle))]
    if lone:
        bmesh.ops.dissolve_verts(bm, verts=lone)


def preset_layers(count, size):
    return [(w * size, h * size) for w, h in LAYER_PRESETS[max(1, min(3, int(count)))]]


# -----------------------------------------------------------------------------
# Live objects
# -----------------------------------------------------------------------------

from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty  # noqa: E402

KINDS = {'DETAIL': 'TRIM', 'DETAIL2': 'RISE'}
DIRECTIONS = (('OUT', 'Edge High', 'The edge is highest, layers step down inward to the flat inside'),
              ('IN', 'Inside High', 'Layers step up inward, the inside panel is the highest'))
SCREW_ITEMS = (('0', 'No Screw', ''), ('1', '1 Screw', ''), ('2', '2 Screws', ''))
SPACING_PX = 20                # face size on screen for the surface patch (0.24.2: light, like Armor Plate)
RISE_DEFAULT = dict(height=0.035, ramp=0.12)
LENGTHS = ('w1', 'h1', 'w2', 'h2', 'w3', 'h3', 'base', 'center', 'screw_r', 'screw_depth', 'height', 'ramp', 'lift')
_SYNC = [False]


def is_detail(ob):
    pd_ = getattr(ob, 'mch_pdetail', None)
    return bool(pd_ is not None and pd_.live and pd_.region is not None)


def _ref(self):
    return self.id_data


DEBOUNCE = 0.15


def _queue(ob):
    """Rebuild once the slider stops moving (0.24.2: a drag sends many updates;
    rebuilding on each of them froze Blender)."""
    _PENDING.add(ob.name)
    if bpy.app.timers.is_registered(_rebuild_timer):
        bpy.app.timers.unregister(_rebuild_timer)
    bpy.app.timers.register(_rebuild_timer, first_interval=DEBOUNCE)


@bpy.app.handlers.persistent
def _on_undo_pre(*_args):
    """Ctrl+Z: drop pending rebuilds (they belong to the state being undone)."""
    _PENDING.clear()
    if bpy.app.timers.is_registered(_rebuild_timer):
        bpy.app.timers.unregister(_rebuild_timer)


_PENDING = set()


def _rebuild_timer():
    names = list(_PENDING)
    _PENDING.clear()
    for n in names:
        ob = bpy.data.objects.get(n)
        if ob is not None and is_detail(ob):
            try:
                rebuild(ob)
            except (ValueError, RuntimeError):
                pass
    return None


def _changed(self, _context):
    if _SYNC[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_detail(ob):
        remember(ob)
        _queue(ob)


class MCH_PG_PlateDetail(bpy.types.PropertyGroup):
    """Settings of a live Plate Detail object (lengths in the object's units)."""
    live: BoolProperty(default=False)
    kind: EnumProperty(items=(('TRIM', 'Trim', ''), ('RISE', 'Rise', '')), default='TRIM')
    region: PointerProperty(type=bpy.types.Mesh)
    size: FloatProperty(default=1.0)
    layers: IntProperty(name='Layers', default=2, min=1, max=3, update=_changed)
    direction: EnumProperty(name='Direction', items=DIRECTIONS, default='OUT', update=_changed)
    w1: FloatProperty(name='Width 1', default=0.05, min=0.0, soft_max=1.0, unit='LENGTH', precision=4, update=_changed,
                      description='Outer trim layer width')
    h1: FloatProperty(name='Height 1', default=0.014, min=0.0, soft_max=0.5, unit='LENGTH', precision=4, update=_changed)
    w2: FloatProperty(name='Width 2', default=0.04, min=0.0, soft_max=1.0, unit='LENGTH', precision=4, update=_changed)
    h2: FloatProperty(name='Height 2', default=0.007, min=0.0, soft_max=0.5, unit='LENGTH', precision=4, update=_changed)
    w3: FloatProperty(name='Width 3', default=0.03, min=0.0, soft_max=1.0, unit='LENGTH', precision=4, update=_changed)
    h3: FloatProperty(name='Height 3', default=0.006, min=0.0, soft_max=0.5, unit='LENGTH', precision=4, update=_changed)
    base: FloatProperty(name='Base Thickness', default=0.006, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
                        update=_changed, description='Flat inside panel above the surface')
    center: FloatProperty(name='Inside Height', default=0.02, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
                          update=_changed, description='Inside High: the inside panel above the last layer')
    screws: EnumProperty(name='Screws', items=SCREW_ITEMS, default='0', update=_changed)
    screw_r: FloatProperty(name='Screw Size', default=0.02, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
                           update=_changed, description='Screw radius (kept inside the outer layer)')
    screw_depth: FloatProperty(name='Screw Depth', default=0.006, min=0.0, soft_max=0.2, unit='LENGTH', precision=4,
                               update=_changed)
    height: FloatProperty(name='Height', default=0.035, min=0.0, soft_max=1.0, unit='LENGTH', precision=4,
                          update=_changed, description='Detail 2: height of the flat top above the surface')
    ramp: FloatProperty(name='Slope Width', default=0.12, min=0.0001, soft_max=1.0, unit='LENGTH', precision=4,
                        update=_changed, description='Detail 2: how far in the top starts - wider = narrower top')
    profile: EnumProperty(name='Edge', items=RISE_PROFILES, default='ROUND', update=_changed)
    lift: FloatProperty(name='Lift', default=0.0, soft_min=-0.2, soft_max=0.2, unit='LENGTH', precision=4,
                        update=_changed, description='Move the detail along the surface normal (- = into the '
                        'surface) so it sits right on it')


class MCH_PG_PlateDetailScene(bpy.types.PropertyGroup):
    """Settings for the next detail: lengths as FRACTIONS of the drawn size (the
    last edited detail is remembered this way, so a bigger outline gets a
    bigger trim)."""
    layers: IntProperty(name='Layers', default=2, min=1, max=3)
    direction: EnumProperty(name='Direction', items=DIRECTIONS, default='OUT')
    screws: EnumProperty(name='Screws', items=SCREW_ITEMS, default='0')
    profile: EnumProperty(name='Edge', items=RISE_PROFILES, default='ROUND')
    fractions: bpy.props.StringProperty(default='')


def _fractions(scene):
    import json
    try:
        return json.loads(scene.mch_pdetail.fractions or '{}')
    except ValueError:
        return {}


def default_fractions(layers):
    f = {'base': BASE_FRAC, 'center': 0.02, 'height': RISE_DEFAULT['height'], 'ramp': RISE_DEFAULT['ramp'],
         'lift': 0.0}
    for i, (w, h) in enumerate(LAYER_PRESETS[layers], 1):
        f[f'w{i}'], f[f'h{i}'] = w, h
    for i in range(len(LAYER_PRESETS[layers]) + 1, 4):
        f[f'w{i}'], f[f'h{i}'] = LAYER_PRESETS[3][i - 1]
    f['screw_r'] = f['w1'] * SCREW_R_FRAC
    f['screw_depth'] = f['h1'] * SCREW_DEPTH_FRAC
    return f


def remember(ob):
    """Edited values -> the next detail (fractions of this one's size)."""
    import json
    p = ob.mch_pdetail
    st = bpy.context.scene.mch_pdetail
    size = max(p.size, 1e-9)
    f = _fractions(bpy.context.scene)
    for k in LENGTHS:
        f[k] = getattr(p, k) / size
    st.fractions = json.dumps(f)
    st.layers, st.direction, st.screws, st.profile = p.layers, p.direction, p.screws, p.profile


def set_preset(ob, layers):
    """Layer count button: widths / heights from the preset for this size."""
    p = ob.mch_pdetail
    f = default_fractions(layers)
    _SYNC[0] = True
    try:
        p.layers = layers
        for k in ('w1', 'h1', 'w2', 'h2', 'w3', 'h3', 'screw_r', 'screw_depth'):
            setattr(p, k, f[k] * p.size)
    finally:
        _SYNC[0] = False
    remember(ob)
    rebuild(ob)


def rebuild(ob):
    p = ob.mch_pdetail
    embed = p.size * 0.002
    if p.kind == 'RISE':
        me = build_rise(p.region, p.height, p.ramp, embed=embed, profile=p.profile, lift=p.size * 0.0004 + p.lift,
                        name=ob.name)
    else:
        layers = [(p.w1, p.h1), (p.w2, p.h2), (p.w3, p.h3)][:p.layers]
        me = build_detail(p.region, layers, p.base, screws=int(p.screws), screw_r=p.screw_r,
                          screw_depth=p.screw_depth, embed=embed, name=ob.name, direction=p.direction,
                          center=p.center, lift=p.lift)
    old = ob.data
    for m in old.materials:
        me.materials.append(m)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.name = ob.name
    return me


def pick_target(context, projector, groups):
    """The mesh under the outline: armour plates count, live details do not."""
    outer = groups[0][0]
    probes = [(sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))] + list(outer[::4])
    dg = context.evaluated_depsgraph_get()
    counts = {}
    for xy in probes:
        o, d = projector.ray(xy)
        for _ in range(16):
            hit, loc, _n, _i, hob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or hob is None:
                break
            real = bpy.data.objects.get(hob.name)
            if real is not None and real.type == 'MESH' and not is_detail(real):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    if not counts:
        return None
    return bpy.data.objects[max(counts, key=counts.get)]


def perform(context, loops, projector, tool='DETAIL'):
    """Lasso -> a live Plate Detail object on the mesh under it."""
    from . import armor_plate as ap
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    target = pick_target(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the detail over a mesh (an armour plate or any part).')
    region, surround, local_size, _missing = ap.plate_meshes(context, target, groups, projector, SPACING_PX)
    bpy.data.meshes.remove(surround)
    kind = KINDS.get(tool, 'TRIM')
    st = context.scene.mch_pdetail
    f = default_fractions(st.layers)
    f.update(_fractions(context.scene))
    me = bpy.data.meshes.new(target.name + ('_Detail' if kind == 'TRIM' else '_Rise'))
    ob = bpy.data.objects.new(me.name, me)
    coll = target.users_collection[0] if target.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.parent = target
    ob.matrix_parent_inverse.identity()
    ob.matrix_basis.identity()
    for m in target.data.materials:
        me.materials.append(m)
    p = ob.mch_pdetail
    _SYNC[0] = True
    try:
        p.region = region
        p.size = local_size
        p.kind = kind
        p.layers, p.direction, p.screws, p.profile = st.layers, st.direction, st.screws, st.profile
        for k in LENGTHS:
            setattr(p, k, f[k] * local_size)
        p.live = True
    finally:
        _SYNC[0] = False
    try:
        rebuild(ob)
    except ValueError as ex:
        bpy.data.objects.remove(ob)
        raise cg.CutError(f'Detail could not be built ({ex}).')
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    what = f'{p.layers}-layer trim' if kind == 'TRIM' else 'smooth rise'
    return f'Plate Detail "{ob.name}" on {target.name} ({what}, {len(ob.data.polygons)} faces)'


def apply_detail(ob):
    """Keep the mesh as it is; drop the live data."""
    p = ob.mch_pdetail
    region = p.region
    p.live = False
    p.region = None
    if region is not None and region.users == 0:
        bpy.data.meshes.remove(region)


def active_detail(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_detail(ob) else None


class MCH_OT_pdetail_layers(bpy.types.Operator):
    """Trim layers 1 / 2 / 3: widths and heights from the preset for this size (adjust them after)"""
    bl_idname = 'mch.pdetail_layers'
    bl_label = 'Trim Layers'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    count: IntProperty(default=2, min=1, max=3)

    def execute(self, context):
        ob = active_detail(context)
        if ob is not None and ob.mch_pdetail.kind == 'TRIM':
            set_preset(ob, self.count)
        else:
            import json
            st = context.scene.mch_pdetail
            st.layers = self.count
            f = _fractions(context.scene)
            f.update({k: v for k, v in default_fractions(self.count).items() if k[0] in 'wh' or k.startswith('screw')})
            st.fractions = json.dumps(f)
        return {'FINISHED'}


class MCH_OT_pdetail_apply(bpy.types.Operator):
    """Make the detail a plain mesh (no more live changes)"""
    bl_idname = 'mch.pdetail_apply'
    bl_label = 'Apply Detail'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_detail(context) is not None

    def execute(self, context):
        apply_detail(context.active_object)
        return {'FINISHED'}


class MCH_OT_pdetail_remove(bpy.types.Operator):
    """Delete this live detail"""
    bl_idname = 'mch.pdetail_remove'
    bl_label = 'Remove Detail'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_detail(context) is not None

    def execute(self, context):
        ob = context.active_object
        region, me = ob.mch_pdetail.region, ob.data
        bpy.data.objects.remove(ob)
        for m in (me, region):
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)
        return {'FINISHED'}


def _draw_trim(col, p, scene_mode=False):
    row = col.row(align=True)
    for n in (1, 2, 3):
        row.operator('mch.pdetail_layers', text=f'{n} Layer' + ('s' if n > 1 else ''),
                     depress=(p.layers == n)).count = n
    col.row(align=True).prop(p, 'direction', expand=True)
    if scene_mode:
        col.row(align=True).prop(p, 'screws', expand=True)
        return
    for i in range(1, p.layers + 1):
        r = col.row(align=True)
        r.prop(p, f'w{i}', text=f'Width {i}')
        r.prop(p, f'h{i}', text=f'Height {i}')
    col.prop(p, 'base')
    col.prop(p, 'lift')
    if p.direction == 'IN':
        col.prop(p, 'center')
    col.row(align=True).prop(p, 'screws', expand=True)
    if p.screws != '0':
        r = col.row(align=True)
        r.prop(p, 'screw_r', text='Size')
        r.prop(p, 'screw_depth', text='Depth')


def draw(layout, context, tool='DETAIL'):
    kind = KINDS.get(tool, 'TRIM')
    ob = active_detail(context)
    if ob is not None and ob.mch_pdetail.kind == kind:
        p = ob.mch_pdetail
        box = layout.box()
        box.label(text='LIVE: ' + ob.name, icon='MOD_SOLIDIFY')
        col = box.column(align=True)
        if kind == 'TRIM':
            _draw_trim(col, p)
        else:
            _draw_rise_presets(col)
            col.prop(p, 'height')
            col.prop(p, 'ramp')
            col.prop(p, 'lift')
            col.row(align=True).prop(p, 'profile', expand=True)
        row = box.row(align=True)
        row.operator('mch.pdetail_apply', icon='CHECKMARK')
        row.operator('mch.pdetail_remove', icon='TRASH')
    else:
        st = context.scene.mch_pdetail
        layout.label(text='Settings for the next detail', icon='MOD_SOLIDIFY')
        col = layout.column(align=True)
        if kind == 'TRIM':
            _draw_trim(col, st, scene_mode=True)
        else:
            _draw_rise_presets(col)
            col.row(align=True).prop(st, 'profile', expand=True)
        layout.label(text='Sizes follow the outline; adjust them after drawing', icon='INFO')
    tip = ('Draw a closed outline on a plate: flat inside, trim along the edge' if kind == 'TRIM' else
           'Draw a closed outline: the surface rises smoothly inside it')
    layout.label(text=tip)


class MCH_PT_plate_detail(bpy.types.Panel):
    """Sidebar in Select mode with a live detail selected."""
    bl_idname = 'MCH_PT_plate_detail'
    bl_label = 'Plate Detail'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 3

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        return active_detail(context) is not None and ts.sidebar_select(context)

    def draw(self, context):
        ob = active_detail(context)
        draw(self.layout, context, 'DETAIL' if ob.mch_pdetail.kind == 'TRIM' else 'DETAIL2')


# 0.24.4 Detail 2 presets: (label, icon, edge profile, slope width as a factor of the height)
RISE_PRESETS = (
    ('VERTICAL', 'Vertical', 'Straight up from the surface (a wall)', 'CHAMFER', 0.03),
    ('SLANT', 'Slanted', 'Rises with a slight tilt (about 20 degrees off vertical)', 'CHAMFER', 0.36),
    ('ROUND', 'Round', 'Grows out of the surface with soft fillets (the default)', 'ROUND', None),
)


def _draw_rise_presets(col):
    row = col.row(align=True)
    for pid, label, _d, _prof, _k in RISE_PRESETS:
        row.operator('mch.pdetail_rise_preset', text=label).preset = pid


class MCH_OT_pdetail_rise_preset(bpy.types.Operator):
    """Detail 2 preset: Vertical / Slanted / Round (for the selected detail and the next ones)"""
    bl_idname = 'mch.pdetail_rise_preset'
    bl_label = 'Detail 2 Preset'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    preset: EnumProperty(items=[(r[0], r[1], r[2]) for r in RISE_PRESETS])

    @classmethod
    def description(cls, context, properties):
        return dict((r[0], r[2]) for r in RISE_PRESETS).get(properties.preset, '')

    def execute(self, context):
        import json
        _pid, _l, _d, prof, k = next(r for r in RISE_PRESETS if r[0] == self.preset)
        ob = active_detail(context)
        if ob is not None and ob.mch_pdetail.kind == 'RISE':
            p = ob.mch_pdetail
            _SYNC[0] = True
            try:
                p.profile = prof
                p.ramp = max(1e-4, p.height * k) if k is not None else RISE_DEFAULT['ramp'] * p.size
            finally:
                _SYNC[0] = False
            remember(ob)
            rebuild(ob)
        else:
            st = context.scene.mch_pdetail
            st.profile = prof
            f = _fractions(context.scene)
            h = f.get('height', RISE_DEFAULT['height'])
            f['ramp'] = h * k if k is not None else RISE_DEFAULT['ramp']
            st.fractions = json.dumps(f)
        return {'FINISHED'}


CLASSES = (MCH_PG_PlateDetail, MCH_PG_PlateDetailScene, MCH_OT_pdetail_rise_preset, MCH_OT_pdetail_layers, MCH_OT_pdetail_apply,
           MCH_OT_pdetail_remove, MCH_PT_plate_detail)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_pdetail = PointerProperty(type=MCH_PG_PlateDetail)
    bpy.types.Scene.mch_pdetail = PointerProperty(type=MCH_PG_PlateDetailScene)
    for lst in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if _on_undo_pre not in lst:
            lst.append(_on_undo_pre)


def unregister():
    if bpy.app.timers.is_registered(_rebuild_timer):
        bpy.app.timers.unregister(_rebuild_timer)
    _PENDING.clear()
    for lst in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        while _on_undo_pre in lst:
            lst.remove(_on_undo_pre)
    for owner, attr in ((bpy.types.Object, 'mch_pdetail'), (bpy.types.Scene, 'mch_pdetail')):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
