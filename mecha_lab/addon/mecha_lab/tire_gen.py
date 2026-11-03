"""0.24.95 Tire & Wheel (user: "타이어 만드는 제너레이터도 만들어 줘, 내가 디자인할 수 있게 - 바퀴에 맞는 비율의 원기둥을
소환하고 거기에 어레이로 내가 그 타이어 위에 그린 메쉬를 돌려 주고, 휠 부분을 따로 또 같은 방식으로").

The design is the user's - the add-on gives the base and the repeat:

* **Summon Tire** - a tire-proportioned ring at the 3D cursor, its axle along X: a preset (Car, Truck, Off-road, Moto,
  Bike, Mech) or the sliders (Diameter, Width, Rim, Shoulder, Segments, Tread Lines); its sidewalls bulge a little,
  its shoulders round, a hole for the rim.  While it is selected the sliders change it at once.
* **Summon Wheel** - the rim for it, the same way: sized to the selected tire (its rim hole) and put in it (a child of
  it) - a Barrel (an open rim + a hub: draw a spoke from the hub to the rim) or a Disc (a dished face to draw on).
* **Array Around** - a piece drawn on the tire (a tread block) or on the wheel (a spoke), repeated round the axle:
  an Array modifier on the piece itself, so the copies follow every edit of it (Edit Mode) at once; Count and Mirror
  Across (the other half of the tread, across the middle) change it live.  Apply makes the copies real mesh, Remove
  takes the repeat away (the piece stays).

The piece's origin goes to the axle (its look stays), it becomes a child of the tire / wheel (moving the tire moves
it), and a small hidden empty under it holds the step (360 / Count round the axle)."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

TAG = 'mch_tire'                   # on a summoned object: 'TIRE' / 'WHEEL'
PARAMS = 'mch_tire_p'              # its numbers (JSON)
ARR = 'mch_tire_array'             # on a piece: the tire / wheel it is repeated round (its name)
MOD_ARRAY = 'MCH Tire Array'
MOD_MIRROR = 'MCH Tire Mirror'
STEP = 'MCH_TireStep'

# (label, diameter, width / diameter, rim / diameter, shoulder roundness)
PRESETS = {
    'CAR': ('Car', 0.66, 0.33, 0.65, 0.3),
    'TRUCK': ('Truck', 1.0, 0.3, 0.56, 0.2),
    'OFFROAD': ('Off-road', 0.82, 0.4, 0.52, 0.45),
    'MOTO': ('Moto', 0.62, 0.26, 0.62, 0.9),
    'BIKE': ('Bike', 0.7, 0.06, 0.88, 1.0),
    'MECH': ('Mech', 1.2, 0.5, 0.55, 0.12),
}
PRESET_IDS = tuple(PRESETS)
STYLES = (('BARREL', 'Barrel', 'An open rim and a hub: draw a spoke from the hub to the rim, then Array Around'),
          ('DISC', 'Disc', 'A dished disc wheel: draw on its face, then Array Around'))
_BUSY = [False]


def kind_of(ob):
    return ob.get(TAG, '') if ob is not None and getattr(ob, 'type', '') == 'MESH' else ''


def _st(context):
    return context.scene.mch_tire


def _numbers(st):
    return dict(D=st.diameter, w=st.width, rr=st.rim, s=st.shoulder, segs=int(st.segments),
                lines=int(st.tread_lines), style=st.wheel_style)


# --- the shapes --------------------------------------------------------------------------------------------------

def _arc(cx, cr, rad, a0, a1, n):
    return [(cx + rad * math.cos(a0 + (a1 - a0) * i / n), cr + rad * math.sin(a0 + (a1 - a0) * i / n))
            for i in range(n + 1)]


def tire_profile(p):
    """The tire's cross-section [(x along the axle, radius)], a closed loop: the bead at the rim, the sidewall
    (bulging a little), the shoulder (round), the tread band (``lines`` strips), the other side."""
    R = p['D'] / 2
    W = max(1e-3, p['w'] * p['D'])
    r_in = max(0.05, min(0.95, p['rr'])) * R
    H = R - r_in
    sh = max(0.0, min(1.0, p['s'])) * min(W / 2, H) * 0.9
    wb = 0.84 * W
    lines = max(1, int(p['lines']))
    left = [(-wb / 2, r_in), (-W / 2, r_in + 0.42 * H)]
    if sh > 1e-4:
        left += _arc(-W / 2 + sh, R - sh, sh, math.pi, math.pi / 2, 4)
    else:
        left += [(-W / 2, R)]
    x0, x1 = left[-1][0], -left[-1][0]
    band = [(x0 + (x1 - x0) * i / lines, R) for i in range(1, lines)]
    right = [(-x, r) for x, r in reversed(left)]
    inner = [(wb / 2 - wb * i / 3, r_in) for i in range(1, 3)]
    return left + band + right + inner


def wheel_profiles(p):
    """The wheel's cross-sections: [(closed, points)] - a barrel ring (+ a hub from the axle) or one disc wheel."""
    R = p['D'] / 2
    W = max(1e-3, p['w'] * p['D'])
    Rw = max(0.05, min(0.95, p['rr'])) * R
    Ww = 0.84 * W
    lip = min(0.08 * Ww, 0.25 * Rw)
    fl, inn = Rw * 1.05, Rw * 0.9
    barrel = [(-Ww / 2, inn), (-Ww / 2, fl), (-Ww / 2 + lip, fl), (-Ww / 2 + lip, Rw), (Ww / 2 - lip, Rw),
              (Ww / 2 - lip, fl), (Ww / 2, fl), (Ww / 2, inn)]
    rh = 0.24 * Rw
    xd, t = 0.12 * Ww, max(0.05 * Ww, 0.03 * Rw)
    if p.get('style') == 'DISC':
        pts = [(xd - 0.14 * Ww, 0.0), (xd - 0.14 * Ww, rh), (xd, rh * 1.25), (xd, inn)] + barrel + \
              [(xd + t, inn), (xd + t, rh * 1.25), (xd + t + 0.12 * Ww, rh), (xd + t + 0.12 * Ww, 0.0)]
        return [(False, pts)]
    hub = [(xd - 0.2 * Ww, 0.0), (xd - 0.2 * Ww, rh), (xd + 0.1 * Ww, rh), (xd + 0.14 * Ww, rh * 0.6),
           (xd + 0.14 * Ww, 0.0)]
    return [(True, barrel), (False, hub)]


def _revolve(bm, prof, segs, closed):
    """``prof`` [(x, r)] turned round X in ``segs`` steps: a ring (``closed``: the loop joined) or a body from the axle
    to the axle (a radius of 0: one point there)."""
    n = max(8, int(segs))
    rings = []
    for x, r in prof:
        if r < 1e-9:
            rings.append([bm.verts.new((x, 0.0, 0.0))])
        else:
            rings.append([bm.verts.new((x, r * math.cos(2 * math.pi * j / n), r * math.sin(2 * math.pi * j / n)))
                          for j in range(n)])
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for a, b in pairs:
        for j in range(n):
            k = (j + 1) % n
            if len(a) == 1 and len(b) == 1:
                continue
            if len(a) == 1:
                bm.faces.new((a[0], b[k], b[j]))
            elif len(b) == 1:
                bm.faces.new((a[j], a[k], b[0]))
            else:
                bm.faces.new((a[j], a[k], b[k], b[j]))


def build_mesh(me, kind, p):
    """The mesh ``me`` made the tire / wheel of numbers ``p`` (its old geometry replaced)."""
    bm = bmesh.new()
    try:
        if kind == 'TIRE':
            _revolve(bm, tire_profile(p), p['segs'], True)
        else:
            for closed, prof in wheel_profiles(p):
                _revolve(bm, prof, p['segs'], closed)
        bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        bm.normal_update()
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:                                   # (the corners stay sharp, the round shades smooth)
            if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(40):
                e.smooth = False
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def _new(context, kind, p, name):
    me = bpy.data.meshes.new(name)
    build_mesh(me, kind, p)
    ob = bpy.data.objects.new(name, me)
    context.collection.objects.link(ob)
    ob[TAG] = kind
    ob[PARAMS] = json.dumps(p)
    return ob


def rebuild(ob, p):
    if kind_of(ob) not in {'TIRE', 'WHEEL'}:
        return
    if ob.mode == 'EDIT':
        return
    build_mesh(ob.data, kind_of(ob), p)
    ob[PARAMS] = json.dumps(p)


def params(ob):
    try:
        return json.loads(ob.get(PARAMS, '{}'))
    except (TypeError, ValueError):
        return {}


# --- the repeat round the axle ------------------------------------------------------------------------------------

def axle(target):
    """(centre, unit axis) of a tire / wheel in the world."""
    mw = target.matrix_world
    return mw.translation.copy(), (mw.to_3x3() @ Vector((1.0, 0.0, 0.0))).normalized()


def target_for(context, pieces):
    """The tire / wheel the pieces go round: the active one, a selected one, else the nearest to them."""
    act = getattr(context, 'active_object', None)
    if kind_of(act) in {'TIRE', 'WHEEL'}:
        return act
    sel = [o for o in context.selected_objects if kind_of(o) in {'TIRE', 'WHEEL'}]
    if sel:
        return sel[0]
    cands = [o for o in context.scene.objects if kind_of(o) in {'TIRE', 'WHEEL'}]
    if not cands or not pieces:
        return None
    pc = sum((p.matrix_world @ (sum((Vector(c) for c in p.bound_box), Vector()) / 8) for p in pieces),
             Vector()) / len(pieces)

    def dist(o):
        c, a = axle(o)
        d = pc - c
        return (d - a * d.dot(a)).length + abs(d.dot(a))
    return min(cands, key=dist)


def _step_matrix(piece, target, count):
    """The step (360 / count round the axle) in the piece's own space: A^-1 R A (its origin on the axle)."""
    _c, a = axle(target)
    A = piece.matrix_world.to_3x3()
    try:
        Ai = A.inverted()
    except ValueError:
        return Matrix.Identity(4)
    R = Matrix.Rotation(2 * math.pi / max(1, int(count)), 3, a)
    return (Ai @ R @ A).to_4x4()


def _step_empty(piece):
    return next((c for c in piece.children if c.get(STEP)), None)


def set_origin(piece, c):
    """The piece's origin moved to the world point ``c`` (its mesh moved back: it does not move)."""
    mw = piece.matrix_world.copy()
    A = mw.to_3x3()
    try:
        d = A.inverted() @ (mw.translation - c)
    except ValueError:
        return False
    if piece.data.users > 1:
        piece.data = piece.data.copy()
    piece.data.transform(Matrix.Translation(d))
    for ch in piece.children:                              # (its children stay where they are: P' = P T(-d))
        ch.matrix_parent_inverse = Matrix.Translation(d) @ ch.matrix_parent_inverse
    nm = mw.copy()
    nm.translation = c
    piece.matrix_world = nm
    return True


def set_mirror(piece, target, on):
    m = piece.modifiers.get(MOD_MIRROR)
    if on and m is None:
        m = piece.modifiers.new(MOD_MIRROR, 'MIRROR')
        m.use_axis = (True, False, False)
        m.mirror_object = target
        m.show_in_editmode = True
        m.show_on_cage = False
        arr = piece.modifiers.get(MOD_ARRAY)
        if arr is not None:                                # (mirrored first, then the pair goes round)
            mods = list(piece.modifiers)
            ia, im = mods.index(arr), mods.index(m)
            try:
                piece.modifiers.move(im, ia)
            except (AttributeError, TypeError):
                with bpy.context.temp_override(object=piece):
                    bpy.ops.object.modifier_move_to_index(modifier=m.name, index=ia)
    elif not on and m is not None:
        piece.modifiers.remove(m)


def set_count(piece, target, count):
    arr = piece.modifiers.get(MOD_ARRAY)
    em = _step_empty(piece)
    if arr is None or em is None:
        return
    arr.count = max(1, int(count))
    em.matrix_parent_inverse = Matrix.Identity(4)
    em.matrix_basis = _step_matrix(piece, target, count)


def array_round(context, piece, target, count, mirror):
    """The piece repeated round the target's axle (live: an Array modifier on it, a step empty under it)."""
    if piece.get(ARR) and piece.modifiers.get(MOD_ARRAY) is not None and _step_empty(piece) is not None:
        set_mirror(piece, target, mirror)
        set_count(piece, target, count)
        return
    c, _a = axle(target)
    if not set_origin(piece, c):
        return
    mw = piece.matrix_world.copy()
    if piece.parent is not target:
        piece.parent = target
        piece.matrix_world = mw
    em = bpy.data.objects.new(STEP, None)
    em[STEP] = 1
    em.empty_display_size = 0.05
    em.empty_display_type = 'PLAIN_AXES'
    for col in piece.users_collection:
        col.objects.link(em)
    em.parent = piece
    em.matrix_parent_inverse = Matrix.Identity(4)
    em.matrix_basis = _step_matrix(piece, target, count)
    em.hide_select = True
    try:
        em.hide_set(True)
    except RuntimeError:
        pass
    arr = piece.modifiers.new(MOD_ARRAY, 'ARRAY')
    arr.use_relative_offset = False
    arr.use_constant_offset = False
    arr.use_object_offset = True
    arr.offset_object = em
    arr.count = max(1, int(count))
    arr.show_in_editmode = True
    arr.show_on_cage = False
    piece[ARR] = target.name
    set_mirror(piece, target, mirror)


def remove_round(piece):
    for name in (MOD_ARRAY, MOD_MIRROR):
        m = piece.modifiers.get(name)
        if m is not None:
            piece.modifiers.remove(m)
    em = _step_empty(piece)
    if em is not None:
        bpy.data.objects.remove(em)
    if ARR in piece.keys():
        del piece[ARR]


def apply_round(context, piece):
    """The copies made real mesh (the piece's modifiers baked into it), the repeat taken away."""
    dg = context.evaluated_depsgraph_get()
    ev = piece.evaluated_get(dg)
    me = bpy.data.meshes.new_from_object(ev, preserve_all_data_layers=True, depsgraph=dg)
    old = piece.data
    piece.modifiers.clear()
    piece.data = me
    me.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    em = _step_empty(piece)
    if em is not None:
        bpy.data.objects.remove(em)
    if ARR in piece.keys():
        del piece[ARR]


def arrayed(context):
    """The repeated pieces to change: the selected ones - else every piece of the selected tire / wheel."""
    sel = [o for o in context.selected_objects if o.get(ARR)]
    if sel:
        return sel
    act = getattr(context, 'active_object', None)
    if kind_of(act) in {'TIRE', 'WHEEL'}:
        return [o for o in act.children if o.get(ARR) == act.name]
    return []


def _target_of(context, piece):
    return context.scene.objects.get(piece.get(ARR, '')) or piece.parent


# --- live settings ------------------------------------------------------------------------------------------------

def _shape_update(self, context):
    if _BUSY[0]:
        return
    p = _numbers(self)
    for ob in context.selected_objects:
        k = kind_of(ob)
        if k in {'TIRE', 'WHEEL'}:
            rebuild(ob, p)


def _preset_update(self, context):
    if _BUSY[0] or self.preset not in PRESETS:
        return
    _l, D, w, rr, s = PRESETS[self.preset]
    _BUSY[0] = True
    try:
        self.diameter, self.width, self.rim, self.shoulder = D, w, rr, s
    finally:
        _BUSY[0] = False
    _shape_update(self, context)


def _count_update(self, context):
    for pc in arrayed(context):
        t = _target_of(context, pc)
        if t is not None:
            set_count(pc, t, self.count)


def _mirror_update(self, context):
    for pc in arrayed(context):
        t = _target_of(context, pc)
        if t is not None:
            set_mirror(pc, t, self.mirror)


class MCH_PG_Tire(bpy.types.PropertyGroup):
    preset: bpy.props.EnumProperty(name='Preset', items=[(k, v[0], f'{v[0]} tire proportions')
                                                         for k, v in PRESETS.items()],
                                   default='CAR', update=_preset_update)
    diameter: bpy.props.FloatProperty(name='Diameter', default=0.66, min=0.01, soft_max=3.0, unit='LENGTH',
                                      update=_shape_update, description='The tire\'s outside diameter')
    width: bpy.props.FloatProperty(name='Width', default=0.33, min=0.02, max=1.2, update=_shape_update,
                                   description='Its width, of the diameter')
    rim: bpy.props.FloatProperty(name='Rim', default=0.65, min=0.1, max=0.95, update=_shape_update,
                                 description='The rim (the hole in it, the wheel), of the diameter')
    shoulder: bpy.props.FloatProperty(name='Shoulder', default=0.3, min=0.0, max=1.0, update=_shape_update,
                                      description='How round its shoulders (0 square, 1 round)')
    segments: bpy.props.IntProperty(name='Segments', default=64, min=12, max=256, update=_shape_update,
                                    description='Steps round the axle')
    tread_lines: bpy.props.IntProperty(name='Tread Lines', default=8, min=1, max=40, update=_shape_update,
                                       description='Strips across the tread (lines to draw along)')
    wheel_style: bpy.props.EnumProperty(name='Wheel', items=STYLES, default='BARREL', update=_shape_update)
    count: bpy.props.IntProperty(name='Count', default=24, min=1, max=360, update=_count_update,
                                 description='How many times round the axle')
    mirror: bpy.props.BoolProperty(name='Mirror Across', default=False, update=_mirror_update,
                                   description='Its mirror image across the middle of the tire too')


# --- operators ----------------------------------------------------------------------------------------------------

class MCH_OT_tire_add(bpy.types.Operator):
    """Summon a tire (a tire-proportioned ring, its axle along X) or the wheel for it - the selected tire's rim hole,
    put in it - at the 3D cursor: draw on it, then Array Around"""
    bl_idname = 'mch.tire_add'
    bl_label = 'Summon Tire'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=(('TIRE', 'Tire', ''), ('WHEEL', 'Wheel', '')), default='TIRE')

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Tire: Object Mode only')
            return {'CANCELLED'}
        st = _st(context)
        p = _numbers(st)
        act = getattr(context, 'active_object', None)
        tire = act if self.kind == 'WHEEL' and kind_of(act) == 'TIRE' else None
        if tire is not None:                               # (the wheel for this tire: its numbers)
            p = dict(params(tire) or p, style=st.wheel_style, segs=p['segs'])
        ob = _new(context, self.kind, p, 'MCH_Tire' if self.kind == 'TIRE' else 'MCH_Wheel')
        if tire is not None:
            ob.parent = tire
            ob.matrix_world = tire.matrix_world.copy()
        else:
            ob.location = context.scene.cursor.location
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        self.report({'INFO'}, f'{ob.name}: draw on it, then Array Around' +
                    (f' (in "{tire.name}")' if tire is not None else ''))
        return {'FINISHED'}


class MCH_OT_tire_array(bpy.types.Operator):
    """Repeat the selected piece(s) drawn on a tire / wheel round its axle - live: Count and Mirror Across change it,
    an edit of the piece shows on every copy"""
    bl_idname = 'mch.tire_array'
    bl_label = 'Array Around'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Array Around: Object Mode only')
            return {'CANCELLED'}
        pieces = [o for o in context.selected_objects if o.type == 'MESH' and kind_of(o) not in {'TIRE', 'WHEEL'}]
        target = target_for(context, pieces)
        if not pieces or target is None:
            self.report({'WARNING'}, 'Array Around: select the piece(s) you drew (and the tire / wheel)')
            return {'CANCELLED'}
        st = _st(context)
        for pc in pieces:
            array_round(context, pc, target, st.count, st.mirror)
        context.view_layer.objects.active = pieces[0]
        self.report({'INFO'}, f'{len(pieces)} piece(s) x {st.count} round "{target.name}"')
        return {'FINISHED'}


class MCH_OT_tire_array_apply(bpy.types.Operator):
    """Make the copies real mesh (the piece's modifiers baked); the repeat is taken away"""
    bl_idname = 'mch.tire_array_apply'
    bl_label = 'Apply Array'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pcs = arrayed(context)
        if not pcs or context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Apply: select a repeated piece (Object Mode)')
            return {'CANCELLED'}
        for pc in pcs:
            apply_round(context, pc)
        return {'FINISHED'}


class MCH_OT_tire_array_remove(bpy.types.Operator):
    """Take the repeat away (the piece stays as you drew it)"""
    bl_idname = 'mch.tire_array_remove'
    bl_label = 'Remove Array'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        pcs = arrayed(context)
        if not pcs:
            self.report({'WARNING'}, 'Remove: select a repeated piece')
            return {'CANCELLED'}
        for pc in pcs:
            remove_round(pc)
        return {'FINISHED'}


# --- the Shapes page section and the sidebar ----------------------------------------------------------------------

def page_section(b, context, x, width):
    from . import mech_shader_ui as mu
    st = _st(context)
    obj_mode = context.mode == 'OBJECT'

    def fill(sx, sw):
        cells = [mu._cell('tbtn', PRESETS[k][0], ('op', 'mch.tire_preset', {'preset': k}), on=st.preset == k)
                 for k in PRESET_IDS]
        for i in range(0, len(cells), 3):
            mu.row(b, sx, sw, cells[i:i + 3])
        mu.row(b, sx, sw, [mu.number(st, 'diameter', 'Diameter'), mu.number(st, 'width', 'Width')])
        mu.row(b, sx, sw, [mu.number(st, 'rim', 'Rim'), mu.number(st, 'shoulder', 'Shoulder')])
        mu.row(b, sx, sw, [mu.number(st, 'segments', 'Segments'), mu.number(st, 'tread_lines', 'Tread Lines')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Tire', ('op', 'mch.tire_add', {'kind': 'TIRE'}), active=obj_mode)])
        mu.row(b, sx, sw, [mu._cell('tbtn', label, ('op', 'mch.tire_style', {'style': ident}),
                                    on=st.wheel_style == ident) for ident, label, _d in STYLES])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Summon Wheel', ('op', 'mch.tire_add', {'kind': 'WHEEL'}),
                                    active=obj_mode)])
        n = len(arrayed(context)) if obj_mode else 0
        b.note(('note', f'{n} repeated piece(s): Count / Mirror change them live' if n else
                'Draw a piece on the tire or wheel (a tread block, a spoke), select it, then Array Around',
                False, None, None, None, True), sx, sw)
        mu.row(b, sx, sw, [mu.number(st, 'count', 'Count'), mu.prop_cell(st, 'mirror', 'Mirror Across')])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Array Around', ('op', 'mch.tire_array', {}), active=obj_mode)])
        mu.row(b, sx, sw, [mu._cell('tbtn', 'Apply', ('op', 'mch.tire_array_apply', {}), active=n > 0),
                           mu._cell('tbtn', 'Remove', ('op', 'mch.tire_array_remove', {}), active=n > 0)])
    mu.section(b, 'rs_tire', 'Tire & Wheel', x, width, fill)


def draw(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='Tire & Wheel')
    c = box.column(align=True)
    c.prop(st, 'preset', text='')
    c.prop(st, 'diameter')
    c.prop(st, 'width')
    c.prop(st, 'rim')
    c.prop(st, 'shoulder')
    c.prop(st, 'segments')
    c.prop(st, 'tread_lines')
    box.operator('mch.tire_add', text='Summon Tire', icon='MESH_TORUS').kind = 'TIRE'
    box.prop(st, 'wheel_style', expand=True)
    box.operator('mch.tire_add', text='Summon Wheel', icon='MESH_CYLINDER').kind = 'WHEEL'
    c = box.column(align=True)
    c.prop(st, 'count')
    c.prop(st, 'mirror')
    box.operator('mch.tire_array', icon='MOD_ARRAY')
    r = box.row(align=True)
    r.operator('mch.tire_array_apply', text='Apply')
    r.operator('mch.tire_array_remove', text='Remove')


class MCH_OT_tire_preset(bpy.types.Operator):
    """Tire proportions of this kind (the selected tire / wheel changes at once)"""
    bl_idname = 'mch.tire_preset'
    bl_label = 'Tire Preset'
    bl_options = {'INTERNAL', 'UNDO'}
    preset: bpy.props.StringProperty(default='CAR')

    def execute(self, context):
        if self.preset in PRESETS:
            _st(context).preset = self.preset
        return {'FINISHED'}


class MCH_OT_tire_style(bpy.types.Operator):
    """The next wheel's kind: Barrel (an open rim + a hub, for spokes) or Disc"""
    bl_idname = 'mch.tire_style'
    bl_label = 'Wheel Style'
    bl_options = {'INTERNAL', 'UNDO'}
    style: bpy.props.StringProperty(default='BARREL')

    def execute(self, context):
        if self.style in {s[0] for s in STYLES}:
            _st(context).wheel_style = self.style
        return {'FINISHED'}


CLASSES = (MCH_PG_Tire, MCH_OT_tire_add, MCH_OT_tire_array, MCH_OT_tire_array_apply, MCH_OT_tire_array_remove,
           MCH_OT_tire_preset, MCH_OT_tire_style)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_tire = bpy.props.PointerProperty(type=MCH_PG_Tire)


def unregister():
    try:
        del bpy.types.Scene.mch_tire
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
