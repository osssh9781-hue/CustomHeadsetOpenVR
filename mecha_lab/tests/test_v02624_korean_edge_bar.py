"""0.24.212 (user: "한글 번역 버전도 싹 다 만들고 그걸 한글 / 영어 에드온 설정에서 바꿀 수 있게 해 줘"; "베이스 메쉬 챔퍼나 베벨
두께 조절할 때 위랑 아래 어디 할지 선택하는 게 마우스 대면 사라졌다가 꾹 누르고 있어야 나타나는 것도 불편하니까 그냥 잘 나오게
해 주고 위아래 베벨 조절도 섬세하게"): the Korean table looked up when drawing; Base Mesh's bevel sides as buttons with the
top and the bottom each their own width; the top bar's number cells drag finely; lists open on release."""
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import base_mesh, i18n, quick_hud, top_bar, ui_bars, workspace_ui as wu  # noqa: E402
from mecha_lab.i18n_ko import KO  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
check(f'the Korean table: {len(KO):,} sentences, every one with the same number of # as its English',
      len(KO) > 8000 and all(k.count('#') == v.count('#') for k, v in KO.items()))
check('the tests read English (MCH_LANG=EN): tr() gives the sentence back', i18n.lang() == 'EN'
      and i18n.tr('Thickness') == 'Thickness')
i18n.force('KO')
th, gr = i18n.tr('Thickness'), i18n.tr('Gravity')
check(f'Korean on: Thickness -> {th}, Gravity -> {gr}; a sentence not in the table and an object\'s name stay as they are',
      th == '두께' and gr == '중력' and i18n.tr('Zzz not a sentence') == 'Zzz not a sentence'
      and i18n.tr(i18n.raw('Thickness')) == 'Thickness')
key = next(k for k in KO if k.count('#') == 1 and not any(ch.isdigit() for ch in k))
shown = i18n.tr(key.replace('#', '37'))
check(f'a sentence with a number: "{key}" asked with 37 -> "{shown}" (the number put back)',
      '37' in shown and shown != key.replace('#', '37'))
check(f'the width of a Korean word counts its letters wide ("{th}": {i18n.vlen("Thickness"):.1f} Latin letters, not 2)',
      abs(i18n.vlen('Thickness') - 3.5) < 1e-6)
i18n.force('EN')
check('... English again: Thickness', i18n.tr('Thickness') == 'Thickness')
i18n.force(None)
p = wu.prefs()
check('Preferences > Korean: on by default, kept with the sizes (it survives a reinstall)',
      'korean' in wu.SIZE_KEYS and (p is None or p.korean is True))

# Base Mesh: the bevel sides in the top bar
d = base_mesh.scene_defaults(C)
d.profile, d.bevel_sides, d.bevel_link = 'BEVEL', 'TOP', True


def edge_cells():
    g = dict(top_bar.edge_groups(C, 'BASE'))
    return g['Edge'] + g.get('Sides', [])


cells = edge_cells()
labels = [c['label'] for c in cells]
check(f'Base Mesh, Bevel: the sides are buttons, always there ({labels}) - no closed list',
      all(x in labels for x in ('Top', 'Bottom', 'Both', 'Off')) and not any(c['kind'] == 'drop' for c in cells)
      and 'Width' in labels and 'Segments' in labels)
d.bevel_sides = 'BOTH'
l1 = [c['label'] for c in edge_cells()]
d.bevel_link = False
l2 = [c['label'] for c in edge_cells()]
check(f'Both: a Same switch; off -> the top and the bottom each their own width and segments ({l2[-5:]})',
      'Same' in l1 and 'Width' in l1 and all(x in l2 for x in ('Top W', 'Top Segs', 'Bottom W', 'Bottom Segs')))
d.profile = 'CHAMFER'
l3 = [c['label'] for c in edge_cells()]
check(f'Chamfer: widths only ({l3[-3:]})', 'Top W' in l3 and 'Bottom W' in l3 and 'Top Segs' not in l3)
d.bevel_sides = 'NONE'
check('Off: no width cells', not any(c['kind'] == 'mini' for c in edge_cells()))
d.bevel_sides, d.bevel_link, d.profile = 'TOP', True, 'BEVEL'
# the number cells of the top bar drag finely
coarse = quick_hud.drag_value(d, 'bevel_width', 0.05, 10, px=130) - 0.05
fine = quick_hud.drag_value(d, 'bevel_width', 0.05, 10, px=130, gentle=True) - 0.05
finer = quick_hud.drag_value(d, 'bevel_width', 0.05, 10, fine=True, px=130, gentle=True) - 0.05
zero = quick_hud.drag_value(d, 'bevel_width', 0.0, 10, px=130, gentle=True)
big = quick_hud.drag_value(d, 'bevel_width', 1.5, 10, px=130, gentle=True) - 1.5
check(f'a 0.05 bevel dragged 10 px: {coarse:.4f} before, {fine:.4f} now (Shift {finer:.5f}); from 0 it still moves '
      f'({zero:.4f}); a big value as fast as before ({big:.3f})',
      fine < coarse * 0.2 and abs(finer - fine * 0.1) < 1e-9 and zero > 0.0 and abs(big - 10 * 2.0 / 130) < 1e-6)
check('a list of the drawn UI opens when the button comes up (mch.ui_menu_release), not as a hold-and-drag pop-up',
      hasattr(bpy.types, 'MCH_OT_ui_menu_release') and 'open_menu' in dir(ui_bars))
summary()
