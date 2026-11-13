"""0.24.153 (user: "왜 갑자기 중간 클릭으로 화면이 안 돌아가?" ... "3D 마우스 연결이 이상했나 봐"): a 3D mouse with a bad
connection sends motion events all the time.  MECHA LAB's middle-click gate (a click = the Mecha Menu, a drag = the
view turns) ended on the first 3D-mouse event, before the hand moved the drag distance - so a middle drag never turned
the view and a click never opened the menu.  Now 3D-mouse / trackpad events go on to Blender and the gate keeps
waiting.  The gate's modal is fed made-up events here; in a real window (simulated events, 0.24.152 vs this):
tests/gui/mmb_ndof_real_window.py."""
import glob
import os
import re
import types

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mecha_menu as mm, smart_move  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
gate = mm.MCH_OT_mecha_mmb_gate.modal
CALLS = []
real_bpy, real_open = mm.bpy, mm.open_menu
fake_ops = types.SimpleNamespace(view3d=types.SimpleNamespace(rotate=lambda *a, **k: CALLS.append('rotate')))
mm.bpy = types.SimpleNamespace(ops=fake_ops)
mm.open_menu = lambda context, source='': CALLS.append(('menu', source)) or True


def ev(t, v='NOTHING', x=100, y=100):
    return types.SimpleNamespace(type=t, value=v, mouse_x=x, mouse_y=y)


def new_op():
    CALLS.clear()
    return types.SimpleNamespace(x0=100, y0=100, limit=5)


try:
    # a drag while the 3D mouse sends motion
    op = new_op()
    spam = [gate(op, C, ev('NDOF_MOTION')) for _i in range(200)]
    check('a 3D mouse sending motion (200 events) while the middle button is down: each goes on to Blender, the gate '
          'keeps waiting', all(r == {'PASS_THROUGH'} for r in spam) and CALLS == [], {tuple(sorted(r)) for r in spam})
    small = gate(op, C, ev('MOUSEMOVE', x=103, y=101))
    more = [gate(op, C, ev('NDOF_MOTION')) for _i in range(50)]
    far = gate(op, C, ev('MOUSEMOVE', x=140, y=104))
    check('... the mouse moved under the drag distance: still waiting; past it: Blender\'s view turning starts, the gate '
          'ends', small == {'RUNNING_MODAL'} and all(r == {'PASS_THROUGH'} for r in more) and far == {'FINISHED'}
          and CALLS == ['rotate'], (small, far, CALLS))
    # a click while the 3D mouse sends motion
    op = new_op()
    for _i in range(120):
        gate(op, C, ev('NDOF_MOTION'))
    rel = gate(op, C, ev('MIDDLEMOUSE', 'RELEASE'))
    check('a middle click while the 3D mouse sends motion: the Mecha Menu', rel == {'FINISHED'}
          and CALLS == [('menu', 'middle click')], CALLS)
    # trackpad, 3D-mouse buttons
    op = new_op()
    rs = [gate(op, C, ev(t, v)) for t, v in (('TRACKPADPAN', 'NOTHING'), ('TRACKPADZOOM', 'NOTHING'),
                                             ('NDOF_BUTTON_FIT', 'PRESS'), ('NDOF_BUTTON_MENU', 'RELEASE'))]
    far = gate(op, C, ev('MOUSEMOVE', x=60, y=100))
    check('trackpad and 3D-mouse button events also go on without ending it; a drag after them turns the view',
          all(r == {'PASS_THROUGH'} for r in rs) and far == {'FINISHED'} and CALLS == ['rotate'], (rs, CALLS))
    # other events as before
    op = new_op()
    other = [gate(op, C, ev(t, v)) for t, v in (('A', 'PRESS'), ('LEFT_SHIFT', 'PRESS'), ('TIMER', 'NOTHING'))]
    esc = gate(op, C, ev('ESC', 'PRESS'))
    check('other events go on as before (0.24.54), Esc stops it with no menu', all(r == {'PASS_THROUGH'} for r in other)
          and esc == {'CANCELLED'} and CALLS == [])
    # a release that never came
    op = new_op()
    away = gate(op, C, ev('WINDOW_DEACTIVATE'))
    op2 = new_op()
    again = gate(op2, C, ev('MIDDLEMOUSE', 'PRESS'))
    check('the release lost (the window left, or a new middle press): the gate ends and the event goes on - never '
          'left waiting to open a menu later', away == {'FINISHED', 'PASS_THROUGH'}
          and again == {'FINISHED', 'PASS_THROUGH'} and CALLS == [])
finally:
    mm.bpy, mm.open_menu = real_bpy, real_open

# the 3D MOUSE: View default - the add-on's 3D-mouse key passes every event on
fake_self = types.SimpleNamespace()
r = smart_move.MCH_OT_smart_ndof.invoke(fake_self, C, ev('NDOF_MOTION'))
check('3D MOUSE: View (default): the add-on\'s 3D-mouse key passes the motion on to Blender (the view moves as in '
      'plain Blender)', not smart_move.ndof_parts_on(C) and r == {'PASS_THROUGH'})

# the add-on never writes Blender's own 3D-mouse settings (it only reads them for Smart Move's Blender axes)
src_dir = os.path.dirname(mecha_lab.__file__)
writes = []
for path in glob.glob(os.path.join(src_dir, '*.py')):
    for n, line in enumerate(open(path, encoding='utf-8'), 1):
        code = line.split('#', 1)[0]
        if re.search(r'\bndof_\w+\s*=(?!=)', code) and ('inputs' in code or 'prefs' in code or 'preferences' in code):
            writes.append(f'{os.path.basename(path)}:{n}')
check('Blender\'s 3D-mouse preferences: no assignment to them anywhere in the add-on\'s code (this bpy build has no 3D-mouse '
      'support, so the settings before / after are compared in tests/gui/mmb_ndof_real_window.py)', not writes, writes)
summary()
