"""Register / unregister / re-register, UI icon names, panel draw smoke test."""
import re
import os
from _harness import bpy, check, fresh

import mecha_lab

fresh()
for cycle in range(2):
    try:
        mecha_lab.register()
        ok = True
    except Exception as ex:
        ok = False
        import traceback; traceback.print_exc()
    check(f'register cycle {cycle}', ok)
    check(f'ops present {cycle}', hasattr(bpy.ops.mch, 'cut_stroke') and hasattr(bpy.ops.mch, 'workspace_open'))
    check(f'scene props {cycle}', all(hasattr(bpy.context.scene, n) for n in
                                      ('mch_settings', 'mch_brush', 'mch_cut', 'mch_png_preset')))
    try:
        mecha_lab.unregister()
        ok = True
    except Exception:
        ok = False
        import traceback; traceback.print_exc()
    check(f'unregister cycle {cycle}', ok)
    check(f'no leftover op {cycle}', not hasattr(bpy.types, 'MCH_OT_cut_stroke'))

# Icon names used anywhere in the source must exist in this Blender build
icons = set(bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items.keys())
src_dir = os.path.dirname(mecha_lab.__file__)
bad = []
for fn in os.listdir(src_dir):
    if fn.endswith('.py'):
        text = open(os.path.join(src_dir, fn), encoding='utf-8').read()
        for m in re.finditer(r"icon\s*=\s*'([A-Z0-9_]+)'", text):
            line = text[text.rfind('\n', 0, m.start()) + 1:text.find('\n', m.start())]
            if 'confirm_text' in line or 'invoke_confirm' in line:
                continue   # invoke_confirm uses its own small icon enum
            if m.group(1) not in icons:
                bad.append((fn, m.group(1)))
from mecha_lab import tool_state as ts
for t in ts.TOOLS:
    if t[4] not in icons:
        bad.append(('tool_state', t[4]))
for s in ts.SHAPES:
    if s[4] not in icons:
        bad.append(('tool_state', s[4]))
check('all icon names valid in this Blender', not bad, bad)

# The v0.5.9 release used icon names that no longer exist (shown here so the
# report documents the real cause of the Smart Fuse panel traceback).
ref = os.path.join(os.path.dirname(os.path.dirname(src_dir)), 'reference', 'RELEASE_v0_5_9', 'mecha_lab')
old_bad = []
if os.path.isdir(ref):
    for fn in os.listdir(ref):
        if fn.endswith('.py'):
            for m in re.finditer(r"icon\s*=\s*'([A-Z0-9_]+)'", open(os.path.join(ref, fn), encoding='utf-8').read()):
                if m.group(1) not in icons:
                    old_bad.append((fn, m.group(1)))
print('INFO v0.5.9 invalid icon names in Blender', bpy.app.version_string, ':', old_bad)

from _harness import summary
import sys
sys.exit(1 if summary() else 0)
