"""0.24.58 Box Hide follows the live symmetry: on a part with a live Mirror / Radial the drawn shape is hidden on
every symmetric copy too (the hiding sits after the Mirror in the stack, so it hid only the side drawn on)."""
import inspect

from _harness import bpy, check, cube, fresh, summary
import bmesh
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import box_hide as bh, core_geometry as cg, symmetry as sy

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def square(x, y=0.5, h=40):
    cx, cy = TOP.to_screen(Vector((x, y, 0)))
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def part(mode='MIRROR'):
    fresh()
    p = cube('P', size=2.0, loc=(2, 0, 0))
    bm = bmesh.new()
    bm.from_mesh(p.data)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=3, use_grid_fill=True)
    bm.to_mesh(p.data)
    bm.free()
    sy.set_mode(C, p, mode)
    return p


def sides(ob):
    """(points right of the mirror, points left) of what is shown."""
    me = ob.evaluated_get(C.evaluated_depsgraph_get()).data
    xs = [(ob.matrix_world @ v.co).x for v in me.vertices]
    return sum(1 for x in xs if x > 0), sum(1 for x in xs if x < 0)


st = C.scene.mch_hide if hasattr(C.scene, 'mch_hide') else None
check('Follow Symmetry: on by default (the old local Mirror X stays for parts without a live Mirror)',
      st is not None and st.follow_symmetry and not st.mirror)
for x, label in ((2.0, 'the real half'), (-2.0, 'the mirrored copy')):
    p = part()
    before = sides(p)
    msg = bh.perform(C, [p], [square(x)], TOP)
    after = sides(p)
    check(f'Drawn over {label}: both sides hidden the same', after[0] == after[1] and after != before
          and 'symmetric cop' in msg, (before, after, msg))
p = part()
C.scene.mch_hide.follow_symmetry = False             # (fresh() makes a new scene)
before = sides(p)
bh.perform(C, [p], [square(2.0)], TOP)
after = sides(p)
check('Follow Symmetry off: only the side drawn on (as before)', after[0] != before[0] and after[1] == before[1],
      (before, after))
p = part()
before = sides(p)
bh.perform(C, [p], [square(2.0)], TOP)
bh.perform(C, [p], [square(-2.0)], TOP, restore=True)
check('Alt (show again) over the copy: both sides back', sides(p) == before or not bh.is_hidden(p), sides(p))
p = part()
bh.perform(C, [p], [square(2.0)], TOP)
shown = sides(p)
bh.apply(C, p)
check('Apply: the real half keeps the hole, the Mirror shows it on both sides', sides(p) == shown
      and not bh.is_hidden(p) and p.modifiers.get('MCH_Mirror') is not None, (shown, sides(p)))
p = part('RADIAL')
n = C.scene.mch_rsym.count
copies = bh.symmetry_copies(C, p)
check(f'Radial x{n}: hidden on the other {n - 1} turns too', len(copies) == n - 1, len(copies))
p = part('KALEIDO')
copies = bh.symmetry_copies(C, p)
check('Kaleido (turns x mirror): every copy', len(copies) == 2 * C.scene.mch_rsym.count - 1, len(copies))
fresh()
q = cube('Q', size=2.0, loc=(2, 0, 0))
check('No live symmetry: no copies (the local Mirror X button still works there)', bh.symmetry_copies(C, q) == [])
check('Panel: Follow Symmetry next to Mirror X', 'follow_symmetry' in inspect.getsource(bh.draw))
summary()
