"""0.24.95 HDRI page (user: "hdri 에서 배경 안 보이게 할 때 내가 원하는 배경 색깔 선택하게 해 줘", "내가 선택한 hdri 폴더가
폴더 안에 다 분류가 되어 있는데 일일이 클릭하기 귀찮아서 그 폴더 안에 있는 거 감지해서 들어가게 해 줘"):

* the HDRI background hidden: the camera sees a Background Colour of its own (rendered: the colour behind the model),
  the HDRI still lights the model (the model as bright as with the background shown); shown: the HDRI again; the
  HDRI page: the colour swatch only while it is hidden
* an HDRI world made before (no colour nodes): made anew the next time a setting changes
* the user's HDRI folder: the HDRIs in the folders inside it too (any depth; hidden folders left out), listed
  '* Folder / Name', Set HDRI loads that file; a file added to a folder inside: listed; the HDRI page: a heading per
  folder over its previews, the folder line counts the folders
* (user: "이미지들까지 다 불러와져서 이상한 거 다 들어왔어 - 한 번에 지우는 버튼이랑 그냥 지우는 버튼") pictures that are
  not panoramas left out (All Pictures: in); Remove (the picked one, out of the list - the file kept), Bring Back,
  Remove All (the folder let go - every file kept)"""
import os
import shutil
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, workspace_ui

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene
PX = 64

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
ball = C.active_object
bpy.ops.mch.mech_shader_apply(preset='PAINTED')
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -6.0, 0.0), (1.5708, 0.0, 0.0)
sc.camera = cam
sc.render.engine = 'CYCLES'
sc.cycles.samples = 8
sc.cycles.use_denoising = False
sc.render.resolution_x = sc.render.resolution_y = PX
sc.view_settings.view_transform = 'Standard'          # (the colours as they are, no tone mapping)


def render():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(PX, PX, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


sc.mch_mech_hdri = 'courtyard.exr'
bpy.ops.mch.mech_hdri(action='SET')
w = sc.world
shown = render()
sc.mch_mech_hdri_bg_color = (0.8, 0.05, 0.05)
sc.mch_mech_hdri_show = False
hidden = render()
corner, mid = hidden[2, 2], hidden[PX // 2, PX // 2]
check('The HDRI background hidden: the camera sees the Background Colour (red) behind the model',
      corner[0] > corner[1] * 3 and corner[0] > corner[2] * 3 and w.cycles_visibility.camera,
      np.round(corner, 3).tolist())
check('... the HDRI still lights the model (the ball as bright as with the background shown)',
      abs(float(mid.mean()) - float(shown[PX // 2, PX // 2].mean())) < 0.05,
      (round(float(mid.mean()), 3), round(float(shown[PX // 2, PX // 2].mean()), 3)))
sc.mch_mech_hdri_show = True
again = render()
check('... shown again: the HDRI behind it (not red)', not (again[2, 2][0] > again[2, 2][1] * 3)
      and np.allclose(again[2, 2], shown[2, 2], atol=0.03))
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
props_on = {getattr(i, 'prop', '') for i in its}
sc.mch_mech_hdri_show = False
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
props_off = {getattr(i, 'prop', '') for i in its}
check('... the HDRI page: the Colour swatch only while the background is hidden',
      'mch_mech_hdri_bg_color' not in props_on and 'mch_mech_hdri_bg_color' in props_off)
# an HDRI world from before (no colour nodes)
nt = w.node_tree
for n in ('mch:bg_mix', 'mch:bg_color', 'mch:bg_hide'):
    nt.nodes.remove(nt.nodes[n])
nt.links.new(nt.nodes['mch:bg'].outputs['Background'], next(n for n in nt.nodes if n.type == 'OUTPUT_WORLD')
             .inputs['Surface'])
sc.mch_mech_hdri_strength = 1.2
check('An HDRI world made before (no colour nodes): made anew the next time a setting changes',
      w.node_tree.nodes.get('mch:bg_mix') is not None
      and w.node_tree.nodes['mch:bg_hide'].outputs[0].default_value == 1.0)
sc.mch_mech_hdri_show = True

# ---- the user's HDRI folder, sorted into folders (+ pictures that are not HDRIs, kept next to them)
import types
mine = tempfile.mkdtemp(prefix='mch_hdri_')
src = os.path.join(ms.hdri_dir(), 'sunset.exr')
for rel in ('top.exr', 'Outdoor/Sunny/beach.exr', 'Studio/softbox.exr', '.cache/skip.exr'):
    os.makedirs(os.path.dirname(os.path.join(mine, rel)), exist_ok=True)
    shutil.copy(src, os.path.join(mine, rel))


def picture(rel, w, h, fmt):
    img = bpy.data.images.new('pic', w, h)
    img.filepath_raw = os.path.join(mine, rel)
    img.file_format = fmt
    img.save()
    bpy.data.images.remove(img)


picture('Outdoor/Sunny/preview.jpg', 320, 200, 'JPEG')          # (a preview next to the HDRI: not one)
picture('Studio/thumb.png', 256, 256, 'PNG')
picture('Studio/pano.png', 1024, 512, 'PNG')                     # (a 2:1 panorama: an HDRI)
PR = types.SimpleNamespace(hdri_folder=mine, hdri_hidden='', hdri_all_images=False)
real_pref, real_prefs = workspace_ui.pref, workspace_ui.prefs
workspace_ui.pref = lambda name, default=True: getattr(PR, name) if hasattr(PR, name) else real_pref(name, default)
workspace_ui.prefs = lambda: PR
ms.rescan()
try:
    files = ms.user_hdri_files()
    check('My HDRIs: the folders inside the HDRI folder too, any depth; hidden folders left out; pictures that are '
          'not panoramas (a preview, a thumbnail) left out, a 2:1 panorama in',
          files == ['top.exr', 'Outdoor/Sunny/beach.exr', 'Studio/pano.png', 'Studio/softbox.exr'], files)
    PR.hdri_all_images = True
    ms.rescan()
    check('... All Pictures on: the other pictures listed too',
          {'Outdoor/Sunny/preview.jpg', 'Studio/thumb.png'} <= set(ms.user_hdri_files()))
    PR.hdri_all_images = False
    ms.rescan()
    items = {i[0]: i[1] for i in ms._hdri_items(None, C)}
    check('... listed "* Folder / Name" (first), the built-in ones after',
          items.get('U:Outdoor/Sunny/beach.exr') == '* Outdoor / Sunny / beach' and items.get('U:top.exr') == '* top'
          and list(items)[0] == 'U:top.exr' and 'courtyard.exr' in items, list(items.values())[:4])
    sc.mch_mech_hdri = 'U:Studio/softbox.exr'
    r = bpy.ops.mch.mech_hdri(action='SET')
    env = sc.world.node_tree.nodes['mch:env']
    check('... Set HDRI on one in a folder inside: that file', r == {'FINISHED'}
          and os.path.normcase(bpy.path.abspath(env.image.filepath))
          == os.path.normcase(os.path.join(mine, 'Studio', 'softbox.exr')))
    shutil.copy(src, os.path.join(mine, 'Studio', 'ring.exr'))
    ms._SCAN['time'] = 0.0                     # (as SCAN_EVERY seconds later)
    check('... a file added to a folder inside: listed', 'U:Studio/ring.exr' in [i[0] for i in ms._hdri_items(None, C)])
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    heads = [i.label for i in its if i.kind == 'pnote']
    notes = ' '.join(heads)
    btns = {i.label: i for i in its if i.kind == 'tbtn'}
    check('... the HDRI page: a heading per folder over its previews, the folder line counts them; Remove (the one '
          'picked) and Remove All', any(h.startswith('Outdoor / Sunny') for h in heads)
          and any(h.startswith('Studio  (3)') for h in heads) and any(h.startswith('Blender') for h in heads)
          and '2 folders inside' in notes and 'Remove softbox' in btns and 'Remove All' in btns, (heads, list(btns)))
    # Remove: the picked one out of the list, the next one picked, the file kept
    sc.mch_mech_hdri = 'U:Studio/softbox.exr'
    r = bpy.ops.mch.mech_hdri_remove(what='ONE')
    ids = [i[0] for i in ms._hdri_items(None, C)]
    check('Remove: the picked HDRI out of the list (its file kept), the list on the next one',
          r == {'FINISHED'} and 'U:Studio/softbox.exr' not in ids and sc.mch_mech_hdri in ids
          and sc.mch_mech_hdri != 'U:Studio/softbox.exr' and PR.hdri_hidden == 'Studio/softbox.exr'
          and os.path.isfile(os.path.join(mine, 'Studio', 'softbox.exr')), (sc.mch_mech_hdri, PR.hdri_hidden))
    sc.mch_mech_hdri = 'courtyard.exr'
    r = bpy.ops.mch.mech_hdri_remove(what='ONE')
    check('... a built-in HDRI: not removed (a warning)', r == {'CANCELLED'} and 'courtyard.exr' in
          [i[0] for i in ms._hdri_items(None, C)])
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
    check('... "Bring Back 1 Removed" on the page', any(i.label == 'Bring Back 1 Removed' for i in its))
    r = bpy.ops.mch.mech_hdri_remove(what='RESTORE')
    check('... Bring Back: it is in the list again', r == {'FINISHED'} and PR.hdri_hidden == ''
          and 'U:Studio/softbox.exr' in [i[0] for i in ms._hdri_items(None, C)])
    sc.mch_mech_hdri = 'U:top.exr'
    r = bpy.ops.mch.mech_hdri_remove(what='ALL')
    ids = [i[0] for i in ms._hdri_items(None, C)]
    check('Remove All: none of the folder\'s in the list (the folder let go), the built-in ones stay, every file kept',
          r == {'FINISHED'} and PR.hdri_folder == '' and not any(i.startswith(ms.USER) for i in ids)
          and 'courtyard.exr' in ids and sc.mch_mech_hdri in ids
          and os.path.isfile(os.path.join(mine, 'top.exr')) and os.path.isfile(os.path.join(mine, 'Studio', 'pano.png')))
finally:
    workspace_ui.pref, workspace_ui.prefs = real_pref, real_prefs
    shutil.rmtree(mine, ignore_errors=True)
    ms.rescan()
bpy.ops.mch.mech_hdri(action='OFF')
summary()
