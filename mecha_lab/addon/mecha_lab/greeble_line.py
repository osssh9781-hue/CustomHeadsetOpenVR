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

0.24.151 (user: "그리블 라인을 크리쳐 탭도 만들어 줘, 비늘 전용이나 디테일 전용으로") Scale Line (the Creature
tools): the same lines with their own parts list and settings - Scale Parts (five scale shapes laid overlapping in
staggered rows, leaning a little like shingles) or Detail Parts (spikes, bumps, nubs, fins, warts, scattered), or
your own.  Stagger: every second row half a part along (scales / bricks).

A line is a live object on the part (it moves with it): select it and change anything - it is redone.  The values go on
to the next line.  Apply: real geometry (one mesh, the parts' materials).  Light: the parts are instances until Apply.

0.24.154 (user: "쉬프트 누르고 라쏘로 그리면 그 스탬프 베이스로 만들어 줘, 그리블이랑 크리쳐 둘 다") Stamp: Shift + draw
(the shared lasso shapes - Lasso, Curve Lasso, Rectangle, Circle, Ellipse, Free Draw) makes a part from the outline: a
live Base Mesh (Greeble Line: Flat / Chamfer / Bevel / Dome) or Creature Base Mesh (Scale Line: Puff / Ridge / Pillow)
as big as drawn on the surface, Stamp Height x its short side tall, standing beside the model, in the list and ticked.
Select a stamp: its Height / Border / Puff ... in the window - every line using it follows.
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
NAV_EVENTS = {'MIDDLEMOUSE', 'WHEELUPMOUSE', 'WHEELDOWNMOUSE', 'WHEELINMOUSE', 'WHEELOUTMOUSE', 'TRACKPADPAN',
              'TRACKPADZOOM', 'MOUSEROTATE', 'MOUSESMARTZOOM'}
LINE_KEY = 'mch_greeble_line'          # on a line object (1)
STROKE_KEY = 'mch_greeble_stroke'      # on a line object: the drawn line, x y z nx ny nz per point (the part's space)
STARTER_TAG = 'mch_greeble_starter'
STARTER_COLL = 'Greeble Parts'
SIG_KEY = 'mch_greeble_sig'            # on a line's node group: the parts it was built for
LIVE_KEYS = ('order', 'axis', 'up', 'turn', 'tilt', 'scale', 'scale_random', 'gap', 'rows', 'row_gap', 'sink',
             'flip_random', 'turn_random', 'seed', 'stagger', 'edge_shrink')
KINDS = ('MECH', 'CREATURE')
UP_AXES = {'POS_X': (0, 1.0), 'NEG_X': (0, -1.0), 'POS_Y': (1, 1.0), 'NEG_Y': (1, -1.0), 'POS_Z': (2, 1.0),
           'NEG_Z': (2, -1.0)}
_BUSY = [False]


# ---- settings ------------------------------------------------------------------------------------------------------

def _props(update):
    return {
        'order': EnumProperty(name='Order', default='SEQ', update=update, items=[
            ('SEQ', 'In Turn', 'The parts one after another (1 2 3 1 2 3 ...)'),
            ('RANDOM', 'Random', 'A random part each time')]),
        'axis': EnumProperty(name='Along', default='AUTO', update=update, items=[
            ('AUTO', 'Auto', 'The part\'s longer side (of the two that are not Up) along the line'),
            ('X', 'X', 'The part\'s X along the line'), ('Y', 'Y', 'The part\'s Y along the line'),
            ('Z', 'Z', 'The part\'s Z along the line (when Up is X or Y)')]),
        # 0.24.151 (user: "벽에 붙는 방향을 내가 맘대로 조절하게 해 줘") which side of the part faces out of the wall,
        # a turn on the wall, a lean along the line
        'up': EnumProperty(name='Up', default='POS_Z', update=update, items=[
            ('POS_Z', '+Z', 'The part\'s +Z away from the surface (it stands on its bottom)'),
            ('NEG_Z', '-Z', 'The part\'s -Z away from the surface (upside down: its top on the surface)'),
            ('POS_X', '+X', 'The part\'s +X away from the surface (on its side)'),
            ('NEG_X', '-X', 'The part\'s -X away from the surface'),
            ('POS_Y', '+Y', 'The part\'s +Y away from the surface (on its front / back)'),
            ('NEG_Y', '-Y', 'The part\'s -Y away from the surface')]),
        'turn': FloatProperty(name='Turn', default=0.0, min=-math.pi, max=math.pi, subtype='ANGLE', update=update,
                              description='Every part turned on the surface (about the surface normal): 90 = '
                                          'across the line'),
        'tilt': FloatProperty(name='Tilt', default=0.0, min=-math.radians(85), max=math.radians(85), subtype='ANGLE',
                              update=update, description='Every part leaning forward / back along the line (about '
                                                         'its bottom edge across the line)'),
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
        'stagger': BoolProperty(name='Stagger', default=False, update=update,
                                description='Every second row half a part along (scales, bricks)'),
        # 0.24.152 (user: "그리블들은 가생이에 있는 로우들이 점점 작아지는 옵션도 만들어 줘")
        'edge_shrink': FloatProperty(name='Edge Rows Smaller', default=0.0, min=0.0, max=0.9, update=update,
                                     description='The rows away from the middle get smaller, step by step (0.5: the '
                                                 'outermost row half size) - each row packed with its own size'),
    }


def _upd_line(self, context):
    ob = self.id_data
    if _BUSY[0] or not is_line(ob):
        return
    rebuild(ob, context)
    st = settings(context, self.kind)                 # (the values go on to the next line of that tool)
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
    __annotations__ = {**_props(_upd_line), 'parts_json': StringProperty(default='[]'),
                       'kind': StringProperty(default='MECH')}


STAMP_PROFILE_ITEMS = [   # 0.24.154 the stamp's profile: Base Mesh's (Greeble Line) / Creature Base Mesh's (Scale Line)
    ('FLAT', 'Flat', 'Flat top, straight sides'),
    ('CHAMFER', 'Chamfer', 'Flat top, its border cut at an angle'),
    ('BEVEL', 'Bevel', 'Flat top, its border rounded'),
    ('DOME', 'Dome', 'The whole top bulges from the border in'),
    ('PUFF', 'Puff', 'A round lump (a sculpting base)'),
    ('RIDGE', 'Ridge', 'Rising to a sharp ridge along the middle'),
    ('PILLOW', 'Pillow', 'Flat in the middle, the edge rounded')]


class MCH_PG_Greeble(bpy.types.PropertyGroup):
    __annotations__ = {**_props(_upd_scene),
                       'parts': CollectionProperty(type=MCH_PG_GreeblePart),
                       'hide_parts': BoolProperty(name='Hide Parts', default=False, update=_upd_hide,
                                                  description='The picked parts hidden in the viewport and the render '
                                                              '(the lines still show them)'),
                       # 0.24.154 Shift + draw: a part from the outline (a stamp)
                       'stamp_profile': EnumProperty(name='Stamp Profile', items=STAMP_PROFILE_ITEMS, default='CHAMFER',
                                                     description='The next stamp (Shift + draw): Greeble Line - Flat / '
                                                                 'Chamfer / Bevel / Dome (Base Mesh), Scale Line - Puff / '
                                                                 'Ridge / Pillow (Creature Base Mesh)'),
                       'stamp_height': FloatProperty(name='Stamp Height', default=0.3, min=0.02, soft_max=2.0,
                                                     description='The next stamp\'s height, x its outline\'s short side '
                                                                 '(Puff / Ridge / Pillow: each side of the middle)'),
                       'stamp_edge': FloatProperty(name='Stamp Border', default=0.35, min=0.0, soft_max=1.0,
                                                   description='Chamfer / Bevel: the border, x the stamp\'s height'),
                       'stamp_alone': BoolProperty(name='Use Only the New Stamp', default=True,
                                                   description='A new stamp is ticked alone (the other parts unticked - '
                                                               'tick them again to mix)')}


def settings(context_or_scene, kind='MECH'):
    """The settings and parts list of Greeble Line (MECH) or Scale Line (CREATURE, 0.24.151)."""
    sc = getattr(context_or_scene, 'scene', context_or_scene)
    return getattr(sc, 'mch_cgreeble' if kind == 'CREATURE' else 'mch_greeble', None)


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

def part_info(ob, axis='AUTO', up='POS_Z'):
    """A part in its own space x its own scale, for ``up`` (its side away from the surface) and ``axis`` (its side
    along the line): (length, width, height, the bottom middle (3), scale vector, the part's axes as columns: along,
    up, across) - or None for an empty one."""
    bb = np.array([tuple(c) for c in ob.bound_box], float)
    if not len(bb):
        return None
    s = np.abs(np.array(tuple(ob.matrix_world.to_scale()), float))
    mn, mx = bb.min(0) * s, bb.max(0) * s
    ext = mx - mn
    if ext.max() <= 1e-9:
        return None
    u, su = UP_AXES.get(up, (2, 1.0))
    rest = [i for i in range(3) if i != u]
    want = {'X': 0, 'Y': 1, 'Z': 2}.get(axis)
    a = want if want in rest else (rest[0] if ext[rest[0]] >= ext[rest[1]] else rest[1])
    c = rest[1] if a == rest[0] else rest[0]
    mid = (mn + mx) * 0.5
    bottom = mid.copy()
    bottom[u] = mn[u] if su > 0 else mx[u]              # (the side on the surface)
    A = Vector([1.0 if i == a else 0.0 for i in range(3)])
    U = Vector([su if i == u else 0.0 for i in range(3)])
    axes = Matrix((A, U, A.cross(U))).transposed()      # (columns: along, up, along x up)
    return (max(ext[a], 1e-6), max(ext[c], 1e-6), max(ext[u], 1e-6), bottom, s, axes)


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


def row_layout(rows, shrink, width, row_gap):
    """(size factor, across offset) per row: the middle row(s) full size, the rows outwards smaller by ``shrink`` at
    the outermost, each row ``row_gap`` x their widths beside the one inside it (``width`` = a full-size width)."""
    rows = max(1, int(rows))
    half = (rows - 1) * 0.5
    lift = 0.0 if rows % 2 else 0.5                    # (an even count: the two middle rows are the middle)
    kmax = half - lift
    fac = [1.0 - shrink * ((abs(r - half) - lift) / kmax) if kmax > 0 else 1.0 for r in range(rows)]
    W = [width * f for f in fac]
    off = [0.0] * rows
    c = rows // 2
    step = 1.0 + row_gap
    if rows % 2 == 0:                                   # (two middle rows either side of the line)
        off[c], off[c - 1] = W[c] * 0.5 * step, -W[c - 1] * 0.5 * step
        inner_hi, inner_lo = c, c - 1
    else:
        inner_hi = inner_lo = c
    for r in range(inner_hi + 1, rows):
        off[r] = off[r - 1] + (W[r - 1] + W[r]) * 0.5 * step
    for r in range(inner_lo - 1, -1, -1):
        off[r] = off[r + 1] - (W[r + 1] + W[r]) * 0.5 * step
    return list(zip(fac, off))


def placements(line, infos, cfg, unit, nearest=None):
    """Where the parts go along ``line`` (the part's space): (locations N x 3, quaternions N x 4 (w x y z),
    scales N x 3, picks N).  ``infos`` = part_info per part, ``unit`` = world size -> the part's space,
    ``nearest(p)`` -> (point, normal) on the surface (rows beside the line go back onto it).  0.24.152 each row laid
    on its own (Edge Rows Smaller: the outer rows smaller and packed with their own size)."""
    rng = random.Random(int(cfg['seed']))
    locs, quats, scls, picks = [], [], [], []
    if not infos or line.length <= 1e-9:
        return np.zeros((0, 3)), np.zeros((0, 4)), np.zeros((0, 3)), np.zeros(0, int)
    ct, st_ = abs(math.cos(cfg['turn'])), abs(math.sin(cfg['turn']))
    w_mean = float(np.mean([st_ * inf[0] + ct * inf[1] for inf in infos])) * cfg['scale'] * unit
    layout = row_layout(cfg['rows'], cfg.get('edge_shrink', 0.0), w_mean, cfg['row_gap'])
    for r, (rf, off) in enumerate(layout):
        s = 0.0
        k = 0
        first = True
        while k < 20000:
            j = k % len(infos) if cfg['order'] == 'SEQ' else rng.randrange(len(infos))
            ln, wd, ht, bottom, sv, axes = infos[j]
            f = cfg['scale'] * unit * rf * (1.0 + rng.uniform(-1.0, 1.0) * cfg['scale_random'])
            L0, W0, H = ln * f, wd * f, ht * f
            # (turned / leaning: what it takes up along and across the line - end to end still)
            L, W = ct * L0 + st_ * W0, st_ * L0 + ct * W0
            L = abs(math.cos(cfg['tilt'])) * L + abs(math.sin(cfg['tilt'])) * H
            if first and cfg.get('stagger') and r % 2:
                s = 0.5 * L * (1.0 + cfg['gap'])          # (every second row half a part along)
            first = False
            if s + 0.5 * L > line.length + 1e-9:
                break
            mid = s + 0.5 * L
            flip = cfg['flip_random'] and rng.random() < 0.5
            turn = rng.uniform(-1.0, 1.0) * cfg['turn_random']
            p0, n0 = line.at(mid)
            t0 = line.tangent(mid, max(0.5 * L, line.length * 0.01))
            b0 = n0.cross(t0)
            b0 = b0.normalized() if b0.length > 1e-12 else n0.orthogonal().normalized()
            q = p0 + b0 * off
            p, n = q, n0
            hit = nearest(q) if nearest is not None else None
            if hit is not None:
                # 0.24.151 (a high-poly human) every part back on the surface, its up = the surface under its whole
                # footprint (five points: the middle and the ends / sides), not the line's averaged normal
                p = Vector(hit[0])
                acc = Vector(hit[1]).normalized()
                for d in (t0 * (0.35 * L), t0 * (-0.35 * L), b0 * (0.35 * W), b0 * (-0.35 * W)):
                    h2 = nearest(p + d)
                    if h2 is not None:
                        acc += Vector(h2[1]).normalized()
                n = acc.normalized() if acc.length > 1e-9 else n0
                if n.dot(n0) < 0.0:                         # (a thin wall's far side: keep the drawn side)
                    n = n0
            t = (t0 - n * t0.dot(n))
            t = t.normalized() if t.length > 1e-9 else n.orthogonal().normalized()
            b = n.cross(t)
            # the part's along / up axes onto the line / the surface normal (any of its six sides out: Up)
            m = Matrix((t, n, t.cross(n))).transposed() @ axes.transposed()
            if abs(cfg['tilt']) > 1e-12:                    # (a lean along the line, about the across axis)
                m = Matrix.Rotation(cfg['tilt'], 3, b) @ m
            yaw = cfg['turn'] + turn + (math.pi if flip else 0.0)
            if abs(yaw) > 1e-12:                            # (a turn on the surface, about its normal)
                m = Matrix.Rotation(yaw, 3, n) @ m
            sc = Vector(tuple(sv)) * f
            local = Vector(tuple(bottom)) * f               # (its bottom middle on the surface, sunk by Sink)
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

class FastCaster:
    """The part's surface in its own space for a stroke: like geo_sculpt.SurfaceCaster (cast at the mouse, nearest),
    on Blender's own search tree of the part (Object.ray_cast / closest_point_on_mesh) - 0.24.151 (user: "인간 바디 +
    하이폴리곤으로 테스트") nothing built twice: the click that starts the stroke has Blender build it (1.8 s once for
    3.8 M faces), after that every look-up is free and it is never out of date."""

    def __init__(self, context, ob):
        from . import light_copies
        self.ob = getattr(ob, 'original', ob)
        self.mw = ob.matrix_world.copy()
        self.mi = self.mw.inverted_safe()
        self.dg = context.evaluated_depsgraph_get()
        light_copies.full(self.ob, self.dg)            # (the part itself, not its light copy)

    def _ray(self, o, d):
        try:
            ok, loc, nrm, _i = self.ob.ray_cast(o, d, depsgraph=self.dg)
        except (RuntimeError, ReferenceError):
            return None
        return (loc, nrm.normalized()) if ok else None

    def cast(self, context, xy):
        from bpy_extras import view3d_utils
        region, rv3d = context.region, context.region_data
        o = self.mi @ view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        d = (self.mi.to_3x3() @ view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)).normalized()
        return self._ray(o, d)

    def ray_cast(self, o, d):
        return self._ray(Vector(o), Vector(d))

    def nearest(self, p):
        try:
            ok, loc, nrm, _i = self.ob.closest_point_on_mesh(Vector(p), depsgraph=self.dg)
        except (RuntimeError, ReferenceError):
            return None
        return (loc, nrm.normalized()) if ok else None


def _caster(context, target):
    return FastCaster(context, target)


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
    infos = [part_info(p, st.axis, st.up) for p in parts]
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


def new_line(context, target, pts, nrm, parts, pg, kind='MECH'):
    """A Greeble Line (kind CREATURE: a Scale Line) on ``target`` (its child, its space): ``parts`` along the drawn
    line, settings from ``pg``."""
    name = 'Scale Line' if kind == 'CREATURE' else 'Greeble Line'
    me = bpy.data.meshes.new(name)
    ob = bpy.data.objects.new(name, me)
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
        ln.kind = kind
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


def _mesh(name, bm, smooth=True):
    me = bpy.data.meshes.new(name)
    bm.normal_update()
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = smooth
    return name, me


def _dome(bm, rx, ry, h, seg=20, rings=6, shape=None):
    """A flat-bottomed dome (Z up, bottom at z = 0) of radii rx, ry and height h; ``shape(x, y) -> (x, y)`` bends its
    outline (a teardrop, a point)."""
    import bmesh as _bm
    verts = []
    for j in range(rings + 1):
        a = (math.pi / 2) * j / rings                     # 0 = the rim, pi/2 = the top
        ring = []
        for i in range(seg if j < rings else 1):
            t = 2 * math.pi * i / seg
            x, y = math.cos(t) * math.cos(a), math.sin(t) * math.cos(a)
            if shape is not None:
                x, y = shape(x, y)
            ring.append(bm.verts.new((x * rx, y * ry, math.sin(a) * h)))
        verts.append(ring)
    for j in range(rings - 1):
        for i in range(seg):
            bm.faces.new((verts[j][i], verts[j][(i + 1) % seg], verts[j + 1][(i + 1) % seg], verts[j + 1][i]))
    top = verts[rings][0]
    for i in range(seg):
        bm.faces.new((verts[rings - 1][i], verts[rings - 1][(i + 1) % seg], top))
    bm.faces.new(list(reversed(verts[0])))
    _bm.ops.recalc_face_normals(bm, faces=list(bm.faces))


def _scale_meshes():
    """Five scale shapes, Z up, long side along X (the line), about 1 long: they overlap in rows."""
    import bmesh as _bm
    out = []
    bm = _bm.new()                                       # round, a little narrower at the back
    _dome(bm, 0.5, 0.42, 0.12, shape=lambda x, y: (x, y * (0.8 + 0.2 * x)))
    out.append(_mesh('Scale Round', bm))
    bm = _bm.new()                                       # pointed at the front
    _dome(bm, 0.5, 0.36, 0.12, shape=lambda x, y: (x, y * (1.0 - 0.75 * max(0.0, x)) * (0.85 + 0.15 * (1 - abs(x)))))
    out.append(_mesh('Scale Pointed', bm))
    bm = _bm.new()                                       # a keel down the middle
    _dome(bm, 0.5, 0.4, 0.1)
    for v in bm.verts:
        v.co.z += 0.09 * max(0.0, 1.0 - abs(v.co.y) / 0.12) * (v.co.z > 1e-6)
    out.append(_mesh('Scale Keeled', bm))
    bm = _bm.new()                                       # a hexagon plate (a lizard's belly)
    _dome(bm, 0.5, 0.45, 0.09, seg=6, rings=3)
    out.append(_mesh('Scale Hex', bm, smooth=False))
    bm = _bm.new()                                       # a big domed scute
    _dome(bm, 0.5, 0.5, 0.2, seg=24, rings=8, shape=lambda x, y: (math.copysign(abs(x) ** 0.7, x),
                                                                  math.copysign(abs(y) ** 0.7, y)))
    out.append(_mesh('Scale Scute', bm))
    return out


def _detail_meshes():
    """Five creature details, Z up: a spike, a bump, a curved nub, a fin, a cluster of warts."""
    import bmesh as _bm
    out = []
    bm = _bm.new()
    _bm.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.3, radius2=0.0, depth=1.0,
                        matrix=Matrix.Translation((0, 0, 0.5)))
    out.append(_mesh('Detail Spike', bm))
    bm = _bm.new()
    _dome(bm, 0.45, 0.45, 0.3, seg=20, rings=8)
    out.append(_mesh('Detail Bump', bm))
    bm = _bm.new()
    _bm.ops.create_cone(bm, cap_ends=True, segments=16, radius1=0.25, radius2=0.03, depth=0.8,
                        matrix=Matrix.Translation((0, 0, 0.4)))
    for v in bm.verts:                                   # bent forward
        v.co.x += 0.5 * (v.co.z / 0.8) ** 2
    out.append(_mesh('Detail Nub', bm))
    bm = _bm.new()                                       # a fin: thin, high at the back, low at the front
    r = _bm.ops.create_cube(bm, size=1.0)
    for v in r['verts']:
        v.co.x *= 1.0
        v.co.y *= 0.12
        v.co.z = (v.co.z + 0.5) * (0.45 if v.co.x < 0 else 0.12)
    out.append(_mesh('Detail Fin', bm, smooth=False))
    bm = _bm.new()
    for (x, y, rr) in ((0.0, 0.0, 0.22), (0.3, 0.12, 0.14), (-0.25, 0.15, 0.12), (0.12, -0.25, 0.1)):
        before = set(bm.verts)
        _dome(bm, rr, rr, rr * 0.7, seg=12, rings=4)
        for v in set(bm.verts) - before:
            v.co.x += x
            v.co.y += y
    out.append(_mesh('Detail Warts', bm))
    return out


# the settings each built-in set starts with (Scale Parts: overlapping staggered rows, a slight lean like shingles)
PRESETS = {
    'MECH': {},
    'SCALES': dict(order='RANDOM', axis='AUTO', up='POS_Z', turn=0.0, tilt=math.radians(10), scale=1.0,
                   scale_random=0.12, gap=-0.3, rows=3, row_gap=-0.2, sink=0.25, flip_random=False,
                   turn_random=math.radians(4), stagger=True),
    'DETAILS': dict(order='RANDOM', axis='AUTO', up='POS_Z', turn=0.0, tilt=0.0, scale=1.0, scale_random=0.4,
                    gap=0.5, rows=1, row_gap=0.5, sink=0.1, flip_random=False, turn_random=math.pi, stagger=False),
}
SETS = {'MECH': ('Greeble Parts', 'Starter Parts'), 'SCALES': ('Scale Parts', 'Scale Parts'),
        'DETAILS': ('Creature Detail Parts', 'Detail Parts')}


def make_starters(context, near=None, which='MECH'):
    """A built-in set of parts in a collection beside the model (``near``), sized to it; added to the parts list
    (``which``: MECH - five machine parts for Greeble Line; SCALES / DETAILS for Scale Line, with their settings)."""
    sc = context.scene
    kind = 'MECH' if which == 'MECH' else 'CREATURE'
    st = settings(sc, kind)
    coll_name = SETS[which][0]
    coll = bpy.data.collections.get(coll_name)
    if coll is None:
        coll = bpy.data.collections.new(coll_name)
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    size, at = 0.1, Vector((0.0, 0.0, 0.0))
    if near is not None:
        bb = [near.matrix_world @ Vector(c) for c in near.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        size = max((hi - lo).length * (0.05 if which == 'MECH' else 0.025), 1e-3)
        at = Vector((hi.x + size * (2.0 if which == 'MECH' else 4.0), (lo.y + hi.y) * 0.5, lo.z))
        if which == 'DETAILS':
            at.x += size * 3.0
    meshes = _starter_meshes() if which == 'MECH' else _scale_meshes() if which == 'SCALES' else _detail_meshes()
    made = []
    for i, (name, me) in enumerate(meshes):
        ob = bpy.data.objects.new(name, me)
        ob[STARTER_TAG] = 1
        ob.scale = (size, size, size)
        ob.location = at + Vector((0.0, 0.0, i * size * 1.2))
        coll.objects.link(ob)
        made.append(ob)
    if which != 'MECH':                                  # (a set of its own: the other one unticked)
        for it in st.parts:
            it.use = False
        _BUSY[0] = True
        try:
            for k, v in PRESETS[which].items():
                setattr(st, k, v)
        finally:
            _BUSY[0] = False
    for ob in made:
        add_part(st, ob)
    return made


# ---- 0.24.154 stamps: a part from an outline drawn with Shift -------------------------------------------------------

STAMP_TAG = 'mch_greeble_stamp'           # on a stamp part: its kind (MECH / CREATURE)
STAMP_COLLS = {'MECH': 'Greeble Stamps', 'CREATURE': 'Scale Stamps'}
STAMP_NAMES = {'MECH': 'Greeble Stamp', 'CREATURE': 'Scale Stamp'}
STAMP_PROFILES = {'MECH': ('FLAT', 'CHAMFER', 'BEVEL', 'DOME'), 'CREATURE': ('PUFF', 'RIDGE', 'PILLOW')}
STAMP_START = {'MECH': 'CHAMFER', 'CREATURE': 'PUFF'}
STAMP_RES = 12


def stamp_profile(st, kind):
    """The stamp profile for ``kind`` (one of its tool's own: a Creature profile never on Greeble Line, ...)."""
    p = getattr(st, 'stamp_profile', '')
    return p if p in STAMP_PROFILES[kind] else STAMP_START[kind]


def is_stamp(ob):
    return ob is not None and bool(ob.get(STAMP_TAG))


class _StampSettings:
    """Base Mesh (Greeble Line) / Creature Base Mesh (Scale Line) settings for a stamp: the stamp's profile, its height
    and border; the rest (segments, roundness, puff, resolution ...) the scene's Base Mesh / Creature Base Mesh ones."""

    def __init__(self, base, profile, height, edge):
        from . import base_mesh
        self._base = base
        self.profile = profile
        self.profile_sweep = 'OFF'
        self.embed = 0.0
        self.offset = 0.0
        # (a part laid many times: Dome / Puff / Ridge / Pillow at most STAMP_RES points across - the selected stamp's
        #  Resolution raises it)
        self.resolution = max(4, min(int(base.resolution), STAMP_RES))
        if profile in base_mesh.CREATURE_PROFILES:
            self.peak = height
        else:
            self.wall = base.wall * height / max(base.height, 1e-9)       # (Dome: its edge, in the same proportion)
            self.height = height if profile != 'DOME' else max(height - self.wall, height * 0.2)   # (Dome: on its edge)
            self.bevel_width = self.bevel_width_bottom = edge
            self.bevel_sides = 'TOP'

    def __getattr__(self, name):
        return getattr(self._base, name)


def _stamp_spot(context, near, ob, w, h):
    """Where a new stamp ``ob`` (w x h across) stands: beside the model (right of the built-in parts), above any stamp
    already there - Greeble Line's and Scale Line's stamps share the spot, one above the other, never inside each
    other (a Puff / Ridge / Pillow stamp reaches below its middle too)."""
    if near is not None:
        bb = [near.matrix_world @ Vector(c) for c in near.bound_box]
        lo = Vector((min(v.x for v in bb), min(v.y for v in bb), min(v.z for v in bb)))
        hi = Vector((max(v.x for v in bb), max(v.y for v in bb), max(v.z for v in bb)))
        x, y, z = hi.x + (hi - lo).length * 0.3, (lo.y + hi.y) * 0.5, lo.z
    else:
        c = context.scene.cursor.location
        x, y, z = c.x + max(w, h) * 4.0, c.y, c.z
    own_lo = min((v.co.z for v in ob.data.vertices), default=0.0)       # (<= 0: below its own middle)
    z -= min(own_lo, 0.0)
    gap = max(w, h) * 0.3
    for o in context.scene.objects:
        if o == ob or not is_stamp(o):
            continue
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        if max(v.x for v in bb) < x or min(v.x for v in bb) > x + w or max(v.y for v in bb) < y - h * 0.5 \
                or min(v.y for v in bb) > y + h * 0.5:
            continue                                                    # (not in the way)
        z = max(z, max(v.z for v in bb) + gap - own_lo)
    return Vector((x + w * 0.5, y, z))


def make_stamp(context, loops, projector, kind='MECH'):
    """0.24.154 (user: "방금 만든 그 툴에다가 내가 쉬프트 누르고 라쏘로 그리면 그 스탬프 베이스로 만들어 줄 수 있어? 그리블이랑
    크리쳐 둘 다") An outline drawn with Shift (any of the shared lasso shapes; region px) becomes a part: a live Base
    Mesh (Greeble Line: Flat / Chamfer / Bevel / Dome) or Creature Base Mesh (Scale Line: Puff / Ridge / Pillow) of that
    outline, as big as it was drawn on the surface under it, Stamp Height x its short side tall - standing beside the
    model (outline in its X / Y, up +Z), added to the tool's parts and ticked.  Returns (object, message)."""
    from . import base_mesh, core_geometry as cg
    st = settings(context, kind)
    screen_groups = cg.prepare_loops(loops)
    outer = screen_groups[0][0] if screen_groups else []
    if len(outer) < 3 or 0.5 * abs(sum(outer[i][0] * outer[(i + 1) % len(outer)][1] - outer[(i + 1) % len(outer)][0]
                                       * outer[i][1] for i in range(len(outer)))) < 40.0:    # (px, as Press Cut)
        raise cg.CutError('Draw a bigger outline (Shift + drag round it)')
    origin, x, y, n = base_mesh.plane_frame(context, projector, screen_groups)

    def to_local(q):
        v = base_mesh._plane_point(projector, q, origin, n) - origin
        return (v.dot(x), v.dot(y))
    groups = [([to_local(q) for q in outer], [[to_local(q) for q in hl] for hl in holes])
              for outer, holes in screen_groups]
    xs = [q[0] for outer, _h in groups for q in outer]
    ys = [q[1] for outer, _h in groups for q in outer]
    w, h = max(xs) - min(xs), max(ys) - min(ys)
    if min(w, h) <= 1e-6:
        raise cg.CutError('Draw a bigger outline (Shift + drag round it)')
    cx, cy = (max(xs) + min(xs)) * 0.5, (max(ys) + min(ys)) * 0.5      # (the part's origin: its middle)
    groups = cg.organize_loops([[(q[0] - cx, q[1] - cy) for q in lp] for outer, holes in groups
                                for lp in [outer] + holes])
    profile = stamp_profile(st, kind)
    height = st.stamp_height * min(w, h)
    sc = context.scene
    base = getattr(sc, 'mch_cbase', None) if kind == 'CREATURE' else getattr(sc, 'mch_base', None)
    if base is None:
        raise cg.CutError('Base Mesh settings missing')
    p = _StampSettings(base, profile, height, st.stamp_edge * height)
    near = None
    try:
        _q, found = base_mesh.anchor_hit(context, projector, screen_groups[0][0])
        near = found[2] if found is not None else None
    except (AttributeError, RuntimeError, TypeError, IndexError):
        near = None
    if near is not None and (is_line(near) or is_stamp(near) or any(it.ob == near for it in st.parts)):
        near = near.parent if is_line(near) else None
    if near is None:
        ln = active_line(context)
        near = ln.parent if ln is not None else None
    sel = [o for o in context.selected_objects]
    act = context.view_layer.objects.active
    before = set(bpy.data.objects)
    base_mesh._create_live_base(context, groups, Matrix.Identity(4), p, 0.0)
    made = [o for o in bpy.data.objects if o not in before]
    if not made:
        raise cg.CutError('The stamp could not be made from this outline')
    ob = made[0]
    sess = [nm for nm in sc.get(base_mesh.SESSION_KEY, []) if nm != ob.name]      # (never frozen with a Base Mesh
    if sess:                                                                    #  session: it stays live)
        sc[base_mesh.SESSION_KEY] = sess
    elif base_mesh.SESSION_KEY in sc:
        del sc[base_mesh.SESSION_KEY]
    ob.name = ob.data.name = STAMP_NAMES[kind]
    ob[STAMP_TAG] = kind
    coll = bpy.data.collections.get(STAMP_COLLS[kind])
    if coll is None:
        coll = bpy.data.collections.new(STAMP_COLLS[kind])
    if coll.name not in sc.collection.children:
        sc.collection.children.link(coll)
    for c in list(ob.users_collection):
        c.objects.unlink(ob)
    coll.objects.link(ob)
    ob.matrix_world = Matrix.Translation(_stamp_spot(context, near if near is not None and near.type == 'MESH' else None,
                                                     ob, w, h))       # (matrix_world now: the next stamp stacks on it)
    if st.stamp_alone:
        for it in st.parts:
            it.use = False
    add_part(st, ob)
    for o in context.selected_objects:
        o.select_set(False)
    for o in sel:
        try:
            o.select_set(True)
        except (RuntimeError, ReferenceError):
            pass
    context.view_layer.objects.active = act if act is not None and act.name in bpy.data.objects else None
    name = dict((i[0], i[1]) for i in STAMP_PROFILE_ITEMS)[profile]
    return ob, (f'{ob.name}: a {name} part from your outline ({w:.3f} x {h:.3f}, {height:.3f} high) beside the model - '
                f'in the list' + (', ticked alone' if st.stamp_alone else ', ticked') + '; drag on a part to lay it')


# ---- operators -----------------------------------------------------------------------------------------------------

def _draw_stroke(op, context):
    try:
        if context.region is None or context.region != op.region or len(op.screen) < 2:
            return
        from . import ui_gpu as ug
        ug.polyline(op.screen, (1.0, 0.55, 0.1, 0.9), 2.0)
    except (ReferenceError, AttributeError, RuntimeError):
        pass


def _greeble_sources(context):
    """Every mesh a Greeble Line lays (picked, starters, in any line): a click on one of their instances is a click
    on the surface under it."""
    out = set()
    for kind in KINDS:
        st = settings(context, kind)
        if st is not None:
            out.update(it.ob for it in st.parts if it.ob is not None)
    for ob in context.scene.objects:
        if is_line(ob):
            out.update(line_parts(ob))
        elif ob.get(STARTER_TAG):
            out.add(ob)
    return out


def pick_surface(context, xy):
    """((part, world hit, world normal) or None, what was hit first) under the mouse - through Greeble parts and lines
    (0.24.151: a stroke started on parts already laid went to a part's source mesh, then to nothing).  ``what was hit
    first`` = the world point of the first thing the ray met (a laid part, the part itself), or None (empty space)."""
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    if region is None or rv3d is None:
        return None, None
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy).normalized()
    dg = context.evaluated_depsgraph_get()
    skip, first, last, step = None, None, None, 1e-4
    for _i in range(200):
        try:
            hit, loc, nrm, _f, ob, _m = context.scene.ray_cast(dg, o, d)
        except (RuntimeError, TypeError):
            return None, first
        if not hit or ob is None:
            return None, first
        if first is None:
            first = loc.copy()
        ob = getattr(ob, 'original', ob)
        if skip is None:
            skip = _greeble_sources(context)
        if ob.type == 'MESH' and not is_line(ob) and ob not in skip and not ob.get('mch_geo_part'):
            return (ob, loc, nrm), first
        # on through it: a bigger step whenever the ray met the same point again (a face hit twice)
        step = step * 4.0 if last is not None and (loc - last).length < step else 1e-4
        last = loc.copy()
        o = loc + d * step * max(1.0, loc.length)
    return None, first


def line_at(context, p, reach):
    """The Greeble Line with a part placed within ``reach`` of world point ``p`` (the nearest), or None."""
    best, bd = None, reach
    for ob in context.scene.objects:
        if not is_line(ob) or not len(ob.data.vertices):
            continue
        mi = ob.matrix_world.inverted_safe()
        q = mi @ p
        co = np.empty(len(ob.data.vertices) * 3, np.float32)
        ob.data.vertices.foreach_get('co', co)
        dist = float(np.min(np.linalg.norm(co.reshape(-1, 3) - np.array(tuple(q)), axis=1)))
        dist *= ob.matrix_world.to_scale().length / math.sqrt(3.0)
        if dist < bd:
            best, bd = ob, dist
    return best


class MCH_OT_greeble_stroke(bpy.types.Operator):
    """Greeble Line: drag on a part - the picked meshes laid one after another along the line, standing on the
    surface (Esc while drawing: none)"""
    bl_idname = 'mch.greeble_stroke'
    bl_label = 'Greeble Line'
    bl_options = {'REGISTER', 'UNDO'}
    kind: EnumProperty(items=[('MECH', 'Greeble Line', ''), ('CREATURE', 'Scale Line', '')], default='MECH',
                       options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        from . import geo_sculpt as gs
        st = settings(context, self.kind)
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit, first = pick_surface(context, xy)
        if st is None:
            return {'PASS_THROUGH'}
        if hit is None:
            # (0.24.151: a drag started just off the body went on to Blender, which dragged the selected line away)
            # empty space: a click = nothing selected, a drag = nothing at all; never moves what is selected
            self.empty = (event.mouse_x, event.mouse_y)
            context.window_manager.modal_handler_add(self)
            return {'RUNNING_MODAL'}
        self.empty = None
        self.clicked = line_at(context, first, 0.05 * max(1.0, first.length)) if first is not None and \
            (first - hit[1]).length > 1e-6 else None
        target = hit[0]
        if is_line(target) and target.parent is not None:
            target = target.parent                     # (drawn over a line: on the part under it)
        self.parts = picked(st)
        if not self.parts:
            self.report({'WARNING'}, ('Scale Line: pick parts first (the window: Scale Parts / Detail Parts / Pick '
                                      'Part)') if self.kind == 'CREATURE' else
                        'Greeble Line: pick parts first (the window: Pick Part / Add Selected / Starter Parts)')
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
        self.line = new_line(context, target, self.pts, self.nrm, self.parts, st, self.kind)
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
        if getattr(self, 'empty', None) is not None:          # (pressed on empty space)
            # 0.24.152 (user: "왜 갑자기 중간 클릭으로 화면이 안 돌아가?") only the left button is held here: the
            # middle / right buttons, the wheel, keys go on as always (and end this), a lost release ends it too
            if event.type == 'LEFTMOUSE':
                if event.value == 'RELEASE':
                    if abs(event.mouse_x - self.empty[0]) + abs(event.mouse_y - self.empty[1]) < 5:
                        for o in context.selected_objects:
                            o.select_set(False)
                    return {'FINISHED'}
                if event.value == 'PRESS':                # (the release went elsewhere)
                    return {'FINISHED', 'PASS_THROUGH'}
                return {'RUNNING_MODAL'}                  # (a left drag: never Blender's move / box)
            if event.type in {'MIDDLEMOUSE', 'RIGHTMOUSE', 'ESC', 'WINDOW_DEACTIVATE'} or event.type.startswith('NDOF'):
                return {'FINISHED', 'PASS_THROUGH'}
            return {'PASS_THROUGH'}
        if event.type in NAV_EVENTS or event.type.startswith('NDOF'):
            return {'PASS_THROUGH'}                       # 0.24.152 the view turns / zooms while drawing
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS':
            event_release = True                          # (the release went elsewhere: this press ends it)
        else:
            event_release = False
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
        if (event.type == 'LEFTMOUSE' and event.value == 'RELEASE') or event_release \
                or event.type == 'WINDOW_DEACTIVATE':
            n = self._live(final=True) if len(self.pts) > 1 else 0
            self._end(context)
            if n == 0:
                self._drop()
                if self.clicked is not None and len(self.screen) <= 2:      # (a click on laid parts: that line)
                    for o in context.selected_objects:
                        o.select_set(False)
                    self.clicked.select_set(True)
                    context.view_layer.objects.active = self.clicked
                    self.report({'INFO'}, f'{self.clicked.name} selected - change it in the window')
                    return {'FINISHED'}
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
    kind: EnumProperty(items=[('MECH', 'Greeble Line', ''), ('CREATURE', 'Scale Line', '')], default='MECH',
                       options={'SKIP_SAVE'})

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
            if ob is not None and add_part(settings(context, self.kind), ob):
                self.added += 1
                self.report({'INFO'}, f'Greeble part: {ob.name} added')
            return {'RUNNING_MODAL'}
        if event.type in {'ESC', 'RIGHTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            self._done(context)
            self.report({'INFO'}, f'Parts: {len(settings(context, self.kind).parts)} ({self.added} picked now)')
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
    kind: EnumProperty(items=[('MECH', 'Greeble Line', ''), ('CREATURE', 'Scale Line', '')], default='MECH',
                       options={'SKIP_SAVE'})
    which: EnumProperty(items=[('MECH', 'Starter Parts', ''), ('SCALES', 'Scale Parts', ''),
                               ('DETAILS', 'Detail Parts', '')], default='MECH', options={'SKIP_SAVE'})

    def execute(self, context):
        st = settings(context, self.kind)
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
            which = self.which if self.kind == 'CREATURE' else 'MECH'
            made = make_starters(context, near if near is not None and near.type == 'MESH' else None, which)
            msg = f'{len(made)} {SETS[which][1].lower()} made beside the model (collection "{SETS[which][0]}") - ' \
                  f'yours to change' + ('; the settings set for them' if which != 'MECH' else '')
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


class MCH_OT_greeble_stamp_profile(bpy.types.Operator):
    """The next stamp's profile (Shift + draw a part): Greeble Line - Flat / Chamfer / Bevel / Dome, Scale Line - Puff /
    Ridge / Pillow"""
    bl_idname = 'mch.greeble_stamp_profile'
    bl_label = 'Stamp Profile'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: EnumProperty(items=[('MECH', 'Greeble Line', ''), ('CREATURE', 'Scale Line', '')], default='MECH',
                       options={'SKIP_SAVE'})
    profile: EnumProperty(items=STAMP_PROFILE_ITEMS, default='CHAMFER', options={'SKIP_SAVE'})

    def execute(self, context):
        st = settings(context, self.kind)
        if st is None or self.profile not in STAMP_PROFILES[self.kind]:
            return {'CANCELLED'}
        st.stamp_profile = self.profile
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
        # 0.24.154 Shift + draw (the shared lasso shapes): a part from the outline - a Base Mesh stamp
        ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, {'properties': [('mode', 'GREEBLE')]}),
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        draw(layout, context)


class MCH_TOOL_scale_line(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.scale_line'
    bl_label = 'Mecha Scale Line'
    bl_description = ('Drag on a creature: scales (overlapping, staggered rows) or details (spikes, bumps, nubs ...) '
                      'laid along the line, standing on the surface.\nScale Parts / Detail Parts / your own (Pick '
                      'Part) in the window')
    bl_icon = 'ops.generic.select_paint'
    bl_widget = None
    bl_keymap = (
        ('mch.greeble_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, {'properties': [('kind', 'CREATURE')]}),
        # 0.24.154 Shift + draw: a part from the outline - a Creature Base Mesh stamp
        ('mch.cut_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True},
         {'properties': [('mode', 'CGREEBLE')]}),
        ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return
        draw(layout, context, 'CREATURE')


HELP = ('Pick the meshes (Pick Part: click them), then drag on a part',
        'Shift + draw: your own part from the outline (a stamp)',
        'Up: which side faces out of the wall; Along, Turn, Tilt',
        'Select a line to change it; Apply = real geometry')


def draw(layout, context, kind='MECH'):
    """The window (the right panel): the parts to pick, the settings (of the selected line, else of the next one).
    ``kind``: MECH (Greeble Line) or CREATURE (Scale Line)."""
    st = settings(context, kind)
    if st is None:
        return
    def op(row, idname, text, icon='NONE', **props):
        o = row.operator(idname, text=text, icon=icon)
        o.kind = kind
        for k_, v_ in props.items():
            setattr(o, k_, v_)
        return o
    col = layout.column(align=True)
    col.label(text=f'Parts ({len(picked(st))} ticked)')
    for i, it in enumerate(st.parts):                # (one row a part: its name - click = ticked or not - and x)
        row = col.row(align=True)
        o = row.operator('mch.greeble_parts', text=(it.ob.name if it.ob is not None else '(gone)'), depress=bool(it.use))
        o.action, o.index, o.kind = 'TOGGLE', i, kind
        op(row, 'mch.greeble_parts', 'Remove', action='REMOVE', index=i)
    row = col.row(align=True)
    op(row, 'mch.greeble_pick', 'Pick Part', icon='EYEDROPPER')
    op(row, 'mch.greeble_parts', 'Add Selected', action='ADD_SELECTED')
    row = col.row(align=True)
    if kind == 'CREATURE':                           # (0.24.151 the built-in sets, each with its settings)
        op(row, 'mch.greeble_parts', 'Scale Parts', action='STARTER', which='SCALES')
        op(row, 'mch.greeble_parts', 'Detail Parts', action='STARTER', which='DETAILS')
        row = col.row(align=True)
    else:
        op(row, 'mch.greeble_parts', 'Starter Parts', action='STARTER')
    if st.parts:
        op(row, 'mch.greeble_parts', 'Clear List', action='CLEAR')
    col.prop(st, 'hide_parts')
    # 0.24.154 Shift + draw: a part from the outline (the Base Mesh / Creature Base Mesh of it)
    col = layout.column(align=True)
    col.label(text='Stamp: Shift + draw (Base Mesh)' if kind == 'MECH' else 'Stamp: Shift + draw (Creature Base Mesh)')
    row = col.row(align=True)
    cur = stamp_profile(st, kind)
    for ident in STAMP_PROFILES[kind]:
        o = row.operator('mch.greeble_stamp_profile', text=dict((i[0], i[1]) for i in STAMP_PROFILE_ITEMS)[ident],
                         depress=ident == cur)
        o.kind, o.profile = kind, ident
    col.prop(st, 'stamp_height')
    if cur in {'CHAMFER', 'BEVEL'}:
        col.prop(st, 'stamp_edge')
    col.prop(st, 'stamp_alone')
    stamp = context.view_layer.objects.active
    if is_stamp(stamp) and stamp.get(STAMP_TAG) == kind and getattr(stamp, 'mch_base', None) is not None:
        lb = stamp.mch_base                          # (the selected stamp itself: live, every line using it follows)
        col = layout.column(align=True)
        col.label(text=f'{stamp.name} (live: the lines follow)')
        col.prop(lb, 'profile', text='')
        if lb.profile in {'PUFF', 'RIDGE', 'PILLOW'}:
            for k_ in ('peak', 'puff', 'resolution'):
                col.prop(lb, k_)
        else:
            col.prop(lb, 'height')
            if lb.profile == 'DOME':
                col.prop(lb, 'resolution')
            if lb.profile in {'CHAMFER', 'BEVEL'}:
                col.prop(lb, 'bevel_width')
                col.prop(lb, 'bevel_segments')
    ln = active_line(context)
    if ln is not None and ln.mch_greeble_line.kind != kind:
        ln = None                                     # (a line of the other tool: not this window's)
    pg = ln.mch_greeble_line if ln is not None else st
    col = layout.column(align=True)
    col.label(text=f'{ln.name}: {len(ln.data.vertices)} parts (live)' if ln is not None else 'The next line')
    col.row(align=True).prop(pg, 'order', expand=True)
    col.label(text='Up: the side away from the wall')
    col.row(align=True).prop(pg, 'up', expand=True)
    col.label(text='Along: the side along the line')
    col.row(align=True).prop(pg, 'axis', expand=True)
    col.prop(pg, 'turn')
    col.prop(pg, 'tilt')
    for k in ('scale', 'scale_random', 'gap', 'rows', 'row_gap', 'edge_shrink', 'sink', 'turn_random', 'seed'):
        col.prop(pg, k)
    col.prop(pg, 'stagger')
    col.prop(pg, 'flip_random')
    if ln is not None:
        row = col.row(align=True)
        op(row, 'mch.greeble_parts', 'Use Picked Parts', action='USE_PICKED')
        row.operator('mch.greeble_apply', text='Apply')
    col = layout.column(align=True)
    for line in (HELP_CREATURE if kind == 'CREATURE' else HELP):
        col.label(text=line)


HELP_CREATURE = ('Scale Parts / Detail Parts (or Pick Part), then drag on the creature',
                 'Shift + draw: your own scale / detail from the outline (a stamp)',
                 'Scales: overlapping, staggered rows; Details: scattered',
                 'Select a line to change it; Apply = real geometry')


CLASSES = (MCH_PG_GreeblePart, MCH_PG_GreebleLine, MCH_PG_Greeble, MCH_OT_greeble_stroke, MCH_OT_greeble_pick,
           MCH_OT_greeble_parts, MCH_OT_greeble_stamp_profile, MCH_OT_greeble_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_greeble = PointerProperty(type=MCH_PG_Greeble)
    bpy.types.Scene.mch_cgreeble = PointerProperty(type=MCH_PG_Greeble)      # (0.24.151 Scale Line's own)
    bpy.types.Object.mch_greeble_line = PointerProperty(type=MCH_PG_GreebleLine)
    try:
        bpy.utils.register_tool(MCH_TOOL_greeble, after={'mecha.geo_sculpt'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_greeble, separator=True, group=False)
        except (ValueError, RuntimeError):
            pass
    try:
        bpy.utils.register_tool(MCH_TOOL_scale_line, after={'mecha.greeble_line'}, group=False)
    except (ValueError, RuntimeError, KeyError):
        try:
            bpy.utils.register_tool(MCH_TOOL_scale_line, separator=True, group=False)
        except (ValueError, RuntimeError):
            pass


def unregister():
    for tool in (MCH_TOOL_scale_line, MCH_TOOL_greeble):
        try:
            bpy.utils.unregister_tool(tool)
        except (ValueError, RuntimeError, KeyError):
            pass
    for attr, owner in (('mch_greeble', bpy.types.Scene), ('mch_cgreeble', bpy.types.Scene),
                        ('mch_greeble_line', bpy.types.Object)):
        if hasattr(owner, attr):
            delattr(owner, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
