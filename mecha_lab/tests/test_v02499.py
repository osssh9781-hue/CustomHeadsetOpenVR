"""0.24.66 Safety Save for sculpting: quiet-moment copies also in Sculpt Mode (after a rest, only when something
changed), a copy right before the ZBrush steps that crash most, uncompressed copies (fast), and crash detection: a
session marker, a gone session's copy offered at the next start (and kept from being overwritten)."""
import inspect
import os
import subprocess
import sys
import tempfile
import time
from types import SimpleNamespace

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import safety_save as ss, workspace_ui, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context
src = inspect.getsource(workspace_ui.MCH_AddonPreferences)
check('Preferences: Rest (s) 3 and Offer Recovery After a Crash', "safety_rest: FloatProperty(name='Rest (s)', "
      "default=3.0" in src and "safety_crash_prompt: BoolProperty(name='Offer Recovery After a Crash', default=True"
      in src and "'safety_rest'" in inspect.getsource(ss.draw_prefs))
p = SimpleNamespace(safety_save=True, safety_minutes=3.0, safety_rest=3.0, safety_crash_prompt=True)
ss._pref = lambda name, default: getattr(p, name, default)
TMP = tempfile.mkdtemp(prefix='mch_safety66_')
ss.folder = lambda: TMP
ss.ALLOW_BACKGROUND[0] = True
ss._dirty = lambda: True

# --- quiet moments ------------------------------------------------------------------------------------------------
win = SimpleNamespace(modal_operators=[])
wm = SimpleNamespace(windows=[win])
check('Quiet moments now also in Sculpt Mode and paint modes, still not in Edit Mode or during any modal operator',
      ss.idle_ok(SimpleNamespace(window_manager=wm, mode='SCULPT'))
      and ss.idle_ok(SimpleNamespace(window_manager=wm, mode='PAINT_VERTEX'))
      and not ss.idle_ok(SimpleNamespace(window_manager=wm, mode='EDIT_MESH'))
      and not ss.idle_ok(SimpleNamespace(window_manager=SimpleNamespace(
          windows=[SimpleNamespace(modal_operators=[object()])]), mode='SCULPT')))
ss.EDITED[0] = ss.BUSY[0] = 0.0
stroke = SimpleNamespace(modal_operators=[SimpleNamespace(bl_idname='SCULPT_OT_brush_stroke')])
ss.watch(SimpleNamespace(window_manager=SimpleNamespace(windows=[stroke])))
check('A sculpt stroke running = a change and interaction', ss.EDITED[0] > 0 and ss.BUSY[0] > 0)
ss.EDITED[0] = ss.BUSY[0] = 0.0
orbit = SimpleNamespace(modal_operators=[SimpleNamespace(bl_idname='VIEW3D_OT_rotate')])
ss.watch(SimpleNamespace(window_manager=SimpleNamespace(windows=[orbit])))
check('Turning the view = interaction only (no copy just for looking around)', ss.EDITED[0] == 0.0
      and ss.BUSY[0] > 0)
check('... and it must be followed by a rest (Rest seconds) before a copy', not ss.rested())
ss.BUSY[0] = time.monotonic() - 10.0
check('After 10 s without strokes or view drags: rested', ss.rested())
ss.LAST[0] = time.monotonic()
ss.EDITED[0] = ss.LAST[0] - 1.0
check('Nothing changed since the last copy: no new copy', not ss.changed())
ss.note_edit()
check('A change after it (a ZBrush stroke press / shelf action): a copy is wanted', ss.changed())
check('ZBrush strokes and shelf actions note the change', inspect.getsource(zs.MCH_OT_zb_press.invoke).count(
      '_edited()') >= 3 and '_edited()' in inspect.getsource(zs.MCH_OT_zb_action.execute))
check('The quiet-moment timer looks every half second (cheap checks) and needs: due, changed, rested, quiet',
      ss.TICK <= 0.5 and all(k in inspect.getsource(ss._tick) for k in ('due()', 'changed()', 'rested()',
                                                                          'idle_ok(')))

# --- before the risky ZBrush steps, in Sculpt Mode ----------------------------------------------------------------
zs.on = lambda c: getattr(c, 'mode', '') == 'SCULPT'
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=5)
ob = C.active_object
ob.name = 'Sculpt'
bpy.ops.object.mode_set(mode='SCULPT')
n0 = len(ob.data.polygons)
ss.LAST[0] = 0.0
C.scene.mch_zb.decimate = 25
msg = zs.run(C, 'DECIMATE')
path = ss.LAST_PATH[0]
check('ZBrush Decimate: a recovery copy right before it, made in Sculpt Mode', path and os.path.isfile(path)
      and C.mode == 'SCULPT' and len(ob.data.polygons) < n0, (path, msg))
with bpy.data.libraries.load(path) as (data_from, data_to):
    data_to.meshes = [n for n in data_from.meshes if n == ob.data.name]
check('... the copy holds the model as it was before the step', data_to.meshes
      and len(data_to.meshes[0].polygons) == n0, (n0, data_to.meshes and len(data_to.meshes[0].polygons)))
with open(path, 'rb') as f:
    head = f.read(7)
check('Copies are written uncompressed (quick for big sculpts)', head == b'BLENDER', head)
check('The risky steps: DynaMesh, Decimate, Divide, ZRemesher, Mirror And Weld, Close Holes, Extract, Split, Merge',
      {'DYNAMESH', 'DYNA_UPDATE', 'DECIMATE', 'DIVIDE', 'ZREMESH', 'MIRROR_WELD', 'CLOSE_HOLES', 'EXTRACT',
       'SPLIT_MASKED', 'MERGE_VISIBLE', 'DEL_HIDDEN'} <= zs.RISKY)
ss.note_edit()
check('... not again within 15 s', ss.before_risky('test') == '')
ss.LAST[0] = time.monotonic() - 20.0
ss.EDITED[0] = ss.LAST[0] - 1.0
check('... nor when nothing changed since the last copy', ss.before_risky('test') == '')
ss.note_edit()
check('... but after a change, 15 s later: yes', ss.before_risky('test') == path)
bpy.ops.object.mode_set(mode='OBJECT')

# --- crash detection ----------------------------------------------------------------------------------------------
ss.write_marker()
mine = ss.marker_path()
check('This session keeps a marker next to the copies (Blender, file, newest copy)', os.path.isfile(mine))
check('... refreshed every minute by the timer, removed when Blender closes normally (atexit) or the add-on goes',
      ss.HEARTBEAT <= 60 and 'write_marker()' in inspect.getsource(ss._tick)
      and 'atexit.register(_at_exit)' in inspect.getsource(ss.register)
      and 'remove_marker()' in inspect.getsource(ss.unregister))
m, paths = ss.find_crashed()
check('A running session (this one) is not a crash', m is None and mine not in paths)
gone = subprocess.Popen([sys.executable, '-c', 'pass'])
gone.wait()
rec = os.path.join(TMP, 'Robot_recovery.blend')
bpy.ops.wm.save_as_mainfile(filepath=rec, copy=True, check_existing=False)
saved = time.time() - 300
import json
with open(ss.marker_path(gone.pid), 'w') as f:
    json.dump({'pid': gone.pid, 'file': '/work/Robot.blend', 'beat': time.time() - 30, 'recovery': rec,
               'saved': saved, 'started': saved - 600}, f)
with open(ss.marker_path(os.getppid()), 'w') as f:                   # (another Blender still running)
    json.dump({'pid': os.getppid(), 'file': '/work/Other.blend', 'beat': time.time(), 'recovery': ''}, f)
m, paths = ss.find_crashed()
check('A marker whose Blender is gone = a crashed session; another live Blender is not',
      m is not None and m['pid'] == gone.pid and ss.marker_path(os.getppid()) not in paths)
lines = ss.crash_text(m)
check('The window says which file, when the copy was made and how much before it stopped',
      'Robot.blend' in lines[0] and 'recovery copy from' in lines[1] and 'min before' in lines[1], lines)
m = ss.check_crash()
crash_files = [n for n in os.listdir(TMP) if '_crash_' in n]
check('At start its copy is renamed _crash_<date time> (this session\'s copies cannot overwrite it), its marker goes',
      len(crash_files) == 1 and not os.path.exists(rec) and m['recovery'].endswith(crash_files[0])
      and not os.path.exists(ss.marker_path(gone.pid)) and os.path.exists(ss.marker_path(os.getppid())),
      crash_files)
os.remove(ss.marker_path(os.getppid()))
with open(ss.marker_path(4242424), 'w') as f:      # (a live pid, but silent for an hour: the pid was reused)
    json.dump({'pid': os.getppid(), 'file': '', 'beat': time.time() - 3600, 'recovery': ''}, f)
m2, paths2 = ss.find_crashed()
check('A marker not refreshed for 10 minutes counts as gone too (its pid may be reused); no copy: says Blender\'s '
      'own Auto Save', m2 is not None and 'Auto Save' in ' '.join(ss.crash_text(m2)))
os.remove(ss.marker_path(4242424))
check('The offer comes 2 s after start (a timer), as a window with Open Recovery Copy / Open Folder',
      "bpy.app.timers.register(_offer, first_interval=2.0)" in inspect.getsource(ss.register)
      and 'invoke_props_dialog' in inspect.getsource(ss.MCH_OT_safety_crash.invoke))
ss.CRASH[0] = m
r = bpy.ops.mch.safety_crash('EXEC_DEFAULT')
check('Open Recovery Copy: the crashed session\'s scene comes back', r == {'FINISHED'} and 'Sculpt' in bpy.data.objects
      and ss.CRASH[0] is None)
ss.remove_marker()
check('The marker is removed on a normal exit', not os.path.exists(mine))

summary()
