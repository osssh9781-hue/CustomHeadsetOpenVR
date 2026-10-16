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
mecha_lab.unregister()
check('unregister removes the undo handlers', ct._on_undo_post not in bpy.app.handlers.undo_post)
sys.exit(1 if summary() else 0)
