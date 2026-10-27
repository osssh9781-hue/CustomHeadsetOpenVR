"""0.24.60 ZBrush-style sculpting: Sculpt Mode in the MECHA LAB tab gets ZBrush's names, keys and shelves (the user's
own ZBrush custom UI) on top of Blender's sculpt tools.  Nothing outside the MECHA LAB tab changes (every key and
button checks ``on()``), and Blender's own sculpt keys work again the moment you leave the tab.

Mouse (like ZBrush):
    drag on the model            sculpt with the brush            Alt: Zsub        Shift: Smooth
    drag on empty canvas         rotate (Shift: snap to a side)   Alt: move, let Alt go while dragging: zoom
    Ctrl + drag on the model     MaskPen                          Ctrl+Alt: unmask
    Ctrl + click empty           invert the mask                  Ctrl + drag empty: mask lasso (Alt: unmask)
    Ctrl+Shift + click model     show only that polygroup         Ctrl+Shift + click empty: show all
    Ctrl+Shift + drag empty      show only what is inside         Ctrl+Shift+Alt: hide what is inside
Keys: Space / right-click = brush menu at the cursor, S / U / O = it with Draw Size / Z Intensity / Focal Shift under
the mouse, B = brushes (then the letters: B S T = Standard), X = symmetry, D / Shift+D = SDiv up / down,
Ctrl+D = Divide, Ctrl+W = polygroup from mask, F = frame, Shift+F = PolyF.

The ZBrush brushes are Blender's own Essentials brushes (Standard = Draw, ClayBuildup = Clay Strips,
DamStandard = Crease Sharp, Move = Grab ...); DynaMesh is Blender's voxel remesh by point count, ZRemesher is
Quadriflow, SDiv / Divide / Del Higher are Multires.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Quaternion, Vector

ORANGE = (0.93, 0.47, 0.13, 1.0)
ORANGE_FILL = (0.70, 0.34, 0.09, 1.0)
LIB = 'brushes/essentials_brushes-mesh_sculpt.blend/Brush/'
MULTIRES = 'Multires'

# (ZBrush name, Blender Essentials brush, B-key letters)
BRUSHES = (
    ('Standard', 'Draw', 'ST'), ('Paint', 'Paint Hard', 'PA'), ('ClayBuildup', 'Clay Strips', 'CB'),
    ('Move', 'Grab', 'MV'), ('SnakeHook', 'Snake Hook', 'SK'), ('DamStandard', 'Crease Sharp', 'DS'),
    ('Layer', 'Layer', 'LA'), ('Clay', 'Clay', 'CL'), ('Inflat', 'Inflate/Deflate', 'IN'),
    ('ClayTubes', 'Clay Thumb', 'CT'), ('hPolish', 'Scrape/Fill', 'HP'), ('TrimDynamic', 'Trim', 'TD'),
    ('TrimAdaptive', 'Scrape Multiplane', 'TA'), ('Flatten', 'Flatten/Contrast', 'FL'), ('Planar', 'Plateau', 'PL'),
    ('sPolish', 'Relax Slide', 'SP'), ('Move Topological', 'Elastic Grab', 'MT'), ('Polish', 'Fill/Deepen', 'PO'),
    ('Smooth', 'Smooth', 'SM'), ('MaskPen', 'Mask', 'MP'), ('Pinch', 'Pinch/Magnify', 'PN'), ('Blob', 'Blob', 'BB'),
    ('Pose', 'Pose', 'PS'), ('Polygroupit', 'Face Set Paint', 'PG'),
)
BY_Z = {z: (z, bl, code) for z, bl, code in BRUSHES}
BY_BL = {bl: z for z, bl, _c in BRUSHES}
SHELF = (('Standard', 'Paint', 'ClayBuildup', 'Move', 'SnakeHook', 'DamStandard', 'Layer', 'Clay', 'Inflat',
          'ClayTubes'),
         ('hPolish', 'TrimDynamic', 'TrimAdaptive', 'Flatten', 'Planar', 'sPolish', 'Move Topological', 'Polish'))
# ZBrush stroke names -> Blender stroke methods
STROKES = (('FREEHAND', 'FreeHand', 'DOTS'), ('DOTS', 'Dots', 'SPACE'), ('DRAGDOT', 'DragDot', 'DRAG_DOT'),
           ('DRAGRECT', 'DragRect', 'ANCHORED'), ('SPRAY', 'Spray', 'AIRBRUSH'), ('LINE', 'LineII', 'LINE'),
           ('CURVE', 'Curve', 'CURVE'))
# Focal Shift -> Blender falloff preset (negative = harder / flatter, positive = softer / pointier)
FOCAL = ((-100, -61, 'CONSTANT', -80), (-60, -21, 'SPHERE', -40), (-20, 19, 'SMOOTH', 0), (20, 59, 'LIN', 40),
         (60, 100, 'SHARP', 80))
TOOLS = {'CLIP_CURVE': 'builtin.line_project', 'TRIM_CURVE': 'builtin.line_trim', 'TRIM_LASSO': 'builtin.lasso_trim',
         'DRAW': 'builtin.brush', 'MOVE': 'builtin.move', 'SCALE': 'builtin.scale', 'ROTATE': 'builtin.rotate'}


def icon_stem(bl_name):
    return 'zb_' + bl_name.lower().replace('/', '_').replace(' ', '_')


# --- where it is on ----------------------------------------------------------------------------------------------

def on(context):
    """Sculpt Mode in the MECHA LAB tab (Preferences: ZBrush Sculpt)."""
    from .workspace_ui import pref
    from . import tool_state as ts
    try:
        return (bool(pref('zbrush_sculpt', True)) and getattr(context, 'mode', '') == 'SCULPT'
                and ts.is_mecha_workspace(getattr(context, 'workspace', None)))
    except (AttributeError, ReferenceError):
        return False


def brush(context=None):
    context = context or bpy.context
    sc = getattr(getattr(context, 'tool_settings', None), 'sculpt', None)
    return getattr(sc, 'brush', None) if sc is not None else None


def unified(context=None):
    context = context or bpy.context
    ts = context.tool_settings
    sc = getattr(ts, 'sculpt', None)
    return getattr(sc, 'unified_paint_settings', None) or getattr(ts, 'unified_paint_settings', None)


def zb_name(b):
    return BY_BL.get(b.name, b.name) if b is not None else ''


def activate(context, zname):
    """Make the Blender brush behind ZBrush's ``zname`` the sculpt brush; '' or an error text."""
    entry = BY_Z.get(zname)
    if entry is None:
        return f'Unknown brush {zname}'
    try:
        if _tool_id(context) != 'builtin.brush':
            bpy.ops.wm.tool_set_by_id(name='builtin.brush')
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:
        bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS', relative_asset_identifier=LIB + entry[1])
    except RuntimeError as ex:
        return str(ex).splitlines()[0]
    remember(zname)
    return ''


RECENT = []                 # the last brushes used (the Space menu shows them)


def remember(zname):
    if zname in RECENT:
        RECENT.remove(zname)
    RECENT.insert(0, zname)
    del RECENT[6:]


def multires(ob):
    if ob is None:
        return None
    return next((m for m in ob.modifiers if m.type == 'MULTIRES'), None)


def space(context=None):
    context = context or bpy.context
    sp = getattr(context, 'space_data', None)
    if sp is not None and sp.type == 'VIEW_3D':
        return sp
    area = getattr(context, 'area', None)
    if area is not None and area.type == 'VIEW_3D':
        return area.spaces.active
    for win in getattr(context.window_manager, 'windows', []):
        for a in win.screen.areas:
            if a.type == 'VIEW_3D':
                return a.spaces.active
    return None


# --- ZBrush-named settings (they read / write the Blender brush and view settings) --------------------------------

def _safe(fn, default):
    try:
        return fn()
    except (AttributeError, ReferenceError, TypeError, ValueError, IndexError, KeyError, RuntimeError):
        return default


def _size_get(self):
    def f():
        u, b = unified(), brush()
        return int(u.size if u is not None and u.use_unified_size else b.size)
    return _safe(f, 50)


def _size_set(self, v):
    def f():
        u, b = unified(), brush()
        if u is not None and u.use_unified_size:
            u.size = int(v)
        else:
            b.size = int(v)
    _safe(f, None)


def _int_get(self):
    def f():
        u, b = unified(), brush()
        s = u.strength if u is not None and u.use_unified_strength else b.strength
        return int(round(s * 100))
    return _safe(f, 50)


def _int_set(self, v):
    def f():
        u, b = unified(), brush()
        if u is not None and u.use_unified_strength:
            u.strength = v / 100.0
        else:
            b.strength = v / 100.0
    _safe(f, None)


def _focal_get(self):
    def f():
        preset = brush().curve_distance_falloff_preset
        stored = int(self.get('_focal', 0))
        for lo, hi, p, mid in FOCAL:
            if p == preset:
                return stored if lo <= stored <= hi else mid
        return stored
    return _safe(f, 0)


def _focal_set(self, v):
    self['_focal'] = int(v)

    def f():
        for lo, hi, p, _mid in FOCAL:
            if lo <= v <= hi:
                brush().curve_distance_falloff_preset = p
                return
    _safe(f, None)


def _zmode_get(self):
    def f():
        b = brush()
        items = [i.identifier for i in b.bl_rna.properties['direction'].enum_items]
        return 1 if len(items) > 1 and b.direction == items[1] else 0
    return _safe(f, 0)


def _zmode_set(self, v):
    def f():
        b = brush()
        items = [i.identifier for i in b.bl_rna.properties['direction'].enum_items]
        if len(items) > 1:
            b.direction = items[1 if v else 0]
    _safe(f, None)


def _brush_bool(attr):
    def get(self):
        return _safe(lambda: bool(getattr(brush(), attr)), False)

    def set_(self, v):
        _safe(lambda: setattr(brush(), attr, bool(v)), None)
    return get, set_


def _lazy_step_get(self):
    return _safe(lambda: max(0.0, min(1.0, (brush().smooth_stroke_factor - 0.5) / 0.49)), 0.25)


def _lazy_step_set(self, v):
    _safe(lambda: setattr(brush(), 'smooth_stroke_factor', 0.5 + 0.49 * max(0.0, min(1.0, v))), None)


def _lazy_radius_get(self):
    return _safe(lambda: int(brush().smooth_stroke_radius), 75)


def _lazy_radius_set(self, v):
    _safe(lambda: setattr(brush(), 'smooth_stroke_radius', int(v)), None)


def _dynamic_get(self):
    def f():
        u, b = unified(), brush()
        src = u if u is not None and u.use_unified_size and hasattr(u, 'use_locked_size') else b
        return src.use_locked_size == 'SCENE'
    return _safe(f, False)


def _dynamic_set(self, v):
    def f():
        u, b = unified(), brush()
        src = u if u is not None and u.use_unified_size and hasattr(u, 'use_locked_size') else b
        src.use_locked_size = 'SCENE' if v else 'VIEW'
    _safe(f, None)


def _stroke_get(self):
    def f():
        m = brush().stroke_method
        return next(i for i, (_k, _n, bl) in enumerate(STROKES) if bl == m)
    return _safe(f, 1)


def _stroke_set(self, v):
    _safe(lambda: setattr(brush(), 'stroke_method', STROKES[v][2]), None)


def _sym(axis):
    def get(self):
        return _safe(lambda: bool(getattr(bpy.context.tool_settings.sculpt, 'use_symmetry_' + axis)), False)

    def set_(self, v):
        _safe(lambda: setattr(bpy.context.tool_settings.sculpt, 'use_symmetry_' + axis, bool(v)), None)
    return get, set_


def _radial_axis():
    sc = bpy.context.tool_settings.sculpt
    return next((i for i, a in enumerate('xyz') if getattr(sc, 'use_symmetry_' + a)), 0)


def _radial_get(self):
    return _safe(lambda: max(bpy.context.active_object.data.radial_symmetry) > 1, False)


def _radial_set(self, v):
    def f():
        me = bpy.context.active_object.data
        r = [1, 1, 1]
        if v:
            r[_radial_axis()] = max(2, int(self.radial_count))
        me.radial_symmetry = r
    _safe(f, None)


def _rcount_set(self, v):
    self['radial_count'] = int(v)
    if _radial_get(self):
        _radial_set(self, True)


def _rcount_get(self):
    return int(self.get('radial_count', 8))


def _sdiv_get(self):
    return _safe(lambda: int(multires(bpy.context.active_object).sculpt_levels), 0)


def _sdiv_set(self, v):
    def f():
        m = multires(bpy.context.active_object)
        v2 = max(0, min(int(v), m.total_levels))
        m.sculpt_levels = v2
        m.levels = v2
    _safe(f, None)


def _view_bool(path, invert=False):
    def get(self):
        def f():
            obj = space()
            for p in path[:-1]:
                obj = getattr(obj, p)
            return bool(getattr(obj, path[-1])) != invert
        return _safe(f, False)

    def set_(self, v):
        def f():
            obj = space()
            for p in path[:-1]:
                obj = getattr(obj, p)
            setattr(obj, path[-1], bool(v) != invert)
        _safe(f, None)
    return get, set_


def _persp_get(self):
    return _safe(lambda: space().region_3d.view_perspective == 'PERSP', True)


def _persp_set(self, v):
    _safe(lambda: setattr(space().region_3d, 'view_perspective', 'PERSP' if v else 'ORTHO'), None)


def _polyf_get(self):
    return _safe(lambda: bool(space().overlay.show_wireframes), False)


def _polyf_set(self, v):
    def f():
        ov = space().overlay
        ov.show_wireframes = bool(v)
        if hasattr(ov, 'show_sculpt_face_sets'):
            ov.show_sculpt_face_sets = bool(v)
    _safe(f, None)


def _matcap_items(self, context):
    try:
        lights = [l.name for l in context.preferences.studio_lights if l.type == 'MATCAP']
    except (AttributeError, ReferenceError):
        lights = []
    _MATCAPS[:] = [(n, n.rsplit('.', 1)[0].replace('_', ' ').title(), '') for n in lights] or [('NONE', 'None', '')]
    return _MATCAPS


_MATCAPS = []


def _matcap_get(self):
    def f():
        sh = space().shading
        names = [i[0] for i in _MATCAPS] or [i[0] for i in _matcap_items(self, bpy.context)]
        return names.index(sh.studio_light) if sh.light == 'MATCAP' and sh.studio_light in names else 0
    return _safe(f, 0)


def _matcap_set(self, v):
    def f():
        sh = space().shading
        names = [i[0] for i in _MATCAPS] or [i[0] for i in _matcap_items(self, bpy.context)]
        sh.type = 'SOLID'
        sh.light = 'MATCAP'
        sh.studio_light = names[v]
    _safe(f, None)


_bf = _brush_bool('use_frontface')
_lazy = _brush_bool('use_smooth_stroke')
_sx, _sy, _sz = _sym('x'), _sym('y'), _sym('z')
_floor = _view_bool(('overlay', 'show_floor'))
_transp = _view_bool(('shading', 'show_xray'))
_double = _view_bool(('shading', 'show_backface_culling'), invert=True)


class MCH_PG_ZBrush(bpy.types.PropertyGroup):
    draw_size: IntProperty(name='Draw Size', min=1, max=2000, soft_max=400, get=_size_get, set=_size_set,
                           description='Brush radius in pixels (Blender Radius)')
    z_intensity: IntProperty(name='Z Intensity', min=0, max=100, get=_int_get, set=_int_set,
                             description='How strong the brush is (Blender Strength x 100)')
    focal_shift: IntProperty(name='Focal Shift', min=-100, max=100, get=_focal_get, set=_focal_set,
                             description='Brush falloff: negative = harder, flatter; positive = softer, pointier '
                                         '(Blender Falloff preset Constant / Sphere / Smooth / Linear / Sharp)')
    zmode: EnumProperty(name='Z Mode', items=[('ZADD', 'Zadd', 'Add (Blender Direction +)'),
                                              ('ZSUB', 'Zsub', 'Subtract (Blender Direction -)')],
                        get=_zmode_get, set=_zmode_set)
    backface_mask: BoolProperty(name='BackfaceMask', get=_bf[0], set=_bf[1],
                                description='Do not sculpt the far side (Blender Front Faces Only)')
    lazy_mouse: BoolProperty(name='LazyMouse', get=_lazy[0], set=_lazy[1],
                             description='The stroke trails the pen (Blender Stabilize Stroke)')
    lazy_step: FloatProperty(name='LazyStep', min=0.0, max=1.0, get=_lazy_step_get, set=_lazy_step_set,
                             description='How smooth the trailing stroke is (Blender Stabilize Factor)')
    lazy_radius: IntProperty(name='LazyRadius', min=1, max=200, get=_lazy_radius_get, set=_lazy_radius_set,
                             description='Trail length in pixels (Blender Stabilize Radius)')
    dynamic: BoolProperty(name='Dynamic', get=_dynamic_get, set=_dynamic_set,
                          description='Brush size goes with the model when you zoom (Blender Radius Unit: Scene)')
    stroke: EnumProperty(name='Stroke', items=[(k, n, f'Blender: {bl.replace("_", " ").title()}', i)
                                               for i, (k, n, bl) in enumerate(STROKES)],
                         get=_stroke_get, set=_stroke_set)
    sym_x: BoolProperty(name='>X<', get=_sx[0], set=_sx[1], description='Mirror the stroke across X')
    sym_y: BoolProperty(name='>Y<', get=_sy[0], set=_sy[1], description='Mirror the stroke across Y')
    sym_z: BoolProperty(name='>Z<', get=_sz[0], set=_sz[1], description='Mirror the stroke across Z')
    radial: BoolProperty(name='(R)', get=_radial_get, set=_radial_set,
                         description='Radial symmetry round the symmetry axis (RadialCount copies)')
    radial_count: IntProperty(name='RadialCount', min=2, max=64, default=8, get=_rcount_get, set=_rcount_set)
    sdiv: IntProperty(name='SDiv', min=0, max=12, get=_sdiv_get, set=_sdiv_set,
                      description='Subdivision level you sculpt on (Blender Multires Sculpt level)')
    persp: BoolProperty(name='Persp', get=_persp_get, set=_persp_set, description='Perspective view')
    floor: BoolProperty(name='Floor', get=_floor[0], set=_floor[1], description='Show the floor grid')
    polyf: BoolProperty(name='PolyF', get=_polyf_get, set=_polyf_set,
                        description='Show the polygons and polygroups (wireframe + face sets)')
    transp: BoolProperty(name='Transp', get=_transp[0], set=_transp[1], description='See through (X-Ray)')
    double: BoolProperty(name='Double', get=_double[0], set=_double[1],
                         description='Show both sides of faces (Backface Culling off)')
    matcap: EnumProperty(name='Material', items=_matcap_items, get=_matcap_get, set=_matcap_set)
    # stored settings (this file)
    points: IntProperty(name='Points', default=20000, min=200, soft_max=2000000,
                        description='DynaMesh: about how many points the remeshed SubTool gets (Active Points Count)')
    target_polys: FloatProperty(name='Target Polygons Count', default=5.0, min=0.1, soft_max=100.0, precision=1,
                                description='ZRemesher: how many polygons, in thousands (5 = 5,000)')
    keep_creases: BoolProperty(name='KeepCreases', default=True, description='ZRemesher keeps sharp edges')
    keep_border: BoolProperty(name='KeepBorder', default=True, description='ZRemesher keeps open borders')
    decimate: IntProperty(name='% of decimation', default=20, min=1, max=99, subtype='PERCENTAGE',
                          description='Decimate Current keeps this many percent of the polygons')
    inflate: IntProperty(name='Inflate', default=10, min=-100, max=100,
                         description='Deformation: how far Inflate pushes the surface out (minus = in)')
    thick: FloatProperty(name='Thick', default=0.02, min=0.0, soft_max=0.5, precision=3,
                         description='Extract: thickness of the new shell')
    blur: IntProperty(name='Blur', default=2, min=0, max=20, description='Mask By Cavity: how often it is blurred')
    res: IntProperty(name='Res', default=4, min=1, max=64, description='QCube / QGrid resolution')
    fbx_scope: EnumProperty(name='Export', default='SELECTED', items=[
        ('VISIBLE', 'Visible', 'FBX / OBJ / STL export: every visible SubTool'),
        ('SELECTED', 'Selected', 'FBX / OBJ / STL export: the selected SubTool(s)')])


# --- actions ------------------------------------------------------------------------------------------------------

def _mode(context, mode):
    ob = context.active_object
    if ob is not None and ob.mode != mode:
        bpy.ops.object.mode_set(mode=mode)


def switch_to(context, ob):
    """Make ``ob`` the SubTool being sculpted (Sculpt Mode moves to it)."""
    if ob is None or ob.type != 'MESH':
        return False
    if ob.name not in context.view_layer.objects:
        context.view_layer.update()
        if ob.name not in context.view_layer.objects:
            return False
    was = context.mode
    _mode(context, 'OBJECT')
    for o in context.selected_objects:
        o.select_set(False)
    if ob.hide_get():
        ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    if was == 'SCULPT':
        _mode(context, 'SCULPT')
    return True


def _new_object(context, me, name, like=None):
    ob = bpy.data.objects.new(name, me)
    coll = like.users_collection[0] if like is not None and like.users_collection else context.collection
    coll.objects.link(ob)
    if like is not None:
        ob.matrix_world = like.matrix_world.copy()
    return ob


def _bm_edit(context, ob, fn):
    """Run ``fn(bm)`` on the mesh of ``ob`` in Object Mode, then back to Sculpt Mode."""
    import bmesh
    _mode(context, 'OBJECT')
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out = fn(bm)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    _mode(context, 'SCULPT')
    return out


def _split_faces(context, ob, pick, name):
    """New SubTool from the faces ``pick(face)`` says yes to, taken out of ``ob``; the new object or None."""
    import bmesh
    _mode(context, 'OBJECT')
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.index_update()
    bm.faces.index_update()
    take = [f for f in bm.faces if pick(bm, f)]
    if not take or len(take) == len(bm.faces):
        bm.free()
        _mode(context, 'SCULPT')
        return None
    part = bm.copy()
    part.faces.index_update()
    keep_idx = {f.index for f in take}
    bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in keep_idx], context='FACES')
    bmesh.ops.delete(bm, geom=take, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    new_me = bpy.data.meshes.new(ob.name + '_' + name)
    part.to_mesh(new_me)
    part.free()
    for mat in me.materials:
        new_me.materials.append(mat)
    new = _new_object(context, new_me, ob.name + '_' + name, ob)
    _mode(context, 'SCULPT')
    return new


def _face_layer(bm, name):
    return bm.faces.layers.int.get(name)


def _ensure_multires(ob):
    m = multires(ob)
    if m is None:
        m = ob.modifiers.new(MULTIRES, 'MULTIRES')
    return m


def _divide(context, ob, times=1):
    m = _ensure_multires(ob)
    for _i in range(times):
        bpy.ops.object.multires_subdivide(modifier=m.name, mode='CATMULL_CLARK')
    m.sculpt_levels = m.levels = m.total_levels
    return m.total_levels


def dynamesh(context, ob, points):
    from . import voxel_for_points
    if multires(ob) is not None:
        return 'DynaMesh: this SubTool has subdivision levels - Del Higher / Del Lower first'
    v = voxel_for_points(context, ob, points)
    if v <= 0.0:
        return 'DynaMesh: no surface'
    ob.data.remesh_voxel_size = v
    _mode(context, 'OBJECT')                 # (from Object Mode: the Sculpt Mode call crashed without a window)
    bpy.ops.object.voxel_remesh()
    _mode(context, 'SCULPT')
    return ''


def _mask_values(ob):
    import numpy as np
    me = ob.data
    att = me.attributes.get('.sculpt_mask')
    if att is None:
        return np.zeros(len(me.vertices), dtype=np.float32)
    vals = np.empty(len(me.vertices), dtype=np.float32)
    att.data.foreach_get('value', vals)
    return vals


def run(context, action):
    """Do one ZBrush shelf action; '' when fine, else a short report."""
    ob = context.active_object
    zb = context.scene.mch_zb
    if action in TOOLS:
        bpy.ops.wm.tool_set_by_id(name=TOOLS[action])
        return ''
    if action == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT' if context.mode == 'SCULPT' else 'SCULPT')
        return ''
    if ob is None or ob.type != 'MESH':
        return 'Pick a SubTool (mesh) first'
    if action == 'DUPLICATE':
        _mode(context, 'OBJECT')
        new = ob.copy()
        new.data = ob.data.copy()
        for c in ob.users_collection:
            c.objects.link(new)
        context.view_layer.update()
        switch_to(context, new)
        _mode(context, 'SCULPT')
        return f'Duplicate: {new.name}'
    if action == 'DELETE':
        others = [o for o in context.view_layer.objects if o.type == 'MESH' and o != ob and o.visible_get()]
        _mode(context, 'OBJECT')
        bpy.data.objects.remove(ob)
        if others:
            switch_to(context, others[0])
            _mode(context, 'SCULPT')
        return 'Deleted'
    if action in {'SPLIT_MASKED', 'SPLIT_UNMASKED'}:
        vals = _mask_values(ob)
        if not vals.any():
            return 'Split: paint a mask first (Ctrl + drag on the model)'
        hi = action == 'SPLIT_MASKED'
        new = _split_faces(context, ob, lambda bm, f: all((vals[v.index] > 0.5) == hi for v in f.verts),
                           'masked' if hi else 'unmasked')
        return f'Split: {new.name}' if new else 'Split: nothing to take out'
    if action == 'EXTRACT':
        if not _mask_values(ob).any():
            return 'Extract: paint a mask first (Ctrl + drag on the model)'
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.paint_mask_extract(thickness=zb.thick, apply_solidify=zb.thick > 0)
        return 'Extract: new SubTool'
    if action == 'DIVIDE':
        _mode(context, 'SCULPT')
        return f'Divide: SDiv {_divide(context, ob)}'
    if action == 'DEL_HIGHER':
        m = multires(ob)
        if m is None or m.sculpt_levels >= m.total_levels:
            return 'Del Higher: no higher levels'
        bpy.ops.object.multires_higher_levels_delete(modifier=m.name)
        return 'Del Higher'
    if action == 'DEL_LOWER':
        m = multires(ob)
        if m is None:
            return 'Del Lower: no subdivision levels'
        if m.sculpt_levels < m.total_levels:
            return 'Del Lower: go to the highest SDiv first (Blender keeps its base mesh)'
        _mode(context, 'OBJECT')
        m.levels = m.total_levels
        bpy.ops.object.modifier_apply(modifier=m.name)
        _mode(context, 'SCULPT')
        return 'Del Lower: this level is the base now'
    if action in {'SDIV_UP', 'SDIV_DOWN'}:
        m = multires(ob)
        if m is None:
            return 'No subdivision levels (Ctrl+D: Divide)'
        zb.sdiv = m.sculpt_levels + (1 if action == 'SDIV_UP' else -1)
        return f'SDiv {m.sculpt_levels}'
    if action in {'DYNAMESH', 'DYNA_SUBDIV', 'DYNA_SUBDIV3'}:
        msg = dynamesh(context, ob, zb.points)
        if msg:
            return msg
        if action != 'DYNAMESH':
            _divide(context, ob, 3 if action == 'DYNA_SUBDIV3' else 2)
        return f'DynaMesh: {len(ob.data.vertices):,} points'
    if action == 'ZREMESH':
        if multires(ob) is not None:
            return 'ZRemesher: Del Higher / Del Lower first'
        _mode(context, 'OBJECT')
        try:
            bpy.ops.object.quadriflow_remesh(target_faces=max(100, int(zb.target_polys * 1000)),
                                             use_preserve_sharp=zb.keep_creases, use_preserve_boundary=zb.keep_border,
                                             use_mesh_symmetry=bool(zb.sym_x), mode='FACES')
        except RuntimeError as ex:
            _mode(context, 'SCULPT')
            return 'ZRemesher: ' + str(ex).splitlines()[0]
        _mode(context, 'SCULPT')
        return f'ZRemesher: {len(ob.data.polygons):,} polygons'
    if action in {'HALF', 'SAME', 'DOUBLE'}:
        f = {'HALF': 0.5, 'SAME': 1.0, 'DOUBLE': 2.0}[action]
        zb.target_polys = max(0.1, round(len(ob.data.polygons) * f / 1000.0, 1))
        return f'Target Polygons Count {zb.target_polys:g}'
    if action == 'MIRROR':
        def flip(bm):
            for v in bm.verts:
                v.co.x = -v.co.x
            for f in bm.faces:
                f.normal_flip()
        _bm_edit(context, ob, flip)
        return 'Mirror (X)'
    if action == 'MIRROR_WELD':
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.symmetrize()
        return 'Mirror And Weld'
    if action == 'CLOSE_HOLES':
        import bmesh

        def close(bm):
            edges = [e for e in bm.edges if e.is_boundary]
            if edges:
                bmesh.ops.holes_fill(bm, edges=edges, sides=0)
            return len(edges)
        n = _bm_edit(context, ob, close)
        return 'Close Holes' if n else 'Close Holes: no holes'
    if action in {'DEL_HIDDEN', 'SPLIT_HIDDEN'}:
        hidden = ob.data.attributes.get('.hide_poly')
        if hidden is None:
            return 'Nothing hidden (Ctrl+Shift + drag to hide)'
        import numpy as np
        vals = np.zeros(len(ob.data.polygons), dtype=bool)
        hidden.data.foreach_get('value', vals)
        if not vals.any():
            return 'Nothing hidden (Ctrl+Shift + drag to hide)'
        if action == 'SPLIT_HIDDEN':
            new = _split_faces(context, ob, lambda bm, f: bool(vals[f.index]), 'hidden')
            return f'Split Hidden: {new.name}' if new else 'Split Hidden: nothing'
        import bmesh

        def dele(bm):
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if vals[f.index]], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        _bm_edit(context, ob, dele)
        return 'Del Hidden'
    if action == 'INFLATE':
        import numpy as np
        _mode(context, 'OBJECT')
        me = ob.data
        n = len(me.vertices)
        co, nrm = np.empty(n * 3, dtype=np.float32), np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        me.vertices.foreach_get('normal', nrm)
        size = float(np.ptp(co.reshape(-1, 3), axis=0).max()) if n else 0.0
        co += nrm * (zb.inflate / 100.0) * 0.02 * size
        me.vertices.foreach_set('co', co)
        me.update()
        _mode(context, 'SCULPT')
        return f'Inflate {zb.inflate}'
    if action == 'MASK_CAVITY':
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.mask_from_cavity()
        for _i in range(zb.blur):
            bpy.ops.sculpt.mask_filter(filter_type='SMOOTH')
        return 'Mask By Cavity'
    if action == 'MASK_BLUR':
        bpy.ops.sculpt.mask_filter(filter_type='SMOOTH')
        return 'Mask: blur'
    if action == 'MASK_INVERT':
        bpy.ops.paint.mask_flood_fill(mode='INVERT')
        return ''
    if action == 'MASK_CLEAR':
        bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0.0)
        return ''
    if action == 'GROUPS_FROM_MASK':
        bpy.ops.sculpt.face_sets_create(mode='MASKED')
        return 'Polygroup from mask'
    if action == 'AUTO_GROUPS':
        bpy.ops.sculpt.face_sets_init(mode='LOOSE_PARTS')
        return 'Auto Groups'
    if action == 'GROUPS_SPLIT':
        _mode(context, 'OBJECT')
        att = ob.data.attributes.get('.sculpt_face_set')
        if att is None:
            _mode(context, 'SCULPT')
            return 'Groups Split: only one polygroup'
        import numpy as np
        sets = np.zeros(len(ob.data.polygons), dtype=np.int32)
        att.data.foreach_get('value', sets)
        made = 0
        for val in sorted(set(sets.tolist()))[1:]:
            vals = sets.copy()
            if _split_faces(context, ob, lambda bm, f, v=val, s=vals: s[f.index] == v, f'group{val}'):
                made += 1
            _mode(context, 'OBJECT')
            att = ob.data.attributes.get('.sculpt_face_set')
            if att is None:
                break
            sets = np.zeros(len(ob.data.polygons), dtype=np.int32)
            att.data.foreach_get('value', sets)
        _mode(context, 'SCULPT')
        return f'Groups Split: {made} new SubTool(s)' if made else 'Groups Split: only one polygroup'
    if action in {'MERGE_DOWN', 'MERGE_VISIBLE'}:
        meshes = [o for o in sorted(context.view_layer.objects, key=lambda o: o.name.lower())
                  if o.type == 'MESH' and o.visible_get()]
        if action == 'MERGE_DOWN':
            i = meshes.index(ob) if ob in meshes else -1
            others = meshes[i + 1:i + 2] if 0 <= i < len(meshes) - 1 else []
        else:
            others = [o for o in meshes if o != ob]
        if not others:
            return 'Nothing to merge'
        _mode(context, 'OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        for o in others + [ob]:
            o.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.join()
        _mode(context, 'SCULPT')
        return f'Merged {len(others) + 1} SubTools'
    if action in {'ALL_LOW', 'ALL_HIGH'}:
        for o in context.view_layer.objects:
            m = multires(o) if o.type == 'MESH' else None
            if m is not None:
                m.sculpt_levels = m.levels = 0 if action == 'ALL_LOW' else m.total_levels
        return ''
    if action == 'DECIMATE':
        _mode(context, 'OBJECT')
        mod = ob.modifiers.new('MCH_Decimate', 'DECIMATE')
        mod.ratio = zb.decimate / 100.0
        bpy.ops.object.modifier_apply(modifier=mod.name)
        _mode(context, 'SCULPT')
        return f'Decimate: {len(ob.data.polygons):,} polygons'
    if action in {'CHECK_MESH', 'FIX_MESH'}:
        import bmesh

        def check(bm):
            loose = [v for v in bm.verts if not v.link_faces]
            bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
            if action == 'FIX_MESH':
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
                bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            return len(loose), len(bad)
        loose, bad = _bm_edit(context, ob, check)
        if action == 'CHECK_MESH':
            return f'Check Mesh: {loose} loose points, {bad} bad edges' if loose or bad else 'Check Mesh: clean'
        return 'Fix Mesh: done'
    if action == 'POLYMESH3D':
        _mode(context, 'OBJECT')
        for mod in list(ob.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:
                pass
        _mode(context, 'SCULPT')
        return 'Make PolyMesh3D'
    if action == 'SWITCH_COLOR':
        bpy.ops.paint.brush_colors_flip()
        return ''
    if action == 'FILL_COLOR':
        import numpy as np
        _mode(context, 'OBJECT')
        me = ob.data
        att = me.color_attributes.active_color or me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
        u = unified(context)
        col = (u.color if u is not None and u.use_unified_color else brush(context).color)
        n = len(att.data)
        att.data.foreach_set('color', np.tile(np.array([col[0], col[1], col[2], 1.0], dtype=np.float32), n))
        me.update()
        _mode(context, 'SCULPT')
        return 'FillColor'
    if action == 'SYM_X':
        zb.sym_x = not zb.sym_x
        return f'Symmetry X {"on" if zb.sym_x else "off"}'
    if action == 'POLYF':
        zb.polyf = not zb.polyf
        return ''
    if action == 'FRAME':
        bpy.ops.view3d.view_selected()
        return ''
    if action == 'SOLO':
        bpy.ops.view3d.localview()
        return ''
    if action in {'QCUBE', 'QGRID'}:
        return append(context, 'QCUBE' if action == 'QCUBE' else 'QGRID')
    if action == 'POLISH_GROUPS':
        try:
            bpy.ops.sculpt.mesh_filter(type='RELAX_FACE_SETS', strength=0.5, iteration_count=4)
        except (RuntimeError, TypeError) as ex:
            return 'Polish By Groups: ' + str(ex).splitlines()[0]
        return 'Polish By Groups'
    if action in {'EXPORT_OBJ', 'EXPORT_STL', 'FBX_EXPORT', 'FBX_IMPORT'}:
        _mode(context, 'OBJECT')
        sel = zb.fbx_scope == 'SELECTED'
        try:
            if action == 'EXPORT_OBJ':
                bpy.ops.wm.obj_export('INVOKE_DEFAULT', export_selected_objects=sel)
            elif action == 'EXPORT_STL':
                bpy.ops.wm.stl_export('INVOKE_DEFAULT', export_selected_objects=sel)
            elif action == 'FBX_EXPORT':
                bpy.ops.export_scene.fbx('INVOKE_DEFAULT', use_selection=sel)
            else:
                bpy.ops.import_scene.fbx('INVOKE_DEFAULT')
        except (RuntimeError, AttributeError) as ex:
            return str(ex).splitlines()[0]
        return ''
    return f'Unknown action {action}'


PRIMITIVES = (('SPHERE', 'Sphere3D'), ('CUBE', 'Cube3D'), ('CYLINDER', 'Cylinder3D'), ('CONE', 'Cone3D'),
              ('TORUS', 'Ring3D'), ('QCUBE', 'QCube'), ('QGRID', 'QGrid'))


def append(context, kind='SPHERE'):
    """A new SubTool at the 3D cursor (IMM Primitives / Append / QCube / QGrid), sculpted right away."""
    if context.active_object is not None:
        _mode(context, 'OBJECT')
    zb = context.scene.mch_zb
    loc = context.scene.cursor.location
    size = 1.0
    ref = context.active_object
    if ref is not None and ref.type == 'MESH':
        size = max(ref.dimensions) * 0.5 or 1.0
    if kind == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size * 0.5, segments=48, ring_count=24, location=loc)
    elif kind == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    elif kind == 'CYLINDER':
        bpy.ops.mesh.primitive_cylinder_add(radius=size * 0.3, depth=size, vertices=32, location=loc)
    elif kind == 'CONE':
        bpy.ops.mesh.primitive_cone_add(radius1=size * 0.4, depth=size, vertices=32, location=loc)
    elif kind == 'TORUS':
        bpy.ops.mesh.primitive_torus_add(major_radius=size * 0.4, minor_radius=size * 0.12, location=loc)
    elif kind == 'QCUBE':
        bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
        import bmesh
        ob = context.active_object
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        if zb.res > 1:
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=zb.res - 1, use_grid_fill=True)
        bm.to_mesh(ob.data)
        bm.free()
    elif kind == 'QGRID':
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=zb.res + 1, y_subdivisions=zb.res + 1, size=size,
                                        location=loc)
    new = context.active_object
    new.name = dict(PRIMITIVES).get(kind, kind.title())
    _mode(context, 'SCULPT')
    return f'Append: {new.name}'


# --- operators ------------------------------------------------------------------------------------------------------

class _ZBPoll:
    @classmethod
    def poll(cls, context):
        return on(context)


class MCH_OT_zb_action(_ZBPoll, bpy.types.Operator):
    """ZBrush shelf action on the SubTool (Blender equivalent in the tooltip of each button)"""
    bl_idname = 'mch.zb_action'
    bl_label = 'ZBrush Action'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    action: StringProperty()

    def execute(self, context):
        try:
            msg = run(context, self.action)
        except RuntimeError as ex:
            msg = str(ex).splitlines()[0]
        if msg:
            self.report({'INFO'}, msg)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_brush(_ZBPoll, bpy.types.Operator):
    """Pick this brush (a Blender Essentials brush under its ZBrush name)"""
    bl_idname = 'mch.zb_brush'
    bl_label = 'ZBrush Brush'
    bl_options = {'REGISTER', 'INTERNAL'}
    name: StringProperty()

    def execute(self, context):
        msg = activate(context, self.name)
        if msg:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        close_popup(context)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_append(_ZBPoll, bpy.types.Operator):
    """Append a new SubTool (IMM Primitives)"""
    bl_idname = 'mch.zb_append'
    bl_label = 'Append SubTool'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=[(k, n, '') for k, n in PRIMITIVES], default='SPHERE')

    def execute(self, context):
        self.report({'INFO'}, append(context, self.kind))
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_subtool(_ZBPoll, bpy.types.Operator):
    """Sculpt this SubTool"""
    bl_idname = 'mch.zb_subtool'
    bl_label = 'Pick SubTool'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()

    def execute(self, context):
        if not switch_to(context, bpy.data.objects.get(self.name)):
            return {'CANCELLED'}
        _bump()
        return {'FINISHED'}


def _bump():
    try:
        from . import ui_bars
        ui_bars.bump()
    except ImportError:
        pass


# --- mouse: sculpt on the model, navigate on the canvas -----------------------------------------------------------

def stroke_kwargs(kind):
    """sculpt.brush_stroke arguments for a ZBrush mouse action (Blender 5.2 has a brush switch for the stroke;
    5.0: mode SMOOTH, the mask by a tool switch)."""
    rna = bpy.ops.sculpt.brush_stroke.get_rna_type().properties
    kw = {'ignore_background_click': True} if 'ignore_background_click' in rna else {}
    toggle = 'brush_toggle' in rna
    if kind == 'ZSUB':
        kw['mode'] = 'INVERT'
    elif kind == 'SMOOTH':
        if toggle:
            kw['brush_toggle'] = 'SMOOTH'
        else:
            kw['mode'] = 'SMOOTH'
    elif kind in {'MASK', 'UNMASK'}:
        if toggle:
            kw['brush_toggle'] = 'MASK'
            if kind == 'UNMASK':
                kw['mode'] = 'INVERT'
        elif kind == 'UNMASK':
            kw['mode'] = 'INVERT'
    return kw, toggle


def plan(ctrl, shift, alt):
    """(on the model, on the canvas) for a left press with these keys - the ZBrush mouse."""
    if ctrl and shift:
        return ('GROUP_SOLO', 'SHOW_ALL_OR_HIDE_INSIDE' if alt else 'SHOW_ALL_OR_SHOW_INSIDE')
    if ctrl:
        return ('UNMASK', 'INVERT_OR_UNMASK_LASSO') if alt else ('MASK', 'INVERT_OR_MASK_LASSO')
    if alt:
        return 'ZSUB', 'PAN'
    if shift:
        return 'SMOOTH', 'ROTATE_SNAP'
    return 'STROKE', 'ROTATE'


class MCH_OT_zb_press(_ZBPoll, bpy.types.Operator):
    """ZBrush mouse: on the model it sculpts (Alt Zsub, Shift Smooth, Ctrl mask), on the canvas it turns / moves
    the view, Ctrl+click inverts the mask, Ctrl+Shift shows / hides"""
    bl_idname = 'mch.zb_press'
    bl_label = 'ZBrush Mouse'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        try:
            from . import ui_bars
            inside, _it = ui_bars.hit(context, event.mouse_region_x, event.mouse_region_y)
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
            inside = False
        if inside:
            return bpy.ops.mch.quick_hud_press('INVOKE_DEFAULT')
        if popup_open(context):
            close_popup(context)
            return {'FINISHED'}
        model, canvas = plan(event.ctrl, event.shift, event.alt)
        if model == 'GROUP_SOLO':
            r = bpy.ops.sculpt.face_set_change_visibility('INVOKE_DEFAULT', mode='TOGGLE')
            if 'FINISHED' in r:
                return {'FINISHED'}
        elif model == 'STROKE':
            r = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', **stroke_kwargs('STROKE')[0])
            if 'RUNNING_MODAL' in r or 'FINISHED' in r:
                return {'FINISHED'}
        else:
            kw, toggle = stroke_kwargs(model)
            swapped = None
            if model in {'MASK', 'UNMASK'} and not toggle:      # Blender 5.0: the Mask tool for this stroke
                swapped = _tool_id(context)
                bpy.ops.wm.tool_set_by_id(name='builtin_brush.mask')
                bpy.ops.mch.zb_restore_tool('INVOKE_DEFAULT', tool=swapped)
            r = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', **kw)
            if 'RUNNING_MODAL' in r or 'FINISHED' in r:
                return {'FINISHED'}
            if swapped:
                bpy.ops.wm.tool_set_by_id(name=swapped)
        # the canvas
        if canvas in {'ROTATE', 'ROTATE_SNAP', 'PAN'}:
            return bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode='PAN' if canvas == 'PAN' else 'ROTATE')
        self.canvas, self.x0, self.y0 = canvas, event.mouse_region_x, event.mouse_region_y
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if abs(event.mouse_region_x - self.x0) + abs(event.mouse_region_y - self.y0) > 5:
                if self.canvas.startswith('INVERT_OR'):
                    bpy.ops.paint.mask_lasso_gesture('INVOKE_DEFAULT', mode='VALUE',
                                                     value=0.0 if 'UNMASK' in self.canvas else 1.0)
                else:
                    bpy.ops.paint.hide_show_lasso_gesture(
                        'INVOKE_DEFAULT', action='HIDE', area='INSIDE' if 'HIDE_INSIDE' in self.canvas else 'OUTSIDE')
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self.canvas.startswith('INVERT_OR'):
                bpy.ops.paint.mask_flood_fill(mode='INVERT')
            else:
                bpy.ops.paint.hide_show_all(action='SHOW')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


def _tool_id(context):
    try:
        return context.workspace.tools.from_space_view3d_mode('SCULPT').idname
    except (AttributeError, RuntimeError):
        return 'builtin.brush'


class MCH_OT_zb_restore_tool(bpy.types.Operator):
    """(Blender 5.0) back to the brush after a Ctrl mask stroke: the first event after the stroke"""
    bl_idname = 'mch.zb_restore_tool'
    bl_label = 'Restore Tool'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='builtin.brush')

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'TIMER', 'TIMER_REPORT', 'NONE'}:
            return {'PASS_THROUGH'}
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool or 'builtin.brush')
        except RuntimeError:
            pass
        return {'FINISHED', 'PASS_THROUGH'}


def snap_rotation(q):
    """The nearest of the 24 square-on view rotations (front / side / top ... with an upright up)."""
    m = q.to_matrix()
    best, best_d = None, -9.0
    axes = [Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, 1)),
            Vector((0, 0, -1))]
    z = m.col[2]
    y = m.col[1]
    for a in axes:
        for b in axes:
            if abs(a.dot(b)) > 0.5:
                continue
            d = a.dot(z) + b.dot(y)
            if d > best_d:
                best_d, best = d, (a, b)
    zc, yc = best
    xc = yc.cross(zc)
    return Matrix((xc, yc, zc)).transposed().to_quaternion()


class MCH_OT_zb_nav(_ZBPoll, bpy.types.Operator):
    """ZBrush canvas drag: rotate (Shift: snap square-on), Alt: move, let Alt go while dragging: zoom"""
    bl_idname = 'mch.zb_nav'
    bl_label = 'ZBrush Navigate'
    bl_options = {'INTERNAL', 'BLOCKING'}
    mode: EnumProperty(items=[('ROTATE', 'Rotate', ''), ('PAN', 'Move', ''), ('ZOOM', 'Zoom', '')], default='ROTATE')

    def invoke(self, context, event):
        rv3d = getattr(context, 'region_data', None)
        if rv3d is None:
            return {'CANCELLED'}
        self.rv3d = rv3d
        self.start = (rv3d.view_rotation.copy(), rv3d.view_location.copy(), rv3d.view_distance)
        self.last = (event.mouse_x, event.mouse_y)
        self.alt_pan = self.mode == 'PAN' and event.alt
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        rv3d = self.rv3d
        if event.type == 'MOUSEMOVE':
            dx, dy = event.mouse_x - self.last[0], event.mouse_y - self.last[1]
            self.last = (event.mouse_x, event.mouse_y)
            if self.mode == 'PAN' and self.alt_pan and not event.alt:
                self.mode = 'ZOOM'                         # ZBrush: let Alt go while dragging = zoom
            if self.mode == 'ROTATE':
                q = rv3d.view_rotation
                up = q @ Vector((0, 1, 0))
                right = q @ Vector((1, 0, 0))
                s = 0.006
                q = Quaternion(up, -dx * s) @ Quaternion(right, dy * s) @ q
                rv3d.view_rotation = snap_rotation(q) if event.shift else q.normalized()
            elif self.mode == 'PAN':
                q = rv3d.view_rotation
                scale = rv3d.view_distance * 2.0 / max(1, context.region.height)
                rv3d.view_location -= (q @ Vector((1, 0, 0))) * dx * scale + (q @ Vector((0, 1, 0))) * dy * scale
            else:
                rv3d.view_distance = max(1e-4, rv3d.view_distance * math.exp(-dy * 0.006))
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            rv3d.view_rotation, rv3d.view_location, rv3d.view_distance = self.start
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_zb_viewdrag(_ZBPoll, bpy.types.Operator):
    """Drag on Move / Zoom3D / Rotate (right shelf) to move the view"""
    bl_idname = 'mch.zb_viewdrag'
    bl_label = 'View Drag'
    bl_options = {'INTERNAL'}
    mode: EnumProperty(items=[('ROTATE', 'Rotate', ''), ('PAN', 'Move', ''), ('ZOOM', 'Zoom', '')], default='ROTATE')

    def invoke(self, context, event):
        return bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode=self.mode)


# --- the menu at the cursor (Space / S / U / O / right-click) and the brush picker (B) -----------------------------

def popup_open(context):
    return bool(getattr(context.window_manager, 'mch_zb_pop', ''))


def close_popup(context):
    wm = context.window_manager
    if getattr(wm, 'mch_zb_pop', ''):
        wm.mch_zb_pop = ''
        _bump()


class MCH_OT_zb_popup(_ZBPoll, bpy.types.Operator):
    """ZBrush menu at the cursor: Draw Size / Focal Shift / Z Intensity, Zadd / Zsub, Stroke, recent brushes"""
    bl_idname = 'mch.zb_popup'
    bl_label = 'ZBrush Menu'
    bl_options = {'INTERNAL'}
    focus: StringProperty(default='')
    kind: StringProperty(default='MENU')

    def invoke(self, context, event):
        wm = context.window_manager
        if wm.mch_zb_pop == self.kind and not self.focus:
            wm.mch_zb_pop = ''
        else:
            wm.mch_zb_pop = self.kind
            wm.mch_zb_pop_xy = (event.mouse_region_x, event.mouse_region_y)
            wm.mch_zb_pop_focus = self.focus
        _bump()
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_zb_brush_pick(_ZBPoll, bpy.types.Operator):
    """B: the brushes at the cursor - type the letters (B S T = Standard) or click one; Esc closes"""
    bl_idname = 'mch.zb_brush_pick'
    bl_label = 'ZBrush Brushes'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.mch_zb_pop = 'BRUSH'
        wm.mch_zb_pop_xy = (event.mouse_region_x, event.mouse_region_y)
        wm.mch_zb_pop_focus = ''
        _bump()
        self.typed = ''
        context.window_manager.modal_handler_add(self)
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager
        if wm.mch_zb_pop != 'BRUSH':
            return {'FINISHED'}
        if event.value != 'PRESS':
            return {'PASS_THROUGH'}
        if event.type == 'ESC':
            close_popup(context)
            return {'FINISHED'}
        if len(event.type) == 1 and event.type.isalpha():
            self.typed += event.type
            hits = [z for z, _bl, code in BRUSHES if code.startswith(self.typed)]
            wm.mch_zb_pop_focus = self.typed
            if len(hits) == 1:
                activate(context, hits[0])
                close_popup(context)
                self.report({'INFO'}, hits[0])
                return {'FINISHED'}
            if not hits:
                self.typed = ''
                wm.mch_zb_pop_focus = ''
            _bump()
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MCH_OT_zb_close(bpy.types.Operator):
    """Close the ZBrush menu"""
    bl_idname = 'mch.zb_close'
    bl_label = 'Close ZBrush Menu'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return on(context) and popup_open(context)

    def execute(self, context):
        close_popup(context)
        return {'FINISHED'}


CLASSES = (MCH_PG_ZBrush, MCH_OT_zb_action, MCH_OT_zb_brush, MCH_OT_zb_append, MCH_OT_zb_subtool, MCH_OT_zb_press,
           MCH_OT_zb_restore_tool, MCH_OT_zb_nav, MCH_OT_zb_viewdrag, MCH_OT_zb_popup, MCH_OT_zb_brush_pick,
           MCH_OT_zb_close)
_keymaps = []

# (key, ctrl, shift, alt, operator, properties)
KEYS = (
    ('LEFTMOUSE', False, False, False, 'mch.zb_press', {}), ('LEFTMOUSE', False, True, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', False, False, True, 'mch.zb_press', {}), ('LEFTMOUSE', True, False, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', True, False, True, 'mch.zb_press', {}), ('LEFTMOUSE', True, True, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', True, True, True, 'mch.zb_press', {}),
    ('SPACE', False, False, False, 'mch.zb_popup', {}), ('RIGHTMOUSE', False, False, False, 'mch.zb_popup', {}),
    ('S', False, False, False, 'mch.zb_popup', {'focus': 'draw_size'}),
    ('U', False, False, False, 'mch.zb_popup', {'focus': 'z_intensity'}),
    ('O', False, False, False, 'mch.zb_popup', {'focus': 'focal_shift'}),
    ('B', False, False, False, 'mch.zb_brush_pick', {}), ('ESC', False, False, False, 'mch.zb_close', {}),
    ('X', False, False, False, 'mch.zb_action', {'action': 'SYM_X'}),
    ('D', False, False, False, 'mch.zb_action', {'action': 'SDIV_UP'}),
    ('D', False, True, False, 'mch.zb_action', {'action': 'SDIV_DOWN'}),
    ('D', True, False, False, 'mch.zb_action', {'action': 'DIVIDE'}),
    ('W', True, False, False, 'mch.zb_action', {'action': 'GROUPS_FROM_MASK'}),
    ('F', False, False, False, 'mch.zb_action', {'action': 'FRAME'}),
    ('F', False, True, False, 'mch.zb_action', {'action': 'POLYF'}),
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_zb = bpy.props.PointerProperty(type=MCH_PG_ZBrush)
    wmt = bpy.types.WindowManager
    wmt.mch_zb_pop = StringProperty(default='', options={'SKIP_SAVE'})
    wmt.mch_zb_pop_xy = bpy.props.FloatVectorProperty(size=2, default=(0.0, 0.0), options={'SKIP_SAVE'})
    wmt.mch_zb_pop_focus = StringProperty(default='', options={'SKIP_SAVE'})
    wmt.mch_zb_scroll = FloatProperty(default=0.0, options={'SKIP_SAVE'})
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='Sculpt', space_type='EMPTY')
        for key, ctrl, shift, alt, op, props in KEYS:
            kmi = km.keymap_items.new(op, key, 'PRESS', ctrl=ctrl, shift=shift, alt=alt)
            for k, v in props.items():
                setattr(kmi.properties, k, v)
            _keymaps.append((km, kmi))


def unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _keymaps.clear()
    wmt = bpy.types.WindowManager
    for name in ('mch_zb_pop', 'mch_zb_pop_xy', 'mch_zb_pop_focus', 'mch_zb_scroll'):
        if hasattr(wmt, name):
            delattr(wmt, name)
    if hasattr(bpy.types.Scene, 'mch_zb'):
        del bpy.types.Scene.mch_zb
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
