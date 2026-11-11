"""0.24.95 The Mech Shader and the HDRI in Mecha Lab's own side panel (the Material page), in the Mecha look.

User: "우리 예쁘게 만든 우리의 유아이가 이미 메카 랩에 있는데 왜 다시 블렌더 기본 패널로 바꿨어" - the material's
settings were only in a Blender sidebar panel (Mecha Lab tab).  They are drawn here like every tool's settings:

* the side panel has two tabs at its top, the tool's settings | Material (the Mecha Menu's Material button opens it)
* preset / maps / HDRI: ◀ [list v] ▶ - the arrows step, the list opens the choices
* numbers -> bars (drag, click = type, Ctrl+click = default), colours -> a swatch (click = colour picker)
* Surface (base colour, metallic, roughness, glass, IOR, alpha, clear coat, brushed), the base / roughness maps,
  each layer (paint, edge wear, scratches, rust, dirt, snow, glow, weave) in its own section - a layer in use starts
  open, its amount in the section's title - then Height & Detail
* Edge Wear (user: "엣지 까지는 옵션은 좀 더 편하게 많이 - 엣지 텍스처랑 색깔, 까지는 마스크, 러프니스, 프리셋으로도
  많이"): its own presets (◀ [preset] ▶, 24), the mask (map, follow edges, reach, softness, breakup, scale), what
  shows at the chips (edge material: colour, texture, metallic, roughness, polish), the primer, the depth
* the HDRI is a page of its own (user: "재질이랑 hdri는 분리해야지"): the tabs Tool | Material | HDRI
* 0.24.95 (user: "이건 데칼 탭으로 가자! 메테리얼도 크리쳐랑 메카닉이랑 좀 분리해 줘") the tabs Tool | Mech | Creature |
  Decals | HDRI: the Mech page only the Mech Shader, the Creature page the Creature Shader (skins, parts, the eye), the
  Decals page the decal library (Sci-Fi full-colour + two-tone + text) and the selected decal's settings; a page shown
  with the other kind selected says so and has a button to its page
* the presets as sphere icons (user: "메테리얼 창도 아이콘으로 보이게 해 줄래? 구 형태로"): a grid of shader balls
  (``mech_icons/mat_<ID>.png``, ``wear_<ID>.png`` - made by ``tools_dev/make_mech_preset_icons.py``), click = that
  preset; the one in use is blue

The Blender sidebar panel stays (the drawn panel hides while the sidebar is open, as for the tools)."""
from __future__ import annotations

import os

import bpy

from . import side_panel as sp

PAGE = 'MATERIAL'
# (slot, section title, what makes it "in use", rows before the amount, the amount, rows after, its height)
LAYERS = (
    ('scratch', 'Scratches', ('scratches',), ('scratch_color', 'scratch_tint'), 'scratches', (), 'h_scratch'),
    ('rust', 'Rust', ('rust', 'rust_scratch'), ('rust_color',), 'rust', ('rust_scratch',), 'h_rust'),
    ('dirt', 'Dirt', ('dirt', 'dirt_top', 'dirt_low', 'dust', 'streaks'), ('dirt_color',), 'dirt',
     ('dirt_top', 'dirt_low', 'dust', 'dust_color', 'streaks'), 'h_dirt'),
    ('snow', 'Snow', ('snow',), (), 'snow', ('snow_soft',), 'h_snow'),
    ('emit', 'Glow', ('emission',), ('emit_color',), 'emission', (), None),
    ('weave', 'Weave', ('cloth',), (), 'cloth', (), 'h_weave'),
)
SURFACE = ('base_color', 'metallic', 'roughness', 'glass', 'ior', 'alpha', 'coat', 'aniso')
DETAIL = ('bump', 'ao', 'map_scale', 'edge_width')
PAINT = ('paint', 'paint_color', 'paint_rough', 'paint_pattern')
MASK = ('chip_follow', 'chip_reach', 'chip_soft', 'chip_breakup', 'chip_scale')
BARE = ('edge_mat', 'edge_color', 'edge_metal', 'edge_rough', 'edge_polish')
_IN_USE = {}             # (material, preset) -> the layers in use when it was first shown: they start open
ICON_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'mech_icons')
GRID_COLS = 4


_ICONS = {}


def icon(kind, ident):
    """'file:<png>' of a preset's sphere icon ('mat' / 'wear'), '' when it is missing (a plain ball is drawn).
    Looked up once (the panel is rebuilt many times a second while the mouse moves)."""
    key = (kind, ident)
    if key not in _ICONS:
        p = os.path.join(ICON_DIR, f'{kind}_{ident}.png')
        _ICONS[key] = 'file:' + p if os.path.isfile(p) else ''
    return _ICONS[key]


def grid(b, x, w, tiles, cols=GRID_COLS):
    """Sphere tiles in rows of ``cols``: tiles = [(label, icon, on, action, data, prop)]."""
    k = b.k
    gap = 5 * k
    tw = (w - (cols - 1) * gap) / cols
    th = tw + 15 * k
    for i, (label, ic, on, action, data, prop) in enumerate(tiles):
        c = i % cols
        if c == 0:
            b.y -= th + (gap if i else 0)
        b.out.append(b.Item('mtile', x + c * (tw + gap), b.y, tw, th, label, ic, on, True, action, data, prop))
    b.y -= sp.GAP * k


def hgrid(b, x, w, tiles, cols=2):
    """0.24.95 HDRI previews (2 : 1 panoramas) in rows of ``cols``: tiles = [(label, icon, on, action)]."""
    k = b.k
    gap = 5 * k
    tw = (w - (cols - 1) * gap) / cols
    th = (tw - 6 * k) / 2 + 6 * k + 15 * k
    for i, (label, ic, on, action) in enumerate(tiles):
        c = i % cols
        if c == 0:
            b.y -= th + (gap if i else 0)
        b.out.append(b.Item('htile', x + c * (tw + gap), b.y, tw, th, label, ic, on, True, action))
    b.y -= sp.GAP * k


def _cell(kind, label, action, data=None, prop=None, on=False, active=True):
    return (kind, label, on, action, data, prop, active)


def number(data, prop, label=None):
    return _cell('mini', label or '', ('number',), data, prop)


def swatch(data, prop, label=None):
    rna = data.bl_rna.properties[prop]
    return _cell('swatch', label or rna.name, ('color',), data, prop)


def button(text, idname, **props):
    return _cell('tbtn', text, ('op', idname, props))


def prop_cell(data, prop, label=None):
    """The cell for property ``prop``: a swatch for a colour, a switch for on / off, a bar for a number."""
    rna = data.bl_rna.properties[prop]
    if rna.type == 'FLOAT' and getattr(rna, 'is_array', False):
        return swatch(data, prop, label)
    if rna.type == 'BOOLEAN':
        return _cell('switch', label or rna.name, ('bool',), data, prop, on=bool(getattr(data, prop)))
    if rna.type == 'ENUM':
        return _cell('drop', label if label is not None else rna.name, ('menu_enum',), data, prop)
    return number(data, prop, label)


def stepper(b, x, w, prev, choice, nxt):
    """◀ [the list v] ▶ on one row (the arrows narrow)."""
    k = b.k
    h, gap, bw = sp.ROW * k, 4 * k, 30 * k
    b.y -= h
    b.out.append(b._item(prev, x, b.y, bw, h))
    b.out.append(b._item(choice, x + bw + gap, b.y, w - 2 * (bw + gap), h))
    b.out.append(b._item(nxt, x + w - bw, b.y, bw, h))
    b.y -= sp.GAP * k


def row(b, x, w, cells):
    b.place_row([c for c in cells if c is not None], x, w)


def section(b, key, title, x, w, fill, start_folded=False, summary=''):
    """A foldable section (its title clicked folds it), ``fill(x, w)`` places its rows."""
    k = b.k
    is_folded = sp.folded(PAGE, key, start_folded)
    top = b.y
    b.gap(0.5)
    bg = b.Item('sbg', x, 0, w, 0)
    b.out.append(bg)
    b.y -= sp.SECTION * k
    label = title.upper() + (f'   {summary}' if summary else '')
    b.out.append(b.Item('shead', x, b.y, w, sp.SECTION * k, label, '', not is_folded, True,
                        ('fold', f'{PAGE}:{key}', start_folded)))
    if not is_folded:
        b.gap(0.5)
        fill(x + 8 * k, w - 16 * k)
    b.gap(0.3)
    bg.y, bg.h = b.y, top - b.y - sp.GAP * k * 0.5
    b.gap(0.7)


def _pct(v):
    return f'{round(v * 100)} %'


def _map_stepper(b, st, slot, x, w, label='Map'):
    from . import mech_shader as ms
    p = ms.MAP_PROPS[slot]
    stepper(b, x, w, button('◀', 'mch.mech_shader_step', prop=p, step=-1),
            _cell('drop', label, ('menu_enum',), st, p),
            button('▶', 'mch.mech_shader_step', prop=p, step=1))


def _preset_stepper(b, data, prop, x, w):
    stepper(b, x, w, button('◀', 'mch.mech_shader_step', prop='preset', step=-1),
            _cell('drop', '', ('menu_enum',), data, prop),
            button('▶', 'mch.mech_shader_step', prop='preset', step=1))


def in_use(mat, st):
    key = (mat.name, st.preset)
    if key not in _IN_USE:
        if len(_IN_USE) > 200:
            _IN_USE.clear()
        used = {slot for slot, _t, which, *_r in LAYERS if any(getattr(st, p) > 0.0 for p in which)}
        if st.paint > 0.0:
            used.add('paint')
        if st.edge_wear > 0.0 or st.primer > 0.0:
            used.add('chip')
        _IN_USE[key] = frozenset(used)
    return _IN_USE[key]


def layer_summary(st, used):
    v = max(getattr(st, p) for p in used)
    return '' if v <= 0.0 else (f'{v:.1f}' if v > 1.0 else _pct(v))


# --- the page ------------------------------------------------------------------------------------------------------

def content(context, x, width, k):
    """(items, content height) - the Material page's rows, y measured down from 0 (as ``side_panel.content``)."""
    from . import mech_shader as ms
    from . import creature_shader as cs
    b = sp.Builder(PAGE, x, width, k)
    sc = context.scene
    ob = getattr(context, 'active_object', None)
    from . import decals as dc
    if dc.is_decal(ob):                              # (0.24.95 a decal: its settings are on the Decals page)
        elsewhere(b, x, width, f'"{ob.name}" is a decal - its settings are on the Decals page', 'DECALS')
        return b.out, -b.y
    mat = ms.active_mech(context)
    if mat is None:
        other = cs.active_eye(context) or cs.active_creature(context)
        if other is not None:                        # (0.24.95 a Creature material: its own page; Apply = Mech)
            elsewhere(b, x, width, f'"{other.name}" is a Creature material - its settings are on the Creature page',
                      'CREATURE')
        _preset_stepper(b, sc, 'mch_mech_preset', x, width)
        row(b, x, width, [button('Apply Mech Shader', 'mch.mech_shader_apply', preset='')])

        def presets0(sx, sw):
            grid(b, sx, sw, [(n, icon('mat', kk), sc.mch_mech_preset == kk, ('op', 'mch.mech_shader_apply',
                                                                          {'preset': kk}), None, None)
                             for kk, n, _s in ms.PRESETS])
        section(b, 'presets', 'Presets', x, width, presets0)
        my_materials_section(b, x, width)
        other = getattr(ob, 'active_material', None) if ob is not None else None
        if ob is None or ob.type != 'MESH':
            b.note(('note', 'Select meshes, then Apply', False, None, None, None, True), x, width)
        elif other is not None and not (cs.is_creature(other) or cs.is_eye(other)):
            over_mine(b, x, width, other, 'MECH')
        return b.out, -b.y
    st = getattr(mat, ms.KEY)
    _preset_stepper(b, st, 'preset', x, width)
    n_parts = len(ms.users_of(mat))
    b.note(('note', mat.name + (f'   - shared by {n_parts} parts' if n_parts > 1 else '   - this part only'), False,
            None, None, None, True), x, width)
    # 0.24.95 (user: "메테리얼 링크 끊는 버튼도 만들어 줄래?") Unlink: the selected parts get their own copy
    row(b, x, width, [_cell('tbtn', 'Unlink', ('op', 'mch.mech_shader_unlink', {}), active=n_parts > 1),
                      button('New Copy', 'mch.mech_shader_apply', preset=st.preset),
                      button('Edges', 'mch.mech_shader_edges')])
    over = over_note(b, x, width, mat, 'Your material is the coat: Edge Wear / Scratches cut through it to the '
                                       'Surface (the metal under it); rust, dirt, dust, snow on top')
    names = {kk: n for kk, n, _s in ms.PRESETS}

    def presets(sx, sw):
        grid(b, sx, sw, [(n, icon('mat', kk), st.preset == kk, ('enum', kk), st, 'preset') for kk, n, _s in ms.PRESETS])
    section(b, 'presets', 'Presets', x, width, presets, summary=names.get(st.preset, ''))
    my_materials_section(b, x, width)
    my_presets_section(b, x, width, 'mech')
    zones_section(b, x, width, context, mat)

    def surface(sx, sw):
        for p in SURFACE:
            if p == 'ior' and st.glass <= 0.0:
                continue
            row(b, sx, sw, [prop_cell(st, p)])
            if p == 'base_color':               # (0.24.95 Hue / Saturation / Value of the base colour + its map)
                row(b, sx, sw, [number(st, 'base_hue', 'Hue'), number(st, 'base_sat', 'Sat'),
                                number(st, 'base_val', 'Val')])
    section(b, 'surface', 'Surface - under your material' if over else 'Surface', x, width, surface)

    def bevel(sx, sw):                           # (0.24.95 user: "베벨 - 조금 · 중간 · 많이 프리셋, 세부 조정 슬라이더")
        b.note(('note', 'Edges rounded in the shading (the mesh stays sharp) - Cycles; Material Preview shows them '
                'sharp', False, None, None, None, True), sx, sw)
        cur = ms.bevel_preset(st)
        row(b, sx, sw, [_cell('tbtn', n, ('op', 'mch.mech_bevel', {'preset': kk}), on=cur == kk)
                        for kk, n, _r, _s in ms.BEVEL_PRESETS])
        row(b, sx, sw, [number(st, 'bevel_radius', 'Radius')])
        row(b, sx, sw, [number(st, 'bevel_samples', 'Samples')])
    bev_names = {kk: n for kk, n, _r, _s in ms.BEVEL_PRESETS}
    section(b, 'bevel', 'Bevel', x, width, bevel, start_folded=st.bevel_radius <= 0.0,
            summary=('' if st.bevel_radius <= 0.0 else
                     f'{bev_names.get(ms.bevel_preset(st), "Custom")} {st.bevel_radius * 1000:.0f} mm'))

    def maps(sx, sw):
        _map_stepper(b, st, 'base', sx, sw, 'Base')
        row(b, sx, sw, [number(st, 'h_base', 'Height')])
        row(b, sx, sw, [number(st, 'variation')])
        _map_stepper(b, st, 'rough', sx, sw, 'Roughness')
        row(b, sx, sw, [number(st, 'rough_amount', 'Amount')])
    section(b, 'maps', 'Maps', x, width, maps, start_folded=True)

    used = in_use(mat, st)

    def paint(sx, sw):
        for p in PAINT:
            row(b, sx, sw, [prop_cell(st, p)])
    if not over:                                 # (over the user's material: their material is the paint)
        section(b, 'paint', 'Paint', x, width, paint, start_folded='paint' not in used,
                summary=layer_summary(st, ('paint',)))

    def wear(sx, sw):
        stepper(b, sx, sw, button('◀', 'mch.mech_shader_step', prop='wear_preset', step=-1),
                _cell('drop', 'Preset', ('menu_enum',), st, 'wear_preset'),
                button('▶', 'mch.mech_shader_step', prop='wear_preset', step=1))
        row(b, sx, sw, [prop_cell(st, 'edge_wear', 'Amount')])
        sub(b, 'Mask - where it chips', sx, sw)
        _map_stepper(b, st, 'chip', sx, sw, 'Mask')
        for p in MASK:
            row(b, sx, sw, [prop_cell(st, p)])
        sub(b, 'At the chips - the edge', sx, sw)
        for p in BARE:
            row(b, sx, sw, [prop_cell(st, p)])
        stepper(b, sx, sw, button('◀', 'mch.mech_shader_step', prop='edge_map', step=-1),
                _cell('drop', 'Texture', ('menu_enum',), st, 'edge_map'),
                button('▶', 'mch.mech_shader_step', prop='edge_map', step=1))
        sub(b, 'Primer - between paint and metal', sx, sw)
        row(b, sx, sw, [prop_cell(st, 'primer')])
        row(b, sx, sw, [prop_cell(st, 'primer_color')])
        row(b, sx, sw, [number(st, 'h_chip', 'Chip Depth')])
    section(b, 'chip', 'Edge Wear', x, width, wear, start_folded='chip' not in used,
            summary=layer_summary(st, ('edge_wear',)))
    wnames = {i.identifier: i.name for i in st.bl_rna.properties['wear_preset'].enum_items}

    def wear_presets(sx, sw):
        grid(b, sx, sw, [(wnames[kk] if kk != 'PRESET' else 'As Material', icon('wear', kk), st.wear_preset == kk,
                          ('enum', kk), st, 'wear_preset') for kk in wnames])
    section(b, 'wear_presets', 'Edge Wear Presets', x, width, wear_presets, start_folded=True,
            summary=wnames.get(st.wear_preset, '') if st.wear_preset != 'PRESET' else '')

    for slot, title, which, before, amount, after, height in LAYERS:
        def fill(sx, sw, before=before, amount=amount, after=after, height=height, slot=slot):
            for p in before:
                row(b, sx, sw, [prop_cell(st, p)])
            row(b, sx, sw, [prop_cell(st, amount)])
            for p in after:
                row(b, sx, sw, [prop_cell(st, p)])
            _map_stepper(b, st, slot, sx, sw)
            if height:
                row(b, sx, sw, [number(st, height, 'Height')])
        section(b, slot, title, x, width, fill, start_folded=slot not in used, summary=layer_summary(st, which))

    bake_section(b, x, width, context)

    def overall(sx, sw):                         # (0.24.95 user: "가장 밑에 전체 헤이트랑 전체 스케일 조정하는 칸에도
        for p in DETAIL:                         #  언링크 버튼")
            row(b, sx, sw, [prop_cell(st, p)])
        project_rows(b, sx, sw, sc)
        unlink_row(b, sx, sw, n_parts, button('New Copy', 'mch.mech_shader_apply', preset=st.preset))
    section(b, 'overall', 'Overall - Height & Scale', x, width, overall)
    return b.out, -b.y


def project_rows(b, x, w, sc):
    """0.24.95 (user: "한 프로젝트 할 때는 전부 비슷한 스케일일 거 아니야 - 전체적으로 조정"): the whole file's map size
    (every Mech / Creature material) and Follow Object Scale."""
    sub(b, 'The whole project - every Mech / Creature material', x, w)
    row(b, x, w, [number(sc, 'mch_map_scale', 'Project Scale')])
    row(b, x, w, [prop_cell(sc, 'mch_obj_scale', 'Follow Object Scale')])


def unlink_row(b, x, w, n_parts, *more):
    """Unlink (the selected parts their own copy of the material) + more buttons on one row."""
    row(b, x, w, [_cell('tbtn', 'Unlink', ('op', 'mch.mech_shader_unlink', {}), active=n_parts > 1)] + list(more))


def over_mine(b, x, width, other, kind):
    """0.24.95 The active part has a material of the user's own: ours can go over it (user: "내가 이미 만들어 놓은
    메테리얼에 우리가 만든 메테리얼 연결해서 그 위에 우리가 만든 재질 얹어서")."""
    what = 'chips, scratches, rust, dirt, snow' if kind == 'MECH' else 'mud, dust, blood, slime, snow'
    b.note(('note', f'"{other.name}" is your own material - lay ours over it ({what} on top; yours stays as it is)',
            False, None, None, None, True), x, width)
    row(b, x, width, [button('Layer Over My Material', 'mch.material_over', kind=kind, preset='')])


def over_note(b, x, width, mat, text):
    """Over the user's material: a line saying so + Back to Mine.  True when it is."""
    from . import material_overlay as mo
    if not mo.is_over(mat):
        return False
    src = mo.source_of(mat)
    b.note(('note', f'Over "{mat.get(mo.SRC, "?")}"' + ('' if src else ' (gone)') + f' - {text}', True, None, None,
            None, True), x, width)
    row(b, x, width, [_cell('tbtn', 'Back to Mine', ('op', 'mch.material_over_back', {}), active=src is not None)])
    return True


def bake_section(b, x, width, context):
    """0.24.95 Bake to Polypaint (user: "폴리페인트로 구워 줘"): the material's colour into one colour per point."""
    from . import bake_material as bk
    ob = getattr(context, 'active_object', None)
    me = ob.data if ob is not None and ob.type == 'MESH' else None
    lay = me.color_attributes.get(bk.LAYER) if me is not None else None

    def fill(sx, sw):
        b.note(('note', 'The colour (wear, zones, markings, conditions) into polypaint: one colour per point',
                False, None, None, None, True), sx, sw)
        row(b, sx, sw, [button('Bake to Polypaint', 'mch.bake_polypaint'),
                        _cell('tbtn', 'Show Polypaint', ('op', 'mch.show_polypaint', {}), on=bk.showing(context))])
        if me is not None:
            b.note(('note', f'{len(me.vertices):,} points - denser = finer' + (f'   (baked: "{bk.LAYER}")' if lay
                                                                               else ''), False, None, None, None,
                    True), sx, sw)
    section(b, 'bake_pp', 'Bake', x, width, fill, start_folded=lay is None, summary='polypaint' if lay else '')


def _zone_button(text, kind, context):
    """0.24.95 (user: "라쏘도 컷이나 이런 거처럼 위에 막대에 옵션 다 넣어 줘 - 스케치랑 라인 이런 거 다") Paint Zone /
    Split Zone: the Lasso Zone tool (the shared lasso of the top bar), lit while it draws that kind."""
    from . import zones as zn
    return _cell('tbtn', text, ('op', 'mch.zone_tool', {'kind': kind}), on=zn.tool_on(context, kind))


def zones_section(b, x, width, context, mat):
    """0.24.95 Lasso Zones (user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게"): Paint Zone (its own paint,
    projected - the mesh as it is) / Split Zone (edges cut along it, a material of its own); the zones' sliders; the
    part's materials (slots) to switch between."""
    from . import mech_shader as ms
    from . import zones as zn
    ob = getattr(context, 'active_object', None)
    zs = zn.zones_of(mat)
    slots = [sl for sl in getattr(ob, 'material_slots', ())] if ob is not None else []
    creature = not ms.is_mech(mat)

    def fill(sx, sw):
        b.note(('note', 'Draw on the part with the top bar\'s lasso (shapes, Corners, Line, Sketch, Slow Line, '
                'Surface - like Cut); Esc: back to Select', False, None, None, None, True), sx, sw)
        if creature:                                # (0.24.95 a creature's markings: Paint Zones)
            row(b, sx, sw, [_zone_button('Paint Zone', 'PAINT', context)])
            sub(b, 'Markings: its colour / texture over the skin, the edge airbrushed or textured', sx, sw)
            for i, z in enumerate(zs or ()):
                sub(b, f'{z.name} - marking', sx, sw)
                for p in ('color', 'tex'):
                    row(b, sx, sw, [prop_cell(z, p)])
                if z.tex != 'FLAT':
                    row(b, sx, sw, [prop_cell(z, 'tex_scale')])
                for p in ('roughness', 'opacity', 'edge', 'edge_width'):
                    row(b, sx, sw, [prop_cell(z, p)])
                if z.edge == 'TEXTURE':
                    row(b, sx, sw, [prop_cell(z, 'edge_scale')])
                row(b, sx, sw, [prop_cell(z, 'invert', 'Invert - outside the lasso')])
                row(b, sx, sw, [prop_cell(z, 'through', 'Through - the back faces too'),
                                _cell('tbtn', 'Delete', ('op', 'mch.zone_remove', {'index': i}))])
            return
        row(b, sx, sw, [_zone_button('Paint Zone', 'PAINT', context), _zone_button('Split Zone', 'SPLIT', context)])
        sub(b, 'Paint: its own paint, the mesh as it is.  Split: new edges, its own material', sx, sw)
        for i, z in enumerate(zs or ()):
            if z.kind == 'LINE':                    # (a Split Zone's boundary line - in both its materials)
                sub(b, f'{z.name} - the boundary line', sx, sw)
                for p in ('line_height', 'line_width'):
                    row(b, sx, sw, [prop_cell(z, p)])
                zmat = mat if getattr(mat, 'mch_zone_parent', None) is not None else zn.split_partner(ob, mat, z)
                cells = [_cell('tbtn', 'Remove Line', ('op', 'mch.zone_remove', {'index': i}))]
                if zmat is not None:                # (0.24.95 user: "스플릿 페인트 반전은 못 해?")
                    cells.insert(0, _cell('tbtn', 'Invert (inside / outside)',
                                          ('op', 'mch.zone_split_invert', {'material': zmat.name}),
                                          on=bool(zmat.get('mch_zone_inverted', False))))
                row(b, sx, sw, cells)
                continue
            sub(b, f'{z.name} - paint', sx, sw)
            for p in ('color', 'tex'):              # (0.24.95 a base colour texture of its own, tinted by Color)
                row(b, sx, sw, [prop_cell(z, p)])
            if z.tex != 'FLAT':
                row(b, sx, sw, [prop_cell(z, 'tex_scale')])
            row(b, sx, sw, [prop_cell(z, 'base_through')])  # (0.24.95 the material's own texture under it: 0 covered)
            for p in ('roughness', 'metallic', 'cover', 'opacity', 'line_height', 'line_width', 'edge'):
                row(b, sx, sw, [prop_cell(z, p)])
            if z.edge != 'HARD':
                row(b, sx, sw, [prop_cell(z, 'edge_width')])
            if z.edge == 'TEXTURE':
                row(b, sx, sw, [prop_cell(z, 'edge_scale')])
            row(b, sx, sw, [prop_cell(z, 'own_wear', 'Own Wear - chips, scratches, dirt, rust')])
            if z.own_wear:
                for p in ms.ZONE_WEAR:
                    row(b, sx, sw, [prop_cell(z, p)])
            row(b, sx, sw, [prop_cell(z, 'invert', 'Invert - paint outside the lasso')])
            row(b, sx, sw, [prop_cell(z, 'through', 'Through - the back faces too'),
                            _cell('tbtn', 'Delete', ('op', 'mch.zone_remove', {'index': i}))])
        parent = getattr(mat, 'mch_zone_parent', None)
        if parent is not None:                      # (a Split Zone's own material)
            sub(b, f'A Split Zone of "{parent.name}"', sx, sw)
            row(b, sx, sw, [prop_cell(mat, 'mch_zone_follow', 'Same Wear as the Part')])
            if mat.mch_zone_follow:
                b.note(('note', 'Chips, scratches, dirt, rust: the part\'s (off: set them here)', False, None, None,
                        None, True), sx, sw)
        if len(slots) > 1:
            sub(b, 'This part\'s materials (Split Zones) - click one to change it', sx, sw)
            for i, sl in enumerate(slots):
                name = sl.material.name if sl.material is not None else '(empty)'
                row(b, sx, sw, [_cell('tbtn', name, ('op', 'mch.zone_slot', {'index': i}),
                                      on=i == ob.active_material_index)])
    n = len(zs or ())
    section(b, 'zones', 'Zones', x, width, fill, start_folded=not n and len(slots) < 2,
            summary=(f'{n} zones' if n else '') + (f'  {len(slots)} materials' if len(slots) > 1 else ''))


PAGE_NAMES = {'MATERIAL': 'Mech', 'CREATURE': 'Creature', 'DECALS': 'Decals', 'HDRI': 'HDRI', 'SHAPES': 'Shapes'}


def elsewhere(b, x, width, text, page):
    """0.24.95 What is selected belongs on another page: a line saying so + a button to that page."""
    b.note(('note', text, True, None, None, None, True), x, width)
    row(b, x, width, [button(f'Open the {PAGE_NAMES[page]} Page', 'mch.side_page', page=page)])
    b.gap(0.6)


def creature_page(context, x, width, k):
    """0.24.95 (items, content height) - the Creature page (user: "메테리얼도 크리쳐랑 메카닉이랑 좀 분리해 줘"): the
    Creature Shader material's own settings, the eye's, or (none of them selected) the skin types and parts to put on
    the selected meshes."""
    from . import creature_shader as cs
    from . import decals as dc
    from . import mech_shader as ms
    b = sp.Builder(PAGE, x, width, k)
    sc = context.scene
    ob = getattr(context, 'active_object', None)
    if dc.is_decal(ob):
        elsewhere(b, x, width, f'"{ob.name}" is a decal - its settings are on the Decals page', 'DECALS')
        return b.out, -b.y
    emat = cs.active_eye(context)
    if emat is not None:                             # (an eye's own page)
        eye_content(b, x, width, emat)
        return b.out, -b.y
    cmat = cs.active_creature(context)
    if cmat is not None:
        creature_content(b, x, width, cmat)
        return b.out, -b.y
    mech = ms.active_mech(context)
    if mech is not None:
        elsewhere(b, x, width, f'"{mech.name}" is a Mech material - its settings are on the Mech page', 'MATERIAL')
    from . import material_overlay as mo
    own = mo.user_material(context)
    if own is not None:
        over_mine(b, x, width, own, 'CREATURE')
    creature_apply_section(b, x, width, sc, start_folded=False)
    my_materials_section(b, x, width)
    if ob is None or ob.type != 'MESH':
        b.note(('note', 'Select meshes, then click a skin type or a part', False, None, None, None, True), x, width)
    return b.out, -b.y


def decal_page(context, x, width, k):
    """0.24.95 (items, content height) - the Decals page (user: "이건 데칼 탭으로 가자!"): the selected decal's settings
    (look, damage, size), then the library - Sci-Fi Signs (full colour), Two-Tone, Text."""
    from . import decals as dc
    b = sp.Builder(PAGE, x, width, k)
    ob = getattr(context, 'active_object', None)
    if dc.is_decal(ob):
        decal_content(b, x, width, ob)
        decal_library(b, x, width, start_folded=True)
    else:
        decal_library(b, x, width, start_folded=False)
    return b.out, -b.y


# --- the Creature Shader (0.24.95 user: "크리쳐 전용으로" - polypaint as the colour, layers from the shape) ------------

def creature_apply_section(b, x, width, sc, start_folded):
    """The Creature Shader's skin types as balls: a click puts a new Creature material on the selected meshes; the
    parts (eye, teeth, gums, claw) the same."""
    from . import creature_shader as cs

    def fill(sx, sw):
        b.note(('note', 'Polypaint is the colour; mud, dust, SSS ... come from the shape', False, None, None, None,
                True), sx, sw)
        grid(b, sx, sw, [(n, icon('cskin', kk), sc.mch_creature_skin == kk,
                          ('op', 'mch.creature_apply', {'skin': kk}), None, None)
                         for kk, n, _s in cs.SKINS if kk not in cs.PART_SKINS])
    section(b, 'cr_apply', 'Skin Types', x, width, fill, start_folded=start_folded)

    def parts(sx, sw):
        b.note(('note', 'Eyes, teeth, gums, claws - a material of that part on the selected meshes', False, None,
                None, None, True), sx, sw)
        parts_grid(b, sx, sw)
    section(b, 'cr_apply_parts', 'Parts', x, width, parts, start_folded=start_folded)


def parts_grid(b, sx, sw):
    """0.24.95 Creature parts (user picked "눈 · 이빨 · 잇몸 · 혀 · 발톱"): a click puts that part's material on the
    selected meshes (an eye: its own eye material - the eye a separate object)."""
    from . import creature_shader as cs
    grid(b, sx, sw, [(n, icon('cpart', kk), False, ('op', 'mch.creature_part', {'part': kk}), None, None)
                     for kk, n in cs.PARTS])


def decal_library(b, x, width, start_folded=False):
    """0.24.95 The decal library (user picked "데칼 - 번호, 경고 줄무늬, 로고"; "추가 데칼이야! 이거도 추가해 줘"): a ball per
    decal - click it, then click a part.  Sci-Fi Signs (the user's 30, their own colours), Tech Marks (24 barcodes,
    codes, labels ...), Two-Tone (24 signs, any two colours), Text."""
    from . import decals as dc
    sfx = '_open' if not start_folded else ''            # (opened on the library page, folded under a decal's own)
    b.note(('note', 'Click a decal, then click a part (Esc: cancel)', False, None, None, None, True), x, width)
    row(b, x, width, [button('Text Decal...', 'mch.decal_text')])

    def scifi(sx, sw):
        grid(b, sx, sw, [(lab, icon('decal', kk), False, ('op', 'mch.decal_place', {'decal': kk}), None, None)
                         for kk, (lab, _r) in dc.COLOR_DECALS.items()])
    section(b, 'decals_scifi' + sfx, 'Sci-Fi Signs', x, width, scifi, start_folded=start_folded,
            summary=str(len(dc.COLOR_DECALS)))

    def tech(sx, sw):                              # (0.24.95 user: "바코드 같은 데칼 종류 더 만들어 줘")
        b.note(('note', 'Barcodes, codes, labels, rulers ... two colours of your choice', False, None, None, None,
                True), sx, sw)
        grid(b, sx, sw, [(lab, icon('decal', kk), False, ('op', 'mch.decal_place', {'decal': kk}), None, None)
                         for kk, (lab, *_r) in dc.TECH_MARKS.items()])
    section(b, 'decals_tech' + sfx, 'Tech Marks', x, width, tech, start_folded=start_folded,
            summary=str(len(dc.TECH_MARKS)))
    signs = {kk: v for kk, v in dc.DECALS.items() if kk not in dc.TECH_MARKS}

    def two(sx, sw):
        b.note(('note', 'Two colours of your choice (Color 1 / Color 2)', False, None, None, None, True), sx, sw)
        grid(b, sx, sw, [(lab, icon('decal', kk), False, ('op', 'mch.decal_place', {'decal': kk}), None, None)
                         for kk, (lab, *_r) in signs.items()])
    section(b, 'decals' + sfx, 'Two-Tone', x, width, two, start_folded=start_folded, summary=str(len(signs)))


def decal_content(b, x, width, ob):
    """0.24.95 The Material page of a decal: its colours, its damage (user: "데칼에 데미지 들어간 것도 쉐이더로,
    조절할 수 있게"), size / lift, Mirror / Apply / Delete."""
    from . import decals as dc
    st = getattr(ob, dc.KEY)
    what = f'Text "{st.text}"' if st.kind == dc.TEXT else dc.label_of(st.kind)
    on = ob.parent.name if ob.parent is not None else '-'
    b.note(('note', f'Decal: {what}   on {on}', False, None, None, None, True), x, width)
    row(b, x, width, [button('Mirror X', 'mch.decal_mirror'), button('Apply', 'mch.decal_apply'),
                      button('Delete', 'mch.decal_delete')])

    full = dc.is_full(st.kind)

    def look(sx, sw):
        if full:                                   # (its own colours: a tint, Hue / Saturation / Value)
            row(b, sx, sw, [prop_cell(st, 'tint')])
            row(b, sx, sw, [number(st, 'hue', 'Hue'), number(st, 'sat', 'Sat'), number(st, 'val', 'Val')])
        else:
            row(b, sx, sw, [prop_cell(st, 'color1')])
            row(b, sx, sw, [prop_cell(st, 'color2')])
        for p in ('opacity', 'roughness', 'metallic'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'decal_look', 'Look', x, width, look)

    def damage(sx, sw):
        for p in ('wear', 'peel', 'scratches', 'dirt', 'fade', 'damage_scale', 'seed'):
            row(b, sx, sw, [prop_cell(st, p)])
    used = max(st.wear, st.peel, st.scratches, st.dirt, st.fade)
    section(b, 'decal_damage', 'Damage', x, width, damage, summary=_pct(used) if used > 0 else '')

    def place(sx, sw):
        for p in ('size', 'rotation', 'offset'):
            row(b, sx, sw, [prop_cell(st, p)])
        b.note(('note', 'G / R / S move it over the surface (it wraps on)', False, None, None, None, True), sx, sw)
    section(b, 'decal_place', 'Size & Place', x, width, place)


def eye_content(b, x, width, mat):
    """0.24.95 The Material page of an eye material (iris, pupil, white, cornea)."""
    from . import creature_shader as cs
    from . import mech_shader as ms
    st = getattr(mat, cs.EYE_KEY)
    _cstep(b, st, 'eye_type', x, width)
    n_parts = len(ms.users_of(mat))
    b.note(('note', mat.name + (f'   - shared by {n_parts} parts' if n_parts > 1 else '   - this part only'), False,
            None, None, None, True), x, width)
    row(b, x, width, [_cell('tbtn', 'Unlink', ('op', 'mch.mech_shader_unlink', {}), active=n_parts > 1),
                      button('New Copy', 'mch.creature_part', part='EYE', eye=st.eye_type)])
    names = {kk: n for kk, n, _s in cs.EYES}

    def eyes(sx, sw):
        grid(b, sx, sw, [(n, icon('ceye', kk), st.eye_type == kk, ('enum', kk), st, 'eye_type')
                         for kk, n, _s in cs.EYES])
    section(b, 'eye_presets', 'Eyes', x, width, eyes, summary=names.get(st.eye_type, ''))

    def iris(sx, sw):
        for p in ('front', 'iris_size', 'pupil_size', 'pupil_shape', 'iris_color1', 'iris_color2', 'iris_detail',
                  'limbal', 'limbal_color', 'pupil_color'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'eye_iris', 'Iris & Pupil', x, width, iris)

    def white(sx, sw):
        for p in ('sclera_color', 'veins', 'wet', 'glow', 'glow_color'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'eye_white', 'White, Cornea & Glow', x, width, white)
    b.note(('note', 'The eye is its own object (its box is the eyeball); Looks Along: the axis it looks along',
            False, None, None, None, True), x, width)


def my_materials_section(b, x, width):
    """0.24.95 My Materials (user: "기존에 만들어 놓은 재질도 프리셋으로 등록 가능하게"): any material saved whole (yours
    too), a ball each with its picture - a click puts a copy on the selected parts."""
    from . import my_materials as mm
    ns = mm.names()

    def fill(sx, sw):
        b.note(('note', 'Any material saved whole (yours too) - a ball: on the selected parts', False, None, None,
                None, True), sx, sw)
        row(b, sx, sw, [button('Save Material...', 'mch.my_material_save'),
                        _cell('tbtn', 'Delete...', ('op', 'mch.my_material_delete', {}), active=bool(ns))])
        if ns:
            tiles = []
            for n in ns:
                p = mm.icon_path(n)
                tiles.append((n, 'file:' + p if p else '', False, ('op', 'mch.my_material_apply', {'name': n}), None,
                              None))
            grid(b, sx, sw, tiles)
        else:
            b.note(('note', 'None yet - Save Material keeps any material of this file', False, None, None, None,
                    True), sx, sw)
    section(b, 'my_materials', 'My Materials', x, width, fill, start_folded=not ns,
            summary=str(len(ns)) if ns else '')


def my_presets_section(b, x, width, kind):
    """0.24.95 My Presets: this material's settings saved under a name (for every .blend), a ball each."""
    from . import my_presets as mp
    ns = mp.names(kind)

    def fill(sx, sw):
        row(b, sx, sw, [button('Save Current...', 'mch.my_preset_save'),
                        _cell('tbtn', 'Delete...', ('op', 'mch.my_preset_delete', {}), active=bool(ns))])
        if ns:
            grid(b, sx, sw, [(n, '', False, ('op', 'mch.my_preset_apply', {'name': n}), None, None) for n in ns])
        else:
            b.note(('note', 'None yet - Save Current keeps these settings under a name', False, None, None, None,
                    True), sx, sw)
    section(b, 'my_presets_' + kind, 'My Presets', x, width, fill, start_folded=not ns,
            summary=str(len(ns)) if ns else '')


def _cstep(b, st, prop, x, w, label=''):
    stepper(b, x, w, button('◀', 'mch.creature_step', prop=prop, step=-1),
            _cell('drop', label, ('menu_enum',), st, prop),
            button('▶', 'mch.creature_step', prop=prop, step=1))


def _colour_rows(b, st, layer, flat, sx, sw):
    """A layer's colour: its texture (◀ [Flat / a texture] ▶), its swatch, Hue / Saturation / Value, its size."""
    _cstep(b, st, layer + '_tex', sx, sw, 'Texture')
    if flat:
        row(b, sx, sw, [prop_cell(st, flat)])
    row(b, sx, sw, [number(st, layer + '_hue', 'Hue'), number(st, layer + '_sat', 'Sat'),
                    number(st, layer + '_val', 'Val')])
    row(b, sx, sw, [number(st, layer + '_scale', 'Texture Scale')])     # (0.24.95 user: "이끼 크기가 너무 커")


# (section key, title, the amounts that make it "in use", its rows: a property, ('tex', layer, swatch) or ('sub', text))
CREATURE_LAYERS = (
    ('cr_mud', 'Mud', ('mud', 'mud_top', 'mud_low'),
     ('mud', 'mud_top', 'mud_low', 'low_reach', ('tex', 'mud', 'mud_color'), 'mud_wet', 'mud_cake', 'h_mud')),
    ('cr_dust', 'Dust', ('dust',), ('dust', ('tex', 'dust', 'dust_color'))),
    ('cr_blood', 'Blood', ('blood', 'blood_dry', 'scars'),
     ('blood', ('tex', 'blood', 'blood_color'), ('sub', 'Dried blood - in the crevices'), 'blood_dry',
      ('tex', 'blood_dry', 'blood_dry_color'), ('sub', 'Scars'), 'scars', 'scar_color')),
    ('cr_slime', 'Slime & Wet', ('slime', 'wet'), ('slime', ('tex', 'slime', 'slime_color'), 'wet')),
    ('cr_moss', 'Moss', ('moss',), ('moss', ('tex', 'moss', 'moss_color'), 'h_moss')),
    ('cr_snow', 'Snow & Frost', ('snow', 'frost'), ('snow', 'frost')),
    ('cr_soot', 'Soot', ('soot',), ('soot', 'soot_color')),
    ('cr_rot', 'Rot & Weathering', ('rot', 'fade'), ('rot', 'rot_color', 'fade')),
    ('cr_glow', 'Glow', ('glow',), ('glow', 'glow_color', 'glow_power')),
)


def creature_content(b, x, width, mat):
    """The Material page of a Creature Shader material."""
    from . import creature_shader as cs
    from . import mech_shader as ms
    st = getattr(mat, cs.KEY)
    _cstep(b, st, 'skin_type', x, width)
    n_parts = len(ms.users_of(mat))
    b.note(('note', mat.name + (f'   - shared by {n_parts} parts' if n_parts > 1 else '   - this part only'), False,
            None, None, None, True), x, width)
    row(b, x, width, [_cell('tbtn', 'Unlink', ('op', 'mch.mech_shader_unlink', {}), active=n_parts > 1),
                      button('New Copy', 'mch.creature_apply', skin=st.skin_type, condition=st.condition),
                      button('Edges', 'mch.mech_shader_edges')])
    over_note(b, x, width, mat, 'your material is the skin: the conditions (mud, dust, blood ...) on top')
    skins = {kk: n for kk, n, _s in cs.SKINS}
    conds = {kk: n for kk, n, _s in cs.CONDITIONS}

    def skin_grid(sx, sw):
        grid(b, sx, sw, [(n, icon('cskin', kk), st.skin_type == kk, ('enum', kk), st, 'skin_type')
                         for kk, n, _s in cs.SKINS if kk not in cs.PART_SKINS])
    section(b, 'cr_skins', 'Skin Types', x, width, skin_grid, summary=skins.get(st.skin_type, ''))
    my_materials_section(b, x, width)

    def part_grid(sx, sw):
        b.note(('note', 'A new material of that part on the selected meshes', False, None, None, None, True), sx, sw)
        parts_grid(b, sx, sw)
    section(b, 'cr_parts', 'Parts', x, width, part_grid, start_folded=st.skin_type not in cs.PART_SKINS,
            summary=skins.get(st.skin_type, '') if st.skin_type in cs.PART_SKINS else '')

    def cond_grid(sx, sw):
        _cstep(b, st, 'condition', sx, sw, 'Condition')
        row(b, sx, sw, [prop_cell(st, 'cond_stack', 'Stack - add on top')])
        grid(b, sx, sw, [(n, icon('ccond', kk), st.condition == kk, ('enum', kk), st, 'condition')
                         for kk, n, _s in cs.CONDITIONS])
    section(b, 'cr_conds', 'Conditions', x, width, cond_grid,
            summary=conds.get(st.condition, '') + ('  +' if st.cond_stack else ''))
    my_presets_section(b, x, width, 'creature')
    zones_section(b, x, width, bpy.context, mat)

    def colour(sx, sw):
        row(b, sx, sw, [prop_cell(st, 'polypaint')])
        sub(b, 'Where there is no polypaint', sx, sw)
        _colour_rows(b, st, 'base', 'base_color', sx, sw)
        sub(b, 'Belly - the underside lighter (no polypaint)', sx, sw)
        row(b, sx, sw, [prop_cell(st, 'belly')])
        row(b, sx, sw, [prop_cell(st, 'belly_color')])
        sub(b, 'Mottle - a second colour', sx, sw)
        _cstep(b, st, 'mottle_map', sx, sw, 'Pattern')
        for p in ('mottle', 'mottle_color', 'mottle_scale', 'variation'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'cr_color', 'Color', x, width, colour)

    def skin(sx, sw):
        _cstep(b, st, 'skin_map', sx, sw, 'Relief')
        row(b, sx, sw, [number(st, 'h_skin', 'Height')])
        _cstep(b, st, 'detail_map', sx, sw, 'Detail')
        row(b, sx, sw, [number(st, 'h_detail', 'Height')])
        for p in ('skin_scale', 'roughness', 'rough_var', 'ridge_gloss', 'coat', 'irid'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'cr_skin', 'Skin', x, width, skin)

    def sss(sx, sw):
        for p in ('sss', 'sss_color', 'sss_radius', 'sss_thin', 'thick'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'cr_sss', 'SSS', x, width, sss, start_folded=st.sss <= 0.0, summary=layer_summary(st, ('sss',)))

    def shape(sx, sw):
        for p in ('cav_dark', 'cav_color', 'ridge_light', 'ridge_color', 'ao'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'cr_shape', 'Crevices & Ridges', x, width, shape, start_folded=True)

    for key, title, which, rows in CREATURE_LAYERS:
        def fill(sx, sw, rows=rows):
            for r in rows:
                if isinstance(r, tuple) and r[0] == 'tex':
                    _colour_rows(b, st, r[1], r[2], sx, sw)
                elif isinstance(r, tuple):
                    sub(b, r[1], sx, sw)
                else:
                    row(b, sx, sw, [prop_cell(st, r)])
        on = any(getattr(st, p) > 0.0 for p in which)
        section(b, key, title, x, width, fill, start_folded=not on, summary=layer_summary(st, which))

    bake_section(b, x, width, bpy.context)

    def overall(sx, sw):                         # (0.24.95 user: "크리쳐 메테리얼에도 가장 밑에다가 전체 조정")
        for p in ('bump', 'map_scale', 'ao', 'seed', 'size'):
            row(b, sx, sw, [prop_cell(st, p)])
        project_rows(b, sx, sw, bpy.context.scene)
        unlink_row(b, sx, sw, n_parts, button('New Copy', 'mch.creature_apply', skin=st.skin_type,
                                              condition=st.condition))
    section(b, 'cr_overall', 'Overall - Height & Scale', x, width, overall)


def sub(b, text, x, w):
    """A small heading inside a section."""
    b.gap(0.4)
    b.note(('note', text, False, None, None, None, True), x, w)


HDRI_PAGE = 6                     # (HDRI previews on a page - user: "6 개씩만 불러오면 안 돼? 넘기면 되잖아")
_HPAGE = {'page': 0, 'cur': None, 'pages': 1, 'ids': []}


def hdri_page(cur, ids):
    """(page, pages) of the HDRI previews: the page turned with ◀ ▶; when the HDRI in use changes (a click, the
    arrows above, a file opened) the page with it."""
    pages = max(1, -(-len(ids) // HDRI_PAGE))
    if cur != _HPAGE['cur']:
        _HPAGE['cur'] = cur
        _HPAGE['page'] = ids.index(cur) // HDRI_PAGE if cur in ids else 0
    _HPAGE['page'] = min(max(_HPAGE['page'], 0), pages - 1)
    _HPAGE['pages'], _HPAGE['ids'] = pages, ids
    return _HPAGE['page'], pages


class MCH_OT_mech_hdri_page(bpy.types.Operator):
    """Turn the page of HDRI previews (6 on a page; the page number: back to the HDRI in use)"""
    bl_idname = 'mch.mech_hdri_page'
    bl_label = 'HDRI Previews Page'
    bl_options = {'INTERNAL'}
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        pages = max(1, _HPAGE['pages'])
        if self.step == 0:
            cur, ids = context.scene.mch_mech_hdri, _HPAGE['ids']
            _HPAGE['page'] = ids.index(cur) // HDRI_PAGE if cur in ids else 0
        else:
            _HPAGE['page'] = (_HPAGE['page'] + self.step) % pages
        return {'FINISHED'}


def bgrid(b, x, w, tiles, cols=3):
    """0.24.95 Background pictures, square tiles in rows of ``cols`` (the picture fitted in, wide or tall):
    tiles = [(label, icon, on, action, aspect)]."""
    k = b.k
    gap = 5 * k
    tw = (w - (cols - 1) * gap) / cols
    th = tw * 0.8 + 15 * k
    for i, (label, ic, on, action, asp) in enumerate(tiles):
        c = i % cols
        if c == 0:
            b.y -= th + (gap if i else 0)
        b.out.append(b.Item('btile', x + c * (tw + gap), b.y, tw, th, label, ic, on, True, action, asp))
    b.y -= sp.GAP * k


def backdrop_previews(b, sc, sx, sw, faint=False):
    """0.24.95 The studio backdrops and the user's pictures, 6 on a page; a click = that picture behind the model."""
    from . import backdrops as bd, mech_shader as ms_
    ents = bd.entries()
    if not ents:
        return
    cur = getattr(sc, 'mch_mech_hdri_bg_image', '')
    on_img = not sc.mch_mech_hdri_show and getattr(sc, 'mch_mech_hdri_bg_mode', 'COLOR') == 'IMAGE'
    page, pages = bd.page_of(cur, [e[0] for e in ents])
    if pages > 1:
        stepper(b, sx, sw, button('◀', 'mch.mech_bg_page', step=-1),
                _cell('tbtn', f'Page {page + 1} / {pages}', ('op', 'mch.mech_bg_page', {'step': 0})),
                button('▶', 'mch.mech_bg_page', step=1))
    tiles = []
    for ident, label in ents[page * bd.PAGE:(page + 1) * bd.PAGE]:
        p = bd.path(ident)
        ic = ('file:' + p) if ident.startswith(bd.BUILTIN) else (ms_.picture_icon(p) if p else '')   # (yours: a
        tiles.append((label, ic, on_img and cur == ident,                                           #  small copy)
                      ('op', 'mch.mech_bg_image', {'ident': ident}), bd.aspect(p)))
    bgrid(b, sx, sw, tiles)
    d = bd.folder()
    n = len(bd.user_files()) if d else 0
    b.note(('note', (f'My pictures: {os.path.basename(os.path.normpath(d))} ({n})' if d else
                     'My pictures: none - the studio backdrops'), False, None, None, None, True), sx, sw)
    row(b, sx, sw, [button('Choose Folder…', 'mch.mech_bg_folder')])


class MCH_OT_mech_bg_mode(bpy.types.Operator):
    """Behind the model: a colour or a picture; Fill (the frame covered) or Fit (the whole picture)"""
    bl_idname = 'mch.mech_bg_mode'
    bl_label = 'Background'
    bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.StringProperty(default='', options={'SKIP_SAVE'})
    fit: bpy.props.StringProperty(default='', options={'SKIP_SAVE'})

    def execute(self, context):
        sc = context.scene
        if self.mode in {'COLOR', 'IMAGE'}:
            sc.mch_mech_hdri_bg_mode = self.mode
        if self.fit in {'FILL', 'FIT'}:
            sc.mch_mech_hdri_bg_fit = self.fit
        return {'FINISHED'}


# --- the Render page (0.24.95 HDRI page; 0.24.137 Render: Quick Render, Viewport, Background) --------------------

def quick_render_section(b, context, x, width):
    """0.24.133 (user: "렌더링이 빡센데 좀 더 빠르고 편하게", "난 사이클만 써") Quick Render (Cycles) on the Render page."""
    from . import quick_render as qr
    st = qr.settings(context)
    if st is None:
        return

    def fill(sx, sw):
        row(b, sx, sw, [button('Quick Render', 'mch.quick_render'), button('Open Folder', 'mch.quick_render_folder')])
        # 0.24.134 (user: "1억 폴리곤이면?") what matters for a heavy scene first, without scrolling: the device, the
        # triangles and the memory Cycles needs against the free RAM, the last render
        lines = qr.status_lines(context)
        b.note(('note', lines[0], not qr.gpu_ready(context), None, None, None, True), sx, sw)
        if not qr.gpu_ready(context):
            row(b, sx, sw, [button('Use the GPU (Blender Preferences)', 'mch.quick_render_gpu')])
        else:                                    # a scene too big for the graphics card: the RAM
            row(b, sx, sw, [prop_cell(st, 'cpu_only', 'CPU Only (scene too big for the GPU)')])
        mem, big = qr.memory_line(context, st)
        for ln in mem:
            b.note(('note', ln, big, None, None, None, True), sx, sw)
        for ln in lines[1:]:
            b.note(('note', ln, False, None, None, None, True), sx, sw)
        row(b, sx, sw, [_cell('seg', v['label'], ('enum', key), st, 'quality', on=st.quality == key)
                        for key, v in qr.QUALITY.items()])
        row(b, sx, sw, [_cell('seg', 'This View', ('enum', 'VIEW'), st, 'camera', on=st.camera == 'VIEW'),
                        _cell('seg', 'Scene Camera', ('enum', 'SCENE'), st, 'camera', on=st.camera == 'SCENE')])
        row(b, sx, sw, [prop_cell(st, 'fast_shading', 'Fast Shading'), prop_cell(st, 'clay', 'Clay')])
        row(b, sx, sw, [prop_cell(st, 'selected_only', 'Selected Only'), prop_cell(st, 'transparent', 'Transparent')])
        row(b, sx, sw, [prop_cell(st, 'hidden_stay_hidden', 'Hidden Stay Hidden'), prop_cell(st, 'save', 'Save')])
    q = qr.QUALITY[st.quality]
    section(b, 'quick_render', 'Quick Render (Cycles)', x, width, fill, summary=q['label'])


def viewport_section(b, context, x, width):
    """0.24.135 / 0.24.136 (user: "뷰포트에서도 빨라야 돼", "사본 쓰면 더 빨라?" -> "그럼 일단 그렇게 해 보고") the viewport:
    Fast Viewport, Blender's viewport anti-aliasing, Light Copies."""
    from . import fast_view, light_copies as lc
    sc = context.scene
    lst = lc.settings(context)

    def fill(sx, sw):
        row(b, sx, sw, [_cell('seg', 'Fast Viewport (Solid + Rendered)', ('op', 'mch.fast_view', {}),
                              on=fast_view.on(sc))])
        aa = fast_view.aa_value(context)
        if aa is not None:
            row(b, sx, sw, [button('Viewport AA: Single Pass (back to 8)' if aa == fast_view.AA_FAST
                                   else f'Viewport AA: {fast_view.aa_label(aa)} > Single Pass', 'mch.viewport_aa')])
        if lst is None:
            return
        row(b, sx, sw, [_cell('seg', 'Light Copies (parts not worked on)', ('op', 'mch.light_copies', {}),
                              on=lst.on)])
        row(b, sx, sw, [number(lst, 'percent', 'Copy %')])
        row(b, sx, sw, [number(lst, 'min_tris', 'From')])
        for ln in lc.status(context):
            b.note(('note', ln, False, None, None, None, True), sx, sw)
    on = [t for t, v in (('Fast', fast_view.on(sc)), ('Light', lst is not None and lst.on)) if v]
    section(b, 'viewport', 'Viewport', x, width, fill, summary=' + '.join(on))


def background_section(b, context, x, width):
    """0.24.137 (user: "HDRI 는 다른 애드온 쓸 거라 배경만 내가 원하는 색으로 바꿀 수 있게 해 주라") Background Colour on
    whatever world the scene has."""
    from . import bg_color as bgc, mech_shader as ms
    sc = context.scene
    st = bgc.settings(sc)
    if st is None:
        return
    on = bgc.on(sc)

    def fill(sx, sw):
        row(b, sx, sw, [_cell('seg', 'Background Colour', ('op', 'mch.bg_color', {}), on=on),
                        swatch(st, 'color', 'Colour')])
        row(b, sx, sw, [prop_cell(st, 'solid_too', 'Solid View Too')])
        b.note(('note', 'The camera sees the colour; your HDRI still lights the parts', False, None, None, None,
                True), sx, sw)
        if ms.hdri_world(sc) is not None:            # (a scene still on the old Mecha HDRI world: back to its own)
            row(b, sx, sw, [button('Mecha HDRI Off (back to your world)', 'mch.mech_hdri', action='OFF')])
    section(b, 'background_colour', 'Background', x, width, fill, summary='on' if on else '')


def hdri_content(context, x, width, k):
    """(items, content height) - the Render page (0.24.137, was HDRI: the HDRI library is gone - the user's own HDRI
    add-on lights the scene): Quick Render, the viewport, the background colour."""
    b = sp.Builder('HDRI', x, width, k)
    quick_render_section(b, context, x, width)
    viewport_section(b, context, x, width)
    background_section(b, context, x, width)
    return b.out, -b.y


# --- the folder ----------------------------------------------------------------------------------------------------

class MCH_OT_mech_hdri_folder(bpy.types.Operator):
    """Choose the folder you keep your HDRIs in (.hdr / .exr / .jpg / .png): they come first in the HDRI list,
    marked * (Mecha Lab preferences, HDRI Folder)"""
    bl_idname = 'mch.mech_hdri_folder'
    bl_label = 'Choose HDRI Folder'
    bl_options = {'INTERNAL'}
    directory: bpy.props.StringProperty(subtype='DIR_PATH')

    def invoke(self, context, event):
        from .workspace_ui import pref
        self.directory = pref('hdri_folder', '') or ''
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from . import mech_shader as ms
        from .workspace_ui import prefs
        pr = prefs()
        if pr is None:
            self.report({'WARNING'}, 'HDRI Folder: the Mecha Lab preferences are not available')
            return {'CANCELLED'}
        pr.hdri_folder = self.directory
        n = len(ms.user_hdri_files())
        sp.dirty()
        self.report({'INFO'}, f'HDRI Folder: {n} HDRI{"s" if n != 1 else ""} found'
                    + ('' if n else ' (.hdr / .exr / .jpg / .png)'))
        return {'FINISHED'}


class MCH_OT_mech_hdri_remove(bpy.types.Operator):
    """Take HDRIs of your folder out of the list - the files themselves are not touched.  Remove: the one picked;
    Remove All: every one (the folder let go - Choose Folder brings them back); Bring Back: the removed ones"""
    bl_idname = 'mch.mech_hdri_remove'
    bl_label = 'Remove HDRI from the List'
    bl_options = {'INTERNAL'}
    what: bpy.props.EnumProperty(items=[('ONE', 'Remove', ''), ('ALL', 'Remove All', ''),
                                        ('RESTORE', 'Bring Back', '')], default='ONE')

    def execute(self, context):
        from . import mech_shader as ms
        try:
            if self.what == 'ONE':
                name = ms.remove_hdri(context, context.scene.mch_mech_hdri)
                msg = f'"{name}" out of the HDRI list (the file is kept)'
            elif self.what == 'ALL':
                n = ms.remove_all_hdris(context)
                msg = f'{n} HDRI{"s" if n != 1 else ""} of your folder out of the list (the files are kept; Choose ' \
                      'Folder brings them back)'
            else:
                n = ms.restore_hdris()
                msg = f'{n} removed HDRI{"s" if n != 1 else ""} back in the list'
        except RuntimeError as ex:
            self.report({'WARNING'}, f'HDRI: {ex}')
            return {'CANCELLED'}
        sp.dirty()
        self.report({'INFO'}, msg)
        return {'FINISHED'}


CLASSES = (MCH_OT_mech_hdri_folder, MCH_OT_mech_hdri_remove, MCH_OT_mech_hdri_page, MCH_OT_mech_bg_mode)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
