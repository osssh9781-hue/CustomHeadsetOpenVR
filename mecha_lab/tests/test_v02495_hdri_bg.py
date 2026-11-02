"""0.24.95 HDRI page (user: "hdri 에서 배경 안 보이게 할 때 내가 원하는 배경 색깔 선택하게 해 줘", "내가 선택한 hdri 폴더가
폴더 안에 다 분류가 되어 있는데 일일이 클릭하기 귀찮아서 그 폴더 안에 있는 거 감지해서 들어가게 해 줘"):

* the HDRI background hidden: the camera sees a Background Colour of its own (rendered: the colour behind the model),
  the HDRI still lights the model (the model as bright as with the background shown); shown: the HDRI again; the
  HDRI page: the colour swatch only while it is hidden
* an HDRI world made before (no colour nodes): made anew the next time a setting changes
* the user's HDRI folder: the HDRIs in the folders inside it too (any depth; hidden folders left out), listed
  '* Folder / Name', Set HDRI loads that file; a file added to a folder inside: listed; the HDRI page: a heading per
  folder over its previews, the folder line counts the folders"""
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

# ---- the user's HDRI folder, sorted into folders
mine = tempfile.mkdtemp(prefix='mch_hdri_')
src = os.path.join(ms.hdri_dir(), 'sunset.exr')
for rel in ('top.exr', 'Outdoor/Sunny/beach.exr', 'Studio/softbox.exr', '.cache/skip.exr'):
    os.makedirs(os.path.dirname(os.path.join(mine, rel)), exist_ok=True)
    shutil.copy(src, os.path.join(mine, rel))
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: mine if name == 'hdri_folder' else real_pref(name, default)
try:
    files = ms.user_hdri_files()
    check('My HDRIs: the folders inside the HDRI folder too, any depth; hidden folders left out',
          files == ['top.exr', 'Outdoor/Sunny/beach.exr', 'Studio/softbox.exr'], files)
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
    check('... the HDRI page: a heading per folder over its previews, the folder line counts them',
          any(h.startswith('Outdoor / Sunny') for h in heads) and any(h.startswith('Studio  (2)') for h in heads)
          and any(h.startswith('Blender') for h in heads) and '2 folders inside' in notes, (heads, notes[:160]))
finally:
    workspace_ui.pref = real_pref
    shutil.rmtree(mine, ignore_errors=True)
bpy.ops.mch.mech_hdri(action='OFF')
summary()
