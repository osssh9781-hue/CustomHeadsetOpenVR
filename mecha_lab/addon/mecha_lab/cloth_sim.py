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
# 0.24.88 the padded family runs 3 - 4 solver steps per frame (measured: the same puff as 5 - 6, 40 % faster)
PRESETS = (
    ('PADDING', 'Padding', 'Firm padded panel, folds along the border',
     dict(pressure=9.0, shrink=-0.05, gravity=0.3, mass=0.15, bend=0.5, cuts=3, frames=30, quality=3)),
    ('PUFFER', 'Puffer', 'Down jacket: strongly puffed, soft border folds',
     dict(pressure=16.0, shrink=-0.08, gravity=0.2, mass=0.1, bend=0.3, cuts=3, frames=35, quality=4)),
    ('PILLOW', 'Pillow', 'Soft cushion: puffed with many loose folds',
     dict(pressure=7.0, shrink=-0.16, gravity=0.5, mass=0.15, bend=0.2, cuts=3, frames=35, quality=4)),
    ('QUILT', 'Quilt', 'Every split piece puffs on its own (use Split Angle / Seam)',
     dict(pressure=10.0, shrink=-0.06, gravity=0.3, mass=0.15, bend=0.4, cuts=3, frames=30, quality=3,
          random=True, variation=0.4)),
    ('CLOTH', 'Cloth', 'Loose fabric: no puff, hangs and folds',
     dict(pressure=0.0, shrink=-0.15, gravity=1.0, mass=0.3, bend=0.5, cuts=3, frames=40, quality=6)),
    ('SILK', 'Silk', 'Thin light fabric: many small folds',
     dict(pressure=0.0, shrink=-0.22, gravity=1.0, mass=0.05, bend=0.02, cuts=4, frames=45, quality=8)),
    ('CANVAS', 'Canvas', 'Heavy fabric: few big soft folds',
     dict(pressure=0.5, shrink=-0.1, gravity=1.5, mass=0.6, bend=5.0, cuts=3, frames=40, quality=6)),
    ('LEATHER', 'Leather', 'Stiff: a slight puff and a few thick folds',
     dict(pressure=1.5, shrink=-0.06, gravity=0.8, mass=0.5, bend=20.0, cuts=3, frames=35, quality=4)),
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
                thickness=0.005, self_collision=True, pin_group=None, bend=0.5, shrink_max=None,
                weights=None, tension=1.0):
    """0.24.88 Self collision on by default (collision quality 2, self distance = the contact thickness): the
    fabric presets came out with hundreds of faces passing through each other (CLOTH 485, SILK 641 crossing
    pairs) and sliver faces; with it 0 crossings at the same bake time (measured on a 9k-point panel)."""
    cm = ob.modifiers.new('MCH_PanelCloth', 'CLOTH')
    s = cm.settings
    if abs(tension - 1.0) > 1e-9:                     # Tension 1 = untouched: the result stays the preset's
        s.tension_stiffness = s.tension_stiffness * tension
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
    c.collision_quality = 2 if self_collision else 3
    c.use_self_collision = self_collision
    if self_collision:
        c.self_distance_min = thickness
    cm.point_cache.frame_start = scene.frame_start
    cm.point_cache.frame_end = scene.frame_start + frames
    return cm


def bake(context, objs, frames, colliders=()):
    """Play the frames (the cloth caches fill) and keep the last frame as each object's mesh.

    0.24.88 The frames run in a **temporary scene** holding only the cloth and its colliders: stepping the user's
    scene re-evaluated everything time-dependent or freshly tagged in it (a Mirror on a 1.3M-face part: +3 s per
    bake, measured) and left its frame counter and caches touched.  The scene's fps and gravity are copied so the
    cloth's time step and weight are the same."""
    scene = context.scene
    keep = scene.frame_current
    start = scene.frame_start
    tmp = bpy.data.scenes.new('MCH_ClothBake')
    try:
        tmp.frame_start, tmp.frame_end = start, start + frames
        tmp.render.fps, tmp.render.fps_base = scene.render.fps, scene.render.fps_base
        tmp.use_gravity, tmp.gravity = scene.use_gravity, scene.gravity
        for o in list(objs) + [c for c in colliders if c is not None]:
            try:
                tmp.collection.objects.link(o)
            except RuntimeError:
                pass
        for f in range(start, start + frames + 1):
            tmp.frame_set(f)
        dg = tmp.view_layers[0].depsgraph
        if dg is None:
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
    finally:
        for o in list(tmp.collection.objects):
            try:
                tmp.collection.objects.unlink(o)
            except RuntimeError:
                pass
        bpy.data.scenes.remove(tmp)
    if scene.frame_current != keep:
        scene.frame_set(keep)


def cloth_params(cm):
    """0.24.88 The cloth modifier's settings as a plain dict (for the background worker)."""
    s, c = cm.settings, cm.collision_settings
    return dict(quality=int(s.quality), mass=float(s.mass), bend=float(s.bending_stiffness),
                tension=float(s.tension_stiffness), compression=float(s.compression_stiffness),
                shear=float(s.shear_stiffness), use_pressure=bool(s.use_pressure),
                pressure=float(s.uniform_pressure_force), shrink_min=float(s.shrink_min),
                shrink_max=float(s.shrink_max), vg_mass=s.vertex_group_mass, vg_shrink=s.vertex_group_shrink,
                vg_pressure=s.vertex_group_pressure, gravity=float(s.effector_weights.gravity),
                air=float(s.air_damping), distance_min=float(c.distance_min),
                collision_quality=int(c.collision_quality), self_collision=bool(c.use_self_collision),
                self_distance=float(c.self_distance_min), frame_start=int(cm.point_cache.frame_start),
                frame_end=int(cm.point_cache.frame_end))


def apply_cloth_params(cm, p):
    """0.24.88 ``cloth_params`` back onto a cloth modifier."""
    s, c = cm.settings, cm.collision_settings
    s.quality = p['quality']; s.mass = p['mass']; s.bending_stiffness = p['bend']
    s.tension_stiffness = p['tension']; s.compression_stiffness = p['compression']; s.shear_stiffness = p['shear']
    s.use_pressure = p['use_pressure']; s.uniform_pressure_force = p['pressure']
    s.shrink_min = p['shrink_min']; s.shrink_max = p['shrink_max']
    s.vertex_group_mass = p['vg_mass'] or ''; s.vertex_group_shrink = p['vg_shrink'] or ''
    s.vertex_group_pressure = p['vg_pressure'] or ''
    s.effector_weights.gravity = p['gravity']; s.air_damping = p['air']
    c.use_collision = True; c.distance_min = p['distance_min']; c.collision_quality = p['collision_quality']
    c.use_self_collision = p['self_collision']; c.self_distance_min = p['self_distance']
    cm.point_cache.frame_start = p['frame_start']; cm.point_cache.frame_end = p['frame_end']


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
                self_collision=True, thickness=0.005, split='NONE', angle=30.0, join=True, hide_source=True,
                bend=0.5, shrink_max=None, random_islands=False, variation=0.0, collider='REGION',
                preset='', remove_faces=False, tension=1.0, background=False):
    """Make + simulate + bake the cloth objects.  Returns the new objects.

    0.24.88 ``background``: the frames run in a second Blender (bg_jobs); the cloth object appears at once with
    its flat start and gets the baked mesh when the worker is done (status row + Cancel in the Panel Cloth box)."""
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
        if getattr(context.scene, 'mch_pcloth_fast', True):
            # 0.24.2 Fast Start: all normals read once (reading v.normal after moving verts recomputes every
            # normal each time - seconds on a fine panel).  The start differs a hair, so folds land a bit
            # elsewhere; off = exactly the old result.
            n = len(me.vertices)
            co = [0.0] * (3 * n)
            nr = [0.0] * (3 * n)
            me.vertices.foreach_get('co', co)
            me.vertices.foreach_get('normal', nr)
            lift = thick * 2.0
            me.vertices.foreach_set('co', [c + d * lift for c, d in zip(co, nr)])
            me.update()
        else:
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
                    self_collision, PIN_GROUP if pins else None, bend, rmax, weights if random_islands else None,
                    tension)
        if collider == 'REGION':
            temp_objs.append(_region_collider(context, parts, ob.name + '_Collider'))
        elif collider == 'BODY' and body is not None and body.type == 'MESH' and body is not ob and \
                not any(m.type == 'COLLISION' for m in body.modifiers):
            body.modifiers.new('MCH_TempCollision', 'COLLISION')
            temp_cols.append(body)
        ob['mch_pcloth'] = ','.join(it[0].name for it in items)
        ob['mch_pcloth_preset'] = preset
        set_sliders(ob, tension, gravity)
        made.append((ob, items))
    if background and made and _background_ok():
        from . import bg_jobs
        started = []
        for ob, items in made:
            cm = next((m for m in ob.modifiers if m.type == 'CLOTH'), None)
            body = items[0][2]
            cols = [t.data for t in temp_objs if t.name == ob.name + '_Collider']
            if collider == 'BODY' and body is not None and body.type == 'MESH':
                cols = [body.data]
            msg = bg_jobs.start(context, ob, 'PANEL_CLOTH', dict(cloth=cloth_params(cm), colliders=[m.name for m in cols],
                                                                  fps=float(context.scene.render.fps / context.scene.render.fps_base),
                                                                  gravity=list(context.scene.gravity) if context.scene.use_gravity else [0.0, 0.0, 0.0]),
                                extra=cols)
            if cm is not None:
                ob.modifiers.remove(cm)
            ob['mch_pcloth_pending'] = 1
            started.append(msg)
        for body in temp_cols:
            m = body.modifiers.get('MCH_TempCollision')
            if m is not None:
                body.modifiers.remove(m)
        for t in temp_objs:
            me = t.data
            bpy.data.objects.remove(t)
            if me.users == 0:
                bpy.data.meshes.remove(me)
        LAST_BACKGROUND[:] = started
        return _after_bake(made, subsurf, hide_source, edit_object)
    try:
        bake(context, [m[0] for m in made], frames, colliders=temp_objs + temp_cols)
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
    finish_cloth([m[0] for m in made])
    return _after_bake(made, subsurf, hide_source, edit_object)


LAST_BACKGROUND = []            # the start messages of the last background bake (the operator reports them)


def _background_ok():
    from . import bg_jobs
    return bg_jobs.can_run()


def finish_cloth(obs):
    """0.24.88 After the frames: smooth faces, the sim-only vertex groups gone (also run on a background result)."""
    for ob in obs:
        if ob.data is not None:
            ob.data.polygons.foreach_set('use_smooth', [True] * len(ob.data.polygons))
        for vg_name in (SHRINK_GROUP, PRESSURE_GROUP):
            vg = ob.vertex_groups.get(vg_name)
            if vg is not None:
                ob.vertex_groups.remove(vg)
        if 'mch_pcloth_pending' in ob:
            del ob['mch_pcloth_pending']


def _after_bake(made, subsurf, hide_source, edit_object):
    out = []
    for ob, items in made:
        if subsurf > 0 and ob.modifiers.get('MCH_Subsurf') is None:
            ob.modifiers.new('MCH_Subsurf', 'SUBSURF').levels = subsurf
        if hide_source and items[0][0] is not edit_object:
            for src, _f, _b in items:
                src.hide_set(True)
                src.hide_render = True
        out.append(ob)
    return out


def use_background(context):
    """0.24.88 The Background toggle (ZBrush shelf / Mesh Tools, default on) decides for Panel Cloth too."""
    zb = getattr(context.scene, 'mch_zb', None)
    return bool(getattr(zb, 'bg_jobs', False)) and _background_ok()


def run_preset(context, sources, preset, **over):
    """Panel Cloth with a preset's values (+ overrides)."""
    v = preset_values(preset)
    v.update(over)
    return panel_cloth(context, sources, frames=v['frames'], quality=v['quality'], mass=v['mass'],
                       pressure=v['pressure'], shrink=v['shrink'], gravity=v['gravity'], cuts=v['cuts'],
                       noise=v['noise'], bend=v['bend'], random_islands=v['random'], variation=v['variation'],
                       shrink_max=v['shrink'] * 2.2 if v['random'] else None, preset=preset,
                       **{k: over[k] for k in over if k in ('collider', 'split', 'angle', 'seed', 'pin', 'join',
                                                              'subsurf', 'thickness', 'tension', 'background',
                                                              'self_collision')})


def is_pcloth(ob):
    return ob is not None and bool(ob.get('mch_pcloth'))


DIRTY_KEY = 'mch_pcloth_dirty'
TENSION_KEY = 'mch_pcloth_tension'
PUFF_KEY = 'mch_pcloth_puff'
GRAVITY_KEY = 'mch_pcloth_gravity'


def puff_pressure(base, puff):
    """0.24.16 Puff slider: 1 = the preset; 0 = flat, 2 = twice the puff.  Presets with (almost) no puff
    (Cloth / Silk / Canvas) get some added instead of a multiple of nothing."""
    puff = max(0.0, float(puff))
    if base >= 1.0:
        return base * puff
    return max(0.0, base + (puff - 1.0) * 3.0) if puff >= 1.0 else base * puff


def sim_values(preset, tension=1.0, gravity=None, puff=1.0):
    """0.23.28 preset values with the live Tension / Gravity sliders:
    Tension 1 = preset; higher = tighter (less slack, stiffer), lower = looser.  0.24.16 Puff = the pressure."""
    v = preset_values(preset)
    t = max(0.05, float(tension))
    over = dict(shrink=v['shrink'] * min(1.0 / t, 2.5), tension=t)     # looser at most 2.5 x the preset slack
    if gravity is not None:
        over['gravity'] = float(gravity)
    if abs(float(puff) - 1.0) > 1e-9:            # Puff 1 = untouched: the result stays the preset's
        over['pressure'] = puff_pressure(v['pressure'], puff)
    return over


def redo(context, ob, preset, tension=None, gravity=None, puff=None):
    """Bake a cloth again from its (hidden) source with another preset
    (and the object's Tension / Gravity, kept on the new cloth)."""
    names = [n for n in str(ob.get('mch_pcloth', '')).split(',') if n in bpy.data.objects]
    if not names:
        return []
    if tension is None:
        tension = ob.mch_pcloth_tension
    if gravity is None:
        gravity = ob.mch_pcloth_gravity if ob.get(GRAVITY_KEY) is not None else None
    if puff is None:
        puff = ob.mch_pcloth_puff
    from . import bg_jobs
    if bg_jobs.busy(ob):
        return []
    srcs = [bpy.data.objects[n] for n in names]
    background = use_background(context)
    me = ob.data
    bpy.data.objects.remove(ob)
    if me.users == 0:
        bpy.data.meshes.remove(me)
    for s in srcs:
        s.hide_set(False)
        s.hide_render = False
    made = run_preset(context, srcs, preset, background=background, **sim_values(preset, tension, gravity, puff))
    for o in made:
        set_sliders(o, tension, gravity if gravity is not None else preset_values(preset)['gravity'], puff)
    return made


_SYNC = [False]
_PENDING = {}


def set_sliders(ob, tension, gravity, puff=1.0):
    """Show the values on a (new) cloth without baking again."""
    _SYNC[0] = True
    try:
        ob.mch_pcloth_puff = puff
        ob.mch_pcloth_tension = tension
        ob.mch_pcloth_gravity = gravity
        ob[GRAVITY_KEY] = float(gravity)
    finally:
        _SYNC[0] = False


def _rebake_timer():
    names = list(_PENDING)
    _PENDING.clear()
    for name in names:
        ob = bpy.data.objects.get(name)
        if ob is None or not is_pcloth(ob):
            continue
        try:
            made = redo(bpy.context, ob, ob.get('mch_pcloth_preset', '') or 'PADDING')
        except (RuntimeError, ReferenceError, ValueError):
            continue
        if made:
            for o in bpy.context.view_layer.objects:
                o.select_set(False)
            for o in made:
                o.select_set(True)
            bpy.context.view_layer.objects.active = made[0]
    return None


@bpy.app.handlers.persistent
def _on_undo_pre(*_args):
    _PENDING.clear()
    if bpy.app.timers.is_registered(_rebake_timer):
        bpy.app.timers.unregister(_rebake_timer)


def _slider_update(self, _context):
    """0.24.4 changing Tension / Gravity only marks the cloth: Refresh bakes it
    again with the new values (no automatic re-bake)."""
    if _SYNC[0] or not is_pcloth(self):
        return
    self[GRAVITY_KEY] = float(self.mch_pcloth_gravity)
    self[DIRTY_KEY] = True


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
    self_collision: BoolProperty(name='Self Collision', default=True,
                                 description='The cloth cannot pass through itself (0.24.88 on: no crossing folds, same bake time)')
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
                               self.preset, self.remove_faces, background=use_background(context))
        except ValueError as exc:
            self.report({'WARNING'}, str(exc))
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in made:
            o.select_set(True)
        if made:
            context.view_layer.objects.active = made[0]
        if LAST_BACKGROUND:
            self.report({'INFO'}, '; '.join(LAST_BACKGROUND))
            LAST_BACKGROUND.clear()
        else:
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
        made = redo(context, context.active_object, self.preset, gravity=preset_values(self.preset)['gravity'])
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
    r = box.row(align=True)
    if hasattr(context.scene, 'mch_pcloth_fast'):
        r.prop(context.scene, 'mch_pcloth_fast')
    zb = getattr(context.scene, 'mch_zb', None)
    if zb is not None and hasattr(zb, 'bg_jobs'):
        r.prop(zb, 'bg_jobs', text='Background', toggle=True)           # 0.24.88 the bake in a second Blender
    box.operator('mch.panel_cloth', text='Panel Cloth on selection', icon='MOD_CLOTH')
    ob = context.active_object
    from . import bg_jobs
    bg_jobs.draw_status(box, ob)
    if is_pcloth(ob):
        col = box.column(align=True)
        col.prop(ob, 'mch_pcloth_puff', slider=True)
        col.prop(ob, 'mch_pcloth_tension', slider=True)
        col.prop(ob, 'mch_pcloth_gravity', slider=True)
        row = box.row()
        row.scale_y = 1.3
        row.alert = bool(ob.get(DIRTY_KEY))
        row.operator('mch.panel_cloth_refresh', icon='FILE_REFRESH',
                     text='Refresh (apply changes)' if ob.get(DIRTY_KEY) else 'Refresh')
        box.label(text=f'{ob.name}: redo with', icon='FILE_REFRESH')
        grid = box.grid_flow(columns=3, align=True)
        cur = ob.get('mch_pcloth_preset', '')
        for pid, label, _d in PRESET_ITEMS:
            grid.operator('mch.panel_cloth_redo', text=label, depress=(pid == cur)).preset = pid


class MCH_OT_panel_cloth_refresh(bpy.types.Operator):
    """Bake this cloth again with its current Tension / Gravity (and preset)"""
    bl_idname = 'mch.panel_cloth_refresh'
    bl_label = 'Refresh Cloth'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return is_pcloth(context.active_object)

    def execute(self, context):
        ob = context.active_object
        made = redo(context, ob, ob.get('mch_pcloth_preset', '') or 'PADDING')
        if not made:
            self.report({'WARNING'}, 'The source of this cloth is gone')
            return {'CANCELLED'}
        for o in context.selected_objects:
            o.select_set(False)
        for o in made:
            o.select_set(True)
        context.view_layer.objects.active = made[0]
        self.report({'INFO'}, f'Panel Cloth refreshed (Puff {made[0].mch_pcloth_puff:.2f}, '
                              f'Tension {made[0].mch_pcloth_tension:.2f}, '
                              f'Gravity {made[0].mch_pcloth_gravity:.2f})')
        return {'FINISHED'}


CLASSES = (MCH_OT_panel_cloth, MCH_OT_panel_cloth_redo, MCH_OT_panel_cloth_refresh)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    for lst in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        if _on_undo_pre not in lst:
            lst.append(_on_undo_pre)
    bpy.types.Scene.mch_pcloth_fast = BoolProperty(
        name='Fast Start', default=True,                                  # 0.24.88 on: 2.9 s less per bake (measured)
        description='Prepare the cloth much faster (big panels: seconds less). The folds come out a little '
                    'different from the 0.24.1 result; off = that result')
    bpy.types.Object.mch_pcloth_puff = FloatProperty(
        name='Puff', default=1.0, min=0.0, max=5.0, soft_max=3.0, update=_slider_update,
        description='Panel Cloth: how much it puffs up - 1 = preset, 0 = flat, 2 = twice as much (Refresh bakes it)')
    bpy.types.Object.mch_pcloth_tension = FloatProperty(
        name='Tension', default=1.0, min=0.2, max=4.0, soft_max=3.0, update=_slider_update,
        description='Panel Cloth: 1 = preset; higher = tighter cloth (less slack, stiffer), lower = looser, more folds')
    bpy.types.Object.mch_pcloth_gravity = FloatProperty(
        name='Gravity', default=0.3, min=0.0, max=10.0, soft_max=5.0, update=_slider_update,
        description='Panel Cloth: how much the cloth sags toward world down')


def unregister():
    if bpy.app.timers.is_registered(_rebake_timer):
        bpy.app.timers.unregister(_rebake_timer)
    _PENDING.clear()
    for lst in (bpy.app.handlers.undo_pre, bpy.app.handlers.redo_pre):
        while _on_undo_pre in lst:
            lst.remove(_on_undo_pre)
    for attr in ('mch_pcloth_puff', 'mch_pcloth_tension', 'mch_pcloth_gravity'):
        if hasattr(bpy.types.Object, attr):
            delattr(bpy.types.Object, attr)
    if hasattr(bpy.types.Scene, 'mch_pcloth_fast'):
        del bpy.types.Scene.mch_pcloth_fast
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
