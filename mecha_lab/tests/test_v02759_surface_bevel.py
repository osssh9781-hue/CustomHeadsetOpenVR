"""0.24.364 GN Edge Method: Surface (user: "베벨이랑 챔퍼도 더 좋고 빠르게" -> research: 3ds Max Smart Bevel): the cut's rim
chamfered / rounded without a second boolean - the band round the rim cut at an even distance on the surface and down
the wall, its points moved onto the profile.  Sweep (the default) unchanged; Surface also works on a High Poly
(region) cut, where the Sweep found no rim (as before)."""
import math
import bmesh
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import cut_engine as ce, core_geometry as cg, region_cut as rc

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
ce.open_popup = lambda name: None
cut = S.mch_cut
check('GN Edge has Method Sweep (default) / Surface', cut.gn_method == 'SWEEP'
      and [i.identifier for i in cut.bl_rna.properties['gn_method'].enum_items] == ['SWEEP', 'SURFACE'])
LOOP = [(500 + 45 * math.cos(a), 500 + 45 * math.sin(a)) for a in [2 * math.pi * k / 7 + 0.3 for k in range(7)]]
W = 0.06


def part(levels=6):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    m = ob.modifiers.new('s', 'SUBSURF'); m.subdivision_type = 'SIMPLE'; m.levels = levels
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='s')
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True); C.view_layer.objects.active = ob
    return ob


def run(finish, method, pocket=True):
    ob = part()
    cut.edge_finish = 'NONE'
    cut.depth_mode = 'SURFACE' if pocket else 'THROUGH'
    cut.depth = 0.15
    cut.gn_finish, cut.gn_width, cut.gn_segments, cut.gn_method = finish, W, 4, method
    msg = ce.perform_closed(C, 'CUT', [ob], [LOOP], cg.OrthoProjector(Quaternion()))
    bm = bmesh.new(); bm.from_mesh(ob.data)
    vol, op, nf = bm.calc_volume(signed=False), sum(1 for e in bm.edges if not e.is_manifold), len(bm.faces)
    bm.free()
    bpy.data.objects.remove(ob)
    return msg, vol, op, nf


perim = 2 * 7 * 0.45 * math.sin(math.pi / 7)
for pocket in (True, False):
    _m, v0, _o, _n = run('NONE', 'SWEEP', pocket)
    rims = 1 if pocket else 2
    for finish, share in (('CHAMFER', 0.5), ('BEVEL', 1 - math.pi / 4)):
        ms, vs, os_, _ = run(finish, 'SWEEP', pocket)
        mf, vf, of, _ = run(finish, 'SURFACE', pocket)
        want = share * W * W * perim * rims
        check(f'{"pocket" if pocket else "through"} {finish}: Surface takes off about the profile '
              f'({v0 - vf:.5f}; the corner {want:.5f}; Sweep {v0 - vs:.5f}), closed ({of} open edges)',
              abs((v0 - vf) - want) < 0.15 * want and of == 0 and os_ == 0 and 'GN' in mf)

# High Poly (region) cut: Surface finds the rim, Sweep as before (no rim found there)
keep = rc.MIN_FACES
rc.MIN_FACES = 10_000
try:
    _m, v0, _o, _n = run('NONE', 'SWEEP')
    rc.LAST_REGION.clear()
    mf, vf, of, _ = run('CHAMFER', 'SURFACE')
    region = bool(rc.LAST_REGION.get('faces'))
    ms, vs, _os, _ = run('CHAMFER', 'SWEEP')
finally:
    rc.MIN_FACES = keep
want = 0.5 * W * W * perim
check(f'High Poly (region) cut: Surface chamfers the rim ({v0 - vf:.5f}, the corner {want:.5f}), closed ({of})',
      region and abs((v0 - vf) - want) < 0.15 * want and of == 0)
check(f'High Poly cut, Sweep as before: no rim found ({ms[-60:]!r})', 'no new border edges' in ms and abs(vs - v0) < 1e-6)

# 0.24.365 (user's low-poly tube: long spikes) a low-poly part round the cut: the Sweep, said so - no folded faces
bpy.ops.mesh.primitive_cylinder_add(vertices=32, radius=1.7, depth=3.1)
ob = C.active_object
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True); C.view_layer.objects.active = ob
from mathutils import Euler
cut.depth_mode, cut.gn_finish, cut.gn_method, cut.gn_width = 'THROUGH', 'CHAMFER', 'SURFACE', 0.235
side = Euler((math.radians(90), 0, math.radians(20))).to_quaternion()
LOOP2 = [(560 + 60 * math.cos(a), 430 + 45 * math.sin(a)) for a in [2 * math.pi * k / 40 for k in range(40)]]
msg = ce.perform_closed(C, 'CUT', [ob], [LOOP2], cg.OrthoProjector(side))
bm = bmesh.new(); bm.from_mesh(ob.data); bm.normal_update()
fn = {f.index: f.normal.copy() for f in bm.faces}
t = bm.copy(); ol = t.faces.layers.int.new('o')
for f in t.faces:
    f[ol] = f.index
bmesh.ops.triangulate(t, faces=t.faces[:])
folds = len({f[ol] for f in t.faces if f.normal.length > 0 and f.normal.dot(fn[f[ol]]) < 0})
op = sum(1 for e in bm.edges if not e.is_manifold)
t.free(); bm.free()
check(f'low-poly tube, Surface: the Sweep used and said ({msg[-70:]!r}), no folded faces ({folds}), closed ({op})',
      'Sweep used' in msg and 'GN Chamfer' in msg and folds == 0 and op == 0)
bpy.data.objects.remove(ob)
summary()
