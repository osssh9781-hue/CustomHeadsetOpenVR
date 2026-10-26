"""0.24 Screw Stamp: click on a surface to place a screw head, aligned to it.

Four heads (from the user's sketch): Dome (round button), Post (tall pin),
Socket (cylinder with a round hole in the top) and Cross (flat head with a +
slot).  Every click places one screw object parented to the mesh under the
mouse (it follows the plate), sunk a little into the surface so curved
surfaces leave no gap.  Size / height / recess stay live per screw until Join;
Alt + click removes the screw under the mouse.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector
from mathutils.geometry import delaunay_2d_cdt
from . import target_rules

KINDS = (
    ('DOME', 'Dome', 'Round button head', 'MESH_UVSPHERE'),
    ('POST', 'Post', 'Tall pin with a chamfered top', 'MESH_CYLINDER'),
    ('SOCKET', 'Socket', 'Cylinder with a round hole in the top', 'MESH_TORUS'),
    ('CROSS', 'Cross', 'Flat head with a + slot', 'ADD'),
)
# default height / radius per head
HEIGHTS = {'DOME': 0.45, 'POST': 1.4, 'SOCKET': 0.9, 'CROSS': 0.3}
SEGMENTS = 32
SINK = 0.25                   # x radius below the surface


# -----------------------------------------------------------------------------
# Geometry (local: base on z = 0, up = +Z)
# -----------------------------------------------------------------------------


def revolve(profile, segments=SEGMENTS):
    """Closed solid from a (radius, z) profile, top of the axis first, bottom of
    the axis last (radius 0 points become single axis verts)."""
    verts, rings = [], []
    for r, z in profile:
        if r <= 1e-12:
            rings.append([len(verts)])
            verts.append((0.0, 0.0, z))
        else:
            ring = []
            for i in range(segments):
                a = 2 * math.pi * i / segments
                ring.append(len(verts))
                verts.append((r * math.cos(a), r * math.sin(a), z))
            rings.append(ring)
    faces = []
    for ra, rb in zip(rings, rings[1:]):
        for i in range(segments):
            j = (i + 1) % segments
            if len(ra) == 1:
                faces.append((ra[0], rb[i], rb[j]))
            elif len(rb) == 1:
                faces.append((ra[j], ra[i], rb[0]))
            else:
                faces.append((ra[j], ra[i], rb[i], rb[j]))
    return verts, faces


def _cross_mesh(r, h, sink, slot_w, slot_l, depth, segments=SEGMENTS):
    """Flat disc with a + slot: top ring around the cross by CDT, slot walls,
    slot floor, side wall and bottom."""
    w, L = slot_w * 0.5, slot_l * 0.5
    cross = [(L, w), (w, w), (w, L), (-w, L), (-w, w), (-L, w), (-L, -w), (-w, -w), (-w, -L), (w, -L), (w, -w),
             (L, -w)]
    circle = [(r * math.cos(2 * math.pi * i / segments), r * math.sin(2 * math.pi * i / segments))
              for i in range(segments)]
    pts = [Vector(p) for p in circle + cross]
    nc = len(circle)
    edges = [(i, (i + 1) % nc) for i in range(nc)] + [(nc + i, nc + (i + 1) % 12) for i in range(12)]
    out_v, _e, out_f, _vo, _eo, _fo = delaunay_2d_cdt(pts, edges, [], 0, 1e-9)

    def inside_cross(x, y):
        return (abs(x) < L and abs(y) < w) or (abs(x) < w and abs(y) < L)

    verts = [(v.x, v.y, h) for v in out_v]
    faces = []
    for f in out_f:
        cx = sum(out_v[i].x for i in f) / len(f)
        cy = sum(out_v[i].y for i in f) / len(f)
        if not inside_cross(cx, cy) and math.hypot(cx, cy) < r:
            faces.append(tuple(f))
    # map the original circle / cross points to the CDT verts
    def find(p):
        return min(range(len(out_v)), key=lambda k: (out_v[k].x - p[0]) ** 2 + (out_v[k].y - p[1]) ** 2)
    top_c = [find(p) for p in circle]
    top_x = [find(p) for p in cross]
    zf = h - depth
    floor = []
    for x, y in cross:
        floor.append(len(verts))
        verts.append((x, y, zf))
    bot = []
    for x, y in circle:
        bot.append(len(verts))
        verts.append((x, y, -sink))
    for i in range(12):                       # slot walls
        j = (i + 1) % 12
        faces.append((top_x[i], floor[i], floor[j], top_x[j]))
    # slot floor: the + as 5 quads (centre square + 4 arms)
    fi = floor
    faces += [(fi[1], fi[4], fi[7], fi[10]), (fi[0], fi[1], fi[10], fi[11]), (fi[2], fi[3], fi[4], fi[1]),
              (fi[5], fi[6], fi[7], fi[4]), (fi[8], fi[9], fi[10], fi[7])]
    for i in range(nc):                       # side wall
        j = (i + 1) % nc
        faces.append((top_c[j], top_c[i], bot[i], bot[j]))
    faces.append(tuple(reversed(bot)))
    return verts, faces


def head_mesh(kind, r, h, recess=0.5, name='MCH_Screw'):
    sink = r * SINK
    if kind == 'DOME':
        n = 8
        prof = [(0.0, h)] + [(r * math.sin(math.pi * 0.5 * k / n), h * math.cos(math.pi * 0.5 * k / n))
                             for k in range(1, n + 1)] + [(r, -sink), (0.0, -sink)]
        verts, faces = revolve(prof)
    elif kind == 'POST':
        c = min(r * 0.15, h * 0.3)
        verts, faces = revolve([(0.0, h), (r - c, h), (r, h - c), (r, -sink), (0.0, -sink)])
    elif kind == 'SOCKET':
        c = min(r * 0.1, h * 0.2)
        ri = r * 0.55
        d = max(1e-5, min(h * 0.95, h * recess))
        verts, faces = revolve([(0.0, h - d), (ri, h - d), (ri, h), (r - c, h), (r, h - c), (r, -sink),
                                (0.0, -sink)])
    else:
        d = max(1e-5, min(h * 0.9, h * recess))
        verts, faces = _cross_mesh(r, h, sink, r * 0.22, r * 1.4, d)
    me = bpy.data.meshes.new(name)
    me.from_pydata(verts, [], faces)
    me.validate()
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=r * 1e-5)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.to_mesh(me)
    finally:
        bm.free()
    me.shade_smooth()
    try:
        me.set_sharp_from_angle(angle=math.radians(40))
    except (AttributeError, TypeError):
        pass
    me.update()
    return me


# -----------------------------------------------------------------------------
# Live screws
# -----------------------------------------------------------------------------

_SYNC = [False]


def is_screw(ob):
    s = getattr(ob, 'mch_screw', None)
    return bool(s is not None and s.live)


def rebuild(ob):
    s = ob.mch_screw
    me = head_mesh(s.kind, s.radius, s.radius * s.height, s.recess, name=ob.name)
    old = ob.data
    for m in old.materials:
        me.materials.append(m)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)


def _changed(self, context):
    if _SYNC[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_screw(ob):
        rebuild(ob)
        st = context.scene.mch_screw
        st.kind, st.radius, st.height, st.recess = self.kind, self.radius, self.height, self.recess


def _kind_changed(self, context):
    """Another head: its usual height."""
    if not _SYNC[0]:
        _SYNC[0] = True
        try:
            self.height = HEIGHTS[self.kind]
        finally:
            _SYNC[0] = False
    _changed(self, context)


_KIND_ITEMS = [(k[0], k[1], k[2], k[3], i) for i, k in enumerate(KINDS)]


class MCH_PG_Screw(bpy.types.PropertyGroup):
    live: BoolProperty(default=False)
    kind: EnumProperty(name='Head', items=_KIND_ITEMS, default='DOME', update=_kind_changed)
    radius: FloatProperty(name='Size', default=0.03, min=0.0001, soft_max=1.0, unit='LENGTH', precision=4,
                          update=_changed, description='Screw head radius')
    height: FloatProperty(name='Height', default=0.45, min=0.02, soft_max=4.0, update=_changed,
                          description='Height as a factor of the size')
    recess: FloatProperty(name='Hole Depth', default=0.5, min=0.05, max=0.95, subtype='FACTOR', update=_changed,
                          description='Socket / Cross: depth of the hole or slot (part of the height)')
    spin: FloatProperty(name='Spin', default=0.0, subtype='ANGLE', description='Turn around the surface normal')


def _scene_kind(self, _context):
    self.height = HEIGHTS[self.kind]


class MCH_PG_ScrewScene(bpy.types.PropertyGroup):
    kind: EnumProperty(name='Head', items=_KIND_ITEMS, default='DOME', update=_scene_kind)
    radius: FloatProperty(name='Size', default=0.03, min=0.0001, soft_max=1.0, unit='LENGTH', precision=4)
    height: FloatProperty(name='Height', default=0.45, min=0.02, soft_max=4.0)
    recess: FloatProperty(name='Hole Depth', default=0.5, min=0.05, max=0.95, subtype='FACTOR')
    random_spin: BoolProperty(name='Random Spin', default=True, description='Cross heads: random slot angle')


def _view_ray(context, xy):
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    return o, d


def ray_hit(context, origin, direction, skip_screws=True):
    """First mesh hit (screws skipped when asked): (object, location, normal)."""
    dg = context.evaluated_depsgraph_get()
    o = Vector(origin)
    d = Vector(direction).normalized()
    for _ in range(16):
        hit, loc, nrm, _i, hob, _m = target_rules.scene_ray(context, dg, o, d)
        if not hit or hob is None:
            return None, None, None
        real = bpy.data.objects.get(hob.name)
        if real is not None and real.type == 'MESH' and not (skip_screws and is_screw(real)):
            if nrm.dot(d) > 0:
                nrm = -nrm
            return real, loc, nrm.normalized()
        if real is not None and not skip_screws and is_screw(real):
            return real, loc, nrm
        o = loc + d * 1e-5
    return None, None, None


def place(context, target, loc, normal, spin=0.0):
    """One screw on ``target`` at ``loc`` (world), up along ``normal``."""
    st = context.scene.mch_screw
    me = head_mesh(st.kind, st.radius, st.radius * st.height, st.recess, name='Screw')
    ob = bpy.data.objects.new('Screw', me)
    coll = target.users_collection[0] if target.users_collection else context.scene.collection
    coll.objects.link(ob)
    for m in target.data.materials:
        me.materials.append(m)
    rot = Vector((0, 0, 1)).rotation_difference(Vector(normal)).to_matrix().to_4x4() @ Matrix.Rotation(spin, 4, 'Z')
    world = Matrix.Translation(loc) @ rot
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted_safe()
    ob.matrix_world = world
    s = ob.mch_screw
    _SYNC[0] = True
    try:
        s.kind, s.radius, s.height, s.recess, s.spin = st.kind, st.radius, st.height, st.recess, spin
        s.live = True
    finally:
        _SYNC[0] = False
    return ob


class MCH_OT_screw_stamp(bpy.types.Operator):
    """Click: place a screw on the surface under the mouse. Alt + click: remove the screw under the mouse"""
    bl_idname = 'mch.screw_stamp'
    bl_label = 'Screw Stamp'
    bl_options = {'REGISTER', 'UNDO'}
    remove: BoolProperty(default=False, options={'SKIP_SAVE'})
    leave: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        xy = (event.mouse_region_x, event.mouse_region_y)
        if self.leave:
            return self.leave_tool(context, xy)
        o, d = _view_ray(context, xy)
        return self.run(context, o, d)

    def leave_tool(self, context, xy):
        """0.24.5 double-click: the screw the first click just placed is taken back, then the tool is
        left and the object under the mouse selected."""
        import time
        name, when = _LAST
        if name and time.time() - when < 1.0:
            ob = bpy.data.objects.get(name)
            if ob is not None and is_screw(ob):
                me = ob.data
                bpy.data.objects.remove(ob)
                if me.users == 0:
                    bpy.data.meshes.remove(me)
        _LAST[0] = None
        from . import cut_engine
        cut_engine.double_click_leave(context, xy, skip=is_screw)
        return {'FINISHED'}

    def run(self, context, origin, direction):
        if self.remove:
            ob, _l, _n = ray_hit(context, origin, direction, skip_screws=False)
            if ob is None or not is_screw(ob):
                return {'CANCELLED'}
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            return {'FINISHED'}
        target, loc, nrm = ray_hit(context, origin, direction)
        if target is None:
            self.report({'WARNING'}, 'Click on a mesh surface')
            return {'CANCELLED'}
        st = context.scene.mch_screw
        import random
        spin = random.uniform(0, math.pi) if (st.random_spin and st.kind == 'CROSS') else 0.0
        ob = place(context, target, loc, nrm, spin)
        import time
        _LAST[0], _LAST[1] = ob.name, time.time()
        for o_ in context.selected_objects:
            o_.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


def _selected_screws(context):
    return [o for o in context.selected_objects if is_screw(o)]


class MCH_OT_screw_join(bpy.types.Operator):
    """Join the selected screws into the mesh they sit on (no more live changes)"""
    bl_idname = 'mch.screw_join'
    bl_label = 'Join Screws to Surface'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_selected_screws(context))

    def execute(self, context):
        groups = {}
        for s in _selected_screws(context):
            if s.parent is not None and s.parent.type == 'MESH':
                groups.setdefault(s.parent, []).append(s)
        n = 0
        for parent, screws in groups.items():
            import bmesh
            bm = bmesh.new()
            try:
                bm.from_mesh(parent.data)
                inv = parent.matrix_world.inverted_safe()
                for s in screws:
                    me = s.data.copy()
                    me.transform(inv @ s.matrix_world)
                    tmp = bmesh.new()
                    tmp.from_mesh(me)
                    vmap = {v: bm.verts.new(v.co) for v in tmp.verts}
                    for f in tmp.faces:
                        try:
                            nf = bm.faces.new([vmap[v] for v in f.verts])
                            nf.smooth = f.smooth
                        except ValueError:
                            pass
                    tmp.free()
                    bpy.data.meshes.remove(me)
                    old = s.data
                    bpy.data.objects.remove(s)
                    if old.users == 0:
                        bpy.data.meshes.remove(old)
                    n += 1
                bm.to_mesh(parent.data)
            finally:
                bm.free()
            parent.data.update()
        self.report({'INFO'}, f'{n} screw(s) joined')
        return {'FINISHED'}


class MCH_OT_screw_kind(bpy.types.Operator):
    """Screw head for the next clicks (and the selected screws)"""
    bl_idname = 'mch.screw_kind'
    bl_label = 'Screw Head'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=[(k[0], k[1], k[2]) for k in KINDS])

    def execute(self, context):
        context.scene.mch_screw.kind = self.kind
        for s in _selected_screws(context):
            s.mch_screw.kind = self.kind
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_screw
    grid = layout.grid_flow(columns=4, align=True, even_columns=True)
    for kid, label, _d, icon in KINDS:
        grid.operator('mch.screw_kind', text=label, icon=icon, depress=(st.kind == kid)).kind = kid
    ob = context.active_object
    if is_screw(ob):
        s = ob.mch_screw
        box = layout.box()
        box.label(text='SELECTED: ' + ob.name, icon='RADIOBUT_ON')
        col = box.column(align=True)
        col.prop(s, 'radius')
        col.prop(s, 'height')
        if s.kind in {'SOCKET', 'CROSS'}:
            col.prop(s, 'recess')
        box.operator('mch.screw_join', icon='AUTOMERGE_ON')
    else:
        col = layout.column(align=True)
        col.label(text='Next screws:')
        col.prop(st, 'radius')
        col.prop(st, 'height')
        if st.kind in {'SOCKET', 'CROSS'}:
            col.prop(st, 'recess')
        if st.kind == 'CROSS':
            col.prop(st, 'random_spin')
    layout.label(text='Click: place on the surface | Alt + click: remove')


_LAST = [None, 0.0]        # the screw placed by the last click (a double-click takes it back)

TOOL_KEYMAP = (
    ('mch.screw_stamp', {'type': 'LEFTMOUSE', 'value': 'DOUBLE_CLICK'}, {'properties': [('leave', True)]}),
    ('mch.screw_stamp', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
    ('mch.screw_stamp', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, {'properties': [('remove', True)]}),
    ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
)

CLASSES = (MCH_PG_Screw, MCH_PG_ScrewScene, MCH_OT_screw_stamp, MCH_OT_screw_join, MCH_OT_screw_kind)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_screw = PointerProperty(type=MCH_PG_Screw)
    bpy.types.Scene.mch_screw = PointerProperty(type=MCH_PG_ScrewScene)


def unregister():
    for owner in (bpy.types.Object, bpy.types.Scene):
        if hasattr(owner, 'mch_screw'):
            delattr(owner, 'mch_screw')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
