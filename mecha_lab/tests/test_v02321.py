"""0.23.21 every tool HUD only while its own tool is chosen (like the Mirror buttons)."""
import sys

_src = open(__file__.replace('test_v02321.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, tool_state as ts, armor_plate as ap, curve_tube as ct, robot_base as rb
from mecha_lab import random_panels as rp, creature_shell as cs
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
b = cube('B', 4.0)
r, m = lasso([(330, 330), (670, 330), (680, 660), (320, 670)])
check('Cloth Plate HUD shown in the Cloth Plate tool', cw.MCH_GGT_wrinkle_hud.poll(C))
S.mch_settings.mch_active_tool = 'CUT'
check('... hidden after switching to Cut (the panel stays)', not cw.MCH_GGT_wrinkle_hud.poll(C) and cw.active_wrinkle(C) is not None)
check('the other HUDs follow their own tools', ts.hud_for(C, {'CUT'}) and not ts.hud_for(C, {'PLATE'}) and
      not ts.hud_for(C, {'TUBE'}) and not ts.hud_for(C, {'BASE'}))
src = {m_.__name__: open(m_.__file__).read() for m_ in (ap, ct, rb, rp, cs)}
# every gated HUD poll really runs (a missing import would only fail in Blender)
for klass in (ap.MCH_GGT_plate_hud, rp.MCH_GGT_random_hud, cs.MCH_GGT_shell_hud, ct.MCH_GGT_tube_points,
              ct.MCH_GGT_tube_bar, rb.MCH_GGT_robot_hud, cw.MCH_GGT_wrinkle_hud):
    try:
        klass.poll(C)
        ok_ = True
    except Exception as ex:
        ok_ = False
        print('poll error', klass.__name__, ex)
    check(f'{klass.__name__}.poll runs', ok_)
check('Armor Plate / Random Panels / Creature Shell / Tube / Robot HUD polls check their tool',
      "hud_for(context, {'PLATE'})" in src['mecha_lab.armor_plate'] and "hud_for(context, {'PLATE'})" in src['mecha_lab.random_panels']
      and "hud_for(context, {'PLATE'})" in src['mecha_lab.creature_shell'] and
      src['mecha_lab.curve_tube'].count("hud_for(context, {'TUBE'})") >= 2 and "_ts.hud_for(context, {'BASE'})" in src['mecha_lab.robot_base'])
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
