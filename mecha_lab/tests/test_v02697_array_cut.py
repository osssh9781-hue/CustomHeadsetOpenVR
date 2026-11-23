"""0.24.297 Array Cut (user: "어레이컷 - 스케치 모드가 기본, 쉬프트 누르고 라인 그으면 어레이 가이드 (직선 / 프리드로우 / 원 /
박스), 그 라인을 따라서, 거리나 개수 사후 실시간 조정, 크기가 점점 작아지는 것도")."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import array_cut as ac, core_geometry as cg, lasso_sketch as ls, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_cut.depth_mode = 'SURFACE'
S.mch_cut.depth = 0.1


def sq(cx, cy, h=8):
    return [(cx - h, cy - h), (cx + h, cy - h), (cx + h, cy + h), (cx - h, cy + h)]


def hole(x, y):
    C.view_layer.update()
    r = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return bool(r[0]) and r[1].z < 0.45          # (the plate's top is at 0.5)


def plate():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    ls.clear(S)
    if ac.record(S):
        del S[ac.KEY]
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    ob = C.active_object
    ob.scale = (3.0, 2.0, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    return ob


check('Array Cut is a tool (Cut group, enum 89, a sketch tool always)', 'ACUT' in ts.TOOL_BY_ID
      and 'ACUT' in dict(ts.TOOL_GROUPS)['Cut'] and ts._ENUM_NUMBERS['ACUT'] == 89 and ls.enabled(C, 'ACUT')
      and 'ACUT' in ls.MODES)
# pure: the copies along a line
path, closed = ac.guide_path('LINE', [(0, 0), (10, 3), (100, 0)], (0, 0))
cps = ac.copies([sq(0, 0, 2)], path, closed, 5, 0.0, 0.5)
cx = [sum(q[0] for q in cp[0]) / 4 for cp in cps]
size = [max(q[0] for q in cp[0]) - min(q[0] for q in cp[0]) for cp in cps]
check('copies along a Line: 5, the first the shape itself, evenly to the end; End Size 0.5 shrinks them to half',
      len(cps) == 5 and [round(x) for x in cx] == [0, 25, 50, 75, 100] and abs(size[0] - 4) < 1e-6 and abs(size[-1] - 2) < 1e-6,
      (cx, size))
path, closed = ac.guide_path('CIRCLE', [(0, 0), (50, 0)], (50, 0))
cps = ac.copies([sq(50, 0, 2)], path, closed, 4, 0.0, 1.0)
cs = [(round(sum(q[0] for q in cp[0]) / 4), round(sum(q[1] for q in cp[0]) / 4)) for cp in cps]
check('Circle: round the start point, starting at the shape, 4 at 90 deg', cs == [(50, 0), (0, 50), (-50, 0), (0, -50)], cs)
path, closed = ac.guide_path('BOX', [(0, 0), (40, 20)], (0, 0))
check('Box: a closed rectangle from the shape\'s corner', closed and _ if (_ := True) else False)
check('... its length the rectangle\'s outline (120)', abs(ac._length(path, closed) - 120) < 1e-6, ac._length(path, closed))
st_ = ac.stations([(0, 0), (100, 0)], False, 50, 30.0)
check('Spacing 30 px on a 100 line: a cut every 30 (4 of them), Count only a limit', [round(p[0][0]) for p in st_] == [0, 30, 60, 90])

# the tool: sketch, then the guide
ob = plate()
st = S.mch_acut
st.guide = 'LINE'
st.count = 5
st.end_scale = 1.0
msg = ls.add(C, 'ACUT', [sq(300, 500)], TOP)
check('a plain draw: into the sketch, nothing cut yet', ls.data(S) is not None and not hole(-2.0, 0.0), msg)
msg = ac.set_guide(C, [(300, 500), (500, 520), (700, 500)], TOP)
check('Shift + draw a Line guide: 5 cuts from the shape to the end of the line (x -2 ... 2), closed mesh, sketch gone',
      all(hole(x, 0.0) for x in (-2.0, -1.0, 0.0, 1.0, 2.0)) and not hole(-1.5, 0.0) and non_manifold(ob) == 0
      and ls.data(S) is None and ac.record(S) is not None, msg)
st.count = 3
ac.flush()
check('live: Count 3 -> cuts at -2, 0, 2 only (the part cut again from its kept mesh)',
      hole(-2.0, 0) and hole(0.0, 0) and hole(2.0, 0) and not hole(-1.0, 0) and not hole(1.0, 0) and non_manifold(ob) == 0)
st.spacing = 0.5
st.count = 20
ac.flush()
check('live: Spacing 0.5 (Count 20 as a limit): a cut every 0.5 from -2 to 2 (9)', all(hole(-2.0 + 0.5 * k, 0) for k in range(9))
      and not hole(-1.75, 0), [hole(-2.0 + 0.5 * k, 0) for k in range(9)])
st.spacing = 0.0
st.count = 5
st.end_scale = 0.3
ac.flush()
check('live: End Size 0.3 - the last cut small (0.06 wide: 2.05 not cut, 2.0 cut), the first as drawn',
      hole(2.0, 0) and not hole(2.05, 0) and hole(-1.95, 0), (hole(2.0, 0), hole(2.05, 0)))
st.end_scale = 1.0
st.guide = 'CIRCLE'
ac.flush()
check('live: Guide Circle - round the guide\'s start (x -2) through the shape: cuts on a 4-wide circle', hole(-2.0, 0)
      and non_manifold(ob) == 0)
st.guide = 'LINE'
ac.flush()
bpy.ops.mch.array_cut_apply()
check('Apply (Enter): kept, no live record, its kept meshes gone',
      ac.record(S) is None and not any(m.name.startswith('MCH_ArrayCutBackup_') for m in bpy.data.meshes))
st.count = 2
ac.flush()
check('... the settings no longer change it', hole(1.0, 0))
# Free / Box guides
ob = plate()
st.guide = 'BOX'
st.count = 12
ls.add(C, 'ACUT', [sq(300, 400)], TOP)
ac.set_guide(C, [(300, 400), (700, 600)], TOP)
check('Box guide: 12 cuts round the 4 x 2 rectangle (one every 1.0: on every corner)', hole(-2.0, -1.0) and hole(2.0, 1.0) and hole(2.0, -1.0)
      and hole(-2.0, 1.0) and non_manifold(ob) == 0)
ob = plate()
st.guide = 'FREE'
st.count = 3
ls.add(C, 'ACUT', [sq(300, 500)], TOP)
ac.set_guide(C, [(300 + 4 * k, 500 + 80 * math.sin(k / 100 * math.pi)) for k in range(101)], TOP)
check('Free guide: along the drawn arc (the middle cut 0.8 up)', hole(0.0, 0.8) and hole(2.0, 0.0) and not hole(0.0, 0.0))
st.guide = 'LINE'
try:
    ls.commit(C)
    err = ''
except cg.CutError as ex:
    err = str(ex)
ls.add(C, 'ACUT', [sq(300, 500)], TOP)
try:
    ls.commit(C)
    err = ''
except cg.CutError as ex:
    err = str(ex)
check('Enter with only a sketch: tells to Shift + draw the guide (no plain cut)', 'Shift' in err, err)
summary()
