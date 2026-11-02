"""0.24.95 My Presets (user: picked "내 프리셋 저장 - 만져 놓은 설정을 이름 붙여 저장하고 다시 불러오기"): the Mech Shader's
or the Creature Shader's settings as they are now, saved under a name, and put back on any material of that kind.

Kept in one JSON file in Blender's user config folder (``<config>/mecha_lab/my_presets.json``) - written only when
Save / Delete is pressed - so the presets are there in every .blend.  Each preset: every setting of that shader (the
sliders, colours, maps / textures, the preset names), not the material's own name or the mesh's measurements
(Creature Size is the creature's)."""
from __future__ import annotations

import json
import os

import bpy
from bpy.props import EnumProperty, StringProperty

PATH = [None]                 # (a test points it elsewhere: never the user's own file)
SKIP = {'size'}               # (the creature's own measure, not a look)


def path():
    if PATH[0]:
        return PATH[0]
    d = bpy.utils.user_resource('CONFIG', path='mecha_lab', create=False)    # (made only when saving)
    return os.path.join(d, 'my_presets.json')


_CACHE = {}


def load_all():
    """The saved presets ({kind: {name: settings}}); read again only when the file changed (the side panel asks
    many times a second)."""
    p = path()
    try:
        mtime = os.path.getmtime(p)
    except OSError:
        return {}
    if _CACHE.get('key') != (p, mtime):
        try:
            with open(p, encoding='utf-8') as f:
                data = json.load(f)
        except (OSError, ValueError):
            data = {}
        _CACHE['key'], _CACHE['data'] = (p, mtime), data if isinstance(data, dict) else {}
    return json.loads(json.dumps(_CACHE['data']))


def _write(data):
    p = path()
    os.makedirs(os.path.dirname(p), exist_ok=True)
    tmp = p + '.tmp'
    with open(tmp, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=1, ensure_ascii=False)
    os.replace(tmp, p)
    _CACHE.clear()


def kind_of(context):
    """('mech' | 'creature', the material, its settings, the keys saved) of the active part - or Nones."""
    from . import creature_shader as cs, mech_shader as ms
    mat = cs.active_creature(context)
    if mat is not None:
        st = getattr(mat, cs.KEY)
        keys = [k for k in cs.BASE if k not in SKIP] + ['skin_type', 'condition']
        return 'creature', mat, st, keys, cs
    mat = ms.active_mech(context)
    if mat is not None:
        st = getattr(mat, ms.KEY)
        keys = list(ms.BASE) + ['preset', 'wear_preset']
        return 'mech', mat, st, keys, ms
    return None, None, None, None, None


def names(kind):
    return sorted(load_all().get(kind, {}))


def save(kind, name, st, keys):
    vals = {}
    for k in keys:
        if not hasattr(st, k):
            continue
        v = getattr(st, k)
        vals[k] = list(v) if hasattr(v, '__len__') and not isinstance(v, str) else v
    data = load_all()
    data.setdefault(kind, {})[name] = vals
    _write(data)
    return len(vals)


def apply(kind, name, mat, st, module):
    vals = load_all().get(kind, {}).get(name)
    if vals is None:
        return False
    module._SYNCING[0] = True                  # (one rebuild at the end, the presets' own updates held)
    try:
        for k, v in vals.items():
            if hasattr(st, k):
                try:
                    setattr(st, k, tuple(v) if isinstance(v, list) else v)
                except (TypeError, ValueError):
                    pass                       # (a setting a newer / older version has not: skipped)
    finally:
        module._SYNCING[0] = False
    module.sync(mat)
    return True


def delete(kind, name):
    data = load_all()
    if name in data.get(kind, {}):
        del data[kind][name]
        _write(data)
        return True
    return False


class MCH_OT_my_preset_save(bpy.types.Operator):
    """Save this material's settings as one of My Presets (for every .blend)"""
    bl_idname = 'mch.my_preset_save'
    bl_label = 'Save My Preset'
    bl_options = {'REGISTER'}
    name: StringProperty(name='Name', default='My Preset')

    def invoke(self, context, event):
        kind, _mat, st, _keys, _m = kind_of(context)
        if kind is None:
            self.report({'WARNING'}, 'My Presets: the active part has no Mech / Creature material')
            return {'CANCELLED'}
        base = (st.skin_type if kind == 'creature' else st.preset).replace('_', ' ').title()
        taken = set(names(kind))
        n = 1
        while f'{base} {n}' in taken:
            n += 1
        self.name = f'{base} {n}'
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        kind, _mat, st, keys, _m = kind_of(context)
        if kind is None or not self.name.strip():
            return {'CANCELLED'}
        n = save(kind, self.name.strip(), st, keys)
        self.report({'INFO'}, f'My Presets: "{self.name.strip()}" saved ({n} settings)')
        return {'FINISHED'}


class MCH_OT_my_preset_apply(bpy.types.Operator):
    """Put this saved preset on the material"""
    bl_idname = 'mch.my_preset_apply'
    bl_label = 'Apply My Preset'
    bl_options = {'REGISTER', 'UNDO'}
    name: StringProperty()

    def execute(self, context):
        kind, mat, st, _keys, module = kind_of(context)
        if kind is None or not apply(kind, self.name, mat, st, module):
            self.report({'WARNING'}, f'My Presets: "{self.name}" not found')
            return {'CANCELLED'}
        return {'FINISHED'}


def _delete_items(self, context):
    kind = kind_of(context)[0]
    items = [(n, n, '') for n in names(kind)] if kind else []
    _delete_items.keep = items                 # (Blender keeps only references to the strings)
    return items or [('', '(none)', '')]


class MCH_OT_my_preset_delete(bpy.types.Operator):
    """Delete one of My Presets (of this kind of material)"""
    bl_idname = 'mch.my_preset_delete'
    bl_label = 'Delete My Preset'
    bl_options = {'REGISTER'}
    name: EnumProperty(name='Preset', items=_delete_items)

    def invoke(self, context, event):
        if kind_of(context)[0] is None:
            return {'CANCELLED'}
        return context.window_manager.invoke_props_dialog(self)

    def execute(self, context):
        kind = kind_of(context)[0]
        if not kind or not self.name or not delete(kind, self.name):
            return {'CANCELLED'}
        self.report({'INFO'}, f'My Presets: "{self.name}" deleted')
        return {'FINISHED'}


CLASSES = (MCH_OT_my_preset_save, MCH_OT_my_preset_apply, MCH_OT_my_preset_delete)


def register():
    for c in CLASSES:
        bpy.utils.register_class(c)


def unregister():
    for c in reversed(CLASSES):
        try:
            bpy.utils.unregister_class(c)
        except RuntimeError:
            pass
