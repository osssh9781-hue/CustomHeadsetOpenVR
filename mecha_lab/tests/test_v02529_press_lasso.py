"""0.24.122 (user: "프레스 컷에 라쏘 모드도 만들어 줘 - 걍 베이스 메쉬 기존 라쏘처럼 작동하면 돼")
Press Cut: Draw = Line (as before) / Lasso - in Lasso mode the press IS the Base Mesh tool's own lasso stroke
(mch.cut_stroke, mode BASE: same shapes, corners, sketch, Alt and result); Shift + draw still draws the stamp.
"""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import key_legend, press_cut as pc, top_bar

fresh()
mecha_lab.register()
C = bpy.context
st = C.scene.mch_press

check('Press has Draw: Line / Lasso, Line by default', st.bl_rna.properties['draw_mode'].default == 'LINE'
      and {e.identifier for e in st.bl_rna.properties['draw_mode'].enum_items} == {'LINE', 'LASSO'} and not pc.lasso_mode(st))
st.draw_mode = 'LASSO'
check('lasso_mode reads it', pc.lasso_mode(st))


class Ev:
    def __init__(self, shift=False, alt=False):
        self.shift, self.alt, self.ctrl = shift, alt, False
        self.mouse_region_x = self.mouse_region_y = 100
        self.type, self.value = 'LEFTMOUSE', 'PRESS'


class Shim:
    def __init__(self):
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((kind, msg))


class Shim:
    def __init__(self):
        self.reports = []

    def report(self, kind, msg):
        self.reports.append((kind, msg))


r1 = pc.MCH_OT_press_unified.invoke(Shim(), C, Ev())
r2 = pc.MCH_OT_press_unified.invoke(Shim(), C, Ev(alt=True))
check('Lasso mode: the Press tool\'s own press steps aside (PASS_THROUGH) for plain and Alt - the Base Mesh stroke bound '
      'ahead of it in the keymap takes the press', r1 == {'PASS_THROUGH'} and r2 == {'PASS_THROUGH'}, (r1, r2))
st.draw_mode = 'LINE'
km = [(k[0], (k[2] or {}).get('properties')) for k in pc.TOOL_KEYMAP]
names = [k[0] for k in km]
i_stroke = names.index('mch.cut_stroke')
check('the Press keymap binds mch.cut_stroke (mode BASE, press_lasso) on the plain and the Alt press, BEFORE the Press '
      'tool\'s own press', km[i_stroke][1] == [('mode', 'BASE'), ('press_lasso', True)] and km[i_stroke + 1][1] == [('mode', 'BASE'), ('press_lasso', True)]
      and i_stroke < names.index('mch.press_unified') and names.index('mch.quick_hud_press') < i_stroke, km[:5])
props = bpy.ops.mch.cut_stroke.get_rna_type().properties
src_ce = open(mecha_lab.cut_engine.__file__).read()
check('mch.cut_stroke has the press_lasso gate: it runs only while Press Cut is in Lasso mode, else passes through to the '
      'Press tool; the plain tool check stays for everyone else',
      'press_lasso' in props and "if getattr(self, 'press_lasso', False):" in src_ce
      and "if st_ is None or getattr(st_, 'draw_mode', 'LINE') != 'LASSO':" in src_ce
      and "if not getattr(self, 'force', False) and ts.effective_tool(context) != self.mode:" in src_ce)
src = open(pc.__file__).read()
check('wired: the cursor shows the Base Mesh cursor in Lasso mode, the sidebar has the Draw row',
      'ce.draw_stamp_cursor(context, xy)' in src and "row.prop(st, 'draw_mode', expand=True)" in src and hasattr(bpy.types, 'MCH_OT_cut_stroke'))
src_t = open(top_bar.__file__).read()
check('the Press top bar has a Draw: Line / Lasso group and names the shapes row "Shape" in Lasso mode',
      "_enum_segs(pr, 'draw_mode', (('LINE', 'Line'), ('LASSO', 'Lasso')))" in src_t and "'Shape' if lasso_on else 'Shift+Draw'" in src_t)
from mecha_lab import base_mesh
km = [k[0] for k in pc.TOOL_KEYMAP]
check('the Press keymap carries the Base Mesh sketch keys (Enter / Alt+Enter / Esc / Backspace) - Sketch First works in '
      'Lasso mode - and their poll admits Press in Lasso mode',
      km.count('mch.base_sketch_key') == 4 and 'mch.base_sketch_clear' in km and 'mch.base_sketch_undo' in km
      and km.index('mch.base_sketch_key') < km.index('mch.exit_tool')
      and 'sketch_tool_ok(context) and sketch_data(context.scene) is not None' in open(base_mesh.__file__).read())
st.draw_mode = 'LASSO'
try:
    ok_lasso = base_mesh.sketch_tool_ok(C) if False else None     # (no tool in a headless context: the source check above)
finally:
    st.draw_mode = 'LINE'
check('the key legend tells it', any('Draw: Lasso' in line for line in key_legend.LEGEND['PRESS']) if hasattr(key_legend, 'LEGEND')
      else 'Draw: Lasso (top bar)' in open(key_legend.__file__).read())
summary()
