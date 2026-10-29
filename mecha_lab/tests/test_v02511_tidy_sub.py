"""0.24.86 The result tidy of a dense part runs on the changed faces only (taken out with their attributes, tidied,
put back with the rim welded); the whole-mesh tidy stays for small parts and as the fallback."""
import time

import numpy as np

from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import core_geometry as cg, region_cut as rc, tool_state as ts

_src = open(__file__.replace('test_v02511_tidy_sub.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (the stroke driver)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_cut.targets = 'AUTO'
S.mch_cut.shared_mesh = 'SINGLE'


def body(sub):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1.0)
    ob = C.active_object
    m = ob.modifiers.new('d', 'DISPLACE')
    t = bpy.data.textures.new('t', 'CLOUDS')
    t.noise_scale = 0.3
    m.texture = t
    m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    me = ob.data
    n = len(me.polygons)
    a = me.attributes.new('grp', 'INT', 'FACE')
    a.data.foreach_set('value', (np.arange(n) % 5).astype(np.int32))
    a = me.attributes.new('mask', 'FLOAT', 'POINT')
    a.data.foreach_set('value', np.linspace(0, 1, len(me.vertices)).astype(np.float32))
    a = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    a.data.foreach_set('value', (np.arange(len(me.edges)) % 7 == 0))
    me.polygons.foreach_set('material_index', (np.arange(n) % 2).astype(np.int32))
    me.materials.append(bpy.data.materials.new('A'))
    me.materials.append(bpy.data.materials.new('B'))
    me.update()
    return ob


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


# --- extract / replace round trip -----------------------------------------------------------------------------------
ob = body(7)
me = ob.data
n = len(me.polygons)
co = np.empty(len(me.vertices) * 3)
me.vertices.foreach_get('co', co)
co = co.reshape(-1, 3)
fmask = np.zeros(n, bool)
cen = np.empty(n * 3)
me.polygons.foreach_get('center', cen)
fmask[cen.reshape(-1, 3)[:, 2] > 0.9] = True                 # a cap of faces round the top
sub, used = rc.extract_faces(me, fmask)
check('extract_faces: the masked faces as a mesh with the attributes along', len(sub.polygons) == int(fmask.sum())
      and sub.attributes.get('grp') is not None and sub.attributes.get('mask') is not None and sub.attributes.get('sharp_edge') is not None
      and len(sub.materials) == 2, (len(sub.polygons), int(fmask.sum())))
gr = np.empty(len(sub.polygons), np.int32)
sub.attributes['grp'].data.foreach_get('value', gr)
gr0 = np.empty(n, np.int32)
me.attributes['grp'].data.foreach_get('value', gr0)
check('... face values are the originals in order', np.array_equal(gr, gr0[fmask]))
mk = np.empty(len(sub.vertices), np.float32)
sub.attributes['mask'].data.foreach_get('value', mk)
mk0 = np.empty(len(me.vertices), np.float32)
me.attributes['mask'].data.foreach_get('value', mk0)
check('... point values follow the points', np.allclose(mk, mk0[used]))
se = np.empty(len(sub.edges), bool)
sub.attributes['sharp_edge'].data.foreach_get('value', se)
check('... edge values come along (by the edge\'s two points)', se.sum() > 0.1 * len(se))
n_edges0, nm0 = len(me.edges), non_manifold(ob)
vol0 = cg.mesh_size(me)
ok = rc.replace_faces(me, fmask, sub, vol0)
check('replace_faces with the sub-mesh unchanged: the part is back as it was - same faces, closed, same size',
      ok and len(me.polygons) == n and non_manifold(ob) == 0 and abs(cg.mesh_size(me) - vol0) < 1e-6, (ok, len(me.polygons), n, non_manifold(ob)))
gr1 = np.empty(n, np.int32)
me.attributes['grp'].data.foreach_get('value', gr1)
mi1 = np.empty(n, np.int32)
me.polygons.foreach_get('material_index', mi1)
check('... the face attributes and material indices of every face are the originals (untouched first, then the region)',
      sorted(gr1.tolist()) == sorted(gr0.tolist()) and sorted(mi1.tolist()) == sorted(((np.arange(n) % 2)).tolist()) and len(me.materials) == 2)
bpy.data.meshes.remove(sub)
# a rim point moved in the sub-mesh: refused, the part untouched
sub, used = rc.extract_faces(me, fmask)
rim = rc._boundary_verts(*(lambda a: (a[3][np.repeat(fmask, a[1])], a[1][fmask]))(rc.arrays(me)))
sub.vertices[0].co.x += 0.01                                    # (point 0 of the sub: on the rim or not, the test only
rimv = rc._boundary_verts(rc.arrays(sub)[3], rc.arrays(sub)[1])  #  needs a moved rim point)
sub.vertices[int(rimv[0])].co.z += 0.05
nv = len(me.vertices)
check('... a moved rim point: replace_faces refuses and leaves the part alone', not rc.replace_faces(me, fmask, sub, vol0) and len(me.vertices) == nv)
bpy.data.meshes.remove(sub)

# --- the tidy of a dense cut result goes through the sub-mesh path -------------------------------------------------
bpy.data.objects.remove(ob)
ob = body(8)                                                     # 327k faces
select(ob)
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]
S.mch_settings.mch_active_tool = 'CUT'
real_sub = rc.tidy_sub
calls = []


def spy(me_, fmask_, size_, shards_, slivers_):
    t = time.perf_counter()
    r = real_sub(me_, fmask_, size_, shards_, slivers_)
    calls.append((int(fmask_.sum()), len(me_.polygons), time.perf_counter() - t, r))
    return r


rc.tidy_sub = spy
for hip in (False, True):
    calls.clear()
    S.mch_cut.hipoly = hip
    t = time.perf_counter()
    r, msg = lasso([(470, 470), (530, 470), (530, 530), (470, 530)] if not hip else [(400, 400), (460, 400), (460, 460), (400, 460)])
    dt = time.perf_counter() - t
    check(f'Cut on the 327k-face body (High Poly {"on" if hip else "off"}): the tidy ran on the changed faces only '
          f'(a small part of the result), fast, the result closed',
          r == {'FINISHED'} and calls and all(c[0] < 0.2 * c[1] for c in calls) and all(c[2] < 0.6 for c in calls)
          and all(c[3] is not None for c in calls) and non_manifold(ob) == 0, (r, [(c[0], c[1], round(c[2], 2)) for c in calls], round(dt, 2)))
rc.tidy_sub = real_sub
mi = np.empty(len(ob.data.polygons), np.int32)
ob.data.polygons.foreach_get('material_index', mi)
check('... attributes and materials survived both cuts', ob.data.attributes.get('grp') is not None and ob.data.attributes.get('mask') is not None
      and set(mi.tolist()) == {0, 1} and len(ob.data.materials) >= 2,     # (the whole-part boolean adds the cutter's slot)
      (ob.data.attributes.get('grp') is not None, ob.data.attributes.get('mask') is not None, sorted(set(mi.tolist())), len(ob.data.materials),
       sorted(a.name for a in ob.data.attributes if not a.name.startswith('.'))))
S.mch_cut.hipoly = False
summary()
