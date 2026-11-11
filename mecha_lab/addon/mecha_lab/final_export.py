"""0.24.95 Final High Poly (user: "최종으로 낼 때 하이폴리여야 돼서" - work light, hand in high): one button makes a
high copy of every part at the Final Resolution and writes the low and the high out.

  1. every part (the selected ones, or every visible mesh / curve) is copied; the copy is made again at the Final
     Resolution (``res_parts`` - Base Mesh outlines resampled, bevels / profiles / screws ... x the Resolution), its
     modifiers applied, and kept as a plain mesh "<part>_high" in the "MCH Final High" collection (hidden);
  2. Round Facets (optional): the copy is subdivided and rounded the Bake High Poly way (hard edges kept);
  3. Bake Maps (optional): Normal / AO of each high onto its part (the Bake Maps settings);
  4. Export (optional): "<file>_low.fbx" (the parts as they are) and "<file>_high.fbx" into the Folder.

The working parts are not rebuilt or changed (Bake Maps gives them UVs and the baked material, as Bake Maps
always does); the scene's Resolution is put back.  A second run replaces the earlier "_high" copies."""
from __future__ import annotations

import os
import time

import bpy
from bpy.props import BoolProperty, IntProperty, StringProperty

from . import tool_state as ts
from .light_copies import full as _lc_full  # 0.24.136 a part's own geometry, never its light copy

COLL = 'MCH Final High'
SRC_KEY = 'mch_final_src'
LAST = {}
FAILED = []


class MCH_PG_Final(bpy.types.PropertyGroup):
    final_res: IntProperty(name='Final Resolution', default=400, min=100, max=800, subtype='PERCENTAGE',
                           description='The Resolution the high copies are made at (circles, bevels, profiles ...)')
    round_facets: BoolProperty(name='Round Facets', default=False,
                               description='Also subdivide and round each high copy the Bake High Poly way (hard '
                                           'edges kept) - for parts that are faceted in themselves (decimated, cut)')
    round_faces: IntProperty(name='Round Target', default=200_000, min=10_000, max=4_000_000, step=10000,
                             description='Faces each rounded high copy is subdivided towards')
    bake: BoolProperty(name='Bake Maps', default=False,
                       description='Bake each high copy onto its part (Normal / AO ... as set in Bake Maps)')
    export: BoolProperty(name='Export FBX', default=True,
                         description='Write <file>_low.fbx (the parts) and <file>_high.fbx (the high copies)')
    folder: StringProperty(name='Folder', default='//final_export/', subtype='DIR_PATH',
                           description='Where the FBX files go (// = next to the saved .blend)')
    show: BoolProperty(name='Show', default=True, options={'HIDDEN'})


def settings(context):
    return getattr(context.scene, 'mch_final', None)


def parts(context):
    """The parts to finish: the selected meshes / curves, or every visible one (never our own high copies or the
    Bake High Poly copies)."""
    def ok(o):
        return o.type in {'MESH', 'CURVE'} and not o.get(SRC_KEY) and not o.get('mch_bakehp_src') \
            and o.name in context.view_layer.objects and not (o.users_collection and
                                                               all(c.name == COLL for c in o.users_collection))
    sel = [o for o in context.selected_objects if ok(o)]
    if sel:
        return sel
    return [o for o in context.view_layer.objects if ok(o) and o.visible_get()]


def _collection(context):
    coll = bpy.data.collections.get(COLL)
    if coll is None:
        coll = bpy.data.collections.new(COLL)
    if coll.name not in context.scene.collection.children:
        try:
            context.scene.collection.children.link(coll)
        except RuntimeError:
            pass
    return coll


def _drop_old(name):
    old = bpy.data.objects.get(name)
    if old is not None and old.get(SRC_KEY):
        me = old.data
        bpy.data.objects.remove(old, do_unlink=True)
        if me is not None and getattr(me, 'users', 1) == 0:
            bpy.data.meshes.remove(me)


def high_copy(context, ob, coll):
    """A plain mesh object: ``ob`` made again at the current Resolution, modifiers applied.  Returns (object,
    rebuilt (bool))."""
    from . import res_parts
    tmp = ob.copy()
    tmp.data = ob.data.copy()
    context.scene.collection.objects.link(tmp)
    rebuilt = False
    try:
        for label, fn in res_parts.live_kinds(tmp):
            try:
                fn(context, tmp)
                rebuilt = True
            except Exception as ex:                    # (it is copied as it is, and the message says so)
                FAILED.append(f'{ob.name} ({label}): {ex}')
        dg = context.evaluated_depsgraph_get()
        me = bpy.data.meshes.new_from_object(_lc_full(tmp, dg), preserve_all_data_layers=True, depsgraph=dg)
    finally:
        data = tmp.data
        bpy.data.objects.remove(tmp, do_unlink=True)
        if data is not None and data.users == 0:
            (bpy.data.curves if isinstance(data, bpy.types.Curve) else bpy.data.meshes).remove(data)
    name = ob.name + '_high'
    _drop_old(name)
    me.name = name
    hi = bpy.data.objects.new(name, me)
    hi.matrix_world = ob.matrix_world.copy()
    hi[SRC_KEY] = ob.name
    coll.objects.link(hi)
    return hi, rebuilt


def round_facets(hi, target):
    """Bake High Poly on the high copy's own mesh (hard edges kept, the faces between subdivided and rounded)."""
    from . import bake_highpoly as bk
    from . import budget
    me = hi.data
    f0 = len(me.polygons)
    if f0 < bk.MIN_FACES:
        return 0
    levels = bk.levels_for(f0, target)
    while levels > 1 and not budget.faces_fit(f0 * 4 ** levels)[0]:
        levels -= 1
    bk.bake_mesh(me, levels)
    me.shade_smooth()
    return levels


def _export(context, obs, path):
    keep_sel = [o for o in context.selected_objects]
    keep_act = context.view_layer.objects.active
    hidden = [o for o in obs if o.hide_get()]
    try:
        for o in context.selected_objects:
            o.select_set(False)
        for o in obs:
            o.hide_set(False)
            o.select_set(True)
        context.view_layer.objects.active = obs[0]
        os.makedirs(os.path.dirname(path), exist_ok=True)
        from . import light_copies
        light_copies.full_all(obs)                  # 0.24.136 the parts themselves, never their light copies
        bpy.ops.export_scene.fbx(filepath=path, use_selection=True, use_mesh_modifiers=True,
                                 object_types={'MESH', 'OTHER'})
    finally:
        for o in obs:
            o.select_set(False)
        for o in hidden:
            o.hide_set(True)
        for o in keep_sel:
            if o.name in context.view_layer.objects:
                o.select_set(True)
        context.view_layer.objects.active = keep_act


def folder_path(context, st):
    raw = st.folder or '//final_export/'
    if raw.startswith('//') and not bpy.data.filepath:
        raise RuntimeError('save the .blend first (the Folder is next to it), or pick a folder')
    return bpy.path.abspath(raw)


def run(context, st=None):
    """The whole pipeline.  Returns the message; LAST holds the numbers."""
    from . import live_queue
    st = st or settings(context)
    todo = parts(context)
    if not todo:
        raise RuntimeError('nothing to finish: select the parts (or show them)')
    out_dir = folder_path(context, st) if st.export else None
    live_queue.flush()
    t0 = time.time()
    coll = _collection(context)
    mset = context.scene.mch_settings
    res0 = mset.geo_res
    highs, rebuilt = [], 0
    FAILED.clear()
    try:
        mset.geo_res = st.final_res
        for ob in todo:
            hi, again = high_copy(context, ob, coll)
            highs.append((ob, hi))
            rebuilt += int(again)
    finally:
        mset.geo_res = res0
    rounded = 0
    if st.round_facets:
        for _ob, hi in highs:
            if round_facets(hi, st.round_faces):
                rounded += 1
    baked = 0
    if st.bake:
        from . import bake_maps as bm
        bst = bm.settings(context)
        keep = bm._Keep(context, [o for o, _h in highs] + [h for _o, h in highs])
        try:
            for ob, hi in highs:
                if ob.type == 'MESH':
                    bm.bake_pair(context, ob, [hi], bst, keep_state=keep)
                    baked += 1
        finally:
            keep.restore(context)
    files = []
    if st.export:
        stem = bpy.path.basename(bpy.data.filepath).rsplit('.', 1)[0] or 'mecha_lab'
        low_path = os.path.join(out_dir, stem + '_low.fbx')
        high_path = os.path.join(out_dir, stem + '_high.fbx')
        _export(context, [o for o, _h in highs], low_path)
        _export(context, [h for _o, h in highs], high_path)
        files = [low_path, high_path]
    for _ob, hi in highs:
        hi.hide_set(True)
    faces_low = sum(len(o.data.polygons) for o, _h in highs if o.type == 'MESH')
    faces_high = sum(len(h.data.polygons) for _o, h in highs)
    LAST.clear()
    LAST.update(parts=len(highs), rebuilt=rebuilt, rounded=rounded, baked=baked, files=files,
                faces_low=faces_low, faces_high=faces_high, seconds=time.time() - t0, res=st.final_res,
                highs=[h.name for _o, h in highs])
    msg = (f'Final High Poly: {len(highs)} parts at {st.final_res} % ({rebuilt} made again, '
           f'{len(highs) - rebuilt} copied as they are), {faces_high:,} faces')
    if rounded:
        msg += f', {rounded} rounded'
    if baked:
        msg += f', {baked} baked'
    if files:
        msg += ' -> ' + ', '.join(os.path.basename(f) for f in files)
    msg += f' ({LAST["seconds"]:.1f} s)'
    if FAILED:
        msg += ' | not made again (copied as they were): ' + '; '.join(FAILED[:3])
    return msg


class MCH_OT_final_highpoly(bpy.types.Operator):
    bl_idname = 'mch.final_highpoly'
    bl_label = 'Final High Poly'
    bl_description = ('Make a high copy of every part (selected, or all visible) at the Final Resolution - Round '
                      'Facets / Bake Maps if on - and export <file>_low.fbx and <file>_high.fbx. The parts you work on '
                      'stay as they are')
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        if context.mode != 'OBJECT':
            self.report({'WARNING'}, 'Final High Poly works in Object Mode')
            return {'CANCELLED'}
        try:
            msg = run(context)
        except RuntimeError as ex:
            self.report({'ERROR'}, f'Final High Poly: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    box = layout.box()
    box.label(text='FINAL HIGH POLY  (work light, hand in high)', icon='EXPORT')
    col = box.column(align=True)
    r = col.row(align=True)
    r.scale_y = 1.2
    r.operator('mch.final_highpoly', text='Final High Poly', icon='MOD_SUBSURF')
    r.prop(st, 'final_res', text='')
    r = col.row(align=True)
    r.prop(st, 'round_facets', toggle=True)
    sub = r.row(align=True)
    sub.active = st.round_facets
    sub.prop(st, 'round_faces', text='')
    r = col.row(align=True)
    r.prop(st, 'bake', toggle=True)
    r.prop(st, 'export', toggle=True)
    if st.export:
        col.prop(st, 'folder', text='')


classes = (MCH_PG_Final, MCH_OT_final_highpoly)


def register():
    for c in classes:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_final = bpy.props.PointerProperty(type=MCH_PG_Final)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_final'):
        del bpy.types.Scene.mch_final
    for c in reversed(classes):
        bpy.utils.unregister_class(c)
