"""0.24.68 a round hole with GN Edge Chamfer was slow (~1 s) and came out lopsided: a band that does not cross
itself skips the Exact self-union (Manifold straight away), a width bigger than the hole is kept under its radius
(the two sides' bands ran into each other), a small closed rim gets one even width all round."""
import math
import time

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
import numpy as np
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, rim_sweep as rs

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
cut.depth_mode = 'THROUGH'


def base(sc=1.0):
    me = bpy.data.meshes.new('MCH_Base')
    bm = bmesh.new()
    outline = [(-2, -1.2), (-0.6, -1.2), (-0.6, -0.2), (0.6, -0.2), (0.6, -1.2), (2, -1.2), (2, 1.4), (-0.6, 1.4),
               (-0.6, 0.9), (-2, 0.9)]
    f = bm.faces.new([bm.verts.new((x * sc, y * sc, 0)) for x, y in outline])
    r = bmesh.ops.extrude_face_region(bm, geom=[f])
    for v in r['geom']:
        if isinstance(v, bmesh.types.BMVert):
            v.co.z = 0.35 * sc
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new('MCH_Base', me)
    C.collection.objects.link(ob)
    C.view_layer.objects.active = ob
    m = ob.modifiers.new('b', 'BEVEL')
    m.width, m.segments, m.limit_method = 0.08 * sc, 4, 'ANGLE'
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier=m.name)
    return ob


def hole(ob, cx, cy, rad, width):
    circle = [(500 + 100 * (cx + rad * math.cos(2 * math.pi * i / 64)),
               500 + 100 * (cy + rad * math.sin(2 * math.pi * i / 64))) for i in range(64)]
    cut.gn_finish, cut.gn_width, cut.gn_segments = 'CHAMFER', width, 4
    t = time.perf_counter()
    msg = ce.perform_closed(C, 'CUT', [ob], [circle], TOP, False)
    dt = time.perf_counter() - t
    co = np.array([v.co[:] for v in ob.data.vertices])
    top = co[np.abs(co[:, 2] - co[:, 2].max()) < 1e-4]
    d = np.hypot(top[:, 0] - cx, top[:, 1] - cy)
    ring = d[d < rad + 1.2 * width]          # (not the part's own bevel nearby)
    return dt, msg, ring


used = []
real = rs._sweep
rs._sweep = lambda me, n, fast: used.append(fast) or real(me, n, fast)
ob = base()
dt, msg, ring = hole(ob, 1.3, 0.9, 0.12, 0.036)
print(f'  hole r 0.12, chamfer 0.036: {dt:.3f} s')
check('A round hole: its band does not cross itself - straight into the Manifold difference (no Exact self-union)',
      used == ['band', 'direct'] and 'GN Chamfer' in msg, (used, msg))
check('... the chamfer is even all round (0.036 out from the hole) and the part stays closed',
      len(ring) and abs(ring.min() - 0.156) < 2e-3 and abs(ring.max() - 0.156) < 2e-3 and non_manifold(ob) == 0,
      (ring.min(), ring.max()))
check('... quick (the old Exact self-union took ~0.3-1 s here)', dt < 0.25, dt)
bpy.data.objects.remove(ob)
used.clear()
ob = base(0.3)
dt, msg, ring = hole(ob, 0.5, 0.32, 0.03, 0.036)
check('A chamfer wider than a small hole\'s radius stays under it (no funnel past the axis), even all round, quick',
      len(ring) and ring.max() - 0.03 < 0.8 * 0.03 + 2e-3 and ring.max() - ring.min() < 0.004 and dt < 0.25
      and non_manifold(ob) == 0, (ring.min(), ring.max(), dt))
bpy.data.objects.remove(ob)
ob = base(0.3)
dt, msg, ring = hole(ob, 0.5, 0.32, 0.06, 0.036)
check('A hole next to the part\'s bevelled corner: one even width all round (was 0.008 on the corner side, 0.030 '
      'on the other)', len(ring) and ring.max() - ring.min() < 0.002 and non_manifold(ob) == 0,
      (ring.min(), ring.max()))
rs._sweep = real
summary()
