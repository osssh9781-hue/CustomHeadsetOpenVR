"""0.24.95 (user: "지브러시 탭에 클레이 빌드업 있잖아, 지브러시에서는 ㄹㅇ 빌드업이 돼서 계속 올라오는데 블렌더는 안 그래서
설정 한번 만져 주라") ClayBuildup (Blender Clay Strips) builds up: Accu on (going over the same place again in one
stroke piles up - off, a stroke reaches its height once and stops), the clay plane higher (0.15 -> 0.3: each pass
adds about the same again instead of levelling off), strength 0.55 -> 0.4 (the first pass about as before).
Measured in a real window (tests/gui/claybuildup_real_window.py, one stroke back and forth, 40 px brush on a plane):
1 / 3 / 6 passes 7.9 / 21 / 36 mm, was 6.5 / 9.6 / 9.9 mm.  A brush tuned by an older version gets the new values
only where it still has the old ones (a value you set stays)."""
from _harness import bpy, check, fresh, sphere, summary

import mecha_lab
from mecha_lab import zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context
ob = sphere('S')
C.view_layer.objects.active = ob
ob.select_set(True)
bpy.ops.object.mode_set(mode='SCULPT')
zb = C.scene.mch_zb

msg = zs.activate(C, 'ClayBuildup')
b = zs.brush(C)
check('ClayBuildup: Accu on, clay plane 0.3, strength 0.4 (first use in a file)',
      msg == '' and b.use_accumulate and abs(b.plane_offset - 0.3) < 1e-6 and abs(b.strength - 0.4) < 1e-6
      and b.get(zs.TUNED_KEY) == zs.TUNE_VERSION, (msg, b.use_accumulate, b.plane_offset, b.strength))
check('... the Accu switch on the left shelf shows it on', zb.accu)
zs.activate(C, 'Standard')
check('Standard keeps Accu off (a stroke does not pile up on itself)', not zs.brush(C).use_accumulate and not zb.accu)

# a brush tuned by the older version (0.55 / Accu off / plane 0.15), untouched: the new values
zs.activate(C, 'ClayBuildup')
b = zs.brush(C)
b.strength, b.use_accumulate, b.plane_offset = 0.55, False, 0.15
b[zs.TUNED_KEY] = 1
changed = zs.tune(b, 'ClayBuildup')
check('A ClayBuildup tuned by the older version (its old defaults): upgraded to build up',
      changed and b.use_accumulate and abs(b.plane_offset - 0.3) < 1e-6 and abs(b.strength - 0.4) < 1e-6
      and b.get(zs.TUNED_KEY) == zs.TUNE_VERSION)
# ... the same, but the user had set the strength: that stays
b.strength, b.use_accumulate, b.plane_offset = 0.7, False, 0.15
b[zs.TUNED_KEY] = 1
zs.tune(b, 'ClayBuildup')
check('... a strength you set stays (only the old defaults change)', abs(b.strength - 0.7) < 1e-6
      and b.use_accumulate and abs(b.plane_offset - 0.3) < 1e-6)
b.strength = 0.66
b.use_accumulate = False
zs.activate(C, 'Standard')
zs.activate(C, 'ClayBuildup')
check('... and changes made later are kept (not tuned again; Accu off by hand stays off)',
      abs(zs.brush(C).strength - 0.66) < 1e-6 and not zs.brush(C).use_accumulate)
summary()
