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
check('No Mech material yet: ◀ [preset] ▶ on the scene\'s preset, Apply Mech Shader (the HDRI on its own page)',
      by_prop(its, 'mch_mech_preset', 'drop') and any(i.kind == 'tbtn' and i.label == 'Apply Mech Shader' for i in its)
      and 'HDRI' not in heads(its) and h > 0, [i.label for i in its if i.kind in {'tbtn', 'shead'}])
tiles0 = [i for i in its if i.kind == 'mtile']
check('... and the presets as sphere icons (user: "메테리얼 창도 아이콘으로 보이게 해 줄래? 구 형태로"): 34 tiles, a click '
      'applies that preset', len(tiles0) == len(ms.PRESETS) and all(t.action[:2] == ('op', 'mch.mech_shader_apply')
                                                                   for t in tiles0), len(tiles0))
check('... every preset has its sphere icon file (mech_icons/mat_<ID>.png)',
      all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in tiles0),
      [t.label for t in tiles0 if not t.icon])
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

tiles = [i for i in its if i.kind == 'mtile']
on = [t.label for t in tiles if t.on]
check('Presets as sphere icons: a grid of 34, the one in use blue (Steel)', len(tiles) == len(ms.PRESETS)
      and on == ['Steel'] and heads(its)['PRESETS'].on, on)
cols = sorted({round(t.x) for t in tiles})
check('... 4 per row, square balls with the name under them', len(cols) == 4 and all(t.h > t.w for t in tiles))
rust = next(t for t in tiles if t.label == 'Rusted Steel')
ui_bars.run(C, rust)
check('... a click on a ball: that preset (Rusted Steel)', st.preset == 'RUSTED' and st.rust > 0.5, st.preset)
st.preset = 'STEEL'
its, _h = page()
before = st.preset
nxt = next(i for i in its if i.kind == 'tbtn' and i.label == '▶' and i.action[1] == 'mch.mech_shader_step'
           and i.action[2].get('prop') == 'preset')
ui_bars.run(C, nxt)
check('◀ [preset] ▶: ▶ steps the material to the next preset', st.preset != before, (before, st.preset))

st.preset = 'CHIPPED'
its, _h = page()
hd = heads(its)
check('Sections: Surface, Maps, Paint, Edge Wear, Scratches, Rust, Dirt, Snow, Glow, Weave, Height & Detail - no HDRI '
      '(its own page)', all(t in hd for t in ('SURFACE', 'MAPS', 'PAINT', 'EDGE WEAR', 'SCRATCHES', 'RUST', 'DIRT',
                                               'SNOW', 'GLOW', 'WEAVE', 'HEIGHT & DETAIL')) and 'HDRI' not in hd,
      sorted(hd))
used = mu.in_use(mat, st)
check('Chipped Paint: the layers in use start open (Paint, Edge Wear), the others folded (Snow, Glow, Weave)',
      {'paint', 'chip'} <= used and hd['PAINT'].on and hd['EDGE WEAR'].on and not hd['SNOW'].on and not hd['GLOW'].on
      and not hd['WEAVE'].on, sorted(used))
check('... a layer\'s amount in its title (EDGE WEAR  35 %)', next(i.label for i in its if i.kind == 'shead'
                                                                 and i.label.startswith('EDGE WEAR')).endswith('35 %'))
check('Paint: coverage, colour swatch, roughness, pattern',
      by_prop(its, 'paint', 'mini') and by_prop(its, 'paint_color', 'swatch') and by_prop(its, 'paint_rough', 'mini')
      and by_prop(its, 'paint_pattern', 'mini'))
check('Edge Wear (user: "엣지 텍스처랑 색깔, 까지는 마스크, 러프니스"): ◀ [wear preset] ▶, Amount; the mask: ◀ [Mask map] ▶, '
      'Follow Edges / Reach / Softness / Breakup / Mask Scale; at the chips: Edge Material, Edge Color swatch, Edge '
      'Metallic / Roughness / Polish, ◀ [Texture] ▶; Primer + colour; Chip Depth',
      by_prop(its, 'wear_preset', 'drop') and by_prop(its, 'edge_wear', 'mini') and by_prop(its, 'chip_map', 'drop')
      and all(by_prop(its, p, 'mini') for p in ('chip_follow', 'chip_reach', 'chip_soft', 'chip_breakup', 'chip_scale',
                                                'edge_mat', 'edge_metal', 'edge_rough', 'edge_polish', 'primer',
                                                'h_chip'))
      and by_prop(its, 'edge_color', 'swatch') and by_prop(its, 'edge_map', 'drop')
      and by_prop(its, 'primer_color', 'swatch'))
check('... small headings: Mask / At the chips / Primer', sum(1 for i in its if i.kind == 'pnote' and (
      i.label.startswith('Mask') or i.label.startswith('At the chips') or i.label.startswith('Primer'))) == 3)

# edge wear presets
check('Edge Wear presets: 24 (+ "As the Material Preset")', len(ms.WEAR_PRESETS) == 24
      and len(st.bl_rna.properties['wear_preset'].enum_items) == 25)
others = {k: (tuple(getattr(st, k)) if k.endswith('color') else getattr(st, k)) for k in ms.SLIDERS + tuple(
    ms.MAP_PROPS.values()) if k not in ms.WEAR_KEYS}
wp = next(i for i in its if i.kind == 'tbtn' and i.label == '▶' and i.action[2].get('prop') == 'wear_preset')
ui_bars.run(C, wp)
after = {k: (tuple(getattr(st, k)) if k.endswith('color') else getattr(st, k)) for k in others}
check('▶ on the wear preset: the next one (No Wear) - only the edge wear changes, the rest of the material stays',
      st.wear_preset == 'NONE' and st.edge_wear == 0.0 and after == others and st.preset == 'CHIPPED',
      (st.wear_preset, [k for k in others if others[k] != after[k]]))
its, _h = page()
wh = heads(its)['EDGE WEAR PRESETS']
check('Edge Wear Presets: their own section (folded at first)', not wh.on and not [
    i for i in its if i.kind == 'mtile' and i.prop == 'wear_preset'])
ui_bars.run(C, wh)
its, _h = page()
wt = [i for i in its if i.kind == 'mtile' and i.prop == 'wear_preset']
check('... opened: 25 sphere icons (each wear preset on Chipped Paint + "As Material"), icon files there',
      len(wt) == 25 and all(t.icon.startswith('file:') and os.path.isfile(t.icon[5:]) for t in wt), len(wt))
ui_bars.run(C, next(t for t in wt if t.label == 'Brass Underneath'))
check('... a click: that wear preset', st.wear_preset == 'BRASS' and st.edge_mat == 1.0)
nodes = mat.node_tree.nodes
col = tuple(nodes['mch:edge_color'].outputs[0].default_value)[:3]
check('Brass Underneath: Edge Material 1, the edge colour brass (written into the material), its texture Mottled',
      st.edge_mat == 1.0 and abs(col[0] - st.edge_color[0]) < 1e-6 and col[0] > col[2] * 1.5
      and nodes['mch:img:edge_tex'].image is not None and 'MOTTLED' in nodes['mch:img:edge_tex'].image.name.upper(),
      (st.edge_mat, col, nodes['mch:img:edge_tex'].image))
st.wear_preset = 'PRESET'
check('"As the Material Preset": the Chipped Paint edge wear back (35 %, Flakes, primer 0.5)',
      abs(st.edge_wear - 0.35) < 1e-6 and st.chip_map == 'FLAKES' and abs(st.primer - 0.5) < 1e-6
      and st.edge_mat == 0.0)
st.wear_preset = 'HEAVY'
st.preset = 'STEEL'
check('A material preset puts its own edge wear back (the wear preset reads "As the Material Preset")',
      st.wear_preset == 'PRESET' and st.edge_wear == 0.0 and st.chip_reach == 0.0)
check('Defaults = the old fixed values (every material looks as before): Follow Edges 0.65, Softness 0.04, Reach / '
      'Breakup / Edge Material 0, Polish 1, Mask Scale 1',
      ms.BASE['chip_follow'] == 0.65 and ms.BASE['chip_soft'] == 0.04 and ms.BASE['chip_reach'] == 0.0
      and ms.BASE['chip_breakup'] == 0.0 and ms.BASE['edge_mat'] == 0.0 and ms.BASE['edge_polish'] == 1.0
      and ms.BASE['chip_scale'] == 1.0)
st.chip_scale = 2.0
sc_node = nodes['mch:scale:chip']
check('Mask Scale: the mask map\'s own size (its scale node x Mask Scale)', any(
    lk.from_node.name == 'mch:chip_scale' for lk in mat.node_tree.links if lk.to_node == sc_node))
st.preset = 'CHIPPED'
its, _h = page()
hd = heads(its)
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

# the HDRI page (user: "재질이랑 hdri는 분리해야지")
its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
names = {i.prop for i in its if i.data == S}
check('HDRI page: ◀ [HDRI] ▶, Set / Off, My HDRIs (folder), Light (Strength / Rotation), Background (Blur, Show)',
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
    its, _h = mu.hdri_content(C, 0.0, 276.0, 1.0)
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
bpy.ops.mch.side_page(page='HDRI')
its4, _h = sp.content(C, 'CUT', 0.0, 276.0, 1.0)
check('... the HDRI page apart from the material (no material rows on it, no HDRI rows on the Material page)',
      sp.page(C) == 'HDRI' and by_prop(its4, 'mch_mech_hdri', 'drop') and not any(i.data == st for i in its4)
      and not any(getattr(i, 'prop', '').startswith('mch_mech_hdri') for i in its2))
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
