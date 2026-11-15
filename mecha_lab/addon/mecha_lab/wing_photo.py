"""0.24.173 The Insect Wing's photo patterns (user: four black-and-white photos of wings - "너에게 곤충 날개 패턴을 주마,
이것도 추가해 줘", "블랙 앤 화이트 값으로 주는 게 낫겠다"): white = a vein (raised), black = the membrane.

Each photo's wing is found in it (its silhouette: everything the background cannot reach past the white margin; its
root: the narrower end along its long axis; its tip: the other end; its leading edge: the straighter side), so its
veins can be laid on any wing drawn - by the place along it (root .. tip) and across it (leading .. trailing edge).
Broad white patches (an over-exposed base or tip) are taken down to the veins' height (a high-pass on the photo).
Pure numpy except ``load`` (Blender reads the file).
"""
from __future__ import annotations

import os

import numpy as np

DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'wing_patterns')
# (id, label, file, look like the procedural preset, its outline when it cannot be found (x, y as shares of the
# photo, from its top-left) and its root / tip)
_BROAD_OUTLINE = ((20, 280), (100, 275), (150, 255), (200, 200), (250, 165), (320, 95), (400, 55), (460, 35),
                  (520, 30), (600, 50), (612, 70), (600, 110), (560, 150), (500, 200), (450, 245), (400, 290),
                  (350, 335), (300, 365), (250, 395), (200, 420), (165, 445), (130, 445), (100, 400), (65, 380),
                  (50, 330), (30, 300))
PHOTOS = (
    ('P_LACEWING', 'Lacewing (Photo)', 'lacewing.jpg', 'LACEWING', None),
    ('P_DRAGONFLY', 'Dragonfly (Photo)', 'dragonfly.jpg', 'DRAGONFLY', None),
    ('P_CICADA', 'Cicada (Photo)', 'cicada.jpg', 'CICADA', None),
    # (its membrane darker than the photo's background in places: its outline given - 640 x 470 photo)
    ('P_BROAD', 'Broad Veins (Photo)', 'broad.jpg', 'BEE',
     dict(outline=tuple((x / 640.0, y / 470.0) for x, y in _BROAD_OUTLINE), root=(25 / 640.0, 288 / 470.0),
          tip=(612 / 640.0, 62 / 470.0))),
)
_CACHE = {}


class MaskFrame:
    """A photo's wing frame (pixels): root, axis, perp, L, and the margins at each place along it."""

    def __init__(self, inside_xy, root=None, tip=None):
        P = np.asarray(inside_xy, float)
        if root is not None and tip is not None:      # (given)
            self.root = np.asarray(root, float)
            d = np.asarray(tip, float) - self.root
            self.L = float(np.linalg.norm(d))
            self.axis = d / self.L
        else:
            c = P.mean(0)
            _u, _s, vt = np.linalg.svd(P - c, full_matrices=False)
            a = vt[0]
            t = (P - c) @ a
            lo, hi = t.min(), t.max()
            span = hi - lo
            perp = np.array([-a[1], a[0]])
            w = (P - c) @ perp

            def width(sel):
                return float(np.ptp(w[sel])) if np.any(sel) else 0.0
            w_lo = width(t < lo + 0.1 * span)
            w_hi = width(t > hi - 0.1 * span)
            if w_lo <= w_hi:                          # (the root: the narrower end)
                self.root = c + a * lo
                self.axis = a
            else:
                self.root = c + a * hi
                self.axis = -a
            self.L = float(span)
        self.perp = np.array([-self.axis[1], self.axis[0]])
        R = P - self.root
        s = R @ self.axis / self.L
        ww = R @ self.perp / self.L
        self.S = np.linspace(0.0, 1.0, 401)
        b = np.clip((s * 400).round().astype(int), 0, 400)
        hiw = np.full(401, -np.inf)
        low = np.full(401, np.inf)
        np.maximum.at(hiw, b, ww)
        np.minimum.at(low, b, ww)
        ok = np.isfinite(hiw)
        hiw = np.interp(self.S, self.S[ok], hiw[ok])
        low = np.interp(self.S, self.S[ok], low[ok])
        if np.mean(np.abs(hiw)) > np.mean(np.abs(low)):   # (the leading edge: the straighter side, + across)
            self.perp = -self.perp
            hiw, low = -low, -hiw
        self.lead_w, self.trail_w = hiw, low

    def point(self, s, f):
        s = np.clip(np.asarray(s, float), 0.0, 1.0)
        f = np.clip(np.asarray(f, float), 0.0, 1.0)
        hi = np.interp(s, self.S, self.lead_w)
        lo = np.interp(s, self.S, self.trail_w)
        w = hi + f * (lo - hi)
        return self.root + self.L * (s[..., None] * self.axis + w[..., None] * self.perp)


def _shift_or(m):
    out = m.copy()
    out[1:] |= m[:-1]
    out[:-1] |= m[1:]
    out[:, 1:] |= m[:, :-1]
    out[:, :-1] |= m[:, 1:]
    return out


def silhouette(G, size=320):
    """The wing's inside (bool, at a smaller size) and the scale back: everything the background (the border, its
    own darkness) cannot reach past anything lighter than it (the veins, a grey membrane)."""
    H, W = G.shape
    k = max(1, int(np.ceil(max(H, W) / size)))
    h, w = H // k, W // k
    g = G[:h * k, :w * k].reshape(h, k, w, k).mean(axis=(1, 3))
    border = np.r_[g[0], g[-1], g[:, 0], g[:, -1]]
    bg = float(np.median(border))
    walls = _shift_or(g > bg + 0.09)
    reached = np.zeros_like(walls)
    reached[0, :] = ~walls[0, :]
    reached[-1, :] = ~walls[-1, :]
    reached[:, 0] = ~walls[:, 0]
    reached[:, -1] = ~walls[:, -1]
    for _ in range(4 * (h + w)):
        nxt = _shift_or(reached) & ~walls
        if np.array_equal(nxt, reached):
            break
        reached = nxt
    return ~reached, k


def _box_blur(A, r):
    if r < 1:
        return A
    out = A.astype(np.float64)
    for axis in (0, 1):
        c = np.cumsum(np.pad(out, [(r + 1, r) if i == axis else (0, 0) for i in range(2)], mode='edge'), axis=axis)
        n = out.shape[axis]
        hi = np.take(c, np.arange(2 * r + 1, 2 * r + 1 + n), axis=axis)
        lo = np.take(c, np.arange(0, n), axis=axis)
        out = (hi - lo) / (2 * r + 1)
    return out


def _inside(Q, P):
    A, B = P, np.roll(P, -1, axis=0)
    x, y = Q[:, 0:1], Q[:, 1:2]
    cross = (A[None, :, 1] > y) != (B[None, :, 1] > y)
    with np.errstate(divide='ignore', invalid='ignore'):
        xi = A[None, :, 0] + (y - A[None, :, 1]) * (B[None, :, 0] - A[None, :, 0]) / (B[None, :, 1] - A[None, :, 1])
    return (np.sum(cross & (x < xi), axis=1) % 2).astype(bool)


def analyse(G, given=None):
    """(frame in pixels, the veins' field 0..1 the size of ``G``) for a photo ``G`` (H x W, 0..1, rows bottom-up);
    ``given``: its outline / root / tip (shares of the photo from its top-left) when it cannot be found."""
    H, W = G.shape
    if given:
        def px(q):
            return np.array([q[0] * W, (1.0 - q[1]) * H])
        poly = np.array([px(q) for q in given['outline']])
        k = max(1, int(np.ceil(max(H, W) / 320)))
        gx, gy = np.meshgrid(np.arange(0, W, k) + 0.5 * k, np.arange(0, H, k) + 0.5 * k)
        Q = np.c_[gx.ravel(), gy.ravel()]
        Q = Q[_inside(Q, poly)]
        fr = MaskFrame(Q, px(given['root']), px(given['tip']))
    else:
        inside, k = silhouette(G)
        ys, xs = np.nonzero(inside)
        fr = MaskFrame(np.c_[(xs + 0.5) * k, (ys + 0.5) * k])
    r = max(2, int(fr.L * 0.025))
    blur = G
    for _ in range(3):
        blur = _box_blur(blur, r)
    hp = np.clip(G - 0.85 * blur, 0.0, None)          # (broad white patches down to the veins' height)
    top = float(np.percentile(hp[hp > 0.02], 99.0)) if np.any(hp > 0.02) else 1.0
    field = np.clip(hp / max(top, 1e-6), 0.0, 1.0).astype(np.float32)
    return fr, field


def sample(field, xy):
    H, W = field.shape
    x = np.clip(xy[:, 0] - 0.5, 0, W - 1.001)
    y = np.clip(xy[:, 1] - 0.5, 0, H - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = x - x0, y - y0
    a = field[y0, x0] * (1 - fx) + field[y0, x0 + 1] * fx
    b = field[y0 + 1, x0] * (1 - fx) + field[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


def load(pid):
    """(frame, field) of a photo preset (read once)."""
    if pid in _CACHE:
        return _CACHE[pid]
    import bpy
    spec = next(p for p in PHOTOS if p[0] == pid)
    path = os.path.join(DIR, spec[2])
    im = bpy.data.images.load(path, check_existing=False)
    try:
        W, H = im.size
        px = np.empty(W * H * im.channels, np.float32)
        im.pixels.foreach_get(px)
        G = px.reshape(H, W, im.channels)[..., :3].mean(-1)
    finally:
        bpy.data.images.remove(im)
    _CACHE[pid] = analyse(G, spec[4])
    return _CACHE[pid]
