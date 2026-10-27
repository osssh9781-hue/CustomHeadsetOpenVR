"""0.24.51 One size for all viewport popups (− / + in the Mecha Menu, Ctrl + wheel over it, sidebar Icon Size >
Viewport Popups, kept with the other sizes).  Quick HUD rows take the mouse again (a click operator that checks the HUD first and passes every
other click on to the tool, instead of gizmos the drawing tools' own left click could beat); middle click (no
movement) opens the Mecha Menu, a middle drag still orbits."""
import inspect
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import mecha_menu as mm, quick_hud as qh, workspace_ui as wui, screw_stamp, primitive_place

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
S.mch_settings.mch_active_tool = 'CUT'

check('Every Mecha drawing tool (and Screw, Primitive) asks the HUD first on a left click',
      all([k[0] for k in wui._tool_keymap(m)][:4] == ['mch.concept_hold', 'mch.quick_hud_press', 'mch.quick_hud_press',
                                                       'mch.cut_stroke']
          for m in ('CUT', 'BASE'))         # hold D + drag stays first (0.24.37), then the HUD (press, 0.24.57 double)
      and [k[0] for k in screw_stamp.TOOL_KEYMAP].index('mch.quick_hud_press')
      < [k[1].get('value') for k in screw_stamp.TOOL_KEYMAP].index('PRESS') + 1
      and primitive_place.TOOL_KEYMAP[0][0] == 'mch.quick_hud_press')
km_items = [it for km in C.window_manager.keyconfigs.addon.keymaps if km.name == '3D View' for it in km.keymap_items
            if it.idname == 'mch.quick_hud_press']
check('... and in 3D View for the other tools (Concept / Path Move, Curve): press and (0.24.57) double-click',
      len(km_items) == 2 and {it.value for it in km_items} == {'PRESS', 'DOUBLE_CLICK'}
      and all(it.type == 'LEFTMOUSE' and it.any for it in km_items))
check('... the old HUD gizmos are gone (nothing can beat the click any more)',
      not hasattr(qh, 'MCH_GGT_quick_hud') and qh.MCH_OT_quick_hud_press in qh.CLASSES)
src = inspect.getsource(qh.MCH_OT_quick_hud_press.invoke)
check('... a click that is not on the HUD passes on to the tool', "return {'PASS_THROUGH'}" in src)

# where the rows are: same place as they are drawn
region = types.SimpleNamespace(width=1600, height=900, x=0, type='WINDOW')
fake = types.SimpleNamespace(region=region, area=None, scene=S, window_manager=C.window_manager,
                             preferences=C.preferences, active_object=None, selected_objects=[])
qh_visible = qh.visible
qh.visible = lambda c: True
its, grip, rows = qh.current(fake)
check('HUD rows and title under the view text (as drawn)', its and len(rows) == len(its)
      and grip[1] > rows[0][1] and grip[1] < 900)
x, y = rows[1]
check('Hit test: a row', qh.hit(fake, x + 30, y + 3) == ('row', 1))
check('... the title row (move the HUD)', qh.hit(fake, grip[0], grip[1]) == ('grip', None))
check('... elsewhere nothing (the click goes to the tool)', qh.hit(fake, 1500, 100) is None)
C.window_manager.mch_hud_offset = (200.0, -40.0)
its2, grip2, rows2 = qh.current(fake)
check('... moved HUD: the hit area moves with it', qh.hit(fake, rows2[1][0], rows2[1][1]) == ('row', 1)
      and abs(grip2[0] - grip[0] - 200) < 1e-6)
C.window_manager.mch_hud_offset = (0.0, 0.0)
qh.visible = qh_visible
src = inspect.getsource(qh.MCH_OT_quick_hud_press.modal)
check('Drag = value (Shift fine), Esc / RMB = back, click = type / next choice, Ctrl+click = default, undo step',
      'drag_value' in src and 'event.shift' in src and "'ESC'" in src and 'step_choice' in src
      and 'reset(' in src and 'undo_push' in src and 'MCH_PT_quick_value' in src)

# middle click
mmb = [it for km in C.window_manager.keyconfigs.addon.keymaps for it in km.keymap_items
       if it.idname == 'mch.mecha_mmb_gate']
check('Middle click: one key item, middle mouse with no Shift / Ctrl (pan / zoom untouched)', len(mmb) == 1
      and mmb[0].type == 'MIDDLEMOUSE' and mmb[0].value == 'PRESS' and not mmb[0].shift and not mmb[0].ctrl
      and not mmb[0].any)
src = inspect.getsource(mm.MCH_OT_mecha_mmb_gate.modal)
check('... no movement + let go = the menu; a drag = the usual orbit', 'open_menu' in src
      and 'view3d.rotate' in src and "'RELEASE'" in src)
outside = types.SimpleNamespace(workspace=types.SimpleNamespace(name='Layout', get=lambda k, d=None: d),
                                mode='OBJECT', area=types.SimpleNamespace(type='VIEW_3D'), scene=S,
                                window_manager=C.window_manager)
check('... only in MECHA LAB, can be switched off', not mm.MCH_OT_mecha_mmb_gate.poll(outside)
      and "pref('mmb_menu'" in inspect.getsource(mm.MCH_OT_mecha_mmb_gate.poll)
      and "'mmb_menu'" in inspect.getsource(wui.MCH_AddonPreferences.draw))

# one size for the viewport popups
items = mm.build(C, 800, 450, 1600, 900, 1.0)
pills = [i.label for i in items if i.kind == 'pill']
check('Mecha Menu: − / + size buttons under the tool strip', '−' in pills and '+' in pills)
p = wui.prefs()
before = mm.ui_size()
mm.run(C, next(i for i in items if i.kind == 'pill' and i.label == '+'))
check('... + makes everything bigger (preference Viewport Popups), − smaller, kept in 0.5 - 3',
      (p is None) or (abs(mm.ui_size() - before - 0.1) < 1e-6), (before, mm.ui_size()))
mm.set_ui_size(99)
check('... clamped', p is None or mm.ui_size() == 3.0)
mm.set_ui_size(1.0)
check('Ctrl + wheel over the menu resizes it', "event.ctrl and event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}"
      in inspect.getsource(mm.MCH_OT_mecha_menu.modal))
check('Sidebar Icon Size shows Viewport Popups; presets and the saved sizes include it',
      "'mecha_ui_size'" in inspect.getsource(wui.draw_icon_sizes) and 'mecha_ui_size' in wui.SIZE_KEYS
      and 'mecha_ui_size' in inspect.getsource(wui.MCH_OT_icon_size_preset.execute))
from mecha_lab import ui_gpu as G
check('The size factor follows it (menu, Quick HUD, key legend all use ui_factor)',
      "pref('mecha_ui_size'" in inspect.getsource(G.ui_factor) and 'ui_factor' in inspect.getsource(qh.current)
      and 'ui_factor' in inspect.getsource(mecha_lab.key_legend._draw))
summary()
