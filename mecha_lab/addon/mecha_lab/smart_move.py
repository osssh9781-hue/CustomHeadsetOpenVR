"""0.24.123 Smart Move: place a part by hand, the way you would in VR, with the mouse and a 3D mouse.

User: "내가 어떤 오브젝트를 클릭해, 그리고 내가 원하는 메시의 표면에 클릭하면 그 위치로 기존의 로테이션 값은 변하지 않고 가,
그리고 내가 그 위치에서 3D 마우스로 그 오브젝트를 로테이션 하는 거야" / "회전축은 오리진 기준으로 하자".

  * LMB on a part          -> it is held (selected, a ring on its origin, hints in the header)
  * LMB on a surface       -> the held part's ORIGIN goes to that point (+ Lift along the surface normal); its rotation and
                              size do not change; click again anywhere to move it again
  * 3D mouse (NDOF) twist  -> the held part turns about its ORIGIN - Turntable (default: twist round the world's up,
                              tilt round the screen's horizontal, like Blender's view), View (a trackball) or World;
                              Speed / Invert in the panel; the view does not move while a part is held
  * 3D mouse push          -> off by default; "Normal" slides the part along the last surface normal, "Free" in the view
  * Enter / Space / RMB    -> keep (one undo step for the whole hold),  Esc -> the part goes back where it was
  * MMB / wheel / numpad / trackpad -> the view, as always (passed on)

Idle (nothing held) Esc leaves the tool (Select), like every Mecha tool.  Everything the tool needs for a test is plain
math here (``turn_axis``, ``turn_angle``, ``rotate_about``, ``place``, ``cast``); the operator only adds the events.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty
from mathutils import Matrix, Vector

RING_COL = (1.0, 0.62, 0.15, 0.95)        # the Move family's orange
HIT_COL = (0.35, 0.8, 1.0, 0.95)
NAV_TYPES = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'TRACKPADPAN',
             'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM', 'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}
CONFIRM_TYPES = {'RET', 'NUMPAD_ENTER', 'SPACE', 'RIGHTMOUSE', 'E'}   # (E: the key that started a hold in any tool ends it too)
ACTIVE = [None]       # the running operator (tests / the real-window check look here)
_DRAW = [None]


def _redraw(self, context):
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


class MCH_PG_Smart(bpy.types.PropertyGroup):
    axes: EnumProperty(name='Turn Axes', items=(
        ('TURNTABLE', 'Turntable', '0.24.125 like Blender\'s view turning: twist = round the world\'s up (Z, a turntable), '
                                   'tilt = round the screen\'s horizontal, roll = round the view axis'),
        ('VIEW', 'View', 'The 3D mouse turns the part about the axes of the view you look through (tilt = up / down on '
                         'screen, twist = round the screen\'s up - tilted with the view, a trackball)'),
        ('WORLD', 'World', 'The 3D mouse turns the part about the world axes (twist = round Z up, tilt = round X), '
                           'whatever the view')), default='TURNTABLE', update=_redraw)
    speed: FloatProperty(name='Speed', description='How fast the 3D mouse turns the part (1 = about as fast as it '
                         'turns the view)', default=1.0, min=0.05, max=8.0, soft_min=0.2, soft_max=4.0)
    invert: BoolProperty(name='Invert', description='Turn the other way round', default=False)
    push: EnumProperty(name='Push', items=(
        ('OFF', 'Off', 'The 3D mouse only turns the part'),
        ('NORMAL', 'Normal', 'Pushing / pulling the 3D mouse slides the part along the normal of the surface it was '
                             'last put on (up / down from it)'),
        ('FREE', 'Free', 'The 3D mouse also slides the part along the axes of the view')), default='FREE', update=_redraw)
    show_help: BoolProperty(name='How to use', default=False, description='Show the short how-to lines')
    push_speed: FloatProperty(name='Push Speed', description='How far a full push moves the part in one second, as '
                              'a share of the view distance', default=0.5, min=0.02, max=5.0)
    lift: FloatProperty(name='Lift', description='The origin is put this far off the surface, along its normal',
                        default=0.0, soft_min=-1.0, soft_max=1.0, step=1, precision=3, unit='LENGTH')


# ---- the maths ------------------------------------------------------------------------------------------------------

def turn_axis(rot, mode, view_matrix=None):
    """The world axis a 3D-mouse rotation vector (view space: X right, Y up, Z towards you) turns about.
    TURNTABLE (0.24.125, user: "약간 축이 돌아가 있어" - the View twist was round the screen's up, tilted with a view that
    looks down): twist = round the world's up (Z), tilt = round the view's horizontal, roll = round the view axis -
    Blender's own turntable view turning.  VIEW: all three through the view's rotation (a trackball).  WORLD: tilt
    forward = round world X, twist = round world Z (up), roll = round world Y - the front view's mapping, whatever the
    view.  No view: the front view's mapping for every mode."""
    v = Vector(rot)
    if view_matrix is None:
        return Vector((v.x, -v.z, v.y))
    inv = view_matrix.to_3x3().inverted_safe()
    if mode == 'VIEW':
        return inv @ v
    if mode == 'TURNTABLE':
        vx = (inv @ Vector((1.0, 0.0, 0.0))).normalized()
        vz = (inv @ Vector((0.0, 0.0, 1.0))).normalized()
        return vx * v.x + Vector((0.0, 0.0, 1.0)) * v.y + vz * v.z
    return Vector((v.x, -v.z, v.y))


def turn_angle(rot, dt, speed=1.0, invert=False):
    """Radians for one motion event: the vector's length is the angle where 1.0 = 360 deg (Blender's NDOF data),
    scaled by the time since the last event (clamped: a first / stalled event is not a jump)."""
    dt = dt if dt and dt > 0.0 else 1.0 / 60.0
    dt = min(dt, 0.1)
    ang = Vector(rot).length * 2.0 * math.pi * dt * speed
    return -ang if invert else ang


def rotate_about(matrix, axis, angle, pivot):
    """``matrix`` turned by ``angle`` (rad) round the world ``axis`` through the world ``pivot`` (the origin stays)."""
    axis = Vector(axis)
    if axis.length < 1e-12 or abs(angle) < 1e-12:
        return matrix.copy()
    rot = Matrix.Rotation(angle, 4, axis.normalized())
    pivot = Vector(pivot)
    return Matrix.Translation(pivot) @ rot @ Matrix.Translation(-pivot) @ matrix


def place(matrix, hit, normal=None, lift=0.0):
    """``matrix`` with its translation at ``hit`` (+ lift along the normal) - the rotation and the scale untouched."""
    m = matrix.copy()
    p = Vector(hit)
    if normal is not None and lift:
        n = Vector(normal)
        if n.length > 1e-9:
            p = p + n.normalized() * lift
    m.translation = p
    return m


def cast(scene, depsgraph, origin, direction, skip=()):
    """The first mesh surface along a ray that is not one of ``skip`` (object names): (location, normal, object) or
    None.  The ray goes on through skipped objects."""
    o, d = Vector(origin), Vector(direction)
    if d.length < 1e-12:
        return None
    d.normalize()
    for _ in range(8):
        try:
            hit, loc, nor, _i, hob, _m = scene.ray_cast(depsgraph, o, d)
        except (AttributeError, RuntimeError, TypeError):
            return None
        if not hit or hob is None:
            return None
        ob = bpy.data.objects.get(hob.name)
        if ob is not None and ob.type == 'MESH' and ob.name not in skip:
            n = Vector(nor)
            return Vector(loc), (n.normalized() if n.length > 1e-9 else Vector((0.0, 0.0, 1.0))), ob
        o = Vector(loc) + d * 1e-4
    return None


def hit_under(context, xy, skip=()):
    """``cast`` from the mouse: (location, normal, object) or None."""
    try:
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        if region is None or rv3d is None:
            return None
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    except (AttributeError, RuntimeError, TypeError, ValueError):
        return None
    return cast(context.scene, context.evaluated_depsgraph_get(), o, d, skip)


def selectable(ob):
    try:
        return ob is not None and ob.type == 'MESH' and not ob.hide_get() and not ob.hide_select and not ob.hide_viewport
    except (AttributeError, RuntimeError, ReferenceError):
        return False


def ndof_apply(ob, data, st, rv3d, last_normal=None):
    """One 3D-mouse motion event on ``ob``: turned about its ORIGIN (Turntable / View / World axes, Speed, Invert) and, with Push
    on, slid - Normal: along ``last_normal`` (the surface it was last put on; none known: as Free), Free: along the view's
    axes.  Returns (radians turned, world step)."""
    mode = getattr(st, 'axes', 'TURNTABLE')
    speed = getattr(st, 'speed', 1.0)
    invert = getattr(st, 'invert', False)
    push = getattr(st, 'push', 'FREE')
    view = rv3d.view_matrix if rv3d is not None else None
    rot = Vector(data.rotation)
    dt = float(getattr(data, 'time_delta', 0.0) or 0.0)
    m = ob.matrix_world
    ang = 0.0
    if rot.length > 1e-9:
        axis = turn_axis(rot, mode, view)
        ang = turn_angle(rot, dt, speed, invert)
        m = rotate_about(m, axis, ang, m.translation)
    step = Vector((0.0, 0.0, 0.0))
    if push != 'OFF':
        tr = Vector(data.translation)
        if tr.length > 1e-9:
            dtc = min(dt if dt > 0.0 else 1.0 / 60.0, 0.1)
            dist = (rv3d.view_distance if rv3d is not None else 1.0) * getattr(st, 'push_speed', 0.5) * dtc
            if push == 'NORMAL' and last_normal is not None:
                step = Vector(last_normal) * (tr.y * dist)       # pull the cap up = up the normal, push down = down
            else:
                step = turn_axis(tr, 'VIEW', view) * dist
            m = m.copy()
            m.translation = m.translation + step
    ob.matrix_world = m
    return ang, step


def ndof_parts_on(context):
    """0.24.124 the corner card's 3D MOUSE: Parts - the 3D mouse drives the selected part in any tool."""
    return bool(getattr(context.window_manager, 'mch_ndof_parts', False))


def mecha_workspace(context):
    try:
        from . import tool_state as ts
        return ts.is_mecha_workspace(context.workspace)
    except (AttributeError, ReferenceError, ImportError):
        return False


# ---- the operator -----------------------------------------------------------------------------------------------------

def _draw(op, context):
    """A ring on the held part's origin (with its name) and a mark where it was last put (the surface normal)."""
    try:
        import blf
        import gpu
        from bpy_extras import view3d_utils
        from gpu_extras.batch import batch_for_shader
        ob = bpy.data.objects.get(op.ob_name) if op.ob_name else None
        if ob is None or context.region is None or context.region_data is None:
            return
        region, rv3d = context.region, context.region_data
        ui = context.preferences.system.ui_scale
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        o2 = view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world.translation)
        if o2 is not None:
            r = 14.0 * ui
            pts = [(o2.x + r * math.cos(a), o2.y + r * math.sin(a)) for a in (2 * math.pi * i / 40 for i in range(40))]
            sh.uniform_float('color', RING_COL)
            batch_for_shader(sh, 'LINE_LOOP', {'pos': pts}).draw(sh)
            cross = [(o2.x - r * 0.5, o2.y), (o2.x + r * 0.5, o2.y), (o2.x, o2.y - r * 0.5), (o2.x, o2.y + r * 0.5)]
            batch_for_shader(sh, 'LINES', {'pos': cross}).draw(sh)
            blf.size(0, 11 * ui)
            blf.color(0, *RING_COL)
            blf.position(0, o2.x + r + 4 * ui, o2.y + 4 * ui, 0)
            blf.draw(0, ob.name)
        if op.last_hit is not None:
            loc, nor = op.last_hit
            h2 = view3d_utils.location_3d_to_region_2d(region, rv3d, loc)
            scale = max(rv3d.view_distance * 0.06, 1e-3)
            n2 = view3d_utils.location_3d_to_region_2d(region, rv3d, loc + nor * scale)
            if h2 is not None:
                r = 5.0 * ui
                sh.uniform_float('color', HIT_COL)
                pts = [(h2.x + r * math.cos(a), h2.y + r * math.sin(a)) for a in (2 * math.pi * i / 20 for i in range(20))]
                batch_for_shader(sh, 'LINE_LOOP', {'pos': pts}).draw(sh)
                if n2 is not None:
                    batch_for_shader(sh, 'LINES', {'pos': [(h2.x, h2.y), (n2.x, n2.y)]}).draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


class MCH_OT_smart_move(bpy.types.Operator):
    """Smart Move: click a part to hold it, click a surface - its origin goes there (rotation and size unchanged);
    the 3D mouse turns it about its origin.  Enter / Space / RMB keep, Esc puts it back"""
    bl_idname = 'mch.smart_move'
    bl_label = 'Smart Move'
    bl_options = {'UNDO'}          # (no REGISTER: a redo would undo the hold and have nothing to redo)

    # 0.24.124 (user: "스마트 무브는 모든 툴에 넣어줘") E in any Mecha tool: the part under the mouse, else the selected one
    from_key: BoolProperty(default=False, options={'SKIP_SAVE', 'HIDDEN'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    # ---- state ----
    def _setup(self):
        self.ob_name = ''
        self.orig = None
        self.last_hit = None
        self.turned = 0.0
        self.prev_sel = []
        self.prev_active = ''
        self.tool0 = 'SMART'
        self.t_start = 0.0

    def invoke(self, context, event):
        import time
        self._setup()
        xy = (event.mouse_region_x, event.mouse_region_y)
        over = False
        try:
            from . import quick_hud
            over = quick_hud.over_ui(context, *xy)
        except (AttributeError, ImportError, TypeError):
            pass
        if over and not self.from_key:
            return {'PASS_THROUGH'}
        if self.from_key and not mecha_workspace(context):
            return {'PASS_THROUGH'}             # (E outside MECHA LAB stays Blender's)
        ob = self._target_for(context, xy, over)
        if ob is None:
            if self.from_key:
                self.report({'INFO'}, 'Smart Move: put the mouse on a part (or select one) and press E')
                return {'CANCELLED'}
            return {'PASS_THROUGH'}             # empty space / nothing to hold: Blender's click goes on
        try:
            from . import tool_state as ts
            self.tool0 = ts.effective_tool(context)
        except (AttributeError, KeyError, TypeError, ImportError):
            self.tool0 = 'SMART'
        self.t_start = time.perf_counter()
        self.ob_name = ob.name
        self.orig = ob.matrix_world.copy()
        try:
            self.prev_sel = [o.name for o in context.selected_objects]
            self.prev_active = context.view_layer.objects.active.name if context.view_layer.objects.active else ''
            for o in context.selected_objects:
                o.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
        except (AttributeError, RuntimeError, ReferenceError):
            pass
        self._hook(context)
        self._header(context)
        ACTIVE[0] = self
        try:
            context.window_manager.modal_handler_add(self)
        except (AttributeError, RuntimeError):
            self._unhook(context)
            ACTIVE[0] = None
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _target_for(self, context, xy, over=False):
        """The part a press (the Smart Move tool) or E (any tool) holds: the mesh under the mouse; with E and nothing
        under the mouse (or the mouse on the drawn UI) the selected active part.  None: nothing to hold."""
        hit = None if over else hit_under(context, xy)
        ob = hit[2] if hit is not None and selectable(hit[2]) else None
        if ob is None and self.from_key:
            try:
                act = context.view_layer.objects.active
                if act is not None and act.type in {'MESH', 'CURVE', 'EMPTY', 'FONT', 'SURFACE', 'META'} \
                        and not act.hide_get() and act.select_get():
                    ob = act
            except (AttributeError, RuntimeError, ReferenceError):
                ob = None
        return ob

    def _hook(self, context):
        if _DRAW[0] is None:
            try:
                _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (self, context), 'WINDOW', 'POST_PIXEL')
            except (AttributeError, RuntimeError, ValueError):
                _DRAW[0] = None

    def _unhook(self, context):
        if _DRAW[0] is not None:
            try:
                bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            except (AttributeError, RuntimeError, ValueError):
                pass
            _DRAW[0] = None
        try:
            context.area.header_text_set(None)
        except (AttributeError, RuntimeError):
            pass
        _redraw(None, context)

    def _header(self, context):
        st = getattr(context.scene, 'mch_smart', None)
        axes = getattr(st, 'axes', 'TURNTABLE').title()
        try:
            push = getattr(st, 'push', 'FREE')
            context.area.header_text_set(
                f'Smart Move  |  {self.ob_name}  |  LMB on a surface: put it there (origin, same rotation)  |  '
                f'3D mouse: turn about the origin ({axes} axes, speed {getattr(st, "speed", 1.0):.2g})'
                + ('' if push == 'OFF' else f', push: {push.title()}')
                + '  |  Enter / Space / RMB' + (' / E' if self.from_key else '') + ': keep   Esc: put back   MMB / wheel: view')
        except (AttributeError, RuntimeError):
            pass

    def _object(self):
        return bpy.data.objects.get(self.ob_name) if self.ob_name else None

    def _finish(self, context, keep):
        ob = self._object()
        if not keep and ob is not None and self.orig is not None:
            ob.matrix_world = self.orig
            try:
                for o in context.selected_objects:
                    o.select_set(False)
                for name in self.prev_sel:
                    o = bpy.data.objects.get(name)
                    if o is not None:
                        o.select_set(True)
                act = bpy.data.objects.get(self.prev_active) if self.prev_active else None
                context.view_layer.objects.active = act if act is not None else ob
            except (AttributeError, RuntimeError, ReferenceError):
                pass
        self._unhook(context)
        ACTIVE[0] = None
        return {'FINISHED'} if keep else {'CANCELLED'}

    # ---- one event of the hold ----
    def _place(self, context, xy):
        ob = self._object()
        hit = hit_under(context, xy, skip={self.ob_name})
        if ob is None or hit is None:
            return False
        loc, nor, _target = hit
        st = getattr(context.scene, 'mch_smart', None)
        ob.matrix_world = place(ob.matrix_world, loc, nor, getattr(st, 'lift', 0.0))
        self.last_hit = (loc, nor)
        return True

    def _ndof(self, context, event):
        ob = self._object()
        data = getattr(event, 'ndof_motion', None)
        if ob is None or data is None:
            return False
        st = getattr(context.scene, 'mch_smart', None)
        ang, _step = ndof_apply(ob, data, st, getattr(context, 'region_data', None),
                                self.last_hit[1] if self.last_hit is not None else None)
        self.turned += abs(ang)
        return True

    def modal(self, context, event):
        ob = self._object()
        if ob is None:                                    # undone away / deleted meanwhile
            return self._finish(context, True)
        try:
            from . import tool_state as ts
            if ts.effective_tool(context) != self.tool0:   # the tool was changed (strip / pie / key): keep as is
                return self._finish(context, True)
        except (AttributeError, KeyError, TypeError, ImportError):
            pass
        et, ev = event.type, event.value
        if getattr(event, 'is_repeat', False):           # (a held E repeats: not a second press)
            return {'RUNNING_MODAL'}
        if et == 'E' and ev == 'PRESS':
            import time
            if time.perf_counter() - self.t_start < 0.25:  # (the press that started the hold, seen again)
                return {'RUNNING_MODAL'}
        if et == 'NDOF_MOTION':
            self._ndof(context, event)
            _redraw(None, context)
            return {'RUNNING_MODAL'}
        if et in NAV_TYPES or et.startswith('NDOF_BUTTON') or (et.startswith('NUMPAD_') and et != 'NUMPAD_ENTER'):
            return {'PASS_THROUGH'}
        if et == 'LEFTMOUSE':
            if ev != 'PRESS':
                return {'RUNNING_MODAL'}
            xy = (event.mouse_region_x, event.mouse_region_y)
            try:
                from . import quick_hud
                if quick_hud.over_ui(context, *xy):
                    return {'PASS_THROUGH'}
            except (AttributeError, ImportError, TypeError):
                pass
            self._place(context, xy)
            self._header(context)
            _redraw(None, context)
            return {'RUNNING_MODAL'}
        if et in CONFIRM_TYPES and ev == 'PRESS':
            return self._finish(context, True)
        if et == 'ESC' and ev == 'PRESS':
            return self._finish(context, False)
        return {'PASS_THROUGH'}


class MCH_OT_smart_ndof(bpy.types.Operator):
    """3D mouse on the selected part (the corner card's 3D MOUSE: Parts): it turns about its origin and slides, in any
    tool; with View (default) the 3D mouse moves the view as always"""
    bl_idname = 'mch.smart_ndof'
    bl_label = '3D Mouse: Part'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        if not ndof_parts_on(context) or ACTIVE[0] is not None or not mecha_workspace(context):
            return {'PASS_THROUGH'}
        data = getattr(event, 'ndof_motion', None)
        ob = getattr(context.view_layer.objects, 'active', None)
        try:
            ok = data is not None and ob is not None and ob.select_get() and not ob.hide_get()
        except (AttributeError, RuntimeError, ReferenceError):
            ok = False
        if not ok:
            return {'PASS_THROUGH'}
        st = getattr(context.scene, 'mch_smart', None)
        ndof_apply(ob, data, st, getattr(context, 'region_data', None))
        if getattr(data, 'progress', '') == 'FINISHING':          # one undo step per gesture
            try:
                bpy.ops.ed.undo_push(message='3D Mouse Move')
            except (RuntimeError, AttributeError):
                pass
        _redraw(None, context)
        return {'FINISHED'}


class MCH_OT_ndof_parts(bpy.types.Operator):
    """What the 3D mouse drives: the view (as always) or the selected part (turned about its origin, slid), in any tool"""
    bl_idname = 'mch.ndof_parts'
    bl_label = '3D Mouse: View / Parts'
    bl_options = {'INTERNAL'}

    on: BoolProperty(default=True)

    def execute(self, context):
        context.window_manager.mch_ndof_parts = bool(self.on)
        self.report({'INFO'}, '3D mouse: ' + ('the selected part (any tool)' if self.on else 'the view'))
        _redraw(None, context)
        return {'FINISHED'}


# ---- the tool ----------------------------------------------------------------------------------------------------------

class MCH_TOOL_smart_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.smart_move'
    bl_label = 'Mecha Smart Move'
    bl_description = ('0.24.123 Smart Move: click a part to hold it, click a surface - its origin goes there (same\n'
                      'rotation and size); the 3D mouse turns it about its origin.  Enter / Space / RMB keep, Esc back')
    bl_icon = 'ops.transform.translate'
    bl_widget = None
    bl_keymap = (
        ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.smart_move', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        draw(layout, context)


def draw(layout, context):
    st = getattr(context.scene, 'mch_smart', None)
    if st is None:
        return
    box = layout.box()
    row = box.row(align=True)
    row.label(text='Smart Move', icon='OBJECT_ORIGIN')
    row.prop(st, 'show_help', text='', icon='TRIA_DOWN' if st.show_help else 'TRIA_RIGHT', emboss=False)
    if st.show_help:                               # 0.24.124 (user: "기능 설명은 접을 수 있게") folded by default
        col = box.column(align=True)
        col.label(text='Click a part: hold it.  Click a surface: its origin goes there.')
        col.label(text='3D mouse: turn about the origin.  Enter / RMB keep, Esc back.')
        col.label(text='E in any tool: hold the part under the mouse (or the selected one).')
    wm = context.window_manager
    if hasattr(wm, 'mch_ndof_parts'):
        row = box.row(align=True)
        row.label(text='3D Mouse')
        row.prop(wm, 'mch_ndof_parts', text='View', toggle=True, invert_checkbox=True)
        row.prop(wm, 'mch_ndof_parts', text='Parts', toggle=True)
    row = box.row(align=True)
    row.label(text='Turn Axes')
    row.prop(st, 'axes', expand=True)
    row = box.row(align=True)
    row.prop(st, 'speed')
    row.prop(st, 'invert', toggle=True)
    row = box.row(align=True)
    row.label(text='Push')
    row.prop(st, 'push', expand=True)
    if st.push != 'OFF':
        box.prop(st, 'push_speed')
    box.prop(st, 'lift')


def top_bar_groups(context, tool):
    """0.24.123 the Mecha top bar for Smart Move: Turn axes / speed / invert, Push, Lift."""
    st = getattr(context.scene, 'mch_smart', None)
    if st is None or tool != 'SMART':
        return []
    from .top_bar import _enum_segs, _mini, _seg
    turn = _enum_segs(st, 'axes', (('TURNTABLE', 'Turntable'), ('VIEW', 'View'), ('WORLD', 'World')))
    turn.append(_mini('Speed', st, 'speed', 130))
    turn.append(_seg('Invert', st, 'invert'))
    push = _enum_segs(st, 'push', (('OFF', 'Off'), ('NORMAL', 'Normal'), ('FREE', 'Free')))
    if st.push != 'OFF':
        push.append(_mini('Push Speed', st, 'push_speed', 150))
    return [('Turn', turn), ('Push', push), ('Place', [_mini('Lift', st, 'lift', 140)])]


CLASSES = (MCH_PG_Smart, MCH_OT_smart_move, MCH_OT_smart_ndof, MCH_OT_ndof_parts)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_smart = bpy.props.PointerProperty(type=MCH_PG_Smart)
    bpy.types.WindowManager.mch_ndof_parts = BoolProperty(
        name='3D Mouse: Parts', default=False, update=_redraw,
        description='The 3D mouse drives the selected part (turn about its origin, push) in any tool; off = the view')
    try:
        bpy.utils.register_tool(MCH_TOOL_smart_move, after={'mecha.silhouette_move'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_smart_move, separator=True, group=False)
        except (ValueError, RuntimeError, KeyError):
            pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_smart_move)
    except (ValueError, RuntimeError, KeyError, AttributeError):
        pass
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    ACTIVE[0] = None
    for owner, name in ((bpy.types.Scene, 'mch_smart'), (bpy.types.WindowManager, 'mch_ndof_parts')):
        try:
            delattr(owner, name)
        except (AttributeError, RuntimeError):
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except (RuntimeError, ValueError):
            pass
