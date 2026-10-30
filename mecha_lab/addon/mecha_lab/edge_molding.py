"""Edge Molding: a profile swept along edge chains, as a SEPARATE object.

Sources: boundary of the selected faces, selected edges (Edit Mode), the
boundary of an Extract / Armor part, or the Armor Sculpt centre line.  The
chains (points + surface normals) are stored on the molding object, so width,
height, slope, chamfer, bevel, profile and offset rebuild it live, and the
original edges are never changed.  The profile is oriented by the surface
normal (not by a curve twist), so it stands upright on curved hulls.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty
from mathutils import Vector

COLL_MOLD = 'Edge Moldings'


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.is_molding and self.chains:
        rebuild(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Molding(bpy.types.PropertyGroup):
    is_molding: BoolProperty(default=False, options={'HIDDEN'})
    chains: StringProperty(default='', options={'HIDDEN'})
    source: PointerProperty(type=bpy.types.Object, name='Source')
    source_kind: StringProperty(default='', options={'HIDDEN'})
    profile: _p(EnumProperty, name='Profile', items=[
        ('ROUND', 'Round', ''), ('SQUARE', 'Square', ''), ('FLAT', 'Flat', 'Wide and low strip'),
        ('CHAMFER', 'Chamfer', 'Trapezoid with chamfered top corners'), ('CUSTOM', 'Custom', 'From a curve object')],
        default='SQUARE')
    custom_profile: _p(PointerProperty, type=bpy.types.Object, name='Custom Profile',
                       poll=lambda self, ob: ob.type == 'CURVE')
    width: _p(FloatProperty, name='Molding Width', default=0.04, min=0.0001, soft_max=1.0, precision=4, unit='LENGTH')
    height: _p(FloatProperty, name='Molding Height', default=0.02, min=0.0001, soft_max=1.0, precision=4, unit='LENGTH')
    surface_offset: _p(FloatProperty, name='Surface Offset', default=0.0, soft_min=-0.5, soft_max=0.5, precision=4,
                       unit='LENGTH')
    slope_angle: _p(FloatProperty, name='Slope Angle', default=math.radians(90.0), min=math.radians(20.0),
                    max=math.radians(90.0), subtype='ANGLE', description='Side wall angle (90 = vertical)')
    chamfer_width: _p(FloatProperty, name='Chamfer Width', default=0.0, min=0.0, soft_max=0.2, precision=4,
                      unit='LENGTH')
    chamfer_angle: _p(FloatProperty, name='Chamfer Angle', default=math.radians(45.0), min=math.radians(5.0),
                      max=math.radians(85.0), subtype='ANGLE')
    bevel_width: _p(FloatProperty, name='Bevel Width', default=0.0, min=0.0, soft_max=0.2, precision=4, unit='LENGTH')
    bevel_segments: _p(IntProperty, name='Bevel Segments', default=3, min=1, max=16)
    profile_resolution: _p(IntProperty, name='Profile Resolution', default=12, min=3, max=64)
    smooth_boundary: _p(IntProperty, name='Smooth Boundary', default=0, min=0, max=50,
                        description='0 = follow the original edges exactly')
    side: _p(EnumProperty, name='Placement', items=[
        ('CENTER', 'Centered', 'Centred on the edge'), ('INSIDE', 'Inside', 'Inside the boundary'),
        ('OUTSIDE', 'Outside', 'Outside the boundary')], default='CENTER')
    smooth_shading: _p(BoolProperty, name='Smooth Shading', default=True)


# =============================================================================
# Profile
# =============================================================================


def _fillet_pts(prev_pt, c, next_pt, size, seg):
    from .panel_gen import _fillet
    return _fillet(prev_pt, c, next_pt, size, seg, 0.5)


def profile_points(p):
    """Closed 2D profile (x = side, y = up), counter-clockwise, base at y = 0."""
    w, h = p.width, p.height
    if p.profile == 'CUSTOM' and p.custom_profile is not None and p.custom_profile.type == 'CURVE':
        spl = p.custom_profile.data.splines[0] if p.custom_profile.data.splines else None
        if spl is not None:
            pts = [(q.co.x, q.co.y) for q in (spl.bezier_points if spl.type == 'BEZIER' else spl.points)]
            if len(pts) >= 3:
                xs, ys = [q[0] for q in pts], [q[1] for q in pts]
                sx = (max(xs) - min(xs)) or 1.0
                sy = (max(ys) - min(ys)) or 1.0
                pts = [((x - (max(xs) + min(xs)) / 2) / sx * w, (y - min(ys)) / sy * h) for x, y in pts]
                return _ccw(pts)
    if p.profile == 'ROUND':
        n = max(3, p.profile_resolution)
        pts = [(-w / 2, 0.0)] + [(-w / 2 * math.cos(math.pi * k / n), h * math.sin(math.pi * k / n))
                                 for k in range(1, n)] + [(w / 2, 0.0)]
        return _ccw(pts)
    if p.profile == 'FLAT':
        h = min(h, w * 0.25)
    inset = 0.0 if p.slope_angle >= math.radians(89.9) else h / math.tan(p.slope_angle)
    inset = min(inset, w * 0.45)
    top_l, top_r = (-w / 2 + inset, h), (w / 2 - inset, h)
    corners = [(-w / 2, 0.0), (w / 2, 0.0)]
    cw = p.chamfer_width if p.profile in {'CHAMFER', 'SQUARE', 'FLAT'} else 0.0
    if p.profile == 'CHAMFER' and cw <= 0:
        cw = min(w, h) * 0.3
    if cw > 0:
        cw = min(cw, (top_r[0] - top_l[0]) * 0.45)
        cd = min(cw * math.tan(p.chamfer_angle), h * 0.9)
        top = [(top_r[0], h - cd), (top_r[0] - cw, h), (top_l[0] + cw, h), (top_l[0], h - cd)]
    else:
        top = [top_r, top_l]
    poly = corners + top
    if p.bevel_width > 0:
        out = []
        n = len(poly)
        for i in range(n):
            if i < 2:                      # keep the base corners sharp (sits on the surface)
                out.append(poly[i])
                continue
            out.extend(_fillet_pts(poly[i - 1], poly[i], poly[(i + 1) % n], p.bevel_width, p.bevel_segments))
        poly = out
    return _ccw(poly)


def _ccw(pts):
    area = sum(pts[i][0] * pts[(i + 1) % len(pts)][1] - pts[(i + 1) % len(pts)][0] * pts[i][1]
               for i in range(len(pts)))
    return pts if area > 0 else list(reversed(pts))


# =============================================================================
# Chains
# =============================================================================


def chains_from_edges(edges):
    """Ordered vertex chains from a set of BMEdges: [(verts, closed)]."""
    adj = {}
    for e in edges:
        a, b = e.verts
        adj.setdefault(a, []).append(b)
        adj.setdefault(b, []).append(a)
    used = set()
    chains = []
    ends = [v for v, n in adj.items() if len(n) != 2]
    for start in ends + list(adj):
        for nb in adj[start]:
            key = frozenset((start, nb))
            if key in used:
                continue
            chain = [start]
            prev, cur = start, nb
            used.add(key)
            closed = False
            while True:
                chain.append(cur)
                if cur == start:
                    closed = True
                    chain.pop()
                    break
                nxt = [w for w in adj[cur] if frozenset((cur, w)) not in used]
                if len(adj[cur]) != 2 or not nxt:
                    break
                prev, cur = cur, nxt[0]
                used.add(frozenset((prev, cur)))
            if len(chain) >= 2:
                chains.append((chain, closed))
    return chains


def boundary_edges_of_faces(faces):
    fset = set(faces)
    return [e for f in faces for e in f.edges if sum(1 for g in e.link_faces if g in fset) == 1]


def serialize(chains, matrix=None):
    out = []
    for verts, closed in chains:
        pts, nrm = [], []
        for v in verts:
            co = v.co if matrix is None else matrix @ v.co
            pts.append(tuple(co))
            nrm.append(tuple(v.normal))
        out.append({'pts': pts, 'nrm': nrm, 'closed': closed})
    return json.dumps(out)


def _smooth(pts, closed, iterations):
    pts = [Vector(p) for p in pts]
    for _ in range(iterations):
        new = list(pts)
        n = len(pts)
        for i in range(n):
            if not closed and i in (0, n - 1):
                continue
            a, b = pts[i - 1], pts[(i + 1) % n]
            new[i] = pts[i] * 0.5 + (a + b) * 0.25
        pts = new
    return pts


# =============================================================================
# Build
# =============================================================================


def build_bmesh(chains_json, p):
    data = json.loads(chains_json)
    prof = profile_points(p)
    shift = {'CENTER': 0.0, 'INSIDE': p.width / 2, 'OUTSIDE': -p.width / 2}[p.side]
    bm = bmesh.new()
    for ch in data:
        pts = _smooth(ch['pts'], ch['closed'], p.smooth_boundary)
        nrm = [Vector(n).normalized() if Vector(n).length > 1e-9 else Vector((0, 0, 1)) for n in ch['nrm']]
        closed = ch['closed'] and len(pts) >= 3
        n = len(pts)
        if n < 2:
            continue
        rings = []
        for i in range(n):
            if closed:
                a, b = pts[i - 1], pts[(i + 1) % n]
                t1 = (pts[i] - a).normalized()
                t2 = (b - pts[i]).normalized()
            else:
                t1 = (pts[i] - pts[max(i - 1, 0)]).normalized() if i > 0 else (pts[1] - pts[0]).normalized()
                t2 = (pts[min(i + 1, n - 1)] - pts[i]).normalized() if i < n - 1 else t1
            t = (t1 + t2)
            t = t.normalized() if t.length > 1e-9 else t1
            up = nrm[i] - t * nrm[i].dot(t)
            up = up.normalized() if up.length > 1e-9 else t.orthogonal().normalized()
            side = t.cross(up).normalized()
            cosh = max(0.3, t.dot(t1)) if t1.length > 0 else 1.0
            miter = 1.0 / cosh
            ring = [bm.verts.new(pts[i] + up * (p.surface_offset + y) + side * ((x + shift) * miter)) for x, y in prof]
            rings.append(ring)
        m = len(prof)
        last = n if closed else n - 1
        for i in range(last):
            a, b = rings[i], rings[(i + 1) % n]
            for k in range(m):
                k2 = (k + 1) % m
                try:
                    f = bm.faces.new((a[k], b[k], b[k2], a[k2]))
                    f.smooth = p.smooth_shading
                except ValueError:
                    pass
        if not closed:
            try:
                bm.faces.new(list(reversed(rings[0])))
                bm.faces.new(rings[-1])
            except ValueError:
                pass
    bm.normal_update()
    if bm.faces:
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rebuild(ob):
    bm = build_bmesh(ob.mch_molding.chains, ob.mch_molding)
    try:
        bm.to_mesh(ob.data)
        from . import edge_memory as _em; _em.mark_generated(ob.data)   # 0.24.95 Edge Memory: the part's own lines
    finally:
        bm.free()
    if ob.mch_molding.smooth_shading:
        try:
            ob.data.set_sharp_from_angle(angle=math.radians(40.0))
        except (AttributeError, TypeError):
            pass
    ob.data.update()


def create_molding(context, chains_json, matrix_world, name, source=None, kind=''):
    from .face_extract import _parts_collection
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
    _parts_collection(context, COLL_MOLD).objects.link(ob)
    ob.matrix_world = matrix_world.copy()
    p = ob.mch_molding
    d = context.scene.mch_molding
    for key in ('profile', 'width', 'height', 'surface_offset', 'slope_angle', 'chamfer_width', 'chamfer_angle',
                'bevel_width', 'bevel_segments', 'profile_resolution', 'smooth_boundary', 'side', 'smooth_shading'):
        setattr(p, key, getattr(d, key))
    p.custom_profile = d.custom_profile
    p.chains = chains_json
    p.source = source
    p.source_kind = kind
    p.is_molding = True
    rebuild(ob)
    return ob


# =============================================================================
# Operators
# =============================================================================


def _part_boundary(part):
    """Boundary chains of an Extract / Armor part's region (where it meets the hull)."""
    region = part.mch_extract.region
    bm = bmesh.new()
    bm.from_mesh(region)
    bm.normal_update()
    try:
        return serialize(chains_from_edges(boundary_edges_of_faces(list(bm.faces))))
    finally:
        bm.free()


def _part_centerline(part, samples=48):
    """Armor centre line polylines mapped onto the part's top surface."""
    from mathutils.bvhtree import BVHTree
    from . import panel_gen as pg
    p = part.mch_extract
    bm = bmesh.new()
    bm.from_mesh(p.region)
    bm.normal_update()
    cen, n, t, b, radius = pg.region_frame(list(bm.verts), list(bm.faces))
    bm.free()
    rot = p.dir_rotation
    from mathutils import Matrix
    q = Matrix.Rotation(rot, 3, n)
    t, b = q @ t, q @ b
    tree_bm = bmesh.new()
    tree_bm.from_mesh(part.data)
    tree = BVHTree.FromBMesh(tree_bm)
    tree_bm.free()
    out = []
    for pts, _w in pg.guide_branches(p):
        dense = []
        for i in range(len(pts) - 1):
            a, c = pts[i], pts[i + 1]
            steps = max(2, int(samples * math.dist(a, c) / 2))
            for k in range(steps):
                f = k / steps
                dense.append((a[0] + (c[0] - a[0]) * f, a[1] + (c[1] - a[1]) * f))
        dense.append(pts[-1])
        chain_p, chain_n = [], []
        for u, v in dense:
            u2 = (u * (-1 if p.dir_mirror else 1) * p.dir_scale_x + p.dir_offset_x) * radius   # inverse of local_uv
            v2 = (v * p.dir_scale_y + p.dir_offset_y) * radius
            origin = cen + t * u2 + b * v2 + n * radius * 4
            loc, nrm, _i, _d = tree.ray_cast(origin, -n)
            if loc is not None:
                chain_p.append(tuple(loc))
                chain_n.append(tuple(nrm))
        if len(chain_p) >= 2:
            out.append({'pts': chain_p, 'nrm': chain_n, 'closed': False})
    return json.dumps(out)


class MCH_OT_molding_create(bpy.types.Operator):
    bl_idname = 'mch.molding_create'
    bl_label = 'Create Edge Molding'
    bl_description = 'Sweep the molding profile along edges into a separate object (source unchanged)'
    bl_options = {'REGISTER', 'UNDO'}

    source: EnumProperty(name='Source', items=[
        ('FACES', 'Selected Face Boundary', 'Edit Mode: outline of the selected faces'),
        ('EDGES', 'Selected Edges', 'Edit Mode: the selected edges'),
        ('PART', 'Extracted Panel Boundary', 'Boundary of the selected Extract / Armor parts'),
        ('CENTER', 'Armor Center Line', 'Centre line of the selected Armor Sculpt parts')], default='FACES')

    @classmethod
    def poll(cls, context):
        return context.mode in {'EDIT_MESH', 'OBJECT'}

    def execute(self, context):
        made = []
        if self.source in {'FACES', 'EDGES'}:
            if context.mode != 'EDIT_MESH':
                self.report({'WARNING'}, 'Tab into Edit Mode and select faces / edges first')
                return {'CANCELLED'}
            for ob in [o for o in (context.objects_in_mode or [context.active_object]) if o and o.type == 'MESH']:
                ob.update_from_editmode()
                bm = bmesh.from_edit_mesh(ob.data)
                bm.normal_update()
                if self.source == 'FACES':
                    edges = boundary_edges_of_faces([f for f in bm.faces if f.select])
                else:
                    edges = [e for e in bm.edges if e.select]
                if not edges:
                    continue
                chains = chains_from_edges(edges)
                made.append(create_molding(context, serialize(chains), ob.matrix_world, ob.name + '_Molding', ob,
                                           self.source))
        else:
            parts = [o for o in context.selected_objects if getattr(o, 'mch_extract', None) and o.mch_extract.is_part]
            from .face_extract import active_part
            ap = active_part(context)
            if ap is not None and ap not in parts:
                parts.append(ap)
            for part in parts:
                if self.source == 'CENTER':
                    if part.mch_extract.mode != 'ARMOR' or part.mch_extract.cl_preset == 'NONE':
                        continue
                    data = _part_centerline(part)
                    name = part.name + '_RidgeMolding'
                else:
                    data = _part_boundary(part)
                    name = part.name + '_Molding'
                if json.loads(data):
                    made.append(create_molding(context, data, part.matrix_world, name, part, self.source))
        if not made:
            self.report({'WARNING'}, 'Nothing to follow: select faces / edges, or an Extract / Armor part')
            return {'CANCELLED'}
        context.scene.mch_molding_last = made[-1]
        self.report({'INFO'}, f'{len(made)} molding object(s) created')
        return {'FINISHED'}


def active_molding(context):
    ob = context.active_object
    if ob is not None and getattr(ob, 'mch_molding', None) and ob.mch_molding.is_molding:
        return ob
    last = getattr(context.scene, 'mch_molding_last', None)
    if last is not None and last.name in bpy.data.objects and last.mch_molding.is_molding:
        return last
    return None


class MCH_OT_molding_apply(bpy.types.Operator):
    bl_idname = 'mch.molding_apply'
    bl_label = 'Apply Molding'
    bl_description = 'Keep the mesh, drop the live settings'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_molding(context) is not None

    def execute(self, context):
        ob = active_molding(context)
        ob.mch_molding.is_molding = False
        ob.mch_molding.chains = ''
        return {'FINISHED'}


def draw(layout, context):
    ob = active_molding(context)
    p = ob.mch_molding if ob is not None else context.scene.mch_molding
    col = layout.column(align=True)
    col.scale_y = 1.3
    for src, label, icon in (('FACES', 'From Selected Faces (outline)', 'FACESEL'),
                             ('EDGES', 'From Selected Edges', 'EDGESEL'),
                             ('PART', 'From Extracted Panel Boundary', 'MOD_SOLIDIFY'),
                             ('CENTER', 'From Armor Center Line', 'IPO_LINEAR')):
        col.operator('mch.molding_create', text=label, icon=icon).source = src
    box = layout.box()
    box.label(text=('MOLDING: ' + ob.name) if ob else 'Settings for the next molding', icon='MOD_CURVE')
    box.prop(p, 'profile', text='')
    if p.profile == 'CUSTOM':
        box.prop(p, 'custom_profile')
    col = box.column(align=True)
    col.prop(p, 'width')
    col.prop(p, 'height')
    col.prop(p, 'surface_offset')
    col.prop(p, 'slope_angle')
    col = box.column(align=True)
    col.prop(p, 'chamfer_width')
    col.prop(p, 'chamfer_angle')
    col.prop(p, 'bevel_width')
    col.prop(p, 'bevel_segments')
    col.prop(p, 'profile_resolution')
    box.prop(p, 'smooth_boundary')
    box.row(align=True).prop(p, 'side', expand=True)
    box.prop(p, 'smooth_shading')
    if ob is not None:
        layout.operator('mch.molding_apply', icon='CHECKMARK')


CLASSES = (MCH_PG_Molding, MCH_OT_molding_create, MCH_OT_molding_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_molding = PointerProperty(type=MCH_PG_Molding)
    bpy.types.Scene.mch_molding = PointerProperty(type=MCH_PG_Molding)
    bpy.types.Scene.mch_molding_last = PointerProperty(type=bpy.types.Object)


def unregister():
    for owner, name in ((bpy.types.Scene, 'mch_molding_last'), (bpy.types.Scene, 'mch_molding'),
                        (bpy.types.Object, 'mch_molding')):
        if hasattr(owner, name):
            delattr(owner, name)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
