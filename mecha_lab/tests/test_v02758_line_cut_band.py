"""0.24.363 line cut speed (user: "근데 왜 라인으로 자르는 건 엄청 느려?"): a bent line's cutter is half of the part,
so the "faces round the cutter" boolean took most of the part.  Now only the band of faces the cutter's surface runs
through goes through the boolean; the rest is told inside / outside by the C engine (mcut_inside).  A straight line's
Split tidied its other half against the kept half (every face "new"): now against the part before the cut.
Same shapes as before."""
import numpy as np
import bmesh
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import cut_engine as ce, core_geometry as cg, region_cut as rc

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ce.open_popup = lambda name: None
TOP = cg.OrthoProjector(Quaternion())

# the inside test against bmesh's own (a closed, bumpy sphere)
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=3, radius=1.0)
ball = C.active_object
tris = np.array([[v.co[:] for v in (ball.data.vertices[i] for i in p.vertices)] for p in ball.data.polygons])
rng = np.random.default_rng(3)
pts = rng.uniform(-1.2, 1.2, (20000, 3))
got = rc.points_inside(pts, tris.reshape(-1, 9))
r = np.linalg.norm(pts, axis=1)
sure = (r < 0.97) | (r > 1.01)                     # (away from the faceted surface: plainly inside / outside)
check('the C inside test is in the library and agrees with the sphere', got is not None
      and bool(np.all(got[sure] == (r[sure] < 0.97))), None if got is None else int((got[sure] != (r[sure] < 0.97)).sum()))
bpy.data.objects.remove(ball)


def body():
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=8, radius=1.0)
    ob = C.active_object
    m = ob.modifiers.new('d', 'DISPLACE')
    t = bpy.data.textures.new('t', 'CLOUDS'); t.noise_scale = 0.3
    m.texture = t; m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True); C.view_layer.objects.active = ob
    return ob


def shape():
    out = []
    for o in sorted([o for o in S.objects if o.type == 'MESH'], key=lambda o: o.name):
        bm = bmesh.new(); bm.from_mesh(o.data)
        out.append((bm.calc_volume(signed=False), sum(1 for e in bm.edges if not e.is_manifold), len(bm.faces)))
        bm.free()
    return out


def run(mode, pts, band=True):
    keep = rc.points_inside
    if not band:
        rc.points_inside = lambda co, tris: None
    try:
        ob = body()
        msg = ce.perform_line(C, mode, [ob], pts, TOP, side_xy=(700, 500))
        return msg, shape()
    finally:
        rc.points_inside = keep
        for o in [o for o in S.objects if o.type == 'MESH']:
            bpy.data.objects.remove(o)


BENT = [(520, 250), (470, 500), (520, 750)]
for mode in ('CUT', 'SPLIT'):
    m_new, s_new = run(mode, BENT)
    m_old, s_old = run(mode, BENT, band=False)
    same = len(s_new) == len(s_old) and all(abs(a[0] - b[0]) < 1e-4 * max(1e-9, b[0]) for a, b in zip(s_new, s_old))
    check(f'bent line {mode}: the band through the boolean ({m_new[:40]!r}), the same volume as the whole-part one '
          f'({[round(x[0], 5) for x in s_new]} / {[round(x[0], 5) for x in s_old]})', '(Region)' in m_new and same)
    check(f'bent line {mode}: closed (open edges {[x[1] for x in s_new]}), about the same faces '
          f'({[x[2] for x in s_new]} / {[x[2] for x in s_old]})',
          all(x[1] == 0 for x in s_new) and all(abs(a[2] - b[2]) <= 0.001 * b[2] for a, b in zip(s_new, s_old)))

m, s = run('SPLIT', [(510, 250), (490, 750)])
v0 = run('CUT', [(510, 250), (490, 750)])[1][0][0]
check(f'straight line Split: two closed halves ({[(round(x[0], 4), x[1]) for x in s]}), the kept one as Cut keeps it',
      len(s) == 2 and all(x[1] == 0 for x in s) and any(abs(x[0] - v0) < 1e-6 * v0 for x in s))
summary()
