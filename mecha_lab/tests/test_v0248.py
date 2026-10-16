"""0.24.8 hotkeys in MECHA LAB: Alt+X = Mirror (lean, live), S = Split only with nothing selected (else Blender's
Scale), Alt+A = Armor Plate."""
import sys

_src = open(__file__.replace('test_v0248.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import workspace_ui as wui, tool_state as ts

items = {}
for km, it in wui._keymaps:
    if it.idname == 'mch.hotkey':
        items[(it.type, it.alt, it.shift, it.ctrl)] = (km.name, it)
for key, action in (('X', 'MIRROR'), ('S', 'SPLIT'), ('A', 'PLATE')):
    alt = key != 'S'
    got = items.get((key, alt, False, False))
    check(f'{"Alt+" if alt else ""}{key} -> {action} in Object Mode', got is not None and got[0] == 'Object Mode'
          and got[1].properties.action == action, got and (got[0], got[1].properties.action))
check('S item only with nothing selected', items[('S', False, False, False)][1].properties.only_empty)

calls = []
real_activate = wui.activate_mecha_tool
wui.activate_mecha_tool = lambda ctx, tid: calls.append(tid)
real_poll = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda ws: True
check('poll ok in MECHA LAB, Object Mode', wui.MCH_OT_hotkey.poll(C))


def run(action, only_empty=False):
    op = types.SimpleNamespace(action=action, only_empty=only_empty, reports=[])
    op.report = lambda kind, msg: op.reports.append(msg)
    op.execute = lambda ctx: wui.MCH_OT_hotkey.execute(op, ctx)
    return wui.MCH_OT_hotkey.invoke(op, C, None), op


b = cube('Hull', 2.0)
select_only(b)
res, _ = run('SPLIT', True)
check('S with a selection passes through (Blender Scale)', res == {'PASS_THROUGH'} and not calls, (res, calls))
for o in bpy.data.objects:
    o.select_set(False)
res, _ = run('SPLIT', True)
check('S with nothing selected -> Split tool', res == {'FINISHED'} and calls == ['SPLIT'], (res, calls))
calls.clear()
res, _ = run('PLATE')
check('Alt+A -> Armor Plate tool', res == {'FINISHED'} and calls == ['PLATE'], (res, calls))
res, op = run('MIRROR')
check('Alt+X with nothing selected: warning, no tool change', res == {'CANCELLED'} and op.reports, (res, op.reports))
select_only(b)
lean = []
import mecha_lab.workspace_ui as W
orig = W.bpy
W.bpy = types.SimpleNamespace(ops=types.SimpleNamespace(mch=types.SimpleNamespace(
    mirror_lean=lambda *a, **k: (lean.append((a, k)), {'RUNNING_MODAL'})[1])), types=bpy.types)
try:
    res, _ = run('MIRROR')
finally:
    W.bpy = orig
check('Alt+X with a mesh selected -> live lean Mirror', res == {'RUNNING_MODAL'} and lean and
      lean[0][1].get('keep_live') is True, (res, lean))
wui.activate_mecha_tool = real_activate
ts.is_mecha_workspace = real_poll

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
