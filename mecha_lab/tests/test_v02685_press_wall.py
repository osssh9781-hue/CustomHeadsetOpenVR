"""0.24.289 Press Cut Wall Angle (user: "프레스 컷 들어갈 때 훅 들어가는데 스탬프 모양에 맞춰서 대각선으로 들어가게"): the
pocket's walls go in on a slant - its floor is the stamp's shape drawn in by depth x tan(angle); 0 = straight."""
import math

import bmesh
import numpy as np

from _harness import bpy, check, cube, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, press_cut as pc

mecha_lab.register()
C = bpy.context
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)


def press(angle, depth=0.4, floor='FLAT'):
    fresh()
    S = C.scene
    S.mch_settings.auto_apply = True
    S.mch_press.wall_angle = math.radians(angle)
    S.mch_press.floor_mode = floor
    p = cube('P', size=2.0)
    xy = TOP.to_screen(Vector((0, 0, 1)))
    pr = pc.Press(C, p, pc.stamp_loops(C, xy, S.mch_press), TOP, 'CUT', center=xy, spacing=6.0,
                  follow=floor == 'FOLLOW', level=floor == 'LEVEL')
    ok = pr.cut_to(C, depth)
    pr.finish(C)
    co = np.array([p.matrix_world @ v.co for v in p.data.vertices])
    bm = bmesh.new()
    bm.from_mesh(p.data)
    closed = all(e.is_manifold for e in bm.edges)
    vol = bm.calc_volume()
    bm.free()
    return ok, co, closed, vol


def widths(co, depth):
    top = co[np.abs(co[:, 2] - 1.0) < 1e-4]
    rim = top[(np.abs(top[:, 0]) < 0.99) & (np.abs(top[:, 1]) < 0.99)]
    floor = co[np.abs(co[:, 2] - (1.0 - depth)) < 1e-3]
    return (np.ptp(rim[:, 0]) if len(rim) else 0.0), (np.ptp(floor[:, 0]) if len(floor) else 0.0)


check('default: Wall Angle 20 degrees', abs(math.degrees(C.scene.mch_press.wall_angle) - 20.0) < 1e-4)
ok0, co0, cl0, v0 = press(0.0)
w_top0, w_floor0 = widths(co0, 0.4)
check('0 degrees: straight in (the floor as wide as the opening)', ok0 and cl0 and abs(w_top0 - w_floor0) < 0.02,
      (round(w_top0, 3), round(w_floor0, 3)))
ok, co, cl, v = press(20.0)
w_top, w_floor = widths(co, 0.4)
want = 2 * 0.4 * math.tan(math.radians(20.0))
check('20 degrees: the floor narrower than the opening by about 2 x depth x tan(20) (walls on a slant)',
      ok and abs((w_top - w_floor) - want) < 0.25 * want, (round(w_top, 3), round(w_floor, 3), round(want, 3)))
check('... a closed solid, less taken away than with straight walls', cl and v > v0, (round(v0, 4), round(v, 4)))
ok, co, cl, v2 = press(40.0)
w_top2, w_floor2 = widths(co, 0.4)
check('40 degrees: steeper still (narrower floor)', ok and cl and w_floor2 < w_floor - 0.05, (w_floor, w_floor2))
ok, co, cl, vf = press(20.0, floor='FOLLOW')
check('Follow floor: slanted too, a closed solid', ok and cl and vf > v0 * 0.9 and widths(co, 0.4)[1] < w_top - 0.1,
      widths(co, 0.4))
check('after a press nothing is left set for other cuts (the slant only while Press Cut cuts)', cg.WARP[0] is None)
summary()
