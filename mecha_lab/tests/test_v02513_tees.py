"""0.24.86 The region cut's seam T-junction pass (region_cut._seam_tees): a point of one side lying on an open edge
of the other side splits that edge and is welded to it; a point off the line is left alone; short open edges are
split too (the voxel-quad case that was missed: a 2.9e-4 edge under a 3.6e-4 tolerance)."""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from _harness import bpy, check, summary
import bmesh
sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), 'addon'))
from mecha_lab import region_cut as rc


def two_faces(mid, scale=1.0):
    bm = bmesh.new()
    s = scale
    a, b, c, d = [bm.verts.new((x * s, y * s, z * s)) for x, y, z in ((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0))]
    m = bm.verts.new(tuple(v * s for v in mid))
    e, f = bm.verts.new((1 * s, -1 * s, 0)), bm.verts.new((0, -1 * s, 0))
    bm.faces.new([a, b, c, d])
    bm.faces.new([a, m, b, e, f])
    return bm


def open_edges(bm):
    return sum(1 for e in bm.edges if e.is_valid and len(e.link_faces) == 1)


bm = two_faces((0.5, 0, 0))
before = open_edges(bm)
n = rc._seam_tees(bm, 1e-3)
check('a point on the other side\'s open edge: the edge split there and welded (3 open edges fewer, one split)',
      before == 9 and open_edges(bm) == 6 and n == 1, (before, open_edges(bm), n))
check('... the two faces stay, the mesh has the same 7 points (the split point merged into the existing one)',
      len(bm.faces) == 2 and len(bm.verts) == 7, (len(bm.faces), len(bm.verts)))
bm.free()

bm = two_faces((0.81, 1e-4, 0))
rc._seam_tees(bm, 1e-3)
check('a point a little off the line (within the tolerance), not at the middle: welded too', open_edges(bm) == 6, open_edges(bm))
bm.free()

bm = two_faces((0.5, 0.01, 0))
n = rc._seam_tees(bm, 1e-3)
check('a point farther from the line than the tolerance: left alone', open_edges(bm) == 9 and n == 0, (open_edges(bm), n))
bm.free()

bm = two_faces((0.5, 0, 0), scale=2.9e-4)
n = rc._seam_tees(bm, 3.6e-4)
check('an open edge shorter than the tolerance is still split (the voxel-quad T-junction that stayed open)',
      open_edges(bm) == 6 and n == 1, (open_edges(bm), n))
bm.free()

bm = bmesh.new()
check('an empty mesh: nothing to do', rc._seam_tees(bm, 1e-3) == 0)
bm.free()
summary()
