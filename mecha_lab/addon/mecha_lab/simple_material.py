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
from bpy.props import BoolProperty, FloatProperty, FloatVectorProperty, PointerProperty

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


def page(context, x, width, k):
    """(items, content height) - the Simple page of the side panel."""
    from . import mech_shader_ui as mu
    from . import side_panel as sp
    b = sp.Builder(PAGE, x, width, k)
    mat = active_material(context)
    mu.row(b, x, width, [mu.button('New Simple Material', 'mch.simple_material_new')])
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
    return b.out, -b.y


CLASSES = (MCH_PG_Simple, MCH_OT_simple_new, MCH_OT_simple_adopt)


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
