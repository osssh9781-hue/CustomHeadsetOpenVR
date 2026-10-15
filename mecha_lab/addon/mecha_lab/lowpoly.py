"""0.23.22 Low Poly from a sculpt (ZBrush / dense meshes) as a rough robot base mesh.

Make Low Poly: a copy of the selected mesh is voxel remeshed (closes holes, even density), reduced to about
``Faces`` faces and flat areas are merged into big faces (baked - so dragging the bevel stays fast).  The
original is kept, hidden.  Live on the copy: a Bevel on the edges sharper than ``Angle`` (Segments 1 =
chamfer, more = round, Profile) and Weighted Normals.  Re-make with other settings, or Apply.
"""
from __future__ import annotations

import math

import bpy
from bpy.props import FloatProperty, IntProperty

SRC_KEY = 'mch_lowpoly_source'
BEVEL = 'MCH_LP_Bevel'
NORMALS = 'MCH_LP_Normals'


class MCH_PG_LowPoly(bpy.types.PropertyGroup):
    detail: IntProperty(name='Detail', default=64, min=8, max=400,
                        description='Voxels across the longest side for the clean-up remesh (higher = more shape)')
    faces: IntProperty(name='Faces', default=3000, min=50, max=200000,
                       description='About this many faces before flat areas are merged')
    flat_angle: FloatProperty(name='Flat Merge', default=math.radians(4.0), min=0.0, max=math.radians(30.0),
                              subtype='ANGLE', description='Neighbouring faces closer than this become one big face')
    side_angle: FloatProperty(name='Flatten Sides', default=math.radians(25.0), min=0.0, max=math.radians(60.0),
                              subtype='ANGLE', description='Faces within this of a side\'s main direction are pushed '
                                                           'flat onto it (0 = off). Bigger = fewer, flatter sides')
    bevel_width: FloatProperty(name='Bevel Width', default=0.01, min=0.0, soft_max=0.2, precision=4,
                               description='Bevel width as a part of the mesh size')
    bevel_segments: IntProperty(name='Segments', default=1, min=1, max=12, description='1 = chamfer, more = round')
    bevel_angle: FloatProperty(name='Angle', default=math.radians(30.0), min=math.radians(1.0),
                               max=math.radians(180.0), subtype='ANGLE',
                               description='Only edges sharper than this get the bevel')


def is_lowpoly(ob):
    return ob is not None and ob.type == 'MESH' and SRC_KEY in ob


def _size(ob):
    """Longest side in the object's own space (modifier sizes are in object space; a ZBrush FBX often
    comes with an unapplied scale like 0.01)."""
    if ob.type == 'MESH' and ob.data.vertices:
        import numpy as np
        co = np.empty(len(ob.data.vertices) * 3)
        ob.data.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        return max(float((co.max(0) - co.min(0)).max()), 1e-9)
    d = ob.dimensions
    s = max(max(ob.scale), 1e-9)
    return max(max(d) / s, 1e-9)


def flatten_sides(me, angle, keep=0.02):
    """0.23.22 each side of the shape becomes flat: faces are grouped while their normals stay within
    ``angle`` of the group's main direction (area weighted), every point of a group is pushed onto that
    group's plane; points shared by several groups go where the planes meet (straight edges / corners).
    Groups smaller than a tiny part of the area are left as they are.  ``keep`` holds points a little to
    where they were (planes that are nearly parallel)."""
    from collections import deque
    import numpy as np
    import bmesh
    bm = bmesh.new()
    try:
        bm.from_mesh(me)
        bm.faces.ensure_lookup_table()
        bm.verts.ensure_lookup_table()
        nf = len(bm.faces)
        if nf == 0:
            return 0
        nrm = np.array([f.normal[:] for f in bm.faces])
        area = np.array([f.calc_area() for f in bm.faces])
        cen = np.array([f.calc_center_median()[:] for f in bm.faces])
        nbrs = [[g.index for e in f.edges for g in e.link_faces if g is not f] for f in bm.faces]
        cos_t = np.cos(angle)
        group = np.full(nf, -1, dtype=np.int64)
        planes = []
        total = float(area.sum()) or 1.0
        for seed in np.argsort(-area):
            if group[seed] >= 0:
                continue
            gid = len(planes)
            group[seed] = gid
            nsum = nrm[seed] * area[seed]
            stack = deque([seed])                # breadth first: round groups, not snakes
            members = [seed]
            while stack:
                f = stack.popleft()
                nmean = nsum / (np.linalg.norm(nsum) or 1.0)
                for g in nbrs[f]:
                    if group[g] < 0 and float(nrm[g] @ nmean) >= cos_t:
                        group[g] = gid
                        nsum = nsum + nrm[g] * area[g]
                        stack.append(g)
                        members.append(g)
            planes.append(None)                 # filled below
        ng = len(planes)

        def fit():
            out = []
            for gi in range(ng):
                m = np.nonzero(group == gi)[0]
                if len(m) == 0:
                    out.append(None)
                    continue
                a = area[m]
                nsum = (nrm[m] * a[:, None]).sum(0)
                n = nsum / (np.linalg.norm(nsum) or 1.0)
                out.append((n, float((cen[m] @ n * a).sum() / a.sum()), float(a.sum())))
            return out

        planes = fit()
        size = float(np.linalg.norm(cen.max(0) - cen.min(0))) or 1.0
        # tiny groups join the neighbouring group that fits them best
        small = total * 0.003
        for gi, pl in enumerate(planes):
            if pl is None or pl[2] >= small:
                continue
            m = np.nonzero(group == gi)[0]
            cand = {group[g] for f in m for g in nbrs[f]} - {gi}
            cand = [c for c in cand if planes[c] is not None and planes[c][2] >= small]
            if cand:
                best = max(cand, key=lambda c: float(planes[c][0] @ pl[0]))
                group[m] = best
        planes = fit()
        # straighten the borders: a face may move to a neighbouring group whose plane fits it better
        for _it in range(8):
            changed = 0
            for f in range(nf):
                cur = group[f]
                best, best_cost = cur, None
                for c in {cur} | {group[g] for g in nbrs[f]}:
                    pl = planes[c]
                    if pl is None:
                        continue
                    cost = (1.0 - float(nrm[f] @ pl[0])) + 4.0 * abs(float(cen[f] @ pl[0]) - pl[1]) / size
                    if best_cost is None or cost < best_cost - 1e-12:
                        best, best_cost = c, cost
                if best != cur:
                    group[f] = best
                    changed += 1
            planes = fit()
            if not changed:
                break
        planes = [None if (pl is None or pl[2] < small) else (pl[0], pl[1]) for pl in planes]
        moved = 0
        eye = np.eye(3)
        for v in bm.verts:
            ps = {group[f.index] for f in v.link_faces}
            ps = [planes[g] for g in ps if planes[g] is not None]
            if not ps:
                continue
            x0 = np.array(v.co[:])
            A = keep * eye
            b = keep * x0
            for n, d in ps:
                A = A + np.outer(n, n)
                b = b + n * d
            v.co = np.linalg.solve(A, b).tolist()
            moved += 1
        bm.normal_update()
        bm.to_mesh(me)
    finally:
        bm.free()
    me.update()
    return len([p for p in planes if p is not None])


def _evaluated_copy(context, ob, mods):
    """Bake ``mods`` [(type, {attr: value})] on a temporary copy of ``ob``; returns the new mesh."""
    tmp = ob.copy()
    tmp.data = ob.data.copy()
    tmp.modifiers.clear()
    context.scene.collection.objects.link(tmp)
    try:
        for i, (kind, attrs) in enumerate(mods):
            m = tmp.modifiers.new(f'lp{i}', kind)
            for k, v in attrs.items():
                setattr(m, k, v)
        dg = context.evaluated_depsgraph_get()
        dg.update()
        me = bpy.data.meshes.new_from_object(tmp.evaluated_get(dg), preserve_all_data_layers=False, depsgraph=dg)
    finally:
        data = tmp.data
        bpy.data.objects.remove(tmp, do_unlink=True)
        if data.users == 0:
            bpy.data.meshes.remove(data)
    return me


def build_mesh(context, src, detail, faces, flat_angle, side_angle=0.0):
    """The low poly mesh (object space of ``src``): voxel remesh -> fewer faces -> flatten the sides ->
    merge flat areas."""
    voxel = _size(src) / max(8, detail)
    me = _evaluated_copy(context, src, [('REMESH', {'mode': 'VOXEL', 'voxel_size': voxel})])
    me = _bake_steps(context, src, me, [('DECIMATE', {'decimate_type': 'COLLAPSE',
                                                      'ratio': min(1.0, faces * (3 if side_angle > 0 else 1)
                                                                   / max(len(me.polygons), 1))})])
    if side_angle > 0:
        flatten_sides(me, side_angle)
    if flat_angle > 0:
        me = _bake_steps(context, src, me, [('DECIMATE', {'decimate_type': 'DISSOLVE', 'angle_limit': flat_angle})])
    return me


def _bake_steps(context, src, me, steps):
    tmp = bpy.data.objects.new('MCH_LP_tmp', me)
    tmp.matrix_world = src.matrix_world.copy()
    context.scene.collection.objects.link(tmp)
    try:
        out = _evaluated_copy(context, tmp, steps)
    finally:
        bpy.data.objects.remove(tmp, do_unlink=True)
        if me.users == 0:
            bpy.data.meshes.remove(me)
    return out


def _live_modifiers(ob, st):
    bev = ob.modifiers.get(BEVEL) or ob.modifiers.new(BEVEL, 'BEVEL')
    bev.limit_method = 'ANGLE'
    bev.angle_limit = st.bevel_angle
    bev.width = st.bevel_width * _size(ob) / max(max(ob.scale), 1e-9)
    bev.segments = st.bevel_segments
    bev.profile = 0.5
    bev.use_clamp_overlap = True
    bev.harden_normals = True
    wn = ob.modifiers.get(NORMALS) or ob.modifiers.new(NORMALS, 'WEIGHTED_NORMAL')
    wn.keep_sharp = True
    return bev, wn


def make(context, src, st):
    if src is None or src.type != 'MESH':
        raise RuntimeError('Select a mesh (your sculpt) first.')
    me = build_mesh(context, src, st.detail, st.faces, st.flat_angle, st.side_angle)
    me.name = src.name + '_Low'
    ob = bpy.data.objects.new(src.name + '_Low', me)
    for coll in src.users_collection:
        coll.objects.link(ob)
    ob.matrix_world = src.matrix_world.copy()
    ob[SRC_KEY] = src.name
    for p in me.polygons:
        p.use_smooth = True
    _live_modifiers(ob, st)
    src.hide_set(True)
    for o in context.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    context.view_layer.objects.active = ob
    return ob


def remake(context, ob, st):
    src = bpy.data.objects.get(ob.get(SRC_KEY, ''))
    if src is None:
        raise RuntimeError('The original sculpt is gone; cannot re-make.')
    me = build_mesh(context, src, st.detail, st.faces, st.flat_angle, st.side_angle)
    old = ob.data
    me.name = old.name
    ob.data = me
    for p in me.polygons:
        p.use_smooth = True
    if old.users == 0:
        bpy.data.meshes.remove(old)
    return ob


def apply(context, ob):
    with context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob]):
        for name in (BEVEL, NORMALS):
            if ob.modifiers.get(name) is not None:
                bpy.ops.object.modifier_apply(modifier=name)
    if SRC_KEY in ob:
        del ob[SRC_KEY]


class MCH_OT_lowpoly_make(bpy.types.Operator):
    """Low poly copy of the selected sculpt with a live Bevel / Chamfer (the original is kept, hidden)"""
    bl_idname = 'mch.lowpoly_make'
    bl_label = 'Make Low Poly'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        st = context.scene.mch_lowpoly
        ob = context.active_object
        try:
            if is_lowpoly(ob):
                remake(context, ob, st)
            else:
                ob = make(context, ob, st)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        self.report({'INFO'}, f'{ob.name}: {len(ob.data.polygons)} faces (low poly), live Bevel')
        return {'FINISHED'}


class MCH_OT_lowpoly_apply(bpy.types.Operator):
    """Make the bevel permanent (the low poly becomes an ordinary mesh)"""
    bl_idname = 'mch.lowpoly_apply'
    bl_label = 'Apply Low Poly'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_lowpoly(context.active_object)

    def execute(self, context):
        apply(context, context.active_object)
        return {'FINISHED'}


class MCH_OT_lowpoly_show_source(bpy.types.Operator):
    """Show / hide the original sculpt"""
    bl_idname = 'mch.lowpoly_show_source'
    bl_label = 'Show Original'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_lowpoly(context.active_object)

    def execute(self, context):
        src = bpy.data.objects.get(context.active_object.get(SRC_KEY, ''))
        if src is not None:
            src.hide_set(not src.hide_get())
        return {'FINISHED'}


def draw(layout, context):
    st = context.scene.mch_lowpoly
    ob = context.active_object
    box = layout.box()
    box.label(text='LOW POLY (sculpt -> base mesh)', icon='MOD_DECIM')
    col = box.column(align=True)
    col.prop(st, 'detail')
    col.prop(st, 'faces')
    col.prop(st, 'side_angle')
    col.prop(st, 'flat_angle')
    row = box.row(align=True)
    row.scale_y = 1.3
    row.operator('mch.lowpoly_make', text='Re-make Low Poly' if is_lowpoly(ob) else 'Make Low Poly',
                 icon='FILE_REFRESH' if is_lowpoly(ob) else 'MOD_DECIM')
    if not is_lowpoly(ob):
        box.label(text='Select your sculpt (ZBrush import) first', icon='INFO')
        return
    bev = ob.modifiers.get(BEVEL)
    if bev is not None:
        col = box.column(align=True)
        col.label(text=f'{len(ob.data.polygons)} faces | Bevel / Chamfer (live)')
        col.prop(bev, 'width')
        col.prop(bev, 'segments', text='Segments (1 = chamfer)')
        col.prop(bev, 'profile', slider=True)
        col.prop(bev, 'angle_limit', text='Edges sharper than')
    row = box.row(align=True)
    row.operator('mch.lowpoly_show_source', icon='HIDE_OFF')
    row.operator('mch.lowpoly_apply', icon='CHECKMARK')


CLASSES = (MCH_PG_LowPoly, MCH_OT_lowpoly_make, MCH_OT_lowpoly_apply, MCH_OT_lowpoly_show_source)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_lowpoly = bpy.props.PointerProperty(type=MCH_PG_LowPoly)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_lowpoly'):
        del bpy.types.Scene.mch_lowpoly
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
