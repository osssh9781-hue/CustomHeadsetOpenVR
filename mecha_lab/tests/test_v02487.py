"""0.24.58 GN Edge Bevel / Chamfer on a hand-drawn cut and a thin part: the profile directions are averaged along
the rim within the width (a slightly zigzag outline gave a notch at every kink - big widths crossed their
neighbours' profiles: torn faces, open edges, very slow), real corners keep their exact mitre, and the width is
limited to under half of what is left of the part (both sides' bevels ran into each other)."""
import math
import random
import time

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import base_mesh as bm_, core_geometry as cg, cut_engine as ce, lasso_line, rim_sweep

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
FRONT = cg.OrthoProjector(Quaternion((math.cos(math.pi / 4), math.sin(math.pi / 4), 0, 0)), pixels_per_unit=100.0)
S.mch_brush.line_mode = True
S.mch_brush.line_width = 0.3
path = [(200 + 10 * i, 500 + 60 * math.sin(i / 30 * math.pi)) for i in range(31)]
bm_.perform_base(C, [lasso_line.line_loop(C, TOP, path, S.mch_brush, None)], TOP)
ob = C.active_object
zs = [(ob.matrix_world @ v.co).z for v in ob.data.vertices]
zmid = (min(zs) + max(zs)) / 2
random.seed(3)
top = [Vector((-1 + 5 * i / 100, 0, zmid + random.uniform(-0.012, 0.012) + 0.03 * math.sin(i / 5.0)))
       for i in range(101)]
loop = [FRONT.to_screen(p) for p in top + [Vector((4, 0, zmid - 5)), Vector((-1, 0, zmid - 5))]]
cut = S.mch_cut
cut.gn_finish, cut.gn_width, cut.gn_segments, cut.depth_mode = 'BEVEL', 0.198, 6, 'THROUGH'
t = time.perf_counter()
msg = ce.perform_closed(C, 'CUT', [ob], [loop], FRONT)
took = time.perf_counter() - t
check('Zigzag cut through a thin band with a big GN Bevel: closed result, no torn faces', 'GN Bevel' in msg
      and non_manifold(ob) == 0, (msg[:90], non_manifold(ob)))
check('... the width was limited where the band is thin (under half of the 0.1 left)',
      rim_sweep.LAST.get('limited') is not None and rim_sweep.LAST['limited'] < 0.05, rim_sweep.LAST)
print(f'(took {took:.1f} s)')
# pure parts: the rim runs, the smoothing keeps real corners
fresh()
bpy.ops.mesh.primitive_cube_add(size=2.0)
c = C.active_object
cut = C.scene.mch_cut                      # (fresh() makes a new scene)
cut.gn_finish, cut.gn_width, cut.gn_segments = 'CHAMFER', 0.1, 2
msg = ce.perform_closed(C, 'CUT', [c], [ce.rect_loop((450, 450), (550, 550))], TOP)
xs = sorted({round(v.co.x, 4) for v in c.data.vertices if abs(v.co.z - 1.0) < 1e-4})
check('A square cut keeps square corners: the chamfer is exactly the width all round (corners mitred)',
      non_manifold(c) == 0 and any(abs(x + 0.6) < 1e-3 for x in xs) and any(abs(x - 0.6) < 1e-3 for x in xs), xs)
summary()
