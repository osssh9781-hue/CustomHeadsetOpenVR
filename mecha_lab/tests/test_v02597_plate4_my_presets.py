"""0.24.180 (user: "디테일 플레이트 4에 프리셋 저장도 만들어 줘"): Plate Detail 4 - the selected rough plate's values
saved under a name in My Presets (a test file, never the user's), put back on another plate of another size (the
lengths as shares of the size), on the next one when none is selected; deleted; the window shows them."""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, my_presets as mp, plate_detail as pd, plate_rough as pr  # noqa: E402

fresh()
mecha_lab.register()
tmp = tempfile.mkdtemp()
mp.PATH[0] = os.path.join(tmp, 'my_presets.json')
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def blob(cx, cy, rx, ry, n=64, k=3, wob=0.1):
    return [[(500 + (cx + rx * math.cos(a) * (1 + wob * math.sin(k * a))) * 100,
              500 + (cy + ry * math.sin(a)) * 100) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


bpy.ops.mesh.primitive_plane_add(size=8.0)
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=40)
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.mch.pdetail_rough_preset(preset='STONE')
pd.perform(C, blob(-1.5, 0, 1.0, 0.8), TOP, 'DETAIL4')
a = C.active_object
check('a rough plate made', pd.is_detail(a) and a.mch_pdetail.kind == 'ROUGH')
p = a.mch_pdetail
p.r_cracks, p.r_pits, p.r_chips = 0.77, -0.4, 0.33
p.r_strength = p.size * 0.031
p.r_profile = 'DOME'
r = bpy.ops.mch.pdetail_my_save('EXEC_DEFAULT', name='My Rock')
saved = mp.load_all().get(pd.MY_KIND, {}).get('My Rock')
check(f'Save Preset ({r}): "My Rock" in My Presets ({len(saved or {})} values; Strength as a share of the size '
      f'{(saved or {}).get("r_strength", 0):.3f})', r == {'FINISHED'} and saved is not None
      and abs(saved['r_strength'] - 0.031) < 1e-6 and saved['r_cracks'] == p.r_cracks and saved['r_profile'] == 'DOME'
      and os.path.isfile(mp.PATH[0]))
# another plate, another preset and size: My Rock put on it
bpy.ops.mch.pdetail_rough_preset(preset='CONCRETE')
pd.perform(C, blob(1.8, 0, 0.6, 0.5), TOP, 'DETAIL4')
b = C.active_object
q = b.mch_pdetail
before = (q.r_cracks, q.r_profile)
r = bpy.ops.mch.pdetail_my_apply(name='My Rock')
check(f'My Rock on a smaller plate ({r}): its mix (Cracks {before[0]:.2f} -> {q.r_cracks:.2f}, Pits {q.r_pits:.2f}, Chips '
      f'{q.r_chips:.2f}, Edge {before[1]} -> {q.r_profile}), Strength the same share of its own size '
      f'({q.r_strength / q.size:.3f})', r == {'FINISHED'} and abs(q.r_cracks - 0.77) < 1e-6 and abs(q.r_pits + 0.4) < 1e-6
      and q.r_profile == 'DOME' and abs(q.r_strength / q.size - 0.031) < 1e-5 and abs(q.size - p.size) > 0.1)
# none selected: the next one gets it
for o in C.selected_objects:
    o.select_set(False)
C.view_layer.objects.active = None
bpy.ops.mch.pdetail_rough_preset(preset='CONCRETE')
bpy.ops.mch.pdetail_my_apply(name='My Rock')
pd.perform(C, blob(0, 2.2, 0.7, 0.6), TOP, 'DETAIL4')
c = C.active_object.mch_pdetail
check(f'nothing selected: the next plate drawn gets it (Cracks {c.r_cracks:.2f}, Edge {c.r_profile})',
      abs(c.r_cracks - 0.77) < 1e-6 and c.r_profile == 'DOME')
# the window shows them
from mecha_lab import panel_capture  # noqa: E402,F401
lay = type('L', (), {})


class Rec:
    def __init__(self):
        self.ops = []

    def __getattr__(self, k):
        return lambda *a_, **kw: (self.ops.append((a_[0] if a_ else None, kw.get('text'))) or self) if k == 'operator' \
            else self

    def label(self, **kw):
        self.ops.append(('label', kw.get('text')))


rec = Rec()
pd._draw_rough_presets(rec, 'STONE')
texts = [t for _o, t in rec.ops]
check(f'the window: My Presets under the ten - "My Rock", Save Preset, Delete ({texts[-4:]})',
      'My Rock' in texts and 'Save Preset' in texts and 'Delete' in texts)
r = bpy.ops.mch.pdetail_my_delete('EXEC_DEFAULT', name='My Rock')
check(f'Delete ({r}): gone', r == {'FINISHED'} and 'My Rock' not in mp.names(pd.MY_KIND))
summary()
