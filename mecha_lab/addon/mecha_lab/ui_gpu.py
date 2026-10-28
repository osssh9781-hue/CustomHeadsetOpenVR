"""0.24.50 Drawing helpers for Mecha Lab's own viewport UI (Substance 3D Modeler look): dark rounded cards,
white text, big PNG icons, simple line glyphs.  Everything is drawn in region pixels with the gpu module;
nothing is added to the .blend (icons are read into GPU textures once and the temporary image is removed).
"""
from __future__ import annotations

import math
import os

import bpy

ICON_DIR = os.path.join(os.path.dirname(__file__), 'icons')

CARD = (0.085, 0.087, 0.095, 0.98)       # Modeler: near black cards, no border
CARD_EDGE = (0.25, 0.26, 0.29, 1.0)
BTN = (0.18, 0.185, 0.205, 1.0)
BTN_HOVER = (0.27, 0.28, 0.31, 1.0)
ACCENT = (0.24, 0.48, 0.96, 1.0)            # Modeler's blue
ORANGE = (1.0, 0.62, 0.16, 1.0)
TEXT = (0.95, 0.95, 0.97, 1.0)
TEXT_DIM = (0.62, 0.64, 0.68, 1.0)
TRACK = (0.22, 0.23, 0.26, 1.0)

_TEX = {}             # path -> GPUTexture (or None when it could not be read)


def card_color(edge=False):
    """0.24.59 a card's background with Preferences > Panel Opacity - only the card: icons, text, buttons and value
    bars on it stay solid."""
    try:
        from .workspace_ui import pref
        a = max(0.0, min(1.0, float(pref('panel_opacity', CARD[3]))))
    except (TypeError, ValueError, ImportError):
        a = CARD[3]
    c = CARD_EDGE if edge else CARD
    return (c[0], c[1], c[2], c[3] * a if edge else a)


def ui_factor(context, region=None, menu=False):
    """UI scale x a bump for big screens (4K at 100 % made everything tiny) x Preferences > Viewport Panels
    (0.24.58 ``menu``: x RMB Menu instead - the Mecha Menu has its own size)."""
    try:
        ui = context.preferences.system.ui_scale or 1.0      # 0 without a window
    except AttributeError:
        ui = 1.0
    region = region or getattr(context, 'region', None)
    h = getattr(region, 'height', 900) or 900
    big = min(2.0, max(1.0, h / (950.0 * ui)))
    from .workspace_ui import pref
    try:
        user = float(pref('menu_size' if menu else 'mecha_ui_size', 1.0))
    except (TypeError, ValueError):
        user = 1.0
    return ui * big * max(0.5, user)


def _shader(name):
    import gpu
    return gpu.shader.from_builtin(name)


def rounded_rect(x, y, w, h, r, color):
    """Filled rounded rectangle, (x, y) = bottom left."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    r = max(0.0, min(r, w / 2.0, h / 2.0))
    pts = [(x + w / 2.0, y + h / 2.0)]
    corners = ((x + w - r, y + h - r, 0), (x + r, y + h - r, 90), (x + r, y + r, 180), (x + w - r, y + r, 270))
    for cx, cy, a0 in corners:
        for i in range(7):
            a = math.radians(a0 + i * 15)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
    pts.append(pts[1])
    sh = _shader('UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'TRI_FAN', {'pos': pts})
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_float('color', color)
    batch.draw(sh)


def lines(segments, color, width=2.0):
    """Line segments [((x0, y0), (x1, y1))] with a real width."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    if not segments:
        return
    pts = [p for seg in segments for p in seg]
    sh = _shader('POLYLINE_UNIFORM_COLOR')
    batch = batch_for_shader(sh, 'LINES', {'pos': [(p[0], p[1], 0.0) for p in pts]})
    gpu.state.blend_set('ALPHA')
    sh.bind()
    vp = gpu.state.viewport_get()
    sh.uniform_float('viewportSize', (vp[2], vp[3]))
    sh.uniform_float('lineWidth', width)
    sh.uniform_float('color', color)
    batch.draw(sh)


def circle_pts(cx, cy, r, n=24, a0=0.0, a1=360.0):
    return [(cx + math.cos(math.radians(a0 + (a1 - a0) * i / n)) * r,
             cy + math.sin(math.radians(a0 + (a1 - a0) * i / n)) * r) for i in range(n + 1)]


def polyline(pts, color, width=2.0, closed=False):
    segs = list(zip(pts[:-1], pts[1:]))
    if closed and len(pts) > 2:
        segs.append((pts[-1], pts[0]))
    lines(segs, color, width)


def text(x, y, s, size, color=TEXT, align='LEFT', vcenter=True):
    """Text at (x, y); align LEFT / CENTER / RIGHT; vcenter puts y in the middle of the letters."""
    import blf
    blf.size(0, size)
    w, h = blf.dimensions(0, s)
    if align == 'CENTER':
        x -= w / 2.0
    elif align == 'RIGHT':
        x -= w
    if vcenter:
        y -= blf.dimensions(0, 'Hg')[1] * 0.35
    blf.color(0, *color)
    blf.position(0, x, y, 0)
    blf.draw(0, s)
    return w


def fit(s, size, width):
    """Shorten ``s`` with '…' so it fits ``width`` px."""
    import blf
    blf.size(0, size)
    if blf.dimensions(0, s)[0] <= width:
        return s
    while len(s) > 1 and blf.dimensions(0, s + '…')[0] > width:
        s = s[:-1]
    return s + '…'


def wrap2(s, size, width):
    """``s`` in at most two lines that fit ``width`` px (split at a space, the rest shortened with '…')."""
    import blf
    blf.size(0, size)
    if blf.dimensions(0, s)[0] <= width or ' ' not in s:
        return [fit(s, size, width)]
    words = s.split(' ')
    first = words[0]
    i = 1
    while i < len(words) and blf.dimensions(0, first + ' ' + words[i])[0] <= width:
        first += ' ' + words[i]
        i += 1
    rest = ' '.join(words[i:])
    return [fit(first, size, width), fit(rest, size, width)] if rest else [fit(first, size, width)]


def _texture(path, mono=False, thumb=0):
    """GPU texture of a PNG; ``mono``: only its bright strokes, as white (Modeler's white line icons; the
    dark tile the Mecha icons are drawn on disappears), tinted by the draw colour.  ``thumb``: scaled down to
    that many pixels first (0.24.60 alpha thumbnails - a 4K PSD alpha is not kept at full size)."""
    key = (path, mono, thumb)
    if key in _TEX:
        return _TEX[key]
    tex = None
    if path and os.path.isfile(path):
        img = None
        try:
            import gpu
            import numpy as np
            img = bpy.data.images.load(path, check_existing=False)
            w, h = img.size
            if thumb and max(w, h) > thumb:
                img.scale(thumb, thumb)
                w, h = img.size
            px = np.empty(w * h * 4, dtype=np.float32)
            img.pixels.foreach_get(px)
            if img.is_float:                     # 0.24.60 a float image (EXR MatCap) is linear: shown as sRGB
                px = px.reshape(-1, 4)
                c = np.clip(px[:, :3], 0.0, 1.0)
                px[:, :3] = np.where(c <= 0.0031308, c * 12.92, 1.055 * np.power(c, 1 / 2.4) - 0.055)
                px = px.reshape(-1)
            if mono:
                px = px.reshape(-1, 4)
                bright = px[:, :3].max(axis=1)
                px[:, 3] = np.clip((bright - 0.30) / 0.45, 0.0, 1.0) * px[:, 3]
                px[:, :3] = 1.0
                px = px.reshape(-1)
            tex = gpu.types.GPUTexture((w, h), format='RGBA16F', data=gpu.types.Buffer('FLOAT', w * h * 4, px))
        except Exception:
            tex = None
        finally:
            if img is not None:
                try:
                    bpy.data.images.remove(img)          # nothing stays in the user's file
                except (ReferenceError, RuntimeError):
                    pass
    _TEX[key] = tex
    return tex


def image_quad(path, corners, alpha=1.0, thumb=256):
    """0.24.60 Draw an image on any four corners (bottom left, bottom right, top right, top left) - a turned
    texture stamp preview.  False if not drawn."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    tex = _texture(path, False, thumb)
    if tex is None:
        return False
    sh = _shader('IMAGE_COLOR')
    batch = batch_for_shader(sh, 'TRI_FAN', {'pos': tuple(corners), 'texCoord': ((0, 0), (1, 0), (1, 1), (0, 1))})
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_sampler('image', tex)
    sh.uniform_float('color', (1.0, 1.0, 1.0, alpha))
    batch.draw(sh)
    return True


def icon_path(stem):
    return os.path.join(ICON_DIR, stem + '.png') if stem else ''


def image(path, x, y, size, alpha=1.0, mono=False, tint=TEXT, thumb=0):
    """Draw a PNG (cached GPU texture) in a size x size square, bottom left (x, y). False if not drawn.
    ``mono``: as a one-colour line icon in ``tint``."""
    import gpu
    from gpu_extras.batch import batch_for_shader
    tex = _texture(path, mono, thumb)
    if tex is None:
        return False
    sh = _shader('IMAGE_COLOR')
    batch = batch_for_shader(sh, 'TRI_FAN', {'pos': ((x, y), (x + size, y), (x + size, y + size), (x, y + size)),
                                             'texCoord': ((0, 0), (1, 0), (1, 1), (0, 1))})
    gpu.state.blend_set('ALPHA')
    sh.bind()
    sh.uniform_sampler('image', tex)
    sh.uniform_float('color', (tint[0], tint[1], tint[2], alpha) if mono else (1.0, 1.0, 1.0, alpha))
    batch.draw(sh)
    return True


def done():
    """Back to Blender's default blending after painting."""
    try:
        import gpu
        gpu.state.blend_set('NONE')
    except Exception:
        pass


def free_textures():
    _TEX.clear()


# --- glyphs: small line icons for actions that have no PNG (drawn in a size x size box) --------------------

def glyph(name, x, y, size, color=TEXT, width=2.0):
    s = size
    cx, cy = x + s / 2.0, y + s / 2.0
    P = lambda u, v: (x + u * s, y + v * s)
    if name == 'duplicate':
        polyline([P(.18, .30), P(.62, .30), P(.62, .74), P(.18, .74)], color, width, True)
        polyline([P(.38, .50), P(.38, .86), P(.82, .86), P(.82, .50), P(.62, .50)], color, width)
    elif name == 'redo':                                 # 0.24.82 Redo Last: a circling arrow
        import math as _m
        arc = [(cx + s * .30 * _m.cos(a), cy + s * .30 * _m.sin(a)) for a in [_m.radians(t) for t in range(-60, 230, 10)]]
        polyline(arc, color, width)
        tip = arc[0]
        lines([(tip, (tip[0] - s * .16, tip[1] - s * .02)), (tip, (tip[0] - s * .02, tip[1] + s * .16))], color, width)
    elif name == 'join':
        polyline([P(.12, .30), P(.46, .30), P(.46, .70), P(.12, .70)], color, width, True)
        polyline([P(.54, .30), P(.88, .30), P(.88, .70), P(.54, .70)], color, width, True)
        lines([(P(.40, .50), P(.60, .50))], color, width)
    elif name == 'delete':
        polyline([P(.28, .78), P(.32, .16), P(.68, .16), P(.72, .78)], color, width)
        lines([(P(.20, .78), P(.80, .78)), (P(.42, .86), P(.58, .86)), (P(.42, .30), P(.42, .64)),
               (P(.58, .30), P(.58, .64))], color, width)
    elif name == 'origin':
        polyline(circle_pts(cx, cy, s * .30), color, width)
        polyline(circle_pts(cx, cy, s * .06, 10), color, width)
    elif name == 'axes':
        lines([(P(.25, .25), P(.80, .25)), (P(.25, .25), P(.25, .80)), (P(.25, .25), P(.62, .55))], color, width)
    elif name == 'smooth':
        polyline([P(.12, .30), P(.30, .55), P(.50, .62), P(.70, .55), P(.88, .30)], color, width)
        lines([(P(.12, .74), P(.88, .74))], color, width)
    elif name == 'shade_flat':
        pts = [(cx + math.cos(math.radians(30 + 60 * i)) * s * .36, cy + math.sin(math.radians(30 + 60 * i)) * s * .36)
               for i in range(6)]
        polyline(pts, color, width, True)
        lines([((cx, cy), p) for p in pts[::2]], color, width)
    elif name == 'shade_smooth':
        polyline(circle_pts(cx, cy, s * .36), color, width)
        polyline(circle_pts(cx - s * .08, cy + s * .08, s * .16, 12, 100, 200), color, width)
    elif name == 'shade_auto':
        polyline(circle_pts(cx, cy, s * .36, 12, 90, 270), color, width)
        polyline([(cx, cy + s * .36), (cx + s * .31, cy + s * .18), (cx + s * .31, cy - s * .18), (cx, cy - s * .36)],
                 color, width)
        lines([((cx, cy + s * .36), (cx, cy - s * .36))], color, width)
    elif name == 'radial':
        polyline(circle_pts(cx, cy, s * .30), color, width)
        for k in range(6):
            a = math.radians(90 + k * 60)
            px, py = cx + math.cos(a) * s * .30, cy + math.sin(a) * s * .30
            polyline(circle_pts(px, py, s * .06, 8), color, width)
    elif name == 'kaleido':
        for k in range(3):
            a = math.radians(90 + k * 60)
            lines([((cx - math.cos(a) * s * .38, cy - math.sin(a) * s * .38),
                    (cx + math.cos(a) * s * .38, cy + math.sin(a) * s * .38))], color, width)
        polyline(circle_pts(cx, cy, s * .38), color, width * 0.7)
    elif name == 'grid':
        for u in (.18, .5, .82):
            for v in (.22, .56):
                polyline([P(u - .1, v), P(u + .1, v), P(u + .1, v + .22), P(u - .1, v + .22)], color, width, True)
    elif name == 'card':
        polyline([P(.15, .25), P(.85, .25), P(.85, .80), P(.15, .80)], color, width, True)
        lines([(P(.25, .64), P(.75, .64)), (P(.25, .48), P(.60, .48)), (P(.25, .36), P(.68, .36))], color, width)
    elif name in {'group', 'select_group'}:
        for a0, b0 in ((P(.12, .12), P(.38, .12)), (P(.62, .12), P(.88, .12)), (P(.12, .88), P(.38, .88)),
                       (P(.62, .88), P(.88, .88)), (P(.12, .12), P(.12, .38)), (P(.12, .62), P(.12, .88)),
                       (P(.88, .12), P(.88, .38)), (P(.88, .62), P(.88, .88))):
            lines([(a0, b0)], color, width)
        polyline([P(.28, .30), P(.50, .30), P(.50, .52), P(.28, .52)], color, width, True)
        polyline([P(.48, .50), P(.72, .50), P(.72, .72), P(.48, .72)], color, width, True)
        if name == 'select_group':
            polyline(circle_pts(cx, cy, s * .06, 8), color, width)
    elif name == 'ungroup':
        polyline([P(.14, .20), P(.42, .20), P(.42, .48), P(.14, .48)], color, width, True)
        polyline([P(.58, .52), P(.86, .52), P(.86, .80), P(.58, .80)], color, width, True)
        lines([(P(.46, .46), P(.56, .56))], color, width)
    elif name == 'merge':
        polyline([P(.10, .62), P(.34, .62), P(.34, .86), P(.10, .86)], color, width, True)
        polyline([P(.66, .62), P(.90, .62), P(.90, .86), P(.66, .86)], color, width, True)
        polyline([P(.30, .14), P(.70, .14), P(.70, .44), P(.30, .44)], color, width, True)
        lines([(P(.22, .60), P(.40, .46)), (P(.78, .60), P(.60, .46))], color, width)
    elif name in {'enter', 'exit'}:
        polyline([P(.45, .15), P(.85, .15), P(.85, .85), P(.45, .85)], color, width)
        if name == 'enter':
            lines([(P(.10, .50), P(.62, .50)), (P(.50, .62), P(.62, .50)), (P(.50, .38), P(.62, .50))], color, width)
        else:
            lines([(P(.62, .50), P(.10, .50)), (P(.22, .62), P(.10, .50)), (P(.22, .38), P(.10, .50))], color, width)
    elif name == 'cube':                         # 0.24.59 a part in the Layers panel
        polyline([P(.50, .88), P(.86, .70), P(.86, .30), P(.50, .12), P(.14, .30), P(.14, .70)], color, width, True)
        lines([(P(.14, .70), P(.50, .52)), (P(.86, .70), P(.50, .52)), (P(.50, .52), P(.50, .12))], color, width)
    elif name == 'curve':
        polyline([P(.12, .25), P(.28, .55), P(.45, .72), P(.62, .66), P(.75, .45), P(.88, .78)], color, width)
    elif name == 'quad':
        for t in (.2, .5, .8):
            lines([(P(t, .2), P(t, .8)), (P(.2, t), P(.8, t))], color, width)
    elif name == 'lowpoly':
        polyline([P(.50, .85), P(.85, .25), P(.15, .25)], color, width, True)
        lines([(P(.50, .85), P(.50, .25))], color, width)
    elif name in {'X', 'Y', 'Z'}:
        text(cx, cy, name, s * .55, color, 'CENTER')
    elif name == 'eye' or name == 'eye_off':
        polyline([P(.10, .50), P(.30, .70), P(.50, .76), P(.70, .70), P(.90, .50), P(.70, .30), P(.50, .24),
                  P(.30, .30)], color, width, True)
        polyline(circle_pts(cx, cy, s * .12, 12), color, width)
        if name == 'eye_off':
            lines([(P(.16, .16), P(.84, .84))], color, width)
    elif name == 'isolate':
        for a, b, c in ((P(.15, .35), P(.15, .15), P(.35, .15)), (P(.65, .15), P(.85, .15), P(.85, .35)),
                        (P(.85, .65), P(.85, .85), P(.65, .85)), (P(.35, .85), P(.15, .85), P(.15, .65))):
            polyline([a, b, c], color, width)
        polyline(circle_pts(cx, cy, s * .14, 12), color, width)
    elif name == 'check':
        polyline([P(.18, .52), P(.40, .28), P(.82, .74)], color, width)
    elif name == 'cross':
        lines([(P(.22, .22), P(.78, .78)), (P(.22, .78), P(.78, .22))], color, width)
    elif name == 'stack':
        for t in (.30, .50, .70):
            polyline([P(.18, t), P(.50, t + .12), P(.82, t)], color, width)
    elif name == 'arrow':
        polyline([P(.30, .85), P(.30, .20), P(.45, .35), P(.58, .12), P(.66, .16), P(.54, .40), P(.74, .42)],
                 color, width, True)
    elif name == 'star' or name == 'star_on':
        pts = []
        for i in range(10):
            r = s * (.40 if i % 2 == 0 else .17)
            a = math.radians(90 + i * 36)
            pts.append((cx + math.cos(a) * r, cy + math.sin(a) * r))
        polyline(pts, ORANGE if name == 'star_on' else color, width, True)
    elif name == 'menu':
        for t in (.3, .5, .7):
            lines([(P(.2, t), P(.8, t))], color, width)
    else:
        polyline(circle_pts(cx, cy, s * .3), color, width)
