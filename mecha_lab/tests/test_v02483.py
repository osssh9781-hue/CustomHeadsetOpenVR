"""0.24.58 Safety Save: a recovery copy of the whole file in Mecha Lab's own temp folder before heavy steps and
while idle (at most one per interval, only with unsaved changes); the open file, its path and Blender settings are
not touched."""
import inspect
import os
import tempfile
import time
from types import SimpleNamespace

from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import concept_move as cm, cut_engine as ce, safety_save as ss, workspace_ui

mecha_lab.register()
fresh()
C = bpy.context
src = inspect.getsource(workspace_ui.MCH_AddonPreferences)
check('Preferences: Safety Save on, every 3 minutes', "safety_save: BoolProperty(name='Safety Save', default=True" in src
      and "safety_minutes: FloatProperty(name='Every (min)', default=3.0" in src)
p = SimpleNamespace(safety_save=True, safety_minutes=3.0)     # add-on preferences do not exist in background
ss._pref = lambda name, default: getattr(p, name, default)
TMP = tempfile.mkdtemp(prefix='mch_safety_')
ss.folder = lambda: TMP                              # the test writes into its own folder
cube('P', size=1.0)
check('Background (tests, command line): no save unless asked', ss.checkpoint('test') == '')
ss.ALLOW_BACKGROUND[0] = True
ss.LAST[0] = 0.0
ss._dirty = lambda: False
check('No unsaved changes (just saved): nothing - your own file is up to date', ss.checkpoint('test') == '')
ss._dirty = lambda: True                 # (headless Blender 5.2 does not mark API edits as unsaved)
dirty0 = bpy.data.is_dirty
path = ss.checkpoint('test')
check('The first heavy step of a session saves the copy; the open file is not touched (no path, unsaved state)',
      path and os.path.exists(path) and os.path.basename(path).startswith(f'untitled_{os.getpid()}_')
      and path.endswith('_recovery.blend') and bpy.data.filepath == ''
      and bpy.data.is_dirty == dirty0, path)
check('... the next one within the interval does not', ss.checkpoint('test') == '')
p.safety_minutes = 0.0
time.sleep(0.05)
path2 = ss.checkpoint('test')
files = sorted(f for f in os.listdir(TMP) if f.endswith('.blend'))     # (0.24.66: + the session marker)
check('Every 0 min: each step; the copy before is kept as _prev, no half-written file left',
      path2 == path and files == sorted([os.path.basename(path), os.path.basename(path)[:-6] + '_prev.blend']), files)
p.safety_minutes = 3.0
with bpy.data.libraries.load(path) as (data_from, _data_to):
    names = list(data_from.objects)
check('The copy is a real .blend with the scene in it', 'P' in names, names)
check('Newest copy found for Open Last Recovery', ss.latest() == path and bpy.ops.mch.safety_recover.poll())
p.safety_save = False
ss.LAST[0] = 0.0
check('Safety Save off: nothing', ss.checkpoint('test') == '')
p.safety_save = True
win = SimpleNamespace(modal_operators=[])
busy = SimpleNamespace(modal_operators=[object()])
check('Idle saves wait for a quiet moment: no modal operator, Object Mode (older Blender: never)',
      ss.idle_ok(SimpleNamespace(window_manager=SimpleNamespace(windows=[win]), mode='OBJECT'))
      and not ss.idle_ok(SimpleNamespace(window_manager=SimpleNamespace(windows=[win, busy]), mode='OBJECT'))
      and not ss.idle_ok(SimpleNamespace(window_manager=SimpleNamespace(windows=[win]), mode='EDIT_MESH'))
      and not ss.idle_ok(SimpleNamespace(window_manager=SimpleNamespace(windows=[SimpleNamespace()]), mode='OBJECT')))
a, b = ss.recovery_path('/w/Robot.blend'), ss.recovery_path('/other/Robot.blend')
check('Named after the file + an id of its folder: two Robot.blend in different folders get different copies; a '
      'recovered copy keeps saving under its first name',
      os.path.basename(a).startswith('Robot_') and a.endswith('_recovery.blend') and a != b
      and ss.recovery_path(a).endswith(os.path.basename(a)), (a, b))
check('Unsaved files: one copy per session (two untitled Blenders do not overwrite each other), and the save in '
      'progress has a per-Blender name', ss.recovery_path('') == ss.recovery_path('')
      and str(os.getpid()) in os.path.basename(ss.recovery_path(''))
      and "os.getpid()}_saving.blend" in inspect.getsource(ss.save_now))
ss.LAST[0], ss.LAST_PATH[0], ss.EDITED[0] = 5.0, '/x/old_recovery.blend', 9.0
ss._on_load(None)
check('Opening another file starts its own copies, interval and changes (the last file\'s were carried over)',
      ss.LAST[0] == 0.0 and ss.LAST_PATH[0] == '' and ss.EDITED[0] == 0.0)
check('Hooked before the heavy steps: every stroke tool, Concept Move, Path Move',
      'safety_save.checkpoint' in inspect.getsource(ce.StrokeLogic._run)
      and 'safety_save.checkpoint' in inspect.getsource(cm.MCH_OT_concept_move.execute)
      and 'safety_save.checkpoint' in inspect.getsource(cm.MCH_OT_concept_path.execute))
check('Preferences show it (folder, newest copy, Open Last Recovery / Open Folder / Save Now)',
      'safety_save.draw_prefs' in inspect.getsource(workspace_ui.MCH_AddonPreferences.draw))
bpy.ops.wm.open_mainfile(filepath=path, load_ui=False)
check('Open Last Recovery: the scene comes back', 'P' in bpy.data.objects)
summary()
