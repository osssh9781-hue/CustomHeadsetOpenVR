"""0.24.273 (user: "바닥은 Z 축 조정할 수 있게 해 주고 배경 이미지 근처로 위치 옮겨 주고 구다리마다 잘 보이게 색 구별해 주고"):
Floor Height moves the floor up / down from under the parts (Fit keeps it); the floor is its own section right after
Background (no longer inside Creature Light); every Render page section has its own coloured title."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import creature_light as cl, mech_shader_ui as mu, side_panel as sp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(location=(0, 0, 1))          # (the lowest point at z 0)
st = cl.settings(S)
bpy.ops.mch.creature_floor(kind='FADE')
fl = cl.floor_object(S)
check('the floor under the part (z 0)', fl is not None and abs(fl.location.z) < 1e-4)
st.floor_z = -0.25
check('Floor Height -0.25: the floor 0.25 lower', abs(fl.location.z + 0.25) < 1e-4)
bpy.ops.mch.creature_floor(kind='FIT')
check('Fit Floor to Model keeps the height', abs(fl.location.z + 0.25) < 1e-4)
st.floor_z = 0.0
check('back to 0: under the part again', abs(fl.location.z) < 1e-4)
C.window_manager.mch_side_page = 'HDRI'
for k in ('quick_render', 'creature_light', 'viewport', 'background_colour', 'floor', 'r_camera', 'r_hdri_turn'):
    sp.FOLDED.discard(f'MATERIAL:{k}')
sp.OPENED.add('MATERIAL:creature_light')
items, _h = sp.content(C, 'CUT', 0, 300, 1.0)
heads = [(i.label, str(i.icon)) for i in items if i.kind == 'shead']
order = [h[0] for h in heads]
check(f'the sections, each a coloured title ({order})', all(ic.startswith('big:') for _l, ic in heads) and len(heads) >= 9)
cols = [ic.split('|')[0] for _l, ic in heads]
check(f'neighbouring sections never the same colour ({cols})', all(a != b for a, b in zip(cols, cols[1:])))
labels = [getattr(i, 'label', '') for i in items]
bi, fi = order.index('BACKGROUND'), order.index('FLOOR')
check('the Floor section right after Background', fi == bi + 1)
ci = labels.index('CREATURE LIGHT')
nxt = min(j for j in range(ci + 1, len(items)) if items[j].kind == 'shead')
check('Creature Light no longer holds the floor buttons', 'No Floor' not in labels[ci:nxt] and 'No Floor' in labels
      and 'Floor Height' in labels)
summary()
