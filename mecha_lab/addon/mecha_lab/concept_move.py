"""0.24.32 Concept Move: grab the surface and pull it - the stretch-and-look move of VR modelers, in Object Mode.

Press on a mesh and drag: the area under the brush follows the mouse like clay (a light preview while you drag).
When you let go the pulled part is really generated: what got stretched is split in its rest shape and pulled
again, so the new points sit on the curved surface and the faces stay as dense as the rest of the mesh (no long
stretched faces).  Then F9 / Adjust Last Operation: Size, Hardness, Pull, Shape, Falloff - recomputed from the
original.
* Shape: Sphere or Box (a view-aligned cube - frames, plates, flat panels).  Hardness: how much of the brush moves
  whole (1 = a rigid lump, 0 = a soft dome).  Falloffs: Clay (hardness), Elastic (Kelvinlet grab), Sharp.
* While dragging: Shift = straight out of the surface, wheel = depth, [ ] = size, right click / Esc = cancel.
  A 3D mouse (and middle mouse) still navigates the view; with Follow View the grab stays in front of you, so
  moving the view carries the clay even with the mouse held still (re-evaluated 60 times a second).
* Live objects (cape, hood, plates ... still on their sliders) need no Apply: every move is recorded on the object
  and replayed (with the same generation) each time the sliders rebuild it.  Clear Moves forgets them.
* Hold D and drag (in any tool of the MECHA LAB workspace): the same move without switching tools.
* Shift+click: drop a clay blob.  Fuse: join the selected clay into one smooth piece (voxel remesh).
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


def displace(co, centre, delta, radius, falloff='CLAY', mirror_x=False, shape='SPHERE', hardness=0.5,
             axes=None):
    """New coordinates (N,3) for a grab at centre moved by delta (all in the same space)."""
    co = np.asarray(co, dtype=np.float64)
    out = co.copy()
    if axes is None:
        axes = np.eye(3)
    axes = np.asarray(axes, dtype=np.float64).reshape(3, 3)
    brushes = [(np.asarray(centre, dtype=np.float64), np.asarray(delta, dtype=np.float64), axes)]
    if mirror_x and abs(centre[0]) > radius * 0.5:          # a grab on the middle already moves both sides
        flip = np.array([-1.0, 1.0, 1.0])
        brushes.append((brushes[0][0] * flip, brushes[0][1] * flip, axes * flip))
    for c, d, ax in brushes:
        r = co - c
        dist = box_distance(r, ax) if shape == 'BOX' else np.sqrt((r * r).sum(1))
        if falloff == 'ELASTIC':
            s, t = elastic_weights(dist, radius)
            out += s[:, None] * d[None, :] + (t * (r @ d))[:, None] * r
        elif falloff == 'SHARP':
            out += sharp_weights(dist, radius)[:, None] * d[None, :]
        else:
            out += clay_weights(dist, radius, hardness)[:, None] * d[None, :]
    return out


def move_field(move):
    """A recorded move (dict) -> function rest coords (N,3) -> moved coords."""
    def f(co):
        return displace(co, move['centre'], move['delta'], move['radius'], move.get('falloff', 'CLAY'),
                        move.get('mirror', False), move.get('shape', 'SPHERE'), move.get('hardness', 0.5),
                        move.get('axes'))
    return f


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


def generate(me, field, ratio=1.3, max_rounds=6, max_verts=400000):
    """Really generate the pulled part: split (in the rest shape) every edge the field stretches past ratio x the
    mesh's usual edge, repeat, then move everything.  New points land on the smooth moved surface, the faces keep
    the mesh's density.  Returns the number of edges split."""
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
    bm.to_mesh(me)
    bm.free()
    me.update()
    return split


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
        generate(ob.data, move_field(mv))
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
    follow_view: BoolProperty(name='Follow View', default=True,
                              description='The grab stays in front of you while the view turns (3D mouse = hand)')
    strength: FloatProperty(name='Strength', default=1.0, min=0.05, max=2.0,
                            description='How far the surface follows the mouse')
    fuse_detail: FloatProperty(name='Fuse Detail', default=0.01, min=0.001, max=0.2, precision=3,
                               description='Fuse voxel size (part of the clay size): smaller = more detail')


_DRAW = [None]


def _draw_brush(op, context):
    import gpu
    from gpu_extras.batch import batch_for_shader
    try:
        if op.center_2d is None:
            return
        cx, cy = op.center_2d
        st = context.scene.mch_concept
        r = st.radius_px
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

    def move_dict(self):
        return {'centre': list(self.centre), 'delta': [c * self.pull for c in self.delta],
                'radius': self.radius * self.size, 'falloff': self.falloff, 'mirror': self.mirror,
                'shape': self.shape, 'hardness': self.hardness, 'axes': list(self.axes)}

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
            n = generate(ob.data, field)
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
        if self.falloff == 'CLAY':
            col.prop(self, 'hardness', slider=True)
        self.layout.prop(self, 'shape', expand=True)
        self.layout.prop(self, 'falloff')
        row = self.layout.row(align=True)
        row.prop(self, 'mirror', toggle=True)
        row.prop(self, 'generate_mesh', toggle=True)

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
        self.dist0 = (loc - origin).length                   # Follow View: distance along the mouse ray
        self.mw = ob.matrix_world.copy()
        self.mwi = self.mw.inverted_safe()
        self.orig = read_coords(ob.data)
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
            f'Concept Move  |  {st.shape.title()} {st.radius_px}px  hardness {st.hardness:.2f}  |  {st.falloff.title()}'
            f'  |  Mirror X {"on" if st.mirror_x else "off"}  |  Follow View {"on" if st.follow_view else "off"}'
            '  |  Shift: out   Wheel: depth   [ ]: size   3D mouse / MMB: view   RMB/Esc: cancel')

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
        radius = self._world_radius(context, st.radius_px, self.hit)
        m3 = self.mwi.to_3x3()
        scale = (m3 @ Vector((1.0, 0.0, 0.0))).length if abs(m3.determinant()) > 1e-12 else 1.0
        vm = rv3d.view_matrix.to_3x3().transposed()        # box faces the view: screen right / up / depth
        axes = [c for i in range(3) for c in (m3 @ vm.col[i]).normalized()]
        return {'centre': list(self.mwi @ self.hit), 'delta': list(m3 @ delta), 'radius': radius * scale,
                'falloff': st.falloff, 'mirror': st.mirror_x, 'shape': st.shape, 'hardness': st.hardness,
                'axes': axes}

    def _preview(self, context):
        self.cur = self._current_move(context)
        write_coords(self.ob.data, move_field(self.cur)(self.orig))

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
            self._preview(context)
        elif event.type == 'MOUSEMOVE':
            self.mouse = (event.mouse_region_x, event.mouse_region_y)
            self.shift = event.shift
            self._preview(context)
        elif event.type in {'WHEELUPMOUSE', 'WHEELDOWNMOUSE'}:
            step = self._world_radius(context, st.radius_px) * 0.15
            self.depth += step if event.type == 'WHEELDOWNMOUSE' else -step
            self._preview(context)
        elif event.type in {'LEFT_BRACKET', 'RIGHT_BRACKET'} and event.value == 'PRESS':
            st.radius_px = max(5, int(st.radius_px * (1.15 if event.type == 'RIGHT_BRACKET' else 1 / 1.15)))
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
            self.generate_mesh = st.keep_density
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
        st = context.scene.mch_concept
        st.radius_px = max(5, int(round(st.radius_px * self.factor)))
        return {'FINISHED'}


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
        st = context.scene.mch_concept
        a = view3d_utils.region_2d_to_location_3d(region, rv3d, mouse, at)
        b = view3d_utils.region_2d_to_location_3d(region, rv3d, (mouse[0] + st.radius_px * 0.6, mouse[1]), at)
        ob = add_blob(context, at, max((a - b).length, 1e-4))
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
                      'Shift+click: add clay.  Dragging: Shift = out, wheel = depth, [ ] = size, 3D mouse = view')
    bl_icon = 'ops.transform.translate'
    bl_widget = None
    bl_keymap = (
        ('mch.concept_move', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
        ('mch.concept_add', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'shift': True}, None),
        ('mch.concept_size', {'type': 'LEFT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1 / 1.15)]}),
        ('mch.concept_size', {'type': 'RIGHT_BRACKET', 'value': 'PRESS'}, {'properties': [('factor', 1.15)]}),
    )

    def draw_settings(context, layout, tool):
        draw(layout, context, compact=True)


def draw(layout, context, compact=False):
    st = context.scene.mch_concept
    layout.prop(st, 'shape', text='' if compact else 'Shape')
    layout.prop(st, 'radius_px')
    if st.falloff == 'CLAY':
        layout.prop(st, 'hardness', slider=True)
    layout.prop(st, 'falloff', text='' if compact else 'Falloff')
    layout.prop(st, 'strength')
    layout.prop(st, 'mirror_x', toggle=True)
    layout.prop(st, 'keep_density', toggle=True)
    layout.prop(st, 'follow_view', toggle=True)
    layout.operator('mch.concept_fuse', icon='META_BALL')
    ob = context.active_object
    if ob is not None and MOVES_KEY in ob:
        layout.operator('mch.concept_clear', text=f'Clear Moves ({len(recorded_moves(ob))})', icon='X')


CLASSES = (MCH_PG_Concept, MCH_OT_concept_move, MCH_OT_concept_hold, MCH_OT_concept_size, MCH_OT_concept_add, MCH_OT_concept_fuse,
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
