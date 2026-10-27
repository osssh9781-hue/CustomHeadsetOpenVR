"""0.19.1 High Poly for hand-off (export FBX with Blender as usual).

Work stays light (low poly, smooth shading).  For the vendor, "Make High
Poly" builds a dense COPY of each selected mesh in the "HighPoly" collection
(the originals are only hidden, never changed):

    1. the mesh with its own modifiers (mirror, plate bevel / shell ...);
    2. Bevel on the sharp edges only (angle limit) = support loops, so plate
       edges, chamfer lines and corners stay crisp;
    3. Subdivision Surface: curved areas become really round (not just shaded);
    4. everything applied and shaded smooth: a plain dense mesh that looks the
       same in Flat mode and in any program.

Right-click a selection > "Make High Poly"; the Adjust Last Operation panel
(bottom left / F9) changes smoothness, edge sharpness and angle at once.
Export with Blender's own File > Export > FBX.
``support_width`` / ``estimate_faces`` are pure and tested headless.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

COLL = 'HighPoly'
SRC_KEY = 'mch_highpoly_src'
MAX_FACES = 3_000_000


def support_width(dims, ratio):
    """Bevel width for the support loops: a fraction of the mesh size."""
    return max(1e-5, math.sqrt(sum(d * d for d in dims)) * ratio)


def estimate_faces(faces, level, segments=2, sharp_share=0.3):
    """Rough face count after bevel + subdivision (for the safety limit)."""
    return int(faces * (1.0 + sharp_share * segments) * 4 ** level)


def safe_level(faces, level, segments=2, limit=None):
    """The highest level up to ``level`` that stays under the limit (MAX_FACES and the free memory); 0 when even
    level 1 does not (0.24.73: it used to stop at 1 and go over the limit)."""
    from . import budget
    if limit is None:
        limit = min(MAX_FACES, budget.max_faces())
    while level > 0 and estimate_faces(faces, level, segments) > limit:
        level -= 1
    return level


class HighPolyError(RuntimeError):
    """The high poly copy would be too big (nothing was changed)."""


def _too_big(name, faces, segments):
    return HighPolyError(f'{name}: {faces:,} faces is too many for High Poly '
                         f'(about {estimate_faces(faces, 1, segments):,} even at Smoothness 1) - decimate it first')


def is_highpoly(ob):
    try:
        return bool(ob.get(SRC_KEY))
    except (TypeError, ReferenceError):
        return False


def _collection(context):
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
    if coll.name not in context.scene.collection.children and not any(
            coll.name in c.children for c in bpy.data.collections):
        context.scene.collection.children.link(coll)
    return coll


def _targets(context):
    return [o for o in context.selected_objects if o.type == 'MESH' and not is_highpoly(o)]


def creased_subdiv(context, ob, level, angle):
    """0.20.2 High Poly of a plate without changing its look: the low poly plate as it is (modifiers
    applied), every sharp edge (marked sharp, crease lines, or sharper than ``angle``) gets a full
    crease, then Subdivision - flat facets and chamfers stay crisp, only the face count grows.
    (0.19.2-0.20.1 re-projected small faces onto the surface: on a detailed face mesh that made the
    plate lumpy and moved its crease lines.)"""
    import bmesh
    dg = context.evaluated_depsgraph_get()
    base = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    bm = bmesh.new()
    try:
        bm.from_mesh(base)
        sharp = base.attributes.get('sharp_edge')
        flags = [False] * len(base.edges)
        if sharp is not None and sharp.domain == 'EDGE':
            sharp.data.foreach_get('value', flags)
        cl = bm.edges.layers.float.get('crease_edge') or bm.edges.layers.float.new('crease_edge')
        bm.edges.ensure_lookup_table()
        for e in bm.edges:
            hard = flags[e.index] if e.index < len(flags) else False
            if not hard and len(e.link_faces) == 2:
                hard = e.calc_face_angle(0.0) > angle
            if hard or len(e.link_faces) != 2:
                e[cl] = 1.0
        bm.to_mesh(base)
    finally:
        bm.free()
    level = safe_level(len(base.polygons), max(1, level), 0)
    if level < 1:
        n = len(base.polygons)
        bpy.data.meshes.remove(base)
        raise _too_big(ob.name, n, 0)
    tmp = bpy.data.objects.new('MCH_HP_tmp', base)
    context.scene.collection.objects.link(tmp)
    tmp.matrix_world = ob.matrix_world.copy()
    sub = tmp.modifiers.new('MCH_HP_Subdiv', 'SUBSURF')
    sub.levels = sub.render_levels = level
    sub.quality = 3
    sub.use_creases = True
    sub.boundary_smooth = 'PRESERVE_CORNERS'
    try:
        dg = context.evaluated_depsgraph_get()
        dense = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), depsgraph=dg)
    finally:
        bpy.data.objects.remove(tmp)
        if base.users == 0:
            bpy.data.meshes.remove(base)
    try:
        dense.set_sharp_from_angle(angle=angle)
    except (AttributeError, TypeError):
        pass
    return dense


def make_highpoly(context, ob, level, ratio, angle, segments, plate_detail=10):
    """Dense copy of ``ob`` in the HighPoly collection.  Returns (copy, level).
    Armor plates / live parts are rebuilt densely instead (shape kept exactly)."""
    st_coll = _collection(context)
    olds = [o for o in st_coll.objects if o.get(SRC_KEY) == ob.name]     # rebuild = replace (after success)
    hp, level = _make_highpoly(context, ob, st_coll, level, ratio, angle, segments)
    for old in olds:                         # 0.24.73 the old copy goes only now: a failure above keeps it
        me_old = old.data
        bpy.data.objects.remove(old)
        if me_old.users == 0:
            bpy.data.meshes.remove(me_old)
    hp.name = ob.name + '_HP'
    hp.data.name = ob.name + '_HP'
    return hp, level


def _make_highpoly(context, ob, st_coll, level, ratio, angle, segments):
    from . import armor_plate as ap
    from . import cloth_wrinkle as cw
    dense = cw.dense_mesh(context, ob) if cw.is_wrinkle(ob) else None
    if dense is None and (ap.plate_hp_data(ob) is not None or getattr(ob.mch_extract, 'is_part', False)):
        dense = creased_subdiv(context, ob, level, angle)      # plates: the SAME shape, just more faces
    if dense is not None:
        dense.name = ob.name + '_HP'
        try:
            dense.shade_smooth()
        except AttributeError:
            pass
        hp = bpy.data.objects.new(ob.name + '_HP', dense)
        st_coll.objects.link(hp)
        hp.matrix_world = ob.matrix_world.copy()
        hp[SRC_KEY] = ob.name
        return hp, 0
    dg = context.evaluated_depsgraph_get()
    base = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
    level = safe_level(len(base.polygons), level, segments)
    if level < 1:
        n = len(base.polygons)
        bpy.data.meshes.remove(base)
        raise _too_big(ob.name, n, segments)
    hp = bpy.data.objects.new(ob.name + '_HP', base)
    st_coll.objects.link(hp)
    hp.matrix_world = ob.matrix_world.copy()
    xs = [v.co for v in base.vertices] or [hp.location]
    dims = [max(c[k] for c in xs) - min(c[k] for c in xs) for k in range(3)]
    if segments > 0 and ratio > 0:
        bev = hp.modifiers.new('MCH_HP_Support', 'BEVEL')
        bev.limit_method = 'ANGLE'
        bev.angle_limit = angle
        bev.width = support_width(dims, ratio)
        bev.segments = segments
        bev.profile = 0.5
        bev.use_clamp_overlap = True
        bev.harden_normals = False
    sub = hp.modifiers.new('MCH_HP_Subdiv', 'SUBSURF')
    sub.levels = sub.render_levels = level
    sub.quality = 3
    try:
        dg = context.evaluated_depsgraph_get()
        dense = bpy.data.meshes.new_from_object(hp.evaluated_get(dg), depsgraph=dg)
    except Exception:                            # (the half-made copy goes; the old one is still there)
        bpy.data.objects.remove(hp)
        if base.users == 0:
            bpy.data.meshes.remove(base)
        raise
    hp.modifiers.clear()
    hp.data = dense
    dense.name = ob.name + '_HP'
    if base.users == 0:
        bpy.data.meshes.remove(base)
    try:
        dense.shade_smooth()
    except AttributeError:
        for p in dense.polygons:
            p.use_smooth = True
    hp[SRC_KEY] = ob.name
    return hp, level


class MCH_OT_make_highpoly(bpy.types.Operator):
    """Dense high poly copies of the selected meshes for hand-off (originals kept, only hidden)"""
    bl_idname = 'mch.make_highpoly'
    bl_label = 'Make High Poly'
    bl_options = {'REGISTER', 'UNDO'}
    level: IntProperty(name='Smoothness', default=2, min=1, max=3,
                       description='Subdivision level: 2 = good hand-off quality, 3 = very dense')
    edge: FloatProperty(name='Edge Softness', default=0.004, min=0.0, max=0.05, precision=3, step=0.1,
                        description='Width of the support bevel on sharp edges (part of the mesh size): smaller = '
                                    'crisper edges, 0 = soft, fully rounded')
    angle: FloatProperty(name='Sharp Edge Angle', default=math.radians(35.0), min=math.radians(5.0),
                         max=math.radians(90.0), subtype='ANGLE',
                         description='Edges sharper than this stay crisp; softer edges are rounded into curves')
    segments: IntProperty(name='Support Loops', default=2, min=1, max=4,
                          description='Bevel segments on the sharp edges before subdividing')
    plate_detail: IntProperty(name='Plate Detail (px)', default=10, min=4, max=60,
                              description='Armor plates: face size of the dense rebuild (smaller = denser). '
                                          'Plates keep their exact shape and edges, no subdivision')
    hide_originals: BoolProperty(name='Hide Originals', default=True,
                                 description='Hide the low poly meshes after making the high poly copies')
    join: BoolProperty(name='Join Into One', default=False,
                       description='One high poly object instead of one per part')

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(_targets(context))

    def execute(self, context):
        st = self
        obs = _targets(context)
        made, lowered, faces, refused = [], False, 0, []
        from . import budget
        for ob in obs:
            try:
                hp, lv = make_highpoly(context, ob, st.level, st.edge, st.angle, st.segments, st.plate_detail)
            except HighPolyError as ex:          # (0.24.73 too big: refused before anything was made)
                refused.append(str(ex))
                continue
            lowered |= 0 < lv < st.level
            faces += len(hp.data.polygons)
            made.append(hp)
            ok, why = budget.faces_fit(faces)
            if not ok:                           # all of them together: stop before memory runs out
                refused.append(f'stopped after {len(made)} object(s): {why}')
                break
        if not made:
            self.report({'WARNING'}, 'High poly: ' + ('; '.join(refused) or 'nothing made'))
            return {'CANCELLED'}
        if st.join and len(made) > 1:
            with context.temp_override(active_object=made[0], object=made[0], selected_objects=made,
                                       selected_editable_objects=made):
                bpy.ops.object.join()
            made[0].name = 'HighPoly_Joined'
            made[0][SRC_KEY] = ','.join(o.name for o in obs)
            made = made[:1]
        for o in context.selected_objects:
            o.select_set(False)
        if st.hide_originals:
            for ob in obs:
                ob.hide_set(True)
        for hp in made:
            hp.select_set(True)
        context.view_layer.objects.active = made[-1]
        note = ' (smoothness lowered to stay under the face limit)' if lowered else ''
        if refused:
            note += ' - ' + '; '.join(refused)
        self.report({'WARNING'} if refused else {'INFO'},
                    f'High poly: {len(made)} object(s), {faces:,} faces in "{COLL}"{note}')
        return {'FINISHED'}


class MCH_OT_highpoly_view(bpy.types.Operator):
    """Show the low poly originals or the high poly copies"""
    bl_idname = 'mch.highpoly_view'
    bl_label = 'Low / High Poly View'
    bl_options = {'REGISTER', 'UNDO'}
    show: EnumProperty(items=[('LOW', 'Low Poly', ''), ('HIGH', 'High Poly', '')], default='HIGH')

    def execute(self, context):
        coll = bpy.data.collections.get(COLL)
        if coll is None:
            return {'CANCELLED'}
        names = set()
        for hp in coll.objects:
            names.update(str(hp.get(SRC_KEY, '')).split(','))
            hp.hide_set(self.show == 'LOW')
        for n in names:
            ob = context.view_layer.objects.get(n)
            if ob is not None:
                ob.hide_set(self.show == 'HIGH')
        return {'FINISHED'}


def draw(layout, context):
    box = layout.box()
    box.label(text='HIGH POLY  (for hand-off)', icon='MOD_SUBSURF')
    r = box.row()
    r.scale_y = 1.3
    r.operator('mch.make_highpoly', icon='MOD_SUBSURF')
    row = box.row(align=True)
    row.operator('mch.highpoly_view', text='Show Low').show = 'LOW'
    row.operator('mch.highpoly_view', text='Show High').show = 'HIGH'
    c = box.column(align=True)
    c.scale_y = 0.8
    c.label(text='Or right-click the selection > Make High Poly', icon='INFO')
    c.label(text='Bottom-left panel (F9): smoothness / edge softness')
    c.label(text='Copies in "HighPoly"; originals kept (hidden)')
    c.label(text='Export: File > Export > FBX as usual')


def _context_menu(self, context):
    if context.mode == 'OBJECT' and _targets(context):
        self.layout.separator()
        self.layout.operator('mch.make_highpoly', icon='MOD_SUBSURF')


class MCH_PT_highpoly(bpy.types.Panel):
    bl_idname = 'MCH_PT_highpoly'
    bl_label = 'High Poly'
    bl_space_type = 'VIEW_3D'
    bl_region_type = 'UI'
    bl_category = 'Mecha Lab'
    bl_order = 80

    @classmethod
    def poll(cls, context):
        from . import tool_state as ts
        return ts.sidebar_select(context)

    def draw(self, context):
        draw(self.layout, context)


CLASSES = (MCH_OT_make_highpoly, MCH_OT_highpoly_view, MCH_PT_highpoly)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.VIEW3D_MT_object_context_menu.append(_context_menu)


def unregister():
    try:
        bpy.types.VIEW3D_MT_object_context_menu.remove(_context_menu)
    except (ValueError, AttributeError):
        pass
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
