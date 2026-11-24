"""0.24.308 a profile turned round Z into a closed mesh, each ring of it round, a hexagon or a (rounded) square, a
ring optionally threaded (the helix of cylinder_gen's screw joint) - shared by the Cylinder (actuator) and the Bolt.

A profile is [(radius, z, thread weight, shape)] from the axis at its bottom round to the axis at its top (radius 0:
one point on the axis) - or a loop that never touches the axis (joined round).  ``shape``: 'R' round, 'H' hexagon
(its corners at ``radius``), 'S' a rounded square (its sides at ``radius``; how square: ``sq_p``)."""
from __future__ import annotations

import math

from mathutils import Matrix, Vector


def tri(x):
    f = x - math.floor(x)
    return 1.0 - abs(2.0 * f - 1.0)


def shape_r(shape, r, a, sq_p=8.0):
    if shape == 'H':                                  # (a hexagon: corners at 0, 60, ... degrees)
        k = (a % (math.pi / 3)) - math.pi / 6
        return r * math.cos(math.pi / 6) / math.cos(k)
    if shape == 'S':                                  # (a superellipse: p 2 a circle, more - squarer)
        c, s = abs(math.cos(a)), abs(math.sin(a))
        return r / max((c ** sq_p + s ** sq_p) ** (1.0 / sq_p), 1e-9)
    return r


def thread_pts(r, za, zb, pitch, on=True, shape='R', fade=0.75):
    """Points along a threaded wall from ``za`` to ``zb`` (the thread fading out ``fade`` pitch from either end)."""
    if not on:
        return [(r, za, 0.0, shape), (r, zb, 0.0, shape)]
    lo, hi = min(za, zb), max(za, zb)
    k = max(2, int(math.ceil(abs(zb - za) / (pitch / 6.0))))
    out = []
    for i in range(k + 1):
        z = za + (zb - za) * i / k
        f = min(z - lo, hi - z) / max(pitch * fade, 1e-9)
        out.append((r, z, max(0.0, min(1.0, f)), shape))
    return out


def revolve(bm, P, segs, depth=0.0, pitch=1.0, sq_p=8.0, yscale=1.0, matrix=None, smooth_angle=50.0, mat=0):
    """``P`` turned round Z in ``segs`` steps into ``bm`` (then moved by ``matrix``); returns its faces."""
    segs = max(3, int(segs))
    closed = P[0][0] > 1e-9
    rings = []
    new_v = []
    for r, z, w, shape in P:
        if r < 1e-9:
            v = bm.verts.new((0.0, 0.0, z))
            rings.append([v])
            new_v.append(v)
            continue
        ring = []
        for j in range(segs):
            a = 2 * math.pi * j / segs
            rr = shape_r(shape, r, a, sq_p)
            if w > 0 and depth > 0:
                rr += w * depth * tri(z / pitch - a / (2 * math.pi))
            v = bm.verts.new((rr * math.cos(a), rr * math.sin(a) * yscale, z))
            ring.append(v)
            new_v.append(v)
        rings.append(ring)
    faces = []
    pairs = list(zip(rings, rings[1:])) + ([(rings[-1], rings[0])] if closed else [])
    for a_, b_ in pairs:
        if len(a_) == 1 and len(b_) == 1:
            continue
        for j in range(segs):
            k = (j + 1) % segs
            try:
                if len(a_) == 1:
                    f = bm.faces.new((a_[0], b_[k], b_[j]))
                elif len(b_) == 1:
                    f = bm.faces.new((a_[j], a_[k], b_[0]))
                else:
                    f = bm.faces.new((a_[j], a_[k], b_[k], b_[j]))
            except ValueError:
                continue
            f.material_index = mat
            faces.append(f)
    if matrix is not None:
        for v in new_v:
            v.co = matrix @ v.co
    return faces


def finish(bm, smooth_angle=40.0, flat=False):
    """Doubles merged, normals out, smooth with its corners sharp."""
    import bmesh
    bmesh.ops.remove_doubles(bm, verts=list(bm.verts), dist=1e-7)
    bmesh.ops.dissolve_degenerate(bm, dist=1e-8, edges=list(bm.edges))
    bmesh.ops.recalc_face_normals(bm, faces=list(bm.faces))
    for f in bm.faces:
        f.smooth = not flat
    lim = math.radians(smooth_angle)
    for e in bm.edges:
        if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim:
            e.smooth = False


def frame(origin, axis):
    """A matrix putting Z along ``axis`` at ``origin``."""
    q = Vector((0, 0, 1)).rotation_difference(Vector(axis).normalized())
    return Matrix.Translation(Vector(origin)) @ q.to_matrix().to_4x4()


def bolt_profile(shank_r, shank_len, head, head_r, head_h, thread=True, pitch=0.05, chamfer=0.12, socket=0.5):
    """A bolt standing on Z: its head's underside at z = 0, its shank down to -``shank_len``.
    ``head``: HEX / ROUND (a button) / SOCKET (a round cap, a hexagon hole in its top) / NONE."""
    P = []
    tip = min(shank_r * 0.25, shank_len * 0.2)
    if shank_len > 1e-6:
        P += [(0.0, -shank_len, 0.0, 'R'), (shank_r * 0.75, -shank_len, 0.0, 'R')]
        P += thread_pts(shank_r, -shank_len + tip, 0.0, pitch, thread)
        P.append((shank_r, 0.0, 0.0, 'R'))
    else:
        P += [(0.0, 0.0, 0.0, 'R')]
    ch = head_h * chamfer
    if head == 'HEX':
        P += [(head_r, 0.0, 0.0, 'H'), (head_r, head_h - ch, 0.0, 'H'), (head_r * 0.84, head_h, 0.0, 'R'),
              (0.0, head_h, 0.0, 'R')]
    elif head == 'ROUND':
        n = 6
        for i in range(n + 1):
            t = i / n * math.pi / 2
            P.append((head_r * math.cos(t), head_h * math.sin(t), 0.0, 'R'))
        P[-1] = (0.0, head_h, 0.0, 'R')
    elif head == 'SOCKET':
        hr = head_r * socket
        P += [(head_r, 0.0, 0.0, 'R'), (head_r, head_h - ch, 0.0, 'R'), (head_r - ch, head_h, 0.0, 'R'),
              (hr, head_h, 0.0, 'H'), (hr, head_h * 0.45, 0.0, 'H'), (0.0, head_h * 0.45, 0.0, 'R')]
    else:
        P[-1] = (shank_r, 0.0, 0.0, 'R')
        P.append((0.0, 0.0, 0.0, 'R'))
    return P


def nut_profile(r_in, r_out, h, chamfer=0.12):
    """A hex nut on Z from 0 to ``h`` (a ring round the axis - its hole ``r_in``)."""
    ch = h * chamfer
    return [(r_in, h, 0.0, 'R'), (r_in, 0.0, 0.0, 'R'), (r_out * 0.84, 0.0, 0.0, 'R'), (r_out, ch, 0.0, 'H'),
            (r_out, h - ch, 0.0, 'H'), (r_out * 0.84, h, 0.0, 'R')]
