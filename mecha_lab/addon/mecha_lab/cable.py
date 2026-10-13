"""Cable Generator.

Two-Point Cable: click a point on any mesh surface, then a second point (the
same or another object).  The cable leaves each surface along its normal and
is a real Bezier curve object: start / end stay fixed while the path sliders
(handle angle / length, sag, curvature, midpoint offset, twist, number of
control points) reshape the middle, and the curve can still be edited in Edit
Mode.  Edge to Cable turns selected edge chains (Edit Mode) into cables; the
source edges are kept.

Thickness: overall, start / end factors with taper (point radius), curve and
profile resolution.  Profiles: Round (curve bevel), Square, Flat / Ribbon,
Oval (a generated profile curve, hidden) or any custom curve object.
Path sliders rebuild the control points (manual edits are replaced only when
a PATH slider changes; thickness / profile sliders never touch the path).
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from bpy.props import (BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty,
                       StringProperty)
from mathutils import Matrix, Vector

COLL_CABLE = 'Cable Objects'


def _path_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.active:
        rebuild_path(ob)
        rebuild_look(ob)


def _look_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.active:
        rebuild_look(ob)


def _pp(prop, **kw):
    kw.setdefault('update', _path_update)
    return prop(**kw)


def _pl(prop, **kw):
    kw.setdefault('update', _look_update)
    return prop(**kw)


class MCH_PG_Cable(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    kind: StringProperty(default='POINTS', options={'HIDDEN'})
    chain: StringProperty(default='', options={'HIDDEN'})
    start: FloatVectorProperty(size=3, options={'HIDDEN'})
    start_normal: FloatVectorProperty(size=3, default=(0, 0, 1), options={'HIDDEN'})
    end: FloatVectorProperty(size=3, options={'HIDDEN'})
    end_normal: FloatVectorProperty(size=3, default=(0, 0, 1), options={'HIDDEN'})
    profile_object: PointerProperty(type=bpy.types.Object)
    # ---- path -----------------------------------------------------------------
    control_points: _pp(IntProperty, name='Control Points', default=3, min=0, max=32,
                        description='Points between start and end')
    handle_angle: _pp(FloatProperty, name='Handle Angle', default=math.radians(30.0), min=0.0, max=math.pi / 2,
                      subtype='ANGLE', description='0 = leave the surface along its normal, 90 = straight to the other end')
    handle_length: _pp(FloatProperty, name='Handle Length', default=0.35, min=0.0, soft_max=2.0,
                       description='Relative to the start-end distance')
    sag: _pp(FloatProperty, name='Sag / Droop', default=0.15, soft_min=-1.0, soft_max=1.0,
             description='Droop toward world -Z, relative to the distance')
    curvature: _pp(FloatProperty, name='Curvature', default=0.0, soft_min=-1.0, soft_max=1.0,
                   description='Bulge away from the surfaces, relative to the distance')
    mid_offset: _pp(FloatVectorProperty, name='Midpoint Offset', size=3, subtype='XYZ', unit='LENGTH',
                    description='Along / side / up offset of the middle of the cable')
    smoothing: _pp(IntProperty, name='Smoothing', default=0, min=0, max=50, description='Edge to Cable: smooth the path')
    # ---- look -------------------------------------------------------------------
    twist: _pl(FloatProperty, name='Twist', default=0.0, subtype='ANGLE')
    thickness: _pl(FloatProperty, name='Thickness', default=0.03, min=0.0001, soft_max=1.0, precision=4, unit='LENGTH')
    start_thickness: _pl(FloatProperty, name='Start Thickness', default=1.0, min=0.0, soft_max=3.0)
    end_thickness: _pl(FloatProperty, name='End Thickness', default=1.0, min=0.0, soft_max=3.0)
    taper: _pl(FloatProperty, name='Taper', default=1.0, min=0.1, soft_max=5.0,
               description='Start -> end thickness curve (1 = linear)')
    resolution: _pl(IntProperty, name='Curve Resolution', default=16, min=2, max=64)
    profile_resolution: _pl(IntProperty, name='Profile Resolution', default=6, min=1, max=32)
    profile: _pl(EnumProperty, name='Profile', items=[
        ('ROUND', 'Round', ''), ('SQUARE', 'Square', ''), ('RIBBON', 'Flat / Ribbon', ''), ('OVAL', 'Oval', ''),
        ('CUSTOM', 'Custom', 'Any curve object as the cross-section')], default='ROUND')
    profile_ratio: _pl(FloatProperty, name='Profile Ratio', default=0.4, min=0.05, max=1.0,
                       description='Ribbon / Oval height relative to width')
    custom_profile: _pl(PointerProperty, type=bpy.types.Object, name='Custom Profile',
                        poll=lambda s, o: o.type == 'CURVE')


# =============================================================================
# Path
# =============================================================================


def _toward(n, d, angle):
    """Rotate unit vector n toward d by ``angle`` (0 = n)."""
    n, d = n.normalized(), d.normalized()
    axis = n.cross(d)
    if axis.length < 1e-9:
        return n
    full = n.angle(d)
    return (Matrix.Rotation(min(angle, full), 3, axis.normalized()) @ n).normalized()


def path_points(p):
    """[(co, handle_left, handle_right, kind)] for a two-point cable."""
    p0, p3 = Vector(p.start), Vector(p.end)
    n0 = Vector(p.start_normal).normalized() if Vector(p.start_normal).length > 1e-9 else Vector((0, 0, 1))
    n3 = Vector(p.end_normal).normalized() if Vector(p.end_normal).length > 1e-9 else Vector((0, 0, 1))
    chord = p3 - p0
    dist = max(chord.length, 1e-6)
    d0 = _toward(n0, chord, p.handle_angle)
    d3 = _toward(n3, -chord, p.handle_angle)
    L = p.handle_length * dist
    c1, c2 = p0 + d0 * L, p3 + d3 * L
    up = (n0 + n3)
    up = (up - chord.normalized() * up.dot(chord.normalized()))
    up = up.normalized() if up.length > 1e-9 else chord.orthogonal().normalized()
    side = chord.normalized().cross(up).normalized()
    m = max(0, p.control_points)
    pts = [(p0, p0 - d0 * L / 3, p0 + d0 * L / 3, 'ALIGNED')]
    for k in range(1, m + 1):
        t = k / (m + 1)
        q = p0 * (1 - t) ** 3 + c1 * 3 * t * (1 - t) ** 2 + c2 * 3 * t * t * (1 - t) + p3 * t ** 3
        bell = 4 * t * (1 - t)
        q = q + Vector((0, 0, -1)) * (p.sag * dist * bell) + up * (p.curvature * dist * bell)
        mo = Vector(p.mid_offset)
        q = q + (chord.normalized() * mo.x + side * mo.y + up * mo.z) * bell
        pts.append((q, None, None, 'AUTO'))
    pts.append((p3, p3 + d3 * L / 3, p3 - d3 * L / 3, 'ALIGNED'))
    return pts


def _chain_points(p):
    data = json.loads(p.chain) if p.chain else []
    out = []
    for ch in data:
        pts = [Vector(q) for q in ch['pts']]
        closed = ch.get('closed', False)
        for _ in range(p.smoothing):
            new = list(pts)
            for i in range(len(pts)):
                if not closed and i in (0, len(pts) - 1):
                    continue
                new[i] = pts[i] * 0.5 + (pts[i - 1] + pts[(i + 1) % len(pts)]) * 0.25
            pts = new
        out.append((pts, closed))
    return out


def rebuild_path(ob):
    p = ob.mch_cable
    cu = ob.data
    cu.splines.clear()
    if p.kind == 'EDGES':
        for pts, closed in _chain_points(p):
            spl = cu.splines.new('BEZIER')
            spl.bezier_points.add(len(pts) - 1)
            for bp, co in zip(spl.bezier_points, pts):
                bp.handle_left_type = bp.handle_right_type = 'AUTO'
                bp.co = co
            spl.use_cyclic_u = closed
        return
    spl = cu.splines.new('BEZIER')
    pts = path_points(p)
    spl.bezier_points.add(len(pts) - 1)
    for bp, (co, hl, hr, kind) in zip(spl.bezier_points, pts):
        if kind == 'AUTO':
            bp.handle_left_type = bp.handle_right_type = 'AUTO'
            bp.co = co
        else:
            bp.handle_left_type = bp.handle_right_type = 'FREE'
            bp.co = co
            bp.handle_left = hl
            bp.handle_right = hr
            bp.handle_left_type = bp.handle_right_type = 'ALIGNED'


def _profile_curve(ob, p):
    """Generated (hidden) cross-section curve for Square / Ribbon / Oval."""
    prof = p.profile_object
    if prof is None or prof.name not in bpy.data.objects:
        cu = bpy.data.curves.new('MCH_CableProfile', 'CURVE')
        prof = bpy.data.objects.new('MCH_CableProfile_' + ob.name, cu)
        from .face_extract import _parts_collection
        _parts_collection(bpy.context, COLL_CABLE).objects.link(prof)
        prof.hide_viewport = True
        prof.hide_render = True
        p.profile_object = prof
    cu = prof.data
    cu.splines.clear()
    w = p.thickness
    h = w * (1.0 if p.profile == 'SQUARE' else p.profile_ratio)
    if p.profile == 'OVAL':
        n = max(8, p.profile_resolution * 4)
        pts = [(w / 2 * math.cos(2 * math.pi * k / n), h / 2 * math.sin(2 * math.pi * k / n)) for k in range(n)]
    else:
        pts = [(-w / 2, -h / 2), (w / 2, -h / 2), (w / 2, h / 2), (-w / 2, h / 2)]
    spl = cu.splines.new('POLY')
    spl.points.add(len(pts) - 1)
    for q, (x, y) in zip(spl.points, pts):
        q.co = (x, y, 0.0, 1.0)
    spl.use_cyclic_u = True
    return prof


def rebuild_look(ob):
    p = ob.mch_cable
    cu = ob.data
    cu.dimensions = '3D'
    cu.resolution_u = p.resolution
    cu.use_fill_caps = True
    cu.twist_mode = 'MINIMUM'
    if p.profile == 'ROUND':
        cu.bevel_mode = 'ROUND'
        cu.bevel_depth = p.thickness / 2
        cu.bevel_resolution = p.profile_resolution
        cu.bevel_object = None
        base = 1.0
    elif p.profile == 'CUSTOM' and p.custom_profile is not None:
        cu.bevel_mode = 'OBJECT'
        cu.bevel_object = p.custom_profile
        base = p.thickness
    else:
        cu.bevel_mode = 'OBJECT'
        cu.bevel_object = _profile_curve(ob, p)
        base = 1.0
    for spl in cu.splines:
        pts = spl.bezier_points if spl.type == 'BEZIER' else spl.points
        n = len(pts)
        for i, q in enumerate(pts):
            t = i / max(1, n - 1)
            f = p.start_thickness + (p.end_thickness - p.start_thickness) * (t ** p.taper)
            q.radius = max(0.0, f * base)
            q.tilt = p.twist * t
    cu.update_tag()


def create_cable(context, start, start_n, end, end_n, chain=None, name='MCH_Cable'):
    from .face_extract import _parts_collection
    cu = bpy.data.curves.new(name, 'CURVE')
    ob = bpy.data.objects.new(name, cu)
    _parts_collection(context, COLL_CABLE).objects.link(ob)
    p = ob.mch_cable
    d = context.scene.mch_cable
    for key in ('control_points', 'handle_angle', 'handle_length', 'sag', 'curvature', 'mid_offset', 'smoothing',
                'twist', 'thickness', 'start_thickness', 'end_thickness', 'taper', 'resolution', 'profile_resolution',
                'profile', 'profile_ratio'):
        setattr(p, key, getattr(d, key))
    p.custom_profile = d.custom_profile
    if chain is not None:
        p.kind = 'EDGES'
        p.chain = chain
    else:
        p.start, p.start_normal, p.end, p.end_normal = start, start_n, end, end_n
    p.active = True
    rebuild_path(ob)
    rebuild_look(ob)
    context.scene.mch_cable_last = ob
    return ob


# =============================================================================
# Operators
# =============================================================================


def surface_hit(context, region, rv3d, xy):
    """(location, normal, object) under the mouse, any visible mesh."""
    from bpy_extras import view3d_utils
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
    if not hit:
        return None
    return loc, nrm, ob


class CableClickLogic:
    """Two clicks -> cable (plain Python; ``hit(context, event)`` is patchable)."""

    def hit(self, context, event):
        return surface_hit(context, context.region, context.region_data,
                           (event.mouse_region_x, event.mouse_region_y))

    def on_event(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return self._done(context, {'CANCELLED'})
        if event.type == 'TAB' and event.value == 'PRESS':
            self._done(context, {'CANCELLED'})
            return {'CANCELLED', 'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            h = self.hit(context, event)
            if h is None:
                self.report({'WARNING'}, 'Click on a mesh surface')
                return {'RUNNING_MODAL'}
            if self.first is None:
                self.first = h
                self._status(context, 'Cable: click the END point on any mesh (Esc = cancel)')
                return {'RUNNING_MODAL'}
            (p0, n0, o0), (p1, n1, o1) = self.first, h
            self.cable = create_cable(context, p0, n0, p1, n1)
            self.report({'INFO'}, f'Cable {o0.name} -> {o1.name}: path / thickness sliders in the panel')
            return self._done(context, {'FINISHED'})
        return {'PASS_THROUGH'}

    def _status(self, context, text):
        try:
            context.workspace.status_text_set(text)
        except AttributeError:
            pass

    def _done(self, context, result):
        self._status(context, None)
        return result


class MCH_OT_cable_draw(CableClickLogic, bpy.types.Operator):
    bl_idname = 'mch.cable_draw'
    bl_label = 'Two-Point Cable'
    bl_description = 'Click a start point and an end point on mesh surfaces (different objects allowed)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        self.first = None
        self.cable = None
        self._status(context, 'Cable: click the START point on a mesh (Esc = cancel, Tab passes through)')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        return self.on_event(context, event)


class MCH_OT_edge_to_cable(bpy.types.Operator):
    bl_idname = 'mch.edge_to_cable'
    bl_label = 'Edge to Cable'
    bl_description = 'Edit Mode: each selected edge chain becomes a cable (the edges are kept)'
    bl_options = {'REGISTER', 'UNDO'}

    together: BoolProperty(name='One Object', default=False, description='All chains in one cable object')

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        from .edge_molding import chains_from_edges
        made = []
        for ob in [o for o in (context.objects_in_mode or [context.active_object]) if o and o.type == 'MESH']:
            ob.update_from_editmode()
            bm = bmesh.from_edit_mesh(ob.data)
            chains = chains_from_edges([e for e in bm.edges if e.select])
            data = [{'pts': [tuple(ob.matrix_world @ v.co) for v in vs], 'closed': closed} for vs, closed in chains]
            if not data:
                continue
            groups = [data] if self.together else [[d] for d in data]
            for g in groups:
                made.append(create_cable(context, None, None, None, None, chain=json.dumps(g),
                                         name=ob.name + '_Cable'))
        if not made:
            self.report({'WARNING'}, 'Select edges first')
            return {'CANCELLED'}
        self.report({'INFO'}, f'{len(made)} cable object(s) from edges')
        return {'FINISHED'}


def active_cable(context):
    ob = context.active_object
    for cand in (ob, getattr(context.scene, 'mch_cable_last', None)):
        if cand is not None and cand.name in bpy.data.objects and getattr(cand, 'mch_cable', None) and \
                cand.mch_cable.active:
            return cand
    return None


class MCH_OT_cable_points(bpy.types.Operator):
    bl_idname = 'mch.cable_points'
    bl_label = 'Add / Delete Control Point'
    bl_options = {'REGISTER', 'UNDO'}

    delta: IntProperty(default=1, min=-1, max=1)

    @classmethod
    def poll(cls, context):
        ob = active_cable(context)
        return ob is not None and ob.mch_cable.kind == 'POINTS'

    def execute(self, context):
        p = active_cable(context).mch_cable
        p.control_points = max(0, p.control_points + self.delta)
        return {'FINISHED'}


def cable_to_mesh(context, ob):
    """Bake a live cable (curve + bevel) into an ordinary mesh object with the
    same name, transform, collections and materials.  The curve object and
    its generated hidden profile curve are removed."""
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    if me is None or not me.polygons:
        if me is not None:
            bpy.data.meshes.remove(me)
        raise RuntimeError('The cable has no thickness (Thickness 0?); nothing to convert')
    for mat in ob.data.materials:
        me.materials.append(mat)
    name = ob.name
    new = bpy.data.objects.new(name + '_Mesh', me)
    new.matrix_world = ob.matrix_world.copy()
    colls = list(ob.users_collection) or [context.scene.collection]
    for coll in colls:
        coll.objects.link(new)
    prof = ob.mch_cable.profile_object
    curve = ob.data
    if getattr(context.scene, 'mch_cable_last', None) == ob:
        context.scene.mch_cable_last = None
    bpy.data.objects.remove(ob, do_unlink=True)
    if curve.users == 0:
        bpy.data.curves.remove(curve)
    if prof is not None and prof.name in bpy.data.objects and prof.name.startswith('MCH_CableProfile_'):
        pdata = prof.data
        if not any(o.type == 'CURVE' and o.data.bevel_object == prof for o in bpy.data.objects):
            bpy.data.objects.remove(prof, do_unlink=True)
            if pdata.users == 0:
                bpy.data.curves.remove(pdata)
    new.name = name
    me.name = name + '_Mesh'
    for o in list(context.selected_objects):
        o.select_set(False)
    new.select_set(True)
    context.view_layer.objects.active = new
    return new


class MCH_OT_cable_to_mesh(bpy.types.Operator):
    bl_idname = 'mch.cable_to_mesh'
    bl_label = 'Convert Cable to Object'
    bl_description = 'Turn the live cable into an ordinary mesh object (the cable settings are no longer editable)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_cable(context) is not None

    def execute(self, context):
        targets = [o for o in context.selected_objects if getattr(o, 'mch_cable', None) and o.mch_cable.active
                   and o.type == 'CURVE']
        if not targets:
            targets = [active_cable(context)]
        done = []
        try:
            for ob in targets:
                done.append(cable_to_mesh(context, ob).name)
        except RuntimeError as ex:
            self.report({'ERROR'}, str(ex))
            return {'CANCELLED'} if not done else {'FINISHED'}
        self.report({'INFO'}, 'Converted to mesh: ' + ', '.join(done))
        return {'FINISHED'}


def draw(layout, context):
    ob = active_cable(context)
    p = ob.mch_cable if ob is not None else context.scene.mch_cable
    row = layout.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.cable_draw', icon='CURVE_BEZCURVE')
    row.operator('mch.edge_to_cable', icon='EDGESEL')
    box = layout.box()
    box.label(text=('CABLE: ' + ob.name) if ob else 'Settings for the next cable', icon='OUTLINER_OB_CURVE')
    if ob is None or p.kind == 'POINTS':
        col = box.column(align=True)
        col.label(text='Curve Control')
        r = col.row(align=True)
        r.prop(p, 'control_points')
        if ob is not None:
            r.operator('mch.cable_points', text='', icon='ADD').delta = 1
            r.operator('mch.cable_points', text='', icon='REMOVE').delta = -1
        col.prop(p, 'handle_angle')
        col.prop(p, 'handle_length')
        col.prop(p, 'sag')
        col.prop(p, 'curvature')
        box.prop(p, 'mid_offset')
    else:
        box.prop(p, 'smoothing')
    col = box.column(align=True)
    col.label(text='Thickness')
    col.prop(p, 'thickness')
    row = col.row(align=True)
    row.prop(p, 'start_thickness', text='Start')
    row.prop(p, 'end_thickness', text='End')
    col.prop(p, 'taper')
    col.prop(p, 'twist')
    col.prop(p, 'resolution')
    col.prop(p, 'profile_resolution')
    box.prop(p, 'profile', text='Profile')
    if p.profile in {'RIBBON', 'OVAL'}:
        box.prop(p, 'profile_ratio')
    if p.profile == 'CUSTOM':
        box.prop(p, 'custom_profile')
    if ob is not None:
        row = layout.row()
        row.scale_y = 1.3
        row.operator('mch.cable_to_mesh', text='Convert to Object (Mesh)', icon='OUTLINER_OB_MESH')
    layout.label(text='Start / end stay fixed; edit points in Edit Mode too', icon='INFO')


CLASSES = (MCH_PG_Cable, MCH_OT_cable_draw, MCH_OT_edge_to_cable, MCH_OT_cable_points, MCH_OT_cable_to_mesh)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_cable = PointerProperty(type=MCH_PG_Cable)
    bpy.types.Scene.mch_cable = PointerProperty(type=MCH_PG_Cable)
    bpy.types.Scene.mch_cable_last = PointerProperty(type=bpy.types.Object)


def unregister():
    for owner, name in ((bpy.types.Scene, 'mch_cable_last'), (bpy.types.Scene, 'mch_cable'),
                        (bpy.types.Object, 'mch_cable')):
        if hasattr(owner, name):
            delattr(owner, name)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
