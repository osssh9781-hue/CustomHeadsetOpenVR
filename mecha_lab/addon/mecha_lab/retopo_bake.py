"""0.24.241 Retopo + Bake in one click (user: "리토포 하고 베이킹 하는 툴도 만들어 줄 수 있어?" - "리토포+베이크 한 번에").

Select the detailed mesh (the high) and press Retopo + Bake:

1. a low-poly copy ``<name>_Low`` - the high as it shows (its modifiers too), quad remeshed by our engine to
   about ``Faces`` (QuadriFlow when the engine is not there);
2. new UVs on it (Smart UV, a margin for the map size);
3. the high's Normal / AO (and Color when on) baked onto it with the Bake Maps settings (size, ray, margin ...),
   a material with the maps put on it;
4. the low shown, the high hidden (both kept: select the low and press again to bake again from the same high).

The high is never changed.
"""
import time

import bpy
from bpy.props import IntProperty

HIGH_KEY = 'mch_rb_high'        # on the low: the name of its high


def high_of(low):
    if low is None or low.type != 'MESH':
        return None
    h = bpy.data.objects.get(low.get(HIGH_KEY, ''))
    return h if h is not None and h.type == 'MESH' and h is not low else None


def make_low(context, high, faces):
    """A remeshed copy of ``high`` (as it shows).  Returns (low, note).  Raises RuntimeError."""
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(high.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    if len(me.polygons) == 0:
        bpy.data.meshes.remove(me)
        raise RuntimeError(f'{high.name} has no faces')
    for lay in list(me.uv_layers):                   # (the remesh makes new faces: old UVs do not fit)
        me.uv_layers.remove(lay)
    me.name = high.name + '_Low'
    low = bpy.data.objects.new(high.name + '_Low', me)
    for coll in high.users_collection:
        coll.objects.link(low)
    if not low.users_collection:
        context.scene.collection.objects.link(low)
    low.matrix_world = high.matrix_world.copy()
    low[HIGH_KEY] = high.name
    before = len(me.polygons)
    note = ''
    try:
        from . import quad_field as qf
        engine = qf.available()
    except ImportError:
        engine = False
    if engine:
        note = qf.remesh_object(low, max(4, int(faces)), all_quads=False, crease_deg=30.0) or ''
    if not engine or len(low.data.polygons) == before:
        from . import quad_remesh as qr             # (old QuadriFlow way, in place)
        st = context.scene.mch_quadremesh
        keep = st.faces
        st.faces = max(4, int(faces))
        try:
            me2, _kept, _miss, note2 = qr.build_mesh(context, low, st)
        except RuntimeError as ex:
            bpy.data.objects.remove(low)
            bpy.data.meshes.remove(me)
            raise RuntimeError(f'Retopo failed: {ex}') from None
        finally:
            st.faces = keep
        old = low.data
        low.data = me2
        me2.name = high.name + '_Low'
        if old.users == 0:
            bpy.data.meshes.remove(old)
        note = note2 or note
    for mat in high.data.materials:
        low.data.materials.append(mat)
    for p in low.data.polygons:
        p.use_smooth = True
    return low, note


def run(context, high=None, low=None):
    """Retopo (when no ``low``) and bake.  Returns the message.  Raises RuntimeError."""
    from . import bake_maps as bm
    st = bm.settings(context)
    if st is None:
        raise RuntimeError('Bake settings are missing')
    t0 = time.time()
    note = ''
    made = low is None
    if made:
        low, note = make_low(context, high, context.scene.mch_rb_faces)
    keep = bm._Keep(context, [low, high])
    new_uv = st.new_uv
    st.new_uv = made or not low.data.uv_layers       # (a fresh low: its own UVs; a low baked before: kept)
    try:
        info = bm.bake_pair(context, low, [high], st, keep_state=keep)
    except RuntimeError:
        if made:
            keep.restore(context)
            m = low.data
            bpy.data.objects.remove(low)
            if m.users == 0:
                bpy.data.meshes.remove(m)
            raise
        raise
    finally:
        st.new_uv = new_uv
    keep.restore(context)
    if st.show:
        high.hide_set(True)
        high.select_set(False)
    low.hide_set(False)
    for o in list(context.selected_objects):
        o.select_set(False)
    low.select_set(True)
    context.view_layer.objects.active = low
    return (f'Retopo + Bake: {high.name} ({len(high.data.polygons):,} faces) -> {low.name} '
            f'({len(low.data.polygons):,} faces), {", ".join(bm.SUFFIX[k] for k in info["maps"])} {info["res"]} px, '
            f'{time.time() - t0:.1f} s' + (f' | {note}' if note and not note.startswith('Quad Remesh:') else ''))


class MCH_OT_retopo_bake(bpy.types.Operator):
    """Make a low-poly copy of the selected detailed mesh (quad remesh + UVs) and bake its Normal / AO maps onto it.
    With a low made here selected: bake again from its high"""
    bl_idname = 'mch.retopo_bake'
    bl_label = 'Retopo + Bake'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH'

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        ob = context.active_object
        high = high_of(ob)
        low = ob if high is not None else None
        high = high or ob
        try:
            from . import safety_save
            safety_save.before_risky('Retopo + Bake')
        except (ImportError, AttributeError, RuntimeError):
            pass
        try:
            msg = run(context, high, low)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    """The one-click box (Remesh tool window, Bake Maps)."""
    from . import bake_maps as bm, panel_capture as pc
    st = bm.settings(context)
    S = context.scene
    if st is None or not hasattr(S, 'mch_rb_faces'):
        return
    ob = context.active_object
    again = high_of(ob) is not None
    box = layout.box()
    box.label(text='RETOPO + BAKE  (one click)', icon='MOD_REMESH')
    r = pc.primary(box.row(align=True))
    r.scale_y = 1.3
    r.operator('mch.retopo_bake', text='Bake Again' if again else 'Retopo + Bake', icon='RENDER_STILL')
    col = box.column(align=True)
    r = col.row(align=True)
    sub = r.row(align=True)
    sub.enabled = not again
    sub.prop(S, 'mch_rb_faces')
    r.prop(st, 'res', text='')
    r = col.row(align=True)
    r.prop(st, 'normal', toggle=True)
    r.prop(st, 'ao', toggle=True)
    r.prop(st, 'color', toggle=True)
    if again:
        box.label(text=f'{high_of(ob).name} -> {ob.name}', icon='CHECKMARK')
    else:
        box.label(text='Select the detailed mesh (high)', icon='INFO')


CLASSES = (MCH_OT_retopo_bake,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_rb_faces = IntProperty(
        name='Faces', default=5000, min=50, max=200000,
        description='About how many faces the low poly gets')


def unregister():
    if hasattr(bpy.types.Scene, 'mch_rb_faces'):
        del bpy.types.Scene.mch_rb_faces
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
