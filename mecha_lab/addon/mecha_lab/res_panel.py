"""0.24.282 / 0.24.283 (user: "해상도 글씨 옆에 세팅 버튼 - 누르면 옆에 세팅 뜨고, 원하는 버튼 (리메시, 데시메이션 등)
누르면 그땐 세팅 조절 가능, 다시 세팅 버튼 눌러서 끄면 버튼 누르면 바로 적용") The bottom row's Resolution settings.

A Settings switch beside the RESOLUTION title.  Off (as always): Remesh / Quad / Low Poly / HP Keep / HP Round /
HP Divide / Decimate run at once.  On: the row's leftmost box (the one that changes with the tool) shows the settings
of the button clicked last (the button lit) instead of running it; Apply in the box runs it; the switch off again (or
Close) puts the tool's box back and the buttons run at once again.
The settings are the ones the panels already had (the scene's / the ZBrush shelf's): nothing copied.
Quad: the engine - Mecha Lab's own (Flow, 0.24.281) or the old QuadriFlow / Patch (Make Quad, the original kept).
"""
from __future__ import annotations

import bpy

ARMED = [None]           # the key of the button whose settings the box shows, or None
SETTINGS = [False]       # 0.24.283 the Settings switch beside the RESOLUTION title

# (label of the button in mecha_menu.ACTIONS 'Resolution') -> key
KEYS = {'Remesh': 'REMESH', 'Quad': 'QUAD', 'Low Poly': 'LOWPOLY', 'HP Keep': 'HP_KEEP', 'HP Round': 'HP_ROUND',
        'HP Divide': 'HP_DIVIDE', 'Decimate': 'DECIMATE'}
TITLES = {'REMESH': 'Remesh', 'QUAD': 'Quad Remesh', 'LOWPOLY': 'Low Poly', 'HP_KEEP': 'HP Keep',
          'HP_ROUND': 'HP Round', 'HP_DIVIDE': 'HP Divide', 'DECIMATE': 'Decimate'}

ROW = 34.0               # px (x UI factor) a settings row
WIDTH = 300.0
TITLE_H = 19.0


def armed():
    return ARMED[0]


def settings_on():
    return SETTINGS[0]


def toggle_settings():
    SETTINGS[0] = not SETTINGS[0]
    if not SETTINGS[0]:
        ARMED[0] = None
    _redraw()


def close():
    SETTINGS[0] = False
    ARMED[0] = None
    _redraw()


def _redraw():
    try:
        from . import side_panel
        side_panel.dirty()
    except (ImportError, AttributeError):
        pass
    for w in getattr(bpy.context.window_manager, 'windows', ()):
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()


def _run(context, key):
    """The button's own job, as its one click did (mecha_menu.ACTIONS), Quad: the engine chosen here."""
    from . import mecha_menu as mm
    sc = context.scene
    if key == 'QUAD' and getattr(sc, 'mch_res_quad_engine', 'NEW') == 'NEW':
        op, props, invoke = 'mch.mesh_tool', {'action': 'QUAD_REMESH'}, False
    else:
        label = next(lb for lb, k in KEYS.items() if k == key)
        btn = next(b for sec, bs in mm.ACTIONS if sec == 'Resolution' for b in bs if b[0] == label)
        op, props, invoke = btn[2], dict(btn[3]), btn[5]
    if context.mode != 'OBJECT':
        try:
            bpy.ops.object.mode_set(mode='OBJECT')
        except RuntimeError:
            pass
    mod, name = op.split('.')
    getattr(getattr(bpy.ops, mod), name)('INVOKE_DEFAULT' if invoke else 'EXEC_DEFAULT', True, **props)
    return TITLES.get(key, key)


def press(context, key):
    """A click on one of the buttons: Settings on - its settings in the box; off - run it.  Returns a short report."""
    if SETTINGS[0]:
        ARMED[0] = key
        _redraw()
        return ''
    return _run(context, key)


def apply(context, key):
    """The box's Apply: run ``key`` with the settings shown (the box stays)."""
    return _run(context, key)


def fields(context, key):
    """[(kind, data, prop, label)] the settings shown for ``key``: kind 'num' / 'bool' / 'enum' (one row of choices) /
    'note' (data = the text)."""
    sc = context.scene
    zb = getattr(sc, 'mch_zb', None)
    out = []
    if key == 'REMESH':
        s = sc.mch_settings
        out.append(('enum', s, 'remesh_by', 'Remesh By'))
        out.append(('num', s, 'target_points' if s.remesh_by == 'POINTS' else 'voxel_size', ''))
        out += [('num', s, 'smooth_iterations', ''), ('num', s, 'smooth_factor', ''),
                ('bool', s, 'join_remesh', ''), ('bool', s, 'apply_remesh', ''), ('bool', s, 'apply_existing', '')]
    elif key == 'QUAD':
        out.append(('enum', sc, 'mch_res_quad_engine', 'Engine'))
        if sc.mch_res_quad_engine == 'NEW' and zb is not None:
            out += [('num', zb, 'qr_target', 'Target (k)'), ('enum', zb, 'qr_mode', ''),
                    ('num', zb, 'qr_angle', 'Hard Edges'), ('num', zb, 'qr_flow', ''), ('num', zb, 'qr_subd', '')]
        else:
            st = sc.mch_quadremesh
            out += [('enum', st, 'method', ''), ('num', st, 'faces', ''), ('num', st, 'edge_angle', ''),
                    ('bool', st, 'keep_marked', ''), ('bool', st, 'smooth_shade', '')]
    elif key == 'LOWPOLY':
        st = sc.mch_lowpoly
        out += [('num', st, p, '') for p in ('faces', 'detail', 'flat_angle', 'side_angle', 'bevel_width',
                                              'bevel_segments', 'bevel_angle') if hasattr(st, p)]
    elif key in {'HP_KEEP', 'HP_ROUND', 'HP_DIVIDE'} and zb is not None:
        out += [('num', zb, 'bk_target', ''), ('num', zb, 'bk_rounding', ''), ('num', zb, 'bk_fillet', ''),
                ('bool', zb, 'bk_copy', '')]
    elif key == 'DECIMATE' and zb is not None:
        out += [('num', zb, 'decimate', 'Keep %'), ('bool', zb, 'dec_even', ''), ('bool', zb, 'dec_quads', ''),
                ('bool', zb, 'dec_borders', ''), ('enum', zb, 'result_shade', '')]
    return [f for f in out if f[0] == 'note' or (f[1] is not None and hasattr(f[1], f[2]))]


def card(context, k):
    """(width, height, items from 0, 0 going down) of the box with the armed button's settings, or None."""
    if not SETTINGS[0]:
        return None
    key = ARMED[0]
    from .mecha_menu import Item
    from . import i18n
    ko = i18n.lang() == 'KO'
    w = WIDTH * k
    if key is None:
        title = '해상도 설정' if ko else 'RESOLUTION SETTINGS'
        out = [Item('glabel', 0, -TITLE_H * k, w, TITLE_H * k, title, 'title')]
        note = '해상도 버튼을 누르면 그 설정이 여기에' if ko else 'Click a Resolution button: its settings show here'
        out.append(Item('glabel', 0, -(TITLE_H + ROW) * k, w, 30 * k, note, ''))
        out.append(Item('seg', 0, -(TITLE_H + 2 * ROW) * k, w, 30 * k, 'Close', '', False, True, ('resclose',)))
        return w, (TITLE_H + 2 * ROW) * k, out
    title = i18n.tr(TITLES.get(key, key))
    title = title if ko else title.upper()
    out = [Item('glabel', 0, -TITLE_H * k, w, TITLE_H * k, title, 'title')]
    y = -TITLE_H * k
    for kind, data, prop, label in fields(context, key):
        rna = data.bl_rna.properties[prop]
        name = label or rna.name or prop
        y -= ROW * k
        if kind == 'num':
            out.append(Item('mini', 0, y, w, 30 * k, name, '', False, True, ('number',), data, prop))
        elif kind == 'bool':
            out.append(Item('seg', 0, y, w, 30 * k, name, '', bool(getattr(data, prop)), True, ('bool',), data, prop))
        elif kind == 'enum':
            items = [(e.identifier, e.name) for e in rna.enum_items]
            cur = getattr(data, prop)
            cw = w / max(1, len(items))
            for n, (ident, nm) in enumerate(items):
                out.append(Item('seg', n * cw, y, cw - 3 * k, 30 * k, nm, '', cur == ident, True, ('enum', ident),
                                data, prop))
    y -= ROW * k
    out.append(Item('seg', 0, y, w * 0.62, 30 * k, 'Apply', '', True, True, ('resapply', key)))
    out.append(Item('seg', w * 0.64, y, w * 0.36, 30 * k, 'Close', '', False, True, ('resclose',)))
    return w, -y, out


def register():
    bpy.types.Scene.mch_res_quad_engine = bpy.props.EnumProperty(
        name='Engine', default='NEW',
        items=[('NEW', 'Flow (new)', "Mecha Lab's own quad remesher: Hard Edges, Flow (follows the softer folds), "
                                     'Subdivision; the part itself is remeshed'),
               ('OLD', 'QuadriFlow / Patch', 'Make Quad (Blender QuadriFlow or the Patch grid): a quad copy, the '
                                             'original kept hidden')],
        description='Quad: which remesher the Quad button of the bottom row runs')


def unregister():
    ARMED[0] = None
    SETTINGS[0] = False
    if hasattr(bpy.types.Scene, 'mch_res_quad_engine'):
        del bpy.types.Scene.mch_res_quad_engine
