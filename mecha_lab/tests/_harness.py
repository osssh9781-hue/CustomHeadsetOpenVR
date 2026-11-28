"""Shared helpers for headless Mecha Lab tests (run with a bpy-enabled Python).

Usage:  <python-with-bpy> tests/run_all.py
The add-on is imported from ../addon as package ``mecha_lab``.  The user's
Blender config is NOT used: BLENDER_USER_CONFIG / RESOURCES point to a temp dir.
"""
import os
import sys
import atexit
import shutil
import tempfile

sys.dont_write_bytecode = True   # keep reference/ and addon/ free of __pycache__

HERE = os.path.dirname(os.path.abspath(__file__))
ADDON_PARENT = os.path.join(os.path.dirname(HERE), 'addon')
_TMP = tempfile.mkdtemp(prefix='mecha_lab_test_')
atexit.register(shutil.rmtree, _TMP, True)     # (0.24.349 the temp config gone after the run - they filled the disk)
for var in ('BLENDER_USER_CONFIG', 'BLENDER_USER_SCRIPTS', 'BLENDER_USER_DATAFILES',
            'BLENDER_USER_RESOURCES', 'BLENDER_USER_EXTENSIONS'):
    os.environ[var] = os.path.join(_TMP, var.lower())
if ADDON_PARENT not in sys.path:
    sys.path.insert(0, ADDON_PARENT)

os.environ.setdefault('MCH_LANG', 'EN')     # 0.24.212 the tests read the screen in English (Korean: test_v02624)
import bpy  # noqa: E402
import bmesh  # noqa: E402

RESULTS = []


def check(name, cond, detail=''):
    RESULTS.append((name, bool(cond), detail))
    print(('PASS ' if cond else 'FAIL ') + name + ('  -- ' + str(detail) if detail else ''))
    return cond


def fresh():
    bpy.ops.wm.read_factory_settings(use_empty=True)


def mesh_obj(name, builder, loc=(0, 0, 0), **kw):
    me = bpy.data.meshes.new(name)
    bm = bmesh.new()
    builder(bm, **kw)
    bm.to_mesh(me)
    bm.free()
    ob = bpy.data.objects.new(name, me)
    bpy.context.scene.collection.objects.link(ob)
    ob.location = loc
    bpy.context.view_layer.update()
    return ob


def cube(name='Cube', size=2.0, loc=(0, 0, 0)):
    return mesh_obj(name, lambda bm: bmesh.ops.create_cube(bm, size=size), loc)


def cylinder(name='Cyl', segments=12, radius=1.0, depth=2.0, loc=(0, 0, 0)):
    return mesh_obj(name, lambda bm: bmesh.ops.create_cone(
        bm, cap_ends=True, segments=segments, radius1=radius, radius2=radius, depth=depth), loc)


def sphere(name='Sphere', loc=(0, 0, 0)):
    return mesh_obj(name, lambda bm: bmesh.ops.create_uvsphere(bm, u_segments=24, v_segments=12, radius=1.0), loc)


def non_manifold(ob_or_mesh):
    me = ob_or_mesh.data if hasattr(ob_or_mesh, 'data') else ob_or_mesh
    bm = bmesh.new()
    bm.from_mesh(me)
    n = sum(1 for e in bm.edges if not e.is_manifold)
    bm.free()
    return n


def volume(ob):
    bm = bmesh.new()
    bm.from_mesh(ob.data)
    v = bm.calc_volume()
    bm.free()
    return v * abs(ob.matrix_world.determinant())


def select_only(*obs):
    for o in bpy.context.selected_objects:
        o.select_set(False)
    for o in obs:
        o.select_set(True)
    bpy.context.view_layer.objects.active = obs[0] if obs else None


def summary():
    failed = [r for r in RESULTS if not r[1]]
    print(f'\n{len(RESULTS) - len(failed)}/{len(RESULTS)} passed')
    return failed


def script_cmd(script, *args):
    """0.24.349 the command that runs ``script`` (a test helper) in a fresh process with bpy: this Python when it is
    bpy-enabled, else (the tests run inside Blender, ``blender -b --python``) the Blender binary itself - before,
    ``sys.executable`` there was Blender's bare Python and the fuzz reruns got no result at all."""
    exe = getattr(bpy.app, 'binary_path', '') or ''
    if exe and 'blender' in os.path.basename(exe).lower():
        return [exe, '-b', '--factory-startup', '--python-use-system-env', '--python', script, '--'] + [str(a) for a in args]
    return [sys.executable, script] + [str(a) for a in args]


def script_env():
    env = dict(os.environ)
    env['PYTHONPATH'] = HERE + (os.pathsep + env['PYTHONPATH'] if env.get('PYTHONPATH') else '')
    return env

