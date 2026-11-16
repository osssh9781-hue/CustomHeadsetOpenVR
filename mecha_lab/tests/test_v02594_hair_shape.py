"""0.24.179 Hair in a sculpted shape (user: "털 부분에 내가 만든 털 모양 스컬핑에 맞춰서 머리카락 만드는 거도 가능한가?" -
"따로 만든 메쉬"): a head and a lock sculpted as its own mesh, bent like a J (up off the head, over and down): the hair
fills the lock - rooted where it meets the head (found by itself), following the bend to its end, inside it; live
values (Frizz: no tracing again; Fill: traced again); the lock hidden; a second piece with no head under it: rooted
at its top."""
import math
import time

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
head.name = 'Head'

path = [Vector(p) for p in ((0.0, 0.0, 0.92), (0.25, 0.0, 1.15), (0.6, 0.0, 1.2), (0.95, 0.0, 1.0),
                            (1.15, 0.0, 0.6), (1.2, 0.0, 0.15), (1.18, 0.0, -0.25))]


def dense(P, n=60):
    seg = [(a, b) for a, b in zip(P[:-1], P[1:])]
    L = [(b - a).length for a, b in seg]
    tot = sum(L)
    out = []
    for i in range(n):
        s = tot * i / (n - 1)
        for (a, b), l_ in zip(seg, L):
            if s <= l_ + 1e-9:
                out.append(a.lerp(b, s / l_))
                break
            s -= l_
    return out


C_ = dense(path)


def lock_mesh(name, centre, r0, r1):
    bm = bmesh.new()
    rings = []
    for i, c in enumerate(centre):
        t = i / (len(centre) - 1)
        tan = (centre[min(i + 1, len(centre) - 1)] - centre[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        r = r0 + (r1 - r0) * t
        rings.append([bm.verts.new(c + (u * math.cos(a) + v * math.sin(a)) * r)
                      for a in np.linspace(0, 2 * math.pi, 16, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(16):
            bm.faces.new((a[k], a[(k + 1) % 16], b[(k + 1) % 16], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    C.scene.collection.objects.link(ob)
    return ob


lock = lock_mesh('Lock', C_, 0.13, 0.03)
for o in C.selected_objects:
    o.select_set(False)
lock.select_set(True)
C.view_layer.objects.active = lock
S.mch_hshape.count = 1200
t0 = time.perf_counter()
r = bpy.ops.mch.hair_from_shape()
t_make = time.perf_counter() - t0
hair = next((o for o in S.objects if hs.is_hair(o)), None)
check(f'Hair in the Selected Shape ({r}, {t_make:.1f} s): a hair object ({hair and hair.name}, '
      f'{hair and len(hair.data.curves):,} strands) on the head (found by itself: {hair and hair.mch_hshape.body and hair.mch_hshape.body.name}), '
      f'its child; the lock hidden', r == {'FINISHED'} and hair is not None and len(hair.data.curves) == 1200
      and hair.mch_hshape.body == head and hair.parent == head and lock.hide_get())


def strands(ob):
    P = np.empty(len(ob.data.points) * 3, np.float32)
    ob.data.attributes['position'].data.foreach_get('vector', P)
    seg = ob.mch_hshape.segments
    M = np.array(ob.matrix_world)
    W = P.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]
    return W.reshape(-1, seg, 3)


W = strands(hair)
roots, tips = W[:, 0], W[:, -1]
d_root = np.abs(np.linalg.norm(roots, axis=1) - 1.0)
cl = np.array([tuple(p) for p in C_])
d_axis = np.array([np.min(np.linalg.norm(cl - p, axis=1)) for p in W.reshape(-1, 3)[::7]])
r_at = 0.13
end = np.array(tuple(C_[-1]))
d_tip = np.linalg.norm(tips - end, axis=1)
check(f'rooted where the lock meets the head (roots off the head\'s skin: median {np.median(d_root):.3f}), along '
      f'the bend inside the lock (points off its middle line: 95 % within {np.percentile(d_axis, 95):.3f}, the lock '
      f'0.13 thick at its root), to its end (tips within {np.median(d_tip):.2f} of it, median)',
      np.median(d_root) < 0.06 and np.percentile(d_axis, 95) < r_at * 1.25 and np.median(d_tip) < 0.35)
mid = W[:, W.shape[1] // 2]
check(f'the J followed round, not cut across (the strands\' middles out at x {np.median(mid[:, 0]):.2f}, z '
      f'{np.median(mid[:, 2]):.2f} - over the top of the head, as the lock is)', np.median(mid[:, 0]) > 0.5
      and np.median(mid[:, 2]) > 0.7)
t0 = time.perf_counter()
hair.mch_hshape.frizz = 0.6
hs.rebuild(hair)
t_frizz = time.perf_counter() - t0
W2 = strands(hair)
t0 = time.perf_counter()
hair.mch_hshape.fill = 0.2
hs.rebuild(hair)
t_fill = time.perf_counter() - t0
check(f'live: Frizz (no tracing again: {t_frizz * 1000:.0f} ms) changes the strands ({np.abs(W2 - W).max():.3f}), '
      f'Fill traced again ({t_fill:.2f} s)', np.abs(W2 - W).max() > 0.005 and t_frizz < 0.5 and t_fill > t_frizz)
hair.mch_hshape.hide_shape = False
shown = not lock.hide_get()
hair.mch_hshape.hide_shape = True
check(f'Hide the Shape off: the lock shown ({shown}); on: hidden', shown and lock.hide_get())
# the start clicked (0.24.179 "결 시작 부분은 내가 찍어 주는 게 낫지 않나?"): at the lock's far end - the hair runs from there
S.mch_hshape.count = 400
ob_c, msg_c = hs.make(C, lock, None, starts=[tuple(C_[-1])])
Wc = strands(ob_c)
d_r = np.median(np.linalg.norm(Wc[:, 0] - np.array(tuple(C_[-1])), axis=1))
d_t = np.median(np.abs(np.linalg.norm(Wc[:, -1], axis=1) - 1.0))
check(f'a start clicked at the lock\'s far end: rooted there (roots {d_r:.2f} from it), running back to the head (tips '
      f'{d_t:.2f} off its skin) - {msg_c}', d_r < 0.25 and d_t < 0.2 and 'clicked' in msg_c)
ob_c.mch_hshape.frizz = 0.4
hs.rebuild(ob_c)
Wc2 = strands(ob_c)
check('... kept with it: rebuilt (Frizz), still from there',
      np.median(np.linalg.norm(Wc2[:, 0] - np.array(tuple(C_[-1])), axis=1)) < 0.25)
bpy.data.objects.remove(ob_c)
# a second piece with nothing under it: rooted at its top
lock2 = lock_mesh('Bun', [Vector((4.0, 0.0, 1.0 - 0.02 * i)) for i in range(40)], 0.12, 0.04)
for o in C.selected_objects:
    o.select_set(False)
lock2.select_set(True)
C.view_layer.objects.active = lock2
S.mch_hshape.count = 300
bpy.ops.mch.hair_from_shape()
h2 = C.active_object
W3 = strands(h2)
check(f'a shape with no body under it: rooted at its top (roots z {np.median(W3[:, 0, 2]):.2f}, tips '
      f'{np.median(W3[:, -1, 2]):.2f})', hs.is_hair(h2) and h2.mch_hshape.body is None
      and np.median(W3[:, 0, 2]) > np.median(W3[:, -1, 2]) + 0.4)
r = bpy.ops.mch.hair_shape_apply()
check(f'Apply: kept, not live ({r})', r == {'FINISHED'} and not hs.is_hair(h2) and len(h2.data.curves) == 300)
summary()
