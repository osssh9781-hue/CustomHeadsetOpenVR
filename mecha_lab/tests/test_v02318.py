"""0.23.18 Base Mesh Bevel / Chamfer: Width runs across the top (not capped at the thickness any more), live;
Mirror Apply buttons only in the Mirror tool / Select."""
import sys

_src = open(__file__.replace('test_v02318.py', 'test_v0141.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
from mecha_lab import base_mesh as bm_

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'RECT'
S.mch_settings.mch_active_tool = 'BASE'
S.mch_base.sketch = False
S.mch_base.profile = 'FLAT'
S.mch_base.height = 0.06                                   # a thin plate, 4 x 2
rect(300, 400, 700, 600)
o = [o for o in bpy.data.objects if o.name.startswith('MCH_Base')][0]
p = o.mch_base
check('live Base Mesh right after drawing', bm_.active_live_base(C) is o)


def top_x():
    xs = [v.co.x for v in o.data.vertices if abs(v.co.z - 0.06) < 1e-6]
    return min(xs), max(xs)


p.profile = 'CHAMFER'
p.bevel_sides = 'TOP'
p.bevel_width = 0.4
a, b = top_x()
check('Chamfer width 0.4 on a 6 cm plate: the top is 0.4 narrower on each side (was capped at 0.057)',
      abs(a + 1.6) < 1e-4 and abs(b - 1.6) < 1e-4 and non_manifold(o) == 0, (a, b))
check('... and the rim drops (45 deg up to 95 % of the height)', min(round(v.co.z, 4) for v in o.data.vertices
                                                                    if abs(abs(v.co.x) - 2.0) < 1e-6) == 0.0 and
      any(abs(v.co.z - 0.003) < 1e-4 for v in o.data.vertices), sorted({round(v.co.z, 4) for v in o.data.vertices}))
p.profile = 'BEVEL'
p.bevel_segments = 4
zs = sorted({round(v.co.z, 4) for v in o.data.vertices})
check('Bevel: a rounded rim (several heights), still closed', len(zs) >= 5 and non_manifold(o) == 0, zs)
p.bevel_width = 2.0
check('a width wider than the shape is limited by the shape, and the panel says so',
      non_manifold(o) == 0 and 'limited' in o.get('mch_base_notes', '') and top_x()[1] < 1.1, o.get('mch_base_notes'))
p.bevel_sides = 'BOTTOM'
p.bevel_width = 0.3
xs = [v.co.x for v in o.data.vertices if abs(v.co.z) < 1e-6]
check('Bottom: the bottom face is inset instead', abs(max(xs) - 1.7) < 1e-4 and abs(top_x()[1] - 2.0) < 1e-6, max(xs))
p.bevel_sides = 'BOTH'
check('Both sides: closed, no error', non_manifold(o) == 0 and not p.last_error, p.last_error)
from mecha_lab import mirror_hud
S.mch_settings.mch_active_tool = 'CUT'
cut_hidden = not mirror_hud.shown_for_tool(C)
S.mch_settings.mch_active_tool = 'MIRROR'
check('Mirror Apply / Remove buttons: hidden in Cut, shown in the Mirror tool', cut_hidden and mirror_hud.shown_for_tool(C))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
