"""0.24.20 a hotkey that runs Remesh + Smooth right away (unassigned until set in the Hotkeys box / Remesh panel),
new tool pictures and Plate Detail in the Line list."""
import os

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import lasso_line, tool_state as ts, workspace_ui as wsui

mecha_lab.register()
fresh()
C = bpy.context
items = [it for _km, it in wsui.hotkey_items(C) if wsui.hotkey_id(it)[1] == 'REMESH']
check('a Remesh + Smooth run key exists', len(items) == 1)
check('it starts unassigned (you pick the key)', items and items[0].type == 'NONE', items and items[0].type)
check('it is labelled in the Hotkeys box', wsui.HOTKEY_LABELS.get('REMESH', '').startswith('Remesh'))
check('the key runs the Remesh action', items and items[0].idname == 'mch.hotkey'
      and items[0].properties.action == 'REMESH')
icons = os.path.join(os.path.dirname(mecha_lab.__file__), 'icons')
for tid in ('CBASE', 'CPLATE', 'BELT', 'SPIKE', 'SCALES', 'SBRUSH', 'BRIDGE', 'FLOWER', 'SCURVE'):
    stem = ts.TOOL_BY_ID[tid][3]
    check(f'{tid} has its own picture ({stem}.png)', os.path.isfile(os.path.join(icons, stem + '.png')))
for stem in ('profile_puff', 'profile_ridge', 'profile_pillow', 'profile_cushion'):
    check(f'profile picture {stem}.png', os.path.isfile(os.path.join(icons, stem + '.png')))
check('Plate Detail 1 / 2 / 3 take the Line button', {'DETAIL', 'DETAIL2', 'DETAIL3'} <= lasso_line.MODES)
summary()
