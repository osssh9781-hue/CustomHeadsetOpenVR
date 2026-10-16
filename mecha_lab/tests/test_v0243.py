"""0.24.3 Ctrl+Z crash (user crash log: curve_tube._on_depsgraph read depsgraph.updates, which listed IDs that
Ctrl+Z / an add-on had just freed): the Tube and Loft depsgraph handlers never read the update list (they compare
their sources' state), stay out for a moment after undo / redo, and do nothing when nothing is live."""
import sys

_src = open(__file__.replace('test_v0243.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import curve_tube as ct, loft_surface as lf


class Bomb:
    """A depsgraph whose update list must not be touched."""
    @property
    def updates(self):
        raise AssertionError('depsgraph.updates read')

    def __getattr__(self, name):
        return getattr(C.evaluated_depsgraph_get(), name)


ok = True
try:
    ct._on_depsgraph(S, Bomb())
    lf._on_depsgraph(S, Bomb())
except AssertionError:
    ok = False
check('handlers do not read depsgraph.updates (no live tubes / lofts)', ok)
check('undo / redo handlers registered', ct._on_undo_post in bpy.app.handlers.undo_post and
      lf._on_undo_post in bpy.app.handlers.redo_post)
ct._on_undo_post()
check('after undo the Tube handler stays out for a moment', ct._UNDO_QUIET[0] and
      bpy.app.timers.is_registered(ct._quiet_off))
ct._quiet_off()
check('... and comes back', not ct._UNDO_QUIET[0])
import inspect
check('no depsgraph.updates access left in either handler',
      'depsgraph.updates' not in ''.join(l for l in inspect.getsource(ct._on_depsgraph).splitlines(True)
                                         if not l.strip().startswith('#')) and
      'depsgraph.updates' not in ''.join(l for l in inspect.getsource(lf._on_depsgraph).splitlines(True)
                                         if not l.strip().startswith('#')))
# ---- Box Hide with Sketch on: Alt + draw (no Box Hide sketch) shows again right away
from mecha_lab import lasso_sketch as ls, box_hide as bh
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
b = cube('B', 4.0)
ls.set_on(C, False)
r, m = lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
n_hidden = len(b.modifiers)
r0, m0 = lasso([(300, 300), (700, 300), (700, 700), (300, 700)], alt=True)
r, m = lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
ls.set_on(C, True)
r, m = lasso([(300, 300), (700, 300), (700, 700), (300, 700)], alt=True)
check('Sketch on: Alt + draw with no sketch starts one (no "draw a shape first" error)', r == {'FINISHED'} and
      ls.data(S) is not None and ls.data(S)['items'][0]['op'] == 'ADD', m)
mods = len(b.modifiers)
res = bpy.ops.mch.lasso_sketch_commit(alt=True)
check('Alt + Enter: the hidden part shows again', res == {'FINISHED'} and ls.data(S) is None)
r, m = lasso([(350, 350), (550, 350), (550, 550), (350, 550)])
res = bpy.ops.mch.lasso_sketch_commit(alt=False)
check('Enter: hides', res == {'FINISHED'} and ls.data(S) is None)
ls.set_on(C, False)
mecha_lab.unregister()
check('unregister removes the undo handlers', ct._on_undo_post not in bpy.app.handlers.undo_post)
sys.exit(1 if summary() else 0)
