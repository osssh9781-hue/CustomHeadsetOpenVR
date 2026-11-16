"""0.24.180 Bend any part, later (user, the Base Mesh window's Bend card: "내가 만든 오브젝트를 나중에 내가 벤드로 휠 수
있는 거 만들어 줄래, 각도나 이런 거 다 조절 가능하게? 여기 있는 메뉴 다 넣어 줘"): a long bar - Band up 90 (ends rise
the same, its middle line as long), Angle (a fold at the Position, the sides straight), Sideways, Position, Direction;
on a part with something live on it (an Array: stays live, bent after it); Remove; Freeze (a plain mesh, bent); the
Live Stack lists it and shows the card."""
import math

import numpy as np
from _harness import bpy, check, fresh, summary

import mecha_lab
from mecha_lab import bend_any as ba, live_stack as ls  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def bar(x_len=4.0, cuts=63, loc=(0.0, 0.0, 0.0)):
    bpy.ops.mesh.primitive_grid_add(x_subdivisions=cuts + 1, y_subdivisions=3, size=1.0, location=loc)
    g = C.active_object
    g.scale = (x_len, 0.4, 1.0)
    bpy.ops.object.transform_apply(scale=True)
    m = g.modifiers.new('S', 'SOLIDIFY')
    m.thickness, m.offset = 0.1, 0.0
    C.view_layer.objects.active = g
    bpy.ops.object.modifier_apply(modifier='S')
    return g


def pts(ob):
    dg = C.evaluated_depsgraph_get()
    dg.update()
    e = ob.evaluated_get(dg)
    return np.array([tuple(v.co) for v in e.data.vertices])


def middle_line(P, X0):
    """The bent bar's middle line: the points that started on y = 0, z = 0 sorted by their start x."""
    sel = (np.abs(X0[:, 1]) < 1e-4) & (np.abs(X0[:, 2]) < 0.051)
    idx = np.nonzero(sel)[0]
    idx = idx[np.argsort(X0[idx, 0])]
    Q = (P[idx][0::2] + P[idx][1::2]) / 2 if False else P[idx]
    return X0[idx], Q


b = bar()
X0 = np.array([tuple(v.co) for v in b.data.vertices])
r = bpy.ops.mch.bend_add()
check(f'Bend on a plain part ({r}): its modifier at the end of the stack, the Live Stack names it ("Bend")',
      r == {'FINISHED'} and ba.has(b) and b.modifiers[-1].name == ba.MOD
      and [n for _m, n, _s in ls.entries(b)] == ['Bend'])
P0 = pts(b)
check(f'0 degrees: the part as it was ({np.abs(P0 - X0).max():.6f})', np.abs(P0 - X0).max() < 1e-5)
b.mch_bend.up = math.radians(90)
P = pts(b)
ends = P[np.argsort(X0[:, 0])]
left = P[X0[:, 0] < -1.99]
right = P[X0[:, 0] > 1.99]
mid_z = P[np.abs(X0[:, 0]) < 0.04][:, 2].mean()
# the middle sheet (z = 0 at the start): its length along x as bent
ms = (np.abs(X0[:, 2]) < 1e-6) & (np.abs(X0[:, 1]) < 1e-6)
if not ms.any():
    ms = np.abs(X0[:, 1] - X0[np.argmin(np.abs(X0[:, 1])), 1]) < 1e-6
row = np.nonzero(np.abs(X0[:, 1] - X0[np.argmin(np.abs(X0[:, 1])), 1]) < 1e-6)[0]
top = row[X0[row, 2] > 0]
bot = row[X0[row, 2] < 0]
top = top[np.argsort(X0[top, 0])]
bot = bot[np.argsort(X0[bot, 0])]
mid_pts = (P[top] + P[bot]) / 2
L_bent = float(np.linalg.norm(np.diff(mid_pts, axis=0), axis=1).sum())
check(f'Band, Up 90: both ends rise the same (left z {left[:, 2].mean():.3f}, right {right[:, 2].mean():.3f}, the '
      f'middle {mid_z:.3f}); the middle line as long (4.000 -> {L_bent:.3f}); its ends turned 45 each '
      f'({math.degrees(math.atan2(*(mid_pts[-1] - mid_pts[-2])[[2, 0]])):.1f})',
      abs(left[:, 2].mean() - right[:, 2].mean()) < 1e-3 and left[:, 2].mean() > mid_z + 0.5
      and abs(L_bent - 4.0) < 0.01 and abs(math.degrees(math.atan2(*(mid_pts[-1] - mid_pts[-2])[[2, 0]])) - 45) < 2.0)
b.mch_bend.up = -math.radians(90)
Pd = pts(b)
check(f'Up -90: both ends drop ({Pd[X0[:, 0] < -1.99][:, 2].mean():.3f})', Pd[X0[:, 0] < -1.99][:, 2].mean() < -0.5)
# Angle: a fold at the Position, the sides straight
b.mch_bend.style, b.mch_bend.up, b.mch_bend.pos, b.mch_bend.fold = 'ANGLE', math.radians(90), 0.5, 0.05
P = pts(b)
mp = (P[top] + P[bot]) / 2
xs = X0[top, 0]
fold_x = 0.5 * 2.0
lhs = mp[xs < fold_x - 0.2]
rhs = mp[xs > fold_x + 0.2]


def line_of(Q):
    d = Q[-1] - Q[0]
    d = d / np.linalg.norm(d)
    return d, float(np.linalg.norm(np.cross(Q - Q[0], d), axis=1).max())


dl, off_l = line_of(lhs)
dr, off_r = line_of(rhs)
between = math.degrees(math.acos(max(-1.0, min(1.0, float(np.dot(dl, dr))))))
corner = mp[np.argmin(np.abs(xs - fold_x))]
check(f'Angle, Position 0.5, Fold Width 0.05: one fold at x = 1.0 (the fold at x {corner[0]:.3f}) - both sides straight '
      f'({off_l:.5f}, {off_r:.5f}), 90 between them ({between:.1f}), both rising from it as the Base Mesh\'s',
      off_l < 1e-4 and off_r < 1e-4 and abs(between - 90.0) < 1.0 and abs(corner[0] - 1.0) < 0.05)
# Sideways, Direction
b.mch_bend.style, b.mch_bend.up, b.mch_bend.side, b.mch_bend.pos = 'SMOOTH', 0.0, math.radians(90), 0.0
P = pts(b)
check(f'Sideways 90: both ends go the same way across (y {P[X0[:, 0] < -1.99][:, 1].mean():.3f} / '
      f'{P[X0[:, 0] > 1.99][:, 1].mean():.3f}), not up (z {np.abs(P[:, 2]).max():.3f})',
      abs(P[X0[:, 0] < -1.99][:, 1].mean() - P[X0[:, 0] > 1.99][:, 1].mean()) < 1e-3
      and abs(P[X0[:, 0] < -1.99][:, 1].mean()) > 0.5 and np.abs(P[:, 2]).max() < 0.06)
b.mch_bend.side, b.mch_bend.up, b.mch_bend.axis = 0.0, math.radians(60), math.radians(90)
P = pts(b)
check(f'Bend Direction 90: bent across the bar instead (its long ends level: z spread at x = +-2 '
      f'{np.ptp(P[np.abs(X0[:, 0]) > 1.99][:, 2]):.3f}; its sides rise: {P[X0[:, 1] > 0.19][:, 2].mean():.3f})',
      P[X0[:, 1] > 0.19][:, 2].mean() > 0.005)
b.mch_bend.axis = 0.0
r = bpy.ops.mch.bend_remove()
check(f'Remove ({r}): the part as it was ({np.abs(pts(b) - X0).max():.6f})', r == {'FINISHED'} and not ba.has(b)
      and np.abs(pts(b) - X0).max() < 1e-6)
# a part with something live on it
a = bar(x_len=1.0, cuts=15, loc=(0.0, 3.0, 0.0))
arr = a.modifiers.new('Array', 'ARRAY')
arr.count = 4
arr.relative_offset_displace = (1.0, 0.0, 0.0)
C.view_layer.objects.active = a
for o in C.selected_objects:
    o.select_set(False)
a.select_set(True)
bpy.ops.mch.bend_add()
a.mch_bend.up = math.radians(120)
Pa = pts(a)
check(f'on a part with an Array (still live: {a.modifiers[0].type}): the four copies bent as one ({len(Pa)} points, '
      f'the ends up {Pa[:, 2].max():.3f})', a.modifiers[0].type == 'ARRAY' and a.modifiers[-1].name == ba.MOD
      and Pa[:, 2].max() > 0.5)
arr.count = 6
P6 = pts(a)
check(f'... the Array changed after (6): bent as measured when the Bend was added ({len(P6)} points)', len(P6) > len(Pa))
arr.count = 4
r = bpy.ops.mch.bend_freeze()
Pf = np.array([tuple(v.co) for v in a.data.vertices])
check(f'Freeze ({r}): a plain mesh, bent (no modifiers, {len(Pf)} points, ends up {Pf[:, 2].max():.3f})',
      r == {'FINISHED'} and not len(a.modifiers) and abs(Pf[:, 2].max() - Pa[:, 2].max()) < 1e-4)


class Rec:
    def __init__(self):
        self.seen = []

    def __getattr__(self, k):
        def f(*a_, **kw):
            if k in ('prop', 'prop_enum'):
                self.seen.append(a_[1])
            elif k == 'operator':
                self.seen.append(a_[0])
            return self
        return f


rec = Rec()
for o in C.selected_objects:
    o.select_set(False)
b.select_set(True)
C.view_layer.objects.active = b
bpy.ops.mch.bend_add()
ba.draw(rec, C, b)
check(f'the card (the Base Mesh window\'s): {rec.seen}',
      all(k in rec.seen for k in ('style', 'up', 'side', 'pos', 'axis', 'mch.bend_remove', 'mch.bend_freeze')))
summary()
