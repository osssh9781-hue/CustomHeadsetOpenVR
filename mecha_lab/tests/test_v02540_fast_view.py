"""0.24.135 (user: "뷰포트에서도 빨라야 돼" - GAMERA 192 M triangles; a lighter copy of the parts was declined) Fast
Viewport: Solid draws without the per-triangle extras (wireframes - Blender's overlay and Mecha Lab's Wire -, shadows,
X-Ray, face orientation); the Cycles viewport gets its own lighter settings (64 samples, denoised from the first sample,
half resolution); F12 / Quick Render settings are not touched; off puts every value back unless you changed it while it
was on.  Blender's viewport anti-aliasing (a Preference) only from its own button."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_view as fv, mech_shader_ui as msu, zb_ui  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.render.engine = 'CYCLES'
cy = S.cycles

views = fv._views()
check('a 3D view to work on (the bpy module has a window)', len(views) >= 1, len(views))
scr, idx, sp = views[0]
sp.overlay.show_wireframes = True
sp.overlay.show_face_orientation = True
sp.shading.show_shadows = True
sp.shading.show_xray = True
sp.shading.show_cavity = True
bpy.ops.mesh.primitive_cube_add()
a = C.active_object
bpy.ops.mesh.primitive_uv_sphere_add(location=(3, 0, 0))
b = C.active_object
a.show_wire = b.show_wire = True                       # (Mecha Lab's Wire on both parts)
cy.preview_samples, cy.use_preview_denoising, cy.preview_denoising_start_sample = 1024, False, 4
S.render.preview_pixel_size = 'AUTO'
final = (cy.samples, cy.use_denoising, cy.denoising_prefilter, S.render.resolution_x, S.render.resolution_percentage,
         cy.max_bounces)


def view_vals():
    return (sp.overlay.show_wireframes, sp.overlay.show_face_orientation, sp.shading.show_shadows, sp.shading.show_xray)


msg = fv.apply(C)
check('on: the Solid extras off (wireframe overlay, face orientation, shadows, X-Ray), cavity kept; the parts\' Wire off',
      view_vals() == (False, False, False, False) and sp.shading.show_cavity and not a.show_wire and not b.show_wire
      and fv.on(S), (msg, view_vals()))
check('on: the Cycles viewport 64 samples, denoised from sample 1, half resolution (pixel size 2)',
      cy.preview_samples == 64 and cy.use_preview_denoising and cy.preview_denoising_start_sample == 1
      and S.render.preview_pixel_size == '2', (cy.preview_samples, cy.use_preview_denoising, S.render.preview_pixel_size))
check('... F12 / Quick Render settings untouched (samples, denoiser, size, bounces)',
      (cy.samples, cy.use_denoising, cy.denoising_prefilter, S.render.resolution_x, S.render.resolution_percentage,
       cy.max_bounces) == final)
ch = fv.changes(S)
check('what it changed is kept on the scene and the screen (saved with the file)',
      'cycles.preview_samples' in ch['scene'] and sorted(ch['wire']) == sorted([a.name, b.name])
      and scr.name in ch['screens'] and fv.KEY in scr.keys(), ch)
msg = fv.restore(C)
check('off: every value back (view, parts\' Wire, Cycles viewport)',
      view_vals() == (True, True, True, True) and a.show_wire and b.show_wire and cy.preview_samples == 1024
      and not cy.use_preview_denoising and cy.preview_denoising_start_sample == 4 and S.render.preview_pixel_size == 'AUTO'
      and not fv.on(S) and fv.KEY not in scr.keys(), msg)

# a value you change while it is on stays yours
fv.apply(C)
cy.preview_samples = 200
sp.shading.show_shadows = True
fv.restore(C)
check('a change made while on stays (samples 200, shadows on); the rest goes back',
      cy.preview_samples == 200 and sp.shading.show_shadows and sp.overlay.show_wireframes and a.show_wire)
# lighter already: left as it is
cy.preview_samples = 32
S.render.preview_pixel_size = '4'
fv.apply(C)
lite = (cy.preview_samples, S.render.preview_pixel_size, 'cycles.preview_samples' in fv.changes(S)['scene'])
fv.restore(C)
check('already lighter (32 samples, pixel size 4): left alone, and still so after off',
      lite == (32, '4', False) and cy.preview_samples == 32 and S.render.preview_pixel_size == '4', lite)

# the operator, the VIEW row, the panel
r1 = bpy.ops.mch.fast_view()
on1 = fv.on(S)
w_, area, region = None, None, None
for win in C.window_manager.windows:
    for ar in win.screen.areas:
        if ar.type == 'VIEW_3D':
            w_, area = win, ar
            region = next(rg for rg in ar.regions if rg.type == 'WINDOW')
with C.temp_override(window=w_, area=area, region=region):
    items = zb_ui.corner_items(C, 1600, 900, 1.0)
fast = [i for i in items if getattr(i, 'label', '') == 'Fast']
r2 = bpy.ops.mch.fast_view()
check('Fast in the VIEW row (Wire | Solo | Fast) is lit while on; the button turns it on and off',
      'FINISHED' in r1 and on1 and len(fast) == 1 and fast[0].on and fast[0].action == ('op', 'mch.fast_view', {})
      and {'Wire', 'Solo'} <= {getattr(i, 'label', '') for i in items} and not fv.on(S), (r1, r2, [i.label for i in items]))
ps = C.preferences.system
ps.viewport_aa = '8'
pitems, _h = msu.hdri_content(C, 0, 300, 1.0)
labels = [getattr(i, 'label', '') for i in pitems]
m1 = fv.aa_toggle(C)
v1 = ps.viewport_aa
pitems2, _h = msu.hdri_content(C, 0, 300, 1.0)
labels2 = [getattr(i, 'label', '') for i in pitems2]
m2 = fv.aa_toggle(C)
check('the panel: Fast Viewport, "Viewport AA: 8 Samples > Single Pass"; the AA button sets Single Pass and back to 8',
      'Fast Viewport (Solid + Rendered)' in labels and 'Viewport AA: 8 Samples > Single Pass' in labels
      and v1 == 'FXAA' and 'Viewport AA: Single Pass (back to 8)' in labels2 and ps.viewport_aa == '8'
      and 'Preferences' in m1 and 'Preferences' in m2, (m1, m2))
summary()
