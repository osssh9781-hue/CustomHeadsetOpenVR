"""0.24.0 Screw Stamp: click on a surface -> a screw head aligned to the surface normal, parented to that mesh;
4 heads (Dome / Post / Socket / Cross) are closed solids; live size / height / hole depth; Alt + click removes;
Join puts the screws into the surface mesh."""
import math
import sys

_src = open(__file__.replace('test_v0240b.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import bmesh
from mathutils import Vector

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import screw_stamp as ss, tool_state as ts, bottom_bar as bb, ui_tool_settings as uts

check('tool + bottom bar button + sidebar drawer', 'SCREW' in ts.TOOL_BY_ID and 'SCREW' in {t[0] for t in bb.BAR_TOOLS}
      and 'SCREW' in uts.DRAWERS)


def closed(me):
    bm = bmesh.new()
    bm.from_mesh(me)
    ok = all(len(e.link_faces) == 2 for e in bm.edges) and len(bm.faces) > 0
    bm.free()
    return ok


for kind in ('DOME', 'POST', 'SOCKET', 'CROSS'):
    me = ss.head_mesh(kind, 0.05, 0.05 * ss.HEIGHTS[kind], 0.5)
    zs = [v.co.z for v in me.vertices]
    check(f'{kind}: closed solid, top at its height, sunk below the base', closed(me) and
          abs(max(zs) - 0.05 * ss.HEIGHTS[kind]) < 1e-6 and min(zs) < 0, (len(me.polygons), max(zs), min(zs)))
    if kind in {'SOCKET', 'CROSS'}:
        top = 0.05 * ss.HEIGHTS[kind]
        check(f'{kind}: has a hole / slot below the top', any(1e-4 < top - z < top * 0.9 for z in zs))

b = cube('B', 2.0)
S.mch_screw.kind = 'SOCKET'
S.mch_screw.radius = 0.1
from mecha_lab.screw_stamp import MCH_OT_screw_stamp


class FakeOp:
    remove = False

    def report(self, *a):
        print('report', a)


def stamp(origin, direction, remove=False):
    f = FakeOp()
    f.remove = remove
    return MCH_OT_screw_stamp.run(f, C, Vector(origin), Vector(direction))


r = stamp((0.3, 0.2, 5), (0, 0, -1))
s1 = C.active_object
check('click on the top: a screw on the surface, parented', r == {'FINISHED'} and ss.is_screw(s1) and s1.parent == b and
      (s1.matrix_world.translation - Vector((0.3, 0.2, 1.0))).length < 1e-4)
r = stamp((5, 0.1, 0.2), (-1, 0, 0))
s2 = C.active_object
up = (s2.matrix_world.to_3x3() @ Vector((0, 0, 1))).normalized()
check('click on the side: aligned to the side normal (+X)', ss.is_screw(s2) and (up - Vector((1, 0, 0))).length < 1e-4,
      tuple(up))
b.location.x = 3.0
C.view_layer.update()
check('screws follow the mesh', abs(s1.matrix_world.translation.x - 3.3) < 1e-4)
b.location.x = 0.0
C.view_layer.update()
h0 = s1.dimensions.z
s1.mch_screw.height = 2.0
C.view_layer.update()
check('live height', s1.dimensions.z > h0 * 1.5 and closed(s1.data))
s1.mch_screw.kind = 'CROSS'
check('live head change (usual height for the head)', abs(s1.mch_screw.height - ss.HEIGHTS['CROSS']) < 1e-6 and
      closed(s1.data))
check('last edit remembered for the next click', S.mch_screw.kind == 'CROSS')
r = stamp((0.3, 0.2, 5), (0, 0, -1), remove=True)
names = [o.name for o in bpy.data.objects]
check('Alt + click removes the screw under the mouse', r == {'FINISHED'} and s2.name in names and
      sum(1 for o in bpy.data.objects if ss.is_screw(o)) == 1)
n_screws = sum(1 for o in bpy.data.objects if ss.is_screw(o))
check('one screw left', n_screws == 1, n_screws)
f0 = len(b.data.polygons)
for o in bpy.data.objects:
    o.select_set(ss.is_screw(o))
bpy.ops.mch.screw_join()
check('Join: the screw becomes part of the mesh', len(b.data.polygons) > f0 and
      not any(ss.is_screw(o) for o in bpy.data.objects))
mecha_lab.unregister()
check('unregister removes the properties', not hasattr(bpy.types.Object, 'mch_screw'))
sys.exit(1 if summary() else 0)
