"""0.24.95 A picture behind the model (user: "hdri 배경 컬러 말고 내가 원하는 배경 이미지를 넣을 수 있게 해 줄래? 너가 기본으로
몇 장 넣어 줘 세로 가로 그 이후에는 내가 폴더로 불러올게", "배경은 스튜디오 이미지처럼 해 줘"):

* 48 studio backdrops come with the add-on, each wide (16 : 9) and tall (9 : 16); the user's folder (and the folders in
  it) after them
* a preview clicked: that picture behind the model - the HDRI background hidden, the HDRI world on; rendered (Cycles
  and EEVEE): Fill - the frame covered (a red | blue picture: red left, blue right); Fit - a tall picture whole in the
  middle, the Colour round it; the model as lit as with a plain colour (the HDRI lights it)
* Colour: the colour again; an HDRI world from before (no picture nodes): made anew
* the HDRI page, Background: Colour | Picture, Fill | Fit, previews 6 on a page (◀ Page n / m ▶), Choose Folder…
* (user: "사진에 컬러램프 기능 넣어 주라 - 대비랑 색 같은 거 내가 조절", "프리셋 한 열 장만 더") Brightness, Contrast and a
  Colour Ramp on the picture (rendered); 10 more studio backdrops"""
import math
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import backdrops as bd, mech_shader as ms, mech_shader_ui as mu, ui_bars, workspace_ui

fresh()
mecha_lab.register()
C = bpy.context
sc = C.scene

built = bd.builtin_files()
ents = bd.entries()
asp = [round(bd.aspect(bd.path(bd.BUILTIN + f)), 2) for f in built]
check('48 studio backdrops come with the add-on (8, then 10 more: "프리셋 한 열 장만 더", then 30 more: "30 개만 더"), each '
      'wide (16:9) and tall (9:16), named', len(built) == 96 and asp.count(1.78) == 48 and asp.count(0.56) == 48
      and ('B:white_sweep_land.jpg', 'Studio White') in ents and ('B:canvas_port.jpg', 'Canvas - Tall') in ents
      and ('B:gels_land.jpg', 'Colour Gels') in ents and ('B:canvas_brown_port.jpg', 'Brown Canvas - Tall') in ents
      and ('B:blinds_land.jpg', 'Window Blinds') in ents and ('B:kraft_port.jpg', 'Kraft Paper - Tall') in ents,
      (len(built), asp[:4]))

# the user's folder: a red | blue picture (2 : 1) in a folder inside, a tall one red over blue
mine = tempfile.mkdtemp(prefix='mch_bg_')
os.makedirs(os.path.join(mine, 'Sub'))


def picture(path, w, h, fill):
    img = bpy.data.images.new('p', w, h, alpha=False)
    px = np.zeros((h, w, 4), np.float32)
    px[..., 3] = 1.0
    fill(px)
    img.pixels.foreach_set(px.ravel())
    img.filepath_raw = path
    img.file_format = 'PNG'
    img.save()
    bpy.data.images.remove(img)


def red_blue(px):
    px[:, :px.shape[1] // 2, 0] = 1.0                    # (left red)
    px[:, px.shape[1] // 2:, 2] = 1.0                    # (right blue)


def red_over_blue(px):
    px[px.shape[0] // 2:, :, 0] = 1.0                    # (top red - Blender's rows: bottom first)
    px[:px.shape[0] // 2, :, 2] = 1.0


picture(os.path.join(mine, 'Sub', 'redblue.png'), 400, 200, red_blue)
picture(os.path.join(mine, 'tall.png'), 100, 200, red_over_blue)
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: mine if name == 'bg_folder' else real_pref(name, default)
bd.rescan()
ids = [e[0] for e in bd.entries()]
check('... your folder after them (the folders inside it too)', ids[-2:] == ['U:tall.png', 'U:Sub/redblue.png']
      and len(ids) == 98, ids[-3:])

# the scene: a grey ball, a camera, 16 : 9
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.6)
ball = C.active_object
bpy.ops.object.shade_smooth()
bpy.ops.mch.mech_shader_apply(preset='PLASTIC_MATTE')
st = ball.active_material.mch_mech
st.base_color = (0.5, 0.5, 0.5)
st.base_map = 'FLAT'
st.variation = st.h_base = 0.0
cd = bpy.data.cameras.new('Cam')
cam = bpy.data.objects.new('Cam', cd)
sc.collection.objects.link(cam)
cam.location, cam.rotation_euler = (0.0, -4.0, 0.0), (math.radians(90), 0.0, 0.0)
sc.camera = cam
sc.render.resolution_x, sc.render.resolution_y = 160, 90
sc.render.engine = 'CYCLES'
sc.cycles.samples = 8
sc.cycles.use_denoising = False
sc.view_settings.view_transform = 'Standard'
sc.mch_mech_hdri_bg_color = (0.0, 0.6, 0.0)


def render():
    p = os.path.join(tempfile.mkdtemp(), 'r.png')
    sc.render.filepath = p
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(p)
    a = np.array(img.pixels[:]).reshape(90, 160, 4)[..., :3]
    bpy.data.images.remove(img)
    return a


def is_red(c):
    return c[0] > 0.6 and c[2] < 0.25


def is_blue(c):
    return c[2] > 0.6 and c[0] < 0.25


def is_green(c):
    return c[1] > 0.4 and c[0] < 0.2 and c[2] < 0.2


r = bpy.ops.mch.mech_bg_image(ident='U:Sub/redblue.png')
w = ms.hdri_world(sc)
nt = w.node_tree if w else None
check('A preview clicked: that picture behind the model - Picture, the HDRI background hidden, the HDRI world on',
      r == {'FINISHED'} and sc.mch_mech_hdri_bg_mode == 'IMAGE' and not sc.mch_mech_hdri_show and w is not None
      and nt.nodes['mch:bgimg'].image is not None
      and nt.nodes['mch:bgimg'].image.filepath.endswith('redblue.png')
      and nt.nodes['mch:bgimg_on'].outputs[0].default_value == 1.0)
a = render()
L, R, mid = a[45, 4], a[45, 155], a[45, 80]
check('... rendered (Cycles), Fill: the frame covered by the picture - red at the left, blue at the right',
      is_red(L) and is_blue(R) and is_red(a[85, 4]) and is_blue(a[5, 155]),
      (np.round(L, 2).tolist(), np.round(R, 2).tolist()))
sc.mch_mech_hdri_bg_mode = 'COLOR'
a_col = render()
lit_col = float(a_col[45, 80].mean())
check('... Colour: the colour again behind the model', is_green(a_col[45, 4]) and is_green(a_col[45, 155]),
      np.round(a_col[45, 4], 2).tolist())
check('... the model lit by the HDRI either way (as bright with the picture as with the colour)',
      abs(float(mid.mean()) - lit_col) < 0.08 * max(lit_col, 0.05) + 0.02, (round(float(mid.mean()), 3), round(lit_col, 3)))
bpy.ops.mch.mech_bg_image(ident='U:tall.png')
sc.mch_mech_hdri_bg_fit = 'FIT'
a = render()
check('... Fit, a tall picture: whole in the middle (red over blue), the Colour round it',
      is_green(a[45, 4]) and is_green(a[45, 155]) and is_red(a[82, 74]) and is_blue(a[8, 74]),
      (np.round(a[82, 74], 2).tolist(), np.round(a[8, 74], 2).tolist(), np.round(a[45, 4], 2).tolist()))
# EEVEE (Material Preview's engine)
sc.mch_mech_hdri_bg_fit = 'FILL'
bpy.ops.mch.mech_bg_image(ident='U:Sub/redblue.png')
engines = [e.identifier for e in bpy.types.RenderSettings.bl_rna.properties['engine'].enum_items]
sc.render.engine = 'BLENDER_EEVEE' if 'BLENDER_EEVEE' in engines else 'BLENDER_EEVEE_NEXT'
a = render()
check('... EEVEE too (Material Preview\'s engine): red at the left, blue at the right',
      is_red(a[45, 4]) and is_blue(a[45, 155]), (np.round(a[45, 4], 2).tolist(), np.round(a[45, 155], 2).tolist()))
sc.render.engine = 'CYCLES'
# (user: "사진에 컬러램프 기능 넣어 주라 - 대비랑 색 같은 거 내가 조절")
sc.mch_mech_hdri_bg_bright = 0.5
a = render()
check('Brightness +0.5: the picture lighter (the red side: green and blue come up too)',
      a[45, 4][0] > 0.9 and a[45, 4][1] > 0.4, np.round(a[45, 4], 2).tolist())
sc.mch_mech_hdri_bg_bright = 0.0
sc.mch_mech_hdri_bg_contrast = -1.0
a = render()
L, R = a[45, 4], a[45, 155]
check('Contrast -1: flat - both sides the same grey', np.allclose(L, R, atol=0.03) and abs(L[0] - L[2]) < 0.03,
      (np.round(L, 2).tolist(), np.round(R, 2).tolist()))
sc.mch_mech_hdri_bg_contrast = 0.0
sc.mch_mech_hdri_bg_ramp = True
rn = bd.ramp_node(sc)
rn.color_ramp.elements[0].color = (0.0, 0.0, 0.0, 1.0)              # (dark: black)
rn.color_ramp.elements[1].color = (1.0, 0.8, 0.0, 1.0)              # (light: yellow)
a = render()
L, R = a[45, 4], a[45, 155]
check('Colour Ramp on (dark black .. light yellow): the picture in the ramp\'s colours - no blue left, the red side '
      '(lighter) more yellow than the blue side', L[2] < 0.1 and R[2] < 0.1 and L[0] > R[0] > 0.05 and L[1] > R[1]
      and L[0] > 0.2, (np.round(L, 2).tolist(), np.round(R, 2).tolist()))
r = bpy.ops.mch.mech_bg_ramp('INVOKE_DEFAULT')
import inspect
check('... Edit Ramp…: Blender\'s own ramp editor in a popup (add stops, colours, positions)',
      r == {'FINISHED'} and 'template_color_ramp' in inspect.getsource(bd.MCH_OT_mech_bg_ramp.draw))
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
cells = {getattr(i, 'prop', ''): i for i in its}
labels = [i.label for i in its]
check('... the HDRI page: Brightness, Contrast, Colour Ramp, the Dark / Light swatches (the ramp\'s ends), Edit Ramp…',
      {'mch_mech_hdri_bg_bright', 'mch_mech_hdri_bg_contrast', 'mch_mech_hdri_bg_ramp'} <= set(cells)
      and 'Dark' in labels and 'Light' in labels and 'Edit Ramp…' in labels)
sc.mch_mech_hdri_bg_ramp = False
# an HDRI world from before
nt.nodes.remove(nt.nodes['mch:bgimg_pick'])
ms.hdri_sync(sc)
check('An HDRI world made before (no picture nodes): made anew, the picture in it',
      ms.hdri_world(sc).node_tree.nodes.get('mch:bgimg_pick') is not None
      and ms.hdri_world(sc).node_tree.nodes['mch:bgimg_on'].outputs[0].default_value == 1.0)

# the HDRI page
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
btns = {i.label: i for i in its if i.kind == 'tbtn'}
tiles = [i for i in its if i.kind == 'btile']
check('The HDRI page, Background: Colour | Picture, Fill | Fit, previews 6 on a page (98: 17 pages), Choose Folder',
      {'Colour', 'Picture', 'Fill', 'Fit', 'Choose Folder…'} <= set(btns) and btns['Picture'].on
      and len(tiles) == 2 and any(t.on for t in tiles) and any(i.label == 'Page 17 / 17' for i in its),
      (sorted(btns)[:12], len(tiles)))
check('... a tall picture\'s tile knows it is tall (fitted in, not stretched)',
      any(t.label == 'tall' and abs(t.data - 0.5) < 0.01 for t in tiles))
nxt = next(i for i in its if i.kind == 'tbtn' and i.action[:2] == ('op', 'mch.mech_bg_page') and
           i.action[2].get('step') == 1)
ui_bars.run(C, nxt)
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
first = [t.label for t in its if t.kind == 'btile']
check('... ▶ (last page): back to the first - the studio backdrops', first[:2] == ['Studio White', 'Studio White - Tall'],
      first)
ui_bars.run(C, next(i for i in its if i.kind == 'tbtn' and i.label == 'Colour'))
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
check('... Colour clicked: the colour swatch, no previews', sc.mch_mech_hdri_bg_mode == 'COLOR'
      and not [i for i in its if i.kind == 'btile'] and any(getattr(i, 'prop', '') == 'mch_mech_hdri_bg_color'
                                                            for i in its))
workspace_ui.pref = real_pref
summary()
