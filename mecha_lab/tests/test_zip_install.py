"""Install the built extension ZIP through Blender's extension system and enable it.

Runs with temporary BLENDER_USER_* directories (see _harness), so the real
user's preferences / extensions are never touched.
"""
import glob
import os
import sys

from _harness import bpy, check, summary

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))


def _key(p):                                     # mecha_lab-0.24.82_20261028-2359.zip: version, then the build stamp
    name = os.path.basename(p)[10:-4]
    ver, _s, stamp = name.partition('_')
    return tuple(int(x) for x in ver.split('.')), stamp                                   # 0.10 > 0.9


zips = sorted(glob.glob(os.path.join(ROOT, 'dist', 'mecha_lab-*.zip')), key=_key)
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
    import zipfile
    with zipfile.ZipFile(zips[-1]) as z:
        stamp = z.read('build_stamp.txt').decode().strip() if 'build_stamp.txt' in z.namelist() else ''
    label = sys.modules[mod].workspace_ui.build_label() if mod in sys.modules else ''
    check('0.24.82 the zip carries its build stamp (version + build time, also in the file name) and Preferences shows it',
          stamp.startswith('0.24.') and ' build ' in stamp
          and label == 'Mecha Lab ' + stamp and stamp.split('build ')[-1] in os.path.basename(zips[-1]), (stamp, label))
    kc = bpy.context.window_manager.keyconfigs.addon
    for cycle in range(3):          # docs/04 A1: disable / enable three times
        try:
            bpy.ops.preferences.addon_disable(module=mod)
            ok = True
        except Exception as ex:
            ok = False
            print(ex)
        check(f'cycle {cycle}: disable works', ok and 'MCH_OT_cut_stroke' not in dir(bpy.types))
        left = [ki.idname for km in kc.keymaps for ki in km.keymap_items if ki.idname.startswith('mch.')] if kc else []
        check(f'cycle {cycle}: no hotkeys left after disable', not left, left)
        try:
            bpy.ops.preferences.addon_enable(module=mod)
            ok = True
        except Exception as ex:
            ok = False
            print(ex)
        check(f'cycle {cycle}: re-enable works (no "already registered")', ok and 'MCH_OT_cut_stroke' in dir(bpy.types))
        # 0.24.17 the per-tool keys share one (unassigned) key but pick different tools
        items = [(km.name, ki.idname, ki.type, ki.value, ki.shift, ki.alt, ki.ctrl,
                  getattr(ki.properties, 'action', ''), getattr(ki.properties, 'tool', '')) for km in kc.keymaps
                 for ki in km.keymap_items if ki.idname.startswith('mch.')] if kc else []
        check(f'cycle {cycle}: keymap items not duplicated', len(items) == len(set(items)), len(items))
    check('Mirror panel available after cycles', hasattr(bpy.types, 'MCH_PT_mirror'))
sys.exit(1 if summary() else 0)
