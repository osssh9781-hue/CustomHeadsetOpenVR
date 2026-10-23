"""0.24.20 Bridge Patch: lasso across two meshes, the gap between them fills with a smooth patch on the side you see
(front only), its rim sunk into both meshes; Smooth / Bulge / Round / Wrap / Thickness / Sink / Overlap / Resolution live."""
import math

from _harness import bpy, check, fresh, non_manifold, summary, volume
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import bridge_patch as bp, core_geometry as cg

TOP = cg.OrthoProjector(Quaternion())                  # 100 px = 1 unit, looking down -Z
C = bpy.context
mecha_lab.register()

# pure: a chain 0 - 1 - ... - 10, the ends held
chain = [(i, i + 1) for i in range(10)]
target = [0.0] + [None] * 9 + [10.0]
weight = [1.0] + [0.0] * 9 + [1.0]
h = bp.soft_fill(11, chain, target, weight, smooth=0.0, stiff=1e6)
check('soft_fill harmonic: a straight join between the held ends', all(abs(h[i] - i) < 1e-3 for i in range(11)),
      [round(x, 3) for x in h])
# held points 0, 1 (slope 1) and 9, 10 (slope 1, offset): biharmonic keeps the slope across
target = [0.0, 1.0] + [None] * 7 + [9.0, 10.0]
weight = [1.0, 1.0] + [0.0] * 7 + [1.0, 1.0]
b = bp.soft_fill(11, chain, target, weight, smooth=1.0, stiff=1e6)
check('soft_fill biharmonic: the slope carries on across the gap', all(abs(b[i] - i) < 1e-2 for i in range(11)),
      [round(x, 3) for x in b])
bmp = bp.bump(11, chain, {0: 0.0, 10: 0.0})
check('bump: 0 at the held ends, 1 in the middle', bmp[0] == 0.0 and bmp[10] == 0.0 and abs(max(bmp) - 1.0) < 1e-9
      and bmp.index(max(bmp)) == 5)
g = bp.spread(11, chain, [1.0] + [0.0] * 10, 3)
check('spread: blurs a value to its neighbours, fading', g[0] > g[1] > g[2] > g[3] > 0 and g[5] == 0.0)


def lumps():
    fresh()
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32, location=(0.1, 1.55, 0))
    a = C.active_object
    a.scale = (0.7, 1.2, 0.6)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1, segments=64, ring_count=32, location=(-0.2, -1.65, 0))
    b_ = C.active_object
    b_.scale = (0.9, 1.3, 0.7)
    for o in (a, b_):
        for x in C.selected_objects:
            x.select_set(False)
        o.select_set(True)
        C.view_layer.objects.active = o
        bpy.ops.object.transform_apply(scale=True)
    return a, b_


LASSO = [(460, 620), (570, 620), (565, 520), (560, 420), (545, 330), (430, 380), (445, 470), (450, 540)]


def front_z(xy):
    """Height of the first thing the view ray meets at a screen point."""
    o, d = TOP.ray(xy)
    hit, loc, _n, _i, ob, _m = C.scene.ray_cast(C.evaluated_depsgraph_get(), Vector(o), Vector(d))
    return (loc.z, ob.name) if hit else (None, None)


a, b_ = lumps()
gap_xy = (500, 500)                                 # world (0, 0): between the two lumps
check('the gap is empty before', front_z(gap_xy)[0] is None)
C.scene.mch_bridge.round = 0.0                   # a flat sheet first (Round tested below)
C.scene.mch_bridge.fill = 0.0
msg = bp.perform(C, [LASSO], TOP)
ob = C.active_object
check('patch made', ob is not None and ob.get(bp.SRC_KEY) is not None, msg)
check('patch is a closed solid', non_manifold(ob) == 0, non_manifold(ob))
z, name = front_z(gap_xy)
check('the gap is covered by the patch, in front', name == ob.name and z is not None and z > -0.05, (z, name))
z_up, name_up = front_z((505, 540))           # just below the upper lump's tip: steep side, the patch covers it
check('the steep side near a lump is covered like a skin', name_up == ob.name, name_up)
z_far, name_far = front_z((505, 600))          # on the upper lump where it faces the view: the lump shows
check('where the lump faces you, the lump shows (the patch rim is under it)', name_far == a.name, name_far)
p = ob.mch_bridge
z0 = front_z(gap_xy)[0]
p.bulge = 0.8
z1 = front_z(gap_xy)[0]
check('Bulge + pushes the middle of the gap toward you', z1 is not None and z1 > z0 + 0.02, (z0, z1))
p.bulge = -0.8
z2 = front_z(gap_xy)[0]
check('Bulge - pulls it in', z2 is not None and z2 < z0 - 0.02, (z0, z2))
p.bulge = 0.0
side_xy = (462, 500)                                # near the lasso's side, in the gap
zc0, zs0 = front_z(gap_xy)[0], front_z(side_xy)[0]
p.round = 1.0
zc1, zs1 = front_z(gap_xy)[0], front_z(side_xy)[0]
check('Round: a round neck - the middle comes forward, the sides curve back', zs1 is not None and zc1 is not None
      and zc1 > zc0 + 0.2 and zs1 < zc1 - 0.1, (zc0, zc1, zs0, zs1))
check('Round: still a closed solid', non_manifold(ob) == 0)
def back_under(xy):
    o, d = TOP.ray(xy)
    o = Vector(o) + Vector(d) * 999.5          # start just above the scene, look down through everything
    zs = []
    for _k in range(10):
        hit, loc, _n, _i, hob, _m = C.scene.ray_cast(C.evaluated_depsgraph_get(), o, Vector(d))
        if not hit:
            break
        if hob == ob:
            zs.append(loc.z)
        o = loc + Vector(d) * 1e-4
    return min(zs) if zs else None
v0 = volume(ob)
p.fill = 1.0
v1 = volume(ob)
check('Fill: a solid reaching into the meshes (much more volume than the sheet)', v1 > 2.0 * v0, (v0, v1))
check('Fill: closed solid', p.last_error == '' and non_manifold(ob) == 0)
bz = back_under(gap_xy)
zc = front_z(gap_xy)[0]
check('Fill: the back mirrors the front about the meshes\' middle (a full round neck)', bz is not None and zc is not None
      and abs(bz + zc) < 0.15, (zc, bz))
for k, v in (('smooth', 0.0), ('quality', 'HIGH'), ('quality', 'LOW'), ('thickness', 0.08), ('overlap', 6),
             ('wrap', math.radians(70)), ('sink', 2.0)):
    setattr(p, k, v)
    check(f'{k} = {v}: rebuilt, closed', p.last_error == '' and non_manifold(ob) == 0, (p.last_error, non_manifold(ob)))
bpy.ops.mch.bridge_apply()
check('Apply: plain mesh', ob.get(bp.SRC_KEY) is None and not ob.mch_bridge.live)

# errors
a, b_ = lumps()
try:
    bp.perform(C, [[(480, 640), (520, 640), (520, 680), (480, 680)]], TOP)   # all on the upper lump
    check('a lasso fully on one surface is refused', False)
except cg.CutError as ex:
    check('a lasso fully on one surface is refused', 'gap' in str(ex), str(ex))
try:
    bp.perform(C, [[(800, 800), (900, 800), (900, 900), (800, 900)]], TOP)   # nothing there
    check('a lasso over nothing is refused', False)
except cg.CutError as ex:
    check('a lasso over nothing is refused', 'no mesh' in str(ex), str(ex))
check('nothing left behind after a refusal', not [o for o in bpy.data.objects if o.get(bp.SRC_KEY)])
summary()
