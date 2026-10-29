"""0.24.91 tidy_result's one-by-one stages: (1) a fix touches the face it picked and nothing else, and the guard
counts the edges round it (not the whole part per try); (2) on a mesh past SUB_FACES the candidates and two rings
round them are fixed on a cut-out (every try copied and re-counted the whole part: 68 s of a 96 s chamfer cut on a
10k-face fuzz knob), the rim points stay put, the corner data (UVs) of untouched faces comes along; the spikes are
found once per call; (3) rim_sweep gives up on a tangled band with a message (no 7-minute Exact self-union) and
tells the Cut's warning why."""
import sys, os, time
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import bpy, check, summary
import bmesh
import numpy as np
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon'))
from mecha_lab import core_geometry as cg, rim_sweep as rs


def grid_mesh(cuts):
    bpy.ops.mesh.primitive_cube_add(size=1)
    ob = bpy.context.object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.mesh.quads_convert_to_tris()
    bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    me.uv_layers.new(name='UVMap')
    uv = me.uv_layers[0].data
    for i in range(len(me.loops)):
        uv[i].uv = (i % 7 / 7.0, i % 11 / 11.0)
    return me


def with_needles(me, count, seed=3):
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    rng = np.random.default_rng(seed)
    moved = []
    for vi in rng.choice(len(bm.verts), count, replace=False):
        v = bm.verts[vi]
        if not v.link_edges:
            continue
        o = v.link_edges[0].other_vert(v)
        v.co = o.co + (v.co - o.co) * 0.002
        moved.append(vi)
    return bm, moved


def needles(bm):
    return sum(1 for f in bm.faces if cg._is_needle(f))


def key(f):
    return tuple(sorted(tuple(round(c, 5) for c in v.co) for v in f.verts))


# (1) the right face: a small mesh (the plain way), two needles; every other face must come out as it was
me = grid_mesh(6)
bm, moved = with_needles(me, 2, seed=1)
before = {key(f) for f in bm.faces}
n0 = needles(bm)
bm, n = cg._one_by_one(bm, lambda b: [f for f in b.faces if cg._is_needle(f)], (cg._collapse_short, cg._dissolve_long))
after = {key(f) for f in bm.faces}
lost = before - after
near = {key(f) for f in bm.faces}  # (unused: the check is on what was lost)
check('(1) two needles on a small part: both fixed, no edge opened', n == n0 and n0 >= 2 and cg._bad_edges(bm) == 0, (n0, n, cg._bad_edges(bm)))
# the faces that vanished all sat round the moved points (a wrong-face collapse takes faces elsewhere)
bm0, _m = with_needles(me, 2, seed=1)
bm0.verts.ensure_lookup_table()
spots = [bm0.verts[i].co.copy() for i in _m]
far = [k for k in lost if all(min((np.array(p) - np.array(s)).dot(np.array(p) - np.array(s)) for s in spots) > 0.25 ** 2 for p in k)]
check('... and only faces round the needles changed', not far, (len(lost), len(far)))
bm.free()
bm0.free()

# (2) the cut-out way on a 20k-face part
me = grid_mesh(40)
bm, moved = with_needles(me, 80)
uv_lay = bm.loops.layers.uv[0]
before_uv = {key(f): {tuple(round(c, 5) for c in l.vert.co): l[uv_lay].uv.copy() for l in f.loops} for f in bm.faces}
n0 = needles(bm)
t = time.perf_counter()
bm, n = cg._one_by_one(bm, lambda b: [f for f in b.faces if cg._is_needle(f)], (cg._collapse_short, cg._dissolve_long), test=lambda b, f: cg._is_needle(f))
dt = time.perf_counter() - t
check('(2) 80 needles on a 20k-face part: all fixed on the cut-outs, no edge opened', needles(bm) == 0 and n >= 0.9 * n0 and cg._bad_edges(bm) == 0, (n0, n, needles(bm), cg._bad_edges(bm)))
check('... in under 1.5 s (the whole-part way: ~3.5 s here, 68 s on the fuzz knob)', dt < 1.5, round(dt, 2))
uv_lay = bm.loops.layers.uv[0]
same = changed = 0
for f in bm.faces:
    old = before_uv.get(key(f))
    if old is None:
        continue
    if all((old[tuple(round(c, 5) for c in l.vert.co)] - l[uv_lay].uv).length < 1e-6 for l in f.loops):
        same += 1
    else:
        changed += 1
check('... the UVs of every face left as it was came along', changed == 0 and same > 0.9 * len(bm.faces), (same, changed, len(bm.faces)))
check('... and no candidate-mark layer is left on the bmesh', bm.faces.layers.int.get('_mch_cand') is None)
bm.free()

# the plain way is still there for a small part / when the cut-out is not worth it
cg_sub = cg.SUB_FACES
cg.SUB_FACES = 10 ** 9
bm, moved = with_needles(me, 80)
bm, n = cg._one_by_one(bm, lambda b: [f for f in b.faces if cg._is_needle(f)], (cg._collapse_short, cg._dissolve_long))
check('... the plain way (SUB_FACES raised) fixes the same needles', needles(bm) == 0 and cg._bad_edges(bm) == 0, (n, needles(bm)))
cg.SUB_FACES = cg_sub
bm.free()

# a cut-out pass that cannot be put back safely says None and the plain way runs: a candidate list that is nothing
bm, moved = with_needles(me, 4)
got = cg._one_by_one_sub(bm, [], lambda b: [], (cg._collapse_short,), 8)
check('a cut-out with no candidates: (bmesh, 0)', got is not None and got[1] == 0)
bm.free()

# (3) rim_sweep: a tangled band is given up with a reason
band = bpy.data.meshes.new('band')
band.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, -0.5, -0.5), (0.5, 0.5, 0.5), (0.5, 1.5, -0.5)], [],
                 [(0, 1, 2, 3), (4, 5, 6)])
check('band_cross_count: a face through another is a crossing (and stop ends the count early)', rs.band_cross_count(band) == 1 and rs.band_cross_count(band, stop=1) == 1)
bpy.data.meshes.remove(band)
me = bpy.data.meshes.new('part')
me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0)], [], [(0, 1, 2, 3)])
me.attributes.new(rs.RIM, 'BOOLEAN', 'EDGE')
rs.LAST['narrowed'] = 0.1
got = rs._skip(me, 'too jagged')
check('_skip: 0 rim edges, the reason kept for the warning, the rim marks cleared', got == 0 and rs.LAST.get('skipped') == 'too jagged' and 'narrowed' not in rs.LAST and me.attributes.get(rs.RIM) is None)
src = open(os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon', 'mecha_lab', 'cut_engine.py')).read()
check("the Cut's 0-edge warning says the sweep's reason when there is one", "rim_sweep.LAST.get('skipped')" in src)
check('the dense-part cap and the tangle ratio are set', rs.DENSE == 5000 and rs.TANGLED == 4)
bpy.data.meshes.remove(me)
summary()
