"""0.24.199 (user: "지브러시에서 마스크하면 익스트랙트하는 거 구현되어 있나?" - yes, since 0.24.60 - / "익스트랙트도 오프셋 조정
가능하게 해 줘"): the ZBrush tab's Extract - the new shell's distance off the surface (Offset), live like Thick."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zb_sculpt as zs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
zb = C.scene.mch_zb
bpy.ops.mesh.primitive_uv_sphere_add(segments=48, ring_count=32, radius=1.0)
ball = C.active_object
co = np.array([v.co[:] for v in ball.data.vertices])
att = ball.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
att.data.foreach_set('value', (co[:, 2] > 0.4).astype(np.float32))
zb.thick = 0.05
zb.extract_offset = 0.0
bpy.ops.object.mode_set(mode='SCULPT')
msg = zs.extract(C, ball, zb.thick)
shell = next((o for o in bpy.data.objects if o.get(zs.EXTRACT_KEY)), None)


def radii():
    C.view_layer.update()
    me = shell.evaluated_get(C.evaluated_depsgraph_get()).data
    r = np.linalg.norm(np.array([shell.matrix_world @ v.co for v in me.vertices]), axis=1)
    return float(r.min()), float(r.max())


check('Extract (a masked cap of a ball): a new shell, marked as an extract of the ball, Thick on its Solidify, no '
      'offset modifier while Offset is 0', shell is not None and shell[zs.EXTRACT_KEY] == ball.name
      and any(m.type == 'SOLIDIFY' and abs(m.thickness - 0.05) < 1e-6 for m in shell.modifiers)
      and shell.modifiers.get(zs.EXTRACT_OFFSET) is None, msg)
lo0, hi0 = radii()
zb.extract_offset = 0.1
lo1, hi1 = radii()
names = [m.type for m in shell.modifiers]
check(f'Offset 0.1: the last extract moves off the ball at once (inner side {lo0:.3f} -> {lo1:.3f}, outer '
      f'{hi0:.3f} -> {hi1:.3f}), the thickness the same, the Displace before the Solidify',
      abs((lo1 - lo0) - 0.1) < 0.02 and abs((hi1 - hi0) - 0.1) < 0.02 and names.index('DISPLACE') < names.index('SOLIDIFY'))
zb.thick = 0.1
lo2, hi2 = radii()
check(f'Thick 0.1 moves live too (the shell {hi1 - lo1:.3f} -> {hi2 - lo2:.3f} thick)', (hi2 - lo2) > (hi1 - lo1) + 0.03)
zb.extract_offset = -0.03
lo3, _hi3 = radii()
check(f'a minus Offset sinks it in (inner side {lo3:.3f})', lo3 < lo2 - 0.1)
summary()
