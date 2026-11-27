"""0.24.263 Simple material (user: "툴 옆에 메크랑 크리쳐 있는데 그거 말고 심플 메테리얼 하나 - 쉐이더 창처럼 나오는 건데
기본으로 프린시플처럼 작동하는 거").

A plain Principled BSDF material, its settings on the side panel's Simple page - grouped like Blender's own shader
panel (Surface, Subsurface, Specular, Transmission, Coat, Sheen, Emission, Thin Film).  The values live on the material
(``Material.mch_simple``) and go straight into its Principled node when changed, so the material renders, exports and
edits in the shader editor exactly like any Principled material.  "Use This Material" takes an existing material with a
Principled node over (its values read in).
"""
from __future__ import annotations

import bpy
from bpy.props import BoolProperty, EnumProperty, FloatProperty, FloatVectorProperty, PointerProperty, StringProperty

PAGE = 'SIMPLE'
NODE = 'Principled BSDF'

# (property, socket, kind, default, soft max)  kind: 'f' a number, 'c' a colour
FIELDS = (
    ('base_color', 'Base Color', 'c', (0.8, 0.8, 0.8), None),
    ('metallic', 'Metallic', 'f', 0.0, 1.0),
    ('roughness', 'Roughness', 'f', 0.5, 1.0),
    ('ior', 'IOR', 'f', 1.5, 3.0),
    ('alpha', 'Alpha', 'f', 1.0, 1.0),
    ('subsurface', 'Subsurface Weight', 'f', 0.0, 1.0),
    ('subsurface_scale', 'Subsurface Scale', 'f', 0.05, 1.0),
    ('specular', 'Specular IOR Level', 'f', 0.5, 1.0),
    ('specular_tint', 'Specular Tint', 'c', (1.0, 1.0, 1.0), None),
    ('anisotropic', 'Anisotropic', 'f', 0.0, 1.0),
    ('anisotropic_rotation', 'Anisotropic Rotation', 'f', 0.0, 1.0),
    ('transmission', 'Transmission Weight', 'f', 0.0, 1.0),
    ('coat', 'Coat Weight', 'f', 0.0, 1.0),
    ('coat_roughness', 'Coat Roughness', 'f', 0.03, 1.0),
    ('coat_ior', 'Coat IOR', 'f', 1.5, 3.0),
    ('coat_tint', 'Coat Tint', 'c', (1.0, 1.0, 1.0), None),
    ('sheen', 'Sheen Weight', 'f', 0.0, 1.0),
    ('sheen_roughness', 'Sheen Roughness', 'f', 0.5, 1.0),
    ('sheen_tint', 'Sheen Tint', 'c', (1.0, 1.0, 1.0), None),
    ('emission_color', 'Emission Color', 'c', (1.0, 1.0, 1.0), None),
    ('emission', 'Emission Strength', 'f', 0.0, 20.0),
    ('thin_film', 'Thin Film Thickness', 'f', 0.0, 1000.0),
    ('thin_film_ior', 'Thin Film IOR', 'f', 1.33, 3.0),
)
GROUPS = (('surface', 'Surface', ('base_color', 'metallic', 'roughness', 'ior', 'alpha'), False),
          ('subsurface', 'Subsurface', ('subsurface', 'subsurface_scale'), True),
          ('specular', 'Specular', ('specular', 'specular_tint', 'anisotropic', 'anisotropic_rotation'), True),
          ('transmission', 'Transmission', ('transmission',), True),
          ('coat', 'Coat', ('coat', 'coat_roughness', 'coat_ior', 'coat_tint'), True),
          ('sheen', 'Sheen', ('sheen', 'sheen_roughness', 'sheen_tint'), True),
          ('emission', 'Emission', ('emission_color', 'emission'), True),
          ('thin_film', 'Thin Film', ('thin_film', 'thin_film_ior'), True))
_BY = {f[0]: f for f in FIELDS}


def principled(mat):
    """The material's Principled node (the one named so, else the first), or None."""
    if mat is None or not mat.use_nodes or mat.node_tree is None:
        return None
    nt = mat.node_tree
    n = nt.nodes.get(NODE)
    if n is not None and n.bl_idname == 'ShaderNodeBsdfPrincipled':
        return n
    return next((x for x in nt.nodes if x.bl_idname == 'ShaderNodeBsdfPrincipled'), None)


def _write(mat, prop):
    n = principled(mat)
    if n is None:
        return
    _p, sock, kind, _d, _m = _BY[prop]
    s = n.inputs.get(sock)
    if s is None or s.is_linked:                     # (a texture plugged in: left alone)
        return
    v = getattr(mat.mch_simple, prop)
    s.default_value = (v[0], v[1], v[2], 1.0) if kind == 'c' else v
    if prop == 'alpha':                              # (see-through in EEVEE too)
        try:
            mat.surface_render_method = 'BLENDED' if v < 0.999 else 'DITHERED'
        except (AttributeError, TypeError):
            pass


def _updater(prop):
    def upd(self, context):
        mat = self.id_data
        if isinstance(mat, bpy.types.Material) and self.on:
            _write(mat, prop)
            if prop == 'roughness' and getattr(self, 'tex_image', None) is not None:
                tex_sync(mat)                        # (0.24.345 the slider's share of the textured roughness)
    return upd


def read(mat):
    """The material's Principled values into its Simple settings (unplugged inputs only)."""
    n = principled(mat)
    if n is None:
        return False
    st = mat.mch_simple
    st.on = False                                    # (no write-back while reading)
    for prop, sock, kind, _d, _m in FIELDS:
        s = n.inputs.get(sock)
        if s is None or s.is_linked:
            continue
        v = s.default_value
        setattr(st, prop, tuple(v[:3]) if kind == 'c' else float(v))
    st.on = True
    return True


def is_simple(mat):
    return mat is not None and getattr(mat, 'mch_simple', None) is not None and mat.mch_simple.on


def active_material(context):
    ob = getattr(context, 'active_object', None)
    return ob.active_material if ob is not None and ob.type in {'MESH', 'CURVE', 'SURFACE', 'META', 'FONT'} else None


def new_material(name='Simple'):
    mat = bpy.data.materials.new(name)
    mat.use_nodes = True
    read(mat)
    return mat


# ---------------------------------------------------------------------------------------------------------------------
# 0.24.345 (user: "심플 메테리얼에 베이스 컬러에 텍스처 불러올 수 있게 해 주고 그 소스로 범프랑 러프니스도 다 조절할 수
# 있게"): one picture for the Base Color, its colour adjusted (Bright / Contrast / Hue / Saturation / Value / Tint), and
# the same picture's grey made the Roughness (Amount, From / To, Invert) and the Bump (Strength, Distance, Invert).
# Our nodes are named "mchs:..." - made anew when the picture / a switch changes, their values set when a slider does.
# ---------------------------------------------------------------------------------------------------------------------
TEX = 'mchs:'


def _tex_nodes(mat):
    return [n for n in mat.node_tree.nodes if n.name.startswith(TEX)] if mat and mat.node_tree else []


def tex_build(mat):
    """The texture's nodes (made anew) into the material - or taken out (no picture): the sliders back in charge."""
    n = principled(mat)
    if n is None:
        return
    nt = mat.node_tree
    st = mat.mch_simple
    for x in _tex_nodes(mat):
        nt.nodes.remove(x)
    img = st.tex_image
    if img is None:
        for prop in ('base_color', 'roughness'):
            _write(mat, prop)
        return
    x0, y0 = n.location.x - 1100, n.location.y

    def node(kind, name, dx, dy):
        nd = nt.nodes.new(kind)
        nd.name = nd.label = TEX + name
        nd.location = (x0 + dx, y0 + dy)
        return nd
    tc = node('ShaderNodeTexCoord', 'coord', 0, 0)
    mp = node('ShaderNodeMapping', 'map', 180, 0)
    nt.links.new(tc.outputs['UV' if st.tex_proj == 'UV' else 'Object'], mp.inputs['Vector'])
    tx = node('ShaderNodeTexImage', 'image', 380, 0)
    tx.image = img
    if st.tex_proj == 'BOX':
        tx.projection = 'BOX'
        tx.projection_blend = 0.2
    nt.links.new(mp.outputs['Vector'], tx.inputs['Vector'])
    bc = node('ShaderNodeBrightContrast', 'bc', 680, 120)
    nt.links.new(tx.outputs['Color'], bc.inputs['Color'])
    hs = node('ShaderNodeHueSaturation', 'hsv', 860, 120)
    nt.links.new(bc.outputs['Color'], hs.inputs['Color'])
    tint = node('ShaderNodeMix', 'tint', 1040, 120)
    tint.data_type = 'RGBA'
    tint.blend_type = 'MULTIPLY'
    tint.inputs['Factor'].default_value = 1.0
    nt.links.new(hs.outputs['Color'], tint.inputs['A'])
    nt.links.new(tint.outputs['Result'], n.inputs['Base Color'])
    bw = node('ShaderNodeRGBToBW', 'grey', 680, -160)
    nt.links.new(tx.outputs['Color'], bw.inputs['Color'])
    if st.rough_on:
        mr = node('ShaderNodeMapRange', 'rough_range', 860, -120)
        mr.clamp = True
        nt.links.new(bw.outputs['Val'], mr.inputs['Value'])
        mx = node('ShaderNodeMix', 'rough_amount', 1040, -120)
        mx.data_type = 'FLOAT'
        nt.links.new(mr.outputs['Result'], mx.inputs['B'])
        nt.links.new(mx.outputs['Result'], n.inputs['Roughness'])
    else:
        _write(mat, 'roughness')
    nin = n.inputs['Normal']
    if st.bump_on:
        bp = node('ShaderNodeBump', 'bump', 1040, -380)
        nt.links.new(bw.outputs['Val'], bp.inputs['Height'])
        nt.links.new(bp.outputs['Normal'], nin)
    tex_sync(mat)


def tex_sync(mat):
    """The sliders' values into our nodes (no rebuild)."""
    st = mat.mch_simple
    nd = mat.node_tree.nodes if mat and mat.node_tree else None
    if nd is None or nd.get(TEX + 'image') is None:
        return
    mp = nd.get(TEX + 'map')
    if mp is not None:
        sc = max(st.tex_scale, 1e-4)
        mp.inputs['Scale'].default_value = (sc, sc, sc)
        mp.inputs['Rotation'].default_value = (0.0, 0.0, st.tex_rotation)
    bc = nd.get(TEX + 'bc')
    if bc is not None:
        bc.inputs['Bright'].default_value = st.tex_bright
        bc.inputs['Contrast'].default_value = st.tex_contrast
    hs = nd.get(TEX + 'hsv')
    if hs is not None:
        hs.inputs['Hue'].default_value = st.tex_hue
        hs.inputs['Saturation'].default_value = st.tex_saturation
        hs.inputs['Value'].default_value = st.tex_value
    tn = nd.get(TEX + 'tint')
    if tn is not None:
        tn.inputs['B'].default_value = (*st.tex_tint, 1.0)
    mr = nd.get(TEX + 'rough_range')
    if mr is not None:
        lo, hi = st.rough_from, st.rough_to
        if st.rough_invert:
            lo, hi = hi, lo
        mr.inputs['To Min'].default_value = lo
        mr.inputs['To Max'].default_value = hi
    mx = nd.get(TEX + 'rough_amount')
    if mx is not None:
        mx.inputs['Factor'].default_value = st.rough_amount
        mx.inputs['A'].default_value = st.roughness
    bp = nd.get(TEX + 'bump')
    if bp is not None:
        bp.inputs['Strength'].default_value = st.bump_strength
        bp.inputs['Distance'].default_value = st.bump_distance
        bp.invert = st.bump_invert


def _tex_rebuild(self, context):
    mat = self.id_data
    if isinstance(mat, bpy.types.Material) and self.on:
        tex_build(mat)


def _tex_values(self, context):
    mat = self.id_data
    if isinstance(mat, bpy.types.Material) and self.on:
        tex_sync(mat)


TEX_PROPS = dict(
    tex_image=PointerProperty(name='Texture', type=bpy.types.Image, update=_tex_rebuild,
                              description='The picture on the Base Color (its grey also makes the Roughness and the '
                              'Bump)'),
    tex_proj=EnumProperty(name='Projection', items=[('UV', 'UV', 'Along the mesh\'s UVs'),
                                                     ('BOX', 'Box', 'From the six sides (no UVs needed)')],
                          default='UV', update=_tex_rebuild),
    tex_scale=FloatProperty(name='Scale', default=1.0, min=0.001, soft_min=0.1, soft_max=20.0, update=_tex_values,
                            description='How many times the picture repeats'),
    tex_rotation=FloatProperty(name='Rotation', default=0.0, subtype='ANGLE', update=_tex_values),
    tex_bright=FloatProperty(name='Brightness', default=0.0, soft_min=-1.0, soft_max=1.0, update=_tex_values),
    tex_contrast=FloatProperty(name='Contrast', default=0.0, soft_min=-1.0, soft_max=1.0, update=_tex_values),
    tex_hue=FloatProperty(name='Hue', default=0.5, min=0.0, max=1.0, update=_tex_values),
    tex_saturation=FloatProperty(name='Saturation', default=1.0, min=0.0, soft_max=2.0, update=_tex_values),
    tex_value=FloatProperty(name='Value', default=1.0, min=0.0, soft_max=2.0, update=_tex_values),
    tex_tint=FloatVectorProperty(name='Texture Tint', subtype='COLOR', size=3, min=0.0, soft_max=1.0, default=(1.0, 1.0, 1.0),
                                 update=_tex_values, description='The picture x this colour (white: as it is)'),
    rough_on=BoolProperty(name='Roughness from Texture', default=True, update=_tex_rebuild,
                          description='The picture\'s grey makes the Roughness'),
    rough_amount=FloatProperty(name='Amount', default=1.0, min=0.0, max=1.0, update=_tex_values,
                               description='0: the Roughness slider only .. 1: the picture\'s'),
    rough_from=FloatProperty(name='At Dark', default=0.3, min=0.0, max=1.0, update=_tex_values,
                             description='The roughness where the picture is darkest'),
    rough_to=FloatProperty(name='At Light', default=0.8, min=0.0, max=1.0, update=_tex_values,
                           description='The roughness where the picture is lightest'),
    rough_invert=BoolProperty(name='Invert', default=False, update=_tex_values,
                              description='Light parts smooth, dark parts rough'),
    bump_on=BoolProperty(name='Bump from Texture', default=True, update=_tex_rebuild,
                         description='The picture\'s grey as a height: light up, dark down'),
    bump_strength=FloatProperty(name='Strength', default=0.3, min=0.0, max=1.0, update=_tex_values),
    bump_distance=FloatProperty(name='Distance', default=0.05, min=0.0, soft_max=1.0, update=_tex_values,
                                description='How deep the picture\'s dark parts go'),
    bump_invert=BoolProperty(name='Invert', default=False, update=_tex_values,
                             description='Dark parts up, light parts down'),
)


class MCH_PG_Simple(bpy.types.PropertyGroup):
    on: BoolProperty(default=False, options={'HIDDEN'})


def _make_pg():
    ann = {}
    for prop, sock, kind, d, mx in FIELDS:
        if kind == 'c':
            ann[prop] = FloatVectorProperty(name=sock.replace(' Weight', ''), subtype='COLOR', size=3, min=0.0,
                                            soft_max=1.0, default=d, update=_updater(prop))
        else:
            ann[prop] = FloatProperty(name=sock.replace(' Weight', ''), default=d, min=0.0, soft_max=mx,
                                      max=100000.0, update=_updater(prop))
    ann.update(TEX_PROPS)
    MCH_PG_Simple.__annotations__.update(ann)


_make_pg()


class MCH_OT_simple_new(bpy.types.Operator):
    """A new Simple material (a plain Principled BSDF) on the selected meshes (their active slot; a mesh with no
    material gets one)"""
    bl_idname = 'mch.simple_material_new'
    bl_label = 'New Simple Material'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return any(o.type in {'MESH', 'CURVE'} for o in context.selected_objects) or \
            (context.active_object is not None and context.active_object.type in {'MESH', 'CURVE'})

    def execute(self, context):
        obs = [o for o in context.selected_objects if o.type in {'MESH', 'CURVE'}]
        act = context.active_object
        if act is not None and act.type in {'MESH', 'CURVE'} and act not in obs:
            obs.append(act)
        mat = new_material()
        for o in obs:
            if not o.material_slots:
                o.data.materials.append(mat)
            else:
                o.active_material = mat
        self.report({'INFO'}, f'{mat.name} on {len(obs)} object(s)')
        return {'FINISHED'}


class MCH_OT_simple_adopt(bpy.types.Operator):
    """Use the active material here: its Principled node's values read into the Simple settings"""
    bl_idname = 'mch.simple_material_adopt'
    bl_label = 'Use This Material'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return principled(active_material(context)) is not None

    def execute(self, context):
        mat = active_material(context)
        read(mat)
        self.report({'INFO'}, f'{mat.name}: Simple settings')
        return {'FINISHED'}


class MCH_OT_simple_tex_load(bpy.types.Operator):
    """Load a picture onto the Base Color of the active Simple material - its grey makes the Roughness and the Bump
    too (each adjustable below)"""
    bl_idname = 'mch.simple_tex_load'
    bl_label = 'Load Texture'
    bl_options = {'REGISTER', 'UNDO'}
    filepath: StringProperty(subtype='FILE_PATH')
    filter_image: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})
    filter_folder: BoolProperty(default=True, options={'HIDDEN', 'SKIP_SAVE'})

    @classmethod
    def poll(cls, context):
        return is_simple(active_material(context))

    def invoke(self, context, event):
        context.window_manager.fileselect_add(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        mat = active_material(context)
        if not is_simple(mat):
            self.report({'WARNING'}, 'Load Texture: the active object needs a Simple material')
            return {'CANCELLED'}
        try:
            img = bpy.data.images.load(self.filepath, check_existing=True)
        except (RuntimeError, OSError) as ex:
            self.report({'WARNING'}, f'Load Texture: {ex}')
            return {'CANCELLED'}
        st = mat.mch_simple
        ob = context.active_object
        has_uv = ob is not None and ob.type == 'MESH' and len(ob.data.uv_layers) > 0
        st.on = False
        st.tex_proj = 'UV' if has_uv else 'BOX'
        st.on = True
        st.tex_image = img                                 # (builds the nodes)
        try:
            from . import side_panel as sp
            sp.dirty()
        except (ImportError, AttributeError):
            pass
        self.report({'INFO'}, f'{img.name} on {mat.name} ({"UVs" if has_uv else "Box: no UVs"})')
        return {'FINISHED'}


class MCH_OT_simple_tex_remove(bpy.types.Operator):
    """Take the picture off: the Base Color / Roughness sliders back, the bump gone"""
    bl_idname = 'mch.simple_tex_remove'
    bl_label = 'Remove Texture'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        mat = active_material(context)
        return is_simple(mat) and mat.mch_simple.tex_image is not None

    def execute(self, context):
        active_material(context).mch_simple.tex_image = None
        return {'FINISHED'}


def shared_count(mat):
    """How many objects use ``mat`` (in any slot)."""
    if mat is None:
        return 0
    return sum(1 for o in bpy.data.objects if any(sl.material is mat for sl in getattr(o, 'material_slots', ())))


class MCH_OT_simple_single(bpy.types.Operator):
    """Break the material link: each selected object gets its own copy of the active material (changing it no longer
    changes the others)"""
    bl_idname = 'mch.simple_material_single'
    bl_label = 'Break Material Link'
    bl_options = {'REGISTER', 'UNDO'}

    @classmethod
    def poll(cls, context):
        return shared_count(active_material(context)) > 1

    def execute(self, context):
        act = context.active_object
        mat = active_material(context)
        obs = [o for o in context.selected_objects if o.active_material is mat]
        if act is not None and act.active_material is mat and act not in obs:
            obs.append(act)
        if len(obs) >= shared_count(mat):            # (every user selected: one keeps the original - the active one)
            keep = act if act in obs else obs[0]
            obs = [o for o in obs if o is not keep]
        for o in obs:
            o.active_material = mat.copy()
        self.report({'INFO'}, f'{len(obs)} object(s) got their own copy of {mat.name}')
        return {'FINISHED'}


def page(context, x, width, k):
    """(items, content height) - the Simple page of the side panel."""
    from . import mech_shader_ui as mu
    from . import side_panel as sp
    b = sp.Builder(PAGE, x, width, k)
    mat = active_material(context)
    mu.row(b, x, width, [mu.button('New Simple Material', 'mch.simple_material_new')])
    users = shared_count(mat)
    if users > 1:                                    # 0.24.264 (user: "메테리얼 링크 끊는 것도")
        from . import i18n
        txt = (f'"{mat.name}" - 오브젝트 {users} 개가 함께 씀' if i18n.lang() == 'KO'
               else f'"{mat.name}" is shared by {users} objects')
        b.note(('note', txt, True, None, None, None, True), x, width)
        mu.row(b, x, width, [mu.button('Break Material Link', 'mch.simple_material_single')])
    if mat is None:
        b.note(('note', 'Select a mesh: New Simple Material puts a plain Principled material on it', True, None,
                None, None, True), x, width)
        return b.out, -b.y
    if not is_simple(mat):
        if principled(mat) is None:
            b.note(('note', f'"{mat.name}" has no Principled node', True, None, None, None, True), x, width)
            return b.out, -b.y
        b.note(('note', f'"{mat.name}": its Principled values can be set here', True, None, None, None, True), x,
               width)
        mu.row(b, x, width, [mu.button('Use This Material', 'mch.simple_material_adopt')])
        return b.out, -b.y
    st = mat.mch_simple
    b.note(('note', mat.name, False, None, None, None, True), x, width)
    n = principled(mat)
    for key, title, props, folded in GROUPS:
        def fill(sx, sw, props=props):
            for p in props:
                sock = n.inputs.get(_BY[p][1]) if n is not None else None
                if sock is not None and sock.is_linked:
                    b.note(('note', f'{_BY[p][1]}: from a texture', False, None, None, None, True), sx, sw)
                    continue
                mu.row(b, sx, sw, [mu.prop_cell(st, p)])
        mu.section(b, 'simple_' + key, title, x, width, fill, start_folded=folded)
        if key == 'surface':
            texture_section(b, x, width, mat)
    return b.out, -b.y


def texture_section(b, x, width, mat):
    """0.24.345 the Base Color picture and what it drives (Roughness, Bump)."""
    from . import mech_shader_ui as mu
    st = mat.mch_simple

    def fill(sx, sw):
        img = st.tex_image
        if img is None:
            b.note(('note', 'A picture on the Base Color - its grey makes the Roughness and the Bump too', False, None,
                    None, None, True), sx, sw)
            mu.row(b, sx, sw, [mu.button('Load Texture', 'mch.simple_tex_load')])
            return
        b.note(('note', img.name, False, None, None, None, True), sx, sw)
        mu.row(b, sx, sw, [mu.button('Change Texture', 'mch.simple_tex_load'),
                           mu.button('Remove Texture', 'mch.simple_tex_remove')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'tex_proj')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'tex_scale'), mu.prop_cell(st, 'tex_rotation')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'tex_tint')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'tex_bright'), mu.prop_cell(st, 'tex_contrast')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'tex_hue'), mu.prop_cell(st, 'tex_saturation'),
                           mu.prop_cell(st, 'tex_value')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'rough_on')])
        if st.rough_on:
            mu.row(b, sx, sw, [mu.prop_cell(st, 'rough_amount'), mu.prop_cell(st, 'rough_invert')])
            mu.row(b, sx, sw, [mu.prop_cell(st, 'rough_from'), mu.prop_cell(st, 'rough_to')])
        mu.row(b, sx, sw, [mu.prop_cell(st, 'bump_on')])
        if st.bump_on:
            mu.row(b, sx, sw, [mu.prop_cell(st, 'bump_strength'), mu.prop_cell(st, 'bump_distance')])
            mu.row(b, sx, sw, [mu.prop_cell(st, 'bump_invert')])
    mu.section(b, 'simple_texture', 'Texture', x, width, fill, start_folded=False)


CLASSES = (MCH_PG_Simple, MCH_OT_simple_new, MCH_OT_simple_adopt, MCH_OT_simple_single, MCH_OT_simple_tex_load,
           MCH_OT_simple_tex_remove)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    bpy.types.Material.mch_simple = PointerProperty(type=MCH_PG_Simple)


def unregister():
    if hasattr(bpy.types.Material, 'mch_simple'):
        del bpy.types.Material.mch_simple
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
