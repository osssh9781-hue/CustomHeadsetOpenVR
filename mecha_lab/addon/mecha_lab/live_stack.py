"""0.24.82 Live Stack: the live things on the selected part, in the order they are applied.

Mirror / Radial (the symmetry card), Box Hide, Armor Shell, the Hard Edges bevel + Subdivide, Cloth Plate, High
Poly Subdivide, a GN Edge ... are all ordinary Blender modifiers named ``MCH_...``.  This card lists them (plus
any other modifier) on the active part in stack order with a plain name, and lets you: hide / show one (the eye),
move it up / down, **Apply** one (a Mecha tool's own Apply when it has one, so its records are tidied too), remove
one, Apply All.  No stack engine of its own: Blender's modifiers stay the truth, undo stays Blender's.

Shown in the Layers panel (a section) and N > Mecha Lab.  ``entries`` / ``label`` / ``warnings`` are pure (tested
headless); the operators use Blender's modifier operators with an override on the part.
"""
from __future__ import annotations

import bpy

# modifier name (or its start) -> (plain name, the tool module whose apply(context, ob) bakes it, or None)
NAMES = (
    ('MCH_BoxHide', 'Box Hide', 'box_hide'),
    ('MCH_ArmorShell', 'Armor Shell', 'armor_shell'),
    ('MCH_Symmetry', 'Mirror', 'symmetry'),
    ('MCH_HE_Bevel', 'Edge Bevel (Hard Edges)', None),
    ('MCH_HE_Subdivide', 'Edge Subdivide (Hard Edges)', None),
    ('MCH_HE_Normals', 'Edge Normals (Hard Edges)', None),
    ('MCH_HE_Fit', 'Fit to Original (Edge Mesh)', None),
    ('MCH_HP_Subdiv', 'High Poly Subdivide', None),
    ('MCH_Wrinkle', 'Cloth Plate', None),
    ('MCH_FoldPatch', 'Fold Patch', None),
    ('MCH_Perforate', 'Perforate', None),
    ('MCH_PanelCloth', 'Panel Cloth', None),
    ('MCH_VoxelRemesh', 'Voxel Remesh', None),
    ('MCH_Union', 'Union', None),
    ('MCH_Shell', 'Shell', None),
    ('MCH_RobotBevel', 'Robot Bevel', None),
    ('MCH_Subsurf', 'Subdivide', None),
)
TYPE_NAMES = {'MIRROR': 'Mirror', 'ARRAY': 'Array', 'BEVEL': 'Bevel', 'SUBSURF': 'Subdivide', 'BOOLEAN': 'Boolean',
              'NODES': 'Geometry Nodes', 'SOLIDIFY': 'Solidify', 'SHRINKWRAP': 'Shrinkwrap', 'REMESH': 'Remesh',
              'WEIGHTED_NORMAL': 'Weighted Normals', 'TRIANGULATE': 'Triangulate', 'DISPLACE': 'Displace',
              'SMOOTH': 'Smooth', 'DECIMATE': 'Decimate', 'WIREFRAME': 'Wireframe', 'SCREW': 'Screw'}


def _symmetry_names():
    try:
        from . import mirror_tools, radial_sym
        return {mirror_tools.MOD_NAME: ('Mirror', 'symmetry'), radial_sym.MOD_NAME: ('Radial', 'symmetry')}
    except (ImportError, AttributeError):
        return {}


def label(mod):
    """A plain name for a modifier: 'Box Hide', 'Mirror', 'Edge Bevel (Hard Edges)', else its own name."""
    sym = _symmetry_names()
    if mod.name in sym:
        return sym[mod.name][0]
    for start, name, _tool in NAMES:
        if mod.name == start or mod.name.startswith(start):
            return name
    if mod.name.startswith('MCH_'):
        return mod.name[4:].replace('_', ' ')
    base = TYPE_NAMES.get(mod.type, mod.type.title().replace('_', ' '))
    return mod.name if mod.name.lower().startswith(base.lower()) else f'{mod.name} ({base})'


def tool_of(mod):
    """The Mecha module whose apply(context, ob) bakes this modifier (None: Blender's apply)."""
    sym = _symmetry_names()
    if mod.name in sym:
        return sym[mod.name][1]
    for start, _name, tool in NAMES:
        if tool and (mod.name == start or mod.name.startswith(start)):
            return tool
    return None


def entries(ob):
    """[(modifier, plain name, shown?)] in stack order (top = applied first), or []."""
    if ob is None or ob.type != 'MESH':
        return []
    return [(m, label(m), bool(m.show_viewport)) for m in ob.modifiers]


def warnings(ob):
    """Short notes on the order (what a user asks about most): nothing fatal, just what it means."""
    out = []
    names = [m.name for m in ob.modifiers] if ob is not None and ob.type == 'MESH' else []
    sym = set(_symmetry_names()) | {'MCH_Symmetry'}

    def idx(pred):
        return next((i for i, n in enumerate(names) if pred(n)), None)
    i_mirror = idx(lambda n: n in sym)
    i_hide = idx(lambda n: n == 'MCH_BoxHide')
    i_shell = idx(lambda n: n == 'MCH_ArmorShell')
    i_sub = idx(lambda n: n in {'MCH_HE_Subdivide', 'MCH_HP_Subdiv'} or (ob.modifiers[n].type == 'SUBSURF'))
    i_bool = idx(lambda n: ob.modifiers[n].type == 'BOOLEAN')
    if i_mirror is not None and i_hide is not None and i_mirror < i_hide:
        out.append('Mirror before Box Hide: both sides are hidden (Follow Symmetry)')
    if i_mirror is not None and i_hide is not None and i_hide < i_mirror:
        out.append('Box Hide before Mirror: the hidden result is mirrored')
    if i_sub is not None and i_bool is not None and i_sub < i_bool:
        out.append('Subdivide before a Boolean: the boolean works on the dense mesh (slow)')
    if i_shell is not None and i_shell != len(names) - 1:
        out.append('Armor Shell is not last: what comes after shapes the shell, not the part')
    return out


def _override(context, ob):
    return context.temp_override(object=ob, active_object=ob, selected_objects=[ob], selected_editable_objects=[ob])


def apply_one(context, ob, name):
    """Bake one modifier into the mesh (the tool's own apply when it has one).  Returns a short note."""
    mod = ob.modifiers.get(name)
    if mod is None:
        return 'gone'
    tool = tool_of(mod)
    if tool:
        import importlib
        m = importlib.import_module(f'{__package__}.{tool}')
        try:
            m.apply(context, ob)
            if ob.modifiers.get(name) is None:
                return f'{label(mod)} applied'
        except Exception as ex:                       # the tool could not: Blender's apply below
            print('Live Stack:', tool, 'apply:', ex)
    was = mod.show_viewport
    mod.show_viewport = True
    with _override(context, ob):
        r = bpy.ops.object.modifier_apply(modifier=name)
    if 'FINISHED' not in r:
        mod.show_viewport = was
        return 'could not apply'
    return 'applied'


def apply_all(context, ob):
    n = 0
    while ob.modifiers:
        first = ob.modifiers[0].name
        note = apply_one(context, ob, first)
        if ob.modifiers.get(first) is not None:
            raise RuntimeError(f'{label(ob.modifiers[first])}: {note}')
        n += 1
    return n


class _Stack(bpy.types.Operator):
    bl_options = {'REGISTER', 'UNDO'}
    name: bpy.props.StringProperty()

    @classmethod
    def poll(cls, context):
        ob = context.active_object
        return ob is not None and ob.type == 'MESH' and context.mode == 'OBJECT'

    def _ob(self, context):
        return context.active_object


class MCH_OT_stack_toggle(_Stack):
    """Show / hide this live step in the viewport (it stays in the stack)"""
    bl_idname = 'mch.stack_toggle'
    bl_label = 'Show / Hide'

    def execute(self, context):
        ob = self._ob(context)
        mod = ob.modifiers.get(self.name)
        if mod is None:
            return {'CANCELLED'}
        mod.show_viewport = not mod.show_viewport
        mod.show_render = mod.show_viewport
        return {'FINISHED'}


class MCH_OT_stack_move(_Stack):
    """Move this live step up (applied earlier) or down (later) in the stack"""
    bl_idname = 'mch.stack_move'
    bl_label = 'Move'
    step: bpy.props.IntProperty(default=1)

    def execute(self, context):
        ob = self._ob(context)
        mod = ob.modifiers.get(self.name)
        if mod is None:
            return {'CANCELLED'}
        i = list(ob.modifiers).index(mod)
        j = max(0, min(len(ob.modifiers) - 1, i + self.step))
        if j == i:
            return {'CANCELLED'}
        with _override(context, ob):
            bpy.ops.object.modifier_move_to_index(modifier=self.name, index=j)
        for w in warnings(ob):
            self.report({'INFO'}, w)
        return {'FINISHED'}


class MCH_OT_stack_apply(_Stack):
    """Bake this live step into the mesh (a Mecha tool's own Apply when it has one)"""
    bl_idname = 'mch.stack_apply'
    bl_label = 'Apply'

    def execute(self, context):
        ob = self._ob(context)
        try:
            note = apply_one(context, ob, self.name)
        except (RuntimeError, ReferenceError) as ex:
            from . import toast
            toast.report(self, 'ERROR', f'Apply: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Live Stack: {note}')
        return {'FINISHED'}


class MCH_OT_stack_remove(_Stack):
    """Remove this live step (the part goes back to before it)"""
    bl_idname = 'mch.stack_remove'
    bl_label = 'Remove'

    def execute(self, context):
        ob = self._ob(context)
        mod = ob.modifiers.get(self.name)
        if mod is None:
            return {'CANCELLED'}
        name = label(mod)
        with _override(context, ob):
            bpy.ops.object.modifier_remove(modifier=self.name)
        self.report({'INFO'}, f'Live Stack: {name} removed')
        return {'FINISHED'}


class MCH_OT_stack_apply_all(_Stack):
    """Bake every live step into the mesh, in stack order"""
    bl_idname = 'mch.stack_apply_all'
    bl_label = 'Apply All'

    def execute(self, context):
        ob = self._ob(context)
        try:
            n = apply_all(context, ob)
        except (RuntimeError, ReferenceError) as ex:
            from . import toast
            toast.report(self, 'ERROR', f'Apply All stopped: {ex}')
            return {'CANCELLED'}
        self.report({'INFO'}, f'Live Stack: {n} step{"s" if n != 1 else ""} applied')
        return {'FINISHED'}


def draw(layout, context):
    """The card's rows (normal layout code: the Layers panel turns it into drawn rows, the N panel shows it)."""
    ob = context.active_object
    box = layout.box()
    box.label(text='LIVE STACK', icon='MODIFIER_ON')
    rows = entries(ob)
    if ob is None or ob.type != 'MESH':
        box.label(text='Select a part', icon='INFO')
        return
    if not rows:
        box.label(text=f'{ob.name}: nothing live (a plain mesh)', icon='INFO')
        return
    for i, (mod, name, shown) in enumerate(rows):
        row = box.row(align=True)
        row.operator('mch.stack_toggle', text='', icon='HIDE_OFF' if shown else 'HIDE_ON', depress=shown).name = mod.name
        row.label(text=f'{i + 1}. {name}')
        op = row.operator('mch.stack_move', text='', icon='TRIA_UP')
        op.name, op.step = mod.name, -1
        op = row.operator('mch.stack_move', text='', icon='TRIA_DOWN')
        op.name, op.step = mod.name, 1
        row.operator('mch.stack_apply', text='', icon='CHECKMARK').name = mod.name
        row.operator('mch.stack_remove', text='', icon='X').name = mod.name
    for w in warnings(ob):
        box.label(text=w, icon='INFO')
    box.operator('mch.stack_apply_all', text=f'Apply All ({len(rows)})', icon='CHECKMARK')


CLASSES = (MCH_OT_stack_toggle, MCH_OT_stack_move, MCH_OT_stack_apply, MCH_OT_stack_remove, MCH_OT_stack_apply_all)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        bpy.utils.unregister_class(c)
