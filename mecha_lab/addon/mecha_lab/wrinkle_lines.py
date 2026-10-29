"""0.24.92 Wrinkle Lines: draw guide lines on a mesh, a short cloth simulation folds the surface along them.

Not a full garment simulation: the aim is "a pretty wrinkle where I want it" on a game model.  The mesh itself
(no copy, no new layer) becomes a cloth for a few frames:

    * along the drawn lines the fabric is **shrunk** (Blender cloth Shrinking through a vertex group whose weight
      falls off with the distance to the lines: Wrinkle Size) - the surface gathers there and folds;
    * the mesh boundary (open edges: the ends of a sleeve) is pinned, everything far from the lines is pinned
      *softly* (Silhouette Keep = the pin weight away from the lines), so the part keeps its shape and the folds
      stay where the lines are;
    * a fabric preset (Cotton / Denim / Silk / Leather / Knit) sets mass and stiffness, Gravity the sag;
    * Crease mode pushes the line itself in (a fold line) and shrinks a narrow band round it.

Keys (the Wrinkle Lines tool):  drag = a new line on the surface · drag a point = move it · Shift + click = a point
added to the nearest line · Ctrl + click = that point removed · X = the line under the mouse removed ·
Space = run / pause the simulation · Enter = keep the result · Esc = back to the start (the lines stay).

The lines live on the object (``PROP``, local space) so they stay on the mesh while orbiting and survive a save.
The simulation runs in the user's scene frame by frame (a timer), so the cloth is seen folding; Enter bakes the
frame into the mesh, Esc puts the saved copy of the mesh back.  ``weights`` and ``simulate`` are plain functions
(tested headless).
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
MODES = (('WRINKLE', 'Wrinkle Line', 'The fabric gathers along the line: soft folds run off it'),
         ('CREASE', 'Crease', 'A fold line: the line itself is pushed in, a narrow band shrinks round it'))


# -----------------------------------------------------------------------------
# settings
# -----------------------------------------------------------------------------


class MCH_PG_WrinkleLines(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Mode', items=MODES, default='WRINKLE')
    fabric: EnumProperty(name='Fabric', items=FABRIC_ITEMS, default='COTTON')
    size: FloatProperty(name='Wrinkle Size', description='How far from a line the fabric gathers, as % of the part size',
                        default=5.0, min=0.5, max=30.0, subtype='PERCENTAGE')
    shrink: FloatProperty(name='Shrink', description='How much the fabric along a line shrinks (more = deeper folds)',
                          default=33.0, min=0.0, max=90.0, subtype='PERCENTAGE')
    fold: FloatProperty(name='Fold Strength', description='Wrinkle Line: how hard the line pulls; Crease: how deep the line is pushed in',
                        default=100.0, min=0.0, max=200.0, subtype='PERCENTAGE')
    gravity: FloatProperty(name='Gravity', default=30.0, min=0.0, max=300.0, subtype='PERCENTAGE')
    keep: FloatProperty(name='Silhouette Keep', description='How firmly the surface away from the lines stays where it is',
                        default=47.0, min=0.0, max=100.0, subtype='PERCENTAGE')
    strength: FloatProperty(name='Line Strength', description='The strength of the last drawn line (each line keeps its own)',
                            default=100.0, min=0.0, max=200.0, subtype='PERCENTAGE', update=lambda s, c: _strength_changed(s, c))
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


def _strength_changed(st, context):
    lines = _lines_of(context.view_layer.objects.active)
    if lines:
        lines[-1]['strength'] = st.strength / 100.0
        _save(context.view_layer.objects.active, lines)


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

RIDGE = 0.5                      # Crease: the line pushed in by Wrinkle Size x this x Fold Strength
PINCH = 0.3                      # Wrinkle Line: the pull toward the line per frame, x Fold Strength x line strength
KEEP_RATE = 0.1                  # Silhouette Keep 47 % -> this much of the way back per frame (x keep / 0.47)
ITERATIONS = 12                  # constraint passes per frame
SOR = 1.6
JITTER = 0.02                    # x Wrinkle Size: the nudge a perfectly even surface needs to start folding
# fabric: bending constraint strength, Laplacian smoothing (fold breadth), damping
FABRIC_SIM = {'COTTON': (0.5, 0.2, 0.1), 'DENIM': (1.0, 0.4, 0.2), 'SILK': (0.2, 0.1, 0.05), 'LEATHER': (1.0, 0.5, 0.3),
              'KNIT': (0.4, 0.15, 0.1)}


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


def line_field(co, paths, strengths, radius, crease=False):
    """Per point: the weight of the nearest line (``weights``) and the nearest point ON that line (the pinch
    target).  Returns (w, target)."""
    n = len(co)
    w = np.zeros(n)
    target = co.copy()
    r = radius * (0.5 if crease else 1.0)
    for path, strength in zip(paths, strengths):
        if len(path) < 2 or strength <= 0 or r <= 0:
            continue
        kd = KDTree(len(path))
        for i, p in enumerate(path):
            kd.insert(p, i)
        kd.balance()
        d = np.empty(n)
        near = np.empty((n, 3))
        for i in range(n):
            pt, _j, dist = kd.find(co[i])
            d[i], near[i] = dist, pt
        t = np.clip(d / r, 0.0, 1.0)
        f = ((1.0 - t) if crease else (1.0 - t * t) ** 2) * strength
        better = f > w
        w[better] = np.clip(f[better], 0.0, 1.0)
        target[better] = near[better]
    return w, target


def build(context, ob, st, lines):
    """The cloth for ``ob``'s mesh (Add Detail first): the line field, the pins, the solver.  Returns the
    session dict."""
    from . import cloth_pbd
    me = ob.data
    levels = detail_levels(len(me.polygons)) if st.detail else 0
    if levels:
        _subdivide(me, levels)
    target = target_of(context, ob, fresh=True)
    size = target.size
    radius = size * st.size / 100.0
    co = mio.read_co(me)
    paths = [np.array([list(p) for p in line_path(target, ln)]) for ln in lines]
    crease = st.mode == 'CREASE'
    w, tgt = line_field(co, paths, [ln['strength'] for ln in lines], radius, crease=crease)
    pin = np.zeros(len(co))
    bnd = boundary_verts(me) if st.pin_boundary else np.zeros(0, np.int64)
    if len(bnd):
        pin[bnd] = 1.0
    if st.pin_selected:
        sel = np.zeros(len(me.vertices), bool)
        me.vertices.foreach_get('select', sel)
        pin[sel] = 1.0
    if crease and st.fold > 0:               # the line pushed in and held: a fold line the cloth settles round
        nrm = np.zeros((len(co), 3))
        me.vertices.foreach_get('normal', nrm.ravel())
        depth = radius * RIDGE * st.fold / 100.0
        co = co - nrm * (w * depth)[:, None]
        pin = np.maximum(pin, np.clip(w * 2.0 - 0.5, 0.0, 1.0))
    bend, smooth, damping = FABRIC_SIM.get(st.fabric, FABRIC_SIM['COTTON'])
    vi = mio.read_corner_verts(me)
    start, tot = mio.read_face_starts(me)
    cloth = cloth_pbd.Cloth(co, vi, start, tot, bend=bend, keep=st.keep / 100.0, pin=pin)
    cloth.sor = SOR
    cloth.smooth = smooth * (0.5 + 0.5 * st.size / 5.0)        # (a bigger Wrinkle Size: broader folds)
    cloth.jitter(radius * JITTER, seed=1)
    cloth.init = co.copy()
    return dict(cloth=cloth, w=w, target=tgt, radius=radius, centre=co.mean(0), damping=damping, crease=crease,
                levels=levels, verts=len(co), frames=st.frames, frame=0, fps=max(1.0, context.scene.render.fps / max(1e-6, context.scene.render.fps_base)))


def advance(sess, st):
    """One frame of the session: the forces of this frame (scale toward the centre, the pinch toward the lines,
    gravity), then the solver.  Returns the positions."""
    cloth = sess['cloth']
    n = cloth.n
    force = np.zeros((n, 3))
    frames = max(1, sess['frames'])
    if st.shrink > 0:
        force += cloth.scale_force(st.shrink / 100.0 / frames, sess['centre'])
    if not sess['crease'] and st.fold > 0:
        force += cloth.toward_force(sess['target'], PINCH * st.fold / 100.0, mask=sess['w'])
    dt = 1.0 / sess['fps']
    g = -9.8 * st.gravity / 100.0 * dt * dt * sess['radius'] / 0.05      # (scaled to the part: 5 % size = 1 unit)
    keep_rate = KEEP_RATE * (st.keep / 47.0) if st.keep > 0 else 0.0
    cloth.step(force=force, gravity=(0.0, 0.0, g), damping=sess['damping'], iterations=ITERATIONS, keep_rate=keep_rate)
    sess['frame'] += 1
    return cloth.co


def simulate(context, ob, st, lines, frames=None):
    """Headless / in one go: every frame, the last written into the mesh.  Returns the session info + time."""
    t = time.perf_counter()
    sess = build(context, ob, st, lines)
    if frames is not None:
        sess['frames'] = frames
    for _ in range(sess['frames']):
        advance(sess, st)
    mio.write_co(ob.data, sess['cloth'].co)
    ob.data.update()
    return dict(levels=sess['levels'], verts=sess['verts'], radius=sess['radius'], frames=sess['frames'],
                time=time.perf_counter() - t, shrink=float(sess['w'].max()) if len(sess['w']) else 0.0)


def cleanup(ob):
    """(nothing to take off the object: the solver lives outside it)"""


# the live session (one at a time)
SIM = {}


def sim_active():
    return bool(SIM.get('ob'))


def _sim_ob():
    return bpy.data.objects.get(SIM.get('ob', '')) if SIM else None


def start(context, ob, st):
    lines = _lines_of(ob)
    if not lines:
        return None, 'Wrinkle Lines: draw a line on the mesh first'
    if sim_active():
        return None, 'a simulation is already on (Enter / Esc)'
    backup = ob.data.copy()
    backup.name = ob.data.name + '_mch_wl_backup'
    backup.use_fake_user = True
    try:
        sess = build(context, ob, st, lines)
    except Exception:
        old = ob.data
        ob.data = backup                 # (Add Detail may have subdivided it already)
        backup.name = old.name
        backup.use_fake_user = False
        if old.users == 0:
            bpy.data.meshes.remove(old)
        raise
    SIM.clear()
    SIM.update(ob=ob.name, backup=backup.name, sess=sess, frames=sess['frames'], running=True, want=None,
               snapshot=_snapshot(st), done=False, info=dict(levels=sess['levels'], verts=sess['verts']))
    return SIM['info'], None


def _snapshot(st):
    return tuple(getattr(st, k) for k in ('mode', 'fabric', 'size', 'shrink', 'fold', 'gravity', 'keep', 'pin_boundary',
                                          'pin_selected', 'self_collision', 'detail', 'frames'))


def step(context):
    """One frame on, written into the mesh; False when the last frame is reached."""
    ob = _sim_ob()
    sess = SIM.get('sess')
    if ob is None or sess is None:
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
    """The simulated frame stays in the mesh; the backup dropped."""
    ob = _sim_ob()
    if ob is None:
        return 'nothing to keep'
    n = SIM['sess']['frame']
    _finish(context)
    _TARGET.pop(ob.name, None)
    for ln in _lines_of(ob):
        ln['path'] = None
    return f'Wrinkle Lines: kept frame {n} ({len(ob.data.vertices):,} points)'


def cancel(context):
    """The mesh as it was before the simulation (the lines stay)."""
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
    if backup is not None and backup.users == 0:
        bpy.data.meshes.remove(backup)
    SIM.clear()


def status():
    if not sim_active():
        return ''
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
        if SIM.get('done'):
            self._restart(context)
            return
        if not SIM['running'] and st is not None and _snapshot(st) != SIM.get('snapshot'):
            self._restart(context)        # the settings changed while paused: from the start with them
            return
        SIM['running'] = not SIM['running']

    def _restart(self, context):
        st = settings(context)
        ob = _sim_ob()
        cancel(context)
        if ob is not None and st is not None:
            try:
                start(context, ob, st)
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
    r = box.row(align=True)
    r.operator('mch.wrinkle_sim_control', text='Pause (Space)' if (live and SIM.get('running')) else
               ('Continue (Space)' if live and not SIM.get('done') else 'Simulate (Space)'), icon='PLAY').action = 'toggle'
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
    col.prop(st, 'size', slider=True)
    col.prop(st, 'shrink', slider=True)
    col.prop(st, 'fold', slider=True)
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
