"""0.24.315 Joint Generator (user, six photos of mech legs / arms: "이거 보고 관절 메뉴도 만들어 줘, 관절 제네레이터야").

A joint on the 3D cursor: an upper link, the hinge, a lower link that bends round the pin (X).  Styles:
* Fork - clevis plates round a drum (the hinge's cap through them)
* Side Plates - two plates with lightening holes either side of the drum
* Tube Frame - bent tubes round the drum up to the upper link
* Ball Joint - a ball on the upper link in a socket on the lower one
* Universal - two pins square to each other (a yoke, a cross, a yoke)
The drum: its caps (Flat / Dome / Slot) and a ring of bolts.  The links: round or square bars, their lengths and
thickness.  Bend (and Side, Universal) turn the lower link - live, no rebuild; Piston: a cylinder between the links
that follows the bend.  The sliders change the selected joint."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector
from mathutils.geometry import tessellate_polygon

from . import mech_revolve as mr

TAG = 'mch_joint'
PART = 'mch_joint_part'
PARAMS = 'mch_joint_p'
_BUSY = [False]

STYLES = (('KNEE', 'Mech Knee', 'A detailed mech knee (after the user\'s photo): a khaki housing, an olive link plate, '
                                 'a drum with a slotted cap in a chamfered housing, a shin with red cartridges and a tan '
                                 'cover - bevelled edges'),
          ('FORK', 'Fork', 'Clevis plates round a drum, the drum\'s cap through them'),
          ('PLATES', 'Side Plates', 'Two plates with lightening holes either side of the drum'),
          ('TUBE', 'Tube Frame', 'Bent tubes round the drum up to the upper link'),
          ('BALL', 'Ball Joint', 'A ball on the upper link in a socket on the lower one'),
          ('UNIVERSAL', 'Universal', 'Two pins square to each other: a yoke, a cross, a yoke (Bend and Side)'))
CAPS = (('FLAT', 'Flat Cap', 'A flat cap with a boss'), ('DOME', 'Dome Cap', 'A domed cap'),
        ('SLOT', 'Slot Cap', 'A flat cap with a bar across it'))
ARMS = (('BOX', 'Square Bar', 'Square links, rounded corners'), ('ROUND', 'Round Bar', 'Round links'))
KEYS = ('style', 'size', 'width', 'upper_len', 'lower_len', 'arm_w', 'arm_d', 'arm_shape', 'cap', 'bolts', 'holes',
        'piston', 'piston_r', 'segs')


def _st(context):
    return context.scene.mch_joint


def numbers(st):
    return {k: getattr(st, k) for k in KEYS}


# --- shapes ------------------------------------------------------------------------------------------------------

def plate(bm, outline, holes, t, M, mat=0):
    """A flat plate (``t`` thick along w) of ``outline`` [(u, v)] with ``holes`` [[(u, v)]], mapped by ``M``."""
    loops = [outline] + holes
    tris = tessellate_polygon([[Vector((u, v, 0)) for u, v in lp] for lp in loops])
    flat = [p for lp in loops for p in lp]
    A = [bm.verts.new(M @ Vector((u, v, -t / 2))) for u, v in flat]
    B = [bm.verts.new(M @ Vector((u, v, t / 2))) for u, v in flat]
    for i, j, k in tris:
        try:
            bm.faces.new((A[k], A[j], A[i])).material_index = mat
            bm.faces.new((B[i], B[j], B[k])).material_index = mat
        except ValueError:
            pass
    o = 0
    for lp in loops:
        n = len(lp)
        for i in range(n):
            a, b = o + i, o + (i + 1) % n
            try:
                bm.faces.new((A[a], A[b], B[b], B[a])).material_index = mat
            except ValueError:
                pass
        o += n


def circle(cx, cy, r, n=20, rev=False):
    pts = [(cx + r * math.cos(2 * math.pi * k / n), cy + r * math.sin(2 * math.pi * k / n)) for k in range(n)]
    return pts[::-1] if rev else pts


def stadium(r0, r1, L, n=12):
    """An outline round (0, 0) (radius ``r0``) up to (0, L) (radius ``r1``) - a link plate."""
    pts = [(r0 * math.cos(a), r0 * math.sin(a)) for a in
           (math.pi + math.pi * k / n for k in range(n + 1))]                  # (round the pin, under it)
    pts += [(r1 * math.cos(a), L + r1 * math.sin(a)) for a in (math.pi * k / n for k in range(n + 1))]
    return pts


def bar(bm, p, z0, z1, mat=0, scale=1.0):
    """A link bar along Z from ``z0`` to ``z1`` (round or a rounded square), its ends chamfered."""
    w = p['arm_w'] / 2 * scale
    d = p['arm_d'] / p['arm_w'] if p['arm_w'] > 1e-9 else 1.0
    sh = 'S' if p['arm_shape'] == 'BOX' else 'R'
    lo, hi = min(z0, z1), max(z0, z1)
    ch = min(w * 0.18, (hi - lo) * 0.2)
    P = [(0.0, lo, 0.0, sh), (w - ch, lo, 0.0, sh), (w, lo + ch, 0.0, sh), (w, hi - ch, 0.0, sh), (w - ch, hi, 0.0, sh),
         (0.0, hi, 0.0, sh)]
    mr.revolve(bm, P, max(24, int(p['segs'])), sq_p=8.0, yscale=d, mat=mat)


def drum(bm, p, mat=0):
    """The hinge's drum round X at the origin, its caps out through the plates, a ring of bolts on each."""
    R = p['size'] / 2
    W = p['width'] / 2
    Rc = R * 0.62
    t = p['width'] * 0.12
    capx = W + t + R * 0.12                                   # (the caps stand out past the plates)
    segs = max(32, int(p['segs']))
    P = [(0.0, -W, 0.0, 'R'), (R * 0.94, -W, 0.0, 'R'), (R, -W + R * 0.06, 0.0, 'R'), (R, W - R * 0.06, 0.0, 'R'),
         (R * 0.94, W, 0.0, 'R'), (0.0, W, 0.0, 'R')]
    mr.revolve(bm, P, segs, matrix=mr.frame(Vector((0, 0, 0)), Vector((1, 0, 0))), mat=mat)
    for sgn in (-1, 1):
        ax = Vector((sgn, 0, 0))
        base = W - R * 0.02
        h = capx - base
        if p['cap'] == 'DOME':
            C = [(0.0, 0.0, 0.0, 'R'), (Rc, 0.0, 0.0, 'R'), (Rc, h * 0.5, 0.0, 'R')]
            for i in range(1, 7):
                a = i / 6 * math.pi / 2
                C.append((Rc * math.cos(a), h * 0.5 + h * 0.9 * math.sin(a), 0.0, 'R'))
            C[-1] = (0.0, h * 1.4, 0.0, 'R')
        else:
            C = [(0.0, 0.0, 0.0, 'R'), (Rc, 0.0, 0.0, 'R'), (Rc, h - Rc * 0.06, 0.0, 'R'), (Rc * 0.94, h, 0.0, 'R'),
                 (Rc * 0.42, h, 0.0, 'R'), (Rc * 0.42, h + Rc * 0.12, 0.0, 'R'), (0.0, h + Rc * 0.12, 0.0, 'R')]
        mr.revolve(bm, C, segs, matrix=mr.frame(ax * base, ax), mat=2)
        if p['cap'] == 'SLOT':                               # (a bar across the boss)
            M = mr.frame(ax * (base + h + Rc * 0.12), ax)
            bx, by, bz = Rc * 0.38, Rc * 0.08, Rc * 0.08
            vs = [bm.verts.new(M @ Vector((x, y, z))) for x in (-bx, bx) for y in (-by, by) for z in (0.0, bz)]
            for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
                bm.faces.new([vs[i] for i in q]).material_index = 2
        n = int(p['bolts'])
        if n and p['cap'] != 'DOME':
            hr = Rc * 0.09
            for k in range(n):
                a = 2 * math.pi * (k + 0.5) / n
                c = ax * (base + h) + Vector((0, math.cos(a), math.sin(a))) * Rc * 0.72
                mr.revolve(bm, mr.bolt_profile(hr * 0.5, 0.0, 'SOCKET', hr, hr * 0.7), 24,
                           matrix=mr.frame(c - ax * hr * 0.1, ax), mat=2)


def side_plates(bm, p, holes=0, mat=1):
    """The upper link's plates either side of the drum, the caps through their big holes."""
    R = p['size'] / 2
    W = p['width'] / 2
    Rc = R * 0.62
    t = p['width'] * 0.12
    Lp = max(p['upper_len'] * 0.55, R * 1.4)
    r0, r1 = R * 1.08, max(p['arm_d'] / 2 * 1.1, R * 0.6)
    out = stadium(r0, r1, Lp)
    hl = [circle(0.0, 0.0, Rc * 1.04, 28, rev=True)]
    if holes:
        z0, z1 = r0 + R * 0.2, Lp - r1 * 0.4
        for k in range(int(holes)):
            zc = z0 + (z1 - z0) * (k + 0.5) / holes
            half = r0 + (r1 - r0) * (zc / Lp)
            rr = min(half * 0.5, (z1 - z0) / holes * 0.36)
            if rr > R * 0.05:
                hl.append(circle(0.0, zc, rr, 16, rev=True))
    for sgn in (-1, 1):
        x = sgn * (W + t / 2 + 0.002 * p['size'])
        M = Matrix(((0, 0, 1, x), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
        plate(bm, out, hl, t, M, mat)
    return Lp, W + t


def catmull(P, n=8):
    out = []
    P = [Vector(p) for p in P]
    for i in range(len(P) - 1):
        p0, p1, p2, p3 = P[max(i - 1, 0)], P[i], P[i + 1], P[min(i + 2, len(P) - 1)]
        for k in range(n):
            t = k / n
            out.append(0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t * t
                              + (-p0 + 3 * p1 - 3 * p2 + p3) * t ** 3))
    out.append(P[-1])
    return out


def tube(bm, pts, r, mat=1, sides=12):
    from . import wire_gen as wg
    F = wg.frames(pts, (pts[-1] - pts[0]).orthogonal())
    wg.sweep(bm, pts, F, wg._round(r, sides), sides, mat)


# --- 0.24.319 the Mech Knee (user: "일단 한번 최대한 비슷하게 만들어 봐, 하나만") -----------------------------------------
# materials: 0 dark body, 1 olive plate, 2 metal, 3 red, 4 tan (khaki)

def bevelled(bm, fn, off, segs=2):
    """``fn(tmp)`` builds a part in a bmesh of its own; its sharp edges bevelled ``off``; then put into ``bm``."""
    tmp = bmesh.new()
    try:
        fn(tmp)
        bmesh.ops.recalc_face_normals(tmp, faces=list(tmp.faces))
        tmp.normal_update()                                  # (else every edge reads 0 degrees: nothing bevelled)
        if off > 0:
            edges = [e for e in tmp.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > math.radians(30)]
            if edges:
                try:
                    bmesh.ops.bevel(tmp, geom=edges, offset=off, segments=segs, profile=0.5, affect='EDGES',
                                    clamp_overlap=True)
                except (RuntimeError, ValueError, TypeError):
                    pass
        me = bpy.data.meshes.new('_mch_tmp')
        tmp.to_mesh(me)
    finally:
        tmp.free()
    bm.from_mesh(me)
    bpy.data.meshes.remove(me)


def cbox(bm, lo, hi, mat):
    """An axis-aligned box from ``lo`` to ``hi`` (world X Y Z)."""
    vs = [bm.verts.new((x, y, z)) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
    for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
        bm.faces.new([vs[i] for i in q]).material_index = mat


def xplate(bm, outline, holes, x, t, mat):
    """A plate square to X at ``x`` (``t`` thick): ``outline`` [(y, z)]."""
    M = Matrix(((0, 0, 1, x), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1)))
    plate(bm, outline, holes, t, M, mat)


def socket_bolt(bm, c, axis, r, mat=2):
    mr.revolve(bm, mr.bolt_profile(r * 0.5, 0.0, 'SOCKET', r, r * 0.7), 24, matrix=mr.frame(c, axis), mat=mat)


def knee_upper(bm, p):
    R = p['size'] / 2
    W = p['width'] / 2
    D = p['arm_d'] / 2
    Lu = max(p['upper_len'], p['size'] * 2)
    t = p['width'] * 0.14
    Lp = Lu * 0.62
    xo = W + t * 1.6                                         # (the olive plate, outside the knee housing)
    rp = R * 0.72
    out = [(rp * math.cos(a), rp * math.sin(a)) for a in (math.radians(d) for d in range(200, 341, 14))]
    out += [(R * 0.78, R * 0.25), (R * 0.62, R * 1.0), (R * 0.62, R * 1.6), (R * 0.95, R * 2.1), (R * 0.95, Lp - R * 0.25),
            (R * 0.7, Lp), (-R * 0.75, Lp), (-R * 0.95, Lp - R * 0.3), (-R * 0.95, R * 1.7), (-R * 0.7, R * 1.15),
            (-R * 0.72, R * 0.3)]
    holes = [circle(0.0, 0.0, R * 0.36, 24, rev=True), circle(0.0, R * 1.85, R * 0.16, 16, rev=True)]
    bevelled(bm, lambda b: xplate(b, out, holes, xo, t, 1), t * 0.25)
    # (its pivot boss mid-way: a ring and a bolt)
    mr.revolve(bm, [(R * 0.17, 0.0, 0.0, 'R'), (R * 0.3, 0.0, 0.0, 'R'), (R * 0.3, t * 0.9, 0.0, 'R'),
                    (R * 0.17, t * 0.9, 0.0, 'R')], 28, matrix=mr.frame(Vector((xo + t / 2, 0, R * 1.85)), AXX), mat=2)
    socket_bolt(bm, Vector((xo + t / 2 + t * 0.3, 0, R * 1.85)), AXX, R * 0.12)
    for z in (Lp * 0.55, Lp * 0.8):                           # (bolt heads down the plate)
        socket_bolt(bm, Vector((xo + t / 2, R * 0.55, z)), AXX, R * 0.07)
    # (the other side: a plain dark plate)
    out2 = [(rp * math.cos(a), rp * math.sin(a)) for a in (math.radians(d) for d in range(200, 341, 14))]
    out2 += [(R * 0.78, R * 0.3), (R * 0.8, Lp), (-R * 0.8, Lp), (-R * 0.78, R * 0.3)]
    bevelled(bm, lambda b: xplate(b, out2, [circle(0.0, 0.0, R * 0.36, 24, rev=True)], -xo, t, 0), t * 0.25)
    # (the khaki housing on top: an angled block - its front cut back at the bottom - a dark rail under it, bolts at its
    #  side corners, a groove across its front)
    zb = Lp - R * 0.15
    xb = xo + t * 0.9
    H = Lu - zb
    D1 = D * 1.6
    prof = [(-D1 * 0.55, zb), (D1, zb), (D1, Lu - H * 0.1), (D1 * 0.85, Lu), (-D1 * 0.8, Lu), (-D1, Lu - H * 0.15),
            (-D1, zb + H * 0.45)]
    bevelled(bm, lambda b: xplate(b, prof, [], 0.0, 2 * xb, 4), R * 0.06, 3)
    bevelled(bm, lambda b: cbox(b, (-(xo + t * 0.4), -D1 * 0.6, zb - R * 0.12), (xo + t * 0.4, D1 * 0.9, zb + R * 0.02), 0),
             R * 0.03)
    for sgn in (-1, 1):
        for (yy, zz) in ((D1 * 0.7, Lu - H * 0.18), (-D1 * 0.55, Lu - H * 0.22), (D1 * 0.7, zb + H * 0.2)):
            socket_bolt(bm, Vector((sgn * xb, yy, zz)), Vector((sgn, 0, 0)), R * 0.075)
    bevelled(bm, lambda b: cbox(b, (-xb * 0.92, -D1 * 1.02, zb + H * 0.52), (xb * 0.92, -D1 * 0.9, zb + H * 0.58), 0),
             R * 0.01, 1)
    # (a dark round actuator on the housing's side, its axle along X)
    mr.revolve(bm, [(0.0, 0.0, 0.0, 'R'), (R * 0.42, 0.0, 0.0, 'R'), (R * 0.45, R * 0.05, 0.0, 'R'), (R * 0.45, t * 2.2, 0.0, 'R'),
                    (R * 0.25, t * 2.4, 0.0, 'R'), (R * 0.25, t * 2.9, 0.0, 'R'), (0.0, t * 2.9, 0.0, 'R')], 36,
               matrix=mr.frame(Vector((xo + t * 0.9, D * 0.2, zb - R * 0.55)), AXX), mat=0)
    # (an inner spine joining the plates, under the housing)
    bevelled(bm, lambda b: cbox(b, (-xo, -D * 0.7, R * 1.2), (xo, D * 0.7, zb), 0), R * 0.05)


def knee_lower(bm, p):
    R = p['size'] / 2
    W = p['width'] / 2
    D = p['arm_d'] / 2
    Ll = max(p['lower_len'], p['size'] * 2)
    t = p['width'] * 0.14
    segs = max(48, int(p['segs']))
    # (the drum: a thick rim, a recessed disc, a slotted screw cap - on both sides)
    mr.revolve(bm, [(0.0, -W, 0.0, 'R'), (R * 0.95, -W, 0.0, 'R'), (R, -W + R * 0.05, 0.0, 'R'), (R, W - R * 0.05, 0.0, 'R'),
                    (R * 0.95, W, 0.0, 'R'), (0.0, W, 0.0, 'R')], segs, matrix=mr.frame(Vector(), AXX), mat=0)
    for sgn in (-1, 1):
        ax = Vector((sgn, 0, 0))
        base = W - R * 0.02
        h = t * 2.6 + R * 0.1
        C = [(0.0, 0.0, 0.0, 'R'), (R * 0.92, 0.0, 0.0, 'R'), (R * 0.92, h - R * 0.06, 0.0, 'R'), (R * 0.86, h, 0.0, 'R'),
             (R * 0.66, h, 0.0, 'R'), (R * 0.62, h - R * 0.08, 0.0, 'R'), (R * 0.42, h - R * 0.08, 0.0, 'R'),
             (R * 0.4, h + R * 0.02, 0.0, 'R'), (0.0, h + R * 0.02, 0.0, 'R')]
        mr.revolve(bm, C, segs, matrix=mr.frame(ax * base, ax), mat=0)
        M = mr.frame(ax * (base + h + R * 0.02), ax)           # (the slot across the cap: a bar)
        vs = [bm.verts.new(M @ Vector((x, y, z))) for x in (-R * 0.3, R * 0.3) for y in (-R * 0.045, R * 0.045)
              for z in (0.0, R * 0.05)]
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in q]).material_index = 2
        for k in range(3):                                    # (three lugs round the rim)
            a = math.radians(30 + 120 * k)
            c = ax * (base + h * 0.5) + Vector((0, math.cos(a), math.sin(a))) * R * 0.97
            mr.revolve(bm, [(0.0, -h * 0.4, 0.0, 'R'), (R * 0.1, -h * 0.4, 0.0, 'R'), (R * 0.1, h * 0.4, 0.0, 'R'),
                            (0.0, h * 0.4, 0.0, 'R')], 12, matrix=mr.frame(c, ax), mat=0)
    # (the knee housing: a chamfered plate each side round the drum, open for its cap, bolts at its corners)
    hr = R * 1.22
    out = [(hr * 0.55, hr), (hr, hr * 0.5), (hr, -hr * 0.3), (R * 0.85, -R * 1.75), (-R * 0.85, -R * 1.75),
           (-hr, -hr * 0.3), (-hr, hr * 0.35), (-hr * 0.6, hr)]
    for sgn in (-1, 1):
        x = sgn * (W + t * 0.5)
        bevelled(bm, lambda b, x=x: xplate(b, out, [circle(0.0, 0.0, R * 0.94, 40, rev=True)], x, t, 0), t * 0.3)
        for (yy, zz) in ((hr * 0.75, hr * 0.55), (-hr * 0.75, hr * 0.6), (hr * 0.78, -hr * 0.25), (-hr * 0.78, -hr * 0.25)):
            socket_bolt(bm, Vector((x + sgn * t / 2, yy, zz)), Vector((sgn, 0, 0)), R * 0.07)
    # (the front cover over the drum's lower front)
    bevelled(bm, lambda b: cbox(b, (-W - t, -hr * 0.95, -R * 1.7), (W + t, -R * 0.55, -R * 0.75), 0), R * 0.06)
    # (the shin: a chamfered housing, two red cartridges in front, their caps, a tan cover on the side, a collar)
    zs0, zs1 = -R * 1.6, -Ll * 0.42
    bevelled(bm, lambda b: cbox(b, (-W * 1.05, -D * 1.1, zs1), (W * 1.05, D * 1.1, zs0), 0), R * 0.08, 3)
    zc0, zc1 = -Ll * 0.4, -Ll * 0.8
    for xx in (-W * 0.52, W * 0.52):
        bevelled(bm, lambda b, xx=xx: cbox(b, (xx - W * 0.42, -D * 1.6, zc1), (xx + W * 0.42, -D * 0.4, zc0), 3), R * 0.04)
        bevelled(bm, lambda b, xx=xx: cbox(b, (xx - W * 0.3, -D * 1.75, zc0 - R * 0.35), (xx + W * 0.3, -D * 1.45,
                                                                                         zc0 - R * 0.05), 3), R * 0.03)
        bevelled(bm, lambda b, xx=xx: cbox(b, (xx - W * 0.36, -D * 1.55, zc0 - R * 0.02), (xx + W * 0.36, -D * 0.5,
                                                                                         zc0 + R * 0.18), 3), R * 0.04)
        for zz in (zc1 + (zc0 - zc1) * 0.25, zc1 + (zc0 - zc1) * 0.55):      # (ribs across each)
            bevelled(bm, lambda b, xx=xx, zz=zz: cbox(b, (xx - W * 0.44, -D * 1.66, zz - R * 0.03),
                                                     (xx + W * 0.44, -D * 0.45, zz + R * 0.03), 0), R * 0.01, 1)
    bevelled(bm, lambda b: cbox(b, (-W * 0.12, -D * 1.4, zc1), (W * 0.12, D * 0.6, zc0), 0), R * 0.03)   # (between)
    tc = [(D * 1.4, -R * 1.5), (D * 1.5, -Ll * 0.55), (D * 0.9, -Ll * 0.86), (-D * 0.6, -Ll * 0.86), (-D * 1.0, -Ll * 0.7),
          (-D * 0.7, -Ll * 0.45), (-D * 0.2, -R * 1.5)]
    bevelled(bm, lambda b: xplate(b, tc, [], W * 1.05 + t * 0.6, t * 1.1, 4), t * 0.3)
    bevelled(bm, lambda b: cbox(b, (-W * 0.95, -D * 1.0, zc1 - R * 0.05), (W * 0.95, D * 1.0, -Ll * 0.85), 0), R * 0.05)
    bevelled(bm, lambda b: cbox(b, (-W * 1.1, -D * 1.25, -Ll * 0.92), (W * 1.1, D * 1.25, -Ll * 0.85), 4), R * 0.04, 3)
    bevelled(bm, lambda b: cbox(b, (-W * 0.8, -D * 0.9, -Ll), (W * 0.8, D * 0.9, -Ll * 0.92), 0), R * 0.04)


AXX = Vector((1, 0, 0))


# --- the parts -----------------------------------------------------------------------------------------------------

def build_upper(me, p):
    bm = bmesh.new()
    try:
        R = p['size'] / 2
        st = p['style']
        Lu = max(p['upper_len'], p['size'])
        if st == 'KNEE':
            knee_upper(bm, p)
        elif st in {'FORK', 'PLATES'}:
            Lp, half = side_plates(bm, p, holes=int(p['holes']) if st == 'PLATES' else 0)
            z0 = Lp - max(p['arm_d'] / 2, R * 0.6) * 0.9
            M = Matrix.Identity(4)
            bx = half + p['width'] * 0.02                    # (a block joining the plates under the bar)
            box_ = [(-bx, -p['arm_d'] / 2 * 1.05, z0), (bx, p['arm_d'] / 2 * 1.05, z0 + p['size'] * 0.35)]
            vs = [bm.verts.new(M @ Vector((x, y, z))) for x in (box_[0][0], box_[1][0]) for y in (box_[0][1], box_[1][1])
                  for z in (box_[0][2], box_[1][2])]
            for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
                bm.faces.new([vs[i] for i in q]).material_index = 1
            bar(bm, p, z0 + p['size'] * 0.3, Lu, mat=0)
        elif st == 'TUBE':
            W = p['width'] / 2
            tr = max(p['size'] * 0.06, 1e-4)
            Lp = max(Lu * 0.6, R * 1.6)
            for sgn in (-1, 1):
                x = sgn * (W + tr * 1.6)
                ring = [Vector((x, R * 1.05 * math.cos(a), R * 1.05 * math.sin(a)))
                        for a in (2 * math.pi * k / 24 for k in range(25))]
                tube(bm, ring, tr)                           # (a ring round the drum)
                for yy in (-1, 1):                           # (two legs from it up to the bar)
                    pts = catmull([(x, yy * R * 1.05 * 0.7, R * 1.05 * 0.7), (x, yy * R * 1.0, R * 1.6),
                                   (x * 0.8, yy * p['arm_d'] * 0.45, Lp)], 8)
                    tube(bm, pts, tr)
            tube(bm, [Vector((-(W + tr * 1.6), 0, Lp)), Vector((W + tr * 1.6, 0, Lp))], tr * 1.1)   # (a crossbar)
            bar(bm, p, Lp - p['size'] * 0.1, Lu, mat=0)
            mr.revolve(bm, [(0.0, -(W + tr * 3.2), 0.0, 'R'), (R * 0.3, -(W + tr * 3.2), 0.0, 'R'),
                            (R * 0.3, W + tr * 3.2, 0.0, 'R'), (0.0, W + tr * 3.2, 0.0, 'R')], 24,
                       matrix=mr.frame(Vector(), Vector((1, 0, 0))), mat=2)   # (the pin through the rings)
        elif st == 'BALL':
            Rb = R * 0.8
            P = [(0.0, -Rb, 0.0, 'R')]
            for i in range(1, 16):
                a = -math.pi / 2 + math.pi * i / 16
                P.append((Rb * math.cos(a), Rb * math.sin(a), 0.0, 'R'))
            P += [(p['arm_w'] * 0.32, Rb * 1.5, 0.0, 'R'), (0.0, Rb * 1.5, 0.0, 'R')]
            mr.revolve(bm, P, max(32, int(p['segs'])), mat=2)
            bar(bm, p, Rb * 1.3, Lu, mat=0)
        elif st == 'UNIVERSAL':
            yoke(bm, p, up=True)
            bar(bm, p, p['size'] / 2 * 1.4, Lu, mat=0)            # (from the yoke's block)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def yoke(bm, p, up=True, axis='X'):
    """A yoke: two tabs round a pin (X, or Y turned), a block joining them."""
    from .actuator_gen import tab, box
    R = p['size'] / 2
    W = p['width'] / 2
    t = p['width'] * 0.16
    s = 1 if up else -1
    for sgn in (-1, 1):
        if axis == 'X':
            M = Matrix(((0, 0, 1, sgn * (W + t / 2)), (1, 0, 0, 0), (0, s, 0, 0), (0, 0, 0, 1)))
        else:
            M = Matrix(((1, 0, 0, 0), (0, 0, 1, sgn * (W + t / 2)), (0, s, 0, 0), (0, 0, 0, 1)))
        tab(bm, R * 1.2, R * 1.1, t, R * 0.25, 28, M, mat=1)
    if axis == 'X':
        Mb = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, s, 0, 0), (0, 0, 0, 1)))
    else:
        Mb = Matrix(((1, 0, 0, 0), (0, 0, 1, 0), (0, s, 0, 0), (0, 0, 0, 1)))
    box(bm, (-R * 0.6, R * 1.1 - t, -(W + t)), (R * 0.6, R * 1.1 + R * 0.4, W + t), Mb, mat=1)


def build_lower(me, p):
    """The lower link (its origin on the pin): the drum (or socket / yoke) and the bar down."""
    bm = bmesh.new()
    try:
        R = p['size'] / 2
        st = p['style']
        Ll = max(p['lower_len'], p['size'])
        if st == 'KNEE':
            knee_lower(bm, p)
        elif st in {'FORK', 'PLATES', 'TUBE'}:
            drum(bm, p, mat=0)
            from .actuator_gen import box
            bx = p['width'] / 2 * 0.96                         # (a neck under the drum to the bar)
            box(bm, (-p['arm_d'] / 2, -R * 1.25, -bx), (p['arm_d'] / 2, -R * 0.5, bx),
                Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, 1, 0, 0), (0, 0, 0, 1))), mat=0)
            bar(bm, p, -R * 1.15, -Ll, mat=0)
        elif st == 'BALL':
            Rb = R * 0.8
            Rs = Rb * 1.18
            P = []
            for i in range(0, 11):                          # (a cup round the ball, open upward)
                a = -math.pi / 2 + (math.pi / 2 + math.radians(25)) * i / 10
                P.append((Rs * math.cos(a), Rs * math.sin(a), 0.0, 'R'))
            a = math.radians(25)
            P += [(Rb * 1.02 * math.cos(a), Rb * 1.02 * math.sin(a), 0.0, 'R')]
            for i in range(1, 11):
                a2 = math.radians(25) - (math.pi / 2 + math.radians(25)) * i / 10
                P.append((Rb * 1.02 * math.cos(a2), Rb * 1.02 * math.sin(a2), 0.0, 'R'))
            P[-1] = (0.0, -Rb * 1.02, 0.0, 'R')
            mr.revolve(bm, P, max(32, int(p['segs'])), mat=1)
            n = int(p['bolts'])
            for k in range(n):                              # (a bolt ring round the cup's rim)
                ang = 2 * math.pi * k / max(n, 1)
                c = Vector((Rs * 1.0 * math.cos(ang), Rs * 1.0 * math.sin(ang), Rs * 0.2))
                mr.revolve(bm, mr.bolt_profile(Rs * 0.04, 0.0, 'SOCKET', Rs * 0.08, Rs * 0.06), 24,
                           matrix=mr.frame(c, c.normalized()), mat=2)
            bar(bm, p, -Rs * 0.9, -Ll, mat=0)
        elif st == 'UNIVERSAL':
            yoke(bm, p, up=False, axis='Y')
            bar(bm, p, -p['size'] / 2 * 1.4, -Ll, mat=0)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def build_cross(me, p):
    """Universal: the cross between the yokes (a block, four trunnions)."""
    bm = bmesh.new()
    try:
        R = p['size'] / 2
        W = p['width'] / 2
        c = R * 0.45
        from .actuator_gen import box
        box(bm, (-c, -c, -c), (c, c, c), Matrix.Identity(4), mat=2)
        for ax in (Vector((1, 0, 0)), Vector((-1, 0, 0)), Vector((0, 1, 0)), Vector((0, -1, 0))):
            z0 = c * 0.5                                    # (from inside the block: no shared centre point)
            mr.revolve(bm, [(0.0, z0, 0.0, 'R'), (R * 0.22, z0, 0.0, 'R'), (R * 0.22, W + p['width'] * 0.18, 0.0, 'R'),
                            (0.0, W + p['width'] * 0.18, 0.0, 'R')], 20, matrix=mr.frame(Vector(), ax), mat=2)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def piston_meshes(me_a, me_b, p, length):
    """The piston: a barrel (from its eye at 0 down -Z) and a rod (from its eye down -Z) - they overlap at any bend."""
    pr = max(p['piston_r'], 1e-4)
    for me, (r, L) in ((me_a, (pr, length * 0.62)), (me_b, (pr * 0.45, length * 0.7))):
        bm = bmesh.new()
        try:
            P = [(0.0, -L, 0.0, 'R'), (r, -L, 0.0, 'R'), (r, -r * 1.6, 0.0, 'R'), (r * 0.6, -r * 1.2, 0.0, 'R'),
                 (r * 0.6, 0.0, 0.0, 'R'), (0.0, 0.0, 0.0, 'R')]
            mr.revolve(bm, P, 24, mat=2 if me is me_b else 0)
            mr.revolve(bm, [(0.0, -pr * 0.8, 0.0, 'R'), (pr * 0.9, -pr * 0.8, 0.0, 'R'), (pr * 0.9, pr * 0.8, 0.0, 'R'),
                            (0.0, pr * 0.8, 0.0, 'R')], 24, matrix=mr.frame(Vector(), Vector((1, 0, 0))), mat=2)
            mr.finish(bm)
            bm.to_mesh(me)
        finally:
            bm.free()
        me.update()


# --- the objects ----------------------------------------------------------------------------------------------------

def joint_of(ob):
    return ob.get(TAG, '') if ob is not None else ''


def parts_of(scene, jid):
    return {o.get(PART, ''): o for o in scene.objects if joint_of(o) == jid}


def _obj(context, old, part, jid, coll, kind='MESH'):
    ob = old.get(part)
    if ob is None:
        nm = f'MCH_{jid}_{part.title()}'
        ob = bpy.data.objects.new(nm, bpy.data.meshes.new(nm) if kind == 'MESH' else None)
        coll.objects.link(ob)
    ob[TAG], ob[PART] = jid, part
    return ob


def _drop(ob):
    if ob is None:
        return
    me = ob.data if ob.type == 'MESH' else None
    bpy.data.objects.remove(ob)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def _mats(me):
    if len(me.materials):
        return
    for name, col, metal, rough in (('MCH Joint Body', (0.32, 0.34, 0.3), 0.1, 0.5),
                                     ('MCH Joint Plate', (0.36, 0.42, 0.22), 0.1, 0.45),
                                     ('MCH Joint Metal', (0.55, 0.56, 0.58), 0.9, 0.3),
                                     ('MCH Joint Red', (0.55, 0.08, 0.05), 0.1, 0.45),
                                     ('MCH Joint Tan', (0.52, 0.45, 0.32), 0.1, 0.55)):
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            b = m.node_tree.nodes.get('Principled BSDF')
            if b is not None:
                b.inputs['Base Color'].default_value = (*col, 1.0)
                b.inputs['Metallic'].default_value = metal
                b.inputs['Roughness'].default_value = rough
            m.diffuse_color = (*col, 1.0)
        me.materials.append(m)


def build(context, p, jid=None):
    scene = context.scene
    old = parts_of(scene, jid) if jid else {}
    if not jid:
        k = 1
        names = {joint_of(o) for o in scene.objects}
        while f'Joint{k}' in names:
            k += 1
        jid = f'Joint{k}'
    up0 = old.get('UPPER')
    coll = up0.users_collection[0] if up0 is not None and up0.users_collection else context.collection
    upper = _obj(context, old, 'UPPER', jid, coll)
    if up0 is None:
        upper.matrix_world = Matrix.Translation(scene.cursor.location)
    lower = _obj(context, old, 'LOWER', jid, coll)
    for ob, fn in ((upper, build_upper), (lower, build_lower)):
        if ob.mode != 'EDIT':
            if ob.data.users > 1:
                ob.data = ob.data.copy()
            fn(ob.data, p)
            _mats(ob.data)
    bend = float(upper.get('mch_joint_bend', 0.0))
    side = float(upper.get('mch_joint_side', 0.0))
    if p['style'] == 'UNIVERSAL':
        cross = _obj(context, old, 'CROSS', jid, coll)
        build_cross(cross.data, p)
        _mats(cross.data)
        cross.parent = upper
        cross.matrix_parent_inverse = Matrix.Identity(4)
        lower.parent = cross
    else:
        _drop(old.get('CROSS'))
        lower.parent = upper
    lower.matrix_parent_inverse = Matrix.Identity(4)
    out = {'UPPER': upper, 'LOWER': lower}
    if p['style'] == 'UNIVERSAL':
        out['CROSS'] = parts_of(scene, jid)['CROSS']
    upper[PARAMS] = json.dumps(p)
    set_bend(scene, jid, bend, side)
    set_piston(context, p, jid, old, coll, out)
    return jid, parts_of(scene, jid)


def set_bend(scene, jid, bend, side=0.0):
    """Bend (degrees, round the pin X) and Side (Universal: round Y) - the lower link turned, no rebuild."""
    parts = parts_of(scene, jid)
    upper, lower, cross = parts.get('UPPER'), parts.get('LOWER'), parts.get('CROSS')
    if upper is None or lower is None:
        return
    upper['mch_joint_bend'], upper['mch_joint_side'] = float(bend), float(side)
    if cross is not None:
        cross.matrix_basis = Matrix.Rotation(math.radians(bend), 4, 'X')
        lower.matrix_basis = Matrix.Rotation(math.radians(side), 4, 'Y')
    else:
        lower.matrix_basis = Matrix.Rotation(math.radians(bend), 4, 'X')


def set_piston(context, p, jid, old, coll, out):
    """A piston between the links in front (+Y): a barrel on the upper one tracking the rod's eye, a rod on the lower
    one tracking the barrel's - it follows any bend."""
    names = ('PISTON_A', 'PISTON_B', 'PIN_A', 'PIN_B')
    if not p['piston'] or p['style'] == 'UNIVERSAL':
        for n in names:
            _drop(old.get(n))
        return
    upper, lower = out['UPPER'], out['LOWER']
    off = p['arm_d'] / 2 + p['piston_r'] * 1.4
    za, zb = max(p['upper_len'], p['size']) * 0.6, -max(p['lower_len'], p['size']) * 0.6
    a = _obj(context, old, 'PISTON_A', jid, coll)
    b = _obj(context, old, 'PISTON_B', jid, coll)
    ea = _obj(context, old, 'PIN_A', jid, coll, kind='EMPTY')
    eb = _obj(context, old, 'PIN_B', jid, coll, kind='EMPTY')
    length = abs(za - zb)
    piston_meshes(a.data, b.data, p, length)
    for me in (a.data, b.data):
        _mats(me)
    for ob, par, z in ((a, upper, za), (ea, upper, za), (b, lower, zb), (eb, lower, zb)):
        ob.parent = par
        ob.matrix_parent_inverse = Matrix.Identity(4)
        ob.matrix_basis = Matrix.Translation((0.0, off, z))
    for e in (ea, eb):
        e.empty_display_size = p['piston_r']
        try:
            e.hide_set(True)
        except RuntimeError:
            pass
    for ob, tgt in ((a, eb), (b, ea)):
        c = ob.constraints.get('MCH Piston') or ob.constraints.new('DAMPED_TRACK')
        c.name = 'MCH Piston'
        c.target = tgt
        c.track_axis = 'TRACK_NEGATIVE_Z'


def selected_joints(context):
    out = []
    for o in context.selected_objects:
        j = joint_of(o)
        if j and j not in out:
            out.append(j)
    return out


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for j in selected_joints(context):
        build(context, p, j)


def _bend_update(self, context):
    if _BUSY[0]:
        return
    for j in selected_joints(context):
        set_bend(context.scene, j, self.bend, self.side)


class MCH_PG_Joint(bpy.types.PropertyGroup):
    style: bpy.props.EnumProperty(name='Style', items=STYLES, default='FORK', update=_update)
    size: bpy.props.FloatProperty(name='Joint Size', default=0.5, min=0.005, soft_max=5.0, unit='LENGTH',
                                  update=_update, description='The drum (the hinge) across')
    width: bpy.props.FloatProperty(name='Joint Width', default=0.36, min=0.005, soft_max=5.0, unit='LENGTH',
                                   update=_update, description='The drum\'s width along the pin')
    upper_len: bpy.props.FloatProperty(name='Upper Length', default=1.2, min=0.01, soft_max=10.0, unit='LENGTH',
                                       update=_update)
    lower_len: bpy.props.FloatProperty(name='Lower Length', default=1.2, min=0.01, soft_max=10.0, unit='LENGTH',
                                       update=_update)
    arm_w: bpy.props.FloatProperty(name='Link Width', default=0.3, min=0.005, soft_max=3.0, unit='LENGTH',
                                   update=_update, description='The link bars across (X)')
    arm_d: bpy.props.FloatProperty(name='Link Depth', default=0.26, min=0.005, soft_max=3.0, unit='LENGTH',
                                   update=_update, description='The link bars front to back (Y)')
    arm_shape: bpy.props.EnumProperty(name='Links', items=ARMS, default='BOX', update=_update)
    cap: bpy.props.EnumProperty(name='Cap', items=CAPS, default='SLOT', update=_update)
    bolts: bpy.props.IntProperty(name='Cap Bolts', default=6, min=0, max=24, update=_update,
                                 description='Bolts round each cap (Ball Joint: round the cup)')
    holes: bpy.props.IntProperty(name='Holes', default=3, min=0, max=8, update=_update,
                                 description='Side Plates: lightening holes in each plate')
    piston: bpy.props.BoolProperty(name='Piston', default=False, update=_update,
                                   description='A cylinder between the links in front (it follows the bend)')
    piston_r: bpy.props.FloatProperty(name='Piston Size', default=0.06, min=0.002, soft_max=1.0, unit='LENGTH',
                                      update=_update)
    segs: bpy.props.IntProperty(name='Segments', default=48, min=12, max=256, update=_update)
    bend: bpy.props.FloatProperty(name='Bend', default=30.0, min=-170.0, max=170.0, update=_bend_update,
                                  description='The lower link turned round the pin (degrees) - live')
    my_name: bpy.props.StringProperty(name='Name', default='My Joint',
                                      description='The name to save the selected joint under')
    side: bpy.props.FloatProperty(name='Side', default=0.0, min=-90.0, max=90.0, update=_bend_update,
                                  description='Universal: the lower link turned the other way (degrees)')


class MCH_OT_joint_add(bpy.types.Operator):
    """A joint (an upper link, the hinge, a lower link) on the 3D cursor - its sliders change it while selected"""
    bl_idname = 'mch.joint_add'
    bl_label = 'Summon Joint'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Joint: Object Mode only')
            return {'CANCELLED'}
        st = _st(context)
        jid, parts = build(context, numbers(st))
        set_bend(context.scene, jid, st.bend, st.side)
        for o in context.selected_objects:
            o.select_set(False)
        for o in parts.values():
            if o.type == 'MESH':
                o.select_set(True)
        context.view_layer.objects.active = parts['UPPER']
        self.report({'INFO'}, f'{jid}: the sliders change it while selected')
        return {'FINISHED'}


class MCH_OT_joint_plain(bpy.types.Operator):
    """Keep the selected joints as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.joint_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        js = selected_joints(context)
        for j in js:
            for o in parts_of(context.scene, j).values():
                for k in (TAG, PART, PARAMS):
                    if k in o.keys():
                        del o[k]
        return {'FINISHED'} if js else {'CANCELLED'}


# --- 0.24.316 My Joints (user: "관절은 그냥 내가 만들게, 내가 프리셋 만든 거나 저장해서 불러올 수 있게 해 줘") ------------

DIR = [None]                    # (a test points it elsewhere: never the user's own folder)
PIVOT = 'mch_myjoint_pivot'     # on saved objects: the point that goes to the 3D cursor when loaded


def my_dir(create=False):
    import os
    if DIR[0]:
        d = DIR[0]
    else:
        d = os.path.join(bpy.utils.user_resource('CONFIG', path='mecha_lab', create=create), 'my_joints')
    if create:
        os.makedirs(d, exist_ok=True)
    return d


def my_joints():
    """The saved joints' names (their .blend files in the My Joints folder), sorted."""
    import os
    d = my_dir()
    try:
        return sorted(f[:-6] for f in os.listdir(d) if f.endswith('.blend'))
    except OSError:
        return []


def _safe(name):
    import re
    name = re.sub(r'[^\w.\-]+', '_', name.strip(), flags=re.UNICODE).strip('._')
    return name[:60] or 'Joint'


def save_joint(context, name, objs, pivot):
    """``objs`` (the joint you made) written to My Joints as ``name`` (their meshes, materials, parents among them,
    constraints kept); ``pivot`` (world) - where it sits on the 3D cursor when loaded."""
    import os
    objs = [o for o in objs if o is not None]
    if not objs:
        return None
    path = os.path.join(my_dir(create=True), _safe(name) + '.blend')
    for o in objs:
        o[PIVOT] = list(pivot)
    try:
        bpy.data.libraries.write(path, set(objs), fake_user=False, compress=True)
    finally:
        for o in objs:
            if PIVOT in o.keys():
                del o[PIVOT]
    return path


def load_joint(context, name, where=None):
    """A saved joint brought in (new copies, in the active collection), its pivot on ``where`` (the 3D cursor)."""
    import os
    path = os.path.join(my_dir(), _safe(name) + '.blend')
    if not os.path.isfile(path):
        return []
    with bpy.data.libraries.load(path, link=False) as (src, dst):
        dst.objects = list(src.objects)
    obs = [o for o in dst.objects if o is not None]
    coll = context.collection
    where = Vector(where if where is not None else context.scene.cursor.location)
    pivot = None
    for o in obs:
        if PIVOT in o.keys():
            pivot = Vector(o[PIVOT])
            del o[PIVOT]
    delta = where - (pivot if pivot is not None else Vector())
    names = {o.name for o in obs}
    for o in obs:
        if o.name not in coll.objects:
            coll.objects.link(o)
    for o in obs:
        if o.parent is None:                             # (just loaded: its own location, not a stale world matrix)
            o.location = o.location + delta
        elif o.parent.name not in names:
            o.parent = None
            o.location = o.location + delta
    return obs


class MCH_OT_joint_save(bpy.types.Operator):
    """Save the selected objects (the joint you made) to My Joints - the active one's origin is its pivot"""
    bl_idname = 'mch.joint_save'
    bl_label = 'Save Selected as Joint'
    bl_options = {'REGISTER'}

    def execute(self, context):
        objs = list(context.selected_objects)
        if not objs:
            self.report({'WARNING'}, 'My Joints: select the joint\'s parts first')
            return {'CANCELLED'}
        name = _st(context).my_name.strip() or (context.active_object.name if context.active_object else 'Joint')
        act = context.active_object if context.active_object in objs else objs[0]
        path = save_joint(context, name, objs, act.matrix_world.translation.copy())
        self.report({'INFO'}, f'My Joints: "{_safe(name)}" saved ({len(objs)} objects)')
        return {'FINISHED'} if path else {'CANCELLED'}


class MCH_OT_joint_load(bpy.types.Operator):
    """Bring this saved joint in on the 3D cursor"""
    bl_idname = 'mch.joint_load'
    bl_label = 'Load Joint'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'My Joints: Object Mode only')
            return {'CANCELLED'}
        obs = load_joint(context, self.name)
        if not obs:
            self.report({'WARNING'}, f'My Joints: "{self.name}" not found')
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in obs:
            try:
                o.select_set(True)
            except RuntimeError:
                pass
        context.view_layer.objects.active = obs[0]
        return {'FINISHED'}


class MCH_OT_joint_delete(bpy.types.Operator):
    """Delete this saved joint from My Joints"""
    bl_idname = 'mch.joint_delete'
    bl_label = 'Delete Saved Joint'
    bl_options = {'REGISTER'}
    name: bpy.props.StringProperty()

    def invoke(self, context, event):
        return context.window_manager.invoke_confirm(self, event)

    def execute(self, context):
        import os
        path = os.path.join(my_dir(), _safe(self.name) + '.blend')
        try:
            os.remove(path)
        except OSError:
            return {'CANCELLED'}
        return {'FINISHED'}


def draw_my(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='My Joints')
    r = box.row(align=True)
    r.prop(st, 'my_name', text='')
    r.operator('mch.joint_save', text='Save Selected', icon='ADD')
    names = my_joints()
    if not names:
        box.label(text='Make a joint, select its parts, Save Selected', icon='INFO')
    col = box.column(align=True)
    for nm in names:
        r = col.row(align=True)
        r.operator('mch.joint_load', text=nm, icon='IMPORT').name = nm
        r.operator('mch.joint_delete', text='', icon='X').name = nm


def draw(layout, context):
    draw_my(layout, context)
    st = _st(context)
    box = layout.box()
    box.label(text='Joint Generator')
    box.prop(st, 'style', text='')
    c = box.column(align=True)
    for k in ('size', 'width'):
        c.prop(st, k)
    c = box.column(align=True)
    c.label(text='Links')
    c.row(align=True).prop(st, 'arm_shape', expand=True)
    for k in ('upper_len', 'lower_len', 'arm_w', 'arm_d'):
        c.prop(st, k)
    c = box.column(align=True)
    if st.style in {'FORK', 'PLATES', 'TUBE'}:
        c.row(align=True).prop(st, 'cap', expand=True)
    if st.style != 'UNIVERSAL' and st.style != 'TUBE':
        c.prop(st, 'bolts')
    if st.style == 'PLATES':
        c.prop(st, 'holes')
    c = box.column(align=True)
    c.prop(st, 'bend', slider=True)
    if st.style == 'UNIVERSAL':
        c.prop(st, 'side', slider=True)
    if st.style != 'UNIVERSAL':
        r = box.row(align=True)
        r.prop(st, 'piston')
        sub = r.row(align=True)
        sub.active = st.piston
        sub.prop(st, 'piston_r', text='Size')
    box.prop(st, 'segs')
    box.operator('mch.joint_add', icon='CON_PIVOT')
    n = len(selected_joints(context))
    if n:
        box.label(text=f'{n} joint(s) selected: live', icon='INFO')
        box.operator('mch.joint_plain', icon='CHECKMARK')
    else:
        box.label(text='Select a joint: the sliders change it', icon='INFO')


class MCH_TOOL_joint(bpy.types.WorkSpaceTool):
    """0.24.315 Joint Generator"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.joint_gen'
    bl_label = 'Joint Generator'
    bl_description = ('Summon a joint (Fork / Side Plates / Tube Frame / Ball Joint / Universal) on the 3D cursor - '
                      'select it and the sliders change it; Bend turns it live')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('view3d.select', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('toggle', True)]}))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Joint, MCH_OT_joint_add, MCH_OT_joint_plain, MCH_OT_joint_save, MCH_OT_joint_load,
           MCH_OT_joint_delete)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_joint = bpy.props.PointerProperty(type=MCH_PG_Joint)
    try:
        bpy.utils.register_tool(MCH_TOOL_joint, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_joint)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_joint
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
