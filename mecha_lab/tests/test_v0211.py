"""0.21.1 Humanoid limb base meshes from the user's Genesis 9 segments: forearm /
upper arm / thigh / calf with slider-only shape (bottom width / thickness, taper
start, bulge position / front-back, muscle split + angle, groove, ridge, twist,
bend, top notch, bottom / top slant), no joints, outward normals."""
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


def key(ob):
    return round(sum(abs(v.co.x) * 3 + abs(v.co.y) * 7 + v.co.z * 11 + v.co.x * 0.3 + v.co.y * 0.7
                     for v in ob.data.vertices), 6)


def signed_volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume(signed=True)
    bm.free()
    return v


def extent(ob, axis, zlo, zhi):
    vs = [v.co[axis] for v in ob.data.vertices if zlo <= v.co.z <= zhi]
    return max(vs) - min(vs)


check('scene default: details off (plain base)', S.mch_robot_settings.details is False)
for part in ('FOREARM', 'UPPER_ARM', 'THIGH', 'CALF'):
    ob = rb.create_part(C, part, 'HUMANOID', 'SLEEK', seed=1, variation=0.0, details=False)
    rp = ob.mch_robot
    check(f'{part}: limb builder in use', rb.is_limb(rp))
    check(f'{part}: closed and normals outward', non_manifold(ob) == 0 and signed_volume(ob) > 0,
          (non_manifold(ob), signed_volume(ob)))
    check(f'{part}: defaults from LIMB_SHAPES', all(abs(getattr(rp, k) - v) < 1e-5
                                                   for k, v in rb.LIMB_SHAPES[part].items()))
    check(f'{part}: one single piece (no joints)', len(ob.data.polygons) > 50)
    L = rp.length
    top_w = extent(ob, 0, -L * 0.45, -L * 0.4)
    bot_w = extent(ob, 0, -L * 0.97, -L * 0.93)
    if rp.bottom_w < 1.0:
        check(f'{part}: thinner toward the bottom', bot_w < top_w, (top_w, bot_w))
    for prop, val in (('bottom_w', 1.3), ('bottom_d', 1.3), ('taper_start', 0.7), ('bulge', 1.5),
                      ('bulge_pos', 0.8), ('bulge_offset', -0.9), ('split', 1.0), ('split_angle', 1.0),
                      ('groove', 1.2), ('groove_angle', 2.5), ('ridge', 1.5), ('ridge_angle', 1.0),
                      ('twist', 1.0), ('bow', 0.8), ('bow_angle', 0.3), ('notch', 0.15), ('notch_width', 0.9),
                      ('slant', math.radians(30)), ('top_slant', math.radians(-30))):
        if prop == 'split_angle' and rp.split == 0.0:
            rp.split = 0.5
        if prop == 'ridge_angle' and rp.ridge == 0.0:
            rp.ridge = 1.0
        if prop == 'groove_angle' and rp.groove == 0.0:
            rp.groove = 0.5
        if prop == 'bow_angle' and rp.bow == 0.0:
            rp.bow = 0.5
        if prop == 'notch_width' and rp.notch == 0.0:
            rp.notch = 0.1
        k0 = key(ob)
        setattr(rp, prop, val)
        if not check(f'{part}: slider {prop} changes the mesh', key(ob) != k0):
            break
    check(f'{part}: still closed after all sliders', non_manifold(ob) == 0 and signed_volume(ob) > 0)

# measured proportions (Genesis 9 segments, scaled to 1.8 m)
ob = rb.create_part(C, 'FOREARM', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
rp = ob.mch_robot
L = rp.length
w_top = extent(ob, 0, -L * 0.2, -L * 0.15)
w_bot = extent(ob, 0, -L * 0.9, -L * 0.85)
check('forearm: elbow ~ 9.2 / 24.6 of the length', abs(w_top / L - 0.374) < 0.06, w_top / L)
check('forearm: wrist ~ 0.58 of the elbow width', 0.5 < w_bot / w_top < 0.75, w_bot / w_top)
ob = rb.create_part(C, 'THIGH', 'HUMANOID', 'SLEEK', seed=1, variation=0.0, side='LEFT')
zs = [(v.co.x, v.co.z) for v in ob.data.vertices if v.co.z > -0.12]
inner = max(z for x, z in zs if x < -0.05)
outer = max(z for x, z in zs if x > 0.05)
check('left thigh: hip cut lower on the inner side', inner < outer, (inner, outer))
ob = rb.create_part(C, 'UPPER_ARM', 'HUMANOID', 'SLEEK', seed=1, variation=0.0)
check('upper arm: deeper front-back than wide', ob.mch_robot.depth > ob.mch_robot.width)

# rugged limb = fewer sides; seed / randomness change it
a = rb.create_part(C, 'CALF', 'HUMANOID', 'RUGGED', seed=1)
b = rb.create_part(C, 'CALF', 'HUMANOID', 'SLEEK', seed=1)
check('rugged limb has fewer verts', len(a.data.vertices) < len(b.data.vertices))
k0 = key(b)
b.mch_robot.seed = 7
check('seed changes a limb', key(b) != k0)
k0 = key(b)
b.mch_robot.variation = 0.0
check('randomness 0 changes it again', key(b) != k0)

# end shapes still work on humanoid limbs
b.mch_robot.bottom_shape, b.mch_robot.top_shape = 'ROUND', 'SQUARE'
check('limb with round -> square ends closed', non_manifold(b) == 0 and signed_volume(b) > 0)

# HUD: limb slider set, wrapped into columns when tall
keys = rb.slider_keys(b.mch_robot)
check('limb HUD has the shape sliders', {'bottom_w', 'split_angle', 'groove', 'notch', 'top_slant'} <= set(keys)
      and 'taper' not in keys)
lay = rb.hud_layout([(100, 300), (200, 500)], 1600, 600, keys=keys)
xs = {round(lay['slider_' + k][0]) for k in keys}
check('limb HUD wraps into several columns on a short view', len(xs) >= 2, xs)
check('every slider placed', all('slider_' + k in lay for k in keys))
check('HUD inside the view', all(0 <= p[1] <= 600 for k, p in lay.items()), [p for p in lay.values()][:3])
ind = rb.create_part(C, 'HEAD', 'HUMANOID', 'SLEEK')
check('head keeps the general sliders', 'taper' in rb.slider_keys(ind.mch_robot)
      and 'bottom_w' not in rb.slider_keys(ind.mch_robot))
for k in keys:
    spec = rb.slider_spec(C, k, b)
    if spec is None or len(spec) != 6:
        check(f'slider spec {k}', False)
        break
else:
    check('all limb slider specs valid', True)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
