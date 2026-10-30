"""0.24.32 Concept Move: grab the surface and pull it - the stretch-and-look move of VR modelers, in Object Mode.

Press on a mesh and drag: the area under the brush follows the mouse like clay (a light preview while you drag).
When you let go the pulled part is really generated: what got stretched is split in its rest shape and pulled
again, so the new points sit on the curved surface and the faces stay as dense as the rest of the mesh (no long
stretched faces).  Then F9 / Adjust Last Operation: Size, Hardness, Pull, Shape, Falloff - recomputed from the
original.
* Shape: Sphere or Box (a view-aligned cube - frames, plates, flat panels).  Hardness: how much of the brush moves
  whole (1 = a rigid lump, 0 = a soft dome).  Falloffs: Clay (hardness), Elastic (Kelvinlet grab), Sharp.
* While dragging: Shift = straight out of the surface, Ctrl + mouse = turn the grabbed part as seen on screen
  (left / right, up / down), wheel = depth, [ ] = size, right click / Esc = cancel.
  A 3D mouse (and middle mouse) still navigates the view; with Follow View the grab stays in front of you, so
  moving the view carries the clay even with the mouse held still (re-evaluated 60 times a second).
* Live objects (cape, hood, plates ... still on their sliders) need no Apply: every move is recorded on the object
  and replayed (with the same generation) each time the sliders rebuild it.  Clear Moves forgets them.
* Hold D and drag (in any tool of the MECHA LAB workspace): the same move without switching tools.
* F + move the mouse: brush size (like sculpting).  Real Size keeps the brush the same size in the scene when
  you zoom.
* Path Move (its own tool): grab like Concept Move and drag a path - the grabbed box / ball keeps its shape and
  follows the way you go, sweeping a body behind it; it turns where the path bends (Follow Turns); F9 adjusts.
* Panel (like Cut): Through All / From Surface (also move the other meshes inside the brush), Auto Target /
  Selected Only / Active, Auto Apply (off = the moves stay editable: Undo Last, Clear, Apply).
* Shift+click: drop a clay blob.  Fuse: join the selected clay into one smooth piece (voxel remesh).
While dragging only the points the brush can reach are computed, and a still frame costs nothing.
``clay_weights``, ``elastic_weights``, ``sharp_weights``, ``box_distance``, ``displace`` and ``generate`` are the
working parts (numpy / bmesh, no UI).
"""
from __future__ import annotations

import json
import math
import time

import bmesh
import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, IntProperty, StringProperty
from bpy_extras import view3d_utils
from mathutils import Vector

MOVES_KEY = 'mch_concept_moves'
BASE_KEY = 'mch_concept_base'             # Auto Apply off: the mesh before the moves (kept to undo / clear them)
TARGET_ITEMS = [
    ('AUTO', 'Auto Target', 'The mesh under the mouse, whatever is selected'),
    ('SELECTED', 'Selected Only', 'Only selected meshes (grab and move several chosen parts at once)'),
    ('ACTIVE', 'Active', 'Only the active object'),
]
DEPTH_ITEMS = [
    ('THROUGH', 'Through All', 'Every target mesh inside the brush moves too (a plate on a body moves with it)'),
    ('SURFACE', 'From Surface', 'Only the mesh you grab'),
]
AREA_ITEMS = [
    ('BRUSH', 'Brush', '0.24.54 Extend pulls out only the surface under the brush (Box = square, Ball = round)'),
    ('SECTION', 'Whole', 'Extend pulls out the whole cross-section of the part (cut by a plane across the drag) - '
                         'Tab while dragging switches'),
]
PATH_METHODS = [
    ('EXTEND', 'Extend', 'Cut where you grab and run that section along the path; the end goes to the end of the '
                         'path - one clean mesh that looks pulled (light while dragging)'),
    ('SWEEP', 'Separate Tube', 'The section where you grab swept into a new object (the mesh stays); Merge joins it '
                               'later'),
    ('STRETCH', 'Stretch (slow)', 'The old way: the mesh itself is stretched step by step (slow on big meshes)'),
]
SPACE_ITEMS = [('LOCAL', 'Local', 'The move is in the active object\'s own space'),
               ('WORLD', 'World', 'The move is in the scene, applied to the listed objects')]
PATH_MAX_STEPS = 48
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


def screen_turn(view_rot, yaw, pitch):
    """Ctrl-drag turn seen on screen -> (axis, angle) in the world: left / right = round the screen's up axis,
    up / down = round its right axis (tips the front up / down).  ``view_rot``: the view's rotation (3x3)."""
    from mathutils import Quaternion
    up = view_rot @ Vector((0.0, 1.0, 0.0))
    right = view_rot @ Vector((1.0, 0.0, 0.0))
    q = Quaternion(right, -pitch) @ Quaternion(up, yaw)
    axis, angle = q.to_axis_angle()
    return Vector(axis).normalized(), angle


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
        # 0.24.31 grid fill done here: Blender's own (use_grid_fill) can crash on long Path Move chains
        out = bmesh.ops.subdivide_edges(bm, edges=edges, cuts=1, use_grid_fill=False)
        grid_fill(bm, {v for v in out['geom_split'] if isinstance(v, bmesh.types.BMVert)})
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


def grid_fill(bm, new_verts):
    """A quad cut on all four sides (an 8-sided face: corner, cut, corner, cut ...) -> four quads round a middle
    point, like a grid.  Other faces are left to the caller."""
    for f in [f for f in bm.faces if len(f.verts) == 8]:
        vs = list(f.verts)
        if vs[0] in new_verts:
            vs = vs[1:] + vs[:1]
        if not all((v in new_verts) == (i % 2 == 1) for i, v in enumerate(vs)):
            continue
        c = bm.verts.new(sum((v.co for v in vs), Vector()) / 8.0)
        smooth = f.smooth
        mat = f.material_index
        bm.faces.remove(f)
        for i in range(0, 8, 2):
            try:
                nf = bm.faces.new((vs[i], vs[(i + 1) % 8], c, vs[i - 1]))
                nf.smooth, nf.material_index = smooth, mat
            except ValueError:
                pass
    bm.normal_update()


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
    from . import edge_memory as em
    kept = em.remember(me)                      # 0.24.95
    with context.temp_override(active_object=target, object=target):
        bpy.ops.object.voxel_remesh()
    em.restore(target.data, kept)
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
        replay_one(ob.data, mv)
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
    knife_cuts: IntProperty(name='Knife Cuts', default=12, min=2, max=64,
                            description='Knife Mesh: cuts across the longest side (the other sides get the same spacing)')
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
    path_taper: FloatProperty(name='Taper', default=0.0, min=0.0, max=0.95,
                              description='Path Move: thinner toward the end (0 = the same all the way)')
    path_method: EnumProperty(name='Method', items=PATH_METHODS, default='EXTEND')
    path_area: EnumProperty(name='Area', items=AREA_ITEMS, default='BRUSH')
    path_hardness: FloatProperty(name='Hardness', default=1.0, min=0.0, max=1.0,
                                 description='Path Move: 1 = a hard start (the grabbed part runs straight out); lower = '
                                             'the mesh round the grab is pulled along too, fading out softly (like '
                                             'Concept Move)')
    path_turn: BoolProperty(name='Follow Turns', default=True,
                            description='Path Move: the grabbed box / ball turns where the path bends')
    path_back_mask: BoolProperty(name='Back Mask', default=False,
                                 description='Path Move: the far side (faces turned away from you) stays put - a thin '
                                             'part is pulled only on the side you grabbed.  Extend Brush then never '
                                             'falls back to the whole section; Whole still takes the whole section')
    lock_size: BoolProperty(name='Real Size', default=False,
                            description='Keep the brush the same size in the scene (not on screen) when you zoom')
    radius_world: FloatProperty(name='Size', default=0.1, min=1e-4, soft_max=5.0, unit='LENGTH', precision=4,
                                description='Brush radius in the scene (Real Size)')
    targets: EnumProperty(name='Targets', items=TARGET_ITEMS, default='AUTO')
    depth_mode: EnumProperty(name='Depth', items=DEPTH_ITEMS, default='SURFACE')
    auto_apply: BoolProperty(name='Auto Apply', default=True,
                             description='On: the move is part of the mesh at once.  Off: the moves stay editable '
                                         '(Undo Last / Clear / Apply below)')
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


def target_pool(context, targets):
    """The meshes a grab may move: every visible one (Auto Target), the selected ones, or the active one."""
    def ok(o):
        try:
            return _mesh_ok(o) and o.visible_get()
        except (RuntimeError, ReferenceError):
            return False
    if targets == 'ACTIVE':
        ob = context.active_object
        return [ob] if ok(ob) else []
    if targets == 'SELECTED':
        return [o for o in context.selected_objects if ok(o)]
    return [o for o in context.view_layer.objects if ok(o)]


def pick_grab(context, origin, direction, targets='AUTO'):
    """(location, normal, object) of the grab under the mouse - for Selected Only / Active only those meshes
    count (others in front are looked through).  None when nothing is hit."""
    dg = context.evaluated_depsgraph_get()
    if targets == 'AUTO':
        hit, loc, nrm, _i, ob, _m = context.scene.ray_cast(dg, origin, direction)
        if not hit or ob is None or ob.type != 'MESH' or ob.library or ob.data.library:
            return None
        return loc, nrm, ob
    best = None
    for ob in target_pool(context, targets):
        mwi = ob.matrix_world.inverted_safe()
        try:
            ok, loc, nrm, _i = ob.ray_cast(mwi @ origin, (mwi.to_3x3() @ direction).normalized(), depsgraph=dg)
        except (RuntimeError, TypeError):
            continue
        if not ok:
            continue
        w = ob.matrix_world @ loc
        dist = (w - origin).length
        if best is None or dist < best[0]:
            best = (dist, w, (mwi.to_3x3().transposed() @ nrm).normalized(), ob)
    return best[1:] if best else None


def bbox_gap(ob, p):
    """Distance from p to the object's box in the scene (0 inside)."""
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    gap = Vector([max(min(q[i] for q in pts) - p[i], 0.0, p[i] - max(q[i] for q in pts)) for i in range(3)])
    return gap.length


def grab_objects(context, hit_ob, hit, reach_w, targets='AUTO', depth='SURFACE'):
    """What one grab moves: the grabbed mesh (From Surface), or every target mesh the brush reaches (Through All)."""
    if depth != 'THROUGH':
        return [hit_ob]
    objs = [o for o in target_pool(context, targets) if o is hit_ob or bbox_gap(o, hit) <= reach_w]
    if hit_ob not in objs:
        objs.insert(0, hit_ob)
    return objs


def to_local(mv, ob, mref=None, mirror=False):
    """A move in the scene -> the same move in ob's own space (through its own Mirror: ``mref``)."""
    from mathutils import Matrix
    mwi = ob.matrix_world.inverted_safe()
    m3 = mwi.to_3x3()
    mref = mref if mref is not None else Matrix.Identity(4)
    r3 = mref.to_3x3()
    scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
    out = dict(mv)
    out['centre'] = list(mref @ (mwi @ Vector(mv['centre'])))
    out['delta'] = list(r3 @ (m3 @ Vector(mv.get('delta', (0.0, 0.0, 0.0)))))
    out['radius'] = mv['radius'] * scale
    ax = list(mv.get('axes') or (1, 0, 0, 0, 1, 0, 0, 0, 1))
    out['axes'] = [c for i in range(3) for c in (r3 @ (m3 @ Vector(ax[3 * i:3 * i + 3]))).normalized()]
    out['mirror'] = mirror
    if mv.get('twist'):
        tw = mv['twist']
        sign = 1.0 if r3.determinant() > 0 else -1.0         # a turn seen in a mirror turns the other way
        out['twist'] = list((r3 @ (m3 @ Vector(tw[:3]))).normalized()) + [tw[3] * sign]
    return out


def local_frame(ob, centre_world):
    """(mirror map, has own Mirror) for a grab at centre_world on ob."""
    refl = mirror_reflections(ob)
    return base_side(ob, ob.matrix_world.inverted_safe() @ Vector(centre_world), refl), bool(refl)


def has_base(ob):
    return ob is not None and BASE_KEY in ob and bpy.data.meshes.get(ob[BASE_KEY]) is not None


def keep_base(ob):
    """Auto Apply off: keep the mesh as it was before the first move (once), so the moves stay editable."""
    if has_base(ob) or is_live(ob):
        return
    me = ob.data.copy()
    me.name = ob.data.name + '.concept_base'
    me.use_fake_user = True
    ob[BASE_KEY] = me.name


def rebuild_from_base(ob, moves):
    """Back to the kept mesh, then the given moves again."""
    base = bpy.data.meshes.get(ob[BASE_KEY])
    bm = bmesh.new()
    bm.from_mesh(base)
    bm.to_mesh(ob.data)
    bm.free()
    ob.data.update()
    for mv in moves:
        replay_one(ob.data, mv)
    ob[MOVES_KEY] = json.dumps(moves)


def replay_one(me, mv):
    """One remembered move again: a grab (generated) or a Path Move Extend."""
    if mv.get('kind') == 'extend':
        from . import path_sweep
        try:
            path_sweep.extend(me, mv['hit'], mv['normal'], mv['offsets'], mv.get('turn', True), mv.get('taper', 0.0),
                              mv.get('hardness', 1.0), mv.get('radius'), mv.get('sides', 8),
                              mv.get('front_only', False))
        except ValueError:
            pass
        return
    if mv.get('kind') == 'path':                # 0.24.53 a Path Move Stretch: all its steps in one go
        steps = mv.get('moves', [])
        field = lambda co: run_path(co, steps)                       # noqa: E731
        if mv.get('back'):                      # 0.24.58 Back Mask
            field = back_field(me, field, mv['back'])
        generate(me, field, relax=mv.get('relax', 0))
        return
    generate(me, move_field(mv), relax=mv.get('relax', 0))


def drop_base(ob):
    name = ob.get(BASE_KEY)
    me = bpy.data.meshes.get(name) if name else None
    if me is not None and me.users <= 1:
        bpy.data.meshes.remove(me)
    if BASE_KEY in ob:
        del ob[BASE_KEY]


def apply_moves(ob, moves, generate_mesh=True, auto_apply=True):
    """Do the moves on ob; live objects and editable ones (Auto Apply off) also remember them."""
    if not auto_apply:
        keep_base(ob)
    for mv in moves:
        if generate_mesh:
            generate(ob.data, move_field(mv), relax=mv.get('relax', 0))
        else:
            write_coords(ob.data, move_field(mv)(read_coords(ob.data)))
    if is_live(ob) or has_base(ob):
        for mv in moves:
            record_move(ob, mv)


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
                         description='Turn of the grabbed part (Ctrl + mouse while dragging: left / right, up / down on screen)')
    twist_axis: FloatVectorProperty(size=3, default=(0, 0, 1), options={'HIDDEN'})
    space: EnumProperty(items=SPACE_ITEMS, default='LOCAL', options={'HIDDEN'})
    objects: StringProperty(options={'HIDDEN'})              # World: the moved objects (JSON names)
    auto_apply: BoolProperty(name='Auto Apply', default=True,
                             description='Off: the move stays editable (Undo Last / Clear / Apply in the panel)')

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
        """The real move (also re-run by F9 after undo): on the active object (Local), or on every listed object
        (World: Through All / Selected Only)."""
        from . import safety_save              # 0.24.58 a recovery copy first (when one is due)
        safety_save.checkpoint(self.bl_label)
        mv = self.move_dict()
        if self.space == 'WORLD':
            objs = [bpy.data.objects.get(n) for n in json.loads(self.objects or '[]')]
            objs = [o for o in objs if _mesh_ok(o)]
            if not objs:
                self.report({'WARNING'}, 'Concept Move: nothing to move')
                return {'CANCELLED'}
            for ob in objs:
                mref, own = local_frame(ob, mv['centre'])
                apply_moves(ob, [to_local(mv, ob, mref, self.mirror and not own)], self.generate_mesh,
                            self.auto_apply)
            return {'FINISHED'}
        ob = context.active_object
        if not _mesh_ok(ob):
            self.report({'WARNING'}, 'Concept Move: pick a mesh (single user)')
            return {'CANCELLED'}
        apply_moves(ob, [mv], self.generate_mesh, self.auto_apply)
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
        st = context.scene.mch_concept
        grab = pick_grab(context, origin, direction, st.targets)
        if grab is None:
            return {'PASS_THROUGH'}
        loc, nrm, ob = grab
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
        self.twist_angle = 0.0                               # kept for the header / old callers
        self.yaw = self.pitch = 0.0
        self.last_x, self.last_y = mouse
        self.dist0 = (loc - origin).length                   # Follow View: distance along the mouse ray
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted_safe()
        self.orig = read_coords(ob.data)
        # 0.24.31 one mirror: an object with its own Mirror (Mecha Mirror) - grabbing the mirrored copy moves the
        # real half (and the modifier copies it back); Concept's Mirror X then stays out of the way
        self.mref, self.obj_mirror = local_frame(ob, loc)
        self.cur = None
        # 0.24.32 Targets / Through All: one grab can move several meshes (each in its own space)
        r = brush_world(context, loc)
        objs = grab_objects(context, ob, loc, r * (4.0 if st.falloff == 'ELASTIC' else 1.8), st.targets,
                            st.depth_mode)
        self.parts = []
        for o in objs:
            if not _mesh_ok(o):
                continue
            mref, own = (self.mref, self.obj_mirror) if o is ob else local_frame(o, loc)
            self.parts.append({'ob': o, 'orig': self.orig if o is ob else read_coords(o.data), 'mref': mref,
                               'own': own, 'mask': None, 'mkey': None})
        if st.targets == 'AUTO' and st.depth_mode == 'SURFACE':
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
            f'  |  Turn {math.degrees(getattr(self, "yaw", 0.0)):.0f}° / {math.degrees(getattr(self, "pitch", 0.0)):.0f}°'
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
        self.r_px = brush_px(context, self.target)
        vm = rv3d.view_matrix.to_3x3().transposed()        # box faces the view: screen right / up / depth
        mv = {'centre': list(self.hit), 'delta': list(delta), 'radius': brush_world(context, self.hit),
              'falloff': st.falloff, 'mirror': st.mirror_x, 'shape': st.shape, 'hardness': st.hardness,
              'axes': [c for i in range(3) for c in vm.col[i].normalized()]}
        if abs(self.yaw) > 1e-9 or abs(self.pitch) > 1e-9:   # Ctrl: turn as seen on screen
            axis, angle = screen_turn(rv3d.view_rotation.to_matrix(), self.yaw, self.pitch)
            if angle > 1e-9:
                mv['twist'] = list(axis) + [angle]
        return mv                                            # in the scene; to_local() per moved mesh

    def _preview(self, context, timer=False):
        rv3d = context.region_data
        key = (tuple(round(c, 6) for row in rv3d.view_matrix for c in row), tuple(self.mouse), self.depth,
               self.shift, self.yaw, self.pitch, context.scene.mch_concept.radius_px,
               context.scene.mch_concept.radius_world)
        if timer and key == getattr(self, '_last_key', None):
            return                                           # nothing moved: no work on a still frame
        self._last_key = key
        self.cur = self._current_move(context)
        for part in self.parts:
            lm = to_local(self.cur, part['ob'], part['mref'], self.cur['mirror'] and not part['own'])
            mkey = (tuple(lm['centre']), lm['radius'], lm['mirror'], lm['falloff'], lm['shape'])
            if part['mkey'] != mkey:                         # the grab point and size stay put during a drag
                part['mask'] = near_mask(part['orig'], lm)
                part['mkey'] = mkey
            write_coords(part['ob'].data, fast_field(lm, part['mask'])(part['orig']))

    def _restore(self):
        for part in getattr(self, 'parts', ()):
            write_coords(part['ob'].data, part['orig'])

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
            x, y = event.mouse_region_x, event.mouse_region_y
            if event.ctrl:                                   # Ctrl: turn it as seen on screen
                self.yaw += (x - self.last_x) * 0.01         # left / right
                self.pitch += (y - self.last_y) * 0.01       # up / down
                self._header(context)
            else:
                self.mouse = (x, y)
            self.last_x, self.last_y = x, y
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
            self._restore()                                  # back to the start: execute() does the real move
            self.space = 'WORLD'
            self.objects = json.dumps([p['ob'].name for p in self.parts])
            self.auto_apply = st.auto_apply
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
            self._restore()
            self._finish_ui(context)
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


def path_moves(path, radius, hardness=0.9, taper=0.0, mirror=False, shape='SPHERE', axes=None, turn=True):
    """Path Move: the drag path (object space) -> short grabs, each from one path point to the next.  The part
    grabbed at a point is carried to the next one, so the grabbed box / ball keeps its shape and follows the path,
    sweeping a body behind it.  ``turn``: where the path bends the grabbed part turns with it (the cross-section
    stays square to the way it goes, like bending a pipe).  ``taper`` > 0 thins it toward the end."""
    pts = [Vector(p) for p in path]
    n = len(pts) - 1
    ax = np.asarray(list(axes) if axes is not None else [1, 0, 0, 0, 1, 0, 0, 0, 1], dtype=np.float64).reshape(3, 3)
    total = np.eye(3)
    moves = []
    for k in range(n):
        t = k / max(n - 1, 1)
        a, b = pts[k], pts[k + 1]
        mv = {'centre': list(a), 'delta': list(b - a), 'radius': radius * max(1.0 - taper * t, 0.05),
              'falloff': 'CLAY', 'mirror': mirror, 'shape': shape, 'hardness': hardness}
        if turn and k > 0:
            u, v = (a - pts[k - 1]), (b - a)
            if u.length > 1e-12 and v.length > 1e-12:
                u.normalize()
                v.normalize()
                c = u.cross(v)
                angle = math.atan2(c.length, u.dot(v))
                if c.length > 1e-9 and angle > 1e-6:
                    mv['twist'] = list(c.normalized()) + [angle]
                    total = rotation_matrix(c.normalized(), angle) @ total
        mv['axes'] = list((ax @ total.T).ravel())            # the box turns with the part it grabbed
        moves.append(mv)
    return moves


def smooth_path(pts, passes=2):
    """Take the shake out of a hand-drawn path (the ends stay)."""
    pts = [Vector(p) for p in pts]
    for _ in range(passes):
        if len(pts) < 3:
            break
        pts = [pts[0]] + [(pts[i - 1] + pts[i] * 2.0 + pts[i + 1]) / 4.0 for i in range(1, len(pts) - 1)] + [pts[-1]]
    return pts


def even_path(pts, step, max_steps=PATH_MAX_STEPS):
    """Evenly spaced path points (about ``step`` apart, at most ``max_steps`` steps)."""
    pts = [Vector(p) for p in pts]
    if len(pts) < 2:
        return pts
    lens = [0.0]
    for a, b in zip(pts, pts[1:]):
        lens.append(lens[-1] + (b - a).length)
    total = lens[-1]
    if total < 1e-9:
        return pts[:1]
    n = max(1, min(max_steps, int(math.ceil(total / max(step, 1e-9)))))
    out, j = [], 0
    for i in range(n + 1):
        s = total * i / n
        while j < len(pts) - 2 and lens[j + 1] < s:
            j += 1
        seg = lens[j + 1] - lens[j]
        out.append(pts[j].lerp(pts[j + 1], 0.0 if seg < 1e-12 else (s - lens[j]) / seg))
    return out


def section_radius(info):
    c = Vector(info['centre'])
    return max((Vector(q) - c).length for q in info['loop'])


def turn_radius(a, b, c):
    """Radius of the circle through three points (inf when they are in a line)."""
    ab, bc, ca = (b - a).length, (c - b).length, (a - c).length
    area2 = (b - a).cross(c - a).length
    return float('inf') if area2 < 1e-12 else ab * bc * ca / (2.0 * area2)


def relax_path(pts, radius, max_passes=60):
    """0.24.42 a swept section of ``radius`` folds over itself where the path turns tighter than that: those
    places are smoothed out until every turn is at least ``radius`` wide (the ends stay)."""
    pts = [Vector(p) for p in pts]
    if len(pts) < 3 or radius <= 0:
        return pts
    for _ in range(max_passes):
        tight = [i for i in range(1, len(pts) - 1) if turn_radius(pts[i - 1], pts[i], pts[i + 1]) < radius]
        if not tight:
            break
        near = {j for i in tight for j in (i - 1, i, i + 1) if 0 < j < len(pts) - 1}
        pts = [p if i not in near else (pts[i - 1] + p * 2.0 + pts[i + 1]) / 4.0 for i, p in enumerate(pts)]
    return pts


def run_path(co, moves):
    """The moves one after another on coordinates (no new faces) - the drag preview."""
    co = np.array(co, dtype=np.float64)
    for mv in moves:
        mask = near_mask(co, mv)
        if mask.any():
            co[mask] = move_field(mv)(co[mask])
    return co


def vertex_normals(me):
    n = np.empty(len(me.vertices) * 3, dtype=np.float32)
    me.vertices.foreach_get('normal', n)
    return n.reshape(-1, 3).astype(np.float64)


def facing_weights(normals, toward):
    """0.24.58 Back Mask: 1 for points facing ``toward`` (the viewer), 0 for the far side, a short ramp between."""
    t = np.asarray(toward, dtype=np.float64)
    t = t / max(float(np.linalg.norm(t)), 1e-12)
    return np.clip((np.asarray(normals, dtype=np.float64) @ t + 0.1) / 0.3, 0.0, 1.0)


def toward_local(ob, toward, mref=None):
    """The way to the viewer (scene) -> in ob's own space, for comparing with its normals (through its Mirror)."""
    v = ob.matrix_world.to_3x3().transposed() @ Vector(toward)
    if mref is not None:
        v = mref.to_3x3() @ v
    return list(v.normalized())


def masked(field, rest0, w0):
    """Back Mask: ``field`` held back by the weights ``w0`` of the points ``rest0`` (the mesh before the move).
    Points added later (generate splits edges and appends them) take the weight of the nearest original point."""
    n0 = len(rest0)
    kd = []

    def f(co):
        co = np.asarray(co, dtype=np.float64)
        moved = field(co)
        w = np.empty(len(co))
        k = min(n0, len(co))
        w[:k] = w0[:k]
        if len(co) > n0:
            if not kd:
                from mathutils.kdtree import KDTree
                tree = KDTree(n0)
                for i, c in enumerate(rest0):
                    tree.insert(c, i)
                tree.balance()
                kd.append(tree)
            w[n0:] = [w0[kd[0].find(c)[1]] for c in co[n0:]]
        return co + w[:, None] * (moved - co)
    return f


def back_field(me, field, toward):
    """``field`` with the Back Mask for the mesh as it is now (``toward``: the viewer, in the mesh's space)."""
    rest = read_coords(me)
    return masked(field, rest, facing_weights(vertex_normals(me), toward))


class MCH_OT_concept_path(bpy.types.Operator):
    """Path Move: grab like Concept Move and drag a path - the box / ball keeps its shape and follows the way"""
    bl_idname = 'mch.concept_path'
    bl_label = 'Path Move'
    bl_description = 'Grab the surface and drag a path: the grabbed box / ball keeps its shape and follows it (F9 adjusts)'
    bl_options = {'REGISTER', 'UNDO', 'BLOCKING'}

    path: StringProperty(options={'HIDDEN'})                 # object space points (JSON)
    axes: FloatVectorProperty(size=9, default=(1, 0, 0, 0, 1, 0, 0, 0, 1), options={'HIDDEN'})
    radius: FloatProperty(name='Radius', min=1e-6, default=1.0, options={'HIDDEN'})
    size: FloatProperty(name='Size', default=1.0, min=0.05, max=10.0, description='Thickness (x the brush)')
    hardness: FloatProperty(name='Hardness', default=0.9, min=0.0, max=0.98)
    taper: FloatProperty(name='Taper', default=0.0, min=0.0, max=0.95, description='Thinner toward the end (0 = the same all the way)')
    edge_hardness: FloatProperty(name='Hardness', default=1.0, min=0.0, max=1.0,
                                 description='Extend: 1 = the section runs straight out of the cut; lower = the mesh '
                                             'round it is pulled out too, fading out (soft, like Concept Move)')
    turn: BoolProperty(name='Follow Turns', default=True,
                       description='The grabbed box / ball turns where the path bends (stays square to the path)')
    shape: EnumProperty(name='Shape', items=SHAPE_ITEMS, default='SPHERE')
    mirror: BoolProperty(name='Mirror X', default=True)
    generate_mesh: BoolProperty(name='Generate', default=True,
                                description='Really generate the body along the path (even faces, no stretching)')
    even_out: BoolProperty(name='Even Out', default=False,
                           description='Even out the faces along the body (sharp edges stay)')
    space: EnumProperty(items=SPACE_ITEMS, default='LOCAL', options={'HIDDEN'})
    objects: StringProperty(options={'HIDDEN'})
    auto_apply: BoolProperty(name='Auto Apply', default=True,
                             description='Off: the moves stay editable (Undo Last / Clear / Apply in the panel)')
    method: EnumProperty(name='Method', items=PATH_METHODS, default='STRETCH')
    area: EnumProperty(name='Area', items=AREA_ITEMS, default='SECTION')
    back_mask: BoolProperty(name='Back Mask', default=False,
                            description='The far side (faces turned away from you) stays put')
    toward: FloatVectorProperty(size=3, default=(0, 0, 1), options={'HIDDEN'})   # the way to the viewer (scene)
    grab_point: FloatVectorProperty(size=3, options={'HIDDEN'})   # Extend / Separate Tube: in the object's space
    grab_normal: FloatVectorProperty(size=3, default=(1, 0, 0), options={'HIDDEN'})
    offsets: StringProperty(options={'HIDDEN'})
    silhouette: BoolProperty(default=False, options={'HIDDEN', 'SKIP_SAVE'})   # 0.24.76 Silhouette Move: Whole always

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def moves(self, pts=None, radius=None, axes=None, mirror=None):
        pts = pts if pts is not None else [Vector(p) for p in json.loads(self.path or '[]')]
        return path_moves(pts, radius if radius is not None else self.radius * self.size, self.hardness, self.taper,
                          self.mirror if mirror is None else mirror, self.shape,
                          axes if axes is not None else self.axes, self.turn)

    def execute(self, context):
        from . import safety_save              # 0.24.58 a recovery copy first (when one is due)
        safety_save.checkpoint(self.bl_label)
        if self.method != 'STRETCH':
            return self._execute_section(context)
        if self.space == 'WORLD':                            # every listed object, each in its own space
            pts = [Vector(p) for p in json.loads(self.path or '[]')]
            objs = [o for o in (bpy.data.objects.get(n) for n in json.loads(self.objects or '[]')) if _mesh_ok(o)]
            if len(pts) < 2 or not objs:
                self.report({'WARNING'}, 'Path Move: drag a path over a mesh')
                return {'CANCELLED'}
            n = 0
            for ob in objs:
                mref, own = local_frame(ob, pts[0])
                lpts, lrad, laxes = local_path(ob, pts, self.radius * self.size, self.axes, mref)
                n = self._run(ob, self.moves(lpts, lrad, laxes, self.mirror and not own), lpts, lrad,
                              toward_local(ob, self.toward, mref) if self.back_mask else None)
            self.report({'INFO'}, f'Path Move: {n} steps')
            return {'FINISHED'}
        ob = context.active_object
        if not _mesh_ok(ob):
            self.report({'WARNING'}, 'Path Move: pick a mesh (single user)')
            return {'CANCELLED'}
        moves = self.moves()
        if not moves:
            self.report({'WARNING'}, 'Path Move: drag a path')
            return {'CANCELLED'}
        n = self._run(ob, moves, [Vector(p) for p in json.loads(self.path)], self.radius * self.size,
                      toward_local(ob, self.toward) if self.back_mask else None)
        self.report({'INFO'}, f'Path Move: {n} steps')
        return {'FINISHED'}

    def _execute_section(self, context):
        """Extend / Separate Tube on the grabbed object (its own space): the section sweeps along the path."""
        from . import path_sweep
        names = json.loads(self.objects or '[]')
        ob = bpy.data.objects.get(names[0]) if names else context.active_object
        offsets = [Vector(o) for o in json.loads(self.offsets or '[]')]
        if not _mesh_ok(ob) or len(offsets) < 2:
            self.report({'WARNING'}, 'Path Move: drag a path over a mesh')
            return {'CANCELLED'}
        hit, normal = Vector(self.grab_point), Vector(self.grab_normal)
        method = self.method
        if method == 'EXTEND' and is_live(ob):
            method = 'SWEEP'                                 # a live object is rebuilt by its sliders
        if method == 'EXTEND':
            try:
                if not self.auto_apply:
                    keep_base(ob)
                rad = self.radius * self.size if self.area == 'BRUSH' else None
                sides = 4 if self.shape == 'BOX' else 8
                front = self.back_mask and rad is not None
                msg = path_sweep.extend(ob.data, hit, normal, offsets, self.turn, self.taper, self.edge_hardness,
                                        rad, sides, front)
                if has_base(ob):
                    record_move(ob, {'kind': 'extend', 'hit': list(hit), 'normal': list(normal),
                                     'offsets': [list(o) for o in offsets], 'turn': self.turn, 'taper': self.taper,
                                     'hardness': self.edge_hardness, 'radius': rad, 'sides': sides,
                                     'front_only': front})
                self.report({'INFO'}, f'Path Move {msg}')
                return {'FINISHED'}
            except ValueError as exc:
                if self.back_mask and self.area == 'BRUSH':  # a Separate Tube would take the whole section
                    self.report({'WARNING'}, f'Path Move: {exc} - try a smaller brush or turn Back Mask off')
                    return {'CANCELLED'}
                self.report({'WARNING'}, f'Path Move: {exc} - made a Separate Tube instead')
        try:
            new = path_sweep.sweep_object(context, ob, hit, normal, offsets, self.turn, self.taper,
                                          hardness=self.edge_hardness)
        except ValueError as exc:
            self.report({'WARNING'}, f'Path Move: {exc}')
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        new.select_set(True)
        context.view_layer.objects.active = new
        self.report({'INFO'}, 'Path Move: Separate Tube (Merge in the panel joins it)')
        return {'FINISHED'}

    def _run(self, ob, moves, pts, radius, back=None):
        """``back``: Back Mask on - the way to the viewer in ob's space (faces turned away stay put)."""
        if not moves:
            return 0
        if not self.auto_apply:
            keep_base(ob)
        field = lambda co: run_path(co, moves)                       # noqa: E731
        if back is not None:
            field = back_field(ob.data, field, back)
        if self.generate_mesh:
            # 0.24.53 all the steps as one field, one generate: step by step every call split the part again
            # (about 1.5x the points per step - 59 s and 400k points on a 10k plate, open edges)
            generate(ob.data, field)
        else:
            write_coords(ob.data, field(read_coords(ob.data)))
        if self.generate_mesh and self.even_out:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            bm.verts.ensure_lookup_table()
            r = radius * 1.2
            region = [min((v.co - _closest_seg(a, b, v.co)).length for a, b in zip(pts, pts[1:])) < r
                      for v in bm.verts]
            even_out(bm, region, 3)
            bm.to_mesh(ob.data)
            bm.free()
            ob.data.update()
        if is_live(ob) or has_base(ob):
            record_move(ob, {'kind': 'path', 'moves': moves, **({'back': list(back)} if back is not None else {})})
        return len(moves)

    def draw(self, context):
        col = self.layout.column(align=True)
        col.prop(self, 'size', slider=True)
        col.prop(self, 'hardness', slider=True)
        col.prop(self, 'taper', slider=True)
        row = self.layout.row(align=True)
        row.prop(self, 'turn', toggle=True)
        row.prop(self, 'back_mask', toggle=True)
        if self.method != 'STRETCH':
            self.layout.prop(self, 'method', expand=True)
            return
        self.layout.prop(self, 'shape', expand=True)
        row = self.layout.row(align=True)
        row.prop(self, 'mirror', toggle=True)
        row.prop(self, 'generate_mesh', toggle=True)
        if self.generate_mesh:
            row.prop(self, 'even_out', toggle=True)

    # --- the drag: the grab of Concept Move, but every step of the way is kept ---------

    def invoke(self, context, event):
        res = MCH_OT_concept_move.invoke(self, context, event)
        if 'RUNNING_MODAL' in res:
            self.trail = [self.hit.copy()]
            from .stabilizer import LazyStabilizer       # 0.24.36 Lazy Mouse (Slow Line) for the path too
            self.stab = LazyStabilizer(context.scene.mch_brush)
            self.stab.reset(self.mouse, time.monotonic())
            self.local = []
            self._sig = None
            self.info = None                                 # Extend / Separate Tube: the section (once known)
            self.method_now = None
            self.preview_ob = None
            self.local_hit = self.mref @ (self.mwi @ self.hit)
            rv3d = context.region_data                   # 0.24.58 Back Mask: the way to the viewer at the grab
            eye = rv3d.view_matrix.inverted().translation
            self.toward = (eye - self.hit) if rv3d.is_perspective else rv3d.view_rotation @ Vector((0.0, 0.0, 1.0))
        return res

    def _to_local(self, p):
        return self.mref @ (self.mwi @ p)

    def _section_offsets(self, context):
        """The path in the object's space, as offsets from the grab point (smoothed, evenly spaced)."""
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
        step = brush_world(context, self.hit) * scale * 0.3
        local = even_path(smooth_path([self._to_local(p) for p in self.trail]), step, 96)
        if self.info:                                    # 0.24.42 no turn tighter than the section: no folds
            local = relax_path(local, section_radius(self.info) * 1.05)
        return [p - self.local_hit for p in local]

    def _brush_local(self, context):
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
        return brush_world(context, self.hit) * scale

    def _method(self, context):
        """The method of this drag (0.24.44: always the one picked - switching a drag to Stretch by itself crashed
        Blender)."""
        if getattr(self, 'silhouette', False):
            return 'EXTEND'
        return getattr(self, 'method_now', None) or context.scene.mch_concept.path_method

    def _area(self, context):
        """0.24.76 Brush / Whole of this drag - Silhouette Move: always Whole (the part's whole section)."""
        return 'SECTION' if getattr(self, 'silhouette', False) else context.scene.mch_concept.path_area

    def _section_preview(self, context):
        """Extend / Separate Tube while dragging: only the new rings (and the carried end) are rebuilt."""
        from . import path_sweep
        st = context.scene.mch_concept
        offsets = self._section_offsets(context)
        if len(offsets) < 2:
            return
        if self.info is None:
            normal = offsets[-1] - offsets[0]
            if normal.length < brush_world(context, self.hit) * 0.3:
                return                                       # wait until the way it goes is clear
            self.normal_l = normal.normalized()
            rad = local_radius(context, self.ob, self.hit) if MCH_OT_concept_path._area(self, context) == 'BRUSH' else None
            self.info = path_sweep.analyse(self.ob.data, self.local_hit, self.normal_l, rad,
                                           4 if st.shape == 'BOX' else 8, st.path_back_mask and rad is not None) or False
            if self.info:
                me = bpy.data.meshes.new('MCH_PathPreview')
                self.preview_ob = bpy.data.objects.new('MCH_PathPreview', me)
                context.scene.collection.objects.link(self.preview_ob)
                self.preview_ob.matrix_world = self.ob.matrix_world.copy()
                path_sweep.copy_mirror(self.ob, self.preview_ob)
                self.preview_ob.display_type = 'SOLID'
                self.preview_ob.show_wire = True
        if not self.info:
            return
        path = path_sweep.path_from(self.info['centre'], offsets)
        verts, faces = path_sweep.preview_geometry(self.info, path, self.normal_l, st.path_turn, st.path_taper,
                                                   MCH_OT_concept_path._method(self, context), st.path_hardness)
        me = self.preview_ob.data
        me.clear_geometry()
        me.from_pydata([tuple(v) for v in verts], [], faces)
        me.update()

    def _toggle_area(self, context):
        if getattr(self, 'silhouette', False):           # (Silhouette Move: always the whole section)
            return
        st = context.scene.mch_concept
        st.path_area = 'SECTION' if st.path_area == 'BRUSH' else 'BRUSH'
        if getattr(self, 'info', None) is not None:          # read the grab again the other way
            self._drop_preview()
            self.info = None
        self._header(context)
        self._preview(context)

    def _drop_preview(self):
        ob = getattr(self, 'preview_ob', None)
        if ob is not None:
            me = ob.data
            bpy.data.objects.remove(ob, do_unlink=True)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        self.preview_ob = None

    def _header(self, context):
        st = context.scene.mch_concept
        if getattr(self, 'silhouette', False):
            context.area.header_text_set(
                f'Silhouette Move  |  {len(getattr(self, "trail", [])) - 1} steps  the whole part follows  |  '
                f'taper {st.path_taper:.2f}  hardness {st.path_hardness:.2f}  |  '
                'drag the way it should go   Wheel: depth   [ ]: size   3D mouse / MMB: view   RMB/Esc: cancel')
            return
        context.area.header_text_set(
            f'Path Move  |  {len(getattr(self, "trail", [])) - 1} steps  {st.shape.title()}  taper {st.path_taper:.2f}  '
            f'hardness {st.path_hardness:.2f}  |  Mirror X {"on" if st.mirror_x else "off"}  |  '
            + (f'Extend: {"brush area" if st.path_area == "BRUSH" else "whole section"} (Tab)  |  '
               if st.path_method == 'EXTEND' else '')
            + f'Back Mask {"on" if st.path_back_mask else "off"} (B)  |  '
            + 'drag the way it should go   Wheel: depth   [ ]: size   3D mouse / MMB: view   RMB/Esc: cancel')

    def _target(self, context):
        return MCH_OT_concept_move._target(self, context)

    def _world_radius(self, context, px, at=None):
        return MCH_OT_concept_move._world_radius(self, context, px, at)

    def _finish_ui(self, context):
        MCH_OT_concept_move._finish_ui(self, context)

    def _world_path(self, context):
        """(path, radius, axes) in the scene: the trail smoothed and evenly spaced, the box facing the view."""
        rv3d = context.region_data
        radius = brush_world(context, self.hit)
        vm = rv3d.view_matrix.to_3x3().transposed()
        axes = [c for i in range(3) for c in vm.col[i].normalized()]
        return even_path(smooth_path(self.trail), radius * 0.3), radius, axes

    def _preview(self, context, timer=False):
        st = context.scene.mch_concept
        target = self._target(context)
        step = brush_world(context, self.hit) * 0.15
        if (target - self.trail[-1]).length > step:
            self.trail.append(target.copy())
        region, rv3d = context.region, context.region_data
        self.target = self.trail[-1]
        self.center_2d = view3d_utils.location_3d_to_region_2d(region, rv3d, self.target) or self.mouse
        self.r_px = brush_px(context, self.target) * max(1.0 - st.path_taper, 0.05)
        sig = (len(self.trail), st.radius_px, st.radius_world, st.path_hardness, st.path_taper, st.path_turn, st.shape,
               self._method(context))
        if sig == self._sig:
            return
        self._sig = sig
        if self._method(context) != 'STRETCH':
            self._section_preview(context)
            if self._method(context) != 'STRETCH':
                self._header(context)
                return
        path, radius, axes = self._world_path(context)
        for part in self.parts:
            ob = part['ob']
            lpts, lrad, laxes = local_path(ob, path, radius, axes, part['mref'])
            moves = path_moves(lpts, lrad, st.path_hardness, st.path_taper, st.mirror_x and not part['own'], st.shape,
                               laxes, st.path_turn)
            co = run_path(part['orig'], moves) if moves else part['orig']
            if moves and st.path_back_mask:                  # 0.24.58 the far side stays put
                if part.get('back_w') is None:
                    part['back_w'] = facing_weights(vertex_normals(ob.data),
                                                    toward_local(ob, self.toward, part['mref']))
                w = part['back_w']
                co = part['orig'] + w[:, None] * (co - part['orig'])
            write_coords(ob.data, co)
        self._header(context)

    def modal(self, context, event):
        st = context.scene.mch_concept
        if event.type in NAV_EVENTS:
            return {'PASS_THROUGH'}
        if event.type in {'TIMER', 'MOUSEMOVE'}:
            stab = getattr(self, 'stab', None)
            raw = (event.mouse_region_x, event.mouse_region_y)
            if stab is not None and stab.active:          # Slow Line: the path follows the mouse lazily
                p = stab.update(raw, time.monotonic()) if event.type == 'MOUSEMOVE' else stab.tick(time.monotonic())
                if p is not None:
                    self.mouse = (p[0], p[1])
            elif event.type == 'MOUSEMOVE':
                self.mouse = raw
            self._preview(context)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = brush_world(context, self.hit) * 0.15
            self.depth += step if event.type == 'WHEELDOWNMOUSE' else -step
            self._preview(context)
        elif event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            scale_size(st, 1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)
            self._preview(context)
        elif event.type == 'TAB' and event.value == 'PRESS':
            self._toggle_area(context)               # 0.24.55 Extend: the brush patch <-> the whole section
        elif event.type == 'B' and event.value == 'PRESS':
            st.path_back_mask = not st.path_back_mask    # 0.24.58 Back Mask on / off while dragging
            if getattr(self, 'info', None) is not None:
                self._drop_preview()
                self.info = None
            self._sig = None
            self._preview(context)
        elif event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            self._finish_ui(context)
            MCH_OT_concept_move._restore(self)               # back to the start: execute() does the real thing
            self._drop_preview()
            if self._method(context) != 'STRETCH':
                offsets = self._section_offsets(context)
                if len(offsets) < 2 or not getattr(self, 'normal_l', None):
                    return {'CANCELLED'}
                self.method = self._method(context)
                self.objects = json.dumps([self.ob.name])
                self.grab_point, self.grab_normal = self.local_hit, self.normal_l
                self.offsets = json.dumps([list(o) for o in offsets])
                self.taper, self.turn, self.auto_apply = st.path_taper, st.path_turn, st.auto_apply
                self.edge_hardness = st.path_hardness
                self.area, self.shape = self._area(context), st.shape
                self.radius, self.size = local_radius(context, self.ob, self.hit), 1.0
                self.back_mask = st.path_back_mask and not self.silhouette
                return self.execute(context)
            path, radius, axes = self._world_path(context)
            if len(path) < 2:
                return {'CANCELLED'}
            self.space = 'WORLD'
            self.method = 'STRETCH'                          # also when a too-thick section made it a Stretch
            self.objects = json.dumps([p['ob'].name for p in self.parts])
            self.auto_apply = st.auto_apply
            self.path = json.dumps([list(p) for p in path])
            self.radius, self.size, self.axes = radius, 1.0, axes
            self.hardness, self.taper, self.shape, self.mirror = st.path_hardness, st.path_taper, st.shape, st.mirror_x
            self.turn, self.back_mask = st.path_turn, st.path_back_mask
            self.generate_mesh, self.even_out = st.keep_density, st.even_out
            return self.execute(context)
        elif event.type in {'RIGHTMOUSE', 'ESC'} and event.value == 'PRESS':
            MCH_OT_concept_move._restore(self)
            self._drop_preview()
            self._finish_ui(context)
            return {'CANCELLED'}
        if context.area:
            context.area.tag_redraw()
        return {'RUNNING_MODAL'}


def local_radius(context, ob, at):
    """The brush radius at ``at`` in ``ob``'s own space."""
    sc = ob.matrix_world.to_scale()
    return brush_world(context, at) / max(1e-9, (abs(sc.x) + abs(sc.y) + abs(sc.z)) / 3.0)


def local_path(ob, pts, radius, axes, mref=None):
    """A path, its radius and box axes in the scene -> in ob's own space (through its own Mirror)."""
    from mathutils import Matrix
    mref = mref if mref is not None else Matrix.Identity(4)
    lm = to_local({'centre': list(pts[0]), 'radius': radius, 'axes': list(axes)}, ob, mref)
    mwi = ob.matrix_world.inverted_safe()
    return [mref @ (mwi @ Vector(p)) for p in pts], lm['radius'], lm['axes']


def _closest_seg(a, b, q):
    ab = b - a
    t = 0.0 if ab.length_squared < 1e-12 else max(0.0, min(1.0, (q - a).dot(ab) / ab.length_squared))
    return a + ab * t


def _in_tool_header(context):
    """0.24.78 Blender's tool header (the row at the top of the viewport): empty, like for every other Mecha tool -
    the settings are in the side panel / sidebar (they filled the whole header row here)."""
    region = getattr(context, 'region', None)
    return region is not None and region.type == 'TOOL_HEADER'


class MCH_TOOL_concept_path(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.concept_path'
    bl_label = 'Mecha Path Move'
    bl_description = ('Concept: grab like Concept Move and drag a path - the box / ball keeps its shape and\n'
                      'follows the way you go (frames, pipes, arms).  F + mouse: size.  Wheel while dragging: depth')
    bl_icon = 'ops.sculpt.cloth_filter'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_path', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
        ('mch.concept_resize', {'type': 'F', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        if _in_tool_header(context):
            return
        draw_path(layout, context, compact=True)


class MCH_TOOL_silhouette_move(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.silhouette_move'
    bl_label = 'Mecha Silhouette Move'
    bl_description = ('0.24.76 Path Move that always pulls the whole part: cut where you grab, the whole section\n'
                      'follows the way you go, so the part stretches and bends (its silhouette changes)')
    bl_icon = 'ops.sculpt.cloth_filter'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_path', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, {'properties': [('silhouette', True)]}),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
        ('mch.concept_resize', {'type': 'F', 'value': 'PRESS'}, None),
    )

    def draw_settings(context, layout, tool):
        if _in_tool_header(context):
            return
        draw_path(layout, context, compact=True, silhouette=True)


def knife_grid(bm, cuts):
    """0.24.35 Knife Mesh: slice the whole mesh with evenly spaced planes along X, Y and Z (its own space) - the
    shape stays exactly the same, the faces get evenly split so a move / path move bends where you grab.  Returns
    the number of planes."""
    if not bm.verts:
        return 0
    lo = Vector([min(v.co[i] for v in bm.verts) for i in range(3)])
    hi = Vector([max(v.co[i] for v in bm.verts) for i in range(3)])
    size = hi - lo
    step = max(size) / max(2, cuts)
    if step <= 1e-9:
        return 0
    n = 0
    for axis in range(3):
        parts = int(round(size[axis] / step))       # even spacing along this side, about ``step`` apart
        for k in range(1, parts):
            co = lo.copy()
            co[axis] = lo[axis] + size[axis] * k / parts
            no = Vector((0.0, 0.0, 0.0))
            no[axis] = 1.0
            bmesh.ops.bisect_plane(bm, geom=bm.verts[:] + bm.edges[:] + bm.faces[:], plane_co=co, plane_no=no,
                                   dist=step * 1e-4)
            n += 1
    return n


class MCH_OT_knife_grid(bpy.types.Operator):
    """Knife the whole selected mesh evenly (X / Y / Z slices): the shape stays, the faces get split evenly so the
    move bends where you grab instead of at the old edges"""
    bl_idname = 'mch.knife_grid'
    bl_label = 'Knife Mesh'
    bl_options = {'REGISTER', 'UNDO'}

    cuts: IntProperty(name='Knife Cuts', default=12, min=2, max=64)

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and any(_mesh_ok(o) for o in context.selected_objects + [context.active_object]
                                                if o is not None)

    def execute(self, context):
        if not self.properties.is_property_set('cuts'):      # the button: the Cuts slider next to it
            self.cuts = context.scene.mch_concept.knife_cuts
        obs = [o for o in dict.fromkeys(context.selected_objects + [context.active_object]) if _mesh_ok(o)]
        total = 0
        for ob in obs:
            bm = bmesh.new()
            bm.from_mesh(ob.data)
            planes = knife_grid(bm, self.cuts)
            bm.to_mesh(ob.data)
            bm.free()
            ob.data.update()
            total += planes
        context.scene.mch_concept.knife_cuts = self.cuts
        self.report({'INFO'}, f'Knife Mesh: {len(obs)} mesh(es), {total} slices')
        return {'FINISHED'}


def draw_slow_line(layout, context):
    """0.24.36 Slow Line (Lazy Mouse) on / off - the same switch as in the drawing tools."""
    brush = context.scene.mch_brush
    row = layout.row(align=True)
    row.prop(brush, 'stab_enable', text='Slow Line', toggle=True, icon='MOD_SMOOTH')
    if brush.stab_enable:
        row.prop(brush, 'stab_strength', text='', slider=True)


def draw_knife(layout, context):
    row = layout.row(align=True)
    row.prop(context.scene.mch_concept, 'knife_cuts', text='Cuts')
    row.operator('mch.knife_grid', icon='MOD_EDGESPLIT')


def draw_path(layout, context, compact=False, silhouette=False):
    from . import path_sweep
    st = context.scene.mch_concept
    if silhouette:                       # 0.24.76 Silhouette Move: Extend, the whole section - nothing to pick
        layout.label(text='The whole part follows the drag', icon='MOD_SIMPLEDEFORM')
    else:
        layout.prop(st, 'path_method', expand=not compact, text='' if compact else 'Method')
        if st.path_method == 'EXTEND':
            layout.prop(st, 'path_area', expand=True)
    if not compact:
        draw_knife(layout, context)
        draw_slow_line(layout, context)
    ob = context.active_object
    if not compact and ob is not None and path_sweep.SOURCE_KEY in ob:
        row = layout.row(align=True)
        row.operator('mch.path_merge', text='Merge: Join', icon='LINKED').mode = 'JOIN'
        row.operator('mch.path_merge', text='Merge: Union', icon='MOD_BOOLEAN').mode = 'UNION'
    if not compact and st.path_method == 'STRETCH' and not silhouette:
        draw_targets(layout, context)
    elif not compact:
        layout.prop(st, 'auto_apply', text='Auto Apply (OFF = live, editable moves)')
    row = layout.row(align=True)
    row.prop(st, 'radius_world' if st.lock_size else 'radius_px')
    row.prop(st, 'lock_size', toggle=True)
    layout.prop(st, 'path_hardness', slider=True)
    layout.prop(st, 'path_taper', slider=True)
    row = layout.row(align=True)
    row.prop(st, 'path_turn', toggle=True)
    if not silhouette:
        row.prop(st, 'path_back_mask', toggle=True, icon='MOD_MASK')
    layout.prop(st, 'shape', text='' if compact else 'Shape')
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
    if not compact:
        draw_moves(layout, context)


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
    bl_description = 'Forget the remembered moves of this object (live: back to what its sliders make; editable: back to the mesh before them)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and MOVES_KEY in ob

    def execute(self, context):
        ob = context.active_object
        n = len(recorded_moves(ob))
        if has_base(ob):                                     # editable moves: back to the kept mesh
            rebuild_from_base(ob, [])
            drop_base(ob)
            del ob[MOVES_KEY]
        else:
            del ob[MOVES_KEY]
            rebuild_live(context, ob)
        self.report({'INFO'}, f'{n} move(s) cleared')
        return {'FINISHED'}


class MCH_OT_path_merge(bpy.types.Operator):
    bl_idname = 'mch.path_merge'
    bl_label = 'Merge Path Tube'
    bl_description = 'Merge this Separate Tube into the mesh it came from (Join = one object, Union = boolean)'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=[('JOIN', 'Join', 'One object (fast)'), ('UNION', 'Union', 'Boolean union (one surface)')],
                       default='JOIN')

    @classmethod
    def poll(cls, context):
        from . import path_sweep
        ob = context.active_object
        return context.mode == 'OBJECT' and ob is not None and path_sweep.SOURCE_KEY in ob

    def execute(self, context):
        from . import path_sweep
        try:
            src = path_sweep.merge(context, context.active_object, self.mode)
        except (ValueError, RuntimeError) as exc:
            self.report({'WARNING'}, f'Merge: {exc}')
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        src.select_set(True)
        context.view_layer.objects.active = src
        self.report({'INFO'}, f'Merged into {src.name} ({self.mode.title()})')
        return {'FINISHED'}


class MCH_OT_concept_undo_last(bpy.types.Operator):
    bl_idname = 'mch.concept_undo_last'
    bl_label = 'Undo Last Move'
    bl_description = 'Take back the last remembered Concept / Path Move of this object (the others stay)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and bool(recorded_moves(ob))

    def execute(self, context):
        ob = context.active_object
        moves = recorded_moves(ob)[:-1]
        if has_base(ob):
            rebuild_from_base(ob, moves)
        else:
            ob[MOVES_KEY] = json.dumps(moves)
            rebuild_live(context, ob)
        if not moves and MOVES_KEY in ob:
            del ob[MOVES_KEY]
        self.report({'INFO'}, f'{len(moves)} move(s) left')
        return {'FINISHED'}


class MCH_OT_concept_bake(bpy.types.Operator):
    bl_idname = 'mch.concept_bake'
    bl_label = 'Apply Moves'
    bl_description = 'Make the editable moves part of the mesh (they can no longer be taken back one by one)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return has_base(context.active_object)

    def execute(self, context):
        ob = context.active_object
        drop_base(ob)
        if MOVES_KEY in ob:
            del ob[MOVES_KEY]
        self.report({'INFO'}, 'Moves applied')
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
        if _in_tool_header(context):
            return
        draw(layout, context, compact=True)


def draw_targets(layout, context):
    """Like the Cut tool: Through All / From Surface, Auto Target / Selected Only / Active, Auto Apply."""
    st = context.scene.mch_concept
    col = layout.column(align=True)
    col.prop(st, 'depth_mode', expand=True)
    col.prop(st, 'targets', expand=True)
    col.prop(st, 'auto_apply', text='Auto Apply (OFF = live, editable moves)')


def draw_moves(layout, context):
    ob = context.active_object
    if ob is None or MOVES_KEY not in ob:
        return
    n = len(recorded_moves(ob))
    col = layout.column(align=True)
    col.label(text=f'{n} editable move(s) on {ob.name}', icon='MODIFIER')
    row = col.row(align=True)
    row.operator('mch.concept_undo_last', text='Undo Last', icon='LOOP_BACK')
    row.operator('mch.concept_clear', text='Clear', icon='X')
    if has_base(ob):
        row.operator('mch.concept_bake', text='Apply', icon='CHECKMARK')


def draw(layout, context, compact=False):
    st = context.scene.mch_concept
    if not compact:
        draw_targets(layout, context)
        draw_knife(layout, context)
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
    if not compact:
        draw_moves(layout, context)


CLASSES = (MCH_PG_Concept, MCH_OT_concept_move, MCH_OT_concept_path, MCH_OT_concept_hold, MCH_OT_concept_size,
           MCH_OT_concept_resize, MCH_OT_concept_add, MCH_OT_concept_fuse, MCH_OT_concept_clear,
           MCH_OT_concept_undo_last, MCH_OT_concept_bake, MCH_OT_path_merge, MCH_OT_knife_grid)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_concept = bpy.props.PointerProperty(type=MCH_PG_Concept)
    _hook_live_modules()
    try:
        bpy.utils.register_tool(MCH_TOOL_concept_move, separator=True, group=False)
        bpy.utils.register_tool(MCH_TOOL_concept_path, after={MCH_TOOL_concept_move.bl_idname}, group=False)
        bpy.utils.register_tool(MCH_TOOL_silhouette_move, after={MCH_TOOL_concept_path.bl_idname}, group=False)
    except (ValueError, RuntimeError):
        pass


def unregister():
    for tool in (MCH_TOOL_silhouette_move, MCH_TOOL_concept_path, MCH_TOOL_concept_move):
        try:
            bpy.utils.unregister_tool(tool)
        except (ValueError, RuntimeError, KeyError, AttributeError):
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
