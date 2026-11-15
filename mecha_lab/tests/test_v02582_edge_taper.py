"""0.24.174 (user: "깃털이랑 비늘 퍼에 달린 거 그거 가생이로 갈수록 얇아지는 버튼 만들어 주고, 그리고 스케일 라인에도 퍼에 있는
비늘 넣어 줘" ... "스케일 라인도 테이퍼 만들어 줘"): the Fur tool's feathers / scales smaller and flatter toward the area's edge
(Thinner at Edge), the Fur tool's eight real scales as buttons in Scale Line, Taper Start / End on the lines.
Measured on the covers' / lines' own placements."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, greeble_line as gl, skin_cover as sc  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1


def ellipse(cx, cy, rx, ry, n=64):
    return [[(cx + rx * math.cos(a), cy + ry * math.sin(a)) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def attrs(ob):
    me = ob.data
    n = len(me.vertices)
    P = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', P)
    s_ = np.empty(n * 3, np.float32)
    me.attributes['mch_scale'].data.foreach_get('vector', s_)
    return P.reshape(-1, 3), s_.reshape(-1, 3)


S.mch_cover.grow = 'SCALES'
cf.perform(C, ellipse(500, 500, 150, 120), FRONT)
cov = C.active_object
P0, S0 = attrs(cov)
sx, sy = 500 + P0[:, 0] * 200, 500 + P0[:, 2] * 200
rr = np.sqrt(((sx - 500) / 150) ** 2 + ((sy - 500) / 120) ** 2)       # (0 the middle .. 1 the drawn edge)
check('the button: Thinner at Edge on the Fur tool\'s feathers / scales (off: as before)',
      hasattr(cov.mch_cover, 'edge_thin') and not cov.mch_cover.edge_thin and np.ptp(S0[:, 0] / S0[:, 2]) < 1e-3)
cov.mch_cover.edge_thin = True
P1, S1 = attrs(cov)
sx1, sy1 = 500 + P1[:, 0] * 200, 500 + P1[:, 2] * 200
rr1 = np.sqrt(((sx1 - 500) / 150) ** 2 + ((sy1 - 500) / 120) ** 2)
mid = rr1 < 0.3
edge = rr1 > 0.92
ratio_mid = float(np.median(S1[mid, 0])) / float(np.median(S0[rr < 0.3, 0]))
ratio_edge = float(np.median(S1[edge, 0])) / float(np.median(S0[rr > 0.92, 0]))
flat_edge = float(np.median(S1[edge, 2] / S1[edge, 0])) / float(np.median(S0[rr > 0.92, 2] / S0[rr > 0.92, 0]))
check(f'Thinner at Edge on: the middle ones as they were (x {ratio_mid:.2f}), the ones at the edge smaller (x '
      f'{ratio_edge:.2f}) and flatter still (height / length x {flat_edge:.2f}) - they fade into the skin',
      abs(ratio_mid - 1.0) < 0.12 and ratio_edge < 0.6 and flat_edge < 0.8)
cov.mch_cover.edge_taper = 0.3
P2, S2 = attrs(cov)
sx2, sy2 = 500 + P2[:, 0] * 200, 500 + P2[:, 2] * 200
e2 = np.sqrt(((sx2 - 500) / 150) ** 2 + ((sy2 - 500) / 120) ** 2) > 0.92
check(f'Edge Taper 0.3: less smaller at the edge (x {float(np.median(S2[e2, 0])) / float(np.median(S0[rr > 0.92, 0])):.2f})',
      float(np.median(S2[e2, 0])) > float(np.median(S1[edge, 0])))

# Scale Line: the Fur tool's scales
for o in list(bpy.data.objects):
    if o != body:
        bpy.data.objects.remove(o)
st = gl.settings(S, 'CREATURE')
r = bpy.ops.mch.scale_pick(scale='DRAGON')
P_ = gl.picked(st)
check(f'Scale Line: a scale button (the Fur tool\'s real scales) - that one made and picked ({[p.name for p in P_]}), '
      f'shown as in use', r == {'FINISHED'} and len(P_) == 1 and P_[0].data.get('mch_shape_id') == 'DRAGON'
      and gl.scale_in_use(C) == 'DRAGON')


def draw_line(kind='CREATURE', **kw):
    stt = gl.settings(S, kind)
    for k, v in kw.items():
        setattr(stt, k, v)
    pts, nrm = [], []
    for t in np.linspace(-1.2, 1.2, 60):
        pts.append((math.sin(t), -math.cos(t) * 1.0, 0.0))
        nrm.append(tuple(Vector(pts[-1]).normalized()))
    ln = gl.new_line(C, body, pts, nrm, gl.picked(stt), stt, kind)
    gl.rebuild(ln, C)
    return ln


ln0 = draw_line(taper_start=0.0, taper_end=0.0, scale_random=0.0)
_p, T0 = attrs(ln0)
ln1 = draw_line(taper_start=0.0, taper_end=0.8, scale_random=0.0)
_p, T1 = attrs(ln1)
check(f'Taper End 0.8: the scales smaller and smaller toward the end (first {T1[0, 0]:.3f} -> last {T1[-1, 0]:.3f}; '
      f'without: {T0[0, 0]:.3f} -> {T0[-1, 0]:.3f}), packed closer there ({len(T0)} -> {len(T1)} along it)',
      T1[-1, 0] < T1[0, 0] * 0.4 and abs(T0[-1, 0] / T0[0, 0] - 1.0) < 1e-3 and len(T1) > len(T0))
ln2 = draw_line(taper_start=0.8, taper_end=0.8, scale_random=0.0)
_p, T2 = attrs(ln2)
m = len(T2) // 2
check(f'both ends: small at both, the middle the biggest ({T2[0, 0]:.3f} / {T2[m, 0]:.3f} / {T2[-1, 0]:.3f})',
      T2[0, 0] < T2[m, 0] * 0.6 and T2[-1, 0] < T2[m, 0] * 0.6)
ln1.select_set(True)
C.view_layer.objects.active = ln1
ln1.mch_greeble_line.taper_end = 0.0
_p, T3 = attrs(ln1)
check('a selected line: its Taper live (back to even)', abs(T3[-1, 0] / T3[0, 0] - 1.0) < 1e-3)
summary()
