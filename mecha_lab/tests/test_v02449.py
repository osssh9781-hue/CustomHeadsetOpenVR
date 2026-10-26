"""0.24.36 Slow Line (Lazy Mouse) switch in every drawing tool panel (and Path Move): the drawn line follows the
mouse slowly; the stroke engine starts it in every drawing mode, the Path Move drag uses it too."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import concept_move as cm, cut_engine as ce, target_rules as tr, ui_tool_settings as uts
from mecha_lab.stabilizer import LazyStabilizer

mecha_lab.register()
fresh()
C = bpy.context
brush = C.scene.mch_brush
check('the switch is called Slow Line', brush.bl_rna.properties['stab_enable'].name == 'Slow Line (Lazy Mouse)'
      and not brush.stab_enable)
check('in the panel of every drawing tool, and in Path Move', hasattr(uts, 'draw_slow_line')
      and 'draw_slow_line' in cm.draw_path.__code__.co_names)


class Layout:
    """a pretend panel layout that records what is drawn"""
    def __init__(self, log):
        self.log = log

    def __getattr__(self, name):
        if name in {'box', 'row', 'column'}:
            return lambda *a, **k: Layout(self.log)
        return lambda *a, **k: self.log.append((name, a, k))


log = []
brush.stab_enable = True
brush.shape = 'LASSO'
uts.draw_slow_line(Layout(log), C)
check('on: strength / radius / guide sliders, and a note for the Lasso shape',
      [a[1] for n, a, k in log if n == 'prop'][:4] == ['stab_enable', 'stab_strength', 'stab_radius', 'stab_guide']
      and any(n == 'label' for n, a, k in log))


class Fake:
    _wm = None
    stab_timer = None

    def __init__(self, mode):
        self.mode = mode
        self.brush = brush
        self.stab = None

    def _clock(self):
        return 0.0


brush.shape = 'STROKE'
started = []
for mode in sorted((tr.PICKING | {'CUT', 'SPLIT', 'HIDE'}) - {'MASK'}):
    f = Fake(mode)
    ce.MCH_OT_cut_stroke._stroke_start(f, (100, 100))
    started.append(f.stab is not None)
check('the stroke engine starts it in every drawing mode (Surface Draw, Belt, Cape, Cut ...)', all(started))
s = LazyStabilizer(brush)
brush.stab_strength, brush.stab_radius = 60.0, 20.0
s.reset((0, 0), 0.0)
p = s.update((100, 0), 0.016)
check('it follows slowly: one quick mouse jump is not reached at once', 0.0 < p[0] < 80.0, p)
brush.stab_enable = False
check('off: not active (the old exact line)', not LazyStabilizer(brush).active)
summary()
