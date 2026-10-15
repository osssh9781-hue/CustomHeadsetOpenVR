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


def cut_iso(bm, field, level, eps):
    """Cut the triangle patch exactly along field == level (marching triangles)."""
    verts = list(bm.verts)
    vals = dict(zip(verts, field(np.array([tuple(v.co) for v in verts])) - level))
    on = {v for v in verts if abs(vals[v]) < eps}
    for e in list(bm.edges):
        a, b = e.verts
        if a in on or b in on:
            continue
        fa, fb = vals[a], vals[b]
        if fa * fb < 0:
            _ne, nv = bmesh.utils.edge_split(e, a, fa / (fa - fb))
            vals[nv] = 0.0
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


# -----------------------------------------------------------------------------
# Screws
# -----------------------------------------------------------------------------


def screw_centres(loop, w1, count, min_turn=25.0):
    """Up to ``count`` screw centres on the middle of the outer trim, at the
    sharpest CONVEX corners of the outline (far apart): the point on the
    corner bisector at distance w1 / 2 from both sides."""
    if count <= 0 or len(loop) < 3:
        return []
    co = np.array([tuple(v.co) for v in loop])
    nr = np.array([tuple(v.normal) for v in loop])
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
                 name='MCH_PlateDetail'):
    """New mesh: flat panel + stepped trim layers + screw recesses on the
    region (triangle patch, faces pointing out of the surface)."""
    layers = [(float(w), float(h)) for w, h in layers if w > 0]
    bm = bmesh.new()
    try:
        bm.from_mesh(region_me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        loops = _boundary_loop(bm)
        if not loops or not bm.faces:
            raise ValueError('empty region')
        A, B = _seg_arrays(loops)
        outline = lambda P: dist_to_segments(P, A, B)
        size = float(np.linalg.norm(A.max(0) - A.min(0)))
        eps = size * 1e-5
        levels = list(np.cumsum([w for w, _h in layers]))
        for L in levels:
            cut_iso(bm, outline, L, eps)
        # screws on the middle of the outer layer
        centres = []
        if layers and screws > 0:
            w1, h1 = layers[0]
            r = min(screw_r if screw_r else w1 * SCREW_R_FRAC, w1 * 0.45)
            bm.normal_update()
            centres = screw_centres(max(loops, key=len), w1, screws)
            for c in centres:
                cc = np.array(tuple(c))
                cut_iso(bm, lambda P, cc=cc: np.linalg.norm(P - cc, axis=1), r, eps)
        else:
            r = 0.0
        depth = screw_depth if screw_depth is not None else (layers[0][1] * SCREW_DEPTH_FRAC if layers else 0.0)
        bm.normal_update()

        heights = [base + h for _w, h in layers]

        def face_height(f):
            cen = f.calc_center_median()
            d = outline(np.array([tuple(cen)]))[0]
            h = base
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
        out_co, key_idx = [], {}

        def vid(v, h):
            k = (v.index, h)
            i = key_idx.get(k)
            if i is None:
                i = key_idx[k] = len(out_co)
                out_co.append(v.co + nrm[v] * h)
            return i

        bm.verts.index_update()
        faces = []
        for f in bm.faces:
            h = fh[f]
            faces.append([vid(v, h) for v in f.verts])                  # top
            faces.append([vid(v, -embed) for v in reversed(f.verts)])  # bottom
        for e in bm.edges:
            lf = e.link_faces
            a, b = e.verts
            if len(lf) == 1:
                h = fh[lf[0]]
                faces.append([vid(a, h), vid(b, h), vid(b, -embed), vid(a, -embed)])
            elif len(lf) == 2 and fh[lf[0]] != fh[lf[1]]:
                h1, h2 = fh[lf[0]], fh[lf[1]]
                faces.append([vid(a, h1), vid(b, h1), vid(b, h2), vid(a, h2)])
    finally:
        bm.free()
    me = bpy.data.meshes.new(name)
    me.from_pydata([tuple(c) for c in out_co], [], faces)
    me.validate()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=size * 1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
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


def preset_layers(count, size):
    return [(w * size, h * size) for w, h in LAYER_PRESETS[max(1, min(3, int(count)))]]
