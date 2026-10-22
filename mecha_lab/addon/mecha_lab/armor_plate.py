"""0.16 Armor Plate: draw a lasso on a mesh, get a separate armour plate.

No retopology needed.  The plate does NOT reuse the faces of the mesh under the
lasso: a NEW clean patch is built inside the drawn outline and laid onto the
surface (like a shrinkwrap):

    1. the outline (screen pixels) is resampled densely, so the plate edge
       follows the drawn line exactly (corners kept);
    2. an even grid of points fills the inside, a constrained Delaunay
       triangulation joins them, triangles are paired into quads;
    3. every point is projected through the view onto the mesh it was drawn
       on (the surface normal is kept); points that miss land on the plane
       through the hits.

The patch then goes through the Face Extract / Armor Sculpt engine
(``panel_gen``): height, thickness, chamfer, bevel, outer edge and the live
part settings work exactly as for an extracted part, and the mesh you drew on
is never changed.

While drawing, the mouse wheel steps through the plate profiles.  Profile
sizes scale with the plate (Auto Size), so a small plate gets a small bevel.

Pure helpers (``resample_loop``, ``screen_patch``, ``preset_values``) are
tested headless; the stroke itself shares the Cut / Base Mesh lasso.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from mathutils import Matrix, Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

from . import core_geometry as cg
from . import tool_state as ts

# Profile presets: values are FRACTIONS of the plate size (bounding diagonal)
# when Auto Size is on; angles in degrees.  Everything not listed is reset.
PRESETS = (
    ('FLAT', 'Flat Plate', 'Plain plate, sharp edges', dict(extract_height=0.03)),
    ('CHAMFER', 'Chamfer 45', 'Top edge cut at 45 deg', dict(extract_height=0.04, chamfer_width=0.02,
                                                              chamfer_angle=45)),
    ('STEEP', 'Steep Chamfer', 'Narrow, steep top chamfer', dict(extract_height=0.05, chamfer_width=0.012,
                                                                  chamfer_angle=70)),
    ('SOFT', 'Soft Bevel', 'Small rounded top edge', dict(extract_height=0.04, bevel_width=0.012,
                                                           bevel_segments=3)),
    ('ROUND', 'Round Edge', 'Fully rounded top edge', dict(extract_height=0.05, bevel_width=0.025,
                                                            bevel_segments=6)),
    ('CHAMFER_BEVEL', 'Chamfer + Bevel', 'Chamfer with softened lines', dict(extract_height=0.05,
                                                                             chamfer_width=0.02,
                                                                             chamfer_angle=45, bevel_width=0.006,
                                                                             bevel_segments=2)),
    ('FLARED', 'Flared', 'Chamfer flaring outward beyond the outline', dict(extract_height=0.04,
                                                                           chamfer_width=0.02,
                                                                           chamfer_angle=45,
                                                                           chamfer_direction='OUT')),
    ('SHELL', 'Thin Shell', 'Thin plate shell (open underneath)', dict(extract_height=0.025, thickness=0.008)),
    ('HEAVY', 'Heavy Armor', 'Thick plate, wide chamfer', dict(extract_height=0.08, chamfer_width=0.03,
                                                                chamfer_angle=50, bevel_width=0.004,
                                                                bevel_segments=2)),
    ('STEPPED', 'Stepped Edge', 'Top chamfer + base chamfer', dict(extract_height=0.05, chamfer_width=0.015,
                                                                    chamfer_angle=45, outer_chamfer_width=0.015,
                                                                    outer_chamfer_angle=45)),
    ('CLOTH', 'Soft Cloth', 'Soft padded edge (tactical cloth)', dict(extract_height=0.035, bevel_width=0.03,
                                                                       bevel_segments=8, bevel_profile=0.3)),
    ('RIDGE', 'Center Ridge', 'Armor Sculpt plate with a ridge down the middle',
     dict(mode='ARMOR', extract_height=0.05, n_thickness=0.03, e_thickness=0.03, s_thickness=0.03,
          w_thickness=0.03, cl_preset='STRAIGHT', cl_height=0.02)),
)
PRESET_IDS = tuple(p[0] for p in PRESETS)
LENGTH_KEYS = {'extract_height', 'thickness', 'surface_offset', 'bevel_width', 'chamfer_width', 'chamfer_depth',
               'outer_bevel_width', 'outer_chamfer_width', 'cl_height', 'n_thickness', 'e_thickness',
               's_thickness', 'w_thickness'}
ANGLE_KEYS = {'chamfer_angle', 'outer_chamfer_angle', 'bevel_angle'}
RESET = dict(mode='BASIC', thickness=0.0, surface_offset=0.0, bevel_width=0.0, bevel_segments=3, bevel_profile=0.5,
             chamfer_width=0.0, chamfer_angle=45, chamfer_direction='IN', chamfer_mode='WIDTH_ANGLE',
             outer_bevel_width=0.0, outer_chamfer_width=0.0, outer_chamfer_angle=45, cl_preset='NONE')
MAX_POINTS = 9000


def preset_values(preset, size, auto=True):
    """Settings dict for a profile: lengths scaled by the plate size (Auto
    Size), angles converted to radians, the rest reset to plain values."""
    spec = next((p[3] for p in PRESETS if p[0] == preset), PRESETS[0][3])
    out = dict(RESET)
    out.update(spec)
    for k, v in list(out.items()):
        if k in ANGLE_KEYS:
            out[k] = math.radians(v)
        elif k in LENGTH_KEYS and auto:
            out[k] = v * size
        elif k in LENGTH_KEYS and not auto:
            out.pop(k)                         # manual size: keep the user's own value
    return out


# -----------------------------------------------------------------------------
# 2D patch (screen pixels)
# -----------------------------------------------------------------------------


def resample_loop(loop, step):
    """Closed loop with extra points every ``step`` px; the drawn points
    (corners) are all kept."""
    out = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        out.append((float(a[0]), float(a[1])))
        d = math.dist(a, b)
        k = int(d // step)
        for j in range(1, k + 1):
            t = j / (k + 1)
            out.append((a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t))
    return out


def _seg_dist(p, a, b):
    ax, ay = b[0] - a[0], b[1] - a[1]
    L = ax * ax + ay * ay
    if L < 1e-12:
        return math.dist(p, a)
    t = max(0.0, min(1.0, ((p[0] - a[0]) * ax + (p[1] - a[1]) * ay) / L))
    return math.dist(p, (a[0] + ax * t, a[1] + ay * t))


def screen_patch(groups, spacing=14.0, min_spacing=2.0):
    """Clean triangulation of the outline groups [(outer, [holes])] in pixels.

    Returns (points, triangles, boundary_count): the first ``boundary_count``
    points lie on the outline (in loop order, outer then holes)."""
    spacing = max(min_spacing, float(spacing))
    loops = [lp for outer, holes in groups for lp in [outer] + list(holes)]
    area = sum(abs(cg.signed_area(o)) - sum(abs(cg.signed_area(h)) for h in hs) for o, hs in groups)
    while area / (spacing * spacing) > MAX_POINTS:      # keep big plates light
        spacing *= 1.25
    rings = [resample_loop(lp, spacing * 0.5) for lp in loops]
    pts, edges = [], []
    for r in rings:
        start = len(pts)
        pts += r
        edges += [(start + i, start + (i + 1) % len(r)) for i in range(len(r))]
    nb = len(pts)
    segs = [(r[i], r[(i + 1) % len(r)]) for r in rings for i in range(len(r))]
    xs = [p[0] for p in pts]
    ys = [p[1] for p in pts]
    row = 0
    y = min(ys) + spacing * 0.5
    while y < max(ys):
        x = min(xs) + spacing * (0.5 + 0.5 * (row % 2))       # staggered rows: even triangles
        while x < max(xs):
            q = (x, y)
            if cg.point_in_loops(q, [g for o, hs in groups for g in [o] + list(hs)]) and \
                    min(_seg_dist(q, a, b) for a, b in segs) > spacing * 0.45:
                pts.append(q)
            x += spacing
        y += spacing * 0.866
        row += 1
    vs = [Vector(p) for p in pts]
    out_v, _e, out_f, out_vo, _eo, _fo = delaunay_2d_cdt(vs, edges, [], 0, 1e-6, True)
    remap = {}
    for new_i, orig in enumerate(out_vo):
        if orig:
            remap[new_i] = orig[0]
    tris = []
    all_loops = [g for o, hs in groups for g in [o] + list(hs)]
    for f in out_f:
        if len(f) != 3 or any(i not in remap for i in f):
            continue
        a, b, c = (remap[i] for i in f)
        cen = ((pts[a][0] + pts[b][0] + pts[c][0]) / 3, (pts[a][1] + pts[b][1] + pts[c][1]) / 3)
        if not cg.point_in_loops(cen, all_loops):
            continue
        ar = (pts[b][0] - pts[a][0]) * (pts[c][1] - pts[a][1]) - (pts[b][1] - pts[a][1]) * (pts[c][0] - pts[a][0])
        if abs(ar) < 1e-9:
            continue
        tris.append((a, b, c) if ar > 0 else (a, c, b))
    return pts, tris, nb


# -----------------------------------------------------------------------------
# Surface projection
# -----------------------------------------------------------------------------


def is_plate_or_part(ob):
    ex = getattr(ob, 'mch_extract', None)
    if ex is not None and ex.is_part:
        return True
    try:
        # 0.20: live cloth wrinkle layers are skipped too (0.24.20 and live Creature Plates)
        return bool(ob.get('mch_wrinkle')) or bool(ob.get('mch_cplate_src'))
    except (AttributeError, TypeError, ReferenceError):
        return False


def pick_surface(context, projector, groups):
    """The mesh under the outline (armour parts / plates are skipped)."""
    outer = groups[0][0]
    probes = [(sum(q[0] for q in outer) / len(outer), sum(q[1] for q in outer) / len(outer))] + list(outer[::4])
    dg = context.evaluated_depsgraph_get()
    counts = {}
    for xy in probes:
        o, d = projector.ray(xy)
        for _ in range(16):
            hit, loc, _n, _i, ob, _m = context.scene.ray_cast(dg, o, d)
            if not hit or ob is None:
                break
            real = bpy.data.objects.get(ob.name)
            if real is not None and real.type == 'MESH' and not is_plate_or_part(real):
                counts[real.name] = counts.get(real.name, 0) + 1
                break
            o = loc + d * 1e-4
    if not counts:
        return None
    return bpy.data.objects[max(counts, key=counts.get)]


def _target_bvh(context, ob):
    dg = context.evaluated_depsgraph_get()
    ev = ob.evaluated_get(dg)
    me = ev.to_mesh()
    try:
        mw = ev.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        ev.to_mesh_clear()
    return BVHTree.FromPolygons(verts, polys), verts, polys


def project_patch(points, projector, bvh):
    """World positions + normals of 2D points on the surface (view rays).
    Misses go to the depth of the nearest hits.  Returns (cos, normals, misses)."""
    cos, nrms, missing = [None] * len(points), [None] * len(points), []
    for i, xy in enumerate(points):
        o, d = projector.ray(xy)
        loc, n, _i, _dist = bvh.ray_cast(o, d)
        if loc is None:
            missing.append(i)
            continue
        # second, short cast from just in front of the hit: a view ray starts far away and the first
        # hit is only float-precise to ~1e-4
        loc2, n2, _i2, _d2 = bvh.ray_cast(loc - d * 0.05, d, 0.1)
        if loc2 is not None:
            loc, n = loc2, n2
        if n.dot(d) > 0:
            n = -n
        cos[i], nrms[i] = loc, n.normalized()
    hits = [i for i in range(len(points)) if cos[i] is not None]
    if not hits:
        raise cg.CutError('The outline is not on a mesh: draw over the surface you want the plate on.')
    if missing:
        # 0.19.2: a point past the surface edge goes to the depth of the nearest hits on screen (a plane
        # facing the view), not onto one plane through all hits - that made spikes past a silhouette
        from mathutils.kdtree import KDTree
        kd = KDTree(len(hits))
        for i in hits:
            kd.insert((points[i][0], points[i][1], 0.0), i)
        kd.balance()
        for i in missing:
            o, d = projector.ray(points[i])
            near = kd.find_n((points[i][0], points[i][1], 0.0), min(3, len(hits)))
            wsum = t = 0.0
            n = Vector()
            for _co, j, dist in near:
                w = 1.0 / max(dist, 1e-6)
                t += (cos[j] - o).dot(d) * w
                n += nrms[j] * w
                wsum += w
            cos[i] = o + d * (t / wsum)
            nrms[i] = n.normalized() if n.length > 1e-9 else -projector.view_dir
    return cos, nrms, missing


def build_region(points, tris, cos_local, nrms_local, quads=True):
    """Region mesh (object space of the surface) with outward faces."""
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(c) for c in cos_local]
        for a, b, c in tris:
            try:
                bm.faces.new((vs[a], vs[b], vs[c]))
            except ValueError:
                pass
        bm.normal_update()
        agree = sum(1 for f in bm.faces
                    if f.normal.dot(sum((nrms_local[v.index] for v in f.verts), Vector())) > 0)
        if agree < len(bm.faces) / 2:
            bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
        if quads and bm.faces:
            bmesh.ops.join_triangles(bm, faces=bm.faces[:], angle_face_threshold=math.radians(25),
                                     angle_shape_threshold=math.radians(40))
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        me = bpy.data.meshes.new('MCH_PlateRegion')
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return me


def surround_mesh(verts_world, polys, inv, lo, hi):
    """Faces of the surface near the plate (object space), for outward rings."""
    keep = []
    for poly in polys:
        for i in poly:
            p = verts_world[i]
            if all(lo[k] <= p[k] <= hi[k] for k in range(3)):
                keep.append(poly)
                break
    vmap, coords, faces = {}, [], []
    for poly in keep:
        idx = []
        for i in poly:
            if i not in vmap:
                vmap[i] = len(coords)
                coords.append(inv @ verts_world[i])
            idx.append(vmap[i])
        faces.append(idx)
    me = bpy.data.meshes.new('MCH_PlateSurround')
    me.from_pydata(coords, [], faces)
    me.update()
    return me


# -----------------------------------------------------------------------------
# Create
# -----------------------------------------------------------------------------


def plate_meshes(context, target, groups, projector, spacing):
    """Region + surround meshes (object space of ``target``) for the outline
    groups.  Returns (region, surround, local_size, missing)."""
    pts, tris, _nb = screen_patch(groups, spacing)
    if not tris:
        raise cg.CutError('The outline is too small for a plate.')
    bvh, wverts, polys = _target_bvh(context, target)
    cos, nrms, missing = project_patch(pts, projector, bvh)
    inv = target.matrix_world.inverted_safe()
    rot = inv.to_3x3()
    cos_l = [inv @ c for c in cos]
    nrm_l = [(rot @ n).normalized() for n in nrms]
    region = build_region(pts, tris, cos_l, nrm_l)
    lo = Vector([min(c[k] for c in cos) for k in range(3)])
    hi = Vector([max(c[k] for c in cos) for k in range(3)])
    size = max((hi - lo).length, 1e-6)
    pad = Vector((size * 0.25,) * 3)
    surround = surround_mesh(wverts, polys, inv, lo - pad, hi + pad)
    scale = target.matrix_world.to_scale()
    local_size = size / max(1e-9, (abs(scale.x) + abs(scale.y) + abs(scale.z)) / 3.0)
    return region, surround, local_size, missing



def through_plate_meshes(context, target, groups, projector, spacing, crease):
    """0.23.7 Through: [(region, surround, local_size)] - one per panel (front / back / creases)."""
    from . import through_region as tr
    panels = tr.panels_for(context, target, groups, projector, spacing, crease)
    _bvh, wverts, polys = _target_bvh(context, target)
    inv = target.matrix_world.inverted_safe()
    rot = inv.to_3x3()
    scale = target.matrix_world.to_scale()
    out = []
    for pn in panels:
        cos, nrms = pn['cos'], pn['nrms']
        region = build_region(cos, pn['tris'], [inv @ c for c in cos], [(rot @ n).normalized() for n in nrms])
        lo = Vector([min(c[k] for c in cos) for k in range(3)])
        hi = Vector([max(c[k] for c in cos) for k in range(3)])
        size = max((hi - lo).length, 1e-6)
        pad = Vector((size * 0.25,) * 3)
        surround = surround_mesh(wverts, polys, inv, lo - pad, hi + pad)
        local_size = size / max(1e-9, (abs(scale.x) + abs(scale.y) + abs(scale.z)) / 3.0)
        out.append((region, surround, local_size))
    return out

def perform_plate(context, loops, projector, preset=None):
    """Lasso -> new armour plate object (a live Face Extract part).  Returns
    a report; raises cg.CutError with the scene unchanged.

    0.19: the outline and the view are kept on the plate (``SRC_KEY``) until
    Apply, so Face Size / height / chamfer / profile change it live (HUD)."""
    scene = context.scene
    st = scene.mch_plate
    preset = preset or st.preset
    groups = cg.prepare_loops(loops)
    target = pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the plate over a mesh (armour parts and plates are skipped).')
    brush = getattr(scene, 'mch_brush', None)
    if getattr(brush, 'through_mode', False):
        return _perform_through(context, loops, projector, preset, target, groups, st, brush)
    region, surround, local_size, missing = plate_meshes(context, target, groups, projector, st.spacing)
    part = create_plate(context, target, region, surround, preset, local_size, st.auto_size)
    frozen = freeze_projector(projector)
    recalled = False
    if frozen is not None:
        part[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops],
                                    'proj': frozen, 'spacing': int(st.spacing), 'size': local_size})
        recalled = recall_plate(part, local_size, preset)      # 0.20.2 last used profile / lines / rims
    scene.mch_extract_last = part
    if getattr(st, 'creature', False):
        from . import creature_shell
        creature_shell.attach(part, -Vector(projector.view_dir), local_size)
    for o in context.selected_objects:
        o.select_set(False)
    part.select_set(True)
    context.view_layer.objects.active = part
    name = dict((p_[0], p_[1]) for p_ in PRESETS)[preset]
    extra = f' | {len(missing)} point(s) past the surface edge' if missing else ''
    return f'Armor plate "{part.name}" on {target.name} ({name}, {len(region.polygons)} clean faces){extra}'



def _perform_through(context, loops, projector, preset, target, groups, st, brush):
    """0.23.7 Through: one plate per panel (front / back / creases), each keeps its outline for Face Size."""
    crease = float(getattr(brush, 'through_crease', 50.0))
    made = through_plate_meshes(context, target, groups, projector, st.spacing, crease)
    frozen = freeze_projector(projector)
    parts = []
    for k, (region, surround, local_size) in enumerate(made):
        part = create_plate(context, target, region, surround, preset, local_size, st.auto_size)
        if frozen is not None:
            part[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops],
                                        'proj': frozen, 'spacing': int(st.spacing), 'size': local_size,
                                        'through': k, 'crease': crease})
            recall_plate(part, local_size, preset)
        if getattr(st, 'creature', False):
            from . import creature_shell
            nr = sum((Vector(p_.normal) for p_ in region.polygons), Vector())
            up = target.matrix_world.to_3x3() @ nr if nr.length > 1e-9 else -Vector(projector.view_dir)
            creature_shell.attach(part, up, local_size)
        parts.append(part)
    context.scene.mch_extract_last = parts[0]
    for o in context.selected_objects:
        o.select_set(False)
    for part in parts:
        part.select_set(True)
    context.view_layer.objects.active = parts[0]
    name = dict((p_[0], p_[1]) for p_ in PRESETS)[preset]
    return f'Armor plate through {target.name}: {len(parts)} plate(s) ({name}, front / back / creases)'


# -----------------------------------------------------------------------------
# 0.19 live plate: the drawn outline + a frozen view, rebuilt on demand
# -----------------------------------------------------------------------------

SRC_KEY = 'mch_plate_src'


class FrozenProjector:
    """A viewport projection saved as plain numbers (perspective matrix +
    region size), so the plate can be re-projected after the view moved."""

    def __init__(self, data):
        self.pers = Matrix(data['pers'])
        self.inv = self.pers.inverted_safe()
        self.w, self.h = float(data['w']), float(data['h'])
        self.is_perspective = bool(data['persp'])
        self.eye = Vector(data['eye'])
        self.view_dir = Vector(data['dir']).normalized()

    def _un(self, nx, ny, z):
        v = self.inv @ Vector((nx, ny, z, 1.0))
        return v.xyz / (v.w if abs(v.w) > 1e-12 else 1e-12)

    def ray(self, xy):
        nx, ny = 2.0 * xy[0] / self.w - 1.0, 2.0 * xy[1] / self.h - 1.0
        a, b = self._un(nx, ny, -1.0), self._un(nx, ny, 1.0)
        d = (b - a).normalized()
        return (self.eye.copy() if self.is_perspective else a), d

    def to_screen(self, co):
        p = self.pers @ Vector((co[0], co[1], co[2], 1.0))
        if p.w <= 1e-9:
            return None
        return ((p.x / p.w + 1.0) * self.w / 2.0, (p.y / p.w + 1.0) * self.h / 2.0)


def freeze_projector(pr):
    if isinstance(pr, cg.OrthoProjector):
        return {'kind': 'ortho', 'rot': list(pr.rot.to_quaternion()), 'center': list(pr.center), 'ppu': pr.ppu,
                'size': list(pr.size)}
    rv3d, region = getattr(pr, 'rv3d', None), getattr(pr, 'region', None)
    if rv3d is None or region is None:
        return None
    return {'kind': 'view', 'pers': [list(r) for r in rv3d.perspective_matrix], 'w': region.width,
            'h': region.height, 'persp': bool(pr.is_perspective), 'eye': list(pr.eye), 'dir': list(pr.view_dir)}


def thaw_projector(data):
    if data.get('kind') == 'ortho':
        return cg.OrthoProjector(Quaternion(data['rot']), Vector(data['center']), data['ppu'], tuple(data['size']))
    return FrozenProjector(data)


def plate_source(ob):
    """The saved outline of a plate still waiting for Apply (or None)."""
    if ob is None or not is_plate_or_part(ob):
        return None
    try:
        raw = ob.get(SRC_KEY)
    except (TypeError, ReferenceError):
        return None
    if not raw:
        return None
    try:
        return json.loads(raw)
    except (TypeError, ValueError):
        return None


def rebuild_plate(context, ob, spacing=None):
    """New faces for a live plate from its saved outline (Face Size changed).
    The profile settings stay as they are.  Returns True when rebuilt."""
    from . import face_extract as fx
    src = plate_source(ob)
    p = ob.mch_extract
    target = p.source
    if src is None or target is None or target.name not in bpy.data.objects:
        return False
    spacing = int(src.get('spacing', 120) if spacing is None else spacing)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    try:
        if src.get('through') is not None:
            made = through_plate_meshes(context, target, groups, thaw_projector(src['proj']), spacing,
                                        float(src.get('crease', 50.0)))
            k = int(src['through'])
            if k >= len(made):
                return False
            region, surround = made[k][0], made[k][1]
            for j, (r_, s_, _z) in enumerate(made):
                if j != k:
                    bpy.data.meshes.remove(r_)
                    bpy.data.meshes.remove(s_)
        else:
            region, surround, _size, _miss = plate_meshes(context, target, groups, thaw_projector(src['proj']),
                                                          spacing)
    except cg.CutError:
        return False
    old = (p.region, p.surround)
    p.region, p.surround = region, surround
    for m in old:
        if m is not None and m.users == 0:
            bpy.data.meshes.remove(m)
    src['spacing'] = spacing
    ob[SRC_KEY] = json.dumps(src)
    fx.rebuild(ob)
    return True


BAKED_KEY = 'mch_plate_baked'


def _settings(p):
    from . import face_extract as fx
    out = {}
    for k in fx.SETTING_KEYS:
        v = getattr(p, k)
        if isinstance(v, (bool, int, float, str)):
            out[k] = v
    return out


def plate_hp_data(ob):
    """Everything needed to rebuild a plate densely: outline, view, target and
    profile settings (live plate, or a plate applied since 0.19.2)."""
    src = plate_source(ob)
    if src is not None and ob.mch_extract.source is not None:
        return dict(src, target=ob.mch_extract.source.name, settings=_settings(ob.mch_extract))
    try:
        raw = ob.get(BAKED_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def dense_plate_mesh(context, ob, spacing=10):
    """0.19.2 High Poly of a plate: the SAME plate rebuilt with small faces from
    its outline (or, for other live parts, with a finer resolution), so the
    shape and the crisp edges are kept.  Returns a new mesh or None."""
    from . import face_extract as fx
    data = plate_hp_data(ob)
    p = ob.mch_extract
    live_part = p.is_part and p.region is not None
    if data is None and not live_part:
        return None
    me_tmp = bpy.data.meshes.new('MCH_HPtmp')
    tmp = bpy.data.objects.new('MCH_HPtmp', me_tmp)
    context.scene.collection.objects.link(tmp)
    tmp.matrix_world = ob.matrix_world.copy()
    tp = tmp.mch_extract
    made = []
    try:
        for k, v in (data['settings'] if data else _settings(p)).items():
            try:
                setattr(tp, k, v)
            except (TypeError, AttributeError, ValueError):
                pass
        if tp.bevel_width > 0:
            tp.bevel_segments = max(tp.bevel_segments, 6)
        target = bpy.data.objects.get(data['target']) if data else None
        if data and target is not None:
            groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in data['loops']])
            region, surround, _s, _m = plate_meshes(context, target, groups, thaw_projector(data['proj']), spacing)
            tp.resolution = 0
            tp.source = target
        elif live_part:
            region = p.region.copy()
            surround = p.surround.copy() if p.surround is not None else None
            tp.resolution = min(4, p.resolution + 2)
            tp.source = p.source
        else:
            return None
        made = [region, surround]
        tp.region, tp.surround = region, surround
        if not fx.rebuild(tmp):
            return None
        dg = context.evaluated_depsgraph_get()
        return bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    except cg.CutError:
        return None
    finally:
        bpy.data.objects.remove(tmp)
        for m in [me_tmp] + made:
            if m is not None and m.users == 0:
                bpy.data.meshes.remove(m)


def apply_plate(ob):
    """Apply: the plate becomes a plain mesh (modifiers applied, no live part).
    The outline + settings are kept (``BAKED_KEY``) for Make High Poly."""
    p = ob.mch_extract
    data = plate_hp_data(ob)
    dg = bpy.context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old, region, surround = ob.data, p.region, p.surround
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    p.is_part = False
    p.region = p.surround = None
    if SRC_KEY in ob:
        del ob[SRC_KEY]
    if data is not None:
        ob[BAKED_KEY] = json.dumps(data)
    for m in (old, region, surround):
        if m is not None and m.users == 0:
            bpy.data.meshes.remove(m)


def create_plate(context, target, region, surround, preset, local_size, auto=True, collection='Armor Plates',
                 height_scale=1.0):
    """A live Face Extract part on ``target`` from a region / surround mesh
    (object space of the target).  Raises cg.CutError when it cannot be built."""
    from . import face_extract as fx
    scene = context.scene
    me = bpy.data.meshes.new(target.name + '_Plate')
    part = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, collection).objects.link(part)
    part.matrix_world = target.matrix_world.copy()
    for mat in target.data.materials:
        me.materials.append(mat)
    p = part.mch_extract
    defaults = scene.mch_extract
    for key in fx.SETTING_KEYS:
        setattr(p, key, getattr(defaults, key))
    for k, v in preset_values(preset, local_size, auto).items():
        if k == 'extract_height':
            v *= height_scale
        try:
            setattr(p, k, v)
        except (TypeError, AttributeError):
            pass
    p.resolution = 0                          # the patch is already dense and even
    p.source = target
    p.region = region
    p.surround = surround
    p.is_part = True
    if not fx.rebuild(part):
        note = p.notes
        fx._remove_part(part)
        raise cg.CutError('Plate could not be built: ' + note)
    return part


def cycle_preset(scene, step):
    st = scene.mch_plate
    i = PRESET_IDS.index(st.preset) if st.preset in PRESET_IDS else 0
    st.preset = PRESET_IDS[(i + step) % len(PRESET_IDS)]
    return dict((p[0], p[1]) for p in PRESETS)[st.preset]


# -----------------------------------------------------------------------------
# Settings / panel
# -----------------------------------------------------------------------------


def pending_plate(context):
    """The active plate that is still live (drawn, not applied yet)."""
    ob = getattr(context, 'active_object', None)
    return ob if plate_source(ob) is not None else None


def _spacing_update(self, context):
    ob = pending_plate(context)
    if ob is not None and plate_source(ob).get('spacing') != self.spacing:
        rebuild_plate(context, ob, self.spacing)


class MCH_PG_Plate(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Profile', items=[(p[0], p[1], p[2]) for p in PRESETS], default='CHAMFER',
                         description='Plate profile (mouse wheel while drawing steps through them)')
    spacing: IntProperty(name='Face Size (px)', default=120, min=4, max=400, update=_spacing_update,
                         description='Size of the new faces on screen: bigger = fewer, cleaner faces '
                                     '(changes the selected plate live until Apply)')
    auto_size: BoolProperty(name='Auto Size', default=True,
                            description='Profile height / bevel / chamfer scale with the plate size')
    creature: BoolProperty(name='Creature Shell', default=False,
                           description='Creature Shell brush: new plates get hard random facets, bulges, '
                                       'N/E/S/W edge lift and gravity')


class MCH_OT_plate_preset(bpy.types.Operator):
    """Plate profile for the next plate (and the selected plate)"""
    bl_idname = 'mch.plate_preset'
    bl_label = 'Plate Profile'
    bl_options = {'REGISTER', 'UNDO'}
    preset: EnumProperty(items=[(p[0], p[1], p[2]) for p in PRESETS], default='CHAMFER')

    @classmethod
    def description(cls, context, properties):
        return dict((p[0], p[2]) for p in PRESETS).get(properties.preset, '')

    def execute(self, context):
        from . import face_extract as fx
        context.scene.mch_plate.preset = self.preset
        ob = context.active_object
        if ob is not None and is_plate_or_part(ob) and ob.mch_extract.region is not None:
            reg = ob.mch_extract.region
            pts = [v.co for v in reg.vertices]
            lo = Vector([min(c[k] for c in pts) for k in range(3)])
            hi = Vector([max(c[k] for c in pts) for k in range(3)])
            p = ob.mch_extract
            p.is_part = False                     # one rebuild at the end
            for k, v in preset_values(self.preset, (hi - lo).length, context.scene.mch_plate.auto_size).items():
                try:
                    setattr(p, k, v)
                except (TypeError, AttributeError):
                    pass
            p.resolution = 0
            p.is_part = True
            fx.rebuild(ob)
        return {'FINISHED'}


class MCH_OT_plate_cycle(bpy.types.Operator):
    """Next / previous plate profile (the selected live plate changes at once)"""
    bl_idname = 'mch.plate_cycle'
    bl_label = 'Plate Profile Step'
    bl_options = {'REGISTER', 'UNDO'}
    step: IntProperty(default=1)

    def execute(self, context):
        st = context.scene.mch_plate
        i = PRESET_IDS.index(st.preset) if st.preset in PRESET_IDS else 0
        return bpy.ops.mch.plate_preset(preset=PRESET_IDS[(i + self.step) % len(PRESET_IDS)])


class MCH_OT_plate_lines(bpy.types.Operator):
    """Surface lines on the plate top: off > center line > cross > random (Reroll: new random lines)"""
    bl_idname = 'mch.plate_lines'
    bl_label = 'Plate Surface Lines'
    bl_options = {'REGISTER', 'UNDO'}
    reroll: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and is_plate_or_part(ob)

    def execute(self, context):
        p = context.active_object.mch_extract
        if self.reroll:
            if p.facet_style != 'RANDOM':
                p.facet_style = 'RANDOM'
            else:
                p.facet_seed += 1
        else:
            i = LINE_STYLES.index(p.facet_style) if p.facet_style in LINE_STYLES else 0
            p.facet_style = LINE_STYLES[(i + 1) % len(LINE_STYLES)]
        remember_plate(context.active_object)
        return {'FINISHED'}


class MCH_OT_plate_rim(bpy.types.Operator):
    """Raise (or lower) the border band on this side of the plate: N / E / S / W"""
    bl_idname = 'mch.plate_rim'
    bl_label = 'Plate Rim'
    bl_options = {'REGISTER', 'UNDO'}
    side: EnumProperty(items=[(k, k, '') for k in 'NESW'] + [('RANDOM', 'Random', ''), ('PROFILE', 'Profile', '')],
                       default='N')

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and is_plate_or_part(ob)

    def execute(self, context):
        p = context.active_object.mch_extract
        if self.side == 'RANDOM':
            if p.rim_random:
                p.rim_seed += 1                 # pressed again: new random pieces
            else:
                p.rim_random = True
        elif self.side == 'PROFILE':
            p.rim_profile = 'BEVEL' if p.rim_profile == 'CHAMFER' else 'CHAMFER'
        else:
            key = 'rim_' + self.side.lower()
            setattr(p, key, not getattr(p, key))
        remember_plate(context.active_object)
        return {'FINISHED'}


class MCH_OT_plate_apply(bpy.types.Operator):
    """Apply the plate: it becomes a plain mesh with the current shape (no more live changes)"""
    bl_idname = 'mch.plate_apply'
    bl_label = 'Apply Plate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return pending_plate(context) is not None

    def execute(self, context):
        obs = [o for o in context.selected_objects if plate_source(o) is not None]
        ob = pending_plate(context)
        if ob is not None and ob not in obs:
            obs.append(ob)
        for o in obs:
            apply_plate(o)
        self.report({'INFO'}, f'Applied {len(obs)} plate(s)')
        return {'FINISHED'}


class MCH_OT_plate_cancel(bpy.types.Operator):
    """Remove the plate you just drew"""
    bl_idname = 'mch.plate_cancel'
    bl_label = 'Remove Plate'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return pending_plate(context) is not None

    def execute(self, context):
        from . import face_extract as fx
        ob = pending_plate(context)
        target = ob.mch_extract.source
        fx._remove_part(ob)
        if target is not None and target.name in context.view_layer.objects:
            target.select_set(True)
            context.view_layer.objects.active = target
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# HUD next to a live plate: Apply / Remove / profile and live sliders
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('apply', 'CHECKMARK', 'mch.plate_apply', {}, 'Apply'),
               ('cancel', 'X', 'mch.plate_cancel', {}, 'Remove'),
               ('prev', 'TRIA_LEFT', 'mch.plate_cycle', {'step': -1}, 'Previous profile'),
               ('next', 'TRIA_RIGHT', 'mch.plate_cycle', {'step': 1}, 'Next profile'),
               ('lines', 'IPO_LINEAR', 'mch.plate_lines', {'reroll': False}, 'Surface lines'),
               ('reroll', 'FILE_REFRESH', 'mch.plate_lines', {'reroll': True}, 'New random lines'),
               ('rim_n', 'EVENT_N', 'mch.plate_rim', {'side': 'N'}, 'Raise the north border'),
               ('rim_e', 'EVENT_E', 'mch.plate_rim', {'side': 'E'}, 'Raise the east border'),
               ('rim_s', 'EVENT_S', 'mch.plate_rim', {'side': 'S'}, 'Raise the south border'),
               ('rim_w', 'EVENT_W', 'mch.plate_rim', {'side': 'W'}, 'Raise the west border'),
               ('rim_rand', 'FILE_REFRESH', 'mch.plate_rim', {'side': 'RANDOM'}, 'Random border pieces (again: new)'),
               ('rim_prof', 'MOD_BEVEL', 'mch.plate_rim', {'side': 'PROFILE'}, 'Rim edge: chamfer / bevel'))
# key, label, part property (None = Face Size), lo, hi  (lengths: 1/1000 of the plate size)
SLIDERS = (('height', 'Height', 'extract_height', 1, 300), ('chamfer', 'Chamfer', 'chamfer_width', 0, 200),
           ('bevel', 'Bevel', 'bevel_width', 0, 200), ('crease', 'Crease', 'facet_depth', -200, 200),
           ('line_width', 'Line Width', 'facet_width', 0, 80), ('line_move', 'Line Move', 'facet_offset', -100, 100),
           ('line_turn', 'Line Turn', 'facet_rotation', -180, 180),
           ('rim_height', 'Rim Height', 'rim_height', -200, 200), ('rim_width', 'Rim Width', 'rim_width', 1, 60),
           ('rim_slope', 'Rim Slope', 'rim_slope', 2, 200), ('rim_turn', 'Rim Turn', 'dir_rotation', -180, 180),
           ('spacing', 'Face Size', None, 20, 400))
PCT_PROPS = {'facet_depth', 'facet_width', 'facet_offset', 'rim_height', 'rim_width', 'rim_slope'}
LINE_STYLES = ('NONE', 'CENTER', 'CROSS', 'RANDOM')
LINE_NAMES = {'NONE': 'Lines: off', 'CENTER': 'Lines: center', 'CROSS': 'Lines: cross', 'RANDOM': 'Lines: random'}


REMEMBER_REL = ('extract_height', 'chamfer_width', 'bevel_width')
REMEMBER_RAW = ('chamfer_angle', 'facet_style', 'facet_depth', 'facet_width', 'facet_offset', 'facet_rotation',
                'facet_count', 'facet_seed', 'rim_n', 'rim_e', 'rim_s', 'rim_w', 'rim_random', 'rim_seed', 'rim_count',
                'rim_profile', 'rim_slope', 'rim_width', 'rim_height', 'dir_rotation')


def remember_plate(ob):
    """0.20.2: keep this plate's profile / lines / rims for the next plate (lengths relative to its size)."""
    from . import last_used
    src = plate_source(ob)
    if src is None:
        return
    size = max(1e-6, float(src.get('size', 1.0)))
    p = ob.mch_extract
    for k in REMEMBER_REL:
        last_used.remember('plate', k, getattr(p, k))      # the same numbers next time
    for k in REMEMBER_RAW:
        v = getattr(p, k)
        last_used.remember('plate', k, v if isinstance(v, (bool, int, float, str)) else float(v))
    last_used.remember('plate', '_preset', context_preset(ob))


def context_preset(ob):
    try:
        return bpy.context.scene.mch_plate.preset
    except AttributeError:
        return ''


def recall_plate(part, local_size, preset):
    """Apply the remembered settings to a new plate (only when the profile is the same as last time)."""
    from . import last_used
    from . import face_extract as fx
    last = last_used.recall('plate')
    if not last or last.get('_preset') != preset:
        return False
    p = part.mch_extract
    p.is_part = False
    for k, v in last.items():
        if k.startswith('_'):
            continue
        try:
            setattr(p, k, v)
        except (TypeError, AttributeError, ValueError):
            pass
    p.is_part = True
    fx.rebuild(part)
    return True


def slider_spec(context, key, ob=None):
    """(label, value, lo, hi, setter, text) of a HUD slider for the live plate."""
    ob = ob or pending_plate(context)
    label, prop, lo, hi = next((l, pr, a, b) for k, l, pr, a, b in SLIDERS if k == key)
    if prop is None:
        st = context.scene.mch_plate
        v = int(plate_source(ob).get('spacing', st.spacing))

        def setter(val):
            if st.spacing != val:
                st.spacing = val                        # rebuilds through the update
            elif plate_source(ob).get('spacing') != val:
                rebuild_plate(context, ob, val)
        return label, v, lo, hi, setter, f'{label}  {v} px'
    p = ob.mch_extract
    if prop in PCT_PROPS:                           # surface lines: percent
        v = int(round(getattr(p, prop) * 100.0))
        return label, v, lo, hi, (lambda val: setattr(p, prop, val / 100.0)), f'{label}  {v} %'
    if prop in {'facet_rotation', 'dir_rotation'}:
        import math as _m
        v = int(round(_m.degrees(getattr(p, prop))))
        return label, v, lo, hi, (lambda val: setattr(p, prop, _m.radians(val))), f'{label}  {v} deg'
    size = max(1e-6, float(plate_source(ob).get('size', 1.0)))
    v = int(round(getattr(p, prop) / size * 1000.0))

    def setter(val):
        setattr(p, prop, max(0.0001 if prop == 'extract_height' else 0.0, val / 1000.0 * size))
    return label, v, lo, hi, setter, f'{label}  {getattr(p, prop):.3f}'


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - slider_w - btn)
    step = btn + gap
    total = step * 5 + (slider_h + gap) * len(SLIDERS)
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {'apply': (x, top), 'cancel': (x, top - step),
           'prev': (x, top - 2 * step), 'next': (x + step, top - 2 * step),
           'lines': (x, top - 3 * step), 'reroll': (x + step, top - 3 * step)}
    for i, k in enumerate(('rim_n', 'rim_e', 'rim_s', 'rim_w', 'rim_rand', 'rim_prof')):
        out[k] = (x + i * step, top - 4 * step)
    y = top - 5 * step
    for key, *_ in SLIDERS:
        out['slider_' + key] = (x - btn / 2 + slider_w / 2, y + btn / 2 - slider_h / 2)
        y -= slider_h + gap
    return out


def _hud_current(context):
    try:
        from . import tool_state as ts
        if context.mode != 'OBJECT' or not ts.is_mecha_workspace(getattr(context, 'workspace', None)):
            return None, {}
    except (AttributeError, TypeError):
        return None, {}
    from .primitive_hud import anchored, release_anchor
    ob = pending_plate(context)
    region, rv3d = context.region, context.region_data
    if ob is None or region is None or rv3d is None:
        if ob is None:
            release_anchor('plate')
        return None, {}
    from bpy_extras import view3d_utils
    ui = context.preferences.system.ui_scale
    pts = []
    for c in ob.bound_box:
        q = view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
        pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    return ob, anchored('plate', ob.name, region, hud_layout(pts, region.width / ui, region.height / ui))


class MCH_GT_plate_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_plate_slider'
    __slots__ = ('shape', 'init_x', 'init_value', 'key')

    def setup(self):
        if not hasattr(self, 'shape'):
            from .primitive_hud import _RECT
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.init_x = event.mouse_region_x
        self.init_value = slider_spec(context, self.key)[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        from .primitive_hud import slider_value
        spec = slider_spec(context, self.key)
        step = 3.0 if self.key == 'spacing' else 4.0
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x, step_px=step, lo=spec[2], hi=spec[3])
        if v != spec[1]:
            spec[4](v)
        if context.area:
            context.area.header_text_set(slider_spec(context, self.key)[5])
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            slider_spec(context, self.key)[4](self.init_value)
        else:
            ob = pending_plate(context)
            if ob is not None:
                remember_plate(ob)
            try:
                bpy.ops.ed.undo_push(message='Plate ' + self.key)
            except RuntimeError:
                pass


class MCH_GGT_plate_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_plate_hud'
    bl_label = 'Armor Plate HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and ts.hud_for(context, {'PLATE'}) and pending_plate(context) is not None

    def setup(self, context):
        self.items = {}
        for name, icon, op, props, _label in HUD_BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            t = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(t, k, v)
            gz.color = (1.0, 0.62, 0.16) if name == 'apply' else (0.17, 0.19, 0.23)
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        for key, *_ in SLIDERS:
            gz = self.gizmos.new(MCH_GT_plate_slider.bl_idname)
            gz.key = key
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        _ob, lay = _hud_current(context)
        ui = context.preferences.system.ui_scale
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            if name.startswith('slider_'):
                gz.matrix_basis = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (52.0 * ui, 10.0 * ui, 1.0, 1.0))
                continue
            gz.scale_basis = 15.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            if name in {'rim_n', 'rim_e', 'rim_s', 'rim_w'} and _ob is not None:
                gz.color = (1.0, 0.62, 0.16) if getattr(_ob.mch_extract, name) else (0.17, 0.19, 0.23)
            elif name == 'rim_rand' and _ob is not None:
                gz.color = (1.0, 0.62, 0.16) if _ob.mch_extract.rim_random else (0.17, 0.19, 0.23)


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        ob, lay = _hud_current(context)
        if ob is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        name = dict((p[0], p[1]) for p in PRESETS).get(context.scene.mch_plate.preset, '')
        lines = LINE_NAMES.get(ob.mch_extract.facet_style, '')
        for key, text in (('apply', 'Apply'), ('cancel', 'Remove'), ('next', name), ('reroll', lines),
                          ('rim_prof', 'Rims: ' + ob.mch_extract.rim_profile.title())):
            x, y = lay[key]
            blf.color(0, *((1.0, 0.62, 0.16) if key == 'apply' else (0.85, 0.87, 0.9)), 1.0)
            blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
            blf.draw(0, text)
        for key, *_ in SLIDERS:
            x, y = lay['slider_' + key]
            text = slider_spec(context, key, ob)[5]
            w, _h = blf.dimensions(0, text)
            blf.color(0, 1.0, 1.0, 1.0, 1.0)
            blf.position(0, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(0, text)
    except Exception:          # never break viewport drawing
        pass


def draw(layout, context):
    from . import face_extract as fx
    st = context.scene.mch_plate
    box = layout.box()
    box.label(text='ARMOR PLATE: draw on a mesh', icon='MOD_SOLIDIFY')
    grid = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
    for pid, label, _d, _v in PRESETS:
        grid.operator('mch.plate_preset', text=label, depress=(st.preset == pid)).preset = pid
    row = box.row(align=True)
    row.prop(st, 'spacing')
    row.prop(st, 'auto_size', toggle=True)
    ob = pending_plate(context)
    if ob is not None:
        p = ob.mch_extract
        sub = box.box()
        sub.label(text=f'LIVE: {ob.name} (until Apply)', icon='MOD_SOLIDIFY')
        col = sub.column(align=True)
        for prop in ('extract_height', 'chamfer_width', 'chamfer_angle', 'bevel_width'):
            col.prop(p, prop)
        rr = sub.row(align=True)
        rr.label(text='Rims')
        for k in 'nesw':
            rr.prop(p, f'rim_{k}', toggle=True)
        rr.prop(p, 'rim_random', toggle=True, text='Random')
        if p.rim_n or p.rim_e or p.rim_s or p.rim_w or p.rim_random:
            rc = sub.column(align=True)
            rc.prop(p, 'rim_height', slider=True)
            rc.prop(p, 'rim_width', slider=True)
            rc.row(align=True).prop(p, 'rim_profile', expand=True)
            rc.prop(p, 'rim_slope', slider=True)
            if p.rim_random:
                r2 = rc.row(align=True)
                r2.prop(p, 'rim_count')
                r2.prop(p, 'rim_seed')
            rc.prop(p, 'dir_rotation', text='Rim Turn')
        ln = sub.column(align=True)
        ln.prop(p, 'facet_style')
        if p.facet_style != 'NONE':
            ln.prop(p, 'facet_depth', slider=True)
            ln.prop(p, 'facet_width', slider=True)
            ln.prop(p, 'facet_offset', slider=True)
            ln.prop(p, 'facet_rotation')
            if p.facet_style == 'RANDOM':
                r = ln.row(align=True)
                r.prop(p, 'facet_count')
                r.prop(p, 'facet_seed')
        r = sub.row(align=True)
        r.scale_y = 1.3
        r.operator('mch.plate_apply', text='Apply', icon='CHECKMARK')
        r.operator('mch.plate_cancel', text='Remove', icon='X')
    col = box.column(align=True)
    col.scale_y = 0.8
    col.label(text='Click points / drag freehand, Enter or double-click: plate', icon='INFO')
    col.label(text='Mouse wheel while drawing: change the profile')
    col.label(text='Until Apply: face size / height / chamfer change live')
    col.label(text='The mesh you draw on is not changed')
    from . import random_panels
    random_panels.draw(layout, context)
    fx.draw(layout, context)


CLASSES = (MCH_PG_Plate, MCH_OT_plate_preset, MCH_OT_plate_cycle, MCH_OT_plate_lines, MCH_OT_plate_rim, MCH_OT_plate_apply, MCH_OT_plate_cancel,
           MCH_GT_plate_slider, MCH_GGT_plate_hud)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_plate = bpy.props.PointerProperty(type=MCH_PG_Plate)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    if hasattr(bpy.types.Scene, 'mch_plate'):
        del bpy.types.Scene.mch_plate
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
