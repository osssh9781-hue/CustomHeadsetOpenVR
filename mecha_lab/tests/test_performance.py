"""Cut timing on dense meshes (headless, single run, informational).

GUI drawing latency is not measured here: the stroke overlay never evaluates
the Boolean while drawing; only the confirm step below is timed.
"""
import sys
import time

from _harness import bpy, bmesh, check, fresh, mesh_obj, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

TOP = cg.OrthoProjector(Quaternion())
mecha_lab.register()
rows = []
for subdiv in (3, 5, 6, 7):
    fresh()
    t = mesh_obj('Dense', lambda bm, s=subdiv: bmesh.ops.create_icosphere(bm, subdivisions=s, radius=1.0))
    faces = len(t.data.polygons)
    for solver in ('AUTO', 'MANIFOLD'):
        bpy.context.scene.mch_cut.solver = solver
        t0 = time.perf_counter()
        try:
            ce.perform_closed(bpy.context, 'CUT', [t], [ce.circle_loop((500, 500), (540, 500), 64)], TOP)
            ok = non_manifold(t) == 0
        except cg.CutError as ex:
            ok = False
            print(ex)
        ms = (time.perf_counter() - t0) * 1000
        rows.append((faces, solver, ms, ok))
        check(f'{faces} faces [{solver}] manifold cut', ok, f'{ms:.0f} ms')
mecha_lab.unregister()
print('\nfaces      solver     ms')
for faces, solver, ms, ok in rows:
    print(f'{faces:<10} {solver:<9} {ms:8.0f}')
sys.exit(1 if summary() else 0)
