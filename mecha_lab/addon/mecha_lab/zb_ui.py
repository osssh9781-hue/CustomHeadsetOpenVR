"""0.24.60 The ZBrush-style sculpt screen, drawn in the Mecha look with an orange accent (the user's ZBrush custom UI):

    top shelf      Edit Draw | Move Scale Rotate | Material | Zadd Zsub | Z Intensity  Focal Shift  Draw Size Dynamic
                   | Polish By Groups | Check Mesh Fix Mesh  /  Make PolyMesh3D | DynaMesh > SubDiv | OBJ STL | FBX
    left shelf     SubTool / Geometry / Masking / Stroke / Decimation / Quad Remesh / Edge Mesh / Hard Edges (the
                   Blender-layout drawer ``draw_tool_shelf`` read by panel_capture, like the side panel), then
                   brush / stroke / material / colour / symmetry / clip / initialize
    right          view shelf (Persp Floor Frame Move Zoom3D Rotate PolyF Transp Solo ...) and the SubTool list
    bottom         the brush shelf (Blender brushes, ZBrush names), IMM Primitives / Append, subtool buttons
    at the cursor  Space / S / U / O / right-click menu, B brushes
Clicks go through ``ui_bars`` (hit test / run) like the rest of the drawn UI.
"""
from __future__ import annotations

import os

import bpy

from . import panel_capture as pc
from . import zb_sculpt as zs
from .quick_hud import points_text

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
    r.operator('mch.zb_action', text='DynaMesh', depress=zs.dynamesh_on(context.active_object)).action = 'DYNAMESH'
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
    r.prop(zb, 'cavity_inv', toggle=True)
    r = box.row()
    r.prop(zb, 'cavity_int')
    r.prop(zb, 'blur')
    ops(box.row(), ('Invert', 'MASK_INVERT'), ('Clear', 'MASK_CLEAR'), ('Blur', 'MASK_BLUR'))
    box.prop(zb, 'cavity_auto', toggle=True)
    box = layout.box()
    box.label(text='Stroke')
    r = box.row()
    r.prop(zb, 'double', toggle=True)
    r.prop(zb, 'lazy_mouse', toggle=True)
    r = box.row()
    r.prop(zb, 'accu', toggle=True)
    r.prop(zb, 'pressure', text='')
    r = box.row()
    r.prop(zb, 'lazy_step')
    r.prop(zb, 'lazy_smooth')
    box.prop(zb, 'lazy_radius')
    box = layout.box()
    box.label(text='Decimation')
    r = box.row()
    ops(r, ('Decimate Current', 'DECIMATE'))
    r.prop(zb, 'decimate', text='%')
    r = box.row()
    r.prop(zb, 'dec_even', toggle=True)
    r.prop(zb, 'dec_quads', toggle=True)
    r = box.row()
    r.prop(zb, 'dec_mask', toggle=True)
    r.prop(zb, 'dec_groups', toggle=True)
    r.prop(zb, 'dec_borders', toggle=True)
    box = layout.box()
    box.label(text='Quad Remesh')
    r = box.row()
    ops(r, ('Quad Remesh', 'QUAD_REMESH'))
    r.prop(zb, 'qr_target', text='Target')
    box.row().prop(zb, 'qr_mode', expand=True)
    box.prop(zb, 'qr_angle')
    ops(box.row(), ('Half', 'QR_HALF'), ('Same', 'QR_SAME'), ('Double', 'QR_DOUBLE'))
    box = layout.box()
    box.label(text='Edge Mesh')
    r = box.row()
    ops(r, ('Edge Mesh', 'EDGE_MESH'))
    r.prop(zb, 'em_detail')
    r = box.row()
    r.prop(zb, 'em_auto', toggle=True)
    r.prop(zb, 'em_tolerance')
    r = box.row()
    r.prop(zb, 'em_adaptive', toggle=True)
    r.prop(zb, 'em_straight', toggle=True)
    r = box.row()
    r.prop(zb, 'he_fit', toggle=True)
    r.prop(zb, 'he_match', toggle=True)
    ops(box.row(), ('Half', 'EM_HALF'), ('Double', 'EM_DOUBLE'))
    box = layout.box()
    box.label(text='Hard Edges')
    r = box.row()
    ops(r, ('Find Edges', 'HE_FIND'))
    r.prop(zb, 'he_angle')
    r = box.row()
    r.prop(zb, 'he_merge', toggle=True)
    r.prop(zb, 'he_crease', toggle=True)
    r.prop(zb, 'he_outer', toggle=True)
    r = box.row()
    r.prop(zb, 'he_bevel', toggle=True)
    r.prop(zb, 'he_width')
    box.row().prop(zb, 'he_style', expand=True)
    r = box.row()
    r.prop(zb, 'he_segments')
    r.prop(zb, 'he_profile')
    r = box.row()
    r.prop(zb, 'he_subdiv')
    r.prop(zb, 'he_client', toggle=True)
    box.prop(zb, 'he_normals', toggle=True)
    ops(box.row(), ('Apply', 'HE_APPLY'), ('Clear', 'HE_CLEAR'))


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


def _matcap_name(context, zb):
    try:
        cur = zb.matcap
    except (TypeError, AttributeError):
        return 'Material'
    return next((n for i, n, _p in zs.matcaps(context) if i == cur), 'Material')


def top_shelf(context, region_w, region_h, k, Item):
    zb = context.scene.mch_zb
    tool = zs._tool_id(context)
    rows = [
        [('', [_ops_cell('Edit', 'EDIT', True, 'seg'), _ops_cell('Draw', 'DRAW', tool == 'builtin.brush', 'seg')]),
         ('', [_ops_cell('Move', 'MOVE', tool == 'builtin.move', 'seg'),
               _ops_cell('Scale', 'SCALE', tool == 'builtin.scale', 'seg'),
               _ops_cell('Rotate', 'ROTATE', tool == 'builtin.rotate', 'seg')]),
         ('Mat', [{'kind': 'tbtn', 'label': _matcap_name(context, zb), 'width': 120,
                   'action': ('op', 'mch.zb_popup', {'kind': 'MATERIAL'})}]),
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
    room = region_w - 2 * corner_reserve(context, region_w, region_h, k) - 16 * k
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
    for r, rw in zip(rows, widths):          # (the corner card sits right of it)
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
    _MAX['mch_zb_scroll'] = max(0.0, h - view)
    return out


def _safe_matcap(zb):
    try:
        return zb.matcap
    except (TypeError, AttributeError):
        return ''


def shelf_b(context, k, Item, top, floor=0.0):
    """The brush tray (brush / alpha / stroke / material / texture, symmetry, clip, initialize); 0.24.60 it scrolls
    when the viewport is too short for it (mouse wheel over it)."""
    zb = context.scene.mch_zb
    b = zs.brush(context)
    x0, w = 12 * k + A_W * k + 8 * k, B_W * k
    iw = w - 2 * PAD * k
    out = []
    y = 0.0                                          # (rows from 0 down; _scroll_card puts them under ``top``)
    tool = zs._tool_id(context)

    def tile(label, icon, action, h=72.0, on=False):
        nonlocal y
        y -= h * k
        out.append(Item('sbtn', x0 + PAD * k, y, iw, h * k, label, icon, on, True, action, 'RIGHT'))
        y -= GAP * k

    def pair(a, b, h):                               # two half tiles side by side: (label, icon, action)
        nonlocal y
        y -= h * k
        hw = (iw - GAP * k) / 2
        for i, (label, icon, action) in enumerate((a, b)):
            out.append(Item('sbtn', x0 + PAD * k + i * (hw + GAP * k), y, hw, h * k, label, icon, False, True, action,
                            'RIGHT'))
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
    ap = zs.current_alpha(context)                   # 0.24.60 the alpha / texture (click: ZBrush's pickers)
    tp = zs.current_texture(context)
    pair((os.path.splitext(os.path.basename(ap))[0] if ap else 'Alpha Off', ('alpha:' + ap) if ap else 'card',
          ('op', 'mch.zb_popup', {'kind': 'ALPHA'})),
         (os.path.splitext(os.path.basename(tp))[0] if tp else 'Texture Off', ('alpha:' + tp) if tp else 'card',
          ('op', 'mch.zb_popup', {'kind': 'TEXTURE'})), 60.0)
    flips = [{'kind': 'tbtn', 'label': lab, 'action': ('op', 'mch.zb_alpha_edit', {'action': act})}
             for lab, act in (('Flh', 'FLIP_H'), ('Flv', 'FLIP_V'), ('Rot', 'ROTATE'), ('Invr', 'INVERT'))]
    row(flips[:2])
    row(flips[2:])
    row([_prop_cell(zb, 'alpha_directional', 'seg', 'Directional')])   # 0.24.65 the alpha follows the stroke
    st = zb.stroke                                   # Stroke / Material: tiles that open ZBrush's pickers
    mc = next(((n, p) for i, n, p in zs.matcaps(context) if i == _safe_matcap(zb)), ('Material', ''))
    pair((dict((k_, n) for k_, n, _b in zs.STROKES).get(st, 'Stroke'), zs.stroke_icon(st),
          ('op', 'mch.zb_popup', {'kind': 'STROKE'})),
         (mc[0], ('alpha:' + mc[1]) if mc[1] else 'card', ('op', 'mch.zb_popup', {'kind': 'MATERIAL'})), 56.0)
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
    scroll = float(getattr(context.window_manager, 'mch_zb_scroll_b', 0.0))
    out, h, view = _scroll_card(Item, out, -y, x0, top, w, floor, k, scroll)
    _MAX['mch_zb_scroll_b'] = max(0.0, h - view)
    return out


VIEW_SHELF = (('Persp', 'persp', 'isolate', None), ('Floor', 'floor', 'grid', None), ('Frame', None, 'isolate', 'FRAME'),
              ('Move', None, 'arrow', ('viewdrag', 'PAN')), ('Zoom3D', None, 'origin', ('viewdrag', 'ZOOM')),
              ('Rotate', None, 'radial', ('viewdrag', 'ROTATE')), ('Z Up', 'rot_zup', 'axes', None),
              ('PolyF', 'polyf', 'quad', None),
              ('Transp', 'transp', 'card', None), ('Solo', None, 'eye', 'SOLO'), ('HiPoly', 'highpoly', 'lowpoly', None))


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
    zb = context.scene.mch_zb
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
    out.append(Item('pnote', ix, y, iw, 18 * k, f'Active Points {points_text(act)}   Total Points {points_text(tot)}',
                    '', False, True))
    y -= GAP * k
    active = context.active_object
    if zb.highpoly:                                  # 0.24.61 High Poly Mode: what still weighs on this SubTool
        from . import zb_highpoly
        notes = zb_highpoly.heavy(active)
        for t in (['High Poly Mode on'] + notes[:3]):
            y -= 16 * k
            out.append(Item('pnote', ix, y, iw, 16 * k, t, '', False, True))
        y -= GAP * k
    meshes = [o for o in sorted(context.view_layer.objects, key=lambda o: o.name.lower())
              if o.type == 'MESH' and layers_panel.listed(o)]
    room = int(max(1, (y - floor - 4 * (ROW + GAP) * k - 30 * k) // ((26 + 2) * k)))
    for ob in meshes[:room]:
        y -= 26 * k
        hidden = layers_panel._hidden(context, ob)
        out.append(Item('lrow', ix, y, iw - 28 * k, 26 * k, ob.name, 'cube', ob == active, True,
                        ('op', 'mch.zb_subtool', {'name': ob.name}),
                        {'hidden': hidden, 'badge': points_text(_points(context, ob)), 'active': ob == active}))
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
             'Right drag (pen button)   rotate anywhere, Alt: move',
             'Alt / Shift   Zsub / Smooth', 'Ctrl + drag model   MaskPen, Alt: unmask', 'Ctrl + click canvas   invert mask',
             'Ctrl + lasso model   mask, Alt: unmask', 'Ctrl + drag canvas   clear mask / DynaMesh',
             'Alt + click SubTool   pick it', 'Ctrl+Shift   show only / polygroup', 'S / U / O   Size / Intensity / Focal',
             'Space / B   menu / brushes (B S T)', 'X   symmetry', 'D / Shift+D   SDiv up / Duplicate',
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


def _place(mx, my, w, h, region_w, region_h, k):
    """A picker card round the mouse, kept inside the viewport."""
    return (min(max(8 * k, mx - w / 2), region_w - w - 8 * k), min(max(8 * k, my - h / 2), region_h - h - 8 * k))


def _image_picker(context, kind, mx, my, region_w, region_h, k, Item):
    """ZBrush's Alpha / Texture picker: where from (Mecha / ZBrush / Folder...), Off, a thumbnail per image."""
    import os
    zb = context.scene.mch_zb
    alpha = kind == 'ALPHA'
    files, total = zs.alpha_files(context) if alpha else zs.texture_files(context)
    cur = zs.current_alpha(context) if alpha else zs.current_texture(context)
    src, prop = (zb.alpha_source, 'alpha_source') if alpha else (zb.tex_source, 'tex_source')
    pick = 'mch.zb_alpha' if alpha else 'mch.zb_texture'
    cols, tw = 7, 64 * k
    rows = max(1, (len(files) + cols - 1) // cols)
    extra = 0.0 if alpha else (28 + GAP) * k        # (Texture: the Rgb Intensity bar)
    w = cols * tw + (cols - 1) * GAP * k + 2 * PAD * k
    h = rows * tw + (rows - 1) * GAP * k + 2 * PAD * k + (ROW + GAP) * k + 20 * k + extra
    x0, y0 = _place(mx, my, w, h, region_w, region_h, k)
    out = [Item('card', x0, y0, w, h)]
    y = y0 + h - PAD * k - ROW * k
    cells = [('Mecha', ('enum', 'MECHA'), src == 'MECHA', zb, prop)]
    if (zs.zbrush_alpha_dir() if alpha else zs.zbrush_texture_dir()):
        cells.append(('ZBrush', ('enum', 'ZBRUSH'), src == 'ZBRUSH', zb, prop))
    cells.append(('Folder...', ('op', 'mch.zb_alpha_folder' if alpha else 'mch.zb_texture_folder', {}),
                  src == 'FOLDER', None, ''))
    cells.append(('Alpha Off' if alpha else 'Texture Off', ('op', pick, {'path': ''}), not cur, None, ''))
    old = len(zs.old_copies()) if alpha else 0
    if old:                                          # 0.24.65 the brush copies 0.24.60 - 0.24.62 left behind
        cells.append((f'Clean {old} old', ('op', 'mch.zb_action', {'action': 'CLEAN_COPIES'}), False, None, ''))
    cw = (w - 2 * PAD * k - GAP * k * (len(cells) - 1)) / len(cells)
    for i, (lab, act, on, data, prp) in enumerate(cells):
        out.append(Item('seg', x0 + PAD * k + i * (cw + GAP * k), y, cw, ROW * k, lab, '', on, True, act, data, prp))
    if not alpha:
        y -= (28 + GAP) * k
        out.append(Item('mini', x0 + PAD * k, y, w - 2 * PAD * k, 28 * k, '', '', False, True, ('number',), zb,
                        'rgb_int'))
    y -= 20 * k
    folder = zs.alpha_folder(context) if alpha else zs.texture_folder(context)
    note = folder + (f'   (first {len(files)} of {total})' if total > len(files) else '')
    if not alpha:
        note = 'Paint + drag on the model: stamp (size / turn)   ' + note
    out.append(Item('pnote', x0 + PAD * k, y + 2 * k, w - 2 * PAD * k, 16 * k, note))
    for i, path in enumerate(files):
        c, r = i % cols, i // cols
        tx = x0 + PAD * k + c * (tw + GAP * k)
        ty = y - GAP * k - (r + 1) * tw - r * GAP * k
        out.append(Item('sbtn', tx, ty, tw, tw, os.path.splitext(os.path.basename(path))[0], 'alpha:' + path,
                        os.path.normcase(path) == os.path.normcase(cur), True, ('op', pick, {'path': path}), 'ABOVE'))
    return out


def popup(context, region_w, region_h, k, Item):
    wm = context.window_manager
    kind = getattr(wm, 'mch_zb_pop', '')
    if not kind:
        return []
    mx, my = wm.mch_zb_pop_xy
    zb = context.scene.mch_zb
    out = []
    if kind in {'ALPHA', 'TEXTURE'}:
        return _image_picker(context, kind, mx, my, region_w, region_h, k, Item)
    if kind == 'MATERIAL':
        caps = zs.matcaps(context)
        cur = _safe_matcap(zb)
        cols, tw = 8, 58 * k
        rows = max(1, (len(caps) + cols - 1) // cols)
        w = cols * tw + (cols - 1) * GAP * k + 2 * PAD * k
        h = rows * (tw + 14 * k) + (rows - 1) * GAP * k + 2 * PAD * k + 20 * k
        x0, y0 = _place(mx, my, w, h, region_w, region_h, k)
        out.append(Item('card', x0, y0, w, h))
        out.append(Item('glabel', x0 + PAD * k, y0 + h - PAD * k - 16 * k, w, 16 * k, 'MATERIAL  (MatCap)'))
        for i, (ident, name, path) in enumerate(caps):
            c, r = i % cols, i // cols
            tx = x0 + PAD * k + c * (tw + GAP * k)
            ty = y0 + h - PAD * k - 20 * k - (r + 1) * (tw + 14 * k) - r * GAP * k
            out.append(Item('sbtn', tx, ty, tw, tw + 14 * k, name, ('alpha:' + path) if path else 'card', ident == cur,
                            True, ('op', 'mch.zb_set', {'prop': 'matcap', 'value': ident}), 'ABOVE'))
        return out
    if kind == 'STROKE':
        cols, tw, th = len(zs.STROKES), 74 * k, 74 * k
        w = cols * tw + (cols - 1) * GAP * k + 2 * PAD * k
        h = th + 2 * PAD * k + 20 * k
        x0, y0 = _place(mx, my, w, h, region_w, region_h, k)
        out.append(Item('card', x0, y0, w, h))
        out.append(Item('glabel', x0 + PAD * k, y0 + h - PAD * k - 16 * k, w, 16 * k, 'STROKE'))
        for i, (key, name, _bl) in enumerate(zs.STROKES):
            tx = x0 + PAD * k + i * (tw + GAP * k)
            out.append(Item('sbtn', tx, y0 + PAD * k, tw, th, name, zs.stroke_icon(key), zb.stroke == key, True,
                            ('op', 'mch.zb_set', {'prop': 'stroke', 'value': key}), 'ABOVE'))
        return out
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
    out.append(Item('tbtn', x0 + PAD * k + 2 * (cw + GAP * k), y, cw, ROW * k,
                    dict((k_, n) for k_, n, _b in zs.STROKES).get(zb.stroke, 'Stroke'), '', False, True,
                    ('op', 'mch.zb_popup', {'kind': 'STROKE'})))
    y -= GAP * k + 46 * k
    recent = (zs.RECENT + [z for z in zs.SHELF[0] if z not in zs.RECENT])[:6]
    tw = (iw - 5 * GAP * k) / 6
    cur = zs.zb_name(zs.brush(context))
    for i, z in enumerate(recent):
        out.append(Item('sbtn', x0 + PAD * k + i * (tw + GAP * k), y, tw, 46 * k, z,
                        'png:' + zs.icon_stem(zs.BY_Z[z][1]), z == cur, True, ('op', 'mch.zb_brush', {'name': z}),
                        'ABOVE'))
    return out


_POP_SEEN = {'key': None, 'inside': False}
LEAVE_MARGIN = 24.0


def popup_leave(context, x, y):
    """0.24.60 ZBrush: the S / U / O / Space menu (and the brush / alpha pickers) close as soon as the mouse leaves
    the card - a little margin round it.  A card that opened away from the mouse (pushed in from the edge) waits
    until the mouse has been on it once, or has gone well away.  True when it closed."""
    wm = context.window_manager
    kind = getattr(wm, 'mch_zb_pop', '')
    region = getattr(context, 'region', None)
    if not kind or region is None:
        _POP_SEEN['key'] = None
        return False
    from .mecha_menu import Item
    from .ui_gpu import ui_factor
    k = ui_factor(context, region)
    cards = popup(context, region.width, region.height, k, Item)
    if not cards:
        return False
    c = cards[0]
    key = (kind, tuple(round(v) for v in wm.mch_zb_pop_xy))
    if _POP_SEEN['key'] != key:
        _POP_SEEN.update(key=key, inside=False)
    m = LEAVE_MARGIN * k
    inside = c.x - m <= x <= c.x + c.w + m and c.y - m <= y <= c.y + c.h + m
    if inside:
        _POP_SEEN['inside'] = True
        return False
    ox, oy = wm.mch_zb_pop_xy
    if not _POP_SEEN['inside'] and abs(x - ox) + abs(y - oy) < 120 * k:
        return False
    zs.close_popup(context)
    _POP_SEEN['key'] = None
    return True


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
        out.append(Item('pnote', 14 * k, yt, 300 * k, 16 * k, f'Active Points Count  {points_text(act)}'))
        out.append(Item('pnote', 14 * k, yt - 17 * k, 300 * k, 16 * k, f'Total Points Count  {points_text(tot)}'))
    except (ImportError, RuntimeError, AttributeError):
        top_y0 = region_h
    top = min(region_h - TOP_MARGIN * k, top_y0 - 50 * k)
    legend = key_legend(context, k, Item, 12 * k, 8 * k)
    floor = (legend[0].y + legend[0].h if legend else shelf_top) + 10 * k
    out += top_items
    out += shelf_a(context, region_w, region_h, k, Item, top, floor)
    out += shelf_b(context, k, Item, top, shelf_top + 10 * k)
    out += view_shelf(context, region_w, k, Item, top)
    out += subtool_list(context, region_w, k, Item, top, shelf_top + 10 * k)
    out += shelf
    out += legend
    out += corner_items(context, region_w, region_h, k)
    out += popup(context, region_w, region_h, k, Item)
    return out


CORNER_W, CORNER_SEG = 210.0, 99.0


def corner_box(context, region_w, region_h, k):
    """(x, y, w, h) of the MECHA LAB / ZBRUSH card in the top right corner (left of Blender's navigation gizmo
    and an overlapping sidebar)."""
    from . import ui_bars
    w, h = CORNER_W * k, 2 * ROW * k + GAP * k + 2 * PAD * k
    gizmo = 0.0
    try:
        prefs = context.preferences
        if getattr(context.space_data, 'show_gizmo', True) and getattr(context.space_data, 'show_gizmo_navigate',
                                                                       True):
            gizmo = (prefs.view.gizmo_size_navigate_v3d + 24.0) * prefs.system.ui_scale
    except AttributeError:
        gizmo = 104.0 * k
    inset = 0.0
    area = getattr(context, 'area', None)
    try:
        if area is not None and context.preferences.system.use_region_overlap:
            inset = sum(r.width for r in area.regions if r.type == 'UI' and r.width > 1)
    except AttributeError:
        pass
    x = region_w - inset - gizmo - 12 * k - w
    y = region_h - ui_bars.top_inset(context) - 10 * k - h
    return max(8 * k, x), y, w, h


def corner_reserve(context, region_w, region_h, k):
    """How much of the top right the card (and the gizmo beside it) takes - the top bars keep clear."""
    x, _y, _w, _h = corner_box(context, region_w, region_h, k)
    return region_w - x + 8 * k


def corner_items(context, region_w, region_h, k=1.0):
    """0.24.60 MECHA LAB | ZBRUSH (Object / Sculpt Mode) and STYLE ZBrush | Blender."""
    from .mecha_menu import Item
    x0, y0, w, h = corner_box(context, region_w, region_h, k)
    sculpt = getattr(context, 'mode', '') == 'SCULPT'
    st = zs.style()
    out = [Item('card', x0, y0, w, h)]
    y = y0 + h - PAD * k - ROW * k
    seg = (w - 2 * PAD * k - GAP * k) / 2
    out.append(Item('seg', x0 + PAD * k, y, seg, ROW * k, 'MECHA LAB', '', not sculpt, True,
                    ('op', 'mch.zb_switch', {'target': 'MECHA'})))
    out.append(Item('seg', x0 + PAD * k + seg + GAP * k, y, seg, ROW * k, 'ZBRUSH', '', sculpt, True,
                    ('op', 'mch.zb_switch', {'target': 'ZBRUSH'})))
    y -= ROW * k + GAP * k
    lw = 44 * k
    out.append(Item('glabel', x0 + PAD * k, y, lw, ROW * k, 'STYLE'))
    s2 = (w - 2 * PAD * k - lw - 2 * GAP * k) / 2
    out.append(Item('seg', x0 + PAD * k + lw + GAP * k, y, s2, ROW * k, 'ZBrush', '', st == 'ZBRUSH', True,
                    ('op', 'mch.zb_style', {'style': 'ZBRUSH'})))
    out.append(Item('seg', x0 + PAD * k + lw + 2 * GAP * k + s2, y, s2, ROW * k, 'Blender', '', st == 'BLENDER', True,
                    ('op', 'mch.zb_style', {'style': 'BLENDER'})))
    return out


_OVER = ['A']               # which tray the wheel is over (over_shelf -> scroll_by)
_MAX = {}                   # 0.24.73 how far each tray scrolls (set when drawn)


def scroll_by(context, region_w, region_h, k, dy):
    """Scroll the tray under the mouse by ``dy``.  0.24.73 kept inside its rows: the wheel used to run on past the
    end - the tray drew the last rows, but the value kept growing and scrolling back up seemed to do nothing for a
    while (the 'sometimes it doesn't scroll')."""
    wm = context.window_manager
    name = 'mch_zb_scroll_b' if _OVER[0] == 'B' else 'mch_zb_scroll'
    top = _MAX.get(name)
    cur = float(getattr(wm, name, 0.0))
    if top is not None:
        cur = min(cur, top)
    new = cur + dy
    setattr(wm, name, max(0.0, min(new, top) if top is not None else new))
    from . import ui_bars
    ui_bars.bump()


def over_shelf(context, x, y):
    """Is region point (x, y) on the left tray or the brush tray (both scroll)?"""
    from .ui_gpu import ui_factor
    region = getattr(context, 'region', None)
    if region is None or not zs.on(context):
        return False
    k = ui_factor(context, region)
    if y >= region.height - TOP_MARGIN * k:
        return False
    if 12 * k <= x <= 12 * k + A_W * k:
        _OVER[0] = 'A'
        return True
    bx = 12 * k + A_W * k + 8 * k
    if bx <= x <= bx + B_W * k:
        _OVER[0] = 'B'
        return True
    return False


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
