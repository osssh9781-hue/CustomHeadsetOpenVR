"""Install the built extension ZIP through Blender's extension system and enable it.

Runs with temporary BLENDER_USER_* directories (see _harness), so the real
user's preferences / extensions are never touched.
"""
import glob
import os
import sys

from _harness import bpy, check, summary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
zips = sorted(glob.glob(os.path.join(ROOT, 'dist', 'mecha_lab-*.zip')))
check('dist zip exists', bool(zips), zips)
if zips:
    # The addon must come from the zip, not from ../addon on sys.path.
    sys.path[:] = [p for p in sys.path if not p.rstrip('/').endswith('addon')]
    repo = next((r for r in bpy.context.preferences.extensions.repos if r.module == 'user_default'), None)
    check('user_default repo available', repo is not None)
    try:
        r = bpy.ops.extensions.package_install_files(filepath=zips[-1], repo='user_default', enable_on_install=True)
        ok = r == {'FINISHED'}
    except Exception as ex:
        ok = False
        print('install error', ex)
    check('package_install_files FINISHED', ok)
    mod = 'bl_ext.user_default.mecha_lab'
    check('extension enabled', mod in bpy.context.preferences.addons.keys(), list(bpy.context.preferences.addons.keys()))
    check('operators available after install', hasattr(bpy.ops.mch, 'cut_stroke') and 'MCH_OT_cut_stroke' in dir(bpy.types))
    prefs = bpy.context.preferences.addons[mod].preferences if mod in bpy.context.preferences.addons else None
    check('addon preferences registered (hotkey switches)', prefs is not None and hasattr(prefs, 'space_menu'))
    try:
        bpy.ops.preferences.addon_disable(module=mod)
        ok = True
    except Exception as ex:
        ok = False
        print(ex)
    check('disable works', ok and 'MCH_OT_cut_stroke' not in dir(bpy.types))
    kc = bpy.context.window_manager.keyconfigs.addon
    left = [ki.idname for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')]
    check('no hotkeys left after disable', not left, left)
    bpy.ops.preferences.addon_enable(module=mod)
    check('re-enable works', 'MCH_OT_cut_stroke' in dir(bpy.types))
sys.exit(1 if summary() else 0)
