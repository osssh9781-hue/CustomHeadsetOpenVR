"""0.24.32 Concept Move: grab the surface and pull it - the stretch-and-look move of VR modelers, in Object Mode.

Press on a mesh and drag: the area round the press point follows the mouse like soft clay (Clay = the middle
moves whole and only the edge stretches, Elastic = the regularised Kelvinlet grab of Blender's Elastic Deform
brush, Smooth / Sharp = simpler falloffs).  While dragging:
Shift pulls straight out of the surface, the wheel pushes the grab toward / away from you, [ ] change the size,
right click / Esc cancels.  Mirror X moves the other side too.  Keep Density splits what got stretched when you let
go, so long pulls do not end in long thin faces.  One drag = one undo step.
``clay_weights``, ``elastic_weights``, ``smooth_weights`` and ``displace`` are pure (numpy).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy_extras import view3d_utils
from mathutils import Vector

FALLOFF_ITEMS = [
    ('CLAY', 'Clay', 'Grab a lump: the middle moves whole (keeps its thickness), only the edge stretches'),
    ('ELASTIC', 'Elastic', 'Soft clay: the whole area stretches, volume is kept (Kelvinlet grab)'),
    ('SMOOTH', 'Smooth', 'Round falloff, nothing moves outside the circle'),
    ('SHARP', 'Sharp', 'A tight pull: a spike / horn / finger'),
]


# -----------------------------------------------------------------------------
# pure math
# -----------------------------------------------------------------------------


def elastic_weights(dist, radius, poisson=0.4):
    """Regularised Kelvinlet grab, as scalar part + radial part factors, normalised to 1 at the centre.

    Returns (s, t) arrays: displacement = s * d + t * (r . d) r  (r = point - centre)."""
    a = 1.0 / (4.0 * math.pi)
    b = a / (4.0 * (1.0 - poisson))
    eps = max(radius, 1e-9)
    re = np.sqrt(dist * dist + eps * eps)
    s = (a - b) / re + a * eps * eps / (2.0 * re ** 3)
    t = b / re ** 3
    norm = (a - b) / eps + a / (2.0 * eps)
    # infinite support -> fade out far away (2.5 .. 4 radii) so other parts of the mesh stay put
    fade = np.clip((4.0 * eps - dist) / (1.5 * eps), 0.0, 1.0)
    fade = fade * fade * (3.0 - 2.0 * fade)
    return s / norm * fade, t / norm * fade


def clay_weights(dist, radius, core=0.55, soft=1.6):
    """Plateau falloff: everything inside core*radius moves fully, smooth fade out to soft*radius."""
    r = max(radius, 1e-9)
    x = np.clip((soft * r - dist) / ((soft - core) * r), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def smooth_weights(dist, radius, sharp=False):
    x = np.clip(1.0 - dist / max(radius, 1e-9), 0.0, 1.0)
    w = x * x * (3.0 - 2.0 * x)
    return w ** 3 if sharp else w


def displace(co, centre, delta, radius, falloff='CLAY', mirror_x=False):
    """New coordinates (N,3) for a grab at centre moved by delta (all in the same space)."""
    co = np.asarray(co, dtype=np.float64)
    out = co.copy()
    brushes = [(np.asarray(centre, dtype=np.float64), np.asarray(delta, dtype=np.float64))]
    if mirror_x and abs(centre[0]) > radius * 0.5:          # a grab on the middle already moves both sides
        c2 = np.array([-centre[0], centre[1], centre[2]])
        d2 = np.array([-delta[0], delta[1], delta[2]])
        brushes.append((c2, d2))
    for c, d in brushes:
        r = co - c
        dist = np.sqrt((r * r).sum(1))
        if falloff == 'CLAY':
            w = clay_weights(dist, radius)
            out += w[:, None] * d[None, :]
        elif falloff == 'ELASTIC':
            s, t = elastic_weights(dist, radius)
            out += s[:, None] * d[None, :] + (t * (r @ d))[:, None] * r
        else:
            w = smooth_weights(dist, radius, falloff == 'SHARP')
            out += w[:, None] * d[None, :]
    return out


# -----------------------------------------------------------------------------
# mesh helpers
# -----------------------------------------------------------------------------


def read_coords(me):
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3).astype(np.float64)


def write_coords(me, co):
    me.vertices.foreach_set('co', np.asarray(co, dtype=np.float32).ravel())
    me.update()


def keep_density(me, before, after, radius, ratio=1.6):
    """Split edges the pull stretched (longer than ratio x before, and longer than the mesh's usual edge)."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    lens0 = np.array([np.linalg.norm(before[e.verts[0].index] - before[e.verts[1].index]) for e in bm.edges])
    usual = float(np.median(lens0)) if len(lens0) else 0.0
    long_e = []
    for e, l0 in zip(bm.edges, lens0):
        l1 = (e.verts[0].co - e.verts[1].co).length
        if l1 > max(l0 * ratio, usual * 1.5):
            long_e.append(e)
    n = 0
    if long_e:
        res = bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        new_v = [g for g in res['geom_inner'] + res['geom_split'] if isinstance(g, bmesh.types.BMVert)]
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        for _ in range(2):                                   # settle the new points into the surface
            for v in new_v:
                if v.is_valid and not v.is_boundary and v.link_edges:
                    avg = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
                    v.co = v.co.lerp(avg, 0.4)
        n = len(long_e)
        bm.to_mesh(me)
        me.update()
    bm.free()
    return n


# -----------------------------------------------------------------------------
# settings / operator / tool
# -----------------------------------------------------------------------------


class MCH_PG_Concept(bpy.types.PropertyGroup):
    radius_px: IntProperty(name='Size', default=90, min=5, max=2000, subtype='PIXEL',
                           description='Grab size on screen ([ and ] while dragging)')
    falloff: EnumProperty(name='Falloff', items=FALLOFF_ITEMS, default='CLAY')
    mirror_x: BoolProperty(name='Mirror X', default=True, description='Move the other side (object X) too')
    keep_density: BoolProperty(name='Keep Density', default=True,
                               description='Split what got stretched when you let go (no long thin faces)')
    strength: FloatProperty(name='Strength', default=1.0, min=0.05, max=2.0,
                            description='How far the surface follows the mouse')


_DRAW = [None]


def _draw_circle(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    try:
        if op.center_2d is None:
            return
        cx, cy = op.center_2d
        r = context.scene.mch_concept.radius_px
        pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (2 * math.pi * i / 48 for i in range(48))]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        batch = batch_for_shader(sh, 'LINE_LOOP', {'pos': pts})
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        sh.uniform_float('color', (1.0, 0.62, 0.15, 0.9))
        batch.draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


class MCH_OT_concept_move(bpy.types.Operator):
    bl_idname = 'mch.concept_move'
    bl_label = 'Concept Move'
    bl_description = 'Grab the surface and pull it (Shift: straight out, wheel: depth, [ ]: size)'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    def _world_radius(self, context, px):
        region, rv3d = context.region, context.region_data
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, self.center_2d, self.hit)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (self.center_2d[0] + px, self.center_2d[1]), self.hit)
        return (a - b).length

    def invoke(self, context, event):
        if context.mode != 'OBJECT' or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
        dg = context.evaluated_depsgraph_get()
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, origin, direction)
        if not hit or ob is None or ob.type != 'MESH' or ob.library or ob.data.library:
            return {'PASS_THROUGH'}
        if ob.data.users > 1:
            self.report({'WARNING'}, 'Concept Move: this mesh is shared by other objects (make it single user)')
            return {'CANCELLED'}
        self.ob = ob
        self.hit = loc.copy()
        self.normal = nrm.normalized()
        self.mouse0 = Vector(mouse)
        self.center_2d = mouse
        self.depth = 0.0
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted_safe()
        self.orig = read_coords(ob.data)
        self.last = self.orig
        self.view = direction.normalized()
        for o in context.selected_objects:
            if o is not ob:
                o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw_circle, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        st = context.scene.mch_concept
        context.area.header_text_set(
            f'Concept Move  |  size {st.radius_px}px  |  {st.falloff.title()}  |  Mirror X {"on" if st.mirror_x else "off"}'
            '  |  Shift: out of the surface   Wheel: depth   [ ]: size   RMB/Esc: cancel')

    def _apply(self, context, event):
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        p = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, self.hit)
        delta = (p - self.hit) + self.view * self.depth
        if event.shift:                                      # straight out of / into the surface
            dy = (Vector(mouse) - self.mouse0).y
            delta = self.normal * (dy * self._world_radius(context, 1.0))
        delta *= st.strength
        radius = self._world_radius(context, st.radius_px)
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if m3.determinant() != 0 else 1.0
        centre = self.mwi @ self.hit
        new = displace(self.orig, centre[:], (m3 @ delta)[:], radius * scale, st.falloff, st.mirror_x)
        write_coords(self.ob.data, new)
        self.last = new

    def _finish(self, context):
        if _DRAW[0] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            _DRAW[0] = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        st = context.scene.mch_concept
        if event.type == 'MOUSEMOVE':
            self._apply(context, event)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = self._world_radius(context, st.radius_px) * 0.15
            self.depth += step if event.type == 'WHEELDOWNMOUSE' else -step
            self._apply(context, event)
        elif event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            st.radius_px = max(5, int(st.radius_px * (1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)))
            self._header(context)
            self._apply(context, event)
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self._apply(context, event)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            n = 0
            if st.keep_density:
                n = keep_density(self.ob.data, self.orig, self.last, self._world_radius(context, st.radius_px))
            self._finish(context)
            if n:
                self.report({'INFO'}, f'Concept Move: {n} stretched edges split')
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            write_coords(self.ob.data, self.orig)
            self._finish(context)
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class MCH_OT_concept_size(bpy.types.Operator):
    bl_idname = 'mch.concept_size'
    bl_label = 'Concept Move Size'
    bl_options = {'INTERNAL'}
    factor: FloatProperty(default=1.15)

    def execute(self, context):
        st = context.scene.mch_concept
        st.radius_px = max(5, int(round(st.radius_px * self.factor)))
        return {'FINISHED'}


class MCH_TOOL_concept_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.concept_move'
    bl_label = 'Mecha Concept Move'
    bl_description = ('Concept: grab the surface and pull it (like a VR move tool).\n'
                      'Shift: straight out, wheel: depth, [ ]: size, RMB/Esc: cancel')
    bl_icon = 'ops.transform.translate'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_move', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
    )

    def draw_settings(context, layout, tool):
        draw(layout, context)


def draw(layout, context):
    st = context.scene.mch_concept
    layout.prop(st, 'radius_px')
    layout.prop(st, 'falloff', text='')
    layout.prop(st, 'strength')
    layout.prop(st, 'mirror_x', toggle=True)
    layout.prop(st, 'keep_density', toggle=True)


CLASSES = (MCH_PG_Concept, MCH_OT_concept_move, MCH_OT_concept_size)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_concept = bpy.props.PointerProperty(type=MCH_PG_Concept)
    try:
        bpy.utils.register_tool(MCH_TOOL_concept_move, separator=True, group=False)
    except (ValueError, RuntimeError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_concept_move)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    try:
        del bpy.types.Scene.mch_concept
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
