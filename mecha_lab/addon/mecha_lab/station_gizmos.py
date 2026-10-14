"""Viewport handles for the Station Primitive (gizmos, no modal operator).

* a dot on every station: click = make it active
* a + in the middle of every segment: click = insert a station there
* 0.15 (same style as the ghost primitive): active station = dials for Up /
  Down, Left / Right and Twist (turned toward the viewer so they follow the
  mouse), an arrow for the length, squares for the widths and thicknesses;
  a dot outside every bend cycles the fold shape (right angle -> bands).

Placement is computed by ``station_handles`` (pure, tested headless); drawing
and dragging need a real viewport.
"""
import math

import bpy
from mathutils import Matrix, Vector

from . import station_primitive as sp
from . import tool_state as ts

SELECT_NATIVE = {'builtin.move', 'builtin.select', 'builtin.select_box', 'builtin.select_circle',
                 'builtin.select_lasso'}
COL_DOT = (0.75, 0.78, 0.84)
COL_ACTIVE = (1.0, 0.62, 0.16)
COL_WIDTH = (0.35, 0.83, 0.55)
COL_HEIGHT = (0.31, 0.70, 1.0)
COL_LEN = (0.9, 0.9, 0.9)


def _basis(origin, z, x_hint):
    """4x4 matrix with +Z along ``z`` (the gizmo's axis) at ``origin``."""
    z = Vector(z).normalized()
    x = Vector(x_hint)
    x = (x - z * x.dot(z))
    if x.length < 1e-6:
        x = z.orthogonal()
    x.normalize()
    y = z.cross(x)
    m = Matrix((x, y, z)).transposed().to_4x4()
    m.translation = Vector(origin)
    return m


def facing(axis, view_dir):
    """+1 when a dial around ``axis`` faces the viewer, else -1.  Blender dials
    turn counter-clockwise as seen from their own +Z, so a dial whose axis
    points away from the viewer turned the opposite way to the mouse (0.15)."""
    if view_dir is None:
        return 1.0
    return 1.0 if Vector(axis).dot(-Vector(view_dir)) >= 0.0 else -1.0


def station_handles(ob, view_dir=None):
    """Handle placement in WORLD space (0.15 layout, like the ghost primitive):
    'dots' [(index, matrix)], 'plus' [(index, matrix)], 'folds' [(index, matrix)]
    (the dot on the outside of every bend: click = fold shape), and for the
    active station > 0: dials 'up' (Up / Down), 'side' (Left / Right), 'twist',
    the 'length' arrow and the squares 'width_r', 'width_l', 'height',
    'height_bot'.  'signs' = +1 / -1 per dial (dial turned toward the viewer)."""
    p = ob.mch_station
    mw = ob.matrix_world
    rot = mw.to_3x3().normalized()
    frames = sp.station_frames(ob)
    out = {'dots': [], 'plus': [], 'folds': [], 'signs': {}}
    for i, (P, X, T, Z) in enumerate(frames):
        out['dots'].append((i, _basis(mw @ Vector(P), rot @ Vector(T), rot @ Vector(X))))
        if i > 0:
            mid = (Vector(P) + Vector(frames[i - 1][0])) / 2
            out['plus'].append((i, _basis(mw @ mid, rot @ Vector(T), rot @ Vector(X))))
    for i in range(1, min(len(frames), len(p.stations))):
        st = p.stations[i]
        up, side = sp.total_bend(st)
        if abs(up) + abs(side) < 1e-6:
            continue
        P0, X0, _T0, Z0 = (Vector(v) for v in frames[i - 1])
        inside = (Z0 * up + X0 * side).normalized()
        out['folds'].append((i, _basis(mw @ (P0 - inside * sp.profile_size(st) * 1.15), rot @ -inside,
                                       rot @ X0)))
    i = p.active
    if 0 < i < len(frames) and i < len(p.stations):
        P0, X0, T0, Z0 = (Vector(v) for v in frames[i - 1])
        P1, X1, T1, Z1 = (Vector(v) for v in frames[i])
        st = p.stations[i]
        for name, origin, axis, hint in (('up', P0, X0, T0), ('side', P0, -Z0, T0), ('twist', P1, T1, Z1)):
            sign = facing(rot @ axis, view_dir)
            out['signs'][name] = sign
            out[name] = _basis(mw @ origin, rot @ (axis * sign), rot @ hint)
        start_run = P1 - T1 * st.length
        out['length'] = _basis(mw @ start_run, rot @ T1, rot @ Z1)
        out['width_r'] = _basis(mw @ P1, rot @ X1, rot @ Z1)
        out['width_l'] = _basis(mw @ P1, rot @ -X1, rot @ Z1)
        out['height'] = _basis(mw @ P1, rot @ Z1, rot @ X1)
        out['height_bot'] = _basis(mw @ P1, rot @ -Z1, rot @ X1)
    elif i == 0 and len(p.stations):
        P1, X1, T1, Z1 = (Vector(v) for v in frames[0])
        out['width_r'] = _basis(mw @ P1, rot @ X1, rot @ Z1)
        out['width_l'] = _basis(mw @ P1, rot @ -X1, rot @ Z1)
        out['height'] = _basis(mw @ P1, rot @ Z1, rot @ X1)
        out['height_bot'] = _basis(mw @ P1, rot @ -Z1, rot @ X1)
    return out


SIGNS = {}           # (object, station, dial) -> +1 / -1 : the dial was turned toward the viewer
ANGLE_KEYS = {'bend_angle', 'bend_dir', 'bend_up', 'bend_side', 'twist'}
DIAL_KEY = {'up': 'bend_up', 'side': 'bend_side', 'twist': 'twist'}


def _station(ob_name, index):
    ob = bpy.data.objects.get(ob_name)
    if ob is None or not sp.is_live(ob):
        return None, None
    p = ob.mch_station
    if index >= len(p.stations):
        return ob, None
    return ob, p.stations[index]


# 0.14.3: a handle drag changes properties directly, which makes no undo step
# of its own: Ctrl+Z then jumped back past the creation of the primitive (it
# vanished and the blue ghost box showed up).  One undo step is pushed when a
# drag pauses / ends.
UNDO = {'last': 0.0, 'pending': False}
UNDO_SETTLE = 0.35


def _clock():
    import time
    return time.monotonic()


def note_handle_edit(now=None):
    UNDO['last'] = _clock() if now is None else now
    UNDO['pending'] = True
    if not bpy.app.background and not bpy.app.timers.is_registered(_undo_timer):
        bpy.app.timers.register(_undo_timer, first_interval=UNDO_SETTLE + 0.05)


def flush_handle_undo(now=None):
    """Push the undo step if the last handle edit is old enough.  Returns
    True when a step was pushed (testable without a window)."""
    now = _clock() if now is None else now
    if not UNDO['pending'] or now - UNDO['last'] < UNDO_SETTLE:
        return False
    UNDO['pending'] = False
    try:
        bpy.ops.ed.undo_push(message='Station Primitive handle')
    except RuntimeError:
        win = next(iter(bpy.context.window_manager.windows), None) if bpy.context.window_manager else None
        if win is None:
            return False
        try:
            with bpy.context.temp_override(window=win):
                bpy.ops.ed.undo_push(message='Station Primitive handle')
        except RuntimeError:
            return False
    return True


def _undo_timer():
    if not UNDO['pending']:
        return None
    if _clock() - UNDO['last'] < UNDO_SETTLE:
        return 0.1
    flush_handle_undo()
    return None


def _dial_factor():
    from .workspace_ui import dial_factor
    return dial_factor()


def make_accessors(ob_name, index, key):
    """(get, set) for a gizmo target; angles in radians for the dials.  With
    Left = Right the right width handle edits the shared (left) value."""
    def get():
        ob, st = _station(ob_name, index)
        if st is None:
            return 0.0
        k = key
        if key == 'width_r' and ob.mch_station.sym_lr:
            k = 'width_l'
        v = getattr(st, k)
        if key in ANGLE_KEYS:
            return math.radians(v) * SIGNS.get((ob_name, index, key), 1.0) * _dial_factor()
        return v

    def set_(value):
        ob, st = _station(ob_name, index)
        if st is None:
            return
        k = key
        if key == 'width_r' and ob.mch_station.sym_lr:
            k = 'width_l'
        if key in ANGLE_KEYS:
            value = math.degrees(value) * SIGNS.get((ob_name, index, key), 1.0) * _dial_factor()
            if key in {'bend_angle', 'bend_up', 'bend_side'}:
                st.world = False
        elif key in {'width_l', 'width_r', 'height_top', 'height_bot'}:
            value = max(0.0005, value)
        elif key == 'length':
            value = max(0.0, value)
        setattr(st, k, value)
        note_handle_edit()
    return get, set_


def _ui_ok(context):
    ob = context.active_object
    if not sp.is_live(ob) or context.mode != 'OBJECT':
        return False
    try:
        tool = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        tool = ''
    return tool == 'PRIMITIVE' or ts.native_tool_id(context) in SELECT_NATIVE


def _sig(ob):
    p = ob.mch_station
    folds = tuple(j for j in range(1, len(p.stations)) if any(abs(v) > 1e-6 for v in sp.total_bend(p.stations[j])))
    return (ob.name, len(p.stations), p.active, p.sym_lr, folds)


class MCH_GGT_station_handles(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_station_handles'
    bl_label = 'Station Primitive Handles'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'3D', 'PERSISTENT', 'SHOW_MODAL_ALL'}

    @classmethod
    def poll(cls, context):
        return _ui_ok(context)

    def setup(self, context):
        self.sig = None
        self.items = {}
        self._build(context)

    def _clear(self):
        for gz in list(self.gizmos):
            self.gizmos.remove(gz)
        self.items = {}

    def _build(self, context):
        ob = context.active_object
        p = ob.mch_station
        self._clear()
        self.base = {}
        self.sig = _sig(ob)
        for i in range(len(p.stations)):
            gz = self.gizmos.new('GIZMO_GT_move_3d')
            gz.draw_style = 'RING_2D'
            gz.draw_options = {'ALIGN_VIEW'}
            gz.target_set_operator('mch.station_select').index = i
            gz.scale_basis = 0.09
            gz.color = COL_ACTIVE if i == p.active else COL_DOT
            gz.alpha = 0.9
            gz.color_highlight = COL_ACTIVE
            gz.alpha_highlight = 1.0
            self.items[('dot', i)] = gz
        for i in range(1, len(p.stations)):
            gz = self.gizmos.new('GIZMO_GT_move_3d')
            gz.draw_style = 'CROSS_2D'
            gz.draw_options = {'ALIGN_VIEW'}
            gz.target_set_operator('mch.station_insert').index = i
            gz.scale_basis = 0.06
            gz.color = COL_DOT
            gz.alpha = 0.6
            gz.color_highlight = COL_ACTIVE
            gz.alpha_highlight = 1.0
            self.items[('plus', i)] = gz
        i = p.active
        specs = []
        if i > 0:
            specs += [('up', 'GIZMO_GT_dial_3d', 'bend_up', COL_ACTIVE, 0.6),
                      ('side', 'GIZMO_GT_dial_3d', 'bend_side', COL_WIDTH, 0.5),
                      ('twist', 'GIZMO_GT_dial_3d', 'twist', COL_HEIGHT, 0.4),
                      ('length', 'GIZMO_GT_arrow_3d', 'length', COL_LEN, 0.9)]
        specs += [('width_r', 'GIZMO_GT_arrow_3d', 'width_r', COL_WIDTH, 0.5),
                  ('height', 'GIZMO_GT_arrow_3d', 'height_top', COL_HEIGHT, 0.5),
                  ('height_bot', 'GIZMO_GT_arrow_3d', 'height_bot', COL_HEIGHT, 0.5)]
        if not p.sym_lr:
            specs.append(('width_l', 'GIZMO_GT_arrow_3d', 'width_l', COL_WIDTH, 0.5))
        for name, kind, key, col, scale in specs:
            gz = self.gizmos.new(kind)
            get, set_ = make_accessors(ob.name, i, key)
            gz.target_set_handler('offset', get=get, set=set_)
            if kind == 'GIZMO_GT_dial_3d':
                gz.draw_options = {'ANGLE_VALUE', 'CLIP'}
            elif name == 'length':
                gz.draw_style = 'NORMAL'
            else:
                gz.draw_style = 'BOX'               # squares = size, like the ghost primitive
                try:
                    gz.length = 0.0
                except (AttributeError, TypeError):
                    pass
            gz.scale_basis = scale
            gz.color = col
            gz.alpha = 0.85
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha_highlight = 1.0
            self.items[(name, i)] = gz
        for j in range(1, len(p.stations)):
            up, side = sp.total_bend(p.stations[j])
            if abs(up) + abs(side) < 1e-6:
                continue
            gz = self.gizmos.new('GIZMO_GT_move_3d')
            gz.draw_style = 'RING_2D'
            gz.draw_options = {'ALIGN_VIEW', 'FILL'}
            gz.target_set_operator('mch.station_bend_cycle').index = j
            gz.scale_basis = 0.07
            gz.color = (1.0, 0.85, 0.3)
            gz.alpha = 0.9
            gz.color_highlight = (1.0, 1.0, 1.0)
            gz.alpha_highlight = 1.0
            self.items[('fold', j)] = gz

    def refresh(self, context):
        ob = context.active_object
        p = ob.mch_station
        if self.sig != _sig(ob):
            self._build(context)

    def draw_prepare(self, context):
        ob = context.active_object
        if not sp.is_live(ob):
            return
        p = ob.mch_station
        if self.sig != _sig(ob):
            self._build(context)
        from .workspace_ui import handle_scale
        f = handle_scale()
        for key, gz in self.items.items():
            base = self.base.get(key)
            if base is None:
                base = self.base[key] = gz.scale_basis
            gz.scale_basis = base * f
        rv3d = context.region_data
        view_dir = (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))) if rv3d is not None else None
        h = station_handles(ob, view_dir)
        for name, sign in h['signs'].items():
            SIGNS[(ob.name, p.active, DIAL_KEY[name])] = sign
        for i, m in h['folds']:
            gz = self.items.get(('fold', i))
            if gz is not None:
                gz.matrix_basis = m
        for i, m in h['dots']:
            gz = self.items.get(('dot', i))
            if gz is not None:
                gz.matrix_basis = m
        for i, m in h['plus']:
            gz = self.items.get(('plus', i))
            if gz is not None:
                gz.matrix_basis = m
        for name in ('up', 'side', 'twist', 'length', 'width_r', 'width_l', 'height', 'height_bot'):
            gz = self.items.get((name, p.active))
            if gz is not None and name in h:
                gz.matrix_basis = h[name]


CLASSES = (MCH_GGT_station_handles,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
