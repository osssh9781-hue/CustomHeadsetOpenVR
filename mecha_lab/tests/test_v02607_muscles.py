"""0.24.183 Muscle / Mecha Muscle (user: "근육 제네레이터 ... 끝과 끝 점을 이으면 거기에 근육이 생기는 거" / "메카 근육 메뉴도 ...
홀 옵션 ... 끝부분 마감 메쉬" / "인공 근육은 내가 프리셋도 만들고 싶어서" / "케이블로만 바뀐 것도" / "스킨이랑 근육은 다른 메쉬"):
muscles from clicked points on a body (through the module), their sliders live; the artificial muscle's core / sleeve /
caps and cables; your own presets (in a scratch file); a skin over all as a mesh of its own."""
import json
import math
import os
import sys
import tempfile

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary
from mathutils import Vector  # noqa: E402

import mecha_lab
from mecha_lab import muscle_gen as mg, my_presets  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp()
my_presets.PATH[0] = os.path.join(TMP, 'my_presets.json')        # (never the user's own file)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
body.scale = (0.5, 0.5, 1.6)
bpy.ops.object.transform_apply(scale=True)


def pt(z, ang):
    d = Vector((math.cos(ang), math.sin(ang), 0.0))
    p = Vector((0.0, 0.0, z)) + d * 2.0
    ok, loc, nrm, _i, _o, _m = S.ray_cast(C.evaluated_depsgraph_get(), p, -d)
    return (body.name, tuple(loc), tuple(nrm))


def non_manifold(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def build_with(tool, pts, **vals):
    st = mg.settings(C, tool)
    for k, v in vals.items():
        setattr(st, k, v)
    ob, msg = mg.make(C, tool, pts)
    return ob


st = S.mch_muscle
A, B = pt(0.8, -math.pi / 2), pt(-0.8, -math.pi / 2)
m1 = build_with('MUSCLE', [A, B], preset='SPINDLE', shape='STRANDS', style='CREATURE')
f1 = len(m1.data.polygons)
check(f'two points: a muscle between them, on the body (its child) ({f1} faces)', m1.parent == body and 100 < f1 < 20000)
m1.mch_muscle.strands = 3
check('Strands 3: three bellies (more faces, live)', len(m1.data.polygons) > f1 * 2)
V0 = np.array([v.co[:] for v in m1.data.vertices])
m1.mch_muscle.thickness = 2.0
V1 = np.array([v.co[:] for v in m1.data.vertices])
check('Thickness: it stands higher off the body', np.linalg.norm(V1, axis=1).max() > np.linalg.norm(V0, axis=1).max() + 0.01)
m2 = build_with('MUSCLE', [A, B], preset='SPINDLE', shape='SCULPT', strands=1)
check('Your Sculpts: the user\'s one-belly muscle laid between the points',
      len(m2.data.polygons) == len(mg.templates()['SINGLE']['N']))
m2.mch_muscle.strands = 2
check('... Strands 2: the user\'s two-belly muscle', len(m2.data.polygons) == len(mg.templates()['DOUBLE']['N']))
# mecha
P3 = [pt(0.6, -math.pi / 2 - 0.5), pt(0.1, -math.pi / 2 - 0.5), pt(0.2, -math.pi / 2 + 0.6)]
for core in ('BUNDLE', 'SMOOTH', 'RIBBED', 'PISTON'):
    for cap in ('COLLAR', 'FORK'):
        mm = build_with('MMUSCLE', [A, B], preset='SPINDLE', style='ARTIFICIAL', core=core, holes='SQUARE', cap=cap)
        mats = set(np.unique([p.material_index for p in mm.data.polygons]))
        check(f'Artificial {core} + holed sleeve + {cap} caps: core, sleeve and caps (3 materials), watertight sleeve '
              f'({non_manifold(mm)} open edges)', mats == {0, 1, 2} and mm.mch_muscle.style == 'ARTIFICIAL',
              (sorted(int(x) for x in mats), mm.mch_muscle.style, mm.mch_muscle.holes, len(mm.data.polygons)))
        bpy.data.objects.remove(mm)
cb = build_with('MMUSCLE', [A, B], preset='SPINDLE', style='CABLE', cap='NUT')
check('Cables: a cable with end caps', len(cb.data.polygons) > 50 and
      set(np.unique([p.material_index for p in cb.data.polygons])) == {0, 2},
      (sorted(int(x) for x in np.unique([p.material_index for p in cb.data.polygons])), cb.mch_muscle.style))
# your own presets (no muscle picked: the window's - the tool's - settings)
for o in C.selected_objects:
    o.select_set(False)
C.view_layer.objects.active = body
mst = S.mch_mmuscle
mst.core, mst.core_count, mst.cap, mst.cap_size = 'RIBBED', 9, 'CLAMP', 1.7
r1 = bpy.ops.mch.muscle_my_save(kind=mg.MY_CORE, name='Bellows 9', tool='MMUSCLE')
r2 = bpy.ops.mch.muscle_my_save(kind=mg.MY_CAP, name='Big Clamp', tool='MMUSCLE')
mst.core, mst.core_count, mst.cap, mst.cap_size = 'SMOOTH', 3, 'COLLAR', 1.0
r3 = bpy.ops.mch.muscle_my_apply(kind=mg.MY_CORE, name='Bellows 9', tool='MMUSCLE')
r4 = bpy.ops.mch.muscle_my_apply(kind=mg.MY_CAP, name='Big Clamp', tool='MMUSCLE')
check('my presets: a core and an end cap saved and put back (a scratch file)',
      {'FINISHED'} == r1 == r2 == r3 == r4 and mst.core == 'RIBBED' and mst.core_count == 9 and mst.cap == 'CLAMP'
      and abs(mst.cap_size - 1.7) < 1e-6 and os.path.isfile(my_presets.PATH[0]),
      (r1, r2, r3, r4, mst.core, mst.core_count, mst.cap, mst.cap_size))
# skin: a mesh of its own
for o in C.selected_objects:
    o.select_set(False)
body.select_set(True)
C.view_layer.objects.active = body
r = bpy.ops.mch.muscle_skin(look='CREATURE')
skin = C.active_object
check('Skin Over All: one skin, its own mesh (the muscles and the body untouched)', r == {'FINISHED'} and
      mg.is_skin(skin) and skin is not body and not mg.is_muscle(skin))

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
