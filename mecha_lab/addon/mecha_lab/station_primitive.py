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
from mathutils import Matrix

from . import station_sweep as ss

ROLE = 'MCH_STATION_PRIMITIVE'
SHELL_MOD = 'MCH_StationShell'
_building = set()


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
    interp: EnumProperty(name='Blend', items=[('LINEAR', 'Linear', 'Even change from the previous station'),
                                               ('SMOOTH', 'Smooth', 'Eased change (more segments)'),
                                               ('STEP', 'Step', 'Sharp change at this station')],
                         default='LINEAR', update=_rebuild_update)


class MCH_PG_StationPrimitive(bpy.types.PropertyGroup):
    live: BoolProperty(name='Live', default=False)
    kind: EnumProperty(name='Profile', items=[
        ('ROUNDED', 'Rounded Box', ''), ('CHAMFER', 'Chamfered Box', ''), ('BOX', 'Flat Box', ''),
        ('RIBBON', 'Ribbon', ''), ('ROUND', 'Round / Oval', ''), ('CAPSULE', 'Capsule', ''),
        ('POLYGON', 'Polygon', '')], default='ROUNDED', update=_rebuild_update)
    sides: IntProperty(name='Sides', default=6, min=3, max=32, update=_rebuild_update)
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
    show_adv: BoolProperty(name='Advanced', default=False)
    warnings: StringProperty(default='')


def _station_dict(st):
    return {k: getattr(st, k) for k in ss.STATION_KEYS}


def spec_of(ob):
    p = ob.mch_station
    return dict(kind=p.kind, sides=p.sides, ridge=p.ridge, res=p.res, quality=p.quality, seg_mode=p.seg_mode,
                seg_bend=p.seg_bend, seg_run=p.seg_run, cap_start=p.cap_start, cap_end=p.cap_end,
                cap_len=p.cap_len, stations=[_station_dict(s) for s in p.stations])


def _write_mesh(me, result):
    bm = bmesh.new()
    try:
        vs = [bm.verts.new(v) for v in result['verts']]
        for f in result['faces']:
            try:
                bm.faces.new([vs[i] for i in f])
            except ValueError:          # duplicate face from a collapsed corner
                pass
        bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=1e-6)
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges[:], dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
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
        _write_mesh(ob.data, result)
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
    p.active = min(1, len(p.stations) - 1)
    if preset == 'DUCT':
        p.shell = 0.02
    p.live = True
    rebuild(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------

PRESET_ITEMS = [('PANEL', 'Flat Panel', 'Flat rounded plate: add stations to fold it'),
                ('MULTI_BEND', 'Multi-Bend Armor', '30 deg + 45 deg folds, one side thicker, box ridge'),
                ('WRAP', 'Wrap / Tyre Cover', 'Ribbon wrapped 200 deg'),
                ('TEARDROP', 'Helmet / Teardrop', 'Round front, tapered pointed back, raised ridge'),
                ('AUTOMOTIVE', 'Automotive Panel', 'Asymmetric curved body panel with a crease'),
                ('DUCT', 'Duct', 'Round hollow tube with two smooth bends')]


class MCH_OT_station_create(bpy.types.Operator):
    """Create a Station Primitive at the 3D cursor (live: edit stations, profile, ridge, then Apply)"""
    bl_idname = 'mch.station_create'
    bl_label = 'New Station Primitive'
    bl_options = {'REGISTER', 'UNDO'}

    preset: EnumProperty(name='Preset', items=PRESET_ITEMS, default='PANEL')

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
        st.bend_angle = self.bend
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
        mod = ob.modifiers.get(SHELL_MOD)
        if mod is not None:
            from . import core_geometry as cg
            try:
                cg.apply_single_modifier(context, ob, mod, 'SINGLE')
            except Exception as ex:                       # keep it live and report
                self.report({'ERROR'}, f'Shell could not be applied: {ex}')
                return {'CANCELLED'}
        ob.mch_station.live = False
        ob.mch_station.stations.clear()
        if 'mch_role' in ob:
            del ob['mch_role']
        self.report({'INFO'}, f'{ob.name}: applied as an ordinary mesh')
        return {'FINISHED'}


class MCH_UL_stations(bpy.types.UIList):
    def draw_item(self, context, layout, data, item, icon, active_data, active_propname, index):
        if index == 0:
            layout.label(text='Start', icon='KEYFRAME')
            return
        bend = f'{item.bend_angle:+.0f}°' if abs(item.bend_angle) > 1e-6 else '—'
        kind = 'fold' if item.bend_radius <= 1e-6 else f'r {item.bend_radius:.2f}'
        layout.label(text=f'S{index}   {bend} {kind if abs(item.bend_angle) > 1e-6 else ""}   L {item.length:.2f}',
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
            r = col.row(align=True)
            r.prop(st, 'bend_angle')
            r.prop(st, 'bend_dir', text='Dir')
            r = col.row(align=True)
            r.prop(st, 'bend_radius', text='Radius (0 = fold)')
            r.prop(st, 'length')
        r = col.row(align=True)
        r.prop(st, 'width_l', text='W left')
        r.prop(st, 'width_r', text='W right')
        r = col.row(align=True)
        r.prop(st, 'height_top', text='Top')
        r.prop(st, 'height_bot', text='Bottom')
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
                c.prop(st, 'twist')
                c.prop(st, 'interp', expand=True)
                c.prop(st, 'world')
                if st.world:
                    r = c.row(align=True)
                    r.prop(st, 'yaw')
                    r.prop(st, 'pitch')
    row = box.row(align=True)
    row.prop(p, 'cap_start')
    row.prop(p, 'cap_end')
    box.prop(p, 'shell')
    box.prop(p, 'show_adv', icon='TRIA_DOWN' if p.show_adv else 'TRIA_RIGHT', emboss=False)
    if p.show_adv:
        c = box.column(align=True)
        c.prop(p, 'res')
        if p.kind == 'POLYGON':
            c.prop(p, 'sides')
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
    box.label(text='Viewport station handles: next phase', icon='INFO')


CLASSES = (MCH_PG_Station, MCH_PG_StationPrimitive, MCH_OT_station_create, MCH_OT_station_add,
           MCH_OT_station_remove, MCH_OT_station_move, MCH_OT_station_apply, MCH_UL_stations)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_station = PointerProperty(type=MCH_PG_StationPrimitive)


def unregister():
    if hasattr(bpy.types.Object, 'mch_station'):
        del bpy.types.Object.mch_station
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
