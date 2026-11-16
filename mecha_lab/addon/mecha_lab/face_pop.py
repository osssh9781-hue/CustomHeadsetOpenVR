"""0.24.179 Face Pop (user, a faceted rock in Edit Mode: "내가 선택한 면이 튀어나오게 하는 것도 만들어 주라"): pick faces of a
part and they stand out - extruded along their normals, Height high, their sides slanting in by Taper; faces picked
side by side come out together as one (Each Face: every face on its own).  Live (a Geometry Nodes modifier reading the
part's face attribute ``mch_pop``) until Apply; the part's mesh is not touched.

In Object Mode with the tool: click a face (the face under the mouse is shown), drag over faces - each one picked,
Alt: taken off.  Faces picked in Edit Mode: "From Edit Mode Selection".
"""
from __future__ import annotations

import bpy
import numpy as np
from bpy.props import BoolProperty, FloatProperty, PointerProperty
from mathutils import Vector
from mathutils.bvhtree import BVHTree

ATTR = 'mch_pop'
MOD = 'MCH Face Pop'
TREE = 'MCH Face Pop'
TREE_V = 1


def node_group():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for s_ in list(ng.interface.items_tree):
        ng.interface.remove(s_)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    h = ng.interface.new_socket('Height', in_out='INPUT', socket_type='NodeSocketFloat')
    h.default_value = 0.05
    t = ng.interface.new_socket('Taper', in_out='INPUT', socket_type='NodeSocketFloat')
    t.default_value, t.min_value, t.max_value = 0.3, 0.0, 0.95
    ind = ng.interface.new_socket('Each Face', in_out='INPUT', socket_type='NodeSocketBool')
    ind.default_value = False
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    na = N.new('GeometryNodeInputNamedAttribute')
    na.data_type = 'BOOLEAN'
    na.inputs['Name'].default_value = ATTR
    ex = N.new('GeometryNodeExtrudeMesh')
    ex.mode = 'FACES'
    L.new(gi.outputs['Geometry'], ex.inputs['Mesh'])
    L.new(na.outputs['Attribute'], ex.inputs['Selection'])
    L.new(gi.outputs['Height'], ex.inputs['Offset Scale'])
    L.new(gi.outputs['Each Face'], ex.inputs['Individual'])
    one = N.new('ShaderNodeMath')
    one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0
    L.new(gi.outputs['Taper'], one.inputs[1])
    sc = N.new('GeometryNodeScaleElements')
    sc.domain = 'FACE'
    L.new(ex.outputs['Mesh'], sc.inputs['Geometry'])
    L.new(ex.outputs['Top'], sc.inputs['Selection'])
    L.new(one.outputs[0], sc.inputs['Scale'])
    L.new(sc.outputs['Geometry'], go.inputs['Geometry'])
    ng['mch_v'] = TREE_V
    return ng


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object):
        push(ob)


class MCH_PG_FacePop(bpy.types.PropertyGroup):
    height: FloatProperty(name='Height', default=0.05, soft_min=-0.5, soft_max=0.5, precision=4, unit='LENGTH',
                          update=_upd, description='How far the picked faces come out (minus: in)')
    taper: FloatProperty(name='Taper', default=0.3, min=0.0, max=0.95, update=_upd,
                         description='Their tops smaller - the sides slant in')
    each: BoolProperty(name='Each Face', default=False, update=_upd,
                       description='Every picked face on its own (off: faces side by side come out together)')


def _set_input(mod, name, value):
    from . import geo_sculpt as gs
    gs.set_input(mod, name, value)


def push(ob):
    """The part's values into its modifier (made when it has picked faces)."""
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    p = ob.mch_pop
    _set_input(mod, 'Height', p.height / _scale(ob))
    _set_input(mod, 'Taper', p.taper)
    _set_input(mod, 'Each Face', p.each)


def _scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def picked(me):
    a = me.attributes.get(ATTR)
    v = np.zeros(len(me.polygons), bool)
    if a is not None and a.domain == 'FACE' and len(me.polygons):
        a.data.foreach_get('value', v)
    return v


def set_faces(ob, faces, on=True, settings=None):
    """Faces ``faces`` of ``ob``'s own mesh picked (``on``) or taken off; the modifier made / removed with them."""
    me = ob.data
    a = me.attributes.get(ATTR)
    if a is None:
        a = me.attributes.new(ATTR, 'BOOLEAN', 'FACE')
    v = picked(me)
    idx = [int(f) for f in faces if 0 <= int(f) < len(v)]
    v[idx] = on
    a.data.foreach_set('value', v)
    me.update()
    mod = ob.modifiers.get(MOD)
    if v.any() and mod is None:
        if settings is not None:
            for k in ('height', 'taper', 'each'):
                setattr(ob.mch_pop, k, getattr(settings, k))
        mod = ob.modifiers.new(MOD, 'NODES')
        mod.node_group = node_group()
        try:                                          # (first: what is made after it - mirror ... - takes it along)
            ob.modifiers.move(len(ob.modifiers) - 1, 0)
        except (RuntimeError, TypeError, AttributeError):
            pass
        push(ob)
    elif not v.any() and mod is not None:
        ob.modifiers.remove(mod)
    return int(v.sum())


def from_edit_selection(ob, settings=None):
    """The faces picked in Edit Mode (back in Object Mode)."""
    me = ob.data
    sel = np.zeros(len(me.polygons), bool)
    me.polygons.foreach_get('select', sel)
    if not sel.any() or sel.all():
        return 0
    return set_faces(ob, np.nonzero(sel)[0], True, settings)


def apply(context, ob):
    from . import core_geometry as cg
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return False
    cg.apply_single_modifier(context, ob, mod)
    at = ob.data.attributes.get(ATTR)
    if at is not None:
        ob.data.attributes.remove(at)
    return True


# --- the tool ------------------------------------------------------------------------------------------------------

HOVER = {'part': None, 'face': None}
_TREES = {}


def _tree(ob):
    me = ob.data
    key = (me.as_pointer(), len(me.vertices), len(me.polygons))
    hit = _TREES.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    polys = [tuple(p.vertices) for p in me.polygons]
    t = BVHTree.FromPolygons([tuple(c) for c in co], polys)
    if len(_TREES) > 8:
        _TREES.clear()
    _TREES[ob.name] = (key, t)
    return t


def face_at(context, xy):
    """(part, its face index) under the mouse - read on the part's own mesh (not what it pops out) - or None."""
    from bpy_extras import view3d_utils
    from . import geo_sculpt as gs
    hit = gs.pick_part(context, xy)
    if hit is None:
        return None
    ob = hit[0]
    region, rv3d = context.region, context.region_data
    mi = ob.matrix_world.inverted_safe()
    o = mi @ view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = (mi.to_3x3() @ view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)).normalized()
    loc, _n, idx, _dist = _tree(ob).ray_cast(o, d)
    if idx is None:
        loc, _n, idx, _dist = _tree(ob).find_nearest(mi @ Vector(hit[1]))
    return (ob, int(idx)) if idx is not None else None


def tool_on(context):
    from . import tool_state as ts
    try:
        return ts.effective_tool(context) == 'FPOP'
    except (AttributeError, KeyError, TypeError):
        return False


def _face_tris(ob, faces):
    me = ob.data
    mw = ob.matrix_world
    out = []
    for f in faces:
        if 0 <= f < len(me.polygons):
            vs = [mw @ me.vertices[i].co for i in me.polygons[f].vertices]
            n = (mw.to_3x3() @ me.polygons[f].normal).normalized() * 0.0015
            for k in range(1, len(vs) - 1):
                out += [tuple(vs[0] + n), tuple(vs[k] + n), tuple(vs[k + 1] + n)]
    return out


def draw_faces():
    context = bpy.context
    try:
        if not tool_on(context):
            return
        ob = bpy.data.objects.get(HOVER['part']) if HOVER['part'] else None
        if ob is None or ob.type != 'MESH':
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
        sel = np.nonzero(picked(ob.data))[0].tolist()
        if sel and len(sel) < 20000:
            tris = _face_tris(ob, sel)
            sh.uniform_float('color', (1.0, 0.55, 0.1, 0.35))
            batch_for_shader(sh, 'TRIS', {'pos': tris}).draw(sh)
        if HOVER['face'] is not None:
            tris = _face_tris(ob, [HOVER['face']])
            sh.uniform_float('color', (1.0, 0.92, 0.2, 0.45))
            batch_for_shader(sh, 'TRIS', {'pos': tris}).draw(sh)
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')
    except (ReferenceError, AttributeError, RuntimeError, KeyError, ValueError):
        pass


class MCH_OT_face_pop_hover(bpy.types.Operator):
    """(Face Pop) the face under the mouse, shown (passes the move on)"""
    bl_idname = 'mch.face_pop_hover'
    bl_label = 'Face Pop Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
        part, face = (got[0].name, got[1]) if got else (HOVER['part'], None)
        if (part, face) != (HOVER['part'], HOVER['face']):
            HOVER['part'], HOVER['face'] = part, face
            context.region.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_face_pop_pick(bpy.types.Operator):
    """Face Pop: click a face of a part - it stands out; drag over faces - each one; Alt: taken off"""
    bl_idname = 'mch.face_pop_pick'
    bl_label = 'Face Pop'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
        if got is None:
            return {'PASS_THROUGH'}
        self.ob = got[0]
        self.on = not event.alt
        self.done = set()
        self._take(context, got[1])
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _take(self, context, f):
        if f in self.done:
            return
        self.done.add(f)
        set_faces(self.ob, [f], self.on, context.scene.mch_pop)
        HOVER['part'], HOVER['face'] = self.ob.name, None
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
            if got is not None and got[0] == self.ob:
                self._take(context, got[1])
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            n = int(picked(self.ob.data).sum())
            self.report({'INFO'}, f'Face Pop on "{self.ob.name}": {n} face{"s" if n != 1 else ""} out - Height, Taper, '
                                  f'Each Face in the window; Apply keeps it')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


def active_part(context):
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None:
        return ob
    ob = bpy.data.objects.get(HOVER['part']) if HOVER['part'] else None
    if ob is not None and ob.modifiers.get(MOD) is not None:
        return ob
    return None


class MCH_OT_face_pop_from_edit(bpy.types.Operator):
    """The faces you selected in Edit Mode (back in Object Mode) stand out"""
    bl_idname = 'mch.face_pop_from_edit'
    bl_label = 'From Edit Mode Selection'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if ob is None or ob.type != 'MESH':
            self.report({'WARNING'}, 'Select the part first')
            return {'CANCELLED'}
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        n = from_edit_selection(ob, context.scene.mch_pop)
        if not n:
            self.report({'WARNING'}, 'No faces picked in Edit Mode (or all of them)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Face Pop on "{ob.name}": {n} faces out')
        return {'FINISHED'}


class MCH_OT_face_pop_clear(bpy.types.Operator):
    """All picked faces taken off (the part as it was)"""
    bl_idname = 'mch.face_pop_clear'
    bl_label = 'Clear'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = active_part(context)
        if ob is None:
            return {'CANCELLED'}
        set_faces(ob, range(len(ob.data.polygons)), False)
        return {'FINISHED'}


class MCH_OT_face_pop_apply(bpy.types.Operator):
    """Keep it: the popped faces into the part's mesh"""
    bl_idname = 'mch.face_pop_apply'
    bl_label = 'Apply'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = active_part(context)
        if ob is None or not apply(context, ob):
            return {'CANCELLED'}
        self.report({'INFO'}, f'Face Pop applied on "{ob.name}"')
        return {'FINISHED'}


def draw(layout, context):
    ob = active_part(context)
    p = ob.mch_pop if ob is not None else context.scene.mch_pop
    col = layout.column(align=True)
    if ob is not None:
        col.label(text=f'{ob.name}: {int(picked(ob.data).sum())} faces out (live)')
    col.prop(p, 'height')
    col.prop(p, 'taper')
    col.prop(p, 'each')
    row = layout.row(align=True)
    row.operator('mch.face_pop_from_edit', text='From Edit Mode Selection')
    if ob is not None:
        row = layout.row(align=True)
        row.operator('mch.face_pop_clear', text='Clear')
        row.operator('mch.face_pop_apply', text='Apply')
    col = layout.column(align=True)
    for line in ('Click a face: it stands out; drag: each face passed',
                 'Alt + click / drag: taken off',
                 'Faces side by side come out together (Each Face: apart)'):
        col.label(text=line)


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return
    draw(layout, context)


class MCH_TOOL_face_pop(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.face_pop'
    bl_label = 'Mecha Face Pop'
    bl_description = 'Click faces of a part: they stand out (Height, Taper); drag: each face passed; Alt: off'
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = (('mch.face_pop_hover', {'type': 'MOUSEMOVE', 'value': 'ANY', 'any': True}, None),
                 ('mch.face_pop_pick', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
                 ('mch.face_pop_pick', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),
                 ('mch.toggle_targets', {'type': 'T', 'value': 'PRESS'}, None),
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_PG_FacePop, MCH_OT_face_pop_hover, MCH_OT_face_pop_pick, MCH_OT_face_pop_from_edit,
           MCH_OT_face_pop_clear, MCH_OT_face_pop_apply)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_pop = PointerProperty(type=MCH_PG_FacePop)
    bpy.types.Scene.mch_pop = PointerProperty(type=MCH_PG_FacePop)
    try:
        bpy.utils.register_tool(MCH_TOOL_face_pop, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_faces, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_face_pop)
    except (ValueError, RuntimeError, KeyError):
        pass
    for owner in (bpy.types.Scene, bpy.types.Object):
        if hasattr(owner, 'mch_pop'):
            delattr(owner, 'mch_pop')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    _TREES.clear()
