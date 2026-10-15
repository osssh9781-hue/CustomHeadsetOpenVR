"""0.23.19 Cloth Plate Overall Scale: one slider scales every length (not the trim); the wrinkles stay as they are."""
import sys

_src = open(__file__.replace('test_v02319.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, last_used
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
S.mch_wrinkle.wtype = 'DENIM'
S.mch_wrinkle.trim = 'BINDING'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
o = C.active_object
check('Overall Scale is the first Cloth Plate slider (100 %)', cw.slider_keys(o)[0] == 'all_scale' and
      cw.slider_spec(C, 'all_scale', o)[1] == 100)
names = sorted((cw.SIZE_INPUTS - cw.SCALE_ALL_SKIP) & cw.INPUT_NAMES)
before = {n: float(cw.get_input(o, n)) for n in names}
other = {n: float(cw.get_input(o, n)) for n in ('Fan', 'Fold Sharp', 'Fold Tilt', 'Variety', 'Type')}
trim = (cw.get_input(o, 'Trim Width'), cw.get_input(o, 'Trim Height'))
thick = o.modifiers[cw.MOD_SHELL].thickness
cw.slider_spec(C, 'all_scale', o)[4](200)
check('200 %: every length x2 (folds, puff, roll, stitch, pattern...)',
      all(abs(float(cw.get_input(o, n)) - 2 * before[n]) <= 1e-6 * max(1.0, abs(before[n])) for n in names),
      [n for n in names if abs(float(cw.get_input(o, n)) - 2 * before[n]) > 1e-6 * max(1.0, abs(before[n]))])
check('... thickness x2, the trim stays, angles / sharpness / fan stay',
      abs(o.modifiers[cw.MOD_SHELL].thickness - 2 * thick) < 1e-9 and
      (cw.get_input(o, 'Trim Width'), cw.get_input(o, 'Trim Height')) == trim and
      all(abs(float(cw.get_input(o, n)) - v) < 1e-9 for n, v in other.items()))
check('the slider shows 200 %', cw.slider_spec(C, 'all_scale', o)[1] == 200)
cw.slider_spec(C, 'all_scale', o)[4](100)
check('back to 100 %: the original values', all(abs(float(cw.get_input(o, n)) - before[n]) <= 1e-6 * max(1.0, abs(before[n]))
                                                for n in names) and abs(o.modifiers[cw.MOD_SHELL].thickness - thick) < 1e-9)
dg = C.evaluated_depsgraph_get()
check('the panel still evaluates', len(o.evaluated_get(dg).data.vertices) > 100)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
