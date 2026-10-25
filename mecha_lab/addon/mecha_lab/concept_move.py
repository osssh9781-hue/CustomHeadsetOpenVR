"""0.24.32 Concept Move: grab the surface and pull it - the stretch-and-look move of VR modelers, in Object Mode.

Press on a mesh and drag: the area under the brush follows the mouse like clay (a light preview while you drag).
When you let go the pulled part is really generated: what got stretched is split in its rest shape and pulled
again, so the new points sit on the curved surface and the faces stay as dense as the rest of the mesh (no long
stretched faces).  Then F9 / Adjust Last Operation: Size, Hardness, Pull, Shape, Falloff - recomputed from the
original.
* Shape: Sphere or Box (a view-aligned cube - frames, plates, flat panels).  Hardness: how much of the brush moves
  whole (1 = a rigid lump, 0 = a soft dome).  Falloffs: Clay (hardness), Elastic (Kelvinlet grab), Sharp.
* While dragging: Shift = straight out of the surface, Ctrl + left / right = turn the grabbed part, wheel = depth, [ ] = size, right click / Esc = cancel.
  A 3D mouse (and middle mouse) still navigates the view; with Follow View the grab stays in front of you, so
  moving the view carries the clay even with the mouse held still (re-evaluated 60 times a second).
* Live objects (cape, hood, plates ... still on their sliders) need no Apply: every move is recorded on the object
  and replayed (with the same generation) each time the sliders rebuild it.  Clear Moves forgets them.
* Hold D and drag (in any tool of the MECHA LAB workspace): the same move without switching tools.
* F + move the mouse: brush size (like sculpting).  Real Size keeps the brush the same size in the scene when
  you zoom.
* Shift+click: drop a clay blob.  Fuse: join the selected clay into one smooth piece (voxel remesh).
While dragging only the points the brush can reach are computed, and a still frame costs nothing.
``clay_weights``, ``elastic_weights``, ``sharp_weights``, ``box_distance``, ``displace`` and ``generate`` are the
working parts (numpy / bmesh, no UI).
"""
from __future__ import annotations

import json
import math

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty
from bpy_extras import view3d_utils
from mathutils import Vector

MOVES_KEY = 'mch_concept_moves'
FALLOFF_ITEMS = [
    ('CLAY', 'Clay', 'Hardness decides how much moves whole; keeps the thickness of what you grab'),
    ('ELASTIC', 'Elastic', 'Soft rubber: the whole area stretches, volume is kept (Kelvinlet grab)'),
    ('SHARP', 'Sharp', 'A tight pull: a spike / horn / finger'),
]
SHAPE_ITEMS = [
    ('SPHERE', 'Sphere', 'Round brush'),
    ('BOX', 'Box', 'Square brush (a cube facing the view): frames, plates, flat panels'),
]


# -----------------------------------------------------------------------------
# pure math
# -----------------------------------------------------------------------------


def elastic_weights(dist, radius, poisson=0.4):
    """Regularised Kelvinlet grab, as scalar part + radial part factors, normalised to 1 at the centre.

    Returns (s, t) arrays: displacement = s * d + t * (r . d) r  (r = point - centre)."""
    a = 1.0 / (4.0 * math.pi)
    b = a / (4.0 * (1.0 - poisson))
    eps = max(radius, 1e-9)
    re = np.sqrt(dist * dist + eps * eps)
    s = (a - b) / re + a * eps * eps / (2.0 * re ** 3)
    t = b / re ** 3
    norm = (a - b) / eps + a / (2.0 * eps)
    # infinite support -> fade out far away (2.5 .. 4 radii) so other parts of the mesh stay put
    fade = np.clip((4.0 * eps - dist) / (1.5 * eps), 0.0, 1.0)
    fade = fade * fade * (3.0 - 2.0 * fade)
    return s / norm * fade, t / norm * fade


def clay_weights(dist, radius, hardness=0.5):
    """1 inside hardness*radius (moves whole), smooth fade to 0 at the brush edge (radius)."""
    r = max(radius, 1e-9)
    core = min(max(hardness, 0.0), 0.98) * r
    x = np.clip((r - dist) / (r - core), 0.0, 1.0)
    return x * x * (3.0 - 2.0 * x)


def sharp_weights(dist, radius):
    x = np.clip(1.0 - dist / max(radius, 1e-9), 0.0, 1.0)
    return (x * x * (3.0 - 2.0 * x)) ** 3


def box_distance(r, axes, round_=0.2):
    """'Distance' for a box brush: the largest coordinate along the three axes (rows of axes), corners slightly
    rounded (round_ = 0 -> a sharp cube)."""
    p = np.abs(r @ np.asarray(axes, dtype=np.float64).T)
    if round_ <= 0:
        return p.max(1)
    k = 1.0 / max(round_, 1e-3) * 4.0                       # smooth max (p-norm)
    return (p ** k).sum(1) ** (1.0 / k)


def rotation_matrix(axis, angle):
    """3x3 rotation about ``axis`` by ``angle`` (Rodrigues) - numpy."""
    a = np.asarray(axis, dtype=np.float64)
    n = np.linalg.norm(a)
    if n < 1e-12 or abs(angle) < 1e-12:
        return np.eye(3)
    x, y, z = a / n
    k = np.array([[0.0, -z, y], [z, 0.0, -x], [-y, x, 0.0]])
    return np.eye(3) + math.sin(angle) * k + (1.0 - math.cos(angle)) * (k @ k)


def displace(co, centre, delta, radius, falloff='CLAY', mirror_x=False, shape='SPHERE', hardness=0.5,
             axes=None, twist=None):
    """New coordinates (N,3) for a grab at centre moved by delta (all in the same space).
    ``twist`` = (axis x, y, z, angle): the grabbed part also turns round the grab point (Ctrl while dragging)."""
    co = np.asarray(co, dtype=np.float64)
    out = co.copy()
    if axes is None:
        axes = np.eye(3)
    axes = np.asarray(axes, dtype=np.float64).reshape(3, 3)
    tw_axis = np.asarray(twist[:3], dtype=np.float64) if twist is not None else np.zeros(3)
    tw_angle = float(twist[3]) if twist is not None else 0.0
    brushes = [(np.asarray(centre, dtype=np.float64), np.asarray(delta, dtype=np.float64), axes,
                rotation_matrix(tw_axis, tw_angle))]
    if mirror_x and abs(centre[0]) > radius * 0.5:          # a grab on the middle already moves both sides
        flip = np.array([-1.0, 1.0, 1.0])
        # a mirrored turn: the axis keeps x and flips y / z (axial vector under the X mirror)
        rot_m = rotation_matrix(tw_axis * np.array([1.0, -1.0, -1.0]), tw_angle)
        brushes.append((brushes[0][0] * flip, brushes[0][1] * flip, axes * flip, rot_m))
    for c, d, ax, rot in brushes:
        r = co - c
        if tw_angle:                                          # the turn of the grabbed part, as a move
            d = d[None, :] + r @ rot.T - r
        dist = box_distance(r, ax) if shape == 'BOX' else np.sqrt((r * r).sum(1))
        dd = d if d.ndim == 2 else d[None, :]
        if falloff == 'ELASTIC':
            s, t = elastic_weights(dist, radius)
            out += s[:, None] * dd + (t * (r * dd).sum(1))[:, None] * r
        elif falloff == 'SHARP':
            out += sharp_weights(dist, radius)[:, None] * dd
        else:
            out += clay_weights(dist, radius, hardness)[:, None] * dd
    return out


def move_field(move):
    """A recorded move (dict) -> function rest coords (N,3) -> moved coords."""
    def f(co):
        return displace(co, move['centre'], move['delta'], move['radius'], move.get('falloff', 'CLAY'),
                        move.get('mirror', False), move.get('shape', 'SPHERE'), move.get('hardness', 0.5),
                        move.get('axes'), move.get('twist'))
    return f


def reach(move):
    """How far from the grab point anything moves (elastic fades out by 4 radii, a box reaches its corners)."""
    r = move['radius']
    if move.get('falloff') == 'ELASTIC':
        return 4.0 * r
    return r * (math.sqrt(3.0) if move.get('shape') == 'BOX' else 1.0) * 1.01


def near_mask(co, move):
    """Points the move can touch (around the grab point and its X mirror) - the rest are skipped."""
    c = np.asarray(move['centre'], dtype=np.float64)
    lim = reach(move) ** 2
    mask = ((co - c) ** 2).sum(1) <= lim
    if move.get('mirror'):
        mask |= ((co - c * np.array([-1.0, 1.0, 1.0])) ** 2).sum(1) <= lim
    return mask


def fast_field(move, mask):
    """Like move_field, but only the masked points are computed (the drag preview on heavy meshes)."""
    f = move_field(move)

    def g(co):
        out = co.copy()
        if mask.any():
            out[mask] = f(co[mask])
        return out
    return g


# -----------------------------------------------------------------------------
# mesh helpers
# -----------------------------------------------------------------------------


def read_coords(me):
    co = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3).astype(np.float64)


def write_coords(me, co):
    me.vertices.foreach_set('co', np.asarray(co, dtype=np.float32).ravel())
    me.update()


def generate(me, field, ratio=1.3, max_rounds=6, max_verts=400000, relax=0):
    """Really generate the pulled part: split (in the rest shape) every edge the field stretches past ratio x the
    mesh's usual edge, repeat, then move everything.  New points land on the smooth moved surface, the faces keep
    the mesh's density.  ``relax`` > 0 (Even Out): that many passes evening out the moved part along its surface
    (sharp edges and corners stay).  Returns the number of edges split."""
    bm = bmesh.new()
    bm.from_mesh(me)
    split = 0
    target = None
    for _round in range(max_rounds):
        bm.verts.ensure_lookup_table()
        bm.verts.index_update()
        rest = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
        moved = field(rest)
        ev = np.array([(e.verts[0].index, e.verts[1].index) for e in bm.edges], dtype=np.int64)
        if not len(ev):
            break
        l0 = np.linalg.norm(rest[ev[:, 0]] - rest[ev[:, 1]], axis=1)
        l1 = np.linalg.norm(moved[ev[:, 0]] - moved[ev[:, 1]], axis=1)
        if target is None:
            target = float(np.median(l0)) * ratio
        stretch = l1 / np.maximum(l0, 1e-12)
        bad = np.nonzero((l1 > target) & (stretch > 1.05))[0]
        if not len(bad) or len(bm.verts) + len(bad) > max_verts:
            break
        bm.edges.ensure_lookup_table()
        bm.edges.index_update()
        # split whole rings across quads (the opposite edge of each quad, while it is stretched too):
        # new clean edge loops, quads stay quads
        chosen = set(int(i) for i in bad)
        stack = list(chosen)
        while stack:
            e = bm.edges[stack.pop()]
            for f in e.link_faces:
                if len(f.edges) != 4:
                    continue
                k = list(f.edges).index(e)
                o = f.edges[(k + 2) % 4]
                if o.index not in chosen and stretch[o.index] > 1.12 and l1[o.index] > target * 0.6:
                    chosen.add(o.index)
                    stack.append(o.index)
        if len(bm.verts) + len(chosen) > max_verts:
            break
        edges = [bm.edges[i] for i in chosen]
        bad = chosen
        bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        split += len(bad)
    bm.verts.ensure_lookup_table()
    rest = np.array([v.co[:] for v in bm.verts], dtype=np.float64)
    moved = field(rest)
    for v, c in zip(bm.verts, moved):
        v.co = c
    if relax > 0:
        even_out(bm, np.linalg.norm(moved - rest, axis=1) > 1e-9, relax)
    bm.to_mesh(me)
    bm.free()
    me.update()
    return split


def even_out(bm, region, passes=3, amount=0.5, sharp_deg=40.0):
    """Even out the faces of the moved ``region`` (bool per vert) by sliding points along the surface: each point
    goes part way to the middle of its neighbours, minus the part across the surface.  Points on open borders and
    sharp edges / corners stay, so the shape does not shrink or round off."""
    bm.verts.ensure_lookup_table()
    cos_sharp = math.cos(math.radians(sharp_deg))
    for _ in range(passes):
        bm.normal_update()
        moves = []
        for v in bm.verts:
            if not region[v.index] or v.is_boundary or not v.link_edges:
                continue
            fn = [f.normal for f in v.link_faces]
            if any(a.dot(b) < cos_sharp for i, a in enumerate(fn) for b in fn[i + 1:]):
                continue                                      # a sharp edge or corner runs through it
            mid = sum((e.other_vert(v).co for e in v.link_edges), Vector()) / len(v.link_edges)
            lap = mid - v.co
            n = v.normal
            moves.append((v, (lap - n * lap.dot(n)) * amount))
        for v, d in moves:
            v.co += d


def keep_density(me, before, after, radius, ratio=1.6):
    """Older quick fix (kept for scripts): split edges longer than ratio x before, at their midpoints."""
    bm = bmesh.new()
    bm.from_mesh(me)
    bm.edges.ensure_lookup_table()
    lens0 = np.array([np.linalg.norm(before[e.verts[0].index] - before[e.verts[1].index]) for e in bm.edges])
    usual = float(np.median(lens0)) if len(lens0) else 0.0
    long_e = [e for e, l0 in zip(bm.edges, lens0)
              if (e.verts[0].co - e.verts[1].co).length > max(l0 * ratio, usual * 1.5)]
    n = len(long_e)
    if long_e:
        bmesh.ops.subdivide_edges(bm, edges=long_e, cuts=1, use_grid_fill=True)
        bmesh.ops.triangulate(bm, faces=[f for f in bm.faces if len(f.verts) > 4])
        bm.to_mesh(me)
        me.update()
    bm.free()
    return n


def add_blob(context, location, radius, name='Clay'):
    """A smooth clay ball (quad sphere) at location; returns the object."""
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=2.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=7, use_grid_fill=True)
    for v in bm.verts:
        v.co = v.co.normalized() * radius
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(name, me)
    (context.collection or context.scene.collection).objects.link(ob)
    ob.location = location
    return ob


def fuse(context, objects, voxel):
    """Join the meshes into the first one and voxel remesh it into one smooth piece."""
    objects = [o for o in objects if o.type == 'MESH']
    if not objects:
        return None
    target = objects[0]
    if len(objects) > 1:
        with context.temp_override(active_object=target, selected_editable_objects=objects,
                                   selected_objects=objects, object=target):
            bpy.ops.object.join()
    me = target.data
    me.remesh_voxel_size = max(voxel, 1e-4)
    me.remesh_voxel_adaptivity = 0.0
    with context.temp_override(active_object=target, object=target):
        bpy.ops.object.voxel_remesh()
    for p in target.data.polygons:
        p.use_smooth = True
    return target


# -----------------------------------------------------------------------------
# live objects: record the moves, replay them after every slider rebuild
# -----------------------------------------------------------------------------

# modules whose rebuild() recomputes a live object's mesh from its sliders
LIVE_MODULES = (('armor_plate', 'rebuild_plate'), ('base_mesh', 'rebuild'), ('belt_maker', 'rebuild'),
                ('bridge_patch', 'rebuild'), ('cape_gen', 'rebuild'), ('clothing_gen', 'rebuild'),
                ('creature_hair', 'rebuild'), ('creature_plate', 'rebuild'), ('creature_scales', 'rebuild'),
                ('creature_spike', 'rebuild'), ('flower_plate', 'rebuild'), ('hood_gen', 'rebuild'),
                ('mech_ridge', 'rebuild'), ('scale_brush', 'rebuild'), ('scarf_gen', 'rebuild'),
                ('face_extract', 'rebuild'), ('edge_molding', 'rebuild'), ('loft_surface', 'rebuild'),
                ('robot_base', 'rebuild'))
_ORIGINALS = {}


def is_live(ob):
    """A mesh our sliders rebuild (it keeps its source on the object)."""
    if ob is None or ob.type != 'MESH':
        return False
    try:
        keys = ob.keys()
    except TypeError:
        return False
    return any(k.startswith('mch_') and (k.endswith('_src') or k.endswith('_source')) for k in keys)


def recorded_moves(ob):
    try:
        return json.loads(ob.get(MOVES_KEY, '[]'))
    except (TypeError, ValueError):
        return []


def record_move(ob, move):
    moves = recorded_moves(ob)
    moves.append(move)
    ob[MOVES_KEY] = json.dumps(moves)


def replay(ob):
    """Re-apply the recorded moves (with generation) to ob's freshly rebuilt mesh."""
    if ob is None or ob.type != 'MESH':
        return 0
    n = 0
    for mv in recorded_moves(ob):
        generate(ob.data, move_field(mv), relax=mv.get('relax', 0))
        n += 1
    return n


def _wrap(fn):
    def wrapped(*args, **kwargs):
        result = fn(*args, **kwargs)
        for a in args:
            if isinstance(a, bpy.types.Object):
                try:
                    if MOVES_KEY in a:
                        replay(a)
                except ReferenceError:
                    pass
                break
        return result
    wrapped.__wrapped__ = fn
    wrapped.__name__ = getattr(fn, '__name__', 'rebuild')
    return wrapped


def _hook_live_modules():
    import importlib
    for mod_name, fn_name in LIVE_MODULES:
        try:
            mod = importlib.import_module(f'{__package__}.{mod_name}')
        except ImportError:
            continue
        fn = getattr(mod, fn_name, None)
        if fn is None or hasattr(fn, '__wrapped__'):
            continue
        _ORIGINALS[(mod_name, fn_name)] = fn
        setattr(mod, fn_name, _wrap(fn))


def _unhook_live_modules():
    import importlib
    for (mod_name, fn_name), fn in list(_ORIGINALS.items()):
        try:
            setattr(importlib.import_module(f'{__package__}.{mod_name}'), fn_name, fn)
        except ImportError:
            pass
    _ORIGINALS.clear()


def rebuild_live(context, ob):
    """Run the live rebuild of ob (its module's rebuild) - used by Clear Moves."""
    import importlib
    for mod_name, fn_name in LIVE_MODULES:
        try:
            mod = importlib.import_module(f'{__package__}.{mod_name}')
        except ImportError:
            continue
        key = getattr(mod, 'SRC_KEY', None)
        if key and key in ob:
            fn = getattr(mod, fn_name)
            try:
                fn(context, ob)
            except TypeError:
                fn(ob)
            return True
    return False


# -----------------------------------------------------------------------------
# settings / operators / tool
# -----------------------------------------------------------------------------


class MCH_PG_Concept(bpy.types.PropertyGroup):
    radius_px: IntProperty(name='Size', default=120, min=5, max=3000, subtype='PIXEL',
                           description='Brush size on screen ([ and ] while dragging)')
    shape: EnumProperty(name='Shape', items=SHAPE_ITEMS, default='SPHERE')
    hardness: FloatProperty(name='Hardness', default=0.5, min=0.0, max=0.98,
                            description='How much of the brush moves whole (high = a rigid lump, low = soft)')
    falloff: EnumProperty(name='Falloff', items=FALLOFF_ITEMS, default='CLAY')
    mirror_x: BoolProperty(name='Mirror X', default=True, description='Move the other side (object X) too')
    keep_density: BoolProperty(name='Generate', default=True,
                               description='Really generate the pulled part when you let go (even faces, no '
                                           'stretching)')
    even_out: BoolProperty(name='Even Out', default=False,
                           description='After a pull, even out its faces along the surface (sharp edges stay)')
    follow_view: BoolProperty(name='Follow View', default=True,
                              description='The grab stays in front of you while the view turns (3D mouse = hand)')
    strength: FloatProperty(name='Strength', default=1.0, min=0.05, max=2.0,
                            description='How far the surface follows the mouse')
    lock_size: BoolProperty(name='Real Size', default=False,
                            description='Keep the brush the same size in the scene (not on screen) when you zoom')
    radius_world: FloatProperty(name='Size', default=0.1, min=1e-4, soft_max=5.0, unit='LENGTH', precision=4,
                                description='Brush radius in the scene (Real Size)')
    fuse_detail: FloatProperty(name='Fuse Detail', default=0.01, min=0.001, max=0.2, precision=3,
                               description='Fuse voxel size (part of the clay size): smaller = more detail')


_DRAW = [None]


def scale_size(st, factor):
    """[ ] / the F drag: the brush size, in pixels or (Real Size) in the scene."""
    if st.lock_size:
        st.radius_world = max(1e-4, st.radius_world * factor)
    else:
        st.radius_px = max(5, min(3000, int(round(st.radius_px * factor))))


def _px_per_world(context, at):
    region, rv3d = context.region, context.region_data
    c = view3d_utils.location_3d_to_region_2d(region, rv3d, at)
    if c is None:
        return 100.0
    a = view3d_utils.region_2d_to_location_3d(region, rv3d, c, at)
    b = view3d_utils.region_2d_to_location_3d(region, rv3d, (c[0] + 100.0, c[1]), at)
    return 100.0 / max((a - b).length, 1e-9)


def brush_px(context, at):
    """The brush radius on screen at ``at``."""
    st = context.scene.mch_concept
    return st.radius_world * _px_per_world(context, at) if st.lock_size else float(st.radius_px)


def brush_world(context, at):
    st = context.scene.mch_concept
    return st.radius_world if st.lock_size else st.radius_px / _px_per_world(context, at)


def _draw_brush(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    try:
        if op.center_2d is None:
            return
        cx, cy = op.center_2d
        st = context.scene.mch_concept
        r = getattr(op, 'r_px', None) or st.radius_px
        if st.shape == 'BOX':
            pts = [(cx - r, cy - r), (cx + r, cy - r), (cx + r, cy + r), (cx - r, cy + r)]
        else:
            pts = [(cx + r * math.cos(a), cy + r * math.sin(a)) for a in (2 * math.pi * i / 48 for i in range(48))]
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.line_width_set(2.0)
        sh.uniform_float('color', (1.0, 0.62, 0.15, 0.9))
        batch_for_shader(sh, 'LINE_LOOP', {'pos': pts}).draw(sh)
        core = r * (st.hardness if st.falloff == 'CLAY' else 0.0)
        if core > 3:
            if st.shape == 'BOX':
                cp = [(cx - core, cy - core), (cx + core, cy - core), (cx + core, cy + core), (cx - core, cy + core)]
            else:
                cp = [(cx + core * math.cos(a), cy + core * math.sin(a))
                      for a in (2 * math.pi * i / 48 for i in range(48))]
            sh.uniform_float('color', (1.0, 0.62, 0.15, 0.35))
            batch_for_shader(sh, 'LINE_LOOP', {'pos': cp}).draw(sh)
        gpu.state.line_width_set(1.0)
        gpu.state.blend_set('NONE')
    except Exception:
        pass


NAV_EVENTS = {'NDOF_MOTION', 'NDOF_BUTTON_PRESS', 'NDOF_BUTTON_RELEASE', 'MIDDLEMOUSE', 'TRACKPADPAN',
              'TRACKPADZOOM', 'NDOF_BUTTON_FIT', 'NDOF_BUTTON_TOP', 'NDOF_BUTTON_FRONT', 'NDOF_BUTTON_RIGHT'}


def mirror_reflections(ob):
    """The reflections (4x4, object space) of the object's own Mirror modifier (the Mecha Mirror) - [] if none."""
    from mathutils import Matrix
    mods = [m for m in ob.modifiers if m.type == 'MIRROR' and m.show_viewport] if ob is not None else []
    if not mods:
        return []
    m = mods[0]
    axes = [i for i in range(3) if m.use_axis[i]]
    a = (m.mirror_object.matrix_world.inverted_safe() @ ob.matrix_world) if m.mirror_object else Matrix.Identity(4)
    ai = a.inverted_safe()
    out = []
    for mask in range(1, 2 ** len(axes)):
        flip = Matrix.Identity(4)
        for j, ax in enumerate(axes):
            if mask >> j & 1:
                flip[ax][ax] = -1.0
        out.append(ai @ flip @ a)
    return out


def base_side(ob, local, reflections):
    """The reflection that takes a point grabbed on the mirrored copy back onto the real mesh (identity when it is
    already there): the candidate nearest to the mesh itself."""
    from mathutils import Matrix
    from mathutils.bvhtree import BVHTree
    ident = Matrix.Identity(4)
    if not reflections or not len(ob.data.polygons):
        return ident
    bvh = BVHTree.FromPolygons([v.co for v in ob.data.vertices], [tuple(p.vertices) for p in ob.data.polygons])

    def gap(m):
        hit = bvh.find_nearest(m @ local)
        return hit[3] if hit[0] is not None else 1e30
    return min([ident] + reflections, key=gap)


def _mesh_ok(ob):
    return ob is not None and ob.type == 'MESH' and not ob.library and not ob.data.library and ob.data.users == 1


class MCH_OT_concept_move(bpy.types.Operator):
    """Drag = light preview; let go = the real move (generated), adjustable afterwards (F9)."""
    bl_idname = 'mch.concept_move'
    bl_label = 'Concept Move'
    bl_description = 'Grab the surface and pull it (Shift: straight out, wheel: depth, [ ]: size)'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    # the move, in the object's own space (filled when you let go; F9 changes them)
    centre: FloatVectorProperty(name='Centre', size=3, options={'HIDDEN'})
    delta: FloatVectorProperty(name='Pull', size=3, options={'HIDDEN'})
    axes: FloatVectorProperty(name='Axes', size=9, default=(1, 0, 0, 0, 1, 0, 0, 0, 1), options={'HIDDEN'})
    radius: FloatProperty(name='Radius', min=1e-6, default=1.0, options={'HIDDEN'})
    size: FloatProperty(name='Size', default=1.0, min=0.05, max=10.0, description='Brush size (x the drag)')
    pull: FloatProperty(name='Pull', default=1.0, min=-3.0, max=5.0, description='How far (x the drag)')
    hardness: FloatProperty(name='Hardness', default=0.5, min=0.0, max=0.98)
    shape: EnumProperty(name='Shape', items=SHAPE_ITEMS, default='SPHERE')
    falloff: EnumProperty(name='Falloff', items=FALLOFF_ITEMS, default='CLAY')
    mirror: BoolProperty(name='Mirror X', default=True)
    generate_mesh: BoolProperty(name='Generate', default=True,
                                description='Really generate the pulled part (even faces, no stretching)')
    even_out: BoolProperty(name='Even Out', default=False,
                           description='Even out the faces of the pulled part along its surface (sharp edges stay)')
    twist: FloatProperty(name='Turn', default=0.0, subtype='ANGLE',
                         description='Turn of the grabbed part (Ctrl + mouse left / right while dragging)')
    twist_axis: FloatVectorProperty(size=3, default=(0, 0, 1), options={'HIDDEN'})

    def move_dict(self):
        mv = {'centre': list(self.centre), 'delta': [c * self.pull for c in self.delta],
              'radius': self.radius * self.size, 'falloff': self.falloff, 'mirror': self.mirror,
              'shape': self.shape, 'hardness': self.hardness, 'axes': list(self.axes)}
        if abs(self.twist) > 1e-9:
            mv['twist'] = list(self.twist_axis) + [self.twist]
        if self.even_out and self.generate_mesh:
            mv['relax'] = 3
        return mv

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        """The real move on the active object (also re-run by F9 after undo)."""
        ob = context.active_object
        if not _mesh_ok(ob):
            self.report({'WARNING'}, 'Concept Move: pick a mesh (single user)')
            return {'CANCELLED'}
        mv = self.move_dict()
        field = move_field(mv)
        if self.generate_mesh:
            n = generate(ob.data, field, relax=3 if self.even_out else 0)
        else:
            write_coords(ob.data, field(read_coords(ob.data)))
            n = 0
        if is_live(ob):
            record_move(ob, mv)                              # the sliders rebuild it: replay this move then
        return {'FINISHED'}

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(self, 'size', slider=True)
        col.prop(self, 'pull', slider=True)
        col.prop(self, 'twist')
        if self.falloff == 'CLAY':
            col.prop(self, 'hardness', slider=True)
        self.layout.prop(self, 'shape', expand=True)
        self.layout.prop(self, 'falloff')
        row = self.layout.row(align=True)
        row.prop(self, 'mirror', toggle=True)
        row.prop(self, 'generate_mesh', toggle=True)
        if self.generate_mesh:
            row.prop(self, 'even_out', toggle=True)

    # --- the drag (preview) --------------------------------------------------

    def _world_radius(self, context, px, at=None):
        region, rv3d = context.region, context.region_data
        at = at if at is not None else self.target
        c = view3d_utils.location_3d_to_region_2d(region, rv3d, at) or Vector(self.center_2d)
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, c, at)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (c[0] + px, c[1]), at)
        return (a - b).length

    def invoke(self, context, event):
        if context.mode != 'OBJECT' or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse)
        dg = context.evaluated_depsgraph_get()
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, origin, direction)
        if not hit or ob is None or ob.type != 'MESH' or ob.library or ob.data.library:
            return {'PASS_THROUGH'}
        if ob.data.users > 1:
            self.report({'WARNING'}, 'Concept Move: this mesh is shared by other objects (make it single user)')
            return {'CANCELLED'}
        self.ob = ob
        self.hit = loc.copy()
        self.target = loc.copy()
        self.normal = nrm.normalized()
        self.mouse0 = Vector(mouse)
        self.mouse = mouse
        self.center_2d = mouse
        self.depth = 0.0
        self.shift = False
        self.twist_angle = 0.0
        self.last_x = mouse[0]
        self.dist0 = (loc - origin).length                   # Follow View: distance along the mouse ray
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted_safe()
        self.orig = read_coords(ob.data)
        # 0.24.31 one mirror: an object with its own Mirror (Mecha Mirror) - grabbing the mirrored copy moves the
        # real half (and the modifier copies it back); Concept's Mirror X then stays out of the way
        refl = mirror_reflections(ob)
        self.obj_mirror = bool(refl)
        self.mref = base_side(ob, self.mwi @ loc, refl)
        self.cur = None
        for o in context.selected_objects:
            if o is not ob:
                o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw_brush, (self, context), 'WINDOW', 'POST_PIXEL')
        self.timer = context.window_manager.event_timer_add(1.0 / 60.0, window=context.window)
        context.window_manager.modal_handler_add(self)
        self._header(context)
        return {'RUNNING_MODAL'}

    def _header(self, context):
        st = context.scene.mch_concept
        context.area.header_text_set(
            f'Concept Move  |  {st.shape.title()} '
            + (f'{st.radius_world:.4g}' if st.lock_size else f'{st.radius_px}px')
            + f'  hardness {st.hardness:.2f}  |  {st.falloff.title()}'
            f'  |  Mirror X {"on" if st.mirror_x else "off"}  |  Follow View {"on" if st.follow_view else "off"}'
            f'  |  Turn {math.degrees(getattr(self, "twist_angle", 0.0)):.0f}°'
            '  |  Shift: out   Ctrl: turn   Wheel: depth   [ ]: size   3D mouse / MMB: view   RMB/Esc: cancel')

    def _target(self, context):
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, self.mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, self.mouse).normalized()
        if st.follow_view:
            return origin + ray * (self.dist0 + self.depth)
        p = view3d_utils.region_2d_to_location_3d(region, rv3d, self.mouse, self.target)
        return p + ray * self.depth

    def _current_move(self, context):
        """The move as it stands (object space) - preview and the final operator properties."""
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        delta = self._target(context) - self.hit
        if self.shift:                                       # straight out of / into the surface
            dy = (Vector(self.mouse) - self.mouse0).y
            delta = self.normal * (dy * self._world_radius(context, 1.0, self.hit))
        delta *= st.strength
        self.target = self.hit + delta
        self.center_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, self.target) or self.mouse
        radius = brush_world(context, self.hit)
        self.r_px = brush_px(context, self.target)
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
        vm = rv3d.view_matrix.to_3x3().transposed()        # box faces the view: screen right / up / depth
        axes = [c for i in range(3) for c in (m3 @ vm.col[i]).normalized()]
        r3 = self.mref.to_3x3()                              # mirrored copy -> the real half
        axes = [c for i in range(3) for c in (r3 @ Vector(axes[3 * i:3 * i + 3])).normalized()]
        mv = {'centre': list(self.mref @ (self.mwi @ self.hit)), 'delta': list(r3 @ (m3 @ delta)),
              'radius': radius * scale, 'falloff': st.falloff, 'mirror': st.mirror_x and not self.obj_mirror,
              'shape': st.shape, 'hardness': st.hardness, 'axes': axes}
        if abs(self.twist_angle) > 1e-9:                     # Ctrl: turn round the view axis
            view_axis = (m3 @ (rv3d.view_rotation @ Vector((0.0, 0.0, -1.0)))).normalized()
            sign = 1.0 if r3.determinant() > 0 else -1.0     # a turn seen in a mirror turns the other way
            mv['twist'] = list(r3 @ view_axis) + [self.twist_angle * sign]
        return mv

    def _preview(self, context, timer=False):
        rv3d = context.region_data
        key = (tuple(round(c, 6) for row in rv3d.view_matrix for c in row), tuple(self.mouse), self.depth,
               self.shift, self.twist_angle, context.scene.mch_concept.radius_px,
               context.scene.mch_concept.radius_world)
        if timer and key == getattr(self, '_last_key', None):
            return                                           # nothing moved: no work on a still frame
        self._last_key = key
        self.cur = self._current_move(context)
        mkey = (tuple(self.cur['centre']), self.cur['radius'], self.cur['mirror'], self.cur['falloff'],
                self.cur['shape'])
        if getattr(self, '_mask_key', None) != mkey:         # the grab point and size stay put during a drag
            self._mask = near_mask(self.orig, self.cur)
            self._mask_key = mkey
        write_coords(self.ob.data, fast_field(self.cur, self._mask)(self.orig))

    def _finish_ui(self, context):
        if _DRAW[0] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            _DRAW[0] = None
        if getattr(self, 'timer', None) is not None:
            context.window_manager.event_timer_remove(self.timer)
            self.timer = None
        if context.area:
            context.area.header_text_set(None)
            context.area.tag_redraw()

    def modal(self, context, event):
        st = context.scene.mch_concept
        if event.type in NAV_EVENTS:                         # the 3D mouse / MMB still moves the view
            return {'PASS_THROUGH'}
        if event.type == 'TIMER':                            # the view may have moved under a still mouse
            self._preview(context, timer=True)
        elif event.type == 'MOUSEMOVE':
            x = event.mouse_region_x
            if event.ctrl:                                   # Ctrl: left / right turns the grabbed part
                self.twist_angle += (x - self.last_x) * 0.01
                self._header(context)
            else:
                self.mouse = (event.mouse_region_x, event.mouse_region_y)
            self.last_x = x
            self.shift = event.shift
            self._preview(context)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = brush_world(context, self.hit) * 0.15
            self.depth += step if event.type == 'WHEELDOWNMOUSE' else -step
            self._preview(context)
        elif event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            scale_size(st, 1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)
            self._header(context)
            self._preview(context)
        elif event.type in {'LEFT_SHIFT', 'RIGHT_SHIFT'}:
            self.shift = event.value == 'PRESS'
            self._preview(context)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._finish_ui(context)
            mv = self.cur or self._current_move(context)
            write_coords(self.ob.data, self.orig)            # back to the start: execute() does the real move
            self.centre, self.delta, self.axes = mv['centre'], mv['delta'], mv['axes']
            self.radius, self.size, self.pull = mv['radius'], 1.0, 1.0
            self.hardness, self.shape, self.falloff, self.mirror = mv['hardness'], mv['shape'], mv['falloff'], \
                mv['mirror']
            tw = mv.get('twist')
            self.twist_axis, self.twist = (tw[:3], tw[3]) if tw else ((0.0, 0.0, 1.0), 0.0)
            self.generate_mesh = st.keep_density
            self.even_out = st.even_out
            return self.execute(context)
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            write_coords(self.ob.data, self.orig)
            self._finish_ui(context)
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


class MCH_OT_concept_hold(bpy.types.Operator):
    """Hold D and drag (any Mecha tool, MECHA LAB only): Concept Move right away, the tool stays as it was"""
    bl_idname = 'mch.concept_hold'
    bl_label = 'Concept Move (hold key)'
    bl_options = {'INTERNAL'}

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        try:
            return context.mode == 'OBJECT' and ts.is_mecha_workspace(context.workspace)
        except (AttributeError, ReferenceError):
            return False

    def invoke(self, context, event):
        res = bpy.ops.mch.concept_move('INVOKE_DEFAULT')
        return {'FINISHED'} if 'RUNNING_MODAL' in res or 'FINISHED' in res else {'PASS_THROUGH'}


class MCH_OT_concept_size(bpy.types.Operator):
    bl_idname = 'mch.concept_size'
    bl_label = 'Concept Move Size'
    bl_options = {'INTERNAL'}
    factor: FloatProperty(default=1.15)

    def execute(self, context):
        scale_size(context.scene.mch_concept, self.factor)
        return {'FINISHED'}


class MCH_OT_concept_resize(bpy.types.Operator):
    """F + move the mouse left / right: brush size (click or F again = keep, right click / Esc = back)"""
    bl_idname = 'mch.concept_resize'
    bl_label = 'Concept Move Brush Size'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        st = context.scene.mch_concept
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse).normalized()
        try:
            hit, loc, _n, _i, _o, _m = context.scene.ray_cast(context.evaluated_depsgraph_get(), origin, ray)
        except (RuntimeError, AttributeError):
            hit = False
        self.at = loc if hit else view3d_utils.region_2d_to_location_3d(region, rv3d, mouse,
                                                                         context.scene.cursor.location)
        self.x0 = event.mouse_region_x
        self.start = (st.radius_px, st.radius_world)
        self.center_2d = mouse
        self.r_px = brush_px(context, self.at)
        _DRAW[0] = bpy.types.SpaceView3D.draw_handler_add(_draw_brush, (self, context), 'WINDOW', 'POST_PIXEL')
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _end(self, context):
        if _DRAW[0] is not None:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
            _DRAW[0] = None
        context.area.header_text_set(None)
        context.area.tag_redraw()

    def modal(self, context, event):
        st = context.scene.mch_concept
        if event.type == 'MOUSEMOVE':
            st.radius_px, st.radius_world = self.start
            scale_size(st, math.exp((event.mouse_region_x - self.x0) * 0.006))
            self.r_px = brush_px(context, self.at)
            context.area.header_text_set(
                f'Brush size  {st.radius_world:.4g} (scene)' if st.lock_size else f'Brush size  {st.radius_px}px')
            context.area.tag_redraw()
        elif (event.type in {'LEFTMOUSE', 'RET', 'NUMPAD_ENTER'} and event.value == 'PRESS') or \
                (event.type == 'F' and event.value == 'PRESS'):
            self._end(context)
            return {'FINISHED'}
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            st.radius_px, st.radius_world = self.start
            self._end(context)
            return {'CANCELLED'}
        return {'RUNNING_MODAL'}


class MCH_OT_concept_add(bpy.types.Operator):
    bl_idname = 'mch.concept_add'
    bl_label = 'Add Clay'
    bl_description = 'Drop a clay ball (brush size) on the surface under the mouse, or in front of you'
    bl_options = {'REGISTER', 'UNDO'}

    def invoke(self, context, event):
        if context.mode != 'OBJECT' or context.area is None or context.area.type != 'VIEW_3D':
            return {'PASS_THROUGH'}
        region, rv3d = context.region, context.region_data
        mouse = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, mouse)
        ray = view3d_utils.region_2d_to_vector_3d(region, rv3d, mouse).normalized()
        dg = context.evaluated_depsgraph_get()
        hit, loc, _n, _i, _ob, _m = context.scene.ray_cast(dg, origin, ray)
        at = loc if hit else view3d_utils.region_2d_to_location_3d(region, rv3d, mouse,
                                                                    context.scene.cursor.location)
        ob = add_blob(context, at, max(brush_world(context, at) * 0.6, 1e-4))
        for o in context.selected_objects:
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        return {'FINISHED'}


class MCH_OT_concept_fuse(bpy.types.Operator):
    bl_idname = 'mch.concept_fuse'
    bl_label = 'Fuse Clay'
    bl_description = 'Join the selected meshes into one smooth piece (voxel remesh)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        objs = [context.active_object] if context.active_object in context.selected_objects else []
        objs += [o for o in context.selected_objects if o not in objs and o.type == 'MESH']
        size = max(max(o.dimensions) for o in objs)
        ob = fuse(context, objs, size * context.scene.mch_concept.fuse_detail)
        if ob is None:
            return {'CANCELLED'}
        self.report({'INFO'}, f'Fused into {ob.name} ({len(ob.data.polygons)} faces)')
        return {'FINISHED'}


class MCH_OT_concept_clear(bpy.types.Operator):
    bl_idname = 'mch.concept_clear'
    bl_label = 'Clear Moves'
    bl_description = 'Forget the Concept Moves of this live object (back to what its sliders make)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and MOVES_KEY in ob

    def execute(self, context):
        ob = context.active_object
        n = len(recorded_moves(ob))
        del ob[MOVES_KEY]
        rebuild_live(context, ob)
        self.report({'INFO'}, f'{n} move(s) cleared')
        return {'FINISHED'}


class MCH_TOOL_concept_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.concept_move'
    bl_label = 'Mecha Concept Move'
    bl_description = ('Concept: grab the surface and pull it (like a VR move tool).\n'
                      'Shift+click: add clay.  F + mouse: brush size.  Dragging: Shift = out, Ctrl = turn, wheel = depth, '
                      '[ ] = size, 3D mouse = view')
    bl_icon = 'ops.transform.translate'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_move', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.concept_add', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
        ('mch.concept_resize', {'type': 'F', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        draw(layout, context, compact=True)


def draw(layout, context, compact=False):
    st = context.scene.mch_concept
    layout.prop(st, 'shape', text='' if compact else 'Shape')
    row = layout.row(align=True)
    row.prop(st, 'radius_world' if st.lock_size else 'radius_px')
    row.prop(st, 'lock_size', toggle=True)
    if st.falloff == 'CLAY':
        layout.prop(st, 'hardness', slider=True)
    layout.prop(st, 'falloff', text='' if compact else 'Falloff')
    layout.prop(st, 'strength')
    ob = context.active_object
    if ob is not None and mirror_reflections(ob):
        layout.label(text='Mirror: the object\'s own Mirror', icon='MOD_MIRROR')
    else:
        layout.prop(st, 'mirror_x', toggle=True)
    row = layout.row(align=True)
    row.prop(st, 'keep_density', toggle=True)
    if st.keep_density:
        row.prop(st, 'even_out', toggle=True)
    layout.prop(st, 'follow_view', toggle=True)
    layout.operator('mch.concept_fuse', icon='META_BALL')
    ob = context.active_object
    if ob is not None and MOVES_KEY in ob:
        layout.operator('mch.concept_clear', text=f'Clear Moves ({len(recorded_moves(ob))})', icon='X')


CLASSES = (MCH_PG_Concept, MCH_OT_concept_move, MCH_OT_concept_hold, MCH_OT_concept_size, MCH_OT_concept_resize, MCH_OT_concept_add, MCH_OT_concept_fuse,
           MCH_OT_concept_clear)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_concept = bpy.props.PointerProperty(type=MCH_PG_Concept)
    _hook_live_modules()
    try:
        bpy.utils.register_tool(MCH_TOOL_concept_move, separator=True, group=False)
    except (ValueError, RuntimeError):
        pass


def unregister():
    try:
        bpy.utils.unregister_tool(MCH_TOOL_concept_move)
    except (ValueError, RuntimeError, KeyError):
        pass
    _unhook_live_modules()
    if _DRAW[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_DRAW[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _DRAW[0] = None
    try:
        del bpy.types.Scene.mch_concept
    except AttributeError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
