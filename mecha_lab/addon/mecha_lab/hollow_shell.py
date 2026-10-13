"""Hollow / Shell: keep the outer form, make the inside empty (non-destructive).

Modifier stack on each selected mesh (the mesh geometry is never edited):

    MCH_Hollow_Openings  (Geometry Nodes, only with openings) - deletes the
                          faces marked as openings (face attribute mch_opening)
    MCH_Hollow           (Solidify) wall thickness / direction / even / rim fill;
                          writes the rim vertex group used below
    MCH_Hollow_RimBevel  (Bevel, rim vertex group) rounded rim

Rim Thickness uses Solidify's per-vertex thickness: vertices on open edges /
openings get the rim thickness, the rest the wall thickness (vertex group
mch_hollow_rim on the object).  Self-intersection of the result is checked on
demand and before Apply; the original stays untouched until Apply.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty
from mathutils.bvhtree import BVHTree

MOD_OPEN = 'MCH_Hollow_Openings'
MOD_SHELL = 'MCH_Hollow'
MOD_RIM = 'MCH_Hollow_RimBevel'
ATTR_OPEN = 'mch_opening'
VG_RIM = 'mch_hollow_rim'
VG_RIM_OUT = 'mch_hollow_rim_out'
GROUP = 'MCH Hollow Openings'


def _update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.active:
        sync(ob)


def _p(prop, **kw):
    kw.setdefault('update', _update)
    return prop(**kw)


class MCH_PG_Hollow(bpy.types.PropertyGroup):
    active: BoolProperty(default=False, options={'HIDDEN'})
    wall_thickness: _p(FloatProperty, name='Wall Thickness', default=0.05, min=0.0001, soft_max=1.0, precision=4,
                       unit='LENGTH')
    direction: _p(EnumProperty, name='Thickness Direction', items=[
        ('IN', 'Inward', 'Outer surface kept'), ('OUT', 'Outward', 'Inner surface = original'),
        ('CENTER', 'Center', 'Centred on the original surface')], default='IN')
    even: _p(BoolProperty, name='Even Thickness', default=True)
    rim_fill: _p(BoolProperty, name='Fill Rim', default=True, description='Close the wall at open edges / openings')
    rim_thickness: _p(FloatProperty, name='Rim Thickness', default=0.0, min=0.0, soft_max=1.0, precision=4,
                      unit='LENGTH', description='0 = same as the wall. Otherwise the wall thickness at open edges')
    rim_bevel: _p(FloatProperty, name='Rim Bevel', default=0.0, min=0.0, soft_max=0.2, precision=4, unit='LENGTH')
    rim_bevel_segments: _p(IntProperty, name='Rim Bevel Segments', default=2, min=1, max=16)
    smooth_shading: _p(BoolProperty, name='Smooth Shading', default=True)


def _openings_group():
    g = bpy.data.node_groups.get(GROUP)
    if g is not None:
        return g
    g = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    g.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    g.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    gi = g.nodes.new('NodeGroupInput')
    go = g.nodes.new('NodeGroupOutput')
    attr = g.nodes.new('GeometryNodeInputNamedAttribute')
    attr.data_type = 'BOOLEAN'
    attr.inputs['Name'].default_value = ATTR_OPEN
    dele = g.nodes.new('GeometryNodeDeleteGeometry')
    dele.domain = 'FACE'
    g.links.new(gi.outputs[0], dele.inputs['Geometry'])
    g.links.new(attr.outputs['Attribute'], dele.inputs['Selection'])
    g.links.new(dele.outputs[0], go.inputs[0])
    return g


def has_openings(ob):
    attr = ob.data.attributes.get(ATTR_OPEN)
    return attr is not None and any(d.value for d in attr.data)


def _rim_vertices(me):
    """Vertices on open edges or on the border of opening faces."""
    bm = bmesh.new()
    bm.from_mesh(me)
    try:
        layer = bm.faces.layers.bool.get(ATTR_OPEN)
        rim = set()
        for e in bm.edges:
            faces = [f for f in e.link_faces if not (layer and f[layer])]
            if len(faces) == 1:
                rim.update(v.index for v in e.verts)
        return rim
    finally:
        bm.free()


def sync(ob):
    p = ob.mch_hollow
    mods = ob.modifiers
    gn = mods.get(MOD_OPEN)
    if has_openings(ob):
        if gn is None:
            gn = mods.new(MOD_OPEN, 'NODES')
        gn.node_group = _openings_group()
    elif gn is not None:
        mods.remove(gn)
    shell = mods.get(MOD_SHELL) or mods.new(MOD_SHELL, 'SOLIDIFY')
    shell.offset = {'IN': -1.0, 'OUT': 1.0, 'CENTER': 0.0}[p.direction]
    shell.use_even_offset = p.even
    shell.use_rim = p.rim_fill
    if ob.vertex_groups.get(VG_RIM_OUT) is None:
        ob.vertex_groups.new(name=VG_RIM_OUT)           # Solidify writes the rim into it
    shell.rim_vertex_group = VG_RIM_OUT
    vg = ob.vertex_groups.get(VG_RIM)
    if p.rim_thickness > 0:
        if vg is None:
            vg = ob.vertex_groups.new(name=VG_RIM)
        rim = _rim_vertices(ob.data)
        vg.remove(list(range(len(ob.data.vertices))))
        if rim:
            vg.add(list(rim), 1.0, 'REPLACE')
        big = max(p.rim_thickness, p.wall_thickness)
        shell.thickness = big
        shell.vertex_group = VG_RIM
        if p.rim_thickness >= p.wall_thickness:
            shell.thickness_vertex_group = p.wall_thickness / big       # non-rim verts
            shell.invert_vertex_group = False
        else:
            shell.thickness_vertex_group = p.rim_thickness / big        # rim verts thinner
            shell.invert_vertex_group = True
    else:
        shell.thickness = p.wall_thickness
        shell.vertex_group = ''
        if vg is not None:
            ob.vertex_groups.remove(vg)
    rim_mod = mods.get(MOD_RIM)
    if p.rim_bevel > 0:
        if rim_mod is None:
            rim_mod = mods.new(MOD_RIM, 'BEVEL')
        rim_mod.limit_method = 'VGROUP'
        rim_mod.vertex_group = VG_RIM_OUT
        rim_mod.width = p.rim_bevel
        rim_mod.segments = p.rim_bevel_segments
        rim_mod.use_clamp_overlap = True
    elif rim_mod is not None:
        mods.remove(rim_mod)
    for i, name in enumerate([n for n in (MOD_OPEN, MOD_SHELL, MOD_RIM) if mods.get(n)]):
        idx = mods.find(name)
        if idx != i:
            try:
                mods.move(idx, i)
            except (RuntimeError, ValueError):
                pass
    for poly in ob.data.polygons:
        poly.use_smooth = p.smooth_shading


def too_thick_vertices(ob):
    """Vertices where the inward wall is thicker than the room to the opposite
    surface (the inner skin would turn inside out even without overlaps)."""
    p = ob.mch_hollow
    inward = {'IN': 1.0, 'CENTER': 0.5, 'OUT': 0.0}[p.direction] * max(p.wall_thickness, p.rim_thickness)
    if inward <= 0:
        return 0
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    bm.normal_update()
    tree = BVHTree.FromBMesh(bm)
    bad = 0
    for v in bm.verts:
        n = v.normal
        if n.length < 1e-9:
            continue
        loc, _n, _i, dist = tree.ray_cast(v.co - n * 1e-5, -n)
        if loc is not None and inward > dist * 0.98:
            bad += 1
    bm.free()
    return bad


def self_intersections(context, ob):
    """Problems of the evaluated result: intersecting non-adjacent triangle
    pairs + vertices whose wall is thicker than the room inside."""
    dg = context.evaluated_depsgraph_get()
    me = ob.evaluated_get(dg).to_mesh()
    try:
        bm = bmesh.new()
        bm.from_mesh(me)
        bmesh.ops.triangulate(bm, faces=bm.faces[:])
        tree = BVHTree.FromBMesh(bm)
        bm.faces.ensure_lookup_table()
        count = 0
        for a, b in tree.overlap(tree):
            if a >= b:
                continue
            fa, fb = bm.faces[a], bm.faces[b]
            if set(fa.verts) & set(fb.verts):
                continue
            count += 1
        bm.free()
        return count + too_thick_vertices(ob)
    finally:
        ob.evaluated_get(dg).to_mesh_clear()


def _targets(context):
    return [o for o in context.selected_objects if o.type == 'MESH' and o.library is None]


class MCH_OT_hollow(bpy.types.Operator):
    bl_idname = 'mch.hollow'
    bl_label = 'Hollow / Shell'
    bl_description = 'Make every selected mesh a hollow shell (live Solidify; mesh untouched until Apply)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(_targets(context))

    def execute(self, context):
        d = context.scene.mch_hollow
        n = 0
        for ob in _targets(context):
            p = ob.mch_hollow
            for key in ('wall_thickness', 'direction', 'even', 'rim_fill', 'rim_thickness', 'rim_bevel',
                        'rim_bevel_segments', 'smooth_shading'):
                setattr(p, key, getattr(d, key))
            p.active = True
            sync(ob)
            n += 1
        notes = []
        for ob in _targets(context):
            size = min(ob.dimensions) or 1.0
            if ob.mch_hollow.wall_thickness > size * 0.3:
                k = self_intersections(context, ob)
                if k:
                    notes.append(f'{ob.name}: {k} self-intersections (wall too thick?)')
        self.report({'WARNING' if notes else 'INFO'}, f'Hollow on {n} mesh(es)' + (' | ' + '; '.join(notes) if notes else ''))
        return {'FINISHED'}


class MCH_OT_hollow_openings(bpy.types.Operator):
    bl_idname = 'mch.hollow_openings'
    bl_label = 'Selected Faces = Openings'
    bl_description = 'Edit Mode: mark the selected faces as openings (removed in the shell; geometry untouched)'
    bl_options = {'REGISTER', 'UNDO'}

    clear: BoolProperty(default=False, options={'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        n = 0
        for ob in [o for o in (context.objects_in_mode or [context.active_object]) if o and o.type == 'MESH']:
            bm = bmesh.from_edit_mesh(ob.data)
            layer = bm.faces.layers.bool.get(ATTR_OPEN) or bm.faces.layers.bool.new(ATTR_OPEN)
            for f in bm.faces:
                if self.clear:
                    f[layer] = False
                elif f.select:
                    f[layer] = True
                    n += 1
            bmesh.update_edit_mesh(ob.data)
        bpy.ops.object.mode_set(mode='OBJECT')
        for ob in _targets(context):
            if ob.mch_hollow.active:
                sync(ob)
        bpy.ops.object.mode_set(mode='EDIT')
        self.report({'INFO'}, 'Openings cleared' if self.clear else f'{n} opening face(s)')
        return {'FINISHED'}


def active_hollow(context):
    ob = context.active_object
    return ob if ob is not None and getattr(ob, 'mch_hollow', None) and ob.mch_hollow.active else None


class MCH_OT_hollow_check(bpy.types.Operator):
    bl_idname = 'mch.hollow_check'
    bl_label = 'Check Self-Intersection'
    bl_options = {'REGISTER'}

    @classmethod
    def poll(cls, context):
        return active_hollow(context) is not None

    def execute(self, context):
        k = self_intersections(context, active_hollow(context))
        self.report({'WARNING' if k else 'INFO'}, f'{k} self-intersecting face pairs' if k else 'No self-intersection')
        return {'FINISHED'}


class MCH_OT_hollow_finish(bpy.types.Operator):
    bl_idname = 'mch.hollow_finish'
    bl_label = 'Apply / Reset Hollow'
    bl_options = {'REGISTER', 'UNDO'}

    action: EnumProperty(items=[('APPLY', 'Apply', 'Bake the shell into the mesh'),
                                ('RESET', 'Reset', 'Remove the shell; the mesh is unchanged')])

    @classmethod
    def poll(cls, context):
        return any(o.mch_hollow.active for o in _targets(context)) or active_hollow(context) is not None

    def execute(self, context):
        from . import core_geometry as cg
        obs = [o for o in _targets(context) if o.mch_hollow.active]
        warn = []
        for ob in obs:
            if self.action == 'APPLY':
                k = self_intersections(context, ob)
                if k:
                    warn.append(f'{ob.name}: {k} self-intersections (applied anyway, Ctrl+Z to undo)')
                dg = context.evaluated_depsgraph_get()
                me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
                info = cg.commit_mesh(ob, me)
                bpy.data.meshes.remove(me)
            for name in (MOD_RIM, MOD_SHELL, MOD_OPEN):
                m = ob.modifiers.get(name)
                if m is not None:
                    ob.modifiers.remove(m)
            for vgn in (VG_RIM, VG_RIM_OUT):
                vg = ob.vertex_groups.get(vgn)
                if vg is not None:
                    ob.vertex_groups.remove(vg)
            if self.action == 'RESET' and ob.data.attributes.get(ATTR_OPEN) is not None:
                ob.data.attributes.remove(ob.data.attributes[ATTR_OPEN])
            ob.mch_hollow.active = False
        self.report({'WARNING' if warn else 'INFO'}, f'{self.action.title()}: {len(obs)} mesh(es)' +
                    (' | ' + '; '.join(warn) if warn else ''))
        return {'FINISHED'}


def draw(layout, context):
    ob = active_hollow(context)
    p = ob.mch_hollow if ob is not None else context.scene.mch_hollow
    row = layout.row()
    row.scale_y = 1.4
    row.operator('mch.hollow', icon='MOD_SOLIDIFY')
    box = layout.box()
    box.label(text=('SHELL: ' + ob.name) if ob else 'Settings for the next shell', icon='MESH_DATA')
    col = box.column(align=True)
    col.prop(p, 'wall_thickness')
    box.row(align=True).prop(p, 'direction', expand=True)
    box.prop(p, 'even')
    col = box.column(align=True)
    col.prop(p, 'rim_fill')
    col.prop(p, 'rim_thickness')
    col.prop(p, 'rim_bevel')
    col.prop(p, 'rim_bevel_segments')
    box.prop(p, 'smooth_shading')
    row = layout.row(align=True)
    row.operator('mch.hollow_openings', icon='FACESEL')
    row.operator('mch.hollow_openings', text='Clear', icon='X').clear = True
    if ob is not None:
        layout.operator('mch.hollow_check', icon='ERROR')
        row = layout.row(align=True)
        row.operator('mch.hollow_finish', text='Apply', icon='CHECKMARK').action = 'APPLY'
        row.operator('mch.hollow_finish', text='Reset', icon='LOOP_BACK').action = 'RESET'


CLASSES = (MCH_PG_Hollow, MCH_OT_hollow, MCH_OT_hollow_openings, MCH_OT_hollow_check, MCH_OT_hollow_finish)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_hollow = PointerProperty(type=MCH_PG_Hollow)
    bpy.types.Scene.mch_hollow = PointerProperty(type=MCH_PG_Hollow)


def unregister():
    for owner in (bpy.types.Scene, bpy.types.Object):
        if hasattr(owner, 'mch_hollow'):
            delattr(owner, 'mch_hollow')
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
