"""0.24.60 The ZBrush-style sculpt screen, drawn in the Mecha look with an orange accent (the user's ZBrush custom UI):

    top shelf      Edit Draw | Move Scale Rotate | Material | Zadd Zsub | Z Intensity  Focal Shift  Draw Size Dynamic
                   | Polish By Groups | Check Mesh Fix Mesh  /  Make PolyMesh3D | DynaMesh > SubDiv | OBJ STL | FBX
    left shelf     SubTool / Geometry / Masking / Stroke / Decimation buttons (the Blender-layout drawer
                   ``draw_tool_shelf`` read by panel_capture, like the side panel), then brush / stroke / material /
                   colour / symmetry / clip / initialize
    right          view shelf (Persp Floor Frame Move Zoom3D Rotate PolyF Transp Solo ...) and the SubTool list
    bottom         the brush shelf (Blender brushes, ZBrush names), IMM Primitives / Append, subtool buttons
    at the cursor  Space / S / U / O / right-click menu, B brushes
Clicks go through ``ui_bars`` (hit test / run) like the rest of the drawn UI.
"""
from __future__ import annotations

import bpy

from . import panel_capture as pc
from . import zb_sculpt as zs

ROW = 24.0
GAP = 4.0
PAD = 8.0
SEP = 12.0
A_W = 290.0             # left shelf (actions)
B_W = 116.0             # left shelf (brush / symmetry ...)
V_W = 74.0              # view shelf
S_W = 290.0             # SubTool list
TOP_MARGIN = 150.0
TILE_W, TILE_H = 76.0, 60.0


def _ops_cell(label, action, on=False, kind='tbtn'):
    return {'kind': kind, 'label': label, 'on': on, 'action': ('op', 'mch.zb_action', {'action': action})}


def _prop_cell(zb, prop, kind, label='', width=None, on=None, value=None):
    act = {'mini': ('number',), 'seg': ('bool',), 'drop': ('menu_enum',)}[kind]
    if value is not None:
        act = ('enum', value)
    return {'kind': kind, 'label': label, 'on': bool(getattr(zb, prop)) if on is None else on, 'action': act,
            'data': zb, 'prop': prop, 'width': width}


# --- the left shelf as an ordinary panel drawer (read by panel_capture, drawn by side_panel.Builder) --------------

def draw_tool_shelf(layout, context):
    zb = context.scene.mch_zb

    def ops(row, *pairs):
        for text, action in pairs:
            row.operator('mch.zb_action', text=text).action = action
    box = layout.box()
    box.label(text='SubTool')
    r = box.row()
    ops(r, ('Duplicate', 'DUPLICATE'))
    r.operator('mch.zb_append', text='Append').kind = 'SPHERE'
    box.prop(zb, 'backface_mask', toggle=True)
    ops(box.row(), ('Split Unmasked', 'SPLIT_UNMASKED'), ('Split Masked', 'SPLIT_MASKED'))
    r = box.row()
    ops(r, ('Extract', 'EXTRACT'))
    r.prop(zb, 'thick')
    box = layout.box()
    box.label(text='Geometry')
    ops(box.row(), ('Del Lower', 'DEL_LOWER'), ('Del Higher', 'DEL_HIGHER'))
    r = box.row()
    ops(r, ('Divide', 'DIVIDE'))
    r.prop(zb, 'sdiv')
    r = box.row()
    ops(r, ('DynaMesh', 'DYNAMESH'))
    r.prop(zb, 'points')
    r = box.row()
    ops(r, ('ZRemesher', 'ZREMESH'))
    r.prop(zb, 'target_polys', text='Target')
    ops(box.row(), ('Half', 'HALF'), ('Same', 'SAME'))
    r = box.row()
    r.prop(zb, 'keep_creases', toggle=True)
    r.prop(zb, 'keep_border', toggle=True)
    ops(box.row(), ('Mirror', 'MIRROR'), ('Mirror And Weld', 'MIRROR_WELD'))
    ops(box.row(), ('Close Holes', 'CLOSE_HOLES'), ('Del Hidden', 'DEL_HIDDEN'))
    r = box.row()
    ops(r, ('Inflate', 'INFLATE'))
    r.prop(zb, 'inflate', text='Amount')
    box = layout.box()
    box.label(text='Masking')
    r = box.row()
    ops(r, ('Mask By Cavity', 'MASK_CAVITY'))
    r.prop(zb, 'blur')
    ops(box.row(), ('Invert', 'MASK_INVERT'), ('Clear', 'MASK_CLEAR'), ('Blur', 'MASK_BLUR'))
    box = layout.box()
    box.label(text='Stroke')
    r = box.row()
    r.prop(zb, 'double', toggle=True)
    r.prop(zb, 'lazy_mouse', toggle=True)
    r = box.row()
    r.prop(zb, 'lazy_step')
    r.prop(zb, 'lazy_radius')
    box = layout.box()
    box.label(text='Decimation')
    r = box.row()
    ops(r, ('Decimate Current', 'DECIMATE'))
    r.prop(zb, 'decimate', text='%')


def _builder():
    from . import side_panel

    class ZBBuilder(side_panel.Builder):
        """ZBrush shelves pair a button with its slider on one line (Divide | SDiv): narrower bars."""

        def _min_w(self, c):
            if c[0] in {'mini', 'switch'}:
                return 96.0 * self.k
            return super()._min_w(c)
    return ZBBuilder


def _shelf_rows(context, x, width, k):
    b = _builder()('ZB', x, width, k)
    node = pc.capture(draw_tool_shelf, context)
    if node.opts.get('error'):
        return [], 0.0
    b.node(node, x, width)
    return b.out, -b.y


# --- layout --------------------------------------------------------------------------------------------------------

def _cells_row(Item, out, cells, x, y, k, rowh=ROW):
    for c in cells:
        w = (c.get('width') or (len(c['label']) * 7.0 + 22.0)) * k
        it = Item(c['kind'], x, y, w, rowh * k, c['label'], c.get('icon', ''), c.get('on', False), True,
                  c['action'], c.get('data'), c.get('prop', ''))
        out.append(it)
        x += w + GAP * k
    return x


def _cells_width(cells, k):
    return sum((c.get('width') or (len(c['label']) * 7.0 + 22.0)) * k for c in cells) + GAP * k * (len(cells) - 1)


def top_shelf(context, region_w, region_h, k, Item):
    zb = context.scene.mch_zb
    tool = zs._tool_id(context)
    rows = [
        [('', [_ops_cell('Edit', 'EDIT', True, 'seg'), _ops_cell('Draw', 'DRAW', tool == 'builtin.brush', 'seg')]),
         ('', [_ops_cell('Move', 'MOVE', tool == 'builtin.move', 'seg'),
               _ops_cell('Scale', 'SCALE', tool == 'builtin.scale', 'seg'),
               _ops_cell('Rotate', 'ROTATE', tool == 'builtin.rotate', 'seg')]),
         ('Mat', [_prop_cell(zb, 'matcap', 'drop', width=120)]),
         ('', [_prop_cell(zb, 'zmode', 'seg', 'Zadd', 56, on=zb.zmode == 'ZADD', value='ZADD'),
               _prop_cell(zb, 'zmode', 'seg', 'Zsub', 56, on=zb.zmode == 'ZSUB', value='ZSUB')]),
         ('', [_prop_cell(zb, 'z_intensity', 'mini', width=150), _prop_cell(zb, 'focal_shift', 'mini', width=150),
               _prop_cell(zb, 'draw_size', 'mini', width=150), _prop_cell(zb, 'dynamic', 'seg', 'Dynamic', 76)]),
         ('', [_ops_cell('Polish By Groups', 'POLISH_GROUPS')]),
         ('', [_ops_cell('Check Mesh', 'CHECK_MESH'), _ops_cell('Fix Mesh', 'FIX_MESH')])],
        [('', [_ops_cell('Make PolyMesh3D', 'POLYMESH3D')]),
         ('DynaMesh', [_ops_cell('> SubDiv', 'DYNA_SUBDIV'), _ops_cell('> SubDiv Div3', 'DYNA_SUBDIV3')]),
         ('Export', [_ops_cell('OBJ', 'EXPORT_OBJ'), _ops_cell('STL', 'EXPORT_STL')]),
         ('FBX', [_ops_cell('Import', 'FBX_IMPORT'), _ops_cell('Export', 'FBX_EXPORT'),
                  _prop_cell(zb, 'fbx_scope', 'seg', 'Visible', 70, on=zb.fbx_scope == 'VISIBLE', value='VISIBLE'),
                  _prop_cell(zb, 'fbx_scope', 'seg', 'Selected', 80, on=zb.fbx_scope == 'SELECTED',
                             value='SELECTED')])],
    ]

    def gw(title, cells):
        return _cells_width(cells, k) + ((len(title) * 7 + 8) * k + GAP * k if title else 0.0)
    room = region_w - 40 * k
    wrapped = []
    for r in rows:                                   # too wide: the groups go on more lines (narrow screen)
        line, lw = [], 0.0
        for g in r:
            w = gw(*g)
            if line and lw + SEP * k + w > room - 2 * PAD * k:
                wrapped.append(line)
                line, lw = [], 0.0
            lw += (SEP * k if line else 0.0) + w
            line.append(g)
        if line:
            wrapped.append(line)
    rows = wrapped
    widths = [sum(gw(t, c) for t, c in r) + SEP * k * (len(r) - 1) for r in rows]
    from . import ui_bars
    bw = max(widths) + 2 * PAD * k
    bh = len(rows) * ROW * k + GAP * k * (len(rows) - 1) + 2 * PAD * k
    x0 = (region_w - bw) / 2.0
    y0 = region_h - ui_bars.top_inset(context) - 10 * k - bh
    out = [Item('card', x0, y0, bw, bh)]
    y = y0 + bh - PAD * k - ROW * k
    for r, rw in zip(rows, widths):
        x = x0 + (bw - rw) / 2.0
        for gi, (title, cells) in enumerate(r):
            if gi:
                out.append(Item('vrule', x + SEP * k / 2, y + 5 * k, 1.0 * k, ROW * k - 10 * k))
                x += SEP * k
            if title:
                tw = (len(title) * 7 + 8) * k
                out.append(Item('glabel', x, y, tw, ROW * k, title.upper()))
                x += tw + GAP * k
            x = _cells_row(Item, out, cells, x, y, k) - GAP * k
        y -= ROW * k + GAP * k
    return out, y0


def _scroll_card(Item, rows, h, x0, top, w, floor, k, scroll):
    view = max(0.0, min(h, top - floor - 2 * PAD * k))
    scroll = max(0.0, min(scroll, h - view))
    out = [Item('card', x0, top - view - 2 * PAD * k, w, view + 2 * PAD * k)]
    y_top = top - PAD * k
    cy = y_top - view
    for it in rows:
        it.y += y_top + scroll
        if it.kind == 'sbg':
            lo, hi = max(it.y, cy), min(it.y + it.h, y_top)
            if hi - lo < 2 * k:
                continue
            it.y, it.h = lo, hi - lo
        elif it.y < cy - 0.5 or it.y + it.h > y_top + 0.5:
            continue
        out.append(it)
    if h > view + 1:
        bar_h = max(30 * k, view * view / h)
        bar_y = y_top - bar_h - (view - bar_h) * (scroll / max(1e-6, h - view))
        out.append(Item('sbar', x0 + w - 6 * k, bar_y, 3 * k, bar_h))
    return out, h, view


def shelf_a(context, region_w, region_h, k, Item, top, floor):
    x0 = 12 * k
    rows, h = _shelf_rows(context, x0 + PAD * k, A_W * k - 2 * PAD * k, k)
    scroll = float(getattr(context.window_manager, 'mch_zb_scroll', 0.0))
    out, h, view = _scroll_card(Item, rows, h, x0, top, A_W * k, floor, k, scroll)
    return out


def shelf_b(context, k, Item, top):
    zb = context.scene.mch_zb
    b = zs.brush(context)
    x0, w = 12 * k + A_W * k + 8 * k, B_W * k
    iw = w - 2 * PAD * k
    out = []
    y = top - PAD * k
    tool = zs._tool_id(context)

    def tile(label, icon, action, h=72.0, on=False):
        nonlocal y
        y -= h * k
        out.append(Item('sbtn', x0 + PAD * k, y, iw, h * k, label, icon, on, True, action, 'RIGHT'))
        y -= GAP * k

    def head(text):
        nonlocal y
        y -= 18 * k
        out.append(Item('glabel', x0 + PAD * k, y, iw, 18 * k, text))

    def row(cells):
        nonlocal y
        y -= ROW * k
        n = len(cells)
        cw = (iw - GAP * k * (n - 1)) / n
        for i, c in enumerate(cells):
            out.append(Item(c['kind'], x0 + PAD * k + i * (cw + GAP * k), y, cw, ROW * k, c['label'], '',
                            c.get('on', False), True, c['action'], c.get('data'), c.get('prop', '')))
        y -= GAP * k
    name = zs.zb_name(b)
    tile(name or 'Brush', 'png:' + zs.icon_stem(b.name) if b is not None else '',
         ('op', 'mch.zb_brush_pick', {}), 78.0)
    head('STROKE')
    row([_prop_cell(zb, 'stroke', 'drop')])
    head('MATERIAL')
    row([_prop_cell(zb, 'matcap', 'drop')])
    head('COLOR')
    row([_ops_cell('SwitchColor', 'SWITCH_COLOR')])
    row([_ops_cell('FillColor', 'FILL_COLOR')])
    head('SYMMETRY')
    row([_prop_cell(zb, 'sym_x', 'seg', '>X<'), _prop_cell(zb, 'sym_y', 'seg', '>Y<'),
         _prop_cell(zb, 'sym_z', 'seg', '>Z<')])
    row([_prop_cell(zb, 'radial', 'seg', '(R)')])
    row([_prop_cell(zb, 'radial_count', 'mini', 'Radial')])
    head('CLIP / TRIM')
    tile('ClipCurve', 'png:cut', ('op', 'mch.zb_action', {'action': 'CLIP_CURVE'}), 52.0,
         tool == 'builtin.line_project')
    tile('TrimCurve', 'png:hide', ('op', 'mch.zb_action', {'action': 'TRIM_CURVE'}), 52.0, tool == 'builtin.line_trim')
    tile('TrimLasso', 'png:lasso', ('op', 'mch.zb_action', {'action': 'TRIM_LASSO'}), 52.0,
         tool == 'builtin.lasso_trim')
    head('INITIALIZE')
    row([_ops_cell('QCube', 'QCUBE'), _ops_cell('QGrid', 'QGRID')])
    row([_prop_cell(zb, 'res', 'mini', 'Res')])
    row([_ops_cell('Delete', 'DELETE')])
    h = top - y + PAD * k
    return [Item('card', x0, top - h, w, h)] + out


VIEW_SHELF = (('Persp', 'persp', 'isolate', None), ('Floor', 'floor', 'grid', None), ('Frame', None, 'isolate', 'FRAME'),
              ('Move', None, 'arrow', ('viewdrag', 'PAN')), ('Zoom3D', None, 'origin', ('viewdrag', 'ZOOM')),
              ('Rotate', None, 'radial', ('viewdrag', 'ROTATE')), ('PolyF', 'polyf', 'quad', None),
              ('Transp', 'transp', 'card', None), ('Solo', None, 'eye', 'SOLO'))


def view_shelf(context, region_w, k, Item, top):
    zb = context.scene.mch_zb
    x0 = region_w - 12 * k - S_W * k - 8 * k - V_W * k
    w = V_W * k
    out = []
    y = top - PAD * k
    for label, prop, icon, act in VIEW_SHELF:
        y -= 54 * k
        if prop:
            action, on, data = ('bool',), bool(getattr(zb, prop)), zb
        elif isinstance(act, tuple):
            action, on, data = ('op', 'mch.zb_viewdrag', {'mode': act[1]}), False, None
        else:
            action, on, data = ('op', 'mch.zb_action', {'action': act}), False, None
        out.append(Item('sbtn', x0 + 5 * k, y, w - 10 * k, 54 * k, label, icon, on, True, action, data, prop or ''))
        y -= GAP * k
    for label, action in (('Groups Split', 'GROUPS_SPLIT'), ('Auto Groups', 'AUTO_GROUPS'),
                          ('MergeDown', 'MERGE_DOWN'), ('MergeVisible', 'MERGE_VISIBLE')):
        y -= ROW * k
        out.append(Item('tbtn', x0 + 4 * k, y, w - 8 * k, ROW * k, label, '', False, True,
                        ('op', 'mch.zb_action', {'action': action})))
        y -= GAP * k
    h = top - y + PAD * k
    return [Item('card', x0, top - h, w, h)] + out


def _points(context, ob):
    try:
        return len(ob.evaluated_get(context.evaluated_depsgraph_get()).data.vertices)
    except (RuntimeError, ReferenceError, AttributeError):
        return 0


def subtool_list(context, region_w, k, Item, top, floor):
    from . import layers_panel
    x0 = region_w - 12 * k - S_W * k
    w, iw = S_W * k, S_W * k - 2 * PAD * k
    ix = x0 + PAD * k
    out = []
    y = top - PAD * k
    y -= 34 * k
    out.append(Item('phead', ix, y, iw - 34 * k, 34 * k, 'SUBTOOL', 'stack', False, True, None))
    try:
        from . import point_counts
        act, tot = point_counts(context)
    except (ImportError, RuntimeError, AttributeError):
        act = tot = 0
    y -= 18 * k + GAP * k
    out.append(Item('pnote', ix, y, iw, 18 * k, f'Active Points {act:,}   Total Points {tot:,}', '', False, True))
    y -= GAP * k
    active = context.active_object
    meshes = [o for o in sorted(context.view_layer.objects, key=lambda o: o.name.lower())
              if o.type == 'MESH' and layers_panel.listed(o)]
    room = int(max(1, (y - floor - 4 * (ROW + GAP) * k - 30 * k) // ((26 + 2) * k)))
    for ob in meshes[:room]:
        y -= 26 * k
        hidden = layers_panel._hidden(context, ob)
        out.append(Item('lrow', ix, y, iw - 28 * k, 26 * k, ob.name, 'cube', ob == active, True,
                        ('op', 'mch.zb_subtool', {'name': ob.name}),
                        {'hidden': hidden, 'badge': f'{_points(context, ob):,}', 'active': ob == active}))
        out.append(Item('pmin', ix + iw - 24 * k, y + 1 * k, 24 * k, 24 * k, 'Show' if hidden else 'Hide',
                        'eye_off' if hidden else 'eye', False, True, ('op', 'mch.layer_eye', {'name': ob.name}),
                        'LEFT'))
        y -= 2 * k
    if len(meshes) > room:
        y -= 17 * k
        out.append(Item('pnote', ix, y, iw, 17 * k, f'+ {len(meshes) - room} more', '', False, True))
    y -= GAP * k
    for a, b in ((('All Low', 'ALL_LOW'), ('All High', 'ALL_HIGH')), (('Duplicate', 'DUPLICATE'), ('Delete', 'DELETE')),
                 (('Split Hidden', 'SPLIT_HIDDEN'), ('Groups Split', 'GROUPS_SPLIT'))):
        y -= ROW * k
        cw = (iw - GAP * k) / 2
        for i, (label, action) in enumerate((a, b)):
            out.append(Item('tbtn', ix + i * (cw + GAP * k), y, cw, ROW * k, label, '', False, True,
                            ('op', 'mch.zb_action', {'action': action})))
        y -= GAP * k
    h = top - y + PAD * k
    return [Item('card', x0, top - h, w, h)] + out


def brush_shelf(context, region_w, k, Item):
    b = zs.brush(context)
    cur = zs.zb_name(b)
    groups = [list(zs.SHELF[0]), ['IMM', 'APPEND'], list(zs.SHELF[1]), ['SPLIT_HIDDEN', 'AUTO_GROUPS']]
    cols = [5, 1, 4, 1]
    tw, th, gap, sep, pad = TILE_W * k, TILE_H * k, GAP * k, SEP * k, PAD * k
    width = sum(c * tw + (c - 1) * gap for c in cols) + sep * (len(groups) - 1) + 2 * pad
    height = 2 * th + gap + 2 * pad
    x0, y0 = (region_w - width) / 2.0, 8 * k
    out = [Item('card', x0, y0, width, height)]
    x = x0 + pad
    special = {'IMM': ('IMM Primitives', 'png:primitive', ('menu', 'MCH_MT_zb_imm')),
               'APPEND': ('Append', 'png:assets', ('op', 'mch.zb_append', {'kind': 'SPHERE'})),
               'SPLIT_HIDDEN': ('Split Hidden', 'ungroup', ('op', 'mch.zb_action', {'action': 'SPLIT_HIDDEN'})),
               'AUTO_GROUPS': ('Auto Groups', 'select_group', ('op', 'mch.zb_action', {'action': 'AUTO_GROUPS'}))}
    for gi, (names, n) in enumerate(zip(groups, cols)):
        if gi:
            out.append(Item('vrule', x - sep / 2, y0 + pad + 4 * k, 1.0 * k, height - 2 * pad - 8 * k))
        for j, name in enumerate(names):
            c, r = j % n, j // n
            tx, ty = x + c * (tw + gap), y0 + height - pad - (r + 1) * th - r * gap
            if name in special:
                label, icon, action = special[name]
                out.append(Item('sbtn', tx, ty, tw, th, label, icon, False, True, action, 'ABOVE'))
                continue
            _z, bl, code = zs.BY_Z[name]
            out.append(Item('sbtn', tx, ty, tw, th, name, 'png:' + zs.icon_stem(bl), name == cur, True,
                            ('op', 'mch.zb_brush', {'name': name}), 'ABOVE'))
            out.append(Item('keycap', tx + tw - 18 * k, ty + th - 11 * k, 16 * k, 10 * k, code))
        x += n * tw + (n - 1) * gap + sep
    return out, y0 + height


KEYS_TEXT = ('ZBRUSH KEYS', 'Drag canvas   rotate, Shift: snap', 'Alt + drag canvas   move, let Alt go: zoom',
             'Alt / Shift   Zsub / Smooth', 'Ctrl + drag model   MaskPen, Alt: unmask', 'Ctrl + click canvas   invert mask',
             'Ctrl + drag canvas   mask lasso', 'Ctrl+Shift   show only / polygroup', 'S / U / O   Size / Intensity / Focal',
             'Space / B   menu / brushes (B S T)', 'X   symmetry', 'D / Shift+D   SDiv up / down',
             'Ctrl+D / Ctrl+W   Divide / polygroup', 'F / Shift+F   Frame / PolyF')


def key_legend(context, k, Item, x0, y0):
    from .workspace_ui import pref
    if not pref('key_legend', True):
        return []
    lh, w = 17 * k, A_W * k
    h = lh * len(KEYS_TEXT) + 12 * k
    out = [Item('card', x0, y0, w, h)]
    y = y0 + h - 7 * k
    for i, t in enumerate(KEYS_TEXT):
        y -= lh
        if i == 0:
            out.append(Item('glabel', x0 + 12 * k, y, w - 24 * k, lh, t))
            continue
        key, _s, what = t.partition('   ')
        out.append(Item('pnote', x0 + 10 * k, y + 1 * k, 118 * k, lh - 2 * k, key))
        out.append(Item('pnote', x0 + 130 * k, y + 1 * k, w - 138 * k, lh - 2 * k, what))
    return out


def popup(context, region_w, region_h, k, Item):
    wm = context.window_manager
    kind = getattr(wm, 'mch_zb_pop', '')
    if not kind:
        return []
    mx, my = wm.mch_zb_pop_xy
    zb = context.scene.mch_zb
    out = []
    if kind == 'BRUSH':
        typed = wm.mch_zb_pop_focus
        cols = 6
        tw, th = 70 * k, 56 * k
        rows = (len(zs.BRUSHES) + cols - 1) // cols
        w = cols * tw + (cols - 1) * GAP * k + 2 * PAD * k
        h = rows * th + (rows - 1) * GAP * k + 2 * PAD * k + 22 * k
        x0 = min(max(8 * k, mx - w / 2), region_w - w - 8 * k)
        y0 = min(max(8 * k, my - h / 2), region_h - h - 8 * k)
        out.append(Item('card', x0, y0, w, h))
        out.append(Item('glabel', x0 + PAD * k, y0 + h - PAD * k - 16 * k, w, 16 * k,
                        'B  ' + ' '.join(typed) + ('   (type the letters)' if not typed else '')))
        cur = zs.zb_name(zs.brush(context))
        for i, (z, bl, code) in enumerate(zs.BRUSHES):
            c, r = i % cols, i // cols
            tx = x0 + PAD * k + c * (tw + GAP * k)
            ty = y0 + h - PAD * k - 22 * k - (r + 1) * th - r * GAP * k
            ok = code.startswith(typed) if typed else True
            out.append(Item('sbtn', tx, ty, tw, th, z, 'png:' + zs.icon_stem(bl), z == cur, ok,
                            ('op', 'mch.zb_brush', {'name': z}), 'ABOVE'))
            out.append(Item('keycap', tx + tw - 18 * k, ty + th - 11 * k, 16 * k, 10 * k, code))
        return out
    w = 330 * k
    bars = ('draw_size', 'focal_shift', 'z_intensity')
    h = PAD * k * 2 + 3 * (28 + GAP) * k + (ROW + GAP) * k + 46 * k
    focus = wm.mch_zb_pop_focus
    x0 = mx - w / 2
    y0 = my - h + PAD * k + 14 * k
    if focus in bars:                                # the bar asked for under the mouse
        y0 = my - (h - PAD * k - (bars.index(focus) + 0.5) * (28 + GAP) * k)
    x0 = min(max(8 * k, x0), region_w - w - 8 * k)
    y0 = min(max(8 * k, y0), region_h - h - 8 * k)
    out.append(Item('card', x0, y0, w, h))
    y = y0 + h - PAD * k
    for p in bars:
        y -= 28 * k
        out.append(Item('mini', x0 + PAD * k, y, w - 2 * PAD * k, 28 * k, '', '', p == focus, True, ('number',), zb, p))
        y -= GAP * k
    y -= ROW * k
    iw = w - 2 * PAD * k
    cw = (iw - 2 * GAP * k) / 3
    out.append(Item('seg', x0 + PAD * k, y, cw, ROW * k, 'Zadd', '', zb.zmode == 'ZADD', True, ('enum', 'ZADD'), zb,
                    'zmode'))
    out.append(Item('seg', x0 + PAD * k + cw + GAP * k, y, cw, ROW * k, 'Zsub', '', zb.zmode == 'ZSUB', True,
                    ('enum', 'ZSUB'), zb, 'zmode'))
    out.append(Item('drop', x0 + PAD * k + 2 * (cw + GAP * k), y, cw, ROW * k, '', '', False, True, ('menu_enum',),
                    zb, 'stroke'))
    y -= GAP * k + 46 * k
    recent = (zs.RECENT + [z for z in zs.SHELF[0] if z not in zs.RECENT])[:6]
    tw = (iw - 5 * GAP * k) / 6
    cur = zs.zb_name(zs.brush(context))
    for i, z in enumerate(recent):
        out.append(Item('sbtn', x0 + PAD * k + i * (tw + GAP * k), y, tw, 46 * k, z,
                        'png:' + zs.icon_stem(zs.BY_Z[z][1]), z == cur, True, ('op', 'mch.zb_brush', {'name': z}),
                        'ABOVE'))
    return out


def items(context, region_w, region_h, k=1.0):
    """Every card of the ZBrush screen (Mecha Menu Items, region px)."""
    from .mecha_menu import Item
    out = []
    shelf, shelf_top = brush_shelf(context, region_w, k, Item)
    top_items, top_y0 = top_shelf(context, region_w, region_h, k, Item)
    try:                                             # ZBrush's point counts, top left under the top shelf
        from . import point_counts
        act, tot = point_counts(context)
        yt = top_y0 - 20 * k
        out.append(Item('pnote', 14 * k, yt, 300 * k, 16 * k, f'Active Points Count  {act:,}'))
        out.append(Item('pnote', 14 * k, yt - 17 * k, 300 * k, 16 * k, f'Total Points Count  {tot:,}'))
    except (ImportError, RuntimeError, AttributeError):
        top_y0 = region_h
    top = min(region_h - TOP_MARGIN * k, top_y0 - 50 * k)
    legend = key_legend(context, k, Item, 12 * k, 8 * k)
    floor = (legend[0].y + legend[0].h if legend else shelf_top) + 10 * k
    out += top_items
    out += shelf_a(context, region_w, region_h, k, Item, top, floor)
    out += shelf_b(context, k, Item, top)
    out += view_shelf(context, region_w, k, Item, top)
    out += subtool_list(context, region_w, k, Item, top, shelf_top + 10 * k)
    out += shelf
    out += legend
    out += popup(context, region_w, region_h, k, Item)
    return out


def scroll_by(context, region_w, region_h, k, dy):
    wm = context.window_manager
    wm.mch_zb_scroll = max(0.0, float(wm.mch_zb_scroll) + dy)
    from . import ui_bars
    ui_bars.bump()


def over_shelf(context, x, y):
    """Is region point (x, y) on the left (scrolling) shelf?"""
    from .ui_gpu import ui_factor
    region = getattr(context, 'region', None)
    if region is None or not zs.on(context):
        return False
    k = ui_factor(context, region)
    return 12 * k <= x <= 12 * k + A_W * k and y < region.height - TOP_MARGIN * k


class MCH_MT_zb_imm(bpy.types.Menu):
    bl_idname = 'MCH_MT_zb_imm'
    bl_label = 'IMM Primitives'

    def draw(self, context):
        for kind, name in zs.PRIMITIVES:
            self.layout.operator('mch.zb_append', text=name).kind = kind


CLASSES = (MCH_MT_zb_imm,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
