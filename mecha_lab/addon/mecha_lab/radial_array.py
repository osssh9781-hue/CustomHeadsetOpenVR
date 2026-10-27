"""Mecha Lab radial (Z-axis) instanced array, compatible with Blender 4.3+.

Preview: one source mesh stored in a carrier; GN instances it at radial points.
Apply: Realize Instances is enabled immediately before baking so the result is
real mesh geometry. Source object is never deleted by create/cancel/apply.
"""

import math
import bpy
import numpy as np
from mathutils import Matrix
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty

GN_MOD = 'MCH_Radial_Array'
ROLE = 'MCH_RADIAL'
EPSILON = 1.0e-6
BOOL_PREFIX = 'MCH Radial Boolean'
# 0.24.65 Crash guards, measured with 0.3 cube teeth on a 1.2 tire and the live Exact Boolean: a Size of
# 1e25 segfaults bpy 5.2.3; 192 copies take 12 s / 1.4 GB, 256 copies 42 s / 3.8 GB, 2048 copies were killed
# for memory (> 15 GB, bpy 5.0.1 and 5.2.3). Baking costs about 0.8 KB per realized point (BMesh).
MAX_EXTENT = 1.0e6                  # 1,000 km from the ring centre
MAX_REALIZED_VERTS = 5_000_000      # about 4 GB while baking
BOOLEAN_LIVE_LOAD = 50_000          # see boolean_load(): a few seconds per update, under 1 GB
BOOLEAN_APPLY_LOAD = 400_000        # about 4 GB once
# Every named node of make_radial_group(); without MCH_Radial_Realize a bake would come out empty.
NODE_NAMES = ('MCH_Radial_Points', 'MCH_Radial_Step', 'MCH_Radial_Start', 'MCH_Radial_Cos', 'MCH_Radial_Sin',
              'MCH_Radial_X', 'MCH_Radial_Y', 'MCH_Radial_Position', 'MCH_Radial_SetPosition', 'MCH_Radial_Phase',
              'MCH_Radial_Orient', 'MCH_Radial_Instances', 'MCH_Radial_CopyRot', 'MCH_Radial_RingRot',
              'MCH_Radial_Realize', 'MCH_Radial_BakeSwitch')


def radial_step(count, arc):
    """Closed rings do not duplicate a first/last instance."""
    if count <= 1:
        return 0.0
    if arc >= math.tau - 1.0e-5:
        return math.tau / count
    return max(0.0, arc) / (count - 1)


def radial_positions(count, radius, base_angle, phase, arc, height):
    """Pure Python geometry oracle for tests, not used per-frame in Blender."""
    step = radial_step(count, arc)
    return [
        (radius * math.cos(base_angle + phase + step * i),
         radius * math.sin(base_angle + phase + step * i),
         height)
        for i in range(count)
    ]


def get_radial(obj):
    if obj is None or obj.get('mch_role') != ROLE:
        return None
    return obj.modifiers.get(GN_MOD)


def edit_problem(ob):
    """0.24.65 Why the radial operators must not write into ``ob`` (library data, which Python could still
    change without saving or undo), or ''."""
    data = getattr(ob, 'data', None)
    if ob.library is not None or (data is not None and data.library is not None):
        return f'"{ob.name}" is linked from a library; make it local first'
    if ob.override_library is not None:
        return f'"{ob.name}" is a library override; make it local first'
    return ''


def in_view_layer(context, ob):
    """0.24.65 select_set / active raise for an object outside the view layer (deleted from the scene but kept
    by the ring's Source pointer, or in an excluded collection)."""
    return ob is not None and context.view_layer.objects.get(ob.name) == ob


def boolean_load(p, tris, size):
    """0.24.65 Rough Exact Boolean memory of the ring (about 10 KB per unit in the measurements): cutter
    triangles x (1 + neighbour copies crossing each triangle) ^ 2. Overlapping copies are what blows up."""
    chord = 2.0 * abs(p.radius) * math.sin(radial_step(p.count, p.arc) / 2.0)
    near = min(p.count - 1, 2 * int(size / chord)) if chord > EPSILON else p.count - 1
    return p.count * tris * (1.0 + near / math.sqrt(max(tris, 1))) ** 2


def realize_problem(carrier, boolean_limit=0):
    """0.24.65 Why realizing the ring (Confirm, Radial Boolean) could crash Blender or run out of memory,
    or '' when it is safe. ``boolean_limit`` > 0 also checks the Exact Boolean load."""
    p = carrier.mch_radial
    values = (p.radius, p.phase, p.arc, p.scale, p.height, p.base_angle, p.ring_rot_x, p.ring_rot_y,
              p.ring_rot_z, p.copy_rot_x, p.copy_rot_y, p.copy_rot_z)
    if not all(math.isfinite(v) for v in values):
        return 'Radial values are not numbers (NaN / inf): re-enter Radius, Size and angles'
    me = carrier.data
    n = len(me.vertices)
    if n == 0 or p.count < 1:
        return 'Radial source mesh is empty'
    if n * p.count > MAX_REALIZED_VERTS:
        return f'Too many points to realize ({n * p.count:,}, limit {MAX_REALIZED_VERTS:,}): lower Count'
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    if not np.isfinite(co).all():
        return 'Radial source mesh has broken (NaN / inf) points'
    reach = float(np.abs(co).max()) * math.sqrt(3.0) * p.scale
    if abs(p.radius) + abs(p.height) + reach > MAX_EXTENT:
        return 'Radial array is too large (over 1,000 km): lower Radius, Size or Z Offset'
    if boolean_limit > 0:
        co = co.reshape(-1, 3)
        size = float(np.linalg.norm(co.max(axis=0) - co.min(axis=0))) * p.scale
        if boolean_load(p, max(0, len(me.loops) - 2 * len(me.polygons)), size) > boolean_limit:
            return 'Exact Boolean too heavy (many overlapping cutters): lower Count or Size'
    return ''


def _math(nodes, name, operation, value=None):
    n = nodes.new('ShaderNodeMath')
    n.name = name
    n.operation = operation
    if value is not None:
        n.inputs[1].default_value = value
    return n


def make_radial_group(carrier):
    p = carrier.mch_radial
    ng = bpy.data.node_groups.new('MCH Radial GN | ' + carrier.name, 'GeometryNodeTree')
    ng.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    nodes = ng.nodes
    links = ng.links
    gi = nodes.new('NodeGroupInput')
    gi.location = (-800, -300)
    go = nodes.new('NodeGroupOutput')
    go.location = (1200, 0)

    line = nodes.new('GeometryNodeMeshLine')
    line.name = 'MCH_Radial_Points'
    line.mode = 'OFFSET'
    line.inputs['Count'].default_value = p.count
    line.inputs['Offset'].default_value = (0.0, 0.0, 0.0)
    line.location = (-850, 350)

    index = nodes.new('GeometryNodeInputIndex')
    index.location = (-850, 50)
    angle_step = _math(nodes, 'MCH_Radial_Step', 'MULTIPLY', radial_step(p.count, p.arc))
    angle_step.location = (-650, 50)
    links.new(index.outputs['Index'], angle_step.inputs[0])

    pos_angle = _math(nodes, 'MCH_Radial_Start', 'ADD', p.base_angle + p.phase)
    pos_angle.location = (-450, 250)
    links.new(angle_step.outputs['Value'], pos_angle.inputs[0])
    cs = _math(nodes, 'MCH_Radial_Cos', 'COSINE')
    sn = _math(nodes, 'MCH_Radial_Sin', 'SINE')
    cs.location = (-250, 390)
    sn.location = (-250, 220)
    links.new(pos_angle.outputs['Value'], cs.inputs[0])
    links.new(pos_angle.outputs['Value'], sn.inputs[0])
    xm = _math(nodes, 'MCH_Radial_X', 'MULTIPLY', p.radius)
    ym = _math(nodes, 'MCH_Radial_Y', 'MULTIPLY', p.radius)
    links.new(cs.outputs['Value'], xm.inputs[0])
    links.new(sn.outputs['Value'], ym.inputs[0])
    xyz = nodes.new('ShaderNodeCombineXYZ')
    xyz.name = 'MCH_Radial_Position'
    xyz.inputs['Z'].default_value = p.height
    links.new(xm.outputs['Value'], xyz.inputs['X'])
    links.new(ym.outputs['Value'], xyz.inputs['Y'])
    reposition = nodes.new('GeometryNodeSetPosition')
    reposition.name = 'MCH_Radial_SetPosition'
    links.new(line.outputs['Mesh'], reposition.inputs['Geometry'])
    links.new(xyz.outputs['Vector'], reposition.inputs['Position'])

    rot_phase = _math(nodes, 'MCH_Radial_Phase', 'ADD', p.phase)
    links.new(angle_step.outputs['Value'], rot_phase.inputs[0])
    rot_enabled = _math(nodes, 'MCH_Radial_Orient', 'MULTIPLY', 1.0 if p.follow_circle else 0.0)
    links.new(rot_phase.outputs['Value'], rot_enabled.inputs[0])
    rot_xyz = nodes.new('ShaderNodeCombineXYZ')
    links.new(rot_enabled.outputs['Value'], rot_xyz.inputs['Z'])
    euler = nodes.new('FunctionNodeEulerToRotation')
    links.new(rot_xyz.outputs['Vector'], euler.inputs['Euler'])

    inst = nodes.new('GeometryNodeInstanceOnPoints')
    inst.name = 'MCH_Radial_Instances'
    links.new(reposition.outputs['Geometry'], inst.inputs['Points'])
    links.new(gi.outputs['Geometry'], inst.inputs['Instance'])
    links.new(euler.outputs['Rotation'], inst.inputs['Rotation'])
    inst.inputs['Scale'].default_value = (p.scale, p.scale, p.scale)

    # Per-copy rotation in each copy's own space (independent of the ring).
    copy_rot = nodes.new('GeometryNodeRotateInstances')
    copy_rot.name = 'MCH_Radial_CopyRot'
    copy_rot.inputs['Rotation'].default_value = (p.copy_rot_x, p.copy_rot_y, p.copy_rot_z)
    copy_rot.inputs['Local Space'].default_value = True
    links.new(inst.outputs['Instances'], copy_rot.inputs['Instances'])
    # Whole-ring rotation about the ring centre (tilts the ring plane).
    ring_rot = nodes.new('GeometryNodeTransform')
    ring_rot.name = 'MCH_Radial_RingRot'
    ring_rot.inputs['Rotation'].default_value = (p.ring_rot_x, p.ring_rot_y, p.ring_rot_z)
    links.new(copy_rot.outputs['Instances'], ring_rot.inputs['Geometry'])
    ring_out = ring_rot.outputs['Geometry']

    realize = nodes.new('GeometryNodeRealizeInstances')
    realize.name = 'MCH_Radial_Realize'
    links.new(ring_out, realize.inputs['Geometry'])
    switch = nodes.new('GeometryNodeSwitch')
    switch.name = 'MCH_Radial_BakeSwitch'
    switch.input_type = 'GEOMETRY'
    switch.inputs['Switch'].default_value = False
    links.new(ring_out, switch.inputs['False'])
    links.new(realize.outputs['Geometry'], switch.inputs['True'])
    links.new(switch.outputs['Output'], go.inputs['Geometry'])
    return ng


def ensure_radial_group(obj):
    """0.24.65 The ring's node group, rebuilt from the stored settings when it was removed or lost one of its
    nodes (pre-0.9 rings, user edits) instead of a KeyError / None mid-operation. None without the GN modifier."""
    mod = get_radial(obj)
    if mod is None:
        return None
    old = mod.node_group
    if old is not None and all(old.nodes.get(name) is not None for name in NODE_NAMES):
        return old
    mod.node_group = make_radial_group(obj)
    if old is not None and old.users == 0:
        bpy.data.node_groups.remove(old)
    return mod.node_group


def set_realize(carrier, realize):
    """0.24.65 Realize Instances on / off; False when the switch node is missing."""
    mod = get_radial(carrier)
    switch = mod.node_group.nodes.get('MCH_Radial_BakeSwitch') if mod is not None and mod.node_group else None
    if switch is not None:
        switch.inputs['Switch'].default_value = bool(realize)
    return switch is not None


# Keep instances cheap during ordinary array edits. Turning on Boolean Preview
# realizes cutters and runs the exact solver, so it is explicitly opt-in.
def find_boolean_link(carrier):
    if carrier is None:
        return None, None
    for obj in bpy.data.objects:
        if obj.type != 'MESH' or obj == carrier:
            continue
        for mod in obj.modifiers:
            if mod.type == 'BOOLEAN' and mod.object == carrier and mod.name.startswith(BOOL_PREFIX):
                return obj, mod
    return None, None


def set_boolean_preview(carrier, preview):
    mod = get_radial(carrier)
    if mod is None:
        return
    switch = mod.node_group.nodes.get('MCH_Radial_BakeSwitch') if mod.node_group is not None else None
    target, bool_mod = find_boolean_link(carrier)
    # 0.24.65 The live cut pauses (cheap instances, Boolean hidden) while the node group is missing or the ring is
    # too heavy / out of range for the Exact solver: it segfaults or runs out of memory there.
    enabled = bool(preview and bool_mod is not None and switch is not None
                   and not realize_problem(carrier, BOOLEAN_LIVE_LOAD))
    # Exact Boolean needs genuine evaluated meshes, not cheap GN instances.
    if switch is not None:
        switch.inputs['Switch'].default_value = enabled
    if bool_mod is not None:
        # Array cutters can overlap each other. Without the Boolean solver's
        # self-intersection option, a dense 360-degree ring may evaluate as an
        # EMPTY mesh (reproduced with 48+ cutters in bpy 5.2.2).
        # Cover existing .blend projects with a previously linked modifier, too.
        if hasattr(bool_mod, 'use_self') and not bool_mod.use_self:
            bool_mod.use_self = True
        bool_mod.show_viewport = enabled
        bool_mod.show_render = enabled
        bool_mod.operation = carrier.mch_radial.boolean_operation


def update_boolean_preview(self, context):
    carrier = self.id_data
    if get_radial(carrier) is not None:
        set_boolean_preview(carrier, self.boolean_preview)


def update_boolean_operation(self, context):
    carrier = self.id_data
    target, bool_mod = find_boolean_link(carrier)
    if bool_mod is not None:
        bool_mod.operation = self.boolean_operation


def remove_boolean_link(carrier):
    previous_target, _ = find_boolean_link(carrier)
    # Remove only Boolean modifiers that actually reference this ring.
    for obj in list(bpy.data.objects):
        if obj.type != 'MESH' or obj == carrier:
            continue
        for modifier in list(obj.modifiers):
            if (modifier.type == 'BOOLEAN' and modifier.object == carrier
                    and modifier.name.startswith(BOOL_PREFIX)):
                obj.modifiers.remove(modifier)
    carrier.mch_radial.boolean_preview = False
    set_boolean_preview(carrier, False)
    return previous_target


def restore_selection(context, original_selection, original_active):
    for ob in list(context.selected_objects):
        ob.select_set(False)
    for ob in original_selection:
        if ob.name in bpy.data.objects and not ob.hide_get():
            ob.select_set(True)
    if original_active is not None and original_active.name in bpy.data.objects and not original_active.hide_get():
        context.view_layer.objects.active = original_active


class MCH_OT_radial_boolean_link(bpy.types.Operator):
    bl_idname = 'mch.radial_boolean_link'
    bl_label = 'Use Radial Array As Boolean'
    bl_description = 'Use all Z-ring instances as Boolean cutters on the selected target mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_radial(context.active_object) is not None

    def execute(self, context):
        carrier = context.active_object
        p = carrier.mch_radial
        target = p.boolean_target
        if target is None or target.name not in bpy.data.objects or target.type != 'MESH':
            self.report({'ERROR'}, 'Choose a valid target MESH with the eyedropper first')
            return {'CANCELLED'}
        if target is carrier:
            self.report({'ERROR'}, 'The Boolean target and cutter cannot be the same object')
            return {'CANCELLED'}
        # 0.24.65 A live ring as target, or a carrier modifier using the target, is a dependency cycle
        # (Blender: 'Dependency cycle detected'); library data would be changed without saving.
        problem = edit_problem(carrier) or edit_problem(target)
        if not problem and get_radial(target) is not None:
            problem = f'"{target.name}" is a live Radial Array: Confirm or Cancel it first'
        if not problem and any(getattr(m, 'object', None) == target for m in carrier.modifiers):
            problem = f'A modifier on the ring already uses "{target.name}" (dependency cycle)'
        if not problem and ensure_radial_group(carrier) is None:
            problem = 'Radial Geometry Nodes modifier is missing'
        problem = problem or realize_problem(carrier, BOOLEAN_APPLY_LOAD)
        if problem:
            self.report({'ERROR'}, 'Radial Boolean: ' + problem)
            return {'CANCELLED'}
        # Other existing modifiers/booleans on target are not touched.
        remove_boolean_link(carrier)
        bm = target.modifiers.new(BOOL_PREFIX + ' | ' + carrier.name, 'BOOLEAN')
        bm.operation = p.boolean_operation
        bm.solver = 'EXACT'
        bm.object = carrier
        p.linked_target = target
        p.boolean_preview = True
        carrier.display_type = 'WIRE'
        set_boolean_preview(carrier, True)
        live = realize_problem(carrier, BOOLEAN_LIVE_LOAD)
        if live:
            self.report({'WARNING'}, 'Radial Boolean linked; live preview paused (' + live + '). Apply still works')
            return {'FINISHED'}
        self.report({'INFO'}, 'Radial Boolean linked. Adjust Count/Radius; disable preview for fast edits')
        return {'FINISHED'}


class MCH_OT_radial_boolean_unlink(bpy.types.Operator):
    bl_idname = 'mch.radial_boolean_unlink'
    bl_label = 'Unlink Radial Boolean'
    bl_description = 'Remove the live Boolean modifier without changing the original target mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_radial(context.active_object) is not None and find_boolean_link(context.active_object)[1] is not None

    def execute(self, context):
        carrier = context.active_object
        problem = edit_problem(carrier)
        if problem:
            self.report({'ERROR'}, 'Unlink Radial Boolean: ' + problem)
            return {'CANCELLED'}
        remove_boolean_link(carrier)
        carrier.display_type = 'TEXTURED'
        carrier.mch_radial.linked_target = None
        self.report({'INFO'}, 'Radial Boolean removed; target mesh not modified')
        return {'FINISHED'}


class MCH_OT_radial_boolean_apply(bpy.types.Operator):
    bl_idname = 'mch.radial_boolean_apply'
    bl_label = 'Apply Radial Boolean'
    bl_description = 'Bake all radial cutters into the target once; remove procedural ring on success'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_radial(context.active_object) is not None and find_boolean_link(context.active_object)[1] is not None

    def execute(self, context):
        carrier = context.active_object
        p = carrier.mch_radial
        target, bm = find_boolean_link(carrier)
        if target is None or bm is None:
            self.report({'ERROR'}, 'No linked Boolean modifier')
            return {'CANCELLED'}
        # 0.24.65 Every check runs before anything changes: a missing node group used to fail only after the
        # ring was deleted (one cut, source left hidden), heavy / out-of-range rings crash the Exact solver.
        problem = edit_problem(carrier) or edit_problem(target)
        if not problem and target.mode != 'OBJECT':
            problem = f'"{target.name}" is in {target.mode.title()} Mode: switch it to Object Mode first'
        if not problem and ensure_radial_group(carrier) is None:
            problem = 'Radial Geometry Nodes modifier is missing'
        problem = problem or realize_problem(carrier, BOOLEAN_APPLY_LOAD)
        if problem:
            self.report({'ERROR'}, 'Radial Boolean apply: ' + problem)
            return {'CANCELLED'}
        # Names, not objects, are kept for the code after the ring is removed.
        source_name = p.source.name if p.source is not None else ''
        source_was_hidden = p.source_was_hidden
        gn_mod = get_radial(carrier)
        ng = gn_mod.node_group
        old_mesh = carrier.data
        previous_selection = list(context.selected_objects)
        previous_active = context.view_layer.objects.active
        original_hidden = target.hide_get()
        was_preview = p.boolean_preview
        try:
            # Even if the user left fast mode active, evaluate real mesh cutters
            # for the final difference/intersect/union operation.
            set_boolean_preview(carrier, True)
            set_realize(carrier, True)          # 0.24.65 also when the live preview is paused as too heavy
            bm.show_viewport = True
            bm.show_render = True
            if original_hidden:
                target.hide_set(False)
            for ob in list(context.selected_objects):
                ob.select_set(False)
            target.select_set(True)
            context.view_layer.objects.active = target
            from . import core_geometry
            core_geometry.apply_single_modifier(context, target, bm, getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE'))
        except Exception as exc:
            if original_hidden:
                target.hide_set(True)
            restore_selection(context, previous_selection, previous_active)
            p.boolean_preview = was_preview
            set_boolean_preview(carrier, was_preview)
            self.report({'ERROR'}, 'Radial Boolean apply failed: ' + str(exc))
            return {'CANCELLED'}
        # Only tear down helpers AFTER the target operation is known successful.
        bpy.data.objects.remove(carrier, do_unlink=True)
        if old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        if ng.users == 0:
            bpy.data.node_groups.remove(ng)
        source = bpy.data.objects.get(source_name) if source_name else None
        if in_view_layer(context, source):
            source.hide_set(source_was_hidden)
        # Target stays selected so the result can be inspected immediately.
        if original_hidden:
            target.hide_set(False)
        for ob in list(context.selected_objects):
            ob.select_set(False)
        target.select_set(True)
        context.view_layer.objects.active = target
        self.report({'INFO'}, 'Radial Boolean applied to target; source mesh preserved')
        return {'FINISHED'}


def update_radial(self, context):
    obj = self.id_data
    # Radial arrays made before v0.9 lack the rotation nodes: rebuild once.
    # 0.24.65 The same for a removed node group or any missing node (was a KeyError on every edit).
    group = ensure_radial_group(obj)
    if group is None:
        return
    nodes = group.nodes
    # Only cheap node socket values are updated. No topology rebuild or bpy.ops.
    nodes['MCH_Radial_Points'].inputs['Count'].default_value = self.count
    nodes['MCH_Radial_Step'].inputs[1].default_value = radial_step(self.count, self.arc)
    nodes['MCH_Radial_Start'].inputs[1].default_value = self.base_angle + self.phase
    nodes['MCH_Radial_Phase'].inputs[1].default_value = self.phase
    nodes['MCH_Radial_X'].inputs[1].default_value = self.radius
    nodes['MCH_Radial_Y'].inputs[1].default_value = self.radius
    nodes['MCH_Radial_Position'].inputs['Z'].default_value = self.height
    nodes['MCH_Radial_Orient'].inputs[1].default_value = float(self.follow_circle)
    nodes['MCH_Radial_Instances'].inputs['Scale'].default_value = (self.scale,) * 3
    nodes['MCH_Radial_CopyRot'].inputs['Rotation'].default_value = (self.copy_rot_x, self.copy_rot_y, self.copy_rot_z)
    nodes['MCH_Radial_RingRot'].inputs['Rotation'].default_value = (self.ring_rot_x, self.ring_rot_y, self.ring_rot_z)
    if self.boolean_preview:
        # 0.24.65 Re-checked before the next depsgraph update: dragging Count / Size up with the live Exact
        # Boolean on pauses the cut instead of running out of memory (or segfaulting on a huge Size).
        set_boolean_preview(obj, True)


class MCH_PG_Radial(bpy.types.PropertyGroup):
    count: IntProperty(name='Count', description='Number of tread blocks or details', default=24, min=1, max=2048, update=update_radial)
    radius: FloatProperty(name='Radius', description='Distance from ring center to each mesh origin', default=1.0, min=0.0, soft_max=10.0, precision=4, update=update_radial)
    phase: FloatProperty(name='Start Angle', description='Angle of the first copy around the ring (rotates the whole array about the ring axis)', subtype='ANGLE', default=0.0, update=update_radial)
    arc: FloatProperty(name='Arc Span', description='360 degrees is full ring; smaller spans distribute across an open arc', subtype='ANGLE', default=math.tau, min=0.001, max=math.tau, update=update_radial)
    scale: FloatProperty(name='Size', description='Uniform scale of all copies', default=1.0, min=0.001, soft_max=5.0, update=update_radial)
    height: FloatProperty(name='Z Offset', description='Height above the ring center', default=0.0, precision=4, update=update_radial)
    follow_circle: BoolProperty(name='Rotate Each Copy', description='Rotate every copy to face along the ring (like tyre treads). OFF (default) keeps every copy in the source orientation', default=False, update=update_radial)
    ring_rot_x: FloatProperty(name='Ring Rotation X', subtype='ANGLE', default=0.0, update=update_radial,
                              description='Rotate the whole ring around its centre (tilts the ring plane)')
    ring_rot_y: FloatProperty(name='Ring Rotation Y', subtype='ANGLE', default=0.0, update=update_radial)
    ring_rot_z: FloatProperty(name='Ring Rotation Z', subtype='ANGLE', default=0.0, update=update_radial)
    copy_rot_x: FloatProperty(name='Copy Rotation X', subtype='ANGLE', default=0.0, update=update_radial,
                              description='Extra rotation of every copy in its own space')
    copy_rot_y: FloatProperty(name='Copy Rotation Y', subtype='ANGLE', default=0.0, update=update_radial)
    copy_rot_z: FloatProperty(name='Copy Rotation Z', subtype='ANGLE', default=0.0, update=update_radial)
    source: PointerProperty(name='Source Object', type=bpy.types.Object)
    source_was_hidden: BoolProperty(default=False)
    base_angle: FloatProperty(default=0.0)
    boolean_target: PointerProperty(name='Target Mesh', description='The tire or hard-surface object to cut', type=bpy.types.Object)
    linked_target: PointerProperty(name='Linked Boolean Target', type=bpy.types.Object)
    boolean_operation: EnumProperty(name='Operation', items=[
        ('DIFFERENCE', 'Difference / Cut', 'Subtract all radial instances from the target'),
        ('UNION', 'Union', 'Fuse the instances into the target'),
        ('INTERSECT', 'Intersect', 'Keep overlapping volume only'),
    ], default='DIFFERENCE', update=update_boolean_operation)
    boolean_preview: BoolProperty(name='Live Boolean Preview', description='Costs more than the lightweight ring preview; turn off while adjusting large arrays', default=False, update=update_boolean_preview)


class MCH_OT_radial_create(bpy.types.Operator):
    bl_idname = 'mch.radial_create'
    bl_label = 'Create Radial Array'
    bl_description = 'Use selected mesh as one spoke/tread; 3D cursor is center; rotate around world Z'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        src = context.active_object
        if get_radial(src):
            self.report({'WARNING'}, 'Select the original mesh, not an existing radial result')
            return {'CANCELLED'}
        s = context.scene.mch_settings
        center = context.scene.cursor.location.copy()
        origin = src.matrix_world.translation.copy()
        offset = origin - center
        default_radius = math.hypot(offset.x, offset.y)
        # Preserve full evaluated shape/rotation/scale of the source, while the
        # duplicated carrier itself is placed at the ring center (3D cursor).
        deps = context.evaluated_depsgraph_get()
        mesh = None
        carrier = None
        group = None
        try:
            mesh = bpy.data.meshes.new_from_object(src.evaluated_get(deps), preserve_all_data_layers=False, depsgraph=deps)
            if mesh is None or len(mesh.vertices) == 0:
                raise ValueError('Source mesh has no vertices')
            mesh.transform(src.matrix_world.to_3x3().to_4x4())
            mesh.name = 'MCH Radial Source | ' + src.name
            carrier = bpy.data.objects.new(src.name + '_Radial', mesh)
            context.collection.objects.link(carrier)
            carrier.matrix_world = Matrix.Translation(center)
            carrier['mch_role'] = ROLE
            p = carrier.mch_radial
            p.source = src
            p.source_was_hidden = src.hide_get()
            p.base_angle = math.atan2(offset.y, offset.x)
            p.count = s.radial_count
            p.radius = default_radius if s.radial_auto_radius and default_radius > EPSILON else s.radial_radius
            p.phase = s.radial_phase
            p.arc = s.radial_arc
            p.scale = s.radial_scale
            p.height = offset.z
            p.follow_circle = s.radial_follow
            group = make_radial_group(carrier)
            mod = carrier.modifiers.new(GN_MOD, 'NODES')
            mod.node_group = group
            if s.radial_hide_source:
                src.hide_set(True)
            for obj in context.selected_objects:
                obj.select_set(False)
            carrier.select_set(True)
            context.view_layer.objects.active = carrier
        except Exception as exc:
            if carrier is not None:
                bpy.data.objects.remove(carrier, do_unlink=True)
            elif mesh is not None and mesh.users == 0:
                bpy.data.meshes.remove(mesh)
            if group is not None and group.users == 0:
                bpy.data.node_groups.remove(group)
            self.report({'ERROR'}, 'Radial Array failed: ' + str(exc))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Radial Array: edit controls in Mecha Lab > Radial Array, then Confirm')
        return {'FINISHED'}


class MCH_OT_radial_bake(bpy.types.Operator):
    bl_idname = 'mch.radial_bake'
    bl_label = 'Confirm Radial Array'
    bl_description = 'Realize instances and bake them into an editable mesh; original mesh is preserved'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_radial(context.active_object) is not None

    def execute(self, context):
        ob = context.active_object
        if find_boolean_link(ob)[1] is not None:
            self.report({'WARNING'}, 'Radial Boolean is linked: Apply Boolean or Unlink first')
            return {'CANCELLED'}
        # 0.24.65 A removed node group is rebuilt (was an AttributeError); NaN / huge values or too many
        # points (out of memory while baking) are refused before anything changes.
        problem = edit_problem(ob)
        if not problem and ensure_radial_group(ob) is None:
            problem = 'Radial Geometry Nodes modifier is missing'
        problem = problem or realize_problem(ob)
        if problem:
            self.report({'ERROR'}, 'Radial bake: ' + problem)
            return {'CANCELLED'}
        mod = get_radial(ob)
        group = mod.node_group
        switch = group.nodes.get('MCH_Radial_BakeSwitch')
        if switch is None:
            self.report({'ERROR'}, 'Radial realize node missing')
            return {'CANCELLED'}
        switch.inputs['Switch'].default_value = True
        old_mesh = ob.data
        try:
            # Realize Instances is ON for bake only; preview remains light.
            from . import core_geometry
            core_geometry.apply_single_modifier(context, ob, mod, getattr(getattr(context.scene, 'mch_cut', None), 'shared_mesh', 'SINGLE'))
        except Exception as exc:
            switch.inputs['Switch'].default_value = False
            self.report({'ERROR'}, 'Radial bake failed: ' + str(exc))
            return {'CANCELLED'}
        if group.users == 0:
            bpy.data.node_groups.remove(group)
        if old_mesh != ob.data and old_mesh.users == 0:
            bpy.data.meshes.remove(old_mesh)
        ob['mch_role'] = 'MCH_RADIAL_BAKED'
        self.report({'INFO'}, 'Radial Array confirmed. Original source remains available (possibly hidden).')
        return {'FINISHED'}


class MCH_OT_radial_cancel(bpy.types.Operator):
    bl_idname = 'mch.radial_cancel'
    bl_label = 'Cancel Radial Array'
    bl_description = 'Remove procedural radial result and restore source mesh visibility'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and get_radial(context.active_object) is not None

    def execute(self, context):
        ob = context.active_object
        problem = edit_problem(ob)
        if problem:
            self.report({'ERROR'}, 'Cancel Radial Array: ' + problem)
            return {'CANCELLED'}
        if find_boolean_link(ob)[1] is not None:
            remove_boolean_link(ob)
        # 0.24.65 The source is found again by name after the ring is removed, and only selected when it is in
        # the view layer: a source deleted from the scene (kept by this pointer) raised after the ring was gone.
        src_name = ob.mch_radial.source.name if ob.mch_radial.source is not None else ''
        was_hidden = ob.mch_radial.source_was_hidden
        mod = get_radial(ob)
        group = mod.node_group
        mesh = ob.data
        bpy.data.objects.remove(ob, do_unlink=True)
        if mesh is not None and mesh.users == 0:
            bpy.data.meshes.remove(mesh)
        if group is not None and group.users == 0:
            bpy.data.node_groups.remove(group)
        src = bpy.data.objects.get(src_name) if src_name else None
        if in_view_layer(context, src):
            src.hide_set(was_hidden)
            if not was_hidden:
                src.select_set(True)
                context.view_layer.objects.active = src
        return {'FINISHED'}


class MCH_PT_radial(bpy.types.Panel):
    bl_parent_id = 'MCH_PT_main'
    bl_label = 'Radial Array | Tire / Wheel'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'

    @classmethod
    def poll(cls, context):
        from . import tool_state
        return tool_state.tool_is(context, 'RADIAL')

    def draw(self, context):
        layout = self.layout
        s = context.scene.mch_settings
        ob = context.active_object
        mod = get_radial(ob)
        if mod is None:
            layout.label(text='Z axis around the 3D Cursor', icon='CURSOR')
            layout.label(text='Place one tread where first copy goes')
            layout.prop(s, 'radial_count')
            layout.prop(s, 'radial_auto_radius')
            if not s.radial_auto_radius:
                layout.prop(s, 'radial_radius')
            layout.prop(s, 'radial_arc')
            layout.prop(s, 'radial_phase')
            layout.prop(s, 'radial_scale')
            layout.prop(s, 'radial_follow')
            layout.prop(s, 'radial_hide_source')
            layout.operator('mch.radial_create', text='CREATE RADIAL ARRAY', icon='MOD_ARRAY')
            layout.label(text='Center = 3D Cursor; edit Radius live')
        else:
            p = ob.mch_radial
            col = layout.column(align=True)
            col.label(text='LIVE: adjust without baking')
            col.prop(p, 'count')
            col.prop(p, 'radius', slider=True)
            col.prop(p, 'arc')
            col.prop(p, 'phase')
            col.prop(p, 'height')
            col.prop(p, 'scale')
            col.prop(p, 'follow_circle')
            box = layout.box()
            box.label(text='Ring rotation (whole array)', icon='ORIENTATION_GIMBAL')
            r = box.column(align=True)
            r.prop(p, 'ring_rot_x')
            r.prop(p, 'ring_rot_y')
            r.prop(p, 'ring_rot_z')
            box.label(text='Copy rotation (each copy, own space)', icon='ORIENTATION_LOCAL')
            r = box.column(align=True)
            r.prop(p, 'copy_rot_x')
            r.prop(p, 'copy_rot_y')
            r.prop(p, 'copy_rot_z')
            layout.separator()
            box = layout.box()
            box.label(text='RADIAL BOOLEAN | Tire Tread Cut', icon='MOD_BOOLEAN')
            linked_target, bm = find_boolean_link(ob)
            box.prop(p, 'boolean_target', text='Target Mesh')
            box.prop(p, 'boolean_operation', text='Operation')
            if bm is None:
                box.operator('mch.radial_boolean_link', text='LINK RADIAL BOOLEAN', icon='MOD_BOOLEAN')
                box.label(text='Pick target (e.g. tire cylinder) first')
            else:
                box.label(text='Linked: ' + linked_target.name)
                box.prop(p, 'boolean_preview', text='Live Boolean Preview')
                box.label(text='OFF: fast instances; ON: real cut')
                live = realize_problem(ob, BOOLEAN_LIVE_LOAD) if p.boolean_preview else ''
                if live:
                    box.label(text='Preview paused: ' + live, icon='ERROR')      # 0.24.65
                r = box.row(align=True)
                r.operator('mch.radial_boolean_apply', text='APPLY BOOLEAN', icon='CHECKMARK')
                r.operator('mch.radial_boolean_unlink', text='UNLINK', icon='UNLINKED')
            problem = realize_problem(ob) if bm is None else ''
            if problem:
                layout.label(text=problem, icon='ERROR')                       # 0.24.65 why Confirm will refuse
            row = layout.row(align=True)
            row.enabled = bm is None
            row.operator('mch.radial_bake', text='CONFIRM / APPLY', icon='CHECKMARK')
            row.operator('mch.radial_cancel', text='CANCEL', icon='CANCEL')
            layout.label(text='Source object remains preserved')


CLASSES = (MCH_PG_Radial, MCH_OT_radial_create, MCH_OT_radial_bake,
           MCH_OT_radial_cancel, MCH_OT_radial_boolean_link,
           MCH_OT_radial_boolean_unlink, MCH_OT_radial_boolean_apply,
           MCH_PT_radial)
