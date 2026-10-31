"""0.24.95 Cloth Drape Cape / Neck Cloth (user: "점을 딱딱 찍어 엔터를 누르면 천이 생겨, 시뮬 돌리면 망토 / 원을 그려 엔터 -
길이 조절 슬라이더 - 목도리(목 위에 얹어 놓는 천)", "당연히 찍은 만큼만 나와야지"): a line across the back hangs a cape as
wide as the line, a loop round the neck hangs a cloth over the shoulders; Length / Flare / Detail rebuild it before
Space; long-range tethers keep a cloth hung from one edge from stretching."""
import inspect
import math
import types

import numpy as np
from _harness import bpy, check, fresh, select_only, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import cloth_drape as cd, cloth_pbd, core_geometry as cg, cut_engine as ce, mesh_io as mio, surface_lasso as sl
from mecha_lab import wrinkle_lines as wl

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
st = S.mch_cdrape
st.padding, st.trim, st.stop_at_pins, st.two_sides = False, False, False, False
PX = 400.0


class Back:                     # an orthographic "view" from +Y (the back): outline points are (x, z) x PX
    view_dir = Vector((0, -1, 0))

    def ray(self, xy):
        return Vector((xy[0] / PX, 5.0, xy[1] / PX)), Vector((0, -1, 0))


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


# ---- the body: a standing cylinder (r 0.3, z 0 .. 1.6); the cape line across its back (+Y) near the top
clear()
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=1.6, vertices=48, location=(0, 0, 0.8))
body = C.active_object
select_only(body)
check('Settings: Mode Area by default, Cape / Neck Cloth there; Length 50 %, Flare 0 (as wide as the points)',
      st.drape_mode == 'AREA' and {'CAPE', 'NECK'} <= {i.identifier for i in st.bl_rna.properties['drape_mode'].enum_items}
      and abs(st.cape_length - 50.0) < 1e-6 and abs(st.cape_flare) < 1e-6)
line = [Vector((x, math.sqrt(0.09 - x * x), 0.65)) for x in np.linspace(-0.2, 0.2, 9)]   # on the surface, at the back (local: z 1.45 - 0.8)
size, step, gap, down, length = cd._hang_args(body, st)
me, nb = cd.hang_patch(body, np.array([p[:] for p in line]), length, 0.0, step, gap, down, closed=False)
co = mio.read_co(me)
rows = len(co) // nb
G = co.reshape(rows, nb, 3)
across = np.linalg.norm(np.diff(G, axis=1), axis=2)
check('hang_patch (cape): a grid nb x rows, the top row on the line, as wide as the line (x within the line +- a cell)',
      rows > 10 and nb >= 9 and co[:, 0].min() > -0.2 - step * 1.5 and co[:, 0].max() < 0.2 + step * 1.5,
      (nb, rows, co[:, 0].min(), co[:, 0].max()))
check('... no column fans out (the widest gap between columns under 3 cells)', across.max() < step * 3.0, (across.max(), step))
check('... every point outside the body (radius >= 0.3), hanging down from the line',
      np.hypot(co[:, 0], co[:, 1]).min() > 0.3 * math.cos(math.pi / 48) - 1e-6 and co[:, 2].min() < 0.65 - length * 0.8, (np.hypot(co[:, 0], co[:, 1]).min(), co[:, 2].min()))
bpy.data.meshes.remove(me)

# ---- 0.24.95 Curtain (user: "위에 시작 부분을 커튼처럼 만들어 주면 중간 부분이 예뻐질 것 같아"): the top gathered into pleats
check('Settings: Curtain 50 % (on by default), Pleats 0 = auto', abs(st.cape_gather - 50.0) < 1e-6 and st.cape_pleats == 0)
L = np.array([p[:] for p in line])
me_f, nb_f = cd.hang_patch(body, L, length, 0.0, step, gap, down, False, 0.0)
me_c, nb_c = cd.hang_patch(body, L, length, 0.0, step, gap, down, False, 50.0, 0, size * 0.04)
info = dict(cd.HANG_INFO)
cf, cc = mio.read_co(me_f), mio.read_co(me_c)
tf, tc = cf[:nb_f], cc[:nb_c]
arc = lambda t: float(np.linalg.norm(np.diff(t, axis=0), axis=1).sum())
check('Curtain 50: the top row is 1.5 x the line long (the extra fabric folded in), about 1.5 x the columns',
      abs(arc(tc) / arc(tf) - 1.5) < 0.08 and 1.3 < nb_c / nb_f < 1.7, (arc(tc) / arc(tf), nb_f, nb_c))
order = np.argsort(tf[:, 0])
off = tc[:, 1] - np.interp(tc[:, 0], tf[order, 0], tf[order, 1])          # (out = +Y at the back of the cylinder)
crest = [i for i in range(1, len(off) - 1) if off[i] >= off[i - 1] and off[i] > off[i + 1] and off[i] > 0.5 * off.max()]
check('... folded into pleats that bulge OUT only (pinch points on the line, crests the pleat depth out), as many crests as pleats',
      off.min() > -step * 0.25 and abs(off.max() - info['depth']) < step * 0.5 and info['depth'] > step and len(crest) == info['pleats'] >= 2,
      (off.min(), off.max(), info, len(crest)))
Gc = cc.reshape(-1, nb_c, 3)
check('... the folds run straight down the cloth from the pleats (every row the same pattern), every point outside the body',
      np.abs(Gc[:, :, :2] - Gc[0, :, :2]).max() < 1e-6 and np.hypot(cc[:, 0], cc[:, 1]).min() > 0.3 * math.cos(math.pi / 48) - 1e-6,
      np.abs(Gc[:, :, :2] - Gc[0, :, :2]).max())
me4, nb4 = cd.hang_patch(body, L, length, 0.0, step, gap, down, False, 50.0, info['pleats'] + 3, size * 0.04)
check('Pleats set by hand (3 more than auto): that many, the same 1.5 x fabric (so shallower pleats)',
      cd.HANG_INFO['pleats'] == info['pleats'] + 3 and cd.HANG_INFO['depth'] < info['depth']
      and abs(arc(mio.read_co(me4)[:nb4]) / arc(tf) - 1.5) < 0.08, cd.HANG_INFO)
check('Curtain 0: the flat sheet as before (the top row as long as the line, no pleats)', abs(arc(tf) - cd.HANG_INFO['base_width']) < step
      and cd.hang_patch(body, L, length, 0.0, step, gap, down, False, 0.0)[1] == nb_f and cd.HANG_INFO['pleats'] == 0)
for m_ in (me_f, me_c, me4):
    bpy.data.meshes.remove(m_)
for m_ in [m for m in bpy.data.meshes if m.users == 0 and m.name.startswith('Cloth Cape')]:
    bpy.data.meshes.remove(m_)

# ---- the lasso path: Mode Cape, a line drawn across the back (seen from behind)
st.drape_mode = 'CAPE'
stroke = [(x * PX, 1.45 * PX) for x in np.linspace(-0.2, 0.2, 12)]
msg = cd.perform(C, [stroke], Back())
ob = C.view_layer.objects.active
sess = cd.SIM.get('sess')
check('Mode Cape + a drawn line: a "Cloth Cape" parented to the body, the line pinned, the session ready',
      ob is not None and ob.name.startswith('Cloth Cape') and ob.parent is body and cd.sim_active() and cd.SIM['source'] == 'CAPE'
      and int((sess['cloth'].pin >= 1).sum()) == cd.SIM['nb'] and 'Cape' in msg, msg)
check('... long-range tethers on (a cloth hung from one edge cannot stretch like rubber)',
      sess['cloth'].tether is not None and len(sess['cloth'].tether[0]) == len(sess['cloth'].co) - cd.SIM['nb'])
n0 = len(ob.data.vertices)
st.gravity = 200.0
for _ in range(40):
    cd.advance(sess, st)
c = sess['cloth'].co
check('drape 40 frames: finite, outside the body, hanging (not stretched past its length x Looseness)',
      np.all(np.isfinite(c)) and np.hypot(c[:, 0], c[:, 1]).min() > 0.29 and c[:, 2].min() > 0.65 - length * (1 + st.slack / 100.0) * 1.1,   # (body space)
      (np.hypot(c[:, 0], c[:, 1]).min(), c[:, 2].min()))
cd.SIM['running'] = False
st.cape_length = 80.0
check('Length 50 -> 80 with the cape waiting: it is made again at once from the same line (before Space)',
      len(C.view_layer.objects.active.data.vertices) > n0 * 1.4, (n0, len(C.view_layer.objects.active.data.vertices)))
check('Length is in the snapshot (a change restarts the drape with Space)', 'cape_length' in inspect.getsource(cd._snapshot))
cd.restart(C)
ob = C.view_layer.objects.active
check('Length 50 -> 80 and Space / Restart: the cape is made again from the same line, longer',
      len(ob.data.vertices) > n0 * 1.4 and cd.SIM['source'] == 'CAPE' and cd.SIM['sess']['frame'] == 0, (n0, len(ob.data.vertices)))
n80 = len(ob.data.vertices)
cd.SIM['running'] = False
st.cape_gather = 0.0
n_flat = len(C.view_layer.objects.active.data.vertices)
st.cape_pleats = 5
check('Curtain 50 -> 0 / Pleats with the cape waiting: made again at once (fewer columns without the pleats); both in the snapshot',
      1.3 < n80 / max(n_flat, 1) < 1.7 and 'cape_gather' in inspect.getsource(cd._snapshot) and 'cape_pleats' in inspect.getsource(cd._snapshot)
      and "'cape_gather'" in inspect.getsource(cd.draw), (n80, n_flat))
st.cape_gather, st.cape_pleats = 50.0, 0
ob = C.view_layer.objects.active
st.cape_flare = 60.0
cd.restart(C)
w = mio.read_co(ob.data)
check('Flare 60: the hem wider than the line', w[:, 0].max() - w[:, 0].min() > 0.4 * 1.3, w[:, 0].max() - w[:, 0].min())
st.cape_flare, st.cape_length = 0.0, 50.0
msg = cd.confirm(C)
check('Enter keeps the cape', 'kept' in msg and not cd.sim_active(), msg)
bpy.data.objects.remove(ob)

# ---- Neck Cloth: a loop round the "neck" of a ball (z 0.6 on a sphere of r 1: the shoulders below it)
clear()
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
ball = C.active_object
select_only(ball)
st.drape_mode = 'NECK'
check('Neck Cloth: Tube (a vertical cylinder) by default, Ring as the other style, Pin Top on',
      st.neck_style == 'TUBE' and 'RING' in {i.identifier for i in st.bl_rna.properties['neck_style'].enum_items} and st.neck_pin_top)
# the tube: round a cylinder "neck" (r 0.12, z 0 .. 1) standing on nothing
neck_ob = None
bpy.ops.mesh.primitive_cylinder_add(radius=0.12, depth=1.0, vertices=48, location=(3.0, 0, 0.5))
neck_ob = C.active_object
tloop = [Vector((3.0 + 0.12 * math.cos(a), 0.12 * math.sin(a), 0.3)) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
st.cape_length = 20.0
msg = cd.perform_hang(C, neck_ob, tloop, closed=True)
tob = C.view_layer.objects.active
tco = cd.SIM['surface']
tn = cd.SIM['nb'] // 2
rad = np.hypot(tco[:, 0], tco[:, 1])
h = tco[:, 2]
trim = wl.boundary_verts(tob.data)
check('Tube: a vertical cylinder from the loop straight up by Length (every point at the loop radius + gap, no taper)',
      tob.name.startswith('Neck Cloth') and rad.max() - rad.min() < 0.01 and abs((h.max() - h.min()) - cd._hang_args(neck_ob, st)[4]) < cd._hang_args(neck_ob, st)[1] * 1.01,
      (rad.min(), rad.max(), h.max() - h.min(), msg))
check('... open only at the bottom and top rings (no side seam); with Pin Top both rings pinned',
      len(trim) == 2 * tn and int((cd.SIM['sess']['cloth'].pin >= 1).sum()) == 2 * tn, (len(trim), tn))
sess_t = cd.SIM['sess']
for _ in range(30):
    cd.advance(sess_t, st)
ct = sess_t['cloth'].co
check('... drapes 30 frames: finite, never inside the neck (radius >= 0.12), the extra fabric folds (not a smooth cylinder any more)',
      np.all(np.isfinite(ct)) and np.hypot(ct[:, 0], ct[:, 1]).min() > 0.12 * math.cos(math.pi / 48) - 1e-3
      and np.hypot(ct[:, 0], ct[:, 1]).std() > 0.002, (np.hypot(ct[:, 0], ct[:, 1]).min(), np.hypot(ct[:, 0], ct[:, 1]).std()))
cd.cancel(C)
st.neck_pin_top = False
cd.perform_hang(C, neck_ob, tloop, closed=True)
check('Pin Top off: only the bottom ring pinned', int((cd.SIM['sess']['cloth'].pin >= 1).sum()) == cd.SIM['nb'] == tn)
# 0.24.95 set the shape first (user: "위 고리랑 아래 고리 사이즈를 다르게 ... 원기둥 사이즈랑 위아래 고리를 먼저 정하고 그 다음에 시뮬")
tob = C.view_layer.objects.active
st.neck_top = 100.0                                     # (the slider's update: the waiting tube follows right away)
tc = mio.read_co(tob.data)
r_bot = np.hypot(tc[:tn, 0], tc[:tn, 1]).mean()
r_top = np.hypot(tc[-tn:, 0], tc[-tn:, 1]).mean()
check('Top Size 100: the waiting tube follows the slider at once - a cone, the top ring about twice the neck radius wider',
      r_top > r_bot + 0.1 and not cd.SIM['running'] and np.ptp(np.linalg.norm(tc - cd.SIM['surface'], axis=1)) < 1e-6, (r_bot, r_top))
st.neck_bottom = -50.0
tc = mio.read_co(tob.data)
check('Bottom Size -50: smaller, but never inside the neck', np.hypot(tc[:tn, 0], tc[:tn, 1]).min() > 0.12 * math.cos(math.pi / 48) - 1e-6,
      np.hypot(tc[:tn, 0], tc[:tn, 1]).min())
cd.restart(C)
check('Space after setting the shape: the drape starts from it (frame 0, the cloth on the new shape)',
      cd.SIM['running'] and cd.SIM['sess']['frame'] == 0 and len(cd.SIM['sess']['cloth'].co) == len(tob.data.vertices))
st.neck_top, st.neck_bottom = 0.0, 0.0
cd.cancel(C)
st.neck_pin_top, st.cape_length = True, 50.0
bpy.data.objects.remove(neck_ob)
st.neck_style = 'RING'                                   # (the ring checks below)
loop = [Vector((0.8 * math.cos(a), 0.8 * math.sin(a), 0.6)) for a in np.linspace(0, 2 * math.pi, 24, endpoint=False)]
msg = cd.perform_hang(C, ball, loop, closed=True)
ob = C.view_layer.objects.active
me = ob.data
rim = wl.boundary_verts(me)
nb = cd.SIM['nb']
co = cd.SIM['surface']
inner = set(range(nb))
check('Neck Cloth: a flat ring round the loop - only the neck ring and the outer hem are open (no side seam)',
      ob.name.startswith('Neck Cloth') and cd.SIM['source'] == 'NECK' and inner <= set(rim.tolist()) and len(rim) > nb * 1.5
      and len(me.polygons) > 100, (len(rim), nb, msg))
el = np.array([(co[e.vertices[0]] - co[e.vertices[1]]) for e in me.edges])
el = np.linalg.norm(el, axis=1)
check('... the cells stay even out to the hem (more points on every ring: longest edge under 2.5 x the median)',
      el.max() < 2.5 * np.median(el), (el.min(), np.median(el), el.max()))
r_top = np.hypot(co[:nb, 0], co[:nb, 1]).mean()
r_all = np.hypot(co[:, 0], co[:, 1])
check('... it reaches out past the shoulders (the hem ring farther out than the neck by about Length), every point outside the ball',
      r_all.max() > r_top + 0.5 and np.linalg.norm(co, axis=1).min() > 0.99, (r_top, r_all.max(), np.linalg.norm(co, axis=1).min()))
sess = cd.SIM['sess']
for _ in range(30):
    cd.advance(sess, st)
check('... drapes 30 frames: finite, outside the ball', np.all(np.isfinite(sess['cloth'].co)) and np.linalg.norm(sess['cloth'].co, axis=1).min() > 0.98,
      np.linalg.norm(sess['cloth'].co, axis=1).min())
cd.cancel(C)
st.neck_style = 'TUBE'

# ---- Surface mode: clicked points on the ball (front view), Mode Cape
FRONT = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(90)))
sl.make_projector = lambda region, rv3d: FRONT


class Ctx:
    def __init__(self):
        self.area = types.SimpleNamespace(type='VIEW_3D', header_text_set=lambda t: None, tag_redraw=lambda: None)
        self.region = types.SimpleNamespace(width=1000, height=1000)
        self.region_data = object()

    scene = property(lambda self: bpy.context.scene)
    view_layer = property(lambda self: bpy.context.view_layer)
    selected_objects = property(lambda self: bpy.context.selected_objects)
    collection = property(lambda self: bpy.context.scene.collection)
    preferences = property(lambda self: bpy.context.preferences)

    def evaluated_depsgraph_get(self):
        return bpy.context.evaluated_depsgraph_get()


S.mch_brush.surface_mode = True
st.drape_mode = 'CAPE'
ctx, op = Ctx(), sl.SurfaceLogic()
op.start(ctx, (440, 550), 'CDRAPE')
for xy in [(500, 560), (560, 550)]:
    op.click(ctx, xy)
parts, msg = op.finish(ctx)
ob = C.view_layer.objects.active
check('Surface + Mode Cape: 3 clicked points on the body hang a cape from them (open line, not closed)',
      parts is not None and ob is not None and ob.name.startswith('Cloth Cape') and cd.SIM.get('closed') is False, msg)
if cd.sim_active():
    cd.cancel(C)
S.mch_brush.surface_mode = False
st.drape_mode = 'AREA'
check('The lasso tool hands Cape / Neck Cloth the drawn path itself in Line mode (not its band)',
      "dst.drape_mode in {'CAPE', 'NECK'} and self._line_mode()" in inspect.getsource(ce))
check('Panel: Mode row and Length / Flare', "'drape_mode', expand=True" in inspect.getsource(cd.draw) and "'cape_length'" in inspect.getsource(cd.draw))
check('cloth_pbd.tethers: free points tied to the nearest pinned one along the cloth', cloth_pbd.tethers(
      np.array([[0, 0, 0], [1, 0, 0], [2, 0, 0.]]), np.array([[0, 1], [1, 2]]), np.array([1.0, 0, 0]))[2].tolist() == [1.0, 2.0])
summary()
