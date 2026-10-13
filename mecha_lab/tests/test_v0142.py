"""0.14.2: Icon Size tab (panel icons, bottom toolbar, viewport handles)."""
import os
import re
import sys
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bottom_bar as bb, workspace_ui as wui

fresh()
mecha_lab.register()
P = wui.MCH_AddonPreferences.bl_rna.properties
check('three size settings, all 1.0 by default (nothing changes until the user moves them)',
      all(P[k].default == 1.0 for k in ('icon_scale', 'toolbar_scale', 'handle_scale')))
check('ranges allow clearly smaller and bigger', P['icon_scale'].hard_min <= 0.5 and P['icon_scale'].hard_max >= 2.0)

fake = types.SimpleNamespace(icon_scale=1.0, toolbar_scale=1.0, handle_scale=1.0)
real_prefs = wui.prefs
wui.prefs = lambda: fake
check('default 1.0: icon sizes stay as designed', wui.isz(2.0) == 2.0)
fake.icon_scale = 1.5
check('Panel Icons 1.5 -> thumbnails 1.5x bigger', abs(wui.isz(2.0) - 3.0) < 1e-9)
fake.icon_scale = 0.1
check('never smaller than a readable minimum', wui.isz(1.0) >= 0.5)
fake.handle_scale = 2.0
check('handle multiplier follows the setting', wui.handle_scale() == 2.0)
res = bpy.ops.mch.icon_size_preset(factor=1.4)
check('Large preset sets all three at once', res == {'FINISHED'} and
      all(abs(v - 1.4) < 1e-6 for v in (fake.icon_scale, fake.toolbar_scale, fake.handle_scale)),
      (res, fake))

pos1, d1 = bb.toolbar_layout(1600, 1.0, 8, 'M')
pos2, d2 = bb.toolbar_layout(1600, 1.0, 8, 'M', factor=2.0)
check('Bottom Toolbar 2.0 -> buttons twice as big, still centred',
      abs(d2 - 2 * d1) < 1e-9 and abs((pos2[0][0] + pos2[-1][0]) / 2 - 800) < 1e-6)
check('bigger toolbar keeps a gap between buttons and lifts above the edge',
      pos2[1][0] - pos2[0][0] > d2 and pos2[0][1] - d2 / 2 >= pos1[0][1] - d1 / 2)
pos3, d3 = bb.toolbar_layout(1600, 1.0, 8, 'M', factor=0.5)
check('Bottom Toolbar 0.5 -> half size', abs(d3 - d1 / 2) < 1e-9)

# every thumbnail in the add-on goes through isz()
src = os.path.join(os.path.dirname(wui.__file__))
raw = []
for name in os.listdir(src):
    if name.endswith('.py'):
        for i, line in enumerate(open(os.path.join(src, name), encoding='utf-8'), 1):
            if 'template_icon' in line and 'scale=' in line and 'isz(' not in line:
                raw.append(f'{name}:{i}')
check('all panel / popup thumbnails follow Panel Icons', not raw, raw)


class L:
    def _c(self, *a, **k):
        return L()
    row = column = box = _c

    def label(self, **k):
        pass

    def prop(self, data, name, **k):
        assert hasattr(data, name), name

    def operator(self, idname, **k):
        return types.SimpleNamespace()


try:
    wui.draw_icon_sizes(L(), fake)
    ok = True
except Exception as ex:
    ok = repr(ex)
check('Icon Size panel draws', ok is True, ok)
check('Icon Size panel is in the Mecha Lab sidebar tab', bpy.types.MCH_PT_icon_size.bl_category == 'Mecha Lab')
wui.prefs = real_prefs
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
