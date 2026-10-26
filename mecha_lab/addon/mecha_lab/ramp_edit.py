"""0.24.45 Alt: Ramp stays editable: pick the deep side AFTER drawing.

Working out which edge to draw first was the hard part, so an Alt: Ramp carve is kept live (one at a time):

* the mesh as it was before the carve is kept (a hidden copy) with the outline, the frozen view and the
  polygon's corners;
* ``set_side`` / the panel's < > buttons / Pick Edge (click a side in the viewport) choose the deep side - the
  mesh goes back to the copy and is carved again with that side deep;
* Carve Depth / Ramp Length / Ramp Soft re-carve it at once;
* Apply keeps it (the copy goes), Remove puts the mesh back as it was.

``corners`` and ``nearest_side`` are pure (tested headless).
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Vector

from . import core_geometry as cg

KEY = 'mch_ramp_live'
SCENE_KEY = 'mch_ramp_target'
_DRAW = [None]
_BUSY = [False]


def corners(loop, tol_frac=0.02):
    """The polygon's corners of a drawn (screen) outline: a clicked polygon stays as it is, a free-drawn one is
    simplified to its sides."""
    pts = [tuple(q) for q in loop]
    if len(pts) < 3:
        return pts
    per = sum(math.dist(pts[i - 1], pts[i]) for i in range(len(pts)))
    simple = cg.simplify_open(pts + [pts[0]], per * tol_frac)[:-1]
    return simple if len(simple) >= 3 else pts


def sides(loop):
    c = corners(loop)
    return [(c[i], c[(i + 1) % len(c)]) for i in range(len(c))]


def _seg_dist(p, a, b):
    ax, ay = a
    dx, dy = b[0] - ax, b[1] - ay
    ll = dx * dx + dy * dy
    t = 0.0 if ll < 1e-12 else max(0.0, min(1.0, ((p[0] - ax) * dx + (p[1] - ay) * dy) / ll))
    return math.hypot(p[0] - (ax + t * dx), p[1] - (ay + t * dy))


def nearest_side(point, segs):
    """Index of the segment (a, b) nearest ``point`` (all 2D)."""
    return min(range(len(segs)), key=lambda i: _seg_dist(point, *segs[i])) if segs else -1


# -----------------------------------------------------------------------------
# the live record
# -----------------------------------------------------------------------------


def record(ob):
    try:
        raw = ob.get(KEY) if ob is not None else None
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def live_target(context):
    name = context.scene.get(SCENE_KEY)
    ob = bpy.data.objects.get(name) if name else None
    return ob if ob is not None and record(ob) is not None else None


def _write(ob, rec):
    ob[KEY] = json.dumps(rec)


def _copy_into(src, dst):
    bm = bmesh.new()
    try:
        bm.from_mesh(src)
        bm.to_mesh(dst)
    finally:
        bm.free()
    dst.update()


def begin(context, target, loops, projector):
    """Before an Alt: Ramp carve on ``target``: keep the mesh as it is and the outline (an earlier live ramp is
    kept as it is first).  Returns the side that is deep (0)."""
    from . import armor_plate as ap
    old = live_target(context)
    if old is not None:
        finish(old)
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        return None
    backup = target.data.copy()
    backup.name = 'MCH_RampBackup_' + target.name
    backup.use_fake_user = True
    segs = sides(loops[0])
    corners_w = _corners_world(context, target, projector, [a for a, _b in segs])
    _write(target, {'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen, 'side': 0,
                    'backup': backup.name, 'corners': [[float(x), float(y)] for x, y in (a for a, _b in segs)],
                    'corners_w': corners_w})
    context.scene[SCENE_KEY] = target.name
    return 0


def _corners_world(context, target, projector, pts):
    """The corners laid on the target (its object space), for picking a side in any later view."""
    from . import cape_gen
    bvh, _lo, _hi = cape_gen._body(context, target)
    inv = target.matrix_world.inverted()
    out = []
    for xy in pts:
        o, d = projector.ray(xy)
        loc, _n, _i, _dd = bvh.ray_cast(o, d)
        out.append(list(inv @ loc) if loc is not None else None)
    return out


def finish(ob):
    """Keep the carve as it is: the copy and the record go."""
    rec = record(ob)
    if rec is not None:
        me = bpy.data.meshes.get(rec.get('backup', ''))
        if me is not None and me.users <= 1:
            bpy.data.meshes.remove(me)
        del ob[KEY]
    scene = bpy.context.scene
    if scene.get(SCENE_KEY) == ob.name:
        del scene[SCENE_KEY]


def remove(ob):
    """Put the mesh back as it was before the ramp."""
    rec = record(ob)
    if rec is None:
        return False
    me = bpy.data.meshes.get(rec.get('backup', ''))
    if me is not None:
        _copy_into(me, ob.data)
    finish(ob)
    return True


def recarve(context, ob):
    """The mesh back to the copy, carved again with the recorded side deep (and the current settings)."""
    from . import armor_plate as ap
    from . import base_mesh as bm_
    rec = record(ob)
    if rec is None or _BUSY[0]:
        return None
    me = bpy.data.meshes.get(rec.get('backup', ''))
    if me is None:
        raise cg.CutError('The ramp can no longer be changed (its saved mesh is gone): Apply or Remove it.')
    loops = [[tuple(q) for q in lp] for lp in rec['loops']]
    segs = sides(loops[0])
    side = rec.get('side', 0) % max(1, len(segs))
    projector = ap.thaw_projector(rec['proj'])
    _BUSY[0] = True
    try:
        _copy_into(me, ob.data)
        return bm_.carve_surface(context, loops, projector, bm_.scene_defaults(context), [ob], ramp_edge=segs[side],
                                 live=False)
    finally:
        _BUSY[0] = False


def set_side(context, ob, side):
    rec = record(ob)
    if rec is None:
        return None
    n = len(sides([tuple(q) for q in rec['loops'][0]]))
    rec['side'] = side % max(1, n)
    _write(ob, rec)
    return recarve(context, ob)


def refresh(context):
    """A Ramp slider changed: carve the live ramp again."""
    ob = live_target(context)
    if ob is None or _BUSY[0]:
        return
    try:
        recarve(context, ob)
    except cg.CutError:
        pass


# -----------------------------------------------------------------------------
# operators / panel / drawing
# -----------------------------------------------------------------------------


class MCH_OT_ramp_side(bpy.types.Operator):
    """Alt: Ramp still live: make the next / previous side of the polygon the deep one"""
    bl_idname = 'mch.ramp_side'
    bl_label = 'Ramp Deep Side'
    bl_options = {'REGISTER', 'UNDO'}
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        ob = live_target(context)
        if ob is None:
            return {'CANCELLED'}
        try:
            set_side(context, ob, record(ob).get('side', 0) + self.step)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        return {'FINISHED'}


class MCH_OT_ramp_pick(bpy.types.Operator):
    """Alt: Ramp still live: click a side of the polygon in the viewport - that side becomes the deep one
    (Esc / right click: stop)"""
    bl_idname = 'mch.ramp_pick'
    bl_label = 'Pick Deep Side'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return live_target(context) is not None

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'), None)
            if area is None:
                return {'CANCELLED'}
        context.window_manager.modal_handler_add(self)
        context.window.cursor_modal_set('EYEDROPPER')
        context.workspace.status_text_set('Click a side of the ramp polygon: it becomes the deep side   '
                                          'Esc / right click: done')
        return {'RUNNING_MODAL'}

    def _end(self, context):
        context.window.cursor_modal_restore()
        context.workspace.status_text_set(None)

    def modal(self, context, event):
        if event.type in {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            return {'PASS_THROUGH'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            return {'FINISHED'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            area = next((a for a in context.screen.areas if a.type == 'VIEW_3D'
                         and a.x <= event.mouse_x < a.x + a.width and a.y <= event.mouse_y < a.y + a.height), None)
            if area is None:
                return {'RUNNING_MODAL'}
            region = next((r for r in area.regions if r.type == 'WINDOW'), None)
            rv3d = area.spaces.active.region_3d
            ob = live_target(context)
            if region is None or ob is None:
                self._end(context)
                return {'CANCELLED'}
            side = pick_side(ob, region, rv3d, (event.mouse_x - region.x, event.mouse_y - region.y))
            if side >= 0:
                try:
                    set_side(context, ob, side)
                except cg.CutError as ex:
                    self.report({'WARNING'}, str(ex))
                area.tag_redraw()
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}


def screen_corners(ob, region, rv3d):
    from bpy_extras import view3d_utils
    rec = record(ob)
    out = []
    for c in rec.get('corners_w', []):
        p = None if c is None else view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
        out.append(None if p is None else (p.x, p.y))
    return out


def pick_side(ob, region, rv3d, xy):
    pts = screen_corners(ob, region, rv3d)
    segs, index = [], []
    for i in range(len(pts)):
        a, b = pts[i], pts[(i + 1) % len(pts)]
        if a is not None and b is not None:
            segs.append((a, b))
            index.append(i)
    k = nearest_side(xy, segs)
    return index[k] if k >= 0 else -1


class MCH_OT_ramp_apply(bpy.types.Operator):
    """Keep the ramp as it is (it can no longer change its deep side)"""
    bl_idname = 'mch.ramp_apply'
    bl_label = 'Apply Ramp'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = live_target(context)
        if ob is None:
            return {'CANCELLED'}
        finish(ob)
        return {'FINISHED'}


class MCH_OT_ramp_remove(bpy.types.Operator):
    """Take the ramp away: the mesh goes back to how it was before it"""
    bl_idname = 'mch.ramp_remove'
    bl_label = 'Remove Ramp'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = live_target(context)
        if ob is None or not remove(ob):
            return {'CANCELLED'}
        return {'FINISHED'}


def draw_panel(layout, context):
    ob = live_target(context)
    if ob is None:
        return
    rec = record(ob)
    n = len(sides([tuple(q) for q in rec['loops'][0]]))
    box = layout.box()
    box.label(text=f'RAMP (live) on {ob.name}: deep side {rec.get("side", 0) % max(1, n) + 1} / {n}', icon='MOD_SMOOTH')
    row = box.row(align=True)
    row.operator('mch.ramp_side', text='', icon='TRIA_LEFT').step = -1
    row.operator('mch.ramp_pick', text='Pick Edge', icon='EYEDROPPER')
    row.operator('mch.ramp_side', text='', icon='TRIA_RIGHT').step = 1
    row = box.row(align=True)
    row.operator('mch.ramp_apply', text='Apply', icon='CHECKMARK')
    row.operator('mch.ramp_remove', text='Remove', icon='X')


def _draw():
    try:
        context = bpy.context
        ob = live_target(context)
        if ob is None or context.region_data is None:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        rec = record(ob)
        pts = [None if c is None else ob.matrix_world @ Vector(c) for c in rec.get('corners_w', [])]
        n = len(pts)
        side = rec.get('side', 0) % max(1, n)
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('NONE')
        for i in range(n):
            a, b = pts[i], pts[(i + 1) % n]
            if a is None or b is None:
                continue
            gpu.state.line_width_set(5.0 if i == side else 1.5)
            sh.uniform_float('color', (1.0, 0.55, 0.1, 1.0) if i == side else (1.0, 1.0, 1.0, 0.5))
            batch_for_shader(sh, 'LINES', {'pos': [tuple(a), tuple(b)]}).draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


CLASSES = (MCH_OT_ramp_side, MCH_OT_ramp_pick, MCH_OT_ramp_apply, MCH_OT_ramp_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    if not bpy.app.background and _DRAW[0] is None:
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
