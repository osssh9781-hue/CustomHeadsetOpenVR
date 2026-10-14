"""Station Primitive engine (Advanced Parametric Primitive, Phase 1).

A primitive = one cross-section PROFILE kind swept along a chain of STATIONS.

* Station 0 is the start.  Every following station i describes the segment that
  leads to it: first a bend (angle / direction / radius; radius 0 = hard fold),
  then a straight run of ``length``.  Bends are LOCAL: each segment starts from
  the direction the previous one ended in, so changing station 1 swings every
  later segment with it while their own values stay untouched.  A station can
  use WORLD direction instead (absolute yaw / pitch).
* Each station carries its own profile values (left / right width, top /
  bottom height, left / right thickness factor, left / right corner radius,
  ridge height / width / offset, twist).  Values blend between stations
  (Linear, Smooth or Step).
* Every ring of every profile has the same vertex count for a given kind and
  resolution, so rings are bridged directly; coincident points from collapsed
  corners are merged afterwards.
* Segments are added automatically where they are needed (bend angle, twist,
  smooth blending); straight linear runs stay one segment.

Pure geometry (mathutils only); ``build`` returns vertices / faces / warnings.
"""
import math

from mathutils import Matrix, Vector

KINDS = ('ROUND', 'CAPSULE', 'BOX', 'ROUNDED', 'CHAMFER', 'RIBBON', 'POLYGON', 'ARC', 'NGON')
RIDGES = ('NONE', 'CREASE', 'RAISED', 'BOX', 'ROUND', 'GROOVE', 'DOUBLE')
CAPS = ('FLAT', 'ROUND', 'POINT', 'OPEN')
QUALITY_DEG = {'DRAFT': 15.0, 'NORMAL': 8.0, 'FINE': 4.0}
STATION_KEYS = ('length', 'bend_angle', 'bend_dir', 'bend_up', 'bend_side', 'bend_radius', 'twist', 'world', 'yaw',
                'pitch',
                'width_l', 'width_r', 'height_top', 'height_bot', 'thick_l', 'thick_r',
                'corner_l', 'corner_r', 'ridge_h', 'ridge_w', 'ridge_offset', 'interp', 'bend_style', 'profile')
BEND_STYLES = ('AUTO', 'FOLD', 'TIGHT', 'BAND')     # AUTO: radius 0 = fold, > 0 = band
BLEND_KEYS = ('width_l', 'width_r', 'height_top', 'height_bot', 'thick_l', 'thick_r', 'corner_l', 'corner_r',
              'ridge_h', 'ridge_w', 'ridge_offset')

DEFAULT_STATION = dict(length=1.0, bend_angle=0.0, bend_dir=0.0, bend_up=0.0, bend_side=0.0, bend_radius=0.0,
                       twist=0.0, world=False,
                       yaw=0.0, pitch=0.0, width_l=0.5, width_r=0.5, height_top=0.05, height_bot=0.05,
                       thick_l=1.0, thick_r=1.0, corner_l=0.02, corner_r=0.02, ridge_h=0.0, ridge_w=0.15,
                       ridge_offset=0.0, interp='LINEAR', bend_style='AUTO', profile='INHERIT')


def station(**kw):
    s = dict(DEFAULT_STATION)
    s.update(kw)
    return s


# =============================================================================
# Profile
# =============================================================================


def _cos_pattern(n, wr, wl):
    """n x-positions from +wr to -wl, dense near both ends (round corners)."""
    out = []
    for i in range(n):
        c = math.cos(math.pi * i / (n - 1))
        out.append(wr * c if c >= 0 else wl * c)
    return out


def _ridge_points(kind, p, wl, wr):
    """[(x, f)] extra top points (f = ridge factor) that keep the ridge crisp."""
    o = max(-wl, min(wr, p['ridge_offset']))
    w = max(1e-4, p['ridge_w'])
    if kind == 'CREASE':
        return [(o, 1.0)]
    if kind in {'RAISED', 'ROUND'}:
        return [(o + w / 2, 0.0), (o, 1.0), (o - w / 2, 0.0)]
    if kind in {'BOX', 'GROOVE'}:
        return [(o + w / 2, 0.0), (o + w / 2, 1.0), (o - w / 2, 1.0), (o - w / 2, 0.0)]
    if kind == 'DOUBLE':
        s = w * 0.75
        return [(o + s + w / 4, 0.0), (o + s, 1.0), (o + s - w / 4, 0.0),
                (o - s + w / 4, 0.0), (o - s, 1.0), (o - s - w / 4, 0.0)]
    return []


def _ridge_f(kind, p, x, wl, wr):
    o = p['ridge_offset']
    w = max(1e-4, p['ridge_w'])
    d = x - o
    if kind == 'CREASE':
        span = (wr - o) if d >= 0 else (o + wl)
        return max(0.0, 1.0 - abs(d) / max(span, 1e-6))
    if kind == 'RAISED':
        return max(0.0, 1.0 - abs(d) / (w / 2))
    if kind == 'ROUND':
        return math.cos(min(1.0, abs(d) / (w / 2)) * math.pi / 2) ** 2 if abs(d) < w / 2 else 0.0
    if kind in {'BOX', 'GROOVE'}:
        return 1.0 if abs(d) < w / 2 - 1e-9 else 0.0
    if kind == 'DOUBLE':
        s = w * 0.75
        return max(0.0, 1.0 - abs(abs(d) - s) / (w / 4))
    return 0.0


def _corner_y(kind, x, w, h, r, sides):
    """Upper boundary height (>= 0) at |x| <= w for one side (w = that side's half width)."""
    ax = abs(x)
    if kind == 'POLYGON':
        # regular n-gon (vertex at the top when n is odd, flat top when even), x scaled by
        # this side's half width, y by the height: height of the upper chain at x.
        n = max(3, sides)
        off = math.pi / 2 if n % 2 else math.pi / 2 - math.pi / n
        pts = [(math.cos(off + 2 * math.pi * k / n), math.sin(off + 2 * math.pi * k / n)) for k in range(n)]
        u = max(-1.0, min(1.0, ax / max(w, 1e-9)))
        best = 0.0
        for k in range(n):
            (x1, y1), (x2, y2) = pts[k], pts[(k + 1) % n]
            if (x1 - u) * (x2 - u) <= 0 and abs(x2 - x1) > 1e-12:
                best = max(best, y1 + (y2 - y1) * (u - x1) / (x2 - x1))
        top = max(y for _x, y in pts)
        return max(0.0, best / top) * h
    if kind == 'ROUND':
        rx, ry = w, h
    elif kind == 'CAPSULE':
        rx = ry = min(w, h)
    elif kind == 'BOX':
        return h
    else:  # ROUNDED, CHAMFER, RIBBON
        rx, ry = min(r, w), min(r, h)
    if rx <= 1e-9 or ry <= 1e-9 or ax <= w - rx:
        return h
    t = (ax - (w - rx)) / rx                     # 0 at corner start .. 1 at the side
    if kind == 'CHAMFER':
        return h - ry * t
    return h - ry + ry * math.sqrt(max(0.0, 1.0 - t * t))


def _poly_breaks(sides, wl, wr):
    """x of the polygon corners on the upper / lower chain (inner corners only)."""
    n = max(3, sides)
    off = math.pi / 2 if n % 2 else math.pi / 2 - math.pi / n
    top, bot = [], []
    for k in range(n):
        a = off + 2 * math.pi * k / n
        c, sn = math.cos(a), math.sin(a)
        if abs(c) > 1 - 1e-9:
            continue
        x = (wr if c > 0 else wl) * c
        (top if sn > 1e-9 else bot if sn < -1e-9 else []).append(x)
    return top, bot


def _arc_point(x, w, s):
    """Outer surface of a curved plate at x: (y, unit normal).  Crown s at x = 0,
    edges at +-w on y = 0.  Up to a half circle it is a true circular arc (no
    tight spots, so the thickness never folds); taller crowns use an ellipse."""
    s = max(s, 1e-6)
    ax = min(abs(x), w)
    sg = 1.0 if x >= 0 else -1.0
    if s <= w:
        R = (w * w + s * s) / (2 * s)
        cy = s - R
        y = cy + math.sqrt(max(0.0, R * R - ax * ax))
        n = (sg * ax / R, (y - cy) / R)
    else:
        u = ax / w
        y = s * math.sqrt(max(0.0, 1 - u * u))
        nx, ny = (ax / (w * w), y / (s * s)) if y > 1e-12 else (1.0, 0.0)
        ln = math.hypot(nx, ny)
        n = (sg * nx / ln, ny / ln)
    return y, n


def _arc_loop(p, top_pts, bot_extra, res, ridge, rh, wl, wr):
    """Curved plate (armor shell) cross-section: outer arc right -> left, then
    the inner arc (offset by the thickness along the normal) left -> right.
    Height Top = crown height, Height Bottom = plate thickness, Left / Right
    Thickness = factors at the two edges."""
    s = max(1e-4, p['height_top'])
    t0 = max(1e-4, p['height_bot'])

    def thick(x):
        tt = (x + wl) / (wl + wr)
        return t0 * (p['thick_l'] + (p['thick_r'] - p['thick_l']) * tt)

    loop = []
    for x, f in top_pts:
        w = wr if x >= 0 else wl
        y, _n = _arc_point(x, w, s)
        if ridge != 'NONE':
            ff = _ridge_f(ridge, p, x, wl, wr) if f is None else f
            y += rh * ff
        loop.append((x, y))
    n_bot = max(5, res * 2 + 1)
    for x in sorted(_cos_pattern(n_bot, wr, wl) + bot_extra):
        w = wr if x >= 0 else wl
        y, (nx, ny) = _arc_point(x, w, s)
        t = thick(x)
        loop.append((x - nx * t, y - ny * t))
    return loop


def ngon_loop(p, sides):
    """0.15 Polygon Prism profile: exactly ``sides`` corners (flat top when even),
    x scaled by the left / right width, y by top / bottom.  No extra points, so
    folds and bands stay clean at any number of sides."""
    n = max(3, int(sides))
    off = math.pi / 2 if n % 2 else math.pi / 2 - math.pi / n
    wl, wr = max(1e-4, p['width_l']), max(1e-4, p['width_r'])
    ht, hb = max(1e-4, p['height_top']), max(1e-4, p['height_bot'])
    loop = []
    for k in range(n):
        a = off + 2 * math.pi * k / n
        c, sn = math.cos(a), math.sin(a)
        loop.append((c * (wr if c >= 0 else wl), sn * (ht if sn >= 0 else hb)))
    return loop


def ring_loop(kind, p, res=12, ridge='NONE', sides=6):
    """Profile of one ring: the station's own kind, or a morph between two kinds."""
    if kind == 'NGON':                    # its own vertex layout: no per-station profile change
        return ngon_loop(p, sides)
    ka = p.get('_ka') or (p['profile'] if p.get('profile', 'INHERIT') != 'INHERIT' else kind)
    kb = p.get('_kb') or ka
    t = p.get('_kt', 0.0)
    la = profile_loop(ka, p, res, ridge, sides)
    if kb == ka or t <= 0.0:
        return la
    lb = profile_loop(kb, p, res, ridge, sides)
    if t >= 1.0:
        return lb
    return [(x0 + (x1 - x0) * t, y0 + (y1 - y0) * t) for (x0, y0), (x1, y1) in zip(la, lb)]


def profile_loop(kind, p, res=12, ridge='NONE', sides=6):
    """Closed CCW loop [(x, y)] in the profile plane (x = right, y = up).

    Same vertex count for a given (kind, res, ridge) whatever the values, so
    rings of different stations bridge directly."""
    wl, wr = max(1e-4, p['width_l']), max(1e-4, p['width_r'])
    ht, hb = max(0.0, p['height_top']), max(0.0, p['height_bot'])
    if kind == 'RIBBON':
        ht, hb = min(ht, 0.25 * (wl + wr)), min(hb, 0.25 * (wl + wr))
    n_top = max(5, res * 2 + 1)
    tops = [(x, None) for x in _cos_pattern(n_top, wr, wl)]
    extra = _ridge_points(ridge, p, wl, wr) if ridge != 'NONE' else []
    top_poly, bot_poly = _poly_breaks(sides, wl, wr)
    extra += [(x, None) for x in top_poly]           # always present: every kind has the same count
    pts = sorted(tops + extra, key=lambda q: -q[0])
    # keep box ridge walls in the right order (equal x: right side first goes up, left side down)
    for i in range(len(pts) - 1):
        a, b = pts[i], pts[i + 1]
        if abs(a[0] - b[0]) < 1e-12 and a[1] is not None and b[1] is not None:
            right_wall = a[0] > p['ridge_offset']
            if right_wall and a[1] > b[1] or (not right_wall) and a[1] < b[1]:
                pts[i], pts[i + 1] = b, a
    rh = p['ridge_h'] * (-1.0 if ridge == 'GROOVE' else 1.0)
    if kind == 'ARC':
        return _arc_loop(p, pts, bot_poly, res, ridge, rh, wl, wr)

    def scale(x):
        t = (x + wl) / (wl + wr)
        return p['thick_l'] + (p['thick_r'] - p['thick_l']) * t

    loop = []
    for x, f in pts:
        w = wr if x >= 0 else wl
        r = p['corner_r'] if x >= 0 else p['corner_l']
        y = _corner_y(kind, x, w, ht, r, sides) * scale(x)
        if ridge != 'NONE':
            ff = _ridge_f(ridge, p, x, wl, wr) if f is None else f
            y += rh * ff
        loop.append((x, y))
    n_bot = max(5, res * 2 + 1)
    for x in sorted(_cos_pattern(n_bot, wr, wl) + bot_poly):       # -wl .. +wr along the bottom
        w = wr if x >= 0 else wl
        r = p['corner_r'] if x >= 0 else p['corner_l']
        loop.append((x, -_corner_y(kind, x, w, hb, r, sides) * scale(x)))
    return loop


# =============================================================================
# Spine / stations
# =============================================================================


def _kind_of(st, kind):
    return st['profile'] if st.get('profile', 'INHERIT') != 'INHERIT' else kind


def _blend(a, b, t, mode, kind='ROUNDED'):
    if mode == 'SMOOTH':
        t = t * t * (3 - 2 * t)
    elif mode == 'STEP':
        t = 0.0 if t < 1.0 else 1.0
    out = dict(b)
    for k in BLEND_KEYS:
        out[k] = a[k] + (b[k] - a[k]) * t
    out['_ka'], out['_kb'], out['_kt'] = _kind_of(a, kind), _kind_of(b, kind), t
    return out


def _rot(axis, angle):
    return Matrix.Rotation(angle, 3, axis)


class Frame:
    __slots__ = ('P', 'X', 'T', 'Z')

    def __init__(self, P, X, T, Z):
        self.P, self.X, self.T, self.Z = P, X, T, Z

    def copy(self):
        return Frame(self.P.copy(), self.X.copy(), self.T.copy(), self.Z.copy())

    def rotated(self, R, pivot=None):
        P = self.P if pivot is None else pivot + R @ (self.P - pivot)
        return Frame(P.copy(), (R @ self.X).normalized(), (R @ self.T).normalized(), (R @ self.Z).normalized())


def _profile_extent(loop, dir_xy):
    """Largest extent of the profile toward the bend's inside direction."""
    return max(x * dir_xy[0] + y * dir_xy[1] for x, y in loop)


def build(spec):
    """spec: kind, res, ridge, sides, quality, seg_mode ('AUTO'|'MANUAL'), seg_bend, seg_run,
    cap_start, cap_end, cap_len, stations[list of station dicts].
    Returns dict(verts, faces, warnings, frames, ring_count, sharp_rings)."""
    kind = spec.get('kind', 'ROUNDED')
    res = int(spec.get('res', 12))
    ridge = spec.get('ridge', 'NONE')
    sides = int(spec.get('sides', 6))
    q = QUALITY_DEG.get(spec.get('quality', 'NORMAL'), 8.0)
    manual = spec.get('seg_mode', 'AUTO') == 'MANUAL'
    seg_bend, seg_run = max(1, int(spec.get('seg_bend', 8))), max(1, int(spec.get('seg_run', 1)))
    sts = [dict(DEFAULT_STATION, **s) for s in spec['stations']]
    warnings = []
    if not sts:
        raise ValueError('A Station Primitive needs at least one station')
    frame = Frame(Vector((0, 0, 0)), Vector((1, 0, 0)), Vector((0, 1, 0)), Vector((0, 0, 1)))
    rings = []                       # (frame, params, miter(dir_vec, scale) or None)
    station_frames = [frame.copy()]
    rings.append((frame.copy(), sts[0], None))
    for i in range(1, len(sts)):
        a, b = sts[i - 1], sts[i]
        mode = b['interp']
        angle = math.radians(b['bend_angle'])
        if b['world']:
            yaw, pitch = math.radians(b['yaw']), math.radians(b['pitch'])
            d = Vector((math.sin(yaw) * math.cos(pitch), math.cos(yaw) * math.cos(pitch), math.sin(pitch)))
            dot = max(-1.0, min(1.0, frame.T.dot(d)))
            angle = math.acos(dot)
            inside = (d - frame.T * dot)
            inside = inside.normalized() if inside.length > 1e-9 else frame.Z.copy()
        else:
            # 0.15: Up / Down (bend_up, toward +Z) and Left / Right (bend_side, toward +X) at the same
            # station, added to the older angle + direction pair: one bend about the combined axis
            phi = math.radians(b['bend_dir'])
            up = b['bend_angle'] * math.cos(phi) + b.get('bend_up', 0.0)
            side = b['bend_angle'] * math.sin(phi) + b.get('bend_side', 0.0)
            angle = math.radians(math.hypot(up, side))
            if angle > 1e-9:
                inside = (frame.Z * up + frame.X * side).normalized()
            else:
                inside = (frame.Z * math.cos(phi) + frame.X * math.sin(phi)).normalized()
        if angle < 0:
            angle, inside = -angle, -inside
        style = b.get('bend_style', 'AUTO')
        R = max(0.0, b['bend_radius'])
        if style == 'FOLD':
            R = 0.0
        elif style == 'TIGHT' and angle > 1e-6:
            # sheet-metal look: the smallest radius that does not fold the inside onto itself
            loop_t = ring_loop(kind, _blend(a, b, 0.0, mode, kind), res, ridge, sides)
            R = max(_profile_extent(loop_t, (inside.dot(frame.X), inside.dot(frame.Z))) * 1.02, 1e-4)
        elif style == 'BAND' and R <= 1e-6:
            R = 0.25
        arc_len = R * angle
        total = arc_len + max(0.0, b['length'])
        travelled = 0.0
        if angle > 1e-6:
            axis = frame.T.cross(inside).normalized()
            if R <= 1e-6:
                # hard fold: one mitred ring on the bisector
                half = frame.rotated(_rot(axis, angle / 2))
                dir_m = (_rot(axis, angle / 2) @ inside).normalized()
                s = 1.0 / max(math.cos(angle / 2), 0.1)
                if math.cos(angle / 2) < 0.1:
                    warnings.append(f'Station {i}: fold of {math.degrees(angle):.0f} deg is almost flat-back; '
                                    'the mitre is limited (use a bend radius)')
                rings.append((half, _blend(a, b, 0.0, mode, kind), (dir_m, s)))
                frame = frame.rotated(_rot(axis, angle))
            else:
                loop0 = ring_loop(kind, _blend(a, b, 0.0, mode, kind), res, ridge, sides)
                inside_xy = (inside.dot(frame.X), inside.dot(frame.Z))
                ext = _profile_extent(loop0, inside_xy)
                if R < ext * 0.999:
                    warnings.append(f'Station {i}: bend radius {R:.3g} is smaller than the profile on the inside '
                                    f'({ext:.3g}); raised to {ext * 1.05:.3g} to avoid self-intersection')
                    R = ext * 1.05
                    arc_len = R * angle
                    total = arc_len + max(0.0, b['length'])
                n = seg_bend if manual else max(2, math.ceil(math.degrees(angle) / q))
                centre = frame.P + inside * R
                start = frame.copy()
                for k in range(1, n + 1):
                    Rk = _rot(axis, angle * k / n)
                    fk = start.rotated(Rk, pivot=centre)
                    travelled = arc_len * k / n
                    rings.append((fk, _blend(a, b, travelled / total if total > 0 else 1.0, mode, kind), None))
                frame = start.rotated(_rot(axis, angle), pivot=centre)
        L = max(0.0, b['length'])
        twist = math.radians(b['twist'])
        step = mode == 'STEP'
        if L > 1e-9 or abs(twist) > 1e-9:
            if manual:
                n = seg_run
            else:
                n = 1
                if mode == 'SMOOTH':
                    n = max(n, 6 if q <= 8 else 4)
                if abs(twist) > 1e-6:
                    n = max(n, math.ceil(math.degrees(abs(twist)) / q))
            start = frame.copy()
            for k in range(1, n + 1):
                t = k / n
                fk = start.copy()
                fk.P = start.P + start.T * (L * t)
                Rt = _rot(start.T, twist * t)
                fk.X, fk.Z = (Rt @ start.X).normalized(), (Rt @ start.Z).normalized()
                frac = (travelled + L * t) / total if total > 0 else 1.0
                rings.append((fk, a if step else _blend(a, b, frac, mode, kind), None))
            frame = rings[-1][0].copy()
        if step:
            rings.append((frame.copy(), b, None))    # same place, new profile: a deliberate step face
        elif angle <= 1e-6 and L <= 1e-9 and abs(twist) <= 1e-9:
            rings.append((frame.copy(), b, None))
        station_frames.append(frame.copy())
    # ---- rings -> vertices
    verts, faces = [], []
    ring_idx = []
    for fr, p, miter in rings:
        loop = ring_loop(kind, p, res, ridge, sides)
        idx = []
        for x, y in loop:
            v = fr.X * x + fr.Z * y
            if miter is not None:
                dm, s = miter
                v = v + dm * (v.dot(dm) * (s - 1.0))
            idx.append(len(verts))
            verts.append(tuple(fr.P + v))
        ring_idx.append(idx)
    n = len(ring_idx[0])
    for r0, r1 in zip(ring_idx, ring_idx[1:]):
        for j in range(n):
            k = (j + 1) % n
            faces.append((r0[j], r0[k], r1[k], r1[j]))
    cap_len = spec.get('cap_len', 0.0)
    _cap(verts, faces, ring_idx[0], rings[0], spec.get('cap_start', 'FLAT'), cap_len, -1, kind, res, ridge, sides)
    _cap(verts, faces, ring_idx[-1], rings[-1], spec.get('cap_end', 'FLAT'), cap_len, 1, kind, res, ridge, sides)
    if len(rings) < 2:
        warnings.append('Only one station: add a station to give the primitive length')
    return dict(verts=verts, faces=faces, warnings=warnings, frames=station_frames, ring_count=len(rings),
                ring_size=n)


def _cap(verts, faces, ring, ring_data, mode, cap_len, sign, kind, res, ridge, sides):
    fr, p, _m = ring_data
    if mode == 'OPEN':
        return
    if mode == 'FLAT' or cap_len <= 1e-9:
        faces.append(tuple(reversed(ring)) if sign < 0 else tuple(ring))
        return
    loop = ring_loop(kind, p, res, ridge, sides)
    k = max(2, res // 2) if mode == 'ROUND' else 1
    prev = ring
    for step in range(1, k):
        th = math.pi / 2 * step / k
        s = math.cos(th) if mode == 'ROUND' else 1 - step / k
        adv = cap_len * (math.sin(th) if mode == 'ROUND' else step / k)
        idx = []
        for x, y in loop:
            idx.append(len(verts))
            verts.append(tuple(fr.P + fr.T * (adv * sign) + fr.X * (x * s) + fr.Z * (y * s)))
        for j in range(len(idx)):
            jj = (j + 1) % len(idx)
            f = (prev[j], prev[jj], idx[jj], idx[j])
            faces.append(f if sign > 0 else tuple(reversed(f)))
        prev = idx
    apex = len(verts)
    cy = sum(y for _x, y in loop) / len(loop) * 0.0
    verts.append(tuple(fr.P + fr.T * (cap_len * sign) + fr.Z * cy))
    for j in range(len(prev)):
        jj = (j + 1) % len(prev)
        f = (prev[j], prev[jj], apex)
        faces.append(f if sign > 0 else tuple(reversed(f)))


# =============================================================================
# Presets (scenarios of the request)
# =============================================================================


def preset(name):
    """Spec dicts for the request's scenarios."""
    if name == 'PANEL':
        return dict(kind='ROUNDED', res=8, ridge='NONE', cap_start='FLAT', cap_end='FLAT',
                    stations=[station(), station(length=1.0)])
    if name == 'PRISM':               # 0.15: square prism; Sides slider -> towards a cylinder
        r = math.sqrt(0.5)                # square of side 1
        base = dict(width_l=r, width_r=r, height_top=r, height_bot=r, corner_l=0.0, corner_r=0.0)
        return dict(kind='NGON', sides=4, res=2, ridge='NONE', cap_start='FLAT', cap_end='FLAT',
                    stations=[station(**base), station(length=1.0, **base)])
    if name == 'MULTI_BEND':          # scenario B: 30 deg, then +45 deg, thicker one side, box ridge
        return dict(kind='CHAMFER', res=8, ridge='BOX', cap_start='FLAT', cap_end='FLAT',
                    stations=[station(ridge_h=0.03, ridge_w=0.18),
                              station(length=0.6, ridge_h=0.03, ridge_w=0.18),
                              station(length=0.6, bend_angle=30, ridge_h=0.03, ridge_w=0.18),
                              station(length=0.5, bend_angle=45, thick_r=1.8, ridge_h=0.03, ridge_w=0.18)])
    if name == 'WRAP':                # scenario C: ribbon wrapped > 180 deg (tyre cover)
        return dict(kind='RIBBON', res=6, ridge='NONE', cap_start='FLAT', cap_end='FLAT',
                    stations=[station(width_l=0.35, width_r=0.35, height_top=0.03, height_bot=0.03, corner_l=0.03,
                                      corner_r=0.03),
                              station(length=0.0, bend_angle=200, bend_radius=0.8, width_l=0.35, width_r=0.35,
                                      height_top=0.03, height_bot=0.03, corner_l=0.03, corner_r=0.03)])
    if name == 'TEARDROP':            # scenario A: round front, long tapered pointed back, raised ridge
        base = dict(height_top=0.42, height_bot=0.34, corner_l=1, corner_r=1, ridge_h=0.035, ridge_w=0.12,
                    interp='SMOOTH')
        return dict(kind='ROUND', res=12, ridge='RAISED', cap_start='ROUND', cap_end='POINT', cap_len=0.45,
                    stations=[station(width_l=0.42, width_r=0.42, **base),
                              station(length=0.5, width_l=0.46, width_r=0.46, **base),
                              station(length=0.9, width_l=0.16, width_r=0.16, **dict(base, height_top=0.16,
                                                                                         height_bot=0.1))])
    if name == 'AUTOMOTIVE':          # scenario D (manual version): asymmetric curved body panel
        return dict(kind='ROUNDED', res=10, ridge='CREASE', cap_start='FLAT', cap_end='FLAT',
                    stations=[station(width_l=0.7, width_r=0.4, height_top=0.04, height_bot=0.04, thick_l=1.0,
                                      thick_r=0.6, ridge_h=0.03, interp='SMOOTH'),
                              station(length=0.8, bend_angle=12, bend_radius=1.5, width_l=0.8, width_r=0.45,
                                      height_top=0.04, height_bot=0.04, thick_r=0.6, ridge_h=0.04, interp='SMOOTH'),
                              station(length=0.7, bend_angle=-18, bend_radius=1.2, width_l=0.55, width_r=0.3,
                                      height_top=0.04, height_bot=0.04, thick_r=0.5, ridge_h=0.02, interp='SMOOTH')])
    if name == 'DUCT':
        base = dict(width_l=0.18, width_r=0.18, height_top=0.18, height_bot=0.18)
        return dict(kind='ROUND', res=8, ridge='NONE', cap_start='OPEN', cap_end='OPEN',
                    stations=[station(**base), station(length=0.6, **base),
                              station(length=0.5, bend_angle=90, bend_radius=0.4, bend_dir=90, **base),
                              station(length=0.6, bend_angle=60, bend_radius=0.35, **base)])
    if name in ARMOR_PRESETS:
        return armor_preset(name)
    raise KeyError(name)


ARMOR_PRESETS = ('SHOULDER', 'UPPER_LIMB', 'LOWER_LIMB', 'TORSO', 'HELMET')
PRESETS = ('PANEL', 'PRISM', 'MULTI_BEND', 'WRAP', 'TEARDROP', 'AUTOMOTIVE', 'DUCT') + ARMOR_PRESETS


def _armor(**kw):
    # curved plate: width = half span, height_top = crown, height_bot = thickness (metres, human scale)
    return station(**dict(dict(height_bot=0.012, corner_l=0.0, corner_r=0.0, ridge_w=0.03, interp='SMOOTH'), **kw))


def armor_preset(name):
    if name == 'SHOULDER':        # shoulder pauldron / knee guard: a cap that rolls over the joint
        return dict(kind='ARC', res=10, ridge='RAISED', cap_start='FLAT', cap_end='FLAT', stations=[
            _armor(width_l=0.11, width_r=0.11, height_top=0.06, ridge_h=0.008),
            _armor(length=0.05, width_l=0.15, width_r=0.15, height_top=0.09, ridge_h=0.012),
            _armor(length=0.06, bend_angle=40, bend_dir=180, bend_style='BAND', bend_radius=0.12,
                   width_l=0.17, width_r=0.17, height_top=0.11, ridge_h=0.014),
            _armor(length=0.05, bend_angle=35, bend_dir=180, bend_style='BAND', bend_radius=0.1,
                   width_l=0.15, width_r=0.15, height_top=0.1, ridge_h=0.01)])
    if name == 'UPPER_LIMB':      # upper arm / thigh: long shell, wider at the top, slight bend
        return dict(kind='ARC', res=10, ridge='DOUBLE', cap_start='FLAT', cap_end='FLAT', stations=[
            _armor(width_l=0.085, width_r=0.085, height_top=0.075, ridge_h=0.006, ridge_w=0.04),
            _armor(length=0.12, width_l=0.08, width_r=0.08, height_top=0.072, ridge_h=0.006, ridge_w=0.04),
            _armor(length=0.16, bend_angle=6, bend_dir=180, width_l=0.068, width_r=0.068, height_top=0.062,
                   ridge_h=0.005, ridge_w=0.035)])
    if name == 'LOWER_LIMB':      # forearm / shin: flared at the joint, tapered, small cuff at the end
        return dict(kind='ARC', res=10, ridge='RAISED', cap_start='FLAT', cap_end='FLAT', stations=[
            _armor(width_l=0.085, width_r=0.085, height_top=0.07, ridge_h=0.01),
            _armor(length=0.06, width_l=0.075, width_r=0.075, height_top=0.065, ridge_h=0.009),
            _armor(length=0.2, width_l=0.055, width_r=0.055, height_top=0.05, ridge_h=0.007),
            _armor(length=0.035, width_l=0.065, width_r=0.065, height_top=0.058, ridge_h=0.006)])
    if name == 'TORSO':           # chest plate: waist -> chest, top rolls back toward the collar
        return dict(kind='ARC', res=12, ridge='CREASE', cap_start='FLAT', cap_end='FLAT', stations=[
            _armor(width_l=0.15, width_r=0.15, height_top=0.06, height_bot=0.015, ridge_h=0.012),
            _armor(length=0.12, width_l=0.17, width_r=0.17, height_top=0.08, height_bot=0.015, ridge_h=0.016),
            _armor(length=0.14, width_l=0.2, width_r=0.2, height_top=0.1, height_bot=0.015, ridge_h=0.02),
            _armor(length=0.08, bend_angle=28, bend_dir=180, bend_style='BAND', bend_radius=0.15,
                   width_l=0.16, width_r=0.16, height_top=0.08, height_bot=0.015, ridge_h=0.012)])
    if name == 'HELMET':          # helmet shell: brow -> crown -> back, crest ridge, rounded closed back
        return dict(kind='ARC', res=12, ridge='RAISED', cap_start='FLAT', cap_end='ROUND', cap_len=0.07, stations=[
            _armor(width_l=0.1, width_r=0.1, height_top=0.11, ridge_h=0.006, ridge_w=0.025),
            _armor(length=0.06, width_l=0.115, width_r=0.115, height_top=0.15, ridge_h=0.012, ridge_w=0.025),
            _armor(length=0.09, width_l=0.12, width_r=0.12, height_top=0.16, ridge_h=0.014, ridge_w=0.025),
            _armor(length=0.05, bend_angle=22, bend_dir=180, bend_style='BAND', bend_radius=0.2,
                   width_l=0.11, width_r=0.11, height_top=0.14, ridge_h=0.01, ridge_w=0.025)])
    raise KeyError(name)
