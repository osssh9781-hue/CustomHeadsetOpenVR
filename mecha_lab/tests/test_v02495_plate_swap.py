"""0.24.95 (user: "아머 플레이트 할 때 왜 메카 리지랑 다른 거가 바뀌지가 않아?") Mech Ridge is a plate of its own kind
(a sloped roof, mech_ridge.py); the other Armor Plate profiles are Face Extract parts.  Picking Mech Ridge for a
plate just drawn, or another profile for a Mech Ridge plate, only set the NEXT plate - the plate on screen stayed.
Now the plate is drawn again from its own outline and view (``armor_plate.swap_profile``), and a Mech Ridge plate
gets the HUD's Apply / Remove / profile arrows too.  And (user: "알파 png 불러오는 창 어딨어?") the ZBrush Alpha /
Texture pickers get a File... button: one image file, not only a whole folder."""
import os

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import armor_plate as ap, core_geometry as cg, mech_ridge as mr, zb_sculpt as zs, zb_ui as zu
from mecha_lab.mecha_menu import Item

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion())
BOX = [[(380, 420), (620, 420), (620, 580), (380, 580)]]


def body():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
    return C.active_object


def plates():
    return [o for o in bpy.data.objects if o.type == 'MESH' and (ap.is_plate_or_part(o) or mr.source(o))]


tgt = body()
S.mch_plate.preset = 'CHAMFER'
ap.perform_plate(C, BOX, TOP)
first = C.active_object
check('A Chamfer plate drawn: live (outline kept for the HUD)', ap.live_any(C) == (first, 'PLATE'))
r = bpy.ops.mch.plate_preset(preset='MRIDGE')
ob = C.active_object
check('Mech Ridge picked for it: the plate on screen BECOMES a Mech Ridge plate (before: it stayed a Chamfer plate)',
      r == {'FINISHED'} and mr.live_plate(C) == ob and ap.live_any(C)[1] == 'MRIDGE' and len(plates()) == 1
      and non_manifold(ob) == 0, (r, [o.name for o in plates()]))
check('... on the part, from the same outline (its footprint matches the Chamfer plate\'s)',
      mr.source(ob)['target'] == tgt.name and mr.source(ob)['loops'] == [[list(map(float, q)) for q in lp]
                                                                          for lp in BOX])
r = bpy.ops.mch.plate_preset(preset='ROUND')
ob = C.active_object
check('... and back: Round picked for the Mech Ridge plate makes it a Round plate (before: nothing happened)',
      r == {'FINISHED'} and ap.live_any(C) == (ob, 'PLATE') and len(plates()) == 1
      and not any(mr.source(o) for o in bpy.data.objects), [o.name for o in plates()])
i = ap.PRESET_IDS.index('MRIDGE')
S.mch_plate.preset = ap.PRESET_IDS[i - 1]
bpy.ops.mch.plate_cycle(step=1)
check('The HUD arrows step onto Mech Ridge too (the plate turns into one)', ap.live_any(C)[1] == 'MRIDGE'
      and S.mch_plate.preset == 'MRIDGE')
check('... and the HUD stays on a Mech Ridge plate with Apply / Remove / the arrows (its sliders are in the panel)',
      ap.MRIDGE_HUD == ('apply', 'cancel', 'prev', 'next') and 'live_any(context)' in
      __import__('inspect').getsource(ap.MCH_GGT_plate_hud.poll))
bpy.ops.mch.plate_cycle(step=1)
check('... and off it again', ap.live_any(C)[1] == 'PLATE' and len(plates()) == 1)
bpy.ops.mch.plate_preset(preset='MRIDGE')
r = bpy.ops.mch.plate_cancel()
check('Remove on a Mech Ridge plate: gone, the part active again', r == {'FINISHED'} and not plates()
      and C.active_object == tgt)
ap.perform_plate(C, BOX, TOP, 'MRIDGE')
ob = C.active_object
r = bpy.ops.mch.plate_apply()
check('Apply on a Mech Ridge plate: a plain mesh (no longer live)', r == {'FINISHED'} and not ob.mch_mridge.live
      and mr.live_plate(C) is None)

# ---- the ZBrush Alpha / Texture pickers: File... loads one image
real_on = zs.on
zs.on = lambda c: True
bpy.ops.mesh.primitive_uv_sphere_add()
bpy.ops.object.mode_set(mode='SCULPT')
C.window_manager.mch_zb_pop = 'ALPHA'
items = zu.popup(C, 1200, 900, 1.0, Item)
labels = [it.label for it in items if it.kind == 'seg']
check('Alpha picker: a File... button next to Folder... (one image file)', 'File...' in labels and 'Folder...' in labels,
      labels)
C.window_manager.mch_zb_pop = 'TEXTURE'
labels = [it.label for it in zu.popup(C, 1200, 900, 1.0, Item) if it.kind == 'seg']
check('... and in the Texture picker', 'File...' in labels, labels)
C.window_manager.mch_zb_pop = ''
img = bpy.data.images.new('my_alpha', 64, 64)
path = os.path.join(bpy.app.tempdir or '/tmp', 'my_alpha_test.png')
img.filepath_raw = path
img.file_format = 'PNG'
img.save()
r = bpy.ops.mch.zb_image_file('EXEC_DEFAULT', filepath=path, kind='ALPHA')
check('File... -> the picked PNG becomes the brush alpha', r == {'FINISHED'}
      and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(path), zs.current_alpha(C))
r = bpy.ops.mch.zb_image_file('EXEC_DEFAULT', filepath=path + '.missing', kind='ALPHA')
check('... a missing file is refused with a message (the alpha stays)', r == {'CANCELLED'}
      and os.path.normcase(zs.current_alpha(C)) == os.path.normcase(path))
zs.set_alpha(C, '')
zs.on = real_on
summary()
