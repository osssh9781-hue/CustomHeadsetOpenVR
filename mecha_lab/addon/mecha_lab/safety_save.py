"""0.24.58 Safety Save: Mecha Lab keeps its own recovery copy of the scene, so a crash loses little.

Blender's own Auto Save (Preferences > Save & Load) only runs on its timer and waits while any modal operator is
running; nothing is written when Blender crashes.  Mecha Lab adds:

* before a heavy step (a stroke tool's Cut / Split / Base Mesh ..., Concept / Path Move) and
* every few minutes while Blender is idle (no modal operator, Object Mode)

a copy of the whole file to ``<temp>/MechaLab_Recovery/<file name>_recovery.blend`` (``copy=True``: the open file,
its path and its unsaved state are not touched; the user's own files and Blender settings are never changed).  At
most one save per interval (Preferences: Safety Save, Every N minutes, 0 = before every heavy step), only when
there are unsaved changes.  The copy is written to a temporary name first and then swapped in, the one before is
kept as ``_recovery_prev.blend`` - a crash during a save never leaves no copy.
Recover: Preferences > Mecha Lab > Safety Save > Open Last Recovery / Open Folder.
"""
from __future__ import annotations

import os
import tempfile
import time

import bpy

FOLDER = 'MechaLab_Recovery'
TICK = 30.0                 # s between idle checks
LAST = [0.0]                # time.monotonic() of the last save (0 = none yet this session)
LAST_PATH = ['']
ALLOW_BACKGROUND = [False]  # tests: save in background mode too


def _pref(name, default):
    from .workspace_ui import pref
    return pref(name, default)


def folder():
    base = ''
    try:
        base = bpy.path.abspath(bpy.context.preferences.filepaths.temporary_directory or '')
    except AttributeError:
        pass
    if not base or not os.path.isdir(base):
        base = tempfile.gettempdir()
    return os.path.join(base, FOLDER)


def recovery_path(filepath=None):
    stem = bpy.path.display_name_from_filepath(bpy.data.filepath if filepath is None else filepath) or 'untitled'
    if stem.endswith('_recovery'):             # a recovered copy keeps saving under its first name
        stem = stem[:-len('_recovery')] or 'untitled'
    return os.path.join(folder(), f'{stem}_recovery.blend')


def latest():
    """The newest recovery copy in the folder (any file name) or ''."""
    d = folder()
    try:
        files = [os.path.join(d, f) for f in os.listdir(d) if f.endswith('_recovery.blend')]
    except OSError:
        return ''
    return max(files, key=os.path.getmtime) if files else ''


def _active():
    return _pref('safety_save', True) and (not bpy.app.background or ALLOW_BACKGROUND[0])


def _dirty():
    return bpy.data.is_dirty


def due():
    minutes = max(0.0, float(_pref('safety_minutes', 3.0)))
    return LAST[0] == 0.0 or time.monotonic() - LAST[0] >= minutes * 60.0


def save_now():
    """Write the recovery copy now.  Returns its path (raises OSError / RuntimeError on failure)."""
    path = recovery_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path[:-len('.blend')] + '_saving.blend'
    if os.path.exists(tmp):
        os.remove(tmp)
    bpy.ops.wm.save_as_mainfile(filepath=tmp, copy=True, check_existing=False)
    if os.path.exists(path):
        os.replace(path, path[:-len('.blend')] + '_prev.blend')
    os.replace(tmp, path)
    LAST[0] = time.monotonic()
    LAST_PATH[0] = path
    return path


def checkpoint(why=''):
    """Before a heavy step: save the recovery copy when one is due.  Never raises; returns the path or ''."""
    try:
        if not _active() or not _dirty() or not due():
            return ''
        t = time.monotonic()
        path = save_now()
        print(f'[Mecha Lab] Safety Save{" before " + why if why else ""}: {path} ({time.monotonic() - t:.1f} s)')
        return path
    except (OSError, RuntimeError, AttributeError, TypeError) as ex:
        print('[Mecha Lab] Safety Save failed:', ex)
        return ''


def idle_ok(context):
    """No modal operator running in any window and Object Mode (a consistent state, like Blender's Auto Save)."""
    wm = context.window_manager
    if wm is None or getattr(context, 'mode', 'OBJECT') != 'OBJECT':
        return False
    for win in wm.windows:
        ops = getattr(win, 'modal_operators', None)
        if ops is None or len(ops):          # older Blender (no way to know) / a modal operator is running
            return False
    return True


def _tick():
    try:
        context = bpy.context
        if _active() and _dirty() and due() and idle_ok(context):
            win = context.window_manager.windows[0]
            with context.temp_override(window=win):
                checkpoint('(idle)')
    except Exception as ex:                    # a timer must never stop Blender's loop
        print('[Mecha Lab] Safety Save timer:', ex)
    return TICK


class MCH_OT_safety_save_now(bpy.types.Operator):
    """Write the Mecha Lab recovery copy now (your own file is not touched)"""
    bl_idname = 'mch.safety_save_now'
    bl_label = 'Save Recovery Copy Now'

    def execute(self, context):
        try:
            path = save_now()
        except (OSError, RuntimeError) as ex:
            self.report({'ERROR'}, f'Safety Save failed: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Safety Save: {path}')
        return {'FINISHED'}


class MCH_OT_safety_open_folder(bpy.types.Operator):
    """Open the folder with the Mecha Lab recovery copies"""
    bl_idname = 'mch.safety_open_folder'
    bl_label = 'Open Recovery Folder'

    def execute(self, context):
        os.makedirs(folder(), exist_ok=True)
        bpy.ops.wm.path_open(filepath=folder())
        return {'FINISHED'}


class MCH_OT_safety_recover(bpy.types.Operator):
    """Open the newest Mecha Lab recovery copy (replaces what is open now - save it first if you need it)"""
    bl_idname = 'mch.safety_recover'
    bl_label = 'Open Last Recovery'

    @classmethod
    def poll(cls, context):
        return bool(latest())

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        path = latest()
        if not path:
            self.report({'WARNING'}, 'No recovery copy yet')
            return {'CANCELLED'}
        bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
        return {'FINISHED'}


def draw_prefs(layout, prefs):
    box = layout.box()
    box.label(text='Safety Save (crash recovery copy)', icon='FILE_TICK')
    row = box.row()
    row.prop(prefs, 'safety_save')
    sub = row.row()
    sub.active = prefs.safety_save
    sub.prop(prefs, 'safety_minutes')
    col = box.column(align=True)
    col.scale_y = 0.8
    col.label(text=f'Folder: {folder()}')
    last = latest()
    if last:
        col.label(text='Newest: ' + os.path.basename(last) + time.strftime('  (%Y-%m-%d %H:%M)',
                                                                         time.localtime(os.path.getmtime(last))))
    row = box.row(align=True)
    row.operator('mch.safety_recover', icon='RECOVER_LAST')
    row.operator('mch.safety_open_folder', icon='FILEBROWSER')
    row.operator('mch.safety_save_now', icon='FILE_TICK')


CLASSES = (MCH_OT_safety_save_now, MCH_OT_safety_open_folder, MCH_OT_safety_recover)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=TICK, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
