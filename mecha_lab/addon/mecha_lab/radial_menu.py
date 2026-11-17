"""0.24.201 Tool Wheel (user: a radial menu at the cursor - click / hover / flick, slots with tools under them -
"우리는 이미 이게 있잖아, 이렇게 분리해 놨으니까 이거 이용해서 하면 될 것 같아": the tool groups of the bottom menu).

V (the Tool Pie key) or Alt + right click (0.24.206, in any tool) opens a wheel at the mouse: the inner ring holds the tool groups (Block-out, Cut, Surface
detail ...), the group under the mouse fans its tools out beyond it.  Three ways to pick, with no mode to set:

* **click**: tap the key - the wheel stays; click a group, then a tool; a click on the middle switches
  Select <-> the tool (0.24.205); Esc / right click / the key again = close;
* **hover**: hold the key, move onto a group and on to a tool, let the key go;
* **flick**: hold the key, flick toward a group and on outward - the tool nearest the mouse is taken when the key
  is let go, the mouse need not be on it.

The layout and the pick are plain functions (``layout`` / ``pick``) so they are tested without a window.
"""
import math
import time

import bpy
from bpy.props import StringProperty

from . import tool_state as ts

R_GROUP = 152.0          # px at UI scale 1: the groups' ring (0.24.205: 118 -> 152, user: "거리가 좀 더 있으면
#                          좋겠어, 지금 너무 몰려 있어서 가독성이 떨어져" - room between the bubbles and off the middle)
R_CENTRE = 81.0          # the middle disc (as before)
B_GROUP = 27.0           # a group bubble's radius
B_TOOL = 23.0            # a tool bubble's radius
R_TOOL = 250.0           # the first arc of tools
ROW_STEP = 58.0          # the next arc
PER_ROW = 7              # tools in one arc
DEAD = 0.30              # x R_GROUP: nearer the middle than this = nothing picked
TAP = 0.28               # s: the key let go sooner than this (and the mouse still) = the wheel stays open
BUBBLE = (0.095, 0.098, 0.11, 1.0)        # 0.24.204 (user: "조그만 원 색도 좀 더 진하게, 명도 낮춰 줘"): darker than
BUBBLE_HOVER = (0.19, 0.2, 0.225, 1.0)    # the panels' buttons (0.18)
BUBBLE_EDGE = (0.17, 0.175, 0.195, 1.0)
STATE = {}               # the open wheel: centre, k, groups, open, hover, handle, area


def groups():
    """[(name, [tool rows])]: the bottom menu's groups (the visible tools, each tool once)."""
    seen, out = set(), []
    for name, rows in ts.grouped_tools():
        rows = [t for t in rows if t[0] not in seen]
        seen.update(t[0] for t in rows)
        if rows:
            out.append((name, rows))
    return out


def group_angle(i, n):
    """Group ``i`` of ``n``: clockwise from the top (degrees, 90 = up)."""
    return 90.0 - 360.0 * i / n


def layout(cx, cy, k, grp, open_idx=-1):
    """The bubbles: dicts(kind 'group' / 'tool', index, id, label, icon, x, y, r).  The open group's tools sit in
    arcs beyond it, centred on its direction (``PER_ROW`` an arc, the first arc nearest)."""
    out = []
    n = len(grp)
    for i, (name, rows) in enumerate(grp):
        a = math.radians(group_angle(i, n))
        out.append(dict(kind='group', index=i, id=name, label=name, icon=rows[0][3],
                        x=cx + math.cos(a) * R_GROUP * k, y=cy + math.sin(a) * R_GROUP * k, r=B_GROUP * k))
    if 0 <= open_idx < n:
        rows = grp[open_idx][1]
        mid = group_angle(open_idx, n)
        for row in range((len(rows) + PER_ROW - 1) // PER_ROW):
            part = rows[row * PER_ROW:(row + 1) * PER_ROW]
            rad = (R_TOOL + row * ROW_STEP) * k
            step = math.degrees(2.0 * math.asin(min(1.0, (B_TOOL * k * 1.12) / rad)))      # bubbles just apart
            for j, t in enumerate(part):
                a = math.radians(mid - (j - (len(part) - 1) / 2.0) * step)
                out.append(dict(kind='tool', index=open_idx, id=t[0], label=t[1], icon=t[3],
                                x=cx + math.cos(a) * rad, y=cy + math.sin(a) * rad, r=B_TOOL * k))
    return out


def pick(cx, cy, k, grp, open_idx, mx, my):
    """What the mouse at (mx, my) means: ('tool', id) / ('group', index) / None (the middle).  On a bubble = that
    bubble; else by direction - near the ring the group that way, farther out the open group's nearest tool."""
    items = layout(cx, cy, k, grp, open_idx)
    for it in items:
        if math.hypot(mx - it['x'], my - it['y']) <= it['r'] * 1.08:
            return (it['kind'], it['id'] if it['kind'] == 'tool' else it['index'])
    d = math.hypot(mx - cx, my - cy)
    if d < DEAD * R_GROUP * k:
        return None
    n = len(grp)
    ang = math.degrees(math.atan2(my - cy, mx - cx))
    gi = min(range(n), key=lambda i: abs((group_angle(i, n) - ang + 180.0) % 360.0 - 180.0))
    tools = [it for it in items if it['kind'] == 'tool']
    if tools and d > (R_GROUP + B_GROUP * 1.25) * k:
        # (beyond the ring: toward the open group's tools unless the mouse has clearly turned to another group)
        off = abs((group_angle(open_idx, n) - ang + 180.0) % 360.0 - 180.0)
        if off < max(360.0 / n, 62.0):
            best = min(tools, key=lambda it: math.hypot(mx - it['x'], my - it['y']))
            return ('tool', best['id'])
    return ('group', gi)


def fit_centre(mx, my, w, h, k):
    """The wheel's middle: the mouse, kept far enough from the region's edges for the groups' ring to show."""
    m = (R_GROUP + B_GROUP + 8.0) * k
    if w < 2 * m or h < 2 * m:
        return mx, my
    return min(max(mx, m), w - m), min(max(my, m), h - m)


# ---- drawing ----------------------------------------------------------------------------------------------------------
def _disc(g, x, y, r, color):
    g.rounded_rect(x - r, y - r, 2 * r, 2 * r, r, color)


def wheel_size():
    """Preferences > Tool Wheel Size (x the UI size)."""
    try:
        from .workspace_ui import pref
        return max(0.5, min(2.5, float(pref('wheel_size', 1.0))))
    except (TypeError, ValueError, ImportError):
        return 1.0


def opacity():
    """Preferences > Tool Wheel Opacity (0 .. 1)."""
    try:
        from .workspace_ui import pref
        return max(0.0, min(1.0, float(pref('wheel_opacity', 0.92))))
    except (TypeError, ValueError, ImportError):
        return 0.92


def centre_state(context):
    """(tool id, its name, is it on now) - what the middle of the wheel switches: Select <-> this tool."""
    from . import bottom_bar
    try:
        tid, t = bottom_bar.chosen_tool(context)
        live = bottom_bar.tool_live(context)
    except (AttributeError, KeyError, TypeError):
        tid, t, live = '', None, False
    if not t:
        tid, t = 'CUT', ts.TOOL_BY_ID.get('CUT')
    return tid, (t[1] if t else 'Tool'), bool(live)


def centre_click(context):
    """The middle clicked: the tool on -> Select; Select -> the tool again.  Returns what is on now."""
    tid, label, live = centre_state(context)
    try:
        bpy.ops.mch.tool_active()
    except RuntimeError:
        if live:
            bpy.ops.mch.select_move()
        else:
            bpy.ops.mch.bar_tool(tool=tid)
    return 'Select' if live else label


def _label(g, x, y, s, size, k, bright):
    s = g.fit(s, size, 150 * k)
    w = max(30.0 * k, len(s) * size * 0.64 + 12.0 * k)
    h = size * 1.7
    g.rounded_rect(x - w / 2, y - h / 2, w, h, 6.0 * k, (0.06, 0.06, 0.07, 0.88))
    g.text(x, y, s, size, g.TEXT if bright else g.TEXT_DIM, 'CENTER')


def _draw():
    st = STATE
    if not st or bpy.context.area is None or bpy.context.area.as_pointer() != st.get('area'):
        return
    from . import ui_gpu as g
    cx, cy, k = st['cx'], st['cy'], st['k']
    grp, open_idx, hover = st['groups'], st['open'], st['hover']
    items = layout(cx, cy, k, grp, open_idx)
    try:
        cur = ts.effective_tool(bpy.context)
    except (AttributeError, KeyError):
        cur = ''
    # 0.24.203 Tool Wheel Opacity: the big disc in the middle only (user: "가운데에 제일 큰 원 말이야, 다른 건 냅둬")
    _disc(g, cx, cy, R_CENTRE * k, (0.085, 0.087, 0.095, opacity()))
    # 0.24.205 the middle: Select <-> the tool by a click (user: "클릭으로 셀렉이랑 툴 번갈아 가면서 할 수 있게 그걸 중앙에다가
    # 놔 줄래? 다른 걸로 커서 옮기면 그때는 그 툴 이름 뜨게")
    if hover is not None and hover[0] == 'tool':
        t = ts.TOOL_BY_ID.get(hover[1])
        g.text(cx, cy + 7 * k, grp[open_idx][0].upper() if 0 <= open_idx < len(grp) else '', 10 * k, g.TEXT_DIM, 'CENTER')
        g.text(cx, cy - 11 * k, t[1] if t else '', 13 * k, g.TEXT, 'CENTER')
    elif hover is not None:
        g.text(cx, cy, grp[hover[1]][0].upper(), 13 * k, g.TEXT, 'CENTER')
    else:
        tid, label, live = centre_state(bpy.context)
        now, nxt = (label, 'Select') if live else ('Select', label)
        rr = (R_CENTRE - 6.0) * k       # (a ring, not a second disc: Tool Wheel Opacity stays the disc's)
        g.polyline(g.circle_pts(cx, cy, rr, 64), g.ACCENT if live else BUBBLE_HOVER, 3.0 * k, closed=True)
        sz = 30.0 * k
        if live and tid in ts.TOOL_BY_ID:
            g.image(g.icon_path(ts.TOOL_BY_ID[tid][3]), cx - sz / 2, cy + 6.0 * k, sz)
        else:
            g.glyph('arrow', cx - sz / 2, cy + 6.0 * k, sz)
        g.text(cx, cy - 6 * k, g.fit(now.upper(), 12 * k, rr * 1.8), 12 * k, g.TEXT, 'CENTER')
        g.text(cx, cy - 24 * k, g.fit('click: ' + nxt, 9.5 * k, rr * 1.8), 9.5 * k, g.TEXT_DIM, 'CENTER')
    lines = []
    for it in items:
        if it['kind'] == 'group':
            a = math.atan2(it['y'] - cy, it['x'] - cx)
            r0 = R_CENTRE * k
            lines.append(((cx + math.cos(a) * r0, cy + math.sin(a) * r0),
                          (it['x'] - math.cos(a) * it['r'], it['y'] - math.sin(a) * it['r'])))
    if lines:
        g.lines(lines, (0.4, 0.42, 0.47, 0.5), 1.5)
    for it in items:
        is_group = it['kind'] == 'group'
        lit = (hover == ('group', it['index'])) if is_group else (hover == ('tool', it['id']))
        opened = is_group and it['index'] == open_idx
        using = (not is_group) and it['id'] == cur
        r = it['r'] * (1.1 if lit else 1.0)
        _disc(g, it['x'], it['y'], r + 2.0 * k, g.ACCENT if (lit or opened) else (g.ORANGE if using else BUBBLE_EDGE))
        _disc(g, it['x'], it['y'], r, BUBBLE_HOVER if lit else BUBBLE)
        s = r * 1.18
        g.image(g.icon_path(it['icon']), it['x'] - s / 2, it['y'] - s / 2 + 2.0 * k, s)
        if is_group:                 # (the groups keep their names; a tool's name shows when the mouse is on it -
            _label(g, it['x'], it['y'] - r - 9.0 * k, it['label'], 9.5 * k, k, lit or opened)   # in an arc the
    for it in items:                 # names would lie on the next bubbles)
        if it['kind'] == 'tool' and hover == ('tool', it['id']):
            a = math.atan2(it['y'] - cy, it['x'] - cx)
            d = it['r'] * 1.1 + 16.0 * k
            _label(g, it['x'] + math.cos(a) * d * 1.6, it['y'] + math.sin(a) * d, it['label'], 12.0 * k, k, True)
    g.done()


def _close(context):
    h = STATE.pop('handle', None)
    if h is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(h, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
    STATE.clear()
    if context.area is not None:
        context.area.tag_redraw()


def is_open():
    return bool(STATE)


class MCH_OT_radial_menu(bpy.types.Operator):
    """Tool Wheel: the tool groups in a ring at the mouse, the group under the mouse fans out its tools. Tap the key = it stays (click a tool); hold the key = let go on a tool (or flick toward it)"""
    bl_idname = 'mch.radial_menu'
    bl_label = 'Tool Wheel'
    bl_options = {'INTERNAL'}
    key: StringProperty(default='V')
    held: bpy.props.BoolProperty(default=True)       # (False: opened by a click - it stays, click mode)

    @classmethod
    def poll(cls, context):
        from . import bottom_bar
        return bottom_bar.ui_active(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if STATE:
            _close(context)
            return {'CANCELLED'}
        from .ui_gpu import ui_factor
        region = context.region
        k = ui_factor(context, region) * wheel_size()
        grp = groups()
        if not grp:
            return {'CANCELLED'}
        cx, cy = fit_centre(event.mouse_region_x, event.mouse_region_y, region.width, region.height, k)
        STATE.update(cx=cx, cy=cy, k=k, groups=grp, open=-1, hover=None, area=context.area.as_pointer())
        self.t0 = time.monotonic()
        self.start = (event.mouse_region_x, event.mouse_region_y)
        self.moved = False
        self.held = bool(self.properties.held) if self.properties.is_property_set('held') else True
        self.region = region
        STATE['handle'] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def _mouse(self, event):
        return event.mouse_x - self.region.x, event.mouse_y - self.region.y

    def _hover(self, context, event):
        st = STATE
        mx, my = self._mouse(event)
        if math.hypot(mx - self.start[0], my - self.start[1]) > 8.0 * st['k']:
            self.moved = True
        h = pick(st['cx'], st['cy'], st['k'], st['groups'], st['open'], mx, my)
        if h is not None and h[0] == 'group':
            st['open'] = h[1]
        st['hover'] = h
        context.area.tag_redraw()
        return h

    def _run(self, context, tool):
        _close(context)
        try:
            bpy.ops.mch.bar_tool(tool=tool)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex).splitlines()[0])
            return {'CANCELLED'}
        t = ts.TOOL_BY_ID.get(tool)
        self.report({'INFO'}, t[1] if t else tool)
        return {'FINISHED'}

    def modal(self, context, event):
        if not STATE or context.area is None:
            _close(context)
            return {'CANCELLED'}
        if event.type == 'ESC' or (event.type == 'RIGHTMOUSE' and self.key != 'RIGHTMOUSE'):
            _close(context)
            return {'CANCELLED'}
        if event.type == 'MOUSEMOVE':
            self._hover(context, event)
            return {'RUNNING_MODAL'}
        if event.type == self.key and event.value == 'RELEASE' and self.held:
            self.held = False
            h = self._hover(context, event)
            if not self.moved and time.monotonic() - self.t0 < TAP:
                return {'RUNNING_MODAL'}                      # a tap: the wheel stays (click mode)
            if h is not None and h[0] == 'tool':
                return self._run(context, h[1])
            if h is None:                                     # held and let go in the middle: nothing
                _close(context)
                return {'CANCELLED'}
            return {'RUNNING_MODAL'}                          # let go on a group: it stays open, click its tool
        if event.type == self.key and event.value == 'PRESS' and not self.held:
            _close(context)                                   # the key again: close
            return {'CANCELLED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            h = self._hover(context, event)
            if h is None:                                     # the middle: Select <-> the tool
                _close(context)
                self.report({'INFO'}, centre_click(context))
                return {'FINISHED'}
            if h[0] == 'tool':
                return self._run(context, h[1])
            return {'RUNNING_MODAL'}
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        return {'RUNNING_MODAL'}


# ---- 0.24.205 a plain left click on empty space opens it (user: "좌클릭으로 그냥 해 줘" / "더블클릭이 아니라 그냥 클릭") ---
def click_wanted(context, event):
    """A left press that may become the wheel: Select / Move is on (a tool's own clicks are the tool's), no Ctrl /
    Shift / Alt, nothing under the mouse, the wheel not open, the setting on."""
    if STATE or event.type != 'LEFTMOUSE' or event.value not in {'PRESS', 'CLICK'} or event.ctrl or event.shift \
            or event.alt:
        return False
    try:
        from . import bottom_bar
        from .workspace_ui import object_under_mouse, pref
        if not pref('wheel_click', False) or not bottom_bar.ui_active(context) or context.mode != 'OBJECT':
            return False
        if context.area is None or context.area.type != 'VIEW_3D' or not bottom_bar.in_select(context):
            return False
        from . import ui_bars
        from . import ui_bars
        if ui_bars.hit(context, event.mouse_region_x, event.mouse_region_y)[0]:      # (on a card: the card's)
            return False
        return object_under_mouse(context, event) is None
    except (AttributeError, KeyError, TypeError, ReferenceError, RuntimeError, ImportError):
        return False


def click_start(context, event):
    """(from the press handler, the press not on any card) watch this press: let go without a drag = the wheel."""
    if not click_wanted(context, event):
        return False
    try:
        return 'RUNNING_MODAL' in bpy.ops.mch.radial_click('INVOKE_DEFAULT')
    except RuntimeError:
        return False


class MCH_OT_radial_click(bpy.types.Operator):
    """A left click on empty space (Select / Move on): the Tool Wheel opens there; a drag stays Blender's box select"""
    bl_idname = 'mch.radial_click'
    bl_label = 'Tool Wheel (click)'
    bl_options = {'INTERNAL'}

    direct: bpy.props.BoolProperty(default=False)     # (from the Select tool's own keymap: the click is complete)

    def invoke(self, context, event):
        if self.direct and not click_wanted(context, event):
            return {'PASS_THROUGH'}
        self.start = (event.mouse_x, event.mouse_y)
        self.t0 = time.monotonic()
        context.window_manager.modal_handler_add(self)
        # (the press goes on: Blender's own click on empty space - deselect - and its box-select drag still work)
        return {'RUNNING_MODAL', 'PASS_THROUGH'} if self.direct else {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            if math.hypot(event.mouse_x - self.start[0], event.mouse_y - self.start[1]) > 6.0:
                return {'CANCELLED', 'PASS_THROUGH'}          # a drag: Blender's box select
            return {'PASS_THROUGH'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if time.monotonic() - self.t0 < 0.6 and not STATE:
                try:
                    bpy.ops.mch.radial_menu('INVOKE_DEFAULT', held=False)
                except RuntimeError:
                    pass
            return {'FINISHED', 'PASS_THROUGH'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            return {'CANCELLED', 'PASS_THROUGH'}
        return {'PASS_THROUGH'}


_keymaps = []
SELECT_KEYMAPS = ('3D View Tool: Select Box', '3D View Tool: Tweak', '3D View Tool: Select Circle',
                  '3D View Tool: Select Lasso')


def register():
    bpy.utils.register_class(MCH_OT_radial_menu)
    bpy.utils.register_class(MCH_OT_radial_click)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:                # (the Select tools take the left button before the 3D View keymap sees it)
        # 0.24.206 Alt + right click opens it in ANY tool (user: "그냥 알트 우클릭으로 하는 게 나을 것 같다, 셀렉트에서만
        # 되네 이러니까"): no Mecha tool, nor Blender's Object Mode, uses Alt + right button
        for name, space in (('3D View', 'VIEW_3D'), ('Object Mode', 'EMPTY')):
            km = kc.keymaps.new(name=name, space_type=space)
            item = km.keymap_items.new('mch.radial_menu', 'RIGHTMOUSE', 'PRESS', alt=True)
            item.properties.key = 'RIGHTMOUSE'
            _keymaps.append((km, item))
        for name in SELECT_KEYMAPS:
            km = kc.keymaps.new(name=name, space_type='VIEW_3D', region_type='WINDOW')
            item = km.keymap_items.new('mch.radial_menu', 'RIGHTMOUSE', 'PRESS', alt=True)
            item.properties.key = 'RIGHTMOUSE'
            _keymaps.append((km, item))
            # (PRESS, in the tool's own keymap: Blender's select there swallows a press on empty space, so neither a
            #  CLICK item nor the 3D View keymap ever saw it)
            item = km.keymap_items.new('mch.radial_click', 'LEFTMOUSE', 'PRESS')
            item.properties.direct = True
            _keymaps.append((km, item))


def unregister():
    try:
        _close(bpy.context)
    except (AttributeError, ReferenceError):
        STATE.clear()
    for km, item in _keymaps:
        try:
            km.keymap_items.remove(item)
        except (RuntimeError, ReferenceError):
            pass
    _keymaps.clear()
    bpy.utils.unregister_class(MCH_OT_radial_click)
    bpy.utils.unregister_class(MCH_OT_radial_menu)
