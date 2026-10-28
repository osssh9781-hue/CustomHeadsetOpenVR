"""0.24.61 High Poly Mode for the ZBrush screen (Preferences / the HiPoly button on the view shelf).

While the ZBrush screen is on (Sculpt Mode in the MECHA LAB tab, ZBrush style) it takes the load off Blender:
    - Blender's Sculpt option Delay Viewport Updates (faster turning of the view).  0.24.76 not Deform Only any
      more: with it Smooth by Angle / Mirror / Subdivision were not shown while sculpting - flat-shaded parts turned
      smooth the moment you went to the ZBrush screen,
    - the heavy viewport extras off: wireframe, statistics, face orientation, mesh analysis, cavity, shadows,
      X-Ray, the selection outline.
Leaving the ZBrush screen (another mode, tab or style) or turning the mode off puts every one of them back as it
was.  What it changed is kept on the screen (not in the undo history), so a saved file is put back too.
Blender's own Preferences (undo steps, graphics backend) are never touched - ``advice()`` only names them.
"""
from __future__ import annotations

import json

import bpy

SCULPT = ('use_sculpt_delay_updates',)       # 0.24.76 (Deform Only hid Smooth by Angle: the shading changed)
VIEW_OFF = (('overlay', 'show_wireframes'), ('overlay', 'show_stats'), ('overlay', 'show_face_orientation'),
            ('overlay', 'show_statvis'), ('shading', 'show_cavity'), ('shading', 'show_shadows'),
            ('shading', 'show_xray'), ('shading', 'show_object_outline'))
KEY = 'mch_highpoly'
TICK = 0.4


def pref_on():
    from .workspace_ui import pref
    return bool(pref('zb_highpoly', False))


def set_pref(value):
    from .workspace_ui import prefs
    p = prefs()
    if p is not None and hasattr(p, 'zb_highpoly'):
        p.zb_highpoly = bool(value)


def _views(screen):
    out = []
    for i, area in enumerate(getattr(screen, 'areas', ())):
        if area.type == 'VIEW_3D':
            sp = area.spaces.active
            if sp is not None and sp.type == 'VIEW_3D':
                out.append((str(i), sp))
    return out


def applied(screen):
    return screen is not None and KEY in screen.keys()


def _load(screen):
    try:
        return json.loads(screen[KEY])
    except (TypeError, ValueError, KeyError):
        return {}


def _other(scene_name, but):
    """Another screen with High Poly Mode on for the same scene (it shares the scene's sculpt options)."""
    for s in bpy.data.screens:
        if s != but and applied(s) and _load(s).get('scene') == scene_name:
            return s
    return None


def apply(scene, screen):
    """Lighten ``scene``'s sculpt options and every 3D view of ``screen``; what was there is kept on the screen."""
    if screen is None or scene is None or applied(screen):
        return False
    sc = scene.tool_settings.sculpt
    keep = {'scene': scene.name, 'sculpt': {}, 'views': {}}
    if _other(scene.name, screen) is None:          # (the scene's sculpt options: kept once, by the first screen)
        for name in SCULPT:
            if hasattr(sc, name):
                keep['sculpt'][name] = bool(getattr(sc, name))
                setattr(sc, name, True)
    for idx, sp in _views(screen):
        vals = {}
        for group, name in VIEW_OFF:
            owner = getattr(sp, group, None)
            if owner is not None and hasattr(owner, name):
                vals[f'{group}.{name}'] = bool(getattr(owner, name))
                setattr(owner, name, False)
        keep['views'][idx] = vals
    screen[KEY] = json.dumps(keep)
    return True


def restore(screen, scene=None):
    """Put back what ``apply`` changed (the views of ``screen``, the sculpt options of its scene)."""
    if not applied(screen):
        return False
    keep = _load(screen)
    del screen[KEY]
    other = _other(keep.get('scene', ''), screen)
    if other is not None and keep.get('sculpt'):    # still on in another window: it keeps the sculpt options
        more = _load(other)
        more['sculpt'] = keep['sculpt']
        other[KEY] = json.dumps(more)
        keep['sculpt'] = {}
    scene = bpy.data.scenes.get(keep.get('scene', '')) or scene
    if scene is not None:
        sc = scene.tool_settings.sculpt
        for name, v in keep.get('sculpt', {}).items():
            if hasattr(sc, name):
                setattr(sc, name, bool(v))
    views = dict(_views(screen))
    for idx, vals in keep.get('views', {}).items():
        sp = views.get(idx)
        if sp is None:
            continue
        for dotted, v in vals.items():
            group, _s, name = dotted.partition('.')
            owner = getattr(sp, group, None)
            if owner is not None and hasattr(owner, name):
                setattr(owner, name, bool(v))
    return True


def heavy(ob):
    """What makes this SubTool heavier than it needs to be for sculpting (short texts, ZBrush style)."""
    out = []
    if ob is None or ob.type != 'MESH':
        return out
    me = ob.data
    keys = getattr(me, 'shape_keys', None)
    if keys is not None and len(keys.key_blocks) > 1:
        out.append(f'{len(keys.key_blocks) - 1} shape key(s): sculpting with them is slow')
    if len(me.uv_layers) > 1:
        out.append(f'{len(me.uv_layers)} UV maps')
    if len(me.color_attributes) > 1:
        out.append(f'{len(me.color_attributes)} colour layers')
    if len(ob.vertex_groups) > 3:
        out.append(f'{len(ob.vertex_groups)} vertex groups')
    mods = [m for m in ob.modifiers if m.show_viewport and m.type != 'MULTIRES']
    if mods:
        out.append('modifiers on: ' + ', '.join(m.name for m in mods[:3]) + (' ...' if len(mods) > 3 else ''))
    try:
        if ob.mode == 'SCULPT' and bpy.context.sculpt_object is ob and ob.use_dynamic_topology_sculpting:
            out.append('Dyntopo on (slow on dense meshes)')
    except (AttributeError, ReferenceError):
        pass
    return out


def advice():
    """Blender Preferences that help with dense meshes - named only, never changed here."""
    return ('Edit > Preferences > System: Undo Steps lower (e.g. 16) saves memory on dense meshes',
            'Preferences > System > Display Graphics: try Vulkan (faster on some drivers, not on all)',
            'Windows: power plan High Performance; Blender on the fast GPU')


FADE_KEY = 'mch_zb_fade'
FADE_ALPHA = 0.5             # 0.24.76 the other objects this faded on the ZBrush screen (the SubTool stands out)


def fade_apply(screen):
    """0.24.76 The ZBrush screen: Blender's Fade Inactive Geometry on, so the active SubTool is the bright one (which
    one is picked was hard to tell); what was there is kept on the screen."""
    if screen is None or FADE_KEY in screen.keys():
        return False
    keep = {}
    for idx, sp in _views(screen):
        ov = sp.overlay
        if hasattr(ov, 'show_fade_inactive'):
            keep[idx] = [bool(ov.show_fade_inactive), float(getattr(ov, 'fade_inactive_alpha', FADE_ALPHA))]
            ov.show_fade_inactive = True
            if hasattr(ov, 'fade_inactive_alpha'):
                ov.fade_inactive_alpha = FADE_ALPHA
    screen[FADE_KEY] = json.dumps(keep)
    return True


def fade_restore(screen):
    if screen is None or FADE_KEY not in screen.keys():
        return False
    try:
        keep = json.loads(screen[FADE_KEY])
    except (TypeError, ValueError):
        keep = {}
    del screen[FADE_KEY]
    views = dict(_views(screen))
    for idx, (on, alpha) in keep.items():
        sp = views.get(idx)
        if sp is None:
            continue
        sp.overlay.show_fade_inactive = bool(on)
        if hasattr(sp.overlay, 'fade_inactive_alpha'):
            sp.overlay.fade_inactive_alpha = float(alpha)
    return True


def fade_update(context):
    """Fade on while the ZBrush screen is on (any High Poly setting), back as it was after."""
    from . import zb_sculpt
    screen = getattr(context, 'screen', None)
    if screen is None:
        return False
    if zb_sculpt.on(context):
        return fade_apply(screen)
    return fade_restore(screen)


def _wanted(context):
    from . import zb_sculpt
    return pref_on() and zb_sculpt.on(context)


def update(context):
    """Apply or put back for this window, as the ZBrush screen / the preference say; True if it changed."""
    screen = getattr(context, 'screen', None)
    scene = getattr(context, 'scene', None)
    if screen is None:
        return False
    want = _wanted(context)
    if want and not applied(screen):
        return apply(scene, screen)
    if applied(screen) and not want:
        return restore(screen, scene)
    return False


def _tick():
    try:
        wm = bpy.context.window_manager
        for win in wm.windows:
            with bpy.context.temp_override(window=win, screen=win.screen):
                if update(bpy.context) | fade_update(bpy.context):
                    for area in win.screen.areas:
                        area.tag_redraw()
    except Exception:          # (a closing window, a file loading: try again on the next tick)
        pass
    return TICK


def register():
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=TICK, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    try:                                             # (the add-on going away: put every screen back)
        for screen in bpy.data.screens:
            restore(screen)
            fade_restore(screen)
    except (AttributeError, ReferenceError, RuntimeError):
        pass
