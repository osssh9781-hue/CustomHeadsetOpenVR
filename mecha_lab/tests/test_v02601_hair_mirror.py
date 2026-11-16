"""0.24.181 (user: "근데 머리카락 미러는 왜 아직 안 되지?"): hair made in a sculpted shape on a head with a live Mirror is
mirrored like the head (as plates and Creature Hair are - that follow took meshes only, this hair is curves): live
through a value / Amount; a lock across the middle is not doubled; the hair's Apply bakes the mirror into it; with
no Mirror on the head, none."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Vector

import bmesh  # noqa: E402
import mecha_lab
from mecha_lab import hair_shape as hs, mirror_tools as mt  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def lock(name, path, r0=0.15):
    bm = bmesh.new()
    rings = []
    n = len(path)
    for i, c in enumerate(path):
        tan = (path[min(i + 1, n - 1)] - path[max(i - 1, 0)]).normalized()
        u = tan.orthogonal().normalized()
        v = tan.cross(u)
        rings.append([bm.verts.new(c + (u * math.cos(a) + v * math.sin(a)) * (r0 - 0.1 * i / (n - 1)))
                      for a in np.linspace(0, 2 * math.pi, 14, endpoint=False)])
    for a, b in zip(rings[:-1], rings[1:]):
        for k in range(14):
            bm.faces.new((a[k], a[(k + 1) % 14], b[(k + 1) % 14], b[k]))
    bm.faces.new(list(reversed(rings[0])))
    bm.faces.new(rings[-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    return ob


def make(shape):
    for o in C.selected_objects:
        o.select_set(False)
    shape.select_set(True)
    C.view_layer.objects.active = shape
    return hs.make(C, shape)


def ev(hair):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    e = hair.evaluated_get(dg)
    M = np.array(hair.matrix_world)
    P = np.array([tuple(p.position) for p in e.data.points]) @ M[:3, :3].T + M[:3, 3]
    return len(e.data.curves), P


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
head = C.active_object
head.name = 'Head'
mt.setup_mirror(head, S.mch_mirror, S, (True, False, False), (False, False, False), Vector((0.0, 0.0, 0.0)))
check('the head: a live Mirror X', head.modifiers.get(mt.MOD_NAME) is not None)
side = lock('Side Lock', [Vector((0.55 + 0.3 * t, -0.2, 0.8 - 1.2 * t)) for t in np.linspace(0, 1, 30)])
S.mch_hshape.count = 1000
hair, msg = make(side)
n, P = ev(hair)
check(f'a lock on one side: its hair mirrored like the head ({n} strands from 1,000; x {P[:, 0].min():.2f} .. '
      f'{P[:, 0].max():.2f}) - {msg}', mt.curves_mod(hair) is not None and n == 2000
      and abs(P[:, 0].min() + P[:, 0].max()) < 0.02 and 'Mirror X like Head' in msg)
hair.mch_hshape.frizz = 0.4
hs.rebuild(hair)
hair.mch_hshape.count = 2500
hs.rebuild(hair)
n2, P2 = ev(hair)
check(f'... live: a value and Amount 2,500 - still mirrored ({n2} strands)', n2 == 5000
      and abs(P2[:, 0].min() + P2[:, 0].max()) < 0.03)
mid = lock('Middle Lock', [Vector((0.0, 0.3 + 0.5 * t, 0.85 - 0.9 * t)) for t in np.linspace(0, 1, 30)], 0.25)
hm, msg_m = make(mid)
nm, _Pm = ev(hm)
check(f'a lock across the middle (roots on both sides): not doubled ({nm} strands, no mirror: '
      f'{mt.curves_mod(hm) is None})', nm == 1000 and mt.curves_mod(hm) is None)
C.view_layer.objects.active = hair
r = bpy.ops.mch.hair_shape_apply()
check(f'the hair\'s Apply ({r}): the mirror baked into its strands ({len(hair.data.curves)}), no modifier left, not live',
      r == {'FINISHED'} and len(hair.data.curves) == 5000 and mt.curves_mod(hair) is None and not hs.is_hair(hair))
head.modifiers.remove(head.modifiers[mt.MOD_NAME])
other = lock('Other Lock', [Vector((-0.55 - 0.3 * t, 0.2, 0.8 - 1.2 * t)) for t in np.linspace(0, 1, 30)])
ho, msg_o = make(other)
no, _Po = ev(ho)
check(f'no Mirror on the head: none on the hair ({no})', no == 1000 and mt.curves_mod(ho) is None)
summary()
