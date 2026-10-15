"""0.23.15: Cloth Plate / Panel Cloth back to 0.23.9; last used lengths follow the panel size; Space moves the outline."""
import math
import sys

_src = open(__file__.replace('test_v02315.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import cloth_wrinkle as cw, last_used

S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'

# 2b. last used lengths follow the panel size (a small panel after a big one exploded into shards)
for o_ in list(bpy.data.objects):
    bpy.data.objects.remove(o_)
last_used.forget('wrinkle')
S.mch_wrinkle.wtype = 'DENIM'
big = cube('Big', 40.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
A = C.active_object
sa = A['mch_wrinkle_size']
cw.set_input(A, 'Pinch Length', sa * 0.31)
cw.set_input(A, 'Puff', sa * 0.05)
cw.set_input(A, 'Fan', 7.5)                                  # not a length: copied as it is
for o_ in list(bpy.data.objects):
    bpy.data.objects.remove(o_)
small = cube('Small', 0.4)
r, m = lasso([(484, 484), (516, 484), (516, 516), (484, 516)])
B = C.active_object
sb = B['mch_wrinkle_size']
check('big then small panel: sizes differ a lot', sa > 8 * sb, (round(sa, 3), round(sb, 4)))
check('remembered lengths scaled to the new panel (Pinch Length, Puff)',
      abs(cw.get_input(B, 'Pinch Length') - sb * 0.31) < sb * 1e-3 and abs(cw.get_input(B, 'Puff') - sb * 0.05) < sb * 1e-3,
      (cw.get_input(B, 'Pinch Length'), sb * 0.31))
check('non-length values copied exactly (Fan)', abs(cw.get_input(B, 'Fan') - 7.5) < 1e-6)
co_b = [B.matrix_world @ v.co for v in B.evaluated_get(C.evaluated_depsgraph_get()).data.vertices]
ext = max((c - co_b[0]).length for c in co_b)
check('the small panel stays small (no shards)', ext < 0.4 * 2.0, round(ext, 3))
bpy.ops.mch.wrinkle_preset_save(name='BigPreset')
# a preset saved on the small panel B, loaded onto a big panel: lengths scaled up, not 1:1
cw.set_input(B, 'Puff', sb * 0.04)
bpy.ops.mch.wrinkle_preset_save(name='SmallPreset')
for o_ in list(bpy.data.objects):
    bpy.data.objects.remove(o_)
big = cube('Big2', 40.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
D = C.active_object
sd = D['mch_wrinkle_size']
bpy.ops.mch.wrinkle_preset_load(name='SmallPreset')
check('preset from a small panel on a big one: Puff follows the size', abs(cw.get_input(D, 'Puff') - sd * 0.04) < sd * 1e-3,
      (cw.get_input(D, 'Puff'), sd * 0.04))
check('presets store the panel size of their lengths', cw.user_presets()['SmallPreset'].get('Puff' + cw.SIZE_TAG) == sb)
for n_ in ('BigPreset', 'SmallPreset'):
    bpy.ops.mch.wrinkle_preset_delete(name=n_)
# safety net: any length a new panel starts with stays inside its range for that size
for o_ in list(bpy.data.objects):
    bpy.data.objects.remove(o_)
small = cube('Small2', 0.4)
for k_, v_ in {'Puff': 5.0, 'Pinch Length': 40.0, 'Crumple': 2.0, '_thickness': 3.0}.items():
    last_used.remember('wrinkle', k_, v_)
    last_used.remember('wrinkle', k_ + cw.SIZE_TAG, 0.45)          # as if set on a panel this size
r, m = lasso([(484, 484), (516, 484), (516, 516), (484, 516)])
E2 = C.active_object
se = E2['mch_wrinkle_size']
check('absurd remembered lengths are clamped on a new panel (Puff, Fold Length, Crumple, thickness)',
      cw.get_input(E2, 'Puff') <= 0.3 * se + 1e-9 and cw.get_input(E2, 'Pinch Length') <= 2.0 * se + 1e-9 and
      cw.get_input(E2, 'Crumple') <= 0.05 * se + 1e-9 and E2.modifiers[cw.MOD_SHELL].thickness <= 0.05 * se + 1e-9,
      (cw.get_input(E2, 'Puff'), cw.get_input(E2, 'Pinch Length'), E2.modifiers[cw.MOD_SHELL].thickness, se))
co_e = [E2.matrix_world @ v.co for v in E2.evaluated_get(C.evaluated_depsgraph_get()).data.vertices]
check('... and the panel stays small', max((c - co_e[0]).length for c in co_e) < 0.8)
last_used.forget('wrinkle')
check('Billow: lower preset default, an old absolute Billow is dropped',
      cw.PRESETS['DRAPE']['Billow'] <= 0.02 and cw.recalled({'Billow': 0.5, 'Billow Size': 0.01}, 0.3) == {})
from mecha_lab import cloth_sim as cs
check('Cloth Plate and Panel Cloth are the 0.23.9 ones (no Center Calm / membrane / Panel Cloth sliders)',
      'Center Calm' not in cw.INPUT_NAMES and not hasattr(cw, 'EDGE_SMOOTH') and not hasattr(cs, 'scene_overrides'))
vals = cw.recalled({'Puff': 9.0, 'Fan': 3.0}, 0.3)
check('a length remembered without its size (old file) is dropped, others kept', vals == {'Fan': 3.0}, vals)

# 3. Space: no big tool menu any more; Space held while drawing moves the outline
kc = C.window_manager.keyconfigs.addon
check('Space no longer opens the tool menu', kc is None or not any(
    ki.idname == 'mch.space_tools' for km in kc.keymaps for ki in km.keymap_items))
ctx, op = Ctx(), Op()
pts = [(330, 330), (670, 330), (680, 660)]
op.invoke(ctx, E('LEFTMOUSE', 'PRESS', *pts[0]))
op.modal(ctx, E('LEFTMOUSE', 'RELEASE', *pts[0]))
for x, y in pts[1:]:
    op.modal(ctx, E('LEFTMOUSE', 'PRESS', x, y))
    op.modal(ctx, E('LEFTMOUSE', 'RELEASE', x, y))
before = [tuple(p) for p in op.pts]
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 680, 660))
op.modal(ctx, E('SPACE', 'PRESS', 680, 660))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 700, 640))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 720, 610))
r_sp = op.modal(ctx, E('SPACE', 'RELEASE', 720, 610))
after = [tuple(p) for p in op.pts]
check('Space + mouse move shifts every point by the mouse motion (stroke still running)',
      len(after) == len(before) and all(abs(a[0] - b[0] - 40) < 1e-6 and abs(a[1] - b[1] + 50) < 1e-6
                                        for a, b in zip(after, before)) and 'RUNNING_MODAL' in r_sp, (before, after))
op.modal(ctx, E('MOUSEMOVE', 'NOTHING', 760, 600))
check('after Space is released the mouse no longer moves the outline', [tuple(p) for p in op.pts] == after)
op.modal(ctx, E('ESC'))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
