"""0.24.82 Toasts: short messages drawn in the viewport (what went wrong, what Redo Last did) - queue / dedupe /
expiry are pure; drawing hooks into the drawn UI; tools report through toast.report."""
from types import SimpleNamespace

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import toast, cut_engine, last_op, live_stack, ui_bars

mecha_lab.register()
fresh()
toast.clear()
toast.show('Cut: not one clean solid', 'WARNING', now=100.0)
toast.show('Mecha CUT failed: boom', 'ERROR', now=100.5)
rows = toast.active(now=101.0)
check('Two toasts up, oldest first, with their seconds left and kinds', [(round(l, 1), k, t) for l, k, t in rows]
      == [(3.0, 'WARNING', 'Cut: not one clean solid'), (3.5, 'ERROR', 'Mecha CUT failed: boom')], rows)
toast.show('Cut: not one clean solid', 'WARNING', now=102.0)
rows = toast.active(now=102.0)
check('The same line again: once, moved to the bottom with a fresh time', [t for _l, _k, t in rows]
      == ['Mecha CUT failed: boom', 'Cut: not one clean solid'] and round(rows[-1][0], 1) == 4.0)
for i in range(5):
    toast.show(f'line {i}', 'INFO', now=103.0)
check('At most 3 kept (the newest)', [t for _l, _k, t in toast.active(now=103.0)] == ['line 2', 'line 3', 'line 4'])
check('Expired ones go', toast.active(now=200.0) == [])
toast.show('x' * 400 + '\nsecond line', 'ODD', seconds=1.0, now=0.0)
l, k, t = toast.active(now=0.5)[0]
check('A long / multi-line message: the first line, cut to 160; an unknown kind is INFO; own seconds',
      len(t) == 160 and k == 'INFO' and round(l, 1) == 0.5)
toast.clear()
reports = []
op = SimpleNamespace(report=lambda kinds, text: reports.append((tuple(kinds), text)))
toast.report(op, 'WARNING', 'warned')
toast.report(op, 'INFO', 'just info')
check('toast.report: the operator report always, a toast for WARNING / ERROR only',
      reports == [(('WARNING',), 'warned'), (('INFO',), 'just info')]
      and [t for _l, _k, t in toast.active()] == ['warned'])
check('Headless: no redraw timer is armed', bpy.app.background and not toast._TIMER[0])
import inspect
check('Hooked in: the drawing gate (CutError / failures / kept-as-it-was results), Redo Last, Live Stack apply, '
      'drawn above the bottom toolbar', "toast.report(self, 'WARNING', str(ex))" in inspect.getsource(cut_engine.StrokeLogic._run)
      and "'kept as it was' in msg" in inspect.getsource(cut_engine.StrokeLogic._run)
      and 'toast.show(' in inspect.getsource(last_op.MCH_OT_last_redo.execute)
      and 'toast.report' in inspect.getsource(live_stack.MCH_OT_stack_apply_all.execute)
      and 'toast.draw(' in inspect.getsource(ui_bars._draw))
toast.clear()
summary()
