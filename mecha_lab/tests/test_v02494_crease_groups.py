"""0.24.94 Creases as polygroups on export: ZBrush reads no crease values from OBJ, so the faces between creased /
sharp edges are written as OBJ groups (polygroups) - CreasePG in ZBrush creases their borders."""
import os
import tempfile

import numpy as np
from _harness import bpy, bmesh, check, fresh, summary

import mecha_lab
from mecha_lab import zbrush_bridge as zb

mecha_lab.register()
fresh()
C = bpy.context

bpy.ops.mesh.primitive_cube_add(size=2.0)
cube = C.active_object
me = cube.data
ids, n, nb = zb.crease_regions(me)
check('A plain cube has one region and no creased edges', n == 1 and nb == 0 and np.all(ids == 0))
# crease the 4 edges round the top face (z = 1): the top face becomes its own region
att = me.attributes.new('crease_edge', 'FLOAT', 'EDGE')
vals = np.zeros(len(me.edges), np.float32)
for e in me.edges:
    a, b = me.vertices[e.vertices[0]].co, me.vertices[e.vertices[1]].co
    if a.z > 0.5 and b.z > 0.5:
        vals[e.index] = 1.0
att.data.foreach_set('value', vals)
ids, n, nb = zb.crease_regions(me)
top = next(p.index for p in me.polygons if p.normal.z > 0.5)
check('Four creased edges round the top: 2 regions, the top face alone in one of them', n == 2 and nb == 4
      and np.sum(ids == ids[top]) == 1, (n, nb, ids.tolist()))
# a sharp edge counts too: mark the 4 bottom edges sharp -> 3 regions
sh = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
sv = np.zeros(len(me.edges), bool)
for e in me.edges:
    a, b = me.vertices[e.vertices[0]].co, me.vertices[e.vertices[1]].co
    if a.z < -0.5 and b.z < -0.5:
        sv[e.index] = True
sh.data.foreach_set('value', sv)
ids, n, nb = zb.crease_regions(me)
check('Sharp edges are borders too: top, bottom and the four sides = 3 regions', n == 3 and nb == 8, (n, nb))
g = zb.crease_materials(cube)
check('crease_materials: a PG_ material per region, the faces assigned by region (top / sides / bottom)',
      g == 3 and [m.name for m in me.materials] == ['PG_001', 'PG_002', 'PG_003']
      and sorted(np.bincount([p.material_index for p in me.polygons]).tolist()) == [1, 1, 4], [m.name for m in me.materials])
me.materials.clear()                      # (the direct call above was on the cube itself; the exports work on a copy)
zb.drop_crease_materials()
d = tempfile.mkdtemp(prefix='mch_crease_')
for o in C.view_layer.objects:
    o.select_set(o is cube)
# FBX (the user exports FBX): the PG_ materials travel in the file = ZBrush "Import Mats as Polygroups"
path_f = os.path.join(d, 'export.fbx')
r = bpy.ops.mch.export_mesh(filepath=path_f, scope='SELECTED', file_format='FBX', crease_groups=True, apply_modifiers=False)
raw = open(path_f, 'rb').read()
check('mch.export_mesh FBX with Creases as Polygroups: the three PG_ materials are in the FBX file',
      'FINISHED' in r and all(f'PG_00{i}'.encode() in raw for i in (1, 2, 3)), (r, len(raw)))
check('... the temporary PG_ materials are gone afterwards and the cube itself has no materials (the copy had them)',
      not any(m.name.startswith('PG_') for m in bpy.data.materials) and len(cube.data.materials) == 0,
      ([m.name for m in bpy.data.materials], len(cube.data.materials)))
# OBJ: material groups (ZBrush reads usemtl / g as polygroups)
path2 = os.path.join(d, 'export.obj')
r = bpy.ops.mch.export_mesh(filepath=path2, scope='SELECTED', file_format='OBJ', crease_groups=True, apply_modifiers=False)
txt2 = open(path2, encoding='utf-8').read()
check('mch.export_mesh OBJ: usemtl PG_ per region and material groups (g) in the file',
      'FINISHED' in r and txt2.count('usemtl PG_') >= 3 and txt2.count('g ') >= 3, (txt2.count('usemtl PG_'), txt2.count('g ')))
r = bpy.ops.mch.export_mesh(filepath=os.path.join(d, 'export2.obj'), scope='SELECTED', file_format='OBJ', crease_groups=False, apply_modifiers=False)
txt3 = open(os.path.join(d, 'export2.obj'), encoding='utf-8').read()
check('... and no PG_ without it', 'PG_' not in txt3)
check('The setting is on by default in the ZBrush bridge settings and drawn in the Layers panel',
      C.scene.mch_zbrush.crease_groups and "'crease_groups'" in open(os.path.join(os.path.dirname(zb.__file__), 'layers_panel.py'), encoding='utf-8').read())
summary()
