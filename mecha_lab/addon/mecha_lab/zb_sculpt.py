"""0.24.60 ZBrush-style sculpting: Sculpt Mode in the MECHA LAB tab gets ZBrush's names, keys and shelves (the user's
own ZBrush custom UI) on top of Blender's sculpt tools.  Nothing outside the MECHA LAB tab changes (every key and
button checks ``on()``), and Blender's own sculpt keys work again the moment you leave the tab.

Mouse (like ZBrush):
    drag on the model            sculpt with the brush            Alt: Zsub        Shift: Smooth
    drag on empty canvas         rotate (Shift: snap to a side)   Alt: move, let Alt go while dragging: zoom
    Ctrl + drag on the model     MaskPen                          Ctrl+Alt: unmask
    Ctrl + click empty           invert the mask                  Ctrl + lasso round the model: mask (Alt: unmask)
    Ctrl + drag on empty canvas  a mask: cleared; no mask: DynaMesh again (when the SubTool's DynaMesh is on)
    Alt + click another SubTool  it becomes the SubTool you sculpt
    Ctrl+Shift + click model     show only that polygroup         Ctrl+Shift + click empty: show all
    Ctrl+Shift + drag empty      show only what is inside         Ctrl+Shift+Alt: hide what is inside
Keys: Space / right-click = brush menu at the cursor, S / U / O = it with Draw Size / Z Intensity / Focal Shift under
the mouse, B = brushes (then the letters: B S T = Standard), X = symmetry, D / Shift+D = SDiv up / down,
Ctrl+D = Divide, Ctrl+W = polygroup from mask, F = frame, Shift+F = PolyF.

The ZBrush brushes are Blender's own Essentials brushes (Standard = Draw, ClayBuildup = Clay Strips,
DamStandard = Crease Sharp, Move = Grab ...); DynaMesh is Blender's voxel remesh by point count, ZRemesher is
Quadriflow, SDiv / Divide / Del Higher are Multires.
"""
from __future__ import annotations

import math
import os

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from mathutils import Matrix, Quaternion, Vector

ORANGE = (0.93, 0.47, 0.13, 1.0)
ORANGE_FILL = (0.70, 0.34, 0.09, 1.0)
LIB = 'brushes/essentials_brushes-mesh_sculpt.blend/Brush/'
MULTIRES = 'Multires'

# (ZBrush name, Blender Essentials brush, B-key letters)
BRUSHES = (
    ('Standard', 'Draw', 'ST'), ('Paint', 'Paint Hard', 'PA'), ('ClayBuildup', 'Clay Strips', 'CB'),
    ('Move', 'Grab', 'MV'), ('SnakeHook', 'Snake Hook', 'SK'), ('DamStandard', 'Crease Sharp', 'DS'),
    ('Layer', 'Layer', 'LA'), ('Clay', 'Clay', 'CL'), ('Inflat', 'Inflate/Deflate', 'IN'),
    ('ClayTubes', 'Clay Thumb', 'CT'), ('hPolish', 'Scrape/Fill', 'HP'), ('TrimDynamic', 'Trim', 'TD'),
    ('TrimAdaptive', 'Scrape Multiplane', 'TA'), ('Flatten', 'Flatten/Contrast', 'FL'), ('Planar', 'Plateau', 'PL'),
    ('sPolish', 'Relax Slide', 'SP'), ('Move Topological', 'Elastic Grab', 'MT'), ('Polish', 'Fill/Deepen', 'PO'),
    ('Smooth', 'Smooth', 'SM'), ('MaskPen', 'Mask', 'MP'), ('Pinch', 'Pinch/Magnify', 'PN'), ('Blob', 'Blob', 'BB'),
    ('Pose', 'Pose', 'PS'), ('Polygroupit', 'Face Set Paint', 'PG'),
)
BY_Z = {z: (z, bl, code) for z, bl, code in BRUSHES}
BY_BL = {bl: z for z, bl, _c in BRUSHES}
SHELF = (('Standard', 'Paint', 'ClayBuildup', 'Move', 'SnakeHook', 'DamStandard', 'Layer', 'Clay', 'Inflat',
          'ClayTubes'),
         ('hPolish', 'TrimDynamic', 'TrimAdaptive', 'Flatten', 'Planar', 'sPolish', 'Move Topological', 'Polish'))
# ZBrush stroke names -> Blender stroke methods
STROKES = (('FREEHAND', 'FreeHand', 'DOTS'), ('DOTS', 'Dots', 'SPACE'), ('DRAGDOT', 'DragDot', 'DRAG_DOT'),
           ('DRAGRECT', 'DragRect', 'ANCHORED'), ('SPRAY', 'Spray', 'AIRBRUSH'), ('LINE', 'LineII', 'LINE'),
           ('CURVE', 'Curve', 'CURVE'))
# Focal Shift -> Blender falloff preset (negative = harder / flatter, positive = softer / pointier)
FOCAL = ((-100, -61, 'CONSTANT', -80), (-60, -21, 'SPHERE', -40), (-20, 19, 'SMOOTH', 0), (20, 59, 'LIN', 40),
         (60, 100, 'SHARP', 80))
TOOLS = {'CLIP_CURVE': 'builtin.line_project', 'TRIM_CURVE': 'builtin.line_trim', 'TRIM_LASSO': 'builtin.lasso_trim',
         'DRAW': 'builtin.brush', 'MOVE': 'builtin.move', 'SCALE': 'builtin.scale', 'ROTATE': 'builtin.rotate'}


ZB_SUFFIX = ' (ZB)'          # (0.24.60 - 0.24.62 made "<brush> (ZB)" copies for alphas: still named by ZBrush name)


def bl_base(name):
    return name[:-len(ZB_SUFFIX)] if name.endswith(ZB_SUFFIX) else name


def icon_stem(bl_name):
    return 'zb_' + bl_base(bl_name).lower().replace('/', '_').replace(' ', '_')


# --- where it is on ----------------------------------------------------------------------------------------------

STYLE = ['ZBRUSH']          # (used when the add-on preferences cannot be read)


def style():
    """'ZBRUSH' or 'BLENDER': how the MECHA LAB tab is driven (the corner card / Preferences: Control Style)."""
    from .workspace_ui import prefs
    p = prefs()
    return getattr(p, 'control_style', STYLE[0]) if p is not None else STYLE[0]


def set_style(value):
    from .workspace_ui import prefs
    STYLE[0] = value
    p = prefs()
    if p is not None and hasattr(p, 'control_style'):
        p.control_style = value


def mecha_tab(context):
    from . import tool_state as ts
    try:
        return ts.is_mecha_workspace(getattr(context, 'workspace', None))
    except (AttributeError, ReferenceError):
        return False


def mecha_sculpt(context):
    """Sculpt Mode in the MECHA LAB tab (either style - the corner card shows)."""
    return getattr(context, 'mode', '') == 'SCULPT' and mecha_tab(context)


def on(context):
    """The ZBrush screen and keys: Sculpt Mode in the MECHA LAB tab with the ZBrush style."""
    try:
        return style() == 'ZBRUSH' and mecha_sculpt(context)
    except (AttributeError, ReferenceError):
        return False


def nav_on(context):
    """ZBrush navigation (canvas drag) in the MECHA LAB tab: Object or Sculpt Mode, ZBrush style."""
    try:
        return style() == 'ZBRUSH' and getattr(context, 'mode', '') in {'OBJECT', 'SCULPT'} and mecha_tab(context)
    except (AttributeError, ReferenceError):
        return False


def brush(context=None):
    context = context or bpy.context
    sc = getattr(getattr(context, 'tool_settings', None), 'sculpt', None)
    return getattr(sc, 'brush', None) if sc is not None else None


def unified(context=None):
    context = context or bpy.context
    ts = context.tool_settings
    sc = getattr(ts, 'sculpt', None)
    return getattr(sc, 'unified_paint_settings', None) or getattr(ts, 'unified_paint_settings', None)


def zb_name(b):
    if b is None:
        return ''
    base = bl_base(b.name)
    return BY_BL.get(base, base)


def activate(context, zname):
    """Make the Blender brush behind ZBrush's ``zname`` the sculpt brush; '' or an error text."""
    entry = BY_Z.get(zname)
    if entry is None:
        return f'Unknown brush {zname}'
    try:
        if _tool_id(context) != 'builtin.brush':
            bpy.ops.wm.tool_set_by_id(name='builtin.brush')
    except (AttributeError, RuntimeError, TypeError):
        pass
    try:                                         # (the brush keeps its alpha while Blender runs, like ZBrush)
        bpy.ops.brush.asset_activate(asset_library_type='ESSENTIALS', relative_asset_identifier=LIB + entry[1])
    except RuntimeError as ex:
        return str(ex).splitlines()[0]
    remember(zname)
    tune(brush(context), zname)
    return ''


# 0.24.60 ZBrush feel: the first time a brush is used in a file it gets ZBrush-like defaults (pen pressure on
# size and intensity, a close Dots spacing, ZBrush-ish strength / falloff); later changes are kept.
TUNE_ALL = {'use_pressure_strength': True, 'use_pressure_size': True, 'spacing': 5}
TUNE = {
    'Standard': {'strength': 0.5, 'curve_distance_falloff_preset': 'SMOOTH'},
    'ClayBuildup': {'strength': 0.55, 'spacing': 6},
    'Clay': {'strength': 0.5},
    'DamStandard': {'strength': 0.6},
    'Inflat': {'strength': 0.45},
    'Layer': {'strength': 0.5},
    'Move': {'strength': 1.0, 'use_pressure_size': False, 'use_pressure_strength': False},
    'Move Topological': {'strength': 1.0, 'use_pressure_size': False, 'use_pressure_strength': False},
    'SnakeHook': {'use_pressure_size': False},
    'Pose': {'use_pressure_size': False, 'use_pressure_strength': False},
    'Smooth': {'strength': 1.0, 'use_pressure_size': False},
    'sPolish': {'strength': 0.8},
    'hPolish': {'strength': 0.6}, 'Polish': {'strength': 0.5}, 'Flatten': {'strength': 0.6},
    'TrimDynamic': {'strength': 0.6}, 'TrimAdaptive': {'strength': 0.6}, 'Planar': {'strength': 0.6},
    'MaskPen': {'strength': 1.0, 'use_pressure_size': False},
}
TUNED_KEY = 'mch_zb_tuned'


def tune(b, zname):
    """ZBrush-like defaults on ``b`` once per file (True when it changed it)."""
    if b is None or b.get(TUNED_KEY):
        return False
    vals = dict(TUNE_ALL)
    vals.update(TUNE.get(zname, {}))
    for k, v in vals.items():
        if k == 'spacing' and getattr(b, 'stroke_method', 'SPACE') not in {'SPACE', 'LINE', 'CURVE'}:
            continue
        if k in b.bl_rna.properties and not b.bl_rna.properties[k].is_readonly:
            try:
                setattr(b, k, v)
            except (TypeError, ValueError, AttributeError):
                pass
    try:
        b[TUNED_KEY] = 1
    except (TypeError, AttributeError):
        pass
    return True


# --- alphas (ZBrush: an image that shapes the brush) --------------------------------------------------------------

ALPHA_DIR = os.path.join(os.path.dirname(__file__), 'alphas')
ALPHA_EXT = {'.png', '.psd', '.tif', '.tiff', '.jpg', '.jpeg', '.bmp', '.tga', '.exr'}
ZB_ALPHA_GLOBS = (r'C:\Program Files\Maxon ZBrush*\ZAlphas', r'C:\Program Files\Maxon\ZBrush*\ZAlphas',
                  r'C:\Program Files\Pixologic\ZBrush*\ZAlphas', '/Applications/Maxon ZBrush*/ZAlphas',
                  '/Applications/ZBrush*/ZAlphas')
_ALPHA_CACHE = {}
_ZB_DIRS = []


def zbrush_alpha_dir():
    """ZBrush's own alpha folder when ZBrush is installed here (read only), or ''."""
    if not _ZB_DIRS:
        import glob
        found = []
        for g in ZB_ALPHA_GLOBS:
            found += sorted(glob.glob(g))
        _ZB_DIRS.append(found[-1] if found else '')
    return _ZB_DIRS[0]


def alpha_folder(context):
    zb = context.scene.mch_zb
    if zb.alpha_source == 'ZBRUSH' and zbrush_alpha_dir():
        return zbrush_alpha_dir()
    if zb.alpha_source == 'FOLDER' and zb.alpha_dir:
        return bpy.path.abspath(zb.alpha_dir)
    return ALPHA_DIR


def alpha_files(context, limit=42):
    """The alpha images of the chosen folder (sorted, at most ``limit``; listed again every 2 s)."""
    return image_files(alpha_folder(context), limit)


def image_files(folder, limit=42):
    import time
    hit = _ALPHA_CACHE.get(folder)
    if hit is None or time.monotonic() - hit[0] > 2.0:
        try:
            names = sorted(f for f in os.listdir(folder) if os.path.splitext(f)[1].lower() in ALPHA_EXT)
        except OSError:
            names = []
        hit = (time.monotonic(), [os.path.join(folder, f) for f in names])
        _ALPHA_CACHE[folder] = hit
    return hit[1][:limit], len(hit[1])


def current_alpha(context):
    b = brush(context)
    tex = getattr(b, 'texture', None) if b is not None else None
    img = getattr(tex, 'image', None) if tex is not None else None
    return bpy.path.abspath(img.filepath) if img is not None else ''


INV = ' (Inv)'


def _alpha_lib_dir():
    """A folder of this add-on's own for the alpha texture files (Blender's extension user folder)."""
    try:
        return bpy.utils.extension_path_user(__package__, path='alpha_textures', create=True)
    except (AttributeError, ValueError, TypeError, OSError):
        return bpy.utils.user_resource('DATAFILES', path=os.path.join('mecha_lab', 'alpha_textures'), create=True)


def alpha_texture(path, inverted=False):
    """0.24.63 The alpha as an image texture linked from a small .blend of its own (made once per image in the
    add-on's folder).  Blender's Essentials brushes are linked data: they take a linked texture, never one made in
    this file - so the alpha goes on the brush you sculpt with, no brush copy, nothing new in your file."""
    import hashlib
    full = os.path.abspath(bpy.path.abspath(path))
    key = hashlib.sha1(os.path.normcase(full).encode('utf-8')).hexdigest()[:12]
    lib = os.path.join(_alpha_lib_dir(), f'alpha_{key}.blend')
    base = 'ZB Alpha ' + os.path.splitext(os.path.basename(full))[0]
    want = base + (INV if inverted else '')
    for t in bpy.data.textures:
        if t.library is not None and t.name == want and \
                os.path.normcase(bpy.path.abspath(t.library.filepath)) == os.path.normcase(lib):
            return t
    if not os.path.isfile(lib):
        img = bpy.data.images.load(full, check_existing=False)
        made = []
        try:
            img.name = base
            for name, inv in ((base, False), (base + INV, True)):
                t = bpy.data.textures.new(name, 'IMAGE')
                t.image = img
                t.extension = 'CLIP'
                if inv:                              # ZBrush Invr: white <-> black
                    t.use_color_ramp = True
                    els = t.color_ramp.elements
                    els[0].color = (1.0, 1.0, 1.0, 1.0)
                    els[-1].color = (0.0, 0.0, 0.0, 1.0)
                made.append(t)
            bpy.data.libraries.write(lib, set(made), path_remap='ABSOLUTE', fake_user=True)
        finally:                                     # (only the file on disk keeps them; this file stays as it was)
            for t in made:
                bpy.data.textures.remove(t)
            bpy.data.images.remove(img)
    with bpy.data.libraries.load(lib, link=True) as (_src, dst):
        dst.textures = [want]
    return dst.textures[0]


def set_alpha(context, path):
    """The brush's alpha (Blender: an image brush texture from the view) - '' = Alpha Off."""
    b = brush(context)
    if b is None:
        return 'No brush'
    if not path:
        if b.texture is not None:
            b.texture = None
        return 'Alpha Off'
    try:
        tex = alpha_texture(path)
    except (RuntimeError, OSError) as ex:
        return 'Alpha: ' + str(ex).splitlines()[0]
    b.texture = tex
    if b.texture != tex:
        return 'Alpha: Blender did not take it on this brush'
    slot = b.texture_slot
    for mode in ('VIEW_PLANE', 'AREA_PLANE'):     # 0.24.61 from the view, like a ZBrush alpha
        try:
            slot.map_mode = mode
            break
        except (TypeError, ValueError):
            continue
    for attr, v in (('use_rake', False), ('use_random', False)):
        if hasattr(slot, attr):
            setattr(slot, attr, v)
    if hasattr(b, 'use_primary_overlay'):         # the alpha shows in the brush circle
        b.use_primary_overlay = True
        b.texture_overlay_alpha = 40
    return 'Alpha ' + os.path.splitext(os.path.basename(path))[0]


def alpha_edit(context, action):
    """Flip H / Flip V / Rotate 90 / Invert the brush alpha (ZBrush's alpha buttons)."""
    b = brush(context)
    tex = getattr(b, 'texture', None) if b is not None else None
    if tex is None:
        return 'Pick an alpha first'
    slot = b.texture_slot
    if action == 'FLIP_H':
        slot.scale[0] = -slot.scale[0]
    elif action == 'FLIP_V':
        slot.scale[1] = -slot.scale[1]
    elif action == 'ROTATE':
        slot.angle = (slot.angle + math.pi / 2) % (2 * math.pi)
    elif action == 'INVERT':
        path = current_alpha(context)
        if path:                                     # (the inverted twin from the same alpha file)
            b.texture = alpha_texture(path, inverted=not tex.name.endswith(INV))
    return {'FLIP_H': 'Flip H', 'FLIP_V': 'Flip V', 'ROTATE': 'Rotate', 'INVERT': 'Invert'}.get(action, action)


# --- textures (ZBrush Texture: a colour image the Paint brush stamps, DragRect) -----------------------------------

TEXTURE_DIR = os.path.join(os.path.dirname(__file__), 'textures')
ZB_TEXTURE_GLOBS = tuple(g.replace('ZAlphas', 'ZTextures') for g in ZB_ALPHA_GLOBS)
_ZB_TEX_DIRS = []
_TEX_PIX = {}


def zbrush_texture_dir():
    """ZBrush's own texture folder when ZBrush is installed here (read only), or ''."""
    if not _ZB_TEX_DIRS:
        import glob
        found = []
        for g in ZB_TEXTURE_GLOBS:
            found += sorted(glob.glob(g))
        _ZB_TEX_DIRS.append(found[-1] if found else '')
    return _ZB_TEX_DIRS[0]


def texture_folder(context):
    zb = context.scene.mch_zb
    if zb.tex_source == 'ZBRUSH' and zbrush_texture_dir():
        return zbrush_texture_dir()
    if zb.tex_source == 'FOLDER' and zb.tex_dir:
        return bpy.path.abspath(zb.tex_dir)
    return TEXTURE_DIR


def texture_files(context, limit=42):
    return image_files(texture_folder(context), limit)


def current_texture(context):
    p = bpy.path.abspath(context.scene.mch_zb.texture) if context.scene.mch_zb.texture else ''
    return p if p and os.path.isfile(p) else ''


def stamp_ready(context):
    """A Texture is on and the brush is Paint: a press on the model stamps the texture (DragRect)."""
    return bool(current_texture(context)) and zb_name(brush(context)) == 'Paint'


def set_texture(context, path):
    """ZBrush Texture ('' = Texture Off).  Picking one takes the Paint brush, which stamps it."""
    zb = context.scene.mch_zb
    zb.texture = path or ''
    if not path:
        return 'Texture Off'
    name = os.path.splitext(os.path.basename(path))[0]
    if zb_name(brush(context)) != 'Paint':
        if activate(context, 'Paint'):
            return f'Texture {name}: pick the Paint brush to stamp it'
    return f'Texture {name}: drag on the model with Paint to stamp it'


def texture_pixels(path, max_size=2048):
    """(h, w, 4) float32 sRGB pixels of an image file (read once; again when the file changes) or None."""
    import numpy as np
    path = bpy.path.abspath(path)
    try:
        mtime = os.path.getmtime(path)
    except OSError:
        return None
    hit = _TEX_PIX.get(path)
    if hit is not None and hit[0] == mtime:
        return hit[1]
    try:
        img = bpy.data.images.load(path, check_existing=False)
    except RuntimeError:
        return None
    try:
        w, h = img.size
        if max(w, h) > max_size:
            f = max_size / float(max(w, h))
            img.scale(max(1, int(w * f)), max(1, int(h * f)))
            w, h = img.size
        px = np.empty(w * h * 4, dtype=np.float32)
        img.pixels.foreach_get(px)
        px = px.reshape(h, w, 4)
        if img.is_float:                     # (a float image is linear: to sRGB like the 8-bit ones)
            c = np.clip(px[..., :3], 0.0, 1.0)
            px[..., :3] = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
    finally:
        bpy.data.images.remove(img)         # nothing stays in the user's file
    _TEX_PIX.clear()
    _TEX_PIX[path] = (mtime, px)
    return px


def _color_layer(me):
    att = me.color_attributes.active_color
    if att is None:
        import numpy as np
        att = me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
        att.data.foreach_set('color', np.ones(len(att.data) * 4, dtype=np.float32))
        me.color_attributes.active_color = att
        try:
            me.color_attributes.render_color_index = me.color_attributes.active_color_index
        except (AttributeError, TypeError):
            pass
    return att


def stamp_rect(center, half, angle, aspect):
    """The four corners (region px) of a DragRect stamp: centre, half width, turn, image height / width."""
    cx, cy = center
    ca, sa = math.cos(angle), math.sin(angle)
    hw, hh = half, half * aspect
    return [(cx + x * ca - y * sa, cy + x * sa + y * ca) for x, y in ((-hw, -hh), (hw, -hh), (hw, hh), (-hw, hh))]


def texture_stamp(ob, px, matrix, width, height, center, half, angle, view, strength=1.0, mirrors=((1, 1, 1),)):
    """Stamp the texture ``px`` ((h, w, 4) sRGB, alpha = how much) on ``ob``'s colour, ZBrush DragRect style.
    ``matrix`` = perspective matrix x object matrix, ``center`` / ``half`` / ``angle`` in region px, ``view`` =
    ('ORTHO', view direction) or ('PERSP', eye) in world space: only points facing the view take colour.  The
    mask keeps points as they are.  ``mirrors``: symmetry - (sx, sy, sz) sign sets, (1, 1, 1) = the stamp itself.
    Returns how many points it coloured."""
    import numpy as np
    me = ob.data
    n = len(me.vertices)
    if n == 0 or half <= 0.0 or px is None:
        return 0
    att = _color_layer(me)
    co = np.empty(n * 3, dtype=np.float64)
    nrm = np.empty(n * 3, dtype=np.float64)
    me.vertices.foreach_get('co', co)
    me.vertices.foreach_get('normal', nrm)
    co, nrm = co.reshape(-1, 3), nrm.reshape(-1, 3)
    mask = _mask_values(ob).astype(np.float64)
    mw = np.array(ob.matrix_world, dtype=np.float64)
    m = np.array(matrix, dtype=np.float64)
    nmat = np.linalg.inv(mw[:3, :3]).T
    ih, iw = px.shape[:2]
    ca, sa = math.cos(-angle), math.sin(-angle)
    hw, hh = half, half * ih / float(iw)
    weight = np.zeros(n)
    color = np.zeros((n, 3))
    for sx, sy, sz in mirrors:               # each point looks where its mirror twin is on screen
        sgn = np.array((sx, sy, sz), dtype=np.float64)
        c = co * sgn
        world = c @ mw[:3, :3].T + mw[:3, 3]
        nw = (nrm * sgn) @ nmat.T
        vd = np.broadcast_to(np.array(view[1], dtype=np.float64), world.shape) if view[0] == 'ORTHO' \
            else world - np.array(view[1], dtype=np.float64)
        facing = (nw * vd).sum(axis=1) < 0.0
        h4 = np.hstack([c, np.ones((n, 1))]) @ m.T
        ok = h4[:, 3] > 1e-9
        w4 = np.where(ok, h4[:, 3], 1.0)
        dx = (h4[:, 0] / w4 + 1.0) * 0.5 * width - center[0]
        dy = (h4[:, 1] / w4 + 1.0) * 0.5 * height - center[1]
        u = (dx * ca - dy * sa) / (2.0 * hw) + 0.5
        v = (dx * sa + dy * ca) / (2.0 * hh) + 0.5
        idx = np.nonzero(ok & facing & (u >= 0.0) & (u < 1.0) & (v >= 0.0) & (v < 1.0))[0]
        if not len(idx):
            continue
        tex = px[np.clip((v[idx] * ih).astype(int), 0, ih - 1), np.clip((u[idx] * iw).astype(int), 0, iw - 1)]
        wt = tex[:, 3] * strength
        better = wt > weight[idx]            # (overlapping mirror stamps: the stronger one)
        idx, wt, tex = idx[better], wt[better], tex[better]
        weight[idx] = wt
        color[idx] = tex[:, :3]
    weight *= 1.0 - np.clip(mask, 0.0, 1.0)
    hit = weight > 0.0
    if not hit.any():
        return 0
    if att.domain == 'POINT':
        wv, cv = weight, color
    else:                                    # a face corner layer: each corner takes its point's stamp
        lv = np.empty(len(me.loops), dtype=np.int64)
        me.loops.foreach_get('vertex_index', lv)
        wv, cv = weight[lv], color[lv]
    cur = np.empty(len(att.data) * 4, dtype=np.float32)
    att.data.foreach_get('color_srgb', cur)
    cur = cur.reshape(-1, 4)
    cur[:, :3] = cur[:, :3] * (1.0 - wv[:, None]) + cv * wv[:, None]
    att.data.foreach_set('color_srgb', cur.ravel())
    me.update()
    return int(hit.sum())


def stamp_mirrors(context):
    """The symmetry sign sets for a stamp (X / Y / Z symmetry on: its mirror stamps too)."""
    sc = context.tool_settings.sculpt
    axes = [getattr(sc, f'use_symmetry_{a}', False) for a in 'xyz']
    out = [(1, 1, 1)]
    for i, on_ in enumerate(axes):
        if on_:
            out += [tuple(-s if j == i else s for j, s in enumerate(m)) for m in out]
    return tuple(out)


def apply_stamp(context, center, half, angle):
    """Texture stamp on the SubTool from the view (the Ctrl+Z step: Blender's colour filter, zero strength)."""
    ob = context.active_object
    if ob is None or ob.type != 'MESH':
        return 'Texture stamp: no SubTool'
    px = texture_pixels(current_texture(context))
    if px is None:
        return 'Texture stamp: the texture cannot be read'
    region, rv3d = context.region, context.region_data
    if rv3d.is_perspective:
        view = ('PERSP', tuple(rv3d.view_matrix.inverted().translation))
    else:
        view = ('ORTHO', tuple(rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))))
    if ob.data.color_attributes.active_color is not None and not bpy.app.background:
        try:                                 # stores the colours before the stamp: one Ctrl+Z takes it back
            bpy.ops.sculpt.color_filter('EXEC_DEFAULT', True, type='FILL', strength=0.0, fill_color=(1.0, 1.0, 1.0))
        except (RuntimeError, TypeError):
            pass
    n = texture_stamp(ob, px, rv3d.perspective_matrix @ ob.matrix_world, region.width, region.height, center, half,
                      angle, view, context.scene.mch_zb.rgb_int / 100.0, stamp_mirrors(context))
    from .quick_hud import points_text
    return f'Texture stamp: {points_text(n)} points' if n else 'Texture stamp: nothing under it'


_STAMP = {'rect': None, 'path': '', 'handle': None}


def _stamp_draw():
    try:
        rect = _STAMP['rect']
        if rect:
            from . import ui_gpu as G
            G.image_quad(_STAMP['path'], rect, 0.55)
            G.polyline(rect, ORANGE, 1.5, closed=True)
    except Exception:          # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


def stamp_show(rect, path):
    _STAMP['rect'], _STAMP['path'] = rect, path
    if _STAMP['handle'] is None and not bpy.app.background:
        _STAMP['handle'] = bpy.types.SpaceView3D.draw_handler_add(_stamp_draw, (), 'WINDOW', 'POST_PIXEL')


def stamp_hide():
    _STAMP['rect'] = None
    if _STAMP['handle'] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_STAMP['handle'], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _STAMP['handle'] = None


RECENT = []                 # the last brushes used (the Space menu shows them)


def remember(zname):
    if zname in RECENT:
        RECENT.remove(zname)
    RECENT.insert(0, zname)
    del RECENT[6:]


def multires(ob):
    if ob is None:
        return None
    return next((m for m in ob.modifiers if m.type == 'MULTIRES'), None)


def space(context=None):
    context = context or bpy.context
    sp = getattr(context, 'space_data', None)
    if sp is not None and sp.type == 'VIEW_3D':
        return sp
    area = getattr(context, 'area', None)
    if area is not None and area.type == 'VIEW_3D':
        return area.spaces.active
    for win in getattr(context.window_manager, 'windows', []):
        for a in win.screen.areas:
            if a.type == 'VIEW_3D':
                return a.spaces.active
    return None


# --- ZBrush-named settings (they read / write the Blender brush and view settings) --------------------------------

def _safe(fn, default):
    try:
        return fn()
    except (AttributeError, ReferenceError, TypeError, ValueError, IndexError, KeyError, RuntimeError):
        return default


def _size_get(self):
    def f():
        u, b = unified(), brush()
        return int(u.size if u is not None and u.use_unified_size else b.size)
    return _safe(f, 50)


def _size_set(self, v):
    def f():
        u, b = unified(), brush()
        if u is not None and u.use_unified_size:
            u.size = int(v)
        else:
            b.size = int(v)
    _safe(f, None)


def _int_get(self):
    def f():
        u, b = unified(), brush()
        s = u.strength if u is not None and u.use_unified_strength else b.strength
        return int(round(s * 100))
    return _safe(f, 50)


def _int_set(self, v):
    def f():
        u, b = unified(), brush()
        if u is not None and u.use_unified_strength:
            u.strength = v / 100.0
        else:
            b.strength = v / 100.0
    _safe(f, None)


FOCAL_KEY = 'mch_focal'


def zb_falloff(t, fs):
    """0.24.61 ZBrush's brush profile at ``t`` (0 = centre, 1 = edge) for Focal Shift ``fs`` (-100 .. 100):
    0 = a soft bell, minus = a flat top with a firmer edge, plus = pointier."""
    t = min(max(float(t), 0.0), 1.0)
    u = t
    if fs < 0:
        c = -fs / 100.0 * 0.85                       # the flat core grows with minus Focal Shift
        if t <= c:
            return 1.0
        u = (t - c) / (1.0 - c)
    s = 1.0 - u
    v = s * s * (3.0 - 2.0 * s)
    if fs > 0:
        v = v ** (1.0 + fs / 25.0)
    return v


def set_focal_curve(b, fs, n=13):
    """The brush falloff as a custom curve following ZBrush's Focal Shift (every value, not 5 presets)."""
    fs = int(max(-100, min(100, fs)))
    b.curve_distance_falloff_preset = 'CUSTOM'
    cm = b.curve_distance_falloff
    pts = cm.curves[0].points
    xs = [i / (n - 1.0) for i in range(n)]
    if fs < 0:
        xs = sorted(set(xs + [round(-fs / 100.0 * 0.85, 4)]))
    while len(pts) > 2:
        pts.remove(pts[1])
    pts[0].location = (0.0, zb_falloff(0.0, fs))
    pts[-1].location = (1.0, zb_falloff(1.0, fs))
    for x in xs[1:-1]:
        pts.new(x, zb_falloff(x, fs))
    for p in pts:
        p.handle_type = 'AUTO_CLAMPED'
    cm.update()
    b[FOCAL_KEY] = fs


def _focal_get(self):
    def f():
        b = brush()
        if b.curve_distance_falloff_preset == 'CUSTOM' and FOCAL_KEY in b.keys():
            return int(b[FOCAL_KEY])
        for _lo, _hi, p, mid in FOCAL:               # (a Blender preset: the Focal Shift nearest to it)
            if p == b.curve_distance_falloff_preset:
                return mid
        return 0
    return _safe(f, 0)


def _focal_set(self, v):
    _safe(lambda: set_focal_curve(brush(), v), None)


def _zmode_get(self):
    def f():
        b = brush()
        items = [i.identifier for i in b.bl_rna.properties['direction'].enum_items]
        return 1 if len(items) > 1 and b.direction == items[1] else 0
    return _safe(f, 0)


def _zmode_set(self, v):
    def f():
        b = brush()
        items = [i.identifier for i in b.bl_rna.properties['direction'].enum_items]
        if len(items) > 1:
            b.direction = items[1 if v else 0]
    _safe(f, None)


def _brush_bool(attr):
    def get(self):
        return _safe(lambda: bool(getattr(brush(), attr)), False)

    def set_(self, v):
        _safe(lambda: setattr(brush(), attr, bool(v)), None)
    return get, set_


STEP_KEY, SPACING_KEY = 'mch_lazy_step', 'mch_spacing0'


def _lazy_smooth_get(self):
    return _safe(lambda: max(0.0, min(1.0, (brush().smooth_stroke_factor - 0.5) / 0.49)), 0.25)


def _lazy_smooth_set(self, v):
    _safe(lambda: setattr(brush(), 'smooth_stroke_factor', 0.5 + 0.49 * max(0.0, min(1.0, v))), None)


def _lazy_step_get(self):
    """0.24.61 ZBrush LazyStep: the distance between the dots with LazyMouse on (0.05 = close, 1 = a dot every
    Draw Size) - Blender brush Spacing."""
    def f():
        b = brush()
        return float(b[STEP_KEY]) if STEP_KEY in b.keys() else b.spacing / 100.0
    return _safe(f, 0.05)


def _lazy_step_set(self, v):
    def f():
        b = brush()
        b[STEP_KEY] = float(v)
        if b.use_smooth_stroke:
            b.spacing = max(1, int(round(v * 100)))
    _safe(f, None)


def _lazy_mouse_get(self):
    return _safe(lambda: bool(brush().use_smooth_stroke), False)


def _lazy_mouse_set(self, v):
    """LazyMouse on: Blender's stroke stabilizer, and the dots LazyStep apart; off: the spacing it had."""
    def f():
        b = brush()
        if v and not b.use_smooth_stroke:
            b[SPACING_KEY] = int(b.spacing)
            if STEP_KEY in b.keys():
                b.spacing = max(1, int(round(float(b[STEP_KEY]) * 100)))
        elif not v and b.use_smooth_stroke and SPACING_KEY in b.keys():
            b.spacing = int(b[SPACING_KEY])
        b.use_smooth_stroke = bool(v)
    _safe(f, None)


def _highpoly_get(self):
    from . import zb_highpoly
    return zb_highpoly.pref_on()


def _highpoly_set(self, v):
    from . import zb_highpoly
    zb_highpoly.set_pref(v)
    _safe(lambda: zb_highpoly.update(bpy.context), None)


def _lazy_radius_get(self):
    return _safe(lambda: int(brush().smooth_stroke_radius), 75)


def _lazy_radius_set(self, v):
    _safe(lambda: setattr(brush(), 'smooth_stroke_radius', int(v)), None)


def _dynamic_get(self):
    def f():
        u, b = unified(), brush()
        src = u if u is not None and u.use_unified_size and hasattr(u, 'use_locked_size') else b
        return src.use_locked_size == 'SCENE'
    return _safe(f, False)


def _dynamic_set(self, v):
    def f():
        u, b = unified(), brush()
        src = u if u is not None and u.use_unified_size and hasattr(u, 'use_locked_size') else b
        src.use_locked_size = 'SCENE' if v else 'VIEW'
    _safe(f, None)


def _stroke_get(self):
    def f():
        m = brush().stroke_method
        return next(i for i, (_k, _n, bl) in enumerate(STROKES) if bl == m)
    return _safe(f, 1)


def _stroke_set(self, v):
    _safe(lambda: setattr(brush(), 'stroke_method', STROKES[v][2]), None)


def _sym(axis):
    def get(self):
        return _safe(lambda: bool(getattr(bpy.context.tool_settings.sculpt, 'use_symmetry_' + axis)), False)

    def set_(self, v):
        _safe(lambda: setattr(bpy.context.tool_settings.sculpt, 'use_symmetry_' + axis, bool(v)), None)
    return get, set_


def _radial_axis():
    sc = bpy.context.tool_settings.sculpt
    return next((i for i, a in enumerate('xyz') if getattr(sc, 'use_symmetry_' + a)), 0)


def _radial_get(self):
    return _safe(lambda: max(bpy.context.active_object.data.radial_symmetry) > 1, False)


def _radial_set(self, v):
    def f():
        me = bpy.context.active_object.data
        r = [1, 1, 1]
        if v:
            r[_radial_axis()] = max(2, int(self.radial_count))
        me.radial_symmetry = r
    _safe(f, None)


def _rcount_set(self, v):
    self['radial_count'] = int(v)
    if _radial_get(self):
        _radial_set(self, True)


def _rcount_get(self):
    return int(self.get('radial_count', 8))


def _sdiv_get(self):
    return _safe(lambda: int(multires(bpy.context.active_object).sculpt_levels), 0)


def _sdiv_set(self, v):
    def f():
        m = multires(bpy.context.active_object)
        v2 = max(0, min(int(v), m.total_levels))
        m.sculpt_levels = v2
        m.levels = v2
    _safe(f, None)


def _view_bool(path, invert=False):
    def get(self):
        def f():
            obj = space()
            for p in path[:-1]:
                obj = getattr(obj, p)
            return bool(getattr(obj, path[-1])) != invert
        return _safe(f, False)

    def set_(self, v):
        def f():
            obj = space()
            for p in path[:-1]:
                obj = getattr(obj, p)
            setattr(obj, path[-1], bool(v) != invert)
        _safe(f, None)
    return get, set_


def _persp_get(self):
    return _safe(lambda: space().region_3d.view_perspective == 'PERSP', True)


def _persp_set(self, v):
    _safe(lambda: setattr(space().region_3d, 'view_perspective', 'PERSP' if v else 'ORTHO'), None)


def _polyf_get(self):
    return _safe(lambda: bool(space().overlay.show_wireframes), False)


def _polyf_set(self, v):
    def f():
        ov = space().overlay
        ov.show_wireframes = bool(v)
        if hasattr(ov, 'show_sculpt_face_sets'):
            ov.show_sculpt_face_sets = bool(v)
    _safe(f, None)


def _matcap_items(self, context):
    try:
        lights = [l.name for l in context.preferences.studio_lights if l.type == 'MATCAP']
    except (AttributeError, ReferenceError):
        lights = []
    _MATCAPS[:] = [(n, n.rsplit('.', 1)[0].replace('_', ' ').title(), '') for n in lights] or [('NONE', 'None', '')]
    return _MATCAPS


_MATCAPS = []


def matcaps(context):
    """(identifier, name, image file) of each MatCap Blender has - the ZBrush Material picker."""
    out = []
    try:
        for l in context.preferences.studio_lights:
            if l.type == 'MATCAP':
                out.append((l.name, l.name.rsplit('.', 1)[0].replace('_', ' ').title(), getattr(l, 'path', '')))
    except (AttributeError, ReferenceError):
        pass
    return out


def stroke_icon(key):
    return 'png:zb_stroke_' + key.lower()


def _matcap_get(self):
    def f():
        sh = space().shading
        names = [i[0] for i in _MATCAPS] or [i[0] for i in _matcap_items(self, bpy.context)]
        return names.index(sh.studio_light) if sh.light == 'MATCAP' and sh.studio_light in names else 0
    return _safe(f, 0)


def _matcap_set(self, v):
    def f():
        sh = space().shading
        names = [i[0] for i in _MATCAPS] or [i[0] for i in _matcap_items(self, bpy.context)]
        sh.type = 'SOLID'
        sh.light = 'MATCAP'
        sh.studio_light = names[v]
    _safe(f, None)


_bf = _brush_bool('use_frontface')
_sx, _sy, _sz = _sym('x'), _sym('y'), _sym('z')
_floor = _view_bool(('overlay', 'show_floor'))
_transp = _view_bool(('shading', 'show_xray'))
_double = _view_bool(('shading', 'show_backface_culling'), invert=True)


def automask_settings(context=None):
    """Where Blender keeps the sculpt auto masking (5.2: Sculpt.mesh_automasking_settings; 5.0: Sculpt itself)."""
    sc = (context or bpy.context).tool_settings.sculpt
    return getattr(sc, 'mesh_automasking_settings', None) or sc


def _cav_get(self):
    return _safe(lambda: bool(automask_settings().use_automasking_cavity), False)


def _cav_set(self, v):
    _safe(lambda: setattr(automask_settings(), 'use_automasking_cavity', bool(v)), None)


_cav = (_cav_get, _cav_set)


class MCH_PG_ZBrush(bpy.types.PropertyGroup):
    draw_size: IntProperty(name='Draw Size', min=1, max=2000, soft_max=400, get=_size_get, set=_size_set,
                           description='Brush radius in pixels (Blender Radius)')
    z_intensity: IntProperty(name='Z Intensity', min=0, max=100, get=_int_get, set=_int_set,
                             description='How strong the brush is (Blender Strength x 100)')
    focal_shift: IntProperty(name='Focal Shift', min=-100, max=100, get=_focal_get, set=_focal_set,
                             description='Brush falloff: negative = harder, flatter; positive = softer, pointier '
                                         '(Blender Falloff preset Constant / Sphere / Smooth / Linear / Sharp)')
    zmode: EnumProperty(name='Z Mode', items=[('ZADD', 'Zadd', 'Add (Blender Direction +)'),
                                              ('ZSUB', 'Zsub', 'Subtract (Blender Direction -)')],
                        get=_zmode_get, set=_zmode_set)
    backface_mask: BoolProperty(name='BackfaceMask', get=_bf[0], set=_bf[1],
                                description='Do not sculpt the far side (Blender Front Faces Only)')
    lazy_mouse: BoolProperty(name='LazyMouse', get=_lazy_mouse_get, set=_lazy_mouse_set,
                             description='The stroke trails the pen (Blender Stabilize Stroke)')
    lazy_step: FloatProperty(name='LazyStep', min=0.01, max=2.0, get=_lazy_step_get, set=_lazy_step_set,
                             description='LazyMouse on: how far apart the dots are (0.05 close, 1 = a dot every '
                                         'Draw Size) - stitches and rivets with an alpha (Blender Spacing)')
    lazy_smooth: FloatProperty(name='LazySmooth', min=0.0, max=1.0, get=_lazy_smooth_get, set=_lazy_smooth_set,
                               description='How smooth the trailing stroke is (Blender Stabilize Factor)')
    highpoly: BoolProperty(name='HiPoly', get=_highpoly_get, set=_highpoly_set,
                           description='High Poly Mode: Blender Sculpt Deform Only + Delay Viewport Updates and the '
                                       'heavy viewport extras off while the ZBrush screen is on (all put back after)')
    lazy_radius: IntProperty(name='LazyRadius', min=1, max=200, get=_lazy_radius_get, set=_lazy_radius_set,
                             description='Trail length in pixels (Blender Stabilize Radius)')
    dynamic: BoolProperty(name='Dynamic', get=_dynamic_get, set=_dynamic_set,
                          description='Brush size goes with the model when you zoom (Blender Radius Unit: Scene)')
    stroke: EnumProperty(name='Stroke', items=[(k, n, f'Blender: {bl.replace("_", " ").title()}', i)
                                               for i, (k, n, bl) in enumerate(STROKES)],
                         get=_stroke_get, set=_stroke_set)
    sym_x: BoolProperty(name='>X<', get=_sx[0], set=_sx[1], description='Mirror the stroke across X')
    sym_y: BoolProperty(name='>Y<', get=_sy[0], set=_sy[1], description='Mirror the stroke across Y')
    sym_z: BoolProperty(name='>Z<', get=_sz[0], set=_sz[1], description='Mirror the stroke across Z')
    radial: BoolProperty(name='(R)', get=_radial_get, set=_radial_set,
                         description='Radial symmetry round the symmetry axis (RadialCount copies)')
    radial_count: IntProperty(name='RadialCount', min=2, max=64, default=8, get=_rcount_get, set=_rcount_set)
    sdiv: IntProperty(name='SDiv', min=0, max=12, get=_sdiv_get, set=_sdiv_set,
                      description='Subdivision level you sculpt on (Blender Multires Sculpt level)')
    persp: BoolProperty(name='Persp', get=_persp_get, set=_persp_set, description='Perspective view')
    floor: BoolProperty(name='Floor', get=_floor[0], set=_floor[1], description='Show the floor grid')
    polyf: BoolProperty(name='PolyF', get=_polyf_get, set=_polyf_set,
                        description='Show the polygons and polygroups (wireframe + face sets)')
    transp: BoolProperty(name='Transp', get=_transp[0], set=_transp[1], description='See through (X-Ray)')
    double: BoolProperty(name='Double', get=_double[0], set=_double[1],
                         description='Show both sides of faces (Backface Culling off)')
    matcap: EnumProperty(name='Material', items=_matcap_items, get=_matcap_get, set=_matcap_set)
    # stored settings (this file)
    points: IntProperty(name='Points', default=20000, min=200, soft_max=2000000,
                        description='DynaMesh: about how many points the remeshed SubTool gets (Active Points Count)')
    target_polys: FloatProperty(name='Target Polygons Count', default=5.0, min=0.1, soft_max=100.0, precision=1,
                                description='ZRemesher: how many polygons, in thousands (5 = 5,000)')
    keep_creases: BoolProperty(name='KeepCreases', default=True, description='ZRemesher keeps sharp edges')
    keep_border: BoolProperty(name='KeepBorder', default=True, description='ZRemesher keeps open borders')
    decimate: IntProperty(name='% of decimation', default=20, min=1, max=99, subtype='PERCENTAGE',
                          description='Decimate Current keeps this many percent of the polygons')
    inflate: IntProperty(name='Inflate', default=10, min=-100, max=100,
                         description='Deformation: how far Inflate pushes the surface out (minus = in)')
    thick: FloatProperty(name='Thick', default=0.02, min=0.0, soft_max=0.5, precision=3,
                         description='Extract: thickness of the new shell')
    blur: IntProperty(name='Blur', default=2, min=0, max=20, description='Mask By Cavity: how often it is blurred')
    cavity_int: IntProperty(name='Intensity', default=50, min=0, max=100,
                            description='Mask By Cavity: how deep a dent has to be to get masked (Blender Factor)')
    cavity_inv: BoolProperty(name='Inv', default=False,
                             description='Mask By Cavity: mask the ridges instead of the dents')
    cavity_auto: BoolProperty(name='CavityMask', get=_cav[0], set=_cav[1],
                              description='Brush Auto Masking: the brush only works in the dents '
                                          '(Blender Auto-Masking Cavity)')
    res: IntProperty(name='Res', default=4, min=1, max=64, description='QCube / QGrid resolution')
    alpha_source: EnumProperty(name='Alphas', default='MECHA', items=[
        ('MECHA', 'Mecha', 'The alphas that come with Mecha Lab'),
        ('ZBRUSH', 'ZBrush', 'ZBrush\'s own ZAlphas folder (when ZBrush is installed - only read)'),
        ('FOLDER', 'Folder', 'Your own alpha folder')])
    alpha_dir: StringProperty(name='Alpha Folder', subtype='DIR_PATH', default='',
                              description='A folder of alpha images (PNG / PSD / TIF ...)')
    texture: StringProperty(name='Texture', subtype='FILE_PATH', default='',
                            description='ZBrush Texture: the colour image the Paint brush stamps (empty = Texture Off)')
    tex_source: EnumProperty(name='Textures', default='MECHA', items=[
        ('MECHA', 'Mecha', 'The textures that come with Mecha Lab'),
        ('ZBRUSH', 'ZBrush', 'ZBrush\'s own ZTextures folder (when ZBrush is installed - only read)'),
        ('FOLDER', 'Folder', 'Your own texture folder')])
    tex_dir: StringProperty(name='Texture Folder', subtype='DIR_PATH', default='',
                            description='A folder of texture images (PNG / JPG / TIF ...)')
    rgb_int: IntProperty(name='Rgb Intensity', default=100, min=0, max=100,
                         description='How strongly a texture stamp (or the paint) covers the colour underneath')
    fbx_scope: EnumProperty(name='Export', default='SELECTED', items=[
        ('VISIBLE', 'Visible', 'FBX / OBJ / STL export: every visible SubTool'),
        ('SELECTED', 'Selected', 'FBX / OBJ / STL export: the selected SubTool(s)')])


# --- actions ------------------------------------------------------------------------------------------------------

def _mode(context, mode):
    ob = context.active_object
    if ob is not None and ob.mode != mode:
        bpy.ops.object.mode_set(mode=mode)


def switch_to(context, ob):
    """Make ``ob`` the SubTool being sculpted (Sculpt Mode moves to it)."""
    if ob is None or ob.type != 'MESH':
        return False
    if ob.name not in context.view_layer.objects:
        context.view_layer.update()
        if ob.name not in context.view_layer.objects:
            return False
    was = context.mode
    _mode(context, 'OBJECT')
    for o in context.selected_objects:
        o.select_set(False)
    if ob.hide_get():
        ob.hide_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    if was == 'SCULPT':
        _mode(context, 'SCULPT')
    return True


def _new_object(context, me, name, like=None):
    ob = bpy.data.objects.new(name, me)
    coll = like.users_collection[0] if like is not None and like.users_collection else context.collection
    coll.objects.link(ob)
    if like is not None:
        ob.matrix_world = like.matrix_world.copy()
    return ob


def _bm_edit(context, ob, fn):
    """Run ``fn(bm)`` on the mesh of ``ob`` in Object Mode, then back to Sculpt Mode."""
    import bmesh
    _mode(context, 'OBJECT')
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    out = fn(bm)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    _mode(context, 'SCULPT')
    return out


def _split_faces(context, ob, pick, name):
    """New SubTool from the faces ``pick(face)`` says yes to, taken out of ``ob``; the new object or None."""
    import bmesh
    _mode(context, 'OBJECT')
    me = ob.data
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.index_update()
    bm.faces.index_update()
    take = [f for f in bm.faces if pick(bm, f)]
    if not take or len(take) == len(bm.faces):
        bm.free()
        _mode(context, 'SCULPT')
        return None
    part = bm.copy()
    part.faces.index_update()
    keep_idx = {f.index for f in take}
    bmesh.ops.delete(part, geom=[f for f in part.faces if f.index not in keep_idx], context='FACES')
    bmesh.ops.delete(bm, geom=take, context='FACES')
    bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
    bm.to_mesh(me)
    bm.free()
    new_me = bpy.data.meshes.new(ob.name + '_' + name)
    part.to_mesh(new_me)
    part.free()
    for mat in me.materials:
        new_me.materials.append(mat)
    new = _new_object(context, new_me, ob.name + '_' + name, ob)
    _mode(context, 'SCULPT')
    return new


def _face_layer(bm, name):
    return bm.faces.layers.int.get(name)


def _ensure_multires(ob):
    m = multires(ob)
    if m is None:
        m = ob.modifiers.new(MULTIRES, 'MULTIRES')
    return m


def _divide(context, ob, times=1):
    m = _ensure_multires(ob)
    for _i in range(times):
        bpy.ops.object.multires_subdivide(modifier=m.name, mode='CATMULL_CLARK')
    m.sculpt_levels = m.levels = m.total_levels
    return m.total_levels


DYNA_KEY = 'mch_dynamesh'


def dynamesh_on(ob):
    """The SubTool's DynaMesh is on (ZBrush: the DynaMesh button stays lit; Ctrl + drag on empty canvas remeshes
    again).  Subdivision levels turn it off, as in ZBrush."""
    return ob is not None and bool(ob.get(DYNA_KEY)) and multires(ob) is None


def dynamesh(context, ob, points):
    from . import voxel_for_points
    if multires(ob) is not None:
        return 'DynaMesh: this SubTool has subdivision levels - Del Higher / Del Lower first'
    v = voxel_for_points(context, ob, points)
    if v <= 0.0:
        return 'DynaMesh: no surface'
    ob.data.remesh_voxel_size = v
    if bpy.app.background:
        _mode(context, 'OBJECT')             # (without a window the Sculpt Mode call crashed)
        bpy.ops.object.voxel_remesh()
        _mode(context, 'SCULPT')
    else:
        bpy.ops.object.voxel_remesh()        # in Sculpt Mode like Blender's Ctrl+R: its own undo step
    return ''


def has_mask(ob, eps=1e-4):
    if ob is None or ob.type != 'MESH':
        return False
    vals = _mask_values(ob)
    return bool(len(vals)) and float(vals.max()) > eps


def empty_ctrl_drag(ob):
    """What Ctrl + drag on empty canvas does (ZBrush): 'CLEAR_MASK' when something is masked (or the mask cannot
    be read: subdivision levels), else 'DYNAMESH' when the SubTool's DynaMesh is on, else 'OFF'."""
    if ob is None or ob.type != 'MESH':
        return 'OFF'
    if multires(ob) is not None or has_mask(ob):
        return 'CLEAR_MASK'
    return 'DYNAMESH' if dynamesh_on(ob) else 'OFF'


def lasso_holds(co, matrix, width, height, path):
    """Does the closed screen lasso ``path`` (region px) hold any of the points ``co`` ((n, 3) object space)?
    ``matrix`` = the view's perspective matrix times the object's matrix."""
    import numpy as np
    if len(path) < 3 or not len(co):
        return False
    m = np.array(matrix, dtype=np.float64)
    h = np.hstack([co, np.ones((len(co), 1))]) @ m.T
    front = h[:, 3] > 1e-6
    h = h[front]
    if not len(h):
        return False
    px = (h[:, 0] / h[:, 3] + 1.0) * 0.5 * width
    py = (h[:, 1] / h[:, 3] + 1.0) * 0.5 * height
    poly = np.array(path, dtype=np.float64)
    if len(poly) > 256:
        poly = poly[np.linspace(0, len(poly) - 1, 256).astype(int)]
    lo, hi = poly.min(axis=0), poly.max(axis=0)
    box = (px >= lo[0]) & (px <= hi[0]) & (py >= lo[1]) & (py <= hi[1])
    px, py = px[box], py[box]
    if not len(px):
        return False
    inside = np.zeros(len(px), dtype=bool)
    x2, y2 = poly[-1]
    for x1, y1 in poly:                       # even-odd rule, every point against each edge at once
        if y1 != y2:
            cross = ((y1 > py) != (y2 > py)) & (px < (x2 - x1) * (py - y1) / (y2 - y1) + x1)
            inside ^= cross
        x2, y2 = x1, y1
    return bool(inside.any())


def lasso_touches(context, ob, path):
    """Ctrl + lasso: does it go round (or over) the SubTool?  Then it masks; else it is a drag on empty canvas."""
    import numpy as np
    region, rv3d = getattr(context, 'region', None), getattr(context, 'region_data', None)
    if ob is None or ob.type != 'MESH' or region is None or rv3d is None:
        return True
    me = ob.data
    n = len(me.vertices)
    co = np.empty(n * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    if n > 400000:                            # a big mesh: every few points is enough to see the outline
        co = co[::max(1, n // 400000)]
    if lasso_holds(co, rv3d.perspective_matrix @ ob.matrix_world, region.width, region.height, path):
        return True
    from bpy_extras import view3d_utils       # a few big faces: no point inside, but the lasso is on a face
    pts = path[::max(1, len(path) // 16)]
    cx = sum(p[0] for p in path) / len(path)
    cy = sum(p[1] for p in path) / len(path)
    inv = ob.matrix_world.inverted()
    for xy in list(pts) + [(cx, cy)]:
        o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        try:
            lo = inv @ o
            ld = (inv.to_3x3() @ d).normalized()
            if ob.ray_cast(lo, ld)[0]:
                return True
        except (RuntimeError, ValueError):
            return True
    return False


def _mask_values(ob):
    import numpy as np
    me = ob.data
    att = me.attributes.get('.sculpt_mask')
    if att is None:
        return np.zeros(len(me.vertices), dtype=np.float32)
    vals = np.empty(len(me.vertices), dtype=np.float32)
    att.data.foreach_get('value', vals)
    return vals


def run(context, action):
    """Do one ZBrush shelf action; '' when fine, else a short report."""
    ob = context.active_object
    zb = context.scene.mch_zb
    if action in TOOLS:
        bpy.ops.wm.tool_set_by_id(name=TOOLS[action])
        return ''
    if action == 'EDIT':
        bpy.ops.object.mode_set(mode='OBJECT' if context.mode == 'SCULPT' else 'SCULPT')
        return ''
    if ob is None or ob.type != 'MESH':
        return 'Pick a SubTool (mesh) first'
    if action == 'DUPLICATE':
        _mode(context, 'OBJECT')
        new = ob.copy()
        new.data = ob.data.copy()
        for c in ob.users_collection:
            c.objects.link(new)
        context.view_layer.update()
        switch_to(context, new)
        _mode(context, 'SCULPT')
        return f'Duplicate: {new.name}'
    if action == 'DELETE':
        others = [o for o in context.view_layer.objects if o.type == 'MESH' and o != ob and o.visible_get()]
        _mode(context, 'OBJECT')
        bpy.data.objects.remove(ob)
        if others:
            switch_to(context, others[0])
            _mode(context, 'SCULPT')
        return 'Deleted'
    if action in {'SPLIT_MASKED', 'SPLIT_UNMASKED'}:
        vals = _mask_values(ob)
        if not vals.any():
            return 'Split: paint a mask first (Ctrl + drag on the model)'
        hi = action == 'SPLIT_MASKED'
        new = _split_faces(context, ob, lambda bm, f: all((vals[v.index] > 0.5) == hi for v in f.verts),
                           'masked' if hi else 'unmasked')
        return f'Split: {new.name}' if new else 'Split: nothing to take out'
    if action == 'EXTRACT':
        if not _mask_values(ob).any():
            return 'Extract: paint a mask first (Ctrl + drag on the model)'
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.paint_mask_extract(thickness=zb.thick, apply_solidify=zb.thick > 0)
        return 'Extract: new SubTool'
    if action == 'DIVIDE':
        _mode(context, 'SCULPT')
        return f'Divide: SDiv {_divide(context, ob)}'
    if action == 'DEL_HIGHER':
        m = multires(ob)
        if m is None or m.sculpt_levels >= m.total_levels:
            return 'Del Higher: no higher levels'
        bpy.ops.object.multires_higher_levels_delete(modifier=m.name)
        return 'Del Higher'
    if action == 'DEL_LOWER':
        m = multires(ob)
        if m is None:
            return 'Del Lower: no subdivision levels'
        if m.sculpt_levels < m.total_levels:
            return 'Del Lower: go to the highest SDiv first (Blender keeps its base mesh)'
        _mode(context, 'OBJECT')
        m.levels = m.total_levels
        bpy.ops.object.modifier_apply(modifier=m.name)
        _mode(context, 'SCULPT')
        return 'Del Lower: this level is the base now'
    if action in {'SDIV_UP', 'SDIV_DOWN'}:
        m = multires(ob)
        if m is None:
            return 'No subdivision levels (Ctrl+D: Divide)'
        zb.sdiv = m.sculpt_levels + (1 if action == 'SDIV_UP' else -1)
        return f'SDiv {m.sculpt_levels}'
    if action == 'DYNAMESH' and dynamesh_on(ob):           # ZBrush: pressing the lit DynaMesh turns it off
        del ob[DYNA_KEY]
        return 'DynaMesh off'
    if action in {'DYNAMESH', 'DYNA_UPDATE', 'DYNA_SUBDIV', 'DYNA_SUBDIV3'}:
        from .quick_hud import points_text
        msg = dynamesh(context, ob, zb.points)
        if msg:
            return msg
        if action in {'DYNA_SUBDIV', 'DYNA_SUBDIV3'}:
            _divide(context, ob, 3 if action == 'DYNA_SUBDIV3' else 2)
            ob.pop(DYNA_KEY, None)
        else:
            ob[DYNA_KEY] = 1
        return f'DynaMesh: {points_text(len(ob.data.vertices))} points'
    if action == 'ZREMESH':
        if multires(ob) is not None:
            return 'ZRemesher: Del Higher / Del Lower first'
        _mode(context, 'OBJECT')
        try:
            bpy.ops.object.quadriflow_remesh(target_faces=max(100, int(zb.target_polys * 1000)),
                                             use_preserve_sharp=zb.keep_creases, use_preserve_boundary=zb.keep_border,
                                             use_mesh_symmetry=bool(zb.sym_x), mode='FACES')
        except RuntimeError as ex:
            _mode(context, 'SCULPT')
            return 'ZRemesher: ' + str(ex).splitlines()[0]
        _mode(context, 'SCULPT')
        return f'ZRemesher: {len(ob.data.polygons):,} polygons'
    if action in {'HALF', 'SAME', 'DOUBLE'}:
        f = {'HALF': 0.5, 'SAME': 1.0, 'DOUBLE': 2.0}[action]
        zb.target_polys = max(0.1, round(len(ob.data.polygons) * f / 1000.0, 1))
        return f'Target Polygons Count {zb.target_polys:g}'
    if action == 'MIRROR':
        def flip(bm):
            for v in bm.verts:
                v.co.x = -v.co.x
            for f in bm.faces:
                f.normal_flip()
        _bm_edit(context, ob, flip)
        return 'Mirror (X)'
    if action == 'MIRROR_WELD':
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.symmetrize()
        return 'Mirror And Weld'
    if action == 'CLOSE_HOLES':
        import bmesh

        def close(bm):
            edges = [e for e in bm.edges if e.is_boundary]
            if edges:
                bmesh.ops.holes_fill(bm, edges=edges, sides=0)
            return len(edges)
        n = _bm_edit(context, ob, close)
        return 'Close Holes' if n else 'Close Holes: no holes'
    if action in {'DEL_HIDDEN', 'SPLIT_HIDDEN'}:
        hidden = ob.data.attributes.get('.hide_poly')
        if hidden is None:
            return 'Nothing hidden (Ctrl+Shift + drag to hide)'
        import numpy as np
        vals = np.zeros(len(ob.data.polygons), dtype=bool)
        hidden.data.foreach_get('value', vals)
        if not vals.any():
            return 'Nothing hidden (Ctrl+Shift + drag to hide)'
        if action == 'SPLIT_HIDDEN':
            new = _split_faces(context, ob, lambda bm, f: bool(vals[f.index]), 'hidden')
            return f'Split Hidden: {new.name}' if new else 'Split Hidden: nothing'
        import bmesh

        def dele(bm):
            bm.faces.ensure_lookup_table()
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if vals[f.index]], context='FACES')
            bmesh.ops.delete(bm, geom=[v for v in bm.verts if not v.link_faces], context='VERTS')
        _bm_edit(context, ob, dele)
        return 'Del Hidden'
    if action == 'INFLATE':
        import numpy as np
        _mode(context, 'OBJECT')
        me = ob.data
        n = len(me.vertices)
        co, nrm = np.empty(n * 3, dtype=np.float32), np.empty(n * 3, dtype=np.float32)
        me.vertices.foreach_get('co', co)
        me.vertices.foreach_get('normal', nrm)
        size = float(np.ptp(co.reshape(-1, 3), axis=0).max()) if n else 0.0
        co += nrm * (zb.inflate / 100.0) * 0.02 * size
        me.vertices.foreach_set('co', co)
        me.update()
        _mode(context, 'SCULPT')
        return f'Inflate {zb.inflate}'
    if action == 'MASK_CAVITY':
        _mode(context, 'SCULPT')
        bpy.ops.sculpt.mask_from_cavity(mix_mode='MIX', mix_factor=1.0, settings_source='OPERATOR',
                                        factor=zb.cavity_int / 100.0, blur_steps=zb.blur, invert=zb.cavity_inv)
        return 'Mask By Cavity' + (' (ridges)' if zb.cavity_inv else '')
    if action == 'MASK_BLUR':
        bpy.ops.sculpt.mask_filter(filter_type='SMOOTH')
        return 'Mask: blur'
    if action == 'MASK_INVERT':
        bpy.ops.paint.mask_flood_fill(mode='INVERT')
        return ''
    if action == 'MASK_CLEAR':
        bpy.ops.paint.mask_flood_fill(mode='VALUE', value=0.0)
        return ''
    if action == 'GROUPS_FROM_MASK':
        bpy.ops.sculpt.face_sets_create(mode='MASKED')
        return 'Polygroup from mask'
    if action == 'AUTO_GROUPS':
        bpy.ops.sculpt.face_sets_init(mode='LOOSE_PARTS')
        return 'Auto Groups'
    if action == 'GROUPS_SPLIT':
        _mode(context, 'OBJECT')
        att = ob.data.attributes.get('.sculpt_face_set')
        if att is None:
            _mode(context, 'SCULPT')
            return 'Groups Split: only one polygroup'
        import numpy as np
        sets = np.zeros(len(ob.data.polygons), dtype=np.int32)
        att.data.foreach_get('value', sets)
        made = 0
        for val in sorted(set(sets.tolist()))[1:]:
            vals = sets.copy()
            if _split_faces(context, ob, lambda bm, f, v=val, s=vals: s[f.index] == v, f'group{val}'):
                made += 1
            _mode(context, 'OBJECT')
            att = ob.data.attributes.get('.sculpt_face_set')
            if att is None:
                break
            sets = np.zeros(len(ob.data.polygons), dtype=np.int32)
            att.data.foreach_get('value', sets)
        _mode(context, 'SCULPT')
        return f'Groups Split: {made} new SubTool(s)' if made else 'Groups Split: only one polygroup'
    if action in {'MERGE_DOWN', 'MERGE_VISIBLE'}:
        meshes = [o for o in sorted(context.view_layer.objects, key=lambda o: o.name.lower())
                  if o.type == 'MESH' and o.visible_get()]
        if action == 'MERGE_DOWN':
            i = meshes.index(ob) if ob in meshes else -1
            others = meshes[i + 1:i + 2] if 0 <= i < len(meshes) - 1 else []
        else:
            others = [o for o in meshes if o != ob]
        if not others:
            return 'Nothing to merge'
        _mode(context, 'OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        for o in others + [ob]:
            o.select_set(True)
        context.view_layer.objects.active = ob
        bpy.ops.object.join()
        _mode(context, 'SCULPT')
        return f'Merged {len(others) + 1} SubTools'
    if action in {'ALL_LOW', 'ALL_HIGH'}:
        for o in context.view_layer.objects:
            m = multires(o) if o.type == 'MESH' else None
            if m is not None:
                m.sculpt_levels = m.levels = 0 if action == 'ALL_LOW' else m.total_levels
        return ''
    if action == 'DECIMATE':
        _mode(context, 'OBJECT')
        mod = ob.modifiers.new('MCH_Decimate', 'DECIMATE')
        mod.ratio = zb.decimate / 100.0
        bpy.ops.object.modifier_apply(modifier=mod.name)
        _mode(context, 'SCULPT')
        return f'Decimate: {len(ob.data.polygons):,} polygons'
    if action in {'CHECK_MESH', 'FIX_MESH'}:
        import bmesh

        def check(bm):
            loose = [v for v in bm.verts if not v.link_faces]
            bad = [e for e in bm.edges if not e.is_manifold and not e.is_boundary]
            if action == 'FIX_MESH':
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=1e-6)
                bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=1e-7)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
            return len(loose), len(bad)
        loose, bad = _bm_edit(context, ob, check)
        if action == 'CHECK_MESH':
            return f'Check Mesh: {loose} loose points, {bad} bad edges' if loose or bad else 'Check Mesh: clean'
        return 'Fix Mesh: done'
    if action == 'POLYMESH3D':
        _mode(context, 'OBJECT')
        for mod in list(ob.modifiers):
            try:
                bpy.ops.object.modifier_apply(modifier=mod.name)
            except RuntimeError:
                pass
        _mode(context, 'SCULPT')
        return 'Make PolyMesh3D'
    if action == 'SWITCH_COLOR':
        bpy.ops.paint.brush_colors_flip()
        return ''
    if action == 'FILL_COLOR':
        import numpy as np
        _mode(context, 'OBJECT')
        me = ob.data
        att = me.color_attributes.active_color or me.color_attributes.new('Color', 'FLOAT_COLOR', 'POINT')
        u = unified(context)
        col = (u.color if u is not None and u.use_unified_color else brush(context).color)
        n = len(att.data)
        att.data.foreach_set('color', np.tile(np.array([col[0], col[1], col[2], 1.0], dtype=np.float32), n))
        me.update()
        _mode(context, 'SCULPT')
        return 'FillColor'
    if action == 'SYM_X':
        zb.sym_x = not zb.sym_x
        return f'Symmetry X {"on" if zb.sym_x else "off"}'
    if action == 'POLYF':
        zb.polyf = not zb.polyf
        return ''
    if action == 'FRAME':
        bpy.ops.view3d.view_selected()
        return ''
    if action == 'SOLO':
        bpy.ops.view3d.localview()
        return ''
    if action in {'QCUBE', 'QGRID'}:
        return append(context, 'QCUBE' if action == 'QCUBE' else 'QGRID')
    if action == 'POLISH_GROUPS':
        try:
            bpy.ops.sculpt.mesh_filter(type='RELAX_FACE_SETS', strength=0.5, iteration_count=4)
        except (RuntimeError, TypeError) as ex:
            return 'Polish By Groups: ' + str(ex).splitlines()[0]
        return 'Polish By Groups'
    if action in {'EXPORT_OBJ', 'EXPORT_STL', 'FBX_EXPORT', 'FBX_IMPORT'}:
        _mode(context, 'OBJECT')
        sel = zb.fbx_scope == 'SELECTED'
        try:
            if action == 'EXPORT_OBJ':
                bpy.ops.wm.obj_export('INVOKE_DEFAULT', export_selected_objects=sel)
            elif action == 'EXPORT_STL':
                bpy.ops.wm.stl_export('INVOKE_DEFAULT', export_selected_objects=sel)
            elif action == 'FBX_EXPORT':
                bpy.ops.export_scene.fbx('INVOKE_DEFAULT', use_selection=sel)
            else:
                bpy.ops.import_scene.fbx('INVOKE_DEFAULT')
        except (RuntimeError, AttributeError) as ex:
            return str(ex).splitlines()[0]
        return ''
    return f'Unknown action {action}'


PRIMITIVES = (('SPHERE', 'Sphere3D'), ('CUBE', 'Cube3D'), ('CYLINDER', 'Cylinder3D'), ('CONE', 'Cone3D'),
              ('TORUS', 'Ring3D'), ('QCUBE', 'QCube'), ('QGRID', 'QGrid'))


def append(context, kind='SPHERE'):
    """A new SubTool at the 3D cursor (IMM Primitives / Append / QCube / QGrid), sculpted right away."""
    if context.active_object is not None:
        _mode(context, 'OBJECT')
    zb = context.scene.mch_zb
    loc = context.scene.cursor.location
    size = 1.0
    ref = context.active_object
    if ref is not None and ref.type == 'MESH':
        size = max(ref.dimensions) * 0.5 or 1.0
    if kind == 'SPHERE':
        bpy.ops.mesh.primitive_uv_sphere_add(radius=size * 0.5, segments=48, ring_count=24, location=loc)
    elif kind == 'CUBE':
        bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
    elif kind == 'CYLINDER':
        bpy.ops.mesh.primitive_cylinder_add(radius=size * 0.3, depth=size, vertices=32, location=loc)
    elif kind == 'CONE':
        bpy.ops.mesh.primitive_cone_add(radius1=size * 0.4, depth=size, vertices=32, location=loc)
    elif kind == 'TORUS':
        bpy.ops.mesh.primitive_torus_add(major_radius=size * 0.4, minor_radius=size * 0.12, location=loc)
    elif kind == 'QCUBE':
        bpy.ops.mesh.primitive_cube_add(size=size, location=loc)
        import bmesh
        ob = context.active_object
        bm = bmesh.new()
        bm.from_mesh(ob.data)
        if zb.res > 1:
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=zb.res - 1, use_grid_fill=True)
        bm.to_mesh(ob.data)
        bm.free()
    elif kind == 'QGRID':
        bpy.ops.mesh.primitive_grid_add(x_subdivisions=zb.res + 1, y_subdivisions=zb.res + 1, size=size,
                                        location=loc)
    new = context.active_object
    new.name = dict(PRIMITIVES).get(kind, kind.title())
    _mode(context, 'SCULPT')
    return f'Append: {new.name}'


# --- operators ------------------------------------------------------------------------------------------------------

class _ZBPoll:
    @classmethod
    def poll(cls, context):
        return on(context)


class MCH_OT_zb_action(_ZBPoll, bpy.types.Operator):
    """ZBrush shelf action on the SubTool (Blender equivalent in the tooltip of each button)"""
    bl_idname = 'mch.zb_action'
    bl_label = 'ZBrush Action'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    action: StringProperty()

    def execute(self, context):
        try:
            msg = run(context, self.action)
        except RuntimeError as ex:
            msg = str(ex).splitlines()[0]
        if msg:
            self.report({'INFO'}, msg)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_brush(_ZBPoll, bpy.types.Operator):
    """Pick this brush (a Blender Essentials brush under its ZBrush name)"""
    bl_idname = 'mch.zb_brush'
    bl_label = 'ZBrush Brush'
    bl_options = {'REGISTER', 'INTERNAL'}
    name: StringProperty()

    def execute(self, context):
        msg = activate(context, self.name)
        if msg:
            self.report({'WARNING'}, msg)
            return {'CANCELLED'}
        close_popup(context)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_append(_ZBPoll, bpy.types.Operator):
    """Append a new SubTool (IMM Primitives)"""
    bl_idname = 'mch.zb_append'
    bl_label = 'Append SubTool'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=[(k, n, '') for k, n in PRIMITIVES], default='SPHERE')

    def execute(self, context):
        self.report({'INFO'}, append(context, self.kind))
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_subtool(_ZBPoll, bpy.types.Operator):
    """Sculpt this SubTool"""
    bl_idname = 'mch.zb_subtool'
    bl_label = 'Pick SubTool'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: StringProperty()

    def execute(self, context):
        if not switch_to(context, bpy.data.objects.get(self.name)):
            return {'CANCELLED'}
        _bump()
        return {'FINISHED'}


def _bump():
    try:
        from . import ui_bars
        ui_bars.bump()
    except ImportError:
        pass


# --- mouse: sculpt on the model, navigate on the canvas -----------------------------------------------------------

def stroke_kwargs(kind):
    """sculpt.brush_stroke arguments for a ZBrush mouse action (Blender 5.2 has a brush switch for the stroke;
    5.0: mode SMOOTH, the mask by a tool switch)."""
    rna = bpy.ops.sculpt.brush_stroke.get_rna_type().properties
    kw = {'ignore_background_click': True} if 'ignore_background_click' in rna else {}
    toggle = 'brush_toggle' in rna
    if kind == 'ZSUB':
        kw['mode'] = 'INVERT'
    elif kind == 'SMOOTH':
        if toggle:
            kw['brush_toggle'] = 'SMOOTH'
        else:
            kw['mode'] = 'SMOOTH'
    elif kind in {'MASK', 'UNMASK'}:
        if toggle:
            kw['brush_toggle'] = 'MASK'
            if kind == 'UNMASK':
                kw['mode'] = 'INVERT'
        elif kind == 'UNMASK':
            kw['mode'] = 'INVERT'
    return kw, toggle


def plan(ctrl, shift, alt):
    """(on the model, on the canvas) for a left press with these keys - the ZBrush mouse."""
    if ctrl and shift:
        return ('GROUP_SOLO', 'SHOW_ALL_OR_HIDE_INSIDE' if alt else 'SHOW_ALL_OR_SHOW_INSIDE')
    if ctrl:
        return ('UNMASK', 'INVERT_OR_UNMASK_LASSO') if alt else ('MASK', 'INVERT_OR_MASK_LASSO')
    if alt:
        return 'ZSUB', 'PAN'
    if shift:
        return 'SMOOTH', 'ROTATE_SNAP'
    return 'STROKE', 'ROTATE'


def object_under(context, x, y):
    """The (original) object under region px (x, y), or None."""
    from bpy_extras import view3d_utils
    region, rv3d = getattr(context, 'region', None), getattr(context, 'region_data', None)
    if region is None or rv3d is None:
        return None
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, (x, y))
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, (x, y))
    try:
        hit, _loc, _nrm, _i, obj, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)
    except (RuntimeError, ReferenceError, AttributeError):
        return None
    return getattr(obj, 'original', obj) if hit and obj is not None else None


def ctrl_canvas_release(context, path, unmask=False):
    """Ctrl pressed on empty canvas, let go (ZBrush): a click inverts the mask; a lasso round the model masks it
    (Alt: unmasks); a drag on empty canvas clears the mask, or with no mask DynaMeshes again (empty_ctrl_drag)."""
    ob = context.active_object
    if not path:
        bpy.ops.paint.mask_flood_fill('EXEC_DEFAULT', True, mode='INVERT')
        return ''
    if lasso_touches(context, ob, path):
        bpy.ops.paint.mask_lasso_gesture('EXEC_DEFAULT', True, path=[{'name': '', 'loc': p, 'time': 0.0} for p in path],
                                         mode='VALUE', value=0.0 if unmask else 1.0)
        return ''
    what = empty_ctrl_drag(ob)
    if what == 'CLEAR_MASK':
        bpy.ops.paint.mask_flood_fill('EXEC_DEFAULT', True, mode='VALUE', value=0.0)
        return 'Mask cleared'
    if what == 'DYNAMESH':
        bpy.ops.mch.zb_action('EXEC_DEFAULT', True, action='DYNA_UPDATE')
        return ''
    return 'DynaMesh is off for this SubTool: Geometry > DynaMesh turns it on (then Ctrl + drag here remeshes)'


_LASSO = {'path': None, 'handle': None}


def _lasso_draw():
    try:
        path = _LASSO['path']
        if path and len(path) > 1:
            from . import ui_gpu as G
            G.polyline(path, ORANGE, 2.0)
            G.polyline([path[-1], path[0]], (ORANGE[0], ORANGE[1], ORANGE[2], 0.4), 1.0)
    except Exception:          # never break viewport drawing
        pass
    from . import ui_gpu
    ui_gpu.done()


def lasso_show(path):
    _LASSO['path'] = path
    if _LASSO['handle'] is None and not bpy.app.background:
        _LASSO['handle'] = bpy.types.SpaceView3D.draw_handler_add(_lasso_draw, (), 'WINDOW', 'POST_PIXEL')


def lasso_hide():
    _LASSO['path'] = None
    if _LASSO['handle'] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_LASSO['handle'], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _LASSO['handle'] = None


class MCH_OT_zb_press(_ZBPoll, bpy.types.Operator):
    """ZBrush mouse: on the model it sculpts (Alt Zsub, Shift Smooth, Ctrl mask), on the canvas it turns / moves
    the view, Ctrl+click inverts the mask, Ctrl+lasso masks, Ctrl+drag on empty canvas clears the mask or
    DynaMeshes, Ctrl+Shift shows / hides, Alt+click on another SubTool picks it"""
    bl_idname = 'mch.zb_press'
    bl_label = 'ZBrush Mouse'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        try:
            from . import ui_bars
            inside, _it = ui_bars.hit(context, event.mouse_region_x, event.mouse_region_y)
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
            inside = False
        if inside:
            return bpy.ops.mch.quick_hud_press('INVOKE_DEFAULT')
        if popup_open(context):
            close_popup(context)
            return {'FINISHED'}
        model, canvas = plan(event.ctrl, event.shift, event.alt)
        if event.alt and not event.ctrl and not event.shift:     # ZBrush: Alt + click another SubTool picks it
            other = object_under(context, event.mouse_region_x, event.mouse_region_y)
            if other is not None and other.type == 'MESH' and other != context.active_object:
                if switch_to(context, other):
                    _bump()
                    self.report({'INFO'}, f'SubTool: {other.name}')
                    return {'FINISHED'}
        if model == 'GROUP_SOLO':
            r = bpy.ops.sculpt.face_set_change_visibility('INVOKE_DEFAULT', mode='TOGGLE')
            if 'FINISHED' in r:
                return {'FINISHED'}
        elif model == 'STROKE' and stamp_ready(context) and \
                object_under(context, event.mouse_region_x, event.mouse_region_y) == context.active_object:
            r = bpy.ops.mch.zb_tex_stamp('INVOKE_DEFAULT')       # Paint + Texture: a DragRect stamp
            return {'FINISHED'} if 'RUNNING_MODAL' in r or 'FINISHED' in r else {'CANCELLED'}
        elif model == 'STROKE':
            r = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', **stroke_kwargs('STROKE')[0])
            if 'RUNNING_MODAL' in r or 'FINISHED' in r:
                return {'FINISHED'}
        else:
            kw, toggle = stroke_kwargs(model)
            swapped = None
            if model in {'MASK', 'UNMASK'} and not toggle:      # Blender 5.0: the Mask tool for this stroke
                swapped = _tool_id(context)
                bpy.ops.wm.tool_set_by_id(name='builtin_brush.mask')
                bpy.ops.mch.zb_restore_tool('INVOKE_DEFAULT', tool=swapped)
            r = bpy.ops.sculpt.brush_stroke('INVOKE_DEFAULT', **kw)
            if 'RUNNING_MODAL' in r or 'FINISHED' in r:
                return {'FINISHED'}
            if swapped:
                bpy.ops.wm.tool_set_by_id(name=swapped)
        # the canvas
        if canvas in {'ROTATE', 'ROTATE_SNAP', 'PAN'}:
            return bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode='PAN' if canvas == 'PAN' else 'ROTATE')
        self.canvas, self.x0, self.y0 = canvas, event.mouse_region_x, event.mouse_region_y
        self.path, self.moved = [(self.x0, self.y0)], False
        if canvas.startswith('INVERT_OR'):           # Ctrl: our own lasso (decided when let go)
            lasso_show(self.path)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        lasso = self.canvas.startswith('INVERT_OR')
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            x, y = event.mouse_region_x, event.mouse_region_y
            if abs(x - self.x0) + abs(y - self.y0) > 5:
                self.moved = True
            if lasso:
                lx, ly = self.path[-1]
                if abs(x - lx) + abs(y - ly) >= 3:
                    self.path.append((x, y))
                    if context.area:
                        context.area.tag_redraw()
                return {'RUNNING_MODAL'}
            if self.moved:
                bpy.ops.paint.hide_show_lasso_gesture(
                    'INVOKE_DEFAULT', action='HIDE', area='INSIDE' if 'HIDE_INSIDE' in self.canvas else 'OUTSIDE')
                return {'FINISHED'}
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if lasso:
                lasso_hide()
                if context.area:
                    context.area.tag_redraw()
                try:
                    msg = ctrl_canvas_release(context, self.path if self.moved and len(self.path) > 2 else None,
                                              'UNMASK' in self.canvas)
                except RuntimeError as ex:
                    msg = str(ex).splitlines()[0]
                if msg:
                    self.report({'INFO'}, msg)
            else:
                bpy.ops.paint.hide_show_all(action='SHOW')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            lasso_hide()
            if context.area:
                context.area.tag_redraw()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


def _tool_id(context):
    try:
        return context.workspace.tools.from_space_view3d_mode('SCULPT').idname
    except (AttributeError, RuntimeError):
        return 'builtin.brush'


class MCH_OT_zb_restore_tool(bpy.types.Operator):
    """(Blender 5.0) back to the brush after a Ctrl mask stroke: the first event after the stroke"""
    bl_idname = 'mch.zb_restore_tool'
    bl_label = 'Restore Tool'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='builtin.brush')

    def invoke(self, context, event):
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'TIMER', 'TIMER_REPORT', 'NONE'}:
            return {'PASS_THROUGH'}
        try:
            bpy.ops.wm.tool_set_by_id(name=self.tool or 'builtin.brush')
        except RuntimeError:
            pass
        return {'FINISHED', 'PASS_THROUGH'}


def snap_rotation(q):
    """The nearest of the 24 square-on view rotations (front / side / top ... with an upright up)."""
    m = q.to_matrix()
    best, best_d = None, -9.0
    axes = [Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0)), Vector((0, 0, 1)),
            Vector((0, 0, -1))]
    z = m.col[2]
    y = m.col[1]
    for a in axes:
        for b in axes:
            if abs(a.dot(b)) > 0.5:
                continue
            d = a.dot(z) + b.dot(y)
            if d > best_d:
                best_d, best = d, (a, b)
    zc, yc = best
    xc = yc.cross(zc)
    return Matrix((xc, yc, zc)).transposed().to_quaternion()


class MCH_OT_zb_nav(bpy.types.Operator):
    """ZBrush canvas drag: rotate (Shift: snap square-on), Alt: move, let Alt go while dragging: zoom"""
    bl_idname = 'mch.zb_nav'
    bl_label = 'ZBrush Navigate'
    bl_options = {'INTERNAL', 'BLOCKING'}
    mode: EnumProperty(items=[('ROTATE', 'Rotate', ''), ('PAN', 'Move', ''), ('ZOOM', 'Zoom', '')], default='ROTATE')
    button: StringProperty(default='LEFTMOUSE', options={'SKIP_SAVE'})
    alt_start: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return nav_on(context) and getattr(context, 'region_data', None) is not None

    def invoke(self, context, event):
        rv3d = getattr(context, 'region_data', None)
        if rv3d is None:
            return {'CANCELLED'}
        self.rv3d = rv3d
        self.start = (rv3d.view_rotation.copy(), rv3d.view_location.copy(), rv3d.view_distance)
        self.last = (event.mouse_x, event.mouse_y)
        self.alt_pan = self.mode == 'PAN' and (event.alt or self.alt_start)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        rv3d = self.rv3d
        if event.type == 'MOUSEMOVE':
            dx, dy = event.mouse_x - self.last[0], event.mouse_y - self.last[1]
            self.last = (event.mouse_x, event.mouse_y)
            if self.mode == 'PAN' and self.alt_pan and not event.alt:
                self.mode = 'ZOOM'                         # ZBrush: let Alt go while dragging = zoom
            if self.mode == 'ROTATE':
                q = rv3d.view_rotation
                up = q @ Vector((0, 1, 0))
                right = q @ Vector((1, 0, 0))
                s = 0.006
                q = Quaternion(up, -dx * s) @ Quaternion(right, dy * s) @ q
                rv3d.view_rotation = snap_rotation(q) if event.shift else q.normalized()
            elif self.mode == 'PAN':
                q = rv3d.view_rotation
                scale = rv3d.view_distance * 2.0 / max(1, context.region.height)
                rv3d.view_location -= (q @ Vector((1, 0, 0))) * dx * scale + (q @ Vector((0, 1, 0))) * dy * scale
            else:
                rv3d.view_distance = max(1e-4, rv3d.view_distance * math.exp(-dy * 0.006))
            return {'RUNNING_MODAL'}
        if event.type == self.button and event.value == 'RELEASE':
            return {'FINISHED'}
        if event.type == 'ESC' or (event.type in {'RIGHTMOUSE', 'LEFTMOUSE'} and event.type != self.button
                                   and event.value == 'PRESS'):
            rv3d.view_rotation, rv3d.view_location, rv3d.view_distance = self.start
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_zb_viewdrag(_ZBPoll, bpy.types.Operator):
    """Drag on Move / Zoom3D / Rotate (right shelf) to move the view"""
    bl_idname = 'mch.zb_viewdrag'
    bl_label = 'View Drag'
    bl_options = {'INTERNAL'}
    mode: EnumProperty(items=[('ROTATE', 'Rotate', ''), ('PAN', 'Move', ''), ('ZOOM', 'Zoom', '')], default='ROTATE')

    def invoke(self, context, event):
        return bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode=self.mode)


# --- the menu at the cursor (Space / S / U / O / right-click) and the brush picker (B) -----------------------------

def popup_open(context):
    return bool(getattr(context.window_manager, 'mch_zb_pop', ''))


def close_popup(context):
    wm = context.window_manager
    if getattr(wm, 'mch_zb_pop', ''):
        wm.mch_zb_pop = ''
        _bump()


class MCH_OT_zb_popup(_ZBPoll, bpy.types.Operator):
    """ZBrush menu at the cursor: Draw Size / Focal Shift / Z Intensity, Zadd / Zsub, Stroke, recent brushes.
    0.24.63 right button: a drag turns the view anywhere, over the model too (Alt: move, let Alt go: zoom) - the
    pen's side button while hovering, like ZBrush; a click opens the menu"""
    bl_idname = 'mch.zb_popup'
    bl_label = 'ZBrush Menu'
    bl_options = {'INTERNAL'}
    focus: StringProperty(default='')
    kind: StringProperty(default='MENU')

    def invoke(self, context, event):
        if event.type == 'RIGHTMOUSE' and self.kind == 'MENU' and not self.focus:
            self.rmb = RMBDrag()
            self.rmb.rmb_drag_start(context, event)
            self.event_xy = (event.mouse_region_x, event.mouse_region_y)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        return self.open(context, (event.mouse_region_x, event.mouse_region_y))

    def modal(self, context, event):
        if self.rmb.rmb_drag_check(context, event):        # dragged: the view turns (zb_nav takes it)
            return {'FINISHED'}
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            return self.open(context, self.event_xy)       # a click: the menu
        if event.type == 'ESC':
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def open(self, context, xy):
        wm = context.window_manager
        if wm.mch_zb_pop == self.kind and not self.focus:
            wm.mch_zb_pop = ''
        else:
            wm.mch_zb_pop = self.kind
            wm.mch_zb_pop_xy = xy
            wm.mch_zb_pop_focus = self.focus
        _bump()
        if context.area:
            context.area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_zb_brush_pick(_ZBPoll, bpy.types.Operator):
    """B: the brushes at the cursor - type the letters (B S T = Standard) or click one; Esc closes"""
    bl_idname = 'mch.zb_brush_pick'
    bl_label = 'ZBrush Brushes'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        wm = context.window_manager
        wm.mch_zb_pop = 'BRUSH'
        wm.mch_zb_pop_xy = (event.mouse_region_x, event.mouse_region_y)
        wm.mch_zb_pop_focus = ''
        _bump()
        self.typed = ''
        context.window_manager.modal_handler_add(self)
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        wm = context.window_manager
        if wm.mch_zb_pop != 'BRUSH':
            return {'FINISHED'}
        if event.value != 'PRESS':
            return {'PASS_THROUGH'}
        if event.type == 'ESC':
            close_popup(context)
            return {'FINISHED'}
        if len(event.type) == 1 and event.type.isalpha():
            self.typed += event.type
            hits = [z for z, _bl, code in BRUSHES if code.startswith(self.typed)]
            wm.mch_zb_pop_focus = self.typed
            if len(hits) == 1:
                activate(context, hits[0])
                close_popup(context)
                self.report({'INFO'}, hits[0])
                return {'FINISHED'}
            if not hits:
                self.typed = ''
                wm.mch_zb_pop_focus = ''
            _bump()
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'PASS_THROUGH'}


class MCH_OT_zb_switch(bpy.types.Operator):
    """MECHA LAB (Object Mode, the Mecha tools) or ZBRUSH (Sculpt Mode on the active mesh)"""
    bl_idname = 'mch.zb_switch'
    bl_label = 'MECHA LAB / ZBRUSH'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    target: EnumProperty(items=[('MECHA', 'MECHA LAB', ''), ('ZBRUSH', 'ZBRUSH', '')], default='ZBRUSH')

    def execute(self, context):
        ob = context.active_object
        if self.target == 'MECHA':
            if ob is not None and ob.mode != 'OBJECT':
                bpy.ops.object.mode_set(mode='OBJECT')
            _bump()
            return {'FINISHED'}
        if ob is None or ob.type != 'MESH':
            mesh = next((o for o in context.selected_objects if o.type == 'MESH'), None)
            if mesh is None:
                self.report({'WARNING'}, 'ZBRUSH: pick a mesh first')
                return {'CANCELLED'}
            context.view_layer.objects.active = mesh
        if context.active_object.mode != 'SCULPT':
            bpy.ops.object.mode_set(mode='SCULPT')
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_style(bpy.types.Operator):
    """ZBrush style (ZBrush screen and keys in Sculpt Mode, ZBrush canvas navigation) or Blender style (as Blender)"""
    bl_idname = 'mch.zb_style'
    bl_label = 'Control Style'
    bl_options = {'INTERNAL'}
    style: EnumProperty(items=[('ZBRUSH', 'ZBrush', ''), ('BLENDER', 'Blender', '')], default='ZBRUSH')

    def execute(self, context):
        set_style(self.style)
        _bump()
        for area in getattr(context.screen, 'areas', []):
            area.tag_redraw()
        return {'FINISHED'}


def over_object(context, event):
    """Is a visible object under the mouse (Object Mode, ZBrush style: empty canvas turns the view)?"""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return True
    xy = (event.mouse_region_x, event.mouse_region_y)
    origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, direction)[0]
    except (RuntimeError, ReferenceError):
        return True
    return bool(hit)


def obj_select_state(context):
    """Object Mode in MECHA LAB with Select / Move (no Mecha drawing tool waiting for a stroke)."""
    from . import bottom_bar
    try:
        return bottom_bar.ui_active(context) and bottom_bar.in_select(context)
    except (AttributeError, KeyError, TypeError, ReferenceError):
        return False


class MCH_OT_zb_obj_press(bpy.types.Operator):
    """ZBrush style in Select / Move: drag the empty canvas = rotate (Shift snap), Alt = move / zoom,
    Ctrl = box select; on an object Blender's select / move as before"""
    bl_idname = 'mch.zb_obj_press'
    bl_label = 'ZBrush Canvas (Object Mode)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return nav_on(context) and getattr(context, 'mode', '') == 'OBJECT' and obj_select_state(context)

    def invoke(self, context, event):
        try:
            from . import ui_bars
            if ui_bars.hit(context, event.mouse_region_x, event.mouse_region_y)[0]:
                return {'PASS_THROUGH'}
        except (AttributeError, KeyError, TypeError, ReferenceError, ImportError):
            pass
        if over_object(context, event):
            return {'PASS_THROUGH'}
        if event.ctrl:
            return bpy.ops.view3d.select_box('INVOKE_DEFAULT', mode='SET', wait_for_input=False)
        return bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode='PAN' if event.alt else 'ROTATE')


class RMBDrag:
    """ZBrush style for a right-button press that opens a menu: dragging turns the view instead
    (Alt: move, let Alt go: zoom); a click still opens the menu."""

    def rmb_drag_start(self, context, event):
        self.rmb_xy = (event.mouse_x, event.mouse_y)
        self.rmb_alt = event.alt
        self.rmb_live = nav_on(context)

    def rmb_drag_check(self, context, event):
        """True when this event turned the press into a view drag (the nav took over)."""
        if event.type == 'RIGHTMOUSE' and event.value == 'RELEASE':
            self.rmb_live = False                    # a click: the menu as before
        if not getattr(self, 'rmb_live', False) or event.type != 'MOUSEMOVE':
            return False
        x, y = self.rmb_xy
        if abs(event.mouse_x - x) + abs(event.mouse_y - y) < 6:
            return False
        bpy.ops.mch.zb_nav('INVOKE_DEFAULT', mode='PAN' if (self.rmb_alt or event.alt) else 'ROTATE',
                           button='RIGHTMOUSE', alt_start=self.rmb_alt)
        return True


class MCH_OT_zb_alpha(_ZBPoll, bpy.types.Operator):
    """Use this alpha on the brush (empty: Alpha Off)"""
    bl_idname = 'mch.zb_alpha'
    bl_label = 'ZBrush Alpha'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    path: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        self.report({'INFO'}, set_alpha(context, self.path))
        close_popup(context)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_alpha_edit(_ZBPoll, bpy.types.Operator):
    """Alpha: Flip H / Flip V / Rotate 90 / Invert"""
    bl_idname = 'mch.zb_alpha_edit'
    bl_label = 'ZBrush Alpha Edit'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    action: StringProperty(default='FLIP_H')

    def execute(self, context):
        self.report({'INFO'}, alpha_edit(context, self.action))
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_set(_ZBPoll, bpy.types.Operator):
    """Pick this (ZBrush picker: Material / Stroke) - the picker closes"""
    bl_idname = 'mch.zb_set'
    bl_label = 'ZBrush Pick'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    prop: StringProperty()
    value: StringProperty()

    def execute(self, context):
        zb = context.scene.mch_zb
        if self.prop in {'matcap', 'stroke'}:
            try:
                setattr(zb, self.prop, self.value)
            except (TypeError, ValueError) as ex:
                self.report({'WARNING'}, str(ex).splitlines()[0])
        close_popup(context)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_texture(_ZBPoll, bpy.types.Operator):
    """Use this texture (the Paint brush stamps it; empty: Texture Off)"""
    bl_idname = 'mch.zb_texture'
    bl_label = 'ZBrush Texture'
    bl_options = {'REGISTER', 'INTERNAL'}
    path: StringProperty(subtype='FILE_PATH')

    def execute(self, context):
        self.report({'INFO'}, set_texture(context, self.path))
        close_popup(context)
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_texture_folder(_ZBPoll, bpy.types.Operator):
    """Pick a folder of texture images"""
    bl_idname = 'mch.zb_texture_folder'
    bl_label = 'Texture Folder'
    bl_options = {'INTERNAL'}
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        zb = context.scene.mch_zb
        zb.tex_dir = self.directory
        zb.tex_source = 'FOLDER'
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_tex_stamp(_ZBPoll, bpy.types.Operator):
    """Texture stamp (ZBrush DragRect, Paint brush + Texture): drag from the centre - how far is the size, the
    direction turns it; a click stamps at Draw Size.  Symmetry stamps the mirror too; the mask protects"""
    bl_idname = 'mch.zb_tex_stamp'
    bl_label = 'Texture Stamp'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        self.c = (event.mouse_region_x, event.mouse_region_y)
        self.half, self.angle = 0.0, 0.0
        self.path = current_texture(context)
        px = texture_pixels(self.path)
        if px is None:
            self.report({'WARNING'}, 'Texture stamp: the texture cannot be read')
            return {'CANCELLED'}
        self.aspect = px.shape[0] / float(px.shape[1])
        stamp_show(None, self.path)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            dx, dy = event.mouse_region_x - self.c[0], event.mouse_region_y - self.c[1]
            self.half = math.hypot(dx, dy)
            if self.half > 2.0:
                self.angle = math.atan2(dy, dx) - math.pi / 2       # dragging up = upright
            _STAMP['rect'] = stamp_rect(self.c, self.half, self.angle, self.aspect) if self.half > 2.0 else None
            if context.area:
                context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            stamp_hide()
            half = self.half if self.half >= 6.0 else float(context.scene.mch_zb.draw_size)
            try:
                msg = apply_stamp(context, self.c, half, self.angle if self.half >= 6.0 else 0.0)
            except (RuntimeError, ValueError, MemoryError) as ex:
                msg = 'Texture stamp: ' + str(ex).splitlines()[0]
            self.report({'INFO'}, msg)
            if context.area:
                context.area.tag_redraw()
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            stamp_hide()
            if context.area:
                context.area.tag_redraw()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_zb_alpha_folder(_ZBPoll, bpy.types.Operator):
    """Pick a folder of alpha images"""
    bl_idname = 'mch.zb_alpha_folder'
    bl_label = 'Alpha Folder'
    bl_options = {'INTERNAL'}
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        zb = context.scene.mch_zb
        zb.alpha_dir = self.directory
        zb.alpha_source = 'FOLDER'
        _bump()
        return {'FINISHED'}


class MCH_OT_zb_close(bpy.types.Operator):
    """Close the ZBrush menu"""
    bl_idname = 'mch.zb_close'
    bl_label = 'Close ZBrush Menu'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return on(context) and popup_open(context)

    def execute(self, context):
        close_popup(context)
        return {'FINISHED'}


CLASSES = (MCH_PG_ZBrush, MCH_OT_zb_action, MCH_OT_zb_brush, MCH_OT_zb_append, MCH_OT_zb_subtool, MCH_OT_zb_press,
           MCH_OT_zb_restore_tool, MCH_OT_zb_nav, MCH_OT_zb_viewdrag, MCH_OT_zb_popup, MCH_OT_zb_brush_pick,
           MCH_OT_zb_switch, MCH_OT_zb_style, MCH_OT_zb_obj_press, MCH_OT_zb_alpha, MCH_OT_zb_alpha_edit,
           MCH_OT_zb_alpha_folder, MCH_OT_zb_set, MCH_OT_zb_texture, MCH_OT_zb_texture_folder, MCH_OT_zb_tex_stamp, MCH_OT_zb_close)
_keymaps = []

# (key, ctrl, shift, alt, operator, properties)
KEYS = (
    ('LEFTMOUSE', False, False, False, 'mch.zb_press', {}), ('LEFTMOUSE', False, True, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', False, False, True, 'mch.zb_press', {}), ('LEFTMOUSE', True, False, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', True, False, True, 'mch.zb_press', {}), ('LEFTMOUSE', True, True, False, 'mch.zb_press', {}),
    ('LEFTMOUSE', True, True, True, 'mch.zb_press', {}),
    ('SPACE', False, False, False, 'mch.zb_popup', {}), ('RIGHTMOUSE', False, False, False, 'mch.zb_popup', {}),
    ('RIGHTMOUSE', False, False, True, 'mch.zb_popup', {}),         # 0.24.63 Alt + right drag = move the view
    ('S', False, False, False, 'mch.zb_popup', {'focus': 'draw_size'}),
    ('U', False, False, False, 'mch.zb_popup', {'focus': 'z_intensity'}),
    ('O', False, False, False, 'mch.zb_popup', {'focus': 'focal_shift'}),
    ('B', False, False, False, 'mch.zb_brush_pick', {}), ('ESC', False, False, False, 'mch.zb_close', {}),
    ('X', False, False, False, 'mch.zb_action', {'action': 'SYM_X'}),
    ('D', False, False, False, 'mch.zb_action', {'action': 'SDIV_UP'}),
    ('D', False, True, False, 'mch.zb_action', {'action': 'DUPLICATE'}),     # 0.24.61 (asked: SDiv seldom used)
    ('D', True, False, False, 'mch.zb_action', {'action': 'DIVIDE'}),
    ('W', True, False, False, 'mch.zb_action', {'action': 'GROUPS_FROM_MASK'}),
    ('F', False, False, False, 'mch.zb_action', {'action': 'FRAME'}),
    ('F', False, True, False, 'mch.zb_action', {'action': 'POLYF'}),
)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_zb = bpy.props.PointerProperty(type=MCH_PG_ZBrush)
    wmt = bpy.types.WindowManager
    wmt.mch_zb_pop = StringProperty(default='', options={'SKIP_SAVE'})
    wmt.mch_zb_pop_xy = bpy.props.FloatVectorProperty(size=2, default=(0.0, 0.0), options={'SKIP_SAVE'})
    wmt.mch_zb_pop_focus = StringProperty(default='', options={'SKIP_SAVE'})
    wmt.mch_zb_scroll = FloatProperty(default=0.0, options={'SKIP_SAVE'})
    wmt.mch_zb_scroll_b = FloatProperty(default=0.0, options={'SKIP_SAVE'})
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:
        km = kc.keymaps.new(name='Sculpt', space_type='EMPTY')
        for key, ctrl, shift, alt, op, props in KEYS:
            kmi = km.keymap_items.new(op, key, 'PRESS', ctrl=ctrl, shift=shift, alt=alt)
            for k, v in props.items():
                setattr(kmi.properties, k, v)
            _keymaps.append((km, kmi))
        # ZBrush style in Object Mode (Select / Move): the canvas turns the view
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
        for ctrl, shift, alt in ((False, False, False), (False, True, False), (False, False, True),
                                 (True, False, False)):
            _keymaps.append((km, km.keymap_items.new('mch.zb_obj_press', 'LEFTMOUSE', 'PRESS', ctrl=ctrl,
                                                     shift=shift, alt=alt)))
    from . import zb_highpoly
    zb_highpoly.register()


def unregister():
    from . import zb_highpoly
    zb_highpoly.unregister()
    lasso_hide()
    stamp_hide()
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:      # (a keymap item freed with its key config: like ui_bars, never stop unregister)
            pass
    _keymaps.clear()
    wmt = bpy.types.WindowManager
    for name in ('mch_zb_pop', 'mch_zb_pop_xy', 'mch_zb_pop_focus', 'mch_zb_scroll', 'mch_zb_scroll_b'):
        if hasattr(wmt, name):
            delattr(wmt, name)
    if hasattr(bpy.types.Scene, 'mch_zb'):
        del bpy.types.Scene.mch_zb
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
