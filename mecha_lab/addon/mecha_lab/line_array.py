"""0.24.279 Line Array (user: "커브 어레이 말고도 그냥 직선이나 대각선 토글도 되고 내가 긋는 직선대로 어레이되는 툴 -
라쏘나 이런 거 다 있고 오토 셀렉트 액티브 다 있어야 돼").

Draw with any of the shared shapes; the part is repeated from where it is, the way the drawing goes:

* Path: Straight - from where the drawing starts to where it ends (Snap: Free / Straight (0 / 90 deg) / Diagonal
  (every 45 deg) on the screen); Follow - along the drawn path as it is; a closed shape (Rectangle, Circle, Ellipse,
  Polygon, Custom) - round its outline;
* Fill: Count copies spread to the end of the path, or one every Spacing;
* Align: each copy turned with the path (a curve / an outline); off: all as the part;
* Targets (the shared row): Auto - the part under the start of the drawing (else the selected); Selected - every
  selected part, each its own array; Active - the active part.

Each array is a live object of its own ("<part> Line Array"): the part's copies as instances (Geometry Nodes), where
the part moves / changes they follow; select it: Path / Count / Spacing / Align lay it again; Enter (Make Real) turns
it into a mesh.  The path lies in the plane through the part's centre facing the view it was drawn in.
"""
from __future__ import annotations

import json
import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Euler, Matrix, Quaternion, Vector

KEY = 'mch_line_array'          # on the array object: the path (json)
MOD = 'MCH Line Array'
TREE = 'MCH Line Array'
TREE_V = 2
CLOSED_SHAPES = {'RECT', 'CIRCLE', 'ELLIPSE', 'POLY', 'POLYGON', 'CUSTOM', 'STAR', 'HEX'}


# ---- the path ----------------------------------------------------------------------------------------------------

def snap_screen(p0, p1, snap):
    """The end point ``p1`` turned so the line from ``p0`` is at 0 / 90 deg (STRAIGHT) or every 45 deg (DIAG)."""
    if snap == 'FREE':
        return tuple(p1)
    dx, dy = p1[0] - p0[0], p1[1] - p0[1]
    ln = math.hypot(dx, dy)
    if ln < 1e-9:
        return tuple(p1)
    step = math.pi / 2 if snap == 'STRAIGHT' else math.pi / 4
    a = round(math.atan2(dy, dx) / step) * step
    return (p0[0] + math.cos(a) * ln, p0[1] + math.sin(a) * ln)


def screen_path(pts, shape, kind, snap):
    """(screen points, closed) of the drawing as the array's path."""
    pts = [tuple(p) for p in pts]
    if len(pts) < 2:
        return pts, False
    if shape in CLOSED_SHAPES and len(pts) >= 3:
        return pts, True
    if kind == 'STRAIGHT':
        return [pts[0], snap_screen(pts[0], pts[-1], snap)], False
    return pts, False


def _plane_point(projector, xy, co, no):
    o, d = projector.ray(xy)
    den = d.dot(no)
    if abs(den) < 1e-12:
        return None
    return o + d * ((co - o).dot(no) / den)


def world_path(projector, spts, origin):
    """The screen path on the plane through ``origin`` facing the view."""
    no = Vector(projector.view_dir).normalized()
    out = [_plane_point(projector, p, Vector(origin), no) for p in spts]
    return [p for p in out if p is not None], no


def layout(path, closed, fill, count, spacing):
    """[(distance along, point, tangent)] of the copies (not the part itself at the start)."""
    pts = [Vector(p) for p in path]
    if closed and (pts[0] - pts[-1]).length > 1e-9:
        pts.append(pts[0].copy())
    seg = [(a, b, (b - a).length) for a, b in zip(pts, pts[1:]) if (b - a).length > 1e-12]
    total = sum(s[2] for s in seg)
    if total <= 1e-12:
        return []
    if fill == 'COUNT':
        n = max(1, int(count))
        if closed:
            ds = [total * i / (n + 1) for i in range(1, n + 1)]
        else:
            ds = [total * i / n for i in range(1, n + 1)]
    else:
        sp = max(spacing, 1e-6)
        k = int(total / sp + 1e-6)
        if closed and abs(k * sp - total) < 1e-6:
            k -= 1                                    # (the last would sit on the part itself)
        ds = [sp * i for i in range(1, k + 1)][:5000]
    out = []
    for d in ds:
        acc = 0.0
        for a, b, ln in seg:
            if acc + ln >= d - 1e-9:
                t = (d - acc) / ln
                out.append((d, a.lerp(b, min(max(t, 0.0), 1.0)), (b - a).normalized()))
                break
            acc += ln
        else:
            a, b, _ln = seg[-1]
            out.append((d, b.copy(), (b - a).normalized()))
    return out


def first_tangent(path):
    pts = [Vector(p) for p in path]
    for a, b in zip(pts, pts[1:]):
        if (b - a).length > 1e-12:
            return (b - a).normalized()
    return Vector((1, 0, 0))


# ---- the live object -----------------------------------------------------------------------------------------------

def tree():
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Part', in_out='INPUT', socket_type='NodeSocketObject')
    ng.interface.new_socket('Realize', in_out='INPUT', socket_type='NodeSocketBool')   # (Make Real: real geometry)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    oi = N.new('GeometryNodeObjectInfo')
    oi.transform_space = 'ORIGINAL'                  # (the part's own geometry; its place / turn / size below)
    L.new(gi.outputs['Part'], oi.inputs['Object'])
    # the copies' points: offsets from the part (stored) + where the part is now
    sp_ = N.new('GeometryNodeSetPosition')
    L.new(gi.outputs['Geometry'], sp_.inputs['Geometry'])
    L.new(oi.outputs['Location'], sp_.inputs['Offset'])
    turn = N.new('GeometryNodeInputNamedAttribute')
    turn.data_type = 'FLOAT_VECTOR'
    turn.inputs['Name'].default_value = 'mch_turn'
    e2r = N.new('FunctionNodeEulerToRotation')
    L.new(turn.outputs['Attribute'], e2r.inputs['Euler'])
    rot = N.new('FunctionNodeRotateRotation')                    # (the part's turn, then the copy's own turn)
    rot.rotation_space = 'GLOBAL'
    L.new(oi.outputs['Rotation'], rot.inputs['Rotation'])
    L.new(e2r.outputs['Rotation'], rot.inputs['Rotate By'])
    inst = N.new('GeometryNodeInstanceOnPoints')
    L.new(sp_.outputs['Geometry'], inst.inputs['Points'])
    L.new(oi.outputs['Geometry'], inst.inputs['Instance'])
    L.new(rot.outputs['Rotation'], inst.inputs['Rotation'])
    L.new(oi.outputs['Scale'], inst.inputs['Scale'])
    real = N.new('GeometryNodeRealizeInstances')
    L.new(inst.outputs['Instances'], real.inputs['Geometry'])
    sw = N.new('GeometryNodeSwitch')
    sw.input_type = 'GEOMETRY'
    L.new(gi.outputs['Realize'], sw.inputs['Switch'])
    L.new(inst.outputs['Instances'], sw.inputs['False'])
    L.new(real.outputs['Geometry'], sw.inputs['True'])
    L.new(sw.outputs['Output'], go.inputs['Geometry'])
    for i, n in enumerate((gi, oi, turn, e2r, rot, sp_, inst, go)):
        n.location = (-900 + 170 * i, -80 * (i % 2))
    ng['mch_v'] = TREE_V
    return ng


def _data(ob):
    try:
        return json.loads(ob.get(KEY, '{}'))
    except ValueError:
        return {}


def is_array(ob):
    return ob is not None and bool(ob.get(KEY))


def rebuild(ob):
    """The array object's points from its stored path and its settings."""
    d = _data(ob)
    st = ob.mch_larray
    part = st.part
    if not d or part is None:
        return 0
    path = [Vector(p) for p in d['path']]
    no = Vector(d['normal'])
    lay = layout(path, d.get('closed', False), st.fill, st.count, st.spacing)
    t0 = first_tangent(path)
    me = ob.data
    me.clear_geometry()
    me.vertices.add(len(lay))
    co = []
    turns = []
    for _dist, p, t in lay:
        co.extend(p)                                  # (offsets from the part's centre)
        if st.align:
            a = t0.cross(t).dot(no)
            ang = math.atan2(a, t0.dot(t))
            turns.extend(Quaternion(no, ang).to_euler())
        else:
            turns.extend((0.0, 0.0, 0.0))
    me.vertices.foreach_set('co', co)
    at = me.attributes.get('mch_turn') or me.attributes.new('mch_turn', 'FLOAT_VECTOR', 'POINT')
    at.data.foreach_set('vector', turns)
    me.update()
    ob.update_tag()
    return len(lay)


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_array(ob):
        rebuild(ob)


def _upd_path(self, context):
    """Straight / Follow changed on a live array: the path made again from the stored drawing."""
    ob = self.id_data
    if not (isinstance(ob, bpy.types.Object) and is_array(ob)):
        return
    d = _data(ob)
    raw = d.get('raw')
    if not raw or d.get('closed'):
        return
    pts = [Vector(p) for p in raw]
    if self.path == 'STRAIGHT':
        end = pts[-1]
        if self.snap != 'FREE':                   # (snapped in the drawing's own plane, as on the screen)
            ax, ay = Vector(d['right']), Vector(d['up'])
            v = end - pts[0]
            sx, sy = snap_screen((0.0, 0.0), (v.dot(ax), v.dot(ay)), self.snap)
            end = pts[0] + ax * sx + ay * sy
        path = [pts[0], end]
    else:
        path = pts
    d['path'] = [tuple(p) for p in path]
    ob[KEY] = json.dumps(d)
    rebuild(ob)


class MCH_PG_LineArray(bpy.types.PropertyGroup):
    part: PointerProperty(type=bpy.types.Object, name='Part', options={'HIDDEN'})
    path: EnumProperty(name='Path', default='STRAIGHT', update=_upd_path, items=[
        ('STRAIGHT', 'Straight', 'A straight line from where the drawing starts to where it ends'),
        ('FOLLOW', 'Follow', 'Along the drawn path as it is (a closed shape: always round its outline)')])
    snap: EnumProperty(name='Snap', default='FREE', update=_upd_path, items=[
        ('FREE', 'Free', 'The line at any angle'),
        ('STRAIGHT', 'Straight', 'The line at 0 / 90 deg on the screen (across / up and down)'),
        ('DIAG', 'Diagonal', 'The line at every 45 deg on the screen (straight and diagonal)')])
    fill: EnumProperty(name='Fill', default='COUNT', update=_upd, items=[
        ('COUNT', 'Count', 'This many copies spread to the end of the path'),
        ('SPACING', 'Spacing', 'A copy every Spacing along the path')])
    count: IntProperty(name='Count', default=5, min=1, soft_max=50, max=5000, update=_upd,
                       description='How many copies (the part itself not counted)')
    spacing: FloatProperty(name='Spacing', default=0.5, min=0.0001, soft_max=5.0, subtype='DISTANCE', update=_upd,
                           description='The distance between copies along the path')
    align: BoolProperty(name='Align', default=False, update=_upd,
                        description='Each copy turned with the path (a curve / an outline); off: all as the part')


def _sources(context, projector, spts):
    """The parts to repeat (the Targets row): Auto - under the drawing's start (else its end / the selected),
    Selected - every selected part, Active - the active part."""
    from . import target_rules as tr
    md = tr.mode(context)
    meshes = [o for o in context.selected_objects if o.type == 'MESH' and not is_array(o)]
    act = context.active_object
    if md == 'SELECTED':
        return meshes
    if md == 'ACTIVE':
        return [act] if act is not None and act.type == 'MESH' and not is_array(act) else []
    dg = context.evaluated_depsgraph_get()
    for xy in (spts[0], spts[-1]):
        o, d = projector.ray(xy)
        try:
            hit, _loc, _n, _i, ob, _m = tr.scene_ray(context, dg, o, d)
        except (RuntimeError, ReferenceError, AttributeError):
            hit, ob = False, None
        if hit and ob is not None and ob.type == 'MESH':
            ob = ob.original
            if is_array(ob) and ob.mch_larray.part is not None:
                ob = ob.mch_larray.part
            return [ob]
    if meshes:
        return meshes
    return [act] if act is not None and act.type == 'MESH' and not is_array(act) else []


def make(context, part, projector, spts_raw, shape, settings):
    """A live Line Array of ``part`` from the drawing.  Returns the new object, or None (nothing to lay)."""
    st = settings
    spts, closed = screen_path(spts_raw, shape, st.path, st.snap)
    origin = part.matrix_world.translation.copy()
    wpath, no = world_path(projector, spts, origin)
    raw, _no = world_path(projector, [tuple(p) for p in spts_raw], origin)
    if len(wpath) < 2:
        return None
    start = wpath[0]
    path = [p - start for p in wpath]                 # (offsets: the part sits at the start)
    rawo = [p - raw[0] for p in raw] if raw else path
    right = (projector.rot @ Vector((1, 0, 0))) if hasattr(projector, 'rot') else None
    if right is None:
        try:
            right = projector.rv3d.view_rotation @ Vector((1, 0, 0))
        except AttributeError:
            right = Vector((1, 0, 0))
    up = right.cross(no).normalized()
    me = bpy.data.meshes.new(part.name + ' Line Array')
    ob = bpy.data.objects.new(part.name + ' Line Array', me)
    for c in part.users_collection:
        c.objects.link(ob)
        break
    else:
        context.scene.collection.objects.link(ob)
    ob[KEY] = json.dumps({'path': [tuple(p) for p in path], 'raw': [tuple(p) for p in rawo], 'closed': closed,
                          'normal': tuple(no), 'right': tuple(right.normalized()), 'up': tuple(up)})
    a = ob.mch_larray
    a.part = part
    for k in ('path', 'snap', 'fill', 'count', 'spacing', 'align'):
        try:
            setattr(a, k, getattr(st, k))
        except (AttributeError, TypeError):
            pass
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = tree()
    from . import geo_sculpt as gs
    gs.set_input(mod, 'Part', part)
    rebuild(ob)
    return ob


def perform(context, pts, shape, projector):
    """The drawing finished: a Line Array of each target part.  Returns the report."""
    if len(pts) < 2:
        return 'Line Array: draw a line (2 points or more)'
    st = context.scene.mch_larray
    spts, _closed = screen_path(pts, shape, st.path, st.snap)
    parts = _sources(context, projector, spts)
    if not parts:
        return 'Line Array: no part - start the line on a part (Auto), or select one'
    made = []
    for p in parts:
        ob = make(context, p, projector, pts, shape, st)
        if ob is not None:
            made.append(ob)
    if not made:
        return 'Line Array: the line is too short'
    for o in list(context.selected_objects):
        o.select_set(False)
    for o in made:
        o.select_set(True)
    context.view_layer.objects.active = made[-1]
    n = len(made[-1].data.vertices)
    return (f'Line Array: {", ".join(p.name for p in parts)} - {n} copies'
            + (' each' if len(made) > 1 else '') + ' (select it: Count / Spacing / Path; Enter: Make Real)')


def make_real(context, ob):
    """The array object as a mesh of its own (the copies real geometry)."""
    if not is_array(ob):
        return False
    mod = ob.modifiers.get(MOD)
    from . import geo_sculpt as gs
    if mod is not None:
        if mod.node_group is None or mod.node_group.get('mch_v') != TREE_V:
            part = ob.mch_larray.part
            mod.node_group = tree()
            gs.set_input(mod, 'Part', part)
        gs.set_input(mod, 'Realize', True)
    context.view_layer.update()
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    part = ob.mch_larray.part
    if part is not None and part.type == 'MESH':
        for mat in part.data.materials:
            if mat is not None and mat.name not in me.materials:
                me.materials.append(mat)
    old = ob.data
    ob.data = me
    if mod is not None:
        ob.modifiers.remove(mod)
    del ob[KEY]
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return True


class MCH_OT_line_array_real(bpy.types.Operator):
    """Make Real: the selected Line Arrays turned into meshes (the copies real geometry, no longer live)"""
    bl_idname = 'mch.line_array_real'
    bl_label = 'Make Real'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(is_array(o) for o in context.selected_objects) or is_array(context.active_object)

    def execute(self, context):
        obs = [o for o in context.selected_objects if is_array(o)]
        if is_array(context.active_object) and context.active_object not in obs:
            obs.append(context.active_object)
        n = sum(1 for o in obs if make_real(context, o))
        self.report({'INFO'}, f'Line Array: {n} made real')
        return {'FINISHED'}


def draw(layout, context):
    """The tool window: the settings for the next drawing, or those of the selected Line Array."""
    ob = context.active_object
    live = is_array(ob)
    st = ob.mch_larray if live else context.scene.mch_larray
    box = layout.box()
    col = box.column(align=True)
    col.label(text=('Line Array: ' + ob.name) if live else 'Line Array', icon='STRIP_COLOR_05')
    col.prop(st, 'path', expand=True)
    if st.path == 'STRAIGHT':
        col.prop(st, 'snap', expand=True)
    col.prop(st, 'fill', expand=True)
    if st.fill == 'COUNT':
        col.prop(st, 'count')
    else:
        col.prop(st, 'spacing')
    col.prop(st, 'align')
    if live:
        col.operator('mch.line_array_real', text='Make Real (Enter)')
    col.label(text='Draw from a part: copies along the line')


CLASSES = (MCH_PG_LineArray, MCH_OT_line_array_real)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_larray = PointerProperty(type=MCH_PG_LineArray)
    bpy.types.Object.mch_larray = PointerProperty(type=MCH_PG_LineArray)


def unregister():
    for name in ('mch_larray',):
        for t in (bpy.types.Scene, bpy.types.Object):
            if hasattr(t, name):
                delattr(t, name)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
