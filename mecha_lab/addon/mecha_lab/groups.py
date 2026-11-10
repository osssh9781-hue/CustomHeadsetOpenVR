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
SCOPE_PATH_KEY = 'mch_scope_path'        # 0.24.101 path of nested group names, outermost first
ADOPTED_KEY = 'mch_group_adopted'        # 0.24.95 on a collection: the user's own, made a group in place (Ungroup
#                                          keeps it; its parts never moved collection)
SAVED_KEY = 'mch_scope_saved'            # on other objects while in a group: [hide_select, display_type, viewport_hidden]
COLLAPSE_KEY = 'mch_group_collapsed'
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


def parent_collection(context, coll):
    """The collection ``coll`` sits in (the scene's own collection at the top)."""
    def walk(c):
        for ch in c.children:
            if ch == coll:
                return c
            r = walk(ch)
            if r is not None:
                return r
        return None
    return walk(context.scene.collection) or context.scene.collection


def adopt(context, coll):
    """0.24.95 (user: "콜렉션도 오리진 이랑 미러 되게") the user's collection made a group in place: a handle at the
    middle of its parts (in the collection's parent), its top parts parented to it - the parts stay in the collection.
    Then Origin / Mirror / Enter work on it as on any group.  Returns the handle (the one it has if it is a group)."""
    if coll is None:
        return None
    g = bpy.data.objects.get(coll.get(GROUP_KEY, '') or '')
    if is_group(g) and collection_of(g) == coll:
        return g
    objs = [o for o in coll.all_objects if CARRIER_KEY not in o and not is_group(o)]
    if not objs:
        return None
    parent_coll = parent_collection(context, coll)
    centre, size = _world_box(objs)
    g = bpy.data.objects.new(coll.name, None)
    handle_look(g, size)
    g.show_in_front = True
    parent_coll.objects.link(g)
    g.matrix_world = Matrix.Translation(centre)
    g[GROUP_KEY] = coll.name
    coll[GROUP_KEY] = g.name
    coll[ADOPTED_KEY] = True
    inside = set(coll.all_objects)              # (its sub-collections' parts too: they move with the handle)
    for o in coll.all_objects:
        if CARRIER_KEY in o or o == g:
            continue
        if o.parent is None or o.parent not in inside:
            mw = o.matrix_world.copy()
            o.parent = g
            o.matrix_world = mw
    adopt_pivots(context, g)
    return g


def rename(context, g, new):
    """0.24.95 (user: "레이어 이름도 바꿀 수 있게") a group renamed: its handle, its collection (unless it is the
    user's own collection made a group - that keeps the name given here too), its repetition.  Returns the name."""
    old = g.name
    coll = collection_of(g)
    g.name = new
    name = g.name
    if coll is not None:
        coll.name = name
        g[GROUP_KEY] = coll.name
        coll[GROUP_KEY] = name
    for o in bpy.data.objects:
        if o.get(CARRIER_KEY) == old:
            o[CARRIER_KEY] = name
            o.name = name + ' Repetition'
    tree = bpy.data.node_groups.get(TREE_PREFIX + old)
    if tree is not None:
        tree.name = TREE_PREFIX + name
    if context.scene.get(SCOPE_KEY) == old:
        context.scene[SCOPE_KEY] = name
    if SCOPE_PATH_KEY in context.scene:
        try:
            path = json.loads(context.scene[SCOPE_PATH_KEY])
            context.scene[SCOPE_PATH_KEY] = json.dumps([name if x == old else x for x in path])
        except (ValueError, TypeError):
            pass
    return name


HANDLE_SIZE = 0.002        # 0.24.107 the handle Empty is not shown (user: "Empty / group box hidden"); the group shows
#                            as a green outline round its parts when selected (group_outline.py)


def handle_look(g, size=None):
    """0.24.58 The handle: a small cross at the centre - 0.24.107 so small it is not seen; clicking any of the
    group's parts picks the group, and the selected group shows a green outline (``group_outline``)."""
    g.empty_display_type = 'PLAIN_AXES'
    g.empty_display_size = HANDLE_SIZE


def tidy_handles(scene=None):
    """Groups made before 0.24.58 (a big cube) or 0.24.107 (a visible cross) get the hidden handle."""
    for g in [o for o in bpy.data.objects if is_group(o) and o.library is None and
              (o.empty_display_type != 'PLAIN_AXES' or o.empty_display_size > HANDLE_SIZE * 1.5)]:
        try:
            handle_look(g)
        except (AttributeError, RuntimeError):
            pass


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


def boxes_on(context):
    """0.24.87 the scene-wide switch for every group's box lines (Layers panel head / Groups card)."""
    st = getattr(getattr(context, 'scene', None), 'mch_settings', None)
    return st is None or bool(st.group_boxes)


def _draw_boxes():
    try:
        context = bpy.context
        if not boxes_on(context):
            return
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
    """After a file opens: small handles, the auto-add watcher starts from the file's objects (none of them is
    "new"), a scope whose group is gone is undone, and the watcher / click keys run (0.24.107: their timers were
    dropped when Blender started with a file, so group clicks never worked in that session)."""
    try:
        tidy_handles()
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    _seen_scene_objects.clear()
    _pending.clear()
    _reseed_all()
    try:
        ctx = bpy.context
        if getattr(ctx, 'scene', None) is not None:
            ensure_scope(ctx, leftovers=True)
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    _start_timers()
    return None


@bpy.app.handlers.persistent
def _on_undo(_dummy=None):
    """Undo / redo: the restored objects are not new parts; a scope left half-way by the step is set right."""
    _pending.clear()
    _reseed_all()
    try:
        ctx = bpy.context
        if getattr(ctx, 'scene', None) is not None:
            ensure_scope(ctx, leftovers=True)
    except (AttributeError, ReferenceError, RuntimeError):
        pass


@bpy.app.handlers.persistent
def _on_import(_dummy=None):
    """Append / Link: what came in is not a new part made inside the group."""
    _pending.clear()
    _reseed_all()


def _tidy_later():
    try:
        tidy_handles()
    except (AttributeError, ReferenceError, RuntimeError):
        pass
    return None


def _start_timers():
    if not _auto_timer_live:
        return
    try:
        if not bpy.app.timers.is_registered(_auto_group_tick):
            bpy.app.timers.register(_auto_group_tick, first_interval=0.45, persistent=True)
        if not _group_keymaps and not bpy.app.background and not bpy.app.timers.is_registered(_register_group_keymaps):
            bpy.app.timers.register(_register_group_keymaps, first_interval=0.2, persistent=True)
    except (AttributeError, RuntimeError, ValueError):
        pass


def ungroup(context, g):
    """Parts back where they were; the handle, its collection and any repetition go."""
    if not is_group(g):
        return 0
    set_repeat(context, g, mode='OFF')
    coll = collection_of(g)
    home = next(iter(g.users_collection), context.scene.collection)
    n = 0
    if coll is not None and coll.get(ADOPTED_KEY):      # (0.24.95 the user's own collection: it stays, as it was)
        for o in list(coll.all_objects):
            if o.parent == g:
                mw = o.matrix_world.copy()
                o.parent = g.parent
                o.matrix_world = mw
                n += 1
        for k in (GROUP_KEY, ADOPTED_KEY):
            if k in coll:
                del coll[k]
        if context.scene.get(SCOPE_KEY) == g.name or g.name in scope_path(context):
            clear_scope(context)
        _release_pivots(g)
        bpy.data.objects.remove(g, do_unlink=True)
        return n
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
    if context.scene.get(SCOPE_KEY) == g.name or g.name in scope_path(context):
        clear_scope(context)
    _release_pivots(g)
    bpy.data.objects.remove(g, do_unlink=True)
    return n


REP_KEYS = ('mch_rep_mode', 'mch_rep_axes', 'mch_rep_axis', 'mch_rep_count', 'mch_rep_center', 'mch_rep_cursor',
            'mch_rep_grid', 'mch_rep_gap')


def duplicate(context, g, linked=False, _made=None):
    """0.24.81 A copy of the whole group (Shift+D on a group handle copied the handle alone): a new collection next
    to the group's, a new handle, every part copied (``linked``: sharing the mesh, Alt+D style) at the same place
    under it, nested groups and the symmetry centres too, the repetition set up again.  Returns the new handle."""
    if not is_group(g):
        return None
    root_call = _made is None
    if _made is None:
        _made = {}
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
    made = _made
    made[g] = h
    children = [o for o in (coll.objects if coll is not None else []) if CARRIER_KEY not in o]
    # World-mirror pivots are often parented to the group handle but linked
    # only to Scene Collection; coll.objects misses them. Copy these helpers
    # ONCE, then remap all nested modifier references using the shared map.
    helpers = []
    for part in members(g):
        if part.type != 'MESH':
            continue
        for mod in part.modifiers:
            if mod.type != 'MIRROR':
                continue
            pivot = mod.mirror_object
            if pivot is not None and pivot.type == 'EMPTY' and not is_group(pivot) and \
                    (pivot.parent == g or (root_call and pivot.parent is None and pivot.get('_mch_world_pivot'))) and \
                    pivot not in children and pivot not in made and pivot not in helpers:
                helpers.append(pivot)
    children.extend(helpers)
    helper_set = set(helpers)
    for o in children:
        if is_group(o):
            sub = duplicate(context, o, linked, made)
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
            car = carrier_of(sub)              # 0.24.107 its repetition object moves along (it stayed in the
            if car is not None:                #  original group, which then showed the copy's copies too)
                for c in list(car.users_collection):
                    c.objects.unlink(car)
                new_coll.objects.link(car)
            made[o] = sub
            continue
        c = o.copy()
        if o.data is not None and not linked:
            c.data = o.data.copy()
        elif o.data is not None:                       # 0.24.84 linked: both keep the one mesh - a Cut / Decimate /
            o[LINKED_KEY] = c[LINKED_KEY] = 1          # Re-Fix on either changes it for all (commit_mesh, swap_mesh)
        c.animation_data_clear() if c.animation_data else None
        if o in helper_set:            # 0.24.107 a symmetry centre: next to the original's (not into the group)
            homes = [new_coll if col == coll else col for col in o.users_collection] or [context.scene.collection]
            for col in homes:
                if c.name not in col.objects:
                    col.objects.link(c)
        else:
            new_coll.objects.link(c)
        made[o] = c
    if root_call:
        # Restore each source's world transform after replacing old parent links.
        for source, copied in made.items():
            if source.parent in made:
                world = source.matrix_world.copy()
                copied.parent = made[source.parent]
                copied.matrix_world = world
            elif source in helper_set and source.parent is None:
                world = source.matrix_world.copy()     # 0.24.107 a world centre's copy follows the new group
                copied.parent = h
                copied.matrix_world = world
        for source, copied in made.items():
            if copied.type not in {'MESH', 'CURVE'}:
                continue
            for mod in copied.modifiers:
                for attr in ('mirror_object', 'object', 'offset_object'):
                    try:
                        target = getattr(mod, attr, None)
                        if target in made:
                            setattr(mod, attr, made[target])
                    except (AttributeError, ReferenceError, TypeError, ValueError):
                        pass
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
    handle_to(context, g, centre)
    handle_look(g, box[1] - box[0])
    return centre


def handle_to(context, g, loc):
    """The handle moved to ``loc`` (world), its parts staying where they are (0.24.95 also Origin to 3D Cursor)."""
    kids = [(o, o.matrix_world.copy()) for o in g.children]
    mw = g.matrix_world.copy()
    mw.translation = Vector(loc)
    g.matrix_world = mw
    context.view_layer.update()
    for o, m in kids:
        o.matrix_world = m
    if repeat_mode(g) != 'OFF':
        set_repeat(context, g)
    return g.matrix_world.translation.copy()


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

def scope_path(context):
    """Existing handles from the scene's saved outer-to-inner edit path."""
    scene = context.scene
    try:
        names = json.loads(scene.get(SCOPE_PATH_KEY, '[]'))
        if not isinstance(names, list):
            names = []
    except (ValueError, TypeError):
        names = []
    if not names and scene.get(SCOPE_KEY):
        names = [scene[SCOPE_KEY]]  # old scenes before nested scope
    return [n for n in names if is_group(bpy.data.objects.get(n))]


def _parents_of(g):
    """Path through actual parent handles; nesting Collection alone is insufficient."""
    chain, seen = [], set()
    while is_group(g) and g.name not in seen:
        seen.add(g.name)
        chain.append(g)
        g = group_of(g.parent)
    return list(reversed(chain))


def _hide(o, state, view_layer=None):
    """``o.hide_set`` that never raises (0.24.107: an object outside the view layer - in an excluded collection -
    raised RuntimeError there and left the scene stuck half inside a group)."""
    try:
        if view_layer is not None:
            o.hide_set(bool(state), view_layer=view_layer)
        else:
            o.hide_set(bool(state))
        return True
    except (RuntimeError, ReferenceError, TypeError):
        return False


def _hidden(o):
    try:
        return bool(o.hide_get())
    except (RuntimeError, ReferenceError):
        return False


def _restore_scope_objects(context):
    """Every object the scope changed gets its pick flag, display and hidden state back.  0.24.107: per object,
    nothing can stop the loop half way (a linked object, one outside the view layer)."""
    for o in list(context.scene.objects):
        try:
            saved = o.get(SAVED_KEY)
        except (ReferenceError, TypeError):
            continue
        if saved is None:
            continue
        try:
            entry = json.loads(saved)
            hs, dt = entry[:2]
            o.hide_select = bool(hs)
            o.display_type = str(dt)
            if len(entry) >= 3:
                _hide(o, entry[2], context.view_layer)
        except (TypeError, IndexError, ValueError, AttributeError, RuntimeError):
            pass
        try:
            del o[SAVED_KEY]
        except (KeyError, TypeError, AttributeError, RuntimeError):
            pass


def _show_scope(context, g):
    """Apply visual isolation without altering the saved scope navigation path."""
    _restore_scope_objects(context)
    inside = set(members(g)) | {g}
    view_mode = getattr(context.scene, 'mch_group_scope_display', 'WIRE')
    vl = context.view_layer
    for o in context.scene.objects:
        if o in inside or CARRIER_KEY in o or o.library is not None:
            continue
        try:
            o[SAVED_KEY] = json.dumps([bool(o.hide_select), o.display_type, _hidden(o)])
            o.hide_select = True
            if view_mode == 'HIDDEN':
                _hide(o, True, vl)
            elif view_mode == 'WIRE' and o.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'}:
                o.display_type = 'WIRE'
        except (AttributeError, RuntimeError, TypeError):
            continue
    # Do not select *all* meshes: that makes moving one part move everything.
    for o in list(context.selected_objects):
        o.select_set(False)
    context.view_layer.objects.active = None


def _scope_display_update(self, context):
    current = scope(context)
    if current is not None:
        _show_scope(context, current)


def enter_scope(context, g):
    """Enter a group, including nested groups, without losing the parent scope."""
    if not is_group(g):
        return False
    path = [ob.name for ob in _parents_of(g)]
    if not path:
        return False
    _show_scope(context, g)
    context.scene[SCOPE_KEY] = g.name
    context.scene[SCOPE_PATH_KEY] = json.dumps(path)
    # Remember the object baseline *before* new meshes are created.
    _remember_scene(context.scene)
    return True


def clear_scope(context, select=True):
    """Leave every scope level and restore the original display and pick flags."""
    scene = context.scene
    path = scope_path(context)
    was = scene.get(SCOPE_KEY)
    _restore_scope_objects(context)
    for key in (SCOPE_KEY, SCOPE_PATH_KEY):
        if key in scene:
            del scene[key]
    g = bpy.data.objects.get(path[0] if path else was) if (path or was) else None
    if select and is_group(g):
        try:
            select_group(context, g)
        except (RuntimeError, ReferenceError):
            pass
    return bool(path or was)


def ensure_scope(context, leftovers=False):
    """0.24.107 The saved scope must make sense: its group still exists and its path ends at it (a deleted or
    renamed handle, a file from another version) - otherwise everything is restored instead of staying ghosted and
    unpickable.  ``leftovers``: also give objects back their look when no scope is set but some still carry the
    saved state (after an undo / a file load).  Returns the current scope handle or None."""
    scene = context.scene
    if scene is None:
        return None
    name = scene.get(SCOPE_KEY)
    if name:
        g = bpy.data.objects.get(name)
        path = scope_path(context)
        if not is_group(g) or not path or path[-1] != name:
            if is_group(g):                   # the path lost a step: rebuild it from the parents
                full = [o.name for o in _parents_of(g)]
                scene[SCOPE_PATH_KEY] = json.dumps(full)
                return g
            clear_scope(context, select=False)
            return None
        return g
    if leftovers and any(SAVED_KEY in o for o in scene.objects):
        _restore_scope_objects(context)
    return None


def exit_scope(context):
    """Step out of one nested scope, or restore the scene at the outermost level."""
    path = scope_path(context)
    if len(path) <= 1:
        return clear_scope(context)
    parent = bpy.data.objects.get(path[-2])
    if not is_group(parent):
        return clear_scope(context)
    _show_scope(context, parent)
    context.scene[SCOPE_KEY] = parent.name
    context.scene[SCOPE_PATH_KEY] = json.dumps(path[:-1])
    child = bpy.data.objects.get(path[-1])
    if is_group(child) and not child.hide_select:
        select_group(context, child)
    return True


def scope(context):
    name = context.scene.get(SCOPE_KEY)
    return bpy.data.objects.get(name) if name else None


# --- one click = whole group, double click = enter group ------------------------------------

def _focus_group(ob, current):
    """Out of scope: outermost group. Inside: immediate child group of this scope."""
    g = group_of(ob)
    if g is None:
        return None
    path = _parents_of(g)
    if current is None:
        return path[0] if path else None
    if g == current:
        return None  # a direct member in this scope stays individually selectable
    for idx, parent in enumerate(path):
        if parent == current and idx + 1 < len(path):
            return path[idx + 1]
    return None


def _pick_visible_mesh(context, event):
    """Ray-cast the geometry under this click: never require the group Empty.

    In Blender a CLICK/DOUBLE_CLICK keymap may run before or after native
    selection, so context.active_object can still belong to the previous click.
    Ray casting makes the first click deterministic.
    0.24.107: helpers (cutters, previews, wire / bounds guides) are stepped past like unpickable parts.
    """
    try:
        from bpy_extras import view3d_utils
        region = context.region
        rv3d = context.region_data
        if region is None or rv3d is None or region.type != 'WINDOW':
            return None
        xy = (event.mouse_region_x, event.mouse_region_y)
        origin = view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
        direction = view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)
        dg = context.evaluated_depsgraph_get()
        # A non-selectable overlay may be intersected first: step past it.
        for _ in range(24):
            hit, location, _normal, _index, evaluated, _matrix = context.scene.ray_cast(
                dg, origin, direction)
            if not hit or evaluated is None:
                return None
            ob = getattr(evaluated, 'original', None) or bpy.data.objects.get(evaluated.name)
            if ob is not None and ob.type in {'MESH', 'CURVE', 'SURFACE', 'FONT'} and \
                    not ob.hide_select and not _hidden(ob) and ob.visible_get(view_layer=context.view_layer) \
                    and not _is_helper(ob):
                return ob
            origin = location + direction * 0.001
    except (AttributeError, ReferenceError, RuntimeError, TypeError, ValueError):
        pass
    return None


_last_click = {'t': -10.0, 'hit': None, 'xy': (0, 0)}
DOUBLE_GAP = 0.6           # seconds: a double-click counts only on what the first click of the pair hit
DOUBLE_SLOP = 12           # pixels


def _same_pair(hit, xy):
    """The double-click's first click hit the same part (or empty space) as this one.  When this operator did not see
    the first click at all (another handler took it, e.g. a press that started a tiny drag), Blender's own
    double-click test stands: it already needs both presses at the same spot, quickly."""
    import time
    last = _last_click
    if time.monotonic() - last['t'] > DOUBLE_GAP:
        return True
    if abs(xy[0] - last['xy'][0]) > DOUBLE_SLOP or abs(xy[1] - last['xy'][1]) > DOUBLE_SLOP:
        return False
    return last['hit'] == (hit.name if hit is not None else None)


def _note_click(hit, xy):
    import time
    _last_click.update(t=time.monotonic(), hit=hit.name if hit is not None else None, xy=tuple(xy))


class MCH_OT_group_view_pick(bpy.types.Operator):
    """In Mecha Select mode: click a part to select its group, double-click to edit inside, double-click empty
    space to step out of the group"""
    bl_idname = 'mch.group_view_pick'
    bl_label = 'Group Focus (Viewport)'
    bl_options = {'INTERNAL', 'UNDO'}
    enter: bpy.props.BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        if context.mode != 'OBJECT' or not context.scene or not context.area or context.area.type != 'VIEW_3D':
            return False
        try:
            from . import bottom_bar
            return bool(getattr(context.scene, 'mch_group_focus_enabled', True)
                        and bottom_bar.in_select(context))
        except (AttributeError, RuntimeError, ImportError):
            return False

    def invoke(self, context, event):
        if event.shift or event.ctrl or event.alt or context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        # Do not intercept clicks on the custom viewport HUD / Layers panel.
        try:
            from . import layers_panel
            if layers_panel.over(context, event.mouse_region_x, event.mouse_region_y):
                return {'PASS_THROUGH'}
        except (AttributeError, RuntimeError, TypeError, ImportError):
            pass
        xy = (event.mouse_region_x, event.mouse_region_y)
        hit = _pick_visible_mesh(context, event)
        current = ensure_scope(context)
        if not self.enter:
            _note_click(hit, xy)
        if hit is None:
            if self.enter and current is not None and _same_pair(None, xy):
                exit_scope(context)          # double-click on empty space: one level out
                _note_click(None, (-9999, -9999))
                return {'FINISHED'}
            return {'PASS_THROUGH'}  # Blender handles clicking empty space (a single click deselects).
        focus = _focus_group(hit, current)
        if self.enter:
            if focus is None or not _same_pair(hit, xy):
                return {'PASS_THROUGH'}  # A direct part inside Scope edits like a normal object.
            if enter_scope(context, focus):
                _note_click(None, (-9999, -9999))
                return {'FINISHED'}
            return {'PASS_THROUGH'}
        if focus is None:
            # In the current Scope, direct parts are the click targets.
            # Do not fall through to Blender's Empty/handle picker.
            if current is not None and group_of(hit) == current:
                for ob in list(context.selected_objects):
                    ob.select_set(False)
                hit.select_set(True)
                context.view_layer.objects.active = hit
                return {'FINISHED'}
            return {'PASS_THROUGH'}
        select_group(context, focus)
        return {'FINISHED'}


# --- automatic membership of new meshes created during a scope -------------------------------
# Polling only handles NEW objects; existing models, imported resources and other groups
# are never silently reparented. This avoids updating Blender data inside a depsgraph handler.
# 0.24.107: objects are known by ``session_uid`` (it stays the same over undo / redo, a pointer does not) per scene
# name; a new object joins only once it has stayed still for one tick with no modal operator running (Shift+A then G
# no longer gets its parent changed half way through the move), and never a helper (cutter, preview, wire / bounds
# display, unpickable, linked) or an object brought in by Append / Link.
_seen_scene_objects = {}      # scene name -> {uid}
_pending = {}                 # scene name -> {uid: signature or None}
_auto_timer_live = False
_group_keymaps = []
_IDLE_MODALS = set()          # modal operators that run all the time and do not mean "the user is busy"


def _uid(o):
    try:
        return o.session_uid
    except (AttributeError, ReferenceError):
        return o.as_pointer()


def _remember_scene(scene):
    if scene is not None:
        _seen_scene_objects[scene.name] = {_uid(o) for o in scene.objects}
        _pending.pop(scene.name, None)


def _reseed_all():
    try:
        for sc in bpy.data.scenes:
            _remember_scene(sc)
    except (AttributeError, ReferenceError, RuntimeError):
        pass


def _is_helper(o):
    """Cutters, previews, carriers, wire / bounds guides: never group members, never click targets."""
    try:
        if o.get(CARRIER_KEY) or o.get('mch_cut_carrier') or o.get('mch_preview_source') or o.get('mch_array_copy') \
                or o.get('mch_path') or o.get('mch_profile_file') or o.get('mch_perf_cutter'):
            return True
        if o.display_type in {'WIRE', 'BOUNDS'}:
            return True
        return o.name.startswith(('MCH_Cutter', 'MCH_GapIn', 'MCH_GapOut', 'MCH_Preview'))
    except (AttributeError, ReferenceError, TypeError):
        return True


def _auto_candidate(o, g):
    if o.type not in {'MESH', 'CURVE', 'SURFACE', 'FONT'} or o.parent is not None:
        return False
    if is_group(o) or CARRIER_KEY in o or group_of(o) is not None:
        return False
    if o.library is not None or o.override_library is not None or (o.data is not None and o.data.library is not None):
        return False  # linked from another file
    if o.hide_viewport or o.hide_render or _hidden(o) or o.hide_select or SAVED_KEY in o:
        return False  # hidden, or a ghosted outside part
    if _is_helper(o):
        return False  # construction paths, cutters, previews, profile library resources
    destination = collection_of(g)
    if any(c.get(GROUP_KEY) for c in o.users_collection if c != destination):
        return False  # already housed in another group (including duplicates)
    return bool(o.users_collection)


def put_in_scope(context, o, g=None):
    """Safely move an independent, visible newly created part into the current scope."""
    g = g if g is not None else scope(context)
    coll = collection_of(g) if is_group(g) else None
    if coll is None or not _auto_candidate(o, g):
        return False
    # FROM_KEY makes Ungroup restore the exact original collection membership.
    old = [c.name for c in o.users_collection]
    world = o.matrix_world.copy()
    o[FROM_KEY] = json.dumps(old)
    if coll not in o.users_collection:
        coll.objects.link(o)
    for c in list(o.users_collection):
        if c != coll:
            c.objects.unlink(o)
    o.parent = g
    o.matrix_world = world
    return True


def _busy(ctx):
    """A modal operator is running somewhere (a move after Shift+A, a tool drawing): new objects wait."""
    try:
        for w in ctx.window_manager.windows:
            for op in getattr(w, 'modal_operators', ()):
                if op.bl_idname not in _IDLE_MODALS:
                    return True
    except (AttributeError, ReferenceError, RuntimeError, TypeError):
        return False
    return False


def _signature(o):
    try:
        return (tuple(round(v, 6) for row in o.matrix_world for v in row), o.parent, o.data)
    except (AttributeError, ReferenceError):
        return None


def auto_group_step(ctx):
    """One pass of the auto-add watcher (the timer calls it; tests call it directly).  Returns the objects added."""
    scene = ctx.scene
    if scene is None:
        return []
    key = scene.name
    if scene.get(SCOPE_KEY):
        ensure_scope(ctx)
    objs = {_uid(o): o for o in scene.objects}
    old = _seen_scene_objects.get(key)
    _seen_scene_objects[key] = set(objs)
    pend = _pending.setdefault(key, {})
    if old is None:
        pend.clear()
        return []
    for u in [u for u in pend if u not in objs]:
        del pend[u]
    g = scope(ctx)
    if not (is_group(g) and collection_of(g) is not None and ctx.mode == 'OBJECT'
            and getattr(scene, 'mch_group_auto_add', True)):
        pend.clear()
        return []
    for u in objs.keys() - old:
        pend[u] = None
    if not pend:
        return []
    if _busy(ctx):
        for u in pend:
            pend[u] = None           # still being made / moved: wait for one quiet tick after it ends
        return []
    added = []
    for u, sig in list(pend.items()):
        o = objs[u]
        now = _signature(o)
        if sig is None or sig != now:
            pend[u] = now            # first quiet look, or it moved: look again next tick
            continue
        del pend[u]
        try:
            if put_in_scope(ctx, o, g):
                added.append(o)
        except (ReferenceError, RuntimeError, ValueError, TypeError):
            pass
    return added


def _auto_group_tick():
    if not _auto_timer_live:
        return None
    try:
        ctx = bpy.context
        auto_group_step(ctx)
        return 0.3 if scope(ctx) is not None else 1.0
    except (AttributeError, ReferenceError, RuntimeError):
        return 0.7
    except UnicodeDecodeError as ex:          # 0.24.129 a data-block name that is not UTF-8: repair, go on
        from . import name_fix
        name_fix.on_error(ex)
        return 0.7


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


class MCH_OT_group_boxes_all(bpy.types.Operator):
    """Show / hide the box lines of every group at once (the per-group eye stays as it is)"""
    bl_idname = 'mch.group_boxes_all'
    bl_label = 'All Group Box Lines'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}

    def execute(self, context):
        st = getattr(context.scene, 'mch_settings', None)
        if st is None:
            return {'CANCELLED'}
        st.group_boxes = not st.group_boxes
        for area in context.screen.areas if context.screen else []:
            area.tag_redraw()
        return {'FINISHED'}


class MCH_OT_group_toggle_collapse(bpy.types.Operator):
    """Expand/collapse one group in the Mecha sidebar without changing scene visibility."""
    bl_idname = 'mch.group_toggle_collapse'
    bl_label = 'Expand / Collapse Group'
    bl_options = {'INTERNAL'}
    name: bpy.props.StringProperty()

    def execute(self, context):
        g = bpy.data.objects.get(self.name)
        if not is_group(g):
            return {'CANCELLED'}
        g[COLLAPSE_KEY] = not bool(g.get(COLLAPSE_KEY))
        return {'FINISHED'}


class MCH_OT_group_rename(bpy.types.Operator):
    """Rename a whole group without invalidating collection / repeat / scope name references."""
    bl_idname = 'mch.group_rename'
    bl_label = 'Rename Group'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()
    new_name: bpy.props.StringProperty(name='Group Name')

    def invoke(self, context, event):
        g = bpy.data.objects.get(self.name)
        if not is_group(g):
            return {'CANCELLED'}
        self.new_name = g.name
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        g = bpy.data.objects.get(self.name)
        if not is_group(g) or not self.new_name.strip():
            return {'CANCELLED'}
        rename(context, g, self.new_name.strip())
        return {'FINISHED'}


def _scope_to_reach(context, g):
    """0.24.107 Selecting a group from the Layers panel leaves only as many scope levels as needed to pick it (it
    left them all): a group inside the current scope is picked in place."""
    path = scope_path(context)
    if not path:
        return
    chain = [o.name for o in _parents_of(g)]
    keep = []
    for name in path:
        if name in chain and name != g.name:
            keep.append(name)
        else:
            break
    if keep == path:
        return
    if not keep:
        clear_scope(context, select=False)
        return
    top = bpy.data.objects.get(keep[-1])
    _show_scope(context, top)
    context.scene[SCOPE_KEY] = top.name
    context.scene[SCOPE_PATH_KEY] = json.dumps(keep)


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
        current = ensure_scope(context)
        if self.enter:
            if current == g:
                exit_scope(context)
            else:
                enter_scope(context, g)
        elif current == g:
            exit_scope(context)          # 0.24.107 the row's Exit: one level out (it left every level)
        else:
            _scope_to_reach(context, g)
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


def _visible_group_rows(context):
    """Visible sidebar tree rows; collapsed descendants still exist in scene."""
    blocked_depth = None
    for g, depth in all_groups(context):
        if blocked_depth is not None and depth > blocked_depth:
            continue
        blocked_depth = None
        yield g, depth
        if g.get(COLLAPSE_KEY):
            blocked_depth = depth


def draw_list(layout, context):
    """Tree sidebar: select, enter, collapse, rename and choose scope display."""
    rows = list(_visible_group_rows(context))
    inside = scope(context)
    from . import work_scene                                             # 0.24.95 a clean scene for one group
    work_scene.draw(layout, context)
    if not rows:
        layout.label(text='No groups yet (Mecha Menu > Groups > Group)', icon='INFO')
        return
    st = getattr(context.scene, 'mch_settings', None)
    layout.prop(context.scene, 'mch_group_focus_enabled', text='Click Select / Double-click Enter', icon='RESTRICT_SELECT_OFF')
    layout.prop(context.scene, 'mch_group_auto_add', text='Auto-add New Parts in Group', icon='ADD')
    layout.prop(context.scene, 'mch_group_scope_display', text='Outside Scope')
    if st is not None:                                                   # 0.24.87 every group's box lines at once
        layout.prop(st, 'group_boxes', text='Box Lines (all groups)', icon='MESH_CUBE' if st.group_boxes else 'CUBE', toggle=True)
    if inside is not None:
        layout.label(text=' / '.join(scope_path(context)), icon='GROUP')
        layout.operator('mch.group_action', text=f'Up from {inside.name}', icon='LOOP_BACK').action = 'EXIT'
    g = group_of(context.active_object)
    if g is not None:
        row = layout.row(align=True)
        row.operator('mch.duplicate', text='Duplicate', icon='DUPLICATE')
        row.operator('mch.duplicate', text='Linked Copy', icon='LINKED').linked = True      # 0.24.85
        row.operator('mch.group_action', text='Origin to Geometry', icon='PIVOT_MEDIAN').action = 'ORIGIN'
        layout.operator('mch.group_mirror_lean', text='Mirror Group (Alt+X)', icon='MOD_MIRROR')
    col = layout.column(align=True)
    for g, depth in rows:
        row = col.row(align=True)
        for _ in range(depth):
            row.label(text='', icon='BLANK1')
        has_children = any(is_group(child) for child in g.children)
        if has_children:
            toggle = row.operator('mch.group_toggle_collapse', text='',
                icon='TRIA_RIGHT' if g.get(COLLAPSE_KEY) else 'TRIA_DOWN', emboss=False)
            toggle.name = g.name
        else:
            row.label(text='', icon='BLANK1')
        sel = context.active_object == g
        op = row.operator('mch.group_pick', text=g.name, icon='GROUP', depress=sel)
        op.name, op.enter = g.name, False
        rename_op = row.operator('mch.group_rename', text='', icon='GREASEPENCIL', emboss=False)
        rename_op.name = g.name
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


CLASSES = (MCH_OT_group_view_pick, MCH_OT_group, MCH_OT_group_action, MCH_OT_duplicate, MCH_OT_group_repeat, MCH_OT_group_box_eye, MCH_OT_group_boxes_all,
           MCH_OT_group_toggle_collapse, MCH_OT_group_rename, MCH_OT_group_pick, MCH_PT_groups)


def _register_group_keymaps():
    """Register viewport group shortcuts after add-on registration finishes.

    Blender supplies restricted context/data during register().  Returning a
    number retries later if a WindowManager or add-on keyconfig is not ready.
    """
    if not _auto_timer_live or bpy.app.background:
        return None
    if _group_keymaps:
        return None
    try:
        wm = bpy.context.window_manager
        kc = wm.keyconfigs.addon if wm else None
    except (AttributeError, ReferenceError, RuntimeError):
        return 1.0
    if kc is None:
        return 1.0
    km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
    try:
        for value, enter in (('CLICK', False), ('DOUBLE_CLICK', True)):
            kmi = km.keymap_items.new('mch.group_view_pick', 'LEFTMOUSE', value)
            kmi.properties.enter = enter
            _group_keymaps.append((km, kmi))
    except Exception:
        for registered_km, item in _group_keymaps:
            try:
                registered_km.keymap_items.remove(item)
            except (ReferenceError, RuntimeError):
                pass
        _group_keymaps.clear()
        return 1.0
    return None


def register():
    global _box_handle, _auto_timer_live
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_group_focus_enabled = bpy.props.BoolProperty(
        name='Viewport Group Focus', default=True,
        description='Select mode: single-click a part to select its group, double-click to edit inside')
    bpy.types.Scene.mch_group_auto_add = bpy.props.BoolProperty(
        name='Auto-add New Parts', default=True,
        description='Automatically place newly created visible objects inside the active group scope')
    bpy.types.Scene.mch_group_scope_display = bpy.props.EnumProperty(
        name='Outside Scope',
        items=[('NORMAL', 'Normal', 'Outside objects keep their display, but cannot be selected'),
               ('WIRE', 'Ghost (Wire)', 'Outside objects are shown as non-selectable wireframes'),
               ('HIDDEN', 'Hidden', 'Outside objects are hidden while working in the group')],
        default='WIRE', update=_scope_display_update)
    _auto_timer_live = True
    _seen_scene_objects.clear()
    _pending.clear()
    # Blender intentionally restricts bpy.data while an add-on is registering.
    # _auto_group_tick seeds the scene snapshot on its first tick, after registration.
    # 0.24.107: persistent timers (a plain timer is dropped when a file loads - Blender started with a .blend had no
    # group clicks and no auto-add); the keymap timer also stays until it got the add-on keyconfig.
    _start_timers()
    for hl, fn in ((bpy.app.handlers.load_post, _on_load), (bpy.app.handlers.undo_post, _on_undo),
                   (bpy.app.handlers.redo_post, _on_undo),
                   (getattr(bpy.app.handlers, 'blend_import_post', None), _on_import)):
        if hl is not None and fn not in hl:
            hl.append(fn)
    if not bpy.app.background and _box_handle is None:
        _box_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_boxes, (), 'WINDOW', 'POST_VIEW')
        if not bpy.app.timers.is_registered(_tidy_later):
            bpy.app.timers.register(_tidy_later, first_interval=0.5)
    try:
        from . import group_outline
        group_outline.register()
    except ImportError:
        pass


def unregister():
    global _box_handle, _auto_timer_live
    _auto_timer_live = False
    for timer in (_auto_group_tick, _register_group_keymaps):
        if bpy.app.timers.is_registered(timer):
            bpy.app.timers.unregister(timer)
    _seen_scene_objects.clear()
    _pending.clear()
    for km, kmi in _group_keymaps:
        try:
            km.keymap_items.remove(kmi)
        except (ReferenceError, RuntimeError):
            pass
    _group_keymaps.clear()
    for prop in ('mch_group_focus_enabled', 'mch_group_auto_add', 'mch_group_scope_display'):
        if hasattr(bpy.types.Scene, prop):
            delattr(bpy.types.Scene, prop)
    if _box_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_box_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _box_handle = None
    for hl, fn in ((bpy.app.handlers.load_post, _on_load), (bpy.app.handlers.undo_post, _on_undo),
                   (bpy.app.handlers.redo_post, _on_undo),
                   (getattr(bpy.app.handlers, 'blend_import_post', None), _on_import)):
        if hl is not None and fn in hl:
            hl.remove(fn)
    if bpy.app.timers.is_registered(_tidy_later):
        bpy.app.timers.unregister(_tidy_later)
    try:
        from . import group_outline
        group_outline.unregister()
    except ImportError:
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
