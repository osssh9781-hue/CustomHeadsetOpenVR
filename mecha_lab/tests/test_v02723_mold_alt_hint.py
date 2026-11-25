"""0.24.323 (user: "왜 다른 메쉬에는 몰드로 자르는 게 안 돼? 그냥 플랫하게 잘리는데" / "아 카브 하이트가 꺼져 있었어" / "그래"):
the Mold Cut carves only with Alt: Carve Height - with it on and Alt set to something else, the Mold Cut box and the
top bar say so, with a button that sets Carve Height."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import mold_cut, top_bar

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.mch_active_tool = 'MBASE'
mc = S.mch_moldcut
p = S.mch_base
mc.on = True
p.alt_mode = 'HEIGHT'
check('Carve Height: no warning', mold_cut.wrong_alt(C, mc) == '' and
      not any('Carve Height' in c['label'] for c in top_bar.mold_cut_group(mc, C)[1]))
for mode in ('THROUGH', 'RAMP', 'INSIDE', 'CUT'):
    p.alt_mode = mode
    cells = top_bar.mold_cut_group(mc, C)[1]
    btn = [c for c in cells if c['label'] == 'Alt is not Carve Height: Use It']
    check(f'Alt: {mode} with Mold Cut on: warned, a button to Carve Height', mold_cut.wrong_alt(C, mc) == mode and
          len(btn) == 1 and btn[0]['action'] == ('op', 'mch.mold_cut_height', {}))
r = bpy.ops.mch.mold_cut_height()
check('the button: Alt -> Carve Height', r == {'FINISHED'} and p.alt_mode == 'HEIGHT' and mold_cut.wrong_alt(C, mc) == '')
p.alt_mode = 'CUT'
mc.on = False
check('Mold Cut off: no warning (whatever Alt is)', mold_cut.wrong_alt(C, mc) == '' and
      len(top_bar.mold_cut_group(mc, C)[1]) == 1)
check('the plain group (Mold Armor Plate, no context): as before', len(top_bar.mold_cut_group(mc)[1]) == 1)


class Rec:
    """A layout that writes down what is drawn."""
    seen = []

    def __init__(self):
        self.alert = False

    def _c(self, *a, **k):
        return Rec()

    row = column = box = split = _c

    def label(self, text='', **k):
        Rec.seen.append(('label', text))

    def prop(self, data, name, **k):
        Rec.seen.append(('prop', name))

    def operator(self, idname, **k):
        Rec.seen.append(('op', idname))
        return type('O', (), {})()


mc.on = True
p.alt_mode = 'THROUGH'
Rec.seen = []
mold_cut.draw(Rec(), mc, C)
check('the Mold Cut box (panel): the warning and the Use Carve Height button',
      ('label', 'Mold Cut works only with Alt: Carve Height') in Rec.seen and ('label', 'Alt: Through') in Rec.seen
      and ('op', 'mch.mold_cut_height') in Rec.seen, Rec.seen[:6])
p.alt_mode = 'HEIGHT'
Rec.seen = []
mold_cut.draw(Rec(), mc, C)
check('... not with Carve Height', ('op', 'mch.mold_cut_height') not in Rec.seen)
Rec.seen = []
mold_cut.draw(Rec(), mc)
check('... nor without context (Mold Armor Plate: no Alt modes there)', ('op', 'mch.mold_cut_height') not in Rec.seen)
summary()
