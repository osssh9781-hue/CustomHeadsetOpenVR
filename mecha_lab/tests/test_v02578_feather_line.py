"""0.24.172 (user: "깃털 탭도 만들어 줘 - 이건 메쉬로 해야 되는데 가벼운 메쉬, 그리고 깃털 모양 프리셋도 15개 정도, 길이도
다양하게; 내가 그으면 그 라인 따라서 주욱 생기는 느낌; 길이랑 폭은 내가 조정 가능하게; 끝부분으로 갈수록 길어지게 하는 거랑
시작 부분이 길어지게 하는 거 두 개; 랜덤 길이 하나 넣어서 큰 틀은 유지하면서 중간중간 좀 달라지게" ... "비늘도 좀 더 리얼하게 -
지금은 너무 네모 동그라미"): the 15 feather shapes and 8 real scales (creature_shapes), the Feather Line tool (a line
drawn: feathers along it, their quills on it), Length / Width / Longer to End / Longer at Start / Length Random.
Measured on the meshes and the line's own placements.  The real drawing: tests/gui/round172_real_window.py."""
import math
import os

import numpy as np
from _harness import bpy, check, fresh, summary
from mathutils import Quaternion, Vector

import mecha_lab
from mecha_lab import creature_shapes as cs, greeble_line as gl, tool_state as ts, ui_tool_settings as uts  # noqa
from mecha_lab import workspace_ui as wu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene


def coords(me):
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    return co.reshape(-1, 3)


# ---- the shapes -----------------------------------------------------------------------------------------------------
fm = cs.feather_meshes()
faces = [len(me.polygons) for _n, me in fm]
ext = [np.ptp(coords(me), axis=0) for _n, me in fm]
base = [coords(me)[:, 0].min() for _n, me in fm]
lens = sorted(cs.FEATHER_LENGTHS.values())
check(f'16 feather shapes (0.24.173 the kestrel\'s tail from the user\'s photo), light ({min(faces)}..{max(faces)} faces each), each its own outline, the quill base at '
      f'the origin, length along +X, lengths {lens[0]:.2f}..{lens[-1]:.2f}',
      len(fm) == 16 and len({me.get('mch_shape_id') for _n, me in fm}) == 16 and max(faces) <= 1100
      and all(e[0] > e[1] for e in ext) and all(abs(b) < 0.03 for b in base) and lens[-1] / lens[0] > 2.5
      and all(me.attributes.get(cs.T_ATTR) is not None for _n, me in fm))
widths = [round(float(e[1] / e[0]), 2) for e in ext]
check(f'the feathers differ (width / length {sorted(widths)})', len(set(widths)) >= 10)
kme = dict((me['mch_shape_id'], me) for _n, me in fm)['KESTREL']
kc = np.empty(len(kme.vertices) * 4, np.float32)
kme.attributes[cs.C_ATTR].data.foreach_get('color', kc)
kc = kc.reshape(-1, 4)
kt = np.empty(len(kme.vertices), np.float32)
kme.attributes[cs.T_ATTR].data.foreach_get('value', kt)
kco = coords(kme)
lum = kc[:, :3].mean(1)
tipw = lum[kt > 0.985].mean()
band = lum[(kt > 0.82) & (kt < 0.88)].mean()
body = kc[(kt > 0.35) & (kt < 0.6) & (kco[:, 1] < -0.01)]
outer = (kco[:, 1] > 0.004) & (kt > 0.45) & (kt < 0.7)
check(f'the kestrel\'s tail (the photo): a long blunt feather ({np.ptp(kco[:, 0]) / np.ptp(kco[:, 1]):.1f} x as long as wide), '
      f'the narrow vane on +Y ({kco[:, 1].max():.3f} vs {-kco[:, 1].min():.3f}), its own colours: a white tip ({tipw:.2f}), a '
      f'black band ({band:.2f}), rufous ({np.round(body[:, :3].mean(0), 2)}), black spots on the narrow vane '
      f'({lum[outer].min():.2f}) among white ({lum[outer].max():.2f})',
      np.ptp(kco[:, 0]) / np.ptp(kco[:, 1]) > 5.0 and kco[:, 1].max() < -kco[:, 1].min() * 0.8 and tipw > 0.5
      and band < 0.05 and body[:, 0].mean() > 2.5 * body[:, 2].mean() and lum[outer].min() < 0.05
      and lum[outer].max() > 0.5)
cme = dict((me['mch_shape_id'], me) for _n, me in fm)['CONTOUR']
cc = np.empty(len(cme.vertices) * 4, np.float32)
cme.attributes[cs.C_ATTR].data.foreach_get('color', cc)
check('the other feathers keep their brown (dark at the base, lighter to the tip), every one opaque in its colours',
      cc.reshape(-1, 4)[:, 3].min() == 1.0 and cc.reshape(-1, 4)[:, :3].mean(1).max() > 0.2
      and cc.reshape(-1, 4)[:, :3].mean(1).min() < 0.03)
sm = cs.scale_meshes_real()


def closed(me):
    import bmesh
    bm = bmesh.new()
    bm.from_mesh(me)
    ok = all(len(e.link_faces) == 2 for e in bm.edges)
    bm.free()
    return ok


def outline_spread(me):
    """How far the outline is from a square / a circle: its radius (about the middle) round the outline."""
    P = coords(me)
    bot = P[np.abs(P[:, 2]) < 1e-6]
    c = bot[:, :2].mean(0)
    r = np.linalg.norm(bot[:, :2] - c, axis=1)
    ang = np.arctan2(bot[:, 1] - c[1], bot[:, 0] - c[0])
    sq = 1.0 / np.maximum(np.abs(np.cos(ang)), np.abs(np.sin(ang)))       # (a square's radius that way)
    rs = r / r.mean()
    return float(rs.std()), float(np.corrcoef(rs, sq / sq.mean())[0, 1])


spr = [outline_spread(me) for _n, me in sm]
sfaces = [len(me.polygons) for _n, me in sm]
check(f'8 real scales: closed meshes, the root edge at the origin, the free edge along +X, {min(sfaces)}..'
      f'{max(sfaces)} faces; outlines neither circles (radius spread {min(s for s, _c in spr):.2f}..) nor squares '
      f'(like a square {max(c for _s, c in spr):.2f})', len(sm) == 8 and all(closed(me) for _n, me in sm)
      and all(abs(coords(me)[:, 0].min()) < 0.02 for _n, me in sm) and max(sfaces) <= 450
      and min(s for s, _c in spr) > 0.03 and max(c for _s, c in spr) < 0.8)
kz = {me.get('mch_shape_id'): coords(me) for _n, me in sm}
K = kz['KEELED']
mid = K[np.abs(K[:, 1]) < 0.02]
side = K[(np.abs(K[:, 1]) > 0.12) & (np.abs(K[:, 1]) < 0.2)]
check(f'the keeled scale has its keel (middle {mid[:, 2].max():.3f} over the side {side[:, 2].max():.3f})',
      mid[:, 2].max() > side[:, 2].max() * 1.15)

# ---- the tool ----------------------------------------------------------------------------------------------------------
check('Feather Line: a tool in the Creature tools, its icon, its window, its settings',
      'FGREEBLE' in ts.TOOL_BY_ID and 'FGREEBLE' in dict(ts.TOOL_GROUPS)['Creature']
      and os.path.isfile(os.path.join(os.path.dirname(gl.__file__), 'icons', 'fgreeble.png'))
      and uts.DRAWERS.get('FGREEBLE') is not None and gl.settings(S, 'FEATHER') is not None)
for o in list(bpy.data.objects):
    bpy.data.objects.remove(o)
bpy.ops.mesh.primitive_uv_sphere_add(radius=1.0, segments=64, ring_count=32)
body = C.active_object
body.scale = (2.2, 0.35, 0.18)
bpy.ops.object.transform_apply(scale=True)
st = gl.settings(S, 'FEATHER')
r = bpy.ops.mch.feather_pick(feather='PRIMARY')
P_ = gl.picked(st)
check(f'a feather button: that feather made and picked ({[p.name for p in P_]})', r == {'FINISHED'}
      and len(P_) == 1 and 'Primary' in P_[0].name)


def draw_line(**kw):
    for k, v in kw.items():
        setattr(st, k, v)
    pts, nrm = [], []
    for t in np.linspace(-0.95, 0.95, 50):
        x = 2.2 * t
        pts.append((x, 0.0, 0.18 * math.sqrt(max(0.0, 1 - t * t))))
        nrm.append((0.0, 0.0, 1.0))
    ln = gl.new_line(C, body, pts, nrm, gl.picked(st), st, 'FEATHER')
    gl.rebuild(ln, C)
    me = ln.data
    n = len(me.vertices)
    sc = np.empty(n * 3, np.float32)
    me.attributes['mch_scale'].data.foreach_get('vector', sc)
    q = np.empty(n * 4, np.float32)
    me.attributes['mch_rot'].data.foreach_get('value', q)
    return ln, coords(me), sc.reshape(-1, 3), q.reshape(-1, 4)


base_k = dict(length=1.0, width=1.0, grow_end=0.0, grow_start=0.0, length_random=0.0, scale_random=0.0)
ln0, P0, S0, Q0 = draw_line(**base_k)
Lx = S0[:, 0]
check(f'drawn: feathers along the line ({len(P0)}), all the same length with nothing on ({Lx.min():.3f}..'
      f'{Lx.max():.3f}), live', len(P0) >= 5 and np.ptp(Lx) < 1e-5 and ln0.modifiers.get('MCH Greeble') is not None)
# the quill on the line: the feather's origin (its quill base) where the line is
M = ln0.matrix_world
on = []
for p in P0:
    w = M @ Vector(tuple(p))
    t = max(-0.95, min(0.95, w.x / 2.2))
    on.append(abs(w.z - 0.18 * math.sqrt(max(0.0, 1 - t * t))) + abs(w.y))
check(f'each feather\'s quill base on the line (off by {max(on):.4f} at most)', max(on) < 0.02)
ln1, P1, S1, _q = draw_line(**dict(base_k, grow_end=1.5))
u = np.argsort(P1[:, 0])
check(f'Longer to End 1.5: longer and longer along it (first {S1[u[0], 0]:.3f} -> last {S1[u[-1], 0]:.3f}, '
      f'never shorter than the one before)', S1[u[-1], 0] > S1[u[0], 0] * 2.0
      and np.all(np.diff(S1[np.argsort(np.arange(len(S1))), 0]) >= -1e-6))
ln2, P2, S2, _q = draw_line(**dict(base_k, grow_start=1.5))
check(f'Longer at Start 1.5: the start long, the end short (first {S2[0, 0]:.3f}, last {S2[-1, 0]:.3f})',
      S2[0, 0] > S2[-1, 0] * 2.0 and np.all(np.diff(S2[:, 0]) <= 1e-6))
ln3, P3, S3, _q = draw_line(**dict(base_k, grow_start=1.0, grow_end=1.0))
ln3b, P3b, S3b, _q = draw_line(**dict(base_k, grow_start=1.0, grow_end=0.4))
check(f'both the same ("똑같이 길게"): all equally longer ({S3[:, 0].min():.3f}..{S3[:, 0].max():.3f} = 2 x '
      f'{Lx[0]:.3f}); Start 1 / End 0.4 ("한쪽만 짧게"): the end shorter ({S3b[0, 0]:.3f} -> {S3b[-1, 0]:.3f})',
      np.ptp(S3[:, 0]) < 1e-5 and abs(S3[0, 0] / Lx[0] - 2.0) < 0.01 and S3b[-1, 0] < S3b[0, 0] * 0.8
      and S3b[-1, 0] > Lx[0] * 1.2)
ln4, P4, S4, _q = draw_line(**dict(base_k, grow_end=1.5, length_random=0.25))
k = np.arange(len(S4))
corr = np.corrcoef(k, S4[:, 0])[0, 1]
steps = np.diff(S4[:, 0])
check(f'Length Random 0.25 with Longer to End: some in between differ (shorter than the one before {int((steps < 0).sum())} '
      f'times), the overall shape kept (along it vs length: {corr:.2f})', (steps < 0).sum() >= 1 and corr > 0.8)
ln5, P5, S5, _q = draw_line(**dict(base_k, length=2.0, width=0.5))
ia = 0
check(f'Length 2 / Width 0.5: the feathers twice as long ({S5[0, 0] / S0[0, 0]:.2f} x), half as wide '
      f'({S5[0, 1] / S0[0, 1]:.2f} x)', abs(S5[0, 0] / S0[0, 0] - 2.0) < 0.02 and abs(S5[0, 1] / S0[0, 1] - 0.5) < 0.02)
for o in C.selected_objects:
    o.select_set(False)
ln5.select_set(True)
C.view_layer.objects.active = ln5
tg = wu.enter_apply_target(C)
check(f'Enter applies the feather line ({tg})', tg is not None and tg[0] == 'greeble_apply')
bpy.ops.mch.greeble_apply()
check(f'applied: real feathers ({len(ln5.data.polygons):,} faces) named Feathers, not live',
      not gl.is_line(ln5) and len(ln5.data.polygons) > 100 and ln5.name.startswith('Feathers')
      and not ln5.modifiers)

summary()
