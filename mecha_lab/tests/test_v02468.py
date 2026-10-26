"""0.24.48 Quad Remesh (keep edges): a part that was cut / booleaned becomes all quads; the hard edges
the cut left (Edge Angle, marked Sharp / Crease) stay as quad lines; the original is kept hidden;
Re-make / Show Original / Apply; open meshes are refused with a clear message.
Two methods: Flow (QuadriFlow, warns when thin slivers lost their edges) and Patch (flat patches between the
hard edges get an even grid; the hard edges stay exactly)."""
import inspect
import math

from _harness import bpy, check, fresh, non_manifold, summary
import bmesh
from mathutils import Quaternion, Vector
from mathutils.bvhtree import BVHTree
from mathutils.geometry import intersect_point_line

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, quad_remesh as qr, ui_tool_settings as uts

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
check('Quad Remesh is in the Remesh panel', 'quad_remesh.draw' in inspect.getsource(uts.draw_remesh))


def hard_edges(me, deg=25):
    bm = bmesh.new()
    bm.from_mesh(me)
    out = [(e.verts[0].co.copy(), e.verts[1].co.copy()) for e in bm.edges
           if e.is_manifold and e.calc_face_angle(0) > math.radians(deg)]
    bm.free()
    return out


def samples(edges, step=0.02):
    pts = []
    for a, b in edges:
        k = max(2, int((a - b).length / step))
        pts += [a.lerp(b, i / k) for i in range(k + 1)]
    return pts


def edge_error(pts, edges):
    """For each point the distance to the nearest hard edge of the result; (median, 95%)."""
    ds = []
    for p in pts:
        best = 9.0
        for a, b in edges:
            _q, t = intersect_point_line(p, a, b)
            best = min(best, (a.lerp(b, min(1.0, max(0.0, t))) - p).length)
        ds.append(best)
    ds.sort()
    return ds[len(ds) // 2], ds[int(len(ds) * 0.95)]


bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
cube.name = 'Part'
S.mch_cut.depth_mode, S.mch_cut.depth = 'SURFACE', 0.3
ce.perform_closed(C, 'CUT', [cube], [[(430, 430), (430, 570), (570, 570), (570, 430)]], TOP, False)
bpy.ops.mesh.primitive_cylinder_add(radius=0.45, depth=3, location=(0.9, 0, -0.9), rotation=(math.pi / 2, 0, 0))
cyl = C.active_object
m = cube.modifiers.new('notch', 'BOOLEAN')
m.object, m.solver = cyl, 'EXACT'
cyl.hide_set(True)
C.view_layer.objects.active = cube
cube.select_set(True)
n_src = len(cube.data.polygons)
src_edges = hard_edges(cube.evaluated_get(C.evaluated_depsgraph_get()).to_mesh())
pts = samples(src_edges)
st = S.mch_quadremesh
st.faces = 3000
r = bpy.ops.mch.quad_remesh()
quad = C.active_object
polys = quad.data.polygons
check('Make Quad: a new all-quad copy near Faces, closed', r == {'FINISHED'} and quad != cube
      and qr.is_quad(quad) and all(len(p.vertices) == 4 for p in polys) and 2000 < len(polys) < 4000
      and non_manifold(quad) == 0, (r, len(polys)))
check('... the original is kept, hidden, untouched (its live boolean too)', cube.hide_get()
      and len(cube.data.polygons) == n_src and cube.modifiers.get('notch') is not None)
med, p95 = edge_error(pts, hard_edges(quad.data))
check('... the cut and boolean edges stay as hard quad lines (close to the old edges)',
      med < 0.005 and p95 < 0.02, (round(med, 4), round(p95, 4)))
bvh = BVHTree.FromObject(cube, C.evaluated_depsgraph_get())
far = max((bvh.find_nearest(v.co)[0] - v.co).length for v in quad.data.vertices)
check('... the shape stays the same (every new point on the old surface)', far < 0.02, round(far, 4))
check('... smooth shading with the kept edges sharp',
      all(p.use_smooth for p in polys) and any(not e.use_edge_sharp for e in quad.data.edges)
      and any(e.use_edge_sharp for e in quad.data.edges))
check('... no Mecha Lab cut attributes carried over', not any(a.name.startswith('mch_') for a in quad.data.attributes))

st.faces = 1200
bpy.ops.mch.quad_remesh()
check('Re-make: the same copy, rebuilt with the new Faces', C.active_object == quad
      and len(quad.data.polygons) < 1700 and cube.hide_get(), len(quad.data.polygons))
bpy.ops.mch.quad_show_source()
check('Show Original toggles the original', not cube.hide_get())
bpy.ops.mch.quad_show_source()
bpy.ops.mch.quad_apply()
check('Apply: an ordinary mesh now', not qr.is_quad(quad) and quad.name in bpy.data.objects)

# smaller Edge Angle keeps a soft 20 degree fold, the default 30 lets it go
fresh()
bpy.ops.mesh.primitive_cube_add(size=2.0)
fold = C.active_object
st = C.scene.mch_quadremesh                               # the old scene is gone after fresh()
bpy.ops.object.select_all(action='DESELECT')
fold.select_set(True)
C.view_layer.objects.active = fold
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.subdivide(number_cuts=1)
bpy.ops.object.mode_set(mode='OBJECT')
for v in fold.data.vertices:
    if v.co.z > 0 and v.co.x > 1e-4:
        v.co.z += 0.364 * v.co.x                          # the top bends up 20 degrees at x = 0
st.faces, st.edge_angle = 2000, math.radians(10)
bpy.ops.mch.quad_remesh()
q = C.active_object
fold_line = [(Vector((0, -1, 1)), Vector((0, 1, 1)))]
med10, _ = edge_error(samples(fold_line), hard_edges(q.data, 12))
check('Edge Angle 10: the soft fold stays a quad line', med10 < 0.01, round(med10, 4))
marked_pts = samples(fold_line)
st.edge_angle = math.radians(30)
bpy.ops.mch.quad_remesh()
src = bpy.data.objects[q[qr.SRC_KEY]]
probe = src.data.copy()
k30, _o = qr.prepare(probe, math.radians(30))
k10, _o = qr.prepare(probe, math.radians(10))
check('... Edge Angle 30 leaves the 20 degree fold soft, 10 marks it hard', k10 > k30, (k30, k10))
for e in src.data.edges:
    a, b = (src.data.vertices[i].co for i in e.vertices)
    if abs(a.x) < 1e-4 and abs(b.x) < 1e-4 and a.z > 0.9 and b.z > 0.9:
        e.use_edge_sharp = True
probe = src.data.copy()
check('Keep Marked Edges: edges marked Sharp count as hard even under Edge Angle',
      qr.prepare(probe.copy(), math.radians(30), True)[0] > qr.prepare(probe.copy(), math.radians(30), False)[0])
st.keep_marked = True
bpy.ops.mch.quad_remesh()
medm, _ = edge_error(marked_pts, hard_edges(q.data, 12))
check('... and stays a quad line', medm < 0.01,
      round(medm, 4))

# open mesh: refused, nothing changed
fresh()
bpy.ops.mesh.primitive_grid_add(size=2)
g = C.active_object
n_obj = len(bpy.data.objects)
r = bpy.ops.mch.quad_remesh()
check('Open mesh (a plane): refused with a message, nothing made', r == {'CANCELLED'}
      and len(bpy.data.objects) == n_obj and not g.hide_get() and not qr.is_quad(C.active_object))
check('... the message says why', "open / non-manifold" in inspect.getsource(qr.build_mesh))

# a cut that runs out through the side leaves thin slivers: Flow warns, Patch keeps every edge
fresh()
S = C.scene
st = S.mch_quadremesh
S.mch_settings.auto_apply = True
check('Method: Flow (default) and Patch, in the panel', st.method == 'FLOW'
      and {i.identifier for i in st.bl_rna.properties['method'].enum_items} == {'FLOW', 'PATCH'}
      and "'method'" in inspect.getsource(qr.draw))
bpy.ops.mesh.primitive_cube_add(size=2.0)
part = C.active_object
part.scale = (1.3, 1.0, 0.6)
bpy.ops.object.transform_apply(scale=True)
S.mch_cut.depth_mode, S.mch_cut.depth = 'SURFACE', 0.25
ce.perform_closed(C, 'CUT', [part], [[(400, 440), (400, 560), (520, 560), (520, 440)]], TOP, False)
ce.perform_closed(C, 'CUT', [part], [[(560, 520), (600, 560), (640, 520), (600, 480)]], TOP, False)
bpy.ops.mesh.primitive_cylinder_add(radius=0.35, depth=3, location=(1.3, 0, -0.6), rotation=(math.pi / 2, 0, 0))
cyl = C.active_object
m = part.modifiers.new('notch', 'BOOLEAN')
m.object, m.solver = cyl, 'EXACT'
with C.temp_override(object=part, active_object=part):
    bpy.ops.object.modifier_apply(modifier='notch')
bpy.data.objects.remove(cyl)
probe = part.data.copy()
qr.prepare(probe, math.radians(30))
src_edges = hard_edges(probe)
pts = samples(src_edges)
area = sum(p.area for p in part.data.polygons)


def run(method):
    st.method, st.faces = method, 3000
    part.hide_set(False)
    bpy.ops.object.select_all(action='DESELECT')
    part.select_set(True)
    C.view_layer.objects.active = part
    bpy.ops.mch.quad_remesh()
    return C.active_object


flow = run('FLOW')
h = math.sqrt(area / 3000)
check('Flow on thin slivers: the lost edge length is measured and warned about (panel line too)',
      flow.get(qr.MISS_KEY, 0) > qr.MISS_LIMIT and 'Some cut edges got lost' in inspect.getsource(qr.draw),
      round(flow.get(qr.MISS_KEY, 0), 2))
patch = run('PATCH')
polys = patch.data.polygons
check('Patch: all quads, near Faces, closed', all(len(p.vertices) == 4 for p in polys)
      and 2000 < len(polys) < 4500 and non_manifold(patch) == 0 and patch != flow, len(polys))
check('... every cut / boolean edge kept (nothing lost)', patch.get(qr.MISS_KEY, 1) == 0.0
      and qr._edge_miss(src_edges, patch.data, h, math.radians(18)) == 0.0)
med, p95 = edge_error(pts, hard_edges(patch.data))
check('... exactly on the old edges', p95 < 1e-4, (med, p95))
bvh = BVHTree.FromObject(part, C.evaluated_depsgraph_get())
far = max((bvh.find_nearest(v.co)[0] - v.co).length for v in patch.data.vertices)
check('... the shape is the same (flat patches stay flat)', far < 1e-3, far)
lens = sorted(e.calc_length() if hasattr(e, 'calc_length') else
              (patch.data.vertices[e.vertices[0]].co - patch.data.vertices[e.vertices[1]].co).length
              for e in patch.data.edges)
check('... even quads: most edges near the quad size', lens[len(lens) // 2] > 0.6 * h
      and lens[int(len(lens) * 0.9)] < 1.6 * h, (round(h, 3), round(lens[len(lens) // 2], 3)))
top = [p for p in polys if p.normal.z > 0.99 and p.center.z > 0.59]
square = sum(1 for p in top if max(abs(patch.data.vertices[a].co.x - patch.data.vertices[b].co.x)
                                   + abs(patch.data.vertices[a].co.y - patch.data.vertices[b].co.y)
                                   for a, b in zip(p.vertices, list(p.vertices[1:]) + [p.vertices[0]])) < 1.3 * h)
check('... the flat top is mostly a grid lined up with the part (quads near h, axis aligned)',
      square > 0.6 * len(top), (square, len(top)))

# curved part: Patch keeps going (the faces of curved areas are split into quads)
bpy.ops.mesh.primitive_uv_sphere_add(segments=24, ring_count=12, radius=1, location=(5, 0, 0))
sph = C.active_object
st.method, st.faces = 'PATCH', 2000
bpy.ops.mch.quad_remesh()
q = C.active_object
check('Patch on a curved part: still all quads and closed (no flat patches to grid)',
      q != sph and all(len(p.vertices) == 4 for p in q.data.polygons) and non_manifold(q) == 0,
      len(q.data.polygons))
summary()
