"""0.20 Cloth Wrinkle: draw a lasso on a mesh -> a separate cloth layer with
procedural wrinkles (Geometry Nodes, live until Apply).

The patch is built like an Armor Plate (new clean faces laid on the surface,
the mesh you drew on is never changed), then put in its own frame (local Z =
the average surface normal) so the node group can work in the tangent plane:

    Padding   quilted pillows between stitched seams (diamond quilting)
    Denim     thin sharp creases bunching up, with small secondary folds
    Leather   few thick, round, heavy folds

Inputs (HUD sliders, all live): Type, Strength, Scale, Direction, Seed,
Detail (subdivision), Edge Soft (wrinkles fade out toward the border),
Thickness (cloth layer).  Apply bakes it to a plain mesh.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import EnumProperty, IntProperty
from mathutils import Matrix, Vector

from . import core_geometry as cg

GROUP = 'MCH_ClothWrinkle'
MOD = 'MCH_Wrinkle'
MOD_SHELL = 'MCH_WrinkleShell'
COLL = 'Cloth Wrinkles'
EDGE_ATTR = 'mch_edge_dist'
TYPES = (('PADDING', 'Padding', 'Quilted pillows between stitched seams'),
         ('DENIM', 'Denim', 'Thin sharp creases with small secondary folds'),
         ('LEATHER', 'Leather', 'Few thick, round, heavy folds'))
TYPE_IDS = tuple(t[0] for t in TYPES)
# name, socket, default, min, max
INPUTS = (('Type', 'NodeSocketInt', 0, 0, 2),
          ('Strength', 'NodeSocketFloat', 0.03, -1.0, 1.0),
          ('Scale', 'NodeSocketFloat', 0.25, 0.001, 100.0),
          ('Direction', 'NodeSocketFloat', 0.0, -10.0, 10.0),
          ('Seed', 'NodeSocketInt', 1, 0, 100000),
          ('Detail', 'NodeSocketInt', 1, 0, 3),
          ('Edge Soft', 'NodeSocketFloat', 0.1, 0.0, 100.0),
          ('Lift', 'NodeSocketFloat', 0.0, -100.0, 100.0))
VERSION = 4


# -----------------------------------------------------------------------------
# Node group
# -----------------------------------------------------------------------------


def _math(nodes, links, op, a=None, b=None, va=None, vb=None, clamp=False):
    n = nodes.new('ShaderNodeMath')
    n.operation = op
    n.use_clamp = clamp
    for i, (src, val) in enumerate(((a, va), (b, vb))):
        if src is not None:
            links.new(src, n.inputs[i])
        elif val is not None:
            n.inputs[i].default_value = val
    return n.outputs[0]


def build_group():
    """The wrinkle node group (rebuilt when an older version is found)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get('mch_version') == VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for name, sock, default, lo, hi in INPUTS:
        it = ng.interface.new_socket(name, in_out='INPUT', socket_type=sock)
        it.default_value = default
        it.min_value, it.max_value = lo, hi
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gin = N.new('NodeGroupInput')
    gout = N.new('NodeGroupOutput')
    I = {name: gin.outputs[name] for name, *_r in INPUTS}

    sub = N.new('GeometryNodeSubdivideMesh')
    L.new(gin.outputs['Geometry'], sub.inputs['Mesh'])
    L.new(I['Detail'], sub.inputs['Level'])

    # tangent-plane coordinates: rotate around local Z by Direction, divide by Scale, seed offset
    pos = N.new('GeometryNodeInputPosition')
    rot = N.new('ShaderNodeVectorRotate')
    rot.rotation_type = 'Z_AXIS'
    L.new(pos.outputs[0], rot.inputs['Vector'])
    L.new(_math(N, L, 'MULTIPLY', I['Direction'], vb=-1.0), rot.inputs['Angle'])
    inv_s = _math(N, L, 'DIVIDE', vb=None, va=1.0, b=I['Scale'])
    scl = N.new('ShaderNodeVectorMath')
    scl.operation = 'SCALE'
    L.new(rot.outputs[0], scl.inputs[0])
    L.new(inv_s, scl.inputs['Scale'])
    seedv = N.new('ShaderNodeCombineXYZ')
    sx = _math(N, L, 'MULTIPLY', I['Seed'], vb=17.123)
    sy = _math(N, L, 'MULTIPLY', I['Seed'], vb=-9.731)
    L.new(sx, seedv.inputs[0])
    L.new(sy, seedv.inputs[1])
    uv = N.new('ShaderNodeVectorMath')
    uv.operation = 'ADD'
    L.new(scl.outputs[0], uv.inputs[0])
    L.new(seedv.outputs[0], uv.inputs[1])
    sep = N.new('ShaderNodeSeparateXYZ')
    L.new(uv.outputs[0], sep.inputs[0])
    X, Y = sep.outputs[0], sep.outputs[1]

    def noise(vec, scale, detail=2.0, rough=0.5):
        n = N.new('ShaderNodeTexNoise')
        n.inputs['Scale'].default_value = scale
        n.inputs['Detail'].default_value = detail
        n.inputs['Roughness'].default_value = rough
        L.new(vec, n.inputs['Vector'])
        return n.outputs['Fac']

    # ---- Padding: diamond quilting -> pillows |sin(u) sin(v)|^0.5, seams at 0
    k = 2.0 * math.pi
    u = _math(N, L, 'ADD', X, Y)
    v = _math(N, L, 'SUBTRACT', X, Y)
    su = _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', u, vb=k * 0.7071))
    sv = _math(N, L, 'SINE', _math(N, L, 'MULTIPLY', v, vb=k * 0.7071))
    pillow = _math(N, L, 'POWER', _math(N, L, 'ABSOLUTE', _math(N, L, 'MULTIPLY', su, sv)), vb=0.45)
    pad = _math(N, L, 'ADD', pillow, _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 3.0), vb=0.15))

    # ---- Denim: thin sharp creases across X, wobbling, + small folds
    warp = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(uv.outputs[0], 0.7, 3.0), vb=0.5), vb=4.0)
    phase = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', X, vb=k * 1.1), warp)
    crease = _math(N, L, 'POWER', _math(N, L, 'ABSOLUTE', _math(N, L, 'SINE', phase)), vb=4.0)
    amp = noise(uv.outputs[0], 0.5, 1.0)                                   # bunching: some creases stronger
    small = _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 5.0, 3.0, 0.55), vb=0.15)
    den = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', crease, _math(N, L, 'MULTIPLY', amp, vb=1.6)), small)

    # ---- Leather: few thick round folds
    lwarp = _math(N, L, 'MULTIPLY', _math(N, L, 'SUBTRACT', noise(uv.outputs[0], 0.45, 2.0), vb=0.5), vb=2.5)
    lphase = _math(N, L, 'ADD', _math(N, L, 'MULTIPLY', X, vb=k * 0.55), lwarp)
    lfold = _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', _math(N, L, 'SINE', lphase), vb=1.0), vb=0.5)
    lfold = _math(N, L, 'POWER', lfold, vb=1.3)
    lea = _math(N, L, 'MULTIPLY', _math(N, L, 'ADD', lfold, _math(N, L, 'MULTIPLY', noise(uv.outputs[0], 2.0, 2.0),
                                                                    vb=0.1)), vb=2.2)

    sw = N.new('GeometryNodeIndexSwitch')
    sw.data_type = 'FLOAT'
    while len(sw.index_switch_items) < 3:                # the node starts with 2 items
        sw.index_switch_items.new()
    L.new(I['Type'], sw.inputs['Index'])
    for i, src in enumerate((pad, den, lea)):
        L.new(src, sw.inputs[i + 1])

    # fade toward the border (distance attribute written at creation)
    attr = N.new('GeometryNodeInputNamedAttribute')
    attr.data_type = 'FLOAT'
    attr.inputs['Name'].default_value = EDGE_ATTR
    soft = _math(N, L, 'MAXIMUM', I['Edge Soft'], vb=1e-6)
    t = _math(N, L, 'DIVIDE', attr.outputs['Attribute'], soft, clamp=True)
    mask = _math(N, L, 'MULTIPLY', t, _math(N, L, 'SUBTRACT', va=3.0, b=_math(N, L, 'MULTIPLY', t, vb=2.0)))
    mask = _math(N, L, 'MULTIPLY', mask, t)                                  # smoothstep 3t^2 - 2t^3

    h = _math(N, L, 'MULTIPLY', _math(N, L, 'MULTIPLY', sw.outputs[0], I['Strength']), mask)
    h = _math(N, L, 'ADD', h, I['Lift'])                                     # layer height above the surface
    nrm = N.new('GeometryNodeInputNormal')
    off = N.new('ShaderNodeVectorMath')
    off.operation = 'SCALE'
    L.new(nrm.outputs[0], off.inputs[0])
    L.new(h, off.inputs['Scale'])
    setp = N.new('GeometryNodeSetPosition')
    L.new(sub.outputs['Mesh'], setp.inputs['Geometry'])
    L.new(off.outputs[0], setp.inputs['Offset'])
    smooth = N.new('GeometryNodeSetShadeSmooth')
    L.new(setp.outputs[0], smooth.inputs['Geometry'])
    L.new(smooth.outputs[0], gout.inputs['Geometry'])
    ng['mch_version'] = VERSION
    return ng


# -----------------------------------------------------------------------------
# Modifier inputs
# -----------------------------------------------------------------------------


def _ident(name):
    ng = build_group()
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def get_input(ob, name):
    mod = ob.modifiers.get(MOD)
    return None if mod is None else mod[_ident(name)]


def set_input(ob, name, value):
    mod = ob.modifiers.get(MOD)
    if mod is None:
        return
    mod[_ident(name)] = value
    ob.update_tag()
    try:
        mod.show_viewport = mod.show_viewport          # nudges the depsgraph
    except AttributeError:
        pass


def is_wrinkle(ob):
    return ob is not None and ob.type == 'MESH' and ob.modifiers.get(MOD) is not None and bool(ob.get('mch_wrinkle'))


def active_wrinkle(context):
    ob = getattr(context, 'active_object', None)
    return ob if is_wrinkle(ob) else None


# -----------------------------------------------------------------------------
# Create
# -----------------------------------------------------------------------------


def _edge_distances(bm):
    """Distance of every vertex from the patch border (along the edges)."""
    import heapq
    dist = {v: math.inf for v in bm.verts}
    heap = []
    for v in bm.verts:
        if v.is_boundary:
            dist[v] = 0.0
            heap.append((0.0, v.index, v))
    heapq.heapify(heap)
    while heap:
        d, _i, v = heapq.heappop(heap)
        if d > dist[v]:
            continue
        for e in v.link_edges:
            w = e.other_vert(v)
            nd = d + e.calc_length()
            if nd < dist[w]:
                dist[w] = nd
                heapq.heappush(heap, (nd, w.index, w))
    return dist


def perform_wrinkle(context, loops, projector, wtype=None):
    """Lasso -> new cloth wrinkle layer.  Returns a report; raises cg.CutError
    with the scene unchanged."""
    from . import armor_plate as ap
    scene = context.scene
    st = scene.mch_wrinkle
    groups = cg.prepare_loops(loops)
    target = ap.pick_surface(context, projector, groups)
    if target is None:
        raise cg.CutError('Draw the wrinkles over a mesh.')
    pts, tris, _nb = ap.screen_patch(groups, st.spacing)
    if not tris:
        raise cg.CutError('The outline is too small.')
    bvh, _wv, _polys = ap._target_bvh(context, target)
    cos, nrms, missing = ap.project_patch(pts, projector, bvh)
    cen = sum(cos, Vector()) / len(cos)
    n = sum(nrms, Vector())
    n = n.normalized() if n.length > 1e-9 else -projector.view_dir
    t = n.orthogonal().normalized()
    # long side of the patch = local X (Direction 0 runs the folds across it)
    flat = [(c - cen) - n * (c - cen).dot(n) for c in cos]
    sxx = sum(f.dot(t) ** 2 for f in flat)
    b0 = n.cross(t)
    syy = sum(f.dot(b0) ** 2 for f in flat)
    sxy = sum(f.dot(t) * f.dot(b0) for f in flat)
    ang = 0.5 * math.atan2(2 * sxy, sxx - syy)
    x = (t * math.cos(ang) + b0 * math.sin(ang)).normalized()
    y = n.cross(x).normalized()
    frame = Matrix.Identity(4)
    for r in range(3):
        frame[r][0], frame[r][1], frame[r][2], frame[r][3] = x[r], y[r], n[r], cen[r]
    inv = frame.inverted()
    size = max((max(f.length for f in flat) * 2.0), 1e-6)
    cos_l = [inv @ c for c in cos]
    nrm_l = [(inv.to_3x3() @ nn).normalized() for nn in nrms]
    region = ap.build_region(pts, tris, cos_l, nrm_l, quads=True)
    bm = bmesh.new()
    try:
        bm.from_mesh(region)
        bm.verts.ensure_lookup_table()
        dist = _edge_distances(bm)
        vals = [min(dist.get(v, 0.0), 1e6) for v in bm.verts]
        bm.to_mesh(region)
    finally:
        bm.free()
    attr = region.attributes.new(EDGE_ATTR, 'FLOAT', 'POINT')
    attr.data.foreach_set('value', vals)
    region.name = target.name + '_Wrinkle'
    for mat in target.data.materials:
        region.materials.append(mat)
    ob = bpy.data.objects.new(region.name, region)
    from . import face_extract as fx
    fx._parts_collection(context, COLL).objects.link(ob)
    ob.matrix_world = frame
    ob['mch_wrinkle'] = target.name
    mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = build_group()
    wtype = wtype or st.wtype
    set_input(ob, 'Type', TYPE_IDS.index(wtype))
    set_input(ob, 'Strength', size * st.strength)
    set_input(ob, 'Scale', size * st.scale)
    set_input(ob, 'Edge Soft', size * 0.08)
    set_input(ob, 'Seed', 1)
    set_input(ob, 'Detail', 1)
    set_input(ob, 'Lift', size * st.lift)
    shell = ob.modifiers.new(MOD_SHELL, 'SOLIDIFY')
    shell.thickness = size * st.thickness
    shell.offset = 1.0
    shell.use_even_offset = True
    ob['mch_wrinkle_size'] = size
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    extra = f' | {len(missing)} point(s) past the surface edge' if missing else ''
    return f'Cloth wrinkles "{ob.name}" on {target.name} ({dict((a, b) for a, b, _c in TYPES)[wtype]}){extra}'


def dense_mesh(context, ob, extra=2, limit=1_500_000):
    """High Poly of a live layer: the same wrinkles with a finer Detail (no subdivision blur)."""
    if not is_wrinkle(ob):
        return None
    old = int(get_input(ob, 'Detail'))
    dg = context.evaluated_depsgraph_get()
    base = len(ob.evaluated_get(dg).data.polygons) or 1
    lv = old
    while lv < min(3, old + extra) and base * 4 ** (lv + 1 - old) <= limit:
        lv += 1
    try:
        set_input(ob, 'Detail', lv)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        return bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    finally:
        set_input(ob, 'Detail', old)


def apply_wrinkle(context, ob):
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    ob.modifiers.clear()
    ob.data = me
    me.name = old.name
    for key in ('mch_wrinkle', 'mch_wrinkle_size'):
        if key in ob:
            del ob[key]
    if old.users == 0:
        bpy.data.meshes.remove(old)


# -----------------------------------------------------------------------------
# Settings / operators
# -----------------------------------------------------------------------------


class MCH_PG_Wrinkle(bpy.types.PropertyGroup):
    wtype: EnumProperty(name='Wrinkle Type', items=TYPES, default='DENIM',
                        description='Kind of cloth wrinkles for the next layer')
    spacing: IntProperty(name='Face Size (px)', default=8, min=3, max=40,
                         description='Mesh density of the cloth layer on screen (smaller = finer wrinkles)')
    strength: bpy.props.FloatProperty(name='Depth', default=0.03, soft_min=-0.2, soft_max=0.2,
                                      description='Wrinkle depth (part of the patch size)')
    scale: bpy.props.FloatProperty(name='Scale', default=0.18, min=0.005, soft_max=1.0,
                                   description='Wrinkle spacing (part of the patch size)')
    thickness: bpy.props.FloatProperty(name='Thickness', default=0.01, min=0.0, soft_max=0.1,
                                       description='Cloth layer thickness (part of the patch size)')
    lift: bpy.props.FloatProperty(name='Height', default=0.002, soft_min=-0.05, soft_max=0.2,
                                  description='Height of the cloth layer above the surface (part of the patch size)')


class MCH_OT_wrinkle_type(bpy.types.Operator):
    """Next wrinkle type: Padding > Denim > Leather (the selected layer changes at once)"""
    bl_idname = 'mch.wrinkle_type'
    bl_label = 'Wrinkle Type'
    bl_options = {'REGISTER', 'UNDO'}
    step: IntProperty(default=1, options={'SKIP_SAVE'})

    def execute(self, context):
        st = context.scene.mch_wrinkle
        i = (TYPE_IDS.index(st.wtype) + self.step) % len(TYPE_IDS)
        st.wtype = TYPE_IDS[i]
        ob = active_wrinkle(context)
        if ob is not None:
            set_input(ob, 'Type', i)
        return {'FINISHED'}


class MCH_OT_wrinkle_reroll(bpy.types.Operator):
    """New random wrinkles (next seed)"""
    bl_idname = 'mch.wrinkle_reroll'
    bl_label = 'Reroll Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        set_input(ob, 'Seed', int(get_input(ob, 'Seed')) + 1)
        return {'FINISHED'}


class MCH_OT_wrinkle_apply(bpy.types.Operator):
    """Apply: the cloth layer becomes a plain mesh with the current wrinkles"""
    bl_idname = 'mch.wrinkle_apply'
    bl_label = 'Apply Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        apply_wrinkle(context, active_wrinkle(context))
        return {'FINISHED'}


class MCH_OT_wrinkle_remove(bpy.types.Operator):
    """Remove the cloth layer you just drew"""
    bl_idname = 'mch.wrinkle_remove'
    bl_label = 'Remove Wrinkles'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_wrinkle(context) is not None

    def execute(self, context):
        ob = active_wrinkle(context)
        target = bpy.data.objects.get(ob.get('mch_wrinkle', ''))
        me = ob.data
        bpy.data.objects.remove(ob)
        if me.users == 0:
            bpy.data.meshes.remove(me)
        if target is not None and target.name in context.view_layer.objects:
            target.select_set(True)
            context.view_layer.objects.active = target
        return {'FINISHED'}


# -----------------------------------------------------------------------------
# HUD
# -----------------------------------------------------------------------------

HUD_BUTTONS = (('apply', 'CHECKMARK', 'mch.wrinkle_apply', {}, 'Apply'),
               ('cancel', 'X', 'mch.wrinkle_remove', {}, 'Remove'),
               ('prev', 'TRIA_LEFT', 'mch.wrinkle_type', {'step': -1}, 'Previous type'),
               ('next', 'TRIA_RIGHT', 'mch.wrinkle_type', {'step': 1}, 'Next type'),
               ('reroll', 'FILE_REFRESH', 'mch.wrinkle_reroll', {}, 'New random wrinkles'))
# key, label, input / modifier field, lo, hi, kind
SLIDERS = (('lift', 'Height', 'Lift', -50, 200, 'SIZE'),
           ('strength', 'Depth', 'Strength', -100, 100, 'SIZE'),
           ('scale', 'Scale', 'Scale', 1, 100, 'SIZE'),
           ('direction', 'Direction', 'Direction', -180, 180, 'DEG'),
           ('edge', 'Edge Soft', 'Edge Soft', 0, 50, 'SIZE'),
           ('detail', 'Detail', 'Detail', 0, 3, 'INT'),
           ('thickness', 'Thickness', 'THICK', 0, 50, 'SIZE'))


def slider_spec(context, key, ob=None):
    ob = ob or active_wrinkle(context)
    label, name, lo, hi, kind = next((l, nm, a, b, k) for kk, l, nm, a, b, k in SLIDERS if kk == key)
    size = float(ob.get('mch_wrinkle_size', 1.0)) or 1.0
    if name == 'THICK':
        mod = ob.modifiers.get(MOD_SHELL)
        cur = mod.thickness if mod else 0.0
        v = int(round(cur / size * 1000.0))

        def setter(val):
            m = ob.modifiers.get(MOD_SHELL)
            if m is not None:
                m.thickness = val / 1000.0 * size
        return label, v, lo, hi, setter, f'{label}  {cur:.3f}'
    cur = get_input(ob, name)
    if kind == 'DEG':
        v = int(round(math.degrees(cur)))
        return label, v, lo, hi, (lambda val: set_input(ob, name, math.radians(val))), f'{label}  {v} deg'
    if kind == 'INT':
        v = int(cur)
        return label, v, lo, hi, (lambda val: set_input(ob, name, int(val))), f'{label}  {v}'
    v = int(round(cur / size * 1000.0))
    return label, v, lo, hi, (lambda val: set_input(ob, name, val / 1000.0 * size)), f'{label}  {cur:.3f}'


def hud_layout(screen_pts, region_w, region_h, btn=30.0, gap=6.0, slider_w=104.0, slider_h=20.0):
    pts = [p for p in screen_pts if p is not None]
    if not pts:
        return {}
    x = min(max(max(p[0] for p in pts) + btn * 1.2, btn), region_w - slider_w - btn)
    step = btn + gap
    total = step * 3 + (slider_h + gap) * len(SLIDERS)
    top = min(max((max(p[1] for p in pts) + min(p[1] for p in pts)) / 2 + total / 2, total), region_h - btn)
    out = {'apply': (x, top), 'cancel': (x, top - step), 'prev': (x, top - 2 * step),
           'next': (x + step, top - 2 * step), 'reroll': (x + 2 * step, top - 2 * step)}
    y = top - 3 * step
    for key, *_r in SLIDERS:
        out['slider_' + key] = (x - btn / 2 + slider_w / 2, y + btn / 2 - slider_h / 2)
        y -= slider_h + gap
    return out


def _hud_current(context):
    from .primitive_hud import anchored, release_anchor
    try:
        from . import tool_state as ts
        if context.mode != 'OBJECT' or not ts.is_mecha_workspace(getattr(context, 'workspace', None)):
            return None, {}
    except (AttributeError, TypeError):
        return None, {}
    ob = active_wrinkle(context)
    region, rv3d = context.region, context.region_data
    if ob is None:
        release_anchor('wrinkle')
        return None, {}
    if region is None or rv3d is None:
        return None, {}
    from bpy_extras import view3d_utils
    ui = context.preferences.system.ui_scale
    pts = []
    for c in ob.bound_box:
        q = view3d_utils.location_3d_to_region_2d(region, rv3d, ob.matrix_world @ Vector(c))
        pts.append(None if q is None else (q[0] / ui, q[1] / ui))
    return ob, anchored('wrinkle', ob.name, region, hud_layout(pts, region.width / ui, region.height / ui))


class MCH_GT_wrinkle_slider(bpy.types.Gizmo):
    bl_idname = 'MCH_GT_wrinkle_slider'
    __slots__ = ('shape', 'init_x', 'init_value', 'key')

    def setup(self):
        if not hasattr(self, 'shape'):
            from .primitive_hud import _RECT
            self.shape = self.new_custom_shape('TRIS', _RECT)

    def draw(self, context):
        self.draw_custom_shape(self.shape)

    def draw_select(self, context, select_id):
        self.draw_custom_shape(self.shape, select_id=select_id)

    def invoke(self, context, event):
        self.init_x = event.mouse_region_x
        self.init_value = slider_spec(context, self.key)[1]
        return {'RUNNING_MODAL'}

    def modal(self, context, event, tweak):
        from .primitive_hud import slider_value
        spec = slider_spec(context, self.key)
        step = 20.0 if self.key == 'detail' else 3.0
        v = slider_value(self.init_value, event.mouse_region_x - self.init_x, step_px=step, lo=spec[2], hi=spec[3])
        if v != spec[1]:
            spec[4](v)
        if context.area:
            context.area.header_text_set(slider_spec(context, self.key)[5])
        return {'RUNNING_MODAL'}

    def exit(self, context, cancel):
        if context.area:
            context.area.header_text_set(None)
        if cancel:
            slider_spec(context, self.key)[4](self.init_value)
        else:
            try:
                bpy.ops.ed.undo_push(message='Wrinkle ' + self.key)
            except RuntimeError:
                pass


class MCH_GGT_wrinkle_hud(bpy.types.GizmoGroup):
    bl_idname = 'MCH_GGT_wrinkle_hud'
    bl_label = 'Cloth Wrinkle HUD'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'WINDOW'
    bl_options = {'PERSISTENT', 'SCALE'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and active_wrinkle(context) is not None

    def setup(self, context):
        self.items = {}
        for name, icon, op, props, _label in HUD_BUTTONS:
            gz = self.gizmos.new('GIZMO_GT_button_2d')
            gz.icon = icon
            gz.draw_options = {'BACKDROP', 'OUTLINE'}
            t = gz.target_set_operator(op)
            for k, v in props.items():
                setattr(t, k, v)
            gz.color = (1.0, 0.62, 0.16) if name == 'apply' else (0.17, 0.19, 0.23)
            gz.alpha = 0.92
            gz.color_highlight = (0.32, 0.35, 0.41)
            gz.alpha_highlight = 1.0
            self.items[name] = gz
        for key, *_r in SLIDERS:
            gz = self.gizmos.new(MCH_GT_wrinkle_slider.bl_idname)
            gz.key = key
            gz.color = (0.24, 0.27, 0.32)
            gz.alpha = 0.95
            gz.color_highlight = (0.36, 0.40, 0.47)
            gz.alpha_highlight = 1.0
            gz.use_draw_scale = False
            self.items['slider_' + key] = gz

    def draw_prepare(self, context):
        _ob, lay = _hud_current(context)
        ui = context.preferences.system.ui_scale
        for name, gz in self.items.items():
            pos = lay.get(name)
            gz.hide = pos is None
            if pos is None:
                continue
            if name.startswith('slider_'):
                gz.matrix_basis = Matrix.Translation((pos[0] * ui, pos[1] * ui, 0.0)) @ Matrix.Diagonal(
                    (52.0 * ui, 10.0 * ui, 1.0, 1.0))
                continue
            gz.scale_basis = 15.0
            gz.matrix_basis[0][3] = pos[0] * ui
            gz.matrix_basis[1][3] = pos[1] * ui


_label_handle = None


def _draw_labels():
    try:
        context = bpy.context
        ob, lay = _hud_current(context)
        if ob is None or not lay:
            return
        import blf
        ui = context.preferences.system.ui_scale
        blf.size(0, 11 * ui)
        tname = TYPES[max(0, min(2, int(get_input(ob, 'Type'))))][1]
        for key, text in (('apply', 'Apply'), ('cancel', 'Remove'), ('reroll', tname)):
            x, y = lay[key]
            blf.color(0, *((1.0, 0.62, 0.16) if key == 'apply' else (0.85, 0.87, 0.9)), 1.0)
            blf.position(0, (x + 21) * ui, (y - 4) * ui, 0)
            blf.draw(0, text)
        for key, *_r in SLIDERS:
            x, y = lay['slider_' + key]
            text = slider_spec(context, key, ob)[5]
            w, _h = blf.dimensions(0, text)
            blf.color(0, 1.0, 1.0, 1.0, 1.0)
            blf.position(0, x * ui - w / 2, (y - 4) * ui, 0)
            blf.draw(0, text)
    except Exception:          # never break viewport drawing
        pass


def draw(layout, context):
    st = context.scene.mch_wrinkle
    box = layout.box()
    box.label(text='CLOTH WRINKLE: draw on a mesh', icon='MOD_CLOTH')
    box.row(align=True).prop(st, 'wtype', expand=True)
    col = box.column(align=True)
    col.prop(st, 'lift', slider=True)
    col.prop(st, 'strength', slider=True)
    col.prop(st, 'scale', slider=True)
    col.prop(st, 'thickness', slider=True)
    col.prop(st, 'spacing')
    ob = active_wrinkle(context)
    if ob is not None:
        sub = box.box()
        sub.label(text=f'LIVE: {ob.name} (until Apply)', icon='MOD_CLOTH')
        mod = ob.modifiers.get(MOD)
        c = sub.column(align=True)
        for name, *_r in INPUTS:
            c.prop(mod, f'["{_ident(name)}"]', text=name)
        r = sub.row(align=True)
        r.scale_y = 1.3
        r.operator('mch.wrinkle_apply', text='Apply', icon='CHECKMARK')
        r.operator('mch.wrinkle_remove', text='Remove', icon='X')
    c = box.column(align=True)
    c.scale_y = 0.8
    c.label(text='Draw a lasso on a mesh: a separate cloth layer', icon='INFO')
    c.label(text='Wrinkles are Geometry Nodes: change them live')
    c.label(text='Apply bakes; the mesh you draw on is not changed')


CLASSES = (MCH_PG_Wrinkle, MCH_OT_wrinkle_type, MCH_OT_wrinkle_reroll, MCH_OT_wrinkle_apply, MCH_OT_wrinkle_remove,
           MCH_GT_wrinkle_slider, MCH_GGT_wrinkle_hud)


def register():
    global _label_handle
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_wrinkle = bpy.props.PointerProperty(type=MCH_PG_Wrinkle)
    if not bpy.app.background and _label_handle is None:
        _label_handle = bpy.types.SpaceView3D.draw_handler_add(_draw_labels, (), 'WINDOW', 'POST_PIXEL')


def unregister():
    global _label_handle
    if _label_handle is not None:
        try:
            bpy.types.SpaceView3D.draw_handler_remove(_label_handle, 'WINDOW')
        except (ValueError, RuntimeError):
            pass
        _label_handle = None
    if hasattr(bpy.types.Scene, 'mch_wrinkle'):
        del bpy.types.Scene.mch_wrinkle
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
