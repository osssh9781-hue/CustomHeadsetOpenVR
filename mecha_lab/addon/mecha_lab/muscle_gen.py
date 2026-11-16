"""0.24.183 Muscle Generator (user: "근육 제네레이터 만들자. 내가 끝과 끝 점을 이으면 거기에 근육이 생기는 거고, 기존 크리쳐
베이스 메쉬로 뼈대를 만들면 그 위에 생기는 거야 ... 어깨 근육은 세 덩이니까 쇠골 쪽, 등 쪽, 팔 쪽 이렇게 찍으면 ... 허벅지 앞
근육, 삼두 이거는 두 개만 찍어도 되고, 프리셋의 두께, 볼륨, 길이 조정 ... 그 이후에 근육 전체를 덮는 스킨"; "근육이랑 인공 근육
둘 다 두 줄짜리도 만들어 줘, 가슴 근육은 세 줄이 꼬여서 팔에 붙어 있는 거니까 시작하는 부분이랑 가슴 근육 두께 정하는 부분,
팔에 있는 부분 찍으면 ... 슬라이더로 근육 개수"; "메카 근육 할 때는 양 끝 마감이랑 내부 근육을 내가 프리셋 저장하게 해 주고 너도
따로 만들어서 내가 고르게 ... 케이블로만 바뀐 것도 ... 메카도 스킨 입혀지면 좋은데, 스킨이랑 근육은 다른 메쉬"; "근육 쪽에
내가 만들어 놓은 메쉬에 점점점 찍으면 우리 드래곤 클로스처럼 메쉬가 생기면 좋을 듯").

Click the points of a muscle on your mesh (the bones: Creature Base Mesh parts) - two for a long muscle (thigh front,
triceps: where it starts, where it ends), three for a fan (shoulder: collarbone, shoulder blade, arm; chest: where it
starts, how far down it reaches, the arm) - and the muscle lies on the mesh between them, following its surface.
Strands: how many bellies (two for a double one; the chest's twist into the arm).  Thickness, Volume, Width, Length,
Belly, Tendon, Sink and the fibres: live until Apply.  Membrane: click as many points as you like over the mesh, Enter:
a membrane between them (as Creature Cloth).

Two tools: Muscle (a muscle: its strands merged into one smooth mesh, fibres, tendons) and Mecha Muscle (the same
points and presets, made as an artificial muscle - an inner core (Fibre Bundle, Smooth, Ribbed, Piston), a sleeve
with holes (Square, Round, Hex, Slots) and end caps (Collar, Clamp, Cone, Nut, Fork, Plate) - or as Cables; your own
core / cap / whole presets saved).  Skin: one mesh of its own over the bones and every muscle (a creature's or a
mecha's), its own detail, tension and fat.
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, PointerProperty
from bpy.props import StringProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

KEY = 'mch_muscle'                 # on a muscle: its points (in its body's space), the body, the paths (json)
DONE = 'mch_muscle_done'
SKIN_KEY = 'mch_mskin'             # on a skin: the bodies it covers (json)
MOD = 'MCH Muscle'
TREE = 'MCH Muscle'
TREE_VERSION = 1
SKIN_MOD = 'MCH Skin'
COLLECTION = 'Muscles'
TEND = 'mch_mu_tend'               # on a muscle's points: 1 on a tendon, 0 on the belly
FIB_C, FIB_S = 'mch_mu_fc', 'mch_mu_fs'   # cos / sin of the angle round its strand (the fibres in the material)
MY_CORE, MY_CAP, MY_ALL = 'mecha_core', 'mecha_cap', 'mecha_muscle'

# (id, label, the points to click (None: as many as you like, Enter), kind, values)
#   kind: LINE (a muscle from one point to the other, Strands side by side), FAN (from a line between the first two
#   points to the third), SHEET (a membrane over the points)
PRESETS = (
    ('SPINDLE', 'Muscle', ('where it starts', 'where it ends'), 'LINE',
     dict(strands=1, twist=0.0, thickness=1.0, width=1.0, belly=0.5, tendon=0.15, segments=0)),
    ('DOUBLE', 'Two Strands', ('where it starts', 'where it ends'), 'LINE',
     dict(strands=2, twist=0.0, thickness=0.9, width=0.85, belly=0.5, tendon=0.15, segments=0)),
    ('BICEPS', 'Biceps', ('shoulder (front)', 'elbow (inside)'), 'LINE',
     dict(strands=2, twist=0.15, thickness=1.15, width=0.95, belly=0.55, tendon=0.2, segments=0)),
    ('TRICEPS', 'Triceps', ('shoulder (back)', 'elbow (back)'), 'LINE',
     dict(strands=3, twist=0.0, thickness=0.85, width=1.05, belly=0.4, tendon=0.28, segments=0)),
    ('QUAD', 'Thigh Front', ('hip (front)', 'knee'), 'LINE',
     dict(strands=3, twist=0.0, thickness=0.85, width=1.15, belly=0.48, tendon=0.14, segments=0)),
    ('HAMSTRING', 'Thigh Back', ('hip (back)', 'knee (back)'), 'LINE',
     dict(strands=2, twist=0.0, thickness=0.85, width=1.0, belly=0.45, tendon=0.2, segments=0)),
    ('CALF', 'Calf', ('knee (back)', 'heel'), 'LINE',
     dict(strands=2, twist=0.0, thickness=1.2, width=1.1, belly=0.3, tendon=0.38, segments=0)),
    ('FOREARM', 'Forearm', ('elbow', 'wrist'), 'LINE',
     dict(strands=2, twist=0.1, thickness=0.9, width=0.9, belly=0.3, tendon=0.3, segments=0)),
    ('NECK', 'Neck', ('behind the ear', 'collarbone (middle)'), 'LINE',
     dict(strands=1, twist=0.0, thickness=0.8, width=0.7, belly=0.5, tendon=0.12, segments=0)),
    ('ABS', 'Abs', ('ribs (bottom, middle)', 'pelvis (middle)'), 'LINE',
     dict(strands=2, twist=0.0, thickness=0.45, width=1.3, belly=0.5, tendon=0.04, segments=4)),
    ('DELTOID', 'Shoulder', ('collarbone (front)', 'shoulder blade (back)', 'arm (where it ends)'), 'FAN',
     dict(strands=3, twist=0.0, thickness=1.1, width=1.0, belly=0.38, tendon=0.2, segments=0)),
    ('PEC', 'Chest', ('where it starts (breastbone, top)', 'how far down (its thickness)', 'arm (where it ends)'),
     'FAN', dict(strands=3, twist=1.0, thickness=0.75, width=1.0, belly=0.35, tendon=0.15, segments=0)),
    ('LAT', 'Back (Lat)', ('lower back', 'mid back (spine)', 'armpit (where it ends)'), 'FAN',
     dict(strands=4, twist=0.3, thickness=0.5, width=1.0, belly=0.4, tendon=0.15, segments=0)),
    ('TRAP', 'Trapezius', ('skull (back)', 'mid back (spine)', 'shoulder (where it ends)'), 'FAN',
     dict(strands=3, twist=0.0, thickness=0.55, width=1.0, belly=0.45, tendon=0.1, segments=0)),
    ('GLUTE', 'Glute', ('hip (top)', 'tailbone', 'thigh (where it ends)'), 'FAN',
     dict(strands=3, twist=0.0, thickness=1.1, width=1.0, belly=0.4, tendon=0.15, segments=0)),
    ('MEMBRANE', 'Membrane', None, 'SHEET', dict()),
)
PRESET = {p[0]: p for p in PRESETS}
PRESET_ITEMS = [(p[0], p[1], ('Click: ' + ', '.join(p[2]) if p[2] else 'Click points over the mesh, Enter'))
                for p in PRESETS]
STYLES = (('CREATURE', 'Muscle', 'A muscle: smooth, fibres, tendons'),
          ('ARTIFICIAL', 'Artificial Muscle', 'A core in a holed sleeve, end caps'),
          ('CABLE', 'Cables', 'Cables between the points, end caps'))
CORES = (('BUNDLE', 'Fibre Bundle', 'Thin fibres twisting round each other'),
         ('SMOOTH', 'Smooth', 'One smooth spindle'),
         ('RIBBED', 'Ribbed', 'Rings along it (bellows)'),
         ('PISTON', 'Piston', 'A barrel and a rod'))
HOLES = (('NONE', 'No Sleeve', 'The core bare'),
         ('SOLID', 'Solid', 'A sleeve without holes'),
         ('SQUARE', 'Square', 'Square holes in rows'),
         ('ROUND', 'Round', 'Round holes in rows'),
         ('HEX', 'Hex', 'Six-sided holes'),
         ('SLOT', 'Slots', 'Long slots along it'))
CAPS = (('COLLAR', 'Collar', 'A thick ring'),
        ('CLAMP', 'Clamp', 'Two rings and bolts'),
        ('CONE', 'Cone', 'Tapering into a neck and a button'),
        ('NUT', 'Nut', 'A six-sided nut'),
        ('FORK', 'Fork', 'A fork (clevis) and its pin'),
        ('PLATE', 'Plate', 'An anchor plate on the surface, four bolts'))
CORE_KEYS = ('core', 'core_count', 'core_size', 'core_color')
CAP_KEYS = ('cap', 'cap_size', 'cap_length', 'cap_color')
_BUSY = [False]
_BVH = {}
PENDING = {'tool': None, 'pts': []}                     # the points clicked for the next muscle


# ---- objects ---------------------------------------------------------------------------------------------------------

def is_muscle(ob):
    return ob is not None and bool(ob.get(KEY))


def is_skin(ob):
    return ob is not None and bool(ob.get(SKIN_KEY))


def active_muscle(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_muscle(ob) else None


def data(ob):
    try:
        return json.loads(ob.get(KEY, '{}'))
    except ValueError:
        return {}


def settings(context, tool):
    sc = context.scene
    return sc.mch_mmuscle if tool == 'MMUSCLE' else sc.mch_muscle


# ---- the body's surface ------------------------------------------------------------------------------------------------

def body_bvh(context, body, others=()):
    """(BVH, size) of ``body`` (and ``others``) as shown - in ``body``'s own space."""
    dg = context.evaluated_depsgraph_get()
    obs = [body] + [o for o in others if o is not None and o is not body and o.type == 'MESH']
    key = tuple((o.name, len(o.data.vertices), tuple(round(x, 5) for r in o.matrix_world for x in r)) for o in obs)
    hit = _BVH.get('key')
    if hit == key:
        return _BVH['bvh'], _BVH['size']
    inv = body.matrix_world.inverted()
    V, T, off = [], [], 0
    for o in obs:
        ev = o.evaluated_get(dg)
        me = ev.to_mesh()
        try:
            me.calc_loop_triangles()
            M = inv @ o.matrix_world
            co = np.empty(len(me.vertices) * 3)
            me.vertices.foreach_get('co', co)
            co = co.reshape(-1, 3) @ np.array(M.to_3x3()).T + np.array(M.translation)
            tri = np.empty(len(me.loop_triangles) * 3, np.int64)
            me.loop_triangles.foreach_get('vertices', tri)
            V.append(co)
            T.append(tri.reshape(-1, 3) + off)
            off += len(co)
        finally:
            ev.to_mesh_clear()
    V = np.concatenate(V) if V else np.zeros((0, 3))
    T = np.concatenate(T) if T else np.zeros((0, 3), np.int64)
    bvh = BVHTree.FromPolygons(V.tolist(), T.tolist())
    size = float(np.ptp(V, axis=0).max()) if len(V) else 1.0
    _BVH.update(key=key, bvh=bvh, size=size)
    return bvh, size


def _near(bvh, p):
    loc, nrm, _i, _d = bvh.find_nearest(Vector(p))
    if loc is None:
        return np.asarray(p, float), np.array([0.0, 0.0, 1.0])
    return np.array(loc), np.array(nrm)


def surface_path(bvh, A, B, nA, nB, n=40, ext=0.3):
    """Points (n, 3) and normals on the surface from ``A`` to ``B`` (and ``ext`` of its length on past each end): the
    straight way between them pushed out over the surface (round the shoulder, not through it), smoothed."""
    A, B = np.asarray(A, float), np.asarray(B, float)
    nav = np.asarray(nA, float) + np.asarray(nB, float)
    if np.linalg.norm(nav) < 1e-6:
        nav = np.asarray(nA, float)
    nav = nav / max(np.linalg.norm(nav), 1e-9)
    L = max(float(np.linalg.norm(B - A)), 1e-9)
    ts = np.linspace(-ext, 1.0 + ext, n)
    P = np.array([A + (B - A) * t + nav * L * 0.18 * math.sin(math.pi * min(max(t, 0.0), 1.0)) for t in ts])
    out = [_near(bvh, p) for p in P]
    P = np.array([o[0] for o in out])
    N = np.array([o[1] for o in out])
    for _k in range(3):                               # (smoothed, back onto the surface)
        Q = P.copy()
        Q[1:-1] = P[1:-1] * 0.5 + (P[:-2] + P[2:]) * 0.25
        out = [_near(bvh, q) for q in Q]
        P = np.array([o[0] for o in out])
        N = np.array([o[1] for o in out])
    Ns = N.copy()
    Ns[1:-1] = N[1:-1] * 0.5 + (N[:-2] + N[2:]) * 0.25
    Ns /= np.maximum(np.linalg.norm(Ns, axis=1, keepdims=True), 1e-9)
    return P, Ns


def _onto(bvh, p):
    return _near(bvh, p)


def strand_ends(kind, pts, nrms, strands, twist, spread, bvh):
    """[(start, end, start normal, end normal, share of the width)] per strand."""
    pts = [np.asarray(p, float) for p in pts]
    nrms = [np.asarray(n, float) for n in nrms]
    n_ = max(int(strands), 1)
    out = []
    if kind == 'FAN':
        O1, O2, I = pts[0], pts[1], pts[2]
        nI = nrms[2]
        mid = (O1 + O2) * 0.5
        side_i = np.cross(I - mid, nI)
        side_i /= max(np.linalg.norm(side_i), 1e-9)
        L = float(np.linalg.norm(I - mid))
        span = float(np.linalg.norm(O2 - O1))
        for k in range(n_):
            f = k / (n_ - 1) if n_ > 1 else 0.5
            nav = nrms[0] * (1 - f) + nrms[1] * f
            o = O1 * (1 - f) + O2 * f + nav * span * 0.12 * math.sin(math.pi * f)
            o, on = _onto(bvh, o)
            # where it ends: the strands side by side at the arm - twist 1: in the other order (they cross)
            g = (f - 0.5) * (1.0 - 2.0 * float(twist))
            e, en = _onto(bvh, I + side_i * g * L * 0.12 * spread)
            out.append((o, e, on, en, span / n_ / max(L, 1e-9)))
        return out
    A, B = pts[0], pts[1]
    nA, nB = nrms[0], nrms[1]
    L = max(float(np.linalg.norm(B - A)), 1e-9)
    nav = (nA + nB)
    nav /= max(np.linalg.norm(nav), 1e-9)
    side = np.cross(B - A, nav)
    side /= max(np.linalg.norm(side), 1e-9)
    for k in range(n_):
        g = (k - (n_ - 1) / 2.0)
        w = 0.3 / math.sqrt(n_)
        a, an = _onto(bvh, A + side * g * L * w * 0.75 * spread)
        b, bn = _onto(bvh, B + side * g * L * w * 0.55 * spread * (1.0 - 2.0 * float(twist)))
        out.append((a, b, an, bn, w))
    return out


# ---- shapes -------------------------------------------------------------------------------------------------------------

def profile(t, belly, tendon, fan=False, segments=0):
    """A strand's size along it (0 .. 1): tendons at the ends (the far one longer), the belly where Belly says."""
    t = np.asarray(t, float)
    t0, t1 = tendon * 0.45, 1.0 - tendon
    u = np.clip((t - t0) / max(t1 - t0, 1e-6), 0.0, 1.0)
    k = math.log(0.5) / math.log(min(max(belly, 0.05), 0.95))
    w = u ** k
    tend_r = 0.16
    base = np.where(t < 0.5, 0.62 if fan else tend_r, tend_r) if fan else np.full_like(t, tend_r)
    r = base + (1.0 - base) * np.sin(math.pi * w) ** 0.9
    if fan:                                           # (a fan: broad where it starts, a tendon where it ends)
        r = np.where(t < 0.5, np.maximum(r, 0.62 * (1.0 - t)), r)
    if segments > 0:                                  # (the abs: a groove across between each pack)
        x = u * segments
        dip = np.exp(-((x - np.round(x)) / 0.07) ** 2) * ((x > 0.5) & (x < segments - 0.5))
        r = r * (1.0 - 0.32 * dip)
    return r


def _frames(P, N):
    T = np.gradient(P, axis=0)
    T /= np.maximum(np.linalg.norm(T, axis=1, keepdims=True), 1e-12)
    n = N - T * (N * T).sum(1, keepdims=True)
    n /= np.maximum(np.linalg.norm(n, axis=1, keepdims=True), 1e-12)
    side = np.cross(T, n)
    return T, n, side


def _resample(P, N, s0, s1, n):
    """``n`` points from arc share ``s0`` to ``s1`` of the polyline (past its ends: on along its end directions)."""
    seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)])
    L = max(s[-1], 1e-12)
    q = np.linspace(s0, s1, n) * L
    out_p, out_n = [], []
    for x in q:
        if x <= 0:
            d = P[1] - P[0]
            out_p.append(P[0] + d / max(np.linalg.norm(d), 1e-12) * x)
            out_n.append(N[0])
        elif x >= L:
            d = P[-1] - P[-2]
            out_p.append(P[-1] + d / max(np.linalg.norm(d), 1e-12) * (x - L))
            out_n.append(N[-1])
        else:
            i = int(np.searchsorted(s, x) - 1)
            f = (x - s[i]) / max(s[i + 1] - s[i], 1e-12)
            out_p.append(P[i] * (1 - f) + P[i + 1] * f)
            nn = N[i] * (1 - f) + N[i + 1] * f
            out_n.append(nn / max(np.linalg.norm(nn), 1e-12))
    return np.array(out_p), np.array(out_n)


class Mesh:
    """Verts / faces / material index / tendon value, gathered."""

    def __init__(self):
        self.V, self.F, self.M, self.T, self.A = [], [], [], [], []

    def add_v(self, p, tend=0.0, ang=0.0):
        self.V.append(tuple(float(x) for x in p))
        self.T.append(float(tend))
        self.A.append(float(ang))
        return len(self.V) - 1

    def add_f(self, idx, mat=0):
        self.F.append(tuple(idx))
        self.M.append(mat)


def tube(mesh, C, A1, A2, ra, rb, mat=0, tend=None, caps=True, sides=14, flat=1.0):
    """A closed tube through centres ``C`` (n, 3): at each, an ellipse ``ra`` along ``A1``, ``rb`` along ``A2``
    (``flat``: the A2 side below the centre flattened by that share)."""
    n = len(C)
    ang = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    rings = []
    for i in range(n):
        ring = []
        for a in ang:
            s_ = math.sin(a)
            p = C[i] + A1[i] * math.cos(a) * ra[i] + A2[i] * s_ * rb[i] * (flat if s_ < 0 else 1.0)
            ring.append(mesh.add_v(p, tend[i] if tend is not None else 0.0, a))
        rings.append(ring)
    for i in range(n - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            mesh.add_f((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k]), mat)
    if caps:
        for i, rev in ((0, True), (n - 1, False)):
            ring = rings[i]
            mesh.add_f(tuple(reversed(ring)) if rev else tuple(ring), mat)
    return rings


def cylinder(mesh, c, axis, r_out, length, mat=0, r_in=0.0, sides=16, side=None):
    """A ring (``r_in`` > 0) or a solid cylinder centred at ``c`` along ``axis``."""
    axis = np.asarray(axis, float)
    axis = axis / max(np.linalg.norm(axis), 1e-12)
    u = np.asarray(side, float) if side is not None else np.cross(axis, (0.0, 0.0, 1.0) if abs(axis[2]) < 0.9 else (1.0, 0.0, 0.0))
    u = u - axis * float(np.dot(u, axis))
    u /= max(np.linalg.norm(u), 1e-12)
    v = np.cross(axis, u)
    ang = np.linspace(0, 2 * math.pi, sides, endpoint=False)
    h = axis * length * 0.5

    def ring(r, z):
        return [mesh.add_v(c + z + (u * math.cos(a) + v * math.sin(a)) * r) for a in ang]
    o0, o1 = ring(r_out, -h), ring(r_out, h)
    for k in range(sides):
        k2 = (k + 1) % sides
        mesh.add_f((o0[k], o0[k2], o1[k2], o1[k]), mat)
    if r_in > 0:
        i0, i1 = ring(r_in, -h), ring(r_in, h)
        for k in range(sides):
            k2 = (k + 1) % sides
            mesh.add_f((i0[k2], i0[k], i1[k], i1[k2]), mat)
            mesh.add_f((o0[k2], o0[k], i0[k], i0[k2]), mat)
            mesh.add_f((o1[k], o1[k2], i1[k2], i1[k]), mat)
    else:
        mesh.add_f(tuple(reversed(o0)), mat)
        mesh.add_f(tuple(o1), mat)


def box(mesh, c, ax, ay, az, sx, sy, sz, mat=0):
    """A box centred at ``c``, half sizes along the axes."""
    c = np.asarray(c, float)
    ids = {}
    for i in (-1, 1):
        for j in (-1, 1):
            for k in (-1, 1):
                ids[(i, j, k)] = mesh.add_v(c + ax * sx * i + ay * sy * j + az * sz * k)
    for f in (((-1, -1, -1), (-1, 1, -1), (1, 1, -1), (1, -1, -1)), ((-1, -1, 1), (1, -1, 1), (1, 1, 1), (-1, 1, 1)),
              ((-1, -1, -1), (1, -1, -1), (1, -1, 1), (-1, -1, 1)), ((-1, 1, -1), (-1, 1, 1), (1, 1, 1), (1, 1, -1)),
              ((-1, -1, -1), (-1, -1, 1), (-1, 1, 1), (-1, 1, -1)), ((1, -1, -1), (1, 1, -1), (1, 1, 1), (1, -1, 1))):
        mesh.add_f(tuple(ids[x] for x in f), mat)


def cap(mesh, design, c, axis, n, r, length, size, mat=2):
    """An end cap at ``c`` (the strand's end), ``axis`` pointing out of the strand, ``n`` the surface normal."""
    axis = np.asarray(axis, float) / max(np.linalg.norm(axis), 1e-12)
    n = np.asarray(n, float) - axis * float(np.dot(n, axis))
    n /= max(np.linalg.norm(n), 1e-12)
    s = np.cross(axis, n)
    R = r * size
    if design == 'COLLAR':
        cylinder(mesh, c, axis, R, length, mat, r_in=r * 0.7, side=n)
    elif design == 'CLAMP':
        for z in (-0.3, 0.3):
            cylinder(mesh, c + axis * length * z, axis, R, length * 0.28, mat, r_in=r * 0.7, side=n)
        for a in range(4):
            d = n * math.cos(a * math.pi / 2 + math.pi / 4) + s * math.sin(a * math.pi / 2 + math.pi / 4)
            cylinder(mesh, c + d * R * 1.02, d, R * 0.16, R * 0.22, mat, sides=6)
    elif design == 'CONE':
        sides = 16
        ang = np.linspace(0, 2 * math.pi, sides, endpoint=False)
        r0 = [mesh.add_v(c - axis * length * 0.5 + (n * math.cos(a) + s * math.sin(a)) * R) for a in ang]
        r1 = [mesh.add_v(c + axis * length * 0.5 + (n * math.cos(a) + s * math.sin(a)) * r * 0.45) for a in ang]
        for k in range(sides):
            k2 = (k + 1) % sides
            mesh.add_f((r0[k], r0[k2], r1[k2], r1[k]), mat)
        mesh.add_f(tuple(reversed(r0)), mat)
        mesh.add_f(tuple(r1), mat)
        cylinder(mesh, c + axis * length * 0.62, axis, r * 0.62, length * 0.25, mat, side=n)
    elif design == 'NUT':
        cylinder(mesh, c, axis, R * 1.1, length, mat, r_in=r * 0.55, sides=6, side=n)
    elif design == 'FORK':
        for sgn in (-1, 1):
            box(mesh, c + axis * length * 0.35 + s * sgn * R * 0.8, axis, n, s, length * 0.65, R * 0.9, R * 0.18, mat)
        cylinder(mesh, c + axis * length * 0.7, s, R * 0.35, R * 2.2, mat, side=n)
        cylinder(mesh, c - axis * length * 0.1, axis, R * 0.95, length * 0.5, mat, side=n)
    else:                                             # PLATE: on the surface under the end
        base = c - n * r * 0.75
        box(mesh, base, axis, s, n, R * 1.5, R * 1.5, r * 0.12, mat)
        for i in (-1, 1):
            for j in (-1, 1):
                cylinder(mesh, base + axis * R * 1.05 * i + s * R * 1.05 * j + n * r * 0.18, n, R * 0.2, r * 0.14,
                         mat, sides=6)
        cylinder(mesh, c - n * r * 0.3, n, R * 0.65, r * 0.7, mat, side=axis)


def _zip(outer, inner, oa, ia):
    """Triangles between two closed rings (indices, angles sorted from 0): the annulus round a hole."""
    tris = []
    i = j = 0
    no, ni = len(outer), len(inner)
    while i < no or j < ni:
        a_next = oa[(i + 1) % no] + (2 * math.pi if i + 1 >= no else 0.0) if i < no else 1e9
        b_next = ia[(j + 1) % ni] + (2 * math.pi if j + 1 >= ni else 0.0) if j < ni else 1e9
        if a_next <= b_next:
            tris.append((outer[i % no], outer[(i + 1) % no], inner[j % ni]))
            i += 1
        else:
            tris.append((outer[i % no], inner[(j + 1) % ni], inner[j % ni]))
            j += 1
    return tris


def sleeve(mesh, C, n_, s_, ra, rb, t0, t1, holes, cells_u, hole_size, thick, mat=1):
    """A sleeve round the centres ``C`` from arc share ``t0`` to ``t1``: a grid of cells round and along it, each
    a hole (Square / Round / Hex / Slot) in the middle rows, solid in the first and last; the wall Thickness thick,
    the holes' sides and the ends closed."""
    n = len(C)
    seg = np.linalg.norm(np.diff(C, axis=0), axis=1)
    s = np.concatenate([[0.0], np.cumsum(seg)]) / max(seg.sum(), 1e-12)
    circ = 2 * math.pi * float(np.mean(ra))
    L = float(seg.sum()) * (t1 - t0)
    nu = max(int(cells_u), 4)
    nv = min(max(2, int(round(L / max(circ / nu, 1e-9)))), nu * 3)

    def frame(v):
        t = t0 + (t1 - t0) * v / nv
        i = int(np.clip(np.searchsorted(s, t) - 1, 0, n - 2))
        f = (t - s[i]) / max(s[i + 1] - s[i], 1e-12)
        return (C[i] * (1 - f) + C[i + 1] * f, n_[i] * (1 - f) + n_[i + 1] * f, s_[i] * (1 - f) + s_[i + 1] * f,
                ra[i] * (1 - f) + ra[i + 1] * f, rb[i] * (1 - f) + rb[i + 1] * f)
    cache = {}

    def vid(u, v, layer):
        """the point at grid (u, v) on the outer (0) or inner (1) layer (u round: wraps)"""
        u = u % nu
        key = (round(u, 6), round(v, 6), layer)
        if key in cache:
            return cache[key]
        c, nn, ss, a1, a2 = frame(v)
        phi = 2 * math.pi * u / nu
        k = 1.0 if layer == 0 else max(1.0 - thick / max(min(a1, a2), 1e-9), 0.2)
        p = c + (ss * math.cos(phi) * a1 + nn * math.sin(phi) * a2) * k
        cache[key] = mesh.add_v(p)
        return cache[key]
    style = holes
    edge_pts = {'SQUARE': (), 'ROUND': ('mid',), 'SLOT': ('mid',), 'HEX': ('tb',), 'SOLID': ()}[style]

    def outer_ring(i, j):
        """(grid points (u, v), angles) round cell (i, j): its corners and the edge points the scheme shares"""
        pts = [((i + 1, j + 1), math.radians(45)), ((i, j + 1), math.radians(135)), ((i, j), math.radians(225)),
               ((i + 1, j), math.radians(315))]
        if 'mid' in edge_pts:
            pts += [((i + 1, j + 0.5), 0.0), ((i + 0.5, j + 1), math.radians(90)), ((i, j + 0.5), math.radians(180)),
                    ((i + 0.5, j), math.radians(270))]
        elif 'tb' in edge_pts:
            pts += [((i + 0.5, j + 1), math.radians(90)), ((i + 0.5, j), math.radians(270))]
        pts.sort(key=lambda q: q[1])
        return [q[0] for q in pts], [q[1] for q in pts]

    def hole_ring(i, j):
        cx, cy = i + 0.5, j + 0.5
        if style == 'SQUARE':
            k, a0, sx, sy = 4, math.radians(45), 0.5 * hole_size * math.sqrt(2), 0.5 * hole_size * math.sqrt(2)
        elif style == 'HEX':
            k, a0, sx, sy = 6, 0.0, 0.5 * hole_size, 0.5 * hole_size
        elif style == 'SLOT':
            k, a0, sx, sy = 8, 0.0, 0.5 * hole_size * 0.45, 0.5 * hole_size * 1.15
        else:
            k, a0, sx, sy = 8, 0.0, 0.5 * hole_size, 0.5 * hole_size
        angs = [a0 + 2 * math.pi * q / k for q in range(k)]
        return [(cx + math.cos(a) * sx, min(max(cy + math.sin(a) * sy, j + 0.04), j + 0.96)) for a in angs], angs
    hole_rims = []
    for j in range(nv):
        for i in range(nu):
            ring, ra_ = outer_ring(i, j)
            o_out = [vid(u, v, 0) for u, v in ring]
            o_in = [vid(u, v, 1) for u, v in ring]
            if style == 'SOLID' or j == 0 or j == nv - 1:
                mesh.add_f(tuple(o_out), mat)
                mesh.add_f(tuple(reversed(o_in)), mat)
                continue
            hp, ha = hole_ring(i, j)
            h_out = [vid(u, v, 0) for u, v in hp]
            h_in = [vid(u, v, 1) for u, v in hp]
            for a, b, c in _zip(o_out, h_out, ra_, ha):
                mesh.add_f((a, b, c), mat)
            for a, b, c in _zip(o_in, h_in, ra_, ha):
                mesh.add_f((c, b, a), mat)
            hole_rims.append((h_out, h_in))
    for h_out, h_in in hole_rims:                     # (the holes' sides)
        k = len(h_out)
        for q in range(k):
            q2 = (q + 1) % k
            mesh.add_f((h_out[q2], h_out[q], h_in[q], h_in[q2]), mat)
    for j, flip in ((0, True), (nv, False)):          # (the sleeve's ends)
        us = []
        for i in range(nu):
            us.append(i)
            if 'mid' in edge_pts or 'tb' in edge_pts:
                us.append(i + 0.5)
        for q in range(len(us)):
            u1, u2 = us[q], us[(q + 1) % len(us)]
            a, b = vid(u1, j, 0), vid(u2, j, 0)
            c, d = vid(u2, j, 1), vid(u1, j, 1)
            mesh.add_f((a, b, c, d) if not flip else (d, c, b, a), mat)


# ---- a muscle from its settings ---------------------------------------------------------------------------------------

def paths_of(context, ob, force=False):
    """The strands' paths (in the body's space): kept on the muscle, worked out again when its points or strands
    changed."""
    d = data(ob)
    pg = ob.mch_muscle
    kind = PRESET[pg.preset][3]
    key = [pg.preset, int(pg.strands), round(float(pg.twist), 4), round(float(pg.spread), 4)]
    if not force and d.get('paths') and d.get('pkey') == key:
        return [(np.array(p['P']), np.array(p['N']), p['w']) for p in d['paths']]
    body = bpy.data.objects.get(d.get('body', ''))
    if body is None:
        raise RuntimeError('The mesh the muscle was made on is gone')
    others = [bpy.data.objects.get(n) for n in d.get('others', [])]
    bvh, _size = body_bvh(context, body, others)
    ends = strand_ends(kind, d['pts'], d['nrm'], pg.strands, pg.twist, pg.spread, bvh)
    paths = []
    for a, b, an, bn, w in ends:
        P, N = surface_path(bvh, a, b, an, bn)
        paths.append((P, N, w))
    d['paths'] = [{'P': P.round(6).tolist(), 'N': N.round(5).tolist(), 'w': float(w)} for P, N, w in paths]
    d['pkey'] = key
    ob[KEY] = json.dumps(d)
    return paths


def build_mesh(context, ob):
    """The muscle's mesh from its paths and sliders (``Mesh``), and the length of its first strand."""
    pg = ob.mch_muscle
    kind = PRESET[pg.preset][3]
    paths = paths_of(context, ob)
    mesh = Mesh()
    ext = 0.3                                         # (the paths go on this share past each end, see surface_path)
    lens = []
    style = pg.style
    for si, (P, N, w) in enumerate(paths):
        seg = np.linalg.norm(np.diff(P, axis=0), axis=1)
        full = float(seg.sum())
        L0 = full / (1.0 + 2 * ext)                   # (the clicked length)
        lens.append(L0)
        half = 0.5 * float(pg.length)
        mid = 0.5
        s0 = mid - half / (1.0 + 2 * ext)
        s1 = mid + half / (1.0 + 2 * ext)
        K = 40
        C, Nn = _resample(P, N, s0, s1, K)
        T, nrm, side = _frames(C, Nn)
        t = np.linspace(0.0, 1.0, K)
        L = L0 * float(pg.length)
        fan = kind == 'FAN'
        r = profile(t, pg.belly, pg.tendon, fan=fan, segments=int(pg.segments))
        vol = float(pg.volume)
        if fan:                                       # (a fan's strands overlap into one sheet)
            base_w = w * L0 * 1.45
        else:                                         # (a muscle about a third as wide as it is long)
            base_w = 0.36 * L0 * w / 0.3 / math.sqrt(max(len(paths), 1))
        W = base_w * float(pg.width) * vol * r
        H = base_w * 0.62 * float(pg.thickness) * vol * r * (0.6 if fan else 1.0)
        if style == 'CREATURE':                       # (light: each strand a clean tube, its fibres in the material)
            K2 = max(int(pg.resolution), 16)
            C, Nn = _resample(P, N, s0, s1, K2)
            T, nrm, side = _frames(C, Nn)
            t2 = np.linspace(0.0, 1.0, K2)
            r2 = profile(t2, pg.belly, pg.tendon, fan=fan, segments=int(pg.segments))
            W2 = base_w * float(pg.width) * vol * r2
            H2 = base_w * 0.62 * float(pg.thickness) * vol * r2 * (0.6 if fan else 1.0)
            ctr = C + nrm * (H2 * (1.0 - float(pg.sink)))[:, None]
            tend = np.clip(1.0 - (r2 - 0.16) / 0.5, 0.0, 1.0)
            tube(mesh, ctr, side, nrm, W2, H2, 0, tend=tend, flat=0.55, sides=18)
        elif style == 'CABLE':
            rc = np.full(K, base_w * 0.18 * float(pg.cable_radius) / 0.2 * vol)
            ctr = C + nrm * (rc * 1.05)[:, None]
            tube(mesh, ctr, side, nrm, rc, rc, 0, sides=10)
            for end, sgn in ((0, -1.0), (K - 1, 1.0)):
                cap(mesh, pg.cap, ctr[end], T[end] * sgn, nrm[end], rc[end] * 1.4, L * float(pg.cap_length) * 0.6,
                    float(pg.cap_size), mat=2)
        else:                                         # ARTIFICIAL: core, sleeve, caps
            R = np.maximum(W, H) * 0.5 + 1e-6
            Ra, Rb = np.maximum(W * 0.5, 1e-6), np.maximum(H * 0.5, 1e-6)
            Rm = float(np.max(R))
            ctr = C + nrm * (Rb * (1.05 - float(pg.sink)))[:, None]
            cl = min(float(pg.cap_length), 0.3)
            i0, i1 = int(round(cl * (K - 1))), int(round((1 - cl) * (K - 1)))
            cs = float(pg.core_size)
            core = pg.core
            sl = slice(i0, i1 + 1)
            if core == 'SMOOTH':
                tube(mesh, ctr[sl], side[sl], nrm[sl], Ra[sl] * cs, Rb[sl] * cs, 0)
            elif core == 'RIBBED':
                k_ = max(int(pg.core_count), 2)
                rib = 1.0 - 0.16 * np.abs(np.sin(np.linspace(0, math.pi * k_, i1 - i0 + 1))) ** 0.5
                tube(mesh, ctr[sl], side[sl], nrm[sl], Ra[sl] * cs * rib, Rb[sl] * cs * rib, 0, sides=16)
            elif core == 'PISTON':
                m_ = (i0 + i1) // 2 + 2
                barrel = np.full(m_ - i0 + 1, Rm * cs * 0.8)
                tube(mesh, ctr[i0:m_ + 1], side[i0:m_ + 1], nrm[i0:m_ + 1], barrel, barrel, 0, sides=16)
                rod = np.full(i1 - m_ + 3, Rm * cs * 0.32)
                tube(mesh, ctr[m_ - 2:i1 + 1], side[m_ - 2:i1 + 1], nrm[m_ - 2:i1 + 1], rod, rod, 0, sides=12)
            else:                                     # BUNDLE: fibres twisting round the axis
                nf = max(int(pg.core_count), 3)
                tt = np.linspace(0, 1, i1 - i0 + 1)
                for f in range(nf):
                    ph = 2 * math.pi * f / nf + tt * math.pi * 1.2
                    off = (side[sl] * np.cos(ph)[:, None] * Ra[sl, None] + nrm[sl] * np.sin(ph)[:, None] * Rb[sl, None])
                    fr = np.maximum(np.minimum(Ra[sl], Rb[sl]) * cs * 0.42, 1e-6)
                    tube(mesh, ctr[sl] + off * cs * 0.55, side[sl], nrm[sl], fr, fr, 0, sides=6)
            if pg.holes != 'NONE':
                sleeve(mesh, ctr, nrm, side, Ra * 1.02, Rb * 1.02, cl * 0.9, 1.0 - cl * 0.9,
                       'SOLID' if pg.holes == 'SOLID' else pg.holes, int(pg.hole_cells), float(pg.hole_size),
                       Rm * float(pg.sleeve_thick), mat=1)
            for end, sgn in ((i0, -1.0), (i1, 1.0)):
                cap(mesh, pg.cap, ctr[end], T[end] * sgn, nrm[end], max(Ra[end], Rb[end]) * 1.05,
                    L * cl * 0.8, float(pg.cap_size), mat=2)
    return mesh, (lens[0] if lens else 1.0)


def materials(ob):
    """The muscle's own materials: [muscle / core, sleeve, caps]."""
    pg = ob.mch_muscle
    d = data(ob)
    names = d.get('mats') or []
    mats = [bpy.data.materials.get(n) for n in names] if names else []
    if len(mats) != 3 or any(m is None for m in mats):
        mats = []
        for nm in ('Muscle', 'Sleeve', 'Cap'):
            m = bpy.data.materials.new(f'MCH {nm}')
            m.use_nodes = True
            mats.append(m)
        d['mats'] = [m.name for m in mats]
        ob[KEY] = json.dumps(d)
    core, slv, cp = mats
    creature = pg.style == 'CREATURE'
    _principled(core, pg.color if creature else pg.core_color, 0.45 if creature else 0.5, 0.0,
                sss=0.25 if creature else 0.0, tendon=pg.tendon_color if creature else None)
    if creature:
        _fibres(core, float(pg.fibers), float(pg.fiber_scale))
    _principled(slv, pg.sleeve_color, 0.35, 0.6)
    _principled(cp, pg.cap_color, 0.3, 1.0)
    return mats


def _fibres(m, amount, scale):
    """The fibres: lines along the strand (the angle round it, from the points' cos / sin), a bump - no points."""
    nt = m.node_tree
    bs = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    bump = nt.nodes.get('MCH Fibres')
    if bump is None and bs is not None:
        ac, as_ = nt.nodes.new('ShaderNodeAttribute'), nt.nodes.new('ShaderNodeAttribute')
        ac.attribute_name, as_.attribute_name = FIB_C, FIB_S
        at2 = nt.nodes.new('ShaderNodeMath')
        at2.operation = 'ARCTAN2'
        nt.links.new(as_.outputs['Fac'], at2.inputs[0])
        nt.links.new(ac.outputs['Fac'], at2.inputs[1])
        mul = nt.nodes.new('ShaderNodeMath')
        mul.operation = 'MULTIPLY'
        mul.name = 'MCH Fibre Count'
        nt.links.new(at2.outputs[0], mul.inputs[0])
        sn = nt.nodes.new('ShaderNodeMath')
        sn.operation = 'SINE'
        nt.links.new(mul.outputs[0], sn.inputs[0])
        bump = nt.nodes.new('ShaderNodeBump')
        bump.name = 'MCH Fibres'
        nt.links.new(sn.outputs[0], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], bs.inputs['Normal'])
    if bump is not None:
        bump.inputs['Strength'].default_value = min(max(amount, 0.0), 2.0) * 0.25
        nt.nodes['MCH Fibre Count'].inputs[1].default_value = max(scale, 1.0) * 0.5


def _principled(m, col, rough, metal, sss=0.0, tendon=None):
    nt = m.node_tree
    bs = next((n for n in nt.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if bs is None:
        return
    a = tuple(col) + (1.0,)
    if tendon is not None:
        mix = nt.nodes.get('MCH Tendon')
        if mix is None:
            at = nt.nodes.new('ShaderNodeAttribute')
            at.attribute_name = TEND
            mix = nt.nodes.new('ShaderNodeMix')
            mix.data_type = 'RGBA'
            mix.name = 'MCH Tendon'
            nt.links.new(at.outputs['Fac'], mix.inputs[0])
            nt.links.new(mix.outputs[2], bs.inputs['Base Color'])
        mix.inputs[6].default_value = a
        mix.inputs[7].default_value = tuple(tendon) + (1.0,)
    else:
        bs.inputs['Base Color'].default_value = a
    bs.inputs['Roughness'].default_value = rough
    bs.inputs['Metallic'].default_value = metal
    try:
        bs.inputs['Subsurface Weight'].default_value = sss
        bs.inputs['Subsurface Radius'].default_value = (0.3, 0.06, 0.04)
        bs.inputs['Subsurface Scale'].default_value = 0.02
    except KeyError:
        pass
    m.diffuse_color = a


def muscle_tree():
    """A muscle's strands merged into one smooth mesh (a volume, adaptive), its tendons kept (for the colour), fine
    fibres running toward where it ends."""
    from .creature_fur import _B, _socket
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _socket(ng, 'Geometry', 'GEOMETRY')
    for name, kind, default in (('Remesh', 'BOOL', True), ('Voxel', 'FLOAT', 0.01), ('Adaptivity', 'FLOAT', 0.25),
                                ('Smooth', 'INT', 2), ('Fibers', 'FLOAT', 0.5), ('Fiber Scale', 'FLOAT', 30.0),
                                ('Size', 'FLOAT', 1.0), ('Insertion', 'VECTOR', (0.0, 0.0, 0.0))):
        _socket(ng, name, kind, default)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs
    m2v = b.node('GeometryNodeMeshToVolume')
    b.feed(m2v.inputs['Mesh'], I['Geometry'])
    try:
        m2v.inputs['Resolution Mode'].default_value = 'Size'
    except (TypeError, ValueError):
        pass
    b.feed(m2v.inputs['Voxel Size'], I['Voxel'])
    v2m = b.node('GeometryNodeVolumeToMesh')
    b.feed(v2m.inputs['Volume'], m2v.outputs['Volume'])
    try:
        v2m.inputs['Resolution Mode'].default_value = 'Size'
    except (TypeError, ValueError):
        pass
    b.feed(v2m.inputs['Voxel Size'], I['Voxel'])
    v2m.inputs['Threshold'].default_value = 0.3
    b.feed(v2m.inputs['Adaptivity'], I['Adaptivity'])
    sw = b.node('GeometryNodeSwitch', input_type='GEOMETRY')
    b.feed(sw.inputs['Switch'], I['Remesh'])
    b.feed(sw.inputs['False'], I['Geometry'])
    b.feed(sw.inputs['True'], v2m.outputs['Mesh'])
    geo = sw.outputs['Output']
    tn = b.node('GeometryNodeSampleNearestSurface', data_type='FLOAT')
    b.feed(tn.inputs['Mesh'], I['Geometry'])
    b.feed(tn.inputs['Value'], b.attr(TEND).outputs['Attribute'])
    geo = b.store(geo, TEND, tn.outputs['Value'])
    P = b.node('GeometryNodeInputPosition').outputs['Position']
    bl = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(bl.inputs['Value'], P)
    b.feed(bl.inputs['Iterations'], I['Smooth'])
    sp0 = b.node('GeometryNodeSetPosition')
    b.feed(sp0.inputs['Geometry'], geo)
    b.feed(sp0.inputs['Position'], bl.outputs['Value'])
    geo = sp0.outputs['Geometry']
    P = b.node('GeometryNodeInputPosition').outputs['Position']
    N = b.node('GeometryNodeInputNormal').outputs['Normal']
    dirn = b.vec('NORMALIZE', b.vec('SUBTRACT', P, I['Insertion']))
    nz = b.node('ShaderNodeTexNoise')
    b.feed(nz.inputs['Vector'], dirn)
    b.feed(nz.inputs['Scale'], I['Fiber Scale'])
    nz.inputs['Detail'].default_value = 1.0
    fib = b.math('SUBTRACT', nz.outputs['Factor'], 0.5)
    amt = b.math('MULTIPLY', b.math('MULTIPLY', I['Fibers'], b.math('MULTIPLY', I['Size'], 0.006)),
                 b.math('SUBTRACT', 1.0, b.attr(TEND).outputs['Attribute']))
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], geo)
    b.feed(sp.inputs['Offset'], b.vec('SCALE', N, scale=b.math('MULTIPLY', fib, amt)))
    sm = b.node('GeometryNodeSetShadeSmooth')
    b.feed(sm.inputs['Mesh'], sp.outputs['Geometry'])
    b.feed(go.inputs[0], sm.outputs['Mesh'])
    ng['mch_v'] = TREE_VERSION
    return ng


def build(ob, context=None):
    """Lay the muscle again (its mesh, its modifier, its materials); returns the face count of its base mesh."""
    context = context or bpy.context
    pg = ob.mch_muscle
    mesh, L = build_mesh(context, ob)
    me = ob.data
    me.clear_geometry()
    me.from_pydata(mesh.V, [], mesh.F)
    me.validate(clean_customdata=False)
    if len(me.polygons) == len(mesh.M):
        me.polygons.foreach_set('material_index', np.array(mesh.M, np.int32))
    at = me.attributes.get(TEND) or me.attributes.new(TEND, 'FLOAT', 'POINT')
    if len(at.data) == len(mesh.T):
        at.data.foreach_set('value', np.array(mesh.T, np.float32))
    A = np.array(mesh.A, np.float32)
    for nm, arr in ((FIB_C, np.cos(A)), (FIB_S, np.sin(A))):      # (round the strand, no seam: the fibres' way)
        a2 = me.attributes.get(nm) or me.attributes.new(nm, 'FLOAT', 'POINT')
        if len(a2.data) == len(arr):
            a2.data.foreach_set('value', arr.astype(np.float32))
    mats = materials(ob)
    if len(me.materials) != 3:
        me.materials.clear()
        for m in mats:
            me.materials.append(m)
    mod = ob.modifiers.get(MOD)
    creature = pg.style == 'CREATURE'
    if creature and pg.remesh:
        if mod is None:
            mod = ob.modifiers.new(MOD, 'NODES')
            try:
                ob.modifiers.move(len(ob.modifiers) - 1, 0)
            except (RuntimeError, TypeError, AttributeError):
                pass
        if mod.node_group is None or mod.node_group.get('mch_v') != TREE_VERSION:
            mod.node_group = muscle_tree()
        from . import geo_sculpt as gs
        d = data(ob)
        ins = np.array(d['pts'][-1], float)
        vals = {'Remesh': True, 'Voxel': max(L, 1e-6) / max(int(pg.resolution), 10),
                'Adaptivity': 0.25, 'Smooth': int(pg.smooth), 'Fibers': float(pg.fibers),
                'Fiber Scale': float(pg.fiber_scale), 'Size': max(L, 1e-6), 'Insertion': tuple(ins)}
        for k, v in vals.items():
            try:
                gs.set_input(mod, k, v)
            except (KeyError, AttributeError, TypeError):
                pass
    elif mod is not None:
        ob.modifiers.remove(mod)
    for f in me.polygons:
        f.use_smooth = creature or pg.style == 'CABLE'
    me.update()
    ob.update_tag()
    return len(me.polygons)


def follow_mirror(ob, body):
    """The body's live Mirror on the muscle too (across each plane all its points are on one side of)."""
    from . import symmetry
    m = symmetry.mirror_mod(body)
    if m is None or not any(m.use_axis):
        return ''
    d = data(ob)
    P = np.array(d['pts'], float)
    piv = m.mirror_object
    if piv is not None:
        PM = np.array(body.matrix_world.inverted() @ piv.matrix_world)
        local = (P - PM[:3, 3]) @ PM[:3, :3]
    else:
        local = P
    axes = []
    for k in range(3):
        axes.append(bool(m.use_axis[k]) and (bool((local[:, k] > -1e-6).all()) or bool((local[:, k] < 1e-6).all())))
    if not any(axes):
        return ''
    mm = ob.modifiers.get('MCH Muscle Mirror') or ob.modifiers.new('MCH Muscle Mirror', 'MIRROR')
    mm.use_axis = axes
    mm.mirror_object = piv
    mm.use_clip = False
    return ' - mirrored as its body (' + ''.join(a for a, on in zip('XYZ', axes) if on) + ')'


def _collection(context):
    coll = bpy.data.collections.get(COLLECTION)
    if coll is None:
        coll = bpy.data.collections.new(COLLECTION)
    if coll.name not in context.scene.collection.children:
        context.scene.collection.children.link(coll)
    return coll


LIVE = ('preset', 'style', 'strands', 'twist', 'spread', 'thickness', 'width', 'volume', 'length', 'belly', 'tendon',
        'segments', 'sink', 'fibers', 'fiber_scale', 'smooth', 'resolution', 'remesh', 'color', 'tendon_color', 'core',
        'core_count', 'core_size', 'core_color', 'holes', 'hole_size', 'hole_cells', 'sleeve_thick', 'sleeve_color',
        'cap', 'cap_size', 'cap_length', 'cap_color', 'cable_radius')


def make(context, tool, pts):
    """A muscle from the clicked points ``pts`` [(object name, world point, world normal)] with the tool's settings."""
    st = settings(context, tool)
    body = bpy.data.objects.get(pts[0][0])
    if body is None:
        raise RuntimeError('Click on a mesh')
    inv = body.matrix_world.inverted()
    R = inv.to_3x3()
    others = sorted({n for n, _p, _q in pts[1:] if n != body.name})
    local = [list(inv @ Vector(p)) for _n, p, _q in pts]
    nloc = [list((R @ Vector(q)).normalized()) for _n, _p, q in pts]
    me = bpy.data.meshes.new(PRESET[st.preset][1])
    ob = bpy.data.objects.new(PRESET[st.preset][1], me)
    _collection(context).objects.link(ob)
    ob.parent = body
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob[KEY] = json.dumps({'pts': local, 'nrm': nloc, 'body': body.name, 'others': others, 'tool': tool})
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(ob.mch_muscle, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    n = build(ob, context)
    note = follow_mirror(ob, body)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob, f'{ob.name} on "{body.name}" ({n:,} faces){note} - its sliders lay it again; Enter: keep'


def make_membrane(context, pts):
    """0.24.183 (user: "내가 만들어 놓은 메쉬에 점점점 찍으면 우리 드래곤 클로스처럼 메쉬가 생기면 좋을 듯") a
    membrane between the points clicked over the mesh (Creature Cloth's, from its outline on the meshes)."""
    from . import creature_membrane as cm
    if len(pts) < 3:
        raise RuntimeError('Click at least 3 points')
    ring, pin, owner = [], [], []
    for k in range(len(pts)):
        n1, p1, q1 = pts[k]
        n2, p2, q2 = pts[(k + 1) % len(pts)]
        a, b = np.array(p1), np.array(p2)
        steps = 8
        for s in range(steps):
            f = s / steps
            ring.append(tuple(a + (b - a) * f))
            pin.append(s == 0)
            owner.append(n1 if s == 0 else '')
    rv3d = getattr(context, 'region_data', None)
    view = tuple(rv3d.view_rotation @ Vector((0.0, 0.0, -1.0))) if rv3d is not None else (0.0, 0.0, -1.0)
    return cm.perform_ring(context, ring, pin, owner, view)


# ---- the skin ----------------------------------------------------------------------------------------------------------

def skin_tree(name, bodies, coll):
    """One skin's node group: the bodies and every muscle (the Muscles collection) as one volume, its surface smoothed
    (Tension) and grown (Fat)."""
    from .creature_fur import _B, _socket
    ng = bpy.data.node_groups.get(name) or bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    _socket(ng, 'Geometry', 'GEOMETRY')
    for nm, kind, default in (('Voxel', 'FLOAT', 0.01), ('Adaptivity', 'FLOAT', 0.2), ('Tension', 'INT', 4),
                              ('Fat', 'FLOAT', 0.0), ('Material', 'MATERIAL', None)):
        _socket(ng, nm, kind, default)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    b = _B(ng)
    gi = b.node('NodeGroupInput')
    go = b.node('NodeGroupOutput')
    I = gi.outputs
    join = b.node('GeometryNodeJoinGeometry')
    for o in bodies:
        oi = b.node('GeometryNodeObjectInfo', transform_space='RELATIVE')
        oi.inputs['Object'].default_value = o
        b.feed(join.inputs[0], oi.outputs['Geometry'])
    ci = b.node('GeometryNodeCollectionInfo', transform_space='RELATIVE')
    ci.inputs['Collection'].default_value = coll
    real = b.node('GeometryNodeRealizeInstances')
    b.feed(real.inputs['Geometry'], ci.outputs['Instances'])
    b.feed(join.inputs[0], real.outputs['Geometry'])
    m2v = b.node('GeometryNodeMeshToVolume')
    b.feed(m2v.inputs['Mesh'], join.outputs['Geometry'])
    try:
        m2v.inputs['Resolution Mode'].default_value = 'Size'
    except (TypeError, ValueError):
        pass
    b.feed(m2v.inputs['Voxel Size'], I['Voxel'])
    v2m = b.node('GeometryNodeVolumeToMesh')
    b.feed(v2m.inputs['Volume'], m2v.outputs['Volume'])
    try:
        v2m.inputs['Resolution Mode'].default_value = 'Size'
    except (TypeError, ValueError):
        pass
    b.feed(v2m.inputs['Voxel Size'], I['Voxel'])
    v2m.inputs['Threshold'].default_value = 0.3
    b.feed(v2m.inputs['Adaptivity'], I['Adaptivity'])
    P = b.node('GeometryNodeInputPosition').outputs['Position']
    bl = b.node('GeometryNodeBlurAttribute', data_type='FLOAT_VECTOR')
    b.feed(bl.inputs['Value'], P)
    b.feed(bl.inputs['Iterations'], I['Tension'])
    sp = b.node('GeometryNodeSetPosition')
    b.feed(sp.inputs['Geometry'], v2m.outputs['Mesh'])
    b.feed(sp.inputs['Position'], bl.outputs['Value'])
    sp2 = b.node('GeometryNodeSetPosition')
    b.feed(sp2.inputs['Geometry'], sp.outputs['Geometry'])
    b.feed(sp2.inputs['Offset'], b.vec('SCALE', b.node('GeometryNodeInputNormal').outputs['Normal'], scale=I['Fat']))
    sm = b.node('GeometryNodeSetShadeSmooth')
    b.feed(sm.inputs['Mesh'], sp2.outputs['Geometry'])
    mt = b.node('GeometryNodeSetMaterial')
    b.feed(mt.inputs['Geometry'], sm.outputs['Mesh'])
    b.feed(mt.inputs['Material'], I['Material'])
    b.feed(go.inputs[0], mt.outputs['Geometry'])
    return ng


def make_skin(context, look='CREATURE'):
    """A skin over the bodies the muscles are on (and the selected meshes) and every muscle: its own mesh."""
    coll = bpy.data.collections.get(COLLECTION)
    bodies = []
    if coll is not None:
        for o in coll.objects:
            if is_muscle(o):
                bd = bpy.data.objects.get(data(o).get('body', ''))
                if bd is not None and bd not in bodies:
                    bodies.append(bd)
    for o in context.selected_objects:
        if o.type == 'MESH' and not is_muscle(o) and not is_skin(o) and o not in bodies:
            bodies.append(o)
    if not bodies and coll is None:
        raise RuntimeError('Make some muscles first (or select the bodies)')
    me = bpy.data.meshes.new('Skin')
    ob = bpy.data.objects.new('Skin' if look == 'CREATURE' else 'Mecha Skin', me)
    context.scene.collection.objects.link(ob)
    ob[SKIN_KEY] = json.dumps({'bodies': [o.name for o in bodies], 'look': look})
    size = 1.0
    for o in bodies:
        size = max(size if bodies.index(o) else 0.0, max(o.dimensions))
    ob.mch_mskin.look = look
    mod = ob.modifiers.new(SKIN_MOD, 'NODES')
    mod.node_group = skin_tree('MCH Skin ' + ob.name, bodies, coll or _collection(context))
    mat = bpy.data.materials.new('MCH Skin' if look == 'CREATURE' else 'MCH Mecha Skin')
    mat.use_nodes = True
    _principled(mat, (0.55, 0.4, 0.33) if look == 'CREATURE' else (0.12, 0.13, 0.14),
                0.5 if look == 'CREATURE' else 0.35, 0.0 if look == 'CREATURE' else 0.3,
                sss=0.2 if look == 'CREATURE' else 0.0)
    me.materials.append(mat)
    ob['mch_mskin_size'] = float(size)
    push_skin(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def push_skin(ob):
    from . import geo_sculpt as gs
    mod = ob.modifiers.get(SKIN_MOD)
    if mod is None:
        return
    p = ob.mch_mskin
    size = float(ob.get('mch_mskin_size', 1.0) or 1.0)
    vals = {'Voxel': size / max(int(p.detail), 16), 'Adaptivity': float(p.adaptivity), 'Tension': int(p.tension),
            'Fat': float(p.fat) * size, 'Material': ob.data.materials[0] if ob.data.materials else None}
    for k, v in vals.items():
        try:
            gs.set_input(mod, k, v)
        except (KeyError, AttributeError, TypeError):
            pass
    ob.update_tag()


def _upd_skin(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_skin(ob):
        push_skin(ob)


class MCH_PG_MuscleSkin(bpy.types.PropertyGroup):
    look: EnumProperty(name='Look', items=(('CREATURE', 'Creature', ''), ('MECHA', 'Mecha', '')), default='CREATURE')
    detail: IntProperty(name='Detail', default=140, min=24, soft_max=400, max=1000, update=_upd_skin,
                        description='Points across the whole body (more: finer, heavier)')
    adaptivity: FloatProperty(name='Lightness', default=0.2, min=0.0, max=1.0, update=_upd_skin,
                              description='Fewer faces where it is flat (0: even everywhere)')
    tension: IntProperty(name='Tension', default=4, min=0, max=40, update=_upd_skin,
                         description='How tight the skin is: higher - smoother over the muscles, the valleys filled')
    fat: FloatProperty(name='Fat', default=0.0, min=-0.05, max=0.1, precision=4, update=_upd_skin,
                       description='A layer under the skin (a share of the body\'s size)')


# ---- settings ----------------------------------------------------------------------------------------------------------

def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_muscle(ob):
        try:
            build(ob, context)
        except RuntimeError as ex:
            print('Muscle:', ex)


def _upd_preset(self, context):
    if _BUSY[0]:
        return
    vals = PRESET[self.preset][4]
    _BUSY[0] = True
    try:
        for k, v in vals.items():
            setattr(self, k, v)
    finally:
        _BUSY[0] = False
    _upd(self, context)


class MCH_PG_Muscle(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Muscle', items=PRESET_ITEMS, default='SPINDLE', update=_upd_preset)
    style: EnumProperty(name='Look', items=STYLES, default='CREATURE', update=_upd)
    strands: IntProperty(name='Strands', default=1, min=1, max=12, update=_upd,
                         description='How many bellies (2: a double muscle; the chest: the bands twisting into the arm)')
    twist: FloatProperty(name='Twist', default=0.0, min=0.0, max=1.0, update=_upd,
                         description='The strands cross on their way (1: they end in the other order - the chest)')
    spread: FloatProperty(name='Spread', default=1.0, min=0.2, max=3.0, update=_upd,
                          description='How far apart the strands are')
    thickness: FloatProperty(name='Thickness', default=1.0, min=0.1, soft_max=3.0, max=6.0, update=_upd,
                             description='How high it stands off the bone')
    width: FloatProperty(name='Width', default=1.0, min=0.1, soft_max=3.0, max=6.0, update=_upd)
    volume: FloatProperty(name='Volume', default=1.0, min=0.1, soft_max=3.0, max=6.0, update=_upd,
                          description='Bigger all round (thickness and width)')
    length: FloatProperty(name='Length', default=1.0, min=0.4, max=1.6, update=_upd,
                          description='Longer or shorter than between the points (round its middle)')
    belly: FloatProperty(name='Belly At', default=0.5, min=0.1, max=0.9, update=_upd,
                         description='Where it is thickest (0: near where it starts)')
    tendon: FloatProperty(name='Tendon', default=0.15, min=0.0, max=0.45, update=_upd,
                          description='How long the thin tendons at its ends are')
    segments: IntProperty(name='Segments', default=0, min=0, max=8, update=_upd,
                          description='Grooves across it (the abs: 4)')
    sink: FloatProperty(name='Sink', default=0.35, min=0.0, max=1.0, update=_upd,
                        description='How far into the bone it sits')
    fibers: FloatProperty(name='Fibres', default=0.5, min=0.0, max=2.0, update=_upd,
                          description='The fibres along it (in its material: a bump, no extra points)')
    remesh: BoolProperty(name='Merge Strands', default=False, update=_upd,
                         description='The strands merged into one mesh (a volume - heavier); off: each a clean tube')
    fiber_scale: FloatProperty(name='Fibre Size', default=40.0, min=4.0, max=200.0, update=_upd,
                               description='More, finer fibres (higher)')
    smooth: IntProperty(name='Smooth', default=2, min=0, max=12, update=_upd)
    resolution: IntProperty(name='Detail', default=48, min=16, soft_max=200, max=400, update=_upd,
                            description='Points along its length (more: finer, heavier)')
    color: FloatVectorProperty(name='Muscle', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.42, 0.07, 0.06),
                               update=_upd)
    tendon_color: FloatVectorProperty(name='Tendon', subtype='COLOR', size=3, min=0.0, max=1.0,
                                      default=(0.82, 0.76, 0.66), update=_upd)
    # mecha
    core: EnumProperty(name='Core', items=CORES, default='BUNDLE', update=_upd)
    core_count: IntProperty(name='Fibres / Rings', default=6, min=2, max=24, update=_upd)
    core_size: FloatProperty(name='Core Size', default=0.78, min=0.2, max=1.0, update=_upd)
    core_color: FloatVectorProperty(name='Core', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.08, 0.08, 0.09),
                                    update=_upd)
    holes: EnumProperty(name='Sleeve', items=HOLES, default='SQUARE', update=_upd)
    hole_size: FloatProperty(name='Hole Size', default=0.6, min=0.1, max=0.92, update=_upd)
    hole_cells: IntProperty(name='Holes Round', default=10, min=4, max=64, update=_upd,
                            description='How many holes round the sleeve (smaller holes: more)')
    sleeve_thick: FloatProperty(name='Sleeve Thickness', default=0.08, min=0.01, max=0.4, update=_upd)
    sleeve_color: FloatVectorProperty(name='Sleeve', subtype='COLOR', size=3, min=0.0, max=1.0,
                                      default=(0.55, 0.56, 0.5), update=_upd)
    cap: EnumProperty(name='End Cap', items=CAPS, default='COLLAR', update=_upd)
    cap_size: FloatProperty(name='Cap Size', default=1.3, min=0.6, max=3.0, update=_upd)
    cap_length: FloatProperty(name='Cap Length', default=0.08, min=0.02, max=0.3, update=_upd,
                              description='The end caps (and the bare ends) - a share of its length')
    cap_color: FloatVectorProperty(name='Caps', subtype='COLOR', size=3, min=0.0, max=1.0, default=(0.6, 0.58, 0.52),
                                   update=_upd)
    cable_radius: FloatProperty(name='Cable Thickness', default=0.2, min=0.05, max=1.0, update=_upd)


# ---- the clicks ------------------------------------------------------------------------------------------------------------

def roles(context, tool):
    st = settings(context, tool)
    return PRESET[st.preset][2]


def _status(context, tool):
    r = roles(context, tool)
    n = len(PENDING['pts'])
    try:
        if r is None:
            context.area.header_text_set(f'Membrane: click points over the mesh ({n}) | Enter: make it (3+) | '
                                         f'Backspace: back | Esc: cancel')
        elif n < len(r):
            context.area.header_text_set(f'{PRESET[settings(context, tool).preset][1]}: click {n + 1} of {len(r)} - '
                                         f'{r[n]} | Backspace: back | Esc: cancel')
        else:
            context.area.header_text_set(None)
    except (AttributeError, ReferenceError):
        pass


def _hit(context, xy):
    from bpy_extras import view3d_utils
    region, rv3d = context.region, context.region_data
    o = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy).normalized()
    dg = context.evaluated_depsgraph_get()
    for _k in range(32):
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, o, d)
        if not hit or ob is None:
            return None
        real = bpy.data.objects.get(ob.name) or ob
        if real.type == 'MESH' and not is_muscle(real) and not is_skin(real):
            return real.name, tuple(loc), tuple(nrm)
        o = Vector(loc) + d * 1e-4
    return None


class MCH_OT_muscle_click(bpy.types.Operator):
    """Click a point of the muscle on your mesh (the window says which); the last one makes it"""
    bl_idname = 'mch.muscle_click'
    bl_label = 'Muscle Point'
    bl_options = {'REGISTER', 'UNDO'}
    tool: StringProperty(default='MUSCLE', options={'SKIP_SAVE'})

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D' or context.mode != 'OBJECT':
            return {'PASS_THROUGH'}
        got = _hit(context, (event.mouse_region_x, event.mouse_region_y))
        if got is None:
            return {'PASS_THROUGH'}
        return self.add(context, got)

    def add(self, context, got):
        if PENDING['tool'] != self.tool:
            PENDING.update(tool=self.tool, pts=[])
        PENDING['pts'].append(got)
        r = roles(context, self.tool)
        if r is not None and len(PENDING['pts']) >= len(r):
            pts = list(PENDING['pts'])
            PENDING['pts'] = []
            try:
                _ob, msg = make(context, self.tool, pts)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            self.report({'INFO'}, msg)
        _status(context, self.tool)
        _redraw(context)
        return {'FINISHED'}


class MCH_OT_muscle_back(bpy.types.Operator):
    """The last point clicked off"""
    bl_idname = 'mch.muscle_back'
    bl_label = 'Muscle: Last Point Off'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='MUSCLE', options={'SKIP_SAVE'})

    def execute(self, context):
        if PENDING['pts']:
            PENDING['pts'].pop()
            _status(context, self.tool)
            _redraw(context)
            return {'FINISHED'}
        return {'PASS_THROUGH'}


class MCH_OT_muscle_finish(bpy.types.Operator):
    """Enter: the membrane from the points clicked (3 or more); else keep the selected muscle (Apply)"""
    bl_idname = 'mch.muscle_finish'
    bl_label = 'Muscle: Enter'
    bl_options = {'REGISTER', 'UNDO'}
    tool: StringProperty(default='MUSCLE', options={'SKIP_SAVE'})

    def execute(self, context):
        r = roles(context, self.tool)
        if r is None and len(PENDING['pts']) >= 3:
            pts = list(PENDING['pts'])
            PENDING['pts'] = []
            try:
                msg = make_membrane(context, pts)
            except RuntimeError as ex:
                self.report({'WARNING'}, str(ex))
                return {'CANCELLED'}
            _status(context, self.tool)
            _redraw(context)
            self.report({'INFO'}, msg or 'Membrane made')
            return {'FINISHED'}
        try:
            return bpy.ops.mch.enter_apply('INVOKE_DEFAULT')
        except (RuntimeError, AttributeError):
            return {'CANCELLED'}


class MCH_OT_muscle_esc(bpy.types.Operator):
    """Esc: the points clicked off (none: leave the tool)"""
    bl_idname = 'mch.muscle_esc'
    bl_label = 'Muscle: Cancel'
    bl_options = {'INTERNAL'}
    tool: StringProperty(default='MUSCLE', options={'SKIP_SAVE'})

    def execute(self, context):
        if PENDING['pts']:
            PENDING['pts'] = []
            _status(context, self.tool)
            _redraw(context)
            return {'FINISHED'}
        try:
            return bpy.ops.mch.exit_tool('INVOKE_DEFAULT')
        except (RuntimeError, AttributeError):
            return {'CANCELLED'}


def _redraw(context):
    try:
        for a in context.screen.areas:
            if a.type == 'VIEW_3D':
                a.tag_redraw()
    except (AttributeError, ReferenceError):
        pass


def draw_points():
    """The points clicked (numbered, joined) - and what the next one is."""
    if not PENDING['pts']:
        return
    try:
        from bpy_extras import view3d_utils
        from . import ui_gpu as ug
        region, rv3d = bpy.context.region, bpy.context.region_data
        if region is None or rv3d is None:
            return
        P = []
        for _n, p, _q in PENDING['pts']:
            c = view3d_utils.location_3d_to_region_2d(region, rv3d, Vector(p))
            if c is not None:
                P.append((c.x, c.y))
        if len(P) > 1:
            ug.polyline(P, (1.0, 0.75, 0.3, 0.9), 2.0)
        for k, (x, y) in enumerate(P):
            ug.polyline(ug.circle_pts(x, y, 7.0, n=20), (1.0, 0.8, 0.3, 1.0), 2.5, closed=True)
            ug.text(x + 10, y + 10, str(k + 1), 13, (1.0, 0.9, 0.6, 1.0))
    except (ReferenceError, AttributeError, RuntimeError, ImportError):
        pass


# ---- presets of your own (mecha: the core, the caps, the whole) ----------------------------------------------------------

KEYS_ALL = tuple(k for k in LIVE if k not in {'preset'})


class MCH_OT_muscle_my_save(bpy.types.Operator):
    """Save these values as one of your presets (there in every .blend)"""
    bl_idname = 'mch.muscle_my_save'
    bl_label = 'Save Muscle Preset'
    bl_options = {'REGISTER', 'INTERNAL'}
    kind: StringProperty(default=MY_ALL)
    tool: StringProperty(default='MMUSCLE')
    name: StringProperty(name='Name', default='My Preset')

    def invoke(self, context, event):
        self.name = {MY_CORE: 'My Core', MY_CAP: 'My Cap'}.get(self.kind, 'My Muscle')
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        from . import my_presets as mp
        ob = active_muscle(context)
        pg = ob.mch_muscle if ob is not None else settings(context, self.tool)
        keys = {MY_CORE: CORE_KEYS, MY_CAP: CAP_KEYS}.get(self.kind, KEYS_ALL)
        mp.save(self.kind, self.name.strip() or 'My Preset', pg, keys)
        self.report({'INFO'}, f'Preset "{self.name}" saved')
        return {'FINISHED'}


class MCH_OT_muscle_my_apply(bpy.types.Operator):
    """Use one of your presets (the selected muscle and the next ones)"""
    bl_idname = 'mch.muscle_my_apply'
    bl_label = 'Muscle Preset'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    kind: StringProperty(default=MY_ALL)
    tool: StringProperty(default='MMUSCLE')
    name: StringProperty(default='')

    def execute(self, context):
        from . import my_presets as mp
        vals = mp.load_all().get(self.kind, {}).get(self.name)
        if not vals:
            return {'CANCELLED'}
        ob = active_muscle(context)
        targets = [settings(context, self.tool)] + ([ob.mch_muscle] if ob is not None else [])
        for pg in targets:
            _BUSY[0] = True
            try:
                for k, v in vals.items():
                    if hasattr(pg, k):
                        try:
                            setattr(pg, k, tuple(v) if isinstance(v, list) else v)
                        except (TypeError, ValueError):
                            pass
            finally:
                _BUSY[0] = False
        if ob is not None:
            build(ob, context)
        return {'FINISHED'}


class MCH_OT_muscle_my_delete(bpy.types.Operator):
    """Delete one of your presets"""
    bl_idname = 'mch.muscle_my_delete'
    bl_label = 'Delete Muscle Preset'
    bl_options = {'REGISTER', 'INTERNAL'}
    kind: StringProperty(default=MY_ALL)
    name: StringProperty(default='')

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event, title=f'Delete the preset "{self.name}"?',
                                                     confirm_text='Delete')

    def execute(self, context):
        from . import my_presets as mp
        mp.delete(self.kind, self.name)
        return {'FINISHED'}


class MCH_OT_muscle_set(bpy.types.Operator):
    """Pick this (the selected muscle too)"""
    bl_idname = 'mch.muscle_set'
    bl_label = 'Muscle Setting'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    tool: StringProperty(default='MUSCLE')
    prop: StringProperty(default='preset')
    value: StringProperty(default='')

    def execute(self, context):
        ob = active_muscle(context)
        st = settings(context, self.tool)
        if self.prop == 'preset' and PENDING['pts']:
            PENDING['pts'] = []                   # (another muscle: its own points)
        setattr(st, self.prop, self.value)
        if ob is not None and not (self.prop == 'preset' and
                                   PRESET[self.value][3] != PRESET[ob.mch_muscle.preset][3]):
            setattr(ob.mch_muscle, self.prop, self.value)
        _status(context, self.tool)
        return {'FINISHED'}


class MCH_OT_muscle_apply(bpy.types.Operator):
    """Keep the selected muscles / skins as they are (plain meshes)"""
    bl_idname = 'mch.muscle_apply'
    bl_label = 'Apply Muscle'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(is_muscle(o) or is_skin(o) for o in context.selected_objects)

    def execute(self, context):
        dg = context.evaluated_depsgraph_get()
        done = []
        for ob in [o for o in context.selected_objects if is_muscle(o) or is_skin(o)]:
            me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
            old = ob.data
            ob.modifiers.clear()
            ob.data = me
            me.name = old.name
            if old.users == 0:
                bpy.data.meshes.remove(old)
            for k in (KEY, SKIN_KEY):
                if k in ob.keys():
                    del ob[k]
            ob[DONE] = 1
            done.append(ob.name)
        self.report({'INFO'}, 'Kept: ' + ', '.join(done))
        return {'FINISHED'}


class MCH_OT_muscle_skin(bpy.types.Operator):
    """A skin over the bones and every muscle - a mesh of its own (the muscles stay as they are under it)"""
    bl_idname = 'mch.muscle_skin'
    bl_label = 'Skin Over Muscles'
    bl_options = {'REGISTER', 'UNDO'}
    look: StringProperty(default='CREATURE')

    def execute(self, context):
        try:
            ob = make_skin(context, self.look)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: over {", ".join(json.loads(ob[SKIN_KEY])["bodies"]) or "the muscles"} and '
                              f'every muscle - Tension, Fat, Detail in the window')
        return {'FINISHED'}


# ---- the window --------------------------------------------------------------------------------------------------------

def draw(layout, context, tool='MUSCLE'):
    st = settings(context, tool)
    ob = active_muscle(context)
    skin = getattr(context, 'active_object', None)
    pg = ob.mch_muscle if ob is not None else st
    col = layout.column(align=True)
    col.label(text=f'{ob.name} (live)' if ob is not None else 'The next muscle: pick it, click its points')
    if tool == 'MMUSCLE':
        r = layout.row(align=True)
        for sid, label, _d in STYLES[1:]:
            o = r.operator('mch.muscle_set', text=label, depress=pg.style == sid)
            o.tool, o.prop, o.value = tool, 'style', sid
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, rl, kind, _v in PRESETS:
        if tool == 'MMUSCLE' and kind == 'SHEET':
            continue
        o = g.operator('mch.muscle_set', text=label, depress=pg.preset == pid)
        o.tool, o.prop, o.value = tool, 'preset', pid
    rl = PRESET[st.preset][2]
    box = layout.box()
    n = len(PENDING['pts']) if PENDING['tool'] == tool else 0
    if rl is None:
        box.label(text=f'Click points over the mesh ({n}), Enter', icon='MOUSE_LMB')
    else:
        for k, role in enumerate(rl):
            box.label(text=f'{k + 1}. {role}', icon='CHECKMARK' if k < n else ('MOUSE_LMB' if k == n else 'DOT'))
    if PRESET[pg.preset][3] == 'SHEET':
        return
    col = layout.column(align=True)
    col.label(text='Shape')
    for k in ('thickness', 'volume', 'width', 'length', 'strands', 'twist', 'spread', 'belly', 'tendon', 'segments',
              'sink'):
        col.prop(pg, k, slider=k in {'twist', 'belly', 'tendon', 'sink'})
    style = pg.style if tool == 'MMUSCLE' or ob is not None else 'CREATURE'
    if style == 'CREATURE':
        col = layout.column(align=True)
        col.label(text='Surface')
        for k in ('fibers', 'fiber_scale', 'smooth', 'resolution'):
            col.prop(pg, k)
        r = col.row(align=True)
        r.prop(pg, 'color', text='')
        r.prop(pg, 'tendon_color', text='')
    elif style == 'CABLE':
        col = layout.column(align=True)
        col.prop(pg, 'cable_radius')
        _draw_caps(layout, pg, tool)
    else:
        _draw_core(layout, pg, tool)
        col = layout.column(align=True)
        col.label(text='Sleeve')
        r = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
        for hid, label, _d in HOLES:
            o = r.operator('mch.muscle_set', text=label, depress=pg.holes == hid)
            o.tool, o.prop, o.value = tool, 'holes', hid
        if pg.holes not in {'NONE'}:
            for k in ('hole_size', 'hole_cells', 'sleeve_thick'):
                if pg.holes == 'SOLID' and k != 'sleeve_thick':
                    continue
                col.prop(pg, k)
            col.prop(pg, 'sleeve_color')
        _draw_caps(layout, pg, tool)
        _draw_my(layout, MY_ALL, 'Whole Muscle', tool)
    row = layout.row(align=True)
    o = row.operator('mch.muscle_skin', text='Skin Over All', icon='MOD_SKIN')
    o.look = 'MECHA' if tool == 'MMUSCLE' else 'CREATURE'
    if ob is not None:
        row.operator('mch.muscle_apply', text='Apply (Enter)', icon='CHECKMARK')
    if is_skin(skin):
        sb = layout.box()
        sb.label(text=f'{skin.name} (live skin)')
        for k in ('detail', 'adaptivity', 'tension', 'fat'):
            sb.prop(skin.mch_mskin, k)
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


def _draw_core(layout, pg, tool):
    col = layout.column(align=True)
    col.label(text='Inner Core')
    r = col.grid_flow(row_major=True, columns=4, even_columns=True, align=True)
    for cid, label, _d in CORES:
        o = r.operator('mch.muscle_set', text=label, depress=pg.core == cid)
        o.tool, o.prop, o.value = tool, 'core', cid
    for k in ('core_count', 'core_size', 'core_color'):
        col.prop(pg, k)
    _draw_my(layout, MY_CORE, 'Core', tool)


def _draw_caps(layout, pg, tool):
    col = layout.column(align=True)
    col.label(text='End Caps')
    r = col.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for cid, label, _d in CAPS:
        o = r.operator('mch.muscle_set', text=label, depress=pg.cap == cid)
        o.tool, o.prop, o.value = tool, 'cap', cid
    for k in ('cap_size', 'cap_length', 'cap_color'):
        col.prop(pg, k)
    _draw_my(layout, MY_CAP, 'Cap', tool)


def _draw_my(layout, kind, what, tool):
    from . import my_presets as mp
    names = mp.names(kind)
    box = layout.box()
    row = box.row(align=True)
    row.label(text=f'My {what} Presets' + ('' if names else ' (none yet)'))
    o = row.operator('mch.muscle_my_save', text='', icon='ADD')
    o.kind, o.tool = kind, tool
    if names:
        g = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for nm in names:
            o = g.operator('mch.muscle_my_apply', text=nm)
            o.kind, o.tool, o.name = kind, tool, nm
        g = box.grid_flow(row_major=True, columns=2, even_columns=True, align=True)
        for nm in names:
            o = g.operator('mch.muscle_my_delete', text='Delete ' + nm, icon='TRASH')
            o.kind, o.name = kind, nm


HELP = ('Pick a muscle, then click its points on your mesh in order',
        'The last point makes it; its sliders lay it again',
        'Backspace: the last point off;  Esc: cancel;  Enter: keep',
        'Skin Over All: one mesh over the bones and the muscles')


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return


def _keymap(tool):
    return (('mch.muscle_click', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, {'properties': [('tool', tool)]}),
            ('mch.muscle_back', {'type': 'BACK_SPACE', 'value': 'PRESS'}, {'properties': [('tool', tool)]}),
            ('mch.muscle_finish', {'type': 'RET', 'value': 'PRESS'}, {'properties': [('tool', tool)]}),
            ('mch.muscle_finish', {'type': 'NUMPAD_ENTER', 'value': 'PRESS'}, {'properties': [('tool', tool)]}),
            ('mch.muscle_esc', {'type': 'ESC', 'value': 'PRESS'}, {'properties': [('tool', tool)]}))


class MCH_TOOL_muscle(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.muscle'
    bl_label = 'Mecha Muscle Generator'
    bl_description = ('Click the points of a muscle on your mesh: it lies on it between them (two for a long one, '
                      'three for a fan).\nBackspace: back, Esc: cancel, Enter: keep')
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = _keymap('MUSCLE')

    def draw_settings(context, layout, tool):
        _tool_settings(context, layout, 'MUSCLE')


class MCH_TOOL_mecha_muscle(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.mecha_muscle'
    bl_label = 'Mecha Artificial Muscle'
    bl_description = ('Click the points of an artificial muscle (or cables) on your mesh.\nBackspace: back, Esc: '
                      'cancel, Enter: keep')
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = _keymap('MMUSCLE')

    def draw_settings(context, layout, tool):
        _tool_settings(context, layout, 'MMUSCLE')


CLASSES = (MCH_PG_Muscle, MCH_PG_MuscleSkin, MCH_OT_muscle_click, MCH_OT_muscle_back, MCH_OT_muscle_finish,
           MCH_OT_muscle_esc, MCH_OT_muscle_my_save, MCH_OT_muscle_my_apply, MCH_OT_muscle_my_delete,
           MCH_OT_muscle_set, MCH_OT_muscle_apply, MCH_OT_muscle_skin)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_muscle = PointerProperty(type=MCH_PG_Muscle)
    bpy.types.Scene.mch_mmuscle = PointerProperty(type=MCH_PG_Muscle)
    bpy.types.Object.mch_muscle = PointerProperty(type=MCH_PG_Muscle)
    bpy.types.Object.mch_mskin = PointerProperty(type=MCH_PG_MuscleSkin)
    for t in (MCH_TOOL_muscle, MCH_TOOL_mecha_muscle):
        try:
            bpy.utils.register_tool(t, separator=False, group=False)
        except (ValueError, RuntimeError, KeyError):
            pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_points, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    for t in (MCH_TOOL_muscle, MCH_TOOL_mecha_muscle):
        try:
            bpy.utils.unregister_tool(t)
        except (ValueError, RuntimeError, KeyError):
            pass
    for T, attr in ((bpy.types.Scene, 'mch_muscle'), (bpy.types.Scene, 'mch_mmuscle'), (bpy.types.Object, 'mch_muscle'),
                    (bpy.types.Object, 'mch_mskin')):
        if hasattr(T, attr):
            delattr(T, attr)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
