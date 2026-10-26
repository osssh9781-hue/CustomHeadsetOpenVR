"""0.24.48 Quad Remesh that keeps the hard edges left by cuts and booleans.

Make Quad: a copy of the selected part (modifiers baked) is cleaned (close points merged, normals made
consistent), every edge sharper than ``Edge Angle`` (and, if wanted, edges already marked sharp or with a
crease) is marked sharp, then Blender's QuadriFlow rebuilds it as all quads with ``Preserve Sharp`` on, so
the new quad lines run along those edges.  The original is kept, hidden.  Re-make with other settings or
Apply (the copy becomes an ordinary mesh).
"""
from __future__ import annotations

import math
import time

import bmesh
import bpy
from bpy.props import BoolProperty, FloatProperty, IntProperty

SRC_KEY = 'mch_quad_source'


class MCH_PG_QuadRemesh(bpy.types.PropertyGroup):
    faces: IntProperty(name='Faces', default=4000, min=100, max=200000,
                       description='About this many quads. More = thin chamfers and small cuts keep their shape')
    edge_angle: FloatProperty(name='Edge Angle', default=math.radians(30.0), min=math.radians(1.0),
                              max=math.radians(150.0), subtype='ANGLE',
                              description='Edges sharper than this are kept as hard quad lines')
    keep_marked: BoolProperty(name='Keep Marked Edges', default=True,
                              description='Also keep edges you marked Sharp or gave a Crease')
    smooth_shade: BoolProperty(name='Smooth + Sharp Edges', default=True,
                               description='Shade the result smooth with the kept edges sharp')


def is_quad(ob):
    return ob is not None and ob.type == 'MESH' and SRC_KEY in ob


def _size(me):
    if not me.vertices:
        return 1.0
    import numpy as np
    co = np.empty(len(me.vertices) * 3)
    me.vertices.foreach_get('co', co)
    co = co.reshape(-1, 3)
    return max(float((co.max(0) - co.min(0)).max()), 1e-9)


def _baked(context, src):
    dg = context.evaluated_depsgraph_get()
    return bpy.data.meshes.new_from_object(src.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)


def _marked(me):
    """Edge indices marked sharp or creased on ``me``."""
    out = set()
    att = me.attributes.get('sharp_edge')
    if att is not None and att.domain == 'EDGE':
        out.update(i for i, d in enumerate(att.data) if d.value)
    att = me.attributes.get('crease_edge')
    if att is not None and att.domain == 'EDGE':
        out.update(i for i, d in enumerate(att.data) if d.value > 0.0)
    return out


def prepare(me, angle, keep_marked=True):
    """Clean ``me`` for QuadriFlow and mark the edges to keep sharp.  Returns (kept edges, open edges)."""
    marked = _marked(me) if keep_marked else set()
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.edges.ensure_lookup_table()
        for i in marked:
            if i < len(bm.edges):
                bm.edges[i].tag = True
        bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=_size(me) * 1e-5)
        loose = [v for v in bm.verts if not v.link_faces]
        if loose:
            bmesh.ops.delete(bm, geom=loose, context='VERTS')
        bmesh.ops.dissolve_degenerate(bm, edges=bm.edges, dist=_size(me) * 1e-6)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        kept = 0
        open_edges = 0
        for e in bm.edges:
            if not e.is_manifold:
                open_edges += 1
            hard = e.tag or (e.is_manifold and e.calc_face_angle(0.0) > angle)
            e.smooth = not hard
            kept += hard
            e.tag = False
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return kept, open_edges


def _shade(me, angle):
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        for f in bm.faces:
            f.smooth = True
        for e in bm.edges:
            e.smooth = not (not e.is_manifold or e.calc_face_angle(0.0) > angle)
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()


def build_mesh(context, src, st):
    """The quad mesh (object space of ``src``)."""
    me = _baked(context, src)
    kept, open_edges = prepare(me, st.edge_angle, st.keep_marked)
    if open_edges:
        bpy.data.meshes.remove(me)
        raise RuntimeError(f'The part has {open_edges} open / non-manifold edges. Close it first '
                           '(Quad Remesh needs a closed solid).')
    tmp = bpy.data.objects.new('MCH_Quad_tmp', me)
    tmp.matrix_world = src.matrix_world.copy()
    context.scene.collection.objects.link(tmp)
    before = len(me.polygons)
    try:
        with context.temp_override(object=tmp, active_object=tmp, selected_objects=[tmp],
                                   selected_editable_objects=[tmp]):
            bpy.ops.object.quadriflow_remesh(use_mesh_symmetry=False, use_preserve_sharp=kept > 0,
                                             use_preserve_boundary=True, preserve_attributes=False,
                                             smooth_normals=False, mode='FACES', target_faces=st.faces, seed=0)
    except RuntimeError as ex:
        bpy.data.objects.remove(tmp, do_unlink=True)
        bpy.data.meshes.remove(me)
        raise RuntimeError('QuadriFlow failed: ' + str(ex).strip())
    bpy.data.objects.remove(tmp, do_unlink=True)
    polys = me.polygons
    if not polys or (len(polys) == before and any(len(p.vertices) != 4 for p in polys)):
        bpy.data.meshes.remove(me)
        raise RuntimeError('QuadriFlow could not remesh this part (try more Faces or a smaller Edge Angle).')
    for name in [a.name for a in me.attributes if a.name.startswith('mch_')]:
        me.attributes.remove(me.attributes[name])
    if st.smooth_shade:
        _shade(me, st.edge_angle)
    return me, kept


def make(context, src, st):
    if src is None or src.type != 'MESH':
        raise RuntimeError('Select a mesh part first.')
    me, kept = build_mesh(context, src, st)
    me.name = src.name + '_Quad'
    ob = bpy.data.objects.new(src.name + '_Quad', me)
    for coll in src.users_collection:
        coll.objects.link(ob)
    ob.matrix_world = src.matrix_world.copy()
    for mat in src.data.materials:
        me.materials.append(mat)
    ob[SRC_KEY] = src.name
    src.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob, kept


def remake(context, ob, st):
    src = bpy.data.objects.get(ob.get(SRC_KEY, ''))
    if src is None:
        raise RuntimeError('The original part is gone; cannot re-make.')
    me, kept = build_mesh(context, src, st)
    old = ob.data
    me.name = old.name
    for mat in old.materials:
        me.materials.append(mat)
    ob.data = me
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob, kept


class MCH_OT_quad_make(bpy.types.Operator):
    """All-quad copy of the selected part; the hard edges from cuts / booleans stay as quad lines
    (the original is kept, hidden)"""
    bl_idname = 'mch.quad_remesh'
    bl_label = 'Quad Remesh (keep edges)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        st = context.scene.mch_quadremesh
        ob = context.active_object
        t = time.time()
        try:
            if is_quad(ob):
                ob, kept = remake(context, ob, st)
            else:
                ob, kept = make(context, ob, st)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: {len(ob.data.polygons)} quads, {kept} hard edges kept '
                              f'({time.time() - t:.1f} s)')
        return {'FINISHED'}


class MCH_OT_quad_apply(bpy.types.Operator):
    """Keep the quad mesh as an ordinary mesh (the hidden original stays in the file)"""
    bl_idname = 'mch.quad_apply'
    bl_label = 'Apply Quad'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_quad(context.active_object)

    def execute(self, context):
        del context.active_object[SRC_KEY]
        return {'FINISHED'}


class MCH_OT_quad_show_source(bpy.types.Operator):
    """Show / hide the original part"""
    bl_idname = 'mch.quad_show_source'
    bl_label = 'Show Original'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_quad(context.active_object)

    def execute(self, context):
        src = bpy.data.objects.get(context.active_object.get(SRC_KEY, ''))
        if src is not None:
            src.hide_set(not src.hide_get())
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_quadremesh
    ob = context.active_object
    box = layout.box()
    box.label(text='QUAD REMESH (keep cut edges)', icon='MOD_REMESH')
    col = box.column(align=True)
    col.prop(st, 'faces')
    col.prop(st, 'edge_angle')
    col.prop(st, 'keep_marked')
    col.prop(st, 'smooth_shade')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.quad_remesh', text='Re-make Quad' if is_quad(ob) else 'Make Quad',
                 icon='FILE_REFRESH' if is_quad(ob) else 'MOD_REMESH')
    if is_quad(ob):
        box.label(text=f'{len(ob.data.polygons)} quads')
        row = box.row(align=True)
        row.operator('mch.quad_show_source', icon='HIDE_OFF')
        row.operator('mch.quad_apply', icon='CHECKMARK')
    else:
        box.label(text='Needs a closed part. Big meshes take a while', icon='INFO')


CLASSES = (MCH_PG_QuadRemesh, MCH_OT_quad_make, MCH_OT_quad_apply, MCH_OT_quad_show_source)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_quadremesh = bpy.props.PointerProperty(type=MCH_PG_QuadRemesh)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_quadremesh'):
        del bpy.types.Scene.mch_quadremesh
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
