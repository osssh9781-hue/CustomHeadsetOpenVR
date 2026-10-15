"""0.23.26 Fold Patch: an X / Y crease patch (elbow / knee folds) you place on a mesh, like a decal.

+ Add (N panel > Fold Patch) puts a patch on the active mesh at the 3D cursor (snapped to the surface):
a small handle object (move / rotate / scale it with G / R / S) and a live Geometry Nodes modifier on the
mesh that pushes the surface along its normals.  The fold lines are a baked height image (pattern +
thickness; regenerated when those change), everything else is live in the modifier:

    Size        half width of the patch (world)          Depth   how far the folds stand out (- = in)
    Wrap        radius around a limb (0 = flat)          Fade    soft edge (part of the size)
    Taper       "<" - narrower toward one side (- = the other side)
    Mirror X    the same patch on the other side of the mesh (its local X)

It is not part of the Cloth Plate inputs, so Overall Scale does not change it.  Several patches can sit on
one mesh; each has its own handle, image and modifier.
"""
from __future__ import annotations

import math

import bpy
from bpy.app.handlers import persistent
from mathutils import Matrix, Vector

GROUP = 'MCH_FoldPatch'
MOD_PREFIX = 'MCH_FoldPatch'
HANDLE_KEY = 'mch_fold_target'
VERSION = 1
RES = 512

# patterns: strokes in patch units (-1 .. 1, u along the patch X, s around / patch Y), traced from the
# user's drawings (0.23.26)
_WRAP = [[(-0.498, 0.547), (-0.366, 0.285), (-0.247, 0.079), (-0.128, -0.09), (-0.032, -0.352), (0.087, -0.652), (0.183, -0.859)],
         [(-0.18, 0.63), (-0.128, 0.397), (-0.092, 0.097), (-0.056, -0.127), (-0.02, -0.334)],
         [(0.039, 0.585), (0.016, 0.322), (-0.02, 0.229), (-0.056, 0.116)],
         [(0.016, 0.06), (0.111, -0.127), (0.195, -0.277), (0.242, -0.502), (0.266, -0.69), (0.271, -0.952)],
         [(0.123, -0.259), (0.087, -0.577)],
         [(0.187, 0.54), (0.254, 0.21), (0.326, -0.052), (0.331, -0.277), (0.309, -0.465)],
         [(0.409, 0.69), (0.35, 0.397), (0.319, 0.191)],
         [(0.498, 0.952), (0.469, 0.585), (0.469, 0.097), (0.386, -0.24), (0.35, -0.54), (0.333, -0.877)]]
_XY = [[(-0.952, -0.108), (-0.898, -0.346), (-0.844, -0.563)],
         [(-0.498, 0.606), (-0.649, 0.346), (-0.693, 0.087), (-0.584, -0.271), (-0.455, -0.649)],
         [(-0.335, 0.866), (-0.26, 0.519), (-0.195, 0.162), (-0.227, -0.216), (-0.271, -0.649)],
         [(-0.292, 0.693), (-0.097, 0.346)],
         [(0.13, 0.844), (0.022, 0.563), (-0.097, 0.346)],
         [(-0.097, 0.346), (-0.173, 0.054)],
         [(0.065, 0.519), (0.216, 0.238), (0.39, -0.087), (0.455, -0.487), (0.39, -0.909)],
         [(0.173, 0.13), (0.022, -0.087), (-0.087, -0.346), (-0.173, -0.628)],
         [(0.303, 0.368), (0.53, 0.152), (0.66, -0.216)],
         [(0.714, 0.866), (0.768, 0.433), (0.693, 0.054), (0.639, -0.216)],
         [(0.855, -0.216), (0.909, -0.433), (0.952, -0.649)]]
_STAR = [[(-0.85, 0.05), (-0.48, 0.03), (-0.10, 0.00)], [(-0.10, 0.00), (0.22, 0.22), (0.55, 0.45)],
         [(-0.10, 0.00), (0.25, -0.20), (0.60, -0.40)], [(-0.55, -0.55), (-0.15, -0.02), (0.25, 0.50)],
         [(-0.60, 0.50), (-0.20, -0.02), (0.20, -0.55)], [(0.15, 0.25), (0.48, 0.15), (0.80, 0.05)],
         [(0.10, -0.20), (0.40, -0.12), (0.70, -0.05)]]
PATTERNS = (('WRAP', 'Wrap Folds', _WRAP), ('XY', 'X / Y Folds', _XY), ('STAR', 'Crease Star', _STAR))
BASE_WIDTH = {'WRAP': 0.55, 'XY': 1.0, 'STAR': 1.0}      # same Thickness = similar folds on every pattern


def _smooth(stroke, per=6):
    """Catmull-Rom through the drawn points: round folds, no kinks at the points."""
    pts = [Vector((x, y)) for x, y in stroke]
    if len(pts) < 3:
        return [(p.x, p.y) for p in pts]
    out = []
    ext = [pts[0] * 2 - pts[1]] + pts + [pts[-1] * 2 - pts[-2]]
    for i in range(1, len(ext) - 2):
        p0, p1, p2, p3 = ext[i - 1], ext[i], ext[i + 1], ext[i + 2]
        for k in range(per):
            t = k / per
            t2, t3 = t * t, t * t * t
            q = 0.5 * ((2 * p1) + (-p0 + p2) * t + (2 * p0 - 5 * p1 + 4 * p2 - p3) * t2 + (-p0 + 3 * p1 - 3 * p2 + p3) * t3)
            out.append((q.x, q.y))
    out.append((pts[-1].x, pts[-1].y))
    return out


def height_map(pattern, thickness=1.0, flip=False, res=RES):
    """The fold heights on a res x res grid over -1 .. 1 (numpy, row = s, column = u)."""
    import numpy as np
    strokes = dict((a, c) for a, _b, c in PATTERNS).get(pattern, _WRAP)
    g = np.linspace(-1.0, 1.0, res)
    U, V = np.meshgrid(g, g)
    if flip:
        U = -U
    K = 14.0
    acc = np.zeros_like(U)
    n = 0
    for stroke in strokes:
        pts = _smooth(stroke)
        m = len(pts) - 1
        # one fold = the nearest point along the whole stroke (pieces that overlap made beads before)
        dmin = np.full(U.shape, np.inf)
        tmin = np.zeros(U.shape)
        for i in range(m):
            (ax, ay), (bx, by) = pts[i], pts[i + 1]
            dx, dy = bx - ax, by - ay
            L2 = dx * dx + dy * dy or 1e-12
            t = np.clip(((U - ax) * dx + (V - ay) * dy) / L2, 0.0, 1.0)
            dist = np.hypot(U - (ax + t * dx), V - (ay + t * dy))
            closer = dist < dmin
            dmin = np.where(closer, dist, dmin)
            tmin = np.where(closer, (i + t) / m, tmin)
        taper = np.sin(np.pi * np.clip(tmin, 0.0, 1.0)) ** 0.9
        w = (0.020 + 0.032 * taper) * thickness * BASE_WIDTH.get(pattern, 1.0)
        prof = taper * (np.exp(-(dmin / w) ** 2) - 0.3 * np.exp(-(dmin / (2.6 * w)) ** 2))
        acc += np.exp(K * prof)
        n += 1
    return np.log(acc / max(n, 1)) / K


def image_name(handle):
    return 'MCH_FoldPatch_' + handle.name


def ensure_image(handle):
    """Bake the handle's pattern into its float image (made again when the pattern / thickness changes)."""
    import numpy as np
    p = handle.mch_fold
    name = image_name(handle)
    img = bpy.data.images.get(name)
    if img is None or tuple(img.size) != (RES, RES):
        if img is not None:
            bpy.data.images.remove(img)
        img = bpy.data.images.new(name, RES, RES, alpha=False, float_buffer=True)
    h = height_map(p.pattern, p.thickness, p.flip).astype(np.float32)
    px = np.zeros((RES, RES, 4), dtype=np.float32)
    px[..., 0] = h
    px[..., 3] = 1.0
    img.pixels.foreach_set(px.ravel())
    img.update()
    img.use_fake_user = False
    handle['mch_fold_baked'] = f'{p.pattern}|{p.thickness:.4f}|{int(p.flip)}'
    return img


def _link(g, a, b):
    g.links.new(a, b)


def _math(N, g, op, a=None, b=None, va=None, vb=None):
    n = N.new('ShaderNodeMath')
    n.operation = op
    if a is not None:
        _link(g, a, n.inputs[0])
    elif va is not None:
        n.inputs[0].default_value = va
    if b is not None:
        _link(g, b, n.inputs[1])
    elif vb is not None:
        n.inputs[1].default_value = vb
    return n.outputs[0]


def _height_at(N, g, gi, pos, xform):
    """Fold height (with fade) for an object-space position: handle space -> wrap / taper -> image."""
    tp = N.new('FunctionNodeTransformPoint')
    _link(g, pos, tp.inputs['Vector'])
    _link(g, xform, tp.inputs['Transform'])
    sep = N.new('ShaderNodeSeparateXYZ')
    _link(g, tp.outputs['Vector'], sep.inputs[0])
    x, y, z = sep.outputs['X'], sep.outputs['Y'], sep.outputs['Z']
    R = gi.outputs['Wrap']
    # around a limb: s = R * atan2(y, z + R); flat (R = 0): s = y
    zr = _math(N, g, 'ADD', z, R)
    ang = _math(N, g, 'ARCTAN2', y, zr)
    s_wrap = _math(N, g, 'MULTIPLY', ang, R)
    use_wrap = _math(N, g, 'GREATER_THAN', R, vb=1e-6)
    s = _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', s_wrap, use_wrap),
              _math(N, g, 'MULTIPLY', y, _math(N, g, 'SUBTRACT', va=1.0, b=use_wrap)))
    # how far off the surface the point is (only the near layer gets folds)
    radial = _math(N, g, 'SQRT', _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', y, y), _math(N, g, 'MULTIPLY', zr, zr)))
    off_w = _math(N, g, 'ABSOLUTE', _math(N, g, 'SUBTRACT', radial, R))
    off = _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', off_w, use_wrap),
                _math(N, g, 'MULTIPLY', _math(N, g, 'ABSOLUTE', z), _math(N, g, 'SUBTRACT', va=1.0, b=use_wrap)))
    size = _math(N, g, 'MAXIMUM', gi.outputs['Size'], vb=1e-6)
    near = _math(N, g, 'LESS_THAN', off, _math(N, g, 'MULTIPLY', size, vb=0.6))
    a = _math(N, g, 'DIVIDE', x, size)
    b = _math(N, g, 'DIVIDE', s, size)
    # "<" taper: across the patch the s range narrows toward one side
    tap = gi.outputs['Taper']
    side = _math(N, g, 'MULTIPLY', _math(N, g, 'SUBTRACT', va=1.0, b=_math(N, g, 'MULTIPLY', a, _math(N, g, 'SIGN', tap))),
                 vb=0.5)
    side = _math(N, g, 'MINIMUM', _math(N, g, 'MAXIMUM', side, vb=0.0), vb=1.0)
    sc = _math(N, g, 'SUBTRACT', va=1.0, b=_math(N, g, 'MULTIPLY', _math(N, g, 'ABSOLUTE', tap), side))
    b = _math(N, g, 'DIVIDE', b, _math(N, g, 'MAXIMUM', sc, vb=0.05))
    uv = N.new('ShaderNodeCombineXYZ')
    _link(g, _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', a, vb=0.5), vb=0.5), uv.inputs[0])
    _link(g, _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', b, vb=0.5), vb=0.5), uv.inputs[1])
    tex = N.new('GeometryNodeImageTexture')
    tex.interpolation = 'Cubic'
    tex.extension = 'CLIP'
    _link(g, gi.outputs['Image'], tex.inputs['Image'])
    _link(g, uv.outputs[0], tex.inputs['Vector'])
    sc_col = N.new('FunctionNodeSeparateColor')
    _link(g, tex.outputs['Color'], sc_col.inputs[0])
    hgt = sc_col.outputs['Red']
    # soft edge: 1 inside, 0 at the rim (Fade = width of the soft part)
    r = _math(N, g, 'SQRT', _math(N, g, 'ADD', _math(N, g, 'MULTIPLY', a, a), _math(N, g, 'MULTIPLY', b, b)))
    fw = _math(N, g, 'MAXIMUM', gi.outputs['Fade'], vb=1e-3)
    t = _math(N, g, 'DIVIDE', _math(N, g, 'SUBTRACT', va=1.0, b=r), fw)
    t = _math(N, g, 'MINIMUM', _math(N, g, 'MAXIMUM', t, vb=0.0), vb=1.0)
    fade = _math(N, g, 'MULTIPLY', _math(N, g, 'MULTIPLY', t, t), _math(N, g, 'SUBTRACT', va=3.0,
                                                                      b=_math(N, g, 'MULTIPLY', t, vb=2.0)))
    return _math(N, g, 'MULTIPLY', _math(N, g, 'MULTIPLY', hgt, fade), near)


def build_group():
    g = bpy.data.node_groups.get(GROUP)
    if g is not None and g.get('mch_version') == VERSION:
        return g
    if g is None:
        g = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    g.nodes.clear()
    for item in list(g.interface.items_tree):
        g.interface.remove(item)
    ii = g.interface
    ii.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ii.new_socket('Handle', in_out='INPUT', socket_type='NodeSocketObject')
    ii.new_socket('Image', in_out='INPUT', socket_type='NodeSocketImage')
    for name, default in (('Size', 0.25), ('Depth', 0.02), ('Wrap', 0.0), ('Fade', 0.35), ('Taper', 0.0)):
        sock = ii.new_socket(name, in_out='INPUT', socket_type='NodeSocketFloat')
        sock.default_value = default
    mx = ii.new_socket('Mirror X', in_out='INPUT', socket_type='NodeSocketBool')
    mx.default_value = False
    ii.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N = g.nodes
    gi = N.new('NodeGroupInput')
    go = N.new('NodeGroupOutput')
    info = N.new('GeometryNodeObjectInfo')
    info.transform_space = 'RELATIVE'
    _link(g, gi.outputs['Handle'], info.inputs['Object'])
    inv = N.new('FunctionNodeInvertMatrix')
    _link(g, info.outputs['Transform'], inv.inputs['Matrix'])
    pos = N.new('GeometryNodeInputPosition').outputs[0]
    h = _height_at(N, g, gi, pos, inv.outputs['Matrix'])
    # Mirror X: the same patch at the mirrored position (the mesh's own X)
    mpos = N.new('ShaderNodeVectorMath')
    mpos.operation = 'MULTIPLY'
    mpos.inputs[1].default_value = (-1.0, 1.0, 1.0)
    _link(g, pos, mpos.inputs[0])
    hm = _height_at(N, g, gi, mpos.outputs[0], inv.outputs['Matrix'])
    h = _math(N, g, 'ADD', h, _math(N, g, 'MULTIPLY', hm, gi.outputs['Mirror X']))
    off = N.new('ShaderNodeVectorMath')
    off.operation = 'SCALE'
    _link(g, N.new('GeometryNodeInputNormal').outputs['Normal'], off.inputs[0])
    _link(g, _math(N, g, 'MULTIPLY', h, gi.outputs['Depth']), off.inputs['Scale'])
    sp = N.new('GeometryNodeSetPosition')
    _link(g, gi.outputs['Geometry'], sp.inputs['Geometry'])
    _link(g, off.outputs[0], sp.inputs['Offset'])
    _link(g, sp.outputs['Geometry'], go.inputs['Geometry'])
    g['mch_version'] = VERSION
    return g


def _ident(g, name):
    for item in g.interface.items_tree:
        if getattr(item, 'in_out', '') == 'INPUT' and item.name == name:
            return item.identifier
    raise KeyError(name)


def modifier_of(handle):
    target = bpy.data.objects.get(handle.get(HANDLE_KEY, ''))
    if target is None:
        return None, None
    for m in target.modifiers:
        if m.type == 'NODES' and m.name.startswith(MOD_PREFIX) and m.node_group is not None:
            try:
                if m[_ident(m.node_group, 'Handle')] == handle:
                    return target, m
            except KeyError:
                continue
    return target, None


def patches_of(target):
    out = []
    for m in target.modifiers:
        if m.type == 'NODES' and m.name.startswith(MOD_PREFIX) and m.node_group is not None:
            try:
                h = m[_ident(m.node_group, 'Handle')]
            except KeyError:
                h = None
            if h is not None:
                out.append((m, h))
    return out


def push(handle):
    """Handle settings -> its modifier (and the image when pattern / thickness changed)."""
    target, mod = modifier_of(handle)
    if mod is None:
        return
    p = handle.mch_fold
    key = f'{p.pattern}|{p.thickness:.4f}|{int(p.flip)}'
    img = bpy.data.images.get(image_name(handle))
    if img is None or handle.get('mch_fold_baked') != key or not img.has_data:
        img = ensure_image(handle)
    g = mod.node_group
    mod[_ident(g, 'Image')] = img
    for name, val in (('Size', p.size), ('Depth', p.depth), ('Wrap', p.wrap), ('Fade', p.fade), ('Taper', p.taper)):
        mod[_ident(g, name)] = float(val)
    mod[_ident(g, 'Mirror X')] = bool(p.mirror)
    handle.empty_display_size = p.size
    target.update_tag()
    try:
        for win in bpy.context.window_manager.windows:
            for area in win.screen.areas:
                if area.type == 'VIEW_3D':
                    area.tag_redraw()
    except (AttributeError, TypeError, ReferenceError):
        pass


def _update(self, context):
    handle = self.id_data
    if isinstance(handle, bpy.types.Object):
        push(handle)


class MCH_PG_FoldPatch(bpy.types.PropertyGroup):
    pattern: bpy.props.EnumProperty(name='Pattern', items=[(a, b, '') for a, b, _c in PATTERNS], default='WRAP',
                                    update=_update)
    flip: bpy.props.BoolProperty(name='Flip', default=False, update=_update, description='Pattern mirrored left / right')
    size: bpy.props.FloatProperty(name='Size', default=0.25, min=0.001, soft_max=5.0, unit='LENGTH', update=_update,
                                  description='Half width of the patch')
    depth: bpy.props.FloatProperty(name='Depth', default=0.02, soft_min=-0.2, soft_max=0.2, unit='LENGTH',
                                   update=_update, description='How far the folds stand out (negative = in)')
    thickness: bpy.props.FloatProperty(name='Thickness', default=1.8, min=0.2, soft_max=5.0, update=_update,
                                       description='Fold width')
    wrap: bpy.props.FloatProperty(name='Wrap', default=0.0, min=0.0, soft_max=2.0, unit='LENGTH', update=_update,
                                  description='Radius of the limb the patch wraps around (0 = flat)')
    fade: bpy.props.FloatProperty(name='Fade', default=0.35, min=0.01, max=1.0, update=_update,
                                  description='Soft edge, as a part of the size')
    taper: bpy.props.FloatProperty(name='Taper <', default=0.0, min=-0.95, max=0.95, update=_update,
                                   description='Narrower toward one side like "<" (negative = the other side)')
    mirror: bpy.props.BoolProperty(name='Mirror X', default=False, update=_update,
                                   description='The same patch on the other side of the mesh (its local X)')


def _surface_frame(context, target, point):
    """Nearest surface point + normal of the evaluated target (world), and the limb radius behind it."""
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    ev = target.evaluated_get(dg)
    bvh = BVHTree.FromObject(ev, dg)
    inv = target.matrix_world.inverted_safe()
    loc, nrm, _i, _d = bvh.find_nearest(inv @ point)
    if loc is None:
        return point, Vector((0, 0, 1)), 0.0
    nrm = nrm.normalized()
    hit, _n2, _i2, dist = bvh.ray_cast(loc - nrm * 1e-4, -nrm)
    radius = dist * 0.5 if hit is not None and dist else 0.0
    mw = target.matrix_world
    return mw @ loc, (mw.to_3x3() @ nrm).normalized(), radius * max(mw.to_scale())


def add_patch(context, target, point=None):
    if target is None or target.type != 'MESH':
        raise RuntimeError('Select the mesh (a Cloth Plate or a body) to put the patch on.')
    point = context.scene.cursor.location.copy() if point is None else Vector(point)
    loc, nrm, radius = _surface_frame(context, target, point)
    size = max(target.dimensions) * 0.2 or 0.25
    handle = bpy.data.objects.new(f'FoldPatch_{target.name}', None)
    handle.empty_display_type = 'CIRCLE'
    handle.empty_display_size = size
    for coll in target.users_collection:
        coll.objects.link(handle)
    x = Vector((1, 0, 0))
    if abs(x.dot(nrm)) > 0.9:
        x = Vector((0, 1, 0))
    x = (x - nrm * x.dot(nrm)).normalized()
    y = nrm.cross(x)
    m = Matrix((x, y, nrm)).transposed().to_4x4()
    m.translation = loc
    handle.matrix_world = m
    handle[HANDLE_KEY] = target.name
    p = handle.mch_fold
    p['size'] = size
    p['depth'] = size * 0.08
    if 0 < radius < size * 4:
        p['wrap'] = radius
        p['size'] = radius * 2.9                 # the wrap pattern goes a bit more than half way round
        p['depth'] = radius * 0.16
    mod = target.modifiers.new(f'{MOD_PREFIX}', 'NODES')
    mod.node_group = build_group()
    mod[_ident(mod.node_group, 'Handle')] = handle
    # before a Cloth Plate's thickness (Solidify): both sides move together
    shell = next((i for i, mm in enumerate(target.modifiers) if mm.type == 'SOLIDIFY'), None)
    if shell is not None:
        with context.temp_override(object=target, active_object=target):
            bpy.ops.object.modifier_move_to_index(modifier=mod.name, index=shell)
    push(handle)
    for o in context.selected_objects:
        o.select_set(False)
    handle.select_set(True)
    context.view_layer.objects.active = handle
    return handle


def remove_patch(handle):
    target, mod = modifier_of(handle)
    if mod is not None:
        target.modifiers.remove(mod)
    img = bpy.data.images.get(image_name(handle))
    if img is not None:
        bpy.data.images.remove(img)
    bpy.data.objects.remove(handle, do_unlink=True)


def active_target(context):
    ob = context.active_object
    if ob is None:
        return None
    if HANDLE_KEY in ob:
        return bpy.data.objects.get(ob[HANDLE_KEY])
    return ob if ob.type == 'MESH' else None


def active_handle(context):
    ob = context.active_object
    return ob if ob is not None and HANDLE_KEY in ob else None


class MCH_OT_fold_patch_add(bpy.types.Operator):
    """Add a fold patch on the selected mesh at the 3D cursor (move / rotate / scale its handle)"""
    bl_idname = 'mch.fold_patch_add'
    bl_label = 'Add Fold Patch'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            h = add_patch(context, active_target(context))
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'Fold patch on {h[HANDLE_KEY]} - move / rotate / scale the handle')
        return {'FINISHED'}


class MCH_OT_fold_patch_remove(bpy.types.Operator):
    """Remove this fold patch (its handle and modifier)"""
    bl_idname = 'mch.fold_patch_remove'
    bl_label = 'Remove Fold Patch'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    def execute(self, context):
        h = bpy.data.objects.get(self.name) if self.name else active_handle(context)
        if h is None or HANDLE_KEY not in h:
            return {'CANCELLED'}
        target = bpy.data.objects.get(h[HANDLE_KEY])
        remove_patch(h)
        if target is not None:
            for o in context.selected_objects:
                o.select_set(False)
            target.select_set(True)
            context.view_layer.objects.active = target
        return {'FINISHED'}


class MCH_OT_fold_patch_select(bpy.types.Operator):
    """Select this patch's handle"""
    bl_idname = 'mch.fold_patch_select'
    bl_label = 'Select Fold Patch'
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    def execute(self, context):
        h = bpy.data.objects.get(self.name)
        if h is None:
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        h.hide_set(False)
        h.select_set(True)
        context.view_layer.objects.active = h
        return {'FINISHED'}


class MCH_OT_fold_patch_pattern(bpy.types.Operator):
    """Previous / next fold pattern"""
    bl_idname = 'mch.fold_patch_pattern'
    bl_label = 'Fold Pattern'
    bl_options = {'REGISTER', 'UNDO'}
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        h = active_handle(context)
        if h is None:
            return {'CANCELLED'}
        ids = [a for a, _b, _c in PATTERNS]
        # the cycle runs through every pattern and its flipped version
        seq = [(a, f) for a in ids for f in (False, True)]
        p = h.mch_fold
        i = seq.index((p.pattern, p.flip)) if (p.pattern, p.flip) in seq else 0
        a, f = seq[(i + self.step) % len(seq)]
        p['flip'] = f
        p.pattern = a                                   # one update (image baked once)
        return {'FINISHED'}


class MCH_OT_fold_patch_apply(bpy.types.Operator):
    """Make all fold patches of this mesh permanent (modifiers applied, handles removed)"""
    bl_idname = 'mch.fold_patch_apply'
    bl_label = 'Apply Fold Patches'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        target = active_target(context)
        if target is None:
            return {'CANCELLED'}
        for mod, h in patches_of(target):
            with context.temp_override(object=target, active_object=target, selected_objects=[target],
                                       selected_editable_objects=[target]):
                bpy.ops.object.modifier_apply(modifier=mod.name)
            img = bpy.data.images.get(image_name(h))
            if img is not None:
                bpy.data.images.remove(img)
            bpy.data.objects.remove(h, do_unlink=True)
        return {'FINISHED'}


def draw(layout, context):
    target = active_target(context)
    col = layout.column()
    row = col.row(align=True)
    row.scale_y = 1.4
    row.operator('mch.fold_patch_add', text='+ Add Fold Patch', icon='ADD')
    if target is None:
        col.label(text='Select a mesh, place the 3D cursor, + Add', icon='INFO')
        return
    patches = patches_of(target)
    if not patches:
        col.label(text=f'{target.name}: no patches yet (3D cursor = where)', icon='INFO')
        return
    box = col.box()
    box.label(text=f'{target.name}: {len(patches)} patch(es)', icon='MOD_CLOTH')
    act = active_handle(context)
    for _mod, h in patches:
        r = box.row(align=True)
        r.operator('mch.fold_patch_select', text=h.name, depress=(h == act), icon='EMPTY_AXIS').name = h.name
        r.operator('mch.fold_patch_remove', text='', icon='X').name = h.name
    if act is not None and act.get(HANDLE_KEY) == target.name:
        p = act.mch_fold
        b = col.box()
        r = b.row(align=True)
        r.operator('mch.fold_patch_pattern', text='', icon='TRIA_LEFT').step = -1
        r.label(text=dict((a, bb) for a, bb, _c in PATTERNS)[p.pattern] + ('  (flipped)' if p.flip else ''))
        r.operator('mch.fold_patch_pattern', text='', icon='TRIA_RIGHT').step = 1
        c = b.column(align=True)
        c.prop(p, 'size')
        c.prop(p, 'depth')
        c.prop(p, 'thickness', slider=True)
        c.prop(p, 'taper', slider=True)
        c.prop(p, 'fade', slider=True)
        c.prop(p, 'wrap')
        b.prop(p, 'mirror', toggle=True, icon='MOD_MIRROR')
        b.label(text='Move / rotate / scale: G / R / S on the handle', icon='INFO')
    col.operator('mch.fold_patch_apply', icon='CHECKMARK')


class MCH_PT_fold_patch(bpy.types.Panel):
    """Separate from the main Mecha Lab panel (0.23.26)"""
    bl_idname = 'MCH_PT_fold_patch'
    bl_label = 'Fold Patch'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 4

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        ob = context.active_object
        if ob is not None and HANDLE_KEY in ob:
            return True
        return context.mode == 'OBJECT' and (ts.hud_for(context, {'WRINKLE'}) or ts.sidebar_select(context))

    def draw(self, context):
        draw(self.layout, context)


@persistent
def _on_load(_dummy=None):
    """The baked images are made again from the handles after opening a file."""
    for ob in bpy.data.objects:
        if HANDLE_KEY in ob:
            try:
                push(ob)
            except (ReferenceError, RuntimeError, AttributeError):
                pass


CLASSES = (MCH_PG_FoldPatch, MCH_OT_fold_patch_add, MCH_OT_fold_patch_remove, MCH_OT_fold_patch_select,
           MCH_OT_fold_patch_pattern, MCH_OT_fold_patch_apply, MCH_PT_fold_patch)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_fold = bpy.props.PointerProperty(type=MCH_PG_FoldPatch)
    if _on_load not in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.append(_on_load)


def unregister():
    if _on_load in bpy.app.handlers.load_post:
        bpy.app.handlers.load_post.remove(_on_load)
    if hasattr(bpy.types.Object, 'mch_fold'):
        del bpy.types.Object.mch_fold
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
