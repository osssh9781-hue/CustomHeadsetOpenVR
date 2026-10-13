"""Mecha Lab PNG -> vector Custom Cut Shapes.

A PNG is converted once into closed vector loops (outer outlines + holes) and
stored as JSON next to a copy of the source image in the user config folder,
so presets are reusable from every .blend file.  The loops become a regular
shape of the shared shape palette: Cut / Split / Mask project them through the
same watertight frustum cutter as Lasso or Rectangle (see core_geometry).

v0.7.0 fixes the cause of "Boolean result is non-manifold" seen with v0.5.9:
pixels touching only at a corner produced contours sharing a vertex (bow-tie),
and the 2D curve fill of those contours was not watertight.  Now:

* the binary mask is cleaned (tiny islands/holes removed) and every diagonal
  "saddle" 2x2 block is resolved, so traced loops never touch each other;
* simplification is validated (no self/mutual intersections) and falls back
  to less simplification down to the raw pixel outline, which is always valid;
* loops are grouped by containment depth (outline / hole / island in hole).
"""
from __future__ import annotations

import json
import math
import re
import shutil
import uuid
from collections import defaultdict
from pathlib import Path

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
from bpy_extras.io_utils import ImportHelper

from . import core_geometry as cg

try:
    import bpy.utils.previews as previews
except ImportError:  # pragma: no cover
    previews = None

SCHEMA = 2
MAX_POINTS = 20000
_preview_collection = None
_items_cache = []


BUILTIN_PREFIX = 'MCH_BUILTIN_'
_BUILTIN = None
_ADDON_DIR = Path(__file__).resolve().parent


def builtin_shapes():
    """[(stem, name, loops)] shipped with the add-on (shapes/builtin_shapes.json;
    regenerate with tools_dev/make_shapes.py).  Never written to the user's folder."""
    global _BUILTIN
    if _BUILTIN is None:
        try:
            d = json.loads((_ADDON_DIR / 'shapes' / 'builtin_shapes.json').read_text(encoding='utf-8'))
            _BUILTIN = [(BUILTIN_PREFIX + sh['stem'], sh['name'], sh['loops']) for sh in d.get('shapes', [])]
        except (OSError, ValueError, KeyError):
            _BUILTIN = []
    return _BUILTIN


def is_builtin(stem):
    return bool(stem) and stem.startswith(BUILTIN_PREFIX)


def preset_folder():
    return Path(bpy.utils.user_resource('CONFIG', path='mecha_lab/cut_shapes', create=True))


# -----------------------------------------------------------------------------
# Raster cleanup and tracing
# -----------------------------------------------------------------------------


def _components(mask, w, h, value):
    """4-connected components of pixels equal to ``value``: list of index lists."""
    seen = bytearray(w * h)
    comps = []
    for start in range(w * h):
        if seen[start] or mask[start] != value:
            continue
        stack = [start]
        seen[start] = 1
        comp = []
        while stack:
            i = stack.pop()
            comp.append(i)
            x, y = i % w, i // w
            for j, ok in ((i - 1, x > 0), (i + 1, x < w - 1), (i - w, y > 0), (i + w, y < h - 1)):
                if ok and not seen[j] and mask[j] == value:
                    seen[j] = 1
                    stack.append(j)
        comps.append(comp)
    return comps


def clean_mask(mask, w, h, min_area=4):
    """Remove specks/pinholes and resolve diagonal saddles. Returns a new list."""
    mask = [1 if v else 0 for v in mask]
    if min_area > 0:
        for comp in _components(mask, w, h, 1):
            if len(comp) < min_area:
                for i in comp:
                    mask[i] = 0
        for comp in _components(mask, w, h, 0):
            touches_border = any((i % w) in (0, w - 1) or (i // w) in (0, h - 1) for i in comp)
            if len(comp) < min_area and not touches_border:
                for i in comp:
                    mask[i] = 1
    # Saddle: a 2x2 block with exactly two diagonal pixels set.  Filling the
    # block joins both pixels, so contours never share a single vertex.
    for _ in range(w * h):
        changed = False
        for y in range(h - 1):
            row, nxt = y * w, (y + 1) * w
            for x in range(w - 1):
                a, b = mask[row + x], mask[row + x + 1]
                c, d = mask[nxt + x], mask[nxt + x + 1]
                if a == d and b == c and a != b:
                    mask[row + x] = mask[row + x + 1] = mask[nxt + x] = mask[nxt + x + 1] = 1
                    changed = True
        if not changed:
            break
    return mask


def trace_mask(mask, width, height):
    """Pixel-edge contours: outer outlines CCW, holes CW (origin bottom-left)."""
    edges = defaultdict(list)
    for y in range(height):
        row = y * width
        for x in range(width):
            if not mask[row + x]:
                continue
            if y == 0 or not mask[(y - 1) * width + x]:
                edges[(x, y)].append((x + 1, y))
            if x == width - 1 or not mask[row + x + 1]:
                edges[(x + 1, y)].append((x + 1, y + 1))
            if y == height - 1 or not mask[(y + 1) * width + x]:
                edges[(x + 1, y + 1)].append((x, y + 1))
            if x == 0 or not mask[row + x - 1]:
                edges[(x, y + 1)].append((x, y))
    total = sum(map(len, edges.values()))
    if total > 400000:
        raise ValueError('Mask boundary is too complex; lower resolution or remove image noise')
    loops = []
    while edges:
        start = next(iter(edges))
        cur, points = start, []
        for _ in range(total + 1):
            points.append(cur)
            options = edges.get(cur)
            if not options:
                raise ValueError('Open boundary in imported PNG')
            nxt = options.pop()
            if not options:
                del edges[cur]
            cur = nxt
            if cur == start:
                break
        else:
            raise ValueError('PNG boundary tracing exceeded expected length')
        # Drop collinear pixel-edge vertices; keeps corners only.
        corners = []
        n = len(points)
        for i in range(n):
            a, b, c = points[i - 1], points[i], points[(i + 1) % n]
            if (b[0] - a[0]) * (c[1] - b[1]) - (b[1] - a[1]) * (c[0] - b[0]) != 0:
                corners.append(b)
        if len(corners) >= 4:
            loops.append(corners)
        if len(loops) > 4000:
            raise ValueError('Too many independent contours; remove mask noise')
    return loops


def _simplify_closed(loop, tolerance):
    if tolerance <= 0 or len(loop) <= 4:
        return list(loop)
    n = len(loop)
    a = min(range(n), key=lambda i: (loop[i][0], loop[i][1]))
    b = max(range(n), key=lambda i: math.dist(loop[i], loop[a]))
    if a > b:
        a, b = b, a
    first = cg.simplify_open(loop[a:b + 1], tolerance)
    second = cg.simplify_open(loop[b:] + loop[:a + 1], tolerance)
    out = first[:-1] + second[:-1]
    if len(out) < 3 or cg.signed_area(out) * cg.signed_area(loop) <= 0:
        return list(loop)
    return out


def _smooth_closed(loop, iterations):
    """Chaikin corner cutting to reduce pixel stair steps (area preserving-ish)."""
    for _ in range(iterations):
        n = len(loop)
        out = []
        for i in range(n):
            p, q = loop[i], loop[(i + 1) % n]
            out.append((0.75 * p[0] + 0.25 * q[0], 0.75 * p[1] + 0.25 * q[1]))
            out.append((0.25 * p[0] + 0.75 * q[0], 0.25 * p[1] + 0.75 * q[1]))
        loop = out
    return loop


def vectorize_mask(mask, w, h, tolerance=0.8, smooth=1, min_area=4):
    """Return (normalized loops, used tolerance, used smooth)."""
    mask = clean_mask(mask, w, h, min_area)
    raw = trace_mask(mask, w, h)
    if not raw:
        raise ValueError('No filled area was found in the PNG')
    attempts = []
    tol = tolerance
    for sm in (smooth, 0):
        t = tol
        while True:
            attempts.append((t, sm))
            if t <= 0.05:
                break
            t *= 0.5
    attempts.append((0.0, 0))
    chosen = None
    for t, sm in attempts:
        loops = [_simplify_closed(_smooth_closed(lp, sm), t) for lp in raw]
        loops = [cg.dedupe_loop(lp, 1e-6) for lp in loops]
        loops = [lp for lp in loops if len(lp) >= 3]
        if sum(len(lp) for lp in loops) > MAX_POINTS:
            continue
        if not cg.find_intersections(loops):
            chosen = (loops, t, sm)
            break
    if chosen is None:
        raise ValueError('Contour has too many points; increase Simplify or reduce PNG detail')
    loops, t, sm = chosen
    extent = float(max(w, h))
    out = [[[(x - w / 2) / extent, (y - h / 2) / extent] for x, y in lp] for lp in loops]
    return out, t, sm


def _load_pixels(filepath, mode, threshold, invert, max_pixels=512):
    image = bpy.data.images.load(filepath, check_existing=False)
    try:
        if not image.has_data:
            image.reload()
        w, h = image.size
        if w < 2 or h < 2:
            raise ValueError('PNG must be at least 2x2 pixels')
        if max(w, h) > max_pixels:
            ratio = max_pixels / max(w, h)
            image.scale(max(2, round(w * ratio)), max(2, round(h * ratio)))
            w, h = image.size
        import numpy as np
        a = np.empty(w * h * 4, dtype=np.float32)
        image.pixels.foreach_get(a)
        px = a.reshape(h, w, 4)
        if mode == 'ALPHA':
            values = px[:, :, 3]
        else:
            values = 0.2126 * px[:, :, 0] + 0.7152 * px[:, :, 1] + 0.0722 * px[:, :, 2]
        binary = values <= threshold if invert else values >= threshold
        if mode == 'LUMINANCE':
            binary &= (px[:, :, 3] > 0.01)
        return binary.ravel().tolist(), w, h
    finally:
        bpy.data.images.remove(image, do_unlink=True)


def import_png(filepath, name, mode='LUMINANCE', threshold=0.5, invert=False,
               simplify=0.8, smooth=1, min_area=4):
    mask, w, h = _load_pixels(filepath, mode, threshold, invert)
    loops, used_tol, used_smooth = vectorize_mask(mask, w, h, simplify, smooth, min_area)
    folder = preset_folder()
    basename = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')[:50] or 'Shape'
    stem = basename + '_' + uuid.uuid4().hex[:16]
    src = folder / (stem + '.png')
    shutil.copy2(filepath, src)
    record = {'schema': SCHEMA, 'name': name, 'source': src.name, 'mode': mode,
              'threshold': threshold, 'invert': invert, 'simplify': used_tol,
              'smooth': used_smooth, 'min_area': min_area, 'size': [w, h], 'loops': loops}
    out = folder / (stem + '.json')
    try:
        out.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    except Exception:
        src.unlink(missing_ok=True)
        raise
    _refresh_previews()
    return out


def load_loops(stem):
    """Validated normalized loops for a preset; upgrades v0.5.9 (schema 1) files."""
    if is_builtin(stem):
        for b_stem, _name, loops in builtin_shapes():
            if b_stem == stem:
                return loops
        raise cg.CutError('Built-in shape not found; reinstall Mecha Lab.')
    path = preset_folder() / (stem + '.json')
    if not path.is_file():
        raise cg.CutError('Select an imported PNG shape first (shape palette > thumbnails).')
    d = json.loads(path.read_text(encoding='utf-8'))
    loops = d.get('loops') or []
    if d.get('schema') == SCHEMA and loops:
        return loops
    if d.get('schema') == 1:
        if loops and not cg.find_intersections(loops):
            return loops
        src = preset_folder() / d.get('source', '')
        if not src.is_file():
            raise cg.CutError('This PNG shape was made by v0.5.9 and is invalid; re-import the PNG.')
        mask, w, h = _load_pixels(str(src), d.get('mode', 'LUMINANCE'), 0.5, False)
        loops, t, sm = vectorize_mask(mask, w, h, 0.8, 1, 4)
        d.update({'schema': SCHEMA, 'loops': loops, 'simplify': t, 'smooth': sm,
                  'threshold': 0.5, 'invert': False, 'size': [w, h]})
        path.write_text(json.dumps(d, separators=(',', ':')), encoding='utf-8')
        return loops
    raise cg.CutError('Unknown PNG shape data version.')


# -----------------------------------------------------------------------------
# Previews / enum
# -----------------------------------------------------------------------------


def _refresh_previews():
    global _preview_collection
    if previews is None:
        return
    if _preview_collection is not None:
        previews.remove(_preview_collection)
    _preview_collection = previews.new()


def preset_icon(stem):
    if previews is None:
        return 0
    global _preview_collection
    if _preview_collection is None:
        _preview_collection = previews.new()
    if is_builtin(stem):
        thumb = _ADDON_DIR / 'icons' / ('shape_' + stem[len(BUILTIN_PREFIX):].lower() + '.png')
        if not thumb.is_file():
            return 0
        key = str(thumb)
        if key not in _preview_collection:
            _preview_collection.load(key, key, 'IMAGE')
        return _preview_collection[key].icon_id
    try:
        d = json.loads((preset_folder() / (stem + '.json')).read_text(encoding='utf-8'))
    except (OSError, ValueError):
        return 0
    thumb = preset_folder() / d.get('source', '')
    if not thumb.is_file():
        return 0
    key = str(thumb)
    if key not in _preview_collection:
        _preview_collection.load(key, key, 'IMAGE')
    return _preview_collection[key].icon_id


def list_presets():
    """[(stem, name)] newest first."""
    out = []
    for f in sorted(preset_folder().glob('*.json'), key=lambda p: p.stat().st_mtime, reverse=True):
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            out.append((f.stem, d.get('name', f.stem)))
        except (OSError, ValueError):
            continue
    return out


def preset_items(self, context):
    global _items_cache
    items = []
    for i, (stem, name, _loops) in enumerate(builtin_shapes()):
        items.append((stem, name, name + ' (built-in shape)', preset_icon(stem), i))
    base = len(items)
    for i, (stem, name) in enumerate(list_presets()):
        items.append((stem, name, name, preset_icon(stem), base + i))
    if not items:
        items = [('NONE', 'No Cut Presets', 'Use Import PNG to add one', 0, 0)]
    _items_cache = items   # Blender requires enum strings to stay referenced.
    return _items_cache


def _preset_update(self, context):
    brush = getattr(context.scene, 'mch_brush', None)
    if brush is not None and self.mch_png_preset != 'NONE':
        brush.shape = 'CUSTOM'


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class MCH_OT_import_cut_png(bpy.types.Operator, ImportHelper):
    bl_idname = 'mch.import_cut_png'
    bl_label = 'Import PNG Cut Shape'
    bl_description = 'Convert a black/white or alpha PNG into a reusable vector Custom Cut Shape'
    bl_options = {'REGISTER'}
    filename_ext = '.png'
    filter_glob: StringProperty(default='*.png', options={'HIDDEN'})
    shape_name: StringProperty(name='Preset Name', default='')
    mode: EnumProperty(name='Foreground', items=[
        ('LUMINANCE', 'White / Bright', 'Bright pixels become the shape'),
        ('ALPHA', 'Alpha Channel', 'Opaque pixels become the shape')], default='LUMINANCE')
    threshold: FloatProperty(name='Threshold', default=0.5, min=0.0, max=1.0)
    invert: BoolProperty(name='Invert', default=False)
    simplify: FloatProperty(name='Simplify (px)', default=0.8, min=0, max=8,
                            description='Maximum outline deviation; reduced automatically if it would create overlaps')
    smooth: IntProperty(name='Smooth Steps', default=1, min=0, max=3,
                        description='Corner-cutting passes that remove pixel stair steps')
    min_area: IntProperty(name='Remove Specks (px)', default=4, min=0, max=500,
                          description='Islands and pinholes smaller than this many pixels are removed')

    def execute(self, context):
        try:
            name = self.shape_name.strip() or Path(self.filepath).stem
            path = import_png(self.filepath, name, self.mode, self.threshold, self.invert,
                              self.simplify, self.smooth, self.min_area)
            context.scene.mch_png_preset = path.stem
            if hasattr(context.scene, 'mch_brush'):
                context.scene.mch_brush.shape = 'CUSTOM'
            self.report({'INFO'}, 'Imported vector Cut shape: ' + name)
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, f'PNG import failed: {exc}')
            return {'CANCELLED'}


class MCH_OT_delete_cut_preset(bpy.types.Operator):
    bl_idname = 'mch.delete_cut_preset'
    bl_label = 'Delete Selected Cut Shape'
    bl_description = 'Delete the selected PNG Custom Cut Shape from the user library (all .blend files)'
    bl_options = {'REGISTER'}

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        stem = context.scene.mch_png_preset
        if is_builtin(stem):
            self.report({'WARNING'}, 'Built-in shapes cannot be deleted')
            return {'CANCELLED'}
        f = preset_folder() / (stem + '.json')
        if not f.is_file():
            return {'CANCELLED'}
        try:
            d = json.loads(f.read_text(encoding='utf-8'))
            thumb = preset_folder() / Path(d.get('source', '')).name
            f.unlink()
            if thumb.is_file():
                thumb.unlink()
            _refresh_previews()
            self.report({'INFO'}, 'Cut shape removed')
            return {'FINISHED'}
        except Exception as exc:
            self.report({'ERROR'}, str(exc))
            return {'CANCELLED'}


class MCH_OT_stamp_png_cut(bpy.types.Operator):
    """v0.5.9 compatibility: the stamp is now the Custom shape of the Cut tool."""
    bl_idname = 'mch.stamp_png_cut'
    bl_label = 'Stamp Cut Preset'
    bl_description = 'Switch the Cut tool to the selected PNG shape (click = stamp, drag = size)'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        if hasattr(context.scene, 'mch_brush'):
            context.scene.mch_brush.shape = 'CUSTOM'
        from . import workspace_ui
        workspace_ui.activate_mecha_tool(context, 'CUT')
        return {'FINISHED'}


class MCH_OT_pick_stamp_shape(bpy.types.Operator):
    """Use a built-in / imported shape as the stamp of Cut / Split (click = stamp, drag = size / rotate)"""
    bl_idname = 'mch.pick_stamp_shape'
    bl_label = 'Use Stamp Shape'
    bl_options = {'REGISTER', 'INTERNAL'}

    stem: StringProperty()

    def execute(self, context):
        try:
            context.scene.mch_png_preset = self.stem
        except TypeError:
            self.report({'WARNING'}, 'Shape not available')
            return {'CANCELLED'}
        context.scene.mch_brush.shape = 'CUSTOM'
        return {'FINISHED'}


def draw_builtin_row(layout):
    """One row of built-in shape buttons (icons) for the shape palette."""
    row = layout.row(align=True)
    for stem, name, _loops in builtin_shapes():
        iid = preset_icon(stem)
        kw = {'icon_value': iid} if iid else {'icon': 'MESH_PLANE'}
        row.operator('mch.pick_stamp_shape', text='', **kw).stem = stem
    return row


CLASSES = (MCH_OT_import_cut_png, MCH_OT_delete_cut_preset, MCH_OT_stamp_png_cut, MCH_OT_pick_stamp_shape)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_png_preset = EnumProperty(name='PNG Cut Shapes', items=preset_items,
                                                  update=_preset_update)
    # Kept so v0.5.9 files load without missing-property noise.
    bpy.types.Scene.mch_stamp_size = FloatProperty(name='Width', default=1.0, min=0.001, precision=3)
    bpy.types.Scene.mch_stamp_depth = FloatProperty(name='Cut Depth', default=0.3, min=0.001, precision=3)
    bpy.types.Scene.mch_stamp_angle = FloatProperty(name='Rotation', default=0, subtype='ANGLE')


def unregister():
    global _preview_collection
    for n in ('mch_stamp_angle', 'mch_stamp_depth', 'mch_stamp_size', 'mch_png_preset'):
        if hasattr(bpy.types.Scene, n):
            delattr(bpy.types.Scene, n)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
    if _preview_collection is not None and previews:
        previews.remove(_preview_collection)
    _preview_collection = None
