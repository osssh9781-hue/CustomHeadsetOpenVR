"""0.24.192 (user: "플레이트 디테일에 아머플레이트 릿지 같은 거랑 면 위를 지나는 엣지 같은 거 오가닉하게 넣을 수 있는 옵션이랑 프리셋,
강도 조절 가능하게" / "그리블이랑 스케일 둘 다 왜 셀렉트랑 오토 이런 거 다 빠져 있어?" / "왜 실시간으로 내가 선택한 메쉬 바뀌는 거
없앴어?"): Plate Detail 4's Ridges / Edges across the face (six presets, Line Height = the strength); the line tools
honour Targets (Auto / Selected / Active); ticking a part in the list changes the selected line at once."""
import json
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, greeble_line as gl, plate_detail as pd, plate_rough as pr, \
    target_rules as tr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
NEW = ['RIDGED', 'ARMORRIDGE', 'SEGMENTS', 'SCUTES', 'CRESTNET', 'GROOVED']
check('six line presets, each with ridges or edges on; the older presets have none',
      all(p in pr.PRESET_IDS for p in NEW)
      and all(abs(pr.preset_values(p)['r_ridges']) + abs(pr.preset_values(p)['r_edges']) > 0 for p in NEW)
      and all(pr.preset_values(p)['r_ridges'] == 0 and pr.preset_values(p)['r_edges'] == 0
              for p in pr.PRESET_IDS if p not in NEW))
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
bpy.ops.mesh.primitive_plane_add(size=4.0)
slab = C.active_object
slab.select_set(False)
C.view_layer.objects.active = None
bpy.ops.mch.pdetail_rough_preset(preset='RIDGED')
pd.perform(C, [[(500 + 110 * math.cos(a), 500 + 90 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48, endpoint=False)]],
           TOP, 'DETAIL4')
plate = next(o for o in S.objects if pd.is_detail(o))
p = plate.mch_pdetail


def heights():
    C.view_layer.update()
    me = plate.evaluated_get(C.evaluated_depsgraph_get()).data
    z = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', z)
    return z.reshape(-1, 3)[:, 2].copy()


z1 = heights()
h0 = p.r_line_height
p.r_line_height = h0 * 2.0
z2 = heights()
p.r_ridges, p.r_edges = 0.0, 0.0
z0 = heights()
check(f'Ridged Shell on a plate: the lines raise the face (top {z1.max():.4f} against {z0.max():.4f} without), '
      f'Line Height x2 raises it more ({z2.max():.4f})', len(z0) == len(z1) and z1.max() > z0.max() + 0.3 * h0
      and z2.max() > z1.max() + 0.3 * h0)

# the line tools and the Targets row
check('Greeble / Scale / Feather Line show the Targets row', {'GREEBLE', 'CGREEBLE', 'FGREEBLE'} <= tr.TARGET_ONLY)
for o in list(S.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_cube_add(size=2.0)
a = C.active_object
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(5, 0, 0))
b = C.active_object
st = gl.settings(S, 'CREATURE')
bpy.ops.mch.greeble_parts(action='STARTER', kind='CREATURE', which='SCALES')
parts = gl.picked(st)
pts = np.array([(x, 0.0, 1.0) for x in np.linspace(-0.8, 0.8, 40)])
nrm = np.array([(0.0, 0.0, 1.0)] * 40)
line = gl.new_line(C, a, pts, nrm, parts, st, 'CREATURE')
n5 = gl.rebuild(line, C)
for o in S.objects:
    o.select_set(False)
line.select_set(True)
C.view_layer.objects.active = line
used = json.loads(line.mch_greeble_line.parts_json)
bpy.ops.mch.greeble_parts(action='TOGGLE', kind='CREATURE', index=0)
now = json.loads(line.mch_greeble_line.parts_json)
check(f'a part unticked in the list: the selected line changes at once ({len(used)} -> {len(now)} parts)',
      len(used) == 5 and len(now) == 4 and used[0] not in now)
bpy.ops.mch.greeble_parts(action='TOGGLE', kind='CREATURE', index=0)
check('... and ticked again: back in the line', len(json.loads(line.mch_greeble_line.parts_json)) == 5)
S.mch_cut.targets = 'SELECTED'
names = tr.allowed(C)
check('Targets = Selected with only the line selected: the line allowed, and it lies on its mesh (the pick adds it); '
      'the other cube is left out', names is not None and line.name in names and line.parent == a
      and b.name not in names)
summary()
