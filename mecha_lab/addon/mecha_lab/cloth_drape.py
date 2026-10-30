"""0.24.92 Cloth Drape: lasso a region on a mesh, a loose cloth is laid over it (the way a garment is draped in
Marvelous Designer) and drops onto the body.

    1. the outline is meshed into an even patch (Armor Plate's meshing) and projected onto the mesh under it;
    2. the patch, a little above the surface and bigger by Looseness, is the cloth: its rim is pinned where it
       was (the sewn edge), gravity pulls it, the mesh points under the patch - and only those - are baked into a
       light distance grid (``cloth_pbd.GridCollider``) the cloth cannot pass through and sticks to (friction);
    3. the cloth is its own object ("Cloth Drape") from the first frame: Space runs / pauses the frames on a
       timer, Enter keeps the object, Esc removes it.  Every setting is a slider (saved in Tool Presets).
    Or **Drape This Mesh**: the active mesh itself (a remeshed piece of your own) is the cloth, laid as it is on
    the other selected mesh (or its parent) - its open edges are the rim, selected points stay too; Enter keeps
    the mesh changed, Esc puts the saved copy back.
    In every mode the wrinkle lines drawn on the body (the Wrinkle Lines tool, Draw Lines button) are tubes on the
    collider: the cloth catches and folds on them (Lines as Tubes; the tube sliders are the Wrinkle Lines ones).
    Or **Wrap This Mesh**: a cloth round the whole body like a wrapping cloth (bojagi) - a copy of the body (a
    light one for a heavy body), lifted off by Gap and bigger by Looseness, pressed onto the body by Wrap Pressure
    (like vacuum packing) so the excess fabric bunches into wrinkles; a new "Cloth Wrap" object.
"""
from __future__ import annotations

import math
import time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector

from . import core_geometry as cg
from . import mesh_io as mio
from . import wrinkle_lines as wl

GAP = 0.6                        # the cloth starts this x the patch spacing above the surface
MARGIN = 0.3                     # ... and rests this x spacing above the collider
GRID_BAND = 2
ITERATIONS = 6
SOR = 1.3
KEEP_SCALE = 0.1
KEEP_RATE = 0.3
PAD = 0.2                        # the collider takes the mesh points this x the patch size round the patch
GRAV = wl.GRAV_UNIT * 1.5        # gravity 100 % on the drape = the probe's "x1.5" of the Wrinkle Lines unit


class MCH_PG_ClothDrape(bpy.types.PropertyGroup):
    fabric: EnumProperty(name='Fabric', items=wl.FABRIC_ITEMS, default='COTTON')
    mask_points: IntProperty(name='Cloth Points', description='Drape Mask: the masked faces are rebuilt as an even, lighter cloth of about this many points '
                             '(0 = from Cloth Detail; never more points than the body has there)', default=0, min=0, max=200000)
    spacing: FloatProperty(name='Cloth Detail', description='The patch spacing as % of the outline size (smaller = more points, finer folds)',
                           default=1.5, min=0.4, max=6.0, subtype='PERCENTAGE')
    slack: FloatProperty(name='Looseness', description='Extra fabric: the cloth is this much bigger than the region, so it sags and bunches',
                         default=25.0, min=0.0, max=80.0, subtype='PERCENTAGE')
    shrink: FloatProperty(name='Shrink', description='The cloth pulled tight (against Looseness)',
                          default=0.0, min=0.0, max=60.0, subtype='PERCENTAGE')
    gravity: FloatProperty(name='Gravity', description='How hard the cloth drops (world down); below 0 it floats UP instead (0.24.95)', default=200.0, min=-600.0, max=600.0, subtype='PERCENTAGE')
    stick: FloatProperty(name='Stickiness', description='Friction against the body: 0 slides, 100 sticks where it lands',
                         default=30.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    keep: FloatProperty(name='Silhouette Keep', description='A soft spring back to the laid patch', default=5.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    gap: FloatProperty(name='Gap', description='How far above the body the cloth rests, as % of the outline size',
                       default=0.6, min=0.0, max=5.0, subtype='PERCENTAGE')
    wrap_tight: FloatProperty(name='Wrap Pressure', description='Wrap This Mesh / Sew Copy: how hard the loose cloth is pressed onto the body (like vacuum packing) - the excess fabric (Looseness) bunches into wrinkles',
                              default=50.0, min=0.0, max=200.0, subtype='PERCENTAGE')
    wrap_points: IntProperty(name='Wrap Points', description='Wrap This Mesh: the cloth copy is kept to about this many points (a decimated copy of a heavy body)',
                             default=40000, min=1000, soft_max=300000)
    use_lines: BoolProperty(name='Lines as Tubes', description='The wrinkle lines drawn on the body (Wrinkle Lines tool) become tubes under the cloth: it catches and folds on them',
                            default=True)
    thickness: FloatProperty(name='Thickness', description='The cloth gets a Solidify modifier of this thickness (% of the outline / body size; 0 = a single surface)',
                             default=0.0, min=0.0, max=5.0, subtype='PERCENTAGE')
    pin_rim: BoolProperty(name='Pin Rim', description='The outline edge stays where it was drawn (sewn on); off: the cloth is free. Front + Back: only the top edge is held', default=True)
    puff: FloatProperty(name='Puff', description='Sew Copy: the pressure that lifts the cloth away from the plate it is sewn to (a pillow / padding); 0 = only gravity and looseness',
                        default=50.0, min=0.0, max=200.0, subtype='PERCENTAGE')
    two_sides: BoolProperty(name='Front + Back', description='The lasso also makes a back piece on the far side of the body and the two are sewn together down the sides (the top and bottom stay open), like front / back pattern pieces in Marvelous Designer',
                            default=False)
    stop_at_pins: BoolProperty(name='Stop at Pins', description='The cloth cannot hang lower (world down) than the lowest pinned point', default=False)
    wrinkles: FloatProperty(name='Wrinkles', description='How much the cloth folds: 0 = smooth broad folds, 100 = wide bending (points up to 4 edges apart hold their distance, little smoothing, a little jitter) - folds a few cells wide wherever the fabric is loose',
                            default=50.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    frames: IntProperty(name='Frames', default=60, min=5, max=300)
    # 0.24.95 Padding (quilting): seam lines held down on the body, the cells between them puffed up
    padding: BoolProperty(name='Padding', description='Quilted padding: a pattern of seam lines is held on the body and the cloth between them puffs up (needs some Looseness)', default=False)
    pad_pattern: EnumProperty(name='Pattern', items=[('SQUARE', 'Square', 'Seams along and across the outline'), ('DIAMOND', 'Diamond', 'Seams at 45 degrees'),
                                                     ('NONE', 'Whole', 'No seams: the whole drawn area puffs up as one cushion (the rim held)')], default='DIAMOND')
    pad_size: FloatProperty(name='Cell', description='Padding: the seam spacing as % of the outline size', default=15.0, min=3.0, max=60.0, subtype='PERCENTAGE')
    pad_puff: FloatProperty(name='Puff', description='Padding: how hard the cells are blown up between the seams', default=60.0, min=0.0, max=200.0, subtype='PERCENTAGE')
    # 0.24.95 Trim: a piping tube round the cloth's edge, made when the cloth is kept
    trim: BoolProperty(name='Trim', description='A round piping along the cloth edge (its own object "Cloth Trim", child of the cloth) when the cloth is kept', default=False)
    trim_width: FloatProperty(name='Trim Width', description='The piping thickness as % of the outline size', default=1.5, min=0.2, max=8.0, subtype='PERCENTAGE')


def settings(context):
    return getattr(context.scene, 'mch_cdrape', None)


# -----------------------------------------------------------------------------
# the patch + the drape (plain functions)
# -----------------------------------------------------------------------------


def _screen_patch(context, loops, projector, spacing_pct):
    from . import armor_plate as ap
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the cloth over a mesh.')
    outline = [p for outer, _h in groups for p in outer]
    xs = [p[0] for p in outline]
    ys = [p[1] for p in outline]
    size_px = max(max(xs) - min(xs), max(ys) - min(ys), 1.0)
    pts, tris, nb = ap.screen_patch(groups, spacing=size_px * spacing_pct / 100.0, min_spacing=2.0)
    if not tris:
        raise cg.CutError('The outline is too small for a cloth.')
    return target, pts, tris, nb


def _project_local(context, target, pts, projector, bvh):
    from . import armor_plate as ap
    cos, nrms, _missing = ap.project_patch(pts, projector, bvh)
    inv = target.matrix_world.inverted_safe()
    rot = inv.to_3x3()
    return [inv @ c for c in cos], [(rot @ n).normalized() for n in nrms]


def _bbox_size(cos_l):
    lo = Vector([min(c[k] for c in cos_l) for k in range(3)])
    hi = Vector([max(c[k] for c in cos_l) for k in range(3)])
    return max((hi - lo).length, 1e-6)


def patch_from_loops(context, loops, projector, spacing_pct):
    """The outline meshed and projected: (target, mesh (local space of target), rim point count, outline size)."""
    from . import armor_plate as ap
    target, pts, tris, nb = _screen_patch(context, loops, projector, spacing_pct)
    bvh, _wv, _polys = ap._target_bvh(context, target)
    cos_l, nrm_l = _project_local(context, target, pts, projector, bvh)
    me = ap.build_region(pts, tris, cos_l, nrm_l, quads=True)
    me.name = 'MCH_ClothDrape'
    store_uv(me, pts)
    return target, me, nb, _bbox_size(cos_l)


UV_ATTR = '.mch_pad_uv'          # point FLOAT2: the patch point's place in the drawn outline (0..1 of its size)


def store_uv(me, pts):
    """The screen coordinates of the patch points, scaled by the outline size, kept on the mesh (Padding lays its
    seam pattern out in them: a straight grid in the view, however the body bends)."""
    P = np.asarray(pts, np.float64)[:len(me.vertices)]
    if len(P) != len(me.vertices):
        return
    lo = P.min(0)
    size = max(float((P.max(0) - lo).max()), 1e-9)
    a = me.attributes.get(UV_ATTR)
    if a is None or a.domain != 'POINT' or a.data_type != 'FLOAT2':
        if a is not None:
            me.attributes.remove(a)
        a = me.attributes.new(UV_ATTR, 'FLOAT2', 'POINT')
    a.data.foreach_set('vector', ((P - lo) / size).ravel())


def read_uv(me):
    a = me.attributes.get(UV_ATTR)
    if a is None or a.domain != 'POINT':
        return None
    out = np.empty(len(me.vertices) * 2, np.float64)
    a.data.foreach_get('vector', out)
    return out.reshape(-1, 2)


def quilt_lines(uv, cell, width, pattern='DIAMOND'):
    """bool per point: on a seam of the quilting pattern - lines every ``cell`` (outline units) in both directions,
    a point counts when it is within ``width`` of one; DIAMOND turns the grid by 45 degrees."""
    P = np.asarray(uv, np.float64)
    if pattern == 'DIAMOND':
        c, s_ = math.cos(math.pi / 4), math.sin(math.pi / 4)
        P = np.stack([P[:, 0] * c - P[:, 1] * s_, P[:, 0] * s_ + P[:, 1] * c], 1)
    m = np.mod(P, cell)
    d = np.minimum(m, cell - m)
    return (d[:, 0] <= width) | (d[:, 1] <= width)


class _BackProjector:
    """The same view rays cast back from behind the body: the far side of the surface."""

    def __init__(self, projector, far):
        self.p = projector
        self.far = far
        self.view_dir = -projector.view_dir
        self.is_perspective = False
        self.eye = projector.eye + projector.view_dir * far

    def ray(self, xy):
        o, d = self.p.ray(xy)
        return o + d * self.far, -d

    def to_screen(self, co):
        return self.p.to_screen(co)


def rim_classes(pts, nb):
    """The outline points (the first ``nb`` of ``pts``, loop order) sorted into the seams: 'side' where the outline
    runs more up-down than across (sewn), else 'top' / 'bottom' by the outline's mid height (open)."""
    P = np.asarray(pts[:nb], np.float64)
    if nb < 3:
        return np.zeros(nb, bool), np.zeros(nb, bool), np.zeros(nb, bool)
    t = np.roll(P, -1, 0) - np.roll(P, 1, 0)
    side = np.abs(t[:, 1]) > np.abs(t[:, 0])
    mid = 0.5 * (P[:, 1].max() + P[:, 1].min())
    top = ~side & (P[:, 1] > mid)
    bottom = ~side & ~top
    return side, top, bottom


def patch_two_sides(context, loops, projector, spacing_pct):
    """Front + Back: the outline projected on the near side AND the far side of the body - two pattern pieces in one
    mesh (the front's points first).  Returns (target, mesh, rim point count, size, info) with info['sew'] the
    (M, 2) side-seam pairs (front point, back point), info['top'] / info['bottom'] the open edges' point indices
    (both pieces)."""
    from . import armor_plate as ap
    target, pts, tris, nb = _screen_patch(context, loops, projector, spacing_pct)
    bvh, _wv, _polys = ap._target_bvh(context, target)
    mw = target.matrix_world
    corners = [mw @ Vector(c) for c in target.bound_box]
    o0, d0 = projector.ray(pts[0])
    far = max((c - o0).dot(d0) for c in corners) + max((corners[6] - corners[0]).length, 1e-3)
    front_l, front_n = _project_local(context, target, pts, projector, bvh)
    back_l, back_n = _project_local(context, target, pts, _BackProjector(projector, far), bvh)
    me_f = ap.build_region(pts, tris, front_l, front_n, quads=True)
    me_b = ap.build_region(pts, tris, back_l, back_n, quads=True)
    try:
        if len(me_f.vertices) != len(pts) or len(me_b.vertices) != len(pts):
            raise cg.CutError('Front + Back: the outline could not be meshed on both sides')
        nf = len(pts)
        verts = [v.co[:] for v in me_f.vertices] + [v.co[:] for v in me_b.vertices]
        faces = [tuple(p.vertices) for p in me_f.polygons] + [tuple(i + nf for i in p.vertices) for p in me_b.polygons]
    finally:
        bpy.data.meshes.remove(me_f)
        bpy.data.meshes.remove(me_b)
    me = bpy.data.meshes.new('MCH_ClothDrape')
    me.from_pydata(verts, [], faces)
    me.update()
    side, top, bottom = rim_classes(pts, nb)
    idx = np.arange(nb)
    sew = np.stack([idx[side], idx[side] + nf], 1) if np.any(side) else np.zeros((0, 2), np.int64)
    near_seam = np.roll(side, 1) | np.roll(side, -1) | np.roll(side, 2) | np.roll(side, -2)
    top_pin = top & ~near_seam                       # (the top edge is held, but not right next to the seam: no notch)
    info = dict(sew=sew, top=np.concatenate([idx[top_pin], idx[top_pin] + nf]), bottom=np.concatenate([idx[bottom], idx[bottom] + nf]),
                front=nf, far=far)
    return target, me, nb, _bbox_size(front_l + back_l), info


def surface_samples(*a, **k):
    """(0.24.95: lives in cloth_pbd, shared with Wrinkle Lines)"""
    from . import cloth_pbd as _pbd
    return _pbd.surface_samples(*a, **k)


def build(context, target, me, nb, size, st, to_cloth=None, pin_sel=False, gdir_ob=None, wrap=False, sew=None, pin_idx=None, puff=False):
    """The cloth + the collider for the mesh ``me``: a lasso patch (local space of ``target``, the first ``nb``
    points its rim) or (``to_cloth``: the matrix that brings the target's points into the cloth's space) a mesh
    of its own laid on ``target``.  Returns the session."""
    from . import cloth_pbd
    co = mio.read_co(me)
    n = len(co)
    nrm = wl._normals(me)
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    edges = cloth_pbd.edges_of(vi.astype(np.int64), start.astype(np.int64), tot.astype(np.int64))[0]
    spacing = float(np.mean(np.linalg.norm(co[edges[:, 1]] - co[edges[:, 0]], axis=1))) if len(edges) else size * 0.02
    gap = size * st.gap / 100.0
    margin = max(spacing * MARGIN, gap * 0.5)
    cloth_co = co + nrm * (gap + spacing * GAP)
    pin = np.zeros(n)
    if sew is not None:                               # front + back pieces: the seams hold them, only the top edge pinned
        if st.pin_rim and pin_idx is not None and len(pin_idx):
            pin[np.asarray(pin_idx, np.int64)] = 1.0
    elif st.pin_rim and wrap:                         # a wrapped tube: its open ends held firmly
        rim = wl.boundary_verts(me)
        if len(rim):
            pin[rim] = 1.0
    elif st.pin_rim:
        if to_cloth is None and not puff and nb > 0:
            pin[:min(nb, n)] = 1.0
        else:                                         # a mesh of its own / a sewn copy: its open edges are the rim
            rim = wl.boundary_verts(me)
            if len(rim):
                pin[rim] = 1.0
    if pin_sel:
        sel = np.zeros(n, bool)
        me.vertices.foreach_get('select', sel)
        pin[sel] = 1.0
    n_quilt = 0
    uv = read_uv(me) if getattr(st, 'padding', False) and sew is None and not wrap and not puff and to_cloth is None else None
    pad_on = uv is not None
    if uv is not None and st.pad_pattern != 'NONE':    # 0.24.95 Padding: the seam lines held, the cells puffed
        uv_edge = float(np.mean(np.linalg.norm(uv[edges[:, 1]] - uv[edges[:, 0]], axis=1))) if len(edges) else 0.02
        on = quilt_lines(uv, st.pad_size / 100.0, uv_edge * 0.55, st.pad_pattern)
        pin[on] = 1.0
        n_quilt = int(on.sum())
    fabric = wl.FABRIC_SIM.get(st.fabric, wl.FABRIC_SIM['COTTON'])
    friction, damping = fabric[1], fabric[2]
    bend, smooth, far_scale, jit = wl.wrinkle_params(fabric, getattr(st, 'wrinkles', 0.0))
    cloth = cloth_pbd.Cloth(cloth_co, vi, start, tot, bend=bend, keep=st.keep / 100.0 * KEEP_SCALE, pin=pin)
    cloth.sor = SOR
    cloth.smooth = smooth
    if far_scale > 0:                                     # 0.24.93 wide bending: folds a few cells wide, not cell noise
        cloth.set_far()
        cloth.far_scale = far_scale
    scale = (1.0 - st.shrink / 100.0) * (1.0 + st.slack / 100.0)
    cloth.scale_e = cloth.scale_b = scale
    if np.any(pin >= 1) and scale != 1.0:            # the fabric next to a seam cannot be loose at once: taper over 4 rings
        ring = np.full(n, 99, np.int64)
        ring[pin >= 1] = 0
        a, b = cloth.edges[:, 0], cloth.edges[:, 1]
        for k in range(1, 5):
            nb_ring = np.minimum(ring[a], ring[b]) + 1
            upd = np.minimum(ring[a], nb_ring)
            np.minimum.at(ring, a, upd)
            np.minimum.at(ring, b, np.minimum(ring[b], nb_ring))
        tap = np.clip(ring / 4.0, 0.0, 1.0)
        tap_e = np.minimum(tap[a], tap[b])
        cloth.scale_e = 1.0 + (scale - 1.0) * tap_e
        ba, bb = cloth.bends[:, 0], cloth.bends[:, 1]
        cloth.scale_b = 1.0 + (scale - 1.0) * np.minimum(tap[ba], tap[bb])
    cloth.max_step = max(spacing * 1.5, size * 0.01)
    if jit > 0:
        cloth.jitter(spacing * jit)
    cloth.init = cloth_co.copy()
    if sew is not None and len(sew):
        cloth.sew = np.asarray(sew, np.int64)         # (the pairs; the pull itself is seam_pull in the collide pass)
        cloth.sew_pbd = False
        cloth.sew_strength = 0.0                      # ramped up over the first frames (advance)
    # the collider: the target's points near the patch only, with their normals, baked into a grid
    tco = mio.read_co(target.data)
    tn = wl._normals(target.data)
    tubes = 0
    lines = wl._lines_of(target) if st.use_lines else []
    if lines:                                         # the drawn lines as tubes on the body: the cloth catches on them
        wst = wl.settings(context)
        tgt = wl.target_of(context, target)
        paths = [np.array([list(p) for p in wl.line_path(tgt, ln)]) for ln in lines]
        tube_r = tgt.size * wst.size / 100.0 * wl.TUBE
        h = wl.tube_field(tco, paths, [ln['strength'] for ln in lines], tube_r, fade=wst.fade / 100.0, lift=wst.lift / 100.0)
        sign = -1.0 if wst.mode == 'CREASE' else 1.0
        tco = tco + tn * (h * tube_r * sign * wst.fold / 100.0)[:, None]
        tubes = int(np.count_nonzero(h > 0.05))
    if to_cloth is not None:
        M = np.array(to_cloth, np.float64)
        tco = tco @ M[:3, :3].T + M[:3, 3]
        R = np.linalg.inv(M[:3, :3]).T
        tn = tn @ R.T
        tn /= np.maximum(np.linalg.norm(tn, axis=1), 1e-12)[:, None]
    lo, hi = co.min(0) - size * PAD, co.max(0) + size * PAD
    if to_cloth is not None or wrap or sew is not None or puff:    # a mesh of its own may slide far down the body: the whole body
        near = np.ones(len(tco), bool) if len(tco) <= 400000 else np.all((tco >= lo - size * 2) & (tco <= hi + size * 2), axis=1)
    else:
        near = np.all((tco >= lo) & (tco <= hi), axis=1)
    t = time.perf_counter()
    cell = max(spacing * 0.8, size / 160.0)
    # 0.24.95 the body's FACES are sampled too, not just its points: a big flat face has no points across it, and
    # the grid's narrow band round the points left holes the cloth fell through (the user's recessed floor showed
    # through the wrinkles)
    sco, snrm = surface_samples(target.data, tco, tn, near, cell * GRID_BAND, lo - size * 2, hi + size * 2)   # (samples 2 cells
    #                                                                                   apart: the band round each is 2 cells, no cell left empty between them)
    if not len(sco):
        raise cg.CutError('The body is nowhere near the cloth')
    grid = cloth_pbd.GridCollider(sco - snrm * (gap - margin) if gap > margin else sco, snrm, cell=cell, band=GRID_BAND)
    sess = dict(cloth=cloth, grid=grid, margin=margin, friction=st.stick / 100.0, damping=damping, wrap=wrap, tubes=tubes,
                spacing=spacing,
                sew=int(len(sew)) if sew is not None else 0,
                puff=(size * 0.0015 * st.puff / 50.0) if puff else 0.0, puff_dir=nrm.copy() if puff else None,
                puff_max=size * 0.35 * (st.slack / 100.0) ** 0.5 if puff else 0.0,
                press=(size * 0.004 * st.wrap_tight / 50.0) if (wrap or puff) else 0.0,
                gdir=wl._gravity_dir(gdir_ob or target), size=size, frames=st.frames, frame=0, points=n, collider=int(len(sco)),
                grid_time=time.perf_counter() - t, stage='run')

    if pad_on:                                        # the padding's puff: the cells (or the whole area: Whole) blow up
        cell = st.pad_size / 100.0 if st.pad_pattern != 'NONE' else 1.0
        sess.update(puff=size * 0.0015 * st.pad_puff / 50.0, puff_dir=nrm.copy(),
                    puff_max=size * cell * 0.6 * max(0.15, st.slack / 100.0) ** 0.5, quilt=n_quilt)

    def collide(c):
        touch = grid.push(c.co, sess['margin'])
        fr = sess['friction']
        if fr > 0 and np.any(touch):
            c.co[touch] += (c.prev[touch] - c.co[touch]) * fr
        if c.sew is not None and c.sew_strength > 0:
            c.co += seam_pull(sess, c.sew_strength)
    cloth.collide = collide
    if st.stop_at_pins and np.any(pin >= 1):              # nothing hangs below the lowest pinned point
        cloth.floor = (sess['gdir'], float((cloth_co[pin >= 1] @ sess['gdir']).max()) + spacing * 0.5)
    return sess


SEW_RAMP = 0.3                   # the seams pull at full strength after this share of the frames
GRAB_PX = 40.0                   # 0.24.95 grab: the nearest cloth point within this many pixels of the click
GRAB_RADIUS = 4.0                # ... pulls the points within this x the patch spacing with it (smooth falloff)


def seam_pull(sess, strength):
    """The seams' pull (one constraint pass) that slides ALONG the body: the straight line between a front point
    and its back point runs through the body, so the pull's part into the surface is dropped and each end walks
    round the side toward the other (the way a sewn piece is drawn round an avatar); once the two are within a
    step of each other they close straight.  Capped per pass at half the cloth's step (no tunnelling)."""
    cloth = sess['cloth']
    a, b = cloth.sew[:, 0], cloth.sew[:, 1]
    d = cloth.co[b] - cloth.co[a]
    L = np.linalg.norm(d, axis=1)
    L[L < 1e-12] = 1e-12
    _da, na = sess['grid'].inward(cloth.co[a])
    _db, nb_ = sess['grid'].inward(cloth.co[b])
    cap = cloth.max_step * 0.5 if cloth.max_step > 0 else L.max()
    close = (L < cap * 2.0)[:, None]
    ta = np.where(close, d, d - na * (d * na).sum(1)[:, None])
    tb = np.where(close, -d, -d - nb_ * ((-d) * nb_).sum(1)[:, None])
    amt = np.minimum(L * 0.5 * strength, cap)
    force = np.zeros_like(cloth.co)
    for t, idx in ((ta, a), (tb, b)):
        ln = np.linalg.norm(t, axis=1)
        ok = ln > 1e-9
        np.add.at(force, idx[ok], t[ok] / ln[ok][:, None] * amt[ok][:, None])
    return force


def advance(sess, st):
    cloth = sess['cloth']
    force = None
    if cloth.sew is not None:
        cloth.sew_strength = min(1.0, (sess['frame'] + 1) / max(1.0, sess['frames'] * SEW_RAMP))
    g = sess['gdir'] * (GRAV * st.gravity / 100.0 * sess['size'])
    if sess.get('press', 0.0) > 0:                               # the wrap's pressure: every point toward the body / plate
        d, inward = sess['grid'].inward(cloth.co)
        f = inward * sess['press']
        f[d <= sess['margin'] * 1.2] = 0.0
        force = f if force is None else force + f
    if sess.get('puff', 0.0) > 0 and sess.get('puff_dir') is not None:   # the sewn copy's pillow: away from the plate
        lift = ((cloth.co - cloth.init) * sess['puff_dir']).sum(1)            # how far off the plate already
        room = np.clip(1.0 - lift / max(sess['puff_max'], 1e-9), 0.0, 1.0)   # the extra fabric sets the height
        f = sess['puff_dir'] * (sess['puff'] * room * (1.0 - cloth.pin))[:, None]
        force = f if force is None else force + f
    cloth.step(force=force, gravity=g, damping=sess['damping'], iterations=ITERATIONS,
               keep_rate=KEEP_RATE if st.keep > 0 else 0.0)
    sess['frame'] += 1
    return cloth.co


# -----------------------------------------------------------------------------
# 0.24.95 grab: drag the cloth while it drapes (user: "중간중간 메시에 들어갈 때가 있어서 잡아서 뗄 수 있게")
# -----------------------------------------------------------------------------


def grab_pick(sess, xy, mouse, spacing):
    """The grab for a click at ``mouse`` (px): ``xy`` (N, 2) the cloth points on screen (NaN = behind the view).
    Returns dict(idx, w, start) - the nearest point within GRAB_PX and the points within GRAB_RADIUS x spacing of
    it (weights 1 at the centre, 0 at the rim) - or None.  Pinned points are not taken."""
    cloth = sess['cloth']
    d2 = ((xy - np.asarray(mouse, np.float64)[None, :]) ** 2).sum(1)
    d2[~np.isfinite(d2)] = np.inf
    d2[cloth.pin >= 1.0] = np.inf
    k = int(np.argmin(d2))
    if not d2[k] <= GRAB_PX ** 2:
        return None
    r = max(spacing * GRAB_RADIUS, 1e-9)
    dist = np.linalg.norm(cloth.co - cloth.co[k][None, :], axis=1)
    idx = np.nonzero((dist < r) & (cloth.pin < 1.0))[0]
    w = (1.0 - (dist[idx] / r) ** 2) ** 2
    return dict(idx=idx, w=w, start=cloth.co[idx].copy(), centre=k)


def grab_move(sess, grab, offset, running):
    """The grabbed points follow the hand: ``offset`` (3,) in the cloth's space.  While the drape runs they are
    held there every pass (``Cloth.hold``); paused, they are put there straight away."""
    cloth = sess['cloth']
    idx, w = grab['idx'], grab['w']
    target = grab['start'] + np.asarray(offset, np.float64)[None, :] * w[:, None]
    cloth.hold = (idx, w, target)
    if not running:
        cloth.co[idx] = target
        cloth.prev[idx] = target
    return target


def grab_release(sess, grab):
    """Let go: the points stay where they are, with no velocity to fling them."""
    cloth = sess['cloth']
    cloth.hold = None
    cloth.prev[grab['idx']] = cloth.co[grab['idx']]


def _screen_xy(region, rv3d, matrix, co):
    """(N, 2) pixel positions of local points ``co`` seen through the view (NaN behind the eye)."""
    m = np.array(rv3d.perspective_matrix @ matrix, np.float64)
    h = co @ m[:3, :3].T + m[:3, 3][None, :]
    w = co @ m[3, :3] + m[3, 3]
    with np.errstate(divide='ignore', invalid='ignore'):
        ndc = h[:, :2] / w[:, None]
    xy = np.empty_like(ndc)
    xy[:, 0] = (ndc[:, 0] + 1.0) * 0.5 * region.width
    xy[:, 1] = (ndc[:, 1] + 1.0) * 0.5 * region.height
    xy[w <= 1e-9] = np.nan
    return xy


def grab_start_event(context, event):
    """Left press in the 3D view: pick the cloth under the mouse.  Returns True when a grab began."""
    ob = _ob()
    sess = SIM.get('sess')
    region, rv3d = context.region, context.region_data
    if ob is None or sess is None or region is None or rv3d is None:
        return False
    cloth = sess['cloth']
    xy = _screen_xy(region, rv3d, ob.matrix_world, cloth.co)
    grab = grab_pick(sess, xy, (event.mouse_region_x, event.mouse_region_y), sess.get('spacing', sess['size'] * 0.02))
    if grab is None:
        return False
    from bpy_extras import view3d_utils
    anchor = ob.matrix_world @ Vector(cloth.co[grab['centre']])
    grab['anchor'] = anchor
    grab['inv'] = ob.matrix_world.inverted_safe().to_3x3()
    hit = view3d_utils.region_2d_to_location_3d(region, rv3d, (event.mouse_region_x, event.mouse_region_y), anchor)
    grab['mouse0'] = hit if hit is not None else anchor
    SIM['grab'] = grab
    return True


def grab_move_event(context, event):
    ob = _ob()
    sess, grab = SIM.get('sess'), SIM.get('grab')
    region, rv3d = context.region, context.region_data
    if ob is None or sess is None or grab is None or region is None or rv3d is None:
        return
    from bpy_extras import view3d_utils
    hit = view3d_utils.region_2d_to_location_3d(region, rv3d, (event.mouse_region_x, event.mouse_region_y), grab['anchor'])
    if hit is None:
        return
    offset = grab['inv'] @ (hit - grab['mouse0'])            # the hand's move in the cloth's space (view plane)
    grab_move(sess, grab, np.array(offset[:], np.float64), bool(SIM.get('running')))
    if not SIM.get('running'):
        mio.write_co(ob.data, sess['cloth'].co)
        ob.data.update()


def grab_end_event():
    sess, grab = SIM.get('sess'), SIM.pop('grab', None)
    if sess is not None and grab is not None:
        grab_release(sess, grab)


def drape(context, target, me, nb, size, st, frames=None, sew=None, pin_idx=None):
    """Headless / one go: the patch mesh draped in place.  Returns info."""
    t = time.perf_counter()
    sess = build(context, target, me, nb, size, st, sew=sew, pin_idx=pin_idx)
    for _ in range(frames if frames is not None else st.frames):
        advance(sess, st)
    mio.write_co(me, sess['cloth'].co)
    me.update()
    info = dict(points=sess['points'], collider=sess['collider'], frames=sess['frame'], time=time.perf_counter() - t,
                grid_cells=sess['grid'].cells, inside=int((sess['grid'].distance(sess['cloth'].co) < sess['margin'] * 0.5).sum()))
    if sess['cloth'].sew is not None:
        c = sess['cloth']
        info['seam_gap'] = float(np.linalg.norm(c.co[c.sew[:, 1]] - c.co[c.sew[:, 0]], axis=1).mean())
    return info


# -----------------------------------------------------------------------------
# the live session: the cloth object from the lasso, frames on a timer
# -----------------------------------------------------------------------------

SIM = {}
SRC_KEY = 'mch_cdrape_src'


def sim_active():
    return bool(SIM.get('ob')) and bpy.data.objects.get(SIM['ob']) is not None


def _ob():
    return bpy.data.objects.get(SIM.get('ob', '')) if SIM else None


def perform(context, loops, projector):
    """Lasso -> the cloth object laid over the region (flat), the session ready: Space drapes it."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    sew = pin_idx = None
    if st.two_sides:
        target, me, nb, size, info = patch_two_sides(context, loops, projector, st.spacing)
        sew, pin_idx = info['sew'], info['top']
    else:
        target, me, nb, size = patch_from_loops(context, loops, projector, st.spacing)
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new('Cloth Drape', me)
    coll = target.users_collection[0] if target.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.matrix_world = target.matrix_world.copy()
    ob.parent = target
    ob.matrix_parent_inverse = target.matrix_world.inverted_safe()
    ob[SRC_KEY] = target.name
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    surface = mio.read_co(me).copy()
    try:
        sess = build(context, target, me, nb, size, st, sew=sew, pin_idx=pin_idx)
    except Exception:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        raise
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.clear()
    SIM.update(ob=ob.name, target=target.name, nb=nb, size=size, sess=sess, running=False, done=False, want=None,
               surface=surface, start=sess['cloth'].init.copy(), snapshot=_snapshot(st), sew=sew, pin_idx=pin_idx,
               spacing=float(st.spacing))
    pieces = f'front + back, {len(sew):,} seam pairs, ' if sew is not None else ''
    return (f'Cloth Drape on {target.name}: {pieces}{sess["points"]:,} points over {sess["collider"]:,} body points '
            f'(Space drape · Enter keep · Esc drop)')


# -----------------------------------------------------------------------------
# 0.24.95 Drape Mask (user: "지브러시 탭에서 하는 것처럼 마스크 씌워서는 못해?"): the masked faces of the body become the cloth
# -----------------------------------------------------------------------------

MASK_ATTR = '.sculpt_mask'
MASK_MIN = 0.5                   # a face is in the cloth when its corners' mask averages at least this


def masked_faces(me, threshold=MASK_MIN):
    """Indices of the faces whose corner mask (Sculpt Mode / the ZBrush tab) averages >= ``threshold``."""
    att = me.attributes.get(MASK_ATTR)
    if att is None or not len(me.polygons):
        return np.zeros(0, np.int64)
    vals = np.empty(len(me.vertices), np.float32)
    att.data.foreach_get('value', vals)
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    mean = np.add.reduceat(vals[vi].astype(np.float64), start) / np.maximum(tot, 1)
    return np.nonzero(mean >= threshold)[0].astype(np.int64)


def faces_mesh(me, faces, name='Cloth Drape'):
    """A new mesh of ``me``'s faces ``faces`` (same local coordinates, smooth shaded, points compacted)."""
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    faces = np.asarray(faces, np.int64)
    corner_face = np.repeat(np.arange(len(start)), tot)
    keep = np.zeros(len(start), bool)
    keep[faces] = True
    corners = np.nonzero(keep[corner_face])[0]
    uniq, inv = np.unique(vi[corners], return_inverse=True)
    co = mio.read_co(me)[uniq]
    tots = tot[faces]
    starts = np.concatenate(([0], np.cumsum(tots)[:-1])) if len(tots) else np.zeros(0, np.int64)
    new = bpy.data.meshes.new(name)
    new.vertices.add(len(uniq))
    new.vertices.foreach_set('co', co.ravel())
    new.loops.add(len(inv))
    new.loops.foreach_set('vertex_index', inv.astype(np.int32))
    new.polygons.add(len(faces))
    new.polygons.foreach_set('loop_start', starts.astype(np.int32))
    new.polygons.foreach_set('loop_total', tots.astype(np.int32))
    new.polygons.foreach_set('use_smooth', np.ones(len(faces), bool))
    new.update(calc_edges=True)
    new.validate()
    return new


REMESH_ITERS = 5                 # Drape Mask: isotropic remesh passes after the decimation (even triangles)


def rim_loops_idx(me):
    """The open loops of ``me`` as lists of point indices (in order)."""
    ev = mio.read_edge_verts(me)
    be = ev[mio.edge_face_counts(me) == 1]
    nbr = {}
    for a, b in be:
        nbr.setdefault(int(a), []).append(int(b))
        nbr.setdefault(int(b), []).append(int(a))
    seen, loops = set(), []
    for s0 in nbr:
        if s0 in seen:
            continue
        loop, prev, cur = [s0], None, s0
        seen.add(s0)
        while True:
            nx = [x for x in nbr[cur] if x != prev and x not in seen]
            if not nx:
                break
            prev, cur = cur, nx[0]
            loop.append(cur)
            seen.add(cur)
        loops.append(loop)
    return loops


def rim_locks(me, co, length):
    """(N,) uint8: one rim point every ``length`` along each open loop (the decimation keeps those)."""
    locked = np.zeros(len(co), np.uint8)
    for loop in rim_loops_idx(me):
        acc = 0.0
        locked[loop[0]] = 1
        for i in range(1, len(loop)):
            acc += float(np.linalg.norm(co[loop[i]] - co[loop[i - 1]]))
            if acc >= length:
                locked[loop[i]] = 1
                acc = 0.0
    return locked


def light_patch(me, target_points):
    """The masked patch ``me`` (dense, the body's own faces) rebuilt as an even, lighter triangle mesh of about
    ``target_points`` points: Fast Decimate (fast, any size) to about the count, then an isotropic remesh
    (``iso_remesh``: split / collapse / flip / relax, every inside point back on the body) so the triangles are
    even.  Returns a new Mesh, or None when the patch is already light enough / no engine."""
    import bmesh
    from mathutils.bvhtree import BVHTree
    from . import fast_decimate as fd
    from . import iso_remesh
    n = len(me.vertices)
    if target_points <= 0 or target_points >= n * 0.9 or not fd.available():
        return None
    area = sum(p.area for p in me.polygons)
    me.calc_loop_triangles()
    T = np.empty((len(me.loop_triangles), 3), np.int64)
    me.loop_triangles.foreach_get('vertices', T.ravel())
    V = mio.read_co(me)
    length = iso_remesh.target_length(area, target_points)
    # the rim: one point locked every ``length`` along each open loop (keep_borders locks EVERY rim point, so a dense
    # body's rim stayed dense; with no locks the rim was eaten down to 3 points).  The plain decimation reaches the
    # count (the even one stops early on a dense patch: 4k points for 1k asked)
    locked = rim_locks(me, V, length)
    V2, F2, _vs, _fs = fd.run(V, T, int(max(4, 2 * target_points)), even=False, keep_borders=False, locked=locked)
    if len(F2) < 2:
        return None
    new = bpy.data.meshes.new(me.name)
    fd.build_mesh(new, np.asarray(V2, np.float64), np.asarray(F2, np.int64))
    src = bmesh.new()                    # the points go back onto the masked region itself (a multi-million body
    try:                                 # would take minutes to turn into a BVH from Python lists)
        src.from_mesh(me)
        tree = BVHTree.FromBMesh(src)
    finally:
        src.free()

    def project(p):
        loc = tree.find_nearest(p)[0]
        return loc if loc is not None else p
    bm = bmesh.new()
    try:
        bm.from_mesh(new)
        iso_remesh.remesh(bm, length, project, REMESH_ITERS)
        bm.to_mesh(new)
    finally:
        bm.free()
    new.polygons.foreach_set('use_smooth', np.ones(len(new.polygons), bool))
    new.update()
    new.validate()
    return new


def mask_target_points(st, size):
    """Drape Mask's point count: the Cloth Points setting, or (0) what Cloth Detail would give a lasso of this size."""
    if st.mask_points > 0:
        return int(st.mask_points)
    return int(round((100.0 / max(st.spacing, 0.05)) ** 2 * 0.8))      # (a round patch: ~0.8 of the square's points)


def perform_masked(context, body):
    """The masked region of ``body`` (painted in Sculpt Mode / the ZBrush tab) lifted off as the cloth: the same
    flow as a lasso - a "Cloth Drape" object parented to the body, its open rim pinned, the body the collider."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    if body is None or body.type != 'MESH':
        raise cg.CutError('Drape Mask: the active object must be a mesh with a mask')
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    faces = masked_faces(body.data)
    if len(faces) < 3:
        raise cg.CutError('Drape Mask: paint a mask on the body first (Sculpt Mode / the ZBrush tab mask brush)')
    if len(faces) == len(body.data.polygons):
        raise cg.CutError('Drape Mask: the whole body is masked - the cloth needs an unmasked rim to hang from')
    me = faces_mesh(body.data, faces)
    if not len(me.polygons) or not len(wl.boundary_verts(me)):
        bpy.data.meshes.remove(me)
        raise cg.CutError('Drape Mask: the masked region has no open edge (a closed shell): mask a patch, not all of it')
    dense = len(me.vertices)
    light = light_patch(me, mask_target_points(st, 0.0))     # 0.24.95 lighter, even cloth (the body stays dense)
    if light is not None:
        bpy.data.meshes.remove(me)
        me = light
    co = mio.read_co(me)
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    ob = bpy.data.objects.new('Cloth Drape', me)
    coll = body.users_collection[0] if body.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.matrix_world = body.matrix_world.copy()
    ob.parent = body
    ob.matrix_parent_inverse = body.matrix_world.inverted_safe()
    ob[SRC_KEY] = body.name
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    surface = co.copy()
    try:
        sess = build(context, body, me, 0, size, st)
    except Exception:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        raise
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.clear()
    SIM.update(ob=ob.name, target=body.name, nb=0, size=size, sess=sess, running=False, done=False, want=None,
               surface=surface, start=sess['cloth'].init.copy(), snapshot=_snapshot(st), sew=None, pin_idx=None,
               spacing=float(st.spacing), source='MASK')
    rim = int(np.count_nonzero(sess['cloth'].pin >= 1))
    lighter = f' (rebuilt lighter from {dense:,})' if light is not None else ''
    return (f'Cloth Drape from the mask on {body.name}: {len(faces):,} faces, {sess["points"]:,} points{lighter}, {rim:,} on the rim pinned, '
            f'{sess["collider"]:,} body points (Space drape · Enter keep · Esc drop)')


def body_for(context, cloth):
    """The mesh the cloth drops onto: another selected mesh, else the cloth's parent mesh."""
    others = [o for o in context.selected_objects if o != cloth and o.type == 'MESH']
    if len(others) == 1:
        return others[0]
    if cloth.parent is not None and cloth.parent.type == 'MESH':
        return cloth.parent
    return None


def perform_mesh(context, cloth, body):
    """The selected mesh itself as the cloth (a remeshed piece of your own), laid as it is on ``body``: its open
    edges are the rim (Pin Rim), selected points stay too; Space drapes, Enter keeps the mesh, Esc puts it back."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    if cloth is None or cloth.type != 'MESH' or body is None or body.type != 'MESH' or body == cloth:
        raise cg.CutError('Select the cloth mesh (active) and the body mesh it drops onto')
    me = cloth.data
    if not len(me.polygons):
        raise cg.CutError('The cloth mesh has no faces')
    backup = me.copy()
    backup.name = me.name + '_mch_cd_backup'
    backup.use_fake_user = True
    co = mio.read_co(me)
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    to_cloth = cloth.matrix_world.inverted_safe() @ body.matrix_world
    sel = np.zeros(len(me.vertices), bool)
    me.vertices.foreach_get('select', sel)
    pin_sel = bool(sel.any()) and not bool(sel.all())      # (a fresh primitive has every point selected: not a pin)
    try:
        sess = build(context, body, me, 0, size, st, to_cloth=to_cloth, pin_sel=pin_sel, gdir_ob=cloth)
    except Exception:
        backup.use_fake_user = False
        bpy.data.meshes.remove(backup)
        raise
    surface = co.copy()
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.clear()
    SIM.update(ob=cloth.name, target=body.name, nb=0, size=size, sess=sess, running=False, done=False, want=None,
               surface=surface, start=sess['cloth'].init.copy(), snapshot=_snapshot(st), mode='MESH',
               backup=backup.name, to_cloth=to_cloth, pin_sel=pin_sel)
    rim = int(np.count_nonzero(sess['cloth'].pin >= 1))
    return (f'Cloth Drape: "{cloth.name}" itself on {body.name} - {sess["points"]:,} points, {rim:,} pinned, '
            f'{sess["collider"]:,} body points (Space drape · Enter keep · Esc put back)')


def wrap_copy(context, body, target_points):
    """An even, pole-free copy of ``body``'s surface for the wrapping cloth: Blender's voxel remesh at the voxel
    size that gives about ``target_points`` points (the surface area / target).  dict(co, vi, start, tot)."""
    me = body.data
    area = sum(p.area for p in me.polygons) or 1.0
    voxel = max(math.sqrt(area / max(target_points, 100)), 1e-5)
    tmp = bpy.data.objects.new(body.name + '_mch_cd_wrap', me)
    context.scene.collection.objects.link(tmp)
    try:
        md = tmp.modifiers.new('Remesh', 'REMESH')
        md.mode = 'VOXEL'
        md.voxel_size = voxel
        md.use_smooth_shade = True
        dg = context.evaluated_depsgraph_get()
        ev = tmp.evaluated_get(dg)
        pm = ev.to_mesh()
        try:
            pm.update()
            start, tot = mio.read_face_starts(pm)
            out = dict(co=mio.read_co(pm), vi=mio.read_corner_verts(pm), start=start, tot=tot, points=len(pm.vertices), voxel=voxel)
        finally:
            ev.to_mesh_clear()
    finally:
        bpy.data.objects.remove(tmp)
    return out


def perform_wrap(context, body):
    """A wrapping cloth round the whole body, like a bojagi: a copy of the body's mesh (decimated to Wrap Points),
    lifted off it by Gap, is the cloth; nothing is pinned; Wrap Tightness shortens its threads so it pulls in onto
    the body and the excess bunches into wrinkles, gravity sags it; the body is the collider.  A new object
    "Cloth Wrap" (Enter keeps, Esc drops)."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    if body is None or body.type != 'MESH' or not len(body.data.polygons):
        raise cg.CutError('Select the mesh to wrap')
    src = body.data
    open_rim = len(wl.boundary_verts(src)) > 0
    if open_rim:                                            # a tube / sleeve: the copy keeps its open ends (pinned)
        if len(src.vertices) > st.wrap_points:
            px = wl.proxy_mesh(context, body, st.wrap_points)
            me = bpy.data.meshes.new('MCH_ClothWrap')
            faces = [tuple(int(v) for v in px['vi'][s0:s0 + t]) for s0, t in zip(px['start'], px['tot'])]
            me.from_pydata([tuple(c) for c in px['co']], [], faces)
        else:
            me = src.copy()
            me.name = 'MCH_ClothWrap'
    else:                                                   # closed: an even voxel copy (no pole fans, no slivers)
        px = wrap_copy(context, body, st.wrap_points)
        if not px['points']:
            raise cg.CutError('The wrap copy came out empty (is the mesh closed enough for a voxel remesh?)')
        me = bpy.data.meshes.new('MCH_ClothWrap')
        faces = [tuple(int(v) for v in px['vi'][s0:s0 + t]) for s0, t in zip(px['start'], px['tot'])]
        me.from_pydata([tuple(c) for c in px['co']], [], faces)
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    co = mio.read_co(me)
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    ob = bpy.data.objects.new('Cloth Wrap', me)
    coll = body.users_collection[0] if body.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.matrix_world = body.matrix_world.copy()
    ob.parent = body
    ob.matrix_parent_inverse = body.matrix_world.inverted_safe()
    ob[SRC_KEY] = body.name
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    surface = co.copy()
    sess = build(context, body, me, 0, size, st, to_cloth=None, pin_sel=False, gdir_ob=body, wrap=True)
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.clear()
    SIM.update(ob=ob.name, target=body.name, nb=0, size=size, sess=sess, running=False, done=False, want=None,
               surface=surface, start=sess['cloth'].init.copy(), snapshot=_snapshot(st), mode='WRAP')
    tubes = f', {sess["tubes"]:,} points of tubes' if sess.get('tubes') else ''
    return (f'Cloth Wrap round {body.name}: {sess["points"]:,} cloth points, looseness {st.slack:.0f} %, pressure {st.wrap_tight:.0f} %{tubes} '
            f'(Space wrap · Enter keep · Esc drop)')


def perform_sew_copy(context, plate):
    """A sheet you extracted (a plate) copied: the copy is the cloth, its edges sewn to the plate's edges (the
    same points, held), the plate itself the collider - a light one, just that sheet.  Looseness + Puff lift the
    copy off the plate between the seams like a pillow / padding; gravity sags it.  A new object "Cloth Sew"
    (Enter keeps, Esc drops)."""
    st = settings(context)
    if st is None:
        raise cg.CutError('Cloth Drape settings missing')
    if sim_active():
        raise cg.CutError('Cloth Drape: keep (Enter) or drop (Esc) the cloth you have first')
    if plate is None or plate.type != 'MESH' or not len(plate.data.polygons):
        raise cg.CutError('Select the plate (the extracted sheet) to copy and sew')
    if not len(wl.boundary_verts(plate.data)):
        raise cg.CutError('Sew Copy: the plate has no open edge to sew along (a closed mesh - use Wrap This Mesh)')
    me = plate.data.copy()
    me.name = 'MCH_ClothSew'
    for p in me.polygons:
        p.use_smooth = True
    co = mio.read_co(me)
    size = float(np.linalg.norm(co.max(0) - co.min(0)))
    ob = bpy.data.objects.new('Cloth Sew', me)
    coll = plate.users_collection[0] if plate.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.matrix_world = plate.matrix_world.copy()
    ob.parent = plate
    ob.matrix_parent_inverse = plate.matrix_world.inverted_safe()
    ob[SRC_KEY] = plate.name
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    try:
        sess = build(context, plate, me, 0, size, st, to_cloth=None, pin_sel=False, gdir_ob=plate, puff=True)
    except Exception:
        bpy.data.objects.remove(ob)
        bpy.data.meshes.remove(me)
        raise
    c = sess['cloth']
    sewn = c.pin >= 1
    c.co[sewn] = c.init[sewn] = c.prev[sewn] = co[sewn]       # the seam: the copy's edge exactly on the plate's edge
    mio.write_co(me, c.co)
    me.update()
    SIM.clear()
    SIM.update(ob=ob.name, target=plate.name, nb=0, size=size, sess=sess, running=False, done=False, want=None,
               surface=co.copy(), start=c.init.copy(), snapshot=_snapshot(st), mode='SEW')
    return (f'Sew Copy of {plate.name}: {sess["points"]:,} cloth points, {int(sewn.sum()):,} sewn on the edge, puff {st.puff:.0f} % '
            f'(Space simulate · Enter keep · Esc drop)')


def _snapshot(st):
    return tuple(getattr(st, k) for k in ('fabric', 'slack', 'shrink', 'gravity', 'stick', 'keep', 'gap', 'pin_rim', 'frames',
                                          'wrap_tight', 'use_lines', 'stop_at_pins', 'two_sides', 'puff', 'wrinkles',
                                          'padding', 'pad_pattern', 'pad_size', 'pad_puff', 'trim', 'trim_width'))


def restart(context):
    """The cloth back to the laid patch, the session rebuilt with the current sliders (Cloth Detail needs a new lasso)."""
    grab_end_event()
    ob = _ob()
    st = settings(context)
    target = bpy.data.objects.get(SIM.get('target', ''))
    if ob is None or st is None or target is None:
        return False
    me = ob.data
    mio.write_co(me, SIM['surface'])              # the laid patch again, then the cloth with the current sliders
    me.update()
    mode = SIM.get('mode')
    sess = build(context, target, me, SIM['nb'], SIM['size'], st, sew=SIM.get('sew'), pin_idx=SIM.get('pin_idx'),
                 to_cloth=SIM.get('to_cloth'), pin_sel=bool(SIM.get('pin_sel')), gdir_ob=ob if mode == 'MESH' else target,
                 wrap=mode == 'WRAP', puff=mode == 'SEW')
    if mode == 'SEW':
        c = sess['cloth']
        sewn = c.pin >= 1
        c.co[sewn] = c.init[sewn] = c.prev[sewn] = SIM['surface'][sewn]
    mio.write_co(me, sess['cloth'].co)
    me.update()
    SIM.update(sess=sess, running=True, done=False, start=sess['cloth'].init.copy(), snapshot=_snapshot(st))
    return True


def step(context):
    ob = _ob()
    sess = SIM.get('sess')
    if ob is None or sess is None:
        return False
    if sess['frame'] >= sess['frames']:
        SIM['running'] = False
        SIM['done'] = True
        return False
    advance(sess, settings(context))
    mio.write_co(ob.data, sess['cloth'].co)
    ob.data.update()
    return True


def _drop_backup():
    backup = bpy.data.meshes.get(SIM.get('backup', ''))
    if backup is not None:
        backup.use_fake_user = False
        if backup.users == 0:
            bpy.data.meshes.remove(backup)


def add_thickness(ob, size, st):
    """A Solidify modifier (outward) on a cloth object when Thickness is set: the cloth gets a body."""
    if st is None or st.thickness <= 0 or ob is None:
        return False
    md = ob.modifiers.get('MCH Cloth Thickness') or ob.modifiers.new('MCH Cloth Thickness', 'SOLIDIFY')
    md.thickness = size * st.thickness / 100.0
    md.offset = 1.0
    md.use_even_offset = False            # (even offset divides by the corner angle: a crumpled cloth would spike)
    md.use_quality_normals = True
    md.use_rim = True
    return True


def weld_seams(me, sew):
    """The sewn pairs become one point each (the front point stays): the pieces are one surface."""
    import bmesh
    if sew is None or not len(sew):
        return 0
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.verts.ensure_lookup_table()
    tm = {}
    for a, b in np.asarray(sew, np.int64):
        if a != b and 0 <= a < len(bm.verts) and 0 <= b < len(bm.verts):
            tm[bm.verts[int(b)]] = bm.verts[int(a)]
    bmesh.ops.weld_verts(bm, targetmap=tm)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return len(tm)


def confirm(context):
    ob = _ob()
    if ob is None:
        _drop_backup()
        SIM.clear()
        return 'nothing to keep'
    n = SIM['sess']['frame']
    welded = weld_seams(ob.data, SIM.get('sew')) if SIM.get('sew') is not None else 0
    thick = add_thickness(ob, SIM['size'], settings(context)) if SIM.get('mode') != 'MESH' else False
    trim = add_trim(context, ob, SIM['size'], settings(context))
    _drop_backup()
    SIM.clear()
    return (f'Cloth Drape: kept "{ob.name}" at frame {n} ({len(ob.data.vertices):,} points'
            f'{f", {welded} seam points welded" if welded else ""}{", thickness on" if thick else ""}'
            f'{f", trim on {trim} edge loops" if trim else ""})')


def rim_loops(me):
    """The mesh's open edge loops as ordered point index lists (closed where the loop closes)."""
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.verts.ensure_lookup_table()
        bnd = [e for e in bm.edges if e.is_boundary]
        nxt = {}
        for e in bnd:
            a, b = e.verts[0].index, e.verts[1].index
            nxt.setdefault(a, []).append(b)
            nxt.setdefault(b, []).append(a)
        seen = set()
        loops = []
        for v0 in list(nxt):
            if v0 in seen:
                continue
            loop, cur, prev = [v0], v0, None
            seen.add(v0)
            while True:
                cand = [w for w in nxt.get(cur, []) if w != prev and w not in seen]
                if not cand:
                    break
                prev, cur = cur, cand[0]
                loop.append(cur)
                seen.add(cur)
            closed = len(loop) > 2 and loop[0] in nxt.get(loop[-1], [])
            loops.append((loop, closed))
        return loops
    finally:
        bm.free()


def rim_tube_mesh(me, radius, segments=8):
    """A round piping along every open edge loop of ``me``: (verts, faces) of the tubes."""
    co = mio.read_co(me)
    nrm = wl._normals(me)
    verts, faces = [], []
    for loop, closed in rim_loops(me):
        if len(loop) < 2:
            continue
        P = co[loop]
        N = nrm[loop]
        T = np.roll(P, -1, 0) - np.roll(P, 1, 0) if closed else np.gradient(P, axis=0)
        T /= np.maximum(np.linalg.norm(T, axis=1), 1e-12)[:, None]
        B = np.cross(T, N)
        B /= np.maximum(np.linalg.norm(B, axis=1), 1e-12)[:, None]
        N2 = np.cross(B, T)
        ang = np.linspace(0.0, 2.0 * math.pi, segments, endpoint=False)
        ring = (np.cos(ang)[None, :, None] * N2[:, None, :] + np.sin(ang)[None, :, None] * B[:, None, :]) * radius
        R = P[:, None, :] + ring                                   # (m, segments, 3)
        base = len(verts)
        verts.extend(R.reshape(-1, 3).tolist())
        m = len(loop)
        for i in range(m if closed else m - 1):
            j = (i + 1) % m
            for k in range(segments):
                k2 = (k + 1) % segments
                faces.append((base + i * segments + k, base + i * segments + k2, base + j * segments + k2, base + j * segments + k))
    return verts, faces


def add_trim(context, ob, size, st):
    """0.24.95 Trim: a piping tube round the cloth's open edges as its own object 'Cloth Trim' (child of the cloth,
    so it follows it).  Returns the number of edge loops piped."""
    if st is None or not getattr(st, 'trim', False) or ob is None:
        return 0
    verts, faces = rim_tube_mesh(ob.data, size * st.trim_width / 200.0)
    if not faces:
        return 0
    me = bpy.data.meshes.new(ob.name + ' Trim')
    me.from_pydata(verts, [], faces)
    me.validate()
    me.update()
    for p in me.polygons:
        p.use_smooth = True
    trim = bpy.data.objects.new('Cloth Trim', me)
    coll = ob.users_collection[0] if ob.users_collection else context.scene.collection
    coll.objects.link(trim)
    trim.parent = ob
    trim.matrix_world = ob.matrix_world.copy()
    trim.matrix_parent_inverse = ob.matrix_world.inverted_safe()
    for mat in ob.data.materials:
        me.materials.append(mat)
    return len(rim_loops(ob.data))


def cancel(context):
    ob = _ob()
    if ob is not None and SIM.get('mode') == 'MESH':         # the mesh itself: put the saved copy back
        backup = bpy.data.meshes.get(SIM.get('backup', ''))
        if backup is not None:
            old = ob.data
            ob.data = backup
            backup.name = old.name
            backup.use_fake_user = False
            if old.users == 0:
                bpy.data.meshes.remove(old)
        SIM.clear()
        return 'Cloth Drape: the mesh put back'
    if ob is not None:
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    SIM.clear()
    return 'Cloth Drape: dropped'


def status():
    if not sim_active():
        return ''
    sess = SIM['sess']
    esc = 'put back' if SIM.get('mode') == 'MESH' else 'drop'
    grab = SIM.get('grab')
    held = f'  · holding {len(grab["idx"]):,} points' if grab else '  · drag the cloth to pull it'
    if SIM.get('done'):
        return f'done: frame {sess["frame"]} / {sess["frames"]}  (Enter keep · Esc {esc} · Space again){held}'
    return (f'{"draping" if SIM["running"] else "ready"}: frame {sess["frame"]} / {sess["frames"]}  '
            f'(Space {"pause" if SIM["running"] else "drape"} · Enter keep · Esc {esc}){held}')


class MCH_OT_cdrape_sim(bpy.types.Operator):
    """Space: drape / pause the cloth. Enter keeps it, Esc drops it"""
    bl_idname = 'mch.cdrape_sim'
    bl_label = 'Cloth Drape Simulation'
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT' and sim_active()

    def invoke(self, context, event):
        if SIM.get('modal'):
            SIM['want'] = 'toggle'
            return {'CANCELLED'}
        SIM['modal'] = True
        self._toggle(context)
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        self._hint(context)
        return {'RUNNING_MODAL'}

    def _hint(self, context):
        if context.area:
            context.area.header_text_set('Cloth Drape  ' + status())
            context.area.tag_redraw()

    def _end(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        SIM.pop('modal', None)
        grab_end_event()
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        if not sim_active():
            self._end(context)
            return {'CANCELLED'}
        want = SIM.get('want')
        if want:
            SIM['want'] = None
            if want == 'confirm':
                return self._finish(context, confirm(context), {'FINISHED'})
            if want == 'cancel':
                return self._finish(context, cancel(context), {'CANCELLED'})
            if want == 'restart':
                restart(context)
            elif want == 'toggle':
                self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type == 'TIMER':
            if SIM.get('running'):
                step(context)
                self._hint(context)
            return {'RUNNING_MODAL'}
        if SIM.get('grab'):                                   # 0.24.95 dragging the cloth
            if event.type == 'MOUSEMOVE':
                grab_move_event(context, event)
                return {'RUNNING_MODAL'}
            if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
                grab_end_event()
                self._hint(context)
                return {'RUNNING_MODAL'}
            if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
                return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'PRESS' and not (event.ctrl or event.alt or event.shift):
            if grab_start_event(context, event):            # a press on the cloth: grab it (off the cloth: the tool's)
                self._hint(context)
                return {'RUNNING_MODAL'}
        if event.type == 'SPACE' and event.value == 'PRESS':
            self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._finish(context, confirm(context), {'FINISHED'})
        if event.type == 'ESC' and event.value == 'PRESS':
            return self._finish(context, cancel(context), {'CANCELLED'})
        return {'PASS_THROUGH'}

    def _toggle(self, context):
        st = settings(context)
        if SIM.get('done') or (not SIM.get('running') and st is not None and _snapshot(st) != SIM.get('snapshot')):
            restart(context)
            return
        SIM['running'] = not SIM.get('running')

    def _finish(self, context, msg, result):
        self._end(context)
        self.report({'INFO'}, msg)
        return result


class MCH_OT_cdrape_mesh(bpy.types.Operator):
    """Drape the active mesh itself (a remeshed piece of your own) onto the other selected mesh (or its parent): its open edges / selected points stay, Space drapes, Enter keeps it, Esc puts it back"""
    bl_idname = 'mch.cdrape_mesh'
    bl_label = 'Drape This Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT' and not sim_active()

    def execute(self, context):
        cloth = context.view_layer.objects.active
        body = body_for(context, cloth)
        if body is None:
            self.report({'WARNING'}, 'Cloth Drape: select the body mesh too (or parent the cloth to it)')
            return {'CANCELLED'}
        try:
            msg = perform_mesh(context, cloth, body)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_cdrape_mask(bpy.types.Operator):
    """Drape Mask: the masked faces of the active mesh (Sculpt Mode / ZBrush tab mask) lift off as the cloth, pinned at the rim, the body the collider; the drape starts at once (Space pause, Enter keep, Esc drop)"""
    bl_idname = 'mch.cdrape_mask'
    bl_label = 'Drape Mask'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return (ob is not None and ob.type == 'MESH' and context.mode in {'OBJECT', 'SCULPT'} and not sim_active()
                and ob.data.attributes.get(MASK_ATTR) is not None)

    def execute(self, context):
        try:
            msg = perform_masked(context, context.view_layer.objects.active)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def invoke(self, context, event):
        r = self.execute(context)
        if 'FINISHED' in r and context.area is not None and context.area.type == 'VIEW_3D':
            try:
                bpy.ops.mch.cdrape_sim('INVOKE_DEFAULT')       # start draping right away (any tool: the modal has the keys)
            except RuntimeError:
                pass
        return r


class MCH_OT_cdrape_wrap(bpy.types.Operator):
    """Wrap the active mesh in a cloth like a wrapping cloth (bojagi): a copy of it lifted off, pulled in by Wrap Tightness, the excess bunching into wrinkles; Space wraps, Enter keeps the new object, Esc drops it"""
    bl_idname = 'mch.cdrape_wrap'
    bl_label = 'Wrap This Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT' and not sim_active()

    def execute(self, context):
        try:
            msg = perform_wrap(context, context.view_layer.objects.active)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_cdrape_sew_copy(bpy.types.Operator):
    """Copy the active plate (an extracted sheet) as a cloth sewn to it along its edges: the plate is the collider, the copy lifts off between the seams (Puff, Looseness) like a pillow; Space simulates, Enter keeps the new object, Esc drops it"""
    bl_idname = 'mch.cdrape_sew_copy'
    bl_label = 'Sew Copy'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT' and not sim_active()

    def execute(self, context):
        try:
            msg = perform_sew_copy(context, context.view_layer.objects.active)
        except cg.CutError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


class MCH_OT_cdrape_lines(bpy.types.Operator):
    """Draw wrinkle lines on the body (the Wrinkle Lines tool): they become tubes under the cloth. Pick the Cloth Drape tool again to drape"""
    bl_idname = 'mch.cdrape_lines'
    bl_label = 'Draw Lines'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        ob = context.view_layer.objects.active
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT' and not sim_active()

    def execute(self, context):
        from . import workspace_ui
        workspace_ui.activate_mecha_tool(context, 'WLINES')
        self.report({'INFO'}, 'Wrinkle Lines: drag lines on the body, then pick Cloth Drape again (the lines stay)')
        return {'FINISHED'}


class MCH_OT_cdrape_control(bpy.types.Operator):
    """Drape / pause, keep, drop or restart the cloth (the panel buttons)"""
    bl_idname = 'mch.cdrape_control'
    bl_label = 'Cloth Drape Control'
    bl_options = {'INTERNAL'}
    action: bpy.props.StringProperty(default='toggle', options={'SKIP_SAVE'})

    def execute(self, context):
        if not sim_active():
            return {'CANCELLED'}
        if SIM.get('modal'):
            SIM['want'] = self.action
            return {'FINISHED'}
        if self.action == 'confirm':
            self.report({'INFO'}, confirm(context))
            return {'FINISHED'}
        if self.action == 'cancel':
            self.report({'INFO'}, cancel(context))
            return {'FINISHED'}
        if self.action == 'restart':
            restart(context)
            SIM['running'] = False
        return bpy.ops.mch.cdrape_sim('INVOKE_DEFAULT')


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    box = layout.box()
    box.label(text='Cloth Drape', icon='MOD_CLOTH')
    live = sim_active()
    box.label(text=status() if live else 'draw a lasso on the mesh: a loose cloth over that region', icon='PLAY' if live else 'INFO')
    r = box.row(align=True)
    r.enabled = live
    if SIM.get('done'):
        text, icon = 'Again (Space)', 'FILE_REFRESH'
    elif SIM.get('running'):
        text, icon = 'Pause (Space)', 'PAUSE'
    else:
        text, icon = 'Drape (Space)', 'PLAY'
    r.operator('mch.cdrape_control', text=text, icon=icon).action = 'toggle'
    r.operator('mch.cdrape_control', text='Restart', icon='FILE_REFRESH').action = 'restart'
    r = box.row(align=True)
    r.enabled = live
    r.operator('mch.cdrape_control', text='Keep (Enter)', icon='CHECKMARK').action = 'confirm'
    r.operator('mch.cdrape_control', text='Put Back (Esc)' if SIM.get('mode') == 'MESH' else 'Drop (Esc)', icon='X').action = 'cancel'
    r = box.row()
    r.enabled = not live
    r.operator('mch.cdrape_mesh', text='Drape This Mesh (on the other selected)', icon='MOD_CLOTH')
    r = box.row()
    r.enabled = not live
    r.operator('mch.cdrape_mask', text='Drape Mask (masked faces lift off as the cloth)', icon='MOD_MASK')
    r.prop(st, 'mask_points', text='Points')
    r = box.row(align=True)
    r.enabled = not live
    r.operator('mch.cdrape_wrap', text='Wrap This Mesh (like a wrapping cloth)', icon='MOD_SHRINKWRAP')
    r = box.row(align=True)
    r.prop(st, 'wrap_tight', slider=True)
    r.prop(st, 'wrap_points')
    r = box.row(align=True)
    r.enabled = not live
    r.operator('mch.cdrape_sew_copy', text='Sew Copy (plate copied, edges sewn)', icon='MOD_SOLIDIFY')
    box.prop(st, 'puff', slider=True)
    ob = context.view_layer.objects.active
    body = bpy.data.objects.get(SIM.get('target', '')) if live else ob
    n_lines = len(wl._lines_of(body)) if body is not None and body.type == 'MESH' else 0
    r = box.row(align=True)
    r.prop(st, 'use_lines', text=f'Lines as Tubes ({n_lines})', toggle=True)
    rr = r.row()
    rr.enabled = not live
    rr.operator('mch.cdrape_lines', text='Draw Lines', icon='GREASEPENCIL')
    wst = wl.settings(context)
    if wst is not None and st.use_lines:
        r = box.row(align=True)
        r.prop(wst, 'size', text='Tube Size')
        r.prop(wst, 'fold', text='Height')
        r = box.row(align=True)
        r.prop(wst, 'lift', text='Lift')
        r.prop(wst, 'fade', text='End Fade')
    box.row().prop(st, 'fabric', expand=True)
    col = box.column(align=True)
    col.prop(st, 'slack', slider=True)
    col.prop(st, 'shrink', slider=True)
    col.prop(st, 'gravity', slider=True)
    col.prop(st, 'stick', slider=True)
    col.prop(st, 'wrinkles', slider=True)
    col.prop(st, 'keep', slider=True)
    col = box.column(align=True)
    col.prop(st, 'gap', slider=True)
    col.prop(st, 'spacing', slider=True, text='Cloth Detail (less = finer)')
    if sim_active() and SIM.get('spacing') is not None and abs(float(st.spacing) - SIM['spacing']) > 1e-6:
        box.label(text='Cloth Detail changes the NEXT lasso (this cloth keeps its mesh)', icon='INFO')
    r = box.row(align=True)
    r.prop(st, 'two_sides', toggle=True, icon='MOD_MIRROR')
    r.prop(st, 'pin_rim', toggle=True)
    r.prop(st, 'stop_at_pins', toggle=True)
    r = box.row(align=True)                              # 0.24.95 Padding + Trim
    r.prop(st, 'padding', toggle=True, icon='MESH_GRID')
    rr = r.row(align=True)
    rr.active = st.padding
    rr.prop(st, 'pad_pattern', text='')
    r = box.row(align=True)
    r.active = st.padding
    r.prop(st, 'pad_size', slider=True)
    r.prop(st, 'pad_puff', slider=True)
    r = box.row(align=True)
    r.prop(st, 'trim', toggle=True, icon='MOD_SKIN')
    rr = r.row(align=True)
    rr.active = st.trim
    rr.prop(st, 'trim_width', slider=True)
    box.prop(st, 'frames')
    box.prop(st, 'thickness', slider=True)


CLASSES = (MCH_PG_ClothDrape, MCH_OT_cdrape_sim, MCH_OT_cdrape_mesh, MCH_OT_cdrape_mask, MCH_OT_cdrape_wrap, MCH_OT_cdrape_sew_copy, MCH_OT_cdrape_lines,
           MCH_OT_cdrape_control)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_cdrape = bpy.props.PointerProperty(type=MCH_PG_ClothDrape)


def unregister():
    SIM.clear()
    if hasattr(bpy.types.Scene, 'mch_cdrape'):
        del bpy.types.Scene.mch_cdrape
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
