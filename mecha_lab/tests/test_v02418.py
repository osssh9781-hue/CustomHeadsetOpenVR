"""0.24.18 Box Hide Split Off: the hidden part becomes a mesh of its own (like Split), the rest keeps the hole;
both closed, volumes add up; works with Open (cap off) too; the button is in the Box Hide panel."""
import sys

_src = open(__file__.replace('test_v02418.py', 'test_v0200.py')).read()
exec(_src.split('\nfresh()\nmecha_lab.register()')[0])

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
from mecha_lab import box_hide as bh

S.mch_brush.shape = 'LASSO'
S.mch_brush.line_open = False
MODE[0], NATIVE[0] = 'HIDE', 'mecha.box_hide'
S.mch_settings.mch_active_tool = 'HIDE'
S.mch_cut.targets = 'AUTO'

for cap in (True, False):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    S.mch_hide.cap = cap
    b = cube('Body', 2.0)
    C.view_layer.update()
    v0 = volume(b)
    r, m = lasso([(550, 300), (700, 300), (700, 700), (550, 700)])      # world x 0.5 .. 2 (the right part)
    check(f'cap {cap}: hidden', bh.is_hidden(b), m)
    for o in C.selected_objects:
        o.select_set(False)
    res = bh.MCH_OT_box_hide_split.execute(types.SimpleNamespace(report=lambda *a: None), C)
    piece = bpy.data.objects.get('Body_Hidden')
    check(f'cap {cap}: Split Off made a separate mesh', res == {'FINISHED'} and piece is not None and
          piece.type == 'MESH' and not bh.is_hidden(piece), res)
    check(f'cap {cap}: the rest has a real hole, no Box Hide modifier left', not bh.is_hidden(b) and not b.modifiers)
    check(f'cap {cap}: both closed solids', non_manifold(b) == 0 and non_manifold(piece) == 0,
          (non_manifold(b), non_manifold(piece)))
    vb, vp = volume(b), volume(piece)
    check(f'cap {cap}: volumes add up (rest {vb:.3f} + part {vp:.3f} = {v0:.3f})', abs(vb + vp - v0) < 1e-3 and
          abs(vp - 2.0) < 1e-3, (vb, vp, v0))
    check(f'cap {cap}: the new part is selected / active', C.view_layer.objects.active == piece and piece.select_get())
    check(f'cap {cap}: no hide volume left', not [o for o in bpy.data.objects if o.get(bh.VOL_KEY)])
check('Split Off button in the Box Hide panel', "mch.box_hide_split" in open(bh.__file__).read().split('def draw(')[1])
res = None
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
cube('Plain', 2.0)
res = bh.MCH_OT_box_hide_split.execute(types.SimpleNamespace(report=lambda *a: None), C)
check('nothing hidden: Split Off does nothing', res == {'CANCELLED'} and len(bpy.data.objects) == 1)
mecha_lab.unregister()
sys.exit(1 if summary() else 0)
