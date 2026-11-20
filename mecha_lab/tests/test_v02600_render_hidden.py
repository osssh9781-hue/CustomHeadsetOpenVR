"""0.24.180 (user: "내가 눈을 끈 메쉬들을 렌더를 안 하게, 눈 끈 거만 한 번에 카메라 꺼지게 가능? 다시 켜는 것도"): the Layers
window's "Hidden: No Render" leaves every eye-off part out of renders (its own eye or its folder's), a part shown is
left alone, one you turned off yourself is not marked; "Render Again" brings back only the ones it turned off."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import layers_panel as lp, render_hidden as rh  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
S.mch_hidden_auto = False                  # (0.24.270 Auto off: the buttons by hand, as tested here)


def cube(name, x, coll=None):
    bpy.ops.mesh.primitive_cube_add(size=1.0, location=(x, 0.0, 0.0))
    o = C.active_object
    o.name = name
    if coll is not None:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
    return o


shown = cube('Shown', 0.0)
hid = cube('Hidden', 2.0)
mine = cube('Mine', 4.0)
folder = bpy.data.collections.new('Folder')
S.collection.children.link(folder)
inf = cube('InFolder', 6.0, folder)
hid.hide_set(True)
mine.hide_set(True)
mine.hide_render = True                                 # (turned off by the user already)
C.view_layer.layer_collection.children['Folder'].hide_viewport = True
cells = rh.toolbar_cells(C)[1:]                         # (0.24.270: Auto first)
check(f'the Layers window\'s row: {[c[0] for c in cells]}', cells[0][0] == 'No Render (2)' and cells[0][2]
      and cells[1][0] == 'Render Again (0)' and not cells[1][2])
r = bpy.ops.mch.hidden_no_render()
check(f'Hidden: No Render ({r}): the eye-off part and the one in the closed folder out of renders '
      f'({hid.hide_render}, {inf.hide_render}); the shown one in ({not shown.hide_render}); yours not marked '
      f'({rh.MARK not in mine})', r == {'FINISHED'} and hid.hide_render and inf.hide_render and not shown.hide_render
      and mine.hide_render and rh.MARK not in mine and hid.get(rh.MARK) and inf.get(rh.MARK))
r = bpy.ops.mch.render_again()
check(f'Render Again ({r}): those two back in renders ({not hid.hide_render}, {not inf.hide_render}), yours still '
      f'off ({mine.hide_render}), no marks left', r == {'FINISHED'} and not hid.hide_render and not inf.hide_render
      and mine.hide_render and not rh.turned_off())
from mecha_lab.mecha_menu import Item  # noqa: E402,F401
items, _h = lp.content(C, 0.0, 300.0, 1.0)
labels = [getattr(i, 'label', '') for i in items]
check(f'in the Layers window ({[l_ for l_ in labels if "Render" in l_]})',
      any(l_.startswith('No Render') for l_ in labels) and any(l_.startswith('Render Again') for l_ in labels))
summary()
