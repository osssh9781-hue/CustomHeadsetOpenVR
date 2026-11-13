"""0.24.150 Greeble Line (user, with a picture of a dark creature whose chest is covered in small machine parts: "표면에
기계 파츠가 다다닥 붙어 있는 이미지 만들 때 쓸 건데 내가 표면에 그으면 저렇게 메쉬들이 다다다닥 이어지게 만들어 줘, 내가 그은
선 따라서, 메쉬는 내가 픽킹할 수 있게 픽킹 옵션을 오른쪽 패널에").

Drag on a part: the meshes you picked are laid along the line, one after another, end to end - each one standing on
the surface (its bottom on it, its up = the surface's normal, its long side along the line).

    Parts           Pick Part (click meshes in the 3D view - as many as you like, Esc / RMB when done), Add Selected,
                    Starter Parts (five simple machine parts made beside the model, yours to change); a tick per part.
                    A part: Z up, its long side along X or Y (Axis: Auto = the longer one); its size as you made it.
    Order           In Turn (1 2 3 1 2 3 ...) or Random
    Part Size       x the size you made them;  Size Random
    Gap             between neighbours along the line (x a part's length; below 0 they overlap)
    Rows / Row Gap  side by side rows along the line (each row back on the surface)
    Sink            how far into the surface (x a part's height)
    Flip Random     some turned round (180),  Turn Random  a random turn about the normal
    Hide Parts      the picked parts hidden in the viewport and the render (the line still shows them)

A line is a live object on the part (it moves with it): select it and change anything - it is redone.  The values go on
to the next line.  Apply: real geometry (one mesh, the parts' materials).  Light: the parts are instances until Apply.
"""
from __future__ import annotations

import json
import math
import random
import time

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, \
    StringProperty
from mathutils import Matrix, Vector

TOOL = 'GREEBLE'
LINE_KEY = 'mch_greeble_line'          # on a line object (1)
STROKE_KEY = 'mch_greeble_stroke'      # on a line object: the drawn line, x y z nx ny nz per point (the part's space)
STARTER_TAG = 'mch_greeble_starter'
STARTER_COLL = 'Greeble Parts'
SIG_KEY = 'mch_greeble_sig'            # on a line's node group: the parts it was built for
LIVE_KEYS = ('order', 'axis', 'scale', 'scale_random', 'gap', 'rows', 'row_gap', 'sink', 'flip_random', 'turn_random',
             'seed')
_CASTERS = {}                          # target pointer -> (time, caster, vertex count)
_BUSY = [False]


# ---- settings ------------------------------------------------------------------------------------------------------

def _props(update):
    return {
        'order': EnumProperty(name='Order', default='SEQ', update=update, items=[
            ('SEQ', 'In Turn', 'The parts one after another (1 2 3 1 2 3 ...)'),
            ('RANDOM', 'Random', 'A random part each time')]),
        'axis': EnumProperty(name='Axis', default='AUTO', update=update, items=[
            ('AUTO', 'Auto', 'The part\'s longer side (X or Y) along the line'),
            ('X', 'X', 'The part\'s X along the line'), ('Y', 'Y', 'The part\'s Y along the line')]),
        'scale': FloatProperty(name='Part Size', default=1.0, min=0.01, max=100.0, soft_max=4.0, update=update,
                               description='The parts\' size, x the size you made them'),
        'scale_random': FloatProperty(name='Size Random', default=0.0, min=0.0, max=0.9, update=update,
                                      description='Each part a bit bigger or smaller (0.3 = up to 30 %)'),
        'gap': FloatProperty(name='Gap', default=0.0, min=-0.9, max=4.0, soft_max=1.0, update=update,
                             description='Between neighbours along the line, x a part\'s length (below 0: overlap)'),
        'rows': IntProperty(name='Rows', default=1, min=1, max=8, update=update,
                            description='Rows side by side along the line'),
        'row_gap': FloatProperty(name='Row Gap', default=0.0, min=-0.9, max=4.0, soft_max=1.0, update=update,
                                 description='Between the rows, x a part\'s width'),
        'sink': FloatProperty(name='Sink', default=0.0, min=-1.0, max=1.0, update=update,
                              description='How far into the surface, x a part\'s height (below 0: lifted off)'),
        'flip_random': BoolProperty(name='Flip Random', default=False, update=update,
                                    description='Some parts turned round (180 degrees)'),
        'turn_random': FloatProperty(name='Turn Random', default=0.0, min=0.0, max=math.pi, subtype='ANGLE',
                                     update=update, description='A random turn about the surface normal'),
        'seed': IntProperty(name='Seed', default=0, min=0, update=update, description='Another random mix'),
    }


def _upd_line(self, context):
    ob = self.id_data
    if _BUSY[0] or not is_line(ob):
        return
    rebuild(ob, context)
    st = settings(context)                            # (the values go on to the next line)
    if st is not None:
        _BUSY[0] = True
        try:
            for k in LIVE_KEYS:
                setattr(st, k, getattr(self, k))
        finally:
            _BUSY[0] = False


def _upd_scene(self, context):
    pass


def _upd_hide(self, context):
    for it in self.parts:
        ob = it.ob
        if ob is None:
            continue
        try:
            ob.hide_set(bool(self.hide_parts))
        except RuntimeError:
            pass
        ob.hide_render = bool(self.hide_parts)


def _poll_mesh(self, ob):
    return ob.type == 'MESH' and not ob.get(LINE_KEY)


class MCH_PG_GreeblePart(bpy.types.PropertyGroup):
    ob: PointerProperty(name='Part', type=bpy.types.Object, poll=_poll_mesh)
    use: BoolProperty(name='Use', default=True, description='Use this part in the next line')


class MCH_PG_GreebleLine(bpy.types.PropertyGroup):
    __annotations__ = {**_props(_upd_line), 'parts_json': StringProperty(default='[]')}


class MCH_PG_Greeble(bpy.types.PropertyGroup):
    __annotations__ = {**_props(_upd_scene),
                       'parts': CollectionProperty(type=MCH_PG_GreeblePart),
                       'hide_parts': BoolProperty(name='Hide Parts', default=False, update=_upd_hide,
                                                  description='The picked parts hidden in the viewport and the render '
                                                              '(the lines still show them)')}


def settings(context_or_scene):
    sc = getattr(context_or_scene, 'scene', context_or_scene)
    return getattr(sc, 'mch_greeble', None)


def is_line(ob):
    return ob is not None and bool(ob.get(LINE_KEY))


def picked(st):
    """The ticked parts that still exist (in list order, no repeats)."""
    out = []
    for it in st.parts:
        ob = it.ob
        if it.use and ob is not None and ob.type == 'MESH' and ob.name in bpy.data.objects and ob not in out:
            out.append(ob)
    return out


def add_part(st, ob):
    if ob is None or ob.type != 'MESH' or ob.get(LINE_KEY):
        return False
    if any(it.ob == ob for it in st.parts):
        return False
    it = st.parts.add()
    it.ob = ob
    if st.hide_parts:
        try:
            ob.hide_set(True)
        except RuntimeError:
            pass
        ob.hide_render = True
    return True


# ---- the parts -----------------------------------------------------------------------------------------------------

def part_info(ob, axis='AUTO'):
    """A part in its own space x its own scale: (length axis 0 / 1, length, width, height, centre x, centre y,
    bottom z, scale vector) - or None for an empty one."""
    bb = np.array([tuple(c) for c in ob.bound_box], float)
    if not len(bb):
        return None
    s = np.abs(np.array(tuple(ob.matrix_world.to_scale()), float))
    mn, mx = bb.min(0) * s, bb.max(0) * s
    ext = mx - mn
    if ext.max() <= 1e-9:
        return None
    ax = 0 if axis == 'X' else 1 if axis == 'Y' else (0 if ext[0] >= ext[1] else 1)
    c = (mn + mx) * 0.5
    return ax, max(ext[ax], 1e-6), max(ext[1 - ax], 1e-6), max(ext[2], 1e-6), c[0], c[1], mn[2], s


# ---- the drawn line ------------------------------------------------------------------------------------------------

class _Line:
    """A polyline on the surface (points, smoothed normals) measured along its length."""

    def __init__(self, pts, nrm):
        self.p = np.asarray(pts, float)
        n = np.asarray(nrm, float)
        for _ in range(3):                              # (face normals evened out along the line)
            q = n.copy()
            if len(n) > 2:
                q[1:-1] = 0.25 * n[:-2] + 0.5 * n[1:-1] + 0.25 * n[2:]
            n = q / np.maximum(np.linalg.norm(q, axis=1, keepdims=True), 1e-12)
        self.n = n
        seg = np.linalg.norm(np.diff(self.p, axis=0), axis=1) if len(self.p) > 1 else np.zeros(0)
        self.cum = np.concatenate([[0.0], np.cumsum(seg)])
        self.length = float(self.cum[-1])

    def at(self, s):
        s = min(max(s, 0.0), self.length)
        i = int(np.clip(np.searchsorted(self.cum, s) - 1, 0, max(len(self.p) - 2, 0)))
        if len(self.p) < 2:
            return Vector(self.p[0]), Vector(self.n[0])
        d = self.cum[i + 1] - self.cum[i]
        t = (s - self.cum[i]) / d if d > 1e-12 else 0.0
        p = self.p[i] * (1 - t) + self.p[i + 1] * t
        n = self.n[i] * (1 - t) + self.n[i + 1] * t
        return Vector(p), Vector(n).normalized()

    def tangent(self, s, h):
        a, _n = self.at(s - h)
        b, _n = self.at(s + h)
        d = b - a
        if d.length < 1e-12:
            a, _n = self.at(0.0)
            b, _n = self.at(self.length)
            d = b - a
        return d.normalized() if d.length > 1e-12 else Vector((1.0, 0.0, 0.0))


def placements(line, infos, cfg, unit, nearest=None):
    """Where the parts go along ``line`` (the part's space): (locations N x 3, quaternions N x 4 (w x y z),
    scales N x 3, picks N).  ``infos`` = part_info per part, ``unit`` = world size -> the part's space,
    ``nearest(p)`` -> (point, normal) on the surface (rows beside the line go back onto it)."""
    rng = random.Random(int(cfg['seed']))
    locs, quats, scls, picks = [], [], [], []
    if not infos or line.length <= 1e-9:
        return np.zeros((0, 3)), np.zeros((0, 4)), np.zeros((0, 3)), np.zeros(0, int)
    s = 0.0
    k = 0
    rows = max(1, int(cfg['rows']))
    while k < 20000:
        j = k % len(infos) if cfg['order'] == 'SEQ' else rng.randrange(len(infos))
        ax, ln, wd, ht, cx, cy, bz, sv = infos[j]
        f = cfg['scale'] * unit * (1.0 + rng.uniform(-1.0, 1.0) * cfg['scale_random'])
        L, W, H = ln * f, wd * f, ht * f
        if s + 0.5 * L > line.length + 1e-9:
            break
        mid = s + 0.5 * L
        p0, n0 = line.at(mid)
        t0 = line.tangent(mid, max(0.5 * L, line.length * 0.01))
        flip = cfg['flip_random'] and rng.random() < 0.5
        turn = rng.uniform(-1.0, 1.0) * cfg['turn_random']
        for r in range(rows):
            off = (r - (rows - 1) * 0.5) * W * (1.0 + cfg['row_gap'])
            p, n = p0, n0
            if abs(off) > 1e-12:
                b0 = n0.cross(t0).normalized()
                q = p0 + b0 * off
                hit = nearest(q) if nearest is not None else None
                if hit is not None:
                    p = Vector(hit[0])
                    n = (Vector(hit[1]).normalized() + n0).normalized()
                else:
                    p = q
            t = (t0 - n * t0.dot(n))
            t = t.normalized() if t.length > 1e-9 else n.orthogonal().normalized()
            b = n.cross(t)
            m = Matrix((t, b, n)).transposed()              # (columns: along, across, up)
            if ax == 1:                                     # (the part's Y along the line: its X = -across)
                m = Matrix((-b, t, n)).transposed()
            yaw = turn + (math.pi if flip else 0.0)
            if abs(yaw) > 1e-12:
                m = m @ Matrix.Rotation(yaw, 3, 'Z')
            sc = Vector(tuple(sv)) * f
            # the part's own middle (along / across) on the line, its bottom on the surface, sunk by Sink x height
            local = Vector((cx * f, cy * f, bz * f))
            loc = p - m @ local - n * (cfg['sink'] * H)
            locs.append(tuple(loc))
            quats.append(tuple(m.to_quaternion()))
            scls.append(tuple(sc))
            picks.append(j)
        s += L * (1.0 + cfg['gap'])
        k += 1
    return np.asarray(locs, float), np.asarray(quats, float), np.asarray(scls, float), np.asarray(picks, int)


def cfg_of(pg):
    return {k: getattr(pg, k) for k in LIVE_KEYS}


# ---- the line object -------------------------------------------------------------------------------------------------

def _caster(context, target):
    from . import geo_sculpt as gs
    key = target.as_pointer()
    n = len(target.data.vertices) if target.type == 'MESH' else 0
    hit = _CASTERS.get(key)
    if hit is not None and hit[2] == n and time.time() - hit[0] < 30.0:
        return hit[1]
    c = gs.SurfaceCaster(context, target)
    _CASTERS[key] = (time.time(), c, n)
    return c


def read_stroke(ob):
    a = np.asarray(ob.get(STROKE_KEY, []), float).reshape(-1, 6)
    return a[:, :3], a[:, 3:]


def write_stroke(ob, pts, nrm):
    ob[STROKE_KEY] = [float(v) for v in np.concatenate([np.asarray(pts, float), np.asarray(nrm, float)], 1).ravel()]


def _group(ob, parts):
    """The line's own node group for ``parts`` (rebuilt when the parts change): per part, an instance on the points
    that picked it; Realize (for Apply)."""
    sig = '|'.join(p.name for p in parts)
    mod = ob.modifiers.get('MCH Greeble')
    ng = mod.node_group if mod is not None else None
    if ng is not None and ng.get(SIG_KEY) == sig and ng.users <= 1:
        return mod
    if ng is None or ng.users > 1:
        ng = bpy.data.node_groups.new(f'MCH Greeble ({ob.name})', 'GeometryNodeTree')
        ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        ng.interface.new_socket('Realize', in_out='INPUT', socket_type='NodeSocketBool')
        ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    ng.nodes.clear()
    ng[SIG_KEY] = sig
    N, L = ng.nodes, ng.links
    gi = N.new('NodeGroupInput')
    gi.location = (-900, 0)
    go = N.new('NodeGroupOutput')
    go.location = (700, 0)

    def attr(kind, name, y):
        n = N.new('GeometryNodeInputNamedAttribute')
        n.data_type = kind
        n.inputs['Name'].default_value = name
        n.location = (-700, y)
        return n.outputs['Attribute']
    rot, scl, pick = attr('QUATERNION', 'mch_rot', -200), attr('FLOAT_VECTOR', 'mch_scale', -350), \
        attr('INT', 'mch_pick', -500)
    join = N.new('GeometryNodeJoinGeometry')
    join.location = (300, 0)
    for i, part in enumerate(parts):
        y = 300 - i * 260
        oi = N.new('GeometryNodeObjectInfo')
        oi.transform_space = 'ORIGINAL'
        oi.inputs['Object'].default_value = part
        oi.inputs['As Instance'].default_value = True
        oi.location = (-400, y)
        cmp = N.new('FunctionNodeCompare')
        cmp.data_type = 'INT'
        cmp.operation = 'EQUAL'
        cmp.location = (-400, y - 150)
        L.new(pick, cmp.inputs[0])
        cmp.inputs[1].default_value = i
        iop = N.new('GeometryNodeInstanceOnPoints')
        iop.location = (0, y)
        L.new(gi.outputs['Geometry'], iop.inputs['Points'])
        L.new(cmp.outputs['Result'], iop.inputs['Selection'])
        L.new(oi.outputs['Geometry'], iop.inputs['Instance'])
        L.new(rot, iop.inputs['Rotation'])
        L.new(scl, iop.inputs['Scale'])
        L.new(iop.outputs['Instances'], join.inputs[0])
    real = N.new('GeometryNodeRealizeInstances')
    real.location = (450, -150)
    L.new(join.outputs[0], real.inputs[0])
    sw = N.new('GeometryNodeSwitch')
    sw.input_type = 'GEOMETRY'
    sw.location = (550, 0)
    L.new(gi.outputs['Realize'], sw.inputs['Switch'])
    L.new(join.outputs[0], sw.inputs['False'])
    L.new(real.outputs[0], sw.inputs['True'])
    L.new(sw.outputs[0], go.inputs[0])
    if mod is None:
        mod = ob.modifiers.new('MCH Greeble', 'NODES')
    mod.node_group = ng
    return mod


def line_parts(ob):
    try:
        names = json.loads(ob.mch_greeble_line.parts_json)
    except (TypeError, ValueError):
        names = []
    return [bpy.data.objects[n] for n in names if n in bpy.data.objects and bpy.data.objects[n].type == 'MESH']


def rebuild(ob, context=None, caster=None):
    """The line's parts laid again along its drawn line (its own settings).  Returns how many parts."""
    context = context or bpy.context
    target = ob.parent
    parts = line_parts(ob)
    pts, nrm = read_stroke(ob)
    st = ob.mch_greeble_line
    infos = [part_info(p, st.axis) for p in parts]
    keep = [i for i, inf in enumerate(infos) if inf is not None]
    parts, infos = [parts[i] for i in keep], [infos[i] for i in keep]
    if target is not None and caster is None:
        try:
            caster = _caster(context, target)
        except (RuntimeError, AttributeError, ReferenceError):
            caster = None
    ms = target.matrix_world.to_scale() if target is not None else Vector((1, 1, 1))
    unit = 1.0 / max((abs(ms.x) + abs(ms.y) + abs(ms.z)) / 3.0, 1e-9)     # (world sizes -> the part's space)
    line = _Line(pts, nrm) if len(pts) else None
    if line is None:
        locs, quats, scls, picks = np.zeros((0, 3)), np.zeros((0, 4)), np.zeros((0, 3)), np.zeros(0, int)
    else:
        locs, quats, scls, picks = placements(line, infos, cfg_of(st), unit,
                                              caster.nearest if caster is not None else None)
    me = ob.data
    me.clear_geometry()
    n = len(locs)
    if n:
        me.vertices.add(n)
        me.vertices.foreach_set('co', locs.astype(np.float32).ravel())
    for name, kind, field, data in (('mch_rot', 'QUATERNION', 'value', quats), ('mch_scale', 'FLOAT_VECTOR', 'vector',
                                                                                  scls),
                                    ('mch_pick', 'INT', 'value', picks)):
        a = me.attributes.get(name)
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(name, kind, 'POINT')
        if n:
            a.data.foreach_set(field, np.asarray(data).astype(np.int32 if kind == 'INT' else np.float32).ravel())
    me.update()
    _group(ob, parts)
    ob.update_tag()
    return n


def new_line(context, target, pts, nrm, parts, pg):
    """A Greeble Line on ``target`` (its child, its space): ``parts`` along the drawn line, settings from ``pg``."""
    me = bpy.data.meshes.new('Greeble Line')
    ob = bpy.data.objects.new('Greeble Line', me)
    colls = target.users_collection or (context.scene.collection,)
    colls[0].objects.link(ob)
    ob.parent = target
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob[LINE_KEY] = 1
    write_stroke(ob, pts, nrm)
    ln = ob.mch_greeble_line
    _BUSY[0] = True
    try:
        for k in LIVE_KEYS:
            setattr(ln, k, getattr(pg, k))
        ln.parts_json = json.dumps([p.name for p in parts])
    finally:
        _BUSY[0] = False
    return ob


def apply_line(context, ob):
    """The line made real: one mesh with the parts (their materials); the live setup gone."""
    from . import geo_sculpt as gs
    mod = ob.modifiers.get('MCH Greeble')
    if mod is None or mod.node_group is None:
        return False
    gs.set_input(mod, 'Realize', True)
    dg = context.evaluated_depsgraph_get()
    dg.update()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    for a in [a for a in me.attributes if a.name in ('mch_rot', 'mch_scale', 'mch_pick')]:
        me.attributes.remove(a)
    ng = mod.node_group
    ob.modifiers.remove(mod)
    if ng is not None and ng.users == 0:
        bpy.data.node_groups.remove(ng)
    old = ob.data
    ob.data = me
    me.name = 'Greeble Parts'
    ob.name = 'Greeble Parts'
    if old.users == 0:
        bpy.data.meshes.remove(old)
    for k in (LINE_KEY, STROKE_KEY):
        if k in ob.keys():
            del ob[k]
    return True


def active_line(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_line(ob) else None


# ---- starter parts -------------------------------------------------------------------------------------------------

def _starter_meshes():
    """Five simple machine parts, Z up, long side along X, about 1 long."""
    out = []

    def box(bm, x0, x1, y0, y1, z0, z1):
        r = bmesh.ops.create_cube(bm, size=1.0)
        for v in r['verts']:
            v.co.x = x0 + (v.co.x + 0.5) * (x1 - x0)
            v.co.y = y0 + (v.co.y + 0.5) * (y1 - y0)
            v.co.z = z0 + (v.co.z + 0.5) * (z1 - z0)
        return r['verts']

    def finish(name, bm, bevel=0.0):
        if bevel > 0:
            bmesh.ops.bevel(bm, geom=list(bm.edges), offset=bevel, segments=1, affect='EDGES', profile=0.5,
                            clamp_overlap=True)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = False
        out.append((name, me))
    bm = bmesh.new()                                    # a plate with a raised block
    box(bm, -0.5, 0.5, -0.3, 0.3, 0.0, 0.1)
    box(bm, -0.25, 0.25, -0.18, 0.18, 0.1, 0.22)
    finish('Greeble Plate', bm, 0.015)
    bm = bmesh.new()                                    # ribs on a base
    box(bm, -0.5, 0.5, -0.25, 0.25, 0.0, 0.08)
    for i in range(5):
        x = -0.4 + i * 0.2
        box(bm, x - 0.05, x + 0.05, -0.22, 0.22, 0.08, 0.3)
    finish('Greeble Ribs', bm, 0.01)
    bm = bmesh.new()                                    # a pipe lying along X, with two collars
    r = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.16, radius2=0.16, depth=1.0,
                              matrix=Matrix.Translation((0, 0, 0.16)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
    for x in (-0.3, 0.3):
        bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=0.21, radius2=0.21, depth=0.1,
                              matrix=Matrix.Translation((x, 0, 0.16)) @ Matrix.Rotation(math.pi / 2, 4, 'Y'))
    del r
    finish('Greeble Pipe', bm)
    bm = bmesh.new()                                    # a wedge (a sloped block)
    vs = box(bm, -0.5, 0.5, -0.3, 0.3, 0.0, 0.3)
    for v in vs:
        if v.co.z > 0.15 and v.co.x > 0:
            v.co.z = 0.08
    finish('Greeble Wedge', bm, 0.01)
    bm = bmesh.new()                                    # a vent: a frame with slats
    box(bm, -0.5, 0.5, -0.32, 0.32, 0.0, 0.06)
    box(bm, -0.5, -0.42, -0.32, 0.32, 0.06, 0.18)
    box(bm, 0.42, 0.5, -0.32, 0.32, 0.06, 0.18)
    for i in range(6):
        x = -0.33 + i * 0.132
        box(bm, x - 0.025, x + 0.025, -0.3, 0.3, 0.06, 0.16)
    finish('Greeble Vent', bm, 0.006)
    return out


def make_starters(context, near=None):
    """The five starter parts in a collection beside the model (``near``), sized to it; added to the parts list."""
    sc = context.scene
    st = settings(sc)
    coll = bpy.data.collections.get(STARTER_COLL)
    if coll is None:
        coll = bpy.data.collections.new(STARTER_COLL)
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    size, at = 0.1, Vector((0.0, 0.0, 0.0))
    if near is not None:
        bb = [near.matrix_world @ Vector(c) for c in near.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        size = max((hi - lo).length * 0.05, 1e-3)
        at = Vector((hi.x + size * 2.0, (lo.y + hi.y) * 0.5, lo.z))
    made = []
    for i, (name, me) in enumerate(_starter_meshes()):
        ob = bpy.data.objects.new(name, me)
        ob[STARTER_TAG] = 1
        ob.scale = (size, size, size)
        ob.location = at + Vector((0.0, 0.0, i * size * 0.6))
        coll.objects.link(ob)
        made.append(ob)
        add_part(st, ob)
    return made


# ---- operators -----------------------------------------------------------------------------------------------------

def _draw_stroke(op, context):
    try:
        if context.region is None or context.region != op.region or len(op.screen) < 2:
            return
        from . import ui_gpu as ug
        ug.polyline(op.screen, (1.0, 0.55, 0.1, 0.9), 2.0)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


class MCH_OT_greeble_stroke(bpy.types.Operator):
    """Greeble Line: drag on a part - the picked meshes laid one after another along the line, standing on the
    surface (Esc while drawing: none)"""
    bl_idname = 'mch.greeble_stroke'
    bl_label = 'Greeble Line'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        from . import geo_sculpt as gs
        st = settings(context)
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit = gs.pick_part(context, xy)
        if st is None or hit is None:
            return {'PASS_THROUGH'}
        target = hit[0]
        if is_line(target) and target.parent is not None:
            target = target.parent                     # (drawn over a line: on the part under it)
        self.parts = picked(st)
        if not self.parts:
            self.report({'WARNING'}, 'Greeble Line: pick parts first (the window: Pick Part / Add Selected / '
                                     'Starter Parts)')
            return {'CANCELLED'}
        try:
            self.caster = _caster(context, target)
        except (RuntimeError, AttributeError, ReferenceError):
            return {'PASS_THROUGH'}
        first = self.caster.cast(context, xy)
        if first is None:
            return {'PASS_THROUGH'}
        self.target = target
        self.region = context.region
        self.screen = [xy]
        self.pts, self.nrm = [tuple(first[0])], [tuple(first[1])]
        # (points about every 4 px on the screen, in the part's space)
        ppw = gs.px_per_world(context.region, context.region_data, hit[1])
        ms = target.matrix_world.to_scale()
        self.step = (4.0 / max(ppw, 1e-9)) / max((abs(ms.x) + abs(ms.y) + abs(ms.z)) / 3.0, 1e-9)
        self.line = new_line(context, target, self.pts, self.nrm, self.parts, st)
        self.t_live = 0.0
        self._handle = bpy.types.SpaceView3D.draw_handler_add(_draw_stroke, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set(f'Greeble Line: {len(self.parts)} part(s) along the line   release = keep, '
                                     f'Esc = none')
        return {'RUNNING_MODAL'}

    def _live(self, final=False):
        from . import geo_sculpt as gs
        if len(self.pts) >= 3 and final:
            p, n = gs.smooth_line(self.pts, self.caster)
        else:
            p, n = np.asarray(self.pts, float), np.asarray(self.nrm, float)
        write_stroke(self.line, p, n)
        return rebuild(self.line, bpy.context, self.caster)

    def _end(self, context):
        if getattr(self, '_handle', None) is not None:
            bpy.types.SpaceView3D.draw_handler_remove(self._handle, 'WINDOW')
            self._handle = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def _drop(self):
        ob = self.line
        me, mod = ob.data, ob.modifiers.get('MCH Greeble')
        ng = mod.node_group if mod is not None else None
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            xy = (event.mouse_region_x, event.mouse_region_y)
            hit = self.caster.cast(context, xy)
            if hit is not None and (Vector(hit[0]) - Vector(self.pts[-1])).length >= self.step:
                self.pts.append(tuple(hit[0]))
                self.nrm.append(tuple(hit[1]))
                self.screen.append(xy)
                now = time.time()
                if now - self.t_live > 0.05:            # (the parts follow the line as it is drawn)
                    self._live()
                    self.t_live = now
            context.area.tag_redraw()
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            n = self._live(final=True) if len(self.pts) > 1 else 0
            self._end(context)
            if n == 0:
                self._drop()
                self.report({'INFO'}, 'Greeble Line: too short for one part (draw longer, or a smaller Part Size)')
                return {'CANCELLED'}
            for o in context.selected_objects:
                o.select_set(False)
            self.line.select_set(True)
            context.view_layer.objects.active = self.line
            self.report({'INFO'}, f'Greeble Line: {n} parts along the line (select it to change it, Apply to keep)')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            self._end(context)
            self._drop()
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_greeble_pick(bpy.types.Operator):
    """Pick Part: click meshes in the 3D view - each one goes into the parts list (Esc / RMB / Enter when done)"""
    bl_idname = 'mch.greeble_pick'
    bl_label = 'Pick Greeble Part'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'CANCELLED'}
        context.window.cursor_modal_set('EYEDROPPER')
        context.window_manager.modal_handler_add(self)
        context.area.header_text_set('Pick Part: click meshes to add them to the Greeble parts   Esc / RMB / Enter = '
                                     'done')
        self.added = 0
        return {'RUNNING_MODAL'}

    def _done(self, context):
        context.window.cursor_modal_restore()
        if context.area:
            context.area.header_text_set(None)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass

    def modal(self, context, event):
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            ob = pick_object(context, (event.mouse_region_x, event.mouse_region_y))
            if ob is not None and add_part(settings(context), ob):
                self.added += 1
                self.report({'INFO'}, f'Greeble part: {ob.name} added')
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self._done(context)
            self.report({'INFO'}, f'Greeble parts: {len(settings(context).parts)} ({self.added} picked now)')
            return {'FINISHED'}
        return {'PASS_THROUGH'}


def pick_object(context, xy):
    """The mesh object under the mouse (a Greeble Line: none - its parts are instances)."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
    try:
        hit, _loc, _n, _i, ob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    except (RuntimeError, TypeError):
        return None
    ob = getattr(ob, 'original', ob) if hit else None
    return ob if ob is not None and ob.type == 'MESH' and not is_line(ob) else None


class MCH_OT_greeble_parts(bpy.types.Operator):
    """The Greeble parts list: Add Selected (the selected meshes), Remove (this one), Clear, Starter Parts (five
    simple machine parts made beside the model), Use Picked (the selected line takes the ticked parts)"""
    bl_idname = 'mch.greeble_parts'
    bl_label = 'Greeble Parts'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    action: EnumProperty(items=[('ADD_SELECTED', 'Add Selected', ''), ('REMOVE', 'Remove', ''), ('CLEAR', 'Clear', ''),
                                ('TOGGLE', 'Use / Not', ''),
                                ('STARTER', 'Starter Parts', ''), ('USE_PICKED', 'Use Picked Parts', '')],
                         default='ADD_SELECTED', options={'SKIP_SAVE'})
    index: IntProperty(default=-1, options={'SKIP_SAVE'})

    def execute(self, context):
        st = settings(context)
        if st is None:
            return {'CANCELLED'}
        if self.action == 'ADD_SELECTED':
            n = sum(add_part(st, ob) for ob in context.selected_objects)
            msg = f'Greeble parts: {n} added' if n else 'Greeble parts: select meshes first (not a Greeble Line)'
        elif self.action == 'REMOVE':
            if not 0 <= self.index < len(st.parts):
                return {'CANCELLED'}
            ob = st.parts[self.index].ob
            if ob is not None and st.hide_parts:
                try:
                    ob.hide_set(False)
                except RuntimeError:
                    pass
                ob.hide_render = False
            st.parts.remove(self.index)
            msg = 'Greeble part removed from the list (the mesh itself kept)'
        elif self.action == 'TOGGLE':
            if not 0 <= self.index < len(st.parts):
                return {'CANCELLED'}
            it = st.parts[self.index]
            it.use = not it.use
            msg = f'Greeble part {it.ob.name if it.ob else ""}: {"used" if it.use else "not used"} in the next line'
        elif self.action == 'CLEAR':
            st.parts.clear()
            msg = 'Greeble parts: the list cleared (the meshes kept)'
        elif self.action == 'STARTER':
            near = active_line(context)
            near = near.parent if near is not None else context.active_object
            made = make_starters(context, near if near is not None and near.type == 'MESH' else None)
            msg = f'Greeble: {len(made)} starter parts made beside the model (collection "{STARTER_COLL}") - yours ' \
                  f'to change'
        else:
            ob = active_line(context)
            parts = picked(st)
            if ob is None or not parts:
                return {'CANCELLED'}
            ob.mch_greeble_line.parts_json = json.dumps([p.name for p in parts])
            rebuild(ob, context)
            msg = f'{ob.name}: {len(parts)} part(s)'
        self.report({'INFO'}, msg)
        try:
            from . import side_panel
            side_panel.dirty()
        except (ImportError, AttributeError):
            pass
        return {'FINISHED'}


class MCH_OT_greeble_apply(bpy.types.Operator):
    """Apply the selected Greeble Line(s): real geometry - one mesh with the parts (their materials), no longer live"""
    bl_idname = 'mch.greeble_apply'
    bl_label = 'Apply Greeble Line'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        lines = [o for o in context.selected_objects if is_line(o)] or (
            [context.active_object] if is_line(context.active_object) else [])
        n = sum(apply_line(context, ob) for ob in lines)
        if not n:
            self.report({'WARNING'}, 'Greeble: select a Greeble Line')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Greeble: {n} line(s) applied - real meshes now')
        return {'FINISHED'}


# ---- the tool --------------------------------------------------------------------------------------------------------

class MCH_TOOL_greeble(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.greeble_line'
    bl_label = 'Mecha Greeble Line'
    bl_description = ('Drag on a part: the meshes you picked laid one after another along the line, standing on the '
                      'surface.\nPick them in the window (Pick Part / Add Selected / Starter Parts)')
    bl_icon = 'ops.generic.select_paint'
    bl_widget = None
    bl_keymap = (
        ('mch.greeble_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        draw(layout, context)


HELP = ('Pick the meshes (Pick Part: click them), then drag on a part',
        'A part: Z up, its long side along the line (Axis)',
        'Select a line to change it; Apply = real geometry')


def draw(layout, context):
    """The window (the right panel): the parts to pick, the settings (of the selected line, else of the next one)."""
    st = settings(context)
    if st is None:
        return
    col = layout.column(align=True)
    col.label(text=f'Parts ({len(picked(st))} ticked)')
    for i, it in enumerate(st.parts):                # (one row a part: its name - click = ticked or not - and x)
        row = col.row(align=True)
        op = row.operator('mch.greeble_parts', text=(it.ob.name if it.ob is not None else '(gone)'),
                          depress=bool(it.use))
        op.action, op.index = 'TOGGLE', i
        op = row.operator('mch.greeble_parts', text='Remove')
        op.action, op.index = 'REMOVE', i
    row = col.row(align=True)
    row.operator('mch.greeble_pick', text='Pick Part', icon='EYEDROPPER')
    row.operator('mch.greeble_parts', text='Add Selected').action = 'ADD_SELECTED'
    row = col.row(align=True)
    row.operator('mch.greeble_parts', text='Starter Parts').action = 'STARTER'
    if st.parts:
        row.operator('mch.greeble_parts', text='Clear List').action = 'CLEAR'
    col.prop(st, 'hide_parts')
    ln = active_line(context)
    pg = ln.mch_greeble_line if ln is not None else st
    col = layout.column(align=True)
    col.label(text=f'{ln.name}: {len(ln.data.vertices)} parts (live)' if ln is not None else 'The next line')
    col.row(align=True).prop(pg, 'order', expand=True)
    col.row(align=True).prop(pg, 'axis', expand=True)
    for k in ('scale', 'scale_random', 'gap', 'rows', 'row_gap', 'sink', 'turn_random', 'seed'):
        col.prop(pg, k)
    col.prop(pg, 'flip_random')
    if ln is not None:
        row = col.row(align=True)
        row.operator('mch.greeble_parts', text='Use Picked Parts').action = 'USE_PICKED'
        row.operator('mch.greeble_apply', text='Apply')
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


CLASSES = (MCH_PG_GreeblePart, MCH_PG_GreebleLine, MCH_PG_Greeble, MCH_OT_greeble_stroke, MCH_OT_greeble_pick,
           MCH_OT_greeble_parts, MCH_OT_greeble_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_greeble = PointerProperty(type=MCH_PG_Greeble)
    bpy.types.Object.mch_greeble_line = PointerProperty(type=MCH_PG_GreebleLine)
    try:
        bpy.utils.register_tool(MCH_TOOL_greeble, after={'mecha.geo_sculpt'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_greeble, separator=True, group=False)
        except (ValueError, RuntimeError):
            pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_greeble)
    except (ValueError, RuntimeError, KeyError):
        pass
    for attr, owner in (('mch_greeble', bpy.types.Scene), ('mch_greeble_line', bpy.types.Object)):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    _CASTERS.clear()
