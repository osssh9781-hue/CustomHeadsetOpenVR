"""0.24.42 A second cut leaves the first one's border alone (GN Edge left a copy of the cutter flag / UVMap on the
points: the next cut finished the old border again - spikes in the first notch).  Cut Edge Finish (Bevel / Chamfer) never sticks out of the part: where a notch meets the part's own
bevelled edge, Blender's bevel slid points outside (dark spikes at the ends of the notch) - they go back onto
the old surface now.  GN Edge stays inside too."""
from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
NOTCH = [(440, 630), (460, 585), (540, 585), (560, 630)]          # over the plate's top edge


def plate():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=1.0, scale=(2.0, 2.0, 0.2))
    t = C.active_object
    bpy.ops.object.transform_apply(scale=True)
    m = t.modifiers.new('b', 'BEVEL')
    m.width, m.segments = 0.05, 2
    bpy.ops.object.modifier_apply(modifier='b')
    return t


def outside(t):
    return sum(1 for v in t.data.vertices if abs(v.co.x) > 1.0001 or abs(v.co.y) > 1.0001 or abs(v.co.z) > 0.1001)


for depth in ('SURFACE', 'THROUGH'):
    cut.depth_mode, cut.depth = depth, 0.05
    for fin in ('BEVEL', 'CHAMFER'):
        t = plate()
        cut.gn_finish = 'NONE'
        cut.edge_finish, cut.finish_width, cut.finish_segments = fin, 0.04, 4
        msg = ce.perform_closed(C, 'CUT', [t], [NOTCH], TOP, False)
        check(f'Edge Finish {fin} ({depth}): a notch over a bevelled edge, nothing sticks out, closed',
              fin in msg and outside(t) == 0 and non_manifold(t) == 0, (msg, outside(t), non_manifold(t)))
        t = plate()
        cut.edge_finish = 'NONE'
        cut.gn_finish, cut.gn_width = fin, 0.04
        msg = ce.perform_closed(C, 'CUT', [t], [NOTCH], TOP, False)
        check(f'GN Edge {fin} ({depth}): same, inside and closed', outside(t) == 0 and non_manifold(t) == 0,
              (msg, outside(t)))
SLOT = [(480, 620), (480, 540), (520, 540), (520, 620)]
LOW = [(560, 370), (560, 420), (640, 420), (640, 370)]
for fin in ('BEVEL', 'CHAMFER'):
    t = plate()
    cut.depth_mode, cut.edge_finish = 'THROUGH', 'NONE'
    cut.gn_finish, cut.gn_width, cut.gn_segments = fin, 0.03, 3
    ce.perform_closed(C, 'CUT', [t], [SLOT], TOP, False)
    names = [(a.name, a.domain) for a in t.data.attributes if not a.name.startswith('.')]
    near = lambda: sorted((round(v.co.x, 4), round(v.co.y, 4), round(v.co.z, 4)) for v in t.data.vertices
                          if abs(v.co.x) < 0.4 and v.co.y > 0.2)
    first = near()
    from mathutils.bvhtree import BVHTree
    import bmesh as _bm
    b0 = _bm.new()
    b0.from_mesh(t.data)
    shape0 = BVHTree.FromBMesh(b0)
    b0.free()
    msg = ce.perform_closed(C, 'CUT', [t], [LOW], TOP, False)
    off = max((shape0.find_nearest(v.co)[3] for v in t.data.vertices if abs(v.co.x) < 0.4 and v.co.y > 0.2),
              default=0.0)
    check(f'GN {fin}: after the cut no cutter flag and one UVMap (on corners) are left',
          cg.CUTTER_ATTR not in [n for n, _d in names] and [d for n, d in names if n == 'UVMap'] == ['CORNER'],
          names)
    check(f'GN {fin}: a second cut leaves the first notch as it was (every point still on its old surface, '
          f'only the new border finished)', off < 1e-5 and non_manifold(t) == 0 and 'border edges' in msg,
          (off, len(first), len(near()), msg))
cut.gn_finish = cut.edge_finish = 'NONE'
summary()
