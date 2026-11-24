"""0.24.313 Wire Harness (user: "점 두 개 찍으면 생기는 전선도 만들어 주라, 바리에이션 해서 넓은 전선이랑 얇은 거 한 개, 얇은 거
여러 개, 두꺼운 거에 얇은 거 붙어 있는 거, 와이어 뭉쳐 있는 전선 ... 길이 늘릴 수 있고, z 축으로 아래로 살짝 흘러내리는
그래비티 슬라이더랑 트위스트 슬라이더, 좌우 앞옆으로 휠 수 있는 슬라이더").

Click a surface, then another: a wire between them, leaving each surface square to it.  Styles: Flat Ribbon, Single
Wire, Thin Wires (several, twisting round each other), Thick + Thin (thin wires along a thick one), Wire Loom (many
thin wires tied together with bands).  Length (more: it hangs), Gravity (down along -Z), Twist, Bend Left / Right,
Bend Front / Back, Wires, Thickness, Main Thickness, Ties, End Plugs, Loose (each wire its own way a little).
The sliders change the selected wires; a wire remembers where it was clicked on its meshes (they move: it follows
when a slider changes).  The existing Cable tool is unchanged."""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

TAG = 'mch_wire'                # on a wire: its numbers (JSON)
ENDS = 'mch_wire_ends'          # on a wire: its two ends (in their meshes' space)
_BUSY = [False]
PENDING = {'a': None}

STYLES = (('RIBBON', 'Flat Ribbon', 'A wide flat cable (its wires side by side)'),
          ('SINGLE', 'Single Wire', 'One round wire'),
          ('THIN', 'Thin Wires', 'Several thin wires twisting round each other'),
          ('MAIN', 'Thick + Thin', 'Thin wires running along a thick one'),
          ('LOOM', 'Wire Loom', 'Many thin wires bundled, tied with bands'))
MATS = (('MCH Wire Rubber', (0.03, 0.03, 0.035), 0.0, 0.55), ('MCH Wire Red', (0.55, 0.05, 0.04), 0.0, 0.4),
        ('MCH Wire Metal', (0.6, 0.6, 0.62), 1.0, 0.3), ('MCH Wire Blue', (0.04, 0.12, 0.5), 0.0, 0.4),
        ('MCH Wire Yellow', (0.75, 0.55, 0.05), 0.0, 0.4))


def _st(context):
    return context.scene.mch_wire


KEYS = ('style', 'count', 'thick', 'main_thick', 'length', 'gravity', 'twist', 'bend_lr', 'bend_fb', 'ties', 'plugs',
        'loose', 'seed', 'sides', 'segments', 'end_style')


def numbers(st):
    return {k: (getattr(st, k) if not isinstance(getattr(st, k), float) else float(getattr(st, k))) for k in KEYS}


# --- the path -----------------------------------------------------------------------------------------------------

def centerline(a, na, b, nb, p, n=None):
    """The wire's middle from ``a`` to ``b`` (leaving each along its normal): [Vector] evenly spaced."""
    a, b, na, nb = Vector(a), Vector(b), Vector(na).normalized(), Vector(nb).normalized()
    D = max((b - a).length, 1e-6)
    f = (b - a) / D
    up = Vector((0, 0, 1))
    side = f.cross(up)
    if side.length < 1e-6:
        side = f.cross(Vector((1, 0, 0)))
    side.normalize()
    front = side.cross(f).normalized()
    h = D * 0.28
    P0, P1, P2, P3 = a, a + na * h, b + nb * h, b
    extra = max(float(p['length']) - 1.0, 0.0)
    sag = D * 0.5 * float(p['gravity']) + math.sqrt(max(3.0 * D * D * extra / 8.0, 0.0))
    m = max(int(p['segments']), 8)
    raw = []
    K = m * 4
    for i in range(K + 1):
        t = i / K
        u = 1 - t
        q = P0 * u ** 3 + P1 * 3 * u * u * t + P2 * 3 * u * t * t + P3 * t ** 3
        env = math.sin(math.pi * t)
        q = q + Vector((0, 0, -1)) * sag * env ** 1.3
        q = q + side * float(p['bend_lr']) * D * 0.5 * env + front * float(p['bend_fb']) * D * 0.5 * env
        raw.append(q)
    seg = [0.0]
    for i in range(1, len(raw)):
        seg.append(seg[-1] + (raw[i] - raw[i - 1]).length)
    L = seg[-1]
    out = []
    n = n or m
    j = 0
    for i in range(n + 1):
        s = L * i / n
        while j < len(seg) - 2 and seg[j + 1] < s:
            j += 1
        k = (s - seg[j]) / max(seg[j + 1] - seg[j], 1e-12)
        out.append(raw[j].lerp(raw[j + 1], min(max(k, 0.0), 1.0)))
    return out, L


def frames(P, n0):
    """Parallel-transported (tangent, normal, binormal) along ``P``, the first normal from ``n0``."""
    T = []
    for i in range(len(P)):
        d = P[min(i + 1, len(P) - 1)] - P[max(i - 1, 0)]
        T.append(d.normalized() if d.length > 1e-12 else Vector((0, 0, 1)))
    n = Vector(n0) - T[0] * Vector(n0).dot(T[0])
    if n.length < 1e-6:
        n = T[0].orthogonal()
    n.normalize()
    out = []
    for i, t in enumerate(T):
        if i:
            r = T[i - 1].rotation_difference(t)
            n = (r @ n)
            n = (n - t * n.dot(t)).normalized()
        out.append((t, n, t.cross(n).normalized()))
    return out


# --- the strands --------------------------------------------------------------------------------------------------

def sweep(bm, P, F, section, sides, mat=0, caps=True):
    """A closed tube along ``P`` (frames ``F``): ``section(i, k)`` -> (x, y) of point k round station i."""
    rings = []
    for i, (c, (t, n, b)) in enumerate(zip(P, F)):
        ring = []
        for k in range(sides):
            x, y = section(i, k)
            ring.append(bm.verts.new(c + n * x + b * y))
        rings.append(ring)
    for i in range(len(rings) - 1):
        for k in range(sides):
            k2 = (k + 1) % sides
            bm.faces.new((rings[i][k], rings[i][k2], rings[i + 1][k2], rings[i + 1][k])).material_index = mat
    if caps:
        bm.faces.new(list(reversed(rings[0]))).material_index = mat
        bm.faces.new(rings[-1]).material_index = mat


def _round(r, sides):
    return lambda i, k: (r * math.cos(2 * math.pi * k / sides), r * math.sin(2 * math.pi * k / sides))


def strand_offsets(p, r):
    """[(radius from the middle, angle, wire radius, material)] of the thin wires round the middle (twisting)."""
    st = p['style']
    n = max(1, int(p['count']))
    if st == 'THIN' or st == 'LOOM':
        if n == 1:
            return [(0.0, 0.0, r, 1)]
        inner = 0 if n < 7 else max(1, n // 6)
        outer = n - inner
        out = []
        reach_in = 0.0                                  # (how far out the inner wires go)
        if inner == 1:
            out.append((0.0, 0.0, r, 3))
            reach_in = r
        elif inner > 1:
            rin = r / math.sin(math.pi / inner)
            out += [(rin, 2 * math.pi * k / inner, r, 3 + k % 2) for k in range(inner)]
            reach_in = rin + r
        ring_r = max(r / math.sin(math.pi / outer) if outer > 1 else 0.0, reach_in + r if inner else 0.0)
        mats = (1, 3, 4) if st == 'THIN' else (0, 0, 1, 0, 3)
        out += [(ring_r, 2 * math.pi * k / outer, r, mats[k % len(mats)]) for k in range(outer)]
        return out
    return []


def build_mesh(me, a, na, b, nb, p):
    rnd = random.Random(int(p['seed']))
    sides = max(6, int(p['sides']))
    r = max(float(p['thick']) / 2, 1e-5)
    a0, b0 = Vector(a), Vector(b)                   # (the surface points: the end finishes stand on them)
    fl = fit_len(p, est_bundle_r(p, r), r) * 0.85   # 0.24.314 the wire comes out of its finish's mouth
    a = a0 + Vector(na).normalized() * fl
    b = b0 + Vector(nb).normalized() * fl
    P, L = centerline(a, na, b, nb, p)
    F = frames(P, Vector(na).cross((P[-1] - P[0]).normalized()) if Vector(na).cross((P[-1] - P[0])).length > 1e-6
               else Vector(na).orthogonal())
    m = len(P) - 1
    tw = float(p['twist']) * 2 * math.pi
    st = p['style']
    bm = bmesh.new()
    try:
        bundle_r = r
        if st == 'SINGLE':
            sweep(bm, P, F, _round(r, sides), sides, 0)
        elif st == 'RIBBON':
            n = max(1, int(p['count']))
            w = n * r                                   # (half its width: the wires side by side)
            h = r * 0.75
            ns = min(max(n * 8, sides * 2), 480)

            def sec(i, k):
                th = 2 * math.pi * k / ns
                x = w * math.cos(th)
                y = h * math.sin(th)
                if abs(math.cos(th)) < 0.97:            # (a groove between each two wires, top and bottom)
                    y *= 1.0 - 0.22 * abs(math.sin(math.pi * (x + w) / (2 * r)))
                return x, y
            sweep(bm, P, F, sec, ns, 0)
            bundle_r = max(w, h)
        else:
            main_r = 0.0
            if st == 'MAIN':
                main_r = max(float(p['main_thick']) / 2, r)
                sweep(bm, P, F, _round(main_r, sides * 2), sides * 2, 0)
            offs = strand_offsets(p, r)
            if st == 'MAIN':                            # (the thin ones along it, side by side on one side)
                n = max(1, int(p['count']))
                ang = 2 * r / (main_r + r) * 1.05
                offs = [(main_r + r, (k - (n - 1) / 2) * ang, r, (1, 3, 4)[k % 3]) for k in range(n)]
            loose = float(p['loose'])
            for rad, ang0, rr, mat in offs:
                ph = rnd.uniform(0, 2 * math.pi)
                amp = loose * r * 2.0 * rnd.uniform(0.3, 1.0)
                pts = []
                for i, (c, (t, n_, b_)) in enumerate(zip(P, F)):
                    s = i / m
                    a_ = ang0 + tw * s
                    env = math.sin(math.pi * s)
                    lo = amp * env
                    off = n_ * (rad * math.cos(a_) + lo * math.cos(ph)) + b_ * (rad * math.sin(a_) + lo * math.sin(ph))
                    pts.append(c + off)
                sweep(bm, pts, frames(pts, F[0][1]), _round(rr, max(6, sides // 2 + 2)), max(6, sides // 2 + 2), mat)
                bundle_r = max(bundle_r, rad + rr)
            if st == 'LOOM' and int(p['ties']) > 0:     # (bands round the bundle)
                nt = int(p['ties'])
                for j in range(nt):
                    i0 = int(round((j + 1) / (nt + 1) * m))
                    i0 = min(max(i0, 1), m - 1)
                    rr_ = bundle_r + r * 0.35
                    span = max(1, int(round(m * r * 3.0 / max(L, 1e-6))))
                    a_, b2 = max(i0 - span, 0), min(i0 + span, m)
                    sweep(bm, P[a_:b2 + 1], F[a_:b2 + 1], _round(rr_, sides * 2), sides * 2, 2)
        a, b = a0, b0                                   # (the plugs on the surfaces)
        if p['plugs'] and st == 'RIBBON':               # (a flat ribbon: a flat rectangular plug at each end)
            n = max(1, int(p['count']))
            w, h = n * r, r * 0.75
            for (pt, nn), (t_, n_, b_) in (((Vector(a), Vector(na)), F[0]), ((Vector(b), Vector(nb)), F[-1])):
                nn = nn.normalized()
                ax = n_ - nn * n_.dot(nn)
                ax = ax.normalized() if ax.length > 1e-6 else nn.orthogonal().normalized()
                ay = nn.cross(ax).normalized()
                pl = max(h * 6, r * 4)
                hw, hh = w * 1.15 + r * 0.5, h * 2.2
                vs = [bm.verts.new(pt + ax * x + ay * y + nn * z) for z in (0.0, pl) for x in (-hw, hw)
                      for y in (-hh, hh)]
                for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
                    bm.faces.new([vs[i] for i in q]).material_index = 2
        elif p['plugs'] and p.get('end_style', 'PLUG') != 'PLUG':   # 0.24.314 the other end finishes
            for (pt, nn) in ((Vector(a), Vector(na)), (Vector(b), Vector(nb))):
                end_fitting(bm, pt, nn.normalized(), bundle_r, p.get('end_style'), sides)
        elif p['plugs']:                                # (a plug at each end, into its surface)
            for (pt, nn) in ((Vector(a), Vector(na)), (Vector(b), Vector(nb))):
                pr = bundle_r * 1.45
                pl = max(bundle_r * 1.6, r * 4)
                nn = nn.normalized()
                q = Vector((0, 0, 1)).rotation_difference(nn).to_matrix().to_4x4()
                Mx = Matrix.Translation(pt) @ q
                prof = [(0.0, 0.0), (pr, 0.0), (pr, pl * 0.35), (pr * 0.8, pl * 0.45), (pr * 0.8, pl), (0.0, pl)]
                segs = sides * 2
                rings = []
                for rad, z in prof:
                    if rad < 1e-9:
                        rings.append([bm.verts.new(Mx @ Vector((0, 0, z)))])
                    else:
                        rings.append([bm.verts.new(Mx @ Vector((rad * math.cos(2 * math.pi * k / segs),
                                                                 rad * math.sin(2 * math.pi * k / segs), z)))
                                      for k in range(segs)])
                for r0, r1 in zip(rings, rings[1:]):
                    for k in range(segs):
                        k2 = (k + 1) % segs
                        if len(r0) == 1:
                            f = bm.faces.new((r0[0], r1[k2], r1[k]))
                        elif len(r1) == 1:
                            f = bm.faces.new((r0[k], r0[k2], r1[0]))
                        else:
                            f = bm.faces.new((r0[k], r0[k2], r1[k2], r1[k]))
                        f.material_index = 2
        bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
        for f in bm.faces:
            f.smooth = True
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return L


END_STYLES = (('PLUG', 'Plug', 'A plain plug'),
              ('CLAMP', 'Hose Clamp', 'The wire\'s end over a nipple, a ribbed clamp band with its screw round it'),
              ('BOOT', 'Bellows Boot', 'A ribbed rubber boot on a metal collar'),
              ('FERRULE', 'Crimp Sleeve', 'A metal sleeve crimped on (two grooves)'),
              ('HEX', 'Hex Fitting', 'A hydraulic fitting: two hex nuts and a taper'),
              ('FLANGE', 'Flange', 'A square flange plate with four bolts'))


def est_bundle_r(p, r):
    """How thick the wire is round its middle (before it is built)."""
    st = p['style']
    if st == 'SINGLE':
        return r
    if st == 'RIBBON':
        return max(1, int(p['count'])) * r
    if st == 'MAIN':
        return max(float(p['main_thick']) / 2, r) + 2 * r
    offs = strand_offsets(p, r)
    return max([o[0] + o[2] for o in offs] + [r])


def fit_len(p, R, r):
    """How far an end finish stands out of its surface (0: none)."""
    if not p['plugs']:
        return 0.0
    style = p.get('end_style', 'PLUG')
    if p['style'] == 'RIBBON' and style == 'PLUG':
        return max(r * 0.75 * 6, r * 4)
    return {'PLUG': max(R * 1.6, r * 4), 'CLAMP': R * 3.2, 'BOOT': R * 5.5, 'FERRULE': R * 3.6, 'HEX': R * 3.25,
            'FLANGE': R * 1.65}.get(style, 0.0)


def end_fitting(bm, pt, nn, R, style, sides):
    """0.24.314 (user, two photos - a hose clamp, a ribbed boot: "케이블 양 끝에 이런 식의 마감을 할 수 있는 옵션, 다섯 개"):
    an end finish on the surface at ``pt`` going out along ``nn``; ``R`` the wire (bundle) radius.  Materials:
    0 rubber, 2 metal."""
    from . import mech_revolve as mr
    M = mr.frame(pt, nn)
    segs = max(24, sides * 3)
    R = max(R, 1e-5)
    if style == 'CLAMP':
        mr.revolve(bm, [(0.0, 0.0, 0.0, 'R'), (R * 1.55, 0.0, 0.0, 'R'), (R * 1.55, R * 0.22, 0.0, 'R'),
                        (R * 0.75, R * 0.22, 0.0, 'R'), (R * 0.75, R * 0.9, 0.0, 'R'), (0.0, R * 0.9, 0.0, 'R')],
                   segs, matrix=M, mat=2)                          # (a washer and the nipple)
        mr.revolve(bm, [(R * 0.9, R * 0.2, 0.0, 'R'), (R * 1.12, R * 0.2, 0.0, 'R'), (R * 1.12, R * 3.0, 0.0, 'R'),
                        (R * 0.9, R * 3.2, 0.0, 'R')], segs, matrix=M, mat=0)   # (the hose's end, swollen)
        z0, z1 = R * 1.1, R * 1.9
        mr.revolve(bm, [(R * 1.08, z0, 0.0, 'R'), (R * 1.25, z0, 0.0, 'C'), (R * 1.25, z1, 0.0, 'C'),
                        (R * 1.08, z1, 0.0, 'R')], 96, sq_p=24, matrix=M, mat=2)   # (the band, ribbed)
        hb = Matrix.Translation(pt) @ M.to_3x3().to_4x4()
        cx = R * 1.45
        lo, hi = (cx - R * 0.25, -R * 0.45, z0 - R * 0.05), (cx + R * 0.3, R * 0.45, z1 + R * 0.05)
        vs = [bm.verts.new(hb @ Vector((x, y, z))) for x in (lo[0], hi[0]) for y in (lo[1], hi[1]) for z in (lo[2], hi[2])]
        for q in ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3)):
            bm.faces.new([vs[i] for i in q]).material_index = 2   # (the screw's housing)
        sc = hb @ Vector((cx + R * 0.05, R * 0.45, (z0 + z1) / 2))
        mr.revolve(bm, mr.bolt_profile(R * 0.12, R * 0.6, 'HEX', R * 0.26, R * 0.18, thread=False), 36,
                   matrix=mr.frame(sc, (hb.to_3x3() @ Vector((0, 1, 0))).normalized()), mat=2)
    elif style == 'BOOT':
        P = [(0.0, 0.0, 0.0, 'R'), (R * 1.6, 0.0, 0.0, 'R'), (R * 1.6, R * 0.55, 0.0, 'R'), (R * 1.5, R * 0.6, 0.0, 'R'),
             (R * 1.5, R * 0.75, 0.0, 'R'), (R * 1.6, R * 0.8, 0.0, 'R'), (R * 1.6, R * 1.05, 0.0, 'R'),
             (0.0, R * 1.05, 0.0, 'R')]
        mr.revolve(bm, P, segs, matrix=M, mat=2)                 # (the metal collar, a groove round it)
        ribs, L = 6, R * 4.2
        P = [(R * 0.9, R * 1.0, 0.0, 'R')]
        n = ribs * 8
        for i in range(n + 1):
            t = i / n
            base = R * (1.42 - 0.34 * t)
            P.append((base + R * 0.14 * (0.5 + 0.5 * math.cos(2 * math.pi * ribs * t)), R * 1.0 + L * t, 0.0, 'R'))
        P += [(R * 1.03, R * 1.0 + L + R * 0.3, 0.0, 'R'), (R * 0.9, R * 1.0 + L + R * 0.3, 0.0, 'R')]
        mr.revolve(bm, P, segs, matrix=M, mat=0)
    elif style == 'FERRULE':
        L = R * 3.6
        P = [(0.0, 0.0, 0.0, 'R'), (R * 1.5, 0.0, 0.0, 'R'), (R * 1.5, R * 0.3, 0.0, 'R'), (R * 1.22, R * 0.38, 0.0, 'R')]
        for zc in (0.38, 0.62):                                   # (two crimps)
            z = L * zc
            P += [(R * 1.22, z - R * 0.22, 0.0, 'R'), (R * 1.1, z - R * 0.08, 0.0, 'R'), (R * 1.1, z + R * 0.08, 0.0, 'R'),
                  (R * 1.22, z + R * 0.22, 0.0, 'R')]
        P += [(R * 1.22, L - R * 0.15, 0.0, 'R'), (R * 1.08, L, 0.0, 'R'), (R * 0.9, L, 0.0, 'R'), (0.0, L, 0.0, 'R')]
        mr.revolve(bm, P, segs, matrix=M, mat=2)
    elif style == 'HEX':
        segh = 36
        P = [(0.0, 0.0, 0.0, 'R'), (R * 1.55, 0.0, 0.0, 'H'), (R * 1.75, R * 0.1, 0.0, 'H'), (R * 1.75, R * 0.85, 0.0, 'H'),
             (R * 1.5, R * 0.95, 0.0, 'R'), (R * 1.05, R * 0.95, 0.0, 'R'), (R * 1.05, R * 1.35, 0.0, 'R'),
             (R * 1.3, R * 1.4, 0.0, 'H'), (R * 1.42, R * 1.5, 0.0, 'H'), (R * 1.42, R * 2.0, 0.0, 'H'),
             (R * 1.3, R * 2.1, 0.0, 'R'), (R * 1.18, R * 2.1, 0.0, 'R'), (R * 1.05, R * 3.2, 0.0, 'R'),
             (R * 0.9, R * 3.25, 0.0, 'R'), (0.0, R * 3.25, 0.0, 'R')]
        mr.revolve(bm, P, segh, matrix=M, mat=2)
    elif style == 'FLANGE':
        B = R * 2.3
        mr.revolve(bm, [(0.0, 0.0, 0.0, 'R'), (B, 0.0, 0.0, 'S'), (B, R * 0.35, 0.0, 'S'), (0.0, R * 0.35, 0.0, 'R')],
                   64, sq_p=10.0, matrix=M, mat=2)
        mr.revolve(bm, [(0.0, R * 0.3, 0.0, 'R'), (R * 1.35, R * 0.3, 0.0, 'R'), (R * 1.35, R * 1.4, 0.0, 'R'),
                        (R * 1.1, R * 1.65, 0.0, 'R'), (0.0, R * 1.65, 0.0, 'R')], segs, matrix=M, mat=2)
        for u in (-1, 1):
            for v in (-1, 1):
                c = M @ Vector((u * B * 0.7, v * B * 0.7, R * 0.33))
                mr.revolve(bm, mr.bolt_profile(R * 0.12, 0.0, 'HEX', R * 0.3, R * 0.22), 36,
                           matrix=mr.frame(c, nn), mat=2)


def _mats(me):
    if len(me.materials):
        return
    for name, col, metal, rough in MATS:
        m = bpy.data.materials.get(name)
        if m is None:
            m = bpy.data.materials.new(name)
            m.use_nodes = True
            bsdf = m.node_tree.nodes.get('Principled BSDF')
            if bsdf is not None:
                bsdf.inputs['Base Color'].default_value = (*col, 1.0)
                bsdf.inputs['Metallic'].default_value = metal
                bsdf.inputs['Roughness'].default_value = rough
            m.diffuse_color = (*col, 1.0)
        me.materials.append(m)


# --- the objects ---------------------------------------------------------------------------------------------------

def is_wire(ob):
    return ob is not None and getattr(ob, 'type', '') == 'MESH' and TAG in ob.keys()


def _store_end(loc, n, t):
    if t is not None:
        mi = t.matrix_world.inverted_safe()
        return [t.name, list(mi @ Vector(loc)), list((t.matrix_world.to_3x3().transposed() @ Vector(n)).normalized())]
    return ['', list(Vector(loc)), list(Vector(n).normalized())]


def ends_of(context, ob):
    """The wire's two ends now (world): ((loc, normal), (loc, normal)) - they follow their meshes."""
    e = json.loads(ob[ENDS])
    out = []
    for name, loc, n in e:
        t = context.scene.objects.get(name) if name else None
        if t is not None:
            mw = t.matrix_world
            out.append((mw @ Vector(loc), (mw.to_3x3().inverted_safe().transposed() @ Vector(n)).normalized()))
        else:
            out.append((Vector(loc), Vector(n).normalized()))
    return out


def rebuild(context, ob, p):
    if ob.mode == 'EDIT':
        return
    (a, na), (b, nb) = ends_of(context, ob)
    if ob.data.users > 1:
        ob.data = ob.data.copy()
    mi = ob.matrix_world.inverted_safe()
    nm = ob.matrix_world.to_3x3().transposed()
    build_mesh(ob.data, mi @ a, nm @ na, mi @ b, nm @ nb, p)
    _mats(ob.data)
    ob[TAG] = json.dumps(p)


def make(context, a, b, p=None):
    """A wire from ``a`` to ``b`` (each (location, normal, mesh or None)), selected."""
    p = dict(p or numbers(_st(context)))
    me = bpy.data.meshes.new('MCH_Wire')
    ob = bpy.data.objects.new('MCH_Wire', me)
    coll = b[2].users_collection[0] if b[2] is not None and b[2].users_collection else context.collection
    coll.objects.link(ob)
    ob[ENDS] = json.dumps([_store_end(*a), _store_end(*b)])
    rebuild(context, ob, p)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def selected_wires(context):
    return [o for o in context.selected_objects if is_wire(o)]


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for w in selected_wires(context):
        rebuild(context, w, p)


class MCH_PG_Wire(bpy.types.PropertyGroup):
    style: bpy.props.EnumProperty(name='Style', items=STYLES, default='THIN', update=_update)
    count: bpy.props.IntProperty(name='Wires', default=5, min=1, max=60, update=_update,
                                 description='How many thin wires (Flat Ribbon: how wide, in wires)')
    thick: bpy.props.FloatProperty(name='Thickness', default=0.03, min=0.0005, soft_max=0.5, unit='LENGTH',
                                   update=_update, description='A thin wire\'s thickness (Single Wire: the wire\'s)')
    main_thick: bpy.props.FloatProperty(name='Main Thickness', default=0.1, min=0.001, soft_max=1.0, unit='LENGTH',
                                        update=_update, description='Thick + Thin: the thick one\'s thickness')
    length: bpy.props.FloatProperty(name='Length', default=1.1, min=1.0, max=3.0, update=_update,
                                    description='How much longer than straight (more: it hangs lower)')
    gravity: bpy.props.FloatProperty(name='Gravity', default=0.2, min=0.0, max=1.0, subtype='FACTOR', update=_update,
                                     description='How much it droops down (-Z)')
    twist: bpy.props.FloatProperty(name='Twist', default=1.0, min=-10.0, max=10.0, update=_update,
                                   description='Turns the wires make round each other from end to end')
    bend_lr: bpy.props.FloatProperty(name='Bend Left / Right', default=0.0, min=-1.0, max=1.0, update=_update)
    bend_fb: bpy.props.FloatProperty(name='Bend Front / Back', default=0.0, min=-1.0, max=1.0, update=_update)
    ties: bpy.props.IntProperty(name='Ties', default=4, min=0, max=30, update=_update,
                                description='Wire Loom: bands round the bundle')
    plugs: bpy.props.BoolProperty(name='End Plugs', default=True, update=_update,
                                  description='A plug at each end, on the surface')
    end_style: bpy.props.EnumProperty(name='End Finish', items=END_STYLES, default='PLUG', update=_update,
                                      description='How each end is finished on its surface')
    loose: bpy.props.FloatProperty(name='Loose', default=0.3, min=0.0, max=2.0, update=_update,
                                   description='Each wire its own way a little (0: tight)')
    seed: bpy.props.IntProperty(name='Seed', default=1, min=0, update=_update)
    sides: bpy.props.IntProperty(name='Sides', default=10, min=4, max=32, update=_update)
    segments: bpy.props.IntProperty(name='Segments', default=48, min=8, max=400, update=_update,
                                    description='Steps along it')


def _ray(context, event):
    from bpy_extras import view3d_utils
    xy = (event.mouse_region_x, event.mouse_region_y)
    o = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, xy)
    d = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, xy)
    hit, loc, nrm, _i, hob, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), o, d)
    if not hit or hob is None:
        return None, None, None
    real = bpy.data.objects.get(hob.name)
    if nrm.dot(d) > 0:
        nrm = -nrm
    return real, loc, nrm.normalized()


def _header(context, text):
    try:
        if context.area is not None:
            context.area.header_text_set(text)
    except (AttributeError, RuntimeError, TypeError):
        pass


class MCH_OT_wire_click(bpy.types.Operator):
    """Click a surface, then another: a wire between them.  A click on a wire selects it (Shift: add)"""
    bl_idname = 'mch.wire_click'
    bl_label = 'Wire Between Two Points'
    bl_options = {'REGISTER', 'UNDO'}
    extend: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        ob, loc, nrm = _ray(context, event)
        if ob is None or is_wire(ob):
            if not self.extend:
                for o in context.selected_objects:
                    o.select_set(False)
            if ob is not None:
                ob.select_set(True)
                context.view_layer.objects.active = ob
            PENDING['a'] = None
            _header(context, None)
            return {'FINISHED'}
        if PENDING['a'] is None:
            PENDING['a'] = (tuple(loc), tuple(nrm), ob.name)
            _header(context, 'Wire: now click where its other end goes (Esc: start over)')
            return {'FINISHED'}
        a = PENDING['a']
        PENDING['a'] = None
        _header(context, None)
        if (Vector(a[0]) - loc).length < 1e-5:
            return {'CANCELLED'}
        w = make(context, (a[0], a[1], context.scene.objects.get(a[2])), (loc, nrm, ob))
        self.report({'INFO'}, f'{w.name}: the sliders change it while selected')
        return {'FINISHED'}


class MCH_OT_wire_cancel(bpy.types.Operator):
    """Forget the first point clicked"""
    bl_idname = 'mch.wire_cancel'
    bl_label = 'Start Over'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        PENDING['a'] = None
        _header(context, None)
        return {'FINISHED'}


class MCH_OT_wire_pick(bpy.types.Operator):
    """The sliders take the selected wire's numbers"""
    bl_idname = 'mch.wire_pick'
    bl_label = 'Load From Selected'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        act = getattr(context, 'active_object', None)
        if not is_wire(act):
            return {'CANCELLED'}
        p = json.loads(act[TAG])
        st = _st(context)
        _BUSY[0] = True
        try:
            for k in KEYS:
                if k in p:
                    setattr(st, k, p[k])
        finally:
            _BUSY[0] = False
        return {'FINISHED'}


class MCH_OT_wire_plain(bpy.types.Operator):
    """Keep the selected wires as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.wire_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ws = selected_wires(context)
        for w in ws:
            for k in (TAG, ENDS):
                if k in w.keys():
                    del w[k]
        return {'FINISHED'} if ws else {'CANCELLED'}


def draw(layout, context):
    st = _st(context)
    box = layout.box()
    box.label(text='Wire Harness')
    box.label(text='Click a surface, then another: a wire between them', icon='MOUSE_LMB')
    if PENDING['a'] is not None:
        r = box.row(align=True)
        r.label(text='1st point picked: click the other end', icon='CHECKMARK')
        r.operator('mch.wire_cancel', text='', icon='X')
    col = box.column(align=True)
    col.prop(st, 'style', text='')
    c = box.column(align=True)
    if st.style != 'SINGLE':
        c.prop(st, 'count')
    c.prop(st, 'thick')
    if st.style == 'MAIN':
        c.prop(st, 'main_thick')
    if st.style == 'LOOM':
        c.prop(st, 'ties')
    c = box.column(align=True)
    c.label(text='Shape')
    for k in ('length', 'gravity', 'twist', 'bend_lr', 'bend_fb'):
        c.prop(st, k, slider=k != 'twist')
    c = box.column(align=True)
    if st.style in {'THIN', 'MAIN', 'LOOM'}:
        c.prop(st, 'loose', slider=True)
        c.prop(st, 'seed')
    c.prop(st, 'plugs', text='End Finish')
    if st.plugs:
        c.prop(st, 'end_style', text='')
    r = box.row(align=True)
    r.prop(st, 'sides')
    r.prop(st, 'segments')
    n = len(selected_wires(context))
    if n:
        box.label(text=f'{n} wire(s) selected: live', icon='INFO')
        r = box.row(align=True)
        r.operator('mch.wire_pick', icon='IMPORT')
        r.operator('mch.wire_plain', icon='CHECKMARK')


class MCH_TOOL_wire(bpy.types.WorkSpaceTool):
    """0.24.313 Wire Harness"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.wire_gen'
    bl_label = 'Wire Harness'
    bl_description = ('Click a surface, then another: a wire between them (Flat Ribbon / Single / Thin Wires / '
                      'Thick + Thin / Wire Loom) - Length, Gravity, Twist, Bend; the sliders change the selected '
                      'wires')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('mch.wire_click', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),
                 ('mch.wire_click', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('extend', True)]}),
                 ('mch.wire_cancel', {'type': 'ESC', 'value': 'PRESS'}, None))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Wire, MCH_OT_wire_click, MCH_OT_wire_cancel, MCH_OT_wire_pick, MCH_OT_wire_plain)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_wire = bpy.props.PointerProperty(type=MCH_PG_Wire)
    try:
        bpy.utils.register_tool(MCH_TOOL_wire, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_wire)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_wire
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
