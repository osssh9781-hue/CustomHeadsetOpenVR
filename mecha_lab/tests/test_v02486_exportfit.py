"""0.24.77 Export Quad Mesh keeps every part's shape: one Quad Size for the whole export (1 % of everything) made small /
detailed parts a few dozen faces (13,114 -> 5 on the user's model: flat shards in ZBrush).  Now the quads are at most
a 20th of each part, and a result too far from the part (95 % of its surface within 0.5 % of its size) is made again
finer; a part that still does not fit goes out as it was (repaired)."""
import os
import tempfile

from _harness import bpy, check, fresh, summary
import bmesh
import numpy as np
from mathutils.bvhtree import BVHTree

import mecha_lab
from mecha_lab import zbrush_bridge as zbb

mecha_lab.register()
fresh()
C = bpy.context
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)

bpy.ops.mesh.primitive_cube_add(size=1, location=(0, 0, 0))
big = C.active_object
big.name = 'Big'
big.scale = (12, 6, 0.5)
bpy.ops.object.transform_apply(scale=True)
bpy.ops.mesh.primitive_cylinder_add(vertices=48, radius=0.3, depth=0.6, location=(8, 0, 0))
small = C.active_object
small.name = 'Small'
m = small.modifiers.new('b', 'BEVEL')
m.width, m.segments = 0.04, 3
bpy.ops.object.modifier_apply(modifier='b')


def world_bm(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.transform(ob.matrix_world)
    return bm


def lost95(orig, new):
    """95th percentile distance of orig's points to new's surface (world), as a share of orig's size."""
    a, b = world_bm(orig), world_bm(new)
    bvh = BVHTree.FromBMesh(b)
    co = np.array([v.co[:] for v in a.verts])
    d = [bvh.find_nearest(p)[3] for p in co]
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    a.free()
    b.free()
    return float(np.percentile(d, 95)) / size


faces0 = {o.name: len(o.data.polygons) for o in (big, small)}
src = {o.name: o for o in (big, small)}
for o in C.selected_objects:
    o.select_set(False)
big.select_set(True)
small.select_set(True)
C.view_layer.objects.active = big
path = os.path.join(tempfile.mkdtemp(), 'fit.fbx')
r = bpy.ops.mch.export_mesh(filepath=path, scope='SELECTED', file_format='FBX', quad_mesh=True, quad_size=1.0)
check('Export with Quad Mesh (Quad Size 1 % of the whole export): written', r == {'FINISHED'} and os.path.isfile(path), r)
keep = {n: (o.matrix_world.copy(), o.data.copy()) for n, o in src.items()}
before = set(bpy.data.objects)
bpy.ops.import_scene.fbx(filepath=path)
got = {o.name.split('.')[0]: o for o in bpy.data.objects if o not in before and o.type == 'MESH'}
check('Both parts in the file', set(got) == {'Big', 'Small'}, sorted(got))
ls = lost95(src['Small'], got['Small']) if 'Small' in got else 9
check('The small bevelled cylinder keeps its shape (95 % of its surface within 0.5 % of its size; one export-wide '
      'quad size made it a few faces)', ls <= 0.0051 and len(got['Small'].data.polygons) >= 200,
      (round(ls, 4), len(got['Small'].data.polygons), faces0['Small']))
lb = lost95(src['Big'], got['Big']) if 'Big' in got else 9
check('... and the big plate too', lb <= 0.0051, round(lb, 4))
check('The fit test: FIT 0.5 %, at least 20 quads across a part, up to 4 tries',
      zbb.FIT == 0.005 and zbb.PART_QUADS == 20 and zbb.TRIES == 4)
check('Not as quads when the shape cannot be kept: the part goes out as it was (repaired)',
      'kept as it was, repaired' in __import__('inspect').getsource(zbb.quad_copy))

summary()
