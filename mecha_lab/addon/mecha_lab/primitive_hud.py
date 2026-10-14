"""0.15 Primitive HUD: buttons that float next to the shape in the viewport.

Right of the shape (ghost primitive, or the selected live Station Primitive):
    [+]  add mode      [-]  subtract mode      [check]  Apply
    a slider under Apply: Segments (round shapes) / Sides (polygon) / Profile
    resolution - drag left / right, one step per few pixels.
Above / below a Station Primitive (at its end / start):  [+] [-]  add or remove
a segment there.

Apply on the ghost = Enter (merge, or subtract in - mode).  Apply on a Station
Primitive: + merges it into the mesh it overlaps (or just freezes it when it
touches nothing), - carves it out of every mesh it overlaps.

Faces of the ghost lying on a face of the mesh (same size subtract / add)
make Boolean artefacts: they get a red dashed outline and a red note next to
the buttons ("grow or shrink the shape a little").

Placement (``hud_layout``) and the overlap test (``coplanar_faces``) are pure
and tested headless; the buttons and slider need a real viewport.
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg
from . import primitive_place as pp
from . import station_primitive as sp
from . import tool_state as ts

ACCENT = (1.0, 0.62, 0.16)
BASE_COL = (0.17, 0.19, 0.23)
SUB_COL = (0.85, 0.25, 0.25)
BTN = 30.0              # button diameter, px at UI scale 1
SLIDER_W, SLIDER_H = 92.0, 20.0
STEP_PX = 9.0           # slider: pixels per step
_label_handle = None


# -----------------------------------------------------------------------------
# What the HUD is for
# -----------------------------------------------------------------------------


def hud_target(context):
    """('GHOST', None), ('STATION', object) or (None, None)."""
    try:
        if not ts.is_mecha_workspace(getattr(context, 'workspace', None)) or context.mode != 'OBJECT':
            return None, None
    except (AttributeError, TypeError):
        return None, None
    if pp.ghost_visible(context):
        return 'GHOST', None
    ob = context.active_object
    if sp.is_live(ob) and ob.select_get():
        try:
            tool = ts.effective_tool(context)
        except (AttributeError, KeyError, TypeError):
            tool = ''
        from .station_gizmos import SELECT_NATIVE
        if tool == 'PRIMITIVE' or ts.native_tool_id(context) in SELECT_NATIVE:
            return 'STATION', ob
    return None, None


def target_points(context, kind, ob):
    """World points that outline the shape (bounding box corners)."""
    if kind == 'GHOST':
        st = pp.state(context)
        verts, _f, _s = pp.st_shape(st)
        lo = [min(v[i] for v in verts) for i in range(3)]
        hi = [max(v[i] for v in verts) for i in range(3)]
        m = pp.ghost_matrix(st.location if st.placed else context.scene.cursor.location, st.rotation)
        return [m @ Vector((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    if kind == 'STATION' and ob is not None:
        return [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    return []


def station_ends(ob):
    """World positions of the start and the end of a Station Primitive."""
    frames = sp.station_frames(ob)
    return ob.matrix_world @ Vector(frames[0][0]), ob.matrix_world @ Vector(frames[-1][0])


def hud_layout(screen_pts, region_w, region_h, ends=None, btn=BTN, gap=6.0):
    """Region-pixel centres of the HUD controls (UI scale 1).

    ``screen_pts`` = the shape's outline in region pixels.  The column sits
    right of the shape (kept inside the region); ``ends`` = (start_xy, end_xy)
    of a Station Primitive puts its segment buttons just outside each end."""
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    x0 = max(p[0] for p in pts)
    cy = (max(p[1] for p in pts) + min(p[1] for p in pts)) / 2.0
    x = min(max(x0 + btn * 1.2, btn), region_w - SLIDER_W - btn)
    step = btn + gap
    cy = min(max(cy, step * 2 + SLIDER_H), region_h - step * 2)
    out = {'add': (x, cy + step), 'sub': (x, cy), 'apply': (x, cy - step),
           'slider': (x - btn / 2 + SLIDER_W / 2, cy - step * 2 + (btn - SLIDER_H) / 2 - 2)}
    if ends:
        cx = sum(p[0] for p in pts) / len(pts)
        cyy = sum(p[1] for p in pts) / len(pts)
        for tag, p in (('start', ends[0]), ('end', ends[1])):
            if p is None:
                continue
            d = Vector((p[0] - cx, p[1] - cyy))
            d = d.normalized() if d.length > 1e-6 else Vector((0.0, 1.0 if tag == 'end' else -1.0))
            c = Vector(p) + d * (btn * 1.1)
            side = Vector((-d.y, d.x)) * (btn * 0.6)
            out[tag + '_add'] = tuple(c + side)
            out[tag + '_remove'] = tuple(c - side)
    return out


def slider_spec(context, kind, ob):
    """(label, value, minimum, maximum, setter) for the slider, or None."""
    if kind == 'GHOST':
        st = pp.state(context)
        if st.kind == 'BOX':
            if st.edge != 'BEVEL':
                return None
            return ('Bevel Seg', st.edge_segments, 1, 16, lambda v: setattr(st, 'edge_segments', v))
        return ('Segments', st.segments, 8, 128, lambda v: setattr(st, 'segments', v))
    if kind == 'STATION' and ob is not None:
        p = ob.mch_station
        if p.kind in {'POLYGON', 'NGON'}:
            return ('Sides', p.sides, 3, 64, lambda v: setattr(p, 'sides', v))
        return ('Resolution', p.res, 2, 48, lambda v: setattr(p, 'res', v))
    return None


# -----------------------------------------------------------------------------
# Coplanar faces (Boolean artefacts)
# -----------------------------------------------------------------------------


def coplanar_faces(matrix, verts, faces, smooth, targets_bvh, tol, cos_tol=0.999):
    """Indices of flat ghost faces that lie on a face of one of the targets.

    ``targets_bvh`` = list of BVHTree in world space.  A face counts when its
    centre (or a point near one of its corners) is within ``tol`` of a target
    face with a parallel normal."""
    out = []
    for fi, f in enumerate(faces):
        if fi in smooth or len(f) < 3:
            continue
        w = [matrix @ Vector(verts[i]) for i in f]
        c = sum(w, Vector()) / len(w)
        n = (w[1] - w[0]).cross(w[2] - w[0])
        if n.length < 1e-12:
            continue
        n.normalize()
        probes = [c] + [c + (q - c) * 0.8 for q in w]
        hit = False
        for bvh in targets_bvh:
            for q in probes:
                loc, nt, _i, dist = bvh.find_nearest(q, tol)
                if loc is not None and dist <= tol and abs(n.dot(nt)) >= cos_tol:
                    hit = True
                    break
            if hit:
                break
        if hit:
            out.append(fi)
    return out


_COPLANAR = {'key': None, 'faces': [], 't': -1e9}


def coplanar_cached(context, st, now=None):
    """Coplanar ghost faces for drawing (recomputed when the ghost or the
    meshes change, at most every 0.2 s)."""
    import time
    now = time.monotonic() if now is None else now
    m = pp.ghost_matrix(st.location if st.placed else context.scene.cursor.location, st.rotation)
    verts, faces, smooth = pp.st_shape(st)
    key = pp.ghost_signature(st)
    if _COPLANAR['key'] == key and now - _COPLANAR['t'] < 2.0:
        return _COPLANAR['faces']
    if _COPLANAR['key'] != key and now - _COPLANAR['t'] < 0.2:
        return _COPLANAR['faces']
    dg = context.evaluated_depsgraph_get()
    targets = pp.overlapping_meshes(context, m, verts, faces)
    bvhs = [b for b in (pp._bvh_world(t, dg)[0] for t in targets) if b is not None]
    tol = max(1e-5, 0.004 * max(st.size))
    out = coplanar_faces(m, verts, faces, smooth, bvhs, tol) if bvhs else []
    _COPLANAR.update(key=key, faces=out, t=now)
    return out


# -----------------------------------------------------------------------------
# Apply for a Station Primitive
# -----------------------------------------------------------------------------


def commit_station(context, ob, subtract=False):
    """+ : merge into the mesh it overlaps (freeze only when it touches
    nothing); - : carve it out of every mesh it overlaps.  Returns a report."""
    me = ob.data
    world = ob.matrix_world
    verts = [v.co.copy() for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    targets = pp.overlapping_meshes(context, world, verts, faces, exclude=(ob,))
    st = pp.state(context)
    if subtract and not targets:
        raise cg.CutError('Subtract: the primitive does not touch any mesh; nothing was changed.')
    sp.apply_object(context, ob)
    if not targets:
        return f'{ob.name}: applied (it touched no mesh)'
    if not subtract:
        targets = [pp.pick_union_target(context, targets, world.translation)]
    attr = ob.data.attributes.get(cg.CUTTER_ATTR) or ob.data.attributes.new(cg.CUTTER_ATTR, 'BOOLEAN', 'FACE')
    attr.data.foreach_set('value', [True] * len(ob.data.polygons))
    solver = getattr(getattr(context.scene, 'mch_cut', None), 'solver', 'AUTO')
    done, failed, temp = [], [], []
    try:
        for t in targets:
            try:
                cg.check_target(t)
                sp.freeze(t)
                cg.ensure_real_mesh(context, t)
                res, _s = cg.boolean_result(context, t, ob, 'DIFFERENCE' if subtract else 'UNION', solver)
                temp.append(res)
                if st is not None and st.merge != 'HARD':
                    cg.finish_new_edges(res, st.merge, st.finish_width, st.finish_segments, 0.5, label='Seam')
                cg.commit_mesh(t, res)
                done.append(t)
            except (cg.CutError, RuntimeError) as ex:
                if len(targets) == 1:
                    cg.remove_cutter_attribute(ob.data)
                    raise
                failed.append(f'{t.name} ({str(ex).splitlines()[0][:60]})')
    finally:
        for m in temp:
            try:
                bpy.data.meshes.remove(m)
            except ReferenceError:
                pass
    if not done:
        cg.remove_cutter_attribute(ob.data)
        raise cg.CutError('Nothing was changed. ' + '; '.join(failed))
    name = ob.name
    cg.remove_object_and_mesh(ob)
    for o in context.selected_objects:
        o.select_set(False)
    for t in done:
        t.select_set(True)
    context.view_layer.objects.active = done[0]
    names = ', '.join(t.name for t in done)
    return (f'{name} subtracted from {names}' if subtract else f'{name} merged into {names}') + \
        ((' | skipped: ' + '; '.join(failed)) if failed else '')


# -----------------------------------------------------------------------------
# Operators
# -----------------------------------------------------------------------------


class MCH_OT_hud_mode(bpy.types.Operator):
    """HUD: Apply adds (+) or subtracts (-)"""
    bl_idname = 'mch.hud_mode'
    bl_label = 'Add / Subtract Mode'
    bl_options = {'INTERNAL'}
    subtract: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def description(cls, context, properties):
        return 'Subtract mode: Apply carves the shape out' if properties.subtract else \
            'Add mode: Apply merges the shape in'

    def execute(self, context):
        st = pp.state(context)
        if st is None:
            return {'CANCELLED'}
        st.mode_sub = self.subtract
        return {'FINISHED'}


class MCH_OT_hud_apply(bpy.types.Operator):
    """HUD Apply: the ghost or the selected Station Primitive is merged in (+) or carved out (-)"""
    bl_idname = 'mch.hud_apply'
    bl_label = 'Apply Primitive'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return hud_target(context)[0] is not None or pp.state(context) is not None

    def execute(self, context):
        kind, ob = hud_target(context)
        st = pp.state(context)
        sub = bool(st and st.mode_sub)
        if kind == 'STATION':
            try:
                msg = commit_station(context, ob, sub)
            except cg.CutError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            self.report({'INFO'}, msg)
            return {'FINISHED'}
        return bpy.ops.mch.place_commit('EXEC_DEFAULT', subtract=sub)


# -----------------------------------------------------------------------------
# Slider gizmo (custom 2D gizmo: drag left / right)
# -----------------------------------------------------------------------------

_RECT = ((-1.0, -1.0, 0.0), (1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, -1.0, 0.0), (1.0, 1.0, 0.0), (-1.0, 1.0, 0.0))


def slider_value(start, dx, step_px=STEP_PX, lo=1, hi=999):
    """Slider drag: whole steps, clamped."""
    return int(max(lo, min(hi, round(start + dx / step_px))))


class MCH_GT_hud_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_hud_slider'
    __slots__ = ('shape', 'init_x', 'init_value')

    def setup(self):
        if not hasattr(self, 'shape'):
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        spec = slider_spec(context, *hud_target(context))
        if spec is None:
            return {'CANCELLED'}
        self.init_x = event.mouse_region_x
        self.init_value = spec[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        spec = slider_spec(context, *hud_target(context))
        if spec is None:
            return {'CANCELLED'}
        label, _v, lo, hi, setter = spec
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x, lo=lo, hi=hi)
        if v != spec[1]:
            setter(v)
        if context.area:
            context.area.header_text_set(f'{label}: {v}   (drag left / right)')
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            spec = slider_spec(context, *hud_target(context))
            if spec is not None:
                spec[4](self.init_value)


# -----------------------------------------------------------------------------
# Gizmo group
# -----------------------------------------------------------------------------

BUTTONS = (('add', 'ADD', 'mch.hud_mode', {'subtract': False}),
           ('sub', 'REMOVE', 'mch.hud_mode', {'subtract': True}),
           ('apply', 'CHECKMARK', 'mch.hud_apply', {}),
           ('end_add', 'ADD', 'mch.station_segment', {'where': 'END', 'action': 'ADD'}),
           ('end_remove', 'REMOVE', 'mch.station_segment', {'where': 'END', 'action': 'REMOVE'}),
           ('start_add', 'ADD', 'mch.station_segment', {'where': 'START', 'action': 'ADD'}),
           ('start_remove', 'REMOVE', 'mch.station_segment', {'where': 'START', 'action': 'REMOVE'}))


def _project(context, pts):
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return []
    return [view3d_utils.location_3d_to_region_2d(region, rv3d, p) for p in pts]


def current_layout(context):
    """(kind, ob, layout in region px) for the HUD now."""
    kind, ob = hud_target(context)
    if kind is None:
        return None, None, {}
    ui = context.preferences.system.ui_scale
    pts = [None if p is None else (p[0] / ui, p[1] / ui) for p in _project(context, target_points(context, kind, ob))]
    ends = None
    if kind == 'STATION':
        e = _project(context, list(station_ends(ob)))
        ends = tuple(None if p is None else (p[0] / ui, p[1] / ui) for p in e)
    region = context.region
    return kind, ob, hud_layout(pts, region.width / ui, region.height / ui, ends)


class MCH_GGT_prim_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_prim_hud'
    bl_label = 'Primitive HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return hud_target(context)[0] is not None

    def setup(self, context):
        self.items = {}
        for name, icon, op, props in BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            target = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(target, k, v)
            gz.color = BASE_COL
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        gz = self.gizmos.new(MCH_GT_hud_slider.bl_idname)
        gz.color = (0.24, 0.27, 0.32)
        gz.alpha = 0.95
        gz.color_highlight = (0.36, 0.40, 0.47)
        gz.alpha_highlight = 1.0
        gz.use_draw_scale = False
        self.items['slider'] = gz

    def draw_prepare(self, context):
        kind, ob, lay = current_layout(context)
        ui = context.preferences.system.ui_scale
        from .workspace_ui import handle_scale
        f = handle_scale()
        st = pp.state(context)
        sub = bool(st and st.mode_sub)
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None or (name == 'slider' and slider_spec(context, kind, ob) is None)
            if gz.hide:
                continue
            if name == 'slider':
                m = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (SLIDER_W * ui / 2, SLIDER_H * ui / 2, 1.0, 1.0))
                gz.matrix_basis = m
                continue
            gz.scale_basis = BTN / 2.0 * (0.8 if name.startswith(('end', 'start')) else 1.0) * min(1.6, f)
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui
            on = (name == 'add' and not sub) or (name == 'sub' and sub)
            gz.color = (SUB_COL if name == 'sub' else ACCENT) if on else BASE_COL


def _draw_labels():
    """Names next to the HUD buttons, the slider value and the overlap warning."""
    try:
        context = bpy.context
        kind, ob, lay = current_layout(context)
        if kind is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        font = 0
        blf.size(font, 11 * ui)
        st = pp.state(context)
        sub = bool(st and st.mode_sub)
        names = {'add': 'Add', 'sub': 'Subtract', 'apply': 'Apply'}
        for key, text in names.items():
            x, y = lay[key]
            on = (key == 'add' and not sub) or (key == 'sub' and sub) or key == 'apply'
            blf.color(font, *(ACCENT if on else (0.85, 0.87, 0.9)), 1.0)
            blf.position(font, (x + BTN * 0.7) * ui, (y - 4) * ui, 0)
            blf.draw(font, text)
        spec = slider_spec(context, kind, ob)
        if spec is not None:
            x, y = lay['slider']
            text = f'{spec[0]}  {spec[1]}'
            w, _h = blf.dimensions(font, text)
            blf.color(font, 1.0, 1.0, 1.0, 1.0)
            blf.position(font, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(font, text)
        if kind == 'GHOST' and st is not None and coplanar_cached(context, st):
            x, y = lay['slider']
            blf.color(font, 1.0, 0.25, 0.25, 1.0)
            lines = ('Faces lie on the mesh surface:', 'make the shape a little bigger', 'or smaller (Boolean artefacts)')
            for k, line in enumerate(lines):
                blf.position(font, (x - SLIDER_W / 2) * ui, (y - 26 - 14 * k) * ui, 0)
                blf.draw(font, line)
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_OT_hud_mode, MCH_OT_hud_apply, MCH_GT_hud_slider, MCH_GGT_prim_hud)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
