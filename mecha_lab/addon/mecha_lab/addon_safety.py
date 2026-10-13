"""Registration hygiene (B09: "MCH_PG_Brush already registered").

That error means Mecha Lab classes were still registered when the add-on was
enabled: a previous version whose unregister() stopped half-way, a reload
after an exception, or a SECOND copy of Mecha Lab enabled at the same time
(old legacy add-on ``mecha_lab`` + extension ``bl_ext.*.mecha_lab``).  When
register() then raises half-way, everything registered after the failing
class is missing (sub-panels such as Mirror, keymaps, tools), which looks like
unrelated features being "dead".

``purge_stale`` removes every leftover Mecha Lab registration before register
(classes, runtime ``mch_*`` properties, app handlers, header/menu draw
functions, ``mch.*`` add-on keymap items, ``mecha.*`` workspace tools) and
remembers foreign copies so the UI can tell the user to disable them.
``run_steps`` runs unregister steps without stopping at the first error.
"""
from __future__ import annotations

import traceback

import bpy

PREFIXES = ('MCH_', 'MECHA_')
PROP_OWNERS = ('Scene', 'Object', 'WindowManager', 'Mesh', 'Curve', 'Lattice', 'Collection', 'Material')
UI_TYPES = ('VIEW3D_HT_tool_header', 'TOPBAR_MT_workspace_menu', 'VIEW3D_MT_add', 'VIEW3D_MT_mesh_add',
            'VIEW3D_HT_header', 'VIEW3D_MT_object_context_menu')

FOREIGN = []        # module names of other Mecha Lab copies found at register time
LAST_ERRORS = []    # messages from the last tolerant unregister


_ONLY = None   # restrict purges to this module prefix (unregister of one copy)


def _is_mecha_module(name):
    name = name or ''
    if _ONLY is not None:
        return name.startswith(_ONLY)
    return 'mecha_lab' in name


_BASES = ('Operator', 'Panel', 'Menu', 'Header', 'UIList', 'PropertyGroup', 'AddonPreferences',
          'GizmoGroup', 'Gizmo', 'Macro')


def _subclasses(base):
    out, todo = [], list(base.__subclasses__())
    while todo:
        c = todo.pop()
        out.append(c)
        todo.extend(c.__subclasses__())
    return out


def is_registered(cls):
    """Registered classes carry their own ``bl_rna`` (GizmoGroup has no
    ``is_registered`` attribute, so that cannot be used)."""
    try:
        return cls.__dict__.get('bl_rna') is not None
    except (AttributeError, ReferenceError):
        return False


def registered_mecha_classes():
    """Every registered class from a Mecha Lab module (also stale class
    objects of an older import, which ``dir(bpy.types)`` may not list)."""
    found = []
    for base_name in _BASES:
        base = getattr(bpy.types, base_name, None)
        if base is None:
            continue
        for cls in _subclasses(base):
            if cls in found or not _is_mecha_module(getattr(cls, '__module__', '')):
                continue
            if is_registered(cls):
                found.append(cls)
    return found


def _purge_classes():
    removed = []

    def order(cls):
        if getattr(cls, 'bl_parent_id', ''):
            return 0          # child panels before their parent
        if issubclass(cls, bpy.types.PropertyGroup):
            return 2          # property groups last (others may point at them)
        return 1
    for _round in range(3):   # nested PropertyGroups may need a second pass
        left = sorted(registered_mecha_classes(), key=order)
        if not left:
            break
        for cls in left:
            try:
                bpy.utils.unregister_class(cls)
                removed.append(cls.__name__)
            except (RuntimeError, ValueError):
                pass
    return removed


def _purge_props():
    removed = []
    for owner_name in PROP_OWNERS:
        owner = getattr(bpy.types, owner_name, None)
        if owner is None:
            continue
        for prop in list(owner.bl_rna.properties):
            ident = prop.identifier
            if ident.startswith('mch_') and prop.is_runtime:
                try:
                    delattr(owner, ident)
                    removed.append(f'{owner_name}.{ident}')
                except (AttributeError, RuntimeError, TypeError):
                    pass
    return removed


def _purge_handlers():
    removed = 0
    for name in dir(bpy.app.handlers):
        lst = getattr(bpy.app.handlers, name)
        if not isinstance(lst, list):
            continue
        for fn in list(lst):
            if _is_mecha_module(getattr(fn, '__module__', '')):
                lst.remove(fn)
                removed += 1
    return removed


def _purge_draw_funcs():
    removed = 0
    for tname in UI_TYPES:
        t = getattr(bpy.types, tname, None)
        if t is None or not hasattr(t, '_dyn_ui_initialize'):
            continue
        try:
            funcs = t._dyn_ui_initialize()
        except (AttributeError, TypeError):
            continue
        for fn in list(funcs):
            if _is_mecha_module(getattr(fn, '__module__', '')):
                funcs.remove(fn)
                removed += 1
    return removed


def _purge_keymaps():
    removed = 0
    wm = bpy.context.window_manager
    kc = wm.keyconfigs.addon if wm else None
    if kc is None:
        return 0
    for km in kc.keymaps:
        for item in list(km.keymap_items):
            if item.idname.startswith('mch.'):
                try:
                    km.keymap_items.remove(item)
                    removed += 1
                except (ReferenceError, RuntimeError):
                    pass
    return removed


def _purge_tools():
    removed = 0
    try:
        from bl_ui.space_toolsystem_common import ToolSelectPanelHelper
        cls = ToolSelectPanelHelper._tool_class_from_space_type('VIEW_3D')
    except (ImportError, AttributeError):
        return 0
    tools = getattr(cls, '_tools', {})
    for mode, items in tools.items():
        if not isinstance(items, list):
            continue
        for i in range(len(items) - 1, -1, -1):
            item = items[i]
            idname = getattr(item, 'idname', '') if item is not None else ''
            if idname.startswith('mecha.'):
                del items[i]
                removed += 1
    return removed


def purge_stale(own_module, only_own=False):
    """Remove leftover Mecha Lab registrations; returns a short report.

    register:   only_own=False - also unloads another enabled Mecha Lab copy
                (two copies cannot work at the same time) and reports it.
    unregister: only_own=True  - never touches another copy.
    """
    global _ONLY
    if only_own:
        _ONLY = own_module
        try:
            return {'classes': _purge_classes(), 'handlers': _purge_handlers(),
                    'draw_funcs': _purge_draw_funcs()}
        finally:
            _ONLY = None
    FOREIGN.clear()
    for cls in registered_mecha_classes():
        mod = getattr(cls, '__module__', '') or ''
        top = mod.rsplit('.', 1)[0] if '.' in mod else mod
        if not (mod == own_module or mod.startswith(own_module + '.')) and top not in FOREIGN:
            FOREIGN.append(top)
    report = {
        'classes': _purge_classes(),
        'props': _purge_props(),
        'handlers': _purge_handlers(),
        'draw_funcs': _purge_draw_funcs(),
        'keymap_items': _purge_keymaps(),
        'tools': _purge_tools(),
    }
    if any(report.values()):
        print('[Mecha Lab] cleaned stale registrations:',
              {k: (len(v) if isinstance(v, list) else v) for k, v in report.items()})
    if FOREIGN:
        print('[Mecha Lab] WARNING: another Mecha Lab copy was active and has been unloaded:', FOREIGN,
              '- disable / remove it in Preferences.')
    return report


def run_steps(steps):
    """Run every (label, callable); collect errors instead of stopping."""
    LAST_ERRORS.clear()
    for label, fn in steps:
        try:
            fn()
        except Exception as ex:   # keep going: a half-unregistered add-on is worse
            LAST_ERRORS.append(f'{label}: {ex}')
            traceback.print_exc()
    if LAST_ERRORS:
        print('[Mecha Lab] unregister finished with errors:', LAST_ERRORS)
    return LAST_ERRORS
