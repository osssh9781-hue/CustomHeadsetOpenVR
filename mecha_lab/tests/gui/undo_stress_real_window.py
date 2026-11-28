"""0.24.349 Ctrl+Z stress in a real window (run with --enable-event-simulate; ``-- off`` = without undo_guard):
parts with the handlers that read depsgraph update lists working (group outline, Place's BVH cache, edge runs,
zones, side cards), many edits, then Ctrl+Z / Ctrl+Shift+Z pressed fast, again and again.  A crash ends the
process (the log's last STEP line says where); else PASS lines."""
import os
import sys
import time

import bpy

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), 'addon'))
OFF = 'off' in sys.argv[sys.argv.index('--') + 1:] if '--' in sys.argv else False
ROUNDS = 6
STATE = {'i': 0, 'phase': 'edit', 'round': 0, 't0': time.time()}


def step(msg):
    print('STEP', msg, flush=True)


def win_area():
    win = bpy.context.window_manager.windows[0]
    area = next(a for a in win.screen.areas if a.type == 'VIEW_3D')
    region = next(r for r in area.regions if r.type == 'WINDOW')
    return win, area, region


def key(win, area, k, ctrl=False, shift=False):
    x, y = area.x + area.width // 2, area.y + area.height // 2
    win.event_simulate('MOUSEMOVE', 'NOTHING', x=x, y=y)
    if ctrl:
        win.event_simulate('LEFT_CTRL', 'PRESS')
    if shift:
        win.event_simulate('LEFT_SHIFT', 'PRESS')
    win.event_simulate(k, 'PRESS', ctrl=ctrl, shift=shift)
    win.event_simulate(k, 'RELEASE', ctrl=ctrl, shift=shift)
    if shift:
        win.event_simulate('LEFT_SHIFT', 'RELEASE')
    if ctrl:
        win.event_simulate('LEFT_CTRL', 'RELEASE')


def setup():
    import mecha_lab
    from mecha_lab import undo_guard as ug
    if OFF:
        ug.quiet = lambda: False
    C = bpy.context
    win, area, region = win_area()
    with C.temp_override(window=win, area=area, region=region):
        for i in range(6):
            bpy.ops.mesh.primitive_cube_add(size=1.0, location=(i * 1.5, 0, 0))
            bpy.ops.ed.undo_push(message='add')
        try:                                           # (a group: its outline cache is filled by drawing)
            for o in C.scene.objects:
                o.select_set(True)
            bpy.ops.mch.group_make()
        except Exception as ex:                        # noqa: BLE001
            print('note: group', ex)
    step('setup done, guard ' + ('OFF' if OFF else 'ON'))
    return 0.2


def tick():
    C = bpy.context
    win, area, region = win_area()
    i = STATE['i']
    STATE['i'] += 1
    with C.temp_override(window=win, area=area, region=region):
        if STATE['phase'] == 'edit':
            obs = [o for o in C.scene.objects if o.type == 'MESH']
            ob = obs[i % len(obs)] if obs else None
            if ob is not None:
                for o in C.scene.objects:
                    o.select_set(o == ob)
                C.view_layer.objects.active = ob
                kind = i % 4
                step(f'edit {i} {ob.name} kind {kind}')
                if kind == 0:
                    bpy.ops.transform.translate(value=(0, 0, 0.2))
                elif kind == 1:
                    bpy.ops.object.mode_set(mode='EDIT')
                    bpy.ops.mesh.select_all(action='SELECT')
                    bpy.ops.mesh.subdivide(number_cuts=1)
                    bpy.ops.object.mode_set(mode='OBJECT')
                elif kind == 2:
                    bpy.ops.object.modifier_add(type='BEVEL')
                else:
                    bpy.ops.object.duplicate()
                bpy.ops.ed.undo_push(message=f'edit {i}')
            bpy.ops.wm.redraw_timer(type='DRAW', iterations=1)
            if i % 12 == 11:
                STATE['phase'] = 'undo'
        else:
            n = i % 12
            if n < 8:
                step(f'ctrl+z {i}')
                key(win, area, 'Z', ctrl=True)
            else:
                step(f'ctrl+shift+z {i}')
                key(win, area, 'Z', ctrl=True, shift=True)
            if n == 11:
                STATE['phase'] = 'edit'
                STATE['round'] += 1
                step(f'round {STATE["round"]} done')
                if STATE['round'] >= ROUNDS:
                    from mecha_lab import undo_guard as ug
                    print(f'PASS {ROUNDS} rounds of edits + fast Ctrl+Z / Ctrl+Shift+Z without a crash '
                          f'({ug.COUNT["undo"]} undo / redo seen, guard {"OFF" if OFF else "ON"})', flush=True)
                    bpy.ops.wm.quit_blender()
                    return None
    return 0.03


def start():
    setup()
    bpy.app.timers.register(tick, first_interval=0.3)
    return None


bpy.app.timers.register(start, first_interval=1.0)
