bl_info = {
    "name": "Mecha Lab — Cut & Mechanical Modeling",
    "author": "OpenAI / ChatGPT, Claude Code",
    "version": (0, 24, 30),
    "blender": (4, 3, 0),
    "location": "MECHA LAB workspace tab / 3D View > Sidebar (N) > Mecha Lab",
    "description": "Cut, Split, Base Mesh, Boolean, Face Extract, Armor Sculpt, Molding, Cable, Hollow, curve arrays, Mirror",
    "category": "Object",
}

import bpy
from . import (core_geometry, tool_state, cut_engine, cut_tools, surface_conform, radial_array,
               mirror_tools, cut_presets, mask_tools, workspace_ui, ui_tool_settings,
               base_mesh, loft_surface, zbrush_bridge, subd_plane, deform_tools, primitive_tools,
               addon_safety, self_test, face_extract, edge_molding, hollow_shell, along_curve, cable, bottom_bar, station_primitive, station_gizmos,
               primitive_place, primitive_hud, armor_plate, random_panels, mirror_hud, highpoly, lasso_sketch,
               cloth_wrinkle, last_used, robot_base, detail_stamp, surface_lasso,
               curve_tube, creature_shell, cloth_sim, box_hide, plate_detail, screw_stamp, lowpoly, fold_patch,
               creature_plate, belt_maker, creature_spike, creature_scales, flower_plate,
               surface_curve, scale_brush, bridge_patch, mech_ridge, cape_gen, creature_hair, clothing_gen, hood_gen, scarf_gen, quad_cloth)
import os
import re
from pathlib import Path
from mathutils import Vector, Matrix
from mathutils.geometry import intersect_line_plane
from bpy_extras import view3d_utils
from bpy.props import (
    BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty,
)

# -----------------------------------------------------------------------------
# Storage / shared helpers
# -----------------------------------------------------------------------------

_ENUM_KEEPALIVE = {}
_PROFILE_ITEMS = [
    ('RECT', 'Rectangle', 'Rectangular section'),
    ('ROUND', 'Cylinder / Round', 'Round section'),
    ('TRI', 'Triangle', '3-sided section'),
    ('HEX', 'Hexagon', '6-sided section'),
    ('OCT', 'Octagon', '8-sided section'),
    ('CUSTOM', 'Saved Profile', 'Use a saved curve cross-section'),
]


def default_library():
    return bpy.utils.user_resource('CONFIG', path='mecha_lab/assets', create=True)


def folder(settings):
    path = bpy.path.abspath(settings.library_path).strip() or default_library()
    os.makedirs(path, exist_ok=True)
    return Path(path)


def items_for(kind, context):
    scene = context.scene if context else bpy.context.scene
    if not scene or not hasattr(scene, 'mch_settings'):
        return [('NONE', 'No library items', '')]
    files = sorted(folder(scene.mch_settings).glob(kind + '__*.blend'))
    result = [('NONE', 'Select a preset...', '')]
    result.extend((p.name, p.stem.split('__', 1)[1].replace('_', ' '), str(p)) for p in files)
    _ENUM_KEEPALIVE[kind] = result   # Blender RNA enum callbacks require persistent strings.
    return _ENUM_KEEPALIVE[kind]


def mesh_items(self, context):
    return items_for('MESH', context)


def profile_items(self, context):
    return items_for('PROFILE', context)


def activate_only(context, obj):
    if context.mode != 'OBJECT' and context.object:
        bpy.ops.object.mode_set(mode='OBJECT')
    for old in context.selected_objects:
        old.select_set(False)
    obj.hide_set(False)
    obj.select_set(True)
    context.view_layer.objects.active = obj


def make_empty_mesh_object(context, name, collection=None):
    me = bpy.data.meshes.new(name + '_Mesh')
    ob = bpy.data.objects.new(name, me)
    (collection or context.collection).objects.link(ob)
    return ob


def output_group(name):
    group = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    group.interface.new_socket(name='Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    output = group.nodes.new('NodeGroupOutput')
    output.name = 'MCH_OUTPUT'
    return group, output


def object_info(group, ob, name, relative=True):
    node = group.nodes.new('GeometryNodeObjectInfo')
    node.name = name
    node.inputs['Object'].default_value = ob
    node.inputs['As Instance'].default_value = False
    node.transform_space = 'RELATIVE' if relative else 'ORIGINAL'
    return node


def find_gn(ob):
    return next((m for m in ob.modifiers if m.type == 'NODES' and m.name.startswith('MCH_')), None)


def safe_apply(context, ob, mod):
    """Apply one modifier without bpy.ops (works on Alt+D shared meshes, no UI context).

    v0.5.9 used bpy.ops.object.modifier_apply, which fails on multi-user data
    ("Modifiers cannot be applied to multi-user data") and needs an active
    object.  core_geometry evaluates, validates and only then writes back, so a
    failure leaves the mesh untouched.  Errors are raised as RuntimeError.
    """
    activate_only(context, ob)
    policy = context.scene.mch_cut.shared_mesh if hasattr(context.scene, 'mch_cut') else 'SINGLE'
    try:
        core_geometry.apply_single_modifier(context, ob, mod, policy)
    except core_geometry.CutError as ex:
        raise RuntimeError(str(ex)) from ex


def boolean_modifier(target, cutter, operation):
    mod = target.modifiers.new('MCH_' + operation, 'BOOLEAN')
    mod.operation = operation
    mod.solver = 'EXACT'
    mod.object = cutter
    return mod


def remove_object(ob):
    if ob is not None and ob.name in bpy.data.objects:
        bpy.data.objects.remove(ob, do_unlink=True)


def unique_asset_name(label):
    label = re.sub(r'[^\w.\-]+', '_', label.strip(), flags=re.UNICODE).strip('._')
    return label[:72] or 'Untitled'


def library_write(filepath, ob, data):
    clone = bpy.data.objects.new('MCH_LIBRARY_ITEM', data)
    try:
        bpy.data.libraries.write(str(filepath), {clone}, fake_user=True, compress=True)
    finally:
        bpy.data.objects.remove(clone, do_unlink=True)
        if data.users == 0:
            if isinstance(data, bpy.types.Mesh):
                bpy.data.meshes.remove(data)
            elif isinstance(data, bpy.types.Curve):
                bpy.data.curves.remove(data)


def library_load(filepath, collection):
    with bpy.data.libraries.load(str(filepath), link=False) as (src, dest):
        dest.objects = [src.objects[0]] if src.objects else []
    if not dest.objects or not dest.objects[0]:
        raise ValueError('Preset .blend contains no object')
    ob = dest.objects[0]
    collection.objects.link(ob)
    return ob


def get_profile_resource(context, filename):
    if not filename or filename == 'NONE':
        return None
    path = folder(context.scene.mch_settings) / filename
    if not path.is_file():
        return None
    for ob in bpy.data.objects:
        if ob.get('mch_profile_file') == str(path):
            return ob
    collection = bpy.data.collections.get('MCH Profile Resources')
    if not collection:
        collection = bpy.data.collections.new('MCH Profile Resources')
        context.scene.collection.children.link(collection)
    ob = library_load(path, collection)
    if ob.type != 'CURVE':
        remove_object(ob)
        return None
    ob.name = 'MCH Profile | ' + path.stem
    ob['mch_profile_file'] = str(path)
    ob.hide_set(True)
    ob.hide_render = True
    return ob


# -----------------------------------------------------------------------------
# Live geometry nodes
# -----------------------------------------------------------------------------


def set_sweep_parameters(ob):
    mod = find_gn(ob)
    if not mod or not mod.node_group:
        return
    nodes = mod.node_group.nodes
    prop = ob.mch_live
    rect = nodes.get('MCH_RECT')
    if rect:
        rect.inputs['Width'].default_value = prop.width
        rect.inputs['Height'].default_value = prop.depth
    ellipse = nodes.get('MCH_ELLIPSE_SCALE')
    if ellipse:
        ellipse.inputs['Scale'].default_value = (prop.width * 0.5, prop.depth * 0.5, 1.0)
    custom = nodes.get('MCH_CUSTOM_SCALE')
    if custom:
        custom.inputs['Scale'].default_value = (prop.width, prop.depth, 1.0)


_MC_NODES = ('MCH_TWIST', 'MCH_PROFILE_ROT', 'MCH_INST_ROT')


def _mesh_curve_nodes_ok(ob):
    mod = find_gn(ob)
    if not mod or not mod.node_group:
        return None
    nodes = mod.node_group.nodes
    need = ('MCH_TWIST', 'MCH_PROFILE_ROT') if ob.get('mch_role') in {'PANEL', 'CURVE'} else ('MCH_TWIST', 'MCH_INST_ROT')
    return nodes if all(nodes.get(n) for n in need) else None


def set_mesh_curve_parameters(ob):
    """Resolution / segments / rotation / twist of a live Mesh Curve (sweep or curve array).

    Live objects made before v0.9 lack the twist/rotation nodes: their node
    group is rebuilt once, then values are only written to node sockets.
    """
    p = ob.mch_live
    role = ob.get('mch_role')
    if p.path is not None and p.path.type == 'CURVE':
        if p.path.data.resolution_u != p.resolution:
            p.path.data.resolution_u = p.resolution
    nodes = _mesh_curve_nodes_ok(ob)
    if nodes is None:
        mod = find_gn(ob)
        if not mod or not p.path:
            return
        old = mod.node_group
        if role in {'PANEL', 'CURVE'}:
            mod.node_group = sweep_group(ob, p.path, p.custom_profile)
        elif role == 'ARRAY' and p.source:
            mod.node_group = array_group(ob, p.path, p.source)
        else:
            return
        if old and old.users == 0:
            bpy.data.node_groups.remove(old)
        nodes = mod.node_group.nodes
    nodes['MCH_TWIST'].inputs[1].default_value = p.twist
    rot = nodes.get('MCH_PROFILE_ROT') or nodes.get('MCH_INST_ROT')
    if rot is not None:
        rot.inputs['Rotation'].default_value = (p.rot_x, p.rot_y, p.rot_z)
    circle = nodes.get('MCH_CIRCLE')
    if circle is not None and p.shape == 'ROUND':
        circle.inputs['Resolution'].default_value = p.profile_segments


def update_mesh_curve(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and ob.type == 'MESH' and ob.get('mch_role') in {'PANEL', 'CURVE', 'ARRAY'}:
        set_mesh_curve_parameters(ob)


def update_live_dimensions(self, context):
    if self.id_data and self.id_data.type == 'MESH':
        if self.id_data.get('mch_role') in {'PANEL', 'CURVE'}:
            set_sweep_parameters(self.id_data)


def update_live_spacing(self, context):
    ob = self.id_data
    if not ob or ob.get('mch_role') != 'ARRAY':
        return
    mod = find_gn(ob)
    if mod and mod.node_group:
        node = mod.node_group.nodes.get('MCH_POINTS')
        scale = mod.node_group.nodes.get('MCH_ARRAY_SCALE')
        if node:
            node.inputs['Length'].default_value = max(0.001, self.spacing)
        if scale:
            scale.inputs[1].default_value = max(0.001, self.array_scale)


def _twisted_curve(group, curve_socket, twist):
    """Curve -> Set Curve Tilt(existing tilt + factor * twist): total twist along the path."""
    tilt = group.nodes.new('GeometryNodeSetCurveTilt')
    tilt.name = 'MCH_TILT'
    param = group.nodes.new('GeometryNodeSplineParameter')
    base = group.nodes.new('GeometryNodeInputCurveTilt')
    mul = group.nodes.new('ShaderNodeMath')
    mul.operation = 'MULTIPLY'
    mul.name = 'MCH_TWIST'
    mul.inputs[1].default_value = twist
    add = group.nodes.new('ShaderNodeMath')
    add.operation = 'ADD'
    group.links.new(param.outputs['Factor'], mul.inputs[0])
    group.links.new(base.outputs['Tilt'], add.inputs[0])
    group.links.new(mul.outputs['Value'], add.inputs[1])
    group.links.new(add.outputs['Value'], tilt.inputs['Tilt'])
    group.links.new(curve_socket, tilt.inputs['Curve'])
    return tilt.outputs['Curve']


def sweep_group(carrier, path, profile_ob=None):
    params = carrier.mch_live
    group, end = output_group('MCH Sweep | ' + carrier.name)
    path_node = object_info(group, path, 'MCH_PATH')

    if params.shape == 'CUSTOM' and profile_ob and profile_ob.type == 'CURVE':
        profile = object_info(group, profile_ob, 'MCH_CUSTOM_PROFILE')
        scale = group.nodes.new('GeometryNodeTransform')
        scale.name = 'MCH_CUSTOM_SCALE'
        scale.inputs['Scale'].default_value = (params.width, params.depth, 1.0)
        group.links.new(profile.outputs['Geometry'], scale.inputs['Geometry'])
        profile_geometry = scale.outputs['Geometry']
    elif params.shape == 'RECT' or (params.shape == 'CUSTOM' and not profile_ob):
        rect = group.nodes.new('GeometryNodeCurvePrimitiveQuadrilateral')
        rect.name = 'MCH_RECT'
        rect.mode = 'RECTANGLE'
        rect.inputs['Width'].default_value = params.width
        rect.inputs['Height'].default_value = params.depth
        profile_geometry = rect.outputs['Curve']
    else:
        circle = group.nodes.new('GeometryNodeCurvePrimitiveCircle')
        circle.name = 'MCH_CIRCLE'
        count = {'ROUND': params.profile_segments, 'TRI': 3, 'HEX': 6, 'OCT': 8}.get(params.shape, 32)
        circle.inputs['Resolution'].default_value = count
        circle.inputs['Radius'].default_value = 1.0
        scale = group.nodes.new('GeometryNodeTransform')
        scale.name = 'MCH_ELLIPSE_SCALE'
        scale.inputs['Scale'].default_value = (params.width * 0.5, params.depth * 0.5, 1.0)
        group.links.new(circle.outputs['Curve'], scale.inputs['Geometry'])
        profile_geometry = scale.outputs['Geometry']

    rot = group.nodes.new('GeometryNodeTransform')
    rot.name = 'MCH_PROFILE_ROT'
    rot.inputs['Rotation'].default_value = (params.rot_x, params.rot_y, params.rot_z)
    group.links.new(profile_geometry, rot.inputs['Geometry'])
    profile_geometry = rot.outputs['Geometry']

    mesh = group.nodes.new('GeometryNodeCurveToMesh')
    mesh.name = 'MCH_SWEEP'
    mesh.inputs['Fill Caps'].default_value = True
    group.links.new(_twisted_curve(group, path_node.outputs['Geometry'], params.twist), mesh.inputs['Curve'])
    group.links.new(profile_geometry, mesh.inputs['Profile Curve'])
    # Blender 4.5+ explicit scale replaces implicit use of curve point radius.
    if 'Scale' in mesh.inputs:
        radius = group.nodes.new('GeometryNodeInputRadius')
        group.links.new(radius.outputs['Radius'], mesh.inputs['Scale'])
    group.links.new(mesh.outputs['Mesh'], end.inputs['Geometry'])
    return group


def rebuild_sweep(self, context):
    ob = self.id_data
    if not ob or ob.get('mch_role') not in {'PANEL', 'CURVE'}:
        return
    path = self.path
    mod = find_gn(ob)
    if not path or not mod:
        return
    old = mod.node_group
    mod.node_group = sweep_group(ob, path, self.custom_profile)
    if old and old.users == 0:
        bpy.data.node_groups.remove(old)


def array_group(carrier, path, source):
    p = carrier.mch_live
    group, end = output_group('MCH Array | ' + carrier.name)
    curve = object_info(group, path, 'MCH_PATH')
    points = group.nodes.new('GeometryNodeCurveToPoints')
    points.name = 'MCH_POINTS'
    points.mode = 'LENGTH'
    points.inputs['Length'].default_value = p.spacing
    group.links.new(_twisted_curve(group, curve.outputs['Geometry'], p.twist), points.inputs['Curve'])

    source_info = object_info(group, source, 'MCH_SOURCE', relative=False)
    instances = group.nodes.new('GeometryNodeInstanceOnPoints')
    instances.name = 'MCH_INSTANCES'
    group.links.new(points.outputs['Points'], instances.inputs['Points'])
    group.links.new(source_info.outputs['Geometry'], instances.inputs['Instance'])
    group.links.new(points.outputs['Rotation'], instances.inputs['Rotation'])

    radius = group.nodes.new('GeometryNodeInputRadius')
    multiply = group.nodes.new('ShaderNodeMath')
    multiply.operation = 'MULTIPLY'
    multiply.name = 'MCH_ARRAY_SCALE'
    multiply.inputs[1].default_value = p.array_scale
    group.links.new(radius.outputs['Radius'], multiply.inputs[0])
    group.links.new(multiply.outputs['Value'], instances.inputs['Scale'])

    # Rotation X/Y/Z of every placed copy in its own (curve-aligned) space.
    inst_rot = group.nodes.new('GeometryNodeRotateInstances')
    inst_rot.name = 'MCH_INST_ROT'
    inst_rot.inputs['Rotation'].default_value = (p.rot_x, p.rot_y, p.rot_z)
    inst_rot.inputs['Local Space'].default_value = True
    group.links.new(instances.outputs['Instances'], inst_rot.inputs['Instances'])
    instances = inst_rot

    # Keep array as lightweight instances while editing.  Only realize when
    # the user commits the result to a real mesh (or performs a mesh Boolean).
    realize = group.nodes.new('GeometryNodeRealizeInstances')
    realize.name = 'MCH_ARRAY_REALIZE'
    switch = group.nodes.new('GeometryNodeSwitch')
    switch.name = 'MCH_ARRAY_BAKE_SWITCH'
    switch.input_type = 'GEOMETRY'
    switch.inputs['Switch'].default_value = False
    group.links.new(instances.outputs['Instances'], realize.inputs['Geometry'])
    group.links.new(instances.outputs['Instances'], switch.inputs['False'])
    group.links.new(realize.outputs['Geometry'], switch.inputs['True'])
    group.links.new(switch.outputs['Output'], end.inputs['Geometry'])
    return group


def make_live(context, path, kind, target=None, source=None):
    carrier = make_empty_mesh_object(context, 'MCH_' + kind.title() + '_Live')
    carrier.matrix_world = path.matrix_world.copy()
    carrier['mch_role'] = kind
    path['mch_path'] = True
    path['mch_carrier'] = carrier.name
    carrier.mch_live.path = path
    s = context.scene.mch_settings
    prop = carrier.mch_live
    prop.shape = s.profile_shape
    prop.width = s.line_width
    prop.depth = s.line_depth
    prop.spacing = s.array_spacing
    prop.array_scale = s.array_scale
    if path.type == 'CURVE':
        prop.resolution = path.data.resolution_u

    if kind in {'PANEL', 'CURVE'}:
        if s.profile_shape == 'CUSTOM':
            prop.custom_profile = get_profile_resource(context, s.profile_preset)
        group = sweep_group(carrier, path, prop.custom_profile)
    elif kind == 'ARRAY':
        prop.source = source
        group = array_group(carrier, path, source)
    else:
        raise ValueError('Unknown live kind')

    gn = carrier.modifiers.new('MCH_LiveGeometry', 'NODES')
    gn.node_group = group
    if kind == 'PANEL':
        carrier.mch_live.target = target
        cutter = boolean_modifier(target, carrier, 'DIFFERENCE')
        cutter.name = 'MCH_PanelCut_' + carrier.name
        carrier['mch_boolean'] = cutter.name
        carrier.display_type = 'WIRE'
        carrier.hide_set(True)
        activate_only(context, path)
    else:
        carrier.display_type = 'SOLID'
        activate_only(context, path)
    return carrier


# -----------------------------------------------------------------------------
# UI properties
# -----------------------------------------------------------------------------


class MCH_PG_Live(bpy.types.PropertyGroup):
    path: PointerProperty(type=bpy.types.Object)
    target: PointerProperty(type=bpy.types.Object)
    source: PointerProperty(type=bpy.types.Object)
    custom_profile: PointerProperty(type=bpy.types.Object, update=rebuild_sweep)
    shape: EnumProperty(name='Section', items=_PROFILE_ITEMS, default='RECT', update=rebuild_sweep)
    width: FloatProperty(name='Width', default=0.035, min=0.00001, precision=4, update=update_live_dimensions)
    depth: FloatProperty(name='Depth', default=0.045, min=0.00001, precision=4, update=update_live_dimensions)
    spacing: FloatProperty(name='Spacing', default=0.28, min=0.001, precision=3, update=update_live_spacing)
    array_scale: FloatProperty(name='Global Size', default=1.0, min=0.001, update=update_live_spacing)
    resolution: bpy.props.IntProperty(name='Curve Resolution', default=24, min=1, max=128, update=update_mesh_curve,
        description='Samples per curve segment (smoothness of the path)')
    profile_segments: bpy.props.IntProperty(name='Profile Segments', default=32, min=3, max=256,
        update=update_mesh_curve, description='Segments of the round cross-section')
    rot_x: FloatProperty(name='Rotation X', default=0.0, subtype='ANGLE', update=update_mesh_curve)
    rot_y: FloatProperty(name='Rotation Y', default=0.0, subtype='ANGLE', update=update_mesh_curve)
    rot_z: FloatProperty(name='Rotation Z', default=0.0, subtype='ANGLE', update=update_mesh_curve,
        description='Sweep: rotates the cross-section. Array: rotates each copy in curve space')
    twist: FloatProperty(name='Twist', default=0.0, subtype='ANGLE', update=update_mesh_curve,
        description='Total twist from the start to the end of the curve')


TOOL_ITEMS = tool_state.TOOL_ENUM_ITEMS


class MCH_PG_Settings(bpy.types.PropertyGroup):
    # v0.5.9 session toggle; hotkeys are now scoped to the MECHA LAB workspace.
    mch_enabled: BoolProperty(name='Enable Mecha Lab Hotkeys (legacy, unused)', default=False)
    mch_active_tool: EnumProperty(name='Selected Tool', items=TOOL_ITEMS, default='CUT')
    mch_mask_thickness: FloatProperty(name='Raise Thickness', default=0.05, min=0.0001,
        soft_max=1.0, precision=4, description='Outward thickness for masked face extraction')
    auto_apply: BoolProperty(name='Auto Apply', default=True, description='Apply Booleans/Cut and Remove immediately; OFF keeps editable cut curves and boolean modifiers')
    keep_cutter: BoolProperty(name='Keep cutter after apply', default=False)
    cut_draw_style: EnumProperty(name='Cut Shape', items=[
        ('POLYLINE','Points / Line','Left click 2+ points; Enter to choose the side to discard'),
        ('FREEHAND','Freehand','Drag to draw a freehand cut contour'),
        ('BOX','Rectangle','Click and drag a rectangular cut'),
        ('CIRCLE','Circle','Click center and drag radius to cut'),
        ('POLYGON','Custom Polygon','Click vertices to create a closed mechanical polygon; click first vertex to apply'),
        ('NGON','Regular N-gon','Drag from center to radius; adjust number of sides')], default='POLYLINE')
    cut_ngon_sides: bpy.props.IntProperty(name='Polygon Sides',default=6,min=3,max=64,
        description='Number of sides for a regular polygon cutter')
    cut_immediate: BoolProperty(name='Instant Cut',default=True,
        description='Apply a completed stroke immediately without picking its removal side; polygon interior is discarded')
    cut_repeat: BoolProperty(name='Keep Cut Mode',default=True,
        description='Keep drawing new cuts until Q or right-click exits; Esc clears the current stroke')
    cut_closed: BoolProperty(name='Closed Outline', default=False,
        description='Cut out a closed region instead of a line across the model; F also toggles while drawing')
    cut_fast_bisect: BoolProperty(name='Fast Plane Cut (2 pts)', default=True,
        description='Two-point straight stroke, Apply ON: BMesh bisect+cap instead of Boolean; faster on dense meshes')
    cut_fill_caps: BoolProperty(name='Fill Straight Cut', default=True,
        description='Cap planar cut boundary for closed manifold meshes; may require cleanup on non-manifold input')

    library_path: StringProperty(name='Library Directory', subtype='DIR_PATH', default='')
    asset_name: StringProperty(name='Preset Name', default='My_Mech_Part')
    mesh_preset: EnumProperty(name='Mesh Preset', items=mesh_items)
    profile_preset: EnumProperty(name='Profile Preset', items=profile_items)
    profile_shape: EnumProperty(name='Section', items=_PROFILE_ITEMS, default='RECT')
    path_draw_mode: EnumProperty(name='Path Draw Mode',items=[('POLY','Polyline','Click control points; Shift snaps to 45 degrees'),('FREE','Free Draw','Hold LMB to draw sampled control points')],default='POLY')
    path_point_type: EnumProperty(name='New Points', items=[
        ('VECTOR', 'Straight', 'Sharp corners (VECTOR handles); click a point to make it smooth'),
        ('AUTO', 'Smooth', 'Smooth curve through points (AUTO handles)')], default='VECTOR')
    path_sample_px: bpy.props.IntProperty(name='Free Draw Spacing (px)',default=10,min=3,max=100)
    line_width: FloatProperty(name='Width', default=0.035, min=0.00001, precision=4)
    line_depth: FloatProperty(name='Depth', default=0.045, min=0.00001, precision=4)
    array_source: PointerProperty(name='Array Source', type=bpy.types.Object, poll=lambda s, o: o.type == 'MESH')
    array_spacing: FloatProperty(name='Spacing', default=0.28, min=0.001, precision=3)
    array_scale: FloatProperty(name='Overall Size', default=1.0, min=0.001)
    point_radius: FloatProperty(name='Point Scale', default=1.0, min=0.001)
    # Radial Array defaults are scene-level presets; after creation use the
    # live values stored on the newly generated carrier object.
    radial_count: bpy.props.IntProperty(name='Copies', default=24, min=1, max=2048)
    radial_auto_radius: BoolProperty(name='Use Source Distance', default=True,
        description='Read ring radius from selected source origin to 3D cursor')
    radial_radius: FloatProperty(name='Initial Radius', default=1.0, min=0.0, precision=4,
        description='Initial ring radius when automatic source distance is disabled')
    radial_arc: FloatProperty(name='Arc', default=6.283185307179586, min=0.001,
        max=6.283185307179586, subtype='ANGLE')
    radial_phase: FloatProperty(name='Start Rotation', default=0.0, subtype='ANGLE')
    radial_scale: FloatProperty(name='Copy Size', default=1.0, min=0.001)
    radial_follow: BoolProperty(name='Rotate Each Copy', default=False,
        description='OFF (default): copies keep the source orientation. ON: copies turn along the ring')
    radial_hide_source: BoolProperty(name='Hide Original Source', default=True)
    delete_path_on_bake: BoolProperty(name='Remove path on confirm', default=True)
    fuse_mode: EnumProperty(name='Smart Fuse Method', items=[
        ('SEAM','Seam Shape','Non-destructive seam fillet or flat chamfer, preserves hard surface detail'),
        ('SOFT','Soft Fuse','Voxel fusion + smooth, better for organic blobs but loses detail')], default='SEAM')
    fuse_edge_style: EnumProperty(name='Seam Style', items=[
        ('FILLET', 'Fillet', 'Rounded transition with multiple edge loops'),
        ('CHAMFER', 'Chamfer', 'Straight flat transition, one bevel segment')], default='FILLET')
    fuse_radius: FloatProperty(name='Seam Width', default=0.08, min=0.0001, soft_max=1.0, precision=4,
                               description='Length on the mesh in target local units; may clamp at tight corners')
    fuse_segments: bpy.props.IntProperty(name='Initial Segments', default=6, min=1, max=32)
    fuse_voxel_size: FloatProperty(name='Initial Voxel Size', default=0.025, min=0.0001, precision=4)
    fuse_smooth_iterations: bpy.props.IntProperty(name='Initial Iterations', default=3, min=0, max=30)
    fuse_smooth_factor: FloatProperty(name='Initial Smooth', default=0.8, min=0, max=2)
    join_remesh: BoolProperty(name='Join selected meshes first', default=True)
    voxel_size: FloatProperty(name='Voxel Size', default=0.025, min=0.0001, precision=4)
    smooth_iterations: bpy.props.IntProperty(name='Smooth Iterations', default=2, min=0, max=30)
    smooth_factor: FloatProperty(name='Smooth Factor', default=0.55, min=0, max=2)
    apply_remesh: BoolProperty(name='Apply remesh + smooth', default=True)
    apply_existing: BoolProperty(name='Apply existing modifiers first', default=True,
        description='Before joining/remeshing, bake current modifiers on each selected mesh')


# -----------------------------------------------------------------------------
# Smart Fuse - non-destructive Boolean union + seam-only bevel or volumetric fuse
# Geometry Nodes uses Mesh Boolean's intersection edge field to drive a named
# bevel-weight attribute. Voxel mode is a separate option for sculpt-like joins.
# -----------------------------------------------------------------------------

_FUSE_MOD_GN = 'MCH_Fuse_UnionGN'
_FUSE_MOD_BEVEL = 'MCH_Fuse_SeamBevel'
_FUSE_MOD_VOXEL = 'MCH_Fuse_Voxel'
_FUSE_MOD_SMOOTH = 'MCH_Fuse_Smooth'
_FUSE_EDGE_ATTRIBUTE = 'mch_smart_fuse_seam_weight'


def fuse_sync(self, context):
    """Scene-/object-local sliders update actual modifiers, never bake automatically."""
    target = self.id_data
    if not isinstance(target, bpy.types.Object) or not self.active:
        return
    bev = target.modifiers.get(_FUSE_MOD_BEVEL)
    vol = target.modifiers.get(_FUSE_MOD_VOXEL)
    smooth = target.modifiers.get(_FUSE_MOD_SMOOTH)
    if bev:
        bev.width = self.radius
        bev.profile = 0.5
        bev.segments = 1 if self.edge_style == 'CHAMFER' else max(2, self.segments)
        bev.show_viewport = self.mode == 'SEAM'
        bev.show_render = self.mode == 'SEAM'
    if vol:
        vol.voxel_size = self.voxel_size
        vol.show_viewport = self.mode == 'SOFT'
        vol.show_render = self.mode == 'SOFT'
    if smooth:
        smooth.factor = self.smooth_factor
        smooth.iterations = self.smooth_iterations
        smooth.show_viewport = self.mode == 'SOFT' and self.smooth_iterations > 0
        smooth.show_render = self.mode == 'SOFT' and self.smooth_iterations > 0


class MCH_PG_Fuse(bpy.types.PropertyGroup):
    active: BoolProperty(name='Fuse Live', default=False)
    source: PointerProperty(name='Linked Source Mesh', type=bpy.types.Object)
    mode: EnumProperty(name='Blend Mode', items=[
        ('SEAM', 'Seam Shape', 'Fillet or chamfer detected intersection edges; preserve most of the existing mesh'),
        ('SOFT', 'Soft Fuse', 'Voxel remesh the union and smooth the entire surface; consumes detail')],
        default='SEAM', update=fuse_sync)
    edge_style: EnumProperty(name='Seam Style', items=[
        ('FILLET', 'Fillet', 'Rounded edge transition using multiple segments'),
        ('CHAMFER', 'Chamfer', 'One flat beveled face along the union seam')],
        default='FILLET', update=fuse_sync)
    radius: FloatProperty(name='Seam Width', default=0.08, min=0.0001, soft_max=1.0, precision=4,
                          description='Fillet or chamfer width in target-object local units', update=fuse_sync)
    segments: bpy.props.IntProperty(name='Segments', default=6, min=1, max=32, update=fuse_sync)
    voxel_size: FloatProperty(name='Voxel Size', default=0.025, min=0.0001, precision=4,
                              description='Smaller creates more mesh density and can be expensive', update=fuse_sync)
    smooth_iterations: bpy.props.IntProperty(name='Smooth Iterations', default=3, min=0, max=30, update=fuse_sync)
    smooth_factor: FloatProperty(name='Smooth Amount', default=0.8, min=0, max=2, update=fuse_sync)
    delete_source_on_confirm: BoolProperty(name='Delete source on confirm', default=True,
        description='Deletes the linked source object only after all active modifiers were baked successfully')
    source_original_hidden: BoolProperty(default=False)
    source_original_hide_render: BoolProperty(default=False)
    source_original_display: StringProperty(default='TEXTURED')


def fuse_build_group(source, solver='EXACT'):
    group, output = output_group('MCH Smart Fuse | ' + source.name)
    group_input = group.nodes.new('NodeGroupInput')
    group_input.location = (-620, 160)
    info = object_info(group, source, 'Linked Source', relative=True)
    info.location = (-620, -100)

    join = group.nodes.new('GeometryNodeMeshBoolean')
    join.name = 'MCH_Union'
    join.operation = 'UNION'
    join.solver = solver  # intersecting edge selection requires Exact/Manifold solver
    join.location = (-340, 140)

    # The Blender 4.x Mesh Boolean's UNION socket interface has changed between
    # releases: either one multi-input 'Mesh' or separate 'Mesh 1'/'Mesh 2'.
    # Detect the actual sockets at runtime, instead of hardcoding a version.
    available = [socket for socket in join.inputs if socket.enabled and socket.type == 'GEOMETRY']
    if 'Mesh' in join.inputs and join.inputs['Mesh'].is_multi_input:
        input_socket = join.inputs['Mesh']
        group.links.new(group_input.outputs['Geometry'], input_socket)
        group.links.new(info.outputs['Geometry'], input_socket)
    elif 'Mesh 1' in join.inputs and 'Mesh 2' in join.inputs and join.inputs['Mesh 1'].enabled:
        group.links.new(group_input.outputs['Geometry'], join.inputs['Mesh 1'])
        group.links.new(info.outputs['Geometry'], join.inputs['Mesh 2'])
    elif len(available) == 1 and available[0].is_multi_input:
        group.links.new(group_input.outputs['Geometry'], available[0])
        group.links.new(info.outputs['Geometry'], available[0])
    elif len(available) >= 2:
        group.links.new(group_input.outputs['Geometry'], available[0])
        group.links.new(info.outputs['Geometry'], available[1])
    else:
        bpy.data.node_groups.remove(group)
        raise RuntimeError('This Blender version has an unsupported Mesh Boolean socket layout.')

    mark = group.nodes.new('GeometryNodeStoreNamedAttribute')
    mark.name = 'MCH_Mark_Seam_Only'
    mark.data_type = 'FLOAT'
    mark.domain = 'EDGE'
    mark.location = (-70, 150)
    mark.inputs['Name'].default_value = _FUSE_EDGE_ATTRIBUTE
    mark.inputs['Value'].default_value = 1.0
    group.links.new(join.outputs['Mesh'], mark.inputs['Geometry'])
    group.links.new(join.outputs['Intersecting Edges'], mark.inputs['Selection'])
    group.links.new(mark.outputs['Geometry'], output.inputs['Geometry'])
    output.location = (180, 150)
    return group


def fuse_is_live(ob):
    """A preview is live only if its node modifier still exists.  Undo or a
    manual modifier removal can leave ``mch_fuse.active`` stale, which used to
    block every later Smart Fuse on that object (B03)."""
    if ob is None or ob.type != 'MESH' or not getattr(ob.mch_fuse, 'active', False):
        return False
    return ob.modifiers.get(_FUSE_MOD_GN) is not None


def fuse_target_from_context(context):
    """The preview the panel / Confirm / Cancel work on: the ACTIVE object's
    preview, or the preview whose source is being edited.  A preview on some
    other object no longer hijacks the panel when new meshes are selected."""
    ob = context.active_object
    if fuse_is_live(ob):
        return ob
    pending = getattr(context.scene, 'mch_fuse_preview_target', None)
    if pending and pending.name in bpy.data.objects and fuse_is_live(pending):
        src = pending.mch_fuse.source
        if ob is None or ob == src or not context.selected_objects:
            return pending
    return None


def fuse_pending_elsewhere(context):
    pending = getattr(context.scene, 'mch_fuse_preview_target', None)
    if pending and pending.name in bpy.data.objects and fuse_is_live(pending) and \
            fuse_target_from_context(context) != pending:
        return pending
    return None


def fuse_restore_source(target):
    props = target.mch_fuse
    source = props.source
    if source and source.name in bpy.data.objects:
        source.hide_set(props.source_original_hidden)
        source.hide_render = props.source_original_hide_render
        source.display_type = props.source_original_display


def fuse_dispose_group(target):
    mod = target.modifiers.get(_FUSE_MOD_GN)
    if not mod:
        return
    group = mod.node_group
    target.modifiers.remove(mod)
    if group is not None and group.users == 0:
        bpy.data.node_groups.remove(group)


def _purge_fuse_groups():
    """Remove Smart Fuse node groups nothing uses any more (they piled up as
    orphans after every Confirm)."""
    for g in list(bpy.data.node_groups):
        if g.name.startswith('MCH Smart Fuse') and g.users == 0:
            bpy.data.node_groups.remove(g)


def fuse_cleanup(target, restore_source=True):
    if restore_source:
        fuse_restore_source(target)
    for name in (_FUSE_MOD_SMOOTH, _FUSE_MOD_VOXEL, _FUSE_MOD_BEVEL):
        mod = target.modifiers.get(name)
        if mod:
            target.modifiers.remove(mod)
    fuse_dispose_group(target)
    target.mch_fuse.active = False
    target.mch_fuse.source = None


def fuse_validate(context, target):
    """Evaluate only the union GN modifier and check that a seam was found.

    Returns an explanation string when the input cannot be fused, else None.
    """
    gn = target.modifiers.get(_FUSE_MOD_GN)
    if gn is None:
        return 'Smart Fuse node modifier missing'
    saved = [(m, m.show_viewport) for m in target.modifiers]
    try:
        for m, _ in saved:
            m.show_viewport = (m == gn)
        dg = context.evaluated_depsgraph_get()
        ev = target.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            if me is None or not me.polygons:
                return 'Union produced an empty mesh'
            attr = me.attributes.get(_FUSE_EDGE_ATTRIBUTE)
            seam = sum(1 for d in attr.data if d.value > 0.5) if attr else 0
        finally:
            ev.to_mesh_clear()
    finally:
        for m, show in saved:
            m.show_viewport = show
    if seam == 0:
        return ('No intersection seam found: the two meshes must really overlap. '
                'Touching, separate or open (non-closed) meshes cannot be fused.')
    return None


def fuse_setup(context, target, source):
    """Live Smart Fuse preview of ``source`` on ``target`` (raises RuntimeError, leaves nothing behind)."""
    if source.data.shape_keys or target.data.shape_keys:
        raise RuntimeError('remove/apply shape keys first')
    if target.library or source.library:
        raise RuntimeError('make local editable copies of linked-library objects first')
    if target.mch_fuse.active and not fuse_is_live(target):
        fuse_cleanup(target)            # stale flag (undo / removed modifiers): repair silently
    occupied = [m.name for m in target.modifiers if m.name in
                (_FUSE_MOD_GN, _FUSE_MOD_BEVEL, _FUSE_MOD_VOXEL, _FUSE_MOD_SMOOTH)]
    if occupied:
        raise RuntimeError('existing Smart Fuse modifiers found: finalize or remove them first')
    for ob in (target, source):
        _clear_fuse_seam(ob)
    group = None
    try:
        # 0.24.12 Manifold solver when both meshes are closed: Exact broke the result on the 4th fuse of a chain
        # (holes / overlapping faces), so the next Fuse and every Cut on it went wrong
        closed = (core_geometry.non_manifold_edge_count(target.data) == 0 and
                  core_geometry.non_manifold_edge_count(source.data) == 0)
        group = fuse_build_group(source, 'MANIFOLD' if closed else 'EXACT')
        node_mod = target.modifiers.new(_FUSE_MOD_GN, 'NODES')
        node_mod.node_group = group
        bevel = target.modifiers.new(_FUSE_MOD_BEVEL, 'BEVEL')
        bevel.affect = 'EDGES'
        bevel.limit_method = 'WEIGHT'
        bevel.edge_weight = _FUSE_EDGE_ATTRIBUTE
        bevel.loop_slide = True
        bevel.use_clamp_overlap = True
        bevel.segments = context.scene.mch_settings.fuse_segments
        bevel.width = context.scene.mch_settings.fuse_radius
        bevel.profile = 0.5
        voxel = target.modifiers.new(_FUSE_MOD_VOXEL, 'REMESH')
        voxel.mode = 'VOXEL'
        voxel.use_smooth_shade = True
        target.modifiers.new(_FUSE_MOD_SMOOTH, 'SMOOTH')
        props = target.mch_fuse
        props.source_original_hidden = source.hide_get()
        props.source_original_hide_render = source.hide_render
        props.source_original_display = source.display_type
        props.source = source
        props.active = True
        props.mode = context.scene.mch_settings.fuse_mode
        props.edge_style = context.scene.mch_settings.fuse_edge_style
        props.radius = context.scene.mch_settings.fuse_radius
        props.segments = context.scene.mch_settings.fuse_segments
        props.voxel_size = context.scene.mch_settings.fuse_voxel_size
        props.smooth_iterations = context.scene.mch_settings.fuse_smooth_iterations
        props.smooth_factor = context.scene.mch_settings.fuse_smooth_factor
        props.delete_source_on_confirm = True
        fuse_sync(props, context)
        problem = fuse_validate(context, target)
        if problem and closed:
            group.nodes['MCH_Union'].solver = 'EXACT'       # Manifold found no seam: try Exact
            target.update_tag()
            problem = fuse_validate(context, target)
        if problem:
            raise RuntimeError(problem)
        source.hide_set(True)
        source.hide_render = True
        context.scene.mch_fuse_preview_target = target
    except Exception:
        # No partial node stack or hidden source should be left after failure.
        fuse_cleanup(target)
        # v0.5.9 crashed here: fuse_cleanup may already have removed the
        # group, and touching a removed ID raises ReferenceError.
        try:
            if group is not None and group.users == 0:
                bpy.data.node_groups.remove(group)
        except ReferenceError:
            pass
        raise


def _clear_fuse_seam(ob):
    """0.24.12 the seam mark of an earlier (confirmed) fuse stayed on the mesh: the next fuse counted it as a
    seam (a part far away 'fused'), and the bevel rounded the old seams again."""
    me = ob.data if ob is not None and ob.type == 'MESH' else None
    if me is None or me.users > 1:
        return
    attr = me.attributes.get(_FUSE_EDGE_ATTRIBUTE)
    if attr is not None:
        me.attributes.remove(attr)


def fuse_confirm(context, target):
    """Bake a live Smart Fuse preview into the target mesh. Returns an error text, or None when done."""
    props = target.mch_fuse
    source = props.source
    if not source or source.name not in bpy.data.objects:
        return 'Source object was removed: cannot confirm.'
    # Apply only the active chain; undo remains Blender Ctrl+Z.
    keep_mods = ((_FUSE_MOD_BEVEL,) if props.mode == 'SEAM'
                 else (_FUSE_MOD_VOXEL, _FUSE_MOD_SMOOTH))
    try:
        safe_apply(context, target, target.modifiers[_FUSE_MOD_GN])
        for name in keep_mods:
            mod = target.modifiers.get(name)
            if mod is not None and (name != _FUSE_MOD_SMOOTH or props.smooth_iterations > 0):
                safe_apply(context, target, mod)
    except Exception as exc:
        return 'Could not apply fuse modifiers: ' + str(exc)
    # GN has already been applied at this point, so the source is no longer needed.
    if props.delete_source_on_confirm:
        remove_object(source)
    else:
        fuse_restore_source(target)
    fuse_cleanup(target, restore_source=False)
    _clear_fuse_seam(target)
    _purge_fuse_groups()
    if getattr(context.scene, 'mch_fuse_preview_target', None) == target:
        context.scene.mch_fuse_preview_target = None
    return None


def fuse_confirm_live(context, obs):
    """0.24.12 confirm the live Smart Fuse previews among ``obs`` (a Cut / Split / next Fuse needs the real
    mesh: on a preview it cut the base mesh only, and the hidden source was joined back in).  The selection
    and active object are kept.  Returns the names confirmed; raises RuntimeError when one cannot be baked."""
    live = [o for o in obs if fuse_is_live(o)]
    if not live:
        return []
    sel = [o.name for o in context.selected_objects]
    act = context.view_layer.objects.active
    act_name = act.name if act is not None else None
    done = []
    for o in live:
        err = fuse_confirm(context, o)
        if err:
            raise RuntimeError(f'Smart Fuse on {o.name}: {err}')
        done.append(o.name)
    for o in context.selected_objects:
        o.select_set(False)
    for n in sel:
        ob = bpy.data.objects.get(n)
        if ob is not None:
            ob.select_set(True)
    if act_name in bpy.data.objects:
        context.view_layer.objects.active = bpy.data.objects[act_name]
    return done


class MCH_OT_fuse_create(bpy.types.Operator):
    bl_idname = 'mch.smart_fuse'
    bl_label = 'Smart Fuse: Connect Meshes'
    bl_description = ('Active mesh is the target; automatically find the overlap seam and bevel it, or use voxel '
                      'soft fuse.  2 meshes: live preview.  3 or more: each one is fused into the active one')
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.mode == 'OBJECT' and context.active_object and
                context.active_object.type == 'MESH' and
                len([o for o in context.selected_objects if o.type == 'MESH']) >= 2)

    def execute(self, context):
        target = context.active_object
        if any(o.type != 'MESH' for o in context.selected_objects):
            self.report({'ERROR'}, 'Select mesh objects only (no other object types).')
            return {'CANCELLED'}
        sources = [o for o in context.selected_objects if o != target]
        if not sources:
            self.report({'ERROR'}, 'Select two or more different meshes.')
            return {'CANCELLED'}
        # 0.24.12 a preview still live on the target (or a picked mesh) is confirmed first: fusing the next
        # part onto it used to be refused ("finalize/cancel the existing Smart Fuse")
        try:
            fuse_confirm_live(context, [target] + sources)
        except RuntimeError as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}
        sources = [o for o in sources if o.name in bpy.data.objects]
        if len(sources) == 1:
            try:
                fuse_setup(context, target, sources[0])
            except Exception as exc:
                self.report({'ERROR'}, 'Smart Fuse setup failed: ' + str(exc))
                return {'CANCELLED'}
            activate_only(context, target)
            self.report({'INFO'}, 'Smart Fuse live preview created; edit settings, then Confirm / Apply.')
            return {'FINISHED'}
        # 0.24.12 several parts: nearest first, each fused into the active mesh and confirmed
        tw = target.matrix_world.translation
        sources.sort(key=lambda o: (o.matrix_world.translation - tw).length)
        done, errors = [], {}
        pending = [o.name for o in sources]       # names: a fused source object is deleted
        progress = True
        while pending and progress:     # a part may overlap the target only after its neighbour joined it
            progress = False
            for name in list(pending):
                src = bpy.data.objects.get(name)
                if src is None:
                    pending.remove(name)
                    continue
                try:
                    fuse_setup(context, target, src)
                except Exception as exc:
                    errors[name] = str(exc)
                    continue
                err = fuse_confirm(context, target)
                if err:
                    fuse_cleanup(target)
                    errors[name] = err
                    continue
                done.append(name)
                pending.remove(name)
                progress = True
        activate_only(context, target)
        if not done:
            self.report({'ERROR'}, 'Smart Fuse: nothing could be fused - ' +
                        '; '.join(f'{n}: {errors.get(n, "?").splitlines()[0][:80]}' for n in pending))
            return {'CANCELLED'}
        msg = f'Smart Fuse: {len(done)} part(s) fused into {target.name}'
        if pending:
            msg += ' | not fused (no overlap): ' + ', '.join(pending)
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_fuse_source(bpy.types.Operator):
    bl_idname = 'mch.smart_fuse_source'
    bl_label = 'Edit / Hide Fuse Source'
    bl_options = {'REGISTER', 'UNDO'}
    action: EnumProperty(items=[('EDIT','Edit Source',''), ('HIDE','Return to Preview','')], default='EDIT')

    def execute(self, context):
        target = fuse_target_from_context(context)
        if not target or not target.mch_fuse.source:
            self.report({'ERROR'}, 'No active Smart Fuse preview')
            return {'CANCELLED'}
        source = target.mch_fuse.source
        if self.action == 'EDIT':
            source.hide_set(False)
            source.display_type = 'WIRE'
            activate_only(context, source)
        else:
            source.hide_set(True)
            activate_only(context, target)
        return {'FINISHED'}


class MCH_OT_fuse_cancel(bpy.types.Operator):
    bl_idname = 'mch.smart_fuse_cancel'
    bl_label = 'Cancel Smart Fuse Preview'
    bl_description = 'Delete temporary modifiers and restore the original two objects unchanged'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = fuse_target_from_context(context)
        if not target:
            return {'CANCELLED'}
        fuse_cleanup(target, restore_source=True)
        _purge_fuse_groups()
        context.scene.mch_fuse_preview_target = None
        activate_only(context, target)
        self.report({'INFO'}, 'Smart Fuse cancelled; original objects restored.')
        return {'FINISHED'}


class MCH_OT_fuse_confirm(bpy.types.Operator):
    bl_idname = 'mch.smart_fuse_confirm'
    bl_label = 'Confirm Smart Fuse'
    bl_description = 'Bake the live Boolean and selected edge fillet/voxel smoothing; optionally delete source object'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = fuse_target_from_context(context)
        if not target:
            self.report({'ERROR'}, 'No active Smart Fuse preview')
            return {'CANCELLED'}
        err = fuse_confirm(context, target)
        if err:
            self.report({'ERROR'}, err)
            return {'CANCELLED'}
        activate_only(context, target)
        self.report({'INFO'}, 'Smart Fuse applied; resulting mesh stays on the originally active object.')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Boolean operations — the yellow active object is ALWAYS the target
# -----------------------------------------------------------------------------


def boolean_roles(context):
    """F01 (2026-10-13 final rule): the ACTIVE (yellow) mesh is the CUTTER,
    every other selected mesh is a TARGET."""
    cutter = context.view_layer.objects.active
    if cutter is None or cutter.type != 'MESH' or not cutter.select_get():
        return None, []
    targets = [o for o in context.selected_objects if o.type == 'MESH' and o != cutter and o.library is None]
    return cutter, targets


class MCH_OT_boolean(bpy.types.Operator):
    bl_idname = 'mch.boolean'
    bl_label = 'Mecha Boolean'
    bl_description = ('ACTIVE (yellow) mesh = cutter; it is applied to EVERY other selected mesh '
                      '(each target separately). Failed targets stay unchanged')
    bl_options = {'REGISTER', 'UNDO'}

    operation: EnumProperty(items=[('UNION', 'Union', ''), ('DIFFERENCE', 'Cut', ''), ('INTERSECT', 'Intersect', '')], default='DIFFERENCE')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        cutter, targets = boolean_roles(context)
        if cutter is None or not targets:
            self.report({'WARNING'}, 'Select the target mesh(es), then the CUTTER last (active, yellow).')
            return {'CANCELLED'}
        s = context.scene.mch_settings
        cutter_name = cutter.name
        done, failed = [], []
        from . import core_geometry as _cg
        for target in targets:
            station_primitive.freeze(target)              # parameters would overwrite the result
            _cg.ensure_real_mesh(context, target)        # live primitives: bake before the Boolean
            mod = boolean_modifier(target, cutter, self.operation)
            if s.auto_apply:
                try:
                    safe_apply(context, target, mod)
                    done.append(target)
                except RuntimeError as ex:
                    if target.modifiers.get(mod.name):
                        target.modifiers.remove(mod)
                    failed.append(f'{target.name} ({str(ex).splitlines()[0][:80]})')
            else:
                done.append(target)
        if not done:
            self.report({'ERROR'}, 'Boolean failed on every target (meshes unchanged): ' + '; '.join(failed))
            return {'CANCELLED'}
        if s.auto_apply:
            if not s.keep_cutter and not failed:
                remove_object(cutter)
            else:
                cutter.select_set(False)
        else:
            cutter.display_type = 'WIRE'
            cutter.hide_set(True)
        for o in context.selected_objects:
            o.select_set(False)
        for t in done:
            t.select_set(True)
        context.view_layer.objects.active = done[0]
        msg = f'{self.operation}: {len(done)} target(s) with cutter "{cutter_name}"'
        if failed:
            msg += ' | FAILED (unchanged): ' + '; '.join(failed)
            if not s.keep_cutter:
                msg += ' | cutter kept because a target failed'
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_slice(bpy.types.Operator):
    bl_idname = 'mch.slice'
    bl_label = 'Slice (Keep Both Pieces)'
    bl_description = 'Creates the cut-out intersection as a second mesh, alongside the remaining main mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object is not None and context.active_object.type == 'MESH'

    def execute(self, context):
        cutter, targets = boolean_roles(context)
        if cutter is None or len(targets) != 1:
            self.report({'WARNING'}, 'Select the mesh to slice, then the CUTTER last (active, yellow)')
            return {'CANCELLED'}
        original = targets[0]
        piece = original.copy()
        piece.data = original.data.copy()
        piece.name = original.name + '_SlicePiece'
        context.collection.objects.link(piece)
        piece.matrix_world = original.matrix_world.copy()
        # Modifier stacks are copied from original; the cut is added after existing geometry.
        a = boolean_modifier(piece, cutter, 'INTERSECT')
        b = boolean_modifier(original, cutter, 'DIFFERENCE')
        s = context.scene.mch_settings
        try:
            if s.auto_apply:
                safe_apply(context, piece, a)
                safe_apply(context, original, b)
                if not s.keep_cutter:
                    remove_object(cutter)
            else:
                cutter.hide_set(True)
                cutter.display_type = 'WIRE'
        except RuntimeError as ex:
            for ob, m in ((piece, a), (original, b)):
                if ob.modifiers.get(m.name):
                    ob.modifiers.remove(m)
            remove_object(piece)
            self.report({'ERROR'}, 'Slice failed: ' + str(ex))
            return {'CANCELLED'}
        activate_only(context, original)
        piece.select_set(True)
        self.report({'INFO'}, 'Slice created: remaining solid and intersecting piece')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Direct screen-drawn surface cutting: no cutter object / boolean required.
# Blender's native Knife operator creates actual mesh edges from clicks.
# -----------------------------------------------------------------------------


class MCH_OT_surface_cut(bpy.types.Operator):
    bl_idname = 'mch.surface_cut'
    bl_label = 'Knife Edges Only (Legacy)'
    bl_description = (
        'Click successive points directly on the active mesh to cut its topology. '
        'Enter confirms, Esc cancels. This creates edges only, unlike C Cut & Remove'
    )
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return (context.area is not None and context.area.type == 'VIEW_3D'
                and context.active_object is not None
                and context.active_object.type == 'MESH'
                and context.mode in {'OBJECT', 'EDIT_MESH'})

    def invoke(self, context, event):
        target = context.active_object
        view_area = context.area
        # The N-panel button has UI-region context. The Knife tool must be
        # invoked in the View3D WINDOW region to receive actual viewport input.
        window_region = next((r for r in view_area.regions if r.type == 'WINDOW'), None)
        if window_region is None:
            self.report({'ERROR'}, 'No 3D viewport window region available')
            return {'CANCELLED'}

        # Object Mode: only edit the actively selected target, never other
        # simultaneously selected objects. Edit Mode: keep current edit state.
        if context.mode == 'OBJECT':
            for ob in context.selected_objects:
                if ob != target:
                    ob.select_set(False)
            target.select_set(True)
            context.view_layer.objects.active = target
            try:
                bpy.ops.object.mode_set(mode='EDIT')
            except RuntimeError as ex:
                self.report({'ERROR'}, 'Cannot enter Mesh Edit Mode: ' + str(ex))
                return {'CANCELLED'}

        try:
            with context.temp_override(window=context.window, area=view_area, region=window_region):
                result = bpy.ops.mesh.knife_tool('INVOKE_REGION_WIN',
                                                 only_selected=False,
                                                 use_occlude_geometry=True)
        except (RuntimeError, TypeError, ValueError) as ex:
            self.report({'ERROR'}, 'Could not start Knife tool: ' + str(ex))
            return {'CANCELLED'}

        if 'CANCELLED' in result:
            self.report({'WARNING'}, 'Knife tool was not started')
            return {'CANCELLED'}
        return {'FINISHED'}

    def execute(self, context):
        return self.invoke(context, None)


# -----------------------------------------------------------------------------
# Screen click -> editable Bezier curves
# -----------------------------------------------------------------------------


def _path_ray(region, rv3d, xy):
    return (view3d_utils.region_2d_to_origin_3d(region, rv3d, xy),
            view3d_utils.region_2d_to_vector_3d(region, rv3d, xy))


def _path_to_screen(region, rv3d, co):
    p = view3d_utils.location_3d_to_region_2d(region, rv3d, co)
    return None if p is None else (p.x, p.y)


PATH_HIT_PX = 10.0


def set_point_type(bp, kind):
    """kind: 'VECTOR' (sharp corner) or 'AUTO' (smooth curve through the point)."""
    bp.handle_left_type = kind
    bp.handle_right_type = kind


class PathDrawLogic:
    """Mesh Curve drawing (Panel line / swept Curve / Curve Array path).

    Polyline: each click adds a point with the current point type
    (Straight = VECTOR, Smooth = AUTO; S toggles).  Clicking or double-clicking
    an existing point toggles it Straight <-> Smooth while drawing.  Free Draw:
    hold LMB, sampled points get AUTO handles so the result is a smooth curve.
    """

    def invoke(self, context, event):
        # Sidebar invocations start in the UI region, not the 3D View WINDOW region.
        # Use absolute window mouse coordinates so the path is drawn in the actual viewport.
        self._window_region = next((r for r in context.area.regions if r.type == 'WINDOW'), None)
        self._rv3d = context.space_data.region_3d if context.space_data else None
        if not self._window_region or not self._rv3d:
            self.report({'ERROR'}, '3D viewport region unavailable')
            return {'CANCELLED'}
        self._target = context.active_object if context.active_object and context.active_object.type == 'MESH' else None
        self._source = context.scene.mch_settings.array_source or self._target
        if self.kind == 'PANEL' and self._target is None:
            self.report({'WARNING'}, 'Select the target mesh before drawing a panel line')
            return {'CANCELLED'}
        if self.kind == 'ARRAY' and (self._source is None or self._source.type != 'MESH'):
            self.report({'WARNING'}, 'Choose the Array Source mesh in Mecha Lab')
            return {'CANCELLED'}

        data = bpy.data.curves.new('MCH_Path', type='CURVE')
        data.dimensions = '3D'
        data.resolution_u = 24
        data.twist_smooth = 2
        data.splines.new('BEZIER')
        self._path = bpy.data.objects.new('MCH_Path_' + self.kind, data)
        context.collection.objects.link(self._path)
        self._path.show_in_front = True
        self._path.display_type = 'WIRE'
        self._path['mch_path'] = True
        self._points = 0
        self._draw_down = False
        self._last_mouse_xy = None
        self._mode = context.scene.mch_settings.path_draw_mode
        self._ptype = context.scene.mch_settings.path_point_type
        self._header(context)
        try:
            context.window.cursor_modal_set('CROSSHAIR')
        except AttributeError:
            pass
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        try:
            context.area.header_text_set(
                'MESH CURVE | ' + ('Free: hold LMB' if self._mode == 'FREE' else 'Poly: click points (Shift 45°)') +
                f' | New points: {"Smooth" if self._ptype == "AUTO" else "Straight"} (S) | '
                'Click/double-click a point: Straight <-> Smooth | Enter/RMB: finish | Esc: cancel')
        except (AttributeError, ReferenceError):
            pass

    def _region_xy(self, event):
        region = self._window_region
        if not (region.x <= event.mouse_x < region.x + region.width and
                region.y <= event.mouse_y < region.y + region.height):
            return None
        return (event.mouse_x - region.x, event.mouse_y - region.y)

    def _hit(self, context, event):
        point = self._region_xy(event)
        if point is None:
            return None
        ro, rd = _path_ray(self._window_region, self._rv3d, point)
        if self.kind == 'PANEL' and self._target:
            inverse = self._target.matrix_world.inverted_safe()
            origin_local = inverse @ ro
            direction_local = (inverse.to_3x3() @ rd).normalized()
            hit, pos, normal, face = self._target.ray_cast(origin_local, direction_local)
            if not hit:
                return None
            return self._target.matrix_world @ pos
        plane_normal = self._rv3d.view_rotation @ Vector((0, 0, 1))
        return intersect_line_plane(ro, ro + rd * 100000, context.scene.cursor.location, plane_normal, False)

    def _bpoints(self):
        return self._path.data.splines[0].bezier_points

    def _add(self, co, kind=None):
        spline = self._path.data.splines[0]
        if self._points:
            spline.bezier_points.add(1)
        bp = spline.bezier_points[self._points]
        bp.co = co
        set_point_type(bp, kind or self._ptype)
        bp.radius = 1.0
        self._points += 1
        self._path.data.update_tag()

    def _point_near(self, xy):
        if xy is None:
            return None
        best, idx = PATH_HIT_PX, None
        mw = self._path.matrix_world
        for i, bp in enumerate(list(self._bpoints())[:self._points]):
            p = _path_to_screen(self._window_region, self._rv3d, mw @ bp.co)
            if p is None:
                continue
            d = ((p[0] - xy[0]) ** 2 + (p[1] - xy[1]) ** 2) ** 0.5
            if d <= best:
                best, idx = d, i
        return idx

    def toggle_point(self, index):
        bp = self._bpoints()[index]
        set_point_type(bp, 'VECTOR' if bp.handle_left_type == 'AUTO' else 'AUTO')
        self._path.data.update_tag()

    def _toggle_once(self, context, index):
        """B05: one physical double-click on a point = ONE toggle.  Its first
        press already toggled; the DOUBLE_CLICK (or a second PRESS on systems
        that send no DOUBLE_CLICK) used to toggle it straight back."""
        from . import cut_engine
        now = cut_engine._now()
        last = getattr(self, '_last_toggle', None)
        if last is not None and last[0] == index and now - last[1] <= cut_engine._double_click_seconds(context):
            self._last_toggle = None
            return False
        self.toggle_point(index)
        self._last_toggle = (index, now)
        return True

    def _snapped_path_pos(self, co):
        """Snap a clicked point to the nearest 45-degree viewport direction."""
        if self._points == 0:
            return co
        from math import atan2, pi, cos, sin, hypot
        last = self._bpoints()[self._points - 1].co
        orient = self._rv3d.view_rotation
        right = orient @ Vector((1, 0, 0))
        up = orient @ Vector((0, 1, 0))
        delta = co - last
        a, b = delta.dot(right), delta.dot(up)
        angle = round(atan2(b, a) / (pi / 4)) * (pi / 4)
        radius = hypot(a, b)
        guess = last + right * (cos(angle) * radius) + up * (sin(angle) * radius)
        if self.kind == 'PANEL' and self._target is not None:
            inv = self._target.matrix_world.inverted_safe()
            ok, loc, _normal, _face = self._target.closest_point_on_mesh(inv @ guess)
            if ok:
                return self._target.matrix_world @ loc
        return guess

    def _click_point(self, context, event, kind=None):
        co = self._hit(context, event)
        if co is None:
            return False
        if event.shift and self._mode == 'POLY':
            co = self._snapped_path_pos(co)
        self._add(co, kind)
        self._last_mouse_xy = (event.mouse_x, event.mouse_y)
        return True

    def _cleanup(self, context):
        try:
            context.window.cursor_modal_restore()
        except AttributeError:
            pass
        if context.area:
            context.area.header_text_set(None)

    def _remove_last(self):
        curve = self._path.data
        old = curve.splines[0]
        pts = [(bp.co.copy(), bp.radius, bp.handle_left_type) for bp in old.bezier_points][:self._points - 1]
        curve.splines.remove(old)  # BezierSplinePoints has add() but no remove().
        new = curve.splines.new('BEZIER')
        if len(pts) > 1:
            new.bezier_points.add(len(pts) - 1)
        for bp, (co, radius, kind) in zip(new.bezier_points, pts):
            bp.co = co
            bp.radius = radius
            set_point_type(bp, kind if kind in {'AUTO', 'VECTOR'} else 'VECTOR')
        self._points = len(pts)
        curve.update_tag()

    def modal(self, context, event):
        if event.type in {'ESC'} and event.value == 'PRESS':
            self._cleanup(context)
            remove_object(self._path)
            return {'CANCELLED'}
        if event.type in {'RET', 'NUMPAD_ENTER', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._cleanup(context)
            if self._points < 2:
                remove_object(self._path)
                self.report({'WARNING'}, 'Need at least 2 points')
                return {'CANCELLED'}
            try:
                make_live(context, self._path, self.kind, self._target, self._source)
            except Exception as ex:
                remove_object(self._path)
                self.report({'ERROR'}, 'Could not create live modifier: ' + str(ex))
                return {'CANCELLED'}
            self.report({'INFO'}, 'Live curve created. Sidebar: Resolution, Rotation, Twist, Smooth/Straight.')
            return {'FINISHED'}
        if event.type == 'S' and event.value == 'PRESS':
            self._ptype = 'VECTOR' if self._ptype == 'AUTO' else 'AUTO'
            self._header(context)
            return {'RUNNING_MODAL'}
        if event.type == 'BACK_SPACE' and event.value == 'PRESS' and self._points > 1:
            self._remove_last()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE':
            if event.value == 'DOUBLE_CLICK':
                # Double-click a point (usually the one just placed): make it smooth/straight.
                idx = self._point_near(self._region_xy(event))
                if idx is not None:
                    self._toggle_once(context, idx)
                self._draw_down = False
                return {'RUNNING_MODAL'}
            if event.value == 'PRESS':
                if self._mode == 'FREE':
                    self._draw_down = self._click_point(context, event, 'AUTO')
                else:
                    idx = self._point_near(self._region_xy(event))
                    if idx is not None:
                        self._toggle_once(context, idx)
                    elif not self._click_point(context, event) and self.kind == 'PANEL':
                        self.report({'WARNING'}, 'Click directly on the active target mesh')
            elif event.value == 'RELEASE':
                self._draw_down = False
            return {'RUNNING_MODAL'}
        if event.type == 'MOUSEMOVE' and self._mode == 'FREE' and self._draw_down:
            xy = (event.mouse_x, event.mouse_y)
            from math import dist
            if self._last_mouse_xy is None or dist(xy, self._last_mouse_xy) >= context.scene.mch_settings.path_sample_px:
                self._click_point(context, event, 'AUTO')
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


class MCH_OT_draw_path(PathDrawLogic, bpy.types.Operator):
    bl_idname = 'mch.draw_path'
    bl_label = 'Draw Editable Mecha Path'
    bl_description = 'Click to place points (click a point = smooth/straight); Enter/right click to finish; Esc to cancel'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    kind: EnumProperty(items=[('PANEL', 'Panel line', ''), ('CURVE', 'Solid swept profile', ''), ('ARRAY', 'Curve array', '')])

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.area and context.area.type == 'VIEW_3D'


class MCH_OT_path_handles_all(bpy.types.Operator):
    bl_idname = 'mch.path_handles_all'
    bl_label = 'All Points Smooth / Straight'
    bl_description = 'Set every point of the active Mesh Curve path to Smooth (AUTO) or Straight (VECTOR), in Object Mode'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=[('AUTO', 'Smooth', ''), ('VECTOR', 'Straight', '')], default='AUTO')

    @staticmethod
    def _path(context):
        ob = context.active_object
        if ob is None:
            return None
        if ob.type == 'CURVE' and ob.get('mch_path'):
            return ob
        live = getattr(ob, 'mch_live', None)
        if live is not None and live.path is not None and live.path.type == 'CURVE':
            return live.path
        return None

    @classmethod
    def poll(cls, context):
        return cls._path(context) is not None

    def execute(self, context):
        path = self._path(context)
        count = 0
        for sp in path.data.splines:
            for bp in sp.bezier_points:
                set_point_type(bp, self.kind)
                count += 1
        path.data.update_tag()
        self.report({'INFO'}, f'{count} points set to {"Smooth" if self.kind == "AUTO" else "Straight"}')
        return {'FINISHED'}


class MCH_OT_edit_handles(bpy.types.Operator):
    bl_idname = 'mch.edit_handles'
    bl_label = 'Straight / Curved Point'
    bl_description = 'Make selected Bezier control points straight or smoothly curved'
    bl_options = {'REGISTER', 'UNDO'}
    shape: EnumProperty(items=[('VECTOR', 'Straight', ''), ('AUTOMATIC', 'Smooth', '')], default='AUTOMATIC')

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE' and context.active_object is not None

    def execute(self, context):
        bpy.ops.curve.handle_type_set(type=self.shape)
        return {'FINISHED'}


class MCH_OT_double_click(bpy.types.Operator):
    bl_idname = 'mch.double_click_point'
    bl_label = 'Toggle Smooth Point on Double Click'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE' and context.active_object is not None

    def invoke(self, context, event):
        ob = context.active_object
        if not ob.get('mch_path') or not context.region_data:
            return {'PASS_THROUGH'}
        nearest = None
        best = 18 * 18
        mouse = Vector((event.mouse_region_x, event.mouse_region_y))
        for spline in ob.data.splines:
            if spline.type != 'BEZIER':
                continue
            for point in spline.bezier_points:
                on_screen = view3d_utils.location_3d_to_region_2d(
                    context.region, context.region_data, ob.matrix_world @ point.co)
                if on_screen is None:
                    continue
                d2 = (on_screen - mouse).length_squared
                if d2 < best:
                    best, nearest = d2, point
        if nearest is None:
            return {'PASS_THROUGH'}
        target_type = 'VECTOR' if nearest.handle_left_type == 'AUTO' else 'AUTOMATIC'
        bpy.ops.curve.select_all(action='DESELECT')
        nearest.select_control_point = True
        nearest.select_left_handle = True
        nearest.select_right_handle = True
        try:
            bpy.ops.curve.handle_type_set(type=target_type)
        except RuntimeError:
            nearest.handle_left_type = 'VECTOR' if target_type == 'VECTOR' else 'AUTO'
            nearest.handle_right_type = nearest.handle_left_type
        return {'FINISHED'}


class MCH_OT_point_radius(bpy.types.Operator):
    bl_idname = 'mch.point_radius'
    bl_label = 'Set Selected Point Size'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_CURVE'

    def execute(self, context):
        bpy.ops.curve.radius_set(radius=context.scene.mch_settings.point_radius)
        return {'FINISHED'}


class MCH_OT_bake_live(bpy.types.Operator):
    bl_idname = 'mch.bake_live'
    bl_label = 'Confirm / Apply Live Result'
    bl_description = 'Bake procedural result into mesh, optionally remove editable path'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return context.mode == 'OBJECT' and ob is not None and (ob.get('mch_path') or ob.get('mch_role'))

    def execute(self, context):
        ob = context.active_object
        if ob.get('mch_path'):
            ob = bpy.data.objects.get(ob.get('mch_carrier', ''))
        if not ob:
            self.report({'ERROR'}, 'Generated mesh not found')
            return {'CANCELLED'}
        role = ob.get('mch_role')
        path = ob.mch_live.path
        if role == 'PANEL':
            target = ob.mch_live.target
            if not target:
                self.report({'WARNING'}, 'Target mesh missing')
                return {'CANCELLED'}
            mod = target.modifiers.get(ob.get('mch_boolean', ''))
            if not mod:
                self.report({'WARNING'}, 'Panel boolean modifier missing')
                return {'CANCELLED'}
            try:
                safe_apply(context, target, mod)
            except RuntimeError as ex:
                self.report({'ERROR'}, str(ex))
                return {'CANCELLED'}
            remove_object(ob)
            if path:
                if context.scene.mch_settings.delete_path_on_bake:
                    remove_object(path)
                else:
                    path.hide_set(True)
            activate_only(context, target)
        else:
            mod = find_gn(ob)
            array_bake_switch = None
            if mod and role == 'ARRAY' and mod.node_group:
                array_bake_switch = mod.node_group.nodes.get('MCH_ARRAY_BAKE_SWITCH')
                if array_bake_switch:
                    array_bake_switch.inputs['Switch'].default_value = True
            if mod:
                try:
                    safe_apply(context, ob, mod)
                except Exception as ex:
                    if array_bake_switch:
                        array_bake_switch.inputs['Switch'].default_value = False
                    self.report({'ERROR'}, str(ex))
                    return {'CANCELLED'}
            if path:
                if context.scene.mch_settings.delete_path_on_bake:
                    remove_object(path)
                else:
                    path.hide_set(True)
            ob.mch_live.path = None
            ob['mch_role'] = 'BAKED'
            activate_only(context, ob)
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Library and sculpt / remesh
# -----------------------------------------------------------------------------


class MCH_OT_save_asset(bpy.types.Operator):
    bl_idname = 'mch.save_asset'
    bl_label = 'Save Selected to Library'
    bl_options = {'REGISTER'}
    kind: EnumProperty(items=[('MESH', 'Mesh part', ''), ('PROFILE', '2D curve profile', '')], default='MESH')

    def execute(self, context):
        ob = context.active_object
        expected = 'MESH' if self.kind == 'MESH' else 'CURVE'
        if not ob or ob.type != expected:
            self.report({'WARNING'}, 'Select a ' + expected + ' object to save')
            return {'CANCELLED'}
        s = context.scene.mch_settings
        path = folder(s) / (self.kind + '__' + unique_asset_name(s.asset_name) + '.blend')
        try:
            if self.kind == 'MESH':
                deps = context.evaluated_depsgraph_get()
                mesh = bpy.data.meshes.new_from_object(ob.evaluated_get(deps), preserve_all_data_layers=True, depsgraph=deps)
                library_write(path, ob, mesh)
            else:
                curve = ob.data.copy()
                curve.bevel_depth = 0
                curve.extrude = 0
                library_write(path, ob, curve)
        except Exception as ex:
            self.report({'ERROR'}, 'Save failed: ' + str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, 'Saved reusable preset: ' + str(path))
        return {'FINISHED'}


class MCH_OT_insert_asset(bpy.types.Operator):
    bl_idname = 'mch.insert_asset'
    bl_label = 'Insert Saved Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        s = context.scene.mch_settings
        if s.mesh_preset == 'NONE':
            self.report({'WARNING'}, 'Choose a saved mesh preset')
            return {'CANCELLED'}
        try:
            ob = library_load(folder(s) / s.mesh_preset, context.collection)
        except Exception as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'}
        if ob.type != 'MESH':
            remove_object(ob)
            self.report({'ERROR'}, 'Selected library item is not a mesh')
            return {'CANCELLED'}
        ob.name = 'MCH Part | ' + Path(s.mesh_preset).stem.split('__', 1)[-1]
        ob.location = context.scene.cursor.location
        ob.hide_set(False)
        activate_only(context, ob)
        return {'FINISHED'}


class MCH_OT_sculpt_move(bpy.types.Operator):
    bl_idname = 'mch.sculpt_move'
    bl_label = 'Sculpt Move Brush'
    bl_description = 'Switch to sculpt mode and select Blender built-in Move brush'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        bpy.ops.object.mode_set(mode='SCULPT')
        try:
            bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS',
                relative_asset_identifier='brushes/essentials_brushes-mesh_sculpt.blend/Brush/Grab')   # 0.24.21 (no 'Move' brush in 5.0)
        except Exception:
            self.report({'WARNING'}, 'Entered Sculpt Mode; select the Grab brush manually for this Blender version')
        return {'FINISHED'}


class MCH_OT_remesh(bpy.types.Operator):
    bl_idname = 'mch.one_click_remesh'
    bl_label = 'Join + Voxel Remesh + Smooth'
    bl_description = 'Join chosen solids, voxel remesh, smooth and optionally apply resulting modifiers'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.active_object and context.active_object.type == 'MESH'

    def execute(self, context):
        s = context.scene.mch_settings
        ob = context.active_object
        meshes = [obj for obj in context.selected_objects if obj.type == 'MESH']
        # Joining loses the modifier stacks of non-active objects. Never let
        # a destructive Join silently discard those effects.
        if (s.join_remesh and len(meshes) > 1 and not s.apply_existing
                and any(obj.modifiers for obj in meshes if obj != ob)):
            self.report({'ERROR'},
                        'Other selected meshes have modifiers. Enable Apply Existing Modifiers before Join, or remesh separately.')
            return {'CANCELLED'}
        if s.apply_remesh and s.apply_existing:
            # Baking modifier stacks BEFORE joining is essential: Blender's Join
            # can otherwise silently omit non-active objects' modifiers.
            try:
                for item in meshes:
                    for mod in list(item.modifiers):
                        safe_apply(context, item, mod)
            except RuntimeError as ex:
                self.report({'ERROR'}, 'Existing modifier could not be applied: ' + str(ex))
                return {'CANCELLED'}
            for item in meshes:
                item.select_set(True)
            context.view_layer.objects.active = ob
        if s.join_remesh and len(meshes) > 1:
            if not s.apply_remesh:
                # The non-applied branch intentionally leaves modifiers editable;
                # do not silently lose the modifiers of other joined objects.
                self.report({'WARNING'}, 'For multi-object remesh, enable Apply remesh + smooth')
                return {'CANCELLED'}
            try:
                bpy.ops.object.join()
            except RuntimeError as ex:
                self.report({'ERROR'}, 'Join failed: ' + str(ex))
                return {'CANCELLED'}
            ob = context.active_object
        # REMESH followed by Smooth; optionally apply immediately.
        remesh = ob.modifiers.new('MCH_VoxelRemesh', 'REMESH')
        remesh.mode = 'VOXEL'
        remesh.voxel_size = s.voxel_size
        remesh.use_smooth_shade = True
        smooth = None
        if s.smooth_iterations > 0:
            smooth = ob.modifiers.new('MCH_SmoothTransition', 'SMOOTH')
            smooth.factor = s.smooth_factor
            smooth.iterations = s.smooth_iterations
        if s.apply_remesh:
            try:
                safe_apply(context, ob, remesh)
                if smooth:
                    safe_apply(context, ob, smooth)
            except RuntimeError as ex:
                self.report({'ERROR'}, 'Remesh failed: ' + str(ex))
                return {'CANCELLED'}
        self.report({'INFO'}, 'Voxel remesh complete — high-poly topology, not quad retopology')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# N-panel
# -----------------------------------------------------------------------------


class MCH_OT_select_tool(bpy.types.Operator):
    """v0.5.9 compatibility alias of mch.set_tool."""
    bl_idname = 'mch.select_tool'
    bl_label = 'Select Mecha Lab Tool'
    bl_options = {'INTERNAL'}
    tool: EnumProperty(items=TOOL_ITEMS, default='CUT')

    def execute(self, context):
        workspace_ui.activate_mecha_tool(context, self.tool)
        return {'FINISHED'}


class MCH_MT_tool_menu(bpy.types.Menu):
    """v0.5.9 compatibility: text menu (the large-icon popup is MCH_PT_tool_popup)."""
    bl_idname = 'MCH_MT_tool_menu'
    bl_label = 'MECHA LAB  |  Select Tool'

    def draw(self, context):
        layout = self.layout
        layout.scale_y = 1.4
        for tool, name, desc, icon, idx in TOOL_ITEMS:
            layout.operator('mch.set_tool', text=name, icon=icon).tool = tool


CLASSES = (
    MCH_PG_Live, MCH_PG_Settings, MCH_PG_Fuse,
    MCH_OT_fuse_create, MCH_OT_fuse_source, MCH_OT_fuse_confirm, MCH_OT_fuse_cancel,
    MCH_OT_boolean, MCH_OT_slice, MCH_OT_surface_cut, MCH_OT_draw_path, MCH_OT_path_handles_all,
    MCH_OT_edit_handles, MCH_OT_double_click, MCH_OT_point_radius,
    MCH_OT_bake_live, MCH_OT_save_asset, MCH_OT_insert_asset,
    MCH_OT_sculpt_move, MCH_OT_remesh,
    MCH_OT_select_tool, MCH_MT_tool_menu, *mask_tools.CLASSES,
    *radial_array.CLASSES[:-1],
    *cut_tools.CLASSES,
    *cut_engine.CLASSES,
    *surface_conform.CLASSES[:-1],
    *mirror_tools.CLASSES[:-1],
)

# Sub-panels of workspace_ui.MCH_PT_main; registered after it.
SUB_PANELS = (
    mirror_tools.MCH_PT_mirror,
    radial_array.MCH_PT_radial,
    surface_conform.MCH_PT_surface_conform,
)


def _register():
    tool_state.register()
    for klass in CLASSES:
        bpy.utils.register_class(klass)
    bpy.types.Scene.mch_settings = PointerProperty(type=MCH_PG_Settings)
    cut_presets.register()
    bpy.types.Scene.mch_mirror = PointerProperty(type=mirror_tools.MCH_PG_Mirror)
    bpy.types.Scene.mch_conform = PointerProperty(type=surface_conform.MCH_PG_Conform)
    bpy.types.Object.mch_live = PointerProperty(type=MCH_PG_Live)
    bpy.types.Object.mch_radial = PointerProperty(type=radial_array.MCH_PG_Radial)
    bpy.types.Object.mch_fuse = PointerProperty(type=MCH_PG_Fuse)
    bpy.types.Scene.mch_fuse_preview_target = PointerProperty(type=bpy.types.Object)
    base_mesh.register()
    loft_surface.register()
    zbrush_bridge.register()
    subd_plane.register()
    deform_tools.register()
    primitive_tools.register()
    self_test.register()
    face_extract.register()
    edge_molding.register()
    hollow_shell.register()
    along_curve.register()
    cable.register()
    station_primitive.register()
    station_gizmos.register()
    primitive_place.register()
    primitive_hud.register()
    armor_plate.register()
    creature_plate.register()
    mech_ridge.register()
    cape_gen.register()
    creature_hair.register()
    clothing_gen.register()
    hood_gen.register()
    scarf_gen.register()
    quad_cloth.register()
    belt_maker.register()
    creature_spike.register()
    creature_scales.register()
    scale_brush.register()
    bridge_patch.register()
    flower_plate.register()
    surface_curve.register()
    random_panels.register()
    mirror_hud.register()
    highpoly.register()
    lasso_sketch.register()
    cloth_wrinkle.register()
    last_used.register()
    robot_base.register()
    detail_stamp.register()
    surface_lasso.register()
    curve_tube.register()
    creature_shell.register()
    cloth_sim.register()
    box_hide.register()
    plate_detail.register()
    screw_stamp.register()
    lowpoly.register()
    fold_patch.register()
    workspace_ui.register()
    bottom_bar.register()
    for klass in SUB_PANELS:
        bpy.utils.register_class(klass)


def _reset_module_state():
    """Module-level bookkeeping must match the (now clean) Blender state."""
    workspace_ui._tools_registered = False
    workspace_ui._keymaps.clear()
    try:
        workspace_ui._free_icons()   # a crashed unregister may have left it open
    except (KeyError, RuntimeError, AttributeError):
        workspace_ui._icons = None
    primitive_tools._KM.clear()
    bottom_bar._label_handle = None


def register():
    # B09: never fail with "already registered" because of leftovers from a
    # crashed unregister / reload / a second enabled copy of the add-on.
    addon_safety.purge_stale(__name__)
    _reset_module_state()
    try:
        _register()
    except Exception:
        # Roll back completely so a retry (or a disable/enable) starts clean
        # instead of leaving half the add-on registered.
        import traceback
        traceback.print_exc()
        addon_safety.run_steps(_unregister_steps())
        addon_safety.purge_stale(__name__)
        _reset_module_state()
        raise


def _del_prop(owner, name):
    if hasattr(owner, name):
        delattr(owner, name)


def _unregister_classes(classes):
    for klass in classes:
        if addon_safety.is_registered(klass):
            try:
                bpy.utils.unregister_class(klass)
            except RuntimeError:
                pass


def _unregister_steps():
    return [
        ('sub panels', lambda: _unregister_classes(reversed(SUB_PANELS))),
        ('bottom_bar', bottom_bar.unregister),
        ('workspace_ui', workspace_ui.unregister),
        ('fold_patch', fold_patch.unregister),
        ('lowpoly', lowpoly.unregister),
        ('screw_stamp', screw_stamp.unregister),
        ('plate_detail', plate_detail.unregister),
        ('box_hide', box_hide.unregister),
        ('cloth_sim', cloth_sim.unregister),
        ('creature_shell', creature_shell.unregister),
        ('curve_tube', curve_tube.unregister),
        ('surface_lasso', surface_lasso.unregister),
        ('detail_stamp', detail_stamp.unregister),
        ('robot_base', robot_base.unregister),
        ('last_used', last_used.unregister),
        ('cloth_wrinkle', cloth_wrinkle.unregister),
        ('lasso_sketch', lasso_sketch.unregister),
        ('highpoly', highpoly.unregister),
        ('mirror_hud', mirror_hud.unregister),
        ('random_panels', random_panels.unregister),
        ('surface_curve', surface_curve.unregister),
        ('flower_plate', flower_plate.unregister),
        ('bridge_patch', bridge_patch.unregister),
        ('scale_brush', scale_brush.unregister),
        ('creature_scales', creature_scales.unregister),
        ('creature_spike', creature_spike.unregister),
        ('belt_maker', belt_maker.unregister),
        ('creature_plate', creature_plate.unregister),
        ('mech_ridge', mech_ridge.unregister),
        ('cape_gen', cape_gen.unregister),
        ('creature_hair', creature_hair.unregister),
        ('quad_cloth', quad_cloth.unregister),
        ('scarf_gen', scarf_gen.unregister),
        ('hood_gen', hood_gen.unregister),
        ('clothing_gen', clothing_gen.unregister),
        ('armor_plate', armor_plate.unregister),
        ('primitive_hud', primitive_hud.unregister),
        ('primitive_place', primitive_place.unregister),
        ('station_gizmos', station_gizmos.unregister),
        ('station_primitive', station_primitive.unregister),
        ('cable', cable.unregister),
        ('along_curve', along_curve.unregister),
        ('hollow_shell', hollow_shell.unregister),
        ('edge_molding', edge_molding.unregister),
        ('face_extract', face_extract.unregister),
        ('self_test', self_test.unregister),
        ('primitive_tools', primitive_tools.unregister),
        ('deform_tools', deform_tools.unregister),
        ('subd_plane', subd_plane.unregister),
        ('zbrush_bridge', zbrush_bridge.unregister),
        ('loft_surface', loft_surface.unregister),
        ('base_mesh', base_mesh.unregister),
        ('cut_presets', cut_presets.unregister),
        ('properties', lambda: [_del_prop(o, n) for o, n in (
            (bpy.types.Scene, 'mch_fuse_preview_target'), (bpy.types.Object, 'mch_fuse'),
            (bpy.types.Object, 'mch_live'), (bpy.types.Object, 'mch_radial'),
            (bpy.types.Scene, 'mch_conform'), (bpy.types.Scene, 'mch_mirror'),
            (bpy.types.Scene, 'mch_settings'))]),
        ('classes', lambda: _unregister_classes(reversed(CLASSES))),
        ('tool_state', tool_state.unregister),
    ]


def unregister():
    addon_safety.run_steps(_unregister_steps())
    # Anything a failing step left behind is removed here, so the next
    # enable never sees "already registered".
    addon_safety.purge_stale(__name__, only_own=True)
    _reset_module_state()


if __name__ == '__main__':
    register()
