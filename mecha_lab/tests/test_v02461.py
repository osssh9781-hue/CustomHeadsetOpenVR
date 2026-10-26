"""0.24.41 GN Edge (its own menu in Cut / Split, not mixed with Edge Finish): the border of the drawn area is
chamfered / rounded by a Geometry Nodes sweep (Mesh to Curve -> Curve to Mesh -> Set Position -> Mesh Boolean),
evenly all the way round, also on a dense mesh; Split: both parts (or one side)."""
import math

from _harness import bpy, check, fresh, non_manifold, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, cut_engine as ce, rim_sweep as rs

mecha_lab.register()
fresh()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)
S.mch_settings.auto_apply = True
cut = S.mch_cut
cut.depth_mode, cut.depth = 'SURFACE', 0.4
check('its own settings (Off by default); the old Edge Finish untouched', cut.gn_finish == 'NONE'
      and cut.edge_finish == 'NONE' and cut.gn_width > 0)
W = 0.08
LOOP = [(500 + 60 * math.cos(a), 500 + 45 * math.sin(a)) for a in (2 * math.pi * k / 48 for k in range(48))]


def block(name, cuts=6):
    bpy.ops.mesh.primitive_cube_add(size=2.0)
    o = C.active_object
    o.name = name
    bpy.ops.object.mode_set(mode='EDIT')
    bpy.ops.mesh.subdivide(number_cuts=cuts)
    bpy.ops.object.mode_set(mode='OBJECT')
    return o


def top_at(x, y):
    C.view_layer.update()
    hit, loc, _n, _i, ob, _m = S.ray_cast(C.evaluated_depsgraph_get(), Vector((x, y, 5)), Vector((0, 0, -1)))
    return (round(loc.z, 4), ob.name) if hit else (None, None)


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


for fin in ('CHAMFER', 'BEVEL'):
    clear()
    t = block('Dense')
    cut.gn_finish, cut.gn_width, cut.gn_segments = fin, W, 4
    msg = ce.perform_closed(C, 'CUT', [t], [LOOP], TOP, False)
    check(f'{fin}: cut + GN edge on a dense mesh, closed', f'GN {fin.title()}' in msg and non_manifold(t) == 0,
          (msg, non_manifold(t)))
    # half the width outside the drawn border: lower than the top (on the chamfer / round), all the way round
    zs = [top_at(0.6 * math.cos(a) * (1 + (W / 2) / 0.6 * 0) + (W / 2) * math.cos(a), 0.45 * math.sin(a) + (W / 2) * math.sin(a))[0]
          for a in (2 * math.pi * k / 12 for k in range(12))]
    want = 1.0 - W / 2 if fin == 'CHAMFER' else None
    if fin == 'CHAMFER':
        check('CHAMFER: half the width out from the border the surface is half the width down, evenly all round',
              all(z is not None and abs(z - want) < 0.012 for z in zs), zs)
    else:
        check('BEVEL: there the surface is rounded down (between the chamfer line and the top), evenly all round',
              all(z is not None and 1.0 - W / 2 + 0.005 < z < 1.0 - 0.001 for z in zs), zs)
    far = top_at(0.6 + 2 * W, 0.0)[0]
    check(f'{fin}: past the width the top is untouched', far is not None and abs(far - 1.0) < 1e-4, far)
    check(f'{fin}: no helper attributes left on the mesh', not any(a.name.startswith('mch_r') for a in t.data.attributes))

clear()
t = block('Sp', cuts=2)
cut.gn_finish, cut.gn_sides = 'CHAMFER', 'BOTH'
msg = ce.perform_closed(C, 'SPLIT', [t], [LOOP], TOP, False)
piece = [o for o in S.objects if o != t][0]
za, oa = top_at(0.6 + W / 2, 0.0)
zb, ob = top_at(0.6 - W / 2, 0.0)
check('Split, Both: the outer part and the new piece both chamfered at the border, both closed',
      abs(za - (1 - W / 2)) < 0.012 and oa == t.name and abs(zb - (1 - W / 2)) < 0.012 and ob == piece.name
      and non_manifold(t) == 0 and non_manifold(piece) == 0, (za, oa, zb, ob, msg))
clear()
t = block('Sp2', cuts=2)
cut.gn_sides = 'B'
ce.perform_closed(C, 'SPLIT', [t], [LOOP], TOP, False)
piece = [o for o in S.objects if o != t][0]
za, _ = top_at(0.6 + W / 2, 0.0)
zb, _ = top_at(0.6 - W / 2, 0.0)
check('Split, Side B only: the piece chamfered, the outer part left sharp', abs(za - 1.0) < 1e-4
      and abs(zb - (1 - W / 2)) < 0.012, (za, zb))
cut.gn_finish, cut.gn_sides = 'NONE', 'BOTH'
check('the GN Edge menu is in the Cut / Split panel', 'draw_gn_edge' in
      __import__('mecha_lab.ui_tool_settings', fromlist=['x']).draw_cut.__code__.co_names)
summary()
