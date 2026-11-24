"""0.24.306 (user: "타이어 제네레이터도 메뉴로 빼주고 거기에 톱니도 추가해줘 그리고 근육 붙이는거에 양끝이 더 두꺼운 크리쳐
살점 모양도 만들어주라"): Tire & Gear its own tool (enum 92, Block-out), a Gear (teeth, depth, tooth width, Square /
Trapezoid / Round / Saw, hole) live on its sliders and a target for Array Around; the muscle's Flesh (thick ends)."""
import math

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import muscle_gen as mg, tire_gen as tg, tool_state as ts, ui_tool_settings as uts

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

row = ts.TOOL_BY_ID.get('TIREGEN')
check('Tire & Gear is a tool of its own (Block-out, enum 92, workspace tool, its window)',
      row is not None and row[5] == 'mecha.tire_gear' and 'TIREGEN' in dict(ts.TOOL_GROUPS)['Block-out']
      and ts._ENUM_NUMBERS['TIREGEN'] == 92 and 'TIREGEN' in uts.DRAWERS)
check('the enum numbers stay unique', len(set(ts._ENUM_NUMBERS.values())) == len(ts._ENUM_NUMBERS))
check('Block-out keeps its old order (Tire & Gear last)',
      dict(ts.TOOL_GROUPS)['Block-out'][:6] == ('BASE', 'MBASE', 'CBASE', 'OMASS', 'SUBD', 'PRIMITIVE'))


def stats(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    nm = sum(1 for e in bm.edges if not e.is_manifold)
    vol = bm.calc_volume(signed=True)
    bm.free()
    return nm, vol


def radii(ob):
    V = np.array([v.co[:] for v in ob.data.vertices])
    return np.hypot(V[:, 1], V[:, 2]), V


st = S.mch_tire
st.gear_teeth, st.gear_diameter, st.gear_thick, st.gear_depth, st.gear_hole = 20, 0.5, 0.08, 0.12, 0.25
bpy.ops.mch.tire_add(kind='GEAR')
g = C.active_object
r, V = radii(g)
nm, vol = stats(g)
check(f'Summon Gear: a closed gear at the cursor, axle along X ({nm} open edges, volume {vol:.4f})',
      tg.kind_of(g) == 'GEAR' and nm == 0 and vol > 0 and abs(r.max() - 0.25) < 1e-4
      and abs((V[:, 0].max() - V[:, 0].min()) - 0.08) < 1e-5, (nm, vol, r.max()))
check('... its hole (a quarter of the root circle)', abs(r.min() - 0.25 * 0.25 * (1 - 0.12)) < 1e-4, r.min())
check('... its teeth reach in to the root circle (depth of the radius)', abs(np.sort(np.unique(np.round(r, 5)))[-1]
                                                                          - 0.25) < 1e-4 and
      np.any(np.abs(r - 0.25 * (1 - 0.12)) < 1e-4))


def teeth_of(ob):
    """How many teeth: runs of outline points at the tip radius, round the gear."""
    r_, V_ = radii(ob)
    R = r_.max()
    on = [math.atan2(v[2], v[1]) for v, rr in zip(V_, r_) if rr > R - 1e-5 and v[0] > 0]
    a = np.sort(np.mod(on, 2 * math.pi))
    gaps = np.diff(np.concatenate([a, [a[0] + 2 * math.pi]]))
    return int(np.sum(gaps > gaps.max() * 0.9)) if len(a) else 0   # (the gaps between teeth: all the same)


check('20 teeth', teeth_of(g) == 20, teeth_of(g))
st.gear_teeth = 33
check('Teeth 33: the selected gear changes live', teeth_of(g) == 33, teeth_of(g))
st.gear_diameter = 1.0
check('Gear Diameter: live', abs(radii(g)[0].max() - 0.5) < 1e-4)
st.gear_depth = 0.3
check('Tooth Depth: the root circle deeper', np.any(np.abs(radii(g)[0] - 0.5 * 0.7) < 1e-4))
for shp in ('SQUARE', 'TRAPEZOID', 'ROUND', 'SAW'):
    st.gear_shape = shp
    nm, vol = stats(g)
    check(f'{shp} teeth: closed, right way out ({nm} open edges)', nm == 0 and vol > 0 and teeth_of(g) == 33,
          (nm, vol, teeth_of(g)))
st.gear_shape = 'TRAPEZOID'
f_ = len(g.data.polygons)
st.gear_hole = 0.0
nm, vol = stats(g)
check('Hole 0: a solid gear, closed', nm == 0 and vol > 0 and radii(g)[0].min() < 1e-6 or nm == 0 and vol > 0,
      (nm, vol))
st.gear_hole = 0.25
w_before = st.width
st.width = 0.5                                   # (a tire slider: the gear stays as it is)
check('a Tire slider leaves a gear alone', len(g.data.polygons) == f_)
st.width = w_before

# Array Around a gear: a piece on its rim goes round it
bpy.ops.mesh.primitive_cube_add(size=0.04, location=(0.0, 0.0, 0.52))
pc = C.active_object
g.select_set(True)
pc.select_set(True)
C.view_layer.objects.active = pc
st.count = 12
bpy.ops.mch.tire_array()
check('Array Around: a piece drawn on a gear goes round its axle', pc.get(tg.ARR) == g.name and
      pc.modifiers.get(tg.MOD_ARRAY) is not None and pc.modifiers[tg.MOD_ARRAY].count == 12)

# tires as before
for o in list(C.selected_objects):
    o.select_set(False)
bpy.ops.mch.tire_add(kind='TIRE')
t = C.active_object
check('Summon Tire as before (a tire, not a gear)', tg.kind_of(t) == 'TIRE' and stats(t)[0] == 0)

# --- Flesh: thick at both ends -----------------------------------------------------------------------------------
tt = np.linspace(0, 1, 101)
fp = mg.flesh_profile(tt)
check('flesh profile: thick at both ends, thinner between, round shut at the tips',
      fp[20] > 0.95 and fp[80] > 0.95 and fp[50] < 0.7 and fp[0] < 0.1 and fp[100] < 0.1, (fp[0], fp[20], fp[50]))
check('profile with Thick Ends 0: exactly the muscle as before',
      np.allclose(mg.profile(tt, 0.5, 0.15, ends=0.0), mg._profile(tt, 0.5, 0.15)))
check('the old presets keep Thick Ends 0 (a muscle as before)',
      all(p[4].get('ends', 0.0) == 0.0 for p in mg.PRESETS if p[0] != 'FLESH'))
check('Flesh (Thick Ends) preset (after the others: their buttons where they were)',
      mg.PRESET['FLESH'][3] == 'LINE' and mg.PRESET['FLESH'][4]['ends'] == 1.0
      and [p[0] for p in mg.PRESETS][-2:] == ['FLESH', 'MEMBRANE'])

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32, location=(5, 0, 0))
body = C.active_object
body.scale = (0.5, 0.5, 1.6)
bpy.ops.object.transform_apply(scale=True)


def pt(z):
    d = Vector((0.0, -1.0, 0.0))
    p = Vector((5.0, 0.0, z)) - d * 2.0
    ok, loc, nrm, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), p, d)
    return (body.name, tuple(loc), tuple(nrm))


A, B = pt(0.8), pt(-0.8)
mst = mg.settings(C, 'MUSCLE')
mst.preset = 'FLESH'
mst.shape = 'STRANDS'
mst.style = 'CREATURE'
m, _msg = mg.make(C, 'MUSCLE', [A, B])
check('Flesh preset: a lump made between the points', m is not None and m.mch_muscle.ends == 1.0
      and len(m.data.polygons) > 100)


def girth(ob):
    """Its thickness off the body at the near end, the middle and the far end (along Z)."""
    V = np.array([(ob.matrix_world @ v.co)[:] for v in ob.data.vertices])
    z = V[:, 2]
    lo, hi = z.min(), z.max()
    out = []
    for f in (0.2, 0.5, 0.8):
        zz = lo + (hi - lo) * f
        sel = V[np.abs(z - zz) < (hi - lo) * 0.04]
        out.append(float(sel[:, 0].max() - sel[:, 0].min()) if len(sel) else 0.0)
    return out


g0 = girth(m)
check(f'... thicker at both ends than in the middle (widths {g0[0]:.3f} / {g0[1]:.3f} / {g0[2]:.3f})',
      g0[0] > g0[1] * 1.2 and g0[2] > g0[1] * 1.2, g0)
m.mch_muscle.ends = 0.0
g1 = girth(m)
check(f'Thick Ends 0 live: a muscle again (thickest in the middle {g1})', g1[1] > g1[0] and g1[1] > g1[2], g1)
summary()
