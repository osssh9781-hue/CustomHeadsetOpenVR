"""0.24.95 Clean Materials (user: "중간중간 재질이 중복이 있어서 하얀색으로 안 칠해지는 거 매번 지워 주는 거 귀찮으니까 오브젝트
메테리얼 클린 버튼 우클릭 팝업에 만들어 줘, 그리고 내가 선택한 거 한 번에 지울 수 있게"):

* a part with leftover slots (the cutter's material a cut brought, a copy, the same material twice, an empty slot):
  every face on the material of the active slot (the one just applied), the other slots gone - one material, so
  the next material applied covers the whole part
* the part's Split Zone materials stay with their faces
* every selected part at once; a mesh shared by linked copies once; Unused Only: only empty / unused / doubled slots
* in the RMB popups (the Mecha menu's Shading row, the Blender-style popup, the ZBrush cursor menu)"""
import numpy as np
from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import actions_menu as am, mecha_menu as mm

fresh()
mecha_lab.register()
C = bpy.context


def mat(name, col=(1, 1, 1, 1)):
    m = bpy.data.materials.new(name)
    m.diffuse_color = col
    return m


white = mat('White')
cutter = mat('MCH Cutter', (1, 0, 0, 1))
copy = mat('White.001')
zone = mat('White Zone', (0, 0, 1, 1))
zone.mch_zone_parent = white


def part(name, loc):
    ob = cube(name, size=1.0, loc=loc)
    me = ob.data
    for m in (white, cutter, white, copy, None):
        me.materials.append(m)
    idx = np.array([0, 1, 2, 3, 1, 0], np.int32)          # (6 faces: on White, the cutter's, White again, the copy)
    me.polygons.foreach_set('material_index', idx)
    return ob


a = part('A', (0, 0, 0))
b = part('B', (3, 0, 0))
b.data.materials.append(zone)                             # (a Split Zone of White on B: face 5)
b.data.polygons[5].material_index = 5
other = part('NotSelected', (6, 0, 0))
for o in C.selected_objects:
    o.select_set(False)
a.select_set(True)
b.select_set(True)
C.view_layer.objects.active = a
a.active_material_index = 0
b.active_material_index = 0
r = bpy.ops.mch.clean_materials()


def state(ob):
    idx = np.empty(len(ob.data.polygons), np.int32)
    ob.data.polygons.foreach_get('material_index', idx)
    return [m.name if m else None for m in ob.data.materials], idx.tolist()


sa, sb, so = state(a), state(b), state(other)
check('Clean Materials on two selected parts at once: one material (the active slot\'s White) on every face, the '
      'cutter\'s, the copy, the doubled and the empty slot gone', r == {'FINISHED'} and sa == (['White'], [0] * 6),
      sa)
check('... a Split Zone material of White kept with its face', sb[0] == ['White', 'White Zone']
      and sb[1] == [0, 0, 0, 0, 0, 1], sb)
check('... a part not selected: untouched', len(so[0]) == 5, so)

c = part('C', (9, 0, 0))
c.active_material_index = 1                               # (the material just applied went into slot 2: the keeper)
for o in C.selected_objects:
    o.select_set(False)
c.select_set(True)
C.view_layer.objects.active = c
bpy.ops.mch.clean_materials()
check('... the keeper is the active slot\'s material (the one just applied)', state(c) == (['MCH Cutter'], [0] * 6),
      state(c))

d = part('D', (12, 0, 0))
n = am.clean_materials(d, 'UNUSED')
sd = state(d)
check('Unused Only: the doubled White merged, the empty slot gone, the used materials kept (faces on the same '
      'materials as before)', n == 2 and sd[0] == ['White', 'MCH Cutter', 'White.001']
      and sd[1] == [0, 1, 0, 2, 1, 0], (n, sd))

e = part('E', (15, 0, 0))
e2 = bpy.data.objects.new('E twin', e.data)
C.scene.collection.objects.link(e2)
for o in C.selected_objects:
    o.select_set(False)
e.select_set(True)
e2.select_set(True)
C.view_layer.objects.active = e
r = bpy.ops.mch.clean_materials()
check('A mesh shared by linked copies: cleaned once, both show one material', state(e)[0] == ['White']
      and state(e2)[0] == ['White'], state(e2))
check('... a clean part again: nothing to do', am.clean_materials(a) == 0)

labels = [it[0] for _sec, row in mm.ACTIONS for it in row]
from mecha_lab import zb_ui  # noqa: E402
import inspect  # noqa: E402
check('In the RMB popups: the Mecha menu (the Resolution row, a free slot), the Blender-style popup and the ZBrush cursor menu',
      'Clean Materials' in labels and 'mch.clean_materials' in inspect.getsource(am.MCH_PT_actions_popup.draw)
      + inspect.getsource(am) and 'mch.clean_materials' in inspect.getsource(zb_ui), labels[-5:])
summary()
