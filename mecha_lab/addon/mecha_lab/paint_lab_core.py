"""0.24.93 Paint Lab maths, pure numpy (no bpy): photo adjustments for a stencil / brush texture, the masks from
the polypaint's brightness and from the mesh's edges.

Photo adjustments on (H, W, 4) float RGBA (0..1, display space):
hue (degrees: a rotation in YIQ, one 3x3 matrix), saturation (x, about the luminance), contrast (x, about
0.5 grey), brightness (+/-), flips.  One matrix multiply + a few adds: a 2k image in about 0.15 s."""
import math

import numpy as np

_TO_YIQ = np.array([[0.299, 0.587, 0.114], [0.596, -0.274, -0.322], [0.211, -0.523, 0.312]])
_FROM_YIQ = np.linalg.inv(_TO_YIQ)
_LUM = np.array([0.299, 0.587, 0.114])


def colour_matrix(hue=0.0, saturation=1.0, contrast=1.0):
    """The 3x3 matrix (applied to RGB rows) for hue rotation + saturation + contrast, and the offset vector."""
    a = -math.radians(hue)                                           # (+hue turns red -> green -> blue, like HSV)
    rot = np.array([[1, 0, 0], [0, math.cos(a), -math.sin(a)], [0, math.sin(a), math.cos(a)]])
    m = _FROM_YIQ @ rot @ _TO_YIQ                                       # hue
    sat = np.eye(3) * saturation + np.outer(np.ones(3), _LUM) * (1.0 - saturation)   # toward the luminance
    m = sat @ m
    m = m * contrast
    off = np.full(3, 0.5 * (1.0 - contrast))
    return m, off


def adjust(rgba, hue=0.0, saturation=1.0, contrast=1.0, brightness=0.0, flip_x=False, flip_y=False):
    """``rgba`` (H, W, 4) float in 0..1.  Returns a new float32 array of the same shape (alpha kept)."""
    src = np.asarray(rgba, np.float32)
    out = src.copy()
    if hue != 0.0 or saturation != 1.0 or contrast != 1.0 or brightness != 0.0:
        m, off = colour_matrix(hue, saturation, contrast)
        r, g, b = src[..., 0], src[..., 1], src[..., 2]
        for k in range(3):                                               # channel by channel: no big temporaries
            ch = r * np.float32(m[k, 0]) + g * np.float32(m[k, 1]) + b * np.float32(m[k, 2]) + np.float32(off[k] + brightness)
            np.clip(ch, 0.0, 1.0, out=ch)
            out[..., k] = ch
    if flip_x:
        out = out[:, ::-1]
    if flip_y:
        out = out[::-1]
    return np.ascontiguousarray(out)




# -----------------------------------------------------------------------------
# masks
# -----------------------------------------------------------------------------

def luminance(colors):
    """(N, 3|4) colours -> (N,) brightness (Rec. 601 luma)."""
    c = np.asarray(colors, np.float64)
    return c[:, 0] * 0.299 + c[:, 1] * 0.587 + c[:, 2] * 0.114


def value_mask(colors, black=0.0, white=1.0, invert=False):
    """The mask from the polypaint's brightness: 0 at ``black`` and below, 1 at ``white`` and above, a straight
    ramp between (ZBrush's Mask By Intensity).  ``invert`` flips it (dark = masked)."""
    lum = luminance(colors)
    lo, hi = float(black), float(white)
    if hi <= lo + 1e-9:
        m = (lum >= hi).astype(np.float64)
    else:
        m = np.clip((lum - lo) / (hi - lo), 0.0, 1.0)
    return 1.0 - m if invert else m


def corner_to_point(values, corner_verts, n_points):
    """Corner-domain values (C, k) averaged onto the points (N, k)."""
    v = np.asarray(values, np.float64)
    if v.ndim == 1:
        v = v[:, None]
    acc = np.zeros((n_points, v.shape[1]))
    for k in range(v.shape[1]):
        acc[:, k] = np.bincount(corner_verts, weights=v[:, k], minlength=n_points)
    cnt = np.maximum(np.bincount(corner_verts, minlength=n_points), 1)
    return acc / cnt[:, None]


def face_normals(co, corner_verts, face_start, face_tot):
    """Unit normals of polygons (Newell), (F, 3)."""
    F = len(face_start)
    n = np.zeros((F, 3))
    f_of = np.repeat(np.arange(F), face_tot)
    nxt = np.arange(len(corner_verts)) + 1
    ends = face_start + face_tot - 1
    nxt[ends] = face_start
    a = co[corner_verts]
    b = co[corner_verts[nxt]]
    cross = np.stack([(a[:, 1] - b[:, 1]) * (a[:, 2] + b[:, 2]),
                      (a[:, 2] - b[:, 2]) * (a[:, 0] + b[:, 0]),
                      (a[:, 0] - b[:, 0]) * (a[:, 1] + b[:, 1])], 1)
    for k in range(3):
        n[:, k] = np.bincount(f_of, weights=cross[:, k], minlength=F)
    ln = np.linalg.norm(n, axis=1)
    ln[ln < 1e-20] = 1.0
    return n / ln[:, None]


def edge_angles(co, corner_verts, face_start, face_tot, n_points):
    """Per point the sharpest fold through it: the largest angle (degrees) between the two faces of any edge at
    that point (0 on a flat / smooth surface, 90 on a box edge).  Open edges count as 0."""
    F = len(face_start)
    fn = face_normals(co, corner_verts, face_start, face_tot)
    f_of = np.repeat(np.arange(F), face_tot)
    nxt = np.arange(len(corner_verts)) + 1
    ends = face_start + face_tot - 1
    nxt[ends] = face_start
    a, b = corner_verts, corner_verts[nxt]
    lo, hi = np.minimum(a, b), np.maximum(a, b)
    key = lo.astype(np.int64) * (n_points + 1) + hi
    order = np.argsort(key, kind='stable')
    ks = key[order]
    first = np.ones(len(ks), bool)
    first[1:] = ks[1:] != ks[:-1]
    grp = np.cumsum(first) - 1
    pos = np.arange(len(ks)) - np.searchsorted(grp, grp, side='left')
    n_edges = int(grp[-1]) + 1 if len(grp) else 0
    f0 = -np.ones(n_edges, np.int64)
    f1 = -np.ones(n_edges, np.int64)
    fo = f_of[order]
    f0[grp[pos == 0]] = fo[pos == 0]
    f1[grp[pos == 1]] = fo[pos == 1]
    ok = (f0 >= 0) & (f1 >= 0)
    ang = np.zeros(n_edges)
    d = np.clip((fn[f0[ok]] * fn[f1[ok]]).sum(1), -1.0, 1.0)
    ang[ok] = np.degrees(np.arccos(d))
    ea = lo[order][first]
    eb = hi[order][first]
    out = np.zeros(n_points)
    np.maximum.at(out, ea, ang)
    np.maximum.at(out, eb, ang)
    return out


def edge_mask(co, corner_verts, face_start, face_tot, n_points, angle=30.0, soft=15.0, invert=False):
    """The mask on the mesh's edges: 1 where a fold through the point is ``angle`` degrees or sharper, fading to
    0 over ``soft`` degrees below it (ZBrush's Mask By Smoothness / Polish-style edge masks)."""
    ang = edge_angles(co, corner_verts, face_start, face_tot, n_points)
    lo = max(angle - soft, 0.0)
    m = np.clip((ang - lo) / max(angle - lo, 1e-9), 0.0, 1.0)
    return 1.0 - m if invert else m


def grow_mask(mask, corner_verts, face_start, face_tot, n_points, rings=1):
    """The mask spread to its neighbours ``rings`` times (every point takes the max of itself + its edge
    neighbours): a wider edge band."""
    m = np.asarray(mask, np.float64).copy()
    nxt = np.arange(len(corner_verts)) + 1
    ends = face_start + face_tot - 1
    nxt[ends] = face_start
    a, b = corner_verts, corner_verts[nxt]
    for _ in range(max(0, int(rings))):
        nm = m.copy()
        np.maximum.at(nm, a, m[b])
        np.maximum.at(nm, b, m[a])
        m = nm
    return m
