"""0.12 Blender MVP of the UX prototype: Auto Target / Selected Only, Q pie,
Shift+Q, bottom toolbar (2D button gizmos), V/N freed, T toggle.

Not a GUI test: the toolbar gizmos, the pie popup and tooltips need a real window."""
import sys
import types

from _harness import bpy, check, cube, fresh, select_only, summary, volume
from mathutils import Quaternion

import mecha_lab
from mecha_lab import bottom_bar as bb, core_geometry as cg, cut_engine as ce, tool_state as ts, workspace_ui as wui

TOP = cg.OrthoProjector(Quaternion())
CLOCK = [1000.0]
ce.make_projector = lambda region, rv3d: TOP
ce.add_draw_handler = lambda op: 'handle'
ce.remove_draw_handler = lambda h: None
ce._now = lambda: CLOCK[0]


class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000

    def tag_redraw(self):
        pass


class WM:
    def modal_handler_add(self, op):
        pass

    def event_timer_add(self, step, window=None):
        return object()

    def event_timer_remove(self, t):
        pass


class Ctx:
    def __init__(self, native='mecha.cut'):
        self.region = Region()
        self.area = types.SimpleNamespace(type='VIEW_3D', regions=[self.region])
        self.region_data = object()
        self.space_data = types.SimpleNamespace(region_3d=self.region_data)
        self.window_manager = WM()
        self.window = None
        self.mode = 'OBJECT'
        self.preferences = bpy.context.preferences
        nat = native

        class Tools:
            def from_space_view3d_mode(self, mode, create=False):
                return types.SimpleNamespace(idname=nat)
        self.workspace = types.SimpleNamespace(tools=Tools(), status_text_set=lambda t: None)

    scene = property(lambda s: bpy.context.scene)
    view_layer = property(lambda s: bpy.context.view_layer)
    selected_objects = property(lambda s: bpy.context.selected_objects)
    collection = property(lambda s: bpy.context.scene.collection)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


def E(t, v='PRESS', x=500, y=500, alt=False, shift=False, ctrl=False):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y, alt=alt, shift=shift, ctrl=ctrl, oskey=False)


class Op(ce.StrokeLogic):
    def __init__(self, mode='CUT'):
        self.mode = mode
        self.reports = []

    def report(self, kind, msg):
        self.reports.append(msg)


def setup(targets='AUTO', shape='RECT'):
    fresh()
    s = bpy.context.scene
    s.mch_settings.auto_apply = True
    s.mch_settings.mch_active_tool = 'CUT'
    s.mch_brush.shape = shape
    s.mch_cut.targets = targets
    a = cube('A', 2.0, (-2.0, 0, 0))     # screen x 200..400 (100 px / unit, centre 500)
    b = cube('B', 2.0, (2.0, 0, 0))      # screen x 600..800
    select_only(a)
    bpy.context.view_layer.objects.active = a
    CLOCK[0] += 10
    return a, b


def rect(op, ctx, x0, y0, x1, y1, mode='CUT'):
    r0 = op.invoke(ctx, E('LEFTMOUSE', 'PRESS', x0, y0))
    op.modal(ctx, E('MOUSEMOVE', 'NOTHING', x1, y1))
    return r0, op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x1, y1))


fresh()
mecha_lab.register()
check('default target mode is Auto Target', bpy.context.scene.mch_cut.targets == 'AUTO')

# --- Auto Target ------------------------------------------------------------
a, b = setup('AUTO')
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 650, 450, 750, 550)          # over B while A is selected
check('Auto: the shape over B cuts B although A is selected', r == {'FINISHED'} and volume(b) < 8 - 1e-3 and
      abs(volume(a) - 8) < 1e-6, (r, op.reports))
check('Auto: what was cut becomes the selection', [o.name for o in bpy.context.selected_objects] == ['B'])
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 250, 450, 350, 550)          # next part, tool still on, no Select needed
check('Auto: next part right away (no Select in between)', r == {'FINISHED'} and volume(a) < 8 - 1e-3)
a, b = setup('AUTO')
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 150, 470, 850, 530)          # band over both
check('Auto: a band over two parts cuts both', r == {'FINISHED'} and volume(a) < 8 - 1e-3 and volume(b) < 8 - 1e-3,
      op.reports)
a, b = setup('AUTO')
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 420, 100, 580, 200)          # empty space
check('Auto: starts on empty space; a shape over nothing changes nothing', r0 == {'RUNNING_MODAL'} and
      r == {'CANCELLED'} and abs(volume(a) - 8) < 1e-6 and abs(volume(b) - 8) < 1e-6 and
      any('does not cover' in m for m in op.reports), op.reports)
a, b = setup('AUTO')
b.hide_select = True
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 650, 450, 750, 550)
check('Auto: unselectable (locked) meshes are never cut', abs(volume(b) - 8) < 1e-6)
a, b = setup('AUTO')
b.display_type = 'WIRE'                            # e.g. a Mecha cutter object
op, ctx = Op(), Ctx()
rect(op, ctx, 650, 450, 750, 550)
check('Auto: wire-display helper objects are ignored', abs(volume(b) - 8) < 1e-6)
a, b = setup('AUTO', 'LASSO')
op, ctx = Op(), Ctx()
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', 640, 460))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', 640, 460))
for x, y in ((760, 460), (760, 540), (640, 540)):
    CLOCK[0] += 1
    op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
r = op.modal(ctx, E('RET', 'PRESS'))
check('Auto: Lasso over B cuts B', r == {'FINISHED'} and volume(b) < 8 - 1e-3 and abs(volume(a) - 8) < 1e-6)
a, b = setup('AUTO')
bpy.context.scene.mch_settings.mch_active_tool = 'SPLIT'
op, ctx = Op('SPLIT'), Ctx('mecha.split')
r0, r = rect(op, ctx, 650, 450, 750, 550, 'SPLIT')
check('Auto: Split works the same way', r == {'FINISHED'} and 'B_Split' in bpy.data.objects, op.reports)

# --- Selected Only ----------------------------------------------------------
a, b = setup('SELECTED')
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 650, 450, 750, 550)
check('Selected Only: a shape over an unselected part changes nothing', abs(volume(b) - 8) < 1e-6 and
      abs(volume(a) - 8) < 1e-6, (r, op.reports))
op, ctx = Op(), Ctx()
r0, r = rect(op, ctx, 250, 450, 350, 550)
check('Selected Only: the selected part is cut', r == {'FINISHED'} and volume(a) < 8 - 1e-3)

# --- auto_targets directly (perspective view) --------------------------------
from mathutils import Vector


class Persp:
    def __init__(self):
        self.view_dir = Vector((0, 0, -1)); self.is_perspective = True; self.eye = Vector((0, 0, 12)); self.f = 600
    def ray(self, xy):
        return self.eye.copy(), Vector(((xy[0] - 500) / self.f, (xy[1] - 500) / self.f, -1)).normalized()
    def to_screen(self, co):
        v = Vector(co) - self.eye
        return None if v.z >= 0 else (500 + self.f * v.x / -v.z, 500 + self.f * v.y / -v.z)


a, b = setup('AUTO')
found = ce.auto_targets(bpy.context.view_layer, Persp(), [[(560, 480), (640, 480), (640, 520), (560, 520)]])
check('auto_targets in a perspective view finds the covered part only', [o.name for o in found] == ['B'],
      [o.name for o in found])

# --- keys / pie / toolbar -----------------------------------------------------
kc = bpy.context.window_manager.keyconfigs.addon
keys = [(ki.idname, ki.type, ki.shift) for km in kc.keymaps for ki in km.keymap_items]
check('0.22.1: Q = Select <-> last tool, Shift+Q = tool pie', ('mch.tool_pie', 'Q', True) in keys and
      ('mch.toggle_last_tool', 'Q', False) in keys, keys)
check('V and N are free again (no Mecha items)', not any(k[1] in {'V', 'N'} for k in keys))
check('F = Select / Move kept', ('mch.select_move_key', 'F', False) in keys)
tk = wui._tool_keymap('CUT')
check('Cut tool: T toggles targets, no V item', any(k[0] == 'mch.toggle_targets' and k[1]['type'] == 'T' for k in tk)
      and not any(k[1]['type'] == 'V' for k in tk))
check('pie menu, toolbar gizmo group and toggle operators registered',
      all(hasattr(bpy.types, n) for n in ('MCH_MT_tool_pie', 'MCH_OT_tool_pie', 'MCH_OT_toggle_last_tool',
                                          'MCH_OT_toggle_targets')) and 'bl_rna' in bb.MCH_GGT_bottom_toolbar.__dict__)
icons = set(bpy.types.UILayout.bl_rna.functions['prop'].parameters['icon'].enum_items.keys())
check('every toolbar icon is a real Blender icon', all(t[3] in icons for t in bb.BAR_TOOLS),
      [t[3] for t in bb.BAR_TOOLS if t[3] not in icons])
check('every toolbar tool exists', all(t[5] is None or t[5] in ts.TOOL_BY_ID for t in bb.BAR_TOOLS))
pos, d = bb.toolbar_layout(1600, 1.0, 8, 'M')
xs = [p[0] for p in pos]
check('toolbar is centred at the bottom with even spacing', abs((xs[0] + xs[-1]) / 2 - 800) < 1e-6 and
      len({round(xs[i + 1] - xs[i], 6) for i in range(7)}) == 1 and pos[0][1] == 26 + d / 2)
pos2, d2 = bb.toolbar_layout(1600, 2.0, 8, 'L')
check('toolbar size and UI scale change the button size', d2 == 2 * bb.SIZES['L'])
fake = types.SimpleNamespace(workspace=types.SimpleNamespace(get=lambda k, d=None: None, name='Layout'),
                             mode='OBJECT', area=types.SimpleNamespace(type='VIEW_3D'))
check('outside MECHA LAB: pie, Shift+Q and toolbar do nothing (Blender keys win)',
      not bb.MCH_OT_tool_pie.poll(fake) and not bb.MCH_OT_toggle_last_tool.poll(fake) and
      not bb.MCH_GGT_bottom_toolbar.poll(fake))
wm = bpy.context.window_manager
check('last tool / mode live on the WindowManager (not undone, not saved)',
      hasattr(wm, 'mch_last_model') and hasattr(wm, 'mch_ui_mode'))
real_native = ts.native_tool_id
ctxs = types.SimpleNamespace(window_manager=wm, scene=bpy.context.scene, workspace=None)
bb.note_tool(ctxs, 'SPLIT')
ts.native_tool_id = lambda c: 'mecha.split'
check('a picked modelling tool is remembered for Shift+Q', wm.mch_last_model == 'SPLIT' and not bb.in_select(ctxs))
bb.note_select(ctxs)
ts.native_tool_id = lambda c: 'builtin.move'
check('after Select / Move the toggle goes back to the remembered tool', bb.in_select(ctxs) and
      bb.current_bar_tool(ctxs) == 'SELECT')
ts.native_tool_id = real_native
mecha_lab.unregister()
check('unregister removes the WindowManager properties', not hasattr(bpy.types.WindowManager, 'mch_last_model'))
sys.exit(1 if summary() else 0)
