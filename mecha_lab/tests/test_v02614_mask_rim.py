"""0.24.193 (user: "클로스 쪽에 마스크로 만드는 거, 외곽 계단 현상 평평하게 만들어 줘, 그 단면 부분" / "옵션 하나 만들어서 그냥
떨어지게 만들어 줘, 지금은 붙어 있으면서 떨어지는 거잖아"): Drape Mask - the rim's stair steps smoothed out; Fall Free:
the cloth is not held at the rim."""
import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
st = cd.settings(C)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=80, size=2.0)   # a wall of quads, the mask a tilted
body = C.active_object                                                             # disc: its edge runs in stair steps
body.rotation_euler = (np.radians(90), 0, 0)
bpy.ops.object.transform_apply(rotation=True)
co = mio.read_co(body.data)
att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
r = np.hypot(co[:, 0] / 0.7, (co[:, 2] - 0.1) / 0.45)
att.data.foreach_set('value', (r < 1.0).astype(np.float32))


def turn(me):
    """Mean turning angle (deg) along the longest open loop: stair steps turn 90 deg again and again."""
    lp = max(cd.rim_loops_idx(me), key=len)
    p = mio.read_co(me)[lp]
    a = p - np.roll(p, 1, 0)
    b = np.roll(p, -1, 0) - p
    cs = np.einsum('ij,ij->i', a, b) / np.maximum(np.linalg.norm(a, axis=1) * np.linalg.norm(b, axis=1), 1e-12)
    return float(np.degrees(np.arccos(np.clip(cs, -1, 1))).mean()), len(lp)


raw = cd.faces_mesh(body.data, cd.masked_faces(body.data))
t0, n0 = turn(raw)
box0 = np.ptp(mio.read_co(raw), axis=0)
moved = cd.smooth_rim(raw)
t1, _n = turn(raw)
box1 = np.ptp(mio.read_co(raw), axis=0)
step = 2.0 / 80
check(f'the rim of the masked faces: stair steps (mean turn {t0:.1f} deg over {n0} points) smoothed ({t1:.1f} deg), '
      f'no point moved more than a face ({moved / step:.2f} of one), the outline its size ({box1[0] / box0[0]:.3f}, '
      f'{box1[2] / box0[2]:.3f})', t0 > 30 and t1 < t0 * 0.35 and moved < step and abs(box1[0] / box0[0] - 1) < 0.03
      and abs(box1[2] / box0[2] - 1) < 0.04)
raw.calc_loop_triangles()
nrm = np.array([tuple(p.normal) for p in raw.polygons])
check('... and no face folded over (every normal still the wall\'s side)', bool(np.all(nrm @ nrm[0] > 0.5)))

st.mask_points = 100000
st.frames = 60
st.mask_free = False
C.view_layer.objects.active = body
cd.perform_masked(C, body)
ob = bpy.data.objects[cd.SIM['ob']]
t2, _n = turn(ob.data)
pins = int(np.count_nonzero(cd.SIM['sess']['cloth'].pin >= 1))
z0 = mio.read_co(ob.data)[:, 2].mean()
for _i in range(60):
    cd.step(C)
z_held = mio.read_co(ob.data)[:, 2].mean()
check(f'Drape Mask as before (Fall Free off): the rim smooth ({t2:.1f} deg), {pins} rim points held, the cloth stays '
      f'(mean height {z0:.3f} -> {z_held:.3f})', t2 < t0 * 0.35 and pins > 50 and abs(z_held - z0) < 0.3)
bpy.ops.mch.cdrape_control(action='cancel')
st.mask_free = True
C.view_layer.objects.active = body
cd.perform_masked(C, body)
ob = bpy.data.objects[cd.SIM['ob']]
pins = int(np.count_nonzero(cd.SIM['sess']['cloth'].pin >= 1))
for _i in range(60):
    cd.step(C)
co2 = mio.read_co(ob.data)
z_free = co2[:, 2].mean()
check(f'Fall Free on: nothing held ({pins}), the cloth comes off and falls (mean height {z0:.3f} -> {z_free:.3f}), '
      f'finite', pins == 0 and z_free < z0 - 0.3 and bool(np.all(np.isfinite(co2))))
cd.restart(C)
check('... and Restart keeps it free', int(np.count_nonzero(cd.SIM['sess']['cloth'].pin >= 1)) == 0)
bpy.ops.mch.cdrape_control(action='cancel')
st.mask_free = False
summary()
