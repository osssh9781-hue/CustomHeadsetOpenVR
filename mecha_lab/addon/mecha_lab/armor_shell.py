"""0.24.80 Armor Shell: the whole surface of a part extracted as a closed shell around it - a gap off the body, a
thickness outward - to cut into armour plates (Cut / Split lasso on it).

The shell is a new object (``<part>_Shell``) holding a copy of the part's mesh and one live Geometry Nodes modifier
(``MCH_ArmorShell``), so the sliders change it at once:

    Mesh to SDF Grid    the distance to the part's surface, on a voxel grid (Detail = how fine)
    SDF Grid Mean       Smooth: muscles / small detail evened out, joined with the part's own distance so the shell
                        never comes closer than the Gap
    Grid to Mesh x 2    the surface at Gap (inside, faces turned in) and at Gap + Thickness (outside); Fewer Faces =
                        adaptive (big faces where it is flat: ~8k faces instead of ~150k, within a voxel)

Two surfaces of one distance field never cross, so the shell is always one clean closed solid, also in deep hollows
(Blender's voxel Remesh filled the inside of a shell: it was a solid lump).  Fewer Faces is left off on a shell under
three voxels thick (the adaptive surfaces move up to about a voxel and could touch there).

Update from Part takes the part's mesh again (after more sculpting); Apply makes the modifier real.  Anything that
edits the mesh makes it real first by itself (Cut / Split / Boolean and the rest that bake a live primitive, Mesh Tools,
Sculpt / Edit Mode), so the cut is always on the shell, never on the copy of the part under the modifier.  The part
itself is never changed.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, FloatProperty, PointerProperty

from . import core_geometry as cg

MOD = 'MCH_ArmorShell'
GROUP = 'MCH_ArmorShell'
VERSION = 2
GAP, THICK = 0.01, 0.02          # defaults: parts of the part's size
MIN_VOXELS, MAX_VOXELS = 60.0, 260.0
SMOOTH_STEPS = 12                # SDF Grid Mean iterations at Smooth 1 (width 2 voxels)
ADAPTIVE = 0.1                   # Grid to Mesh adaptivity with Fewer Faces
TICK = 0.25                      # a live shell in Sculpt / Edit Mode is made real this often
INPUTS = (('Voxel', 'NodeSocketFloat'), ('Gap', 'NodeSocketFloat'), ('Outer', 'NodeSocketFloat'),
          ('Band', 'NodeSocketInt'), ('Smooth', 'NodeSocketInt'), ('Adaptivity', 'NodeSocketFloat'))


def _sync_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.is_shell:
        sync(ob)


class MCH_PG_Shell(bpy.types.PropertyGroup):
    is_shell: BoolProperty(default=False, options={'HIDDEN'})
    source: PointerProperty(type=bpy.types.Object, name='Part')
    gap: FloatProperty(name='Gap', default=0.02, min=0.0, soft_max=1.0, precision=4, unit='LENGTH',
                       update=_sync_update, description='How far the inside of the shell stays off the part')
    thickness: FloatProperty(name='Thickness', default=0.04, min=0.0005, soft_max=1.0, precision=4, unit='LENGTH',
                             update=_sync_update, description='How thick the shell is (outward)')
    smooth: FloatProperty(name='Smooth', default=0.3, min=0.0, max=1.0, subtype='FACTOR', update=_sync_update,
                          description='Muscles / small detail evened out (0 = follows the part closely); the shell '
                                      'still never comes closer to the part than the Gap')
    detail: FloatProperty(name='Detail', default=0.5, min=0.0, max=1.0, subtype='FACTOR', update=_sync_update,
                          description='How fine the shell is (more = closer to the part\'s shape, more faces)')
    light: BoolProperty(name='Fewer Faces', default=True, update=_sync_update,
                        description='Big faces where the shell is flat (~20x fewer faces: cuts are much faster); '
                                    'off: even small faces everywhere')


def ensure_group():
    """The node group (made once; rebuilt when VERSION changes)."""
    ng = bpy.data.node_groups.get(GROUP)
    if ng is not None and ng.get('mch_version') == VERSION:
        return ng
    if ng is None:
        ng = bpy.data.node_groups.new(GROUP, 'GeometryNodeTree')
    ng.nodes.clear()
    ng.interface.clear()
    ng.interface.new_socket('Geometry', in_out='INPUT', socket_type='NodeSocketGeometry')
    for name, kind in INPUTS:
        ng.interface.new_socket(name, in_out='INPUT', socket_type=kind)
    ng.interface.new_socket('Geometry', in_out='OUTPUT', socket_type='NodeSocketGeometry')
    N, link = ng.nodes, ng.links.new
    gi, go = N.new('NodeGroupInput'), N.new('NodeGroupOutput')
    sdf = N.new('GeometryNodeMeshToSDFGrid')
    link(gi.outputs['Geometry'], sdf.inputs['Mesh'])
    link(gi.outputs['Voxel'], sdf.inputs['Voxel Size'])
    link(gi.outputs['Band'], sdf.inputs['Band Width'])
    mean = N.new('GeometryNodeSDFGridMean')
    link(sdf.outputs[0], mean.inputs['Grid'])
    mean.inputs['Width'].default_value = 2
    link(gi.outputs['Smooth'], mean.inputs['Iterations'])
    union = N.new('GeometryNodeSDFGridBoolean')        # the smoothed field joined with the part's own: never closer
    union.operation = 'UNION'
    link(mean.outputs[0], union.inputs[1])
    link(sdf.outputs[0], union.inputs[1])
    inner, outer = N.new('GeometryNodeGridToMesh'), N.new('GeometryNodeGridToMesh')
    for node, value in ((inner, 'Gap'), (outer, 'Outer')):
        link(union.outputs[0], node.inputs['Grid'])
        link(gi.outputs[value], node.inputs['Threshold'])
        link(gi.outputs['Adaptivity'], node.inputs['Adaptivity'])
    flip = N.new('GeometryNodeFlipFaces')
    link(inner.outputs[0], flip.inputs['Mesh'])
    join = N.new('GeometryNodeJoinGeometry')
    link(outer.outputs[0], join.inputs[0])
    link(flip.outputs[0], join.inputs[0])
    smooth = N.new('GeometryNodeSetShadeSmooth')
    link(join.outputs[0], smooth.inputs['Geometry'])
    link(smooth.outputs[0], go.inputs['Geometry'])
    for i, node in enumerate((gi, sdf, mean, union, inner, flip, join, smooth, go)):
        node.location = (i * 200, 0)
    outer.location = (5 * 200, -250)
    ng['mch_version'] = VERSION
    return ng


def _ident(name):
    ng = ensure_group()
    for it in ng.interface.items_tree:
        if getattr(it, 'in_out', '') == 'INPUT' and it.name == name:
            return it.identifier
    raise KeyError(name)


def local_size(ob):
    """The mesh's largest box side in its own space (the modifier works there)."""
    me = ob.data
    if me is None or not len(me.vertices):
        return 1.0
    import numpy as np
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return float(max((co.max(0) - co.min(0)).max(), 1e-6))


def _scale(ob):
    s = ob.matrix_world.to_scale()
    return max((abs(s.x) + abs(s.y) + abs(s.z)) / 3.0, 1e-9)


def values(size, sc, gap, thickness, smooth, detail, light=False):
    """The modifier inputs (the mesh's own units): voxel, inner / outer distance, band (voxels), smooth steps and
    adaptivity."""
    voxel = size / (MIN_VOXELS + (MAX_VOXELS - MIN_VOXELS) * detail)
    g, t = gap / sc, thickness / sc
    return {'Voxel': voxel, 'Gap': g, 'Outer': g + t, 'Band': int(math.ceil((g + t) / voxel)) + 2,
            'Smooth': int(round(smooth * SMOOTH_STEPS)), 'Adaptivity': ADAPTIVE if light and t >= 3 * voxel else 0.0}


def sync(ob):
    """The modifier from the sliders."""
    st = ob.mch_shell
    ensure_group()
    mod = ob.modifiers.get(MOD)
    if mod is None or mod.type != 'NODES':
        if mod is not None:
            ob.modifiers.remove(mod)
        mod = ob.modifiers.new(MOD, 'NODES')
    if mod.node_group is None or mod.node_group.name != GROUP:
        mod.node_group = bpy.data.node_groups[GROUP]
    vals = values(st.get('size') or local_size(ob), _scale(ob), st.gap, st.thickness, st.smooth, st.detail,
                  st.light)
    for name, v in vals.items():
        cg.gn_set(mod, _ident(name), v)
    idx = ob.modifiers.find(MOD)
    if idx != len(ob.modifiers) - 1:               # (last, after anything the user added before)
        ob.modifiers.move(idx, len(ob.modifiers) - 1)
    ob.update_tag()


def is_shell(ob):
    return ob is not None and ob.type == 'MESH' and getattr(getattr(ob, 'mch_shell', None), 'is_shell', False)


def _part_mesh(context, part):
    dg = context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(part.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)


def make(context, part, gap=None, thickness=None, smooth=0.3, detail=0.5):
    """The shell of ``part`` (a new object next to it, selected and active).  Returns it."""
    me = _part_mesh(context, part)
    me.name = part.name + '_Shell'
    for p in me.polygons:
        p.use_smooth = True
    ob = bpy.data.objects.new(part.name + '_Shell', me)
    for c in part.users_collection:
        c.objects.link(ob)
    if not ob.users_collection:
        context.scene.collection.objects.link(ob)
    ob.matrix_world = part.matrix_world.copy()
    st = ob.mch_shell
    size = local_size(ob)
    st['size'] = size
    world = size * _scale(ob)
    st.source = part
    st['is_shell'] = True
    st['gap'] = world * GAP if gap is None else gap
    st['thickness'] = world * THICK if thickness is None else thickness
    st['smooth'], st['detail'] = smooth, detail
    sync(ob)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def update_from_part(context, ob):
    """The part's mesh again (it was sculpted further); the sliders stay."""
    st = ob.mch_shell
    part = st.source
    if part is None or part.name not in bpy.data.objects:
        return 'Armor Shell: the part is gone'
    old = ob.data
    ob.data = _part_mesh(context, part)
    ob.data.name = old.name
    if old.users == 0:
        bpy.data.meshes.remove(old)
    st['size'] = local_size(ob)
    sync(ob)
    return f'Armor Shell: updated from {part.name}'


def face_count(context, ob):
    """Faces of the shell as it is now (0: the part has no closed volume to wrap)."""
    try:
        return len(ob.evaluated_get(context.evaluated_depsgraph_get()).data.polygons)
    except (RuntimeError, ReferenceError, AttributeError):
        return 0


def apply(context, ob):
    """The modifier made real: a plain mesh to cut."""
    dg = context.evaluated_depsgraph_get()
    new = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    old = ob.data
    if not len(new.materials):
        for mat in old.materials:
            new.materials.append(mat)
    ob.data = new
    new.name = old.name
    m = ob.modifiers.get(MOD)
    if m is not None:
        ob.modifiers.remove(m)
    ob.mch_shell['is_shell'] = False
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return f'Armor Shell applied: {len(new.polygons):,} faces'


def bake_live(context, ob):
    """A live shell made real before a tool edits its mesh (Cut / Split / Boolean / Mesh Tools work on the base mesh -
    under the modifiers that is the copy of the part).  True when it was baked."""
    if not is_shell(ob):
        return False
    apply(context, ob)
    return True


def bake_in_mode(ob):
    """A live shell taken into Sculpt / Edit Mode: made real first (the brush / edit would work on the hidden copy of
    the part under the modifiers), then back to that mode."""
    mode = ob.mode
    wm = bpy.context.window_manager
    win = getattr(bpy.context, 'window', None) or (wm.windows[0] if wm is not None and wm.windows else None)

    def go():
        bpy.ops.object.mode_set(mode='OBJECT')
        apply(bpy.context, ob)
        bpy.ops.object.mode_set(mode=mode)
    if win is not None:
        with bpy.context.temp_override(window=win, screen=win.screen, active_object=ob, object=ob):
            go()
    else:                                          # (no window: tests)
        go()


def _tick():
    try:
        ob = bpy.context.view_layer.objects.active
        if is_shell(ob) and ob.mode in {'SCULPT', 'EDIT'}:
            bake_in_mode(ob)
    except (AttributeError, RuntimeError, ReferenceError, TypeError):
        pass
    return TICK


def _mesh_target(context):
    ob = context.active_object
    if ob is None or ob.type != 'MESH':
        ob = next((o for o in context.selected_objects if o.type == 'MESH'), None)
    return ob


class MCH_OT_shell_extract(bpy.types.Operator):
    """The whole surface of the active part as a closed shell around it (a gap off it, a thickness outward) - cut it
    into armour plates with Cut / Split"""
    bl_idname = 'mch.shell_extract'
    bl_label = 'Extract Whole Surface (Armor Shell)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = _mesh_target(context)
        return ob is not None and not is_shell(ob)

    def execute(self, context):
        part = _mesh_target(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        if not len(part.data.polygons):
            self.report({'WARNING'}, 'Armor Shell: the part has no faces')
            return {'CANCELLED'}
        ob = make(context, part)
        n = face_count(context, ob)
        if not n:
            me = ob.data
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            part.select_set(True)
            context.view_layer.objects.active = part
            self.report({'WARNING'}, f'Armor Shell: nothing came out - "{part.name}" has no closed volume to wrap '
                                     f'(Fix Mesh / Remesh it first)')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Armor Shell: {ob.name}, {n:,} faces (Gap / Thickness / Smooth / Detail in the panel; '
                              f'cut it with Cut / Split)')
        return {'FINISHED'}


class MCH_OT_shell_update(bpy.types.Operator):
    """Take the part's mesh again (after more sculpting); the sliders stay"""
    bl_idname = 'mch.shell_update'
    bl_label = 'Update from Part'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_shell(context.active_object)

    def execute(self, context):
        self.report({'INFO'}, update_from_part(context, context.active_object))
        return {'FINISHED'}


class MCH_OT_shell_apply(bpy.types.Operator):
    """Make the shell a plain mesh (the modifiers real)"""
    bl_idname = 'mch.shell_apply'
    bl_label = 'Apply Shell'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_shell(context.active_object) and context.mode == 'OBJECT'

    def execute(self, context):
        self.report({'INFO'}, apply(context, context.active_object))
        return {'FINISHED'}


def draw(layout, context):
    """The Armor Shell box (Face Extract panel)."""
    box = layout.box()
    box.label(text='Whole Surface: Armor Shell', icon='MOD_SOLIDIFY')
    ob = context.active_object
    if is_shell(ob):
        st = ob.mch_shell
        part = st.source
        box.label(text=f'SHELL of {part.name if part else "?"}', icon='MESH_DATA')
        col = box.column(align=True)
        col.prop(st, 'gap')
        col.prop(st, 'thickness')
        col.prop(st, 'smooth', slider=True)
        col.prop(st, 'detail', slider=True)
        box.prop(st, 'light')
        row = box.row(align=True)
        row.operator('mch.shell_update', icon='FILE_REFRESH')
        row.operator('mch.shell_apply', icon='CHECKMARK')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text='Cut / Split it now: it is made real by itself first')
    else:
        row = box.row()
        row.scale_y = 1.3
        row.operator('mch.shell_extract', text='Extract Whole Surface', icon='MOD_SOLIDIFY')
        col = box.column(align=True)
        col.scale_y = 0.8
        col.label(text='The whole part as a shell around it (gap off it, thickness')
        col.label(text='outward) - cut it into armour with Cut / Split')


CLASSES = (MCH_PG_Shell, MCH_OT_shell_extract, MCH_OT_shell_update, MCH_OT_shell_apply)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_shell = PointerProperty(type=MCH_PG_Shell)
    if not bpy.app.timers.is_registered(_tick):
        bpy.app.timers.register(_tick, first_interval=1.0, persistent=True)


def unregister():
    if bpy.app.timers.is_registered(_tick):
        bpy.app.timers.unregister(_tick)
    if hasattr(bpy.types.Object, 'mch_shell'):
        del bpy.types.Object.mch_shell
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
