"""0.24.73 crash / data-loss review fixes: memory budgets (High Poly, Divide), results built apart, engine arrays
checked, High Poly rebuild keeps the old copy on failure."""
import numpy as np

from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import budget, fast_decimate as fd, highpoly as hp, quad_field as qf, zb_sculpt as zs

mecha_lab.register()
fresh()
C = bpy.context


def sphere(level=4, name='S'):
    bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=level, radius=1.0)
    ob = C.active_object
    ob.name = name
    return ob


# --- budgets --------------------------------------------------------------------------------------------------------
free = budget.available_memory()
check('Free memory is known on this system (Linux: /proc/meminfo; Windows: GlobalMemoryStatusEx)',
      free is not None and free > 0, free)
check('A result over the hard cap never fits; a small one does', not budget.faces_fit(budget.HARD_FACES + 1)[0]
      and budget.faces_fit(1000)[0])
saved = budget.available_memory
budget.available_memory = lambda: 400 * 10_000_000            # (pretend: 4 GB free)
ok, why = budget.faces_fit(6_000_000)
check('... nor one that needs more than half the free memory (it says how much)', not ok and 'GB' in why, why)
check('High Poly: when even Smoothness 1 is over the limit the level is 0 (it used to stay 1 and go over)',
      hp.safe_level(5_000_000, 3) == 0 and hp.safe_level(100, 3) == 3, hp.safe_level(5_000_000, 3))

# --- High Poly: refused when too big, the old copy kept --------------------------------------------------------------
ob = sphere(3, 'Part')
r = bpy.ops.mch.make_highpoly()
first = [o for o in bpy.data.objects if o.get(hp.SRC_KEY) == 'Part']
check('High Poly makes its copy', r == {'FINISHED'} and len(first) == 1)
first_faces = len(first[0].data.polygons)
for o in C.selected_objects:
    o.select_set(False)
ob.hide_set(False)
ob.select_set(True)
C.view_layer.objects.active = ob
budget.available_memory = lambda: 400 * 2_000                 # (pretend: almost nothing free)
r = bpy.ops.mch.make_highpoly()
now = [o for o in bpy.data.objects if o.get(hp.SRC_KEY) == 'Part']
check('Not enough memory: refused, and the copy made before is still there, untouched', r == {'CANCELLED'}
      and len(now) == 1 and len(now[0].data.polygons) == first_faces, (r, len(now)))
budget.available_memory = saved
real = hp._make_highpoly


def failing(*a, **k):
    raise RuntimeError('simulated out of memory')


hp._make_highpoly = failing
try:
    try:
        hp.make_highpoly(C, ob, 2, 0.004, 0.6, 2)
        failed = False
    except RuntimeError:
        failed = True
finally:
    hp._make_highpoly = real
now = [o for o in bpy.data.objects if o.get(hp.SRC_KEY) == 'Part']
check('A rebuild that fails keeps the old copy (it was deleted first before)', failed and len(now) == 1
      and now[0].name == 'Part_HP' and len(now[0].data.polygons) == first_faces, (failed, [o.name for o in now]))
hp_ok, _lv = hp.make_highpoly(C, ob, 1, 0.004, 0.6, 2)
now = [o for o in bpy.data.objects if o.get(hp.SRC_KEY) == 'Part']
check('A rebuild that works replaces the old copy (one copy, same name)', len(now) == 1 and now[0] is hp_ok
      and hp_ok.name == 'Part_HP', [o.name for o in now])

# --- Divide: refused over the budget -------------------------------------------------------------------------------
ob2 = sphere(4, 'Sculpt')
budget.available_memory = lambda: 400 * 4_000                 # (pretend: room for 2,000 faces)
try:
    zs._divide(C, ob2)
    refused = ''
except RuntimeError as ex:
    refused = str(ex)
budget.available_memory = saved
check('Divide that would not fit in memory is refused with a message (each Divide is 4x - 2M faces x 2 Divides '
      'took Blender down)', 'not divided' in refused and zs.multires(ob2) is None, refused)
lv = zs._divide(C, ob2)
check('... and works when it fits', lv == 1 and zs.multires(ob2) is not None)

# --- the engines check their arrays (a broken one is an error message, not a crash) -------------------------------
V = np.array([[0, 0, 0], [1, 0, 0], [0, 1, 0], [0, 0, 1]], np.float32)
T = np.array([[0, 2, 1], [0, 1, 3], [1, 2, 3], [0, 3, 2]], np.int32)


def error_of(fn):
    try:
        fn()
    except (RuntimeError, ValueError) as ex:
        return str(ex)
    return ''


check('Decimate: a short locked / weight array is refused (it read past its end and took Blender down)',
      'one value per point' in error_of(lambda: fd.run(V, T, 2, locked=np.zeros(1, np.uint8)))
      and 'one value per point' in error_of(lambda: fd.run(V, T, 2, weight=np.ones(1, np.float32))))
Vn = V.copy()
Vn[1, 0] = np.nan
check('... NaN positions and broken faces too', 'NaN' in error_of(lambda: fd.run(Vn, T, 2))
      and 'out of range' in error_of(lambda: fd.run(V, T + 10, 2)))
check('... feat indices out of range too', 'out of range' in error_of(
    lambda: fd.run(V, T, 2, feat=np.array([[0, 99, 0]], np.int32))))
w = np.array([np.nan, 1, 2, 5], np.float32)
oV, oF, _a, _b = fd.run(V, T, 4, weight=w)
check('... a weight with NaN is cleaned (1 .. 1e6), the run goes on', len(oF) == 4)
check('Quad Remesh: NaN positions / broken faces are refused before the engine', 'NaN' in error_of(
    lambda: qf.remesh_arrays(Vn, T, 100)) and 'out of range' in error_of(lambda: qf.remesh_arrays(V, T + 10, 100)))
L = qf.lib()
check('Both engines\' functions have their argument types declared (a wrong one is a Python error)',
      L.mquad_run.argtypes is not None and len(L.mquad_run.argtypes) == 10
      and fd.lib().mdecim_run.argtypes is not None and len(fd.lib().mdecim_run.argtypes) == 16)

summary()
