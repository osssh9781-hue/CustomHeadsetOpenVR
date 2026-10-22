"""0.24.20 Base Mesh profile Puff: the drawn outline becomes an inflated lump, round on both sides, every part as
thick as it is wide (an arm-like strip becomes a tube, the body a fat lump); Puff slider = thickness against width."""
import math
import sys

from _harness import bpy, bmesh, check, fresh, non_manifold, summary, volume
from mathutils import Quaternion

import mecha_lab
from mecha_lab import base_mesh as bm_mod, core_geometry as cg, cut_engine as ce

TOP = cg.OrthoProjector(Quaternion())                  # 100 px = 1 unit
OBL = cg.OrthoProjector(Quaternion((1, 0, 0), math.radians(40)) @ Quaternion((0, 0, 1), math.radians(20)))
C = bpy.context
# body 2 x 2 units with an arm 2.5 long and 0.4 wide
BODY_ARM = [(400, 400), (600, 400), (600, 480), (850, 480), (850, 520), (600, 520), (600, 600), (400, 600)]
CIRCLE = ce.circle_loop((500, 500), (600, 500), 64)   # radius 1


def make(loops, projector=TOP, **kw):
    C.scene.mch_settings.mch_active_tool = 'CBASE'        # Puff is a Creature Base Mesh profile
    s = C.scene.mch_cbase
    if s.profile not in {'PUFF', 'RIDGE', 'PILLOW'}:
        s.profile = 'PUFF'
    for k, v in kw.items():
        setattr(s, k, v)
    before = set(bpy.data.objects)
    msg = bm_mod.perform_base(C, loops, projector)
    new = [o for o in bpy.data.objects if o not in before]
    return (new[0] if len(new) == 1 else None), msg


def reset():
    fresh()
    s = C.scene.mch_cbase
    s.resolution, s.offset, s.puff, s.peak, s.profile = 40, 0.0, 1.0, 0.0, 'PUFF'
    C.scene.cursor.location = (0, 0, 0)


def zs(ob, cond=lambda co: True):
    return [v.co.z for v in ob.data.vertices if cond(v.co)]


mecha_lab.register()
check('Puff is a Base Mesh profile with its own picture', 'PUFF' in [p[0] for p in bm_mod.PROFILES]
      and any(p[0] == 'PUFF' and p[3] == 'profile_puff' for p in bm_mod.PROFILES))
import os
check('profile_puff.png exists', os.path.exists(os.path.join(os.path.dirname(bm_mod.__file__), 'icons', 'profile_puff.png')))

reset()
ob, msg = make([CIRCLE])
check('circle: one closed lump', ob is not None and non_manifold(ob) == 0, msg)
z = zs(ob)
check('round on both sides (symmetric about the drawing plane)', abs(max(z) + min(z)) < 1e-4, (min(z), max(z)))
check('circle radius 1 -> a round lump (half height ~0.79 R, Poisson inflation)', 0.7 < max(z) < 0.88, max(z))
check('volume of a rounded lens (~3.3)', 2.8 < volume(ob) < 3.8, volume(ob))
check('smooth shaded', all(p.use_smooth for p in ob.data.polygons))

reset()
ob, msg = make([BODY_ARM])
check('body + arm: closed', ob is not None and non_manifold(ob) == 0, msg)
# local origin = middle of the outline's bounds (x -2.125 .. 2.375): body centre x -1.125, arm x 0.9 .. 2.4
arm = zs(ob, lambda co: 1.0 < co.x < 2.0)
body = zs(ob, lambda co: -1.4 < co.x < -0.8 and -0.3 < co.y < 0.3)
check('the arm is a thin tube (half height ~1.1 x half width 0.2)', 0.14 < max(arm) < 0.28, max(arm))
check('the body is a fat lump (half height ~ 1)', max(body) > 0.8, max(body))

s = ob.mch_base
check('live: settings stored on the object', s.live and s.profile == 'PUFF')
h1 = max(zs(ob))
check('Height slider starts at the real height (not Auto)', abs(s.peak - h1) < 0.02 * h1, (s.peak, h1))
s.peak = h1 * 0.5
h2 = max(zs(ob))
check('Height = half rebuilds live: half as thick, same outline', abs(h2 - h1 * 0.5) < 0.03 * h1
      and non_manifold(ob) == 0, (h1, h2))
s.peak = h1 * 2.0
check('Height x2: taller than wide, still closed', max(zs(ob)) > h1 * 1.9 and non_manifold(ob) == 0)
check('the next shape starts at Auto height again (Height is not carried over)', C.scene.mch_cbase.peak == 0.0)
z_res = []
for res in (20, 60):
    reset()
    ob, _ = make([CIRCLE], resolution=res)
    z_res.append(max(zs(ob)))
check('the same thickness at low and high Resolution (only smoother)', abs(z_res[0] - z_res[1]) < 0.04, z_res)
reset()
taper = [(300, 440), (700, 480), (700, 520), (300, 560)]       # wide end 1.2 -> narrow end 0.4
ob, _ = make([taper], outline_smooth=0.0)
prof = [max(zs(ob, lambda co, x=x: abs(co.x - x) < 0.08)) for x in (-1.5, -0.5, 0.5, 1.5)]
check('a taper tapers smoothly (thickness falls steadily toward the narrow end)', all(a > b for a, b in zip(prof, prof[1:]))
      and prof[0] > 1.6 * prof[-1], prof)

for name, loop in (('star (concave)', [(500 + 150 * math.cos(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.4),
                                         500 + 150 * math.sin(-math.pi / 2 + i * math.pi / 5) * (1 if i % 2 == 0 else 0.4))
                                        for i in range(10)]),
                   ('thin strip', ce.rect_loop((300, 495), (700, 505)))):
    for pn, proj in (('top', TOP), ('oblique', OBL)):
        reset()
        ob, msg = make([loop], proj)
        check(f'{name} / {pn}: closed lump', ob is not None and non_manifold(ob) == 0 and volume(ob) > 1e-7, msg)

reset()
ring = [ce.circle_loop((500, 500), (700, 500), 64), list(reversed(ce.circle_loop((500, 500), (600, 500), 48)))]
ob, msg = make(ring)
z = zs(ob)
check('ring outline (with hole) -> a closed donut, tube half height ~0.56', ob is not None and non_manifold(ob) == 0
      and 0.42 < max(z) < 0.65, (msg, max(z) if ob else None))

reset()
for low in (4, 8):
    C.scene.mch_cbase.resolution = low
    ob, msg = make([BODY_ARM])
    check(f'low resolution {low}: still closed (narrow parts split, no doubled faces)', ob is not None
          and non_manifold(ob) == 0, msg)

reset()
C.scene.mch_cbase.profile = 'PUFF'
try:
    bm_mod._perform_cutter(C, [([(0, 0), (1, 0), (1, 1)], [])], None, C.scene.mch_cbase, None, None, [object()])
    refused = False
except cg.CutError as ex:
    refused = 'Puff' in str(ex)
check('Alt cutter refuses Puff with a message (no flat cap)', refused)
src = open(os.path.join(os.path.dirname(bm_mod.__file__), 'ui_tool_settings.py')).read()
check('panel: Height (peak) slider for the creature shapes', "col.prop(p, 'peak')" in src)
sys.exit(1 if summary() else 0)
