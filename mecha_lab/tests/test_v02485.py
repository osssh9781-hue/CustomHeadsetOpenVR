"""0.24.58 Faster Cut / Split on a mesh of many joined parts (tubes stuck into a body): the Boolean runs only on the
loose parts the shape can reach, the others are added back untouched (Cut) or left out (Split's piece).  A shape
that misses the mesh (e.g. drawn over the live Mirror copy) is known at once, before any Boolean, so the mirrored
retry does not wait for a full Boolean first."""
import math
import time

from _harness import bpy, check, fresh, non_manifold, summary, volume
import bmesh
from mathutils import Matrix, Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, symmetry as sy

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def square(x, y, h=20):
    cx, cy = TOP.to_screen(Vector((x, y, 0)))
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def build(mirror=False, tubes=8):
    fresh()
    me = bpy.data.meshes.new('P')
    bm = bmesh.new()
    r = bmesh.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co = Vector((v.co.x * 3, v.co.y * 1.2, v.co.z * 0.6))
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=8, use_grid_fill=True)
    for k in range(tubes):
        m = (Matrix.Translation((-1.2 + k * 0.3, 0.0, 0.0)) @ Matrix.Rotation(math.radians(70), 4, 'X')
             @ Matrix.Translation((0, 0, 1.2)))
        bmesh.ops.create_cone(bm, cap_ends=True, segments=32, radius1=0.08, radius2=0.08, depth=2.4, matrix=m)
    bm.to_mesh(me)
    bm.free()
    me.materials.append(bpy.data.materials.new('A'))
    me.materials.append(bpy.data.materials.new('B'))
    for poly in me.polygons:                          # the body material A, the tubes B
        poly.material_index = 0 if abs(poly.center.y) < 1.21 and abs(poly.center.z) < 0.61 else 1
    p = bpy.data.objects.new('P', me)
    C.scene.collection.objects.link(p)
    p.location = (2.5, 0, 0)
    C.view_layer.objects.active = p
    p.select_set(True)
    C.view_layer.update()
    if mirror:
        sy.set_mode(C, p, 'MIRROR')
    return p


def far_tubes(ob):
    """Points of the tubes far from the cut (x > 1.9 in the scene): they must stay exactly as they were."""
    return sorted(tuple(round(c, 6) for c in (ob.matrix_world @ v.co)) for v in ob.data.vertices
                  if (ob.matrix_world @ v.co).x > 1.9 and (ob.matrix_world @ v.co).y < -1.3)


real_local = cg._boolean_local
out = {}
for local in (False, True):
    cg._boolean_local = real_local if local else (lambda *a, **k: None)
    p = build()
    keep = far_tubes(p)
    t = time.perf_counter()
    msg = ce.perform_closed(C, 'CUT', [p], [square(1.3, -1.9)], TOP)
    out[local] = (time.perf_counter() - t, len(p.data.polygons), round(volume(p), 6), non_manifold(p), far_tubes(p) == keep,
                  sorted({poly.material_index for poly in p.data.polygons}), dict(cg.LAST_BOOLEAN), msg)
cg._boolean_local = real_local
a, b = out[False], out[True]
check('Cut on one tube of a body + 8 tubes: the same result as the Boolean on everything (faces, volume, closed)',
      a[1:4] == b[1:4] and b[3] == 0, (a[:4], b[:4]))
check('... only the parts the shape reaches went into the Boolean; the far tubes are untouched, materials kept',
      b[6].get('parts', (0, 0))[0] <= 2 and b[6]['parts'][1] == 9 and b[4] and b[5] == [0, 1], (b[6], b[4], b[5]))
p = build()
msg = ce.perform_closed(C, 'SPLIT', [p], [square(1.3, -1.9)], TOP)
piece = bpy.data.objects.get('P_Split')
check("Split: the piece is only what the shape cut out (the other parts are not in it)", piece is not None
      and len(piece.data.vertices) < 400 and non_manifold(piece) == 0 and non_manifold(p) == 0,
      piece and len(piece.data.vertices))
p = build()
t = time.perf_counter()
try:
    ce.perform_closed(C, 'CUT', [p], [square(9.0, 9.0)], TOP)
    msg = ''
except cg.CutError as ex:
    msg = str(ex)
check('A shape beside the mesh: "does not intersect" at once, with the facts', 'does not intersect' in msg
      and '[shape covers' in msg and time.perf_counter() - t < 1.0, msg[:90])
p = build(mirror=True)
before = len(p.data.polygons)
msg = ce.perform_closed(C, 'CUT', [p], [square(-1.3, -1.9)], TOP)
check('Over the live Mirror copy: cut on the real half (mirrored back), still only the parts reached',
      'Cut: P' in msg and len(p.data.polygons) != before and non_manifold(p) == 0
      and cg.LAST_BOOLEAN.get('parts', (9, 9))[0] <= 2, (msg[:60], cg.LAST_BOOLEAN))
lab = cg.loose_labels(build().data)
check('Loose parts found (body + 8 tubes)', len(set(lab.tolist())) == 9)
check('A slow cut says how long it took and which solver', "took > 1.5" in __import__('inspect').getsource(
    ce._perform_closed))
summary()
