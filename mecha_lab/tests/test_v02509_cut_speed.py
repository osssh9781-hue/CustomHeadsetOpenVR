"""0.24.85 Cut / Split on a high-poly part: the result tidy looks only at the faces round what the cut changed (the
whole-body Python scans were 2.4 s of a 2.8 s cut on 82k faces), the twin-face pre-check hashes n-gons without the
{a, a+7, a+8} = {a+2, a+3, a+10} collision, and the Decimate tidy skips clean stages."""
import time

import numpy as np

from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import core_geometry as cg, tool_state as ts

_src = open(__file__.replace('test_v02509_cut_speed.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (the stroke driver)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_cut.targets = 'AUTO'


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def body(sub, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1.0, location=loc)
    ob = C.active_object
    m = ob.modifiers.new('d', 'DISPLACE')
    t = bpy.data.textures.new('t', 'CLOUDS')
    t.noise_scale = 0.3
    m.texture = t
    m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    return ob


# --- the twin-face hash -----------------------------------------------------------------------------------------
me = bpy.data.meshes.new('h')
a = 100
me.from_pydata([(i * 0.01, (i * 7) % 5 * 0.1, (i * 3) % 4 * 0.1) for i in range(a + 12)], [],
               [[a, a + 7, a + 8], [a + 2, a + 3, a + 10], [0, 1, 2, 3, 4], [5, 6, 7, 8, 9]])
me.update()
check('twin pre-check: the two triangles with equal sums and sums of squares are NOT twins (an n-gon mesh: the hash path)',
      not cg._twin_faces(me) and max(p.loop_total for p in me.polygons) == 5)
me2 = bpy.data.meshes.new('h2')
me2.from_pydata([(i * 0.01, (i * 7) % 5 * 0.1, (i * 3) % 4 * 0.1) for i in range(12)], [],
                [[0, 1, 2, 3, 4], [4, 3, 2, 1, 0], [5, 6, 7, 8, 9]])
me2.update()
check('... a real twin n-gon (same points, reversed) is', cg._twin_faces(me2))
check('... and only looked for among the masked faces when a mask is given',
      not cg._twin_faces(me2, np.array([True, False, True])) and cg._twin_faces(me2, np.array([True, True, False])))

# --- the changed region of a cut --------------------------------------------------------------------------------
ob = body(5)
before = ob.data.copy()
n0 = len(ob.data.polygons)
select(ob)
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]
S.mch_settings.mch_active_tool = 'CUT'
S.mch_cut.shared_mesh = 'SINGLE'
real_tidy = cg.tidy_result
seen = {}


def spy(me, ref_size=None, **kw):
    seen['before'] = kw.get('before')
    fm, vm = cg._changed_faces(me, kw.get('before'), ref_size or cg.mesh_size(me))
    seen['faces'] = (int(fm.sum()), len(me.polygons)) if fm is not None else None
    return real_tidy(me, ref_size, **kw)


cg.tidy_result = spy
r, msg = lasso([(470, 470), (530, 470), (530, 530), (470, 530)])
cg.tidy_result = real_tidy
check('Cut on a 20k-face body passes the part\'s mesh as "before": the tidy looks at the faces round the cut only '
      '(under 15 % of the result)', r == {'FINISHED'} and seen.get('before') is not None and seen.get('faces')
      and 0 < seen['faces'][0] < 0.15 * seen['faces'][1] and non_manifold(ob) == 0, (r, seen.get('faces')))
fm, vm = cg._changed_faces(ob.data, before, cg.mesh_size(before))
check('_changed_faces: every face with a new point is in, plus one ring; a face far from the cut is not',
      fm is not None and fm.any() and not fm.all() and vm.any())
check('_changed_faces without a "before" mesh: everything (None)', cg._changed_faces(ob.data, None, 1.0) == (None, None))

# --- a fin near the cut is still removed, with the local look ----------------------------------------------------
res = ob.data
verts = [v.co[:] for v in res.vertices]
faces = [list(p.vertices) for p in res.polygons]
new_idx = np.nonzero(vm)[0]
e = next(e for e in res.edges if vm[e.vertices[0]] and vm[e.vertices[1]])
verts.append((0.0, 0.0, 3.0))
faces.append([e.vertices[0], e.vertices[1], len(verts) - 1])
faces.append([len(verts) - 1, e.vertices[1], e.vertices[0]])
fin = bpy.data.meshes.new('fin')
fin.from_pydata(verts, [], faces)
fin.update()
out = cg.tidy_result(fin, cg.mesh_size(before), before=before)
check('a fin (two faces back to back on a cut edge) is removed by the local tidy', out['folds'] == 2
      and len(fin.vertices) == len(verts) - 1 and cg.non_manifold_edge_count(fin) == 0, out)

# --- speed -------------------------------------------------------------------------------------------------------
ob2 = body(7, loc=(0, 0, 0))
bpy.data.objects.remove(ob)
select(ob2)
t = time.perf_counter()
r, msg = lasso([(470, 470), (530, 470), (530, 530), (470, 530)])
dt = time.perf_counter() - t
check('Cut on an 82k-face body: done, closed, under 1.6 s (0.24.84: 2.8 s, 2.4 s of it the whole-body tidy scans)',
      r == {'FINISHED'} and non_manifold(ob2) == 0 and dt < 1.6, (r, round(dt, 2)))
MODE[0], NATIVE[0] = 'SPLIT', ts.TOOL_BY_ID['SPLIT'][5]
S.mch_settings.mch_active_tool = 'SPLIT'
t = time.perf_counter()
r, msg = lasso([(400, 400), (460, 400), (460, 460), (400, 460)])
dt = time.perf_counter() - t
check('Split on the same body: done, under 2.2 s (was 3.0 s)', r == {'FINISHED'} and dt < 2.2, (r, round(dt, 2)))
summary()
