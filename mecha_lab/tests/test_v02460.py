"""0.24.41 Screw Stamp stands straight on faces made of slivers / slightly bent n-gons: the direction is the
plane under the whole head (rays round the hit), not the one (possibly tilted) triangle clicked."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import screw_stamp as ss

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
# a flat panel (z = 0) whose middle is a thin sliver with a tiny bump: that triangle is tilted 45 degrees
v = [(-1, -1, 0), (1, -1, 0), (1, 1, 0), (-1, 1, 0), (-1, 0, 0), (1, 0, 0), (0, 0.004, 0.004)]
f = [(0, 1, 5, 4), (4, 6, 3), (6, 2, 3), (6, 5, 2), (4, 5, 6)]
me = bpy.data.meshes.new('Panel')
me.from_pydata(v, [], f)
me.update()
panel = bpy.data.objects.new('Panel', me)
C.collection.objects.link(panel)
C.view_layer.update()
UP = Vector((0, 0, 1))
tob, loc, nrm = ss.ray_hit(C, Vector((0.0, 0.002, 5)), Vector((0, 0, -1)))
check('the clicked triangle itself is tilted a lot (the case that stood the screw crooked)',
      tob == panel and math.degrees(nrm.angle(UP)) > 30, math.degrees(nrm.angle(UP)))
n = ss.area_normal(C, tob, loc, nrm, 0.05)
check('the plane under the head: nearly straight up', math.degrees(n.angle(UP)) < 5, math.degrees(n.angle(UP)))
S.mch_screw.kind, S.mch_screw.radius = 'CROSS', 0.05
op = ss.MCH_OT_screw_stamp


class Dummy:
    remove = False

    def report(self, *_a):
        pass


r = op.run(Dummy(), C, Vector((0.0, 0.002, 5)), Vector((0, 0, -1)))
screw = C.active_object
axis = (screw.matrix_world.to_3x3() @ UP).normalized()
check('a click there: the screw stands straight on the panel', r == {'FINISHED'} and ss.is_screw(screw)
      and math.degrees(axis.angle(UP)) < 5, math.degrees(axis.angle(UP)))
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, location=(5, 0, 0), segments=48, ring_count=24)
ball = C.active_object
C.view_layer.update()
d = Vector((-1, -0.3, -0.2)).normalized()
tob, loc, nrm = ss.ray_hit(C, Vector((5, 0, 0)) - d * 6, d)
n = ss.area_normal(C, tob, loc, nrm, 0.05)
true = (loc - Vector((5, 0, 0))).normalized()
check('on a ball: still the normal of the ball there (within a few degrees)', tob == ball
      and math.degrees(n.angle(true)) < 3, math.degrees(n.angle(true)))
check('off the edge (fewer than 5 hits): the clicked normal is kept', ss.area_normal(
      C, panel, Vector((0.999, 0.5, 0)), UP, 0.5) == UP)
summary()
