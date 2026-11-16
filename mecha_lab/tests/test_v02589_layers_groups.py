"""0.24.177 Layers panel (user: "그룹이든 레이어든 선택할 때 쉬프트 누르고 처음 꺼 마지막 꺼 선택하면 그 영역 선택되게, 컨트롤
누르면 빠지고", "그룹 된 거 내가 눈 감게 하면 내부에 메쉬들도 같이 눈 감겨서 하이드 되어야지", "왜 그룹은 뒤집기가 안 돼?"):
Shift: every row from the one clicked before to this one; Ctrl: this one added / taken out; a folder's eye hides / shows
its parts on their own eyes too (their rows' eyes closed with it); a part shown out of a folder hidden the old way
shows alone; Flip with a group picked: its parts flipped across the world (its handle moved across too)."""
import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import groups, layers_panel as lp  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def unselect():
    for o in C.selected_objects:
        o.select_set(False)


cubes = []
for i in range(3):
    bpy.ops.mesh.primitive_cone_add(radius1=0.3, depth=0.6, location=(1.0 + i, 0.5, 0.2 * i))
    cubes.append(C.active_object)
unselect()
for o in cubes[:2]:
    o.select_set(True)
C.view_layer.objects.active = cubes[0]
bpy.ops.mch.group()
h = next(o for o in S.objects if groups.is_group(o))
col = bpy.data.collections.new('Parts')
S.collection.children.link(col)
balls = []
for i in range(3):
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.3, location=(i, 3, 0))
    o = C.active_object
    for c in list(o.users_collection):
        c.objects.unlink(o)
    col.objects.link(o)
    balls.append(o)
unselect()
rows = lp.tree(C, lp.scan(C))
names = [(r[0].name, r[4]) for r in rows]
# a folder's eye
r1 = bpy.ops.mch.layer_eye(name='Parts', coll=True)
hid = [(o.name, o.hide_get(), lp._hidden(C, o)) for o in balls]
check(f'a folder\'s eye closed: its parts hidden on their own eyes too ({hid}), the folder shown hidden',
      r1 == {'FINISHED'} and all(x[1] and x[2] for x in hid) and lp._hidden(C, col))
bpy.ops.mch.layer_eye(name='Parts', coll=True)
check('opened again: its parts shown', all(not o.hide_get() and o.visible_get() for o in balls) and not lp._hidden(C, col))
lc = lp.layer_coll(C, col)
lc.hide_viewport = True                                    # (hidden the old way: the collection itself)
check('a folder hidden the old way: its parts\' rows show hidden too (their eyes closed)',
      all(lp._hidden(C, o) for o in balls))
bpy.ops.mch.layer_eye(name=balls[1].name)
check(f'one part\'s eye opened in it: that part shows, the others stay hidden ({[o.visible_get() for o in balls]})',
      balls[1].visible_get() and not balls[0].visible_get() and not balls[2].visible_get() and not lc.hide_viewport)
bpy.ops.mch.layer_eye(name='Parts', coll=True)
bpy.ops.mch.layer_eye(name='Parts', coll=True)
for o in balls:
    if not o.visible_get():
        o.hide_set(False)
# Shift: the rows between; Ctrl: in / out
rows = lp.tree(C, lp.scan(C))
order = [r[0].name for r in rows if r[4] == 'OBJ']
first, last = balls[0].name, balls[2].name
unselect()
bpy.ops.mch.layer_pick(name=first)
r2 = bpy.ops.mch.layer_pick(name=last, range=True)
sel = sorted(o.name for o in C.selected_objects)
check(f'a click on the first, Shift + click on the last: every row between selected ({sel})',
      r2 == {'FINISHED'} and sel == sorted(o.name for o in balls))
bpy.ops.mch.layer_pick(name=balls[1].name, extend=True)
sel2 = sorted(o.name for o in C.selected_objects)
check(f'Ctrl + click on one of them: taken out ({sel2})', sel2 == sorted([balls[0].name, balls[2].name]))
bpy.ops.mch.layer_pick(name=balls[1].name, extend=True)
check('Ctrl + click again: back in', balls[1].select_get())
unselect()
bpy.ops.mch.layer_pick(name=cubes[2].name)
bpy.ops.mch.layer_pick(name=balls[0].name, range=True)
i0, i1 = sorted((order.index(cubes[2].name), order.index(balls[0].name)))
between = set(order[i0:i1 + 1])
got = {o.name for o in C.selected_objects}
check(f'Shift across rows of another kind too: the rows between ({sorted(got)})', between <= got | {h.name})
# Flip with the group picked
unselect()
h.select_set(True)
C.view_layer.objects.active = h
before = {o.name: [tuple(o.matrix_world @ v.co) for v in o.data.vertices] for o in cubes[:2]}
hx = h.matrix_world.translation.x
ok_poll = bpy.ops.mch.flip_object.poll()
r3 = bpy.ops.mch.flip_object(axis='X')
after = {o.name: [tuple(o.matrix_world @ v.co) for v in o.data.vertices] for o in cubes[:2]}
mirrored = all(sorted((round(-x, 4), round(y, 4), round(z, 4)) for x, y, z in before[k])
               == sorted((round(x, 4), round(y, 4), round(z, 4)) for x, y, z in after[k]) for k in before)
check(f'Flip with the group picked (before: greyed out): its parts flipped across the world\'s X ({r3}), the handle '
      f'moved across ({hx:.3f} -> {h.matrix_world.translation.x:.3f}), no negative scale',
      ok_poll and r3 == {'FINISHED'} and mirrored and abs(h.matrix_world.translation.x + hx) < 1e-5
      and all(min(o.matrix_world.to_scale()) > 0 for o in cubes[:2]))
summary()
