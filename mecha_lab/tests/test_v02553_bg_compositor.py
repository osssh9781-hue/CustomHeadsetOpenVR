"""0.24.148 (user: "컴포지터 방식으로 ㄱㄱ, 그 버튼 누르면 뷰포트나 이런 건 다 너가 알아서 세팅"): the Background (colour /
picture) put behind the render in the compositor - Film Transparent, our compositor group (yours nested in it), the
viewport compositor - all set by the one button, all put back by Off.  Real Cycles renders read back as numbers (the
compositor on the CPU here: no GPU in this machine)."""
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import backdrops as bd, bg_color as bgc, quick_render as qr  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp(prefix='mch_bgcomp_')
st = bgc.settings(S)
check('the Background\'s way is the Compositor (as asked); World still there', st.method == 'COMP'
      and {i.identifier for i in st.bl_rna.properties['method'].enum_items} == {'COMP', 'WORLD'})

mine = bpy.data.worlds.new('My World')
mine.node_tree.nodes.new('ShaderNodeTexNoise')
n_world = len(mine.node_tree.nodes)
S.world = mine
mine.node_tree.nodes['Background'].inputs['Color'].default_value = (0.6, 0.6, 0.6, 1.0)
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.7, location=(0, 0, 0))
cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
S.collection.objects.link(cam)
S.camera = cam
cam.location = (0, -5, 0)
cam.rotation_euler = (1.5708, 0, 0)
S.render.film_transparent = False
S.render.compositor_device = 'CPU'           # (this machine has no GPU; yours keeps its own setting)
st.color = (0.9, 0.1, 0.1)
r = bpy.ops.mch.bg_color()
ng = S.compositing_node_group
check('one button: the scene\'s compositor is our group, Film Transparent on, compositing on',
      'FINISHED' in r and bgc.comp_on(S) and ng is not None and ng.get(bgc.COMP_TAG) == S.name
      and S.render.film_transparent and S.render.use_compositing, ng and ng.name)
check('... the world not touched at all (no node of ours in it)', S.world is mine and len(mine.node_tree.nodes) == n_world
      and not any(n.name.startswith('MCH BG') for n in mine.node_tree.nodes) and not bgc.world_on(S))


def render(name, res=(80, 40)):
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = 4
    S.cycles.use_denoising = False
    S.render.resolution_x, S.render.resolution_y = res
    S.render.resolution_percentage = 100
    S.view_settings.view_transform = 'Standard'
    S.render.image_settings.file_format = 'OPEN_EXR'
    S.render.filepath = os.path.join(TMP, name + '.exr')
    bpy.ops.render.render(write_still=True)
    img = bpy.data.images.load(S.render.filepath)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(res[1], res[0], 4)
    bpy.data.images.remove(img)
    return a


a = render('colour')
check('a render: the colour behind the model (corner = the colour, opaque), the model in front',
      np.allclose(a[2, 2, :3], (0.9, 0.1, 0.1), atol=0.02) and a[2, 2, 3] > 0.99
      and not np.allclose(a[20, 40, :3], (0.9, 0.1, 0.1), atol=0.1), (a[2, 2].round(3).tolist(), a[20, 40].round(3).tolist()))

tall = next(e[0] for e in bd.entries() if e[0].startswith(bd.BUILTIN) and e[0].endswith('_port.jpg'))
bpy.ops.mch.bg_picture(ident=tall)
st.fit = 'FIT'
a = render('fit')
check('Picture, Fit (a tall picture in a wide frame): the colour beside it, the picture in the middle',
      np.allclose(a[20, 2, :3], (0.9, 0.1, 0.1), atol=0.02) and np.allclose(a[20, 77, :3], (0.9, 0.1, 0.1), atol=0.02)
      and not np.allclose(a[3, 40, :3], (0.9, 0.1, 0.1), atol=0.1), (a[20, 2].round(3).tolist(), a[3, 40].round(3).tolist()))
st.fit = 'FILL'
a_fill = render('fill')
check('Fill: the picture over the whole frame (no colour at the sides)',
      not np.allclose(a_fill[20, 2, :3], (0.9, 0.1, 0.1), atol=0.1) and a_fill[20, 2, 3] > 0.99, a_fill[20, 2].round(3).tolist())
st.bright = 0.3
a_b = render('bright')
st.bright = 0.0
d = (a_b[3, 3, :3] - a_fill[3, 3, :3]).mean()
check('Brightness +0.3: the picture 0.3 lighter (as the world way\'s Bright / Contrast)', abs(d - 0.3) < 0.03, round(float(d), 3))
st.contrast = 0.5
a_c = render('contrast')
st.contrast = 0.0
want = np.maximum(1.5 * a_fill[3, 3, :3] - 0.25, 0.0)
check('Contrast 0.5: (1 + c) x colour + (b - c/2), as the world way', np.allclose(a_c[3, 3, :3], want, atol=0.02),
      (a_c[3, 3, :3].round(3).tolist(), want.round(3).tolist()))
st.ramp = True
rn = bgc.ramp_node(S)
check('Colour Ramp: the ramp node found in the compositor (the Render tab / Edit Ramp… edit it)',
      rn is not None and rn.id_data is S.compositing_node_group)
rn.color_ramp.elements[0].color = (0.0, 0.0, 1.0, 1.0)
rn.color_ramp.elements[-1].color = (0.0, 0.0, 1.0, 1.0)
a_r = render('ramp')
st.ramp = False
check('... on: the picture takes the ramp\'s colours (all blue here)', np.allclose(a_r[3, 3, :3], (0, 0, 1), atol=0.02),
      a_r[3, 3].round(3).tolist())

# Quick Render: the film stays transparent (the background needs it); Transparent asked = the compositor skipped
qst = qr.settings(C)
qst.transparent = False
qr.prepare(C, qst)
ok1 = S.render.film_transparent and S.render.use_compositing
qr.restore()
qst.transparent = True
qr.prepare(C, qst)
ok2 = S.render.film_transparent and not S.render.use_compositing
qr.restore()
qst.transparent = False
check('Quick Render: the background kept (film transparent, compositor on); Transparent: the compositor skipped, '
      'and both put back after', ok1 and ok2 and S.render.use_compositing and S.render.film_transparent, (ok1, ok2))

# Off: all back
img_name = S.compositing_node_group.nodes[bgc.N_PIC].image.name
r = bpy.ops.mch.bg_color()
check('Off: the compositor as it was (none), Film Transparent off again, our group and the picture gone',
      'FINISHED' in r and not bgc.on(S) and S.compositing_node_group is None and not S.render.film_transparent
      and not any(g.get(bgc.COMP_TAG) for g in bpy.data.node_groups) and img_name not in bpy.data.images
      and bgc.COMP_KEY not in S.keys())

# your own compositor: nested, kept, put back
mine_c = bpy.data.node_groups.new('My Compositor', 'CompositorNodeTree')
mine_c.interface.new_socket('Image', in_out='OUTPUT', socket_type='NodeSocketColor')
rl = mine_c.nodes.new('CompositorNodeRLayers')
rl.scene = S
bcn = mine_c.nodes.new('CompositorNodeBrightContrast')
mine_c.links.new(rl.outputs['Image'], bcn.inputs['Image'])
go = mine_c.nodes.new('NodeGroupOutput')
mine_c.links.new(bcn.outputs['Image'], go.inputs[0])
S.compositing_node_group = mine_c
n_mine = len(mine_c.nodes)
st.mode = 'COLOR'
bpy.ops.mch.bg_color()
ng = S.compositing_node_group
check('your own compositor: our nodes just before its output (what went there goes over the background), yours kept',
      bgc.comp_on(S) and ng is mine_c and ng.nodes.get(bgc.C_RL) is None
      and bgc.C_AO2 in ng.nodes and ng.nodes[bgc.C_AO2].inputs['Foreground'].links[0].from_node == bcn
      and all(n in mine_c.nodes.values() for n in (rl, bcn, go)))
a = render('yours')
check('... a render through both: the colour behind, the model in front', np.allclose(a[2, 2, :3], (0.9, 0.1, 0.1), atol=0.02)
      and not np.allclose(a[20, 40, :3], (0.9, 0.1, 0.1), atol=0.1), (a[2, 2].round(3).tolist(), a[20, 40].round(3).tolist()))
bpy.ops.mch.bg_color()
check('... Off: your compositor exactly as it was (our nodes out, yours linked to its output again)',
      S.compositing_node_group is mine_c and not S.render.film_transparent and len(mine_c.nodes) == n_mine
      and go.inputs[0].links and go.inputs[0].links[0].from_node == bcn)

# World <-> Compositor while on
S.compositing_node_group = None
bpy.ops.mch.bg_color()
r = bpy.ops.mch.bg_method(method='WORLD')
check('World while on: the compositor\'s changes put back, the colour in the world instead',
      'FINISHED' in r and bgc.world_on(S) and not bgc.comp_on(S) and S.compositing_node_group is None
      and not S.render.film_transparent and st.method == 'WORLD')
r = bpy.ops.mch.bg_method(method='COMP')
check('Compositor again: the world\'s nodes out (as it was), the compositor in',
      'FINISHED' in r and bgc.comp_on(S) and not bgc.world_on(S) and len(mine.node_tree.nodes) == n_world)
bpy.ops.mch.bg_color()
check('Off', not bgc.on(S) and S.compositing_node_group is None and not S.render.film_transparent)

# the Render tab: Compositor | World
from mecha_lab import mech_shader_ui as msu  # noqa: E402
items, _h = msu.hdri_content(C, 0, 320, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the Render tab, Background: Compositor | World', 'Compositor' in labels and 'World' in labels)
summary()
