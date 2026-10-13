"""Parametric primitives for Mecha Lab.

Geometry Nodes generates box frustums, cylindrical frustums, cones, spheres
and capsules. All settings are stored per object (Object.mch_primitive) and
update node values live. A standard bevel modifier provides edge finish.
No meshes are permanently changed before Apply.
"""
from __future__ import annotations

import math
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

MOD_GN = 'MCH_Primitive_Geometry'
MOD_BEVEL = 'MCH_Primitive_Bevel'
KIND_ITEMS = [
    ('BOX', 'Box', 'Box with independent top and bottom X/Y sizes'),
    ('CYLINDER', 'Cylinder', 'Cylinder with different top and bottom radii'),
    ('SPHERE', 'Sphere', 'UV sphere with adjustable radius and segment count'),
    ('CONE', 'Cone', 'Cone / tapered frustum with adjustable length and radii'),
    ('CAPSULE', 'Capsule', 'Pill shape with adjustable full length and radius'),
]


def _on_change(self, context):
    owner = self.id_data
    if isinstance(owner, bpy.types.Object) and owner.type == 'MESH' and self.active:
        try:
            refresh(owner)
        except (RuntimeError, ValueError, KeyError) as exc:
            print('Mecha Lab primitive update:', exc)


class MCH_PG_Primitive(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    kind: EnumProperty(name='Primitive', items=KIND_ITEMS, default='BOX', update=_on_change)
    bottom_x: FloatProperty(name='Bottom X', default=1, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    bottom_y: FloatProperty(name='Bottom Y', default=1, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    top_x: FloatProperty(name='Top X', default=1, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    top_y: FloatProperty(name='Top Y', default=1, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    height: FloatProperty(name='Height / Length', default=1, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    radius_top: FloatProperty(name='Top Radius', default=0.5, min=0.0, soft_max=10, unit='LENGTH', update=_on_change)
    radius_bottom: FloatProperty(name='Bottom Radius', default=0.5, min=0.001, soft_max=10, unit='LENGTH', update=_on_change)
    radius: FloatProperty(name='Radius', default=0.5, min=0.001, soft_max=10, unit='LENGTH', update=_on_change)
    length: FloatProperty(name='Total Length', default=2, min=0.001, soft_max=20, unit='LENGTH', update=_on_change)
    segments: IntProperty(name='Radial Segments', default=48, min=8, max=256, update=_on_change)
    rings: IntProperty(name='Sphere Rings', default=24, min=8, max=128, update=_on_change)
    bevel_width: FloatProperty(name='Bevel Width', default=0.05, min=0, soft_max=0.5, unit='LENGTH', update=_on_change)
    bevel_segments: IntProperty(name='Bevel Segments', default=3, min=1, max=16, update=_on_change)
    hole_enabled: BoolProperty(name='Through Hole (Z)', default=False, update=_on_change)
    hole_radius: FloatProperty(name='Hole Radius', default=0.18, min=0.001, soft_max=5, unit='LENGTH', update=_on_change)
    hole_offset_x: FloatProperty(name='Hole Offset X', default=0, unit='LENGTH', update=_on_change)
    hole_offset_y: FloatProperty(name='Hole Offset Y', default=0, unit='LENGTH', update=_on_change)


def active_primitive(context):
    ob = context.active_object
    return ob if ob and ob.type == 'MESH' and ob.mch_primitive.active else None


def _node(group, node_type, name):
    n = group.nodes.new(node_type)
    n.name = name
    n.label = name.removeprefix('MCH_').replace('_', ' ').title()
    return n


def _combine(group, name, x, y, z):
    n = _node(group, 'ShaderNodeCombineXYZ', name)
    for i, value in zip(('X','Y','Z'),(x,y,z)):
        n.inputs[i].default_value = value
    return n


def _geometry_group(ob, kind):
    group = bpy.data.node_groups.new('MCH_Primitive_' + kind + '_' + ob.name[:32], 'GeometryNodeTree')
    group.interface.new_socket(name='Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    links = group.links
    p = ob.mch_primitive
    output = _node(group, 'NodeGroupOutput', 'MCH_OUTPUT')
    final = None
    if kind == 'BOX':
        cube = _node(group, 'GeometryNodeMeshCube', 'MCH_BOX')
        cube.inputs['Size'].default_value = (1., 1., 1.)
        pos = _node(group, 'GeometryNodeInputPosition', 'MCH_POSITION')
        sep = _node(group, 'ShaderNodeSeparateXYZ', 'MCH_SEPARATE')
        links.new(pos.outputs['Position'], sep.inputs['Vector'])
        gt = _node(group, 'ShaderNodeMath', 'MCH_TOP_TEST')
        gt.operation = 'GREATER_THAN'
        gt.inputs[1].default_value = -0.000001
        links.new(sep.outputs['Z'], gt.inputs[0])
        mix = _node(group, 'ShaderNodeMix', 'MCH_MIX_SIZES')
        mix.data_type = 'VECTOR'
        links.new(gt.outputs[0], mix.inputs['Factor'])
        bottom = _combine(group, 'MCH_BOTTOM_DIMS', p.bottom_x,p.bottom_y,p.height)
        top = _combine(group, 'MCH_TOP_DIMS', p.top_x,p.top_y,p.height)
        links.new(bottom.outputs['Vector'], mix.inputs['A'])
        links.new(top.outputs['Vector'], mix.inputs['B'])
        mul = _node(group, 'ShaderNodeVectorMath', 'MCH_APPLY_DIMS')
        mul.operation = 'MULTIPLY'
        links.new(pos.outputs['Position'], mul.inputs[0])
        links.new(mix.outputs['Result'], mul.inputs[1])
        sp = _node(group, 'GeometryNodeSetPosition', 'MCH_BOX_TAPER')
        links.new(cube.outputs['Mesh'], sp.inputs['Geometry'])
        links.new(mul.outputs['Vector'], sp.inputs['Position'])
        final = sp.outputs['Geometry']
    elif kind in {'CYLINDER','CONE'}:
        c = _node(group,'GeometryNodeMeshCone','MCH_CONE')
        c.inputs['Vertices'].default_value = p.segments
        c.inputs['Radius Top'].default_value = p.radius_top if kind == 'CYLINDER' else p.radius_top
        c.inputs['Radius Bottom'].default_value = p.radius_bottom
        c.inputs['Depth'].default_value = p.height
        final = c.outputs['Mesh']
    elif kind == 'SPHERE':
        sph = _node(group,'GeometryNodeMeshUVSphere','MCH_SPHERE')
        sph.inputs['Segments'].default_value = p.segments
        sph.inputs['Rings'].default_value = p.rings
        sph.inputs['Radius'].default_value = p.radius
        final = sph.outputs['Mesh']
    elif kind == 'CAPSULE':
        # Start with a sphere, offset the upper/lower halves along Z.
        # A pair of sphere latitude rings bridges the newly introduced
        # cylinder length. This stays a single watertight mesh and avoids
        # fragile union at sphere/cylinder tangencies.
        sphere = _node(group,'GeometryNodeMeshUVSphere','MCH_CAPSULE_SPHERE')
        sphere.inputs['Segments'].default_value = p.segments
        sphere.inputs['Rings'].default_value = max(16, p.rings)
        sphere.inputs['Radius'].default_value = p.radius
        position = _node(group,'GeometryNodeInputPosition','MCH_CAPSULE_POSITION')
        sep = _node(group,'ShaderNodeSeparateXYZ','MCH_CAPSULE_Z')
        links.new(position.outputs['Position'],sep.inputs['Vector'])
        sign = _node(group,'ShaderNodeMath','MCH_CAPSULE_SIGN')
        sign.operation = 'SIGN'
        links.new(sep.outputs['Z'],sign.inputs[0])
        half = _node(group,'ShaderNodeMath','MCH_CAPSULE_HALF_STRAIGHT')
        half.operation = 'MULTIPLY'
        half.inputs[0].default_value = max(0., p.length - 2*p.radius)*0.5
        half.inputs[1].default_value = 1.
        offsetZ = _node(group,'ShaderNodeMath','MCH_CAPSULE_OFFSET_Z')
        offsetZ.operation = 'MULTIPLY'
        links.new(sign.outputs[0],offsetZ.inputs[0])
        links.new(half.outputs[0],offsetZ.inputs[1])
        vec = _combine(group,'MCH_CAPSULE_OFFSET_VEC',0,0,0)
        links.new(offsetZ.outputs[0],vec.inputs['Z'])
        sp = _node(group,'GeometryNodeSetPosition','MCH_CAPSULE_STRETCH')
        links.new(sphere.outputs['Mesh'], sp.inputs['Geometry'])
        links.new(vec.outputs['Vector'],sp.inputs['Offset'])
        final = sp.outputs['Geometry']
    else:
        raise ValueError('Unknown primitive: '+ kind)

    # Z-axis through hole, kept as a live Geometry Nodes boolean rather than
    # modifying source mesh data. A hole only makes geometric sense on types
    # with a continuous solid top/bottom; for capsules/spheres disable it.
    if kind in {'BOX','CYLINDER','CONE'} and p.hole_enabled:
        tool = _node(group, 'GeometryNodeMeshCylinder', 'MCH_HOLE_CYLINDER')
        tool.inputs['Vertices'].default_value = max(32,p.segments)
        tool.inputs['Radius'].default_value = p.hole_radius
        tool.inputs['Depth'].default_value = p.height * 3.0 + 2.0
        tform = _node(group,'GeometryNodeTransform','MCH_HOLE_OFFSET')
        tform.inputs['Translation'].default_value = (p.hole_offset_x,p.hole_offset_y,0.)
        links.new(tool.outputs['Mesh'],tform.inputs['Geometry'])
        booln = _node(group,'GeometryNodeMeshBoolean','MCH_HOLE_BOOLEAN')
        booln.operation = 'DIFFERENCE'
        links.new(final,booln.inputs['Mesh 1'])
        links.new(tform.outputs['Geometry'],booln.inputs['Mesh 2'])
        final = booln.outputs['Mesh']
    if kind in {'SPHERE', 'CAPSULE', 'CYLINDER', 'CONE'}:
        shade = _node(group, 'GeometryNodeSetShadeSmooth', 'MCH_SMOOTH_SIDES')
        shade.domain = 'FACE'
        links.new(final, shade.inputs['Geometry'])
        if kind in {'CYLINDER','CONE'} and not p.hole_enabled:
            # Flat caps, smooth curved sides.
            links.new(c.outputs['Side'],shade.inputs['Selection'])
        final = shade.outputs['Geometry']
    links.new(final,output.inputs['Geometry'])
    return group


def _sync_nodes(ob):
    p = ob.mch_primitive
    mod = ob.modifiers.get(MOD_GN)
    if mod is None:
        mod=ob.modifiers.new(MOD_GN,'NODES')
    gn = mod.node_group
    if gn is None or gn.get('mch_primitive_kind') != p.kind or \
            (p.kind in {'BOX','CYLINDER','CONE'} and bool(gn.get('mch_has_hole',False)) != p.hole_enabled):
        old = gn
        gn = _geometry_group(ob,p.kind)
        gn['mch_primitive_kind'] = p.kind
        gn['mch_has_hole'] = p.hole_enabled if p.kind in {'BOX','CYLINDER','CONE'} else False
        mod.node_group = gn
        if old and old.users == 0:
            bpy.data.node_groups.remove(old)
    elif gn.users > 1:
        mod.node_group = gn.copy()
        gn = mod.node_group
    ns=gn.nodes
    def inp(node,name,val):
        if ns.get(node):ns[node].inputs[name].default_value=val
    if p.kind == 'BOX':
        for prefix,x,y in (('MCH_BOTTOM_DIMS',p.bottom_x,p.bottom_y),('MCH_TOP_DIMS',p.top_x,p.top_y)):
            inp(prefix,'X',x);inp(prefix,'Y',y);inp(prefix,'Z',p.height)
    elif p.kind in {'CYLINDER','CONE'}:
        inp('MCH_CONE','Vertices',p.segments)
        inp('MCH_CONE','Radius Top',p.radius_top)
        inp('MCH_CONE','Radius Bottom',p.radius_bottom)
        inp('MCH_CONE','Depth',p.height)
    elif p.kind == 'SPHERE':
        inp('MCH_SPHERE','Segments',p.segments)
        inp('MCH_SPHERE','Rings',p.rings)
        inp('MCH_SPHERE','Radius',p.radius)
    elif p.kind == 'CAPSULE':
        inp('MCH_CAPSULE_SPHERE','Segments',p.segments)
        inp('MCH_CAPSULE_SPHERE','Rings',max(16,p.rings))
        inp('MCH_CAPSULE_SPHERE','Radius',p.radius)
        inp('MCH_CAPSULE_HALF_STRAIGHT','Value',max(0.,p.length-2*p.radius)*.5)
    if p.kind in {'BOX','CYLINDER','CONE'} and p.hole_enabled:
        inp('MCH_HOLE_CYLINDER','Vertices',max(32,p.segments))
        inp('MCH_HOLE_CYLINDER','Radius',p.hole_radius)
        inp('MCH_HOLE_CYLINDER','Depth',p.height*3+2)
        inp('MCH_HOLE_OFFSET','Translation',(p.hole_offset_x,p.hole_offset_y,0))


def refresh(ob):
    if not ob.mch_primitive.active: return
    _sync_nodes(ob)
    p = ob.mch_primitive
    bevel = ob.modifiers.get(MOD_BEVEL)
    if bevel is None:bevel = ob.modifiers.new(MOD_BEVEL,'BEVEL')
    bevel.width = p.bevel_width
    bevel.segments = p.bevel_segments
    bevel.limit_method = 'ANGLE'
    bevel.angle_limit = math.radians(25)
    bevel.loop_slide = True
    bevel.show_viewport = p.bevel_width > 0.000001
    bevel.show_render = bevel.show_viewport


def _select_one(context, ob):
    for other in context.selected_objects:
        other.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob


class MCH_OT_primitive_create(bpy.types.Operator):
    bl_idname='mch.primitive_create'
    bl_label='Create Parametric Primitive'
    bl_description='Create a live Geometry Nodes primitive with editable dimensions, taper, hole and bevel'
    bl_options={'REGISTER','UNDO'}
    kind: EnumProperty(name='Primitive',items=KIND_ITEMS,default='BOX')

    @classmethod
    def poll(cls,context):return context.mode == 'OBJECT'

    def execute(self,context):
        me=bpy.data.meshes.new('MCH_Primitive_Input')
        ob=bpy.data.objects.new('MCH_'+self.kind.title(),me)
        (context.collection or context.scene.collection).objects.link(ob)
        ob.location=context.scene.cursor.location.copy()
        p=ob.mch_primitive
        src=context.scene.mch_primitive
        # Scene settings are defaults. New primitives start with the selected
        # type but do not inherit any live-object boolean modifier/state.
        for prop in ('bottom_x','bottom_y','top_x','top_y','height','radius_top','radius_bottom',
                     'radius','length','segments','rings','bevel_width','bevel_segments',
                     'hole_enabled','hole_radius','hole_offset_x','hole_offset_y'):
            setattr(p,prop,getattr(src,prop))
        p.active = True
        p.kind = self.kind
        if self.kind == 'CONE': p.radius_top = 0.0
        refresh(ob)
        _select_one(context,ob)
        self.report({'INFO'},'Parametric '+self.kind.title()+' created (live Geometry Nodes)')
        return {'FINISHED'}


class MCH_OT_primitive_switch(bpy.types.Operator):
    bl_idname='mch.primitive_switch'
    bl_label='Switch Primitive Shape'
    bl_description='Change the type of the currently selected live primitive'
    bl_options={'REGISTER','UNDO'}
    kind: EnumProperty(name='Primitive',items=KIND_ITEMS,default='BOX')
    def execute(self,context):
        ob=active_primitive(context)
        if ob is None:
            self.report({'WARNING'},'Select a live Mecha Lab primitive first')
            return {'CANCELLED'}
        p = ob.mch_primitive
        previous = p.kind
        p.kind = self.kind
        if previous != self.kind:
            if self.kind == 'CONE':
                p.radius_top = 0.0
            elif self.kind == 'CYLINDER' and p.radius_top == 0.0:
                p.radius_top = p.radius_bottom
        return {'FINISHED'}


class MCH_MT_primitive_picker(bpy.types.Menu):
    bl_idname = 'MCH_MT_primitive_picker'
    bl_label = 'Primitive Shape'

    def draw(self, context):
        # The five custom preview glyphs are shared with the MECHA LAB tool
        # palette's PreviewCollection.  Keep UI drawing read-only and use
        # native operators for undo/redo when choosing a primitive.
        layout = self.layout
        # 0.14: an even grid (thumbnail on top, name below) instead of rows
        # whose big thumbnails pushed the names into a staircase.  Picking a
        # shape here sets the GHOST shape (Enter places it).
        from . import primitive_place
        st = primitive_place.state(context)
        layout.label(text='Ghost Shape (Enter: add, Alt+Enter: subtract)', icon='MESH_CUBE')
        primitive_place.draw_shape_grid(layout, 'mch.place_shape', st.kind if st else None)
        layout.separator()
        if active_primitive(context):
            layout.label(text='Change Selected Live Primitive', icon='GEOMETRY_NODES')
            draw_kind_grid(layout, 'mch.primitive_switch', context.active_object.mch_primitive.kind)
        else:
            layout.label(text='New Live Parametric Primitive', icon='ADD')
            draw_kind_grid(layout, 'mch.primitive_create')


def draw_kind_grid(layout, operator_id, current=None, columns=3):
    """Even grid of the five live-primitive shapes: thumbnail on top, name below."""
    from .workspace_ui import icon_id
    fallback = {'BOX': 'MESH_CUBE', 'CYLINDER': 'MESH_CYLINDER', 'SPHERE': 'MESH_UVSPHERE',
                'CONE': 'MESH_CONE', 'CAPSULE': 'MESH_CAPSULE'}
    grid = layout.grid_flow(row_major=True, columns=columns, even_columns=True, even_rows=True, align=False)
    for kind, label, _ in KIND_ITEMS:
        cell = grid.column(align=True)
        iid = icon_id('primitive_' + kind.lower())
        if iid:
            cell.template_icon(icon_value=iid, scale=1.6)
        cell.operator(operator_id, text=label, icon='NONE' if iid else fallback[kind],
                      depress=(kind == current)).kind = kind


class MCH_OT_primitive_rmb(bpy.types.Operator):
    bl_idname='mch.primitive_rmb'
    bl_label='Primitive Picker (RMB)'
    bl_options={'INTERNAL'}
    @classmethod
    def poll(cls,context):
        from . import tool_state as ts
        return bool(context.mode == 'OBJECT' and context.area and context.area.type=='VIEW_3D' and
                    ts.is_mecha_workspace(context.workspace) and ts.effective_tool(context)=='PRIMITIVE')
    def invoke(self,context,event):
        bpy.ops.wm.call_menu('INVOKE_DEFAULT',name=MCH_MT_primitive_picker.bl_idname)
        return {'FINISHED'}


class MCH_OT_primitive_apply(bpy.types.Operator):
    bl_idname='mch.primitive_apply'
    bl_label='Apply Primitive'
    bl_description='Bake the evaluated Geometry Nodes + Bevel result into a normal editable mesh'
    bl_options={'REGISTER','UNDO'}
    @classmethod
    def poll(cls,context):return active_primitive(context) is not None and context.mode=='OBJECT'
    def execute(self,context):
        ob=active_primitive(context)
        dg=context.evaluated_depsgraph_get()
        ob_eval=ob.evaluated_get(dg)
        fresh=bpy.data.meshes.new_from_object(ob_eval,preserve_all_data_layers=True,depsgraph=dg)
        if len(fresh.vertices)==0:
            bpy.data.meshes.remove(fresh)
            self.report({'ERROR'},'Evaluated primitive is empty. Nothing changed.')
            return {'CANCELLED'}
        old_mesh=ob.data
        old_group=ob.modifiers.get(MOD_GN)
        group=old_group.node_group if old_group else None
        ob.modifiers.clear()
        ob.data=fresh
        ob.mch_primitive.active = False
        if group and group.users==0:
            bpy.data.node_groups.remove(group)
        if old_mesh and old_mesh.users==0:
            bpy.data.meshes.remove(old_mesh)
        self.report({'INFO'},'Primitive applied as regular mesh')
        return {'FINISHED'}


CLASSES = (MCH_PG_Primitive,MCH_OT_primitive_create,MCH_OT_primitive_switch,
           MCH_MT_primitive_picker,MCH_OT_primitive_rmb,MCH_OT_primitive_apply)
_KM=[]


def register():
    for c in CLASSES:bpy.utils.register_class(c)
    bpy.types.Scene.mch_primitive = bpy.props.PointerProperty(type=MCH_PG_Primitive)
    bpy.types.Object.mch_primitive = bpy.props.PointerProperty(type=MCH_PG_Primitive)
    wm=bpy.context.window_manager
    if wm and wm.keyconfigs.addon:
        km=wm.keyconfigs.addon.keymaps.new(name='3D View',space_type='VIEW_3D')
        item=km.keymap_items.new('mch.primitive_rmb','RIGHTMOUSE','PRESS')
        _KM.append((km,item))


def unregister():
    for km,item in _KM:
        try:km.keymap_items.remove(item)
        except (ReferenceError,RuntimeError):pass
    _KM.clear()
    for t in ('mch_primitive',):
        for owner in (bpy.types.Scene,bpy.types.Object):
            if hasattr(owner,t):delattr(owner,t)
    for c in reversed(CLASSES):bpy.utils.unregister_class(c)
