"""0.24.179 Face Pop (user, a faceted rock in Edit Mode: "내가 선택한 면이 튀어나오게 하는 것도 만들어 주라"): pick faces
of a part and they stand out - extruded along their normals, Height high, their sides slanting in by Taper; faces
picked side by side come out together as one (Each Face: every face on its own).

0.24.180 two ways (user: "페이스 팝은 별개의 메쉬로 분리되어야지" - then "그냥 페이스 팝도 나쁘지 않으니까 유지하고
스플릿 버전도 만들어 줘"): In the Part (as 0.24.179: the part's own faces stand out - a modifier on it, live until Apply)
or Split: the faces picked make a part of their own - a new object, a closed piece (top, sides, a bottom sunk a little into the part) - the part itself is not
touched (no modifier, no attribute on it).  The piece is its part's child (it moves with it), has the part's
materials, and stays live (Height, Taper, Each Face: a Geometry Nodes modifier on the piece) until Apply (then a plain
mesh, still its own object).

In Object Mode with the tool: click a face (the face under the mouse is shown), drag over faces - each one picked
into the selected piece of that part (none selected, or after New Pop: a new piece); Alt: taken off it (none left:
the piece goes).  Faces picked in Edit Mode: "From Edit Mode Selection" - a new piece.
"""
from __future__ import annotations

import json

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, PointerProperty, StringProperty
from mathutils import Matrix, Vector
from mathutils.bvhtree import BVHTree

ATTR = 'mch_pop'                       # (0.24.179 parts: the faces picked on the part itself - Apply still works)
MOD = 'MCH Face Pop'
TREE = 'MCH Face Pop Piece'
TREE_V = 1
PART_TREE = 'MCH Face Pop'             # (In the Part: the part's picked faces - its face attribute ``mch_pop``)
PART_TREE_V = 1
KEY = 'mch_face_pop'                   # on a piece: 1
NEW_KEY = 'mch_pop_new'                # window manager: the next click makes a new piece


def part_tree():
    """In the Part: the part's faces picked (attribute ``mch_pop``) pushed out Height, the top smaller by Taper."""
    ng = bpy.data.node_groups.get(PART_TREE)
    if ng is not None and ng.get('mch_v') == PART_TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(PART_TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for s_ in list(ng.interface.items_tree):
        ng.interface.remove(s_)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    h = ng.interface.new_socket('Height', in_out='INPUT', socket_type='NodeSocketFloat')
    h.default_value = 0.05
    t = ng.interface.new_socket('Taper', in_out='INPUT', socket_type='NodeSocketFloat')
    t.default_value, t.min_value, t.max_value = 0.3, 0.0, 0.95
    ind = ng.interface.new_socket('Each Face', in_out='INPUT', socket_type='NodeSocketBool')
    ind.default_value = False
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    na = N.new('GeometryNodeInputNamedAttribute')
    na.data_type = 'BOOLEAN'
    na.inputs['Name'].default_value = ATTR
    ex = N.new('GeometryNodeExtrudeMesh')
    ex.mode = 'FACES'
    L.new(gi.outputs['Geometry'], ex.inputs['Mesh'])
    L.new(na.outputs['Attribute'], ex.inputs['Selection'])
    L.new(gi.outputs['Height'], ex.inputs['Offset Scale'])
    L.new(gi.outputs['Each Face'], ex.inputs['Individual'])
    one = N.new('ShaderNodeMath')
    one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0
    L.new(gi.outputs['Taper'], one.inputs[1])
    sc = N.new('GeometryNodeScaleElements')
    sc.domain = 'FACE'
    L.new(ex.outputs['Mesh'], sc.inputs['Geometry'])
    L.new(ex.outputs['Top'], sc.inputs['Selection'])
    L.new(one.outputs[0], sc.inputs['Scale'])
    L.new(sc.outputs['Geometry'], go.inputs['Geometry'])
    ng['mch_v'] = PART_TREE_V
    return ng


def node_group():
    """Split - the piece: the picked faces sunk a little into the part, pushed out Height (+ the sink) along their normals,
    the top made smaller by Taper, the bottom (the faces turned over) closing it."""
    ng = bpy.data.node_groups.get(TREE)
    if ng is not None and ng.get('mch_v') == TREE_V:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(TREE, 'GeometryNodeTree')
    ng.nodes.clear()
    for s_ in list(ng.interface.items_tree):
        ng.interface.remove(s_)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    h = ng.interface.new_socket('Height', in_out='INPUT', socket_type='NodeSocketFloat')
    h.default_value = 0.05
    t = ng.interface.new_socket('Taper', in_out='INPUT', socket_type='NodeSocketFloat')
    t.default_value, t.min_value, t.max_value = 0.3, 0.0, 0.95
    ind = ng.interface.new_socket('Each Face', in_out='INPUT', socket_type='NodeSocketBool')
    ind.default_value = False
    sk = ng.interface.new_socket('Sink', in_out='INPUT', socket_type='NodeSocketFloat')
    sk.default_value = 0.005
    wd = ng.interface.new_socket('Weld', in_out='INPUT', socket_type='NodeSocketFloat')
    wd.default_value = 1e-5
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = ng.nodes
    L = ng.links
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    nrm = N.new('GeometryNodeInputNormal')
    down = N.new('ShaderNodeVectorMath')
    down.operation = 'SCALE'
    L.new(nrm.outputs['Normal'], down.inputs[0])
    neg = N.new('ShaderNodeMath')
    neg.operation = 'MULTIPLY'
    neg.inputs[1].default_value = -1.0
    L.new(gi.outputs['Sink'], neg.inputs[0])
    L.new(neg.outputs[0], down.inputs['Scale'])
    sink = N.new('GeometryNodeSetPosition')
    L.new(gi.outputs['Geometry'], sink.inputs['Geometry'])
    L.new(down.outputs['Vector'], sink.inputs['Offset'])
    tot = N.new('ShaderNodeMath')
    tot.operation = 'ADD'
    L.new(gi.outputs['Height'], tot.inputs[0])
    L.new(gi.outputs['Sink'], tot.inputs[1])
    ex = N.new('GeometryNodeExtrudeMesh')
    ex.mode = 'FACES'
    L.new(sink.outputs['Geometry'], ex.inputs['Mesh'])
    L.new(tot.outputs[0], ex.inputs['Offset Scale'])
    L.new(gi.outputs['Each Face'], ex.inputs['Individual'])
    one = N.new('ShaderNodeMath')
    one.operation = 'SUBTRACT'
    one.inputs[0].default_value = 1.0
    L.new(gi.outputs['Taper'], one.inputs[1])
    sc = N.new('GeometryNodeScaleElements')
    sc.domain = 'FACE'
    L.new(ex.outputs['Mesh'], sc.inputs['Geometry'])
    L.new(ex.outputs['Top'], sc.inputs['Selection'])
    L.new(one.outputs[0], sc.inputs['Scale'])
    flip = N.new('GeometryNodeFlipFaces')
    L.new(sink.outputs['Geometry'], flip.inputs['Mesh'])
    join = N.new('GeometryNodeJoinGeometry')
    L.new(flip.outputs['Mesh'], join.inputs['Geometry'])
    L.new(sc.outputs['Geometry'], join.inputs['Geometry'])
    weld = N.new('GeometryNodeMergeByDistance')
    L.new(join.outputs['Geometry'], weld.inputs['Geometry'])
    L.new(gi.outputs['Weld'], weld.inputs['Distance'])
    L.new(weld.outputs['Geometry'], go.inputs['Geometry'])
    ng['mch_v'] = TREE_V
    return ng


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object):
        push(ob)


class MCH_PG_FacePop(bpy.types.PropertyGroup):
    mode: EnumProperty(name='Face Pop', items=(
        ('PART', 'In the Part', 'The picked faces stand out of the part itself (a modifier on it, live until Apply)'),
        ('SPLIT', 'Split', 'The picked faces make a part of their own (a new object; the part is not touched)')),
        default='PART')
    height: FloatProperty(name='Height', default=0.05, soft_min=0.0, soft_max=0.5, precision=4, unit='LENGTH',
                          update=_upd, description='How far the piece stands out of the part')
    taper: FloatProperty(name='Taper', default=0.3, min=0.0, max=0.95, update=_upd,
                         description='Its top smaller - the sides slant in')
    each: BoolProperty(name='Each Face', default=False, update=_upd,
                       description='Every picked face on its own (off: faces side by side come out together)')
    source: PointerProperty(type=bpy.types.Object, name='Part', description='The part the piece was picked on')
    faces: StringProperty(default='[]', options={'HIDDEN'})


def is_piece(ob):
    return ob is not None and ob.type == 'MESH' and bool(ob.get(KEY))


def faces_of(piece):
    try:
        return [int(f) for f in json.loads(piece.mch_pop.faces or '[]')]
    except ValueError:
        return []


def pieces_of(source):
    return [o for o in bpy.data.objects if is_piece(o) and o.mch_pop.source == source]


def _set_input(mod, name, value):
    from . import geo_sculpt as gs
    gs.set_input(mod, name, value)


def push(ob):
    """The piece's values into its modifier."""
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    p = ob.mch_pop
    sc = _scale(ob)
    h = p.height / sc
    _set_input(mod, 'Height', h)
    _set_input(mod, 'Taper', p.taper)
    _set_input(mod, 'Each Face', p.each)
    try:
        _set_input(mod, 'Sink', max(abs(h) * 0.12, 1e-5))
        _set_input(mod, 'Weld', max(abs(h) * 1e-4, 1e-7))
    except (StopIteration, KeyError, AttributeError, TypeError):
        pass
    ob.update_tag()


def _scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def picked(me):
    """In the Part: the faces picked on the part's own mesh."""
    a = me.attributes.get(ATTR)
    v = np.zeros(len(me.polygons), bool)
    if a is not None and a.domain == 'FACE' and len(me.polygons):
        a.data.foreach_get('value', v)
    return v


def set_faces(ob, faces, on=True, settings=None):
    """In the Part: faces ``faces`` of ``ob``'s own mesh picked (``on``) or taken off; its modifier made / removed with
    them.  Returns how many are picked."""
    me = ob.data
    a = me.attributes.get(ATTR)
    if a is None:
        a = me.attributes.new(ATTR, 'BOOLEAN', 'FACE')
    v = picked(me)
    idx = [int(f) for f in faces if 0 <= int(f) < len(v)]
    v[idx] = on
    a.data.foreach_set('value', v)
    me.update()
    mod = ob.modifiers.get(MOD)
    if v.any() and mod is None:
        if settings is not None:
            for k in ('height', 'taper', 'each'):
                setattr(ob.mch_pop, k, getattr(settings, k))
        mod = ob.modifiers.new(MOD, 'NODES')
        mod.node_group = part_tree()
        try:                                          # (first: what is made after it - mirror ... - takes it along)
            ob.modifiers.move(len(ob.modifiers) - 1, 0)
        except (RuntimeError, TypeError, AttributeError):
            pass
        push(ob)
    elif not v.any():
        if mod is not None:
            ob.modifiers.remove(mod)
        me.attributes.remove(me.attributes[ATTR])
    return int(v.sum())


def rebuild(piece):
    """The piece's mesh: its faces copied from its part's own mesh (the part's space), the part's materials."""
    src = piece.mch_pop.source
    if src is None or src.type != 'MESH':
        return 0
    sme = src.data
    faces = [f for f in faces_of(piece) if 0 <= f < len(sme.polygons)]
    used, polys, mats = {}, [], []
    for f in faces:
        poly = sme.polygons[f]
        polys.append([used.setdefault(v, len(used)) for v in poly.vertices])
        mats.append(poly.material_index)
    co = [None] * len(used)
    for v, i in used.items():
        co[i] = tuple(sme.vertices[v].co)
    me = bpy.data.meshes.new(piece.name)
    me.from_pydata(co, [], polys)
    if len(mats):
        me.polygons.foreach_set('material_index', mats)
    for m in sme.materials:
        me.materials.append(m)
    me.update()
    old = piece.data
    piece.data = me
    if old is not None and old.users == 0:
        bpy.data.meshes.remove(old)
    piece.mch_pop.faces = json.dumps(faces)
    return len(faces)


def new_piece(context, source, settings=None):
    """A new piece of ``source`` (no faces yet): its child, in its space, the tool's values."""
    me = bpy.data.meshes.new(source.name + ' Pop')
    ob = bpy.data.objects.new(source.name + ' Pop', me)
    coll = source.users_collection[0] if source.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob.parent = source
    ob.matrix_parent_inverse = Matrix.Identity(4)
    ob.matrix_basis = Matrix.Identity(4)
    ob[KEY] = 1
    p = ob.mch_pop
    st = settings if settings is not None else context.scene.mch_pop
    for k in ('height', 'taper', 'each'):
        setattr(p, k, getattr(st, k))
    p.source = source
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = node_group()
    push(ob)
    return ob


def add_faces(context, source, faces, piece=None, settings=None):
    """Faces of ``source`` picked into ``piece`` (None: a new one).  Returns the piece."""
    if piece is None:
        piece = new_piece(context, source, settings)
    have = faces_of(piece)
    new = [int(f) for f in faces if int(f) not in have]
    if new or not len(piece.data.polygons):
        piece.mch_pop.faces = json.dumps(have + new)
        rebuild(piece)
    return piece


def remove_faces(source, faces, piece=None):
    """Faces of ``source`` taken off ``piece`` (None: whichever of its pieces has them); a piece with none left is
    removed.  Returns how many were taken off."""
    gone = 0
    drop = {int(f) for f in faces}
    for pc in ([piece] if piece is not None else pieces_of(source)):
        have = faces_of(pc)
        kept = [f for f in have if f not in drop]
        if len(kept) == len(have):
            continue
        gone += len(have) - len(kept)
        if not kept:
            me = pc.data
            bpy.data.objects.remove(pc)
            if me is not None and me.users == 0:
                bpy.data.meshes.remove(me)
            continue
        pc.mch_pop.faces = json.dumps(kept)
        rebuild(pc)
    return gone


def from_edit_selection(context, ob, settings=None, split=True):
    """The faces picked in Edit Mode (back in Object Mode): a new piece (Split) - or out of the part itself (returns
    the part)."""
    me = ob.data
    sel = np.zeros(len(me.polygons), bool)
    me.polygons.foreach_get('select', sel)
    if not sel.any() or sel.all():
        return None
    if not split:
        set_faces(ob, np.nonzero(sel)[0].tolist(), True, settings)
        return ob
    return add_faces(context, ob, np.nonzero(sel)[0].tolist(), None, settings)


def apply(context, ob):
    """Split: the piece as a plain mesh (still its own object); In the Part: the popped faces into the part."""
    from . import core_geometry as cg
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return False
    cg.apply_single_modifier(context, ob, mod)
    if is_piece(ob):
        del ob[KEY]
        return True
    at = ob.data.attributes.get(ATTR)
    if at is not None:
        ob.data.attributes.remove(at)
    return True


# --- the tool ------------------------------------------------------------------------------------------------------

HOVER = {'part': None, 'face': None}
_TREES = {}


def _tree(ob):
    me = ob.data
    key = (me.as_pointer(), len(me.vertices), len(me.polygons))
    hit = _TREES.get(ob.name)
    if hit is not None and hit[0] == key:
        return hit[1]
    n = len(me.vertices)
    co = np.empty(n * 3, np.float64)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    polys = [tuple(p.vertices) for p in me.polygons]
    t = BVHTree.FromPolygons([tuple(c) for c in co], polys)
    if len(_TREES) > 8:
        _TREES.clear()
    _TREES[ob.name] = (key, t)
    return t


def face_at(context, xy):
    """(part, its face index) under the mouse - read on the part's own mesh - or None.  0.24.180 on a piece: its
    part's face there (under the piece)."""
    from bpy_extras import view3d_utils
    from . import geo_sculpt as gs
    hit = gs.pick_part(context, xy)
    if hit is None:
        return None
    ob = hit[0]
    if is_piece(ob):
        ob = ob.mch_pop.source
        if ob is None or ob.type != 'MESH':
            return None
    region, rv3d = context.region, context.region_data
    mi = ob.matrix_world.inverted_safe()
    o = mi @ view3d_utils.region_2d_to_origin_3d(region, rv3d, xy)
    d = (mi.to_3x3() @ view3d_utils.region_2d_to_vector_3d(region, rv3d, xy)).normalized()
    loc, _n, idx, _dist = _tree(ob).ray_cast(o, d)
    if idx is None:
        loc, _n, idx, _dist = _tree(ob).find_nearest(mi @ Vector(hit[1]))
    return (ob, int(idx)) if idx is not None else None


def tool_on(context):
    from . import tool_state as ts
    try:
        return ts.effective_tool(context) == 'FPOP'
    except (AttributeError, KeyError, TypeError):
        return False


def _face_tris(ob, faces):
    me = ob.data
    mw = ob.matrix_world
    out = []
    for f in faces:
        if 0 <= f < len(me.polygons):
            vs = [mw @ me.vertices[i].co for i in me.polygons[f].vertices]
            n = (mw.to_3x3() @ me.polygons[f].normal).normalized() * 0.0015
            for k in range(1, len(vs) - 1):
                out += [tuple(vs[0] + n), tuple(vs[k] + n), tuple(vs[k + 1] + n)]
    return out


def draw_faces():
    context = bpy.context
    try:
        if not tool_on(context):
            return
        ob = bpy.data.objects.get(HOVER['part']) if HOVER['part'] else None
        if ob is None or ob.type != 'MESH':
            return
        split = context.scene.mch_pop.mode == 'SPLIT'
        pc = current_piece(context, ob) if split else None
        import gpu
        from gpu_extras.batch import batch_for_shader
        sh = gpu.shader.from_builtin('UNIFORM_COLOR')
        gpu.state.blend_set('ALPHA')
        gpu.state.depth_test_set('LESS_EQUAL')
        gpu.state.depth_mask_set(False)
        sel = (faces_of(pc) if pc is not None else []) if split else np.nonzero(picked(ob.data))[0].tolist()
        if sel and len(sel) < 20000:
            tris = _face_tris(ob, sel)
            sh.uniform_float('color', (1.0, 0.55, 0.1, 0.35))
            batch_for_shader(sh, 'TRIS', {'pos': tris}).draw(sh)
        if HOVER['face'] is not None:
            tris = _face_tris(ob, [HOVER['face']])
            sh.uniform_float('color', (1.0, 0.92, 0.2, 0.45))
            batch_for_shader(sh, 'TRIS', {'pos': tris}).draw(sh)
        gpu.state.depth_test_set('NONE')
        gpu.state.blend_set('NONE')
    except (ReferenceError, AttributeError, RuntimeError, KeyError, ValueError):
        pass


class MCH_OT_face_pop_hover(bpy.types.Operator):
    """(Face Pop) the face under the mouse, shown (passes the move on)"""
    bl_idname = 'mch.face_pop_hover'
    bl_label = 'Face Pop Hover'
    bl_options = {'INTERNAL'}

    def invoke(self, context, event):
        if context.region is None or context.region.type != 'WINDOW':
            return {'PASS_THROUGH'}
        got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
        part, face = (got[0].name, got[1]) if got else (HOVER['part'], None)
        if (part, face) != (HOVER['part'], HOVER['face']):
            HOVER['part'], HOVER['face'] = part, face
            context.region.tag_redraw()
        return {'PASS_THROUGH'}


class MCH_OT_face_pop_pick(bpy.types.Operator):
    """Face Pop: click a face of a part - it stands out; drag over faces - each one; Alt: taken off"""
    bl_idname = 'mch.face_pop_pick'
    bl_label = 'Face Pop'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.area is not None and context.area.type == 'VIEW_3D' and context.mode == 'OBJECT'

    def invoke(self, context, event):
        got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
        if got is None:
            return {'PASS_THROUGH'}
        self.ob = got[0]
        self.on = not event.alt
        self.done = set()
        self.split = context.scene.mch_pop.mode == 'SPLIT'
        self.piece = current_piece(context, self.ob)          # (the selected piece of this part; None: a new one)
        if self.on and getattr(context.window_manager, NEW_KEY, False):
            self.piece = None
            setattr(context.window_manager, NEW_KEY, False)
        self._take(context, got[1])
        context.window_manager.modal_handler_add(self)
        return {'RUNNING_MODAL'}

    def _take(self, context, f):
        if f in self.done:
            return
        self.done.add(f)
        if not self.split:                            # (In the Part: the part's own faces)
            set_faces(self.ob, [f], self.on, context.scene.mch_pop)
        elif self.on:
            self.piece = add_faces(context, self.ob, [f], self.piece, context.scene.mch_pop)
            try:                                      # (the piece selected: the next click adds to it)
                for o in context.selected_objects:
                    if o is not self.piece:
                        o.select_set(False)
                self.piece.select_set(True)
                context.view_layer.objects.active = self.piece
            except (RuntimeError, ReferenceError):
                pass
        else:
            remove_faces(self.ob, [f], self.piece if self.piece is not None and f in faces_of(self.piece) else None)
            if self.piece is not None and self.piece.name not in bpy.data.objects:
                self.piece = None
        HOVER['part'], HOVER['face'] = self.ob.name, None
        context.area.tag_redraw()

    def modal(self, context, event):
        if event.type in {'MOUSEMOVE', 'INBETWEEN_MOUSEMOVE'}:
            got = face_at(context, (event.mouse_region_x, event.mouse_region_y))
            if got is not None and got[0] == self.ob:
                self._take(context, got[1])
            return {'RUNNING_MODAL'}
        if event.type == 'LEFTMOUSE' and event.value == 'RELEASE':
            if not self.split:
                n = int(picked(self.ob.data).sum())
                self.report({'INFO'}, f'Face Pop on "{self.ob.name}": {n} face{"s" if n != 1 else ""} out - Height, '
                                      f'Taper, Each Face in the window; Apply keeps it')
                return {'FINISHED'}
            pc = self.piece if self.piece is not None and self.piece.name in bpy.data.objects else None
            if pc is not None:
                n = len(faces_of(pc))
                self.report({'INFO'}, f'Face Pop: "{pc.name}" - {n} face{"s" if n != 1 else ""} of "{self.ob.name}" '
                                      f'out as a part of its own (Height, Taper, Each Face in the window)')
            return {'FINISHED'}
        if event.type in {'ESC', 'RIGHTMOUSE'} and event.value == 'PRESS':
            return {'FINISHED'}
        return {'RUNNING_MODAL'}


def current_piece(context, source):
    """The piece new faces of ``source`` go into: the active piece of it, else None (a new one)."""
    ob = getattr(context, 'active_object', None)
    if is_piece(ob) and ob.mch_pop.source == source:
        return ob
    return None


def active_part(context):
    """The selected piece (or a 0.24.179 part with its faces popped on it)."""
    ob = context.active_object
    if ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None:
        return ob
    return None


class MCH_OT_face_pop_from_edit(bpy.types.Operator):
    """The faces you selected in Edit Mode (back in Object Mode) stand out"""
    bl_idname = 'mch.face_pop_from_edit'
    bl_label = 'From Edit Mode Selection'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if ob is None or ob.type != 'MESH':
            self.report({'WARNING'}, 'Select the part first')
            return {'CANCELLED'}
        if is_piece(ob):
            ob = ob.mch_pop.source
            if ob is None:
                return {'CANCELLED'}
        if context.mode == 'EDIT_MESH':
            bpy.ops.object.mode_set(mode='OBJECT')
        split = context.scene.mch_pop.mode == 'SPLIT'
        pc = from_edit_selection(context, ob, context.scene.mch_pop, split)
        if pc is None:
            self.report({'WARNING'}, 'No faces picked in Edit Mode (or all of them)')
            return {'CANCELLED'}
        if not split:
            self.report({'INFO'}, f'Face Pop on "{ob.name}": {int(picked(ob.data).sum())} faces out')
            return {'FINISHED'}
        for o in context.selected_objects:
            o.select_set(False)
        pc.select_set(True)
        context.view_layer.objects.active = pc
        self.report({'INFO'}, f'Face Pop: "{pc.name}" - {len(faces_of(pc))} faces of "{ob.name}" out as a part of its own')
        return {'FINISHED'}


class MCH_OT_face_pop_clear(bpy.types.Operator):
    """Split: delete the selected piece; In the Part: all its picked faces taken off (the part as it was)"""
    bl_idname = 'mch.face_pop_clear'
    bl_label = 'Clear'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = context.active_object
        if is_piece(ob):
            remove_faces(ob.mch_pop.source, faces_of(ob), ob)
            return {'FINISHED'}
        ob = active_part(context)
        if ob is None:
            return {'CANCELLED'}
        set_faces(ob, range(len(ob.data.polygons)), False)
        return {'FINISHED'}


class MCH_OT_face_pop_new(bpy.types.Operator):
    """The next face you click makes a new piece (instead of adding to the selected one)"""
    bl_idname = 'mch.face_pop_new'
    bl_label = 'New Pop'
    bl_options = {'REGISTER', 'INTERNAL'}

    def execute(self, context):
        setattr(context.window_manager, NEW_KEY, True)
        self.report({'INFO'}, 'Face Pop: the next face you click makes a new piece')
        return {'FINISHED'}


class MCH_OT_face_pop_apply(bpy.types.Operator):
    """Keep it: the piece a plain mesh (still its own object)"""
    bl_idname = 'mch.face_pop_apply'
    bl_label = 'Apply'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = active_part(context)
        if ob is None or not apply(context, ob):
            return {'CANCELLED'}
        self.report({'INFO'}, f'Face Pop applied on "{ob.name}"')
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_pop
    row = layout.row(align=True)
    row.scale_y = 1.2
    row.prop(st, 'mode', expand=True)
    split = st.mode == 'SPLIT'
    ob = context.active_object
    piece = ob if is_piece(ob) else None
    part = ob if (piece is None and ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None) else None
    live = piece or part
    p = live.mch_pop if live is not None else st
    col = layout.column(align=True)
    if piece is not None:
        src = piece.mch_pop.source
        col.label(text=f'{piece.name}: {len(faces_of(piece))} faces of {src.name if src else "?"} (live)')
    elif part is not None:
        col.label(text=f'{part.name}: {int(picked(part.data).sum())} faces out (live)')
    else:
        col.label(text='The next piece' if split else 'The next faces')
    col.prop(p, 'height')
    col.prop(p, 'taper')
    col.prop(p, 'each')
    row = layout.row(align=True)
    if split:
        row.operator('mch.face_pop_new', text='New Pop', depress=bool(getattr(context.window_manager, NEW_KEY, False)))
    row.operator('mch.face_pop_from_edit', text='From Edit Mode Selection' if not split else 'From Edit Mode')
    if live is not None:
        row = layout.row(align=True)
        row.operator('mch.face_pop_clear', text='Delete Piece' if piece is not None else 'Clear')
        row.operator('mch.face_pop_apply', text='Apply')
    col = layout.column(align=True)
    lines = (('Click a face: it stands out as a part of its own',
              '(the part is not touched); drag: each face passed',
              'More clicks: into the selected piece; New Pop: another',
              'Alt + click / drag: taken off the piece') if split else
             ('Click a face: it stands out of the part; drag: each',
              'face passed.  Alt + click / drag: taken off')) + (
        'Faces side by side come out together (Each Face: apart)',)
    for line in lines:
        col.label(text=line)


def _tool_settings(context, layout, tool):
    region = getattr(context, 'region', None)
    if region is not None and region.type == 'TOOL_HEADER':
        return
    draw(layout, context)


class MCH_TOOL_face_pop(bpy.types.WorkSpaceTool):
    bl_space_type = 'VIEW_3D'
    bl_context_mode = 'OBJECT'
    bl_idname = 'mecha.face_pop'
    bl_label = 'Mecha Face Pop'
    bl_description = 'Click faces of a part: they stand out (Height, Taper); drag: each face passed; Alt: off'
    bl_icon = 'ops.generic.select_box'
    bl_widget = None
    bl_keymap = (('mch.face_pop_hover', {'type': 'MOUSEMOVE', 'value': 'ANY', 'any': True}, None),
                 ('mch.face_pop_pick', {'type': 'LEFTMOUSE', 'value': 'PRESS'}, None),
                 ('mch.face_pop_pick', {'type': 'LEFTMOUSE', 'value': 'PRESS', 'alt': True}, None),
                 ('mch.toggle_targets', {'type': 'T', 'value': 'PRESS'}, None),
                 ('mch.exit_tool', {'type': 'ESC', 'value': 'PRESS'}, None))
    draw_settings = staticmethod(_tool_settings)


CLASSES = (MCH_PG_FacePop, MCH_OT_face_pop_hover, MCH_OT_face_pop_pick, MCH_OT_face_pop_from_edit,
           MCH_OT_face_pop_clear, MCH_OT_face_pop_new, MCH_OT_face_pop_apply)
_HANDLE = [None]


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_pop = PointerProperty(type=MCH_PG_FacePop)
    bpy.types.Scene.mch_pop = PointerProperty(type=MCH_PG_FacePop)
    setattr(bpy.types.WindowManager, NEW_KEY, BoolProperty(default=False, options={'SKIP_SAVE'}))
    try:
        bpy.utils.register_tool(MCH_TOOL_face_pop, separator=False, group=False)
    except (ValueError, RuntimeError, KeyError):
        pass
    if _HANDLE[0] is None and not bpy.app.background:
        _HANDLE[0] = bpy.types.SpaceView3D.draw_handler_add(draw_faces, (), 'WINDOW', 'POST_VIEW')


def unregister():
    if _HANDLE[0] is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_HANDLE[0], 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _HANDLE[0] = None
    try:
        bpy.utils.unregister_tool(MCH_TOOL_face_pop)
    except (ValueError, RuntimeError, KeyError):
        pass
    for owner in (bpy.types.Scene, bpy.types.Object):
        if hasattr(owner, 'mch_pop'):
            delattr(owner, 'mch_pop')
    if hasattr(bpy.types.WindowManager, NEW_KEY):
        delattr(bpy.types.WindowManager, NEW_KEY)
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
    _TREES.clear()
