"""0.24.55 New parts follow the Mirror: a plate / Surface Draw / Flower / screw made on a part with a live Mirror
gets the same Mirror (planes, the same mirror object, bisect, flips); Preferences: New Parts Follow the Mirror."""
import inspect

from _harness import bpy, check, cube, fresh, select_only, summary
from mathutils import Vector

import mecha_lab
from mecha_lab import cut_engine as ce, mirror_tools as mt, screw_stamp as ss, symmetry as sy

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene

body = cube('Body', loc=(2.0, 0.0, 0.0))
select_only(body)
sy.set_mode(C, body, 'MIRROR')
bm_ = sy.mirror_mod(body)
check('Body: live Mirror X across the world plane', sy.axes_of(body) == (True, False, False)
      and bm_.mirror_object is not None)
part = cube('Plate', size=0.3, loc=(2.0, 0.3, 1.05))
msg = sy.follow(C, part)
pm = sy.mirror_mod(part)
check('A new part on it: the same Mirror (planes, the same mirror object = the same plane)', pm is not None
      and tuple(pm.use_axis) == (True, False, False) and pm.mirror_object == bm_.mirror_object and 'Body' in msg, msg)
check('... bisect and flips like the body', tuple(pm.use_bisect_axis) == tuple(bm_.use_bisect_axis)
      and tuple(pm.use_bisect_flip_axis) == tuple(bm_.use_bisect_flip_axis))
dg = C.evaluated_depsgraph_get()
xs = [(part.matrix_world @ v.co).x for v in part.evaluated_get(dg).to_mesh().vertices]
check('... so it shows on the other side too', min(xs) < -1.5 and max(xs) > 1.5, (min(xs), max(xs)))
check('A part that already has a Mirror is left alone', sy.follow(C, part) == '')
far = cube('Far', size=0.3, loc=(0.0, 9.0, 0.0))
check('A part not on a mirrored part: nothing', sy.follow(C, far) == '' and sy.mirror_mod(far) is None)

# a Local mirror on the body: the new part mirrors across the body's own planes
loc = cube('LocalBody', loc=(0.0, -6.0, 0.0))
m = loc.modifiers.new(mt.MOD_NAME, 'MIRROR')
m.use_axis = (False, True, False)
m.mirror_object = None
bit = cube('Bit', size=0.2, loc=(0.0, -5.5, 1.05))
sy.follow(C, bit)
check('Local mirror on the body: the new part mirrors across the body (its mirror object = the body)',
      sy.mirror_mod(bit) is not None and sy.mirror_mod(bit).mirror_object == loc
      and tuple(sy.mirror_mod(bit).use_axis) == (False, True, False))

# screws: parented to the part they sit on
scr = ss.place(C, body, Vector((2.5, 0.2, 1.0)), Vector((0, 0, 1)))
check('A screw sits on its part: that part is the source', sy._under(C, scr) == body)
sy.follow(C, scr, body)
check('... the screw gets the Mirror too', sy.mirror_mod(scr) is not None
      and sy.mirror_mod(scr).mirror_object == bm_.mirror_object)
check('The screw tool, plates, Surface Draw and Flower call it', 'symmetry.follow' in inspect.getsource(
      ss.MCH_OT_screw_stamp) and 'symmetry.follow' in inspect.getsource(ce)
      and {'PLATE', 'CPLATE', 'SDRAW', 'FLOWER'} <= ce.FOLLOWERS)

# card: Clip, and the planes shown
bpy.context.view_layer.objects.active = body
select_only(body)
import mecha_lab.bottom_bar as bb
real_ui = bb.ui_active
bb.ui_active = lambda c: True
items = sy.build_card(C, 1600, 900, 1.0)
tog = {i.label: i for i in items if i.kind == 'toggle'}
check('Card: Bisect / Flip / Clip side by side', set(tog) == {'Bisect', 'Flip', 'Clip'})
was = bm_.use_clip
sy.run_card(C, tog['Clip'])
check('... Clip toggles the mirror\'s clipping', bm_.use_clip != was)
quads = sy.plane_quads(body)
c = bm_.mirror_object.matrix_world.translation
check('Mirror planes to show: one quad per plane through the mirror centre, as big as the part and its copy',
      len(quads) == 1 and quads[0][0] == 0 and all(abs(p.x - c.x) < 1e-6 for p in quads[0][1])
      and (quads[0][1][2] - quads[0][1][0]).length > 3.0)
CALLS = []
import types, sys
fake_gpu = types.SimpleNamespace(
    shader=types.SimpleNamespace(from_builtin=lambda n: types.SimpleNamespace(
        bind=lambda: CALLS.append('bind'), uniform_float=lambda k, v: CALLS.append('color'))),
    state=types.SimpleNamespace(blend_set=lambda *a: None, depth_test_set=lambda *a: None,
                                depth_mask_set=lambda *a: None))
fake_batch = types.SimpleNamespace(batch_for_shader=lambda sh, kind, data, indices=None: types.SimpleNamespace(
    draw=lambda s: CALLS.append(kind)))
saved = sys.modules.get('gpu'), sys.modules.get('gpu_extras.batch')
sys.modules['gpu'], sys.modules['gpu_extras.batch'] = fake_gpu, fake_batch
try:
    sy._draw_planes()
finally:
    for name, mod in zip(('gpu', 'gpu_extras.batch'), saved):
        if mod is None:
            sys.modules.pop(name, None)
        else:
            sys.modules[name] = mod
check('The plane drawing runs (stand-in painter): a see-through quad and its outline', CALLS.count('TRIS') == 1
      and CALLS.count('LINE_STRIP') == 1, CALLS)
bb.ui_active = real_ui

# group repetition: Grid
from mecha_lab import groups as gr, mecha_menu as mm
ga = cube('GA', size=1.0, loc=(20, 0, 0))
g = gr.create(C, [ga])
gr.set_repeat(C, g, mode='GRID', grid=(3, 2, 1), gap=0.5)
check('Grid: 3 x 2 x 1 = 5 copies, the part\'s size + gap apart', len(gr._mats(g)) == 5
      and abs(gr.grid_step(g)[0] - 1.5) < 1e-6
      and sorted(round(m.translation.x, 4) for m in gr._mats(g)) == [0.0, 1.5, 1.5, 3.0, 3.0])
dg = C.evaluated_depsgraph_get()
car = gr.carrier_of(g)
inst = [i for i in dg.object_instances if i.is_instance and i.parent is not None and i.parent.original == car]
check('... shown as linked copies', len(inst) == 5)
select_only(g)
C.view_layer.objects.active = g
bb.ui_active = lambda c: True
items = sy.build_card(C, 1600, 900, 1.0)
modes = [i.label for i in items if i.action and i.action[0] == 'sym_mode']
check('Group card: Off / Mirror / Radial / Kaleido / Grid, Grid shows X Y Z counts and Gap',
      modes[:5] == ['Off', 'Mirror', 'Radial', 'Kaleido', 'Grid'] and 'Grid' in [i.label for i in items if i.kind == 'section']
      and len([i for i in items if i.action and i.action[0] == 'sym_grid']) == 6)
sy.run_card(C, next(i for i in items if i.action == ('sym_grid', 2, 1)))
sy.run_card(C, next(i for i in sy.build_card(C, 1600, 900, 1.0) if i.action == ('sym_gap', 0.1)))
check('... + on Z and Gap from the card', gr.repeat_grid(g) == (3, 2, 2) and abs(gr.repeat_gap(g) - 0.6) < 1e-6
      and len(gr._mats(g)) == 11)
n0 = len(gr.members(g))
check('... Apply makes them real', gr.make_real(C, g) == 11 and len(gr.members(g)) == n0 + 11)
bb.ui_active = real_ui
inner = gr.create(C, [cube('GIn', size=0.5, loc=(25, 0, 0))])
outer = gr.create(C, [inner, cube('GOut', size=0.5, loc=(26, 0, 0))])
rows = [(x.name, d) for x, d in gr.all_groups(C)]
check('Group list: every group, inner ones under their outer one', (outer.name, 0) in rows
      and (inner.name, 1) in rows and rows.index((inner.name, 1)) == rows.index((outer.name, 0)) + 1, rows)
bpy.ops.mch.group_pick(name=inner.name, enter=True)
check('... pick with Enter: inside that group', gr.scope(C) == inner)
bpy.ops.mch.group_pick(name=outer.name)
check('... pick: out again, the group selected', gr.scope(C) is None and C.active_object == outer)
class _L:
    def __init__(self): self.calls = []
    def __getattr__(self, n):
        def f(*a, **k):
            self.calls.append(n)
            return types.SimpleNamespace() if n == 'operator' else self
        return f
lay = _L()
gr.draw_list(lay, C)
check('... the sidebar list draws (stand-in layout)', lay.calls.count('operator') >= 2 * len(rows))
from mecha_lab import tool_state as ts
groups = ts.grouped_tools()
ids = [t[0] for _n, rows in groups for t in rows]
check('Tool list by job: about 10 groups, every visible tool exactly once', 8 <= len(groups) <= 11
      and sorted(ids) == sorted(t[0] for t in ts.VISIBLE_TOOLS) and len(ids) == len(set(ids)),
      [(n, len(r)) for n, r in groups])
from mecha_lab import workspace_ui as wui
lay = _L()
wui.icon_tile = (lambda real: (lambda *a, **k: [types.SimpleNamespace()]))(wui.icon_tile)
wui.draw_tool_grid(lay, C, columns=3, scale=1.0)
check('... the tool grid shows a heading per group', lay.calls.count('label') == len(groups))
check('Mecha Menu: Repeat Grid', any(it[0] == 'Repeat Grid' for sec, its in mm.ACTIONS for it in its))

# preference off
addon = C.preferences.addons.get('mecha_lab')
prefs = addon.preferences if addon else None
if prefs is not None and hasattr(prefs, 'symmetry_follow'):
    prefs.symmetry_follow = False
    nb = cube('Off', size=0.2, loc=(2.0, -0.3, 1.05))
    check('Preferences off: new parts do not follow', sy.follow(C, nb) == '' and sy.mirror_mod(nb) is None)
    prefs.symmetry_follow = True
else:
    from mecha_lab import workspace_ui as wui
    real = wui.pref
    wui.pref = lambda k, d=None: False if k == 'symmetry_follow' else real(k, d)
    nb = cube('Off', size=0.2, loc=(2.0, -0.3, 1.05))
    check('Preferences off: new parts do not follow', sy.follow(C, nb) == '' and sy.mirror_mod(nb) is None)
    wui.pref = real
summary()
