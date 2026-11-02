"""0.24.95 Bake to Polypaint (user: "폴리페인트로 구워 줘"): the material's finished colour - the Mech Shader with its wear,
zones, dirt; the Creature Shader with its markings and conditions; any Principled material - baked into a colour
attribute of the mesh, one colour per point (ZBrush polypaint).

* the colour as the material makes it (its Base Color, no light): for the bake each material's Principled BSDF Base
  Color is led into an Emission shader for a moment (Cycles, Emit, 1 sample, target Color Attributes); every link is
  put back as it was afterwards, and so are the scene's engine / samples, the selection
* into its own layer ``Baked Color`` (point, float) - made, or written over the next time - which becomes the active
  colour layer (painting, the OBJ / FBX export, ZBrush Send take it); the layer the Creature Shader reads as polypaint
  (the default one) stays as it was, so the bake is never read back on top of itself
* one colour per point: the denser the mesh, the finer the polypaint (a 10k-point part holds coarse markings only)
* a material that is not a Principled one (no Base Color to read): its diffuse colour (Cycles Diffuse, colour only)

Show Polypaint: the 3D view in Solid shading with the active colour layer (again: back to Material Preview)."""
from __future__ import annotations

import time

import bpy
from bpy.props import StringProperty

LAYER = 'Baked Color'
LAST = {}


def principled(mat):
    """The material's Principled BSDF: the Mech / Creature Shader's ``mch:bsdf``, else the one feeding its output."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return None
    nodes = mat.node_tree.nodes
    nd = nodes.get('mch:bsdf')
    if nd is not None and nd.type == 'BSDF_PRINCIPLED':
        return nd
    out = _output(mat)
    if out is not None and out.inputs['Surface'].is_linked:
        src = out.inputs['Surface'].links[0].from_node
        if src.type == 'BSDF_PRINCIPLED':
            return src
    return next((n for n in nodes if n.type == 'BSDF_PRINCIPLED'), None)


def _output(mat):
    nodes = mat.node_tree.nodes
    outs = [n for n in nodes if n.type == 'OUTPUT_MATERIAL']
    return next((n for n in outs if n.is_active_output), outs[0] if outs else None)


class _Hookup:
    """For each material: its Base Color into an Emission shader on the output; ``undo`` puts every link back."""

    def __init__(self, mats):
        self.done = []
        for mat in mats:
            bs = principled(mat)
            out = _output(mat) if bs is not None else None
            if bs is None or out is None:
                continue
            nt = mat.node_tree
            old = out.inputs['Surface'].links[0].from_socket if out.inputs['Surface'].is_linked else None
            em = nt.nodes.new('ShaderNodeEmission')
            em.name = '.mch_bake_emit'
            em.inputs['Strength'].default_value = 1.0
            bc = bs.inputs['Base Color']
            if bc.is_linked:
                nt.links.new(bc.links[0].from_socket, em.inputs['Color'])
            else:
                em.inputs['Color'].default_value = bc.default_value
            nt.links.new(em.outputs['Emission'], out.inputs['Surface'])
            self.done.append((mat, out, old, em))

    def undo(self):
        for mat, out, old, em in self.done:
            nt = mat.node_tree
            try:
                for lk in list(out.inputs['Surface'].links):
                    nt.links.remove(lk)
                if old is not None:
                    nt.links.new(old, out.inputs['Surface'])
                nt.nodes.remove(em)
            except ReferenceError:
                pass


def bake_polypaint(context, objs, layer=LAYER):
    """The materials' colour baked into the point colour layer ``layer`` of each mesh in ``objs``.  Returns info."""
    from . import bake_maps as bm
    objs = [o for o in objs if o is not None and o.type == 'MESH']
    if not objs:
        raise RuntimeError('select the meshes to bake')
    if context.mode != 'OBJECT':
        bpy.ops.object.mode_set(mode='OBJECT')
    S = context.scene
    t0 = time.time()
    keep = bm._Keep(context, objs)
    info = []
    try:
        S.render.engine = 'CYCLES'
        S.cycles.samples = 1
        for ob in objs:
            mats = [s.material for s in ob.material_slots if s.material is not None]
            if not mats:
                info.append((ob.name, 0, 'no material'))
                continue
            me = ob.data
            ca = me.color_attributes
            default = ca.default_color_name
            att = ca.get(layer)
            if att is not None and (att.domain != 'POINT' or att.data_type != 'FLOAT_COLOR'):
                ca.remove(att)
                att = None
            if att is None:
                att = ca.new(layer, 'FLOAT_COLOR', 'POINT')
            ca.active_color = att
            for o in list(context.selected_objects):
                o.select_set(False)
            ob.hide_viewport = False
            ob.hide_set(False)
            ob.select_set(True)
            context.view_layer.objects.active = ob
            emit = all(principled(m) is not None for m in mats)
            hook = _Hookup(mats) if emit else None
            try:
                if emit:
                    r = bpy.ops.object.bake(type='EMIT', target='VERTEX_COLORS', use_clear=True)
                else:
                    r = bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, target='VERTEX_COLORS',
                                            use_clear=True)
            finally:
                if hook is not None:
                    hook.undo()
            if 'FINISHED' not in r:
                raise RuntimeError(f'the bake of {ob.name} did not finish')
            ca = me.color_attributes
            if default and default != layer and ca.get(default) is not None:
                ca.default_color_name = default          # (the polypaint the Creature Shader reads: as it was)
            ca.active_color = ca.get(layer)
            info.append((ob.name, len(me.vertices), 'emit' if emit else 'diffuse'))
    finally:
        keep.restore(context)
    LAST.clear()
    LAST.update(objects=info, seconds=time.time() - t0, layer=layer)
    return info


def describe(info):
    done = [i for i in info if i[1]]
    pts = sum(i[1] for i in done)
    skipped = [i[0] for i in info if not i[1]]
    return (f'Polypaint baked: {len(done)} mesh(es), {pts:,} points into "{LAYER}"'
            + (f' ({", ".join(skipped)}: no material)' if skipped else ''))


class MCH_OT_bake_polypaint(bpy.types.Operator):
    """Bake the material's colour (wear, zones, markings, conditions ...) into polypaint: one colour per point, in its
    own colour layer "Baked Color" (the active one - painting, export and ZBrush Send take it)"""
    bl_idname = 'mch.bake_polypaint'
    bl_label = 'Bake to Polypaint'
    bl_options = {'REGISTER', 'UNDO'}
    layer: StringProperty(name='Layer', default=LAYER)

    @classmethod
    def poll(cls, context):
        return any(o.type == 'MESH' for o in context.selected_objects) or (
            context.active_object is not None and context.active_object.type == 'MESH')

    def execute(self, context):
        objs = [o for o in context.selected_objects if o.type == 'MESH'] or [context.active_object]
        try:
            from . import safety_save
            safety_save.before_risky('Bake to Polypaint')
        except (ImportError, AttributeError, RuntimeError):
            pass
        try:
            info = bake_polypaint(context, objs, self.layer or LAYER)
        except RuntimeError as ex:
            self.report({'WARNING'}, f'Bake to Polypaint: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, describe(info))
        return {'FINISHED'}


def _views(context):
    for w in context.window_manager.windows:
        for a in w.screen.areas:
            if a.type == 'VIEW_3D':
                yield a.spaces.active


def showing(context):
    sp = next(iter(_views(context)), None) if context.window_manager else None
    return sp is not None and sp.shading.type == 'SOLID' and sp.shading.color_type == 'VERTEX'


class MCH_OT_show_polypaint(bpy.types.Operator):
    """Show the polypaint (Solid shading with the active colour layer); again: back to Material Preview"""
    bl_idname = 'mch.show_polypaint'
    bl_label = 'Show Polypaint'
    bl_options = {'REGISTER'}

    def execute(self, context):
        on = not showing(context)
        for sp in _views(context):
            if on:
                sp.shading.type = 'SOLID'
                sp.shading.color_type = 'VERTEX'
            else:
                sp.shading.type = 'MATERIAL'
        return {'FINISHED'}


CLASSES = (MCH_OT_bake_polypaint, MCH_OT_show_polypaint)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
