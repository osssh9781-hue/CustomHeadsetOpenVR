"""0.24.171 (user: "왜 아직 머리카락 미러가 안 돼"): on a head with a live Mirror (its Bisect keeps +X), hair / fur drawn
on the OTHER side (-X: the side the Mirror makes) was cut away whole (Creature Hair: nothing left; Fur: 0 strands, or
"no surface" on a half head).  Now both tools mirror from either side (the Alt+X mirror of a fur: test_v02575).  And (user: "머리카락을 내가 보는 뷰포트 방향에서 꺾을 수 있게 밴드 옵션") Creature Hair's Bend.
Measured on the evaluated objects."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, creature_fur as cf, creature_hair as ch, symmetry  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)


def px(x, z):
    return FRONT.to_screen(Vector((x, -2.0, z)))


def blob(cx, cz, r=0.2):
    return [[px(cx + r * math.cos(a), cz + r * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 40, endpoint=False)]]


def head(half=False, mirror=True):
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)
    bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=96, ring_count=48)
    h = C.active_object
    if half:
        bm = bmesh.new()
        bm.from_mesh(h.data)
        bmesh.ops.delete(bm, geom=[v for v in bm.verts if v.co.x < -1e-4], context='VERTS')
        bm.to_mesh(h.data)
        bm.free()
    if mirror:
        symmetry.set_mode(C, h, 'MIRROR')
    return h


def select(ob):
    for o in C.selected_objects:
        o.select_set(False)
    ob.select_set(True)
    C.view_layer.objects.active = ob


def world_pts(ob):
    dg = C.evaluated_depsgraph_get()
    d = ob.evaluated_get(dg).data
    if ob.type == 'CURVES':
        P = np.empty(len(d.points) * 3, np.float32)
        d.attributes['position'].data.foreach_get('vector', P)
    else:
        P = np.empty(len(d.vertices) * 3, np.float32)
        d.vertices.foreach_get('co', P)
    P = P.reshape(-1, 3)
    M = np.array(ob.matrix_world)
    return P @ M[:3, :3].T + M[:3, 3]


def hair(h, loop, style='STRANDS'):
    S.mch_hair.style = style
    select(h)
    ch.perform(C, loop, FRONT)
    return C.active_object


def fur(h, loop):
    S.mch_fur.density = 20000.0
    select(h)
    cf.perform(C, loop, FRONT)
    return C.active_object


def roots(ob):
    """The fur's strand roots (world)."""
    dg = C.evaluated_depsgraph_get()
    d = ob.evaluated_get(dg).data
    P = np.empty(len(d.points) * 3, np.float32)
    d.attributes['position'].data.foreach_get('vector', P)
    off = np.empty(len(d.curves), np.int32)
    d.curves.foreach_get('first_point_index', off)
    M = np.array(ob.matrix_world)
    R = P.reshape(-1, 3)[off]
    return R @ M[:3, :3].T + M[:3, 3]


# ---- Creature Hair on a mirrored head, drawn on -X (where the head's own Bisect cuts) ------------------------------
for half in (False, True):
    h = head(half)
    hr = hair(h, blob(-0.45, 0.55))
    P = world_pts(hr)
    nv = len(hr.data.vertices)
    m = symmetry.mirror_mod(hr)
    check(f'Creature Hair drawn on -X of a {"half" if half else "whole"} head with a live Mirror (its Bisect keeping +X): '
          f'hair on both sides, every strand whole (x {P[:, 0].min():.2f} .. {P[:, 0].max():.2f}, {len(P):,} points = '
          f'2 x {nv:,}) - before: nothing left', P[:, 0].min() < -0.4 and P[:, 0].max() > 0.4 and len(P) == 2 * nv
          and m is not None and not m.use_bisect_axis[0], (P[:, 0].min(), P[:, 0].max(), len(P), nv))
h = head()
hr = hair(h, blob(0.45, 0.55))
P = world_pts(hr)
check(f'...drawn on +X (as before): both sides too (x {P[:, 0].min():.2f} .. {P[:, 0].max():.2f})',
      P[:, 0].min() < -0.4 and P[:, 0].max() > 0.4)
bpy.data.objects.remove(hr)
hr = hair(h, [[px(-0.3 + 0.5 * math.cos(a), 0.6 + 0.2 * math.sin(a)) for a in np.linspace(0, 2 * math.pi, 48,
                                                                                        endpoint=False)]])
m = symmetry.mirror_mod(hr)
P = world_pts(hr)
check(f'...an area across the middle, mostly on -X: cut at the middle keeping -X (Bisect {m.use_bisect_axis[0]}, '
      f'Flip {m.use_bisect_flip_axis[0]}) - no doubled strands there; hair on both sides', m.use_bisect_axis[0]
      and m.use_bisect_flip_axis[0] and P[:, 0].min() < -0.4 and P[:, 0].max() > 0.4 and len(P) < 2 * len(hr.data.vertices))
hr.mch_hair.count = 60                                                  # (a slider: rebuilt, the cut still fits)
check('...still so after a slider rebuilds it', symmetry.mirror_mod(hr).use_bisect_axis[0]
      and symmetry.mirror_mod(hr).use_bisect_flip_axis[0])

# ---- Fur on a mirrored head, drawn on -X ----------------------------------------------------------------------------
for half in (False, True):
    h = head(half)
    try:
        fr = fur(h, blob(-0.45, 0.55))
        R = roots(fr)
        nl, nr = int((R[:, 0] < -0.1).sum()), int((R[:, 0] > 0.1).sum())
    except cg.CutError as ex:
        nl = nr = 0
        print('  ', ex)
    check(f'Fur drawn on -X of a {"half" if half else "whole"} head with a live Mirror: strands on both sides ({nl:,} -X, '
          f'{nr:,} +X) - before: 0 strands / "no surface"', nl > 1000 and nr > 1000 and abs(nl - nr) < 0.25 * max(nl, nr),
          (nl, nr))
h = head()
fr = fur(h, blob(0.45, 0.55))
R = roots(fr)
nl, nr = int((R[:, 0] < -0.1).sum()), int((R[:, 0] > 0.1).sum())
check(f'...drawn on +X (as before): both sides ({nl:,} / {nr:,})', nl > 1000 and nr > 1000)
# Alt + draw (erase) on -X takes it away on both sides
select(fr)
cf.perform(C, blob(-0.45, 0.55, 0.3), FRONT, erase=True)
R = roots(fr)
check(f'...Alt + draw on -X takes it away on both sides ({len(R)} strands left)', len(R) < 50, len(R))

# ---- a head with no Mirror: no copy (as before) - the fur's own Alt+X mirror: test_v02575 -------------------------
h = head(mirror=False)
fr = fur(h, blob(-0.45, 0.55))
R = roots(fr)
n0l, n0r = int((R[:, 0] < -0.1).sum()), int((R[:, 0] > 0.1).sum())
check(f'no Mirror on the head: the fur only where drawn ({n0l:,} -X, {n0r} +X)', n0l > 1000 and n0r == 0)

# ---- Bend --------------------------------------------------------------------------------------------------------
h = head(mirror=False)
S.mch_hair.bend = 0.0
hr = hair(h, blob(0.0, -0.75, 0.25), style='STRAIGHT')                  # (low on the front: strands hang down)


def tips(ob):
    P = world_pts(ob)
    me = ob.data
    t = np.empty(len(me.vertices), np.float32)
    me.attributes[ch.T_ATTR].data.foreach_get('value', t)
    return P[t > 0.999]


t0 = tips(hr)
p = hr.mch_hair
p.bend_dir = (1.0, 0.0, 0.0)
p.bend_soft, p.bend_at = 0.0, 0.3
p.bend = math.radians(90.0)
t1 = tips(hr)
L = p.length * 2.0 * math.sqrt(3.0)                                     # (Length: a share of the body's size)
dx = float(t1[:, 0].mean() - t0[:, 0].mean())
dz = float(t1[:, 2].mean() - t0[:, 2].mean())
check(f'Bend 90 toward +X at 0.3 of the strand (sharp): the tips go {dx / L:.2f} strand lengths toward +X and '
      f'{dz / L:.2f} up (they no longer hang)', dx > 0.4 * L and dz > 0.3 * L, (dx / L, dz / L))
pts = [Vector((0, 0, -0.1 * k)) for k in range(11)]
b180 = ch.bend_path(pts, Vector((1, 0, 0)), math.pi, 0.0, 0.0)
last = (b180[-1] - b180[-2]).normalized()
b45 = ch.bend_path(pts, Vector((1, 0, 0)), math.radians(45), 0.5, 0.0)
first = (b45[1] - b45[0]).normalized()
end45 = (b45[-1] - b45[-2]).normalized()
check(f'...never past the direction (Bend 180 on a strand pointing down ends pointing at it: {last.x:.3f}); Bend 45 at '
      f'0.5: the first half untouched, then 45 degrees ({math.degrees(end45.angle(Vector((0, 0, -1)))):.1f})',
      last.x > 0.999 and first.z < -0.999 and abs(math.degrees(end45.angle(Vector((0, 0, -1)))) - 45.0) < 0.5)
bs = ch.bend_path(pts, Vector((1, 0, 0)), math.radians(90), 0.2, 0.6)
angs = [math.degrees((bs[i + 1] - bs[i]).normalized().angle(Vector((0, 0, -1)))) for i in range(10)]
check(f'...Bend Soft: a gradual turn (piece by piece {", ".join(f"{a:.0f}" for a in angs)} degrees)',
      all(b >= a - 1e-6 for a, b in zip(angs, angs[1:])) and max(np.diff(angs)) < 40 and angs[-1] > 85, angs)
p.bend = 0.0
t2 = tips(hr)
check('...Bend 0: back as it was', np.allclose(t2, t0, atol=1e-5))
q = ch.view_rotation(C)                                                 # (the startup file's 3D view)
select(hr)
r = bpy.ops.mch.hair_bend(side='RIGHT')
want = (q @ Vector((1, 0, 0))) if q is not None else None
check(f'the "Right" button: the bend direction the view\'s right ({tuple(round(v, 3) for v in hr.mch_hair.bend_dir)}), '
      f'a first click bends 60 degrees ({math.degrees(hr.mch_hair.bend):.0f}); the next hair too',
      q is not None and r == {'FINISHED'} and (Vector(hr.mch_hair.bend_dir) - want).length < 1e-5
      and abs(math.degrees(hr.mch_hair.bend) - 60) < 1e-4 and (Vector(S.mch_hair.bend_dir) - want).length < 1e-5
      and hr.mch_hair.bend_side == 'RIGHT', (q, r))
r = bpy.ops.mch.hair_bend(side='OFF')
check('..."No Bend": back to 0', r == {'FINISHED'} and hr.mch_hair.bend == 0.0 and np.allclose(tips(hr), t0, atol=1e-5))
check('the window: Bend side buttons (Left / Up / Right / Down / Toward Me / Away / No Bend), Bend, and its screen '
      'angle / Bend At / Bend Soft', [k for k, _l in ch.BEND_SIDES] == ['LEFT', 'UP', 'RIGHT', 'DOWN', 'TOWARD', 'AWAY']
      and all(k in ch.LIVE_KEYS for k in ('bend', 'bend_at', 'bend_soft', 'bend_dir', 'bend_screen')))

mecha_lab.unregister()
summary()
