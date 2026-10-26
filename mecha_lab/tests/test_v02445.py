"""0.24.34 Scarf Cape: the Cape, but the folds run across (like a draped scarf); Gravity sags the middle down.
Its own tool and settings (Scene.mch_scape); the Cape is unchanged."""
import math
from types import SimpleNamespace

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Euler, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import cape_gen as cp, core_geometry as cg, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
check('Scarf Cape tool: in the list, with its settings and icon', 'SCAPE' in {t[0] for t in ts.VISIBLE_TOOLS}
      and 'SCAPE' in uts.DRAWERS and 'SCAPE' in ts.SHAPE_TOOLS and ts.TOOL_BY_ID['SCAPE'][3] == 'scarf_cape')
check('its own settings; Gravity only there by default use', hasattr(S, 'mch_scape') and S.mch_scape != S.mch_cape
      and 0.0 < S.mch_scape.gravity <= 1.0)

# the folds on a flat test sheet (no body in the way)
far = BVHTree.FromPolygons([Vector((0, -100, 0)), Vector((1, -100, 0)), Vector((0, -100, 1))], [(0, 2, 1)])
grid = [[Vector((-1 + 2 * i / 40, 1.0, -2 * k / 30)) for k in range(31)] for i in range(41)]


def sheet(fold_dir, gravity=0.0):
    p = SimpleNamespace(seed=1, folds=6, fold_depth=0.04, fold_random=0.0, wind=0.0, wind_dir=0.0,
                        fold_dir=fold_dir, gravity=gravity)
    return cp.shape_sheet(grid, Vector((0, 0, 0)), p, 3.0, far, 0.0)


def wiggle(g):
    """(change down the columns, change across the rows) of how far the sheet was pushed out"""
    off = [[(g[i][k] - grid[i][k]).y for k in range(31)] for i in range(41)]
    down = sum(abs(off[i][k + 1] - off[i][k]) for i in range(41) for k in range(30)) / (41 * 30)
    across = sum(abs(off[i + 1][k] - off[i][k]) for i in range(40) for k in range(31)) / (40 * 31)
    return down, across


d_down, d_across = wiggle(sheet('DOWN'))
a_down, a_across = wiggle(sheet('ACROSS'))
check('Cape: folds run down (the sheet changes across it)', d_across > 3 * d_down, (d_down, d_across))
check('Scarf Cape: folds run across (the sheet changes down it)', a_down > 3 * a_across, (a_down, a_across))
g0, g1 = sheet('ACROSS', 0.0), sheet('ACROSS', 0.8)
check('Gravity: the middle sags down, the drawn ends stay', g1[20][30].z < g0[20][30].z - 0.05
      and abs(g1[0][30].z - g0[0][30].z) < 1e-6 and abs(g1[20][0].z - g0[20][0].z) < 1e-6,
      (g0[20][30].z, g1[20][30].z))
check('Gravity does nothing on a normal Cape', all(abs(a.z - b.z) < 1e-9 for a, b in
                                                  zip(sheet('DOWN', 0.0)[20], sheet('DOWN', 0.8)[20])))

# on a body
bpy.ops.mesh.primitive_cylinder_add(radius=0.6, depth=4.0, vertices=48, location=(0, 0, 0))
body = C.active_object
body.name = 'Body'
BACK = cg.OrthoProjector(Euler((math.radians(90), 0, math.pi)).to_quaternion())   # behind (+Y), looking -Y
SHORT = [[(405, 560), (595, 560), (595, 530), (405, 530)]]
cape_before = {k: getattr(S.mch_cape, k) for k in cp.LIVE_KEYS}
msg = cp.perform(C, SHORT, BACK, 'ACROSS')
ob = C.active_object
check('Scarf Cape on the body: live, closed mesh, folds across', cp.live_cape(C, 'ACROSS') == ob
      and ob.mch_cape.fold_dir == 'ACROSS' and non_manifold(ob) == 0 and 'Scarf Cape' in msg and 'ScarfCape' in ob.name,
      (msg, non_manifold(ob)))
check('it is not a plain Cape (the Cape panel does not take it)', cp.live_cape(C, 'DOWN') is None)
z0 = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
ob.mch_cape.gravity = 1.0
z1 = min((ob.matrix_world @ v.co).z for v in ob.data.vertices)
check('Gravity is live (more = hangs lower in the middle)', z1 < z0 - 0.01 and ob.mch_cape.last_error == '', (z0, z1))
check('the next Scarf Cape starts like this one; the Cape settings did not change', S.mch_scape.gravity == 1.0
      and {k: getattr(S.mch_cape, k) for k in cp.LIVE_KEYS} == cape_before)
cp.perform(C, SHORT, BACK)
check('a plain Cape still has folds down', C.active_object.mch_cape.fold_dir == 'DOWN'
      and cp.live_cape(C, 'DOWN') == C.active_object)
C.view_layer.objects.active = ob
bpy.ops.mch.cape_apply()
check('Apply: plain mesh', cp.source(ob) is None and not ob.mch_cape.live)
summary()
