"""0.24.52 Groups, the Substance 3D Modeler way.

- Group: the selected parts go into a new collection with a group handle (an Empty at their middle) as parent -
  move / turn / scale the handle and the whole group follows.  Groups can hold groups.
- Ungroup: the parts go back to where they were (their old collections), handle and collection removed.
- Merge: the group's meshes (modifiers baked) become one mesh.
- Enter / Exit (scope): inside a group everything else is shown as wire and cannot be selected.
- Repetition (non-destructive, linked): Mirror (X / Y / Z planes), Radial (Count copies round an axis) or Kaleido
  (both), about the world origin and axes (0.24.53 default; or the group handle, or the 3D cursor - Centre),
  or Grid (0.24.55: X x Y x Z copies side by side, the group's size plus Gap apart).  The copies are made by a Geometry Nodes object that shows the group's
  collection again, so editing a part changes every copy at once; switching it off removes them.  Apply makes
  the copies real objects.

Everything is plain Blender data (collections, an Empty, one helper object) so files open without the add-on.
"""
from __future__ import annotations

import json
import math

import bpy
from mathutils import Matrix, Vector

GROUP_KEY = 'mch_group'                  # on the handle: its collection's name
FROM_KEY = 'mch_group_from'              # on a member: the collections it came from (json)
CARRIER_KEY = 'mch_group_carrier'        # on the repetition object: the handle's name
LINKED_KEY = 'mch_linked'                # 0.24.85 on a part: it shares its mesh with a linked group copy (edits
BOX_HIDDEN_KEY = 'mch_box_hidden'        #   on one show on all); on a handle: its box lines are off
SCOPE_KEY = 'mch_scope'                  # on the scene: the handle of the group we are in
SAVED_KEY = 'mch_scope_saved'            # on other objects while in a group: [hide_select, display_type]
MOD_NAME = 'MCH_GroupRepeat'
TREE_PREFIX = 'MCH Group Repeat | '


# --- finding --------------------------------------------------------------------------------------------------

def is_group(ob):
    return ob is not None and ob.type == 'EMPTY' and GROUP_KEY in ob


def group_of(ob):
    """The nearest group handle of ``ob`` (itself, a parent, or the group a repetition object belongs to)."""
    if ob is None:
        return None
    if CARRIER_KEY in ob:
        return bpy.data.objects.get(ob[CARRIER_KEY])
    o = ob
    while o is not None:
        if is_group(o):
            return o
        o = o.parent
    return None


def collection_of(g):
    return bpy.data.collections.get(g.get(GROUP_KEY, '')) if g is not None else None


def members(g):
    """Every object in the group (nested groups included), handles of nested groups too."""
    coll = collection_of(g)
    return list(coll.all_objects) if coll is not None else []


def _pivots(context, objs):
    """The symmetry centres (mirror / radial empties) the parts in ``objs`` use."""
    from . import radial_sym, symmetry
    objs = set(objs)
    out = []
    rs = getattr(context.scene, 'mch_rsym', None)
    rpiv = rs.pivot if rs is not None else None
    for o in objs:
        m = symmetry.mirror_mod(o)
        p = m.mirror_object if m is not None else None
        if p is not None and p not in objs and p not in out and (p.get('_mch_world_pivot') or p == rpiv):
            out.append(p)
    if rpiv is not None and rpiv not in out:
        rad = radial_sym.members(context)
        if rad and all(o in objs for o in rad):            # every radial part is in here: its centre comes along
            out.append(rpiv)
    return out


def adopt_pivots(context, g):
    """0.24.57 the symmetry centres of the group's parts follow the group: move the group and a mirrored / radial
    part moves as one piece with its copies (they no longer spread round the world origin)."""
    if not is_group(g):
        return 0
    n = 0
    for p in _pivots(context, members(g)):
        if p.parent is None or not is_group(p.parent):
            mw = p.matrix_world.copy()
            p.parent = g
            p.matrix_world = mw
            n += 1
    return n


def _release_pivots(g):
    for p in [c for c in g.children if c.type == 'EMPTY' and not is_group(c) and GROUP_KEY not in c]:
        mw = p.matrix_world.copy()
        p.parent = g.parent
        p.matrix_world = mw


def carrier_of(g):
    return next((o for o in bpy.data.objects if o.get(CARRIER_KEY) == g.name), None) if g is not None else None


def _world_box(objs):
    pts = []
    for o in objs:
        if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
        else:
            pts.append(o.matrix_world.translation.copy())
    if not pts:
        return Vector(), Vector((1, 1, 1))
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return (lo + hi) / 2, hi - lo


# --- group / ungroup / merge ---------------------------------------------------------------------------------

def create(context, objs, name='Group'):
    """Group ``objs``; returns the handle."""
    objs = [o for o in objs if CARRIER_KEY not in o]
    if not objs:
        return None
    parent_coll = next(iter(objs[0].users_collection), context.scene.collection)
    outer = group_of(objs[0].parent) if objs[0].parent is not None else None   # not objs[0]: it may be a group
    if parent_coll.get(GROUP_KEY) is None and collection_of(outer) is not None:
        parent_coll = collection_of(outer)                        # grouping inside a group: nest there
    coll = bpy.data.collections.new(name)
    parent_coll.children.link(coll)
    centre, size = _world_box(objs)
    g = bpy.data.objects.new(coll.name, None)
    handle_look(g, size)
    g.show_in_front = True
    parent_coll.objects.link(g)
    g.matrix_world = Matrix.Translation(centre)
    if outer is not None:                      # a group inside a group follows the outer handle
        g.parent = outer
        g.matrix_world = Matrix.Translation(centre)
    g[GROUP_KEY] = coll.name
    coll[GROUP_KEY] = g.name
    picked = set(objs)
    for o in objs:
        if is_group(o):                        # a nested group: its collection moves under ours
            sub = collection_of(o)
            if sub is not None:
                for pc in [c for c in bpy.data.collections if sub.name in c.children]:
                    pc.children.unlink(sub)
                if sub.name in context.scene.collection.children:
                    context.scene.collection.children.unlink(sub)
                coll.children.link(sub)
        old = [c.name for c in o.users_collection]
        o[FROM_KEY] = json.dumps(old)
        for c in list(o.users_collection):
            c.objects.unlink(o)
        coll.objects.link(o)
        if o.parent is None or o.parent not in picked:
            mw = o.matrix_world.copy()
            o.parent = g
            o.matrix_world = mw
    adopt_pivots(context, g)
    for o in context.selected_objects:
        o.select_set(False)
    g.select_set(True)
    context.view_layer.objects.active = g
    return g


def handle_look(g, size):
    """0.24.58 The handle: a small cross at the centre (still a click target) - the group's outline is a box drawn
    tight round its parts (``_draw_boxes``) instead of a cube as big as the longest side."""
    g.empty_display_type = 'PLAIN_AXES'
    g.empty_display_size = max(0.05, max(size) * 0.2)


def tidy_handles(scene=None):
    """Groups made before 0.24.58 (a big cube) get the small handle."""
    for g in [o for o in bpy.data.objects if is_group(o) and o.empty_display_type == 'CUBE']:
        parts = [o for o in members(g) if o.type == 'MESH']
        if parts:
            handle_look(g, _world_box(parts)[1])


def group_box(g):
    """World box (low, high corners) of the group's parts (its repetition copies not counted)."""
    pts = []
    for o in members(g):
        if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'} and not o.hide_get():
            pts += [o.matrix_world @ Vector(c) for c in o.bound_box]
    if not pts:
        return None
    return (Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts))),
            Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts))))


BOX_EDGES = ((0, 1), (1, 3), (3, 2), (2, 0), (4, 5), (5, 7), (7, 6), (6, 4), (0, 4), (1, 5), (2, 6), (3, 7))


def box_lines(lo, hi, pad=0.02):
    d = (hi - lo) * pad + Vector((1e-3, 1e-3, 1e-3))
    lo, hi = lo - d, hi + d
    c = [Vector((hi.x if i & 1 else lo.x, hi.y if i & 2 else lo.y, hi.z if i & 4 else lo.z)) for i in range(8)]
    return [tuple(c[i]) for e in BOX_EDGES for i in e]


def _draw_boxes():
    try:
        context = bpy.context
        groups = [o for o in context.visible_objects if is_group(o)]
        if not groups:
            return
        import gpu
        from gpu_extras.batch import batch_for_shader
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        sh.bind()
        active = context.view_layer.objects.active
        for g in groups:
            if g.get(BOX_HIDDEN_KEY) and not g.select_get():    # 0.24.85 the Layers panel's box eye (a selected
                continue                                       #  group still shows its box)
            box = group_box(g)
            if box is None:
                continue
            col = ((1.0, 0.62, 0.16, 0.9) if g == active else (1.0, 0.5, 0.1, 0.75)) if g.select_get() \
                else (0.85, 0.88, 0.9, 0.22)
            sh.uniform_float('color', col)
            batch_for_shader(sh, 'LINES', {'pos': box_lines(*box)}).draw(sh)
        gpu.state.blend_set('NONE')
    except Exception:          # never break viewport drawing
        pass


_box_handle = None


@bpy.app.handlers.persistent
def _on_load(_dummy=None):
    try:
        tidy_handles()
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def ungroup(context, g):
    """Parts back where they were; the handle, its collection and any repetition go."""
    if not is_group(g):
        return 0
    set_repeat(context, g, mode='OFF')
    coll = collection_of(g)
    home = next(iter(g.users_collection), context.scene.collection)
    n = 0
    for o in list(coll.objects) if coll else []:
        try:
            old = [bpy.data.collections.get(c) or (context.scene.collection if c == context.scene.collection.name
                                                   else None) for c in json.loads(o.get(FROM_KEY, '[]'))]
        except ValueError:
            old = []
        old = [c for c in old if c is not None and c != coll] or [home]
        coll.objects.unlink(o)
        for c in old:
            if o.name not in c.objects:
                c.objects.link(o)
        if FROM_KEY in o:
            del o[FROM_KEY]
        if o.parent == g:
            mw = o.matrix_world.copy()
            o.parent = g.parent
            o.matrix_world = mw
        n += 1
    if coll is not None:
        for sub in list(coll.children):            # nested groups move up
            coll.children.unlink(sub)
            home.children.link(sub)
        bpy.data.collections.remove(coll)
    if context.scene.get(SCOPE_KEY) == g.name:
        exit_scope(context)
    _release_pivots(g)
    bpy.data.objects.remove(g, do_unlink=True)
    return n


REP_KEYS = ('mch_rep_mode', 'mch_rep_axes', 'mch_rep_axis', 'mch_rep_count', 'mch_rep_center', 'mch_rep_cursor',
            'mch_rep_grid', 'mch_rep_gap')


def duplicate(context, g, linked=False):
    """0.24.81 A copy of the whole group (Shift+D on a group handle copied the handle alone): a new collection next
    to the group's, a new handle, every part copied (``linked``: sharing the mesh, Alt+D style) at the same place
    under it, nested groups and the symmetry centres too, the repetition set up again.  Returns the new handle."""
    if not is_group(g):
        return None
    coll = collection_of(g)
    home = next((c for c in bpy.data.collections if coll is not None and coll.name in c.children), None)
    if home is None:
        home = context.scene.collection if coll is None or coll.name in context.scene.collection.children \
            else next(iter(g.users_collection), context.scene.collection)
    new_coll = bpy.data.collections.new(coll.name if coll is not None else g.name)
    home.children.link(new_coll)
    h = g.copy()
    h.name = new_coll.name
    h[GROUP_KEY] = new_coll.name
    new_coll[GROUP_KEY] = h.name
    for c in g.users_collection:
        c.objects.link(h)
    h.parent = g.parent
    h.matrix_world = g.matrix_world.copy()
    made = {g: h}
    children = [o for o in (coll.objects if coll is not None else []) if CARRIER_KEY not in o]
    for o in children:
        if is_group(o):
            sub = duplicate(context, o, linked)       # (its collection lands next to the old sub group's: moved below)
            if sub is None:
                continue
            sc = collection_of(sub)
            for pc in [c for c in bpy.data.collections if sc.name in c.children]:
                pc.children.unlink(sc)
            if sc.name in context.scene.collection.children:
                context.scene.collection.children.unlink(sc)
            new_coll.children.link(sc)
            for c in list(sub.users_collection):
                c.objects.unlink(sub)
            new_coll.objects.link(sub)
            made[o] = sub
            continue
        c = o.copy()
        if o.data is not None and not linked:
            c.data = o.data.copy()
        elif o.data is not None:                       # 0.24.84 linked: both keep the one mesh - a Cut / Decimate /
            o[LINKED_KEY] = c[LINKED_KEY] = 1          # Re-Fix on either changes it for all (commit_mesh, swap_mesh)
        c.animation_data_clear() if c.animation_data else None
        new_coll.objects.link(c)
        made[o] = c
    for o, c in made.items():                          # parents inside the copy point at the copies
        if o is g:
            continue
        if o.parent in made:
            mw = o.matrix_world.copy()
            c.parent = made[o.parent]
            c.matrix_world = mw
    for o, c in made.items():                          # modifier object links (mirror centres etc.) too
        if o is g or c.type not in {'MESH', 'CURVE'}:
            continue
        for m in c.modifiers:
            for attr in ('mirror_object', 'object', 'offset_object'):
                tgt = getattr(m, attr, None) if hasattr(m, attr) else None
                if tgt in made:
                    setattr(m, attr, made[tgt])
    if repeat_mode(g) != 'OFF':
        for k in REP_KEYS:
            if k in g:
                h[k] = g[k]
        set_repeat(context, h)
    return h


def recenter(context, g):
    """0.24.81 Origin to Geometry for a group: the handle to the middle of its parts' box (the parts stay put;
    Repetition about the handle follows).  Returns the new centre."""
    if not is_group(g):
        return None
    box = group_box(g)
    if box is None:
        return None
    centre = (box[0] + box[1]) / 2
    kids = [(o, o.matrix_world.copy()) for o in g.children]
    mw = g.matrix_world.copy()
    mw.translation = centre
    g.matrix_world = mw
    context.view_layer.update()
    for o, m in kids:
        o.matrix_world = m
    handle_look(g, box[1] - box[0])
    if repeat_mode(g) != 'OFF':
        set_repeat(context, g)
    return centre


def merge(context, g):
    """The group's meshes become one mesh (modifiers baked), still in the group."""
    meshes = [o for o in members(g) if o.type == 'MESH' and CARRIER_KEY not in o]
    if len(meshes) < 2:
        return None
    dg = context.evaluated_depsgraph_get()
    for o in meshes:
        if o.modifiers:
            me = bpy.data.meshes.new_from_object(o.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
            old = o.data
            o.modifiers.clear()
            o.data = me
            if old.users == 0:
                bpy.data.meshes.remove(old)
    first = meshes[0]
    with context.temp_override(active_object=first, object=first, selected_objects=meshes,
                               selected_editable_objects=meshes):
        bpy.ops.object.join()
    return first


def select_group(context, g):
    for o in context.selected_objects:
        o.select_set(False)
    g.select_set(True)
    context.view_layer.objects.active = g


# --- scope -------------------------------------------------------------------------------------------------

def enter_scope(context, g):
    """Work inside ``g``: everything else shows as wire and cannot be picked."""
    if not is_group(g):
        return False
    exit_scope(context)
    inside = set(members(g)) | {g}
    for o in context.scene.objects:
        if o in inside or CARRIER_KEY in o:
            continue
        o[SAVED_KEY] = json.dumps([bool(o.hide_select), o.display_type])
        o.hide_select = True
        if o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
            o.display_type = 'WIRE'
    context.scene[SCOPE_KEY] = g.name
    for o in context.selected_objects:
        o.select_set(False)
    for o in inside:
        if o.type == 'MESH':
            o.select_set(True)
            context.view_layer.objects.active = o
    return True


def exit_scope(context):
    scene = context.scene
    for o in scene.objects:
        saved = o.get(SAVED_KEY)
        if saved is None:
            continue
        try:
            hs, dt = json.loads(saved)
            o.hide_select = bool(hs)
            o.display_type = str(dt)
        except (TypeError, IndexError, ValueError):
            pass
        del o[SAVED_KEY]
    was = scene.get(SCOPE_KEY)
    if SCOPE_KEY in scene:
        del scene[SCOPE_KEY]
    g = bpy.data.objects.get(was) if was else None
    if g is not None:
        select_group(context, g)
    return was is not None


def scope(context):
    name = context.scene.get(SCOPE_KEY)
    return bpy.data.objects.get(name) if name else None


# --- repetition ----------------------------------------------------------------------------------------------

def repeat_mode(g):
    return g.get('mch_rep_mode', 'OFF') if g is not None else 'OFF'


def repeat_axes(g):
    a = g.get('mch_rep_axes', [1, 0, 0]) if g is not None else [1, 0, 0]
    return tuple(bool(v) for v in a)


def repeat_axis(g):
    return g.get('mch_rep_axis', 'Z') if g is not None else 'Z'


CENTRES = ('WORLD', 'GROUP', 'CURSOR')


def repeat_center(g):
    return g.get('mch_rep_center', 'WORLD') if g is not None else 'WORLD'


def repeat_count(g):
    return int(g.get('mch_rep_count', 6)) if g is not None else 6


def repeat_grid(g):
    a = g.get('mch_rep_grid', [3, 1, 1]) if g is not None else [3, 1, 1]
    return tuple(max(1, int(v)) for v in a)


def repeat_gap(g):
    return float(g.get('mch_rep_gap', 0.2)) if g is not None else 0.2


def group_size(g):
    """The world size (x, y, z) of the group's parts together."""
    pts = [o.matrix_world @ Vector(c) for o in members(g) if o.type in {'MESH', 'CURVE'} for c in o.bound_box]
    if not pts:
        return Vector((1.0, 1.0, 1.0))
    return Vector(tuple(max(p[i] for p in pts) - min(p[i] for p in pts) for i in range(3)))


def grid_step(g):
    size = group_size(g)
    gap = repeat_gap(g)
    return tuple(max(1e-4, size[i] * (1.0 + gap)) for i in range(3))


def copy_matrices(mode, axes=(True, False, False), axis='Z', count=6, grid=(3, 1, 1), step=(1.0, 1.0, 1.0)):
    """The copies' transforms in the handle's frame (the original itself not included)."""
    if mode == 'GRID':
        out = []
        for i in range(max(1, int(grid[0]))):
            for j in range(max(1, int(grid[1]))):
                for k in range(max(1, int(grid[2]))):
                    if i or j or k:
                        out.append(Matrix.Translation((i * step[0], j * step[1], k * step[2])))
        return out
    mirrors = [Matrix.Identity(4)]
    if mode in {'MIRROR', 'KALEIDO'}:
        for i, on in enumerate(axes):
            if not on:
                continue
            flip = Matrix.Identity(4)
            flip[i][i] = -1.0
            mirrors += [flip @ m for m in mirrors]
    rots = [Matrix.Identity(4)]
    if mode in {'RADIAL', 'KALEIDO'}:
        n = max(2, int(count))
        rots = [Matrix.Rotation(2.0 * math.pi * k / n, 4, axis) for k in range(n)]
    out = []
    for r in rots:
        for m in mirrors:
            t = r @ m
            if not _is_identity(t):
                out.append(t)
    return out


def _is_identity(m):
    return all(abs(m[i][j] - (1.0 if i == j else 0.0)) < 1e-9 for i in range(4) for j in range(4))


def _tree(g, mats):
    """Geometry Nodes: the group's collection (relative to the handle) once per copy matrix."""
    name = TREE_PREFIX + g.name
    tree = bpy.data.node_groups.get(name)
    if tree is None:
        tree = bpy.data.node_groups.new(name, 'GeometryNodeTree')
        tree.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
        tree.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    tree.nodes.clear()
    nodes, links = tree.nodes, tree.links
    out = nodes.new('NodeGroupOutput')
    out.location = (900, 0)
    nodes.new('NodeGroupInput').location = (-600, 200)
    info = nodes.new('GeometryNodeCollectionInfo')
    info.location = (-400, 0)
    info.transform_space = 'RELATIVE'
    info.inputs['Collection'].default_value = collection_of(g)
    join = nodes.new('GeometryNodeJoinGeometry')
    join.location = (600, 0)
    for i, m in enumerate(mats):
        loc, rot, scale = _decompose(m)
        t = nodes.new('GeometryNodeTransform')
        t.location = (100, -i * 160)
        t.inputs['Translation'].default_value = loc
        t.inputs['Rotation'].default_value = rot
        t.inputs['Scale'].default_value = scale
        links.new(info.outputs['Instances'], t.inputs['Geometry'])
        links.new(t.outputs['Geometry'], join.inputs['Geometry'])
    links.new(join.outputs['Geometry'], out.inputs['Geometry'])
    return tree


def _decompose(m):
    """(translation, euler, scale) with a mirror kept as a negative scale (R @ S, S = diag(+-1))."""
    m3 = m.to_3x3()
    s = Vector((1.0, 1.0, 1.0))
    if m3.determinant() < 0:
        # find the mirror axis combination: R = M @ S^-1 must be a rotation
        for sx in (1, -1):
            for sy in (1, -1):
                for sz in (1, -1):
                    S = Matrix.Diagonal((sx, sy, sz))
                    r = m3 @ S
                    if r.determinant() > 0 and _orthonormal(r):
                        return m.translation.copy(), r.to_euler(), Vector((sx, sy, sz))
    return m.translation.copy(), m3.to_euler(), s


def _orthonormal(r):
    p = r @ r.transposed()
    return all(abs(p[i][j] - (1.0 if i == j else 0.0)) < 1e-6 for i in range(3) for j in range(3))


def _place_carrier(context, g, car):
    """The copies are made in the carrier's space: at the world origin (World), at the 3D cursor (Cursor, where it
    was when picked) or following the handle (Group)."""
    where = repeat_center(g)
    if where == 'GROUP':
        if car.parent != g:
            car.parent = g
        car.matrix_parent_inverse = Matrix.Identity(4)
        car.matrix_basis = Matrix.Identity(4)
        return
    car.parent = None
    if where == 'CURSOR':
        if 'mch_rep_cursor' not in g:
            g['mch_rep_cursor'] = list(context.scene.cursor.location)
        car.matrix_world = Matrix.Translation(Vector(g['mch_rep_cursor']))
    else:
        car.matrix_world = Matrix.Identity(4)


def _mats(g):
    return copy_matrices(repeat_mode(g), repeat_axes(g), repeat_axis(g), repeat_count(g), repeat_grid(g),
                         grid_step(g))


def set_repeat(context, g, mode=None, axes=None, axis=None, count=None, center=None, grid=None, gap=None):
    """Change the group's repetition; OFF removes the copies."""
    if not is_group(g):
        return None
    if mode is not None:
        g['mch_rep_mode'] = mode
    if axes is not None:
        g['mch_rep_axes'] = [int(bool(a)) for a in axes]
    if axis is not None:
        g['mch_rep_axis'] = axis
    if count is not None:
        g['mch_rep_count'] = max(2, min(64, int(count)))
    if grid is not None:
        g['mch_rep_grid'] = [max(1, min(32, int(v))) for v in grid]
    if gap is not None:
        g['mch_rep_gap'] = max(-0.5, min(5.0, float(gap)))
    if center in CENTRES:
        g['mch_rep_center'] = center
        if center == 'CURSOR':
            g['mch_rep_cursor'] = list(context.scene.cursor.location)
    mode = repeat_mode(g)
    car = carrier_of(g)
    if mode == 'OFF':
        if car is not None:
            data = car.data
            bpy.data.objects.remove(car, do_unlink=True)
            if data is not None and data.users == 0:
                bpy.data.meshes.remove(data)
        tree = bpy.data.node_groups.get(TREE_PREFIX + g.name)
        if tree is not None:
            bpy.data.node_groups.remove(tree)
        return None
    mats = _mats(g)
    tree = _tree(g, mats)
    if car is None:
        me = bpy.data.meshes.new(g.name + ' Repetition')
        car = bpy.data.objects.new(g.name + ' Repetition', me)
        for c in g.users_collection:
            c.objects.link(car)
        car[CARRIER_KEY] = g.name
        car.hide_select = True
    _place_carrier(context, g, car)
    mod = car.modifiers.get(MOD_NAME) or car.modifiers.new(MOD_NAME, 'NODES')
    mod.node_group = tree
    return car


def make_real(context, g):
    """Apply: every copy becomes real objects (linked mesh data), the repetition is switched off."""
    if not is_group(g) or repeat_mode(g) == 'OFF':
        return 0
    coll = collection_of(g)
    car = carrier_of(g)
    context.view_layer.update()
    gm = car.matrix_world.copy() if car is not None else g.matrix_world.copy()     # the copies' frame
    gi = gm.inverted_safe()
    mats = _mats(g)
    made = 0
    sources = [o for o in members(g) if o.type in {'MESH', 'CURVE'} and not is_group(o)]
    for i, m in enumerate(mats):
        world = gm @ m @ gi
        for o in sources:
            c = o.copy()
            c.parent = None
            c.matrix_world = world @ o.matrix_world
            coll.objects.link(c)
            mw = c.matrix_world.copy()
            c.parent = g
            c.matrix_world = mw
            made += 1
    set_repeat(context, g, mode='OFF')
    return made


# --- operators ------------------------------------------------------------------------------------------------

class MCH_OT_group(bpy.types.Operator):
    """Group the selected parts (one handle moves them all; Repetition, Enter / Exit in the Mecha Menu)"""
    bl_idname = 'mch.group'
    bl_label = 'Group'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def execute(self, context):
        g = create(context, list(context.selected_objects))
        if g is None:
            return {'CANCELLED'}
        self.report({'INFO'}, f'{g.name}: {len(members(g))} objects grouped')
        return {'FINISHED'}


class MCH_OT_group_action(bpy.types.Operator):
    """Ungroup / Merge / Enter / Exit / Select the group of the active object"""
    bl_idname = 'mch.group_action'
    bl_label = 'Group Action'
    bl_options = {'REGISTER', 'UNDO'}
    action: bpy.props.EnumProperty(items=[
        ('UNGROUP', 'Ungroup', 'The parts go back where they were'),
        ('MERGE', 'Merge', 'The group\'s meshes become one mesh'),
        ('ENTER', 'Enter', 'Work inside the group; the rest is wire and cannot be picked'),
        ('EXIT', 'Exit', 'Back out of the group'),
        ('SELECT', 'Select Group', 'Select the group handle (its Repetition card shows)'),
        ('ORIGIN', 'Origin to Geometry', 'The group handle to the middle of its parts (the parts stay put)')],
        default='SELECT')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT'

    def execute(self, context):
        if self.action == 'EXIT':
            if not exit_scope(context):
                return {'CANCELLED'}
            return {'FINISHED'}
        g = group_of(context.active_object) or scope(context)
        if g is None:
            self.report({'WARNING'}, 'Not in a group')
            return {'CANCELLED'}
        if self.action == 'UNGROUP':
            n = ungroup(context, g)
            self.report({'INFO'}, f'Ungrouped {n} objects')
        elif self.action == 'MERGE':
            if merge(context, g) is None:
                self.report({'WARNING'}, 'A group needs two or more meshes to merge')
                return {'CANCELLED'}
        elif self.action == 'ENTER':
            enter_scope(context, g)
        elif self.action == 'ORIGIN':
            if recenter(context, g) is None:
                self.report({'WARNING'}, 'The group has no visible parts')
                return {'CANCELLED'}
            self.report({'INFO'}, f'{g.name}: origin to the middle of its parts')
        else:
            select_group(context, g)
        return {'FINISHED'}


class MCH_OT_duplicate(bpy.types.Operator):
    """Duplicate the selection and move it (a group handle: the whole group - parts, nested groups, repetition)"""
    bl_idname = 'mch.duplicate'
    bl_label = 'Duplicate'
    bl_options = {'REGISTER', 'UNDO'}
    linked: bpy.props.BoolProperty(name='Linked', default=False, description='Copies share the mesh (Alt+D)',
                                   options={'SKIP_SAVE'})      # 0.24.85 (the Linked Copy button must not make Shift+D linked)
    move: bpy.props.BoolProperty(name='Move', default=True, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        # (anywhere: plain objects get Blender's duplicate + grab from it, so the key loses nothing outside MECHA LAB)
        return context.mode == 'OBJECT' and bool(context.selected_objects)

    def invoke(self, context, event):
        return self.execute(context)

    def execute(self, context):
        sel = list(context.selected_objects)
        handles = [o for o in sel if is_group(o)]
        inside = {o for g in handles for o in members(g)}
        rest = [o for o in sel if o not in handles and o not in inside and CARRIER_KEY not in o]
        new = []
        for g in handles:
            h = duplicate(context, g, self.linked)
            if h is not None:
                new.append(h)
        if rest:
            for o in sel:
                o.select_set(False)
            for o in rest:
                o.select_set(True)
            context.view_layer.objects.active = rest[0]
            with context.temp_override(selected_objects=rest, selected_editable_objects=rest, active_object=rest[0]):
                bpy.ops.object.duplicate(linked=self.linked)
            new += [o for o in context.selected_objects if o not in sel]
        if not new:
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in new:
            o.select_set(True)
        context.view_layer.objects.active = new[0]
        if handles:
            self.report({'INFO'}, f'Duplicated {len(handles)} group(s)' + (f' + {len(rest)} object(s)' if rest else ''))
        if self.move and context.region is not None and context.region.type == 'WINDOW':
            bpy.ops.transform.translate('INVOKE_DEFAULT')
        return {'FINISHED'}


class MCH_OT_group_repeat(bpy.types.Operator):
    """Repetition of the active group: Off / Mirror / Radial / Kaleido (linked copies, non-destructive)"""
    bl_idname = 'mch.group_repeat'
    bl_label = 'Group Repetition'
    bl_options = {'REGISTER', 'UNDO'}
    mode: bpy.props.EnumProperty(items=[(m, m.title(), '') for m in ('OFF', 'MIRROR', 'RADIAL', 'KALEIDO', 'GRID')],
                                 default='MIRROR')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and group_of(context.active_object) is not None

    def execute(self, context):
        g = group_of(context.active_object)
        set_repeat(context, g, mode=self.mode)
        select_group(context, g)
        context.window_manager.mch_sym_card = g.name
        return {'FINISHED'}


class MCH_OT_group_box_eye(bpy.types.Operator):
    """Show / hide this group's box lines in the viewport (a selected group always shows them)"""
    bl_idname = 'mch.group_box_eye'
    bl_label = 'Group Box Lines'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: bpy.props.StringProperty()

    def execute(self, context):
        g = bpy.data.objects.get(self.name)
        if g is None or not is_group(g):
            return {'CANCELLED'}
        if g.get(BOX_HIDDEN_KEY):
            del g[BOX_HIDDEN_KEY]
        else:
            g[BOX_HIDDEN_KEY] = 1
        for area in context.screen.areas if context.screen else []:
            area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_group_pick(bpy.types.Operator):
    """Select this group (its Repetition card shows); with Enter: work inside it"""
    bl_idname = 'mch.group_pick'
    bl_label = 'Pick Group'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    name: bpy.props.StringProperty()
    enter: bpy.props.BoolProperty(default=False)

    def execute(self, context):
        g = bpy.data.objects.get(self.name)
        if not is_group(g) or context.mode != 'OBJECT':
            return {'CANCELLED'}
        if self.enter:
            enter_scope(context, g)
        else:
            exit_scope(context)
            select_group(context, g)
        return {'FINISHED'}


def all_groups(context):
    """The scene's groups, outer ones first (each with its depth)."""
    out = []

    def walk(g, depth):
        out.append((g, depth))
        for c in sorted((o for o in g.children if is_group(o)), key=lambda o: o.name):
            walk(c, depth + 1)
    for g in sorted((o for o in context.scene.objects if is_group(o) and group_of(o.parent) is None),
                    key=lambda o: o.name):
        walk(g, 0)
    return out


def draw_list(layout, context):
    """0.24.55 the group list (sidebar): pick, enter, what repeats."""
    rows = all_groups(context)
    inside = scope(context)
    if not rows:
        layout.label(text='No groups yet (Mecha Menu > Groups > Group)', icon='INFO')
        return
    if inside is not None:
        layout.operator('mch.group_action', text=f'Exit {inside.name}', icon='LOOP_BACK').action = 'EXIT'
    g = group_of(context.active_object)
    if g is not None:
        row = layout.row(align=True)
        row.operator('mch.duplicate', text='Duplicate', icon='DUPLICATE')
        row.operator('mch.duplicate', text='Linked Copy', icon='LINKED').linked = True      # 0.24.85
        row.operator('mch.group_action', text='Origin to Geometry', icon='PIVOT_MEDIAN').action = 'ORIGIN'
    col = layout.column(align=True)
    for g, depth in rows:
        row = col.row(align=True)
        if depth:
            row.label(text='', icon='BLANK1')
        sel = context.active_object == g
        op = row.operator('mch.group_pick', text=g.name, icon='GROUP', depress=sel)
        op.name, op.enter = g.name, False
        mode = repeat_mode(g)
        row.label(text='' if mode == 'OFF' else mode.title())
        row.operator('mch.group_box_eye', text='', icon='MESH_CUBE' if not g.get(BOX_HIDDEN_KEY) else 'CUBE',
                     depress=not g.get(BOX_HIDDEN_KEY)).name = g.name                          # 0.24.84 box lines
        op = row.operator('mch.group_pick', text='', icon='FORWARD' if inside != g else 'CHECKMARK')
        op.name, op.enter = g.name, True


class MCH_PT_groups(bpy.types.Panel):
    bl_idname = 'MCH_PT_groups'
    bl_label = 'Groups'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 76
    bl_options = {'DEFAULT_CLOSED'}

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        try:
            return ts.sidebar_select(context)
        except (AttributeError, KeyError):
            return True

    def draw(self, context):
        draw_list(self.layout, context)


CLASSES = (MCH_OT_group, MCH_OT_group_action, MCH_OT_duplicate, MCH_OT_group_repeat, MCH_OT_group_box_eye,
           MCH_OT_group_pick, MCH_PT_groups)


def register():
    global _box_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)
    if not bpy.app.background and _box_handle is None:
        _box_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_boxes, (), 'WINDOW', 'POST_VIEW')
        bpy.app.timers.register(_on_load, first_interval=0.5)


def unregister():
    global _box_handle
    if _box_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_box_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _box_handle = None
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
