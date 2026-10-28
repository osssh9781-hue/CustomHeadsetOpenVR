"""0.24.81 Quad Remesh (the C engine: ZBrush shelf / Mesh Tools) on a cut part with many hard edges took 10 - 31 s
for 7k faces (the user's 00001.fbx) and gave 2 - 4x the faces asked for:
* the even decimation that makes the coarse levels stops early on such a part (level 3 wanted 935 faces, got 8,906),
  so the 200 coarse sweeps ran on a level nearly as big as the fine one - a level gets the sweeps its size pays for;
* the finer retries: a 4x finer try tripled the time and gave 4x the faces, and a 2x finer try ran for a handful of
  open sides that the hole closing takes anyway - at most 2x now, and only when more than 1 % of the sides are open.
Measured on 00001.fbx (7,480 faces): Mostly 1/4: 10.4 -> 1.6 s, 1/2: 31.4 -> 8.3 s, 8k: 19.8 -> 5 s; All Quads 1/2:
8.7 -> 3.6 s with 7,450 faces (was 15,242); the same quads, open edges and distance to the part.
0.24.81 also: the alpha is no longer drawn inside the ZBrush brush circle (Preferences > Alpha in Brush Circle)."""
import time

from _harness import bpy, check, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import core_geometry as cg, quad_field as qf, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context

it = qf.level_iters([59840, 14960, 3740, 935], [57498, 14960, 3740, 934])
check('Levels that reach their counts: the sweeps as before (20/30, 30/40, 60/80, coarsest 200/200)',
      it == [(20, 30), (30, 40), (60, 80), (200, 200)], it)
it = qf.level_iters([59840, 14960, 3740, 935], [57498, 14960, 11010, 8906])
check('Levels that could not coarsen (a part with many hard edges): their sweeps cut by how far they fell short, never '
      'under the fine level\'s', it[:2] == [(20, 30), (30, 40)] and it[2] == (20, 30) and it[3] == (20, 30), it)
check('At most a 2x finer retry, and none for a few open sides (1 %, at least 16)', qf.CUT_TRIES == (1, 2)
      and qf.HOLES_OK == 0.01 and 'max(16, HOLES_OK' in __import__('inspect').getsource(qf.remesh_cut))


def part():
    """A cut-like part with many hard edges: a cube with a beveled grid of pockets (about 3k faces)."""
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.select_all(action='SELECT')
    bpy.ops.mesh.subdivide(number_cuts=5)
    bpy.ops.mesh.select_all(action='DESELECT')
    bpy.ops.object.mode_set(mode='OBJECT')
    for p in ob.data.polygons:
        p.select = (p.index % 3 == 0)
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.inset(thickness=0.05, depth=-0.04)
    bpy.ops.object.mode_set(mode='OBJECT')
    m = ob.modifiers.new('b', 'BEVEL')
    m.width, m.segments = 0.015, 2
    bpy.ops.object.modifier_apply(modifier='b')
    return ob


if qf.available():
    ob = part()
    n0 = len(ob.data.polygons)
    for mode, target in (('MOSTLY', n0 // 2), ('ALL', n0 // 2)):
        src = ob.copy()
        src.data = ob.data.copy()
        C.scene.collection.objects.link(src)
        t = time.perf_counter()
        msg = qf.remesh_object(src, target, all_quads=mode == 'ALL', crease_deg=30.0)
        took = time.perf_counter() - t
        n = len(src.data.polygons)
        check(f'{mode} on a {n0:,}-face part with many hard edges, target {target:,}: within 2.2x of the count asked '
              f'for, closed, quads, under 20 s', target * 0.4 <= n <= target * 2.2 and non_manifold(src) == 0
              and cg.non_manifold_edge_count(src.data) == 0 and took < 20.0
              and sum(1 for p in src.data.polygons if len(p.vertices) == 4) > 0.8 * n, (n, round(took, 1), msg[:90]))
else:
    check('(the C engine is not available here: the remesh runs were skipped)', True)

# --- the alpha no longer drawn in the brush circle -------------------------------------------------------------------
props = __import__('mecha_lab.workspace_ui', fromlist=['x']).MCH_AddonPreferences.bl_rna.properties
check('Preferences > Alpha in Brush Circle exists, off by default', 'alpha_overlay' in props
      and props['alpha_overlay'].default is False)
src = __import__('inspect').getsource(zs._alpha_slot)
check('... the alpha slot follows it (the alpha picture inside the circle painted its black parts solid)',
      "pref('alpha_overlay', False)" in src)
summary()
