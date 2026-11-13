"""0.24.149 (user: "백그라운드 이미지를 포토샵처럼 내가 그릴 수 없어?"): Paint Background - a canvas the frame's shape put
behind the model (starting as what is there now), painted in Blender's Image Editor; the background follows the
painting, the painting is kept in the .blend.  Real Cycles renders + compositor (CPU here) read back as numbers; the
painting itself is done here by writing the canvas's pixels (real brush strokes: tests/gui/bg_paint_real_window.py)."""
import os
import tempfile

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import backdrops as bd, bg_color as bgc  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TMP = tempfile.mkdtemp(prefix='mch_bgpaint_')


def setup(scene):
    for o in list(scene.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=0.5, location=(0, 0, 0))
    cam = bpy.data.objects.new('Cam', bpy.data.cameras.new('Cam'))
    scene.collection.objects.link(cam)
    scene.camera = cam
    cam.location = (0, -5, 0)
    cam.rotation_euler = (1.5708, 0, 0)
    scene.render.resolution_x, scene.render.resolution_y = 1920, 1080
    scene.render.resolution_percentage = 100
    scene.render.compositor_device = 'CPU'          # (no GPU in this machine)


def render(name, res=(64, 36)):
    S = bpy.context.scene
    r = S.render
    keep = (r.resolution_x, r.resolution_y)
    S.render.engine = 'CYCLES'
    S.cycles.device = 'CPU'
    S.cycles.samples = 2
    S.cycles.use_denoising = False
    r.resolution_x, r.resolution_y = res
    S.view_settings.view_transform = 'Standard'
    r.image_settings.file_format = 'OPEN_EXR'
    r.filepath = os.path.join(TMP, name + '.exr')
    bpy.ops.render.render(write_still=True)
    r.resolution_x, r.resolution_y = keep
    img = bpy.data.images.load(r.filepath)
    a = np.array(img.pixels[:], dtype=np.float32).reshape(res[1], res[0], 4)
    bpy.data.images.remove(img)
    return a


def srgb(v):
    v = np.asarray(v, np.float32)
    return np.where(v <= 0.0031308, v * 12.92, 1.055 * np.power(v, 1 / 2.4) - 0.055)


setup(S)
st = bgc.settings(S)
st.color = (0.8, 0.05, 0.05)
st.mode = 'COLOR'
r = bpy.ops.mch.bg_paint()
cv = bgc.canvas_image(S)
px = np.empty(cv.size[0] * cv.size[1] * 4, np.float32) if cv is not None else None
if cv is not None:
    cv.pixels.foreach_get(px)
    px = px.reshape(cv.size[1], cv.size[0], 4)
check('Paint Background: a canvas the frame\'s shape (1920 x 1080 for a 1920 x 1080 render), kept in the .blend',
      'FINISHED' in r and cv is not None and tuple(cv.size) == (1920, 1080) and cv.packed_file is not None,
      cv and tuple(cv.size))
check('... it starts as what was behind the model (the colour)', px is not None
      and np.allclose(px[500, 900, :3], srgb((0.8, 0.05, 0.05)), atol=0.01), px is not None and px[500, 900].round(3).tolist())
check('... it is the background now: Picture, Fill, the background on (Compositor), the compositor showing the canvas',
      st.mode == 'IMAGE' and st.image == bgc.CANVAS_PREFIX + cv.name and st.fit == 'FILL' and bgc.comp_on(S)
      and S.compositing_node_group.nodes[bgc.N_PIC].image is cv)

a = render('canvas_red')
check('a render: the canvas behind the model', np.allclose(a[2, 2, :3], (0.8, 0.05, 0.05), atol=0.03),
      a[2, 2].round(3).tolist())
px[:, :960, :3] = (0.0, 0.0, 1.0)                    # "painted": the left half blue
cv.pixels.foreach_set(px.ravel())
cv.update()
a = render('canvas_painted')
check('painted (the left half blue): the background follows - left blue, right still the colour',
      np.allclose(a[18, 3, :3], (0, 0, 1), atol=0.03) and np.allclose(a[18, 60, :3], (0.8, 0.05, 0.05), atol=0.03),
      (a[18, 3].round(3).tolist(), a[18, 60].round(3).tolist()))

# the painting kept in the file
check('(the canvas changed since it was packed)', cv.is_dirty)
path = os.path.join(TMP, 'painted.blend')
bpy.ops.wm.save_as_mainfile(filepath=path)
check('saving the file: the painting packed again (kept in the .blend)', not cv.is_dirty and cv.packed_file is not None)
bpy.ops.wm.open_mainfile(filepath=path)
S = bpy.context.scene
st = bgc.settings(S)
cv = bgc.canvas_image(S)
px2 = np.empty(cv.size[0] * cv.size[1] * 4, np.float32) if cv is not None else None
if cv is not None:
    cv.pixels.foreach_get(px2)
    px2 = px2.reshape(cv.size[1], cv.size[0], 4)
check('the file opened again: the painted canvas there, the left half still blue, still the background',
      cv is not None and np.allclose(px2[500, 100, :3], (0, 0, 1), atol=0.01)
      and np.allclose(px2[500, 1800, :3], srgb((0.8, 0.05, 0.05)), atol=0.01) and bgc.comp_on(S)
      and S.compositing_node_group.nodes[bgc.N_PIC].image is cv)

# another picture picked: the canvas kept (not let go), Paint Background again = the same painting back
pic = next(e[0] for e in bd.entries() if e[0].startswith(bd.BUILTIN) and e[0].endswith('_land.jpg'))
bpy.ops.mch.bg_picture(ident=pic)
check('a backdrop picked after painting: that picture behind, the painting kept in the file',
      st.image == pic and bgc.canvas_image(S) is None and cv.name in bpy.data.images
      and S.compositing_node_group.nodes[bgc.N_PIC].image is not cv)
bpy.ops.mch.bg_paint()
check('Paint Background again: the same canvas, the painting as it was', bgc.canvas_image(S) is cv
      and np.allclose(np.array(cv.pixels[(500 * 1920 + 100) * 4:(500 * 1920 + 100) * 4 + 3]), (0, 0, 1), atol=0.01))
bpy.ops.mch.bg_picture(ident=pic)
st.fit = 'FILL'
r = bpy.ops.mch.bg_paint(fresh=True)
cv2 = bgc.canvas_image(S)
src = bpy.data.images.load(bd.path(pic), check_existing=True)
ref = src.copy()
ref.scale(1920, int(round(src.size[1] * 1920 / src.size[0])))
rp = np.array(ref.pixels[:], np.float32).reshape(ref.size[1], ref.size[0], 4)
c_ref = rp[ref.size[1] // 2, 960, :3]
c_cv = np.array(cv2.pixels[(540 * 1920 + 960) * 4:(540 * 1920 + 960) * 4 + 3])
check('New Canvas with a backdrop behind: the canvas starts as that picture (its middle the picture\'s middle)',
      'FINISHED' in r and cv2 is cv and np.allclose(c_cv, c_ref, atol=0.04) and cv.get('mch_from') == pic,
      (c_cv.round(3).tolist(), c_ref.round(3).tolist()))
px3 = np.array(cv.pixels[:], np.float32).reshape(1080, 1920, 4)
px3[..., :3] = (0.0, 1.0, 0.0)
cv.pixels.foreach_set(px3.ravel())
cv.update()
bpy.ops.mch.bg_paint(fresh=True)
c2 = np.array(cv.pixels[(540 * 1920 + 960) * 4:(540 * 1920 + 960) * 4 + 3])
check('New Canvas while painting: back to what it started from (the picture, not the paint)',
      np.allclose(c2, c_ref, atol=0.04), c2.round(3).tolist())

# the World way shows the canvas too; Colour mode: the canvas still kept
st.method = 'WORLD'
bpy.ops.mch.bg_method(method='WORLD')
check('the World way: the canvas in the world\'s picture node', bgc.world_on(S)
      and S.world.node_tree.nodes[bgc.N_PIC].image is cv)
bpy.ops.mch.bg_method(method='COMP')
bpy.ops.mch.bg_picture(mode='COLOR')
check('Colour: the canvas out of the background (the colour behind) but kept in the file',
      S.compositing_node_group.nodes[bgc.N_PIC].image is None and cv.name in bpy.data.images
      and cv.get(bgc.CANVAS_TAG))

from mecha_lab import mech_shader_ui as msu  # noqa: E402
bpy.ops.mch.bg_paint()
items, _h = msu.hdri_content(bpy.context, 0, 320, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the Render tab, Background: Paint Background… and New Canvas', 'Paint Background…' in labels
      and 'New Canvas' in labels)
summary()
