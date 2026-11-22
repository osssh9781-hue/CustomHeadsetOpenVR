"""0.24.284 Clean (Planar) (user: "지브러시에서 덩어리 잡아 오면 스컬핑한 상태 - 옆의 평평한 면이 있으면 그걸로 밀어서
정리", "클린이라고 새로", "그 부근의 평평한 면으로 그냥 밀어 버렸으면, 지브러시의 플래너처럼"): a lasso tool - the surface
you see inside the outline goes onto one plane (Both / Cut / Fill, Soft Edge, Height); outside it and the back of the part
stay as they are; the mesh keeps its points and faces."""
import math

import numpy as np

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import bottom_row, clean_flat as cf, core_geometry as cg, cut_engine as ce, tool_state as ts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
PPU = 300.0
TOP = cg.OrthoProjector(Quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=PPU)


def P(x, y):
    return (500 + x * PPU, 500 + y * PPU)


def lump(seed=1):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    box = C.active_object
    box.scale = (1.0, 0.7, 0.5)
    bpy.ops.object.transform_apply(scale=True)
    bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=0.6, location=(0.3, 0.0, 0.6), vertices=64)
    cyl = C.active_object
    m = box.modifiers.new('u', 'BOOLEAN')
    m.object, m.operation, m.solver = cyl, 'UNION', 'EXACT'
    C.view_layer.objects.active = box
    bpy.ops.object.modifier_apply(modifier='u')
    bpy.data.objects.remove(cyl)
    box.data.remesh_voxel_size = 0.02
    with C.temp_override(object=box, active_object=box):
        bpy.ops.object.voxel_remesh()
    m = box.modifiers.new('s', 'SMOOTH')                 # the soft edges a sculpt has
    m.factor, m.iterations = 1.0, 20
    with C.temp_override(object=box, active_object=box):
        bpy.ops.object.modifier_apply(modifier='s')
    rng = np.random.default_rng(seed)                     # the grain
    me = box.data
    co = np.array([v.co for v in me.vertices])
    no = np.array([v.normal for v in me.vertices])
    co += no * rng.normal(0, 0.003, len(co))[:, None]
    me.vertices.foreach_set('co', co.astype(np.float32).ravel())
    me.update()
    for o in list(C.selected_objects):
        o.select_set(False)
    box.select_set(True)
    C.view_layer.objects.active = box
    return box


def pts(o):
    return np.array([v.co for v in o.data.vertices])


def spread(Q):
    c = Q - Q.mean(0)
    return float(np.linalg.svd(c, full_matrices=False)[1][-1] / math.sqrt(len(Q)))


def run(ob, loop, **kw):
    st = S.mch_clean
    for k, v in dict(mode='BOTH', plane='FIT', height=0.0, soft=0.0, strength=1.0).items():
        setattr(st, k, kw.get(k, v))
    return cf.perform(C, [loop], TOP)


SQ = ce.rect_loop(P(-0.8, -0.5), P(-0.05, 0.5))      # over the top, away from the round boss


def in_sq(Q):
    return (Q[:, 0] > -0.78) & (Q[:, 0] < -0.07) & (np.abs(Q[:, 1]) < 0.48)


check('Clean (Planar) is a lasso tool (shapes), the Resolution box\'s Clean button picks it',
      'PLANAR' in ts.TOOL_BY_ID and 'PLANAR' in ts.SHAPE_TOOLS
      and any(i.action == ('tool', 'PLANAR') for _w, _h, its in bottom_row.boxes(C, 2400, 1400, 1.0) for i in its
              if i.kind == 'abtn' and i.label == 'Clean'))
import inspect  # noqa: E402
from mecha_lab import lasso_sketch, workspace_ui  # noqa: E402
modes = {e.identifier for e in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items}
src = inspect.getsource(ce)
check('wired like Mecha Holes: the lasso operator has the PLANAR mode, the drawn outline goes to clean_flat.perform '
      '(and in Sketch mode too), a workspace tool with the lasso keymap',
      'PLANAR' in modes and "self.mode == 'PLANAR'" in src and 'clean_flat.perform(context, loops' in src
      and 'PLANAR' in lasso_sketch.MODES and workspace_ui.MCH_TOOL_clean_planar.bl_idname == 'mecha.clean_planar'
      and any(k[0] == 'mch.cut_stroke' and dict(k[2]['properties']).get('mode') == 'PLANAR'
              for k in workspace_ui.MCH_TOOL_clean_planar.bl_keymap if k[2]), sorted(m for m in modes if 'PL' in m))
ob = lump()
P0 = pts(ob)
nv, nf = len(ob.data.vertices), len(ob.data.polygons)
msg = run(ob, SQ)
P1 = pts(ob)
top = in_sq(P0) & (P0[:, 2] > 0.4)
check('Both: the top under the outline made flat (off its plane: 20x less)', spread(P1[top]) < spread(P0[top]) / 20,
      (round(spread(P0[top]), 5), round(spread(P1[top]), 7), msg))
out = ~in_sq(P0) & (np.abs(P0[:, 0] + 0.42) > 0.45)
check('... outside the outline nothing moved', np.allclose(P1[out], P0[out], atol=1e-6))
back = P0[:, 2] < 0.0
check('... the back of the part (under it, facing away) never touched', np.allclose(P1[back], P0[back], atol=1e-6))
check('... the same points and faces (no remesh)', len(ob.data.vertices) == nv and len(ob.data.polygons) == nf)

ob = lump(2)
P0 = pts(ob)
run(ob, SQ, mode='CUT')
d = (pts(ob) - P0)[:, 2]
check('Cut: only what stands above the plane comes down (nothing goes up, no wall squashed)', d.max() < 1e-6 and -0.06 < d.min() < -1e-3,
      (float(d.max()), float(d.min())))
ob = lump(3)
P0 = pts(ob)
run(ob, SQ, mode='FILL')
d = (pts(ob) - P0)[:, 2]
check('Fill: only the hollows come up (nothing goes down)', d.min() > -1e-6 and d.max() > 1e-3,
      (float(d.min()), float(d.max())))
ob = lump(4)
P0 = pts(ob)
run(ob, SQ, height=-20.0, mode='CUT')
check('Height -20 % with Cut: a lower plane - the top comes down further', (pts(ob) - P0)[top, 2].mean() < -0.05,
      float((pts(ob) - P0)[top, 2].mean()))
ob = lump(5)
P0 = pts(ob)
run(ob, SQ, soft=40.0)
P1 = pts(ob)
mv = np.abs(P1 - P0).max(1)
Q = np.array([TOP.to_screen(Vector(p)) for p in P0[top]])
de = cf.edge_distance(Q, SQ)
near, mid = de < 10, de > 80
check('Soft Edge: near the outline the points move less than in the middle (no step)',
      mv[top][near].mean() < 0.5 * mv[top][mid].mean() and spread(P1[top][mid]) < spread(P0[top][mid]) / 5,
      (float(mv[top][near].mean()), float(mv[top][mid].mean())))
ob = lump(6)
P0 = pts(ob)
for o in list(C.selected_objects):
    o.select_set(False)
msg = run(ob, SQ)
check('nothing selected: the part under the outline is the one', not np.allclose(pts(ob), P0), msg)
try:
    run(ob, ce.rect_loop(P(1.4, 1.4), P(1.6, 1.6)))
    ok = False
except cg.CutError as ex:
    ok = 'nothing' in str(ex).lower() or 'over a part' in str(ex).lower()
check('an outline off the part: says so, changes nothing', ok)
summary()
