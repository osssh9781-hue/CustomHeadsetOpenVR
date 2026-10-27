"""0.24.58 Safety Save: Mecha Lab keeps its own recovery copy of the scene, so a crash loses little.

0.24.66 (crash safety for sculpting, ZBrush QuickSave style):

* the quiet-moment save also runs in Sculpt / paint modes: when the interval is due, something was changed since the
  last copy and you have rested ``Rest`` seconds (no stroke, no view drag - modal operators are watched every half
  second, a ZBrush-style press counts as a change).  Copies are written uncompressed (fast for big meshes).
* right before the steps that crash most (ZBrush DynaMesh, Decimate, Divide, ZRemesher, Mirror And Weld, Close
  Holes, Extract, Split, Merge, Del Hidden ...): a copy when anything changed since the last one (not the interval;
  at most one per 15 s).
* crash detection: each Blender session keeps a small marker file next to the copies (refreshed every minute and on
  every save, removed when Blender closes normally).  A marker whose Blender is gone means that session crashed (or
  was killed): on the next start a window offers its newest recovery copy (Open / Open Folder / Ignore).
  Nothing can be written at the moment of a crash itself (the process is already broken) - so the copies are made
  as often as is cheap instead.

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

import atexit
import json
import os
import sys
import tempfile
import time

import bpy
from bpy.app.handlers import persistent

FOLDER = 'MechaLab_Recovery'
TICK = 0.5                  # s between quiet-moment checks (cheap: modal operators, mode, unsaved flag)
HEARTBEAT = 60.0            # s between session marker refreshes
RISKY_GAP = 15.0            # s: at most one copy before risky steps per this
STALE = 600.0               # s: a marker not refreshed for this long belongs to a gone session
LAST = [0.0]                # time.monotonic() of the last save (0 = none yet this session)
LAST_PATH = ['']
LAST_SECONDS = [0.0]        # how long the last save took
ALLOW_BACKGROUND = [False]  # tests: save in background mode too
EDITED = [0.0]              # time.monotonic() of the last change seen (stroke, action, scene update)
BUSY = [0.0]                # time.monotonic() of the last interaction seen (any modal operator, a press)
BEAT = [0.0]
CRASH = [None]              # the crashed session found at start: dict(marker data) or None
QUIET_MODES = {'OBJECT', 'SCULPT', 'PAINT_VERTEX', 'PAINT_WEIGHT', 'PAINT_TEXTURE', 'SCULPT_CURVES',
               'SCULPT_GREASE_PENCIL', 'PAINT_GREASE_PENCIL'}


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
    t = time.monotonic()
    bpy.ops.wm.save_as_mainfile(filepath=tmp, copy=True, check_existing=False, compress=False)
    if os.path.exists(path):
        os.replace(path, path[:-len('.blend')] + '_prev.blend')
    os.replace(tmp, path)
    LAST[0] = time.monotonic()
    LAST_SECONDS[0] = LAST[0] - t
    LAST_PATH[0] = path
    write_marker()
    return path


def changed():
    """Something was changed since the last copy (or none was made yet this session)."""
    return LAST[0] == 0.0 or EDITED[0] > LAST[0]


def note_edit():
    """A change happened now (a stroke starts, a shelf action, a scene update)."""
    EDITED[0] = BUSY[0] = time.monotonic()


def before_risky(why=''):
    """Right before a step that may crash Blender: a copy when anything changed since the last one.  Never raises."""
    try:
        if not _active() or not _dirty() or not changed():
            return ''
        if LAST[0] and time.monotonic() - LAST[0] < RISKY_GAP:
            return ''
        path = save_now()
        print(f'[Mecha Lab] Safety Save before {why}: {path} ({LAST_SECONDS[0]:.1f} s)')
        return path
    except (OSError, RuntimeError, AttributeError, TypeError) as ex:
        print('[Mecha Lab] Safety Save failed:', ex)
        return ''


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
    """No modal operator running in any window and Object / Sculpt / paint mode (not Edit Mode, like Blender's Auto
    Save: a consistent state)."""
    wm = context.window_manager
    if wm is None or getattr(context, 'mode', 'OBJECT') not in QUIET_MODES:
        return False
    for win in wm.windows:
        ops = getattr(win, 'modal_operators', None)
        if ops is None or len(ops):          # older Blender (no way to know) / a modal operator is running
            return False
    return True


def watch(context):
    """Note interaction (any modal operator: a stroke, a view drag) and changes (a sculpt / paint stroke)."""
    wm = context.window_manager
    now = time.monotonic()
    for win in (wm.windows if wm else ()):
        for op in getattr(win, 'modal_operators', ()):
            BUSY[0] = now
            name = getattr(op, 'bl_idname', '')
            if name.startswith(('SCULPT_OT', 'PAINT_OT', 'MESH_OT', 'TRANSFORM_OT', 'OBJECT_OT', 'MCH_OT')) \
                    and 'view' not in name.lower() and 'nav' not in name.lower():
                EDITED[0] = now


def rested():
    return time.monotonic() - BUSY[0] >= max(0.0, float(_pref('safety_rest', 3.0)))


def _tick():
    try:
        context = bpy.context
        if _active():
            watch(context)
            if _dirty() and due() and changed() and rested() and idle_ok(context):
                win = context.window_manager.windows[0]
                with context.temp_override(window=win):
                    checkpoint('(quiet moment)')
            if time.monotonic() - BEAT[0] >= HEARTBEAT:
                write_marker()
    except Exception as ex:                    # a timer must never stop Blender's loop
        print('[Mecha Lab] Safety Save timer:', ex)
    return TICK


# --- crash detection ----------------------------------------------------------------------------------------------

def marker_path(pid=None):
    return os.path.join(folder(), f'session_{os.getpid() if pid is None else pid}.json')


def write_marker():
    """This session's marker: alive (refreshed), which file, its newest recovery copy."""
    BEAT[0] = time.monotonic()
    if bpy.app.background and not ALLOW_BACKGROUND[0]:
        return
    try:
        os.makedirs(folder(), exist_ok=True)
        # (getattr: while Blender loads add-ons bpy.data cannot be read yet - 0.24.66 stopped the add-on there)
        data = {'pid': os.getpid(), 'file': getattr(bpy.data, 'filepath', ''), 'beat': time.time(),
                'recovery': LAST_PATH[0],
                'saved': (time.time() - (time.monotonic() - LAST[0])) if LAST[0] else 0.0,
                'started': START[0], 'blender': bpy.app.version_string}
        tmp = marker_path() + '.tmp'
        with open(tmp, 'w', encoding='utf-8') as f:
            json.dump(data, f)
        os.replace(tmp, marker_path())
    except Exception as ex:                    # (best effort: never stop Blender or the add-on for a marker)
        print('[Mecha Lab] Safety Save marker:', ex)


START = [time.time()]


def remove_marker():
    try:
        os.remove(marker_path())
    except OSError:
        pass


def pid_alive(pid):
    if pid == os.getpid():
        return True
    if sys.platform == 'win32':
        import ctypes
        k = ctypes.WinDLL('kernel32', use_last_error=True)
        h = k.OpenProcess(0x1000, False, int(pid))           # PROCESS_QUERY_LIMITED_INFORMATION
        if not h:
            return ctypes.get_last_error() == 5               # access denied: it exists
        code = ctypes.c_ulong()
        ok = k.GetExitCodeProcess(h, ctypes.byref(code))
        k.CloseHandle(h)
        return bool(ok) and code.value == 259                 # STILL_ACTIVE
    try:
        os.kill(int(pid), 0)
        return True
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except (OSError, ValueError, OverflowError):
        return False


def find_crashed():
    """Markers of sessions that did not close normally: their Blender is gone (or silent for STALE seconds).
    Returns (the newest one's data or None, all their paths)."""
    d = folder()
    try:
        names = [n for n in os.listdir(d) if n.startswith('session_') and n.endswith('.json')]
    except OSError:
        return None, []
    found, paths = [], []
    for n in names:
        path = os.path.join(d, n)
        try:
            with open(path, encoding='utf-8') as f:
                data = json.load(f)
            pid = int(data.get('pid', -1))
        except (OSError, ValueError, TypeError):
            paths.append(path)                                # a broken marker: just tidy it away
            continue
        if pid == os.getpid():
            continue
        if not pid_alive(pid) or time.time() - float(data.get('beat', 0)) > STALE:
            found.append(data)
            paths.append(path)
    found.sort(key=lambda m: float(m.get('beat', 0)))
    return (found[-1] if found else None), paths


def crash_text(m):
    """Lines describing the crashed session ``m`` for the window."""
    name = os.path.basename(m.get('file') or '') or 'untitled (never saved)'
    lines = [f'Blender closed unexpectedly last time ({name}).']
    rec = m.get('recovery') or ''
    if rec and os.path.isfile(rec):
        saved = float(m.get('saved') or os.path.getmtime(rec))
        lost = max(0.0, float(m.get('beat', saved)) - saved)
        lines.append(time.strftime('Mecha Lab recovery copy from %H:%M:%S', time.localtime(saved))
                     + (f' (about {lost / 60.0:.0f} min before it stopped)' if lost >= 60 else ''))
        lines.append('Open it now? (what is open now is replaced - save it first if needed)')
    else:
        lines.append('No Mecha Lab copy was made in that session. Blender\'s own: File > Recover > Auto Save.')
    return lines


KEEP_CRASH = 3              # crash copies kept (oldest go)


def check_crash():
    """At start: remember the newest crashed session (for the window), tidy the markers.  Its recovery copy is
    renamed ``<name>_crash_<date time>.blend`` so this session's own copies never overwrite it."""
    m, paths = find_crashed()
    for p in paths:
        try:
            os.remove(p)
        except OSError:
            pass
    rec = (m or {}).get('recovery') or ''
    if rec.endswith('_recovery.blend') and os.path.isfile(rec):
        saved = float(m.get('saved') or os.path.getmtime(rec))
        new = rec[:-len('_recovery.blend')] + time.strftime('_crash_%Y%m%d_%H%M%S.blend', time.localtime(saved))
        try:
            os.replace(rec, new)
            m['recovery'] = new
        except OSError:
            pass
        try:
            d = folder()
            crashes = sorted((os.path.join(d, n) for n in os.listdir(d) if '_crash_' in n and n.endswith('.blend')),
                             key=os.path.getmtime)
            for old in crashes[:-KEEP_CRASH]:
                os.remove(old)
        except OSError:
            pass
    CRASH[0] = m
    return m


def _offer():
    """Show the crash window once the UI is up (a timer, first run only)."""
    try:
        if CRASH[0] is None or not _pref('safety_crash_prompt', True):
            return None
        wm = bpy.context.window_manager
        if not wm or not wm.windows:
            return 1.0                                        # (no window yet: try again)
        win = wm.windows[0]
        area = next((a for a in win.screen.areas if a.type == 'VIEW_3D'), win.screen.areas[0])
        region = next((r for r in area.regions if r.type == 'WINDOW'), None)
        with bpy.context.temp_override(window=win, screen=win.screen, area=area, region=region):
            bpy.ops.mch.safety_crash('INVOKE_DEFAULT')
    except Exception as ex:
        print('[Mecha Lab] Safety Save crash window:', ex)
    return None


@persistent
def _on_load(_dummy):
    write_marker()


@persistent
def _on_depsgraph(_scene, _depsgraph):
    EDITED[0] = time.monotonic()


def _at_exit():
    remove_marker()


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


class MCH_OT_safety_crash(bpy.types.Operator):
    """Blender closed unexpectedly last time: open that session's newest Mecha Lab recovery copy"""
    bl_idname = 'mch.safety_crash'
    bl_label = 'Recover After a Crash'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if CRASH[0] is None:
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self, width=520, confirm_text='Open Recovery Copy')

    def draw(self, context):
        col = self.layout.column(align=True)
        for i, line in enumerate(crash_text(CRASH[0] or {})):
            col.label(text=line, icon='ERROR' if i == 0 else 'NONE')
        self.layout.operator('mch.safety_open_folder', icon='FILEBROWSER')

    def execute(self, context):
        m = CRASH[0] or {}
        rec = m.get('recovery') or ''
        CRASH[0] = None
        if not rec or not os.path.isfile(rec):
            self.report({'WARNING'}, 'No recovery copy from that session')
            return {'CANCELLED'}
        bpy.ops.wm.open_mainfile(filepath=rec, load_ui=False)
        return {'FINISHED'}

    def cancel(self, context):
        CRASH[0] = None


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
    sub.prop(prefs, 'safety_rest')
    box.prop(prefs, 'safety_crash_prompt')
    col = box.column(align=True)
    col.scale_y = 0.8
    col.label(text=f'Folder: {folder()}')
    last = latest()
    if last:
        col.label(text='Newest: ' + os.path.basename(last) + time.strftime('  (%Y-%m-%d %H:%M)',
                                                                         time.localtime(os.path.getmtime(last))))
    if LAST[0]:
        col.label(text=f'This session: last copy took {LAST_SECONDS[0]:.1f} s')
    row = box.row(align=True)
    row.operator('mch.safety_recover', icon='RECOVER_LAST')
    row.operator('mch.safety_open_folder', icon='FILEBROWSER')
    row.operator('mch.safety_save_now', icon='FILE_TICK')


CLASSES = (MCH_OT_safety_save_now, MCH_OT_safety_open_folder, MCH_OT_safety_recover, MCH_OT_safety_crash)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background:
        start()


def start():
    """The session part (not in background): timers, handlers, the crash check.  Runs while Blender loads add-ons,
    when bpy.data cannot be read: nothing here reads it (the marker is written by the first tick)."""
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=TICK, persistent=True)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    if _on_depsgraph not in bpy.app.handlers.depsgraph_update_post:
        bpy.app.handlers.depsgraph_update_post.append(_on_depsgraph)
    try:
        if check_crash() is not None:
            bpy.app.timers.register(_offer, first_interval=2.0)
    except Exception as ex:
        print('[Mecha Lab] Safety Save crash check:', ex)
    BEAT[0] = 0.0                                  # the first tick writes the marker
    atexit.register(_at_exit)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if bpy.app.timers.is_registered(_offer):
        bpy.app.timers.unregister(_offer)
    for lst, fn in ((bpy.app.handlers.load_post, _on_load), (bpy.app.handlers.depsgraph_update_post, _on_depsgraph)):
        if fn in lst:
            lst.remove(fn)
    atexit.unregister(_at_exit)
    remove_marker()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
