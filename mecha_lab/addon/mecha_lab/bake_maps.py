"""0.24.95 Bake Maps: bake a high poly onto our low poly (user: "우리 만든 거 내가 베이크도 할 수 있게 베이킹 툴도
만들어 주라, 우리 거 리메시나 그런 거 한 거 말이야").

The pair (``pairs``):
    * a part and its Bake High Poly copy ``<name>_BakeHP`` find each other - select either one (or many parts at
      once: every one with its own copy is baked in turn); the part is the low (Quad Remesh / Decimate / Edge Mesh /
      Fix Mesh made it), the BakeHP copy the high;
    * otherwise the classic way: the active mesh is the low, the other selected meshes are the high.

One bake (``bake_pair``), Cycles "Selected to Active", the scene put back as it was afterwards (engine, samples, the
world's AO distance, what is selected / hidden):
    1. UVs: the low's own; Smart UV Project only when it has none (or **New UVs** asks for a fresh layer);
    2. shading: **Smooth Low** smooths it with its hard edges (Edge Memory marks + more than **Sharp Angle**) sharp
       where they are UV island borders (a sharp edge inside an island tears a tangent-space map), the way a normal
       map is meant to be used (the map is baked against this shading);
    3. the maps: **Normal** (tangent, OpenGL or DirectX green), **AO** (from the high; other objects shade it only
       with **Others Shade AO**), **Color** (the high's base colour / polypaint material) - one image each,
       ``<low>_Normal`` / ``_AO`` / ``_Color`` at **Size**, reused on the next bake;
    4. rays: from a cage (the low pushed out by **Ray Distance**, % of the low's size, along its averaged normals -
       no split rays at sharp edges) through the low, twice that far - the gap the high may be off the low on
       either side;
    5. the low's materials are swapped for a bake target only while baking (the user's materials are never edited);
       **Use on Low** then gives it ``<low>_Baked`` (the maps hooked up: normal map, AO x base colour, colour);
    6. the images: saved as PNG in **Folder** (default ``//bake_maps/``, next to the .blend) when the file is saved,
       else packed into the .blend.
"""
from __future__ import annotations

import math
import os
import time

import bpy
import numpy as np
from bpy.props import BoolProperty, EnumProperty, FloatProperty, IntProperty, StringProperty

MAPS = ('NORMAL', 'AO', 'COLOR')
SUFFIX = {'NORMAL': 'Normal', 'AO': 'AO', 'COLOR': 'Color'}
UV_NAME = 'MCH_Bake'
MAT_SUFFIX = '_Baked'
TARGET_MAT = '.MCH Bake Target'
IMG_KEY = 'mch_bake_map'          # image: "<low name>|<map>"
BASE_KEY = 'mch_bake_base'        # baked material: the base colour taken from the low's own material
LAST = {}                         # the last run (tests / message)


def _pg_res_items():
    return [(str(r), f'{r}', f'{r} x {r} pixels') for r in (256, 512, 1024, 2048, 4096, 8192)]


class MCH_PG_BakeMaps(bpy.types.PropertyGroup):
    res: EnumProperty(name='Size', items=_pg_res_items(), default='2048', description='The map size in pixels')
    normal: BoolProperty(name='Normal', default=True, description='Tangent-space normal map: the high\'s surface detail on the low')
    ao: BoolProperty(name='AO', default=True, description='Ambient occlusion of the high (crevices darker)')
    color: BoolProperty(name='Color', default=False, description='The high\'s base colour (its material / polypaint)')
    ray: FloatProperty(name='Ray Distance', default=2.0, min=0.05, max=20.0, precision=2, subtype='PERCENTAGE',
                       description='How far the high may be off the low (% of the low\'s size), on either side.  Too small: '
                       'holes in the map; too big: rays catch a neighbouring wall of a thin part')
    margin: IntProperty(name='Margin', default=16, min=0, max=64, subtype='PIXEL',
                        description='Pixels the maps run on past each UV island (no seams when mip-mapped)')
    ao_samples: IntProperty(name='AO Samples', default=64, min=4, max=2048, description='More = smoother AO, slower')
    ao_distance: FloatProperty(name='AO Distance', default=20.0, min=0.5, max=200.0, subtype='PERCENTAGE',
                               description='How far AO looks for occluders (% of the low\'s size)')
    ao_others: BoolProperty(name='Others Shade AO', default=False,
                            description='Other objects in the scene darken the AO too (off: only the high itself)')
    green: EnumProperty(name='Green', items=[('OPENGL', 'OpenGL', 'Y+ (Blender, Unity, Substance default)'),
                                             ('DIRECTX', 'DirectX', 'Y- (Unreal, 3ds Max)')], default='OPENGL',
                        description='Normal map green channel convention')
    new_uv: BoolProperty(name='New UVs', default=False,
                         description=f'Smart UV Project into a new UV layer "{UV_NAME}" even when the low has UVs (off: '
                         'its own UVs, Smart UV only when it has none)')
    smooth: BoolProperty(name='Smooth Low', default=True,
                         description='Smooth the low with its hard edges sharp (Edge Memory + Sharp Angle) before baking '
                         '- the normal map is baked against this shading')
    sharp_angle: FloatProperty(name='Sharp Angle', default=math.radians(60.0), min=math.radians(5.0), max=math.radians(180.0),
                               subtype='ANGLE', description='Edges bent more than this are sharp on the low')
    use_on_low: BoolProperty(name='Use on Low', default=True,
                             description=f'Give the low a material "<name>{MAT_SUFFIX}" with the maps hooked up (off: its '
                             'materials stay; the images are made either way)')
    save: BoolProperty(name='Save PNGs', default=True,
                       description='Save the maps as PNG in Folder (needs a saved .blend; else they are packed into it)')
    folder: StringProperty(name='Folder', default='//bake_maps/', subtype='DIR_PATH',
                           description='Where the PNGs go (// = next to the .blend)')
    show: BoolProperty(name='Show Low', default=True, description='After baking show the low (the high hidden)')


def settings(context):
    return getattr(context.scene, 'mch_bake', None)


# ---------------------------------------------------------------------------------------------------- which meshes
def _visible(o):
    try:
        return bool(o.visible_get())
    except RuntimeError:
        return False


def twin_high(low):
    """``low``'s Bake High Poly copy (the newest visible one), or None."""
    from . import bake_highpoly as bk
    hs = [o for o in bpy.data.objects if o.type == 'MESH' and o.get(bk.SRC_KEY) == low.name and o is not low]
    if not hs:
        return None
    return sorted(hs, key=lambda o: (_visible(o), o.name))[-1]


def pairs(context):
    """[(low, [highs])]: parts with their BakeHP copies, else the active mesh (low) + the other selected (high).
    Raises RuntimeError when there is no pair."""
    from . import bake_highpoly as bk
    act = context.view_layer.objects.active
    sel = [o for o in context.selected_objects if o.type == 'MESH']
    if not sel and act is not None and act.type == 'MESH':
        sel = [act]
    out, unpaired = {}, []
    for o in sel:
        if bk.is_bake(o):
            low = bpy.data.objects.get(o[bk.SRC_KEY])
            if low is not None and low.type == 'MESH' and low is not o:
                hs = out.setdefault(low.name, (low, []))[1]
                if o not in hs:
                    hs.append(o)
                continue
        else:
            hp = twin_high(o)
            if hp is not None:
                hs = out.setdefault(o.name, (o, []))[1]
                if not any(bk.is_bake(h) for h in hs):
                    hs.append(hp)
                continue
        unpaired.append(o)
    if out and not unpaired:
        return list(out.values())
    if act is not None and act.type == 'MESH' and act in sel and len(sel) >= 2:
        return [(act, [o for o in sel if o is not act])]
    raise RuntimeError('select the low poly (active) and its high poly - or a part with its Bake High Poly copy')


def size_of(ob):
    """The object's world bounding-box diagonal."""
    from mathutils import Vector
    pts = [ob.matrix_world @ Vector(c) for c in ob.bound_box]
    lo = Vector([min(p[k] for p in pts) for k in range(3)])
    hi = Vector([max(p[k] for p in pts) for k in range(3)])
    return max((hi - lo).length, 1e-6)


# ---------------------------------------------------------------------------------------------------- the low
def _select_state(me):
    out = {}
    for name, seq in (('v', me.vertices), ('e', me.edges), ('f', me.polygons)):
        a = np.zeros(len(seq), bool)
        seq.foreach_get('select', a)
        out[name] = a
    return out


def _put_select_state(me, st):
    for name, seq in (('v', me.vertices), ('e', me.edges), ('f', me.polygons)):
        if len(seq) == len(st[name]):
            seq.foreach_set('select', st[name])


def ensure_uv(context, low, new=False, res=2048):
    """UVs for the bake: the low's own (the active render layer), or Smart UV Project when it has none / ``new``.
    Returns 'kept' / 'smart'."""
    me = low.data
    if me.uv_layers and not new:
        return 'kept'
    lay = me.uv_layers.get(UV_NAME) if new else None
    if lay is None:
        lay = me.uv_layers.new(name=UV_NAME if (new or not me.uv_layers) else None)
    me.uv_layers.active = lay
    lay.active_render = True
    keep = _select_state(me)
    prev_active = context.view_layer.objects.active
    prev_sel = [o for o in context.selected_objects]
    for o in prev_sel:
        o.select_set(False)
    low.select_set(True)
    context.view_layer.objects.active = low
    try:
        bpy.ops.object.mode_set(mode='EDIT')
        try:
            bpy.ops.mesh.select_all(action='SELECT')
            bpy.ops.uv.smart_project(angle_limit=math.radians(66.0), island_margin=max(0.002, 6.0 / float(res)),
                                     area_weight=0.0, correct_aspect=True, scale_to_bounds=False)
        finally:
            bpy.ops.object.mode_set(mode='OBJECT')
    finally:
        _put_select_state(me, keep)
        low.select_set(False)
        for o in prev_sel:
            try:
                o.select_set(True)
            except RuntimeError:
                pass
        context.view_layer.objects.active = prev_active
    return 'smart'


def uv_seams(me, eps=1e-5):
    """bool per edge: the edge splits the active UV map (its two faces' UVs differ there) or is open - the island
    borders."""
    from . import mesh_io as mio
    ne = len(me.edges)
    seam = np.zeros(ne, bool)
    lay = me.uv_layers.active
    if lay is None or not ne or not len(me.loops):
        return seam | (mio.edge_face_counts(me) != 2) if ne else seam
    uv = np.empty(len(me.loops) * 2, np.float32)
    lay.uv.foreach_get('vector', uv)
    uv = uv.reshape(-1, 2).astype(np.float64)
    cv = mio.read_corner_verts(me)
    ce = mio.read_corner_edges(me)
    start, tot = mio.read_face_starts(me)
    nxt = np.arange(len(cv)) + 1
    last = start.astype(np.int64) + tot - 1
    nxt[last] = start
    va, vb = cv, cv[nxt]
    ua, ub = uv, uv[nxt]
    swap = va > vb                                     # (the UV at the lower point first, on both faces)
    ua, ub = np.where(swap[:, None], ub, ua), np.where(swap[:, None], ua, ub)
    order = np.argsort(ce, kind='stable')
    e_s = ce[order]
    cnt = np.bincount(ce, minlength=ne)
    seam[cnt != 2] = True
    first = np.searchsorted(e_s, np.arange(ne))
    two = np.nonzero(cnt == 2)[0]
    c1, c2 = order[first[two]], order[first[two] + 1]
    diff = np.abs(ua[c1] - ua[c2]).sum(1) + np.abs(ub[c1] - ub[c2]).sum(1)
    seam[two[diff > eps]] = True
    return seam


def smooth_low(low, angle):
    """Smooth faces; sharp = (what was sharp + Edge Memory marks + edges bent more than ``angle`` + open edges) ON A
    UV ISLAND BORDER.  A sharp edge inside a UV island tears the tangent-space normal map (both sides need very
    different map colours right next to each other: a dark line along the edge after filtering), so a hard edge
    that is not a seam stays smooth and the map carries its turn.  Returns the number of sharp edges."""
    from . import bake_highpoly as bk
    me = low.data
    hard = bk.hard_mask(me, angle=angle, memory=True, specks=False)
    old = me.attributes.get('sharp_edge')
    if old is not None and old.domain == 'EDGE' and len(me.edges):
        a = np.zeros(len(me.edges), bool)
        old.data.foreach_get('value', a)
        hard |= a
    hard &= uv_seams(me)
    me.shade_smooth()
    att = me.attributes.get('sharp_edge')
    if att is None:
        att = me.attributes.new('sharp_edge', 'BOOLEAN', 'EDGE')
    att.data.foreach_set('value', hard)
    me.update()
    return int(hard.sum())


# ---------------------------------------------------------------------------------------------------- images, materials
def image_for(low, kind, res):
    name = f'{low.name}_{SUFFIX[kind]}'
    img = bpy.data.images.get(name)
    if img is not None and (img.size[0] != res or img.size[1] != res):
        img.scale(res, res)
    if img is None:
        img = bpy.data.images.new(name, res, res, alpha=False, float_buffer=False)
    img.colorspace_settings.name = 'sRGB' if kind == 'COLOR' else 'Non-Color'
    img[IMG_KEY] = f'{low.name}|{kind}'
    return img


def _target_material(img):
    mat = bpy.data.materials.get(TARGET_MAT)
    if mat is None:
        mat = bpy.data.materials.new(TARGET_MAT)
    mat.use_nodes = True
    nt = mat.node_tree
    node = next((n for n in nt.nodes if n.type == 'TEX_IMAGE'), None) or nt.nodes.new('ShaderNodeTexImage')
    node.image = img
    nt.nodes.active = node
    return mat


def _swap_materials(low, mat):
    """Every slot of ``low`` -> ``mat`` (one slot added when it has none).  Returns what to put back."""
    slots = [s.material for s in low.material_slots]
    added = not slots
    if added:
        low.data.materials.append(mat)
    else:
        for s in low.material_slots:
            s.material = mat
    return slots, added


def _restore_materials(low, kept):
    slots, added = kept
    if added:
        low.data.materials.pop(index=len(low.data.materials) - 1)
        return
    for s, m in zip(low.material_slots, slots):
        s.material = m


def _base_colour(mats):
    for m in mats:
        if m is None:
            continue
        if BASE_KEY in m:
            return tuple(m[BASE_KEY])
        if m.use_nodes and m.node_tree:
            b = next((n for n in m.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
            if b is not None:
                return tuple(b.inputs['Base Color'].default_value)
        return tuple(m.diffuse_color)
    return (0.6, 0.6, 0.62, 1.0)


def baked_material(low, images, base, green='OPENGL', uv_name=''):
    """``<low>_Baked``: Principled BSDF, base colour (x AO), the colour map, the normal map - made fresh each time."""
    name = low.name + MAT_SUFFIX
    mat = bpy.data.materials.get(name) or bpy.data.materials.new(name)
    mat.use_nodes = True
    mat[BASE_KEY] = list(base)
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new('ShaderNodeOutputMaterial')
    out.location = (600, 0)
    bsdf = nt.nodes.new('ShaderNodeBsdfPrincipled')
    bsdf.location = (300, 0)
    nt.links.new(bsdf.outputs['BSDF'], out.inputs['Surface'])
    bsdf.inputs['Base Color'].default_value = base
    bsdf.inputs['Roughness'].default_value = 0.5

    def tex(img, y):
        n = nt.nodes.new('ShaderNodeTexImage')
        n.image = img
        n.location = (-500, y)
        if uv_name:
            uv = nt.nodes.new('ShaderNodeUVMap')
            uv.uv_map = uv_name
            uv.location = (-750, y)
            nt.links.new(uv.outputs['UV'], n.inputs['Vector'])
        return n
    colour = None
    if images.get('COLOR') is not None:
        colour = tex(images['COLOR'], 300).outputs['Color']
    if images.get('AO') is not None:
        ao = tex(images['AO'], 0)
        mix = nt.nodes.new('ShaderNodeMix')
        mix.data_type = 'RGBA'
        mix.blend_type = 'MULTIPLY'
        mix.location = (0, 150)
        mix.inputs['Factor'].default_value = 1.0
        if colour is not None:
            nt.links.new(colour, mix.inputs['A'])
        else:
            mix.inputs['A'].default_value = base
        nt.links.new(ao.outputs['Color'], mix.inputs['B'])
        colour = mix.outputs['Result']
    if colour is not None:
        nt.links.new(colour, bsdf.inputs['Base Color'])
    if images.get('NORMAL') is not None:
        n = tex(images['NORMAL'], -300)
        nm = nt.nodes.new('ShaderNodeNormalMap')
        nm.space = 'TANGENT'
        nm.uv_map = uv_name
        nm.location = (0, -300)
        src = n.outputs['Color']
        if green == 'DIRECTX':                     # (flip green back for Blender's own view)
            sep = nt.nodes.new('ShaderNodeSeparateColor')
            inv = nt.nodes.new('ShaderNodeMath')
            inv.operation = 'SUBTRACT'
            inv.inputs[0].default_value = 1.0
            comb = nt.nodes.new('ShaderNodeCombineColor')
            sep.location, inv.location, comb.location = (-250, -450), (-100, -450), (-50, -300)
            nt.links.new(src, sep.inputs['Color'])
            nt.links.new(sep.outputs['Red'], comb.inputs['Red'])
            nt.links.new(sep.outputs['Green'], inv.inputs[1])
            nt.links.new(inv.outputs['Value'], comb.inputs['Green'])
            nt.links.new(sep.outputs['Blue'], comb.inputs['Blue'])
            src = comb.outputs['Color']
        nt.links.new(src, nm.inputs['Color'])
        nt.links.new(nm.outputs['Normal'], bsdf.inputs['Normal'])
    return mat


def _store_image(img, st):
    """PNG in the folder when the .blend is saved (and Save PNGs is on), else packed.  Returns the path or 'packed'."""
    if st.save and bpy.data.filepath:
        folder = bpy.path.abspath(st.folder or '//bake_maps/')
        os.makedirs(folder, exist_ok=True)
        path = os.path.join(folder, bpy.path.clean_name(img.name) + '.png')
        img.filepath_raw = path
        img.file_format = 'PNG'
        img.save()
        try:
            img.filepath = bpy.path.relpath(path)
        except ValueError:
            img.filepath = path
        if img.packed_file is not None:
            img.unpack(method='REMOVE')
        return path
    img.pack()
    return 'packed'


# ---------------------------------------------------------------------------------------------------- the bake
CAGE = '.MCH Bake Cage'


def make_cage(context, low, ext):
    """The ray cage: the low (with its modifiers) pushed out by ``ext`` (world units) along its AVERAGED point normals.
    Without it Blender casts along the low's shading normals, which split at every sharp edge - the rays there fan
    apart (a gap: dark streaks along the edges) or cross (doubled detail).  Rays go from the cage to the low and on,
    so a sharp low bakes as cleanly as a smooth one."""
    from . import mesh_io as mio
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(low.evaluated_get(dg), depsgraph=dg)
    me.name = CAGE
    co = mio.read_co(me)
    nrm = np.empty(len(co) * 3, np.float32)
    me.vertex_normals.foreach_get('vector', nrm)
    sc = low.matrix_world.to_scale()
    s = max(float(np.mean(np.abs([sc.x, sc.y, sc.z]))), 1e-9)
    mio.write_co(me, co + nrm.reshape(-1, 3).astype(np.float64) * (ext / s))
    me.update()
    cage = bpy.data.objects.new(CAGE, me)
    cage.matrix_world = low.matrix_world.copy()
    context.scene.collection.objects.link(cage)
    cage.hide_render = True
    return cage


def drop_cage(cage):
    if cage is None:
        return
    try:
        me = cage.data
        bpy.data.objects.remove(cage)
        if me is not None and me.users == 0:
            bpy.data.meshes.remove(me)
    except ReferenceError:
        pass


class _Keep:
    """The scene state a bake touches, put back by ``restore``."""

    def __init__(self, context, objs):
        S = context.scene
        self.engine = S.render.engine
        self.samples = S.cycles.samples if hasattr(S, 'cycles') else None
        self.world = S.world
        self.ao_dist = S.world.light_settings.distance if S.world is not None else None
        self.active = context.view_layer.objects.active
        self.selected = list(context.selected_objects)
        self.hidden = {o.name: (o.hide_get(), o.hide_viewport, o.hide_render) for o in objs}
        self.render_off = []
        self.temp_world = None

    def restore(self, context):
        S = context.scene
        S.render.engine = self.engine
        if self.samples is not None:
            S.cycles.samples = self.samples
        if self.temp_world is not None:
            S.world = self.world
            bpy.data.worlds.remove(self.temp_world)
        elif S.world is not None and self.ao_dist is not None:
            S.world.light_settings.distance = self.ao_dist
        for o in self.render_off:
            try:
                o.hide_render = False
            except ReferenceError:
                pass
        for name, (h, hv, hr) in self.hidden.items():
            o = bpy.data.objects.get(name)
            if o is not None:
                o.hide_viewport = hv
                o.hide_render = hr
                try:
                    o.hide_set(h)
                except RuntimeError:
                    pass
        for o in list(context.selected_objects):
            o.select_set(False)
        for o in self.selected:
            try:
                o.select_set(True)
            except (RuntimeError, ReferenceError):
                pass
        try:
            context.view_layer.objects.active = self.active
        except (RuntimeError, ReferenceError):
            pass


def bake_pair(context, low, highs, st, keep_state=None):
    """Bake ``highs`` onto ``low`` with the settings ``st``.  Returns info (dict).  Raises RuntimeError."""
    S = context.scene
    t0 = time.time()
    kinds = [k for k, on in (('NORMAL', st.normal), ('AO', st.ao), ('COLOR', st.color)) if on]
    if not kinds:
        raise RuntimeError('no map chosen (Normal / AO / Color)')
    if not highs:
        raise RuntimeError('no high poly')
    for o in [low] + list(highs):
        if o.name not in context.view_layer.objects:
            raise RuntimeError(f'{o.name} is not in this view layer (its collection is excluded)')
    if len(low.data.polygons) == 0:
        raise RuntimeError(f'{low.name} has no faces')
    res = int(st.res)
    size = size_of(low)
    uv = ensure_uv(context, low, new=st.new_uv, res=res)
    sharp = smooth_low(low, st.sharp_angle) if st.smooth else None
    uv_name = low.data.uv_layers.active.name if low.data.uv_layers.active else ''
    keep = keep_state or _Keep(context, [low] + list(highs))
    images = {}
    swapped = None
    cage = None
    try:
        for o in [low] + list(highs):           # (hidden ones can't be selected / baked)
            o.hide_viewport = False
            o.hide_render = False
            o.hide_set(False)
        for o in list(context.selected_objects):
            o.select_set(False)
        for h in highs:
            h.select_set(True)
        low.select_set(True)
        context.view_layer.objects.active = low
        S.render.engine = 'CYCLES'
        ext = size * float(st.ray) / 100.0
        cage = make_cage(context, low, ext)
        common = dict(use_selected_to_active=True, use_cage=True, cage_object=cage.name, cage_extrusion=0.0,
                      max_ray_distance=2.0 * ext, margin=int(st.margin), margin_type='EXTEND', use_clear=True,
                      target='IMAGE_TEXTURES', save_mode='INTERNAL')
        for kind in kinds:
            img = image_for(low, kind, res)
            images[kind] = img
            tgt = _target_material(img)
            if swapped is None:
                swapped = _swap_materials(low, tgt)
            if kind == 'NORMAL':
                S.cycles.samples = 1
                g = 'NEG_Y' if st.green == 'DIRECTX' else 'POS_Y'
                r = bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', normal_r='POS_X', normal_g=g,
                                        normal_b='POS_Z', **common)
            elif kind == 'AO':
                S.cycles.samples = int(st.ao_samples)
                if S.world is None:
                    keep.temp_world = bpy.data.worlds.new('.MCH Bake World')
                    S.world = keep.temp_world
                S.world.light_settings.distance = size * float(st.ao_distance) / 100.0
                if not st.ao_others:
                    mine = {low.name} | {h.name for h in highs}
                    for o in context.view_layer.objects:
                        if o.name not in mine and not o.hide_render and o.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT', 'CURVES', 'VOLUME'}:
                            o.hide_render = True
                            keep.render_off.append(o)
                r = bpy.ops.object.bake(type='AO', **common)
                for o in keep.render_off:
                    o.hide_render = False
                keep.render_off.clear()
            else:
                S.cycles.samples = 4
                r = bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, **common)
            if 'FINISHED' not in r:
                raise RuntimeError(f'the {SUFFIX[kind]} bake did not finish')
    finally:
        drop_cage(cage)
        if swapped is not None:
            _restore_materials(low, swapped)
        tm = bpy.data.materials.get(TARGET_MAT)
        if tm is not None and tm.users == 0:
            bpy.data.materials.remove(tm)
        if keep_state is None:
            keep.restore(context)
    stored = {k: _store_image(img, st) for k, img in images.items()}
    mat = None
    if st.use_on_low:
        mat = baked_material(low, images, _base_colour([s.material for s in low.material_slots]), st.green, uv_name)
        if not low.material_slots:
            low.data.materials.append(mat)
        else:
            for s in low.material_slots:
                s.material = mat
    info = dict(low=low.name, highs=[h.name for h in highs], maps=kinds, res=res, uv=uv, sharp=sharp,
                ray=size * float(st.ray) / 100.0, stored=stored, material=mat.name if mat else None,
                seconds=time.time() - t0)
    LAST.clear()
    LAST.update(info)
    return info


def describe(info):
    where = next(iter(info['stored'].values()), '')
    where = 'packed in the .blend' if where == 'packed' else f'saved to {os.path.dirname(where)}'
    return (f'Bake Maps: {", ".join(SUFFIX[k] for k in info["maps"])} {info["res"]} px  {"+".join(info["highs"])} -> '
            f'{info["low"]}' + (' (Smart UV made)' if info['uv'] == 'smart' else '')
            + (f', {info["sharp"]:,} sharp edges' if info.get('sharp') is not None else '')
            + f', {where}' + (f', material {info["material"]}' if info.get('material') else '') + f', {info["seconds"]:.1f} s')


def run(context, st=None):
    """Every pair from the selection.  Returns the message."""
    st = st or settings(context)
    todo = pairs(context)
    objs = [lo for lo, _h in todo] + [h for _lo, hs in todo for h in hs]
    keep = _Keep(context, objs)
    infos = []
    try:
        for low, highs in todo:
            infos.append(bake_pair(context, low, highs, st, keep_state=keep))
    finally:
        keep.restore(context)
    if st.show:
        lows = {i['low'] for i in infos}
        for i in infos:
            for h in i['highs']:
                ob = bpy.data.objects.get(h)
                if ob is not None and h not in lows:
                    ob.hide_set(True)
                    ob.select_set(False)
        for name in lows:
            ob = bpy.data.objects.get(name)
            if ob is not None:
                ob.hide_set(False)
                ob.select_set(True)
        last = bpy.data.objects.get(infos[-1]['low'])
        if last is not None:
            context.view_layer.objects.active = last
    if len(infos) == 1:
        return describe(infos[0])
    return f'Bake Maps: {len(infos)} parts, {sum(i["seconds"] for i in infos):.1f} s - ' + describe(infos[-1])


class MCH_OT_bake_maps(bpy.types.Operator):
    """Bake the high poly onto the low poly: Normal / AO / Color maps (Cycles, Selected to Active).  Select a part and
    its Bake High Poly copy (either one), or the low (active) + the high"""
    bl_idname = 'mch.bake_maps'
    bl_label = 'Bake Maps'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return settings(context) is not None and any(o.type == 'MESH' for o in context.selected_objects)

    def execute(self, context):
        mode = context.mode
        act = context.view_layer.objects.active
        if mode != 'OBJECT':
            bpy.ops.object.mode_set(mode='OBJECT')
        try:
            from . import safety_save
            safety_save.before_risky('Bake Maps')
        except (ImportError, AttributeError, RuntimeError):
            pass
        try:
            msg = run(context)
        except RuntimeError as ex:
            self.report({'WARNING'}, str(ex))
            return {'CANCELLED'}
        finally:
            if mode != 'OBJECT' and act is not None:          # back to the mode it was in, on the object it was on
                try:
                    act.hide_set(False)
                    context.view_layer.objects.active = act
                    act.select_set(True)
                    bpy.ops.object.mode_set(mode={'SCULPT': 'SCULPT', 'EDIT_MESH': 'EDIT', 'PAINT_VERTEX': 'VERTEX_PAINT',
                                                  'PAINT_TEXTURE': 'TEXTURE_PAINT', 'PAINT_WEIGHT': 'WEIGHT_PAINT'}.get(mode, 'OBJECT'))
                except RuntimeError:
                    pass
        self.report({'INFO'}, msg)
        return {'FINISHED'}


def draw(layout, context):
    st = settings(context)
    if st is None:
        return
    box = layout.box()
    box.label(text='BAKE MAPS  (high -> low)', icon='TEXTURE')
    col = box.column(align=True)
    r = col.row(align=True)
    r.scale_y = 1.2
    r.operator('mch.bake_maps', text='Bake Maps', icon='RENDER_STILL')
    r.prop(st, 'res', text='')
    r = col.row(align=True)
    r.prop(st, 'normal', toggle=True)
    r.prop(st, 'ao', toggle=True)
    r.prop(st, 'color', toggle=True)
    col = box.column(align=True)
    col.prop(st, 'ray', slider=True)
    r = col.row(align=True)
    r.prop(st, 'margin')
    r.prop(st, 'green', text='')
    if st.ao:
        col = box.column(align=True)
        r = col.row(align=True)
        r.prop(st, 'ao_samples', text='AO Samples')
        r.prop(st, 'ao_distance', text='Dist')
        col.prop(st, 'ao_others', toggle=True)
    col = box.column(align=True)
    r = col.row(align=True)
    r.prop(st, 'smooth', toggle=True)
    sub = r.row(align=True)
    sub.enabled = st.smooth
    sub.prop(st, 'sharp_angle', text='')
    r = col.row(align=True)
    r.prop(st, 'new_uv', toggle=True)
    r.prop(st, 'use_on_low', toggle=True)
    r.prop(st, 'show', toggle=True)
    r = col.row(align=True)
    r.prop(st, 'save', toggle=True)
    sub = r.row(align=True)
    sub.enabled = st.save
    sub.prop(st, 'folder', text='')
    try:
        found = pairs(context)
        txt = ', '.join(f'{"+".join(h.name for h in hs)} -> {lo.name}' for lo, hs in found[:2]) + (' ...' if len(found) > 2 else '')
        box.label(text=txt, icon='CHECKMARK')
    except RuntimeError:
        box.label(text='Select a part + its BakeHP copy, or low (active) + high', icon='INFO')


CLASSES = (MCH_PG_BakeMaps, MCH_OT_bake_maps)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Scene.mch_bake = bpy.props.PointerProperty(type=MCH_PG_BakeMaps)


def unregister():
    if hasattr(bpy.types.Scene, 'mch_bake'):
        del bpy.types.Scene.mch_bake
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
