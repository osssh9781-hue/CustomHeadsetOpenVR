"""0.24.183 (user: "헤어 시스템 뿌리 정하는 거 하나가 아니라 여러 개 할 수 있나?"): Hair in a sculpted shape from several
starts you click - the strands start round every one of them; the window shows how many (up top, the button to add /
take off - picking again shows them), X: back to where the shape meets the body.  The clicking itself (each click one
more, a click on a start takes it off, Backspace the last): tests/gui/round183_real_window.py."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector
from mathutils.bvhtree import BVHTree

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import hair_shape as hs  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
head = C.active_object


def tube(name, centre, rad_fn, ring=24):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        rings.append([bm.verts.new(c + (u * math.cos(a) + v * math.sin(a)) * rad_fn(t))
                      for a in np.linspace(0, 2 * math.pi, ring, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(ring):
            bm.faces.new((a[k], a[(k + 1) % ring], b[(k + 1) % ring], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob


# a long horizontal lock lying over the head - three starts along it
cen = [Vector((-1.0, 0.0, 1.05)).lerp(Vector((1.0, 0.0, 1.05)), i / 40) for i in range(41)]
lock = tube('Lock', cen, lambda t: 0.12)
LB = BVHTree.FromPolygons([tuple(v.co) for v in lock.data.vertices], [tuple(f.vertices) for f in lock.data.polygons])
starts = [tuple(LB.find_nearest(Vector((x, 0.0, 1.3)))[0]) for x in (-0.7, 0.0, 0.7)]
for o in C.selected_objects:
    o.select_set(False)
lock.select_set(True)
C.view_layer.objects.active = lock
S.mch_hshape.count = 3000
hair, msg = hs.make(C, lock, None, starts=starts)
check('three starts kept on the hair', len(hs.starts_of(hair)) == 3, msg)
d = hair.data
P = np.empty(len(d.points) * 3, np.float32)
d.attributes['position'].data.foreach_get('vector', P)
seg = hair.mch_hshape.segments
W = P.reshape(-1, seg, 3).astype(float)
R = W[:, 0]
near = [float((np.linalg.norm(R - np.array(s_), axis=1) < 0.2).mean()) for s_ in starts]
check(f'the strands start round every start you clicked ({", ".join(f"{x:.0%}" for x in near)} of the roots by '
      f'each)', min(near) > 0.15 and sum(near) > 0.8, near)
# each start's strands run away from it: the tips farther from the nearest start than the roots
dr = np.min([np.linalg.norm(R - np.array(s_), axis=1) for s_ in starts], axis=0)
dt = np.min([np.linalg.norm(W[:, -1] - np.array(s_), axis=1) for s_ in starts], axis=0)
check(f'... and run away from them (root {np.median(dr):.2f}, tip {np.median(dt):.2f} from the nearest start)',
      np.median(dt) > np.median(dr) + 0.15)
one, _m = hs.make(C, lock, None, starts=starts[:1])
R1 = np.empty(len(one.data.points) * 3, np.float32)
one.data.attributes['position'].data.foreach_get('vector', R1)
R1 = R1.reshape(-1, seg, 3)[:, 0].astype(float)
check('one start alone: the roots only round it (the others are not starts)',
      float((np.linalg.norm(R1 - np.array(starts[0]), axis=1) < 0.2).mean()) > 0.9)
bpy.data.objects.remove(one)


# the window: the starts up top
class Rec:
    def __init__(self):
        self.ops = []

    def __getattr__(self, name):
        def f_(*a, **k):
            if name == 'operator':
                self.ops.append((a[0], k.get('text', '')))
            return self
        return f_


rec = Rec()
C.view_layer.objects.active = hair
hs.draw(rec, C, hair)
texts = [t for _i, t in rec.ops]
check('the window: "Starts: 3 (click to add / take off)" up top, an X to go back to the body',
      texts and texts[0] == 'Starts: 3 (click to add / take off)' and ('mch.hair_shape_starts_clear', '') in rec.ops,
      texts[:4])
had = hs.MCH_OT_hair_shape_pick._had(hair)
check('picking again starts with the hair\'s three starts (to add to / take off)', len(had) == 3 and
      all(np.linalg.norm(np.array(q) - np.array(s_)) < 1e-4 for (_n, q), s_ in zip(had, starts)))
for o in C.selected_objects:
    o.select_set(False)
hair.select_set(True)
C.view_layer.objects.active = hair
r = bpy.ops.mch.hair_shape_starts_clear()
check('X: the starts off - from where the shape meets the body again', r == {'FINISHED'} and
      not hs.starts_of(hair) and len(hair.data.curves) == 3000)
rec = Rec()
hs.draw(rec, C, hair)
check('... the window says so', rec.ops[0][1] == 'Starts: from the body (click to set, several)', rec.ops[:2])

mecha_lab.unregister()
import sys  # noqa: E402
sys.exit(1 if summary() else 0)
