"""0.12 Mecha Lab UX (from the browser prototype v2.1): bottom toolbar, tool pie
(Shift+Q since 0.22.1), Q toggles between Select / Move and the last modelling tool.

All of it is active only in the MECHA LAB workspace (Object Mode); outside it
the keys keep their Blender meaning because the operators' poll fails there.

Bottom toolbar = 2D button gizmos (the same kind as the viewport navigation
buttons): no modal operator, so it cannot fight the Cut / Split stroke modal.
"""
import bpy
from bpy.props import EnumProperty, StringProperty

from . import tool_state as ts

# (id, label, key, Blender icon, operator, tool argument)
BAR_TOOLS = (
    ('SELECT', 'Select', 'F', 'RESTRICT_SELECT_OFF', 'mch.select_move', None),
    ('CMOVE', 'Move', 'D', 'VIEW_PAN', 'mch.set_tool', 'CMOVE'),
    ('CPATH', 'Path', '', 'MOD_CURVE', 'mch.set_tool', 'CPATH'),
    ('CUT', 'Cut', 'C', 'SELECT_SUBTRACT', 'mch.set_tool', 'CUT'),
    ('SPLIT', 'Split', '', 'MOD_EDGESPLIT', 'mch.set_tool', 'SPLIT'),
    ('BASE', 'Base', '', 'MOD_SOLIDIFY', 'mch.set_tool', 'BASE'),
    ('BOOLEAN', 'Boolean', 'B', 'MOD_BOOLEAN', 'mch.set_tool', 'BOOLEAN'),
    ('MIRROR', 'Symmetry', '', 'MOD_MIRROR', 'mch.set_tool', 'MIRROR'),
    ('PRIMITIVE', 'Primitive', '', 'MESH_CUBE', 'mch.set_tool', 'PRIMITIVE'),
    ('RADIAL', 'Radial', '', 'MOD_SCREW', 'mch.set_tool', 'RADIAL'),
    ('PLATE', 'Plate', '', 'MESH_GRID', 'mch.set_tool', 'PLATE'),
    ('DETAIL', 'Detail', '', 'MESH_PLANE', 'mch.set_tool', 'DETAIL'),
    ('DETAIL2', 'Detail 2', '', 'SURFACE_NSURFACE', 'mch.set_tool', 'DETAIL2'),
    ('DETAIL3', 'Detail 3', '', 'MESH_PLANE', 'mch.set_tool', 'DETAIL3'),
    ('SCREW', 'Screw', '', 'RADIOBUT_ON', 'mch.set_tool', 'SCREW'),
    ('TUBE', 'Curve', '', 'CURVE_BEZCURVE', 'mch.set_tool', 'TUBE'),
    ('TUBE_SAME', 'Line Curve', '', 'CURVE_BEZCURVE', 'mch.set_tool', 'TUBE_SAME'),
    ('SKIN', 'Skin', '', 'OUTLINER_OB_FORCE_FIELD', 'mch.creature_brush', 'SKIN'),
    ('SHELL', 'Shell', '', 'MESH_ICOSPHERE', 'mch.creature_brush', 'SHELL'),
)
SELECT_NATIVE = {'builtin.move', 'builtin.select', 'builtin.select_box', 'builtin.select_circle',
                 'builtin.select_lasso', 'builtin.rotate', 'builtin.scale', 'builtin.transform'}
SIZES = {'S': 34, 'M': 42, 'L': 52}       # button diameter in px at UI scale 1
ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
_label_handle = None


def _pref(name, default=True):
    from .workspace_ui import pref
    return pref(name, default)


def ui_active(context):
    return (ts.is_mecha_workspace(getattr(context, 'workspace', None)) and context.mode == 'OBJECT')


MIN_BUTTON = 22.0          # 0.24.49 smallest button (px at UI scale 1) before the bar goes to two rows


def toolbar_layout(region_width, ui_scale=1.0, count=len(BAR_TOOLS), size='M', margin=26.0, factor=1.0):
    """Centres (x, y) of the toolbar buttons in region pixels, bottom centre.
    ``factor`` = Preferences > Icon Size > Bottom Toolbar.
    0.24.49 a narrow viewport: the buttons shrink to fit (down to MIN_BUTTON), then wrap to two rows,
    so none goes off the screen."""
    f = max(0.3, float(factor))
    d = SIZES.get(size, SIZES['M']) * ui_scale * f
    gap = 8.0 * ui_scale * max(1.0, f)       # room for the names under bigger buttons
    avail = max(1.0, region_width - 24.0 * ui_scale)
    rows = 1
    per = count
    total = count * d + (count - 1) * gap
    if total > avail and count > 1:
        k = avail / total
        if d * k >= MIN_BUTTON * ui_scale:
            d, gap = d * k, gap * k
        else:
            rows = 2
            per = (count + 1) // 2
            total = per * d + (per - 1) * gap
            if total > avail:
                k = avail / total
                d, gap = d * k, gap * k
    y = margin * ui_scale * max(0.8, f) + d / 2.0
    step_y = d + 16.0 * ui_scale * max(0.6, f)      # the second row sits above, labels fit between
    out = []
    for i in range(count):
        r, c = divmod(i, per)
        n = min(per, count - r * per)
        x0 = region_width / 2.0 - (n * d + (n - 1) * gap) / 2.0 + d / 2.0
        out.append((x0 + c * (d + gap), y + r * step_y))
    return out, d


def current_bar_tool(context):
    """Which toolbar button shows as active."""
    wm = context.window_manager
    native = ts.native_tool_id(context)
    if native in SELECT_NATIVE and getattr(wm, 'mch_ui_mode', 'TOOL') == 'SELECT':
        return 'SELECT'
    try:
        tool = ts.effective_tool(context)
    except (AttributeError, KeyError, TypeError):
        return ''
    scene = context.scene
    if tool == 'WRINKLE' and getattr(getattr(scene, 'mch_wrinkle', None), 'creature', False):
        return 'SKIN'
    if tool == 'PLATE' and getattr(getattr(scene, 'mch_plate', None), 'creature', False):
        return 'SHELL'
    return tool


def note_tool(context, tool_id):
    """Called by activate_mecha_tool: remember the last modelling tool (not undoable)."""
    wm = context.window_manager
    if wm is None or not hasattr(wm, 'mch_last_model'):
        return
    wm.mch_ui_mode = 'TOOL'
    if tool_id in ts.TOOL_BY_ID:
        wm.mch_last_model = tool_id
        from . import tool_recent
        tool_recent.note(tool_id)                         # 0.24.49 Recent list (RMB popup)


def note_select(context):
    wm = context.window_manager
    if wm is not None and hasattr(wm, 'mch_ui_mode'):
        wm.mch_ui_mode = 'SELECT'


def in_select(context):
    wm = context.window_manager
    native = ts.native_tool_id(context)
    return native in SELECT_NATIVE and (getattr(wm, 'mch_ui_mode', 'TOOL') == 'SELECT' or
                                        ts.TOOL_BY_ID.get(ts.effective_tool(context), (None,) * 6)[5] is not None)


# -----------------------------------------------------------------------------
# Q pie / Shift+Q
# -----------------------------------------------------------------------------


PIE_SHARED = {'BASE': ('PLATE',), 'RADIAL': ('TUBE',), 'PRIMITIVE': ('CMOVE', 'CPATH')}      # pie slot -> extra tools stacked under it


class MCH_MT_tool_pie(bpy.types.Menu):
    bl_idname = 'MCH_MT_tool_pie'
    bl_label = 'Mecha Tools'

    def draw(self, context):
        pie = self.layout.menu_pie()
        # pie order: W, E, S, N, NW, NE, SW, SE  (N = Select, clockwise as in the prototype)
        order = ('PRIMITIVE', 'SPLIT', 'BOOLEAN', 'SELECT', 'RADIAL', 'CUT', 'MIRROR', 'BASE')
        by_id = {t[0]: t for t in BAR_TOOLS}
        for tid in order:
            t = by_id[tid]
            if t[4] == 'mch.select_move':
                pie.operator('mch.select_move', text='Select / Move  (F)', icon=t[3])
            elif tid in PIE_SHARED:
                # 0.19.2: a pie has 8 slots - this slot holds a small column of tools
                col = pie.column(align=True)
                for sid in (tid,) + PIE_SHARED[tid]:
                    st = by_id[sid]
                    col.operator('mch.set_tool', text=st[1], icon=st[3]).tool = st[5]
            else:
                op = pie.operator('mch.set_tool', text=t[1] + (f'  ({t[2]})' if t[2] else ''), icon=t[3])
                op.tool = t[5]


class MCH_OT_tool_pie(bpy.types.Operator):
    """V: all Mecha tools as a pie at the mouse (MECHA LAB only)"""
    bl_idname = 'mch.tool_pie'
    bl_label = 'Mecha Tool Pie'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _pref('tool_pie') and ui_active(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        bpy.ops.wm.call_menu_pie(name=MCH_MT_tool_pie.bl_idname)
        return {'FINISHED'}

    def execute(self, context):
        bpy.ops.wm.call_menu_pie(name=MCH_MT_tool_pie.bl_idname)
        return {'FINISHED'}


class MCH_OT_toggle_last_tool(bpy.types.Operator):
    """Q: Select / Move <-> the last Mecha modelling tool, one key like Tab (shape and settings are kept)"""
    bl_idname = 'mch.toggle_last_tool'
    bl_label = 'Select <-> Last Tool'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return _pref('last_tool_key') and ui_active(context) and context.area is not None and context.area.type == 'VIEW_3D'

    def execute(self, context):
        from .workspace_ui import activate_mecha_tool
        wm = context.window_manager
        if in_select(context):
            tool = wm.mch_last_model if wm.mch_last_model in ts.TOOL_BY_ID else 'CUT'
            activate_mecha_tool(context, tool)
            self.report({'INFO'}, 'Back to ' + ts.TOOL_BY_ID[tool][1])
        else:
            try:
                current = ts.effective_tool(context)
                if current in ts.TOOL_BY_ID:
                    wm.mch_last_model = current
            except (AttributeError, KeyError, TypeError):
                pass
            bpy.ops.mch.select_move()
        return {'FINISHED'}


def bar_tip(tool_id):
    """Toolbar tooltip: just the button's name and its key (0.14, not a description)."""
    t = next((t for t in BAR_TOOLS if t[0] == tool_id), None)
    if t is None:
        full = ts.TOOL_BY_ID.get(tool_id)
        return full[1] if full else 'Mecha Tool'
    return t[1] + (f'  ({t[2]})' if t[2] else '')


class MCH_OT_bar_tool(bpy.types.Operator):
    """Bottom toolbar button"""
    bl_idname = 'mch.bar_tool'
    bl_label = 'Mecha Tool'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='CUT', options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return bar_tip(properties.tool)

    def execute(self, context):
        if self.tool == 'SELECT':
            return bpy.ops.mch.select_move()
        if self.tool in {'SKIN', 'SHELL'}:
            return bpy.ops.mch.creature_brush(kind=self.tool)
        if self.tool not in ts.TOOL_BY_ID:
            return {'CANCELLED'}
        from .workspace_ui import activate_mecha_tool
        activate_mecha_tool(context, self.tool)
        return {'FINISHED'}


class MCH_OT_toggle_targets(bpy.types.Operator):
    """T (Cut / Split tool): Auto Target <-> Selected Only"""
    bl_idname = 'mch.toggle_targets'
    bl_label = 'Toggle Cut Targets'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        from . import target_rules
        return hasattr(context.scene, 'mch_cut') and (ts.effective_tool(context) in {'CUT', 'SPLIT'}
                                                       or ts.effective_tool(context) in target_rules.PICKING)

    def execute(self, context):
        cut = context.scene.mch_cut
        cut.targets = 'SELECTED' if cut.targets == 'AUTO' else 'AUTO'
        self.report({'INFO'}, 'Targets: ' + ('Auto (what the shape covers)' if cut.targets == 'AUTO'
                                              else 'Selected only'))
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# Bottom toolbar (2D button gizmos)
# -----------------------------------------------------------------------------


class MCH_GGT_bottom_toolbar(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_bottom_toolbar'
    bl_label = 'Mecha Bottom Toolbar'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return _pref('bottom_toolbar') and not _pref('drawn_toolbar', True) and ui_active(context)

    def setup(self, context):
        self.buttons = []
        for tid, label, key, icon, op, arg in BAR_TOOLS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            # one operator for every button so the tooltip is the button's name
            gz.target_set_operator('mch.bar_tool').tool = tid
            gz.color = BASE_COL
            gz.alpha = 0.9
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.buttons.append((tid, gz))

    def draw_prepare(self, context):
        region = context.region
        ui = context.preferences.system.ui_scale
        # 0.24.49 the positions are multiplied by the UI scale below, so the width must be unscaled too
        pos, d = toolbar_layout(region.width / max(ui, 1e-3), 1.0, len(self.buttons), _pref('toolbar_size', 'M'),
                                factor=_pref('toolbar_scale', 1.0))
        active = current_bar_tool(context)
        for (tid, gz), (x, y) in zip(self.buttons, pos):
            # 'SCALE' multiplies the gizmo by the UI scale; positions are in region px
            gz.scale_basis = d / 2.0
            gz.matrix_basis[0][3] = x * ui
            gz.matrix_basis[1][3] = y * ui
            on = tid == active
            gz.color = ACCENT if on else BASE_COL
            gz.alpha = 1.0 if on else 0.9


# -----------------------------------------------------------------------------
# 0.19.2 Tool Active button: top-left of the viewport, next to Blender's toolbar.
# Shows the chosen Mecha tool; click = switch it on in the viewport (click
# again = back to Select / Move).
# -----------------------------------------------------------------------------


def chosen_tool(context):
    st = getattr(context.scene, 'mch_settings', None)
    tid = getattr(st, 'mch_active_tool', '') if st else ''
    t = ts.TOOL_BY_ID.get(tid)
    return (tid, t) if t is not None and t[5] else (None, None)


def tool_live(context):
    tid, t = chosen_tool(context)
    return bool(t) and ts.native_tool_id(context) == t[5]


def active_button_pos(context):
    """Region px (UI scale 1) of the Tool Active button: right of Blender's toolbar, upper left."""
    region, area = context.region, context.area
    ui = context.preferences.system.ui_scale or 1.0
    left = 0.0
    tools = next((r for r in area.regions if r.type == 'TOOLS'), None) if area else None
    if tools is not None and tools.width > 1:
        left = max(0.0, float(tools.x + tools.width - region.x))
    f = max(0.6, float(_pref('toolbar_scale', 1.0) or 1.0))
    try:                                         # 0.24.58 right of the left tool strip
        from . import ui_bars
        from .ui_gpu import ui_factor
        left += ui_bars.strip_width(context, ui_factor(context, region))
    except (ImportError, AttributeError, TypeError):
        pass
    return left / ui + 30.0 * f, region.height / ui * 0.6     # 0.19.3: middle left (user placement)


def _btn_factor():
    return max(0.6, float(_pref('toolbar_scale', 1.0) or 1.0))


class MCH_OT_tool_active(bpy.types.Operator):
    """Switch the chosen Mecha tool on in the viewport (click again: back to Select / Move)"""
    bl_idname = 'mch.tool_active'
    bl_label = 'Tool Active'
    bl_options = {'INTERNAL'}

    @classmethod
    def description(cls, context, properties):
        tid, t = chosen_tool(context)
        if not t:
            return cls.__doc__
        return (f'{t[1]} is ON: click to go back to Select / Move' if tool_live(context)
                else f'Switch {t[1]} on in the viewport')

    def execute(self, context):
        tid, t = chosen_tool(context)
        if not t:
            return {'CANCELLED'}
        if tool_live(context):
            bpy.ops.mch.select_move()
        else:
            from .workspace_ui import activate_mecha_tool
            activate_mecha_tool(context, tid)
        return {'FINISHED'}


class MCH_GGT_tool_active(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_tool_active'
    bl_label = 'Mecha Tool Active'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):                      # 0.24.59 the drawn actions card has it (Drawn Toolbar on)
        return ui_active(context) and chosen_tool(context)[1] is not None and not _pref('drawn_toolbar', True)

    def setup(self, context):
        gz = self.gizmos.new('GIZMO_GT_button_2d')
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.tool_active')
        gz.color = BASE_COL
        gz.alpha = 0.95
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.button = gz
        self.icon = ''

    def draw_prepare(self, context):
        tid, t = chosen_tool(context)
        gz = self.button
        gz.hide = t is None
        if t is None:
            return
        if self.icon != t[4]:
            try:
                gz.icon = t[4]
                self.icon = t[4]
            except (TypeError, ValueError):
                pass
        ui = context.preferences.system.ui_scale
        x, y = active_button_pos(context)
        gz.scale_basis = 24.0 * _btn_factor()
        gz.matrix_basis[0][3] = x * ui
        gz.matrix_basis[1][3] = y * ui
        gz.color = ACCENT if tool_live(context) else BASE_COL


TIDY = (('RESET_AXIS', 'ORIENTATION_GLOBAL', 'Reset Axis',
         'Local axes back to the world axes, the shape stays where it is (applies the rotation)'),
        ('ORIGIN_GEOMETRY', 'PIVOT_MEDIAN', 'Origin to Geometry', 'Origin to the middle of the mesh'),
        ('ORIGIN_CURSOR', 'PIVOT_CURSOR', 'Origin to 3D Cursor', 'Origin to the 3D cursor'),
        ('SYMMETRY', 'ARROW_LEFTRIGHT', 'Symmetry',
         'Make the mesh symmetric: lean the mouse toward the side to copy to, Enter applies'),
        ('MIRROR', 'MOD_MIRROR', 'Mirror',
         'Live Mirror modifier on the selected meshes (stays live; Apply / Remove in the popup next to it)'))


def _unlive(ob):
    """Live generated shapes rebuild their mesh: freeze them first so the change sticks."""
    done = False
    try:
        from . import station_primitive as sp
        done |= bool(sp.freeze(ob))
    except (ImportError, AttributeError):
        pass
    for attr in ('mch_base', 'mch_extract'):
        pg = getattr(ob, attr, None)
        for flag in ('live', 'is_part'):
            if pg is not None and getattr(pg, flag, False):
                try:
                    setattr(pg, flag, False)
                    done = True
                except (AttributeError, TypeError):
                    pass
    return done


class MCH_OT_object_tidy(bpy.types.Operator):
    """Reset Axis / Origin to Geometry / Origin to 3D Cursor for the selected objects"""
    bl_idname = 'mch.object_tidy'
    bl_label = 'Object Tidy'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=[(a, l, d) for a, _i, l, d in TIDY], default='RESET_AXIS')

    @classmethod
    def description(cls, context, properties):
        return next(d for a, _i, _l, d in TIDY if a == properties.action)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_editable_objects)

    def execute(self, context):
        if self.action in {'SYMMETRY', 'MIRROR'}:
            # Symmetry: live while you lean, Enter applies; Mirror (0.23.2): the result stays a live Mirror.
            # 0.24.14 one entry with Alt+X: collection instances too, a plain message for anything else
            from . import mirror_tools
            return mirror_tools.start_mirror(context, self.action == 'MIRROR', self.report)
        obs = [o for o in context.selected_editable_objects if o.type in {'MESH', 'CURVE'}]
        if not obs:
            return {'CANCELLED'}
        frozen = [o.name for o in obs if _unlive(o)]
        with context.temp_override(selected_editable_objects=obs, selected_objects=obs,
                                   active_object=context.active_object or obs[0]):
            if self.action == 'RESET_AXIS':
                bpy.ops.object.transform_apply(location=False, rotation=True, scale=False)
            elif self.action == 'ORIGIN_GEOMETRY':
                bpy.ops.object.origin_set(type='ORIGIN_GEOMETRY', center='MEDIAN')
            else:
                bpy.ops.object.origin_set(type='ORIGIN_CURSOR')
        label = next(l for a, _i, l, _d in TIDY if a == self.action)
        extra = f' (live shape frozen: {", ".join(frozen)})' if frozen else ''
        self.report({'INFO'}, f'{label}: {len(obs)} object(s){extra}')
        return {'FINISHED'}


def apply_all_modifiers(context, ob):
    """0.24.21 apply every enabled modifier of ``ob`` in stack order (top to bottom).  Returns (applied names,
    error or '').  Stops at the first one that fails (the ones before it stay applied)."""
    from . import safe_apply
    if ob is None or ob.type != 'MESH':
        return [], 'click a mesh'
    if not ob.modifiers:
        return [], ''
    _unlive(ob)                                   # a live Mecha shape would rebuild over the result
    done = []
    for mod in list(ob.modifiers):
        if not mod.show_viewport:
            continue                              # switched off in the viewport: left as it is
        name = mod.name
        try:
            safe_apply(context, ob, mod)
        except RuntimeError as ex:
            return done, f'{name}: {str(ex).splitlines()[0][:90]}'
        done.append(name)
    return done, ''


class MCH_OT_apply_modifiers_pick(bpy.types.Operator):
    """Apply the modifiers of the selected meshes, top to bottom; nothing selected: click a mesh (Esc / right-click:
    done)"""
    bl_idname = 'mch.apply_modifiers_pick'
    bl_label = 'Apply Modifiers (click a mesh)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def _apply(self, context, ob):
        done, err = apply_all_modifiers(context, ob)
        if err and not done:
            self.report({'WARNING'}, f'{ob.name if ob else "Nothing"}: {err}')
        elif err:
            self.report({'WARNING'}, f'{ob.name}: applied {", ".join(done)} - stopped at {err}')
        elif not done:
            self.report({'INFO'}, f'{ob.name}: no modifiers to apply')
        else:
            self.report({'INFO'}, f'{ob.name}: applied {len(done)} modifier(s) in order - {", ".join(done)}')
        return bool(done)

    def execute(self, context):
        # no click (e.g. from a script): the selected meshes
        obs = [o for o in context.selected_editable_objects if o.type == 'MESH']
        if not obs:
            self.report({'WARNING'}, 'Select a mesh (or use the button and click one)')
            return {'CANCELLED'}
        any_done = False
        for ob in obs:
            any_done |= self._apply(context, ob)
        return {'FINISHED'} if any_done else {'CANCELLED'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return self.execute(context)
        if any(o.type == 'MESH' for o in context.selected_editable_objects):
            return self.execute(context)         # 0.24.59 already picked: apply now, no second pick
        context.window_manager.modal_handler_add(self)
        context.workspace.status_text_set('Apply Modifiers: click a mesh (its modifiers are applied top to bottom) '
                                          '| Esc / Right-click: done')
        context.window.cursor_modal_set('EYEDROPPER')
        return {'RUNNING_MODAL'}

    def _finish(self, context):
        try:
            context.workspace.status_text_set(None)
            context.window.cursor_modal_restore()
        except (AttributeError, RuntimeError):
            pass

    def modal(self, context, event):
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._finish(context)
            return {'FINISHED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            from . import workspace_ui
            ob = workspace_ui.object_under_mouse(context, event)
            if ob is None:
                self.report({'INFO'}, 'Apply Modifiers: click on a mesh (Esc: done)')
                return {'RUNNING_MODAL'}
            for o in context.selected_objects:
                o.select_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            self._apply(context, ob)
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}             # orbit / zoom / pan still work


TOP_TIDY = ('APPLY_MODS', 'MODIFIER', 'Apply Modifiers', 'Click a mesh: its modifiers are applied in order')


def top_tidy_position(context):
    """0.24.21 the Apply Modifiers button above the tool button."""
    x, y = active_button_pos(context)
    return x, y + 62.0 * _btn_factor()


def tidy_positions(context):
    x, y = active_button_pos(context)
    f = _btn_factor()
    return [(x, y - (62.0 + i * 48.0) * f) for i in range(len(TIDY))]


class MCH_GGT_object_tidy(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_object_tidy'
    bl_label = 'Mecha Object Tidy'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):                      # 0.24.59 the drawn actions card has them (Drawn Toolbar on)
        return ui_active(context) and not _pref('drawn_toolbar', True)

    def setup(self, context):
        self.items = []
        gz = self.gizmos.new('GIZMO_GT_button_2d')        # 0.24.21 Apply Modifiers (click a mesh), on top
        gz.icon = TOP_TIDY[1]
        gz.draw_options = {'BACKDROP', 'OUTLINE'}
        gz.target_set_operator('mch.apply_modifiers_pick')
        gz.color = BASE_COL
        gz.alpha = 0.92
        gz.color_highlight = (0.32, 0.35, 0.41)
        gz.alpha_highlight = 1.0
        self.top = gz
        for action, icon, _l, _d in TIDY:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            gz.target_set_operator('mch.object_tidy').action = action
            gz.color = BASE_COL
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items.append(gz)

    def draw_prepare(self, context):
        ui = context.preferences.system.ui_scale
        x, y = top_tidy_position(context)
        self.top.scale_basis = 19.0 * _btn_factor()
        self.top.matrix_basis[0][3] = x * ui
        self.top.matrix_basis[1][3] = y * ui
        for gz, (x, y) in zip(self.items, tidy_positions(context)):
            gz.scale_basis = 19.0 * _btn_factor()
            gz.matrix_basis[0][3] = x * ui
            gz.matrix_basis[1][3] = y * ui


def _draw_tidy_labels(context):
    import blf
    ui = context.preferences.system.ui_scale
    f = _btn_factor()
    blf.size(0, 12.5 * ui * f)
    blf.color(0, 0.88, 0.9, 0.93, 1.0)
    for (_a, _i, label, _d), (x, y) in zip(TIDY, tidy_positions(context)):
        blf.position(0, (x + 27 * f) * ui, (y - 5 * f) * ui, 0)
        blf.draw(0, label)
    x, y = top_tidy_position(context)
    blf.position(0, (x + 27 * f) * ui, (y - 5 * f) * ui, 0)
    blf.draw(0, TOP_TIDY[2] + '  (click a mesh)')


def _draw_active_label(context):
    import blf
    tid, t = chosen_tool(context)
    if t is None:
        return
    ui = context.preferences.system.ui_scale
    x, y = active_button_pos(context)
    on = tool_live(context)
    f = _btn_factor()
    blf.size(0, 14 * ui * f)
    blf.color(0, *(ACCENT if on else (0.9, 0.92, 0.95)), 1.0)
    blf.position(0, (x + 32 * f) * ui, (y - 5 * f) * ui, 0)
    blf.draw(0, f'{t[1]}  ON' if on else f'{t[1]}  -  click to activate')


def _draw_labels():
    """Optional names under the toolbar icons (Preferences: Toolbar Labels)."""
    try:
        context = bpy.context
        if not ui_active(context):
            return
        if not _pref('drawn_toolbar', True):     # 0.24.59 the drawn actions card has its own names
            if chosen_tool(context)[1] is not None:
                _draw_active_label(context)
            _draw_tidy_labels(context)
        if not _pref('toolbar_labels', True):
            return
        import blf
        if not _pref('bottom_toolbar') or _pref('drawn_toolbar', True):     # 0.24.58 the drawn bar has bubbles
            return
        region = context.region
        ui = context.preferences.system.ui_scale
        f = _pref('toolbar_scale', 1.0)
        pos, d = toolbar_layout(region.width / max(ui, 1e-3), 1.0, len(BAR_TOOLS), _pref('toolbar_size', 'M'),
                                factor=f)
        active = current_bar_tool(context)
        font = 0
        blf.size(font, 10 * ui * max(0.6, f))
        for (tid, label, *_), (x, y) in zip(BAR_TOOLS, pos):
            w, _h = blf.dimensions(font, label)
            on = tid == active
            blf.color(font, *(ACCENT if on else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, x * ui - w / 2, (y - d / 2 - 12 * max(0.6, f)) * ui, 0)
            blf.draw(font, label)
    except Exception:            # never break viewport drawing
        pass


CLASSES = (MCH_OT_bar_tool, MCH_MT_tool_pie, MCH_OT_tool_pie, MCH_OT_toggle_last_tool, MCH_OT_toggle_targets, MCH_GGT_bottom_toolbar,
           MCH_OT_tool_active, MCH_GGT_tool_active, MCH_OT_object_tidy, MCH_OT_apply_modifiers_pick, MCH_GGT_object_tidy)
# 0.19.1: the 0.15 floating side tool list was removed (user request)


def register():
    global _label_handle
    bpy.types.WindowManager.mch_last_model = StringProperty(default='CUT', options={'SKIP_SAVE'})
    bpy.types.WindowManager.mch_ui_mode = EnumProperty(items=[('TOOL', 'Tool', ''), ('SELECT', 'Select', '')],
                                                       default='TOOL', options={'SKIP_SAVE'})
    for c in CLASSES:
        bpy.utils.register_class(c)
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
    for n in ('mch_ui_mode', 'mch_last_model'):
        if hasattr(bpy.types.WindowManager, n):
            delattr(bpy.types.WindowManager, n)
