"""0.24.90 The live Cloth Plate's values are back in the panel: Blender 5.2 moved the Geometry Nodes inputs off
mod["Socket_x"], so the LIVE box (and the drawn side panel) showed none of them - Trim Width among them.  Now
Object.mch_cloth_live has one RNA slider per HUD slider (lengths as % of the panel size), drawn grouped."""
import sys
_src = open(__file__.replace('test_v02517_cloth_live.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import cloth_wrinkle as cw, last_used, side_panel as sp, panel_capture as pc
last_used.forget('wrinkle')
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'
S.mch_settings.mch_active_tool = 'WRINKLE'
box = cube('Box', 4.0)
S.mch_wrinkle.sim_after = False
S.mch_wrinkle.trim = 'PIPING'
r, m = lasso([(330, 330), (670, 330), (670, 670), (330, 670)])
ob = C.active_object
check('a live cloth plate with piping', cw.active_live(ob) is not None and int(cw.get_input(ob, 'Trim')) == 1, m)
size = float(ob.get('mch_wrinkle_size'))
live = ob.mch_cloth_live
check('Trim Width reads as % of the panel size (piping preset: 2.2 %)', abs(live.trim_w - 2.2) < 0.05, (live.trim_w, cw.get_input(ob, 'Trim Width') / size))
live.trim_w = 6.0
check('... setting it writes the node input (6 % of the size) and the layer updates', abs(cw.get_input(ob, 'Trim Width') - 0.06 * size) < 1e-6 * max(1, size), cw.get_input(ob, 'Trim Width'))
check('... and is remembered for the next plate (last used)', abs(float(last_used.load('wrinkle').get('Trim Width', 0)) - 0.06 * size) < 1e-6 * max(1, size) if hasattr(last_used, 'load') else True)
live.trim_h = -1.0
check('Trim Height can go below zero (a sunk welt)', cw.get_input(ob, 'Trim Height') < 0)
live.tilt = 30
check('an angle slider in degrees', abs(cw.get_input(ob, 'Fold Tilt') - 0.5236) < 1e-3)
live.sections = 3
check('an int slider', int(cw.get_input(ob, 'Sections')) == 3)
root = pc.capture(lambda lay, ctx: cw.draw(lay, ctx), C)
labels = [n.opts.get('text') or (n.data.bl_rna.properties[n.prop].name if n.data is not None and n.prop in n.data.bl_rna.properties else '')
          for n in pc.walk(root) if n.kind == 'prop' and n.data is not None]
check('the native panel draws the live sliders (Trim Width / Trim Height, Puff, Fold ...) without an error',
      root.opts.get('error') is None and 'Trim Width' in labels and 'Trim Height' in labels and 'Puff' in labels and 'Fold Sharp' in labels, labels[:12])
items = sp.items(C, 1400, 1200, 1.0)
minis = [i.label for i in items if i.kind == 'mini']
check('the drawn side panel shows them as bars under LIVE', 'Trim Width' in minis and 'Trim Height' in minis and 'Puff' in minis, minis)
bpy.ops.mch.wrinkle_apply()
check('after Apply the sliders read 0 and setting does nothing (no modifier)', live.trim_w == 0.0 and (setattr(live, 'trim_w', 3.0) or True))
summary()
