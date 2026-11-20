"""0.24.275 (user: "렌더 탭이랑 메테리얼 쪽 컬러 피커가 마우스 치우면 바로 꺼져"): a colour clicked on the Render /
Mech / Creature / Simple page opens its picker inside the panel (Hue / Saturation / Value, Pick, Done) - nothing a
moved mouse can close; Done or the same colour again closes it; the bars change that colour."""
import colorsys

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import color_pick as cp, live_ref, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_cube_add()
C.window_manager.mch_side_page = 'HDRI'
sp.FOLDED.discard('MATERIAL:background_colour')


def items():
    out, _h = sp.content(C, 'CUT', 0, 300, 1.0)
    return out


its = items()
sw = next(i for i in its if i.kind == 'swatch' and i.label == 'Colour')
check('the swatch asks for the picker in the panel', tuple(sw.action) == ('color', 'inline'))
cp.inline_open(sw.ref, sw.prop)
its = items()
labels = [getattr(i, 'label', '') for i in its]
k = labels.index('Colour')
check(f'open: Hue / Saturation / Value, Pick and Done right under it ({labels[k + 1:k + 6]})',
      labels[k + 1:k + 6] == ['Hue', 'Saturation', 'Value', 'Pick (eyedropper)', 'Done'])
st = S.mch_bg if hasattr(S, 'mch_bg') else live_ref.resolve(sw.ref)
data = live_ref.resolve(sw.ref)
wm = C.window_manager
wm.mch_pick_v = 1.0; wm.mch_pick_s = 1.0; wm.mch_pick_h = 0.0
c = tuple(getattr(data, sw.prop))[:3]
check(f'the bars change that colour (Hue 0, full: red {tuple(round(x, 2) for x in c)})', c[0] > 0.9 and c[1] < 0.05 and c[2] < 0.05)
wm.mch_pick_h = 1 / 3
c = tuple(getattr(data, sw.prop))[:3]
check(f'Hue 1/3: green ({tuple(round(x, 2) for x in c)})', c[1] > 0.9 and c[0] < 0.05)
check('the bars read the colour back', abs(wm.mch_pick_h - 1 / 3) < 0.01 and abs(wm.mch_pick_s - 1) < 0.01)
bpy.ops.mch.color_inline_close()
check('Done closes it', 'Pick (eyedropper)' not in [getattr(i, 'label', '') for i in items()])
cp.inline_open(sw.ref, sw.prop); cp.inline_open(sw.ref, sw.prop)
check('the same colour clicked again closes it too', 'Pick (eyedropper)' not in [getattr(i, 'label', '') for i in items()])
# Simple page: the Base Color swatch opens inline too
bpy.ops.mch.simple_material_new()
C.window_manager.mch_side_page = 'SIMPLE'
its = items()
bc = next(i for i in its if i.kind == 'swatch')
cp.inline_open(bc.ref, bc.prop)
check('Simple page: its colour opens in the panel too', 'Pick (eyedropper)' in [getattr(i, 'label', '') for i in items()])
cp.inline_close()
# Mech / Creature pages: their colours open in the panel too
for page in ('MATERIAL', 'CREATURE'):
    C.window_manager.mch_side_page = page
    for kk in list(sp.FOLDED):
        sp.FOLDED.discard(kk)
    its = items()
    sws = [i for i in its if i.kind == 'swatch']
    if not sws:
        try:
            bpy.ops.mch.mech_shader_apply() if page == 'MATERIAL' else bpy.ops.mch.creature_apply()
        except Exception as ex:
            print('apply', ex)
        its = items()
        sws = [i for i in its if i.kind == 'swatch']
    print('PAGE', page, len(sws), [i.label for i in sws][:6])
    if sws:
        cp.inline_open(sws[0].ref, sws[0].prop)
        check(f'{page} page: its colour "{sws[0].label}" opens in the panel', 'Pick (eyedropper)' in [getattr(i, 'label', '') for i in items()])
        cp.inline_close()
summary()
