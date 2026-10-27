"""0.24.58 Split with the live Mirror on: a shape drawn over the mirrored copy (the base mesh is only the real half)
is mirrored back onto the real half - Split's inner part failed ('does not intersect'), Cut already worked.
Auto Apply off: the live cutter is moved onto the real half too (the live Boolean only sees the base mesh)."""
from _harness import bpy, check, cube, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, symmetry as sy

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def square(x):
    cx, cy = TOP.to_screen(Vector((x, 0.5, 0)))
    return [(cx - 40, cy - 40), (cx + 40, cy - 40), (cx + 40, cy + 40), (cx - 40, cy + 40)]


def setup(gap=False, auto=True):
    fresh()
    C.scene.mch_cut.split_mode = 'GAP' if gap else 'NORMAL'
    C.scene.mch_settings.auto_apply = auto
    p = cube('P', size=2.0, loc=(2, 0, 0))                    # real half at x 1..3, the copy at -3..-1
    sy.set_mode(C, p, 'MIRROR')
    return p


def xs(ob):
    return [(ob.matrix_world @ v.co).x for v in ob.data.vertices]


def evaluated_verts(ob):
    dg = C.evaluated_depsgraph_get()
    return len(ob.evaluated_get(dg).data.vertices)


for gap in (False, True):
    p = setup(gap)
    try:
        msg = ce.perform_closed(C, 'SPLIT', [p], [square(-2.0)], TOP)
    except cg.CutError as ex:
        msg = 'FAILED ' + str(ex)[:120]
    piece = bpy.data.objects.get('P_Split')
    check(f'{"Gap " if gap else ""}Split drawn over the mirrored copy: works, the piece is cut from the real half '
          '(x 1.6..2.4) and keeps the Mirror', 'plit: P' in msg and piece is not None
          and 1.55 < min(xs(piece)) and max(xs(piece)) < 2.45 and len(p.data.vertices) == 16
          and piece.modifiers.get('MCH_Mirror') is not None and non_manifold(p) == 0 and non_manifold(piece) == 0,
          (msg[:120], piece and (min(xs(piece)), max(xs(piece)))))
p = setup()
msg = ce.perform_closed(C, 'SPLIT', [p], [square(2.0)], TOP)
piece = bpy.data.objects.get('P_Split')
check('Split on the real half: as before', 'Split: P' in msg and piece is not None and 1.55 < min(xs(piece)))
p = setup()
msg = ce.perform_closed(C, 'CUT', [p], [square(-2.0)], TOP)
check('Cut over the mirrored copy: still works', 'Cut: P' in msg and len(p.data.vertices) == 16)
for mode in ('CUT', 'SPLIT'):
    p = setup(auto=False)
    ce.perform_closed(C, mode, [p], [square(-2.0)], TOP)
    cutter = bpy.data.objects.get('MCH_Cut_Live')
    check(f'Auto Apply off, {mode} over the copy: the live cutter moved onto the real half, the part really cut',
          cutter is not None and 1.55 < min(xs(cutter)) and max(xs(cutter)) < 2.45
          and evaluated_verts(p) > 2 * 8, cutter and (min(xs(cutter)), evaluated_verts(p)))
p = setup(auto=False)
ce.perform_closed(C, 'CUT', [p], [square(2.0)], TOP)
cutter = bpy.data.objects.get('MCH_Cut_Live')
check('Auto Apply off on the real half: the cutter stays where drawn', 1.55 < min(xs(cutter)) < 1.65)
summary()
