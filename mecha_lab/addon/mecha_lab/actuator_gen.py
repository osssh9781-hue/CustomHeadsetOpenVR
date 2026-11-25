"""0.24.308 Cylinder - a hydraulic / linear actuator (user, with a photo of a mech's leg: "이건 나사잖아!! 내가 첨부한거처럼
원형 실린더랑 네모난 실린더로 만들어줘, 비율은 내가 조정 가능하게, 그리고 각 끝부분에 메카랑 연결되는 부분 쪽 나사가 있는 부분
크기 두께 나사 유무까지 조정되게").

Two objects on the 3D cursor, along Z: the Body (a round or square barrel, its end caps, the rear mount) and the
Rod (sliding out of it, the rod-end mount) - its origin at the rod end's pin (move it along Z to extend it).
Each end: an Eye (one plate with a hole) or a Clevis (a fork: two plates), its Size, Thickness, Hole and a Bolt
through it (a hex bolt and its nut) on or off.  Proportions: Length (pin to pin), Width, Depth (square), Body (its
share of the length), Rod (of the width), Caps, Corner Round, Body Bolts.  The sliders change the selected one."""
from __future__ import annotations

import json
import math

import bmesh
import bpy
from mathutils import Matrix, Vector

from . import mech_revolve as mr

TAG = 'mch_act'                  # on both objects: the actuator's id
PART = 'mch_act_part'            # 'BODY' / 'ROD'
PARAMS = 'mch_act_p'
_BUSY = [False]

SHAPES = (('ROUND', 'Round Body', 'A round barrel'), ('SQUARE', 'Square Body', 'A square housing (rounded corners)'))
ROD_SHAPES = (('ROUND', 'Round Rod', 'A round rod'), ('SQUARE', 'Square Rod', 'A square rod'))
MOUNTS = (('EYE', 'Eye Plate', 'One plate with a hole (a rod eye)'), ('CLEVIS', 'Clevis', 'A fork: two plates, the pin '
                                                                                   'through both'),
          ('BALL', 'Ball Joint', 'A rod end with a ball bearing in its eye (it swivels a little)'),
          ('NONE', 'None', 'No mount: a flat end'))
BSTYLES = (('PLATE', 'Base Plate', 'On a square base plate with bolts at its corners'),
           ('ARM', 'Lever Arm', 'On a lever arm going out sideways (its end chamfered) - Arm Length / Thickness / Width / '
                          'Turn'),
           ('BARE', 'Ears Only', 'No base plate: just the ears round the pin (a clevis\' two joined at their foot), '
                                 'their foot on the surface'))      # 0.24.324
LINK_KEYS = ('size', 'thick', 'hole', 'bolt', 'bracket', 'base', 'base_t', 'bstyle', 'arm_len', 'arm_t', 'arm_w',
             'arm_turn')      # 0.24.324 Link Ends: the pairs that change together (not the mount type)
SCALED = ('L', 'W', 'hinge_gap', 'cage_len') + tuple(f'{e}_{k}' for e in ('rear', 'front')
                                                    for k in ('size', 'thick', 'hole', 'base', 'base_t', 'arm_len',
                                                              'arm_t', 'arm_w'))


def _st(context):
    return context.scene.mch_actuator


END_KEYS = ('type', 'size', 'thick', 'hole', 'bolt', 'bracket', 'base', 'base_t', 'bstyle', 'arm_len', 'arm_t',
            'arm_w', 'arm_turn')
MORE_KEYS = ('hinge_gap', 'bracket_bolts', 'spring', 'spring_coils', 'spring_wire', 'spring_size', 'spring_seat',
             'spring_place', 'seat_style', 'seat_teeth', 'cage_posts', 'cage_len')
SPRING_PLACES = (('BODY', 'Round the Body', 'From a seat on the body to one under the rod end'),
                 ('ROD', 'Round the Rod', 'From a seat on the gland (the body\'s top) to one under the rod end - '
                                          'round the rod only'))
SEAT_STYLES = (('FLAT', 'Flat Seat', 'Flat rings'), ('CASTLE', 'Toothed Seat', 'Rings with teeth round their rims'),
               ('CUP', 'Cup Seat', 'Rings with a lip round the coil\'s ends'))


def numbers(st):
    p = dict(shape=st.shape, L=st.length, W=st.width, depth=st.depth, body=st.body_share, rod=st.rod_ratio,
             rod_shape=st.rod_shape, cap=st.cap_ratio, flare=st.cap_flare, corner=st.corner, bolts=bool(st.body_bolts),
             segs=int(st.segments))
    for e in ('rear', 'front'):
        for k in END_KEYS:
            p[f'{e}_{k}'] = getattr(st, f'{e}_{k}')
    for k in MORE_KEYS:                                     # 0.24.309 the brackets, the spring
        p[k] = getattr(st, k)
    f = float(getattr(st, 'overall', 1.0))                  # 0.24.324 Overall Size: every length at once
    if f != 1.0:
        for k in SCALED:
            p[k] = p[k] * f
    return p


# --- the parts -------------------------------------------------------------------------------------------------

def _tab_outline(size, neck, n):
    """The eye plate's outline round its hole's centre [(u, v)]: a disc (``size`` across) and a neck ``neck`` long
    toward +v, square sided; its two corners exactly."""
    s2 = size / 2
    angs = [2 * math.pi * j / n for j in range(n)]
    for c in (math.atan2(neck, s2), math.atan2(neck, -s2)):
        angs.append(c % (2 * math.pi))
    angs = sorted(set(round(a, 9) for a in angs))
    out = []
    for a in angs:
        ca, sa = math.cos(a), math.sin(a)
        r = s2
        if sa > 1e-9:
            t = neck / sa
            if abs(ca) > 1e-9:
                t = min(t, s2 / abs(ca))
            r = max(r, t)
        out.append((a, r))
    return out


def tab(bm, size, neck, thick, hole_r, n, M, mat=0):
    """An eye plate (extruded ``thick`` along w), its hole ``hole_r``; (u, v, w) mapped by ``M``."""
    ol = _tab_outline(size, neck, n)
    hole_r = min(hole_r, size * 0.42)
    vs = {}
    for side, w in (('a', -thick / 2), ('b', thick / 2)):
        vs[side] = [bm.verts.new(M @ Vector((r * math.cos(a), r * math.sin(a), w))) for a, r in ol]
        vs[side + 'h'] = [bm.verts.new(M @ Vector((hole_r * math.cos(a), hole_r * math.sin(a), w))) for a, _r in ol]
    m = len(ol)
    for j in range(m):
        k = (j + 1) % m
        for quad in ((vs['a'][j], vs['a'][k], vs['b'][k], vs['b'][j]),
                     (vs['bh'][j], vs['bh'][k], vs['ah'][k], vs['ah'][j]),
                     (vs['a'][k], vs['a'][j], vs['ah'][j], vs['ah'][k]),
                     (vs['b'][j], vs['b'][k], vs['bh'][k], vs['bh'][j])):
            f = bm.faces.new(quad)
            f.material_index = mat


def box(bm, lo, hi, M, mat=0):
    vs = []
    for x in (lo[0], hi[0]):
        for y in (lo[1], hi[1]):
            for z in (lo[2], hi[2]):
                vs.append(bm.verts.new(M @ Vector((x, y, z))))
    idx = ((0, 1, 3, 2), (4, 6, 7, 5), (0, 4, 5, 1), (2, 3, 7, 6), (0, 2, 6, 4), (1, 5, 7, 3))
    for q in idx:
        f = bm.faces.new([vs[i] for i in q])
        f.material_index = mat


def bracket_on(p, end):
    return bool(p.get(f'{end}_bracket', False)) and p[f'{end}_type'] != 'NONE'


def end_span(p, end):
    """How wide the hinge is along the pin (X): the end's plates, with the bracket's round them (an Eye end in a
    Clevis bracket)."""
    t = p[f'{end}_thick']
    hg = p.get('hinge_gap', 0.005)
    if p[f'{end}_type'] in {'EYE', 'BALL'}:
        w = ball_w(p, end) if p[f'{end}_type'] == 'BALL' else t
        return (w + 2 * hg) + 2 * t if bracket_on(p, end) else w
    return 3 * t


def ball_w(p, end):
    """A ball joint's ball: as wide along the pin."""
    return p[f'{end}_thick'] * 1.6


def ball_r(p, end):
    size = p[f'{end}_size']
    hole = min(p[f'{end}_hole'], size * 0.8) / 2
    return max(min(size * 0.36, hole * 2.4), hole * 1.3, ball_w(p, end) * 0.6)


def prism(bm, pts, w0, w1, M, mat=0):
    """A closed prism: the outline ``pts`` [(u, v)] pushed from w0 to w1, mapped by ``M``."""
    a = [bm.verts.new(M @ Vector((u, v, w0))) for u, v in pts]
    b = [bm.verts.new(M @ Vector((u, v, w1))) for u, v in pts]
    n = len(pts)
    for f in [list(reversed(a)), b] + [[a[i], a[(i + 1) % n], b[(i + 1) % n], b[i]] for i in range(n)]:
        bm.faces.new(f).material_index = mat


def mount(bm, p, end, z_pin, direction, segs):
    """An end's mount at ``z_pin`` (``direction``: +1 its neck going up to the body, -1 down) and its bolt.
    Returns how far along Z (from the pin) the body / rod starts."""
    kind = p[f'{end}_type']
    if kind == 'NONE':
        return 0.0
    size = p[f'{end}_size']
    t = p[f'{end}_thick']
    hole = min(p[f'{end}_hole'], size * 0.8) / 2
    neck = size * 0.45                             # (the pin to where the neck meets the body)
    ov = size * 0.05                               # (into the body a little: no gap)
    # (u, v, w) -> (Y, direction * Z, X) at the pin
    M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, direction, 0, z_pin), (0, 0, 0, 1)))
    if kind == 'EYE':
        tab(bm, size, neck + ov, t, hole, max(24, segs), M)
    elif kind == 'BALL':                           # 0.24.310 a rod end: its eye round a ball bearing
        rb = ball_r(p, end)
        tab(bm, size, neck + ov, t, rb * 0.97, max(32, segs), M)
        hw = min(ball_w(p, end) / 2, rb * 0.85)
        prof = [(hole, -hw, 0.0, 'R')]
        n = 10
        for i in range(n + 1):
            x = -hw + 2 * hw * i / n
            prof.append((math.sqrt(max(rb * rb - x * x, 0.0)), x, 0.0, 'R'))
        prof.append((hole, hw, 0.0, 'R'))
        mr.revolve(bm, prof, max(32, segs), matrix=mr.frame(Vector((0, 0, z_pin)), Vector((1, 0, 0))), mat=1)
    else:
        gap = t
        for sgn in (-1, 1):
            Mw = M @ Matrix.Translation(Vector((0, 0, sgn * (gap / 2 + t / 2))))
            tab(bm, size, neck + ov, t, hole, max(24, segs), Mw)
        box(bm, (-size / 2, neck - t * 0.9, -(gap / 2 + t)), (size / 2, neck + ov, gap / 2 + t), M)
    span = end_span(p, end)                        # (the bolt through the bracket too)
    if p[f'{end}_bolt']:                           # (a hex bolt through, its nut on the other side)
        sr = hole * 0.96
        hr, hh = hole * 1.9, hole * 1.15
        nh = hole * 1.0
        seg6 = max(36, int(math.ceil(segs / 12.0)) * 12)
        bp = mr.bolt_profile(sr, span + nh * 1.6, 'HEX', hr, hh, thread=True, pitch=max(sr * 0.35, 1e-4))
        mr.revolve(bm, bp, seg6, depth=sr * 0.12, pitch=max(sr * 0.35, 1e-4),
                   matrix=mr.frame(Vector((span / 2, 0, z_pin)), Vector((1, 0, 0))), mat=1)
        mr.revolve(bm, mr.nut_profile(sr * 1.0, hr, nh), seg6,
                   matrix=mr.frame(Vector((-span / 2, 0, z_pin)), Vector((-1, 0, 0))), mat=1)
    return neck


def build_bracket(me, p, end):
    """0.24.309 (user: "양 끝부분에 반대쪽에 달릴 부분도 만들어줘, 경첩인 거니깐"): the part the end hinges in - its
    pin's centre at the origin, the other way from the end: a Clevis for an Eye end, a tongue (Eye) between a Clevis
    end's plates; on a base plate (to fix on the mech) with a bolt head at each corner."""
    bm = bmesh.new()
    try:
        segs = max(24, int(p['segs']))
        size = p[f'{end}_size']
        t = p[f'{end}_thick']
        hg = p.get('hinge_gap', 0.005)
        hole = min(p[f'{end}_hole'], size * 0.8) / 2
        db = -1 if end == 'rear' else 1                       # (away from the cylinder)
        M = Matrix(((0, 0, 1, 0), (1, 0, 0, 0), (0, db, 0, 0), (0, 0, 0, 1)))
        nb = size * 0.75                                      # (the pin to the base plate)
        ov = size * 0.05
        span = end_span(p, end)
        if p[f'{end}_type'] in {'EYE', 'BALL'}:              # (a clevis round the eye / the ball)
            gap = (ball_w(p, end) if p[f'{end}_type'] == 'BALL' else t) + 2 * hg
            for sgn in (-1, 1):
                Mw = M @ Matrix.Translation(Vector((0, 0, sgn * (gap / 2 + t / 2))))
                tab(bm, size, nb + ov, t, hole, segs, Mw)
        else:                                                 # (a tongue between the clevis' plates)
            tab(bm, size, nb + ov, max(t - 2 * hg, t * 0.3), hole, segs, M)
        if p.get(f'{end}_bstyle', 'PLATE') == 'BARE':         # 0.24.324 (user: "바닥 판 없이 깔끔하게 홀까지만")
            if p[f'{end}_type'] in {'EYE', 'BALL'}:          # (the clevis' two ears joined by a slim foot)
                gap = (ball_w(p, end) if p[f'{end}_type'] == 'BALL' else t) + 2 * hg
                fb = max(t * 0.6, size * 0.08)
                box(bm, (-size / 2, nb + ov - fb, -(gap / 2 + t)), (size / 2, nb + ov, gap / 2 + t), M)
            mr.finish(bm)
            bm.to_mesh(me)
            me.update()
            return
        if p.get(f'{end}_bstyle', 'PLATE') == 'ARM':          # 0.24.310 (user's photo: a lever arm under it)
            al = max(p.get(f'{end}_arm_len', size * 2.5), size * 0.8)
            at = max(p.get(f'{end}_arm_t', size * 0.45), 1e-4)
            aw = max(p.get(f'{end}_arm_w', size), span * 1.05)
            Ma = M @ Matrix.Rotation(math.radians(p.get(f'{end}_arm_turn', 0.0)), 4, 'Y')
            u0, u1 = -size * 0.6, al
            ch = min(at * 0.7, (u1 - u0) * 0.3)
            prism(bm, [(u0, nb), (u1, nb), (u1, nb + at - ch), (u1 - ch, nb + at), (u0, nb + at)], -aw / 2, aw / 2, Ma)
            if p.get('bracket_bolts', True):                 # (socket heads on its top, past the joint)
                hr, hh = min(at, aw) * 0.22, min(at, aw) * 0.16
                up = (Ma.to_3x3() @ Vector((0, -1, 0))).normalized()
                for u in (u1 - size * 0.45, u1 - size * 1.05):
                    if u > size * 0.75:
                        mr.revolve(bm, mr.bolt_profile(hr * 0.5, 0.0, 'SOCKET', hr, hh), 36,
                                   matrix=mr.frame(Ma @ Vector((u, nb + hh * 0.15, 0.0)), up), mat=1)
            mr.finish(bm)
            bm.to_mesh(me)
            me.update()
            return
        B = max(p.get(f'{end}_base', size * 1.6), size * 1.3, span * 1.45)   # (its corner bolts clear of the fork)
        bt = max(p.get(f'{end}_base_t', size * 0.15), 1e-4)
        box(bm, (-B / 2, nb, -B / 2), (B / 2, nb + bt, B / 2), M)
        if p.get('bracket_bolts', True):                     # (socket heads at its corners, on the pin's side)
            hr, hh = B * 0.07, B * 0.05
            up = (M.to_3x3() @ Vector((0, -1, 0))).normalized()
            for u in (-1, 1):
                for w in (-1, 1):
                    c = M @ Vector((u * B * 0.36, nb + hh * 0.15, w * B * 0.36))
                    mr.revolve(bm, mr.bolt_profile(hr * 0.5, 0.0, 'SOCKET', hr, hh), 36, matrix=mr.frame(c, up),
                               mat=1)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def spring_ns(p, length):
    """The coil (spring_gen's numbers) round the cylinder."""
    from types import SimpleNamespace
    W = p['W']
    return SimpleNamespace(wire=max(W * p.get('spring_wire', 0.07), 1e-5), end_coils=1.0,
                           coils=max(1.0, float(p.get('spring_coils', 8))), width=W * p.get('spring_size', 1.5),
                           end_width=1.0, profile='ROUND', sides=8, resolution=12, hand='RIGHT', caps=True)


def spring_seats(p):
    """(z of the seat on the body, z of the seat on the rod - rod at its pin L, the seats' height, outer radius)."""
    g = layout(p)
    W = p['W']
    wire = W * p.get('spring_wire', 0.07)
    hs = max(wire * 1.2, W * 0.03)
    za = g['z0'] + g['Lb'] * min(max(p.get('spring_seat', 0.5), 0.1), 0.95)
    if p.get('spring_place', 'BODY') == 'ROD':          # 0.24.311 (user's reference): round the rod, from the gland
        za = g['z1'] + hs
        if int(p.get('cage_posts', 0)) > 0:             # (the cage between the gland and the seat, as in it)
            za += max(p.get('cage_len', W * 0.5), hs) + hs
    c2 = min(W * 0.12, (g['zr1'] - g['z0']) * 0.1)
    zb = g['zr1'] - c2 - hs
    Rs = W * p.get('spring_size', 1.5) / 2 + wire * 0.6
    return za, zb, hs, Rs


def seat(bm, p, z, up, ri, segs):
    """A spring seat: a ring from ``ri`` out to past the coil, at ``z`` (its face toward the coil: ``up`` +1 above,
    -1 below) - Flat, Toothed (teeth round its rim) or Cup (a lip round the coil's end); and the Cage's posts under
    the lower seat."""
    _za, _zb, hs, Rs = spring_seats(p)
    W = p['W']
    wire = W * p.get('spring_wire', 0.07)
    style = p.get('seat_style', 'FLAT')
    sh = 'C' if style == 'CASTLE' else 'R'
    teeth = float(p.get('seat_teeth', 10))
    Ro = Rs + (wire * 0.9 if style == 'CASTLE' else 0.0)
    a, b = z - up * hs, z                               # (its back, its face)
    if style == 'CUP':
        lip, lh = wire * 0.5, wire * 1.4
        P = [(ri, b, 0.0, 'R'), (ri, a, 0.0, 'R'), (Rs + lip, a, 0.0, 'R'), (Rs + lip, b + up * lh, 0.0, 'R'),
             (Rs, b + up * lh, 0.0, 'R'), (Rs, b, 0.0, 'R')]
    else:
        P = [(ri, b, 0.0, 'R'), (ri, a, 0.0, 'R'), (Ro, a, 0.0, sh), (Ro, b, 0.0, sh)]
    if up < 0:
        P = list(reversed(P))
    seg_ = max(segs, int(teeth) * 8) if sh == 'C' else segs
    if sh == 'C':
        seg_ = int(math.ceil(seg_ / (2 * teeth)) * 2 * teeth)
    mr.revolve(bm, P, seg_, sq_p=teeth, mat=1)
    n = int(p.get('cage_posts', 0))
    if up > 0 and n > 0:                                # (a cage under the lower seat: posts and a ring)
        Lc = max(p.get('cage_len', W * 0.5), hs)
        pr = max(wire * 0.55, W * 0.025)
        rc = (ri + Rs) / 2 if (Rs - ri) > pr * 3 else Rs - pr * 1.5
        for k in range(n):
            ang = 2 * math.pi * (k + 0.5) / n
            c = Vector((rc * math.cos(ang), rc * math.sin(ang), a))
            mr.revolve(bm, [(0.0, 0.0, 0.0, 'R'), (pr, 0.0, 0.0, 'R'), (pr, Lc, 0.0, 'R'), (0.0, Lc, 0.0, 'R')], 12,
                       matrix=mr.frame(c, Vector((0, 0, -1))), mat=1)
        mr.revolve(bm, [(ri, a - Lc, 0.0, 'R'), (ri, a - Lc - hs, 0.0, 'R'), (Rs, a - Lc - hs, 0.0, 'R'),
                        (Rs, a - Lc, 0.0, 'R')], segs, mat=1)


def layout(p):
    """Where things go along Z: (z0 body start, z1 body end (its gland's top), rod start, rod end, ...)."""
    L = max(p['L'], 1e-3)
    rear = 0.0 if p['rear_type'] == 'NONE' else p['rear_size'] * 0.45
    front = 0.0 if p['front_type'] == 'NONE' else p['front_size'] * 0.45
    span = max(L - rear - front, L * 0.2)
    Lb = span * min(max(p['body'], 0.15), 0.95)
    return dict(L=L, z0=rear, z1=rear + Lb, zr1=L - front, span=span, Lb=Lb)


def _sq_p(corner):
    return 2.0 + 28.0 * (1.0 - min(max(corner, 0.0), 1.0)) ** 2


def build_body(me, p):
    g = layout(p)
    bm = bmesh.new()
    try:
        segs = max(16, int(p['segs']))
        sh = 'S' if p['shape'] == 'SQUARE' else 'R'
        ys = p['depth'] if sh == 'S' else 1.0
        W = p['W']
        Rb = W / 2
        Rc = Rb * max(p['flare'], 0.5)
        rr = Rb * min(max(p['rod'], 0.05), 0.95)
        Rg = min(rr * 1.4, Rb * 0.98)
        z0, z1 = g['z0'], g['z1']
        gl = min(g['Lb'] * 0.06, W * 0.15)
        capL = min(g['Lb'] * min(max(p['cap'], 0.02), 0.45), (g['Lb'] - gl) * 0.45)
        zt = z1 - gl                                       # (the front cap's face; the gland above it)
        ch = min(capL * 0.18, W * 0.04)
        rsh = 'S' if p['rod_shape'] == 'SQUARE' else 'R'
        P = [(0.0, z0, 0.0, sh), (Rc - ch, z0, 0.0, sh), (Rc, z0 + ch, 0.0, sh), (Rc, z0 + capL - ch, 0.0, sh),
             (Rc - ch, z0 + capL, 0.0, sh), (Rb, z0 + capL, 0.0, sh), (Rb, zt - capL, 0.0, sh),
             (Rc - ch, zt - capL, 0.0, sh), (Rc, zt - capL + ch, 0.0, sh), (Rc, zt - ch, 0.0, sh),
             (Rc - ch, zt, 0.0, sh), (Rg, zt, 0.0, rsh), (Rg, z1, 0.0, rsh), (0.0, z1, 0.0, rsh)]
        mr.revolve(bm, P, segs, sq_p=_sq_p(p['corner']), yscale=ys)
        if p['bolts']:                                     # (bolt heads at the caps' corners)
            hr, hh = W * 0.055, W * 0.04
            k = 0.7
            for zf, d in ((z0, -1.0), (zt, 1.0)):
                for a in (45, 135, 225, 315):
                    ar = math.radians(a)
                    x, y = Rc * k * math.cos(ar), Rc * k * math.sin(ar) * ys
                    if sh == 'S':
                        x, y = Rc * k * math.copysign(0.78, math.cos(ar)), Rc * k * math.copysign(0.78, math.sin(ar)) * ys
                    mr.revolve(bm, mr.bolt_profile(hr * 0.5, 0.0, 'SOCKET', hr, hh), 36,
                               matrix=mr.frame(Vector((x, y, zf - d * hh * 0.15)), Vector((0, 0, d))), mat=1)
        if p.get('spring'):                                # (the spring's seat round the barrel)
            za, _zb, hs, Rs = spring_seats(p)
            if p.get('spring_place', 'BODY') == 'ROD':       # (on the gland, round the rod)
                ri = Rb * min(max(p['rod'], 0.05), 0.95) * 1.08
            else:
                ri = Rb * (0.9 if sh == 'S' else 0.97)
            seat(bm, p, za, 1, ri, segs)
        mount(bm, p, 'rear', 0.0, 1, segs)
        mr.finish(bm)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def build_rod(me, p):
    """The rod (its origin at the rod end's pin: z = L)."""
    g = layout(p)
    bm = bmesh.new()
    try:
        segs = max(16, int(p['segs']))
        W = p['W']
        Rb = W / 2
        rr = Rb * min(max(p['rod'], 0.05), 0.95)
        rsh = 'S' if p['rod_shape'] == 'SQUARE' else 'R'
        ys = p['depth'] if (rsh == 'S' and p['shape'] == 'SQUARE') else 1.0
        zr0 = g['z0'] + g['Lb'] * 0.35                    # (deep in the body: it slides)
        zr1 = g['zr1']
        c2 = min(W * 0.12, (zr1 - zr0) * 0.1)
        P = [(0.0, zr0, 0.0, rsh), (rr, zr0, 0.0, rsh), (rr, zr1 - c2, 0.0, rsh), (rr * 1.3, zr1 - c2, 0.0, rsh),
             (rr * 1.3, zr1 + p['front_size'] * 0.03, 0.0, rsh), (0.0, zr1 + p['front_size'] * 0.03, 0.0, rsh)]
        mr.revolve(bm, P, segs, sq_p=_sq_p(p['corner']), yscale=ys)
        if p.get('spring'):                                # (the spring's seat on the rod, under its end)
            _za, zb, hs, Rs = spring_seats(p)
            seat(bm, p, zb, -1, rr * 0.97, segs)
        mount(bm, p, 'front', g['L'], -1, segs)
        mr.finish(bm)
        bmesh.ops.translate(bm, verts=list(bm.verts), vec=Vector((0, 0, -g['L'])))
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


# --- the objects ------------------------------------------------------------------------------------------------

def act_of(ob):
    return ob.get(TAG, '') if ob is not None and getattr(ob, 'type', '') == 'MESH' else ''


def parts_of(scene, aid):
    d = {}
    for o in scene.objects:
        if act_of(o) == aid:
            d[o.get(PART, '')] = o
    return d


def params(ob):
    try:
        return json.loads(ob.get(PARAMS, '{}'))
    except (TypeError, ValueError):
        return {}


def build(context, p, aid=None):
    scene = context.scene
    old = parts_of(scene, aid) if aid else {}
    if not aid:
        k = 1
        names = {act_of(o) for o in scene.objects}
        while f'Act{k}' in names:
            k += 1
        aid = f'Act{k}'
    body = old.get('BODY')
    glued = None
    if body is not None and body.get(GLUE):                # 0.24.312 clicked between two surfaces: glue it again
        try:
            pts = _glue_points(context, json.loads(body[GLUE]))
            fr = glue_frame(p, pts[0], pts[1])
            if fr is not None:
                p = dict(p, L=(fr[1] - fr[0]).length)
                glued = (pts, fr)
        except (TypeError, ValueError, KeyError, IndexError):
            glued = None
    rod0 = old.get('ROD')
    base = body.matrix_world.copy() if body is not None else Matrix.Translation(scene.cursor.location)
    slide = 0.0                                            # (how far the user slid the rod out: kept)
    if body is not None and rod0 is not None and rod0.parent is body:
        slide = rod0.matrix_basis.translation.z - layout(params(body) or p)['L']   # (its own: no stale world matrix)
    coll = body.users_collection[0] if body is not None and body.users_collection else context.collection
    out = {}
    for part, fn in (('BODY', build_body), ('ROD', build_rod)):
        ob = old.get(part)
        if ob is None:
            nm = f'MCH_{aid}_{part.title()}'
            ob = bpy.data.objects.new(nm, bpy.data.meshes.new(nm))
            coll.objects.link(ob)
        elif ob.mode == 'EDIT':
            out[part] = ob
            continue
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        fn(ob.data, p)
        ob[TAG] = aid
        ob[PART] = part
        ob[PARAMS] = json.dumps(p)
        out[part] = ob
    body, rod = out['BODY'], out['ROD']
    if body.mode != 'EDIT' and body is not old.get('BODY'):
        body.matrix_world = base
    if rod.mode != 'EDIT':
        if rod.parent is not body:
            rod.parent = body
        rod.matrix_parent_inverse = Matrix.Identity(4)
        rod.matrix_basis = Matrix.Translation((0.0, 0.0, layout(p)['L'] + slide))
    bw = body.matrix_basis.copy() if body.parent is None else body.matrix_world.copy()   # (the rear pin)
    for end, part, pin in (('rear', 'BRACKET_REAR', bw),
                           ('front', 'BRACKET_FRONT', bw @ rod.matrix_basis)):
        ob = old.get(part)
        if not bracket_on(p, end):
            _drop(ob)
            continue
        new = ob is None
        if new:
            nm = f'MCH_{aid}_{"Rear" if end == "rear" else "Front"}Bracket'
            ob = bpy.data.objects.new(nm, bpy.data.meshes.new(nm))
            coll.objects.link(ob)
        if ob.mode == 'EDIT':
            out[part] = ob
            continue
        if ob.data.users > 1:
            ob.data = ob.data.copy()
        build_bracket(ob.data, p, end)
        ob[TAG], ob[PART], ob[PARAMS] = aid, part, json.dumps(p)
        auto = list(ob.get(AUTO, []))
        here = [x for row in ob.matrix_basis for x in row]
        if new or (len(auto) == 16 and max(abs(a - b) for a, b in zip(auto, here)) < 1e-5):
            ob.matrix_basis = pin                          # (where its pin is - till you move it to the mech)
            ob[AUTO] = [x for row in pin for x in row]
        out[part] = ob
    set_spring(context, p, aid, out, old, coll, slide)
    if glued is not None:
        apply_glue(out, glued[0][0], glued[0][1], glued[1])
    return aid, out


AUTO = 'mch_act_auto'           # on a bracket: where it was put by itself (moved by you: it stays)


def _drop(ob):
    if ob is None:
        return
    me = ob.data if ob.type == 'MESH' else None
    bpy.data.objects.remove(ob)
    if me is not None and me.users == 0:
        bpy.data.meshes.remove(me)


def set_spring(context, p, aid, out, old, coll, slide):
    """0.24.309 (user: "실린더에 스프링 옵션도"): a coil round it from the seat on the body to the seat on the rod -
    a child of the body, stretched to an empty under the rod (Stretch To): extend the rod, the spring follows."""
    sp, end = old.get('SPRING'), old.get('SPRING_END')
    body, rod = out['BODY'], out['ROD']
    if not p.get('spring'):
        _drop(sp)
        _drop(end)
        return
    za, zb, hs, Rs = spring_seats(p)
    L = layout(p)['L']
    rest = max((zb + slide) - za, 1e-4)
    if end is None:
        end = bpy.data.objects.new(f'MCH_{aid}_SpringEnd', None)
        end.empty_display_size = p['W'] * 0.2
        coll.objects.link(end)
        end.hide_select = True
    end.parent = rod
    end.matrix_parent_inverse = Matrix.Identity(4)
    end.matrix_basis = Matrix.Translation((0.0, 0.0, zb - L))
    end[TAG], end[PART] = aid, 'SPRING_END'
    try:
        end.hide_set(True)
    except RuntimeError:
        pass
    if sp is None:
        nm = f'MCH_{aid}_Spring'
        sp = bpy.data.objects.new(nm, bpy.data.meshes.new(nm))
        coll.objects.link(sp)
    from . import spring_gen
    verts, faces = spring_gen.build([Vector((0, 0, 0)), Vector((0, rest, 0))], Vector((0, 0, 1)), spring_ns(p, rest))
    me = sp.data
    if me.users > 1:
        me = sp.data = sp.data.copy()
    me.clear_geometry()
    me.from_pydata([tuple(v) for v in verts], [], faces)
    for f in me.polygons:
        f.use_smooth = True
    me.update()
    sp.parent = body
    sp.matrix_parent_inverse = Matrix.Identity(4)
    sp.matrix_basis = Matrix.Translation((0.0, 0.0, za)) @ Matrix.Rotation(math.radians(90), 4, 'X')
    c = sp.constraints.get('MCH Spring Stretch') or sp.constraints.new('STRETCH_TO')
    c.name = 'MCH Spring Stretch'
    c.target = end
    c.rest_length = rest
    c.volume = 'NO_VOLUME'
    sp[TAG], sp[PART], sp[PARAMS] = aid, 'SPRING', json.dumps(p)
    out['SPRING'], out['SPRING_END'] = sp, end


def selected_acts(context):
    out = []
    for o in context.selected_objects:
        a = act_of(o)
        if a and a not in out:
            out.append(a)
    return out


def _update(self, context):
    if _BUSY[0]:
        return
    p = numbers(self)
    for aid in selected_acts(context):
        build(context, p, aid)


_LINKING = [False]


def _linked(key):
    """0.24.324 (user: "위아래 판 홀 크기 사이즈 이런 거 각 쌍끼리 동시에 조절되게") with Link Ends on, the other end's
    same setting follows; one rebuild."""
    end, k = key.split('_', 1)
    other = 'front' if end == 'rear' else 'rear'

    def upd(self, context):
        if getattr(self, 'link_ends', False) and not _BUSY[0]:
            _BUSY[0] = True
            try:
                if getattr(self, f'{other}_{k}') != getattr(self, key):
                    setattr(self, f'{other}_{k}', getattr(self, key))
            finally:
                _BUSY[0] = False
        _update(self, context)
    return upd


def _link_on(self, context):
    """Link Ends turned on: the Rod End takes the Rear's settings (they match from here)."""
    if self.link_ends:
        _BUSY[0] = True
        try:
            for k in LINK_KEYS:
                setattr(self, f'front_{k}', getattr(self, f'rear_{k}'))
        finally:
            _BUSY[0] = False
    _update(self, context)


def _end_props(end, label, size, thick, hole):
    d = {}
    d[f'{end}_type'] = bpy.props.EnumProperty(name=f'{label} Mount', items=MOUNTS, default='CLEVIS' if end == 'rear'
                                              else 'EYE', update=_update)
    d[f'{end}_size'] = bpy.props.FloatProperty(name=f'{label} Size', default=size, min=0.002, soft_max=3.0,
                                               unit='LENGTH', update=_linked(f'{end}_size'),
                                               description='The mount\'s plate across (round its hole)')
    d[f'{end}_thick'] = bpy.props.FloatProperty(name=f'{label} Thickness', default=thick, min=0.001, soft_max=1.0,
                                                unit='LENGTH', update=_linked(f'{end}_thick'), description='The plate\'s thickness')
    d[f'{end}_hole'] = bpy.props.FloatProperty(name=f'{label} Pin Hole', default=hole, min=0.001, soft_max=1.0,
                                               unit='LENGTH', update=_linked(f'{end}_hole'),
                                               description='The hole (the bolt\'s diameter)')
    d[f'{end}_bolt'] = bpy.props.BoolProperty(name=f'{label} Bolt', default=True, update=_linked(f'{end}_bolt'),
                                              description='A hex bolt through it, its nut on the other side')
    d[f'{end}_bracket'] = bpy.props.BoolProperty(
        name=f'{label} Bracket', default=True, update=_linked(f'{end}_bracket'),
        description='The part it hinges in (an object of its own, to fix on the mech): a Clevis round an Eye, a '
                    'tongue between a Clevis\' plates, on a base plate')
    d[f'{end}_base'] = bpy.props.FloatProperty(name=f'{label} Base Plate', default=size * 1.8, min=0.002,
                                               soft_max=3.0, unit='LENGTH', update=_linked(f'{end}_base'),
                                               description='The bracket\'s base plate across')
    d[f'{end}_base_t'] = bpy.props.FloatProperty(name=f'{label} Base Thickness', default=size * 0.15, min=0.0005,
                                                 soft_max=1.0, unit='LENGTH', update=_linked(f'{end}_base_t'))
    d[f'{end}_bstyle'] = bpy.props.EnumProperty(name=f'{label} Bracket Style', items=BSTYLES, default='PLATE',
                                                update=_linked(f'{end}_bstyle'))
    d[f'{end}_arm_len'] = bpy.props.FloatProperty(name=f'{label} Arm Length', default=size * 2.5, min=0.002,
                                                  soft_max=5.0, unit='LENGTH', update=_linked(f'{end}_arm_len'),
                                                  description='How far the arm goes out from the joint')
    d[f'{end}_arm_t'] = bpy.props.FloatProperty(name=f'{label} Arm Thickness', default=size * 0.45, min=0.0005,
                                                soft_max=2.0, unit='LENGTH', update=_linked(f'{end}_arm_t'))
    d[f'{end}_arm_w'] = bpy.props.FloatProperty(name=f'{label} Arm Width', default=size * 1.0, min=0.0005,
                                                soft_max=2.0, unit='LENGTH', update=_linked(f'{end}_arm_w'),
                                                description='The arm across (along the pin; at least the joint)')
    d[f'{end}_arm_turn'] = bpy.props.FloatProperty(name=f'{label} Arm Turn', default=0.0, min=-180.0, max=180.0,
                                                   update=_linked(f'{end}_arm_turn'),
                                                   description='Which way the arm goes out, round the cylinder\'s '
                                                               'axis (degrees)')
    return d


class MCH_PG_Actuator(bpy.types.PropertyGroup):
    __annotations__ = dict(
        shape=bpy.props.EnumProperty(name='Shape', items=SHAPES, default='ROUND', update=_update),
        overall=bpy.props.FloatProperty(name='Overall Size', default=1.0, min=0.01, soft_max=5.0, update=_update,
                                        description='Every length of the cylinder at once (its mounts and brackets '
                                                    'too); a cylinder clicked between two surfaces keeps its length'),
        link_ends=bpy.props.BoolProperty(name='Link Ends', default=False, update=_link_on,
                                         description='Both mounts change together (size, thickness, pin hole, bolt, '
                                                     'bracket, plate, arm - not the mount type); on: the Rod End takes '
                                                     'the Rear\'s'),
        length=bpy.props.FloatProperty(name='Length', default=2.0, min=0.01, soft_max=20.0, unit='LENGTH',
                                       update=_update, description='Pin to pin'),
        width=bpy.props.FloatProperty(name='Width', default=0.36, min=0.002, soft_max=5.0, unit='LENGTH',
                                      update=_update, description='The body across'),
        depth=bpy.props.FloatProperty(name='Depth', default=1.0, min=0.2, max=4.0, update=_update,
                                      description='Square: its depth, of the width'),
        body_share=bpy.props.FloatProperty(name='Body Share', default=0.6, min=0.15, max=0.95, subtype='FACTOR',
                                           update=_update, description='The body\'s share of the length (the rest: '
                                                                       'the rod out of it)'),
        rod_ratio=bpy.props.FloatProperty(name='Rod Width', default=0.42, min=0.05, max=0.95, subtype='FACTOR',
                                          update=_update, description='The rod across, of the width'),
        rod_shape=bpy.props.EnumProperty(name='Rod Shape', items=ROD_SHAPES, default='ROUND', update=_update),
        cap_ratio=bpy.props.FloatProperty(name='Caps', default=0.14, min=0.02, max=0.45, subtype='FACTOR',
                                          update=_update, description='The end caps\' length, of the body'),
        cap_flare=bpy.props.FloatProperty(name='Cap Size', default=1.12, min=0.6, max=2.0, update=_update,
                                          description='The end caps across, of the body'),
        corner=bpy.props.FloatProperty(name='Corner Round', default=0.25, min=0.0, max=1.0, subtype='FACTOR',
                                       update=_update, description='Square: how round its corners'),
        body_bolts=bpy.props.BoolProperty(name='Body Bolts', default=True, update=_update,
                                          description='Bolt heads at the end caps\' corners'),
        segments=bpy.props.IntProperty(name='Segments', default=48, min=12, max=256, update=_update),
        hinge_gap=bpy.props.FloatProperty(name='Hinge Gap', default=0.005, min=0.0, soft_max=0.05, unit='LENGTH',
                                          update=_update, description='Room between the end and its bracket\'s '
                                                                      'plates (a print fit)'),
        bracket_bolts=bpy.props.BoolProperty(name='Bracket Bolts', default=True, update=_update,
                                             description='Bolt heads at the base plates\' corners'),
        spring=bpy.props.BoolProperty(name='Spring', default=False, update=_update,
                                      description='A coil spring round it, from a seat on the body to one under the '
                                                  'rod end (it stretches as the rod moves out)'),
        spring_coils=bpy.props.IntProperty(name='Coils', default=8, min=1, max=60, update=_update),
        spring_wire=bpy.props.FloatProperty(name='Wire', default=0.07, min=0.01, max=0.3, subtype='FACTOR',
                                            update=_update, description='The wire\'s thickness, of the width'),
        spring_size=bpy.props.FloatProperty(name='Spring Size', default=1.5, min=0.5, max=4.0, update=_update,
                                            description='The spring across, of the width'),
        spring_seat=bpy.props.FloatProperty(name='Spring Seat', default=0.5, min=0.1, max=0.95, subtype='FACTOR',
                                            update=_update,
                                            description='Where on the body its lower seat is (of the body)'),
        spring_place=bpy.props.EnumProperty(name='Spring On', items=SPRING_PLACES, default='BODY', update=_update),
        seat_style=bpy.props.EnumProperty(name='Seats', items=SEAT_STYLES, default='FLAT', update=_update),
        seat_teeth=bpy.props.IntProperty(name='Teeth', default=10, min=3, max=40, update=_update,
                                         description='Toothed Seat: teeth round its rim'),
        cage_posts=bpy.props.IntProperty(name='Cage Posts', default=0, min=0, max=12, update=_update,
                                         description='Posts under the lower seat down to a ring (a cage; 0: none)'),
        cage_len=bpy.props.FloatProperty(name='Cage Length', default=0.18, min=0.001, soft_max=2.0, unit='LENGTH',
                                         update=_update, description='How long the cage\'s posts'),
        **_end_props('rear', 'Rear', 0.34, 0.1, 0.1),
        **_end_props('front', 'Rod End', 0.26, 0.12, 0.08),
    )


class MCH_OT_actuator_add(bpy.types.Operator):
    """A cylinder (a body and a rod sliding out of it, a mount and its bolt at each end) on the 3D cursor"""
    bl_idname = 'mch.actuator_add'
    bl_label = 'Summon Cylinder'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Cylinder: Object Mode only')
            return {'CANCELLED'}
        aid, obs = build(context, numbers(_st(context)))
        for o in context.selected_objects:
            o.select_set(False)
        for o in obs.values():
            o.select_set(True)
        context.view_layer.objects.active = obs['BODY']
        self.report({'INFO'}, f'{aid}: the sliders change it while selected; move the Rod along Z to extend it')
        return {'FINISHED'}


class MCH_OT_actuator_pick(bpy.types.Operator):
    """The sliders take the selected cylinder's numbers"""
    bl_idname = 'mch.actuator_pick'
    bl_label = 'Load From Selected'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        act = getattr(context, 'active_object', None)
        p = params(act) if act_of(act) else {}
        if not p:
            return {'CANCELLED'}
        st = _st(context)
        keys = dict(shape='shape', L='length', W='width', depth='depth', body='body_share', rod='rod_ratio',
                    rod_shape='rod_shape', cap='cap_ratio', flare='cap_flare', corner='corner', bolts='body_bolts',
                    segs='segments')
        for e in ('rear', 'front'):
            for k in END_KEYS:
                keys[f'{e}_{k}'] = f'{e}_{k}'
        for k in MORE_KEYS:
            keys[k] = k
        _BUSY[0] = True
        try:
            for k, a in keys.items():
                if k in p:
                    setattr(st, a, p[k])
        finally:
            _BUSY[0] = False
        return {'FINISHED'}


class MCH_OT_actuator_plain(bpy.types.Operator):
    """Keep the selected cylinders as plain meshes (the sliders leave them alone after)"""
    bl_idname = 'mch.actuator_plain'
    bl_label = 'Make Plain'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        aids = selected_acts(context)
        if not aids:
            self.report({'WARNING'}, 'Make Plain: select a cylinder')
            return {'CANCELLED'}
        for aid in aids:
            for o in parts_of(context.scene, aid).values():
                for k in (TAG, PART, PARAMS):
                    if k in o.keys():
                        del o[k]
        return {'FINISHED'}


def draw(layout_, context):
    st = _st(context)
    box_ = layout_.box()
    box_.label(text='Cylinder')
    box_.row(align=True).prop(st, 'shape', expand=True)
    box_.prop(st, 'overall', slider=False)                 # 0.24.324 every length at once
    c = box_.column(align=True)
    for k in ('length', 'width'):
        c.prop(st, k)
    if st.shape == 'SQUARE':
        c.prop(st, 'depth')
        c.prop(st, 'corner')
    c = box_.column(align=True)
    c.label(text='Proportions')
    for k in ('body_share', 'rod_ratio', 'cap_ratio', 'cap_flare'):
        c.prop(st, k, slider=True)
    r = box_.row(align=True)
    r.prop(st, 'rod_shape', expand=True)
    box_.prop(st, 'body_bolts')
    box_.prop(st, 'link_ends', toggle=True, icon='LINKED' if st.link_ends else 'UNLINKED')   # 0.24.324
    for end, label in (('rear', 'Rear Mount'), ('front', 'Rod End Mount')):
        b = box_.box()
        r_ = b.row()
        r_.label(text=label)
        if st.link_ends:
            r_.label(text='', icon='LINKED')
        b.row(align=True).prop(st, f'{end}_type', expand=True)
        if getattr(st, f'{end}_type') != 'NONE':
            c = b.column(align=True)
            for k in ('size', 'thick', 'hole'):
                c.prop(st, f'{end}_{k}', text=('Size', 'Thickness', 'Pin Hole')[('size', 'thick', 'hole').index(k)])
            c.prop(st, f'{end}_bolt', text='Bolt')
            c = b.column(align=True)
            c.prop(st, f'{end}_bracket', text='Bracket (the other side of the hinge)')
            if getattr(st, f'{end}_bracket'):
                b.row(align=True).prop(st, f'{end}_bstyle', expand=True)
                c = b.column(align=True)
                if getattr(st, f'{end}_bstyle') == 'ARM':
                    c.prop(st, f'{end}_arm_len', text='Arm Length')
                    c.prop(st, f'{end}_arm_t', text='Arm Thickness')
                    c.prop(st, f'{end}_arm_w', text='Arm Width')
                    c.prop(st, f'{end}_arm_turn', text='Arm Turn')
                else:
                    c.prop(st, f'{end}_base', text='Base Plate')
                    c.prop(st, f'{end}_base_t', text='Plate Thickness')
    c = box_.column(align=True)
    c.prop(st, 'hinge_gap')
    c.prop(st, 'bracket_bolts')
    b = box_.box()
    b.prop(st, 'spring')
    if st.spring:
        c = b.column(align=True)
        b.row(align=True).prop(st, 'spring_place', expand=True)
        c = b.column(align=True)
        for k in ('spring_coils', 'spring_wire', 'spring_size'):
            c.prop(st, k, slider=k != 'spring_coils')
        if st.spring_place == 'BODY':
            c.prop(st, 'spring_seat', slider=True)
        b.row(align=True).prop(st, 'seat_style', expand=True)
        c = b.column(align=True)
        if st.seat_style == 'CASTLE':
            c.prop(st, 'seat_teeth')
        c.prop(st, 'cage_posts')
        if st.cage_posts:
            c.prop(st, 'cage_len')
    box_.prop(st, 'segments')
    box_.label(text='Click a surface, then another: a cylinder between them', icon='MOUSE_LMB')
    if PENDING['a'] is not None:
        r = box_.row(align=True)
        r.label(text='1st point picked: click the other end', icon='CHECKMARK')
        r.operator('mch.actuator_cancel', text='', icon='X')
    box_.operator('mch.actuator_add', icon='MESH_CYLINDER')
    act = getattr(context, 'active_object', None)
    if act is not None and act.select_get() and act_of(act):
        box_.label(text=f'{act_of(act)}: live - move its Rod along Z to extend it', icon='INFO')
        r = box_.row(align=True)
        r.operator('mch.actuator_pick', icon='IMPORT')
        r.operator('mch.actuator_plain', icon='CHECKMARK')
    else:
        box_.label(text='Select a cylinder: the sliders change it', icon='INFO')


# --- 0.24.312 two clicks: a cylinder between two surfaces, its brackets on them ------------------------------------
# (user: "이 실린더도 내가 근육 만든 거처럼 양 끝 찍으면 저 경첩 바닥면이 붙어서 나오면 편하겠네")

PENDING = {'a': None}           # the first click: (location, normal, the mesh's name)


def reach(p, end):
    """From the pin to the outside of its bracket's base plate / arm (what lies on the surface)."""
    if p[f'{end}_type'] == 'NONE':
        return 0.0
    size = p[f'{end}_size']
    if not bracket_on(p, end):
        return size * 0.5
    nb = size * 0.75
    if p.get(f'{end}_bstyle', 'PLATE') == 'BARE':           # 0.24.324 the ears' foot (their neck's end)
        return nb + size * 0.05
    if p.get(f'{end}_bstyle', 'PLATE') == 'ARM':
        return nb + max(p.get(f'{end}_arm_t', size * 0.45), 1e-4)
    return nb + max(p.get(f'{end}_base_t', size * 0.15), 1e-4)


def _frame(origin, x, z):
    x = Vector(x).normalized()
    z = Vector(z).normalized()
    y = z.cross(x).normalized()
    x = y.cross(z).normalized()
    return Matrix(((x.x, y.x, z.x, origin.x), (x.y, y.y, z.y, origin.y), (x.z, y.z, z.z, origin.z), (0, 0, 0, 1)))


GLUE = 'mch_act_glue'           # on the body: the two surface points it was clicked between (in their meshes' space)


def _glue_points(context, glue):
    """The glue's points now (world): [(location, normal, mesh or None)] x 2 - they follow their meshes."""
    out = []
    for key in ('a', 'b'):
        name, loc, nrm = glue[key]
        t = context.scene.objects.get(name) if name else None
        if t is not None:
            mw = t.matrix_world
            out.append((mw @ Vector(loc), (mw.to_3x3().inverted_safe().transposed() @ Vector(nrm)).normalized(), t))
        else:
            out.append((Vector(loc), Vector(nrm).normalized(), None))
    return out


def glue_frame(p, a, b):
    """Where the pins go between the surface points ``a``, ``b`` and the pin axis: (pa, pb, x, z) or None."""
    la, na = Vector(a[0]), Vector(a[1]).normalized()
    lb, nb_ = Vector(b[0]), Vector(b[1]).normalized()
    pa = la + na * reach(p, 'rear')
    pb = lb + nb_ * reach(p, 'front')
    d = pb - pa
    if d.length < 1e-5:
        return None
    z = d.normalized()
    xa, xb = na.cross(z), nb_.cross(z)
    if xa.length < 1e-6 and xb.length < 1e-6:
        x = z.orthogonal()
    else:
        if xa.dot(xb) < 0:
            xb = -xb
        x = xa + xb
        if x.length < 1e-6:
            x = xa if xa.length > xb.length else xb
    x = (x - z * x.dot(z)).normalized()
    return pa, pb, x, z


def apply_glue(out, a, b, fr):
    """The body at the rear pin along the cylinder, each bracket turned flat onto its surface (a child of it)."""
    pa, pb, x, z = fr
    body = out['BODY']
    body.matrix_world = _frame(pa, x, z)
    for end, part, (loc, n, tgt), pin in (('rear', 'BRACKET_REAR', a, pa), ('front', 'BRACKET_FRONT', b, pb)):
        br = out.get(part)
        if br is None or br.mode == 'EDIT':
            continue
        n = Vector(n)
        n2 = (n - x * n.dot(x))
        n2 = n2.normalized() if n2.length > 1e-6 else (-z if end == 'rear' else z)
        mw = _frame(pin, x, n2 if end == 'rear' else -n2)  # (its away side - the plate - onto the surface)
        if tgt is not None and br.parent is not tgt:
            br.parent = tgt
        if tgt is not None:                                 # (a scaled / turned mesh: its inverse in the parent
            br.matrix_parent_inverse = tgt.matrix_world.inverted_safe()    # inverse - no shear in the bracket)
            br.matrix_basis = mw
        else:
            br.parent = None
            br.matrix_basis = mw
        br[AUTO] = []                                       # (placed on the mech)


def place_between(context, a, b, p=None):
    """0.24.312 a cylinder from the surface point ``a`` to ``b`` (each (location, normal, mesh or None)): its pins off
    the surfaces by its brackets' height, its pin axis square to the cylinder and both normals, each bracket turned to
    lie flat on its surface (a child of that mesh).  Remembered: a slider change glues it again (a bracket higher or
    lower - the pins move, the plates stay on the surfaces).  Returns the actuator's id and parts."""
    st = _st(context)
    p = dict(p or numbers(st))
    fr = glue_frame(p, a, b)
    if fr is None:
        return None, {}
    p['L'] = (fr[1] - fr[0]).length
    _BUSY[0] = True
    try:
        st.length = p['L']                                 # (the window shows its length)
    finally:
        _BUSY[0] = False
    aid, out = build(context, p)
    glue = {}
    for key, (loc, n, t) in (('a', a), ('b', b)):
        if t is not None:
            mi = t.matrix_world.inverted_safe()
            glue[key] = [t.name, list(mi @ Vector(loc)), list((t.matrix_world.to_3x3().transposed() @ Vector(n)).normalized())]
        else:
            glue[key] = ['', list(Vector(loc)), list(Vector(n).normalized())]
    out['BODY'][GLUE] = json.dumps(glue)
    apply_glue(out, a, b, fr)
    return aid, out


def _ray(context, event):
    from bpy_extras import view3d_utils
    xy = (event.mouse_region_x, event.mouse_region_y)
    o = view3d_utils.region_2d_to_origin_3d(context.region, context.region_data, xy)
    d = view3d_utils.region_2d_to_vector_3d(context.region, context.region_data, xy)
    dg = context.evaluated_depsgraph_get()
    hit, loc, nrm, _i, hob, _m = context.scene.ray_cast(dg, o, d)
    if not hit or hob is None:
        return None, None, None, d
    real = bpy.data.objects.get(hob.name)
    if nrm.dot(d) > 0:
        nrm = -nrm
    return real, loc, nrm.normalized(), d


class MCH_OT_actuator_click(bpy.types.Operator):
    """Click a surface, then another: a cylinder between them, its brackets on them.  A click on a cylinder selects
    it (Shift: add to the selection)"""
    bl_idname = 'mch.actuator_click'
    bl_label = 'Cylinder Between Two Points'
    bl_options = {'REGISTER', 'UNDO'}
    extend: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        ob, loc, nrm, _d = _ray(context, event)
        part = act_of(ob) or (ob is not None and ob.get(PART))
        if ob is None or part:                              # (a cylinder: select it; nothing: deselect)
            if not self.extend:
                for o in context.selected_objects:
                    o.select_set(False)
            if ob is not None:
                aid = act_of(ob)
                for o in (parts_of(context.scene, aid).values() if aid and not self.extend else [ob]):
                    if o.type == 'MESH':
                        o.select_set(True)
                context.view_layer.objects.active = ob
            PENDING['a'] = None
            _header(context, None)
            return {'FINISHED'}
        try:
            from . import screw_stamp
            nrm = screw_stamp.area_normal(context, ob, loc, nrm, _st(context).width * 0.5)
        except (ImportError, AttributeError, RuntimeError):
            pass
        if PENDING['a'] is None:
            PENDING['a'] = (tuple(loc), tuple(nrm), ob.name)
            _header(context, 'Cylinder: now click where its other end goes (Esc: start over)')
            return {'FINISHED'}
        a = PENDING['a']
        PENDING['a'] = None
        _header(context, None)
        ta = context.scene.objects.get(a[2])
        aid, out = place_between(context, (a[0], a[1], ta), (loc, nrm, ob))
        if not out:
            self.report({'WARNING'}, 'Cylinder: the two points are too close')
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in out.values():
            if o.type == 'MESH':
                o.select_set(True)
        context.view_layer.objects.active = out['BODY']
        self.report({'INFO'}, f'{aid}: between the two points - the sliders change it while selected')
        return {'FINISHED'}


class MCH_OT_actuator_cancel(bpy.types.Operator):
    """Forget the first point clicked"""
    bl_idname = 'mch.actuator_cancel'
    bl_label = 'Start Over'
    bl_options = {'INTERNAL'}

    def execute(self, context):
        PENDING['a'] = None
        _header(context, None)
        return {'FINISHED'}


def _header(context, text):
    try:
        if context.area is not None:
            context.area.header_text_set(text)
    except (AttributeError, RuntimeError, TypeError):
        pass


class MCH_TOOL_actuator(bpy.types.WorkSpaceTool):
    """0.24.308 Cylinder (actuator): its own tool"""
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.cylinder_gen'
    bl_label = 'Cylinder'
    bl_description = ('Click a surface, then another: a cylinder between them, its brackets on them (or Summon '
                      'Cylinder at the 3D cursor) - select it and the sliders change it; move its Rod along Z to '
                      'extend it')
    bl_icon = 'ops.generic.select'
    bl_widget = None
    bl_keymap = (('mch.actuator_click', {'type': 'LEFTMOUSE', 'value': 'CLICK'}, None),      # 0.24.312 two clicks
                 ('mch.actuator_click', {'type': 'LEFTMOUSE', 'value': 'CLICK', 'shift': True},
                  {'properties': [('extend', True)]}),
                 ('mch.actuator_cancel', {'type': 'ESC', 'value': 'PRESS'}, None))

    def draw_settings(context, layout, tool):
        region = getattr(context, 'region', None)
        if region is not None and region.type == 'TOOL_HEADER':
            return


CLASSES = (MCH_PG_Actuator, MCH_OT_actuator_add, MCH_OT_actuator_pick, MCH_OT_actuator_plain, MCH_OT_actuator_click,
           MCH_OT_actuator_cancel)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_actuator = bpy.props.PointerProperty(type=MCH_PG_Actuator)
    try:
        bpy.utils.register_tool(MCH_TOOL_actuator, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_actuator)
    except (ValueError, RuntimeError, KeyError):
        pass
    try:
        del bpy.types.Scene.mch_actuator
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
