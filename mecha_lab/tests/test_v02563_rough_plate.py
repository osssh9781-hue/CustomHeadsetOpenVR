"""0.24.161 (user: "디테일 플레이트 하나 더 만들자 - 내가 그으면 약간 외각 부분이 콘크리트나 크리쳐 질감처럼 디테일이 있는 거야, 돌처럼
있어도 되고 - 그 디테일 프리셋도 한 10개"): Plate Detail 4 (Rough Rim) - a raised plate whose rim is rough (concrete, stone,
creature skin), the texture strongest at the outline and fading inward; 10 presets; live until Apply; Alt cuts / engraves.
Outlines through a fixed top view; measured on the evaluated mesh.  The real clicks: tests/gui/rough_plate_real_window.py."""
import math
import os
import time

import numpy as np
from _harness import bpy, check, fresh, summary
import bmesh  # noqa: E402  (after bpy)
from mathutils import Quaternion

import mecha_lab
from mecha_lab import (core_geometry as cg, cut_engine as ce, key_legend as kl, lasso_line as ll,  # noqa: E402
                       lasso_sketch as lsk, live_subtract as lsub, plate_detail as pd, plate_rough as pr,
                       quick_hud as qh, target_rules as tr, tool_state as ts, ui_tool_settings as uts)

fresh()
mecha_lab.register()
C = bpy.context
S = C.scene
TOP = cg.OrthoProjector(Quaternion(), pixels_per_unit=100.0)        # (looking down: 100 px = 1, (500, 500) = origin)
icons = os.path.join(os.path.dirname(pd.__file__), 'icons')
check('the tool: Plate Detail 4 in Surface detail (after Detail 3), its icon, window, HUD, Alt line, the shared lasso',
      'DETAIL4' in ts.TOOL_BY_ID and ts.TOOL_BY_ID['DETAIL4'][3] == 'detail4'
      and os.path.isfile(os.path.join(icons, 'detail4.png'))
      and dict(ts.TOOL_GROUPS)['Surface detail'].index('DETAIL4') == dict(ts.TOOL_GROUPS)['Surface detail'].index('DETAIL3') + 1
      and uts.DRAWERS.get('DETAIL4') is not None and 'DETAIL4' in qh.SPEC and 'DETAIL4' in kl.ALT
      and 'DETAIL4' in ll.MODES and 'DETAIL4' in lsk.MODES and 'DETAIL4' in tr.PICKING and 'DETAIL4' in ts.SHAPE_TOOLS
      and 'DETAIL4' in bpy.ops.mch.cut_stroke.get_rna_type().properties['mode'].enum_items.keys()
      and pd.KINDS['DETAIL4'] == 'ROUGH')
check('ten rough presets, each its own mix (+ Columnar Basalt, 0.24.163)', len(pr.PRESETS) == 11 and len(
      {tuple(sorted((k, str(v)) for k, v in p[3].items())) for p in pr.PRESETS}) == 11,
      [p[1] for p in pr.PRESETS])


def blob(cx, cy, rx, ry, n=64, k=3, wob=0.1):
    return [[(500 + (cx + rx * math.cos(a) * (1 + wob * math.sin(k * a))) * 100,
              500 + (cy + ry * math.sin(a)) * 100) for a in np.linspace(0, 2 * math.pi, n, endpoint=False)]]


def ev(ob):
    dg = C.evaluated_depsgraph_get()
    return ob.evaluated_get(dg).data


def arr(me, name, width=1):
    at = me.attributes[name]
    a = np.empty(len(at.data) * width, np.float32)
    at.data.foreach_get('vector' if width == 3 else 'value', a)
    return a.reshape(-1, width) if width > 1 else a


def coords(me):
    a = np.empty(len(me.vertices) * 3, np.float32)
    me.vertices.foreach_get('co', a)
    return a.reshape(-1, 3)


def vol(o):
    b = bmesh.new()
    b.from_mesh(o.data)
    v = b.calc_volume()
    b.free()
    return v


def clear():
    for o in list(bpy.data.objects):
        bpy.data.objects.remove(o)


def pick(ob):
    for o in C.selected_objects:
        o.select_set(False)
    if ob is not None:
        ob.select_set(True)
    C.view_layer.objects.active = ob


clear()
bpy.ops.mesh.primitive_plane_add(size=6.0)
ground = C.active_object
pick(None)
bpy.ops.mch.pdetail_rough_preset(preset='CONCRETE')
pick(ground)
t0 = time.time()
msg = pd.perform(C, blob(0, 0, 1.4, 1.0), TOP, 'DETAIL4')
t_make = time.time() - t0
plate = C.active_object
p = plate.mch_pdetail
base = plate.data
names = {a.name for a in base.attributes}
check('drawn on a plane: a live rough plate on it (kind Rough Rim, Concrete), the base shell with its distance / top / '
      'normal on every point', pd.is_detail(plate) and p.kind == 'ROUGH' and p.r_preset == 'CONCRETE'
      and plate.modifiers.get(pr.MOD) is not None and {pr.D_ATTR, pr.TOP_ATTR, pr.UP_ATTR} <= names
      and plate.parent == ground, msg)
t0 = time.time()
me = ev(plate)
t_eval = time.time() - t0
P = coords(me)
d = arr(me, pr.D_ATTR)
top = arr(me, pr.TOP_ATTR) > 0.5
rough = arr(me, pr.OUT_ATTR)
check('...subdivided as fine as the texture needs (many more faces than the base), a closed shell',
      len(me.polygons) > 20 * len(base.polygons), (len(base.polygons), len(me.polygons)))
inner = top & (d > p.r_ramp * 2) & (d > p.r_rim * 2)
h_in = float(np.median(P[inner, 2]))
check(f'...its top {h_in * 1000:.1f} mm up inside (Height {p.r_height * 1000:.1f} mm), the bottom under the surface',
      abs(h_in - p.r_height) < 0.25 * p.r_height and P[~top, 2].max() < 1e-4, (h_in, P[~top, 2].max()))
band = top & (d > p.r_ramp) & (d < p.r_rim * 0.6)
core = top & (d > p.r_rim * 1.5)
sb, sc = float(np.std(rough[band])), float(np.std(rough[core]))
check(f'...the texture strong along the rim, weak inside (rough std rim {sb:.3f} vs inside {sc:.3f})',
      sb > 2.5 * sc and sb > 0.05, (sb, sc))
check(f'...made in {t_make:.2f} s, worked out in {t_eval:.2f} s', t_make < 3.0 and t_eval < 3.0, (t_make, t_eval))

# Chips: the outline eaten in - near the outline fewer points at full height
near = top & (d > p.r_ramp) & (d < p.r_rim * 0.5)
full = float(np.mean(P[near, 2] > 0.6 * p.r_height))
p.r_chips = 0.0
P0 = coords(ev(plate))
full0 = float(np.mean(P0[near, 2] > 0.6 * p.r_height))
check(f'Chips: pieces broken off the edge (near the outline at full height: Chips 0.45 {full:.0%}, Chips 0 {full0:.0%})',
      full0 - full > 0.08, (full, full0))
sunk = float(np.mean(P[near, 2] < 0.0))
check(f'...where a piece is broken off, the plate goes just under the surface (the surface shows, no thin film of the '
      f'plate on it): {sunk:.0%} of the rim under it, the lowest {P[top, 2].min() * 1000:.2f} mm',
      sunk > 0.05 and -p.size * 0.0016 < P[top, 2].min() < 0.0, (sunk, P[top, 2].min()))

# live: a value straight into the modifier (no rebuild), Strength 0 = smooth
s0 = p.r_strength
p.r_chips = 0.0
p.r_strength = 0.0
me2 = ev(plate)
r2 = arr(me2, pr.OUT_ATTR)
P2 = coords(me2)
check('Strength 0: a smooth plate (texture flat to the profile), the base mesh kept (the value went to the modifier)',
      plate.data == base and float(np.std(P2[inner, 2])) < 1e-4, float(np.std(P2[inner, 2])))
p.r_strength = s0 * 2.5
P3 = coords(ev(plate))
check('Strength up: the rim rougher at once', float(np.std(P3[band, 2])) > float(np.std(P0[band, 2])),
      (float(np.std(P3[band, 2])), float(np.std(P0[band, 2]))))
q1 = coords(ev(plate))[band, 2].copy()
p.r_seed = 7
q2 = coords(ev(plate))[band, 2]
check('Seed: another pattern', float(np.abs(q1 - q2).mean()) > 1e-4, float(np.abs(q1 - q2).mean()))
p.r_center = 1.0
r_c = arr(ev(plate), pr.OUT_ATTR)
check('Center 1: the texture inside as strong as at the rim', float(np.std(r_c[core])) > 0.5 * float(np.std(r_c[band])),
      (float(np.std(r_c[core])), float(np.std(r_c[band]))))
p.r_center = 0.1
lv_lo = pr.level_for(p, len(base.polygons))
p.r_detail = 12.0
lv_hi = pr.level_for(p, len(base.polygons))
check(f'Detail: finer when raised (level {lv_lo} -> {lv_hi}), never over the face limit',
      lv_hi >= lv_lo and len(base.polygons) * 4 ** lv_hi <= pr.MAX_FACES, (lv_lo, lv_hi))
p.r_detail = 6.0
p.r_strength = 0.0
slope = top & (np.abs(d - 0.3 * p.r_ramp) < 0.08 * p.r_ramp)
hs = {}
for prof in ('ROUND', 'DOME', 'CHAMFER'):
    p.r_profile = prof
    hs[prof] = float(np.median(coords(ev(plate))[slope, 2])) / p.r_height
check(f'Edge: 30 % in on the slope - Round {hs["ROUND"]:.2f}, Dome {hs["DOME"]:.2f}, Chamfer {hs["CHAMFER"]:.2f} of the '
      'height (soft S / steep foot / straight)', abs(hs['ROUND'] - 0.163) < 0.05 and abs(hs['DOME'] - 0.454) < 0.05
      and abs(hs['CHAMFER'] - 0.3) < 0.05, hs)
p.r_profile = 'ROUND'
p.r_strength = s0

# presets on the live plate: every value from the preset (lengths for this plate's size)
bpy.ops.mch.pdetail_rough_preset(preset='SKIN')
check('a preset on the selected plate: Creature Skin - its values (lengths x this size)',
      p.r_preset == 'SKIN' and abs(p.r_rim - pr.preset_values('SKIN')['r_rim'] * p.size) < 1e-6
      and p.r_wrinkles == 1.0 and p.r_chips == 0.0, (p.r_rim, p.size))
sig = {}
for pid in pr.PRESET_IDS:
    bpy.ops.mch.pdetail_rough_preset(preset=pid)
    mm = ev(plate)
    z = coords(mm)[:, 2]
    sig[pid] = (round(float(z.max()), 5), round(float(np.std(arr(mm, pr.OUT_ATTR))), 4) if pr.OUT_ATTR in mm.attributes
                else -1.0)                                      # (Columnar Basalt: columns, no texture attribute)
check('all eleven presets make a plate, each a different one', len(set(sig.values())) == 11 and all(v[0] > 0 for v in sig.values()),
      sig)
# remembered: the next plate starts from the last edited one (lengths as fractions of the size)
bpy.ops.mch.pdetail_rough_preset(preset='BARK')
p.r_strength = p.size * 0.02
pick(ground)
pd.perform(C, blob(0, 0, 0.7, 0.5), TOP, 'DETAIL4')
p2 = C.active_object.mch_pdetail
check('the next plate starts from the last edited one (Bark, Strength as the same part of its size)',
      p2.r_preset == 'BARK' and abs(p2.r_strength / p2.size - 0.02) < 1e-4 and p2.r_wrinkles == 1.0,
      (p2.r_preset, p2.r_strength / p2.size))
bpy.data.objects.remove(C.active_object)
# another kind edited in between (a Plate Detail 3 panel): the next rough plate still the last rough one's values
pick(ground)
pd.perform(C, blob(0, 0, 0.6, 0.4), TOP, 'DETAIL3')
flat = C.active_object
flat.mch_pdetail.flat_h = flat.mch_pdetail.flat_h * 1.5
bpy.data.objects.remove(flat)
pick(ground)
pd.perform(C, blob(0, 0, 0.7, 0.5), TOP, 'DETAIL4')
p3 = C.active_object.mch_pdetail
check('...a Plate Detail 3 edited in between does not change that (still Bark, its mix and sizes)',
      p3.r_preset == 'BARK' and p3.r_wrinkles == 1.0 and abs(p3.r_strength / p3.size - 0.02) < 1e-4
      and abs(p3.r_rim / p3.size - pr.preset_values('BARK')['r_rim']) < 1e-4, (p3.r_preset, p3.r_wrinkles, p3.r_rim / p3.size))
bpy.data.objects.remove(C.active_object)

# Alt + draw over the live plate: that area cut out, still live
pick(plate)
v_before = len(ev(plate).polygons)
msg = lsub.perform(C, 'DETAIL', [[(470, 470), (530, 470), (530, 530), (470, 530)]], TOP, tool='DETAIL4')
me_cut = ev(plate)
Pc = coords(me_cut)
hole = (np.abs(Pc[:, 0]) < 0.25) & (np.abs(Pc[:, 1]) < 0.25)
check('Alt + draw on the live plate: a hole cut out of it, it stays live (its modifier, its values)',
      'Cut out' in msg and pd.is_detail(plate) and plate.modifiers.get(pr.MOD) is not None and hole.sum() == 0, msg)

# Apply: the modifier made real, the helper attributes gone, the texture attribute kept
n_ev = len(ev(plate).polygons)
pick(plate)
bpy.ops.mch.pdetail_apply()
names = {a.name for a in plate.data.attributes}
check('Apply: a plain mesh as it was (the modifier applied), no more live, its helper attributes gone',
      not pd.is_detail(plate) and plate.modifiers.get(pr.MOD) is None and len(plate.data.polygons) == n_ev
      and not ({pr.D_ATTR, pr.TOP_ATTR, pr.UP_ATTR} & names) and pr.OUT_ATTR in names, (n_ev, len(plate.data.polygons)))

# on a curved surface: the plate follows it
clear()
bpy.ops.mesh.primitive_uv_sphere_add(radius=2.0, segments=64, ring_count=32, location=(0, 0, -2.0))
ball = C.active_object
pick(None)
bpy.ops.mch.pdetail_rough_preset(preset='STONE')
pick(ball)
pd.perform(C, blob(0, 0, 0.9, 0.7), TOP, 'DETAIL4')
pl = C.active_object
mm = ev(pl)
Pw = coords(mm) @ np.array(pl.matrix_world)[:3, :3].T + np.array(pl.matrix_world.translation)
rad = np.linalg.norm(Pw - np.array((0, 0, -2.0)), axis=1)
tp = arr(mm, pr.TOP_ATTR) > 0.5
check(f'on a sphere: the plate follows the surface (bottom {rad[~tp].min():.3f} - {rad[~tp].max():.3f}, top up to '
      f'{rad[tp].max():.3f}; radius 2)', abs(rad[~tp].max() - 2.0) < 0.01 and rad[~tp].min() > 1.97
      and 2.0 < rad[tp].max() < 2.0 + 3 * pl.mch_pdetail.r_height, (rad[~tp].min(), rad[~tp].max(), rad[tp].max()))

# Alt over a plain mesh: the rough plate engraved into it
clear()
bpy.ops.mesh.primitive_cube_add(size=8, location=(0, 0, -4))
cube_ob = C.active_object
v0 = vol(cube_ob)
f0 = len(cube_ob.data.polygons)
msg = lsub.perform(C, 'DETAIL', [[(400, 400), (600, 400), (600, 600), (400, 600)]], TOP, tool='DETAIL4')
check('Alt over a plain mesh: the rough plate engraved into it (no new object, a shallow rough recess)',
      'Engraved' in msg and len(bpy.data.objects) == 1 and vol(cube_ob) < v0 and v0 - vol(cube_ob) < 0.4
      and len(cube_ob.data.polygons) > 50 * f0, (msg, v0 - vol(cube_ob), len(cube_ob.data.polygons)))

mecha_lab.unregister()
check('unregisters', not hasattr(bpy.types, 'MCH_OT_pdetail_rough_preset'))
summary()
