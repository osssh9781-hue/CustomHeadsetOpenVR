"""0.24.95 A picture behind the model (user: "hdri 배경 컬러 말고 내가 원하는 배경 이미지를 넣을 수 있게 해 줄래? 너가
기본으로 몇 장 넣어 줘 - 세로 가로, 그 이후에는 내가 폴더로 불러올게", "배경은 스튜디오 이미지처럼 해 줘"):

* the HDRI page, Background: Show the HDRI off - Colour or Image; Image: the camera sees the picture behind the model
  (the HDRI still lights it), Fill (the frame covered, the picture's edges cut) or Fit (the whole picture, the Colour
  round it) - fitted to the render frame (resolution, pixel aspect)
* 8 studio backdrops come with the add-on (``backgrounds/``, made by ``tools_dev/make_backgrounds.py``), each wide and
  tall; Choose Folder… adds the user's pictures (the folders inside it too) - nothing in that folder is changed
* previews 6 on a page (◀ Page n / m ▶), a click = that picture, behind the model
"""
from __future__ import annotations

import os
import time

import bpy
from bpy.props import EnumProperty, IntProperty, StringProperty

HERE = os.path.dirname(os.path.abspath(__file__))
BUILTIN_DIR = os.path.join(HERE, 'backgrounds')
BUILTIN, USER = 'B:', 'U:'
EXT = ('.jpg', '.jpeg', '.png', '.tif', '.tiff', '.webp', '.bmp', '.exr', '.hdr', '.tga')
LOOKS = (('white_sweep', 'Studio White'), ('light_grey', 'Light Grey'), ('mid_grey_spot', 'Grey Spot'),
         ('charcoal', 'Charcoal'), ('black_key', 'Black'), ('warm_paper', 'Warm Paper'), ('cool_blue', 'Cool Blue'),
         ('canvas', 'Canvas'))
PAGE = 6
SCAN_EVERY = 3.0
SCAN_MAX = 3000
_SCAN = {'dir': None, 'time': 0.0, 'files': []}
_PAGE = {'page': 0, 'cur': None, 'pages': 1, 'ids': []}


def builtin_files():
    """The add-on's own backdrops, look by look - wide then tall."""
    out = []
    for key, _n in LOOKS:
        for tag in ('land', 'port'):
            f = f'{key}_{tag}.jpg'
            if os.path.isfile(os.path.join(BUILTIN_DIR, f)):
                out.append(f)
    return out


def folder():
    from .workspace_ui import pref
    d = pref('bg_folder', '') or ''
    d = bpy.path.abspath(d) if d else ''
    return d if d and os.path.isdir(d) else ''


def user_files():
    """The pictures in the user's backdrop folder and the folders inside it (paths relative to it, '/' between)."""
    d = folder()
    if not d:
        return []
    now = time.monotonic()
    if _SCAN['dir'] == d and now - _SCAN['time'] < SCAN_EVERY:
        return _SCAN['files']
    out = []
    try:
        for root, dirs, files in os.walk(d):
            dirs[:] = sorted(x for x in dirs if not x.startswith('.'))
            rel = os.path.relpath(root, d)
            rel = '' if rel == '.' else rel.replace(os.sep, '/') + '/'
            for f in sorted(files):
                if f.lower().endswith(EXT) and not f.startswith('.'):
                    out.append(rel + f)
                    if len(out) >= SCAN_MAX:
                        break
            if len(out) >= SCAN_MAX:
                break
    except OSError:
        out = []
    if out == _SCAN['files']:
        out = _SCAN['files']
    _SCAN.update(dir=d, time=now, files=out)
    return out


def rescan():
    _SCAN['time'] = 0.0


def entries():
    """[(ident, label)] - the add-on's backdrops, then the user's."""
    names = dict(LOOKS)
    out = []
    for f in builtin_files():
        key, tag = f[:-4].rsplit('_', 1)
        out.append((BUILTIN + f, names.get(key, key) + (' - Tall' if tag == 'port' else '')))
    for f in user_files():
        out.append((USER + f, os.path.splitext(f.split('/')[-1])[0]))
    return out


def path(ident):
    if not ident:
        return ''
    if ident.startswith(BUILTIN):
        return os.path.join(BUILTIN_DIR, ident[len(BUILTIN):])
    if ident.startswith(USER):
        d = folder()
        return os.path.normpath(os.path.join(d, *ident[len(USER):].split('/'))) if d else ''
    return ''


def aspect(p):
    """Width / height of a picture (from its header when it can; else 16 : 9)."""
    from .mech_shader import _pic_size
    wh = _pic_size(p) if p else None
    if wh and wh[1]:
        return wh[0] / wh[1]
    return 16.0 / 9.0


def page_of(cur, ids):
    pages = max(1, -(-len(ids) // PAGE))
    if cur != _PAGE['cur']:
        _PAGE['cur'] = cur
        _PAGE['page'] = ids.index(cur) // PAGE if cur in ids else 0
    _PAGE['page'] = min(max(_PAGE['page'], 0), pages - 1)
    _PAGE['pages'], _PAGE['ids'] = pages, ids
    return _PAGE['page'], pages


def fit_scale(frame_aspect, image_aspect, fit):
    """(sx, sy): the frame's 0 .. 1 window coordinates -> the picture's, about the middle.  FILL covers the frame
    (the picture's long edges cut), FIT shows the whole picture (the colour round it)."""
    fa, ia = max(frame_aspect, 1e-6), max(image_aspect, 1e-6)
    if fit == 'FIT':
        return (fa / ia, 1.0) if fa > ia else (1.0, ia / fa)
    return (1.0, ia / fa) if fa > ia else (fa / ia, 1.0)


def frame_aspect(scene):
    r = scene.render
    return (r.resolution_x * r.pixel_aspect_x) / max(1e-6, r.resolution_y * r.pixel_aspect_y)


def _update(self, context):
    from . import mech_shader as ms
    ms._hdri_update(self, context)


class MCH_OT_mech_bg_image(bpy.types.Operator):
    """Put this picture behind the model (the HDRI page's Background: Image) - the HDRI still lights the model"""
    bl_idname = 'mch.mech_bg_image'
    bl_label = 'Background Picture'
    bl_options = {'REGISTER', 'UNDO'}
    ident: StringProperty(default='', options={'SKIP_SAVE'})

    def execute(self, context):
        from . import mech_shader as ms
        sc = context.scene
        p = path(self.ident)
        if not p or not os.path.isfile(p):
            self.report({'WARNING'}, f'Background: no picture "{self.ident}"')
            return {'CANCELLED'}
        sc.mch_mech_hdri_bg_image = self.ident
        sc.mch_mech_hdri_bg_mode = 'IMAGE'
        sc.mch_mech_hdri_show = False
        if ms.hdri_world(sc) is None:                       # (the picture is drawn by the HDRI world: on)
            try:
                ms.set_hdri(context)
            except (FileNotFoundError, RuntimeError) as ex:
                self.report({'WARNING'}, f'Background: the HDRI could not be put on ({ex})')
                return {'CANCELLED'}
        ms.hdri_sync(sc)
        self.report({'INFO'}, 'Background: ' + os.path.basename(p))
        return {'FINISHED'}


class MCH_OT_mech_bg_folder(bpy.types.Operator):
    """Choose the folder you keep your background pictures in (.jpg / .png / .tif / .exr ...; the folders inside it
    too): they come after the add-on's studio backdrops (nothing in the folder is changed)"""
    bl_idname = 'mch.mech_bg_folder'
    bl_label = 'Choose Background Folder'
    bl_options = {'INTERNAL'}
    directory: StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        from .workspace_ui import pref
        self.directory = pref('bg_folder', '') or ''
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .workspace_ui import prefs
        pr = prefs()
        if pr is None or not hasattr(pr, 'bg_folder'):
            self.report({'WARNING'}, 'Background Folder: the Mecha Lab preferences are not available')
            return {'CANCELLED'}
        pr.bg_folder = self.directory
        rescan()
        n = len(user_files())
        try:
            from . import side_panel
            side_panel.dirty()
        except ImportError:
            pass
        self.report({'INFO'}, f'Background Folder: {n} picture{"s" if n != 1 else ""} found')
        return {'FINISHED'}


class MCH_OT_mech_bg_page(bpy.types.Operator):
    """Turn the page of background previews (6 on a page; the page number: back to the picture in use)"""
    bl_idname = 'mch.mech_bg_page'
    bl_label = 'Background Previews Page'
    bl_options = {'INTERNAL'}
    step: IntProperty(default=1)

    def execute(self, context):
        pages = max(1, _PAGE['pages'])
        if self.step == 0:
            cur, ids = context.scene.mch_mech_hdri_bg_image, _PAGE['ids']
            _PAGE['page'] = ids.index(cur) // PAGE if cur in ids else 0
        else:
            _PAGE['page'] = (_PAGE['page'] + self.step) % pages
        return {'FINISHED'}


CLASSES = (MCH_OT_mech_bg_image, MCH_OT_mech_bg_folder, MCH_OT_mech_bg_page)
SCENE_PROPS = ('mch_mech_hdri_bg_mode', 'mch_mech_hdri_bg_image', 'mch_mech_hdri_bg_fit')


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    T = bpy.types.Scene
    T.mch_mech_hdri_bg_mode = EnumProperty(
        name='Behind the Model', items=[('COLOR', 'Colour', 'A colour of its own'),
                                        ('IMAGE', 'Picture', 'A picture (a studio backdrop or one of yours)')],
        default='COLOR', update=_update,
        description='What the camera sees behind the model when the HDRI background is hidden')
    T.mch_mech_hdri_bg_image = StringProperty(name='Background Picture', default=BUILTIN + 'white_sweep_land.jpg',
                                              update=_update)
    T.mch_mech_hdri_bg_fit = EnumProperty(
        name='Fit', items=[('FILL', 'Fill', 'The frame covered (the picture\'s edges cut off)'),
                           ('FIT', 'Fit', 'The whole picture (the Colour round it)')],
        default='FILL', update=_update)


def unregister():
    for p in SCENE_PROPS:
        try:
            delattr(bpy.types.Scene, p)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
