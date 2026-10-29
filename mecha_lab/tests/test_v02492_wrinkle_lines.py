"""0.24.92 Wrinkle Lines: thin tubes along the drawn lines (live sliders), then a copy of the mesh draped over the
surface + tubes as a collider (Marvelous-Designer style): the cloth hangs on the tubes and folds below them."""
import inspect
import json
import math
import time

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import wrinkle_lines as wl

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

# -- tube_field (pure) ------------------------------------------------------------------------------------------
grid = np.array([[x, y, 0.0] for x in np.linspace(-1, 1, 41) for y in np.linspace(-1, 1, 41)])
path = [Vector((-0.8, 0, 0)), Vector((0.8, 0, 0))]
h = wl.tube_field(grid, [path], [1.0], 0.2, fade=0.0)
on = np.isclose(grid[:, 1], 0) & (np.abs(grid[:, 0]) <= 0.8)
check('tube_field: 1 on the line, 0 beyond the tube radius, a round profile in between (no end fade)',
      np.allclose(h[on], 1.0) and np.all(h[np.abs(grid[:, 1]) > 0.2 + 1e-9] == 0)
      and abs(h[np.isclose(grid[:, 1], 0.1) & np.isclose(grid[:, 0], 0)][0] - math.sqrt(0.75)) < 1e-6, (h.max(), h.min()))
hf = wl.tube_field(grid, [path], [1.0], 0.2, fade=0.25)
mid = np.isclose(grid[:, 1], 0) & np.isclose(grid[:, 0], 0)
end = np.isclose(grid[:, 1], 0) & np.isclose(grid[:, 0], -0.8)
near_end = np.isclose(grid[:, 1], 0) & np.isclose(grid[:, 0], -0.6)
check('End fade: full in the middle, 0 at the ends, part way near an end (25 % of the length)',
      np.isclose(hf[mid][0], 1.0) and hf[end][0] < 1e-9 and 0.1 < hf[near_end][0] < 0.95, (hf[mid][0], hf[end][0], hf[near_end][0]))
ring = [Vector((0.5 * math.cos(a), 0.5 * math.sin(a), 0)) for a in np.linspace(0, 2 * math.pi, 33)]
hr = wl.tube_field(grid, [ring], [0.5], 0.1, fade=0.3)
on_ring = np.abs(np.linalg.norm(grid[:, :2], axis=1) - 0.5) < 0.02
check('A closed line has no ends (the ring is full all round) and the line strength scales the tube',
      hr[on_ring].min() > 0.45 and abs(hr.max() - 0.5) < 1e-6, (hr[on_ring].min(), hr.max()))
h2 = wl.tube_field(grid, [path, ring], [1.0, 1.0], 0.1)
check('Several lines: the highest tube wins at every point', np.all(h2 >= wl.tube_field(grid, [path], [1.0], 0.1))
      and np.all(h2 >= wl.tube_field(grid, [ring], [1.0], 0.1)))
check('No lines / no points: zeros', len(wl.tube_field(grid, [], [], 0.1)) == len(grid)
      and wl.tube_field(np.zeros((0, 3)), [path], [1.0], 0.1).shape == (0,))


# -- the sleeve ---------------------------------------------------------------------------------------------------
def sleeve(name='Sleeve', R=0.5, H=3.0, NA=64, NZ=96):
    import bmesh
    bm = bmesh.new()
    rows = []
    for k in range(NZ + 1):
        z = -H / 2 + H * k / NZ
        rows.append([bm.verts.new((R * math.cos(2 * math.pi * i / NA), R * math.sin(2 * math.pi * i / NA), z)) for i in range(NA)])
    for k in range(NZ):
        for i in range(NA):
            bm.faces.new((rows[k][i], rows[k][(i + 1) % NA], rows[k + 1][(i + 1) % NA], rows[k + 1][i]))
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.scene.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    ob.select_set(True)
    return ob


def put_lines(ob, specs, R=0.5):
    data = []
    for spec in specs:
        pts = [Vector((R * math.cos(math.radians(a)), R * math.sin(math.radians(a)), z)) for a, z in spec]
        data.append(dict(pts=[list(p) for p in pts], nrm=[list(Vector((p.x, p.y, 0)).normalized()) for p in pts], strength=1.0))
    ob[wl.PROP] = json.dumps(data)
    wl._CACHE.pop(ob.name, None)
    return wl._lines_of(ob)


SPECS = [[(240, 0.8), (200, 0.5), (230, 0.2), (270, 0.0), (310, 0.2), (335, 0.6)], [(210, -0.6), (250, -0.9), (300, -0.9), (340, -0.7)]]
ob = sleeve()
lines = put_lines(ob, SPECS)
st = S.mch_wlines
check('Settings: Wrinkle Size 5 % (tube = 1/3 of it), Fold 100, End Fade 20, Shrink 33, Gravity 30, Keep 47, boundary pinned',
      (st.size, st.fold, st.fade, st.shrink, st.gravity, st.keep, st.pin_boundary) == (5.0, 100.0, 20.0, 33.0, 30.0, 47.0, True))
st.detail = False
st.frames = 20
co0 = np.array([v.co[:] for v in ob.data.vertices])
# stage 1: the tubes
sess = wl.prepare(C, ob, st, lines)
shape, hh = wl.tube_shape(sess, st)
rr = np.linalg.norm(shape[:, :2], axis=1)
tube_r = sess['tube_r']
check('Tubes: radius = size x 5 % / 3, the surface lifted up to about one radius along the lines, nowhere pushed in',
      abs(tube_r - sess['size'] * 0.05 / 3) < 1e-9 and 0.8 * tube_r < hh.max() <= tube_r + 1e-9 and hh.min() >= 0
      and rr.max() > 0.5 + 0.8 * tube_r, (tube_r, hh.max(), rr.max()))
check('Tubes: most of the sleeve untouched (the tubes are thin)', np.count_nonzero(hh > 1e-6) < 0.35 * len(hh),
      np.count_nonzero(hh > 1e-6) / len(hh))
st.fold = 50.0
shape2, hh2 = wl.tube_shape(sess, st)
check('Fold Strength = the tube height (50 % -> half), the field reused (no recompute)',
      abs(hh2.max() - hh.max() * 0.5) < 1e-9 and sess['field_key'] is not None)
st.mode = 'CREASE'
_shape3, hh3 = wl.tube_shape(sess, st)
check('Crease mode: a groove (the heights negative)', hh3.min() < 0 and abs(hh3.min() + hh2.max()) < 1e-9)
st.mode = 'WRINKLE'
st.fold = 100.0
# stage 2: the cloth over the collider
t = time.perf_counter()
wl.build(C, ob, st, sess)
cloth = sess['cloth']
check('Cloth: a copy a little above the tubes, rest lengths shrunk 33 %, the two open rings pinned',
      abs(cloth.scale_e - 0.67) < 1e-9 and np.count_nonzero(cloth.pin >= 1) == 2 * 64
      and np.all(np.linalg.norm(cloth.co[:, :2], axis=1) > 0.5), (cloth.scale_e, np.count_nonzero(cloth.pin >= 1)))
for _ in range(20):
    wl.advance(sess, st)
dt = time.perf_counter() - t
co = cloth.co
N, Cc = sess['nrm'], sess['collider']
height = ((co - Cc[sess['ref']]) * N[sess['ref']]).sum(1)
check('After 20 frames the cloth stays outside the collider (never deeper than a sliver under the margin)',
      height.min() > sess['margin'] - tube_r * 0.5, (height.min(), sess['margin']))
pinned = cloth.pin >= 1
check('The pinned rings did not move; the rest moved and folded (points moved, spread of radii)',
      np.allclose(co[pinned], cloth.init[pinned]) and np.linalg.norm(co - cloth.init, axis=1).max() > tube_r * 0.4
      and (np.linalg.norm(co[:, :2], axis=1).max() - np.linalg.norm(co[:, :2], axis=1).min()) > tube_r * 0.4,
      np.linalg.norm(co - cloth.init, axis=1).max())
check('Gravity is world down in local space (the sleeve upright: -Z)', np.allclose(sess['gdir'], (0, 0, -1)))
check('20 frames on a 6k-point sleeve under 4 s', dt < 4.0, round(dt, 2))
check('Nothing is NaN / exploded', np.all(np.isfinite(co)) and np.abs(co).max() < 5.0, np.abs(co).max())
check('The cloth sticks (friction): the mid points of the sleeve did not slide down the whole tube',
      co[:, 2].min() > -1.6, co[:, 2].min())

# -- simulate (one go) + the live flow --------------------------------------------------------------------------
fresh()
S = C.scene
ob = sleeve('S2')
lines = put_lines(ob, SPECS)
st = S.mch_wlines
st.detail = False
info = wl.simulate(C, ob, st, lines, frames=10)
co = np.array([v.co[:] for v in ob.data.vertices])
check('simulate writes the result into the mesh (same point count), reports time / tubes lifted',
      len(co) == 97 * 64 and info['frames'] == 10 and info['lifted'] > 0 and info['time'] > 0
      and np.linalg.norm(co - co0, axis=1).max() > 1e-3, info)
fresh()
S = C.scene
ob = sleeve('S3')
lines = put_lines(ob, SPECS)
st = S.mch_wlines
st.detail = False
st.frames = 8
before = np.array([v.co[:] for v in ob.data.vertices])
info, err = wl.start(C, ob, st)
mid = np.array([v.co[:] for v in ob.data.vertices])
check('start = stage 1: the tubes shown in the mesh, a backup kept, no cloth yet',
      err is None and wl.sim_active() and wl.stage() == 'preview' and np.linalg.norm(mid - before, axis=1).max() > 1e-4
      and bpy.data.meshes.get(wl.SIM['backup']) is not None and not wl.step(C))
st.size = 10.0
tubes2 = np.array([v.co[:] for v in ob.data.vertices])
check('A tube slider moved while the tubes are shown: the shape updates live',
      np.linalg.norm(tubes2 - mid, axis=1).max() > 1e-4 and wl.stage() == 'preview')
st.size = 5.0
check('Space from the tubes = the cloth stage; frames step until done', wl.run(C) and wl.stage() == 'run'
      and all(wl.step(C) for _ in range(8)) and not wl.step(C) and wl.SIM['done'])
after = np.array([v.co[:] for v in ob.data.vertices])
msg = wl.confirm(C)
check('Enter keeps the frame; the backup is dropped; nothing else changes', 'kept frame 8' in msg and not wl.sim_active()
      and np.allclose(np.array([v.co[:] for v in ob.data.vertices]), after) and 'S3_mch_wl_backup' not in bpy.data.meshes, msg)
info, err = wl.start(C, ob, st)
msg = wl.cancel(C)
check('Esc goes back to the mesh before the tubes', 'back' in msg and not wl.sim_active()
      and np.allclose(np.array([v.co[:] for v in ob.data.vertices]), after))
info, err = wl.start(C, ob, st)
msg = wl.confirm(C)
check('Enter while the tubes are shown keeps just the tubes', 'kept the tubes' in msg and not wl.sim_active(), msg)
check('status text names the stage', wl.status() == '')
src = inspect.getsource(wl.draw)
check('Panel: Tubes / Simulate / Keep / Back, the tube sliders (size, fold, fade) and the cloth sliders (shrink, gravity, keep)',
      all(k in src for k in ("'size'", "'fold'", "'fade'", "'shrink'", "'gravity'", "'keep'", 'Tubes (Space)', 'Simulate (Space)',
                             'Keep (Enter)', 'Back (Esc)', "'pin_boundary'")))
keys = [k[0] for k in wl.TOOL_KEYMAP]
check('Tool keys: Space simulate, X remove line, Shift / Ctrl click points', 'mch.wrinkle_sim' in keys and 'mch.wrinkle_line_delete' in keys)
summary()
