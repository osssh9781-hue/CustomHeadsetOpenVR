"""Data-level checks of the MECHA LAB workspace helpers and keymap scoping.

Creating/switching a workspace needs a window, so workspace.duplicate, the
deferred area split and real key presses are NOT tested here (GUI checklist).
"""
import sys

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import tool_state as ts, workspace_ui as wui

fresh()
bpy.ops.wm.read_factory_settings(use_empty=False)
mecha_lab.register()

names_before = [w.name for w in bpy.data.workspaces]
screens_before = {s.name: [(a.type, a.x, a.y, a.width, a.height) for a in s.areas] for s in bpy.data.screens}

layout = bpy.data.screens['Layout']
area = wui.configure_screen(layout)
sp = area.spaces.active
check('configure_screen picks the 3D view', area is not None and area.type == 'VIEW_3D')
check('toolbar / tool header / sidebar shown', sp.show_region_toolbar and sp.show_region_tool_header and sp.show_region_ui)
after = [(a.type, a.x, a.y, a.width, a.height) for a in layout.areas]
same = len(after) == len(screens_before['Layout']) and all(
    a[0] == b[0] and all(abs(p - q) <= 4 for p, q in zip(a[1:], b[1:]))
    for a, b in zip(sorted(screens_before['Layout']), sorted(after)))
check('configure_screen keeps areas (only region flags; <=4px rect recompute)', same,
      (screens_before['Layout'], after))
check('no left tool area on stock Layout', wui.left_tool_area(layout) is None)
check('register created no workspace', [w.name for w in bpy.data.workspaces] == names_before)
check('find_mecha_workspace none by default', ts.find_mecha_workspace() is None)

ws = bpy.data.workspaces['Modeling']
check('stock workspace not detected as MECHA', not ts.is_mecha_workspace(ws))
ws[ts.WORKSPACE_TAG] = True
check('tagged workspace detected (even if renamed)', ts.is_mecha_workspace(ws) and ts.find_mecha_workspace() == ws)
del ws[ts.WORKSPACE_TAG]

kc = bpy.context.window_manager.keyconfigs.addon
items = [(km.name, ki.idname, ki.type) for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')]
check('addon keymap: Space -> mch.space_tools (gated)', ('3D View', 'mch.space_tools', 'SPACE') in items, items)
check('addon keymap: B/C via gated mch.hotkey only', {('Object Mode', 'mch.hotkey', 'B'), ('Object Mode', 'mch.hotkey', 'C')} <= set(items))
check('no ungated mch.boolean / draw_delete_cut keys', not any(i[1] in ('mch.boolean', 'mch.draw_delete_cut') for i in items))

tools = [t.idname for t in bpy.types.VIEW3D_PT_tools_active._tools['OBJECT'] if t is not None and hasattr(t, 'idname')] \
    if hasattr(bpy.types.VIEW3D_PT_tools_active, '_tools') else []
mecha_lab.unregister()
items_after = [ki.idname for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')]
check('unregister removes all addon keymap items', not items_after, items_after)
check('unregister removes tool header palette',
      wui.draw_shape_palette not in getattr(bpy.types.VIEW3D_HT_tool_header, '_dyn_ui_initialize', lambda: [])())
mecha_lab.register()
mecha_lab.unregister()
items_after = [ki.idname for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')]
check('re-register/unregister leaves no duplicate keys', not items_after)
sys.exit(1 if summary() else 0)
