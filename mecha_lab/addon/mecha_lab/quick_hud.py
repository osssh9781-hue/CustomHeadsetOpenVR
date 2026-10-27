"""0.24.50 Quick HUD: the 3-5 settings you change most for the tool that is on, as sliders in the viewport, so
you don't go to the sidebar while drawing.

- drag a slider left / right: change the value (Shift = fine); the live result follows like in the panel
- click (no drag): type the exact value;  Ctrl + click: back to the default
- on / off and choice settings: click flips / steps to the next choice
- the title row moves the whole HUD (kept per Blender session)
0.24.51: the clicks are taken by ``mch.quick_hud_press`` (first in the tool keymaps) instead of gizmos, which the
drawing tools' own left-click could beat.
Shown in MECHA LAB, Object Mode, with a modelling tool on (not in Select / Move), when the tool has no HUD of
its own on screen.  Preferences: Quick HUD.  Everything else stays in the sidebar.
"""
from __future__ import annotations

import bpy
from bpy.props import FloatVectorProperty, StringProperty

from . import tool_state as ts

ROW_H = 28.0          # px at scale 1 (x the Mecha UI factor: UI scale, big screens, Mecha UI Size)
ROW_W = 230.0
GAP = 6.0


# --- what the HUD shows -------------------------------------------------------------------------------------

def _scene(name):
    return lambda context: getattr(context.scene, name, None)


def _base(context):
    from . import base_mesh
    ob = base_mesh.active_live_base(context)
    return ob.mch_base if ob is not None else base_mesh.scene_defaults(context)


def _sdraw(context):
    from . import surface_draw
    ob = surface_draw.live_object(context, 'BAND')
    return ob.mch_sdraw if ob is not None else surface_draw.scene_settings(context.scene, 'BAND')


def _screw(context):
    from . import screw_stamp
    ob = context.active_object
    return ob.mch_screw if screw_stamp.is_screw(ob) else context.scene.mch_screw


def _detail(context):
    from . import plate_detail
    ob = plate_detail.active_detail(context)
    return ob.mch_pdetail if ob is not None else None


def _plate_scene(context):
    from . import armor_plate
    return None if armor_plate.pending_plate(context) is not None else context.scene.mch_plate   # own HUD then


# tool -> [(data resolver, property)]; a property the data does not have is skipped
SPEC = {
    'CUT': [(_scene('mch_cut'), 'depth'), (_scene('mch_cut'), 'gn_finish'), (_scene('mch_cut'), 'gn_width'),
            (_scene('mch_cut'), 'gn_segments'), (_scene('mch_cut'), 'gn_ramp')],
    'SPLIT': [(_scene('mch_cut'), 'split_mode'), (_scene('mch_cut'), 'gap_width'),
              (_scene('mch_cut'), 'side_a_finish'), (_scene('mch_cut'), 'side_a_width')],
    'BASE': [(_base, 'profile'), (_base, 'height'), (_base, 'bevel_width'), (_base, 'bevel_segments'),
             (_base, 'offset')],
    'CBASE': [(_base, 'profile'), (_base, 'peak'), (_base, 'edge_round'), (_base, 'resolution')],
    'PLATE': [(_plate_scene, 'spacing'), (_plate_scene, 'carve_depth')],
    'DETAIL': [(_detail, 'height'), (_detail, 'lift')],
    'DETAIL2': [(_detail, 'height'), (_detail, 'lift')],
    'DETAIL3': [(_detail, 'profile'), (_detail, 'height'), (_detail, 'lift')],
    'SDRAW': [(_sdraw, 'profile'), (_sdraw, 'width'), (_sdraw, 'height'), (_sdraw, 'edge')],
    'SCREW': [(_screw, 'kind'), (_screw, 'radius'), (_screw, 'height')],
    'CMOVE': [(_scene('mch_concept'), 'radius_px'), (_scene('mch_concept'), 'strength'),
              (_scene('mch_concept'), 'falloff')],
    'CPATH': [(_scene('mch_concept'), 'path_method'), (_scene('mch_concept'), 'path_area'),
              (_scene('mch_concept'), 'radius_px'),
              (_scene('mch_concept'), 'path_hardness'), (_scene('mch_concept'), 'path_taper')],
    'TUBE': [(_scene('mch_tube_defaults'), 'radius')],
    'TUBE_SAME': [(_scene('mch_tube_defaults'), 'radius')],
}
MAX_ROWS = 5


def items(context, tool=None):
    """[(data, prop)] the HUD shows now (only properties that exist)."""
    tool = tool or ts.effective_tool(context)
    out = []
    for resolve, prop in SPEC.get(tool, ()):
        try:
            data = resolve(context)
        except (AttributeError, KeyError, TypeError, ImportError):
            data = None
        if data is not None and prop in data.bl_rna.properties:
            out.append((data, prop))
    return out[:MAX_ROWS]


def visible(context):
    from .workspace_ui import pref
    if not pref('quick_hud', True):
        return False
    from . import bottom_bar
    try:
        if _side_panel_shows(context):
            return False
        return bottom_bar.ui_active(context) and not bottom_bar.in_select(context) and bool(items(context))
    except (AttributeError, KeyError, TypeError):
        return False


def _side_panel_shows(context):
    """0.24.59 the side panel (open, not folded) has the same settings - and the RMB menu too: no HUD then."""
    try:
        from . import side_panel
        return side_panel.on(context) and not side_panel.minimised(context)
    except (ImportError, AttributeError, TypeError, ReferenceError):
        return False


# --- values -----------------------------------------------------------------------------------------------

def points_text(v):
    """0.24.60 ZBrush point counts: from a million in Mil (1,578,000 -> '1.578 Mil'), below with commas."""
    v = int(v)
    if abs(v) >= 1000000:
        return f'{v / 1e6:.3f}'.rstrip('0').rstrip('.') + ' Mil'
    return f'{v:,}' if abs(v) >= 10000 else str(v)


def value_text(data, prop):
    rna = data.bl_rna.properties[prop]
    v = getattr(data, prop)
    name = rna.name or prop
    if rna.type == 'ENUM':
        label = next((i.name for i in rna.enum_items if i.identifier == v), None)
        if label is None:                          # 0.24.60 a dynamic list (MatCap): ask the UI for the name
            try:
                label = bpy.types.UILayout.enum_item_name(data, prop, v) or str(v)
            except (TypeError, AttributeError):
                label = str(v)
        return f'{name}  {label}'
    if rna.type == 'BOOLEAN':
        return f'{name}  {"On" if v else "Off"}'
    if rna.type == 'INT':
        if 'Points' in name:                       # 0.24.60 2.5 Mil (ZBrush)
            return f'{name}  {points_text(v)}'
        return f'{name}  {v:,}' if abs(v) >= 10000 else f'{name}  {v}'   # 0.24.59 20,000 points
    if rna.subtype in {'ANGLE'}:
        import math
        return f'{name}  {math.degrees(v):.0f}°'
    if rna.subtype == 'FACTOR' or rna.subtype == 'PERCENTAGE':
        return f'{name}  {v:.2f}'
    prec = getattr(rna, 'precision', 3)
    return f'{name}  {v:.{prec}f}' if prec < 3 else f'{name}  {v:.3f}'      # 0.24.60 '5.0' (thousands)


def drag_value(data, prop, start, dx, fine=False, px=None):
    """New value after dragging ``dx`` px from ``start`` (whole soft range ≈ 300 px; ints 1 per 8 px).
    0.24.59 ``px`` = the bar's width: the bar's whole range over its own width, so the fill follows the mouse
    (ints: at least 4 px a step)."""
    rna = data.bl_rna.properties[prop]
    k = 0.1 if fine else 1.0
    if px and px > 1:
        if rna.type == 'INT':
            from .mecha_menu import _int_range
            lo, hi = _int_range(rna)
            span = hi - lo
            if 0 < span < 1e9 and px / span < 4.0:   # a big range (points): like a float, rounded
                span = max(span, abs(start))
                return int(max(rna.hard_min, min(rna.hard_max, round(start + dx * k * span / px))))
            per = px / span if 0 < span < 1e9 else 8.0
            return int(max(rna.hard_min, min(rna.hard_max, round(start + dx * k / per))))
        span = rna.soft_max - rna.soft_min
        if not (0.0 < span < 1e6):
            span = max(abs(start) * 2.0, 0.1)
        span = max(span, abs(start))           # a value past the bar's range (a big scene) moves as fast as it is big
        return max(rna.hard_min, min(rna.hard_max, start + dx * k * span / px))
    if rna.type == 'INT':
        lo, hi = rna.hard_min, rna.hard_max
        return int(max(lo, min(hi, round(start + dx * k / 8.0))))
    lo, hi = rna.soft_min, rna.soft_max
    span = hi - lo
    if not (0.0 < span < 1e6):
        span = max(abs(start) * 2.0, 0.1)
    v = start + dx * k * span / 300.0
    return max(rna.hard_min, min(rna.hard_max, v))


def _cursor(context, kind):
    """A drag cursor while a bar is dragged (None: back to normal)."""
    try:
        if kind:
            context.window.cursor_modal_set(kind)
        else:
            context.window.cursor_modal_restore()
    except (AttributeError, RuntimeError, TypeError):
        pass


def step_choice(data, prop, step=1):
    rna = data.bl_rna.properties[prop]
    if rna.type == 'BOOLEAN':
        setattr(data, prop, not getattr(data, prop))
        return
    ids = [i.identifier for i in rna.enum_items]
    cur = getattr(data, prop)
    i = ids.index(cur) if cur in ids else 0
    setattr(data, prop, ids[(i + step) % len(ids)])


def reset(data, prop):
    rna = data.bl_rna.properties[prop]
    if getattr(rna, 'is_array', False):
        return
    setattr(data, prop, rna.default)


def layout_rows(region_w, region_h, n, offset=(0.0, 0.0), left=0.0, k=1.0):
    """Upper left, right of Blender's toolbar (``left``), under the view name / stats text: (grip, [row centres])
    in region px; ``k`` = size factor, ``offset`` = where the grip moved it."""
    rw, rh, gap = ROW_W * k, ROW_H * k, GAP * k
    x = min(max(left + 16.0 * k + rw / 2.0 + offset[0], rw / 2.0 + 4.0), region_w - rw / 2.0 - 4.0)
    top = min(max(region_h - 150.0 * k + offset[1], (rh + gap) * (n + 1)), region_h - rh)
    grip = (x, top)
    rows = [(x, top - (rh + gap) * (i + 1)) for i in range(n)]
    return grip, rows


def _offset(context):
    wm = context.window_manager
    return tuple(getattr(wm, 'mch_hud_offset', (0.0, 0.0)))


def current(context):
    """(items, grip, rows) for drawing, or (None, None, None)."""
    if not visible(context) or context.region is None:
        return None, None, None
    from .ui_gpu import ui_factor
    k = ui_factor(context)
    its = items(context)
    left = 0.0
    area = context.area
    tools = next((r for r in area.regions if r.type == 'TOOLS'), None) if area else None
    if tools is not None and tools.width > 1:
        left = max(0.0, float(tools.x + tools.width - context.region.x))
    try:                                         # 0.24.58 right of the left tool strip
        from . import ui_bars
        left += ui_bars.strip_width(context, k)
    except (ImportError, AttributeError, TypeError):
        pass
    grip, rows = layout_rows(context.region.width, context.region.height, len(its), _offset(context), left, k)
    return its, grip, rows


# --- mouse ------------------------------------------------------------------------------------------------
# 0.24.51 no gizmos: a left click first asks the HUD (first item in the Mecha tool keymaps and in '3D View');
# over a row it drags / clicks it, anywhere else the click passes on to the tool as before.


def hit(context, mx, my):
    """('row', index) / ('grip', None) under the mouse (region px), or None."""
    its, grip, rows = current(context)
    if its is None:
        return None
    from .ui_gpu import ui_factor
    k = ui_factor(context)
    rw, rh = ROW_W * k, ROW_H * k
    for i, (x, y) in enumerate(rows):
        if abs(mx - x) <= rw / 2 and abs(my - y) <= rh / 2:
            return 'row', i
    gx, gy = grip
    if abs(mx - gx) <= rw / 2 and abs(my - gy) <= rh / 2:
        return 'grip', None
    # 0.24.57 anywhere else on the card (the gaps between rows, its edge): the nearest row / the title - a click
    # on the card never falls through to the tool behind it
    pad = 10 * k
    top, bottom = gy + rh / 2 + pad, rows[-1][1] - rh / 2 - pad if rows else gy - rh / 2 - pad
    if abs(mx - gx) <= rw / 2 + pad and bottom <= my <= top:
        if my >= gy - rh / 2 or not rows:
            return 'grip', None
        return 'row', min(range(len(rows)), key=lambda i: abs(rows[i][1] - my))
    return None


class MCH_OT_quick_hud_press(bpy.types.Operator):
    """Quick HUD: drag a row = change it (Shift fine), click = type / next choice, Ctrl+click = default,
    drag the title = move the HUD.  A click elsewhere goes on to the tool"""
    bl_idname = 'mch.quick_hud_press'
    bl_label = 'Quick HUD'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        # 0.24.58 the drawn toolbar / tool strip
        try:
            from . import ui_bars
            inside, item = ui_bars.hit(context, event.mouse_region_x, event.mouse_region_y)
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
            inside, item = False, None
        if inside:
            if item is not None and item.kind == 'mini':      # 0.24.59 a number bar: drag it / click = type
                from . import ui_values
                self.kind, self.index, self.ui_item = 'ui', None, item
                self.x0, self.y0 = event.mouse_region_x, event.mouse_region_y
                self.moved, self.ctrl = False, event.ctrl
                self.init = ui_values.get(item.data, item.prop)
                self.acc, self.last_x = 0.0, event.mouse_x        # 0.24.59 summed moves (the cursor wraps)
                context.window_manager.modal_handler_add(self)
                return {'RUNNING_MODAL'}
            if item is not None:
                msg = ui_bars.run(context, item)
                if msg:
                    self.report({'INFO'}, msg)
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}
        # 0.24.52 the Symmetry / Repetition card first (single clicks)
        try:
            from . import symmetry
            inside, item = symmetry.card_hit(context, event.mouse_region_x, event.mouse_region_y)
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
            inside, item = False, None
        if inside:
            if item is not None:
                msg = symmetry.run_card(context, item)
                if msg:
                    self.report({'INFO'}, msg)
                from . import undo_keep
                undo_keep.push(msg or 'Symmetry')
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}
        try:
            h = hit(context, event.mouse_region_x, event.mouse_region_y) if visible(context) else None
        except (AttributeError, KeyError, TypeError, ReferenceError):
            h = None
        if h is None:
            return {'PASS_THROUGH'}
        self.kind, self.index = h
        self.x0, self.y0 = event.mouse_region_x, event.mouse_region_y
        self.moved = False
        self.ctrl = event.ctrl
        if self.kind == 'grip':
            self.init = _offset(context)
        else:
            data, prop = items(context)[self.index]
            self.init = getattr(data, prop)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _item(self, context):
        its = items(context)
        return its[self.index] if self.index is not None and self.index < len(its) else (None, None)

    def modal(self, context, event):
        if context.area:
            context.area.tag_redraw()
        if self.kind == 'ui':
            return self._modal_ui(context, event)
        dx, dy = event.mouse_region_x - self.x0, event.mouse_region_y - self.y0
        if event.type == 'MOUSEMOVE':
            if abs(dx) > 3 or abs(dy) > 3:
                self.moved = True
            if self.kind == 'grip':
                context.window_manager.mch_hud_offset = (self.init[0] + dx, self.init[1] + dy)
                return {'RUNNING_MODAL'}
            data, prop = self._item(context)
            if data is None:
                return {'CANCELLED'}
            rna = data.bl_rna.properties[prop]
            if self.moved and rna.type in {'INT', 'FLOAT'} and not getattr(rna, 'is_array', False):
                v = drag_value(data, prop, self.init, dx, fine=event.shift)
                if v != getattr(data, prop):
                    setattr(data, prop, v)
                if context.area:
                    context.area.header_text_set(value_text(data, prop) + '   (Shift: fine, Esc / RMB: back)')
            elif self.moved and rna.type == 'ENUM':
                ids = [e.identifier for e in rna.enum_items]
                i0 = ids.index(self.init) if self.init in ids else 0
                v = ids[int(i0 + dx // 30) % len(ids)]
                if v != getattr(data, prop):
                    setattr(data, prop, v)
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            if self.kind == 'grip':
                context.window_manager.mch_hud_offset = self.init
            else:
                data, prop = self._item(context)
                if data is not None and self.moved:
                    setattr(data, prop, self.init)
            return self._end(context, {'CANCELLED'})
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if self.kind == 'grip':
                return self._end(context, {'FINISHED'})
            data, prop = self._item(context)
            if data is None:
                return self._end(context, {'CANCELLED'})
            rna = data.bl_rna.properties[prop]
            if not self.moved:
                if self.ctrl:
                    reset(data, prop)
                elif rna.type in {'BOOLEAN', 'ENUM'}:
                    step_choice(data, prop)
                else:
                    context.window_manager.mch_hud_edit = str(self.index)
                    self._end(context, {'FINISHED'})
                    try:
                        bpy.ops.wm.call_panel(name=MCH_PT_quick_value.bl_idname, keep_open=False)
                    except RuntimeError:
                        pass
                    return {'FINISHED'}
            from . import undo_keep
            if not undo_keep.is_setting(data):           # 0.24.65 a setting is no undo step
                undo_keep.push('HUD ' + (rna.name or prop))
            return self._end(context, {'FINISHED'})
        return {'RUNNING_MODAL'}

    def _modal_ui(self, context, event):
        """0.24.59 A number bar of the top bar / side panel: drag = change (Shift fine), click = type the value,
        Ctrl+click = default, Esc / RMB = back."""
        from . import side_panel, ui_bars, ui_values
        it = self.ui_item
        try:
            if event.type == 'MOUSEMOVE':
                self.acc += event.mouse_x - self.last_x
                self.last_x = event.mouse_x
                if abs(self.acc) > 3 or abs(event.mouse_region_y - self.y0) > 3:
                    if not self.moved:
                        _cursor(context, 'SCROLL_X')
                    self.moved = True
                region = context.region
                rx = event.mouse_x - region.x
                if self.moved and (rx < 8 or rx > region.width - 8):     # at the viewport edge: wrap round
                    tx = int(region.x + region.width / 2)
                    context.window.cursor_warp(tx, event.mouse_y)
                    self.last_x = tx
                if self.moved and ui_values.kind(it.data, it.prop) in {'INT', 'FLOAT'}:
                    # 0.24.59 the bar's range over its own width: the fill follows the mouse
                    v = ui_values.drag(it.data, it.prop, self.init, self.acc, fine=event.shift, width=it.w)
                    if v != ui_values.get(it.data, it.prop):
                        ui_values.set(it.data, it.prop, v)
                    if context.area:
                        context.area.header_text_set(ui_values.text(it.data, it.prop, it.label)
                                                     + '   (Shift: fine, Esc / RMB: back)')
                return {'RUNNING_MODAL'}
            if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
                if self.moved:
                    ui_values.set(it.data, it.prop, self.init)
                return self._end(context, {'CANCELLED'})
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                if not self.moved:
                    if self.ctrl:
                        ui_values.reset(it.data, it.prop)
                    else:
                        self._end(context, {'FINISHED'})
                        ui_bars.open_value(context, it)
                        return {'FINISHED'}
                from . import undo_keep
                if not undo_keep.is_setting(it.data):    # 0.24.65 a setting is no undo step
                    undo_keep.push('Mecha ' + (it.label or it.prop))
                side_panel.dirty()
                return self._end(context, {'FINISHED'})
        except (ReferenceError, AttributeError, KeyError, TypeError):
            return self._end(context, {'CANCELLED'})
        return {'RUNNING_MODAL'}

    def _end(self, context, result):
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()
        if getattr(self, 'kind', '') == 'ui' and getattr(self, 'moved', False):
            _cursor(context, None)
        return result


KEYMAP_ITEM = ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True}, None)


class MCH_PT_quick_value(bpy.types.Panel):
    """Click on a HUD slider: type the exact value"""
    bl_idname = 'MCH_PT_quick_value'
    bl_label = 'Value'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'HEADER'
    bl_ui_units_x = 12

    def draw(self, context):
        try:
            i = int(context.window_manager.mch_hud_edit)
        except ValueError:
            return
        its = items(context)
        if i < len(its):
            data, prop = its[i]
            self.layout.prop(data, prop)
            self.layout.label(text='Ctrl + click a slider: default', icon='INFO')


_label_handle = None


def _draw_labels():
    """The HUD itself (0.24.50 Modeler look): a dark rounded card, the tool name on the grip, rounded value bars."""
    try:
        context = bpy.context
        its, grip, rows = current(context)
        if its is None:
            return
        from . import ui_gpu as G
        from .mecha_menu import _fraction
        k = G.ui_factor(context)
        rw, rh, pad = ROW_W * k, ROW_H * k, 10 * k
        gx, gy = grip
        top = gy + rh / 2 + pad
        bottom = rows[-1][1] - rh / 2 - pad
        G.rounded_rect(gx - rw / 2 - pad - 1, bottom - 1, rw + 2 * pad + 2, top - bottom + 2, 12 * k, G.card_color(edge=True))
        G.rounded_rect(gx - rw / 2 - pad, bottom, rw + 2 * pad, top - bottom, 12 * k, G.card_color())
        tool = ts.TOOL_BY_ID.get(ts.effective_tool(context))
        G.text(gx - rw / 2, gy, (tool[1] if tool else '') + ' tool', 13 * k, G.TEXT)
        G.text(gx + rw / 2, gy, 'drag · click · Ctrl+click', 10 * k, G.TEXT_DIM, 'RIGHT')
        for (data, prop), (x, y) in zip(its, rows):
            rna = data.bl_rna.properties[prop]
            name, _sep, val = value_text(data, prop).partition('  ')
            x0, y0 = x - rw / 2, y - rh / 2
            G.rounded_rect(x0, y0, rw, rh, rh / 2, G.TRACK)
            if rna.type in {'INT', 'FLOAT'}:
                f = _fraction(data, prop)
                if f > 0:
                    G.rounded_rect(x0, y0, max(rh, rw * f), rh, rh / 2, (0.22, 0.38, 0.72, 1.0))
            elif rna.type == 'BOOLEAN' and getattr(data, prop):
                G.rounded_rect(x0, y0, rw, rh, rh / 2, (0.22, 0.38, 0.72, 1.0))
            G.text(x0 + 12 * k, y, name, 12 * k, G.TEXT)
            G.text(x0 + rw - 12 * k, y, val, 12 * k, G.TEXT, 'RIGHT')
    except Exception:          # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


def over_ui(context, x, y):
    """0.24.58 Is region point (x, y) on the drawn toolbar / tool strip, the Symmetry card or the Quick HUD?"""
    try:
        from . import ui_bars
        if ui_bars.hit(context, x, y)[0]:
            return True
    except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
        pass
    try:
        from . import symmetry
        if symmetry.card_hit(context, x, y)[0]:
            return True
    except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
        pass
    try:
        return visible(context) and hit(context, x, y) is not None
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


class MCH_GT_ui_catch(bpy.types.Gizmo):
    """0.24.58 An invisible gizmo over the Mecha viewport panels.  Gizmos get the click before any tool keymap, so
    a plain click / drag on the HUD, the Symmetry card or the toolbar works in every tool - also Blender's own
    Select / Move, whose click-select used to come first (it deselected; only Ctrl + click got through)."""
    bl_idname = 'MCH_GT_ui_catch'

    def draw(self, context):
        pass

    def test_select(self, context, location):
        return 0 if over_ui(context, location[0], location[1]) else -1


class MCH_GGT_ui_catch(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_ui_catch'
    bl_label = 'Mecha Viewport Panels'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT'}

    @classmethod
    def poll(cls, context):
        from . import bottom_bar, zb_sculpt
        try:
            return bottom_bar.ui_active(context) or zb_sculpt.mecha_sculpt(context)   # 0.24.60 + ZBrush / card
        except (AttributeError, KeyError, TypeError, ReferenceError):
            return False

    def setup(self, context):
        gz = self.gizmos.new(MCH_GT_ui_catch.bl_idname)
        gz.target_set_operator(MCH_OT_quick_hud_press.bl_idname)     # the same click handling as the keymaps
        if hasattr(gz, 'use_tooltip'):
            gz.use_tooltip = False                       # the panels show their own names


CLASSES = (MCH_OT_quick_hud_press, MCH_PT_quick_value, MCH_GT_ui_catch, MCH_GGT_ui_catch)
_keymaps = []


def register():
    global _label_handle
    bpy.types.WindowManager.mch_hud_offset = FloatVectorProperty(size=2, default=(0.0, 0.0), options={'SKIP_SAVE'})
    bpy.types.WindowManager.mch_hud_edit = StringProperty(default='', options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:                       # tools that are not Mecha drawing tools (they have it in their keymap)
        km = kc.keymaps.new(name='3D View', space_type='VIEW_3D')
        _keymaps.append((km, km.keymap_items.new('mch.quick_hud_press', 'LEFTMOUSE', 'PRESS', any=True)))
        _keymaps.append((km, km.keymap_items.new('mch.quick_hud_press', 'LEFTMOUSE', 'DOUBLE_CLICK', any=True)))
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')      # 0.24.57 before Object Mode clicks too
        _keymaps.append((km, km.keymap_items.new('mch.quick_hud_press', 'LEFTMOUSE', 'PRESS', any=True)))
        _keymaps.append((km, km.keymap_items.new('mch.quick_hud_press', 'LEFTMOUSE', 'DOUBLE_CLICK', any=True)))
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
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except Exception:            # a stale item (key configuration rebuilt, e.g. factory settings)
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    for name in ('mch_hud_offset', 'mch_hud_edit'):
        if hasattr(bpy.types.WindowManager, name):
            delattr(bpy.types.WindowManager, name)
