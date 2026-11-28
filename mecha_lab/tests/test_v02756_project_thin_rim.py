"""0.24.356 (user: "끝부분 바지 소매 보면 찌그러지거든 ... 프로젝트를 할수록 좀 더 찌그러지더라고"): Project to Original
on a thin, two-walled edge (a trouser cuff: the outside and the inside a few mm apart) - each point goes only onto a
surface facing its own way (not through to the inner wall), and projecting again does not crumple it more."""
import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import os
import mecha_lab
LOW_R = float(os.environ.get('LOW_R', 0.49))   # (a little inside the outer wall: the inner one is as near)
LOW_D = float(os.environ.get('LOW_D', 2.06))  # (its ends past the cuff's rim)
from mecha_lab import retopo_project as rp

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
# the high: an open tube with a thin wall (Solidify 0.02, rim closed), a bumpy outside
bpy.ops.mesh.primitive_cylinder_add(vertices=96, radius=0.5, depth=2.0, end_fill_type='NOTHING')
hi = C.active_object
hi.name = 'Leg'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode='OBJECT')
tex = bpy.data.textures.new('T', 'CLOUDS'); tex.noise_scale = 0.3
d = hi.modifiers.new('D', 'DISPLACE'); d.texture, d.strength = tex, 0.03
so = hi.modifiers.new('S', 'SOLIDIFY'); so.thickness = 0.02; so.use_rim = True
# the low: a coarse open tube a little off the surface
bpy.ops.mesh.primitive_cylinder_add(vertices=24, radius=LOW_R, depth=LOW_D, end_fill_type='NOTHING')
lo = C.active_object
lo.name = 'Leg_Low'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=3)
bpy.ops.object.mode_set(mode='OBJECT')
tree = rp._high_tree(C, [hi])


def wrong_side():
    """Points that sit on a surface facing away from them (the inner wall) - and the folded faces."""
    M = lo.matrix_world
    me = lo.data
    me.update()
    bad = 0
    for v in me.vertices:
        h = tree.find_nearest(M @ v.co)
        p_ = M @ v.co
        rad = Vector((p_.x, p_.y, 0.0)).normalized()
        if h[0] is not None and h[1].dot(rad) < -0.3:        # (on the inner wall: its surface faces the axis)
            bad += 1
    folds = sum(1 for p in me.polygons if Vector(p.normal).dot(Vector(p.center).normalized() * Vector((1, 1, 0))) < 0.0)
    return bad, folds


def spread():
    co = np.array([v.co[:] for v in lo.data.vertices])
    E = np.array([e.vertices[:] for e in lo.data.edges])
    el = np.linalg.norm(co[E[:, 0]] - co[E[:, 1]], axis=1)
    return float(el.std() / el.mean())


rp.project(C, lo, [hi], relax=2)
b1, f1 = wrong_side()
s1 = spread()
check(f'projected once: (almost) no point on the inner wall ({b1} - before 0.24.356: 221), no folded face ({f1})',
      b1 <= 2 and f1 == 0)
for _i in range(4):
    rp.project(C, lo, [hi], relax=2)
b5, f5 = wrong_side()
s5 = spread()
check(f'projected 5 times: no more on the inner wall ({b5}), none folded ({f5})', b5 <= b1 and f5 == 0)
check(f'... and no more crumpled (edge length spread {s1:.3f} -> {s5:.3f})', s5 <= s1 * 1.15)
summary()
