"""0.24.29 Creature Hair: draw an area on a head (the scalp) -> live dreadlocks / tentacles / quills / strands.

Roots are spread evenly inside the drawn area (on the surface, through the view).  Every strand starts along the
surface normal (Lift), bends down under Gravity, wanders a little (Wave) and never goes into the body (it slides
over the shoulders and down the back like the cape does).  Each strand is a closed tube: rope ridges twisting round
it (Rope), thinner toward the tip (Taper), and Rings - metal bands / beads at random places (material slot 2, so
they can get their own colour).

Styles fill in the sliders: Dreads (Predator: thick roped dreads with bands), Tentacles (thick, smooth, tapering,
curling), Quills (stiff spikes, little gravity), Strands (many thin hairs).  ``root_points``, ``strand_path`` and
``tube_radius`` are pure-ish and tested headless.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

SRC_KEY = 'mch_hair_src'
COLLECTION = 'Creature Hair'
STYLE_ITEMS = [
    ('DREADS', 'Dreads', 'Predator dreadlocks: thick roped strands with metal bands'),
    ('TENTACLE', 'Tentacles', 'Thick smooth tentacles, tapering and curling'),
    ('QUILLS', 'Quills', 'Stiff spikes standing out'),
    ('STRANDS', 'Strands', 'Many thin hairs'),
    # 0.24.169 (user: "생머리, 파마머리, 수염, 동물털 이런 거 프리셋 좀 만들어 줘")
    ('STRAIGHT', 'Straight Hair', 'Long thin hair hanging straight down'),
    ('PERM', 'Perm', 'Curly permed hair: every strand a corkscrew'),
    ('BEARD', 'Beard', 'A beard: dense, shorter, a little wavy, hanging from the chin and cheeks'),
    ('FUR', 'Animal Fur', 'Short dense fur lying close along the body'),
]
STYLES = {
    'DREADS': dict(count=34, length=0.55, length_random=0.3, radius=0.022, radius_random=0.2, taper=0.35, lift=0.55,
                   gravity=1.0, wave=0.15, straight=0.7, rope=0.18, rope_twist=6.0, rings=2, ring_size=1.35),
    'TENTACLE': dict(count=10, length=0.5, length_random=0.35, radius=0.05, radius_random=0.25, taper=0.9, lift=0.8,
                     gravity=0.55, wave=0.45, straight=0.2, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
    'QUILLS': dict(count=40, length=0.3, length_random=0.4, radius=0.014, radius_random=0.3, taper=1.0, lift=1.0,
                   gravity=0.08, wave=0.05, straight=0.0, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
    'STRANDS': dict(count=120, length=0.5, length_random=0.25, radius=0.006, radius_random=0.3, taper=0.6, lift=0.4,
                    gravity=1.2, wave=0.25, straight=0.7, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3),
    'STRAIGHT': dict(count=260, length=0.5, length_random=0.12, radius=0.0035, radius_random=0.25, taper=0.7,
                     lift=0.25, gravity=1.6, wave=0.04, straight=1.0, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3,
                     curl=0.0, curl_turns=6.0, sides=5, segments=32),
    'PERM': dict(count=170, length=0.32, length_random=0.25, radius=0.0045, radius_random=0.25, taper=0.55, lift=0.6,
                 gravity=0.7, wave=0.12, straight=0.3, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3,
                 curl=0.55, curl_turns=7.0, sides=5, segments=64),
    'BEARD': dict(count=260, length=0.12, length_random=0.4, radius=0.0028, radius_random=0.3, taper=0.8, lift=0.75,
                  gravity=0.9, wave=0.45, straight=0.15, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3,
                  curl=0.22, curl_turns=2.5, sides=4, segments=18),     # (out from the face first, then down, frizzy)
    'FUR': dict(count=600, length=0.05, length_random=0.4, radius=0.0022, radius_random=0.3, taper=0.9, lift=0.18,
                gravity=0.35, wave=0.2, straight=0.0, rope=0.0, rope_twist=0.0, rings=0, ring_size=1.3,
                curl=0.0, curl_turns=3.0, sides=4, segments=6),
}
for _st in ('DREADS', 'TENTACLE', 'QUILLS', 'STRANDS'):          # (0.24.169 the first four: no curl, as they were)
    STYLES[_st].update(curl=0.0, curl_turns=6.0, sides=8, segments=28)
LIVE_KEYS = ('count', 'length', 'length_random', 'radius', 'radius_random', 'taper', 'lift', 'gravity', 'wave',
             'straight', 'rope',
             'rope_twist', 'rings', 'ring_size', 'seed', 'gap', 'sides', 'segments', 'curl', 'curl_turns',
             'bend', 'bend_at', 'bend_soft', 'bend_screen', 'bend_dir', 'bend_side')
COLOUR_KEYS = ('colour_mode', 'root_colour', 'tip_colour', 'tip_start', 'colour_random', 'shine', 'ring_colour')
# 0.24.169 (user: "머리카락 색 바뀌게 해 줘") (preset, label, root colour, tip colour) - scene-linear
COLOUR_PRESETS = (
    ('BLACK', 'Black', (0.010, 0.009, 0.008), (0.026, 0.023, 0.020)),
    ('DARK_BROWN', 'Dark Brown', (0.030, 0.018, 0.010), (0.075, 0.047, 0.028)),
    ('BROWN', 'Brown', (0.080, 0.045, 0.022), (0.190, 0.115, 0.058)),
    ('AUBURN', 'Auburn', (0.140, 0.035, 0.012), (0.330, 0.095, 0.032)),
    ('BLONDE', 'Blonde', (0.300, 0.210, 0.100), (0.660, 0.530, 0.300)),
    ('GREY', 'Grey', (0.180, 0.180, 0.180), (0.500, 0.500, 0.510)),
    ('WHITE', 'White', (0.700, 0.680, 0.650), (0.880, 0.870, 0.850)),
    ('FOX', 'Fox', (0.300, 0.070, 0.015), (0.860, 0.810, 0.730)),
)


# -----------------------------------------------------------------------------
# Pure helpers
# -----------------------------------------------------------------------------


def _inside(pt, poly):
    x, y = pt
    inside = False
    n = len(poly)
    for i in range(n):
        a, b = poly[i], poly[(i + 1) % n]
        if (a[1] > y) != (b[1] > y):
            if x < a[0] + (y - a[1]) * (b[0] - a[0]) / (b[1] - a[1]):
                inside = not inside
    return inside


def root_points(poly, count, seed):
    """About ``count`` points spread evenly inside the outline (jittered grid), screen pixels."""
    xs = [q[0] for q in poly]
    ys = [q[1] for q in poly]
    lo_x, hi_x, lo_y, hi_y = min(xs), max(xs), min(ys), max(ys)
    area = abs(0.5 * sum(a[0] * b[1] - b[0] * a[1] for a, b in zip(poly, poly[1:] + poly[:1])))
    if area < 1.0 or count <= 0:
        return []
    step = math.sqrt(area / count)
    rng = random.Random(seed)
    out = []
    y = lo_y + step * 0.5
    row = 0
    while y < hi_y:
        x = lo_x + step * (0.25 if row % 2 else 0.75)
        while x < hi_x:
            q = (x + rng.uniform(-0.35, 0.35) * step, y + rng.uniform(-0.35, 0.35) * step)
            if _inside(q, poly):
                out.append(q)
            x += step
        y += step * 0.866
        row += 1
    return out


def tube_radius(t, theta, r0, taper, rope, twist, length):
    """Radius of a strand at t (0 root .. 1 tip) and angle theta: taper + rope ridges twisting round it."""
    r = r0 * max(0.04, 1.0 - taper * t ** 1.3)
    if rope > 0:
        r *= 1.0 + rope * math.sin(3.0 * theta + twist * t * length / max(r0, 1e-9) * 0.25)
    return r


def strand_path(root, normal, length, segments, lift, gravity, wave, rng, push=None, outward=None, straight=0.0):
    """Points of one strand: starts along the normal (Lift), bends down (Gravity), wanders (Wave); ``push`` keeps
    it out of the body.  ``outward`` (horizontal) is where a strand standing straight up falls to.  ``straight``
    (0.24.29, 0..1): once it has turned over it hangs plumb - the turn speeds up and the sideways drift / wave fade."""
    down = Vector((0.0, 0.0, -1.0))
    n = normal.normalized()
    v = (n * max(0.05, lift) + down * (1.0 - lift) * 0.3)
    if v.length < 1e-9:
        v = n.copy()
    v.normalize()
    step = length / segments
    p = root.copy()
    pts = [p.copy()]
    wdir = Vector((rng.uniform(-1, 1), rng.uniform(-1, 1), rng.uniform(-0.3, 0.3)))
    side = outward if outward is not None and outward.length > 1e-9 else Vector((wdir.x, wdir.y, 0.0))
    if side.length < 1e-9:
        side = Vector((1.0, 0.0, 0.0))
    turn = gravity * 0.18 * 28.0 / max(4, segments)     # radians per step toward down (the same over any length)
    for k in range(segments):
        t = (k + 1) / segments
        # 0.24.29 gravity turns the strand toward down by an angle (adding a down vector did nothing to a strand
        # pointing straight up)
        axis = v.cross(down)
        if axis.length < 1e-6:
            axis = v.cross(side)
        falling = v.dot(down) > 0.0                 # past the top of its arc
        if axis.length > 1e-9:
            ang = min(v.angle(down, 0.0), turn * (1.0 + 3.0 * straight if falling else 1.0))
            v = Matrix.Rotation(ang, 3, axis.normalized()) @ v
        if falling and straight > 0:
            v = Vector((v.x * (1.0 - 0.6 * straight), v.y * (1.0 - 0.6 * straight), v.z))   # less sideways drift
        v = v + wdir * (wave * (1.0 - 0.8 * straight) * 0.12 * math.sin(t * 6.0 + rng.random()))
        if v.length < 1e-9:
            v = down.copy()
        v.normalize()
        p = p + v * step
        if push is not None:
            q = push(p)
            if (q - p).length > 1e-9:
                # slide along the body: keep going in the pushed direction
                v = (v + (q - p).normalized() * 0.5).normalized()
                p = q
        pts.append(p.copy())
    return pts


def curl_path(pts, amount, turns, phase, length):
    """0.24.169 Perm: the strand wound into a corkscrew round its own path - ``amount`` x 8 % of its length wide,
    ``turns`` turns along it; straight at the root, the full curl from a sixth of the way on."""
    if amount <= 0 or len(pts) < 3:
        return pts
    fr = _frames(pts)
    m = len(pts)
    rad = amount * length * 0.08
    out = []
    for i, (q, (_t, nv, bv)) in enumerate(zip(pts, fr)):
        tt = i / (m - 1)
        ph = phase + 2.0 * math.pi * turns * tt
        out.append(q + (nv * math.cos(ph) + bv * math.sin(ph)) * (rad * min(1.0, tt / 0.16)))
    return out


def bend_path(pts, direction, angle, at, soft, push=None):
    """0.24.171 Bend (user: "머리카락을 내가 보는 뷰포트 방향에서 꺾을 수 있게"): from ``at`` (0 root .. 1 tip) on, each
    piece of the strand turned toward ``direction`` (world) by up to ``angle`` - never past it - over ``soft`` of the
    length (0: a sharp kink, 1: a long curve); ``push`` keeps it out of the body."""
    d = Vector(direction)
    if angle <= 0 or len(pts) < 3 or d.length < 1e-9:
        return pts
    d.normalize()
    m = len(pts)
    p = pts[0].copy()
    out = [p.copy()]
    for i in range(m - 1):
        seg = pts[i + 1] - pts[i]
        L = seg.length
        if L < 1e-12:
            out.append(p.copy())
            continue
        v = seg / L
        t = (i + 0.5) / (m - 1)
        if soft <= 1e-3:
            w = 1.0 if t >= at else 0.0
        else:
            x = min(1.0, max(0.0, (t - at) / soft))
            w = x * x * (3.0 - 2.0 * x)
        a = angle * w
        if a > 0:
            ax = v.cross(d)
            if ax.length > 1e-6:
                v = Matrix.Rotation(min(a, v.angle(d, 0.0)), 3, ax.normalized()) @ v
            elif v.dot(d) < 0:                       # (pointing straight away: turn over any side)
                v = Matrix.Rotation(min(a, math.pi), 3, v.orthogonal().normalized()) @ v
        p = p + v * L
        if push is not None:
            p = push(p)
        out.append(p.copy())
    return out


# -----------------------------------------------------------------------------
# Mesh
# -----------------------------------------------------------------------------


def _frames(pts):
    """Parallel-transport frames (tangent, normal, binormal) along a path."""
    tans = []
    for i in range(len(pts)):
        a = pts[max(i - 1, 0)]
        b = pts[min(i + 1, len(pts) - 1)]
        d = b - a
        tans.append(d.normalized() if d.length > 1e-12 else Vector((0, 0, 1)))
    ref = Vector((0, 0, 1)) if abs(tans[0].z) < 0.9 else Vector((1, 0, 0))
    nrm = tans[0].cross(ref).normalized()
    out = []
    for i, t in enumerate(tans):
        if i > 0:
            prev = tans[i - 1]
            axis = prev.cross(t)
            if axis.length > 1e-9:
                ang = prev.angle(t)
                nrm = (Matrix.Rotation(ang, 3, axis.normalized()) @ nrm)
            nrm = (nrm - t * nrm.dot(t)).normalized()
        out.append((t, nrm, t.cross(nrm)))
    return out


T_ATTR = 'mch_hair_t'           # 0.24.169 on every point: 0 at the root .. 1 at the tip (the colour's gradient)
R_ATTR = 'mch_hair_r'           # 0.24.169 a random 0 - 1 per strand (each strand a little different)


def add_tube(bm, pts, r0, p, length, sides, mat=0, radius_fn=None, tag=None):
    """Closed tube along pts (flat root cap, pointed tip).  ``tag`` (0.24.169): (t layer, r layer, the strand's random,
    t0, t1) - the points get t from t0 at the start to t1 at the end and the strand's random."""
    fr = _frames(pts)
    rings = []
    m = len(pts)

    def mark(v, tt):
        if tag is not None:
            lt, lr, rnd, t0, t1 = tag
            v[lt] = t0 + (t1 - t0) * tt
            v[lr] = rnd
        return v
    for i, (q, (t, nv, bv)) in enumerate(zip(pts, fr)):
        tt = i / max(1, m - 1)
        ring = []
        for s in range(sides):
            th = 2 * math.pi * s / sides
            r = radius_fn(tt, th) if radius_fn else tube_radius(tt, th, r0, p.taper, p.rope, p.rope_twist, length)
            ring.append(mark(bm.verts.new(q + (nv * math.cos(th) + bv * math.sin(th)) * r), tt))
        rings.append(ring)
    faces = []
    for i in range(m - 1):
        a, b = rings[i], rings[i + 1]
        for s in range(sides):
            s2 = (s + 1) % sides
            faces.append(bm.faces.new((a[s], a[s2], b[s2], b[s])))
    faces.append(bm.faces.new(rings[0][::-1]))
    tip = mark(bm.verts.new(pts[-1] + fr[-1][0] * (r0 * 0.3)), 1.0)
    for s in range(sides):
        faces.append(bm.faces.new((rings[-1][s], rings[-1][(s + 1) % sides], tip)))
    for f in faces:
        f.material_index = mat
        f.smooth = True
    return faces


def add_ring(bm, pts, at, r, width, sides, tag=None):
    """A metal band round the strand at fraction ``at`` of its length (its own closed short tube)."""
    m = len(pts)
    i = min(m - 2, max(0, int(at * (m - 1))))
    centre = pts[i].lerp(pts[i + 1], at * (m - 1) - i)
    d = (pts[i + 1] - pts[i])
    if d.length < 1e-12:
        return
    d.normalize()
    seg = [centre - d * width * 0.5, centre, centre + d * width * 0.5]
    add_tube(bm, seg, r, None, 1.0, sides, mat=1,
             radius_fn=lambda tt, th: r * (0.92 if tt in (0.0, 1.0) else 1.0),
             tag=None if tag is None else (tag[0], tag[1], tag[2], at, at))


# -----------------------------------------------------------------------------
# Build / live object
# -----------------------------------------------------------------------------


def source(ob):
    if ob is None:
        return None
    try:
        raw = ob.get(SRC_KEY)
        return json.loads(raw) if raw else None
    except (TypeError, ValueError, ReferenceError):
        return None


def build(context, src, p, target):
    from . import armor_plate as ap
    from . import cape_gen
    projector = ap.thaw_projector(src['proj'])
    bvh, lo, hi = cape_gen._body(context, target)
    groups = cg.prepare_loops([[tuple(q) for q in lp] for lp in src['loops']])
    if not groups:
        raise cg.CutError('The outline is empty.')
    outer = groups[0][0]
    roots2d = root_points(outer, p.count, p.seed)
    if not roots2d:
        raise cg.CutError('Draw a bigger area for the hair.')
    cos, nrms, missing = ap.project_patch(roots2d, projector, bvh)
    size = (hi - lo).length
    miss = set(missing)
    gap = p.gap if p.gap > 0 else size * 0.004
    rng = random.Random(p.seed * 7 + 1)
    good = [c for i, c in enumerate(cos) if i not in miss]
    mid = sum(good, Vector()) / max(1, len(good))
    bm = bmesh.new()
    lt = bm.verts.layers.float.new(T_ATTR)          # (made before any point: a new layer drops the points' handles)
    lr = bm.verts.layers.float.new(R_ATTR)
    crng = random.Random(p.seed * 131 + 7)          # (its own stream: the strands' shapes stay as they were)
    sides = max(3, p.sides)
    segs = max(3, p.segments)
    for i, (c, n) in enumerate(zip(cos, nrms)):
        if i in miss:
            continue                         # off the head: no strand there
        L = p.length * size * (1.0 + p.length_random * rng.uniform(-1, 1))
        r0 = p.radius * size * (1.0 + p.radius_random * rng.uniform(-1, 1))
        if L <= r0 or r0 <= 0:
            continue
        keep = r0 * (max(1.0, p.ring_size) if p.rings else 1.0) + gap     # the rings are fatter than the strand

        def push(q, keep=keep):
            return cape_gen._push_out(bvh, q, keep)
        out = Vector((n.x, n.y, 0.0))
        if out.length < 0.2:                 # on top of the head: fall away from the middle of the area
            out = Vector((c.x - mid.x, c.y - mid.y, 0.0))
        pts = strand_path(c + n * (r0 * 0.3), n, L, segs, p.lift, p.gravity, p.wave, rng, push, out, p.straight)
        if p.bend > 0:                       # 0.24.171 bent toward a side of the view
            pts = bend_path(pts, Vector(p.bend_dir), p.bend, p.bend_at, p.bend_soft, push)
        if p.curl > 0:                       # 0.24.169 Perm: corkscrews (kept out of the body)
            pts = curl_path(pts, p.curl, p.curl_turns * crng.uniform(0.85, 1.15), crng.uniform(0, 2 * math.pi), L)
            pts = [pts[0]] + [push(q) for q in pts[1:]]
        tag = (lt, lr, crng.random(), 0.0, 1.0)
        add_tube(bm, pts, r0, p, L, sides, tag=tag)
        for _k in range(p.rings):
            at = rng.uniform(0.12, 0.8)
            add_ring(bm, pts, at, r0 * p.ring_size * max(0.1, 1.0 - p.taper * at ** 1.3), r0 * rng.uniform(1.2, 2.4),
                     sides + 2, tag=tag)
    if not bm.faces:
        bm.free()
        raise cg.CutError('No hair could grow there (draw on the head).')
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    return bm


def rebuild(context, ob):
    src = source(ob)
    if src is None:
        raise cg.CutError('This hair was applied (no outline kept).')
    target = bpy.data.objects.get(src.get('target', ''))
    if target is None or target.type != 'MESH':
        raise cg.CutError('The head the hair was drawn on is gone.')
    bm = build(context, src, ob.mch_hair, target)
    try:
        bmesh.ops.transform(bm, matrix=ob.matrix_world.inverted_safe(), verts=bm.verts[:])
        bm.to_mesh(ob.data)
    finally:
        bm.free()
    ob.data.update()
    fit_mirror(ob)


MIRROR_FIT = 'mch_hair_mirror_fit'      # 0.24.171 on a hair whose Mirror came from its head


def fit_mirror(ob):
    """0.24.171 (user: "왜 아직 머리카락 미러가 안 돼"): the Mirror a hair takes from its head kept its head's Bisect -
    the side the head keeps; hair drawn on the other side (the side the head's Mirror makes) was cut away whole.  Now
    the hair's own roots decide: all on one side of a plane - no cut there (whole strands, mirrored); across it - cut,
    keeping the side most roots are on.  Returns True when it changed something."""
    from . import symmetry
    m = symmetry.mirror_mod(ob)
    if m is None or not ob.get(MIRROR_FIT):
        return False
    me = ob.data
    at = me.attributes.get(T_ATTR)
    n = len(me.vertices)
    if at is None or n == 0:
        return False
    import numpy as np
    t = np.empty(n, np.float32)
    at.data.foreach_get('value', t)
    co = np.empty(n * 3, np.float32)
    me.vertices.foreach_get('co', co)
    roots = co.reshape(-1, 3)[t < 1e-6]
    if not len(roots):
        return False
    M = np.array(ob.matrix_world, float)
    W = roots @ M[:3, :3].T + M[:3, 3]
    F = np.array((m.mirror_object or ob).matrix_world, float)
    loc = (W - F[:3, 3]) @ np.linalg.inv(F[:3, :3]).T
    size = float(np.linalg.norm(np.ptp(co.reshape(-1, 3) @ M[:3, :3].T, axis=0))) or 1.0
    tol = size * 1e-3
    changed = False
    for i in range(3):
        if not m.use_axis[i]:
            continue
        c = loc[:, i]
        one_side = bool((c >= -tol).all() or (c <= tol).all())
        flip = bool(np.median(c) < 0)
        if bool(m.use_bisect_axis[i]) != (not one_side) or bool(m.use_bisect_flip_axis[i]) != flip:
            m.use_bisect_axis[i] = not one_side
            m.use_bisect_flip_axis[i] = flip
            changed = True
    return changed


_BUSY = [False]


def _update(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if not isinstance(ob, bpy.types.Object) or not self.live:
        return
    try:
        rebuild(context, ob)
        self.last_error = ''
    except (cg.CutError, ValueError, RuntimeError) as ex:
        self.last_error = str(ex)
    st = getattr(getattr(context, 'scene', None), 'mch_hair', None)
    if st is not None:                       # the next hair starts like this one
        _BUSY[0] = True
        try:
            for k in LIVE_KEYS + ('style',):
                v = getattr(self, k)
                v = v if isinstance(v, (str, float, int, bool)) else tuple(v)
                cur = getattr(st, k)
                if (cur if isinstance(cur, (str, float, int, bool)) else tuple(cur)) != v:
                    setattr(st, k, v)
        except (AttributeError, TypeError):
            pass
        finally:
            _BUSY[0] = False


MAT_KEY = 'mch_hair_mat'               # 0.24.169 on a hair: the names of its own materials (hair, rings)


def _hair_tree(m):
    """The hair material's nodes: root -> tip colour along the strand (``mch_hair_t``, from Tip From), each strand a
    little lighter / darker / warmer (``mch_hair_r`` x Strand Variation), Shine as the roughness."""
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.name = 'BSDF'
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name = T_ATTR
    at.attribute_type = 'GEOMETRY'
    ar = nt.nodes.new('ShaderNodeAttribute')
    ar.attribute_name = R_ATTR
    ar.attribute_type = 'GEOMETRY'
    mr = nt.nodes.new('ShaderNodeMapRange')
    mr.name = 'Fade'
    mr.interpolation_type = 'SMOOTHSTEP'
    nt.links.new(at.outputs['Fac'], mr.inputs['Value'])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.name = 'Colour'
    mix.data_type = 'RGBA'
    nt.links.new(mr.outputs['Result'], mix.inputs['Factor'])
    hsv = nt.nodes.new('ShaderNodeHueSaturation')
    hsv.name = 'Vary'
    col_out = next(o for o in mix.outputs if o.type == 'RGBA')
    nt.links.new(col_out, hsv.inputs['Color'])
    for name, sock in (('Hue', 'Hue'), ('Value', 'Value')):
        mm = nt.nodes.new('ShaderNodeMath')
        mm.operation = 'MULTIPLY_ADD'
        mm.name = 'Vary ' + name
        nt.links.new(ar.outputs['Fac'], mm.inputs[0])
        nt.links.new(mm.outputs[0], hsv.inputs[sock])
    nt.links.new(hsv.outputs['Color'], bsdf.inputs['Base Color'])
    nt.links.new(bsdf.outputs[0], out.inputs['Surface'])
    m['mch_hair_v'] = 1


def _materials(ob):
    """The hair's own materials (hair, rings), made the first time."""
    names = (ob.get(MAT_KEY) or '').split('|')
    hair = bpy.data.materials.get(names[0]) if names[0] else None
    rings = bpy.data.materials.get(names[1]) if len(names) > 1 and names[1] else None
    if hair is None:
        hair = bpy.data.materials.new('MCH Hair - ' + ob.name)
        _hair_tree(hair)
    if rings is None:
        rings = bpy.data.materials.new('MCH Hair Rings - ' + ob.name)
        rings.use_nodes = True
    ob[MAT_KEY] = hair.name + '|' + rings.name
    return hair, rings


def apply_colours(ob, body_mat=None):
    """0.24.169 The hair's colour settings into its materials (no rebuild): its own hair material (or the body's),
    the rings' colour.  Material slot 1 = the hair, 2 = the rings."""
    p = ob.mch_hair
    me = ob.data
    if T_ATTR not in me.attributes and source(ob) is not None and p.live:     # (a hair made before 0.24.169)
        try:
            rebuild(bpy.context, ob)
        except (cg.CutError, ValueError, RuntimeError):
            pass
    hair, rings = _materials(ob)
    if hair.get('mch_hair_v') != 1:
        _hair_tree(hair)
    nt = hair.node_tree
    mix = nt.nodes['Colour']
    a, b = [i for i in mix.inputs if i.type == 'RGBA'][:2]
    a.default_value = (*p.root_colour, 1.0)
    b.default_value = (*p.tip_colour, 1.0)
    fade = nt.nodes['Fade']
    fade.inputs['From Min'].default_value = p.tip_start
    fade.inputs['From Max'].default_value = 1.0
    k = p.colour_random
    vh, vv = nt.nodes['Vary Hue'], nt.nodes['Vary Value']
    vh.inputs[1].default_value, vh.inputs[2].default_value = 0.08 * k, 0.5 - 0.04 * k          # (hue 0.5 +- 0.04 k)
    vv.inputs[1].default_value, vv.inputs[2].default_value = 1.2 * k, 1.0 - 0.6 * k            # (value 1 +- 0.6 k)
    bsdf = nt.nodes['BSDF']
    bsdf.inputs['Roughness'].default_value = 1.0 - 0.75 * p.shine
    hair.roughness = 1.0 - 0.75 * p.shine
    hair.diffuse_color = (*[(x + y) * 0.5 for x, y in zip(p.root_colour, p.tip_colour)], 1.0)   # (the solid view)
    rb = rings.node_tree.nodes.get('Principled BSDF') if rings.node_tree else None
    if rb is not None:
        rb.inputs['Base Color'].default_value = (*p.ring_colour, 1.0)
        rb.inputs['Metallic'].default_value = 1.0
        rb.inputs['Roughness'].default_value = 0.3
    rings.diffuse_color = (*p.ring_colour, 1.0)
    rings.metallic = 1.0
    if p.colour_mode == 'BODY':
        src = source(ob) or {}
        body = bpy.data.objects.get(src.get('target', '')) if src else None
        body_mat = body_mat or (next((m for m in body.data.materials if m is not None), None)
                                if body is not None and body.type == 'MESH' else None)
    first = body_mat if p.colour_mode == 'BODY' and body_mat is not None else hair
    while len(me.materials) < 2:
        me.materials.append(None)
    me.materials[0] = first
    me.materials[1] = rings


def _colour_update(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.live:
        apply_colours(ob)
    st = getattr(getattr(context, 'scene', None), 'mch_hair', None)
    if st is not None and st != self and isinstance(ob, bpy.types.Object):   # the next hair starts like this one
        _BUSY[0] = True
        try:
            for k in COLOUR_KEYS:
                v = getattr(self, k)
                setattr(st, k, tuple(v) if not isinstance(v, (str, float, int)) else v)
        finally:
            _BUSY[0] = False


class MCH_OT_hair_colour(bpy.types.Operator):
    """A hair colour: the live hair's (or the next hair's) root and tip colours"""
    bl_idname = 'mch.hair_colour'
    bl_label = 'Hair Colour'
    bl_options = {'REGISTER', 'UNDO'}
    preset: EnumProperty(items=[(c[0], c[1], '') for c in COLOUR_PRESETS])

    def execute(self, context):
        ob = live_hair(context)
        p = ob.mch_hair if ob is not None else context.scene.mch_hair
        _key, _label, root, tip = next(c for c in COLOUR_PRESETS if c[0] == self.preset)
        _BUSY[0] = True
        try:
            p.colour_mode = 'OWN'
            p.root_colour = root
        finally:
            _BUSY[0] = False
        p.tip_colour = tip                         # (its update applies the colours and passes them on)
        if ob is None:
            pass
        return {'FINISHED'}


def view_rotation(context):
    """The rotation of the 3D view the user looks through (this region's, else the biggest 3D view's), or None."""
    rv = getattr(context, 'region_data', None)
    if isinstance(rv, bpy.types.RegionView3D):
        return rv.view_rotation.copy()
    win = getattr(context, 'window', None)
    scr = getattr(context, 'screen', None) or (win.screen if win is not None else None)
    best = None
    for a in (scr.areas if scr is not None else ()):
        if a.type == 'VIEW_3D' and (best is None or a.width * a.height > best.width * best.height):
            best = a
    if best is None:
        return None
    return best.spaces.active.region_3d.view_rotation.copy()


BEND_SIDES = (('LEFT', 'Left'), ('UP', 'Up'), ('RIGHT', 'Right'), ('DOWN', 'Down'), ('TOWARD', 'Toward Me'),
              ('AWAY', 'Away'))
_SIDE_DEG = {'RIGHT': 0.0, 'UP': 90.0, 'LEFT': 180.0, 'DOWN': 270.0}


def view_direction(context, side=None, screen_angle=None):
    """A world direction from the view: ``side`` (BEND_SIDES) or ``screen_angle`` (radians: 0 right, pi/2 up) on the
    screen; None without a 3D view."""
    q = view_rotation(context)
    if q is None:
        return None
    if side == 'TOWARD':
        v = q @ Vector((0.0, 0.0, 1.0))
    elif side == 'AWAY':
        v = q @ Vector((0.0, 0.0, -1.0))
    else:
        a = math.radians(_SIDE_DEG[side]) if side in _SIDE_DEG else (screen_angle or 0.0)
        v = q @ Vector((math.cos(a), math.sin(a), 0.0))
    return v.normalized()


def _bend_screen_update(self, context):
    if _BUSY[0]:
        return
    d = view_direction(context, screen_angle=self.bend_screen)
    if d is not None:
        _BUSY[0] = True
        try:
            self.bend_dir = tuple(d)
            self.bend_side = ''
        finally:
            _BUSY[0] = False
    _update(self, context)


class MCH_OT_hair_bend(bpy.types.Operator):
    """Bend the hair toward this side of the view you are looking through (the selected live hair and the next)"""
    bl_idname = 'mch.hair_bend'
    bl_label = 'Hair Bend Toward'
    bl_options = {'REGISTER', 'UNDO'}
    side: EnumProperty(items=[(k, l, '') for k, l in BEND_SIDES] + [('OFF', 'No Bend', '')], default='RIGHT')

    def execute(self, context):
        hairs = apply_targets(context)
        d = None if self.side == 'OFF' else view_direction(context, self.side)
        if self.side != 'OFF' and d is None:
            self.report({'WARNING'}, 'Bend: no 3D view to take the direction from')
            return {'CANCELLED'}
        for pg in [context.scene.mch_hair] + [o.mch_hair for o in hairs]:
            _BUSY[0] = True
            try:
                if self.side == 'OFF':
                    pg.bend = 0.0
                    pg.bend_side = ''
                else:
                    pg.bend_dir = tuple(d)
                    pg.bend_side = self.side
                    if self.side in _SIDE_DEG:
                        pg.bend_screen = math.radians(_SIDE_DEG[self.side])
                    if pg.bend < 1e-6:
                        pg.bend = math.radians(60.0)     # (a first click: a bend you can see)
            finally:
                _BUSY[0] = False
        for o in hairs:
            try:
                rebuild(context, o)
                o.mch_hair.last_error = ''
            except (cg.CutError, ValueError, RuntimeError) as ex:
                o.mch_hair.last_error = str(ex)
        lab = dict(BEND_SIDES).get(self.side, 'No Bend')
        self.report({'INFO'}, f'Hair bend: {lab}' + (f' - {len(hairs)} hair(s)' if hairs else ' (the next hair)'))
        return {'FINISHED'}


def _style_update(self, context):
    if _BUSY[0]:
        return
    vals = STYLES.get(self.style)
    if not vals:
        return
    _BUSY[0] = True
    try:
        for k, v in vals.items():
            setattr(self, k, v)
    finally:
        _BUSY[0] = False
    _update(self, context)


class MCH_PG_Hair(bpy.types.PropertyGroup):
    """Scene.mch_hair = settings for the next hair; Object.mch_hair = live hair."""
    style: EnumProperty(name='Style', items=STYLE_ITEMS, default='DREADS', update=_style_update,
                        description='Fills in the sliders')
    count: IntProperty(name='Count', default=34, min=1, soft_max=600, max=4000, update=_update,
                       description='How many strands')
    length: FloatProperty(name='Length', default=0.55, min=0.01, max=2.0, update=_update,
                          description='Strand length (part of the body size)')
    length_random: FloatProperty(name='Length Random', default=0.3, min=0.0, max=0.95, update=_update)
    radius: FloatProperty(name='Thickness', default=0.022, min=0.001, max=0.2, precision=4, update=_update,
                          description='Strand thickness (part of the body size)')
    radius_random: FloatProperty(name='Thickness Random', default=0.2, min=0.0, max=0.9, update=_update)
    taper: FloatProperty(name='Taper', default=0.35, min=0.0, max=1.0, update=_update,
                         description='Thinner toward the tip (1 = pointed)')
    lift: FloatProperty(name='Lift', default=0.55, min=0.0, max=1.0, update=_update,
                        description='How far a strand stands out of the scalp before it bends down')
    gravity: FloatProperty(name='Gravity', default=1.0, min=0.0, max=3.0, update=_update)
    wave: FloatProperty(name='Wave', default=0.15, min=0.0, max=1.5, update=_update, description='Random wander / curl')
    straight: FloatProperty(name='Straight', default=0.7, min=0.0, max=1.0, update=_update,
                            description='How straight the strands hang once they fall (1 = plumb, little sideways '
                                        'drift or wave; 0 = loose and wavy)')
    rope: FloatProperty(name='Rope', default=0.18, min=0.0, max=0.6, update=_update,
                        description='Twisted rope ridges on the strands (dreadlock texture)')
    rope_twist: FloatProperty(name='Rope Twist', default=6.0, min=0.0, max=30.0, update=_update)
    rings: IntProperty(name='Rings', default=2, min=0, max=8, update=_update,
                       description='Metal bands / beads per strand (material slot 2)')
    ring_size: FloatProperty(name='Ring Size', default=1.35, min=1.05, max=3.0, update=_update)
    seed: IntProperty(name='Seed', default=1, min=0, update=_update)
    gap: FloatProperty(name='Gap', default=0.0, min=0.0, soft_max=0.1, precision=4, unit='LENGTH', update=_update,
                       description='Distance kept from the body (0 = Auto)')
    sides: IntProperty(name='Sides', default=8, min=3, max=24, update=_update)
    segments: IntProperty(name='Segments', default=28, min=4, max=120, update=_update)
    curl: FloatProperty(name='Curl', default=0.0, min=0.0, max=1.5, update=_update,
                        description='0.24.169 Perm: every strand wound into a corkscrew (how wide)')
    curl_turns: FloatProperty(name='Curl Turns', default=6.0, min=0.5, max=30.0, update=_update,
                              description='How many turns along a strand (raise Segments for many)')
    # 0.24.171 (user: "머리카락을 내가 보는 뷰포트 방향에서 꺾을 수 있게 밴드 옵션") Bend toward a side of the view
    bend: FloatProperty(name='Bend', default=0.0, min=0.0, max=math.pi, subtype='ANGLE', update=_update,
                        description='How far the strands turn toward the bend direction (0 = no bend)')
    bend_at: FloatProperty(name='Bend At', default=0.3, min=0.0, max=0.95, update=_update,
                           description='Where along the strand it bends (0 = at the root, 0.9 = near the tip)')
    bend_soft: FloatProperty(name='Bend Soft', default=0.35, min=0.0, max=1.0, update=_update,
                             description='0 = a sharp kink, 1 = a long smooth curve')
    bend_screen: FloatProperty(name='Bend Toward (screen)', default=0.0, min=0.0, max=2 * math.pi, subtype='ANGLE',
                               update=_bend_screen_update,
                               description='The direction on the screen it bends toward, seen from the view you are '
                                           'looking through when you change it: 0 right, 90 up, 180 left, 270 down')
    bend_dir: FloatVectorProperty(name='Bend Direction', size=3, default=(1.0, 0.0, 0.0), options={'HIDDEN'},
                                  description='The bend direction in the world (set from the view)')
    bend_side: StringProperty(default='', options={'HIDDEN'})
    # 0.24.169 (user: "머리카락 색 바뀌게 해 줘") colour: its own material, changed without rebuilding the strands
    colour_mode: EnumProperty(name='Colour', items=(('OWN', 'Hair Colour', 'The hair\'s own colour (below)'),
                                                    ('BODY', 'Body\'s Material', 'The same material as the head / '
                                                                                   'body it grows on')),
                              default='OWN', update=_colour_update)
    root_colour: FloatVectorProperty(name='Root', subtype='COLOR', size=3, min=0.0, max=1.0,
                                     default=(0.030, 0.018, 0.010), update=_colour_update,
                                     description='The colour at the roots')
    tip_colour: FloatVectorProperty(name='Tip', subtype='COLOR', size=3, min=0.0, max=1.0,
                                    default=(0.075, 0.047, 0.028), update=_colour_update,
                                    description='The colour at the tips')
    tip_start: FloatProperty(name='Tip From', default=0.35, min=0.0, max=0.99, update=_colour_update,
                             description='Where along the strand the colour starts turning to the tip colour '
                                         '(0 = from the root, a long fade; 0.9 = only the very tips)')
    colour_random: FloatProperty(name='Strand Variation', default=0.3, min=0.0, max=1.0, update=_colour_update,
                                 description='Each strand a little lighter / darker / warmer than the next')
    shine: FloatProperty(name='Shine', default=0.4, min=0.0, max=1.0, update=_colour_update,
                         description='Glossy (1) or matt (0)')
    ring_colour: FloatVectorProperty(name='Ring Colour', subtype='COLOR', size=3, min=0.0, max=1.0,
                                     default=(0.8, 0.62, 0.28), update=_colour_update,
                                     description='The rings / beads (material slot 2)')
    live: BoolProperty(default=False, options={'HIDDEN'})
    last_error: StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'})


def _material(name, colour, metal, rough):
    """A plain material (reused when it already exists) so the rings show apart from the strands."""
    m = bpy.data.materials.get(name)
    if m is None:
        m = bpy.data.materials.new(name)
        m.diffuse_color = (*colour, 1.0)
        m.metallic = metal
        m.roughness = rough
        try:
            m.use_nodes = True
            b = m.node_tree.nodes.get('Principled BSDF')
            if b is not None:
                b.inputs['Base Color'].default_value = (*colour, 1.0)
                b.inputs['Metallic'].default_value = metal
                b.inputs['Roughness'].default_value = rough
        except (AttributeError, KeyError, TypeError):
            pass
    return m


def perform(context, loops, projector):
    """Area drawn on a head -> live creature hair.  Returns a report; raises cg.CutError."""
    from . import armor_plate as ap
    from . import cape_gen
    from . import face_extract as fx
    scene = context.scene
    st = scene.mch_hair
    groups = cg.prepare_loops(loops)
    target = cape_gen.pick_body(context, projector, groups)
    if target is not None and SRC_KEY in target:
        target = None
    if target is None:
        raise cg.CutError('Draw the hair area on a head (the scalp).')
    frozen = ap.freeze_projector(projector)
    if frozen is None:
        raise cg.CutError('This view cannot be saved for the hair.')
    me = bpy.data.meshes.new(target.name + '_Hair')
    ob = bpy.data.objects.new(me.name, me)
    fx._parts_collection(context, COLLECTION).objects.link(ob)
    body_mat = next((m for m in target.data.materials if m is not None), None)
    ob[SRC_KEY] = json.dumps({'loops': [[[float(x), float(y)] for x, y in lp] for lp in loops], 'proj': frozen,
                              'target': target.name})
    p = ob.mch_hair
    _BUSY[0] = True
    try:
        for k in LIVE_KEYS + ('style',) + COLOUR_KEYS:
            v = getattr(st, k)
            setattr(p, k, tuple(v) if not isinstance(v, (str, float, int)) else v)
    finally:
        _BUSY[0] = False
    try:
        rebuild(context, ob)
    except Exception:
        bpy.data.objects.remove(ob, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise
    cen = sum((v.co for v in me.vertices), Vector()) / max(1, len(me.vertices))
    me.transform(Matrix.Translation(-cen))
    ob.matrix_world = Matrix.Translation(cen)
    p.live = True
    _LAST[0] = ob.name
    apply_colours(ob, body_mat)                   # 0.24.169 its own colour (slot 1), the rings' (slot 2)
    mirrored = ''
    try:                                          # 0.24.169 (user: "머리카락은 왜 미러가 안 돼?") like the plates: a
        from . import symmetry                    # head with a live Mirror mirrors the hair grown on it
        mirrored = symmetry.follow(context, ob, target)
        if mirrored:                              # 0.24.171 cut (or not) by where its roots are, not the head's cut
            ob[MIRROR_FIT] = 1
            fit_mirror(ob)
    except (ImportError, AttributeError, RuntimeError, ReferenceError):
        pass
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    name = dict((s[0], s[1]) for s in STYLE_ITEMS)[p.style]
    return f'Creature hair "{ob.name}" on {target.name} ({name}, {len(me.polygons)} faces)' + mirrored


_LAST = [None]          # 0.24.169 the name of the hair made last (Enter applies it in the Hair tool)


def _is_live(ob):
    return (ob is not None and ob.type == 'MESH' and getattr(ob, 'mch_hair', None) is not None and ob.mch_hair.live
            and source(ob) is not None)


def apply_targets(context):
    """0.24.169 (user: "머리카락도 엔터 치면 어플라이 되게"): the live hair(s) Enter / Apply takes - the active one, else
    the selected live hairs, else (in the Hair tool) the one made last, even when the head was clicked since."""
    ob = live_hair(context)
    if ob is not None:
        return [ob]
    sel = [o for o in getattr(context, 'selected_objects', []) or [] if _is_live(o)]
    if sel:
        return sel
    try:
        from . import tool_state as ts
        in_tool = ts.effective_tool(context) == 'HAIR'
    except (AttributeError, ImportError, ReferenceError):
        in_tool = False
    last = bpy.data.objects.get(_LAST[0] or '')
    return [last] if in_tool and _is_live(last) else []


def live_hair(context):
    ob = getattr(context, 'active_object', None)
    if ob is not None and getattr(ob, 'mch_hair', None) is not None and ob.mch_hair.live and source(ob):
        return ob
    return None


def apply(ob):
    ob.mch_hair.live = False
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_hair_apply(bpy.types.Operator):
    bl_idname = 'mch.hair_apply'
    bl_label = 'Apply Hair'
    bl_description = 'The hair becomes a plain mesh (the sliders stop rebuilding it)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(apply_targets(context))

    def execute(self, context):
        obs = apply_targets(context)
        for ob in obs:
            apply(ob)
        self.report({'INFO'}, 'Hair applied: ' + ', '.join(o.name for o in obs))
        return {'FINISHED'}


def draw(layout, context):
    ob = live_hair(context)
    p = ob.mch_hair if ob is not None else context.scene.mch_hair
    box = layout.box()
    if ob is not None:
        box.label(text='LIVE Hair: ' + ob.name, icon='CURVES')
        if p.last_error:
            box.label(text=p.last_error, icon='ERROR')
    else:
        box.label(text='Creature Hair: settings for the next one', icon='CURVES')
    grid = box.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
    for key, label, _d in STYLE_ITEMS:                  # (0.24.169 eight styles: two rows)
        grid.prop_enum(p, 'style', key, text=label)
    col = box.column(align=True)                         # 0.24.169 the colour
    col.label(text='Colour')
    col.row(align=True).prop(p, 'colour_mode', expand=True)
    if p.colour_mode == 'OWN':
        g = col.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
        for key, label, _r, _t in COLOUR_PRESETS:
            g.operator('mch.hair_colour', text=label).preset = key
        r = col.row(align=True)
        r.prop(p, 'root_colour')
        r.prop(p, 'tip_colour')
        col.prop(p, 'tip_start', slider=True)
        col.prop(p, 'colour_random', slider=True)
        col.prop(p, 'shine', slider=True)
    if p.rings:
        col.prop(p, 'ring_colour')
    col = box.column(align=True)
    col.prop(p, 'count')
    col.prop(p, 'length', slider=True)
    col.prop(p, 'length_random', slider=True)
    col.prop(p, 'radius', slider=True)
    col.prop(p, 'radius_random', slider=True)
    col.prop(p, 'taper', slider=True)
    col = box.column(align=True)
    col.prop(p, 'lift', slider=True)
    col.prop(p, 'gravity', slider=True)
    col.prop(p, 'wave', slider=True)
    col.prop(p, 'straight', slider=True)
    col.prop(p, 'curl', slider=True)                     # 0.24.169 perm
    if p.curl > 0:
        col.prop(p, 'curl_turns', slider=True)
    col = box.column(align=True)                         # 0.24.171 Bend toward a side of the view
    col.label(text='Bend (toward a side of the view you look through)')
    for row_keys in (BEND_SIDES[:4], BEND_SIDES[4:] + (('OFF', 'No Bend'),)):
        r = col.row(align=True)
        for key, label in row_keys:
            on = (p.bend > 0 and p.bend_side == key) if key != 'OFF' else p.bend <= 0
            r.operator('mch.hair_bend', text=label, depress=on).side = key
    col.prop(p, 'bend', slider=True)
    if p.bend > 0:
        col.prop(p, 'bend_screen', slider=True)
        col.prop(p, 'bend_at', slider=True)
        col.prop(p, 'bend_soft', slider=True)
    col = box.column(align=True)
    col.prop(p, 'rope', slider=True)
    if p.rope > 0:
        col.prop(p, 'rope_twist', slider=True)
    r = col.row(align=True)
    r.prop(p, 'rings')
    if p.rings:
        r.prop(p, 'ring_size')
    col = box.column(align=True)
    col.prop(p, 'seed')
    col.prop(p, 'gap')
    r = col.row(align=True)
    r.prop(p, 'sides')
    r.prop(p, 'segments')
    if ob is not None:
        box.operator('mch.hair_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    for line in ('Draw the scalp area on a head (the chin for a beard)', 'Strands grow there and fall over the body',
                 'Colour: its own material - changes at once', 'Rings = material slot 2', 'Apply: plain mesh'):
        col.label(text=line)


CLASSES = (MCH_PG_Hair, MCH_OT_hair_apply, MCH_OT_hair_colour, MCH_OT_hair_bend)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_hair = bpy.props.PointerProperty(type=MCH_PG_Hair)
    bpy.types.Object.mch_hair = bpy.props.PointerProperty(type=MCH_PG_Hair)


def unregister():
    for n, t in (('mch_hair', bpy.types.Object), ('mch_hair', bpy.types.Scene)):
        try:
            delattr(t, n)
        except AttributeError:
            pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
