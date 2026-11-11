"""0.24.133 (user: "폴리곤이 높아서 렌더링이 빡센데 좀 더 빠르고 편하게 렌더 못 하나?", "난 사이클만 써") Quick Render (Cycles):
one click renders with fast settings (quality presets, adaptive + denoise, fewer bounces, lighter AO / Bevel / skin
shading, the GPU when set), saves the picture, and puts EVERY scene setting it touched back - the user's file keeps its
own render settings."""
import os
import tempfile

from _harness import bpy, check, fresh, summary
from mathutils import Matrix, Vector  # noqa: E402

import mecha_lab
from mecha_lab import mech_shader_ui as msu, quick_render as qr, ui_bars  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene

# a dense part with the Creature Shader (AO nodes + random-walk skin), a light, a scene camera
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=48, ring_count=24)
body = C.active_object
body.data.remesh_voxel_size = 0.03
bpy.ops.object.voxel_remesh()
r = bpy.ops.mch.creature_apply()
mat = body.active_material
ao_before = sorted((n.name, n.samples) for n in mat.node_tree.nodes if n.bl_idname in qr.RAY_NODES)
sss_before = [(n.name, n.subsurface_method) for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled']
check('setup: the Creature Shader with AO nodes (16 rays) and random-walk skin', 'FINISHED' in r and ao_before
      and all(sm >= 16 for _n, sm in ao_before) and any(m.startswith('RANDOM_WALK') for _n, m in sss_before), (ao_before, sss_before))
bpy.ops.mesh.primitive_cube_add(size=0.5, location=(2.5, 0, 0))
other = C.active_object
bpy.ops.object.light_add(type='AREA', location=(2, -2, 3))
bpy.ops.object.camera_add(location=(0, -5, 0.5), rotation=(1.47, 0, 0))
cam = C.active_object
S.camera = cam
# the user's own render settings (heavy ones, a JPEG output) - Quick Render must leave all of them as they are
r_, cy = S.render, S.cycles
r_.engine = 'CYCLES'
r_.resolution_x, r_.resolution_y, r_.resolution_percentage = 320, 180, 100
cy.samples, cy.max_bounces, cy.adaptive_threshold = 4096, 12, 0.01
cy.denoising_prefilter = 'ACCURATE'
r_.image_settings.file_format = 'JPEG'
r_.film_transparent = False
r_.use_lock_interface = False
WATCH = [(r_, 'engine'), (r_, 'resolution_x'), (r_, 'resolution_y'), (r_, 'resolution_percentage'), (r_, 'film_transparent'),
         (r_, 'use_lock_interface'), (r_.image_settings, 'file_format'), (r_.image_settings, 'color_mode'),
         (cy, 'samples'), (cy, 'max_bounces'), (cy, 'diffuse_bounces'), (cy, 'glossy_bounces'), (cy, 'adaptive_threshold'),
         (cy, 'use_adaptive_sampling'), (cy, 'use_denoising'), (cy, 'denoising_prefilter'), (cy, 'device'),
         (cy, 'caustics_reflective'), (cy, 'caustics_refractive'), (cy, 'blur_glossy'), (cy, 'volume_bounces'),
         (S, 'camera'), (C.view_layer, 'material_override'), (other, 'hide_render'), (body, 'hide_render')]


def snap():
    return [getattr(o, a) for o, a in WATCH]


before = snap()
out = tempfile.mkdtemp(prefix='mch_qr_')
st = S.mch_qrender
st.folder = out
st.camera = 'SCENE'
st.quality = 'DRAFT'
cams_before = len(bpy.data.cameras)
res = bpy.ops.mch.quick_render()
files = [f for f in os.listdir(out) if f.endswith('.png')]
img = bpy.data.images.load(os.path.join(out, files[0])) if files else None
check('Quick Render (Draft) renders and saves a PNG at half size (160 x 90) into the folder',
      'FINISHED' in res and len(files) == 1 and img is not None and tuple(img.size) == (160, 90) and files[0].endswith('_draft.png'),
      (res, files, tuple(img.size) if img else None))
check('... every scene setting it touched is back exactly (engine, size, samples 4096, bounces 12, denoiser, JPEG, '
      'camera, lock interface ...)', snap() == before, [(a, x, y) for (o, a), x, y in zip(WATCH, before, snap()) if x != y])
check('... the AO nodes have their 16 rays again and the skin its random walk',
      sorted((n.name, n.samples) for n in mat.node_tree.nodes if n.bl_idname in qr.RAY_NODES) == ao_before
      and [(n.name, n.subsurface_method) for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'] == sss_before)
check('... no temporary camera left, nothing remembered any more; the last result reads "<seconds> s - <file>"',
      len(bpy.data.cameras) == cams_before and not bpy.data.objects.get(qr.CAM_NAME) and qr._JOB.get('undo') == []
      and not qr._JOB.get('active') and qr.LAST['path'].endswith(files[0]) and ' s - ' in qr.LAST['text'], qr.LAST)
# what it set during the render: watch prepare() directly
st.quality = 'PREVIEW'
summary_text = qr.prepare(C, st)
during = dict(engine=r_.engine, samples=cy.samples, adaptive=cy.use_adaptive_sampling, thr=round(cy.adaptive_threshold, 3),
              denoise=cy.use_denoising, pre=cy.denoising_prefilter, bounces=cy.max_bounces, caustics=cy.caustics_reflective,
              lock=r_.use_lock_interface, png=r_.image_settings.file_format,
              ao=sorted(n.samples for n in mat.node_tree.nodes if n.bl_idname in qr.RAY_NODES),
              sss={n.subsurface_method for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled'})
check('during a Preview: Cycles, 32 samples adaptive (0.05), denoised (fast prefilter), 4 bounces, no caustics, the '
      'interface locked, PNG; AO nodes at 4 rays, the skin Burley', during == dict(
          engine='CYCLES', samples=32, adaptive=True, thr=0.05, denoise=True, pre='FAST', bounces=4, caustics=False, lock=True,
          png='PNG', ao=[4] * len(ao_before), sss={'BURLEY'}) and 'Preview' in summary_text, (during, summary_text))
qr.restore()
check('restore() puts all of that back', snap() == before
      and sorted((n.name, n.samples) for n in mat.node_tree.nodes if n.bl_idname in qr.RAY_NODES) == ao_before)
# Final: the shaders as made
st.quality = 'FINAL'
qr.prepare(C, st)
check('Final: 256 samples, 8 bounces, the accurate prefilter, the shaders as made (no lighter AO / skin)',
      cy.samples == 256 and cy.max_bounces == 8 and cy.denoising_prefilter == 'ACCURATE'
      and sorted((n.name, n.samples) for n in mat.node_tree.nodes if n.bl_idname in qr.RAY_NODES) == ao_before)
qr.restore()
# options: Clay, Selected Only, Hidden Stay Hidden, Transparent
st.quality, st.clay, st.selected_only, st.transparent = 'DRAFT', True, True, True
for o in bpy.data.objects:
    o.select_set(False)
body.select_set(True)
qr.prepare(C, st)
check('Clay = one grey override material; Selected Only hides the unselected part (not the light / camera); '
      'Transparent = film transparent + RGBA', C.view_layer.material_override is not None
      and C.view_layer.material_override.name == qr.CLAY_NAME and other.hide_render and not body.hide_render
      and r_.film_transparent and r_.image_settings.color_mode == 'RGBA')
qr.restore()
check('... all back', snap() == before)
st.clay = st.selected_only = st.transparent = False
other.hide_set(True)
qr.prepare(C, st)
hidden_render = other.hide_render
qr.restore()
other.hide_set(False)
check('Hidden Stay Hidden: a part hidden in the viewport is not rendered (only during the render)', hidden_render
      and not other.hide_render)
# This View with a 3D View (the bpy module has a window): a temporary camera where the view is, gone after - and no
# empty (None) entry left behind in the view layer's objects
st.camera = 'VIEW'
w_, area_, region_, space_ = qr._find_view(C)
qr.prepare(C, st)
used = S.camera
vm_eye = space_.region_3d.view_matrix.inverted().translation if space_ is not None else None
eye_ok = used is not None and vm_eye is not None and (used.matrix_world.translation - vm_eye).length < 1e-4
used_name = used.name if used is not None else None
qr.restore()
check('This View with a 3D View: a temporary camera at the view\'s eye; after: the scene camera back, the temporary '
      'one gone, no empty entry in view_layer.objects', area_ is not None and used_name == qr.CAM_NAME
      and eye_ok and S.camera == cam and not bpy.data.objects.get(qr.CAM_NAME)
      and all(o is not None for o in C.view_layer.objects) and snap() == before,
      (area_, used_name, eye_ok, [o for o in C.view_layer.objects]))
# no 3D View (a script with no window): the scene camera; no camera at all: a clear message
real_find = qr._find_view
qr._find_view = lambda context: (None, None, None, None)
qr.prepare(C, st)
used = S.camera
qr.restore()
S.camera = None
msg = ''
try:
    qr.prepare(C, st)
except RuntimeError as ex:
    msg = str(ex)
qr._find_view = real_find
S.camera = cam
check('This View with no 3D View: the scene camera; no camera at all: "No camera ..." and nothing changed',
      used == cam and msg.startswith('No camera') and snap() == before, msg)
# a cancelled render: nothing saved, all back
qr.prepare(C, st)
qr._JOB.update(active=True, cancelled=True, t0=0.0, path=os.path.join(out, 'x.png'))
qr._finish(C)
check('a cancelled render (Esc): nothing saved, everything back, "Stopped after ..."',
      not os.path.exists(os.path.join(out, 'x.png')) and snap() == before and qr.LAST['text'].startswith('Stopped'))

# --- the camera from the view -------------------------------------------------------------------------------------------
check('view_frame: the viewport shape with the scene\'s long side', qr.view_frame(1600, 900, 1920) == (1920, 1080)
      and qr.view_frame(900, 1600, 1920) == (1080, 1920) and qr.view_frame(1000, 1000, 640) == (640, 640))
vm = (Matrix.Translation((0.3, -0.2, -6.0)) @ Matrix.Rotation(0.4, 4, 'X')).inverted()
mw, kind, lens, ortho, cs, ce = qr.view_camera_params(vm, True, 50.0, 6.0, 0.01, 1000.0)
check('perspective view: the camera sits at the eye, half the viewport lens (Blender draws the view at 2x the camera '
      'view plane)', kind == 'PERSP' and abs(lens - 25.0) < 1e-6 and (mw.translation - vm.inverted().translation).length < 1e-6
      and ortho is None and (cs, ce) == (0.01, 1000.0))
mw, kind, lens, ortho, cs, ce = qr.view_camera_params(vm, False, 50.0, 6.0, 0.01, 1000.0)
check('orthographic view: width = 2 x distance x 36 / lens, moved back half the clip range so nothing in front is cut',
      kind == 'ORTHO' and abs(ortho - 2 * 6.0 * 36 / 50.0) < 1e-6 and cs > 0 and abs(ce - 1500.0) < 1e-6
      and abs((mw.translation - vm.inverted().translation).length - 500.0) < 1e-3)

# --- the GPU ------------------------------------------------------------------------------------------------------------
kind, names = qr.gpu_state(C, refresh=True)
lines = qr.status_lines(C)
check('the GPU state is read from Blender\'s Preferences (none here: "CPU only ...")', kind == 'NONE' and names == []
      and lines[0].startswith('CPU only'), (kind, names, lines))
msg = qr.enable_gpu(C)
check('the Use GPU button with no GPU: a message, the preference left as it was',
      msg.startswith('No GPU') and qr._cycles_prefs(C).compute_device_type == 'NONE', msg)

# --- where it shows ------------------------------------------------------------------------------------------------------
check('a Quick Render tile on the actions bar (camera icon)', any(a[0] == 'render' and a[3] == ('op', 'mch.quick_render', {})
                                                                  and a[1] == 'camera' for a in ui_bars.ACTIONS))
items, _h = msu.hdri_content(C, 0, 300, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the HDRI page starts with QUICK RENDER (CYCLES): Quick Render / Open Folder, Draft / Preview / Final, This View / '
      'Scene Camera, Fast Shading, Clay, the device line',
      any(lb.startswith('QUICK RENDER (CYCLES)') for lb in labels) and {'Quick Render', 'Open Folder', 'Draft', 'Preview', 'Final',
                                                                       'This View', 'Scene Camera'} <= set(labels)
      and any(lb.startswith('CPU only') for lb in labels) and 'Use the GPU (Blender Preferences)' in labels, labels[:24])
summary()
