"""0.24.279 (user: "커브 어레이 말고도 그냥 직선이나 대각선 토글도 되고 내가 긋는 직선대로 어레이되는 툴 - 라쏘나 이런 거
다 있고 오토 셀렉트 액티브 다 있어야 돼"): Line Array - copies of a part from where it is along the drawn line:
Straight (Free / Straight / Diagonal snap), Follow, round a closed shape; Count / Spacing; Align; Targets Auto /
Selected / Active; live (the copies follow the part; Count lays it again); Make Real."""
import math

from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, line_array as la, tool_state as ts  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())             # (screen x = 500 + 100 * world x, y = 500 + 100 * world y)
px = lambda x, y: (500 + 100 * x, 500 + 100 * y)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def cube(name, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_cube_add(size=0.4, location=loc)
    ob = C.active_object
    ob.name = name
    return ob


def copies(ob):
    """World positions of the copies (the evaluated instances)."""
    dg = C.evaluated_depsgraph_get()
    return [inst.matrix_world.translation.copy() for inst in dg.object_instances
            if inst.is_instance and inst.parent is not None and inst.parent.original == ob]


check('the tool: Line Array in Symmetry & repeat, a shape tool, the Targets row, its icon, its window',
      'LARRAY' in ts.TOOL_BY_ID and 'LARRAY' in dict(ts.TOOL_GROUPS)['Symmetry & repeat'] and 'LARRAY' in ts.SHAPE_TOOLS
      and 'LARRAY' in __import__('mecha_lab.target_rules', fromlist=['x']).PICKING)

st = S.mch_larray
S.mch_cut.targets = 'AUTO'
clear(); a = cube('A')
for o in list(C.selected_objects):
    o.select_set(False)
st.path, st.snap, st.fill, st.count = 'STRAIGHT', 'FREE', 'COUNT', 4
msg = la.perform(C, [px(0, 0), px(1, 0.3), px(2, 0.5), px(3, 1.0)], 'STROKE', TOP)
arr = C.active_object
cs = sorted(copies(arr), key=lambda v: v.x)
check(f'Auto: the part under the start; Straight: from its centre to the drawing\'s end - 4 copies evenly ({msg})',
      la.is_array(arr) and arr.mch_larray.part == a and len(cs) == 4
      and all((c - Vector((3 * k / 4, 1.0 * k / 4, 0))).length < 1e-4 for k, c in zip(range(1, 5), cs)))
st.snap = 'STRAIGHT'
la.perform(C, [px(0, 0), px(3, 0.4)], 'LASSO', TOP)
cs = copies(C.active_object)
check('Snap Straight: across (0 deg)', len(cs) == 4 and all(abs(c.y) < 1e-4 for c in cs) and max(c.x for c in cs) > 2.9)
st.snap = 'DIAG'
la.perform(C, [px(0, 0), px(2.0, 1.7)], 'LASSO', TOP)
cs = copies(C.active_object)
check('Snap Diagonal: 45 deg', len(cs) == 4 and all(abs(c.x - c.y) < 1e-4 for c in cs))
st.snap = 'FREE'
# Follow, Align along an L-shaped path
st.path, st.align, st.count = 'FOLLOW', True, 4
la.perform(C, [px(0, 0), px(2, 0), px(2, 2)], 'STROKE', TOP)
arr = C.active_object
dg = C.evaluated_depsgraph_get()
insts = [(i.matrix_world.translation.copy(), i.matrix_world.to_euler().z) for i in dg.object_instances
         if i.is_instance and i.parent is not None and i.parent.original == arr]
last = max(insts, key=lambda t: t[0].y)
check(f'Follow + Align: along the drawn path, turned with it (the last copy at the end, turned 90 deg: {math.degrees(last[1]):.0f})',
      len(insts) == 4 and (last[0] - Vector((2, 2, 0))).length < 1e-4 and abs(abs(last[1]) - math.pi / 2) < 1e-3)
st.align = False
# a closed shape: round its outline
la.perform(C, [px(0, 0), px(2, 0), px(2, 2), px(0, 2)], 'RECT', TOP)
cs = copies(C.active_object)
check(f'a Rectangle: round its outline ({len(cs)} copies, none on the part itself)',
      len(cs) == 4 and all(c.length > 0.5 for c in cs))
# Spacing
st.path, st.fill, st.spacing = 'STRAIGHT', 'SPACING', 0.5
la.perform(C, [px(0, 0), px(2.6, 0)], 'LASSO', TOP)
cs = copies(C.active_object)
check(f'Spacing 0.5 over 2.6: 5 copies 0.5 apart ({sorted(round(c.x, 2) for c in cs)})',
      sorted(round(c.x, 3) for c in cs) == [0.5, 1.0, 1.5, 2.0, 2.5])
st.fill = 'COUNT'
# live: Count again, the part moved
arr = C.active_object
arr.mch_larray.fill, arr.mch_larray.count = 'COUNT', 8
check('live: Count 8 lays it again', len(copies(arr)) == 8)
a.location = (0, 1, 0); C.view_layer.update()
check('live: the part moved - the copies follow', all(abs(c.y - 1.0) < 1e-4 for c in copies(arr)))
a.location = (0, 0, 0); C.view_layer.update()
arr.mch_larray.path = 'FOLLOW'
check('live: Path Straight -> Follow re-laid from the drawing', len(copies(arr)) == 8)
# Targets: Selected / Active
clear(); a = cube('A'); b = cube('B', (0, -2, 0)); c_ = cube('C', (0, -4, 0))
for o in list(C.selected_objects):
    o.select_set(False)
a.select_set(True); b.select_set(True); C.view_layer.objects.active = b
S.mch_cut.targets = 'SELECTED'
st.path, st.count = 'STRAIGHT', 3
la.perform(C, [px(5, 5), px(7, 5)], 'LASSO', TOP)
arrs = [o for o in S.objects if la.is_array(o)]
check(f'Selected: every selected part its own array, from where it is ({sorted(o.name for o in arrs)})',
      sorted(o.mch_larray.part.name for o in arrs) == ['A', 'B']
      and all(abs(max(c.x for c in copies(o)) - 2.0) < 1e-4 for o in arrs))
for o in arrs:
    bpy.data.objects.remove(o)
for o in list(C.selected_objects):
    o.select_set(False)
a.select_set(True); C.view_layer.objects.active = c_
S.mch_cut.targets = 'ACTIVE'
la.perform(C, [px(5, 5), px(7, 5)], 'LASSO', TOP)
arrs = [o for o in S.objects if la.is_array(o)]
check('Active: only the active part', [o.mch_larray.part.name for o in arrs] == ['C'])
S.mch_cut.targets = 'AUTO'
arr = arrs[0]
for o in list(C.selected_objects):
    o.select_set(False)
arr.select_set(True); C.view_layer.objects.active = arr
r = bpy.ops.mch.line_array_real()
check(f'Make Real: a mesh of the copies (3 cubes = 24 points), no longer live',
      r == {'FINISHED'} and not la.is_array(arr) and len(arr.data.vertices) == 24 and not arr.modifiers)
summary()
