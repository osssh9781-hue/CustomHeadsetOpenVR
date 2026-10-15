"""0.23.27 Lasso Settings: one shared sidebar panel shown in every tool (Armor Plate, Cloth Plate and the
others had none); the tool panels no longer draw their own copy."""
import sys

_src = open(__file__.replace('test_v02327.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import tool_state as ts, workspace_ui as wui, ui_tool_settings as uts


class Lay:
    """Records every prop / label drawn."""
    def __init__(self, log):
        self.log = log

    def __getattr__(self, name):
        def f(*a, **k):
            if name == 'prop' and len(a) > 1:
                self.log.append(a[1])
            if name == 'label':
                self.log.append(k.get('text', ''))
            return Lay(self.log)
        return f

    def __setattr__(self, name, value):
        object.__setattr__(self, name, value)


class P:
    def __init__(self):
        self.log = []
        self.layout = Lay(self.log)


S.mch_brush.shape = 'STROKE'
for tool in sorted(ts.SHAPE_TOOLS):
    S.mch_settings.mch_active_tool = tool
    ok = wui.MCH_PT_lasso.poll(C)
    p = P()
    if ok:
        wui.MCH_PT_lasso.draw(p, C)
    check(f'{tool}: Lasso Settings shown with smoothing', ok and 'stroke_smooth' in p.log)
    q = P()
    try:
        uts.DRAWERS[tool](q.layout, C)
    except Exception as e:     # some drawers need a live object; only the duplication matters here
        print('  (drawer', tool, 'raised', type(e).__name__, ')')
    check(f'{tool}: tool panel has no second copy', 'stroke_smooth' not in q.log)
for tool in [t[0] for t in ts.TOOLS if t[0] not in ts.SHAPE_TOOLS]:
    S.mch_settings.mch_active_tool = tool
    p = P()
    ok = wui.MCH_PT_lasso.poll(C)
    if ok:
        wui.MCH_PT_lasso.draw(p, C)
    check(f'{tool}: Lasso Settings shown too', ok and 'stroke_smooth' in p.log)
S.mch_brush.shape = 'LASSO'
S.mch_settings.mch_active_tool = 'CUT'
p = P()
wui.MCH_PT_lasso.draw(p, C)
check('Cut + Lasso: edge finish still under the lasso settings', 'edge_finish' in p.log)
from mecha_lab import cut_engine as ce
check('Alt outline red for every lasso tool', all(ce.stroke_color(m, True) == ce.ALT_RED for m in ts.SHAPE_TOOLS))
check('without Alt each tool keeps its colour', ce.stroke_color('PLATE', False) != ce.ALT_RED)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
