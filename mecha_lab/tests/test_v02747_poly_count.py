"""0.24.347 (user: "지브러시로 바꾸는 탭 있는 쪽 아래에 선택한 오브젝트 폴리곤 수 좀 써 줘"): the MECHA | ZBRUSH | PAINT
card ends with POLY - the selected meshes' faces / points as shown (modifiers on), and how many objects."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zb_ui

fresh()
mecha_lab.register()
C = bpy.context
bpy.ops.mesh.primitive_cube_add()
cube = C.active_object
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, location=(3, 0, 0))
sph = C.active_object
for o in C.scene.objects:
    o.select_set(False)
cube.select_set(True)
C.view_layer.objects.active = cube
C.view_layer.update()
check(f'one cube selected: "{zb_ui.poly_text(C)}"', zb_ui.poly_text(C) == '6 faces · 8 verts')
sph.select_set(True)
txt = zb_ui.poly_text(C)
check(f'cube + sphere: "{txt}" (6 + 512 faces, 2 objects)', txt == '518 faces · 490 verts · 2 obj')
m = cube.modifiers.new('S', 'SUBSURF')
m.levels = 2
C.view_layer.update()
txt = zb_ui.poly_text(C)
check(f'a Subdivision on the cube: counted as shown ("{txt}")', txt.startswith('608 faces'))
items = zb_ui.corner_items(C, 1600, 900, 1.0)
labels = [i.label for i in items]
x0, y0, w, h = zb_ui.corner_box(C, 1600, 900, 1.0)
inside = all(y0 - 1 <= i.y <= y0 + h + 1 for i in items)
check(f'the card has the POLY row with the count, inside the card ({labels[-3:]})', 'POLY' in labels
      and txt in labels and inside)
for o in C.scene.objects:
    o.select_set(False)
C.view_layer.objects.active = None
check('nothing selected: says so', zb_ui.poly_text(C) == 'nothing selected')
summary()
