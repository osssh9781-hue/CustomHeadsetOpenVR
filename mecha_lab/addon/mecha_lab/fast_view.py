"""0.24.135 Fast Viewport (user: "뷰포트에서도 빨라야 돼" - GAMERA, 192 M triangles, RTX 5090; a lighter copy of the
parts was offered and declined, so only how the viewport draws changes - never the meshes).

On (the VIEW row's Fast, or the Quick Render section):
* Solid: the wireframes (Blender's overlay and Mecha Lab's Wire on parts), shadows, X-Ray and face orientation off -
  each of them draws every triangle / edge again, so they grow with the polygon count (cavity and outline work per
  pixel and stay);
* Rendered (Cycles): the viewport's own settings only - samples 1024 -> 64, the denoiser on from the first sample
  (Blender's Automatic denoiser = OptiX on an NVIDIA card, unless you picked another), half the viewport resolution.  F12 and Quick Render keep the scene's render settings.
Off puts back every value it changed - unless you changed that value yourself while it was on.  What it changed is
kept on the scene and on the screen (saved with the file), so it can be put back after a reload too.

Blender's viewport anti-aliasing (Preferences > Viewport, default 8 samples: the whole scene is drawn 8 more times
each time the view stops) is a Blender Preference: only its own button changes it, and says so.

0.24.140 (user: "5.3 에는 dlss 디노이즈도 있으니까 그거도 같이 해서 뷰포트 빠르게") Blender 5.3's viewport denoiser
"DLSS" (NVIDIA DLSS Ray Reconstruction - the Rendered viewport only, not F12) with its Upscale Mode (the viewport
rendered smaller and scaled up by DLSS): when Blender takes it (5.3+, an NVIDIA RTX card - compute capability 7.5+ -
with driver 620+, Cycles set to that GPU), Fast Viewport uses DLSS with Upscale ``DLSS_UPSCALE`` instead of its own
half resolution (both together would halve twice); else everything as before.
"""
from __future__ import annotations

import json

import bpy

KEY = 'mch_fast_view'
VIEW_OFF = (('overlay', 'show_wireframes'), ('overlay', 'show_face_orientation'), ('shading', 'show_shadows'),
            ('shading', 'show_xray'))
CYCLES = (('cycles', 'preview_samples', 64, 'max'),            # (only lowered)
          ('cycles', 'use_preview_denoising', True, 'set'),
          ('cycles', 'preview_denoising_start_sample', 1, 'set'),
          ('cycles', 'preview_denoising_use_gpu', True, 'set'),
          ('render', 'preview_pixel_size', '2', 'pixels'))
AA_FAST = 'FXAA'
AA = {'before': None}
DLSS_UPSCALE = 'PERFORMANCE'        # (Blender's own default is Balanced; Fast Viewport is about speed)
DLSS_MODES = ('NONE', 'QUALITY', 'BALANCED', 'PERFORMANCE', 'ULTRA_PERFORMANCE')


def dlss_possible(scene):
    """Does this Blender have the DLSS viewport denoiser at all (5.3+)?"""
    cy = getattr(scene, 'cycles', None)
    return cy is not None and hasattr(cy, 'preview_denoising_upscale_quality')


def dlss_gpu(context=None):
    """Cycles' own check: a GPU used for rendering supports DLSS (NVIDIA RTX, driver new enough)."""
    try:
        prefs = (context or bpy.context).preferences.addons['cycles'].preferences
        return bool(prefs.has_dlss_gpu_devices())
    except (KeyError, AttributeError, RuntimeError):
        return False


def _try_dlss(cy):
    """The viewport denoiser set to DLSS - True only when Blender took it (its list has DLSS only with an NVIDIA
    card it can use)."""
    try:
        cy.preview_denoiser = 'DLSS'
        return cy.preview_denoiser == 'DLSS'
    except (TypeError, ValueError):
        return False


def dlss_on(scene):
    cy = getattr(scene, 'cycles', None)
    return bool(cy is not None and getattr(cy, 'preview_denoiser', '') == 'DLSS'
                and getattr(cy, 'use_preview_denoising', False))


def dlss_note(context):
    """One line for the panel about DLSS (Blender 5.3+ only), or ''."""
    scene = context.scene
    if not dlss_possible(scene):
        return ''
    if dlss_on(scene):
        mode = scene.cycles.preview_denoising_upscale_quality.replace('_', ' ').title()
        return f'Rendered viewport: DLSS (NVIDIA) - Upscale {mode}'
    if dlss_gpu(context):
        return 'DLSS ready (NVIDIA): Fast Viewport turns it on for the Rendered viewport'
    return 'DLSS (Blender 5.3): needs an NVIDIA RTX card, driver 620+, Cycles on that GPU'


def on(scene):
    return scene is not None and KEY in scene.keys()


def _load(idb):
    try:
        return json.loads(idb[KEY])
    except (TypeError, ValueError, KeyError):
        return {}


def _views():
    """(screen, area index, space) of every 3D view in the open windows."""
    out = []
    wm = bpy.context.window_manager
    for win in getattr(wm, 'windows', ()):
        scr = win.screen
        for i, area in enumerate(scr.areas):
            if area.type == 'VIEW_3D':
                sp = area.spaces.active
                if sp is not None and sp.type == 'VIEW_3D':
                    out.append((scr, str(i), sp))
    return out


def _owner(scene, group):
    return getattr(scene, group, None)


def apply(context):
    """Fast Viewport on for the scene and the open 3D views; every old value kept.  Returns a short summary."""
    scene = context.scene
    if on(scene):
        return 'Fast Viewport is on'
    keep = {'scene': {}, 'wire': []}
    plan = list(CYCLES)
    if dlss_possible(scene) and dlss_gpu(context):
        # (Blender 5.3 DLSS: the denoiser and its upscaling instead of the half resolution - only when Blender takes
        #  the value; on a card / driver it does not accept, the plan stays as it was)
        cy = scene.cycles
        old = cy.preview_denoiser
        ok = _try_dlss(cy)
        if ok:
            keep['scene']['cycles.preview_denoiser'] = [old, 'DLSS']
            plan = [c for c in plan if c[1] != 'preview_pixel_size']
            plan.append(('cycles', 'preview_denoising_upscale_quality', DLSS_UPSCALE, 'set'))
    for group, name, value, how in plan:
        owner = _owner(scene, group)
        if owner is None or not hasattr(owner, name):
            continue
        old = getattr(owner, name)
        new = value
        if how == 'max':
            new = min(int(old), int(value))
        elif how == 'pixels' and old not in ('AUTO', '1'):
            continue                                  # (already coarser: left as it is)
        if old == new:
            continue
        try:
            setattr(owner, name, new)
        except (TypeError, ValueError, AttributeError):
            continue
        keep['scene'][f'{group}.{name}'] = [old, new]
    for ob in scene.objects:                          # (Mecha Lab's Wire: the parts' own wireframe)
        try:
            if ob.type == 'MESH' and ob.show_wire:
                ob.show_wire = False
                keep['wire'].append(ob.name)
        except (AttributeError, ReferenceError):
            continue
    screens = {}
    for scr, idx, sp in _views():
        vals = {}
        for group, name in VIEW_OFF:
            owner = getattr(sp, group, None)
            if owner is not None and hasattr(owner, name) and getattr(owner, name):
                setattr(owner, name, False)
                vals[f'{group}.{name}'] = True
        if vals:
            screens.setdefault(scr.name, {})[idx] = vals
    for name, views in screens.items():
        scr = bpy.data.screens.get(name)
        if scr is not None:
            mine = _load(scr) if KEY in scr.keys() else {}
            mine.update(views)
            scr[KEY] = json.dumps(mine)
    keep['screens'] = sorted(screens)
    scene[KEY] = json.dumps(keep)
    n = len(keep['scene']) + len(keep['wire']) + sum(len(v) for vs in screens.values() for v in vs.values())
    return f'Fast Viewport on: {n} setting(s) lighter (off puts them back)'


def restore(context=None, scene=None):
    """Put back what ``apply`` changed - each value only if it is still the one Fast Viewport set (a change you made
    while it was on stays)."""
    scene = scene or (context.scene if context is not None else None)
    if not on(scene):
        return 'Fast Viewport is off'
    keep = _load(scene)
    del scene[KEY]
    back = 0
    for dotted, (old, new) in keep.get('scene', {}).items():
        group, _s, name = dotted.partition('.')
        owner = _owner(scene, group)
        try:
            if owner is not None and getattr(owner, name) == new:
                setattr(owner, name, old)
                back += 1
        except (TypeError, ValueError, AttributeError):
            pass
    for name in keep.get('wire', ()):
        ob = bpy.data.objects.get(name)
        if ob is not None and not ob.show_wire:
            ob.show_wire = True
            back += 1
    live = {}
    for scr, idx, sp in _views():
        live.setdefault(scr.name, {})[idx] = sp
    for name in keep.get('screens', ()):
        scr = bpy.data.screens.get(name)
        if scr is None or KEY not in scr.keys():
            continue
        views = _load(scr)
        del scr[KEY]
        for idx, vals in views.items():
            sp = live.get(name, {}).get(idx)
            if sp is None:
                continue
            for dotted in vals:
                group, _s, prop = dotted.partition('.')
                owner = getattr(sp, group, None)
                if owner is not None and hasattr(owner, prop) and not getattr(owner, prop):
                    setattr(owner, prop, True)
                    back += 1
    return f'Fast Viewport off: {back} setting(s) back as they were'


def changes(scene):
    """What Fast Viewport changed (for the panel / tests): {'scene': {...}, 'wire': [...], 'screens': [...]}."""
    return _load(scene) if on(scene) else {}


# ---- Blender's viewport anti-aliasing (a Preference: only from its own button) ---------------------------------------

def aa_value(context=None):
    try:
        return (context or bpy.context).preferences.system.viewport_aa
    except AttributeError:
        return None


def aa_label(value):
    return {'OFF': 'Off', 'FXAA': 'Single Pass', '5': '5 Samples', '8': '8 Samples', '11': '11 Samples',
            '16': '16 Samples', '32': '32 Samples'}.get(value, str(value))


def aa_toggle(context=None):
    """Single Pass <-> what it was before (8 Samples when not known).  Returns a message."""
    ps = (context or bpy.context).preferences.system
    cur = ps.viewport_aa
    if cur != AA_FAST:
        AA['before'] = cur
        ps.viewport_aa = AA_FAST
        return (f'Viewport anti-aliasing: {aa_label(cur)} -> Single Pass (Blender Preferences > Viewport) - the scene '
                f'is drawn once when the view stops, not {cur} more times')
    back = AA['before'] or '8'
    ps.viewport_aa = back
    AA['before'] = None
    return f'Viewport anti-aliasing back to {aa_label(back)} (Blender Preferences > Viewport)'


class MCH_OT_fast_view(bpy.types.Operator):
    """Fast Viewport: lighter Solid drawing (wireframes, shadows, X-Ray off) and lighter Cycles viewport settings
    (64 samples, denoised, half resolution) - F12 / Quick Render unchanged.  Again: everything back"""
    bl_idname = 'mch.fast_view'
    bl_label = 'Fast Viewport'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        msg = restore(context) if on(context.scene) else apply(context)
        self.report({'INFO'}, msg)
        for area in context.screen.areas if context.screen else ():
            area.tag_redraw()
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


class MCH_OT_viewport_aa(bpy.types.Operator):
    """Blender's viewport anti-aliasing (a Blender Preference): Single Pass draws a heavy scene once when the view
    stops instead of 8 more times; again: back to what it was"""
    bl_idname = 'mch.viewport_aa'
    bl_label = 'Viewport Anti-Aliasing'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        self.report({'INFO'}, aa_toggle(context))
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


CLASSES = (MCH_OT_fast_view, MCH_OT_viewport_aa)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
