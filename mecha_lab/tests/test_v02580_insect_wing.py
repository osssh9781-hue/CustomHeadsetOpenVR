"""0.24.173 (user: "이건 시뮬은 필요 없는데 잠자리 날개나 곤충 날개 같은 거 만들 수 있게 내가 그린 영역 내부에 곤충 날개 무늬가
양각으로 드러나게 해 줘"): the Insect Wing tool - a wing's outline drawn (here in pixels through a fixed front view):
a thin wing plate in that shape, its veins raised on it (both sides), six presets, live sliders, Enter keeps it.
The real drawing: tests/gui/round173_real_window.py."""
import math
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import core_geometry as cg, insect_wing as iw, tool_state as ts, ui_tool_settings as uts  # noqa: E402
from mecha_lab import workspace_ui as wu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('the tool: Insect Wing in the Creature tools, its icon, its window, its stroke mode',
      'WING' in ts.TOOL_BY_ID and 'WING' in dict(ts.TOOL_GROUPS)['Creature'] and 'WING' in ts.SHAPE_TOOLS
      and os.path.isfile(os.path.join(os.path.dirname(iw.__file__), 'icons', 'wing.png'))
      and uts.DRAWERS.get('WING') is not None and hasattr(S, 'mch_wing')
      and 'WING' in {i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items})
bpy.ops.mesh.primitive_uv_sphere_add(radius=0.25, location=(0, 0, 0))
body = C.active_object
body.scale = (0.6, 0.6, 1.6)
bpy.ops.object.transform_apply(location=False, rotation=False, scale=True)
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1


def outline(x0, z0, L, Wd, n=80, reverse=False):
    """A wing from (x0, z0) to the right: a straight leading edge on top, a bulging trailing edge below."""
    pts = [(x0 + L * i / (n - 1), z0 + 0.02 * L * math.sin(math.pi * i / (n - 1))) for i in range(n)]
    pts += [(x0 + L * (1 - i / (n - 1)), z0 - Wd * math.sin(math.pi * (1 - i / (n - 1))) ** 0.7)
            for i in range(n)]
    if reverse:
        pts = pts[n:] + pts[:n]                        # (drawing started at the tip)
    return [[FRONT.to_screen(Vector((x, -2.0, z))) for x, z in pts]]


def mesh_data(ob):
    me = ob.data
    co = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', co)
    W = co.reshape(-1, 3) @ np.array(ob.matrix_world)[:3, :3].T + np.array(ob.matrix_world)[:3, 3]
    return W


S.mch_wing.preset = 'DRAGONFLY'
t0 = time.time()
msg = iw.perform(C, outline(0.15, 0.3, 1.2, 0.26, reverse=True), FRONT)
dt = time.time() - t0
wing = C.active_object
W = mesh_data(wing)
bm = bmesh.new()
bm.from_mesh(wing.data)
closed = all(e.is_manifold for e in bm.edges)
bm.free()
check(f'a drawn outline: an insect wing ({len(wing.data.polygons):,} faces, {dt:.2f} s), a closed thin plate in the '
      f'plane of the drawing (y {W[:, 1].min():.3f}..{W[:, 1].max():.3f}), live', iw.is_wing(wing) and closed
      and len(wing.data.polygons) > 2000 and np.ptp(W[:, 0]) > 1.15 and dt < 4.0, msg)
d = iw.data(wing)
root = np.array(d['outline'][d['root']])
check(f'its root: the outline\'s point nearest the body (drawing started at the tip): x {wing.matrix_world.translation.x:.3f}',
      'root at the mesh' in msg and wing.matrix_world.translation.x < 0.25)
L = wing['mch_wing_size']
front = -W[:, 1]                                       # (toward the viewer: + y is away)
plane_y = float(np.median(W[:, 1]))
top = W[W[:, 1] < plane_y]
h = -(top[:, 1] - top[:, 1].max())                   # (how far each top point stands out of the membrane)
base = float(np.percentile(h, 30))
raised = (h - base) > 0.3 * L * wing.mch_wing.vein_height / 100.0
check(f'the veins raised: the top stands out up to {h.max() - base:.4f} (Vein Height {wing.mch_wing.vein_height} % of '
      f'{L:.2f} = {L * wing.mch_wing.vein_height / 100:.4f}) on {raised.mean() * 100:.0f} % of it (the veins), the rest '
      f'flat', abs((h.max() - base) - L * wing.mch_wing.vein_height / 100.0) < 0.35 * L * wing.mch_wing.vein_height / 100.0
      and 0.05 < raised.mean() < 0.6)
mat = wing.data.materials[0]
im = next((n.image for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage'), None)
check(f'its material: the veins\' image (crisp: {im and tuple(im.size)}, packed {im and im.packed_file is not None}), '
      f'a thin membrane (alpha), iridescent (thin film)', im is not None and im.size[0] > 800 and im.packed_file is not None
      and any(n.bl_idname == 'ShaderNodeBsdfPrincipled' and n.inputs['Alpha'].is_linked for n in mat.node_tree.nodes)
      and wing.data.uv_layers.get('UVMap') is not None)


def coverage(ob):
    im_ = next(n.image for n in ob.data.materials[0].node_tree.nodes if n.bl_idname == 'ShaderNodeTexImage')
    px = np.empty(im_.size[0] * im_.size[1] * 4, np.float32)
    im_.pixels.foreach_get(px)
    return float((px.reshape(-1, 4)[:, 0] > 0.05).mean())


cov = {}
for pid, _l, _s in iw.PRESETS:
    wing.mch_wing.preset = pid
    cov[pid] = coverage(wing)
check(f'six presets, each its own veins (image covered: {", ".join(f"{k} {v:.3f}" for k, v in cov.items())}): a '
      f'dragonfly\'s net of cells the most, a fly\'s few veins the least',
      len(cov) == 6 and cov['DRAGONFLY'] > cov['BEE'] and cov['DRAGONFLY'] > 1.5 * cov['FLY']
      and cov['LACEWING'] > cov['FLY'] and len({round(v, 4) for v in cov.values()}) == 6)
from mecha_lab import wing_photo as wp  # noqa: E402
pinfo = {}
for pid, label, fname, look, given in wp.PHOTOS:
    pfr, pfield = wp.load(pid)
    end_w = []
    for s_ in (0.04, 0.96):                           # (the root end narrower than the tip end)
        end_w.append(float(np.interp(s_, pfr.S, pfr.lead_w) - np.interp(s_, pfr.S, pfr.trail_w)))
    wing.mch_wing.preset = pid
    pinfo[pid] = (round(pfr.L), round(end_w[0], 3), round(end_w[1], 3), round(coverage(wing), 3))
check(f'four photo patterns (the user\'s black-and-white wings: white = vein): each photo\'s wing found (length in '
      f'pixels, width at the root / near the tip, the drawn wing\'s veins covered: {pinfo})',
      len(pinfo) == 4 and all(v[0] > 300 and v[1] < v[2] + 0.2 and 0.03 < v[3] < 0.6 for v in pinfo.values())
      and all(os.path.isfile(os.path.join(wp.DIR, f[2])) for f in wp.PHOTOS))
wing.mch_wing.preset = 'P_CICADA'
cp1 = coverage(wing)
wing.mch_wing.vein_width = 2.0
cp2 = coverage(wing)
wing.mch_wing.vein_width = 1.0
wing.mch_wing.flip = True
cp3 = coverage(wing)
wing.mch_wing.flip = False
Wp = mesh_data(wing)
check(f'a photo pattern on the drawn wing: Vein Width widens its veins ({cp1:.3f} -> {cp2:.3f}), Flip lays it the other '
      f'way ({cp3:.3f}), raised as the others ({np.ptp(Wp[:, 1]):.4f} thick at most)', cp2 > cp1 * 1.2
      and abs(cp3 - cp1) > 1e-4 and np.ptp(Wp[:, 1]) > 0.004)
wing.mch_wing.preset = 'DRAGONFLY'
c1 = coverage(wing)
wing.mch_wing.density = 2.0
c2 = coverage(wing)
wing.mch_wing.density = 1.0
wing.mch_wing.vein_height = 0.0
Wf = mesh_data(wing)
flat = np.ptp(Wf[:, 1])
wing.mch_wing.vein_height = 0.6
check(f'live sliders: Vein Density 2 -> more veins ({c1:.3f} -> {c2:.3f}); Vein Height 0 -> a flat plate ({flat:.4f} '
      f'thick = Thickness {wing.mch_wing.thickness} % of the length)', c2 > c1 * 1.3
      and abs(flat - L * wing.mch_wing.thickness / 100.0) < 0.2 * L * wing.mch_wing.thickness / 100.0)
Wb0 = mesh_data(wing)
wing.mch_wing.bend = math.radians(60)
Wb = mesh_data(wing)
wing.mch_wing.bend = 0.0
wing.mch_wing.twist = math.radians(45)
Wt = mesh_data(wing)
wing.mch_wing.twist = 0.0
rootp = np.array(wing.matrix_world.translation)
d0 = np.linalg.norm(Wb0 - rootp, axis=1)
near = d0 < 0.05 * L
far = d0 > 0.9 * np.percentile(d0, 99)
off_b = np.abs(Wb[:, 1] - Wb0[:, 1])
tip_dir = float(np.mean(Wb[far, 1] - Wb0[far, 1]))
spread_t = float(np.ptp(Wt[far, 1]))
check(f'Bend / Twist from the root (user: "뿌리 부분을 기준으로 밴드랑 트위스트"): the root stays (moved {off_b[near].max():.4f}), '
      f'Bend 60 deg lifts the tip off the plane ({np.abs(tip_dir):.3f} toward you: {tip_dir < 0}), Twist 45 deg turns the '
      f'tip end round its length (it spans {spread_t:.3f} across the plane, flat {np.ptp(Wb0[far, 1]):.3f})',
      off_b[near].max() < 0.01 * L and tip_dir < -0.3 * L and spread_t > 0.04 * L and np.ptp(Wb0[far, 1]) < 0.02 * L)
r = bpy.ops.mch.wing_preset(preset='CICADA')
check('a preset button: the selected wing takes it (and the next wing too)', r == {'FINISHED'}
      and wing.mch_wing.preset == 'CICADA' and S.mch_wing.preset == 'CICADA')
f0 = iw.Frame(np.array(d['outline']), d['root'])
f1 = iw.Frame(np.array(d['outline']), d['root'], flip=True)
lead_z0 = float(np.mean(f0.point(np.array([0.5]), np.array([0.0]))[:, 1]))
lead_z1 = float(np.mean(f1.point(np.array([0.5]), np.array([0.0]))[:, 1]))
check(f'its leading edge: the straighter side (the top here, at {lead_z0:.3f} in the plane), Flip: the other one '
      f'({lead_z1:.3f})', lead_z0 > lead_z1)
# 0.24.174 (user: "인섹트 윙은 내가 그린 대로 안 나와, 혈관이"): the veins follow the shape as drawn - a curved (banana) wing
ban_in, ban_out = [], []
for i in range(60):
    t = i / 59
    an = math.radians(-20 + 80 * t)
    w_ = 0.18 * math.sin(math.pi * t) ** 0.7 + 0.02
    cx, cz = 1.2 * math.sin(an), 1.2 * (1 - math.cos(an))
    nx_, nz_ = -math.sin(an), math.cos(an)
    ban_in.append((cx + nx_ * w_ * 0.3, cz + nz_ * w_ * 0.3))
    ban_out.append((cx - nx_ * w_, cz - nz_ * w_))
BAN = np.array(ban_in + ban_out[::-1])
from mecha_lab import outline_mesh as om  # noqa: E402
ss, ff = np.meshgrid(np.linspace(0.05, 0.95, 19), np.linspace(0.1, 0.9, 9))
old = iw.Frame(BAN, 0)
new = iw.HFrame(BAN, 0)
in_new = om.inside(new.point(ss.ravel(), ff.ravel()).reshape(-1, 2), [BAN]).mean()
lead_new = new.point(np.linspace(0.05, 0.95, 40), np.zeros(40)).reshape(-1, 2)
d_lead = om.seg_distance(lead_new, BAN[new.lead_arc], closed=False).max()


def spread(fr_):
    """How evenly its long veins spread across it: their ink in the third by the leading edge, the middle third, the
    third by the trailing edge (the drawn shape's own across, the same for both frames)."""
    spec_ = dict(iw.SPEC['FLY'], cross=0.0, cells=0.0)
    vl, st_ = iw.veins(fr_, spec_)
    vl = [v for v in vl if not v[2]]                    # (the margin left out: it runs round both edges)
    px_ = fr_.L / 600.0
    img, lo_ = iw.raster(fr_, vl, st_, px_)
    H_, W_ = img.shape[:2]
    gx_, gy_ = np.meshgrid(lo_[0] + np.arange(W_) * px_, lo_[1] + np.arange(H_) * px_)
    Q = np.c_[gx_.ravel(), gy_.ravel()]
    ins = om.inside(Q, [BAN])
    v = img[..., 0].ravel()[ins]
    f_ = new.sf(Q[ins])[:, 1]
    third = [float(v[(f_ >= k / 3) & (f_ < (k + 1) / 3)].sum()) for k in range(3)]
    return min(third) / max(max(third), 1e-9), third


s_old, t_old = spread(old)
s_new, t_new = spread(new)
check(f'the veins follow the drawn shape (a curved wing): its long veins spread across it (least / most third '
      f'{s_new:.2f}; the straight frame before: {s_old:.2f} - bunched to one edge), all its places inside it '
      f'({in_new * 100:.0f} %), its leading edge on the drawn edge (off {d_lead:.4f} at most)',
      s_new > 0.12 and s_old < 0.05 and in_new > 0.98 and d_lead < 0.02)
from mecha_lab import lasso_sketch  # noqa: E402
S.mch_brush.sketch_first = True                       # (user: "당연히 스케치 모드도 되지?")
n_before = len([o for o in bpy.data.objects if iw.is_wing(o)])
m1 = lasso_sketch.add(C, 'WING', outline(0.15, -0.4, 1.0, 0.22), FRONT)
m2 = lasso_sketch.add(C, 'WING', outline(0.8, -0.4, 0.5, 0.18), FRONT)          # (added to it: one shape)
check(f'Sketch mode: drawing only sketches ({m1[:40]}...), no wing yet', len([o for o in bpy.data.objects
      if iw.is_wing(o)]) == n_before and lasso_sketch.data(S) is not None)
m3 = lasso_sketch.commit(C)
w2 = C.active_object
S.mch_brush.sketch_first = False
n_after = len([o for o in bpy.data.objects if iw.is_wing(o)])
check(f'Sketch mode: shapes drawn first (nothing made yet: {n_before} live wing -> still {n_before}), Enter makes one '
      f'wing from them ({m3}), {np.ptp(mesh_data(w2)[:, 0]):.2f} wide (both shapes)', 'WING' in lasso_sketch.MODES
      and n_after == n_before + 1 and iw.is_wing(w2) and lasso_sketch.data(S) is None
      and np.ptp(mesh_data(w2)[:, 0]) > 1.1)
for o in C.selected_objects:
    o.select_set(False)
wing.select_set(True)
w2.select_set(True)
C.view_layer.objects.active = wing
tg = wu.enter_apply_target(C)
r = getattr(bpy.ops.mch, tg[0])() if tg else None
check(f'Enter keeps the selected wings ({tg}): plain meshes, their veins and material kept',
      tg is not None and tg[0] == 'wing_apply' and r == {'FINISHED'} and not iw.is_wing(wing) and not iw.is_wing(w2)
      and len(wing.data.polygons) > 2000 and wing.data.materials[0] is not None)
summary()
