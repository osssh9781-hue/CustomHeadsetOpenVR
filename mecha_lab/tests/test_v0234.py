"""0.23.4: fold direction (the steep folded wall on the upper side, world up), Creature Skin
(Cloth Plate: crocodile / dragon / godzilla / toad / elephant + border finishing + shrink),
Creature Shell (Armor Plate layer: hard plates, bulges, N/E/S/W edge lift, gravity)."""
import math
import sys

_src = open(__file__.replace('test_v0234.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])
import numpy as np

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
from mecha_lab import armor_plate as ap, bottom_bar as bb, cloth_wrinkle as cw, creature_shell as cs, last_used, \
    tool_state as ts
last_used.forget('creature')
last_used.forget('shell')
last_used.forget('wrinkle')
S.mch_settings.mch_active_tool = 'WRINKLE'
MODE[0], NATIVE[0] = 'WRINKLE', 'mecha.cloth_wrinkle'

# ---- fold direction on a standing panel (the -Y side of a box, seen from the front)
box = cube('Box', 4.0)
VIEW[0] = cg.OrthoProjector(Quaternion(Vector((1, 0, 0)), math.pi / 2))
S.mch_wrinkle.wtype = 'DENIM'
r, m = lasso([(300, 300), (700, 300), (700, 700), (300, 700)])
pan = C.active_object
check('standing cloth plate made', r == {'FINISHED'} and cw.is_wrinkle(pan), m)
check('Fold Direction input (Up / Down / Random), Up by default',
      next(x for x in cw.INPUTS if x[0] == 'Fold Direction')[2:] == (0, 0, 2) and
      int(cw.get_input(pan, 'Fold Direction')) == 0)


def slopes(fdir):
    cw.set_input(pan, 'Fold Asymmetry', 1.0)
    cw.set_input(pan, 'Fold Direction', fdir)
    n = cw.fold_lines(pan)
    me = pan.data
    h = np.array([d.value for d in me.attributes[cw.FOLD_H].data])
    mw = pan.matrix_world
    W = np.array([(mw @ v.co)[:] for v in me.vertices])
    g = []
    for e in me.edges:
        a, b = e.vertices
        d = W[b] - W[a]
        ln = np.linalg.norm(d)
        if ln > 1e-9 and abs(d[2]) > 0.7 * ln:                      # mostly vertical edges
            g.append((h[b] - h[a]) / d[2])
    g = np.array(g)
    eps = float(np.percentile(np.abs(g), 60))
    # the gentle side covers more of the panel: count the edges climbing vs falling going upward
    return n, int((g > eps).sum()), int((g < -eps).sum())


n0, rise0, fall0 = slopes(0)
n1, rise1, fall1 = slopes(1)
check('folds exist on the standing panel', n0 > 0 and n1 > 0, (n0, n1))
check('Up: going upward a fold rises over a long gentle slope, drops on a short steep wall', rise0 > fall0 * 1.15,
      (rise0, fall0))
check('Down: the steep wall is underneath', fall1 > rise1 * 1.15, (rise1, fall1))

# ---- Creature Skin
check('five skins (+ Croc Back since 0.23.6) + four border finishes',
      cw.SKIN_IDS[:5] == ('CROC', 'DRAGON', 'GODZILLA', 'TOAD', 'ELEPHANT') and
      len(cw.SKIN_EDGES) == 4 and all(cw.CREATURE[k]['Skin'] == i + 1 for i, k in enumerate(cw.SKIN_IDS)))
check('skin inputs in the node group', all(any(x[0] == k for x in cw.INPUTS) for k in
      ('Skin', 'Skin Scale', 'Skin Depth', 'Skin Random', 'Edge Shrink', 'Shrink Width', 'Skin Edge',
       'Skin Edge Width', 'Skin Edge Height', 'Gravity')))
VIEW[0] = cg.OrthoProjector(Quaternion())
S.mch_wrinkle.creature = True
made = []
for k, skin in enumerate(cw.SKIN_IDS[:5]):
    b = cube('B%d' % k, 4.0, loc=(6.0 * (k + 1), 0, 0))
    VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((6.0 * (k + 1), 0, 0)))
    S.mch_wrinkle.skin = skin
    r, m = lasso([(300, 350), (700, 350), (700, 650), (300, 650)])
    o = C.active_object
    ok = r == {'FINISHED'} and cw.is_creature(o) and o.get('mch_creature') == skin and \
        int(cw.get_input(o, 'Skin')) == cw.CREATURE[skin]['Skin'] and 'Creature skin' in m
    dg = C.evaluated_depsgraph_get()
    ev = o.evaluated_get(dg).data
    zs = [v.co.z for v in ev.vertices]
    made.append((o, ok, len(ev.vertices), max(zs) - min(zs) if zs else 0.0))
check('every skin preset makes a creature skin plate', all(x[1] for x in made), [x[1] for x in made])
check('skins are displaced (scales / warts / cracks show up)', all(x[2] > 500 and x[3] > 1e-3 for x in made),
      [(x[2], round(x[3], 4)) for x in made])
o = made[0][0]
check('cloth features off on a skin (puff low, no stitch / trim / pinch)',
      cw.get_input(o, 'Stitch') == 0 and int(cw.get_input(o, 'Trim')) == 0 and cw.get_input(o, 'Pinch') == 0)
check('scales get smaller toward the border (Edge Shrink on)', cw.get_input(o, 'Edge Shrink') > 0)
C.view_layer.objects.active = o
for ob_ in C.selected_objects:
    ob_.select_set(False)
o.select_set(True)
bpy.ops.mch.wrinkle_skin()
check('Skin button cycles the preset', o.get('mch_creature') == 'DRAGON' and S.mch_wrinkle.skin == 'DRAGON')
e0 = int(cw.get_input(o, 'Skin Edge'))
bpy.ops.mch.wrinkle_skin_edge()
check('Edge button cycles the border finishing', int(cw.get_input(o, 'Skin Edge')) == (e0 + 1) % 4)
cw.HUD_SLIDERS = True                                     # 0.23.24: the HUD list is off by default
check('skin HUD: skin + edge buttons, skin sliders only on a creature', {'skin', 'skin_edge'} <=
      {b_[0] for b_ in cw.HUD_BUTTONS} and set(cw.slider_keys(o)) & set(cw.SKIN_KEYS) and
      not set(cw.slider_keys(pan)) & set(cw.SKIN_KEYS))
cw.HUD_SLIDERS = False
S.mch_wrinkle.creature = False

# ---- toolbar + creature brush
tools = {t[0]: t for t in bb.BAR_TOOLS}
check('bottom toolbar: Skin + Shell buttons', 'SKIN' in tools and 'SHELL' in tools)
bpy.ops.mch.creature_brush(kind='SKIN')
check('Skin brush = Cloth Plate with the creature layer', S.mch_wrinkle.creature and
      S.mch_settings.mch_active_tool == 'WRINKLE')
bpy.ops.mch.creature_brush(kind='SHELL')
check('Shell brush = Armor Plate with the creature layer', S.mch_plate.creature and
      S.mch_settings.mch_active_tool == 'PLATE')

# ---- Creature Shell
ng = cs.build_group()
check('shell node group + inputs', ng.bl_idname == 'GeometryNodeTree' and ng.get('mch_version') == cs.VERSION and
      all(cs._ident(n) for n, *_r in cs.INPUTS))
MODE[0], NATIVE[0] = 'PLATE', 'mecha.armor_plate'
S.mch_plate.creature = True
b = cube('Body', 4.0, loc=(0, 8, 0))
VIEW[0] = cg.OrthoProjector(Quaternion(), center=Vector((0, 8, 0)))
nb = len(b.data.vertices)
r, m = lasso([(300, 330), (700, 330), (720, 660), (330, 680)])
sh = C.active_object
check('Shell lasso: an armor plate with the shell layer, body unchanged', r == {'FINISHED'} and cs.is_shell(sh) and
      len(b.data.vertices) == nb, m)
up = Vector(cs.get_input(sh, 'Up'))
check('shell faces outward (toward the viewer)', up.dot(sh.matrix_world.inverted().to_3x3() @ Vector((0, 0, 1))) > 0.99,
      tuple(up))


def ev_z():
    dg = C.evaluated_depsgraph_get()
    me = sh.evaluated_get(dg).data
    return np.array([(sh.matrix_world @ v.co).z for v in me.vertices]), me


z0, me0 = ev_z()
check('hard plates + bulges displace the plate', len(me0.vertices) > len(sh.data.vertices) and z0.ptp() > 1e-3)
C.view_layer.objects.active = sh
cs.set_input(sh, 'Facets', 0.0)
cs.set_input(sh, 'Bulge', 0.0)
zf, _m0 = ev_z()
bpy.ops.mch.shell_option(option='LIFT_S')
zl, _m1 = ev_z()
check('Lift S raises the plate edge off the body', float(cs.get_input(sh, 'Lift S')) == 1.0 and zl.max() > zf.max() + 1e-3,
      (round(zf.max(), 4), round(zl.max(), 4)))
bpy.ops.mch.shell_option(option='LIFT_S')
check('Lift S toggles back off', float(cs.get_input(sh, 'Lift S')) == 0.0)
for o_ in ('LIFT_N', 'LIFT_E', 'LIFT_W'):
    bpy.ops.mch.shell_option(option=o_)
check('N / E / W lift toggles', all(float(cs.get_input(sh, 'Lift ' + s_)) == 1.0 for s_ in 'NEW'))
s0 = int(cs.get_input(sh, 'Seed'))
bpy.ops.mch.shell_option(option='REROLL')
check('reroll = new random plates', int(cs.get_input(sh, 'Seed')) == s0 + 1)
cs.set_input(sh, 'Gravity', 2.0)
zg, _m2 = ev_z()
cs.set_input(sh, 'Gravity', 0.0)
zn, _m3 = ev_z()
check('Gravity moves the raised parts', np.abs(zg - zn).max() > 1e-4)
check('shell values remembered for the next shell', last_used.recall('shell').get(cs._ident('Gravity') if False else 'Gravity') == 0.0)
bpy.ops.mch.shell_option(option='REMOVE')
check('Remove Shell', not cs.is_shell(sh))
bpy.ops.mch.shell_option(option='ADD')
check('Add Shell to any plate', cs.is_shell(sh))
S.mch_plate.creature = False
bpy.ops.mch.creature_brush(kind='SKIN')
S.mch_settings.mch_active_tool = 'PLATE'
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
