"""Station Primitive (Advanced Parametric Primitive) - Blender side.

The object's mesh is always a real mesh rebuilt from the parameters (no
Geometry Nodes): Cut / Split / Boolean can use it directly.  Cutting it
freezes the parameters (the cut would be overwritten by the next rebuild);
the report says so.  Apply = freeze and drop the live editing.
"""
import bmesh
import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty, StringProperty)
from mathutils import Matrix, Vector

from . import station_sweep as ss

ROLE = 'MCH_STATION_PRIMITIVE'
SHELL_MOD = 'MCH_StationShell'
_building = set()
FRAMES = {}          # object name -> station frames (P, X, T, Z) in object space, for the handles


def station_frames(ob):
    if ob.name not in FRAMES:
        r = ss.build(spec_of(ob))
        FRAMES[ob.name] = [(tuple(f.P), tuple(f.X), tuple(f.T), tuple(f.Z)) for f in r['frames']]
    return FRAMES[ob.name]


def _rebuild_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and getattr(ob, 'mch_station', None) and ob.mch_station.live:
        rebuild(ob)


def _fp(name, default, **kw):
    return FloatProperty(name=name, default=default, update=_rebuild_update, **kw)


class MCH_PG_Station(bpy.types.PropertyGroup):
    length: _fp('Length', 1.0, min=0.0, soft_max=10.0, unit='LENGTH', description='Straight run after the bend')
    bend_angle: _fp('Bend', 0.0, soft_min=-180, soft_max=180, min=-360, max=360,
                    description='Bend at the start of this segment, from the direction the previous one ended in')
    bend_dir: _fp('Bend Direction', 0.0, soft_min=-180, soft_max=180,
                  description='Which way the bend turns, around the path: 0 = up, 90 = right, 180 = down')
    bend_up: _fp('Up / Down', 0.0, soft_min=-180, soft_max=180, min=-360, max=360,
                 description='Bend up (+) or down (-) at the start of this segment; works together with Left / Right')
    bend_side: _fp('Left / Right', 0.0, soft_min=-180, soft_max=180, min=-360, max=360,
                   description='Bend right (+) or left (-) at the start of this segment; works together with Up / Down')
    bend_radius: _fp('Radius', 0.0, min=0.0, soft_max=5.0, unit='LENGTH',
                     description='0 = hard fold (sharp crease). > 0 = smooth bend; large angles wrap around')
    twist: _fp('Twist', 0.0, soft_min=-360, soft_max=360, description='Twist of the profile along this segment')
    world: BoolProperty(name='World Direction', default=False, update=_rebuild_update,
                        description='Point this segment at an absolute direction (Yaw / Pitch) instead of bending '
                                    'relative to the previous segment')
    yaw: _fp('Yaw', 0.0, soft_min=-180, soft_max=180)
    pitch: _fp('Pitch', 0.0, soft_min=-90, soft_max=90)
    width_l: _fp('Left Width', 0.5, min=0.0005, soft_max=5.0, unit='LENGTH')
    width_r: _fp('Right Width', 0.5, min=0.0005, soft_max=5.0, unit='LENGTH')
    height_top: _fp('Top', 0.05, min=0.0, soft_max=3.0, unit='LENGTH')
    height_bot: _fp('Bottom', 0.05, min=0.0, soft_max=3.0, unit='LENGTH')
    thick_l: _fp('Left Thickness', 1.0, min=0.0, soft_max=4.0, description='Thickness factor at the left edge')
    thick_r: _fp('Right Thickness', 1.0, min=0.0, soft_max=4.0, description='Thickness factor at the right edge')
    corner_l: _fp('Left Corner', 0.02, min=0.0, soft_max=1.0, unit='LENGTH')
    corner_r: _fp('Right Corner', 0.02, min=0.0, soft_max=1.0, unit='LENGTH')
    ridge_h: _fp('Ridge Height', 0.0, soft_min=-0.5, soft_max=0.5, unit='LENGTH')
    ridge_w: _fp('Ridge Width', 0.15, min=0.001, soft_max=2.0, unit='LENGTH')
    ridge_offset: _fp('Ridge Offset', 0.0, soft_min=-2.0, soft_max=2.0, unit='LENGTH')
    bend_style: EnumProperty(name='Bend Style', items=[
        ('AUTO', 'Auto', 'Radius 0 = sharp fold, radius > 0 = band'),
        ('FOLD', 'Fold', 'Sharp crease (mitred, thickness kept)'),
        ('TIGHT', 'Tight', 'Almost a right angle: the smallest radius that does not fold the inside onto itself'),
        ('BAND', 'Band', 'Smooth band with the Radius below')], default='AUTO', update=_rebuild_update)
    profile: EnumProperty(name='Profile Here', items=[
        ('INHERIT', 'Same as primitive', 'Use the primitive profile'),
        ('ROUNDED', 'Rounded Box', ''), ('CHAMFER', 'Chamfered Box', ''), ('BOX', 'Flat Box', ''),
        ('RIBBON', 'Ribbon', ''), ('ROUND', 'Round / Oval', ''), ('CAPSULE', 'Capsule', ''),
        ('POLYGON', 'Polygon', ''), ('ARC', 'Curved Plate (armor)', '')], default='INHERIT',
        update=_rebuild_update,
        description='Profile at this station; the segment before it morphs from the previous profile')
    interp: EnumProperty(name='Blend', items=[('LINEAR', 'Linear', 'Even change from the previous station'),
                                               ('SMOOTH', 'Smooth', 'Eased change (more segments)'),
                                               ('STEP', 'Step', 'Sharp change at this station')],
                         default='LINEAR', update=_rebuild_update)


class MCH_PG_StationPrimitive(bpy.types.PropertyGroup):
    live: BoolProperty(name='Live', default=False)
    kind: EnumProperty(name='Profile', items=[
        ('ROUNDED', 'Rounded Box', ''), ('CHAMFER', 'Chamfered Box', ''), ('BOX', 'Flat Box', ''),
        ('RIBBON', 'Ribbon', ''), ('ROUND', 'Round / Oval', ''), ('CAPSULE', 'Capsule', ''),
        ('POLYGON', 'Polygon', ''),
        ('ARC', 'Curved Plate (armor)', 'Curved shell: Top = crown height, Bottom = plate thickness'),
        ('NGON', 'Polygon Prism', 'Exactly N corners (Sides): clean folds and bands at any number of sides')],
        default='ROUNDED', update=_rebuild_update)
    sides: IntProperty(name='Sides', default=6, min=3, max=64, update=_rebuild_update,
                       description='Polygon sides: 4 = square ... 64 = almost a cylinder')
    corner_finish: EnumProperty(name='Side Edges', items=[('NONE', 'Sharp', ''), ('BEVEL', 'Bevel', ''),
                                                          ('CHAMFER', 'Chamfer', '')], default='NONE',
                                update=_rebuild_update,
                                description='Finish of the edges running along the primitive (polygon corners)')
    corner_width: _fp('Side Edge Width', 0.03, min=0.0, soft_max=0.5, unit='LENGTH')
    corner_segments: IntProperty(name='Side Edge Segments', default=3, min=1, max=16, update=_rebuild_update)
    cap_finish: EnumProperty(name='End Edges', items=[('NONE', 'Sharp', ''), ('BEVEL', 'Bevel', ''),
                                                      ('CHAMFER', 'Chamfer', '')], default='NONE',
                             update=_rebuild_update, description='Finish of the rim edges of the two flat ends')
    cap_width: _fp('End Edge Width', 0.03, min=0.0, soft_max=0.5, unit='LENGTH')
    cap_segments: IntProperty(name='End Edge Segments', default=3, min=1, max=16, update=_rebuild_update)
    ridge: EnumProperty(name='Ridge', items=[
        ('NONE', 'None', ''), ('CREASE', 'Center Crease', 'Sharp centre edge (roof)'),
        ('RAISED', 'Raised Ridge', 'Triangular ridge'), ('BOX', 'Box Ridge', 'Square ridge'),
        ('ROUND', 'Rounded Ridge', ''), ('GROOVE', 'Recessed Groove', 'Square groove'),
        ('DOUBLE', 'Double Ridge', 'Two parallel ridges')], default='NONE', update=_rebuild_update)
    res: IntProperty(name='Profile Resolution', default=8, min=2, max=48, update=_rebuild_update)
    quality: EnumProperty(name='Bend Segments', items=[('DRAFT', 'Draft', '15 deg'), ('NORMAL', 'Normal', '8 deg'),
                                                      ('FINE', 'Fine', '4 deg')], default='NORMAL',
                          update=_rebuild_update)
    seg_mode: EnumProperty(name='Segments', items=[('AUTO', 'Auto', 'From angle, twist and blending'),
                                                   ('MANUAL', 'Manual', '')], default='AUTO', update=_rebuild_update)
    seg_bend: IntProperty(name='Bend Segments', default=8, min=1, max=128, update=_rebuild_update)
    seg_run: IntProperty(name='Run Segments', default=1, min=1, max=128, update=_rebuild_update)
    cap_start: EnumProperty(name='Start', items=[(c, c.title(), '') for c in ss.CAPS], default='FLAT',
                            update=_rebuild_update)
    cap_end: EnumProperty(name='End', items=[(c, c.title(), '') for c in ss.CAPS], default='FLAT',
                          update=_rebuild_update)
    cap_len: _fp('Cap Length', 0.3, min=0.0, soft_max=3.0, unit='LENGTH')
    shell: _fp('Shell Thickness', 0.0, min=0.0, soft_max=0.5, unit='LENGTH',
               description='> 0: hollow shell (live Solidify), e.g. ducts and helmet shells')
    stations: CollectionProperty(type=MCH_PG_Station)
    active: IntProperty(name='Active Station', default=1, min=0)
    show_asym: BoolProperty(name='Asymmetry', default=False)
    sym_lr: BoolProperty(name='Left = Right', default=False, update=_rebuild_update,
                         description='Profile symmetric: right width / thickness / corner follow the left values')
    show_adv: BoolProperty(name='Advanced', default=False)
    warnings: StringProperty(default='')


def _station_dict(st):
    return {k: getattr(st, k) for k in ss.STATION_KEYS}


def spec_of(ob):
    p = ob.mch_station
    sts = [_station_dict(s) for s in p.stations]
    if p.sym_lr:
        for d in sts:
            d['width_r'], d['thick_r'], d['corner_r'] = d['width_l'], d['thick_l'], d['corner_l']
    return dict(kind=p.kind, sides=p.sides, ridge=p.ridge, res=p.res, quality=p.quality, seg_mode=p.seg_mode,
                seg_bend=p.seg_bend, seg_run=p.seg_run, cap_start=p.cap_start, cap_end=p.cap_end,
                cap_len=p.cap_len, stations=sts)


TAG_SIDE, TAG_END = 1, 2


def edge_tag(u, v, n, rings):
    """Which finish an edge between generated vertices u, v gets: TAG_SIDE =
    runs along the primitive (polygon corner lines), TAG_END = rim of the
    first / last ring, 0 = other.  Ring vertices come first: ring r, slot j =
    r * n + j."""
    total = n * rings
    if u >= total or v >= total or n < 3:
        return 0
    if abs(u - v) == n:
        return TAG_SIDE
    ru, rv = u // n, v // n
    if ru == rv and ru in (0, rings - 1) and (abs(u - v) == 1 or abs(u - v) == n - 1):
        return TAG_END
    return 0


def _finish(bm, layer, tag, mode, width, segments):
    if mode == 'NONE' or width <= 0:
        return 0
    edges = [e for e in bm.edges if e[layer] == tag and e.is_manifold and e.calc_face_angle(0.0) > 0.02]
    if not edges:
        return 0
    bmesh.ops.bevel(bm, geom=edges + list({v for e in edges for v in e.verts}), offset=width,
                    offset_type='OFFSET', segments=1 if mode == 'CHAMFER' else max(1, segments), profile=0.5,
                    affect='EDGES', clamp_overlap=True, loop_slide=True)
    return len(edges)


def _write_mesh(me, result, p=None):
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(v) for v in result['verts']]
        for f in result['faces']:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:          # duplicate face from a collapsed corner
                pass
        bm.verts.index_update()
        layer = bm.edges.layers.int.new('mch_finish')
        n, rings = result.get('ring_size', 0), result.get('ring_count', 0)
        for e in bm.edges:
            e[layer] = edge_tag(e.verts[0].index, e.verts[1].index, n, rings)
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if p is not None:
            # 0.15: Bevel / Chamfer of the side edges (polygon corners) and of the end rims
            _finish(bm, layer, TAG_SIDE, p.corner_finish, p.corner_width, p.corner_segments)
            _finish(bm, layer, TAG_END, p.cap_finish, p.cap_width, p.cap_segments)
            bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        bm.edges.layers.int.remove(layer)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:              # hard folds / corners stay crisp, curves stay smooth
            e.smooth = not (e.is_manifold and e.calc_face_angle(0.0) > 0.52)
        nm = sum(1 for e in bm.edges if not e.is_manifold)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return nm


def rebuild(ob):
    if ob.name in _building:
        return
    _building.add(ob.name)
    try:
        p = ob.mch_station
        result = ss.build(spec_of(ob))
        _write_mesh(ob.data, result, p)
        FRAMES[ob.name] = [(tuple(f.P), tuple(f.X), tuple(f.T), tuple(f.Z)) for f in result['frames']]
        warn = list(result['warnings'])
        p.warnings = ' | '.join(warn)
        mod = ob.modifiers.get(SHELL_MOD)
        if p.shell > 0:
            if mod is None:
                mod = ob.modifiers.new(SHELL_MOD, 'SOLIDIFY')
            mod.thickness = p.shell
            mod.offset = -1.0
            mod.use_even_offset = True
        elif mod is not None:
            ob.modifiers.remove(mod)
    finally:
        _building.discard(ob.name)


def is_live(ob):
    return ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_station', None) is not None and \
        ob.mch_station.live


def freeze(ob):
    """Stop rebuilding (before a destructive edit such as Cut).  Returns True when it was live."""
    if is_live(ob):
        ob.mch_station.live = False
        return True
    return False


def active_station_primitive(context):
    ob = context.active_object
    return ob if is_live(ob) else None


def migrate_bend(st):
    """Older 'Bend + Direction' -> Up / Down + Left / Right (same shape)."""
    import math
    if abs(st.bend_angle) > 1e-9:
        phi = math.radians(st.bend_dir)
        st.bend_up = st.bend_up + st.bend_angle * math.cos(phi)
        st.bend_side = st.bend_side + st.bend_angle * math.sin(phi)
        st.bend_angle = 0.0
        return True
    return False


def migrate_object(ob):
    p = ob.mch_station
    live = p.live
    p.live = False
    changed = [migrate_bend(st) for st in p.stations]
    p.live = live
    if live and any(changed):
        rebuild(ob)
    return any(changed)


@bpy.app.handlers.persistent
def _migrate_on_load(_dummy=None):
    for ob in bpy.data.objects:
        if is_live(ob):
            migrate_object(ob)


def total_bend(st):
    """(up, side) in degrees, the older angle + direction included."""
    import math
    phi = math.radians(st.bend_dir)
    return (st.bend_up + st.bend_angle * math.cos(phi), st.bend_side + st.bend_angle * math.sin(phi))


def create(context, preset='PANEL'):
    spec = ss.preset(preset)
    me = bpy.data.meshes.new('MCH_Station_' + preset.title())
    ob = bpy.data.objects.new('MCH_' + preset.title().replace('_', ''), me)
    context.collection.objects.link(ob)
    ob.matrix_world = Matrix.Translation(context.scene.cursor.location)
    ob['mch_role'] = ROLE
    p = ob.mch_station
    p.live = False                      # fill without rebuilding on every field
    for key in ('kind', 'ridge', 'res', 'sides', 'cap_start', 'cap_end', 'cap_len'):
        if key in spec:
            setattr(p, key, spec[key])
    for sd in spec['stations']:
        st = p.stations.add()
        for k, v in sd.items():
            setattr(st, k, v)
    for st in p.stations:
        migrate_bend(st)
    p.active = min(1, len(p.stations) - 1)
    if preset == 'DUCT':
        p.shell = 0.02
    if preset == 'PRISM':                 # stands up: the path runs along world Z
        import math
        ob.matrix_world = Matrix.Translation(context.scene.cursor.location) @ Matrix.Rotation(math.pi / 2, 4, 'X')
        p.active = 1
    p.live = True
    rebuild(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    try:                                   # 0.14.3: editing it now, not placing ghost shapes
        context.window_manager.mch_place.show = False
    except AttributeError:
        pass
    return ob


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

PRESET_ITEMS = [('PANEL', 'Flat Panel', 'Flat rounded plate: add stations to fold it'),
                ('PRISM', 'Polygon Prism', 'Square prism standing up: Sides 3 ... 64 (a cylinder), bevel / chamfer '
                                           'the edges, + / - adds segments above / below, fold them'),
                ('MULTI_BEND', 'Multi-Bend Armor', '30 deg + 45 deg folds, one side thicker, box ridge'),
                ('WRAP', 'Wrap / Tyre Cover', 'Ribbon wrapped 200 deg'),
                ('TEARDROP', 'Helmet / Teardrop', 'Round front, tapered pointed back, raised ridge'),
                ('AUTOMOTIVE', 'Automotive Panel', 'Asymmetric curved body panel with a crease'),
                ('DUCT', 'Duct', 'Round hollow tube with two smooth bends')]
ARMOR_ITEMS = [('SHOULDER', 'Shoulder / Knee', 'Cap that rolls over the joint (pauldron or knee guard)'),
               ('UPPER_LIMB', 'Upper Arm / Thigh', 'Long shell, wider at the top'),
               ('LOWER_LIMB', 'Forearm / Shin', 'Flared at the joint, tapered, small cuff'),
               ('TORSO', 'Torso / Chest', 'Chest plate, top rolls back toward the collar'),
               ('HELMET', 'Helmet', 'Shell with crest ridge and a rounded closed back')]


class MCH_OT_station_create(bpy.types.Operator):
    """Create a Station Primitive at the 3D cursor (live: edit stations, profile, ridge, then Apply)"""
    bl_idname = 'mch.station_create'
    bl_label = 'New Station Primitive'
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(name='Preset', items=PRESET_ITEMS + ARMOR_ITEMS, default='PANEL')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        ob = create(context, self.preset)
        w = ob.mch_station.warnings
        self.report({'WARNING' if w else 'INFO'}, w or f'{ob.name}: live Station Primitive')
        return {'FINISHED'}


class MCH_OT_station_add(bpy.types.Operator):
    """Add a station after the active one; it starts from where that segment ends and copies its values"""
    bl_idname = 'mch.station_add'
    bl_label = 'Add Station'
    bl_options = {'REGISTER', 'UNDO'}

    bend: FloatProperty(name='Bend', default=30.0)

    @classmethod
    def poll(cls, context):
        return active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        p = ob.mch_station
        i = min(max(p.active, 0), len(p.stations) - 1)
        src = _station_dict(p.stations[i])
        p.live = False
        st = p.stations.add()
        for k, v in src.items():
            setattr(st, k, v)
        st.bend_angle = 0.0
        st.bend_up = self.bend
        st.bend_side = 0.0
        st.length = max(0.3, src['length'] * 0.6) if i > 0 else 0.6
        st.world = False
        p.stations.move(len(p.stations) - 1, i + 1)
        p.active = i + 1
        p.live = True
        rebuild(ob)
        return {'FINISHED'}


class MCH_OT_station_remove(bpy.types.Operator):
    """Remove the active station (the first one stays)"""
    bl_idname = 'mch.station_remove'
    bl_label = 'Remove Station'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = active_station_primitive(context)
        return ob is not None and len(ob.mch_station.stations) > 2 and ob.mch_station.active > 0

    def execute(self, context):
        ob = active_station_primitive(context)
        p = ob.mch_station
        p.live = False
        p.stations.remove(p.active)
        p.active = min(p.active, len(p.stations) - 1)
        p.live = True
        rebuild(ob)
        return {'FINISHED'}


class MCH_OT_station_move(bpy.types.Operator):
    """Move the active station up / down in the chain"""
    bl_idname = 'mch.station_move'
    bl_label = 'Move Station'
    bl_options = {'REGISTER', 'UNDO'}

    delta: IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        p = ob.mch_station
        j = p.active + self.delta
        if p.active < 1 or j < 1 or j >= len(p.stations):
            return {'CANCELLED'}
        p.live = False
        p.stations.move(p.active, j)
        p.active = j
        p.live = True
        rebuild(ob)
        return {'FINISHED'}


class MCH_OT_station_select(bpy.types.Operator):
    """Make this station the active one (its handles appear)"""
    bl_idname = 'mch.station_select'
    bl_label = 'Select Station'
    bl_options = {'INTERNAL'}

    index: IntProperty(default=0)

    @classmethod
    def poll(cls, context):
        return active_station_primitive(context) is not None

    def execute(self, context):
        p = active_station_primitive(context).mch_station
        p.active = max(0, min(self.index, len(p.stations) - 1))
        return {'FINISHED'}


class MCH_OT_station_insert(bpy.types.Operator):
    """Insert a station in the middle of the segment that leads to station 'index'"""
    bl_idname = 'mch.station_insert'
    bl_label = 'Insert Station Here'
    bl_options = {'REGISTER', 'UNDO'}

    index: IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        p = ob.mch_station
        i = max(1, min(self.index, len(p.stations) - 1))
        a, b = p.stations[i - 1], p.stations[i]
        p.live = False
        st = p.stations.add()
        for k in ss.STATION_KEYS:
            setattr(st, k, getattr(b, k))
        for k in ss.BLEND_KEYS:                    # halfway profile
            setattr(st, k, (getattr(a, k) + getattr(b, k)) / 2)
        st.length = b.length / 2
        b.length = b.length / 2
        for key in ('bend_angle', 'bend_up', 'bend_side'):   # the bend stays at the start of the segment
            setattr(st, key, getattr(b, key))
            setattr(b, key, 0.0)
        st.profile = 'INHERIT'
        p.stations.move(len(p.stations) - 1, i)
        p.active = i
        p.live = True
        rebuild(ob)
        return {'FINISHED'}


class MCH_OT_station_bend_dir(bpy.types.Operator):
    """Bend the active segment up / down / left / right"""
    bl_idname = 'mch.station_bend_dir'
    bl_label = 'Bend Direction'
    bl_options = {'REGISTER', 'UNDO'}

    direction: FloatProperty(default=0.0)

    @classmethod
    def poll(cls, context):
        ob = active_station_primitive(context)
        return ob is not None and ob.mch_station.active > 0

    def execute(self, context):
        ob = active_station_primitive(context)
        import math
        st = ob.mch_station.stations[ob.mch_station.active]
        st.world = False
        up, side = total_bend(st)
        amount = math.hypot(up, side) or 30.0
        d = math.radians(self.direction)
        st.bend_dir = self.direction
        st.bend_angle = 0.0
        st.bend_up = amount * math.cos(d)
        st.bend_side = amount * math.sin(d)
        return {'FINISHED'}


def _frame_matrix(fr):
    P, X, T, Z = (Vector(v) for v in fr)
    m = Matrix((X, T, Z)).transposed().to_4x4()
    m.translation = P
    return m


def add_segment(ob, where='END', length=None):
    """0.15 + button above / below: a new segment at the end (or before the
    start) with the same profile; the existing shape stays where it is."""
    p = ob.mch_station
    p.live = False
    try:
        if where == 'END':
            src = _station_dict(p.stations[-1])
            st = p.stations.add()
            for k, v in src.items():
                setattr(st, k, v)
            for k in ('bend_angle', 'bend_up', 'bend_side', 'twist'):
                setattr(st, k, 0.0)
            st.length = length if length is not None else (src['length'] if src['length'] > 1e-6 else 0.5)
            p.active = len(p.stations) - 1
        else:
            first = p.stations[0]
            L = length if length is not None else (p.stations[1].length if len(p.stations) > 1 and
                                                   p.stations[1].length > 1e-6 else 0.5)
            src = _station_dict(first)
            st = p.stations.add()
            for k, v in src.items():
                setattr(st, k, v)
            p.stations.move(len(p.stations) - 1, 0)
            old_start = p.stations[1]
            old_start.length = L
            for k in ('bend_angle', 'bend_up', 'bend_side', 'twist'):
                setattr(old_start, k, 0.0)
            ob.matrix_world = ob.matrix_world @ Matrix.Translation((0.0, -L, 0.0))
            p.active = 0
    finally:
        p.live = True
    rebuild(ob)


def remove_segment(ob, where='END'):
    """0.15 - button above / below: drop the last (or the first) segment."""
    p = ob.mch_station
    if len(p.stations) <= 2:
        return False
    if where == 'END':
        p.live = False
        p.stations.remove(len(p.stations) - 1)
    else:
        fr = station_frames(ob)[1]
        mw = ob.matrix_world @ _frame_matrix(fr)
        p.live = False
        p.stations.remove(0)
        for k in ('bend_angle', 'bend_up', 'bend_side', 'twist'):
            setattr(p.stations[0], k, 0.0)
        ob.matrix_world = mw
    p.active = min(p.active, len(p.stations) - 1)
    p.live = True
    rebuild(ob)
    return True


BEND_LEVELS = (0.0, 0.6, 1.5, 3.0)       # fold, then band radius x profile size


def profile_size(st):
    return max(st.width_l, st.width_r, st.height_top, st.height_bot, 1e-3)


def bend_level(st):
    if st.bend_style == 'FOLD' or (st.bend_style == 'AUTO' and st.bend_radius <= 1e-6):
        return 0
    r = st.bend_radius / profile_size(st)
    return min(range(1, len(BEND_LEVELS)), key=lambda k: abs(BEND_LEVELS[k] - r))


def cycle_bend(st):
    """Click on the fold dot: right angle -> softer -> rounder -> roundest -> right angle."""
    level = (bend_level(st) + 1) % len(BEND_LEVELS)
    if level == 0:
        st.bend_style = 'FOLD'
        st.bend_radius = 0.0
    else:
        st.bend_style = 'BAND'
        st.bend_radius = BEND_LEVELS[level] * profile_size(st)
    return level


class MCH_OT_station_segment(bpy.types.Operator):
    """Add or remove a segment at the end (top) or the start (bottom)"""
    bl_idname = 'mch.station_segment'
    bl_label = 'Station Segment'
    bl_options = {'REGISTER', 'UNDO'}
    where: EnumProperty(items=[('END', 'End', ''), ('START', 'Start', '')], default='END')
    action: EnumProperty(items=[('ADD', 'Add', ''), ('REMOVE', 'Remove', '')], default='ADD')

    @classmethod
    def description(cls, context, properties):
        side = 'end' if properties.where == 'END' else 'start'
        return (f'Add a segment at the {side} (same profile)' if properties.action == 'ADD'
                else f'Remove the segment at the {side}')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        if self.action == 'ADD':
            add_segment(ob, self.where)
        elif not remove_segment(ob, self.where):
            self.report({'WARNING'}, 'At least one segment stays')
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_station_bend_cycle(bpy.types.Operator):
    """Fold dot: right angle -> softer band -> rounder -> roundest -> right angle"""
    bl_idname = 'mch.station_bend_cycle'
    bl_label = 'Fold Shape'
    bl_options = {'REGISTER', 'UNDO'}
    index: IntProperty(default=1)

    @classmethod
    def poll(cls, context):
        return active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        p = ob.mch_station
        if not 0 < self.index < len(p.stations):
            return {'CANCELLED'}
        level = cycle_bend(p.stations[self.index])
        self.report({'INFO'}, ('Right angle', 'Soft band', 'Rounder band', 'Round band')[level])
        return {'FINISHED'}


class MCH_OT_station_apply(bpy.types.Operator):
    """Freeze into an ordinary mesh (the shell becomes real geometry); the parameters are removed"""
    bl_idname = 'mch.station_apply'
    bl_label = 'Apply Station Primitive'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_station_primitive(context) is not None

    def execute(self, context):
        ob = active_station_primitive(context)
        try:
            apply_object(context, ob)
        except Exception as ex:                       # keep it live and report
            self.report({'ERROR'}, f'Shell could not be applied: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: applied as an ordinary mesh')
        return {'FINISHED'}


def apply_object(context, ob):
    """Freeze: the shell becomes real geometry, the parameters are removed."""
    mod = ob.modifiers.get(SHELL_MOD)
    if mod is not None:
        from . import core_geometry as cg
        cg.apply_single_modifier(context, ob, mod, 'SINGLE')
    ob.mch_station.live = False
    ob.mch_station.stations.clear()
    if 'mch_role' in ob:
        del ob['mch_role']


class MCH_UL_stations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if index == 0:
            layout.label(text='Start', icon='KEYFRAME')
            return
        up, side = total_bend(item)
        parts = ([f'up {up:+.0f}°'] if abs(up) > 1e-6 else []) + ([f'side {side:+.0f}°'] if abs(side) > 1e-6 else [])
        bend = ' '.join(parts) or '—'
        kind = 'fold' if item.bend_radius <= 1e-6 or item.bend_style == 'FOLD' else f'r {item.bend_radius:.2f}'
        layout.label(text=f'S{index}   {bend} {kind if parts else ""}   L {item.length:.2f}',
                     icon='KEYFRAME_HLT' if index == active_data.active else 'KEYFRAME')


def draw(layout, context):
    """Compact panel: main controls first, the rest folded away."""
    ob = active_station_primitive(context)
    box = layout.box()
    box.label(text='STATION PRIMITIVE', icon='CURVE_PATH')
    if ob is None:
        grid = box.grid_flow(columns=2, align=True)
        for key, label, _desc in PRESET_ITEMS:
            grid.operator('mch.station_create', text=label).preset = key
        box.label(text='ARMOR (human scale, metres)', icon='MOD_CLOTH')
        grid = box.grid_flow(columns=2, align=True)
        for key, label, _desc in ARMOR_ITEMS:
            grid.operator('mch.station_create', text=label).preset = key
        return
    p = ob.mch_station
    row = box.row(align=True)
    row.prop(p, 'kind', text='')
    row.prop(p, 'ridge', text='')
    box.template_list('MCH_UL_stations', '', p, 'stations', p, 'active', rows=4)
    row = box.row(align=True)
    row.scale_y = 1.2
    row.operator('mch.station_add', text='Add Station', icon='ADD').bend = 30.0
    row.operator('mch.station_remove', text='', icon='REMOVE')
    row.operator('mch.station_move', text='', icon='TRIA_UP').delta = -1
    row.operator('mch.station_move', text='', icon='TRIA_DOWN').delta = 1
    if 0 <= p.active < len(p.stations):
        st = p.stations[p.active]
        col = box.column(align=True)
        if p.active > 0:
            col.prop(st, 'length')
            r = col.row(align=True)
            r.prop(st, 'bend_up', text='Up / Down')
            r.prop(st, 'bend_side', text='Left / Right')
            col.prop(st, 'twist', text='Twist (along the axis)')
            if abs(st.bend_angle) > 1e-6:
                r = col.row(align=True)
                r.prop(st, 'bend_angle', text='Older Bend')
                r.prop(st, 'bend_dir', text='Dir')
            col.row(align=True).prop(st, 'bend_style', expand=True)
            if st.bend_style == 'BAND' or (st.bend_style == 'AUTO' and st.bend_radius > 0):
                col.prop(st, 'bend_radius', text='Band Radius')
            if p.kind != 'NGON':
                col.prop(st, 'profile')
        r = col.row(align=True)
        if p.sym_lr:
            r.prop(st, 'width_l', text='Width (half)')
        else:
            r.prop(st, 'width_l', text='W left')
            r.prop(st, 'width_r', text='W right')
        r.prop(p, 'sym_lr', text='', icon='MOD_MIRROR')
        r = col.row(align=True)
        arc = (st.profile if st.profile != 'INHERIT' else p.kind) == 'ARC'
        r.prop(st, 'height_top', text='Crown' if arc else 'Top')
        r.prop(st, 'height_bot', text='Thickness' if arc else 'Bottom')
        if p.ridge != 'NONE':
            r = col.row(align=True)
            r.prop(st, 'ridge_h', text='Ridge H')
            r.prop(st, 'ridge_w', text='W')
        box.prop(p, 'show_asym', icon='TRIA_DOWN' if p.show_asym else 'TRIA_RIGHT', emboss=False)
        if p.show_asym:
            c = box.column(align=True)
            r = c.row(align=True)
            r.prop(st, 'thick_l', text='Thick L')
            r.prop(st, 'thick_r', text='Thick R')
            r = c.row(align=True)
            r.prop(st, 'corner_l', text='Corner L')
            r.prop(st, 'corner_r', text='Corner R')
            c.prop(st, 'ridge_offset')
            if p.active > 0:
                c.prop(st, 'interp', expand=True)
                c.prop(st, 'world')
                if st.world:
                    r = c.row(align=True)
                    r.prop(st, 'yaw')
                    r.prop(st, 'pitch')
    if p.kind in {'POLYGON', 'NGON'}:
        box.prop(p, 'sides', slider=True)
    row = box.row(align=True)
    row.prop(p, 'cap_start')
    row.prop(p, 'cap_end')
    c = box.column(align=True)
    r = c.row(align=True)
    r.label(text='Side edges')
    r.prop(p, 'corner_finish', expand=True)
    if p.corner_finish != 'NONE':
        r = c.row(align=True)
        r.prop(p, 'corner_width', text='Width')
        if p.corner_finish == 'BEVEL':
            r.prop(p, 'corner_segments', text='Seg')
    r = c.row(align=True)
    r.label(text='End edges')
    r.prop(p, 'cap_finish', expand=True)
    if p.cap_finish != 'NONE':
        r = c.row(align=True)
        r.prop(p, 'cap_width', text='Width')
        if p.cap_finish == 'BEVEL':
            r.prop(p, 'cap_segments', text='Seg')
    row = box.row(align=True)
    row.operator('mch.station_segment', text='Segment at End', icon='ADD').where = 'END'
    row.operator('mch.station_segment', text='at Start', icon='ADD').where = 'START'
    box.prop(p, 'shell')
    box.prop(p, 'show_adv', icon='TRIA_DOWN' if p.show_adv else 'TRIA_RIGHT', emboss=False)
    if p.show_adv:
        c = box.column(align=True)
        c.prop(p, 'res')
        c.prop(p, 'cap_len')
        c.prop(p, 'seg_mode', expand=True)
        if p.seg_mode == 'AUTO':
            c.prop(p, 'quality', expand=True)
        else:
            c.prop(p, 'seg_bend')
            c.prop(p, 'seg_run')
    if p.warnings:
        for w in p.warnings.split(' | '):
            box.label(text=w, icon='ERROR')
    row = box.row()
    row.scale_y = 1.3
    row.operator('mch.station_apply', text='Apply', icon='CHECKMARK')
    box.label(text='Viewport: click a station dot, drag its handles; + on a segment inserts', icon='INFO')


CLASSES = (MCH_PG_Station, MCH_PG_StationPrimitive, MCH_OT_station_create, MCH_OT_station_add,
           MCH_OT_station_remove, MCH_OT_station_move, MCH_OT_station_select, MCH_OT_station_insert,
           MCH_OT_station_bend_dir, MCH_OT_station_segment, MCH_OT_station_bend_cycle, MCH_OT_station_apply,
           MCH_UL_stations)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_station = PointerProperty(type=MCH_PG_StationPrimitive)
    if _migrate_on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_migrate_on_load)


def unregister():
    if _migrate_on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_migrate_on_load)
    if hasattr(bpy.types.Object, 'mch_station'):
        del bpy.types.Object.mch_station
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
