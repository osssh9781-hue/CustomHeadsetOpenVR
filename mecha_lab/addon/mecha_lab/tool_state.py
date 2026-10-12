"""Shared Mecha Lab state: tool registry, shape (brush) settings, cut settings.

Separation (docs/01 "data design"):
* Tool ID ............ ``Scene.mch_settings.mch_active_tool`` (+ the native
                       WorkSpaceTool for drawing tools, which wins when active)
* Shape/brush ........ ``Scene.mch_brush`` (shared by Cut / Split / Mask)
* Per-tool options ... ``Scene.mch_cut`` and the v0.5.9 ``Scene.mch_settings``
* Machine-wide ....... add-on preferences (hotkeys) and the PNG shape library
                       in the user config folder (see cut_presets).
"""
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

WORKSPACE_NAME = 'MECHA LAB'
WORKSPACE_TAG = 'mch_workspace'

# (id, label, description, png icon stem, fallback icon, native tool idname, status)
# status: 'OK' working, 'PARTIAL' limited, 'TODO' not implemented (shown honestly).
TOOLS = (
    ('CUT', 'Cut', 'Draw a shape to remove the inside (Alt: keep inside)', 'cut', 'MOD_BOOLEAN', 'mecha.cut', 'OK'),
    ('SPLIT', 'Split', 'Draw a shape to split the mesh into two solid parts', 'split', 'MOD_EDGESPLIT', 'mecha.split', 'OK'),
    ('BASE', 'Base Mesh', 'Draw an outline to create a NEW solid (Flat / Chamfer / Bevel / Dome); RMB = profiles',
     'base', 'MESH_CUBE', 'mecha.base_mesh', 'OK'),
    ('SUBD', 'SubD Plane', 'Plane with live Simple + Catmull-Clark subdivision and Solidify; extrude edges '
     'in Edit Mode to build armour panels', 'subd', 'MOD_SUBSURF', None, 'OK'),
    ('BOOLEAN', 'Boolean', 'Difference / Union / Intersect with a selected cutter mesh', 'boolean', 'MOD_BOOLEAN', None, 'OK'),
    ('FUSE', 'Smart Fuse', 'Union two overlapping meshes with a fillet/chamfer seam', 'fuse', 'MOD_BEVEL', None, 'PARTIAL'),
    ('MIRROR', 'Mirror', 'World / local / collection mirror', 'mirror', 'MOD_MIRROR', None, 'OK'),
    ('MASK', 'Mask', 'Paint a face mask with the shared shapes (Alt: erase)', 'mask', 'MOD_MASK', 'mecha.mask', 'PARTIAL'),
    ('ARRAY', 'Curve Array', 'Repeat a part along a drawn curve', 'array', 'MOD_ARRAY', None, 'OK'),
    ('RADIAL', 'Radial Array', 'Radial copies around the 3D cursor + Boolean', 'radial', 'MOD_SCREW', None, 'OK'),
    ('DRAW', 'Mesh Curve', 'Draw a curve and sweep a profile along it (or a panel-line cut); '
     'smooth/straight points, resolution, rotation, twist', 'panel', 'CURVE_BEZCURVE', None, 'OK'),
    ('POSE', 'Pose', 'Rigid / soft pose (not implemented yet)', 'pose', 'ARMATURE_DATA', None, 'TODO'),
    ('LOFT', 'Loft / Surface', 'Smooth surface through 2+ curves, or sweep a profile along a path (live)',
     'loft', 'SURFACE_DATA', None, 'PARTIAL'),
    ('ZBRUSH', 'ZBrush Bridge', 'Send selected objects to ZBrush as OBJ files and import them back (not GoZ)',
     'zbrush', 'EXPORT', None, 'PARTIAL'),
    ('SURFACE', 'Surface Conform', 'Snap / wrap a part onto a surface', 'surface', 'MOD_SHRINKWRAP', None, 'OK'),
    ('LIBRARY', 'Assets', 'Save / insert reusable mesh parts and profiles', 'assets', 'ASSET_MANAGER', None, 'OK'),
    ('REMESH', 'Remesh', 'Voxel remesh + smooth, sculpt Move', 'remesh', 'MOD_REMESH', None, 'OK'),
    ('EDIT', 'Live Result', 'Confirm live curves / arrays / cuts', 'live', 'CHECKMARK', None, 'OK'),
)
TOOL_BY_ID = {t[0]: t for t in TOOLS}
NATIVE_TO_TOOL = {t[5]: t[0] for t in TOOLS if t[5]}
SHAPE_TOOLS = {'CUT', 'SPLIT', 'MASK', 'BASE'}

# Enum numbers keep v0.5.9 values so saved .blend files map to the same tool.
_ENUM_NUMBERS = {'CUT': 1, 'BOOLEAN': 2, 'FUSE': 3, 'MIRROR': 4, 'MASK': 5, 'DRAW': 6,
                 'ARRAY': 7, 'RADIAL': 8, 'SURFACE': 9, 'LIBRARY': 10, 'EDIT': 11,
                 'REMESH': 12, 'SPLIT': 13, 'POSE': 14, 'BASE': 15, 'LOFT': 16, 'ZBRUSH': 17, 'SUBD': 18}
TOOL_ENUM_ITEMS = [(t[0], t[1], t[2], t[4], _ENUM_NUMBERS[t[0]]) for t in TOOLS]

SHAPES = (
    ('LASSO', 'Lasso', 'Straight-segment outline: click points (hold LMB to draw freely). '
     'Double-click anywhere closes and applies. 2 points = straight line cut', 'lasso', 'GP_SELECT_POINTS'),
    ('CURVE_LASSO', 'Curve Lasso', 'Smooth closed spline through control points from the start. '
     'Click a point: sharp/smooth, drag points or Bezier handles. Double-click anywhere closes',
     'curve_lasso', 'CURVE_BEZCURVE'),
    ('RECT', 'Rectangle', 'Drag a rectangle (Shift square, Ctrl from center)', 'rect', 'MESH_PLANE'),
    ('CIRCLE', 'Circle', 'Drag from center to radius', 'circle', 'MESH_CIRCLE'),
    ('ELLIPSE', 'Ellipse', 'Drag an ellipse box (Shift circle, Ctrl from center)', 'ellipse', 'MESH_UVSPHERE'),
    ('STROKE', 'Free Draw', 'Hold LMB and draw continuously; release applies. Cut/Split/Base Mesh: closed '
     'freehand outline. Mask: open brush stroke', 'stroke', 'GREASEPENCIL'),
    ('CUSTOM', 'Custom', 'Imported PNG vector shape: click = stamp, drag = size', 'custom', 'IMAGE_DATA'),
)
SHAPE_BY_ID = {s[0]: s for s in SHAPES}
SHAPE_ENUM_ITEMS = [(s[0], s[1], s[2], s[4], i) for i, s in enumerate(SHAPES)]


def is_mecha_workspace(workspace):
    if workspace is None:
        return False
    try:
        return bool(workspace.get(WORKSPACE_TAG)) or workspace.name.startswith(WORKSPACE_NAME)
    except ReferenceError:
        return False


def find_mecha_workspace():
    for ws in bpy.data.workspaces:
        if ws.get(WORKSPACE_TAG):
            return ws
    for ws in bpy.data.workspaces:
        if ws.name.startswith(WORKSPACE_NAME):
            return ws
    return None


def native_tool_id(context):
    try:
        tool = context.workspace.tools.from_space_view3d_mode('OBJECT', create=False)
    except (AttributeError, TypeError, RuntimeError):
        return ''
    return tool.idname if tool else ''


def effective_tool(context):
    """Native drawing tool wins (it is what LMB does); else the selected tool."""
    native = NATIVE_TO_TOOL.get(native_tool_id(context))
    if native:
        return native
    settings = getattr(getattr(context, 'scene', None), 'mch_settings', None)
    return settings.mch_active_tool if settings else 'CUT'


def tool_is(context, tool_id):
    return bool(getattr(context, 'scene', None) and hasattr(context.scene, 'mch_settings')
                and effective_tool(context) == tool_id)


class MCH_PG_Brush(bpy.types.PropertyGroup):
    shape: EnumProperty(name='Shape', items=SHAPE_ENUM_ITEMS, default='LASSO')
    circle_segments: IntProperty(name='Circle Segments', default=64, min=8, max=512,
                                 description='Real geometric resolution of circles/ellipses (not shading)')
    curve_resolution: IntProperty(name='Curve Samples', default=12, min=2, max=64,
                                  description='Samples per Curve Lasso span (between two control points)')
    curve_smoothness: FloatProperty(name='Curve Smoothness', default=1.0, min=0.0, max=2.0,
                                    description='Tangent length of automatic (Catmull-Rom) control points')
    outline_corner: EnumProperty(name='Outline Corners', items=[
        ('NONE', 'Sharp', 'Keep drawn corners'),
        ('ROUND', 'Round', 'Round the corners of the 2D outline (Lasso / Rectangle)'),
        ('CHAMFER', 'Chamfer', 'Straight-cut the corners of the 2D outline (Lasso / Rectangle)')],
        default='NONE', description='2D shape option, separate from the 3D Edge Finish of the cut')
    outline_radius: FloatProperty(name='Corner Width (px)', default=12.0, min=0.0, max=500.0)
    outline_segments: IntProperty(name='Corner Segments', default=6, min=1, max=32)
    stroke_smooth: IntProperty(name='Free Draw Smoothing', default=2, min=0, max=10,
                               description='Smoothing passes applied to the drawn freehand path')
    stroke_spacing: FloatProperty(name='Sample Spacing (px)', default=4.0, min=1.0, max=50.0,
                                  description='Free Draw: a new sample every N pixels of mouse movement')
    mask_brush_radius: FloatProperty(name='Mask Brush Radius (px)', default=18.0, min=1.0, max=200.0,
                                     description='Pixel radius for Brush Stroke in Mask mode')
    stroke_simplify: FloatProperty(name='Simplify (px)', default=1.0, min=0.0, max=10.0,
                                   description='Removes mouse jitter from Brush Stroke outlines')
    custom_size: FloatProperty(name='Stamp Radius (px)', default=120.0, min=4.0, max=4000.0,
                               description='Screen radius used when the Custom shape is clicked without dragging')
    custom_rotation: FloatProperty(name='Stamp Rotation', default=0.0, subtype='ANGLE')
    custom_drag_rotate: BoolProperty(name='Rotate With Drag', default=False,
                                     description='Dragging a Custom shape also rotates it')
    line_open: BoolProperty(name='Open Line (F)', default=False,
                            description='Lasso points form an open line across the mesh instead of a closed outline')


class MCH_PG_Cut(bpy.types.PropertyGroup):
    depth_mode: EnumProperty(name='Depth', items=[
        ('THROUGH', 'Through All', 'Cut through the whole object along the view'),
        ('SURFACE', 'From Surface', 'Pocket of fixed depth starting at the surface under the shape')],
        default='THROUGH')
    depth: FloatProperty(name='Cut Depth', default=0.1, min=0.00001, soft_max=10.0, precision=4,
                         unit='LENGTH')
    targets: EnumProperty(name='Targets', items=[
        ('ACTIVE', 'Active', 'Only the active mesh (or the mesh under the cursor)'),
        ('SELECTED', 'Selected', 'All selected meshes')], default='ACTIVE')
    solver: EnumProperty(name='Solver', items=[
        ('AUTO', 'Auto', 'Closed mesh: fast Manifold solver, Exact as fallback. Open mesh: Exact'),
        ('EXACT', 'Exact', 'Blender Exact solver only'),
        ('MANIFOLD', 'Manifold', 'Fast manifold solver (needs closed input)'),
        ('FAST', 'Float', 'Legacy fast solver (least robust)')], default='AUTO')
    hole_tolerant: BoolProperty(name='Hole Tolerant', default=False,
                                description='Exact solver option for meshes with holes/non-manifold parts (slower)')
    edge_finish: EnumProperty(name='Edge Finish', items=[
        ('NONE', 'Off', 'Keep the new cut edges sharp'),
        ('BEVEL', 'Bevel', 'Round only the NEW cut edges'),
        ('CHAMFER', 'Chamfer', 'Flat chamfer on the NEW cut edges only')], default='NONE')
    finish_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=0.5, precision=4,
                                unit='LENGTH')
    finish_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    finish_profile: FloatProperty(name='Profile', default=0.5, min=0.0, max=1.0)
    shared_mesh: EnumProperty(name='Shared Mesh', items=[
        ('SINGLE', 'This Object Only', 'Linked duplicates (Alt+D) keep the old mesh; this object gets its own copy'),
        ('ALL', 'All Linked Copies', 'Change the shared mesh data, so every linked duplicate is cut')],
        default='SINGLE')
    split_mode: EnumProperty(name='Split Mode', items=[
        ('NORMAL', 'Normal', 'Thin cut line: two parts touching along the cut'),
        ('GAP', 'Gap', 'Thick blade: removes a strip of Gap Width between the two parts')], default='NORMAL')
    gap_width: FloatProperty(name='Gap Width', default=0.02, min=0.0, soft_max=1.0, precision=4, unit='LENGTH',
                             description='Width of the removed strip in model units, centred on the drawn line')
    side_a_finish: EnumProperty(name='Side A', items=[
        ('NONE', 'None', 'Keep the cut edge sharp'), ('CHAMFER', 'Chamfer', 'Flat chamfer on the cut edge'),
        ('BEVEL', 'Bevel', 'Rounded bevel on the cut edge')], default='NONE',
        description='Side A = the remaining original object')
    side_a_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=0.5, precision=4, unit='LENGTH')
    side_a_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    side_b_finish: EnumProperty(name='Side B', items=[
        ('NONE', 'None', 'Keep the cut edge sharp'), ('CHAMFER', 'Chamfer', 'Flat chamfer on the cut edge'),
        ('BEVEL', 'Bevel', 'Rounded bevel on the cut edge')], default='NONE',
        description='Side B = the new "_Split" part')
    side_b_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=0.5, precision=4, unit='LENGTH')
    side_b_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    split_cap: BoolProperty(name='Cap Split', default=True,
                            description='Close the cut faces of both parts (OFF leaves open shells)')
    fast_line: BoolProperty(name='Plane Cut for 2 Points', default=True,
                            description='A two-point line uses a fast plane bisect instead of a Boolean')
    line_cap: BoolProperty(name='Fill Plane Cut', default=True,
                           description='Fill the opening left by a plane cut (closed meshes)')


CLASSES = (MCH_PG_Brush, MCH_PG_Cut)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_brush = bpy.props.PointerProperty(type=MCH_PG_Brush)
    bpy.types.Scene.mch_cut = bpy.props.PointerProperty(type=MCH_PG_Cut)


def unregister():
    for n in ('mch_cut', 'mch_brush'):
        if hasattr(bpy.types.Scene, n):
            delattr(bpy.types.Scene, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
