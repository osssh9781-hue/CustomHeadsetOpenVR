"""0.24.76 The hard look on the ZBrush screen: Sculpt Mode ignores the edges marked Sharp (a Make Quad / Quad Remesh part
looked soft), so on the way into Sculpt Mode the smooth faces along Sharp edges are set flat, and back in Object Mode
exactly those faces are smooth again (the mesh as it was)."""
import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import zb_sculpt as zs, zb_shading as zsh

mecha_lab.register()
fresh()
C = bpy.context


def sharp_faces(ob):
    a = ob.data.attributes.get('sharp_face')
    out = np.zeros(len(ob.data.polygons), bool)
    if a is not None:
        a.data.foreach_get('value', out)
    return out


def part():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add()
    ob = C.active_object
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=2)           # 3 x 3 faces a side: the middle one touches no box edge
    bpy.ops.object.mode_set(mode='OBJECT')
    me = ob.data
    for p in me.polygons:
        p.use_smooth = True
    attr = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    for i, e in enumerate(me.edges):               # the box edges (both points on two outer planes) Sharp
        a, b = (me.vertices[v].co for v in e.vertices)
        attr.data[i].value = sum(abs(abs(a[k]) - 1) < 1e-6 and abs(abs(b[k]) - 1) < 1e-6 for k in range(3)) >= 2
    if me.attributes.get('sharp_face') is not None:
        me.attributes.remove(me.attributes['sharp_face'])
    return ob


zs.set_style('ZBRUSH')
ob = part()
check('A smooth part with its box edges Sharp: no flat faces at first', not sharp_faces(ob).any()
      and len(ob.data.polygons) == 54)
zs._mode(C, 'SCULPT')
sf = sharp_faces(ob)
check('Into Sculpt Mode on the ZBrush screen: the faces along the Sharp edges are flat (48), the middle ones smooth (6)',
      ob.mode == 'SCULPT' and sf.sum() == 48 and zsh.KEY in ob, (ob.mode, int(sf.sum())))
zs._mode(C, 'OBJECT')
check('Back in Object Mode: exactly as it was (no flat faces, no attribute left, nothing kept on the object)',
      ob.mode == 'OBJECT' and ob.data.attributes.get('sharp_face') is None and zsh.KEY not in ob)

ob = part()
attr = ob.data.attributes.new('sharp_face', 'BOOLEAN', 'FACE')
mid = next(i for i, p in enumerate(ob.data.polygons) if abs(p.center.z - 1) < 1e-6 and abs(p.center.x) < 0.1
           and abs(p.center.y) < 0.1)
attr.data[mid].value = True                        # a face the user set flat himself
r = bpy.ops.mch.zb_switch(target='ZBRUSH')
sf = sharp_faces(ob)
check('MECHA LAB -> ZBRUSH button: the same (the user\'s own flat face stays flat)', ob.mode == 'SCULPT'
      and sf.sum() == 49 and sf[mid], (r, int(sf.sum())))
bpy.ops.mch.zb_switch(target='MECHA')
sf = sharp_faces(ob)
check('ZBRUSH -> MECHA LAB: put back - only the user\'s own flat face', ob.mode == 'OBJECT' and sf.sum() == 1 and sf[mid],
      int(sf.sum()))

ob = part()
zs._mode(C, 'SCULPT')
bpy.ops.object.mode_set(mode='OBJECT')             # left another way (Blender's mode menu)
check('Left Sculpt Mode another way: still flat until the watcher comes by', sharp_faces(ob).sum() == 48 and zsh.KEY in ob)
check('... the watcher puts it back', zsh.tick() and not sharp_faces(ob).any() and zsh.KEY not in ob)

ob = part()
zs._mode(C, 'SCULPT')
bpy.ops.object.mode_set(mode='OBJECT')
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.subdivide(number_cuts=1)              # other faces now (like DynaMesh / Remesh)
bpy.ops.object.mode_set(mode='OBJECT')
check('Faces changed in between: nothing put back, no error, nothing left on the object', zsh.tick() is False
      and zsh.KEY not in ob)

ob = part()
bpy.ops.object.mode_set(mode='OBJECT')
zs.set_style('BLENDER')
zs._mode(C, 'SCULPT')
check('Blender style: Sculpt Mode as Blender has it (no change)', not sharp_faces(ob).any() and zsh.KEY not in ob)
zs._mode(C, 'OBJECT')
zs.set_style('ZBRUSH')

for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add()
ob = C.active_object
before = sharp_faces(ob).copy()
zs._mode(C, 'SCULPT')
check('No Sharp edges (a sculpt): untouched', (sharp_faces(ob) == before).all() and zsh.KEY not in ob)
zs._mode(C, 'OBJECT')

summary()
