"""B09: "MCH_PG_Brush already registered" - registration must heal itself.

Scenarios: unregister crashing half-way, leftovers from an older run,
a second Mecha Lab copy enabled at the same time, an exception in the
middle of register(), and repeated cycles without duplicated keymaps,
header draw functions or workspace tools.
"""
import importlib
import os
import shutil
import sys
import tempfile

from _harness import ADDON_PARENT, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import addon_safety, primitive_tools, tool_state, workspace_ui


def mecha_classes(prefix='mecha_lab'):
    return [n for n in dir(bpy.types) if n.startswith('MCH_') and
            (getattr(getattr(bpy.types, n), '__module__', '') or '').startswith(prefix)]


def mch_props():
    return [p.identifier for p in bpy.types.Scene.bl_rna.properties if p.identifier.startswith('mch_') and p.is_runtime]


def keymap_items():
    kc = bpy.context.window_manager.keyconfigs.addon
    if kc is None:
        return []
    return [(km.name, ki.idname, ki.type) for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')]


def header_funcs():
    return [f for f in bpy.types.VIEW3D_HT_tool_header._dyn_ui_initialize()
            if 'mecha_lab' in (getattr(f, '__module__', '') or '')]


def tool_ids():
    from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
    cls = ToolSelectPanelHelper._tool_class_from_space_type('VIEW_3D')
    return [getattr(t, 'idname', '') for t in cls._tools.get('OBJECT', []) if t is not None
            and getattr(t, 'idname', '').startswith('mecha.')]


fresh()

# 1. plain cycles: nothing duplicated, nothing left ------------------------------
for cycle in range(3):
    mecha_lab.register()
    check(f'cycle {cycle}: Mirror sub-panel registered', hasattr(bpy.types, 'MCH_PT_mirror'))
    check(f'cycle {cycle}: one shape palette in the tool header', len(header_funcs()) == 1, len(header_funcs()))
    km = keymap_items()
    check(f'cycle {cycle}: no duplicated keymap items', len(km) == len(set(km)), km)
    tids = tool_ids()
    check(f'cycle {cycle}: Mecha tools registered once', len(tids) == len(set(tids)) and 'mecha.cut' in tids, tids)
    mecha_lab.unregister()
    check(f'cycle {cycle}: unregister leaves no class', not mecha_classes(), mecha_classes())
    check(f'cycle {cycle}: unregister leaves no scene prop', not mch_props(), mch_props())
    check(f'cycle {cycle}: unregister leaves no keymap / tool / header func',
          not keymap_items() and not tool_ids() and not header_funcs())

# 2. an unregister step crashes: the rest still runs --------------------------------
mecha_lab.register()
orig = workspace_ui.unregister


def boom():
    raise RuntimeError('simulated crash in workspace_ui.unregister')


workspace_ui.unregister = boom
mecha_lab.unregister()
workspace_ui.unregister = orig
check('crashing unregister step is reported, not fatal', addon_safety.LAST_ERRORS and
      'workspace_ui' in addon_safety.LAST_ERRORS[0], addon_safety.LAST_ERRORS)
check('...and MCH_PG_Brush is still unregistered', not addon_safety.is_registered(tool_state.MCH_PG_Brush))
try:
    mecha_lab.register()
    ok = True
except Exception as ex:
    ok = False
    print(ex)
check('register after a crashed unregister works', ok and hasattr(bpy.types, 'MCH_PT_mirror'))
mecha_lab.unregister()

# 3. leftovers of an old run (the exact v0.9.3 report) -------------------------------
mecha_lab.register()
# old code that died right after the sub panels: everything else still registered
for klass in reversed(mecha_lab.SUB_PANELS):
    bpy.utils.unregister_class(klass)
check('setup: MCH_PG_Brush still registered (old crash state)', addon_safety.is_registered(tool_state.MCH_PG_Brush))
try:
    mecha_lab.register()
    ok = True
except Exception as ex:
    ok = False
    print('register error:', ex)
check('no "MCH_PG_Brush already registered": register heals leftovers', ok)
check('after healing: Mirror / Radial / Surface panels exist',
      all(hasattr(bpy.types, n) for n in ('MCH_PT_mirror', 'MCH_PT_radial', 'MCH_PT_surface_conform')))
check('after healing: keymaps not duplicated', len(keymap_items()) == len(set(keymap_items())))
check('after healing: scene settings usable', hasattr(bpy.context.scene, 'mch_brush') and
      bpy.context.scene.mch_brush.shape == 'LASSO')
mecha_lab.unregister()

# 4. exception in the middle of register(): complete rollback ------------------------
orig = primitive_tools.register


def fail():
    raise RuntimeError('simulated register failure')


primitive_tools.register = fail
raised = False
try:
    mecha_lab.register()
except RuntimeError:
    raised = True
primitive_tools.register = orig
check('failing register raises (Blender shows the error)', raised)
check('failing register rolls back every class', not mecha_classes(), mecha_classes())
check('failing register rolls back props / keymaps / tools', not mch_props() and not keymap_items() and not tool_ids())
try:
    mecha_lab.register()
    ok = True
except Exception as ex:
    ok = False
check('register works again after the failure', ok and hasattr(bpy.types, 'MCH_PT_mirror'))
mecha_lab.unregister()

# 5. a second Mecha Lab copy (old legacy add-on) is active -----------------------------
tmp = tempfile.mkdtemp(prefix='mch_copy_')
shutil.copytree(os.path.join(ADDON_PARENT, 'mecha_lab'), os.path.join(tmp, 'mecha_lab_old'),
                ignore=shutil.ignore_patterns('__pycache__'))
sys.path.insert(0, tmp)
old = importlib.import_module('mecha_lab_old')
old.register()
check('setup: other copy registered', addon_safety.is_registered(old.tool_state.MCH_PG_Brush))
try:
    mecha_lab.register()
    ok = True
except Exception as ex:
    ok = False
    print('register error:', ex)
check('second copy active: this copy still registers', ok and addon_safety.is_registered(tool_state.MCH_PG_Brush)
      and not addon_safety.is_registered(old.tool_state.MCH_PG_Brush))
check('the other copy is reported (UI warning)', 'mecha_lab_old' in addon_safety.FOREIGN, addon_safety.FOREIGN)
check('no class of the other copy remains', not mecha_classes('mecha_lab_old'))
mecha_lab.unregister()
check('unregister cleans this copy', not mecha_classes())
sys.path.remove(tmp)
shutil.rmtree(tmp, ignore_errors=True)

sys.exit(1 if summary() else 0)
