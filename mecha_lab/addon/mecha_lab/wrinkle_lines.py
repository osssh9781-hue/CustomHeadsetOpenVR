"""0.24.92 Wrinkle Lines: draw guide lines on a mesh, thin tubes go along them, a cloth laid over the mesh folds
over the tubes.

Not a full garment simulation: the aim is "a pretty wrinkle where I want it" on a game model.  Two stages:

    1. **Tubes** (Space): along every drawn line a thin round tube (Wrinkle Size x 1/3 of the part size, Fold
       Strength its height, End Fade the fade-out at the ends, Line Strength per line) is laid on the surface -
       live with the sliders, Enter keeps just that;
    2. **Cloth** (Space again): the way a garment is draped in Marvelous Designer - a copy of the mesh is laid a
       little above the surface, its open edges (the ends of a sleeve) pinned, its rest lengths shrunk (Shrink),
       gravity pulls it, and the original surface with the tubes is the **collider** inside: the cloth cannot
       pass through it and sticks to it (friction).  The cloth hangs on the tubes and folds below them, the fabric
       between the lines crumples; Silhouette Keep is a soft spring back to the start.  Enter writes the cloth into
       the mesh (same points, so nothing else changes), Esc puts the saved copy back.
    Crease mode lays a groove instead of a tube: the cloth sags into it, a fold line.

Keys (the Wrinkle Lines tool):  drag = a new line on the surface · drag a point = move it · Shift + click = a point
added to the nearest line · Ctrl + click = that point removed · X = the line under the mouse removed ·
Space = tubes / simulate / pause · Enter = keep · Esc = back to the start (the lines stay).

The lines live on the object (``PROP``, local space) so they stay on the mesh while orbiting and survive a save.
The frames run in the user's scene on a timer, so the cloth is seen folding.  ``tube_field``, ``prepare`` /
``build`` / ``advance`` and ``simulate`` are plain functions (tested headless); the solver is ``cloth_pbd``.
"""
from __future__ import annotations

import json
import math
import time

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty
from mathutils import Vector
from mathutils.kdtree import KDTree

from . import core_geometry as cg
from . import mesh_io as mio
from . import surface_lasso as sl
from . import target_rules

PROP = 'mch_wlines'
HIT_PX = 14.0
DETAIL_FACES = 20000             # a mesh under this is subdivided before the simulation (folds need points)
DETAIL_TARGET = 40000
MAX_DETAIL_LEVELS = 2
# Blender's own cloth presets (Cotton = the defaults) + a soft knit
FABRICS = (
    ('COTTON', 'Cotton', 'Plain fabric: medium folds', dict(mass=0.3, tension=15.0, compression=15.0, shear=5.0, bend=0.5, quality=5)),
    ('DENIM', 'Denim', 'Heavy stiff fabric: few, big folds', dict(mass=1.0, tension=40.0, compression=40.0, shear=10.0, bend=10.0, quality=5)),
    ('SILK', 'Silk', 'Thin light fabric: many fine folds', dict(mass=0.15, tension=5.0, compression=5.0, shear=3.0, bend=0.05, quality=6)),
    ('LEATHER', 'Leather', 'Stiff: thick rounded folds', dict(mass=0.4, tension=80.0, compression=80.0, shear=80.0, bend=150.0, quality=5)),
    ('KNIT', 'Knit', 'Soft stretchy fabric: round soft folds', dict(mass=0.4, tension=4.0, compression=4.0, shear=2.0, bend=0.2, quality=5)),
)
FABRIC_ITEMS = tuple((f[0], f[1], f[2]) for f in FABRICS)
FABRIC_BY_ID = {f[0]: f[3] for f in FABRICS}
MODES = (('WRINKLE', 'Wrinkle Line', 'A tube along the line under the cloth: the cloth folds over and off it'),
         ('CREASE', 'Crease', 'A groove along the line: the cloth sags into it, a fold line'))


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------


def _strength_changed(st, context):
    lines = _lines_of(context.view_layer.objects.active)
    if lines:
        lines[-1]['strength'] = st.strength / 100.0
        _save(context.view_layer.objects.active, lines)
        if sim_active() and SIM['sess'].get('stage') == 'preview':
            SIM['sess']['strengths'] = [ln['strength'] for ln in lines]
            _tube_changed(st, context)


def _tube_changed(st, context):
    if refresh(context):
        for area in context.screen.areas if context.screen else ():
            if area.type == 'VIEW_3D':
                area.tag_redraw()



class MCH_PG_WrinkleLines(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Mode', items=MODES, default='WRINKLE', update=_tube_changed)
    fabric: EnumProperty(name='Fabric', items=FABRIC_ITEMS, default='COTTON')
    size: FloatProperty(name='Wrinkle Size', description='The thickness of the tube laid along a line, as % of the part size (x 3)',
                        default=5.0, min=0.5, max=30.0, subtype='PERCENTAGE', update=_tube_changed)
    fade: FloatProperty(name='End Fade', description='The tube fades out over this much of the line at each end',
                        default=20.0, min=0.0, max=50.0, subtype='PERCENTAGE', update=_tube_changed)
    shrink: FloatProperty(name='Shrink', description='How much the cloth laid over the mesh shrinks (more = deeper folds)',
                          default=33.0, min=0.0, max=90.0, subtype='PERCENTAGE')
    fold: FloatProperty(name='Fold Strength', description='The height of the tubes (Crease: how deep the groove is)',
                        default=100.0, min=0.0, max=200.0, subtype='PERCENTAGE', update=_tube_changed)
    gravity: FloatProperty(name='Gravity', default=30.0, min=0.0, max=300.0, subtype='PERCENTAGE')
    keep: FloatProperty(name='Silhouette Keep', description='How firmly the surface away from the lines stays where it is',
                        default=47.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    strength: FloatProperty(name='Line Strength', description='The strength of the last drawn line (each line keeps its own)',
                            default=100.0, min=0.0, max=200.0, subtype='PERCENTAGE', update=_strength_changed)
    pin_boundary: BoolProperty(name='Pin Mesh Boundary', description='The open edges of the mesh (the ends of a sleeve) stay put',
                               default=True)
    pin_selected: BoolProperty(name='Pin Selected', description='Points selected in Edit Mode stay put too', default=False)
    self_collision: BoolProperty(name='Cloth Self Collision', description='Folds do not pass through each other (slower)',
                                 default=False)
    detail: BoolProperty(name='Add Detail', description='A coarse mesh (under 20k faces) is subdivided first: folds need points',
                         default=True)
    frames: IntProperty(name='Frames', default=30, min=5, max=120)
    show: BoolProperty(name='Show Lines', default=True)


def settings(context):
    return getattr(context.scene, 'mch_wlines', None)


# -----------------------------------------------------------------------------
# lines on the object
# -----------------------------------------------------------------------------

_CACHE = {}          # object name -> list of lines (dicts: pts [Vector], nrm [Vector], strength float, path [Vector])
_TARGET = {}         # object name -> SurfaceTarget (the BVH; rebuilt when the mesh changes)


def _lines_of(ob):
    if ob is None or ob.type != 'MESH':
        return []
    lines = _CACHE.get(ob.name)
    if lines is None:
        lines = load(ob)
        _CACHE[ob.name] = lines
    return lines


def load(ob):
    raw = ob.get(PROP)
    if not raw:
        return []
    try:
        data = json.loads(raw)
    except (TypeError, ValueError):
        return []
    out = []
    for item in data:
        pts = [Vector(p) for p in item.get('pts', [])]
        nrm = [Vector(n) for n in item.get('nrm', [])]
        if len(pts) >= 2 and len(nrm) == len(pts):
            out.append(dict(pts=pts, nrm=nrm, strength=float(item.get('strength', 1.0)), path=None))
    return out


def _save(ob, lines):
    if ob is None:
        return
    if not lines:
        if PROP in ob:
            del ob[PROP]
        _CACHE.pop(ob.name, None)
        return
    ob[PROP] = json.dumps([dict(pts=[list(p) for p in ln['pts']], nrm=[list(n) for n in ln['nrm']],
                                strength=ln['strength']) for ln in lines])
    _CACHE[ob.name] = lines


def target_of(context, ob, fresh=False):
    t = _TARGET.get(ob.name)
    if t is None or fresh or t.faces != len(ob.data.polygons):
        t = sl.SurfaceTarget(context, ob)
        t.faces = len(ob.data.polygons)
        _TARGET[ob.name] = t
    return t


def line_path(target, ln):
    """The line's points joined along the surface (local space), cached on the line."""
    if ln.get('path') is None:
        pts = []
        for i in range(len(ln['pts']) - 1):
            seg = sl.trace(target, ln['pts'][i], ln['nrm'][i], ln['pts'][i + 1], ln['nrm'][i + 1])
            pts.extend(seg[:-1] if i < len(ln['pts']) - 2 else seg)
        ln['path'] = pts
    return ln['path']


def thin_stroke(hits, count):
    """``count`` (point, normal) pairs evenly spaced along the raw stroke - pure."""
    if len(hits) <= count:
        return list(hits)
    acc = [0.0]
    for (a, _na), (b, _nb) in zip(hits, hits[1:]):
        acc.append(acc[-1] + (b - a).length)
    total = acc[-1] or 1.0
    out, j = [], 0
    for k in range(count):
        s = total * k / (count - 1)
        while j < len(acc) - 2 and acc[j + 1] < s:
            j += 1
        t = (s - acc[j]) / max(acc[j + 1] - acc[j], 1e-12)
        a, na = hits[j]
        b, nb = hits[j + 1]
        out.append((a.lerp(b, t), na.lerp(nb, t).normalized()))
    return out


def point_count(length, size):
    """Control points for a stroke: about one per 4 % of the part size, 3 .. 24."""
    return max(3, min(24, int(length / max(size * 0.04, 1e-9)) + 2))


# -----------------------------------------------------------------------------
# weights (pure, numpy)
# -----------------------------------------------------------------------------


def weights(co, paths, strengths, radius, crease=False):
    """Per-point shrink weight 0..1 from the distance to the lines' surface paths: ``(1 - (d / R)^2)^2`` within
    ``radius`` (Crease: a band half as wide, a straight fall-off).  ``co`` (N, 3), ``paths`` lists of points."""
    n = len(co)
    w = np.zeros(n)
    if n == 0:
        return w
    r = radius * (0.5 if crease else 1.0)
    for path, strength in zip(paths, strengths):
        if len(path) < 2 or strength <= 0 or r <= 0:
            continue
        kd = KDTree(len(path))
        for i, p in enumerate(path):
            kd.insert(p, i)
        kd.balance()
        d = np.empty(n)
        for i in range(n):
            d[i] = kd.find(co[i])[2]
        t = np.clip(d / r, 0.0, 1.0)
        f = (1.0 - t) if crease else (1.0 - t * t) ** 2
        w = np.maximum(w, np.clip(f * strength, 0.0, 1.0))
    return w


def boundary_verts(me):
    """Indices of the points on open edges (numpy)."""
    if not len(me.polygons):
        return np.zeros(0, np.int64)
    counts = mio.edge_face_counts(me)
    ev = mio.read_edge_verts(me)
    open_e = ev[counts == 1]
    return np.unique(open_e.ravel()) if len(open_e) else np.zeros(0, np.int64)


# -----------------------------------------------------------------------------
# the simulation (cloth_pbd: the sculpt-cloth way)
# -----------------------------------------------------------------------------

TUBE = 1.0 / 3.0                 # the tube's radius = Wrinkle Size x this (5 % -> 1.7 % of the part size)
MARGIN = 0.25                    # the cloth rests this x tube radius above the collider (the collider sits that far in)
GAP = 0.6                        # the cloth copy starts this x tube radius above the collider
ITERATIONS = 6                   # constraint passes per frame
SOR = 1.3
DAMPING = 0.3
GRAV_UNIT = 0.0015 / (0.3 * 3.3) # gravity 30 % on a 3.3-unit part = the probe's 0.0015 / frame^2 (x part size)
KEEP_SCALE = 0.1                 # Silhouette Keep 100 % -> the goal spring weight (47 % = a gentle pull back)
KEEP_RATE = 0.3
REPICK = 0.5                     # a cloth point re-picks its collider point when it slid this x the mean edge length
FIELD_CHUNK = 2048
# fabric: bending constraint strength, contact friction, damping
FABRIC_SIM = {'COTTON': (0.5, 0.3, 0.3), 'DENIM': (1.0, 0.5, 0.4), 'SILK': (0.2, 0.15, 0.2), 'LEATHER': (1.0, 0.6, 0.5),
              'KNIT': (0.4, 0.3, 0.3)}


def _subdivide(me, levels):
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        for _ in range(levels):
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=1, use_grid_fill=True)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def detail_levels(faces):
    """Subdivision levels for a coarse mesh: up to ~DETAIL_TARGET faces (one level = 4x), at least one under
    DETAIL_FACES."""
    if faces >= DETAIL_FACES or faces == 0:
        return 0
    return int(min(MAX_DETAIL_LEVELS, max(1, math.floor(math.log(DETAIL_TARGET / faces, 4)))))


def tube_field(co, paths, strengths, radius, fade=0.2):
    """Per point the height (0..1, x the line's strength) of a round tube of ``radius`` lying along each line:
    ``sqrt(1 - (d / r)^2)`` from the exact distance to the polyline, the ends fading out over ``fade`` of the
    line's length (a closed line has no ends).  ``co`` (N, 3), ``paths`` lists / arrays of points - pure numpy."""
    n = len(co)
    h = np.zeros(n)
    if n == 0 or radius <= 0:
        return h
    co = np.asarray(co, np.float64)
    for path, strength in zip(paths, strengths):
        P = np.asarray([list(p) for p in path], np.float64)
        if len(P) < 2 or strength <= 0:
            continue
        A, B = P[:-1], P[1:]
        AB = B - A
        L2 = np.maximum((AB * AB).sum(1), 1e-18)
        seg = np.sqrt(L2)
        acc = np.concatenate([[0.0], np.cumsum(seg)])
        total = max(acc[-1], 1e-9)
        closed = np.linalg.norm(P[0] - P[-1]) < radius * 0.5
        for s0 in range(0, n, FIELD_CHUNK):
            c = co[s0:s0 + FIELD_CHUNK]
            diff = c[:, None, :] - A[None, :, :]
            t = np.clip((diff * AB[None]).sum(2) / L2[None], 0.0, 1.0)
            proj = A[None] + t[:, :, None] * AB[None]
            d2 = ((c[:, None, :] - proj) ** 2).sum(2)
            j = d2.argmin(1)
            rows = np.arange(len(c))
            d = np.sqrt(d2[rows, j])
            u = np.clip(d / radius, 0.0, 1.0)
            hh = np.sqrt(np.maximum(1.0 - u * u, 0.0))
            if not closed and fade > 0:
                along = (acc[j] + t[rows, j] * seg[j]) / total
                e = np.clip(np.minimum(along, 1.0 - along) / fade, 0.0, 1.0)
                hh *= e * e * (3.0 - 2.0 * e)
            h[s0:s0 + FIELD_CHUNK] = np.maximum(h[s0:s0 + FIELD_CHUNK], hh * strength)
    return h


def _normals(me):
    nrm = np.empty(len(me.vertices) * 3, np.float64)
    me.vertices.foreach_get('normal', nrm)
    return nrm.reshape(-1, 3)


def _gravity_dir(ob):
    """World down in the object's local space (unit)."""
    try:
        d = ob.matrix_world.to_3x3().inverted() @ Vector((0.0, 0.0, -1.0))
    except ValueError:
        d = Vector((0.0, 0.0, -1.0))
    if d.length < 1e-9:
        d = Vector((0.0, 0.0, -1.0))
    return np.array(d.normalized(), np.float64)


def prepare(context, ob, st, lines):
    """Stage 1 - the tubes: Add Detail, the line field on the mesh.  Returns the session dict (no cloth yet)."""
    me = ob.data
    levels = detail_levels(len(me.polygons)) if st.detail else 0
    if levels:
        _subdivide(me, levels)
    target = target_of(context, ob, fresh=True)
    co = mio.read_co(me)
    paths = [np.array([list(p) for p in line_path(target, ln)]) for ln in lines]
    return dict(stage='preview', co0=co, nrm=_normals(me), paths=paths, strengths=[ln['strength'] for ln in lines],
                size=target.size, levels=levels, verts=len(co), frames=st.frames, frame=0, field=None, field_key=None)


def tube_shape(sess, st):
    """The tubes on the original surface for the current sliders: the collider positions (N, 3) and the heights."""
    tube_r = sess['size'] * st.size / 100.0 * TUBE
    key = (round(st.size, 4), round(st.fade, 4), tuple(sess['strengths']))
    if sess['field'] is None or sess['field_key'] != key:
        sess['field'] = tube_field(sess['co0'], sess['paths'], sess['strengths'], tube_r, fade=st.fade / 100.0)
        sess['field_key'] = key
    sign = -1.0 if st.mode == 'CREASE' else 1.0
    h = sess['field'] * tube_r * sign * st.fold / 100.0
    sess['tube_r'] = tube_r
    sess['h'] = h
    return sess['co0'] + sess['nrm'] * h[:, None], h


def preview(sess, st, me):
    """The tubes written into the mesh (stage 1, live with the sliders)."""
    shape, _h = tube_shape(sess, st)
    mio.write_co(me, shape)
    me.update()
    return shape


def build(context, ob, st, sess):
    """Stage 2 - the cloth: a copy of the mesh laid over the collider (the original surface a margin in + the
    tubes), the open edges pinned, the rest lengths shrunk; the collider pushes the cloth out, with friction."""
    from . import cloth_pbd
    me = ob.data
    shape, h = tube_shape(sess, st)
    tube_r = sess['tube_r']
    margin = tube_r * MARGIN
    nrm = sess['nrm']
    collider = shape - nrm * margin
    co = shape + nrm * (tube_r * GAP)
    pin = np.zeros(len(co))
    bnd = boundary_verts(me) if st.pin_boundary else np.zeros(0, np.int64)
    if len(bnd):
        pin[bnd] = 1.0
    if st.pin_selected:
        sel = np.zeros(len(me.vertices), bool)
        me.vertices.foreach_get('select', sel)
        pin[sel] = 1.0
    bend, friction, damping = FABRIC_SIM.get(st.fabric, FABRIC_SIM['COTTON'])
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    cloth = cloth_pbd.Cloth(co, vi, start, tot, bend=bend, keep=st.keep / 100.0 * KEEP_SCALE, pin=pin)
    cloth.sor = SOR
    cloth.scale_e = cloth.scale_b = 1.0 - st.shrink / 100.0
    cloth.init = co.copy()
    edge_len = float(np.mean(np.linalg.norm(co[cloth.edges[:, 1]] - co[cloth.edges[:, 0]], axis=1))) if len(cloth.edges) else tube_r
    kd = KDTree(len(collider))
    for i, p in enumerate(collider):
        kd.insert(p, i)
    kd.balance()
    sess.update(stage='run', cloth=cloth, collider=collider, kd=kd, ref=np.arange(len(co)), pick=co.copy(),
                margin=margin, repick=edge_len * REPICK, friction=friction, damping=damping, frame=0,
                gdir=_gravity_dir(ob), frames=st.frames)
    cloth.collide = lambda c: collide(c, sess)
    return sess


def collide(cloth, sess):
    """The collider: every cloth point stays ``margin`` above the tangent plane of its collider point (re-picked
    by nearness when it slid); a touching point is held back toward where the frame began (friction)."""
    C, N = sess['collider'], sess['nrm']
    ref = sess['ref']
    rel = cloth.co - C[ref]
    hgt = (rel * N[ref]).sum(1)
    inside = hgt < sess['margin']
    if np.any(inside):
        cloth.co[inside] += N[ref[inside]] * (sess['margin'] - hgt[inside])[:, None]
    fr = sess['friction']
    if fr > 0:
        touch = hgt < sess['margin'] * 1.5
        if np.any(touch):
            cloth.co[touch] += (cloth.prev[touch] - cloth.co[touch]) * fr


def repick(sess):
    """Cloth points that slid more than ``repick`` since their last pick get the nearest collider point again."""
    cloth = sess['cloth']
    moved = np.linalg.norm(cloth.co - sess['pick'], axis=1) > sess['repick']
    idx = np.nonzero(moved)[0]
    if not len(idx):
        return 0
    kd, ref = sess['kd'], sess['ref']
    for i in idx:
        ref[i] = kd.find(cloth.co[i])[1]
    sess['pick'][idx] = cloth.co[idx]
    return len(idx)


def advance(sess, st):
    """One frame: gravity, then the solver with the collider.  Returns the positions."""
    cloth = sess['cloth']
    repick(sess)
    g = sess['gdir'] * (GRAV_UNIT * st.gravity / 100.0 * sess['size'])
    keep_rate = KEEP_RATE if st.keep > 0 else 0.0
    cloth.step(force=None, gravity=g, damping=sess['damping'], iterations=ITERATIONS, keep_rate=keep_rate)
    sess['frame'] += 1
    return cloth.co


def simulate(context, ob, st, lines, frames=None):
    """Headless / in one go: the tubes, then every frame, the last written into the mesh.  Returns info + time."""
    t = time.perf_counter()
    sess = prepare(context, ob, st, lines)
    build(context, ob, st, sess)
    if frames is not None:
        sess['frames'] = frames
    for _ in range(sess['frames']):
        advance(sess, st)
    mio.write_co(ob.data, sess['cloth'].co)
    ob.data.update()
    return dict(levels=sess['levels'], verts=sess['verts'], radius=sess['tube_r'], frames=sess['frames'],
                time=time.perf_counter() - t, lifted=int(np.count_nonzero(sess['h'] > sess['tube_r'] * 0.05)))


def cleanup(ob):
    """(nothing to take off the object: the solver lives outside it)"""


# the live session (one at a time)
SIM = {}


def sim_active():
    return bool(SIM.get('ob'))


def _sim_ob():
    return bpy.data.objects.get(SIM.get('ob', '')) if SIM else None


def stage():
    return SIM['sess']['stage'] if sim_active() else ''


def start(context, ob, st):
    """Stage 1: the tubes shown on the mesh (a backup kept); Space then runs the cloth."""
    lines = _lines_of(ob)
    if not lines:
        return None, 'Wrinkle Lines: draw a line on the mesh first'
    if sim_active():
        return None, 'a simulation is already on (Enter / Esc)'
    backup = ob.data.copy()
    backup.name = ob.data.name + '_mch_wl_backup'
    backup.use_fake_user = True
    try:
        sess = prepare(context, ob, st, lines)
        preview(sess, st, ob.data)
    except Exception:
        old = ob.data
        ob.data = backup                 # (Add Detail may have subdivided it already)
        backup.name = old.name
        backup.use_fake_user = False
        if old.users == 0:
            bpy.data.meshes.remove(old)
        raise
    SIM.clear()
    SIM.update(ob=ob.name, backup=backup.name, sess=sess, frames=sess['frames'], running=False, want=None,
               snapshot=_snapshot(st), done=False, info=dict(levels=sess['levels'], verts=sess['verts']))
    return SIM['info'], None


def refresh(context):
    """A tube slider moved while the tubes are shown: the shape again."""
    if stage() != 'preview':
        return False
    ob = _sim_ob()
    st = settings(context)
    if ob is None or st is None:
        return False
    preview(SIM['sess'], st, ob.data)
    SIM['snapshot'] = _snapshot(st)
    return True


def run(context):
    """Stage 2 from the shown tubes: the cloth built, the frames start."""
    ob = _sim_ob()
    st = settings(context)
    if ob is None or st is None or stage() != 'preview':
        return False
    build(context, ob, st, SIM['sess'])
    SIM.update(frames=SIM['sess']['frames'], running=True, done=False, snapshot=_snapshot(st))
    return True


def _snapshot(st):
    return tuple(getattr(st, k) for k in ('mode', 'fabric', 'size', 'fade', 'shrink', 'fold', 'gravity', 'keep',
                                          'pin_boundary', 'pin_selected', 'self_collision', 'detail', 'frames'))


def step(context):
    """One frame on, written into the mesh; False when the last frame is reached."""
    ob = _sim_ob()
    sess = SIM.get('sess')
    if ob is None or sess is None or sess['stage'] != 'run':
        return False
    if sess['frame'] >= SIM['frames']:
        SIM['running'] = False
        SIM['done'] = True
        return False
    st = settings(context)
    co = advance(sess, st)
    mio.write_co(ob.data, co)
    ob.data.update()
    return True


def confirm(context):
    """The shown state (tubes or the simulated frame) stays in the mesh; the backup dropped."""
    ob = _sim_ob()
    if ob is None:
        return 'nothing to keep'
    n = SIM['sess']['frame']
    what = 'the tubes' if stage() == 'preview' else f'frame {n}'
    _finish(context)
    _TARGET.pop(ob.name, None)
    for ln in _lines_of(ob):
        ln['path'] = None
    return f'Wrinkle Lines: kept {what} ({len(ob.data.vertices):,} points)'


def cancel(context):
    """The mesh as it was before (the lines stay)."""
    ob = _sim_ob()
    backup = bpy.data.meshes.get(SIM.get('backup', ''))
    if ob is not None:
        if backup is not None:
            old = ob.data
            ob.data = backup
            backup.name = old.name
            backup.use_fake_user = False
            if old.users == 0:
                bpy.data.meshes.remove(old)
        _TARGET.pop(ob.name, None)
        for ln in _lines_of(ob):
            ln['path'] = None
    elif backup is not None:
        bpy.data.meshes.remove(backup)
    _finish(context)
    return 'Wrinkle Lines: back to the start'


def _finish(context):
    backup = bpy.data.meshes.get(SIM.get('backup', ''))
    if backup is not None:
        backup.use_fake_user = False
        if backup.users == 0:
            bpy.data.meshes.remove(backup)
    SIM.clear()


def status():
    if not sim_active():
        return ''
    if stage() == 'preview':
        return 'tubes: set Wrinkle Size / Fold / End Fade  (Space simulate · Enter keep the tubes · Esc back)'
    n = SIM['sess']['frame']
    if SIM.get('done'):
        return f'done: frame {n} / {SIM["frames"]}  (Enter keep · Esc back · Space again from the start)'
    return (f'{"running" if SIM["running"] else "paused"}: frame {n} / {SIM["frames"]}  '
            f'(Space {"pause" if SIM["running"] else "continue"} · Enter keep · Esc back)')


# -----------------------------------------------------------------------------
# drawing
# -----------------------------------------------------------------------------

_handle = None
_HOVER = {'line': None, 'point': None, 'ob': None}


def _draw():
    try:
        import gpu
        from gpu_extras.batch import batch_for_shader
        context = bpy.context
        st = settings(context)
        ob = context.view_layer.objects.active if context.view_layer else None
        if st is None or not st.show or ob is None or ob.type != 'MESH':
            return
        from . import tool_state as ts
        native = ts.native_tool_id(context) or ''
        if native != 'mecha.wrinkle_lines' and not sim_active():
            return
        lines = _lines_of(ob)
        if not lines:
            return
        target = target_of(context, ob)
        region = context.region
        size = (region.width, region.height) if region else (1, 1)
        sh = gpu.shader.from_builtin('POLYLINE_UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        for depth, alpha in (('NONE', 0.2), ('LESS_EQUAL', 1.0)):
            gpu.state.depth_test_set(depth)
            sh.bind()
            sh.uniform_float('viewportSize', size)
            for li, ln in enumerate(lines):
                path = [tuple(target.to_world(p)) for p in line_path(target, ln)]
                if len(path) < 2:
                    continue
                last = li == len(lines) - 1
                hover = _HOVER['line'] == li and _HOVER['ob'] == ob.name
                col = (1.0, 0.85, 0.2, alpha) if last else (1.0, 0.35, 0.65, alpha)
                if hover:
                    col = (1.0, 1.0, 1.0, alpha)
                sh.uniform_float('lineWidth', 3.0 if (last or hover) else 2.0)
                sh.uniform_float('color', col)
                batch_for_shader(sh, 'LINE_STRIP', {'pos': path}).draw(sh)
        gpu.state.depth_test_set('NONE')
        psh = gpu.shader.from_builtin('UNIFORM_COLOR')
        psh.bind()
        for li, ln in enumerate(lines):
            pts = [tuple(target.to_world(p)) for p in ln['pts']]
            gpu.state.point_size_set(8.0)
            psh.uniform_float('color', (1.0, 0.9, 0.4, 1.0) if li == len(lines) - 1 else (1.0, 1.0, 1.0, 1.0))
            batch_for_shader(psh, 'POINTS', {'pos': pts}).draw(psh)
            if _HOVER['line'] == li and _HOVER['point'] is not None and _HOVER['ob'] == ob.name \
                    and _HOVER['point'] < len(pts):
                gpu.state.point_size_set(14.0)
                psh.uniform_float('color', (0.3, 1.0, 0.4, 1.0))
                batch_for_shader(psh, 'POINTS', {'pos': [pts[_HOVER['point']]]}).draw(psh)
        gpu.state.point_size_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:            # never break viewport drawing
        pass


def _redraw(context):
    if context.area:
        context.area.tag_redraw()


# -----------------------------------------------------------------------------
# picking
# -----------------------------------------------------------------------------


def _proj(context):
    return cg.Projector(context.region, context.region_data)


def near_point(context, ob, xy, px=HIT_PX):
    """(line index, point index) of the visible control point nearest the cursor, or None."""
    lines = _lines_of(ob)
    if not lines:
        return None
    proj = _proj(context)
    target = target_of(context, ob)
    best, bd = None, px * (bpy.context.preferences.system.ui_scale if bpy.context.preferences else 1.0)
    for li, ln in enumerate(lines):
        for pi, (p, n) in enumerate(zip(ln['pts'], ln['nrm'])):
            s = proj.to_screen(target.to_world(p))
            if s is None:
                continue
            _o, d = proj.ray(s)
            if target.normal_world(n).dot(Vector(d)) > 0.0:
                continue
            dist = math.dist(s, xy)
            if dist <= bd:
                best, bd = (li, pi), dist
    return best


def near_line(context, ob, xy, px=HIT_PX * 1.5):
    """(line index, segment index, t) of the line path nearest the cursor on screen, or None."""
    lines = _lines_of(ob)
    if not lines:
        return None
    proj = _proj(context)
    target = target_of(context, ob)
    best, bd = None, px * (bpy.context.preferences.system.ui_scale if bpy.context.preferences else 1.0)
    for li, ln in enumerate(lines):
        pts = ln['pts']
        scr = [proj.to_screen(target.to_world(p)) for p in pts]
        for i in range(len(pts) - 1):
            a, b = scr[i], scr[i + 1]
            if a is None or b is None:
                continue
            ab = (b[0] - a[0], b[1] - a[1])
            l2 = ab[0] * ab[0] + ab[1] * ab[1]
            t = 0.0 if l2 < 1e-9 else max(0.0, min(1.0, ((xy[0] - a[0]) * ab[0] + (xy[1] - a[1]) * ab[1]) / l2))
            q = (a[0] + ab[0] * t, a[1] + ab[1] * t)
            dist = math.dist(q, xy)
            if dist <= bd:
                best, bd = (li, i, t), dist
    return best


def hit(context, ob, xy):
    o, d = _proj(context).ray(xy)
    return target_of(context, ob).ray(o, d)


def pick_object(context, xy):
    o, d = _proj(context).ray(xy)
    dg = context.evaluated_depsgraph_get()
    ok, _loc, _nrm, _i, ob, _m = target_rules.scene_ray(context, dg, Vector(o), Vector(d))
    return ob if (ok and ob is not None and ob.type == 'MESH') else None


def _use_object(context, ob):
    if context.view_layer.objects.active is not ob:
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob


# -----------------------------------------------------------------------------
# operators
# -----------------------------------------------------------------------------


class MCH_OT_wrinkle_line_stroke(bpy.types.Operator):
    """Drag: a new wrinkle line on the surface. Drag a point: move it. Shift + click: a point added to the nearest line. Ctrl + click: that point removed"""
    bl_idname = 'mch.wrinkle_line_stroke'
    bl_label = 'Wrinkle Line'
    bl_options = {'REGISTER', 'UNDO'}

    add: BoolProperty(default=False, options={'SKIP_SAVE'})
    remove: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        if sim_active():
            self.report({'WARNING'}, 'Wrinkle Lines: Enter keeps / Esc drops the simulation first')
            return {'CANCELLED'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        ob = context.view_layer.objects.active
        if ob is None or ob.type != 'MESH' or (not _lines_of(ob) and hit(context, ob, xy) is None):
            picked = pick_object(context, xy)
            if picked is None:
                self.report({'WARNING'}, 'Wrinkle Lines: drag on a mesh')
                return {'CANCELLED'}
            _use_object(context, picked)
            ob = picked
        self.ob = ob.name
        lines = _lines_of(ob)
        if self.remove:
            got = near_point(context, ob, xy)
            if got is None:
                return {'CANCELLED'}
            li, pi = got
            if len(lines[li]['pts']) <= 2:
                del lines[li]
            else:
                del lines[li]['pts'][pi]
                del lines[li]['nrm'][pi]
                lines[li]['path'] = None
            _save(ob, lines)
            _HOVER.update(line=None, point=None)
            _redraw(context)
            return {'FINISHED'}
        if self.add:
            got = near_line(context, ob, xy)
            h = hit(context, ob, xy)
            if got is None or h is None:
                return {'CANCELLED'}
            li, i, _t = got
            lines[li]['pts'].insert(i + 1, h[0])
            lines[li]['nrm'].insert(i + 1, h[1])
            lines[li]['path'] = None
            _save(ob, lines)
            _redraw(context)
            return {'FINISHED'}
        got = near_point(context, ob, xy)
        self.drag = got
        self.hits = []
        if got is None:
            h = hit(context, ob, xy)
            if h is None:
                return {'CANCELLED'}
            self.hits = [h]
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def modal(self, context, event):
        ob = bpy.data.objects.get(self.ob)
        if ob is None:
            return {'CANCELLED'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        if event.type == 'MOUSEMOVE':
            h = hit(context, ob, xy)
            if h is not None:
                if self.drag is not None:
                    li, pi = self.drag
                    ln = _lines_of(ob)[li]
                    ln['pts'][pi], ln['nrm'][pi] = h
                    ln['path'] = None
                else:
                    self.hits.append(h)
            _redraw(context)
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            lines = _lines_of(ob)
            if self.drag is None:
                target = target_of(context, ob)
                length = sum((b[0] - a[0]).length for a, b in zip(self.hits, self.hits[1:]))
                if length < target.size * 0.01 or len(self.hits) < 2:
                    _redraw(context)
                    return {'CANCELLED'}
                pts = thin_stroke(self.hits, point_count(length, target.size))
                st = settings(context)
                lines.append(dict(pts=[p for p, _n in pts], nrm=[n for _p, n in pts],
                                  strength=(st.strength / 100.0 if st else 1.0), path=None))
            _save(ob, lines)
            _redraw(context)
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'}:
            if self.drag is None:
                _redraw(context)
                return {'CANCELLED'}
            return {'RUNNING_MODAL'}
        return {'RUNNING_MODAL'}


class MCH_OT_wrinkle_line_hover(bpy.types.Operator):
    """(mouse move) the point / line under the cursor is highlighted"""
    bl_idname = 'mch.wrinkle_line_hover'
    bl_label = 'Wrinkle Line Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        ob = context.view_layer.objects.active
        if ob is None or ob.type != 'MESH' or not _lines_of(ob):
            return {'PASS_THROUGH'}
        xy = (event.mouse_region_x, event.mouse_region_y)
        got = near_point(context, ob, xy)
        line = near_line(context, ob, xy)
        new = dict(line=got[0] if got else (line[0] if line else None), point=got[1] if got else None, ob=ob.name)
        if new != _HOVER:
            _HOVER.update(new)
            _redraw(context)
        return {'PASS_THROUGH'}


class MCH_OT_wrinkle_line_delete(bpy.types.Operator):
    """X: the line under the mouse is removed (none under it: the last line)"""
    bl_idname = 'mch.wrinkle_line_delete'
    bl_label = 'Remove Wrinkle Line'
    bl_options = {'REGISTER', 'UNDO'}
    all: BoolProperty(default=False, options={'SKIP_SAVE'})

    def invoke(self, context, event):
        self.xy = (event.mouse_region_x, event.mouse_region_y)
        return self.execute(context)

    def execute(self, context):
        ob = context.view_layer.objects.active
        lines = _lines_of(ob)
        if not lines:
            return {'CANCELLED'}
        if self.all:
            _save(ob, [])
        else:
            got = near_line(context, ob, getattr(self, 'xy', (-1e9, -1e9))) if context.region_data else None
            del lines[got[0] if got else -1]
            _save(ob, lines)
        _HOVER.update(line=None, point=None)
        _redraw(context)
        return {'FINISHED'}


class MCH_OT_wrinkle_sim(bpy.types.Operator):
    """Space: the simulation runs (again: pauses / continues). Enter keeps the result, Esc goes back"""
    bl_idname = 'mch.wrinkle_sim'
    bl_label = 'Wrinkle Simulation'
    bl_options = {'REGISTER', 'UNDO'}

    _timer = None
    _area = None

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        if sim_active():                           # (the live modal consumes Space itself: this is a stale session)
            SIM['want'] = 'toggle'
            return {'CANCELLED'}
        ob = context.view_layer.objects.active
        st = settings(context)
        if ob is None or ob.type != 'MESH' or st is None:
            self.report({'WARNING'}, 'Wrinkle Lines: select the mesh with the lines')
            return {'CANCELLED'}
        try:
            info, err = start(context, ob, st)
        except Exception as ex:
            import traceback
            traceback.print_exc()
            self.report({'ERROR'}, f'Wrinkle Lines failed: {ex}')
            return {'CANCELLED'}
        if info is None:
            self.report({'WARNING'}, err)
            return {'CANCELLED'}
        self.ob = ob.name
        self._area = context.area
        wm = context.window_manager
        self._timer = wm.event_timer_add(0.02, window=context.window)
        wm.modal_handler_add(self)
        self._hint(context)
        return {'RUNNING_MODAL'}

    def _hint(self, context):
        if context.area:
            context.area.header_text_set('Wrinkle Lines  ' + status())
            context.area.tag_redraw()

    def _end(self, context):
        if self._timer is not None:
            context.window_manager.event_timer_remove(self._timer)
            self._timer = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        if not sim_active():
            self._end(context)
            return {'CANCELLED'}
        if context.area is not None and context.area != self._area:
            self._hint(context)
        want = SIM.get('want')
        if want:
            SIM['want'] = None
            if want == 'confirm':
                return self._confirm(context)
            if want == 'cancel':
                return self._cancel(context)
            if want == 'restart':
                self._restart(context)
            elif want == 'toggle':
                self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type == 'TIMER':
            if SIM['running']:
                step(context)
                self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type == 'SPACE' and event.value == 'PRESS':
            self._toggle(context)
            self._hint(context)
            return {'RUNNING_MODAL'}
        if event.type in {'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS':
            return self._confirm(context)
        if event.type == 'ESC' and event.value == 'PRESS':
            return self._cancel(context)
        return {'PASS_THROUGH'}

    def _toggle(self, context):
        st = settings(context)
        if stage() == 'preview':
            run(context)                  # the tubes are set: the cloth goes
            return
        if SIM.get('done'):
            self._restart(context)
            return
        if not SIM['running'] and st is not None and _snapshot(st) != SIM.get('snapshot'):
            self._restart(context)        # the settings changed while paused: from the start with them
            return
        SIM['running'] = not SIM['running']

    def _restart(self, context):
        """From the start with the current settings: the tubes again, then the cloth."""
        st = settings(context)
        ob = _sim_ob()
        cancel(context)
        if ob is not None and st is not None:
            try:
                start(context, ob, st)
                run(context)
            except Exception as ex:
                self.report({'ERROR'}, f'Wrinkle Lines failed: {ex}')

    def _confirm(self, context):
        msg = confirm(context)
        self._end(context)
        self.report({'INFO'}, msg)
        return {'FINISHED'}

    def _cancel(self, context):
        msg = cancel(context)
        self._end(context)
        self.report({'INFO'}, msg)
        return {'CANCELLED'}


class MCH_OT_wrinkle_sim_control(bpy.types.Operator):
    """Run / pause, keep, go back or restart the live simulation (the panel buttons)"""
    bl_idname = 'mch.wrinkle_sim_control'
    bl_label = 'Wrinkle Simulation Control'
    bl_options = {'INTERNAL'}
    action: bpy.props.StringProperty(default='toggle', options={'SKIP_SAVE'})

    def execute(self, context):
        if not sim_active():
            if self.action in {'toggle', 'restart'}:
                return bpy.ops.mch.wrinkle_sim('INVOKE_DEFAULT')
            return {'CANCELLED'}
        SIM['want'] = self.action
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# panel
# -----------------------------------------------------------------------------


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    ob = context.view_layer.objects.active
    lines = _lines_of(ob) if ob is not None and ob.type == 'MESH' else []
    box = layout.box()
    box.label(text='Wrinkle Lines', icon='MOD_CLOTH')
    live = sim_active()
    if live:
        box.label(text=status(), icon='PLAY')
    else:
        box.label(text=f'{len(lines)} line(s) on {ob.name}' if lines and ob else 'drag on the mesh: a wrinkle line', icon='INFO')
        box.label(text='Space: tubes on the lines  ·  Space: the cloth over them', icon='BLANK1')
    r = box.row(align=True)
    if not live:
        run_text, run_icon = 'Tubes (Space)', 'CURVE_DATA'
    elif stage() == 'preview':
        run_text, run_icon = 'Simulate (Space)', 'PLAY'
    elif SIM.get('done'):
        run_text, run_icon = 'Again (Space)', 'FILE_REFRESH'
    elif SIM.get('running'):
        run_text, run_icon = 'Pause (Space)', 'PAUSE'
    else:
        run_text, run_icon = 'Continue (Space)', 'PLAY'
    r.operator('mch.wrinkle_sim_control', text=run_text, icon=run_icon).action = 'toggle'
    r.operator('mch.wrinkle_sim_control', text='Restart', icon='FILE_REFRESH').action = 'restart'
    r = box.row(align=True)
    r.enabled = live
    r.operator('mch.wrinkle_sim_control', text='Keep (Enter)', icon='CHECKMARK').action = 'confirm'
    r.operator('mch.wrinkle_sim_control', text='Back (Esc)', icon='LOOP_BACK').action = 'cancel'
    r = box.row(align=True)
    r.prop(st, 'show', text='Show Lines', toggle=True)
    r.operator('mch.wrinkle_line_delete', text='Clear Lines', icon='X').all = True
    box.prop(st, 'strength', slider=True)
    box.row().prop(st, 'mode', expand=True)
    box.row().prop(st, 'fabric', expand=True)
    col = box.column(align=True)
    col.label(text='Tubes along the lines', icon='CURVE_DATA')
    col.prop(st, 'size', slider=True)
    col.prop(st, 'fold', slider=True)
    col.prop(st, 'fade', slider=True)
    col = box.column(align=True)
    col.label(text='Cloth over them', icon='MOD_CLOTH')
    col.prop(st, 'shrink', slider=True)
    col.prop(st, 'gravity', slider=True)
    col.prop(st, 'keep', slider=True)
    r = box.row(align=True)
    r.prop(st, 'pin_boundary', toggle=True)
    r.prop(st, 'pin_selected', toggle=True)
    r = box.row(align=True)
    r.prop(st, 'self_collision', toggle=True)
    r.prop(st, 'detail', toggle=True)
    box.prop(st, 'frames')


TOOL_KEYMAP = (
    ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'any': True}, None),
    ('mch.quick_hud_press', {'type': 'LEFTMOUSE', 'value': 'DOUBLE_CLICK', 'any': True}, None),
    ('mch.wrinkle_line_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, {'properties': [('add', True)]}),
    ('mch.wrinkle_line_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'ctrl': True}, {'properties': [('remove', True)]}),
    ('mch.wrinkle_line_stroke', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
    ('mch.wrinkle_line_hover', {'type': 'MOUSEMOVE', 'value': 'ANY'}, None),
    ('mch.wrinkle_line_delete', {'type': 'X', 'value': 'PRESS'}, None),
    ('mch.wrinkle_sim', {'type': 'SPACE', 'value': 'PRESS'}, None),
    ('mch.rmb_gate', {'type': 'RIGHTMOUSE', 'value': 'PRESS'}, {'properties': [('popup', 'SHAPE')]}),
    ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None),
)

CLASSES = (MCH_PG_WrinkleLines, MCH_OT_wrinkle_line_stroke, MCH_OT_wrinkle_line_hover, MCH_OT_wrinkle_line_delete,
           MCH_OT_wrinkle_sim, MCH_OT_wrinkle_sim_control)


def register():
    global _handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_wlines = bpy.props.PointerProperty(type=MCH_PG_WrinkleLines)
    if not bpy.app.background and _handle is None:
        _handle = bpy.types.SpaceView3D.draw_handler_add(_draw, (), 'WINDOW', 'POST_VIEW')


def unregister():
    global _handle
    if _handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _handle = None
    if sim_active():
        try:
            cancel(bpy.context)
        except Exception:
            SIM.clear()
    _CACHE.clear()
    _TARGET.clear()
    if hasattr(bpy.types.Scene, 'mch_wlines'):
        del bpy.types.Scene.mch_wlines
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
