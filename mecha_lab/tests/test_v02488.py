"""0.24.58 Mecha Menu (RMB): Line and Sketch switches under the shapes / profiles, for the tools that have them."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mecha_menu as mm, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
real = ts.effective_tool
try:
    for tool in ('CUT', 'BASE'):
        ts.effective_tool = lambda context, t=tool: t
        mm.ts.effective_tool = ts.effective_tool
        items = mm.build(C, 800, 450, 1600, 900, 1.0)
        segs = {i.label: i for i in items if i.kind == 'seg' and i.action and i.action[0] == 'mode'}
        check(f'{tool}: Line and Sketch buttons in the menu', set(segs) == {'Line', 'Sketch'}, list(segs))
        line_before = C.scene.mch_brush.line_mode
        mm.run(C, segs['Line'])
        check(f'{tool}: Line on / off (the menu stays open)', C.scene.mch_brush.line_mode != line_before)
        mm.run(C, segs['Line'])
        on0 = dict((k, v) for k, _l, v in mm.draw_modes(C))['sketch']
        stay = mm.run(C, segs['Sketch'])
        on1 = dict((k, v) for k, _l, v in mm.draw_modes(C))['sketch']
        check(f'{tool}: Sketch on / off', on1 != on0 and stay is False, (on0, on1))
        mm.run(C, segs['Sketch'])
    ts.effective_tool = lambda context: 'CMOVE'
    mm.ts.effective_tool = ts.effective_tool
    check('A tool without line drawing (Concept Move): no switches', mm.draw_modes(C) == [])
finally:
    ts.effective_tool = real
    mm.ts.effective_tool = real
summary()
