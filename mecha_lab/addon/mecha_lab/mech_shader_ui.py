"""0.24.95 The Mech Shader and the HDRI in Mecha Lab's own side panel (the Material page), in the Mecha look.

User: "우리 예쁘게 만든 우리의 유아이가 이미 메카 랩에 있는데 왜 다시 블렌더 기본 패널로 바꿨어" - the material's
settings were only in a Blender sidebar panel (Mecha Lab tab).  They are drawn here like every tool's settings:

* the side panel has two tabs at its top, the tool's settings | Material (the Mecha Menu's Material button opens it)
* preset / maps / HDRI: ◀ [list v] ▶ - the arrows step, the list opens the choices
* numbers -> bars (drag, click = type, Ctrl+click = default), colours -> a swatch (click = colour picker)
* Surface (base colour, metallic, roughness, glass, IOR, alpha, clear coat, brushed), the base / roughness maps,
  each layer (paint & wear, scratches, rust, dirt, snow, glow, weave) in its own section - a layer in use starts
  open, its amount in the section's title - then Detail and the HDRI (folder, blur ...)

The Blender sidebar panel stays (the drawn panel hides while the sidebar is open, as for the tools)."""
from __future__ import annotations

import os

import bpy

from . import side_panel as sp

PAGE = 'MATERIAL'
# (slot, section title, what makes it "in use", rows before the amount, the amount, rows after, its height)
LAYERS = (
    ('chip', 'Paint & Wear', ('paint', 'edge_wear', 'primer'),
     ('paint', 'paint_color', 'paint_rough', 'paint_pattern', 'primer', 'primer_color'), 'edge_wear', (), 'h_chip'),
    ('scratch', 'Scratches', ('scratches',), (), 'scratches', (), 'h_scratch'),
    ('rust', 'Rust', ('rust', 'rust_scratch'), ('rust_color',), 'rust', ('rust_scratch',), 'h_rust'),
    ('dirt', 'Dirt', ('dirt', 'dirt_top', 'dirt_low', 'dust', 'streaks'), ('dirt_color',), 'dirt',
     ('dirt_top', 'dirt_low', 'dust', 'streaks'), 'h_dirt'),
    ('snow', 'Snow', ('snow',), (), 'snow', ('snow_soft',), 'h_snow'),
    ('emit', 'Glow', ('emission',), ('emit_color',), 'emission', (), None),
    ('weave', 'Weave', ('cloth',), (), 'cloth', (), 'h_weave'),
)
SURFACE = ('base_color', 'metallic', 'roughness', 'glass', 'ior', 'alpha', 'coat', 'aniso')
DETAIL = ('bump', 'ao', 'map_scale', 'edge_width')
_IN_USE = {}             # (material, preset) -> the layers in use when it was first shown: they start open


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
        _IN_USE[key] = frozenset(slot for slot, _t, used, *_r in LAYERS if any(getattr(st, p) > 0.0 for p in used))
    return _IN_USE[key]


def layer_summary(st, used):
    v = max(getattr(st, p) for p in used)
    return '' if v <= 0.0 else (f'{v:.1f}' if v > 1.0 else _pct(v))


# --- the page ------------------------------------------------------------------------------------------------------

def content(context, x, width, k):
    """(items, content height) - the Material page's rows, y measured down from 0 (as ``side_panel.content``)."""
    from . import mech_shader as ms
    b = sp.Builder(PAGE, x, width, k)
    sc = context.scene
    ob = getattr(context, 'active_object', None)
    mat = ms.active_mech(context)
    if mat is None:
        _preset_stepper(b, sc, 'mch_mech_preset', x, width)
        row(b, x, width, [button('Apply Mech Shader', 'mch.mech_shader_apply', preset='')])
        other = getattr(ob, 'active_material', None) if ob is not None else None
        if ob is None or ob.type != 'MESH':
            b.note(('note', 'Select meshes, then Apply', False, None, None, None, True), x, width)
        elif other is not None:
            b.note(('note', f'"{other.name}" is not a Mech material - Apply makes one', False, None, None, None,
                    True), x, width)
        hdri(b, context, x, width)
        return b.out, -b.y
    st = getattr(mat, ms.KEY)
    _preset_stepper(b, st, 'preset', x, width)
    b.note(('note', mat.name + (f'   ({mat.users} users)' if mat.users > 1 else ''), False, None, None, None, True),
           x, width)
    row(b, x, width, [button('New Copy', 'mch.mech_shader_apply', preset=st.preset),
                      button('Edges', 'mch.mech_shader_edges')])

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
    hdri(b, context, x, width)
    return b.out, -b.y


def hdri(b, context, x, width):
    from . import mech_shader as ms
    sc = context.scene
    on = ms.hdri_world(sc) is not None

    def fill(sx, sw):
        stepper(b, sx, sw, button('◀', 'mch.mech_hdri', action='SET', step=-1),
                _cell('drop', '', ('menu_enum',), sc, 'mch_mech_hdri'),
                button('▶', 'mch.mech_hdri', action='SET', step=1))
        d = ms.user_hdri_dir()
        if d:
            n = len(ms.user_hdri_files())
            text = f'Folder: {os.path.basename(os.path.normpath(d))}  ({n} HDRI{"s" if n != 1 else ""}, * in the list)'
        else:
            text = 'Folder: none - Blender\'s own HDRIs'
        b.note(('note', text, False, None, None, None, True), sx, sw)
        row(b, sx, sw, [button('Choose Folder…', 'mch.mech_hdri_folder')])
        for p, label in (('mch_mech_hdri_strength', None), ('mch_mech_hdri_rot', None),
                         ('mch_mech_hdri_blur', 'Background Blur')):
            row(b, sx, sw, [number(sc, p, label)])
        row(b, sx, sw, [prop_cell(sc, 'mch_mech_hdri_show', 'Show Background')])
        row(b, sx, sw, [button('Set HDRI', 'mch.mech_hdri', action='SET'),
                        button('Off', 'mch.mech_hdri', action='OFF')])
    section(b, 'hdri', 'HDRI', x, width, fill, summary='on' if on else '')


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
