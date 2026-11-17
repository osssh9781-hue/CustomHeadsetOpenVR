"""0.24.195 GoZ (experimental; user: "GoZ 로 하면 안 되는 거야?" / "그렇게 하자").  No ZBrush here: the .GoZ files are
written and read back, ZBrush's side is played by rewriting the file and the list the way its GoZ button does."""
import os
import struct
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import goz_bridge as gz  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
st = C.scene.mch_goz
root = tempfile.mkdtemp(prefix='mch_goz_')
st.root = root
check('no GoZ folder: Send says so (nothing written)', gz.goz_root(st) == root and not gz.registered(root))
os.makedirs(os.path.join(root, 'GoZBrush'))

# the file
V = np.array(((0, 0, 0), (1, 0, 0), (1, 1, 0), (0, 1, 0), (0.5, 2, 0)), np.float32)
F = np.array(((0, 1, 2, 3), (3, 2, 4, gz.NO_CORNER)), np.uint32)
p = os.path.join(root, 'a.GoZ')
gz.write_goz(p, 'Thing', V, F, groups=[3, 7], colours=[(255, 0, 0), (0, 255, 0), (0, 0, 255), (9, 8, 7), (1, 2, 3)])
raw = open(p, 'rb').read()
check('the file: the 32-byte heading, then the object block (tag 1, length = name + 24, count 1, "GoZMesh_Thing")',
      raw[:32] == b'GoZb 1.0 ZBrush GoZ Binary......' and struct.unpack_from('<IIQ', raw, 32) == (1, 5 + 24, 1)
      and raw[48:61] == b'GoZMesh_Thing' and raw[-16:] == b'\0' * 16)
at = 32 + 29 + 20
check('... the points block (tag 0x2711, length = n * 12 + 16, count n), the faces block (0x4E21, n * 16 + 16)',
      struct.unpack_from('<IIQ', raw, at) == (0x2711, 5 * 12 + 16, 5)
      and struct.unpack_from('<IIQ', raw, at + 76) == (0x4E21, 2 * 16 + 16, 2))
d = gz.read_goz(p)
check('read back: the same name, points, faces (a triangle keeps its empty fourth corner), groups, colours',
      d['name'] == 'Thing' and np.allclose(d['verts'], V) and np.array_equal(d['faces'], F)
      and list(d['groups']) == [3, 7] and d['colours'][0].tolist() == [255, 0, 0] and d['colours'][3].tolist() == [9, 8, 7])
with open(p, 'wb') as f:                       # a block this reader does not know, in the middle
    f.write(raw[:at] + struct.pack('<IIQ', 0x1234, 16 + 5, 5) + b'abcde' + raw[at:])
d2 = gz.read_goz(p)
check('an unknown block is stepped over', np.allclose(d2['verts'], V) and np.array_equal(d2['faces'], F))

# Blender -> the files
bpy.ops.mesh.primitive_cube_add(size=2.0, location=(3, 0, 1))
cube = C.active_object
cube.name = 'My Cube é'
bpy.ops.object.mode_set(mode='EDIT')
bpy.ops.mesh.select_all(action='SELECT')
bpy.ops.mesh.poke()                               # (triangles)
bpy.ops.object.mode_set(mode='OBJECT')
n_before = len(cube.data.vertices)
r = bpy.ops.mch.goz_send()
rows = gz.listed(root)
check('Send (GoZ): one .GoZ in GoZProjects/Default (a plain-letter name), the list names it, a .ztn beside it',
      'FINISHED' in r and len(rows) == 1 and os.path.isfile(rows[0]) and os.path.isfile(rows[0][:-4] + '.ztn')
      and os.path.basename(rows[0]) == 'My_Cube__.GoZ' and rows[0].startswith(gz.project_dir(root)), rows)
d = gz.read_goz(rows[0])
w = np.array([cube.matrix_world @ v.co for v in cube.data.vertices])
check('... the points in world space turned to ZBrush\'s axes (x, -z, y), every face three corners',
      len(d['verts']) == n_before and np.allclose(d['verts'], np.c_[w[:, 0], -w[:, 2], w[:, 1]], atol=1e-5)
      and bool(np.all(d['faces'][:, 3] == gz.NO_CORNER)))

# ZBrush's side: the mesh changed (twice as big, one polygroup per face) and listed again
gz.write_goz(rows[0], d['name'], d['verts'] * 2.0, d['faces'], groups=np.arange(len(d['faces'])) + 1)
with open(gz.list_path(root), 'w') as f:
    f.write(rows[0][:-4] + '\n')
old = cube.data.name
r = bpy.ops.mch.goz_import()
co = np.array([cube.matrix_world @ v.co for v in cube.data.vertices])
check('Import (GoZ): the same object gets the new mesh (twice as big in the world), its place kept, the old mesh '
      'kept as _preZBrush, the polygroups as a face attribute',
      'FINISHED' in r and np.allclose(np.sort(co, 0), np.sort(w * 2.0, 0), atol=1e-4) and tuple(cube.location) == (3, 0, 1)
      and bpy.data.meshes.get(old + '_preZBrush') is not None and cube.data.attributes.get(gz.GROUP_ATTR) is not None
      and len({d_.value for d_ in cube.data.attributes[gz.GROUP_ATTR].data}) == len(cube.data.polygons))
me = cube.data
me.calc_loop_triangles()
mid = co.mean(0)                                  # (the doubled cube's own middle)
out = sum(1 for pl in me.polygons if np.dot(np.array(cube.matrix_world.to_3x3() @ pl.normal),
                                             np.array(cube.matrix_world @ pl.center) - mid) > 0)
check('... and the faces still face outward (the axis change is a turn, not a mirror)', out == len(me.polygons), out)
gz.write_goz(os.path.join(gz.project_dir(root), 'FromZB.GoZ'), 'FromZB', V, F)
with open(gz.list_path(root), 'w') as f:
    f.write(os.path.join(gz.project_dir(root), 'FromZB') + '\n')
r = bpy.ops.mch.goz_import()
new = bpy.data.objects.get('FromZB')
check('a tool that did not come from here: a new object (a quad and a triangle)', new is not None
      and [len(pl.vertices) for pl in new.data.polygons] == [4, 3])
r = bpy.ops.mch.goz_setup()
info = os.path.join(root, 'GoZApps', 'Blender', 'GoZ_Info.txt')
cfg = os.path.join(root, 'GoZApps', 'Blender', 'GoZ_Config.txt')
check('Set Up GoZ for Blender: GoZ_Info.txt and GoZ_Config.txt (this Blender\'s path) in GoZApps/Blender, nothing '
      'else', 'FINISHED' in r and 'NAME' in open(info).read() and bpy.app.binary_path.replace('\\', '/') in open(cfg).read()
      and sorted(os.listdir(os.path.join(root, 'GoZApps'))) == ['Blender'] and gz.registered(root))
note = gz.call_zbrush(root)
txt = os.path.join(gz.project_dir(root), 'MechaLab_GoZ_Import.txt')
body = open(txt).read()
check('0.24.196 Send asks ZBrush with an import script (not GoZBrushFromApp): the script written beside the files, '
      'the list path in it with forward slashes, Tool:Import in it; no ZBrush here: the note says how to load it by '
      'hand', os.path.isfile(txt) and gz.list_path(root).replace('\\', '/') in body and '[IPress,Tool:Import]' in body
      and body.count('[') == body.count(']') and 'ZScript > Load' in note and 'GoZBrushFromApp' not in body, note)
open(txt[:-4] + '.zsc', 'w').close()
gz.write_script(root)
kept = os.path.isfile(txt[:-4] + '.zsc')
with open(txt, 'a') as f:
    f.write('// changed')
gz.write_script(root)
check('... the compiled script is kept while the text is the same, thrown away when the text changes',
      kept and not os.path.isfile(txt[:-4] + '.zsc'))
summary()
