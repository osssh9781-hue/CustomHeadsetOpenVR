"""0.24.138 (user: "백그라운드 이미지가 안 보여", "뒤에 넣는 스튜디오 이미지들 다 어디 갔어?") The studio backdrops come
back: the Render tab's Background can put a picture behind the model (the add-on's 136 backdrop pictures or the user's
folder) on ANY world - another add-on's HDRI still lights the parts; Fill / Fit; Material Preview Too (Material Preview
shows the scene's world)."""
import os
import tempfile

import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import backdrops as bd, bg_color as bgc, mech_shader_ui as msu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
st = S.mch_bg

# another add-on's HDRI: a red world
w = bpy.data.worlds.new('OtherAddonHDRI')
w.use_nodes = True
nt = w.node_tree
for n in list(nt.nodes):
    nt.nodes.remove(n)
red = nt.nodes.new('ShaderNodeBackground')
red.inputs['Color'].default_value = (1.0, 0.0, 0.0, 1.0)
red.inputs['Strength'].default_value = 1.5
out = nt.nodes.new('ShaderNodeOutputWorld')
nt.links.new(red.outputs['Background'], out.inputs['Surface'])
S.world = w

bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0)
bpy.ops.object.shade_smooth()
bpy.ops.object.camera_add(location=(0, -6, 0), rotation=(1.5708, 0, 0))
S.camera = C.active_object
S.render.engine = 'CYCLES'
S.cycles.samples = 8
S.cycles.device = 'CPU'
TMP = tempfile.mkdtemp(prefix='mch_bgpic_')


def render(wd, ht, name):
    S.render.resolution_x, S.render.resolution_y = wd, ht
    S.render.filepath = os.path.join(TMP, name)
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(S.render.filepath)
    px = np.empty(wd * ht * 4, np.float32)
    img.pixels.foreach_get(px)
    bpy.data.images.remove(img)
    return px.reshape(ht, wd, 4)[:, :, :3]


# the old HDRI page's picture carries over
S.mch_mech_hdri_bg_image = 'B:charcoal_land.jpg'
check('the picture the old HDRI page had is the one used (no picture set here yet)',
      st.image == '' and bgc.picture_ident(S) == 'B:charcoal_land.jpg')
S.mch_mech_hdri_bg_image = ''
check('... none at all: the white studio sweep', bgc.picture_ident(S) == bgc.DEFAULT_PICTURE)

# a click on a studio backdrop: on, as a picture
views = bgc._views()
v0 = views[0][2]
v0.shading.use_scene_world = False
r = bpy.ops.mch.bg_picture(ident='B:white_sweep_land.jpg')
pic = nt.nodes.get(bgc.N_PIC)
check('a click on a backdrop: the background on with that picture (window coordinates -> fitted -> the picture -> '
      'brightness / contrast), the world\'s own shader still in it',
      'FINISHED' in r and bgc.on(S) and st.mode == 'IMAGE' and pic is not None and pic.image is not None
      and pic.image.filepath.endswith('white_sweep_land.jpg') and nt.nodes.get(bgc.N_MIX).inputs[1].links[0].from_node == red,
      [n.name for n in nt.nodes])
check('Material Preview Too (on by default): the views\' Material Preview uses the scene\'s world',
      v0.shading.use_scene_world is True)
px = render(64, 64, 'fill.png')
corner, centre = px[2, 2], px[32, 32]
check('a Cycles render: behind the sphere the white studio sweep (light grey), the sphere lit by the red world',
      corner.min() > 0.35 and abs(corner[0] - corner[2]) < 0.1 and centre[0] > centre[2] + 0.1,
      (corner.round(2).tolist(), centre.round(2).tolist()))
# Fit vs Fill with a tall picture in a wide frame: Fit leaves the colour at the sides
st.color = (0.0, 1.0, 0.0)
bpy.ops.mch.bg_picture(ident='B:navy_port.jpg')
st.fit = 'FIT'
px = render(96, 48, 'fit.png')
side_fit, mid_fit = px[24, 2], px[47, 38]      # (the top row, inside the fitted picture, above the sphere)
st.fit = 'FILL'
px = render(96, 48, 'fill2.png')
side_fill = px[24, 2]
check('Fit: a tall picture in a wide frame - the colour (green) at the sides; Fill: the picture (navy) right to the '
      'edges (colours through the view transform)', side_fit[1] > side_fit[0] + 0.2 and side_fit[1] > side_fit[2] + 0.2
      and side_fill[1] < 0.2 and side_fill[2] > side_fill[0] and mid_fit[1] < 0.2 and mid_fit[2] > mid_fit[0], (side_fit.round(2).tolist(), side_fill.round(2).tolist(), mid_fit.round(2).tolist()))
st.bright, st.contrast = 0.3, -0.2
bc = nt.nodes.get(bgc.N_BC)
check('Brightness / Contrast reach the picture', abs(bc.inputs['Bright'].default_value - 0.3) < 1e-6
      and abs(bc.inputs['Contrast'].default_value + 0.2) < 1e-6)
st.bright = st.contrast = 0.0
# back to the colour: the picture chain out, its picture let go
img = nt.nodes.get(bgc.N_PIC).image
img_name = img.name
bpy.ops.mch.bg_picture(mode='COLOR')
check('Colour again: the picture nodes out, the picture this loaded let go (nothing uses it), still on with the colour',
      bgc.on(S) and all(nt.nodes.get(n) is None for n in bgc.PIC_NODES) and img_name not in bpy.data.images
      and tuple(nt.nodes[bgc.N_BG].inputs['Color'].default_value)[:3] == (0.0, 1.0, 0.0))
# the page: Colour | Picture, the backdrops 6 on a page, Fill / Fit, Choose Folder
st.mode = 'IMAGE'
items, _h = msu.hdri_content(C, 0, 300, 1.0)
tiles = [i for i in items if i.kind == 'btile']
labels = {getattr(i, 'label', '') for i in items}
n_pages = -(-len(bd.entries()) // bd.PAGE)
check(f'the Render tab, Background: Colour | Picture, Fill | Fit, Brightness, Contrast, 6 backdrops on a page '
      f'({len(bd.entries())} pictures, {n_pages} pages), Choose Folder…, Material Preview Too',
      {'Colour', 'Picture', 'Fill', 'Fit', 'Choose Folder…', 'Material Preview Too', 'Solid View Too'} <= labels
      and len(tiles) == 6 and all(t.action[:2] == ('op', 'mch.bg_picture') for t in tiles)
      and any(lb.startswith('Page ') for lb in labels), sorted(lb for lb in labels if lb)[:30])
ident = tiles[3].action[2]['ident']
bpy.ops.mch.bg_picture(ident=ident)
check('a tile\'s action puts its picture behind the model', st.image == ident
      and nt.nodes.get(bgc.N_PIC).image.filepath.endswith(ident[2:]), ident)
# off: the world as it was, the views' own setting back
msg = bgc.remove(S)
check('off: every node of ours gone (picture ones too), the world\'s own shader on its output, Material Preview\'s own '
      'setting back', not bgc.on(S) and all(nt.nodes.get(n) is None for n in bgc.NODES) and len(nt.nodes) == 2
      and out.inputs['Surface'].links[0].from_node == red and v0.shading.use_scene_world is False, msg)


class _Rec:
    def __init__(self, log):
        self.log = log

    def box(self):
        return self

    def row(self, **_kw):
        return self

    def column(self, **_kw):
        return self

    def label(self, text='', **_kw):
        self.log.append(('label', text))

    def prop(self, data, name, text=None, **_kw):
        self.log.append(('prop', name))

    def operator(self, idname, text='', **_kw):
        self.log.append(('op', idname, text))
        return type('OpProps', (), {})()


from mecha_lab import mech_shader as msh  # noqa: E402
rec = []
msh.draw_background(_Rec(rec), C)
check('the N sidebar\'s Background box: Colour / Picture, Fill / Fit, Brightness, Contrast, Material Preview Too',
      all(('prop', p) in rec for p in ('mode', 'fit', 'bright', 'contrast', 'material_too', 'solid_too')), rec)
summary()
