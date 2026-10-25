"""0.24.32 Concept Move: grab the surface and pull it - the stretch-and-look move of VR modelers, in Object Mode.

Press on a mesh and drag: the area under the brush follows the mouse like clay.
* Shape: Sphere or Box (a view-aligned cube - frames, plates, flat panels).  Hardness: how much of the brush moves
  whole (1 = a rigid lump, 0 = a soft dome).  Falloffs: Clay (hardness), Elastic (Kelvinlet grab, Blender's Elastic
  Deform), Sharp (spikes / horns / fingers).
* While dragging: Shift = straight out of the surface, wheel = depth, [ ] = size, right click / Esc = cancel.
  A 3D mouse (and middle mouse) still navigates the view: with Follow View the grab stays where it is in front of
  you, so turning / pushing the view carries the clay through space even with the mouse held still (the 3D mouse
  is the hand, the mouse the fine aim) - re-evaluated 60 times a second.
* Mirror X, Keep Density (splits what got stretched when you let go); one drag = one undo step.
* Shift+click: drop a clay blob (brush size) on the surface or in front of you.  Fuse: join the selected clay into
  one smooth piece (voxel remesh).
``clay_weights``, ``elastic_weights``, ``sharp_weights``, ``box_distance`` and ``displace`` are pure (numpy).
"""
from __future__ import annotations

import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from bpy_extras import view3d_utils
from mathutils import Matrix, Vector

FALLOFF_ITEMS = [
    ('CLAY', 'Clay', 'Hardness decides how much moves whole; keeps the thickness of what you grab'),
    ('ELASTIC', 'Elastic', 'Soft rubber: the whole area stretches, volume is kept (Kelvinlet grab)'),
    ('SHARP', 'Sharp', 'A tight pull: a spike / horn / finger'),
]
SHAPE_ITEMS = [
    ('SPHERE', 'Sphere', 'Round brush'),
    ('BOX', 'Box', 'Square brush (a cube facing the view): frames, plates, flat panels'),
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


def clay_weights(dist, radius, hardness=0.5):
    """1 inside hardness*radius (moves whole), smooth fade to 0 at the brush edge (radius)."""
    r = max(radius, 1e-9)
    core = min(max(hardness, 0.0), 0.98) * r
    x = np.clip((r - dist) / (r - core), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def sharp_weights(dist, radius):
    x = np.clip(1.0 - dist / max(radius, 1e-9), 0.0, 1.0)
    return (x * x * (3.0 - 2.0 * x)) ** 3


def box_distance(r, axes, round_=0.2):
    """'Distance' for a box brush: the largest coordinate along the three axes (rows of axes), corners slightly
    rounded (round_ = 0 -> a sharp cube)."""
    p = np.abs(r @ np.asarray(axes, dtype=np.float64).T)
    if round_ <= 0:
        return p.max(1)
    k = 1.0 / max(round_, 1e-3) * 4.0                       # smooth max (p-norm)
    return (p ** k).sum(1) ** (1.0 / k)


def displace(co, centre, delta, radius, falloff='CLAY', mirror_x=False, shape='SPHERE', hardness=0.5,
             axes=None):
    """New coordinates (N,3) for a grab at centre moved by delta (all in the same space)."""
    co = np.asarray(co, dtype=np.float64)
    out = co.copy()
    if axes is None:
        axes = np.eye(3)
    axes = np.asarray(axes, dtype=np.float64)
    brushes = [(np.asarray(centre, dtype=np.float64), np.asarray(delta, dtype=np.float64), axes)]
    if mirror_x and abs(centre[0]) > radius * 0.5:          # a grab on the middle already moves both sides
        flip = np.array([-1.0, 1.0, 1.0])
        brushes.append((brushes[0][0] * flip, brushes[0][1] * flip, axes * flip))
    for c, d, ax in brushes:
        r = co - c
        dist = box_distance(r, ax) if shape == 'BOX' else np.sqrt((r * r).sum(1))
        if falloff == 'ELASTIC':
            s, t = elastic_weights(dist, radius)
            out += s[:, None] * d[None, :] + (t * (r @ d))[:, None] * r
        elif falloff == 'SHARP':
            out += sharp_weights(dist, radius)[:, None] * d[None, :]
        else:
            out += clay_weights(dist, radius, hardness)[:, None] * d[None, :]
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


def add_blob(context, location, radius, name='Clay'):
    """A smooth clay ball (quad sphere) at location; returns the object."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized() * radius
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.location = location
    return ob


def fuse(context, objects, voxel):
    """Join the meshes into the first one and voxel remesh it into one smooth piece."""
    objects = [o for o in objects if o.type == 'MESH']
    if not objects:
        return None
    target = objects[0]
    if len(objects) > 1:
        with context.temp_override(active_object=target, selected_editable_objects=objects,
                                   selected_objects=objects, object=target):
            bpy.ops.object.join()
    me = target.data
    me.remesh_voxel_size = max(voxel, 1e-4)
    me.remesh_voxel_adaptivity = 0.0
    with context.temp_override(active_object=target, object=target):
        bpy.ops.object.voxel_remesh()
    for p in target.data.polygons:
        p.use_smooth = True
    return target


# -----------------------------------------------------------------------------
# settings / operators / tool
# -----------------------------------------------------------------------------


class MCH_PG_Concept(bpy.types.PropertyGroup):
    radius_px: IntProperty(name='Size', default=120, min=5, max=3000, subtype='PIXEL',
                           description='Brush size on screen ([ and ] while dragging)')
    shape: EnumProperty(name='Shape', items=SHAPE_ITEMS, default='SPHERE')
    hardness: FloatProperty(name='Hardness', default=0.5, min=0.0, max=0.98,
                            description='How much of the brush moves whole (high = a rigid lump, low = soft)')
    falloff: EnumProperty(name='Falloff', items=FALLOFF_ITEMS, default='CLAY')
    mirror_x: BoolProperty(name='Mirror X', default=True, description='Move the other side (object X) too')
    keep_density: BoolProperty(name='Keep Density', default=True,
                               description='Split what got stretched when you let go (no long thin faces)')
    follow_view: BoolProperty(name='Follow View', default=True,
                              description='The grab stays in front of you while the view turns (3D mouse = hand)')
    strength: FloatProperty(name='Strength', default=1.0, min=0.05, max=2.0,
                            description='How far the surface follows the mouse')
    fuse_detail: FloatProperty(name='Fuse Detail', default=0.01, min=0.001, max=0.2, precision=3,
                               description='Fuse voxel size (part of the clay size): smaller = more detail')


_DRAW = [None]


def _draw_brush(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    try:
        if op.center_2d is None:
            return
        cx, cy = op.center_2d
        st = context.scene.mch_concept
        r = st.radius_px
        if st.shape == 'BOX':
            pts = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        else:
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (2 * math.pi * i / 48 for i in range(48))]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        sh.uniform_float('color', (1.0, 0.62, 0.15, 0.9))
        batch_for_shader(sh, 'LINE_LOOP', {'pos': pts}).draw(sh)
        core = r * (st.hardness if st.falloff == 'CLAY' else 0.0)
        if core > 3:
            if st.shape == 'BOX':
                cp = [(cx - core, cy - core), (cx + core, cy - core), (cx + core, cy + core), (cx - core, cy + core)]
            else:
                cp = [(cx + core * math.cos(a), cy + core * math.sin(a))
                      for a in (2 * math.pi * i / 48 for i in range(48))]
            sh.uniform_float('color', (1.0, 0.62, 0.15, 0.35))
            batch_for_shader(sh, 'LINE_LOOP', {'pos': cp}).draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


NAV_EVENTS = {'NDOF_MOTION', 'NDOF_BUTTON_PRESS', 'NDOF_BUTTON_RELEASE', 'MIDDLEMOUSE', 'TRACKPADPAN',
              'TRACKPADZOOM', 'NDOF_BUTTON_FIT', 'NDOF_BUTTON_TOP', 'NDOF_BUTTON_FRONT', 'NDOF_BUTTON_RIGHT'}


class MCH_OT_concept_move(bpy.types.Operator):
    bl_idname = 'mch.concept_move'
    bl_label = 'Concept Move'
    bl_description = 'Grab the surface and pull it (Shift: straight out, wheel: depth, [ ]: size)'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    def _world_radius(self, context, px, at=None):
        region, rv3d = context.region, context.region_data
        at = at if at is not None else self.target
        c = view3d_utils.location_3d_to_region_2d(region, rv3d, at) or Vector(self.center_2d)
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, c, at)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (c[0] + px, c[1]), at)
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
        self.target = loc.copy()
        self.normal = nrm.normalized()
        self.mouse0 = Vector(mouse)
        self.mouse = mouse
        self.center_2d = mouse
        self.depth = 0.0
        self.shift = False
        # Follow View: where the grab sits relative to the view (distance along the mouse ray)
        self.dist0 = (loc - origin).length
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted_safe()
        self.orig = read_coords(ob.data)
        self.last = self.orig
        for o in context.selected_objects:
            if o is not ob:
                o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw_brush, (self, context), 'WINDOW', 'POST_PIXEL')
        self.timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        st = context.scene.mch_concept
        context.area.header_text_set(
            f'Concept Move  |  {st.shape.title()} {st.radius_px}px  hardness {st.hardness:.2f}  |  {st.falloff.title()}'
            f'  |  Mirror X {"on" if st.mirror_x else "off"}  |  Follow View {"on" if st.follow_view else "off"}'
            '  |  Shift: out   Wheel: depth   [ ]: size   3D mouse / MMB: view   RMB/Esc: cancel')

    def _target(self, context):
        """Where the grabbed point should be now (mouse + current view)."""
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, self.mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, self.mouse).normalized()
        if st.follow_view:
            return origin + ray * (self.dist0 + self.depth), ray
        p = view3d_utils.region_2d_to_location_3d(region, rv3d, self.mouse, self.target)
        return p + ray * self.depth, ray

    def _apply(self, context):
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        target, ray = self._target(context)
        delta = target - self.hit
        if self.shift:                                       # straight out of / into the surface
            dy = (Vector(self.mouse) - self.mouse0).y
            delta = self.normal * (dy * self._world_radius(context, 1.0, self.hit))
        delta *= st.strength
        self.target = self.hit + delta
        self.center_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, self.target) or self.mouse
        radius = self._world_radius(context, st.radius_px, self.hit)
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
        # box brush faces the view: its axes are the screen right / up / view direction (object space)
        vm = rv3d.view_matrix.to_3x3().transposed()
        axes = [(m3 @ vm.col[i]).normalized()[:] for i in range(3)]
        new = displace(self.orig, (self.mwi @ self.hit)[:], (m3 @ delta)[:], radius * scale, st.falloff,
                       st.mirror_x, st.shape, st.hardness, axes)
        write_coords(self.ob.data, new)
        self.last = new

    def _finish(self, context):
        if _DRAW[0] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            _DRAW[0] = None
        if getattr(self, 'timer', None) is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        st = context.scene.mch_concept
        if event.type in NAV_EVENTS:                         # the 3D mouse / MMB still moves the view
            return {'PASS_THROUGH'}
        if event.type == 'TIMER':                            # the view may have moved under a still mouse
            self._apply(context)
        elif event.type == 'MOUSEMOVE':
            self.mouse = (event.mouse_region_x, event.mouse_region_y)
            self.shift = event.shift
            self._apply(context)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = self._world_radius(context, st.radius_px) * 0.15
            self.depth += step if event.type == 'WHEELDOWNMOUSE' else -step
            self._apply(context)
        elif event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            st.radius_px = max(5, int(st.radius_px * (1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)))
            self._header(context)
            self._apply(context)
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.shift = event.value == 'PRESS'
            self._apply(context)
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


class MCH_OT_concept_add(bpy.types.Operator):
    bl_idname = 'mch.concept_add'
    bl_label = 'Add Clay'
    bl_description = 'Drop a clay ball (brush size) on the surface under the mouse, or in front of you'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.mode != 'OBJECT' or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse).normalized()
        dg = context.evaluated_depsgraph_get()
        hit, loc, _n, _i, _ob, _m = context.scene.ray_cast(dg, origin, ray)
        at = loc if hit else view3d_utils.region_2d_to_location_3d(region, rv3d, mouse,
                                                                    context.scene.cursor.location)
        st = context.scene.mch_concept
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, at)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (mouse[0] + st.radius_px * 0.6, mouse[1]), at)
        ob = add_blob(context, at, max((a - b).length, 1e-4))
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class MCH_OT_concept_fuse(bpy.types.Operator):
    bl_idname = 'mch.concept_fuse'
    bl_label = 'Fuse Clay'
    bl_description = 'Join the selected meshes into one smooth piece (voxel remesh)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        objs = [context.active_object] if context.active_object in context.selected_objects else []
        objs += [o for o in context.selected_objects if o not in objs and o.type == 'MESH']
        size = max(max(o.dimensions) for o in objs)
        ob = fuse(context, objs, size * context.scene.mch_concept.fuse_detail)
        if ob is None:
            return {'CANCELLED'}
        self.report({'INFO'}, f'Fused into {ob.name} ({len(ob.data.polygons)} faces)')
        return {'FINISHED'}


class MCH_TOOL_concept_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.concept_move'
    bl_label = 'Mecha Concept Move'
    bl_description = ('Concept: grab the surface and pull it (like a VR move tool).\n'
                      'Shift+click: add clay.  Dragging: Shift = out, wheel = depth, [ ] = size, 3D mouse = view')
    bl_icon = 'ops.transform.translate'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_move', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.concept_add', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
    )

    def draw_settings(context, layout, tool):
        draw(layout, context, compact=True)


def draw(layout, context, compact=False):
    st = context.scene.mch_concept
    layout.prop(st, 'shape', text='' if compact else 'Shape')
    layout.prop(st, 'radius_px')
    if st.falloff == 'CLAY':
        layout.prop(st, 'hardness', slider=True)
    layout.prop(st, 'falloff', text='' if compact else 'Falloff')
    layout.prop(st, 'strength')
    layout.prop(st, 'mirror_x', toggle=True)
    layout.prop(st, 'keep_density', toggle=True)
    layout.prop(st, 'follow_view', toggle=True)
    layout.operator('mch.concept_fuse', icon='META_BALL')


CLASSES = (MCH_PG_Concept, MCH_OT_concept_move, MCH_OT_concept_size, MCH_OT_concept_add, MCH_OT_concept_fuse)


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
