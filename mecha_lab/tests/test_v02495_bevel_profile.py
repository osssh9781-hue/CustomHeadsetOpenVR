"""0.24.95 Base Mesh Bevel / Chamfer profiles keep their shape through Divide (user, bevel.fbx: "베벨로 된 거 내가
디바이드 하면 이렇게 옆면이 떠 - 이런 종류로 또 테스트 해 봐").  The profile's rows meet the cap and the wall at 45 / n
degrees and each other at 90 / n: by angle alone (30) a 2-segment round had its BORDERS soft and its middle ROW a line,
so Divide rounded the flat sides into the bevel and folded the round.  Now the band's borders are lines, its rows soft
(``edge_memory.SOFT``, which Bake High Poly honours past the angle), and a miter at a sharp outline corner is one line
from the wall's corner to the cap's (half of it soft folded the corner)."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import base_mesh as bm_, bake_highpoly as bk, core_geometry as cg, edge_memory as em

mecha_lab.register()
C = bpy.context
PPU = 100.0
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=PPU)
RECT = [(0.58, 0.28), (-0.58, 0.28), (-0.58, -0.28), (0.58, -0.28)]
CIRCLE = [(math.cos(2 * math.pi * i / 40) * 0.6, math.sin(2 * math.pi * i / 40) * 0.6) for i in range(40)]


def part(profile, width, segs, outline, height=1.11, sides='TOP'):
    fresh()
    C.scene.mch_settings.auto_apply = True
    p = bm_.scene_defaults(C)
    p.sketch = False
    p.profile, p.height, p.bevel_width, p.bevel_segments, p.bevel_sides = profile, height, width, segs, sides
    before = set(bpy.data.objects)
    bm_.perform_base(C, [[(500 + x * PPU, 500 + y * PPU) for x, y in outline]], TOP)
    return [o for o in bpy.data.objects if o not in before][0]


def angles(me):
    e_s, f_s, st, en = em._edge_faces(me)
    s2 = st[(en - st) == 2]
    n = np.array([p.normal[:] for p in me.polygons])
    return e_s[s2], np.degrees(np.arccos(np.clip(np.einsum('ij,ij->i', n[f_s[s2]], n[f_s[s2 + 1]]), -1, 1)))


def divide_quality(ob):
    """(faces of the Divide turned more than 107 degrees from the part's surface under them, farthest point off it)"""
    size = max(ob.dimensions)
    bvh = BVHTree.FromObject(ob, C.evaluated_depsgraph_get())
    hp, _info = bk.build(C, ob, target_faces=40_000, bevels='DIVIDE')
    mw, ow = hp.matrix_world, ob.matrix_world.inverted()
    flipped = 0
    for pf in hp.data.polygons:
        _loc, nrm, _i, _d = bvh.find_nearest(ow @ (mw @ Vector(pf.center)))
        if nrm is not None and (mw.to_3x3() @ Vector(pf.normal)).normalized().dot(nrm) < -0.3:
            flipped += 1
    co = np.array([v.co[:] for v in hp.data.vertices])[::3]
    off = max(bvh.find_nearest(ow @ (mw @ Vector(q)))[3] for q in co) / size
    return flipped, off


# ---- the marks of a 2-segment round on a rectangle (the case that folded)
ob = part('BEVEL', 0.2, 2, RECT)
me = ob.data
e, ang = angles(me)
mk = em.marked(me)[e]
soft = em.soft(me)[e]
border = (ang > 20) & (ang < 25)                    # (22.5: the round's borders with the cap and the wall)
row = (ang > 43) & (ang < 47)                       # (45: its middle row)
check('2-segment Bevel: the round\'s borders (22.5 degrees) are lines (before: soft), its row (45) is soft '
      '(before: a line)', border.sum() >= 8 and mk[border].all() and row.sum() >= 4 and not mk[row].any()
      and soft[row].all(), (int(border.sum()), int(mk[border].sum()), int(row.sum()), int(mk[row].sum())))
check('... the build flags are gone from the mesh (only the marks and the soft rows stay)',
      all(me.attributes.get(n) is None for n in em.PROFILE_FLAGS) and me.attributes.get(em.SOFT) is not None)
hard = bk.hard_mask(me)[e]
check('... Bake High Poly keeps the 45-degree row soft (past its 30-degree angle) and the borders hard',
      not hard[row].any() and hard[border].all())
f, off = divide_quality(ob)
check(f'... Divide: no face turned against the part (before: 8), {off * 100:.2f} % off (before 1.48 %)',
      f == 0 and off < 0.014, (f, off))

# ---- 3 and 4 segments: the miter at the rectangle's corners is one line from the wall to the cap
for segs in (3, 4):
    ob = part('BEVEL', 0.05 * segs / 2, segs, RECT)
    me = ob.data
    e, ang = angles(me)
    mk = em.marked(me)[e]
    co = np.array([v.co[:] for v in me.vertices])
    ev = np.array([ed.vertices[:] for ed in me.edges])[e]
    climb = np.abs(co[ev[:, 0], 2] - co[ev[:, 1], 2]) > 1e-4
    band_top = (co[ev[:, 0], 2] > 1.11 - 0.2) & (co[ev[:, 1], 2] > 1.11 - 0.2)
    miters = climb & band_top & (ang > 1)
    f, off = divide_quality(ob)
    check(f'{segs}-segment Bevel: every miter at the corners marked ({int(miters.sum())}; before: the ones near the cap '
          f'soft), Divide with no face turned against the part, {off * 100:.2f} % off',
          miters.sum() >= 4 * segs and mk[miters].all() and f == 0 and off < 0.01,
          (int(miters.sum()), int(mk[miters].sum()), f, off))

# ---- a round outline: the miters there are soft (the round's sweep along a curve), no fold
ob = part('BEVEL', 0.1, 3, CIRCLE, height=0.6)
me = ob.data
e, ang = angles(me)
co = np.array([v.co[:] for v in me.vertices])
ev = np.array([ed.vertices[:] for ed in me.edges])[e]
climb = (np.abs(co[ev[:, 0], 2] - co[ev[:, 1], 2]) > 1e-4) & (co[ev[:, 0], 2] > 0.45) & (co[ev[:, 1], 2] > 0.45)
f, off = divide_quality(ob)
check(f'Round outline + 3-segment Bevel: the band\'s steps round the circle stay soft ({int(climb.sum())}), Divide '
      f'smooth with no fold ({off * 100:.2f} % off)', climb.sum() > 40 and not em.marked(me)[e][climb].any()
      and em.soft(me)[e][climb].all() and f == 0 and off < 0.01, (int(climb.sum()), f, off))

# ---- Chamfer and Bevel on both sides
for profile, segs, sides in (('CHAMFER', 1, 'TOP'), ('BEVEL', 3, 'BOTH')):
    ob = part(profile, 0.1, segs, RECT, sides=sides)
    f, off = divide_quality(ob)
    check(f'{profile} {segs} on {sides}: Divide with no face turned against the part ({off * 100:.2f} % off)',
          f == 0 and off < 0.01, (f, off))
summary()
