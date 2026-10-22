"""0.11.3: built-in stamp shapes, hotkeys, Ctrl+Z keeps the tool UI, Cable to mesh,
lean mirror (HardOps style), hotkey editor without cached keymap items."""
import math
import sys
import types

from _harness import bpy, check, cube, fresh, non_manifold, select_only, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import (cable, core_geometry as cg, cut_engine as ce, cut_presets, mirror_tools as mt,
                       tool_state as ts, workspace_ui as wui)

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion())

# --- built-in stamp shapes ---------------------------------------------------
names = [b[0] for b in cut_presets.builtin_shapes()]
check('six built-in shapes shipped', names == ['MCH_BUILTIN_' + n for n in (
    'PENTAGON', 'TRAPEZOID', 'PILLS3', 'TRIANGLE', 'NOTCH_ROUND', 'NOTCH_POLY')], names)
items = [i[0] for i in cut_presets.preset_items(None, C)]
check('built-in shapes first in the PNG / stamp list', items[:6] == names, items)
check('each built-in shape has a palette icon', all(cut_presets.preset_icon(n) or bpy.app.background for n in names))
check('built-in shapes cannot be deleted', cut_presets.is_builtin(names[0]))
for stem in names:
    loops = cut_presets.load_loops(stem)
    xs = [p[0] for lp in loops for p in lp]
    ys = [p[1] for lp in loops for p in lp]
    ok_span = max(max(xs) - min(xs), max(ys) - min(ys)) == 1.0 or abs(max(max(xs) - min(xs), max(ys) - min(ys)) - 1) < 1e-3
    fresh_t = cube('T')
    select_only(fresh_t)
    try:
        r = ce.perform_closed(C, 'CUT', [fresh_t], ce.custom_loops(loops, (500, 500), 60, 0.0), TOP)
    except cg.CutError as ex:
        r = f'ERROR {ex}'
    check(f'stamp {stem[12:]}: normalized, cuts a closed hole', ok_span and r.startswith('Cut') and
          volume(fresh_t) < 8 - 1e-3 and non_manifold(fresh_t) == 0, r)
    bpy.data.objects.remove(fresh_t)
pills = cut_presets.load_loops('MCH_BUILTIN_PILLS3')
check('Three Pills = three separate slanted pills', len(pills) == 3)
r = bpy.ops.mch.pick_stamp_shape(stem='MCH_BUILTIN_TRIANGLE')
check('picking a shape selects the stamp tool shape', r == {'FINISHED'} and C.scene.mch_brush.shape == 'CUSTOM' and
      C.scene.mch_png_preset == 'MCH_BUILTIN_TRIANGLE')

# --- hotkeys -----------------------------------------------------------------
kc = C.window_manager.keyconfigs.addon
keys = [(ki.idname, ki.type) for km in kc.keymaps for ki in km.keymap_items]
check('keys: Q toggle + V pie, F = Select / Move, N free', ('mch.tool_pie', 'V') in keys and
      ('mch.toggle_last_tool', 'Q') in keys and
      ('mch.select_move_key', 'F') in keys and not any(k[1] in {'N', 'W'} for k in keys), keys)
tool_km = wui._tool_keymap('CUT')
check('0.12: T toggles targets while a Mecha drawing tool is active', any(
    k[0] == 'mch.toggle_targets' and k[1]['type'] == 'T' for k in tool_km))
found = wui.hotkey_items(C)
check('hotkey editor looks items up fresh (no cached KeyMapItem list)',
      {i.idname for _km, i in found} >= {'mch.select_move_key', 'mch.tool_pie'} and
      'for km, item in _keymaps' not in open(wui.__file__).read().split('def draw_hotkey_editor')[1].split('def ')[0])

# --- Ctrl+Z keeps the tool UI ------------------------------------------------
s = C.scene
s.mch_brush.shape = 'CURVE_LASSO'
s.mch_settings.mch_active_tool = 'SPLIT'
ts.snapshot_ui_state(s)
s.mch_brush.shape = 'RECT'                  # what undo restored (the older shape)
s.mch_settings.mch_active_tool = 'CUT'
changed = ts.restore_ui_state(s)
check('after undo the current shape and tool come back', s.mch_brush.shape == 'CURVE_LASSO' and
      s.mch_settings.mch_active_tool == 'SPLIT' and 'shape' in changed, changed)
check('undo / redo handlers registered', ts._on_undo_post in bpy.app.handlers.undo_post and
      ts._on_undo_pre in bpy.app.handlers.redo_pre)

# --- Cable to mesh -----------------------------------------------------------
fresh()
mecha_lab.register()
C = bpy.context
ob = cable.create_cable(C, Vector((0, 0, 0)), Vector((0, 0, 1)), Vector((3, 0, 0)), Vector((0, 0, 1)))
C.view_layer.update()
select_only(ob)
C.view_layer.objects.active = ob
name = ob.name
r = bpy.ops.mch.cable_to_mesh()
new = bpy.data.objects.get(name)
check('Convert Cable to Object: a mesh object with the same name replaces the curve',
      r == {'FINISHED'} and new is not None and new.type == 'MESH' and len(new.data.polygons) > 20 and
      not any(o.type == 'CURVE' and o.name.startswith('MCH_Cable') for o in bpy.data.objects), r)
check('...and it is selected / active', C.view_layer.objects.active == new)

from mecha_lab import bottom_bar as bb_mod
# --- lean mirror -------------------------------------------------------------
class Region:
    type = 'WINDOW'
    x = y = 0
    width = height = 1000


def E(t, v='PRESS', x=500, y=500, shift=False):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y, shift=shift, alt=False, ctrl=False)


class Op(mt.MirrorLeanLogic):
    pass


def xs(ob):
    dg = C.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    v = [ob.matrix_world @ p.co for p in me.vertices]
    ob.evaluated_get(dg).to_mesh_clear()
    return min(p.x for p in v), max(p.x for p in v), min(p.y for p in v), max(p.y for p in v)


def setup_mirror_scene():
    fresh()
    mecha_lab.register()
    t = cube('M', 1.0, (0.3, 0.0, 0.0))          # spans x -0.2 .. 0.8
    select_only(t)
    C.view_layer.objects.active = t
    C.scene.mch_mirror.space = 'WORLD'
    return t


t = setup_mirror_scene()
op = Op()
check('lean mirror starts with a live mirror at once', op.start(C, Region(), TOP, (500, 500)) and
      t.modifiers.get(mt.MOD_NAME) is not None)
pick = mt.lean_pick(TOP, Vector((0, 0, 0)), [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))], (700, 510))
check('mouse to the right on a top view = +X', pick == (0, 1), pick)
pick = mt.lean_pick(TOP, Vector((0, 0, 0)), [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))], (505, 300))
check('mouse below = -Y', pick == (1, -1), pick)
check('dead zone near the centre', mt.lean_pick(TOP, Vector(), [Vector((1, 0, 0))], (505, 505)) is None)
op.handle(C, E('MOUSEMOVE', 'NOTHING', 300, 180))     # lean to -X (from the bottom-centre gesture)
lo, hi, _a, _b = xs(t)
check('lean -X: the +X half is copied to -X (bisect)', abs(lo + 0.8) < 1e-4 and abs(hi - 0.8) < 1e-4, (lo, hi))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 800, 180))     # lean to +X: copy the - side to +X
lo, hi, _a, _b = xs(t)
check('lean +X: the -X half is copied to +X', abs(lo + 0.2) < 1e-4 and abs(hi - 0.2) < 1e-4, (lo, hi))
op.handle(C, E('LEFTMOUSE', 'PRESS', 800, 180, shift=True))   # add X, keep going
op.handle(C, E('MOUSEMOVE', 'NOTHING', 500, 480))     # lean to +Y as well
mod = t.modifiers[mt.MOD_NAME]
check('Shift+click keeps X and adds the next axis (Y)', tuple(mod.use_axis) == (True, True, False), tuple(mod.use_axis))
r = op.handle(C, E('RET', 'PRESS', 500, 800))
check('Enter = apply', r == 'APPLY')
msg = op.finish_apply(C)
check('apply bakes the mirror (no modifier left, geometry mirrored)', mt.MOD_NAME not in t.modifiers and
      'Mirror applied' in msg and non_manifold(t) == 0, msg)
check('pivot helper removed after apply', not any(o.get('_mch_world_pivot') for o in bpy.data.objects))

t = setup_mirror_scene()
op = Op()
op.start(C, Region(), TOP, (500, 500))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 300, 180))
r = op.handle(C, E('ESC', 'PRESS'))
op.restore_all()
check('Esc cancels: no mirror left, mesh untouched', r == 'CANCEL' and mt.MOD_NAME not in t.modifiers and
      len(t.data.vertices) == 8 and not any(o.get('_mch_world_pivot') for o in bpy.data.objects))

t = setup_mirror_scene()
mt.setup_mirror(t, C.scene.mch_mirror, C.scene, (False, True, False), (False, False, False))
op = Op()
op.start(C, Region(), TOP, (500, 500))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 300, 180))
op.restore_all()
mod = t.modifiers.get(mt.MOD_NAME)
check('Esc restores a mirror that existed before', mod is not None and tuple(mod.use_axis) == (False, True, False))

t = setup_mirror_scene()
op = Op()
op.start(C, Region(), TOP, (500, 500))
op.handle(C, E('MOUSEMOVE', 'NOTHING', 300, 180))
r = op.handle(C, E('RET', 'PRESS', 300, 180))      # 0.24.19 a click now applies (LMB right / RMB left)
op.finish_live(C.scene)
check('keep the live mirror; settings remembered', r == 'APPLY' and mt.MOD_NAME in t.modifiers and
      C.scene.mch_mirror.x and not C.scene.mch_mirror.flip_x)
check('navigation passes through', op.handle(C, E('MIDDLEMOUSE', 'PRESS')) == 'PASS' and
      op.handle(C, E('WHEELUPMOUSE', 'PRESS')) == 'PASS')
check('0.23.2: lean gesture at the bottom centre of the view', tuple(op.center) == (500.0, 180.0))
far = mt.lean_pick(TOP, Vector((0, 0, -50)), [Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1))], (700, 180),
                   center=(500, 180))
check('gesture works when the origin is off screen (picks +X from the bottom centre)', far == (0, 1), far)
check('Mirror button uses the lean gesture, kept live', "start_mirror(context, self.action == 'MIRROR'" in open(bb_mod.__file__).read())
check('mirror tool start hook present', 'start_lean_mirror' in open(wui.__file__).read())
check('Mirror lean operator registered', hasattr(bpy.types, 'MCH_OT_mirror_lean'))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
