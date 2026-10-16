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
import os
import shutil
import uuid
from collections import defaultdict
from pathlib import Path

import bpy
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, StringProperty
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
        has_alpha = float(px[:, :, 3].min()) < 0.999
        if mode == 'AUTO':               # 0.24.6 transparent image -> alpha, else brightness
            mode = 'ALPHA' if has_alpha else 'LUMINANCE'
        if mode == 'ALPHA' and not has_alpha:
            mode = 'LUMINANCE'          # 0.24.5 no transparency (JPEG): use the brightness instead
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
               simplify=0.8, smooth=1, min_area=4, refresh=True):
    mask, w, h = _load_pixels(filepath, mode, threshold, invert)
    loops, used_tol, used_smooth = vectorize_mask(mask, w, h, simplify, smooth, min_area)
    folder = preset_folder()
    basename = re.sub(r'[^A-Za-z0-9_-]+', '_', name).strip('_')[:50] or 'Shape'
    stem = basename + '_' + uuid.uuid4().hex[:16]
    src = folder / (stem + '.png')
    save_thumbnail(filepath, src)       # 0.24.6 a small PNG (the list thumbnail), never the full image
    record = {'schema': SCHEMA, 'name': name, 'source': src.name, 'mode': mode,
              'threshold': threshold, 'invert': invert, 'simplify': used_tol,
              'smooth': used_smooth, 'min_area': min_area, 'size': [w, h], 'loops': loops}
    out = folder / (stem + '.json')
    try:
        out.write_text(json.dumps(record, separators=(',', ':')), encoding='utf-8')
    except Exception:
        src.unlink(missing_ok=True)
        raise
    if refresh:
        _refresh_previews()
    return out


THUMB_PX = 192


def save_thumbnail(filepath, dst, size=THUMB_PX):
    """PNG copy of an image at most ``size`` px (PNG / JPEG in, PNG out)."""
    img = bpy.data.images.load(str(filepath), check_existing=False)
    try:
        if not img.has_data:
            img.reload()
        _ = img.pixels[0]               # make sure the pixels are loaded before saving
        w, h = img.size
        if max(w, h) > size:
            r = size / max(w, h)
            img.scale(max(2, round(w * r)), max(2, round(h * r)))
        img.file_format = 'PNG'
        img.filepath_raw = str(dst)
        img.save()
    finally:
        bpy.data.images.remove(img, do_unlink=True)


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
    info = _INDEX.get(stem)
    if info is None:
        return 0
    key = _THUMBS.get(stem)
    if key is None:                     # resolved once per preset, not on every redraw
        thumb = _small_thumb(preset_folder() / info[2])
        if thumb is None:
            return 0
        key = _THUMBS[stem] = str(thumb)
    if key not in _preview_collection:
        _preview_collection.load(key, key, 'IMAGE')
    return _preview_collection[key].icon_id


_INDEX = {}          # stem -> (mtime, name, source file): each preset file is parsed once, not on every redraw
_ITEMS_KEY = [None]
_THUMBS = {}         # stem -> list thumbnail path


def _scan():
    """[(stem, mtime)] newest first; refreshes _INDEX for new / changed files."""
    entries = []
    try:
        with os.scandir(preset_folder()) as it:
            for e in it:
                if e.name.endswith('.json') and e.is_file():
                    entries.append((e.name[:-5], e.stat().st_mtime, e.path))
    except OSError:
        return []
    seen = set()
    for stem, mtime, path in entries:
        seen.add(stem)
        old = _INDEX.get(stem)
        if old is None or old[0] != mtime:
            try:
                with open(path, encoding='utf-8') as fh:
                    d = json.load(fh)
                _INDEX[stem] = (mtime, d.get('name', stem), d.get('source', ''))
            except (OSError, ValueError):
                _INDEX.pop(stem, None)
    for stem in list(_INDEX):
        if stem not in seen:
            del _INDEX[stem]
            _THUMBS.pop(stem, None)
    entries.sort(key=lambda t: t[1], reverse=True)
    return [(stem, mtime) for stem, mtime, _p in entries if stem in _INDEX]


def _small_thumb(src):
    """A small thumbnail for the list (0.24.6: big source images froze the list); made once."""
    if not src.is_file():
        return None
    try:
        if src.stat().st_size <= 120_000:
            return src
        small = src.with_name(src.stem + '_thumb.png')
        if not small.is_file():
            save_thumbnail(src, small)
        return small
    except (OSError, RuntimeError):
        return src


def list_presets():
    """[(stem, name)] newest first."""
    return [(stem, _INDEX[stem][1]) for stem, _m in _scan()]


def preset_items(self, context):
    global _items_cache
    scan = _scan()
    key = (tuple(scan), _preview_collection is not None and id(_preview_collection))
    if _ITEMS_KEY[0] == key and _items_cache:
        return _items_cache                 # nothing changed: no file reading, no thumbnail work
    items = []
    for i, (stem, name, _loops) in enumerate(builtin_shapes()):
        items.append((stem, name, name + ' (built-in shape)', preset_icon(stem), i))
    base = len(items)
    for i, (stem, _m) in enumerate(scan):
        name = _INDEX[stem][1]
        items.append((stem, name, name, preset_icon(stem), base + i))
    if not items:
        items = [('NONE', 'No Cut Presets', 'Use Import PNG / JPG to add one', 0, 0)]
    _items_cache = items   # Blender requires enum strings to stay referenced.
    _ITEMS_KEY[0] = (tuple(scan), _preview_collection is not None and id(_preview_collection))
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
    bl_label = 'Import Image Cut Shape'
    bl_description = ('Convert a black/white PNG or JPEG (or a PNG with alpha) into a reusable vector Custom Cut '
                      'Shape')
    bl_options = {'REGISTER'}
    filename_ext = '.png'
    filter_glob: StringProperty(default='*.png;*.jpg;*.jpeg', options={'HIDDEN'})
    # 0.24.6 several files at once (Shift / Ctrl / box select in the file browser)
    files: CollectionProperty(type=bpy.types.OperatorFileListElement, options={'HIDDEN', 'SKIP_SAVE'})
    directory: StringProperty(subtype='DIR_PATH', options={'HIDDEN', 'SKIP_SAVE'})
    shape_name: StringProperty(name='Preset Name', default='',
                               description='Name for a single file (several files keep their file names)')
    mode: EnumProperty(name='Foreground', items=[
        ('AUTO', 'Auto', 'Transparent images: opaque pixels; others: bright pixels'),
        ('LUMINANCE', 'White / Bright', 'Bright pixels become the shape'),
        ('ALPHA', 'Alpha Channel', 'Opaque pixels become the shape')], default='AUTO')
    threshold: FloatProperty(name='Threshold', default=0.5, min=0.0, max=1.0)
    invert: BoolProperty(name='Invert', default=False)
    simplify: FloatProperty(name='Simplify (px)', default=0.8, min=0, max=8,
                            description='Maximum outline deviation; reduced automatically if it would create overlaps')
    smooth: IntProperty(name='Smooth Steps', default=1, min=0, max=3,
                        description='Corner-cutting passes that remove pixel stair steps')
    min_area: IntProperty(name='Remove Specks (px)', default=4, min=0, max=500,
                          description='Islands and pinholes smaller than this many pixels are removed')

    def execute(self, context):
        paths = [str(Path(self.directory) / f.name) for f in self.files if f.name] if self.directory else []
        paths = [p for p in paths if Path(p).suffix.lower() in {'.png', '.jpg', '.jpeg'}] or [self.filepath]
        done, failed, last = [], [], None
        for fp in paths:
            try:
                name = (self.shape_name.strip() if len(paths) == 1 else '') or Path(fp).stem
                last = import_png(fp, name, self.mode, self.threshold, self.invert,
                                  self.simplify, self.smooth, self.min_area, refresh=False)
                done.append(name)
            except Exception as exc:
                failed.append(f'{Path(fp).name} ({str(exc).splitlines()[0][:60]})')
        if last is not None:
            _refresh_previews()
            context.scene.mch_png_preset = last.stem
            if hasattr(context.scene, 'mch_brush'):
                context.scene.mch_brush.shape = 'CUSTOM'
        if not done:
            self.report({'ERROR'}, 'Image import failed: ' + '; '.join(failed))
            return {'CANCELLED'}
        msg = f'Imported {len(done)} Cut shape(s)' + (f': {done[0]}' if len(done) == 1 else '')
        if failed:
            msg += ' | failed: ' + '; '.join(failed)
            self.report({'WARNING'}, msg)
        else:
            self.report({'INFO'}, msg)
        return {'FINISHED'}


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
            for t in (thumb, thumb.with_name(thumb.stem + '_thumb.png')):
                if t.is_file():
                    t.unlink()
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
