"""0.23.8 / 0.23.9 Panel Cloth: a short real cloth simulation (Blender's own cloth solver), baked.

The panel is copied into its own object, subdivided, its border pinned, then simulated for
a few frames - Pressure puffs it up (padding), Shrink below 0 makes the cloth bigger than
its frame so it folds (cloth), Gravity, Mass and Bend (bending stiffness) set how it hangs -
and the last frame is baked into the mesh (+ a Subdivision modifier).

0.23.9:
  * Presets: padding family (Padding, Puffer, Pillow, Quilt) and cloth family (Cloth, Silk,
    Canvas, Leather, Tight).
  * Collider: Region (the surface the panel was made from - the faces we generate - so the
    cloth cannot sink into it; light), Body (the whole mesh it was drawn on) or None.
  * Islands: Split None / Angle / Seam; Random gives every split piece its own Shrink
    (between Shrink and Shrink Max) and pressure (Variation) - like per-piece seeds.
  * The Cloth Plate lasso can run it right away (Sim toggle + preset), and a baked cloth can
    be redone with another preset from its source (``mch.panel_cloth_redo``).

Sources: the selected objects (Cloth / Armor Plate layers: their base panel; several panels
on one body - e.g. Through front + back - are joined into one cloth) or, in Edit Mode, the
selected faces.  The source is only hidden; temporary colliders are removed after the bake.
"""
from __future__ import annotations

import math
import random

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

SUFFIX = '_PCloth'
PIN_GROUP = 'mch_pin'
SHRINK_GROUP = 'mch_shrink'
PRESSURE_GROUP = 'mch_pressure'
MAX_FACES = 15000            # the cuts are lowered so the cloth stays light (a few seconds per bake)
PIN_MODES = (('BORDER', 'Border', 'The whole border stays where it is'),
             ('CORNERS', 'Corners', 'Only the corners of the border stay'),
             ('NONE', 'None', 'Nothing pinned: the cloth falls onto the body'))
SPLIT_MODES = (('NONE', 'None', 'One cloth'),
               ('ANGLE', 'Angle', 'Split where the faces meet at a sharp angle: every part puffs on its own'),
               ('SEAM', 'Seam', 'Split along seams / sharp edges marked on the source'))
COLLIDERS = (('REGION', 'Region', 'The surface the panel was made from (the generated faces) - light'),
             ('BODY', 'Body', 'The whole mesh it was drawn on'),
             ('NONE', 'None', 'No collision'))
# name, label, description, settings
PRESETS = (
    ('PADDING', 'Padding', 'Firm padded panel, folds along the border',
     dict(pressure=9.0, shrink=-0.05, gravity=0.3, mass=0.15, bend=0.5, cuts=3, frames=30, quality=5)),
    ('PUFFER', 'Puffer', 'Down jacket: strongly puffed, soft border folds',
     dict(pressure=16.0, shrink=-0.08, gravity=0.2, mass=0.1, bend=0.3, cuts=3, frames=35, quality=6)),
    ('PILLOW', 'Pillow', 'Soft cushion: puffed with many loose folds',
     dict(pressure=7.0, shrink=-0.16, gravity=0.5, mass=0.15, bend=0.2, cuts=3, frames=35, quality=6)),
    ('QUILT', 'Quilt', 'Every split piece puffs on its own (use Split Angle / Seam)',
     dict(pressure=10.0, shrink=-0.06, gravity=0.3, mass=0.15, bend=0.4, cuts=3, frames=30, quality=5,
          random=True, variation=0.4)),
    ('CLOTH', 'Cloth', 'Loose fabric: no puff, hangs and folds',
     dict(pressure=0.0, shrink=-0.15, gravity=1.0, mass=0.3, bend=0.5, cuts=3, frames=40, quality=6)),
    ('SILK', 'Silk', 'Thin light fabric: many small folds',
     dict(pressure=0.0, shrink=-0.22, gravity=1.0, mass=0.05, bend=0.02, cuts=4, frames=45, quality=8)),
    ('CANVAS', 'Canvas', 'Heavy fabric: few big soft folds',
     dict(pressure=0.5, shrink=-0.1, gravity=1.5, mass=0.6, bend=5.0, cuts=3, frames=40, quality=6)),
    ('LEATHER', 'Leather', 'Stiff: a slight puff and a few thick folds',
     dict(pressure=1.5, shrink=-0.06, gravity=0.8, mass=0.5, bend=20.0, cuts=3, frames=35, quality=6)),
    ('CRUMPLE', 'Crumple', 'Crumpled thin fabric: lots of crossing creases',
     dict(pressure=0.4, shrink=-0.3, gravity=0.0, mass=0.05, bend=0.01, cuts=4, frames=40, quality=8, noise=0.15)),
)
PRESET_IDS = tuple(p[0] for p in PRESETS)
PRESET_ITEMS = tuple((p[0], p[1], p[2]) for p in PRESETS)


def preset_values(name):
    base = dict(pressure=4.0, shrink=-0.05, shrink_max=None, gravity=1.0, mass=0.15, bend=0.5, cuts=2,
                frames=30, quality=5, noise=0.0, random=False, variation=0.0)
    for pid, _l, _d, vals in PRESETS:
        if pid == name:
            base.update(vals)
    return base


def collider_for(ob):
    """The body a cloth layer / plate was drawn on, or None."""
    name = ob.get('mch_wrinkle') if hasattr(ob, 'get') else None
    if isinstance(name, str) and name in bpy.data.objects:
        return bpy.data.objects[name]
    p = getattr(ob, 'mch_extract', None)
    return getattr(p, 'source', None) if p is not None else None


def _world_faces_from_object(ob):
    """(world coords, faces, seam edge keys) of the object's base mesh (the panel before its live layers)."""
    mw = ob.matrix_world
    me = ob.data
    cos = [mw @ v.co for v in me.vertices]
    faces = [tuple(p.vertices) for p in me.polygons]
    seams = {frozenset(e.vertices) for e in me.edges if e.use_seam or getattr(e, 'use_edge_sharp', False)}
    return cos, faces, seams


def _world_faces_from_selection(ob):
    bm = bmesh.from_edit_mesh(ob.data)
    mw = ob.matrix_world
    vmap, cos, faces = {}, [], []
    sel = [f for f in bm.faces if f.select]
    for f in sel:
        idx = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = len(cos)
                cos.append(mw @ v.co)
            idx.append(vmap[v])
        faces.append(tuple(idx))
    seams = set()
    for f in sel:
        for e in f.edges:
            if e.seam or not e.smooth:
                a, b = e.verts
                if a in vmap and b in vmap:
                    seams.add(frozenset((vmap[a], vmap[b])))
    return cos, faces, seams


def build_cloth_mesh(parts, cuts=2, split='NONE', angle=30.0, noise=0.0, seed=1, weld=True,
                     random_islands=False, variation=0.0):
    """One cloth mesh (world space) from [(cos, faces, seams)]: joined, welded, split, subdivided, jittered.
    Returns (mesh, border indices, corner indices, {vertex index: (shrink weight, pressure weight)})."""
    bm = bmesh.new()
    try:
        seam_keys = []
        for part in parts:
            cos, faces = part[0], part[1]
            seams = part[2] if len(part) > 2 else set()
            vs = [bm.verts.new(c) for c in cos]
            for f in faces:
                try:
                    bm.faces.new([vs[i] for i in f])
                except ValueError:
                    pass
            seam_keys += [(vs[a], vs[b]) for a, b in (tuple(k) for k in seams if len(k) == 2)]
        bm.normal_update()
        if not bm.faces:
            raise ValueError('Nothing to simulate')
        seam_edges = set()
        for a, b in seam_keys:
            e = bm.edges.get((a, b))
            if e is not None:
                seam_edges.add(e)
        avg = sum(e.calc_length() for e in bm.edges) / max(len(bm.edges), 1)
        if weld:
            bmesh.ops.remove_doubles(bm, verts=bm.verts[:], dist=avg * 0.35)
            seam_edges = {e for e in seam_edges if e.is_valid}
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces[:])
        cut = []
        if split == 'ANGLE':
            lim = math.radians(angle)
            cut = [e for e in bm.edges if len(e.link_faces) == 2 and e.calc_face_angle(0.0) > lim]
        elif split == 'SEAM':
            cut = [e for e in seam_edges if len(e.link_faces) == 2]
        if cut:
            bmesh.ops.split_edges(bm, edges=cut)
        while cuts > 0 and len(bm.faces) * (cuts + 1) ** 2 > MAX_FACES:
            cuts -= 1
        if cuts > 0:
            bmesh.ops.subdivide_edges(bm, edges=bm.edges[:], cuts=cuts, use_grid_fill=True)
        bm.normal_update()
        rng = random.Random(seed)
        if noise > 0.0:
            step = sum(e.calc_length() for e in bm.edges) / max(len(bm.edges), 1)
            for v in bm.verts:
                if not v.is_boundary:
                    v.co += v.normal * (rng.uniform(-1.0, 1.0) * noise * step)
        bm.verts.index_update()
        # islands: every split piece its own shrink / pressure weight
        weights = {}
        seen = set()
        for f0 in bm.faces:
            if f0 in seen:
                continue
            stack, isl = [f0], []
            seen.add(f0)
            while stack:
                f = stack.pop()
                isl.append(f)
                for e in f.edges:
                    for g in e.link_faces:
                        if g not in seen:
                            seen.add(g)
                            stack.append(g)
            r = rng.random() if random_islands else 0.0
            pw = 1.0 - variation * rng.random() if random_islands else 1.0
            for f in isl:
                for v in f.verts:
                    weights[v.index] = (r, pw)
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
    return me, border, corners, weights


def setup_cloth(scene, ob, frames=30, quality=5, mass=0.15, pressure=4.0, shrink=-0.05, gravity=1.0,
                thickness=0.005, self_collision=False, pin_group=None, bend=0.5, shrink_max=None,
                weights=None):
    cm = ob.modifiers.new('MCH_PanelCloth', 'CLOTH')
    s = cm.settings
    s.quality = quality
    s.mass = mass
    s.bending_stiffness = bend
    s.use_pressure = abs(pressure) > 1e-9
    s.uniform_pressure_force = pressure
    s.shrink_min = shrink
    if pin_group:
        s.vertex_group_mass = pin_group
    if weights:
        if shrink_max is not None:
            vg = ob.vertex_groups.new(name=SHRINK_GROUP)
            for i, (r, _p) in weights.items():
                vg.add([i], r, 'REPLACE')
            s.vertex_group_shrink = SHRINK_GROUP
            s.shrink_max = shrink_max
        if any(p < 0.999 for _r, p in weights.values()):
            vg = ob.vertex_groups.new(name=PRESSURE_GROUP)
            for i, (_r, p) in weights.items():
                vg.add([i], p, 'REPLACE')
            s.vertex_group_pressure = PRESSURE_GROUP
    s.effector_weights.gravity = gravity
    c = cm.collision_settings
    c.use_collision = True
    c.distance_min = thickness
    c.collision_quality = 3
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


def _region_collider(context, parts, name):
    """A temporary collision object made of the panel's own surface (the generated faces)."""
    me = bpy.data.meshes.new(name)
    cos, faces, off = [], [], 0
    for part in parts:
        cos += list(part[0])
        faces += [tuple(i + off for i in f) for f in part[1]]
        off += len(part[0])
    me.from_pydata([tuple(c) for c in cos], [], faces)
    me.update()
    ob = bpy.data.objects.new(name, me)
    context.scene.collection.objects.link(ob)
    ob.hide_render = True
    ob.modifiers.new('Collision', 'COLLISION')
    return ob


def panel_cloth(context, sources, edit_object=None, frames=30, quality=5, seed=1, mass=0.15, pressure=4.0,
                shrink=-0.05, gravity=1.0, cuts=2, noise=0.0, subsurf=1, pin='BORDER', collide=True,
                self_collision=False, thickness=0.005, split='NONE', angle=30.0, join=True, hide_source=True,
                bend=0.5, shrink_max=None, random_islands=False, variation=0.0, collider='REGION',
                preset='', remove_faces=False):
    """Make + simulate + bake the cloth objects.  Returns the new objects."""
    if not collide:
        collider = 'NONE'
    groups = {}
    if edit_object is not None:
        groups[edit_object.name] = [(edit_object, _world_faces_from_selection(edit_object), edit_object)]
        if remove_faces:
            bm = bmesh.from_edit_mesh(edit_object.data)
            bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.select], context='FACES_ONLY')
            bmesh.update_edit_mesh(edit_object.data)
        bpy.ops.object.mode_set(mode='OBJECT')
    else:
        for ob in sources:
            body = collider_for(ob)
            key = body.name if (join and body is not None) else ob.name
            groups.setdefault(key, []).append((ob, _world_faces_from_object(ob), body))
    made, temp_cols, temp_objs = [], [], []
    rmax = shrink_max if (random_islands and shrink_max is not None) else None
    for items in groups.values():
        parts = [it[1] for it in items if it[1][1]]
        if not parts:
            continue
        first, body = items[0][0], items[0][2]
        me, border, corners, weights = build_cloth_mesh(parts, cuts, split, angle, noise, seed, True,
                                                        random_islands, variation)
        # the cloth starts just above the surface it collides with (coincident = unstable contact);
        # the contact distance follows the panel size
        size = max((max(v.co[k] for v in me.vertices) - min(v.co[k] for v in me.vertices)) for k in range(3))
        thick = max(thickness, size * 0.003)
        me.update()
        for v in me.vertices:
            v.co += v.normal * (thick * 2.0)
        ob = bpy.data.objects.new(first.name + SUFFIX, me)
        coll = first.users_collection[0] if first.users_collection else context.scene.collection
        coll.objects.link(ob)
        for mat in first.data.materials:
            me.materials.append(mat)
        pins = border if pin == 'BORDER' else corners if pin == 'CORNERS' else []
        if pins:
            ob.vertex_groups.new(name=PIN_GROUP).add(pins, 1.0, 'REPLACE')
        setup_cloth(context.scene, ob, frames, quality, mass, pressure, shrink, gravity, thick,
                    self_collision, PIN_GROUP if pins else None, bend, rmax, weights if random_islands else None)
        if collider == 'REGION':
            temp_objs.append(_region_collider(context, parts, ob.name + '_Collider'))
        elif collider == 'BODY' and body is not None and body.type == 'MESH' and body is not ob and \
                not any(m.type == 'COLLISION' for m in body.modifiers):
            body.modifiers.new('MCH_TempCollision', 'COLLISION')
            temp_cols.append(body)
        ob['mch_pcloth'] = ','.join(it[0].name for it in items)
        ob['mch_pcloth_preset'] = preset
        made.append((ob, items))
    try:
        bake(context, [m[0] for m in made], frames)
    finally:
        for body in temp_cols:
            m = body.modifiers.get('MCH_TempCollision')
            if m is not None:
                body.modifiers.remove(m)
        for t in temp_objs:
            me = t.data
            bpy.data.objects.remove(t)
            if me.users == 0:
                bpy.data.meshes.remove(me)
    out = []
    for ob, items in made:
        for p in ob.data.polygons:
            p.use_smooth = True
        for vg_name in (SHRINK_GROUP, PRESSURE_GROUP):
            vg = ob.vertex_groups.get(vg_name)
            if vg is not None:
                ob.vertex_groups.remove(vg)
        if subsurf > 0:
            ob.modifiers.new('MCH_Subsurf', 'SUBSURF').levels = subsurf
        if hide_source and items[0][0] is not edit_object:
            for src, _f, _b in items:
                src.hide_set(True)
                src.hide_render = True
        out.append(ob)
    return out


def run_preset(context, sources, preset, **over):
    """Panel Cloth with a preset's values (+ overrides)."""
    v = preset_values(preset)
    v.update(over)
    return panel_cloth(context, sources, frames=v['frames'], quality=v['quality'], mass=v['mass'],
                       pressure=v['pressure'], shrink=v['shrink'], gravity=v['gravity'], cuts=v['cuts'],
                       noise=v['noise'], bend=v['bend'], random_islands=v['random'], variation=v['variation'],
                       shrink_max=v['shrink'] * 2.2 if v['random'] else None, preset=preset,
                       **{k: over[k] for k in over if k in ('collider', 'split', 'angle', 'seed', 'pin', 'join',
                                                              'subsurf', 'thickness')})


def is_pcloth(ob):
    return ob is not None and bool(ob.get('mch_pcloth'))


def redo(context, ob, preset):
    """Bake a cloth again from its (hidden) source with another preset."""
    names = [n for n in str(ob.get('mch_pcloth', '')).split(',') if n in bpy.data.objects]
    if not names:
        return []
    srcs = [bpy.data.objects[n] for n in names]
    me = ob.data
    bpy.data.objects.remove(ob)
    if me.users == 0:
        bpy.data.meshes.remove(me)
    for s in srcs:
        s.hide_set(False)
        s.hide_render = False
    return run_preset(context, srcs, preset)


def _apply_preset(self, _context):
    v = preset_values(self.preset)
    for k in ('pressure', 'shrink', 'gravity', 'mass', 'bend', 'cuts', 'frames', 'quality', 'noise', 'variation'):
        setattr(self, k, v[k])
    self.random_islands = v['random']
    self.shrink_max = v['shrink'] * 2.2


class MCH_OT_panel_cloth(bpy.types.Operator):
    """Panel Cloth: a short cloth simulation on the selected panels (or the selected faces) - puffed up by
    Pressure, folded by Shrink, pinned at the border, on the generated surface as a collider - then baked"""
    bl_idname = 'mch.panel_cloth'
    bl_label = 'Panel Cloth'
    bl_options = {'REGISTER', 'UNDO'}
    preset: EnumProperty(name='Preset', items=PRESET_ITEMS, default='PADDING', update=_apply_preset)
    split: EnumProperty(name='Split', items=SPLIT_MODES, default='NONE')
    angle: FloatProperty(name='Angle', default=math.radians(30.0), min=0.0, max=math.pi, subtype='ANGLE')
    frames: IntProperty(name='Bake Frames', default=30, min=1, max=500)
    quality: IntProperty(name='Quality', default=5, min=1, max=40)
    seed: IntProperty(name='Cloth Seed', default=1, min=0)
    mass: FloatProperty(name='Mass', default=0.15, min=0.001, max=10.0)
    pressure: FloatProperty(name='Pressure', default=9.0, min=-50.0, max=80.0,
                            description='Puffs the panel up (padding); 0 = plain cloth')
    shrink: FloatProperty(name='Shrink', default=-0.05, min=-1.0, max=1.0,
                          description='Negative: the cloth is bigger than its frame - it folds')
    random_islands: BoolProperty(name='Random per piece', default=False,
                                 description='Every split piece its own shrink (Shrink .. Shrink Max) and pressure')
    shrink_max: FloatProperty(name='Shrink Max', default=-0.11, min=-1.0, max=1.0)
    variation: FloatProperty(name='Pressure Variation', default=0.0, min=0.0, max=1.0, subtype='FACTOR')
    gravity: FloatProperty(name='Gravity', default=0.3, min=0.0, max=10.0)
    bend: FloatProperty(name='Bend', default=0.5, min=0.0, max=100.0,
                        description='Bending stiffness: low = many small folds, high = few big ones')
    cuts: IntProperty(name='Subdivision', default=3, min=0, max=10, description='Cuts per edge before the sim')
    noise: FloatProperty(name='Noise', default=0.0, min=0.0, max=1.0, description='Random start offset')
    subsurf: IntProperty(name='Subsurf Level', default=1, min=0, max=3)
    pin: EnumProperty(name='Pin', items=PIN_MODES, default='BORDER')
    collider: EnumProperty(name='Collide', items=COLLIDERS, default='REGION')
    self_collision: BoolProperty(name='Self Collision', default=False)
    thickness: FloatProperty(name='Thickness', default=0.005, min=0.0, max=1.0, unit='LENGTH')
    join: BoolProperty(name='Join Panels', default=True,
                       description='Panels on the same body (e.g. Through front + back) become one cloth')
    remove_faces: BoolProperty(name='Remove Faces', default=False,
                               description='Edit Mode: delete the selected faces from the source mesh')
    hide_source: BoolProperty(name='Hide Source', default=True)

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        if ob is not None and ob.mode == 'EDIT':
            return ob.type == 'MESH'
        return any(o.type == 'MESH' for o in context.selected_objects)

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self, width=340)

    def draw(self, context):
        lay = self.layout
        lay.use_property_split = True
        lay.prop(self, 'preset')
        col = lay.column(align=True)
        col.row().prop(self, 'split', expand=True)
        if self.split == 'ANGLE':
            col.prop(self, 'angle')
        for k in ('frames', 'quality', 'seed'):
            col.prop(self, k)
        col = lay.column(align=True)
        for k in ('mass', 'pressure', 'shrink', 'random_islands'):
            col.prop(self, k)
        if self.random_islands:
            col.prop(self, 'shrink_max')
            col.prop(self, 'variation')
        for k in ('gravity', 'bend'):
            col.prop(self, k)
        col = lay.column(align=True)
        for k in ('cuts', 'noise', 'subsurf'):
            col.prop(self, k)
        col = lay.column(align=True)
        col.row().prop(self, 'pin', expand=True)
        col.row().prop(self, 'collider', expand=True)
        for k in ('self_collision', 'thickness', 'join', 'remove_faces', 'hide_source'):
            col.prop(self, k)

    def execute(self, context):
        ob = context.active_object
        edit = ob if (ob is not None and ob.mode == 'EDIT') else None
        if edit is not None and not any(f.select for f in bmesh.from_edit_mesh(edit.data).faces):
            self.report({'WARNING'}, 'Select faces first')
            return {'CANCELLED'}
        srcs = [o for o in context.selected_objects if o.type == 'MESH' and not is_pcloth(o)]
        try:
            made = panel_cloth(context, srcs, edit, self.frames, self.quality, self.seed, self.mass, self.pressure,
                               self.shrink, self.gravity, self.cuts, self.noise, self.subsurf, self.pin,
                               self.collider != 'NONE', self.self_collision, self.thickness, self.split,
                               math.degrees(self.angle), self.join, self.hide_source, self.bend,
                               self.shrink_max, self.random_islands, self.variation, self.collider,
                               self.preset, self.remove_faces)
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


class MCH_OT_panel_cloth_redo(bpy.types.Operator):
    """Bake this cloth again from its source with another preset"""
    bl_idname = 'mch.panel_cloth_redo'
    bl_label = 'Panel Cloth Preset'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    preset: EnumProperty(name='Preset', items=PRESET_ITEMS, default='PADDING')

    @classmethod
    def poll(cls, context):
        return is_pcloth(context.active_object)

    def execute(self, context):
        made = redo(context, context.active_object, self.preset)
        if not made:
            self.report({'WARNING'}, 'The source of this cloth is gone')
            return {'CANCELLED'}
        for o in made:
            o.select_set(True)
        context.view_layer.objects.active = made[0]
        self.report({'INFO'}, 'Panel Cloth: ' + dict((p[0], p[1]) for p in PRESETS)[self.preset])
        return {'FINISHED'}


def draw(layout, context):
    """Panel Cloth box (Cloth Plate panel)."""
    box = layout.box()
    box.label(text='PANEL CLOTH (simulate + bake)', icon='MOD_CLOTH')
    st = context.scene.mch_wrinkle
    r = box.row(align=True)
    r.prop(st, 'sim_after', text='Sim after lasso', toggle=True)
    r.prop(st, 'sim_preset', text='')
    box.operator('mch.panel_cloth', text='Panel Cloth on selection', icon='MOD_CLOTH')
    ob = context.active_object
    if is_pcloth(ob):
        box.label(text=f'{ob.name}: redo with', icon='FILE_REFRESH')
        grid = box.grid_flow(columns=3, align=True)
        cur = ob.get('mch_pcloth_preset', '')
        for pid, label, _d in PRESET_ITEMS:
            grid.operator('mch.panel_cloth_redo', text=label, depress=(pid == cur)).preset = pid


CLASSES = (MCH_OT_panel_cloth, MCH_OT_panel_cloth_redo)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
