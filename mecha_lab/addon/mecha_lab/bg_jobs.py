"""0.24.86 Heavy actions in a background process: Quad Remesh and Re-Fix run in a second Blender while the window
stays live.  The mesh goes out as a small .blend (the one datablock), the worker (``bg_worker.py``) runs the action
exactly as the add-on would, the result comes back as a .blend and is swapped onto the object - unless the object's
mesh changed meanwhile (then the result is dropped and said).  A timer polls the worker; Cancel kills it.

``start`` / ``cancel`` / ``poll`` / ``status`` / ``draw_status``; ``BG_MIN`` faces and the shelf's Background toggle
decide when an action goes to the background.
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
import tempfile
import time

import bpy

BG_MIN = 20_000                   # faces: below this the action runs inline (the start-up of a second Blender costs ~2 s)
JOBS = {}                         # object name -> job dict
_TIMER_ON = False
KINDS = {'QUAD_REMESH': 'Quad Remesh', 'REFIX': 'Re-Fix'}


def _worker_cmd(job_json):
    """The command for one worker: Blender itself in background mode, or this python with the bpy module."""
    here = os.path.dirname(os.path.abspath(__file__))
    script = os.path.join(here, 'bg_worker.py')
    parent = os.path.dirname(here)
    binary = bpy.app.binary_path
    if binary and os.path.basename(binary).lower().startswith('blender'):
        return [binary, '-b', '--factory-startup', '--python', script, '--', parent, job_json]
    return [sys.executable, script, parent, job_json]


def can_run():
    """A worker can be started: a Blender binary or a python with bpy, and a window to keep live (headless Blender
    runs everything inline, unless MECH_BG_FORCE asks for the worker - the tests)."""
    if bpy.app.background and not os.environ.get('MECH_BG_FORCE'):
        return False
    return bool(bpy.app.binary_path) or bool(getattr(sys, 'executable', ''))


def busy(ob):
    j = JOBS.get(ob.name)
    return j is not None and j['proc'].poll() is None


def start(context, ob, kind, params):
    """Launch ``kind`` on ``ob`` in the background.  Returns a message."""
    if ob.type != 'MESH' or ob.data is None:
        return f'{KINDS.get(kind, kind)}: not a mesh'
    if busy(ob):
        return f'{KINDS.get(kind, kind)}: already running on {ob.name} - wait or cancel it'
    me = ob.data
    d = tempfile.mkdtemp(prefix='mch_bg_')
    src = os.path.join(d, 'in.blend')
    out = os.path.join(d, 'out.blend')
    me.use_fake_user = True
    try:
        bpy.data.libraries.write(src, {me}, fake_user=True)
    finally:
        me.use_fake_user = False
    job = {'kind': kind, 'in': src, 'mesh': me.name, 'out': out, 'params': params}
    cmd = _worker_cmd(json.dumps(job))
    log = open(os.path.join(d, 'log.txt'), 'w')
    try:
        proc = subprocess.Popen(cmd, stdout=log, stderr=subprocess.STDOUT, cwd=d)
    except OSError as ex:
        log.close()
        return f'{KINDS.get(kind, kind)}: could not start the background Blender ({ex})'
    JOBS[ob.name] = dict(kind=kind, proc=proc, dir=d, out=out, log=log, started=time.perf_counter(), object=ob.name,
                         mesh=me.name, faces=len(me.polygons), verts=len(me.vertices), message='', done=False)
    _ensure_timer()
    return f'{KINDS.get(kind, kind)} started in the background on {ob.name} ({len(me.polygons):,} faces) - keep working'


def cancel(name):
    j = JOBS.get(name)
    if j is None:
        return 'nothing running'
    if j['proc'].poll() is None:
        try:
            j['proc'].kill()
            j['proc'].wait(timeout=5)
        except (OSError, subprocess.TimeoutExpired):
            pass
    _finish(j, dropped='cancelled')
    return f'{KINDS.get(j["kind"], j["kind"])} on {name}: cancelled'


def _finish(j, dropped=None):
    j['done'] = True
    try:
        j['log'].close()
    except (OSError, ValueError):
        pass
    if dropped:
        j['message'] = dropped
    for f in ('in.blend', 'out.blend', 'log.txt'):
        try:
            os.remove(os.path.join(j['dir'], f))
        except OSError:
            pass
    try:
        os.rmdir(j['dir'])
    except OSError:
        pass


def _result_line(j):
    try:
        with open(os.path.join(j['dir'], 'log.txt')) as f:
            for line in f:
                if line.startswith('MCH_RESULT '):
                    return json.loads(line[len('MCH_RESULT '):])
    except (OSError, ValueError):
        return None
    return None


def _apply(j):
    """The finished worker's mesh onto the object (if its mesh is still the one that went out)."""
    from . import fast_decimate as fd
    ob = bpy.data.objects.get(j['object'])
    res = _result_line(j)
    if res is None:
        j['message'] = f'{KINDS.get(j["kind"], j["kind"])} on {j["object"]}: the background run failed (see log)'
        try:
            with open(os.path.join(j['dir'], 'log.txt')) as f:
                tail = f.read()[-600:]
            print('Mecha background job log:\n' + tail)
        except OSError:
            pass
        return
    if ob is None or ob.data is None or ob.data.name != j['mesh'] or len(ob.data.polygons) != j['faces'] \
            or len(ob.data.vertices) != j['verts']:
        j['message'] = (f'{KINDS.get(j["kind"], j["kind"])} on {j["object"]}: the part changed while it ran - '
                        f'the background result was dropped ({res.get("message", "")[:60]})')
        return
    if not os.path.exists(j['out']):
        j['message'] = f'{KINDS.get(j["kind"], j["kind"])} on {j["object"]}: no result file'
        return
    with bpy.data.libraries.load(j['out'], link=False) as (src, dst):
        dst.meshes = [res['name']] if res['name'] in src.meshes else list(src.meshes)[:1]
    if not dst.meshes or dst.meshes[0] is None:
        j['message'] = f'{KINDS.get(j["kind"], j["kind"])} on {j["object"]}: the result could not be read'
        return
    new = dst.meshes[0]
    new.use_fake_user = False
    fd.swap_mesh(ob, new)
    j['message'] = res.get('message', '') + f' | background, {time.perf_counter() - j["started"]:.0f} s'
    try:
        bpy.ops.ed.undo_push(message=KINDS.get(j['kind'], j['kind']))
    except RuntimeError:
        pass


def poll():
    """One look at every job (the timer): finished workers applied.  Returns the messages of jobs that just ended."""
    ended = []
    for name, j in list(JOBS.items()):
        if j['done']:
            continue
        if j['proc'].poll() is None:
            continue
        try:
            _apply(j)
        except Exception as ex:                       # noqa: BLE001  (a failure here must not kill the timer)
            j['message'] = f'{KINDS.get(j["kind"], j["kind"])} on {name}: {ex}'
        _finish(j)
        ended.append(j['message'])
        print('Mecha:', j['message'])
    for name in [n for n, j in JOBS.items() if j['done'] and time.perf_counter() - j['started'] > 3600]:
        JOBS.pop(name, None)
    return ended


def _timer():
    global _TIMER_ON
    msgs = poll()
    if msgs:
        try:
            from . import workspace_ui
            for m in msgs:
                workspace_ui.toast(m) if hasattr(workspace_ui, 'toast') else None
        except Exception:
            pass
        _redraw()
    if any(not j['done'] for j in JOBS.values()):
        _redraw()
        return 0.5
    _TIMER_ON = False
    return None


def _redraw():
    try:
        for w in bpy.context.window_manager.windows:
            for a in w.screen.areas:
                if a.type == 'VIEW_3D':
                    a.tag_redraw()
    except (AttributeError, RuntimeError):
        pass


def _ensure_timer():
    global _TIMER_ON
    if _TIMER_ON:
        return
    try:
        bpy.app.timers.register(_timer, first_interval=0.5)
        _TIMER_ON = True
    except (ValueError, RuntimeError):
        _TIMER_ON = False


def status(ob):
    """'Quad Remesh running ... 12 s' for the object, or '' when nothing runs."""
    j = JOBS.get(ob.name) if ob is not None else None
    if j is None or j['done']:
        return ''
    return f'{KINDS.get(j["kind"], j["kind"])} running in the background ... {time.perf_counter() - j["started"]:.0f} s'


def last_message(ob):
    j = JOBS.get(ob.name) if ob is not None else None
    return j['message'] if j is not None and j['done'] else ''


def draw_status(layout, ob):
    """A status row with Cancel while a job runs on ``ob``; the last job's message after."""
    if ob is None:
        return
    s = status(ob)
    if s:
        r = layout.row(align=True)
        r.label(text=s, icon='TIME')
        r.operator('mch.bg_cancel', text='', icon='X').name = ob.name
    else:
        m = last_message(ob)
        if m:
            layout.label(text=m[:90], icon='INFO')


class MCH_OT_bg_cancel(bpy.types.Operator):
    """Cancel the background action running on this part"""
    bl_idname = 'mch.bg_cancel'
    bl_label = 'Cancel Background Action'
    bl_options = {'REGISTER'}
    name: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        msg = cancel(self.name)
        self.report({'INFO'}, msg)
        return {'FINISHED'}


CLASSES = (MCH_OT_bg_cancel,)


def register():
    for c in CLASSES:
        try:
            bpy.utils.register_class(c)
        except (ValueError, RuntimeError):
            pass


def unregister():
    for name in list(JOBS):
        try:
            cancel(name)
        except Exception:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except (ValueError, RuntimeError):
            pass
