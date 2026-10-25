"""0.24.32 Concept Move: grab-and-pull in Object Mode (VR move tool feel) - falloffs, mirror X, clay keeps the
grabbed lump's thickness, Keep Density splits stretched edges, tool + operator registered."""
import math

from _harness import bpy, check, fresh, summary
import numpy as np

import mecha_lab
from mecha_lab import concept_move as cm

mecha_lab.register()
fresh()
C = bpy.context

d = np.array([0.0, 0.5, 1.0, 2.0, 5.0])
w = cm.clay_weights(d, 1.0)
check('clay: the middle moves whole, fades to 0 past the edge', w[0] == 1.0 and w[1] == 1.0 and w[-1] == 0.0
      and w[2] < 1.0, w.tolist())
s, t = cm.elastic_weights(np.array([0.0, 10.0]), 1.0)
check('elastic: exactly the drag at the centre, nothing far away', abs(s[0] - 1.0) < 1e-9 and s[1] == 0.0, (s.tolist(), t.tolist()))
ws = cm.smooth_weights(np.array([0.0, 0.5, 1.0]), 1.0)
wsh = cm.smooth_weights(np.array([0.5]), 1.0, sharp=True)
check('smooth: 1 -> 0 inside the circle; sharp is tighter', ws[0] == 1.0 and ws[2] == 0.0 and wsh[0] < ws[1])
co = np.array([[1.0, 0, 0], [-1.0, 0, 0], [0, 0, 3.0]])
new = cm.displace(co, (1.0, 0, 0), (0.5, 0, 0), 0.4, 'CLAY', mirror_x=True)
check('mirror X: the other side moves the mirrored way, far points stay',
      abs(new[0, 0] - 1.5) < 1e-9 and abs(new[1, 0] + 1.5) < 1e-9 and (new[2] == co[2]).all(), new.tolist())
new = cm.displace(co, (1.0, 0, 0), (0.5, 0, 0), 0.4, 'CLAY', mirror_x=False)
check('mirror off: only one side', abs(new[1, 0] + 1.0) < 1e-9)

bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0)
ob = C.active_object
me = ob.data
before = cm.read_coords(me)
side = before[:, 0] > 0.95                     # within the core (0.55 x 0.6) of the grab
thick0 = np.ptp(before[side][:, 1])
after = cm.displace(before, (1.0, 0, 0), (2.0, 0, 0), 0.6, 'CLAY', mirror_x=False)
cm.write_coords(me, after)
moved = after[side][:, 0] - before[side][:, 0]
check('clay pull: the grabbed lump moved out whole (keeps its thickness)', moved.min() > 1.9
      and abs(np.ptp(after[side][:, 1]) - thick0) < 1e-6, (moved.min(), thick0))
n0 = len(me.vertices)
n = cm.keep_density(me, before, after, 0.6)
check('Keep Density: stretched edges split (more verts), still one piece', n > 0 and len(me.vertices) > n0,
      (n, n0, len(me.vertices)))
check('Concept Move operator + tool registered', hasattr(bpy.types, 'MCH_OT_concept_move')
      and hasattr(C.scene, 'mch_concept') and C.scene.mch_concept.falloff == 'CLAY')
summary()
