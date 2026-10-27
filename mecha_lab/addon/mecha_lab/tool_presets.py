"""0.24.65 Tool Search (Ctrl+F / the Search tile) and Tool Presets (the side panel's Presets section).

Search: type a part of a tool's name, Enter = that tool (any Mecha tool, also ones not on the screen).
Presets: the chosen tool's settings (its numbers, switches and choices on the Scene) saved under a name of your own
and used again - in every file (kept in the add-on's user folder, ``tool_presets.json``), never inside a .blend.
"""
from __future__ import annotations

import json
import os

import bpy
from bpy.props import EnumProperty, StringProperty

from . import tool_state as ts

# tools whose settings group is not simply scene.mch_<tool id>
GROUPS = {'SPLIT': 'mch_cut', 'CUT': 'mch_cut', 'CREATURE': 'mch_wrinkle', 'SKIN': 'mch_wrinkle'}
FILE = 'tool_presets.json'


def group_for(scene, tool):
    """(name, the settings group) of ``tool`` on the Scene, or (None, None)."""
    name = GROUPS.get(tool, 'mch_' + tool.lower())
    pg = getattr(scene, name, None)
    return (name, pg) if isinstance(pg, bpy.types.PropertyGroup) else (None, None)


def _path():
    try:
        d = bpy.utils.extension_path_user(__package__, create=True)
    except (AttributeError, ValueError, TypeError, OSError):
        d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=True)
    return os.path.join(d, FILE)


def _load_all():
    try:
        with open(_path(), encoding='utf-8') as f:
            data = json.load(f)
        return data if isinstance(data, dict) else {}
    except (OSError, ValueError):
        return {}


def _save_all(data):
    path = _path()
    tmp = path + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, sort_keys=True)
    os.replace(tmp, path)


def values(pg):
    """The group's settings as plain values (what undo_keep keeps: numbers, switches, choices)."""
    from .undo_keep import _keys
    out = {}
    for key in _keys(pg):
        v = getattr(pg, key)
        out[key] = list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v
    return out


def names(tool):
    return sorted(_load_all().get(tool, {}))


def save(scene, tool, name):
    _gname, pg = group_for(scene, tool)
    if pg is None:
        return f'{ts.TOOL_BY_ID.get(tool, (tool, tool))[1]} has no settings to save'
    data = _load_all()
    data.setdefault(tool, {})[name] = values(pg)
    _save_all(data)
    return f'Preset "{name}" saved'


def load(scene, tool, name):
    """Use preset ``name`` on the tool's settings (as if you set each one: live parts follow)."""
    _gname, pg = group_for(scene, tool)
    vals = _load_all().get(tool, {}).get(name)
    if pg is None or vals is None:
        return f'No preset "{name}"'
    for key, v in vals.items():
        if key in pg.bl_rna.properties and not pg.bl_rna.properties[key].is_readonly:
            try:
                setattr(pg, key, v)
            except (TypeError, ValueError, AttributeError):
                pass                                 # (a choice that no longer exists)
    return f'Preset "{name}"'


def delete(tool, name):
    data = _load_all()
    if data.get(tool, {}).pop(name, None) is None:
        return f'No preset "{name}"'
    _save_all(data)
    return f'Preset "{name}" deleted'


def _tool_items(self, context):
    _TOOL_ITEMS[:] = [(t[0], t[1], t[2]) for t in ts.TOOLS]
    return _TOOL_ITEMS


_TOOL_ITEMS = []
_PRESET_ITEMS = []


def _preset_items(self, context):
    _PRESET_ITEMS[:] = [(n, n, '') for n in names(ts.effective_tool(context))] or [('', '(no presets yet)', '')]
    return _PRESET_ITEMS


class MCH_OT_tool_search(bpy.types.Operator):
    """Search a Mecha tool by name (type a part of it, Enter picks it)"""
    bl_idname = 'mch.tool_search'
    bl_label = 'Search Tools'
    bl_options = {'INTERNAL'}
    bl_property = 'tool'
    tool: EnumProperty(name='Tool', items=_tool_items)

    @classmethod
    def poll(cls, context):
        return getattr(context, 'mode', '') == 'OBJECT'

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        from .workspace_ui import activate_mecha_tool
        activate_mecha_tool(context, self.tool)
        self.report({'INFO'}, ts.TOOL_BY_ID.get(self.tool, (self.tool, self.tool))[1])
        return {'FINISHED'}


class MCH_OT_tool_preset_save(bpy.types.Operator):
    """Save the chosen tool's settings as a preset of your own (kept for every file)"""
    bl_idname = 'mch.tool_preset_save'
    bl_label = 'Save Preset'
    bl_options = {'INTERNAL'}
    name: StringProperty(name='Name', default='My Preset')

    def invoke(self, context, event):
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        self.report({'INFO'}, save(context.scene, ts.effective_tool(context), self.name.strip() or 'Preset'))
        return {'FINISHED'}


class MCH_OT_tool_preset_load(bpy.types.Operator):
    """Use one of your presets on the chosen tool"""
    bl_idname = 'mch.tool_preset_load'
    bl_label = 'Load Preset'
    bl_options = {'REGISTER', 'UNDO', 'INTERNAL'}
    bl_property = 'name'
    name: EnumProperty(name='Preset', items=_preset_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.name:
            self.report({'INFO'}, load(context.scene, ts.effective_tool(context), self.name))
        return {'FINISHED'}


class MCH_OT_tool_preset_delete(bpy.types.Operator):
    """Delete one of your presets of the chosen tool"""
    bl_idname = 'mch.tool_preset_delete'
    bl_label = 'Delete Preset'
    bl_options = {'INTERNAL'}
    bl_property = 'name'
    name: EnumProperty(name='Preset', items=_preset_items)

    def invoke(self, context, event):
        context.window_manager.invoke_search_popup(self)
        return {'RUNNING_MODAL'}

    def execute(self, context):
        if self.name:
            self.report({'INFO'}, delete(ts.effective_tool(context), self.name))
        return {'FINISHED'}


def draw_presets(layout, context, tool):
    """The side panel's Presets section (only for a tool with settings)."""
    if group_for(context.scene, tool)[1] is None:
        return
    row = layout.row(align=True)
    row.operator('mch.tool_preset_load', text='Load')
    row.operator('mch.tool_preset_save', text='Save')
    row.operator('mch.tool_preset_delete', text='Delete')
    n = len(names(tool))
    layout.label(text=f'{n} preset(s) of yours for this tool' if n else 'No presets yet: Save keeps these settings')


CLASSES = (MCH_OT_tool_search, MCH_OT_tool_preset_save, MCH_OT_tool_preset_load, MCH_OT_tool_preset_delete)
_keymaps = []


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is not None:                               # Ctrl+F: Tool Search (Object Mode has no Ctrl+F of its own)
        km = kc.keymaps.new(name='Object Mode', space_type='EMPTY')
        _keymaps.append((km, km.keymap_items.new('mch.tool_search', 'F', 'PRESS', ctrl=True)))


def unregister():
    for km, kmi in _keymaps:
        try:
            km.keymap_items.remove(kmi)
        except Exception:
            pass
    _keymaps.clear()
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
