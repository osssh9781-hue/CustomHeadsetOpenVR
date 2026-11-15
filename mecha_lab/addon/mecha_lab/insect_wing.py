"""0.24.173 Insect Wing (user: "이건 시뮬은 필요 없는데 잠자리 날개나 곤충 날개 같은 거 만들 수 있게 내가 그린 영역 내부에
곤충 날개 무늬가 양각으로 드러나게 해 줘"): draw a wing's outline - a thin wing plate in the drawn shape, its veins
raised (embossed) on it, both sides, no simulation.

Where it sits: the plane of the drawing (through the mesh under it, else the 3D cursor), facing the view.  Its root:
the outline's point nearest to a mesh (the body it grows from), else where the drawing started; its tip: the point
farthest from the root; its leading edge: the straighter side (Flip: the other one).  The veins (in the wing's own
frame - along it from the root, across from the leading edge to the trailing edge): the margin, veins along the
leading edge, veins fanning from the root to the margin, cross veins between them, a net of small cells (dragonfly),
the pterostigma.  They are drawn into an image (crisp in the material: dark, opaque, bumped) and the plate's points
take their height from it (raised).  Six presets: Dragonfly, Damselfly, Bee / Wasp, Fly, Lacewing, Cicada.  Live: the
window's sliders lay it again; Enter / Apply keeps it as it is.
"""
from __future__ import annotations

import json
import math
import random

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils import Vector

from . import outline_mesh as om

KEY = 'mch_wing'                  # on a live wing: its outline and plane (json)
_BUSY = [False]

# (id, label, spec) - lead: the veins along the leading edge (offsets across, 0 the leading edge .. 1 the trailing),
# long: veins fanning from the root, reach: how far toward the margin they go, fork: the chance a vein forks before the
# margin, cross: cross veins every this much of the length (in zone), cells: a net of cells this big (0 none),
# stigma: (from, to, depth) the pterostigma, inner: a vein along the trailing margin this far in (0 none), width: the
# veins' width (x the length); tint / vein: colours (linear), alpha: the membrane's opacity, film: iridescence (nm)
PRESETS = (
    ('DRAGONFLY', 'Dragonfly', dict(lead=(0.03, 0.07, 0.12), long=7, reach=1.0, fork=0.0, cross=0.022,
                                    zone=(0.03, 0.97), cells=0.024, stigma=(0.84, 0.91, 0.08), inner=0.0, width=0.0035,
                                    tint=(0.8, 0.72, 0.5), vein=(0.025, 0.02, 0.015), alpha=0.16, film=480.0)),
    ('DAMSELFLY', 'Damselfly', dict(lead=(0.035, 0.08), long=5, reach=1.0, fork=0.0, cross=0.03, zone=(0.06, 0.96),
                                    cells=0.032, stigma=(0.86, 0.92, 0.07), inner=0.0, width=0.003,
                                    tint=(0.03, 0.06, 0.08), vein=(0.01, 0.012, 0.015), alpha=0.6, film=650.0)),
    ('BEE', 'Bee / Wasp', dict(lead=(0.03, 0.07), long=4, reach=0.68, fork=0.0, cross=0.08, zone=(0.25, 0.62),
                               cells=0.0, stigma=(0.5, 0.58, 0.07), inner=0.0, width=0.006,
                               tint=(0.6, 0.52, 0.38), vein=(0.1, 0.055, 0.02), alpha=0.25, film=380.0)),
    ('FLY', 'Fly', dict(lead=(0.03,), long=4, reach=1.0, fork=0.0, cross=0.16, zone=(0.42, 0.62), cells=0.0,
                        stigma=None, inner=0.0, width=0.005, tint=(0.4, 0.4, 0.42), vein=(0.04, 0.035, 0.03),
                        alpha=0.3, film=420.0)),
    ('LACEWING', 'Lacewing', dict(lead=(0.03, 0.06), long=8, reach=1.0, fork=0.85, cross=0.03, zone=(0.03, 0.96),
                                  cells=0.0, stigma=(0.8, 0.86, 0.06), inner=0.0, width=0.0025,
                                  tint=(0.55, 0.75, 0.5), vein=(0.12, 0.3, 0.04), alpha=0.14, film=320.0)),
    ('CICADA', 'Cicada', dict(lead=(0.035, 0.075), long=7, reach=0.93, fork=0.0, cross=0.13, zone=(0.2, 0.9),
                              cells=0.0, stigma=None, inner=0.06, width=0.0055, tint=(0.6, 0.52, 0.36),
                              vein=(0.08, 0.1, 0.03), alpha=0.22, film=520.0)),
)
PRESET_ITEMS = [(p[0], p[1], '') for p in PRESETS]
SPEC = {p[0]: p[2] for p in PRESETS}


def is_wing(ob):
    return ob is not None and KEY in ob.keys()


def active_wing(context):
    ob = getattr(context.view_layer.objects, 'active', None)
    try:
        return ob if is_wing(ob) and ob.select_get() else None
    except (RuntimeError, ReferenceError):
        return None


# ---- the wing's frame ---------------------------------------------------------------------------------------------

class Frame:
    """The wing's own frame on its outline ``P`` (plane coordinates): s along (0 the root .. 1 the tip), across f
    (0 the leading edge .. 1 the trailing edge) at each s."""

    def __init__(self, P, root_i, flip=False):
        self.P = P = np.asarray(P, float)
        self.root = P[root_i]
        d = np.linalg.norm(P - self.root, axis=1)
        tip_i = int(np.argmax(d))
        self.L = max(float(d[tip_i]), 1e-9)
        self.axis = (P[tip_i] - self.root) / self.L
        self.perp = np.array([-self.axis[1], self.axis[0]])
        n = len(P)
        arc1 = [(root_i + k) % n for k in range((tip_i - root_i) % n + 1)]
        arc2 = [(root_i - k) % n for k in range((root_i - tip_i) % n + 1)]
        w1 = np.abs(((P[arc1] - self.root) @ self.perp)).mean()
        w2 = np.abs(((P[arc2] - self.root) @ self.perp)).mean()
        lead = arc1 if w1 <= w2 else arc2               # (the leading edge: the straighter side)
        if flip:
            lead = arc2 if lead is arc1 else arc1
        self.trail_arc = arc2 if lead is arc1 else arc1
        if ((P[lead] - self.root) @ self.perp).mean() < 0:
            self.perp = -self.perp                      # (across: + toward the leading edge)
        sw = self.to_sw(P)
        self.S = np.linspace(0.0, 1.0, 401)
        self.lead_w, self.trail_w = self._margins(sw)

    def to_sw(self, Q):
        R = np.asarray(Q, float) - self.root
        return np.c_[R @ self.axis, R @ self.perp] / self.L

    def _margins(self, sw):
        """The outline's highest / lowest w at each s (where a line across the wing at s meets it)."""
        A, B = sw, np.roll(sw, -1, axis=0)
        hi = np.full(len(self.S), np.nan)
        lo = np.full(len(self.S), np.nan)
        for i, s in enumerate(self.S):
            m = ((A[:, 0] - s) * (B[:, 0] - s)) <= 0
            if not np.any(m):
                continue
            a, b = A[m], B[m]
            ds = b[:, 0] - a[:, 0]
            t = np.where(np.abs(ds) > 1e-12, (s - a[:, 0]) / np.where(np.abs(ds) > 1e-12, ds, 1.0), 0.5)
            w = a[:, 1] + t * (b[:, 1] - a[:, 1])
            hi[i], lo[i] = w.max(), w.min()
        ok = ~np.isnan(hi)
        if not np.any(ok):
            return np.full(len(self.S), 0.1), np.full(len(self.S), -0.1)
        hi = np.interp(self.S, self.S[ok], hi[ok])
        lo = np.interp(self.S, self.S[ok], lo[ok])
        return hi, lo

    def point(self, s, f):
        """Plane coordinates of (s, f) - arrays."""
        s = np.asarray(s, float)
        f = np.asarray(f, float)
        hi = np.interp(s, self.S, self.lead_w)
        lo = np.interp(s, self.S, self.trail_w)
        w = hi + f * (lo - hi)
        return self.root + self.L * (s[..., None] * self.axis + w[..., None] * self.perp)

    def sf(self, Q):
        sw = self.to_sw(Q)
        hi = np.interp(sw[:, 0], self.S, self.lead_w)
        lo = np.interp(sw[:, 0], self.S, self.trail_w)
        return np.c_[sw[:, 0], (hi - sw[:, 1]) / np.maximum(hi - lo, 1e-9)]


# ---- the veins ----------------------------------------------------------------------------------------------------

def _bezier(p0, p1, p2, n=48):
    t = np.linspace(0.0, 1.0, n)[:, None]
    return (1 - t) ** 2 * np.asarray(p0) + 2 * (1 - t) * t * np.asarray(p1) + t * t * np.asarray(p2)


def veins(fr, spec, density=1.0, seed=0):
    """[(polyline N x 2 in plane coordinates, half-width per point N, closed)], stigma polygon (or None)."""
    rng = random.Random(seed * 7919 + 17)
    L = fr.L
    r0 = spec['width'] * L * 0.5
    out = []
    # the margin: the outline itself
    out.append((fr.P, np.full(len(fr.P), r0 * 0.8), True))
    sf_lines = []                                       # (s, f) polylines, leading edge first, for the cross veins
    for j, f in enumerate(spec['lead']):                # along the leading edge
        s = np.linspace(0.01, 0.985 - 0.035 * j, 90)
        sf = np.c_[s, np.full(len(s), f)]
        sf_lines.append(sf)
        out.append((fr.point(sf[:, 0], sf[:, 1]), np.full(len(s), r0 * (1.35 - 0.15 * j)), False))
    # fanning from the root to the margin (their ends spread from the tip round the trailing edge)
    K = spec['long']
    tr = fr.P[fr.trail_arc[::-1]]                       # (the trailing margin: from the tip back to the root)
    seg = np.r_[0.0, np.cumsum(np.linalg.norm(np.diff(tr, axis=0), axis=1))]
    for k in range(K):
        g = 0.03 + 0.72 * (k / max(K - 1, 1))
        e = np.array([np.interp(g * seg[-1], seg, tr[:, 0]), np.interp(g * seg[-1], seg, tr[:, 1])])
        se, fe = fr.sf(e[None])[0]
        fe = min(max(fe, 0.0), 1.0)
        s0 = 0.02 + 0.03 * k / max(K - 1, 1)
        f0 = 0.17 + 0.3 * k / max(K - 1, 1)
        end = np.array([s0 + (se - s0) * spec['reach'], f0 + (fe - f0) * spec['reach']])
        mid = np.array([s0 + (end[0] - s0) * 0.55, f0 + (end[1] - f0) * 0.22])
        sf = _bezier((s0, f0), mid, end)
        sf_lines.append(sf)
        taper = np.linspace(1.15, 0.6, len(sf))
        out.append((fr.point(sf[:, 0], sf[:, 1]), r0 * taper, False))
        if spec['fork'] > 0 and rng.random() < spec['fork'] and spec['reach'] >= 0.99:
            g2 = min(g + 0.035, 0.98)                   # (a fork near the margin)
            e2 = np.array([np.interp(g2 * seg[-1], seg, tr[:, 0]), np.interp(g2 * seg[-1], seg, tr[:, 1])])
            s2, f2 = fr.sf(e2[None])[0]
            at = sf[int(len(sf) * 0.8)]
            br = _bezier(at, (at + np.array([s2, f2])) / 2, (s2, min(max(f2, 0), 1)), 16)
            out.append((fr.point(br[:, 0], br[:, 1]), np.full(len(br), r0 * 0.55), False))
    if spec['inner'] > 0:                               # a vein along the trailing margin, cells to the margin
        s = np.linspace(0.25, 0.95, 70)
        sf = np.c_[s, np.full(len(s), 1.0 - spec['inner'])]
        out.append((fr.point(sf[:, 0], sf[:, 1]), np.full(len(s), r0 * 0.7), False))
        for s_ in np.arange(0.27, 0.95, 0.045 / density):
            out.append((fr.point(np.array([s_, s_]), np.array([1.0 - spec['inner'], 1.0])),
                        np.full(2, r0 * 0.5), False))
    # cross veins between neighbouring veins (by their place across at mid length)
    if spec['cross'] > 0:
        order = sorted(range(len(sf_lines)), key=lambda i: float(np.interp(0.5, sf_lines[i][:, 0], sf_lines[i][:, 1])))
        step = spec['cross'] / max(density, 0.05)
        z0, z1 = spec['zone']
        for a_i, b_i in zip(order, order[1:]):
            A, B = sf_lines[a_i], sf_lines[b_i]
            lo = max(A[:, 0].min(), B[:, 0].min(), z0)
            hi = min(A[:, 0].max(), B[:, 0].max(), z1)
            s_ = lo + step * rng.uniform(0.2, 0.8)
            while s_ < hi:
                sa = s_ + rng.uniform(-0.25, 0.25) * step
                sb = s_ + rng.uniform(-0.25, 0.25) * step
                if lo <= sa <= hi and lo <= sb <= hi:
                    fa = np.interp(sa, A[:, 0], A[:, 1])
                    fb = np.interp(sb, B[:, 0], B[:, 1])
                    out.append((fr.point(np.array([sa, sb]), np.array([fa, fb])), np.full(2, r0 * 0.5), False))
                s_ += step * rng.uniform(0.8, 1.2)
    # a net of small cells (dragonflies): the edges of the cells round scattered points
    if spec['cells'] > 0:
        c = spec['cells'] * L / max(density, 0.05)
        lo, hi = fr.P.min(0), fr.P.max(0)
        xs = np.arange(lo[0], hi[0] + c, c)
        ys = np.arange(lo[1], hi[1] + c, c * 0.866)
        G = np.array([(x + (0.5 * c if r % 2 else 0.0), y) for r, y in enumerate(ys) for x in xs], float)
        nr = np.random.default_rng(seed + 3)
        G = G + nr.uniform(-0.3, 0.3, G.shape) * c
        G = G[om.inside(G, [fr.P])]
        if len(G) >= 4:
            from mathutils.geometry import delaunay_2d_cdt
            vv, _e, ff, vo, _eo, _fo = delaunay_2d_cdt([Vector(p) for p in G], [], [], 0, 1e-9, True)
            V = np.array([tuple(v) for v in vv], float)
            tris = np.array([f for f in ff if len(f) == 3], int).reshape(-1, 3)
            a, b, cc = V[tris[:, 0]], V[tris[:, 1]], V[tris[:, 2]]
            dd = 2 * (a[:, 0] * (b[:, 1] - cc[:, 1]) + b[:, 0] * (cc[:, 1] - a[:, 1]) + cc[:, 0] * (a[:, 1] - b[:, 1]))
            dd = np.where(np.abs(dd) < 1e-18, 1e-18, dd)
            A2, B2, C2 = (a * a).sum(1), (b * b).sum(1), (cc * cc).sum(1)
            ux = (A2 * (b[:, 1] - cc[:, 1]) + B2 * (cc[:, 1] - a[:, 1]) + C2 * (a[:, 1] - b[:, 1])) / dd
            uy = (A2 * (cc[:, 0] - b[:, 0]) + B2 * (a[:, 0] - cc[:, 0]) + C2 * (b[:, 0] - a[:, 0])) / dd
            CC = np.c_[ux, uy]
            edge_tri = {}
            for t_i, (i, j, k) in enumerate(tris):
                for e_ in ((i, j), (j, k), (k, i)):
                    edge_tri.setdefault((min(e_), max(e_)), []).append(t_i)
            segs = [(CC[ts[0]], CC[ts[1]]) for ts in edge_tri.values() if len(ts) == 2]
            if segs:
                S0 = np.array([s_[0] for s_ in segs])
                S1 = np.array([s_[1] for s_ in segs])
                ok = om.inside(S0, [fr.P]) & om.inside(S1, [fr.P])
                sf0 = fr.sf(S0)
                ok &= sf0[:, 0] > 0.07                    # (none right at the root)
                ok &= np.linalg.norm(S1 - S0, axis=1) < c * 2.5
                for p0, p1 in zip(S0[ok], S1[ok]):
                    out.append((np.array([p0, p1]), np.full(2, r0 * 0.42), False))
    stigma = None
    if spec.get('stigma'):
        a_, b_, dpt = spec['stigma']
        s = np.linspace(a_, b_, 8)
        top = fr.point(s, np.full(len(s), 0.0))
        bot = fr.point(s[::-1], np.full(len(s), dpt))
        stigma = np.r_[top, bot]
    return out, stigma


def raster(fr, vlist, stigma, px):
    """The veins drawn into a height field (H x W: R the veins' height 0..1, round in section, the thicker ones
    higher; G the pterostigma) over the outline's bounds, ``px`` plane units a pixel.  Returns (img, lo)."""
    lo = fr.P.min(0) - px * 4
    hi = fr.P.max(0) + px * 4
    W = int(math.ceil((hi[0] - lo[0]) / px)) + 1
    H = int(math.ceil((hi[1] - lo[1]) / px)) + 1
    R = np.zeros((H, W), np.float32)
    rmax = max(float(max(r.max() for _p, r, _c in vlist)), 1e-12)
    for P, r, closed in vlist:
        if closed:
            P = np.r_[P, P[:1]]
            r = np.r_[r, r[:1]]
        for i in range(len(P) - 1):
            a, b = P[i], P[i + 1]
            ra = max(float(r[i]), float(r[i + 1]))
            x0 = max(int((min(a[0], b[0]) - ra - lo[0]) / px), 0)
            x1 = min(int((max(a[0], b[0]) + ra - lo[0]) / px) + 2, W)
            y0 = max(int((min(a[1], b[1]) - ra - lo[1]) / px), 0)
            y1 = min(int((max(a[1], b[1]) + ra - lo[1]) / px) + 2, H)
            if x1 <= x0 or y1 <= y0:
                continue
            gx = lo[0] + np.arange(x0, x1) * px
            gy = lo[1] + np.arange(y0, y1) * px
            X, Y = np.meshgrid(gx, gy)
            ab = b - a
            L2 = max(float(ab @ ab), 1e-18)
            t = np.clip(((X - a[0]) * ab[0] + (Y - a[1]) * ab[1]) / L2, 0.0, 1.0)
            rr = r[i] + (r[i + 1] - r[i]) * t
            dx, dy = X - (a[0] + t * ab[0]), Y - (a[1] + t * ab[1])
            q = 1.0 - (dx * dx + dy * dy) / np.maximum(rr * rr, 1e-18)
            prof = np.sqrt(np.clip(q, 0.0, 1.0)) * (rr / rmax)
            R[y0:y1, x0:x1] = np.maximum(R[y0:y1, x0:x1], prof.astype(np.float32))
    G = np.zeros((H, W), np.float32)
    if stigma is not None:
        x0, y0 = ((stigma.min(0) - lo) / px).astype(int)
        x1, y1 = ((stigma.max(0) - lo) / px).astype(int) + 2
        gx = lo[0] + np.arange(x0, x1) * px
        gy = lo[1] + np.arange(y0, y1) * px
        X, Y = np.meshgrid(gx, gy)
        m = om.inside(np.c_[X.ravel(), Y.ravel()], [stigma]).reshape(X.shape)
        G[y0:y1, x0:x1] = np.maximum(G[y0:y1, x0:x1], m.astype(np.float32))
        R[y0:y1, x0:x1] = np.maximum(R[y0:y1, x0:x1], 0.55 * m.astype(np.float32))
    return np.stack([R, G], axis=-1), lo


def sample(img, lo, px, Q):
    """Bilinear: the field at the plane points ``Q``."""
    H, W = img.shape[:2]
    x = np.clip((Q[:, 0] - lo[0]) / px, 0, W - 1.001)
    y = np.clip((Q[:, 1] - lo[1]) / px, 0, H - 1.001)
    x0, y0 = x.astype(int), y.astype(int)
    fx, fy = (x - x0)[:, None], (y - y0)[:, None]
    a = img[y0, x0] * (1 - fx) + img[y0, x0 + 1] * fx
    b = img[y0 + 1, x0] * (1 - fx) + img[y0 + 1, x0 + 1] * fx
    return a * (1 - fy) + b * fy


# ---- the material --------------------------------------------------------------------------------------------------

def wing_material(ob, image, spec):
    name = f'MCH Wing ({ob.name})'
    m = ob.data.materials[0] if len(ob.data.materials) and ob.data.materials[0] is not None and \
        ob.data.materials[0].get('mch_wing_mat') else None
    if m is None:
        m = bpy.data.materials.new(name)
        m['mch_wing_mat'] = 1
        ob.data.materials.clear()
        ob.data.materials.append(m)
    m.use_nodes = True
    nt = m.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    pb = nt.nodes.new('ShaderNodeBsdfPrincipled')
    nt.links.new(pb.outputs[0], out.inputs['Surface'])
    tx = nt.nodes.new('ShaderNodeTexImage')
    tx.image = image
    tx.interpolation = 'Linear'
    tx.extension = 'EXTEND'
    sep = nt.nodes.new('ShaderNodeSeparateColor')
    nt.links.new(tx.outputs['Color'], sep.inputs[0])

    def math_(op, a, b=None, clamp=False):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        n.use_clamp = clamp
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]
    vein = math_('MAXIMUM', math_('MULTIPLY', sep.outputs[0], 3.0, clamp=True), sep.outputs[1])
    mix = nt.nodes.new('ShaderNodeMix')
    mix.data_type = 'RGBA'
    sock = {i.identifier: i for i in mix.inputs}
    nt.links.new(vein, sock['Factor_Float'])
    sock['A_Color'].default_value = (*spec['tint'], 1.0)
    sock['B_Color'].default_value = (*spec['vein'], 1.0)
    nt.links.new(next(o for o in mix.outputs if o.identifier == 'Result_Color'), pb.inputs['Base Color'])
    alpha = math_('ADD', spec['alpha'], math_('MULTIPLY', vein, 1.0 - spec['alpha']), clamp=True)
    nt.links.new(alpha, pb.inputs['Alpha'])
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.6
    bump.inputs['Distance'].default_value = 0.002
    nt.links.new(sep.outputs[0], bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    pb.inputs['Roughness'].default_value = 0.12
    for k, v in (('Thin Film Thickness', spec['film']), ('Thin Film IOR', 1.45)):
        try:
            pb.inputs[k].default_value = v
        except KeyError:
            pass
    try:
        m.surface_render_method = 'DITHERED'
    except (AttributeError, TypeError):
        pass
    m.diffuse_color = (*spec['tint'], max(spec['alpha'], 0.35))
    return m


# ---- the wing object ---------------------------------------------------------------------------------------------

def data(ob):
    try:
        return json.loads(ob[KEY])
    except (KeyError, ValueError, TypeError):
        return None


def build(ob, context=None):
    """The wing laid from its outline and its settings (mesh, veins image, material).  Returns faces."""
    d = data(ob)
    if d is None:
        return 0
    p = ob.mch_wing
    spec = SPEC.get(p.preset, SPEC['DRAGONFLY'])
    P = np.array(d['outline'], float)
    fr = Frame(P, int(d['root']) % len(P), p.flip)
    vl, stigma = veins(fr, spec, p.density, p.seed)
    if abs(p.vein_width - 1.0) > 1e-6:
        vl = [(q, r * p.vein_width, c) for q, r, c in vl]
    px = fr.L / 1400.0
    img, lo = raster(fr, vl, stigma, px)
    spacing = fr.L / max(p.detail, 20)
    pts, tris, nb = om.even_mesh(P, spacing)
    hv = sample(img, lo, px, pts)[:, 0]
    L = fr.L
    t = L * p.thickness / 100.0 * 0.5
    H = L * p.vein_height / 100.0
    zt = t + H * hv
    zb = -(t + 0.6 * H * hv)
    n = len(pts)
    V = np.r_[np.c_[pts, zt], np.c_[pts, zb]]
    faces = [tuple(f) for f in tris.tolist()] + [tuple(int(i) + n for i in f[::-1]) for f in tris.tolist()]
    faces += [(i, (i + 1) % nb, (i + 1) % nb + n, i + n) for i in range(nb)]
    O = Vector(d['origin'])
    X, Y, N = Vector(d['x']), Vector(d['y']), Vector(d['n'])
    M = np.array([tuple(X), tuple(Y), tuple(N)], float)
    W3 = V @ M + np.array(tuple(O))
    inv = ob.matrix_world.inverted()
    Ml = np.array(inv)
    Lc = W3 @ Ml[:3, :3].T + Ml[:3, 3]
    me = ob.data
    bm = bmesh.new()
    vs = [bm.verts.new(tuple(c)) for c in Lc]
    for f in faces:
        try:
            bm.faces.new([vs[i] for i in f])
        except ValueError:
            pass
    top = [f for f in bm.faces if all(v.index < n for v in f.verts)]
    bot = [f for f in bm.faces if all(v.index >= n for v in f.verts)]
    bmesh.ops.join_triangles(bm, faces=top, angle_face_threshold=math.radians(20), angle_shape_threshold=math.radians(35))
    bmesh.ops.join_triangles(bm, faces=[f for f in bot if f.is_valid], angle_face_threshold=math.radians(20),
                             angle_shape_threshold=math.radians(35))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    uvl = bm.loops.layers.uv.new('UVMap')
    Hh, Ww = img.shape[:2]
    bm.verts.ensure_lookup_table()
    for f in bm.faces:
        for lp in f.loops:
            i = lp.vert.index % n if lp.vert.index < 2 * n else 0
            q = pts[i]
            lp[uvl].uv = ((q[0] - lo[0]) / px / (Ww - 1), (q[1] - lo[1]) / px / (Hh - 1))
    bm.to_mesh(me)
    bm.free()
    for poly in me.polygons:
        poly.use_smooth = True
    me.update()
    # the veins' image (crisp in the material)
    iname = f'MCH Wing Veins ({ob.name})'
    im = bpy.data.images.get(iname)
    if im is not None and (im.size[0] != Ww or im.size[1] != Hh):
        bpy.data.images.remove(im)
        im = None
    if im is None:
        im = bpy.data.images.new(iname, Ww, Hh, alpha=True, float_buffer=True)
        im.colorspace_settings.name = 'Non-Color'
    rgba = np.zeros((Hh, Ww, 4), np.float32)
    rgba[..., 0] = img[..., 0]
    rgba[..., 1] = img[..., 1]
    rgba[..., 3] = 1.0
    im.pixels.foreach_set(rgba.ravel())
    im.update()
    try:
        im.pack()
    except RuntimeError:
        pass
    wing_material(ob, im, spec)
    ob['mch_wing_size'] = L
    return len(me.polygons)


def _upd(self, context):
    if _BUSY[0]:
        return
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_wing(ob):
        build(ob, context)
        sc = getattr(context, 'scene', None)
        if sc is not None and hasattr(sc, 'mch_wing'):
            _BUSY[0] = True
            try:
                for k in LIVE:
                    setattr(sc.mch_wing, k, getattr(self, k))
            finally:
                _BUSY[0] = False


LIVE = ('preset', 'vein_height', 'vein_width', 'density', 'thickness', 'detail', 'seed', 'flip')


class MCH_PG_Wing(bpy.types.PropertyGroup):
    preset: EnumProperty(name='Wing', items=PRESET_ITEMS, default='DRAGONFLY', update=_upd)
    vein_height: FloatProperty(name='Vein Height %', default=0.6, min=0.0, max=5.0, soft_max=2.0, update=_upd,
                               description='How far the veins stand out (raised), % of the wing\'s length')
    vein_width: FloatProperty(name='Vein Width', default=1.0, min=0.2, max=4.0, update=_upd)
    density: FloatProperty(name='Vein Density', default=1.0, min=0.3, max=3.0, update=_upd,
                           description='More cross veins and smaller cells')
    thickness: FloatProperty(name='Thickness %', default=0.15, min=0.01, max=3.0, update=_upd,
                             description='The membrane\'s thickness, % of the wing\'s length')
    detail: IntProperty(name='Detail', default=220, min=40, max=600, update=_upd,
                        description='Points along the wing\'s length (more: sharper raised veins, heavier)')
    seed: IntProperty(name='Seed', default=0, min=0, update=_upd)
    flip: BoolProperty(name='Flip Leading Edge', default=False, update=_upd,
                       description='The veins along the other edge')


# ---- drawing -------------------------------------------------------------------------------------------------------

def _root_index(context, P3, length):
    """The outline point nearest to a mesh (the body the wing grows from) - None when no mesh is near."""
    best = None
    for o in context.view_layer.objects:
        if o.type != 'MESH' or not o.visible_get() or is_wing(o):
            continue
        Mi = o.matrix_world.inverted()
        for i, q in enumerate(P3):
            ok, loc, _n, _f = o.closest_point_on_mesh(Mi @ Vector(q))
            if ok:
                dd = ((o.matrix_world @ loc) - Vector(q)).length
                if best is None or dd < best[0]:
                    best = (dd, i)
    if best is None or best[0] > 0.25 * length:
        return None
    return best[1]


def perform(context, loops, projector):
    from . import base_mesh
    from . import core_geometry as cg
    groups = cg.prepare_loops(loops)
    if not groups:
        raise cg.CutError('Draw a bigger wing')
    outer = groups[0][0]
    origin, X, Y, N = base_mesh.plane_frame(context, projector, groups)
    P3, P2 = [], []
    for q in outer:
        o, dvec = projector.ray(q)
        o, dvec = Vector(o), Vector(dvec)
        den = dvec.dot(N)
        if abs(den) < 1e-9:
            continue
        p = o + dvec * ((origin - o).dot(N) / den)
        P3.append(tuple(p))
        P2.append(((p - origin).dot(X), (p - origin).dot(Y)))
    if len(P2) < 3:
        raise cg.CutError('Draw the wing facing you')
    P2 = np.array(P2, float)
    step = max(1, len(P2) // 400)
    P2, P3 = P2[::step], P3[::step]
    length = float(np.linalg.norm(P2 - P2[:, None], axis=2).max()) if len(P2) < 2000 else float(np.ptp(P2, axis=0).max())
    if length < 1e-6:
        raise cg.CutError('Draw a bigger wing')
    root = _root_index(context, P3, length)
    st = context.scene.mch_wing
    me = bpy.data.meshes.new('Insect Wing')
    ob = bpy.data.objects.new('Insect Wing', me)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.matrix_world = __import__('mathutils').Matrix.Translation(Vector(P3[root if root is not None else 0]))
    ob[KEY] = json.dumps(dict(outline=P2.round(7).tolist(), root=int(root if root is not None else 0),
                              origin=tuple(origin), x=tuple(X), y=tuple(Y), n=tuple(N)))
    _BUSY[0] = True
    try:
        for k in LIVE:
            setattr(ob.mch_wing, k, getattr(st, k))
    finally:
        _BUSY[0] = False
    nf = build(ob, context)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    where = 'its root at the mesh beside it' if root is not None else 'its root where you started drawing'
    return (f'{ob.name}: a {dict((i[0], i[1]) for i in PRESET_ITEMS)[ob.mch_wing.preset]} wing ({nf:,} faces), {where} '
            f'- Enter: keep')


def apply_wing(ob):
    for k in (KEY, 'mch_wing_size'):
        if k in ob.keys():
            del ob[k]


def apply_targets(context):
    sel = [o for o in getattr(context, 'selected_objects', []) or [] if is_wing(o)]
    return sel or ([active_wing(context)] if active_wing(context) is not None else [])


class MCH_OT_wing_apply(bpy.types.Operator):
    """The selected insect wings kept as they are (no longer live)"""
    bl_idname = 'mch.wing_apply'
    bl_label = 'Apply Insect Wing'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(apply_targets(context))

    def execute(self, context):
        obs = apply_targets(context)
        for ob in obs:
            apply_wing(ob)
        self.report({'INFO'}, 'Insect Wing kept: ' + ', '.join(o.name for o in obs))
        return {'FINISHED'}


class MCH_OT_wing_preset(bpy.types.Operator):
    """This kind of wing (the selected wing too)"""
    bl_idname = 'mch.wing_preset'
    bl_label = 'Insect Wing Preset'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    preset: EnumProperty(items=PRESET_ITEMS)

    def execute(self, context):
        ob = active_wing(context)
        (ob.mch_wing if ob is not None else context.scene.mch_wing).preset = self.preset
        if ob is not None:
            _BUSY[0] = True
            try:
                context.scene.mch_wing.preset = self.preset
            finally:
                _BUSY[0] = False
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_wing
    ob = active_wing(context)
    pg = ob.mch_wing if ob is not None else st
    col = layout.column(align=True)
    col.label(text=f'{ob.name}: {len(ob.data.polygons):,} faces (live)' if ob is not None else 'The next wing')
    g = layout.grid_flow(row_major=True, columns=3, even_columns=True, align=True)
    for pid, label, _s in PRESETS:
        g.operator('mch.wing_preset', text=label, depress=pg.preset == pid).preset = pid
    col = layout.column(align=True)
    for k in ('vein_height', 'vein_width', 'density', 'thickness', 'detail', 'seed'):
        col.prop(pg, k)
    col.prop(pg, 'flip')
    if ob is not None:
        layout.operator('mch.wing_apply', text='Apply (Enter)', icon='CHECKMARK')
    col = layout.column(align=True)
    for line in HELP:
        col.label(text=line)


HELP = ('Draw a wing\'s outline: the veins raised inside it',
        'Its root: the point nearest the body (else where you start)',
        'Select a wing: its sliders lay it again;  Enter: keep')

CLASSES = (MCH_PG_Wing, MCH_OT_wing_apply, MCH_OT_wing_preset)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_wing = PointerProperty(type=MCH_PG_Wing)
    bpy.types.Object.mch_wing = PointerProperty(type=MCH_PG_Wing)


def unregister():
    for T in (bpy.types.Scene, bpy.types.Object):
        if hasattr(T, 'mch_wing'):
            delattr(T, 'mch_wing')
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
