"""0.24.36 Free Draw / Line strokes: hold Shift = a straight piece at 0 / 45 / 90 degrees from where Shift went down;
let go and the line goes on freely from its end (also with Slow Line on)."""
import math

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import cut_engine as ce

mecha_lab.register()
fresh()
C = bpy.context
brush = C.scene.mch_brush
brush.stroke_spacing = 4.0


class Stroke:
    """the stroke logic of the drawing tools, without a window"""
    _stroke_sample = ce.MCH_OT_cut_stroke._stroke_sample
    _stroke_finish = ce.MCH_OT_cut_stroke._stroke_finish
    _stroke_start = ce.MCH_OT_cut_stroke._stroke_start
    _stroke_append = ce.MCH_OT_cut_stroke._stroke_append
    _wm = None
    stab_timer = None

    def __init__(self, mode='SDRAW'):
        self.mode, self.brush, self.stab, self.shift_held = mode, brush, None, False
        self.t = 0.0

    def _clock(self):
        self.t += 0.016
        return self.t

    def begin(self, xy):
        self.pts = [xy]
        self.shift_anchor = None
        self._stroke_start(xy)


def angle(a, b):
    return math.degrees(math.atan2(b[1] - a[1], b[0] - a[0]))


for stab in (False, True):
    brush.stab_enable = stab
    s = Stroke()
    s.begin((100, 100))
    for k in range(1, 11):                       # free first
        s._stroke_sample((100 + 5 * k, 100 + 3 * k))
    corner = s.pts[-1]
    n = len(s.pts)
    s.shift_held = True
    for k in range(1, 30):                       # Shift: the mouse wobbles round 40 degrees
        s._stroke_sample((corner[0] + 6 * k, corner[1] + 5 * k + (3 if k % 2 else -3)))
    straight = s.pts[n - 1:]
    angs = {round(angle(straight[0], p)) for p in straight[1:]}
    tag = ' (Slow Line on)' if stab else ''
    check('Shift: a straight piece from where Shift went down, snapped to 45 degrees' + tag,
          straight[0] == corner and angs == {45}, angs)
    check('the free part before it stays as it was' + tag, len(s.pts) > n and s.pts[n - 1] == corner)
    s._stroke_sample((corner[0] + 200, corner[1] + 3))
    check('turn the mouse: it snaps to 0 degrees (90 / 45 steps)' + tag,
          round(angle(corner, s.pts[-1])) == 0 and abs(s.pts[-1][1] - corner[1]) < 1e-6)
    end = s.pts[-1]
    s.shift_held = False
    s._stroke_sample((end[0] + 10, end[1] + 30))
    check('let go of Shift: drawing goes on freely from the end of the straight piece' + tag,
          s.shift_anchor is None and any(math.dist(p, end) < 1e-6 for p in s.pts))
    s.shift_held = True
    m = len(s.pts)
    s._stroke_sample((s.pts[-1][0] + 1, s.pts[-1][1] + 80))
    s._stroke_finish((s.pts[m - 1][0] + 1, s.pts[m - 1][1] + 90))
    check('Shift again, then release: the line ends exactly on the 90 degree end' + tag,
          round(angle(s.pts[m - 1], s.pts[-1])) == 90)
brush.stab_enable = False
summary()
