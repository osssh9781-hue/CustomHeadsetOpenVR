"""0.24.49 UI / UX: RMB popup laid out like Substance 3D Modeler (tool strip | tool card | Actions panel of
icon buttons under small section titles), Recent tools and Favorites (kept across restarts), Quick HUD (key
settings as viewport sliders), bottom toolbar that shrinks / wraps on a narrow viewport (and the UI-scale
centring fix), key legend per drawing tool."""
import inspect
import os
import tempfile
import types

from _harness import bpy, check, cube, fresh, select_only, summary

import mecha_lab
from mecha_lab import actions_menu as am, bottom_bar as bb, key_legend as kl, last_used, tool_recent as tr
from mecha_lab import tool_state as ts, workspace_ui as wui

# keep the user's real config/mecha_lab/last_used.json out of the test
TMP = os.path.join(tempfile.mkdtemp(), 'last_used.json')
last_used._path = lambda: TMP
last_used._DATA = {}
mecha_lab.register()
fresh()
C = bpy.context

# --- Recent ---------------------------------------------------------------------------------------------
check('Recent is empty at first', tr.recent() == [])
for tid in ('CUT', 'PLATE', 'CUT', 'BASE', 'MASK', 'SCREW', 'DETAIL', 'SPLIT'):
    bb.note_tool(C, tid)
check('Recent: newest first, no repeats, hidden tools left out, at most 5',
      tr.recent() == ['SPLIT', 'DETAIL', 'SCREW', 'BASE', 'CUT'], tr.recent())
last_used.save()
last_used._DATA = None
check('... kept across a restart (last_used.json)', tr.recent()[0] == 'SPLIT' and os.path.exists(TMP))

# --- Favorites --------------------------------------------------------------------------------------------
check('Favorites: three sets with sensible defaults', tr.current_set() == 'MECHA'
      and tr.favorites()[:2] == ['CUT', 'SPLIT'] and 'CBASE' in tr.favorites('CREATURE'))
n0 = len(tr.favorites())
check('Star pins a tool, again unpins it', tr.toggle_favorite('CMOVE') and 'CMOVE' in tr.favorites()
      and not tr.toggle_favorite('CMOVE') and len(tr.favorites()) == n0)
for tid in ('CMOVE', 'CPATH', 'PERF'):
    tr.toggle_favorite(tid)
check('... at most 8 per set (a 9th is refused)', len(tr.favorites()) == tr.FAV_MAX
      and not tr.toggle_favorite('SDRAW') and 'SDRAW' not in tr.favorites())
C.window_manager.mch_fav_set = 'CREATURE'
check('Switching the set shows its own favorites', tr.current_set() == 'CREATURE'
      and tr.favorites()[0] == 'CBASE')
C.window_manager.mch_fav_set = 'MECHA'
r = bpy.ops.mch.tool_fav_toggle(tool='PERF')
check('Star operator works', r == {'FINISHED'} and 'PERF' not in tr.favorites())

# --- Actions popup ------------------------------------------------------------------------------------------
OPS = []
ERR = []


class Props:
    def __init__(self, idname):
        object.__setattr__(self, '_id', idname)
        mod, name = idname.split('.')
        try:
            object.__setattr__(self, '_p', getattr(getattr(bpy.ops, mod), name).get_rna_type().properties)
        except (AttributeError, KeyError):
            ERR.append('unknown operator ' + idname)
            object.__setattr__(self, '_p', None)

    def __setattr__(self, k, v):
        if self._p is not None and k not in self._p:
            ERR.append(f'{self._id}: no property {k}')


ICONS = set(bpy.types.UILayout.bl_rna.functions['label'].parameters['icon'].enum_items.keys())


class Lay:
    def __init__(self):
        self.scale_y = self.scale_x = 1.0
        self.enabled = self.active = True

    def _c(self, *a, **k):
        return Lay()

    row = column = box = split = grid_flow = _c

    def label(self, text='', **kw):
        if kw.get('icon') and kw['icon'] not in ICONS:
            ERR.append('bad icon ' + kw['icon'])

    def prop(self, data, name, **kw):
        if name not in data.bl_rna.properties:
            ERR.append('missing prop ' + name)

    def operator(self, idname, **kw):
        self.label(**kw)
        OPS.append((idname, kw.get('text', '')))
        return Props(idname)

    def template_icon(self, **kw):
        pass

    def separator(self, **kw):
        pass


part = cube('Part')
select_only(part)
am.draw(Lay(), C)
ids = {o for o, _t in OPS}
check('Actions popup draws: tool strip | Actions panel, valid operators and icons',
      not ERR and {'mch.set_tool', 'mch.tool_fav_toggle', 'mch.duplicate', 'object.join', 'object.delete',
                   'mch.actions_mirror', 'object.hide_view_set', 'object.hide_view_clear',
                   'view3d.localview', 'mch.one_click_remesh', 'mch.quad_remesh', 'mch.lowpoly_make'} <= ids,
      (ERR, sorted(ids)))
check('... Modeler style: icon-only buttons in the Actions panel, section titles Actions / Resolution / Symmetry / '
      'Repetition / Visibility', all(t == '' for o, t in OPS if o != 'wm.call_menu')
      and all(f"'{h}'" in inspect.getsource(am.draw_actions)
              for h in ('Actions', 'Resolution', 'Symmetry', 'Repetition', 'Visibility')))
OPS.clear()
ERR.clear()
wui.shape_card(Lay(), C)
check('Tool card (middle): Shapes / Stamps tabs, the shape grid, the key settings - no bad names', not ERR
      and "text='Stamps'" in inspect.getsource(wui.shape_card), ERR)
ERR.clear()
wui.profile_card(Lay(), C)
check('Base Mesh card draws too', not ERR, ERR)
check('Icon-only tool buttons still name the tool (tooltip "Cut: ...")',
      wui.MCH_OT_set_tool.description(C, types.SimpleNamespace(tool='CUT')).startswith('Cut: '))
check('... the tool RMB popups (shapes / profiles) show it on top; the big tool menu shows recent + favorites',
      'actions_menu.draw' in inspect.getsource(wui.MCH_PT_shape_popup.draw)
      and 'actions_menu.draw' in inspect.getsource(wui.MCH_PT_profile_popup.draw)
      and 'tool_recent.draw' in inspect.getsource(wui.MCH_PT_tool_popup.draw))
check('... a Live section only when something live is selected', not any(t == 'Apply Modifiers' for _o, t in OPS))

# symmetry
r = bpy.ops.mch.actions_mirror(axis=0)
m = am.mirror_mod(part)
check('Symmetry X: a live Mirror on the part (clipped, merged)', r == {'FINISHED'} and m is not None
      and tuple(m.use_axis) == (True, False, False) and m.use_clip)
from mecha_lab import core_geometry as cg
check('... the Cut / plate tools follow it (mirror reflections seen)', len(cg.mirror_reflections(part)) == 1)
bpy.ops.mch.actions_mirror(axis=2)
check('Symmetry Z added to the same mirror', tuple(m.use_axis) == (True, False, True)
      and len(cg.mirror_reflections(part)) == 3)
bpy.ops.mch.actions_mirror(axis=0)
bpy.ops.mch.actions_mirror(axis=2)
check('All axes off: the mirror is removed', am.mirror_mod(part) is None)
bpy.ops.mch.actions_mirror(axis=1)
OPS.clear()
am.draw(Lay(), C)
check('... the Live section offers Apply Modifiers once the part has one',
      any(o == 'mch.actions_apply_modifiers' for o, _t in OPS))
nv = len(part.data.vertices)
r = bpy.ops.mch.actions_apply_modifiers()
check('Apply Modifiers bakes the mirror', r == {'FINISHED'} and not part.modifiers
      and len(part.data.vertices) > nv, (nv, len(part.data.vertices)))

# RMB in Select / Move
items = [it for km in C.window_manager.keyconfigs.addon.keymaps for it in km.keymap_items
         if it.idname == 'mch.actions_menu']
check('RMB opens the Actions popup in Select / Move (one key item, Object Mode)', len(items) == 1
      and items[0].type == 'RIGHTMOUSE' and items[0].value == 'PRESS')
outside = types.SimpleNamespace(workspace=types.SimpleNamespace(name='Layout', get=lambda k, d=None: d),
                                mode='OBJECT', area=types.SimpleNamespace(type='VIEW_3D'),
                                window_manager=C.window_manager, scene=C.scene)
check('... but not outside MECHA LAB (Blender\'s RMB menu stays there)', not am.select_rmb_ok(outside))
check('... the popup has a button for Blender\'s own object menu',
      'VIEW3D_MT_object_context_menu' in inspect.getsource(am.MCH_PT_actions_popup.draw))
check('... it can be switched off (Preferences: RMB Actions Menu)', "pref('rmb_actions'" in inspect.getsource(am))

# --- Quick HUD --------------------------------------------------------------------------------------------
from mecha_lab import quick_hud as qh
cut_items = qh.items(C, 'CUT')
check('Quick HUD: Cut shows depth, GN finish, width, segments, ramp', [p for _d, p in cut_items]
      == ['depth', 'gn_finish', 'gn_width', 'gn_segments', 'gn_ramp'], [p for _d, p in cut_items])
check('... every core tool has 1-5 rows that exist', all(1 <= len(qh.items(C, t)) <= qh.MAX_ROWS
      for t in ('CUT', 'SPLIT', 'BASE', 'CBASE', 'PLATE', 'SDRAW', 'SCREW', 'CMOVE', 'CPATH', 'TUBE')),
      {t: len(qh.items(C, t)) for t in ('CUT', 'SPLIT', 'BASE', 'CBASE', 'PLATE', 'SDRAW', 'SCREW', 'CMOVE',
                                         'CPATH', 'TUBE')})
cut = C.scene.mch_cut
check('Drag: +300 px ≈ the whole soft range, Shift = a tenth, clamped',
      abs(qh.drag_value(cut, 'depth', 0.2, 30) - qh.drag_value(cut, 'depth', 0.2, 300, fine=True)) < 1e-9
      and qh.drag_value(cut, 'depth', 0.2, -1e6) >= cut.bl_rna.properties['depth'].hard_min)
check('... whole numbers: 1 step per 8 px', qh.drag_value(cut, 'gn_segments', 3, 16) == 5)
old = cut.gn_finish
qh.step_choice(cut, 'gn_finish')
check('Click on a choice steps to the next one', cut.gn_finish != old)
cut.depth = 0.37
qh.reset(cut, 'depth')
check('Ctrl+click: back to the default', abs(cut.depth - cut.bl_rna.properties['depth'].default) < 1e-6)
check('Value text: name and value', qh.value_text(cut, 'gn_ramp').endswith(('On', 'Off')))
grip, rows = qh.layout_rows(1200, 800, 4)
grip2, rows2 = qh.layout_rows(1200, 800, 4, offset=(100, -50))
check('HUD sits upper left, rows under the grip, the grip moves it',
      grip[1] > rows[0][1] > rows[-1][1] and grip[0] < 400 and abs(grip2[0] - grip[0] - 100) < 1e-6
      and abs(grip2[1] - grip[1] + 50) < 1e-6)
gripc, rowsc = qh.layout_rows(300, 200, 5, offset=(5000, 5000))
check('... kept inside the viewport', all(0 < x < 300 and 0 < y < 200 for x, y in [gripc] + rowsc))
check('HUD click operator and value popup registered; hidden outside MECHA LAB (0.24.51: no gizmos)',
      qh.MCH_OT_quick_hud_press in qh.CLASSES and hasattr(bpy.types, 'MCH_PT_quick_value') and not qh.visible(outside))
check('... Armor Plate: hidden while its own live HUD is up (no double HUD)',
      'pending_plate(context) is not None' in inspect.getsource(qh._plate_scene))

# --- Bottom toolbar -----------------------------------------------------------------------------------------
n = len(bb.BAR_TOOLS)
pos, d = bb.toolbar_layout(1600, 1.0, n, 'M')
check('Wide viewport: one row, full size (as before)', len({round(y, 3) for _x, y in pos}) == 1
      and abs(d - bb.SIZES['M']) < 1e-6)
pos, d = bb.toolbar_layout(700, 1.0, n, 'M')
xs = [x for x, _y in pos]
check('Narrow (700 px): smaller buttons, one row, all inside', len({round(y, 3) for _x, y in pos}) == 1
      and d < bb.SIZES['M'] and min(xs) - d / 2 >= 0 and max(xs) + d / 2 <= 700, (d, min(xs), max(xs)))
pos, d = bb.toolbar_layout(420, 1.0, n, 'M')
xs = [x for x, _y in pos]
ys = sorted({round(y, 3) for _x, y in pos})
check('Very narrow (420 px): two rows, all inside, rows apart', len(ys) == 2 and min(xs) - d / 2 >= 0
      and max(xs) + d / 2 <= 420 and ys[1] - ys[0] > d, (d, ys))
check('UI scale fix: the toolbar is centred with the unscaled width',
      'region.width / max(ui, 1e-3)' in inspect.getsource(bb.MCH_GGT_bottom_toolbar.draw_prepare))

# --- Key legend -----------------------------------------------------------------------------------------
cut = kl.lines('CUT')
check('Key legend: the tool name, what Alt does there, the shared keys', cut[0] == 'CUT'
      and any(l.startswith('Alt') and 'keep the inside' in l for l in cut)
      and any(l.startswith('RMB') for l in cut) and any('Concept Move' in l for l in cut))
check('... Armor Plate: Alt carves, wheel = profile', any('carve' in l for l in kl.lines('PLATE'))
      and any('Wheel' in l for l in kl.lines('PLATE')))
check('... tools without an Alt meaning show none; unknown tool: nothing',
      not any(l.startswith('Alt') for l in kl.lines('SPLIT')) and kl.lines('NOPE') == [])
check('... can be switched off (Preferences: Key Legend)', "pref('key_legend'" in inspect.getsource(kl))
check('Preferences show the new switches', all(f"'{k}'" in inspect.getsource(wui.MCH_AddonPreferences.draw)
                                               for k in ('rmb_actions', 'key_legend', 'quick_hud')))
summary()
