"""0.23.5: organic (curved) cell edges and an irregular border where the cells get smaller
(wide inside, narrow at the border) - Creature Shell and Creature Skin."""
import math
import sys

_src = open(__file__.replace('test_v0235.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, creature_shell as cs, last_used
for sec in ('creature', 'shell', 'wrinkle'):
    last_used.forget(sec)

# ---- Creature Shell
names = [n for n, *_r in cs.INPUTS]
check('shell: Organic / Edge Shrink / Shrink Width / Edge Irregular inputs, appended after the old ones',
      names[-4:] == ['Organic', 'Edge Shrink', 'Shrink Width', 'Edge Irregular'] and names.index('V') == len(names) - 5)
check('shell HUD sliders for them', {'organic', 'shrink', 'shrink_w', 'irregular'} <= {k[0] for k in cs.SLIDERS})
check('Shrink Width scales with the plate', 'Shrink Width' in cs.SIZE_INPUTS and 'Shrink Width' in cs.DEFAULTS)
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
S.mch_settings.mch_active_tool = 'PLATE'
S.mch_plate.creature = True
b = cube('Body', 4.0)
r, m = lasso([(300, 330), (700, 330), (720, 660), (330, 680)])
sh = C.active_object
check('shell plate made', r == {'FINISHED'} and cs.is_shell(sh), m)
cs.set_input(sh, 'Bulge', 0.0)


def ev():
    dg = C.evaluated_depsgraph_get()
    me = sh.evaluated_get(dg).data
    co = np.array([v.co[:] for v in me.vertices])
    nz = np.array([p.normal.z for p in me.polygons])
    return co


cs.set_input(sh, 'Organic', 0.0)
cs.set_input(sh, 'Edge Shrink', 0.0)
a0 = ev()
cs.set_input(sh, 'Organic', 1.0)
a1 = ev()
check('Organic bends the plates (the surface changes)', a0.shape == a1.shape and np.abs(a1 - a0)[:, 2].max() > 1e-4)
cs.set_input(sh, 'Edge Shrink', 0.8)
a2 = ev()
# points on the top: distance from the plate outline in the plate plane
top = a1[:, 2] > a1[:, 2].max() - 0.2
xy = a1[:, :2]
lo, hi = xy[top].min(0), xy[top].max(0)
edge_d = np.minimum(xy - lo, hi - xy).min(1)
sw = float(cs.get_input(sh, 'Shrink Width'))
inner = top & (edge_d > sw * 2.2)
outer = top & (edge_d < sw * 0.5)
di = np.abs(a2 - a1)[inner, 2].max() if inner.any() else 1.0
do = np.abs(a2 - a1)[outer, 2].max() if outer.any() else 0.0
check('Edge Shrink: the inside keeps its wide plates, the border gets smaller ones',
      inner.sum() > 20 and outer.sum() > 20 and di < 1e-6 and do > 1e-4, (int(inner.sum()), int(outer.sum()), di, do))
cs.set_input(sh, 'Edge Irregular', 0.0)
a3 = ev()
cs.set_input(sh, 'Edge Irregular', 1.5)
a4 = ev()
check('Edge Irregular moves the small-plate border', np.abs(a4 - a3)[top, 2].max() > 1e-4)
S.mch_plate.creature = False

# ---- Creature Skin
check('skin: Skin Organic / Skin Irregular inputs + sliders',
      (lambda ns: ns[ns.index('Skin Organic') + 1] == 'Skin Irregular')([n for n, *_r in cw.INPUTS]) and
      {'skin_organic', 'skin_irregular'} <= set(cw.SKIN_KEYS) and
      {'skin_organic', 'skin_irregular'} <= {k[0] for k in cw.SLIDERS})
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.creature = True
S.mch_wrinkle.skin = 'GODZILLA'
b2 = cube('B2', 4.0, loc=(6, 0, 0))
VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((6, 0, 0)))
r, m = lasso([(300, 330), (700, 330), (720, 660), (330, 680)])
o = C.active_object
check('skin plate made', r == {'FINISHED'} and cw.is_creature(o), m)


def evz(ob_):
    dg = C.evaluated_depsgraph_get()
    return np.array([v.co.z for v in ob_.evaluated_get(dg).data.vertices])


cw.set_input(o, 'Skin Organic', 0.0)
z0 = evz(o)
cw.set_input(o, 'Skin Organic', 1.0)
z1 = evz(o)
check('Skin Organic bends the scale edges', z0.shape == z1.shape and np.abs(z1 - z0).max() > 1e-5)
cw.set_input(o, 'Skin Irregular', 0.0)
z2 = evz(o)
cw.set_input(o, 'Skin Irregular', 1.5)
z3 = evz(o)
check('Skin Irregular moves the shrink border', np.abs(z3 - z2).max() > 1e-5)
S.mch_wrinkle.creature = False
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
