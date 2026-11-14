"""0.24.171 (user, Alt+X on a Fur - "Mirror: select a mesh or a collection instance (selected: Curves - convert it to a
mesh first)" - "머리카락은 실시간 미러를 원하는 게 아니라, 내가 만들고 어플라이 한 걸 Alt+X 로 미러하고 싶다고"): hair
curves (a Fur, applied or live) take the same Mirror as a mesh - a mirrored copy of every strand (a small Geometry
Nodes mirror: Blender's Mirror modifier is for meshes), live until applied.  And the Fur's Bend (user: "머리카락을 내가
보는 뷰포트 방향에서 꺾을 수 있게 밴드 옵션").  Measured on the evaluated strands; the real Alt+X: tests/gui."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, mirror_tools as mt  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def blob(cx, cz, r=0.2):
    return [[FRONT.to_screen(Vector((cx + r * math.cos(a), -2.0, cz + r * math.sin(a))))
             for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]]


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def strands(ob):
    """(roots, tips) world, of the evaluated curves."""
    dg = C.evaluated_depsgraph_get()
    d = ob.evaluated_get(dg).data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    P = P.reshape(-1, 3)
    off = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('first_point_index', off)
    sz = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('points_length', sz)
    M = np.array(ob.matrix_world)
    W = P @ M[:3, :3].T + M[:3, 3]
    return W[off], W[off + sz - 1]


def matched(a, b, tol=1e-4):
    """Every point of ``a`` has one of ``b`` within tol (a mirror image)."""
    from mathutils.kdtree import KDTree
    kd = KDTree(len(b))
    for i, q in enumerate(b):
        kd.insert(q, i)
    kd.balance()
    return max(kd.find(q)[2] for q in a) < tol


bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
body = C.active_object
S.mch_fur.density = 15000.0
select(body)
cf.perform(C, blob(-0.45, 0.55), FRONT)
fur = C.active_object
r0, t0 = strands(fur)
check(f'a live fur drawn on -X only ({len(r0):,} strands, x {r0[:, 0].min():.2f} .. {r0[:, 0].max():.2f})',
      len(r0) > 500 and r0[:, 0].max() < 0.0)
p = S.mch_mirror
p.space, p.center = 'WORLD', 'ORIGIN'
select(fur)
check('Alt+X / the Mirror button with only a fur selected: no more "select a mesh" - the lean mirror takes it',
      mt.mirror_targets_kind(C) == 'MESH' and bpy.ops.mch.mirror_lean.poll())
mod = mt.setup_curves_mirror(fur, p, S, axes=(True, False, False))       # (what leaning toward X does)
r1, t1 = strands(fur)
mirror_x = r0 * np.array([-1, 1, 1])
check(f'...the live fur mirrored across World X: {len(r1):,} strands (2 x {len(r0):,}), every root and tip with its '
      f'mirror image', mod is not None and len(r1) == 2 * len(r0) and matched(mirror_x, r1)
      and matched(t0 * np.array([-1, 1, 1]), t1))
fur.mch_fur.length = fur.mch_fur.length * 1.5                           # (the fur still live: the copy follows)
r2, t2 = strands(fur)
check('...still live: a slider changes both sides', len(r2) == 2 * len(r0)
      and matched(t2[r2[:, 0] < 0] * np.array([-1, 1, 1]), t2[r2[:, 0] > 0]))
fur.mch_fur.length = fur.mch_fur.length / 1.5
# Enter in the lean = apply: a live fur keeps its mirror live (its strands come from the modifier above)
lg = mt.MirrorLeanLogic()
lg.p, lg.target_names, lg.axes, lg.flips, lg.pivot_name = p, [fur.name], [True, False, False], [False] * 3, None
msg = lg.finish_apply(C)
check(f'...Enter on a LIVE fur: the mirror stays live, said so ({msg[-70:]})', mt.curves_mod(fur) is not None
      and 'stays live' in msg)
# the user's case: an APPLIED fur (real hair curves)
cf.apply_fur(C, fur)
n_ap = len(fur.data.curves)
check(f'Apply Fur: real hair curves with the mirror on top ({n_ap:,} curves in the data, {len(strands(fur)[0]):,} shown)',
      not cf.is_fur(fur) and n_ap == len(r0) and len(strands(fur)[0]) == 2 * len(r0))
msg = lg.finish_apply(C)
rr, tt = strands(fur)
check(f'...Enter on the applied fur: the mirror baked - {len(fur.data.curves):,} real curves, both sides, no modifier left',
      mt.curves_mod(fur) is None and len(fur.data.curves) == 2 * len(r0) and matched(mirror_x, rr), msg)
piv = [o for o in bpy.data.objects if o.get('_mch_world_pivot')]
check(f'...its mirror centre (an empty) removed once nothing uses it ({len(piv)} left)', not piv)
# a mirror centre elsewhere (the mouse on another object: its centre) and Esc (restore)
bpy.ops.object.duplicate()
f2 = C.active_object
n2 = len(f2.data.curves)
mt.setup_curves_mirror(f2, p, S, axes=(True, False, False), center=Vector((0.5, 0.0, 0.0)))
ra, _ta = strands(f2)
src = strands(f2)[0][:n2]
check('...across another centre (x = 0.5): the copy at 1 - x', len(ra) == 2 * n2
      and matched(np.array([1.0, 0, 0]) + src * np.array([-1, 1, 1]), ra))
mt._restore(f2, None)
check('...Esc: the mirror taken off again (no modifier, no centre left)', mt.curves_mod(f2) is None
      and not [o for o in bpy.data.objects if o.get('_mch_world_pivot')] and len(strands(f2)[0]) == n2)
p.space = 'LOCAL'
f2.location.x += 3.0
C.view_layer.update()
mt.setup_curves_mirror(f2, p, S, axes=(True, False, False))
rl = strands(f2)[0]
ox = f2.matrix_world.translation.x
check(f'...Local (the Mirror panel): across the object\'s own origin (x = {ox:.1f})', len(rl) == 2 * n2
      and matched(rl[:n2] * np.array([-1, 1, 1]) + np.array([2 * ox, 0, 0]), rl))
p.space = 'WORLD'
mt._restore(f2, None)
bpy.data.objects.remove(f2)
bpy.data.objects.remove(fur)

# ---- Fur Bend ------------------------------------------------------------------------------------------------------
S.mch_fur.bend = 0.0
select(body)
cf.perform(C, blob(0.0, -0.6), FRONT)
fur = C.active_object
fur.mch_fur.gravity, fur.mch_fur.frizz, fur.mch_fur.spread, fur.mch_fur.clump = 1.5, 0.0, 0.0, 0.0
rb0, tb0 = strands(fur)
L = fur.mch_fur.length
fur.mch_fur.bend_dir = (1.0, 0.0, 0.0)
fur.mch_fur.bend_at, fur.mch_fur.bend_soft = 0.3, 0.0
fur.mch_fur.bend = math.radians(90.0)
rb1, tb1 = strands(fur)
dx = float(tb1[:, 0].mean() - tb0[:, 0].mean())
check(f'Fur Bend 90 toward +X at 0.3: the tips {dx / L:.2f} strand lengths toward +X (the roots where they were)',
      dx > 0.4 * L and np.allclose(rb0, rb1, atol=1e-6), dx / L)
seg = tb1 - rb1
check(f'...never past it: the strands end up pointing at +X at most ({float((seg / np.linalg.norm(seg, axis=1)[:, None])[:, 0].mean()):.2f} '
      f'along +X on average from root to tip)', float((seg / np.linalg.norm(seg, axis=1)[:, None])[:, 0].min()) > -0.2)
body.rotation_euler.z = math.radians(90)                                 # (the body turned: the direction is the world's)
C.view_layer.update()
cf.push(fur)
_rb2, tb2 = strands(fur)
dx2 = float(tb2[:, 0].mean() - strands(fur)[0][:, 0].mean())
check(f'...the direction is a world one: the body turned 90 degrees, the tips still bend toward world +X '
      f'({dx2 / L:.2f})', dx2 > 0.4 * L, dx2 / L)
body.rotation_euler.z = 0.0
C.view_layer.update()
cf.push(fur)
fur.mch_fur.bend = 0.0
_rb3, tb3 = strands(fur)
check('...Bend 0: as before', np.allclose(tb3, tb0, atol=1e-5))
select(fur)
r = bpy.ops.mch.fur_bend(side='LEFT')
from mecha_lab import creature_hair as ch  # noqa: E402
q = ch.view_rotation(C)
want = q @ Vector((-1, 0, 0)) if q is not None else None
check(f'the "Left" button: the bend direction the view\'s left, a first click 60 degrees ({math.degrees(fur.mch_fur.bend):.0f})',
      r == {'FINISHED'} and want is not None and (Vector(fur.mch_fur.bend_dir) - want).length < 1e-5
      and abs(math.degrees(fur.mch_fur.bend) - 60.0) < 1e-4 and fur.mch_fur.bend_side == 'LEFT')
# an older fur's graph (version 11): pushed - the new graph, the fur still grows (Body, Area, Material kept)
ng = fur.modifiers[cf.MOD].node_group
ng['mch_v'] = 11
n_before = len(strands(fur)[0])
cf.push(fur)
check(f'an older fur (its graph before Bend): upgraded when touched, still {len(strands(fur)[0]):,} strands '
      f'(was {n_before:,})', fur.modifiers[cf.MOD].node_group.get('mch_v') == cf.TREE_VERSION
      and len(strands(fur)[0]) == n_before)

mecha_lab.unregister()
summary()
