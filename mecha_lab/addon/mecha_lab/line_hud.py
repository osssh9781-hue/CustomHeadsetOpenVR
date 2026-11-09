"""0.24.112 Line HUD: buttons that float next to a swept line (Press plain drag / Base Mesh Line) once it is made.

    (dot)  click = Sharp <-> Round corners         [Thickness ----]  drag = the section's size (width and height
                                                                       together, the stamp kept in proportion)
                                                   [Radius -------]  (Round) drag = the bend radius

(user: "만든 이후에 두께랑 이런 거 실시간으로 조정할 수 있게", "꺾이는 부분이 완전 꺾이는 거랑 라운드로 꺾이는 거 옵션으로 ...
그리고 있는 메쉬 옆에 떠 있는 점으로 내가 클릭하면 변하는 걸로")  The HUD sits by the line's end (where the next stroke
goes on from) and follows it.  Everything it sets is the live object's own settings, so the N panel shows the same
values and Ctrl+Z steps back.  ``hud_layout`` is pure and tested headless; the gizmos need a real viewport."""
from __future__ import annotations

import json
import math

import bpy
from bpy.props import BoolProperty
from mathutils import Matrix, Vector

from . import base_mesh
from . import tool_state as ts

ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
ROUND_COL = (0.3, 0.75, 1.0)
BEND_COL = (0.45, 0.85, 0.5)       # 0.24.119 the Section dot when the section bends (the default)
ENDS_COL = (0.9, 0.72, 0.4)        # 0.24.121 the Ends dot when the ends are rounded
BTN = 26.0                 # the corner dot, px at UI scale 1
SLIDER_W, SLIDER_H = 96.0, 18.0
GAP = 8.0
LABEL_W = 42.0              # 0.24.121 room for the short dot labels (Move / Pick) between the dots and the sliders
THICK_PX = 160.0           # thickness slider: pixels for x2
RADIUS_PX = 60.0           # radius slider: pixels per 1.0 x width
HUD_TOOLS = {'PRESS', 'BASE'}


def hud_target(context):
    """The live swept line the HUD belongs to (active, selected, made by a line sweep), or None."""
    try:
        if not ts.is_mecha_workspace(getattr(context, 'workspace', None)) or context.mode != 'OBJECT':
            return None
    except (AttributeError, TypeError):
        return None
    ob = base_mesh.active_live_base(context)
    if ob is None or not ob.get(base_mesh.SWEEP_KEY):
        return None
    try:
        tool = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        tool = ''
    if tool in HUD_TOOLS:
        return ob
    try:
        from .station_gizmos import SELECT_NATIVE
        if ts.native_tool_id(context) in SELECT_NATIVE:
            return ob
    except (ImportError, AttributeError):
        pass
    return None


def hud_layout(end_px, region_w, region_h, btn=BTN, gap=GAP, round_on=False):
    """Pure: where the dot and the sliders go (region px, centres) for a line whose end shows at ``end_px``: to the
    right of the end, kept inside the region.  Keys: 'corner', 'thick', 'move', 'pick', 'section', 'ends', 'detail'
    and - Round only - 'radius'."""
    if end_px is None:
        return {}
    x, y = float(end_px[0]), float(end_px[1])
    x0, y0 = x + btn * 1.8, y + btn * 0.9
    total_w = btn + gap + LABEL_W + SLIDER_W
    if x0 + total_w > region_w - gap:                      # no room on the right: put it on the left
        x0 = x - btn * 1.8 - total_w + btn
    x0 = max(btn, min(x0, region_w - total_w))
    rows = 2 if round_on else 1
    # the column under the dot: Move, Pick, Section, Ends (0.24.114 / 0.24.119 / 0.24.121) - kept inside the region
    y0 = max(gap + SLIDER_H * rows, 4 * (btn + gap) + btn / 2 + gap, min(y0, region_h - btn))
    lay = {'corner': (x0, y0), 'thick': (x0 + btn / 2 + gap + LABEL_W + SLIDER_W / 2, y0),
           'move': (x0, y0 - (btn + gap)),                 # 0.24.114 Move: drag the end rings
           'pick': (x0, y0 - 2 * (btn + gap)),             # 0.24.121 Pick: grab the line anywhere (a new joint)
           'section': (x0, y0 - 3 * (btn + gap)),          # 0.24.119 Section: Bend / Each View
           'ends': (x0, y0 - 4 * (btn + gap))}             # 0.24.121 Ends: Flat / Round
    lay['detail'] = (lay['thick'][0], y0 - 2 * (btn + gap))      # 0.24.121 rings along the line
    if round_on:
        lay['radius'] = (lay['thick'][0], y0 - (btn + gap))
    return lay


def line_end_px(context, ob):
    """Region px of the line's end (the seam of a closed loop), or None when off screen."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    anchor = base_mesh.sweep_anchor(ob)
    if anchor is None:
        return None
    p = view3d_utils.location_3d_to_region_2d(region, rv3d, anchor)
    return None if p is None else (float(p.x), float(p.y))


def end_handles_px(context, ob):
    """Region px of the two ends (for the Move handles): [(xy, at_end)], none for a closed loop."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    ends = base_mesh.sweep_ends(ob) if region is not None and rv3d is not None else None
    if not ends:
        return []
    out = []
    for k, w in enumerate(ends):
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, w)
        if p is not None:
            out.append(((float(p.x), float(p.y)), k == 1))
    return out


MAX_JOINT_HANDLES = 24


def joint_handles_px(context, ob):
    """0.24.117 Region px of the joints the pieces meet at (a closed loop's seam too): [(xy, path index)]."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return []
    out = []
    for j, w in base_mesh.sweep_joints(ob)[:MAX_JOINT_HANDLES]:
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, w)
        if p is not None:
            out.append(((float(p.x), float(p.y)), j))
    return out


def move_on(context):
    return bool(getattr(context.window_manager, 'mch_line_move', False))


def pick_on(context):
    return bool(getattr(context.window_manager, 'mch_line_pick', False))


def rings_shown(move):
    """0.24.120 (user: "이어진 모든 점에 남아있어야 돼 - 합쳐진 곳은 왜 없어져?") Which rings the HUD shows: (the two ends,
    the joints).  The joint rings - every place two strokes met and a closed loop's seam - STAY until Enter and can be
    dragged any time; the end rings come with Move (a stroke from an end goes on with the line otherwise)."""
    return bool(move), True


def layout_for(context, ob):
    """The HUD layout (region px) for ``ob`` in this region now."""
    end = line_end_px(context, ob)
    if end is None:
        return {}
    ui = context.preferences.system.ui_scale
    lay = hud_layout((end[0] / ui, end[1] / ui), context.region.width / ui, context.region.height / ui,
                     round_on=ob.mch_base.line_corner == 'ROUND')
    return {k: (v[0] * ui, v[1] * ui) for k, v in lay.items()}


# -----------------------------------------------------------------------------
# what the HUD sets
# -----------------------------------------------------------------------------

def thickness(ob):
    return float(ob.mch_base.section_width)


def continue_radius_px(context):
    try:
        from . import press_cut
        return press_cut.continue_radius(context.scene.mch_press) * context.preferences.system.ui_scale
    except Exception:
        return 24.0


def set_thickness(ob, width, init=None):
    """The section's size: width ``width``, and the height scaled by the same factor (the stamp in proportion).
    ``init`` = (width, height) the drag started from (so a long drag does not drift)."""
    p = ob.mch_base
    w0, h0 = init if init is not None else (p.section_width, p.height)
    width = max(0.001, float(width))
    f = width / max(float(w0), 1e-9)
    p.height = max(0.001, float(h0) * f)
    p.section_width = width


def toggle_corner(ob):
    p = ob.mch_base
    p.line_corner = 'ROUND' if p.line_corner == 'SHARP' else 'SHARP'
    return p.line_corner


def toggle_ends(ob):
    """0.24.121 (user: "끝부분 마감을 평평하게 하는 거랑 둥글게 하는 거") Flat <-> Round ends on a made line."""
    p = ob.mch_base
    p.line_end = 'ROUND' if p.line_end == 'FLAT' else 'FLAT'
    return p.line_end


def toggle_section(ob):
    """0.24.119 (user: "섹션 토글 넣어줘") Bend <-> Each View on a made line (it rebuilds live)."""
    p = ob.mch_base
    p.line_up = 'VIEW' if p.line_up == 'BEND' else 'BEND'
    return p.line_up


class MCH_OT_line_move_toggle(bpy.types.Operator):
    """Line HUD Move: on, the line's end rings can be dragged (the last piece turns and stretches about its joint);
    off, a stroke from an end ring goes on with the line.  The blue joint rings (where strokes met) stay either way
    and can always be dragged"""
    bl_idname = 'mch.line_move_toggle'
    bl_label = 'Line Move Mode'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.mch_line_move = not wm.mch_line_move
        if wm.mch_line_move:
            wm.mch_line_pick = False
        self.report({'INFO'}, 'Move: drag an end ring (the joint rings drag any time)' if wm.mch_line_move
                    else 'Move off: a stroke from an end goes on - the blue joint rings stay and still drag')
        if context.area:
            context.area.header_text_set('Move: drag an end ring or a joint ring in this view\'s plane' if wm.mch_line_move else None)
        for a in context.screen.areas if context.screen else ():
            a.tag_redraw()
        return {'FINISHED'}


class MCH_OT_line_pick_toggle(bpy.types.Operator):
    """Line HUD Pick: on, press on the line ANYWHERE and that spot becomes a joint (a blue ring) that follows the
    mouse; off again, the new joints stay and drag like the others"""
    bl_idname = 'mch.line_pick_toggle'
    bl_label = 'Line Pick Mode'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        wm = context.window_manager
        wm.mch_line_pick = not wm.mch_line_pick
        if wm.mch_line_pick:
            wm.mch_line_move = False
        self.report({'INFO'}, 'Pick: press on the line anywhere and drag' if wm.mch_line_pick
                    else 'Pick off: the new joints stay as blue rings')
        if context.area:
            context.area.header_text_set('Pick: press on the line anywhere and drag - that spot becomes a blue joint ring'
                                         if wm.mch_line_pick else None)
        for a in context.screen.areas if context.screen else ():
            a.tag_redraw()
        return {'FINISHED'}


class MCH_OT_line_end_toggle(bpy.types.Operator):
    """Line HUD Ends: how the line's two ends are closed - Flat (a flat face) or Round (a dome)"""
    bl_idname = 'mch.line_end_toggle'
    bl_label = 'Line Ends: Flat / Round'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def execute(self, context):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        mode = toggle_ends(ob)
        self.report({'INFO'}, f'{ob.name}: {"Round" if mode == "ROUND" else "Flat"} ends')
        return {'FINISHED'}


class MCH_OT_line_section_toggle(bpy.types.Operator):
    """Line HUD Section: how the section turns between the pieces of this line - Bend (carried round every bend like
    a bent bar, no twist) or Each View (every piece faces the view it was drawn in)"""
    bl_idname = 'mch.line_section_toggle'
    bl_label = 'Line Section: Bend / Each View'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def execute(self, context):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        mode = toggle_section(ob)
        self.report({'INFO'}, f'{ob.name}: section {"Bend" if mode == "BEND" else "Each View"}')
        return {'FINISHED'}


class MCH_OT_line_corner_toggle(bpy.types.Operator):
    """Line HUD dot: Sharp (mitred) <-> Round corners on this line"""
    bl_idname = 'mch.line_corner_toggle'
    bl_label = 'Line Corners: Sharp / Round'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def execute(self, context):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        mode = toggle_corner(ob)
        self.report({'INFO'}, f'{ob.name}: {"Round" if mode == "ROUND" else "Sharp"} corners')
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# gizmos
# -----------------------------------------------------------------------------

_RECT = ((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0))


class MCH_GT_line_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_line_slider'
    __slots__ = ('shape', 'kind', 'init_x', 'init_w', 'init_h', 'init_r', 'init_d')

    def setup(self):
        if not hasattr(self, 'shape'):
            self.shape = self.new_custom_shape('TRIS', _RECT)
        if not hasattr(self, 'kind'):
            self.kind = 'thick'

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def test_select(self, context, location):
        """A 2D gizmo group picks by this (not by draw_select): inside the slider's rectangle?"""
        m = self.matrix_basis
        cx, cy, hw, hh = m[0][3], m[1][3], abs(m[0][0]), abs(m[1][1])
        return 0 if abs(location[0] - cx) <= hw and abs(location[1] - cy) <= hh else -1

    def invoke(self, context, event):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        self.init_x = event.mouse_region_x
        self.init_w, self.init_h = float(ob.mch_base.section_width), float(ob.mch_base.height)
        self.init_r = float(ob.mch_base.corner_radius)
        self.init_d = float(getattr(ob.mch_base, 'line_detail', 1.0))
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        dx = (event.mouse_region_x - self.init_x) / max(context.preferences.system.ui_scale, 1e-6)
        if 'PRECISE' in tweak:
            dx *= 0.2
        if self.kind == 'radius':
            r = max(0.1, min(20.0, self.init_r + dx / RADIUS_PX))
            if abs(r - ob.mch_base.corner_radius) > 1e-6:
                ob.mch_base.corner_radius = r
            text = f'Corner Radius: {r:.2f} x width'
        elif self.kind == 'detail':                        # 0.24.121 rings along the line
            dv = max(0.25, min(8.0, self.init_d * (2.0 ** (dx / THICK_PX))))
            if abs(dv - ob.mch_base.line_detail) > 1e-6:
                ob.mch_base.line_detail = dv
            text = f'Detail: {dv:.2f} x  (rings along the line)'
        else:
            w = max(0.001, self.init_w * (2.0 ** (dx / THICK_PX)))
            if abs(w - ob.mch_base.section_width) > 1e-7:
                set_thickness(ob, w, (self.init_w, self.init_h))
            text = f'Thickness: {w:.3f}'
        if context.area:
            context.area.header_text_set(text + '   (drag left / right, Shift = fine)')
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            ob = hud_target(context)
            if ob is not None:
                if self.kind == 'radius':
                    ob.mch_base.corner_radius = self.init_r
                elif self.kind == 'detail':
                    ob.mch_base.line_detail = self.init_d
                else:
                    set_thickness(ob, self.init_w, (self.init_w, self.init_h))


class MCH_GT_line_end(bpy.types.Gizmo):
    """0.24.114 An end ring (Move on) or - 0.24.120 - a joint ring (always there) you can drag: the point follows the
    mouse in the plane of the view you drag in."""
    bl_idname = 'MCH_GT_line_end'
    __slots__ = ('shape', 'at_end', 'joint', 'plane_co', 'plane_no', 'moved', 'start_world')

    def setup(self):
        if not hasattr(self, 'shape'):
            ring = []                                      # 0.24.120 drawn as a ring (the blue circles), hit as a disc
            r_in = 0.62
            for i in range(24):
                a0, a1 = math.tau * i / 24, math.tau * (i + 1) / 24
                o0, o1 = (math.cos(a0), math.sin(a0), 0.0), (math.cos(a1), math.sin(a1), 0.0)
                i0, i1 = (r_in * math.cos(a0), r_in * math.sin(a0), 0.0), (r_in * math.cos(a1), r_in * math.sin(a1), 0.0)
                ring += [o0, o1, i1, o0, i1, i0]
            self.shape = self.new_custom_shape('TRIS', ring)
        if not hasattr(self, 'at_end'):
            self.at_end = True
        if not hasattr(self, 'joint'):
            self.joint = -1                                # >= 0: this handle is the joint at that path index

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def test_select(self, context, location):
        m = self.matrix_basis
        return 0 if math.dist((location[0], location[1]), (m[0][3], m[1][3])) <= abs(m[0][0]) else -1

    def _anchor(self, ob):
        if self.joint >= 0:
            for j, w in base_mesh.sweep_joints(ob):
                if j == self.joint:
                    return w.copy()
            return None
        ends = base_mesh.sweep_ends(ob)
        return ends[1 if self.at_end else 0].copy() if ends else None

    def _apply(self, ob, where):
        if self.joint >= 0:
            return base_mesh.move_joint(ob, self.joint, where)
        return base_mesh.move_end(ob, self.at_end, where)

    def _hit(self, context, event):
        from bpy_extras import view3d_utils
        from mathutils.geometry import intersect_line_plane
        region, rv3d = context.region, context.region_data
        xy = (event.mouse_region_x, event.mouse_region_y)
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        return intersect_line_plane(o, o + d * 1000.0, self.plane_co, self.plane_no)

    def invoke(self, context, event):
        ob = hud_target(context)
        anchor = self._anchor(ob) if ob is not None else None
        if anchor is None:
            return {'CANCELLED'}
        self.start_world = anchor
        self.plane_co = self.start_world.copy()
        # 0.24.116 (user: "무브가 위아래로는 왜 안 돼?") the end moves in the plane of the CURRENT view through it - up /
        # down on screen is up / down in the world from where you look (the piece's own plane held it flat before)
        rv3d = context.region_data
        self.plane_no = (rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))).normalized() if rv3d is not None else Vector((0.0, 0.0, 1.0))
        self.moved = False
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        ob = hud_target(context)
        if ob is None:
            return {'CANCELLED'}
        hit = self._hit(context, event)
        if hit is None:
            return {'RUNNING_MODAL'}
        try:
            if self._apply(ob, hit):
                self.moved = True
        except Exception as ex:               # a drag must never fail loudly: the line stays where it was
            if context.area:
                context.area.header_text_set(f'Move: {ex}')
            return {'RUNNING_MODAL'}
        if context.area:
            context.area.header_text_set(('Move the joint' if self.joint >= 0 else 'Move the line\'s end')
                                         + ' in this view\'s plane - turn the view to move it another way  (Esc = back)')
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        ob = hud_target(context)
        if cancel and self.moved and ob is not None:
            try:
                self._apply(ob, self.start_world)
            except Exception:
                pass
        elif self.moved:
            try:
                bpy.ops.ed.undo_push(message='Move Line End')
            except Exception:
                pass


def path_hit(context, ob, location):
    """0.24.121 The point of the line's own path nearest to region px ``location``: (world point, px distance), or
    None.  The stored path (a closed loop's seam included), projected to the region."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    try:
        data = json.loads(ob[base_mesh.SWEEP_KEY])
    except (KeyError, TypeError, ValueError):
        return None
    path, _ups, _joints = base_mesh._sweep_lists(data)
    if len(path) < 2:
        return None
    if data.get('closed'):
        path = path + [path[0]]
    mw = ob.matrix_world
    world = [mw @ Vector(q) for q in path]
    px = [view3d_utils.location_3d_to_region_2d(region, rv3d, w) for w in world]
    best = None
    lx, ly = float(location[0]), float(location[1])
    for i in range(len(px) - 1):
        a, b = px[i], px[i + 1]
        if a is None or b is None:
            continue
        dx, dy = b.x - a.x, b.y - a.y
        l2 = dx * dx + dy * dy
        t = 0.0 if l2 < 1e-9 else max(0.0, min(1.0, ((lx - a.x) * dx + (ly - a.y) * dy) / l2))
        d = math.hypot(a.x + dx * t - lx, a.y + dy * t - ly)
        if best is None or d < best[0]:
            best = (d, i, t)
    if best is None:
        return None
    d, i, t = best
    return world[i].lerp(world[i + 1], t), d


class MCH_GT_line_path(bpy.types.Gizmo):
    """0.24.121 (user: "내가 픽하는 부분 잡고 움직일 수 있게") Pick on: the whole line is a handle.  Press on it anywhere
    and that spot becomes a joint (a blue ring) that follows the mouse in the view's plane; let go and it stays.
    (Its own Gizmo class - a registered Gizmo must not inherit another registered one, that broke the parent - the
    drag itself is the end ring's code, shared as plain functions.)"""
    bl_idname = 'MCH_GT_line_path'
    __slots__ = ('at_end', 'joint', 'plane_co', 'plane_no', 'moved', 'start_world', 'hit_world')
    _anchor = MCH_GT_line_end._anchor
    _apply = MCH_GT_line_end._apply
    _hit = MCH_GT_line_end._hit
    modal = MCH_GT_line_end.modal
    exit = MCH_GT_line_end.exit

    def setup(self):
        if not hasattr(self, 'at_end'):
            self.at_end = True
        if not hasattr(self, 'joint'):
            self.joint = -1
        if not hasattr(self, 'hit_world'):
            self.hit_world = None

    def draw(self, context):
        pass

    def test_select(self, context, location):
        ob = hud_target(context)
        if ob is None or not pick_on(context):
            return -1
        hit = path_hit(context, ob, location)
        crp = continue_radius_px(context)
        if hit is None or hit[1] > 0.5 * crp:
            return -1
        for xy, _j in joint_handles_px(context, ob):          # the rings themselves come first
            if math.dist(xy, (location[0], location[1])) <= 0.4 * crp:
                return -1
        if move_on(context):
            for xy, _e in end_handles_px(context, ob):
                if math.dist(xy, (location[0], location[1])) <= 0.5 * crp:
                    return -1
        self.hit_world = hit[0]
        return 0

    def invoke(self, context, event):
        ob = hud_target(context)
        if ob is None or self.hit_world is None:
            return {'CANCELLED'}
        try:
            got = base_mesh.insert_joint(ob, self.hit_world)
        except Exception:
            got = None
        if got is None:
            return {'CANCELLED'}
        idx, is_end = got
        if is_end:
            self.joint = -1
            self.at_end = idx != 0
        else:
            self.joint = idx
        return MCH_GT_line_end.invoke(self, context, event)


class MCH_GGT_line_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_line_hud'
    bl_label = 'Line HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return hud_target(context) is not None

    def setup(self, context):
        self.items = {}
        gz = self.gizmos.new('GIZMO_GT_button_2d')
        gz.icon = 'SHARPCURVE'
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.line_corner_toggle')
        gz.color = BASE_COL
        gz.alpha = 0.92
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.items['corner'] = gz
        gz = self.gizmos.new('GIZMO_GT_button_2d')
        gz.icon = 'ORIENTATION_GLOBAL'
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.line_move_toggle')
        gz.color = BASE_COL
        gz.alpha = 0.92
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.items['move'] = gz
        gz = self.gizmos.new('GIZMO_GT_button_2d')             # 0.24.119 Section: Bend / Each View
        gz.icon = 'MOD_SIMPLEDEFORM'
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.line_section_toggle')
        gz.color = BEND_COL
        gz.alpha = 0.92
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.items['section'] = gz
        for key, icon, op in (('pick', 'PIVOT_CURSOR', 'mch.line_pick_toggle'), ('ends', 'MESH_CYLINDER', 'mch.line_end_toggle')):
            gz = self.gizmos.new('GIZMO_GT_button_2d')         # 0.24.121 Pick / Ends
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            gz.target_set_operator(op)
            gz.color = BASE_COL
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[key] = gz
        for key, at_end in (('end_start', False), ('end_end', True)):
            gz = self.gizmos.new(MCH_GT_line_end.bl_idname)
            gz.at_end = at_end
            gz.color = (0.3, 0.85, 1.0)
            gz.alpha = 0.35
            gz.color_highlight = (1.0, 0.75, 0.2)
            gz.alpha_highlight = 0.7
            gz.use_draw_scale = False
            self.items[key] = gz
        for k in range(MAX_JOINT_HANDLES):                 # 0.24.117 the joints between pieces (hidden until used)
            gz = self.gizmos.new(MCH_GT_line_end.bl_idname)
            gz.joint = 0
            gz.color = (0.55, 0.9, 1.0)
            gz.alpha = 0.3
            gz.color_highlight = (1.0, 0.75, 0.2)
            gz.alpha_highlight = 0.7
            gz.use_draw_scale = False
            self.items[f'joint_{k}'] = gz
        for kind in ('thick', 'radius', 'detail'):
            gz = self.gizmos.new(MCH_GT_line_slider.bl_idname)
            gz.kind = kind
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items[kind] = gz
        gz = self.gizmos.new(MCH_GT_line_path.bl_idname)       # 0.24.121 Pick: the line itself (made last: rings first)
        gz.use_draw_scale = False
        gz.alpha = 0.0
        self.items['path'] = gz

    def draw_prepare(self, context):
        ob = hud_target(context)
        lay = layout_for(context, ob) if ob is not None else {}
        ui = context.preferences.system.ui_scale
        try:
            from .workspace_ui import handle_scale
            f = min(1.6, handle_scale())
        except (ImportError, AttributeError):
            f = 1.0
        round_on = ob is not None and ob.mch_base.line_corner == 'ROUND'
        mv = move_on(context)
        ends_on, joints_on = rings_shown(mv)
        handles = {('end_end' if at_end else 'end_start'): xy for xy, at_end in end_handles_px(context, ob)} \
            if ob is not None and ends_on else {}
        joints = joint_handles_px(context, ob) if ob is not None and joints_on else []   # 0.24.120 always
        pk = pick_on(context)
        for name, gz in self.items.items():
            if name == 'path':
                gz.hide = not (ob is not None and pk)
                continue
            if name in ('end_start', 'end_end'):
                pos = handles.get(name)
                gz.hide = pos is None
                if not gz.hide:
                    r = 0.5 * continue_radius_px(context)
                    gz.matrix_basis = Matrix.Translation((pos[0], pos[1], 0.0)) @ Matrix.Diagonal((r, r, 1.0, 1.0))
                continue
            if name.startswith('joint_'):
                k = int(name[6:])
                gz.hide = k >= len(joints)
                if not gz.hide:
                    pos, j = joints[k]
                    gz.joint = j
                    r = 0.4 * continue_radius_px(context)
                    gz.matrix_basis = Matrix.Translation((pos[0], pos[1], 0.0)) @ Matrix.Diagonal((r, r, 1.0, 1.0))
                continue
            pos = lay.get(name)
            gz.hide = pos is None
            if gz.hide:
                continue
            if name == 'move':
                gz.color = ACCENT if mv else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            if name == 'pick':
                gz.color = ACCENT if pk else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            if name == 'ends':
                rnd = ob is not None and getattr(ob.mch_base, 'line_end', 'FLAT') == 'ROUND'
                gz.icon = 'MESH_CAPSULE' if rnd else 'MESH_CYLINDER'
                gz.color = ENDS_COL if rnd else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            if name == 'section':
                bend = ob is not None and ob.mch_base.line_up == 'BEND'
                gz.icon = 'MOD_SIMPLEDEFORM' if bend else 'VIEW_PERSPECTIVE'
                gz.color = BEND_COL if bend else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            if name == 'corner':
                gz.icon = 'SPHERECURVE' if round_on else 'SHARPCURVE'
                gz.color = ROUND_COL if round_on else BASE_COL
                gz.scale_basis = BTN / 2.0 * f
                gz.matrix_basis[0][3] = pos[0]
                gz.matrix_basis[1][3] = pos[1]
                continue
            gz.matrix_basis = Matrix.Translation((pos[0], pos[1], 0.0)) @ Matrix.Diagonal(
                (SLIDER_W * ui / 2, SLIDER_H * ui / 2, 1.0, 1.0))


def _draw_labels():
    """The dot's state and the slider values, in text."""
    try:
        context = bpy.context
        ob = hud_target(context)
        if ob is None:
            return
        lay = layout_for(context, ob)
        if not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        font = 0
        blf.size(font, 11 * ui)
        p = ob.mch_base
        round_on = p.line_corner == 'ROUND'
        x, y = lay['corner']
        blf.color(font, *(ROUND_COL if round_on else (0.85, 0.87, 0.9)), 1.0)
        blf.position(font, x - BTN * 0.55 * ui, y + BTN * 0.75 * ui, 0)
        blf.draw(font, 'Round' if round_on else 'Sharp')
        if 'move' in lay:
            x, y = lay['move']
            mv = move_on(context)
            blf.color(font, *(ACCENT if mv else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x + BTN * 0.7 * ui, y - 4 * ui, 0)
            blf.draw(font, 'Move')
        if 'section' in lay:                                   # 0.24.119
            x, y = lay['section']
            bend = p.line_up == 'BEND'
            blf.color(font, *(BEND_COL if bend else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x + BTN * 0.7 * ui, y - 4 * ui, 0)
            blf.draw(font, 'Section: Bend' if bend else 'Section: Each View')
        pk = pick_on(context)
        if 'pick' in lay:                                      # 0.24.121
            x, y = lay['pick']
            blf.color(font, *(ACCENT if pk else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x + BTN * 0.7 * ui, y - 4 * ui, 0)
            blf.draw(font, 'Pick')
        if 'ends' in lay:
            x, y = lay['ends']
            rnd = getattr(p, 'line_end', 'FLAT') == 'ROUND'
            blf.color(font, *(ENDS_COL if rnd else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x + BTN * 0.7 * ui, y - 4 * ui, 0)
            blf.draw(font, 'Ends: Round' if rnd else 'Ends: Flat')
        if 'detail' in lay:
            blf.color(font, 1.0, 1.0, 1.0, 1.0)
            x, y = lay['detail']
            text = f'Detail  {getattr(p, "line_detail", 1.0):.2f} x'
            w, _h = blf.dimensions(font, text)
            blf.position(font, x - w / 2, y - 4 * ui, 0)
            blf.draw(font, text)
        if pk:                                                 # the path you can grab, over the line
            try:
                import gpu
                from bpy_extras import view3d_utils
                from . import cut_engine as ce
                data = json.loads(ob[base_mesh.SWEEP_KEY])
                path, _u, _j = base_mesh._sweep_lists(data)
                mw, region, rv3d = ob.matrix_world, context.region, context.region_data
                pts = [view3d_utils.location_3d_to_region_2d(region, rv3d, mw @ Vector(q)) for q in path]
                pts = [(float(q.x), float(q.y)) for q in pts if q is not None]
                if len(pts) >= 2:
                    gpu.state.blend_set('ALPHA')
                    ce._draw_lines(ce._shader(), pts, (0.55, 0.9, 1.0, 0.75), closed=bool(data.get('closed')), width=1.5)
                    gpu.state.blend_set('NONE')
            except Exception:
                pass
        blf.color(font, 1.0, 1.0, 1.0, 1.0)
        x, y = lay['thick']
        text = f'Thickness  {p.section_width:.3f}'
        w, _h = blf.dimensions(font, text)
        blf.position(font, x - w / 2, y - 4 * ui, 0)
        blf.draw(font, text)
        if 'radius' in lay:
            x, y = lay['radius']
            text = f'Radius  {p.corner_radius:.2f} x'
            w, _h = blf.dimensions(font, text)
            blf.position(font, x - w / 2, y - 4 * ui, 0)
            blf.draw(font, text)
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_OT_line_corner_toggle, MCH_OT_line_move_toggle, MCH_OT_line_section_toggle, MCH_OT_line_pick_toggle,
           MCH_OT_line_end_toggle, MCH_GT_line_slider, MCH_GT_line_end, MCH_GT_line_path, MCH_GGT_line_hud)
_label_handle = None


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not hasattr(bpy.types.WindowManager, 'mch_line_move'):
        bpy.types.WindowManager.mch_line_move = BoolProperty(
            name='Line Move', default=False,
            description='Line HUD: drag the end rings of the made line (off: a stroke from an end goes on with it)')
    if not hasattr(bpy.types.WindowManager, 'mch_line_pick'):      # 0.24.121
        bpy.types.WindowManager.mch_line_pick = BoolProperty(
            name='Line Pick', default=False, options={'SKIP_SAVE'},
            description='Line HUD Pick: press on the line anywhere and drag - that spot becomes a joint')
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    if hasattr(bpy.types.WindowManager, 'mch_line_move'):
        try:
            del bpy.types.WindowManager.mch_line_move
        except (AttributeError, RuntimeError):
            pass
    if hasattr(bpy.types.WindowManager, 'mch_line_pick'):
        try:
            del bpy.types.WindowManager.mch_line_pick
        except (AttributeError, RuntimeError):
            pass
