"""0.24.82 Hotkey conflict check: the Blender keys the Mecha hotkeys sit on top of (same key + modifiers in the same
keymap), listed by Preferences > Hotkeys > Check Conflicts (clipboard + console) and the self test."""
from types import SimpleNamespace

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import keymap_check as kc

mecha_lab.register()
fresh()
C = bpy.context


def item(type_, value='PRESS', key_modifier='NONE', **mods):
    d = dict(type=type_, value=value, key_modifier=key_modifier, ctrl=False, alt=False, shift=False, oskey=False)
    d.update(mods)
    return SimpleNamespace(**d)


check('same_key: key + modifiers + key_modifier, PRESS vs ANY', kc.same_key(item('D', shift=True), item('D', shift=True))
      and not kc.same_key(item('D', shift=True), item('D', alt=True))
      and kc.same_key(item('D', value='ANY'), item('D')) and not kc.same_key(item('D'), item('D', value='RELEASE'))
      and not kc.same_key(item('LEFTMOUSE', key_modifier='D'), item('LEFTMOUSE'))
      and kc.same_key(item('S', ctrl=-1), item('S', ctrl=True)) and not kc.same_key(item('NONE'), item('NONE')))
check('describe: Shift+D, D+LMB, double click', kc.describe(item('D', shift=True)) == 'Shift+D'
      and kc.describe(item('LEFTMOUSE', key_modifier='D')) == 'D+LMB'
      and kc.describe(item('LEFTMOUSE', value='DOUBLE_CLICK')) == 'LMB (double click)', 
      (kc.describe(item('D', shift=True)), kc.describe(item('LEFTMOUSE', key_modifier='D'))))
mecha = kc._mecha_items()
check('The Mecha keys are found in the add-on keyconfig (Shift+D duplicate among them)',
      any(i.idname == 'mch.duplicate' and i.shift for _k, i in mecha) and len(mecha) > 10, len(mecha))
wm = C.window_manager
# (headless bpy has empty default / user keyconfigs - Blender's keys only load with a window, so the real-window
# smoke test checks the live list; here a made keyconfig stands in for Blender's Object Mode keys)
made = wm.keyconfigs.new('mch_test_keys')
km = made.keymaps.new(name='Object Mode', space_type='EMPTY')
km.keymap_items.new('object.duplicate_move', 'D', 'PRESS', shift=True)
km.keymap_items.new('object.duplicate_move_linked', 'D', 'PRESS', alt=True)
km.keymap_items.new('object.hide_view_set', 'H', 'PRESS')
km.keymap_items.new('anim.keyframe_insert', 'I', 'PRESS')
km2 = made.keymaps.new(name='3D View', space_type='VIEW_3D')
km2.keymap_items.new('view3d.select', 'Q', 'PRESS')                 # Mecha Q (Select <-> last tool) sits on it
found = kc.conflicts(made)
names = {(k, i.idname, o.idname) for k, i, o in found}
check('Against a keyconfig with Blender\'s keys: Shift+D sits on duplicate_move, Alt+D on the linked one, Q on '
      'view3d.select; H / I (no Mecha key there) are not listed',
      ('Object Mode', 'mch.duplicate', 'object.duplicate_move') in names
      and ('Object Mode', 'mch.duplicate', 'object.duplicate_move_linked') in names
      and ('3D View', 'mch.toggle_last_tool', 'view3d.select') in names
      and not any(o in {'object.hide_view_set', 'anim.keyframe_insert'} for k, i, o in names), sorted(names))
ls = kc.lines(made)
check('... as readable lines (keymap: key  mecha op  shadows  blender op)', ls and all('shadows' in l for l in ls)
      and any('Shift+D' in l and 'mch.duplicate' in l and 'object.duplicate_move' in l for l in ls), ls[:4])
check('The real user keyconfig here is empty (headless): no conflicts, the operator still runs',
      kc.conflicts('user') == [] and bpy.ops.mch.hotkeys_check() == {'FINISHED'})
wm.keyconfigs.remove(made)
check('Preferences > Hotkeys shows the check', 'keymap_check.draw' in __import__('inspect').getsource(
    __import__('mecha_lab.workspace_ui', fromlist=['x']).draw_hotkey_editor))
summary()
