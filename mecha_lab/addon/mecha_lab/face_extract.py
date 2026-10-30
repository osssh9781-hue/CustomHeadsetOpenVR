"""Face Extract (Basic) and Armor Sculpt.

Edit Mode: select faces (on one or several objects), run Extract.  Every
connected selection region becomes its OWN part object (in the "Mechanical
Parts / Extracted Armor" collection).  The source mesh is never changed.

The part stores a copy of the selected region and its surroundings (two
small mesh datablocks) plus all settings (``Object.mch_extract``), so every
slider rebuilds it live, also later after re-selecting the part.  The panel
shows the active part, or the last extracted part while you stay in Edit
Mode on the source.
"""
from __future__ import annotations

import math

import bmesh
import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, PointerProperty, StringProperty

from . import panel_gen as pg

COLL_ROOT = 'Mechanical Parts'
COLL_PARTS = 'Extracted Armor'
MOD_SHELL = 'MCH_Extract_Shell'
MOD_SIDE = 'MCH_Extract_SideBevel'


def _rebuild_now(name):
    ob = bpy.data.objects.get(name)
    st = getattr(ob, 'mch_extract', None) if ob is not None else None
    if st is not None and st.is_part and st.region is not None:
        rebuild(ob)


def _rebuild_update(self, context):
    ob = self.id_data
    if isinstance(ob, bpy.types.Object) and self.is_part and self.region is not None:
        from . import live_queue                 # 0.24.73 at a steady pace while a slider is dragged (R10)
        name = ob.name
        live_queue.queue(('face_extract', name), lambda: _rebuild_now(name))


def _p(prop, **kw):
    kw.setdefault('update', _rebuild_update)
    return prop(**kw)


_ANN = {
    'is_part': BoolProperty(default=False, options={'HIDDEN'}),
    'mode': EnumProperty(name='Extract Mode', items=[
        ('BASIC', 'Basic Extract', 'Uniform height and edge profile'),
        ('ARMOR', 'Armor Sculpt', 'Per-direction thickness / edges and a centre ridge')],
        default='BASIC', update=_rebuild_update),
    'source': PointerProperty(type=bpy.types.Object, name='Source'),
    'region': PointerProperty(type=bpy.types.Mesh),
    'surround': PointerProperty(type=bpy.types.Mesh),
    'notes': StringProperty(default='', options={'HIDDEN', 'SKIP_SAVE'}),
    # ---- 1. basic extract ------------------------------------------------------
    'extract_height': _p(FloatProperty, name='Extract Height', default=0.1, min=0.0001, soft_max=5.0, precision=4,
                         unit='LENGTH', description='Distance from the part bottom to its top (Armor: centre height)'),
    'thickness': _p(FloatProperty, name='Thickness', default=0.0, min=0.0, soft_max=1.0, precision=4, unit='LENGTH',
                    description='0 = solid part. > 0 = the part is a shell with this wall thickness (open below)'),
    'surface_offset': _p(FloatProperty, name='Surface Offset', default=0.0, soft_min=-1.0, soft_max=1.0, precision=4,
                         unit='LENGTH', description='Gap between the original surface and the part bottom'),
    'resolution': _p(IntProperty, name='Resolution', default=1, min=0, max=4,
                     description='Subdivision of the selected faces (smoother height fields and ridges, heavier)'),
    # ---- 2. bevel ---------------------------------------------------------------------
    'bevel_width': _p(FloatProperty, name='Bevel Width', default=0.0, min=0.0, soft_max=0.5, precision=4,
                      unit='LENGTH', description='Rounds the top edge (and the chamfer lines) and the side edges'),
    'bevel_segments': _p(IntProperty, name='Bevel Segments', default=3, min=1, max=16),
    'bevel_profile': _p(FloatProperty, name='Bevel Profile', default=0.5, min=0.0, max=1.0, subtype='FACTOR',
                        description='0 = straight, 0.5 = round, 1 = boxy'),
    'bevel_angle': _p(FloatProperty, name='Bevel Angle', default=math.radians(30.0), min=0.0, max=math.pi,
                      subtype='ANGLE', description='Side edges: only corners of the outline sharper than this '
                                                   'are rounded (vertical wall edges)'),
    # ---- 3. chamfer ----------------------------------------------------------------------
    'chamfer_width': _p(FloatProperty, name='Chamfer Width', default=0.0, min=0.0, soft_max=0.5, precision=4,
                        unit='LENGTH', description='Horizontal size of the top edge chamfer'),
    'chamfer_angle': _p(FloatProperty, name='Chamfer Angle', default=math.radians(45.0), min=0.0,
                        max=math.radians(89.0), subtype='ANGLE', description='Slope of the chamfer face'),
    'chamfer_depth': _p(FloatProperty, name='Chamfer Depth', default=0.02, min=0.0, soft_max=0.5, precision=4,
                        unit='LENGTH', description='Vertical size of the chamfer (used by the Width + Depth / '
                                                   'Depth + Angle modes)'),
    'chamfer_mode': _p(EnumProperty, name='Chamfer Control', items=[
        ('WIDTH_ANGLE', 'Width + Angle', 'Depth follows'), ('WIDTH_DEPTH', 'Width + Depth', 'Angle follows'),
        ('DEPTH_ANGLE', 'Depth + Angle', 'Width follows')], default='WIDTH_ANGLE'),
    'chamfer_direction': _p(EnumProperty, name='Chamfer Direction', items=[
        ('IN', 'Inward', 'Cut into the part (footprint = selection)'),
        ('OUT', 'Outward', 'Flare outward beyond the selection (top = selection)')], default='IN'),
    # ---- 4. outer (base) edge ----------------------------------------------------------------
    'outer_bevel_width': _p(FloatProperty, name='Outer Edge Bevel Width', default=0.0, min=0.0, soft_max=0.5,
                            precision=4, unit='LENGTH', description='Rounds the base edge where the part meets the surface'),
    'outer_chamfer_width': _p(FloatProperty, name='Outer Edge Chamfer Width', default=0.0, min=0.0, soft_max=0.5,
                              precision=4, unit='LENGTH'),
    'outer_chamfer_angle': _p(FloatProperty, name='Outer Edge Chamfer Angle', default=math.radians(45.0), min=0.0,
                              max=math.radians(89.0), subtype='ANGLE'),
    # ---- 0.19.2 surface lines (crease lines across the top) ---------------------------------
    'facet_style': _p(EnumProperty, name='Surface Lines', items=[
        ('NONE', 'None', 'Smooth top'), ('CENTER', 'Center Line', 'One crease along the length'),
        ('CROSS', 'Cross', 'Two creases crossing in the middle'),
        ('RANDOM', 'Random', 'Random crease lines (Seed / Count)')], default='NONE'),
    'facet_depth': _p(FloatProperty, name='Crease Height', default=0.6, soft_min=-2.0, soft_max=2.0,
                      description='Height of the crease lines (1 = a tenth of the plate size; the plate height '
                                  'does not change it): + = raised ridge, - = sunken valley'),
    'facet_width': _p(FloatProperty, name='Line Width', default=0.0, min=0.0, soft_max=0.8, subtype='FACTOR',
                      description='Flat band along the line (part of the plate size): 0 = sharp ridge, wider = a '
                                  'raised strip with a chamfer on both sides'),
    'facet_offset': _p(FloatProperty, name='Line Position', default=0.0, soft_min=-1.0, soft_max=1.0,
                       description='Move the lines across the plate (part of the plate size)'),
    'facet_count': _p(IntProperty, name='Line Count', default=3, min=1, max=8),
    'facet_seed': _p(IntProperty, name='Line Seed', default=1, min=0),
    'facet_rotation': _p(FloatProperty, name='Line Rotation', default=0.0, subtype='ANGLE'),
    # ---- 0.19.4 edge rims (raised border band per side) -----------------------------------------
    'rim_n': _p(BoolProperty, name='N', default=False, description='Raise the north border band'),
    'rim_e': _p(BoolProperty, name='E', default=False, description='Raise the east border band'),
    'rim_s': _p(BoolProperty, name='S', default=False, description='Raise the south border band'),
    'rim_w': _p(BoolProperty, name='W', default=False, description='Raise the west border band'),
    'rim_height': _p(FloatProperty, name='Rim Height', default=0.5, soft_min=-2.0, soft_max=2.0,
                     description='Height of the raised border (1 = a tenth of the plate size; - = sunken)'),
    'rim_random': _p(BoolProperty, name='Random Pieces', default=False,
                     description='Raised pieces at random places along the border (Seed / Count)'),
    'rim_seed': _p(IntProperty, name='Rim Seed', default=1, min=0),
    'rim_count': _p(IntProperty, name='Rim Pieces', default=3, min=1, max=10),
    'rim_profile': _p(EnumProperty, name='Rim Edge', items=[
        ('CHAMFER', 'Chamfer', 'Straight slope from the rim down to the plate'),
        ('BEVEL', 'Bevel', 'Rounded slope from the rim down to the plate')], default='CHAMFER'),
    'rim_slope': _p(FloatProperty, name='Rim Slope', default=0.3, min=0.02, soft_max=2.0,
                    description='Width of the chamfer / bevel from the rim down to the plate (part of the rim width)'),
    'rim_width': _p(FloatProperty, name='Rim Width', default=0.15, min=0.01, soft_max=0.6, subtype='FACTOR',
                    description='Width of the border band (part of the plate size)'),
    'smooth_shading': _p(BoolProperty, name='Smooth Shading', default=True,
                         description='Smooth shading with sharp edges by angle (OFF = flat)'),
    # ---- Armor Sculpt: orientation -----------------------------------------------------------------
    'dir_rotation': _p(FloatProperty, name='Direction Rotation', default=0.0, subtype='ANGLE',
                       description='Rotate N/E/S/W around the region normal'),
    'dir_scale_x': _p(FloatProperty, name='Direction Scale X', default=1.0, min=0.05, soft_max=4.0),
    'dir_scale_y': _p(FloatProperty, name='Direction Scale Y', default=1.0, min=0.05, soft_max=4.0),
    'dir_offset_x': _p(FloatProperty, name='Direction Offset X', default=0.0, soft_min=-1.0, soft_max=1.0),
    'dir_offset_y': _p(FloatProperty, name='Direction Offset Y', default=0.0, soft_min=-1.0, soft_max=1.0),
    'dir_mirror': _p(BoolProperty, name='Mirror Direction', default=False, description='Swap East and West'),
    # ---- centre line -------------------------------------------------------------------------------
    'cl_preset': _p(EnumProperty, name='Center Line', items=[
        ('NONE', 'None', ''), ('STRAIGHT', 'Straight', 'Single line through the centre (N-S)'),
        ('CROSS', 'Cross (+)', 'Vertical + horizontal'), ('Y', 'Y', 'Stem south, two arms north'),
        ('X', 'X', 'Diagonal cross'), ('S', 'S', 'S curve south to north'), ('Z', 'Z', 'Z polyline')],
        default='NONE'),
    'cl_rotation': _p(FloatProperty, name='Rotation', default=0.0, subtype='ANGLE'),
    'cl_scale_x': _p(FloatProperty, name='Scale X', default=1.0, min=0.01, soft_max=4.0),
    'cl_scale_y': _p(FloatProperty, name='Scale Y', default=1.0, min=0.01, soft_max=4.0),
    'cl_offset_x': _p(FloatProperty, name='Offset X', default=0.0, soft_min=-1.0, soft_max=1.0),
    'cl_offset_y': _p(FloatProperty, name='Offset Y', default=0.0, soft_min=-1.0, soft_max=1.0),
    'cl_width': _p(FloatProperty, name='Width', default=0.12, min=0.001, soft_max=1.0,
                   description='Half width of the ridge, relative to the part radius'),
    'cl_height': _p(FloatProperty, name='Ridge Height', default=0.05, min=0.0, soft_max=1.0, precision=4, unit='LENGTH'),
    'cl_strength': _p(FloatProperty, name='Ridge Strength', default=1.0, min=0.0, soft_max=2.0),
    'cl_sharpness': _p(FloatProperty, name='Sharpness', default=0.3, min=0.0, max=1.0, subtype='FACTOR'),
    'cl_roundness': _p(FloatProperty, name='Roundness', default=0.0, min=0.0, max=1.0, subtype='FACTOR'),
    'cl_angle': _p(FloatProperty, name='Angle', default=math.radians(45.0), min=math.radians(3.0),
                   max=math.radians(89.0), subtype='ANGLE', description='Side slope of Flat / Box ridges'),
    'cl_invert': _p(BoolProperty, name='Invert', default=False),
    'cl_symmetry': _p(BoolProperty, name='Symmetry', default=False, description='Mirror the line across N-S'),
    'cl_branch_angle': _p(FloatProperty, name='Branch Angle', default=math.radians(35.0), min=0.0,
                          max=math.radians(89.0), subtype='ANGLE', description='Y / X: spread of the arms'),
    'cl_curvature': _p(FloatProperty, name='Curvature', default=0.6, min=0.0, soft_max=2.0,
                       description='S: bend amount (scaled by East / West length)'),
    'ridge_profile': _p(EnumProperty, name='Ridge Profile', items=[
        ('SHARP', 'Sharp Ridge', ''), ('FLAT', 'Flat Ridge', ''), ('ROUND', 'Round Ridge', ''),
        ('BOX', 'Box Ridge', ''), ('GROOVE', 'Groove', ''), ('SPLIT', 'Split', 'Narrow deep V line between panels')],
        default='SHARP'),
    'transition_width': _p(FloatProperty, name='Transition Width', default=0.25, min=0.01, max=1.0, subtype='FACTOR',
                           description='Ridge fades out over this part of the way to the edge'),
    'transition_smoothness': _p(FloatProperty, name='Transition Smoothness', default=0.1, min=0.0, max=1.0,
                                description='0 = sharp crease where ridges meet, higher = smooth join'),
    'surface_tension': _p(FloatProperty, name='Surface Tension', default=0.0, min=-0.9, max=3.0,
                          description='Directional height transition: < 0 fuller, > 0 tighter to the edge'),
}
for _d, _label in (('n', 'North'), ('e', 'East'), ('s', 'South'), ('w', 'West')):
    _ANN.update({
        f'{_d}_thickness': _p(FloatProperty, name=f'{_label} Thickness', default=0.1, min=0.0001, soft_max=5.0,
                              precision=4, unit='LENGTH', description=f'Height at the {_label.lower()} edge'),
        f'{_d}_chamfer_width': _p(FloatProperty, name=f'{_label} Chamfer Width', default=0.0, min=0.0, soft_max=0.5,
                                  precision=4, unit='LENGTH'),
        f'{_d}_chamfer_angle': _p(FloatProperty, name=f'{_label} Chamfer Angle', default=math.radians(45.0),
                                  min=0.0, max=math.radians(89.0), subtype='ANGLE'),
        f'{_d}_bevel_width': _p(FloatProperty, name=f'{_label} Bevel Width', default=0.0, min=0.0, soft_max=0.5,
                                precision=4, unit='LENGTH'),
        f'{_d}_bevel_segments': _p(IntProperty, name=f'{_label} Bevel Segments', default=3, min=1, max=16),
        f'{_d}_slope': _p(FloatProperty, name=f'{_label} Slope / Taper', default=0.5, min=0.02, max=1.0,
                          subtype='FACTOR', description='How far toward the centre the edge height reaches'),
        f'{_d}_roundness': _p(FloatProperty, name=f'{_label} Roundness', default=0.5, min=0.0, max=1.0,
                              subtype='FACTOR', description='0 = straight slope, 1 = rounded'),
        f'cl_{_d}_length': _p(FloatProperty, name=f'{_label} Length', default=0.8, min=0.0, soft_max=2.0,
                              description=f'Centre line reach toward {_label.lower()}'),
        f'cl_{_d}_width': _p(FloatProperty, name=f'{_label} Width', default=1.0, min=0.05, soft_max=4.0,
                             description=f'Ridge width factor toward {_label.lower()}'),
    })

MCH_PG_Extract = type('MCH_PG_Extract', (bpy.types.PropertyGroup,), {'__annotations__': _ANN})
SETTING_KEYS = [k for k in _ANN if k not in {'is_part', 'source', 'region', 'surround', 'notes'}]


# =============================================================================
# Region capture
# =============================================================================


def _components(faces):
    """Connected selected face sets (sharing an edge)."""
    left = set(faces)
    comps = []
    while left:
        start = left.pop()
        comp, todo = [start], [start]
        while todo:
            f = todo.pop()
            for e in f.edges:
                for g in e.link_faces:
                    if g in left:
                        left.discard(g)
                        comp.append(g)
                        todo.append(g)
        comps.append(comp)
    return comps


def _faces_to_mesh(name, faces):
    vmap, coords, polys = {}, [], []
    for f in faces:
        idx = []
        for v in f.verts:
            if v not in vmap:
                vmap[v] = len(coords)
                coords.append(v.co.copy())
            idx.append(vmap[v])
        polys.append(idx)
    me = bpy.data.meshes.new(name)
    me.from_pydata(coords, [], polys)
    me.update()
    from . import edge_memory as _em; _em.mark_generated(me)   # 0.24.95 Edge Memory: the part's own lines
    return me


def capture_regions(ob, bm):
    """[(region_mesh, surround_mesh)] for each selected face island of ``ob``."""
    sel = [f for f in bm.faces if f.select]
    out = []
    for comp in _components(sel):
        ring = set(comp)
        for _ in range(2):                  # two rings of neighbours for outward projection
            ring |= {g for f in list(ring) for v in f.verts for g in v.link_faces}
        out.append((_faces_to_mesh('MCH_ExtractRegion', comp), _faces_to_mesh('MCH_ExtractSurround', list(ring))))
    return out


# =============================================================================
# Build / modifiers
# =============================================================================


def rebuild(ob):
    p = ob.mch_extract
    notes = []
    try:
        bm = pg.build(p.region, p.surround, p, armor=(p.mode == 'ARMOR'), notes=notes)
    except pg.PanelError as ex:
        p.notes = str(ex)
        return False
    try:
        bm.to_mesh(ob.data)
        from . import edge_memory as _em; _em.mark_generated(ob.data)   # 0.24.95 Edge Memory: the part's own lines
    finally:
        bm.free()
    me = ob.data
    if p.smooth_shading:
        try:
            me.set_sharp_from_angle(angle=math.radians(35.0))
        except (AttributeError, TypeError):
            pass
    crease = me.attributes.get('mch_crease')
    if crease is not None and crease.domain == 'EDGE':
        sharp = me.attributes.get('sharp_edge') or me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
        vals = [0.0] * len(me.edges)
        crease.data.foreach_get('value', vals)
        flags = [False] * len(me.edges)
        sharp.data.foreach_get('value', flags)
        sharp.data.foreach_set('value', [bool(f or c > 0.5) for f, c in zip(flags, vals)])
    me.update()
    _sync_modifiers(ob)
    p.notes = '; '.join(notes)
    return True


def _sync_modifiers(ob):
    p = ob.mch_extract
    side = ob.modifiers.get(MOD_SIDE)
    want_side = p.bevel_width > 0 and p.mode == 'BASIC'
    if want_side:
        if side is None:
            side = ob.modifiers.new(MOD_SIDE, 'BEVEL')
        side.limit_method = 'WEIGHT'
        side.width = p.bevel_width
        side.segments = p.bevel_segments
        side.profile = p.bevel_profile
        side.use_clamp_overlap = True
        side.harden_normals = False
    elif side is not None:
        ob.modifiers.remove(side)
        side = None
    shell = ob.modifiers.get(MOD_SHELL)
    if p.thickness > 0:
        if shell is None:
            shell = ob.modifiers.new(MOD_SHELL, 'SOLIDIFY')
        shell.thickness = p.thickness
        shell.offset = -1.0
        shell.use_even_offset = True
        shell.use_rim = True
    elif shell is not None:
        ob.modifiers.remove(shell)
        shell = None
    # keep order: side bevel first, then shell
    if side is not None and shell is not None and ob.modifiers.find(MOD_SIDE) > ob.modifiers.find(MOD_SHELL):
        ob.modifiers.move(ob.modifiers.find(MOD_SIDE), ob.modifiers.find(MOD_SHELL))


def _parts_collection(context, sub=COLL_PARTS):
    scene = context.scene
    root = bpy.data.collections.get(COLL_ROOT)
    if root is None:
        root = bpy.data.collections.new(COLL_ROOT)
    if root.name not in scene.collection.children:
        try:
            scene.collection.children.link(root)
        except RuntimeError:
            pass
    coll = bpy.data.collections.get(sub)
    if coll is None:
        coll = bpy.data.collections.new(sub)
    if coll.name not in root.children:
        try:
            root.children.link(coll)
        except RuntimeError:
            pass
    return coll


def active_part(context):
    ob = context.active_object
    if ob is not None and getattr(ob, 'mch_extract', None) and ob.mch_extract.is_part:
        return ob
    last = getattr(context.scene, 'mch_extract_last', None)
    if last is not None and last.name in bpy.data.objects and last.mch_extract.is_part:
        return last
    return None


# =============================================================================
# Operators
# =============================================================================


class MCH_OT_face_extract(bpy.types.Operator):
    bl_idname = 'mch.face_extract'
    bl_label = 'Extract Selected Faces'
    bl_description = ('Edit Mode: every selected face island (on every object in Edit Mode) becomes its own part; '
                      'the source mesh is not changed. Settings stay live on the part')
    bl_options = {'REGISTER', 'UNDO'}

    mode: EnumProperty(items=[('BASIC', 'Basic Extract', ''), ('ARMOR', 'Armor Sculpt', '')], default='BASIC')
    stay_in_edit: BoolProperty(name='Stay in Edit Mode', default=True,
                               description='Keep editing the source; the panel shows the new part')

    @classmethod
    def poll(cls, context):
        return context.mode == 'EDIT_MESH'

    def execute(self, context):
        defaults = context.scene.mch_extract
        objs = [o for o in (context.objects_in_mode or [context.active_object]) if o is not None and o.type == 'MESH']
        made, problems = [], []
        coll = _parts_collection(context)
        for src in objs:
            src.update_from_editmode()
            bm = bmesh.from_edit_mesh(src.data)
            regions = capture_regions(src, bm)
            for region, surround in regions:
                me = bpy.data.meshes.new(src.name + '_Armor' if self.mode == 'ARMOR' else src.name + '_Extract')
                part = bpy.data.objects.new(me.name, me)
                coll.objects.link(part)
                part.matrix_world = src.matrix_world.copy()
                for mat in src.data.materials:
                    me.materials.append(mat)
                p = part.mch_extract
                for key in SETTING_KEYS:
                    if key != 'mode':
                        setattr(p, key, getattr(defaults, key))
                p.mode = self.mode
                p.source = src
                p.region = region
                p.surround = surround
                p.is_part = True                       # from now on settings rebuild live
                if not rebuild(part):
                    problems.append(f'{src.name}: {p.notes}')
                    _remove_part(part)
                    continue
                made.append(part)
        if not made:
            self.report({'ERROR'}, 'Nothing extracted: ' + ('; '.join(problems) or 'select faces first'))
            return {'CANCELLED'}
        context.scene.mch_extract_last = made[-1]
        if not self.stay_in_edit:
            bpy.ops.object.mode_set(mode='OBJECT')
            for o in context.selected_objects:
                o.select_set(False)
            for m in made:
                m.select_set(True)
            context.view_layer.objects.active = made[-1]
        msg = f'{len(made)} part(s) extracted ({self.mode.title()}); source unchanged'
        if problems:
            msg += ' | skipped: ' + '; '.join(problems)
        self.report({'WARNING' if problems else 'INFO'}, msg)
        return {'FINISHED'}


def _remove_part(part):
    p = part.mch_extract
    region, surround = p.region, p.surround
    me = part.data
    bpy.data.objects.remove(part)
    for m in (me, region, surround):
        if m is not None and m.users == 0:
            bpy.data.meshes.remove(m)


def _part_targets(context):
    obs = [o for o in context.selected_objects if getattr(o, 'mch_extract', None) and o.mch_extract.is_part]
    ap = active_part(context)
    if ap is not None and ap not in obs:
        obs.append(ap)
    return obs


class MCH_OT_extract_apply(bpy.types.Operator):
    bl_idname = 'mch.extract_apply'
    bl_label = 'Apply Part'
    bl_description = 'Bake the part (and its shell / side bevel) into a plain mesh; settings are dropped'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return context.mode == 'OBJECT' and bool(_part_targets(context))

    def execute(self, context):
        from . import core_geometry as cg
        from . import live_queue
        live_queue.flush()                  # 0.24.73 a rebuild still waiting goes in before applying
        done = []
        for ob in _part_targets(context):
            for name in (MOD_SIDE, MOD_SHELL):
                mod = ob.modifiers.get(name)
                if mod is not None:
                    cg.apply_single_modifier(context, ob, mod)
            p = ob.mch_extract
            region, surround = p.region, p.surround
            p.is_part = False
            p.region = None
            p.surround = None
            for m in (region, surround):
                if m is not None and m.users == 0:
                    bpy.data.meshes.remove(m)
            done.append(ob.name)
        self.report({'INFO'}, 'Applied: ' + ', '.join(done))
        return {'FINISHED'}


class MCH_OT_extract_reset(bpy.types.Operator):
    bl_idname = 'mch.extract_reset'
    bl_label = 'Reset Settings'
    bl_description = 'Back to the default settings (the extracted region is kept)'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return bool(_part_targets(context))

    def execute(self, context):
        for ob in _part_targets(context):
            p = ob.mch_extract
            p.is_part = False            # no rebuild per property
            for key in SETTING_KEYS:
                if key != 'mode':
                    p.property_unset(key)
            p.is_part = True
            rebuild(ob)
        return {'FINISHED'}


class MCH_OT_extract_copy_settings(bpy.types.Operator):
    bl_idname = 'mch.extract_copy_settings'
    bl_label = 'Copy Settings to Selected Parts'
    bl_description = 'Multi-part: copy every setting of the active part to the other selected parts'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and getattr(ob, 'mch_extract', None) and ob.mch_extract.is_part and \
            len(_part_targets(context)) > 1

    def execute(self, context):
        src = context.active_object.mch_extract
        n = 0
        for ob in _part_targets(context):
            if ob == context.active_object:
                continue
            p = ob.mch_extract
            p.is_part = False
            for key in SETTING_KEYS:
                setattr(p, key, getattr(src, key))
            p.is_part = True
            rebuild(ob)
            n += 1
        self.report({'INFO'}, f'Settings copied to {n} part(s)')
        return {'FINISHED'}


class MCH_OT_extract_select(bpy.types.Operator):
    bl_idname = 'mch.extract_select'
    bl_label = 'Select Part'
    bl_description = 'Go to Object Mode and select the part shown in the panel'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return active_part(context) is not None

    def execute(self, context):
        part = active_part(context)
        if context.mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        for o in context.selected_objects:
            o.select_set(False)
        part.hide_set(False)
        part.select_set(True)
        context.view_layer.objects.active = part
        return {'FINISHED'}


# =============================================================================
# Panel drawing (tool EXTRACT)
# =============================================================================


def _fold(layout, context, key, title, default_closed=False):
    """Collapsible section (layout.panel in Blender 4.1+, a box otherwise)."""
    if hasattr(layout, 'panel'):
        header, body = layout.panel('mch_' + key, default_closed=default_closed)
        header.label(text=title)
        return body
    box = layout.box()
    box.label(text=title)
    return box


def draw(layout, context):
    from . import armor_shell
    armor_shell.draw(layout, context)              # 0.24.80 the whole surface as a shell (Object Mode)
    part = active_part(context)
    d = context.scene.mch_extract
    row = layout.row(align=True)
    row.scale_y = 1.5
    op = row.operator('mch.face_extract', text='Basic Extract', icon='FACESEL')
    op.mode = 'BASIC'
    op = row.operator('mch.face_extract', text='Armor Sculpt', icon='MOD_SOLIDIFY')
    op.mode = 'ARMOR'
    if context.mode != 'EDIT_MESH':
        layout.label(text='Tab into Edit Mode, select faces, then Extract', icon='INFO')
    p = part.mch_extract if part is not None else d
    box = layout.box()
    if part is not None:
        box.label(text='PART: ' + part.name, icon='MESH_DATA')
        if part != context.active_object:
            box.operator('mch.extract_select', icon='RESTRICT_SELECT_OFF')
        box.row(align=True).prop(p, 'mode', expand=True)
        if p.notes:
            box.label(text=p.notes, icon='INFO')
    else:
        box.label(text='Settings for the next extract', icon='PREFERENCES')
    armor = p.mode == 'ARMOR' and part is not None
    body = _fold(layout, context, 'ex_basic', 'Extract Settings')
    if body:
        col = body.column(align=True)
        col.prop(p, 'extract_height', text='Center Height' if armor else 'Extract Height')
        col.prop(p, 'thickness')
        col.prop(p, 'surface_offset')
        col.prop(p, 'resolution')
        body.prop(p, 'smooth_shading')
        rr = body.row(align=True)
        rr.label(text='Rims')
        for k in 'nesw':
            rr.prop(p, f'rim_{k}', toggle=True)
        rr.prop(p, 'rim_random', toggle=True, text='Random')
        if p.rim_n or p.rim_e or p.rim_s or p.rim_w or p.rim_random:
            rc = body.column(align=True)
            rc.prop(p, 'rim_height', slider=True)
            rc.prop(p, 'rim_width', slider=True)
            rc.row(align=True).prop(p, 'rim_profile', expand=True)
            rc.prop(p, 'rim_slope', slider=True)
            if p.rim_random:
                r2 = rc.row(align=True)
                r2.prop(p, 'rim_count')
                r2.prop(p, 'rim_seed')
            rc.prop(p, 'dir_rotation')
        ln = body.column(align=True)
        ln.prop(p, 'facet_style')
        if p.facet_style != 'NONE':
            ln.prop(p, 'facet_depth', slider=True)
            ln.prop(p, 'facet_width', slider=True)
            ln.prop(p, 'facet_offset', slider=True)
            ln.prop(p, 'facet_rotation')
            if p.facet_style == 'RANDOM':
                r = ln.row(align=True)
                r.prop(p, 'facet_count')
                r.prop(p, 'facet_seed')
    if not armor:
        body = _fold(layout, context, 'ex_bevel', 'Bevel (top edge + side edges)')
        if body:
            col = body.column(align=True)
            col.prop(p, 'bevel_width')
            col.prop(p, 'bevel_segments')
            col.prop(p, 'bevel_profile', slider=True)
            col.prop(p, 'bevel_angle')
        body = _fold(layout, context, 'ex_chamfer', 'Chamfer (top edge)')
        if body:
            body.row(align=True).prop(p, 'chamfer_mode', expand=True)
            col = body.column(align=True)
            sub = col.column(align=True)
            sub.active = p.chamfer_mode != 'DEPTH_ANGLE'
            sub.prop(p, 'chamfer_width')
            sub = col.column(align=True)
            sub.active = p.chamfer_mode != 'WIDTH_DEPTH'
            sub.prop(p, 'chamfer_angle')
            sub = col.column(align=True)
            sub.active = p.chamfer_mode != 'WIDTH_ANGLE'
            sub.prop(p, 'chamfer_depth')
            cw, cd = pg.chamfer_wd(p.chamfer_width, p.chamfer_angle, p.chamfer_depth, p.chamfer_mode)
            body.label(text=f'= width {cw:.4g}, depth {cd:.4g}, angle {math.degrees(math.atan2(cd, cw)) if cw else 90:.1f}°')
            body.row(align=True).prop(p, 'chamfer_direction', expand=True)
    body = _fold(layout, context, 'ex_outer', 'Outer Edge (base)')
    if body:
        col = body.column(align=True)
        col.prop(p, 'outer_bevel_width')
        col.prop(p, 'outer_chamfer_width')
        col.prop(p, 'outer_chamfer_angle')
        if armor:
            col.prop(p, 'bevel_profile', slider=True)
    if armor:
        draw_armor(layout, context, p)
    if part is not None:
        row = layout.row(align=True)
        row.operator('mch.extract_reset', icon='LOOP_BACK')
        row.operator('mch.extract_copy_settings', icon='DUPLICATE')
        row = layout.row()
        row.scale_y = 1.3
        row.operator('mch.extract_apply', icon='CHECKMARK')
    col = layout.column(align=True)
    col.scale_y = 0.8
    col.label(text='Each selected face island = one part (source unchanged)')
    col.label(text='Re-select a part any time: its settings come back')


def draw_armor(layout, context, p):
    body = _fold(layout, context, 'ar_dir', 'Direction Orientation')
    if body:
        col = body.column(align=True)
        col.prop(p, 'dir_rotation')
        row = col.row(align=True)
        row.prop(p, 'dir_scale_x', text='Scale X')
        row.prop(p, 'dir_scale_y', text='Scale Y')
        row = col.row(align=True)
        row.prop(p, 'dir_offset_x', text='Offset X')
        row.prop(p, 'dir_offset_y', text='Offset Y')
        body.prop(p, 'dir_mirror')
    body = _fold(layout, context, 'ar_thick', 'Directional Thickness')
    if body:
        for d, label in (('n', 'North'), ('s', 'South'), ('e', 'East'), ('w', 'West')):
            col = body.column(align=True)
            col.label(text=label)
            col.prop(p, f'{d}_thickness', text='Thickness')
            row = col.row(align=True)
            row.prop(p, f'{d}_slope', text='Slope', slider=True)
            row.prop(p, f'{d}_roundness', text='Round', slider=True)
    body = _fold(layout, context, 'ar_edge', 'Directional Chamfer / Bevel', default_closed=True)
    if body:
        for d, label in (('n', 'North'), ('s', 'South'), ('e', 'East'), ('w', 'West')):
            col = body.column(align=True)
            col.label(text=label)
            row = col.row(align=True)
            row.prop(p, f'{d}_chamfer_width', text='Chamfer')
            row.prop(p, f'{d}_chamfer_angle', text='Angle')
            row = col.row(align=True)
            row.prop(p, f'{d}_bevel_width', text='Bevel')
            row.prop(p, f'{d}_bevel_segments', text='Seg')
    body = _fold(layout, context, 'ar_cl', 'Center Line Presets')
    if body:
        body.prop(p, 'cl_preset', expand=True)
    if p.cl_preset != 'NONE':
        body = _fold(layout, context, 'ar_cltr', 'Center Line Transform')
        if body:
            col = body.column(align=True)
            col.prop(p, 'cl_rotation')
            row = col.row(align=True)
            row.prop(p, 'cl_scale_x')
            row.prop(p, 'cl_scale_y')
            row = col.row(align=True)
            row.prop(p, 'cl_offset_x')
            row.prop(p, 'cl_offset_y')
            col.prop(p, 'cl_width')
            col.prop(p, 'cl_height')
            col.prop(p, 'cl_strength')
            row = col.row(align=True)
            row.prop(p, 'cl_sharpness', slider=True)
            row.prop(p, 'cl_roundness', slider=True)
            row = body.row(align=True)
            row.prop(p, 'cl_invert', toggle=True)
            row.prop(p, 'cl_symmetry', toggle=True)
            if p.cl_preset in {'Y', 'X'}:
                body.prop(p, 'cl_branch_angle')
            if p.cl_preset == 'S':
                body.prop(p, 'cl_curvature')
        body = _fold(layout, context, 'ar_cldir', 'Directional Center Line Editing', default_closed=True)
        if body:
            for d, label in (('n', 'North'), ('s', 'South'), ('e', 'East'), ('w', 'West')):
                row = body.row(align=True)
                row.label(text=label)
                row.prop(p, f'cl_{d}_length', text='Length')
                row.prop(p, f'cl_{d}_width', text='Width')
        body = _fold(layout, context, 'ar_prof', 'Ridge Profile')
        if body:
            body.prop(p, 'ridge_profile', text='')
            col = body.column(align=True)
            col.prop(p, 'cl_height', text='Height / Depth')
            col.prop(p, 'cl_width')
            col.prop(p, 'cl_angle')
            col.prop(p, 'cl_roundness', slider=True)
    body = _fold(layout, context, 'ar_trans', 'Surface Transition', default_closed=True)
    if body:
        col = body.column(align=True)
        col.prop(p, 'transition_width', slider=True)
        col.prop(p, 'transition_smoothness', slider=True)
        col.prop(p, 'surface_tension')


CLASSES = (MCH_PG_Extract, MCH_OT_face_extract, MCH_OT_extract_apply, MCH_OT_extract_reset,
           MCH_OT_extract_copy_settings, MCH_OT_extract_select)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Object.mch_extract = PointerProperty(type=MCH_PG_Extract)
    bpy.types.Scene.mch_extract = PointerProperty(type=MCH_PG_Extract)
    bpy.types.Scene.mch_extract_last = PointerProperty(type=bpy.types.Object)


def unregister():
    for owner, name in ((bpy.types.Scene, 'mch_extract_last'), (bpy.types.Scene, 'mch_extract'),
                        (bpy.types.Object, 'mch_extract')):
        if hasattr(owner, name):
            delattr(owner, name)
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
