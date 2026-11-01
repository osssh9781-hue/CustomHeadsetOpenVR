"""0.24.95 (user: "우리 예쁘게 만든 우리의 유아이가 이미 메카 랩에 있는데 왜 다시 블렌더 기본 패널로 바꿨어") The Mech
Shader and the HDRI in Mecha Lab's own side panel: a Material page (tabs Tool | Material at the panel's top, the
Mecha Menu's Material button), its rows in the Mecha look - ◀ [list] ▶ steppers, number bars, colour swatches,
foldable sections (a layer in use starts open), the HDRI folder chooser."""
import os
import tempfile

from _harness import bpy, check, cube, fresh, summary

import mecha_lab
from mecha_lab import mech_shader as ms, mech_shader_ui as mu, mecha_menu, side_panel as sp, ui_bars, workspace_ui

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene


def page(**kw):
    its, h = mu.content(C, 0.0, 276.0, 1.0)
    return its, h


def by_prop(its, prop, kind=None):
    return [i for i in its if getattr(i, 'prop', '') == prop and (kind is None or i.kind == kind)]


def heads(its):
    return {i.label.split('   ')[0]: i for i in its if i.kind == 'shead'}


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


ob = cube('Part')
select(ob)
its, h = page()
check('No Mech material yet: ◀ [preset] ▶ on the scene\'s preset, Apply Mech Shader, the HDRI section',
      by_prop(its, 'mch_mech_preset', 'drop') and any(i.kind == 'tbtn' and i.label == 'Apply Mech Shader' for i in its)
      and 'HDRI' in heads(its) and h > 0, [i.label for i in its if i.kind in {'tbtn', 'shead'}])
apply_btn = next(i for i in its if i.kind == 'tbtn' and i.label == 'Apply Mech Shader')
ui_bars.run(C, apply_btn)
mat = ms.active_mech(C)
check('... a click on Apply makes the Mech material (the drawn button runs mch.mech_shader_apply)', mat is not None,
      ob.active_material)
st = mat.mch_mech

its, _h = page()
surface = {i.prop: i.kind for i in its if i.data == st}
check('Surface: Base Color a swatch, Metallic / Roughness / Glass / Alpha / Clear Coat / Brushed as bars',
      surface.get('base_color') == 'swatch' and all(surface.get(p) == 'mini' for p in
                                                     ('metallic', 'roughness', 'glass', 'alpha', 'coat', 'aniso')),
      surface)
check('... IOR only with Glass on', 'ior' not in surface)
st.glass = 0.6
its, _h = page()
check('... Glass 0.6: IOR shows', by_prop(its, 'ior', 'mini'))

before = st.preset
nxt = next(i for i in its if i.kind == 'tbtn' and i.label == '▶' and i.action[1] == 'mch.mech_shader_step'
           and i.action[2].get('prop') == 'preset')
ui_bars.run(C, nxt)
check('◀ [preset] ▶: ▶ steps the material to the next preset', st.preset != before, (before, st.preset))

st.preset = 'CHIPPED'
its, _h = page()
hd = heads(its)
check('Sections: Surface, Maps, Paint & Wear, Scratches, Rust, Dirt, Snow, Glow, Weave, Height & Detail, HDRI',
      all(t in hd for t in ('SURFACE', 'MAPS', 'PAINT & WEAR', 'SCRATCHES', 'RUST', 'DIRT', 'SNOW', 'GLOW', 'WEAVE',
                            'HEIGHT & DETAIL', 'HDRI')), sorted(hd))
used = mu.in_use(mat, st)
check('Chipped Paint: the layers in use start open (Paint & Wear), the others folded (Snow, Glow, Weave)',
      'chip' in used and hd['PAINT & WEAR'].on and not hd['SNOW'].on and not hd['GLOW'].on and not hd['WEAVE'].on,
      sorted(used))
check('... a layer\'s amount in its title (Paint & Wear  NN %)', '%' in next(i.label for i in its if i.kind == 'shead'
                                                                       and i.label.startswith('PAINT & WEAR')))
check('... Paint & Wear open: paint colour + primer colour swatches, Edge Wear bar, its map ◀ [Chips] ▶, height',
      by_prop(its, 'paint_color', 'swatch') and by_prop(its, 'primer_color', 'swatch')
      and by_prop(its, 'edge_wear', 'mini') and by_prop(its, 'chip_map', 'drop') and by_prop(its, 'h_chip', 'mini'))
check('... Dirt folded: its rows not there', not by_prop(its, 'dirt_top'))
ui_bars.run(C, hd['DIRT'])
its, _h = page()
check('A click on DIRT opens it: In Crevices / On Top / From Below / Dust / Grime Streaks bars, its colour, map',
      all(by_prop(its, p, 'mini') for p in ('dirt', 'dirt_top', 'dirt_low', 'dust', 'streaks'))
      and by_prop(its, 'dirt_color', 'swatch') and by_prop(its, 'dirt_map', 'drop'))
st.dirt = 0.0
st.dirt_top = 0.0
its, _h = page()
check('... dragging its amounts to 0 does not fold it under the mouse', by_prop(its, 'dirt_top', 'mini'))

sw = by_prop(its, 'base_color', 'swatch')[0]
ui_bars.run(C, sw)
check('A click on a colour swatch: the colour popup edits that colour', ui_bars.EDIT[0] == st
      and ui_bars.EDIT[1] == 'base_color', ui_bars.EDIT)

# the HDRI section
names = {i.prop for i in its if i.data == S}
check('HDRI: ◀ [HDRI] ▶, Strength / Rotation / Background Blur bars, Show Background switch, Set / Off',
      {'mch_mech_hdri', 'mch_mech_hdri_strength', 'mch_mech_hdri_rot', 'mch_mech_hdri_blur',
       'mch_mech_hdri_show'} <= names and by_prop(its, 'mch_mech_hdri_show', 'switch')
      and {'Set HDRI', 'Off', 'Choose Folder…'} <= {i.label for i in its if i.kind == 'tbtn'}, sorted(names))
check('... no folder set: the note says Blender\'s own HDRIs are listed',
      any(i.kind == 'pnote' and i.label.startswith('Folder: none') for i in its))
tmp = tempfile.mkdtemp(prefix='mch_hdri_')
for f in ('studio_a.hdr', 'yard.exr', 'notes.txt'):
    open(os.path.join(tmp, f), 'wb').close()
real_pref = workspace_ui.pref
workspace_ui.pref = lambda name, default=True: tmp if name == 'hdri_folder' else real_pref(name, default)
try:
    its, _h = page()
    note = next(i.label for i in its if i.kind == 'pnote' and i.label.startswith('Folder:'))
    check('... a folder set: its name and how many HDRIs it has', os.path.basename(tmp) in note and '(2 HDRIs' in note,
          note)
finally:
    workspace_ui.pref = real_pref
check('... Choose Folder… is an operator with a folder browser (mch.mech_hdri_folder)',
      hasattr(bpy.types, 'MCH_OT_mech_hdri_folder') and
      next(i for i in its if i.kind == 'tbtn' and i.label == 'Choose Folder…').action[1] == 'mch.mech_hdri_folder')

# the panel's pages
wm = C.window_manager
check('Side panel: the Tool page by default', sp.page(C) == 'TOOL')
r = bpy.ops.mch.side_page(page='MATERIAL')
check('mch.side_page: the Material page (scroll back to the top, the panel unfolded)',
      r == {'FINISHED'} and sp.page(C) == 'MATERIAL' and wm.mch_side_scroll == 0.0 and not wm.mch_side_min)
its2, h2 = sp.content(C, 'CUT', 0.0, 276.0, 1.0)
check('... the panel\'s content is then the Material page (whatever the tool)',
      any(i.kind == 'shead' and i.label.startswith('SURFACE') for i in its2))
bpy.ops.mch.side_page(page='TOOL')
its3, _h = sp.content(C, 'CUT', 0.0, 276.0, 1.0)
check('... and back to the tool\'s settings', not any(i.kind == 'shead' and i.label.startswith('SURFACE')
                                                     for i in its3))
item = mecha_menu.Item('ptab', 0, 0, 10, 10, 'Material', '', False, True, ('page', 'MATERIAL'))
ui_bars.run(C, item)
check('The Material tab (a click on it) switches the page', sp.page(C) == 'MATERIAL')
bpy.ops.mch.side_page(page='TOOL')
acts = dict(mecha_menu.ACTIONS)['Actions']
check('Mecha Menu: Material in Actions (opens the Material page; its 9th slot - the menu no taller)',
      any(lab == 'Material' and op == 'mch.side_page' and props == {'page': 'MATERIAL'}
          for lab, _g, op, props, *_r in acts) and len(acts) == 9)
check('The Blender sidebar panel stays (the drawn panel hides while the sidebar is open, as for the tools)',
      hasattr(bpy.types, 'MCH_PT_mech_shader'))
summary()
