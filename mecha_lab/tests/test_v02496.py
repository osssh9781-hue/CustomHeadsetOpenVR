"""0.24.65 Ctrl+Z undoes what you did, never the settings you chose (real undo / redo here), and the ZBrush items left
over: the red draw circle, Accu, the pen pressure curve, each brush remembering its alpha, cleaning the old brush
copies, and DynaMesh turning the masked part into its own polygroup."""
import inspect
import json
import os
import types

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import quick_hud as qh, ui_bars as ub, undo_keep as uk, zb_sculpt as zs, zb_ui as zu
from mecha_lab.mecha_menu import Item

mecha_lab.register()
fresh()
C = bpy.context
real_on = zs.on
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'          # (the test has no MECHA LAB tab)
zb = C.scene.mch_zb

# --- Ctrl+Z: the action goes back, the settings stay ------------------------------------------------------------------
zb.points = 1234
C.scene.mch_brush.line_width = 0.01
bpy.ops.ed.undo_push(message='before')
bpy.ops.mesh.primitive_cube_add()
zb.points = 5555
C.scene.mch_brush.line_width = 0.03
bpy.ops.ed.undo_push(message='cube')
bpy.ops.ed.undo()
zb = C.scene.mch_zb                                  # (undo makes the scene anew: look everything up again)
check('Ctrl+Z: the new part is gone, the settings changed after the last step stay (ZBrush and Mecha tools)',
      len(bpy.data.objects) == 0 and zb.points == 5555 and abs(C.scene.mch_brush.line_width - 0.03) < 1e-6,
      (len(bpy.data.objects), zb.points, C.scene.mch_brush.line_width))
bpy.ops.ed.redo()
zb = C.scene.mch_zb
check('Ctrl+Shift+Z: the part is back, the settings still yours', len(bpy.data.objects) == 1 and zb.points == 5555)


def unified():
    sc = C.scene.tool_settings.sculpt
    return getattr(sc, 'unified_paint_settings', None) or C.scene.tool_settings.unified_paint_settings


u = unified()
u.size = 40
bpy.ops.ed.undo_push(message='size 40')
bpy.ops.mesh.primitive_uv_sphere_add()
u.size = 90
C.scene.tool_settings.sculpt.use_symmetry_x = not C.scene.tool_settings.sculpt.use_symmetry_x
sym = C.scene.tool_settings.sculpt.use_symmetry_x
bpy.ops.ed.undo_push(message='sphere')
bpy.ops.ed.undo()
u = unified()
check('... sculpt settings too (Draw Size / brush size, symmetry)', u.size == 90
      and C.scene.tool_settings.sculpt.use_symmetry_x == sym, (u.size,))
base = C.scene.mch_base
live_was = base.live
base.live = True                                     # (a live part is being edited: its values follow the undo)
key = next(k for k in uk._keys(base))
bpy.ops.ed.undo_push(message='live')
old = getattr(base, key)
rna = base.bl_rna.properties[key]
new = (not old) if rna.type == 'BOOLEAN' else (old + 1 if rna.type in {'INT', 'FLOAT'} else old)
if rna.type != 'ENUM':
    setattr(base, key, new)
    bpy.ops.ed.undo_push(message='live change')
    bpy.ops.ed.undo()
    base = C.scene.mch_base
    check('A tool editing a live part right now: its values do follow Ctrl+Z (they belong to that part)',
          getattr(base, key) == old, (key, getattr(base, key), old))
base = C.scene.mch_base
base.live = False
zb = C.scene.mch_zb
check('Settings are no undo step of their own: scene tool settings / brush / view = settings, a live part = model',
      uk.is_setting(zb) and uk.is_setting(C.scene.mch_brush) and uk.is_setting(u)
      and not uk.is_setting(C.active_object) and not uk.is_setting(None))
base.live = True
check('... a tool group editing a live part is not a setting', not uk.is_setting(base))
base.live = live_was
check('The drawn UI skips the undo step for a setting, Blender-like undo for operators',
      'undo_keep.is_setting(data)' in inspect.getsource(ub._undo)
      and "('INVOKE_DEFAULT', True, **a[2])" in inspect.getsource(ub.run)
      and inspect.getsource(qh).count('undo_keep.is_setting(') >= 2)
check('ZBrush shelf: a change to the model is an undo step, a setting / view / tool switch is not',
      'UNDO' not in zs.MCH_OT_zb_action.bl_options and 'SYM_X' in zs.SETTING_ACTIONS
      and 'POLYF' in zs.SETTING_ACTIONS and 'DYNAMESH' not in zs.SETTING_ACTIONS
      and 'undo_step(' in inspect.getsource(zs.MCH_OT_zb_action.execute)
      and all('UNDO' not in c.bl_options for c in (zs.MCH_OT_zb_alpha, zs.MCH_OT_zb_alpha_edit, zs.MCH_OT_zb_set)))

# --- the ZBrush screen ------------------------------------------------------------------------------------------------
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=32, ring_count=16)
ob = C.active_object
bpy.ops.object.mode_set(mode='SCULPT')
zs.activate(C, 'Standard')
b = zs.brush(C)
check('ZBrush red draw circle (Zadd and Zsub)', all(abs(a - e) < 1e-3 for a, e in zip(b.cursor_color_add, zs.ZB_RED))
      and all(abs(a - e) < 1e-3 for a, e in zip(b.cursor_color_subtract, zs.ZB_RED)))
b.cursor_color_add = (0.0, 1.0, 0.0, 1.0)
zs.activate(C, 'ClayBuildup')
zs.activate(C, 'Standard')
check('... a colour you set later is kept', abs(zs.brush(C).cursor_color_add[1] - 1.0) < 1e-3)
check('Accu off at first (ZBrush): a stroke does not pile up on itself', not b.use_accumulate and not zb.accu)
zb.accu = True
check('Accu on = Blender Accumulate', b.use_accumulate and zb.accu)
zb.accu = False
cm = b.curve_strength
check('Pen pressure: ZBrush curve at first (a light touch gives a little less)',
      zb.pressure == 'ZBRUSH' and abs(cm.evaluate(cm.curves[0], 0.5) - 0.5 ** 1.3) < 0.03,
      cm.evaluate(cm.curves[0], 0.5))
zb.pressure = 'FIRM'
check('... Firm: strong at a light touch', abs(cm.evaluate(cm.curves[0], 0.5) - 0.5 ** 0.6) < 0.03)
zb.pressure = 'LINEAR'
check('... Linear = Blender', abs(cm.evaluate(cm.curves[0], 0.5) - 0.5) < 0.03)
zb.pressure = 'ZBRUSH'
check('Accu / Pressure are on the left shelf (Stroke)', "zb, 'accu'" in inspect.getsource(zu.draw_tool_shelf)
      and "zb, 'pressure'" in inspect.getsource(zu.draw_tool_shelf))

# --- each brush remembers its alpha -----------------------------------------------------------------------------------
files, _n = zs.alpha_files(C)
zs.set_alpha(C, files[3])
zs.alpha_edit(C, 'FLIP_H')
zs.alpha_edit(C, 'ROTATE')
amap = json.loads(zb.alpha_map)
check('The alpha is remembered for the brush (with Flh / Rot)', 'Standard' in amap
      and os.path.normcase(amap['Standard']['path']) == os.path.normcase(files[3])
      and amap['Standard']['scale'][0] < 0 and abs(amap['Standard']['angle'] - 1.5708) < 1e-3)
b.texture = None                                     # (what Blender does after the file is opened again)
zs.activate(C, 'ClayBuildup')
zs.activate(C, 'Standard')
b = zs.brush(C)
check('... picking the brush again brings it back, flips and turn too', b.texture is not None
      and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(files[3]) and b.texture_slot.scale[0] < 0
      and abs(b.texture_slot.angle - 1.5708) < 1e-3)
b.texture = None
check('... and before a stroke (after a reopen / undo)', zs.restore_alpha(C) and b.texture is not None
      and 'restore_alpha(context)' in inspect.getsource(zs.MCH_OT_zb_press.invoke))
check('... and after a file is opened (a moment later)', zs._on_load in bpy.app.handlers.load_post)
zs.set_alpha(C, '')
check('Alpha Off forgets it', 'Standard' not in json.loads(zb.alpha_map) and not zs.restore_alpha(C))

# --- the old brush copies (0.24.60 - 0.24.62) ---------------------------------------------------------------------------
cp = b.copy()
cp.name = 'Draw' + zs.ZB_SUFFIX
cp.asset_mark()
img = bpy.data.images.new('old alpha', 4, 4)
tex = bpy.data.textures.new('Alpha old', 'IMAGE')
tex.image = img
cp.texture = tex


class Ctx:
    region = types.SimpleNamespace(width=2560, height=1440, x=0, y=0, type='WINDOW')
    area = None

    def __getattr__(self, n):
        return getattr(bpy.context, n)


C.window_manager.mch_zb_pop, C.window_manager.mch_zb_pop_xy = 'ALPHA', (900, 700)
pop = zu.popup(Ctx(), 2560, 1440, 1.0, Item)
clean = next((i for i in pop if i.kind == 'seg' and i.label.startswith('Clean')), None)
check('Old brush copies in the file: the alpha picker offers to clean them', zs.old_copies() == [cp]
      and clean is not None and clean.label == 'Clean 1 old')
msg = zs.run(C, 'CLEAN_COPIES')
check('... Clean removes them and the alpha textures / images only they used', not zs.old_copies()
      and bpy.data.textures.get(('Alpha old', None)) is None and bpy.data.images.get(('old alpha', None)) is None
      and 'Removed 1' in msg, msg)
C.window_manager.mch_zb_pop = ''

# --- DynaMesh: the masked part gets its own polygroup -----------------------------------------------------------------
ob = C.active_object
me = ob.data
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
att = me.attributes.get('.sculpt_mask') or me.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
me.attributes['.sculpt_mask'].data.foreach_set('value', (co[:, 2] > 0.3).astype(np.float32))
zb.points = 3000
keep_pa = C.active_object.data.use_remesh_preserve_attributes
msg = zs.run(C, 'DYNAMESH')
me = C.active_object.data
fs = me.attributes.get(zs.FACE_SETS)
vals = np.empty(len(me.polygons), dtype=np.int32)
if fs is not None:
    fs.data.foreach_get('value', vals)
check('DynaMesh with a mask: remeshed, the masked part is its own polygroup, the mask is cleared (ZBrush)',
      fs is not None and len(set(vals.tolist())) >= 2 and not zs.has_mask(C.active_object) and 'DynaMesh' in msg,
      (msg, set(vals.tolist())))
check('... the mesh keeps your Preserve Attributes setting as it was', me.use_remesh_preserve_attributes == keep_pa)
zs.run(C, 'DYNAMESH')                                # (turns DynaMesh off again)
# --- a pen's side button in MECHA LAB (it worked on the ZBrush screen only) ---------------------------------------------
from mecha_lab import cut_engine as ce, mecha_menu as mm
r = zs.RMBDrag()
ev = types.SimpleNamespace(mouse_x=100, mouse_y=100, alt=False, is_tablet=True, type='MOUSEMOVE', value='NOTHING')
r.rmb_drag_start(types.SimpleNamespace(mode='OBJECT', workspace=None), ev)
r.rmb_live = True
moved = types.SimpleNamespace(mouse_x=110, mouse_y=102, alt=False, is_tablet=True, type='MOUSEMOVE', value='NOTHING')
check('Pen side button: a small wobble while pressed is still a click (menu), not a turn of the view',
      not r.rmb_drag_check(C, moved) and zs.RMBDrag.PEN_SLOP > zs.RMBDrag.MOUSE_SLOP)
src = inspect.getsource(ce.GateLogic.modal)
check('Drawing tools: a pen repeating the press does not count as the double right-click that leaves the tool',
      "getattr(self, 'rmb_up', True)" in src and "event.value == 'RELEASE'" in src)
op = types.SimpleNamespace(t_open=__import__('time').monotonic())
check('Mecha Menu: the pen repeating its opening press does not close it at once', mm._pen_echo(
    op, types.SimpleNamespace(is_tablet=True)) and not mm._pen_echo(op, types.SimpleNamespace(is_tablet=False)))
zs.on = real_on
mecha_lab.unregister()
summary()
