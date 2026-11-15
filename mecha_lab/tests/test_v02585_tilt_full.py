"""0.24.175 (user, a Feather Line on a dragon's wing arm: "이거 -180 까지 틸트 되게 해 줘"): Tilt goes the whole way round,
-180 .. 180 (was -85 .. 85) - on Feather / Scale / Greeble Lines, the window's setting and a selected line (live).
Measured on the line's own placements: each part's up turned about the across-the-line axis by the tilt."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import greeble_line as gl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
st = gl.settings(S, 'FEATHER')
p = st.bl_rna.properties['tilt']
check(f'Tilt: -180 .. 180 now (was -85 .. 85; slider {math.degrees(p.soft_min):.0f} .. {math.degrees(p.soft_max):.0f})',
      abs(p.hard_min + math.pi) < 1e-6 and abs(p.hard_max - math.pi) < 1e-6 and abs(p.soft_min + math.pi) < 1e-6)
st.tilt = math.radians(-180)
check(f'set to -180: it stays -180 ({math.degrees(st.tilt):.1f})', abs(math.degrees(st.tilt) + 180) < 1e-3)
r = bpy.ops.mch.feather_pick(feather='PRIMARY')
pts, nrm = [], []
for t in np.linspace(-0.9, 0.9, 30):
    pts.append((math.sin(t), -math.cos(t), 0.0))
    nrm.append(tuple(Vector(pts[-1]).normalized()))


def ups(ln):
    me = ln.data
    q = np.empty(len(me.vertices) * 4, np.float32)
    me.attributes['mch_rot'].data.foreach_get('value', q)
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    out = []
    for qq, c in zip(q.reshape(-1, 4), co):
        up = Quaternion(qq) @ Vector((0, 0, 1))
        n = Vector(c).normalized()
        out.append(up.dot(n))
    return np.array(out)


st.tilt = 0.0
st.turn = 0.0
st.scale_random = 0.0
st.turn_random = 0.0
ln0 = gl.new_line(C, body, pts, nrm, gl.picked(st), st, 'FEATHER')
gl.rebuild(ln0, C)
u0 = float(np.median(ups(ln0)))
st.tilt = math.radians(-180)
ln1 = gl.new_line(C, body, pts, nrm, gl.picked(st), st, 'FEATHER')
gl.rebuild(ln1, C)
u1 = float(np.median(ups(ln1)))
st.tilt = math.radians(-120)
ln2 = gl.new_line(C, body, pts, nrm, gl.picked(st), st, 'FEATHER')
gl.rebuild(ln2, C)
u2 = float(np.median(ups(ln2)))
check(f'the parts turned that far: their up against the body\'s normal - tilt 0: {u0:+.2f}, -120: {u2:+.2f} '
      f'(cos -120 = -0.50), -180: {u1:+.2f} (upside down)', r == {'FINISHED'} and u0 > 0.9 and u1 < -0.9
      and abs(u2 + 0.5) < 0.15)
ln0.select_set(True)
C.view_layer.objects.active = ln0
ln0.mch_greeble_line.tilt = math.radians(-180)
u3 = float(np.median(ups(ln0)))
check(f'a selected line: its Tilt to -180 live ({math.degrees(ln0.mch_greeble_line.tilt):.0f}: up {u3:+.2f})',
      abs(math.degrees(ln0.mch_greeble_line.tilt) + 180) < 1e-3 and u3 < -0.9)
summary()
