import math, sys, time
sys.path.insert(0, '/home/user/CustomHeadsetOpenVR/mecha_lab/tests')
from _harness import bpy, fresh
from mathutils import Euler, Vector
import mecha_lab
from mecha_lab import armor_plate as ap, belt_maker as bmk, core_geometry as cg
mecha_lab.register(); fresh()
C = bpy.context
sub = int(sys.argv[-1]) if sys.argv[-1].isdigit() else 8
bpy.ops.mesh.primitive_ico_sphere_add(subdivisions=sub, radius=1.0); body = C.active_object; body.name = 'Body'
print('body faces', len(body.data.polygons))
proj = cg.OrthoProjector(Euler((math.radians(90), 0, 0)).to_quaternion(), center=Vector((0, 0, 0)), pixels_per_unit=200.0, size=(1000, 1000))
scr = lambda x, z: (500 + x * 200, 500 + z * 200)
line = [scr(-1.3, 0.1), scr(0, 0.1), scr(1.3, 0.1)]
T = {}
def wrap(mod, name):
    real = getattr(mod, name)
    def f(*a, **k):
        t = time.perf_counter()
        try: return real(*a, **k)
        finally: T[name] = T.get(name, 0) + time.perf_counter() - t
    setattr(mod, name, f)
for n in ('pick_target', 'target_data', 'plane_section', '_wrap_path', 'resample', 'smooth_path', 'sweep', 'rebuild', 'front_index'):
    wrap(bmk, n)

t = time.perf_counter(); msg = bmk.perform(C, line, proj); print(f'perform {time.perf_counter() - t:.2f}s', msg); print('  ', {k: round(v, 2) for k, v in T.items()})
ob = C.active_object
for k, v in (('width', 0.3), ('thickness', 0.05), ('lift', 0.01), ('smooth', 5), ('preset', 'RAIL')):
    T.clear(); t = time.perf_counter(); setattr(ob.mch_belt, k, v); print(f'set {k}: {time.perf_counter() - t:.2f}s', {kk: round(vv, 2) for kk, vv in T.items()})
