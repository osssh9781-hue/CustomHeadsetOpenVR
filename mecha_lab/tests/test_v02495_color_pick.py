"""0.24.95 The swatch colour picker (user: "컬러 피커에 휴 · 새츄레이션 · 밸류 다 넣어 주고 스포이드도 넣어 줘"):

* Hue / Saturation / Value bars (on the picker of every drawn swatch) read the swatch's colour as shown (a linear colour
  turned to display values) and write it back: Saturation 0 grey, Hue a turn round, Value darker; grey keeps the last
  hue (Saturation back up: the same colour again)
* Pick (the eyedropper): the colour of a screen picture round the clicked pixel, turned back to the swatch's linear
  colour (display 0.5 -> 0.214); with no window it is refused (nothing changed)
* the swatch popup draws the wheel, the three bars, the colour field and Pick"""
import colorsys
import inspect
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import color_pick as cp, ui_bars

fresh()
mecha_lab.register()
C = bpy.context
wm = C.window_manager

bpy.ops.mesh.primitive_cube_add()
bpy.ops.mch.mech_shader_apply(preset='PLASTIC_MATTE')
st = C.active_object.active_material.mch_mech
st.base_color = (0.6, 0.1, 0.05)                    # (linear)
ui_bars.EDIT[:] = [st, 'base_color']
disp = cp._to_display(tuple(st.base_color), True)
h0, s0, v0 = colorsys.rgb_to_hsv(*disp)
check('Hue / Saturation / Value read the swatch\'s colour as shown (linear -> display, then HSV)',
      abs(wm.mch_pick_h - h0) < 1e-4 and abs(wm.mch_pick_s - s0) < 1e-4 and abs(wm.mch_pick_v - v0) < 1e-4,
      (round(wm.mch_pick_h, 3), round(wm.mch_pick_s, 3), round(wm.mch_pick_v, 3)))
wm.mch_pick_s = 0.0
grey = tuple(st.base_color)
wm.mch_pick_s = s0
back = tuple(st.base_color)
check('Saturation 0: grey; back up: the same colour again (the hue kept while grey)',
      abs(grey[0] - grey[1]) < 1e-5 and abs(grey[1] - grey[2]) < 1e-5
      and np.allclose(back, (0.6, 0.1, 0.05), atol=1e-3), (np.round(grey, 4).tolist(), np.round(back, 4).tolist()))
wm.mch_pick_h = (h0 + 0.5) % 1.0
turned = tuple(st.base_color)
check('Hue half a turn: red -> cyan-ish (blue and green over red)', turned[2] > turned[0] and turned[1] > turned[0],
      np.round(turned, 3).tolist())
wm.mch_pick_h = h0
wm.mch_pick_v = v0 * 0.5
dark = tuple(st.base_color)
check('Value halved: darker (the same hue)', sum(dark) < sum((0.6, 0.1, 0.05)) * 0.5 and dark[0] > dark[2],
      np.round(dark, 3).tolist())
st.base_color = (0.6, 0.1, 0.05)

# the eyedropper's reading
p = os.path.join(tempfile.mkdtemp(), 'shot.png')
img = bpy.data.images.new('shot', 64, 32)
px = np.zeros((32, 64, 4), np.float32)
px[..., 3] = 1.0
px[:, 32:, :3] = (0.5, 0.25, 1.0)                    # (the right half: a colour as seen)
img.pixels.foreach_set(px.ravel())
img.filepath_raw = p
img.file_format = 'PNG'
img.save()
bpy.data.images.remove(img)
rgb = cp.sample(p, 48, 16)
check('Pick reads the screen picture round the clicked pixel', np.allclose(rgb, (0.5, 0.25, 1.0), atol=0.01),
      np.round(rgb, 3).tolist())
cp.set_display_colour(st, 'base_color', rgb)
check('... and gives the swatch that colour, turned back to linear (display 0.5 -> 0.214)',
      np.allclose(tuple(st.base_color), (0.214, 0.0508, 1.0), atol=0.01), np.round(tuple(st.base_color), 3).tolist())
before = tuple(st.base_color)
r = bpy.ops.mch.color_eyedrop('INVOKE_DEFAULT')
check('... with no window (background): not run (refused or passed on), nothing changed',
      r & {'CANCELLED', 'PASS_THROUGH'} and tuple(st.base_color) == before, r)
src = inspect.getsource(ui_bars.MCH_PT_ui_value.draw) + inspect.getsource(cp.draw)
check('The swatch popup: the wheel, Hue / Saturation / Value, the colour field and Pick',
      'color_pick.draw' in src and 'template_color_picker' in src and all(k in src for k in ('mch_pick_h', 'mch_pick_s',
                                                                                              'mch_pick_v'))
      and 'mch.color_eyedrop' in src)
summary()
