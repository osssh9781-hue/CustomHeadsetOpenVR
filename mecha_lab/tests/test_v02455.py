"""0.24.37 Export (OBJ / FBX) for the selected meshes, no ZBrush link needed; ZBrush-safe Faces: n-gons split into
clean triangles (quads kept) in the file and for the ZBrush bridge - the Blender mesh is not changed."""
import os
import tempfile

from _harness import bpy, check, fresh, summary
import bmesh

import mecha_lab
from mecha_lab import zbrush_bridge as zb

mecha_lab.register()
fresh()
C = bpy.context
check('the Export button is there', hasattr(bpy.ops.mch, 'export_mesh'))
# a block with a concave n-gon on top (an L shape) - ZBrush tears this kind of face into slivers
me = bpy.data.meshes.new('L')
bm = bmesh.new()
pts = [(0, 0), (2, 0), (2, 1), (1, 1), (1, 2), (0, 2)]
bot = [bm.verts.new((x, y, 0)) for x, y in pts]
top = [bm.verts.new((x, y, 1)) for x, y in pts]
bm.faces.new(bot[::-1])
bm.faces.new(top)
for i in range(6):
    j = (i + 1) % 6
    bm.faces.new((bot[i], bot[j], top[j], top[i]))
bm.to_mesh(me)
bm.free()
ob = bpy.data.objects.new('Block', me)
C.scene.collection.objects.link(ob)
for o in C.selected_objects:
    o.select_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
check('the test block has 2 n-gons (6 corners)', zb.ngon_count(me) == 2)
d = tempfile.mkdtemp()
path = os.path.join(d, 'block.obj')
r = bpy.ops.mch.export_mesh(filepath=path, file_format='OBJ')
text = open(path).read() if os.path.isfile(path) else ''
faces = [ln.split()[1:] for ln in text.splitlines() if ln.startswith('f ')]
check('OBJ written: no face with more than 4 corners, the 6 side quads kept', r == {'FINISHED'} and faces
      and max(len(f) for f in faces) <= 4 and sum(1 for f in faces if len(f) == 4) == 6, (r, [len(f) for f in faces]))
check('... named like the object (not Block.001)', 'o Block\n' in text, [ln for ln in text.splitlines() if ln.startswith('o ')])
check('the Blender mesh is unchanged, the name is back, no extra object left', zb.ngon_count(ob.data) == 2
      and ob.name == 'Block' and len(bpy.data.objects) == 1 and ob.select_get())
r = bpy.ops.mch.export_mesh(filepath=os.path.join(d, 'raw.obj'), file_format='OBJ', split_ngons=False)
raw = [ln for ln in open(os.path.join(d, 'raw.obj')).read().splitlines() if ln.startswith('f ')]
check('ZBrush-safe Faces off: the n-gons go as they are', max(len(f.split()) - 1 for f in raw) == 6)
try:
    r = bpy.ops.mch.export_mesh(filepath=os.path.join(d, 'block.fbx'), file_format='FBX')
    ok = r == {'FINISHED'} and os.path.getsize(os.path.join(d, 'block.fbx')) > 1000
except (RuntimeError, AttributeError) as ex:
    ok = False
check('FBX too', ok)
tmp = zb.export_copy(C, ob, True, True)
check('the ZBrush bridge sends the same clean faces (export copy)', zb.ngon_count(tmp.data) == 0)
bpy.data.objects.remove(tmp)
summary()
