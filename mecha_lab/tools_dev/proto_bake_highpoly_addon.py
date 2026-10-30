"""The add-on's Bake High Poly on the user's part: in.fbx NAME fillet_pct out_dir -> blend with NAME + NAME_BakeHP."""
import bpy, sys, os, time
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/addon')
import mecha_lab
from mecha_lab import bake_highpoly as bk
FBX, NAME, FILLET, OUT = sys.argv[-4], sys.argv[-3], float(sys.argv[-2]), sys.argv[-1]
mecha_lab.register()
bpy.ops.import_scene.fbx(filepath=FBX)
for o in list(bpy.data.objects):
    if o.name != NAME:
        bpy.data.objects.remove(o, do_unlink=True)
src = bpy.data.objects[NAME]
bpy.context.view_layer.update()
for o in bpy.data.objects: o.select_set(o is src)
bpy.context.view_layer.objects.active = src
t0 = time.time()
hp, info = bk.build(bpy.context, src, target_faces=1_000_000, rounding=1.0, fillet=FILLET / 100.0)
print('RESULT', bk.describe(info), f'| total {time.time()-t0:.1f}s | flats {info["flats"]}')
src.hide_set(False)
bpy.ops.wm.save_as_mainfile(filepath=os.path.join(OUT, f'{NAME}_bakehp_addon.blend'))
print('SAVED')
