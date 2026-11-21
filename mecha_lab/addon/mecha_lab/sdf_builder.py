"""0.24.280 SDF Builder (user: "SDF 빌더 한번 만들어 줘" - like Cinema 4D's SDF Builder: a stack of parts, each Union /
Subtract / Intersect with a Blend amount; rendered without visible polygons).

An "SDF Builder" object builds one shape out of a stack of parts (any meshes - a box, cylinders, a sculpt):

* each part is turned into a signed distance field (Mesh to SDF Grid), and the fields are combined down the stack:
  Union / Subtract / Intersect, sharp (Blend 0: the SDF boolean) or blended (Blend > 0: a smooth minimum / maximum
  over that distance - soft fillets where they meet, soft grooves where they are cut);
* the result is meshed again (Grid to Mesh): coarse in the viewport (Viewport Voxel), fine in a render (Render Voxel)
  - the render shows no facets at any normal size;
* the parts stay where they are, drawn as wire and left out of renders: move / rotate / scale / edit them and the
  shape follows (live);
* Make Real: the shape at its render resolution as a mesh of its own.

Blender has no direct SDF rendering (Octane's Vectron renders the field itself); a fine voxel at render time is the
closest it gets - the Render Voxel is how fine.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import (BoolProperty, CollectionProperty, EnumProperty, FloatProperty, IntProperty,
                       PointerProperty)
from mathutils import Vector

KEY = 'mch_sdf'                 # on the builder object
PART_KEY = 'mch_sdf_part'       # on a part: the display it had (restored when it leaves the stack)
MOD = 'MCH SDF Builder'
MODES = [('UNION', 'Union', 'Added to the shape'),
         ('SUBTRACT', 'Subtract', 'Cut out of the shape'),
         ('INTERSECT', 'Intersect', 'Only where it and the shape overlap')]


def is_builder(ob):
    return ob is not None and bool(ob.get(KEY))


def builder_of(context, ob):
    """The SDF Builder ``ob`` is (or is a part of), or None."""
    if is_builder(ob):
        return ob
    if ob is None:
        return None
    for b in context.scene.objects:
        if is_builder(b) and any(it.obj == ob for it in b.mch_sdf.items):
            return b
    return None


# ---- the node tree -----------------------------------------------------------------------------------------------

def _sock(ng, name, kind, default=None):
    s = ng.interface.new_socket(name, in_out='INPUT', socket_type=kind)
    if default is not None:
        s.default_value = default
    return s


def build_tree(ob):
    """The builder's own node group from its stack (made again whenever the stack changes)."""
    st = ob.mch_sdf
    name = 'MCH SDF ' + ob.name
    ng = bpy.data.node_groups.get(name)
    if ng is None:
        ng = bpy.data.node_groups.new(name, 'GeometryNodeTree')
    ng.nodes.clear()
    for it in list(ng.interface.items_tree):
        ng.interface.remove(it)
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, L = ng.nodes, ng.links
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    gi.location, go.location = (-1600, 0), (1200, 0)
    # the voxel: coarse in the viewport, fine in a render
    isv = N.new('GeometryNodeIsViewport')
    vox = N.new('GeometryNodeSwitch')
    vox.input_type = 'FLOAT'
    vox.inputs['False'].default_value = max(st.voxel_render, 1e-5)
    vox.inputs['True'].default_value = max(st.voxel_view, 1e-5)
    L.new(isv.outputs[0], vox.inputs['Switch'])
    isv.location, vox.location = (-1400, 400), (-1200, 400)
    items = [it for it in st.items if it.on and it.obj is not None and it.obj.type in {'MESH', 'CURVE', 'FONT'}]
    if not items:
        L.new(gi.outputs['Geometry'], go.inputs['Geometry'])
        return ng
    max_blend = max([it.blend for it in items] + [0.0])
    # the band (voxels each side of the surface) wide enough for the widest blend
    bdiv = N.new('ShaderNodeMath')
    bdiv.operation = 'DIVIDE'
    bdiv.inputs[0].default_value = max_blend
    L.new(vox.outputs[0], bdiv.inputs[1])
    bceil = N.new('ShaderNodeMath')
    bceil.operation = 'CEIL'
    L.new(bdiv.outputs[0], bceil.inputs[0])
    band = N.new('ShaderNodeMath')
    band.operation = 'ADD'
    band.inputs[1].default_value = 3.0
    L.new(bceil.outputs[0], band.inputs[0])
    bdiv.location, bceil.location, band.location = (-1200, 250), (-1050, 250), (-900, 250)
    acc = None          # the sharp shape so far (SDF booleans: inside / outside right everywhere)
    corrs = []          # the blends, each a field added to the sharp shape where two surfaces meet
    y = 0

    def math(op, a_, b_=None, c_=None):
        n_ = N.new('ShaderNodeMath')
        n_.operation = op
        for i_, v_ in enumerate((a_, b_, c_)):
            if v_ is None:
                continue
            if isinstance(v_, (int, float)):
                n_.inputs[i_].default_value = float(v_)
            else:
                L.new(v_, n_.inputs[i_])
        return n_.outputs[0]

    for k, it in enumerate(items):
        oi = N.new('GeometryNodeObjectInfo')
        oi.transform_space = 'RELATIVE'
        oi.inputs['Object'].default_value = it.obj
        m2s = N.new('GeometryNodeMeshToSDFGrid')
        L.new(oi.outputs['Geometry'], m2s.inputs['Mesh'])
        L.new(vox.outputs[0], m2s.inputs['Voxel Size'])
        L.new(band.outputs[0], m2s.inputs['Band Width'])
        x0 = -800 + 360 * k
        oi.location, m2s.location = (x0, -300 - y), (x0, -500 - y)
        g = m2s.outputs['SDF Grid']
        if acc is None:
            acc = g                                   # (the first part starts the shape)
            continue
        bo = N.new('GeometryNodeSDFGridBoolean')
        bo.operation = {'UNION': 'UNION', 'SUBTRACT': 'DIFFERENCE', 'INTERSECT': 'INTERSECT'}[it.mode]
        if bo.operation == 'DIFFERENCE':              # (Union / Intersect: one many-input socket)
            L.new(acc, bo.inputs[0])
            L.new(g, bo.inputs[1])
        else:
            L.new(g, bo.inputs[1])
            L.new(acc, bo.inputs[1])
        bo.location = (x0 + 180, -100)
        if it.blend > 1e-6:
            # the smooth minimum / maximum written as the sharp one plus max(k - |a -/+ b|, 0)^2 / 4k: only where
            # both surfaces are within Blend of each other (grid math on the two fields)
            kk = it.blend
            diff = math('ADD', acc, g) if it.mode == 'SUBTRACT' else math('SUBTRACT', acc, g)
            h = math('MAXIMUM', math('SUBTRACT', kk, math('ABSOLUTE', diff)), 0.0)
            c = math('DIVIDE', math('MULTIPLY', h, h), 4.0 * kk)
            corrs.append(math('MULTIPLY', c, -1.0) if it.mode == 'UNION' else c)
        acc = bo.outputs['Grid']
    sharp = acc
    field = sharp
    for c in corrs:
        field = math('ADD', field, c)
    acc = field
    g2m = N.new('GeometryNodeGridToMesh')
    L.new(acc, g2m.inputs['Grid'])
    g2m.inputs['Adaptivity'].default_value = st.adaptivity
    g2m.inputs['Threshold'].default_value = 0.0      # (the surface itself - the node's default 0.1 grew the shape)
    mesh_out = g2m.outputs['Mesh']
    if corrs:
        # grid math loses the sharp field's inside / outside tiles: stray shells appear deep inside / far outside -
        # every point farther than the widest Blend (+ 2 voxels) from the sharp shape is one of them
        sg = N.new('GeometryNodeSampleGrid')
        L.new(sharp, sg.inputs['Grid'])
        L.new(N.new('GeometryNodeInputPosition').outputs[0], sg.inputs['Position'])
        lim = math('ADD', math('MULTIPLY', vox.outputs[0], 2.0), max_blend)
        far = N.new('FunctionNodeCompare')
        far.data_type = 'FLOAT'
        far.operation = 'GREATER_THAN'
        L.new(math('ABSOLUTE', sg.outputs['Value']), far.inputs[0])
        L.new(lim, far.inputs[1])
        dele = N.new('GeometryNodeDeleteGeometry')
        dele.domain = 'POINT'
        L.new(mesh_out, dele.inputs['Geometry'])
        L.new(far.outputs['Result'], dele.inputs['Selection'])
        mesh_out = dele.outputs['Geometry']
    smooth = N.new('GeometryNodeSetShadeSmooth')
    L.new(mesh_out, smooth.inputs['Geometry'])
    smooth.inputs['Shade Smooth'].default_value = st.smooth
    mat = ob.active_material
    out = smooth.outputs['Geometry']
    if mat is not None:
        sm_ = N.new('GeometryNodeSetMaterial')
        sm_.inputs['Material'].default_value = mat
        L.new(out, sm_.inputs['Geometry'])
        out = sm_.outputs['Geometry']
        sm_.location = (1000, 0)
    L.new(out, go.inputs['Geometry'])
    g2m.location, smooth.location = (700, 0), (850, 0)
    return ng


def rebuild(ob):
    if not is_builder(ob):
        return
    mod = ob.modifiers.get(MOD)
    if mod is None:
        mod = ob.modifiers.new(MOD, 'NODES')
    mod.node_group = build_tree(ob)
    ob.update_tag()


def _upd(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and is_builder(ob):
        rebuild(ob)


class MCH_PG_SDFItem(bpy.types.PropertyGroup):
    obj: PointerProperty(type=bpy.types.Object, name='Part', update=_upd)
    mode: EnumProperty(name='Mode', items=MODES, default='UNION', update=_upd)
    blend: FloatProperty(name='Blend', default=0.0, min=0.0, soft_max=0.5, subtype='DISTANCE', update=_upd,
                         description='How softly it joins the shape (0: a sharp edge; more: a wider soft fillet / groove)')
    on: BoolProperty(name='On', default=True, update=_upd, description='In the shape (off: left out for now)')


class MCH_PG_SDF(bpy.types.PropertyGroup):
    items: CollectionProperty(type=MCH_PG_SDFItem)
    index: IntProperty(default=0, options={'HIDDEN'})
    voxel_view: FloatProperty(name='Viewport Voxel', default=0.02, min=0.0005, soft_max=0.2, subtype='DISTANCE',
                              update=_upd, description='How fine the shape is in the viewport (smaller: finer, slower)')
    voxel_render: FloatProperty(name='Render Voxel', default=0.004, min=0.0002, soft_max=0.05, subtype='DISTANCE',
                                update=_upd, description='How fine the shape is in a render (smaller: smoother - no '
                                                         'facets to see - and heavier)')
    adaptivity: FloatProperty(name='Adaptivity', default=0.0, min=0.0, max=1.0, subtype='FACTOR', update=_upd,
                              description='Fewer faces on the flat areas (0: even everywhere)')
    smooth: BoolProperty(name='Smooth Shading', default=True, update=_upd)


# ---- building ----------------------------------------------------------------------------------------------------

def _size(obs):
    pts = [o.matrix_world @ Vector(c) for o in obs for c in o.bound_box]
    if not pts:
        return 1.0
    lo = Vector((min(p.x for p in pts), min(p.y for p in pts), min(p.z for p in pts)))
    hi = Vector((max(p.x for p in pts), max(p.y for p in pts), max(p.z for p in pts)))
    return max((hi - lo).length, 1e-3)


def _as_part(ob):
    """A part of the stack: wire in the viewport, out of renders (what it had is kept)."""
    if PART_KEY not in ob:
        ob[PART_KEY] = f'{ob.display_type}|{int(ob.hide_render)}'
    ob.display_type = 'WIRE'
    ob.hide_render = True


def release_part(ob):
    v = ob.get(PART_KEY)
    if v is None:
        return
    disp, hr = v.split('|')
    try:
        ob.display_type = disp
    except TypeError:
        ob.display_type = 'TEXTURED'
    ob.hide_render = bool(int(hr))
    del ob[PART_KEY]


def add_parts(ob, parts, mode):
    st = ob.mch_sdf
    have = {it.obj for it in st.items}
    n = 0
    for p in parts:
        if p is None or p == ob or p in have or is_builder(p) or p.type not in {'MESH', 'CURVE', 'FONT'}:
            continue
        it = st.items.add()
        it.obj = p
        it.mode = 'UNION' if not len(st.items) - 1 else mode
        _as_part(p)
        n += 1
    st.index = len(st.items) - 1
    rebuild(ob)
    return n


def new_builder(context, base, others, mode='SUBTRACT'):
    """An SDF Builder of ``base`` (Union) and ``others`` (``mode``)."""
    me = bpy.data.meshes.new('SDF Builder')
    ob = bpy.data.objects.new('SDF Builder', me)
    coll = base.users_collection[0] if base.users_collection else context.scene.collection
    coll.objects.link(ob)
    ob[KEY] = 1
    if base.type == 'MESH' and base.data.materials and base.data.materials[0] is not None:
        me.materials.append(base.data.materials[0])
    size = _size([base] + list(others))
    st = ob.mch_sdf
    st.voxel_view = size / 90.0
    st.voxel_render = size / 450.0
    st.items.clear()
    it = st.items.add()
    it.obj, it.mode = base, 'UNION'
    _as_part(base)
    add_parts(ob, others, mode)
    return ob


def make_real(context, ob):
    """The shape at its render resolution as a mesh of its own; the parts back as they were."""
    st = ob.mch_sdf
    view = st.voxel_view
    st.voxel_view = st.voxel_render                   # (the viewport evaluation at the render voxel)
    context.view_layer.update()
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
    st.voxel_view = view
    parts = [it.obj for it in st.items if it.obj is not None]
    old = ob.data
    ob.data = me
    mod = ob.modifiers.get(MOD)
    if mod is not None:
        ng = mod.node_group
        ob.modifiers.remove(mod)
        if ng is not None and ng.users == 0:
            bpy.data.node_groups.remove(ng)
    del ob[KEY]
    st.items.clear()
    for p in parts:
        release_part(p)
        p.hide_set(True)                              # (the parts stay - hidden - to build it again)
    if old.users == 0:
        bpy.data.meshes.remove(old)
    me.name = ob.name
    return len(me.polygons)


# ---- operators ---------------------------------------------------------------------------------------------------

def _redraw():
    try:
        from . import side_panel
        side_panel.dirty()
    except (ImportError, AttributeError):
        pass


class MCH_OT_sdf_new(bpy.types.Operator):
    """New SDF Builder from the selected parts: the active one is the base (Union), the others Subtract / Union"""
    bl_idname = 'mch.sdf_new'
    bl_label = 'New SDF Builder'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=MODES, default='SUBTRACT')

    @classmethod
    def poll(cls, context):
        a = context.active_object
        return a is not None and a.type in {'MESH', 'CURVE', 'FONT'} and not is_builder(a)

    def execute(self, context):
        base = context.active_object
        others = [o for o in context.selected_objects if o != base and o.type in {'MESH', 'CURVE', 'FONT'}
                  and not is_builder(o)]
        ob = new_builder(context, base, others, self.mode)
        for o in list(context.selected_objects):
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        _redraw()
        self.report({'INFO'}, f'SDF Builder: {len(ob.mch_sdf.items)} parts')
        return {'FINISHED'}


class MCH_OT_sdf_add(bpy.types.Operator):
    """Add the selected parts to the SDF Builder (the builder selected too, or the one last used)"""
    bl_idname = 'mch.sdf_add'
    bl_label = 'Add Selected'
    bl_options = {'REGISTER', 'UNDO'}
    mode: EnumProperty(items=MODES, default='SUBTRACT')
    builder: bpy.props.StringProperty(options={'SKIP_SAVE'})

    def execute(self, context):
        ob = bpy.data.objects.get(self.builder) if self.builder else None
        if ob is None:
            ob = next((o for o in context.selected_objects if is_builder(o)), None) or \
                builder_of(context, context.active_object)
        if not is_builder(ob):
            self.report({'WARNING'}, 'SDF Builder: select the builder (or one of its parts) and the parts to add')
            return {'CANCELLED'}
        n = add_parts(ob, [o for o in context.selected_objects if o != ob], self.mode)
        _redraw()
        self.report({'INFO'}, f'SDF Builder: {n} part(s) added')
        return {'FINISHED'}


class MCH_OT_sdf_item(bpy.types.Operator):
    """A part of the stack: select it / take it out / move it up or down the stack"""
    bl_idname = 'mch.sdf_item'
    bl_label = 'SDF Part'
    bl_options = {'REGISTER', 'UNDO'}
    builder: bpy.props.StringProperty()
    index: IntProperty()
    action: EnumProperty(items=[('SELECT', 'Select', ''), ('REMOVE', 'Remove', ''), ('UP', 'Up', ''),
                                ('DOWN', 'Down', '')], default='SELECT')

    def execute(self, context):
        ob = bpy.data.objects.get(self.builder)
        if not is_builder(ob):
            return {'CANCELLED'}
        st = ob.mch_sdf
        i = self.index
        if not 0 <= i < len(st.items):
            return {'CANCELLED'}
        part = st.items[i].obj
        if self.action == 'SELECT':
            if part is not None:
                for o in list(context.selected_objects):
                    o.select_set(False)
                part.hide_set(False)
                part.select_set(True)
                context.view_layer.objects.active = part
            st.index = i
        elif self.action == 'REMOVE':
            st.items.remove(i)
            if part is not None:
                release_part(part)
            rebuild(ob)
        else:
            j = i - 1 if self.action == 'UP' else i + 1
            if 0 <= j < len(st.items):
                st.items.move(i, j)
                rebuild(ob)
        _redraw()
        return {'FINISHED'}


class MCH_OT_sdf_real(bpy.types.Operator):
    """Make Real: the SDF shape at its render resolution as a mesh of its own (the parts hidden, kept)"""
    bl_idname = 'mch.sdf_real'
    bl_label = 'Make Real'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        ob = builder_of(context, context.active_object)
        if not is_builder(ob):
            return {'CANCELLED'}
        n = make_real(context, ob)
        for o in list(context.selected_objects):
            o.select_set(False)
        ob.select_set(True)
        context.view_layer.objects.active = ob
        _redraw()
        self.report({'INFO'}, f'SDF Builder: a mesh of {n:,} faces')
        return {'FINISHED'}


# ---- the window --------------------------------------------------------------------------------------------------

def draw(layout, context):
    ob = builder_of(context, context.active_object)
    box = layout.box()
    col = box.column(align=True)
    col.label(text='SDF Builder', icon='STRIP_COLOR_06')
    if not is_builder(ob):
        col.label(text='Select the parts (the active one is the base)')
        r = col.row(align=True)
        r.operator('mch.sdf_new', text='New: Others Subtract').mode = 'SUBTRACT'
        r.operator('mch.sdf_new', text='New: Others Union').mode = 'UNION'
        return
    st = ob.mch_sdf
    col.label(text=ob.name)
    for i, it in enumerate(st.items):
        r = col.row(align=True)
        r.prop(it, 'on', text='')
        op = r.operator('mch.sdf_item', text=it.obj.name if it.obj else '(gone)')
        op.builder, op.index, op.action = ob.name, i, 'SELECT'
        r.prop(it, 'mode', text='')
        r.prop(it, 'blend', text='Blend')
        op = r.operator('mch.sdf_item', text='', icon='X')
        op.builder, op.index, op.action = ob.name, i, 'REMOVE'
    r = col.row(align=True)
    op = r.operator('mch.sdf_add', text='Add Selected: Subtract')
    op.mode, op.builder = 'SUBTRACT', ob.name
    op = r.operator('mch.sdf_add', text='Add Selected: Union')
    op.mode, op.builder = 'UNION', ob.name
    box2 = layout.box()
    c2 = box2.column(align=True)
    c2.label(text='Resolution', icon='STRIP_COLOR_04')
    c2.prop(st, 'voxel_view')
    c2.prop(st, 'voxel_render')
    c2.prop(st, 'adaptivity')
    c2.prop(st, 'smooth')
    c2.operator('mch.sdf_real', text='Make Real (render resolution)')


CLASSES = (MCH_PG_SDFItem, MCH_PG_SDF, MCH_OT_sdf_new, MCH_OT_sdf_add, MCH_OT_sdf_item, MCH_OT_sdf_real)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_sdf = PointerProperty(type=MCH_PG_SDF)


def unregister():
    if hasattr(bpy.types.Object, 'mch_sdf'):
        del bpy.types.Object.mch_sdf
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
