"""0.24.65 Tool Search (Ctrl+F / the Search tile) and Tool Presets (the side panel's Presets section): save the chosen
tool's settings under a name, use them again in any file, delete them."""
import inspect
import os

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import side_panel as sp, tool_presets as tp, tool_state as ts, ui_bars as ub

mecha_lab.register()
fresh()
C = bpy.context

items = tp._tool_items(None, C)
check('Tool Search lists every Mecha tool by name', len(items) == len(ts.TOOLS)
      and ('PLATE', ts.TOOL_BY_ID['PLATE'][1], ts.TOOL_BY_ID['PLATE'][2]) in items)
kc = C.window_manager.keyconfigs.addon
keys = [(km.name, ki.idname, ki.type, ki.ctrl) for km in kc.keymaps for ki in km.keymap_items]
check('Ctrl+F = Tool Search (Object Mode), and a Search tile with the actions',
      ('Object Mode', 'mch.tool_search', 'F', True) in keys
      and any(a[0] == 'search' and a[3] == ('op', 'mch.tool_search', {}) for a in ub.ACTIONS))
r = bpy.ops.mch.tool_search('EXEC_DEFAULT', tool='PLATE')
check('Picking a tool in the search switches to it', r == {'FINISHED'}
      and C.scene.mch_settings.mch_active_tool == 'PLATE', C.scene.mch_settings.mch_active_tool)

name, pg = tp.group_for(C.scene, 'PLATE')
check('The tool\'s settings group is found (Armor Plate = scene.mch_plate)', name == 'mch_plate' and pg is not None)
key = next(k for k in tp.values(pg) if pg.bl_rna.properties[k].type == 'FLOAT')
old = getattr(pg, key)
setattr(pg, key, old + 0.01 if pg.bl_rna.properties[key].hard_max >= old + 0.01 else old - 0.01)
mine = getattr(pg, key)
msg = tp.save(C.scene, 'PLATE', 'Test Thick')
check('Save: the tool\'s settings under your name, in the add-on\'s user folder (not in the .blend)',
      'saved' in msg and 'Test Thick' in tp.names('PLATE') and os.path.isfile(tp._path())
      and 'Test Thick' not in str(dict(C.scene.items())), msg)
setattr(pg, key, old)
msg = tp.load(C.scene, 'PLATE', 'Test Thick')
check('Load: the settings come back', abs(getattr(pg, key) - mine) < 1e-6, (getattr(pg, key), mine, msg))
check('A tool without settings says so', 'no settings' in tp.save(C.scene, 'NO_SUCH_TOOL', 'x'))
check('Delete', 'deleted' in tp.delete('PLATE', 'Test Thick') and 'Test Thick' not in tp.names('PLATE'))
check('The side panel has a folded Presets section for the tool', "'Presets'" in inspect.getsource(sp.content)
      and 'tool_presets.draw_presets' in inspect.getsource(sp.content))
check('Presets load is an undo step (it may change a live part), Save / Delete only touch your preset file',
      'UNDO' in tp.MCH_OT_tool_preset_load.bl_options and 'UNDO' not in tp.MCH_OT_tool_preset_save.bl_options)
mecha_lab.unregister()
summary()
