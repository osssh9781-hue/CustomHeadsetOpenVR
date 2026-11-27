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
from .light_copies import full as _lc_full  # 0.24.136 a part's own geometry, never its light copy

MAPS = ('NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL', 'CURV', 'HEIGHT', 'EMIT')
SUFFIX = {'NORMAL': 'Normal', 'AO': 'AO', 'COLOR': 'Color', 'ROUGH': 'Roughness', 'METAL': 'Metallic',
          'CURV': 'Curvature', 'HEIGHT': 'Height', 'EMIT': 'Emission'}
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
    # 0.24.243 (user: "러프니스 맵이랑 다른 설정은 맵이 안 생겨?")
    rough: BoolProperty(name='Roughness', default=False, description='The high\'s material roughness')
    metal: BoolProperty(name='Metallic', default=False, description='The high\'s material metallic (0 / 1)')
    curv: BoolProperty(name='Curvature', default=False,
                       description='Convex edges light, crevices dark, flat 50 % grey (for edge wear / dirt masks)')
    # 0.24.325 (user: "노말이랑 베이스 컬러, 러프니스, 범프, 메탈릭, 에미션 필요해")
    # 0.24.325 (user: "베이크 하이폴리 안 하고는 못 해?") the low's own material onto its own UVs, no high
    quality: EnumProperty(name='Quality', default='NORMAL', items=[
        ('DRAFT', 'Draft', 'No High Poly: 4 samples where the shader has AO / Bevel nodes - fastest, a little grain'),
        ('NORMAL', 'Normal', 'No High Poly: 8 samples where the shader has AO / Bevel nodes'),
        ('HIGH', 'High', 'No High Poly: 16 samples there (as before 0.24.329) - slowest, cleanest')],
        description='No High Poly: the samples a shader with AO / Bevel nodes gets (one without needs only 2)')
    own: BoolProperty(name='No High Poly', default=False,
                      description='Bake each selected mesh\'s own material onto its own UVs - no high poly: Normal '
                                  '(its shader\'s bump / bevel), Color, Roughness, Metallic, Emission, AO.  Height / '
                                  'Curvature need a high (left out).  Its materials are kept in the file')
    emit: BoolProperty(name='Emission', default=False,
                       description='The high\'s glow (its materials\' Emission colour x strength; black where none)')
    height: BoolProperty(name='Height', default=False,
                         description='How far the high stands out of (light) or sinks into (dark) the low, flat 50 % grey')
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
    st_ = getattr(context.scene, 'mch_bake', None)
    if st_ is not None and getattr(st_, 'own', False):     # 0.24.325 No High Poly: each mesh onto itself
        own = [o for o in sel if not bk.is_bake(o)]
        if not own:
            raise RuntimeError('No High Poly: select the meshes to bake')
        return [(o, []) for o in own]
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
    img.colorspace_settings.name = 'sRGB' if kind in {'COLOR', 'EMIT'} else 'Non-Color'
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
    if images.get('ROUGH') is not None:            # 0.24.243
        nt.links.new(tex(images['ROUGH'], 600).outputs['Color'], bsdf.inputs['Roughness'])
    if images.get('METAL') is not None:
        nt.links.new(tex(images['METAL'], 900).outputs['Color'], bsdf.inputs['Metallic'])
    if images.get('EMIT') is not None:              # 0.24.325
        nt.links.new(tex(images['EMIT'], 1200).outputs['Color'], bsdf.inputs['Emission Color'])
        bsdf.inputs['Emission Strength'].default_value = 1.0
    bump = None
    if images.get('HEIGHT') is not None:
        bump = nt.nodes.new('ShaderNodeBump')
        bump.location = (100, -650)
        bump.inputs['Strength'].default_value = 0.4
        rng = float(images['HEIGHT'].get('mch_height_range', 0.0))
        if rng > 0:
            bump.inputs['Distance'].default_value = 2.0 * rng
        nt.links.new(tex(images['HEIGHT'], -650).outputs['Color'], bump.inputs['Height'])
        nt.links.new(bump.outputs['Normal'], bsdf.inputs['Normal'])
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
        if bump is not None:                       # (the height bumps on top of the normal map)
            nt.links.new(nm.outputs['Normal'], bump.inputs['Normal'])
        else:
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
SRC = '.MCH Bake Source'
ATTR_CURV, ATTR_HEIGHT = 'mch_bake_curv', 'mch_bake_height'


def _emit_sources(context, low, highs, need=('CURV', 'HEIGHT')):
    """0.24.243 copies of the highs as they show (never the highs themselves), with their curvature and their height
    over the low as point colours - the Metallic / Curvature / Height bakes read these."""
    from mathutils import Vector
    from mathutils.bvhtree import BVHTree
    dg = context.evaluated_depsgraph_get()
    lev = low.evaluated_get(dg)
    lbvh = BVHTree.FromObject(lev, dg)
    Lw, Li = low.matrix_world, low.matrix_world.inverted()
    out = []
    for h in highs:
        me = bpy.data.meshes.new_from_object(h.evaluated_get(dg), preserve_all_data_layers=True, depsgraph=dg)
        me.name = SRC
        ob = bpy.data.objects.new(SRC, me)
        context.scene.collection.objects.link(ob)
        ob.matrix_world = h.matrix_world.copy()
        n = len(me.vertices)
        co = np.empty(n * 3)
        me.vertices.foreach_get('co', co)
        co = co.reshape(-1, 3)
        nr = np.empty(n * 3)
        me.vertices.foreach_get('normal', nr)
        nr = nr.reshape(-1, 3)
        E = np.empty(len(me.edges) * 2, np.int64)
        me.edges.foreach_get('vertices', E)
        E = E.reshape(-1, 2)
        # 0.24.329 only what is baked (a Metallic bake needed neither: the height walked every point of the high)
        cv = np.full(n, 0.5)
        hh = np.full(n, 0.5)
        ob['mch_height_range'] = 0.0
        if 'CURV' not in need:
            pass
        else:
            cv = _curvature(co, nr, E, n)
        if 'HEIGHT' in need:
            hh = _height(h, co, n, lbvh, Lw, Li, ob)
        for name, v in ((ATTR_CURV, cv), (ATTR_HEIGHT, hh)):
            a_ = me.color_attributes.get(name) or me.color_attributes.new(name, 'FLOAT_COLOR', 'POINT')
            a_.data.foreach_set('color', np.c_[v, v, v, np.ones(n)].astype(np.float32).ravel())
        ob['mch_src_mats'] = [m.name if m else '' for m in me.materials]
        out.append(ob)
    return out


def _curvature(co, nr, E, n):
    if True:
        # curvature: how much the neighbours rise above (crevice) or fall below (ridge) each point's tangent plane
        acc = np.zeros(n)
        cnt = np.zeros(n)
        for a, b in ((0, 1), (1, 0)):
            d = co[E[:, b]] - co[E[:, a]]
            ln = np.maximum(np.linalg.norm(d, axis=1), 1e-12)
            np.add.at(acc, E[:, a], (nr[E[:, a]] * d).sum(1) / ln)
            np.add.at(cnt, E[:, a], 1)
        curv = -acc / np.maximum(cnt, 1)
        for _i in range(2):                         # (a little smoothed: no salt and pepper)
            sm = np.zeros(n)
            np.add.at(sm, E[:, 0], curv[E[:, 1]])
            np.add.at(sm, E[:, 1], curv[E[:, 0]])
            curv = 0.5 * curv + 0.5 * sm / np.maximum(cnt, 1)
        sc = max(float(np.percentile(np.abs(curv), 97)), 1e-9)
        return np.clip(0.5 + 0.5 * curv / sc, 0.0, 1.0)


def _height(h, co, n, lbvh, Lw, Li, ob):
    from mathutils import Vector
    if True:
        # height: along the low's normal, from the nearest point of the low
        # 0.24.329 the points in the low's own space at once (numpy), the nearest-point search the only loop; the
        # offset measured there and turned back to world size with the low's normal matrix
        M = np.array(Li @ h.matrix_world)
        L = co @ M[:3, :3].T + M[:3, 3]
        A = np.array(Lw.to_3x3())
        Nm = np.linalg.inv(A).T                         # (normals: the inverse transpose, once)
        hv = np.zeros(n)
        fn_ = lbvh.find_nearest
        for i in range(n):
            q = fn_(Vector(L[i]))
            if q[0] is not None:
                d = A @ (L[i] - np.array(q[0]))          # (world offset)
                nw = Nm @ np.array(q[1])
                nw_l = np.linalg.norm(nw)
                hv[i] = float(d @ (nw / nw_l)) if nw_l > 1e-12 else 0.0
        rng = max(float(np.percentile(np.abs(hv), 99)), 1e-9)
        ob['mch_height_range'] = rng
        return np.clip(0.5 + 0.5 * hv / rng, 0.0, 1.0)


def _metal_input(mat):
    """(socket linked into Metallic or None, value) of the material's Principled BSDF."""
    if mat is None or not mat.node_tree:
        return None, 0.0
    b = next((n for n in mat.node_tree.nodes if n.type == 'BSDF_PRINCIPLED'), None)
    if b is None:
        return None, 0.0
    inp = b.inputs['Metallic']
    return (inp.links[0].from_socket if inp.is_linked else None), float(inp.default_value)


def _emit_material(ob, kind):
    """The copy's slots -> materials that glow its Metallic / curvature / height (white = 1)."""
    me = ob.data
    names = list(ob.get('mch_src_mats', []))
    for i in range(max(1, len(names))):
        src = bpy.data.materials.get(names[i]) if i < len(names) and names[i] else None
        if kind == 'METAL' and src is not None and src.node_tree:
            m = src.copy()
            m.name = '.MCH Bake Emit'
            nt = m.node_tree
            sock, val = _metal_input(m)
            em = nt.nodes.new('ShaderNodeEmission')
            if sock is not None:
                nt.links.new(sock, em.inputs['Color'])
            else:
                em.inputs['Color'].default_value = (val, val, val, 1.0)
        else:
            m = bpy.data.materials.new('.MCH Bake Emit')
            m.use_nodes = True
            nt = m.node_tree
            nt.nodes.clear()
            em = nt.nodes.new('ShaderNodeEmission')
            if kind == 'METAL':
                em.inputs['Color'].default_value = (0.0, 0.0, 0.0, 1.0)
            else:
                at = nt.nodes.new('ShaderNodeAttribute')
                at.attribute_name = ATTR_CURV if kind == 'CURV' else ATTR_HEIGHT
                nt.links.new(at.outputs['Color'], em.inputs['Color'])
        em.inputs['Strength'].default_value = 1.0
        outn = next((n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL'), None) or nt.nodes.new('ShaderNodeOutputMaterial')
        for o_ in [n for n in nt.nodes if n.type == 'OUTPUT_MATERIAL']:
            o_.is_active_output = o_ is outn
        nt.links.new(em.outputs['Emission'], outn.inputs['Surface'])
        old = me.materials[i] if i < len(me.materials) else None
        if i < len(me.materials):
            me.materials[i] = m
        else:
            me.materials.append(m)
        if old is not None and old.name.startswith('.MCH Bake Emit') and old.users == 0:
            bpy.data.materials.remove(old)


def _drop_sources(srcs):
    for ob in srcs or ():
        try:
            me = ob.data
            mats = [m for m in me.materials if m is not None and m.name.startswith('.MCH Bake Emit')]
            bpy.data.objects.remove(ob)
            if me.users == 0:
                bpy.data.meshes.remove(me)
            for m in mats:
                if m.users == 0:
                    bpy.data.materials.remove(m)
        except ReferenceError:
            pass


CAGE = '.MCH Bake Cage'


def make_cage(context, low, ext):
    """The ray cage: the low (with its modifiers) pushed out by ``ext`` (world units) along its AVERAGED point normals.
    Without it Blender casts along the low's shading normals, which split at every sharp edge - the rays there fan
    apart (a gap: dark streaks along the edges) or cross (doubled detail).  Rays go from the cage to the low and on,
    so a sharp low bakes as cleanly as a smooth one."""
    from . import mesh_io as mio
    dg = context.evaluated_depsgraph_get()
    me = bpy.data.meshes.new_from_object(_lc_full(low, dg), depsgraph=dg)
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
        self.device = S.cycles.device if hasattr(S, 'cycles') else None      # 0.24.327 (the bake may switch it to GPU)
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
        if self.device is not None:
            try:
                S.cycles.device = self.device
            except (TypeError, AttributeError):
                pass
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


def use_gpu(context):
    """0.24.327 (user: "베이크가 왜 이렇게 느려?") the scene's Cycles device -> GPU for the bake when Blender's Preferences
    have a GPU on (the Preferences are not changed; the scene's device is put back after).  True when on the GPU."""
    S = context.scene
    try:
        from . import quick_render
        if quick_render.gpu_ready(context):
            S.cycles.device = 'GPU'
            return True
    except (ImportError, AttributeError, TypeError, RuntimeError):
        pass
    return False


def bake_pair(context, low, highs, st, keep_state=None):
    """Bake ``highs`` onto ``low`` with the settings ``st``.  Returns info (dict).  Raises RuntimeError."""
    from . import progress
    return progress.run_now(bake_pair_steps(context, low, highs, st, keep_state))


def bake_pair_steps(context, low, highs, st, keep_state=None):
    """``bake_pair`` in steps (0.24.242 the progress card): yields (fraction, what) before the UVs and each map;
    returns the info."""
    S = context.scene
    t0 = time.time()
    kinds = [k for k, on in (('NORMAL', st.normal), ('AO', st.ao), ('COLOR', st.color),
                             ('ROUGH', getattr(st, 'rough', False)), ('METAL', getattr(st, 'metal', False)),
                             ('CURV', getattr(st, 'curv', False)), ('HEIGHT', getattr(st, 'height', False)),
                             ('EMIT', getattr(st, 'emit', False))) if on]
    if not kinds:
        raise RuntimeError('no map chosen (Normal / AO / Color / Roughness / Metallic / Curvature / Height / Emission)')
    if not highs and getattr(st, 'own', False):
        return (yield from bake_self_steps(context, low, st, kinds, keep_state))
    if not highs:
        raise RuntimeError('no high poly')
    for o in [low] + list(highs):
        if o.name not in context.view_layer.objects:
            raise RuntimeError(f'{o.name} is not in this view layer (its collection is excluded)')
    if len(low.data.polygons) == 0:
        raise RuntimeError(f'{low.name} has no faces')
    res = int(st.res)
    size = size_of(low)
    yield (0.02, 'UVs')
    uv = ensure_uv(context, low, new=st.new_uv, res=res)
    sharp = smooth_low(low, st.sharp_angle) if st.smooth else None
    uv_name = low.data.uv_layers.active.name if low.data.uv_layers.active else ''
    keep = keep_state or _Keep(context, [low] + list(highs))
    images = {}
    swapped = None
    cage = None
    srcs = None
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
        gpu = use_gpu(context)                       # 0.24.327
        ext = size * float(st.ray) / 100.0
        cage = make_cage(context, low, ext)
        common = dict(use_selected_to_active=True, use_cage=True, cage_object=cage.name, cage_extrusion=0.0,
                      max_ray_distance=2.0 * ext, margin=int(st.margin), margin_type='EXTEND', use_clear=True,
                      target='IMAGE_TEXTURES', save_mode='INTERNAL')
        for ki, kind in enumerate(kinds):
            yield (0.08 + 0.9 * ki / len(kinds), f'Baking {SUFFIX[kind]} ({ki + 1} / {len(kinds)})')
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
            elif kind == 'COLOR':
                S.cycles.samples = 4
                r = bpy.ops.object.bake(type='DIFFUSE', pass_filter={'COLOR'}, **common)
            elif kind == 'ROUGH':
                S.cycles.samples = 1
                r = bpy.ops.object.bake(type='ROUGHNESS', **common)
            elif kind == 'EMIT':                    # 0.24.325 the high's own emission, as it is
                S.cycles.samples = 1
                r = bpy.ops.object.bake(type='EMIT', **common)
            else:                                   # 0.24.243 Metallic / Curvature / Height: from copies that glow it
                S.cycles.samples = 1
                if srcs is None:
                    srcs = _emit_sources(context, low, highs, need=[k for k in kinds if k in ('CURV', 'HEIGHT')])
                for h in highs:
                    h.select_set(False)
                for c_ in srcs:
                    _emit_material(c_, kind)
                    c_.select_set(True)
                low.select_set(True)
                context.view_layer.objects.active = low
                try:
                    r = bpy.ops.object.bake(type='EMIT', **common)
                finally:
                    for c_ in srcs:
                        c_.select_set(False)
                    for h in highs:
                        h.select_set(True)
                if kind == 'HEIGHT':
                    img['mch_height_range'] = float(srcs[0].get('mch_height_range', 0.0))
            if 'FINISHED' not in r:
                raise RuntimeError(f'the {SUFFIX[kind]} bake did not finish')
    finally:
        drop_cage(cage)
        _drop_sources(srcs)
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
                seconds=time.time() - t0, gpu=gpu)
    LAST.clear()
    LAST.update(info)
    return info


SELF_KINDS = ('NORMAL', 'AO', 'COLOR', 'ROUGH', 'METAL', 'EMIT')
QUALITY_SAMPLES = {'DRAFT': 4, 'NORMAL': 8, 'HIGH': 16}   # 0.24.329 a shader with AO / Bevel nodes (noisy): samples
PLAIN_SAMPLES = 2                                          # ... one without: just the edges smoothed (no noise)
AO_CAP = {'DRAFT': 16, 'NORMAL': 32}                      # ... and the AO map's samples at most (High: AO Samples)
RAY_NODES = {'AMBIENT_OCCLUSION', 'BEVEL'}


def _walk(nt, seen=None):
    seen = seen if seen is not None else set()
    if nt is None or nt.name in seen:
        return
    seen.add(nt.name)
    for n in nt.nodes:
        yield n
        if n.type == 'GROUP' and n.node_tree is not None:
            yield from _walk(n.node_tree, seen)


def has_ray_nodes(mats):
    """0.24.329 any AO / Bevel node in the materials (their groups too): they make the bake noisy, so it needs samples."""
    return any(n.type in RAY_NODES and not getattr(n, 'mute', False) for m in mats for n in _walk(m.node_tree))


def glows(mats):
    """0.24.329 does any material glow (an Emission shader, a BSDF with Emission Strength > 0 or linked)?  None: the
    Emission map is black - no bake."""
    for m in mats:
        for n in _walk(m.node_tree):
            if n.type == 'EMISSION' and not n.name.startswith('.MCH Bake'):
                st_ = n.inputs['Strength']
                if st_.is_linked or st_.default_value > 0.0:
                    return True
            elif n.type.startswith('BSDF_'):
                st_ = n.inputs.get('Emission Strength')
                if st_ is not None and (st_.is_linked or st_.default_value > 0.0):
                    return True
    return False


def _fill(img, rgb):
    px = np.empty(img.size[0] * img.size[1] * 4, np.float32)
    px.reshape(-1, 4)[:] = (rgb[0], rgb[1], rgb[2], 1.0)
    img.pixels.foreach_set(px)
    img.update()


def _split_rm(img_r, img_m):
    """0.24.329 one bake of Roughness (R) + Metallic (G): each to its own grey map."""
    n = img_r.size[0] * img_r.size[1]
    px = np.empty(n * 4, np.float32)
    img_r.pixels.foreach_get(px)
    px = px.reshape(-1, 4)
    out = px.copy()
    out[:, 0] = out[:, 1] = out[:, 2] = px[:, 1]
    img_m.pixels.foreach_set(out.ravel())
    img_m.update()
    px[:, 1] = px[:, 2] = px[:, 0]
    img_r.pixels.foreach_set(px.ravel())
    img_r.update()


def _own_mats(low):
    """The low's own node materials (each once)."""
    out = []
    for s in low.material_slots:
        m = s.material
        if m is not None and m.use_nodes and m.node_tree and m not in out:
            out.append(m)
    return out


GLOW_INPUTS = {'Base Color': ('Base Color', 'Color'), 'Metallic': ('Metallic',), 'Roughness': ('Roughness',)}
GLOW_DEFAULT = {'Base Color': (0.8, 0.8, 0.8, 1.0), 'Metallic': (0.0, 0.0, 0.0, 1.0), 'Roughness': (0.5, 0.5, 0.5, 1.0)}


def _metal_glow(mats, inp='Metallic'):
    """Each material's BSDFs -> Emissions of their ``inp`` (Base Color / Metallic / Roughness), in place: the Mix /
    Add Shaders round them stay, so a mix of two surfaces bakes as the same mix (0.24.327, the user's wall: a Mix
    Shader of two Principled BSDFs by an edge mask - only the first one had been baked).  Put back by the returned
    function.  (Base Color so: Cycles' Diffuse Color pass is black where the surface is metal.)"""
    undo = []
    for m in mats:
        nt = m.node_tree
        for b in [n for n in nt.nodes if n.type.startswith('BSDF_') or n.type == 'SUBSURFACE_SCATTERING']:
            out = b.outputs[0] if b.outputs else None
            if out is None or not out.is_linked:
                continue
            em = nt.nodes.new('ShaderNodeEmission')
            em.name = '.MCH Bake Glow'
            if isinstance(inp, tuple):              # 0.24.329 two scalars at once: R, G (Roughness, Metallic)
                comb = nt.nodes.new('ShaderNodeCombineColor')
                comb.name = '.MCH Bake Glow'
                for ch, one in zip(('Red', 'Green'), inp):
                    src = b.inputs.get(one)
                    if src is not None and src.is_linked:
                        nt.links.new(src.links[0].from_socket, comb.inputs[ch])
                    else:
                        comb.inputs[ch].default_value = (src.default_value if src is not None
                                                         else GLOW_DEFAULT[one][0])
                comb.inputs['Blue'].default_value = 0.0
                nt.links.new(comb.outputs['Color'], em.inputs['Color'])
                em['mch_comb'] = comb.name
            else:
                src = next((b.inputs[k] for k in GLOW_INPUTS[inp] if b.inputs.get(k) is not None), None)
                if src is not None and src.is_linked:
                    nt.links.new(src.links[0].from_socket, em.inputs['Color'])
                elif src is not None:
                    v = src.default_value
                    em.inputs['Color'].default_value = tuple(v) if hasattr(v, '__len__') else (v, v, v, 1.0)
                else:
                    em.inputs['Color'].default_value = GLOW_DEFAULT[inp]
            em.inputs['Strength'].default_value = 1.0
            tos = [lk.to_socket for lk in out.links]
            for t in tos:
                nt.links.new(em.outputs['Emission'], t)
            undo.append((nt, em, out, tos))
        for e in [n for n in nt.nodes if n.type == 'EMISSION' and not n.name.startswith('.MCH Bake')]:
            st_ = e.inputs['Strength']                   # (its own glow off while its colours are baked)
            if not st_.is_linked:
                undo.append((nt, None, st_, st_.default_value))
                st_.default_value = 0.0

    def back():
        for nt, em, out, tos in reversed(undo):
            if em is None:
                out.default_value = tos
                continue
            for t in tos:
                nt.links.new(out, t)
            cn = nt.nodes.get(em.get('mch_comb', '')) if em.get('mch_comb') else None
            if cn is not None:
                nt.nodes.remove(cn)
            nt.nodes.remove(em)
    return back


def bake_self_steps(context, low, st, kinds, keep_state=None):
    """0.24.325 (user: "베이크 하이폴리 안 하고는 못 해?") No High Poly: ``low``'s own materials baked onto its own UVs
    (Cycles, not Selected to Active): Normal = its shader's normal (bump / bevel nodes), Color, Roughness, Metallic (its
    Metallic glowed), Emission, AO.  Height / Curvature need a high: left out.  Its materials are kept (fake user)."""
    S = context.scene
    t0 = time.time()
    skipped = [k for k in kinds if k not in SELF_KINDS]
    kinds = [k for k in kinds if k in SELF_KINDS]
    if not kinds:
        raise RuntimeError('No High Poly bakes Normal / AO / Color / Roughness / Metallic / Emission (Height / '
                           'Curvature need a high poly)')
    if len(low.data.polygons) == 0:
        raise RuntimeError(f'{low.name} has no faces')
    mats = _own_mats(low)
    if not mats:
        raise RuntimeError(f'{low.name} has no node material to bake')
    res = int(st.res)
    yield (0.02, 'UVs')
    uv = ensure_uv(context, low, new=st.new_uv, res=res)
    sharp = smooth_low(low, st.sharp_angle) if st.smooth else None
    uv_name = low.data.uv_layers.active.name if low.data.uv_layers.active else ''
    keep = keep_state or _Keep(context, [low])
    images = {}
    nodes = []
    skipped_fast = []
    try:
        low.hide_viewport = False
        low.hide_render = False
        low.hide_set(False)
        for o in list(context.selected_objects):
            o.select_set(False)
        low.select_set(True)
        context.view_layer.objects.active = low
        S.render.engine = 'CYCLES'
        gpu = use_gpu(context)                       # 0.24.327
        common = dict(use_selected_to_active=False, margin=int(st.margin), margin_type='EXTEND', use_clear=True,
                      target='IMAGE_TEXTURES', save_mode='INTERNAL')
        # 0.24.329 (user: "베이크가 아직도 너무 느려") samples by need: a shader with AO / Bevel nodes gets the Quality's,
        # one without just a little edge smoothing; no glow: the Emission map black, no bake; Roughness + Metallic in one
        spp = QUALITY_SAMPLES.get(getattr(st, 'quality', 'NORMAL'), 8) if has_ray_nodes(mats) else PLAIN_SAMPLES
        pack = 'ROUGH' in kinds and 'METAL' in kinds
        for ki, kind in enumerate(kinds):
            if kind == 'METAL' and pack:
                continue                            # (baked with the Roughness)
            yield (0.08 + 0.9 * ki / len(kinds), f'Baking {SUFFIX[kind]} ({ki + 1} / {len(kinds)})')
            img = image_for(low, kind, res)
            images[kind] = img
            if kind == 'EMIT' and not glows(mats):
                _fill(img, (0.0, 0.0, 0.0))
                skipped_fast.append('EMIT')
                continue
            for nt, n in nodes:
                nt.nodes.remove(n)
            nodes = []
            for m in mats:                          # (the image the bake writes: the active node of every material)
                n = m.node_tree.nodes.new('ShaderNodeTexImage')
                n.name = '.MCH Bake Target'
                n.image = img
                m.node_tree.nodes.active = n
                nodes.append((m.node_tree, n))
            back = None
            if kind == 'NORMAL':
                S.cycles.samples = 4
                g = 'NEG_Y' if st.green == 'DIRECTX' else 'POS_Y'
                r = bpy.ops.object.bake(type='NORMAL', normal_space='TANGENT', normal_r='POS_X', normal_g=g,
                                        normal_b='POS_Z', **common)
            elif kind == 'AO':                      # 0.24.329 capped by the Quality (its shader has its AO look already)
                S.cycles.samples = min(int(st.ao_samples), AO_CAP.get(getattr(st, 'quality', 'NORMAL'), 10 ** 6))
                if S.world is None:
                    keep.temp_world = bpy.data.worlds.new('.MCH Bake World')
                    S.world = keep.temp_world
                S.world.light_settings.distance = size_of(low) * float(st.ao_distance) / 100.0
                r = bpy.ops.object.bake(type='AO', **common)
            elif kind == 'COLOR':                   # (its Base Color glowed: the Diffuse pass is black on metal)
                S.cycles.samples = spp
                back = _metal_glow(mats, 'Base Color')
                try:
                    r = bpy.ops.object.bake(type='EMIT', **common)
                finally:
                    back()
            elif kind == 'ROUGH':                   # (its Roughness glowed, through its Mix Shaders)
                S.cycles.samples = spp
                back = _metal_glow(mats, ('Roughness', 'Metallic') if pack else 'Roughness')
                try:
                    r = bpy.ops.object.bake(type='EMIT', **common)
                finally:
                    back()
                if pack and 'FINISHED' in r:
                    mimg = image_for(low, 'METAL', res)
                    images['METAL'] = mimg
                    _split_rm(img, mimg)
            elif kind == 'EMIT':
                S.cycles.samples = spp
                r = bpy.ops.object.bake(type='EMIT', **common)
            else:                                   # METAL: its Metallic glowed for the bake
                S.cycles.samples = spp
                back = _metal_glow(mats)
                try:
                    r = bpy.ops.object.bake(type='EMIT', **common)
                finally:
                    back()
            if 'FINISHED' not in r:
                raise RuntimeError(f'the {SUFFIX[kind]} bake did not finish')
    finally:
        for nt, n in nodes:
            try:
                nt.nodes.remove(n)
            except (ReferenceError, RuntimeError):
                pass
        if keep_state is None:
            keep.restore(context)
    stored = {k: _store_image(img, st) for k, img in images.items()}
    mat = None
    if st.use_on_low:
        for m in mats:                              # (its own materials stay in the file)
            m.use_fake_user = True
        # 0.24.327 (user: "결과가 달라 보여, 왼쪽 흰 벽이랑 똑같아야 되는데") its own shader has its AO look in its colour
        # already: the AO map is not multiplied in again (it stays a map of its own, for the engine)
        mat = baked_material(low, {k: v for k, v in images.items() if k != 'AO'},
                             _base_colour([s.material for s in low.material_slots]), st.green, uv_name)
        for s in low.material_slots:
            s.material = mat
    info = dict(low=low.name, highs=[], maps=kinds, res=res, uv=uv, sharp=sharp, ray=0.0, stored=stored,
                material=mat.name if mat else None, seconds=time.time() - t0, own=True, skipped=skipped, gpu=gpu)
    LAST.clear()
    LAST.update(info)
    return info


def describe(info):
    where = next(iter(info['stored'].values()), '')
    where = 'packed in the .blend' if where == 'packed' else f'saved to {os.path.dirname(where)}'
    src = 'its own material' if info.get('own') else "+".join(info["highs"])
    return (f'Bake Maps: {", ".join(SUFFIX[k] for k in info["maps"])} {info["res"]} px  {src} -> '
            f'{info["low"]}' + (' (Smart UV made)' if info['uv'] == 'smart' else '')
            + (f' ({", ".join(SUFFIX[k] for k in info["skipped"])}: needs a high poly, left out)'
               if info.get('skipped') else '')
            + (f', {info["sharp"]:,} sharp edges' if info.get('sharp') is not None else '')
            + f', {where}' + (f', material {info["material"]}' if info.get('material') else '') + f', {info["seconds"]:.1f} s'
            + ('' if info.get('gpu', True) else ' on the CPU (turn the GPU on: Quick Render\'s GPU button / Preferences '
                                                 '> System - much faster)'))


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
    r_ = col.row(align=True)
    r_.prop(st, 'own', toggle=True, icon='MATERIAL')     # 0.24.325 no high poly: its own material
    if st.own:
        r_.prop(st, 'quality', text='')                  # 0.24.329
    r = col.row(align=True)
    r.prop(st, 'normal', toggle=True)
    r.prop(st, 'ao', toggle=True)
    r.prop(st, 'color', toggle=True)
    r = col.row(align=True)                          # 0.24.243
    r.prop(st, 'rough', toggle=True)
    r.prop(st, 'metal', toggle=True)
    r.prop(st, 'curv', toggle=True)
    r.prop(st, 'height', toggle=True)
    r.prop(st, 'emit', toggle=True)                  # 0.24.325
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
        txt = ', '.join(f'{"+".join(h.name for h in hs) if hs else "its own material"} -> {lo.name}'
                        for lo, hs in found[:2]) + (' ...' if len(found) > 2 else '')
        box.label(text=txt, icon='CHECKMARK')
    except RuntimeError:
        box.label(text='Select a part + its BakeHP copy, or low (active) + high', icon='INFO')
    if st.own and (st.height or st.curv):
        box.label(text='No High Poly: Height / Curvature need a high (left out)', icon='INFO')
    from . import retopo_bake                        # 0.24.241 Retopo + Bake (0.24.243 last: the sections above keep
    retopo_bake.draw(layout, context)                # their colours)


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
