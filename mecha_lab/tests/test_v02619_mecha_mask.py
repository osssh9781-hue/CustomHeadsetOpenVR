"""0.24.200 (user: "메카랩에서 마스크 쓰게 해 줘, 클로스랑 익스트랙트 할 때" / "나는 변한 게 없다고 느끼지만 사실 스컬프 모드로
변환되게 하는 거지"): Paint Mask - Sculpt Mode under the MECHA LAB screen; Clear / Invert / Extract from there.
(The painting itself needs a real window: tests/gui/round200.)"""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bottom_bar as bb, mecha_mask as mm, zb_sculpt as zs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
real_tab = zs.mecha_tab
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32)
ball = C.active_object
check('before: Object Mode, nothing on', C.mode == 'OBJECT' and not mm.on(C))
r = bpy.ops.mch.mecha_mask(action='PAINT')
zs.mecha_tab = lambda c: True                      # (as in the MECHA LAB tab)
check('Paint Mask: really Sculpt Mode now, with the Mask brush - and the ZBrush screen / keys stay away '
      '(on() and mecha_sculpt() are off)', 'FINISHED' in r and C.mode == 'SCULPT' and mm.on(C) and not zs.on(C)
      and not zs.mecha_sculpt(C) and 'mask' in (zs.brush(C).name.lower() if zs.brush(C) else ''),
      zs.brush(C).name if zs.brush(C) else None)
import mecha_lab.tool_state as ts
real_ws = ts.is_mecha_workspace
ts.is_mecha_workspace = lambda w: True
check('... the Mecha bars keep drawing (ui_active is on in this Sculpt Mode)', bb.ui_active(C))
bpy.ops.mch.mecha_mask(action='PAINT')
check('Paint Mask again: off, back in Object Mode; a plain Sculpt Mode does not count as the Mecha screen',
      C.mode == 'OBJECT' and not mm.on(C))
bpy.ops.object.mode_set(mode='SCULPT')
check('(Sculpt Mode entered the usual way: the ZBrush screen as before, the Mecha bars off)',
      not bb.ui_active(C) and zs.mecha_sculpt(C))
bpy.ops.object.mode_set(mode='OBJECT')
co = np.array([v.co[:] for v in ball.data.vertices])
mm.set_values(C, ball, lambda v: (co[:, 2] > 0.4).astype(np.float32))
n_top = int(mm.values(ball).sum())
bpy.ops.mch.mecha_mask(action='PAINT')
bpy.ops.mch.mecha_mask(action='INVERT')
inv = int(mm.values(ball).sum()) if C.mode == 'OBJECT' else None
bpy.ops.object.mode_set(mode='OBJECT')
n_inv = int(mm.values(ball).sum())
mm.ON[0] = False
check(f'Invert while painting: the mask turned over ({n_top} -> {n_inv} of {len(co)} points), still painting after it',
      n_inv == len(co) - n_top and inv is None)
bpy.ops.mch.mecha_mask(action='INVERT')
C.scene.mch_zb.thick = 0.04
C.scene.mch_zb.extract_offset = 0.05
bpy.ops.mch.mecha_mask(action='PAINT')
r = bpy.ops.mch.mecha_mask(action='EXTRACT')
shell = next((o for o in bpy.data.objects if o.get(zs.EXTRACT_KEY)), None)
check('Extract from the painting: the masked cap as a new shell (Thick on its Solidify, Offset on its Displace), and '
      'back in Object Mode, painting off', 'FINISHED' in r and shell is not None and C.mode == 'OBJECT' and not mm.on(C)
      and any(m.type == 'SOLIDIFY' and abs(m.thickness - 0.04) < 1e-6 for m in shell.modifiers)
      and any(m.type == 'DISPLACE' and abs(m.strength - 0.05) < 1e-6 for m in shell.modifiers))
C.view_layer.objects.active = ball
bpy.ops.mch.mecha_mask(action='CLEAR')
check('Clear: no mask left', not mm.values(ball).any())
r = bpy.ops.mch.mecha_mask(action='EXTRACT')
check('Extract with no mask: a warning, nothing made', 'CANCELLED' in r and C.mode == 'OBJECT')
# any other Mecha button ends the painting first
from mecha_lab import ui_bars as ub
from mecha_lab.mecha_menu import Item
bpy.ops.mch.mecha_mask(action='PAINT')
ub.run(C, Item('seg', 0, 0, 10, 10, 'Cut', '', False, True, ('bar', 'CUT')))
check('another Mecha button while painting (the Cut tool): the painting ends first (Object Mode), then the tool is '
      'chosen', C.mode == 'OBJECT' and not mm.on(C) and ts.effective_tool(C) == 'CUT', ts.effective_tool(C))
ts.is_mecha_workspace = real_ws
zs.mecha_tab = real_tab
summary()
