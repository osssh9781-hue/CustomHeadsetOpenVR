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
    ('HIDE', 'Box Hide', 'Draw a shape over meshes to hide what is inside it (Alt: show it again); Cap / Open, '
     'Mirror X, Show All, Apply - non-destructive until Apply', 'hide', 'HIDE_ON', 'mecha.box_hide', 'OK'),
    ('CMOVE', 'Concept Move', 'Grab the surface and pull it like clay (Sphere / Box, Hardness); the pulled part is '
     'really generated, F9 adjusts it. Hold D + drag in any tool does the same',
     'concept_move', 'VIEW_PAN', 'mecha.concept_move', 'OK'),
    ('GYM', 'Jungle Gym', 'Draw in 3D by crawling along a lattice of bars (orange X / Y / Z, 45 degrees); on a body '
     'the bars stick to it and the line wraps round it. Open line = tube, flat loop = Base Mesh',
     'jungle_gym', 'MESH_GRID', 'mecha.jungle_gym', 'PARTIAL'),
    ('BASE', 'Base Mesh', 'Draw an outline to create a NEW solid (Flat / Chamfer / Bevel / Dome); RMB = profiles',
     'base', 'MESH_CUBE', 'mecha.base_mesh', 'OK'),
    ('CBASE', 'Creature Base Mesh', 'Draw an outline to create a NEW rounded solid: Puff (round, thin parts thin), '
     'Ridge (diamond cross-section) or Pillow (flat, round edge); Height slider; RMB = profiles',
     'cbase', 'META_BALL', 'mecha.creature_base', 'OK'),
    ('SUBD', 'SubD Plane', 'Plane with live Simple + Catmull-Clark subdivision and Solidify; extrude edges '
     'in Edit Mode to build armour panels', 'subd', 'MOD_SUBSURF', None, 'OK'),
    ('PLATE', 'Armor Plate', 'Draw a lasso on a mesh: a separate armour plate made of new clean faces '
     '(no retopology); mouse wheel while drawing = profile', 'armor', 'MOD_SOLIDIFY', 'mecha.armor_plate', 'OK'),
    ('CPLATE', 'Creature Plate', 'Draw a lasso on a mesh: a rounded plate laid on the surface - Puff / Ridge / '
     'Pillow, Height and End Height (one end lifts like a scale), Edge Round / Edge Thickness; live until Apply',
     'cplate', 'MOD_SMOOTH', 'mecha.creature_plate', 'OK'),
    ('BELT', 'Belt Maker', 'Draw a line over a mesh: a strap - Wrap Around (all the way around there) or Follow '
     'Line (along the line); Plain / Rail (sci-fi rails, groove, bolts) strap; live until Apply',
     'belt', 'MOD_CURVE', 'mecha.belt_maker', 'OK'),
    ('SPIKE', 'Creature Spike', 'Draw a line over a mesh: spikes stand along it - four presets (tick some, they '
     'mix at random), size / lean / turn with random amounts; live until Apply',
     'spike', 'CON_TRACKTO', 'mecha.creature_spike', 'OK'),
    ('SCALES', 'Creature Scales', 'Draw a line over a mesh: overlapping scales along it - Scale A / B / C mixed at '
     'random, size and rotation random, rows; thick roots, thin lifted tips; live until Apply',
     'scales', 'SHARPCURVE', 'mecha.creature_scales', 'OK'),
    ('SBRUSH', 'Scale Brush', 'Lasso an area on a mesh: it fills with flat-bottomed scales packed close together '
     'without touching - twelve pebble presets mixed at random, size / rotation random, gap; live until Apply',
     'scale_brush', 'MESH_ICOSPHERE', 'mecha.scale_brush', 'OK'),
    ('BRIDGE', 'Bridge Patch', 'Lasso across two meshes: the gap between them fills with a smooth patch on the side '
     'you see (the slope carries on), its edges sunk into both; Smooth / Bulge / Thickness; live until Apply',
     'bridge_patch', 'MOD_LATTICE', 'mecha.bridge_patch', 'OK'),
    ('FLOWER', 'Flower Plate', 'Draw an outline on a mesh: that shape grows from it - where you start drawing '
     'stays on the surface, the rest lifts off and bends (Lift, Curl back over or outward, Side Bend, Roll); '
     'live until Apply',
     'flower', 'OUTLINER_OB_FORCE_FIELD', 'mecha.flower_plate', 'OK'),
    ('SCURVE', 'Surface Curve', 'Draw along a mesh: a curve (tube) lies on it - then edit it like a Mesh Curve '
     '(points, radius, profiles incl. Creature / Guts / From Object, outer lines)',
     'surface_curve', 'CURVE_BEZCURVE', 'mecha.surface_curve', 'OK'),
    ('CAPE', 'Cape', 'Draw on a body from the side the cape hangs on: the top of the drawing is the collar - a '
     'live cloak / capelet / poncho drapes from it (Style, Length, Hem, Flare, Wrap, folds, Wind, Tatter); a short '
     'drawing = Preset, a tall one = your outline',
     'cape', 'MOD_CLOTH', 'mecha.cape', 'OK'),
    ('HAIR', 'Creature Hair', 'Draw the scalp area on a head: live dreadlocks / tentacles / quills / strands grow '
     'there and fall over the body (Style, Count, Length, Thickness, Taper, Lift, Gravity, Wave, Rope, Rings)',
     'hair', 'CURVES', 'mecha.creature_hair', 'OK'),
    ('GARMENT', 'Clothing', 'Front view: draw the outline of a top or pants over a body - the body surface inside it '
     '(front and back) becomes a live garment: Type (T-Shirt / Hoodie / Pants / Cargo), Fit, Smooth, Hem Flare, '
     'Wrinkles, Thickness',
     'garment', 'MATCLOTH', 'mecha.clothing', 'OK'),
    ('HOOD', 'Hood', 'Look at the face and draw round the head: a live hood over it, open toward you, with a cowl '
     'over the shoulders (Style, Looseness, Peak, Cowl, Open Front, Face Opening, Folds, Thickness)',
     'hood', 'USER', 'mecha.hood', 'OK'),
    ('SCARF', 'Scarf', 'Look at the front and draw round the neck: live wraps round it with tails or a front drape '
     '(Style, Wraps, Height, Thickness, Bunching, Flare, Ends, Tail Length / Width, Fringe)',
     'scarf', 'MOD_CLOTH', 'mecha.scarf', 'OK'),
    ('DETAIL', 'Plate Detail', 'Draw an outline on a plate: a low surface trim - flat inside, 1 / 2 / 3 stepped '
     'layers along the edge (edge high or inside high), optional screw recesses; live until Apply',
     'detail1', 'MESH_PLANE', 'mecha.plate_detail', 'OK'),
    ('DETAIL2', 'Plate Detail 2', 'Draw an outline on a surface: it rises smoothly inside the outline to a flat top '
     '(height, slope width, slope shape); live until Apply', 'detail2', 'SURFACE_NSURFACE', 'mecha.plate_detail2', 'OK'),
    ('DETAIL3', 'Plate Detail 3', 'Draw an outline on a plate: a flat raised panel with straight walls, no trim '
     'layers (height, lift); live until Apply', 'detail3', 'MESH_PLANE', 'mecha.plate_detail3', 'OK'),
    ('SCREW', 'Screw Stamp', 'Click on a surface to place screw heads (Dome / Post / Socket / Cross), aligned '
     'to the surface; size, height and hole depth stay live; Alt + click removes', 'screw', 'RADIOBUT_ON',
     'mecha.screw_stamp', 'OK'),
    ('WRINKLE', 'Cloth Plate', 'Draw a lasso on a mesh: a separate padded cloth panel - puffs up inside the '
     'border, edge roll, seam pinch folds, stitching (+ optional Padding / Denim / Leather pattern), live until Apply', 'cloth', 'MOD_CLOTH', 'mecha.cloth_wrinkle', 'OK'),
    ('PRIMITIVE', 'Primitive', 'Ghost shape with handles: Enter = merge into the mesh it touches, Alt+Enter = '
     'subtract; Station Primitive presets; RMB = shape picker',
     'primitive', 'MESH_CUBE', 'mecha.primitive', 'OK'),
    ('BOOLEAN', 'Boolean', 'Difference / Union / Intersect with a selected cutter mesh', 'boolean', 'MOD_BOOLEAN', None, 'OK'),
    ('FUSE', 'Smart Fuse', 'Union two overlapping meshes with a fillet/chamfer seam', 'fuse', 'MOD_BEVEL', None, 'PARTIAL'),
    ('MIRROR', 'Symmetry', 'Symmetry: lean the mouse to the side to copy to, Enter applies (left buttons: live Mirror)', 'mirror', 'MOD_MIRROR', None, 'OK'),
    ('MASK', 'Mask', 'Paint a face mask with the shared shapes (Alt: erase)', 'mask', 'MOD_MASK', 'mecha.mask', 'PARTIAL'),
    ('ARRAY', 'Curve Array', 'Repeat a part along a drawn curve', 'array', 'MOD_ARRAY', None, 'OK'),
    ('RADIAL', 'Radial Array', 'Radial copies around the 3D cursor + Boolean', 'radial', 'MOD_SCREW', None, 'OK'),
    ('DRAW', 'Mesh Curve', 'Draw a curve and sweep a profile along it (or a panel-line cut); '
     'smooth/straight points, resolution, rotation, twist', 'panel', 'CURVE_BEZCURVE', None, 'OK'),
    ('POSE', 'Deform', 'Lattice Cage / Bend Curve: click control points and Move / Rotate / Scale them with '
     'falloff (rotate a Bend point = local twist); non-destructive until Apply. Rigid pose not yet supported',
     'deform', 'MOD_LATTICE', None, 'PARTIAL'),
    ('EXTRACT', 'Face Extract', 'Edit Mode: selected faces -> a separate part. Basic Extract (height, thickness, '
     'chamfer width / angle / depth, bevel, outer edge) or Armor Sculpt (N/E/S/W thickness and edges, centre ridge)',
     'extract', 'FACESEL', None, 'OK'),
    ('MOLDING', 'Edge Molding', 'Molding profile along face boundaries, edges, part outlines or the Armor centre line',
     'molding', 'MOD_CURVE', None, 'OK'),
    ('HOLLOW', 'Hollow / Shell', 'Hollow shell with wall thickness, direction, rim and openings (live Solidify)',
     'hollow', 'MOD_SOLIDIFY', None, 'OK'),
    ('ALONG', 'Mesh Along Curve', 'Curve Deform and Curve Array (rigid / deform), Free or World X/Y/Z curve base line',
     'along', 'MOD_ARRAY', None, 'OK'),
    ('CABLE', 'Cable', 'Two-point cables between mesh surfaces, Edge to Cable, thickness / profile / sag / twist',
     'cable', 'OUTLINER_OB_CURVE', None, 'OK'),
    ('TUBE', 'Mesh Curve', 'Nomad-style curve: click points (on the mesh or in the air), a live solid tube right '
     'away - radius per point, profile, cap, hole, twist - or Repeat your own (linked) object along it with spacing',
     'tube', 'CURVE_BEZCURVE', None, 'OK'),
    ('TUBE_SAME', 'Line Curve', 'Click points: a tube of one thickness everywhere (no per-point size) - Thickness '
     'makes all of it thicker / thinner; profile, cap, closed, twist like Mesh Curve; live until Apply',
     'line_curve', 'CURVE_BEZCURVE', None, 'OK'),
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
# v0.10 (B08/F07): Mask does not work reliably for the user -> hidden from the
# tool list, Space / V menus, toolbar and hotkeys.  Its code, operators and
# all saved mask data (face attributes, vertex groups) are kept untouched.
HIDDEN_TOOLS = {'MASK', 'DRAW'}     # 0.23.2: the old Mesh Curve (DRAW) is replaced by the Tube tool
# 0.24.31: the new cloth tools (Clothing / Hood / Scarf, and the Edit Mode Quad Cloth panel) are still being tuned:
# hidden from every menu and the toolbar.  Their code and saved live objects are kept; True brings them back.
EXPERIMENTAL_CLOTH = False
EXPERIMENTAL_CLOTH_TOOLS = {'GARMENT', 'HOOD', 'SCARF'}
if not EXPERIMENTAL_CLOTH:
    HIDDEN_TOOLS |= EXPERIMENTAL_CLOTH_TOOLS
VISIBLE_TOOLS = tuple(t for t in TOOLS if t[0] not in HIDDEN_TOOLS)
# V quick menu (docs/02): the six core tools (+ Armor Plate since 0.19).
QUICK_TOOLS = ('CUT', 'BOOLEAN', 'BASE', 'SUBD', 'SPLIT', 'RADIAL', 'PLATE')   # 0.19: + Armor Plate
NATIVE_TO_TOOL = {t[5]: t[0] for t in TOOLS if t[5]}
SHAPE_TOOLS = {'CUT', 'SPLIT', 'MASK', 'BASE', 'CBASE', 'PLATE', 'CPLATE', 'WRINKLE', 'HIDE', 'DETAIL', 'DETAIL2',
               'DETAIL3', 'BELT', 'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'FLOWER', 'SCURVE', 'CAPE', 'HAIR', 'GARMENT', 'HOOD', 'SCARF'}

# Enum numbers keep v0.5.9 values so saved .blend files map to the same tool.
_ENUM_NUMBERS = {'CUT': 1, 'BOOLEAN': 2, 'FUSE': 3, 'MIRROR': 4, 'MASK': 5, 'DRAW': 6,
                 'ARRAY': 7, 'RADIAL': 8, 'SURFACE': 9, 'LIBRARY': 10, 'EDIT': 11,
                 'REMESH': 12, 'SPLIT': 13, 'POSE': 14, 'BASE': 15, 'LOFT': 16, 'ZBRUSH': 17, 'SUBD': 18, 'PRIMITIVE': 19,
                 'EXTRACT': 20, 'MOLDING': 21, 'HOLLOW': 22, 'ALONG': 23, 'CABLE': 24, 'PLATE': 25, 'WRINKLE': 26, 'TUBE': 27,
                 'HIDE': 28, 'DETAIL': 29, 'DETAIL2': 30, 'SCREW': 31, 'DETAIL3': 32, 'TUBE_SAME': 33,
                 'CBASE': 34, 'CPLATE': 35, 'BELT': 36, 'SPIKE': 37, 'SCALES': 38, 'FLOWER': 39, 'SCURVE': 40, 'SBRUSH': 41, 'BRIDGE': 42, 'CAPE': 43, 'HAIR': 44, 'GARMENT': 45, 'HOOD': 46, 'SCARF': 47, 'CMOVE': 48, 'GYM': 49}
TOOL_ENUM_ITEMS = [(t[0], t[1], t[2], t[4], _ENUM_NUMBERS[t[0]]) for t in TOOLS]

SHAPES = (
    ('LASSO', 'Lasso', 'Straight-segment outline: click point by point (draw freely with Free Draw). '
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
    native_id = native_tool_id(context)
    native = NATIVE_TO_TOOL.get(native_id)
    settings = getattr(getattr(context, 'scene', None), 'mch_settings', None)
    if native:
        chosen = settings.mch_active_tool if settings else native
        try:
            stuck = settings is not None and settings.get('mch_native_at_choice') == native_id
        except (AttributeError, TypeError):
            stuck = False
        if stuck and chosen != native and TOOL_BY_ID[chosen][5] is None:
            # The user picked a non-drawing tool but the toolbar could not be
            # switched: the explicit choice wins (the panel follows it and the
            # drawing tool does not grab LMB, see cut_engine.StrokeLogic.invoke).
            return chosen
        return native
    chosen = settings.mch_active_tool if settings else 'CUT'
    return 'CUT' if chosen in HIDDEN_TOOLS else chosen


def sidebar_select(context):
    """0.23.24 the general sidebar extras (Primitive Shapes, Detail Stamp, High Poly, icon size, hotkeys ...)
    only in Select mode - with a tool chosen the sidebar shows just that tool."""
    try:
        from . import bottom_bar
        return bool(bottom_bar.in_select(context))
    except (AttributeError, KeyError, TypeError, ImportError):
        return True


def hud_for(context, tools):
    """0.23.21 a tool's HUD (buttons / sliders next to its result) only while that tool is chosen - like
    the Mirror buttons; switching to another tool hides it (the result itself stays)."""
    try:
        return effective_tool(context) in tools
    except (AttributeError, KeyError, TypeError):
        return True


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
    stroke_spacing: FloatProperty(name='Stroke Spacing (px)', default=4.0, min=1.0, max=50.0,
                                  description='Free Draw: a new outline point every N pixels of (stabilized) movement')
    stab_enable: BoolProperty(name='Stabilizer (Lazy Mouse)', default=False,
                              description='Free Draw: the drawn line follows the mouse slowly and smoothly while '
                                          'drawing (Cut / Split / Base Mesh). OFF = exact previous behaviour')
    stab_strength: FloatProperty(name='Smoothing Strength', default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE',
                                 description='Higher = smoother but slower follow (time based, same feel at any '
                                             'mouse rate). Applies immediately, also while drawing')
    stab_radius: FloatProperty(name='Lazy Radius (px)', default=20.0, min=0.0, soft_max=80.0, max=200.0,
                               description='The line does not move while the cursor stays inside this circle; '
                                           'outside, it is pulled along on the circle edge')
    stab_guide: BoolProperty(name='Show Lazy Guide', default=True,
                             description='Draw the lazy circle and the cursor-to-line string while drawing')
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
    line_mode: BoolProperty(name='Line', default=False,
                            description='Lasso / Curve Lasso / Stroke draw a LINE: the tool uses a band of Line Width '
                                        'around the path instead of the enclosed area')
    line_width: FloatProperty(name='Line Width', default=0.02, min=0.0005, soft_max=0.5, max=20.0, unit='LENGTH',
                              precision=4, description='Width of the band drawn in Line mode')
    line_caps: EnumProperty(name='Line Ends', items=[('ROUND', 'Round', 'Round line ends'),
                                                     ('FLAT', 'Flat', 'Square line ends')], default='ROUND')
    # 0.24.21 like a pen: the line thins to a point at both ends (Taper) and / or follows the tablet pressure
    line_taper_on: BoolProperty(name='Taper', default=False,
                                description='Line mode: the band thins to a point toward both ends (amount next to it)')
    line_taper: FloatProperty(name='Taper Amount', default=0.5, min=0.0, max=1.0, subtype='FACTOR',
                              description='How much of the line thins toward the ends (1 = pointed over the whole '
                                          'length)')
    line_pressure: BoolProperty(name='Pressure', default=False,
                                description='Line mode, Free Draw: the band is as wide as you press the pen '
                                            '(tablet pressure); [ / ] change Line Width')
    surface_mode: BoolProperty(name='Surface', default=False,
                               description='Cut / Split / Armor Plate / Cloth Plate: click points ON the mesh (they '
                                           'stay on it when you orbit); Enter applies (Cut / Split: a loop around a '
                                           'part splits it off; plates: the outline on the surface)')
    through_mode: BoolProperty(name='Through', default=False,
                               description='Armor / Cloth Plate: the outline goes through the mesh - the back is '
                                           'taken too (every layer inside the outline); split into panels where '
                                           'it turns away from the view and at sharp creases')
    through_crease: FloatProperty(name='Crease', default=50.0, min=5.0, max=180.0, precision=0,
                                  description='Through: a fold sharper than this splits the panels (a seam), '
                                              '180 = never')
    surface_gap: FloatProperty(name='Cut Gap', default=0.0005, min=0.0, soft_max=0.02, max=1.0, unit='LENGTH',
                               precision=4, description='Gap between the parts split by the Surface Lasso')
    sketch_first: BoolProperty(name='Sketch', default=False,
                               description='Lasso tools: draw outlines into a sketch, Alt+draw subtracts, '
                                           'Enter applies (Alt+Enter: Alt action), Backspace: last, Esc: clear')


class MCH_PG_Cut(bpy.types.PropertyGroup):
    depth_mode: EnumProperty(name='Depth', items=[
        ('THROUGH', 'Through All', 'Cut through the whole object along the view'),
        ('SURFACE', 'From Surface', 'Pocket of fixed depth starting at the surface under the shape')],
        default='THROUGH')
    depth: FloatProperty(name='Cut Depth', default=0.1, min=0.00001, soft_max=10.0, precision=4,
                         unit='LENGTH')
    targets: EnumProperty(name='Targets', items=[
        ('AUTO', 'Auto Target', 'Every mesh the drawn shape covers, whatever is selected: keep the tool and cut the '
                                'next part directly (T toggles)'),
        ('SELECTED', 'Selected Only', 'Only the selected meshes the shape covers (cut several chosen parts at once)'),
        ('ACTIVE', 'Active', 'Only the active mesh (or the mesh under the cursor)')], default='AUTO',
        description='Auto Target (default since 0.12): the shape decides what is cut. Selected Only: the selection does')
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
    finish_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=10.0, precision=4,
                                unit='LENGTH', description='Edge Finish width in model units (type any value)')
    finish_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    finish_profile: FloatProperty(name='Profile', default=0.5, min=0.0, max=1.0)
    shared_mesh: EnumProperty(name='Shared Mesh', items=[
        ('SINGLE', 'This Object Only', 'Linked duplicates (Alt+D) keep the old mesh; this object gets its own copy'),
        ('ALL', 'All Linked Copies', 'Change the shared mesh data, so every linked duplicate is cut')],
        default='SINGLE')
    split_mode: EnumProperty(name='Split Mode', items=[
        ('NORMAL', 'Normal', 'Thin cut line: two parts touching along the cut'),
        ('GAP', 'Gap', 'Thick blade: removes a strip of Gap Width between the two parts')], default='NORMAL')
    gap_width: FloatProperty(name='Gap Width', default=0.02, min=0.0, soft_max=10.0, precision=4, unit='LENGTH',
                             description='Width of the removed strip in model units, centred on the drawn line')
    side_a_finish: EnumProperty(name='Side A', items=[
        ('NONE', 'None', 'Keep the cut edge sharp'), ('CHAMFER', 'Chamfer', 'Flat chamfer on the cut edge'),
        ('BEVEL', 'Bevel', 'Rounded bevel on the cut edge')], default='NONE',
        description='Side A = the remaining original object')
    side_a_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=10.0, precision=4, unit='LENGTH')
    side_a_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    side_b_finish: EnumProperty(name='Side B', items=[
        ('NONE', 'None', 'Keep the cut edge sharp'), ('CHAMFER', 'Chamfer', 'Flat chamfer on the cut edge'),
        ('BEVEL', 'Bevel', 'Rounded bevel on the cut edge')], default='NONE',
        description='Side B = the new "_Split" part')
    side_b_width: FloatProperty(name='Width', default=0.01, min=0.0, soft_max=10.0, precision=4, unit='LENGTH')
    side_b_segments: IntProperty(name='Segments', default=3, min=1, max=32)
    finish_clamp: BoolProperty(name='Clamp Overlap', default=True,
                               description='Limit bevel width where neighbouring edges are short (safe geometry). '
                                           'The result message tells you when the width was limited')
    finish_crisp: BoolProperty(name='Crisp Shading', default=True,
                               description='0.24.24 hard-surface look: the bevel band gets sharp borders (a chamfer is '
                                           'a flat strip, a bevel shades round inside), the cut walls stay flat, and '
                                           'imported custom normals (FBX) are dropped so they do not smear over the '
                                           'new faces')
    split_cap: BoolProperty(name='Cap Split', default=True,
                            description='Close the cut faces of both parts (OFF leaves open shells)')
    fast_line: BoolProperty(name='Plane Cut for 2 Points', default=True,
                            description='A two-point line uses a fast plane bisect instead of a Boolean')
    line_cap: BoolProperty(name='Fill Plane Cut', default=True,
                           description='Fill the opening left by a plane cut (closed meshes)')


CLASSES = (MCH_PG_Brush, MCH_PG_Cut)


# -----------------------------------------------------------------------------
# Ctrl+Z must not change the tool UI: the brush shape / stamp / selected Mecha
# tool live in the Scene, so Blender's undo restored the shape picked before
# (user report 0.11.2).  Snapshot them before undo/redo, put them back after.
# -----------------------------------------------------------------------------

UNDO_KEEP = (('mch_brush', 'shape'), ('mch_brush', 'line_open'), ('mch_settings', 'mch_active_tool'),
             (None, 'mch_png_preset'))
_undo_snapshot = {}


def _owner(scene, group):
    return scene if group is None else getattr(scene, group, None)


def snapshot_ui_state(scene=None):
    scene = scene or bpy.context.scene
    _undo_snapshot.clear()
    if scene is None:
        return
    _undo_snapshot['scene'] = scene.name
    for group, attr in UNDO_KEEP:
        owner = _owner(scene, group)
        if owner is not None and hasattr(owner, attr):
            _undo_snapshot[(group, attr)] = getattr(owner, attr)


def restore_ui_state(scene=None):
    scene = scene or bpy.context.scene
    if scene is None or _undo_snapshot.get('scene') != scene.name:
        return []
    changed = []
    for group, attr in UNDO_KEEP:
        key = (group, attr)
        owner = _owner(scene, group)
        if key not in _undo_snapshot or owner is None or not hasattr(owner, attr):
            continue
        value = _undo_snapshot[key]
        try:
            if getattr(owner, attr) != value:
                setattr(owner, attr, value)
                changed.append(attr)
        except (TypeError, AttributeError, ValueError):
            pass          # e.g. a stamp preset that no longer exists
    return changed


@bpy.app.handlers.persistent
def _on_undo_pre(scene, *_args):
    try:
        snapshot_ui_state(scene)
    except (ReferenceError, AttributeError):
        _undo_snapshot.clear()


@bpy.app.handlers.persistent
def _on_undo_post(scene, *_args):
    try:
        restore_ui_state(scene)
    except (ReferenceError, AttributeError):
        pass


_UNDO_HANDLERS = (('undo_pre', _on_undo_pre), ('redo_pre', _on_undo_pre),
                  ('undo_post', _on_undo_post), ('redo_post', _on_undo_post))


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_brush = bpy.props.PointerProperty(type=MCH_PG_Brush)
    bpy.types.Scene.mch_cut = bpy.props.PointerProperty(type=MCH_PG_Cut)
    for name, fn in _UNDO_HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        if fn not in lst:
            lst.append(fn)


def unregister():
    for name, fn in _UNDO_HANDLERS:
        lst = getattr(bpy.app.handlers, name)
        while fn in lst:
            lst.remove(fn)
    for n in ('mch_cut', 'mch_brush'):
        if hasattr(bpy.types.Scene, n):
            delattr(bpy.types.Scene, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
