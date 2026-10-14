"""0.21.2 Robot base: humanoid Chest (ribs) / Pelvis / Head from the user's measured
segments with 8 region sliders + Anatomy Detail; bulge shape (round -> cylinder ->
square) and width; top and bottom V notch; end holes (size / depth, through = tube);
much wider slider ranges."""
import math
import sys

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh

import mecha_lab
from mecha_lab import robot_base as rb, robot_templates as rt

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def key(ob):
    return round(sum(abs(v.co.x) * 3 + abs(v.co.y) * 7 + v.co.z * 11 + v.co.x * 0.3 + v.co.y * 0.7
                     for v in ob.data.vertices), 6)


def vol(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def euler(ob):
    return len(ob.data.vertices) - len(ob.data.edges) + len(ob.data.polygons)


check('templates: chest / pelvis / head rings', all(len(rt.RINGS[k]) >= 16 and len(rt.RINGS[k][0]) == 2 + rt.NA
                                                    for k in ('CHEST', 'PELVIS', 'HEAD')))
check('template radii mirrored left / right', all(abs(r[2 + i] - r[2 + rt.NA // 2 - 1 - i]) < 0.05
                                                  for r in rt.RINGS['CHEST'] for i in range(rt.NA // 2)))
check('0.22.1 humanoid panel: no torso / chest / pelvis / head (user models them)',
      not {'TORSO', 'CHEST', 'PELVIS', 'HEAD'} & set(rb.UI_PARTS['HUMANOID']))

for part in ('CHEST', 'PELVIS', 'HEAD'):
    ob = rb.create_part(C, part, 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
    rp = ob.mch_robot
    check(f'{part}: template builder', rb.is_template(rp))
    check(f'{part}: closed, normals out', non_manifold(ob) == 0 and vol(ob) > 0, (non_manifold(ob), vol(ob)))
    L, W, D = rt.SIZES[part]
    dims = ob.dimensions
    check(f'{part}: measured size', abs(dims.z - L) < L * 0.12 and abs(dims.x - W) < W * 0.2
          and abs(dims.y - D) < D * 0.3, (tuple(round(x, 3) for x in dims), (L, W, D)))
    keys = rb.slider_keys(rp)
    check(f'{part}: HUD has anatomy + 8 regions + ends', 'anatomy' in keys and all(k in keys for k in rb.REGION_KEYS)
          and 'hole_top' in keys and 'notch_b' in keys)
    labels = [rb.slider_spec(C, k, ob)[0] for k in rb.REGION_KEYS]
    check(f'{part}: region labels', labels == [r[0] for r in rb.REGIONS[part]], labels)
    for k in rb.REGION_KEYS + ('anatomy',):
        k0 = key(ob)
        setattr(rp, k, 2.5 if k != 'anatomy' else 0.0)
        if not check(f'{part}: {k} changes the shape', key(ob) != k0):
            break
    check(f'{part}: still closed after extreme regions', non_manifold(ob) == 0 and vol(ob) > 0)
    k0 = key(ob)
    rp.style = 'RUGGED'
    check(f'{part}: style switch rebuilds', key(ob) != k0)

ob = rb.create_part(C, 'CHEST', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
w0 = ob.dimensions.x
ob.mch_robot.rg1 = 3.0
check('chest: Shoulder Width x3 makes it much wider', ob.dimensions.x > w0 * 1.5, (w0, ob.dimensions.x))
ob = rb.create_part(C, 'HEAD', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
fz = [v.co for v in ob.data.vertices]
front = max(v.y for v in fz)
back = -min(v.y for v in fz)
check('head faces +Y (nose side further out)', front > 0 and front != back)

# bulge: bigger range, shape round -> cylinder -> square
lim = rb.create_part(C, 'FOREARM', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
rp = lim.mch_robot
rp.bulge = 5.0
check('bulge up to 600 %', abs(rp.bulge - 5.0) < 1e-6 and lim.dimensions.x > rp.width * 1.8, lim.dimensions.x)
k_round = key(lim)
rp.bulge_shape = 1.0
k_cyl = key(lim)
rp.bulge_shape = 2.0
k_sq = key(lim)
check('bulge shape: round / cylinder / square all differ', len({k_round, k_cyl, k_sq}) == 3)
zs = sorted(v.co.z for v in lim.data.vertices)


def width_at(z):
    xs = [v.co.x for v in lim.data.vertices if abs(v.co.z - z) < rp.length * 0.02]
    return max(xs) - min(xs) if xs else 0


check('cylinder bulge: flat band, round bulge: soft swell',
      rb._bulge_curve(0.62, 0.5, 0.2, 1.0) > 0.95 and rb._bulge_curve(0.62, 0.5, 0.2, 0.0) < 0.75)
rp.bulge_shape, rp.bulge_pos, rp.bulge_width = 1.0, 0.5, 0.2
k0 = key(lim)
rp.bulge_width = 0.5
check('bulge width slider', key(lim) != k0)
check('extreme bulge stays closed', non_manifold(lim) == 0 and vol(lim) > 0)

# notches top + bottom
lim = rb.create_part(C, 'UPPER_ARM', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
rp = lim.mch_robot
bottom0 = min(v.co.z for v in lim.data.vertices if abs(v.co.x) < 0.003)
rp.notch_b, rp.notch_b_width = 0.2, 0.8
bottom1 = min(v.co.z for v in lim.data.vertices if abs(v.co.x) < 0.003)
check('bottom notch lifts the middle of the bottom end', bottom1 > bottom0 + rp.length * 0.1, (bottom0, bottom1))
rp.notch = 0.2
top1 = max(v.co.z for v in lim.data.vertices if abs(v.co.x) < 0.003)
check('top notch lowers the middle of the top end', top1 < -rp.length * 0.1, top1)
check('both notches: closed', non_manifold(lim) == 0 and vol(lim) > 0)

# holes
for part in ('FOREARM', 'CHEST'):
    ob = rb.create_part(C, part, 'HUMANOID', 'SLEEK', seed=1, variation=0.0, details=False)
    rp = ob.mch_robot
    v_full = vol(ob)
    rp.hole_top, rp.hole_top_d = 0.6, 0.4
    check(f'{part}: top hole = closed pocket, less volume', non_manifold(ob) == 0 and 0 < vol(ob) < v_full * 0.95
          and euler(ob) == 2, (vol(ob), v_full, euler(ob)))
    rp.hole_bot, rp.hole_bot_d = 0.5, 0.3
    check(f'{part}: holes in both ends (not through)', non_manifold(ob) == 0 and euler(ob) == 2)
    rp.hole_top_d, rp.hole_bot_d = 0.5, 0.5
    check(f'{part}: depths meet -> through hole (tube, genus 1)', non_manifold(ob) == 0 and euler(ob) == 0
          and vol(ob) > 0, (euler(ob), vol(ob)))
    rp.hole_top = 0.0
    check(f'{part}: size 0 -> no through hole', euler(ob) == 2)

# rugged / industrial chest + pelvis
for cat in ('HUMANOID', 'INDUSTRIAL'):
    for part in ('CHEST', 'PELVIS'):
        ob = rb.create_part(C, part, cat, 'RUGGED', seed=3, details=True)
        check(f'{cat} {part} rugged builds', len(ob.data.polygons) > 10 and non_manifold(ob) == 0)

# whole body
for o in list(S.objects):
    o.select_set(False)
S.mch_robot_settings.category = 'HUMANOID'
bpy.ops.mch.robot_add(part='BODY')
names = {o.name for o in C.selected_objects}
check('0.22.1 humanoid body: no torso / chest / pelvis / head', not any(
    n.startswith(p) for n in names for p in ('Robot_Chest', 'Robot_Pelvis', 'Robot_Head', 'Robot_Torso')),
      sorted(names)[:6])
S.mch_robot_settings.category = 'INDUSTRIAL'
for o in list(S.objects):
    o.select_set(False)
bpy.ops.mch.robot_add(part='BODY')
check('industrial body keeps the torso', any(o.name.startswith('Robot_Torso') for o in C.selected_objects))

# ranges
for prop, val in (('split', 4.0), ('groove', 4.0), ('ridge', 6.0), ('bottom_w', 5.0), ('notch', 0.6),
                  ('twist', math.radians(720)), ('bow', 4.0), ('rg1', 6.0), ('anatomy', 4.0)):
    rp.part = rp.part
    try:
        setattr(rp, prop, val)
        ok = abs(getattr(rp, prop) - val) < 1e-5
    except (TypeError, ValueError):
        ok = False
    check(f'wide range: {prop} = {val:.2f}', ok)
lay = rb.hud_layout([(300, 300), (400, 500)], 1800, 700, keys=rb.TEMPLATE_SLIDERS)
check('template HUD lays out every slider', all('slider_' + k in lay for k in rb.TEMPLATE_SLIDERS))
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
