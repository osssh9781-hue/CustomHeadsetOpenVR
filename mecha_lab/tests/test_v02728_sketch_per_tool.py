"""0.24.328 (user: "브러시마다 라인이나 스케치 설정 다르게 저장되던 게 다 통일됐어" / "몰드 도구랑 컷 스플릿이 같이 연동돼, 분리해
줘"): the lasso settings per tool keep Sketch too (it was one for every tool), and the Mold tools keep their own (not
their original's) - Base Mesh's Sketch First too."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import lasso_memory as lm

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
b = S.mch_brush
st = S.mch_settings
lm.forget()


def use(t):
    st.mch_active_tool = t
    lm.sync(C)


use('MBASE')
b.sketch_first = True
b.line_mode = True
S.mch_base.sketch = False
use('CUT')
b.sketch_first = False
b.line_mode = False
use('SPLIT')
b.sketch_first = True
use('BASE')
b.line_mode = False
b.sketch_first = False
S.mch_base.sketch = True
use('CUT')
check('Cut: its own Sketch / Line (off) - not the Mold tool\'s', not b.sketch_first and not b.line_mode)
use('MBASE')
check('Mold Base Mesh: its own (Sketch on, Line on, Base Sketch First off) - not Base Mesh\'s',
      b.sketch_first and b.line_mode and not S.mch_base.sketch)
use('SPLIT')
check('Split: its own Sketch (on)', b.sketch_first)
use('BASE')
check('Base Mesh: its own (Sketch off, Line off, Sketch First on)', not b.sketch_first and not b.line_mode
      and S.mch_base.sketch)
use('MPLATE')
b.shape = 'CIRCLE'
use('PLATE')
b.shape = 'RECT'
use('MPLATE')
check('Mold Armor Plate keeps its own shape (Circle), apart from Armor Plate (Rect)', b.shape == 'CIRCLE')
use('PLATE')
check('... Armor Plate its own', b.shape == 'RECT')
# a tool kept before 0.24.328 (no Sketch of its own): Sketch off when it comes back
lm.store(S)['CUT'].pop('sketch_first', None)
use('SPLIT')
b.sketch_first = True
use('CUT')
check('a tool kept before (no Sketch of its own yet): Sketch off when it comes back', not b.sketch_first)
check('the timer keeps running', bpy.app.timers.is_registered(lm._tick))
summary()
