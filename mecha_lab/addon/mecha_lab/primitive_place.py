"""0.14 Primitive placement (after Substance 3D Modeler).

With the Primitive tool on, a SEMI-TRANSPARENT ghost of the chosen shape sits
in the viewport with handles:

* six arrows = size; each arrow moves only its own face (the opposite face
  stays put, like Substance's asymmetric scaling)
* a dial = spin around the shape's own Z axis
* a ring in the middle = move;  a click on a mesh = put the ghost there
  (aligned to the surface when "Align to Surface" is on)

Enter       = ADD: the shape is merged into the mesh it overlaps (Boolean
              union).  Touching nothing -> it becomes a new object.
Alt+Enter   = SUBTRACT: the shape is carved out of every mesh it overlaps.
The ghost stays where it is, so the next shape can be placed right away.
Holding Alt turns the ghost red (preview of subtract).

Merge seam: Hard (sharp seam), Chamfer or Smooth (only the NEW seam edges are
bevelled - the same seam-only finish as Cut's Edge Finish).

Shapes: Box, Cylinder, Pill Cylinder (stadium cross-section: a cylinder whose
round face is stretched), Sphere, Cone, Capsule.

The ghost state lives on the WindowManager: Ctrl+Z does not move it and it is
not saved into the user's .blend.

Pure helpers (``ghost_geometry``, ``place_handles``, ``ghost_matrix``) are
tested headless; drawing, handles and keys need a real viewport.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty,
                       PointerProperty, StringProperty)
from mathutils import Matrix, Quaternion, Vector

from . import core_geometry as cg
from . import tool_state as ts

KIND_ITEMS = [
    ('BOX', 'Box', 'Box (X / Y / Z size)'),
    ('CYLINDER', 'Cylinder', 'Cylinder (X / Y = diameter, Z = height)'),
    ('PILL', 'Pill Cylinder', 'Cylinder whose round face is stretched: the cross-section is a pill '
                              '(X = long side, Y = width, Z = height)'),
    ('SPHERE', 'Sphere', 'Sphere / ellipsoid'),
    ('CONE', 'Cone', 'Cone or tapered cylinder (Top Size)'),
    ('CAPSULE', 'Capsule', 'Capsule along Z (round ends)'),
]
KINDS = tuple(k for k, _l, _d in KIND_ITEMS)
ICON_STEM = {'BOX': 'primitive_box', 'CYLINDER': 'primitive_cylinder', 'PILL': 'primitive_pill',
             'SPHERE': 'primitive_sphere', 'CONE': 'primitive_cone', 'CAPSULE': 'primitive_capsule'}
FALLBACK_ICON = {'BOX': 'MESH_CUBE', 'CYLINDER': 'MESH_CYLINDER', 'PILL': 'MESH_CYLINDER',
                 'SPHERE': 'MESH_UVSPHERE', 'CONE': 'MESH_CONE', 'CAPSULE': 'MESH_CAPSULE'}
MERGE_ITEMS = [
    ('HARD', 'Hard', 'Sharp seam where the shapes meet'),
    ('CHAMFER', 'Chamfer', 'Chamfer only the new seam'),
    ('SMOOTH', 'Smooth', 'Round only the new seam'),
]
COL_ADD = (0.31, 0.70, 1.0)
COL_SUB = (1.0, 0.30, 0.25)
_draw_handle = None


# -----------------------------------------------------------------------------
# Pure geometry (local space, centred on the origin, outward-facing faces)
# -----------------------------------------------------------------------------


def _ring(points, z):
    return [(x, y, z) for x, y in points]


def _ellipse(n, rx, ry):
    return [(math.cos(2 * math.pi * i / n) * rx, math.sin(2 * math.pi * i / n) * ry) for i in range(n)]


def stadium(n, length, width):
    """Pill cross-section (counter-clockwise, ``n`` points): two half circles of
    diameter = the shorter side, joined by straight sides along the longer one."""
    along_x = length >= width
    a, b = (length, width) if along_x else (width, length)
    r = b / 2.0
    half = max(0.0, a / 2.0 - r)
    per = max(2, n // 2)
    pts = []
    for i in range(per):                       # right half circle, -90 .. +90 deg
        t = -math.pi / 2 + math.pi * i / (per - 1)
        pts.append((half + r * math.cos(t), r * math.sin(t)))
    for i in range(per):                       # left half circle, +90 .. 270 deg
        t = math.pi / 2 + math.pi * i / (per - 1)
        pts.append((-half + r * math.cos(t), r * math.sin(t)))
    if not along_x:
        pts = [(-y, x) for x, y in pts]        # rotate 90 deg, still counter-clockwise
    return pts


def _prism(loop_bottom, loop_top, zb, zt):
    """Two rings joined by quads, n-gon caps.  Loops are counter-clockwise."""
    n = len(loop_bottom)
    verts = _ring(loop_bottom, zb) + _ring(loop_top, zt)
    faces = [tuple(range(n - 1, -1, -1)), tuple(range(n, 2 * n))]
    for i in range(n):
        j = (i + 1) % n
        faces.append((i, j, n + j, n + i))
    return verts, faces, set(range(2, 2 + n))


def _lathe(profile, n, sx, sy):
    """Surface of revolution: ``profile`` = [(radius, z)] from the bottom pole to
    the top pole (radius 0 at both ends).  X / Y scaled to an ellipse."""
    verts, faces = [], []
    bottom = len(verts)
    verts.append((0.0, 0.0, profile[0][1]))
    rings = []
    for r, z in profile[1:-1]:
        start = len(verts)
        for x, y in _ellipse(n, r * sx, r * sy):
            verts.append((x, y, z))
        rings.append(start)
    top = len(verts)
    verts.append((0.0, 0.0, profile[-1][1]))
    first = rings[0]
    for i in range(n):
        faces.append((bottom, first + (i + 1) % n, first + i))
    for a, b in zip(rings, rings[1:]):
        for i in range(n):
            j = (i + 1) % n
            faces.append((a + i, a + j, b + j, b + i))
    last = rings[-1]
    for i in range(n):
        faces.append((last + i, last + (i + 1) % n, top))
    return verts, faces, set(range(len(faces)))


def ghost_geometry(kind, size, segments=32, top=0.0):
    """(verts, faces, smooth_face_indices) of the ghost shape in LOCAL space.

    ``size`` = full (X, Y, Z) extents; ``top`` = Cone top size as a fraction of
    the bottom (0 = pointed)."""
    sx, sy, sz = (max(1e-4, float(v)) for v in size)
    n = max(8, int(segments))
    hz = sz / 2.0
    if kind == 'BOX':
        x, y = sx / 2, sy / 2
        verts = [(-x, -y, -hz), (x, -y, -hz), (x, y, -hz), (-x, y, -hz),
                 (-x, -y, hz), (x, -y, hz), (x, y, hz), (-x, y, hz)]
        faces = [(3, 2, 1, 0), (4, 5, 6, 7), (0, 1, 5, 4), (1, 2, 6, 5), (2, 3, 7, 6), (3, 0, 4, 7)]
        return verts, faces, set()
    if kind == 'CYLINDER':
        loop = _ellipse(n, sx / 2, sy / 2)
        return _prism(loop, loop, -hz, hz)
    if kind == 'PILL':
        loop = stadium(n, sx, sy)
        return _prism(loop, loop, -hz, hz)
    if kind == 'CONE':
        t = max(0.0, min(1.0, float(top)))
        bottom = _ellipse(n, sx / 2, sy / 2)
        if t < 1e-3:
            verts = _ring(bottom, -hz) + [(0.0, 0.0, hz)]
            apex = n
            faces = [tuple(range(n - 1, -1, -1))]
            faces += [(i, (i + 1) % n, apex) for i in range(n)]
            return verts, faces, set(range(1, 1 + n))
        return _prism(bottom, [(x * t, y * t) for x, y in bottom], -hz, hz)
    rings = max(4, n // 2)
    if kind == 'SPHERE':
        prof = [(math.sin(math.pi * i / rings), -math.cos(math.pi * i / rings) * hz) for i in range(rings + 1)]
        return _lathe(prof, n, sx / 2, sy / 2)
    if kind == 'CAPSULE':
        # round ends of radius = half the smaller XY size, straight middle
        rc = min(sx, sy) / 2.0
        rc = min(rc, hz)
        half = hz - rc
        quarter = max(2, rings // 2)
        prof = []
        for i in range(quarter + 1):          # bottom cap: pole -> equator
            a = math.pi / 2 * i / quarter
            prof.append((math.sin(a), -half - rc * math.cos(a)))
        for i in range(quarter + 1):          # top cap: equator -> pole
            a = math.pi / 2 * i / quarter
            prof.append((math.cos(a), half + rc * math.sin(a)))
        if half < 1e-6:
            prof.pop(quarter + 1)             # no straight part: equator only once
        return _lathe(prof, n, sx / 2, sy / 2)
    raise ValueError('Unknown shape: ' + str(kind))


def signed_volume(verts, faces):
    """> 0 when the faces point outwards (used by the tests)."""
    vol = 0.0
    for f in faces:
        a = Vector(verts[f[0]])
        for i in range(1, len(f) - 1):
            vol += a.dot(Vector(verts[f[i]]).cross(Vector(verts[f[i + 1]]))) / 6.0
    return vol


def ghost_matrix(location, rotation):
    q = Quaternion(rotation)
    if q.magnitude < 1e-9:
        q = Quaternion()
    return Matrix.LocRotScale(Vector(location), q.normalized(), None)


def place_handles(location, rotation, size, spin=0.0):
    """World matrices of the handles.  Each size arrow starts on the OPPOSITE
    face (which stays fixed while it is dragged) and points along its own axis;
    its value (``offset``) is the full size on that axis."""
    m = ghost_matrix(location, rotation)
    rot = m.to_3x3()
    out = {}
    for i, axis in enumerate('XYZ'):
        for sign, tag in ((1, '+'), (-1, '-')):
            d = Vector((0.0, 0.0, 0.0))
            d[i] = sign
            origin = m @ (-d * size[i] / 2.0)
            out[axis + tag] = _basis(origin, rot @ d, rot @ Vector((0.0, 0.0, 1.0)) if i != 2
                                     else rot @ Vector((1.0, 0.0, 0.0)))
    unspin = Quaternion(rotation).normalized() @ Quaternion((0.0, 0.0, 1.0), -spin)
    out['spin'] = _basis(Vector(location), unspin @ Vector((0.0, 0.0, 1.0)), unspin @ Vector((1.0, 0.0, 0.0)))
    return out


def _basis(origin, z, x_hint):
    z = Vector(z).normalized()
    x = Vector(x_hint)
    x = x - z * x.dot(z)
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def resize_face(location, rotation, size, axis, sign, new_size, minimum=1e-3):
    """Asymmetric resize: the face on ``sign`` side of ``axis`` moves, the
    opposite face stays.  Returns (location, size)."""
    new_size = max(minimum, float(new_size))
    size = list(size)
    delta = new_size - size[axis]
    size[axis] = new_size
    d = Vector((0.0, 0.0, 0.0))
    d[axis] = sign * delta / 2.0
    loc = Vector(location) + Quaternion(rotation).normalized() @ d
    return loc, size


def align_rotation(normal):
    """Rotation whose Z axis is ``normal``."""
    n = Vector(normal)
    if n.length < 1e-9:
        return Quaternion()
    return Vector((0.0, 0.0, 1.0)).rotation_difference(n.normalized())


# -----------------------------------------------------------------------------
# State
# -----------------------------------------------------------------------------


def _redraw(self, context):
    try:
        for window in context.window_manager.windows:
            for area in window.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (AttributeError, ReferenceError):
        pass


class MCH_PG_Place(bpy.types.PropertyGroup):
    show: BoolProperty(name='Show Ghost', default=True, update=_redraw,
                       description='Semi-transparent shape to place with Enter (Alt+Enter: subtract)')
    placed: BoolProperty(default=False, options={'HIDDEN'})
    kind: EnumProperty(name='Shape', items=KIND_ITEMS, default='BOX', update=_redraw)
    size: FloatVectorProperty(name='Size', size=3, default=(1.0, 1.0, 1.0), min=0.001, soft_max=20.0,
                              subtype='XYZ_LENGTH', unit='LENGTH', update=_redraw)
    location: FloatVectorProperty(name='Location', size=3, subtype='TRANSLATION', unit='LENGTH',
                                  update=_redraw)
    rotation: FloatVectorProperty(name='Rotation', size=4, subtype='QUATERNION',
                                  default=(1.0, 0.0, 0.0, 0.0), update=_redraw)
    spin: FloatProperty(default=0.0, options={'HIDDEN'})
    top: FloatProperty(name='Top Size', default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=_redraw,
                       description='Cone top as a fraction of the bottom (0 = pointed)')
    segments: IntProperty(name='Segments', default=32, min=8, max=256, update=_redraw)
    merge: EnumProperty(name='Seam', items=MERGE_ITEMS, default='HARD')
    finish_width: FloatProperty(name='Seam Width', default=0.03, min=0.0, soft_max=0.5, unit='LENGTH')
    finish_segments: IntProperty(name='Seam Segments', default=3, min=1, max=16)
    align_surface: BoolProperty(name='Align to Surface', default=True,
                                description='A click on a mesh turns the shape\'s Z axis to the surface normal')
    subtract: BoolProperty(default=False, options={'HIDDEN'}, update=_redraw)
    show_live: BoolProperty(name='Live Parametric Primitives', default=False)
    last: StringProperty(default='', options={'HIDDEN'})


def state(context):
    wm = getattr(context, 'window_manager', None)
    return getattr(wm, 'mch_place', None) if wm is not None else None


def ensure_placed(context):
    """First use: put the ghost at the 3D cursor."""
    st = state(context)
    if st is not None and not st.placed:
        st.location = context.scene.cursor.location
        st.placed = True
    return st


def ghost_visible(context):
    st = state(context)
    if st is None or not st.show or context.mode != 'OBJECT':
        return False
    if not ts.is_mecha_workspace(getattr(context, 'workspace', None)):
        return False
    try:
        if ts.effective_tool(context) != 'PRIMITIVE':
            return False
    except (AttributeError, KeyError, TypeError):
        return False
    from . import station_primitive
    ob = context.active_object
    # editing a live Station Primitive: its own handles, no ghost on top
    return not (ob is not None and ob.select_get() and station_primitive.is_live(ob))


# -----------------------------------------------------------------------------
# Enter / Alt+Enter
# -----------------------------------------------------------------------------


def ghost_mesh(st, name='MCH_Place_Mesh'):
    """Real mesh of the ghost (local space).  Its faces carry the cutter flag,
    so the seam-only finish knows which faces came from the shape."""
    verts, faces, smooth = ghost_geometry(st.kind, st.size, st.segments, st.top)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.update()
    for poly in me.polygons:
        poly.use_smooth = poly.index in smooth
    attr = me.attributes.new(cg.CUTTER_ATTR, 'BOOLEAN', 'FACE')
    attr.data.foreach_set('value', [True] * len(me.polygons))
    return me


def _world_bounds(ob, depsgraph):
    ev = ob.evaluated_get(depsgraph)
    pts = [ev.matrix_world @ Vector(c) for c in ev.bound_box]
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


def _bvh_world(ob, depsgraph):
    from mathutils.bvhtree import BVHTree
    ev = ob.evaluated_get(depsgraph)
    me = ev.to_mesh()
    try:
        mw = ev.matrix_world
        verts = [mw @ v.co for v in me.vertices]
        polys = [tuple(p.vertices) for p in me.polygons]
    finally:
        ev.to_mesh_clear()
    if not polys:
        return None, []
    return BVHTree.FromPolygons(verts, polys), verts


def _inside(bvh, point):
    """Ray parity test (an odd number of crossings = inside)."""
    direction = Vector((0.5773, 0.5774, 0.5773)).normalized()
    origin = Vector(point)
    hits = 0
    for _ in range(256):
        loc, _n, _i, _d = bvh.ray_cast(origin, direction)
        if loc is None:
            break
        hits += 1
        origin = loc + direction * 1e-5
    return hits % 2 == 1


def overlapping_meshes(context, matrix, verts, faces):
    """Visible mesh objects the ghost (world ``matrix``) touches or contains."""
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    world = [matrix @ Vector(v) for v in verts]
    gmin = Vector((min(p.x for p in world), min(p.y for p in world), min(p.z for p in world)))
    gmax = Vector((max(p.x for p in world), max(p.y for p in world), max(p.z for p in world)))
    ghost = BVHTree.FromPolygons(world, faces)
    centre = matrix.translation
    out = []
    for ob in context.view_layer.objects:
        if ob.type != 'MESH' or not ob.visible_get() or ob.name.startswith('MCH_Cutter'):
            continue
        lo, hi = _world_bounds(ob, dg)
        if any(hi[i] < gmin[i] or lo[i] > gmax[i] for i in range(3)):
            continue
        bvh, overts = _bvh_world(ob, dg)
        if bvh is None:
            continue
        if bvh.overlap(ghost) or _inside(bvh, centre) or (overts and _inside(ghost, overts[0])):
            out.append(ob)
    return out


def pick_union_target(context, candidates, centre):
    """One mesh to merge into: the active object if it is touched, else the
    nearest one."""
    if not candidates:
        return None
    active = context.view_layer.objects.active
    if active in candidates:
        return active
    return min(candidates, key=lambda o: (o.matrix_world.translation - Vector(centre)).length)


def _object_scale(ob):
    s = ob.matrix_world.to_scale()
    return max(1e-6, (abs(s.x) + abs(s.y) + abs(s.z)) / 3.0)


def commit(context, st, subtract=False):
    """Merge (or carve) the ghost.  Returns a report string; raises
    cg.CutError when nothing could be done (the scene is unchanged)."""
    from . import station_primitive
    if context.mode != 'OBJECT':
        raise cg.CutError('Primitive placement works in Object Mode.')
    ensure_placed(context)
    matrix = ghost_matrix(st.location, st.rotation)
    verts, faces, _smooth = ghost_geometry(st.kind, st.size, st.segments, st.top)
    targets = overlapping_meshes(context, matrix, verts, faces)
    label = dict((k, l) for k, l, _d in KIND_ITEMS)[st.kind]
    solver = getattr(getattr(context.scene, 'mch_cut', None), 'solver', 'AUTO')
    if subtract:
        if not targets:
            raise cg.CutError('Subtract: the shape does not touch any mesh; nothing was changed.')
    else:
        target = pick_union_target(context, targets, matrix.translation)
        if target is None:
            me = ghost_mesh(st, 'MCH_' + st.kind.title())
            cg.remove_cutter_attribute(me)
            ob = bpy.data.objects.new('MCH_' + st.kind.title(), me)
            (context.collection or context.scene.collection).objects.link(ob)
            ob.matrix_world = matrix
            for other in context.selected_objects:
                other.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            st.last = ob.name
            return f'{label} added as new object "{ob.name}" (it touched no mesh)'
        targets = [target]
    cutter = cg.link_temp_object(context, ghost_mesh(st), 'MCH_Cutter_Place')
    cutter.matrix_world = matrix
    done, failed, temp = [], [], []
    try:
        for t in targets:
            try:
                cg.check_target(t)
                station_primitive.freeze(t)
                cg.ensure_real_mesh(context, t)
                me, _solver = cg.boolean_result(context, t, cutter, 'DIFFERENCE' if subtract else 'UNION',
                                                solver)
                temp.append(me)
                if st.merge != 'HARD':
                    cg.finish_new_edges(me, st.merge, st.finish_width / _object_scale(t), st.finish_segments,
                                        0.5, clamp=True, label='Seam')
                cg.commit_mesh(t, me)
                done.append(t)
            except (cg.CutError, RuntimeError) as ex:
                if len(targets) == 1:
                    raise
                failed.append(f'{t.name} ({str(ex).splitlines()[0][:60]})')
    finally:
        cg.remove_object_and_mesh(cutter)
        for me in temp:
            try:
                bpy.data.meshes.remove(me)
            except ReferenceError:
                pass
    if not done:
        raise cg.CutError('Nothing was changed. ' + '; '.join(failed))
    for other in context.selected_objects:
        other.select_set(False)
    for t in done:
        t.select_set(True)
    context.view_layer.objects.active = done[0]
    st.last = done[0].name
    names = ', '.join(t.name for t in done)
    seam = '' if st.merge == 'HARD' else f' | {st.merge.title()} seam'
    tail = (' | skipped: ' + '; '.join(failed)) if failed else ''
    return (f'{label} subtracted from {names}' if subtract else f'{label} merged into {names}') + seam + tail


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class MCH_OT_place_commit(bpy.types.Operator):
    """Enter: merge the ghost shape into the mesh it overlaps (new object if none).
    Alt+Enter: subtract it from every mesh it overlaps"""
    bl_idname = 'mch.place_commit'
    bl_label = 'Place Primitive'
    bl_options = {'REGISTER', 'UNDO'}
    subtract: BoolProperty(name='Subtract', default=False, options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return ('Subtract the shape from every mesh it overlaps  (Alt+Enter)' if properties.subtract else
                'Merge the shape into the mesh it overlaps; touching nothing = new object  (Enter)')

    @classmethod
    def poll(cls, context):
        return state(context) is not None and context.mode == 'OBJECT'

    def execute(self, context):
        st = state(context)
        try:
            msg = commit(context, st, self.subtract)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        finally:
            st.subtract = False
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_place_key(bpy.types.Operator):
    """Enter / Alt+Enter while the ghost is shown (gated: elsewhere the key keeps its meaning)"""
    bl_idname = 'mch.place_key'
    bl_label = 'Place Primitive (key)'
    bl_options = {'INTERNAL'}
    subtract: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and ghost_visible(context)

    def execute(self, context):
        return bpy.ops.mch.place_commit('EXEC_DEFAULT', subtract=self.subtract)


class MCH_OT_place_alt(bpy.types.Operator):
    """Alt held: the ghost turns red (subtract preview).  The key passes on."""
    bl_idname = 'mch.place_alt'
    bl_label = 'Ghost Subtract Preview'
    bl_options = {'INTERNAL'}
    on: BoolProperty(default=True, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return ghost_visible(context)

    def invoke(self, context, event):
        st = state(context)
        if st.subtract != self.on:
            st.subtract = self.on
        return {'PASS_THROUGH'}

    def execute(self, context):
        state(context).subtract = self.on
        return {'FINISHED'}


def _ray_place(context, region, rv3d, xy):
    from bpy_extras import view3d_utils
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    dg = context.evaluated_depsgraph_get()
    hit, loc, normal, _i, _ob, _m = context.scene.ray_cast(dg, origin, direction)
    if hit:
        return loc, normal
    st = state(context)
    plane_co = Vector(st.location)
    plane_no = -direction
    denom = direction.dot(plane_no)
    if abs(denom) < 1e-9:
        return None, None
    t = (plane_co - origin).dot(plane_no) / denom
    return origin + direction * t, None


class MCH_OT_place_click(bpy.types.Operator):
    """Click with the Primitive tool: put the ghost there (on the surface under the mouse)"""
    bl_idname = 'mch.place_click'
    bl_label = 'Move Ghost Here'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and ghost_visible(context)

    def invoke(self, context, event):
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None or region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        st = ensure_placed(context)
        loc, normal = _ray_place(context, region, rv3d, (event.mouse_region_x, event.mouse_region_y))
        if loc is None:
            return {'PASS_THROUGH'}
        st.location = loc
        if normal is not None and st.align_surface:
            st.rotation = align_rotation(normal)
            st.spin = 0.0
        return {'FINISHED'}


class MCH_OT_place_shape(bpy.types.Operator):
    """Shape of the ghost"""
    bl_idname = 'mch.place_shape'
    bl_label = 'Ghost Shape'
    bl_options = {'INTERNAL'}
    kind: EnumProperty(items=KIND_ITEMS, default='BOX')

    @classmethod
    def description(cls, context, properties):
        return dict((k, d) for k, _l, d in KIND_ITEMS).get(properties.kind, '')

    def execute(self, context):
        st = ensure_placed(context)
        if st.kind != self.kind:
            st.kind = self.kind
            if self.kind == 'PILL' and abs(st.size[0] - st.size[1]) < 1e-6:
                st.size = (st.size[0] * 2.0, st.size[1], st.size[2])     # show the pill right away
        st.show = True
        try:
            if ts.effective_tool(context) != 'PRIMITIVE':
                from .workspace_ui import activate_mecha_tool
                activate_mecha_tool(context, 'PRIMITIVE')
        except (AttributeError, KeyError, TypeError, RuntimeError):
            pass
        return {'FINISHED'}


class MCH_OT_place_rotate(bpy.types.Operator):
    """Turn the ghost 90 degrees around its own axis (or reset)"""
    bl_idname = 'mch.place_rotate'
    bl_label = 'Rotate Ghost'
    bl_options = {'INTERNAL'}
    axis: EnumProperty(items=[('X', 'X', ''), ('Y', 'Y', ''), ('Z', 'Z', ''), ('RESET', 'Reset', '')],
                       default='Z')

    def execute(self, context):
        st = ensure_placed(context)
        if self.axis == 'RESET':
            st.rotation = Quaternion()
            st.spin = 0.0
            return {'FINISHED'}
        v = Vector((0.0, 0.0, 0.0))
        v['XYZ'.index(self.axis)] = 1.0
        st.rotation = Quaternion(st.rotation).normalized() @ Quaternion(v, math.pi / 2)
        return {'FINISHED'}


class MCH_OT_place_to_cursor(bpy.types.Operator):
    """Put the ghost at the 3D cursor"""
    bl_idname = 'mch.place_to_cursor'
    bl_label = 'Ghost to 3D Cursor'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        st = state(context)
        st.location = context.scene.cursor.location
        st.placed = True
        st.show = True
        return {'FINISHED'}


class MCH_OT_place_hide(bpy.types.Operator):
    """Esc with the ghost shown: hide it and go to Select / Move"""
    bl_idname = 'mch.place_hide'
    bl_label = 'Hide Ghost'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and ghost_visible(context)

    def execute(self, context):
        state(context).show = False
        try:
            bpy.ops.mch.select_move()
        except (RuntimeError, AttributeError):
            pass
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Handles
# -----------------------------------------------------------------------------


def make_size_accessors(axis, sign):
    def get():
        st = state(bpy.context)
        return st.size[axis] if st is not None else 1.0

    def set_(value):
        st = state(bpy.context)
        if st is None:
            return
        loc, size = resize_face(st.location, st.rotation, st.size, axis, sign, value)
        st.size = size
        st.location = loc
    return get, set_


def _spin_get():
    st = state(bpy.context)
    return st.spin if st is not None else 0.0


def _spin_set(value):
    st = state(bpy.context)
    if st is None:
        return
    delta = value - st.spin
    st.rotation = Quaternion(st.rotation).normalized() @ Quaternion((0.0, 0.0, 1.0), delta)
    st.spin = value


def _move_get():
    st = state(bpy.context)
    return tuple(st.location) if st is not None else (0.0, 0.0, 0.0)


def _move_set(value):
    st = state(bpy.context)
    if st is not None:
        st.location = value


class MCH_GGT_place(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_place'
    bl_label = 'Primitive Ghost Handles'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        return ghost_visible(context)

    def setup(self, context):
        self.items = {}
        for i, axis in enumerate('XYZ'):
            for sign, tag in ((1, '+'), (-1, '-')):
                gz = self.gizmos.new('GIZMO_GT_arrow_3d')
                get, set_ = make_size_accessors(i, sign)
                gz.target_set_handler('offset', get=get, set=set_)
                gz.draw_style = 'BOX'
                gz.scale_basis = 0.5
                gz.color = ((1.0, 0.35, 0.35), (0.45, 0.9, 0.35), (0.35, 0.6, 1.0))[i]
                gz.alpha = 0.9
                gz.color_highlight = (1.0, 1.0, 1.0)
                gz.alpha_highlight = 1.0
                self.items[axis + tag] = gz
        gz = self.gizmos.new('GIZMO_GT_dial_3d')
        gz.target_set_handler('offset', get=_spin_get, set=_spin_set)
        gz.draw_options = {'ANGLE_VALUE', 'ANGLE_START_Y'}
        gz.scale_basis = 0.6
        gz.color = (1.0, 0.62, 0.16)
        gz.alpha = 0.8
        gz.color_highlight = (1.0, 1.0, 1.0)
        gz.alpha_highlight = 1.0
        self.items['spin'] = gz
        gz = self.gizmos.new('GIZMO_GT_move_3d')
        gz.target_set_handler('offset', get=_move_get, set=_move_set)
        gz.draw_style = 'RING_2D'
        gz.draw_options = {'ALIGN_VIEW', 'FILL'}
        gz.scale_basis = 0.12
        gz.color = (0.9, 0.9, 0.9)
        gz.alpha = 0.6
        gz.color_highlight = (1.0, 0.62, 0.16)
        gz.alpha_highlight = 1.0
        gz.matrix_basis = Matrix.Identity(4)
        self.items['move'] = gz

    def draw_prepare(self, context):
        st = state(context)
        if st is None:
            return
        loc = st.location if st.placed else context.scene.cursor.location
        h = place_handles(loc, st.rotation, st.size, st.spin)
        for name, m in h.items():
            gz = self.items.get(name)
            if gz is not None:
                gz.matrix_basis = m


# -----------------------------------------------------------------------------
# Ghost drawing
# -----------------------------------------------------------------------------

_GHOST_CACHE = {}


def _ghost_tris(st):
    key = (st.kind, tuple(round(v, 6) for v in st.size), st.segments, round(st.top, 4))
    hit = _GHOST_CACHE.get('key')
    if hit is not None and hit[0] == key:
        return hit[1], hit[2]
    verts, faces, _s = ghost_geometry(st.kind, st.size, st.segments, st.top)
    tris, lines = [], []
    for f in faces:
        for i in range(1, len(f) - 1):
            tris.append((f[0], f[i], f[i + 1]))
    # outline: edges whose faces meet at an angle (the silhouette-ish wireframe)
    edge_faces = {}
    for fi, f in enumerate(faces):
        for i in range(len(f)):
            e = tuple(sorted((f[i], f[(i + 1) % len(f)])))
            edge_faces.setdefault(e, []).append(fi)

    def normal(f):
        a, b, c = (Vector(verts[f[0]]), Vector(verts[f[1]]), Vector(verts[f[2]]))
        n = (b - a).cross(c - a)
        return n.normalized() if n.length > 1e-12 else n
    for e, fs in edge_faces.items():
        if len(fs) != 2 or normal(faces[fs[0]]).dot(normal(faces[fs[1]])) < 0.94:
            lines.append(e)
    _GHOST_CACHE['key'] = (key, (verts, tris), lines)
    return (verts, tris), lines


def _draw_ghost():
    try:
        context = bpy.context
        if not ghost_visible(context):
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        st = state(context)
        loc = st.location if st.placed else context.scene.cursor.location
        m = ghost_matrix(loc, st.rotation)
        (verts, tris), lines = _ghost_tris(st)
        world = [tuple(m @ Vector(v)) for v in verts]
        col = COL_SUB if st.subtract else COL_ADD
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_mask_set(False)
        gpu.state.depth_test_set('LESS_EQUAL')
        sh.uniform_float('color', (*col, 0.28))
        batch_for_shader(sh, 'TRIS', {'pos': world}, indices=tris).draw(sh)
        gpu.state.depth_test_set('NONE')
        sh.uniform_float('color', (*col, 0.10))       # faint see-through part behind meshes
        batch_for_shader(sh, 'TRIS', {'pos': world}, indices=tris).draw(sh)
        gpu.state.line_width_set(1.5)
        sh.uniform_float('color', (*col, 0.9))
        batch_for_shader(sh, 'LINES', {'pos': world}, indices=lines).draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.depth_mask_set(True)
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


# -----------------------------------------------------------------------------
# Panel
# -----------------------------------------------------------------------------


def draw_shape_grid(layout, operator_id, current=None, columns=3):
    """Even grid: big thumbnail on top, the name underneath (no staircase)."""
    from .workspace_ui import icon_id
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for kind, label, _d in KIND_ITEMS:
        cell = grid.column(align=True)
        iid = icon_id(ICON_STEM[kind])
        if iid:
            cell.template_icon(icon_value=iid, scale=2.4)
        op = cell.operator(operator_id, text=label, icon='NONE' if iid else FALLBACK_ICON[kind],
                           depress=(kind == current))
        op.kind = kind


def draw(layout, context):
    st = state(context)
    if st is None:
        return
    box = layout.box()
    head = box.row(align=True)
    head.label(text='PLACE SHAPES', icon='MESH_CUBE')
    head.prop(st, 'show', text='', icon='HIDE_OFF' if st.show else 'HIDE_ON')
    draw_shape_grid(box, 'mch.place_shape', st.kind)
    col = box.column(align=True)
    col.prop(st, 'size')
    if st.kind == 'CONE':
        col.prop(st, 'top', slider=True)
    if st.kind != 'BOX':
        col.prop(st, 'segments')
    row = box.row(align=True)
    row.label(text='Turn 90')
    for a in ('X', 'Y', 'Z'):
        row.operator('mch.place_rotate', text=a).axis = a
    row.operator('mch.place_rotate', text='', icon='LOOP_BACK').axis = 'RESET'
    row = box.row(align=True)
    row.prop(st, 'align_surface')
    row.operator('mch.place_to_cursor', text='', icon='PIVOT_CURSOR')
    box.label(text='Seam where it merges')
    box.row(align=True).prop(st, 'merge', expand=True)
    if st.merge != 'HARD':
        r = box.row(align=True)
        r.prop(st, 'finish_width', text='Width')
        if st.merge == 'SMOOTH':
            r.prop(st, 'finish_segments', text='Seg')
    row = box.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.place_commit', text='Add  (Enter)', icon='ADD').subtract = False
    row.operator('mch.place_commit', text='Subtract  (Alt+Enter)', icon='REMOVE').subtract = True
    sub = box.column(align=True)
    sub.scale_y = 0.8
    sub.label(text='Click a mesh: move the ghost there', icon='INFO')
    sub.label(text='Arrows: size (one side) | dial: turn | ring: move')
    sub.label(text='Enter merges into the mesh it touches; Esc: hide')


class MCH_PT_place_shapes(bpy.types.Panel):
    """Sidebar > Mecha Lab: the shapes are always one click away (0.14).
    With the Primitive tool on, the full controls are in the main panel."""
    bl_idname = 'MCH_PT_place_shapes'
    bl_label = 'Primitive Shapes'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 5

    @classmethod
    def poll(cls, context):
        if state(context) is None or not hasattr(context.scene, 'mch_settings'):
            return False
        try:
            return ts.effective_tool(context) != 'PRIMITIVE'
        except (AttributeError, KeyError, TypeError):
            return True

    def draw(self, context):
        st = state(context)
        self.layout.label(text='Click a shape: Primitive tool + ghost', icon='INFO')
        draw_shape_grid(self.layout, 'mch.place_shape', st.kind)


# -----------------------------------------------------------------------------
# Registration
# -----------------------------------------------------------------------------

CLASSES = (MCH_PG_Place, MCH_OT_place_commit, MCH_OT_place_key, MCH_OT_place_alt, MCH_OT_place_click,
           MCH_OT_place_shape, MCH_OT_place_rotate, MCH_OT_place_to_cursor, MCH_OT_place_hide, MCH_GGT_place,
           MCH_PT_place_shapes)
TOOL_KEYMAP = (
    # click = move the ghost there; drag = box select; Shift+click = select
    ('mch.place_click', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
    ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
     {'properties': [('toggle', True)]}),
    ('view3d.select_box', {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG'}, {'properties': [('mode', 'SET')]}),
    ('view3d.select_box', {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG', 'shift': True},
     {'properties': [('mode', 'ADD')]}),
    ('view3d.select_box', {'type': 'LEFTMOUSE', 'value': 'CLICK_DRAG', 'ctrl': True},
     {'properties': [('mode', 'SUB')]}),
    ('mch.place_key', {'type': 'RET', 'value': 'PRESS'}, None),
    ('mch.place_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS'}, None),
    ('mch.place_key', {'type': 'RET', 'value': 'PRESS', 'alt': True}, {'properties': [('subtract', True)]}),
    ('mch.place_key', {'type': 'NUMPAD_ENTER', 'value': 'PRESS', 'alt': True},
     {'properties': [('subtract', True)]}),
    ('mch.place_alt', {'type': 'LEFT_ALT', 'value': 'PRESS', 'any': True}, {'properties': [('on', True)]}),
    ('mch.place_alt', {'type': 'RIGHT_ALT', 'value': 'PRESS', 'any': True}, {'properties': [('on', True)]}),
    ('mch.place_alt', {'type': 'LEFT_ALT', 'value': 'RELEASE', 'any': True}, {'properties': [('on', False)]}),
    ('mch.place_alt', {'type': 'RIGHT_ALT', 'value': 'RELEASE', 'any': True}, {'properties': [('on', False)]}),
    ('mch.primitive_rmb', {'type': 'RIGHTMOUSE', 'value': 'PRESS'}, None),
    ('mch.space_tools', {'type': 'SPACE', 'value': 'PRESS'}, None),
    ('mch.place_hide', {'type': 'ESC', 'value': 'PRESS'}, None),
    ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
)


def register():
    global _draw_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.WindowManager.mch_place = PointerProperty(type=MCH_PG_Place)
    if not bpy.app.background and _draw_handle is None:
        _draw_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_ghost, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _draw_handle
    if _draw_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_draw_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _draw_handle = None
    if hasattr(bpy.types.WindowManager, 'mch_place'):
        del bpy.types.WindowManager.mch_place
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
