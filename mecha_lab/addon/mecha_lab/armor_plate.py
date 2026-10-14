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

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, IntProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import delaunay_2d_cdt

from . import core_geometry as cg

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
    return bool(ex is not None and ex.is_part)


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
    Misses go onto the plane through the hits.  Returns (cos, normals, misses)."""
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
        c = sum((cos[i] for i in hits), Vector()) / len(hits)
        n = sum((nrms[i] for i in hits), Vector())
        n = n.normalized() if n.length > 1e-9 else -projector.view_dir
        for i in missing:
            o, d = projector.ray(points[i])
            den = d.dot(n)
            t = (c - o).dot(n) / den if abs(den) > 1e-9 else 0.0
            cos[i], nrms[i] = o + d * t, n.copy()
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


def perform_plate(context, loops, projector, preset=None):
    """Lasso -> new armour plate object (a live Face Extract part).  Returns
    a report; raises cg.CutError with the scene unchanged."""
    scene = context.scene
    st = scene.mch_plate
    preset = preset or st.preset
    groups = cg.prepare_loops(loops)
    target = pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the plate over a mesh (armour parts and plates are skipped).')
    pts, tris, _nb = screen_patch(groups, st.spacing)
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
    part = create_plate(context, target, region, surround, preset, local_size, st.auto_size)
    scene.mch_extract_last = part
    for o in context.selected_objects:
        o.select_set(False)
    part.select_set(True)
    context.view_layer.objects.active = part
    name = dict((p_[0], p_[1]) for p_ in PRESETS)[preset]
    extra = f' | {len(missing)} point(s) past the surface edge' if missing else ''
    return f'Armor plate "{part.name}" on {target.name} ({name}, {len(region.polygons)} clean faces){extra}'


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


class MCH_PG_Plate(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Profile', items=[(p[0], p[1], p[2]) for p in PRESETS], default='CHAMFER',
                         description='Plate profile (mouse wheel while drawing steps through them)')
    spacing: IntProperty(name='Face Size (px)', default=14, min=4, max=80,
                         description='Size of the new faces on screen: smaller = denser plate')
    auto_size: BoolProperty(name='Auto Size', default=True,
                            description='Profile height / bevel / chamfer scale with the plate size')


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
    col = box.column(align=True)
    col.scale_y = 0.8
    col.label(text='Click points / drag freehand, Enter or double-click: plate', icon='INFO')
    col.label(text='Mouse wheel while drawing: change the profile')
    col.label(text='New clean faces follow the surface (no retopology)')
    col.label(text='The mesh you draw on is not changed')
    from . import random_panels
    random_panels.draw(layout, context)
    fx.draw(layout, context)


CLASSES = (MCH_PG_Plate, MCH_OT_plate_preset)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_plate = bpy.props.PointerProperty(type=MCH_PG_Plate)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_plate'):
        del bpy.types.Scene.mch_plate
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
