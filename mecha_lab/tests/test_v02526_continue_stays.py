"""0.24.113 (user: "처음 그은 메쉬의 위치가 두 번째 거 그으면 바뀌어") Going on with a line must not move the piece that was
already there: every vertex of the first stroke's piece (away from the joint) stays exactly where it was, in the same
view and in a turned view, with Sharp and Round corners, and with Attach Ends on (the old bend is kept; the new piece
rides at the old end's depth instead of re-bending the whole line)."""
import json
import math
import time

from _harness import bmesh, bpy, check, cube, fresh, non_manifold, summary
from mathutils import Euler, Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh, core_geometry as cg, press_cut as pc

fresh()
mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0.0, 0.0)).to_quaternion(), pixels_per_unit=100.0)
SPAN = 0.8


class Region:
    width, height = 1000, 1000

    def tag_redraw(self):
        pass


class Shim:
    def report(self, kind, msg):
        self.reports.append((kind, msg))


for n in ('_finish_draw', '_cleanup'):
    setattr(Shim, n, getattr(pc.MCH_OT_press_unified, n))


def stroke(proj, world_pts, make_mesh=True):
    op = Shim()
    op.reports = []
    op.state, op.down_time = 'DRAW', time.perf_counter()
    op.pts = [tuple(proj.to_screen(Vector(q))) for q in world_pts]
    op.anchor = op.pts[0]
    op.press, op.region, op.projector, op.make_mesh = None, Region(), proj, make_mesh
    op.timer = op.handle = op.handle_red = None
    op.cont_end = None
    return op._finish_draw(C, op.pts[-1]), op


def setup(corner='SHARP'):
    global C
    fresh()
    C = bpy.context
    st = C.scene.mch_press
    st.size, st.shape, st.rotation, st.result, st.drawn = 40.0, 'MCH_BUILTIN_M_OCTAGON', 0.0, 'CUT', False
    C.scene.mch_settings.auto_apply = True
    C.scene.mch_base.line_corner, C.scene.mch_base.corner_radius = corner, 1.0
    C.scene.mch_base.line_attach = False
    pc.CONTINUE['base'] = pc.CONTINUE['cut'] = None
    return st, cube('P', size=2.0)


def first_leg(ob, x_max):
    """World vertices of the piece drawn first (x < x_max), sorted, rounded."""
    return sorted(tuple(round(c, 6) for c in (ob.matrix_world @ v.co)) for v in ob.data.vertices if (ob.matrix_world @ v.co).x < x_max)


def moved(a, b, ob=None):
    """How far the first piece moved: the biggest distance from an old vertex to the new SURFACE (Round re-spaces the
    rings along a leg the arc shortened, which moves vertices but not the tube), else to the nearest new vertex."""
    if not a or not b:
        return 9.9
    if ob is not None:
        from mathutils.bvhtree import BVHTree
        bvh = BVHTree.FromObject(ob, C.evaluated_depsgraph_get())      # (object space)
        inv = ob.matrix_world.inverted()
        return max(bvh.find_nearest(inv @ Vector(p))[3] for p in a)
    return max(min(math.dist(p, q) for q in b) for p in a)


for corner in ('SHARP', 'ROUND'):
    st, p = setup(corner)
    r, op = stroke(TOP, [(-1.0 + 1.4 * k / 7, -0.6, 1.0) for k in range(8)])
    ob = C.active_object
    mw0 = ob.matrix_world.copy()
    before = first_leg(ob, 0.4 - 1.2 * SPAN)
    r2, op = stroke(TOP, [(0.4, -0.6 + 1.4 * k / 7, 1.0) for k in range(8)])          # on from the end, same view
    after = first_leg(ob, 0.4 - 1.2 * SPAN)
    same = moved(before, after) if corner == 'SHARP' else moved(before, after, ob)
    check(f'{corner}: a second stroke from the end (same view) leaves the first piece exactly where it was (object frame too)',
          r2 == {'FINISHED'} and before and same < 1e-5 and (corner == 'ROUND' or len(after) == len(before))
          and (ob.matrix_world - mw0).to_scale().length < 1e-9 and (ob.matrix_world.translation - mw0.translation).length < 1e-9,
          (len(before), len(after), round(same, 6)))
    r3, op = stroke(FRONT, [(ob.matrix_world @ Vector(base_mesh._xyz(json.loads(ob[base_mesh.SWEEP_KEY]).get('path3', json.loads(ob[base_mesh.SWEEP_KEY])['path'])[-1]))) + Vector((0.0, 0.0, -0.15 * k)) for k in range(8)])
    after3 = first_leg(ob, 0.4 - 1.2 * SPAN)
    same3 = moved(before, after3) if corner == 'SHARP' else moved(before, after3, ob)
    check(f'{corner}: a third stroke in a turned view (down) leaves the first piece exactly where it was too',
          r3 == {'FINISHED'} and same3 < 1e-5 and (corner == 'ROUND' or len(after3) == len(before)) and non_manifold(ob) == 0,
          (len(after3), round(same3, 6), op.reports[-1:] if op.reports else None))

# Attach Ends: the first piece's bend is kept; the new piece rides at the old end's depth
st, p = setup('SHARP')
r, op = stroke(TOP, [(-1.0 + 1.4 * k / 7, -0.6, 1.0) for k in range(8)])
ob = C.active_object
att = {'path': [list(q) for q in json.loads(ob[base_mesh.SWEEP_KEY])['path']], 'z0': 0.0, 'z1': 0.3, 'eye': None}
ob[base_mesh.ATTACH_KEY] = json.dumps(att)
base_mesh.rebuild(ob)
before = first_leg(ob, 0.4 - 1.2 * SPAN)
end_z = max((ob.matrix_world @ v.co).z for v in ob.data.vertices if (ob.matrix_world @ v.co).x > 0.3)
r2, op = stroke(TOP, [(0.4, -0.6 + 1.4 * k / 7, 1.0) for k in range(8)])
after = first_leg(ob, 0.4 - 1.2 * SPAN)
new_piece = [(ob.matrix_world @ v.co) for v in ob.data.vertices if (ob.matrix_world @ v.co).y > -0.6 + 0.6]
check('Attach Ends on: going on keeps the first piece\'s bend as it was (no re-bend of the whole line)',
      r2 == {'FINISHED'} and moved(before, after) < 1e-5 and len(after) == len(before), (len(before), len(after), round(moved(before, after), 6)))
check('... the new piece rides at the old end\'s depth (its top as high as the old end was, + the end\'s 0.3)',
      new_piece and abs(max(v.z for v in new_piece) - end_z) < 0.02 and non_manifold(ob) == 0,
      (round(max(v.z for v in new_piece), 3) if new_piece else None, round(end_z, 3)))
summary()
