"""0.24.240 (user: "메쉬 잡고 뷰포트에서 이동시키는데 너무 버벅거리지"): our cards are kept as a picture and drawn again
only when something in them changed - the picture's key changes with every item, value, hover and size; a mesh only
moved does not rebuild the cards, any other change does."""
from types import SimpleNamespace as NS

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import ui_bars as ub  # noqa: E402
from mecha_lab.mecha_menu import Item  # noqa: E402

mecha_lab.register(); fresh()
C = bpy.context
S = C.scene
reg = NS(width=1000, height=800)
its = [Item('card', 0, 0, 100, 50), Item('seg', 10, 10, 40, 20, 'Box', '', False, True, ('x',)),
       Item('mini', 60, 10, 40, 20, 'Res', '', False, True, ('y',), S, 'frame_start')]
k0 = ub.picture_key(reg, its, None, 1.0, (False, None))
check('the same cards: the same key', k0 == ub.picture_key(reg, its, None, 1.0, (False, None)))
check('the hover changes it', k0 != ub.picture_key(reg, its, its[1], 1.0, (False, None)))
S.frame_start = S.frame_start + 3
k1 = ub.picture_key(reg, its, None, 1.0, (False, None))
check('a shown value changes it', k1 != k0)
its[1].on = True
check('a button turned on changes it', ub.picture_key(reg, its, None, 1.0, (False, None)) != k1)
its[1].label = 'Kreis'
check('a label changes it', ub.picture_key(reg, its, None, 1.0, (False, None)) != k1)
check('the size changes it', ub.picture_key(NS(width=999, height=800), its, None, 1.0, (False, None)) != k1)
check('the colour mode changes it', ub.picture_key(reg, its, None, 1.0, (True, None)) != k1)


def U(idb, t=False, g=False, s=False):
    return NS(id=idb, is_updated_transform=t, is_updated_geometry=g, is_updated_shading=s)


ob = bpy.data.objects[0] if bpy.data.objects else None
if ob is None:
    bpy.ops.mesh.primitive_cube_add()
    ob = C.active_object
check('a mesh only moved: not rebuilt', ub.moved_only(NS(updates=[U(ob, t=True)])))
check('geometry changed: rebuilt', not ub.moved_only(NS(updates=[U(ob, t=True, g=True)])))
check('a scene value changed: rebuilt', not ub.moved_only(NS(updates=[U(ob, t=True), U(S)])))
check('no updates: rebuilt (as before)', not ub.moved_only(NS(updates=[])))
v = ub.VERSION[0]
ub._dirty_handler(S, NS(updates=[U(ob, t=True)]))
check('the handler keeps the cards on a move', ub.VERSION[0] == v)
ub._dirty_handler(S, NS(updates=[U(S)]))
check('the handler rebuilds them on any other change', ub.VERSION[0] != v)
v = ub.VERSION[0]
ub._dirty_handler()
check('called without a depsgraph (undo / redo): rebuilt as before', ub.VERSION[0] != v)
summary()
