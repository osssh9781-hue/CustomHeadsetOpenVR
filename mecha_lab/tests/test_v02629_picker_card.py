"""0.24.223 the picker card (float_card): the Press Cut stamps as a card of our own - it is built from a panel-like
drawer, a pick runs the operator and closes it, the X closes it; the colour ramps are dialogs; the value popups
activate their number."""
import inspect

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import float_card, ui_bars, press_cut, bg_color, backdrops, quick_hud


mecha_lab.register(); fresh()
C = bpy.context; S = C.scene
float_card.close()
check('closed: no items', not float_card.is_open() and float_card.items(C, 1600, 900) == [])
float_card.open('Press Cut Stamps', press_cut.stamp_tiles, width=760)
its = float_card.items(C, 1600, 900, 1.0)
tiles = [i for i in its if i.kind == 'mtile']
check('open: a solid card first', float_card.is_open() and its[0].kind == 'card' and its[0].icon == 'solid')
check('the X button', any(i.kind == 'pbtn' and i.action == ('float_close',) for i in its))
check(f'stamp tiles ({len(tiles)})', len(tiles) >= 13 and all(t.action[1] == 'mch.press_pick_shape' for t in tiles))
check('tiles inside the card', all(its[0].x - 0.5 <= t.x and t.x + t.w <= its[0].x + its[0].w + 0.5 for t in tiles))
check('the stamp in use is marked', sum(1 for t in tiles if t.on) == (0 if S.mch_press.drawn else 1))
small = float_card.layout(C, 1600, 400, 1.0)
check('a low viewport: scrolls', small['content'] > small['view'] and any(i.kind == 'sbar' for i in small['items']))
float_card.scroll_by(C, 1600, 400, 1.0, 120)
check('scroll_by moves it', float_card.CARD['scroll'] > 0)
x_btn = next(i for i in its if i.kind == 'pbtn')
ui_bars.run(C, x_btn)
check('the X closes it', not float_card.is_open())
float_card.open('Press Cut Stamps', press_cut.stamp_tiles, width=760)
ui_bars.release_refs()
check('undo / file load: closed', not float_card.is_open())
src = inspect.getsource(ui_bars.run)
check('a pick closes the card (ui_bars.run)', 'float_card.holds' in src and 'float_card.close()' in src)
check('the colour ramps: dialogs (they stay)', 'invoke_props_dialog' in inspect.getsource(bg_color.MCH_OT_bg_ramp.invoke)
      and 'invoke_props_dialog' in inspect.getsource(backdrops.MCH_OT_mech_bg_ramp.invoke))
check('the colour picker dialog is registered', hasattr(bpy.types, 'MCH_OT_ui_colour'))
check('value popups: ready to type', 'activate_init' in inspect.getsource(ui_bars.MCH_PT_ui_value.draw)
      and 'activate_init' in inspect.getsource(quick_hud.MCH_PT_quick_value.draw))

summary()
