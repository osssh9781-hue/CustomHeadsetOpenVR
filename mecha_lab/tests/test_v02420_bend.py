"""0.24.20 Base Mesh / Creature Base Mesh Bend: a made (live) shape bends along its main axis - Bend Up / Down
(both ends rise or drop) and Bend Sideways (a banana seen from above), Bend Direction turns the axis."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg

TOP = cg.OrthoProjector(Quaternion())                  # 100 px = 1 unit
C = bpy.context
STRIP = [(300, 460), (700, 460), (700, 540), (300, 540)]      # 4 x 0.8, long along X


def make(tool, profile):
    C.scene.mch_settings.mch_active_tool = tool
    s = C.scene.mch_cbase if tool == 'CBASE' else C.scene.mch_base
    s.profile = profile
    if tool == 'BASE':
        s.sketch = False
    before = set(bpy.data.objects)
    bm_mod.perform_base(C, [STRIP], TOP)
    new = [o for o in bpy.data.objects if o not in before]
    return new[0] if len(new) == 1 else None


def world_z(ob):
    return [(ob.matrix_world @ v.co) for v in ob.data.vertices]


mecha_lab.register()

# pure helpers
check('bend_coords: no bend = same point', bm_mod.bend_coords(0.3, 0.1, 0.2, 1.0, 0.0, 0.0) == (0.3, 0.1, 0.2))
u, w, z = bm_mod.bend_coords(1.0, 0.0, 0.0, 1.0, math.pi, 0.0)
r = 2.0 / math.pi
check('bend_coords: 180 deg up turns the end straight up (a half circle)', abs(u - r) < 1e-9 and abs(z - r) < 1e-9,
      (u, z))
d, _c = bm_mod.bend_axis_dir([([(0, 0), (4, 0), (4, 1), (0, 1)], [])])
check('bend axis = the long side of the outline', abs(abs(d[0]) - 1.0) < 1e-6, d)

for tool, profile in (('BASE', 'FLAT'), ('BASE', 'BEVEL'), ('BASE', 'DOME'), ('CBASE', 'PUFF')):
    fresh()
    C.scene.cursor.location = (0, 0, 0)
    ob = make(tool, profile)
    check(f'{profile}: made', ob is not None)
    if ob is None:
        continue
    p = ob.mch_base
    n0 = len(ob.data.vertices)
    pts = world_z(ob)
    z0 = max(q.z for q in pts) - min(q.z for q in pts)
    y0 = max(q.y for q in pts) - min(q.y for q in pts)
    p.bend_up = math.radians(90)
    pts = world_z(ob)
    ends = [q.z for q in pts if abs(q.x) > 1.6]
    mid = [q.z for q in pts if abs(q.x) < 0.2]
    check(f'{profile}: Bend Up lifts both ends', p.last_error == '' and ends and mid and min(ends) > min(mid) + 0.3,
          (p.last_error, round(min(ends or [0]), 3), round(min(mid or [0]), 3)))
    check(f'{profile}: bent shape stays closed', non_manifold(ob) == 0, non_manifold(ob))
    p.bend_up = math.radians(-90)
    pts = world_z(ob)
    ends = [q.z for q in pts if abs(q.x) > 1.6]
    mid = [q.z for q in pts if abs(q.x) < 0.2]
    check(f'{profile}: Bend Down drops both ends', ends and mid and max(ends) < max(mid) - 0.3)
    p.bend_up = 0.0
    p.bend_side = math.radians(90)
    pts = world_z(ob)
    z1 = max(q.z for q in pts) - min(q.z for q in pts)
    y1 = max(q.y for q in pts) - min(q.y for q in pts)
    check(f'{profile}: Bend Sideways curves it in plan, thickness unchanged',
          y1 > y0 + 0.3 and abs(z1 - z0) < 1e-3 * max(1.0, z0) + 1e-4, (round(y0, 3), round(y1, 3), z0, z1))
    check(f'{profile}: sideways bent shape stays closed', non_manifold(ob) == 0)
    p.bend_side = 0.0
    check(f'{profile}: bend back to 0 = the straight shape again', len(ob.data.vertices) == n0,
          (n0, len(ob.data.vertices)))

fresh()
ob = make('BASE', 'FLAT')
check('new shapes start straight', ob is not None and ob.mch_base.bend_up == 0.0 and ob.mch_base.bend_side == 0.0)
summary()
