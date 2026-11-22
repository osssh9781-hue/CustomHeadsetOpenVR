"""0.24.286 Edge Clear (user: "내가 선택하는 영역의 엣지 크리즈를 클릭하면 지워지는 엣지 클리어도 만들어 줘") A click tool: the
creased (and sharp) edges of the part are shown; a click on one clears it - the whole line it belongs to (up to where
lines meet), Shift: only that one edge.  Its crease goes to 0 and (Also Sharp) its sharp mark off; the mesh does not
move.  One undo step a click.  The part: the one under the mouse, by the Target setting (Auto / Selected / Active)."""
from __future__ import annotations

import numpy as np

import bpy
from bpy.props import BoolProperty, PointerProperty

HOVER = {'part': None, 'edges': None}
PX = 16.0                       # how near the mouse (px) an edge must be on screen


class MCH_PG_EdgeClear(bpy.types.PropertyGroup):
    whole: BoolProperty(name='Whole Line', default=True,
                        description='Edge Clear: a click clears the whole creased line (up to where lines meet); '
                                    'off: only the edge clicked (Shift does the other)')
    sharp: BoolProperty(name='Also Sharp', default=True,
                        description='Edge Clear: the sharp mark of those edges off too (not only the crease)')


def marked(me):
    """Bool per edge: creased (> 0) or marked sharp."""
    n = len(me.edges)
    out = np.zeros(n, bool)
    a = me.attributes.get('crease_edge')
    if a is not None and a.domain == 'EDGE':
        v = np.empty(n, np.float32)
        a.data.foreach_get('value', v)
        out |= v > 1e-4
    a = me.attributes.get('sharp_edge')
    if a is not None and a.domain == 'EDGE':
        v = np.zeros(n, bool)
        a.data.foreach_get('value', v)
        out |= v
    return out


def edge_verts(me):
    ev = np.empty(len(me.edges) * 2, np.int64)
    me.edges.foreach_get('vertices', ev)
    return ev.reshape(-1, 2)


def line_of(me, e, mark=None):
    """The marked edges joined to edge ``e`` through points where exactly two marked edges meet (a crease line, up
    to its corners / ends)."""
    mark = marked(me) if mark is None else mark
    if not mark[e]:
        return [e]
    E = edge_verts(me)
    ids = np.nonzero(mark)[0]
    by_vert = {}
    for k in ids.tolist():
        a, b = E[k]
        by_vert.setdefault(int(a), []).append(k)
        by_vert.setdefault(int(b), []).append(k)
    seen, stack = {e}, [e]
    while stack:
        k = stack.pop()
        for v in E[k]:
            nb = by_vert.get(int(v), [])
            if len(nb) != 2:                  # an end or a corner where lines meet: the line stops
                continue
            for j in nb:
                if j not in seen:
                    seen.add(j)
                    stack.append(j)
    return sorted(seen)


def clear_edges(me, edges, sharp=True):
    """Crease 0 (and sharp off) on ``edges``.  Returns how many were marked."""
    edges = np.asarray(edges, np.int64)
    if not len(edges):
        return 0
    n = len(me.edges)
    was = marked(me)[edges].sum()
    a = me.attributes.get('crease_edge')
    if a is not None and a.domain == 'EDGE':
        v = np.empty(n, np.float32)
        a.data.foreach_get('value', v)
        v[edges] = 0.0
        a.data.foreach_set('value', v)
    if sharp:
        a = me.attributes.get('sharp_edge')
        if a is not None and a.domain == 'EDGE':
            v = np.zeros(n, bool)
            a.data.foreach_get('value', v)
            v[edges] = False
            a.data.foreach_set('value', v)
    me.update()
    return int(was)


def screen_edge(ob, region, rv3d, xy, px=PX):
    """The marked edge of ``ob`` nearest ``xy`` on screen (within ``px``), or None."""
    me = ob.data
    mark = marked(me)
    ids = np.nonzero(mark)[0]
    if not len(ids):
        return None
    E = edge_verts(me)[ids]
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    M = np.array(rv3d.perspective_matrix) @ np.array(ob.matrix_world)
    H = np.c_[co, np.ones(len(co))] @ M.T
    ok = H[:, 3] > 1e-9
    W = np.where(ok, H[:, 3], 1.0)
    X = (H[:, 0] / W + 1.0) * 0.5 * region.width
    Y = (H[:, 1] / W + 1.0) * 0.5 * region.height
    A = np.stack([X[E[:, 0]], Y[E[:, 0]]], 1)
    B = np.stack([X[E[:, 1]], Y[E[:, 1]]], 1)
    p = np.array(xy, float)
    d = B - A
    t = np.clip(((p - A) * d).sum(1) / np.maximum((d * d).sum(1), 1e-12), 0.0, 1.0)
    dist = np.linalg.norm(A + d * t[:, None] - p, axis=1)
    dist[~(ok[E[:, 0]] & ok[E[:, 1]])] = np.inf
    # the side you see: an edge behind the part (its middle farther than the surface under the mouse) does not count
    k = int(np.argmin(dist))
    if dist[k] > px:
        return None
    return int(ids[k])


def _part(context, xy):
    from . import geo_sculpt as gs, target_rules
    hit = gs.pick_part(context, xy)
    if hit is not None:
        return hit[0]
    ob = bpy.data.objects.get(HOVER['part']) if HOVER['part'] else None     # (just off the part: the one last over)
    if ob is not None and ob.type == 'MESH' and target_rules.ok(context, ob):
        return ob
    return None


def tool_on(context):
    from . import tool_state as ts
    try:
        return ts.effective_tool(context) == 'ECLEAR'
    except (AttributeError, KeyError, TypeError):
        return False


def _segs(ob, edges):
    me = ob.data
    mw = ob.matrix_world
    E = edge_verts(me)
    return [(mw @ me.vertices[int(a)].co, mw @ me.vertices[int(b)].co) for a, b in E[list(edges)]]


def draw_edges():
    context = bpy.context
    try:
        if not tool_on(context):
            return
        ob = bpy.data.objects.get(HOVER['part']) if HOVER['part'] else None
        if ob is None or ob.type != 'MESH':
            return
        from . import edge_runs
        ids = np.nonzero(marked(ob.data))[0]
        if len(ids) and len(ids) < 200000:
            edge_runs.draw_lines(_segs(ob, ids), (0.35, 0.85, 1.0, 0.6), 2.0)
        if HOVER['edges']:
            edge_runs.draw_lines(_segs(ob, HOVER['edges']), (1.0, 0.45, 0.2, 1.0), 4.5)
    except (ReferenceError, AttributeError, RuntimeError, KeyError, IndexError):
        pass


class MCH_OT_edge_clear_hover(bpy.types.Operator):
    """(Edge Clear) the creased line under the mouse, shown (passes the move on)"""
    bl_idname = 'mch.edge_clear_hover'
    bl_label = 'Edge Clear Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        ob = _part(context, xy)
        edges = None
        if ob is not None and ob.type == 'MESH':
            e = screen_edge(ob, context.region, context.region_data, xy)
            if e is not None:
                whole = context.scene.mch_edge_clear.whole != event.shift
                edges = line_of(ob.data, e) if whole else [e]
        part = ob.name if ob is not None else None
        if (part, edges) != (HOVER['part'], HOVER['edges']):
            HOVER['part'], HOVER['edges'] = part, edges
            context.region.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_edge_clear_click(bpy.types.Operator):
    """Edge Clear: click a creased edge of a part - its crease (and sharp mark) is cleared, the whole line it belongs
    to (Shift: only that edge)"""
    bl_idname = 'mch.edge_clear_click'
    bl_label = 'Edge Clear'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        ob = _part(context, xy)
        if ob is None or ob.type != 'MESH':
            return {'PASS_THROUGH'}
        e = screen_edge(ob, context.region, context.region_data, xy)
        if e is None:
            self.report({'INFO'}, 'Edge Clear: no creased edge under the mouse')
            return {'CANCELLED'}
        st = context.scene.mch_edge_clear
        edges = line_of(ob.data, e) if st.whole != event.shift else [e]
        n = clear_edges(ob.data, edges, st.sharp)
        HOVER['edges'] = None
        context.region.tag_redraw()
        self.report({'INFO'}, f'Edge Clear: {n} edge{"s" if n != 1 else ""} cleared on {ob.name}')
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_edge_clear
    col = layout.column(align=True)
    col.label(text='Click a creased edge: cleared (Shift: one edge)')
    col.prop(st, 'whole')
    col.prop(st, 'sharp')


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return
    draw(layout, context)


class MCH_TOOL_edge_clear(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.edge_clear'
    bl_label = 'Edge Clear'
    bl_description = ('Click a creased edge of a part: its crease (and sharp mark) is cleared - the whole line.\n'
                      'Shift: only that edge')
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = (('mch.edge_clear_hover', {'type': 'MOUSEMOVE', 'value': 'ANY', 'any': True}, None),
                 ('mch.edge_clear_click', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
                 ('mch.edge_clear_click', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
                 ('mch.toggle_targets', {'type': 'T', 'value': 'PRESS'}, None),
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_PG_EdgeClear, MCH_OT_edge_clear_hover, MCH_OT_edge_clear_click)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_edge_clear = PointerProperty(type=MCH_PG_EdgeClear)
    try:
        bpy.utils.register_tool(MCH_TOOL_edge_clear, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_edges, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_edge_clear)
    except (ValueError, RuntimeError, KeyError):
        pass
    if hasattr(bpy.types.Scene, 'mch_edge_clear'):
        del bpy.types.Scene.mch_edge_clear
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
