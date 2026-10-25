"""0.24.32 Concept Move: grab-and-pull in Object Mode (VR move tool feel) - falloffs, mirror X, clay keeps the
grabbed lump's thickness, Keep Density splits stretched edges, tool + operator registered."""
import math

from _harness import bpy, check, fresh, summary
import numpy as np
from mathutils import Vector

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
wh = cm.clay_weights(np.array([0.8]), 1.0, hardness=0.9)[0]
wl = cm.clay_weights(np.array([0.8]), 1.0, hardness=0.1)[0]
wsh = cm.sharp_weights(np.array([0.5]), 1.0)[0]
check('hardness: high = more moves whole; sharp is tight', wh == 1.0 and wl < 0.2 and wsh < 0.2, (wh, wl, wsh))
r = np.array([[0.9, 0.9, 0.0], [0.9, 0.0, 0.0], [1.3, 0.0, 0.0]])
bd = cm.box_distance(r, np.eye(3), round_=0)
check('box brush: the corner of the square counts like its edge (a square, not a circle)',
      abs(bd[0] - 0.9) < 1e-9 and abs(bd[1] - 0.9) < 1e-9 and bd[2] > 1.0, bd.tolist())
sq = np.array([[0.7, 0.7, 0.0], [0.0, 0.0, 0.0]])
nb = cm.displace(sq, (0, 0, 0), (0, 0, 1.0), 1.0, 'CLAY', shape='BOX', hardness=0.75)
ns = cm.displace(sq, (0, 0, 0), (0, 0, 1.0), 1.0, 'CLAY', shape='SPHERE', hardness=0.75)
check('box moves the corner of its square fully, a sphere of the same size does not',
      abs(nb[0, 2] - 1.0) < 1e-6 and ns[0, 2] < 0.9, (nb[0, 2], ns[0, 2]))
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

# real generation: no stretched faces after a long pull
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(6, 0, 0))
g = C.active_object
rest = cm.read_coords(g.data)
e0 = np.median([np.linalg.norm(rest[e.vertices[0]] - rest[e.vertices[1]]) for e in g.data.edges])
mv = {'centre': [1.0, 0, 0], 'delta': [2.0, 0, 0], 'radius': 0.7, 'falloff': 'CLAY', 'hardness': 0.4}
nsplit = cm.generate(g.data, cm.move_field(mv))
co = cm.read_coords(g.data)
lens = np.array([np.linalg.norm(co[e.vertices[0]] - co[e.vertices[1]]) for e in g.data.edges])
check('Generate: the pull is really built (edges split), no edge much longer than the usual',
      nsplit > 0 and lens.max() < e0 * 1.3 * 1.05, (nsplit, float(lens.max()), float(e0)))
check('Generate: the pulled tip reached the target', co[:, 0].max() > 2.9, float(co[:, 0].max()))
# the operator's execute (also what F9 re-runs): object space move on the active object
bpy.ops.mesh.primitive_uv_sphere_add(segments=32, ring_count=16, radius=1.0, location=(-6, 0, 0))
h = C.active_object
r = bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=(0, 0, 1.0), delta=(0, 0, 1.0), radius=0.6, size=1.0,
                             pull=1.5, hardness=0.6, shape='BOX', falloff='CLAY', mirror=False)
zmax = cm.read_coords(h.data)[:, 2].max()
check('operator (F9 values): Pull x1.5 moves the top 1.5 up, Box shape', 'FINISHED' in r and abs(zmax - 2.5) < 0.05,
      (r, float(zmax)))
check('plain mesh: no move record (it is just the mesh)', cm.MOVES_KEY not in h)
a = cm.add_blob(C, (3.0, 0, 0), 0.5, 'ClayA')
b = cm.add_blob(C, (3.6, 0, 0), 0.4, 'ClayB')
check('Add Clay: a round quad ball of the given size', abs(max(a.dimensions) - 1.0) < 0.02
      and all(len(p.vertices) == 4 for p in a.data.polygons))
bname = b.name
f = cm.fuse(C, [a, b], 0.03)
check('Fuse: the blobs become one object, remeshed', f is a and bname not in C.scene.objects
      and len(f.data.polygons) > 100 and f.dimensions.x > 1.3, (f.dimensions.x, len(f.data.polygons)))

from mathutils import Euler
from mecha_lab import core_geometry as cg, hood_gen as hg


def mannequin():
    parts = []

    def add(op, **kw):
        op(**kw)
        parts.append(C.active_object)
    add(bpy.ops.mesh.primitive_uv_sphere_add, radius=1, segments=40, ring_count=20, location=(0, 0, 1.25))
    parts[-1].scale = (0.36, 0.22, 0.5)
    add(bpy.ops.mesh.primitive_uv_sphere_add, radius=0.12, segments=24, ring_count=12, location=(0, -0.02, 1.86))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.06, depth=0.2, location=(0, 0, 1.72))
    add(bpy.ops.mesh.primitive_cylinder_add, radius=0.085, depth=0.95, location=(0, 0, 1.6), rotation=(0, math.pi / 2, 0))
    for o in C.selected_objects:
        o.select_set(False)
    for o in parts:
        o.select_set(True)
    C.view_layer.objects.active = parts[0]
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    bpy.ops.object.join()
    body = C.active_object
    body.scale = (3, 3, 3)
    body.location = (0, 0, -2.7)
    bpy.ops.object.transform_apply(location=True, rotation=True, scale=True)
    return body


body = mannequin()
FRONT = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion())
hg.perform(C, [[(455, 745), (545, 745), (552, 800), (540, 835), (500, 845), (460, 835), (448, 800)]], FRONT)
hood = C.active_object
check('a live hood is a live object', cm.is_live(hood))
top0 = max((hood.matrix_world @ v.co).z for v in hood.data.vertices)
ctr = hood.matrix_world.inverted() @ Vector((0, 0.3, top0))
r = bpy.ops.mch.concept_move('EXEC_DEFAULT', centre=ctr, delta=(0, 0, 0.6), radius=0.35, hardness=0.6,
                             mirror=False)
top1 = max((hood.matrix_world @ v.co).z for v in hood.data.vertices)
check('live hood: pulled up, the move recorded', top1 > top0 + 0.4 and len(cm.recorded_moves(hood)) == 1,
      (top0, top1))
hood.mch_hood.folds = hood.mch_hood.folds + 0.3           # a slider -> the hood is rebuilt
top2 = max((hood.matrix_world @ v.co).z for v in hood.data.vertices)
check('live hood: a slider rebuild keeps the pull (no Apply needed)', top2 > top0 + 0.4, (top0, top2))
r = bpy.ops.mch.concept_clear()
top3 = max((hood.matrix_world @ v.co).z for v in hood.data.vertices)
check('Clear Moves: back to what the sliders make', 'FINISHED' in r and abs(top3 - top0) < 0.1
      and cm.MOVES_KEY not in hood, (top0, top3))
check('Concept Move operator + tool registered', hasattr(bpy.types, 'MCH_OT_concept_move')
      and hasattr(bpy.types, 'MCH_OT_concept_add') and hasattr(bpy.types, 'MCH_OT_concept_fuse')
      and hasattr(C.scene, 'mch_concept') and C.scene.mch_concept.falloff == 'CLAY')
summary()
