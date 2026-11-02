"""0.24.95 Mirrored parts (user: "이거 왜 컷이든 불린이든 아무것도 안 되냐?" - an FBX part with scale (-1, -0.99, -0.03)):

* a part whose transform mirrors it (an odd number of negative scales) is inside out to the Boolean: the Manifold
  solver added the shape instead of taking it away, Exact gave nothing.  ``unmirror`` makes the same part un-mirrored:
  every point and every (custom) normal where it was in the world, the transform's scale positive, its children where
  they were; refused (a clear message) for a mesh shared with other objects or a modifier that depends on the part's axes
* Cut (``check_target``) and the Mecha Boolean tool un-mirror the part first: the cut takes the shape away
* a Boolean that would leave nothing of the part (Exact on a part with overlapping shells inside it - the user's part)
  is tried with the other solver, else refused - the part is never emptied; the Boolean tool uses Manifold for closed
  meshes (as the Cut tools)"""
import math

import numpy as np
from _harness import bmesh, bpy, check, fresh, summary
from mathutils import Euler, Vector  # noqa: E402  (after bpy)

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_settings.auto_apply = True
S.mch_cut.targets = 'SELECTED'


def part(name, scale=(-1.0, -0.8, -0.4), rot=(0.3, 0.0, 0.5), loc=(0.0, 0.0, 0.0)):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.15, segments=2, affect='EDGES')
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    S.collection.objects.link(ob)
    ob.location, ob.rotation_euler, ob.scale = loc, rot, scale
    me.polygons.foreach_set('use_smooth', [True] * len(me.polygons))
    C.view_layer.update()
    return ob


def world(ob):
    M = ob.matrix_world
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(M)
    vol = bm.calc_volume(signed=True)
    co = np.array([tuple(v.co) for v in bm.verts])
    bm.free()
    return co, vol


def corner_normals(ob):
    """{(face, world point rounded): world corner normal}"""
    me = ob.data
    M = ob.matrix_world
    N = M.to_3x3().inverted_safe().transposed()
    out = {}
    for p in me.polygons:
        for li in p.loop_indices:
            co = tuple(round(c, 5) for c in M @ me.vertices[me.loops[li].vertex_index].co)
            out[(p.index, co)] = (N @ me.corner_normals[li].vector).normalized()
    return out


def select_only(*obs):
    for x in C.selected_objects:
        x.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[-1]


# unmirror itself
a = part('Mirrored')
nrm = [tuple(Vector((c[0], c[1] * 0.6, c[2])).normalized()) for c in
       (a.data.vertices[lp.vertex_index].co for lp in a.data.loops)]          # (custom normals of its own)
a.data.normals_split_custom_set(nrm)
child = bpy.data.objects.new('Child', None)
S.collection.objects.link(child)
child.parent = a
child.location = (0.5, 0.2, 0.3)
C.view_layer.update()
co0, v0 = world(a)
n0 = corner_normals(a)
child0 = child.matrix_world.copy()
check('A part with scale (-1, -0.8, -0.4) is mirrored: inside out in the world (signed volume below 0)',
      cg.mirrored(a) and v0 < 0, round(v0, 3))
done = cg.unmirror(a)
C.view_layer.update()
co1, v1 = world(a)
n1 = corner_normals(a)
worst = max(1.0 - n0[k].dot(n1[k]) for k in n0 if k in n1)
check('unmirror: the same part - every point where it was, the volume the right way out, the scale positive',
      done and not cg.mirrored(a) and np.abs(np.sort(co0, 0) - np.sort(co1, 0)).max() < 1e-5
      and abs(v1 + v0) < 1e-5 and v1 > 0 and all(s > 0 for s in a.scale), (round(v1, 3), tuple(a.scale)))
check('... its shading (custom normals) the same in the world, its child where it was',
      sum(k in n1 for k in n0) > 0.95 * len(n0) and worst < 1e-4
      and (child.matrix_world.translation - child0.translation).length < 1e-5,
      (round(worst, 6), sum(k in n1 for k in n0), len(n0), tuple(child0.translation), tuple(child.matrix_world.translation)))
check('... a part that is not mirrored: left alone', cg.unmirror(a) is False)

b = part('MirroredArray')
b.modifiers.new('Array', 'ARRAY')
try:
    cg.unmirror(b)
    refused = ''
except cg.CutError as ex:
    refused = str(ex)
check('... refused with a modifier that depends on its axes (Array): "Apply its scale first"',
      'Apply its scale' in refused and 'Array' in refused and cg.mirrored(b), refused[:90])
bpy.data.objects.remove(b)
c = part('MirroredShared')
c2 = bpy.data.objects.new('Twin', c.data)
S.collection.objects.link(c2)
try:
    cg.unmirror(c)
    refused = ''
except cg.CutError as ex:
    refused = str(ex)
check('... refused for a mesh shared with other objects (the twin would turn)', 'shared' in refused, refused[:90])
bpy.data.objects.remove(c2)
bpy.data.objects.remove(c)

# Cut on a mirrored part
d = part('CutMe', loc=(5.0, 0.0, 0.0))
select_only(d)
_co, vd0 = world(d)
pr = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=100.0)
cx, cy = pr.to_screen(d.matrix_world.translation)[:2]
S.mch_cut.depth_mode = 'THROUGH'
S.mch_cut.edge_finish = S.mch_cut.gn_finish = 'NONE'
msg = ce.perform_closed(C, 'CUT', [d], [ce.rect_loop((cx - 25, cy - 25), (cx + 25, cy + 25))], pr)
_co, vd1 = world(d)
check('Cut on a mirrored part: the shape taken away (the volume smaller, the right way out - it used to grow)',
      not cg.mirrored(d) and 0 < vd1 < abs(vd0) - 0.05, (round(vd0, 3), round(vd1, 3), msg[:60]))

# the Boolean tool on a mirrored part
e = part('BoolMe', loc=(10.0, 0.0, 0.0))
bpy.ops.mesh.primitive_cylinder_add(radius=0.3, depth=4.0, location=(10.0, 0.0, 0.0))
cyl = C.active_object
select_only(e, cyl)
_co, ve0 = world(e)
r = bpy.ops.mch.boolean(operation='DIFFERENCE')
_co, ve1 = world(e)
check('The Boolean tool on a mirrored part: the cutter taken away (it emptied or grew the part before)',
      r == {'FINISHED'} and not cg.mirrored(e) and 0 < ve1 < abs(ve0) - 0.05, (round(ve0, 3), round(ve1, 3)))
f = part('Plain', scale=(1, 1, 1), loc=(15.0, 0.0, 0.0))
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(15.0, 0.0, 1.0))
cb = C.active_object
from mecha_lab import boolean_modifier  # noqa: E402
mod = boolean_modifier(f, cb, 'DIFFERENCE')
check('... it uses the Manifold solver for closed meshes (as the Cut tools)', mod.solver == 'MANIFOLD', mod.solver)
f.modifiers.remove(mod)

# a Boolean that would leave nothing: refused, the part kept
far = bpy.data.objects.new('Far', bpy.data.meshes.new('Far'))
bm = bmesh.new()
bmesh.ops.create_cube(bm, size=0.5)
bm.to_mesh(far.data)
bm.free()
S.collection.objects.link(far)
far.location = (40.0, 0.0, 0.0)
C.view_layer.update()
nf = len(f.data.polygons)
m = f.modifiers.new('Keep', 'BOOLEAN')
m.operation, m.object = 'INTERSECT', far
try:
    cg.apply_single_modifier(C, f, m)
    said = ''
except cg.CutError as ex:
    said = str(ex)
check('A Boolean that would leave nothing of the part (both solvers): refused, the part as it was',
      'leave nothing' in said and len(f.data.polygons) == nf, (said[:80], len(f.data.polygons)))
summary()
