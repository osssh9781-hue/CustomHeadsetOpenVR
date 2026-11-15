"""0.24.173 (user: "드래곤이나 크리쳐 피막 만들 때 쓸 건데 크리쳐 클로스 탭으로 하나 만들어서 두께는 어플라이 하면 추가 되게 해
주고, 일단 내가 메쉬 위에 따라 그리면 메쉬랑 붙어 있는 부분만 고정되고 나머지는 클로스로 흘러내리게 ... 그리고 사이에 크리쳐 스킨이랑
혈관 같은 거도 만들게 프리셋 만들어 주고" - "피막은 콜리전이 아니라 고정하는 핀 정보로만 내가 만들어 놓은 메쉬에 붙는 걸로"):
Creature Cloth - a membrane drawn over a wing's bones (here the outline in pixels through a fixed front view): pinned
where it is on the bones, the rest a cloth that falls (Space; pins only, no collision), Enter keeps it (+ Thickness,
on the bones), Esc drops it; skin / vein presets.  The real drawing: tests/gui/round173_real_window.py."""
import math
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402
from mathutils import Euler, Vector

import mecha_lab
from mecha_lab import cloth_drape as cd, core_geometry as cg, creature_membrane as cm, tool_state as ts  # noqa: E402
from mecha_lab import ui_tool_settings as uts, workspace_ui as wu  # noqa: E402

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
check('the tool: Creature Cloth in the Creature and the Cloth tools, its icon, its window, its stroke mode, Space runs it',
      'MEMBRANE' in ts.TOOL_BY_ID and 'MEMBRANE' in dict(ts.TOOL_GROUPS)['Creature']
      and 'MEMBRANE' in dict(ts.TOOL_GROUPS)['Cloth'] and 'MEMBRANE' in ts.SHAPE_TOOLS
      and os.path.isfile(os.path.join(os.path.dirname(cm.__file__), 'icons', 'membrane.png'))
      and uts.DRAWERS.get('MEMBRANE') is not None and hasattr(S, 'mch_membrane')
      and 'MEMBRANE' in {i.identifier for i in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items}
      and any(k[0] == 'mch.cdrape_sim' for k in wu.MCH_TOOL_creature_membrane.bl_keymap))
bm = bmesh.new()


def bone(a, b, r):
    a, b = Vector(a), Vector(b)
    d = b - a
    m = bmesh.ops.create_cone(bm, cap_ends=True, segments=12, radius1=r, radius2=r * 0.6, depth=d.length)
    bmesh.ops.rotate(bm, verts=m['verts'], cent=(0, 0, 0), matrix=d.to_track_quat('Z', 'Y').to_matrix())
    bmesh.ops.translate(bm, verts=m['verts'], vec=(a + b) / 2)


bone((0, 0, 1.0), (1.4, 0, 1.15), 0.06)              # (an arm and two fingers: a dragon's wing bones)
bone((1.4, 0, 1.15), (2.4, 0, 0.2), 0.04)
bone((1.4, 0, 1.15), (1.6, 0, -0.3), 0.04)
me = bpy.data.meshes.new('Wing Bones')
bm.to_mesh(me)
bm.free()
bones = bpy.data.objects.new('Wing Bones', me)
S.collection.objects.link(bones)
C.view_layer.update()
FRONT = cg.OrthoProjector(Euler((math.pi / 2, 0, 0)).to_quaternion(), pixels_per_unit=200.0)   # 200 px = 1
PTS = [(0.05, 1.0), (0.7, 1.07), (1.4, 1.15), (1.9, 0.68), (2.38, 0.22), (2.0, 0.1), (1.6, -0.28), (1.0, -0.1),
       (0.4, 0.3), (0.05, 0.6)]                       # (along the arm, down the outer finger, the free edge back)


def loop(pts, y=-3.0):
    return [[FRONT.to_screen(Vector((x, y, z))) for x, z in pts]]


def world(ob, evaluated=False):
    C.view_layer.update()
    m = ob.evaluated_get(C.evaluated_depsgraph_get()).data if evaluated else ob.data
    co = np.empty(len(m.vertices) * 3, np.float32)
    m.vertices.foreach_get('co', co)
    M = np.array(ob.matrix_world)
    return co.reshape(-1, 3) @ M[:3, :3].T + M[:3, 3]


def pins(ob):
    g = ob.vertex_groups[cm.PIN].index
    return np.array([any(x.group == g for x in v.groups) for v in ob.data.vertices])


n_obs = len(bpy.data.objects)
t0 = time.time()
msg = cm.perform(C, loop(PTS), FRONT)
dt = time.time() - t0
mem = C.active_object
W0 = world(mem)
pin = pins(mem)
bones_inv = bones.matrix_world.inverted()
dist = np.array([(bones.matrix_world @ bones.closest_point_on_mesh(bones_inv @ Vector(p))[1] - Vector(p)).length
                 for p in W0[pin]])
mod = mem.modifiers.get(cm.CLOTH_MOD)
check(f'drawn over the bones: a membrane ({len(W0):,} points, {dt:.2f} s), {pin.sum()} pinned - on the bones (off them '
      f'by {dist.max():.4f} at most), the rest free, its shape the drawing (x {W0[:, 0].min():.2f}..{W0[:, 0].max():.2f}, '
      f'z {W0[:, 2].min():.2f}..{W0[:, 2].max():.2f})', cm.is_membrane(mem) and 50 < pin.sum() < 0.5 * len(pin)
      and dist.max() < 0.01 and abs(W0[:, 0].min() - 0.05) < 0.05 and abs(W0[:, 0].max() - 2.38) < 0.05
      and abs(W0[:, 2].max() - 1.15) < 0.05 and abs(W0[:, 2].min() + 0.28) < 0.05, msg)
check('pins only - no collision (light): its cloth pinned by the pin group, collision off, nothing else made, '
      'a Cloth Drape session of its own', mod is not None and mod.settings.vertex_group_mass == cm.PIN
      and not mod.collision_settings.use_collision and not mod.collision_settings.use_self_collision
      and len(bpy.data.objects) == n_obs + 1 and cd.sim_active() and cd.SIM.get('mode') == 'MEMBRANE'
      and not any(m.type == 'COLLISION' for o in bpy.data.objects for m in o.modifiers))
cs_ = mod.settings
check(f'a plain cloth, not the Vacuum Pack\'s film (user: "진공팩보단 좀 더 그냥 클로스에 가까워야"; "중력 값도 좀 더"): '
      f'Gravity {S.mch_membrane.gravity:.0f} % ({cs_.effector_weights.gravity:.1f} x), weight {cs_.mass}, stretch '
      f'{cs_.tension_stiffness:.0f} (cotton 15), soft folds (bending {cs_.bending_stiffness:.2f}), no pressure, no shrink',
      S.mch_membrane.gravity >= 200 and abs(cs_.effector_weights.gravity - S.mch_membrane.gravity / 100) < 1e-4
      and cs_.mass >= 0.3 and cs_.tension_stiffness < 20 and cs_.bending_stiffness > 0.5 and not cs_.use_pressure
      and cs_.shrink_min <= 0)
mat = next(s for s in mem.data.materials if s is not None)
check('its skin: the Dragon preset - no veins (user: "혈관은 그냥 빼 줘도 돼"): no image in it, its own uv kept',
      S.mch_membrane.preset == 'DRAGON' and not any(n.bl_idname == 'ShaderNodeTexImage' for n in mat.node_tree.nodes)
      and mem.data.uv_layers.get('UVMap') is not None and not any(i.name.startswith('MCH Membrane Veins') for i in bpy.data.images))
k = 0
t0 = time.time()
while cd.step(C):
    k += 1
dts = time.time() - t0
W1 = world(mem, evaluated=True)
sag = W1[~pin, 2] - W0[~pin, 2]
check(f'Space: it falls ({k} frames, {dts:.1f} s): the pinned points stay ({np.abs(W1[pin] - W0[pin]).max():.4f}), the '
      f'free part comes down (mean {sag.mean():.3f}, most {sag.min():.3f})', k == S.mch_membrane.frames
      and np.abs(W1[pin] - W0[pin]).max() < 1e-4 and sag.mean() < -0.005 and sag.min() < -0.03)
S.mch_membrane.slack = 30.0                           # (a slider: the session from its first frame again)
check('a slider in the session: back to the first frame, the new value on the cloth',
      cd.SIM['sess']['frame'] == 0 and abs(mod.settings.shrink_min + 0.30) < 1e-6 and not cd.SIM.get('running'))
while cd.step(C):
    pass
W2 = world(mem, evaluated=True)
check(f'more Slack: it hangs lower (mean {sag.mean():.3f} -> {(W2[~pin, 2] - W0[~pin, 2]).mean():.3f})',
      (W2[~pin, 2] - W0[~pin, 2]).mean() < sag.mean())
S.mch_membrane.preset = 'BAT'
pb = next(n for n in mat.node_tree.nodes if n.bl_idname == 'ShaderNodeBsdfPrincipled')
skin = tuple(pb.inputs['Base Color'].default_value)[:3]
check(f'a skin preset on the live membrane: Bat ({np.round(skin, 3)})', np.allclose(skin, cm.LOOK['BAT'][2], atol=1e-4))
S.mch_membrane.style = 'TAUT'                         # (user: "피막은 이 버전까지 해서 옵션을 두 개")
taut = (S.mch_membrane.gravity, S.mch_membrane.slack, mod.settings.mass, round(mod.settings.tension_stiffness, 1),
        cd.SIM['sess']['frame'])
while cd.step(C):
    pass
Wtaut = world(mem, evaluated=True)
S.mch_membrane.style = 'CLOTH'
cloth = (S.mch_membrane.gravity, S.mch_membrane.slack, mod.settings.mass, round(mod.settings.tension_stiffness, 1))
while cd.step(C):
    pass
Wcl = world(mem, evaluated=True)
dz_t = (Wtaut[~pin, 2] - W0[~pin, 2]).mean()
dz_c = (Wcl[~pin, 2] - W0[~pin, 2]).mean()
check(f'two styles: Taut Skin (the first version: gravity / slack / weight / stretch {taut[:4]}, from frame '
      f'{taut[4]} again) and Hanging Cloth ({cloth}): the cloth hangs lower ({dz_t:.3f} -> {dz_c:.3f})',
      taut[:2] == (100.0, 15.0) and abs(taut[2] - 0.15) < 1e-6 and taut[3] == 22.0 and cloth[:2] == (250.0, 10.0)
      and taut[4] == 0
      and abs(cloth[2] - 0.3) < 1e-6 and dz_c < dz_t, (taut, cloth))
tg = wu.enter_apply_target(C)
r = getattr(bpy.ops.mch, tg[0])() if tg else None
size = cd.SIM.get('size', 0) if cd.SIM else 0
W3 = world(mem)
sol = mem.modifiers.get(cm.THICK_MOD)
check(f'Enter keeps it ({tg}): a plain mesh as it hangs (no cloth), Thickness added (Solidify '
      f'{sol and round(sol.thickness, 4)}), still on the bones (its parent), the frame back',
      tg is not None and tg[0] == 'membrane_keep' and r == {'FINISHED'} and not cd.sim_active()
      and mem.modifiers.get(cm.CLOTH_MOD) is None and sol is not None and sol.thickness > 0
      and mem.parent == bones and np.abs(W3 - Wcl).max() < 1e-4 and not cm.is_membrane(mem) and S.frame_current == 1)
bones.location.x += 1.0
moved = world(mem)
check('it moves with the bones (parented)', np.allclose(moved[:, 0] - W3[:, 0], 1.0, atol=1e-4))
bones.location.x -= 1.0
cm.perform(C, loop([(0.3, 1.02), (1.0, 1.1), (0.9, 0.4), (0.3, 0.5)]), FRONT)
out = cd.cancel(C)
check(f'Esc drops a new one ({out})', not any(o.get(cm.KEY) for o in bpy.data.objects) and not cd.sim_active())
from mecha_lab import lasso_sketch  # noqa: E402
S.mch_brush.sketch_first = True                       # (user: "당연히 스케치 모드도 되지?")
lasso_sketch.add(C, 'MEMBRANE', loop([(0.3, 1.02), (1.0, 1.1), (1.0, 0.4), (0.3, 0.5)]), FRONT)
lasso_sketch.add(C, 'MEMBRANE', loop([(0.9, 1.1), (1.6, 1.0), (1.6, 0.3), (0.9, 0.3)]), FRONT)
msg_s = lasso_sketch.commit(C)
m3 = C.active_object
Ws = world(m3)
check(f'Sketch mode: shapes drawn first, Enter makes the membrane from them ({msg_s[:60]}...)',
      'MEMBRANE' in lasso_sketch.MODES and cm.is_membrane(m3) and cd.SIM.get('mode') == 'MEMBRANE'
      and Ws[:, 0].min() < 0.35 and Ws[:, 0].max() > 1.55)
cd.cancel(C)
S.mch_brush.sketch_first = False
try:
    cm.perform(C, loop([(4.0, 3.0), (5.0, 3.0), (5.0, 4.0)]), FRONT)
    err = ''
except cg.CutError as ex:
    err = str(ex)
check(f'drawn where no mesh is: told to draw it over the mesh ("{err}")', 'over your mesh' in err)
summary()
