"""0.24.82 Hotkey conflict check: which Blender keys the Mecha hotkeys sit on top of.

Every Mecha key lives in the add-on keyconfig; Blender looks there first, so a Mecha key that is the same key +
modifiers in the same keymap ('Object Mode', '3D View', 'Sculpt' ...) as a Blender key shadows it - but only
while the Mecha operator's poll says yes (most are MECHA LAB only, or 'nothing selected' only), the rest of the
time the Blender key works as before.  ``conflicts`` lists them: (Mecha item, the Blender item it shadows, keymap
name) against the user's keyconfig (what the keys do right now) and Blender's default one.  Shown by
Preferences > Hotkeys > Check Conflicts and by the self test.  ``same_key`` / ``describe`` are pure.
"""
from __future__ import annotations

import bpy

MODS = ('ctrl', 'alt', 'shift', 'oskey')


def same_key(a, b):
    """Two keymap items fire on the same press: key, value (PRESS / CLICK_DRAG / ...), modifiers, key_modifier."""
    if a.type != b.type or a.type == 'NONE':
        return False
    if a.value != b.value and 'ANY' not in (a.value, b.value):
        return False
    for m in MODS:
        va, vb = getattr(a, m), getattr(b, m)
        if va in (-1, True) and vb in (-1, True):      # (-1 = any, since 4.x an int)
            continue
        if bool(va) != bool(vb):
            return False
    return (a.key_modifier or 'NONE') == (b.key_modifier or 'NONE')


def describe(item):
    """'Shift+D' / 'D + LMB' for a keymap item."""
    mods = [n.title() if n != 'oskey' else 'OS' for n in MODS if getattr(item, n) not in (0, False, -1)]
    mouse = {'LEFTMOUSE': 'LMB', 'RIGHTMOUSE': 'RMB', 'MIDDLEMOUSE': 'MMB'}
    key = mouse.get(item.type) or (item.type.replace('_', ' ').title() if len(item.type) > 1 else item.type)
    if item.key_modifier and item.key_modifier != 'NONE':
        mods.append(item.key_modifier)
    out = '+'.join(mods + [key])
    if item.value not in ('PRESS', 'ANY'):
        out += f' ({item.value.lower().replace("_", " ")})'
    return out


def _mecha_items():
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    out = []
    if kc is None:
        return out
    for km in kc.keymaps:
        for item in km.keymap_items:
            if item.idname.startswith('mch.') and item.active and item.type != 'NONE':
                out.append((km.name, item))
    return out


def conflicts(which='user'):
    """[(keymap name, Mecha item, Blender item)] - the Blender keys Mecha keys shadow in the 'user' keyconfig
    (what runs now), Blender's 'default' one, or a keyconfig given directly."""
    wm = bpy.context.window_manager
    kc = which if not isinstance(which, str) else (getattr(wm.keyconfigs, which, None) if wm else None)
    out = []
    if kc is None:
        return out
    for km_name, item in _mecha_items():
        km = kc.keymaps.get(km_name)
        if km is None:
            continue
        for other in km.keymap_items:
            if other.idname.startswith('mch.') or not other.active or other.idname == '':
                continue
            if same_key(item, other):
                out.append((km_name, item, other))
    return out


def lines(which='user'):
    """Readable lines: 'Object Mode  Shift+D  mch.duplicate  shadows  object.duplicate_move'."""
    out = []
    for km_name, item, other in conflicts(which):
        action = ''
        try:
            if item.idname == 'mch.hotkey':
                action = f' ({item.properties.action}{" " + item.properties.tool if item.properties.tool else ""})'
        except (AttributeError, TypeError):
            pass
        out.append(f'{km_name}: {describe(item)}  {item.idname}{action}  shadows  {other.idname}')
    return out


class MCH_OT_hotkeys_check(bpy.types.Operator):
    """List the Blender keys the Mecha hotkeys sit on top of (they only win while their tool / workspace applies)"""
    bl_idname = 'mch.hotkeys_check'
    bl_label = 'Check Conflicts'

    def execute(self, context):
        found = lines('user')
        self._lines = found
        if not found:
            self.report({'INFO'}, 'Hotkeys: no Mecha key sits on a Blender key in the same keymap')
            return {'FINISHED'}
        try:
            context.window_manager.clipboard = '\n'.join(found)
        except (AttributeError, RuntimeError):
            pass
        print('[Mecha Lab] hotkey conflicts:\n  ' + '\n  '.join(found))
        self.report({'WARNING'}, f'{len(found)} Mecha key(s) sit on Blender keys (list copied to the clipboard, '
                                 f'and in the console): ' + '; '.join(found[:3]))
        return {'FINISHED'}


def draw(layout, context):
    row = layout.row(align=True)
    row.operator('mch.hotkeys_check', icon='VIEWZOOM')
    n = len(conflicts('user'))
    row.label(text=f'{n} on Blender keys' if n else 'no conflicts', icon='INFO' if n else 'CHECKMARK')


def register():
    bpy.utils.register_class(MCH_OT_hotkeys_check)


def unregister():
    bpy.utils.unregister_class(MCH_OT_hotkeys_check)
