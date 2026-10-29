"""0.24.86 High Poly cut: on a dense part the boolean runs only on the faces round the shape (two small Exact
booleans on a patch: patch - cutter, cutter & patch) and is stitched back; checked against the whole-part boolean."""
import time

import numpy as np

from _harness import bpy, check, cube, fresh, non_manifold, summary

import mecha_lab
from mecha_lab import core_geometry as cg, region_cut as rc, tool_state as ts

_src = open(__file__.replace('test_v02510_hipoly.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])      # noqa: S102  (the stroke driver)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_cut.targets = 'AUTO'


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


def body(sub, loc=(0, 0, 0)):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1.0, location=loc)
    ob = C.active_object
    m = ob.modifiers.new('d', 'DISPLACE')
    t = bpy.data.textures.new('t', 'CLOUDS')
    t.noise_scale = 0.3
    m.texture = t
    m.strength = 0.2
    with C.temp_override(object=ob, active_object=ob):
        bpy.ops.object.modifier_apply(modifier='d')
    return ob


def box(size, loc, scale=(1, 1, 1)):
    bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    o = C.active_object
    o.scale = scale
    C.view_layer.update()
    return o


# --- region boolean against the whole-part boolean ------------------------------------------------------------------
ob = body(8)
me = ob.data
n0 = len(me.polygons)
a = me.attributes.new('grp', 'INT', 'FACE')
a.data.foreach_set('value', (np.arange(n0) % 5).astype(np.int32))
a = me.attributes.new('mask', 'FLOAT', 'POINT')
a.data.foreach_set('value', np.linspace(0, 1, len(me.vertices)).astype(np.float32))
me.polygons.foreach_set('material_index', (np.arange(n0) % 2).astype(np.int32))
me.materials.append(bpy.data.materials.new('A'))
me.materials.append(bpy.data.materials.new('B'))
cutter = box(0.3, (0, 0, 1.0), (1, 1, 0.6))
full = cg.evaluate_boolean(C, ob, cutter, 'DIFFERENCE', 'MANIFOLD')
log = []
t = time.perf_counter()
out = rc.region_boolean(C, ob, cutter, 'DIFFERENCE', log)
dt = time.perf_counter() - t
check('region_boolean DIFFERENCE on a 327k-face body: the faces of the whole-part Manifold boolean (within 2 %: the cut '
      'walls come as triangles, a seam point welded onto a point a millionth away drops a zero-size face), closed',
      out is not None and abs(len(out.polygons) - len(full.polygons)) <= 0.02 * len(full.polygons) + 4 and cg.non_manifold_edge_count(out) == 0, (log, len(out.polygons) if out else None, len(full.polygons), cg.non_manifold_edge_count(out) if out else None))
check('... the region was a small part of the body', log and 'region' in log[0] and int(log[0].split('region ')[1].split(' ')[0].replace(',', '')) < 0.1 * n0, log)
gr = np.empty(len(out.polygons), np.int32)
out.attributes['grp'].data.foreach_get('value', gr)
mk = np.empty(len(out.vertices), np.float32)
out.attributes['mask'].data.foreach_get('value', mk)
mi = np.empty(len(out.polygons), np.int32)
out.polygons.foreach_get('material_index', mi)
check('... face / point attributes, material indices and the material slots come along', set(gr.tolist()) == set(range(5))
      and (mk > 0).sum() > 0.9 * len(mk) and set(mi.tolist()) == {0, 1} and len(out.materials) == 2)
bpy.data.meshes.remove(full)
bpy.data.meshes.remove(out)
full = cg.evaluate_boolean(C, ob, cutter, 'INTERSECT', 'MANIFOLD')
out = rc.region_boolean(C, ob, cutter, 'INTERSECT', [])
check('region_boolean INTERSECT (a Split\'s piece): the faces of the whole-part boolean (within 2 %), closed',
      out is not None and abs(len(out.polygons) - len(full.polygons)) <= 0.02 * len(full.polygons) + 4 and cg.non_manifold_edge_count(out) == 0, (len(out.polygons) if out else None, len(full.polygons), cg.non_manifold_edge_count(out) if out else None))
bpy.data.meshes.remove(full)
bpy.data.meshes.remove(out)
far = box(0.3, (3, 3, 3))
check('a cutter that misses the body: None (the whole-part path reports it)', rc.region_boolean(C, ob, far, 'DIFFERENCE', []) is None)
small = cube('Small', 1.0, loc=(0, 5, 0))
near = box(0.4, (0, 5, 0.5))
check('a small part: None (the whole-part boolean is as fast)', rc.region_boolean(C, small, near, 'DIFFERENCE', []) is None)

# --- through a thin dense plate (front and back faces in the region) ------------------------------------------------
bpy.ops.mesh.primitive_plane_add(size=2.0, location=(0, -5, 0))
plate = C.active_object
m = plate.modifiers.new('s', 'SOLIDIFY')
m.thickness = 0.05
with C.temp_override(object=plate, active_object=plate):
    bpy.ops.object.modifier_apply(modifier='s')
m = plate.modifiers.new('sub', 'SUBSURF')
m.subdivision_type = 'SIMPLE'
m.levels = 8
with C.temp_override(object=plate, active_object=plate):
    bpy.ops.object.modifier_apply(modifier='sub')
nplate = len(plate.data.polygons)
through = box(0.3, (0.2, -5, 0), (1, 1, 2))
fullp = cg.evaluate_boolean(C, plate, through, 'DIFFERENCE', 'MANIFOLD')
outp = rc.region_boolean(C, plate, through, 'DIFFERENCE', log := [])
check('a cutter through a thin dense plate (front and back in one region): closed, the whole-part boolean\'s faces within 2 %',
      outp is not None and cg.non_manifold_edge_count(outp) == 0 and abs(len(outp.polygons) - len(fullp.polygons)) <= 0.02 * len(fullp.polygons), (nplate, log, len(outp.polygons) if outp else None, len(fullp.polygons)))

# --- through the tools: Cut and Split on the dense body report the region solver ------------------------------------
for o in (cutter, far, near, through, small, plate):              # (the helper boxes would be Auto targets)
    bpy.data.objects.remove(o)
select(ob)
check('the High Poly setting is on the Cut settings (Advanced), experimental: off by default', S.mch_cut.hipoly is False
      and "'hipoly'" in open(__import__('mecha_lab.ui_tool_settings', fromlist=['x']).__file__).read())
S.mch_cut.hipoly = True
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]
S.mch_settings.mch_active_tool = 'CUT'
S.mch_cut.shared_mesh = 'SINGLE'
t = time.perf_counter()
r, msg = lasso([(470, 470), (530, 470), (530, 530), (470, 530)])
dt = time.perf_counter() - t
check('Cut on the 327k-face body with High Poly on: done through the region path ("Region" in the report), closed',
      r == {'FINISHED'} and 'Region' in msg and non_manifold(ob) == 0, (r, msg[:80], round(dt, 2)))
MODE[0], NATIVE[0] = 'SPLIT', ts.TOOL_BY_ID['SPLIT'][5]
S.mch_settings.mch_active_tool = 'SPLIT'
before = {o.name for o in bpy.data.objects}
r, msg = lasso([(400, 400), (460, 400), (460, 460), (400, 460)])
piece = [o for o in bpy.data.objects if o.name not in before and o.type == 'MESH']
check('Split on it: both pieces closed, the piece through the region path', r == {'FINISHED'} and 'Region' in msg
      and non_manifold(ob) == 0 and len(piece) == 1 and non_manifold(piece[0]) == 0, (r, msg[:80], [o.name for o in piece]))
S.mch_cut.hipoly = False
MODE[0], NATIVE[0] = 'CUT', ts.TOOL_BY_ID['CUT'][5]
S.mch_settings.mch_active_tool = 'CUT'
r, msg = lasso([(560, 420), (610, 420), (610, 470), (560, 470)])
check('High Poly off: the whole-part solver (Manifold) as before', r == {'FINISHED'} and 'Region' not in msg and 'Manifold' in msg and non_manifold(ob) == 0, (r, msg[:80]))
S.mch_cut.hipoly = False
summary()
