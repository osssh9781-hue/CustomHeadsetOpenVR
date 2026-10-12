"""Headless UI smoke test: every Mecha panel draw function is executed against a
validating fake layout.  It checks property names, enum values, operator ids,
operator properties and icon names, which is the class of error that produced
the v0.5.9 Smart Fuse panel traceback (icon 'MOD_NODES' missing in Blender 5).

It does NOT prove layout looks right or that clicks work in the GUI.
"""
import sys
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import tool_state as ts, workspace_ui as wui

ICONS = set(bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items.keys())
ERRORS = []


def err(msg):
    ERRORS.append(msg)


def _check_icon(kw):
    icon = kw.get('icon')
    if icon is not None and icon not in ICONS:
        err(f'bad icon {icon}')


def _rna_props(data):
    try:
        return data.bl_rna.properties
    except AttributeError:
        return None


class FakeOpProps:
    def __init__(self, idname):
        object.__setattr__(self, '_id', idname)
        mod, name = idname.split('.')
        try:
            rna = getattr(getattr(bpy.ops, mod), name).get_rna_type()
            object.__setattr__(self, '_props', rna.properties)
        except (AttributeError, KeyError):
            err(f'unknown operator {idname}')
            object.__setattr__(self, '_props', None)

    def __setattr__(self, key, value):
        props = self._props
        if props is None:
            return
        if key not in props:
            err(f'{self._id}: no property {key}')
            return
        p = props[key]
        if p.type == 'ENUM' and not p.is_enum_flag and p.enum_items and value not in p.enum_items.keys():
            err(f'{self._id}.{key}: invalid enum value {value}')


class FakeLayout:
    def __init__(self):
        self.scale_y = self.scale_x = 1.0
        self.enabled = self.active = True
        self.use_property_split = self.use_property_decorate = False
        self.alignment = 'EXPAND'
        self.operator_context = 'INVOKE_DEFAULT'

    def _child(self, *a, **k):
        return FakeLayout()

    row = column = box = split = grid_flow = column_flow = _child

    def label(self, text='', **kw):
        _check_icon(kw)

    def separator(self, **kw):
        pass

    separator_spacer = separator

    def prop(self, data, name, **kw):
        _check_icon(kw)
        props = _rna_props(data)
        if props is None or name not in props:
            err(f'prop {type(data).__name__}.{name} missing')

    def prop_enum(self, data, name, value, **kw):
        self.prop(data, name, **kw)

    def operator(self, idname, **kw):
        _check_icon(kw)
        return FakeOpProps(idname)

    def template_icon(self, icon_value=0, scale=1.0):
        pass

    def template_icon_view(self, data, name, **kw):
        self.prop(data, name)

    def popover(self, panel, **kw):
        if not hasattr(bpy.types, panel):
            err(f'popover {panel} missing')

    def menu(self, name, **kw):
        if not hasattr(bpy.types, name):
            err(f'menu {name} missing')


class FakeTools:
    def __init__(self, idname):
        self.idname = idname

    def from_space_view3d_mode(self, mode, create=False):
        return types.SimpleNamespace(idname=self.idname)


class FakeWorkspace:
    def __init__(self, name, native=''):
        self.name = name
        self.tools = FakeTools(native)
        self._props = {ts.WORKSPACE_TAG: True} if name == ts.WORKSPACE_NAME else {}

    def get(self, key, default=None):
        return self._props.get(key, default)


def fake_context(ws_name='MECHA LAB', native='', space='VIEW_3D', mode='OBJECT'):
    c = bpy.context
    return types.SimpleNamespace(
        scene=c.scene, view_layer=c.view_layer, mode=mode, workspace=FakeWorkspace(ws_name, native),
        screen=None, active_object=c.view_layer.objects.active, object=c.view_layer.objects.active,
        selected_objects=list(c.selected_objects), preferences=c.preferences,
        window_manager=c.window_manager, region=None,
        space_data=types.SimpleNamespace(type=space), area=None)


def run_draw(label, fn, ctx):
    before = len(ERRORS)
    try:
        fn(ctx)
        ok = len(ERRORS) == before
        check(f'draw {label}', ok, ERRORS[before:])
    except Exception as ex:
        import traceback
        traceback.print_exc()
        check(f'draw {label}', False, repr(ex))


fresh()
mecha_lab.register()
target = cube('Target')
other = cube('Other', loc=(1, 0, 0))
select_only(target)

main = wui.MCH_PT_main
for ws_name in ('MECHA LAB', 'Layout'):
    for t in ts.TOOLS:
        native = t[5] or ''
        bpy.context.scene.mch_settings.mch_active_tool = t[0]
        for shape in ('LASSO', 'CURVE_LASSO', 'CIRCLE', 'STROKE', 'CUSTOM') if t[0] in ts.SHAPE_TOOLS else ('LASSO',):
            bpy.context.scene.mch_brush.shape = shape
            ctx = fake_context(ws_name, native)
            self_ = types.SimpleNamespace(layout=FakeLayout())
            run_draw(f'main[{ws_name}] {t[0]} {shape}', lambda c: (main.draw(self_, c), main.draw_header(self_, c)), ctx)
    ctx = fake_context(ws_name)
    for panel in (mecha_lab.mirror_tools.MCH_PT_mirror, mecha_lab.radial_array.MCH_PT_radial,
                  mecha_lab.surface_conform.MCH_PT_surface_conform, wui.MCH_PT_workspace,
                  wui.MCH_PT_tool_popup, wui.MCH_PT_shape_popup):
        self_ = types.SimpleNamespace(layout=FakeLayout())
        run_draw(f'{panel.__name__}[{ws_name}]', lambda c, p=panel: p.draw(self_, c), ctx)

ctx = fake_context('MECHA LAB', space='PROPERTIES')
check('tool list poll in Properties/MECHA LAB', wui.MCH_PT_tool_list.poll(ctx))
check('tool list hidden in 3D sidebar', not wui.MCH_PT_tool_list.poll(fake_context('MECHA LAB', space='VIEW_3D')))
check('tool list hidden outside workspace', not wui.MCH_PT_tool_list.poll(fake_context('Layout', space='PROPERTIES')))
self_ = types.SimpleNamespace(layout=FakeLayout())
run_draw('MCH_PT_tool_list', lambda c: wui.MCH_PT_tool_list.draw(self_, c), ctx)
for tool in ('CUT', 'BOOLEAN'):
    bpy.context.scene.mch_settings.mch_active_tool = tool
    self_ = types.SimpleNamespace(layout=FakeLayout())
    run_draw(f'shape palette (tool {tool})', lambda c: wui.draw_shape_palette(self_, c), fake_context('MECHA LAB'))
self_ = types.SimpleNamespace(layout=FakeLayout())
wui.draw_shape_palette(self_, fake_context('Layout'))   # must silently do nothing

# Effective tool: native drawing tool wins
bpy.context.scene.mch_settings.mch_active_tool = 'BOOLEAN'
check('effective tool = native Cut', ts.effective_tool(fake_context('MECHA LAB', 'mecha.cut')) == 'CUT')
check('effective tool = selected when native is select', ts.effective_tool(fake_context('MECHA LAB', 'builtin.select_box')) == 'BOOLEAN')

# Gated hotkeys: poll false outside the workspace => Blender's own key runs
check('space menu poll false outside workspace', not wui.MCH_OT_space_tools.poll(fake_context('Layout')))
check('B/C hotkey poll false outside workspace', not wui.MCH_OT_hotkey.poll(fake_context('Layout')))
check('B/C hotkey poll true inside workspace', wui.MCH_OT_hotkey.poll(fake_context('MECHA LAB')))

# Smart Fuse live preview panel (the v0.5.9 crash path)
other.location = (0.8, 0.3, 0.2)
bpy.context.view_layer.update()
select_only(target, other)
r = bpy.ops.mch.smart_fuse()
check('smart fuse create for panel test', r == {'FINISHED'}, r)
bpy.context.scene.mch_settings.mch_active_tool = 'FUSE'
self_ = types.SimpleNamespace(layout=FakeLayout())
run_draw('main FUSE live preview', lambda c: main.draw(self_, c), fake_context('MECHA LAB'))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
