"""0.24.95 Press Cut (user: "내가 정한 라쏘 모양을 저장해 놓으면 그걸로 잘리는데 약간 밀리면서 잘리는 거지 - 내가 오래
누르면 더 잘리고 조금 누르면 조금만 잘리는"): a saved shape (a lasso you drew and saved, a built-in one or an imported
PNG) follows the mouse like a stamp; press on a part and hold - it is cut From Surface, deeper the longer you hold
(Start + Speed x seconds, of the part's size, up to Max); let go and it stays; Esc / right click while holding puts the
part back.  Result Cut (a pocket) or Split (the pressed-in plug becomes its own part).  The Cut tool's settings still
apply (Edge Finish / GN Edge, Split sides, the live Mirror ...): each step is a plain ``perform_closed`` on the part
as it was at the press (kept), so the pressed cut is exactly the cut a From Surface lasso of that depth makes.

Save Shape: the last closed outline drawn with Cut / Split (lasso, sketch, rectangle ...) or any lasso tool is kept
for the session (``cut_presets.remember``); Save Shape writes it as a cut shape (``cut_presets.save_loops``) - it is
then in the shape list of Press Cut and of the Cut / Split Custom stamp, in every file.

[ / ] or F + mouse: stamp size.  R + mouse left / right: turn it (0.4 degree a pixel, Shift fine, Ctrl 5 degree
steps; click keeps, Esc puts it back), Shift + R: back to 0 degrees.
"""
from __future__ import annotations

import math
import time

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, StringProperty

from . import core_geometry as cg

TICK = 0.05                    # (seconds between depth steps while held)
STEP_MIN = 0.002               # (a new cut only when the depth grew by this x the part's size)


def _shape_items(self, context):
    from . import cut_presets
    return cut_presets.preset_items(self, context)


def _redraw(self, context):
    for w in getattr(context.window_manager, 'windows', ()):
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


class MCH_PG_Press(bpy.types.PropertyGroup):
    result: EnumProperty(name='Result', items=[
        ('CUT', 'Cut', 'The shape pressed into the part: a pocket'),
        ('SPLIT', 'Split', 'The pressed-in plug becomes its own part')], default='CUT')
    shape: EnumProperty(name='Shape', items=_shape_items, update=_redraw,
                        description='The stamp: a saved lasso, a built-in shape or an imported PNG')
    size: FloatProperty(name='Size', default=60.0, min=4.0, max=2000.0, subtype='PIXEL', update=_redraw,
                        description='Stamp radius on screen ([ / ] change it)')
    rotation: FloatProperty(name='Rotation', default=0.0, subtype='ANGLE', update=_redraw, step=10,
                            description='Stamp turn (R + mouse: turn it, Shift + R: 0)')
    curve_x: FloatProperty(name='Curve Left-Right', default=0.0, min=-1.0, max=1.0, precision=2, update=_redraw,
                           description='The stamp bent left-right like a round stamp: + the middle goes in first and '
                                       'deepest (a round trough), - the sides first (the middle stays raised); 1 = a '
                                       'half circle across the stamp')
    curve_y: FloatProperty(name='Curve Up-Down', default=0.0, min=-1.0, max=1.0, precision=2, update=_redraw,
                           description='The stamp bent up-down (both: a bowl, or a saddle with opposite signs)')
    start: FloatProperty(name='Start', default=0.01, min=0.0005, max=1.0, subtype='FACTOR', precision=3,
                         description='Depth at the press, of the part\'s size (a quick tap)')
    speed: FloatProperty(name='Speed', default=0.12, min=0.005, soft_max=1.0, max=5.0, precision=3,
                         description='Depth added per second held, of the part\'s size')
    max_depth: FloatProperty(name='Max', default=1.0, min=0.01, max=2.0, subtype='FACTOR', precision=2,
                             description='The deepest it goes, of the part\'s size (1 = through a part as thick '
                                         'as it is long)')
    shape_name: StringProperty(name='Name', default='My Shape')


# --- the pressed cut ------------------------------------------------------------------------------------------------

def part_size(ob):
    pts = cg.object_world_bounds([ob])
    if not pts:
        return 1.0
    lo = [min(p[i] for p in pts) for i in range(3)]
    hi = [max(p[i] for p in pts) for i in range(3)]
    return max(max(hi[i] - lo[i] for i in range(3)), 1e-6)


def depth_at(st, size, seconds):
    """The depth after holding ``seconds``: (Start + Speed x seconds) x the part's size, up to Max."""
    return size * min(st.max_depth, st.start + st.speed * max(0.0, seconds))


def stamp_loops(context, center, st=None):
    """The stamp's outline(s) in region px at ``center`` (the shape at its size and turn)."""
    from . import cut_engine as ce, cut_presets
    st = st or context.scene.mch_press
    norm = cut_presets.load_loops(st.shape)
    return ce.custom_loops(norm, center, st.size, st.rotation)


def resample(loop, step):
    """A closed loop with no side longer than ``step`` px (a curved stamp bends along every side)."""
    out = []
    n = len(loop)
    for i in range(n):
        a, b = loop[i], loop[(i + 1) % n]
        k = max(1, int(math.ceil(math.dist(a, b) / max(step, 1e-6))))
        out += [(a[0] + (b[0] - a[0]) * j / k, a[1] + (b[1] - a[1]) * j / k) for j in range(k)]
    return out


def arc_drop(s, w, h):
    """How far a circular arc across a stamp ``2 w`` wide with ``h`` sag (all world) lies below its middle at ``s``
    (-1 .. 1 across): 0 in the middle, ``h`` at the sides."""
    h = abs(h)
    if h < 1e-12 or w < 1e-12:
        return 0.0
    x = min(abs(s), 1.0) * w
    r = (w * w + h * h) / (2.0 * h)
    return h - (math.sqrt(max(r * r - x * x, 0.0)) - (r - h))


class Press:
    """One press on one part: the part as it was (kept), cut again From Surface at each new depth."""

    def __init__(self, context, target, loops, projector, result='CUT', center=None, angle=0.0, curve=(0.0, 0.0),
                 spacing=6.0):
        from . import ramp_edit
        old = ramp_edit.live_target(context, ramp_edit.ALL_KINDS)
        if old is not None:                      # (an earlier live cut stays as it is: the Cut Depth set while
            ramp_edit.finish(old)                #  pressing must not cut it again)
        self.target = target
        self.curve = (float(curve[0]), float(curve[1]))
        self.curved = abs(self.curve[0]) > 1e-4 or abs(self.curve[1]) > 1e-4
        self.spacing = max(2.0, float(spacing))
        lps = [[tuple(p) for p in lp] for lp in loops]
        self.loops = [resample(lp, self.spacing) for lp in lps] if self.curved else lps
        self.projector = projector
        pts = [p for lp in lps for p in lp]
        self.center = center or (sum(p[0] for p in pts) / len(pts), sum(p[1] for p in pts) / len(pts))
        self.angle = float(angle)
        self.px_world = self._px_world(context, target, projector) if self.curved else 0.0
        self.result = result
        self.size = part_size(target)
        self.backup = target.data.copy()
        self.backup.name = 'MCH_PressBackup_' + target.name
        cut = context.scene.mch_cut
        self.saved = (cut.depth_mode, cut.depth)
        self.depth = 0.0
        self.pieces = []
        self.message = ''

    def _px_world(self, context, target, projector):
        """World size of one screen pixel at the part's surface under the stamp's middle."""
        from . import cut_engine as ce
        hit = ce.surface_hit(context, [target], projector, self.center)
        vd = projector.view_dir
        if hit is None:
            hit = target.matrix_world.translation.copy()
        try:
            o0, d0 = projector.ray(self.center)
            o1, d1 = projector.ray((self.center[0] + 1.0, self.center[1]))
            p0, _t = cg._plane_hit(o0, d0, hit, vd)
            p1, _t = cg._plane_hit(o1, d1, hit, vd)
            return max((p1 - p0).length, 1e-9)
        except cg.CutError:
            return 0.0

    def floor(self, depth):
        """(fn(screen xy) -> how far above the deepest point the stamp's face is there, grid px) for the cutter's
        curved far cap at ``depth`` - None for a flat stamp.  + curve: the middle deepest (a round stamp pressed in),
        - curve: the sides deepest; never above the surface (a press not yet that deep cuts nothing there)."""
        if not self.curved or self.px_world <= 0.0:
            return None
        c, s = math.cos(self.angle), math.sin(self.angle)
        cx, cy = self.center
        uv = [((x - cx) * c + (y - cy) * s, -(x - cx) * s + (y - cy) * c) for lp in self.loops for x, y in lp]
        u0, u1 = min(p[0] for p in uv), max(p[0] for p in uv)
        v0, v1 = min(p[1] for p in uv), max(p[1] for p in uv)
        uc, vc = (u0 + u1) / 2, (v0 + v1) / 2
        wu, wv = max((u1 - u0) / 2, 1e-6), max((v1 - v0) / 2, 1e-6)
        k = self.px_world
        hx, hy = self.curve[0] * wu * k, self.curve[1] * wv * k
        above = max(1e-4, depth * 0.05)
        lowest = -(depth + 0.5 * above)               # (the face up to just above the surface, never past it)

        def fn(xy):
            u = (xy[0] - cx) * c + (xy[1] - cy) * s
            v = -(xy[0] - cx) * s + (xy[1] - cy) * c
            off = 0.0
            for val, mid, half, h in ((u, uc, wu, hx), (v, vc, wv, hy)):
                if abs(h) < 1e-12:
                    continue
                d = arc_drop((val - mid) / half, half * k, h)
                off += -d if h > 0 else -(abs(h) - d)
            return max(off, lowest)
        return fn, self.spacing

    def _restore(self):
        from . import ramp_edit
        for name in self.pieces:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                me = ob.data
                bpy.data.objects.remove(ob)
                if me is not None and me.users == 0:
                    bpy.data.meshes.remove(me)
        self.pieces = []
        ramp_edit._copy_into(self.backup, self.target.data)

    def cut_to(self, context, depth):
        """The part as it was, cut From Surface ``depth`` deep.  A depth that does not cut cleanly keeps the last
        one that did; returns False then."""
        from . import cut_engine as ce, cut_presets
        cut = context.scene.mch_cut
        prev = self.depth
        self._restore()
        before = set(bpy.data.objects.keys())
        cut.depth_mode, cut.depth = 'SURFACE', max(depth, 1e-5)
        cut_presets.QUIET[0] = True              # (the stamp is not "the last drawn outline")
        cg.FLOOR[0] = self.floor(depth)          # (a curved stamp: its face bent)
        try:
            self.message = ce.perform_closed(context, self.result, [self.target], self.loops, self.projector)
        except (cg.CutError, RuntimeError) as ex:
            self.message = str(ex)
            cg.FLOOR[0] = None
            cut_presets.QUIET[0] = False
            self._restore()
            if prev > 0.0 and depth != prev:
                self.cut_to(context, prev)
            return False
        finally:
            cut_presets.QUIET[0] = False
            cg.FLOOR[0] = None
        self.pieces = [o.name for o in bpy.data.objects if o.name not in before]
        self.depth = depth
        return True

    def _settings_back(self, context):
        cut = context.scene.mch_cut
        if (cut.depth_mode, cut.depth) != self.saved:
            cut.depth_mode, cut.depth = self.saved

    def finish(self, context):
        self._settings_back(context)
        if self.backup is not None and self.backup.users == 0:
            bpy.data.meshes.remove(self.backup)
        self.backup = None

    def cancel(self, context):
        if self.backup is not None:
            self._restore()
        self.finish(context)


def press_target(context, projector, xy):
    """The part under ``xy`` - the nearest mesh the mouse is on (Target Auto), only a selected one (Selected) or only
    the active one (Active) - or None."""
    from . import cut_engine as ce
    mode = getattr(context.scene.mch_cut, 'targets', 'AUTO')
    if mode == 'ACTIVE':
        act = context.view_layer.objects.active
        ok = act is not None and act.type == 'MESH' and ce.surface_hit(context, [act], projector, xy) is not None
        return act if ok else None
    picked = ce.pick_mesh_under(context, projector, xy)
    if picked is None or not ce._auto_candidate(picked):
        return None
    if mode == 'SELECTED' and not picked.select_get():
        return None
    return picked


# --- drawing --------------------------------------------------------------------------------------------------------

def draw_cursor(context, xy):
    """Idle stamp preview at the cursor (WorkSpaceTool.draw_cursor, window px)."""
    if TURNING[0]:
        return
    try:
        import gpu
        from . import cut_engine as ce
        st = context.scene.mch_press
        loops = stamp_loops(context, (float(xy[0]), float(xy[1])), st)
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        col = (1.0, 0.62, 0.25, 1.0) if st.result == 'CUT' else (0.45, 1.0, 0.35, 1.0)
        for lp in loops:
            ce._draw_lines(sh, lp, col, closed=True, width=1.5)
        cx, cy = float(xy[0]), float(xy[1])
        c, s = math.cos(st.rotation), math.sin(st.rotation)
        for amt, (ax, ay) in ((st.curve_x, (c, s)), (st.curve_y, (-s, c))):
            if abs(amt) > 1e-4:                  # (a bent stamp: the line it bends across, dashed by its sign)
                r = st.size * (0.9 if amt > 0 else 0.6)
                ce._draw_lines(sh, [(cx - ax * r, cy - ay * r), (cx + ax * r, cy + ay * r)],
                               (0.45, 0.85, 1.0, 0.9), width=1.0 + 2.0 * abs(amt))
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


def _draw_holding(op):
    try:
        import blf
        import gpu
        from . import cut_engine as ce
        if bpy.context.region != op.region:
            return
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        for lp in op.press.loops:
            ce._draw_lines(sh, lp, (1.0, 0.85, 0.3, 1.0), closed=True, width=2.5)
        gpu.state.blend_set('NONE')
        x, y = op.anchor
        blf.size(0, 15)
        blf.color(0, 1.0, 0.92, 0.6, 1.0)
        blf.position(0, x + op.press_st.size * 0.8 + 10, y, 0)
        unit = bpy.context.scene.unit_settings.scale_length or 1.0
        blf.draw(0, f'{op.press.result.title()} {op.press.depth * unit * 100:.1f} cm  (hold: deeper, release: keep, '
                    'Esc: back)')
    except Exception:
        pass


# --- operators ------------------------------------------------------------------------------------------------------

class MCH_OT_press_cut(bpy.types.Operator):
    """Press and hold on a part: the shape is cut in, deeper the longer you hold; let go to keep it"""
    bl_idname = 'mch.press_cut'
    bl_label = 'Press Cut'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        region, rv3d = context.region, getattr(context, 'region_data', None)
        if region is None or rv3d is None or region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        from . import cut_engine as ce
        st = context.scene.mch_press
        xy = (float(event.mouse_region_x), float(event.mouse_region_y))
        projector = ce.make_projector(region, rv3d)
        target = press_target(context, projector, xy)
        if target is None:
            self.report({'WARNING'}, 'Press on a part')
            return {'CANCELLED'}
        try:
            loops = stamp_loops(context, xy, st)
        except (cg.CutError, ValueError, OSError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        try:
            from . import safety_save
            safety_save.checkpoint('Mecha Press Cut')
        except Exception:
            pass
        self.press = Press(context, target, loops, projector, st.result, center=xy, angle=st.rotation,
                           curve=(st.curve_x, st.curve_y), spacing=max(3.0, st.size / 10.0))
        self.press_st = st
        self.region = region
        self.anchor = xy
        self.t0 = time.perf_counter()
        if not self.press.cut_to(context, depth_at(st, self.press.size, 0.0)):
            msg = self.press.message
            self.press.cancel(context)
            self.report({'WARNING'}, msg[:200] or 'Nothing was cut')
            return {'CANCELLED'}
        self.full = False
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_holding, (self,), 'WINDOW', 'POST_PIXEL')
        self.timer = context.window_manager.event_timer_add(TICK, window=context.window)
        context.window_manager.modal_handler_add(self)
        region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _end(self, context):
        try:
            context.window_manager.event_timer_remove(self.timer)
        except (ValueError, RuntimeError, ReferenceError):
            pass
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        self.region.tag_redraw()

    def modal(self, context, event):
        et, ev = event.type, event.value
        if et == 'TIMER' and not self.full:
            st = self.press_st
            d = depth_at(st, self.press.size, time.perf_counter() - self.t0)
            if d >= self.press.size * st.max_depth - 1e-9:
                self.full = True
            if d - self.press.depth >= STEP_MIN * self.press.size or self.full:
                if not self.press.cut_to(context, d):
                    self.full = True              # (it does not go deeper cleanly: stays where it was)
                self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if et == 'LEFTMOUSE' and ev == 'RELEASE':
            self._end(context)
            msg = self.press.message
            depth = self.press.depth
            self.press.finish(context)
            self.report({'INFO'}, f'Press {self.press.result.title()}: {depth:.4f} deep | {msg[:160]}')
            return {'FINISHED'}
        if (et == 'ESC' and ev == 'PRESS') or (et == 'RIGHTMOUSE' and ev == 'PRESS'):
            self._end(context)
            self.press.cancel(context)
            self.report({'INFO'}, 'Press Cut: put back')
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_press_adjust(bpy.types.Operator):
    """Press Cut stamp: size ([ / ]) or turn (R / Shift + R)"""
    bl_idname = 'mch.press_adjust'
    bl_label = 'Press Stamp Size / Turn'
    bl_options = {'INTERNAL'}

    size: FloatProperty(default=1.0)
    turn: FloatProperty(default=0.0)

    def execute(self, context):
        st = context.scene.mch_press
        st.size = max(4.0, min(2000.0, st.size * self.size))
        a = st.rotation + math.radians(self.turn)
        st.rotation = math.atan2(math.sin(a), math.cos(a))
        return {'FINISHED'}


TURN_PX = 0.4                  # (degrees per pixel the mouse moves while turning the stamp)
TURN_FINE = 0.08               # (with Shift)
TURN_SNAP = 5.0                # (with Ctrl: 5 degree steps)
TURNING = [False]              # (the idle stamp previews stay hidden while it is turned at its own place)


def turn_target(context):
    """(owner, property, size px, shape stem) of the stamp R turns: Press Cut's, or the Cut / Split Custom stamp;
    None for anything else (Blender's own R then)."""
    from . import tool_state as ts
    scene = context.scene
    if ts.effective_tool(context) == 'PRESS' and hasattr(scene, 'mch_press'):
        st = scene.mch_press
        return st, 'rotation', st.size, st.shape
    b = getattr(scene, 'mch_brush', None)
    if b is not None and b.shape == 'CUSTOM':
        return b, 'custom_rotation', b.custom_size, scene.mch_png_preset
    return None


def turn_angle(start, dx, ctrl=False, shift=False):
    """The stamp's turn after the mouse moved ``dx`` px from where R was pressed (radians, -180 .. 180 degrees):
    0.4 degree a pixel, Shift 0.08 (fine), Ctrl in 5 degree steps."""
    a = math.degrees(start) + dx * (TURN_FINE if shift else TURN_PX)
    if ctrl:
        a = round(a / TURN_SNAP) * TURN_SNAP
    a = (a + 180.0) % 360.0 - 180.0
    return math.radians(a)


def _draw_turn(op):
    try:
        import blf
        import gpu
        from . import cut_engine as ce
        if bpy.context.region != op.region:
            return
        ang = getattr(op.owner, op.prop)
        sh = ce._shader()
        gpu.state.blend_set('ALPHA')
        cx, cy = op.center
        if op.norm:
            for lp in ce.custom_loops(op.norm, op.center, op.size, ang):
                ce._draw_lines(sh, lp, (1.0, 0.85, 0.3, 1.0), closed=True, width=2.0)
        r = op.size * 1.15
        ce._draw_lines(sh, [(cx, cy), (cx + r * math.cos(ang), cy + r * math.sin(ang))], (0.45, 0.8, 1.0, 1.0),
                       width=1.5)
        gpu.state.blend_set('NONE')
        blf.size(0, 15)
        blf.color(0, 1.0, 0.92, 0.6, 1.0)
        blf.position(0, cx + op.size + 14, cy + 6, 0)
        blf.draw(0, f'{math.degrees(ang):.1f}\u00b0')
        blf.size(0, 12)
        blf.color(0, 0.85, 0.87, 0.9, 1.0)
        blf.position(0, cx + op.size + 14, cy - 14, 0)
        blf.draw(0, 'move: turn   Ctrl: 5\u00b0 steps   Shift: fine   click / R: keep   Esc: back')
    except Exception:
        pass


class MCH_OT_stamp_turn(bpy.types.Operator):
    """R: turn the stamp with the mouse - left / right, 0.4 degree a pixel (Shift: fine, Ctrl: 5 degree steps);
    click / Enter / R keeps, Esc / right click puts it back.  Shift + R: back to 0 degrees"""
    bl_idname = 'mch.stamp_turn'
    bl_label = 'Turn Stamp'
    bl_options = {'INTERNAL'}

    reset: BoolProperty(default=False)

    @classmethod
    def poll(cls, context):
        return turn_target(context) is not None

    def invoke(self, context, event):
        owner, prop, size, stem = turn_target(context)
        if self.reset:
            setattr(owner, prop, 0.0)
            if context.area:
                context.area.tag_redraw()
            self.report({'INFO'}, 'Stamp turn 0\u00b0')
            return {'FINISHED'}
        if context.region is None or context.region.type != 'WINDOW':
            return {'CANCELLED'}
        from . import cut_presets
        self.owner, self.prop, self.size = owner, prop, size
        self.start = getattr(owner, prop)
        self.x0 = event.mouse_x
        self.center = (float(event.mouse_region_x), float(event.mouse_region_y))
        self.region = context.region
        try:
            self.norm = cut_presets.load_loops(stem)
        except (cg.CutError, ValueError, OSError):
            self.norm = None
        TURNING[0] = True
        self.handle = bpy.types.SpaceView3D.draw_handler_add(_draw_turn, (self,), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        self.region.tag_redraw()
        return {'RUNNING_MODAL'}

    def _end(self):
        TURNING[0] = False
        try:
            bpy.types.SpaceView3D.draw_handler_remove(self.handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        self.region.tag_redraw()

    def modal(self, context, event):
        et, ev = event.type, event.value
        if et == 'MOUSEMOVE':
            setattr(self.owner, self.prop, turn_angle(self.start, event.mouse_x - self.x0, event.ctrl, event.shift))
            self.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if getattr(event, 'is_repeat', False):
            return {'RUNNING_MODAL'}
        if ev == 'PRESS' and et in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER', 'SPACE', 'R'}:
            self._end()
            self.report({'INFO'}, f'Stamp turn {math.degrees(getattr(self.owner, self.prop)):.1f}\u00b0')
            return {'FINISHED'}
        if ev == 'PRESS' and et in {'RIGHTMOUSE', 'ESC'}:
            setattr(self.owner, self.prop, self.start)
            self._end()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_save_cut_shape(bpy.types.Operator):
    """Save the last outline you drew (Cut / Split / any lasso: lasso, sketch, rectangle ...) as a cut shape - for
    Press Cut and the Cut / Split Custom stamp, in every file"""
    bl_idname = 'mch.save_cut_shape'
    bl_label = 'Save Shape'
    bl_options = {'REGISTER'}

    name: StringProperty(name='Name', default='')
    use: BoolProperty(name='Use It', default=True, description='Make it the Press Cut shape at once')

    @classmethod
    def poll(cls, context):
        from . import cut_presets
        return cut_presets.LAST_LOOPS[0] is not None

    def invoke(self, context, event):
        from . import cut_presets
        if not self.name:
            self.name = f'My Shape {len(cut_presets.list_presets()) + 1}'
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import cut_presets
        loops = cut_presets.LAST_LOOPS[0]
        if not loops:
            self.report({'WARNING'}, 'Draw an outline first (Cut / Split / a lasso)')
            return {'CANCELLED'}
        try:
            name = self.name or f'My Shape {len(cut_presets.list_presets()) + 1}'
            stem = cut_presets.save_loops(name, loops)
        except (cg.CutError, OSError, ValueError) as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        if self.use:
            try:
                context.scene.mch_press.shape = stem
            except TypeError:
                pass
        self.report({'INFO'}, f'Saved shape "{name}"')
        return {'FINISHED'}


def draw(layout, context):
    """The tool's settings (Sidebar > Mecha Lab)."""
    from . import cut_presets
    st = context.scene.mch_press
    col = layout.column(align=True)
    col.row(align=True).prop(st, 'result', expand=True)
    col.template_icon_view(st, 'shape', show_labels=True, scale=5.0, scale_popup=4.0)
    col.prop(st, 'size')
    col.prop(st, 'rotation')
    col = layout.column(align=True)
    col.label(text='Curve (a round stamp)')
    col.prop(st, 'curve_x', text='Left-Right', slider=True)
    col.prop(st, 'curve_y', text='Up-Down', slider=True)
    col = layout.column(align=True)
    col.label(text='Hold = deeper')
    col.prop(st, 'start')
    col.prop(st, 'speed')
    col.prop(st, 'max_depth')
    row = layout.row(align=True)
    row.enabled = cut_presets.LAST_LOOPS[0] is not None
    row.operator('mch.save_cut_shape', text='Save Last Outline as Shape', icon='FILE_TICK')
    layout.label(text='Press on a part and hold: deeper the longer you hold', icon='INFO')
    layout.label(text='Release: keep  |  Esc / RMB: back  |  [ ] / F size')
    layout.label(text='R + mouse: turn (Shift fine, Ctrl 5\u00b0)  |  Shift+R: 0\u00b0')


TOOL_KEYMAP = (
    ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True}, None),
    ('mch.press_cut', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
    ('mch.press_adjust', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('size', 1 / 1.15)]}),
    ('mch.press_adjust', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('size', 1.15)]}),
    ('mch.stamp_turn', {'type': 'R', 'value': 'PRESS'}, None),           # (R + mouse: turn, fine)
    ('mch.stamp_turn', {'type': 'R', 'value': 'PRESS', 'shift': True}, {'properties': [('reset', True)]}),
    ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    ('mch.brush_resize', {'type': 'F', 'value': 'PRESS'}, None),        # (F + mouse = stamp size)
)

CLASSES = (MCH_PG_Press, MCH_OT_press_cut, MCH_OT_press_adjust, MCH_OT_stamp_turn, MCH_OT_save_cut_shape)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_press = bpy.props.PointerProperty(type=MCH_PG_Press)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_press'):
        del bpy.types.Scene.mch_press
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
