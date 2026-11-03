"""0.24.95 Over My Material (user: "내가 이미 만들어 놓은 메테리얼에 우리가 만든 메테리얼 연결해서 그 위에 우리가 만든
재질 얹어서 사용할 수 있게"): the Mech / Creature Shader laid over a material the user made themselves.

The user's material is not touched: a copy of it is made ("<name> + Mech"), their nodes kept in it as they are, and
our shader built next to them.  What fed their Material Output (the surface shader, the volume, the displacement) is
remembered; one Mix Shader then shows their surface where nothing of ours covers it and our shader where a layer does:

* Mech - their material is the coat: Edge Wear chips and Scratches cut through it to the metal under it (the Surface
  section: colour / metallic / roughness / maps), the primer band round the chips (Primer), and rust, dirt, dust, rain
  streaks, snow sit on top; Glow adds its light over it; a lasso Zone paints over it
* Creature - their material is the skin: mud, dust, soot, snow, frost, moss, blood (fresh and dried), slime, scars,
  rot sit on top; Glow adds its light

Their nodes are kept when the shader is made anew (every node not theirs is ours); "Back to Mine" puts their own
material back on the selected parts."""
from __future__ import annotations

import json

import bpy

OVER = 'mch_over'                  # on our material: 1 = laid over the user's own material (its nodes in it)
SRC = 'mch_over_src'               # the user's material it was made from (its name)
NODES = 'mch_over_nodes'           # the user's nodes (JSON list of names) - kept when ours are made anew
SOCKS = 'mch_over_socks'           # what fed their Material Output (JSON {input: [node, output identifier]})
KINDS = (('MECH', 'Mech', 'The Mech Shader over it: chips / scratches through it, rust, dirt, snow on top'),
         ('CREATURE', 'Creature', 'The Creature Shader over it: mud, dust, blood, slime, snow ... on top'))
DEFAULT_MECH = 'DIRTY'             # (shows at once over any material - low-poly too: dirt in the crevices, scratches)
DEFAULT_COND = 'SWAMP'


def is_over(mat):
    return mat is not None and bool(mat.get(OVER))


def is_ours(mat):
    """A material the Mech / Creature / eye shader made, or a decal's."""
    if mat is None:
        return False
    from . import creature_shader as cs
    from . import mech_shader as ms
    return ms.is_mech(mat) or cs.is_creature(mat) or cs.is_eye(mat) or bool(mat.get('mch_decal'))


def user_material(context):
    """The active part's own material (one we did not make), or None."""
    ob = getattr(context, 'active_object', None)
    mat = getattr(ob, 'active_material', None) if ob is not None and ob.type == 'MESH' else None
    return None if mat is None or is_ours(mat) else mat


def source_of(mat):
    return bpy.data.materials.get(mat.get(SRC, '')) if is_over(mat) else None


# --- inside a build ----------------------------------------------------------------------------------------------

def clear_ours(mat):
    """Before our shader is made: the tree emptied - but over the user's material only our nodes go (theirs stay).
    True when it is over theirs."""
    nt = mat.node_tree
    if not is_over(mat):
        nt.nodes.clear()
        return False
    keep = set(_names(mat))
    for nd in list(nt.nodes):
        if nd.name not in keep:
            nt.nodes.remove(nd)
    return True


def origin(mat):
    """Where our nodes start: to the right of the user's."""
    nodes = [nd for nd in mat.node_tree.nodes if nd.bl_idname != 'NodeFrame']
    if not nodes:
        return (0.0, 0.0)
    return (max(nd.location.x + nd.width for nd in nodes) + 400.0, max(nd.location.y for nd in nodes))


def user_socket(mat, which):
    """The output of the user's node that fed their Material Output's ``which`` (Surface / Volume / Displacement)."""
    try:
        entry = json.loads(mat.get(SOCKS, '{}')).get(which)
    except (TypeError, ValueError):
        return None
    if not entry:
        return None
    nd = mat.node_tree.nodes.get(entry[0])
    if nd is None:
        return None
    return next((s for s in nd.outputs if s.identifier == entry[1]), None)


def finish(b, mat, out, bsdf, vis, glow_color=None, glow_strength=None):
    """The output: their surface where ``vis`` (1) - ours elsewhere - + our glow over it; their volume /
    displacement as they had them.  False (ours alone) when their surface node is gone."""
    surf = user_socket(mat, 'Surface')
    if surf is None:
        return False
    mix = b.node('ShaderNodeMixShader', 'mch:over_mix')
    b.link(vis, mix.inputs[0])
    b.link(bsdf.outputs['BSDF'], mix.inputs[1])
    b.link(surf, mix.inputs[2])
    res = mix.outputs[0]
    if glow_color is not None:
        em = b.node('ShaderNodeEmission', 'mch:over_glow')
        b.put(em.inputs['Color'], glow_color)
        b.link(b.math('MULTIPLY', glow_strength, vis), em.inputs['Strength'])
        add = b.node('ShaderNodeAddShader', 'mch:over_add')
        b.link(res, add.inputs[0])
        b.link(em.outputs[0], add.inputs[1])
        res = add.outputs[0]
    b.link(res, out.inputs['Surface'])
    for which in ('Volume', 'Displacement'):
        s = user_socket(mat, which)
        if s is not None:
            b.link(s, out.inputs[which])
    return True


def keep_not(b, *masks):
    """1 where none of ``masks`` (sockets or (socket, weight)) covers: the product of (1 - each)."""
    out = None
    for m in masks:
        if isinstance(m, tuple):
            m = b.math('MULTIPLY', m[0], m[1])
        t = b.math('SUBTRACT', 1.0, m, clamp=True)
        out = t if out is None else b.math('MULTIPLY', out, t)
    return out


def _names(mat):
    try:
        return json.loads(mat.get(NODES, '[]'))
    except (TypeError, ValueError):
        return []


# --- making one ----------------------------------------------------------------------------------------------------

def make(src, kind):
    """A copy of the user's material ``src`` ready for our shader of ``kind`` (their nodes in it, their outputs
    remembered, their Material Output nodes gone - ours takes their place).  Nothing of ``src`` changes."""
    mat = src.copy()
    mat.name = f'{src.name} + {"Mech" if kind == "MECH" else "Creature"}'
    if mat.node_tree is None:
        mat.use_nodes = True
    nt = mat.node_tree
    outs = [nd for nd in nt.nodes if nd.bl_idname == 'ShaderNodeOutputMaterial']
    act = next((nd for nd in outs if getattr(nd, 'is_active_output', False)), outs[0] if outs else None)
    socks = {}
    if act is not None:
        for name in ('Surface', 'Volume', 'Displacement'):
            s = act.inputs.get(name)
            if s is not None and s.is_linked:
                lk = s.links[0]
                socks[name] = [lk.from_node.name, lk.from_socket.identifier]
    if 'Surface' not in socks:                       # (nothing fed it: their base colour as a plain surface)
        col = tuple(getattr(src, 'diffuse_color', (0.8, 0.8, 0.8, 1.0)))
        bs = nt.nodes.new('ShaderNodeBsdfPrincipled')
        bs.name = 'Your Surface'
        bs.inputs['Base Color'].default_value = col
        socks['Surface'] = [bs.name, 'BSDF']
    for nd in outs:
        nt.nodes.remove(nd)
    mat[NODES] = json.dumps([nd.name for nd in nt.nodes])
    mat[SOCKS] = json.dumps(socks)
    mat[SRC] = src.name
    mat[OVER] = 1
    return mat


def put_on(context, objs, src, mat):
    """``mat`` in place of ``src`` on every slot of ``objs`` that holds it; their edges / crevices measured.  How
    many parts."""
    from . import mech_shader as ms
    n = 0
    for ob in objs:
        if ob is None or ob.type != 'MESH':
            continue
        hit = False
        for sl in ob.material_slots:
            if sl.material == src:
                sl.material = mat
                hit = True
        if not hit:
            continue
        mode = ob.mode
        try:
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='OBJECT')
            ms.store_curvature(ob.data)
        finally:
            if mode == 'EDIT':
                bpy.ops.object.mode_set(mode='EDIT')
        n += 1
    return n


class MCH_OT_material_over(bpy.types.Operator):
    """Lay the Mech / Creature Shader over the active part's own material: a copy of it (yours stays as it is) with
    ours on top - chips, scratches, rust, dirt, snow (Mech) or mud, dust, blood, slime (Creature); the selected parts
    that have your material get it"""
    bl_idname = 'mch.material_over'
    bl_label = 'Layer Over My Material'
    bl_options = {'REGISTER', 'UNDO'}
    kind: bpy.props.EnumProperty(items=KINDS, default='MECH')
    preset: bpy.props.StringProperty(default='', description='Mech: the material preset; Creature: the condition')

    def execute(self, context):
        from . import creature_shader as cs
        from . import mech_shader as ms
        src = user_material(context)
        if src is None:
            self.report({'WARNING'}, 'Over My Material: the active part needs a material of your own')
            return {'CANCELLED'}
        obs = ms._targets(context)
        mat = make(src, self.kind)
        if self.kind == 'MECH':
            ms.build(mat)
            ms.apply_preset(mat, self.preset if self.preset in ms.PRESET_IDS else DEFAULT_MECH)
        else:
            cs.build(mat)
            st = getattr(mat, cs.KEY)
            cs.apply_skin(mat, context.scene.mch_creature_skin)
            cs.apply_condition(mat, self.preset if self.preset in cs.COND_IDS else DEFAULT_COND)
            st.size = cs.body_size(obs)
        n = put_on(context, obs, src, mat)
        src.use_fake_user = True                     # (no part uses yours now: kept in the file for Back to Mine)
        ms._look(context)
        self.report({'INFO'}, f'"{mat.name}": the {"Mech" if self.kind == "MECH" else "Creature"} Shader over '
                              f'"{src.name}" on {n} part(s) ("{src.name}" itself unchanged)')
        return {'FINISHED'}


class MCH_OT_material_over_back(bpy.types.Operator):
    """Your own material back on the selected parts (the one this was laid over)"""
    bl_idname = 'mch.material_over_back'
    bl_label = 'Back to My Material'
    bl_options = {'REGISTER', 'UNDO'}

    def execute(self, context):
        from . import mech_shader as ms
        ob = getattr(context, 'active_object', None)
        mat = getattr(ob, 'active_material', None) if ob is not None else None
        src = source_of(mat)
        if src is None:
            self.report({'WARNING'}, 'Back to Mine: this material is not laid over one of yours (or yours is gone)')
            return {'CANCELLED'}
        n = 0
        for o in ms._targets(context):
            for sl in o.material_slots:
                if sl.material == mat:
                    sl.material = src
                    n += 1
        self.report({'INFO'}, f'"{src.name}" back on {n} slot(s)')
        return {'FINISHED'}


CLASSES = (MCH_OT_material_over, MCH_OT_material_over_back)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
