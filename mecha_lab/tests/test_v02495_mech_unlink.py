"""0.24.95 (user: "메테리얼 링크 끊는 버튼도 만들어 줄래?") Unlink: the selected parts get their own copy of the Mech
material (its settings as they are), the other parts keep the old one - changing the copy no longer changes them.
One copy shared by the selected parts; a mesh shared with other objects (a linked copy) gets the copy on the
object's slot.  In the Material page (Unlink next to New Copy, off when the material is this part's only) and in
the sidebar panel."""
from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, ui_bars

mecha_lab.register()
fresh()
C = bpy.context


def select(*obs):
    for o in C.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    C.view_layer.objects.active = obs[0]


a, b, c = cube('A', loc=(0, 0, 0)), cube('B', loc=(3, 0, 0)), cube('C', loc=(6, 0, 0))
select(a, b, c)
bpy.ops.mch.mech_shader_apply(preset='CHIPPED')
mat = a.active_material
mat.mch_mech.dirt = 0.4
check('Apply on three parts: one material shared by the three', b.active_material == mat
      and c.active_material == mat and len(ms.users_of(mat)) == 3)

select(a)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
btn = next(i for i in its if i.kind == 'tbtn' and i.label == 'Unlink')
check('Material page: "shared by 3 parts", Unlink on (clickable)', btn.enabled
      and any(i.kind == 'pnote' and 'shared by 3 parts' in i.label for i in its))
ui_bars.run(C, btn)
new = a.active_material
check('Unlink (a click on the drawn button): A gets its own copy, B and C keep the old one',
      new != mat and ms.is_mech(new) and b.active_material == mat and c.active_material == mat, new.name)
check('... the copy keeps the settings as they were (Chipped Paint, Dirt 0.4)',
      new.mch_mech.preset == 'CHIPPED' and abs(new.mch_mech.dirt - 0.4) < 1e-6)
new.mch_mech.roughness = 0.9
check('... changing the copy no longer changes the others', abs(mat.mch_mech.roughness - 0.9) > 0.1
      and abs(new.mch_mech.roughness - 0.9) < 1e-6)
its, _h = mu.content(C, 0.0, 276.0, 1.0)
btn = next(i for i in its if i.kind == 'tbtn' and i.label == 'Unlink')
check('... A\'s page: "this part only", Unlink off', not btn.enabled
      and any(i.kind == 'pnote' and 'this part only' in i.label for i in its))

select(b, c)
r = bpy.ops.mch.mech_shader_unlink()
check('B and C selected (all the parts that have it): nothing to unlink - left as it is',
      r == {'CANCELLED'} and b.active_material == mat and c.active_material == mat)

select(b)
d = bpy.data.objects.new('D', b.data)                  # a linked copy of B (the same mesh)
C.scene.collection.objects.link(d)
select(b)
bpy.ops.mch.mech_shader_unlink()
check('A part whose mesh a linked copy shares: the copy on the part\'s own slot, the linked copy keeps the old one',
      b.active_material not in (mat, None) and d.active_material == mat and b.material_slots[0].link == 'OBJECT'
      and c.active_material == mat, (b.active_material.name, d.active_material.name))
check('Sidebar panel: Unlink there too', 'mch.mech_shader_unlink' in __import__('inspect').getsource(ms.draw))
summary()
