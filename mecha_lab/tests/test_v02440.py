"""0.24.33 Perforate: honeycomb / circle / square / diamond holes through selected meshes - live Boolean cutter,
holes only where the surface is under them (margin), before a Mirror, Apply / Remove."""
import math
import time

from _harness import bpy, check, fresh, summary
import bmesh
from mathutils import Vector

import mecha_lab
from mecha_lab import perforate as pf, tool_state as ts, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
check('tool in the list with its settings', 'PERF' in {t[0] for t in ts.VISIBLE_TOOLS} and 'PERF' in uts.DRAWERS)
for pat, n in (('HEX', 6), ('SQUARE', 4), ('DIAMOND', 4), ('CIRCLE', 24)):
    sh = pf.hole_shape(pat, 1.0)
    area = sum(sh[i][0] * sh[(i + 1) % len(sh)][1] - sh[(i + 1) % len(sh)][0] * sh[i][1] for i in range(len(sh))) / 2
    check(f'{pat} hole: {n} corners, counter-clockwise', len(sh) == n and area > 0)
hexes = pf.hole_shape('HEX', 1.0)
check('honeycomb hole: 1 across the flats', abs(max(x for x, _y in hexes) - min(x for x, _y in hexes) - 1.0) < 1e-9)
c = pf.lattice('HEX', 1.0, 0.2, (-3, 3, -3, 3))
d = sorted({round(math.dist(a, b), 6) for a in c[:40] for b in c[:40] if a != b})[0]
check('honeycomb: neighbours one pitch apart (size + gap) in every direction', abs(d - 1.2) < 1e-6, d)
sq = pf.lattice('SQUARE', 1.0, 0.5, (0, 3, 0, 3))
check('square grid: straight rows', len({round(v, 6) for _u, v in sq}) * len({round(u, 6) for u, _v in sq}) == len(sq))
rot = pf.lattice('SQUARE', 1.0, 0.5, (-3, 3, -3, 3), rotation=math.radians(45))
check('rotation turns the grid', any(abs(u - round(u / 1.5) * 1.5) > 0.1 for u, _v in rot[:20]))
v, f = pf.prisms([(0, 0), (2, 0)], pf.hole_shape('HEX', 1.0), 0.0, Vector((1, 0, 0)), Vector((0, 1, 0)),
                 Vector((0, 0, 1)), -1, 1)
check('cutter: one closed prism per hole', len(v) == 24 and len(f) == 2 * (2 + 6))

bpy.ops.mesh.primitive_cube_add(size=1)
plate = C.active_object
plate.name = 'Plate'
plate.scale = (2.0, 1.0, 0.05)
bpy.ops.object.transform_apply(scale=True)
for o in C.selected_objects:
    o.select_set(False)
plate.select_set(True)
C.view_layer.objects.active = plate
d = C.scene.mch_perf_defaults
d.pattern, d.auto_size, d.size, d.gap, d.margin = 'HEX', False, 0.15, 0.04, 0.05
t = time.time()
res = bpy.ops.mch.perforate()
p = plate.mch_perf
check('perforate: live holes (Boolean + hidden cutter)', res == {'FINISHED'} and pf.is_perforated(plate)
      and plate.modifiers.get(pf.MOD_NAME) is not None and p.get('holes', 0) > 20, p.get('holes'))
check('Auto direction: drilled through the thin side (Z)', pf.plane_axes('AUTO', (2, 1, 0.05))[2] == Vector((0, 0, 1)))
dg = C.evaluated_depsgraph_get()
ev = plate.evaluated_get(dg)
me = ev.to_mesh()
bm = bmesh.new()
bm.from_mesh(me)
ev.to_mesh_clear()
holes_ok = len(bm.faces) > 100 and all(e.is_manifold for e in bm.edges)
bm.free()
check('the result really has holes, still a closed solid', holes_ok)
cu = p.cutter
co = [Vector(q.co) for q in cu.data.vertices]
check('margin: no hole within the margin of the edge', max(abs(q.x) for q in co) <= 1.0 - 0.05 + 1e-6
      and max(abs(q.y) for q in co) <= 0.5 - 0.05 + 1e-6, (max(abs(q.x) for q in co), max(abs(q.y) for q in co)))
n1 = p['holes']
p.size = 0.08
check('live: smaller holes = more of them at once', p['holes'] > n1, (n1, p['holes']))
for pat in ('CIRCLE', 'SQUARE', 'DIAMOND'):
    p.pattern = pat
    check(f'live: {pat} pattern', p['holes'] > 10 and len(cu.data.polygons) > 0)
p.rotation = math.radians(30)
check('live: rotation', p['holes'] > 10)
check('quick to change (one slider step)', time.time() - t < 10.0, round(time.time() - t, 2))

# an L-shaped part: holes only where there is surface
bpy.ops.mesh.primitive_plane_add(size=2)
L = C.active_object
L.name = 'Lshape'
bm = bmesh.new()
bm.from_mesh(L.data)
bmesh.ops.delete(bm, geom=[f for f in bm.faces], context='FACES')
for x0, y0 in ((0, 0), (1, 0), (0, 1)):
    vs = [bm.verts.new((x0 + a, y0 + b, 0)) for a, b in ((0, 0), (1, 0), (1, 1), (0, 1))]
    bm.faces.new(vs)
bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
bm.to_mesh(L.data)
bm.free()
for o in C.selected_objects:
    o.select_set(False)
L.select_set(True)
C.view_layer.objects.active = L
d.pattern, d.size, d.gap, d.margin, d.direction = 'SQUARE', 0.2, 0.05, 0.02, 'Z'
bpy.ops.mch.perforate()
cc = [Vector(q.co) for q in L.mch_perf.cutter.data.vertices]
check('irregular outline: no holes over the missing corner', not any(q.x > 1.0 and q.y > 1.0 for q in cc)
      and any(q.x > 1.0 for q in cc) and any(q.y > 1.0 for q in cc))

# a mirrored object: the Boolean goes before the Mirror
bpy.ops.mesh.primitive_cube_add(size=1, location=(10, 0, 0))
m = C.active_object
m.scale = (1, 1, 0.05)
bpy.ops.object.transform_apply(scale=True)
m.modifiers.new('MCH_Mirror', 'MIRROR')
for o in C.selected_objects:
    o.select_set(False)
m.select_set(True)
C.view_layer.objects.active = m
d.direction = 'AUTO'
bpy.ops.mch.perforate()
check('mirrored object: holes before the Mirror (symmetrical)', m.modifiers[0].name == pf.MOD_NAME)

# Apply / Remove
C.view_layer.objects.active = plate
nb = len(plate.data.polygons)
res = bpy.ops.mch.perforate_apply()
check('Apply: holes in the mesh, cutter gone', res == {'FINISHED'} and len(plate.data.polygons) > nb
      and not pf.is_perforated(plate) and plate.modifiers.get(pf.MOD_NAME) is None
      and 'Plate_Holes' not in bpy.data.objects)
C.view_layer.objects.active = L
nl = len(L.data.polygons)
res = bpy.ops.mch.perforate_remove()
check('Remove: the mesh as it was', res == {'FINISHED'} and len(L.data.polygons) == nl
      and L.modifiers.get(pf.MOD_NAME) is None and 'Lshape_Holes' not in bpy.data.objects)
summary()
