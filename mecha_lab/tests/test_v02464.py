"""0.24.42 Cut Edge Finish (Bevel / Chamfer) never sticks out of the part: where a notch meets the part's own
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
cut.gn_finish = cut.edge_finish = 'NONE'
summary()
