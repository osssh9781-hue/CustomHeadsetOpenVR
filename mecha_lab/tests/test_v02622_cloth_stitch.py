"""0.24.208 (user: "클로스에 내가 메쉬를 뽑잖아, 그 위에 선으로 그리면 그쪽이 약간 박음질 같은 거 한 걸로 돼서 시뮬" / "몸에
박힌 거보다 천끼리만 조여지는 느낌, 근데 몸에 붙는 것도 옵션"): Cloth Drape - the drawn lines as Stitches: the cloth
is gathered along them; Sewn to Body holds the seam."""
import json

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cloth_drape as cd, mesh_io as mio, wrinkle_lines as wl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
st = cd.settings(C)
check('the settings: Lines = Tubes by default (as before), Stitches with Tighten 55 %, Seam Width, no groove and no puff (0.24.211: only the gather), Sewn to Body off',
      st.line_mode == 'TUBES' and abs(st.stitch_tight - 55.0) < 1e-6 and abs(st.stitch_puff) < 1e-6
      and abs(st.stitch_depth) < 1e-6
      and st.stitch_stick is False)
bpy.ops.mesh.primitive_grid_add(x_subdivisions=80, y_subdivisions=80, size=2.0)
body = C.active_object
co = mio.read_co(body.data)
att = body.data.attributes.new('.sculpt_mask', 'FLOAT', 'POINT')
att.data.foreach_set('value', ((np.abs(co[:, 0]) < 0.6) & (np.abs(co[:, 1]) < 0.6)).astype(np.float32))
pts = [(float(x), 0.0, 0.0) for x in np.linspace(-0.45, 0.45, 12)]          # a line across the middle
body[wl.PROP] = json.dumps([dict(pts=pts, nrm=[(0.0, 0.0, 1.0)] * len(pts), strength=1.0)])
wl._CACHE.pop(body.name, None)
st.mask_points = 100000
st.frames = 50
st.mask_free = True
st.slack = 0.0
st.use_lines = True


def run(mode, stick=False):
    st.line_mode, st.stitch_stick = mode, stick
    for o in C.selected_objects:
        o.select_set(False)
    body.select_set(True)
    C.view_layer.objects.active = body
    cd.perform_masked(C, body)
    sess = cd.SIM['sess']
    cloth = sess['cloth']
    ob = bpy.data.objects[cd.SIM['ob']]
    start = cloth.init.copy()
    on = (np.abs(start[:, 1]) < 0.012) & (np.abs(start[:, 0]) < 0.4)        # (the cloth points on the line)
    near = (np.abs(start[:, 1]) < 0.03) & (np.abs(start[:, 0]) < 0.4)
    off = np.abs(start[:, 1]) > 0.3
    pins = int(np.count_nonzero(cloth.pin >= 1))
    scale = np.asarray(cloth.scale_e, float)
    for _i in range(50):
        cd.step(C)
    c = mio.read_co(ob.data)
    span_on = float(np.ptp(c[near, 0]) / np.ptp(start[near, 0]))
    out = dict(stitches=sess.get('stitches', 0), pins=pins, scale_min=float(scale.min()), span_on=span_on,
               moved=float(np.abs(c[on] - start[on]).max()), finite=bool(np.all(np.isfinite(c))),
               span_off=float(np.ptp(c[off, 0]) / np.ptp(start[off, 0])))
    cd.cancel(C)
    return out


tube = run('TUBES')
sew = run('STITCH')
check(f'Stitches: the seam touches {sew["stitches"]} cloth points, its edges want to be up to 55 % shorter (shortest '
      f'x{sew["scale_min"]:.2f}); Tubes mode gathers nothing (x{tube["scale_min"]:.2f}, 0 seam points)',
      sew['stitches'] > 20 and 0.4 < sew['scale_min'] < 0.52 and tube['stitches'] == 0 and tube['scale_min'] > 0.99)
check(f'... after the drape the cloth along the line is pulled together (its length x{sew["span_on"]:.2f}; Tubes '
      f'x{tube["span_on"]:.2f}), away from the line it keeps its width (x{sew["span_off"]:.2f}); nothing held '
      f'({sew["pins"]} pins), finite', sew['span_on'] < tube['span_on'] - 0.01 and sew['span_off'] > 0.9
      and sew['pins'] == 0 and sew['finite'])
stuck = run('STITCH', stick=True)
check(f'Sewn to Body: the points on the line are held ({stuck["pins"]} pins) and stay where they were drawn (moved '
      f'{stuck["moved"]:.4f}; free: {sew["moved"]:.4f})', stuck['pins'] > 5 and stuck['moved'] < sew['moved'] * 0.6)
# 0.24.210 the seams drawn on the cloth itself (Draw Stitches): kept on its mesh, used with no body line at all
del body[wl.PROP]
wl._CACHE.pop(body.name, None)
st.use_lines, st.line_mode, st.stitch_stick = False, 'TUBES', False
for o in C.selected_objects:
    o.select_set(False)
body.select_set(True)
C.view_layer.objects.active = body
cd.perform_masked(C, body)
ob = bpy.data.objects[cd.SIM['ob']]
n_before = cd.SIM['sess'].get('stitches', 0)
start = cd.SIM['sess']['cloth'].init
line = np.array([(x, 0.0, float(start[:, 2].mean())) for x in np.linspace(-0.45, 0.45, 12)])
cd.set_stitch_paths(ob.data, [line])
st.slack = 20.0                                    # (some extra fabric: it can swell beside the seam)
cd.stitch_refresh(C)
sess = cd.SIM['sess']
check(f'a seam drawn on the laid cloth (no line on the body, Use Lines off): kept on the cloth\'s mesh, the cloth made '
      f'again with it ({n_before} -> {sess.get("stitches", 0)} seam points), and it still waits (not running)',
      n_before == 0 and len(cd.stitch_paths(ob.data)) == 1 and sess.get('stitches', 0) > 20
      and cd.SIM.get('running') is False and float(np.asarray(sess['cloth'].scale_e).min()) < 0.6)
def seam_span(tight):
    st.stitch_tight = tight
    cd.stitch_refresh(C)
    o = bpy.data.objects[cd.SIM['ob']]
    s0 = cd.SIM['sess']['cloth'].init.copy()
    for _i in range(50):
        cd.step(C)
    c = mio.read_co(o.data)
    near = (np.abs(s0[:, 1]) < 0.03) & (np.abs(s0[:, 0]) < 0.4)
    far = (np.abs(s0[:, 1]) > 0.25) & (np.abs(s0[:, 0]) < 0.35)
    return (float(np.ptp(c[near, 0]) / np.ptp(s0[near, 0])), float(c[far, 2].mean() - s0[far, 2].mean()),
            bool(np.all(np.isfinite(c))), cd.SIM['sess'].get('seam_dent', 0.0))


lo, hi = seam_span(15.0), seam_span(75.0)
st.stitch_tight = 55.0
check(f'0.24.211 a stitch only pulls the cloth together along the line, and Tighten sets how much: the cloth along the '
      f'seam x{lo[0]:.2f} at 15 %, x{hi[0]:.2f} at 75 %; no groove pressed in ({hi[3]:.4f}) and nothing swells (away '
      f'from the seam {hi[1]:+.3f}: not above)',
      hi[0] < lo[0] - 0.02 and hi[3] == 0.0 and hi[1] < 0.005 and lo[2] and hi[2])
cd.cancel(C)
cd.perform_masked(C, body)
ob = bpy.data.objects[cd.SIM['ob']]
cd.set_stitch_paths(ob.data, [line, line + np.array((0.0, 0.2, 0.0))])
r1 = bpy.ops.mch.cdrape_stitch(action='UNDO')
n1 = len(cd.stitch_paths(ob.data))
r2 = bpy.ops.mch.cdrape_stitch(action='CLEAR')
check('Undo takes the last seam off (2 -> 1), Clear all of them', 'FINISHED' in r1 and n1 == 1 and 'FINISHED' in r2
      and len(cd.stitch_paths(ob.data)) == 0 and cd.SIM['sess'].get('stitches', 0) == 0)
cd.cancel(C)
st.line_mode, st.stitch_stick, st.use_lines, st.mask_free, st.slack = 'TUBES', False, False, False, 25.0
summary()
