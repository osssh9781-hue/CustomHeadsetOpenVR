"""0.24.17 L = the lasso shape menu; the Hotkeys box lists every tool of the left list with an editable key
(unassigned by default, C / S / Alt+A tools keep theirs); Save keeps them in config/mecha_lab/hotkeys.json and they
come back on the next start; Default Keys removes the file."""
import sys, os

_src = open(__file__.replace('test_v02417.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import workspace_ui as wui, tool_state as ts

path = wui._hotkeys_path()
if path and os.path.isfile(path):
    os.remove(path)
items = [it for _km, it in wui._keymaps]
ids = {wui.hotkey_id(it): it for it in items}
check('L = lasso shape menu', ('mch.hotkey', 'SHAPES', '') in ids and ids[('mch.hotkey', 'SHAPES', '')].type == 'L')
tool_ids = [t[0] for t in ts.VISIBLE_TOOLS]
missing = [t for t in tool_ids if t not in wui.TOOL_ACTIONS and ('mch.hotkey', 'TOOL', t) not in ids]
check('one key item per tool of the left list', not missing, missing)
check('tool keys unassigned by default', all(ids[('mch.hotkey', 'TOOL', t)].type == 'NONE' for t in wui.tool_key_ids()))
check('Cut / Split / Armor Plate keep C / S / Alt+A', ids[('mch.hotkey', 'CUT', '')].type == 'C' and
      ids[('mch.hotkey', 'SPLIT', '')].type == 'S' and ids[('mch.hotkey', 'PLATE', '')].type == 'A')

# the editor shows every tool
class Lay:
    def __init__(self):
        self.labels, self.props, self.ops = [], [], []
    def box(self): return self
    def column(self, **k): return self
    def row(self, **k): return self
    def label(self, text='', **k): self.labels.append(text)
    def prop(self, ob, name, **k): self.props.append((ob, name))
    def operator(self, op, **k): self.ops.append(op); return types.SimpleNamespace()
lay = Lay()
wui.draw_hotkey_editor(lay, C)
check('Hotkeys box lists every tool + Save / Default', all(t[1] in lay.labels for t in ts.VISIBLE_TOOLS) and
      'mch.hotkeys_save' in lay.ops and 'mch.hotkeys_reset' in lay.ops and 'Lasso Shape Menu' in lay.labels,
      [t[1] for t in ts.VISIBLE_TOOLS if t[1] not in lay.labels])

# set two keys, save, rebuild the keymaps -> they come back
cur = {wui.hotkey_id(it): it for _km, it in wui.hotkey_items(C)}
cur[('mch.hotkey', 'TOOL', 'BASE')].type = 'K'
cur[('mch.hotkey', 'TOOL', 'BASE')].ctrl = True
cur[('mch.hotkey', 'CUT', '')].type = 'J'
n = wui.save_hotkeys(C)
check('Save writes the keys', n > 10 and os.path.isfile(path), n)
wui.unregister_keymaps()
wui.register_keymaps()
ids = {wui.hotkey_id(it): it for _km, it in wui._keymaps}
check('after a restart: Ctrl+K = Base Mesh, J = Cut', ids[('mch.hotkey', 'TOOL', 'BASE')].type == 'K' and
      ids[('mch.hotkey', 'TOOL', 'BASE')].ctrl and ids[('mch.hotkey', 'CUT', '')].type == 'J')
check('the other keys are unchanged', ids[('mch.hotkey', 'SHAPES', '')].type == 'L' and
      ids[('mch.hotkey', 'TOOL', 'SUBD')].type == 'NONE')

# a tool key picks the tool, L opens the shape popup
calls = []
real = wui.activate_mecha_tool
wui.activate_mecha_tool = lambda ctx, tid: calls.append(tid)
orig_bpy = wui.bpy
wui.bpy = types.SimpleNamespace(ops=types.SimpleNamespace(wm=types.SimpleNamespace(
    call_panel=lambda **k: calls.append(('panel', k.get('name'))))), types=bpy.types)
try:
    wui.MCH_OT_hotkey.execute(types.SimpleNamespace(action='TOOL', tool='DETAIL3', only_empty=False), C)
    wui.MCH_OT_hotkey.execute(types.SimpleNamespace(action='SHAPES', tool='CUT', only_empty=False), C)
finally:
    wui.activate_mecha_tool = real
    wui.bpy = orig_bpy
check('tool key -> that tool; L -> the shape popup', calls == ['DETAIL3', ('panel', 'MCH_PT_shape_popup')], calls)

# Default Keys
wui.MCH_OT_hotkeys_reset.execute(types.SimpleNamespace(report=lambda *a: None), C)
ids = {wui.hotkey_id(it): it for _km, it in wui._keymaps}
check('Default Keys: file removed, C = Cut again, Base Mesh unassigned', not os.path.isfile(path) and
      ids[('mch.hotkey', 'CUT', '')].type == 'C' and ids[('mch.hotkey', 'TOOL', 'BASE')].type == 'NONE')
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
