"""0.24.95 Bevel fuzz (user: "베벨로만 한 50개 만들어 봐 - 베벨로 만든 거 컷으로 자르고 베벨로 컷한 거 이런 걸로"): 50
Base Mesh Bevel parts, each cut 5 times with Edge Finish Bevel / Base Mesh Bevel subtracts, then Divided.  Two causes
of the folds Divide made there:
(1) where a cut's Bevel band ran into a crease of the part 0.001 off the hole's wall, Blender's bevel folded a lip
    of the wall's face back over it - the face's outline crosses itself (``core_geometry.tangled_faces``); the
    Edge Finish now collapses the lip's short side (``untangle``).
(2) at the bottom rim of a polygon hole the band's rows lie almost flat and the short miter edge between two long
    rows had its Catmull-Clark edge point dragged 0.1 along the part - ``_crease_strays`` only creased such edges
    when the point LEFT the part; now also when the test level folds there (``_folded_points``)."""
import os
import re
import subprocess
import sys

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bake_highpoly as bk, core_geometry as cg

mecha_lab.register()
fresh()
HERE = os.path.dirname(os.path.abspath(__file__))


def one_face(pts):
    me = bpy.data.meshes.new('f')
    me.from_pydata([(x, y, 0.0) for x, y in pts], [], [list(range(len(pts)))])
    me.update()
    return me


# ---- the lip (the hole wall's face of fuzz seed 2: a 0.013-wide strip whose ends fold 0.001 back over it)
lip = [(0.0143, -1.0424), (0.0, -1.0317), (0.0, 0.9235), (0.0143, 0.9342), (0.0133, 0.9342), (0.0133, -1.0424)]
me = one_face(lip)
found = cg.tangled_faces(me)
check('tangled_faces: the lip face (6 corners, its ends folded 0.001 back over it) crosses itself',
      list(found) == [0] and len(found[0]) == 2, found)
n = cg.untangle(me, 0.005)
check('untangle: the two 0.001 sides collapsed, the face a plain 4-cornered strip, crossing nothing',
      n == 2 and not cg.tangled_faces(me) and len(me.polygons) == 1 and len(me.polygons[0].vertices) == 4,
      (n, len(me.polygons[0].vertices)))
me = one_face(lip)
check('... sides longer than the limit are left alone (the face as it was)', cg.untangle(me, 0.0005) == 0
      and len(me.polygons[0].vertices) == 6)
check('tangled_faces: a bow-tie quad crosses itself; a convex hexagon and an L-shape do not',
      list(cg.tangled_faces(one_face([(0, 0), (1, 1), (1, 0), (0, 1)]))) == [0]
      and not cg.tangled_faces(one_face([(1, 0), (0.5, 0.9), (-0.5, 0.9), (-1, 0), (-0.5, -0.9), (0.5, -0.9)]))
      and not cg.tangled_faces(one_face([(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)])))

# ---- _folded_points: a sheet folded flat over itself is found, a flat sheet is not
me = bpy.data.meshes.new('fold')
me.from_pydata([(0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.2, 0, 0.001), (0.2, 1, 0.001)], [],
               [(0, 1, 2, 3), (1, 4, 5, 2)])
me.update()
pts = bk._folded_points(me)
flat = bpy.data.meshes.new('flat')
b = bmesh.new()
bmesh.ops.create_grid(b, x_segments=4, y_segments=4, size=1.0)
b.to_mesh(flat)
b.free()
check('_folded_points: the points of two faces folded back over each other (180 degrees), none on a flat grid',
      pts.all() and not bk._folded_points(flat).any(), pts.tolist())


# ---- the fuzz seeds, rerun as they were found
def run(seed, steps):
    p = subprocess.run([sys.executable, os.path.join(HERE, 'fuzz', 'bevel_scenario.py'), str(seed), str(steps)],
                       capture_output=True, text=True, timeout=600)
    out = p.stdout + p.stderr
    div = {}
    for m in re.finditer(r'STEP divide (\S+): [\d,]+ faces \| Bake HP folds (\d+) flipped (\d+) off ([\d.]+) %', out):
        div[m.group(1)] = (int(m.group(2)), int(m.group(3)), float(m.group(4)))
    return out, div


out, div = run(2, 1)
check('Fuzz seed 2, step 1 (a circle cut with a Bevel finish through a Chamfer\'s crease): no face crossing itself '
      f'(before: 10), Bake HP Divide folds over nowhere (before: 122) - {div}',
      'DONE' in out and 'tangled' not in out and div.get('MCH_Base', (1,))[0] == 0, div)
out, div = run(20, 5)
d = div.get('MCH_Base')
check(f'Fuzz seed 20 (polygon holes through a 6-row Bevel part): Bake HP Divide {d[2] if d else "-"} % off the part '
      f'(before: 1.18 %), {d[0] if d else "-"} folded edges (before: 473)',
      'DONE' in out and d is not None and d[2] < 1.0 and d[0] < 473, d)
out, div = run(6, 5)
step5 = next((l for l in out.splitlines() if l.startswith('STEP 5 ')), '')
check('Fuzz seed 6 (a GN Bevel pocket on a 17k-face part, where the first run ran out of memory - 13.6 GB): the '
      'slow sure-way sweep is skipped and the cut says why (before: "GN Edge found no new border edges")',
      'DONE' in out and 'Edge Finish skipped: the quick sweep did not come out clean' in step5, step5[-160:])
summary()
