"""0.24.33 Cloth Wrap: live cloth round a cylinder or a box (fits round a selected mesh, or a new one with a core)."""
import math

from _harness import bpy, check, fresh, summary
import bmesh
from mathutils import Vector

import mecha_lab
from mecha_lab import cloth_wrap as cw, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
check('tool in the list with settings', 'CWRAP' in {t[0] for t in ts.VISIBLE_TOOLS} and 'CWRAP' in uts.DRAWERS)
sec = cw.section('CYLINDER', 16, 1.0, 1.0, 0.0)
check('circle section: on the circle, normals outward', all(abs(q.length - 1.0) < 1e-5 and q.dot(n) > 0.99 for q, n in sec))
sb = cw.section('BOX', 64, 1.0, 0.5, 0.1)
check('rounded box section: inside the box, reaches its sides', max(abs(q.x) for q, _n in sb) <= 1.0 + 1e-5
      and max(abs(q.y) for q, _n in sb) <= 0.5 + 1e-5 and max(q.x for q, _n in sb) > 0.999)
spacing = [(sb[(i + 1) % 64][0] - sb[i][0]).length for i in range(64)]
check('evenly spaced round it', max(spacing) / min(spacing) < 1.2, (min(spacing), max(spacing)))


def solid(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ok = len(bm.faces) > 0 and all(e.is_manifold for e in bm.edges)
    bm.free()
    return ok


for o in C.selected_objects:
    o.select_set(False)
res = bpy.ops.mch.cloth_wrap(kind='CYLINDER')
wr = C.active_object
p = wr.mch_wrap
check('nothing selected: a new live cylinder cloth with a core', res == {'FINISHED'} and cw.is_wrap(wr)
      and 'ClothWrap_Core' in bpy.data.objects and wr.parent is not None)
check('a closed cloth (thickness all round)', solid(wr.data))
co = [wr.matrix_world @ v.co for v in wr.data.vertices]
core = bpy.data.objects['ClothWrap_Core']
cen = core.matrix_world.translation
rr = [math.hypot(q.x - cen.x, q.y - cen.y) for q in co]
check('the cloth stands round the core (outside its radius, folds within reach)', min(rr) > 0.5 * 0.85
      and max(rr) < 0.5 * 2.0, (min(rr), max(rr)))
n1 = len(wr.data.vertices)
p.folds = 16
p.wrinkles = 6.0
p.hang = 0.5
check('live: folds / wrinkles / hang rebuild it', solid(wr.data) and len(wr.data.vertices) > n1)
zs = [(wr.matrix_world @ v.co).z for v in wr.data.vertices]
check('Hang: the cloth falls past the bottom of the core', min(zs) < cen.z - 1.0 - 0.4, min(zs))
p.cover_top = True
check('Cover Top: closed over the top', solid(wr.data) and max((wr.matrix_world @ v.co).z for v in wr.data.vertices)
      > cen.z + 1.0)

bpy.ops.mesh.primitive_cube_add(size=1.0, location=(5, 0, 0))
crate = C.active_object
crate.scale = (2.0, 1.0, 0.6)
crate.rotation_euler = (0, 0, math.radians(30))
C.view_layer.update()
res = bpy.ops.mch.cloth_wrap(kind='BOX')
bw = C.active_object
q = bw.mch_wrap
check('a mesh selected: the box cloth fits its size and turn', res == {'FINISHED'} and abs(q.size_x - 2.0) < 1e-4
      and abs(q.size_y - 1.0) < 1e-4 and abs(q.size_z - 0.6) < 1e-4
      and abs(bw.matrix_world.to_euler().z - math.radians(30)) < 1e-4 and q.cover_top)
check('box cloth: closed solid', solid(bw.data))
loc = [bw.matrix_world.inverted() @ (bw.matrix_world @ v.co) for v in bw.data.vertices]
check('it covers the box (reaches past its sides)', max(v.x for v in loc) > 1.0 and max(v.y for v in loc) > 0.5
      and max(v.z for v in loc) > 0.3)
q.kind = 'CYLINDER'
check('live: switch to a cylinder', solid(bw.data))
C.view_layer.objects.active = bw
bpy.ops.mch.cloth_wrap_apply()
check('Apply: plain mesh', not cw.is_wrap(bw))
summary()
