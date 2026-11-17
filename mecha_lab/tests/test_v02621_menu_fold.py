"""0.24.207 (user: "아래 있는 이거는 이제 기본으로 접어 두자"): the bottom tool menu folds to a small tab; folded by
default (the preference); the tab opens it, its Fold button folds it; what sits above it moves down."""
from types import SimpleNamespace

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import ui_bars as ub, workspace_ui as wu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
check('the preference: Tool Menu Folded, on by default, kept with the sizes',
      wu.MCH_AddonPreferences.bl_rna.properties['menu_folded'].default is True and 'menu_folded' in wu.SIZE_KEYS
      if hasattr(wu, 'MCH_AddonPreferences') else 'menu_folded' in wu.SIZE_KEYS)
ctx = SimpleNamespace(area=None, region=None, scene=C.scene, window_manager=C.window_manager, mode='OBJECT',
                      workspace=C.workspace, preferences=C.preferences, view_layer=C.view_layer,
                      active_object=None, selected_objects=[], space_data=None)
real_left, real_on = ub.left_inset, ub.menu_on
ub.left_inset = lambda c: 0.0
ub.menu_on = lambda c: True
ub.set_menu_folded(False)
full = ub.menu_items(ctx, 1920, 1080, 1.0)
h_full = ub.bottom_taken(ctx, 1.0, 1920)
fold_btn = [i for i in full if i.kind == 'tbtn' and i.action == ('op', 'mch.menu_fold', {})]
check(f'open: the tool tiles ({sum(1 for i in full if i.kind == "sbtn")}) and a Fold button on the card',
      sum(1 for i in full if i.kind == 'sbtn') > 60 and len(fold_btn) == 1 and fold_btn[0].label == 'Fold')
bpy.ops.mch.menu_fold()
tab = ub.menu_items(ctx, 1920, 1080, 1.0)
h_fold = ub.bottom_taken(ctx, 1.0, 1920)
check(f'folded (the Fold button\'s operator): one small tab, no tiles; it takes {h_fold:.0f} px of the bottom instead '
      f'of {h_full:.0f}', ub.menu_folded() and not [i for i in tab if i.kind == 'sbtn'] and tab[0].kind == 'card'
      and tab[0].w < 200 and len([i for i in tab if i.action == ('op', 'mch.menu_fold', {})]) == 1
      and h_fold < h_full * 0.6)
bpy.ops.mch.menu_fold()
check('the tab clicked: open again', not ub.menu_folded()
      and sum(1 for i in ub.menu_items(ctx, 1920, 1080, 1.0) if i.kind == 'sbtn') > 60)
ub.FOLD[0] = None
ub.left_inset, ub.menu_on = real_left, real_on
summary()
