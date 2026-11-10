"""0.24.128 (user: "메쉬 커브로 커브 그으면 그 이후에 다른 오브젝트 클릭해서 ... 노란색 메쉬 커브를 주황색으로 만들면 그
오브젝트를 커브에 연결해서 나열되게 해 줘") Link by selection: a live Mesh Curve is selected; Shift + click another part
(the part is the active one, yellow; the curve stays selected, orange) -> the part is the curve's Repeat source and is
repeated along it.  Plus the button / operator, the toggle, the Line Curve case, two curves at once."""
import inspect

from _harness import bpy, check, cube, fresh, summary
from mathutils import Vector  # noqa: E402

import mecha_lab
from mecha_lab import curve_tube as ct, key_legend as kl  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def make_tube(name, at, mode=''):
    ob = ct.new_tube(C, Vector(at), mode=mode)
    ob.name = name
    ct.set_points(ob, [(Vector((0, 0, 0)), 1.0), (Vector((1.0, 0, 0)), 1.0), (Vector((2.0, 0.6, 0)), 1.0),
                       (Vector((3.0, 0.4, 0.3)), 1.0)])
    ct.rebuild(ob)
    return ob


def select(active, *others):
    for o in C.view_layer.objects:
        o.select_set(False)
    for o in others:
        o.select_set(True)
    if active is not None:
        active.select_set(True)
    C.view_layer.objects.active = active


tube = make_tube('Curve', (0, 0, 0))
part = cube('Part', size=0.4, loc=(0, 2, 0))
n_tube = len(tube.data.vertices)
check('a live Mesh Curve (Tube) and a plain part', ct.is_tube(tube) and not ct.is_tube(part) and tube.mch_tube.mode == 'TUBE'
      and n_tube > 0 and S.mch_tube_defaults.select_link)
# the gesture: the curve is the active one (yellow) ... then the part is clicked with Shift (active) while the curve stays selected
select(tube)
got0 = ct.select_link_step(C)
select(part, tube)
got = ct.select_link_step(C)
import math  # noqa: E402
tb = tube.mch_tube
first8 = [tube.data.vertices[i].co.copy() for i in range(min(8, len(tube.data.vertices)))]
diag = max((a - b).length for a in first8 for b in first8) if len(first8) == 8 else 0.0
check('curve active -> Shift + click the part: the part is repeated along the curve (Repeat, source = the part)',
      got0 == [] and got == [tube] and tb.mode == 'REPEAT' and tb.source == part and len(tube.data.vertices) % 8 == 0
      and len(tube.data.vertices) >= 16, (len(tube.data.vertices), tb.count))
check('... at the part\'s REAL size (a copy\'s diagonal = the 0.4 cube\'s), one after another (Spacing: Distance = its length 0.4)',
      abs(diag - 0.4 * math.sqrt(3)) < 1e-3 and not tb.follow_radius and tb.spacing_mode == 'DISTANCE' and abs(tb.spacing - 0.4) < 1e-6
      and abs(tb.radius - 0.2 * math.sqrt(3)) < 1e-4 and tb.size == 1.0, (diag, tb.spacing, tb.radius))
tb.spacing_mode = 'COUNT'
check('... Count / Spacing / Size stay adjustable (Count 8 -> 8 copies)', len(tube.data.vertices) == 8 * 8)
tb.spacing_mode = 'DISTANCE'
got2 = ct.select_link_step(C)
check('... the same selection again links nothing more (one step, one undo)', got2 == [] and tube.mch_tube.mode == 'REPEAT')
part2 = cube('Part2', size=1.0, loc=(0, 3, 0))
tb.spacing = 0.7
select(tube)
ct.select_link_step(C)
select(part2, tube)
got3 = ct.select_link_step(C)
check('a curve that already repeats takes a new part but keeps its Spacing / Size (the user\'s own)', got3 == [tube]
      and tb.source == part2 and abs(tb.spacing - 0.7) < 1e-6)
bpy.data.objects.remove(part2)
# the part stays where it is; moving it (source edit) is followed by the existing watcher - not this test
# a plain click (the curve deselected = not orange): nothing
tube.mch_tube.mode, tube.mch_tube.source = 'TUBE', None
select(tube)
ct.select_link_step(C)
select(part)
got = ct.select_link_step(C)
check('a plain click on the part (the curve no longer selected): nothing happens', got == [] and tube.mch_tube.mode == 'TUBE')
# the other order (part first, then Shift + click the curve): nothing - the curve is the one clicked
select(part)
ct.select_link_step(C)
select(tube, part)
got = ct.select_link_step(C)
check('part active then the curve clicked: nothing (only "curve first, then the part")', got == [] and tube.mch_tube.mode == 'TUBE')
# the toggle off
S.mch_tube_defaults.select_link = False
select(tube)
ct.select_link_step(C)
select(part, tube)
got = ct.select_link_step(C)
check('Link by Selection off: the gesture does nothing', got == [] and tube.mch_tube.mode == 'TUBE')
S.mch_tube_defaults.select_link = True
# the button / operator does the same from the same selection
select(part, tube)
r = bpy.ops.mch.tube_link_selected()
check('the Repeat Along Curve button: the active part along the selected curve', 'FINISHED' in r and tube.mch_tube.mode == 'REPEAT'
      and tube.mch_tube.source == part)
select(part)
check('... its poll needs a selected curve', not bpy.ops.mch.tube_link_selected.poll())
# two curves selected: both repeat the part
tube.mch_tube.mode, tube.mch_tube.source = 'TUBE', None
tube2 = make_tube('Curve2', (0, -2, 0))
select(tube, tube2)
ct.select_link_step(C)
select(part, tube, tube2)
got = ct.select_link_step(C)
check('two curves selected (orange) + the part clicked: both repeat it', sorted(o.name for o in got) == ['Curve', 'Curve2']
      and tube.mch_tube.source == part and tube2.mch_tube.source == part)
# a Line Curve: Same Size Copies (its own mode family)
line = make_tube('Line', (0, 4, 0), mode='LINE')
select(line)
ct.select_link_step(C)
select(part, line)
got = ct.select_link_step(C)
check('a Line Curve takes the part as Same Size Copies', got == [line] and line.mch_tube.mode == 'REPEAT_SAME' and line.mch_tube.source == part)
# another live tube clicked is not a source
select(tube)
ct.select_link_step(C)
select(tube2, tube)
got = ct.select_link_step(C)
check('clicking another curve links nothing (a curve is not a source)', got == [] and not ct.can_link_source(tube, tube2))
# wiring: the timer, the panel toggle / button, the key legend line
check('wired: a selection timer (not in a background Blender), the panel toggle + button, the legend line',
      'bpy.app.timers.register(_select_tick' in inspect.getsource(ct.register) and 'select_link' in inspect.getsource(ct.draw)
      and 'mch.tube_link_selected' in inspect.getsource(ct.draw)
      and any('repeated along the curve' in ln for ln in kl.EXTRA.get('TUBE', []))
      and ct._sel_timer_live and not bpy.app.timers.is_registered(ct._select_tick))
summary()
