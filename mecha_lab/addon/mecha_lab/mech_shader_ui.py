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
        other = getattr(ob, 'active_material', None) if ob is not None else None
        if ob is None or ob.type != 'MESH':
            b.note(('note', 'Select meshes, then Apply', False, None, None, None, True), x, width)
        elif other is not None and not (cs.is_creature(other) or cs.is_eye(other)):
            b.note(('note', f'"{other.name}" is not a Mech material - Apply makes one', False, None, None, None,
                    True), x, width)
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
    names = {kk: n for kk, n, _s in ms.PRESETS}

    def presets(sx, sw):
        grid(b, sx, sw, [(n, icon('mat', kk), st.preset == kk, ('enum', kk), st, 'preset') for kk, n, _s in ms.PRESETS])
    section(b, 'presets', 'Presets', x, width, presets, summary=names.get(st.preset, ''))
    my_presets_section(b, x, width, 'mech')
    zones_section(b, x, width, context, mat)

    def surface(sx, sw):
        for p in SURFACE:
            if p == 'ior' and st.glass <= 0.0:
                continue
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'surface', 'Surface', x, width, surface)

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
    section(b, 'paint', 'Paint', x, width, paint, start_folded='paint' not in used, summary=layer_summary(st, ('paint',)))

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

    def detail(sx, sw):
        for p in DETAIL:
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'detail', 'Height & Detail', x, width, detail, start_folded=True)
    return b.out, -b.y


def zones_section(b, x, width, context, mat):
    """0.24.95 Lasso Zones (user: "메카닉 할 때 내가 라쏘로 그은 영역 색이랑 재질 다르게"): Paint Zone (its own paint,
    projected - the mesh as it is) / Split Zone (edges cut along it, a material of its own); the zones' sliders; the
    part's materials (slots) to switch between."""
    from . import mech_shader as ms
    from . import zones as zn
    ob = getattr(context, 'active_object', None)
    zs = zn.zones_of(mat)
    slots = [sl for sl in getattr(ob, 'material_slots', ())] if ob is not None else []

    def fill(sx, sw):
        b.note(('note', 'Draw on the part: drag a lasso, or click its corners (Enter: done)', False, None, None, None,
                True), sx, sw)
        row(b, sx, sw, [button('Paint Zone', 'mch.zone_lasso', mode='PAINT'),
                        button('Split Zone', 'mch.zone_lasso', mode='SPLIT')])
        sub(b, 'Paint: its own paint, the mesh as it is.  Split: new edges, its own material', sx, sw)
        for i, z in enumerate(zs or ()):
            if z.kind == 'LINE':                    # (a Split Zone's boundary line - in both its materials)
                sub(b, f'{z.name} - the boundary line', sx, sw)
                for p in ('line_height', 'line_width'):
                    row(b, sx, sw, [prop_cell(z, p)])
                row(b, sx, sw, [_cell('tbtn', 'Remove Line', ('op', 'mch.zone_remove', {'index': i}))])
                continue
            sub(b, f'{z.name} - paint', sx, sw)
            for p in ('color', 'roughness', 'metallic', 'cover', 'opacity', 'line_height', 'line_width'):
                row(b, sx, sw, [prop_cell(z, p)])
            row(b, sx, sw, [prop_cell(z, 'own_wear', 'Own Wear - chips, scratches, dirt, rust')])
            if z.own_wear:
                for p in ms.ZONE_WEAR:
                    row(b, sx, sw, [prop_cell(z, p)])
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


PAGE_NAMES = {'MATERIAL': 'Mech', 'CREATURE': 'Creature', 'DECALS': 'Decals', 'HDRI': 'HDRI'}


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
    creature_apply_section(b, x, width, sc, start_folded=False)
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
        for p in ('size', 'offset'):
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
    skins = {kk: n for kk, n, _s in cs.SKINS}
    conds = {kk: n for kk, n, _s in cs.CONDITIONS}

    def skin_grid(sx, sw):
        grid(b, sx, sw, [(n, icon('cskin', kk), st.skin_type == kk, ('enum', kk), st, 'skin_type')
                         for kk, n, _s in cs.SKINS if kk not in cs.PART_SKINS])
    section(b, 'cr_skins', 'Skin Types', x, width, skin_grid, summary=skins.get(st.skin_type, ''))

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

    def detail(sx, sw):
        for p in ('bump', 'map_scale', 'seed', 'size'):
            row(b, sx, sw, [prop_cell(st, p)])
    section(b, 'cr_detail', 'Height & Detail', x, width, detail, start_folded=True)


def sub(b, text, x, w):
    """A small heading inside a section."""
    b.gap(0.4)
    b.note(('note', text, False, None, None, None, True), x, w)


# --- the HDRI page (0.24.95 user: "재질이랑 hdri는 분리해야지") ------------------------------------------------------

def hdri_content(context, x, width, k):
    """(items, content height) - the HDRI page: the scene's lighting, apart from the material."""
    from . import mech_shader as ms
    b = sp.Builder('HDRI', x, width, k)
    sc = context.scene
    w = ms.hdri_world(sc)
    if w is not None:
        name = dict((i[0], i[1]) for i in ms._hdri_items(None, context)).get(sc.mch_mech_hdri, sc.mch_mech_hdri)
        status = f'On: {name}  (the scene\'s world)'
    else:
        status = 'Off - the scene\'s own world.  Set HDRI puts it on'
    b.note(('note', status, False, None, None, None, True), x, width)
    stepper(b, x, width, button('◀', 'mch.mech_hdri', action='SET', step=-1),
            _cell('drop', '', ('menu_enum',), sc, 'mch_mech_hdri'),
            button('▶', 'mch.mech_hdri', action='SET', step=1))
    row(b, x, width, [button('Set HDRI', 'mch.mech_hdri', action='SET'),
                      button('Off', 'mch.mech_hdri', action='OFF')])

    def previews(sx, sw):                        # (0.24.95 user: "hdri 도 미리 보기 넣어 줘") click = that HDRI, on
        hgrid(b, sx, sw, [(n, ms.hdri_icon(ident), sc.mch_mech_hdri == ident,
                           ('op', 'mch.mech_hdri', {'action': 'SET', 'ident': ident}))
                          for ident, n, *_r in ms._hdri_items(None, context) if ident != 'NONE'])
    section(b, 'hdri_previews', 'HDRIs', x, width, previews)

    def folder(sx, sw):
        d = ms.user_hdri_dir()
        if d:
            n = len(ms.user_hdri_files())
            text = f'Folder: {os.path.basename(os.path.normpath(d))}  ({n} HDRI{"s" if n != 1 else ""}, * in the list)'
        else:
            text = 'Folder: none - Blender\'s own HDRIs'
        b.note(('note', text, False, None, None, None, True), sx, sw)
        row(b, sx, sw, [button('Choose Folder…', 'mch.mech_hdri_folder')])
    section(b, 'folder', 'My HDRIs', x, width, folder)

    def light(sx, sw):
        for p in ('mch_mech_hdri_strength', 'mch_mech_hdri_rot'):
            row(b, sx, sw, [number(sc, p)])
    section(b, 'light', 'Light', x, width, light)

    def background(sx, sw):
        row(b, sx, sw, [number(sc, 'mch_mech_hdri_blur', 'Blur')])
        row(b, sx, sw, [prop_cell(sc, 'mch_mech_hdri_show', 'Show (Cycles)')])
    section(b, 'background', 'Background', x, width, background)
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


CLASSES = (MCH_OT_mech_hdri_folder,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
