"""0.24.33 Perforate: sci-fi perforated plates - honeycomb / circle / square / diamond holes through the selected
meshes.

The holes are a hidden cutter (one prism per hole, through the whole part along the plate's normal) on a Boolean
modifier, so every slider is live: Pattern, Hole Size, Gap (the web between holes), Rotation, Offset, Margin (no
holes near the edge), Direction (Auto = the thinnest side of the part, or X / Y / Z / View).  A hole is kept only
where the surface is under all of it (and its margin), so irregular outlines get a clean border.  On a mirrored
object the holes go before the Mirror (symmetrical).  Apply makes them real, Remove takes them away.
``hole_shape``, ``lattice``, ``plane_axes`` and ``prisms`` are pure.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

MOD_NAME = 'MCH_Perforate'
MAX_HOLES = 4000
PATTERNS = [
    ('HEX', 'Honeycomb', 'Hexagon holes, staggered (honeycomb grille)'),
    ('CIRCLE', 'Circle', 'Round holes, staggered (speaker grille / perforated metal)'),
    ('SQUARE', 'Square', 'Square holes in a straight grid'),
    ('DIAMOND', 'Diamond', 'Diamond (45 degree square) holes, staggered (mesh guard)'),
]
DIRECTIONS = [
    ('AUTO', 'Auto', 'Through the thinnest side of the part (the plate normal)'),
    ('X', 'X', 'Along the object X axis'), ('Y', 'Y', 'Along the object Y axis'), ('Z', 'Z', 'Along the object Z axis'),
]


# -----------------------------------------------------------------------------
# pure parts
# -----------------------------------------------------------------------------


def hole_shape(pattern, size, sides=24, round_=0.0):
    """The hole outline (2D, CCW, centred).  ``size`` = across (flat to flat for hexagons and squares, the full
    diagonal for diamonds, the diameter for circles)."""
    if pattern == 'HEX':
        r = size / 2.0 / math.cos(math.pi / 6.0)             # flats left / right
        return [(r * math.cos(math.pi / 6 + k * math.pi / 3), r * math.sin(math.pi / 6 + k * math.pi / 3))
                for k in range(6)]
    if pattern == 'CIRCLE':
        n = max(6, int(sides))
        return [(size / 2 * math.cos(2 * math.pi * k / n), size / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    h = size / 2.0
    if pattern == 'DIAMOND':
        return [(h, 0.0), (0.0, h), (-h, 0.0), (0.0, -h)]
    return [(h, -h), (h, h), (-h, h), (-h, -h)]


def outer_radius(pattern, size):
    return {'HEX': size / 2.0 / math.cos(math.pi / 6.0), 'SQUARE': size / math.sqrt(2.0)}.get(pattern, size / 2.0)


def lattice(pattern, size, gap, bounds, rotation=0.0, offset=(0.0, 0.0)):
    """Hole centres (2D) covering ``bounds`` (min u, max u, min v, max v): staggered rows for honeycomb / circles /
    diamonds, a straight grid for squares; turned by ``rotation`` and shifted by ``offset``."""
    u0, u1, v0, v1 = bounds
    pitch = size + gap
    if pattern == 'DIAMOND':
        dx, dy, stagger = pitch, pitch / 2.0, True
    elif pattern == 'SQUARE':
        dx, dy, stagger = pitch, pitch, False
    else:
        dx, dy, stagger = pitch, pitch * math.sqrt(3.0) / 2.0, True
    cu, cv = (u0 + u1) / 2.0, (v0 + v1) / 2.0
    half = math.hypot(u1 - u0, v1 - v0) / 2.0 + pitch
    c, s = math.cos(rotation), math.sin(rotation)
    out = []
    rows = int(half / dy) + 1
    cols = int(half / dx) + 1
    for j in range(-rows, rows + 1):
        shift = dx / 2.0 if stagger and j % 2 else 0.0
        for i in range(-cols, cols + 1):
            x = i * dx + shift + offset[0]
            y = j * dy + offset[1]
            u, v = cu + x * c - y * s, cv + x * s + y * c
            if u0 - pitch <= u <= u1 + pitch and v0 - pitch <= v <= v1 + pitch:
                out.append((u, v))
    return out


def plane_axes(direction, extents):
    """(u, v, w) unit axes in the object's space: w = the drilling direction."""
    axes = [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))]
    k = {'X': 0, 'Y': 1, 'Z': 2}.get(direction)
    if k is None:
        k = min(range(3), key=lambda i: extents[i])
    w = axes[k]
    u, v = axes[(k + 1) % 3], axes[(k + 2) % 3]
    return u, v, w


def prisms(centres, shape, rotation, u, v, w, w0, w1):
    """(verts, faces): one closed prism per hole, from depth w0 to w1 along w."""
    c, s = math.cos(rotation), math.sin(rotation)
    rot = [(x * c - y * s, x * s + y * c) for x, y in shape]
    verts, faces = [], []
    n = len(rot)
    for cu, cv in centres:
        base = len(verts)
        for depth in (w0, w1):
            for x, y in rot:
                verts.append(u * (cu + x) + v * (cv + y) + w * depth)
        faces.append(tuple(base + i for i in range(n - 1, -1, -1)))
        faces.append(tuple(base + n + i for i in range(n)))
        for i in range(n):
            j = (i + 1) % n
            faces.append((base + i, base + j, base + n + j, base + n + i))
    return verts, faces


# -----------------------------------------------------------------------------
# on objects
# -----------------------------------------------------------------------------


def _bounds(ob):
    pts = [Vector(c) for c in ob.bound_box]
    lo = Vector([min(p[i] for p in pts) for i in range(3)])
    hi = Vector([max(p[i] for p in pts) for i in range(3)])
    return lo, hi


def holes_for(ob, p):
    """(centres, shape, frame) of the holes that fit on ob with settings p (the surface is under the whole hole and
    its margin)."""
    lo, hi = _bounds(ob)
    ext = hi - lo
    u, v, w = plane_axes(p.direction, ext)
    corners = [Vector((x, y, z)) for x in (lo.x, hi.x) for y in (lo.y, hi.y) for z in (lo.z, hi.z)]
    bu = [q.dot(u) for q in corners]
    bv = [q.dot(v) for q in corners]
    bw = [q.dot(w) for q in corners]
    centres = lattice(p.pattern, p.size, p.gap, (min(bu), max(bu), min(bv), max(bv)), p.rotation,
                      tuple(p.offset))
    me = ob.data
    bvh = BVHTree.FromPolygons([vv.co for vv in me.vertices], [tuple(pl.vertices) for pl in me.polygons])
    reach = outer_radius(p.pattern, p.size) + p.margin
    top = max(bw) + 1.0 + ext.length
    ring = [(math.cos(2 * math.pi * k / 8), math.sin(2 * math.pi * k / 8)) for k in range(8)]
    keep = []
    for cu, cv in centres:
        ok = True
        for x, y in [(0.0, 0.0)] + ring:
            o = u * (cu + x * reach) + v * (cv + y * reach) + w * top
            if bvh.ray_cast(o, -w)[0] is None:
                ok = False
                break
        if ok:
            keep.append((cu, cv))
    return keep[:MAX_HOLES], hole_shape(p.pattern, p.size, p.sides), (u, v, w, min(bw), max(bw))


def rebuild(ob):
    """The cutter of ob from its settings (and the Boolean on it)."""
    p = ob.mch_perf
    cutter = p.cutter
    if cutter is None:
        return 0
    centres, shape, (u, v, w, w0, w1) = holes_for(ob, p)
    pad = (w1 - w0) * 0.5 + p.size
    verts, faces = prisms(centres, shape, p.rotation, u, v, w, w0 - pad, w1 + pad)
    me = cutter.data
    me.clear_geometry()
    if verts:
        me.from_pydata([tuple(q) for q in verts], [], faces)
    me.update()
    mod = ob.modifiers.get(MOD_NAME)
    if mod is not None:
        mod.show_viewport = bool(verts)
        try:
            mod.solver = p.solver
        except TypeError:
            pass
    p['holes'] = len(centres)
    return len(centres)


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live:
        rebuild(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


SETTING_KEYS = ('pattern', 'size', 'gap', 'rotation', 'margin', 'direction', 'sides', 'solver')


class MCH_PG_Perforate(bpy.types.PropertyGroup):
    live: BoolProperty(default=False)
    cutter: PointerProperty(type=bpy.types.Object)
    pattern: _p(EnumProperty, name='Pattern', items=PATTERNS, default='HEX')
    size: _p(FloatProperty, name='Hole Size', default=0.05, min=0.0005, soft_max=1.0, unit='LENGTH', precision=4)
    gap: _p(FloatProperty, name='Gap', default=0.015, min=0.0002, soft_max=0.5, unit='LENGTH', precision=4,
            description='The web between holes')
    rotation: _p(FloatProperty, name='Rotation', default=0.0, subtype='ANGLE')
    offset: _p(FloatVectorProperty, name='Offset', size=2, default=(0.0, 0.0), unit='LENGTH',
               description='Slide the pattern across the plate')
    margin: _p(FloatProperty, name='Margin', default=0.02, min=0.0, soft_max=0.5, unit='LENGTH', precision=4,
               description='No holes this close to the edge of the part')
    direction: _p(EnumProperty, name='Direction', items=DIRECTIONS, default='AUTO')
    sides: _p(IntProperty, name='Circle Sides', default=24, min=6, max=64)
    solver: _p(EnumProperty, name='Solver', items=[('EXACT', 'Exact', 'Clean result (slower)'),
                                                   ('FLOAT', 'Fast', 'Quicker, may fail on messy meshes')],
               default='EXACT')


class MCH_PG_PerforateDefaults(bpy.types.PropertyGroup):
    pattern: EnumProperty(name='Pattern', items=PATTERNS, default='HEX')
    auto_size: BoolProperty(name='Auto Size', default=True,
                            description='Pick the hole size from the part (about 8 holes across); change it after')
    size: FloatProperty(name='Hole Size', default=0.05, min=0.0005, soft_max=1.0, unit='LENGTH', precision=4)
    gap: FloatProperty(name='Gap', default=0.015, min=0.0002, soft_max=0.5, unit='LENGTH', precision=4)
    rotation: FloatProperty(name='Rotation', default=0.0, subtype='ANGLE')
    margin: FloatProperty(name='Margin', default=0.02, min=0.0, soft_max=0.5, unit='LENGTH', precision=4)
    direction: EnumProperty(name='Direction', items=DIRECTIONS, default='AUTO')
    sides: IntProperty(name='Circle Sides', default=24, min=6, max=64)
    solver: EnumProperty(name='Solver', items=[('EXACT', 'Exact', ''), ('FLOAT', 'Fast', '')], default='EXACT')


def is_perforated(ob):
    return ob is not None and ob.type == 'MESH' and ob.mch_perf.live and ob.mch_perf.cutter is not None


def setup(context, ob, d):
    """Put a live perforation on ob with the defaults d."""
    p = ob.mch_perf
    p.live = False
    for k in SETTING_KEYS:
        setattr(p, k, getattr(d, k))
    if d.auto_size:
        lo, hi = _bounds(ob)
        ext = sorted((hi - lo)[:])
        across = ext[1] if ext[1] > 1e-9 else ext[2]
        size = max(across / 8.0, 1e-4)
        p.size, p.gap, p.margin = size * 0.75, size * 0.25, size * 0.4
    if p.cutter is None:
        me = bpy.data.meshes.new(ob.name + '_Holes')
        cutter = bpy.data.objects.new(ob.name + '_Holes', me)
        for coll in ob.users_collection:
            coll.objects.link(cutter)
        cutter.parent = ob
        cutter.matrix_parent_inverse = Matrix.Identity(4)
        cutter.matrix_basis = Matrix.Identity(4)
        cutter.display_type = 'WIRE'
        cutter.hide_render = True
        cutter['mch_perf_cutter'] = True
        cutter.hide_set(True)
        p.cutter = cutter
    mod = ob.modifiers.get(MOD_NAME) or ob.modifiers.new(MOD_NAME, 'BOOLEAN')
    mod.operation, mod.object = 'DIFFERENCE', p.cutter
    if ob.modifiers[0] != mod:                               # before a Mirror: symmetrical holes
        ob.modifiers.move(list(ob.modifiers).index(mod), 0)
    p.live = True
    return rebuild(ob)


def remove(ob):
    p = ob.mch_perf
    mod = ob.modifiers.get(MOD_NAME)
    if mod is not None:
        ob.modifiers.remove(mod)
    cutter = p.cutter
    p.live = False
    p.cutter = None
    if cutter is not None:
        me = cutter.data
        bpy.data.objects.remove(cutter, do_unlink=True)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)


def apply(context, ob):
    mod = ob.modifiers.get(MOD_NAME)
    if mod is not None:
        with context.temp_override(object=ob, active_object=ob, selected_objects=[ob]):
            bpy.ops.object.modifier_apply(modifier=mod.name)
    remove(ob)


class MCH_OT_perforate(bpy.types.Operator):
    """Perforate the selected meshes with the pattern (live: change it in the panel, Apply to keep)"""
    bl_idname = 'mch.perforate'
    bl_label = 'Perforate Selected'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        d = context.scene.mch_perf_defaults
        total, done = 0, 0
        for ob in [o for o in context.selected_objects if o.type == 'MESH' and not o.get('mch_perf_cutter')]:
            if ob.data.users > 1 or ob.library:
                continue
            total += setup(context, ob, d)
            done += 1
        if not done:
            self.report({'WARNING'}, 'Perforate: select a mesh')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Perforate: {total} holes on {done} mesh(es) - change them in the panel, Apply to keep')
        return {'FINISHED'}


class MCH_OT_perforate_apply(bpy.types.Operator):
    bl_idname = 'mch.perforate_apply'
    bl_label = 'Apply Holes'
    bl_description = 'Make the holes part of the mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and is_perforated(context.active_object)

    def execute(self, context):
        apply(context, context.active_object)
        return {'FINISHED'}


class MCH_OT_perforate_remove(bpy.types.Operator):
    bl_idname = 'mch.perforate_remove'
    bl_label = 'Remove Holes'
    bl_description = 'Take the holes away (the mesh is as it was)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_perforated(context.active_object)

    def execute(self, context):
        remove(context.active_object)
        return {'FINISHED'}


def draw(layout, context):
    ob = context.active_object
    if is_perforated(ob):
        p = ob.mch_perf
        box = layout.box()
        box.label(text=f'{ob.name}: {p.get("holes", 0)} holes (live)', icon='MOD_BOOLEAN')
        box.row(align=True).prop(p, 'pattern', expand=True)
        col = box.column(align=True)
        col.prop(p, 'size')
        col.prop(p, 'gap')
        col.prop(p, 'margin')
        col.prop(p, 'rotation')
        col.prop(p, 'offset')
        if p.pattern == 'CIRCLE':
            col.prop(p, 'sides')
        box.row(align=True).prop(p, 'direction', expand=True)
        box.prop(p, 'solver', expand=True)
        row = box.row(align=True)
        row.operator('mch.perforate_apply', icon='CHECKMARK')
        row.operator('mch.perforate_remove', icon='X')
    d = context.scene.mch_perf_defaults
    box = layout.box()
    box.label(text='New holes', icon='ADD')
    box.row(align=True).prop(d, 'pattern', expand=True)
    box.prop(d, 'auto_size', toggle=True)
    if not d.auto_size:
        col = box.column(align=True)
        col.prop(d, 'size')
        col.prop(d, 'gap')
        col.prop(d, 'margin')
    box.row(align=True).prop(d, 'direction', expand=True)
    row = box.row()
    row.scale_y = 1.4
    row.operator('mch.perforate', icon='MOD_BOOLEAN')


CLASSES = (MCH_PG_Perforate, MCH_PG_PerforateDefaults, MCH_OT_perforate, MCH_OT_perforate_apply,
           MCH_OT_perforate_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_perf = PointerProperty(type=MCH_PG_Perforate)
    bpy.types.Scene.mch_perf_defaults = PointerProperty(type=MCH_PG_PerforateDefaults)


def unregister():
    for attr, owner in (('mch_perf', bpy.types.Object), ('mch_perf_defaults', bpy.types.Scene)):
        try:
            delattr(owner, attr)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
