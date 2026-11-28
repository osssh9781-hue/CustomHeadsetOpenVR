"""0.24.354 Retopo + Bake: Solo (user: "리토포 탭에 내가 선택한 리토포 메쉬만 남겨서 솔로 모드처럼 하이폴이랑 리토포만
남기고 다른 건 눈 감게"): only the selected low and its high showing, every other object hidden; again: all back
exactly as it was (what was hidden before stays hidden)."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import retopo_bake as rb

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(segments=64, ring_count=32); high = C.active_object; high.name = 'Head'
bpy.ops.mesh.primitive_cube_add(location=(4, 0, 0)); other = C.active_object; other.name = 'Other'
bpy.ops.mesh.primitive_cone_add(location=(-4, 0, 0)); was_hidden = C.active_object; was_hidden.name = 'WasHidden'
was_hidden.hide_set(True)
bpy.ops.mesh.primitive_torus_add(location=(0, 4, 0)); h2 = C.active_object; h2.name = 'Ring'
for o in S.objects:
    o.select_set(False)
high.select_set(True); C.view_layer.objects.active = high
S.mch_rb_method, S.mch_rb_faces = 'DECIMATE', 500
bpy.ops.mch.retopo_make()
low = C.active_object
check('a low made, its high hidden (as Retopo does)', low.name == 'Head_Low' and high.hide_get())
r = bpy.ops.mch.retopo_solo()
vis = sorted(o.name for o in C.view_layer.objects if o.type == 'MESH' and not o.hide_get())
check(f'Solo: only the low and its high showing ({vis})', r == {'FINISHED'} and vis == ['Head', 'Head_Low'])
check('Solo is on (the button shows it)', rb.solo_on(C))
r = bpy.ops.mch.retopo_solo()
vis = sorted(o.name for o in C.view_layer.objects if o.type == 'MESH' and not o.hide_get())
check(f'Solo off: all back as it was ({vis}) - the high hidden again, the one hidden before still hidden',
      r == {'FINISHED'} and vis == ['Head_Low', 'Other', 'Ring'] and not rb.solo_on(C))
# with nothing selected: a warning, nothing hidden
for o in S.objects:
    o.select_set(False)
C.view_layer.objects.active = None
check('nothing selected: Solo does nothing', bpy.ops.mch.retopo_solo() == {'CANCELLED'}
      and not other.hide_get())
summary()
