"""0.24.140 (user: "5.3 에는 dlss 디노이즈도 있으니까 그거도 같이 해서 뷰포트 빠르게 렌더링하는 거 찾아 줘") Fast Viewport
and Blender 5.3's DLSS (NVIDIA DLSS Ray Reconstruction, the Rendered viewport's denoiser, with its Upscale Mode):
used when Blender takes it, instead of Fast Viewport's own half resolution; anywhere else (5.2, no NVIDIA card) the
same as before.  Runs on 5.2 and 5.3 (this server has no NVIDIA card: Blender's acceptance is stood in for)."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import fast_view as fv, mech_shader_ui as msu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.render.engine = 'CYCLES'
cy = S.cycles
v53 = bpy.app.version >= (5, 3, 0)
check(f'Blender {bpy.app.version_string}: the DLSS settings exist only from 5.3 on',
      fv.dlss_possible(S) == v53 and hasattr(cy, 'preview_denoising_upscale_quality') == v53)
check('no NVIDIA card here: Cycles\' own check says no DLSS GPU', fv.dlss_gpu(C) is False)
# 1. as Blender is here: the plan as before
msg = fv.apply(C)
ch = fv.changes(S)['scene']
check('Fast Viewport without DLSS: half resolution, denoised from the first sample, the denoiser left as it was',
      ch.get('render.preview_pixel_size', [None, None])[1] == '2' and 'cycles.preview_denoiser' not in ch
      and cy.preview_denoiser != 'DLSS', (msg, ch))
note = fv.dlss_note(C)
items, _h = msu.hdri_content(C, 0, 300, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check('the Render tab: on 5.3 a line saying what DLSS needs (NVIDIA RTX, driver 620+); on 5.2 no DLSS line',
      (note.startswith('DLSS (Blender 5.3): needs an NVIDIA RTX card') and note in labels) if v53
      else (note == '' and not any('DLSS' in lb for lb in labels)), (note, [lb for lb in labels if 'DLSS' in lb]))
fv.restore(C)
check('off: every value back', fv.changes(S) == {} and S.render.preview_pixel_size == 'AUTO',
      S.render.preview_pixel_size)
# 2. an NVIDIA card Blender cannot use for DLSS (driver too old): Blender refuses DLSS - the plan as before
fv_gpu = fv.dlss_gpu
fv.dlss_gpu = lambda context=None: True
msg = fv.apply(C)
ch = fv.changes(S)['scene']
check('DLSS not taken by Blender (the denoiser list has no DLSS): the half resolution stays, nothing about DLSS kept',
      ch.get('render.preview_pixel_size', [None, None])[1] == '2' and 'cycles.preview_denoiser' not in ch, ch)
fv.restore(C)
# 3. Blender takes DLSS (a stand-in for the NVIDIA card): DLSS + its upscaling instead of the half resolution
if v53:
    real_try = fv._try_dlss
    fv._try_dlss = lambda c: True
    old_mode = cy.preview_denoising_upscale_quality
    msg = fv.apply(C)
    ch = fv.changes(S)['scene']
    check('5.3 with DLSS taken: the denoiser DLSS (kept for Off), Upscale Performance, NOT the half resolution '
          '(both together would halve twice), samples 64, denoised from the first sample',
          ch.get('cycles.preview_denoiser', [None, None])[1] == 'DLSS'
          and cy.preview_denoising_upscale_quality == fv.DLSS_UPSCALE and 'render.preview_pixel_size' not in ch
          and cy.preview_samples <= 64 and cy.preview_denoising_start_sample == 1, ch)
    fv.restore(C)
    check('off: the upscale mode back as it was', cy.preview_denoising_upscale_quality == old_mode,
          cy.preview_denoising_upscale_quality)
    fv._try_dlss = real_try
else:
    check('(5.2: the DLSS path is checked when this file runs on 5.3)', True)
fv.dlss_gpu = fv_gpu
summary()
