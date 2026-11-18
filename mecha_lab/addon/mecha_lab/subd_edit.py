"""0.24.231 (user: "섭디 플레인은 왜 안 돼? ... 내가 말한 건 메카랩 오브젝트 모드에서 편집하게 해 달라고"): the SubD Plane's
cage edited right in Object Mode (MECHA LAB has no Edit Mode) - the SubD Plane tool shows the plane's points and
edges over it:

* drag a point: it moves (in the view's plane, through where it is);
* drag an OPEN edge (the plane's outline): a new face is pulled out of it - like E in Edit Mode;
  Shift + drag an edge (or any inner edge): the edge moves;
* Alt + click a point: it goes (its faces join; a corner's face goes with it - never the last face);
* Ctrl + click an edge: its crease on / off (the Crease value of the window);
* a dragged point near another one snaps onto it (green) and joins it when let go (0.24.232; Ctrl held: no snap);
* a click on another SubD Plane: that one is edited.

Every change is one undo step (Ctrl+Z).
"""
from __future__ import annotations

import bmesh
import bpy
from mathutils import Vector

from . import tool_state as ts

PICK_POINT = 14.0           # px at UI scale 1
PICK_EDGE = 10.0
SNAP = 16.0                 # px at UI scale 1: a dragged point this near another one snaps onto it (and joins it)
HOVER = {'ob': None, 'kind': None, 'index': -1}      # what is under the mouse ('V' point / 'E' edge)
DRAG = {'on': False, 'snap': []}      # snap: [(dragged index, target index)] while dragging


def tool_on(context):
    try:
        return ts.effective_tool(context) == 'SUBD'
    except (AttributeError, KeyError, TypeError):
        return False


def target(context):
    from . import subd_plane
    return subd_plane.active_subd(context)


def _k(context):
    from .ui_gpu import ui_factor
    try:
        return ui_factor(context, context.region)
    except (AttributeError, TypeError):
        return 1.0


def _screen(context, ob):
    """Every cage point on screen: [(x, y) or None]."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    mw = ob.matrix_world
    out = []
    for v in ob.data.vertices:
        p = view3d_utils.location_3d_to_region_2d(region, rv3d, mw @ v.co)
        out.append((p.x, p.y) if p is not None else None)
    return out


def _seg_dist(p, a, b):
    ax, ay = a
    bx, by = b
    dx, dy = bx - ax, by - ay
    L = dx * dx + dy * dy
    t = 0.0 if L < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / L))
    qx, qy = ax + dx * t, ay + dy * t
    return ((p[0] - qx) ** 2 + (p[1] - qy) ** 2) ** 0.5


def pick(context, ob, xy):
    """('V', index) / ('E', index) / None - a point first (within PICK_POINT px), else an edge."""
    if ob is None or ob.type != 'MESH':
        return None
    k = _k(context)
    pts = _screen(context, ob)
    best = None
    for i, p in enumerate(pts):
        if p is None:
            continue
        d = ((p[0] - xy[0]) ** 2 + (p[1] - xy[1]) ** 2) ** 0.5
        if d <= PICK_POINT * k and (best is None or d < best[0]):
            best = (d, i)
    if best is not None:
        return ('V', best[1])
    for e in ob.data.edges:
        a, b = pts[e.vertices[0]], pts[e.vertices[1]]
        if a is None or b is None:
            continue
        d = _seg_dist(xy, a, b)
        if d <= PICK_EDGE * k and (best is None or d < best[0]):
            best = (d, e.index)
    return ('E', best[1]) if best is not None else None


def _subd_under(context, xy):
    """A SubD Plane under the mouse (its evaluated surface), or None."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, TypeError):
        return None
    if hit and ob is not None:
        ob = ob.original
        if ob.type == 'MESH' and getattr(ob, 'mch_subd', None) and ob.mch_subd.active:
            return ob
    return None


def _open_edges(me):
    from . import mesh_io as mio
    try:
        return set(int(i) for i in (mio.edge_face_counts(me) == 1).nonzero()[0])
    except (AttributeError, TypeError, ValueError):
        return set()


def _view_point(context, xy, depth):
    from bpy_extras import view3d_utils
    return view3d_utils.region_2d_to_location_3d(context.region, context.region_data, xy, depth)


class MCH_OT_subd_edit_hover(bpy.types.Operator):
    """(SubD Plane) the point / edge under the mouse, lit (passes the move on)"""
    bl_idname = 'mch.subd_edit_hover'
    bl_label = 'SubD Plane Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW' or DRAG['on']:
            return {'PASS_THROUGH'}
        ob = target(context)
        h = pick(context, ob, (event.mouse_region_x, event.mouse_region_y)) if ob is not None else None
        new = (ob.name if ob is not None else None, h[0] if h else None, h[1] if h else -1)
        if new != (HOVER['ob'], HOVER['kind'], HOVER['index']):
            HOVER.update(ob=new[0], kind=new[1], index=new[2])
            context.region.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_subd_edit(bpy.types.Operator):
    """Edit the SubD Plane in Object Mode: drag a point = move it; drag an outline edge = pull a new face out of it
    (Shift: move the edge); Alt + click a point = remove it; Ctrl + click an edge = crease on / off"""
    bl_idname = 'mch.subd_edit'
    bl_label = 'Edit SubD Plane'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and context.area is not None and context.area.type == 'VIEW_3D'

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        ob = target(context)
        h = pick(context, ob, xy) if ob is not None else None
        if h is None:                                   # another SubD Plane under the mouse: edit that one
            other = _subd_under(context, xy)
            if other is not None and other is not ob:
                for o in context.selected_objects:
                    o.select_set(False)
                other.select_set(True)
                context.view_layer.objects.active = other
                self.report({'INFO'}, f'SubD Plane: {other.name}')
                return {'FINISHED'}
            return {'PASS_THROUGH'}
        me = ob.data
        kind, idx = h
        if event.alt and kind == 'V':
            return self._remove(context, ob, idx)
        if event.ctrl and kind == 'E':
            return self._crease(context, ob, idx)
        self.ob = ob
        self.start = xy
        self.backup = me.copy()
        self.moved = False
        self.extruded = False
        mw = ob.matrix_world
        if kind == 'V':
            self.idx = [idx]
        else:
            e = me.edges[idx]
            self.idx = list(e.vertices)
            if not event.shift and idx in _open_edges(me):
                self.idx = self._extrude(ob, idx)
                self.extruded = True
        self.orig = [mw @ me.vertices[i].co.copy() for i in self.idx]
        # 0.24.232 (user: "그 점끼리 만나서 내가 가져다 대면 자동으로 붙게 해 줘") the points a dragged one may snap onto:
        # all the others (not the dragged ones, nor - pulling a face out - the edge it comes out of)
        skip = set(self.idx) | (set(me.edges[idx].vertices) if kind == 'E' else set())
        pts = _screen(context, ob)
        self.others = [(i, p) for i, p in enumerate(pts) if i not in skip and p is not None]
        self.snap_px = SNAP * _k(context)
        DRAG['snap'] = []
        centre = sum(self.orig, Vector()) / len(self.orig)
        self.depth = centre
        self.anchor = _view_point(context, xy, centre)
        DRAG['on'] = True
        HOVER.update(ob=ob.name, kind=kind, index=idx)
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _extrude(self, ob, edge_index):
        """A new face out of open edge ``edge_index``: (its two new points)."""
        me = ob.data
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            bm.edges.ensure_lookup_table()
            res = bmesh.ops.extrude_edge_only(bm, edges=[bm.edges[edge_index]])
            new = [g for g in res['geom'] if isinstance(g, bmesh.types.BMVert)]
            for v in bm.verts:
                v.tag = False
            for v in new:
                v.tag = True
            bm.to_mesh(me)
            bm.verts.ensure_lookup_table()
            ids = [v.index for v in bm.verts if v.tag]
        finally:
            bm.free()
        me.update()
        return ids

    def _remove(self, context, ob, vi):
        me = ob.data
        if len(me.polygons) <= 1 and len(me.vertices) <= 4:
            self.report({'WARNING'}, 'SubD Plane: the last face stays')
            return {'CANCELLED'}
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()
            v = bm.verts[vi]
            try:
                bmesh.ops.dissolve_verts(bm, verts=[v])
            except (RuntimeError, ValueError):
                bmesh.ops.delete(bm, geom=[v], context='VERTS')
            loose = [x for x in bm.verts if not x.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            if not bm.faces:
                self.report({'WARNING'}, 'SubD Plane: the last face stays')
                return {'CANCELLED'}
            bm.to_mesh(me)
        finally:
            bm.free()
        me.update()
        HOVER.update(kind=None, index=-1)
        return {'FINISHED'}

    def _crease(self, context, ob, ei):
        from . import subd_plane
        me = ob.data
        a = me.attributes.get(subd_plane.CREASE_ATTR)
        if a is None:
            a = me.attributes.new(subd_plane.CREASE_ATTR, 'FLOAT', 'EDGE')
        cur = a.data[ei].value
        a.data[ei].value = 0.0 if cur > 1e-6 else float(context.scene.mch_subd.crease_value)
        if not ob.mch_subd.use_creases and a.data[ei].value > 0:
            ob.mch_subd.use_creases = True
        me.update()
        self.report({'INFO'}, 'Crease ' + ('off' if cur > 1e-6 else 'on'))
        return {'FINISHED'}

    def modal(self, context, event):
        if event.type == 'MOUSEMOVE':
            xy = (event.mouse_region_x, event.mouse_region_y)
            if abs(xy[0] - self.start[0]) + abs(xy[1] - self.start[1]) > 3:
                self.moved = True
            p = _view_point(context, xy, self.depth)
            if p is None or self.anchor is None:
                return {'RUNNING_MODAL'}
            delta = p - self.anchor
            inv = self.ob.matrix_world.inverted_safe()
            me = self.ob.data
            from bpy_extras import view3d_utils
            snaps = []
            for i, w in zip(self.idx, self.orig):
                me.vertices[i].co = inv @ (w + delta)
                q = view3d_utils.location_3d_to_region_2d(context.region, context.region_data, w + delta)
                if q is None or event.ctrl:                 # (Ctrl held: no snapping)
                    continue
                best = None
                for j, pj in self.others:
                    d = ((pj[0] - q.x) ** 2 + (pj[1] - q.y) ** 2) ** 0.5
                    if d <= self.snap_px and (best is None or d < best[0]):
                        best = (d, j)
                if best is not None:
                    me.vertices[i].co = me.vertices[best[1]].co.copy()
                    snaps.append((i, best[1]))
            DRAG['snap'] = snaps
            me.update()
            context.region.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            DRAG['on'] = False
            snaps, DRAG['snap'] = DRAG['snap'], []
            if snaps and self.moved:
                n = self._weld(snaps)
                if n:
                    self.report({'INFO'}, f'SubD Plane: {n} point(s) joined')
            if not self.moved and self.extruded:        # a click on an edge, no drag: nothing pulled out
                self._restore()
                bpy.data.meshes.remove(self.backup)
                return {'CANCELLED'}
            bpy.data.meshes.remove(self.backup)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            DRAG['on'] = False
            DRAG['snap'] = []
            self._restore()
            bpy.data.meshes.remove(self.backup)
            context.region.tag_redraw()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}

    def _weld(self, snaps):
        """The snapped points become one with the points they sit on.  Returns how many were joined."""
        me = self.ob.data
        bm = bmesh.new()
        try:
            bm.from_mesh(me)
            bm.verts.ensure_lookup_table()
            tmap = {}
            for i, j in snaps:
                if i != j and i < len(bm.verts) and j < len(bm.verts):
                    tmap[bm.verts[i]] = bm.verts[j]
            if not tmap:
                return 0
            bmesh.ops.weld_verts(bm, targetmap=tmap)
            loose = [v for v in bm.verts if not v.link_faces]
            if loose:
                bmesh.ops.delete(bm, geom=loose, context='VERTS')
            if not bm.faces:
                return 0
            bm.to_mesh(me)
        finally:
            bm.free()
        me.update()
        HOVER.update(kind=None, index=-1)
        return len(tmap)

    def _restore(self):
        me = self.ob.data
        bm = bmesh.new()
        try:
            bm.from_mesh(self.backup)
            bm.to_mesh(me)
        finally:
            bm.free()
        me.update()

    def cancel(self, context):
        DRAG['on'] = False
        DRAG['snap'] = []


# ---- drawing --------------------------------------------------------------------------------------------------

def _draw():
    context = bpy.context
    try:
        if not tool_on(context):
            return
        ob = target(context)
        if ob is None:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        from . import edge_runs, subd_plane
        me = ob.data
        mw = ob.matrix_world
        co = [mw @ v.co for v in me.vertices]
        open_e = _open_edges(me)
        crease = me.attributes.get(subd_plane.CREASE_ATTR)
        cv = [crease.data[i].value for i in range(len(me.edges))] if crease is not None else [0.0] * len(me.edges)
        inner, outer, creased = [], [], []
        for e in me.edges:
            seg = (co[e.vertices[0]], co[e.vertices[1]])
            (creased if cv[e.index] > 1e-6 else outer if e.index in open_e else inner).append(seg)
        edge_runs.draw_lines(inner, (0.35, 0.85, 1.0, 0.7), 1.5, xray=True)
        edge_runs.draw_lines(outer, (0.35, 0.85, 1.0, 1.0), 2.5, xray=True)
        edge_runs.draw_lines(creased, (1.0, 0.35, 0.8, 1.0), 2.5, xray=True)
        if HOVER['ob'] == ob.name and HOVER['kind'] == 'E' and 0 <= HOVER['index'] < len(me.edges):
            e = me.edges[HOVER['index']]
            edge_runs.draw_lines([(co[e.vertices[0]], co[e.vertices[1]])], (1.0, 0.92, 0.2, 1.0), 4.0, xray=True)
        try:
            sh = gpu.shader.from_builtin('POINT_UNIFORM_COLOR')
        except (ValueError, SystemError):
            sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        k = _k(context)
        gpu.state.point_size_set(9.0 * k)
        b = batch_for_shader(sh, 'POINTS', {'pos': [tuple(p) for p in co]})
        sh.uniform_float('color', (0.95, 0.97, 1.0, 1.0))
        b.draw(sh)
        if HOVER['ob'] == ob.name and HOVER['kind'] == 'V' and 0 <= HOVER['index'] < len(co):
            gpu.state.point_size_set(14.0 * k)
            b = batch_for_shader(sh, 'POINTS', {'pos': [tuple(co[HOVER['index']])]})
            sh.uniform_float('color', (1.0, 0.92, 0.2, 1.0))
            b.draw(sh)
        if DRAG.get('snap'):                            # (where a dragged point will join: green)
            gpu.state.point_size_set(18.0 * k)
            b = batch_for_shader(sh, 'POINTS', {'pos': [tuple(co[j]) for _i, j in DRAG['snap'] if j < len(co)]})
            sh.uniform_float('color', (0.3, 1.0, 0.45, 1.0))
            b.draw(sh)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')
    except (ReferenceError, AttributeError, RuntimeError, KeyError, IndexError):
        pass


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return
    from . import ui_tool_settings
    ui_tool_settings.draw_subd(layout, context)


class MCH_TOOL_subd_plane(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.subd_plane'
    bl_label = 'Mecha SubD Plane'
    bl_description = ('Edit the SubD Plane right here: drag a point to move it, drag an outline edge to pull a new '
                      'face out of it (Shift: move the edge), Alt + click a point to remove it, Ctrl + click an edge: '
                      'crease')
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = (('mch.subd_edit_hover', {'type': 'MOUSEMOVE', 'value': 'ANY', 'any': True}, None),
                 ('mch.subd_edit', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
                 ('mch.subd_edit', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
                 ('mch.subd_edit', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),
                 ('mch.subd_edit', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'ctrl': True}, None),
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_OT_subd_edit_hover, MCH_OT_subd_edit)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    try:
        bpy.utils.register_tool(MCH_TOOL_subd_plane, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_subd_plane)
    except (ValueError, RuntimeError, KeyError):
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
