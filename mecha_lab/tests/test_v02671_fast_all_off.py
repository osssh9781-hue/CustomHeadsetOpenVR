"""0.24.271 (user: "패스트 뷰포트 아예 끄는 것도 만들어 줘"): All Speed-Ups Off - Fast Viewport in every scene, Light
Copies and the Single Pass anti-aliasing off at once, every value back; the button only while something is on."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_view as fv, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
ps = C.preferences.system
aa0 = ps.viewport_aa
S.cycles.preview_samples = 1024
pix0 = S.render.preview_pixel_size
check('nothing on: no All Off button needed', not fv.anything_on(C) or aa0 == fv.AA_FAST)
fv.apply(C)
S2 = bpy.data.scenes.new('Other')
win = C.window_manager.windows[0] if C.window_manager.windows else None
with C.temp_override(scene=S2):
    fv.apply(C)
if aa0 != fv.AA_FAST:
    fv.aa_toggle(C)
check('Fast Viewport in two scenes + Single Pass AA: on', fv.on(S) and fv.on(S2) and ps.viewport_aa == fv.AA_FAST
      and S.cycles.preview_samples == 64)
C.window_manager.mch_side_page = 'HDRI'
sp.FOLDED.discard('MATERIAL:viewport')
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
check('the Render page shows "All Speed-Ups Off"', 'All Speed-Ups Off (normal viewport)' in [getattr(i, 'label', '') for i in items])
r = bpy.ops.mch.fast_all_off()
check('All Speed-Ups Off: Fast off in both scenes, the values back, AA back',
      r == {'FINISHED'} and not fv.on(S) and not fv.on(S2) and S.cycles.preview_samples == 1024
      and S.render.preview_pixel_size == pix0 and ps.viewport_aa == (aa0 if aa0 != fv.AA_FAST else '8'))
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
check('... and the button is gone (nothing on)', 'All Speed-Ups Off (normal viewport)' not in [getattr(i, 'label', '') for i in items])
ps.viewport_aa = aa0
summary()
