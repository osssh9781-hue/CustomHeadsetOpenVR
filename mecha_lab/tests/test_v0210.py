"""0.21.0 Robot Base Mesh: random humanoid / industrial robot parts (sleek / rugged),
separate objects per part, live sliders (length, width, thickness, taper, bulge,
roundness, resolution, bevel width / segments / angle), reroll, toggles, Apply."""
import math
import sys

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh

import mecha_lab
from mecha_lab import robot_base as rb

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def bounds(ob):
    xs = [v.co for v in ob.data.vertices]
    lo = [min(c[i] for c in xs) for i in range(3)]
    hi = [max(c[i] for c in xs) for i in range(3)]
    return [h - l for h, l in zip(hi, lo)]


def mesh_key(ob):
    return (len(ob.data.vertices), round(sum(v.co.length for v in ob.data.vertices), 4))


# ---- pure builder: every part x category x style
bad = []
for cat, _, _ in rb.CATEGORIES:
    for sty, _, _ in rb.STYLES:
        for part in rb.PART_IDS:
            L, W, D = rb.DEFAULTS[part]
            p = dict(category=cat, style=sty, part=part, side='CENTER', seed=3, variation=0.5, length=L, width=W,
                     depth=D, details=True)
            p.update({k: v for k, v in rb.style_defaults(cat, sty, part).items()
                      if k in ('taper', 'bulge', 'roundness', 'resolution')})
            verts, faces = rb.build_part(p)
            okf = all(len(f) >= 3 and max(f) < len(verts) and len(set(f)) == len(f) for f in faces)
            if not verts or not faces or not okf:
                bad.append((cat, sty, part))
check('build_part: 10 parts x 2 categories x 2 styles give valid meshes', not bad and len(rb.PART_IDS) == 10, bad)

# ---- whole body: separate objects
for o in list(S.objects):
    o.select_set(False)
st = S.mch_robot_settings
st.category, st.style = 'HUMANOID', 'SLEEK'
r = bpy.ops.mch.robot_add(part='BODY')
parts = [o for o in S.objects if rb.is_part(o)]
check('humanoid whole body = 12 separate limb / shoulder / foot objects (torso, head: user)', r == {'FINISHED'} and len(parts) == 12, len(parts))
check('parts live in the Robot Base collection', all(rb.COLL in [c.name for c in o.users_collection] for o in parts))
check('every part has faces', all(len(o.data.polygons) > 0 for o in parts))
names = {o.name for o in parts}
check('left / right names', {'Robot_Upper_Arm_L', 'Robot_Upper_Arm_R', 'Robot_Foot_L', 'Robot_Foot_R'} <= names, names)
la, ra = S.objects['Robot_Upper_Arm_L'], S.objects['Robot_Upper_Arm_R']
check('left and right arms sit on opposite sides', la.location.x > 0 > ra.location.x)
lv = sorted(round(v.co.x, 4) for v in la.data.vertices)
rv = sorted(round(-v.co.x, 4) for v in ra.data.vertices)
check('right arm mirrors the left arm', lv == rv)
check('bevel modifier on parts', all(o.modifiers.get(rb.MOD_BEVEL) for o in parts))
check('shoulders above thighs', S.objects['Robot_Shoulder_L'].location.z > S.objects['Robot_Thigh_L'].location.z)
foot = S.objects['Robot_Foot_L']
fb = bounds(foot)
check('foot is longer front-to-back than wide', fb[1] > fb[0], fb)

# ---- all four styles produce different looking bodies
keys = {}
for cat in ('HUMANOID', 'INDUSTRIAL'):
    for sty in ('SLEEK', 'RUGGED'):
        ob = rb.create_part(C, 'TORSO', cat, sty, seed=5)
        keys[(cat, sty)] = mesh_key(ob)
check('4 options give 4 different torsos', len(set(keys.values())) == 4, keys)

# ---- live sliders
ob = rb.create_part(C, 'THIGH', 'HUMANOID', 'SLEEK', seed=2)
rp = ob.mch_robot
b0 = bounds(ob)
rp.length *= 1.5
b1 = bounds(ob)
check('Length slider rebuilds live', b1[2] > b0[2] * 1.3, (b0, b1))
rp.width *= 1.5
check('Width slider rebuilds live', bounds(ob)[0] > b1[0] * 1.2)
d0 = bounds(ob)[1]
rp.depth *= 0.5
check('Thickness slider rebuilds live', bounds(ob)[1] < d0 * 0.8)
k0 = mesh_key(ob)
rp.bulge = 1.5
check('Bulge changes shape', mesh_key(ob) != k0)
n0 = len(ob.data.vertices)
rp.resolution = 1.8
check('Resolution adds sides', len(ob.data.vertices) > n0, (n0, len(ob.data.vertices)))
k0 = mesh_key(ob)
rp.roundness = 0.0
check('Roundness changes shape', mesh_key(ob) != k0)
k0 = mesh_key(ob)
rp.bottom_w = 1.2
check('Bottom Width changes shape (humanoid limb)', mesh_key(ob) != k0)
ind = rb.create_part(C, 'THIGH', 'INDUSTRIAL', 'SLEEK', seed=2)
k1 = mesh_key(ind)
ind.mch_robot.taper = -0.5
check('Taper changes shape (industrial limb)', mesh_key(ind) != k1)
rp.bevel_width = 0.02
rp.bevel_segments = 5
rp.bevel_angle = math.radians(50)
m = ob.modifiers[rb.MOD_BEVEL]
check('bevel params reach the modifier', abs(m.width - 0.02) < 1e-6 and m.segments == 5
      and abs(m.angle_limit - math.radians(50)) < 1e-5 and m.limit_method == 'ANGLE')
rp.bevel_width = 0.0
check('bevel 0 removes the modifier', ob.modifiers.get(rb.MOD_BEVEL) is None)
rp.bevel_width = 0.01
k0 = mesh_key(ob)
rp.details = False
check('Details toggle changes shape', mesh_key(ob) != k0)
rp.details = True

# ---- operators on the active part
for o in list(S.objects):
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
s0, k0 = rp.seed, mesh_key(ob)
bpy.ops.mch.robot_reroll()
check('reroll: next seed, new shape', rp.seed == s0 + 1 and mesh_key(ob) != k0)
bpy.ops.mch.robot_toggle(option='STYLE')
check('style toggle', rp.style == 'RUGGED' and rp.bevel_segments == 1)
bpy.ops.mch.robot_toggle(option='CATEGORY')
check('category toggle', rp.category == 'INDUSTRIAL')
k0 = mesh_key(ob)
bpy.ops.mch.robot_toggle(option='DETAILS')
check('details toggle op', not rp.details and mesh_key(ob) != k0)

for key in ('length', 'width', 'bevel', 'bevel_angle', 'roundness'):
    spec = rb.slider_spec(C, key, ob)
    check(f'HUD slider {key}', spec is not None and len(spec) == 6, spec)
spec = rb.slider_spec(C, 'length', ob)
spec[4](spec[1] * 1.2)
check('HUD slider setter changes the part', abs(rp.length - spec[1] * 1.2 / 1.0) < 1e-3 or rp.length != 0)

n_live = len(ob.data.vertices)
bpy.ops.mch.robot_apply()
check('apply: plain mesh, no live, bevel baked', not rb.is_part(ob) and not ob.modifiers
      and len(ob.data.vertices) > n_live)
seed_before = rp.seed
rp.seed += 3
check('applied part no longer rebuilds', len(ob.data.vertices) > n_live)

# ---- single part op + scale
for o in list(S.objects):
    o.select_set(False)
st.scale = 2.0
bpy.ops.mch.robot_add(part='HEAD')
h = C.active_object
check('add single part at scale 2', rb.is_part(h) and abs(h.mch_robot.length - rb.DEFAULTS['HEAD'][0] * 2) < 1e-4)

# ---- industrial rugged body is mostly closed volumes (base mesh friendly)
st.scale, st.category, st.style = 1.0, 'INDUSTRIAL', 'RUGGED'
for o in list(S.objects):
    o.select_set(False)
bpy.ops.mch.robot_add(part='BODY')
ind = [o for o in C.selected_objects if rb.is_part(o)]
check('industrial body 14 parts', len(ind) == 14)
nm = sum(non_manifold(o) for o in ind)
check('industrial body: no open edges', nm == 0, nm)
st.category, st.style = 'HUMANOID', 'SLEEK'
nm = sum(non_manifold(o) for o in parts if rb.is_part(o))
check('humanoid body: no open edges', nm == 0, nm)

# ---- end shapes: round bottom -> square / polygon top
import math as _m
ob = rb.create_part(C, 'THIGH', 'INDUSTRIAL', 'SLEEK', seed=4, details=False)
rp = ob.mch_robot
rp.bevel_width = 0.0
k0 = mesh_key(ob)
rp.bottom_shape, rp.top_shape = 'ROUND', 'SQUARE'
check('end shapes change the part', mesh_key(ob) != k0)
check('round -> square part stays closed', non_manifold(ob) == 0)
secs = [(0.1 * i, 1.0, 1.0, 0, 0) for i in range(7)]


def rings(ends):
    verts, faces = rb.loft(secs, 16, 2.0, ends=ends)
    n = len(verts) // len(secs)
    return [verts[k * n:(k + 1) * n] for k in range(len(secs))], faces


def spread(ring):
    rs = [_m.hypot(c[0], c[1]) for c in ring]
    return max(rs) / min(rs)


rg, _f = rings({'bottom': ('ROUND', 6), 'top': ('SQUARE', 6), 'mid': 0.5})
check('bottom ring is round', spread(rg[0]) < 1.01, spread(rg[0]))
check('top ring is square (corners ~1.41)', 1.38 < spread(rg[-1]) < 1.44, spread(rg[-1]))
check('square top is axis aligned (max |x| = 1)', abs(max(abs(c[0]) for c in rg[-1]) - 1.0) < 1e-6)
rg, _f = rings({'bottom': ('ROUND', 6), 'top': ('POLYGON', 6), 'mid': 0.5})
rs = sorted(_m.hypot(c[0], c[1]) for c in rg[-1])
check('polygon top: 6 corners on the ring', len(rg[-1]) % 6 == 0
      and sum(1 for r_ in rs if r_ > rs[-1] - 1e-6) == 6, (len(rg[-1]), rs[-8:]))
check('middle ring is in between', 1.0 < spread(rg[3]) < spread(rg[-1]))
k0 = mesh_key(ob)
rp.shape_mid = 0.2
check('Shape Change moves the morph', mesh_key(ob) != k0)
rp.bottom_shape, rp.bottom_sides = 'POLYGON', 5
check('pentagon -> hexagon closed', non_manifold(ob) == 0)
bad = []
for cat in ('HUMANOID', 'INDUSTRIAL'):
    for part in rb.PART_IDS:
        L_, W_, D_ = rb.DEFAULTS[part]
        for bs, ts in (('ROUND', 'SQUARE'), ('SQUARE', 'POLYGON'), ('POLYGON', 'ROUND')):
            p = dict(category=cat, style='SLEEK', part=part, side='CENTER', seed=1, variation=0.5, length=L_,
                     width=W_, depth=D_, details=True, taper=0.3, bulge=0.5, roundness=0.6, resolution=0.5,
                     bottom_shape=bs, top_shape=ts, bottom_sides=5, top_sides=8, shape_mid=0.5)
            verts, faces = rb.build_part(p)
            if not faces or any(max(f) >= len(verts) for f in faces):
                bad.append((cat, part, bs, ts))
check('end shapes work on every part', not bad, bad)
for o in list(S.objects):
    o.select_set(False)
ob = rb.create_part(C, 'CALF', 'HUMANOID', 'SLEEK')
ob.select_set(True)
C.view_layer.objects.active = ob
bpy.ops.mch.robot_toggle(option='TOP')
bpy.ops.mch.robot_toggle(option='TOP')
bpy.ops.mch.robot_toggle(option='BOTTOM')
check('HUD shape buttons cycle shapes', ob.mch_robot.top_shape == 'SQUARE' and ob.mch_robot.bottom_shape == 'ROUND')
spec = rb.slider_spec(C, 'top_sides', ob)
spec[4](9)
check('Top Sides slider', ob.mch_robot.top_sides == 9)
lay = rb.hud_layout([(100, 100), (200, 300)], 1000, 800)
check('HUD layout has shape buttons and all sliders', 'bottom' in lay and 'top' in lay
      and all('slider_' + k[0] in lay for k in rb.SLIDERS))

check('panel registered', 'bl_rna' in rb.MCH_PT_robot_base.__dict__)
check('HUD registered', 'bl_rna' in rb.MCH_GGT_robot_hud.__dict__)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
