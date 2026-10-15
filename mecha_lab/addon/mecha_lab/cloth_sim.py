"""0.23.8 Panel Cloth: a short real cloth simulation (Blender's own cloth solver), baked.

Like a "panel cloth" workflow: the panel is copied into its own object, subdivided, its
border pinned, then simulated for a few frames with Pressure (puffs it up), Shrink (a
negative value makes the cloth bigger than its frame, so it folds), Gravity and the body
as a collider - and the result is baked into the mesh (+ a Subdivision modifier).

Sources: the selected objects (Cloth / Armor Plate layers: their base panel, the body
they were drawn on is the collider; several panels on one body - e.g. Through front +
back - are joined into one cloth) or, in Edit Mode, the selected faces.  The source is
only hidden, the body only gets a temporary Collision modifier (removed after the bake).
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty

SUFFIX = '_PCloth'
MAX_FACES = 15000            # the cuts are lowered so the cloth stays light (a few seconds per bake)
PIN_GROUP = 'mch_pin'
PIN_MODES = (('BORDER', 'Border', 'The whole border stays where it is'),
             ('CORNERS', 'Corners', 'Only the corners of the border stay'),
             ('NONE', 'None', 'Nothing pinned: the cloth falls onto the body'))
SPLIT_MODES = (('NONE', 'None', 'One cloth'),
               ('ANGLE', 'Angle', 'Split where the faces meet at a sharp angle: every part puffs on its own'))


def collider_for(ob):
    """The body a cloth layer / plate was drawn on, or None."""
    name = ob.get('mch_wrinkle') if hasattr(ob, 'get') else None
    if isinstance(name, str) and name in bpy.data.objects:
        return bpy.data.objects[name]
    p = getattr(ob, 'mch_extract', None)
    return getattr(p, 'source', None) if p is not None else None


def _world_faces_from_object(ob):
    """(world coords, faces) of the object's base mesh (the panel before its live layers)."""
    mw = ob.matrix_world
    cos = [mw @ v.co for v in ob.data.vertices]
    faces = [tuple(p.vertices) for p in ob.data.polygons]
    return cos, faces


def _world_faces_from_selection(ob):
    bm = bmesh.from_edit_mesh(ob.data)
    mw = ob.matrix_world
    vmap, cos, faces = {}, [], []
    for f in [f for f in bm.faces if f.select]:
        idx = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = len(cos)
                cos.append(mw @ v.co)
            idx.append(vmap[v])
        faces.append(tuple(idx))
    return cos, faces


def build_cloth_mesh(parts, cuts=2, split='NONE', angle=30.0, noise=0.0, seed=1, weld=True):
    """One cloth mesh (world space) from [(cos, faces)]: joined, welded, split, subdivided, jittered.
    Returns (mesh, border vertex indices, corner vertex indices)."""
    bm = bmesh.new()
    try:
        for cos, faces in parts:
            vs = [bm.verts.new(c) for c in cos]
            for f in faces:
                try:
                    bm.faces.new([vs[i] for i in f])
                except ValueError:
                    pass
        bm.normal_update()
        if not bm.faces:
            raise ValueError('Nothing to simulate')
        avg = sum(e.calc_length() for e in bm.edges) / max(len(bm.edges), 1)
        if weld:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=avg * 0.35)
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        if split == 'ANGLE':
            lim = math.radians(angle)
            sharp = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim]
            if sharp:
                bmesh.ops.split_edges(bm, edges=sharp)
        while cuts > 0 and len(bm.faces) * (cuts + 1) ** 2 > MAX_FACES:
            cuts -= 1
        if cuts > 0:
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
        bm.normal_update()
        if noise > 0.0:
            rng = random.Random(seed)
            step = sum(e.calc_length() for e in bm.edges) / max(len(bm.edges), 1)
            for v in bm.verts:
                if not v.is_boundary:
                    v.co += v.normal * (rng.uniform(-1.0, 1.0) * noise * step)
        bm.verts.index_update()
        border = [v.index for v in bm.verts if v.is_boundary]
        corners = []
        for v in bm.verts:
            if not v.is_boundary:
                continue
            nb = [e.other_vert(v) for e in v.link_edges if e.is_boundary]
            if len(nb) == 2:
                a, b = (nb[0].co - v.co), (nb[1].co - v.co)
                if a.length > 1e-12 and b.length > 1e-12 and a.angle(b) < math.radians(150):
                    corners.append(v.index)
        me = bpy.data.meshes.new('PCloth')
        bm.to_mesh(me)
    finally:
        bm.free()
    return me, border, corners


def setup_cloth(scene, ob, frames=30, quality=5, mass=0.15, pressure=4.0, shrink=-0.05, gravity=1.0,
                thickness=0.005, self_collision=False, pin_group=None):
    cm = ob.modifiers.new('MCH_PanelCloth', 'CLOTH')
    s = cm.settings
    s.quality = quality
    s.mass = mass
    s.use_pressure = abs(pressure) > 1e-9
    s.uniform_pressure_force = pressure
    s.shrink_min = shrink
    s.effector_weights.gravity = gravity
    if pin_group:
        s.vertex_group_mass = pin_group
    c = cm.collision_settings
    c.use_collision = True
    c.distance_min = thickness
    c.use_self_collision = self_collision
    cm.point_cache.frame_start = scene.frame_start
    cm.point_cache.frame_end = scene.frame_start + frames
    return cm


def bake(context, objs, frames):
    """Play the frames (the cloth caches fill) and keep the last frame as each object's mesh."""
    scene = context.scene
    keep = scene.frame_current
    start = scene.frame_start
    for f in range(start, start + frames + 1):
        scene.frame_set(f)
    dg = context.evaluated_depsgraph_get()
    for ob in objs:
        me = bpy.data.meshes.new_from_object(ob.evaluated_get(dg), depsgraph=dg)
        old = ob.data
        for m in [m for m in ob.modifiers if m.type == 'CLOTH']:
            ob.modifiers.remove(m)
        ob.data = me
        me.name = old.name
        if old.users == 0:
            bpy.data.meshes.remove(old)
    scene.frame_set(keep)


def panel_cloth(context, sources, edit_object=None, frames=30, quality=5, seed=1, mass=0.15, pressure=4.0,
                shrink=-0.05, gravity=1.0, cuts=2, noise=0.0, subsurf=1, pin='BORDER', collide=True,
                self_collision=False, thickness=0.005, split='NONE', angle=30.0, join=True, hide_source=True):
    """Make + simulate + bake the cloth objects.  Returns the new objects."""
    groups = {}
    if edit_object is not None:
        groups[edit_object.name] = [(edit_object, _world_faces_from_selection(edit_object), edit_object)]
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        for ob in sources:
            body = collider_for(ob)
            key = body.name if (join and body is not None) else ob.name
            groups.setdefault(key, []).append((ob, _world_faces_from_object(ob), body))
    made, temp_cols = [], []
    for items in groups.values():
        parts = [it[1] for it in items if it[1][1]]
        if not parts:
            continue
        first, body = items[0][0], items[0][2]
        me, border, corners = build_cloth_mesh(parts, cuts, split, angle, noise, seed, weld=True)
        ob = bpy.data.objects.new(first.name + SUFFIX, me)
        coll = first.users_collection[0] if first.users_collection else context.scene.collection
        coll.objects.link(ob)
        for mat in first.data.materials:
            me.materials.append(mat)
        pins = border if pin == 'BORDER' else corners if pin == 'CORNERS' else []
        if pins:
            ob.vertex_groups.new(name=PIN_GROUP).add(pins, 1.0, 'REPLACE')
        setup_cloth(context.scene, ob, frames, quality, mass, pressure, shrink, gravity, thickness,
                    self_collision, PIN_GROUP if pins else None)
        if collide and body is not None and body.type == 'MESH' and body is not ob and \
                not any(m.type == 'COLLISION' for m in body.modifiers):
            body.modifiers.new('MCH_TempCollision', 'COLLISION')
            temp_cols.append(body)
        ob['mch_pcloth'] = first.name
        made.append((ob, items))
    try:
        bake(context, [m[0] for m in made], frames)
    finally:
        for body in temp_cols:
            m = body.modifiers.get('MCH_TempCollision')
            if m is not None:
                body.modifiers.remove(m)
    out = []
    for ob, items in made:
        for p in ob.data.polygons:
            p.use_smooth = True
        if subsurf > 0:
            ob.modifiers.new('MCH_Subsurf', 'SUBSURF').levels = subsurf
        if hide_source and items[0][0] is not edit_object:
            for src, _f, _b in items:
                src.hide_set(True)
                src.hide_render = True
        out.append(ob)
    return out


class MCH_OT_panel_cloth(bpy.types.Operator):
    """Panel Cloth: a short cloth simulation on the selected panels (or the selected faces) - puffed up by
    Pressure, folded by Shrink, pinned at the border, on the body as a collider - then baked"""
    bl_idname = 'mch.panel_cloth'
    bl_label = 'Panel Cloth'
    bl_options = {'REGISTER', 'UNDO'}
    split: EnumProperty(name='Split', items=SPLIT_MODES, default='NONE')
    angle: FloatProperty(name='Angle', default=math.radians(30.0), min=0.0, max=math.pi, subtype='ANGLE')
    frames: IntProperty(name='Bake Frames', default=30, min=1, max=500)
    quality: IntProperty(name='Quality', default=5, min=1, max=40)
    seed: IntProperty(name='Cloth Seed', default=1, min=0)
    mass: FloatProperty(name='Mass', default=0.15, min=0.001, max=10.0)
    pressure: FloatProperty(name='Pressure', default=4.0, min=-50.0, max=50.0,
                            description='Puffs the panel up (negative pulls it in)')
    shrink: FloatProperty(name='Shrink', default=-0.05, min=-1.0, max=1.0,
                          description='Negative: the cloth is bigger than its frame - it folds')
    gravity: FloatProperty(name='Gravity', default=1.0, min=0.0, max=10.0)
    cuts: IntProperty(name='Subdivision', default=2, min=0, max=10, description='Cuts per edge before the sim')
    noise: FloatProperty(name='Noise', default=0.0, min=0.0, max=1.0, description='Random start offset')
    subsurf: IntProperty(name='Subsurf Level', default=1, min=0, max=3)
    pin: EnumProperty(name='Pin', items=PIN_MODES, default='BORDER')
    collide: BoolProperty(name='Collide To Source', default=True, description='The body is a collider')
    self_collision: BoolProperty(name='Self Collision', default=False)
    thickness: FloatProperty(name='Thickness', default=0.005, min=0.0, max=1.0, unit='LENGTH')
    join: BoolProperty(name='Join Panels', default=True,
                       description='Panels on the same body (e.g. Through front + back) become one cloth')
    hide_source: BoolProperty(name='Hide Source', default=True)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is not None and ob.mode == 'EDIT':
            return ob.type == 'MESH'
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=320)

    def draw(self, context):
        lay = self.layout
        lay.use_property_split = True
        col = lay.column(align=True)
        col.row().prop(self, 'split', expand=True)
        if self.split == 'ANGLE':
            col.prop(self, 'angle')
        for k in ('frames', 'quality', 'seed'):
            col.prop(self, k)
        col = lay.column(align=True)
        for k in ('mass', 'pressure', 'shrink', 'gravity'):
            col.prop(self, k)
        col = lay.column(align=True)
        for k in ('cuts', 'noise', 'subsurf'):
            col.prop(self, k)
        col = lay.column(align=True)
        col.row().prop(self, 'pin', expand=True)
        for k in ('collide', 'self_collision', 'thickness', 'join', 'hide_source'):
            col.prop(self, k)

    def execute(self, context):
        ob = context.active_object
        edit = ob if (ob is not None and ob.mode == 'EDIT') else None
        if edit is not None and not any(f.select for f in bmesh.from_edit_mesh(edit.data).faces):
            self.report({'WARNING'}, 'Select faces first')
            return {'CANCELLED'}
        srcs = [o for o in context.selected_objects if o.type == 'MESH']
        try:
            made = panel_cloth(context, srcs, edit, self.frames, self.quality, self.seed, self.mass, self.pressure,
                               self.shrink, self.gravity, self.cuts, self.noise, self.subsurf, self.pin,
                               self.collide, self.self_collision, self.thickness, self.split,
                               math.degrees(self.angle), self.join, self.hide_source)
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in made:
            o.select_set(True)
        if made:
            context.view_layer.objects.active = made[0]
        self.report({'INFO'}, f'Panel Cloth: {len(made)} cloth object(s), {self.frames} frames baked')
        return {'FINISHED'}


CLASSES = (MCH_OT_panel_cloth,)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
