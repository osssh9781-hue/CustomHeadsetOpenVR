"""0.24.172 Feathers and real scales - light meshes for Feather Line and the Fur tool's Feathers / Scales.

    feathers (user: "깃털 탭도 만들어 줘, 이건 메쉬로 - 가벼운 메쉬, 깃털 모양 프리셋도 15 개 정도, 길이도 다양하게")
        a shaft (the rachis, raised) and two vanes either side, one surface of about 200 faces; the bare quill at the
        base, the vane's outline (where it is widest, the tip round / pointed / square, one vane wider than the
        other), the barbs' fringe along the edge, splits between barb groups, a notch near the tip (a flight
        feather's emargination), curved down / sideways / drooping, cupped across.  Origin at the quill's base, the
        length along +X, the vane's top up (+Z).  Points carry ``mch_feather_t`` (0 base .. 1 tip) for the colour.
    scales (user: "비늘도 좀 더 리얼하게, 지금은 너무 네모 동그라미 이래")
        closed meshes, thickest at the root and thin at the free edge where they overlap: a lizard's keeled scale, a
        fish's cycloid (growth rings) and ctenoid (a toothed back edge), a snake's belly scute, a dragon's shield
        (keel, serrated tip), a pangolin's (grooved, cupped), a crocodile's osteoderm (ridge, pits), a tubercle.
        Origin at the root edge, the free edge along +X.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from mathutils import Matrix, Vector

T_ATTR = 'mch_feather_t'

# (id, label, spec) - L: length (x the Part Size), W: the widest half-width x L, calamus: the bare quill (share of L),
# widest: where along the vane it is widest, tip: ROUND / POINT / SQUARE, asym: the right vane wider (left narrower),
# fringe: (depth, count) of the barbs' fringe at the edge, splits: gaps between barb groups, notch: (side, at, depth),
# bend / sweep / droop: curved down / sideways / drooping at the tip, cup: the vane's edges down, shaft: the rachis'
# height x W, start: the vane begins this far along (a crest's bare shaft), eye: a round widening at the tip
FEATHERS = (
    ('CONTOUR', 'Contour', dict(L=0.7, W=0.24, calamus=0.1, widest=0.45, tip='ROUND', cup=0.12, bend=0.05)),
    ('COVERT', 'Covert', dict(L=0.5, W=0.3, calamus=0.08, widest=0.55, tip='ROUND', cup=0.15, bend=0.04)),
    ('PRIMARY', 'Primary', dict(L=1.6, W=0.13, calamus=0.1, widest=0.4, tip='POINT', asym=0.45, bend=0.08,
                                sweep=0.07, notch=('L', 0.62, 0.45), cup=0.06)),
    ('SECONDARY', 'Secondary', dict(L=1.2, W=0.17, calamus=0.1, widest=0.55, tip='SQUARE', asym=0.3, bend=0.06,
                                    cup=0.08)),
    ('TAIL', 'Tail', dict(L=1.4, W=0.12, calamus=0.08, widest=0.7, tip='SQUARE', bend=0.03, cup=0.05)),
    ('DOWN', 'Down', dict(L=0.35, W=0.4, calamus=0.15, widest=0.5, tip='ROUND', fringe=(0.6, 10), cup=0.45,
                          bend=0.15, shaft=0.03)),
    ('PLUME', 'Plume', dict(L=1.5, W=0.32, calamus=0.06, widest=0.6, tip='ROUND', fringe=(0.4, 18), droop=0.35,
                            cup=0.1)),
    ('BLADE', 'Blade', dict(L=1.0, W=0.08, calamus=0.05, widest=0.3, tip='POINT', bend=0.02, cup=0.0, shaft=0.6)),
    ('OWL', 'Owl', dict(L=0.9, W=0.26, calamus=0.08, widest=0.6, tip='ROUND', fringe=(0.2, 16), cup=0.12,
                        bend=0.05)),
    ('NOTCHED', 'Hawk Primary', dict(L=1.6, W=0.14, calamus=0.1, widest=0.35, tip='POINT', asym=0.35, bend=0.09,
                                     notch=('B', 0.55, 0.5), cup=0.06)),
    ('PHEASANT', 'Pheasant Tail', dict(L=2.2, W=0.07, calamus=0.05, widest=0.25, tip='POINT', bend=0.04, sweep=0.03,
                                       cup=0.04)),
    ('CREST', 'Crest', dict(L=0.8, W=0.16, calamus=0.05, start=0.55, widest=0.8, tip='ROUND', fringe=(0.4, 12),
                            bend=-0.12, cup=0.05)),
    ('RIBBON', 'Ribbon', dict(L=1.8, W=0.045, calamus=0.04, widest=0.5, tip='ROUND', wave=(0.35, 6), cup=0.0,
                              bend=0.05)),
    ('PEACOCK', 'Peacock Eye', dict(L=2.0, W=0.06, calamus=0.05, start=0.1, widest=0.85, tip='ROUND', eye=0.2,
                                    fringe=(0.45, 16), droop=0.12, cup=0.05)),
    ('SPLIT', 'Ragged', dict(L=0.8, W=0.22, calamus=0.1, widest=0.5, tip='ROUND', splits=5, fringe=(0.2, 20),
                             cup=0.1, bend=0.06)),
)
FEATHER_IDS = tuple(f[0] for f in FEATHERS)


def _vane_width(u, spec):
    """The vane's half-width (0..1 of its widest) at ``u`` (0 the vane's start .. 1 the tip)."""
    w0 = spec.get('widest', 0.5)
    if u <= w0:
        base = (u / max(w0, 1e-6)) ** 0.45
    else:
        v = (u - w0) / max(1.0 - w0, 1e-6)
        tip = spec.get('tip', 'ROUND')
        if tip == 'POINT':
            base = max(0.0, 1.0 - v) ** 0.85
        elif tip == 'SQUARE':
            base = 1.0 if v < 0.75 else math.sqrt(max(0.0, 1.0 - ((v - 0.75) / 0.25) ** 2))
        else:
            base = math.sqrt(max(0.0, 1.0 - v * v))
    eye = spec.get('eye', 0.0)
    if eye > 0:                                       # (a peacock's eye: the vane narrow, widening round at the tip)
        base = 0.35 * base + eye / max(spec['W'], 1e-6) * math.exp(-((u - 0.88) / 0.1) ** 2)
    wave = spec.get('wave')
    if wave:
        base *= 1.0 + wave[0] * math.sin(u * wave[1] * 2 * math.pi)
    return max(base, 0.0)


def feather_mesh(spec, name='Feather', seed=1):
    """One feather (see the module) as a new mesh."""
    rng = random.Random(seed)
    L, W = 1.0, spec['W']                             # (unit length: the preset's L is set by the object's scale)
    fr = spec.get('fringe')
    ns = max(26, int(fr[1] * 2.2) + 4) if fr else 26  # (along: enough rows for the fringe's teeth; across each vane)
    nw = 4
    cal = spec.get('calamus', 0.08)
    start = max(cal, spec.get('start', 0.0))
    asym = spec.get('asym', 0.0)
    side = {'L': 1.0 - asym, 'R': 1.0 + asym * 0.6}
    fringe = spec.get('fringe')
    notch = spec.get('notch')
    splits = sorted(rng.uniform(0.25, 0.85) for _ in range(spec.get('splits', 0)))
    shaft_h = W * spec.get('shaft', 0.25)
    bm = bmesh.new()
    lt = bm.verts.layers.float.new(T_ATTR)
    rows = []
    for i in range(ns + 1):
        x = i / ns
        u = (x - start) / max(1.0 - start, 1e-6)       # (along the vane)
        row = []
        for j in range(-nw, nw + 1):
            a = j / nw                                  # (-1 left edge .. 0 the shaft .. +1 right edge)
            sd = 'L' if a < 0 else 'R'
            if u < 0:                                   # (the bare quill: a thin strip)
                half = W * 0.06 * (1.0 - x / max(start, 1e-6) * 0.3)
            else:
                half = W * _vane_width(u, spec) * side[sd]
                if notch is not None and notch[0] in (sd, 'B'):
                    half *= 1.0 - notch[2] * max(0.0, 1.0 - abs(u - notch[1]) / 0.12)
                if fringe is not None and abs(a) > 0.5:       # (the barbs' fringe: teeth toward the tip)
                    saw = (u * fringe[1] + (0.5 if sd == 'L' else 0.0)) % 1.0
                    half *= 1.0 - fringe[0] * ((abs(a) - 0.5) / 0.5) * saw
                half = max(half, W * 0.02)
            y = a * half
            z = -spec.get('cup', 0.1) * (a * a) * half      # (the vane's edges down: cupped)
            if j == 0:
                z += shaft_h * (1.0 - 0.7 * x)              # (the shaft raised)
            # curved along its length: down (bend), sideways (sweep), drooping at the tip (droop)
            z += -spec.get('bend', 0.0) * x * x - spec.get('droop', 0.0) * x ** 3
            y += spec.get('sweep', 0.0) * x * x
            v = bm.verts.new((x * L, y, z))
            v[lt] = x
            row.append(v)
        rows.append(row)
    gap_rows = set()
    for sp in splits:                                    # (a split between barb groups: a row of faces left out)
        i = int(round((start + sp * (1.0 - start)) * ns))
        gap_rows.add((min(max(i, 1), ns - 1), 'L' if rng.random() < 0.5 else 'R'))
    for i in range(ns):
        for j in range(2 * nw):
            sd = 'L' if j < nw else 'R'
            if (i, sd) in gap_rows and (j < nw - 1 or j > nw):
                continue
            bm.faces.new((rows[i][j], rows[i][j + 1], rows[i + 1][j + 1], rows[i + 1][j]))
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    if bm.faces and sum(f.normal.z for f in bm.faces) < 0:
        bmesh.ops.reverse_faces(bm, faces=bm.faces[:])
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me['mch_shape'] = 'FEATHER'
    return me


# ---- scales ---------------------------------------------------------------------------------------------------------
# (id, label, spec) - L / W: length (root to free edge) / width, H: thickness at the root, tip: ROUND / POINT / KITE /
# RECT, keel: a ridge along the middle (x H), rings: growth rings (count), teeth: a toothed free edge (count),
# grooves: grooves along it at the free edge (count), pits: dimples (strength), cup: the middle lower than the sides,
# cone: a cone (a tubercle)
SCALES = (
    ('KEELED', 'Keeled', dict(L=1.0, W=0.55, H=0.16, tip='POINT', keel=0.6)),
    ('CYCLOID', 'Cycloid (fish)', dict(L=1.0, W=0.95, H=0.08, tip='ROUND', rings=9)),
    ('CTENOID', 'Ctenoid (fish)', dict(L=1.0, W=0.9, H=0.09, tip='ROUND', rings=7, teeth=11)),
    ('VENTRAL', 'Belly Scute', dict(L=0.42, W=1.0, H=0.07, tip='RECT', bevel=0.25)),
    ('DRAGON', 'Dragon', dict(L=1.0, W=0.75, H=0.24, tip='KITE', keel=0.9, teeth=5)),
    ('PANGOLIN', 'Pangolin', dict(L=1.0, W=0.95, H=0.12, tip='ROUND', grooves=9, cup=0.35)),
    ('OSTEODERM', 'Osteoderm', dict(L=0.8, W=0.62, H=0.22, tip='RECT', keel=0.7, pits=0.25, bevel=0.35)),
    ('TUBERCLE', 'Tubercle', dict(L=0.6, W=0.6, H=0.4, tip='ROUND', cone=True, pits=0.15)),
)
SCALE_IDS = tuple(s[0] for s in SCALES)


def _outline(t, spec):
    """The scale's outline at angle ``t`` (0 = the free edge, +X): (x, y) about its middle, the length along x."""
    rx, ry = spec['L'] * 0.5, spec['W'] * 0.5
    c, s = math.cos(t), math.sin(t)
    tip = spec.get('tip', 'ROUND')
    if tip == 'RECT':                                 # (a rounded rectangle)
        p = 6.0
        r = 1.0 / ((abs(c) ** p + abs(s) ** p) ** (1.0 / p))
    else:
        r = 1.0
    x, y = rx * r * c, ry * r * s
    if tip == 'POINT' and c > 0:                      # (drawn to a point at the free edge)
        y *= 1.0 - 0.75 * c ** 2.5
    elif tip == 'KITE':                               # (a shield: broad at the root, a point at the free edge)
        y *= (1.0 - 0.8 * max(c, 0.0) ** 1.6) * (1.0 + 0.15 * max(-c, 0.0))
        x *= 1.0 + 0.15 * max(c, 0.0)
    teeth = spec.get('teeth', 0)
    if teeth and c > 0.35:                            # (a toothed free edge)
        k = (t / (2 * math.pi) * teeth * 4) % 1.0
        f = 1.0 - 0.08 * abs(2.0 * k - 1.0) * (c - 0.35) / 0.65
        x, y = x * f, y * f
    return x, y


def scale_mesh(spec, name='Scale', seg=48, rings=14, seed=1):
    """One scale (see the module) as a new closed mesh: a top surface over the outline, a flat bottom."""
    rng = random.Random(seed)
    H = spec['H']
    L = spec['L']
    bm = bmesh.new()
    pits = [(rng.uniform(-0.4, 0.4) * L, rng.uniform(-0.35, 0.35) * spec['W'], rng.uniform(0.04, 0.08) * L)
            for _ in range(10)] if spec.get('pits') else []

    def height(x, y, s):
        """The top's height over the bottom at (x, y) (about the middle), ``s`` 0 at the outline .. 1 the middle."""
        u = (x / L) + 0.5                              # (0 the root .. 1 the free edge)
        if spec.get('cone'):
            z = H * s ** 1.4
        else:
            z = H * (1.0 - 0.75 * u) * (1.0 - (1.0 - s) ** 2.2)      # (thick at the root, thin at the free edge)
            z *= 1.0 - spec.get('bevel', 0.0) * (1.0 - s) ** 3
        keel = spec.get('keel', 0.0)
        if keel:                                        # (a ridge along the middle, sharp-topped, rising to the free edge)
            z += H * keel * 0.55 * math.exp(-abs(y) / (spec['W'] * 0.06)) * (1.0 - (1.0 - s) ** 2) * (0.3 + 0.7 * u)
        cup = spec.get('cup', 0.0)
        if cup:
            z -= H * cup * math.exp(-(y / (spec['W'] * 0.3)) ** 2) * s * u
        rn = spec.get('rings', 0)
        if rn:                                          # (growth rings round the root, the grooves from it fanning out)
            rr = math.hypot(x + L * 0.5, y) / L
            z += H * 0.22 * (abs(math.sin(rr * rn * math.pi)) - 0.5) * min(1.0, s * 3.0)
            ang = math.atan2(y, x + L * 0.5)
            if u > 0.55:
                z -= H * 0.25 * max(0.0, math.cos(ang * 9.0)) ** 6 * (u - 0.55) / 0.45 * min(1.0, s * 3.0)
        gr = spec.get('grooves', 0)
        if gr and u > 0.35:                             # (grooves along it toward the free edge)
            z -= H * 0.35 * max(0.0, math.sin(y / spec['W'] * gr * math.pi)) ** 2 * (u - 0.35) / 0.65 * min(1.0, s * 3.0)
        for px, py, pr in pits:
            d = math.hypot(x - px, y - py)
            if d < pr:
                z -= H * spec['pits'] * (1.0 - d / pr) ** 2 * s
        return max(z, 0.0) + H * 0.02
    wob = [rng.uniform(-1.0, 1.0) for _ in range(5)]
    outline = []
    for k in range(seg):                                 # (a little uneven, as a grown scale is)
        t = 2 * math.pi * k / seg
        ox, oy = _outline(t, spec)
        f = 1.0 + 0.035 * sum(w * math.sin((i + 2) * t + i) for i, w in enumerate(wob)) / 2.0
        outline.append((ox * f, oy * f))
    grid = []
    for r in range(rings):                             # (rings from the outline in toward the middle)
        s = r / rings
        ring = []
        for (ox, oy) in outline:
            x, y = ox * (1.0 - s), oy * (1.0 - s)
            ring.append(bm.verts.new((x, y, height(x, y, s))))
        grid.append(ring)
    top = bm.verts.new((0.0, 0.0, height(0.0, 0.0, 1.0)))
    bottom = [bm.verts.new((ox, oy, 0.0)) for (ox, oy) in outline]
    for r in range(rings - 1):
        for k in range(seg):
            a, b = grid[r][k], grid[r][(k + 1) % seg]
            c, d = grid[r + 1][(k + 1) % seg], grid[r + 1][k]
            bm.faces.new((a, b, c, d))
    for k in range(seg):
        bm.faces.new((grid[-1][k], grid[-1][(k + 1) % seg], top))
        bm.faces.new((bottom[k], bottom[(k + 1) % seg], grid[0][(k + 1) % seg], grid[0][k]))   # (the rim)
    bm.faces.new(bottom[::-1])
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
    bmesh.ops.translate(bm, verts=bm.verts[:], vec=Vector((L * 0.5, 0.0, 0.0)))   # (the root edge at the origin)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    me['mch_shape'] = 'SCALE'
    return me


# ---- materials ------------------------------------------------------------------------------------------------------

def feather_material():
    """``MCH Feather``: darker at the base, lighter to the tip (``mch_feather_t``), a little sheen."""
    m = bpy.data.materials.get('MCH Feather')
    if m is not None:
        return m
    m = bpy.data.materials.new('MCH Feather')
    m.use_nodes = True
    nt = m.node_tree
    pb = nt.nodes.get('Principled BSDF')
    at = nt.nodes.new('ShaderNodeAttribute')
    at.attribute_name, at.attribute_type = T_ATTR, 'GEOMETRY'
    ramp = nt.nodes.new('ShaderNodeValToRGB')
    ramp.color_ramp.elements[0].color = (0.12, 0.08, 0.05, 1.0)
    ramp.color_ramp.elements[1].color = (0.62, 0.52, 0.4, 1.0)
    nt.links.new(at.outputs['Fac'], ramp.inputs['Fac'])
    nt.links.new(ramp.outputs['Color'], pb.inputs['Base Color'])
    pb.inputs['Roughness'].default_value = 0.55
    # the barbs: fine lines from the shaft out toward the tip either side (a V along it) - a bump, no extra mesh
    tc = nt.nodes.new('ShaderNodeTexCoord')
    sep = nt.nodes.new('ShaderNodeSeparateXYZ')
    nt.links.new(tc.outputs['Object'], sep.inputs[0])

    def math_(op, a, b=None):
        n = nt.nodes.new('ShaderNodeMath')
        n.operation = op
        for i, v in enumerate((a, b)):
            if v is None:
                continue
            if isinstance(v, bpy.types.NodeSocket):
                nt.links.new(v, n.inputs[i])
            else:
                n.inputs[i].default_value = v
        return n.outputs[0]
    v = math_('SUBTRACT', sep.outputs['X'], math_('MULTIPLY', math_('ABSOLUTE', sep.outputs['Y']), 1.6))
    lines = math_('POWER', math_('ABSOLUTE', math_('SINE', math_('MULTIPLY', v, 260.0))), 0.6)
    bump = nt.nodes.new('ShaderNodeBump')
    bump.inputs['Strength'].default_value = 0.35
    bump.inputs['Distance'].default_value = 0.002
    nt.links.new(lines, bump.inputs['Height'])
    nt.links.new(bump.outputs['Normal'], pb.inputs['Normal'])
    for sock, v in (('Sheen Weight', 0.5), ('Subsurface Weight', 0.0)):
        try:
            pb.inputs[sock].default_value = v
        except KeyError:
            pass
    m.diffuse_color = (0.4, 0.33, 0.25, 1.0)
    return m


def scale_material():
    m = bpy.data.materials.get('MCH Scale')
    if m is not None:
        return m
    m = bpy.data.materials.new('MCH Scale')
    pb = m.node_tree.nodes.get('Principled BSDF')
    pb.inputs['Base Color'].default_value = (0.2, 0.26, 0.14, 1.0)
    pb.inputs['Roughness'].default_value = 0.4
    try:
        pb.inputs['Coat Weight'].default_value = 0.3
    except KeyError:
        pass
    m.diffuse_color = (0.2, 0.26, 0.14, 1.0)
    return m


def feather_meshes():
    """[(name, mesh)] for the 15 feathers (each scaled to its preset length by its object - see ``FEATHER_LENGTHS``)."""
    out = []
    for i, (fid, label, spec) in enumerate(FEATHERS):
        me = feather_mesh(spec, f'Feather {label}', seed=i + 1)
        me.materials.append(feather_material())
        me['mch_shape_id'] = fid
        out.append((f'Feather {label}', me))
    return out


FEATHER_LENGTHS = {fid: spec['L'] for fid, _l, spec in FEATHERS}


def scale_meshes_real():
    out = []
    for i, (sid, label, spec) in enumerate(SCALES):
        me = scale_mesh(spec, f'Scale {label}', seed=i + 3)
        me.materials.append(scale_material())
        me['mch_shape_id'] = sid
        out.append((f'Scale {label}', me))
    return out
