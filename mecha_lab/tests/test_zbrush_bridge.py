"""ZBrush bridge (OBJ round trip, not GoZ): send without join, import back changed files only,
transform/modifiers kept, renamed/deleted objects, missing file, shared mesh."""
import os
import sys
import tempfile
import time

from _harness import bpy, check, cube, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import zbrush_bridge as zb

C = bpy.context


def call(op, **kw):
    try:
        return op(**kw)
    except RuntimeError as ex:
        print('  (operator reported)', str(ex).splitlines()[0])
        return {'CANCELLED'}


def edit_obj(path, fn):
    """Simulate ZBrush: rewrite vertex lines and bump the file time."""
    out = []
    for line in open(path).read().splitlines():
        if line.startswith('v '):
            x, y, z = map(float, line.split()[1:4])
            x, y, z = fn(x, y, z)
            out.append(f'v {x:.6f} {y:.6f} {z:.6f}')
        else:
            out.append(line)
    open(path, 'w').write('\n'.join(out) + '\n')
    st = os.stat(path)
    os.utime(path, (st.st_atime, st.st_mtime + 5))


def local_extent(ob):
    xs = [v.co.x for v in ob.data.vertices]
    return max(xs) - min(xs)


mecha_lab.register()
fresh()
folder = tempfile.mkdtemp(prefix='mch_zb_')
C.scene.mch_zbrush.exchange_dir = folder
a = cube('PartA', loc=(3, 0, 0))
a.rotation_euler = (0.4, 0.1, 0.7)
a.scale = (1.0, 2.0, 1.0)
a.modifiers.new('Bevel', 'BEVEL')
b = cube('PartB', loc=(-3, 1, 0))
b_twin = b.copy()
b_twin.location = (-3, 5, 0)
C.scene.collection.objects.link(b_twin)
C.view_layer.update()
select_only(a, b)
r = call(bpy.ops.mch.zbrush_send)
files = sorted(f for f in os.listdir(folder) if f.endswith('.obj'))
check('send: one OBJ per selected object (no join)', r == {'FINISHED'} and len(files) == 2, files)
check('objects stay separate in Blender', 'PartA' in bpy.data.objects and 'PartB' in bpy.data.objects)
check('selection restored after send', set(C.selected_objects) == {a, b})
check('manifest written with ids', len(zb.read_manifest(zb.exchange_folder(C.scene.mch_zbrush))['objects']) == 2
      and a.get(zb.ID_KEY) and b.get(zb.ID_KEY))

# nothing changed -> nothing imported
r = call(bpy.ops.mch.zbrush_import)
check('import with no ZBrush changes leaves meshes alone', r == {'FINISHED'} and
      not any(m.name.endswith('_preZBrush') for m in bpy.data.meshes))

# Simulated ZBrush edit of A: scale along OBJ X by 1.5 around file origin
fa = os.path.join(folder, next(f for f in files if f.startswith('PartA')))
mw = a.matrix_world.copy()
ext0 = local_extent(a)
n_mod = len(a.modifiers)
time.sleep(0.01)
edit_obj(fa, lambda x, y, z: (x * 1.5, y, z))
r = call(bpy.ops.mch.zbrush_import)
check('import back replaces only the changed object', r == {'FINISHED'} and
      any(m.name.endswith('_preZBrush') for m in bpy.data.meshes) and len(b.data.vertices) == 8)
check('object transform kept', all(abs(x - y) < 1e-6 for r1, r2 in zip(a.matrix_world, mw) for x, y in zip(r1, r2)))
check('modifiers kept', len(a.modifiers) == n_mod)
check('geometry really changed', abs(local_extent(a) - ext0) > 0.1, (ext0, local_extent(a)))
check('previous mesh kept as backup (fake user)', bpy.data.meshes.get(a.data.name + '_preZBrush') is not None)

# Round trip without edits is exact (local coordinates restored)
fresh()
C.scene.mch_zbrush.exchange_dir = tempfile.mkdtemp(prefix='mch_zb2_')
c = cube('Exact', loc=(1, 2, 3))
c.rotation_euler = (0.3, 0.2, 0.1)
C.view_layer.update()
co0 = [v.co.copy() for v in c.data.vertices]
select_only(c)
call(bpy.ops.mch.zbrush_send)
C.scene.mch_zbrush.import_all = True
call(bpy.ops.mch.zbrush_import)
err = max(min((v.co - q).length for q in co0) for v in c.data.vertices)
check('unchanged round trip restores local coordinates (<1e-5)', err < 1e-5, err)
C.scene.mch_zbrush.import_all = False

# Renamed object found by id; deleted object re-created; missing file reported
d = cube('Renamed')
select_only(d)
call(bpy.ops.mch.zbrush_send)
folder2 = zb.exchange_folder(C.scene.mch_zbrush)
fd = next(folder2 / e['file'] for e in zb.read_manifest(folder2)['objects'].values() if e['object'] == 'Renamed')
d.name = 'RenamedLater'
edit_obj(str(fd), lambda x, y, z: (x, y * 2, z))     # OBJ Y = Blender Z (Up axis Y)
call(bpy.ops.mch.zbrush_import)
check('renamed object found by id and updated', bpy.data.objects.get('RenamedLater') is not None and
      max(v.co.z for v in bpy.data.objects['RenamedLater'].data.vertices) > 1.5)
bpy.data.objects.remove(bpy.data.objects['RenamedLater'], do_unlink=True)
edit_obj(str(fd), lambda x, y, z: (x, y, z))
call(bpy.ops.mch.zbrush_import)
check('deleted object re-created from its file', any(o.get(zb.ID_KEY) and o.name.startswith('Renamed')
                                                      for o in bpy.data.objects))
os.remove(str(fd))
r = call(bpy.ops.mch.zbrush_import)
check('missing file reported, no crash', r == {'FINISHED'})
rows = zb.manifest_rows(C.scene.mch_zbrush)
check('status lists the missing file', any(state == 'missing' for _n, _f, state in rows), rows)

# Shared mesh (Alt+D): only the sent object gets the new mesh
fresh()
C.scene.mch_zbrush.exchange_dir = tempfile.mkdtemp(prefix='mch_zb3_')
s1 = cube('Shared1')
s2 = s1.copy()
C.scene.collection.objects.link(s2)
select_only(s1)
call(bpy.ops.mch.zbrush_send)
f3 = zb.exchange_folder(C.scene.mch_zbrush)
fs = next(f3 / e['file'] for e in zb.read_manifest(f3)['objects'].values())
edit_obj(str(fs), lambda x, y, z: (x * 2, y, z))
call(bpy.ops.mch.zbrush_import)
check('shared mesh: twin keeps the original data', s1.data != s2.data and local_extent(s2) < local_extent(s1))
check('GoZ is detected only as information (None here)', zb.detect_goz() is None)

mecha_lab.unregister()
sys.exit(1 if summary() else 0)
